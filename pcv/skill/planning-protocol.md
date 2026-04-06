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

### 1.4 Path 1 Detection — Multi-Phase Language (v3.9)

After resolving paths and before charge validation completes, scan the charge narrative
and any provided `idea.md` for explicit multi-phase language: "multi-phase," "phases,"
"stages," "sequential milestones," "break this into stages," "this will span multiple
sessions," or similar declarations.

If detected:
- Flag this project as a candidate for multi-phase structure.
- Note the user's specific language and intent (exact phrases for decision log).
- Proceed to charge validation normally, but flag the detection for Step 5 (tentative
  phase plan creation).

### 1.4a Path 1 Detection — Lite Language (v3.10)

After multi-phase language detection, scan the charge narrative and any provided
`idea.md` for explicit simplicity language: "simple," "straightforward," "quick,"
"small project," "lightweight," "not complex," "just need," "basic," or similar
declarations of simplicity.

If detected:
- Flag this project as a candidate for PCV Lite mode.
- Note the user's specific language and intent (exact phrases for decision log).
- Proceed to charge validation normally, but flag the detection for Step 4.4a
  (Lite assessment).

---

## Step 1.5: Agent Configuration Proposal

After charge validation, propose an agent configuration based on the charge and the
user's plan tier.

### 1.5.1 Read Plan Tier and Cross-Phase Context (v3.9)

Read `~/.claude/pcv-config.json` for the `plan_tier` value. If the file does not
exist (SKILL.md Step C should have prompted for it), use `pro` as a conservative
default and note this to the user.

**NEW in v3.9 — Master Log Read for Cross-Phase Learning:**

If `../plans/logs/master-log.md` exists (indicating a multi-phase project where you
are planning a phase after the first), read it for cross-phase learning. Use prior
phase configurations as **advisory context** when applying the proposal logic in
Step 1.5.3. For example:

- If phase N required a mid-project upgrade from Sonnet to Opus builders due to
  complexity, start the proposal for phase N+1 with Opus builders if the new phase
  is similarly complex (qualitative assessment based on charge comparison).
- If phase N completed smoothly with Haiku builders, you are more likely to propose
  Haiku for phase N+1 if complexity is comparable.

This learning is advisory — evaluate the current phase's charge independently, and
the user always has final say. The goal is to prevent patterns of repeatedly starting
with inadequate configurations and revising mid-phase.

### 1.5.2 Assess Charge Complexity

Read the charge and evaluate four factors:

1. **Deliverable patterns** — Code (Pattern 1) and Mathematical (Pattern 3) are more
   complex than Prose (Pattern 2). Design-and-Render (Pattern 4) is intermediate.
2. **Prior work scope** — Count files in Prior Work paths. Projects with 10+ files
   benefit from inline research when 1M context is available.
3. **Estimated component count** — Assess from the charge description. 5+ components
   suggests complex construction.
4. **Technology complexity** — Mathematical optimization, multi-language projects,
   complex parsing, or unfamiliar frameworks suggest higher complexity.

### 1.5.3 Apply Proposal Logic

**Research agent:**

```
IF prior work exists AND file count > 10:
  IF plan has 1M context (Max/API, or Pro with /extra-usage opt-in):
    → Propose: Opus, high effort, inline (hub reads directly)
    IF Pro plan: add budget note
  ELSE:
    → Propose: Sonnet, medium effort, subagent
ELSE IF prior work exists (≤ 10 files):
  → Propose: Sonnet, medium effort, subagent
ELSE (no prior work):
  → Not dispatched
```

**Builder agent:**

```
IF complex project (Pattern 3 Math, OR Pattern 1 Code with 5+ components,
   OR Pattern 4 with strict wireframe compliance):
  IF Max or API plan:
    → Propose: Opus, medium effort, subagent
  ELSE (Pro):
    → Propose: Sonnet, high effort, subagent
    Add note: "Opus builders available if Sonnet/high proves insufficient."
ELSE IF moderate project (Pattern 1 Code 2-4 components, Pattern 4):
  → Propose: Sonnet, medium effort, subagent
ELSE IF Pattern 2 Prose — analytical or synthetic (estimated 10+ pages,
   synthesizing findings across multiple source files, or producing
   original analysis rather than following a detailed structural template):
  → Propose: Sonnet, medium effort, subagent
ELSE (simple — single component, Pattern 2 Prose with bounded insertions
   or template-driven generation, Pattern 2 under 10 pages):
  → Propose: Haiku, medium effort, subagent
```

