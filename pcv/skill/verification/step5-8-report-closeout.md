# Verification Steps 5-8: Report + Closeout

## Step 5: Verification Report

Present summary. After presenting the report, write a Verification Complete entry to the decision log. Include `[MILESTONE:VERIFICATION_COMPLETE]` at the end of the entry header.

```markdown
## PCV Verification Report — [Project Name]
### Deliverables Built
List each deliverable file with its absolute path. This is the primary answer to
"what was produced and where is it?"
### Verification Results
[Pattern-specific from Step 1]
### Success Criteria Mapping
[Table from Step 2]
### Planning Artifact Comparison
[From Step 3, or "All match approved specs"]
### Export Status
[Exported to [path] / No export / Skipped (same path)]
### Acceptance Testing
[Results / "Declined" / "N/A"]
### Open Issues
[Unresolved items, or "None"]
```

## Step 6: Final Git Commit

If Git available: stage all deliverable + planning files.
Commit: `"PCV verify: [Project Name] verification complete"`

## Step 7: Finalize Build Record

If `pcvplans/build-record.md` exists:

**7a.** Update Verification Status — replace "Pending" with actual results.
**7b.** Update Acceptance Testing Fixes — record fixes or "declined by user."
**7c.** Pre-Closeout User Notes:

> "Before closing out, any additional notes, observations, or context for the
> build record? Design considerations, advice for future work, anything to preserve."

**GATE.** Notes provided → append to "User Notes" dated. None → write "None."

**7d.** Update Open Items — add new, remove resolved.

## Step 8: Decision Log Closeout

Write closeout entry per pcv-common.md Project Closeout format. **Write immediately.** Include `[MILESTONE:CLOSEOUT]` at the end of the entry header.

### 8.05 Project Summary (always, all project types)

Read: pcvplans/idea.md, pcvplans/charge.md (author, project name, Deployment), decision-log.md
(clarification Q&A, key decisions), deliverable files (primary source for summary),
closeout entry.

**Filename:** Single/Lite → `pcvplans/project-summary.md`.
Multi-phase → `pcvplans/project-summary-phase-N-[name].md`.

```markdown
# Project Summary — [Project Name]
**Author:** [from charge] **Date:** [closeout date]
[If multi-phase: **Phase:** [N] — [Name]]

## Idea
[2-3 sentences from pcvplans/idea.md or charge description]

## Charge Summary
[Key requirements, constraints, tech. 3-5 sentences.]

## Planning Decisions
[Significant Q&A that shaped WHAT was built. Condensed question, answer,
how it shaped scope. Omit agent config/methodology decisions.]

## Deliverable Summary
[Read actual deliverables. Most substantial section — answers "what did this produce?"
Pattern 1: software features, architecture. Pattern 2: findings, recommendations.
Pattern 3: formulation, results. Pattern 4: design, layout approach.
Target 1/3 to 1/2 of total summary length.]

## Verification
[Pass/fail per criterion. Substantive issues found/fixed. 2-3 sentences.]

## Deployment
<!-- Only if Deployment field populated -->
[Actions performed, from decision log deployment entry.]
```

1-2 pages. Concise distillation. Professional tone. Exclude PCV process details.
Deliverable Summary most substantial, Planning Decisions second.

### 8.06 Deployment Checklist (conditional)

Only if `Deployment:` field in charge.md is populated.

1. Read deployment field + survey project for deployment files (git remote, README,
   VERSION, deployment-specific files).
2. Classify each action:
   - **Mechanical** (version bumps, file copies) → execute automatically.
   - **Push** (git push) → execute, report what/where.
   - **Content-heavy** (substantial doc rewrites) → log as open items for follow-up.
3. Order: mechanical edits → commit (`"PCV deploy: [brief]"`) → push.
4. Present summary. Log each action + deployment summary in decision log.

### 8.07 Test Suite Maintenance Check (conditional)

Only if a test suite exists for the project being modified (e.g., `tests/autotests/`
for PCV protocol work, or a project's own test directory).

1. **Assess test impact.** Review changes made in this version against existing
   test expectations (validator checks, charge responses, structural assertions).
   Flag any tests that need updating to reflect the new behavior.
2. **Update tests if needed.** Modify validators, add new test cases, or update
   charges/responses to match protocol or behavioral changes.
3. **Log.** Record any test updates in the decision log.

This step ensures the test suite stays current with protocol changes. Running
the tests themselves is a separate activity (e.g., `bash run-all.sh`).

If no test suite exists, skip silently.

### 8.1 Multi-Phase Detection

Check for `../pcvplans/logs/master-log.md`:
- **Found:** Multi-phase project. Do NOT end session. Load
  `~/.claude/skills/pcv/phase-transition-protocol.md` and follow it.
- **Not found:** Single-phase. End normally.
