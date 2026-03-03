---
name: pcv
description: >
  Plan-Construct-Verify workflow for complex projects. Adds structured planning
  discipline — sequential clarification, adversarial review, human approval gates,
  and verification — on top of Claude Code's native capabilities. Invoke with /pcv.
  Suggest (once) when a user describes a complex multi-component project.
---

# Plan-Construct-Verify (PCV) — Skill Entry Point

You are executing the PCV workflow skill. PCV is opt-in methodology — it only
runs when the user explicitly invokes `/pcv`. Never impose PCV on normal Claude
Code work.

---

## 1. Command Routing

When the user invokes `/pcv`, follow this sequence:

### Step 0: Display version

Read `~/.claude/skills/pcv/VERSION`. The file format is three lines:
1. Version number (e.g., `3.1`)
2. Date (e.g., `2026-02-23`)
3. Brief changelog

Display a one-line version notice before proceeding:
> `PCV v[version] ([date])`

### Step A: Locate the charge file

The charge file can have any name containing "charge" (case-insensitive).
The user may specify it as an argument: `/pcv MyProject_Charge.md`

**Argument:** $ARGUMENTS

1. **If `$ARGUMENTS` is not empty:** treat it as a charge **filename**. Use the
   Read tool to open that file. If the file does not exist on disk, stop with:
   > "Could not find charge file: `[argument]`. The charge must be a file on disk
   > for auditing purposes. Run `/pcv` with no argument to scaffold one, or
   > provide a valid filename."

2. **If `$ARGUMENTS` is empty:** use Glob to search for `*[Cc][Hh][Aa][Rr][Gg][Ee]*.md`
   in the current directory.
   - **No matches** → go to Step B (scaffold).
   - **Exactly one match** → use that file as the charge. Go to Step C.
   - **Multiple matches** → list them and ask the user which one to use. Wait.

**Charge must be a file.** PCV requires the charge to exist as a file on disk for
auditing and decision reconstruction. If charge content appears in conversation
context (e.g., pasted or attached via `@`) but no matching charge file exists on
disk, do NOT proceed. Instead, tell the user:
> "The charge must be saved as a file for auditing purposes. Please save it to
> a file (e.g., `charge.md`) and run `/pcv` again."

### Step B: Scaffold new project

This directory has no charge file. Set it up:

1. Create `.claude/settings.json` with permission pre-approvals (see Section 5).
   **This must be created first** — its allow rules cover all subsequent file writes.
2. Create `CLAUDE.md` with project identity placeholder (see Section 3).
3. Create `charge.md` from the charge template (see Section 4).
4. Create `plans/.gitkeep` (empty file) to establish the plans directory.
   **Use the Write tool, not mkdir.** The Write tool creates parent directories
   implicitly and works cross-platform.
5. Inform the user (include the version from Step 0):
   > "PCV v[version] — workspace initialized. When prompted to approve file edits,
   > select **'Yes, allow all edits during this session'** (option 2) — PCV manages
   > files within this directory automatically.
   >
   > Fill in `charge.md` with your project details, then run `/pcv` again.
   > You may rename the charge file — any filename containing 'charge' will
   > be found automatically, or specify it directly with `/pcv <filename>`."
6. **STOP.** Do not proceed until the user has filled in the charge and re-invoked `/pcv`.

### Step C: Validate and route

Use the charge file located in Step A for all subsequent references to "the charge."

1. **Charge validation.** Read the charge file. Verify:
   - `Name:` is not `<REPLACE>` or blank.
   - `Project Name:` is not `<REPLACE>` or blank.
   - Other Configuration fields may be blank (they have defaults or are optional).
   - If validation fails, stop and tell the user which fields need to be completed.

2. **Git setup.** Perform once per project. **Do NOT use `cd` in any Bash command —
   always operate from the current working directory.**
   - Use Glob to check for `.git` in the current directory. Do NOT use Bash for this check.
   - If `.git` exists, run `git remote -v`. If remotes found, inform the user:
     "This directory is connected to a remote repository at [URL]. Planning
     documents created here would be included in future pushes. Would you like
     to proceed here, or work from a separate directory?" Wait for response.
   - If no `.git`, run `git init` (no `cd`, no compound commands). If Git is
     unavailable, note in the decision log that version control is unavailable
     and inform the user once.

