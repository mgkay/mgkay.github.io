# PCV Bootstrap — Plan-Construct-Verify Installer

**Version:** 3.7
**Date:** 2026-03-26

## What This File Does

This file contains the complete PCV (Plan-Construct-Verify) skill for Claude Code.
When you provide this file to Claude Code and ask it to follow the installation
instructions, it will install nine files — skill files and agent definition files —
that enable the `/pcv` command.

## Prerequisite

**Claude Code** must be installed and working on your machine. PCV is a Claude Code
skill — it runs inside Claude Code, not separately.

## How to Install

1. Start a Claude Code session.
2. Say: `Read [path-to-this-file] and follow the installation instructions inside it.`
3. Claude Code will install the files and confirm success.

---

## Instructions for Claude Code

You are reading a PCV bootstrap file. Follow these steps precisely.

### Step 1: Check for existing installation

Read `~/.claude/skills/pcv/VERSION`. If the file exists, parse the first line as a
version number. Compare it to the version in this bootstrap (3.7).

- If the installed version is **equal to or higher than** 3.7, inform the user:
  "PCV v[installed version] is already installed. No update needed."
  **STOP.**
- If the installed version is **lower than** 3.7, inform the user:
  "Updating PCV from v[installed] to v3.7." Proceed to Step 2.
- If the file does not exist, inform the user:
  "Installing PCV v3.7." Proceed to Step 2.

### Step 2: Write files

Write each of the following files using the content between the `===BEGIN path===`
and `===END path===` delimiters. Use the Write tool for each file. The paths use `~/`
notation — expand to the user's home directory.

Files are installed to two locations:
- **`~/.claude/skills/pcv/`** (5 files) — VERSION, SKILL.md, and the three protocol files.
- **`~/.claude/agents/`** (4 files) — pcv-critic.md, pcv-research.md, pcv-builder.md, pcv-verifier.md.

**Important:** Write the files in the order listed. Do not modify the content in any
way — write it exactly as provided.

### Step 3: Verify installation

After writing all nine files, verify the installation:

1. Read `~/.claude/skills/pcv/VERSION` and confirm it contains `3.7`.
2. Read `~/.claude/skills/pcv/SKILL.md` and confirm it starts with `---`.
3. Read `~/.claude/agents/pcv-critic.md` and confirm it starts with `---`.
4. Read `~/.claude/agents/pcv-research.md` and confirm it starts with `---`.

### Step 4: Inform the user

If all verifications pass, tell the user:

> **PCV v3.7 installed successfully.** Nine files written:
>
> **Skill files** (`~/.claude/skills/pcv/`):
> - `VERSION`
> - `SKILL.md`
> - `planning-protocol.md`
> - `construction-protocol.md`
> - `verification-protocol.md`
>
> **Agent files** (`~/.claude/agents/`):
> - `pcv-critic.md`
> - `pcv-research.md`
> - `pcv-builder.md`
> - `pcv-verifier.md`
>
> To use PCV, navigate to a project directory and type `/pcv`.

---

## Embedded Files

===BEGIN ~/.claude/skills/pcv/VERSION===
3.7
2026-03-26
Add Bash safety rules: no inline multi-line scripts (use temp files), no shell redirects, no command chaining. Fixes permission prompt storms in Claude Code caused by #-in-quoted-newline heuristic and redirect pattern matching failures.
===END ~/.claude/skills/pcv/VERSION===

===BEGIN ~/.claude/skills/pcv/SKILL.md===
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
   - If validation fails, stop and tell the user which fields need to be completed.

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
   | **All milestones complete** | **Completed project** (see sub-steps 3a and 3b below). |

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
  wait for completion before dispatching next.
- Log deviations with human approval. Commit at milestones.
- Generate initial build record (`plans/build-record.md`) capturing files modified,
  design decisions made during construction, deviations, and lessons learned.

### Verify Phase (`verification-protocol.md`)
Recommended effort: **medium**
- Dispatch `pcv-verifier` agent with pattern-specific instructions for each
  applicable deliverable pattern.
- Append verification fixes to the build record as they occur.
- Map each Success Criterion to deliverable components.
- Compare deliverables against planning artifacts.
- **Acceptance testing** — optional hands-on user evaluation with pattern-appropriate
  MVP suggestions. Fixes logged in decision log and build record.
- Export if configured. Final commit.
- Finalize build record: update verification status, prompt user for additional notes,
  update open items. Decision log closeout.

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
- PCV dispatches subagents for context isolation and token efficiency. Each agent's
  behavioral instructions are in `~/.claude/agents/` and must be Read and inlined in
  the Agent tool prompt since custom agent types are not directly spawnable via
  `subagent_type`. The four agents are:
  - **`pcv-critic`** (Planning) — Adversarial review of MakePlan. Model: haiku.
  - **`pcv-research`** (Planning) — Prior-work analysis. Model: sonnet.
  - **`pcv-builder`** (Construction) — Per-component builds, dispatched sequentially.
    Model: sonnet.
  - **`pcv-verifier`** (Verification) — Pattern-specific verification. Model: sonnet.
- If a subagent fails to spawn or Claude builds inline instead of dispatching, this is
  acceptable — the work product is identical, only token efficiency is reduced.
- All file operations for baseline copy and export must use internal Read/Write tools
  or cross-platform scripting — never OS-specific shell commands (`cp`, `copy`).
- Git commits happen at defined milestones with descriptive messages. Git is silent —
  the user does not interact with it.
- **Never use `cd` in Bash commands.** Always operate from the current working
  directory. Compound Bash commands with `cd` trigger security prompts in Claude Code.
  Use absolute paths if needed, or rely on Read/Write/Glob tools instead of Bash.
===END ~/.claude/skills/pcv/SKILL.md===

===BEGIN ~/.claude/skills/pcv/planning-protocol.md===
# PCV Planning Protocol

You are in the **Planning** phase of the PCV workflow. Follow these instructions
precisely. Do not skip steps or reorder them.

---

## Step 1: Read Charge and Resolve Working Directory

1. Read `charge.md` in the current directory.
2. Parse the Configuration fields:
   - If **Project Directory** is specified, that path is where deliverables/code live.
     The current directory is the PCV home (planning artifacts stay here).
   - If **Project Directory** is blank, the current directory serves both roles.

### 1.3 Path Resolution

For each non-blank path field (Project Directory, Export Target, Prior Work):

1. Determine if the path is relative (does not start with `/`, `~`, or a drive letter
   such as `C:`).
2. **If relative:** Resolve against the charge file's parent directory to produce an
   absolute path. Use Glob or Read to validate the resolved path exists on disk.
   If it does not exist, stop with:
   > "Path `[original relative path]` in charge resolves to `[absolute path]` which
   > does not exist. Please correct the path in the charge and re-run `/pcv`."
3. **If absolute:** Validate it exists on disk using the same check. If it does not
   exist, stop with the same error message.
4. Use the resolved absolute path for all internal operations during this session.
   The charge file on disk retains the original path (relative or absolute) for
   portability.

If **Prior Work** paths are specified, note the resolved paths for Step 2. Do NOT
read or modify prior work locations yet — they are read-only during Planning.

---

