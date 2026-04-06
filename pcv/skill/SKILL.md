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

0. **Global settings check (v3.10).** Read `~/.claude/settings.json`.
   - Define "minimal" as: file doesn't exist, or `permissions.allow` is absent/empty,
     or contains fewer than 3 allow rules.
   - **If minimal:** Present recommended global permissions:
     > "PCV works best with these global permissions to avoid repeated prompts
     > across all Claude Code projects:
     >
     > `Read(**)`, `Write(**)`, `Edit(**)`, `Glob(*)`, `Grep(*)`, `Bash(*)`,
     > `Agent`, `WebSearch`
     >
     > These are broad but standard for active development. Would you like to
     > add them to your global settings (`~/.claude/settings.json`)?"
     
     **STOP. Wait for user response.**
     
     - **On approval:** Read existing `~/.claude/settings.json` (or create if absent).
       Merge proposed permissions into `permissions.allow`, preserving all existing
       entries (`deny`, `hooks`, `model`, `statusLine`, etc.). Write back.
     - **On decline:** Log in decision log, proceed without changes.
   - **If user already has established settings (3+ allow rules):** Skip silently.

1. Create `.claude/settings.json` with permission pre-approvals (see Section 5).
   **This must be created first** — its allow rules cover all subsequent file writes.
2. Create `CLAUDE.md` with project identity placeholder (see Section 3).
3. Create `charge.md` from the charge template (see Section 4).
4. Create `idea.md` with the idea prompt header (see Section 4a).
5. Create `plans/.gitkeep` (empty file) to establish the plans directory.
   **Use the Write tool, not mkdir.** The Write tool creates parent directories
   implicitly and works cross-platform.
6. Inform the user (include the version from Step 0):
   > "PCV v[version] — workspace initialized.
   >
   > Describe your project idea in `idea.md`, then let me know when you're ready.
   > PCV will generate a structured charge from your idea."
7. **STOP. Wait for the user to signal readiness** (not a `/pcv` re-invocation).

### Step B2: Charge generation (same session)

When the user signals readiness after Step B (or when `/pcv` is re-invoked and
detects unfilled `charge.md` template placeholders + populated `idea.md`):

1. Read `idea.md`. If empty or unchanged from the template header, remind the user
   to fill it in and **STOP**.
2. Read any additional context in the directory: existing project files, `CLAUDE.md`,
   prior version charge files (if this is an extension project).
3. Generate a draft charge internally using the charge template (Section 4).
4. Present the draft in chat as a **blockquoted preview** (clearly marked as a draft,
   not written to disk). Below the preview, list fields where PCV is uncertain as
   numbered questions — **one question at a time**, following the same protocol as
   planning clarification (Step 4 of the planning protocol).
5. After all questions are resolved, ask: **"Should I write this charge to disk?"**
6. **STOP. Wait for user confirmation.**
7. On confirmation, write `charge.md` with the finalized content.
8. Present the written charge and continue directly to **Step C** (validate and route).

### Step C: Validate and route

Use the charge file located in Step A for all subsequent references to "the charge."

1. **Charge validation.** Read the charge file. Verify:
   - `Name:` is not `<REPLACE>` or blank.
   - `Project Name:` is not `<REPLACE>` or blank.
   - Other Configuration fields may be blank (they have defaults or are optional).
   - `Deployment:` may be blank (default: no deployment steps).
   - If validation fails, stop and tell the user which fields need to be completed.

   1.5 **Plan tier check.** Read `~/.claude/pcv-config.json`.
   - **If the file does not exist or is malformed:** Ask the user:
     > "Which Claude plan are you using? All plans can access all models, but
     > your plan's token budget affects how aggressively PCV recommends
     > higher-cost configurations like Opus agents."
     >
     > (a) Pro — $20/month
     > (b) Max 5x — $100/month
     > (c) Max 20x — $200/month
     > (d) API / pay-as-you-go

     **STOP. Wait for the user's response.**

     On answer, write `~/.claude/pcv-config.json`:
     ```json
     {
       "plan_tier": "[pro|max_5x|max_20x|api]",
       "plan_tier_set_date": "[YYYY-MM-DD]"
     }
     ```
   - **If the file exists and contains a valid `plan_tier`:** Read it silently.
     If `plan_tier_set_date` is older than 6 months, note: "Your plan tier was
     set on [date]. Would you like to update it?" (non-blocking).
   - The plan tier value is available to the planning protocol's Step 1.5 for
     agent configuration proposals.

