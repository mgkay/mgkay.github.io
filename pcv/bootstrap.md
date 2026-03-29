# PCV Bootstrap — Plan-Construct-Verify Installer

**Version:** 3.9
**Date:** 2026-03-28

## What This File Does

This file contains the complete PCV (Plan-Construct-Verify) skill for Claude Code.
When you provide this file to Claude Code and ask it to follow the installation
instructions, it will install ten files — skill files and agent definition files —
that enable the `/pcv` command.

## Prerequisite

**Claude Code** must be installed and working on your machine. PCV is a Claude Code
skill — it runs inside Claude Code, not separately.

## How to Install

1. Start a Claude Code session.
2. Say: `Read [path-to-this-file] and follow the installation instructions inside it.`
3. Claude Code will install the files and confirm success.

---

## Instructions for Claude Code

You are reading a PCV bootstrap file. Follow these steps precisely.

### Step 1: Check for existing installation

Read `~/.claude/skills/pcv/VERSION`. If the file exists, parse the first line as a
version number. Compare it to the version in this bootstrap (3.9).

- If the installed version is **equal to or higher than** 3.9, inform the user:
  "PCV v[installed version] is already installed. No update needed."
  **STOP.**
- If the installed version is **lower than** 3.9, inform the user:
  "Updating PCV from v[installed] to v3.9." Proceed to Step 2.
- If the file does not exist, inform the user:
  "Installing PCV v3.9." Proceed to Step 2.

### Step 2: Write files

Write each of the following files using the content between the `===BEGIN path===`
and `===END path===` delimiters. Use the Write tool for each file. The paths use `~/`
notation — expand to the user's home directory.

Files are installed to two locations:
- **`~/.claude/skills/pcv/`** (6 files) — VERSION, SKILL.md, and the four protocol files (NEW: phase-transition-protocol.md).
- **`~/.claude/agents/`** (4 files) — pcv-critic.md, pcv-research.md, pcv-builder.md, pcv-verifier.md.

**Important:** Write the files in the order listed. Do not modify the content in any
way — write it exactly as provided.

### Step 3: Verify installation

After writing all ten files, verify the installation:

1. Read `~/.claude/skills/pcv/VERSION` and confirm it contains `3.9`.
2. Read `~/.claude/skills/pcv/SKILL.md` and confirm it starts with `---`.
3. Read `~/.claude/agents/pcv-critic.md` and confirm it starts with `---`.
4. Read `~/.claude/agents/pcv-research.md` and confirm it starts with `---`.

### Step 4: Inform the user

If all verifications pass, tell the user:

> **PCV v3.9 installed successfully.** Ten files written:
>
> **Skill files** (`~/.claude/skills/pcv/`):
> - `VERSION`
> - `SKILL.md`
> - `planning-protocol.md`
> - `construction-protocol.md`
> - `verification-protocol.md`
> - `phase-transition-protocol.md` (NEW in v3.9)
>
> **Agent files** (`~/.claude/agents/`):
> - `pcv-critic.md`
> - `pcv-research.md`
> - `pcv-builder.md`
> - `pcv-verifier.md`
>
> To use PCV, navigate to a project directory and type `/pcv`.

---

## Embedded Files

===BEGIN ~/.claude/skills/pcv/VERSION===
3.9
2026-03-28
Add multi-phase project support: tentative phase plans, phase transition protocol, master decision log, cross-phase learning, three entry paths, master progress display. Backward compatible with v3.8.
===END ~/.claude/skills/pcv/VERSION===

===BEGIN ~/.claude/skills/pcv/SKILL.md===
---
name: pcv
description: >
  Plan-Construct-Verify workflow for complex projects. Adds structured planning
  discipline — sequential clarification, adversarial review, human approval gates,
  and verification — on top of Claude Code's native capabilities. Invoke with /pcv.
  Suggest (once) when a user describes a complex multi-component project.
