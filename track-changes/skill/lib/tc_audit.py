"""tc_audit — PostToolUse audit-log analyzer (Fix #13).

Extracted from the bash-embedded PYEOF heredoc in hooks/post-tool-use.sh.
Both the native Python PostToolUse hook (hooks/post_tool_use.py) and the
daemon (lib/tc_daemon.py) import this module.

Module-level regex patterns are compiled once at import time. When the
daemon is in use, imports + compilations happen exactly once per session
instead of per-hook-invocation.

Public API:
    record(source_text, tool_name, ftype, abs_file_path, log_path,
           cache_path, rel_path_for_log) -> dict

Returns:
    {'introduced': [...], 'resolved': [...], 'wrote_log': bool}

Side effects:
    - Appends an entry to log_path (creating the file with a header if needed).
    - Writes the current mark state to cache_path (JSON).

Behavior matches the prior bash+heredoc audit analyzer byte-for-byte
(Fix #7 strikethrough + legacy fallback for resolution classification).
"""
import os
import re
import json
import datetime
import hashlib

# Pre-compiled regex patterns.
_MD_MARK_RE = re.compile(r'<mark>(.*?)</mark><sup>(\d+)</sup>', re.DOTALL)
_MD_S_REP_RE = re.compile(r'^<s>(.*?)</s>(.+)$', re.DOTALL)
_MD_S_DEL_RE = re.compile(r'^<s>(.*?)</s>\s*$', re.DOTALL)
_MD_TILDE_REP_RE = re.compile(r'^~~(.*?)~~(.+)$', re.DOTALL)
_MD_TILDE_DEL_RE = re.compile(r'^~~(.*?)~~\s*$', re.DOTALL)
_TEX_HEAD_RE = re.compile(r'\\tc\{')
_TEX_TCN_AFTER_RE = re.compile(r'\\tcn\{(\d+)\}')
_TEX_SOUT_REP_RE = re.compile(r'^\\sout\{(.*?)\}(.+)$', re.DOTALL)
_TEX_SOUT_DEL_RE = re.compile(r'^\\sout\{(.*?)\}\s*$', re.DOTALL)

# §7 cross-file lineage comment appended to a renumbered destination mark.
# Markdown: ...</mark><sup>14</sup><!-- from-file=doc-A:7 -->
# LaTeX:    ...\tcn{14}<!-- from-file=notes:4 -->
_MD_LINEAGE_RE = re.compile(
    r'</mark><sup>(?P<dest>\d+)</sup>\s*<!--\s*from-file=(?P<src>[^:>]+):(?P<srcn>\d+)\s*-->')
_TEX_LINEAGE_RE = re.compile(
    r'\\tcn\{(?P<dest>\d+)\}\s*<!--\s*from-file=(?P<src>[^:>]+):(?P<srcn>\d+)\s*-->')


def _classify_md(body):
    m = _MD_S_REP_RE.match(body)
    if m: return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    m = _MD_S_DEL_RE.match(body)
    if m: return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    m = _MD_TILDE_REP_RE.match(body)
    if m: return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    m = _MD_TILDE_DEL_RE.match(body)
    if m: return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    return {'type': 'insertion', 'old': '', 'new': body}


def _classify_tex(body):
    m = _TEX_SOUT_REP_RE.match(body)
    if m: return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    m = _TEX_SOUT_DEL_RE.match(body)
    if m: return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    return {'type': 'insertion', 'old': '', 'new': body}


def _extract_marks(text, ftype):
    """Return list of dicts: {N, type, line, old, new}. line is 1-indexed."""
    marks = []
    if ftype in ('md', 'qmd'):
        for m in _MD_MARK_RE.finditer(text):
            body = m.group(1)
            n = m.group(2)
            line_no = 1 + text.count('\n', 0, m.start())
            entry = _classify_md(body)
            entry['N'] = n
            entry['line'] = line_no
            marks.append(entry)
    elif ftype == 'tex':
        pos = 0
        L = len(text)
        while pos < L:
            mh = _TEX_HEAD_RE.search(text, pos)
            if not mh:
                break
            if text[mh.start():mh.start() + 5] == '\\tcn{':
                pos = mh.end(); continue
            body_start = mh.end()
            depth = 1
            i = body_start
            while i < L and depth > 0:
                c = text[i]
                if c == '\\' and i + 1 < L:
                    i += 2; continue
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            if depth != 0:
                pos = mh.end(); continue
            body = text[body_start:i]
            tail = text[i + 1:i + 1 + 30]
            tm = _TEX_TCN_AFTER_RE.match(tail)
            if not tm:
                pos = i + 1; continue
            n = tm.group(1)
            line_no = 1 + text.count('\n', 0, mh.start())
            entry = _classify_tex(body)
            entry['N'] = n
            entry['line'] = line_no
            marks.append(entry)
            pos = i + 1 + len(tm.group(0))
    return marks