2. **Git setup.** Perform once per project. **Do NOT use `cd` in any Bash command —
   always operate from the current working directory.**
   - Use Glob to check for `.git` in the current directory. Do NOT use Bash for this check.
   - If `.git` exists, run `git remote -v`. If remotes found, inform the user:
     "This directory is connected to a remote repository at [URL]. Planning
     documents created here would be included in future pushes. Would you like
     to proceed here, or work from a separate directory?" Wait for response.
   - If no `.git` in current directory, **check parent directories** for `.git` by
     walking up: parent, grandparent, etc. Use Glob for each level. Stop at
     filesystem root or after 5 levels.
     - **If parent `.git` found:** Inform the user: "This directory is within a Git
       repository rooted at `[parent path]`. Commits will be tracked there." Log
       this in the decision log. Do NOT run `git init`.
     - **If no `.git` anywhere:** Ask the user: "No Git repository found. Would you
       like to initialize one here, or skip Git tracking for this project?" Wait
       for response. If the user chooses to skip, log this in the decision log and
       proceed without Git.

3. **Phase detection and progress display (v3.9).**

   ### 3.0 Lite Project Detection (v3.10)

   Before checking for multi-phase or single-phase structure, check for PCV Lite:

   - **Lite indicator:** `plans/lite-plan.md` exists in the current directory.
   - **Precedence rule:** If both `plans/lite-plan.md` AND `plans/make-plan.md` exist,
     treat as Lite and display a warning: "Both `lite-plan.md` and `make-plan.md`
     found — routing as Lite project. Delete `lite-plan.md` if you intend to use
     full PCV."

   If Lite detected, skip multi-phase and single-phase detection. Go to §3.5 (Lite
   Progress Display).

   If no `lite-plan.md`, proceed to §3.1 (Multi-Phase Root Detection) as before.

   ### 3.1 Multi-Phase Root Detection

   Before displaying progress, check for multi-phase project structure. Use Glob or
   file checks to determine if this is a multi-phase project:

   - **Multi-phase indicator:** The directory contains at least one subdirectory
     that has its own `charge.md` AND a `plans/` subdirectory (phase subfolder),
     AND the project root contains `plans/logs/master-log.md`.
   - **Single-phase indicator:** None of the above apply, OR `master-log.md` does not exist.

   Store the result for routing in sub-step 3.2 below.

   ### 3.2 Master Progress Display (v3.9)

   If multi-phase project root detected in 3.1:

   **Read phase information** from each phase subfolder:
   - Phase name from `charge.md` (Name field)
   - Agent config summary from the phase's decision log (look for Agent Configuration entry)
   - Phase completion status from `plans/logs/` directory and decision log

   **Determine milestone status for each phase** (same as single-phase logic):
   - **Charge validated:** Phase has `charge.md`
   - **MakePlan approved:** Phase has `plans/make-plan.md`
   - **ConstructionPlan approved:** Phase has `plans/construction-plan.md`
   - **Construction:** Phase decision log contains "Construction Complete" OR deliverables exist
   - **Verification complete:** Phase decision log contains "Phase Complete" or "Project Closeout"

   **Display master progress in this format:**

   ```
   PCV v[version] — [Project Name] (Multi-Phase)

   Phase 1: [Name] [agent config summary]
     ■ Charge validated
     ■ MakePlan approved
     ■ ConstructionPlan approved
     ■ Construction
     ■ Verification complete

   Phase 2: [Name] [agent config summary]
     ■ Charge validated
     ■ MakePlan approved
     □ ConstructionPlan approved
     □ Construction
     □ Verification complete

   Phase 3: [Name] (tentative)
   Phase 4: [Name] (tentative)
   ```

   Use ■ for completed milestones, □ for incomplete. Tentative phases (not yet
   planned) show only the name without milestone checklists. After display,
   determine which phase is active (earliest incomplete phase) and route accordingly.

   ### 3.3 Single-Phase Progress Display

   If single-phase or phase subfolder detected (see 3.4 below):

   Use Glob or Bash to survey `plans/` for file existence. **Always check disk state
   with a tool call — never infer from conversation history.**

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

   ### 3.4 Phase Subfolder Routing (v3.9)

   When `/pcv` is invoked inside a phase subfolder (detected by checking parent
   directory for `plans/logs/master-log.md`), display single-phase progress for
   this phase only (standard display from 3.3 above). Route to appropriate protocol
   as normal. After routing, add this note:

   > "This phase is part of a multi-phase project. Use `/pcv` from the project root
   > to see all phases and navigate between them."

   **Always display the progress checklist before routing.** Then apply:

   **Note:** If `plans/lite-plan.md` exists, Lite routing (§3.5) takes precedence
   over this table. The table below applies only to full-PCV and multi-phase projects.

   | State | Action |
   |:------|:-------|
   | No `make-plan.md` | Start/resume **Planning**. Load `planning-protocol.md`. |
   | `make-plan.md` exists, no `construction-plan.md` | Ask: "A MakePlan exists. Are you resuming planning, or has this been approved and you're ready to proceed?" |
   | Both exist, scope is verification-only | Load `verification-protocol.md`. |
   | Both exist, construction not complete | Assess construction progress. Present status summary. Load `construction-protocol.md`. |
   | Both exist, construction complete, verification not complete | Load `verification-protocol.md`. |
   | **All milestones complete** | **Completed project** (see sub-steps 3a and 3b below). |

   ### 3.5 Lite Progress Display (v3.10)

   If Lite project detected in §3.0:

   Display a compressed 3-milestone checklist:

   ```
   PCV v[version] — [Project Name] (Lite)
   [■/□] Charge validated
   [■/□] Lite Plan approved
   [■/□] Verification complete
   ```

   Determine status:
   - **Charge validated:** The charge file passed validation in sub-step 1 above.
   - **Lite Plan approved:** `plans/lite-plan.md` exists.
   - **Verification complete:** Decision log contains a "Project Closeout" entry.

   **Routing table for Lite projects:**

   | State | Action |
   |:------|:-------|
   | No `lite-plan.md` | Start planning (Lite detection happens during planning). Load `planning-protocol.md`. |
   | `lite-plan.md` exists, no closeout | Inline construction and verification. Load `construction-protocol.md` (Lite path). |
   | All milestones complete | Completed Lite project. Offer version chain or reopen (same as §3a/3b). |

   ### 3a. Revision Cycle (completed project — version chaining)

   When all five milestones are complete, the project has finished a full PCV cycle.
   Prompt the user:

   > "This project completed a full PCV cycle. Would you like to:
   > (a) Start a new revision cycle (creates a versioned sibling folder), or
   > (b) Reopen for fixes (append to existing logs)?"

   **STOP. Wait for the user's response.**

   - **If (b):** Go to sub-step 3b (Reopen for Fixes).
   - **If neither:** Acknowledge and stop.
   - **If (a):** Perform the version chaining restructure:

   **First revision (no existing `v*/` siblings):**
   1. Inform user: "Starting version chain. This will restructure the current
      directory into `v1/` (current project) and `v2/` (new revision)."
   2. **Dry-run:** Use Glob to inventory all files/directories in the current
      directory (excluding `.git/` internals). Present the list to the user:
      > "The following will be moved to `v1/`: [file list]. Proceed?"
   3. **STOP. Wait for user confirmation.**
   4. If Git is available, commit checkpoint:
      `"PCV: pre-restructure checkpoint for [Project Name]"`
   5. **Copy phase:** Copy all project contents (charge, plans/, deliverables,
      .claude/, idea.md, CLAUDE.md, etc.) into `v1/` subfolder using Read/Write
      tools. For `.git/`, use Bash `git clone` from the current directory into
      `v1/` to preserve history, or skip `.git/` if not present.
   6. **Verify phase:** Glob `v1/` to confirm all files present. Compare file
      count against the dry-run inventory.
   7. **Delete phase:** Remove originals from the root (only after verify
      succeeds). Do NOT delete `v1/` itself.
   8. Create parent `CLAUDE.md` with project identity and version chain context:
      ```
      # [Project Name] — Version Chain
      Active versions in this directory. Each `vN/` folder is an independent
      PCV workspace.
      ```
   9. Scaffold `v2/` as sibling: `idea.md`, `charge.md` (template with Prior
      Work pre-filled as `../v1`), `.claude/settings.json` (full permissions),
      `plans/.gitkeep`, `CLAUDE.md`.
   10. Message:
       > "Project restructured. Previous work archived to `v1/`.
       > Describe your revision goals in `v2/idea.md` and let me know when ready."
   11. **STOP.**

   **Subsequent revisions (existing `v*/` siblings):**
   1. Determine next version number N+1 by scanning for `v*/` directories.
      Sort numerically and use max + 1.
   2. Scaffold `vN+1/` as sibling with Prior Work pointing to `../vN`.
   3. Message:
      > "Fill in `vN+1/idea.md` with your revision goals and let me know
      > when ready."
   4. **STOP.**

   ### 3b. Reopen for Fixes (completed project — lightweight)

   When the user chooses to reopen for fixes instead of a full revision cycle:

   1. Append a "Reopened for Fixes" entry to the decision log:
      ```markdown
      ## Reopened for Fixes — [Date]

      **Reason:** [Ask user what issues they encountered]

      ---
      ```
   2. **STOP. Wait for user to describe the issues.**
   3. For each issue:
      - Fix it per the user's direction.
      - Log the fix in the decision log as a post-closeout fix:
        ```markdown
        ## Post-Closeout Fix — [Date]

        **Issue:** [Description]
        **Fix:** [What was changed]
        **Files affected:** [List]

        ---
        ```
      - Append the fix to the build record (if one exists) under a
        "Post-Closeout Fixes" section.
   4. When all fixes are complete, append a "Project Re-Closeout" entry to the
      decision log. Git commit if available.

