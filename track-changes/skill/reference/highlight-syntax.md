# Highlight Syntax Reference (v2)

Lookup reference for the `track-changes` skill. Use this document when
you need to confirm exact syntax for a specific change type, language,
or non-rendering construct. The full protocol lives in `SKILL.md`; this
file supplements §3 (markdown), §4 (LaTeX), and §6 (non-rendering
contexts).

The v2 encoding is **token-minimal**: each highlight wraps only the
characters that differ from the on-disk source, followed immediately by
a `<sup>N</sup>` (markdown) or `\tcn{N}` (LaTeX) reference number that
sits *outside* the mark.

## Three change types × two languages

### Markdown — Insertion

**Source markup:**

```markdown
The polynomial $p(x)$ has degree $n$ <mark>and exactly $n$ roots in $\mathbb{C}$ counted with multiplicity</mark><sup>1</sup>.
```

**Rendered output (HTML / Quarto / GitHub / VS Code preview):**
A yellow highlight wraps only the inserted text "and exactly $n$ roots
in $\mathbb{C}$ counted with multiplicity"; the surrounding prose
renders normally without highlight. The superscript `1` appears
immediately after the closing `</mark>`, outside the yellow region.

### Markdown — Replacement

**Source markup:**

```markdown
The bound holds for <mark><s>all $n$</s>all positive integers $n$</mark><sup>2</sup>.
```

**Rendered output:**
A yellow highlight wraps the strikethrough `all $n$` immediately
followed by the new text `all positive integers $n$`. Both old and new
are inside the yellow region; the strikethrough delineates them. The
superscript `2` sits outside the mark.

### Markdown — Deletion

**Source markup:**

```markdown
We will revisit this construction<mark><s> in Chapter 4</s></mark><sup>3</sup>.
```

**Rendered output:**
A yellow highlight wraps the struck-through text ` in Chapter 4`
(including the leading space that is also being removed). The
superscript `3` sits outside the mark.

