# track-changes Bootstrap — Source-preserving AI edit protocol (three-skill suite)

**Version:** 8.0.0
**Date:** 2026-06-27

## What This File Does

Installer manifest for the **track-changes** suite for Claude Code. The suite ships **three skills** that share a single `tc_core` package:

- **`track-changes`** (always-on, opt-in per file/folder) — every Claude edit to a tracked `.md` / `.qmd` / `.tex` file is wrapped in a `<mark>…</mark><sup>N</sup>` highlight you can review and accept/reject. This is the mark-gate.
- **`verified-import`** (opt-in, invoked via `/tc import`) — insert a vetted source (a Word chapter, a prior notebook, a manuscript section) into a tracked document. Claude converts the source to the document's format and lands it **clean** (no marks): there is **no mechanical content gate** — the LLM imports faithfully and self-marks only genuinely significant changes (altered meaning) in track-changes marks; minor diffs land clean. A PreToolUse hook writes a one-shot, sha-bound exemption that the always-on `track-changes` skill honors, so the faithful block is not mark-wrapped.
- **`tc-polish`** (opt-in, invoked via `/tc polish [file]`) — clean up **and editorially improve voice-dictated** prose in an existing tracked document: recognition/grammar/dropped-word fixes **plus** meaning-preserving restructuring (split run-ons, reorder for flow, tighten wordiness). Every change surfaces as an ordinary track-changes `<mark>` you review with `/tc accept|reject`. Bright line: it **never** auto-corrects an unrecognized token (jargon / code / math / domain term) — such a token is left and flagged, never silently changed; a meaning-affecting fix is surfaced as a mark, not applied silently. tc-polish adds **no hook** — its fixes flow through the existing `track-changes` PreToolUse hook — and **no slash-command file** (the explicit `/tc polish` invocation is the opt-in). It reuses the shared `tc_core` for its tracked-check.

When Claude Code follows the instructions below, it downloads all three skills — hooks, library modules, the shared `tc_core` package, slash commands, and reference docs — and merges **six** hook registrations into your `~/.claude/settings.json` (five for `track-changes`, one for `verified-import`; `tc-polish` owns no hook).

**The suite design:**
- **Leaner always-on footprint.** The `track-changes` skill is narrowed: source-provenance import wrappers moved out into the separate opt-in `verified-import` skill; cross-file mark renumbering and edit-inside-non-rendering-construct sibling handling were removed (such edits now route to `/draft`).
- **SessionStart digest.** The session-start hook now injects a compact `reference/digest.md` (~2.9 KB) instead of the full `SKILL.md` — ~93.5% smaller, well under the 40 KB inline cap. The full `SKILL.md` is lazy-loaded on demand.
- **Convert-on-import (LLM-judgment).** `verified-import` trusts the LLM to import the AI-converted block faithfully — there is **no mechanical content gate**. On a live pending-import the hook writes a one-shot, sha-bound exemption that the `track-changes` gate consumes, so the converted block lands clean; the model self-marks only genuinely significant changes (altered meaning) for the author to review.
- **Editorial polish (v5; broadened in v5.1).** `tc-polish` (`/tc polish [file]`) cleans up **and editorially improves** voice-dictated prose — recognition/grammar/dropped-word fixes plus meaning-preserving restructuring (split run-ons, reorder for flow, tighten wordiness) — surfacing every change as an ordinary track-changes mark. It adds no hook and no settings change — changes flow through the existing `track-changes` PreToolUse hook — and never auto-corrects an unrecognized domain/code/math token (it leaves and flags it), nor drops a qualifier or alters meaning.

**Backward compatibility / clean break:** the `<mark>…</mark><sup>N</sup>` mark grammar is **unchanged**. Existing tracked documents need **no conversion** — upgrading only re-installs the skill files and re-registers the hooks. See the changelog at the bottom.

## Prerequisites

- **Claude Code** installed. track-changes is a Claude Code skill suite; it runs inside Claude Code, not separately.
- **`curl`** — default in Git Bash on Windows, default on macOS and Linux.
- **Python 3** — required by the validator, audit, and import hooks.
- **`jq`** — only needed by the legacy `bash install.sh` path; the curl bootstrap uses a Python helper for the settings.json merge.

## How to Install

1. Start a Claude Code session (anywhere — the suite installs to your user profile, not a specific project).
2. Say: `Read https://mgkay.github.io/track-changes/bootstrap.md and follow the installation instructions inside it.`
3. Claude Code will download all three skills, merge the hook registrations, and confirm success.

