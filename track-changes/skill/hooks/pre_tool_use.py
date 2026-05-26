"""hooks/pre_tool_use.py — track-changes PreToolUse hook (Fix #11 native).

Replaces hooks/pre-tool-use.sh. Reads the JSON payload from stdin, runs
the activation gate in-process (no bash subshells), and dispatches the
analyzer in-process (tc_analyzer.analyze). The v2 persistent-daemon
fast-path was dropped in v3 (C5): the measured in-process latency is well
under the budget, so the daemon's complexity bought no meaningful saving.

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
    # Read stdin as raw bytes and decode UTF-8 explicitly. The CLI emits the
    # tool payload as UTF-8 JSON; relying on sys.stdin's text decoding mangles
    # multibyte chars (e.g. smart quotes) on platforms whose default stdin
    # codec is not UTF-8 (Windows cp1252).
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
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
    if not raw:
        return None
    try:
        data = raw.decode('utf-8')
    except UnicodeDecodeError:
        try:
            data = raw.decode('utf-8', errors='replace')
        except Exception:
            return None
    try:
        return json.loads(data)
    except ValueError:
        return None


def _emit_block(tool_name, file_path, violations, ftype, suggest_draft, subagent_detected):
    section_ref = ('SKILL.md Highlight Syntax (Markdown)'
                   if ftype in ('md', 'qmd')
                   else 'SKILL.md Highlight Syntax (LaTeX)')
    out = [f'track-changes: blocked {tool_name} to {file_path}']
    for ln, reason in violations:
        out.append(f'- line {ln}: {reason}')
    out.append(f'See {section_ref}.')
    if suggest_draft:
        out.append('This edit lands inside a non-rendering construct (code/math/table/div), '
                   'which cannot carry an inline mark. If intentional, invoke /draft for this '
                   'turn; see SKILL.md.')
    if subagent_detected:
        out.append('Detected subagent context — if this is intentional drafting from a PCV builder, '
                   'the user can invoke /draft then retry.')
    msg = '\n'.join(out) + '\n'
    # Write UTF-8 explicitly so non-ASCII (section signs, smart quotes) survive
    # on platforms whose stderr codec isn't UTF-8.
    try:
        sys.stderr.buffer.write(msg.encode('utf-8'))
        sys.stderr.buffer.flush()
    except Exception:
        try:
            sys.stderr.write(msg)
        except Exception:
            sys.stderr.write(msg.encode('utf-8', 'replace').decode('ascii', 'replace'))


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

    from tc_core import activation as tc_activation
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

    # Read source.
    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as f:
            source_text = f.read()
    except (IOError, OSError):
        _log(f'cannot read source {file_path}; failing open')
        return 0

    # F2 exemption pass-through (C2). verified-import names the exact bytes it
    # is about to write to this tracked file via a one-shot, sha-bound sentinel
    # (tc_core.exempt). If the proposed write matches a live sentinel, this is a
    # verified clean import — allow it silently with no <mark> requirement.
    # The sentinel is consumed (one-shot) regardless of match, so a second write
    # is no longer exempt. Computed over the raw proposed bytes (the same
    # convention tc_core.exempt.content_sha uses, which verified-import records).
    try:
        import tc_analyzer
        proposed_for_exempt = tc_analyzer._build_proposed(
            source_text, payload, tool_name)
    except Exception:
        proposed_for_exempt = None
    if proposed_for_exempt is not None:
        try:
            from tc_core import exempt as tc_exempt
            content_sha = tc_exempt.content_sha(proposed_for_exempt)
            if tc_exempt.consume(file_path, content_sha):
                _log(f'EXEMPT (verified import) {tool_name} {file_path}')
                return 0
        except Exception as e:
            _log(f'exemption check failed: {e}; proceeding to analyzer')

    # Subagent detection (best-effort).
    payload_str = json.dumps(payload)
    import re
    subagent_detected = bool(re.search(
        r'"(?:subagent|sub_agent|subagent_id|subagent_type|agent_id|agent_type|'
        r'is_subagent|delegated_from|parent_session_id|parent_agent|spawned_by)"',
        payload_str))

    # In-process analyzer (the only path — the v2 daemon fast-path was dropped
    # in v3 C5; in-process latency measured well under budget).
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
