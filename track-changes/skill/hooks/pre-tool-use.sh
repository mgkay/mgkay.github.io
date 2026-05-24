#!/usr/bin/env bash
# pre-tool-use.sh — track-changes PreToolUse hook (v2)
#
# Event:   PreToolUse on Write / Edit / MultiEdit
# Purpose: When tracking is active for the target file (see SKILL.md §2),
#          compare proposed content against on-disk source and block the
#          write if any differing content lacks a properly-formed v2
#          highlight wrapper:
#            Markdown: <mark>...</mark><sup>N</sup>
#            LaTeX:    \tc{...}\tcn{N}
#          Inside non-rendering constructs the wrapper takes the
#          sibling-element form on one or more lines immediately above
#          the block opener (each individual change inside the block
#          gets its own sibling).
#
#          Default is OFF — the hook is silent unless one of the
#          activation mechanisms in SKILL.md §2 is in effect:
#            (1) /draft sentinel (suspends for current turn)
#            (2) /track-on or /track-off session sentinel
#            (3) per-file YAML frontmatter `track-changes: true|false`
#                (or `% track-changes: ...` magic comment for .tex)
#            (4) ancestor `.tc-tracked` marker file (walk-up discovery)
#
# Stdin:   Hook event JSON payload from Claude Code.
# Stderr:  On block: a multi-line structured error citing line numbers
#          and rule violated.
# Exit:    0  — allow (no-op, off-scope, draft, off-session, off-file,
#                       off-default, or no violations)
#          2  — block

set -u

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=../lib/tc-common.sh
if ! source "${SCRIPT_DIR}/../lib/tc-common.sh" 2>/dev/null; then
  exit 0
fi

TC_TMP_DIR=""
cleanup_tmp() {
  if [ -n "${TC_TMP_DIR}" ] && [ -d "${TC_TMP_DIR}" ]; then
    rm -rf "${TC_TMP_DIR}" 2>/dev/null || true
  fi
}
trap cleanup_tmp EXIT

_state_dir="$(tc_state_dir 2>/dev/null || true)"
if [ -n "${_state_dir}" ] && [ -d "${_state_dir}" ]; then
  TC_TMP_DIR="$(mktemp -d "${_state_dir}/ptu-XXXXXX" 2>/dev/null || true)"
fi
if [ -z "${TC_TMP_DIR}" ]; then
  TC_TMP_DIR="$(mktemp -d 2>/dev/null || true)"
fi
if [ -z "${TC_TMP_DIR}" ]; then
  tc_log "pre-tool-use.sh: cannot create temp dir; failing open"
  exit 0
fi

# ---------------------------------------------------------------------------
# Read payload
# ---------------------------------------------------------------------------
PAYLOAD=""
if [ ! -t 0 ]; then
  PAYLOAD="$(cat 2>/dev/null || true)"
fi
if [ -z "${PAYLOAD}" ]; then
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  tc_log "pre-tool-use.sh: jq not available; failing open"
  exit 0
fi

# Fix #9: extract tool_name + file_path in ONE jq call (was two separate
# invocations; cuts ~50ms of jq startup per hook on Windows).
_JQ_OUT="$(printf '%s' "${PAYLOAD}" | jq -r '[.tool_name // "", .tool_input.file_path // ""] | @tsv' 2>/dev/null || true)"
TOOL_NAME="${_JQ_OUT%%	*}"
FILE_PATH="${_JQ_OUT#*	}"
if [ -z "${TOOL_NAME}" ]; then
  exit 0
fi

case "${TOOL_NAME}" in
  Write|Edit|MultiEdit) ;;
  *) exit 0 ;;
esac

if [ -z "${FILE_PATH}" ]; then
  exit 0
fi

FILE_TYPE="$(tc_file_type "${FILE_PATH}")"
case "${FILE_TYPE}" in
  md|qmd|tex) ;;
  *) exit 0 ;;
esac

# Drafting a new file (no on-disk source) is unambiguous — pass through.
if [ ! -f "${FILE_PATH}" ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Activation gate (v2). The unified tc_should_track resolver checks
# /draft, /track-on / /track-off, per-file YAML/magic-comment, and the
# .tc-tracked walk-up. Returns 0 if tracking should be enforced, non-zero
# otherwise. The echoed reason is logged for diagnostics.
# ---------------------------------------------------------------------------
ACTIVATION_REASON="$(tc_should_track "${FILE_PATH}" 2>/dev/null || printf 'off-default')"
case "${ACTIVATION_REASON}" in
  on-*)
    tc_log "pre-tool-use.sh: ACTIVE (${ACTIVATION_REASON}) for ${FILE_PATH}"
    ;;
  *)
    tc_log "pre-tool-use.sh: skip (${ACTIVATION_REASON}) for ${FILE_PATH}"
    exit 0
    ;;
esac

# ---------------------------------------------------------------------------
# Subagent-context detection (best-effort) — drives a hint in the block
# message suggesting /draft if the user delegated to a Builder.
# ---------------------------------------------------------------------------
SUBAGENT_DETECTED=0
if printf '%s' "${PAYLOAD}" | grep -qE '"(subagent|sub_agent|subagent_id|subagent_type|agent_id|agent_type|is_subagent|delegated_from|parent_session_id|parent_agent|spawned_by)"' 2>/dev/null; then
  SUBAGENT_DETECTED=1
fi

# ---------------------------------------------------------------------------
# Materialize source and proposed content with CRLF normalization.
# ---------------------------------------------------------------------------
SOURCE_FILE="${TC_TMP_DIR}/source"
PROPOSED_FILE="${TC_TMP_DIR}/proposed"

if ! tc_normalize_eol "${FILE_PATH}" > "${SOURCE_FILE}" 2>/dev/null; then
  tc_log "pre-tool-use.sh: cannot read source ${FILE_PATH}; failing open"
  exit 0
fi

tc_resolve_python() {
  if [ -n "${TC_PYTHON_CMD:-}" ]; then
    printf '%s' "${TC_PYTHON_CMD}"
    return 0
  fi
  local cand
  for cand in python3 python "py -3" py; do
    if ${cand} -c "import sys; sys.exit(0 if sys.version_info[0] >= 3 else 49)" >/dev/null 2>&1; then
      TC_PYTHON_CMD="${cand}"
      printf '%s' "${cand}"
      return 0
    fi
  done
  return 1
}

