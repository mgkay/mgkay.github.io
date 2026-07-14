# track-changes Bootstrap — Source-preserving AI edit protocol (three-skill suite)

**Version:** 9.5.1
**Date:** 2026-07-13

## What This File Does

Installer manifest for the **track-changes** suite for Claude Code. The suite ships **three skills** that share a single `tc_core` package:

- **`track-changes`** (always-on, opt-in per file/folder) — every Claude edit to a tracked `.md` / `.qmd` / `.tex` file is wrapped in a `<mark>…</mark><sup>N</sup>` highlight you can review and accept/reject. This is the mark-gate. **Source-validation discipline (9.0.0):** AI text supported by a document source lands as a green `sourced` region beside a temporary gray `.tc-verbatim` excerpt that is verbatim *by construction* — `/tc source` stages the slice and the write-time hook re-reads the source and refuses a fabricated or paraphrased quotation (fail-closed), with a per-document evidence manifest (`/tc manifest`) and annotated-PDF twins as durable, machine-generated proof. **9.1.0 hardens this:** a `sourced` region is now always-cited and always-verified, enforced at the write — the surviving green interpretation must carry a reader-facing citation, and a `sourced` region can no longer land without its verified gray excerpt.
- **`verified-import`** (opt-in, invoked via `/tc import`) — insert a vetted source (a Word chapter, a prior notebook, a manuscript section) into a tracked document. Claude converts the source to the document's format and lands it **clean** (no marks): the LLM imports faithfully and self-marks only genuinely significant changes (altered meaning) in track-changes marks; minor diffs land clean. A PreToolUse hook writes a one-shot, sha-bound exemption that the always-on `track-changes` skill honors, so the faithful block is not mark-wrapped. **Import-fidelity guarantee (8.2.0):** the same hook mechanically verifies **content-token coverage** — an import that silently drops source content (a word, number, or subscripted identifier) is blocked with the missing tokens named; rewording/reformatting passes, and `--allow-partial` is the explicit, audited override. Audit a whole document with `/tc coverage <doc> <source>`.
- **`tc-polish`** (opt-in, invoked via `/tc polish [file]`) — clean up **and editorially improve voice-dictated** prose in an existing tracked document: recognition/grammar/dropped-word fixes **plus** meaning-preserving restructuring (split run-ons, reorder for flow, tighten wordiness). Every change surfaces as an ordinary track-changes `<mark>` you review with `/tc accept|reject`. Bright line: it **never** auto-corrects an unrecognized token (jargon / code / math / domain term) — such a token is left and flagged, never silently changed; a meaning-affecting fix is surfaced as a mark, not applied silently. tc-polish adds **no hook** — its fixes flow through the existing `track-changes` PreToolUse hook — and **no slash-command file** (the explicit `/tc polish` invocation is the opt-in). It reuses the shared `tc_core` for its tracked-check.

When Claude Code follows the instructions below, it downloads all three skills — hooks, library modules, the shared `tc_core` package, slash commands, and reference docs — and merges **six** hook registrations into your `~/.claude/settings.json` (five for `track-changes`, one for `verified-import`; `tc-polish` owns no hook).

**The suite design:**
- **Leaner always-on footprint.** The `track-changes` skill is narrowed: source-provenance import wrappers moved out into the separate opt-in `verified-import` skill; cross-file mark renumbering and edit-inside-non-rendering-construct sibling handling were removed (such edits now route to `/draft`).
- **SessionStart digest.** The session-start hook now injects a compact `reference/digest.md` (~2.9 KB) instead of the full `SKILL.md` — ~93.5% smaller, well under the 40 KB inline cap. The full `SKILL.md` is lazy-loaded on demand.
- **Convert-on-import (LLM-judgment) + coverage gate (8.2.0).** `verified-import` trusts the LLM to import the AI-converted block faithfully — there is no mechanical *equivalence* gate. On a live pending-import the hook writes a one-shot, sha-bound exemption that the `track-changes` gate consumes, so the converted block lands clean; the model self-marks only genuinely significant changes (altered meaning) for the author to review. As of 8.2.0 the hook does enforce mechanical **completeness**: every source content token must appear in the written block, so an import cannot silently drop content (block + named missing tokens; `--allow-partial` overrides, audited).
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