def _infer_decision(prior_mark, current_text):
    """Best-effort accept/reject inference by substring search."""
    t = prior_mark.get('type', '')
    old = prior_mark.get('old', '')
    new = prior_mark.get('new', '')
    in_text_new = bool(new) and new in current_text
    in_text_old = bool(old) and old in current_text
    if t == 'insertion':
        return 'accepted' if in_text_new else 'rejected'
    if t == 'deletion':
        return 'rejected' if in_text_old else 'accepted'
    if t == 'replacement':
        if in_text_new and not in_text_old: return 'accepted'
        if in_text_old and not in_text_new: return 'rejected'
        return 'ambiguous'
    return 'ambiguous'


def _fmt_str(s):
    """Quote a string for the log entry."""
    if not s:
        return '""'
    if '\n' in s or '"' in s or len(s) > 200:
        indented = '\n'.join('      ' + ln for ln in s.split('\n'))
        return '|\n' + indented
    return '"' + s.replace('\\', '\\\\') + '"'


# ---------------------------------------------------------------------------
# Path helpers (ports of lib/tc-history.sh).
# ---------------------------------------------------------------------------

def _state_dir(home=None):
    h = home or os.environ.get('HOME') or os.path.expanduser('~')
    d = os.path.join(h, '.claude', 'skills', 'track-changes', 'state')
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return None
    return d


def cache_path_for(abs_file, home=None):
    sd = _state_dir(home)
    if sd is None:
        return None
    cache_dir = os.path.join(sd, 'cache')
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError:
        return None
    sha = hashlib.sha1(abs_file.encode('utf-8')).hexdigest()
    return os.path.join(cache_dir, sha + '.marks')


