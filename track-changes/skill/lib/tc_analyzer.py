"""tc_analyzer — track-changes PreToolUse analyzer (Fix #11).

Extracted from the bash-embedded PYEOF heredoc in hooks/pre-tool-use.sh.
Both the native Python hook (hooks/pre_tool_use.py) and the daemon
(lib/tc_daemon.py) import this module.

Module-level regex patterns are compiled once at import time. When the
daemon is in use, imports + compilations happen exactly once per session
instead of per-hook-invocation.

Public API:
    analyze(source_text, payload, tool_name, ftype) -> {
        'proposed_text': str,
        'violations': [(line_no, reason)],
        'suggest_draft': bool,
    }

Behavior matches the prior bash+heredoc analyzer byte-for-byte (Fix #7
strikethrough encoding, Fix #8 resolution pre-pass, Fix #10 walk-based
coverage with sibling-form support).
"""
import re
import difflib
import tc_provenance  # §0 source-provenance wrappers (C1/C3).

# Pre-compiled regex patterns (compiled once at module import).
_MD_MARK_RE = re.compile(r'<mark>(.*?)</mark><sup>(\d+)</sup>', re.DOTALL)
_MD_S_REP_RE = re.compile(r'^<s>(.*?)</s>(.+)$', re.DOTALL)
_MD_S_DEL_RE = re.compile(r'^<s>(.*?)</s>\s*$', re.DOTALL)
_MD_TILDE_REP_RE = re.compile(r'^~~(.*?)~~(.+)$', re.DOTALL)
_MD_TILDE_DEL_RE = re.compile(r'^~~(.*?)~~\s*$', re.DOTALL)
_TEX_SOUT_REP_RE = re.compile(r'^\\sout\{(.*?)\}(.+)$', re.DOTALL)
_TEX_SOUT_DEL_RE = re.compile(r'^\\sout\{(.*?)\}\s*$', re.DOTALL)
_TEX_HEAD_RE = re.compile(r'\\tc\{')
_TEX_TCN_AFTER_RE = re.compile(r'\\tcn\{(\d+)\}')
_TEX_TCN_AFTER_ANCHOR_RE = re.compile(r'\A\\tcn\{\d+\}')
_FENCE_OPEN_RE = re.compile(r'^\s{0,3}(```|~~~)([^`~].*)?$')
_DISPLAY_MATH_RE = re.compile(r'^\s*\$\$\s*$')
_YAML_DELIM_RE = re.compile(r'^---\s*$')
_GFM_SEP_RE = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$')
_GFM_PIPE_RE = re.compile(r'^\s*\|.*\|\s*$')
_QFD_OPEN_RE = re.compile(r'^\s*:::+\s*\S.*$')
_QFD_CLOSE_RE = re.compile(r'^\s*:::+\s*$')
_HUNK_RE = re.compile(r'^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@')
_MD_SIBLING_RE = re.compile(r'<mark>.*?</mark><sup>\d+</sup>')
_MD_SIBLING_PRE_RE = re.compile(r'^\s*<mark>.*?</mark><sup>\d+</sup>\s*$')
_TEX_SIBLING_RE = re.compile(r'\\tc\{[^}]*\}\\tcn\{\d+\}')
# §3 (C9): ATX heading line (must be at column 0 to parse; up to 6 #).
_MD_ATX_HEADING_RE = re.compile(r'^#{1,6}(\s.*)?$')
_SUP_AFTER_CLOSE_RE = re.compile(r'\A<sup>\d+</sup>')
_TEX_ENVS = ('verbatim', 'lstlisting', 'minted', 'equation', 'equation*',
             'align', 'align*', 'gather', 'gather*', 'multline', 'multline*',
             'tabular')
