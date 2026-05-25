---
description: Suspend track-changes for this turn (drafting mode)
allowed-tools: Bash(bash:*)
---

!bash "$HOME/.claude/skills/track-changes/lib/draft-on.sh"

Drafting mode active for this turn. Track-changes is suspended; you may edit existing `.md`, `.qmd`, and `.tex` files without highlight wrappers. Default tracking auto-restores at the start of the next user turn via the UserPromptSubmit clearing hook.

The sentinel is written by the skill's own bash (`lib/draft-on.sh`), so activation no longer depends on a user-supplied shell snippet. When `$CLAUDE_SESSION_ID` is unset (common on Windows / cross-shell), it falls back to a shared `state/default.draft` sentinel, which the activation gate and the clearing hooks both honor.

This is the per-turn override. For per-file opt-out use `/tc disable <file>`; for folder-wide opt-in use `/tc mark <dir>`.

$ARGUMENTS
