## Step Sequence

| Step | Fragment | Action |
|------|----------|--------|
| 1-4 | `verification/steps1-4-verify-mapping-export.md` | Pattern-specific verification, charge mapping, artifact comparison, export |
| 4.5 | `verification/step4.5-acceptance.md` | Optional hands-on acceptance testing |
| 5-8 | `verification/step5-8-report-closeout.md` | Report, commit, build record, closeout, summary, deployment, multi-phase |

## Loading

1. Read `~/.claude/skills/pcv/pcv-common.md` if not in context
2. Read this file and follow steps in order
3. Read next fragment in sequence

## Resumption

Per pcv-common.md Session Resumption Pattern. Also check if verification report
already exists. Inform user of state, confirm before proceeding or re-verifying.

---

# Verification Step 1: Pattern-Specific Verification

## 1.1 Load Agent Instructions

Read `~/.claude/agents/pcv-verifier.md`.

## 1.2 Dispatch Verifier

Read Agent Configuration from decision log. No entry → v3.7 defaults (Sonnet/medium).

For each deliverable pattern in MakePlan, assemble pattern-specific instructions:

**Pattern 1 — Code:**
- Run automated tests. Verify compilation/interpretation. Execute + check runtime.
- Check edge case handling from charge/planning artifacts.
- Compare code against approved pseudocode/test specs.

**Pattern 2 — Prose:**
- All specified sections present. Structural coherence + logical flow.
- Formatting requirements met. Readability for target audience.
- Cross-reference every charge requirement — gaps and generic content.

**Pattern 3 — Math:**
- Solution correctness with known inputs. All constraints satisfied.
- Dimensional consistency + variable domains. Reproducible from document alone.
- Compare against approved math spec.

**Pattern 4 — Design:**
- Compare against approved wireframes in `pcvplans/artifacts/`.
- Glance test. Accessibility. Responsiveness/display target.

Dispatch per pcv-common.md Agent Dispatch Pattern (role: verifier).
May dispatch single verifier for multiple patterns, or once per pattern.
Process returned report — review issues by severity.

## 1.3 Lite Inline Verification

When `pcvplans/lite-plan.md` exists, check Verification Mode:

**Inline:** Hub verifies directly — no subagent. Read deliverables, check against
Success Criteria Mapping. Results go to decision log directly. Skip Steps 2-3.

**Subagent:** Dispatch verifier as normal. Verifier reads lite-plan.md instead of
separate make-plan + construction-plan.

## 1.4 Verification Fixes

If verifier reports issues needing changes:
1. Fix in main session (not via subagent).
2. Log fix as deviation in decision log.
3. Append to build record: new decisions under "Design Decisions," plan changes
   under "Deviations." Update "Verification Status."

After verification fixes (or none needed) → proceed to Step 2 (Charge-to-Deliverable Mapping).

# Verification Steps 2-4: Mapping + Comparison + Export

## Step 2: Charge-to-Deliverable Mapping

Read Success Criteria from charge.md. For each:
1. Identify deliverable component(s) that satisfy it.
2. Verify component actually meets criterion.
3. Record:

| Success Criterion | Deliverable Component | Status |
|---|---|---|
| [criterion] | [file/component] | PASS / FAIL / PARTIAL |

FAIL or PARTIAL → note what's missing, inform user.

## Step 3: Planning Artifact Comparison

Compare deliverables against approved artifacts in `pcvplans/artifacts/`:
- Code vs pseudocode specs
- Tests vs test specs
- Rendered output vs wireframes
- Data models vs design sketches
- Solver code vs math formulations

Note deviations. Minor improvements acceptable but must be documented.
Significant deviations → flag to user.

## Step 4: Export

Read Export Target from charge.md.
- Blank → skip.
- Equals Project Directory → skip.
- Otherwise: copy verified deliverables to target. Use Read/Write tools or
  cross-platform scripting, NOT `cp`/`copy`. Verify intact. Log in decision log.

After mapping + comparison + export → proceed to Step 4.5 (Acceptance Testing).