_TEX_BEGIN_RE = re.compile(r'\\begin\{(' + '|'.join(re.escape(e) for e in _TEX_ENVS) + r')\}')
_TEX_END_RE = re.compile(r'\\end\{(' + '|'.join(re.escape(e) for e in _TEX_ENVS) + r')\}')
_MD_NUMS_RE = re.compile(r'</mark><sup>(\d+)</sup>')
_TEX_NUMS_RE = re.compile(r'\\tcn\{(\d+)\}')
# §0 wrapper comment lines (opening or closing) — never content needing a mark.
_TC_WRAPPER_LINE_RE = re.compile(r'^\s*<!--\s*/?track-changes:?.*?-->\s*$')
# §7 cross-file lineage comment — never content needing a mark (C7 note).
_TC_FROMFILE_LINE_RE = re.compile(r'<!--\s*from-file=')


def _md_classify(body):
    m = _MD_S_REP_RE.match(body)
    if m: return ('replacement', m.group(1), m.group(2))
    m = _MD_S_DEL_RE.match(body)
    if m: return ('deletion', m.group(1), '')
    m = _MD_TILDE_REP_RE.match(body)
    if m: return ('replacement', m.group(1), m.group(2))
    m = _MD_TILDE_DEL_RE.match(body)
    if m: return ('deletion', m.group(1), '')
    return ('insertion', '', body)


def _tex_classify(body):
    m = _TEX_SOUT_REP_RE.match(body)
    if m: return ('replacement', m.group(1), m.group(2))
    m = _TEX_SOUT_DEL_RE.match(body)
    if m: return ('deletion', m.group(1), '')
    return ('insertion', '', body)


def _md_extract_marks(text):
    """Extract <mark>...</mark><sup>N</sup> tokens with documentation
    masking (backtick spans and fenced code blocks are blanked out so they
    can't yield false-positive marks or confuse the non-greedy regex)."""
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
    # Inline backtick spans (per line).
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
    nL = len(lines)
    i = 0
    while i < nL:
        mo = _FENCE_OPEN_RE.match(lines[i])
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
    for m in _MD_MARK_RE.finditer(masked_text):
        n_val = m.group(2)
        body_start = m.start() + 6
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
        tail_start = i + 1
        tm = _TEX_TCN_AFTER_RE.match(text[tail_start:tail_start + 30])
        if not tm:
            pos = tail_start; continue
        t, old, new = _tex_classify(body)
        marks.append({'N': tm.group(1), 'start': mh.start(),
                      'end': tail_start + len(tm.group(0)),
                      'body': body, 'type': t, 'old': old, 'new': new})
        pos = tail_start + len(tm.group(0))
    return marks


def _detect_regions_for_walk(text, ftype):
    """Return (body_start, body_end, opener_line_idx, kind) tuples for
    non-rendering regions, used by the walk's sibling-pair detection."""
    regions = []
    lines = text.split('\n')
    n = len(lines)
    line_starts = [0]
    for ln in lines:
        line_starts.append(line_starts[-1] + len(ln) + 1)
    if ftype in ('md', 'qmd'):
        i = 0
        while i < n:
            mo = _FENCE_OPEN_RE.match(lines[i])
            if mo:
                fc = mo.group(1)
                close_re = re.compile(r'^\s{0,3}' + re.escape(fc) + r'\s*$')
                opener_line = i
                j = i + 1
                while j < n:
                    if close_re.match(lines[j]):
                        regions.append((line_starts[i + 1], line_starts[j], opener_line, 'fenced-code'))
                        i = j + 1
                        break
                    j += 1
                else:
                    regions.append((line_starts[i + 1], len(text), opener_line, 'fenced-code'))
                    i = n
                continue
            i += 1
        i = 0
        while i < n:
            if _DISPLAY_MATH_RE.match(lines[i]):
                opener_line = i
                j = i + 1
                while j < n:
                    if _DISPLAY_MATH_RE.match(lines[j]):
                        regions.append((line_starts[i + 1], line_starts[j], opener_line, 'display-math'))
                        i = j + 1
                        break
                    j += 1
                else:
                    regions.append((line_starts[i + 1], len(text), opener_line, 'display-math'))
                    i = n
                continue
            i += 1
        for i in range(min(n, 8)):
            if _YAML_DELIM_RE.match(lines[i]):
                opener_line = i
                j = i + 1
                while j < n:
                    if _YAML_DELIM_RE.match(lines[j]):
                        regions.append((line_starts[i + 1], line_starts[j], opener_line, 'yaml-frontmatter'))
                        break
                    j += 1
                break
            if lines[i].strip() == '':
                continue
            if _MD_SIBLING_RE.search(lines[i]):
                continue
            break
        i = 0
        while i < n:
            if _GFM_SEP_RE.match(lines[i]) and i > 0 and _GFM_PIPE_RE.match(lines[i - 1]):
                opener_line = i - 1
                k = i + 1
                while k < n and _GFM_PIPE_RE.match(lines[k]):
                    k += 1
                regions.append((line_starts[i + 1], line_starts[k], opener_line, 'gfm-table'))
                i = k
                continue
            i += 1
    elif ftype == 'tex':
        i = 0
        while i < n:
            mb = _TEX_BEGIN_RE.search(lines[i])
            if mb:
                kind = mb.group(1)
                opener_line = i
                j = i + 1
                while j < n:
                    me = _TEX_END_RE.search(lines[j])
                    if me and me.group(1) == kind:
                        regions.append((line_starts[i + 1], line_starts[j], opener_line, 'latex-' + kind))
                        i = j + 1
                        break
                    j += 1
                else:
                    regions.append((line_starts[i + 1], len(text), opener_line, 'latex-' + kind))
                    i = n
                continue
            i += 1
    regions.sort()
    return regions


