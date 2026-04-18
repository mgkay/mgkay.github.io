# PCV Bootstrap — Plan-Construct-Verify Installer

**Version:** 3.14
**Date:** 2026-04-18

## What This File Does

This file is an installer manifest for the PCV (Plan-Construct-Verify) skill for Claude Code. When you provide this file to Claude Code and ask it to follow the installation instructions, it will install the full PCV skill — protocol files, handlers, hooks, and agent definitions — that enable the `/pcv` command.

## Prerequisite

**Claude Code** must be installed and working on your machine. PCV is a Claude Code skill — it runs inside Claude Code, not separately.

## How to Install

1. Start a Claude Code session (anywhere — PCV is installed to your user profile, not a specific project).
2. Say: `Read https://mgkay.github.io/pcv/bootstrap.md and follow the installation instructions inside it.`
3. Claude Code will download the skill files and confirm success.

---

## Instructions for Claude Code

You are reading the PCV v3.14 bootstrap manifest. Follow these steps precisely.

### Step 1: Check for existing installation

Read `~/.claude/skills/pcv/VERSION`. If the file exists, parse the first line as a version number. Compare it to the version in this bootstrap (3.14).

- If the installed version is **equal to** 3.14, inform the user: "PCV v3.14 is already installed. No update needed." **STOP.**
- If the installed version is **higher than** 3.14, inform the user: "PCV v[installed] is newer than this bootstrap (3.14). Aborting — will not downgrade." **STOP.**
- If the installed version is **lower than** 3.14, inform the user: "Updating PCV from v[installed] to v3.14." Proceed to Step 2.
- If the file does not exist, inform the user: "Installing PCV v3.14." Proceed to Step 2.

### Step 2: Download and write all files

For each file listed in the MANIFEST below:

1. Fetch the file content from `https://mgkay.github.io/pcv/<relative-path>` using WebFetch.
2. Write the fetched content to the corresponding path under `~/.claude/skills/pcv/` or `~/.claude/agents/` using the Write tool.
3. Create any needed parent directories (the Write tool creates them implicitly on most systems).

**If any WebFetch fails**, stop and report the specific file + URL to the user. Do not continue with a partial install.

**Important:** write files exactly as fetched. Do not modify content.

### Step 3: Verify installation

After writing all files, verify:

1. Read `~/.claude/skills/pcv/VERSION` → first line must be `3.14`.
2. Read `~/.claude/skills/pcv/SKILL.md` → must exist and begin with `---`.
3. Read `~/.claude/skills/pcv/handlers/lib.sh` → must exist (new in v3.14).
4. Read `~/.claude/skills/pcv/hooks/session-start-resume.sh` → must contain the string `v3.14 session-state sentinel write` (confirms the v3.14 sentinel writer is present).
5. Read `~/.claude/agents/pcv-critic.md` → must begin with `---`.

### Step 4: Inform the user

On success, tell the user:

> **PCV v3.14 installed successfully.**
>
> **Protocol files** (`~/.claude/skills/pcv/`): SKILL.md, pcv-common.md, planning-protocol.md, construction-protocol.md, verification-protocol.md, phase-transition-protocol.md, scaffold-templates.md, VERSION, plus fragments under `planning/`, `construction/`, `verification/`, `transition/`.
> **Handlers** (`~/.claude/skills/pcv/handlers/`, NEW in v3.14): lib.sh + 8 mechanical gate handlers (hook-registration, plan-tier, git-setup, global-settings, charge-write, test-response-clarification, test-response-escalation, scope-creep-trigger).
> **Hooks** (`~/.claude/skills/pcv/hooks/`): pcv-lib.sh, session-start-resume.sh, scaffold-settings.sh, scaffold-phase.sh, stop-closeout.sh, pre-compact-snapshot.sh, post-tool-use-format.sh, subagent-stop-track.sh, tech-permissions-scan.sh, validate-pcv-format.sh.
> **Agents** (`~/.claude/agents/`): pcv-critic.md, pcv-research.md, pcv-builder.md, pcv-verifier.md.
>
> To use PCV, navigate to a project directory and type `/pcv`.

---

## MANIFEST — files to install

Each entry is `source-URL → destination-path`. All source URLs are under `https://mgkay.github.io/pcv/`; destinations are under `~/.claude/`.

### Protocol files (skill root)
- `skill/VERSION` → `~/.claude/skills/pcv/VERSION`
- `skill/SKILL.md` → `~/.claude/skills/pcv/SKILL.md`
- `skill/pcv-common.md` → `~/.claude/skills/pcv/pcv-common.md`
- `skill/scaffold-templates.md` → `~/.claude/skills/pcv/scaffold-templates.md`
- `skill/planning-protocol.md` → `~/.claude/skills/pcv/planning-protocol.md`
- `skill/construction-protocol.md` → `~/.claude/skills/pcv/construction-protocol.md`
- `skill/verification-protocol.md` → `~/.claude/skills/pcv/verification-protocol.md`
- `skill/phase-transition-protocol.md` → `~/.claude/skills/pcv/phase-transition-protocol.md`