You are reading the track-changes v9.5.1 bootstrap manifest. Follow these steps precisely.

### Step 1: Check for existing installation

Read `~/.claude/skills/track-changes/VERSION`. If the file exists, parse the first line as a version number. Compare it to `9.5.1` using semantic-version ordering (compare major, then minor, then patch as integers; treat a missing component as 0, so a two-part `2.0` is `2.0.0`).

- **Equal to 9.5.1** → "track-changes v9.5.1 is already installed. No update needed." **STOP.**
- **Higher than 9.5.1** → "track-changes v[installed] is newer than this bootstrap (9.5.1). Aborting — will not downgrade." **STOP.**
- **Lower than 9.5.1** (e.g. v9.5.0, v9.4.x, v9.3.x, v9.2.x, v9.1.x, v9.0.x, v8.x, v7.0.x, v6.0.x, v5.0.x, v4.x, v3.0.x, or any v1.x or v2.x) → "Updating track-changes from v[installed] to v9.5.1." Proceed to Step 2. The download in Step 2 overwrites every skill file in place (and, from a pre-v5 install, adds the `tc-polish` skill), so the upgrade is a clean replacement (the upgrade also re-merges settings.json, laying down the single combined PreToolUse matcher group); existing `<mark>…</mark><sup>N</sup>` content in your documents is fully backward-compatible and is left untouched (the mark grammar is unchanged — no document migration is needed). **Upgrading from v4.0.x?** The per-file activation key was renamed `track-changes:` → `tc-track:` in v4.1 (the old key is a reserved Quarto YAML field that breaks `.qmd`/`.md` renders); swap any old keys to `tc-track:`. **v6 is behavior-changing:** `/draft` is now **user-only** — the AI can no longer suspend its own tracking (the suspension sentinel is written solely by the `UserPromptSubmit` hook on *your* `/draft` prompt). Everything the AI writes into a tracked deliverable is tracked; large new blocks use the new whole-region insertion (`::: {.tc-region …}` / `\tcregion`). No document migration — the mark grammar is backward-compatible. **Upgrading from v6?** The bare `/polish` and `/import` slash aliases are retired — use `/tc polish` and `/tc import` instead. The `polish` skill directory is renamed to `tc-polish` (the upgrade removes the old `~/.claude/skills/polish/` directory and `~/.claude/commands/import.md` if present). No document migration. **Upgrading from v7?** v8 adds the bundled `decap` editor pre-clean tool under `~/.claude/skills/track-changes/tools/`; no behavior change to tracking, the mark grammar, or the hook suite. **Upgrading from v8.0/v8.1?** 8.2.0 adds the import-fidelity coverage gate (`tc_core/coverage.py` + `tc_coverage_audit.py`, wired into the verified-import hook) and the `/tc coverage` audit command; existing import behavior is otherwise unchanged, hook count stays 6, no document migration. **Upgrading from v8.x?** v9.0.0 adds the source-validation discipline: `/tc source` staging, the `sourced` provenance value with `tc-src` bindings, mechanical gray-excerpt verification in the track-changes hook, the `/tc manifest` evidence file, the `annotate_source_pdf.py` tool, and LaTeX `tcverbatim` + the optional `tcregion` `src` argument. Existing tracking, imports, and polish are unchanged; the mark grammar is backward-compatible (absent provenance/`tc-src` reads as authored — the new optional `tcregion` `src` arg leaves every v6/v7 parse untouched); hook count stays 6; no document migration. **Upgrading from v9.0?** 9.1.0 tightens the source gate — a `sourced` region must now carry a reader-facing citation (the exact key when staged by `@citekey`) and can no longer land without its verified excerpt; no document migration, hook count stays 6. Existing sourced regions keep working; editing one now requires keeping its citation. **Upgrading from v9.1.0?** 9.1.1 lets a gray excerpt carry contiguous source context with the load-bearing sentence marked (`[…]{.tc-src-key}` / `\tcsrckey{…}`); additive and presentational, no gate change, no migration. **Upgrading from v9.1.x?** 9.2.0 adds web-source citation: `/tc source <url>` (or `/tc source @webkey`, a bib `@online`/`@misc` entry with `url`+`urldate`) captures a dated snapshot into the private `validation/sources/` folder and verifies gray excerpts against it, just like a file source; new shared lib `tc_core/websource.py` and a `.html` branch in `sourcetext.py`. No gate change, no new hooks (stays 6), no document migration. **Upgrading from v9.2.x?** 9.3.0 completes the sourced-region lifecycle: `/tc accept`/`/tc reject` of a `sourced`/`transcript` region now also removes its paired gray `.tc-verbatim` scaffolding block, and the human-facing evidence is generated automatically (the manifest refreshes on each sourced write; the annotated-PDF twin regenerates on accept — both best-effort, never blocking). Behavior-changing for resolution, but backward-compatible grammar, no new hooks (stays 6), no document migration. **Upgrading from v9.3.x?** 9.4.0 adds paragraph continuity for region acceptance: a region may carry `tc-join="prev"|"next"` (LaTeX: a 4th optional `egin{tcregion}{N}[prov][src][join]`) to rejoin an adjacent paragraph on `/tc accept` instead of leaving a standalone block, and `/tc accept` now emits an advisory orphan-paragraph warning. Additive/opt-in; absent the attribute, resolution is unchanged; back-compat grammar, no new hooks (stays 6), no migration. **Upgrading from v9.4.x?** 9.5.0 hardens web-source capture: the headless render waits for JavaScript content (`--virtual-time-budget`), a thin/empty snapshot now gives loud save-then-source guidance instead of staging a silent shell, a fail-closed capture leaves no junk file, and SSL/cert fetch errors report plainly. Additive/robustness; no gate, grammar, or hook change (stays 6); no migration. **Upgrading from v9.5.0?** 9.5.1 is a matcher bug fix: the gray-block pairing now recognizes an attribute-free `::: tc-verbatim` div (bare-class Pandoc form), not only `::: {.tc-verbatim …}`, so `/tc accept`/`reject` auto-removes a bare gray block too. Matcher-only; no behavior, grammar, or hook change (6); no migration.
- **Does not exist** → "Installing track-changes v9.5.1." Proceed to Step 2.

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

