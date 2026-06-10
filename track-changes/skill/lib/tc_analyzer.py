"""tc_analyzer — track-changes PreToolUse analyzer (Fix #11; v3 narrowed).

Extracted from the bash-embedded PYEOF heredoc in hooks/pre-tool-use.sh.
The native Python hook (hooks/pre_tool_use.py) imports this module and
calls analyze() in-process. (The v2 persistent daemon that also imported
this module was dropped in v3 C5.)

Module-level regex patterns are compiled once at import time.

v3 narrowing (C2): the §0 source-provenance stage-0 pass left track-changes
entirely (that machinery is reborn in the verified-import skill), and the §6
"edit-inside-a-non-rendering-construct needs a sibling mark" escape hatch was
cut (Option B): such edits now block as ordinary unwrapped content and route
to /draft. The brand-new-block sibling mechanism (_block_sibling_covered_lines)
is KEPT. The mark grammar (regexes + classification) is sourced from
tc_core.grammar (single source of truth); the offset-bearing extractors
(_md_extract_marks/_tex_extract_marks) stay local because they return
character offsets that tc_core.grammar's line-based extractor does not.

Public API:
    analyze(source_text, payload, tool_name, ftype) -> {
        'proposed_text': str,
        'violations': [(line_no, reason)],
        'suggest_draft': bool,
        'imported': [],   # constant empty (back-compat; §0 left the skill)
    }

Behavior matches the prior analyzer byte-for-byte for everything the v3
test-spec A-O categories cover (Fix #7 strikethrough encoding, Fix #8
resolution pre-pass, Fix #10 walk-based coverage, brand-new-block siblings).
"""
import re
import difflib

import tc_core.grammar as _grammar  # single source of truth for the mark grammar

# Pre-compiled regex patterns — sourced from tc_core.grammar (single source of
# truth) where shared, kept local only for analyzer-specific scans.
_MD_MARK_RE = _grammar.MD_MARK_RE
_MD_S_REP_RE = _grammar._MD_S_REP_RE
_MD_S_DEL_RE = _grammar._MD_S_DEL_RE
_MD_TILDE_REP_RE = _grammar._MD_TILDE_REP_RE
_MD_TILDE_DEL_RE = _grammar._MD_TILDE_DEL_RE
_TEX_SOUT_REP_RE = _grammar._TEX_SOUT_REP_RE
_TEX_SOUT_DEL_RE = _grammar._TEX_SOUT_DEL_RE
_TEX_HEAD_RE = _grammar.TEX_HEAD_RE
_TEX_TCN_AFTER_RE = _grammar.TEX_TCN_AFTER_RE
_TEX_TCN_AFTER_ANCHOR_RE = re.compile(r'\A\\tcn\{\d+\}')
_FENCE_OPEN_RE = re.compile(r'^\s{0,3}(```|~~~)([^`~].*)?$')
_DISPLAY_MATH_RE = re.compile(r'^\s*\$\$\s*$')
_YAML_DELIM_RE = re.compile(r'^---\s*$')
_GFM_SEP_RE = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$')
_GFM_PIPE_RE = re.compile(r'^\s*\|.*\|\s*$')
_QFD_OPEN_RE = re.compile(r'^\s*:::+\s*\S.*$')
_QFD_CLOSE_RE = re.compile(r'^\s*:::+\s*$')
_HUNK_RE = re.compile(r'^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@')
# v6 (Critic F4): attribute-tolerant so a provenance-typed sibling
# `<mark tc-prov="…">…</mark><sup>N</sup>` is recognized; still matches bare v5
# `<mark>`. The `(?:\s+[^>]*?)?` optionally consumes attributes on the open tag.
_MD_SIBLING_RE = re.compile(r'<mark(?:\s+[^>]*?)?>.*?</mark><sup>\d+</sup>')
_MD_SIBLING_PRE_RE = re.compile(r'^\s*<mark(?:\s+[^>]*?)?>.*?</mark><sup>\d+</sup>\s*$')
# Brand-new-block sibling (Option B mechanism 1): ATX heading at column 0.
_MD_ATX_HEADING_RE = re.compile(r'^#{1,6}(\s.*)?$')
_SUP_AFTER_CLOSE_RE = re.compile(r'\A<sup>\d+</sup>')
_TEX_ENVS = ('verbatim', 'lstlisting', 'minted', 'equation', 'equation*',
             'align', 'align*', 'gather', 'gather*', 'multline', 'multline*',
             'tabular')
_TEX_BEGIN_RE = re.compile(r'\\begin\{(' + '|'.join(re.escape(e) for e in _TEX_ENVS) + r')\}')
_TEX_END_RE = re.compile(r'\\end\{(' + '|'.join(re.escape(e) for e in _TEX_ENVS) + r')\}')
_MD_NUMS_RE = _grammar.MD_NUMS_RE
_TEX_NUMS_RE = _grammar.TEX_NUMS_RE


def _md_classify(body):
    """Thin adapter over tc_core.grammar.classify_md, returning the
    (type, old, new) tuple shape the offset-bearing extractors expect."""
    c = _grammar.classify_md(body)
    return (c['type'], c['old'], c['new'])


def _tex_classify(body):
    """Thin adapter over tc_core.grammar.classify_tex (tuple shape)."""
    c = _grammar.classify_tex(body)
    return (c['type'], c['old'], c['new'])


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
        # v6: named groups + captured body span — no hardcoded `<mark>`==6 offset
        # (which broke with a tc-prov attribute) and the number is group('n').
        n_val = m.group('n')
        orig_body = text[m.start('body'):m.end('body')]
        t, old, new = _md_classify(orig_body)
        prov = _grammar.prov_from_attrs(m.group('attrs'))
        marks.append({'N': n_val, 'start': m.start(), 'end': m.end(),
                      'body': orig_body, 'type': t, 'old': old, 'new': new,
                      'prov': prov})
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
        prov = _grammar.norm_prov(mh.group('prov'))   # v6 provenance
        marks.append({'N': tm.group(1), 'start': mh.start(), 'prov': prov,
                      'end': tail_start + len(tm.group(0)),
                      'body': body, 'type': t, 'old': old, 'new': new})
        pos = tail_start + len(tm.group(0))
    return marks