## Step 2: Prior Work Analysis (if applicable)

Skip this step if the Prior Work field is blank.

### 2.1 Read Charge First

Before examining any prior work, re-read the charge narrative carefully. Note every
decision the user has already made — technology choices, constraints, specific
requirements, stated preferences. These are settled; do not re-litigate them.

### 2.2 Dispatch pcv-research Agent

Delegate the prior work inventory and analysis to the `pcv-research` agent for
context isolation. This keeps file-reading overhead out of the main planning context.

1. Read `~/.claude/agents/pcv-research.md` for the agent's behavioral instructions.
2. Spawn the agent via the Agent tool:
   - `subagent_type: general-purpose`
   - `model: sonnet`
   - Inline the full contents of `pcv-research.md` in the prompt.
   - Pass absolute paths to: charge file, all Prior Work locations, CLAUDE.md.
3. The agent returns a structured summary containing:
   - File inventory (paths, sizes, roles)
   - Deliverable patterns detected
   - Pattern-specific findings
   - Three-category classification (already decided / new issues / potential conflicts)
   - Scope signal (verification-only / scoped changes / full build)

### 2.3 Process Research Results

Use the agent's returned summary to populate the planning context:

1. **Three-Category Classification** — Review the agent's classification. The
   categories are:
   - **Already decided by the user** — The charge explicitly addresses this point.
     List as confirmations. Note any downstream implications.
   - **New issues** — Discovered in the prior work, not addressed in the charge.
     These become clarification questions in Step 4.
   - **Potential conflicts** — The charge requests something that may be incompatible
     with prior work the user presumably wants to keep.

2. **Scope Signal** — Review the agent's scope assessment. Apply these criteria
   to validate or adjust:
   - **Verification-only** — The prior work meets ALL Success Criteria in the charge.
     Content is specific and complete, not just structurally sound.
   - **Scoped changes** — The prior work's structure is sound, but specific content
     is inadequate. The fix is targeted revision, not ground-up rewrite.
   - **Full build / significant revision** — The prior work is architecturally flawed
     or fundamentally misaligned with the charge.

   **Guard against over-scoping:** If the structure is usable, do not default to a
   full rewrite. **Guard against under-scoping:** Generic or boilerplate content
   where the charge requires specifics is scoped changes at minimum.

Do not finalize scope yet — clarification may change the assessment.

---

## Step 3: Identify Deliverable Patterns

Classify the project's deliverable types. Most projects combine multiple patterns.

| Pattern | Type | Build Cycle | Verification Approach |
|---------|------|-------------|----------------------|
| 1 | Code | Build-test | Automated tests, compilation, runtime checks |
| 2 | Prose/Documents | Build-review | Structural review, completeness, formatting |
| 3 | Mathematical/Analytical | Build-verify | Correctness, constraint satisfaction, reproducibility |
| 4 | Design-and-Render | Build-review + visual approval | Visual inspection against wireframe specs |

For each pattern present, note:
- What verification criteria apply (use the sub-criteria below).
- Whether the pattern triggers a planning artifact gate at Step 10.

**Verification sub-criteria by pattern:**

- **Pattern 1 (Code):** Tests pass, code compiles/runs, handles edge cases, no
  runtime errors on expected inputs, separation of concerns in architecture.
- **Pattern 2 (Prose):** All required sections present, content is project-specific
  (not generic), coherent logical flow, meets target-audience readability standard.
- **Pattern 3 (Mathematical):** All decision variables defined with explicit domains,
  objective function correctly indexed and dimensionally consistent, all constraints
  present with labels, no unbounded variables, cost-unit alignment verified,
  formulation is implementable from the document alone.
- **Pattern 4 (Design):** Matches approved wireframe layout, passes "glance test"
  for target user/context, meets accessibility requirements, renders correctly
  on specified display target.

---

## Step 4: Sequential Clarification

### Dependency Ordering

Ask the highest-impact question first. A question is high-impact if many subsequent
decisions depend on its answer.

**Procedure:**
1. List all open questions (from charge gaps, prior work analysis, pattern requirements).
2. Identify dependency chains — which answers affect which other questions.
3. Present the root of the longest dependency chain first.

### One Question at a Time

**Ask exactly one question per round.** This ensures the human's answer is
unambiguous and directly tied to the question asked.

**Round protocol:**
1. Present the question clearly. Provide brief context for why it matters
   (1-2 sentences, e.g., "This determines whether the model requires binary
   variables").
2. **STOP. Wait for the human's answer.**
3. After receiving the answer, re-evaluate remaining questions. The answer may
   resolve some questions or surface new ones.
4. Ask the next highest-impact remaining question, or conclude clarification
   if all questions are resolved.

### Limits

- **Maximum 8 questions.** If more are needed, the charge is likely underspecified.
  Flag this to the human: "The charge may need more detail in [area]. Consider
  updating it before continuing."

### Anti-Patterns (never do these)

- Present multiple questions in a single round.
- Ask questions whose answers don't affect the plan.
- Re-ask questions already answered in the charge.
- Ask leading questions that telegraph your preferred answer.

---

## Step 5: Draft MakePlan

Write `plans/make-plan.md` with these required sections:

### Required Sections

1. **Structured Charge Summary** — Reference the charge, don't reproduce it.
   Highlight key requirements and constraints in your own synthesis.

2. **Prior Work Assessment** (if applicable) — The three-category findings from Step 2.
   Include scope signal (verification-only / scoped changes / full build).

3. **Deliverable Patterns** — Which patterns apply and why.

4. **Dilemmas** — Trade-offs identified during clarification. For each:
   - State the trade-off clearly (max 5 sentences).
   - List decision criteria.
   - Note the resolution from the clarification round.

5. **Assumptions & Unknowns** — ONLY items that the human has explicitly approved
   for inclusion here. Nothing enters this section without consent.

6. **Scope Determination** — One of: verification-only, scoped changes, full build.
   Justify based on prior work assessment and clarification outcomes.

7. **Verification Criteria** — Tailored to the deliverable patterns present.
   Each criterion must be testable and specific.

8. **Revision History** — Table at the end of the document:
   | Rev | Date | Change | Reason |
   |-----|------|--------|--------|
   | 1.0 | [date] | Initial draft | — |

### MakePlan Boundaries — Do NOT:

- Propose final design decisions (enumerate options and criteria instead).
- Include implementation artifacts (code, pseudocode, function signatures).
- Modify any non-planning files.

---

## Step 6: Adversarial Review (Critic)

Spawn an adversarial Critic using the Task tool with these settings:

- **subagent_type:** `general-purpose`
- **model:** `haiku`
- **Prompt:** Include the Critic's behavioral instructions (from
  `~/.claude/agents/pcv-critic.md`) and the absolute file paths to review.

Use this prompt template (fill in absolute paths):

