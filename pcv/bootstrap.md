# PCV Bootstrap — Plan-Construct-Verify Installer

**Version:** 3.2
**Date:** 2026-02-24

## What This File Does

This file contains the complete PCV (Plan-Construct-Verify) skill for Claude Code.
When you provide this file to Claude Code and ask it to follow the installation
instructions, it will install six files that enable the `/pcv` command.

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
version number. Compare it to the version in this bootstrap (3.2).

- If the installed version is **equal to or higher than** 3.2, inform the user:
  "PCV v[installed version] is already installed. No update needed."
  **STOP.**
- If the installed version is **lower than** 3.2, inform the user:
  "Updating PCV from v[installed] to v3.2." Proceed to Step 2.
- If the file does not exist, inform the user:
  "Installing PCV v3.2." Proceed to Step 2.

### Step 2: Write files

Write each of the following files using the content between the `===BEGIN path===`
and `===END path===` delimiters. Use the Write tool for each file. The paths use `~/`
notation — expand to the user's home directory.

**Important:** Write the files in the order listed. Do not modify the content in any
way — write it exactly as provided.

### Step 3: Verify installation

After writing all six files, verify the installation:

1. Read `~/.claude/skills/pcv/VERSION` and confirm it contains `3.2`.
2. Read `~/.claude/skills/pcv/SKILL.md` and confirm it starts with `---`.
3. Read `~/.claude/agents/pcv-critic.md` and confirm it starts with `---`.

### Step 4: Inform the user

If all verifications pass, tell the user:

> **PCV v3.2 installed successfully.** Six files written:
> - `~/.claude/skills/pcv/VERSION`
> - `~/.claude/skills/pcv/SKILL.md`
> - `~/.claude/skills/pcv/planning-protocol.md`
> - `~/.claude/skills/pcv/construction-protocol.md`
> - `~/.claude/skills/pcv/verification-protocol.md`
> - `~/.claude/agents/pcv-critic.md`
>
> To use PCV, navigate to a project directory and type `/pcv`.

---

## Embedded Files

===BEGIN ~/.claude/skills/pcv/VERSION===
3.2
2026-02-24
Progress display on every invocation; revision cycle for completed projects.
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

**Argument:** `$ARGUMENTS`

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
Export Target:
Prior Work:

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

When scaffolding, create `.claude/settings.json` to pre-approve tool usage within
the project directory. This eliminates permission prompts during PCV execution.

```json
{
  "permissions": {
    "allow": [
      "Read(**)",
      "Write(**)",
      "Glob(*)",
      "Grep(*)",
      "Bash(git *)",
      "Read(~/.claude/skills/pcv/*)",
      "Read(~/.claude/agents/pcv-critic.md)"
    ]
  }
}
```

This allows reading, writing, searching, and Git operations within the project
directory, plus read access to the global PCV skill and agent files, all without
per-action prompts.

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
3. If **Prior Work** paths are specified, note them for Step 2. Do NOT read or modify
   prior work locations yet — they are read-only during Planning.

---

## Step 2: Prior Work Analysis (if applicable)

Skip this step if the Prior Work field is blank.

### 2.1 Read Charge First

Before examining any prior work, re-read the charge narrative carefully. Note every
decision the user has already made — technology choices, constraints, specific
requirements, stated preferences. These are settled; do not re-litigate them.

### 2.2 Inventory Prior Work

Read or scan each path listed in Prior Work. Produce a summary:
- What files/artifacts exist?
- What is the structure and organization?
- What is the overall quality and completeness?

**Pattern-specific analysis depth:**

- **Pattern 1 (Code):** Read the code and critically evaluate its logic. Check for:
  unverified assumptions about input data (e.g., hardcoded formats, assumed schemas),
  error handling gaps, separation of concerns (or lack thereof), testability, and
  whether the code actually handles the variability described in the charge. A
  structural inventory is insufficient — identify specific logical flaws.

- **Pattern 2 (Prose):** Cross-reference prior work content against every specific
  requirement in the charge. Identify not just what is present and wrong, but what
  is **absent** — domain-specific requirements the charge mentions that the prior work
  does not address at all. Generic or boilerplate content that fails to address
  project-specific details is a weakness, not a strength.

