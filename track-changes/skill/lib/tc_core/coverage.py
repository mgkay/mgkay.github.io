"""tc_core.coverage — content-token coverage check for imports (8.2.0).

Mechanical guard against silently subsetting a source: the recurring
verified-import failure is *translating only part of a slide* (e.g. dropping
the `r_f` rate of four). Memory and directives did not stop it; comparing
CONTENT TOKENS does.

A "content token" is a word (>= 4 letters, minus a stoplist), a number
(>= 2 significant chars), or a subscripted identifier such as r_f / c_a / t_0
-- the things that carry meaning. Pure formatting (reordering, slide markup
vs markdown, LaTeX wrappers, fragment divs, image refs) is normalized away,
so REFORMATTING PASSES and only DROPPED CONTENT fails.

Presence is checked anywhere in the target (the concern is *dropping*
content, not placement). False positives (a legitimately reworded word) are
expected -- the output is a review list, and a real drop like `r_f` stands
out.

Lifted from ISE754-dev tools/coverage_check.py (bad6b52), tokenizer kept
verbatim. This module is DATA-ONLY: pure functions, no sys.exit, no argparse,
stdlib only -- callers map results to their own exit contracts (the
verified-import hook maps a non-empty missing list to its block exit 2; the
/tc coverage CLI wrapper maps it to exit 1).
"""
import re

_STOP = {
    # LaTeX / structural noise that survives normalization
    "text", "frac", "begin", "end", "aligned", "quad", "qquad", "left",
    "right", "cdot", "times", "mathbb", "mathrm", "operatorname", "sqrt",
    "label", "caption", "fragment", "index", "smaller", "scrollable",
    "width", "align", "center", "image", "true", "false", "matrix", "array",
    "boxed", "mtext", "lceil", "rceil", "lfloor", "rfloor",
    # math-environment names (the env name survives \begin{...} brace-stripping;
    # structural noise like matrix/array above — required for the charged
    # "equation environment -> $$...$$ passes" case)
    "equation", "gather", "multline",
    # common English function words
    "the", "and", "for", "with", "that", "this", "are", "was", "from", "can",
    "its", "each", "per", "not", "but", "where", "which", "into", "over",
    "than", "then", "have", "has", "will", "would", "your", "you", "they",
    "their", "them", "these", "those", "such", "about", "also", "only",
    "some", "more", "most", "when", "what", "how", "our", "use", "used",
    "using", "here", "there", "been", "being", "both", "all", "any", "one",
    "two", "due", "via", "etc",
}


def tokenize(text):
    """Return the set of content tokens in `text` (formatting normalized away)."""
    # keep the inner text of \text{...}/\rm{...}/\mathbb{...} wrappers
    text = re.sub(r"\\(?:text|rm|mathrm|mathbb|operatorname)\s*\{([^{}]*)\}",
                  r" \1 ", text)
    # drop image refs and image paths (not document content)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\bimages?/\S+", " ", text)
    # drop fenced-div / attribute blocks: {.class}, {#id}, and any {... = ...}
    # (e.g. {fig-align="center" width="80%"})
    text = re.sub(r"\{[.#][^}]*\}", " ", text)
    text = re.sub(r"\{[^{}]*=[^{}]*\}", " ", text)
    text = re.sub(r"^:::+.*$", " ", text, flags=re.M)
    # drop HTML entities (e.g. the &#x2003; em-space artifact from MTEF)
    text = re.sub(r"&#?\w+;", " ", text)
    # remaining LaTeX commands and delimiters -> space
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    text = re.sub(r"[\\{}$&|]", " ", text)
    low = text.lower()

    toks = set()
    # subscripted identifiers: r_e, r_f, c_a, t_0, m_min -> r_e, c_a, t_0, m_m
    for m in re.finditer(r"\b([a-z])\s*_\s*\{?\s*([a-z0-9]+)", low):
        toks.add("%s_%s" % (m.group(1), m.group(2)[0]))
    # words (>= 4 letters), minus stopwords
    for w in re.findall(r"[a-z]{4,}", low):
        if w not in _STOP:
            toks.add(w)
    # numbers (>= 2 significant chars), commas stripped
    for n in re.findall(r"\d[\d,]*\.?\d*", text):
        v = n.replace(",", "")
        if len(v.replace(".", "")) >= 2:
            toks.add(v)
    return toks


def missing_tokens(src_text, tgt_text):
    """Sorted list of source content tokens absent from the target text."""
    return sorted(tokenize(src_text) - tokenize(tgt_text))


def parse_units(text):
    """Split a staging file on `<!-- slide N -->` markers into {N: body}.

    Generic "unit" naming (a unit is whatever the marker numbers: a slide, a
    section, a chunk). The heading line immediately preceding a marker, if
    any, is prepended to that unit's body."""
    out = {}
    parts = re.split(r"<!--\s*slide\s+(\d+)\s*-->", text)
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1]
        prev = parts[i - 1].rstrip().splitlines()
        head = prev[-1] if prev and prev[-1].lstrip().startswith("#") else ""
        out[num] = head + "\n" + body
    return out


_RANGE_RE = re.compile(r"^L(\d+)-L(\d+)$")


def parse_range(rng_str):
    """Parse a pending-record range string to a fragment tuple.

    'L<a>-L<b>' -> (a, b); 'whole-file', empty, or anything unrecognized ->
    None (whole file). Mirrors vi_verify.stage_pending's serialization."""
    if not rng_str:
        return None
    m = _RANGE_RE.match(rng_str.strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)))


def read_slice(path, frag=None):
    """Read `path` (UTF-8) and return the fragment slice.

    frag is None (whole file) or a 1-indexed inclusive (a, b) line range.
    Line endings normalized to '\\n'; out-of-range bounds clamped; an
    inverted range yields ''. May raise OSError/UnicodeDecodeError -- the
    caller decides the failure contract (the hook fails closed)."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if frag is None:
        return text
    a, b = frag
    lines = text.split("\n")
    if a < 1:
        a = 1
    if b > len(lines):
        b = len(lines)
    if b < a:
        return ""
    return "\n".join(lines[a - 1:b])
