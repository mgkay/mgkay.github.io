# PCV Construction Protocol

You are in the **Construct** phase of the PCV workflow. The ConstructionPlan has been
approved by the human. It is your contract — follow it precisely.

---

## Step 1: Resolve Working Directory

1. Read the **Project Directory** field from `charge.md`.
2. If specified, all deliverable work happens at that path. Planning artifacts remain
   in the current (PCV home) directory.
3. If blank, work in the current directory.

---

## Step 2: Baseline Copy (if applicable)

If the ConstructionPlan includes a **Baseline Preservation** section and prior work
is at a separate location:

1. Copy files listed as "unchanged" or "modified" from the prior work location into
   the project directory.
2. **Use internal Read/Write tools or cross-platform scripting (e.g., Python one-liner)
   for file copies. Do NOT use OS-specific shell commands (`cp`, `copy`) via Bash.**
3. Log each copied file in the decision log.
4. Verify copied files are intact before proceeding.

### Copy-Then-Modify Sequencing

- First, copy ALL baseline files.
- Then, begin modifications per the ConstructionPlan.
- Do not interleave copying and modifying — complete the baseline before changing anything.

---

## Step 2.5: Permission Pre-Flight

Ensure the `/pre-approve` skill is available, then run it against
`plans/construction-plan.md` to resolve permission gaps before construction begins.

### Dependency Check

1. Check if `~/.claude/skills/pre-approve/SKILL.md` exists.
2. **If missing:** Copy the bundled version from
   `~/.claude/skills/pcv/bundled/pre-approve-SKILL.md` into
   `~/.claude/skills/pre-approve/SKILL.md` (create the directory if needed).
   Inform the user: "Installed bundled /pre-approve skill."
3. **If present:** Compare its contents against the bundled version.
   - If identical: proceed.
   - If different: warn the user that the installed version differs from the
     PCV-bundled version. Show which is newer (by file modification time) and
     ask whether to (a) keep the installed version, (b) overwrite with the
     bundled version, or (c) skip pre-approval entirely.

### Run Pre-Approval

- Invoke `/pre-approve plans/construction-plan.md`.
- If the user has already run `/pre-approve` for this plan, skip this step.

---

## Step 3: Build in ConstructionPlan Order

The ConstructionPlan specifies a dependency order. Follow it.

1. Build each component in the specified sequence.
2. Reference planning artifacts in `plans/artifacts/` during construction:
   - Wireframes and mockups inform visual implementations.
   - Architecture diagrams inform module structure.
   - Data models inform schema and type definitions.
   - Math formulations inform solver implementations.
   - Pseudocode informs complex logic.
   - Test specifications inform test implementations.
3. After each major component, verify it works in isolation before proceeding to
   dependent components.

---

## Step 4: Handle Deviations

If something in the ConstructionPlan doesn't work during construction:

1. **Do NOT silently change approach.**
2. Explain the issue to the human clearly:
   - What was planned.
   - What went wrong.
   - What alternatives exist.
3. **Wait for human approval before changing approach.**
4. Log the deviation in the decision log:
   ```
   ## Deviation — [Date]
   **Planned:** [What the ConstructionPlan specified]
   **Issue:** [What went wrong]
   **Resolution:** [What was done instead, with human approval]
   #LEARN [If applicable: what lesson this teaches]
   ```

---

## Step 5: Git Commits at Milestones

If Git is available, commit at logical milestones:

- After baseline copy is complete.
- After each major component is built and verified.
- After all construction is complete (pre-verification).

**Commit message format:** `"PCV construct: [brief description] for [Project Name]"`

Git is silent — do not ask the user about commits. Just commit at milestones.

---

## Step 6: Construction Complete

When all ConstructionPlan items are built:

1. **Append a "Construction Complete" entry to the decision log now, before doing
   anything else.** Do not defer this write.
2. Inform the human: "Construction complete per the approved plan. Ready to proceed
   to verification."
3. **Transition to Verify phase:** Read `~/.claude/skills/pcv/verification-protocol.md`
   and follow it.

---

## Session Resumption

If resuming construction in a new conversation:

1. Read `charge.md` and `plans/construction-plan.md`.
2. Read `plans/logs/decision-log.md` for context.
3. Survey the project directory (use Glob/Bash to check file existence and state).
4. If Git is available, check `git log --oneline` for construction commit history.
5. Compare the current state against the ConstructionPlan.
6. Present a status summary to the human:
   - Components that appear complete.
   - Components that remain.
   - Any anomalies detected.
7. **Wait for human confirmation before continuing.**