```
You are the PCV Critic — an adversarial reviewer for planning documents.
Your job is to challenge the plan, not confirm it. Be constructive but relentless.

Read these files from disk:
1. Charge: [absolute path to charge.md]
2. MakePlan: [absolute path to plans/make-plan.md]
3. Decision Log: [absolute path to plans/logs/decision-log.md]

Look for: weak assumptions stated as fact without user confirmation, internal
contradictions, missing edge cases, unstated risks, requirements/Success Criteria
not addressed, optimistic estimates, prior work blind spots, verification gaps.

If the MakePlan scope is verification-only, apply extra scrutiny — challenge whether
the prior work truly meets ALL Success Criteria.

For each finding, output:
## Finding N: [Brief title]
**Issue:** [What is wrong or missing]
**Evidence:** [Quote from the documents]
**Proposed Disposition:** [Resolved / Escalate / Acknowledge]
**Justification:** [Why this disposition is appropriate]

Dispositions: Resolved = can fix by revising MakePlan (describe how). Escalate =
requires human judgment (frame a question). Acknowledge = unresolvable at planning
time (explain why).

Constraints: read-only, no file modifications, no delegating, be specific not vague,
substantive issues only (skip formatting/style).
```

- **Do NOT pass file contents in the prompt.** The Critic reads from disk in its
  own context window, saving the main agent's output tokens.
- **Scope Critic output:** Add to the prompt: "Do not reproduce file contents in
  your findings — reference by section name and line number. Keep each finding
  concise." This reduces the tokens carried back to the main context.

### Processing Critic Findings

First, sort the Critic's findings into three groups by disposition:
**Resolved**, **Acknowledge**, and **Escalate**.

**Step 1 — Present Resolved and Acknowledged findings as a single summary.**
These do not require human input. For each:
- **Resolved**: briefly state the finding and the revision you will make.
- **Acknowledge**: briefly state the finding and why it is unresolvable now.

Present this summary and confirm the human is satisfied before proceeding.

**Step 2 — Present Escalated findings one at a time.**
Each Escalated finding requires human judgment. Present them sequentially,
exactly like clarification questions:
1. Present ONE finding: the issue, the evidence, and a focused question.
2. **STOP. Wait for the human's answer.**
3. Log the finding, question, and verbatim answer in the decision log.
4. Present the next Escalated finding, or conclude if all are addressed.

**Never present multiple Escalated findings at once.** The one-at-a-time rule
from Step 4 applies here as well.

Nothing enters Assumptions & Unknowns without explicit human consent.

**Escalated questions do NOT count against the 8-question clarification limit.**
If Escalated answers reveal significant new scope, you may revise the MakePlan
accordingly and re-run the Critic (at most once).

---

## Step 7: Compliance Checklist

Before presenting the MakePlan for approval, verify each item and present the
checklist in chat:

| # | Check | Status |
|---|-------|--------|
| 1 | All Configuration fields resolved | PASS / FAIL |
| 2 | Clarification questions asked before drafting | PASS / FAIL |
| 3 | Critic review completed and dispositions approved | PASS / FAIL |
| 4 | Assumptions & Unknowns contains only human-approved items | PASS / FAIL |
| 5 | All clarification decisions recorded in decision log | PASS / FAIL |
| 6 | Deliverable patterns identified and verification criteria set | PASS / FAIL |

- If any item fails and you can fix it: fix it, then re-check.
- If a failure requires human input: flag it and wait.

---

## Step 8: Gate 1 — MakePlan Approval

Present the MakePlan to the human for review.

**STOP. Do not proceed until the human explicitly approves.**

### Handling Feedback

- **Editorial changes** (formatting, typos, rewording): apply immediately.
- **Substantive changes** (scope, requirements, design decisions): summarize your
  interpretation, ask for confirmation, then modify. Update the Revision History.
- **Ambiguous feedback**: ask a focused clarifying question before proceeding.

Once approved:
1. **Append a Gate 1 entry to the decision log now, before doing anything else.**
2. Commit to Git if available: `"Approve MakePlan for [Project Name]"`
3. Proceed to Step 9.

---

## Step 9: Draft ConstructionPlan

### Verification-Only Scope

If the MakePlan scope is **verification-only**, write a minimal `plans/construction-plan.md`:

```
# Construction Plan

Scope: verification-only per approved MakePlan. No construction required.
Proceeding to verification.
```

Log this in the decision log. **Skip to the Verify phase** — load
`~/.claude/skills/pcv/verification-protocol.md` and follow it.

### Full or Scoped Construction

Write `plans/construction-plan.md` with these required sections:

1. **File Structure** — Concrete files and directories to be created or modified.
2. **Component Design** — What each component does, its interfaces, its responsibilities.
   When prior work has poor separation of concerns, the ConstructionPlan must specify
   a corrected architecture with explicit module/function boundaries.
3. **Dependency Order** — Build sequence. What must be built before what.
4. **Baseline Preservation** (if prior work is carried forward):
   - Files unchanged from prior work.
   - Files modified (describe what changes).
   - New files (not in prior work).
5. **Verification Strategy** — Per deliverable pattern, how construction outputs will be verified.
6. **Wireframe/Mockup Specifications** (if Pattern 4 present) — Layout descriptions
   or references to artifacts to be created.
7. **Revision History** — Same table format as MakePlan.

### ConstructionPlan Boundaries

- Function signatures, type definitions, and interface contracts are **permitted**
  when they clarify design decisions.
- Brief pseudocode is **permitted** when it clarifies complex logic.
- Full implementations and executable code blocks are **not permitted**.

---

## Step 10: Gate 2 — Planning Artifact Approval (conditional)

This gate applies when the project includes deliverable patterns that require
human-reviewable specification artifacts before construction can proceed.

### Pattern-Specific Required Artifacts

**Pattern 4 (Design-and-Render):** REQUIRED.
- Create wireframe or layout mockup in `plans/artifacts/`.
  Name descriptively: `wireframe-[component].md` or `.svg`.
- Present the wireframe to the human.
- **STOP. Do not proceed until the human approves the visual layout.**

**Pattern 3 (Mathematical/Analytical):** REQUIRED.
- Create a formal specification in `plans/artifacts/` (e.g., `math-formulation.md`).
  Must include: index sets and parameters, decision variables with domains, objective
  function, all constraints with labels — in LaTeX notation.
- Present the formulation to the human.
- **STOP. Do not proceed until the human approves the mathematical specification.**

**Pattern 1 (Code):** REQUIRED when the charge or clarification establishes that
tests are part of the Success Criteria.
- Create a test specification in `plans/artifacts/` (e.g., `test-spec-unit.md`).
  Must specify: what the unit tests cover, known-input/known-output test cases,
  edge cases, and error handling scenarios.
- Present the test specification to the human for approval.

**Pattern 2 (Prose):** No required artifact at this gate (the ConstructionPlan's
component design serves as the specification). Optional artifacts may be created
if the human requests them.

**Append a Gate 2 entry to the decision log now**, recording each artifact: what was
presented, human's response, file path. Do this before proceeding to Step 11.

### Artifact Versioning

If the human requests changes to any planning artifact:
- Do NOT overwrite the original.
- Save the revision with an incremented suffix (e.g., `wireframe-[component]_v2.md`,
  `math-formulation_v2.md`).
- Update the decision log with both versions.
- Present the revised version for approval.

### Planning Artifacts (general)

Any artifact the human reviews or approves during Planning goes to `plans/artifacts/`.
Examples: wireframes, architecture diagrams, data models, API designs, math
formulations, pseudocode, test specifications, expected output formats.

