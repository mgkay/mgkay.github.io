"""tc_core.grammar — mark grammar (single source of truth).

Parse / classify / extract / number the change-mark wrappers:
  - Markdown / Quarto:  <mark>BODY</mark><sup>N</sup>
  - LaTeX:              \\tc{BODY}\\tcn{N}

where BODY is one of:
  insertion    NEW
  deletion     <s>OLD</s>          (md)   \\sout{OLD}          (tex)
  replacement  <s>OLD</s>NEW       (md)   \\sout{OLD}NEW       (tex)

Pre-Fix-#7 markdown deletions/replacements used `~~OLD~~`; still accepted.

v6 additions (back-compatible):
  - Provenance type on a mark (E): md `<mark tc-prov="imported">…`; tex
    `\\tc[imported]{…}`. Absent ⇒ 'authored' (so every v1–v5 mark/document
    parses unchanged). The mark/sibling regexes are now attribute-tolerant.
  - Whole-region insertion (D): a multi-block new region carried as ONE
    numbered insertion.
      md/qmd:  ::: {.tc-region tc-n="N" tc-prov="authored"} … :::
      tex:     \\begin{tcregion}{N}[authored] … \\end{tcregion}
    Region numbers share the file's single mark-number space (uniqueness is
    enforced across inline marks AND regions).

v9 additions (back-compatible):
  - Fourth provenance value 'sourced' (F9): a green region whose text is
    supported by a named document source. Carries a source locator:
      md/qmd:  ::: {.tc-region tc-n="N" tc-prov="sourced" tc-src="…"} … :::
      tex:     \\begin{tcregion}{N}[sourced][<src-locator>] … \\end{tcregion}
    The tex region opener gains an OPTIONAL SECOND bracket group for the src
    locator; absent ⇒ src None (so every v6/v7 region parses unchanged). md
    regions expose the `tc-src` attribute via a new 'src' key (None when
    absent). `src_from_attrs` reads it.
  - Verbatim scaffolding (Dilemma A/D): a transient gray block holding the
    supporting excerpt beside its green sourced region.
      md/qmd:  ::: {.tc-verbatim tc-cite="…"} … :::
      tex:     \\begin{tcverbatim}{<citation>} … \\end{tcverbatim}
    Recognized by extract_verbatim_blocks / verbatim_covered_lines; it carries
    NO mark number and is deliberately kept OUT of region numbering/uniqueness
    (extract_regions must not emit it).

Consolidated so the two skills share one grammar.
"""
import re

DEFAULT_PROV = 'authored'
# 'transcript' (v7): a region reworded from the instructor's class-recording
# transcript — AI wording over the instructor's own spoken content, distinct
# from 'authored' (AI-invented) and 'imported' (verbatim from a named source).
# 'sourced' (v9): AI wording supported by a named document source, carrying a
# tc-src locator and a verified verbatim excerpt (the gray scaffolding block).
PROV_VALUES = ('authored', 'imported', 'transcript', 'sourced')

# --- Inline wrapper detection (attribute-tolerant; back-compatible) ----------
# The optional `(?:\s+[^>]*?)?` matches v6 attributes (e.g. tc-prov="…") while
# still matching a bare v5 `<mark>`. Named groups so callers read attrs/body/N.
MD_MARK_RE = re.compile(
    r'<mark(?P<attrs>\s+[^>]*?)?>(?P<body>.*?)</mark><sup>(?P<n>\d+)</sup>',
    re.DOTALL,
)
# LaTeX inline head: \tc{ or \tc[prov]{  (never matches \tcn{ — 'n' is not '['/'{').
TEX_HEAD_RE = re.compile(r'\\tc(?:\[(?P<prov>\w+)\])?\{')
TEX_TCN_AFTER_RE = re.compile(r'\\tcn\{(\d+)\}')