3. **Phase detection and progress display.** Use Glob or Bash to survey `plans/`
   for file existence. **Always check disk state with a tool call — never infer
   from conversation history.**

   Determine which milestones are complete, then display the progress checklist:

   ```
   PCV v[version] — [Project Name]
   [■/□] Charge validated
   [■/□] MakePlan approved
   [■/□] ConstructionPlan approved
   [■/□] Construction
   [■/□] Verification complete
   ```

   Use ■ for completed milestones and □ for incomplete. Determine status:
   - **Charge validated:** The charge file passed validation in sub-step 1 above.
   - **MakePlan approved:** `plans/make-plan.md` exists.
   - **ConstructionPlan approved:** `plans/construction-plan.md` exists.
   - **Construction:** Decision log contains a "Construction Complete" entry, OR
     deliverables exist matching the ConstructionPlan file structure.
   - **Verification complete:** Decision log contains a "Project Closeout" entry.

   **Always display the progress checklist before routing.** Then apply:

   | State | Action |
   |:------|:-------|
   | No `make-plan.md` | Start/resume **Planning**. Load `planning-protocol.md`. |
   | `make-plan.md` exists, no `construction-plan.md` | Ask: "A MakePlan exists. Are you resuming planning, or has this been approved and you're ready to proceed?" |
   | Both exist, scope is verification-only | Load `verification-protocol.md`. |
   | Both exist, construction not complete | Assess construction progress. Present status summary. Load `construction-protocol.md`. |
   | Both exist, construction complete, verification not complete | Load `verification-protocol.md`. |
   | **All milestones complete** | **Revision cycle** (see sub-step 3a below). |

   ### 3a. Revision Cycle (completed project)

   When all five milestones are complete, the project has finished a full PCV cycle.
   Prompt the user:

   > "This project completed a full PCV cycle. Would you like to start a new
   > revision cycle?"

   **STOP. Wait for the user's response.**

   - **If no:** Acknowledge and stop.
   - **If yes:** Perform the following:
     1. Determine the next revision number. Check for existing `plans/rev*/`
        directories. If none exist, the next revision is `rev1`. If `rev1/`
        exists, use `rev2`, etc.
     2. Copy `charge.md` into `plans/rev[N]/` (preserves the original charge
        for reference). Then move all other `plans/` contents (except `rev*/`
        subdirectories) into `plans/rev[N]/`. Use Read/Write tools to copy
        files, then delete originals. This preserves the historical record.
     3. Create a fresh `charge.md` from the charge template (Section 4), with
        the **Prior Work** field pre-filled with the **absolute path** to the
        current working directory. Preserve the **Name** and **Project Name**
        from the previous charge.
     4. Display:
        > "Previous plans and charge archived to `plans/rev[N]/`.
        > Fill in `charge.md` with your revision goals, then run `/pcv` again."
     5. **STOP.** Do not proceed until the user has filled in the charge and
        re-invoked `/pcv`.

4. **Load the appropriate protocol file.** Read the protocol file from this skill's
   directory (`~/.claude/skills/pcv/`) and follow its instructions. Only one protocol
   is in context at a time.

---

## 2. Phase Summaries

These are brief overviews. Full instructions are in each protocol file.

### Planning Phase (`planning-protocol.md`)
- Read charge, resolve working directory.
- Analyze prior work (if any) with three-category classification.
- Identify deliverable patterns (Code, Prose, Mathematical, Design-and-Render).
- Sequential clarification: one question at a time, dependency-ordered.
- Draft MakePlan → Critic review → Compliance checklist → **Gate 1: MakePlan Approval**.
- Draft ConstructionPlan (or minimal verification-only file) → Planning artifact gate
  (Pattern 4 wireframes, Pattern 3 formulations, Pattern 1 test specs) →
  **Gate 3: ConstructionPlan Approval**.
- Commit approved plans to Git if available.

### Construct Phase (`construction-protocol.md`)
- Resolve working directory from charge.
- Baseline copy if carrying forward prior work.
- Build strictly per approved ConstructionPlan.
- Log deviations with human approval. Commit at milestones.

### Verify Phase (`verification-protocol.md`)
- Pattern-appropriate verification (run tests, review structure, check math, visual compare).
- Map each Success Criterion to deliverable components.
- Compare deliverables against planning artifacts.
- Export if configured. Final commit. Decision log closeout.

---

## 3. CLAUDE.md Template

When scaffolding, create `CLAUDE.md` with this content:

```
# <Project Name>
Language: <Language>
```

This file contains only project identity — no PCV references, no methodology
instructions. Under 5 lines. The user customizes it after scaffolding.

---

## 4. Charge Template

When scaffolding, create `charge.md` with this content:

