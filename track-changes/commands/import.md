---
description: verified-import — faithfully import a source slice into the current tracked document
allowed-tools: Bash(bash:*)
argument-hint: "<source>[#L<a>-L<b>] [<target>]"
---

!bash "$HOME/.claude/skills/verified-import/lib/vi-cli.sh" $ARGUMENTS

`/import <source>[#L<a>-L<b>] [<target>]` stages a verified, faithful import of
a text source into a tracked document.

- `<source>` — path to the source file (relative to the edited/working file's
  directory, the nearest `.tc-tracked` folder, the git root, or the current
  directory; an absolute path is honored as-is). A single leading `@` (Claude's
  file-reference prefix) is accepted and stripped, so `/import @notes.md` and
  `/import notes.md` resolve identically. Only text sources
  (`.md` `.markdown` `.qmd` `.rmd` `.tex` `.txt`) may be imported; a binary or
  mislabeled-binary source (NUL byte / non-UTF-8) is rejected.
- `#L<a>-L<b>` — optional 1-indexed inclusive line range; omit for the whole file.
- `<target>` — optional destination file (a leading `@` is also accepted and
  stripped); defaults to the **working file** (the most-recently-modified
  tracked `.md`/`.qmd`/`.tex` under the project).

The command prints the resolved source slice plus a conversion instruction, and
stages a one-shot pending-import for the target. You then **convert the slice
faithfully** to the target's format and insert it.

## How the converted block lands

This is a verified import: by default the converted block lands **clean — no
`<mark>` wrapping**. When you write a block with a live pending-import staged,
the `verified-import` PreToolUse hook records a one-shot, sha-bound exemption for
the exact bytes being written and appends an `imported:` entry to the project's
`.tc-history.md` audit log. The always-on track-changes skill honors that
exemption, so the faithful import is not mark-wrapped.

There is **no mechanical content gate**: the whole point of using a large
language model is that it can judge which differences matter. Reproduce the
content faithfully — preserve every sentence and clause; only formatting may
change to match the target format. Then exercise judgment:

- **Wrap ONLY a genuinely *significant* change in a track-changes mark.** A
  significant change is one that **alters meaning**: an added or removed sentence
  or clause, or a changed quantity, term, or formula.
- **Minor diffs land clean — do not mark them.** Reflow, reformatting, and
  equivalent notation are NOT significant: e.g. rewrapping lines,
  `\section{X}` → `## X`, or an `equation` environment → `$$…$$`.
- **Positive example (DO mark):** dropping the clause "at optimal lot size" from
  a sentence changes meaning — wrap that change so the author reviews it
  (Markdown: `<mark>NEW</mark><sup>N</sup>`; LaTeX: `\tc{NEW}\tcn{N}`).
- **Negative example (do NOT mark):** rewrapping lines, or converting an
  `equation` environment to `$$…$$`, is equivalent notation — leave it clean.

**Write ONLY the converted block in the import edit** — do not bundle unrelated
edits into the same write, since the exemption covers the whole written file.

The pending-import is one-shot and short-lived (TTL ~300 s, user-overridable). If
it expires before you write the block, re-run `/import` to stage a fresh one.

verified-import depends on **track-changes** (it imports its shared `tc_core`).
If track-changes is not installed, the hook fails closed with an actionable
message. For the always-on mark protocol on ordinary edits, see the
track-changes skill (`/tc`).

$ARGUMENTS
