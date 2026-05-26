---
name: verified-import
description: Opt-in, source-faithful import for tracked documents. The /import command reads a source file (or a #L<a>-L<b> line range), prints it with an instruction to convert it to the target document's format, and a PreToolUse hook verifies that the inserted block's content words match the source — fail-closed on any added or removed content. A verified import lands clean (no <mark>) via an exemption signal that the always-on track-changes skill honors. Separate from track-changes; loads only when /import is invoked. Depends on track-changes' shared tc_core.
---

# verified-import

`verified-import` is the **opt-in** counterpart to the always-on
**track-changes** mark protocol. Where track-changes wraps every Claude-made
change to a tracked `.md`/`.qmd`/`.tex` file in a numbered `<mark>` highlight,
`verified-import` handles the one deliberate operation that should NOT be
mark-wrapped: pulling content **from a source file** into a tracked document
(optionally converting its format) and landing it **clean** — once the content
has been verified to faithfully match the source.

This skill loads only when you invoke `/import`. For ordinary edits, the
track-changes skill governs (see its `/tc` command).

## The `/import` command

```
/import <source>[#L<a>-L<b>] [<target>]
```

- **`<source>`** — the source file. A relative path is resolved against the
  edited/working file's directory, the nearest ancestor `.tc-tracked` folder,
  the git project root, then the current directory; an absolute path is honored
  as-is. Only text sources are eligible:
  `.md` `.markdown` `.qmd` `.rmd` `.tex` `.txt`. A binary or mislabeled-binary
  source (NUL byte / non-UTF-8) is rejected with an actionable message.
- **`#L<a>-L<b>`** — an optional 1-indexed inclusive line range. Omit it to
  import the whole file. Out-of-range bounds are clamped.
- **`<target>`** — an optional destination file. Defaults to the **working
  file**: the most-recently-modified tracked `.md`/`.qmd`/`.tex` under the
  project scope (git root of the current directory, else the current
  directory).

Running `/import` resolves and slices the source, stages a one-shot
pending-import for the target, and prints the source slice plus an instruction
to convert it to the target's format and insert it. You then write the
converted block into the target.

## The faithfulness guarantee

When you write the converted block, the `verified-import` PreToolUse hook:

1. Builds the proposed file content and extracts the **added block** (the lines
   the write introduces).
2. Strips *formatting* markup from both the added block and the staged source
   slice — Markdown (headings, emphasis, code spans, links/images, list
   bullets, blockquotes, `<mark>`/`<sup>`/`<s>` tags) and LaTeX
   (`\section{…}`, `\textbf{…}`/`\emph{…}`/`\texttt{…}`, `\item`, comments,
   `\label`/`\ref`, `\\`) — folds whitespace and smart punctuation, and reduces
   each side to a lowercase **content-word** stream.
3. Compares the two as multisets. The import is faithful **iff** no content
   word was added (in your block but not the source) and none was removed (in
   the source but not your block). **Markup and formatting may differ freely**
   (e.g. `\section{Methods}` ↔ `## Methods`); only *content* is checked.

- **Pass** → the hook records a one-shot, sha-bound exemption for the exact
  bytes about to be written, appends an `imported:` entry to the project's
  `.tc-history.md` audit log, and allows the write. Because track-changes
  honors the exemption, the block lands **clean — no `<mark>`**.
- **Fail** → the write is **blocked, fail-closed**. The error names the content
  words you **added** and/or **removed** so you can re-emit the block
  faithfully. The pending import stays live for a corrected retry (bounded by a
  short TTL).

This is the verified, out-of-band successor to the inline source-provenance
wrappers of earlier versions: the exemption lives in state, so the imported
block carries no inline import markers.

## Dependency on track-changes

`verified-import` depends on the **track-changes** skill: it imports
track-changes' shared `tc_core` package (the exemption protocol + audit log
format) from `~/.claude/skills/track-changes/lib`. If track-changes is not
installed, an `/import` write fails closed with:

> verified-import: track-changes is not installed (install track-changes
> first; verified-import depends on its tc_core).

Install track-changes first, then verified-import.
