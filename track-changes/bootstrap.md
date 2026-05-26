# track-changes Bootstrap — Source-preserving AI edit protocol (two-skill suite)

**Version:** 3.0.2
**Date:** 2026-05-26

## What This File Does

Installer manifest for the **track-changes** suite for Claude Code. v3 ships **two skills** that share a single `tc_core` package:

- **`track-changes`** (always-on, opt-in per file/folder) — every Claude edit to a tracked `.md` / `.qmd` / `.tex` file is wrapped in a `<mark>…</mark><sup>N</sup>` highlight you can review and accept/reject. This is the mark-gate.
- **`verified-import`** (opt-in, invoked via `/import`) — insert a vetted source (a Word chapter, a prior notebook, a manuscript section) into a tracked document. Claude converts the source to the document's format; the hook verifies the result is **content-faithful** to the named source and, on pass, lets the import land **clean** (no marks). A discrepancy blocks fail-closed.

When Claude Code follows the instructions below, it downloads both skills — hooks, library modules, the shared `tc_core` package, slash commands, and reference docs — and merges **six** hook registrations across the two skills into your `~/.claude/settings.json`.

**The v3 thrusts:**
- **Leaner always-on footprint.** The `track-changes` skill is narrowed: source-provenance import wrappers moved out into the separate opt-in `verified-import` skill; cross-file mark renumbering and edit-inside-non-rendering-construct sibling handling were removed (such edits now route to `/draft`).
- **SessionStart digest.** The session-start hook now injects a compact `reference/digest.md` (~2.9 KB) instead of the full `SKILL.md` — ~93.5% smaller, well under the 40 KB inline cap. The full `SKILL.md` is lazy-loaded on demand.
- **Convert-on-import.** `verified-import` verifies the AI-converted block against the source by content words (markup-agnostic), then exempts the verified import from the mark requirement via a one-shot sentinel the `track-changes` gate consumes.

**Backward compatibility / clean break:** the v3 `<mark>…</mark><sup>N</sup>` mark grammar is **unchanged**. Existing tracked documents need **no conversion** — upgrading from v2 only re-installs the skill files and re-registers the hooks. See the v3 changelog at the bottom.

## Prerequisites

- **Claude Code** installed. track-changes is a Claude Code skill suite; it runs inside Claude Code, not separately.
- **`curl`** — default in Git Bash on Windows, default on macOS and Linux.
- **Python 3** — required by the validator, audit, and import hooks.
- **`jq`** — only needed by the legacy `bash install.sh` path; the curl bootstrap uses a Python helper for the settings.json merge.

## How to Install

1. Start a Claude Code session (anywhere — the suite installs to your user profile, not a specific project).
2. Say: `Read https://mgkay.github.io/track-changes/bootstrap.md and follow the installation instructions inside it.`
3. Claude Code will download both skills, merge the hook registrations, and confirm success.

---

## Instructions for Claude Code

You are reading the track-changes v3.0.2 bootstrap manifest. Follow these steps precisely.

### Step 1: Check for existing installation

Read `~/.claude/skills/track-changes/VERSION`. If the file exists, parse the first line as a version number. Compare it to `3.0.2` using semantic-version ordering (compare major, then minor, then patch as integers; treat a missing component as 0, so a two-part `2.0` is `2.0.0`).

- **Equal to 3.0.2** → "track-changes v3.0.2 is already installed. No update needed." **STOP.**
- **Higher than 3.0.2** → "track-changes v[installed] is newer than this bootstrap (3.0.2). Aborting — will not downgrade." **STOP.**
- **Lower than 3.0.2** (e.g. v3.0.0, v3.0.1, or any v1.x or v2.x) → "Updating track-changes from v[installed] to v3.0.2." Proceed to Step 2. The download in Step 2 overwrites every skill file in place, so the upgrade is a clean replacement (a 3.0.0/3.0.1 upgrade also re-merges settings.json, collapsing the pre-3.0.2 two-group PreToolUse registration into the single combined group); existing `<mark>…</mark><sup>N</sup>` content in your documents is fully backward-compatible and is left untouched (the v3 mark grammar is unchanged — no document migration is needed).
- **Does not exist** → "Installing track-changes v3.0.2." Proceed to Step 2.

### Step 2: Download all files (curl-based)

**Why curl, not WebFetch:** Claude Code's WebFetch tool post-processes content through an LLM and does *not* return raw bytes — it will summarize, refuse, or rewrite file content, corrupting installs. Use `curl` via the Bash tool to fetch raw bytes.