- **Pattern 3 (Mathematical):** Check formulation completeness: are all variables
  defined, constraints enumerated, domains specified? Identify implicit assumptions
  (e.g., linearity, continuity) not justified by the charge.

- **Pattern 4 (Design):** Evaluate visual design against any stated display context,
  accessibility requirements, or user-interaction constraints in the charge.

### 2.3 Three-Category Classification

Classify every finding from the prior work into exactly one category:

1. **Already decided by the user** — The charge explicitly addresses this point.
   List as confirmations. Note any downstream implications.
2. **New issues** — Discovered in the prior work, not addressed in the charge.
   These become clarification questions in Step 4.
3. **Potential conflicts** — The charge requests something that may be incompatible
   with prior work the user presumably wants to keep.

### 2.4 Scope Signal

Assess the prior work against the charge and classify the initial scope signal.
Apply these decision criteria:

- **Verification-only** — The prior work meets ALL Success Criteria in the charge.
  Content is specific and complete, not just structurally sound. No sections need
  rewriting — only verification that everything works/reads as specified.

- **Scoped changes** — The prior work's **structure and organization are sound**, but
  specific content is inadequate (generic, incomplete, or missing project-specific
  details). The fix is targeted revision of identified sections, not a ground-up
  rewrite. This is the correct scope when: the skeleton is usable but the substance
  needs work.

- **Full build / significant revision** — The prior work is architecturally flawed,
  fundamentally misaligned with the charge, or so inadequate that preserving its
  structure provides no advantage over starting fresh.

**Guard against over-scoping:** If the prior work's structure is usable, do not
default to a full rewrite. Identify specifically which sections/components need
revision and preserve everything else.

**Guard against under-scoping:** If the prior work contains only generic or
boilerplate content where the charge requires project-specific detail, that is
not "substantially meets" — it is scoped changes at minimum.

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
3. **Transition to Construct phase:** Read `~/.claude/skills/pcv/construction-protocol.md`
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

## Step 3: Build in ConstructionPlan Order

The ConstructionPlan specifies a dependency order. Follow it.

1. Build each component in the specified sequence.
2. Reference planning artifacts in `plans/artifacts/` during construction:
   - Wireframes and mockups inform visual implementations.
   - Architecture diagrams inform module structure.
   - Data models inform schema and type definitions.
   - Math formulations inform solver implementations.
   - Pseudocode informs complex logic.
   - Test specifications inform test implementations.
3. After each major component, verify it works in isolation before proceeding to
   dependent components.

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
3. **Transition to Verify phase:** Read `~/.claude/skills/pcv/verification-protocol.md`
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

Apply verification appropriate to each deliverable pattern identified in the MakePlan.

### Pattern 1 — Code

- Run automated tests (e.g., `julia test/runtests.jl`, `pytest`, `npm test`).
- Verify compilation or interpretation succeeds without errors.
- Execute the application and check runtime behavior against expected outputs.
- Check for error handling of edge cases specified in the charge or planning artifacts.

### Pattern 2 — Prose/Documents

- Verify all sections specified in the charge and ConstructionPlan are present.
- Check structural coherence and logical flow.
- Verify formatting requirements are met.
- Confirm readability for the target audience specified in the charge.

### Pattern 3 — Mathematical/Analytical

- Verify solution correctness with known test inputs where possible.
- Check all constraints are satisfied.
- Verify dimensional consistency and variable domain completeness.
- Test reproducibility — can the formulation be implemented from the document alone?

### Pattern 4 — Design-and-Render

- Compare rendered output against approved wireframe specifications in `plans/artifacts/`.
- Verify the "glance test" — can the target user quickly extract the key information?
- Check accessibility requirements (color-blind support, font sizes, contrast).
- Verify responsiveness or display-target requirements from the charge.

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

### Open Issues
[Any unresolved items, or "None"]
```

---

## Step 6: Final Git Commit

If Git is available:

- Stage all deliverable and planning files.
- Commit: `"PCV verify: [Project Name] verification complete"`

---

## Step 7: Decision Log Closeout

**Append this entry to the decision log now, before ending the session.** Do not
defer this write or batch it with other operations.

```markdown
## Project Closeout — [Date]

**Status:** [Complete / Complete with open issues]

**Summary:** [Brief description of what was built and verified]

**Verification outcome:** [All criteria passed / N of M criteria passed]

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