# ---------------------------------------------------------------------------
# Fix #9: single Python invocation does build + diff + analyze (was three
# separate steps: build_proposed Python, bash diff, analyzer Python). Write
# the payload to a file the Python can read.
# ---------------------------------------------------------------------------
PAYLOAD_FILE="${TC_TMP_DIR}/payload.json"
printf '%s' "${PAYLOAD}" > "${PAYLOAD_FILE}" 2>/dev/null

VIOLATIONS_FILE="${TC_TMP_DIR}/violations"
SUGGEST_DRAFT_FILE="${TC_TMP_DIR}/suggest_draft"
PROPOSED_FILE="${TC_TMP_DIR}/proposed"

PY="$(tc_resolve_python)" || {
  tc_log "pre-tool-use.sh: python missing; failing open"
  exit 0
}

TC_PAYLOAD_FILE="${PAYLOAD_FILE}" \
TC_TOOL_NAME="${TOOL_NAME}" \
TC_PROPOSED="${PROPOSED_FILE}" \
TC_SOURCE="${SOURCE_FILE}" \
TC_FILETYPE="${FILE_TYPE}" \
TC_VIOL_OUT="${VIOLATIONS_FILE}" \
TC_SUGGEST_OUT="${SUGGEST_DRAFT_FILE}" \
  ${PY} - <<'PYEOF' 2>/dev/null
"""
track-changes PreToolUse analyzer (v2 + Fix #8 resolution pre-pass + Fix #9
single-Python consolidation).

Reads the payload + source, builds the proposed content in memory, diffs
source vs proposed using difflib, and runs the existing analyzer
(structural + coverage + resolution pre-pass + uniqueness). Replaces the
prior pipeline of two separate Python invocations plus an external `diff`
command — eliminates one interpreter startup per Edit/MultiEdit.

Validates that any diff region in the proposed file is covered by a v2
mark+sup wrapper or a sibling-form mark above a non-rendering region.

v2 syntax:
  Markdown: <mark>...</mark><sup>N</sup>
  LaTeX:    \tc{...}\tcn{N}
"""
import os, re, sys, json, difflib

payload_path  = os.environ['TC_PAYLOAD_FILE']
tool_name     = os.environ['TC_TOOL_NAME']
source_path   = os.environ['TC_SOURCE']
proposed_path = os.environ['TC_PROPOSED']
ftype         = os.environ['TC_FILETYPE']    # 'md' | 'qmd' | 'tex'
viol_path     = os.environ['TC_VIOL_OUT']
suggest_path  = os.environ['TC_SUGGEST_OUT']

violations = []
suggest_draft = False

def add_violation(line_no, reason):
    violations.append((line_no, reason))

# ---------------------------------------------------------------------------
# Build proposed content from payload + source. Mirrors what the separate
# python_apply_edit / python_apply_multiedit / jq-extract used to do.
# ---------------------------------------------------------------------------
with open(source_path, 'r', encoding='utf-8', newline='') as f:
    source_text = f.read()

try:
    with open(payload_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)
except (IOError, ValueError):
    # Cannot build proposed; write empty violations and exit cleanly.
    with open(viol_path, 'w', encoding='utf-8') as f:
        pass
    with open(suggest_path, 'w', encoding='utf-8') as f:
        f.write('0\n')
    sys.exit(0)

ti = (payload or {}).get('tool_input') or {}

if tool_name == 'Write':
    proposed_text = ti.get('content', '') or ''
elif tool_name == 'Edit':
    old = (ti.get('old_string', '') or '').replace('\r\n', '\n')
    new = (ti.get('new_string', '') or '').replace('\r\n', '\n')
    proposed_text = source_text.replace('\r\n', '\n')
    if old and old in proposed_text:
        proposed_text = proposed_text.replace(old, new, 1)
elif tool_name == 'MultiEdit':
    proposed_text = source_text.replace('\r\n', '\n')
    for ed in (ti.get('edits') or []):
        if not isinstance(ed, dict):
            continue
        old = (ed.get('old_string', '') or '').replace('\r\n', '\n')
        new = (ed.get('new_string', '') or '').replace('\r\n', '\n')
        if not old:
            continue
        if ed.get('replace_all'):
            proposed_text = proposed_text.replace(old, new)
        elif old in proposed_text:
            proposed_text = proposed_text.replace(old, new, 1)
else:
    # Unsupported tool — exit cleanly without violations.
    with open(viol_path, 'w', encoding='utf-8') as f:
        pass
    with open(suggest_path, 'w', encoding='utf-8') as f:
        f.write('0\n')
    sys.exit(0)

# Normalize CRLF (source was raw from disk; payload values were CRLF-normalized above).
source_text = source_text.replace('\r\n', '\n')
proposed_text = proposed_text.replace('\r\n', '\n')

# Persist proposed to TC_PROPOSED for tests / debugging / external tooling.
with open(proposed_path, 'w', encoding='utf-8', newline='') as f:
    f.write(proposed_text)

# ---------------------------------------------------------------------------
# Diff source vs proposed. If no diff, write empty violations and exit.
# ---------------------------------------------------------------------------
if source_text == proposed_text:
    with open(viol_path, 'w', encoding='utf-8') as f:
        pass
    with open(suggest_path, 'w', encoding='utf-8') as f:
        f.write('0\n')
    sys.exit(0)

# Produce unified diff text the existing parser can consume.
_src_lines = source_text.split('\n')
_prp_lines = proposed_text.split('\n')
_src_for_diff = [l + '\n' for l in _src_lines]
_prp_for_diff = [l + '\n' for l in _prp_lines]
diff_text = ''.join(difflib.unified_diff(_src_for_diff, _prp_for_diff,
                                          fromfile='source', tofile='proposed',
                                          n=3))

proposed_lines = proposed_text.split('\n')
n_lines = len(proposed_lines)

