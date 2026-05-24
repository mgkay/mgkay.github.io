---
description: Suspend track-changes for this turn (drafting mode)
allowed-tools: Bash(bash:*)
---

!bash "$HOME/.claude/skills/track-changes/lib/draft-on.sh"

Drafting mode active for this turn. Track-changes is suspended; you may edit existing `.md`, `.qmd`, and `.tex` files without highlight wrappers. Default tracking auto-restores at the start of the next user turn via the UserPromptSubmit clearing hook.

This is the per-turn override. For session-wide disable use `/track-off`; for session-wide force-enable use `/track-on`.

$ARGUMENTS