**Verifier agent:**

```
ALWAYS → Sonnet, medium effort, subagent
```

**Critic agent:**

```
ALWAYS → Haiku, medium effort, subagent
```

**Hub session effort:**

```
Planning: high for complex projects, medium otherwise
Construction/Verification: medium
```

**Context window:**

```
IF Max or API: Recommend 1M. "Phase transition compaction recommended but not required."
ELSE IF Pro with /extra-usage: Recommend 1M with budget note.
ELSE (Pro default): Recommend 200K. "Phase transition compaction strongly recommended."
```

### 1.5.4 Present Configuration Table

Present the full configuration as a table:

> **Proposed agent configuration:**
>
> | Agent | Model | Effort | Dispatch | Rationale |
> |-------|-------|--------|----------|-----------|
> | Hub (planning) | — | [level] | — | [rationale] |
> | Hub (construction) | — | Medium | — | Executing approved plan |
> | Hub (verification) | — | Medium | — | Mechanical checks |
> | Research | [model] | [level] | [Inline/Subagent] | [rationale] |
> | Critic | Haiku | Medium | Subagent | Adversarial pattern matching (always Haiku) |
> | Builder | [model] | [level] | Subagent | [rationale] |
> | Verifier | Sonnet | Medium | Subagent | Mechanical verification |
>
> **Context:** [size] ([plan] plan). [compaction note]
>
> *Approve this configuration, or tell me what you'd like changed.*

Include any plan-tier-specific notes (e.g., Pro budget warnings for Opus proposals).

**Hub effort rows are informational recommendations** — the user sets their session
effort manually. Subagent effort is also informational — subagents inherit session
effort; the Agent tool does not support an `effort` parameter.

**STOP. Wait for user approval or overrides.**

### 1.5.5 Record Configuration

On approval, append the Agent Configuration entry to the decision log as the first
milestone entry (before any clarification questions):

```markdown
## Agent Configuration — [Date]

**Plan tier:** [tier]
**Context window:** [size]

| Agent | Model | Effort | Dispatch | Rationale |
|-------|-------|--------|----------|-----------|
| Hub (planning) | — | [level] | — | [rationale] |
| Hub (construction) | — | Medium | — | Executing approved plan |
| Hub (verification) | — | Medium | — | Mechanical checks |
| Research | [model] | [level] | [mode] | [rationale] |
| Critic | Haiku | Medium | Subagent | Adversarial review |
| Builder | [model] | [level] | Subagent | [rationale] |
| Verifier | Sonnet | Medium | Subagent | Mechanical checks |

**User overrides:** [None / description of changes from proposal]

---
```

### 1.5.6 Backward Compatibility

If a project has no Agent Configuration entry in its decision log when reaching
any dispatch point (Step 2.2, Step 6, or in construction/verification protocols),
fall back to v3.7 defaults:
- Critic: Haiku, medium effort, subagent
- Research: Sonnet, medium effort, subagent
- Builder: Sonnet, medium effort, subagent
- Verifier: Sonnet, medium effort, subagent

---

## Step 2: Prior Work Analysis (if applicable)

Skip this step if the Prior Work field is blank.

### 2.1 Read Charge First

Before examining any prior work, re-read the charge narrative carefully. Note every
decision the user has already made — technology choices, constraints, specific
requirements, stated preferences. These are settled; do not re-litigate them.

### 2.2 Dispatch or Execute Research

Read the Agent Configuration from the decision log (`plans/logs/decision-log.md`).
If no Agent Configuration entry exists, use v3.7 defaults (Sonnet, medium effort,
subagent).

**IF research dispatch mode is "Inline":**

Execute prior-work analysis directly in this session. This keeps firsthand file
knowledge in the hub's context rather than receiving a summary.

1. Read `~/.claude/agents/pcv-research.md` for the behavioral checklist.
2. Follow all analysis steps inline: inventory, pattern-specific evaluation,
   three-category classification, scope signal.
