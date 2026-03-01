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
