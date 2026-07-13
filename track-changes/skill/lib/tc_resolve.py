"""tc_resolve — §5 batch mark resolution (C10).

Implements the `/tc list | accept | reject | accept-all | reject-all`
subcommands. Resolution edits the tracked file directly:

  - accept => keep the mark's `new` text, strip the
    `<mark>...</mark><sup>N</sup>` wrapper (and any `<s>...</s>` /
    `~~...~~` strikethrough of the old text).
  - reject => restore the mark's `old` text, strip the wrapper.

Supports `.md` / `.qmd` (`<mark>` form) and `.tex` (`\\tc{}\\tcn{}` form).

Explicit audit attribution (F7): every resolution writes a log entry with
`decision: explicit` so a later PostToolUse Fix #8 *inference* never
overwrites the human's recorded choice. The mark cache is also updated to
the post-resolution mark set, so a subsequent edit diffs against the
already-resolved state and does not re-infer these marks.

Reuses the offset-bearing mark extractors in tc_analyzer
(`_md_extract_marks` / `_tex_extract_marks`, which return character offsets)
and the path/cache/log helpers in tc_core.audit (single source of truth; the
v2 `tc_audit` shim was removed in v3 C2). The line-based mark extractor for
the cache comes from tc_core.grammar.

Module-level regexes compiled once at import (matches house style).
Best-effort, fail-open I/O for the audit side effects: a logging failure
never aborts the resolution edit.

Public API:
    parse_ranges(spec, max_n) -> sorted list[int]
    list_marks(path) -> list[dict]                       (for `/tc list`)
    resolve(path, decision, ns) -> dict                  (accept|reject of a set)
    main(argv) -> int                                    (CLI entry)
"""
import os
import re
import sys
import json
import datetime
import subprocess

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import tc_analyzer            # offset-bearing mark extractors + classification
from tc_core import audit as tc_audit      # path/cache/log helpers
from tc_core import grammar as tc_grammar  # line-based mark extractor (cache)


def file_type(path):
    p = path.lower()
    if p.endswith('.md'):
        return 'md'
    if p.endswith('.qmd'):
        return 'qmd'
    if p.endswith('.tex'):
        return 'tex'
    return 'other'


# ---------------------------------------------------------------------------
# Range parsing: "1-25,!7,!11" -> {1..25} - {7,11}.
# Grammar: comma-separated terms. A term is either
#   <a>        single number
#   <a>-<b>    inclusive range (a<=b)
#   !<a>       exclude single number
#   !<a>-<b>   exclude inclusive range
# Whitespace around terms is ignored.
# ---------------------------------------------------------------------------
_RANGE_TERM_RE = re.compile(r'^(?P<bang>!)?(?P<a>\d+)(?:-(?P<b>\d+))?$')


def parse_ranges(spec, max_n=None):
    """Parse a range spec into a sorted list of ints. `max_n`, if given, is
    used only to validate (out-of-range numbers are kept; the caller decides
    what to do with numbers that have no matching mark). Raises ValueError on
    a malformed term."""
    include = set()
    exclude = set()
    if spec is None:
        return []
    for raw in spec.split(','):
        term = raw.strip()
        if not term:
            continue
        m = _RANGE_TERM_RE.match(term)
        if not m:
            raise ValueError("bad range term: %r" % term)
        a = int(m.group('a'))
        b = int(m.group('b')) if m.group('b') is not None else a
        if b < a:
            a, b = b, a
        target = exclude if m.group('bang') else include
        for v in range(a, b + 1):
            target.add(v)
    result = sorted(include - exclude)
    return result


# ---------------------------------------------------------------------------
# Mark extraction (with character offsets) reusing tc_analyzer.
# ---------------------------------------------------------------------------

def _extract_marks_with_offsets(text, ftype):
    if ftype in ('md', 'qmd'):
        return tc_analyzer._md_extract_marks(text)
    if ftype == 'tex':
        return tc_analyzer._tex_extract_marks(text)
    return []


