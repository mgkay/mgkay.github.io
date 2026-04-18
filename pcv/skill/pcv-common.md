# PCV Common Patterns

Shared references for all protocol files. Read once per session.

---

## Decision Log Formats

All entries: `## [Type] — [YYYY-MM-DD]` header, content, `---` separator.
Append-only. Write at moment of occurrence, never retroactively. Never batch.
Handlers under `~/.claude/skills/pcv/handlers/` invoke `log_decision` at the
moment of announce — not deferred to a post-handler phase.
File: `pcvplans/logs/decision-log.md`. Create silently on first write (Write tool
creates parent dirs). First line must be `# Decision Log — [Project Name]` (H1
title). Tags: `#LEARN` for reusable insights.

**Test mode annotation:** If `session-state.json` contains `test_mode: true`
(SessionStart hook mirrors `PCV_AUTO_APPROVE` into this file at
`pcvplans/logs/session-state.json`), prefix all decision log entry headers with
`[TEST]`:

`## [TEST] Clarification Q1 — 2026-04-14`
`## [TEST] Gate 1: MakePlan Approved — 2026-04-14 [MILESTONE:GATE_1]`

The `[TEST]` prefix appears after `##`, before the entry type. Enables:
- `grep "^\#\# \[TEST\]" decision-log.md` to list all test-mode entries
- `grep -v "\[TEST\]"` to filter them out

### Compact Format (mechanical entries)

For mechanical entries that don't carry human-meaningful content, use compact form:

```
## [Type] — [Date]
[key]: [value] | [key]: [value] | ...
---
```

Pipes in values escaped with backslash. Use compact format for: Gate Approval,
Multi-Phase Assessment, Lite Assessment, Construction Complete.
Full format retained for: Clarification, Deviation, Project Closeout, Phase Complete.

### Clarification

```
## Clarification Q[N] — [Date]
**Question (verbatim):** [exact text presented]
**Human response (verbatim):** [exact text of answer]
**Interpretation:** [how this answer shapes the plan]
---
```

### Gate Approval

**Compact (preferred):**
```
## Gate [N]: [Document] Approved — [Date]
Document: [path] | Status: Approved | Conditions: [None / list]
---
```

**Full (when conditions need detail):**
```
## Gate [N]: [Document] Approved — [Date]
**Document:** [path]
**Status:** Approved by user.
**Conditions:** [None / list]
---
```

### Deviation

```
## Deviation — [Date]
**Planned:** [spec]
**Issue:** [what went wrong]
**Resolution:** [what was done, with human approval]
#LEARN [if applicable]
---
```

### Construction Complete

**Compact (preferred):**
```
## Construction Complete — [Date]
Components: [count] | Deviations: [count or "None"]
---
```

**Full (when details needed):**
```
## Construction Complete — [Date]
[Component summary, deviation count]
---
```

### Project Closeout

```
## Project Closeout — [Date]
**Status:** [Complete / Complete with open issues]
**Summary:** [brief]
**Verification outcome:** [criteria results]
**Acceptance testing:** [Performed — N fixes / Declined / N/A]
**Open questions:** [items or "None"]
**Deliverables produced:** [list each file with absolute path]
#LEARN [if applicable]
---
```

### Phase Complete (multi-phase)

```
## Phase Complete — [Date]
**Phase:** [Name]
**Agent Configuration Used:** [table: Agent|Model|Effort]
**Mid-Project Revisions:** [list or "None."]
**Deviations:** [list or "None."]
**Lessons Learned:** [insights or "None."]
---
```

### Milestone Tags

Append to decision log entry headers at protocol milestones for automated validation:

