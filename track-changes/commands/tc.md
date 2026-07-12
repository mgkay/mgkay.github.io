---
description: track-changes unified command (draft / enable / disable / mark / migrate / status / coverage / source / manifest / help / import / polish)
allowed-tools: Bash(bash:*)
argument-hint: "draft|enable|disable|mark|migrate|status|list|accept|reject|accept-all|reject-all|coverage|source|manifest|import|polish|help [args]"
---

!bash "$HOME/.claude/skills/track-changes/lib/tc-cli.sh" $ARGUMENTS

Run `/tc` with no arguments to print the compact menu.

Subcommands:

- `/tc draft` — suspend tracking for the current turn only
- `/tc enable <file>` — add `tc-track: true` to the file's YAML frontmatter (or `% tc-track: true` magic comment for `.tex`)
- `/tc disable <file>` — add `tc-track: false` to the file (per-file opt-out)
- `/tc mark [<dir>]` — drop `.tc-tracked` marker in `<dir>` (default: current directory)
- `/tc migrate <dir>` — convert v1 marks to v2 in all `.md`/`.qmd`/`.tex` files under `<dir>`
- `/tc status [<file>]` — show the activation chain for `<file>` (or the working file / current directory)
- `/tc list [<file>]` — list each mark in `<file>` with its number and a short content preview (omit `<file>` to use the working file)
- `/tc accept [<file>] <ranges>` — accept the listed marks: keep the new text, strip the `<mark>…</mark><sup>N</sup>` wrapper. Ranges use `1-25,!7,!11` syntax (inclusive comma-separated ranges; `!N` excludes `N`). Omit `<file>` to use the working file (the lone argument is then the ranges).
- `/tc reject [<file>] <ranges>` — reject the listed marks: restore the old text, strip the wrapper (same range syntax; `<file>` optional)
- `/tc accept-all [<file>]` — accept every mark in `<file>` (omit `<file>` to use the working file)
- `/tc reject-all [<file>]` — reject every mark in `<file>` (omit `<file>` to use the working file)
- `/tc coverage <doc> <source> [--units N,N,…]` — audit import completeness: for each source unit (`<!-- slide N -->` marker; the whole file when the source has no markers), report the % of content tokens covered by `<doc>` and list any missing ones (`--slides` accepted as an alias for `--units`). Exits non-zero when any unit dropped content — run it before declaring a converted document done.
- `/tc source <file>#<locator> [<target>]` (or `/tc source @citekey [<locator>] [<target>]`) — stage a slice of a document source, then print the slice together with an instruction to write **one** edit that pairs a temporary **gray verbatim** excerpt (`::: {.tc-verbatim …}` / `\begin{tcverbatim}{…}`) with a **green `sourced` region** carrying its `tc-src` and the next mark number. The excerpt is **verified mechanically at write time** — the track-changes hook re-reads the source and refuses a fabricated or paraphrased quotation (fail-closed), so a green sourced claim always sits beside genuine supporting text. Two source forms: a **path** with an optional trailing `#locator` (`L<a>-L<b>` text lines, `p.<a>[-<b>]` PDF pages, or none for the whole file), or an **`@citekey`** resolved via the document's `.bib` `file`/`localfile` field or a `.tc-sources.json` map (unresolvable keys fail closed, naming both mechanisms). `<file>` sources may be text (`.md`/`.qmd`/`.tex`/`.txt`), `.pdf` (PyMuPDF), or `.docx` (python-docx); a scanned/image PDF with no text layer is refused. The gray block is scaffolding — delete it once the green region is confirmed; the durable record is the `sourced:` audit entry. `<target>` defaults to the working file.
- `/tc manifest [<doc>]` — regenerate `validation/<stem>.sources.md` for `<doc>` (the working file by default) from the `sourced:` audit evidence in `.tc-history.md`: one section per sourced region with its source, locator, verbatim excerpt, and supported text, plus a "Resolved/removed regions" list. The manifest is written **whole-file and deterministically** (re-running yields identical bytes); it is machine-generated evidence, never model-reconstructed.
- `/tc help` — show this list

**Cooperating skills** (dispatches to the installed companion skill):

- `/tc import [--allow-partial] <source>[#L<a>-L<b>] [<target>]` — import a slice of a text source into a tracked document via the **verified-import** skill. The dispatcher resolves and slices the source file, prints the slice together with a conversion instruction, and you convert faithfully, writing only the converted block. The block lands **clean (no `<mark>`)** via a sha-bound one-shot exemption the track-changes hook honors. Self-mark only genuinely significant changes — meaning-altering additions or removals (added/dropped sentences, changed quantities, terms, or formulas); pure formatting differences need no mark. **Coverage gate (8.2.0):** the write is blocked if any source content token (word, number, subscripted identifier) is missing from the converted block — the hook names the dropped tokens and keeps the pending import live for a corrected retry; reformatting and reordering pass. `--allow-partial` is the explicit override for an intended omission (the audit log records the override and the dropped tokens). Text sources only (`.md`, `.qmd`, `.tex`, `.txt`, etc.); binary/non-text sources are rejected. If verified-import is not installed, the dispatcher prints an actionable install hint and exits non-zero.

- `/tc polish [<file>]` — run the **tc-polish** dictation-cleanup and editorial pass on `<file>`. Corrections and restructures surface as ordinary track-changes `<mark>` marks, reviewable via `/tc accept|reject`. Bright lines: improve freely but never change meaning; never auto-correct a flagged protected token (jargon, code, math, domain terms) — leave it and flag it. If tc-polish is not installed, prints an install hint and exits non-zero.

When `<file>` is omitted for a resolution subcommand, the working file is the most-recently-modified tracked file under the project (git root, else current directory). `/tc enable` and `/tc disable` always require an explicit `<file>`.

Batch resolution edits the file directly and records each decision in `.tc-history.md` with `decision: explicit`, so a later content-survival inference (Fix #8) never overwrites a choice you made deliberately. Resolution works for `.md`/`.qmd` (`<mark>` form) and `.tex` (`\tc{}\tcn{}` form).

For the full activation-precedence chain and encoding specification, see `~/.claude/skills/track-changes/SKILL.md`.

$ARGUMENTS