3. Record results in the same structured format the subagent would return.

Inline research is only proposed when the hub has 1M context available and prior
work is substantial (10+ files). On smaller context windows, the overhead of
accumulating file reads in the hub context outweighs the benefit of firsthand
knowledge.

**ELSE (research dispatch mode is "Subagent"):**

Delegate to the `pcv-research` agent for context isolation.

1. Read `~/.claude/agents/pcv-research.md` for the agent's behavioral instructions.
2. Spawn the agent via the Agent tool:
   - `subagent_type: general-purpose`
   - `model:` use the model from the Agent Configuration (default: `sonnet`)
   - Inline the full contents of `pcv-research.md` in the prompt.
   - Include effort recommendation in the prompt: "Recommended effort level for
     this task: [effort from config]. This is informational — your session effort
     is inherited from the hub."
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

## Step 4: Sequential Clarification and Multi-Phase Assessment

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

### 4.4 Path 2 Detection — Multi-Phase Assessment (v3.9)

**MANDATORY.** After clarification concludes, assess the project scope against the
multi-phase decision criteria. Log the assessment result in the decision log even if
multi-phase is not proposed. **Do this assessment whether or not Path 1 language was
detected earlier.** Use these criteria:

- **Sequential dependencies:** Does the charge describe stages where later work depends
  on validating or completing earlier work? Example: "extract data, then verify it,
  then use it to populate templates."
- **Distinct deliverable milestones:** Are there 2+ clearly separable deliverables,
  each with its own success criteria, where completing one informs the approach to
  the next?
- **Estimated component count:** Will this project likely have 8+ components? Larger
  counts often benefit from phased construction.
- **Risk-gated work:** Does the charge describe work where the viability of later
  steps depends on the outcome of earlier steps?
- **Cross-session scale:** Is this project large enough that it will likely span
  multiple Claude Code sessions?

If **three or more criteria** are clearly present:

Present the multi-phase proposal using this format:

> "This project appears to benefit from a multi-phase approach. The charge describes
> [specific reason: sequential stages / distinct milestones / component count / etc.].
> Here's a proposed phase structure:"
>
> | Phase | Focus | Depends On | Key Deliverable |
> |-------|-------|------------|-----------------|
> | 1 | [Scope] | — | [Specific output] |
> | 2 | [Scope] | Phase 1 | [Specific output] |
> | 3 | [Scope] | Phase(s) [N] | [Specific output] |
>
> *Phases 2+ are tentative and will be refined as each phase completes. Only Phase 1
> is fully planned now. Would you like to proceed with this multi-phase structure, or
> build as a single project?*

The user can:
- **Accept** — Log the decision. PCV scaffolds the multi-phase project structure and
  proceeds to Step 5 to create the tentative phase plan as part of the MakePlan.
- **Modify** — Adjust phase boundaries, merge/split phases, reorder. Log the updated
  structure. Proceed to Step 5.
- **Decline** — Log the decision. PCV proceeds with single-phase planning. Any multi-phase
  recommendation is noted in the decision log as "Proposed but declined by user."

### 4.4a Path 2 Detection — Lite Assessment (v3.10)

**MANDATORY.** After multi-phase assessment (Step 4.4), you MUST assess whether the
project qualifies for PCV Lite. Log the assessment result in the decision log even
if Lite is not proposed — record which criteria were met and which were not. **Do
this assessment whether or not Path 1 Lite language was detected earlier.**

Criteria for proposing Lite:
- Single deliverable pattern (typically Pattern 1 or Pattern 2)
- 1-3 components estimated
- No prior work as a build baseline, or minimal baseline (≤5 files). Note: prior
  work listed as a *review subject* or *reference material* (read-only) still counts
  against this criterion if the analysis task requires synthesizing across many files.
- Straightforward success criteria (2-3 items, no complex interdependencies)
- No multi-phase indicators
- Low cognitive complexity — the task involves bounded edits, template filling, or
  straightforward generation, NOT analytical synthesis across many source files

If **three or more criteria** are clearly met (and no criteria strongly contraindicate):

Present the Lite proposal:

