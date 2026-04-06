# PCV Phase Transition Protocol

You are executing the **Phase Transition Protocol**. This protocol runs at phase
completion when multi-phase context is detected. Follow these instructions precisely.

---

## Step 1: Close Phase Decision Log

Append a **Phase Complete** entry to the phase-specific decision log at `plans/logs/decision-log.md`.

### 1.1 Entry Format

```markdown
## Phase Complete — [Date]

**Phase:** [Phase Name]

**Agent Configuration Used:**
| Agent | Model | Effort |
|-------|-------|--------|
| Builder | [model] | [effort] |
| Verifier | [model] | [effort] |

**Mid-Project Revisions:** [If any configuration revisions occurred, list them; otherwise "None."]

**Deviations:** [If any deviations were approved during construction, list them briefly; otherwise "None."]

**Lessons Learned:** [Any insights about this phase's scope, complexity, or approach that inform the next phase. Or "None."]

---
```

### 1.2 Populate from History

1. Read the phase's decision log (`plans/logs/decision-log.md` in the current phase folder).
2. Extract the Agent Configuration entry (created during planning).
3. Extract any mid-project revision entries (from Step 3.4 of construction-protocol.md).
4. Extract any deviation entries (from Step 4 of construction-protocol.md).
5. Extract any #LEARN tags from the decision log.
6. Write the Phase Complete entry using the format above.

---

## Step 2: Append to Master Log

Read or create the master decision log at `../plans/logs/master-log.md` (relative to
the phase subfolder, i.e., one level up to the project root).

### 2.1 Master Log Location

The master log lives in the project root, shared across all phases:
```
MyProject/
├── plans/logs/master-log.md    ← Master log (cross-phase state)
└── phase-1-name/
    └── plans/logs/decision-log.md  ← Phase-specific log
```

### 2.2 Create Master Log (if missing)

If `../plans/logs/master-log.md` does not exist:

1. Create the parent directory `../plans/logs/` if needed.
2. Write an initial master log with a header:

```markdown
# Master Decision Log — [Project Name]

This log records phase completion transitions, cross-phase configurations,
mid-project revisions, and lessons learned across all phases.

---
```

3. Proceed to Step 2.3.

### 2.3 Append Transition Entry

Read the master log. Append a new transition entry at the end:

```markdown
## Phase [N] Complete — [Date]

**Phase Name:** [Phase Name]

**Phase Folder:** `phase-N-name/`

**Agent Configuration:**
| Agent | Model | Effort |
|-------|-------|--------|
| Builder | [model] | [effort] |
| Verifier | [model] | [effort] |

**Mid-Project Revisions:** [If any occurred during Phase N, summarize; otherwise "None."]

**Deviations:** [Count of deviations approved during construction, or "None."]

**Lessons Learned:** [Key insights from Phase N that inform subsequent phase planning. Or "None."]

---
```

### 2.4 Advisory Note on Master Log Growth

After appending, add a comment to the end of the master log (this note is administrative,
not part of the transition entry):

> **Note:** The master log grows with each phase transition. On very long projects
> (5+ phases), consider archiving older phases' entries to a separate `master-log-archive.md`
> for readability. For now, preserve the full history.

---

## Step 3: Review Tentative Phase Plan

The tentative phase plan lives in the project-level MakePlan. Read it, update it based
on what Phase N's results revealed, and present the updated plan to the user.

### 3.1 Read Project-Level MakePlan

Read `../plans/make-plan.md` (relative to the phase subfolder). This file contains the
tentative phase plan section, typically in the middle of the document.

### 3.2 Draft Updated Plan Table

Review Phase N's outcomes (from the Phase Complete entry, decision log, build record
if it exists):

- Did Phase N's work reveal simpler-than-expected structure? Consider merging subsequent phases.
- Did Phase N's work reveal greater complexity? Consider splitting a subsequent phase.
- Did Phase N's deliverables clarify requirements for Phase N+1? Update Phase N+1's description.
- Are there new phases that emerged from Phase N's results? Add them to the tentative plan.

Draft an updated table. **Do NOT modify the master MakePlan file yet** — the user must
approve any changes to the plan. Format:

```markdown
| Phase | Status | Notes |
|-------|--------|-------|
| 1: [Name] | ✓ Complete | [Brief outcome, e.g., "Scaffold established; 12 section files"] |
| 2: [Name] | Next | [Status: Unchanged, or a proposed revision] |
| 3: [Name] | Tentative | [Status: Unchanged, or a proposed revision] |
| ...
```

---

## Step 4: User Directs Next Phase

Present the updated phase plan to the user and ask what to do next.

### 4.1 Phase Plan Presentation

> "[Phase N name] is complete. Here's the updated phase plan:"
>
> [Updated table from Step 3.2]
>
> *You can:*
> - **(A) Proceed to Phase [N+1]** as planned.
> - **(B) Modify the phase plan** — merge phases, split a phase, reorder, add new phases,
>   adjust scope.
> - **(C) Describe a new phase** not in the tentative plan.
> - **(D) Declare the project complete** — remaining phases are deferred.
> - **(E) Collapse remaining phases** — merge all tentative work into a single final phase.
> - **(F) Convert to single-phase** — fold remaining work into reopen-for-fixes on the
>   last completed phase.

