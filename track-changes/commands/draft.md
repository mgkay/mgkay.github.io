---
description: Suspend track-changes for this turn (drafting mode) — USER ONLY
disable-model-invocation: true
---

<!-- TC-DRAFT-REQUEST -->

Drafting mode requested for **this turn**. Because you (the human) typed
`/draft`, the track-changes **UserPromptSubmit** hook authorizes a one-turn
suspension: it writes the `/draft` sentinel (carrying the authorized marker the
PreToolUse gate checks). Existing `.md`, `.qmd`, and `.tex` files may then be
edited without highlight wrappers for this turn. Default tracking auto-restores
at the start of your next prompt.

**v6 — `/draft` is mechanically user-only.** The sentinel is written *only* by
the UserPromptSubmit hook in response to **your** prompt. The assistant cannot
suspend its own tracking: `lib/draft-on.sh` no longer writes the sentinel, and a
sentinel without the authorized marker is ignored. If the assistant believes
content should land untracked, it must ask you to `/draft` — it cannot do it
itself. For authored content the honest paths are a `<mark>` edit, a whole-region
insertion (`::: {.tc-region …}` / `\begin{tcregion}{N}`), or `/import` for
verbatim source.

This is the per-turn override. For per-file opt-out use `/tc disable <file>`;
for folder-wide opt-in use `/tc mark <dir>`.

$ARGUMENTS