---

# Plan-Construct-Verify (PCV) — Skill Entry Point

[TRUNCATED FOR BOOTSTRAP — the full SKILL.md file is located at ~/.claude/skills/pcv/SKILL.md. Install from the source repository.]
===END ~/.claude/skills/pcv/SKILL.md===

===BEGIN ~/.claude/skills/pcv/planning-protocol.md===
# PCV Planning Protocol

[TRUNCATED FOR BOOTSTRAP — the full planning-protocol.md file is located at ~/.claude/skills/pcv/planning-protocol.md. Install from the source repository.]
===END ~/.claude/skills/pcv/planning-protocol.md===

===BEGIN ~/.claude/skills/pcv/construction-protocol.md===
# PCV Construction Protocol

[TRUNCATED FOR BOOTSTRAP — the full construction-protocol.md file is located at ~/.claude/skills/pcv/construction-protocol.md. Install from the source repository.]
===END ~/.claude/skills/pcv/construction-protocol.md===

===BEGIN ~/.claude/skills/pcv/verification-protocol.md===
# PCV Verification Protocol

[TRUNCATED FOR BOOTSTRAP — the full verification-protocol.md file is located at ~/.claude/skills/pcv/verification-protocol.md. Install from the source repository.]
===END ~/.claude/skills/pcv/verification-protocol.md===

===BEGIN ~/.claude/skills/pcv/phase-transition-protocol.md===
# PCV Phase Transition Protocol

[NEW IN v3.9 — the full phase-transition-protocol.md file is located at ~/.claude/skills/pcv/phase-transition-protocol.md. Install from the source repository.]
===END ~/.claude/skills/pcv/phase-transition-protocol.md===

===BEGIN ~/.claude/agents/pcv-critic.md===
---
name: pcv-critic
description: Adversarial reviewer for PCV planning documents. Invoked during PCV planning phase to challenge assumptions, find gaps, and identify risks.
tools: Read, Grep, Glob
model: haiku
---

[TRUNCATED FOR BOOTSTRAP — the full pcv-critic.md agent file is located at ~/.claude/agents/pcv-critic.md. Install from the source repository.]
===END ~/.claude/agents/pcv-critic.md===

===BEGIN ~/.claude/agents/pcv-research.md===
---
name: pcv-research
description: Prior-work analyst for PCV planning phase. Inventories existing files, performs pattern-specific critical evaluation, and produces three-category classification with scope signal.
tools: Read, Grep, Glob
model: sonnet
---

[TRUNCATED FOR BOOTSTRAP — the full pcv-research.md agent file is located at ~/.claude/agents/pcv-research.md. Install from the source repository.]
===END ~/.claude/agents/pcv-research.md===

===BEGIN ~/.claude/agents/pcv-builder.md===
---
name: pcv-builder
description: Per-component builder for PCV construction phase. Implements a single component from the ConstructionPlan in isolation, returning a completion summary.
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

[TRUNCATED FOR BOOTSTRAP — the full pcv-builder.md agent file is located at ~/.claude/agents/pcv-builder.md. Install from the source repository.]
===END ~/.claude/agents/pcv-builder.md===

===BEGIN ~/.claude/agents/pcv-verifier.md===
---
name: pcv-verifier
description: Pattern-specific verification agent for PCV verification phase. Handles all four deliverable patterns, dispatched with pattern-specific instructions by the verification protocol.
tools: Read, Bash, Glob, Grep
model: sonnet
---

[TRUNCATED FOR BOOTSTRAP — the full pcv-verifier.md agent file is located at ~/.claude/agents/pcv-verifier.md. Install from the source repository.]
===END ~/.claude/agents/pcv-verifier.md===

---

## Source Repository

Full versions of all files are available at:
https://github.com/mgkay/mgkay.github.io/tree/main/pcv/skill

For production installations, clone or pull from the repository instead of using this bootstrap.