```markdown
# Project Charge

## Configuration
Name: <REPLACE>
Project Name: <REPLACE>
Project Directory:
<!-- Absolute path to the folder where code/deliverables live.
     Leave blank if this directory IS the project. -->
Export Target:
<!-- Absolute path to a separate folder where finished files should be copied
     after verification (e.g., a local Git repository). Leave blank if
     deliverables stay in the project directory. -->
Prior Work:
<!-- Absolute path(s) to previous versions or reference files to build on.
     Leave blank if starting from scratch. -->

## Project Description
<!-- What are you building? Who is it for? What should it do? -->

## Technology & Constraints
<!-- What language/framework? Any specific requirements or limitations? -->

## Prior Work Notes
<!-- If you listed prior work above, what do you want to keep,
     change, or improve from the previous version? -->

## Success Criteria
<!-- How will you know the project is done? What must be true? -->
```

**Configuration field definitions (for your reference during validation):**
- **Name:** The human's name.
- **Project Name:** Used for document headers and Git messages.
- **Project Directory:** Where deliverables/code live. Blank = current directory.
- **Export Target:** Where verified deliverables are copied during Verify. Blank = no export.
- **Prior Work:** Path(s) to previous versions or reference material. Blank = starting from scratch.

---

## 5. Permission Settings

PCV requires these permissions to operate without prompts:

```
Read(**)
Write(**)
Glob(*)
Grep(*)
Bash(git *)
Read(~/.claude/skills/pcv/*)
Read(~/.claude/agents/pcv-critic.md)
```

The last two (`Read(~/.claude/skills/pcv/*)` and `Read(~/.claude/agents/pcv-critic.md)`)
are **PCV-specific** and will never appear in global settings. The others are
**general-purpose** and are commonly already present in `~/.claude/settings.json`.

### Merge-aware scaffolding procedure

When creating or updating `.claude/settings.json` in Step B:

1. **Read `~/.claude/settings.json`** (skip gracefully if missing). Parse its
   `permissions.allow` array into a "globally covered" set.
2. **Read `.claude/settings.json`** if it already exists. Parse its current
   `permissions.allow` array into an "already in project" set.
3. **Filter**: From the PCV required list above, keep only entries that are
   NOT covered by global settings AND NOT already in the project file.
   A global entry covers a PCV entry if it is an exact match or a superset
   (e.g., global `Read(**)` covers PCV's `Read(**)`).
4. **Merge**: Add the filtered entries to the project file's existing allow
   array. Preserve all other keys in the file (`deny`, `hooks`, etc.).
5. **Write** the updated `.claude/settings.json`.

If the project file doesn't exist yet, create it with:
`{"permissions": {"allow": [<filtered entries>]}}`

This ensures PCV never duplicates permissions already granted globally and
respects any pre-existing project permissions (e.g., from `/pre-approve`).

**No other Bash commands should be needed.** PCV uses only internal tools (Read,
Write, Glob, Grep) for file operations. Directories are created implicitly by
writing files into them — do NOT use `mkdir` via Bash.

---

## 6. Protocol Loading

When transitioning between phases:
- **Planning → Construct:** Read `~/.claude/skills/pcv/construction-protocol.md` and follow it.
- **Planning → Verify (verification-only scope):** Read `~/.claude/skills/pcv/verification-protocol.md` and follow it.
- **Construct → Verify:** Read `~/.claude/skills/pcv/verification-protocol.md` and follow it.

Each protocol file ends with a transition instruction. Follow it.

---

## 7. Behavioral Constraints

- PCV is **always opt-in**. Never block normal Claude Code work.
- If a user describes a complex project and has not invoked PCV, you may suggest it
  **once**. If declined or ignored, do not repeat.
- The main PCV workflow runs in the main conversation context, never as a subagent.
- The only subagent PCV spawns is the adversarial Critic during Planning (via Task tool
  with `subagent_type: general-purpose`, `model: haiku`). The Critic's behavioral
  instructions are in `~/.claude/agents/pcv-critic.md` for reference but must be
  inlined in the Task prompt since custom agent types are not directly spawnable.
- All file operations for baseline copy and export must use internal Read/Write tools
  or cross-platform scripting — never OS-specific shell commands (`cp`, `copy`).
- Git commits happen at defined milestones with descriptive messages. Git is silent —
  the user does not interact with it.
- **Never use `cd` in Bash commands.** Always operate from the current working
  directory. Compound Bash commands with `cd` trigger security prompts in Claude Code.
  Use absolute paths if needed, or rely on Read/Write/Glob tools instead of Bash.
