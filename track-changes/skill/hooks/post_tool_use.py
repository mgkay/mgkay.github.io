"""hooks/post_tool_use.py — track-changes PostToolUse hook (Fix #13 native).

Replaces hooks/post-tool-use.sh. Reads the JSON payload from stdin, runs
the activation gate in-process, resolves cache + log paths, dispatches
the audit logic either via the persistent daemon (fast path) or
in-process (fallback).

Always exits 0 — the audit log is best-effort and must not block the
user's workflow.
"""
import os
import sys
import json
import time

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(_HOOK_DIR)
_LIB_DIR = os.path.join(_SKILL_ROOT, 'lib')
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)


def _log(msg):
    try:
        home = os.environ.get('HOME') or os.path.expanduser('~')
        d = os.path.join(home, '.claude', 'skills', 'track-changes', 'state')
        os.makedirs(d, exist_ok=True)
        ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        with open(os.path.join(d, 'tc.log'), 'a', encoding='utf-8') as f:
            f.write(f'{ts} post_tool_use.py: {msg}\n')
    except Exception:
        pass


def main():
    try:
        data = sys.stdin.read()
    except Exception:
        return 0
    if not data:
        return 0
    try:
        payload = json.loads(data)
    except ValueError:
        return 0

    tool_name = (payload.get('tool_name') or '').strip()
    if tool_name not in ('Write', 'Edit', 'MultiEdit'):
        return 0
    ti = payload.get('tool_input') or {}
    file_path = (ti.get('file_path') or '').strip()
    if not file_path:
        return 0

    import tc_activation
    ftype = tc_activation.tc_file_type(file_path)
    if ftype not in ('md', 'qmd', 'tex'):
        return 0
    if not os.path.isfile(file_path):
        return 0

    reason = tc_activation.tc_should_track(file_path)
    # Audit log fires for genuine on-* tracking, not for /draft suspends.
    if not reason.startswith('on-'):
        return 0

    abs_file = os.path.abspath(file_path)

    import tc_audit
    cache_path = tc_audit.cache_path_for(abs_file)
    if cache_path is None:
        _log('cannot resolve cache path; skip')
        return 0
    marker = tc_activation.tc_find_marker(abs_file)
    log_path = tc_audit.log_path_for(abs_file, marker_path=marker)

    # Compute project-relative path for log header.
    log_dir = os.path.dirname(log_path)
    try:
        rel_for_log = os.path.relpath(abs_file, log_dir).replace(os.sep, '/')
    except ValueError:
        rel_for_log = abs_file

    try:
        with open(abs_file, 'r', encoding='utf-8', newline='') as f:
            source_text = f.read()
    except (IOError, UnicodeDecodeError):
        _log(f'cannot read {abs_file}; skip')
        return 0

    # Try daemon first.
    used_daemon = False
    try:
        import tc_daemon
        sock = tc_daemon.connect()
        if sock is None:
            tc_daemon.spawn_if_needed()
            sock = tc_daemon.connect()
        if sock is not None:
            resp = tc_daemon.send_request(sock, {
                'op': 'audit',
                'source_text': source_text,
                'tool_name': tool_name,
                'ftype': ftype,
                'abs_file_path': abs_file,
                'log_path': log_path,
                'cache_path': cache_path,
                'rel_path_for_log': rel_for_log,
            })
            if resp and resp.get('ok'):
                used_daemon = True
    except Exception as e:
        _log(f'daemon path failed: {e}; falling back to in-process')

    if not used_daemon:
        try:
            tc_audit.record(source_text, tool_name, ftype, abs_file,
                            log_path, cache_path, rel_for_log)
        except Exception as e:
            _log(f'in-process record failed: {e}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