# Provenance attribute inside an md tag / div attribute block.
_PROV_ATTR_RE = re.compile(r'tc-prov\s*=\s*"([^"]*)"')
# Source-locator attribute (v9) inside a `.tc-region` div attribute block.
TC_SRC_ATTR_RE = re.compile(r'tc-src\s*=\s*"([^"]*)"')
# Paragraph-join directive (9.4.0): a region carved from inside a paragraph may
# declare that it should rejoin an adjacent paragraph on `/tc accept` instead of
# remaining a standalone block. Values: prev | next (anything else ⇒ None).
JOIN_VALUES = ('prev', 'next')
_JOIN_ATTR_RE = re.compile(r'tc-join\s*=\s*"([^"]*)"')

# Body classification.
_MD_S_REP_RE = re.compile(r'^<s>(.*?)</s>(.+)$', re.DOTALL)
_MD_S_DEL_RE = re.compile(r'^<s>(.*?)</s>\s*$', re.DOTALL)
_MD_TILDE_REP_RE = re.compile(r'^~~(.*?)~~(.+)$', re.DOTALL)
_MD_TILDE_DEL_RE = re.compile(r'^~~(.*?)~~\s*$', re.DOTALL)
_TEX_SOUT_REP_RE = re.compile(r'^\\sout\{(.*?)\}(.+)$', re.DOTALL)
_TEX_SOUT_DEL_RE = re.compile(r'^\\sout\{(.*?)\}\s*$', re.DOTALL)

# Inline number-only scanners (numbering uniqueness). Closing-tag based, so a
# leading attribute on the opening <mark …> does not affect these.
MD_NUMS_RE = re.compile(r'</mark><sup>(\d+)</sup>')
TEX_NUMS_RE = re.compile(r'\\tcn\{(\d+)\}')

# --- Region grammar (D) ------------------------------------------------------
# md/qmd: a Quarto fenced div carrying .tc-region with tc-n / tc-prov.
#   ::: {.tc-region tc-n="3" tc-prov="authored"}
# Opener = a `:::`-fence line whose attribute block mentions .tc-region.
# Recognize BOTH standard Quarto fenced-div opener forms so depth-tracking stays
# balanced: a brace block `{…}` OR a bare class identifier (the brace-less
# shorthand `::: statement`, `::: result-box`). A bare `:::` closer never matches
# the opener (it requires a brace/identifier after the colons), so open and close
# stay unambiguous. Non-region openers push None (skipped but depth-counted); the
# downstream `.search()` calls tolerate the braces captured by the brace branch.
_MD_FENCE_OPEN_RE = re.compile(
    r'^\s*(:{3,})\s*(?P<attrs>\{[^}]*\}|[A-Za-z][\w-]*)\s*$')
_MD_FENCE_CLOSE_RE = re.compile(r'^\s*(:{3,})\s*$')
_MD_REGION_CLASS_RE = re.compile(r'(?<![\w.-])\.tc-region(?![\w-])')
_MD_REGION_N_RE = re.compile(r'tc-n\s*=\s*"(\d+)"')
# tex: \begin{tcregion}{N}[prov] … \end{tcregion}
# v9: an OPTIONAL SECOND bracket group carries the src locator —
#   \begin{tcregion}{N}[prov][src]  (src may contain any char except ']').
# Both optional groups are independent, so the v6/v7 forms {N} and {N}[prov]
# match exactly as before (src stays None).
# 9.4.0: an OPTIONAL THIRD bracket group carries the paragraph-join directive —
#   \begin{tcregion}{N}[prov][src][join]  (join in {prev, next}).
# All three optionals are independent, so {N}, {N}[prov], {N}[prov][src] match
# exactly as before (join stays None).
TEX_REGION_OPEN_RE = re.compile(
    r'\\begin\{tcregion\}\{(?P<n>\d+)\}'
    r'(?:\[(?P<prov>\w+)\])?(?:\[(?P<src>[^\]]*)\])?(?:\[(?P<join>[^\]]*)\])?')