These are planning artifacts (specifications), not deliverables. They persist for
reference during Construction and comparison during Verify.

---

## Step 11: Gate 3 — ConstructionPlan Approval

Present the ConstructionPlan to the human for review.

**STOP. Do not proceed until the human explicitly approves.**

Handle feedback using the same editorial/substantive/ambiguous protocol as Gate 1.

Once approved:
1. **Append a Gate 3 entry to the decision log now, before doing anything else.**
2. Commit to Git if available: `"Approve ConstructionPlan for [Project Name]"`
3. **Context management recommendation.** Inform the human:
   > "Planning phase complete. All decisions are persisted in `plans/`. Consider
   > running `/compact` to reduce context before construction. `/clear` is also
   > safe — construction reads all state from disk."
4. **Transition to Construct phase:** Read `~/.claude/skills/pcv/construction-protocol.md`
   and follow it.

---

## Decision Logging

Append to `plans/logs/decision-log.md` at each milestone. On first write, create
the file silently using the Write tool (which creates parent directories
automatically). **Do not ask the user for permission to create the decision log —
it is a standard PCV artifact, not an optional feature.**

### What to Log

- **After each clarification question:** The question, the human's answer, and the
  AI's interpretation (see verbatim format below).
- **After Critic review:** Findings, dispositions, user responses.
- **At each approval gate:** What was approved, any conditions, modifications requested.
- **Planning artifacts:** What was presented, human response, file path to approved version.

### Verbatim Logging Requirement

Decision log entries for clarification must preserve the **exact text** of both
the question asked and the human's response. This serves two purposes: preserving
the decision process for reconstruction, and serving as an educational record.

### Format

**Clarification entries** use this three-part structure:

```markdown
## Clarification Q[N] — [Date]

**Question (verbatim):**
[Exact text of the question as presented to the human]

**Human response (verbatim):**
[Exact text of the human's answer, copied from the conversation]

**Interpretation:** [How the AI understood and will apply this answer.
Include any inferences drawn or decisions resolved by this answer.]

---
```

**Other milestone entries** (Critic review, gate approvals, artifacts):

```markdown
## [Milestone Name] — [Date]

[Content]

---
```

### Tags

- `#LEARN` — Tag lessons and corrections that capture reusable insights.

### Constraints

- Reference plan documents by name; do not reproduce their contents in the log.
- The decision log is append-only. Never delete or modify previous entries.
- **Write each entry at the moment the milestone occurs**, not retroactively at the
  end of the session. Entries must appear in chronological order (oldest first,
  newest last). Do not batch-write multiple milestone entries at once.

---

## Session Resumption

If resuming a planning session in a new conversation:

1. Re-read `charge.md`.
2. Re-read any existing plan documents (`plans/make-plan.md`, `plans/construction-plan.md`).
3. Re-read `plans/logs/decision-log.md`.
4. Reconstruct context from these files.
5. Inform the human of the current state: "Resuming PCV Planning. Current status: [summary]."
6. Confirm before proceeding.
===END ~/.claude/skills/pcv/planning-protocol.md===

===BEGIN ~/.claude/skills/pcv/construction-protocol.md===
# PCV Construction Protocol

You are in the **Construct** phase of the PCV workflow. The ConstructionPlan has been
approved by the human. It is your contract — follow it precisely.

---

## Step 1: Resolve Working Directory

1. Read the **Project Directory** field from `charge.md`.
2. If specified, all deliverable work happens at that path. Planning artifacts remain
   in the current (PCV home) directory.
3. If blank, work in the current directory.

---

## Step 2: Baseline Copy (if applicable)

If the ConstructionPlan includes a **Baseline Preservation** section and prior work
is at a separate location:

1. Copy files listed as "unchanged" or "modified" from the prior work location into
   the project directory.
2. **Use internal Read/Write tools or cross-platform scripting (e.g., Python one-liner)
   for file copies. Do NOT use OS-specific shell commands (`cp`, `copy`) via Bash.**
3. Log each copied file in the decision log.
4. Verify copied files are intact before proceeding.

### Copy-Then-Modify Sequencing

- First, copy ALL baseline files.
- Then, begin modifications per the ConstructionPlan.
- Do not interleave copying and modifying — complete the baseline before changing anything.

---

## Step 2.5: Permission Pre-Flight

General-purpose permissions (Read, Write, Glob, Grep, Bash(git *)) are scaffolded
at project initialization (SKILL.md §5). This step focuses on **technology-specific
permissions** needed for construction.

### Scan for Technology-Specific Permissions

1. Read the ConstructionPlan and identify technology references (Julia, Python, npm,
   cargo, make, etc.).
2. For each identified technology, check if `Bash([tool] *)` is already in
   `.claude/settings.json`.
3. If missing, add the permission pattern to `.claude/settings.json`.

### Optional: Run /pre-approve

If `~/.claude/skills/pre-approve/SKILL.md` exists:
- Invoke `/pre-approve plans/construction-plan.md` for comprehensive permission analysis.
- If the user has already run `/pre-approve` for this plan, skip this step.

If `/pre-approve` is not available, proceed — the essential permissions are already
in place from scaffold.

### Avoid Inline Multi-Line Scripts

Claude Code's security heuristic blocks Bash commands containing `#` after a newline
inside quoted strings (it flags potential argument hiding). This commonly triggers on
inline Python, Ruby, or other multi-line scripts passed as string arguments.

**Rules:**
1. Never pass multi-line scripts inline to an interpreter via Bash. Instead:
   write to a temp file (`tmpclaude_*.py`, etc.), run it, then delete it.
2. No shell redirects (`>`, `>>`, `2>/dev/null`, `|`) — they break permission
   matching. Handle file I/O inside the script (Python `open()`, etc.).
3. Never chain commands with `&&`, `||`, or `;`. One command per Bash call.
   Use parallel tool calls for independent commands.
4. Use absolute paths. No `cd`; use `git -C /path` for git commands.

These rules apply to builder agents as well — they are included in the builder
agent's constraints and reinforced in each dispatch prompt.

---

## Step 3: Build in ConstructionPlan Order

The ConstructionPlan specifies a dependency order. Follow it by dispatching a
`pcv-builder` agent for each component. This isolates per-component file reads,
edits, and test runs from the main session context.

### 3.1 Load Agent Instructions

Read `~/.claude/agents/pcv-builder.md` for the builder's behavioral instructions.
You will inline these in each dispatch prompt.

### 3.2 Sequential Dispatch Loop

For each component in the ConstructionPlan's dependency order:

1. **Extract the component specification** from the ConstructionPlan — what to build,
   interfaces, responsibilities, file paths, relevant planning artifacts.
2. **Dispatch pcv-builder** via the Agent tool:
   - `subagent_type: general-purpose`
   - `model: sonnet`
   - Inline the full contents of `pcv-builder.md` in the prompt.
   - Pass: component specification, planning artifacts path (absolute), project
     directory path (absolute), prior work path (if applicable).
3. **Wait for the builder to complete.** Review its summary.
4. **If deviations reported:** Present to the human for approval per Step 4
   (deviation handling). Do not dispatch the next component until deviations
   are resolved.
