r"""tc_core.cite — reader-facing citation detection for sourced regions (9.1.0).

The v9 source gate proves a gray excerpt is genuinely from its source. This
module supplies the other half the 9.1.0 tightening enforces: that the green
`sourced` interpretation which survives into the finished document carries a
citation a reader can follow. `tc-src` is invisible provenance metadata,
stripped when the region mark is accepted; it is NOT attribution.

Two predicates, both DATA-ONLY (no sys.exit / argparse; stdlib):

  has_citation(text, ftype)          -> bool   (Rule B: any citation/footnote)
  cites_key(text, ftype, citekey)    -> bool   (Rule A: cites THAT exact key)

Recognized forms:
  md / qmd : Pandoc `@key` / `[@key]` / `[-@key]` / `[@a; @b]`; Pandoc footnotes
             `^[...]` (inline) and `[^label]` (reference). Inline/fenced code is
             stripped first, so a `@key` inside a `` `code span` `` does NOT
             count (it renders as literal code, not a citation).
  tex      : the reader-facing \cite family (natbib + biblatex) and \footnote /
             \footfullcite. `\nocite` is deliberately EXCLUDED — it registers a
             key in the bibliography but renders nothing to a reader.

Citekey capture requires the key to END alphanumeric, so a trailing sentence
period (`[@daskin2013].`) does not break detection while `@daskin2013` stays
distinct from `@daskin2013b`.
"""
import re

# --- Markdown / Quarto -------------------------------------------------------
# A Pandoc citekey token. The lookbehind keeps an email local-part
# (`user@host`, `a.b@host`) and an escaped `\@` (literal at-sign, not a cite)
# from matching. The key starts alphanumeric and ENDS alphanumeric (single-char
# keys allowed), so trailing punctuation is excluded and `cites_key` can compare
# the whole captured key.
_MD_CITE = re.compile(r'(?<![\w@.\\])@([A-Za-z0-9](?:[\w:.\-]*[A-Za-z0-9])?)')
# Pandoc footnotes: inline `^[ ... ]` and reference marker `[^label]`.
_MD_FOOTNOTE = re.compile(r'\^\[[^\]]+\]|\[\^[^\]]+\]')

_MD_FENCED = re.compile(r'(?ms)^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[ \t]*$')
_MD_INLINE_CODE = re.compile(r'`+[^`]*`+')
_MD_COMMENT = re.compile(r'<!--.*?-->', re.DOTALL)
_MD_HTML_TAG = re.compile(r'<[^>]+>')                 # raw inline/block HTML tags
_MD_MATH = re.compile(r'\$\$.*?\$\$|\$[^$\n]*\$', re.DOTALL)  # display + inline math
_MD_LINK_DEST = re.compile(r'\]\([^)]*\)')            # ](url) link/image target


def _strip_code_md(text):
    """Remove every markdown context that renders NO reader-facing citation, so
    a citation-looking token hidden there does not count: fenced/inline code,
    HTML comments, raw HTML tags (and their attributes), math, and link/image
    destinations. (F4 + red-team rounds 1-2: comment/attribute/math/URL niches.)
    A citation renderer treats `@key` as a citation only in running prose, which
    is exactly what survives these strips."""
    text = _MD_COMMENT.sub(' ', text)
    text = _MD_FENCED.sub(' ', text)
    text = _MD_INLINE_CODE.sub(' ', text)
    text = _MD_MATH.sub(' ', text)
    text = _MD_HTML_TAG.sub(' ', text)
    text = _MD_LINK_DEST.sub('] ', text)
    return text


# --- LaTeX -------------------------------------------------------------------
# Reader-facing cite commands (natbib + biblatex), case-insensitive to cover the
# capitalized variants (\Citep, \Autocite, ...). Optional trailing `*` and up to
# two optional [prenote][postnote] args, then the mandatory {key,key,...}.
# `\nocite` is NOT here by design (renders nothing).
_TEX_CITE = re.compile(
    r'\\(?:cite|citep|citet|citeauthor|citeyear|citeyearpar|citealt|citealp'
    r'|citenum|citetitle|parencite|textcite|autocite|smartcite|supercite'
    r'|footcite|footfullcite|fullcite)\*?(?:\[[^\]]*\]){0,2}\s*\{([^}]*)\}',
    re.IGNORECASE)
# \footnote{...} / \footfullcite{...} count as a citation vehicle (Rule B only).
_TEX_FOOTNOTE = re.compile(r'\\(?:footnote|footfullcite)\s*(?:\[[^\]]*\])?\s*\{')