TEX_REGION_CLOSE_RE = re.compile(r'\\end\{tcregion\}')
# Region number scanners (for uniqueness / max-N).
MD_REGION_NUMS_RE = re.compile(
    r'^\s*:{3,}\s*\{[^}]*\.tc-region[^}]*tc-n\s*=\s*"(\d+)"[^}]*\}\s*$', re.M)
TEX_REGION_NUMS_RE = re.compile(r'\\begin\{tcregion\}\{(\d+)\}')

# --- Verbatim scaffolding grammar (v9) ---------------------------------------
# A transient gray block holding the supporting excerpt beside a sourced region.
# It carries NO mark number and is NOT part of region numbering/uniqueness.
# md/qmd: a `:::`-fenced div whose attr block carries `.tc-verbatim`, with an
# optional `tc-cite="…"` citation attribute. Recognized with the same
# depth-tracked fence walk as `.tc-region` so nested divs stay balanced.
_MD_VERBATIM_CLASS_RE = re.compile(r'(?<![\w.-])\.tc-verbatim(?![\w-])')
_MD_CITE_ATTR_RE = re.compile(r'tc-cite\s*=\s*"([^"]*)"')
# tex: \begin{tcverbatim}{<citation>} … \end{tcverbatim} — the citation is a
# brace-balanced single group; the environment is non-nesting (like tcregion).
TEX_VERBATIM_OPEN_RE = re.compile(r'\\begin\{tcverbatim\}\{')
TEX_VERBATIM_CLOSE_RE = re.compile(r'\\end\{tcverbatim\}')


def prov_from_attrs(attrs):
    """Provenance from an md attribute string (tag attrs or div attr block).
    Absent / unrecognized ⇒ DEFAULT_PROV ('authored')."""
    if not attrs:
        return DEFAULT_PROV
    m = _PROV_ATTR_RE.search(attrs)
    if m and m.group(1) in PROV_VALUES:
        return m.group(1)
    return DEFAULT_PROV


def src_from_attrs(attrs):
    """Source locator from an md `.tc-region` attribute block (the `tc-src`
    attribute). Returns the raw string, or None when the attribute is absent."""
    if not attrs:
        return None
    m = TC_SRC_ATTR_RE.search(attrs)
    return m.group(1) if m else None


def norm_prov(value):
    """Normalize a provenance token (e.g. a LaTeX optional arg). None/unknown ⇒
    'authored'."""
    return value if value in PROV_VALUES else DEFAULT_PROV


def norm_join(value):
    """Normalize a paragraph-join token (md attr value or LaTeX optional arg).
    None/empty/unknown ⇒ None (no join; standalone block on accept)."""
    v = (value or '').strip()
    return v if v in JOIN_VALUES else None


def join_from_attrs(attrs):
    """Paragraph-join directive from an md `.tc-region` attribute block
    (`tc-join="prev"|"next"`). Returns 'prev'|'next', or None when absent/other."""
    if not attrs:
        return None
    m = _JOIN_ATTR_RE.search(attrs)
    return norm_join(m.group(1)) if m else None


def classify_md(body):
    m = _MD_S_REP_RE.match(body)
    if m:
        return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    m = _MD_S_DEL_RE.match(body)
    if m:
        return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    m = _MD_TILDE_REP_RE.match(body)
    if m:
        return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    m = _MD_TILDE_DEL_RE.match(body)
    if m:
        return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    return {'type': 'insertion', 'old': '', 'new': body}


def classify_tex(body):
    m = _TEX_SOUT_REP_RE.match(body)
    if m:
        return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    m = _TEX_SOUT_DEL_RE.match(body)
    if m:
        return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    return {'type': 'insertion', 'old': '', 'new': body}


