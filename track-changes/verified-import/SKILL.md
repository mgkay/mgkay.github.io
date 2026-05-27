---
name: verified-import
description: Opt-in, source-faithful import for tracked documents. The /import command reads a source file (or a #L<a>-L<b> line range) and prints it with an instruction to convert it to the target document's format. There is no mechanical content gate — the LLM imports faithfully and self-marks only genuinely significant changes (altered meaning) in track-changes marks; minor diffs land clean. A PreToolUse hook writes a one-shot, sha-bound exemption that the always-on track-changes skill honors, so the faithful block lands clean (no <mark>). Separate from track-changes; loads only when /import is invoked. Depends on track-changes' shared tc_core.
---

# verified-import

`verified-import` is the **opt-in** counterpart to the always-on
**track-changes** mark protocol. Where track-changes wraps every Claude-made
change to a tracked `.md`/`.qmd`/`.tex` file in a numbered `<mark>` highlight,
`verified-import` handles the one deliberate operation that should NOT be
mark-wrapped: pulling content **from a source file** into a tracked document
(optionally converting its format) and landing it **clean** — trusting the
LLM to import faithfully and to mark only genuinely significant changes.

This skill loads only when you invoke `/import`. For ordinary edits, the
track-changes skill governs (see its `/tc` command).

## The `/import` command

```
/import <source>[#L<a>-L<b>] [<target>]
```

- **`<source>`** — the source file. A relative path is resolved against the
  edited/working file's directory, the nearest ancestor `.tc-tracked` folder,
  the git project root, then the current directory; an absolute path is honored
  as-is. A single leading `@` (Claude's file-reference prefix) is accepted and
  stripped, so `/import @notes.md` and `/import notes.md` resolve identically.
  Only text sources are eligible:
  `.md` `.markdown` `.qmd` `.rmd` `.tex` `.txt`. A binary or mislabeled-binary
  source (NUL byte / non-UTF-8) is rejected with an actionable message.
- **`#L<a>-L<b>`** — an optional 1-indexed inclusive line range. Omit it to
  import the whole file. Out-of-range bounds are clamped.
- **`<target>`** — an optional destination file (a leading `@` is also accepted
  and stripped). Defaults to the **working file**: the most-recently-modified
  tracked `.md`/`.qmd`/`.tex` under the project scope (git root of the current
  directory, else the current directory).

Running `/import` resolves and slices the source, stages a one-shot
pending-import for the target, and prints the source slice plus an instruction
to convert it to the target's format and insert it. You then write the
converted block into the target.

## How a verified import lands clean

There is **no mechanical content gate**. The whole point of using a large
language model is that it can judge which differences matter — so v4 trusts the
model to import faithfully and to flag only the changes a human author would
want to review. The flow:

1. **`/import` stages a pending-import.** It resolves and slices the source,
   prints the slice plus a conversion instruction, and writes a one-shot,
   target-keyed pending-import record under the track-changes state tree.
2. **You convert faithfully and insert ONLY the converted block.** Reproduce the
   content faithfully — preserve every sentence and clause; only formatting may
   change to match the target format. Write **only** the converted block in this
   edit; do not bundle unrelated edits into the same write (the exemption in
   step 3 covers the whole written file — see *Author responsibility* below).
3. **The PreToolUse hook writes a sha-bound exemption.** With a live
   pending-import staged, the `verified-import` PreToolUse hook records a
   one-shot, sha-bound exemption for the exact bytes about to be written, appends
   an `imported:` entry to the project's `.tc-history.md` audit log, consumes the
   pending-import, and allows the write. The always-on track-changes skill
   consumes that exemption, so the block lands **clean — no `<mark>`**.
4. **Significance is YOUR judgment — self-mark only significant changes.** If
   your conversion introduced a genuinely **significant** content change, wrap
   **only** that change in a track-changes mark so the author reviews it; minor
   diffs land clean and need no mark.

**Operational definition.** A change is **significant** when it **alters
meaning**: an added or removed sentence or clause, or a changed quantity, term,
or formula. It is **NOT significant** — and needs no mark — when it is reflow,
reformatting, or equivalent notation (e.g. `\section{Methods}` → `## Methods`, an
`equation` environment → `$$…$$`, or rewrapped lines).

- **Positive example (DO mark):** dropping the clause "at optimal lot size" from
  a sentence changes meaning — wrap that change
  (Markdown: `<mark>NEW</mark><sup>N</sup>`; LaTeX: `\tc{NEW}\tcn{N}`).
- **Negative example (do NOT mark):** rewrapping lines, or converting an
  `equation` environment to `$$…$$`, is equivalent notation — leave it clean.

**Author responsibility (whole-file exemption).** The exemption is keyed to the
whole written file's bytes, so any unrelated edit bundled into the same import
write would also land unmarked. Keep the import write to **only** the converted
block; make unrelated edits in a separate write so the track-changes mark
protocol covers them normally.

**Pending-import TTL.** The pending-import is one-shot and short-lived
(~300 s by default, user-overridable). If it expires before you write the block,
re-run `/import` to stage a fresh one. This is the out-of-band successor to the
inline source-provenance wrappers of earlier versions: the exemption lives in
state, so the imported block carries no inline import markers.

## Dependency on track-changes

`verified-import` depends on the **track-changes** skill: it imports
track-changes' shared `tc_core` package (the exemption protocol + audit log
format) from `~/.claude/skills/track-changes/lib`. If track-changes is not
installed, an `/import` write fails closed with:

> verified-import: track-changes is not installed (install track-changes
> first; verified-import depends on its tc_core).

Install track-changes first, then verified-import.
