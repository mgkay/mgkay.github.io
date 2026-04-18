## Step Sequence

| Step | Fragment | Action |
|------|----------|--------|
| 1 | `planning/step1-charge-config.md` | Read charge, resolve paths, detect multi-phase/Lite language, agent config |
| 2 | `planning/step2-prior-work.md` | Prior work analysis — skip if Prior Work blank |
| 3-4 | `planning/step3-4-patterns-clarify.md` | Identify patterns, sequential clarification, multi-phase/Lite assessment |
| 5 | `planning/step5-makeplan.md` | Draft MakePlan (or Lite plan), tentative phase plan if multi-phase |
| 6-8 | `planning/step6-8-critic-gates.md` | Critic dispatch, compliance checklist, Gate 1 |
| 9-11 | `planning/step9-11-construction-gates.md` | ConstructionPlan, artifact gates, Gate 3, transition to Construct |

## Loading

1. Read `~/.claude/skills/pcv/pcv-common.md` if not in context
2. Read fragment for current step
3. Follow fragment instructions to completion
4. Read next fragment in sequence

## Resumption

Per pcv-common.md Session Resumption Pattern. Then route:
- No make-plan.md → Step 1
- make-plan.md, no construction-plan.md → ask: resuming planning or proceeding?
- Both exist → planning complete, route to construction
- lite-plan.md exists → Lite path, route per lite-plan state

---

# Planning Step 1: Charge + Agent Configuration

## 1.1 Read Charge

Read `pcvplans/charge.md`. Parse Configuration fields:
- Project Directory specified → deliverables there, planning stays here. Blank → current dir.

## 1.2 Path Resolution

For each non-blank path (Project Directory, Export Target, Prior Work):
- Relative (no `/`, `~`, drive letter)? Resolve against charge parent dir.
- Validate resolved path exists on disk via Glob/Read.
- Missing → stop: "Path [original] resolves to [absolute] which does not exist."
- Use resolved absolute internally. Charge retains original for portability.
- Prior Work: note paths for Step 2, do NOT read/modify yet.

## 1.3 Language Detection

Scan charge + pcvplans/idea.md (if exists) for:
- **Multi-phase keywords:** "multi-phase," "phases," "stages," "sequential milestones,"
  "break into stages," "span multiple sessions" → flag for Step 4.4.
- **Lite keywords:** "simple," "straightforward," "quick," "small project,"
  "lightweight," "not complex," "just need," "basic" → flag for Step 4.4a.

Proceed to charge validation normally.

## 1.4 Agent Configuration Proposal

### Read Context
- Read `~/.claude/pcv-config.json` for plan_tier. Missing → default `pro`, note to user.
- If `../pcvplans/logs/master-log.md` exists → read for advisory cross-phase learning
  (prior configs inform proposals, not dictate them).

### Assess Complexity

| Factor | Indicator |
|--------|-----------|
| Patterns | Code/Math = complex. Prose = simpler. Design = intermediate. |
| Prior work | 10+ files → inline research candidate (needs 1M context) |
| Components | 5+ estimated = complex |
| Technology | Optimization, multi-language, unfamiliar frameworks = higher |

### Default Path

If no complexity signals present (see guard clause below):

Present v3.7 defaults:
> | Agent | Model | Effort | Dispatch | Rationale |
> |-------|-------|--------|----------|-----------|
> | Hub (planning) | — | Medium | — | Standard scope |
> | Hub (construction) | — | Medium | — | Executing approved plan |
> | Hub (verification) | — | Medium | — | Mechanical checks |
> | Critic | Haiku | Medium | Subagent | Adversarial review |
> | Builder | Sonnet | Medium | Subagent | Standard construction |
> | Verifier | Sonnet | Medium | Subagent | Mechanical checks |

"Default agent configuration — approve?" **GATE.**

### Complexity Guard Clause

If ANY of these signals present, use the full decision tree below instead of defaults:
- Pattern 3 (Math)
- Pattern 1 with 5+ estimated components
- Pattern 4 with strict wireframe requirements
- Charge keywords: "optimization," "multi-language," "unfamiliar framework"

### Complex-Case Decision Tree (reference)

**Research:**
- Prior work >10 files + 1M context → Opus/high/inline (Pro: budget note)
- Prior work >10 files, no 1M → Sonnet/medium/subagent
- Prior work ≤10 files → Sonnet/medium/subagent
- No prior work → not dispatched

**Builder:**
- Complex (Pattern 3, Pattern 1 w/ 5+ components, Pattern 4 strict wireframe):
  Max/API → Opus/medium. Pro → Sonnet/high (note: Opus available if insufficient).
- Moderate (Pattern 1 2-4 components, Pattern 4) → Sonnet/medium
- Analytical Pattern 2 (10+ pages, synthesis across sources) → Sonnet/medium
- Simple (single component, bounded Pattern 2, template-driven) → Haiku/medium

**Verifier:** Always Sonnet/medium. **Critic:** Always Haiku/medium.

**Hub effort:** Planning = high (complex) or medium. Construction/Verification = medium.

**Context:** Max/API → 1M, compaction recommended not required. Pro+extra → 1M
w/ budget note. Pro default → 200K, compaction strongly recommended.

### Present + Approve

Present config table (default or complex-case):

Include plan-tier notes. **GATE.** On approval, write Agent Configuration entry
to decision log as first milestone entry (before clarification questions).
Include `[MILESTONE:AGENT_CONFIG]` at the end of the entry header.

### Backward Compat
No Agent Config in decision log at any dispatch point → use v3.7 defaults
(see Agent Configuration v3.7 Defaults at end of this file).

After Agent Configuration approved → proceed to Step 2 (Prior Work).

---

## Agent Configuration v3.7 Defaults

| Agent | Model | Effort | Dispatch |
|-------|-------|--------|----------|
| Critic | Haiku | Medium | Subagent |
| Research | Sonnet | Medium | Subagent |
| Builder | Sonnet | Medium | Subagent |
| Verifier | Sonnet | Medium | Subagent |

Hub effort rows are informational (user sets manually). Subagent effort is
informational (inherited from session, Agent tool has no effort parameter).