**STOP. Wait for the user's response.**

### 4.2 Handle Option A: Proceed as Planned

If the user chooses **(A)**, extract the next phase name and focus from the tentative plan
and proceed to Step 5 (scaffold).

### 4.3 Handle Option B: Modify the Plan

If the user chooses **(B)**, collaborate with the user to refine the plan:

1. Present the current tentative phases with their descriptions.
2. For each proposed change, confirm understanding: "You'd like to merge Phase 2 and 3
   into a single Content phase — is that right?"
3. Draft the updated tentative phase plan.
4. Ask: "Should I write this updated plan to the project-level MakePlan?" Wait for
   confirmation, then update `../plans/make-plan.md`.
5. Extract the next phase name and proceed to Step 5 (scaffold).

### 4.4 Handle Option C: New Phase

If the user chooses **(C)**, they describe a phase not in the tentative plan:

1. Collaborate to capture the new phase's focus, dependencies, and success criteria.
2. Insert the new phase into the tentative plan in the correct location (respecting
   dependencies).
3. Update `../plans/make-plan.md` with the new tentative phase plan.
4. Proceed to Step 5 with the newly described phase.

### 4.5 Handle Option D: Declare Complete

If the user chooses **(D)**, the project is complete even though tentative phases remain:

1. Update the master log's final entry:
   ```markdown
   **Project Status:** Complete — remaining phases deferred.
   **Deferred Phases:**
   - [Phase N+1: Description]
   - [Phase N+2: Description]
   - ...
   ```

1.5 **Generate master project summary (v3.10).** Read all per-phase summaries
    from each completed phase's `plans/` directory (files matching
    `project-summary-phase-*.md`). Generate a lightweight master summary at
    the project root:

    Write to `plans/project-summary.md`:

    ```markdown
    # Project Summary — [Project Name]

    **Author:** [Name from charge]
    **Date:** [final closeout date]
    **Phases:** [N completed]

    ## Phase Overview

    | Phase | Name | Summary File |
    |-------|------|-------------|
    | 1 | [Name] | [relative path to phase summary] |
    | 2 | [Name] | [relative path to phase summary] |
    | ... | ... | ... |

    ## Project Arc
    [2-3 sentences describing the overall project trajectory across phases —
     what was accomplished, how the project evolved from phase to phase.]
    ```

    This is a table-of-contents document that links to individual phase summaries.
    Keep it lightweight — do not reproduce phase summary content.

2. Commit to Git if available: `"PCV: Phase [N] complete — project deferred pending future phases"`
3. Inform the user: "Project marked complete. Deferred phases logged in master log for
   future reference."
4. End the session.

### 4.6 Handle Option E: Collapse Remaining

If the user chooses **(E)**, merge all remaining tentative phases into one:

1. Review the remaining tentative phases and consolidate their scope into a single
   "Final" phase.
2. Update the tentative phase plan: show all completed phases, then a single "Final"
   phase combining the remaining work.
3. Update `../plans/make-plan.md`.
4. Generate a master project summary linking all completed phase summaries
   (same format as Option D Step 1.5 above).
5. Proceed to Step 5, scaffolding the final collapsed phase.

### 4.7 Handle Option F: Convert to Single-Phase

If the user chooses **(F)**, remaining work becomes a reopen-for-fixes on the last
completed phase:

1. Update the master log: "Converted to single-phase mode — remaining work will be
   addressed via reopen-for-fixes on Phase [N]."
2. Generate a master project summary linking all completed phase summaries
   (same format as Option D Step 1.5 above).
3. Generate a charge for the remaining work (summary of all remaining tentative phases).
4. Instruct the user: "Remaining work will be handled via `/pcv reopen` on Phase [N]'s
   subfolder when you're ready." (Per the existing revision chaining workflow.)
5. Commit to Git if available.
6. End the session.

---

## Step 5: Scaffold Next Phase Subfolder

Create a new phase subfolder with the phase-specific artifacts needed to start Phase N+1.

### 5.1 Determine Phase Name

From Step 4, extract the phase name. Use a descriptive name: `phase-1-scaffold`, `phase-2-content-acquisition`, etc.

### 5.2 Create Folder Structure

The phase needs:

```
phase-N-name/
├── charge.md                   (phase-specific charge, fully specified)
├── CLAUDE.md                   (phase identity)
├── .claude/
│   └── settings.json           (same permission pre-approvals as project root)
└── plans/
    └── .gitkeep                (empty file to establish directory)
```

### 5.3 Create CLAUDE.md

Use the same template as the project root:

```markdown
# [Project Name] — [Phase Name]

Language: [Markdown|Python|Julia|etc.]
When compacting, preserve decision log (plans/logs/decision-log.md) and all files in plans/.
```

### 5.4 Create .claude/settings.json

Copy the project root's `.claude/settings.json` to the phase subfolder:

```json
{
  "permissions": {
    "allow": [
      "Read(~/.claude/agents/pcv-critic.md)",
      "Read(~/.claude/agents/pcv-research.md)",
      "Read(~/.claude/agents/pcv-builder.md)",
      "Read(~/.claude/agents/pcv-verifier.md)",
      "Read(~/.claude/skills/pcv/*)",
      "Read(**)",
      "Write(**)",
      "Glob(*)",
      "Grep(*)",
      "Bash(git *)"
    ]
  }
}
```

Technology-specific permissions (e.g., `Bash(julia *)`, `Bash(npm *)`) are added at
Gate 3 transition per construction-protocol.md Step 2.5.

### 5.5 Create Phase-Specific Charge

The phase charge is derived from the tentative phase plan and the user's direction in Step 4.

**Prior Work section:** Point to completed phases:

```markdown
## Prior Work

- Phase 1: [Name] — `/path/to/phase-1-name/`
- (and any other completed phases, if applicable)
```

**All other sections:** Use the same template as the project-level charge (from SKILL.md
Section 4). Populate from the tentative phase plan:

- **Project Name:** Same as project root
- **Name:** Phase N — [Phase Name]
- **Charge Summary:** [Focus and success criteria from tentative plan]
- **Configuration:** [Project Directory, Export Target, etc. — typically same as Phase 1]
- **Success Criteria:** [Specific, testable criteria for this phase]
- **Deviations (optional):** Leave blank initially

### 5.6 Create plans/.gitkeep

Write an empty `.gitkeep` file to establish the `plans/` directory:

```
(empty file)
```

### 5.7 Confirm Creation

Verify all files exist:
- `phase-N-name/charge.md`
- `phase-N-name/CLAUDE.md`
- `phase-N-name/.claude/settings.json`
- `phase-N-name/plans/.gitkeep`

---

## Step 6: Begin Next Phase Planning

Load the planning protocol and start Phase N+1.

### 6.1 Transition Message

Inform the user:

> "Phase [N+1] scaffolded at `phase-N+1-name/`. Loading planning protocol..."

### 6.2 Load Planning Protocol

Read `~/.claude/skills/pcv/planning-protocol.md` for the next phase.

### 6.3 Route to Planning Step C

Begin planning at **Step C** of the planning protocol (Validate and Route):

1. Change working directory context to the phase subfolder.
2. Read the phase-specific `charge.md` (now at `phase-N+1-name/charge.md`).
3. Follow planning-protocol.md Steps C onwards: plan tier check, git setup, progress
   display, and route to the planning workflow (Plan or Clarify).

### 6.4 Cross-Phase Learning at Step 1.5.1

During planning Step 1.5.1 (master log read), the planning protocol will read the
master log just created in Step 2, incorporating prior phase performance into the
agent configuration proposal for Phase N+1.

---

## Context Management

### Recommendation Between Phases

At the completion of Phase N (after Phase Complete entry is written), assess context usage:

- **On 1M context (Max/API default, or Pro with `/extra-usage`):** Compaction is optional but
  recommended. The master log is safe to retain; the phase's decision log can be archived.
  Run `/compact` to reset before beginning Phase N+1 planning.

- **On 200K context (Pro default):** Compaction is strongly recommended. The master log must
  remain accessible (Step 6.4), but the previous phase's detailed logs and build artifacts
  can be cleared. Run `/compact` before beginning Phase N+1 planning. The next session will
  read the master log to reconstruct multi-phase state.

After compaction, begin Phase N+1 planning immediately (Step 6) or wait for the next session.

---

## Session Resumption

If you resume work in a new conversation and need to continue a multi-phase project:

### Phase Transition Already Completed

If the phase's decision log has a Phase Complete entry and the master log exists at
`../plans/logs/master-log.md`:

1. You are mid-transition. Resume at **Step 3** (Review Tentative Phase Plan).
2. Read the master log and the updated tentative phase plan from the project-level MakePlan.
3. Present the phase plan to the user and proceed to Step 4 (User Directs Next Phase).

### New Phase Already Scaffolded

If you resume in a phase subfolder that has its own `charge.md` and the master log exists
in the parent:

1. This is a new phase (Phase N+1) ready for planning.
2. Load planning-protocol.md and proceed to Step C (Validate and Route).
3. Planning Step 1.5.1 will automatically read the master log for cross-phase learning.

### Multi-Phase Project in Initial State

If you resume at the project root after Phase 1 completes but before Phase 2 transition:

1. Change context to the Phase 1 subfolder.
2. Read the verification protocol's Step 8 (Decision Log Closeout).
3. A Phase Complete entry should already be written. Check for it.
4. If Phase Complete entry exists and master log exists, you are mid-transition — resume
   at Phase Transition Protocol Step 3.

---

## STOP Gate

**All decision points in this protocol require explicit user confirmation.** Do not
assume the user will proceed as planned. Wait for their response at:

- Step 4.1 — Phase plan presentation and user direction
- Step 4.3 — Confirmation of plan modifications
- Step 5.7 — Confirmation of scaffold completion (before beginning next planning)

The user retains full control over phase sequencing, scope, and exit ramps.

---