# ---------------------------------------------------------------------------
# Fix #8: Resolution pre-pass.
#
# Extract marks from source and proposed; walk both in parallel. If every
# byte is accounted for by one of:
#   - preserved mark (same N, identical body) on both sides
#   - resolved source mark whose chars at the proposed position match either
#     its `new` (accept) or `old` (reject) text
#   - introduced mark in proposed (new N) — consumed in proposed only
#   - identical plain-text segment
# then the edit is a pure resolution. The line-level coverage check below
# is then skipped (resolutions don't need a wrapping mark on the result line).
# ---------------------------------------------------------------------------

def _md_classify(body):
    m = re.match(r'^<s>(.*?)</s>(.+)$', body, re.DOTALL)
    if m: return ('replacement', m.group(1), m.group(2))
    m = re.match(r'^<s>(.*?)</s>\s*$', body, re.DOTALL)
    if m: return ('deletion', m.group(1), '')
    m = re.match(r'^~~(.*?)~~(.+)$', body, re.DOTALL)
    if m: return ('replacement', m.group(1), m.group(2))
    m = re.match(r'^~~(.*?)~~\s*$', body, re.DOTALL)
    if m: return ('deletion', m.group(1), '')
    return ('insertion', '', body)

def _tex_classify(body):
    m = re.match(r'^\\sout\{(.*?)\}(.+)$', body, re.DOTALL)
    if m: return ('replacement', m.group(1), m.group(2))
    m = re.match(r'^\\sout\{(.*?)\}\s*$', body, re.DOTALL)
    if m: return ('deletion', m.group(1), '')
    return ('insertion', '', body)

def _md_extract_marks(text):
    # Fix #10: mask backtick spans and fenced code blocks before extracting
    # marks. Documentation tokens like `<mark>example</mark><sup>3</sup>`
    # inside backticks or fenced code blocks must not be picked up as real
    # marks, and a nested `<mark>...</mark>` inside backticks would otherwise
    # confuse the non-greedy regex into matching the inner closer rather
    # than the outer.
    lines = text.split('\n')
    line_starts = [0]
    for ln in lines:
        line_starts.append(line_starts[-1] + len(ln) + 1)
    masked = list(text)
    def _mask_range(s, e):
        end = min(e, len(masked))
        for k in range(s, end):
            if masked[k] != '\n':
                masked[k] = ' '
    # Inline backtick spans.
    for idx, line in enumerate(lines):
        line_off = line_starts[idx]
        j = 0
        L = len(line)
        while j < L:
            if line[j] == '`':
                close = line.find('`', j + 1)
                if close == -1:
                    break
                _mask_range(line_off + j, line_off + close + 1)
                j = close + 1
            else:
                j += 1
    # Fenced code blocks.
    fence_re = re.compile(r'^\s{0,3}(```|~~~)([^`~].*)?$')
    nL = len(lines)
    i = 0
    while i < nL:
        mo = fence_re.match(lines[i])
        if mo:
            fc = mo.group(1)
            close_re = re.compile(r'^\s{0,3}' + re.escape(fc) + r'\s*$')
            j = i + 1
            while j < nL:
                if close_re.match(lines[j]):
                    end_off = line_starts[j + 1] if j + 1 < len(line_starts) else len(text)
                    _mask_range(line_starts[i], end_off)
                    i = j + 1
                    break
                j += 1
            else:
                _mask_range(line_starts[i], len(text))
                i = nL
            continue
        i += 1
    masked_text = ''.join(masked)
    marks = []
    pat = re.compile(r'<mark>(.*?)</mark><sup>(\d+)</sup>', re.DOTALL)
    for m in pat.finditer(masked_text):
        # Re-extract the body from the ORIGINAL text using the same span.
        # </mark><sup>N</sup> trails the body; total trailing length = 18 + len(N).
        n_val = m.group(2)
        body_start = m.start() + 6  # len('<mark>')
        body_end = m.end() - 18 - len(n_val)
        orig_body = text[body_start:body_end]
        t, old, new = _md_classify(orig_body)
        marks.append({'N': n_val, 'start': m.start(), 'end': m.end(),
                      'body': orig_body, 'type': t, 'old': old, 'new': new})
    return marks

def _tex_extract_marks(text):
    marks = []
    L = len(text)
    pos = 0
    head = re.compile(r'\\tc\{')
    while pos < L:
        mh = head.search(text, pos)
        if not mh:
            break
        if text[mh.start():mh.start()+5] == '\\tcn{':
            pos = mh.end(); continue
        body_start = mh.end()
        depth = 1
        i = body_start
        while i < L and depth > 0:
            c = text[i]
            if c == '\\' and i + 1 < L:
                i += 2; continue
            if c == '{': depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0: break
            i += 1
        if depth != 0:
            pos = mh.end(); continue
        body = text[body_start:i]
        tail_start = i + 1
        tm = re.match(r'\\tcn\{(\d+)\}', text[tail_start:tail_start+30])
        if not tm:
            pos = tail_start; continue
        t, old, new = _tex_classify(body)
        marks.append({'N': tm.group(1), 'start': mh.start(),
                      'end': tail_start + len(tm.group(0)),
                      'body': body, 'type': t, 'old': old, 'new': new})
        pos = tail_start + len(tm.group(0))
    return marks