**Note on the strikethrough encoding.** Markdown's `~~old~~` syntax
fails to render in markdown-it-based viewers (VS Code preview, common
Chrome markdown extensions) when the wrapped text starts or ends with
whitespace. HTML `<s>` has no such restriction. The skill uses `<s>` as
its standard encoding (Fix #7); files with legacy `~~` marks still
validate and classify correctly for backward compatibility.

### LaTeX — Insertion

**Source markup:**

```latex
The polynomial $p(x)$ has degree $n$ \tc{and exactly $n$ roots in $\mathbb{C}$ counted with multiplicity}\tcn{1}.
```

**Rendered output (compiled PDF):**
A yellow background highlight surrounds only the inserted text; the
math content inside the highlight typesets normally. The `\tcn{1}`
renders as a small superscript `1` immediately after the highlight.

### LaTeX — Replacement

**Source markup:**

```latex
The bound holds for \tc{\sout{all $n$}all positive integers $n$}\tcn{2}.
```

**Rendered output:**
A yellow highlight wraps `\sout{all $n$}` (which renders as `all $n$`
with a horizontal strikethrough) immediately followed by the new
content. The `\tcn{2}` sits outside as a superscript reference.

### LaTeX — Deletion

**Source markup:**

```latex
We will revisit this construction\tc{\sout{ in Chapter 4}}\tcn{3}.
```

**Rendered output:**
A yellow highlight wraps `\sout{ in Chapter 4}` which renders as the
text ` in Chapter 4` with a horizontal strikethrough.

## Token-minimality — worked contrast

The v1 encoding (deprecated) wrapped whole phrases including unchanged
characters. v2 wraps only the changed chars.

**v1 (deprecated):**

```markdown
<mark>[4] ~~Every continuous function~~ → Every monotone continuous function</mark> on a compact set attains its maximum.
```

**v2 (current):**

```markdown
Every <mark><s>continuous</s>monotone</mark><sup>4</sup> function on a compact set attains its maximum.
```

Only the changed word "continuous" → "monotone" is wrapped. The rest of
the sentence stays bare. Run `bash install.sh --migrate <dir>` to
convert v1 marks to v2 in place.

## Resolution (accept / reject) — Fix #8

When a tracked file has been reviewed and the human directs the AI to
accept or reject specific marks, the AI removes the mark wrappers in
place, keeping either the new chars (accept) or the old chars (reject).
The PreToolUse hook recognises the result as a *resolution* and allows
the edit even though the resulting line carries no mark.

### Accept an insertion

**Before:**

```markdown
Every <mark>uniformly </mark><sup>3</sup>continuous function on a compact set attains its maximum.
```

**After accept:**

```markdown
Every uniformly continuous function on a compact set attains its maximum.
```

The mark's `new` text (`uniformly `) survives in the proposed file.
Audit log records mark 3 as `resolved`, `decision: accepted`.

### Reject an insertion

**Before:** same as above.

**After reject:**

```markdown
Every continuous function on a compact set attains its maximum.
```

The mark's `new` text is gone; the mark wrapper is gone. Audit log
records `decision: rejected`.

### Accept a replacement

**Before:**

```markdown
Every <mark><s>continuous</s>monotone</mark><sup>4</sup> function on a compact set attains its maximum.
```

**After accept:**

```markdown
Every monotone function on a compact set attains its maximum.
```

The mark's `new` text (`monotone`) survives. Strikethrough content
(`continuous`) is dropped.

### Reject a replacement

**Before:** same.

**After reject:**

```markdown
Every continuous function on a compact set attains its maximum.
```

The original `continuous` is restored; the mark wrapper is gone.

### Accept a deletion

**Before:**

```markdown
We will revisit this construction<mark><s> in Chapter 4</s></mark><sup>3</sup>.
```

**After accept:**

```markdown
We will revisit this construction.
```

The struck text and the mark wrapper are both removed.

### Mixed accept/reject across multiple marks

A single edit can resolve several marks at once. The walk-based check
verifies each resolved mark independently. Example: source has marks
#1, #2, #3 on one line; the user says "accept #1 and #3, reject #2."
The resulting line has zero marks and is accepted by the hook.

### Resolution mixed with a new edit

A single edit can resolve existing marks AND introduce new ones (e.g.,
acceptance followed by a fresh AI suggestion). The walk treats
introduced marks as new content that must be wrapped, and treats
resolutions as accept-or-reject of existing marks — both can co-occur
in the same edit.

## Sibling-element form (non-rendering contexts)

The sibling-element rule applies when a change falls inside a
non-rendering construct (see SKILL.md §6 for the enumerated list). Each
individual change inside the block gets its own sibling line above the
block opener, encoded the same way as an inline mark.

> **Important — no blank line.** The sibling marks must sit on the
> lines *immediately* above the construct's opener — no blank line
> between the last sibling and the opener. The PreToolUse hook looks at
> exactly the prior lines; inserting an empty line breaks the
> association and the hook reports a missing-sibling violation.

### Markdown sibling — fenced code block (single change)

```markdown
<mark><s>0</s>1</mark><sup>4</sup>
` ``python
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
` ``
```

The sibling renders as a yellow note above the code block; the code
block renders as a normal monospace listing below. The sibling encodes
the change (base case `0` → `1`) using the same v2 form as an inline
mark.

### Markdown sibling — fenced code block (multiple changes)

```markdown
<mark><s>import sys</s>import os</mark><sup>7</sup>
<mark>def foo(): pass</mark><sup>8</sup>
` ``python
import os
print("hi")
def foo(): pass
` ``
```

Each change inside the block gets its own sibling line, stacked
immediately above the block opener with no blank lines.

### Markdown sibling — display math

```markdown
<mark><s>\le</s>&lt;</mark><sup>5</sup>
$$
|f(x) - f(y)| < L \cdot |x - y|
$$
```

### Markdown sibling — YAML front matter

```markdown
<mark><s>2026-05-22</s>2026-06-01</mark><sup>6</sup>
---
title: "Stability of Numerical Methods"
author: "Kay, Michael G."
date: "2026-06-01"
---
```

### Markdown sibling — GFM pipe table

```markdown
<mark><s>5</s>7</mark><sup>7</sup>
| Line | Slope | Intercept |
|------|-------|-----------|
| $\ell_1$ | 2 | 0 |
| $\ell_2$ | -1 | 3 |
| $\ell_3$ | 0 | 7 |
```

### LaTeX sibling — verbatim

```latex
\tc{\sout{tabs}spaces}\tcn{8}
\begin{verbatim}
def harmonic_mean(xs):
    if not xs:
        return 0
    return len(xs) / sum(1/x for x in xs)
\end{verbatim}
```

### LaTeX sibling — equation

```latex
\tc{added zero-case}\tcn{10}
\begin{equation}
  H(x_1, \ldots, x_n) = \begin{cases}
    0 & \text{if } x_i = 0 \text{ for some } i,\\
    \frac{n}{\sum_{i=1}^n 1/x_i} & \text{otherwise.}
  \end{cases}
\end{equation}
```

When a single sibling describes a structural change too large for
strict token-minimality (a new `\begin{cases}` block), the sibling
content is a short prose hint of what changed.

### LaTeX sibling — tabular

```latex
\tc{added cubic row}\tcn{12}
\begin{tabular}{|c|c|c|}
\hline
Order & Method & Error \\
\hline
1 & Euler & $O(h)$ \\
2 & Heun & $O(h^2)$ \\
3 & RK3 & $O(h^3)$ \\
\hline
\end{tabular}
```

## `soul`-package fallback

When `soul` conflicts with `hyperref`, `fontspec`, or another highlight
package, substitute `xcolor`-backed definitions. The protocol's
source-side syntax is unchanged; only the preamble definition differs.

### Fallback preamble

```latex
\usepackage{xcolor,ulem}
\newcommand{\tc}[1]{\colorbox{yellow}{#1}}
\newcommand{\tcn}[1]{\textsuperscript{#1}}
% \sout already provided by ulem
```

The PreToolUse hook does not distinguish `\hl`-backed from
`\colorbox`-backed definitions; both register as valid `\tc{...}`
wrappers.

## Lineage workaround for cross-file paste

When pasting content from a source file into a destination file,
inherited marks renumber on collision (SKILL.md §5). Cross-file
lineage is not preserved automatically. The optional workaround is a
leading comment recording the mapping.

### Markdown

```markdown
<!-- pasted from lecture-01.md: marks 3→8, 5→9 -->
<mark>foo</mark><sup>8</sup>
... rest of pasted region ...
<mark>bar</mark><sup>9</sup>
```

### LaTeX

```latex
% pasted from notes-ch3.tex: marks 3→8, 5→9
\tc{foo}\tcn{8}
... rest of pasted region ...
\tc{bar}\tcn{9}
```

The comment is documentation only — neither the PreToolUse hook nor
the review tooling parses it. It exists so a reviewer can trace any
inherited mark back to its source.

## Quick-reference regex patterns

Useful for users writing enumeration or resolution tooling against v2
marks.

### Markdown

| Pattern | Regex (extended) | Captures |
|---------|------------------|----------|
| Inline mark + number | `<mark>(.*?)</mark><sup>([0-9]+)</sup>` | content, N |
| Replacement detection | `<mark><s>(.*?)</s>(.+?)</mark>` | old, new |
| Deletion detection | `<mark><s>(.*?)</s></mark><sup>` | removed text |
| Insertion detection | `<mark>([^<].*?)</mark><sup>` | inserted text (no leading `<s>`) |
| Mark numbers only | `</mark><sup>([0-9]+)</sup>` | N |
| Legacy replacement (Fix #6 and earlier) | `<mark>~~([^~]+)~~([^<]+)</mark>` | old, new |
| Legacy deletion (Fix #6 and earlier) | `<mark>~~([^~]+)~~</mark><sup>` | removed text |

### LaTeX

| Pattern | Regex (extended) | Captures |
|---------|------------------|----------|
| Inline mark + number | `\\tc\{([^}]*)\}\\tcn\{([0-9]+)\}` | content, N |
| Replacement detection | `\\tc\{\\sout\{([^}]+)\}([^}]+)\}\\tcn\{` | old, new |
| Deletion detection | `\\tc\{\\sout\{([^}]+)\}\}\\tcn\{` | removed text |
| Mark numbers only | `\\tcn\{([0-9]+)\}` | N |

Note on LaTeX matching: the `[^}]*` content captures stop at the first
closing brace, which is correct for simple content but not for content
containing nested `{...}`. For full extraction tooling, prefer a
brace-balancing parser.

### Extracting all mark numbers (file-wide scan)

```bash
# Markdown / Quarto:
grep -oE '</mark><sup>[0-9]+</sup>' file.md | grep -oE '[0-9]+'

# LaTeX:
grep -oE '\\tcn\{[0-9]+\}' file.tex | grep -oE '[0-9]+'
```

The output is one number per line in file order. Pipe through
`sort -n | tail -1` to get the maximum (used for next-N computation).

## Cross-references

- Full protocol: `SKILL.md`
- Markdown syntax discussion: `SKILL.md` §3
- LaTeX syntax discussion: `SKILL.md` §4 and `reference/latex.md`
- Numbering rules: `SKILL.md` §5
- Non-rendering constructs (full enumeration): `SKILL.md` §6
- Activation mechanisms: `SKILL.md` §2
- Slash commands: `SKILL.md` §7
- LaTeX preamble setup: `SKILL.md` §10
- v1 → v2 migration: `bash install.sh --migrate <dir>`