4. **Load the appropriate protocol file.** Read the protocol file from this skill's
   directory (`~/.claude/skills/pcv/`) and follow its instructions. Only one protocol
   is in context at a time.

---

## 2. Phase Summaries

These are brief overviews. Full instructions are in each protocol file.

### Planning Phase (`planning-protocol.md`)
Recommended effort: **high/max**
- Read charge, resolve working directory, validate paths (relative paths resolved
  to absolute for session use).
- Dispatch `pcv-research` agent for prior work analysis (if applicable) — returns
  structured inventory, pattern-specific findings, three-category classification.
- Identify deliverable patterns (Code, Prose, Mathematical, Design-and-Render).
- Sequential clarification: one question at a time, dependency-ordered.
- Agent configuration proposal: PCV proposes model tier, effort level, and context
  window for each agent role based on charge analysis and plan tier. Human approves
  or overrides. Approved configuration is recorded in the decision log.
- Draft MakePlan → Critic review → Compliance checklist → **Gate 1: MakePlan Approval**.
- Draft ConstructionPlan (or minimal verification-only file) → Planning artifact gate
  (Pattern 4 wireframes, Pattern 3 formulations, Pattern 1 test specs) →
  **Gate 3: ConstructionPlan Approval**.
- Commit approved plans to Git if available.

