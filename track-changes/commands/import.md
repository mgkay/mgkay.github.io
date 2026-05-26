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
  directory; an absolute path is honored as-is). Only text sources
  (`.md` `.markdown` `.qmd` `.rmd` `.tex` `.txt`) may be imported.
- `#L<a>-L<b>` — optional 1-indexed inclusive line range; omit for the whole file.
- `<target>` — optional destination file; defaults to the **working file**
  (the most-recently-modified tracked `.md`/`.qmd`/`.tex` under the project).

The command prints the resolved source slice plus a conversion instruction.
Convert the slice to the target's format and insert it: emit **faithful**
content only — do not add, drop, paraphrase, or reorder any sentence or clause;
only the formatting may change. The verified-import PreToolUse hook checks the
inserted block's content words against the source and **blocks the write
(fail-closed)** if any content word was added or removed, naming the
discrepancy so you can retry. A verified import lands **clean** — no `<mark>`
wrapping — because the hook signals an exemption that track-changes honors.

verified-import depends on **track-changes** (it imports its shared `tc_core`).
If track-changes is not installed, the hook fails closed with an actionable
message. For the always-on mark protocol on ordinary edits, see the
track-changes skill (`/tc`).

$ARGUMENTS