def _region_has_sibling(text, opener_line_idx, ftype):
    if opener_line_idx <= 0:
        return False
    lines = text.split('\n')
    sib_idx = opener_line_idx - 1
    if sib_idx >= len(lines):
        return False
    sib_line = lines[sib_idx]
    if ftype in ('md', 'qmd'):
        return bool(_MD_SIBLING_RE.search(sib_line))
    elif ftype == 'tex':
        return bool(_TEX_SIBLING_RE.search(sib_line))
    return False


def _check_pure_resolution(src_text, prop_text, ftype):
    """Walk source and proposed in parallel; accept the edit if every byte
    is accounted for by a preserved mark, resolved source mark, introduced
    mark, paired sibling-marked region body, or identical plain text."""
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
    s_regions = _detect_regions_for_walk(src_text, ftype)
    p_regions = _detect_regions_for_walk(prop_text, ftype)
    s_by_kind = {}
    p_by_kind = {}
    for r in s_regions:
        s_by_kind.setdefault(r[3], []).append(r)
    for r in p_regions:
        p_by_kind.setdefault(r[3], []).append(r)
    region_pairs = []
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
            consumed_old = False
            if mark_type == 'replacement' or mark_type == 'deletion':
                old_chars = p_m['old']
                if old_chars and src_text[s_pos:s_pos + len(old_chars)] == old_chars:
                    s_pos += len(old_chars)
                    consumed_old = True
            p_pos = mark_end
            sibling_line = (p_pos < p_len and prop_text[p_pos] == '\n'
                            and (mark_start == 0 or prop_text[mark_start - 1] == '\n'))
            if sibling_line:
                p_pos += 1
                if consumed_old and s_pos < s_len and src_text[s_pos] == '\n':
                    s_pos += 1
                while p_pos < p_len and prop_text[p_pos] == '\n' \
                        and not (s_pos < s_len and src_text[s_pos] == '\n'):
                    p_pos += 1
            p_idx += 1
            continue
        s_chunk_len = s_next - s_pos
        p_chunk_len = p_next - p_pos
        if s_chunk_len <= 0 and p_chunk_len <= 0:
            return False
        chunk_len = s_chunk_len if s_chunk_len < p_chunk_len else p_chunk_len
        if chunk_len <= 0:
            if s_chunk_len == 0 and p_chunk_len > 0 and p_m is not None and p_m['N'] not in s_n_set:
                p_seg = prop_text[p_pos:p_next]
                if p_seg.strip() == '':
                    preceded_nl = (p_m['start'] == 0 or prop_text[p_m['start'] - 1] == '\n')
                    followed_nl = (p_m['end'] < p_len and prop_text[p_m['end']] == '\n')
                    if preceded_nl and followed_nl:
                        p_pos = p_next
                        continue
            if p_chunk_len == 0 and s_chunk_len > 0 and s_m is not None and s_m['N'] not in p_n_set:
                s_seg = src_text[s_pos:s_next]
                if s_seg.strip() == '':
                    s_preceded_nl = (s_m['start'] == 0 or src_text[s_m['start'] - 1] == '\n')
                    s_followed_nl = (s_m['end'] < s_len and src_text[s_m['end']] == '\n')
                    if s_preceded_nl and s_followed_nl:
                        s_pos = s_next
                        continue
            return False
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