### Step 2.5: Remove retired artifacts (upgrade only)

This step matters only when **upgrading from before v7**; on a fresh install both paths below are absent and it is a no-op. The download in Step 2 overwrites and adds files but does **not** delete files that no longer ship — so a pre-v7 install would otherwise keep the retired `/polish` skill and `/import` command resolvable, defeating the v7 namespace consolidation. If either path still exists, delete it:

- the directory `~/.claude/skills/polish/` — the skill was renamed to `tc-polish` in v7; the old directory must go so a stale `/polish` no longer resolves.
- the file `~/.claude/commands/import.md` — the bare `/import` command was retired in v7 (use `/tc import`).

After deleting, confirm `~/.claude/skills/polish` is gone and `~/.claude/skills/tc-polish` is present.

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

1. Read `~/.claude/skills/track-changes/VERSION` → first line must be `9.5.1`.
2. Read `~/.claude/skills/track-changes/SKILL.md` → must begin with `---` (YAML frontmatter).
3. Read `~/.claude/skills/track-changes/hooks/pre_tool_use.py` → must begin with `"""` (Python docstring).
4. Read `~/.claude/skills/track-changes/lib/tc_core/grammar.py` → must exist (shared mark-grammar package).
4a. Read `~/.claude/skills/track-changes/lib/tc_core/coverage.py` → must exist (import-fidelity coverage lib, 8.2.0).
4b. Read `~/.claude/skills/track-changes/lib/tc_core/sourcetext.py` → must exist (source normalize + extract_text lib, 9.0.0).
4c. Read `~/.claude/skills/track-changes/lib/tc_core/srcstage.py` → must exist (pending-source staging + citekey resolution, 9.0.0).
4d. Read `~/.claude/skills/track-changes/lib/tc_core/cite.py` → must exist (reader-facing citation detector, 9.1.0).
4e. Read `~/.claude/skills/track-changes/lib/tc_core/websource.py` → must exist (web-source capture: validate_url/discover_browser/capture, 9.2.0).
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
15. Read `~/.claude/skills/track-changes/tools/annotate_source_pdf.py` → must exist (source-excerpt PDF annotator, 9.0.0).
16. Read `~/.claude/skills/track-changes/lib/tc_source.py` and `~/.claude/skills/track-changes/lib/tc_manifest.py` → both must exist (the `/tc source` staging CLI and the `/tc manifest` generator, 9.0.0).

