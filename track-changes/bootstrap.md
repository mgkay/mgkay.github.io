# track-changes Bootstrap — Source-preserving AI edit protocol

**Version:** 2.0.0
**Date:** 2026-05-24

## What This File Does

Installer manifest for the **track-changes** skill for Claude Code. When Claude Code follows the instructions below, it downloads the full skill — hooks, library modules, slash commands, and reference docs — and merges the five hook registrations into your `~/.claude/settings.json`. After install, every Claude edit to a tracked `.md` / `.qmd` / `.tex` file is wrapped in a `<mark>` highlight you can review and accept/reject.

**New in v2:** *source-provenance import wrappers* let Claude build a document mostly from vetted sources (Word chapters, prior notebooks, manuscripts) while marking **only** the AI-authored glue — wrap an imported block in `<!-- track-changes: from=PATH#L<a>-L<b> -->` … `<!-- /track-changes -->` and the hook validates it against the named source, leaving verbatim imports unmarked and blocking on undisclosed paraphrase. See the v2 changelog at the bottom.

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

You are reading the track-changes v2.0.0 bootstrap manifest. Follow these steps precisely.

### Step 1: Check for existing installation

Read `~/.claude/skills/track-changes/VERSION`. If the file exists, parse the first line as a version number. Compare it to `2.0.0` using semantic-version ordering (compare major, then minor, then patch as integers; treat a missing component as 0, so a two-part `1.13` is `1.13.0`).

- **Equal to 2.0.0** → "track-changes v2.0.0 is already installed. No update needed." **STOP.**
- **Higher than 2.0.0** → "track-changes v[installed] is newer than this bootstrap (2.0.0). Aborting — will not downgrade." **STOP.**
- **Lower than 2.0.0** (e.g. any v1.x) → "Updating track-changes from v[installed] to v2.0.0." Proceed to Step 2. The download in Step 2 overwrites every skill file in place, so the upgrade is a clean replacement; existing `<mark>…</mark><sup>N</sup>` content in your documents is fully backward-compatible and is left untouched.
- **Does not exist** → "Installing track-changes v2.0.0." Proceed to Step 2.

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

> **Upgrading from v1?** The hook *registrations* are unchanged between v1 and v2, so the merge is a no-op on an existing install — that is expected. The new v2 behavior comes from the freshly downloaded analyzer and library files, which Step 2 has already overwritten. If a v1 `tc_daemon` is still running it will hold the old analyzer in memory until its idle timeout; opening a new Claude Code session (Step 5) guarantees the v2 code is loaded.

### Step 4: Verify installation

1. Read `~/.claude/skills/track-changes/VERSION` → first line must be `2.0.0`.
2. Read `~/.claude/skills/track-changes/SKILL.md` → must begin with `---` (YAML frontmatter).
3. Read `~/.claude/skills/track-changes/hooks/pre_tool_use.py` → must begin with `"""` (Python docstring).
4. Read `~/.claude/skills/track-changes/lib/tc_analyzer.py` → must exist.
5. Read `~/.claude/skills/track-changes/lib/tc_audit.py` → must exist.
6. Read `~/.claude/skills/track-changes/lib/tc_provenance.py` → must exist (v2 source-provenance engine).
7. Read `~/.claude/skills/track-changes/lib/tc_resolve.py` → must exist (v2 batch resolution engine).
8. Read `~/.claude/commands/draft.md` → must exist.
9. Read `~/.claude/commands/tc.md` → must exist.
10. Read `~/.claude/settings.json`, parse as JSON, confirm `.hooks.PreToolUse` contains an entry whose command contains the substring `track-changes/hooks/pre_tool_use.py`.

Any verification failure → report to user and do not claim success.

### Step 5: Inform the user

On success, tell the user:

> **track-changes v2.0.0 installed successfully.**
>
> **Skill files** (`~/.claude/skills/track-changes/`): SKILL.md, VERSION, settings-patch.json, hooks/ (6 sh + 2 py), lib/ (7 py + 5 sh + 1 sty), reference/ (highlight-syntax.md, latex.md, quarto-notes.md, tc-clean.css, tc-clean.js).
>
> **Slash commands** (`~/.claude/commands/`): draft.md, tc.md.
>
> **Settings** (`~/.claude/settings.json`): 5 hook registrations merged (PreToolUse, PostToolUse, SessionStart, Stop, UserPromptSubmit).
>
> **New in v2:** import vetted source with `<!-- track-changes: from=PATH#L<a>-L<b> -->` … `<!-- /track-changes -->` so only AI-authored glue gets marked; batch-resolve marks with `/tc accept|reject|list <file> <ranges>` (e.g. `1-25,!7`); new headings/fenced blocks/`:::` divs land via a single sibling mark; `/draft` now has a reliable Windows fallback; append `?clean=1` to a shared doc URL to hide marks at render. An opt-in git pre-commit advisory is available — wire it with `bash install.sh --enable-pre-commit` (never auto-installed).
>
> **Migrating v1 marks:** run `/tc migrate <dir>` to convert any existing v1 marks in `.md` / `.qmd` / `.tex` files to the v2 form in place (idempotent).
>
> **Activation:** the skill is OFF by default. To track a file, add `track-changes: true` to its YAML frontmatter, or drop a `.tc-tracked` marker in the file's folder (`/tc mark <dir>`), or invoke `/tc enable <file>`.
>
> **Open a new Claude Code session** to activate the hooks (and to retire any v1 daemon). Once activated, every AI edit to a tracked `.md` / `.qmd` / `.tex` file will be wrapped in `<mark>…</mark><sup>N</sup>` highlights you can review and accept/reject.

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
- `skill/hooks/pre-commit.sh` → `~/.claude/skills/track-changes/hooks/pre-commit.sh`

