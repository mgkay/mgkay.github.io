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
- `/tc help` — show this list

For the full activation-precedence chain and encoding specification, see `~/.claude/skills/track-changes/SKILL.md`.

$ARGUMENTS
