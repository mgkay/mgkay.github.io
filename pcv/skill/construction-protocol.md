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

0. **Read Agent Configuration.** Before the first dispatch, read the Agent
   Configuration entry from `plans/logs/decision-log.md`. Extract the Builder
   row's model and effort values. If no Agent Configuration entry exists (v3.7
   project), use defaults: model `sonnet`, effort `medium`.

1. **Extract the component specification** from the ConstructionPlan — what to build,
   interfaces, responsibilities, file paths, relevant planning artifacts.
2. **Dispatch pcv-builder** via the Agent tool:
   - `subagent_type: general-purpose`
   - `model:` use the model from the Agent Configuration (default: `sonnet`)
   - Inline the full contents of `pcv-builder.md` in the prompt.
   - Include effort recommendation in the prompt: "Recommended effort level for this task: [effort from config]. This is informational — your session effort is inherited from the hub."
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

### 3.4 Mid-Project Revision Detection

Track deviation count across components during the dispatch loop. A "deviation"
is any builder-reported divergence from the ConstructionPlan that required human
approval (logged per Step 4).

**After each builder returns with deviations**, increment the deviation count.
If the count reaches **2 or more** on a multi-component project (3+ total
components in the ConstructionPlan), propose a configuration revision before
dispatching the next builder:

> "The builder has reported deviations on [N] of [total] components so far.
> This suggests the construction complexity exceeds what was anticipated.
> Would you like to revise the builder configuration?"
>
> | Agent | Current | Proposed Revision | Rationale |
> |-------|---------|-------------------|-----------|
> | Builder | [current model], [current effort] | [proposed model], [proposed effort] | [rationale] |

**STOP. Wait for user approval.**

- **If approved:** Log a Configuration Revision entry in the decision log:
  ```markdown
  ## Configuration Revision — [Date]

  **Trigger:** [N] deviations on [total] components
  **Change:** Builder [old model/effort] → [new model/effort]
  **Applied to:** Remaining components only

  ---
  ```
  Update the working configuration for subsequent dispatches.
- **If declined:** Continue with the current configuration. Log the declined
  proposal in the decision log.

Mid-project revisions are only proposed when there is concrete evidence (deviation
count). They are never proposed speculatively.

### 3.5 Path 3 Detection — Phased Restructuring During Construction (v3.9)

During the component dispatch loop, if construction encounters scope that was
underestimated at planning time and reveals **sequential dependencies** that would
benefit from a multi-phase approach, propose restructuring after the current round
of deviations is resolved.

**Trigger criteria:**
- Scope creep indicates work that depends on validation of earlier components.
- The charge did not explicitly declare multi-phase intent (Path 1), and the
  planning assessment did not detect multi-phase criteria (Path 2).
- At least one component is complete and demonstrates the pattern.

**Proposal format** (match the style from planning-protocol.md):

> "Based on construction progress, this project has sequential dependencies that
> would benefit from a phased approach. [Specific reason: e.g., 'data validation
> must occur before pipeline construction' or 'architecture proof-of-concept
> should be validated before full implementation']. Would you like to restructure
> into phases?"

**If accepted:**

1. **Write a "Construction Complete — Phase 1" entry** to the decision log immediately:
   ```markdown
   ## Construction Complete — Phase 1 — [Date]

   **Completed components:** [List components built so far]
   **Reason for phase boundary:** [Explanation of sequential dependencies discovered]
   **Phase 1 status:** All planned components in Phase 1 complete. Ready to restructure.

   ---
   ```

2. **Apply the safe restructure protocol:**
   - Document the current project state (record which files exist, current structure).
   - Create a multi-phase directory structure at the project root:
     ```
     project-root/
       phase-1/              [Current work moves here]
       phase-2/              [Scaffolded for next phase]
       plans/
         make-plan.md        [Project-level MakePlan with tentative phase plan]
         logs/
           master-log.md     [Cross-phase transitions and configurations]
     ```
   - **Dry-run phase:** Show the human the planned structure before moving files.
   - **Confirmation:** Wait for human approval of the restructure.
   - **Execute:** Copy current deliverable files into `phase-1/`, moving or copying
     planning artifacts to the root `plans/` directory as appropriate. Create
     `phase-1/plans/` structure to hold Phase 1-specific planning artifacts.
   - **Verify:** Confirm all files are intact in their new locations before deleting originals.

3. **Load phase-transition-protocol.md** to continue the multi-phase workflow:
   ```
   Read ~/.claude/skills/pcv/phase-transition-protocol.md and follow it.
   This protocol manages phase boundaries, session resumption, and verification
   across phases.
   ```

**If declined:**

- Continue single-phase construction with remaining components.
- Log the recommendation in the decision log as a declined proposal:
  ```markdown
  ## Multi-Phase Proposal (Declined) — [Date]

  **Proposed restructuring:** [Describe what was proposed]
  **User decision:** Continue single-phase construction
  **Rationale:** [Note any user explanation]

  ---
  ```
- Proceed to Step 3.6 (formerly 3.5) to resume component dispatch.

---

### 3.6 Planning Artifact References

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