### Library modules (Python + Bash)
- `skill/lib/tc-common.sh` → `~/.claude/skills/track-changes/lib/tc-common.sh`
- `skill/lib/tc_activation.py` → `~/.claude/skills/track-changes/lib/tc_activation.py`
- `skill/lib/tc_analyzer.py` → `~/.claude/skills/track-changes/lib/tc_analyzer.py`
- `skill/lib/tc_audit.py` → `~/.claude/skills/track-changes/lib/tc_audit.py`
- `skill/lib/tc_daemon.py` → `~/.claude/skills/track-changes/lib/tc_daemon.py`
- `skill/lib/tc_provenance.py` → `~/.claude/skills/track-changes/lib/tc_provenance.py`
- `skill/lib/tc_resolve.py` → `~/.claude/skills/track-changes/lib/tc_resolve.py`
- `skill/lib/tc_settings_merge.py` → `~/.claude/skills/track-changes/lib/tc_settings_merge.py`
- `skill/lib/draft-on.sh` → `~/.claude/skills/track-changes/lib/draft-on.sh`
- `skill/lib/tc-cli.sh` → `~/.claude/skills/track-changes/lib/tc-cli.sh`
- `skill/lib/tc-history.sh` → `~/.claude/skills/track-changes/lib/tc-history.sh`
- `skill/lib/migrate-v1-to-v2.sh` → `~/.claude/skills/track-changes/lib/migrate-v1-to-v2.sh`
- `skill/lib/tc.sty` → `~/.claude/skills/track-changes/lib/tc.sty`

### Reference docs
- `skill/reference/highlight-syntax.md` → `~/.claude/skills/track-changes/reference/highlight-syntax.md`
- `skill/reference/latex.md` → `~/.claude/skills/track-changes/reference/latex.md`
- `skill/reference/quarto-notes.md` → `~/.claude/skills/track-changes/reference/quarto-notes.md`
- `skill/reference/tc-clean.css` → `~/.claude/skills/track-changes/reference/tc-clean.css`
- `skill/reference/tc-clean.js` → `~/.claude/skills/track-changes/reference/tc-clean.js`

### Slash commands
- `commands/draft.md` → `~/.claude/commands/draft.md`
- `commands/tc.md` → `~/.claude/commands/tc.md`

---

## v2.0.0 Changelog Summary

v2 closes the largest v1 workflow gap — *source provenance* — and ships the full friction backlog from real ISE 754 lecture authoring.

- **§0 Source-provenance import wrappers (headline).** Wrap imported source in `<!-- track-changes: from=PATH#L<a>-L<b> [mode=…] -->` … `<!-- /track-changes -->`. A new `lib/tc_provenance.py` slices the named plain-text source and matches the wrapped block in `strict` (byte-exact), `normalized` (default — collapses whitespace, normalizes line endings and smart quotes), or `fuzzy` (≥0.85, explicit opt-in) mode. A verbatim import **verifies and is exempt** from the `<mark>` requirement (reads as bare prose); an undisclosed paraphrase **blocks** with a discrepancy message offering fix / mark / drop. Unreadable sources fail **closed** (marks required). A new `imported:` audit-log block records source, lines, verification, and normalization mode. Converting binary sources (`.docx`/`.pptx`/`.ipynb`/`.pdf`) to a committed plain-text companion is Claude's responsibility at import time.
- **§7 Cross-file lineage.** A renumbered cross-file paste carries a `<!-- from-file=basename:N -->` comment and a recorded audit mapping, preserving the source mark number.
- **§3 Block-sibling mark form.** Brand-new headings, fenced code blocks, and `:::` divs land via a single sibling mark on the line above — no `/draft`, no parse-breaking inline wrapping. Modified existing headings still follow the inline rule.
- **§5 Batch resolution.** `/tc list|accept|reject|accept-all|reject-all <file>` with range syntax (`1-25,!7,!11`). Resolutions edit the file directly and record `decision: explicit` so they survive later inference.
- **§1 Windows `/draft` fix.** The per-turn sentinel is written by the skill's own bash with a `default.draft` fallback when `$CLAUDE_SESSION_ID` is unset, so activation no longer depends on a fragile cross-shell snippet.
- **§4 Render-time hiding.** `reference/tc-clean.css` + `tc-clean.js` hide marks/superscripts when a shared doc URL carries `?clean=1`, without touching source.
- **§8 Pre-commit advisory (opt-in).** `bash install.sh --enable-pre-commit` wires a fail-open git pre-commit hook that warns on unresolved marks in staged tracked files. Never auto-wired; bypass with `git commit --no-verify`.
- **§2 / §6 / §9 Docs.** SKILL.md clarifies user-authorized vs autonomous command use and adds a common-pitfalls section, an author-workflow recipe, and a `/draft` composition note; `reference/quarto-notes.md` documents three Quarto interaction gotchas.

**Backward compatibility:** the `<mark>…</mark><sup>N</sup>` grammar, per-file YAML activation, `.tc-tracked` markers, token-minimal wrapping, resolution detection, and the native-Python hook architecture are unchanged. The 198-test v1 regression suite passes **byte-identically** (the analyzer skips the new stage-0 entirely when no `from=` sources are present); 298/298 tests pass overall. Use `/tc migrate <dir>` to convert any pre-existing v1 marks to the v2 form. See `https://mgkay.github.io/track-changes/` for project details.

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