def _check_pure_resolution(src_text, prop_text, ftype):
    """Walk source and proposed in parallel; accept the edit if every byte
    is accounted for by a preserved mark, resolved source mark, introduced
    mark, or identical plain text.

    v3 (C2): the §6 mechanism-2 sibling-marked-region pairing was removed;
    the walk now handles plain marks only. Editing inside a non-rendering
    construct no longer resolves cleanly via a sibling and instead falls
    through to the ordinary unwrapped-content path.
    """
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
    s_pos = p_pos = 0
    s_idx = p_idx = 0
    s_len = len(src_text)
    p_len = len(prop_text)
    while s_pos < s_len or p_pos < p_len:
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


def _block_sibling_covered_lines(proposed_lines, added_set, ftype):
    """Block-sibling mechanism (KEPT in v3 — Option B "mechanism 1").

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
      - Markdown / Quarto only (md, qmd). A brand-new LaTeX construct (a lone
        `\\section{}` or a fresh `\\begin{env}`) is NOT covered by this
        mechanism — it blocks and routes to /draft. (The mechanism-2
        region-walk sibling that once covered LaTeX was removed in C2; the
        function returns early below for any non-md/qmd ftype.)
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


def analyze(source_text, payload, tool_name, ftype):
    """Run the full analyzer pipeline.

    Returns a dict with:
      'proposed_text': str — the constructed proposed file content (with CRLF normalised)
      'violations': list of (line_no, reason) tuples, sorted
      'suggest_draft': bool
      'imported': [] — constant empty (the §0 import machinery left
                  track-changes in v3; verified-import owns imports now).
                  Kept so any caller reading this key still works.
    On unsupported tool or unparseable payload, returns proposed_text=source_text,
    violations=[], suggest_draft=False (caller exits 0).
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

    def line_in_region(ln):
        """True if 1-indexed proposed line `ln` falls inside any detected
        non-rendering region body. v3 (C2): used ONLY to set the /draft hint —
        such an edit no longer gets a sibling escape hatch (mechanism 2 cut)."""
        for (bs, be, op, kind) in regions:
            if bs <= ln <= be:
                return True
        return False

    # Block-sibling coverage for brand-new headings / fenced blocks / `:::`
    # divs (Option B mechanism 1, KEPT). A sibling mark on the line immediately
    # above a new block covers the block's delimiter lines (and heading line)
    # so the author need not inline-wrap them (which would break parsing) nor
    # reach for /draft.
    block_sibling_lines = _block_sibling_covered_lines(
        proposed_lines, set(added_line_nums), ftype)

    # v6 Fix D: whole-region insertion. Lines enclosed by a well-formed region
    # (md/qmd `.tc-region` div with tc-n="N"; LaTeX `\begin{tcregion}{N}` …
    # `\end{tcregion}`) are ONE atomic tracked insertion — the region delimiters
    # carry the mark number, so every enclosed line (delimiters inclusive) is
    # covered and exempt from the inline-mark requirement.
    region_insertion_lines = _grammar.region_covered_lines(proposed_text, ftype)

    if not is_pure_resolution:
        inline_violation_added = False
        for ln in added_line_nums:
            line_text = proposed_lines[ln - 1] if 1 <= ln <= n_lines else ''
            # A line covered by a new-block sibling mark (mechanism 1) is exempt.
            if ln in block_sibling_lines:
                continue
            # A line inside a whole-region insertion (Fix D) is exempt.
            if ln in region_insertion_lines:
                continue
            if line_text.strip() == '':
                continue
            # v3 (C2): an added line inside an existing non-rendering construct
            # no longer has a sibling escape hatch (mechanism 2 cut) — it blocks
            # as ordinary unwrapped content. Hint /draft so the author can route
            # an in-construct edit through drafting mode.
            if line_in_region(ln):
                suggest_draft = True
            if not inline_violation_added:
                if ftype in ('md', 'qmd'):
                    add_v(ln, "added content not wrapped in <mark>...</mark><sup>N</sup> highlight (Fix #10: per-region coverage; every diff char must be inside a mark or be a resolution of an existing mark)")
                else:
                    add_v(ln, "added content not wrapped in \\tc{...}\\tcn{N} highlight (Fix #10: per-region coverage)")
                inline_violation_added = True

    if not is_pure_resolution and has_minus_only and not added_line_nums:
        if ftype in ('md', 'qmd'):
            add_v(1, "deletion(s) detected with no <mark><s>...</s></mark><sup>N</sup> deletion marker")
        else:
            add_v(1, "deletion(s) detected with no \\tc{\\sout{...}}\\tcn{N} deletion marker")

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

    # Per-file uniqueness. v6: region numbers (tc-n / \begin{tcregion}{N}) share
    # the single mark-number space, so include them — a region N that collides
    # with an inline mark N is a duplicate. Region openers are not masked, so
    # scan proposed_text for them.
    if ftype in ('md', 'qmd'):
        nums = _MD_NUMS_RE.findall(masked_text) + _grammar.MD_REGION_NUMS_RE.findall(proposed_text)
    elif ftype == 'tex':
        nums = _TEX_NUMS_RE.findall(masked_text) + _grammar.TEX_REGION_NUMS_RE.findall(proposed_text)
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
