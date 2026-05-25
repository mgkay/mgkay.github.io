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
    # Read stdin as raw bytes and decode UTF-8 explicitly. The CLI emits the
    # tool payload as UTF-8 JSON; relying on sys.stdin's text decoding mangles
    # multibyte chars (e.g. smart quotes in §0 import wrappers) on platforms
    # whose default stdin codec is not UTF-8 (Windows cp1252).
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
    msg = '\n'.join(out) + '\n'
    # Write UTF-8 explicitly so non-ASCII (section signs, smart quotes quoted
    # from a §0 source) survive on platforms whose stderr codec isn't UTF-8.
    try:
        sys.stderr.buffer.write(msg.encode('utf-8'))
        sys.stderr.buffer.flush()
    except Exception:
        try:
            sys.stderr.write(msg)
        except Exception:
            sys.stderr.write(msg.encode('utf-8', 'replace').decode('ascii', 'replace'))


def _resolve_sources(source_text, payload, tool_name, file_path):
    """§0: when the proposed text contains import wrappers, resolve + slice
    each named source and return a {from_spec: value} map. Returns None when
    there are no wrappers (so the analyzer takes its byte-identical v1 path).

    Each map value is one of:
      - the resolved slice STRING (verified path),
      - None (generic unverified — missing/unreadable past the sniff),
      - an unresolved-with-reason marker (tc_provenance.unresolved(...)) with a
        SPECIFIC actionable reason: not-found+did-you-mean (C4) or a binary /
        non-text rejection (C5). The marker is JSON-serializable so it survives
        the daemon socket round-trip; tc_analyzer surfaces its reason verbatim.

    FAIL-CLOSED: any unexpected error in resolution leaves that entry None (or a
    specific marker) rather than skipping the wrapper. Resolution order (C4):
    edited-file dir -> nearest .tc-tracked dir -> git root; absolute honored.
    """
    try:
        import tc_analyzer
        import tc_provenance
    except Exception:
        return None
    try:
        proposed_text = tc_analyzer._build_proposed(source_text, payload, tool_name)
    except Exception:
        proposed_text = None
    if proposed_text is None:
        return None
    proposed_text = proposed_text.replace('\r\n', '\n')
    try:
        wrappers = tc_provenance.scan_wrappers(proposed_text)
    except Exception:
        return None
    if not wrappers:
        return None  # no wrappers -> analyzer stays on the v1 path

    find_root = None
    try:
        import tc_audit
        find_root = tc_audit.find_project_root
    except Exception:
        find_root = None

    sources = {}
    for w in wrappers:
        if w.from_spec in sources:
            continue
        # C4: ordered resolution (file-dir, nearest .tc-tracked, git root);
        # absolute from= honored as-is. First existing file wins.
        src_path, tried = tc_provenance.resolve_source_path(
            w.path, file_path, find_root)
        if src_path is None:
            # C4: not-found -> unresolved-with-reason (did-you-mean).
            sources[w.from_spec] = tc_provenance.unresolved(
                _not_found_reason(w.path, file_path, tried))
            continue
        # C5: reject binary / non-text BEFORE opening/decoding the file.
        ok, why = tc_provenance.is_text_source(src_path)
        if not ok:
            sources[w.from_spec] = tc_provenance.unresolved(
                _binary_reason(w.path, why))
            continue
        try:
            with open(src_path, 'r', encoding='utf-8', newline='') as f:
                src_text = f.read()
            sources[w.from_spec] = tc_provenance.slice_fragment(src_text, w.frag)
        except (IOError, OSError, UnicodeDecodeError):
            # Fail-closed: generic unverified (e.g. a TOCTOU disappearance or a
            # latent decode issue past the sniff head).
            sources[w.from_spec] = None
        except Exception:
            sources[w.from_spec] = None
    return sources


def _not_found_reason(path, file_path, tried):
    """C4 — actionable not-found message: tried dirs + a did-you-mean hint."""
    tried_disp = ', '.join(tried) if tried else '(no candidate roots)'
    base = os.path.basename(path) or path
    suggestion = "write the path relative to the edited file (e.g. from=%s)" % base
    # If a git root is known, also suggest a repo-root-relative path.
    try:
        import tc_audit
        root = tc_audit.find_project_root(file_path)
    except Exception:
        root = None
    if root:
        try:
            rel = os.path.relpath(os.path.join(
                os.path.dirname(os.path.abspath(file_path)), path), root)
            rel = rel.replace(os.sep, '/')
            suggestion += " or to the repo root (e.g. from=%s)" % rel
        except Exception:
            pass
    return ("from=%s not found. Tried: %s. If the source is in the repo, %s."
            % (path, tried_disp, suggestion))


def _binary_reason(path, why):
    """C5 — actionable binary/non-text rejection message (names the format,
    points to SKILL.md §0; explicitly no decode/convert is attempted)."""
    base = os.path.basename(path) or path
    return ("track-changes §0 imports from text sources only "
            "(.md/.markdown/.qmd/.rmd/.tex/.txt). '%s' %s. Convert it to a "
            "vetted text source in a separate step, then import from that. "
            "See SKILL.md §0." % (base, why))


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

    # §0 (C2): resolve import-wrapper sources. Only do the disk I/O when the
    # proposed text actually contains wrappers, so ordinary edits keep their
    # current performance. `sources` stays None for the common no-wrapper case
    # (analyzer is then byte-identical to v1). FAIL-CLOSED: a missing/unreadable
    # source maps to None in the sources dict -> the wrapper is treated as
    # unverified new content (block).
    sources = _resolve_sources(source_text, payload, tool_name, file_path)

    # Try daemon first (unless disabled — TC_DISABLE_DAEMON forces the
    # in-process fallback path, used by tests to exercise both code paths).
    result = None
    try:
        if os.environ.get('TC_DISABLE_DAEMON'):
            raise RuntimeError('daemon disabled via TC_DISABLE_DAEMON')
        import tc_daemon
        sock = tc_daemon.connect()
        if sock is None:
            tc_daemon.spawn_if_needed()
            sock = tc_daemon.connect()
        if sock is not None:
            req = {
                'op': 'analyze',
                'protocol_version': 2,
                'source_text': source_text,
                'payload': payload,
                'tool_name': tool_name,
                'ftype': ftype,
            }
            if sources is not None:
                req['sources'] = sources
            resp = tc_daemon.send_request(sock, req)
            if resp and resp.get('ok'):
                result = {
                    'violations': [tuple(v) for v in resp.get('violations', [])],
                    'suggest_draft': bool(resp.get('suggest_draft', False)),
                    'proposed_text': resp.get('proposed_text', ''),
                }
    except Exception as e:
        _log(f'daemon path failed: {e}; falling back to in-process')

    if result is None:
        # Fallback: in-process analyzer. Pass `sources` on this path too so
        # neither path degrades (D1 both-paths requirement).
        try:
            import tc_analyzer
            result = tc_analyzer.analyze(source_text, payload, tool_name, ftype,
                                         sources=sources)
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