# Strippable non-rendering LaTeX: line comments, verbatim-like environments,
# \iffalse blocks, and inline \verb. A `\cite`/`\footnote` inside any of these
# renders nothing to a reader and must NOT count (red-team rounds 1-2).
#
# Comment stripping is backslash-PARITY-correct: a `%` is a real comment only
# when preceded by an EVEN run of backslashes (zero, `\\`, `\\\\`, ...); an odd
# run means the last `\` escapes the `%` (`\%` = literal percent). The kept
# group is the even run (e.g. a `\\` linebreak before an end-of-line comment).
_TEX_COMMENT = re.compile(r'(?m)(?<!\\)((?:\\\\)*)%[^\n]*')
_TEX_IFFALSE = re.compile(r'\\iffalse\b.*?\\fi\b', re.DOTALL)
# verbatim-family (any env name CONTAINING "verbatim", case-insensitive: covers
# Verbatim, BVerbatim/LVerbatim/SVerbatim, spverbatim, ...).
_TEX_VERBATIM_FAMILY = re.compile(
    r'\\begin\{([A-Za-z@]*[Vv]erbatim[A-Za-z@]*\*?)\}.*?\\end\{\1\}', re.DOTALL)
# other non-rendering / code envs by explicit name.
_TEX_CODE_ENV = re.compile(
    r'\\begin\{(lstlisting|minted|alltt|comment|filecontents)(\*?)\}.*?'
    r'\\end\{\1\2\}', re.DOTALL)
_TEX_VERB = re.compile(r'\\(?:verb|lstinline)\*?(.).*?\1')


def _strip_tex(text):
    """Remove every LaTeX context that renders NO reader-facing citation, so a
    citation token hidden there does not count: verbatim-family and code
    environments (fancyvrb, listings, minted, filecontents, comment), `\\iffalse`
    conditional blocks, backslash-parity-correct line comments, and inline
    `\\verb`/`\\lstinline`. A blocklist can never be proven exhaustive; this
    closes every evasion the adversarial red-team found and every realistic one,
    with human review of the gray/green pairing as the final backstop."""
    text = _TEX_VERBATIM_FAMILY.sub(' ', text)
    text = _TEX_CODE_ENV.sub(' ', text)
    text = _TEX_IFFALSE.sub(' ', text)
    text = _TEX_COMMENT.sub(r'\1', text)
    text = _TEX_VERB.sub(' ', text)
    return text


def _tex_cite_keys(text):
    """All citekeys named by any reader-facing \\cite-family command."""
    keys = []
    for m in _TEX_CITE.finditer(text):
        for k in m.group(1).split(','):
            k = k.strip()
            if k:
                keys.append(k)
    return keys


# --- Citation EXCISION (10.0.0, C4) -----------------------------------------
# Everything above answers "does a reader-facing citation exist here?" for the
# 9.1.0 gate. `strip_citations` answers a different question — "remove the
# citation apparatus so it does not pollute a token comparison" — and detection
# is not excision. The patterns above locate a construct's START; removing one
# needs its EXTENT, which for a nestable delimiter is not a regular language.
#
# This matters concretely: `_TEX_FOOTNOTE` matches only `\footnote{`, with no
# body group and no closing brace, so substituting it away would leave the whole
# footnote text behind — exactly the tokens the caller is trying to drop. And
# `_MD_FOOTNOTE`'s `[^\]]+` stops at the first `]`, so `^[See @k [p. 3].]` would
# be cut mid-construct, leaving `.]` as debris.

_MD_FOOTNOTE_DEF = re.compile(r'(?m)^[ ]{0,3}\[\^[^\]]+\]:')
_TEX_CITE_NAMES = re.compile(
    r'\\(?:cite|citep|citet|citeauthor|citeyear|citeyearpar|citealt|citealp'
    r'|citenum|citetitle|parencite|textcite|autocite|smartcite|supercite'
    # {0,2} matches _TEX_CITE: natbib takes [prenote][postnote], as in
    # \citep[cf.][p. 3]{key}. An earlier `?` here allowed only one and silently
    # left the whole two-arg form in the text.
    r'|footcite|footfullcite|fullcite|footnote)\*?(?:\[[^\]]*\]){0,2}\s*(?=\{)',
    re.IGNORECASE)


def _balanced_span(text, i, open_ch, close_ch):
    """Index just past the delimiter matching the one at `text[i]`, or None.

    Honours nesting and treats a backslash-escaped delimiter as literal. Returns
    None when the construct is UNTERMINATED, and callers must then leave it in
    place: truncating at the first close is the defect that makes the detection
    patterns unusable here, and repeating it would be the same bug in a new
    function. Leaving it errs toward over-flagging, which is the safe direction
    for a support check.
    """
    if i >= len(text) or text[i] != open_ch:
        return None
    depth = 0
    j = i
    while j < len(text):
        c = text[j]
        if c == '\\':
            j += 2
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return None