Any verification failure → report to user and do not claim success.

### Step 5: Inform the user

On success, tell the user:

> **track-changes v9.5.1 installed successfully — three skills + shared `tc_core` + bundled tools.**
>
> **`track-changes`** (`~/.claude/skills/track-changes/`): always-on mark-tracking. SKILL.md, VERSION, settings-patch.json, hooks/ (5 sh + 2 py), lib/ (6 py + 6 sh + 1 sty + the shared `tc_core` package — now 10 modules incl. `sourcetext.py`/`srcstage.py`/`cite.py`/`websource.py`), reference/ (highlight-syntax.md, latex.md, quarto-notes.md, **digest.md**, tc-clean.css, tc-clean.js), tools/ (decap.py, decap_protect.txt, **annotate_source_pdf.py**).
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
> **Verified import:** `/tc import [--allow-partial] <source>[#L<a>-L<b>] [<target>]` inserts a vetted source into a tracked document. Claude converts it faithfully to the document's format and the import lands clean (no marks). Claude self-marks only genuinely significant changes (altered meaning) for you to review. **Import fidelity (8.2.0):** the write is mechanically coverage-gated — if any source content token is missing from the converted block, the import is blocked and the dropped tokens are named (`--allow-partial` is the explicit, audited override). Audit a whole document with `/tc coverage <doc> <source> [--units N,N,…]`.
>
> **Source-validation discipline (9.0.0):** `/tc source <file>#<locator> [<target>]` (or `/tc source @citekey [<locator>] [<target>]`) stages a document source and prints an instruction to write a temporary gray `.tc-verbatim` excerpt beside a green `sourced` region carrying its `tc-src`. The write-time hook re-reads the source and **refuses a fabricated or paraphrased excerpt** (fail-closed), so a green sourced claim always sits beside genuine supporting text. **Always-cited + always-verified (9.1.0):** the hook also refuses a `sourced` region that lacks a reader-facing citation (the exact key when staged by `@citekey`, else any citation/footnote token) or that lands without its verified gray excerpt — a `sourced` claim must be attributed in the document, not only in `tc-src` metadata, and editing a sourced region must keep its citation. Sources may be text, `.pdf`, or `.docx`; `@citekey` resolves via the document's `.bib` or a `.tc-sources.json` map. Regenerate the durable per-document evidence file with `/tc manifest [<doc>]` → `validation/<stem>.sources.md`; highlight verified excerpts in annotated PDF twins with `tools/annotate_source_pdf.py`.
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
- `skill/lib/tc_coverage_audit.py` → `~/.claude/skills/track-changes/lib/tc_coverage_audit.py`
- `skill/lib/tc_source.py` → `~/.claude/skills/track-changes/lib/tc_source.py`
- `skill/lib/tc_manifest.py` → `~/.claude/skills/track-changes/lib/tc_manifest.py`

