#!/usr/bin/env bash
# hooks/post-tool-use.sh — track-changes PostToolUse hook (audit log).
#
# Event:   PostToolUse on Write / Edit / MultiEdit
# Purpose: When tracking is active for the just-edited file, diff the
#          file's current mark-state against the prior-state cache and
#          append an entry to the project's .tc-history.md audit log
#          describing introduced and resolved marks.
#
# Stdin:   Hook event JSON payload from Claude Code.
# Stdout:  (none)
# Stderr:  (none under normal operation)
# Exit:    0 always — the audit log is best-effort; failure must not
#          block the user's workflow.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=../lib/tc-common.sh
if ! source "${SCRIPT_DIR}/../lib/tc-common.sh" 2>/dev/null; then
  exit 0
fi
# shellcheck source=../lib/tc-history.sh
if ! source "${SCRIPT_DIR}/../lib/tc-history.sh" 2>/dev/null; then
  exit 0
fi

# Drain stdin.
PAYLOAD=""
if [ ! -t 0 ]; then
  PAYLOAD="$(cat 2>/dev/null || true)"
fi
if [ -z "${PAYLOAD}" ]; then exit 0; fi

if ! command -v jq >/dev/null 2>&1; then
  tc_log "post-tool-use.sh: jq missing; skip"
  exit 0
fi

TOOL_NAME="$(printf '%s' "${PAYLOAD}" | jq -r '.tool_name // empty' 2>/dev/null || true)"
case "${TOOL_NAME}" in
  Write|Edit|MultiEdit) ;;
  *) exit 0 ;;
esac

FILE_PATH="$(printf '%s' "${PAYLOAD}" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
if [ -z "${FILE_PATH}" ]; then exit 0; fi

FILE_TYPE="$(tc_file_type "${FILE_PATH}")"
case "${FILE_TYPE}" in
  md|qmd|tex) ;;
  *) exit 0 ;;
esac

# File must exist post-edit. (If the tool failed, we wouldn't have arrived
# here in normal Claude Code, but bail defensively.)
if [ ! -f "${FILE_PATH}" ]; then exit 0; fi

# Activation gate — only log tracked files.
ACTIVATION_REASON="$(tc_should_track "${FILE_PATH}" 2>/dev/null || printf 'off-default')"
case "${ACTIVATION_REASON}" in
  on-marker-presence|on-marker-listed|on-file) ;;
  *) exit 0 ;;
esac

# Resolve absolute path of the file (cache key uses abs path).
ABS_FILE="$(cd "$(dirname "${FILE_PATH}")" 2>/dev/null && pwd)/$(basename "${FILE_PATH}")"

CACHE_PATH="$(tc_history_cache_path "${ABS_FILE}" 2>/dev/null || true)"
LOG_PATH="$(tc_history_log_path "${ABS_FILE}" 2>/dev/null || true)"
if [ -z "${CACHE_PATH}" ] || [ -z "${LOG_PATH}" ]; then
  tc_log "post-tool-use.sh: cannot resolve cache/log path; skip"
  exit 0
fi

# Resolve Python.
tc_resolve_python_local() {
  if [ -n "${TC_PYTHON_CMD:-}" ]; then printf '%s' "${TC_PYTHON_CMD}"; return 0; fi
  local cand
  for cand in python3 python "py -3" py; do
    if ${cand} -c "import sys; sys.exit(0 if sys.version_info[0]>=3 else 49)" >/dev/null 2>&1; then
      TC_PYTHON_CMD="${cand}"
      printf '%s' "${cand}"
      return 0
    fi
  done
  return 1
}

PY="$(tc_resolve_python_local)" || { tc_log "post-tool-use.sh: python missing; skip"; exit 0; }

# Invoke analyzer: reads file, reads cache, diffs, appends to log, updates cache.
TC_FILE="${ABS_FILE}" \
TC_FTYPE="${FILE_TYPE}" \
TC_CACHE="${CACHE_PATH}" \
TC_LOG="${LOG_PATH}" \
TC_REL_PATH="${FILE_PATH}" \
TC_TOOL="${TOOL_NAME}" \
  ${PY} - <<'PYEOF' 2>/dev/null