### Construct Phase (`construction-protocol.md`)
Recommended effort: **medium**
- Resolve working directory from charge.
- Baseline copy if carrying forward prior work.
- Dispatch `pcv-builder` agent per component in dependency order — one at a time,
  wait for completion before dispatching next. Builder model and effort come from
  the approved Agent Configuration (v3.7 defaults if no configuration entry exists).
- Mid-project revision: if 2+ builder deviations on a multi-component project,
  PCV proposes configuration revision for remaining components.
- Log deviations with human approval. Commit at milestones.
- Generate initial build record (`plans/build-record.md`) capturing files modified,
  design decisions made during construction, deviations, and lessons learned.

### Verify Phase (`verification-protocol.md`)
Recommended effort: **medium**
- Dispatch `pcv-verifier` agent with pattern-specific instructions for each
  applicable deliverable pattern. Verifier model and effort come from the approved
  Agent Configuration (v3.7 defaults if no configuration entry exists).
- Append verification fixes to the build record as they occur.
- Map each Success Criterion to deliverable components.
- Compare deliverables against planning artifacts.
- **Acceptance testing** — optional hands-on user evaluation with pattern-appropriate
  MVP suggestions. Fixes logged in decision log and build record.
- Export if configured. Final commit.
- Finalize build record: update verification status, prompt user for additional notes,
  update open items. Decision log closeout.
- **Project summary** generated at closeout (`plans/project-summary.md`) — focuses
  on deliverable content and user decisions, not PCV process details.
- **Deployment** — automatic execution of mechanical deployment actions when charge
  `Deployment:` field is populated. Content-heavy updates flagged as follow-up.

### Phase Transition (v3.9) (`phase-transition-protocol.md`)
Recommended effort: **medium**
- At the completion of a phase in a multi-phase project, read the phase transition
  protocol. This protocol guides phase closeout, update of the tentative phase plan,
  and scaffolding of the next phase subfolder.