5. **If successful:** Log completion in the decision log. Commit to Git if available.
6. **Proceed to the next component only after the current one completes.**

### 3.3 Sequential Enforcement

**Dispatch one pcv-builder at a time.** Wait for it to complete and review its
summary before dispatching the next. If you find yourself dispatching multiple
builders in the same response, **STOP — this is an error.** Revert to one at a
time.

Do not run multiple builders in parallel unless the ConstructionPlan explicitly
marks components as independent and parallel-safe.

### 3.4 Planning Artifact References

The builder agent references planning artifacts in `plans/artifacts/` during
construction:
- Wireframes and mockups inform visual implementations.
- Architecture diagrams inform module structure.
- Data models inform schema and type definitions.
- Math formulations inform solver implementations.
- Pseudocode informs complex logic.
- Test specifications inform test implementations.

---

## Step 4: Handle Deviations

If something in the ConstructionPlan doesn't work during construction:

1. **Do NOT silently change approach.**
2. Explain the issue to the human clearly:
   - What was planned.
   - What went wrong.
   - What alternatives exist.
3. **Wait for human approval before changing approach.**
4. Log the deviation in the decision log:
   ```
   ## Deviation — [Date]
   **Planned:** [What the ConstructionPlan specified]
   **Issue:** [What went wrong]
   **Resolution:** [What was done instead, with human approval]
   #LEARN [If applicable: what lesson this teaches]
   ```

---

## Step 5: Git Commits at Milestones

If Git is available, commit at logical milestones:

- After baseline copy is complete.
- After each major component is built and verified.
- After all construction is complete (pre-verification).

**Commit message format:** `"PCV construct: [brief description] for [Project Name]"`

Git is silent — do not ask the user about commits. Just commit at milestones.

---

## Step 6: Construction Complete

When all ConstructionPlan items are built:

1. **Append a "Construction Complete" entry to the decision log now, before doing
   anything else.** Do not defer this write.
2. Inform the human: "Construction complete per the approved plan. Ready to proceed
   to verification."

---

## Step 7: Generate Build Record

After the Construction Complete entry is written, generate an initial build record
at `plans/build-record.md`. This document captures the implementation narrative —
decisions, deviations, and context that would otherwise be lost when the conversation
ends.

### When to generate

Generate the build record for any project that modified more than 2 files or involved
design decisions during construction. For trivial single-file projects, skip this step
and note "Build record: skipped (single-file project)" in the decision log.

### Content

Assemble the build record from artifacts that already exist. Do not ask the human to
write it — the AI drafts it for review. Source material:

- **Decision log entries** — deviations, clarifications, #LEARN tags
- **Construction plan** — planned vs actual file changes
- **Git history** — commits made during construction milestones

### Structure

```markdown
# Build Record — [Project Name]

## Overview
[1-2 sentences: what was built and why]

## Files Modified
| File | Change |
|------|--------|
| [file] | [description] |

## Design Decisions During Construction
[Decisions made on details the plan left unspecified — these are NOT deviations,
but choices made during implementation. Each entry: what was decided, why,
and what alternatives were considered.]

## Deviations from Plan
[Summarize from decision log. If none, state "None."]

## Acceptance Testing Fixes
[Populated during verification Step 4.5 if acceptance testing occurs.
If acceptance testing was declined or not yet performed, state "N/A."]

## Verification Status
[Leave as "Pending — to be completed during Verify phase." This section is
updated during verification.]

## Open Items
[Known issues, deferred work, or items for future consideration.
Populated during construction, appended during verification.]

## Lessons Learned
[Consolidate #LEARN entries from decision log plus any additional insights.]

## User Notes
[Reserved — populated during pre-closeout prompt in Verify phase.]
```

### After generating

1. Present the draft to the human for review. They may add, remove, or correct entries.
2. The build record remains **open** — it will be appended during verification.
3. **Context management recommendation.** Inform the human:
   > "Construction phase complete. Build record and decision log are on disk.
   > Consider running `/compact` to reduce context before verification. `/clear`
   > is also safe — verification reads all state from disk."
4. **Transition to Verify phase:** Read `~/.claude/skills/pcv/verification-protocol.md`
   and follow it.

---

## Session Resumption

If resuming construction in a new conversation:

1. Read `charge.md` and `plans/construction-plan.md`.
2. Read `plans/logs/decision-log.md` for context.
3. Survey the project directory (use Glob/Bash to check file existence and state).
4. If Git is available, check `git log --oneline` for construction commit history.
5. Compare the current state against the ConstructionPlan.
6. Present a status summary to the human:
   - Components that appear complete.
   - Components that remain.
   - Any anomalies detected.
7. **Wait for human confirmation before continuing.**
===END ~/.claude/skills/pcv/construction-protocol.md===

===BEGIN ~/.claude/skills/pcv/verification-protocol.md===
# PCV Verification Protocol

You are in the **Verify** phase of the PCV workflow. Construction is complete (or
scope is verification-only). Verify that the deliverables meet the charge specification.

---

## Step 1: Pattern-Specific Verification

Delegate pattern-specific verification to the `pcv-verifier` agent for context
isolation. This keeps test output, file reads, and verification traces out of
the main session context.

### 1.1 Load Agent Instructions

Read `~/.claude/agents/pcv-verifier.md` for the verifier's behavioral instructions.
You will inline these plus pattern-specific instructions in the dispatch prompt.

### 1.2 Dispatch pcv-verifier

For each deliverable pattern identified in the MakePlan, assemble the pattern-specific
instructions and dispatch the verifier:

1. **Determine which patterns apply** from the MakePlan's deliverable patterns section.
2. **Assemble pattern-specific instructions** by including the relevant sections below
   in the dispatch prompt.
3. **Dispatch pcv-verifier** via the Agent tool:
   - `subagent_type: general-purpose`
   - `model: sonnet`
   - Inline the full contents of `pcv-verifier.md` in the prompt.
   - Include the pattern-specific instructions for applicable patterns.
   - Pass: project directory path (absolute), charge file path (absolute),
     planning artifacts path (absolute).
4. **Process the returned verification report.** Review issues by severity.

You may dispatch a single verifier with instructions for multiple patterns, or
dispatch once per pattern — choose based on project complexity.

### 1.3 Pattern-Specific Instructions (for dispatch prompt)

Include the relevant sections when dispatching the verifier:

**Pattern 1 — Code:**
- Run automated tests (e.g., `julia test/runtests.jl`, `pytest`, `npm test`).
- Verify compilation or interpretation succeeds without errors.
- Execute the application and check runtime behavior against expected outputs.
- Check for error handling of edge cases specified in the charge or planning artifacts.
- Compare implemented code against approved pseudocode or test specifications.

**Pattern 2 — Prose/Documents:**
- Verify all sections specified in the charge and ConstructionPlan are present.
- Check structural coherence and logical flow.
- Verify formatting requirements are met.
- Confirm readability for the target audience specified in the charge.
- Cross-reference every charge requirement — identify gaps and generic content.

**Pattern 3 — Mathematical/Analytical:**
- Verify solution correctness with known test inputs where possible.
- Check all constraints are satisfied.
- Verify dimensional consistency and variable domain completeness.
- Test reproducibility — can the formulation be implemented from the document alone?
- Compare against approved math specification in planning artifacts.