def _extract_regions_with_offsets(text, ftype):
    """v6 Fix D: whole-region insertions with character offsets for the opener
    and closer delimiter LINES (each span includes its trailing newline), so the
    resolver can splice them. Body lies between opener_end and closer_start.

    Returns dicts {N, prov, opener_start, opener_end, closer_start, closer_end,
    line}. Only well-formed regions (both delimiters present) are returned.
    """
    regions = tc_grammar.extract_regions(text, ftype)
    lines = text.split('\n')
    starts = [0]
    for ln in lines:
        starts.append(starts[-1] + len(ln) + 1)  # +1 for the '\n'
    out = []
    for r in regions:
        s, e = r.get('start'), r.get('end')
        if not s or not e or e > len(lines) or s < 1:
            continue
        out.append({
            'N': r['N'], 'prov': r.get('prov', 'authored'),
            'join': r.get('join'), 'line': s, 'close_line': e,
            'opener_start': starts[s - 1], 'opener_end': starts[s],
            'closer_start': starts[e - 1], 'closer_end': starts[e],
            'body_start': starts[s], 'body_end': starts[e - 1],
        })
    return out


def _line_starts(text):
    """Char offset at the start of each line (index i = start of 1-indexed line
    i+1). starts[k] is the offset just past the k-th line's trailing '\\n'."""
    starts = [0]
    for ln in text.split('\n'):
        starts.append(starts[-1] + len(ln) + 1)  # +1 for the '\n'
    return starts


def _extract_verbatim_with_offsets(text, ftype):
    """v9.3.0: gray `.tc-verbatim` scaffolding blocks with the char-offset span of
    the WHOLE block (opener delimiter line through the closer line inclusive of
    its trailing newline). Returns dicts {start_line, end_line, span_start,
    span_end, citation}; only closed blocks (end present)."""
    blocks = tc_grammar.extract_verbatim_blocks(text, ftype)
    n_lines = len(text.split('\n'))
    starts = _line_starts(text)
    out = []
    for b in blocks:
        s, e = b.get('start'), b.get('end')
        if not s or not e or e > n_lines or s < 1:
            continue
        out.append({
            'start_line': s, 'end_line': e,
            'span_start': starts[s - 1], 'span_end': starts[e],
            'citation': b.get('citation'),
        })
    return out


def _paired_gray_span(region_line, gray_blocks, text):
    """v9.3.0: the char span to splice out for the gray `.tc-verbatim` block
    paired with a region whose opener is at 1-indexed `region_line`.

    Pairing is conservative and adjacency-based: the paired block is the closed
    gray block whose closer line sits immediately above the region opener,
    separated only by blank lines. Returns (span_start, span_end) covering the
    block AND the blank gap up to (not including) the region opener line, so no
    orphan blank lines remain. Returns None when no block is immediately
    adjacent (already removed, or a non-scaffolded region) — never guessing
    across intervening content."""
    lines = text.split('\n')
    starts = _line_starts(text)
    best = None
    for b in gray_blocks:
        if b['end_line'] >= region_line:
            continue
        # Lines strictly between the block closer and the region opener
        # (1-indexed end_line+1 .. region_line-1) must all be blank.
        gap = lines[b['end_line']:region_line - 1]
        if all(g.strip() == '' for g in gap):
            if best is None or b['end_line'] > best['end_line']:
                best = b
    if best is None:
        return None
    return (best['span_start'], starts[region_line - 1])


# v9.4.0: a "body-prose" line is a valid paragraph-join neighbour — non-blank and
# NOT a structural construct (heading / list / quote / table / fenced div / region
# or environment delimiter). Conservative: anything that looks structural is
# rejected, so an ambiguous neighbour falls back to a standalone block (safe).
_STRUCT_LINE_RE = re.compile(
    r'^\s*(?:'
    r'#|'                       # md heading
    r'[-*+]\s|'                 # md bullet list
    r'\d+[.)]\s|'               # md ordered list
    r'>|'                       # md blockquote
    r'\||'                      # md table row
    r':{3,}|'                   # md fenced div (region/verbatim)
    r'`{3,}|~{3,}|'             # md code fence
    r'\\begin|\\end|'           # LaTeX environment
    r'\\(?:sub)*section|\\paragraph|\\item|\\chapter|'  # LaTeX sectioning/list
    r'%|'                       # LaTeX comment
    r'\[|\]'                    # LaTeX display-math delimiters
    r')')


def _is_body_line(line):
    """True iff `line` is ordinary body prose (a valid tc-join neighbour)."""
    return line.strip() != '' and _STRUCT_LINE_RE.match(line) is None