def _build_proposed(source_text, payload, tool_name):
    """Apply the payload to source_text; return the proposed string.
    Returns None for unsupported tools."""
    ti = (payload or {}).get('tool_input') or {}
    if tool_name == 'Write':
        return ti.get('content', '') or ''
    if tool_name == 'Edit':
        old = (ti.get('old_string', '') or '').replace('\r\n', '\n')
        new = (ti.get('new_string', '') or '').replace('\r\n', '\n')
        proposed = source_text.replace('\r\n', '\n')
        if old and old in proposed:
            proposed = proposed.replace(old, new, 1)
        return proposed
    if tool_name == 'MultiEdit':
        proposed = source_text.replace('\r\n', '\n')
        for ed in (ti.get('edits') or []):
            if not isinstance(ed, dict):
                continue
            old = (ed.get('old_string', '') or '').replace('\r\n', '\n')
            new = (ed.get('new_string', '') or '').replace('\r\n', '\n')
            if not old:
                continue
            if ed.get('replace_all'):
                proposed = proposed.replace(old, new)
            elif old in proposed:
                proposed = proposed.replace(old, new, 1)
        return proposed
    return None


def _stage0_provenance(proposed_text, sources):
    """§0 stage-0 pass (C4). Scan the proposed text for import wrappers and
    validate each against its resolved source slice in `sources`.

    `sources` maps from_spec -> resolved source slice text (or None when the
    hook could not read/slice the source — fail-closed: treated as mismatch).

    Returns (exempt_lines, imported_regions, discrepancies):
      exempt_lines      : set of 1-indexed proposed line numbers that are
                          inside a VERIFIED wrapper body (skip in the walk).
      imported_regions  : list of dicts for verified wrappers, for the audit
                          `imported:` entry — {lines:(a,b), from, verified,
                          normalization}.
      discrepancies     : list of (line_no, reason) for MISMATCHED wrappers
                          (C8 block message). The mismatched wrapper bodies
                          still fall through to normal new-content handling.
    """
    exempt_lines = set()
    imported_regions = []
    discrepancies = []
    try:
        wrappers = tc_provenance.scan_wrappers(proposed_text)
    except Exception:
        return exempt_lines, imported_regions, discrepancies
    for w in wrappers:
        src_slice = sources.get(w.from_spec) if sources else None
        verified = False
        if src_slice is not None:
            try:
                verified = tc_provenance.matches(w.body, src_slice, w.mode)
            except Exception:
                verified = False
        body_a = w.body_start_line
        body_b = w.line_end - 1  # last body line is just above the closer
        if verified:
            for ln in range(body_a, body_b + 1):
                exempt_lines.add(ln)
            imported_regions.append({
                'lines': (body_a, body_b),
                'from': w.from_spec,
                'verified': True,
                'normalization': w.mode,
            })
        else:
            # Fall through to normal handling AND surface a discrepancy.
            if src_slice is None:
                reason = (f"wrapped import from '{w.from_spec}' could not be "
                          f"verified (source missing or unreadable); treated as "
                          f"unverified new content. Either fix the source reference, "
                          f"correct the paraphrase, wrap the deviation in <mark>, "
                          f"or drop the import wrapper")
            else:
                src_q = _trim_quote(src_slice)
                prop_q = _trim_quote(w.body)
                reason = (f"wrapped import does not match source "
                          f"({w.from_spec}); source has \"{src_q}\", proposed has "
                          f"\"{prop_q}\". Either correct the paraphrase, wrap the "
                          f"change in <mark>, fix the source reference, or drop the "
                          f"import wrapper")
            discrepancies.append((w.body_start_line, reason))
    return exempt_lines, imported_regions, discrepancies


