# Highlight Syntax Reference

Lookup reference for the `track-changes` skill. Use this document when
you need to confirm exact syntax for a specific change type or language.
The full protocol lives in `SKILL.md`; this file supplements §3
(markdown), §4 (LaTeX), and §6 (the brand-new-block sibling form).

The mark encoding is **token-minimal**: each highlight wraps only the
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

## Brand-new block sibling form (Markdown/Quarto only)

A **brand-new** block-level element — an ATX heading, a fenced code
block, or a `::: {...}` Quarto div — cannot be inline-wrapped (wrapping
the delimiter or the `### ` line breaks the construct). The
block-sibling form covers this: put one `<mark>…</mark><sup>N</sup>` on
the line *immediately above* the new block, then write the block
normally. The hook treats the new block's delimiter/heading lines as
covered by that sibling. See `SKILL.md` §6.

> **Important — no blank line.** The sibling mark must sit on the line
> *immediately* above the new block's opener — no blank line between the
> sibling and the opener. The PreToolUse hook looks at exactly the prior
> line; inserting an empty line breaks the association.

### New heading

```markdown
<mark>New subsection: Wider tables demo</mark><sup>1</sup>
### Wider tables
```

### New fenced code block

```markdown
<mark>New helper: factorial</mark><sup>4</sup>
` ``python
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
` ``
```

### New `:::` div

```markdown
<mark>New column-body-outset breakout</mark><sup>2</sup>
::: {.column-body-outset}
| ... wide table ... |
:::
```

**Markdown/Quarto only.** This form does **not** cover a brand-new LaTeX
block (`\section{}`, `equation`/`align`/`tabular`/`verbatim`
environments), nor *editing inside* an existing non-rendering construct
in any language. Those route to `/draft` — a documented v3 limitation
(the v2 in-construct sibling form was removed). See `SKILL.md` §6.

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

## v6: provenance + whole-region insertion

**Provenance type (optional).** A mark or region may carry a provenance type so
the reviewer can tell verbatim imports from authored text:

```
Markdown / Quarto:  <mark tc-prov="imported">NEW</mark><sup>N</sup>
LaTeX:              \tc[imported]{NEW}\tcn{N}
```

Values: `authored` (default — anything written or paraphrased) or `imported` (a
verbatim slice landed via `/import`). Absent ⇒ `authored`, so every pre-v6 mark
is unchanged. The opening-tag attribute does not affect the closing
`</mark><sup>N</sup>` (number extraction is unchanged).

**Whole-region insertion (Fix D).** A multi-block new region (heading + prose +
`:::` div + fenced code, or several paragraphs) is marked as ONE tracked
insertion instead of one mark per line:

```
Markdown / Quarto:                    LaTeX:
::: {.tc-region tc-n="N" tc-prov="authored"}   \begin{tcregion}{N}[authored]
## New section                                 \section{New}
new prose, code, math …                        new body, math, verbatim …
:::                                            \end{tcregion}
```

- One number `N`, shared with the inline mark-number space (uniqueness enforced
  across both). `/tc accept N` strips the delimiters and keeps the body;
  `/tc reject N` removes the whole region.
- The region is **atomic** — do not place inline marks inside it.
- Rendering: md/qmd shows a tinted block with a colored left border
  (`tc-clean.css`); LaTeX draws a colored left change-bar (`tcregion` in
  `tc.sty`) — robust across math/verbatim/paragraph breaks where `\hl` is not.
- This replaces the old "brand-new LaTeX block → `/draft`" routing.

**Number extraction including regions (bash):**
```
# md/qmd region numbers:
grep -E '\.tc-region' file.qmd | grep -oE 'tc-n="[0-9]+"' | grep -oE '[0-9]+'
# LaTeX region numbers:
grep -oE '\\begin\{tcregion\}\{[0-9]+\}' file.tex | grep -oE '[0-9]+'
```

## Cross-references

- Full protocol: `SKILL.md`
- Markdown syntax discussion: `SKILL.md` §3
- LaTeX syntax discussion: `SKILL.md` §4 and `reference/latex.md`
- Numbering rules (per-file uniqueness): `SKILL.md` §5
- Non-rendering contexts (brand-new-block sibling + in-construct → `/draft`):
  `SKILL.md` §6
- Activation mechanisms: `SKILL.md` §2
- Slash commands: `SKILL.md` §7
- Importing from a source (separate skill): `verified-import` `/import`
- LaTeX preamble setup: `SKILL.md` §10
- v1 → v2 migration: `bash install.sh --migrate <dir>`