### PCV Lite (`planning-protocol.md`, `construction-protocol.md`, `verification-protocol.md`)
Recommended effort: **medium**
- Compressed two-gate workflow for simple projects.
- Single combined artifact `plans/lite-plan.md` replaces MakePlan + ConstructionPlan.
- Critic subagent dispatched (Haiku) for independent review.
- Inline construction (no builder subagent).
- Inline verification by default; subagent for Pattern 1 (Code) or Pattern 3 (Math).
- Project summary generated at closeout (deliverable-focused, all project types).
- Deployment actions at closeout (when `Deployment:` field populated).

---

## 3. CLAUDE.md Template

When scaffolding, create `CLAUDE.md` with this content:

```
# <Project Name>
Language: <Language>
When compacting, preserve decision log (plans/logs/decision-log.md) and all files in plans/.
```

This file contains project identity and a compaction-preservation instruction —
no PCV references, no methodology instructions. Under 5 lines. The user
customizes it after scaffolding.

---

## 4. Charge Template

When scaffolding, create `charge.md` with this content:

```markdown
# Project Charge

## Configuration
Name: <REPLACE>
Project Name: <REPLACE>
Project Directory:
<!-- Path to the folder where code/deliverables live.
     Absolute path for external locations. Relative path (from this file)
     for sibling/child directories. Leave blank if this directory IS the project. -->
Export Target:
<!-- Path to a separate folder where finished files should be copied
     after verification. Absolute for external locations, relative for
     siblings. Leave blank if deliverables stay in the project directory. -->
Prior Work:
<!-- Path(s) to previous versions or reference files to build on.
     Absolute for external locations. Relative for sibling versions
     (e.g., ../v1). Leave blank if starting from scratch. -->
Deployment:
<!-- Where is this project deployed or published? (e.g., GitHub Pages,
     npm, standalone repo). Leave blank if deliverables stay local.
     When populated, PCV prompts for deployment actions at closeout. -->

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
  Accepts absolute or relative paths.
- **Export Target:** Where verified deliverables are copied during Verify. Blank = no export.
  Accepts absolute or relative paths.
- **Prior Work:** Path(s) to previous versions or reference material. Blank = starting
  from scratch. Accepts absolute or relative paths.
- **Deployment:** Where the project is deployed/published. Blank = no deployment steps. When populated, verification closeout includes an interactive deployment checklist.

---

## 4a. Idea Template

When scaffolding, create `idea.md` with this content:

```markdown
<!-- Describe your project idea here. Be informal — PCV will generate
     a structured charge from this. Include what you want to build,
     any constraints you know about, and what success looks like. -->
