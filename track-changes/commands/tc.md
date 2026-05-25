---
description: track-changes unified command (draft / enable / disable / mark / migrate / status / help)
allowed-tools: Bash(bash:*)
argument-hint: "<subcommand> [args...]"
---

!bash "$HOME/.claude/skills/track-changes/lib/tc-cli.sh" $ARGUMENTS

Subcommands:

- `/tc on` — force tracking ACTIVE for the rest of this session
- `/tc off` — force tracking INACTIVE for the rest of this session
- `/tc draft` — suspend tracking for the current turn only
- `/tc enable <file>` — add `track-changes: true` to the file's YAML frontmatter (or `% track-changes: true` magic comment for `.tex`)
- `/tc disable <file>` — add `track-changes: false` to the file (per-file opt-out)
- `/tc mark [<dir>]` — drop `.tc-tracked` marker in `<dir>` (default: current directory)
- `/tc migrate <dir>` — convert v1 marks to v2 in all `.md`/`.qmd`/`.tex` files under `<dir>`
- `/tc status [<file>]` — show the activation chain for `<file>` (or current directory)
- `/tc list <file>` — list each mark in `<file>` with its number and a short content preview
- `/tc accept <file> <ranges>` — accept the listed marks: keep the new text, strip the `<mark>…</mark><sup>N</sup>` wrapper. Ranges use `1-25,!7,!11` syntax (inclusive comma-separated ranges; `!N` excludes `N`).
- `/tc reject <file> <ranges>` — reject the listed marks: restore the old text, strip the wrapper (same range syntax)
- `/tc accept-all <file>` — accept every mark in `<file>`
- `/tc reject-all <file>` — reject every mark in `<file>`
- `/tc help` — show this list

Batch resolution edits the file directly and records each decision in `.tc-history.md` with `decision: explicit`, so a later content-survival inference (Fix #8) never overwrites a choice you made deliberately. Resolution works for `.md`/`.qmd` (`<mark>` form) and `.tex` (`\tc{}\tcn{}` form).

For the full activation-precedence chain and encoding specification, see `~/.claude/skills/track-changes/SKILL.md`.

$ARGUMENTS