def _trim_quote(s, limit=80):
    """Condense a span to a single-line, length-bounded quote for messages."""
    one = ' '.join(s.split())
    if len(one) > limit:
        one = one[:limit - 3] + '...'
    return one


def _block_sibling_covered_lines(proposed_lines, added_set, ftype, exempt_lines):
    """§3 (C9): block-sibling extension.

    A brand-new (added) ATX heading line and a brand-new block's DELIMITER
    lines (fenced-code opener+closer, `:::` div opener+closer) are
    sibling-eligible: a `<mark>...</mark><sup>N</sup>` on the line immediately
    above the block start covers the whole new block, so the author can add a
    new section / fenced block / div WITHOUT `/draft` and without inline
    wrapping that would break parsing (e.g. `<mark>### x</mark>` breaks the
    heading; `<mark>```</mark>` breaks the fence).

    Returns a set of 1-indexed proposed line numbers that are covered by such
    a sibling mark (including the sibling mark line itself) and should be
    skipped by the per-line coverage walk.

    Rules:
      - The block must be BRAND NEW: every line of the block is in `added_set`.
        A MODIFIED existing heading therefore does not qualify (it follows the
        normal inline-edit rule).
      - The line immediately above the block start must carry a sibling mark.
      - F2 precedence: a block whose start line is already inside a verified
        import wrapper (in `exempt_lines`) is left to the import-wrapper logic
        and not separately processed here.
      - Markdown / Quarto only (md, qmd). LaTeX block envs already have full
        sibling support in the existing region walk.
    """
    covered = set()
    if ftype not in ('md', 'qmd'):
        return covered
    n = len(proposed_lines)

    def _has_sibling_above(start_idx0):
        # start_idx0 is the 0-indexed line of the block start.
        if start_idx0 <= 0:
            return False
        sib0 = start_idx0 - 1
        sib_line = proposed_lines[sib0]
        if not _MD_SIBLING_RE.search(sib_line):
            return False
        # The sibling mark line must itself be part of the new insertion
        # (a fresh sibling the author added to cover this new block), not a
        # pre-existing line that merely happens to hold a mark.
        return (sib0 + 1) in added_set

    i = 0
    while i < n:
        ln1 = i + 1  # 1-indexed
        if ln1 in exempt_lines:
            i += 1
            continue
        line = proposed_lines[i]
        # --- Fenced code block (opener .. matching closer) ---
        mo = _FENCE_OPEN_RE.match(line)
        if mo:
            fc = mo.group(1)
            close_re = re.compile(r'^\s{0,3}' + re.escape(fc) + r'\s*$')
            j = i + 1
            closer = -1
            while j < n:
                if close_re.match(proposed_lines[j]):
                    closer = j
                    break
                j += 1
            block_end0 = closer if closer >= 0 else n - 1
            block_lines = list(range(ln1, block_end0 + 2))  # 1-indexed inclusive
            all_new = all((b in added_set) for b in block_lines)
            if all_new and _has_sibling_above(i):
                covered.update(block_lines)
                covered.add(i)  # the sibling mark line (1-indexed == idx i)
            i = (block_end0 + 1) + 1
            continue
        # --- Quarto fenced div (::: opener .. ::: closer) ---
        if _QFD_OPEN_RE.match(line):
            j = i + 1
            closer = -1
            while j < n:
                if _QFD_CLOSE_RE.match(proposed_lines[j]):
                    closer = j
                    break
                j += 1
            block_end0 = closer if closer >= 0 else n - 1
            block_lines = list(range(ln1, block_end0 + 2))
            all_new = all((b in added_set) for b in block_lines)
            if all_new and _has_sibling_above(i):
                covered.update(block_lines)
                covered.add(i)
            i = (block_end0 + 1) + 1
            continue
        # --- ATX heading (single-line block) ---
        if _MD_ATX_HEADING_RE.match(line):
            if (ln1 in added_set) and _has_sibling_above(i):
                covered.add(ln1)
                covered.add(i)  # sibling mark line (1-indexed == idx i)
            i += 1
            continue
        i += 1
    return covered


