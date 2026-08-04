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


# ---------------------------------------------------------------------------
# Reverse direction (10.0.0, C4) — the `/tc edits resolve` support check.
#
# Spec of record: pcvplans/gate-b-c5-support-check.md. Read it before changing
# anything here; the obvious formulation is wrong in a way measurement caught.
#
# THE OBVIOUS FORMULATION, AND WHY IT FAILS. "Tokens in the region body that are
# absent from its gray excerpt" is what the charge, the plan, the first critic
# pass and the handoff note all described. Measured on the real fixture (region
# 27 of ISE754-dev 2-loc-2.qmd at b6eb907): the AI's CORRECTLY sourced body
# scores 14 unsupported tokens, 0.67 of its content tokens, against the bad
# rewrite's 31. Nothing separates them. The cause is structural rather than a
# tuning problem — a green region is a GLOSS, unverbatim by design, since
# verbatim reuse is what /tc import is for — so its legitimate vocabulary is
# mostly absent from its excerpt.
#
# WHAT WORKS. Scope to what the EDIT introduced, and compare against the excerpt
# UNION the text already standing in the region: 0 and 1 against 24 on the same
# fixture.
#
# The second union term is FALSE-POSITIVE SUPPRESSION, NOT VERIFICATION. An
# earlier draft justified it as "the prior body was gated at write time, so it
# is supported by construction". That is false in three code paths — the gate
# never compared body to excerpt, a body edit to an existing sourced region
# skips re-verification, and transcript regions are not in its trigger set at
# all. Admitting that vocabulary removes the glossing baseline; it asserts
# nothing about truth, and the recombination blind spot below is its direct
# consequence.
#
# DOCUMENTED BLIND SPOTS — this is a conservative flag, not a proof, and it
# ships that way with the instructor as backstop, exactly as 9.1.0's citation
# scanner did. All measured:
#   - recombination of existing vocabulary into a NEW claim  -> 0 (the largest)
#   - contradiction (a negation flip)                        -> 0
#   - deletion of the supported half                         -> 0
#   - quantifier swap (all -> most)                          -> 0
# The fixture's separation is driven by TOPIC DRIFT (retailer, trucks, fleet),
# not by claim validity. An in-topic rewrite that changes what the region
# asserts is the common case and is invisible here.
# ---------------------------------------------------------------------------

# `tokenize` drops numbers under two significant characters, tuned for the
# IMPORT direction where a dropped `r_f` is the failure and false positives are
# cheap. This direction runs the other way: on a quantitative lecture, `3` -> `8`
# is among the highest-consequence silent edits a reviewer could miss. So single
# digits count HERE ONLY. `missing_tokens` is untouched; TC-AI-9k asserts both.
_SINGLE_NUM_RE = re.compile(r"(?<![\w.])\d(?![\w.])")


def _tokens_with_single_digits(text):
    toks = tokenize(text)
    toks.update(_SINGLE_NUM_RE.findall(text))
    return toks


def unsupported_tokens(added_text, excerpt, prior_body, ftype='md',
                       strip_citations=None):
    """Content tokens the EDIT introduced with no basis in excerpt or prior body.

    DATA-ONLY, per this module's contract: a pure function returning a sorted
    list. The caller maps the result to behaviour — here, to a line in the
    `/tc edits resolve` report. Empty list means "nothing introduced that is
    unaccounted for", which is NOT the same as "true".

    `strip_citations` is injected rather than imported so this module keeps its
    stdlib-only, no-sibling-import contract; `tc_edits` passes `cite`'s. Applied
    to `added_text` ONLY — never to the comparand, whose citation vocabulary
    would otherwise silently join the supported set (a recorded residual).
    """
    if strip_citations is not None:
        added_text = strip_citations(added_text, ftype)
    known = (_tokens_with_single_digits(excerpt or '')
             | _tokens_with_single_digits(prior_body or ''))
    return sorted(_tokens_with_single_digits(added_text or '') - known)


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
