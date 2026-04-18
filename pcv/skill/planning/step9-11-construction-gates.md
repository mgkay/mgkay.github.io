# Planning Steps 9-11: ConstructionPlan + Gates

## Step 9: Draft ConstructionPlan

### Verification-Only Scope
Write minimal `pcvplans/construction-plan.md`:
```
# Construction Plan
Scope: verification-only per approved MakePlan. No construction required.
```
Log in decision log. Skip to Verify phase → read verification-protocol.md.

### Full or Scoped Construction

Write `pcvplans/construction-plan.md`:

1. **File Structure** — files/dirs to create or modify.
   Deliverable files go in the project root (or the Project Directory from charge.md).
   The `pcvplans/` directory is reserved for PCV planning artifacts (make-plan.md,
   construction-plan.md, decision log, build record). Never place project deliverables
   inside `pcvplans/`.
2. **Component Design** — what each does, interfaces, responsibilities. Correct
   poor separation of concerns with explicit boundaries.
3. **Dependency Order** — build sequence.
4. **Baseline Preservation** (if prior work carried forward) — unchanged / modified / new.
5. **Verification Strategy** — per pattern.
6. **Wireframe/Mockup Specs** (Pattern 4) — layout descriptions or artifact references.
7. **Revision History**

**Permitted:** function signatures, type defs, interface contracts, brief pseudocode.
**Not permitted:** full implementations, executable code blocks.

## Step 10: Gate 2 — Planning Artifact Approval (conditional)

Required artifacts by pattern:

- **Pattern 4:** Wireframe/mockup in `pcvplans/artifacts/`. Present. **GATE.**
- **Pattern 3:** Formal math spec in `pcvplans/artifacts/` (index sets, variables w/ domains,
  objective, constraints in LaTeX). Present. **GATE.**
- **Pattern 1:** Test spec if tests are in Success Criteria. Present. **GATE.**
- **Pattern 2:** No required artifact (ConstructionPlan component design suffices).

Write Gate 2 entry to decision log (artifact, response, path). Include `[MILESTONE:GATE_2]` at the end of the entry header.

Revision requests → save with incremented suffix (e.g., `_v2.md`), log both versions.

All planning artifacts go to `pcvplans/artifacts/` — these are specs, not deliverables.

## Step 11: Gate 3 — ConstructionPlan Approval

Present ConstructionPlan. **GATE.** Handle feedback per pcv-common.md Gate Protocol.

On approval:
1. Gate 3 entry to decision log immediately. Include `[MILESTONE:GATE_3]` at the end of the entry header.
2. Git commit: `"Approve ConstructionPlan for [Project Name]"`
3. Transition → read construction-protocol.md.