| Tag | When Written | Protocol Location |
|-----|-------------|-------------------|
| [MILESTONE:AGENT_CONFIG] | Agent configuration approved | step1-charge-config.md Step 1.4 |
| [MILESTONE:GATE_1] | MakePlan/Lite plan approved | step6-8-critic-gates.md Step 8 |
| [MILESTONE:GATE_2] | Artifact gate approved | step9-11-construction-gates.md Step 10 |
| [MILESTONE:GATE_3] | ConstructionPlan approved | step9-11-construction-gates.md Step 11 |
| [MILESTONE:BUILDER_DISPATCH_N] | Builder N dispatched | construction/steps.md Step 3.2 |
| [MILESTONE:BUILDER_COMPLETE_N] | Builder N completed | construction/steps.md Step 3.2 |
| [MILESTONE:CONSTRUCTION_COMPLETE] | All building done | construction/steps.md Step 6 |
| [MILESTONE:VERIFICATION_COMPLETE] | Verification report written | step5-8-report-closeout.md Step 5 |
| [MILESTONE:CLOSEOUT] | Project closeout | step5-8-report-closeout.md Step 8 |
| [MILESTONE:PHASE_COMPLETE] | Phase transition | transition/step1-3-close-review.md Step 1 |

Example: `## Gate 1: MakePlan Approved — 2026-04-14 [MILESTONE:GATE_1]`

---

## Agent Dispatch Pattern

All PCV subagents use this pattern:

1. Read `~/.claude/agents/pcv-[role].md`
2. Read Agent Configuration from decision log. No entry → v3.7 defaults
   (Sonnet/medium for all, Haiku for Critic).
3. Dispatch via Agent tool:
   - `subagent_type: general-purpose`
   - `model:` per config
   - Inline full agent .md in prompt
   - Add: "Recommended effort level: [effort]. Informational — inherited from hub."
   - Pass absolute paths: project dir, charge, planning artifacts
4. Agent reads files from disk — do NOT pass file contents in prompt.

---

## Gate Protocol

**Scope.** The rules in this section apply to **judgment gates only** (J1–J16
per `pcvplans/gate-inventory.md`). Mechanical gates (M1–M8) do not wait for
approval: they announce and execute per their handler under
`~/.claude/skills/pcv/handlers/`, then emit the Mechanical-Gate Footer (see
§Mechanical-Gate Footer below). If a rule below cites "every GATE," read it as
"every judgment GATE."

At every judgment **GATE**: stop, present to user, wait for explicit approval.
- Editorial changes → apply immediately
- Substantive changes → summarize interpretation, confirm, modify, update Revision History
- Ambiguous → ask focused clarifying question
- Judgment gates: never proceed without explicit approval. Mechanical gates
  (see `pcvplans/gate-inventory.md` M1–M8) announce and execute per their
  handler per §Mechanical-Gate Footer below — no approval wait.
- End every *judgment* GATE presentation with a direct approval question (e.g.,
  "Do you approve?" or "Do you approve one of these options?"). Do not present
  information and stop silently — the user must be able to distinguish a gate
  from a pause. Mechanical gates use the handler footer emitted by
  `handlers/lib.sh::print_mechanical_footer` — see §Mechanical-Gate Footer below.
- [Judgment gates only.] After the approval question, on a new line, append:
  *You can also: ask for more information, request a recommendation, or explore trade-offs before deciding.*

**Test mode override:** If `test_mode: true` in `pcvplans/logs/session-state.json`
(written by SessionStart hook from `PCV_AUTO_APPROVE`), skip user interaction
and auto-approve with default choices:
- Gate approvals (1, 2, 3): approve unconditionally.
- Agent Configuration: accept proposed config.
- Plan tier: handled by `handlers/plan-tier.sh` (M2) which reads `pcv-config.json`
  and defaults to "pro" when absent and `test_mode: true`.
- Clarification questions: handled by `handlers/test-response-clarification.sh` (M6)
  which reads next-key from `session-state.json:test_responses_path` and falls back
  to first suggested option.
- Critic escalations: handled by `handlers/test-response-escalation.sh` (M7) which
  reads `EN`-key from `session-state.json:test_responses_path` and falls back to
  proposed resolution.
- Multi-phase/Lite assessment: accept proposal if criteria met, decline otherwise.
- Deviation approval: approve proposed resolution.
- Mid-Project Revision: decline (continue current config).
- Acceptance testing: decline.
- Pre-closeout user notes: "None."
- Global settings check: handled by `handlers/global-settings.sh` (M4) which
  auto-merges proposed permissions when `test_mode: true`.