def analyze(source_text, payload, tool_name, ftype, sources=None):
    """Run the full analyzer pipeline.

    Returns a dict with:
      'proposed_text': str — the constructed proposed file content (with CRLF normalised)
      'violations': list of (line_no, reason) tuples, sorted
      'suggest_draft': bool
      'imported': list of verified-wrapper dicts (only populated when sources
                  is supplied and at least one wrapper verifies) — for the
                  PostToolUse `imported:` audit entry (C6).
    On unsupported tool or unparseable payload, returns proposed_text=source_text,
    violations=[], suggest_draft=False (caller exits 0).

    Backward-compat (C4): when `sources is None`, the §0 stage-0 pass is
    skipped entirely and behavior is byte-identical to the v1 analyzer.
    """
    result = {'proposed_text': source_text, 'violations': [],
              'suggest_draft': False, 'imported': []}
    proposed_text = _build_proposed(source_text, payload, tool_name)
    if proposed_text is None:
        return result
    source_text = source_text.replace('\r\n', '\n')
    proposed_text = proposed_text.replace('\r\n', '\n')
    result['proposed_text'] = proposed_text
    if source_text == proposed_text:
        return result

    # Stage 0 (§0): only when the hook supplied resolved sources.
    exempt_lines = set()
    discrepancies = []
    if sources is not None:
        exempt_lines, imported_regions, discrepancies = _stage0_provenance(
            proposed_text, sources)
        result['imported'] = imported_regions

    violations = []
    suggest_draft = False
    def add_v(ln, reason): violations.append((ln, reason))

    _src_lines = source_text.split('\n')
    _prp_lines = proposed_text.split('\n')
    diff_text = ''.join(difflib.unified_diff(
        [l + '\n' for l in _src_lines],
        [l + '\n' for l in _prp_lines],
        fromfile='source', tofile='proposed', n=3))

    proposed_lines = _prp_lines
    n_lines = len(proposed_lines)

    # Resolution pre-pass.
    try:
        is_pure_resolution = _check_pure_resolution(source_text, proposed_text, ftype)
    except Exception:
        is_pure_resolution = False

    # Diff parse.
    added_line_nums = []
    diff_lines = diff_text.split('\n')
    in_hunk = False
    new_cursor = 0
    for dl in diff_lines:
        if dl.startswith('@@'):
            m = _HUNK_RE.match(dl)
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
        elif tag == ' ':
            new_cursor += 1
    has_minus_only = False
    if not added_line_nums:
        for dl in diff_lines:
            if dl.startswith('-') and not dl.startswith('---'):
                has_minus_only = True
                break

    # Region detection (for sibling-form errors AND mask).
    regions = []
    def add_region(bs, be, op, kind):
        if be >= bs:
            regions.append((bs, be, op, kind))

    if ftype in ('md', 'qmd'):
        i = 0
        while i < n_lines:
            mo = _FENCE_OPEN_RE.match(proposed_lines[i])
            if mo:
                opener = i + 1
                fc = mo.group(1)
                close_re = re.compile(r'^\s{0,3}' + re.escape(fc) + r'\s*$')
                j = i + 1
                while j < n_lines:
                    if close_re.match(proposed_lines[j]):
                        add_region(opener + 1, j, opener, 'fenced-code')
                        i = j + 1
                        break
                    j += 1
                else:
                    add_region(opener + 1, n_lines, opener, 'fenced-code')
                    i = n_lines
                continue
            i += 1
        i = 0
        while i < n_lines:
            if _DISPLAY_MATH_RE.match(proposed_lines[i]):
                opener = i + 1
                j = i + 1
                while j < n_lines:
                    if _DISPLAY_MATH_RE.match(proposed_lines[j]):
                        add_region(opener + 1, j, opener, 'display-math')
                        i = j + 1
                        break
                    j += 1
                else:
                    add_region(opener + 1, n_lines, opener, 'display-math')
                    i = n_lines
                continue
            i += 1
        yaml_opener_idx = -1
        for k in range(min(n_lines, 8)):
            s = proposed_lines[k]
            if _YAML_DELIM_RE.match(s):
                yaml_opener_idx = k
                break
            if s.strip() == '':
                continue
            if _MD_SIBLING_PRE_RE.match(s):
                continue
            break
        if yaml_opener_idx >= 0:
            opener = yaml_opener_idx + 1
            j = yaml_opener_idx + 1
            while j < n_lines:
                if _YAML_DELIM_RE.match(proposed_lines[j]):
                    add_region(opener + 1, j, opener, 'yaml-frontmatter')
                    break
                j += 1
        i = 0
        while i < n_lines:
            if _GFM_SEP_RE.match(proposed_lines[i]) and i > 0 and _GFM_PIPE_RE.match(proposed_lines[i - 1]):
                header_line_idx = i - 1
                opener = header_line_idx + 1
                k = i + 1
                while k < n_lines and _GFM_PIPE_RE.match(proposed_lines[k]):
                    k += 1
                add_region(header_line_idx + 2, k, opener, 'gfm-table')
                i = k
                continue
            i += 1
        i = 0
        while i < n_lines:
            if _QFD_OPEN_RE.match(proposed_lines[i]):
                opener = i + 1
                j = i + 1
                while j < n_lines:
                    if _QFD_CLOSE_RE.match(proposed_lines[j]):
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
        i = 0
        while i < n_lines:
            mb = _TEX_BEGIN_RE.search(proposed_lines[i])
            if mb:
                kind = mb.group(1)
                opener = i + 1
                j = i + 1
                while j < n_lines:
                    me = _TEX_END_RE.search(proposed_lines[j])
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
        i = 0
        while i < n_lines:
            if _DISPLAY_MATH_RE.match(proposed_lines[i]):
                opener = i + 1
                j = i + 1
                while j < n_lines:
                    if _DISPLAY_MATH_RE.match(proposed_lines[j]):
                        add_region(opener + 1, j, opener, 'tex-display-math')
                        i = j + 1
                        break
                    j += 1
                else:
                    add_region(opener + 1, n_lines, opener, 'tex-display-math')
                    i = n_lines
                continue
            i += 1

    def has_sibling(opener_1idx):
        if opener_1idx <= 1:
            return False
        sib_line = proposed_lines[opener_1idx - 2]
        if ftype in ('md', 'qmd'):
            return bool(_MD_SIBLING_RE.search(sib_line))
        elif ftype == 'tex':
            return bool(_TEX_SIBLING_RE.search(sib_line))
        return False

    def find_region_for_line(ln):
        best = None
        for (bs, be, op, kind) in regions:
            if bs <= ln <= be:
                if best is None or (op > best[2]):
                    best = (bs, be, op, kind)
        return best

    reported_regions = set()

    # §3 (C9): block-sibling coverage for brand-new headings / fenced blocks /
    # `:::` divs. A sibling mark on the line immediately above a new block
    # covers the block's delimiter lines (and heading line) so the author need
    # not inline-wrap them (which would break parsing) nor reach for /draft.
    block_sibling_lines = _block_sibling_covered_lines(
        proposed_lines, set(added_line_nums), ftype, exempt_lines)

    if not is_pure_resolution:
        inline_violation_added = False
        for ln in added_line_nums:
            line_text = proposed_lines[ln - 1] if 1 <= ln <= n_lines else ''
            # §0: a verified import-wrapper body line is exempt from the
            # <mark> coverage requirement (stage-0 marked it).
            if ln in exempt_lines:
                continue
            # §3 (C9): a line covered by a new-block sibling mark is exempt.
            if ln in block_sibling_lines:
                continue
            # §0/§7: wrapper comment lines and cross-file lineage comments are
            # bookkeeping, never content that needs a mark.
            if _TC_WRAPPER_LINE_RE.match(line_text) or _TC_FROMFILE_LINE_RE.search(line_text):
                continue
            region = find_region_for_line(ln)
            if region is None:
                if line_text.strip() == '':
                    continue
                if not inline_violation_added:
                    if ftype in ('md', 'qmd'):
                        add_v(ln, "added content not wrapped in <mark>...</mark><sup>N</sup> highlight (Fix #10: per-region coverage; every diff char must be inside a mark or be a resolution of an existing mark)")
                    else:
                        add_v(ln, "added content not wrapped in \\tc{...}\\tcn{N} highlight (Fix #10: per-region coverage)")
                    inline_violation_added = True
            else:
                bs, be, op, kind = region
                key = (op, kind)
                if key in reported_regions:
                    continue
                if not has_sibling(op):
                    if ftype in ('md', 'qmd'):
                        add_v(op, f"change inside non-rendering construct ({kind}) starting at this line lacks sibling <mark>...</mark><sup>N</sup> on the line immediately above")
                    else:
                        add_v(op, f"change inside non-rendering construct ({kind}) starting at this line lacks sibling \\tc{{...}}\\tcn{{N}} on the line immediately above")
                    reported_regions.add(key)
                    if kind == 'quarto-div':
                        suggest_draft = True

    if not is_pure_resolution and has_minus_only and not added_line_nums:
        if ftype in ('md', 'qmd'):
            add_v(1, "deletion(s) detected with no <mark><s>...</s></mark><sup>N</sup> deletion marker")
        else:
            add_v(1, "deletion(s) detected with no \\tc{\\sout{...}}\\tcn{N} deletion marker")

    # §0: import-wrapper discrepancies (C8). A mismatched wrapper both falls
    # through to the normal walk above (its body lines need a <mark>) AND
    # surfaces this explicit block message naming the deviation.
    for ln, reason in discrepancies:
        add_v(ln, reason)

    # Mask non-rendering content + backticks for structural and uniqueness scans.
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

    # Structural well-formedness.
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
                        tail = line[end_close:end_close + 20]
                        if not _SUP_AFTER_CLOSE_RE.match(tail):
                            add_v(idx, "</mark> not immediately followed by <sup>N</sup> reference number")
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
            add_v(open_line, "<mark> opened but never closed with </mark>")
    elif ftype == 'tex':
        text2 = masked_text
        L = len(text2)
        pos = 0
        _line_starts2 = [0]
        for ln in masked_lines:
            _line_starts2.append(_line_starts2[-1] + len(ln) + 1)
        def _off_to_line2(off):
            for i in range(1, len(_line_starts2)):
                if off < _line_starts2[i]:
                    return i
            return len(_line_starts2) - 1
        while pos < L:
            m = _TEX_HEAD_RE.search(text2, pos)
            if not m:
                break
            if text2[m.start():m.start() + 5] == '\\tcn{':
                pos = m.end()
                continue
            body_start = m.end()
            depth = 1
            i = body_start
            while i < L and depth > 0:
                c = text2[i]
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
                ln = _off_to_line2(m.start())
                add_v(ln, "\\tc{...} body brace unmatched")
                pos = m.end()
                continue
            body_end_excl = i
            start_ln = _off_to_line2(m.start())
            tail = text2[body_end_excl + 1: body_end_excl + 1 + 20]
            if not _TEX_TCN_AFTER_ANCHOR_RE.match(tail):
                add_v(start_ln, "\\tc{...} not immediately followed by \\tcn{N} reference number")
            pos = body_end_excl + 1

    # Per-file uniqueness.
    if ftype in ('md', 'qmd'):
        nums = _MD_NUMS_RE.findall(masked_text)
    elif ftype == 'tex':
        nums = _TEX_NUMS_RE.findall(masked_text)
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
            add_v(line_no, f"duplicate mark number {n} appears {count} times (per-file uniqueness required; renumber on collision)")

    violations.sort(key=lambda v: (v[0], v[1]))
    result['violations'] = violations
    result['suggest_draft'] = suggest_draft
    return result
