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
