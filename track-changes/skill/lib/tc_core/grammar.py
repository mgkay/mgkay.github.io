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

Consolidated so the two skills share one grammar.
"""
import re

DEFAULT_PROV = 'authored'
PROV_VALUES = ('authored', 'imported')

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
TEX_REGION_OPEN_RE = re.compile(
    r'\\begin\{tcregion\}\{(?P<n>\d+)\}(?:\[(?P<prov>\w+)\])?')
TEX_REGION_CLOSE_RE = re.compile(r'\\end\{tcregion\}')
# Region number scanners (for uniqueness / max-N).
MD_REGION_NUMS_RE = re.compile(
    r'^\s*:{3,}\s*\{[^}]*\.tc-region[^}]*tc-n\s*=\s*"(\d+)"[^}]*\}\s*$', re.M)
TEX_REGION_NUMS_RE = re.compile(r'\\begin\{tcregion\}\{(\d+)\}')


def prov_from_attrs(attrs):
    """Provenance from an md attribute string (tag attrs or div attr block).
    Absent / unrecognized ⇒ DEFAULT_PROV ('authored')."""
    if not attrs:
        return DEFAULT_PROV
    m = _PROV_ATTR_RE.search(attrs)
    if m and m.group(1) in PROV_VALUES:
        return m.group(1)
    return DEFAULT_PROV


def norm_prov(value):
    """Normalize a provenance token (e.g. a LaTeX optional arg). None/unknown ⇒
    'authored'."""
    return value if value in PROV_VALUES else DEFAULT_PROV


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
    """Return list of region dicts {N(str), prov, start(1-indexed opener line),
    end(1-indexed closer line)} for whole-region insertions (D).

    md/qmd: depth-tracked `:::` fenced divs; only those whose attr block carries
    `.tc-region` are emitted (nested non-region divs are skipped but counted for
    depth). tex: \\begin{tcregion}{N}[prov] … \\end{tcregion} (non-nesting).
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
