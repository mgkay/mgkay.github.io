## Step Sequence

| Step | Fragment | Action |
|------|----------|--------|
| 1-7 | `construction/steps.md` | Resolve dir, baseline copy, build components, deviations, git commits, construction complete, build record |

## Loading

1. Read `~/.claude/skills/pcv/pcv-common.md` if not in context
2. Read this file (`construction/steps.md`) and follow steps in order

## Resumption

Per pcv-common.md Session Resumption Pattern. Additionally:
- Survey project dir (Glob/Bash for file existence).
- If Git available, check `git log --oneline` for construction commits.
- Compare state against ConstructionPlan. Present status: complete / remaining / anomalies.
- Wait for confirmation before continuing.

---

# Construction Steps 1-3: Baseline + Build

## Step 1: Resolve Working Directory

- Read Project Directory from pcvplans/charge.md. Specified → deliverables there. Blank → current dir.
- Verify the File Structure in the ConstructionPlan places deliverables in the project
  root, not in `pcvplans/`. If deliverables target `pcvplans/`, flag to user before proceeding.

## Step 2: Baseline Copy

If ConstructionPlan has Baseline Preservation and prior work is separate:
1. Copy "unchanged" and "modified" files from prior work into project dir.
2. Use Read/Write tools or cross-platform scripting. NO OS-specific `cp`/`copy`.
3. Log each copy in decision log. Verify intact.
4. Copy ALL baseline first, THEN modify. No interleaving.

## Step 2.5: Permission Pre-Flight

Run: `bash ~/.claude/skills/pcv/hooks/tech-permissions-scan.sh --project-dir .`

Detects technology keywords, maps to `Bash([tool] *)` patterns, adds to settings.json.
Review output, manually add any missed. Idempotent — safe to re-run.

### Bash Safety Rules
- Never pass multi-line scripts inline. Write to `tmpclaude_*` file, run, delete.
- No shell redirects (`>`, `>>`, `|`). Handle I/O inside the script.
- No command chaining (`&&`, `||`, `;`). One command per Bash call.
- Use absolute paths. No `cd`. Use `git -C /path`.

These rules apply to builder agents too (in their constraints + dispatch prompts).

## Step 3: Build in ConstructionPlan Order

### 3.1 Lite Inline Construction

When `pcvplans/lite-plan.md` exists (not construction-plan.md):
- Build all components directly in hub session per Approach section.
- Same deviation logging (Step 4), milestone commits (Step 5).
- Generate build record unless trivial (single-file, no decisions).
- Skip 3.2-3.4. After construction → Step 6.

Note: mid-construction simplification does NOT trigger Lite switch. Note in
build record: "Consider Lite for similar projects." Lite is a planning-time decision.

### 3.2 Sequential Dispatch Loop

For each component in dependency order:
1. Read Agent Configuration from decision log (first dispatch only). No entry → v3.7 defaults.
   Read `~/.claude/agents/pcv-builder.md` once (first dispatch only — cache in context for subsequent dispatches).
2. Extract component spec from ConstructionPlan.
3. Dispatch pcv-builder per pcv-common.md Agent Dispatch Pattern. For second and
   subsequent dispatches, re-inline builder instructions from the cached copy in
   context (do not re-Read the file from disk). Pass: component spec,
   planning artifacts path, project dir, prior work path (if applicable).
4. Wait for completion. Review summary.
5. Deviations → present to user per Step 4. Do not dispatch next until resolved.
6. Success → log in decision log. Include `[MILESTONE:BUILDER_DISPATCH_N]` on the dispatch entry header and `[MILESTONE:BUILDER_COMPLETE_N]` on the completion entry header (replace N with component number). Git commit if available.
7. Next component only after current completes.

### 3.3 Sequential Enforcement

**One builder at a time.** If dispatching multiple in one response → STOP, error.
No parallel builders unless ConstructionPlan explicitly marks components parallel-safe.

### 3.4 Mid-Project Revision

Track deviation count. At 2+ deviations on multi-component project (3+ total):

> "Builder reported deviations on [N] of [total] components. Revise builder config?"
> | Agent | Current | Proposed | Rationale |

**GATE.** Approved → log Configuration Revision entry, update config for remaining.
Declined → log, continue.

### 3.5 Mid-Construction Phase Restructure (v3.9) (J15 — mid-construction-restructure judgment gate)

If scope creep reveals sequential dependencies benefiting from multi-phase:

**Trigger:** scope depends on validation of earlier components + not already multi-phase +
at least one component complete.

Propose restructure. If accepted:
1. Write "Construction Complete — Phase 1" entry.
2. Apply safe restructure: document state, create multi-phase structure, dry-run,
   confirm, copy to phase-1/, verify, delete originals.
3. Load phase-transition-protocol.md.

If declined → log as "Proposed but declined," continue single-phase.

### 3.6 Planning Artifact References

Builder references `pcvplans/artifacts/` during construction: wireframes, architecture
diagrams, data models, math formulations, pseudocode, test specs.

After all components built (or Lite construction complete) → proceed to Step 4 (Deviations + Record).

# Construction Steps 4-7: Deviations + Record

## Step 4: Handle Deviations

If something in the approved plan (ConstructionPlan or lite-plan.md) doesn't work:
1. Do NOT silently change approach.
2. Explain: what was planned, what went wrong, what alternatives exist.
3. **GATE.**
4. Log deviation per pcv-common.md Deviation format.

## Step 5: Git Commits

If Git available, commit at:
- Baseline copy complete
- Each major component built + verified
- All construction complete (pre-verification)

Format: `"PCV construct: [brief] for [Project Name]"`
Git is silent — don't ask user about commits.

## Step 6: Construction Complete

When all plan items built (ConstructionPlan components or Lite approach items):
1. Write Construction Complete entry to decision log immediately. Include `[MILESTONE:CONSTRUCTION_COMPLETE]` at the end of the entry header.
2. Inform user: "Construction complete. Ready for verification."
   Name each deliverable file and its absolute path. Example:
   "Construction complete. Deliverable: `optimization-analysis.md` at `/path/to/project/optimization-analysis.md`. Ready for verification."

## Step 7: Generate Build Record

After Construction Complete entry. Generate `pcvplans/build-record.md` per the template below.

### Build Record Template

```
# Build Record — [Project Name]

## Overview
[1-2 sentences]

## Files Modified
| File | Change |
|------|--------|

## Design Decisions During Construction
[Choices on details plan left unspecified. Not deviations.]

## Deviations from Plan
[From decision log, or "None."]

## Acceptance Testing Fixes
[From verification Step 4.5, or "N/A."]

## Verification Status
[Pending / Updated during verification]

## Open Items
[Known issues, deferred work]

## Lessons Learned
[#LEARN entries + additional insights]

## User Notes
[Reserved — populated at pre-closeout prompt]
```

### When
Generate when: >3 files modified OR any deviations OR design decisions during
construction. Otherwise skip, note in decision log: "Build record skipped
(≤3 files, no deviations, no design decisions)."

### Source Material
- Decision log entries (deviations, clarifications, #LEARN)
- Construction plan (planned vs actual)
- Git history (milestone commits)

AI drafts — do not ask human to write it.

### After Generating
1. Present draft for review.
2. Build record remains open — appended during verification.
3. Transition → read verification-protocol.md.