**Source URLs use `raw.githubusercontent.com`**, not `mgkay.github.io`. This bypasses GitHub Pages' Jekyll processing (which otherwise strips frontmatter and 404s on files like `SKILL.md`). All source files live on the `main` branch of the `mgkay/mgkay.github.io` repository.

For each entry in the MANIFEST below:

1. Ensure the destination's parent directory exists. Parent directories under `~/.claude/skills/track-changes/`, `~/.claude/skills/verified-import/`, and `~/.claude/commands/` will be created implicitly by most downloaders, but on some systems you may need `mkdir -p ~/.claude/skills/track-changes/hooks ~/.claude/skills/track-changes/lib/tc_core ~/.claude/skills/verified-import/hooks` (etc.) first.
2. Run in Bash: `curl -fsSL "<source-url>" -o "<destination-path>"`
   - `-f` fails on HTTP errors (404, 500, etc.)
   - `-s` silent (no progress bar)
   - `-S` show errors on failure even with `-s`
   - `-L` follow redirects
3. If any curl invocation exits non-zero, stop and report the failing URL + destination to the user. Do not continue with a partial install.

**After all files downloaded**, verify no file ended up empty (silent download failure) across BOTH skill directories and commands:
```bash
find ~/.claude/skills/track-changes ~/.claude/skills/verified-import ~/.claude/commands -type f -empty -print
```
If this prints nothing, all installed files are non-empty. If it prints any paths, those files failed to download correctly — report to the user and re-run the bootstrap (curl overwrites, so retrying is safe).

### Step 3: Merge hook registrations into settings.json

The suite registers **six** hooks across the two skills in `~/.claude/settings.json`: five for `track-changes` (PreToolUse, PostToolUse, SessionStart, Stop, UserPromptSubmit) and one for `verified-import` (PreToolUse). The downloaded `lib/tc_settings_merge.py` performs an idempotent merge: per event it strips the suite-owned groups (track-changes OR verified-import) and re-adds the patch's groups, preserving third-party hooks.

Run in Bash:

```bash
python ~/.claude/skills/track-changes/lib/tc_settings_merge.py \
       ~/.claude/skills/track-changes/settings-patch.json \
       ~/.claude/settings.json
```

