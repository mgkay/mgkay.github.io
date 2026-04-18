# Transition Steps 5-6: Scaffold + Begin Next Phase

## Step 5: Scaffold Next Phase

### 5.1 Create Mechanical Files

Run: `bash ~/.claude/skills/pcv/hooks/scaffold-phase.sh --phase-name "<name>" --project-name "<Project Name>" --parent-dir .`

Creates: phase dir, CLAUDE.md, .claude/settings.json (via scaffold-settings.sh), pcvplans/.gitkeep.
Phase number auto-detected from existing phase-*/ dirs.

### 5.2 Create Phase-Specific Charge

Write `<phase-dir>/pcvplans/charge.md` from tentative plan + user direction (Step 4).

**Prior Work section (MANDATORY for Phase 2+).** This field must not be blank.
List every completed phase as a prior work entry. Use this exact format:
```markdown
- **Prior Work:** Phase 1 ([Phase 1 Name]) — `../phase-1-[slug]/`
```
For 3+ completed phases, list each on its own line:
```markdown
- **Prior Work:**
  - Phase 1 ([Name]) — `../phase-1-[slug]/`
  - Phase 2 ([Name]) — `../phase-2-[slug]/`
```

**Verification:** After writing charge.md, confirm the Prior Work field contains
a non-blank value referencing at least one prior phase directory.

Other sections: standard charge template (SKILL.md §4). Populate from tentative plan:
- Project Name: same as root
- Name: Phase N — [Phase Name]
- Configuration: typically same as Phase 1
- Success Criteria: specific, testable for this phase

### 5.2a Initialize Phase Decision Log

Write `<phase-dir>/pcvplans/logs/decision-log.md` with a fresh header:
```markdown
# Decision Log — [Project Name]
```
This will be populated during Phase N+1 planning (agent config, clarification, etc.).

### 5.3 Confirm

Verify all files exist:
- `phase-N-name/pcvplans/charge.md`
- `phase-N-name/pcvplans/logs/decision-log.md`
- `phase-N-name/CLAUDE.md`
- `phase-N-name/.claude/settings.json`

## Step 6: Begin Next Phase Planning

### 6.1 Transition Message

> "Phase [N+1] scaffolded at `phase-N+1-name/`. Loading planning protocol..."

### 6.2 Load Planning Protocol

Read `~/.claude/skills/pcv/planning-protocol.md`.

### 6.3 Route to Planning Step C

Begin at Step C (Validate and Route) of planning protocol:
1. Working directory context → phase subfolder.
2. Read phase-specific charge.md.
3. Follow planning steps: plan tier check, git setup, progress display, plan workflow.

### 6.4 Cross-Phase Learning

Planning Step 1.4 (agent config) will read master log from Step 2,
incorporating prior phase performance into configuration proposal.

Phase transition complete. Planning protocol now active for Phase N+1.
