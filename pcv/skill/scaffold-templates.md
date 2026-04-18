# PCV Scaffold Templates

---

## 3. CLAUDE.md Template

```
# <Project Name>
Language: <Language>
When compacting, preserve decision log (pcvplans/logs/decision-log.md) and all files in pcvplans/.
```

Under 5 lines. User customizes after scaffold.

---

## 4. Charge Template

```markdown
# Project Charge

## Configuration
Name: <REPLACE>
Project Name: <REPLACE>
Project Directory:
<!-- Absolute or relative path to code/deliverables. Blank = this directory. -->
Export Target:
<!-- Where verified files are copied. Blank = no export. -->
Prior Work:
<!-- Path(s) to previous versions. Blank = starting fresh. -->
Deployment:
<!-- Where deployed/published (GitHub Pages, npm, etc). Blank = local only. -->

## Project Description
<!-- What are you building? Who is it for? -->

## Technology & Constraints
<!-- Language/framework? Requirements/limitations? -->

## Prior Work Notes
<!-- What to keep, change, improve from previous version? -->

## Success Criteria
<!-- How will you know it's done? What must be true? -->
```

Field definitions: Name = human's name. Project Name = for headers/git.
Project Directory = deliverables location. Export Target = post-verify copy dest.
Prior Work = reference material paths. Deployment = publish target (triggers
deployment checklist at closeout when populated).

---

## 4a. Idea Template

```markdown
<!-- Describe your project idea here. Be informal — PCV will generate
     a structured charge from this. -->
```

---

## 8. Multi-Phase Scaffolding

### 8.1 Project-Level

1. Create project-level charge.md with multi-phase config.
2. Create project-level `pcvplans/make-plan.md` with tentative phase plan.
3. Create `pcvplans/logs/master-log.md`:
   ```markdown
   # Master Decision Log — [Project Name]
   ## Multi-Phase Project Initiated — [Date]
   **Phase structure:** [N phases] **Phase 1 focus:** [brief]
   ---
   ```
4. Update project .claude/settings.json (full perms).

### 8.2 Phase 1 Subfolder

1. Create `phase-1-[name]/` dir.
2. Create phase-specific charge.md.
3. Create CLAUDE.md (§3 template with phase name).
4. Write `pcvplans/.gitkeep`.
5. Run `bash scaffold-settings.sh --project-dir .`
6. Continue planning Phase 1. Do NOT scaffold Phase 2+ yet.

### 8.3 Mid-Project Conversion

Safe restructure: dry-run → confirm → copy to phase-1/ → verify → delete originals →
create project-level structure (§8.1) → resume planning in phase subfolder.

---

### 3a. Version Chaining (completed project)

> "(a) New revision cycle (versioned sibling) or (b) Reopen for fixes?"
**GATE.**

**(b) Reopen:** Log "Reopened for Fixes." Wait for issues. Fix each, log as
Post-Closeout Fix. All done → Re-Closeout entry + commit.

**(a) First revision (no v*/ siblings):**
1. Dry-run: inventory files. Present list. **GATE.**
2. Commit checkpoint.
3. Copy all to v1/ (Read/Write tools). Verify file count. Delete originals.
4. Create parent CLAUDE.md (version chain header).
5. Scaffold v2/ (pcv_idea.md, pcvplans/charge.md w/ Prior Work=../v1, settings, pcvplans, CLAUDE.md).
6. "Project restructured. Describe revision in v2/pcv_idea.md." **STOP.**

**Subsequent:** Scan v*/ for max N. Scaffold vN+1/ with Prior Work=../vN. **STOP.**