def find_project_root(abs_file):
    """Walk up from abs_file's directory looking for .git/. Return the root or None."""
    if not abs_file:
        return None
    d = os.path.dirname(os.path.abspath(abs_file))
    for _ in range(100):
        if os.path.isdir(os.path.join(d, '.git')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def log_path_for(abs_file, marker_path=None):
    """Project root -> .tc-history.md, fallback to marker dir, then file's own dir."""
    root = find_project_root(abs_file)
    if root:
        return os.path.join(root, '.tc-history.md')
    if marker_path:
        return os.path.join(os.path.dirname(marker_path), '.tc-history.md')
    return os.path.join(os.path.dirname(os.path.abspath(abs_file)), '.tc-history.md')


# ---------------------------------------------------------------------------
# §0 (C6) imported-region scan + §7 (C7) cross-file lineage scan.
# ---------------------------------------------------------------------------

def _scan_imported(source_text, abs_file_path):
    """C6: scan the post-edit file for verified import wrappers and return a
    list of {lines, from, verified, normalization} dicts for the audit
    `imported:` block.

    Re-resolves + re-validates each wrapper against its named source (the
    PreToolUse verification already passed; this re-check keeps the audit
    self-contained and honest). Best-effort: any I/O or import error yields an
    empty list rather than blocking the workflow.
    """
    try:
        import sys
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import tc_provenance
    except Exception:
        return []
    try:
        wrappers = tc_provenance.scan_wrappers(
            source_text.replace('\r\n', '\n'))
    except Exception:
        return []
    if not wrappers:
        return []
    root = find_project_root(abs_file_path) or os.path.dirname(
        os.path.abspath(abs_file_path))
    out = []
    for w in wrappers:
        if os.path.isabs(w.path):
            src_path = w.path
        else:
            src_path = os.path.join(root, w.path)
        verified = False
        try:
            with open(src_path, 'r', encoding='utf-8', newline='') as f:
                src_text = f.read()
            src_slice = tc_provenance.slice_fragment(src_text, w.frag)
            verified = tc_provenance.matches(w.body, src_slice, w.mode)
        except Exception:
            verified = False
        if verified:
            out.append({
                'lines': (w.body_start_line, w.line_end - 1),
                'from': w.from_spec,
                'verified': True,
                'normalization': w.mode,
            })
    return out


def _scan_lineage(source_text, ftype):
    """C7: scan for cross-file lineage comments appended to renumbered marks.
    Returns a list of {src, src_n, dest_n} mapping dicts."""
    rx = _TEX_LINEAGE_RE if ftype == 'tex' else _MD_LINEAGE_RE
    out = []
    for m in rx.finditer(source_text):
        out.append({
            'src': m.group('src').strip(),
            'src_n': m.group('srcn'),
            'dest_n': m.group('dest'),
        })
    return out


# ---------------------------------------------------------------------------
# Main entry point.
# ---------------------------------------------------------------------------

def record(source_text, tool_name, ftype, abs_file_path, log_path,
           cache_path, rel_path_for_log):
    """Run the audit-log update.

    Diffs current marks vs prior cache, appends a log entry for
    introduced + resolved marks, verified import regions (§0 C6), and
    cross-file lineage mappings (§7 C7), then writes the new cache state.

    Returns: {'introduced': [marks], 'resolved': [marks], 'imported': [...],
              'lineage': [...], 'wrote_log': bool}.
    Best-effort: I/O errors are swallowed; the user's workflow is never blocked.
    """
    result = {'introduced': [], 'resolved': [], 'imported': [],
              'lineage': [], 'wrote_log': False}
    current_marks = _extract_marks(source_text, ftype)
    current_by_n = {m['N']: m for m in current_marks}

    # Load prior cache (marks + previously-logged imports/lineage keys).
    prior_by_n = {}
    prior_imported_keys = set()
    prior_lineage_keys = set()
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                prior_data = json.load(f)
            prior_by_n = {m['N']: m for m in prior_data.get('marks', [])}
            prior_imported_keys = set(prior_data.get('imported_keys', []))
            prior_lineage_keys = set(prior_data.get('lineage_keys', []))
        except (IOError, ValueError):
            prior_by_n = {}

    # Diff marks.
    introduced = [m for n, m in current_by_n.items() if n not in prior_by_n]
    resolved = [m for n, m in prior_by_n.items() if n not in current_by_n]
    result['introduced'] = introduced
    result['resolved'] = resolved

    # §0 (C6): verified import regions; §7 (C7): cross-file lineage. Both are
    # deduped against the cache so a re-run on an unchanged file does not
    # re-log them.
    all_imported = _scan_imported(source_text, abs_file_path)
    all_lineage = _scan_lineage(source_text, ftype)
    cur_imported_keys = {f"{r['from']}@{r['lines'][0]}-{r['lines'][1]}"
                         for r in all_imported}
    cur_lineage_keys = {f"{lg['src']}:{lg['src_n']}->{lg['dest_n']}"
                        for lg in all_lineage}
    imported = [r for r in all_imported
                if f"{r['from']}@{r['lines'][0]}-{r['lines'][1]}"
                not in prior_imported_keys]
    lineage = [lg for lg in all_lineage
               if f"{lg['src']}:{lg['src_n']}->{lg['dest_n']}"
               not in prior_lineage_keys]
    result['imported'] = imported
    result['lineage'] = lineage

    def _write_cache():
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({'file': abs_file_path, 'marks': current_marks,
                           'imported_keys': sorted(cur_imported_keys),
                           'lineage_keys': sorted(cur_lineage_keys)}, f)
        except IOError:
            pass

    # Update cache regardless of whether we have anything to log.
    if not introduced and not resolved and not imported and not lineage:
        _write_cache()
        return result

    # Build entry.
    ts = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = [f"\n## {ts} -- {rel_path_for_log}  ({tool_name})"]
    if introduced:
        lines.append("introduced:")
        for m in introduced:
            lines.append(f"  - mark: {m['N']}")
            lines.append(f"    type: {m['type']}")
            lines.append(f"    line: {m['line']}")
            if m['type'] in ('deletion', 'replacement'):
                lines.append(f"    old: {_fmt_str(m.get('old', ''))}")
            if m['type'] in ('insertion', 'replacement'):
                lines.append(f"    new: {_fmt_str(m.get('new', ''))}")
    if resolved:
        lines.append("resolved:")
        for m in resolved:
            decision = _infer_decision(m, source_text)
            lines.append(f"  - mark: {m['N']}")
            lines.append(f"    was_type: {m.get('type', '?')}")
            lines.append(f"    decision: {decision}")
            if m.get('old', ''):
                lines.append(f"    was_old: {_fmt_str(m['old'])}")
            if m.get('new', ''):
                lines.append(f"    was_new: {_fmt_str(m['new'])}")
    if imported:
        lines.append("imported:")
        for r in imported:
            a, b = r['lines']
            lines.append(f"  - lines: {a}-{b}")
            lines.append(f"    from: {r['from']}")
            lines.append(f"    verified: {'true' if r['verified'] else 'false'}")
            lines.append(f"    normalization: {r['normalization']}")
    if lineage:
        lines.append("lineage:")
        for lg in lineage:
            lines.append(f"  - from-file: {lg['src']}:{lg['src_n']}")
            lines.append(f"    dest: {rel_path_for_log}:{lg['dest_n']}")
            lines.append(f"    mapping: {lg['src']}:{lg['src_n']} -> "
                         f"{lg['dest_n']}")
    entry = '\n'.join(lines) + '\n'

    # Append to log (create with header if needed).
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
        result['wrote_log'] = True
    except IOError:
        pass

    # Update cache.
    _write_cache()

    return result