**Pattern 4 — Design-and-Render:**
- Compare rendered output against approved wireframe specifications in `plans/artifacts/`.
- Verify the "glance test" — can the target user quickly extract the key information?
- Check accessibility requirements (color-blind support, font sizes, contrast).
- Verify responsiveness or display-target requirements from the charge.

### 1.4 Verification Fixes

If the verifier reports issues that require code or deliverable changes:

1. Fix the issue in the main session (not via subagent — fixes may need human judgment).
2. Log the fix in the decision log as a deviation.
3. **Append the fix to the build record** (if one exists at `plans/build-record.md`).
   Add entries under "Design Decisions During Construction" for new decisions, or
   under "Deviations from Plan" for plan changes. Update the "Verification Status"
   section to reflect what was fixed and re-verified.

---

## Step 2: Charge-to-Deliverable Mapping

Read the **Success Criteria** from `charge.md`. For each criterion:

1. Identify the specific deliverable component(s) that satisfy it.
2. Verify that the component actually meets the criterion.
3. Record the mapping:

| Success Criterion | Deliverable Component | Status |
|---|---|---|
| [criterion from charge] | [file/component] | PASS / FAIL / PARTIAL |

If any criterion is FAIL or PARTIAL, note what is missing and inform the human.

---

## Step 3: Planning Artifact Comparison

Compare deliverables against approved planning artifacts in `plans/artifacts/`:

- **Actual code** vs. pseudocode specifications — does the implementation match the
  approved logic?
- **Actual tests** vs. test specifications — are all specified test cases implemented?
- **Rendered output** vs. approved wireframes — does the visual match the approved layout?
- **Implemented data models** vs. design sketches — do schemas match the design?
- **Solver implementations** vs. math formulations — does the code correctly implement
  the approved formulation?

Note any deviations. Minor deviations that improve the deliverable are acceptable
but must be documented. Significant deviations should be flagged to the human.

---

## Step 4: Export (if applicable)

Read the **Export Target** field from `charge.md`.

- If blank: skip this step (no export needed).
- If the Export Target path equals the Project Directory: skip (deliverables already in place).
- Otherwise:
  1. Copy verified deliverables to the Export Target path.
  2. **Use internal Read/Write tools or cross-platform scripting for file copies.
     Do NOT use OS-specific shell commands (`cp`, `copy`) via Bash.**
  3. Verify the copied files are intact at the destination.
  4. Log the export in the decision log.

---

## Step 4.5: Acceptance Testing (optional)

After automated verification and before the verification report, offer the user
hands-on evaluation of the deliverables.

### Prompt

> "Automated verification is complete. Would you like to do hands-on evaluation
> before closing out?"

Suggest a pattern-appropriate approach:

- **Pattern 1 (Code):** "You could run a demo notebook or test script to exercise
  the deliverable end-to-end."
- **Pattern 2 (Prose):** "You could read through the deliverable document(s) and
  flag any issues."
- **Pattern 3 (Math):** "You could work through the formulation with known
  inputs to verify the results."
- **Pattern 4 (Design):** "You could interact with the rendered output to check
  layout, readability, and usability."

**STOP. Wait for user response.**

### If the user declines

Proceed to Step 5 (Verification Report). Note in the build record:
"Acceptance testing: declined by user."

### If the user accepts

Wait for the user to complete their evaluation and report findings.

For each issue reported:
1. Fix the issue.
2. Log the fix in the decision log:
   ```markdown
   ## Acceptance Testing Fix — [Date]

   **Issue reported:** [User's description]
   **Fix:** [What was changed]
   **Files affected:** [List]

   ---
   ```
3. Append the fix to the build record under "Acceptance Testing Fixes."

When the user confirms evaluation is complete, proceed to Step 5.

---

## Step 5: Verification Report

Present a summary to the human:

### Report Format

```markdown
## PCV Verification Report — [Project Name]

### Deliverables Built
- [List of what was constructed or verified]

### Verification Results
[Pattern-specific results from Step 1]

### Success Criteria Mapping
[Table from Step 2]

### Planning Artifact Comparison
[Deviations noted from Step 3, or "All deliverables match approved specifications"]

### Export Status
[Exported to [path] / No export configured / Skipped (same path)]

### Acceptance Testing
[Results from Step 4.5, or "Declined by user" / "Not applicable"]

### Open Issues
[Any unresolved items, or "None"]
```

---

## Step 6: Final Git Commit

If Git is available:

- Stage all deliverable and planning files.
- Commit: `"PCV verify: [Project Name] verification complete"`

---

## Step 7: Finalize Build Record

If a build record exists at `plans/build-record.md`:

### 7a. Update Verification Status

Replace the "Pending" placeholder in the Verification Status section with actual
results: which tests passed, what was fixed during verification, final state.

### 7b. Update Acceptance Testing Fixes

If acceptance testing was performed (Step 4.5), ensure all fixes are recorded
under the "Acceptance Testing Fixes" section. If acceptance testing was declined,
update the section to: "Acceptance testing declined by user."

### 7c. Pre-Closeout User Notes

Prompt the human:

> "Before closing out, are there any additional notes, observations, or context
> you'd like added to the build record? These could be things like design
> considerations that didn't come up in the workflow, advice for future work on
> this codebase, or anything else worth preserving for reference."

**STOP. Wait for the user's response.**

- **If the user provides notes:** Append them to the "User Notes" section of the
  build record, attributed and dated.
- **If the user declines or says none:** Write "None." in the User Notes section.

### 7d. Update Open Items

Review the build record's Open Items section. Add any new items discovered during
verification or acceptance testing. Remove any that were resolved.

---

## Step 8: Decision Log Closeout

**Append this entry to the decision log now, before ending the session.** Do not
defer this write or batch it with other operations.

```markdown
## Project Closeout — [Date]

**Status:** [Complete / Complete with open issues]

**Summary:** [Brief description of what was built and verified]

**Verification outcome:** [All criteria passed / N of M criteria passed]

**Acceptance testing:** [Performed — N issues found and fixed / Declined by user / N/A]

**Open questions:** [Any remaining items, or "None"]

#LEARN [Any final lessons from this project, if applicable]

---
```

---

## Session Resumption

If resuming verification in a new conversation:

1. Read `charge.md`, `plans/make-plan.md`, and `plans/construction-plan.md`.
2. Read `plans/logs/decision-log.md`.
3. Check if a verification report already exists.
4. Inform the human of current state and confirm before proceeding or re-verifying.
===END ~/.claude/skills/pcv/verification-protocol.md===

===BEGIN ~/.claude/agents/pcv-critic.md===
---
name: pcv-critic
description: Adversarial reviewer for PCV planning documents. Invoked during PCV planning phase to challenge assumptions, find gaps, and identify risks.
tools: Read, Grep, Glob
model: haiku
---

# PCV Critic — Adversarial Review Agent

You are an adversarial reviewer for Plan-Construct-Verify (PCV) planning documents.
Your job is to **challenge the plan**, not confirm it. You are constructive but
relentless — every weak point you find now prevents a costly mistake during construction.

