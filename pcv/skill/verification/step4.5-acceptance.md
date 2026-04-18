# Verification Step 4.5: Acceptance Testing

Optional hands-on evaluation after automated verification.

## Prompt

Before presenting, append marker to decision log:

```markdown
## Acceptance Testing Pending — [Date]
---
```

This tells stop-closeout.sh to exit 0 (not trigger closeout reminder).

Then present:

> "Automated verification complete. Hands-on evaluation before closing out?"

Suggest pattern-appropriate approach:
- **Pattern 1:** Demo notebook or test script, exercise end-to-end.
- **Pattern 2:** Read through deliverable documents, flag issues.
- **Pattern 3:** Work through formulation with known inputs.
- **Pattern 4:** Interact with rendered output — layout, readability, usability.

**GATE.**

## If Declined

Proceed to Step 5. Note in build record: "Acceptance testing: declined by user."
Remove the `## Acceptance Testing Pending` marker from decision log.

## If Accepted

Wait for user evaluation and findings.

Before executing fixes, apply pcv-common.md Scope-Creep Check to the aggregate
scope of all reported issues. If any threshold is met, present the scope
assessment before proceeding.

For each issue:
1. Fix it.
2. Log in decision log:
```markdown
## Acceptance Testing Fix — [Date]
**Issue reported:** [description]
**Fix:** [change]
**Files affected:** [list]
---
```
3. Append to build record under "Acceptance Testing Fixes."

When user confirms complete, replace `## Acceptance Testing Pending` marker
with fix entries (or remove if no fixes). Proceed to Step 5.