### track-changes — shared `tc_core` package
- `skill/lib/tc_core/__init__.py` → `~/.claude/skills/track-changes/lib/tc_core/__init__.py`
- `skill/lib/tc_core/grammar.py` → `~/.claude/skills/track-changes/lib/tc_core/grammar.py`
- `skill/lib/tc_core/activation.py` → `~/.claude/skills/track-changes/lib/tc_core/activation.py`
- `skill/lib/tc_core/audit.py` → `~/.claude/skills/track-changes/lib/tc_core/audit.py`
- `skill/lib/tc_core/exempt.py` → `~/.claude/skills/track-changes/lib/tc_core/exempt.py`
- `skill/lib/tc_core/coverage.py` → `~/.claude/skills/track-changes/lib/tc_core/coverage.py`
- `skill/lib/tc_core/sourcetext.py` → `~/.claude/skills/track-changes/lib/tc_core/sourcetext.py`
- `skill/lib/tc_core/srcstage.py` → `~/.claude/skills/track-changes/lib/tc_core/srcstage.py`
- `skill/lib/tc_core/cite.py` → `~/.claude/skills/track-changes/lib/tc_core/cite.py`
- `skill/lib/tc_core/websource.py` → `~/.claude/skills/track-changes/lib/tc_core/websource.py`

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
- `skill/tools/annotate_source_pdf.py` → `~/.claude/skills/track-changes/tools/annotate_source_pdf.py`

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

## v9.2.0 Changelog Summary

**v9.2.0 (web-source citation with a captured dated snapshot — minor, additive).** Adds a **web page** as a citable source type. `/tc source <url>` (and `/tc source @webkey`, a bib `@online`/`@misc` entry carrying `url`+`urldate`) fetches the page **at stage time** and captures a **dated snapshot** into the document's private `validation/sources/` folder — a discovered headless Chrome/Chromium/Edge renders a `.pdf` (`--print-to-pdf`), and no browser / a render failure / a timeout falls back **loudly** to a `urllib` fetch → `.html` text snapshot. The pending-source record points at the LOCAL snapshot, so everything downstream reuses v9 unchanged: the always-on PreToolUse hook verifies the gray `.tc-verbatim` excerpt against the snapshot text (normalized-exact containment, **network-free**), the 9.1.x always-cited/always-verified gate + the source anchor apply, and the `sourced:` audit entry / `/tc manifest` record the **URL + access date + snapshot** (the manifest links the snapshot with an "(HTML snapshot)" note for the fetch fallback). The snapshot is the durable, viewable proof that gives the access date real teeth against link rot. **Security posture:** capture is **SSRF-guarded** — `validate_url` accepts only public `http(s)` URLs and rejects loopback / private (10/8, 172.16/12, 192.168/16) / link-local / cloud-metadata (169.254.169.254) / reserved addresses **before any fetch** (a `TC_SOURCE_ALLOW_LOCAL=1` opt-in, set only by the test harness, permits loopback for localhost fixtures; production leaves it unset); the browser is invoked as an **argument list** with `shell=False`, so the URL is one argv element and is never interpreted by a shell. **Privacy:** snapshots stay in the private `validation/` folder — `.gitignore` it, never fold it into a public repo. **Non-goal:** authenticated / paywalled pages — save the rendered page to a file and `/tc source` the **file path** instead. New shared lib `tc_core/websource.py` + a `.html`/`.htm` branch in `tc_core/sourcetext.py`; `srcstage`/`tc_source`/audit/manifest carry the URL, access date, and snapshot. Backward compatible (a file/PDF/docx source is byte-identically unchanged); **no new hooks** (suite stays at 6); no document migration.

## v9.1.1 Changelog Summary

