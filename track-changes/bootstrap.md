# track-changes Bootstrap — Source-preserving AI edit protocol

**Version:** 1.13
**Date:** 2026-05-24

## What This File Does

Installer manifest for the **track-changes** skill for Claude Code. When Claude Code follows the instructions below, it downloads the full skill — hooks, library modules, slash commands, and reference docs — and merges the five hook registrations into your `~/.claude/settings.json`. After install, every Claude edit to a tracked `.md` / `.qmd` / `.tex` file is wrapped in a `<mark>` highlight you can review and accept/reject.

## Prerequisites

- **Claude Code** installed. track-changes is a Claude Code skill; it runs inside Claude Code, not separately.
- **`curl`** — default in Git Bash on Windows, default on macOS and Linux.
- **Python 3** — required by the validator and audit hooks.
- **`jq`** — only needed by the legacy `bash install.sh` path; the curl bootstrap uses a Python helper for the settings.json merge.

## How to Install

1. Start a Claude Code session (anywhere — track-changes installs to your user profile, not a specific project).
2. Say: `Read https://mgkay.github.io/track-changes/bootstrap.md and follow the installation instructions inside it.`
3. Claude Code will download the skill files, merge the hook registrations, and confirm success.

---

## Instructions for Claude Code

You are reading the track-changes v1.13 bootstrap manifest. Follow these steps precisely.

### Step 1: Check for existing installation

Read `~/.claude/skills/track-changes/VERSION`. If the file exists, parse the first line as a version number. Compare to 1.13.

- **Equal to 1.13** → "track-changes v1.13 is already installed. No update needed." **STOP.**
- **Higher than 1.13** → "track-changes v[installed] is newer than this bootstrap (1.13). Aborting — will not downgrade." **STOP.**
- **Lower than 1.13** → "Updating track-changes from v[installed] to v1.13." Proceed to Step 2.
- **Does not exist** → "Installing track-changes v1.13." Proceed to Step 2.

### Step 2: Download all files (curl-based)

**Why curl, not WebFetch:** Claude Code's WebFetch tool post-processes content through an LLM and does *not* return raw bytes — it will summarize, refuse, or rewrite file content, corrupting installs. Use `curl` via the Bash tool to fetch raw bytes.

**Source URLs use `raw.githubusercontent.com`**, not `mgkay.github.io`. This bypasses GitHub Pages' Jekyll processing (which otherwise strips frontmatter and 404s on files like `SKILL.md`). All source files live on the `main` branch of the `mgkay/mgkay.github.io` repository.

For each entry in the MANIFEST below:

1. Ensure the destination's parent directory exists. Parent directories under `~/.claude/skills/track-changes/` and `~/.claude/commands/` will be created implicitly by most downloaders, but on some systems you may need `mkdir -p ~/.claude/skills/track-changes/hooks` (etc.) first.
2. Run in Bash: `curl -fsSL "<source-url>" -o "<destination-path>"`
   - `-f` fails on HTTP errors (404, 500, etc.)
   - `-s` silent (no progress bar)
   - `-S` show errors on failure even with `-s`
   - `-L` follow redirects
3. If any curl invocation exits non-zero, stop and report the failing URL + destination to the user. Do not continue with a partial install.

**After all files downloaded**, verify no file ended up empty (silent download failure):
```bash
find ~/.claude/skills/track-changes ~/.claude/commands -type f -empty -print
```
If this prints nothing, all installed files are non-empty. If it prints any paths, those files failed to download correctly — report to the user and re-run the bootstrap (curl overwrites, so retrying is safe).

### Step 3: Merge hook registrations into settings.json

track-changes registers five hooks in `~/.claude/settings.json`. The downloaded `lib/tc_settings_merge.py` performs an idempotent merge: it adds the track-changes entries to each event array if no track-changes entry already exists for that event.

Run in Bash:

```bash
python ~/.claude/skills/track-changes/lib/tc_settings_merge.py \
       ~/.claude/skills/track-changes/settings-patch.json \
       ~/.claude/settings.json
```