def _detect_regions(text, ftype):
    """Return list of (body_start, body_end, opener_line_idx, kind) for
    non-rendering regions in `text`. body_start is the char offset of the
    FIRST char inside the region; body_end is one past the LAST body char.
    opener_line_idx is the 0-indexed line of the *outermost* opener for
    sibling-detection purposes (e.g., for a GFM table the header row, not
    the separator). The sibling mark, if any, sits on opener_line_idx - 1.
    Kind is 'fenced-code', 'display-math', 'gfm-table', 'yaml-frontmatter',
    or 'latex-<env>'.
    """
    regions = []
    lines = text.split('\n')
    n = len(lines)
    line_starts = [0]
    for ln in lines:
        line_starts.append(line_starts[-1] + len(ln) + 1)
    def L(ln_idx):
        return line_starts[ln_idx]
    if ftype in ('md', 'qmd'):
        fence_re = re.compile(r'^\s{0,3}(```|~~~)([^`~].*)?$')
        i = 0
        while i < n:
            mo = fence_re.match(lines[i])
            if mo:
                fc = mo.group(1)
                close_re = re.compile(r'^\s{0,3}' + re.escape(fc) + r'\s*$')
                opener_line = i
                j = i + 1
                while j < n:
                    if close_re.match(lines[j]):
                        regions.append((L(i + 1), L(j), opener_line, 'fenced-code'))
                        i = j + 1
                        break
                    j += 1
                else:
                    regions.append((L(i + 1), len(text), opener_line, 'fenced-code'))
                    i = n
                continue
            i += 1
        i = 0
        while i < n:
            if re.match(r'^\s*\$\$\s*$', lines[i]):
                opener_line = i
                j = i + 1
                while j < n:
                    if re.match(r'^\s*\$\$\s*$', lines[j]):
                        regions.append((L(i + 1), L(j), opener_line, 'display-math'))
                        i = j + 1
                        break
                    j += 1
                else:
                    regions.append((L(i + 1), len(text), opener_line, 'display-math'))
                    i = n
                continue
            i += 1
        # YAML front matter: opening `---` (typically line 0, but may be
        # preceded by a sibling mark line in proposed). Find the first `---`
        # delimiter, then the matching closer.
        for i in range(min(n, 8)):
            if re.match(r'^---\s*$', lines[i]):
                opener_line = i
                j = i + 1
                while j < n:
                    if re.match(r'^---\s*$', lines[j]):
                        regions.append((L(i + 1), L(j), opener_line, 'yaml-frontmatter'))
                        break
                    j += 1
                break
            if lines[i].strip() == '':
                continue
            if re.search(r'<mark>.*?</mark><sup>\d+</sup>', lines[i]):
                # Tolerated above YAML opener.
                continue
            break
        # GFM tables. The "opener" for sibling purposes is the HEADER row,
        # not the separator (sibling sits above the header).
        sep_re = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$')
        pipe_re = re.compile(r'^\s*\|.*\|\s*$')
        i = 0
        while i < n:
            if sep_re.match(lines[i]) and i > 0 and pipe_re.match(lines[i - 1]):
                opener_line = i - 1  # header row
                k = i + 1
                while k < n and pipe_re.match(lines[k]):
                    k += 1
                # Body = data rows (i+1 .. k). Skipping the header+separator
                # for "differ-allowed" purposes is right: the header and
                # separator usually stay structural; only data rows change.
                regions.append((L(i + 1), L(k), opener_line, 'gfm-table'))
                i = k
                continue
            i += 1
    elif ftype == 'tex':
        envs = ['verbatim', 'lstlisting', 'minted', 'equation', 'equation*',
                'align', 'align*', 'gather', 'gather*', 'multline', 'multline*',
                'tabular']
        begin_re = re.compile(r'\\begin\{(' + '|'.join(re.escape(e) for e in envs) + r')\}')
        end_re = re.compile(r'\\end\{(' + '|'.join(re.escape(e) for e in envs) + r')\}')
        i = 0
        while i < n:
            mb = begin_re.search(lines[i])
            if mb:
                kind = mb.group(1)
                opener_line = i
                j = i + 1
                while j < n:
                    me = end_re.search(lines[j])
                    if me and me.group(1) == kind:
                        regions.append((L(i + 1), L(j), opener_line, 'latex-' + kind))
                        i = j + 1
                        break
                    j += 1
                else:
                    regions.append((L(i + 1), len(text), opener_line, 'latex-' + kind))
                    i = n
                continue
            i += 1
    regions.sort()
    return regions

def _region_has_sibling(text, opener_line_idx, ftype):
    """Sibling mark sits on the line immediately above `opener_line_idx`."""
    if opener_line_idx <= 0:
        return False
    lines = text.split('\n')
    sib_idx = opener_line_idx - 1
    if sib_idx >= len(lines):
        return False
    sib_line = lines[sib_idx]
    if ftype in ('md', 'qmd'):
        return bool(re.search(r'<mark>.*?</mark><sup>\d+</sup>', sib_line))
    elif ftype == 'tex':
        return bool(re.search(r'\\tc\{[^}]*\}\\tcn\{\d+\}', sib_line))
    return False

