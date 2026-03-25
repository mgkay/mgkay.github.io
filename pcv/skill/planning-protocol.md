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
