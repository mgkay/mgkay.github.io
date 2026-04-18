# Planning Step 2: Prior Work Analysis

Skip if Prior Work field is blank.

## 2.1 Read Charge First

Re-read charge narrative. Note every settled decision (tech choices, constraints,
preferences). Do not re-litigate.

## 2.2 Dispatch or Inline Research

Read Agent Configuration from decision log. No entry → v3.7 defaults.

**If dispatch mode = "Inline":**
- Execute analysis directly in hub session (keeps firsthand file knowledge).
- Read `~/.claude/agents/pcv-research.md` for behavioral checklist.
- Follow all steps inline: inventory, pattern-specific evaluation, three-category
  classification, scope signal.
- Only proposed when hub has 1M context + prior work >10 files.

**If dispatch mode = "Subagent":**
- Dispatch per pcv-common.md Agent Dispatch Pattern (role: research).
- Agent returns: file inventory, patterns detected, pattern-specific findings,
  three-category classification, scope signal.

## 2.3 Process Results

**Three-Category Classification:**
- **Already decided** — charge addresses it. List as confirmations.
- **New issues** — found in prior work, not in charge. Become clarification questions.
- **Potential conflicts** — charge vs prior work incompatibility.

**Scope Signal** (validate/adjust):
- **Verification-only** — prior work meets ALL criteria. Content specific, not just structural.
- **Scoped changes** — structure sound, content inadequate. Targeted revision.
- **Full build** — architecturally flawed or fundamentally misaligned.

Guard against over-scoping (usable structure ≠ rewrite) and under-scoping
(generic/boilerplate where specifics required = scoped changes minimum).

Do not finalize scope — clarification may change assessment.

After prior work analysis (or skip if blank) → proceed to Step 3 (Patterns + Clarification).