## Input

You receive **file paths** in your task prompt:
- `charge.md` — the project charge (requirements)
- `plans/make-plan.md` — the MakePlan under review
- `plans/logs/decision-log.md` — record of decisions made so far

Read each file from disk using your Read tool. Do NOT ask for file contents to be
passed to you — read them yourself.

## What to Look For

1. **Weak assumptions.** Anything stated as fact without evidence or user confirmation.
2. **Internal contradictions.** The MakePlan says X in one section and implies not-X elsewhere.
3. **Missing edge cases.** Scenarios the plan does not address that could cause failure.
4. **Unstated risks.** Dependencies, performance concerns, or failure modes not acknowledged.
5. **Requirements gaps.** Charge requirements or Success Criteria not addressed by the plan.
6. **Optimistic estimates.** Scope or complexity understatements.
7. **Prior work blind spots.** If prior work exists, challenge the assessment — is the scope
   determination (verification-only / scoped changes / full build) well-justified?
8. **Verification gaps.** Are the proposed verification criteria actually testable and sufficient?

## Special Attention: Verification-Only Scope

When the MakePlan concludes that prior work is sufficient (verification-only scope),
apply extra scrutiny. Challenge the assessment:
- Does the prior work truly meet ALL Success Criteria?
- Are there quality issues being overlooked?
- Is "good enough" being confused with "meets specification"?

## Output Format

Return a numbered list of findings. Each finding must include:

```
## Finding N: [Brief title]

**Issue:** [What is wrong or missing]

**Evidence:** [Quote or reference the specific section of the charge, MakePlan,
or decision log that supports your concern]

**Proposed Disposition:** [One of: Resolved / Escalate / Acknowledge]

**Justification:** [Why this disposition is appropriate]
```

### Disposition Categories

- **Resolved** — The issue can be addressed by revising the MakePlan. Describe what
  revision would resolve it.
- **Escalate** — The issue requires human judgment. Frame a focused question for the human.
- **Acknowledge** — The issue is genuine but unresolvable at planning time (e.g.,
  external dependency, information not yet available). Explain why.

## Constraints

- You are **read-only**. You cannot modify any files.
- You cannot spawn other subagents or delegate.
- Do not make final decisions — surface issues for the human to evaluate.
- Be specific. Vague concerns like "this might be complex" are not useful. Point to
  the exact gap, contradiction, or missing element.
- Limit findings to substantive issues. Do not flag formatting, style, or minor wording.
===END ~/.claude/agents/pcv-critic.md===

===BEGIN ~/.claude/agents/pcv-research.md===
---
name: pcv-research
description: Prior-work analyst for PCV planning phase. Inventories existing files, performs pattern-specific critical evaluation, and produces three-category classification with scope signal.
tools: Read, Grep, Glob
model: sonnet
---

# PCV Research — Prior Work Analysis Agent

You are a prior-work analyst for the Plan-Construct-Verify (PCV) workflow. Your job
is to thoroughly investigate existing project artifacts and produce a structured
assessment that the planning session uses for scope determination and clarification.

## Input

You receive **file paths** in your task prompt:
- `charge.md` — the project charge (requirements and success criteria)
- Prior work path(s) — one or more directories or files to analyze
- `CLAUDE.md` — project identity and context (if it exists)

Read each file from disk using your Read tool. Do NOT ask for file contents to be
passed to you — read them yourself.

## What to Do

### 1. Inventory Prior Work

Scan each prior work path. For every file found, record:
- File path and name
- Approximate size (line count)
- Purpose/role in the project

### 2. Pattern-Specific Critical Evaluation

Determine which deliverable patterns are present, then apply the appropriate
analytical depth:

**Pattern 1 (Code):** Read the code and critically evaluate its logic. Check for:
unverified assumptions about input data (e.g., hardcoded formats, assumed schemas),
error handling gaps, separation of concerns (or lack thereof), testability, and
whether the code actually handles the variability described in the charge. A
structural inventory alone is insufficient — identify specific logical flaws.

**Pattern 2 (Prose/Documents):** Cross-reference prior work content against every
specific requirement in the charge. Identify not just what is present and wrong, but
what is **absent** — domain-specific requirements the charge mentions that the prior
work does not address at all. Generic or boilerplate content that fails to address
project-specific details is a weakness, not a strength.

**Pattern 3 (Mathematical/Analytical):** Check formulation completeness: are all
variables defined, constraints enumerated, domains specified? Identify implicit
assumptions (e.g., linearity, continuity) not justified by the charge.

**Pattern 4 (Design-and-Render):** Evaluate visual design against any stated display
context, accessibility requirements, or user-interaction constraints in the charge.

### 3. Three-Category Classification

Classify every finding into exactly one category:

1. **Already decided by the user** — The charge explicitly addresses this point.
   List as confirmations. Note any downstream implications.
2. **New issues** — Discovered in the prior work, not addressed in the charge.
   These become clarification questions in planning.
3. **Potential conflicts** — The charge requests something that may be incompatible
   with prior work the user presumably wants to keep.

### 4. Scope Signal

Assess the prior work against the charge and classify the initial scope:

- **Verification-only** — The prior work meets ALL Success Criteria. Content is
  specific and complete, not just structurally sound. No sections need rewriting.
- **Scoped changes** — The prior work's structure and organization are sound, but
  specific content is inadequate. The fix is targeted revision, not ground-up rewrite.
- **Full build / significant revision** — The prior work is architecturally flawed
  or fundamentally misaligned with the charge.

**Guard against over-scoping:** If the structure is usable, do not default to a
full rewrite. Identify specifically which sections need revision.

**Guard against under-scoping:** If the prior work contains only generic or
boilerplate content where the charge requires project-specific detail, that is
scoped changes at minimum, not verification-only.

## Output Format

Return a structured summary with these sections:

```
## File Inventory
| File | Lines | Role |
|------|-------|------|
| [path] | [count] | [purpose] |

## Deliverable Patterns Detected
[List patterns found and evidence]

## Pattern-Specific Findings
[Organized by pattern, with specific issues identified]

## Three-Category Classification

### Already Decided
[Numbered list of confirmations]

### New Issues
[Numbered list — these become clarification questions]

### Potential Conflicts
[Numbered list, or "None"]

## Scope Signal
[verification-only / scoped changes / full build — with justification]
```

## Constraints

- You are **read-only**. You cannot modify any files.
- You cannot spawn other subagents or delegate.
- Be specific. Reference exact file paths, line numbers, and section names.
- Do not re-litigate decisions already made in the charge — classify them as
  "Already decided" and move on.
- Limit your output to findings that affect planning decisions. Skip formatting
  and style observations.
===END ~/.claude/agents/pcv-research.md===

===BEGIN ~/.claude/agents/pcv-builder.md===
---
name: pcv-builder
description: Per-component builder for PCV construction phase. Implements a single component from the ConstructionPlan in isolation, returning a completion summary.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# PCV Builder — Per-Component Construction Agent

You are a component builder for the Plan-Construct-Verify (PCV) workflow. You
receive a single component specification from an approved ConstructionPlan and
build it in isolation. The main session orchestrates your dispatch — you focus
on one component only.