def _join_splice(region, text, ftype, gray_blocks):
    """v9.4.0: for an ACCEPTED region carrying `join` in {prev,next}, return
    `(span, subsumes_gray)` where `span` is a single (start, end, repl) that merges
    the region body onto the adjacent body paragraph (one space join), replacing the
    standalone opener/closer strip; or `(None, False)` to fall back to the standalone
    strip when there is no valid neighbour.

    The neighbour scan skips blank lines AND gray `.tc-verbatim` scaffolding lines
    (they are transient and removed on resolution), so a `sourced` region whose
    paragraph sits above its paired gray block still rejoins that paragraph. When a
    `prev` merge subsumes the paired gray block (it lies inside the removed span),
    `subsumes_gray` is True so the caller does not also remove it separately."""
    join = region.get('join')
    if join not in ('prev', 'next'):
        return (None, False)
    body_text = ' '.join(text[region['body_start']:region['body_end']].split())
    if not body_text:
        return (None, False)
    lines = text.split('\n')
    starts = _line_starts(text)
    n = len(lines)
    o_line = region['line']            # opener, 1-indexed
    c_line = region['close_line']      # closer, 1-indexed
    gray_lines = set()
    for gb in gray_blocks:
        gray_lines.update(range(gb['start_line'], gb['end_line'] + 1))

    if join == 'prev':
        pl = o_line - 1
        while pl >= 1 and (lines[pl - 1].strip() == '' or pl in gray_lines):
            pl -= 1
        if pl < 1 or not _is_body_line(lines[pl - 1]):
            return (None, False)
        prev_content_end = starts[pl - 1] + len(lines[pl - 1])
        span = (prev_content_end, region['closer_end'], ' ' + body_text + '\n')
        subsumes_gray = any(pl < gb['start_line'] and gb['end_line'] < o_line
                            for gb in gray_blocks)
        return (span, subsumes_gray)

    # join == 'next'
    nl = c_line + 1
    while nl <= n and (lines[nl - 1].strip() == '' or nl in gray_lines):
        nl += 1
    if nl > n or not _is_body_line(lines[nl - 1]):
        return (None, False)
    next_content_start = starts[nl - 1]
    span = (region['opener_start'], next_content_start, body_text + ' ')
    return (span, False)


def _orphan_line_after(text, offset):
    """v9.4.0 orphan heuristic: at char `offset` in the POST-resolution `text`,
    is the line there a single-line paragraph sandwiched between two body
    paragraphs (blank/BOF above, blank/EOF below, body prose on each present
    side)? Returns the orphan line's stripped text, or None. Advisory only."""
    lines = text.split('\n')
    starts = _line_starts(text)
    # Locate the 1-indexed line containing `offset`.
    li = 1
    for i in range(len(lines)):
        if starts[i] <= offset < starts[i + 1]:
            li = i + 1
            break
    else:
        li = min(max(1, len(lines)), len(lines))
    if li < 1 or li > len(lines):
        return None
    cur = lines[li - 1]
    if not _is_body_line(cur):
        return None
    # Above: nearest non-blank must be a blank gap then a body paragraph (or BOF).
    above = lines[li - 2] if li - 2 >= 0 else ''
    below = lines[li] if li < len(lines) else ''
    above_blank = (li == 1) or (above.strip() == '')
    below_blank = (li == len(lines)) or (below.strip() == '')
    if not (above_blank and below_blank):
        return None
    # Require a real body paragraph on at least one present side (so we do not warn
    # on a lone line in an otherwise empty document).
    def _body_across_gap(idx, step):
        j = idx + step
        while 1 <= j <= len(lines) and lines[j - 1].strip() == '':
            j += step
        return 1 <= j <= len(lines) and _is_body_line(lines[j - 1])
    has_prev = _body_across_gap(li, -1)
    has_next = _body_across_gap(li, +1)
    # "Sandwiched between TWO body paragraphs" — require a body paragraph on both
    # sides (the region-split-orphan signature). A one-line paragraph at the top,
    # the end, or next to a heading/list/region is not flagged.
    if not (has_prev and has_next):
        return None
    return cur.strip()


def _preview(s, limit=60):
    one = ' '.join((s or '').split())
    if len(one) > limit:
        one = one[:limit - 3] + '...'
    return one


