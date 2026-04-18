# PCV Bootstrap — Plan-Construct-Verify Installer

**Version:** 3.14
**Date:** 2026-04-18

## What This File Does

Installer manifest for the PCV (Plan-Construct-Verify) skill for Claude Code. When Claude Code follows the instructions below, it downloads the full PCV skill — protocol files, handlers, hooks, and agent definitions — enabling the `/pcv` command.

## Prerequisite

**Claude Code** must be installed. PCV is a Claude Code skill; it runs inside Claude Code, not separately. `curl` must be available (default in Git Bash on Windows; default on macOS and Linux).

## How to Install

1. Start a Claude Code session (anywhere — PCV installs to your user profile, not a specific project).
2. Say: `Read https://mgkay.github.io/pcv/bootstrap.md and follow the installation instructions inside it.`
3. Claude Code will download the skill files and confirm success.

---

## Instructions for Claude Code

You are reading the PCV v3.14 bootstrap manifest. Follow these steps precisely.

### Step 1: Check for existing installation

Read `~/.claude/skills/pcv/VERSION`. If the file exists, parse the first line as a version number. Compare to 3.14.

- **Equal to 3.14** → "PCV v3.14 is already installed. No update needed." **STOP.**
- **Higher than 3.14** → "PCV v[installed] is newer than this bootstrap (3.14). Aborting — will not downgrade." **STOP.**
- **Lower than 3.14** → "Updating PCV from v[installed] to v3.14." Proceed to Step 2.
- **Does not exist** → "Installing PCV v3.14." Proceed to Step 2.

### Step 2: Download and install all files (curl-based)

**Why curl, not WebFetch:** Claude Code's WebFetch tool post-processes content through an LLM and does *not* return raw bytes — it will summarize, refuse, or rewrite file content, corrupting installs. Use `curl` via the Bash tool to fetch raw bytes.

**Source URLs use `raw.githubusercontent.com`**, not `mgkay.github.io`. This bypasses GitHub Pages' Jekyll processing (which otherwise strips frontmatter and 404s on files like `SKILL.md`). All source files live on the `main` branch of the `mgkay/mgkay.github.io` repository.

For each entry in the MANIFEST below:

1. Ensure the destination's parent directory exists. Parent directories under `~/.claude/skills/pcv/` and `~/.claude/agents/` will be created implicitly by most downloaders, but on some systems you may need `mkdir -p ~/.claude/skills/pcv/handlers` (etc.) first.
2. Run in Bash: `curl -fsSL "<source-url>" -o "<destination-path>"`
   - `-f` fails on HTTP errors (404, 500, etc.)
   - `-s` silent (no progress bar)
   - `-S` show errors on failure even with `-s`
   - `-L` follow redirects
3. If any curl invocation exits non-zero, stop and report the failing URL + destination to the user. Do not continue with a partial install.

**After all files downloaded**, verify no file ended up empty (silent download failure):
```bash
find ~/.claude/skills/pcv ~/.claude/agents -type f -empty -print
```

If this prints nothing, all installed files are non-empty. If it prints any paths, those files failed to download correctly — report to the user and re-run the bootstrap (curl overwrites, so retrying is safe).

Do not inline a long `for f in path1 path2 ...` loop — some Claude Code versions have parser limits on very long shell commands (~4000+ characters).

### Step 3: Verify installation

1. Read `~/.claude/skills/pcv/VERSION` → first line must be `3.14`.
2. Read `~/.claude/skills/pcv/SKILL.md` → must begin with `---` (YAML frontmatter).
3. Read `~/.claude/skills/pcv/handlers/lib.sh` → must exist (new in v3.14).
4. Search `~/.claude/skills/pcv/hooks/session-start-resume.sh` for the string `v3.14 session-state sentinel write` → must be present (confirms v3.14 sentinel writer is installed).
5. Read `~/.claude/agents/pcv-critic.md` → must begin with `---`.

Any verification failure → report to user and do not claim success.

### Step 4: Inform the user

On success, tell the user:

> **PCV v3.14 installed successfully.**
>
> **Protocol files** (`~/.claude/skills/pcv/`): SKILL.md, pcv-common.md, planning-protocol.md, construction-protocol.md, verification-protocol.md, phase-transition-protocol.md, scaffold-templates.md, VERSION, plus step fragments under `planning/`, `construction/`, `verification/`, `transition/`.
>
> **Handlers** (`~/.claude/skills/pcv/handlers/`, NEW in v3.14): lib.sh + 8 mechanical gate handlers (hook-registration, plan-tier, git-setup, global-settings, charge-write, test-response-clarification, test-response-escalation, scope-creep-trigger).
>
> **Hooks** (`~/.claude/skills/pcv/hooks/`): pcv-lib.sh, session-start-resume.sh, scaffold-settings.sh, scaffold-phase.sh, stop-closeout.sh, pre-compact-snapshot.sh, post-tool-use-format.sh, subagent-stop-track.sh, tech-permissions-scan.sh, validate-pcv-format.sh.
>
> **Agents** (`~/.claude/agents/`): pcv-critic.md, pcv-research.md, pcv-builder.md, pcv-verifier.md.
>
> To use PCV, navigate to a project directory and type `/pcv`.

---

## MANIFEST — files to install

Each entry lists source-URL → destination-path. Base URL: `https://raw.githubusercontent.com/mgkay/mgkay.github.io/main/pcv/`.

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

**Protocol Reliability.** Replaces prose conditional logic for mechanical gates (git setup, hook registration, plan tier, artifact scaffolding, metadata writes) with deterministic shell-script handlers backed by a hook-written session-state sentinel. Judgment gates (clarifications, critic escalation, deviation resolution, scope-creep response) remain prose with conflict-audit-driven reconciliation. Every gate site emits `gate-context.json` for future agent-as-user interop. Default permission expansion eliminates repetitive approval prompts for mundane temp-dir and PCV-internal operations. See `https://mgkay.github.io/pcv/` for full version history.

## Troubleshooting

**If `curl` is missing:** install Git for Windows (bundles Git Bash with curl) or use your OS's equivalent. On PowerShell, `Invoke-WebRequest -Uri <url> -OutFile <dest>` is the closest analog but Claude Code's default shell is Bash, so stick with curl.

**If a specific file 404s on the raw URL:** the URL may reference a file not yet committed or pushed. Check `https://github.com/mgkay/mgkay.github.io/tree/main/pcv` in a browser to see what's actually in the repository.

**If Claude Code prompts for network permission:** this is normal on first install. Approve `Bash(curl *)` and the specific destination paths for Write. To avoid prompts on future installs, add to `~/.claude/settings.json`:
```json
"allow": [
  "Bash(curl *)",
  "Read(~/.claude/skills/**)", "Write(~/.claude/skills/**)",
  "Read(~/.claude/agents/**)", "Write(~/.claude/agents/**)"
]
```

**Partial installs:** re-run the bootstrap. curl overwrites destinations, and the Step 1 version check will re-detect and re-install.

## Source Repository

Raw files: https://raw.githubusercontent.com/mgkay/mgkay.github.io/main/pcv/
Repository: https://github.com/mgkay/mgkay.github.io/tree/main/pcv

For development or bulk install, `git clone https://github.com/mgkay/mgkay.github.io` then copy `pcv/skill/*` to `~/.claude/skills/pcv/` and `pcv/agents/*` to `~/.claude/agents/`.