def extract_marks(text, ftype):
    """Return list of dicts {N(str), type, line(1-indexed), old, new, prov}.

    Back-compatible with v2 tc_audit._extract_marks for existing inputs; the
    only added key is 'prov' (default 'authored'), and the regexes still match
    bare v5 marks. Inline marks only — regions are extract_regions().
    """
    marks = []
    if ftype in ('md', 'qmd'):
        for m in MD_MARK_RE.finditer(text):
            body = m.group('body')
            n = m.group('n')
            line_no = 1 + text.count('\n', 0, m.start())
            entry = classify_md(body)
            entry['N'] = n
            entry['line'] = line_no
            entry['prov'] = prov_from_attrs(m.group('attrs'))
            marks.append(entry)
    elif ftype == 'tex':
        pos = 0
        L = len(text)
        while pos < L:
            mh = TEX_HEAD_RE.search(text, pos)
            if not mh:
                break
            prov = norm_prov(mh.group('prov'))
            body_start = mh.end()
            depth = 1
            i = body_start
            while i < L and depth > 0:
                c = text[i]
                if c == '\\' and i + 1 < L:
                    i += 2
                    continue
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            if depth != 0:
                pos = mh.end()
                continue
            body = text[body_start:i]
            tail = text[i + 1:i + 1 + 30]
            tm = TEX_TCN_AFTER_RE.match(tail)
            if not tm:
                pos = i + 1
                continue
            n = tm.group(1)
            line_no = 1 + text.count('\n', 0, mh.start())
            entry = classify_tex(body)
            entry['N'] = n
            entry['line'] = line_no
            entry['prov'] = prov
            marks.append(entry)
            pos = i + 1 + len(tm.group(0))
    return marks


def extract_regions(text, ftype):
    """Return list of region dicts {N(str), prov, src, join, start(1-indexed
    opener line), end(1-indexed closer line)} for whole-region insertions (D).

    'src' (v9) is the source locator (None when absent); 'join' (9.4.0) is the
    paragraph-join directive 'prev'|'next'|None. md/qmd: depth-tracked
    `:::` fenced divs; only those whose attr block carries `.tc-region` are
    emitted (nested non-region divs are skipped but counted for depth). tex:
    \\begin{tcregion}{N}[prov][src] … \\end{tcregion} (non-nesting).
    """
    regions = []
    if ftype in ('md', 'qmd'):
        lines = text.split('\n')
        # Stack of open fenced divs: each entry is the region dict or None.
        stack = []
        for idx, line in enumerate(lines, start=1):
            mo = _MD_FENCE_OPEN_RE.match(line)
            if mo:
                attrs = mo.group('attrs')
                if _MD_REGION_CLASS_RE.search(attrs):
                    mn = _MD_REGION_N_RE.search(attrs)
                    stack.append({
                        'N': mn.group(1) if mn else None,
                        'prov': prov_from_attrs(attrs),
                        'src': src_from_attrs(attrs),
                        'join': join_from_attrs(attrs),
                        'start': idx,
                        'end': None,
                    })
                else:
                    stack.append(None)
                continue
            if _MD_FENCE_CLOSE_RE.match(line) and stack:
                top = stack.pop()
                if top is not None and top['N'] is not None:
                    top['end'] = idx
                    regions.append(top)
    elif ftype == 'tex':
        for mo in TEX_REGION_OPEN_RE.finditer(text):
            start_line = 1 + text.count('\n', 0, mo.start())
            mc = TEX_REGION_CLOSE_RE.search(text, mo.end())
            end_line = (1 + text.count('\n', 0, mc.start())) if mc else None
            regions.append({
                'N': mo.group('n'),
                'prov': norm_prov(mo.group('prov')),
                'src': mo.group('src'),
                'join': norm_join(mo.group('join')),
                'start': start_line,
                'end': end_line,
            })
    return regions


def region_covered_lines(text, ftype):
    """Set of 1-indexed line numbers enclosed by a well-formed region
    (delimiters inclusive). Lines inside a region are 'covered' for analyzer
    purposes — the region is one atomic tracked insertion."""
    covered = set()
    for r in extract_regions(text, ftype):
        if r['start'] and r['end']:
            covered.update(range(r['start'], r['end'] + 1))
    return covered