**v9.1.1 (contextual gray excerpts + source anchor — additive, presentational).** Lets a gray `.tc-verbatim` excerpt carry a **contiguous passage of surrounding source context** instead of the bare load-bearing sentence, so the evidence reads in context. The part actually proposed as the source — the load-bearing sentence — is wrapped in a **source-anchor marker**: `[sentence]{.tc-src-key}` in `.md`/`.qmd`, `\tcsrckey{sentence}` in `.tex`. The whole block stays gray (all of it is verbatim source); the anchor is merely **emphasized** (bold + underline, no new color). The write-time containment check **strips only the anchor marker syntax** before verifying — the inner text must still be verbatim-contained in the staged source, so the marker cannot smuggle non-source text — and the audit/manifest record the clean, anchor-stripped excerpt. Guidance (no gate change): a sourced region must stay **scoped** to what the source supports — an inference built on top of the source is authored (uncited) content, not sourced, and a single citation must not creep over unsupported claims. Backward compatible: an excerpt with no anchor behaves exactly as before; **no new hooks** (suite stays at 6); no new shipped files; no document migration.

## v9.1.0 Changelog Summary

**v9.1.0 (ironclad sourced-region enforcement — behavior-changing, back-compatible grammar).** Closes two holes in the v9.0.0 source gate so `tc-prov="sourced"` becomes an **always-verified AND always-cited** claim, enforced mechanically at the write rather than merely prompted. **Always-verified (hole 2 closed):** the gate's trigger set is widened to *new gray `.tc-verbatim` excerpts* **∪** *touched `sourced` regions*, and a brand-new sourced region and its verified gray excerpt must now land as **one pair** — a `sourced` region can no longer bypass verification by omitting the excerpt (in v9.0.0 it silently landed as an ordinary tracked region). **Always-cited (hole 1 closed):** the surviving green region must carry a **reader-facing citation** — **Rule A** when the source was staged by `@citekey`, the region must cite **that exact key** (`[@key]` md/qmd, `\cite{key}` tex); **Rule B** otherwise, the region must contain any citation/footnote token (`[@key]`/`@key`/`^[…]`/`[^ref]` md/qmd; the `\cite`-family — `\citep`/`\citet`/`\autocite`/`\parencite`/`\textcite`/`\footcite`/… — or `\footnote{` tex). Citations that render **nothing to a reader do not count**: a token inside a code span/fence, an HTML or LaTeX comment, or a `verbatim`/`\verb` context is ignored (`\nocite` is likewise excluded). Editing an already-present sourced region needs no re-staging but must **keep** a citation — a confirmed sourced passage cannot be edited into an unattributed one. Rationale: `tc-src` is invisible provenance metadata (stripped on `/tc accept`), not attribution; a sourced claim must be attributed in the **document itself**, and enforcement — not prompting — is what makes this hold when an AI agent does the authoring. On failure the write is blocked (exit 2) with the staging record preserved and a message naming the exact expected key (Rule A) or the accepted citation forms (Rule B). New shipped file `tc_core/cite.py` (stdlib, data-only citation detector: `has_citation`/`cites_key`); the `/tc source` instruction and SKILL.md §16 are aligned with the enforcement. The change was **adversarially red-teamed** — an independent pass driving the real hook cannot land a citation-free or unverified `sourced` passage. Backward compatible: the mark grammar is unchanged; **no new hooks** (suite stays at 6); no document migration.

## v9.0.0 Changelog Summary

