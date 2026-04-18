---
name: pcv
description: >
  Plan-Construct-Verify workflow for complex projects. Adds structured planning
  discipline — sequential clarification, adversarial review, human approval gates,
  and verification — on top of Claude Code's native capabilities. Invoke with /pcv.
  Suggest (once) when a user describes a complex multi-component project.
---

# PCV — Skill Entry Point

Opt-in only. Runs when user invokes `/pcv`. Never impose on normal work.

---

## 1. Command Routing

### Step 0: Display Version

Read `~/.claude/skills/pcv/VERSION` (3 lines: version, date, changelog).
Display: `PCV v[version] ([date])`

### Step A: Locate Charge

Charge file: any name containing "charge" (case-insensitive).
Argument: `$ARGUMENTS`

1. **`$ARGUMENTS` not empty:** Read that file. Not found → stop:
   "Could not find charge file. Must be a file on disk for auditing."
2. **Empty:** Glob for `pcvplans/*[Cc][Hh][Aa][Rr][Gg][Ee]*.md`.
   - No matches → Glob for `*[Cc][Hh][Aa][Rr][Gg][Ee]*.md` (root fallback).
     - No matches → Step B (scaffold).
   - One match → use it, Step C.
   - Multiple → list, ask user. Wait.

Charge must be a file on disk. Content in conversation without file → stop:
"Save to a file and run `/pcv` again."

### Step B: Scaffold New Project

Read ~/.claude/skills/pcv/scaffold-templates.md for templates.

0. **Global settings check.** Invoke `bash ~/.claude/skills/pcv/handlers/global-settings.sh --project-dir .`.
   Handler reads `~/.claude/settings.json` allow count, reads `session-state.json:test_mode`,
   announces action (propose+merge the full pattern set from §9 below / skip), logs. No hub GATE.
   (Full proposed-permissions pattern list preserved in §9 below; handler merges that set.)

1. Run `bash ~/.claude/skills/pcv/hooks/scaffold-settings.sh --project-dir .`
2. Create `CLAUDE.md` (§3 template).
3. Create `pcvplans/charge.md` (§4 template).
4. Create `pcv_idea.md` in project root (§4a template).
5. Write `pcvplans/.gitkeep` (empty, establishes dir).
6. Message: "PCV v[version] — workspace initialized. Describe idea in pcv_idea.md."
7. **STOP.**

### Step B2: Charge Generation

When user signals ready (or `/pcv` re-invoked with unfilled charge + populated pcv_idea.md):

1. Read pcv_idea.md. Empty → remind, stop.
2. Read additional context (project files, CLAUDE.md, prior charges).
3. Generate draft charge using §4 template.
4. Present as blockquoted preview. List uncertain fields as numbered questions
   (one at a time, per planning clarification protocol).
5. All resolved → invoke `bash ~/.claude/skills/pcv/handlers/charge-write.sh --project-dir .`.
   Handler checks `pcvplans/charge.md` existence, reads `session-state.json:test_mode`, writes
   (or no-ops), announces, logs. No hub GATE.
6. (Handler performs the write in step 5 above.)
7. Relocate pcv_idea.md: Read root pcv_idea.md, Write to pcvplans/idea.md, delete root pcv_idea.md.
8. Continue to Step C.

### Step C: Validate and Route

0. **Read session state.** Read `pcvplans/logs/session-state.json` (written by SessionStart hook).
   If absent, proceed with silent defaults per pcv-common.md Mechanical-Gate Protocol.
   All Step C gates below invoke their handler, which reads this sentinel — no separate
   early-load required.

1. **Charge validation.** Name + Project Name not blank/`<REPLACE>`. Deployment may be blank.
   If `CLAUDE.md` does not exist in the project directory, create it using the §3
   template from scaffold-templates.md (same as Step B).

   **1.5 Plan tier.** Invoke `bash ~/.claude/skills/pcv/handlers/plan-tier.sh --project-dir .`.
   Handler reads `pcv-config.json`, reads `session-state.json:test_mode`, announces
   selection, logs, writes `pcv-config.json` if needed. No hub GATE.

   **1.7 Hook registration.** Invoke `bash ~/.claude/skills/pcv/handlers/hook-registration.sh --project-dir .`.
   Handler checks `.claude/settings.json` for all five hooks, checks opt-out marker,
   reads charge for hook-redesign keyword, reads `session-state.json:test_mode`,
   announces action (install / defer / skip), logs. No hub GATE.

2. **Git setup.** Invoke `bash ~/.claude/skills/pcv/handlers/git-setup.sh --project-dir .`.
   Handler globs for `.git`, walks parent chain (5 levels), reads `session-state.json:test_mode`,
   announces result (found / init / parent-found / skip), logs. No hub Wait.