- Hook registration: handled by `handlers/hook-registration.sh` (M1) which
  auto-approves install when `test_mode: true` and charge does not mention hook redesign.
- Charge write (Step B2): handled by `handlers/charge-write.sh` (M5) which
  auto-writes when `test_mode: true` and `charge.md` absent.

Log each auto-approval in the decision log with "Auto-approved (test mode)"
appended. For mechanical gates (M1–M8), `handlers/lib.sh::log_decision` emits
the entry automatically; for judgment gates, the hub appends the annotation as
part of the approval log write.

---

## Mechanical-Gate Footer

Every mechanical-gate handler (M1–M8 per `pcvplans/gate-inventory.md`) prints
the following canonical footer to stdout immediately after announcing its
action. The text is emitted by `handlers/lib.sh::print_mechanical_footer` —
handler scripts do not duplicate the string inline.

**Canonical text (verbatim):**

```
This action was taken automatically based on project context. To override, edit pcvplans/logs/session-state.json or adjust PCV settings.
```

Mechanical gates use this footer *in place of* the judgment-gate approval
question ("Do you approve?") described in §Gate Protocol above — the action is
already complete by the time the footer prints. Users who need to alter the
outcome edit the sentinel (`session-state.json`) or adjust the relevant PCV
settings file (`~/.claude/pcv-config.json`, `~/.claude/settings.json`, or
`.claude/settings.json`) and re-invoke.

---

## Scope-Creep Check

Before executing user-directed work not in the approved plan (acceptance testing
fixes, scope extensions, ad-hoc requests during any phase), the hub performs a
two-stage check: a **mechanical trigger** (M8) that evaluates thresholds against
proposed-scope metadata, and — if triggered — a **judgment response** gate (J16)
that asks the user to choose a/b/c.

### Trigger (mechanical — M8)

Invoke `bash ~/.claude/skills/pcv/handlers/scope-creep-trigger.sh`. Handler
evaluates the aggregate scope against the thresholds below, emits
`gate-context.json` if triggered, and exits 0 if triggered (meaning: present
the Response gate below) or 1 (no-op, proceed without gate).

**Thresholds (any one met → trigger fires):**
- 3+ new files to be created
- Changes spanning 3+ existing files
- Work requiring decisions not in the approved plan (changes to control flow,
  sequencing, gate behavior, or file/directory structure)

**Invocation:** Evaluate the *aggregate* scope of all reported work, not each
item individually. A sequence of small fixes can accumulate into a scope
bypass. Handler always runs when the hub reports scope expansion — the handler
itself is not a gate.

### Response (judgment — J16)

When the M8 trigger fires (exit 0), present the following judgment gate to the
user:

> "This request spans [X] new files / [Y] existing files / requires decisions
> not in the approved plan. Options:
> **(a)** Approve as in-scope fix.
> **(b)** Defer to a new phase.
> **(c)** Reduce scope to fit current phase.
>
> Do you approve one of these options?"

Log user's choice and reasoning in decision log.

**Bias:** When in doubt, present the check. Do not ask whether to check —
present the result. Conservative false positives are preferable to missed
scope bypass.

---

## Persistence Assurance

Any recommendation, decision, deferred work item, or information the user may
need in a future session must be written to a file before the session ends.

**Rule:** Never assure the user that information will be available in a future
session unless it has been written to disk. Conversation context is ephemeral —
it is lost when the session ends.

**Affirmative behavior:** When a recommendation or deferred item emerges:
1. Write it to the appropriate file (decision log, build record, master log,
   or a dedicated future-work file).
2. Confirm to user: "I've written [item] to [file]. It will persist across sessions."

**Violation:** Saying "this will be available next session" or "I'll note this
for Phase N" without a corresponding disk write is a protocol violation.

**Scope:** Applies to cross-session information only. Deferred work within the
current session (e.g., "I'll address this in Step 5") does not require a disk
write — it's in-context.

---

## Session Resumption Pattern

1. Read pcvplans/charge.md
2. Read plan files (make-plan.md / lite-plan.md, construction-plan.md)
3. Read pcvplans/logs/decision-log.md
4. Reconstruct state from artifacts
5. Present status summary
6. Wait for user confirmation before proceeding

