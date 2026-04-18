# Planning Steps 6-8: Critic Review + Gates

## Step 6: Adversarial Review (Critic)

Dispatch per pcv-common.md Agent Dispatch Pattern (role: critic, always Haiku).

Prompt template (fill absolute paths):

```
You are the PCV Critic — adversarial reviewer for planning documents.
Challenge the plan, not confirm it. Constructive but relentless.

Read from disk:
1. Charge: [path]
2. MakePlan: [path to make-plan.md or lite-plan.md]
3. Decision Log: [path]

Look for: weak assumptions stated as fact, internal contradictions, missing edge
cases, unstated risks, requirements not addressed, optimistic estimates, prior
work blind spots, verification gaps. If verification-only scope, extra scrutiny.

For each finding:
## Finding N: [title]
**Issue:** [what's wrong]
**Evidence:** [quote]
**Proposed Disposition:** [Resolved / Escalate / Acknowledge]
**Justification:** [why]

Constraints: read-only, no delegating, specific not vague, substantive only.
Do not reproduce file contents — reference by section/line. Keep findings concise.
```

### Process Findings

Sort into: Resolved, Acknowledged, Escalated.

**Step 1:** Present Resolved + Acknowledged as single summary (no user input needed).
Confirm user is satisfied.

**Step 2:** Present Escalated one at a time (same rule as clarification):

**Test mode escalation responses (M7 handler).** Before presenting each
escalated finding GATE, invoke:

```
bash ~/.claude/skills/pcv/handlers/test-response-escalation.sh \
  --project-dir . --escalation <N> [--phase <P>]
```

The handler reads `session-state.json:test_responses_path`, looks up key
`"EN"` (or `"E<phase>-N"` for multi-phase), logs the finding + question +
verbatim answer in the decision log, and emits gate-context.json.

- Exit 0 → handler injected response; skip the GATE below and proceed to the
  next escalated finding.
- Exit 1 → no response available; fall back to the proposed resolution
  (test-mode default) or present the GATE interactively.

1. One finding → issue, evidence, focused question.
2. **GATE.** (Skipped if handler injected response.)
3. Log finding + question + verbatim answer in decision log.
4. Next escalated finding, or conclude.

Escalated questions do NOT count against 8-question limit.
If escalated answers reveal significant new scope → revise MakePlan, re-run Critic (max once).
Nothing enters Assumptions & Unknowns without explicit human consent.

## Step 7: Pre-Gate Validation (silent)

Before presenting Gate 1, verify internally: all config resolved, clarification
before drafting, critic reviewed, assumptions human-approved, decisions logged,
patterns identified. All pass → proceed to Gate 1. Any fail → fix or flag to user.

## Step 8: Gate 1 — MakePlan Approval

Present MakePlan. **GATE.** Handle feedback per pcv-common.md Gate Protocol.

On approval:
1. Write Gate 1 entry to decision log immediately. Include `[MILESTONE:GATE_1]` at the end of the entry header.
2. Git commit if available: `"Approve MakePlan for [Project Name]"`
3. Proceed to Step 9.

**Lite Gate 1:** Approves lite-plan.md. On approval:
1. Gate 1 entry to decision log. Include `[MILESTONE:GATE_1]` at the end of the entry header.
2. Git commit: `"Approve Lite Plan for [Project Name]"`
3. Skip Steps 9-11.
4. Transition → read construction-protocol.md (Lite path).