```

---

## 5. Permission Settings

PCV requires Read, Write, Glob, and Grep access to function at all — these are
essential for every phase of the workflow. In v3.4, general-purpose permissions
were deferred to `/pre-approve` at construction time, but this only caused repeated
permission prompts without adding security value, since the user has already opted
into PCV by invoking `/pcv`. All necessary permissions are now added at scaffold
to eliminate this friction.

Technology-specific permissions (e.g., `Bash(julia *)`, `Bash(npm *)`) are not
added at scaffold — they are identified from the ConstructionPlan and added at
the Gate 3 transition (see construction protocol Step 2.5).

### Scaffolding procedure (Step B)

When creating `.claude/settings.json` during scaffold:

1. **If the file already exists**, read it and preserve all existing entries and
   structure (`deny`, `hooks`, etc.). Add the permission entries below if not
   already present.
2. **If the file does not exist**, create it with the full permission set:
   ```json
   {
     "permissions": {
       "allow": [
         "Read(~/.claude/agents/pcv-critic.md)",
         "Read(~/.claude/agents/pcv-research.md)",
         "Read(~/.claude/agents/pcv-builder.md)",
         "Read(~/.claude/agents/pcv-verifier.md)",
         "Read(~/.claude/skills/pcv/*)",
         "Read(**)",
         "Write(**)",
         "Glob(*)",
         "Grep(*)",
         "Bash(git *)"
       ]
     }
   }
   ```

**No other Bash commands should be needed.** PCV uses only internal tools (Read,
Write, Glob, Grep) for file operations. Directories are created implicitly by
writing files into them — do NOT use `mkdir` via Bash.

---

## 5a. Permission Settings for Multi-Phase Projects (v3.9)

When scaffolding a multi-phase project or phase subfolder, apply the same
`.claude/settings.json` permission set as single-phase (above). No additional
permissions are required for multi-phase operations.

---

## 6. Protocol Loading

When transitioning between phases:
- **Planning → Construct:** Read `~/.claude/skills/pcv/construction-protocol.md` and follow it.
- **Planning → Verify (verification-only scope):** Read `~/.claude/skills/pcv/verification-protocol.md` and follow it.
- **Construct → Verify:** Read `~/.claude/skills/pcv/verification-protocol.md` and follow it.
- **Phase complete → Phase Transition (v3.9):** Read `~/.claude/skills/pcv/phase-transition-protocol.md` and follow it.

Each protocol file ends with a transition instruction. Follow it.

---

## 7. Behavioral Constraints

- PCV is **always opt-in**. Never block normal Claude Code work.
- If a user describes a complex project and has not invoked PCV, you may suggest it
  **once**. If declined or ignored, do not repeat.
- The main PCV workflow runs in the main conversation context, never as a subagent.
- PCV dispatches subagents for context isolation and token efficiency. Each agent's
  behavioral instructions are in `~/.claude/agents/` and must be Read and inlined in
  the Agent tool prompt since custom agent types are not directly spawnable via
  `subagent_type`. The four agents are:
  - **`pcv-critic`** (Planning) — Adversarial review of MakePlan. Always Haiku, always dispatched.
  - **`pcv-research`** (Planning) — Prior-work analysis. Model and dispatch mode
    (inline or subagent) determined by approved Agent Configuration.
  - **`pcv-builder`** (Construction) — Per-component builds, dispatched sequentially.
    Model determined by approved Agent Configuration.
  - **`pcv-verifier`** (Verification) — Pattern-specific verification.
    Model determined by approved Agent Configuration.
- If a subagent fails to spawn or Claude builds inline instead of dispatching, this is
  acceptable — the work product is identical, only token efficiency is reduced.
- All file operations for baseline copy and export must use internal Read/Write tools
  or cross-platform scripting — never OS-specific shell commands (`cp`, `copy`).
- Git commits happen at defined milestones with descriptive messages. Git is silent —
  the user does not interact with it.
- **Never use `cd` in Bash commands.** Always operate from the current working
  directory. Compound Bash commands with `cd` trigger security prompts in Claude Code.
  Use absolute paths if needed, or rely on Read/Write/Glob tools instead of Bash.

---

## 8. Multi-Phase Scaffolding (v3.9)

When the user accepts a multi-phase proposal during planning, PCV scaffolds the
project-level structure:

### 8.1 Project-Level Scaffolding

1. **Create project-level charge.md** with Multi-Phase Configuration section
   (includes reference to tentative phase plan in the upcoming MakePlan).
2. **Create project-level plans/make-plan.md** — includes a Tentative Phase Plan
   section (per spec §9.2). Mark all phases after Phase 1 as "tentative."
3. **Create plans/logs/master-log.md** with initial entry:
   ```markdown
   # Master Decision Log — [Project Name]

   ## Multi-Phase Project Initiated — [Date]

   **Phase structure:** [Number of planned phases]
   **Phase 1 focus:** [Brief description]

   ---
   ```
4. **Update project-level .claude/settings.json** to full permissions (same as single-phase).

### 8.2 Phase 1 Subfolder Scaffolding

After project-level scaffolding, scaffold Phase 1 subfolder:

1. **Create `phase-1-[name]/` folder** (use descriptive name from tentative phase plan).
2. **Create phase-specific `charge.md`** — fully specified charge for Phase 1 only.
3. **Create `CLAUDE.md`** with phase identity (see Section 3 template, using phase name).
4. **Create `plans/.gitkeep`** to establish the plans directory.
5. **Create `.claude/settings.json`** with full permissions.
6. **Continue with planning for Phase 1** — do NOT scaffold Phase 2+ subfolders yet.

### 8.3 Mid-Project Conversion to Multi-Phase (v3.9)

If a single-phase project needs to convert to multi-phase mid-stream (Path 3 from
the enhancement spec), use the same safe restructure protocol as version chaining:

1. **Dry-run phase:** Inventory current project files.
2. **Confirmation phase:** Present list to user and await approval.
3. **Copy phase:** Copy all current project contents into `phase-1-[name]/` subfolder.
4. **Verify phase:** Confirm files in Phase 1 subfolder match the inventory.
5. **Delete phase:** Remove originals from project root (only after verify succeeds).
6. **Create project-level structure** (§8.1 above) with master-log.md and project-level MakePlan.
7. **Resume planning** for Phase 1 in its new subfolder.

---