def _check_pure_resolution(src_text, prop_text, ftype):
    if ftype in ('md', 'qmd'):
        s_marks = _md_extract_marks(src_text)
        p_marks = _md_extract_marks(prop_text)
    elif ftype == 'tex':
        s_marks = _tex_extract_marks(src_text)
        p_marks = _tex_extract_marks(prop_text)
    else:
        return False
    s_n_set = {m['N'] for m in s_marks}
    p_n_set = {m['N'] for m in p_marks}

    # Fix #10: detect non-rendering regions and pair sibling-marked proposed
    # regions with their source counterparts. The walk uses these pairs to
    # allow region bodies to legitimately differ between source and proposed.
    s_regions = _detect_regions(src_text, ftype)
    p_regions = _detect_regions(prop_text, ftype)
    # Regions are (body_start, body_end, opener_line_idx, kind).
    # Pair by (kind, ordinal): Nth source region of a kind pairs with Nth
    # proposed region of the same kind.
    s_by_kind = {}
    p_by_kind = {}
    for r in s_regions:
        s_by_kind.setdefault(r[3], []).append(r)
    for r in p_regions:
        p_by_kind.setdefault(r[3], []).append(r)
    region_pairs = []  # list of (s_start, s_end, p_start, p_end)
    for kind, p_list in p_by_kind.items():
        s_list = s_by_kind.get(kind, [])
        for idx, p_r in enumerate(p_list):
            if not _region_has_sibling(prop_text, p_r[2], ftype):
                continue
            if idx < len(s_list):
                s_r = s_list[idx]
                region_pairs.append((s_r[0], s_r[1], p_r[0], p_r[1]))
    region_pairs.sort()

    s_pos = p_pos = 0
    s_idx = p_idx = 0
    s_len = len(src_text)
    p_len = len(prop_text)
    while s_pos < s_len or p_pos < p_len:
        # Fix #10: at start of iteration, if (s_pos, p_pos) sits exactly at
        # a paired sibling-marked region body start, jump past both regions.
        skipped_pair = False
        for (ss, se, ps, pe) in region_pairs:
            if s_pos == ss and p_pos == ps:
                s_pos = se; p_pos = pe
                skipped_pair = True
                break
        if skipped_pair:
            continue

        s_m = s_marks[s_idx] if s_idx < len(s_marks) else None
        p_m = p_marks[p_idx] if p_idx < len(p_marks) else None
        s_next = s_m['start'] if s_m else s_len
        p_next = p_m['start'] if p_m else p_len
        at_s = s_m is not None and s_pos == s_next
        at_p = p_m is not None and p_pos == p_next
        if at_s and at_p and s_m['N'] == p_m['N']:
            if s_m['body'] != p_m['body']:
                return False
            s_pos = s_m['end']; p_pos = p_m['end']
            s_idx += 1; p_idx += 1
            continue
        if at_s and s_m['N'] not in p_n_set:
            new_chars = s_m['new']; old_chars = s_m['old']
            if prop_text[p_pos:p_pos + len(new_chars)] == new_chars:
                p_pos += len(new_chars)
            elif prop_text[p_pos:p_pos + len(old_chars)] == old_chars:
                p_pos += len(old_chars)
            else:
                return False
            s_pos = s_m['end']; s_idx += 1
            continue
        if at_p and p_m['N'] not in s_n_set:
            mark_start = p_m['start']
            mark_end = p_m['end']
            mark_type = p_m['type']
            # Fix #10: introduced marks can claim a replacement or deletion
            # of source content (body starts with <s>OLD</s>). When they do,
            # consume the `old` chars from source as well — the mark IS the
            # replacement event happening in this edit.
            consumed_old = False
            if mark_type == 'replacement' or mark_type == 'deletion':
                old_chars = p_m['old']
                if old_chars and src_text[s_pos:s_pos + len(old_chars)] == old_chars:
                    s_pos += len(old_chars)
                    consumed_old = True
            p_pos = mark_end
            # If this introduced mark sits alone on its own new line
            # (preceded by '\n' or BOF, followed by '\n'), consume the
            # trailing newline — the whole "sibling line" is new content.
            sibling_line = (p_pos < p_len and prop_text[p_pos] == '\n'
                            and (mark_start == 0 or prop_text[mark_start - 1] == '\n'))
            if sibling_line:
                p_pos += 1
                # For a replacement/deletion sibling-line, the mark replaces
                # the entire source line including its trailing newline —
                # consume source's '\n' too if it's still at s_pos.
                if consumed_old and s_pos < s_len and src_text[s_pos] == '\n':
                    s_pos += 1
                # Greedy-consume any additional proposed '\n's that aren't
                # mirrored in source (paragraph-break whitespace around the
                # introduced sibling line).
                while p_pos < p_len and prop_text[p_pos] == '\n' \
                        and not (s_pos < s_len and src_text[s_pos] == '\n'):
                    p_pos += 1
            p_idx += 1
            continue
        # Plain-text segment: advance by the SHORTER of the two chunk
        # lengths and compare. The side that hit its event first will be
        # handled in the next iteration; the other side still has plain
        # text remaining before its own next event.
        s_chunk_len = s_next - s_pos
        p_chunk_len = p_next - p_pos
        if s_chunk_len <= 0 and p_chunk_len <= 0:
            return False
        chunk_len = s_chunk_len if s_chunk_len < p_chunk_len else p_chunk_len
        if chunk_len <= 0:
            # Fix #10: when source has nothing left to compare but proposed
            # still has pure whitespace before an introduced sibling-line
            # mark (typical "blank line then new paragraph" AI pattern),
            # allow consuming that whitespace. Symmetric for the inverse.
            if s_chunk_len == 0 and p_chunk_len > 0 and p_m is not None and p_m['N'] not in s_n_set:
                p_seg = prop_text[p_pos:p_next]
                if p_seg.strip() == '':
                    preceded_nl = (p_m['start'] == 0 or prop_text[p_m['start'] - 1] == '\n')
                    followed_nl = (p_m['end'] < p_len and prop_text[p_m['end']] == '\n')
                    if preceded_nl and followed_nl:
                        p_pos = p_next
                        continue
            if p_chunk_len == 0 and s_chunk_len > 0 and s_m is not None and s_m['N'] not in p_n_set:
                # Inverse: source has pure whitespace before a resolved
                # source mark (mark removed; sibling-line whitespace too).
                s_seg = src_text[s_pos:s_next]
                if s_seg.strip() == '':
                    s_preceded_nl = (s_m['start'] == 0 or src_text[s_m['start'] - 1] == '\n')
                    s_followed_nl = (s_m['end'] < s_len and src_text[s_m['end']] == '\n')
                    if s_preceded_nl and s_followed_nl:
                        s_pos = s_next
                        continue
            return False
        # Fix #10: clip chunk_len so we don't stride past the next paired
        # region start on either side. Stopping exactly at the boundary lets
        # the next iteration take the skip-pair branch above.
        for (ss, se, ps, pe) in region_pairs:
            if s_pos < ss and ss <= s_pos + chunk_len:
                chunk_len = min(chunk_len, ss - s_pos)
            if p_pos < ps and ps <= p_pos + chunk_len:
                chunk_len = min(chunk_len, ps - p_pos)
        if chunk_len <= 0:
            return False
        if src_text[s_pos:s_pos + chunk_len] != prop_text[p_pos:p_pos + chunk_len]:
            return False
        s_pos += chunk_len
        p_pos += chunk_len
    return s_pos == s_len and p_pos == p_len

is_pure_resolution = False
try:
    is_pure_resolution = _check_pure_resolution(source_text, proposed_text, ftype)
except Exception:
    is_pure_resolution = False

# ---------------------------------------------------------------------------
# Parse the unified diff: collect 1-indexed line numbers in PROPOSED where
# '+' lines appear.
# ---------------------------------------------------------------------------
added_line_nums = []
diff_lines = diff_text.split('\n')

