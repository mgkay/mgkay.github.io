# Planning Step 5: Draft MakePlan

## MakePlan Required Sections

1. **Structured Charge Summary** — synthesize, don't reproduce. Surface Deployment field.
2. **Prior Work Assessment** — three-category classification + scope signal (if applicable).
3. **Deliverable Patterns** — which apply and why.
4. **Dilemmas** — trade-offs, criteria, resolution. Max 5 sentences each.
5. **Assumptions & Unknowns** — ONLY human-approved items.
6. **Scope Determination** — verification-only / scoped changes / full build.
7. **Verification Criteria** — testable, pattern-specific.
8. **Tentative Phase Plan** — only if multi-phase accepted (see planning fragment).
9. **Revision History** — `| Rev | Date | Change | Reason |`

Do NOT: propose final design decisions, include implementation artifacts, modify non-planning files.

---

## 5.0 Full MakePlan

Write `pcvplans/make-plan.md` with sections per MakePlan Required Sections above.

## 5.1 Tentative Phase Plan (if multi-phase accepted)

Add after Scope Determination, before Revision History:

```markdown
## Tentative Phase Plan

### Phase 1: [Name] (current — fully planned)
**Focus:** [output] **Criteria:** [testable] **Deliverables:** [concrete]

### Phase 2: [Name] (tentative)
**Focus:** [expected] **Depends on:** [Phase 1 outputs] **Open:** [what Phase 1 clarifies]

### Phase 3+: [as needed]

**Note:** Phases 2+ tentative. Boundaries refined at each transition.
User may add/remove/merge/reorder at any transition.
```

Phase 1 fully specified. Later phases sketched. Spend minimal effort on tentative phases.

## 5a. Lite Plan

When Lite mode active, write `pcvplans/lite-plan.md` instead:

```markdown
# Lite Plan — [Project Name]

## Charge Summary
[3-5 sentences. Surface Deployment field if populated.]

## Deliverable Pattern
[Single pattern, verification approach]

## Approach
[What to build, key decisions, file structure, dependency order]

## Verification Mode
[Inline (default Pattern 2/4) / Subagent (recommended Pattern 1/3)]

## Success Criteria Mapping
[Each criterion → how verified]

## Revision History
| Rev | Date | Change | Reason |
```

~Half to one page. No separate dilemmas/assumptions unless genuinely needed.
After drafting → proceed to Step 6 (Critic still reviews).