> "This project appears straightforward enough for PCV Lite — a compressed
> workflow with a single combined plan, inline construction, and streamlined
> verification. The critic still reviews your plan independently. Would you
> like to use Lite mode, or proceed with full PCV?"

The user can:
- **Accept** — Log the decision. Route to Step 5a (Lite plan drafting).
- **Decline** — Log the decision as "Lite proposed but declined by user."
  Proceed with full PCV planning.

**Interaction with multi-phase:** If Step 4.4 proposed multi-phase AND Step 4.4a
criteria also suggest Lite, multi-phase takes precedence (a project needing phases
is not simple). Do not propose Lite if multi-phase was accepted or is pending.

### 4.5 Path 3 Detection — Mid-Clarification Emergence (v3.9)

**During clarification** (not just at the end), if unexpected complexity or sequential
dependencies emerge that suggest multi-phase structure:

Opportunistically propose restructuring:

> "Based on your clarification, this project has sequential dependencies that would
> benefit from a phased approach. The [specific work] needs to be validated before
> [later work] can begin. Would you like to restructure into phases?"

If accepted mid-clarification:
1. Pause clarification.
2. Apply the safe restructure protocol (see SKILL.md §8.3 for the full steps):
   dry-run inventory, user confirmation, copy current work into Phase 1 subfolder,
   verify, delete originals, create project root with master-log.md and project-level
   MakePlan.
3. Resume clarification for Phase 1 only.
4. Proceed to Step 5 with the full tentative phase plan.

If declined:
- Continue single-phase clarification as planned.
- Log the multi-phase recommendation in the decision log as "Proposed but declined
  during clarification."

### 4.5a Path 3 Detection — Mid-Clarification Simplification (v3.10)

**During clarification**, if answers reveal the project is simpler than initially
assessed (fewer components, simpler requirements, narrower scope than the charge
suggested):

Opportunistically propose Lite mode:

> "Based on your clarification, this project may be simpler than initially scoped.
> Would you like to switch to PCV Lite for a faster workflow?"

If accepted mid-clarification:
1. Log the decision in the decision log.
2. Convert any existing MakePlan draft notes to lite-plan format.
3. Route to Step 5a (Lite plan drafting).

If declined:
- Continue full PCV planning.
- Log the Lite recommendation as "Proposed but declined during clarification."

---

## Step 5: Draft MakePlan (and Tentative Phase Plan if applicable)

Write `plans/make-plan.md` with these required sections:

### Required Sections

1. **Structured Charge Summary** — Reference the charge, don't reproduce it.
   Highlight key requirements and constraints in your own synthesis.
   If the charge's Deployment: field is populated, surface it in this summary.

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

### 5.1 Tentative Phase Plan Section — Optional (v3.9)

**Only include this section if multi-phase was accepted or detected in Step 4.**

If the project is multi-phase (either Path 1, Path 2, or Path 3 acceptance), add
this section within MakePlan **after** Scope Determination and **before** Revision History:

```markdown
## Tentative Phase Plan

### Phase 1: [Name] (current — fully planned)
**Focus:** [What this phase produces]
**Success criteria:** [Specific, testable]
**Deliverables:** [Concrete outputs]

### Phase 2: [Name] (tentative)
**Focus:** [Expected focus, subject to revision]
**Depends on:** [Which Phase 1 outputs]
**Open questions:** [What Phase 1 results will clarify]

### Phase 3: [Name] (tentative)
**Focus:** [Expected focus]
**Depends on:** [Which prior phase outputs]
**Open questions:** [What earlier phase results will clarify]

[Additional phases as needed]

**Note:** Phases 2+ are tentative. Phase boundaries, scope, and even the number of
remaining phases will be refined at each phase transition based on actual results.
The user may add, remove, merge, or reorder phases at any transition point.
```

**Key characteristics:**
- **Phase 1 is fully specified** — it will get a complete charge, MakePlan, and
  ConstructionPlan through the normal PCV planning process.
- **Later phases are sketched** — enough detail to show the overall arc and dependencies,
  but explicitly marked as tentative. No ConstructionPlan, no detailed component design.
- **The tentative plan is a living document** — it is updated at each phase transition
  based on what was learned. Phases can be added, removed, merged, split, or reordered.