---

## Instructions for Claude Code

You are reading the track-changes v8.0.0 bootstrap manifest. Follow these steps precisely.

### Step 1: Check for existing installation

Read `~/.claude/skills/track-changes/VERSION`. If the file exists, parse the first line as a version number. Compare it to `8.0.0` using semantic-version ordering (compare major, then minor, then patch as integers; treat a missing component as 0, so a two-part `2.0` is `2.0.0`).

- **Equal to 8.0.0** → "track-changes v8.0.0 is already installed. No update needed." **STOP.**
- **Higher than 8.0.0** → "track-changes v[installed] is newer than this bootstrap (8.0.0). Aborting — will not downgrade." **STOP.**
- **Lower than 8.0.0** (e.g. v7.0.x, v6.0.x, v5.0.x, v4.x, v3.0.x, or any v1.x or v2.x) → "Updating track-changes from v[installed] to v8.0.0." Proceed to Step 2. The download in Step 2 overwrites every skill file in place (and, from a pre-v5 install, adds the `tc-polish` skill), so the upgrade is a clean replacement (the upgrade also re-merges settings.json, laying down the single combined PreToolUse matcher group); existing `<mark>…</mark><sup>N</sup>` content in your documents is fully backward-compatible and is left untouched (the mark grammar is unchanged — no document migration is needed). **Upgrading from v4.0.x?** The per-file activation key was renamed `track-changes:` → `tc-track:` in v4.1 (the old key is a reserved Quarto YAML field that breaks `.qmd`/`.md` renders); swap any old keys to `tc-track:`. **v6 is behavior-changing:** `/draft` is now **user-only** — the AI can no longer suspend its own tracking (the suspension sentinel is written solely by the `UserPromptSubmit` hook on *your* `/draft` prompt). Everything the AI writes into a tracked deliverable is tracked; large new blocks use the new whole-region insertion (`::: {.tc-region …}` / `\tcregion`). No document migration — the mark grammar is backward-compatible. **Upgrading from v6?** The bare `/polish` and `/import` slash aliases are retired — use `/tc polish` and `/tc import` instead. The `polish` skill directory is renamed to `tc-polish` (the upgrade removes the old `~/.claude/skills/polish/` directory and `~/.claude/commands/import.md` if present). No document migration. **Upgrading from v7?** v8 adds the bundled `decap` editor pre-clean tool under `~/.claude/skills/track-changes/tools/`; no behavior change to tracking, the mark grammar, or the hook suite.
- **Does not exist** → "Installing track-changes v8.0.0." Proceed to Step 2.

### Step 2: Download all files (curl-based)

**Why curl, not WebFetch:** Claude Code's WebFetch tool post-processes content through an LLM and does *not* return raw bytes — it will summarize, refuse, or rewrite file content, corrupting installs. Use `curl` via the Bash tool to fetch raw bytes.

**Source URLs use `raw.githubusercontent.com`**, not `mgkay.github.io`. This bypasses GitHub Pages' Jekyll processing (which otherwise strips frontmatter and 404s on files like `SKILL.md`). All source files live on the `main` branch of the `mgkay/mgkay.github.io` repository.

For each entry in the MANIFEST below:

1. Ensure the destination's parent directory exists. Parent directories under `~/.claude/skills/track-changes/`, `~/.claude/skills/verified-import/`, `~/.claude/skills/tc-polish/`, and `~/.claude/commands/` will be created implicitly by most downloaders, but on some systems you may need `mkdir -p ~/.claude/skills/track-changes/hooks ~/.claude/skills/track-changes/lib/tc_core ~/.claude/skills/track-changes/tools ~/.claude/skills/verified-import/hooks ~/.claude/skills/tc-polish/lib` (etc.) first.
2. Run in Bash: `curl -fsSL "<source-url>" -o "<destination-path>"`
   - `-f` fails on HTTP errors (404, 500, etc.)
   - `-s` silent (no progress bar)
   - `-S` show errors on failure even with `-s`
   - `-L` follow redirects
3. If any curl invocation exits non-zero, stop and report the failing URL + destination to the user. Do not continue with a partial install.

