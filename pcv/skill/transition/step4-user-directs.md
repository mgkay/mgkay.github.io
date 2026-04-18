# Transition Step 4: User Directs Next Phase

Present updated phase plan:

> "[Phase N] complete. Updated plan:"
> [table from Step 3]
>
> Options:
> **(A)** Proceed to Phase [N+1] as planned.
> **(B)** Modify the phase plan.
> **(C)** Describe a new phase not in the plan.
> **(D)** Declare project complete (remaining deferred).
> **(E)** Collapse remaining into single final phase.
> **(F)** Convert to single-phase (reopen-for-fixes on last phase).

**GATE.**

## Option A: Proceed

Extract next phase name/focus from plan → Step 5 (scaffold).

## Option B: Modify

1. Present current phases. For each change, confirm understanding.
2. Draft updated plan. Ask: "Write to project-level MakePlan?" Wait.
3. Update `../pcvplans/make-plan.md`. Extract next phase → Step 5.

## Option C: New Phase

1. Capture focus, dependencies, criteria.
2. Insert in correct location (respect dependencies).
3. Update `../pcvplans/make-plan.md`. Proceed to Step 5.

## Option D: Declare Complete

1. Update master log: "Project complete — remaining deferred." List deferred phases.
2. Generate master project summary at `pcvplans/project-summary.md`:
   ```markdown
   # Project Summary — [Project Name]
   **Author:** [from charge] **Date:** [date] **Phases:** [N completed]
   ## Phase Overview
   | Phase | Name | Summary File |
   ## Project Arc
   [2-3 sentences: trajectory across phases]
   ```
   Links to per-phase summaries. Lightweight — don't reproduce content.
3. Git commit. Inform user. End session.

## Option E: Collapse Remaining

1. Consolidate remaining phases into single "Final" phase.
2. Update plan. Generate master summary (same as D).
3. Proceed to Step 5 with collapsed final phase.

## Option F: Convert to Single-Phase

1. Update master log: "Converted to single-phase."
2. Generate master summary (same as D).
3. Generate charge for remaining work.
4. Instruct: remaining via `/pcv reopen` on Phase [N] subfolder.
5. Git commit. End session.