hunk_re = re.compile(r'^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@')
in_hunk = False
new_cursor = 0
for dl in diff_lines:
    if dl.startswith('@@'):
        m = hunk_re.match(dl)
        if m:
            new_cursor = int(m.group(1))
            in_hunk = True
        else:
            in_hunk = False
        continue
    if not in_hunk:
        continue
    if dl.startswith('\\'):
        continue
    if not dl:
        continue
    tag = dl[0]
    if tag == '+':
        added_line_nums.append(new_cursor)
        new_cursor += 1
    elif tag == '-':
        pass
    elif tag == ' ':
        new_cursor += 1

has_minus_only = False
if not added_line_nums:
    for dl in diff_lines:
        if dl.startswith('-') and not dl.startswith('---'):
            has_minus_only = True
            break

# ---------------------------------------------------------------------------
# Non-rendering region detection (same construct list as v1).
# ---------------------------------------------------------------------------
regions = []
def add_region(body_start, body_end, opener, kind):
    if body_end >= body_start:
        regions.append((body_start, body_end, opener, kind))

# v2 sibling-form pre-regex (used by YAML detector tolerance).
# `.*?` (non-greedy) instead of `[^<]*` so the regex matches marks whose
# body contains `<s>...</s>` strikethrough tags (Fix #7).
md_sibling_pre_re = re.compile(r'^\s*<mark>.*?</mark><sup>\d+</sup>\s*$')

if ftype in ('md', 'qmd'):
    fence_open_re = re.compile(r'^\s{0,3}(```|~~~)([^`~].*)?$')
    i = 0
    while i < n_lines:
        line = proposed_lines[i]
        mo = fence_open_re.match(line)
        if mo:
            opener = i + 1
            fence_char = mo.group(1)
            j = i + 1
            while j < n_lines:
                if re.match(r'^\s{0,3}' + re.escape(fence_char) + r'\s*$', proposed_lines[j]):
                    closer = j + 1
                    add_region(opener + 1, closer - 1, opener, 'fenced-code')
                    i = j + 1
                    break
                j += 1
            else:
                add_region(opener + 1, n_lines, opener, 'fenced-code')
                i = n_lines
            continue
        i += 1

    # Display math $$
    i = 0
    while i < n_lines:
        if re.match(r'^\s*\$\$\s*$', proposed_lines[i]):
            opener = i + 1
            j = i + 1
            while j < n_lines:
                if re.match(r'^\s*\$\$\s*$', proposed_lines[j]):
                    add_region(opener + 1, j, opener, 'display-math')
                    i = j + 1
                    break
                j += 1
            else:
                add_region(opener + 1, n_lines, opener, 'display-math')
                i = n_lines
            continue
        i += 1

    # YAML front matter (tolerates blank / sibling-form lines above opener).
    yaml_opener_idx = -1
    for k in range(min(n_lines, 8)):
        s = proposed_lines[k]
        if re.match(r'^---\s*$', s):
            yaml_opener_idx = k
            break
        if s.strip() == '':
            continue
        if md_sibling_pre_re.match(s):
            continue
        break
    if yaml_opener_idx >= 0:
        opener = yaml_opener_idx + 1
        j = yaml_opener_idx + 1
        while j < n_lines:
            if re.match(r'^---\s*$', proposed_lines[j]):
                add_region(opener + 1, j, opener, 'yaml-frontmatter')
                break
            j += 1

    # GFM tables
    sep_re = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$')
    pipe_row_re = re.compile(r'^\s*\|.*\|\s*$')
    i = 0
    while i < n_lines:
        if sep_re.match(proposed_lines[i]) and i > 0 and pipe_row_re.match(proposed_lines[i - 1]):
            header_line_idx = i - 1
            opener = header_line_idx + 1
            k = i + 1
            while k < n_lines and pipe_row_re.match(proposed_lines[k]):
                k += 1
            add_region(header_line_idx + 2, k, opener, 'gfm-table')
            i = k
            continue
        i += 1

    # Quarto fenced divs (off-enumerated → suggest /draft)
    qfd_open_re = re.compile(r'^\s*:::+\s*\S.*$')
    qfd_close_re = re.compile(r'^\s*:::+\s*$')
    i = 0
    while i < n_lines:
        if qfd_open_re.match(proposed_lines[i]):
            opener = i + 1
            j = i + 1
            while j < n_lines:
                if qfd_close_re.match(proposed_lines[j]):
                    add_region(opener + 1, j, opener, 'quarto-div')
                    i = j + 1
                    break
                j += 1
            else:
                add_region(opener + 1, n_lines, opener, 'quarto-div')
                i = n_lines
            continue
        i += 1

elif ftype == 'tex':
    env_names = [
        'verbatim', 'lstlisting', 'minted',
        'equation', 'equation*',
        'align', 'align*',
        'gather', 'gather*',
        'multline', 'multline*',
        'tabular',
    ]
    begin_re = re.compile(
        r'\\begin\{(' + '|'.join(re.escape(e) for e in env_names) + r')\}'
    )
    end_re = re.compile(
        r'\\end\{(' + '|'.join(re.escape(e) for e in env_names) + r')\}'
    )
    i = 0
    while i < n_lines:
        mb = begin_re.search(proposed_lines[i])
        if mb:
            kind = mb.group(1)
            opener = i + 1
            j = i + 1
            while j < n_lines:
                me = end_re.search(proposed_lines[j])
                if me and me.group(1) == kind:
                    add_region(opener + 1, j, opener, 'latex-' + kind)
                    i = j + 1
                    break
                j += 1
            else:
                add_region(opener + 1, n_lines, opener, 'latex-' + kind)
                i = n_lines
            continue
        i += 1

    # \[ \] display math
    i = 0
    while i < n_lines:
        if re.search(r'\\\[', proposed_lines[i]):
            opener = i + 1
            if re.search(r'\\\]', proposed_lines[i]):
                i += 1
                continue
            j = i + 1
            while j < n_lines:
                if re.search(r'\\\]', proposed_lines[j]):
                    add_region(opener + 1, j, opener, 'tex-display-math')
                    i = j + 1
                    break
                j += 1
            else:
                add_region(opener + 1, n_lines, opener, 'tex-display-math')
                i = n_lines
            continue
        i += 1

    # $$ ... $$
    i = 0
    while i < n_lines:
        if re.match(r'^\s*\$\$\s*$', proposed_lines[i]):
            opener = i + 1
            j = i + 1
            while j < n_lines:
                if re.match(r'^\s*\$\$\s*$', proposed_lines[j]):
                    add_region(opener + 1, j, opener, 'tex-display-math')
                    i = j + 1
                    break
                j += 1
            else:
                add_region(opener + 1, n_lines, opener, 'tex-display-math')
                i = n_lines
            continue
        i += 1

