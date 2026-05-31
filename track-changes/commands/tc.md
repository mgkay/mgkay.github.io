---
description: track-changes unified command (draft / enable / disable / mark / migrate / status / help)
allowed-tools: Bash(bash:*)
argument-hint: "draft|enable|disable|mark|migrate|status|list|accept|reject|accept-all|reject-all|help [args]"
---

!bash "$HOME/.claude/skills/track-changes/lib/tc-cli.sh" $ARGUMENTS

Run `/tc` with no arguments to print the compact menu.

Subcommands:

- `/tc draft` — suspend tracking for the current turn only
- `/tc enable <file>` — add `tc-track: true` to the file's YAML frontmatter (or `% tc-track: true` magic comment for `.tex`)
- `/tc disable <file>` — add `tc-track: false` to the file (per-file opt-out)
- `/tc mark [<dir>]` — drop `.tc-tracked` marker in `<dir>` (default: current directory)
- `/tc migrate <dir>` — convert v1 marks to v2 in all `.md`/`.qmd`/`.tex` files under `<dir>`
- `/tc status [<file>]` — show the activation chain for `<file>` (or the working file / current directory)
- `/tc list [<file>]` — list each mark in `<file>` with its number and a short content preview (omit `<file>` to use the working file)
- `/tc accept [<file>] <ranges>` — accept the listed marks: keep the new text, strip the `<mark>…</mark><sup>N</sup>` wrapper. Ranges use `1-25,!7,!11` syntax (inclusive comma-separated ranges; `!N` excludes `N`). Omit `<file>` to use the working file (the lone argument is then the ranges).
- `/tc reject [<file>] <ranges>` — reject the listed marks: restore the old text, strip the wrapper (same range syntax; `<file>` optional)
- `/tc accept-all [<file>]` — accept every mark in `<file>` (omit `<file>` to use the working file)
- `/tc reject-all [<file>]` — reject every mark in `<file>` (omit `<file>` to use the working file)
- `/tc help` — show this list

When `<file>` is omitted for a resolution subcommand, the working file is the most-recently-modified tracked file under the project (git root, else current directory). `/tc enable` and `/tc disable` always require an explicit `<file>`.

Batch resolution edits the file directly and records each decision in `.tc-history.md` with `decision: explicit`, so a later content-survival inference (Fix #8) never overwrites a choice you made deliberately. Resolution works for `.md`/`.qmd` (`<mark>` form) and `.tex` (`\tc{}\tcn{}` form).

For the full activation-precedence chain and encoding specification, see `~/.claude/skills/track-changes/SKILL.md`.

$ARGUMENTS