**After all files downloaded**, verify no file ended up empty (silent download failure) across BOTH skill directories and commands:
```bash
find ~/.claude/skills/track-changes ~/.claude/skills/verified-import ~/.claude/skills/tc-polish ~/.claude/skills/track-changes/tools ~/.claude/commands -type f -empty -print
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

1. Read `~/.claude/skills/track-changes/VERSION` → first line must be `8.0.0`.
2. Read `~/.claude/skills/track-changes/SKILL.md` → must begin with `---` (YAML frontmatter).
3. Read `~/.claude/skills/track-changes/hooks/pre_tool_use.py` → must begin with `"""` (Python docstring).
4. Read `~/.claude/skills/track-changes/lib/tc_core/grammar.py` → must exist (shared mark-grammar package).
5. Read `~/.claude/skills/track-changes/reference/digest.md` → must exist (SessionStart digest).
6. Read `~/.claude/skills/verified-import/SKILL.md` → must begin with `---` (YAML frontmatter).
7. Read `~/.claude/skills/verified-import/hooks/pre_tool_use.py` → must exist (import exemption hook).
8. Read `~/.claude/skills/verified-import/lib/vi_verify.py` → must exist (import resolution/staging engine).
9. Read `~/.claude/skills/tc-polish/SKILL.md` → must begin with `---` (YAML frontmatter).
10. Read `~/.claude/skills/tc-polish/lib/polish_engine.py` → must exist (dictation diff/scope + tracked-check engine; it imports `tc_core` from `track-changes/lib`).
11. Read `~/.claude/commands/draft.md`, `~/.claude/commands/tc.md` → both must exist. (`tc-polish` has no command file — `/tc polish` invokes the skill via the `/tc` dispatcher. `/import` is retired — use `/tc import`.)
12. Read `~/.claude/settings.json`, parse as JSON, confirm `.hooks.PreToolUse` contains a **single matcher group** whose `hooks` array holds BOTH a command containing `verified-import/hooks/pre_tool_use.py` AND a command containing `track-changes/hooks/pre_tool_use.py`, with the **verified-import entry stacked before** the track-changes entry (same group → sequential execution; not two separate groups). (`polish` adds no hook, so the count stays six.)
13. Read `~/.claude/skills/track-changes/tools/decap.py` → must begin with `#!/usr/bin/env python3` (bundled dictation pre-clean filter).
14. Read `~/.claude/skills/track-changes/tools/decap_protect.txt` → must exist and be non-empty (default protect-list).

Any verification failure → report to user and do not claim success.

### Step 5: Inform the user

On success, tell the user:

> **track-changes v8.0.0 installed successfully — three skills + shared `tc_core` + bundled tools.**
>
> **`track-changes`** (`~/.claude/skills/track-changes/`): always-on mark-tracking. SKILL.md, VERSION, settings-patch.json, hooks/ (5 sh + 2 py), lib/ (4 py + 6 sh + 1 sty + the shared `tc_core` package), reference/ (highlight-syntax.md, latex.md, quarto-notes.md, **digest.md**, tc-clean.css, tc-clean.js), tools/ (decap.py, decap_protect.txt).
>
> **`verified-import`** (`~/.claude/skills/verified-import/`): opt-in `/tc import`. SKILL.md, hooks/pre_tool_use.py, lib/ (vi_verify.py, vi-cli.sh). It imports the shared `tc_core` from `track-changes/lib` — no duplicate copy.
>
> **`tc-polish`** (`~/.claude/skills/tc-polish/`): opt-in `/tc polish`. SKILL.md, lib/ (polish-cli.sh, polish_engine.py). No hook, no command file, no settings entry — it imports the shared `tc_core` from `track-changes/lib` and its fixes flow through the `track-changes` PreToolUse hook.
>
> **Slash commands** (`~/.claude/commands/`): draft.md, tc.md.
>
> **Settings** (`~/.claude/settings.json`): 6 hook registrations merged (verified-import's PreToolUse stacked before track-changes' in one matcher group; tc-polish owns no hook).
>
> **Always-on mark-tracking:** once a file is tracked, every AI edit to a `.md` / `.qmd` / `.tex` file is wrapped in `<mark>…</mark><sup>N</sup>` highlights you can review and accept/reject. Batch-resolve with `/tc accept|reject|list [<file>] <ranges>` (e.g. `1-25,!7`).
>
> **Verified import:** `/tc import <source>[#L<a>-L<b>] [<target>]` inserts a vetted source into a tracked document. Claude converts it faithfully to the document's format and the import lands clean (no marks) — there is no mechanical content gate. Claude self-marks only genuinely significant changes (altered meaning) for you to review.
>
> **Dictation polish:** `/tc polish [file]` cleans up voice-dictated prose (speech-recognition errors, grammar, dropped words) in a tracked document, surfacing every fix as a reviewable `<mark>`. It never auto-corrects a domain/code/math token — it leaves and flags it. On an untracked file it offers a one-time direct polish (no marks) or to enable tracking first.
>
> **Dictation pre-clean:** `decap` — see SKILL.md. Run on fresh, unmarked dictation BEFORE it is tracked; composes with `/tc polish`. Shipped under `tools/` but outside the mark protocol (author-invoked editor filter; never runs through Claude's edit tools).
>
> **`/draft`:** temporarily suspend the highlight requirement for one user turn (e.g. for brand-new, from-scratch content).
>
> **Activation:** `track-changes` is OFF by default. To track a file, add `tc-track: true` to its YAML frontmatter (or `% tc-track: true` for `.tex`), drop a `.tc-tracked` marker in the file's folder (`/tc mark <dir>`), or invoke `/tc enable <file>`. (The per-file key is `tc-track`, **not** `track-changes` — `track-changes` is a reserved Quarto YAML field that breaks `.qmd`/`.md` renders.)
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

### track-changes — tools  (→ `~/.claude/skills/track-changes/tools/`)
- `skill/tools/decap.py` → `~/.claude/skills/track-changes/tools/decap.py`
- `skill/tools/decap_protect.txt` → `~/.claude/skills/track-changes/tools/decap_protect.txt`

### verified-import — skill  (→ `~/.claude/skills/verified-import/`)
*No `tc_core` copy — verified-import imports the shared package from `track-changes/lib`.*
- `verified-import/SKILL.md` → `~/.claude/skills/verified-import/SKILL.md`
- `verified-import/hooks/pre_tool_use.py` → `~/.claude/skills/verified-import/hooks/pre_tool_use.py`
- `verified-import/lib/vi_verify.py` → `~/.claude/skills/verified-import/lib/vi_verify.py`
- `verified-import/lib/vi-cli.sh` → `~/.claude/skills/verified-import/lib/vi-cli.sh`

### tc-polish — skill  (→ `~/.claude/skills/tc-polish/`)
*No `tc_core` copy — tc-polish imports the shared package from `track-changes/lib`. No hook, no command file.*
- `tc-polish/SKILL.md` → `~/.claude/skills/tc-polish/SKILL.md`
- `tc-polish/lib/polish-cli.sh` → `~/.claude/skills/tc-polish/lib/polish-cli.sh`
- `tc-polish/lib/polish_engine.py` → `~/.claude/skills/tc-polish/lib/polish_engine.py`

### Slash commands  (→ `~/.claude/commands/`)
- `commands/draft.md` → `~/.claude/commands/draft.md`
- `commands/tc.md` → `~/.claude/commands/tc.md`
*(No `import.md` — `/tc import` dispatches via the `/tc` command. No `tc-polish.md` — `/tc polish` dispatches via the `/tc` command.)*

---

## v8.0.0 Changelog Summary

**v8.0.0 (bundle `decap`, the dictation pre-clean filter — additive).** Bundles `decap`, a deterministic author-invoked capitalization-cleanup filter for voice dictation, shipped WITH the suite under `~/.claude/skills/track-changes/tools/` but explicitly **outside** the mark protocol. `decap` runs as an editor selection filter (stdin→stdout), never through Claude's Write/Edit tools, so it is inherently untracked. Apply it to fresh, unmarked dictation BEFORE content is tracked; it composes with `/tc polish` (fast mechanical pass you run yourself vs reviewable AI editorial pass). The `<mark>`-boundary caveat: `decap` is regex over raw text — never run it across a selection containing `<mark>`/`\tc{}` marks (it will corrupt mark syntax). **No mark-grammar change, no new hook, no document migration; hook count stays 6; three-skill suite is unchanged.** Only the installer (`install.sh`) and bootstrap (`bootstrap.md`) gain the two new `tools/` entries.

## v7.0.0 Changelog Summary

**v7.0.0 (command-surface namespace consolidation — behavior-preserving).** Collision-proofs the family's slash surface before broader adoption. `/polish` → `/tc polish` and `/import` → `/tc import`: both bare aliases are retired in v7; the verbs are now dispatched by the existing `/tc` command (new `import` and `polish` cases in `tc-cli.sh` shell to the existing `vi-cli.sh` and `polish-cli.sh` front-ends, preserving behavior by construction). The `polish` skill is renamed to `tc-polish` (directory and `name:` in SKILL.md); verified-import keeps its name (not colliding). The bare `/import` slash command file is removed; `/tc-polish` continues to work as the namespaced skill-name fallback alongside `/tc polish`. `/draft` is **unchanged** and confirmed shadow-proof: `UserPromptSubmit` fires on the raw prompt before command routing, so no skill can intercept it. No change to tracking/marking/import/polish semantics, the 6-hook suite count, or the mark grammar. Existing tracked documents require no migration; the mark grammar is backward-compatible. **Migration from v6:** use `/tc import` in place of `/import`; use `/tc polish` in place of `/polish`; the installer removes `~/.claude/commands/import.md` and renames `~/.claude/skills/polish/` to `~/.claude/skills/tc-polish/`.

## Changelog Summary

**v6.0.0 (tracking-enforcement hardening — behavior-changing).** Closes the recurring hole where AI-authored content reached a tracked deliverable **untracked**. **(A)** Everything the AI writes into a tracked deliverable is now tracked regardless of approval — the "approval is the audit trail" rule is removed (authorization and verification are separate gates that both always hold). **(B) `/draft` is now mechanically USER-ONLY:** the per-turn suspension sentinel is written solely by the `UserPromptSubmit` hook when the human's own prompt requests it (carrying an authorized marker the PreToolUse gate requires); `lib/draft-on.sh` no longer writes it and a forged/bare sentinel is ignored, so the AI cannot suspend its own tracking. **(D) Whole-region insertion:** a multi-block new region marks as ONE tracked unit — a Quarto `::: {.tc-region tc-n="N" tc-prov="…"}` … `:::` div, or a LaTeX `tcregion` environment drawing a left **change-bar** (robust across display math and verbatim); `/tc accept|reject N` resolves it atomically. **(E) Provenance-typed marks:** `tc-prov="authored"` (default) vs `"imported"` (a verbatim `/import` slice), with distinct render colors — plus the corpus-example convention (import the lifted scenario; track the new Julia/prose as authored). The mark grammar is **backward-compatible**: every v1–v5 mark and document parses unchanged (absent provenance = authored); no migration. **No new hooks** (the suite stays at 6) and no settings change beyond the existing merge. The only breaking change is behavioral — the AI can no longer self-suspend tracking; only the user can.

## v5.1.0 Changelog Summary

**v5.1.0 (polish broadened to a full editorial pass).** `polish` now does the work a copy-editor does on newly dictated prose — splitting run-on sentences, reordering clauses for flow, tightening wordiness, smoothing awkward phrasing — in addition to the recognition/grammar/dropped-word fixes, while staying **meaning-preserving** and **diff-scoped** (it only ever touches prose newly dictated since the git baseline, never the vetted/committed corpus); every change is still an ordinary track-changes `<mark>`. The bright line is split into one hard rule — **never change meaning**: never drop or weaken a qualifier, hedge, scope phrase, or modal (a qualifier-preservation rule for restructures), and never alter a fact or number — plus a fix to error-handling: an **obvious error** (a broken/nonsensical sentence, e.g. a stray question left in declarative prose) is now **marked** with a best-guess fix rather than demoted to a prose-only suggestion. A restructure wraps the **whole sentence** as one replacement mark (not a scatter of character diffs), and the run reports four buckets — corrections / restructures / left+flagged / suggested; sentence relocations across paragraphs are suggested, not applied. Engine fix: smart-quote contractions/possessives (`it's`, `they're`, `item's`) are no longer mis-flagged as protected tokens — typographic apostrophes/quotes/dashes are folded to ASCII before the non-ASCII protected-token test, so genuine symbols/Greek (`αvhq`) and the prime `′` stay protected while ordinary contractions remain polishable. **No hook or settings change**; the mark grammar, the hooks, and the two prior skills are unchanged.

## v5.0.0 Changelog Summary

v5 adds a **third cooperating skill, `polish`**, to the suite (track-changes + verified-import + polish), and reconciles the source-of-record up to the published v4.1 (the `tc-track` key rename, below) which had shipped to the site but not the source repo.

**v5.0.0 (polish joins the suite).** `polish` (`/polish [file]`) cleans up **voice-dictated** prose — speech-recognition errors, grammar, dropped words — in an existing tracked `.md`/`.qmd` document, surfacing every fix as an ordinary track-changes `<mark>` (reviewable via `/tc accept|reject`). It is opt-in and default-OFF: the explicit `/polish` invocation **is** the opt-in (no marker file). Bright line — it **never** auto-corrects an unrecognized token (jargon / code / math / domain term): such a token is left and flagged, never silently changed; a meaning-affecting fix is surfaced as a mark, not applied silently. `polish` adds **no new hook** and **no settings change** — its prose fixes flow through the **existing** `track-changes` PreToolUse hook unchanged, so the suite hook count stays **six**; on a tracked file fixes become marks, on an untracked file it offers a one-time direct polish (no marks) or to enable tracking first. `polish_engine.py` reuses `track-changes`' own `tc_core.activation` for the authoritative tracked-check and imports `tc_core` from `track-changes/lib` (no duplicate copy — the same shared-core pattern as `verified-import`). There is **no view-time "dictated lens"** (an earlier build's render-time second color was retired after a source-vs-executed token-stream drift; `git diff` is the authoritative "what did I change" view). Existing tracked documents need **no conversion**; the mark grammar, the hooks, and the two prior skills are unchanged. The bootstrap version check is corrected to `5.0.0` (the published 4.x bootstrap still referenced `4.0.0` even after the 4.1 files shipped).

**v4.1.0 (per-file key rename — rolled into the source-of-record here).** The per-file activation key was renamed `track-changes:` → `tc-track:` (YAML) / `% tc-track:` (`.tex` magic comment). The old `track-changes:` key is a **reserved Quarto YAML field** (Quarto accepts only `accept`/`reject`/`all` and errors on `true`/`false`), so it broke every `.qmd`/`.md` render; `tc-track` is an unknown key Quarto passes through untouched. **BREAKING** for files using the old key — swap them to `tc-track`. The skill name, the `/tc` command, the mark grammar, the hooks, and `.tc-tracked` folder markers are unchanged. (4.1 was published to the Pages site and installed locally on 2026-05-31 but was never committed back to the source repo; v5 reconciles `activation.py`, `tc-cli.sh`, `tc-common.sh`, `tc-mark.sh`, `SKILL.md`, `digest.md`, and `latex.md` to the published 4.1 content before adding polish.)

## v4.0.0 Changelog Summary

v4 changes the **import-verification paradigm** of the two-skill suite (introduced in v3, which decomposed the single v2 skill and trimmed the always-on footprint, driven by real ISE 754 authoring friction — SessionStart latency + scope creep).

**v4.0.0 (import-verification paradigm change).** The `verified-import` **mechanical content gate is removed.** v3 ran a mechanical token-multiset comparison of the AI-converted block against the named source and refused any discrepancy — too strict in practice, repeatedly tripping faithful math/code imports (e.g. an EOQ `\sqrt{\frac{2KD}{h}}` rendering). The whole point of using a large language model is that it can judge which differences matter, so v4 trusts the model to import faithfully: on a live pending-import, `verified-import/hooks/pre_tool_use.py` writes the one-shot, sha-bound exemption sentinel **unconditionally** (no comparison) plus an `imported:` audit entry, so the converted block lands clean via the exemption the `track-changes` gate honors. The model **self-marks only genuinely significant changes** — a change that *alters meaning* (an added or removed sentence or clause, or a changed quantity, term, or formula) — in track-changes marks; minor diffs (reflow, reformatting, equivalent notation such as `\section{X}` → `## X` or an `equation` environment → `$$…$$`) land clean with no mark. The dead gate code is deleted; the pending record is slimmed to `{target, source_path, range, expires}`; the pending TTL default is 120 → 300 s (user-overridable); and the `/import` CLI now strips a leading `@` file-reference prefix from the source and target args. No change to the mark grammar, the single-group PreToolUse hook order (verified-import before track-changes), or the two-skill install.

**v3.0.2 patch.** The `verified-import` and `track-changes` PreToolUse hooks are now stacked in a **single** `Write|Edit|MultiEdit` matcher group (verified-import first) instead of two separate matcher groups. Hooks in *separate* matcher groups run in parallel, which raced the exemption-sentinel handoff (verified-import writes the one-shot sentinel that track-changes consumes) — so a verified `/import` was blocked on its first attempt and only landed clean on an identical retry. Stacking them in one group makes the two run **sequentially**, so a verified import lands clean on the first attempt. No hook code changed; the sha-bound sentinel contract is unchanged.

**v3.0.1 patch.** `/tc mark` on a non-directory first argument is now a hard error (exit 1, no marker written) instead of silently writing a broken, full-path list-mode marker in CWD — consistent with `/tc migrate`'s directory check. Regression test TC-M-11 added.

- **Two-skill split (headline).** The narrowed always-on **`track-changes`** mark-gate and the new opt-in **`verified-import`** skill (`/import`) share one `tc_core` package (`track-changes/lib/tc_core` — not duplicated; verified-import imports it). The v2 source-provenance import wrappers (`<!-- track-changes: from=… -->`) are retired in favor of `/import`'s convert-and-land-clean flow.
- **SessionStart digest.** The session-start hook injects a compact `reference/digest.md` (~2.9 KB — activation rules, mark-grammar table, the `/tc` command list, and "see `SKILL.md §N`" lazy-load pointers) instead of `cat`-ing the full `SKILL.md`. **~93.5% smaller** than the v2 ~41.7 KB injection, comfortably under the 40 KB inline cap; the full `SKILL.md` is lazy-loaded on demand.
- **Narrowed always-on surface.** §0 import wrappers → moved to `verified-import`; §5 cross-file mark renumbering → removed; §6 edit-inside-non-rendering-construct sibling → removed (such edits now route to `/draft`). The brand-new-block sibling (mechanism-1) is kept for `.md`/`.qmd`; a brand-new LaTeX `\section`/environment routes to `/draft`.
- **Daemon dropped.** After measurement (in-process `pre_tool_use` p50 ≈ 41.5 ms, ~6× under the keep threshold), the v2 persistent localhost-TCP daemon was removed; the ~13.5 ms/edit it saved did not justify the 294-line subsystem. In-process is now the sole hook path. A plain install removes any stale deployed `tc_daemon.py`.
- **Convert-on-import (LLM-judgment).** `/import` stages a target-keyed pending-import; on a live pending-import `verified-import/hooks/pre_tool_use.py` writes a one-shot exemption sentinel (sha-bound to the proposed bytes, byte-identical to what the track-changes gate consumes) plus an `imported:` audit entry, so the converted block lands clean. There is **no mechanical content gate** (the v3 token-multiset comparison and its EOQ false-reject are gone): the LLM imports faithfully — preserving every sentence and clause, only reformatting to the target format — and self-marks only a genuinely significant change (one that alters meaning) in a track-changes mark for the author. Author responsibility: keep the import write to only the converted block, since the exemption is keyed to the whole written file.
- **Mechanical fixes #4–#7.** `/tc` resolution + `status` default to the most-recently-modified tracked working file (echoed); bare `/tc` prints the compact menu; resolving a whole-line mark to empty drops the orphaned blank line; `datetime.utcnow()` deprecation removed.
- **Clean break — no document migration.** The `<mark>…</mark><sup>N</sup>` mark grammar, per-file YAML activation, `.tc-tracked` markers, token-minimal wrapping, and the native-Python in-process hook architecture are **unchanged** across v4. Existing tracked documents need **no conversion**; an upgrade only re-installs files and lays down the two-skill hook set (verified-import and track-changes stacked in one PreToolUse matcher group, so they run sequentially). `/tc migrate <dir>` is retained for converting any legacy **v1** marks.

The v4 test suite (categories A–V) passes green. See `https://mgkay.github.io/track-changes/` for project details.

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
  "Read(~/.claude/skills/tc-polish/**)", "Write(~/.claude/skills/tc-polish/**)",
  "Read(~/.claude/commands/**)", "Write(~/.claude/commands/**)"
]
```

**Partial installs:** re-run the bootstrap. curl overwrites destinations, and the Step 1 version check will re-detect and re-install. The settings merge is idempotent.

## Source Repository

Raw files: <https://raw.githubusercontent.com/mgkay/mgkay.github.io/main/track-changes/>
Repository: <https://github.com/mgkay/mgkay.github.io/tree/main/track-changes>

For development or bulk install, `git clone https://github.com/mgkay/mgkay.github.io` then copy `track-changes/skill/*` to `~/.claude/skills/track-changes/`, `track-changes/verified-import/*` to `~/.claude/skills/verified-import/`, `track-changes/tc-polish/*` to `~/.claude/skills/tc-polish/`, and `track-changes/commands/*` to `~/.claude/commands/`. The suite's source-of-truth repository (with tests and PCV history) is separately maintained.
