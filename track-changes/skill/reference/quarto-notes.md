# Quarto Interaction Notes

Lookup reference for using the `track-changes` skill inside Quarto
(`.qmd`) documents. These are not track-changes bugs — they are Quarto /
Pandoc rendering interactions that surfaced during real ISE 754
lecture-authoring sessions. A concentrated note here saves the next user
the same diagnostic cycle. Complements `SKILL.md` §3 (Markdown encoding),
§6 (non-rendering contexts), and §12 (render-time visibility).

The `<mark>…</mark><sup>N</sup>` wrapper renders natively in Quarto HTML
(it is raw HTML passed straight through to the output), so the skill works
in `.qmd` exactly as it does in `.md`. The interactions below concern
Quarto *features that sit next to a mark*, not the mark itself.

## 1. Annotations do not combine with `lst-cap`

Quarto **code annotations** (the numbered-circle callouts attached to
lines of a code block) and the **`lst-cap`** listing-caption attribute do
not coexist on the same code block. When a fenced block carries a
`lst-cap` (which wraps the listing in a figure-like container for the
caption), the annotation list that Quarto would normally emit below the
code is not paired with the annotated lines — the caption wrapper changes
the DOM structure the annotation JavaScript walks.

**Practical effect for track-changes.** If you are editing inside a
`lst-cap` listing, use the **sibling-mark form** (`SKILL.md` §6) above the
block rather than trying to attach a track-changes note as a code
annotation. The two mechanisms are independent; do not expect a mark to
ride along inside Quarto's annotation gutter.

## 2. Annotations do not combine with executable chunks that print to stdout

Quarto code annotations pair an annotation list with the code block by DOM
order: the annotation `<ol>` is expected to immediately follow the `<pre>`
holding the annotated source. When the chunk is **executable** and
**produces stdout** (a `print()`, a bare expression that echoes, a
rendered table), Quarto inserts the captured **output between the code
block and the annotation list** in the DOM. That ordering breaks the
pairing — the annotation numbers no longer line up with the source lines,
and the callout interaction silently degrades.

**Practical effect for track-changes.** When you edit inside an executable
chunk whose output is shown, keep track-changes marks on the **sibling
lines above the chunk** (§6). Do not interleave them with Quarto
annotations, and be aware that the chunk's own annotations (if any) may
mis-pair once output is present — this is a Quarto behavior, independent of
the skill.

## 3. Hover previews, lightbox, and code annotation require serving over `http://`

Three Quarto interactive features —

- **hover previews** (link/citation popups),
- **lightbox** (click-to-zoom figures), and
- **code-annotation** (the clickable numbered callouts in §1–§2) —

depend on same-origin `fetch()` / XHR calls at view time. Browsers block
those calls under the `file://` scheme (the same-origin policy treats every
`file://` document as a unique opaque origin), so opening the rendered
`.html` directly from disk leaves these features inert or throwing
console errors.

**Serve the document over `http://` to test them.** From the render output
directory:

```
python -m http.server 8000
# then open http://localhost:8000/your-lecture.html
```

or use `quarto preview`, which serves over `http://` automatically.

**Relevance to track-changes.** The skill's own render-time mark hiding
(`reference/tc-clean.css` + `reference/tc-clean.js`, `?clean=1`; see
`SKILL.md` §12) does **not** have this restriction — it manipulates only
the local DOM (`classList.add`) and reads `location.search`, with no
network fetch. So `?clean=1` works under both `file://` and `http://`. If
hover/lightbox/annotation features misbehave while `?clean` works fine,
the `file://` origin — not the skill — is the cause.

## Cross-references

- Full protocol: `SKILL.md`
- Markdown / Quarto encoding: `SKILL.md` §3 and `reference/highlight-syntax.md`
- Non-rendering contexts + new-block sibling form: `SKILL.md` §6
- Render-time mark hiding (`?clean=1`): `SKILL.md` §12 and
  `reference/tc-clean.css` / `reference/tc-clean.js`
- Common pitfalls (incl. this note): `SKILL.md` §13