def list_marks(path):
    """Return a list of {N, type, line, old, new, preview} for every mark in
    the file, in document order. Raises IOError if the file cannot be read."""
    ftype = file_type(path)
    if ftype == 'other':
        raise ValueError("unsupported file type: %s" % path)
    with open(path, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
    text = text.replace('\r\n', '\n')
    marks = _extract_marks_with_offsets(text, ftype)
    out = []
    for m in marks:
        t = m['type']
        if t == 'deletion':
            preview = '[delete] ' + _preview(m['old'])
        elif t == 'replacement':
            preview = _preview(m['old']) + ' -> ' + _preview(m['new'])
        else:
            preview = _preview(m['new'])
        line_no = 1 + text.count('\n', 0, m['start'])
        out.append({'N': m['N'], 'type': t, 'line': line_no,
                    'old': m['old'], 'new': m['new'], 'preview': preview})
    # v6 Fix D: include whole-region insertions so /tc list shows them and
    # /tc accept|reject recognizes their numbers.
    for r in tc_grammar.extract_regions(text, ftype):
        s, e = r.get('start'), r.get('end')
        if not s or not e:
            continue
        out.append({'N': r['N'], 'type': 'region', 'line': s,
                    'old': '', 'new': '', 'prov': r.get('prov', 'authored'),
                    'preview': f"[region {r.get('prov', 'authored')}] lines {s}-{e}"})
    out.sort(key=lambda d: (d['line'], _n_key(d['N'])))
    return out


# ---------------------------------------------------------------------------
# Resolution: rewrite the file applying accept/reject to a set of mark Ns.
# ---------------------------------------------------------------------------

def _resolved_replacement(mark, decision):
    """Return the literal text that should replace the whole
    <mark>...</mark><sup>N</sup> (or \\tc{...}\\tcn{N}) span for the given
    decision. accept => keep new; reject => restore old."""
    if decision == 'accept':
        return mark['new']
    # reject
    return mark['old']


def _owned_line_empty_span(text, start, end, repl):
    """Fix #6: detect a resolved mark that OWNED its own line and whose
    replacement collapses the line to empty, returning the span to remove so
    no orphan blank line remains.

    The mark owns its line when, on the ORIGINAL `text`:
      - the chars from the line start (after the preceding '\\n' or BOF) up to
        `start` are all whitespace, AND
      - the chars from `end` to the line end (next '\\n' or EOF) are all
        whitespace, AND
      - `repl` (the resolution text) is empty or whitespace-only.

    Returns a (seg_start, seg_end) pair to remove instead of [start:end]:
      - Base case: remove the mark line through its trailing '\\n' (inclusive),
        dropping the empty line that an '' replacement would otherwise leave.
        At EOF (no trailing '\\n') the span stops at end-of-text.
      - Block-paragraph case: when the owned line is flanked by blank-line
        separators on BOTH sides (a brand-new-block / deleted-paragraph
        sibling), the two separators would collapse to two adjacent blank
        lines (triple-spacing). Consume ONE following blank line too so a
        single separator remains.

    Returns None when the mark is mid-line (inline) or leaves non-empty
    content on the line — those keep the ordinary [start:end] splice.
    """
    if repl.strip() != '':
        return None
    # Line start: just after the previous '\n' (or beginning of file).
    nl_before = text.rfind('\n', 0, start)
    line_start = 0 if nl_before == -1 else nl_before + 1
    # Leading chars on the line before the mark must be whitespace.
    if text[line_start:start].strip() != '':
        return None
    # Line end: the next '\n' at or after `end` (or EOF).
    nl_after = text.find('\n', end)
    at_eof = nl_after == -1
    line_end = len(text) if at_eof else nl_after
    # Trailing chars on the line after the mark must be whitespace.
    if text[end:line_end].strip() != '':
        return None
    if at_eof:
        return (line_start, line_end)
    swallow_end = nl_after + 1  # swallow the mark line's own trailing newline

    # Block-paragraph collapse: only when the owned line is flanked by blank
    # lines on BOTH sides. "Preceded by a blank line" => the char before
    # line_start is a '\n' that terminates an empty line (line_start-1 is '\n'
    # and the line before it is also empty/BOF). Practically: line_start >= 1
    # and text[line_start-1] == '\n'. "Followed by a blank line" => the line
    # starting at swallow_end is empty (next char is '\n' or EOF-with-no-text).
    preceded_blank = line_start >= 1 and text[line_start - 1] == '\n'
    next_nl = text.find('\n', swallow_end)
    if next_nl == -1:
        followed_blank = text[swallow_end:].strip() == '' and swallow_end < len(text)
        follow_end = len(text)
    else:
        followed_blank = text[swallow_end:next_nl].strip() == ''
        follow_end = next_nl + 1
    if preceded_blank and followed_blank:
        swallow_end = follow_end
    return (line_start, swallow_end)


def resolve(path, decision, ns):
    """Apply `decision` ('accept' | 'reject') to the marks whose N is in
    `ns` (a collection of string or int values). Edits the file in place,
    writes an explicit-attribution audit entry, and updates the mark cache.

    Returns a dict:
      {'resolved': [N...], 'not_found': [N...], 'remaining': [N...],
       'wrote_file': bool, 'wrote_log': bool}
    """
    if decision not in ('accept', 'reject'):
        raise ValueError("decision must be 'accept' or 'reject'")
    ftype = file_type(path)
    if ftype == 'other':
        raise ValueError("unsupported file type: %s" % path)
    want = set(str(n) for n in ns)

    with open(path, 'r', encoding='utf-8', newline='') as f:
        original = f.read()
    text = original.replace('\r\n', '\n')
    marks = _extract_marks_with_offsets(text, ftype)
    regions = _extract_regions_with_offsets(text, ftype)   # v6 Fix D
    gray_blocks = _extract_verbatim_with_offsets(text, ftype)  # v9.3.0
    by_n = {m['N']: m for m in marks}
    region_by_n = {r['N']: r for r in regions}

    resolved = []
    not_found = sorted((n for n in want if n not in by_n and n not in region_by_n),
                       key=_n_key)

    # Build splice spans (start, end, repl) against the ORIGINAL text for both
    # inline marks and whole-region insertions, then apply right-to-left so
    # earlier offsets stay valid. Regions are atomic and never overlap an inline
    # mark, so one sorted apply is safe.
    spans = []          # (start, end, repl)
    resolved_marks = []
    for m in (mm for mm in marks if mm['N'] in want):
        repl = _resolved_replacement(m, decision)
        # Fix #6: if the mark owned its own line and the replacement collapses
        # that line to empty, swallow the whole line (incl. its trailing '\n').
        # Detection uses the ORIGINAL `text` (offsets are valid there).
        span = _owned_line_empty_span(text, m['start'], m['end'], repl)
        spans.append(span + (repl,) if span is not None
                     else (m['start'], m['end'], repl))
        resolved.append(m['N'])
        resolved_marks.append(m)
    sourced_resolved = []       # v9.3.0: Ns of resolved sourced regions (C3 trigger)
    join_fallbacks = []         # v9.4.0: Ns whose tc-join found no valid neighbour
    orphan_probe_regions = []   # v9.4.0: (N) resolved standalone (no join) → probe
    for r in (rr for rr in regions if rr['N'] in want):
        prov = r.get('prov', 'authored')
        gray_removed = False
        used_join = False
        join_applied = None
        # v9.4.0 (Issue 2): a region carrying tc-join="prev"|"next" rejoins an
        # adjacent body paragraph on ACCEPT instead of leaving a standalone block.
        if decision == 'accept' and r.get('join') in ('prev', 'next'):
            jspan, subsumes_gray = _join_splice(r, text, ftype, gray_blocks)
            if jspan is not None:
                spans.append(jspan)
                used_join = True
                join_applied = r['join']
                if subsumes_gray:
                    gray_removed = True   # the merge span already removed the gray
            else:
                join_applied = 'fallback'
                join_fallbacks.append(r['N'])
        if not used_join:
            if decision == 'accept':
                # Keep the body; strip the closer then the opener delimiter line.
                spans.append((r['closer_start'], r['closer_end'], ''))
                spans.append((r['opener_start'], r['opener_end'], ''))
                orphan_probe_regions.append(r)
            else:
                # reject: remove the whole region (opener through closer inclusive).
                spans.append((r['opener_start'], r['closer_end'], ''))
        # v9.3.0 (Issue 1): a sourced/transcript region's paired gray
        # `.tc-verbatim` scaffolding is transient — remove it in the same
        # resolution (accept OR reject). Its durable record persists in
        # `.tc-history.md`; conservative adjacency pairing (see _paired_gray_span).
        # (A `prev`-join that subsumed the gray block already removed it.)
        if prov in ('sourced', 'transcript') and not gray_removed:
            gspan = _paired_gray_span(r['line'], gray_blocks, text)
            if gspan is not None:
                spans.append((gspan[0], gspan[1], ''))
                gray_removed = True
        if prov == 'sourced':
            sourced_resolved.append(r['N'])
        resolved.append(r['N'])
        entry = {'N': r['N'], 'type': 'region', 'old': '',
                 'new': '(region)', 'prov': prov, 'gray_removed': gray_removed}
        if join_applied:
            entry['join'] = join_applied
        resolved_marks.append(entry)
    spans.sort(key=lambda s: s[0], reverse=True)
    new_text = text
    for (s, e, repl) in spans:
        new_text = new_text[:s] + repl + new_text[e:]
    resolved = sorted(set(resolved), key=_n_key)

    # v9.4.0 (Issue 1): accept-time orphan warning — a region resolved standalone
    # (no tc-join) whose single-line body now sits as a paragraph sandwiched
    # between two body paragraphs is likely a region-split fragment. Advisory only.
    orphan_warnings = []
    if decision == 'accept' and orphan_probe_regions:
        new_lines = new_text.split('\n')
        new_starts = _line_starts(new_text)
        for r in orphan_probe_regions:
            body = ' '.join(text[r['body_start']:r['body_end']].split())
            if not body:
                continue
            raw = [ln for ln in text[r['body_start']:r['body_end']].split('\n')
                   if ln.strip()]
            if len(raw) != 1:            # only a single-line body can orphan
                continue
            for i, ln in enumerate(new_lines):
                if ' '.join(ln.split()) == body:
                    orphan = _orphan_line_after(new_text, new_starts[i])
                    if orphan is not None:
                        orphan_warnings.append({'N': r['N'], 'text': orphan})
                    break

    wrote_file = False
    if new_text != text:
        # Preserve the file's original EOL convention (best-effort): if the
        # original used CRLF, re-apply it. Otherwise write LF.
        out_text = new_text
        if '\r\n' in original and '\r\n' not in out_text:
            out_text = out_text.replace('\n', '\r\n')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(out_text)
        wrote_file = True

    remaining = sorted(
        [m['N'] for m in marks if m['N'] not in want]
        + [r['N'] for r in regions if r['N'] not in want], key=_n_key)

    # Audit attribution (explicit) + cache update. Best-effort.
    wrote_log = _write_explicit_audit(path, ftype, decision, resolved_marks,
                                      new_text)
    _update_cache(path, ftype, new_text)

    return {'resolved': resolved, 'not_found': not_found,
            'remaining': remaining, 'wrote_file': wrote_file,
            'wrote_log': wrote_log,
            'sourced_resolved': sorted(set(sourced_resolved), key=_n_key),
            'join_fallbacks': sorted(set(join_fallbacks), key=_n_key),
            'orphan_warnings': orphan_warnings}


def _n_key(n):
    try:
        return (0, int(n))
    except (TypeError, ValueError):
        return (1, str(n))


# ---------------------------------------------------------------------------
# Audit side effects.
# ---------------------------------------------------------------------------

def _write_explicit_audit(path, ftype, decision, resolved_marks, post_text):
    """Append a `resolved:` block carrying `decision: explicit` (F7) so a
    later Fix #8 inference never re-classifies these marks. Best-effort."""
    if not resolved_marks:
        return False
    abs_path = os.path.abspath(path)
    log_path = tc_audit.log_path_for(abs_path)
    root = tc_audit.find_project_root(abs_path)
    if root:
        try:
            rel = os.path.relpath(abs_path, root).replace(os.sep, '/')
        except ValueError:
            rel = os.path.basename(abs_path)
    else:
        rel = os.path.basename(abs_path)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = [f"\n## {ts} -- {rel}  (/tc {decision})"]
    lines.append("resolved:")
    for m in sorted(resolved_marks, key=lambda mm: _n_key(mm['N'])):
        lines.append(f"  - mark: {m['N']}")
        lines.append(f"    was_type: {m.get('type', '?')}")
        lines.append(f"    decision: explicit")
        lines.append(f"    action: {'accepted' if decision == 'accept' else 'rejected'}")
        if m.get('old', ''):
            lines.append(f"    was_old: {tc_audit._fmt_str(m['old'])}")
        if m.get('new', ''):
            lines.append(f"    was_new: {tc_audit._fmt_str(m['new'])}")
        if m.get('gray_removed'):
            lines.append(f"    gray_removed: true")  # v9.3.0 paired .tc-verbatim
        if m.get('join'):
            lines.append(f"    join: {m['join']}")   # v9.4.0 paragraph-join
    entry = '\n'.join(lines) + '\n'
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if not os.path.exists(log_path):
            header = (
                "# track-changes history\n"
                "#\n"
                "# Append-only audit log of AI-introduced and AI-introduced-then-resolved\n"
                "# marks for tracked files in this project. Each entry records one\n"
                "# Write/Edit/MultiEdit or explicit /tc resolution. Diffable + greppable.\n"
                "#\n"
                "# Generated and maintained by the track-changes skill.\n"
                "# Do not edit by hand (append-only). To reset: delete this file.\n"
            )
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(header)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(entry)
        return True
    except (IOError, OSError):
        return False


def _update_cache(path, ftype, post_text):
    """Rewrite the mark cache to the post-resolution mark set so a subsequent
    PostToolUse `record()` sees no spurious diff for the resolved marks (and
    therefore does not run Fix #8 inference over them). Best-effort."""
    abs_path = os.path.abspath(path)
    cache_path = tc_audit.cache_path_for(abs_path)
    if not cache_path:
        return
    current_marks = tc_grammar.extract_marks(post_text, ftype)
    prior = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                prior = json.load(f)
        except (IOError, ValueError):
            prior = {}
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({'file': abs_path, 'marks': current_marks,
                       'imported_keys': prior.get('imported_keys', []),
                       'lineage_keys': prior.get('lineage_keys', [])}, f)
    except (IOError, OSError):
        pass


# ---------------------------------------------------------------------------
# CLI entry point. Invoked by lib/tc-cli.sh:
#   tc_resolve.py list       <file>
#   tc_resolve.py accept     <file> <ranges>
#   tc_resolve.py reject     <file> <ranges>
#   tc_resolve.py accept-all <file>
#   tc_resolve.py reject-all <file>
# ---------------------------------------------------------------------------

def _cmd_list(path):
    try:
        marks = list_marks(path)
    except (IOError, OSError):
        sys.stderr.write(f"tc: ERROR -- cannot read file: {path}\n")
        return 2
    except ValueError as e:
        sys.stderr.write(f"tc: ERROR -- {e}\n")
        return 2
    if not marks:
        print(f"tc: no marks in {path}")
        return 0
    print(f"tc: {len(marks)} mark(s) in {path}")
    for m in marks:
        print(f"  [{m['N']}] line {m['line']} ({m['type']}): {m['preview']}")
    return 0


def _regen_manifest(path):
    """v9.3.0 (Issue 2): best-effort manifest refresh. Returns True on success."""
    try:
        import tc_manifest
        return bool(tc_manifest.regenerate(path))
    except Exception:
        return False


def _regen_annotated(path):
    """v9.3.0 (Issue 2): best-effort annotated-PDF twin regen for a doc's sourced
    sources. Runs the bundled annotator as a subprocess so its heavier deps
    (PyMuPDF / headless render) and failure modes stay isolated — a failure is
    reported by the caller and never fails the accept. Returns (ok, message)."""
    tool = os.path.join(os.path.dirname(_HERE), 'tools', 'annotate_source_pdf.py')
    if not os.path.isfile(tool):
        return (False, 'annotator not found')
    try:
        env = dict(os.environ)
        env['PYTHONIOENCODING'] = 'utf-8'
        p = subprocess.run([sys.executable, tool, path],
                           capture_output=True, text=True, env=env, timeout=120)
        tail = (p.stdout or p.stderr or '').strip().splitlines()
        msg = tail[-1] if tail else ''
        return (p.returncode == 0, msg)
    except Exception as e:
        return (False, str(e))


def _post_accept_evidence(path):
    """v9.3.0 (Issue 2): after an accept that resolved >=1 sourced region,
    auto-(re)generate the human-facing evidence — the manifest and the annotated
    source twin(s). Best-effort and LOUD on failure; NEVER changes the accept's
    outcome. Emits notes to stdout."""
    if _regen_manifest(path):
        print("tc: refreshed source manifest (validation/)")
    ok, msg = _regen_annotated(path)
    if ok:
        print("tc: regenerated annotated source twin(s)"
              + (" -- %s" % msg if msg else ""))
    else:
        print("tc: note -- could not regenerate annotated source twin(s)"
              + (" (%s)" % msg if msg else "")
              + "; the accept succeeded. Run tools/annotate_source_pdf.py by hand "
                "if you need the highlighted PDF.")


def _cmd_resolve(path, decision, spec, all_marks=False):
    try:
        existing = list_marks(path)
    except (IOError, OSError):
        sys.stderr.write(f"tc: ERROR -- cannot read file: {path}\n")
        return 2
    except ValueError as e:
        sys.stderr.write(f"tc: ERROR -- {e}\n")
        return 2
    existing_ns = [m['N'] for m in existing]
    if all_marks:
        ns = existing_ns
    else:
        max_n = 0
        for n in existing_ns:
            try:
                max_n = max(max_n, int(n))
            except ValueError:
                pass
        try:
            wanted_ints = parse_ranges(spec, max_n)
        except ValueError as e:
            sys.stderr.write(f"tc: ERROR -- {e}\n")
            return 1
        wanted = set(str(i) for i in wanted_ints)
        ns = [n for n in existing_ns if n in wanted]
        # Numbers requested but with no matching mark are reported below.
        missing = sorted((str(i) for i in wanted_ints if str(i) not in set(existing_ns)),
                         key=_n_key)
        if missing:
            sys.stderr.write("tc: note -- no mark for: %s\n" % ', '.join(missing))
    if not ns:
        print(f"tc: no matching marks to {decision} in {path}")
        return 0
    try:
        res = resolve(path, decision, ns)
    except (IOError, OSError):
        sys.stderr.write(f"tc: ERROR -- cannot write file: {path}\n")
        return 2
    except ValueError as e:
        sys.stderr.write(f"tc: ERROR -- {e}\n")
        return 2
    verb = 'accepted' if decision == 'accept' else 'rejected'
    print("tc: %s mark(s) %s in %s: %s"
          % (len(res['resolved']), verb, path,
             ', '.join(res['resolved']) or '(none)'))
    if res['remaining']:
        print("tc: %d mark(s) remain: %s"
              % (len(res['remaining']), ', '.join(res['remaining'])))
    # v9.4.0 (Issue 2): a tc-join with no valid neighbour fell back to standalone.
    for n in res.get('join_fallbacks', []):
        print("tc: note -- region %s had tc-join but no adjacent body paragraph to "
              "merge into; left as a standalone block." % n)
    # v9.4.0 (Issue 1): advisory orphan-paragraph warning (never blocks).
    for w in res.get('orphan_warnings', []):
        print("tc: WARNING -- accepting region %s left a single-line paragraph "
              "between two paragraphs:" % w['N'])
        print("    \"%s\"" % _preview(w['text'], 72))
        print("    If it was carved from a paragraph, add tc-join=\"prev\" (or "
              "\"next\") to that region and re-accept to rejoin it.")
    # v9.3.0 (Issue 2): accept of a sourced region auto-(re)generates evidence.
    if decision == 'accept' and res.get('sourced_resolved'):
        _post_accept_evidence(path)
    return 0


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: tc_resolve.py "
                         "list|accept|reject|accept-all|reject-all <file> [ranges]\n")
        return 1
    sub = argv[0]
    path = argv[1]
    if sub == 'list':
        return _cmd_list(path)
    if sub == 'accept-all':
        return _cmd_resolve(path, 'accept', None, all_marks=True)
    if sub == 'reject-all':
        return _cmd_resolve(path, 'reject', None, all_marks=True)
    if sub in ('accept', 'reject'):
        if len(argv) < 3:
            sys.stderr.write(f"tc {sub}: missing <ranges> argument "
                             f"(e.g. 1-25,!7,!11)\n")
            return 1
        return _cmd_resolve(path, sub, argv[2])
    sys.stderr.write(f"tc_resolve.py: unknown subcommand: {sub}\n")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
