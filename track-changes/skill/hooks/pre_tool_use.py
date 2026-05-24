"""hooks/pre_tool_use.py — track-changes PreToolUse hook (Fix #11 native).

Replaces hooks/pre-tool-use.sh. Reads the JSON payload from stdin, runs
the activation gate in-process (no bash subshells), dispatches the
analyzer either via the persistent daemon (fast path) or in-process
(fallback when daemon is unreachable).

Exit codes:
  0  allow (no violations, off-scope, or activation off)
  2  block (violations emitted to stderr)
"""
import os
import sys
import json
import time

# Make the lib directory importable.
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(_HOOK_DIR)
_LIB_DIR = os.path.join(_SKILL_ROOT, 'lib')
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)


def _log(msg):
    """Best-effort timestamped log to state/tc.log."""
    try:
        home = os.environ.get('HOME') or os.path.expanduser('~')
        d = os.path.join(home, '.claude', 'skills', 'track-changes', 'state')
        os.makedirs(d, exist_ok=True)
        ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        with open(os.path.join(d, 'tc.log'), 'a', encoding='utf-8') as f:
            f.write(f'{ts} pre_tool_use.py: {msg}\n')
    except Exception:
        pass


def _read_payload():
    try:
        data = sys.stdin.read()
    except Exception:
        return None
    if not data:
        return None
    try:
        return json.loads(data)
    except ValueError:
        return None


def _emit_block(tool_name, file_path, violations, ftype, suggest_draft, subagent_detected):
    section_ref = ('SKILL.md §3 Highlight Syntax (Markdown), §6 Non-Rendering Contexts'
                   if ftype in ('md', 'qmd')
                   else 'SKILL.md §4 Highlight Syntax (LaTeX), §6 Non-Rendering Contexts')
    out = [f'track-changes: blocked {tool_name} to {file_path}']
    for ln, reason in violations:
        out.append(f'- line {ln}: {reason}')
    out.append(f'See {section_ref}.')
    if suggest_draft:
        out.append('This appears to involve an off-enumerated construct. If intentional, '
                   'invoke /draft for this turn or /track-off for the session; see SKILL.md §6, §7.')
    if subagent_detected:
        out.append('Detected subagent context — if this is intentional drafting from a PCV builder, '
                   'the user can invoke /draft then retry.')
    sys.stderr.write('\n'.join(out) + '\n')


def main():
    payload = _read_payload()
    if payload is None:
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
    # New-file drafting passes through.
    if not os.path.isfile(file_path):
        return 0

    reason = tc_activation.tc_should_track(file_path)
    if not tc_activation.is_tracking_active(reason):
        _log(f'skip ({reason}) for {file_path}')
        return 0
    _log(f'ACTIVE ({reason}) for {file_path}')

    # Subagent detection (best-effort).
    payload_str = json.dumps(payload)
    import re
    subagent_detected = bool(re.search(
        r'"(?:subagent|sub_agent|subagent_id|subagent_type|agent_id|agent_type|'
        r'is_subagent|delegated_from|parent_session_id|parent_agent|spawned_by)"',
        payload_str))

    # Read source.
    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as f:
            source_text = f.read()
    except (IOError, OSError):
        _log(f'cannot read source {file_path}; failing open')
        return 0

    # Try daemon first.
    result = None
    try:
        import tc_daemon
        sock = tc_daemon.connect()
        if sock is None:
            tc_daemon.spawn_if_needed()
            sock = tc_daemon.connect()
        if sock is not None:
            resp = tc_daemon.send_request(sock, {
                'op': 'analyze',
                'source_text': source_text,
                'payload': payload,
                'tool_name': tool_name,
                'ftype': ftype,
            })
            if resp and resp.get('ok'):
                result = {
                    'violations': [tuple(v) for v in resp.get('violations', [])],
                    'suggest_draft': bool(resp.get('suggest_draft', False)),
                    'proposed_text': resp.get('proposed_text', ''),
                }
    except Exception as e:
        _log(f'daemon path failed: {e}; falling back to in-process')

    if result is None:
        # Fallback: in-process analyzer.
        try:
            import tc_analyzer
            result = tc_analyzer.analyze(source_text, payload, tool_name, ftype)
        except Exception as e:
            _log(f'in-process analyzer failed: {e}; failing open')
            return 0

    violations = result['violations']
    if not violations:
        return 0

    _emit_block(tool_name, file_path, violations, ftype, result['suggest_draft'], subagent_detected)
    _log(f'BLOCK {tool_name} {file_path} ({len(violations)} violations)')
    return 2


if __name__ == '__main__':
    sys.exit(main())