"""
PostToolUse audit-log analyzer.

Reads the just-edited file and the prior-state cache, computes
introduced/resolved marks, appends an entry to the project's audit log,
and updates the cache.

Mark detection (v2):
  Markdown: <mark>BODY</mark><sup>N</sup>
    body interpretation (Fix #7 syntax + legacy fallback):
      starts with `<s>OLD</s>NEW` (or legacy `~~OLD~~NEW`)  → replacement
      is exactly  `<s>OLD</s>`    (or legacy `~~OLD~~`)     → deletion
      otherwise                                              → insertion (NEW only)
  LaTeX:    \tc{BODY}\tcn{N}
    body interpretation:
      starts with `\sout{OLD}NEW` → replacement
      is exactly  `\sout{OLD}`    → deletion
      otherwise                   → insertion
"""
import os, re, json, sys, datetime

file_path = os.environ['TC_FILE']
ftype     = os.environ['TC_FTYPE']
cache     = os.environ['TC_CACHE']
log_path  = os.environ['TC_LOG']
rel_path  = os.environ['TC_REL_PATH']
tool_name = os.environ['TC_TOOL']

# Read current file.
try:
    with open(file_path, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
except (IOError, UnicodeDecodeError):
    sys.exit(0)

# Compute project-relative path for log entries.
log_dir = os.path.dirname(log_path)
try:
    rel_for_log = os.path.relpath(file_path, log_dir).replace(os.sep, '/')
except ValueError:
    rel_for_log = file_path

# -- Mark extraction ---------------------------------------------------------
def extract_marks(text, ftype):
    """Return list of dicts: {N, type, line, old, new}.
    line is 1-indexed line where the mark begins."""
    marks = []
    if ftype in ('md', 'qmd'):
        # <mark>...</mark><sup>N</sup>  — multi-line via DOTALL
        pat = re.compile(r'<mark>(.*?)</mark><sup>(\d+)</sup>', re.DOTALL)
        for m in pat.finditer(text):
            body = m.group(1)
            n = m.group(2)
            line_no = 1 + text.count('\n', 0, m.start())
            entry = classify_md(body)
            entry['N'] = n
            entry['line'] = line_no
            marks.append(entry)
    elif ftype == 'tex':
        # \tc{BODY}\tcn{N}  — brace-balanced body
        pos = 0
        L = len(text)
        head = re.compile(r'\\tc\{')
        while pos < L:
            mh = head.search(text, pos)
            if not mh:
                break
            if text[mh.start():mh.start()+5] == '\\tcn{':
                pos = mh.end()
                continue
            body_start = mh.end()
            depth = 1
            i = body_start
            while i < L and depth > 0:
                c = text[i]
                if c == '\\' and i+1 < L:
                    i += 2; continue
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            if depth != 0:
                pos = mh.end()
                continue
            body = text[body_start:i]
            # Check tcn after.
            tail = text[i+1:i+1+30]
            tm = re.match(r'\\tcn\{(\d+)\}', tail)
            if not tm:
                pos = i + 1
                continue
            n = tm.group(1)
            line_no = 1 + text.count('\n', 0, mh.start())
            entry = classify_tex(body)
            entry['N'] = n
            entry['line'] = line_no
            marks.append(entry)
            pos = i + 1 + len(tm.group(0))
    return marks

def classify_md(body):
    # Fix #7 syntax: <s>OLD</s>NEW (replacement) / <s>OLD</s> (deletion).
    # Replacement: <s>OLD</s>NEW  (NEW non-empty)
    m = re.match(r'^<s>(.*?)</s>(.+)$', body, re.DOTALL)
    if m:
        return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    # Deletion: <s>OLD</s>  (nothing after)
    m = re.match(r'^<s>(.*?)</s>\s*$', body, re.DOTALL)
    if m:
        return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    # Legacy fallback (Fix #6 and earlier): ~~OLD~~NEW / ~~OLD~~
    m = re.match(r'^~~(.*?)~~(.+)$', body, re.DOTALL)
    if m:
        return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    m = re.match(r'^~~(.*?)~~\s*$', body, re.DOTALL)
    if m:
        return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    # Insertion: body is the new chars
    return {'type': 'insertion', 'old': '', 'new': body}

def classify_tex(body):
    # Replacement: \sout{OLD}NEW
    m = re.match(r'^\\sout\{(.*?)\}(.+)$', body, re.DOTALL)
    if m:
        return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    # Deletion: \sout{OLD}
    m = re.match(r'^\\sout\{(.*?)\}\s*$', body, re.DOTALL)
    if m:
        return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    return {'type': 'insertion', 'old': '', 'new': body}

current_marks = extract_marks(text, ftype)
current_by_n = {m['N']: m for m in current_marks}

# -- Load prior cache --------------------------------------------------------
prior_by_n = {}
if os.path.exists(cache):
    try:
        with open(cache, 'r', encoding='utf-8') as f:
            prior_data = json.load(f)
        prior_by_n = {m['N']: m for m in prior_data.get('marks', [])}
    except (IOError, ValueError):
        prior_by_n = {}

# -- Diff --------------------------------------------------------------------
introduced = []
resolved = []
for n, m in current_by_n.items():
    if n not in prior_by_n:
        introduced.append(m)
for n, m in prior_by_n.items():
    if n not in current_by_n:
        resolved.append(m)

if not introduced and not resolved:
    # Save current state (in case prior had stale entries) and exit silent.
    try:
        os.makedirs(os.path.dirname(cache), exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump({'file': file_path, 'marks': current_marks}, f)
    except IOError:
        pass
    sys.exit(0)

# -- Resolution inference (best-effort) --------------------------------------
def infer_decision(prior_mark, current_text):
    """Approximate accept/reject inference by substring search."""
    t = prior_mark.get('type', '')
    old = prior_mark.get('old', '')
    new = prior_mark.get('new', '')
    in_text_new = bool(new) and new in current_text
    in_text_old = bool(old) and old in current_text
    if t == 'insertion':
        # accepted = new chars kept; rejected = new chars removed
        return 'accepted' if in_text_new else 'rejected'
    if t == 'deletion':
        # accepted = old chars removed; rejected = old chars restored
        return 'rejected' if in_text_old else 'accepted'
    if t == 'replacement':
        if in_text_new and not in_text_old: return 'accepted'
        if in_text_old and not in_text_new: return 'rejected'
        return 'ambiguous'
    return 'ambiguous'

# -- Format and append log entry ---------------------------------------------
def fmt_str(s):
    """Quote a string for the log entry. Short single-line: use quotes.
    Multi-line or contains quotes: use a YAML-style block scalar (|)."""
    if not s:
        return '""'
    if '\n' in s or '"' in s or len(s) > 200:
        # Block scalar — preserve content via indentation.
        indented = '\n'.join('      ' + ln for ln in s.split('\n'))
        return '|\n' + indented
    return '"' + s.replace('\\', '\\\\') + '"'

ts = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

lines = [f"\n## {ts} -- {rel_for_log}  ({tool_name})"]

if introduced:
    lines.append("introduced:")
    for m in introduced:
        lines.append(f"  - mark: {m['N']}")
        lines.append(f"    type: {m['type']}")
        lines.append(f"    line: {m['line']}")
        if m['type'] in ('deletion', 'replacement'):
            lines.append(f"    old: {fmt_str(m.get('old', ''))}")
        if m['type'] in ('insertion', 'replacement'):
            lines.append(f"    new: {fmt_str(m.get('new', ''))}")

if resolved:
    lines.append("resolved:")
    for m in resolved:
        decision = infer_decision(m, text)
        lines.append(f"  - mark: {m['N']}")
        lines.append(f"    was_type: {m.get('type', '?')}")
        lines.append(f"    decision: {decision}")
        if m.get('old', ''):
            lines.append(f"    was_old: {fmt_str(m['old'])}")
        if m.get('new', ''):
            lines.append(f"    was_new: {fmt_str(m['new'])}")

entry = '\n'.join(lines) + '\n'

# Append to log. Create log file with a header if it doesn't exist.
try:
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    if not os.path.exists(log_path):
        header = (
            "# track-changes history\n"
            "#\n"
            "# Append-only audit log of AI-introduced and AI-introduced-then-resolved\n"
            "# marks for tracked files in this project. Each entry records one\n"
            "# Write/Edit/MultiEdit. Diffable + greppable + git-committed.\n"
            "#\n"
            "# Generated and maintained by the track-changes skill PostToolUse hook.\n"
            "# Do not edit by hand (append-only). To reset: delete this file.\n"
        )
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(header)
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(entry)
except IOError:
    pass

# Update cache.
try:
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open(cache, 'w', encoding='utf-8') as f:
        json.dump({'file': file_path, 'marks': current_marks}, f)
except IOError:
    pass
PYEOF

exit 0
