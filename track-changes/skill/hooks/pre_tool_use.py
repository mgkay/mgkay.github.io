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


def _emit_block(tool_name, file_path, violations, ftype, suggest_region, subagent_detected):
    section_ref = ('SKILL.md Highlight Syntax (Markdown)'
                   if ftype in ('md', 'qmd')
                   else 'SKILL.md Highlight Syntax (LaTeX)')
    is_md = ftype in ('md', 'qmd')
    out = [f'track-changes: blocked {tool_name} to {file_path}']
    for ln, reason in violations:
        out.append(f'- line {ln}: {reason}')
    # v6 Fix A: every AI write into a tracked deliverable must be tracked —
    # name the three honest paths, never suggest self-/draft (it is user-only).
    out.append('Everything you write into a tracked deliverable must be tracked. Use one of:')
    if is_md:
        out.append('  - inline mark (single edit):  <mark>NEW</mark><sup>M</sup>')
        out.append('  - whole-region insertion (multi-block new content — heading + prose + '
                   'code/div as ONE tracked insertion):')
        out.append('      ::: {.tc-region tc-n="M" tc-prov="authored"}\n      …new blocks…\n      :::')
    else:
        out.append('  - inline mark (single edit):  \\tc{NEW}\\tcn{M}')
        out.append('  - whole-region insertion (multi-block new content):')
        out.append('      \\begin{tcregion}{M}[authored]\n      …new blocks…\n      \\end{tcregion}')
    out.append('  - verbatim from a named source:  /tc import  (lands attributed, typed "imported")')
    out.append(f'See {section_ref}.')
    if suggest_region:
        out.append('This new content spans a non-inline construct (code/math/table/div); wrap it as a '
                   'whole-region insertion (above), which tracks the entire block as one unit.')
    if subagent_detected:
        out.append('Detected subagent context — author content as marks / a region / via /tc import. '
                   '/draft is USER-ONLY and cannot be self-invoked.')
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


def _emit(msg):
    """Write a message to stderr as UTF-8 (non-ASCII survives any codec).
    Mirrors verified-import's _emit / this hook's _emit_block byte-writer."""
    text = msg if msg.endswith('\n') else msg + '\n'
    try:
        sys.stderr.buffer.write(text.encode('utf-8'))
        sys.stderr.buffer.flush()
    except Exception:
        try:
            sys.stderr.write(text)
        except Exception:
            sys.stderr.write(text.encode('utf-8', 'replace').decode('ascii', 'replace'))


def _added_line_set(src_text, prop_text):
    """1-indexed proposed line numbers ADDED by the write — computed exactly the
    way tc_analyzer.analyze parses its unified diff (difflib n=3 + @@-hunk walk),
    so the gate and the analyzer agree on which lines are new."""
    import difflib
    import re as _re
    src_lines = src_text.split('\n')
    prp_lines = prop_text.split('\n')
    diff_text = ''.join(difflib.unified_diff(
        [l + '\n' for l in src_lines],
        [l + '\n' for l in prp_lines],
        fromfile='source', tofile='proposed', n=3))
    hunk_re = _re.compile(r'^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@')
    added = set()
    in_hunk = False
    new_cursor = 0
    for dl in diff_text.split('\n'):
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
        if dl.startswith('\\') or not dl:
            continue
        tag = dl[0]
        if tag == '+':
            added.add(new_cursor)
            new_cursor += 1
        elif tag == ' ':
            new_cursor += 1
    return added


