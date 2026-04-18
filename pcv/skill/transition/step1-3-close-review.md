## Step Sequence

| Step | Fragment | Action |
|------|----------|--------|
| 1-3 | `transition/step1-3-close-review.md` | Close phase log, update master log, review tentative plan |
| 4 | `transition/step4-user-directs.md` | Present options A-F, user decides next phase |
| 5-6 | `transition/step5-6-scaffold-begin.md` | Scaffold next phase, begin planning |

## Loading

1. Read `~/.claude/skills/pcv/pcv-common.md` if not in context
2. Read this file and follow steps in order
3. Read next fragment in sequence

## Resumption

- Phase Complete entry + master log exists → resume at Step 3.
- New phase already scaffolded (own charge.md + master log in parent) → load planning-protocol.md, Step C.
- Project root after phase completes but before transition → go to phase subfolder, check for Phase Complete entry, resume at Step 3.

## Context Management

- **1M context (Max/API, Pro+extra):** Compaction optional but recommended. Run `/compact` before Phase N+1.
- **200K context (Pro default):** Compaction strongly recommended. Master log stays accessible; phase detail can clear.

## STOP Gate

All decision points require explicit user confirmation. Never assume user proceeds as planned.

---

# Transition Steps 1-3: Close Phase + Master Log + Review

## Step 1: Close Phase Decision Log

Write Phase Complete entry per pcv-common.md format. Include `[MILESTONE:PHASE_COMPLETE]` at the end of the entry header. Populate from:
1. Phase decision log → Agent Configuration entry
2. Mid-project revision entries (if any)
3. Deviation entries (if any)
4. #LEARN tags

## Step 2: Append to Master Log (MANDATORY)

**This step is non-optional.** Every completed phase MUST have a "Phase Complete" entry
in the master log. The master log is the cross-phase record that later phases and
validation tools depend on.

Master log: `../pcvplans/logs/master-log.md` (project root, shared across phases).

### Create if Missing

```markdown
# Master Decision Log — [Project Name]

This log records phase transitions, cross-phase configurations, and lessons learned.

---
```

### Append Transition Entry

Write the following block verbatim (filling in bracketed values) to the master log.
The heading **must** contain the exact words "Phase Complete" for cross-phase detection:

```markdown
## Phase [N] Complete — [Date]
**Phase Name:** [Name]
**Phase Folder:** `phase-N-name/`
**Agent Configuration:** [table: Agent|Model|Effort]
**Mid-Project Revisions:** [summary or "None."]
**Deviations:** [count or "None."]
**Lessons Learned:** [insights or "None."]
---
```

**Verification:** After writing, read the master log and confirm the "Phase [N] Complete"
heading is present. If missing, the write failed — retry before proceeding.

On long projects (5+ phases), consider archiving older entries to `master-log-archive.md`.

## Step 3: Review Tentative Phase Plan

Read `../pcvplans/make-plan.md` for tentative phase plan section.

Review Phase N outcomes (Phase Complete entry, decision log, build record):
- Simpler than expected? → consider merging subsequent phases.
- More complex? → consider splitting.
- Requirements clarified? → update Phase N+1 description.
- New phases emerged? → add to plan.

Draft updated table (do NOT write to file yet — user must approve):

```markdown
| Phase | Status | Notes |
|-------|--------|-------|
| 1: [Name] | Complete | [brief outcome] |
| 2: [Name] | Next | [unchanged or proposed revision] |
| 3: [Name] | Tentative | [unchanged or proposed revision] |
```

After updated table drafted → proceed to Step 4 (User Directs Next Phase).