(If `python` isn't on PATH, try `python3` or `py -3`.)

This command:
- Backs up the existing `~/.claude/settings.json` to a `.bak.<timestamp>` sibling file.
- Registers the six suite hook entries across both skills.
- Stacks **`verified-import`'s PreToolUse hook BEFORE `track-changes`'s within a single `Write|Edit|MultiEdit` matcher group** — verified-import writes the one-shot exemption sentinel that track-changes consumes, so it must run first. Hooks stacked in one matcher group run **sequentially** in array order; hooks in *separate* matcher groups run in parallel, so the single-group stacking (not mere array position) is what guarantees the ordering. Encoded in the patch and preserved by the merge.
- Is safe to re-run (idempotent).

> **Upgrading from v2?** The merge **replaces** the single v2 `track-changes` PreToolUse registration with the v3 two-skill hook set: it strips the old track-changes group and lays down the single combined verified-import + track-changes PreToolUse group in its place — no duplicate, no dangling stale entry. (A v2 persistent daemon, if any is still running, self-shuts on its idle timeout and is never contacted once the new in-process hooks load. The v3 hooks are in-process only; the daemon was dropped.)

If the command exits non-zero, report the error to the user and stop.

### Step 4: Verify installation

1. Read `~/.claude/skills/track-changes/VERSION` → first line must be `3.0.2`.
2. Read `~/.claude/skills/track-changes/SKILL.md` → must begin with `---` (YAML frontmatter).
3. Read `~/.claude/skills/track-changes/hooks/pre_tool_use.py` → must begin with `"""` (Python docstring).
4. Read `~/.claude/skills/track-changes/lib/tc_core/grammar.py` → must exist (shared mark-grammar package).
5. Read `~/.claude/skills/track-changes/reference/digest.md` → must exist (SessionStart digest).
6. Read `~/.claude/skills/verified-import/SKILL.md` → must begin with `---` (YAML frontmatter).
7. Read `~/.claude/skills/verified-import/hooks/pre_tool_use.py` → must exist (import verification gate).
8. Read `~/.claude/skills/verified-import/lib/vi_verify.py` → must exist (content-faithfulness engine).
9. Read `~/.claude/commands/draft.md`, `~/.claude/commands/tc.md`, `~/.claude/commands/import.md` → all three must exist.
10. Read `~/.claude/settings.json`, parse as JSON, confirm `.hooks.PreToolUse` contains a **single matcher group** whose `hooks` array holds BOTH a command containing `verified-import/hooks/pre_tool_use.py` AND a command containing `track-changes/hooks/pre_tool_use.py`, with the **verified-import entry stacked before** the track-changes entry (same group → sequential execution; not two separate groups).

Any verification failure → report to user and do not claim success.

### Step 5: Inform the user

On success, tell the user:

> **track-changes v3.0.2 installed successfully — two skills + shared `tc_core`.**
>
> **`track-changes`** (`~/.claude/skills/track-changes/`): always-on mark-tracking. SKILL.md, VERSION, settings-patch.json, hooks/ (5 sh + 2 py), lib/ (4 py + 6 sh + 1 sty + the shared `tc_core` package), reference/ (highlight-syntax.md, latex.md, quarto-notes.md, **digest.md**, tc-clean.css, tc-clean.js).
>
> **`verified-import`** (`~/.claude/skills/verified-import/`): opt-in `/import`. SKILL.md, hooks/pre_tool_use.py, lib/ (vi_verify.py, vi-cli.sh). It imports the shared `tc_core` from `track-changes/lib` — no duplicate copy.
>
> **Slash commands** (`~/.claude/commands/`): draft.md, tc.md, import.md.
>
> **Settings** (`~/.claude/settings.json`): 6 hook registrations merged across both skills (verified-import's PreToolUse stacked before track-changes' in one matcher group).
>
> **Always-on mark-tracking:** once a file is tracked, every AI edit to a `.md` / `.qmd` / `.tex` file is wrapped in `<mark>…</mark><sup>N</sup>` highlights you can review and accept/reject. Batch-resolve with `/tc accept|reject|list [<file>] <ranges>` (e.g. `1-25,!7`).
>
> **Verified import:** `/import <source>[#L<a>-L<b>] [<target>]` inserts a vetted source into a tracked document. Claude converts it to the document's format; the hook verifies content faithfulness and lets a verified import land clean (no marks). A discrepancy blocks with the differing content words named.
>
> **`/draft`:** temporarily suspend the highlight requirement for one user turn (e.g. for brand-new, from-scratch content).
>
> **Activation:** `track-changes` is OFF by default. To track a file, add `track-changes: true` to its YAML frontmatter (or `% track-changes: true` for `.tex`), drop a `.tc-tracked` marker in the file's folder (`/tc mark <dir>`), or invoke `/tc enable <file>`.
>
> **Open a new Claude Code session** to activate the suite hooks.

---

## MANIFEST — files to install

Each entry lists source-URL → destination-path. Base URL: `https://raw.githubusercontent.com/mgkay/mgkay.github.io/main/track-changes/`.

### track-changes — skill root  (→ `~/.claude/skills/track-changes/`)
- `skill/VERSION` → `~/.claude/skills/track-changes/VERSION`
- `skill/SKILL.md` → `~/.claude/skills/track-changes/SKILL.md`
- `skill/settings-patch.json` → `~/.claude/skills/track-changes/settings-patch.json`

### track-changes — hooks
- `skill/hooks/session-start.sh` → `~/.claude/skills/track-changes/hooks/session-start.sh`
- `skill/hooks/pre_tool_use.py` → `~/.claude/skills/track-changes/hooks/pre_tool_use.py`
- `skill/hooks/post_tool_use.py` → `~/.claude/skills/track-changes/hooks/post_tool_use.py`
- `skill/hooks/stop.sh` → `~/.claude/skills/track-changes/hooks/stop.sh`
- `skill/hooks/user-prompt-submit.sh` → `~/.claude/skills/track-changes/hooks/user-prompt-submit.sh`
- `skill/hooks/pre-commit.sh` → `~/.claude/skills/track-changes/hooks/pre-commit.sh`

### track-changes — library modules (Python + Bash)
- `skill/lib/tc-common.sh` → `~/.claude/skills/track-changes/lib/tc-common.sh`
- `skill/lib/tc-mark.sh` → `~/.claude/skills/track-changes/lib/tc-mark.sh`
- `skill/lib/tc_analyzer.py` → `~/.claude/skills/track-changes/lib/tc_analyzer.py`
- `skill/lib/tc_resolve.py` → `~/.claude/skills/track-changes/lib/tc_resolve.py`
- `skill/lib/tc_settings_merge.py` → `~/.claude/skills/track-changes/lib/tc_settings_merge.py`
- `skill/lib/draft-on.sh` → `~/.claude/skills/track-changes/lib/draft-on.sh`
- `skill/lib/tc-cli.sh` → `~/.claude/skills/track-changes/lib/tc-cli.sh`
- `skill/lib/tc-history.sh` → `~/.claude/skills/track-changes/lib/tc-history.sh`
- `skill/lib/migrate-v1-to-v2.sh` → `~/.claude/skills/track-changes/lib/migrate-v1-to-v2.sh`
- `skill/lib/tc.sty` → `~/.claude/skills/track-changes/lib/tc.sty`

### track-changes — shared `tc_core` package
- `skill/lib/tc_core/__init__.py` → `~/.claude/skills/track-changes/lib/tc_core/__init__.py`
- `skill/lib/tc_core/grammar.py` → `~/.claude/skills/track-changes/lib/tc_core/grammar.py`
- `skill/lib/tc_core/activation.py` → `~/.claude/skills/track-changes/lib/tc_core/activation.py`
- `skill/lib/tc_core/audit.py` → `~/.claude/skills/track-changes/lib/tc_core/audit.py`
- `skill/lib/tc_core/exempt.py` → `~/.claude/skills/track-changes/lib/tc_core/exempt.py`

### track-changes — reference docs
- `skill/reference/highlight-syntax.md` → `~/.claude/skills/track-changes/reference/highlight-syntax.md`
- `skill/reference/latex.md` → `~/.claude/skills/track-changes/reference/latex.md`
- `skill/reference/quarto-notes.md` → `~/.claude/skills/track-changes/reference/quarto-notes.md`
- `skill/reference/digest.md` → `~/.claude/skills/track-changes/reference/digest.md`
- `skill/reference/tc-clean.css` → `~/.claude/skills/track-changes/reference/tc-clean.css`
- `skill/reference/tc-clean.js` → `~/.claude/skills/track-changes/reference/tc-clean.js`

### verified-import — skill  (→ `~/.claude/skills/verified-import/`)
*No `tc_core` copy — verified-import imports the shared package from `track-changes/lib`.*
- `verified-import/SKILL.md` → `~/.claude/skills/verified-import/SKILL.md`
- `verified-import/hooks/pre_tool_use.py` → `~/.claude/skills/verified-import/hooks/pre_tool_use.py`
- `verified-import/lib/vi_verify.py` → `~/.claude/skills/verified-import/lib/vi_verify.py`
- `verified-import/lib/vi-cli.sh` → `~/.claude/skills/verified-import/lib/vi-cli.sh`

### Slash commands  (→ `~/.claude/commands/`)
- `commands/draft.md` → `~/.claude/commands/draft.md`
- `commands/tc.md` → `~/.claude/commands/tc.md`
- `commands/import.md` → `~/.claude/commands/import.md`

---

## v3.0.2 Changelog Summary

v3 decomposes the single v2 skill into a **two-skill suite** and trims the always-on footprint, driven by real ISE 754 authoring friction (SessionStart latency + scope creep).

**v3.0.2 patch.** The `verified-import` and `track-changes` PreToolUse hooks are now stacked in a **single** `Write|Edit|MultiEdit` matcher group (verified-import first) instead of two separate matcher groups. Hooks in *separate* matcher groups run in parallel, which raced the exemption-sentinel handoff (verified-import writes the one-shot sentinel that track-changes consumes) — so a verified `/import` was blocked on its first attempt and only landed clean on an identical retry. Stacking them in one group makes the two run **sequentially**, so a verified import lands clean on the first attempt. No hook code changed; the sha-bound sentinel contract is unchanged.

**v3.0.1 patch.** `/tc mark` on a non-directory first argument is now a hard error (exit 1, no marker written) instead of silently writing a broken, full-path list-mode marker in CWD — consistent with `/tc migrate`'s directory check. Regression test TC-M-11 added.

- **Two-skill split (headline).** The narrowed always-on **`track-changes`** mark-gate and the new opt-in **`verified-import`** skill (`/import`) share one `tc_core` package (`track-changes/lib/tc_core` — not duplicated; verified-import imports it). The v2 source-provenance import wrappers (`<!-- track-changes: from=… -->`) are retired in favor of `/import`'s convert-then-verify flow.
- **SessionStart digest.** The session-start hook injects a compact `reference/digest.md` (~2.9 KB — activation rules, mark-grammar table, the `/tc` command list, and "see `SKILL.md §N`" lazy-load pointers) instead of `cat`-ing the full `SKILL.md`. **~93.5% smaller** than the v2 ~41.7 KB injection, comfortably under the 40 KB inline cap; the full `SKILL.md` is lazy-loaded on demand.
- **Narrowed always-on surface.** §0 import wrappers → moved to `verified-import`; §5 cross-file mark renumbering → removed; §6 edit-inside-non-rendering-construct sibling → removed (such edits now route to `/draft`). The brand-new-block sibling (mechanism-1) is kept for `.md`/`.qmd`; a brand-new LaTeX `\section`/environment routes to `/draft`.
- **Daemon dropped.** After measurement (in-process `pre_tool_use` p50 ≈ 41.5 ms, ~6× under the keep threshold), the v2 persistent localhost-TCP daemon was removed; the ~13.5 ms/edit it saved did not justify the 294-line subsystem. In-process is now the sole hook path. A plain install removes any stale deployed `tc_daemon.py`.
- **Convert-on-import faithfulness.** `/import` stages a target-keyed pending-import, then `verified-import/hooks/pre_tool_use.py` verifies the AI-converted block is content-faithful to the named source (markup-agnostic content-word multiset compare — tolerates reflow and `\section{X}`↔`## X` translation, rejects an injected sentence or a dropped clause). On **pass** it writes a one-shot exemption sentinel (sha-bound to the proposed bytes, byte-identical to what the track-changes gate consumes) plus an `imported:` audit entry, so a verified import lands clean. On **fail** it blocks fail-closed, naming the differing content words.
- **Mechanical fixes #4–#7.** `/tc` resolution + `status` default to the most-recently-modified tracked working file (echoed); bare `/tc` prints the compact menu; resolving a whole-line mark to empty drops the orphaned blank line; `datetime.utcnow()` deprecation removed.
- **Clean break — no document migration (Q2).** The v3 `<mark>…</mark><sup>N</sup>` mark grammar, per-file YAML activation, `.tc-tracked` markers, token-minimal wrapping, and the native-Python in-process hook architecture are **unchanged**. Existing tracked documents need **no conversion**; an upgrade from v2 only re-installs files and replaces the single v2 hook registration with the v3 two-skill set (verified-import and track-changes stacked in one PreToolUse matcher group, so they run sequentially). `/tc migrate <dir>` is retained for converting any legacy **v1** marks.

The 339-test v3 suite (categories A–V) passes green. See `https://mgkay.github.io/track-changes/` for project details.

## Troubleshooting

**If `curl` is missing:** install Git for Windows (bundles Git Bash with curl) or use your OS's equivalent. PowerShell's `Invoke-WebRequest` is the closest analog but Claude Code's default shell is Bash, so stick with curl.

**If a specific file 404s on the raw URL:** the URL may reference a file not yet committed or pushed. Check `https://github.com/mgkay/mgkay.github.io/tree/main/track-changes` in a browser to see what's actually in the repository.

**If `python` isn't found:** try `python3`, `py -3`, or `py`. Update the Step 3 command accordingly. The suite requires Python 3.

**If the settings.json merge fails with a JSON error:** your existing `~/.claude/settings.json` is malformed. Fix or move it aside (`mv ~/.claude/settings.json ~/.claude/settings.json.broken`) and re-run the merge command — it will create a fresh file from the patch.

**If Claude Code prompts for permission:** approve `Bash(curl *)` and the relevant `Read`/`Write` patterns on `~/.claude/**`. To avoid prompts on future installs, add to `~/.claude/settings.json`:
```json
"allow": [
  "Bash(curl *)",
  "Read(~/.claude/skills/track-changes/**)", "Write(~/.claude/skills/track-changes/**)",
  "Read(~/.claude/skills/verified-import/**)", "Write(~/.claude/skills/verified-import/**)",
  "Read(~/.claude/commands/**)", "Write(~/.claude/commands/**)"
]
```

**Partial installs:** re-run the bootstrap. curl overwrites destinations, and the Step 1 version check will re-detect and re-install. The settings merge is idempotent.

## Source Repository

Raw files: <https://raw.githubusercontent.com/mgkay/mgkay.github.io/main/track-changes/>
Repository: <https://github.com/mgkay/mgkay.github.io/tree/main/track-changes>

For development or bulk install, `git clone https://github.com/mgkay/mgkay.github.io` then copy `track-changes/skill/*` to `~/.claude/skills/track-changes/`, `track-changes/verified-import/*` to `~/.claude/skills/verified-import/`, and `track-changes/commands/*` to `~/.claude/commands/`. The suite's source-of-truth repository (with tests and PCV history) is separately maintained.
