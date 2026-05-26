"""tc_core.audit — PostToolUse audit-log analyzer (v3; narrowed from v2 tc_audit).

Diffs current marks vs the prior cache and appends introduced/resolved entries
to .tc-history.md. Mark extraction/classification now comes from tc_core.grammar
(single source of truth). v3 removes the §0 imported-region scan and §7
cross-file lineage scan (those features left track-changes); the result dict
retains empty `imported`/`lineage` keys for caller back-compat.

Public API:
    record(source_text, tool_name, ftype, abs_file_path, log_path,
           cache_path, rel_path_for_log) -> dict
      -> {'introduced': [...], 'resolved': [...], 'imported': [],
          'lineage': [], 'wrote_log': bool}
"""
import os
import json
import datetime
import hashlib

from . import grammar


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
        if in_text_new and not in_text_old:
            return 'accepted'
        if in_text_old and not in_text_new:
            return 'rejected'
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
# Main entry point.
# ---------------------------------------------------------------------------

def record(source_text, tool_name, ftype, abs_file_path, log_path,
           cache_path, rel_path_for_log):
    """Diff current marks vs prior cache, append a log entry for introduced +
    resolved marks, then write the new cache state. Best-effort: I/O errors are
    swallowed; the user's workflow is never blocked."""
    result = {'introduced': [], 'resolved': [], 'imported': [],
              'lineage': [], 'wrote_log': False}
    current_marks = grammar.extract_marks(source_text, ftype)
    current_by_n = {m['N']: m for m in current_marks}

    prior_by_n = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                prior_data = json.load(f)
            prior_by_n = {m['N']: m for m in prior_data.get('marks', [])}
        except (IOError, ValueError):
            prior_by_n = {}

    introduced = [m for n, m in current_by_n.items() if n not in prior_by_n]
    resolved = [m for n, m in prior_by_n.items() if n not in current_by_n]
    result['introduced'] = introduced
    result['resolved'] = resolved

    def _write_cache():
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({'file': abs_file_path, 'marks': current_marks}, f)
        except IOError:
            pass

    if not introduced and not resolved:
        _write_cache()
        return result

    ts = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
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
    entry = '\n'.join(lines) + '\n'

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

    _write_cache()
    return result