- **The tentative plan does not commit tokens** — it's lightweight planning, not a source
  of analysis paralysis. Spend minimal effort on tentative phases, maximum effort on Phase 1.

### 5a. Draft Lite Plan (v3.10)

When Lite mode is active (accepted via Path 1, 2, or 3), write `plans/lite-plan.md`
instead of separate make-plan.md and construction-plan.md.

#### Lite Plan Template

Write `plans/lite-plan.md` with these sections:

```markdown
# Lite Plan — [Project Name]

## Charge Summary
[Brief synthesis of charge — 3-5 sentences. Surface Deployment field if populated.]

## Deliverable Pattern
[Single pattern identified, verification approach]

## Approach
[What will be built, key decisions, file structure.
 Dependency order if multiple components.]

## Verification Mode
[Inline / Subagent — with rationale if Pattern 1 or 3.
 Inline is the default for Pattern 2 and Pattern 4.
 Subagent is recommended for Pattern 1 (Code) and Pattern 3 (Math)
 where execution output or independent review has value.]

## Success Criteria Mapping
[Each criterion from the charge → how it will be verified]

## Revision History
| Rev | Date | Change | Reason |
|-----|------|--------|--------|
| 1.0 | [date] | Initial draft | — |
```

The lite-plan should be approximately half a page to one page. Do not include
separate sections for dilemmas, assumptions, or baseline preservation unless
genuinely needed.

After drafting, proceed to Step 6 (Adversarial Review / Critic) — the critic
still reviews lite-plan.md, using the same Haiku subagent for independent context.

### MakePlan Boundaries — Do NOT:

- Propose final design decisions (enumerate options and criteria instead).
- Include implementation artifacts (code, pseudocode, function signatures).
- Modify any non-planning files.

---

## Step 6: Adversarial Review (Critic)

Spawn an adversarial Critic using the Task tool with these settings:

- **subagent_type:** `general-purpose`
- **model: haiku** (always Haiku per Agent Configuration — this is not variable)
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

Recommended effort level: medium. This is informational — your session effort is inherited from the hub.
```

- **Do NOT pass file contents in the prompt.** The Critic reads from disk in its
  own context window, saving the main agent's output tokens.
- **Scope Critic output:** Add to the prompt: "Do not reproduce file contents in
  your findings — reference by section name and line number. Keep each finding
  concise." This reduces the tokens carried back to the main context.

### Lite Mode Adjustment (v3.10)

When reviewing a Lite project, the Critic reads `plans/lite-plan.md` instead of
`plans/make-plan.md`. Adjust the prompt paths accordingly. The Critic's scope is
proportionate to the simpler plan — fewer findings are expected, but the
independent review remains valuable.

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

### Lite Mode Gate (v3.10)

For Lite projects, Gate 1 approves `plans/lite-plan.md` (the single combined
artifact). On approval:
1. Append a Gate 1 entry to the decision log.
2. Commit to Git if available: `"Approve Lite Plan for [Project Name]"`
3. **Skip Steps 9-11** (ConstructionPlan drafting and Gate 3). The lite-plan
   already contains the construction approach.
4. **Context management recommendation:** Inform the user:
   > "Lite plan approved. Consider running `/compact` before construction.
   > `/clear` is also safe — construction reads state from disk."
5. **Transition to Construct phase:** Read `~/.claude/skills/pcv/construction-protocol.md`
   and follow it (Lite path — inline construction per the lite-plan).

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
- **Multi-phase decisions (v3.9):** When Path 1, Path 2, or Path 3 is detected or proposed,
  log the specific language or criteria that triggered the detection, the user's response,
  and the resulting phase structure (if accepted).
- **Lite mode decisions (v3.10):** When Lite language (Path 1.4a) is detected or Lite
  assessment (Path 4.4a) or mid-clarification simplification (Path 4.5a) is proposed,
  log the specific language or criteria, the user's response, and the routing decision.

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
2. Re-read any existing plan documents (`plans/make-plan.md`, `plans/construction-plan.md`, `plans/lite-plan.md`).
3. Re-read `plans/logs/decision-log.md`.
4. Reconstruct context from these files.
5. Inform the human of the current state: "Resuming PCV Planning. Current status: [summary]."
6. Confirm before proceeding.