def _cut_all(text, finder):
    """Replace every span `finder(text, pos)` yields with a single space.

    A space, not '', so `word^[note]word` does not fuse into one token. Scans
    left to right and rebuilds, so spans never invalidate later offsets.
    """
    out = []
    pos = 0
    while pos < len(text):
        found = finder(text, pos)
        if found is None:
            break
        start, end = found
        out.append(text[pos:start])
        out.append(' ')
        pos = end
    out.append(text[pos:])
    return ''.join(out)


def _md_def_span(text, pos):
    """A `[^label]:` definition line plus its lazy continuation.

    Pandoc hoists the whole body, so the whole body must go — not just the
    label. Continuation is the following blank-or-indented lines, per Pandoc's
    footnote-body rule. FR-5 exists because regions in this corpus wrap footnote
    DEFINITIONS, and the marker-only pattern missed them entirely.
    """
    m = _MD_FOOTNOTE_DEF.search(text, pos)
    if not m:
        return None
    end = text.find('\n', m.end())
    if end == -1:
        return (m.start(), len(text))
    end += 1
    while end < len(text):
        nl = text.find('\n', end)
        line = text[end:] if nl == -1 else text[end:nl]
        if line.strip() == '' or line[:1] in (' ', '\t'):
            if nl == -1:
                return (m.start(), len(text))
            end = nl + 1
            continue
        break
    return (m.start(), end)


def _md_bracket_span(text, pos, opener):
    """The next `opener`-introduced bracket construct, balanced. `^[` or `[@`."""
    i = text.find(opener, pos)
    if i == -1:
        return None
    br = i + len(opener) - 1 if opener.startswith('^') else i
    end = _balanced_span(text, br, '[', ']')
    if end is None:
        return None            # unterminated: leave it, and stop scanning
    return (i, end)


def _tex_cmd_span(text, pos):
    """The next `\\cite`-family or `\\footnote` command, through its argument.

    The existing name alternation supplies the NAME; `_balanced_span` supplies
    the EXTENT. That division is the whole fix — `_TEX_CITE`'s `\\{([^}]*)\\}`
    key group breaks on any nested brace.
    """
    m = _TEX_CITE_NAMES.search(text, pos)
    if not m:
        return None
    end = _balanced_span(text, m.end(), '{', '}')
    if end is None:
        return None
    return (m.start(), end)


def strip_citations(text, ftype):
    """Remove citation and footnote apparatus, for TOKENIZING ONLY (10.0.0, C4).

    Never written back to a document — it may leave ragged whitespace. Each
    removal becomes a single space so adjacent words do not fuse.

    Why this is needed: citation apparatus is not source-grounded content, but
    it tokenizes like content. Measured — appending `[@ise754ch1]` to a clean
    body yields the spurious unsupported token `754`.

    NOT built on `_strip_code_md` / `_strip_tex`. Those remove contexts that
    render no citation, to answer the 9.1.0 question; here they would silently
    exempt a fenced code block's identifiers from the support check, which is
    the opposite of what a support check should do.
    """
    if not text:
        return text
    if ftype == 'tex':
        return _cut_all(text, _tex_cmd_span)
    out = _cut_all(text, _md_def_span)                       # definitions first
    out = _cut_all(out, lambda t, p: _md_bracket_span(t, p, '^['))
    out = _cut_all(out, lambda t, p: _md_bracket_span(t, p, '[@'))
    out = _MD_CITE.sub(' ', out)                             # bare @key
    out = _MD_FOOTNOTE.sub(' ', out)                         # surviving [^label]
    return out


def has_citation(text, ftype):
    """True if `text` contains any reader-facing citation or footnote (Rule B)."""
    if not text:
        return False
    if ftype == 'tex':
        s = _strip_tex(text)
        return bool(_TEX_CITE.search(s) or _TEX_FOOTNOTE.search(s))
    # md / qmd
    stripped = _strip_code_md(text)
    return bool(_MD_CITE.search(stripped) or _MD_FOOTNOTE.search(stripped))


def cites_key(text, ftype, citekey):
    """True if `text` cites THAT exact `citekey` (Rule A).

    `citekey` is the bare key (no leading `@`); a leading `@` is tolerated."""
    if not text or not citekey:
        return False
    key = citekey[1:] if citekey.startswith('@') else citekey
    key = key.strip()
    if not key:
        return False
    if ftype == 'tex':
        return key in _tex_cite_keys(_strip_tex(text))
    stripped = _strip_code_md(text)
    return any(m.group(1) == key for m in _MD_CITE.finditer(stripped))