# ---------------------------------------------------------------------------
# Fix #10: the legacy line-level `covered` set computation was removed.
# Coverage is now decided exclusively by the Fix #8/#10 walk
# (_check_pure_resolution) which traces each diff region individually.
# sup_after_close_re remains in scope for the structural well-formedness
# check below.
# ---------------------------------------------------------------------------
sup_after_close_re = re.compile(r'\A<sup>\d+</sup>')

# ---------------------------------------------------------------------------
# Sibling-form check for non-rendering regions.
# A region's body has a valid sibling if the line directly above the
# opener (or several stacked lines above) contains a v2 mark+sup
# (markdown) or \tc{...}\tcn{N} (latex).
# ---------------------------------------------------------------------------
md_sibling_re = re.compile(r'<mark>.*?</mark><sup>\d+</sup>')
tex_sibling_re = re.compile(r'\\tc\{[^}]*\}\\tcn\{\d+\}')

def has_sibling(opener_line_1idx):
    if opener_line_1idx <= 1:
        return False
    # Walk upward through consecutive sibling-form lines.
    sib_line = proposed_lines[opener_line_1idx - 2]
    if ftype in ('md', 'qmd'):
        return bool(md_sibling_re.search(sib_line))
    elif ftype == 'tex':
        return bool(tex_sibling_re.search(sib_line))
    return False

def find_region_for_line(ln):
    best = None
    for (bs, be, op, kind) in regions:
        if bs <= ln <= be:
            if best is None or (op > best[2]):
                best = (bs, be, op, kind)
    return best

reported_regions = set()

# Fix #10: the walk is the SOLE coverage check. If the walk failed, every
# added line is either uncovered by a wrapping mark (inline case) or inside
# a non-rendering region missing its sibling mark — both are violations.
#
# For inline lines (region is None), the walk's verdict already established
# coverage failure; we still emit a per-line violation message for clarity.
# For lines inside non-rendering regions, run the has_sibling check —
# missing sibling = violation.
if not is_pure_resolution:
    inline_violation_added = False
    for ln in added_line_nums:
        line_text = proposed_lines[ln - 1] if 1 <= ln <= n_lines else ''
        region = find_region_for_line(ln)
        if region is None:
            if line_text.strip() == '':
                continue
            # Fix #10: walk is the sole coverage check. If walk failed, the
            # edit has at least one diff character not accounted for by a
            # mark wrapper or a resolution — block. We emit one violation
            # message per failing inline line.
            if not inline_violation_added:
                if ftype in ('md', 'qmd'):
                    add_violation(ln, "added content not wrapped in <mark>...</mark><sup>N</sup> highlight (Fix #10: per-region coverage; every diff char must be inside a mark or be a resolution of an existing mark)")
                else:
                    add_violation(ln, "added content not wrapped in \\tc{...}\\tcn{N} highlight (Fix #10: per-region coverage)")
                inline_violation_added = True
        else:
            bs, be, op, kind = region
            key = (op, kind)
            if key in reported_regions:
                continue
            if not has_sibling(op):
                if ftype in ('md', 'qmd'):
                    add_violation(op, f"change inside non-rendering construct ({kind}) starting at this line lacks sibling <mark>...</mark><sup>N</sup> on the line immediately above")
                else:
                    add_violation(op, f"change inside non-rendering construct ({kind}) starting at this line lacks sibling \\tc{{...}}\\tcn{{N}} on the line immediately above")
                reported_regions.add(key)
                if kind == 'quarto-div':
                    suggest_draft = True

# Pure-deletion case (skipped when the edit is a valid resolution — accepting
# a deletion mark legitimately removes lines from the file).
if not is_pure_resolution and has_minus_only and not added_line_nums:
    if ftype in ('md', 'qmd'):
        add_violation(1, "deletion(s) detected with no <mark><s>...</s></mark><sup>N</sup> deletion marker")
    else:
        add_violation(1, "deletion(s) detected with no \\tc{\\sout{...}}\\tcn{N} deletion marker")

# ---------------------------------------------------------------------------
# Non-rendering content mask — for structural well-formedness and the
# per-file uniqueness scan, mask documentation examples inside non-rendering
# regions and (for markdown) inline backtick spans.
# ---------------------------------------------------------------------------
mask_chars = list(proposed_text)
_mask_line_starts = [0]
for _ln in proposed_lines:
    _mask_line_starts.append(_mask_line_starts[-1] + len(_ln) + 1)

def _mask_range(start_off, end_off):
    if start_off < 0: start_off = 0
    if end_off > len(mask_chars): end_off = len(mask_chars)
    for _i in range(start_off, end_off):
        if mask_chars[_i] != '\n':
            mask_chars[_i] = ' '

for (_bs, _be, _op, _kind) in regions:
    if _bs < 1 or _bs > n_lines:
        continue
    _be_clamped = _be if _be <= n_lines else n_lines
    _start_off = _mask_line_starts[_bs - 1]
    _end_off = _mask_line_starts[_be_clamped] if _be_clamped < len(_mask_line_starts) else len(mask_chars)
    _mask_range(_start_off, _end_off)

if ftype in ('md', 'qmd'):
    for _idx, _line in enumerate(proposed_lines, start=1):
        _line_off = _mask_line_starts[_idx - 1]
        _j = 0
        _llen = len(_line)
        while _j < _llen:
            if _line[_j] == '`':
                _close = _line.find('`', _j + 1)
                if _close == -1:
                    break
                _mask_range(_line_off + _j, _line_off + _close + 1)
                _j = _close + 1
            else:
                _j += 1