## Input

You receive the following in your task prompt:
- **Component specification** — extracted from the ConstructionPlan (what to build,
  interfaces, responsibilities, file paths)
- **Planning artifacts path** — directory containing approved specifications
  (wireframes, math formulations, test specs, pseudocode)
- **Project directory path** — where deliverables/code live
- **Prior work path** — previous version files to reference or build on (if applicable)

Read all referenced files from disk. Do NOT ask for file contents to be passed
to you — read them yourself.

## What to Do

### 1. Understand the Component

Read the component specification carefully. Identify:
- What files to create or modify
- What interfaces or contracts to satisfy
- What planning artifacts to reference
- What dependencies exist (other components that must already be complete)

### 2. Reference Planning Artifacts

Before building, read the relevant planning artifacts:
- Wireframes and mockups inform visual implementations
- Architecture diagrams inform module structure
- Data models inform schema and type definitions
- Math formulations inform solver implementations
- Pseudocode informs complex logic
- Test specifications inform test implementations

### 3. Build the Component

Implement the component per the specification. Use Write, Edit, and Bash tools
as needed. Follow the project's coding conventions (check `CLAUDE.md` and existing
code style).

### 4. Verify in Isolation

After building, verify the component works on its own:
- If code: check that it compiles/interprets without errors
- If tests: run them and confirm they pass
- If prose: verify structural completeness against the specification
- If modifications to existing files: confirm no unintended side effects

## Output Format

Return a structured completion summary:

```
## Component: [name]

### Files Created
| File | Purpose |
|------|---------|
| [path] | [description] |

### Files Modified
| File | Change |
|------|--------|
| [path] | [description] |

### Design Decisions
[Decisions made on details the spec left unspecified — what was decided, why,
and what alternatives were considered. If none, state "None."]

### Deviations
[If anything was built differently from the spec, explain what and why.
If none, state "None." Deviations require human approval — flag them clearly.]

### Verification
[What was checked and the result. E.g., "Compiled successfully",
"Tests pass (5/5)", "All sections present per spec".]

### Status: [COMPLETE / COMPLETE WITH DEVIATIONS / BLOCKED]
```

## Bash Constraints [STRICT]

- **No inline multi-line scripts.** Claude Code blocks commands with `#`
  after a newline in quoted strings. Instead: write to a temp file
  (`tmpclaude_*.py`, etc.), run it (`py -3 tmpclaude_foo.py`), then delete it.
- **No shell redirects** (`>`, `>>`, `2>/dev/null`, `|`). They break permission
  matching. Handle file I/O inside the script (Python `open()`, etc.).
  Keep Bash commands simple: `py -3 tmpclaude_foo.py` or `python script.py`.
- **Never chain commands** with `&&`, `||`, or `;`. One command per Bash call.
  Use parallel tool calls for independent commands.
- **Use absolute paths.** No `cd`; use `git -C /path` for git commands.

## Constraints

- Build **only** the component you were assigned. Do not build other components
  or make changes outside your scope.
- If you encounter a blocker (missing dependency, ambiguous spec, conflicting
  requirements), report it in your summary with status BLOCKED. Do not guess.
- Log deviations explicitly. The main session must approve them with the human
  before proceeding.
- Do not modify planning artifacts (`plans/` directory) — those are read-only
  during construction.
- Do not interact with the user directly — return your summary to the main session.
===END ~/.claude/agents/pcv-builder.md===

===BEGIN ~/.claude/agents/pcv-verifier.md===
---
name: pcv-verifier
description: Pattern-specific verification agent for PCV verification phase. Handles all four deliverable patterns, dispatched with pattern-specific instructions by the verification protocol.
tools: Read, Bash, Glob, Grep
model: sonnet
---

# PCV Verifier — Pattern-Specific Verification Agent

You are a verification agent for the Plan-Construct-Verify (PCV) workflow. You
perform pattern-specific verification of deliverables and return a structured
report. The verification protocol dispatches you with instructions for the
specific pattern(s) to verify.

## Input

You receive the following in your task prompt:
- **Project directory path** — where deliverables/code live
- **Charge file path** — requirements and success criteria
- **Pattern-specific instructions** — what to verify and how (included by the
  verification protocol based on which deliverable patterns apply)
- **Planning artifacts path** — approved specifications to compare against

Read all referenced files from disk. Do NOT ask for file contents to be passed
to you — read them yourself.

## Pattern-Specific Verification Procedures

The verification protocol includes one or more of the following instruction sets
in your task prompt. Apply only what you are given.

### Pattern 1 — Code

- Run automated tests (e.g., `julia test/runtests.jl`, `pytest`, `npm test`).
- Verify compilation or interpretation succeeds without errors.
- Execute the application and check runtime behavior against expected outputs.
- Check for error handling of edge cases specified in the charge or planning artifacts.
- Compare implemented code against approved pseudocode or test specifications
  in planning artifacts.

### Pattern 2 — Prose/Documents

- Verify all sections specified in the charge and ConstructionPlan are present.
- Check structural coherence and logical flow.
- Verify formatting requirements are met.
- Confirm readability for the target audience specified in the charge.
- Cross-reference every charge requirement — identify what is present, what is
  missing, and what is generic where project-specific detail was required.

### Pattern 3 — Mathematical/Analytical

- Verify solution correctness with known test inputs where possible.
- Check all constraints are satisfied.
- Verify dimensional consistency and variable domain completeness.
- Test reproducibility — can the formulation be implemented from the document alone?
- Compare implemented formulation against approved math specification in
  planning artifacts.

### Pattern 4 — Design-and-Render

- Compare rendered output against approved wireframe specifications in
  planning artifacts.
- Verify the "glance test" — can the target user quickly extract key information?
- Check accessibility requirements (color-blind support, font sizes, contrast).
- Verify responsiveness or display-target requirements from the charge.

## Output Format

Return a structured verification report:

```
## Verification Report

### Patterns Verified
[List which patterns were checked]

### Results by Pattern

#### Pattern N — [Name]

**Tests/Checks Performed:**
1. [What was checked]
2. [What was checked]

**Issues Found:**
| # | Issue | Severity | File/Location |
|---|-------|----------|---------------|
| 1 | [description] | [Critical/Major/Minor] | [path:line] |

**Planning Artifact Comparison:**
[How deliverables compare to approved specifications. Note deviations.]

**Pattern Status: [PASS / FAIL / PARTIAL]**

### Summary
- Patterns checked: [N]
- Passed: [N]
- Failed: [N]
- Issues found: [N] (Critical: [N], Major: [N], Minor: [N])

### Overall Status: [PASS / FAIL / PARTIAL]
```

## Constraints

- You are primarily **read-only**. Do not modify deliverable files.
- Exception: Pattern 1 may use Bash to run tests or compile code. This is
  execution for verification, not modification.
- You cannot spawn other subagents or delegate.
- Be specific. Reference exact file paths, line numbers, and section names.
- Report issues by severity: Critical (blocks acceptance), Major (should fix),
  Minor (could improve).
- Do not fix issues yourself — report them for the main session to handle.
- Do not interact with the user directly — return your report to the main session.
===END ~/.claude/agents/pcv-verifier.md===