### Planning fragments
- `skill/planning/step1-charge-config.md` → `~/.claude/skills/pcv/planning/step1-charge-config.md`
- `skill/planning/step2-prior-work.md` → `~/.claude/skills/pcv/planning/step2-prior-work.md`
- `skill/planning/step3-4-patterns-clarify.md` → `~/.claude/skills/pcv/planning/step3-4-patterns-clarify.md`
- `skill/planning/step5-makeplan.md` → `~/.claude/skills/pcv/planning/step5-makeplan.md`
- `skill/planning/step6-8-critic-gates.md` → `~/.claude/skills/pcv/planning/step6-8-critic-gates.md`
- `skill/planning/step9-11-construction-gates.md` → `~/.claude/skills/pcv/planning/step9-11-construction-gates.md`

### Construction fragments
- `skill/construction/steps.md` → `~/.claude/skills/pcv/construction/steps.md`

### Verification fragments
- `skill/verification/steps1-4-verify-mapping-export.md` → `~/.claude/skills/pcv/verification/steps1-4-verify-mapping-export.md`
- `skill/verification/step4.5-acceptance.md` → `~/.claude/skills/pcv/verification/step4.5-acceptance.md`
- `skill/verification/step5-8-report-closeout.md` → `~/.claude/skills/pcv/verification/step5-8-report-closeout.md`

### Transition fragments
- `skill/transition/step1-3-close-review.md` → `~/.claude/skills/pcv/transition/step1-3-close-review.md`
- `skill/transition/step4-user-directs.md` → `~/.claude/skills/pcv/transition/step4-user-directs.md`
- `skill/transition/step5-6-scaffold-begin.md` → `~/.claude/skills/pcv/transition/step5-6-scaffold-begin.md`

### Handlers (NEW in v3.14)
- `skill/handlers/lib.sh` → `~/.claude/skills/pcv/handlers/lib.sh`
- `skill/handlers/hook-registration.sh` → `~/.claude/skills/pcv/handlers/hook-registration.sh`
- `skill/handlers/plan-tier.sh` → `~/.claude/skills/pcv/handlers/plan-tier.sh`
- `skill/handlers/git-setup.sh` → `~/.claude/skills/pcv/handlers/git-setup.sh`
- `skill/handlers/global-settings.sh` → `~/.claude/skills/pcv/handlers/global-settings.sh`
- `skill/handlers/charge-write.sh` → `~/.claude/skills/pcv/handlers/charge-write.sh`
- `skill/handlers/test-response-clarification.sh` → `~/.claude/skills/pcv/handlers/test-response-clarification.sh`
- `skill/handlers/test-response-escalation.sh` → `~/.claude/skills/pcv/handlers/test-response-escalation.sh`
- `skill/handlers/scope-creep-trigger.sh` → `~/.claude/skills/pcv/handlers/scope-creep-trigger.sh`

### Hooks
- `skill/hooks/pcv-lib.sh` → `~/.claude/skills/pcv/hooks/pcv-lib.sh`
- `skill/hooks/session-start-resume.sh` → `~/.claude/skills/pcv/hooks/session-start-resume.sh`
- `skill/hooks/scaffold-settings.sh` → `~/.claude/skills/pcv/hooks/scaffold-settings.sh`
- `skill/hooks/scaffold-phase.sh` → `~/.claude/skills/pcv/hooks/scaffold-phase.sh`
- `skill/hooks/stop-closeout.sh` → `~/.claude/skills/pcv/hooks/stop-closeout.sh`
- `skill/hooks/pre-compact-snapshot.sh` → `~/.claude/skills/pcv/hooks/pre-compact-snapshot.sh`
- `skill/hooks/post-tool-use-format.sh` → `~/.claude/skills/pcv/hooks/post-tool-use-format.sh`
- `skill/hooks/subagent-stop-track.sh` → `~/.claude/skills/pcv/hooks/subagent-stop-track.sh`
- `skill/hooks/tech-permissions-scan.sh` → `~/.claude/skills/pcv/hooks/tech-permissions-scan.sh`
- `skill/hooks/validate-pcv-format.sh` → `~/.claude/skills/pcv/hooks/validate-pcv-format.sh`

### Agents
- `agents/pcv-critic.md` → `~/.claude/agents/pcv-critic.md`
- `agents/pcv-research.md` → `~/.claude/agents/pcv-research.md`
- `agents/pcv-builder.md` → `~/.claude/agents/pcv-builder.md`
- `agents/pcv-verifier.md` → `~/.claude/agents/pcv-verifier.md`

---

## v3.14 Changelog Summary

**Protocol Reliability.** Replaces prose conditional logic for mechanical gates (git setup, hook registration, plan tier, artifact scaffolding, metadata writes) with deterministic shell-script handlers backed by a hook-written session-state sentinel. Judgment gates (clarifications, critic escalation, deviation resolution, scope-creep response) remain prose with conflict-audit-driven reconciliation. Every gate site emits `gate-context.json` for future agent-as-user interop. Default permission expansion eliminates repetitive approval prompts for mundane temp-dir and PCV-internal operations. See full notes at `https://mgkay.github.io/pcv/` and the v3.14 build record in the source project.

## Troubleshooting

If install fails mid-way:
- Confirm network access to `mgkay.github.io` (the manifest fetches files from there).
- Confirm Claude Code has WebFetch permission for `mgkay.github.io` (add to your `~/.claude/settings.json` allow list if prompted).
- Partial installs: re-run the bootstrap — writes are idempotent (overwrite).
- If a specific file 404s, the URL listed in the manifest may be stale. File an issue at `https://github.com/mgkay/mgkay.github.io/issues`.

## Source Repository

Full files at: https://github.com/mgkay/mgkay.github.io/tree/main/pcv

For development setups, clone the repo directly rather than bootstrapping.