def extract_verbatim_blocks(text, ftype):
    """Return list of verbatim-scaffolding dicts (v9), sorted by opener line:
      {'start': int (1-indexed opener/delimiter line),
       'end':   int|None (1-indexed closer line; None when unclosed at EOF),
       'body':  str (text strictly between the delimiter lines),
       'citation': str|None}

    md/qmd: depth-tracked `:::` fenced divs whose attr block carries
    `.tc-verbatim` (citation from the optional `tc-cite="…"` attribute; nested
    non-verbatim divs are skipped but counted for depth). tex:
    \\begin{tcverbatim}{<citation>} … \\end{tcverbatim} (brace-balanced citation,
    non-nesting). These blocks carry NO mark number and are never region marks.
    """
    blocks = []
    if ftype in ('md', 'qmd'):
        lines = text.split('\n')
        # Stack of open fenced divs: each entry is a verbatim dict or None.
        stack = []
        for idx, line in enumerate(lines, start=1):
            mo = _MD_FENCE_OPEN_RE.match(line)
            if mo:
                attrs = mo.group('attrs')
                if _MD_VERBATIM_CLASS_RE.search(attrs):
                    mc = _MD_CITE_ATTR_RE.search(attrs)
                    stack.append({
                        'start': idx,
                        'citation': mc.group(1) if mc else None,
                    })
                else:
                    stack.append(None)
                continue
            if _MD_FENCE_CLOSE_RE.match(line) and stack:
                top = stack.pop()
                if top is not None:
                    top['end'] = idx
                    top['body'] = '\n'.join(lines[top['start']:idx - 1])
                    blocks.append(top)
        # Any verbatim divs still open at EOF are emitted unclosed (end=None).
        for top in stack:
            if top is not None:
                top['end'] = None
                top['body'] = '\n'.join(lines[top['start']:])
                blocks.append(top)
    elif ftype == 'tex':
        lines = text.split('\n')
        L = len(text)
        pos = 0
        while pos < L:
            mh = TEX_VERBATIM_OPEN_RE.search(text, pos)
            if not mh:
                break
            # Brace-balance the citation group (respecting backslash escapes).
            i = mh.end()
            depth = 1
            while i < L and depth > 0:
                c = text[i]
                if c == '\\' and i + 1 < L:
                    i += 2
                    continue
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            if depth != 0:
                pos = mh.end()
                continue
            citation = text[mh.end():i]
            start_line = 1 + text.count('\n', 0, mh.start())
            mc = TEX_VERBATIM_CLOSE_RE.search(text, i + 1)
            if mc:
                end_line = 1 + text.count('\n', 0, mc.start())
                body = '\n'.join(lines[start_line:end_line - 1])
                pos = mc.end()
            else:
                end_line = None
                body = '\n'.join(lines[start_line:])
                pos = i + 1
            blocks.append({
                'start': start_line,
                'end': end_line,
                'body': body,
                'citation': citation,
            })
    blocks.sort(key=lambda b: b['start'])
    return blocks


def verbatim_covered_lines(text, ftype):
    """Set of 1-indexed line numbers enclosed by a well-formed (closed)
    verbatim block, delimiters inclusive. Unclosed blocks (end None) contribute
    nothing."""
    covered = set()
    for b in extract_verbatim_blocks(text, ftype):
        if b['start'] and b['end']:
            covered.update(range(b['start'], b['end'] + 1))
    return covered


def scan_max_n(text, ftype):
    """Largest existing mark number in `text` across BOTH inline marks and
    regions (0 if none). Use max()+1 for the next mark; the gate enforces
    uniqueness, not contiguity."""
    if ftype == 'tex':
        inline = TEX_NUMS_RE.findall(text)
        region = TEX_REGION_NUMS_RE.findall(text)
    else:
        inline = MD_NUMS_RE.findall(text)
        region = MD_REGION_NUMS_RE.findall(text)
    nums = [int(n) for n in inline] + [int(n) for n in region]
    return max(nums) if nums else 0