(If `python` isn't on PATH, try `python3` or `py -3`.)

This command:
- Backs up the existing `~/.claude/settings.json` to a `.bak.<timestamp>` sibling file.
- Adds the five track-changes hook entries (PreToolUse, PostToolUse, SessionStart, Stop, UserPromptSubmit) if not already registered.
- Is safe to re-run (idempotent).

If the command exits non-zero, report the error to the user and stop.

### Step 4: Verify installation

1. Read `~/.claude/skills/track-changes/VERSION` → first line must be `1.13`.
2. Read `~/.claude/skills/track-changes/SKILL.md` → must begin with `---` (YAML frontmatter).
3. Read `~/.claude/skills/track-changes/hooks/pre_tool_use.py` → must begin with `"""` (Python docstring).
4. Read `~/.claude/skills/track-changes/lib/tc_analyzer.py` → must exist.
5. Read `~/.claude/skills/track-changes/lib/tc_audit.py` → must exist.
6. Read `~/.claude/commands/draft.md` → must exist.
7. Read `~/.claude/commands/tc.md` → must exist.
8. Read `~/.claude/settings.json`, parse as JSON, confirm `.hooks.PreToolUse` contains an entry whose command contains the substring `track-changes/hooks/pre_tool_use.py`.

Any verification failure → report to user and do not claim success.

### Step 5: Inform the user

On success, tell the user:

> **track-changes v1.13 installed successfully.**
>
> **Skill files** (`~/.claude/skills/track-changes/`): SKILL.md, VERSION, settings-patch.json, hooks/ (5 sh + 2 py), lib/ (5 py + 6 sh + 1 sty), reference/ (highlight-syntax.md, latex.md).
>
> **Slash commands** (`~/.claude/commands/`): draft.md, tc.md.
>
> **Settings** (`~/.claude/settings.json`): 5 hook registrations merged (PreToolUse, PostToolUse, SessionStart, Stop, UserPromptSubmit).
>
> **Activation:** the skill is OFF by default. To track a file, add `track-changes: true` to its YAML frontmatter, or drop a `.tc-tracked` marker in the file's folder, or invoke `/tc enable <file>`.
>
> **Open a new Claude Code session** to activate the hooks. Once activated, every AI edit to a tracked `.md` / `.qmd` / `.tex` file will be wrapped in `<mark>…</mark><sup>N</sup>` highlights you can review and accept/reject.

---

## MANIFEST — files to install

Each entry lists source-URL → destination-path. Base URL: `https://raw.githubusercontent.com/mgkay/mgkay.github.io/main/track-changes/`.

### Skill root
- `skill/VERSION` → `~/.claude/skills/track-changes/VERSION`
- `skill/SKILL.md` → `~/.claude/skills/track-changes/SKILL.md`
- `skill/settings-patch.json` → `~/.claude/skills/track-changes/settings-patch.json`

### Hooks
- `skill/hooks/session-start.sh` → `~/.claude/skills/track-changes/hooks/session-start.sh`
- `skill/hooks/pre-tool-use.sh` → `~/.claude/skills/track-changes/hooks/pre-tool-use.sh`
- `skill/hooks/pre_tool_use.py` → `~/.claude/skills/track-changes/hooks/pre_tool_use.py`
- `skill/hooks/post-tool-use.sh` → `~/.claude/skills/track-changes/hooks/post-tool-use.sh`
- `skill/hooks/post_tool_use.py` → `~/.claude/skills/track-changes/hooks/post_tool_use.py`
- `skill/hooks/stop.sh` → `~/.claude/skills/track-changes/hooks/stop.sh`
- `skill/hooks/user-prompt-submit.sh` → `~/.claude/skills/track-changes/hooks/user-prompt-submit.sh`

### Library modules (Python + Bash)
- `skill/lib/tc-common.sh` → `~/.claude/skills/track-changes/lib/tc-common.sh`
- `skill/lib/tc_activation.py` → `~/.claude/skills/track-changes/lib/tc_activation.py`
- `skill/lib/tc_analyzer.py` → `~/.claude/skills/track-changes/lib/tc_analyzer.py`
- `skill/lib/tc_audit.py` → `~/.claude/skills/track-changes/lib/tc_audit.py`
- `skill/lib/tc_daemon.py` → `~/.claude/skills/track-changes/lib/tc_daemon.py`
- `skill/lib/tc_settings_merge.py` → `~/.claude/skills/track-changes/lib/tc_settings_merge.py`
- `skill/lib/draft-on.sh` → `~/.claude/skills/track-changes/lib/draft-on.sh`
- `skill/lib/tc-cli.sh` → `~/.claude/skills/track-changes/lib/tc-cli.sh`
- `skill/lib/tc-history.sh` → `~/.claude/skills/track-changes/lib/tc-history.sh`
- `skill/lib/migrate-v1-to-v2.sh` → `~/.claude/skills/track-changes/lib/migrate-v1-to-v2.sh`
- `skill/lib/tc.sty` → `~/.claude/skills/track-changes/lib/tc.sty`

### Reference docs
- `skill/reference/highlight-syntax.md` → `~/.claude/skills/track-changes/reference/highlight-syntax.md`
- `skill/reference/latex.md` → `~/.claude/skills/track-changes/reference/latex.md`

### Slash commands
- `commands/draft.md` → `~/.claude/commands/draft.md`
- `commands/tc.md` → `~/.claude/commands/tc.md`

---

## v1.13 Changelog Summary

Native Python PreToolUse + PostToolUse hooks replace the prior bash + jq + Python-heredoc architecture; per-tracked-edit overhead is ~154ms (down from ~625ms). The validator uses a walk-based per-region coverage check that closes the previous lenient line-level rule. A resolution-mode pre-pass lets the AI accept/reject marks on the user's instruction without disabling tracking via `/draft`. Markdown strikethrough uses HTML `<s>` (not GFM `~~`), which renders correctly in markdown-it-based viewers (VS Code preview, Chrome markdown extensions) as well as GitHub and Quarto. 198/198 tests pass. See `https://mgkay.github.io/track-changes/` for project details.

## Troubleshooting

**If `curl` is missing:** install Git for Windows (bundles Git Bash with curl) or use your OS's equivalent. PowerShell's `Invoke-WebRequest` is the closest analog but Claude Code's default shell is Bash, so stick with curl.

**If a specific file 404s on the raw URL:** the URL may reference a file not yet committed or pushed. Check `https://github.com/mgkay/mgkay.github.io/tree/main/track-changes` in a browser to see what's actually in the repository.

**If `python` isn't found:** try `python3`, `py -3`, or `py`. Update the Step 3 command accordingly. Track-changes requires Python 3.

**If the settings.json merge fails with a JSON error:** your existing `~/.claude/settings.json` is malformed. Fix or move it aside (`mv ~/.claude/settings.json ~/.claude/settings.json.broken`) and re-run the merge command — it will create a fresh file from the patch.

**If Claude Code prompts for permission:** approve `Bash(curl *)` and the relevant `Read`/`Write` patterns on `~/.claude/**`. To avoid prompts on future installs, add to `~/.claude/settings.json`:
```json
"allow": [
  "Bash(curl *)",
  "Read(~/.claude/skills/**)", "Write(~/.claude/skills/**)",
  "Read(~/.claude/commands/**)", "Write(~/.claude/commands/**)"
]
```

**Partial installs:** re-run the bootstrap. curl overwrites destinations, and the Step 1 version check will re-detect and re-install. The settings merge is idempotent.

## Source Repository

Raw files: <https://raw.githubusercontent.com/mgkay/mgkay.github.io/main/track-changes/>
Repository: <https://github.com/mgkay/mgkay.github.io/tree/main/track-changes>

For development or bulk install, `git clone https://github.com/mgkay/mgkay.github.io` then copy `track-changes/skill/*` to `~/.claude/skills/track-changes/` and `track-changes/commands/*` to `~/.claude/commands/`. The skill's source-of-truth repository (with tests and PCV history) is separately maintained.