**v9.0.0 (source-validation discipline, suite-wide — additive, back-compatible).** Generalizes the transcript gray/green convention to arbitrary document sources. AI text supported by a document source lands as a green `sourced` region beside a temporary **gray `.tc-verbatim` excerpt that is verbatim *by construction***: `/tc source <file>#<locator>` (or `/tc source @citekey [<locator>]`) stages the source slice, and the always-on track-changes PreToolUse hook re-reads the source at write time and **refuses a fabricated or paraphrased excerpt** (exit 2, staging preserved for a corrected retry), so a green sourced claim always sits beside genuine supporting text. Containment is **normalized-exact** — NFKC fold, soft-hyphen/ligature/hyphen-linebreak-join, whitespace collapse (case preserved) — so an honest PDF excerpt spanning a line break passes while fabrication stays refused; a scanned/unreadable source **fails closed**. Sources: text (`.md`/`.qmd`/`.tex`/`.txt`), `.pdf` (PyMuPDF), `.docx` (python-docx). New provenance value `tc-prov="sourced"` (joining authored/imported/transcript) with a `tc-src` attribute binding the region to `path#locator` or an `@citekey locator` resolved via the document's `.bib` `file`/`localfile` field or a `.tc-sources.json` map (unresolvable keys fail closed, naming both mechanisms). Durable evidence is **machine-generated, never model-reconstructed**: on a verified landing the hook appends a `sourced:` entry to the project's append-only `.tc-history.md`, and `/tc manifest [<doc>]` regenerates `validation/<stem>.sources.md` whole-file and deterministically (one section per region — source, locator, verbatim excerpt, supported text, links both ways — plus a "Resolved/removed regions" list). The bundled `tools/annotate_source_pdf.py` highlights each verified excerpt in an annotated PDF **twin** (never the original) under `validation/`, regenerates a trailing summary page, and reports every unmatched excerpt (nonzero exit); image-only PDFs are reported and skipped. **LaTeX is first-class:** `tcregion` gains an optional trailing `src` argument (`{N}[prov][src]`, xparse `m o o` — an absent second optional leaves every v6/v7 parse untouched) plus a new `tcverbatim` gray-scaffolding environment and green transcript/sourced change-bars; the suite-shipped `tc-clean.css` now styles all four provenances and `.tc-verbatim` under both raw and `data-`-prefixed attribute forms, so a course `_quarto.yml` can shrink to a thin consumer. Backward compatible: the mark grammar is unchanged (absent provenance/`tc-src` reads as authored); **no new hooks** (suite stays at 6); no document migration. New shipped files: `tc_core/sourcetext.py`, `tc_core/srcstage.py`, `lib/tc_source.py`, `lib/tc_manifest.py`, `tools/annotate_source_pdf.py`.

## v8.2.0 Changelog Summary

**v8.2.0 (import-fidelity coverage check — minor, additive).** A verified import can no longer silently drop source content (the recurring "translated only part of a slide" failure, e.g. keeping three of four rates and losing `r_f`). New shared lib `tc_core/coverage.py` compares **content tokens** (words ≥ 4 letters minus a stoplist, numbers ≥ 2 significant chars, subscripted identifiers like `r_f`) after normalizing formatting away, so reordering/reformatting passes and only dropped content fails. The verified-import PreToolUse hook now blocks a content-dropping import write (exit 2), names the missing tokens, and keeps the pending import live for a corrected retry; `/tc import --allow-partial` is the explicit override for intended omissions (recorded, with the dropped list, in the audit log). Fail-closed: if the source cannot be re-read at write time, the import is blocked. New `/tc coverage <doc> <source> [--units N,N,…]` audits whole-document completeness per source unit (`--slides` alias kept). Backward compatible: the pending record gains one optional key; existing import behavior is otherwise unchanged; hook count stays 6; no document migration.

## v8.1.0 Changelog Summary

**v8.1.0 (committed-content resolution gate + transcript provenance).** `accept`/`reject`/`accept-all`/`reject-all` now REFUSE (exit 3) on a file with uncommitted changes or an untracked file (`tc_require_clean` in `lib/tc-cli.sh`): an open mark is editable right up to resolution, so approval could otherwise attach to content the reviewer never read. Enforced sequence: commit instructor tweaks (own commit) → commit AI corrections as MARKED edits (own commit) → review diffs → resolve. `list` is not gated; `TC_FORCE=1` is a human-only override; fail-open outside a git repo. Also adds `tc-prov="transcript"` to the provenance values (AI wording over the instructor's own class-recording transcript content, conventionally paired with a TEMPORARY `.tc-verbatim` scaffolding block). No new hooks; suite stays at 6.

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