3. **Phase detection.** session-start-resume.sh injects routing block via
   SessionStart hook (version header, progress checklist, ROUTING ACTION line).

   **Hook active:** Display block. Follow ROUTING ACTION.

   **Fallback (no block in context):** Run:
   `bash ~/.claude/skills/pcv/hooks/session-start-resume.sh`
   Follow the ROUTING ACTION in the output.
   If script not found → "session-start-resume.sh missing. Re-run bootstrap or reinstall PCV."
   If script errors → report error to user.

   Display checklist before routing.

   ### 3a. Version Chaining (completed project)

   Read ~/.claude/skills/pcv/scaffold-templates.md for version chaining instructions.

4. **Load protocol.** Read from `~/.claude/skills/pcv/` and follow.
   Only one protocol in context at a time.

---

## 2. Phase Summaries

### Planning (`planning-protocol.md`) — effort: high/max
Charge → paths → patterns → clarification (1 question/round) → agent config →
MakePlan → Critic → Gate 1 → ConstructionPlan → artifact gates → Gate 3.

### Construct (`construction-protocol.md`) — effort: medium
Dir → baseline → builder dispatch (sequential) → deviations → commits → build record.
Lite: inline construction, no builder subagent.

### Verify (`verification-protocol.md`) — effort: medium
Verifier dispatch → criteria mapping → artifact comparison → acceptance testing →
report → commit → build record finalize → closeout → summary → deployment → multi-phase check.

### Phase Transition (`phase-transition-protocol.md`) — effort: medium
Phase closeout → master log → review tentative plan → user directs → scaffold next → begin planning.

### Lite — effort: medium
Compressed 2-gate workflow. Single lite-plan.md. Critic reviews. Inline construction.
Inline verification default (subagent for Pattern 1/3).

---

## 3. Templates — See scaffold-templates.md (loaded at Step B/§3a)

---

## 5. Permission Settings

Managed by `~/.claude/skills/pcv/hooks/scaffold-settings.sh` (single source of truth).

Scaffold: `bash scaffold-settings.sh --project-dir .`
Handles create + merge. Multi-phase uses same script.
Tech permissions added at Gate 3 by `tech-permissions-scan.sh` (see construction protocol).

---

## 6. Protocol Loading

Protocols use spine + fragment architecture. Each protocol file is a compact spine
with a step table pointing to fragment files in subdirectories:

```
planning-protocol.md          → planning/*.md (6 fragments)
construction-protocol.md      → construction/*.md (1 fragment)
verification-protocol.md      → verification/*.md (3 fragments)
phase-transition-protocol.md  → transition/*.md (3 fragments)
pcv-common.md                 → shared patterns (log formats, dispatch, gates)
```

Loading sequence: read pcv-common.md once, then spine, then current fragment.
Each fragment ends → read next fragment in sequence.

---

## 7. Behavioral Constraints

- Always opt-in. May suggest once if complex project described; if declined, don't repeat.
- Main workflow in main conversation, never as subagent.
- Four agents (critic, research, builder, verifier) in `~/.claude/agents/`.
  Read + inline in Agent prompt (custom types not directly spawnable).
- Subagent fails to spawn → acceptable. Work product identical, only token efficiency reduced.
- File ops: Read/Write tools or cross-platform scripting. Never `cp`/`copy`.
- Git: silent commits at milestones. Never `cd` in Bash. Absolute paths.

---

## 8. Multi-Phase Scaffolding — See scaffold-templates.md

---

## 9. Step B.0 Proposed Global Permissions (Full Pattern List)

Referenced by Step B.0 above. When the user approves the gate, merge every
pattern in this list into `~/.claude/settings.json` `permissions.allow` (skip
any already present).

Core tools (broad):

- `Read(**)`, `Write(**)`, `Edit(**)`, `Glob(*)`, `Grep(*)`, `Bash(*)`, `Agent(*)`, `WebSearch(*)`

Temp dirs (MSYS/Unix + Windows):

- `Read(/tmp/**)`, `Write(/tmp/**)`, `Edit(/tmp/**)`
- `Read(~/AppData/Local/Temp/**)`, `Write(~/AppData/Local/Temp/**)`, `Edit(~/AppData/Local/Temp/**)`
- `Bash(rm /tmp/tmpclaude*)` — temp cleanup convention
- `Bash(mkdir -p /tmp/*)` — temp scaffold

PCV internals:

- `Bash(bash ~/.claude/skills/pcv/hooks/*)` — PCV hook invocations
- `Bash(bash ~/.claude/skills/pcv/handlers/*)` — PCV handler invocations (v3.14+)

Git ops:

- `Bash(git -C * *)` — git on arbitrary paths (replaces the forbidden `cd`-then-git pattern)