def _source_gate(tool_name, file_path, source_text, payload, ftype):
    """v9 source-validation gate (MakePlan Dilemma A, resolution 2).

    Runs BEFORE the analyzer verdict on a tracked existing file. Detects NEW
    gray `.tc-verbatim` scaffolding (a verbatim block intersecting added lines)
    and enforces that it is verified verbatim against a live `/tc source`
    staging record:
      - zero new-gray blocks           → no-op (return None; nothing changes).
      - more than one new-gray block   → block (return 2): split the write.
      - exactly one, no live record    → block (return 2): stage with /tc source.
      - exactly one, live record:
          re-read the staged source slice; extraction failure → block, record
          PRESERVED. normalized-exact containment fails → block naming the
          fabricated/mismatched excerpt, record PRESERVED. The accompanying NEW
          green sourced region must carry tc-src == srcstage.expected_src(rec)
          and a tc-n number; missing/mismatched → block printing the expected
          value. All good → write the one-shot sentinel, append the `sourced:`
          audit entry, clear the record, and return None so the write proceeds
          to the analyzer (which consumes the sentinel and covers the gray).

    Fail-open to PROCEED only when the gate machinery itself cannot be imported
    (the gray lines then fall to the analyzer, which fails-open to VIOLATION).
    """
    try:
        import tc_analyzer
        from tc_core import grammar as tc_grammar
        from tc_core import srcstage
        from tc_core import sourcetext
        from tc_core import audit as tc_audit
    except Exception as e:
        _log(f'source gate: import failed ({e}); skipping gate')
        return None

    proposed = tc_analyzer._build_proposed(source_text, payload, tool_name)
    if proposed is None:
        return None
    src_norm = source_text.replace('\r\n', '\n')
    prop_norm = proposed.replace('\r\n', '\n')
    if src_norm == prop_norm:
        return None

    prop_lines = prop_norm.split('\n')
    added = _added_line_set(src_norm, prop_norm)

    # New gray content: verbatim blocks intersecting an added line.
    new_gray = []
    for b in tc_grammar.extract_verbatim_blocks(prop_norm, ftype):
        bs, be = b.get('start'), b.get('end')
        if not bs:
            continue
        span = set(range(bs, (be if be else len(prop_lines)) + 1))
        if span & added:
            new_gray.append(b)

    if not new_gray:
        return None  # gate is a no-op — everything proceeds as today

    hdr = f'track-changes: blocked {tool_name} to {file_path}'

    if len(new_gray) > 1:
        _emit(hdr + '\n'
              + f'This write adds {len(new_gray)} gray `.tc-verbatim` excerpts. '
              'Stage and land ONE sourced excerpt per write: split this into '
              f'{len(new_gray)} separate `/tc source` + write steps (each gray '
              'excerpt needs its own verified staging).')
        _log(f'SOURCE-BLOCK {file_path}: {len(new_gray)} new gray blocks')
        return 2

    block = new_gray[0]
    gray_body = block.get('body') or ''

    rec = srcstage.load(file_path)
    if rec is None:
        _emit(hdr + '\n'
              'A new gray `.tc-verbatim` excerpt requires a live `/tc source` '
              'staging. Run `/tc source <file>#<locator> [<target>]` (or '
              '`/tc source @citekey <locator> [<target>]`) first — it re-reads '
              'the source and authorizes this one write. Fail-closed: an '
              'unstaged (or expired) gray excerpt cannot verify.')
        _log(f'SOURCE-BLOCK {file_path}: gray block, no live staging record')
        return 2

    source_path = rec.get('source_path', '')
    locator = rec.get('locator') or ''
    expected = srcstage.expected_src(rec)

    # Re-read the staged source slice; fail-closed on any extraction failure,
    # preserving the record so a corrected re-stage still verifies.
    try:
        slice_text = sourcetext.extract_text(source_path, locator or None)
    except Exception as e:
        _emit(hdr + '\n'
              f'cannot re-read the staged source {source_path} '
              f'(locator: {locator or "whole"}) to verify the gray excerpt '
              f'({e}). Re-run `/tc source` to re-stage against a readable '
              'source. The staging record is preserved.')
        _log(f'SOURCE-BLOCK {file_path}: source re-read failed ({e}); '
             'record preserved')
        return 2

    if not sourcetext.contains(gray_body, slice_text):
        preview = sourcetext.normalize(gray_body)[:80]
        _emit(hdr + '\n'
              'the gray `.tc-verbatim` excerpt is NOT contained in the staged '
              f'source {expected} — it looks fabricated or mismatched. Excerpt '
              f'(normalized, first 80 chars): "{preview}". Re-stage with '
              '`/tc source` against the correct slice. The staging record is '
              'preserved.')
        _log(f'SOURCE-BLOCK {file_path}: excerpt not contained in {expected}; '
             'record preserved')
        return 2

    # Containment passed. The accompanying NEW green sourced region must carry
    # the expected tc-src (and a tc-n number).
    candidates = []
    for r in tc_grammar.extract_regions(prop_norm, ftype):
        if r.get('prov') != 'sourced':
            continue
        rs, re_ = r.get('start'), r.get('end')
        if not rs or not re_:
            continue
        if set(range(rs, re_ + 1)) & added:
            candidates.append(r)
    matched = [r for r in candidates if r.get('src') == expected]
    if not matched:
        if candidates:
            found = ', '.join('"%s"' % (r.get('src') or '') for r in candidates)
            detail = (f'found new sourced region(s) with tc-src {found}, but '
                      f'expected tc-src="{expected}".')
        else:
            detail = ('no NEW green `sourced` region accompanies the gray '
                      f'excerpt. Add one carrying tc-src="{expected}".')
        _emit(hdr + '\n'
              'the gray excerpt verified, but its green sourced region is '
              f'missing/mismatched. {detail} (md: '
              f'`::: {{.tc-region tc-n="N" tc-prov="sourced" tc-src="{expected}"}}`; '
              f'tex: `\\begin{{tcregion}}{{N}}[sourced][{expected}]`).')
        _log(f'SOURCE-BLOCK {file_path}: tc-src missing/mismatched; '
             f'expected {expected}')
        return 2

    region = matched[0]
    if region.get('N') is None:
        _emit(hdr + '\n'
              'the green sourced region needs a tc-n number (the mark number '
              'that carries this region). Add tc-n="N" (md) / {N} (tex).')
        _log(f'SOURCE-BLOCK {file_path}: sourced region missing tc-n')
        return 2

    # Verified. Write the one-shot sentinel the analyzer consumes, record the
    # durable `sourced:` audit entry, clear the transient staging record, and
    # fall through to the analyzer (which must still run). A failed sentinel
    # write (state dir unwritable / path too long) must fail CLOSED here with a
    # clear message — otherwise the analyzer refuses the gray block with the
    # generic unverified-excerpt error and the record has already been spent.
    if not srcstage.sentinel_write(file_path, srcstage.gray_sha_of(gray_body)):
        _emit('track-changes: could not record the source-verification '
              'sentinel (state dir unwritable or path too long). The staged '
              'record is preserved — retry, or check '
              '~/.claude/skills/track-changes/state/source-ok/.')
        _log(f'SOURCE-BLOCK {file_path}: sentinel_write failed (state dir)')
        return 2
    # supports = the region body (lines strictly between the delimiters).
    rs, re_ = region['start'], region['end']
    supports = '\n'.join(prop_lines[rs:re_ - 1])
    tc_audit.write_sourced_entry(file_path, rec, region['N'], expected,
                                 gray_body, supports)
    srcstage.clear(file_path)
    _log(f'SOURCE-OK {file_path}: region {region["N"]} tc-src {expected}; '
         'sentinel written, record cleared')
    return None


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

    # v9 source-validation gate (Dilemma A): a NEW gray `.tc-verbatim` excerpt
    # must be verified verbatim against a live `/tc source` staging before it
    # can land. Runs before the analyzer verdict; on the verified path it writes
    # the one-shot sentinel the analyzer consumes and falls through (returns
    # None). A no-op when the write adds no gray content (byte-identical to
    # prior behavior for every ordinary write).
    try:
        gate_rc = _source_gate(tool_name, file_path, source_text, payload, ftype)
    except Exception as e:
        _log(f'source gate raised ({e}); proceeding to analyzer')
        gate_rc = None
    if gate_rc is not None:
        return gate_rc

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