masked_text = ''.join(mask_chars)
masked_lines = masked_text.split('\n')

# ---------------------------------------------------------------------------
# Structural well-formedness (phase 2). Runs on MASKED text so that
# documentation tokens inside fenced code / verbatim / backticks etc.
# do not produce false positives.
#
# Markdown checks: every <mark> has matching </mark>, every </mark> is
# immediately followed by <sup>N</sup> with N numeric.
# LaTeX checks: every \tc{ closes cleanly, and is followed by \tcn{N}.
# ---------------------------------------------------------------------------
if ftype in ('md', 'qmd'):
    in_mark = False
    open_line = None
    for idx, line in enumerate(masked_lines, start=1):
        pos = 0
        L = len(line)
        while pos < L:
            if in_mark:
                close = line.find('</mark>', pos)
                if close == -1:
                    pos = L
                else:
                    end_close = close + len('</mark>')
                    tail = line[end_close:end_close+20]
                    if not sup_after_close_re.match(tail):
                        add_violation(idx, "</mark> not immediately followed by <sup>N</sup> reference number")
                    pos = end_close
                    in_mark = False
                    open_line = None
            else:
                op = line.find('<mark>', pos)
                if op == -1:
                    break
                pos = op + len('<mark>')
                in_mark = True
                open_line = idx
    if in_mark and open_line is not None:
        add_violation(open_line, "<mark> opened but never closed with </mark>")

elif ftype == 'tex':
    text = masked_text
    L = len(text)
    pos = 0
    _line_starts2 = [0]
    for ln in masked_lines:
        _line_starts2.append(_line_starts2[-1] + len(ln) + 1)
    def _off_to_line2(off):
        for i in range(1, len(_line_starts2)):
            if off < _line_starts2[i]:
                return i
        return len(_line_starts2) - 1
    tc_head_re2 = re.compile(r'\\tc\{')
    tcn_after_re = re.compile(r'\A\\tcn\{\d+\}')
    while pos < L:
        m = tc_head_re2.search(text, pos)
        if not m:
            break
        if text[m.start():m.start()+5] == '\\tcn{':
            pos = m.end()
            continue
        body_start = m.end()
        depth = 1
        i = body_start
        while i < L and depth > 0:
            c = text[i]
            if c == '\\' and i + 1 < L:
                i += 2
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if depth != 0:
            ln = _off_to_line2(m.start())
            add_violation(ln, "\\tc{...} body brace unmatched")
            pos = m.end()
            continue
        body_end_excl = i
        start_ln = _off_to_line2(m.start())
        tail = text[body_end_excl + 1: body_end_excl + 1 + 20]
        if not tcn_after_re.match(tail):
            add_violation(start_ln, "\\tc{...} not immediately followed by \\tcn{N} reference number")
        pos = body_end_excl + 1

# ---------------------------------------------------------------------------
# Per-file uniqueness of mark numbers (v2 patterns).
# ---------------------------------------------------------------------------
if ftype in ('md', 'qmd'):
    nums = re.findall(r'</mark><sup>(\d+)</sup>', masked_text)
elif ftype == 'tex':
    nums = re.findall(r'\\tcn\{(\d+)\}', masked_text)
else:
    nums = []

seen = {}
for n in nums:
    seen.setdefault(n, 0)
    seen[n] += 1
for n, count in seen.items():
    if count > 1:
        if ftype in ('md', 'qmd'):
            pat = re.compile(r'</mark><sup>' + re.escape(n) + r'</sup>')
        else:
            pat = re.compile(r'\\tcn\{' + re.escape(n) + r'\}')
        m = pat.search(masked_text)
        line_no = 1 + masked_text.count('\n', 0, m.start()) if m else 1
        add_violation(line_no, f"duplicate mark number {n} appears {count} times (per-file uniqueness required; renumber on collision)")

# ---------------------------------------------------------------------------
# Emit results.
# ---------------------------------------------------------------------------
violations.sort(key=lambda v: (v[0], v[1]))
with open(viol_path, 'w', encoding='utf-8') as f:
    for (ln, reason) in violations:
        f.write(f"{ln}\t{reason}\n")
with open(suggest_path, 'w', encoding='utf-8') as f:
    f.write("1\n" if suggest_draft else "0\n")
PYEOF
PY_STATUS=$?

if [ "${PY_STATUS}" -ne 0 ]; then
  tc_log "pre-tool-use.sh: analyzer failed with status ${PY_STATUS}; failing open"
  exit 0
fi

if [ ! -s "${VIOLATIONS_FILE}" ]; then
  exit 0
fi

SECTION_REF=""
case "${FILE_TYPE}" in
  md|qmd) SECTION_REF="SKILL.md §3 Highlight Syntax (Markdown), §6 Non-Rendering Contexts" ;;
  tex)    SECTION_REF="SKILL.md §4 Highlight Syntax (LaTeX), §6 Non-Rendering Contexts" ;;
esac

{
  printf 'track-changes: blocked %s to %s\n' "${TOOL_NAME}" "${FILE_PATH}"
  while IFS=$'\t' read -r line_no reason; do
    [ -z "${line_no}" ] && continue
    printf -- '- line %s: %s\n' "${line_no}" "${reason}"
  done < "${VIOLATIONS_FILE}"
  printf 'See %s.\n' "${SECTION_REF}"
  if [ -s "${SUGGEST_DRAFT_FILE}" ] && [ "$(head -c1 "${SUGGEST_DRAFT_FILE}")" = "1" ]; then
    printf 'This appears to involve an off-enumerated construct. If intentional, invoke /draft for this turn or /track-off for the session; see SKILL.md §6, §7.\n'
  fi
  if [ "${SUBAGENT_DETECTED}" -eq 1 ]; then
    printf 'Detected subagent context — if this is intentional drafting from a PCV builder, the user can invoke /draft then retry.\n'
  fi
} >&2

tc_log "pre-tool-use.sh: BLOCK ${TOOL_NAME} ${FILE_PATH} ($(wc -l < "${VIOLATIONS_FILE}") violations)"

exit 2
