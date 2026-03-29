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

0. **Read Agent Configuration.** Before dispatch, read the Agent Configuration
   entry from `plans/logs/decision-log.md`. Extract the Verifier row's model
   and effort values. If no Agent Configuration entry exists (v3.7 project),
   use defaults: model `sonnet`, effort `medium`.
1. **Determine which patterns apply** from the MakePlan's deliverable patterns section.
2. **Assemble pattern-specific instructions** by including the relevant sections below
   in the dispatch prompt.
3. **Dispatch pcv-verifier** via the Agent tool:
   - `subagent_type: general-purpose`
   - `model:` use the model from the Agent Configuration (default: `sonnet`)
   - Inline the full contents of `pcv-verifier.md` in the prompt.
   - Include the pattern-specific instructions for applicable patterns.
   - Include effort recommendation in the prompt: "Recommended effort level for this task: [effort from config]. This is informational — your session effort is inherited from the hub."
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

### 8.1 Multi-Phase Detection (v3.9)

After writing the closeout entry above, check if this is a multi-phase project by
testing for `../plans/logs/master-log.md` (relative to the current phase subfolder).

- **If found:** This phase is part of a multi-phase project. Do NOT end the session.
  Instead, load `~/.claude/skills/pcv/phase-transition-protocol.md` and follow it.
  The transition protocol handles phase closeout, master log update, and user direction
  for the next phase.

- **If not found:** This is a single-phase project (or a standalone phase). End
  normally per the existing closeout logic.

---

## Session Resumption

If resuming verification in a new conversation:

1. Read `charge.md`, `plans/make-plan.md`, and `plans/construction-plan.md`.
2. Read `plans/logs/decision-log.md`.
3. Check if a verification report already exists.
4. Inform the human of current state and confirm before proceeding or re-verifying.