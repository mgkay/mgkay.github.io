---
description: Suspend track-changes for this turn (drafting mode)
allowed-tools: Bash(bash:*)
---

!bash "$HOME/.claude/skills/track-changes/lib/draft-on.sh"

Drafting mode requested for this turn. Track-changes will be suspended **only
if the sentinel was actually written**; you may then edit existing `.md`,
`.qmd`, and `.tex` files without highlight wrappers. Default tracking
auto-restores at the start of the next user turn via the UserPromptSubmit
clearing hook.

**Assistant: verify before relying on suspension.** The sentinel write above
uses a `!bash` command-prefix that the CLI executes **only when the user
types `/draft`**. If you reached this command via the **Skill tool**, that
line did **not** run and no sentinel exists — your next tracked edit will be
blocked. Confirm by checking that the script echoed a `sentinel:` path above;
if it did not, run
`bash "$HOME/.claude/skills/track-changes/lib/draft-on.sh"` via the Bash tool
yourself before editing.

The sentinel is written by the skill's own bash (`lib/draft-on.sh`), so activation no longer depends on a user-supplied shell snippet. When `$CLAUDE_SESSION_ID` is unset (common on Windows / cross-shell), it falls back to a shared `state/default.draft` sentinel, which the activation gate and the clearing hooks both honor.

This is the per-turn override. For per-file opt-out use `/tc disable <file>`; for folder-wide opt-in use `/tc mark <dir>`.

$ARGUMENTS
