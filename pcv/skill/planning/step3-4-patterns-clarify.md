# Planning Steps 3-4: Patterns + Clarification

## Deliverable Patterns

| Pattern | Type | Verification |
|---------|------|-------------|
| 1 | Code | Tests, compilation, runtime, edge cases |
| 2 | Prose | Sections present, project-specific content, coherent flow |
| 3 | Math | Variables defined w/ domains, objective indexed + dimensional, constraints labeled, implementable |
| 4 | Design | Matches wireframe, glance test, accessibility, display target |

---

## Step 3: Identify Deliverable Patterns

Classify deliverables per the Deliverable Patterns table above.
For each pattern present, note verification criteria and whether it triggers
an artifact gate at Step 10.

## Step 4: Sequential Clarification

### Dependency Ordering
List all open questions (charge gaps, prior work findings, pattern requirements).
Identify dependency chains. Present root of longest chain first.

### One Question at a Time
**Test mode response injection (M6 handler).** Before presenting clarification
question N, invoke:

```
bash ~/.claude/skills/pcv/handlers/test-response-clarification.sh \
  --project-dir . --question <N> [--phase <P>]
```

The handler reads `session-state.json:test_responses_path`, looks up key
`"QN"` (or `"Q<phase>-N"` for multi-phase per the documented schema —
Single-phase: `"Q1"`, `"Q2"`, ...; Multi-phase: `"Q1-1"`, `"Q1-2"`, ...;
Escalations: `"E1"`, `"E2"`, ... or `"E<phase>-N"`), logs it as the human
response in the standard Clarification format, and emits gate-context.json.

- Exit 0 → handler injected response; skip the GATE below and proceed to
  re-evaluation.
- Exit 1 → no response available; fall back to the first suggested option
  (test-mode default) or present the GATE interactively.

1. Present one question with brief context (1-2 sentences: why it matters).
2. **GATE.** (Skipped if handler injected response.)
3. Re-evaluate remaining questions. Answer may resolve some or surface new ones.
4. Next highest-impact question, or conclude if all resolved.

**Max 8 questions.** More needed → charge is underspecified, flag to user.

**Never:** multiple questions per round, questions that don't affect the plan,
re-ask answered questions, leading questions.

## 4.4 Multi-Phase Assessment (MANDATORY — assessment always runs; response auto-decided in test mode per pcv-common.md Gate Protocol)

After clarification concludes, assess regardless of Path 1 detection.
Log result even if not proposed.

**Criteria (need 3+ clearly present):**
- Sequential dependencies (later work depends on validating earlier)
- Distinct deliverable milestones (2+ separable, each with own criteria)
- 8+ estimated components
- Risk-gated work (viability depends on earlier outcomes)
- Cross-session scale

If 3+ met, present proposal with phase table:

> | Phase | Focus | Depends On | Key Deliverable |
> |-------|-------|------------|-----------------|
> | 1 | [Scope] | — | [Output] |
> | 2 | [Scope] | Phase 1 | [Output] |

> *Phases 2+ tentative. Would you like multi-phase or single project?*

**Decline →** log as "Proposed but declined." Proceed to Step 5 in current directory.

**Modify →** adjust boundaries per user feedback, log, then follow Accept steps below.

**Accept →** log acceptance, then execute the multi-phase scaffold sequence:

### 4.4b Multi-Phase Scaffold (execute immediately on acceptance)

1. **Create master log.** Write `pcvplans/logs/master-log.md`:
   ```markdown
   # Master Decision Log — [Project Name]
   ## Multi-Phase Project Initiated — [Date]
   **Phase structure:** [N phases] **Phase 1 focus:** [brief]
   ---
   ```

2. **Scaffold phase-1 directory.** Run:
   `bash ~/.claude/skills/pcv/hooks/scaffold-phase.sh --phase-name "[name]" --project-name "[Project Name]" --parent-dir .`
   This creates: `phase-1-[name]/`, CLAUDE.md, `.claude/settings.json`, `pcvplans/.gitkeep`.

3. **Create phase-1 charge.** Write `phase-1-[name]/pcvplans/charge.md` using the
   standard charge template (SKILL.md §4). Derive from root charge:
   - Project Name: same as root
   - Name: same as root (or "Phase 1 — [Phase Name]")
   - Project Description: Phase 1 scope only (not Phase 2+)
   - Success Criteria: only Phase 1 criteria from root charge
   - Prior Work: as applicable

4. **Initialize phase-1 decision log.** Write `phase-1-[name]/pcvplans/logs/decision-log.md`.
   Copy the Agent Configuration entry and any Clarification entries from the root
   decision log that are relevant to Phase 1. At minimum, include:
   ```markdown
   # Decision Log — [Project Name]
   ## Agent Configuration — [Date] [MILESTONE:AGENT_CONFIG]
   [copy from root log]
   ---
   ```
   This ensures the phase has its own decision log before context switches.

5. **Verify scaffold.** Confirm all exist:
   - `pcvplans/logs/master-log.md` (root)
   - `phase-1-[name]/pcvplans/charge.md`
   - `phase-1-[name]/pcvplans/logs/decision-log.md`
   - `phase-1-[name]/CLAUDE.md`
   - `phase-1-[name]/.claude/settings.json`

6. **Switch context.** All subsequent planning (Step 5 onward), construction, and
   verification for Phase 1 happen **inside `phase-1-[name]/`**. Write the Phase 1
   MakePlan to `phase-1-[name]/pcvplans/make-plan.md`. The root `pcvplans/make-plan.md`
   holds the tentative phase plan (Step 5.1) for cross-phase reference.

7. **Git commit.** Commit scaffold: `"PCV scaffold: multi-phase structure for [Project Name]"`

Proceed to Step 5 working inside `phase-1-[name]/`.

## 4.4a Lite Assessment (MANDATORY — assessment always runs; response auto-decided in test mode per pcv-common.md Gate Protocol)

After multi-phase assessment. Log result even if not proposed.

**Criteria (need 3+ clearly met, none strongly contraindicate):**
- Single deliverable pattern
- 1-3 estimated components
- No/minimal prior work baseline (≤5 files; read-only reference still counts)
- Simple success criteria (2-3 items, no complex interdependencies)
- No multi-phase indicators
- Low cognitive complexity (bounded edits, template filling, not analytical synthesis)

If 3+ met: propose Lite. Accept → route to Step 5a. Decline → log, proceed full PCV.

Multi-phase takes precedence over Lite (phased project ≠ simple).

## 4.5 Mid-Clarification Detection (J14 — mid-clarification-restructure judgment gate)

**During** clarification (not just at end):
- Unexpected complexity/dependencies emerge → propose multi-phase restructure.
  If accepted: pause clarification, apply safe restructure (SKILL.md §8.3),
  resume for Phase 1 only.
- Answers reveal simpler scope → propose Lite switch.
  If accepted: log, convert draft to lite-plan format, route to Step 5a.

Log declined proposals in decision log.

After all clarification answered + multi-phase/Lite assessments logged → proceed to Step 5 (MakePlan).
