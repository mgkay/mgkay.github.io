---
name: track-changes
description: Source-preserving edit protocol. Tracks Claude-introduced changes to existing .md, .qmd, and .tex files by wrapping only the changed characters in a <mark> highlight followed by a <sup>N</sup> reference number, so the human author can accept or reject each change individually. Default-OFF; opt in per folder via .tc-tracked marker, per file via YAML frontmatter (or `% track-changes: true` for .tex). Per-turn override via /draft. Unified /tc command for all operations (/tc mark, /tc enable, /tc disable, /tc migrate, /tc status, /tc draft). Edits to tracked files append to a project-local .tc-history.md audit log.
---

# track-changes

You are reading this because the SessionStart hook loaded it into context.
The track-changes skill is **default-off**. It activates for Write, Edit,
and MultiEdit on existing files with extension `.md`, `.qmd`, or `.tex`
only when one of the opt-in mechanisms in §2 is in effect. When active,
the PreToolUse hook blocks any write that adds or removes content without
an appropriate numbered highlight wrapper. When inactive, the hook is
silent and passes through.

## 1. Protocol

**Disposition.** The human is the author. You are the copy-editor. Vetted
source documents (lecture notes, exams, manuscripts) have often been
reviewed by the author for years; silent AI-introduced changes destroy
trust. The skill exists to make every Claude-introduced change visible
and reviewable in projects where the author has explicitly opted in.

**Token-minimal marks.** Each highlight wraps **only the characters that
differ from the on-disk source** — never surrounding unchanged text. The
visual goal is a yellow span that lines up exactly with the change, so a
reviewer scanning a document can see at a glance what changed. A
phrase-level wrapper that includes unchanged words defeats the purpose
of the skill.

## 2. Activation

The skill is **off by default**. It activates per Write/Edit/MultiEdit
according to the following mechanisms, in precedence order (most-local
wins):

1. **`/draft` (per turn).** When the user invokes `/draft` (or `/tc
   draft`), the skill is suspended for the current user turn regardless
   of any other mechanism. Auto-clears at the start of the next user
   prompt.

2. **Per-file YAML frontmatter or magic comment.** A file containing
   `track-changes: true` in its YAML frontmatter is tracked. A file
   containing `track-changes: false` is exempted (overrides folder
   marker). For `.tex` files (no native frontmatter), the equivalent is
   a magic comment in the first 10 lines: `% track-changes: true` or
   `% track-changes: false`. The skill provides `/tc enable <file>` and
   `/tc disable <file>` slash commands so users do not need to hand-edit
   YAML — see §7.

3. **Folder-local marker (`.tc-tracked`).** A `.tc-tracked` file in the
   edited file's **own folder** (no walk-up, no descent into subfolders)
   activates tracking for that folder's files. The marker operates in
   one of two modes based on its content:
   - **Presence-only mode** (empty or comment-only marker) tracks every
     `.md` / `.qmd` / `.tex` file in that folder.
   - **List mode** (marker contains filename entries) tracks only the
     listed basenames in that folder. Comment lines (lines whose first
     non-whitespace char is `#`) and blank lines are ignored; remaining
     non-blank lines are treated as the filename list.

4. **Default — off.** With none of the above in effect, the hook exits 0
   silently and the edit proceeds without any tracking requirement.

### Hidden-file exclusion

Files whose basename starts with `.` (e.g., `.cache.md`, `.draft-notes.md`)
are excluded from marker-based tracking by default. This avoids friction
on auto-generated cache and scratch files inside an otherwise-tracked
folder. To force-track a hidden file, add `track-changes: true` to its
YAML frontmatter (per-file YAML overrides the hidden-file exclusion).

### Why folder-local (no walk-up)

Walk-up marker discovery caused friction with Claude-internal files
inside tracked subtrees (`CLAUDE.md`, `pcvplans/*`, `.claude/*`, auto-
memory files, etc.). With folder-local markers, each folder is
independent: marking `lectures/` does not implicitly track files under
`lectures/notes/` unless you drop a separate marker there. Subfolders
that should be tracked get their own marker; subfolders that shouldn't
stay untouched.

### Why no `/track-on` or `/track-off`

Pre-Fix-#6 versions had session-scope toggles. They reintroduced the
same internal-file friction at session scope (forcing every `.md` in
the session to track, including ones Claude was editing internally for
its own purposes). Fix #6 dropped them. Bulk activation is now the
folder marker; selective activation is per-file YAML; per-turn override
remains `/draft`.

When the hook is active and a write violates the protocol, the hook
blocks with a structured error citing the line number and the rule
violated.

## 3. Highlight Syntax (Markdown)

For files with extension `.md` and `.qmd`, the highlight wrapper is the
raw HTML `<mark>` element wrapping ONLY the changed characters, followed
immediately by `<sup>N</sup>` carrying the reference number. The `<sup>`
sits *outside* the mark so the yellow highlight stays tight to the change
while the reference number remains visible for review.

This renders natively in Quarto's HTML output, GitHub markdown preview,
and VS Code's built-in preview without extensions.

| Change type | Pattern | Example |
|-------------|---------|---------|
| Insertion | `<mark>new</mark><sup>N</sup>` | `tes<mark>ted</mark><sup>7</sup>` |
| Deletion | `<mark><s>old</s></mark><sup>N</sup>` | `tes<mark><s>ted</s></mark><sup>8</sup>` |
| Replacement | `<mark><s>old</s>new</mark><sup>N</sup>` | `<mark><s>slow</s>tired</mark><sup>9</sup>` |

In a replacement, the strikethrough `<s>old</s>` and the new characters
`new` sit adjacent inside the same mark. Both are highlighted yellow;
the strikethrough delineates old from new.

**Why `<s>` and not `~~`?** GFM strikethrough (`~~old~~`) renders correctly
on GitHub but fails in markdown-it-based viewers (VS Code built-in preview,
common Chrome markdown extensions) when the wrapped text starts or ends with
whitespace — markdown-it enforces a left/right flanking rule on `~~`. HTML
`<s>` has no such restriction and renders strikethrough in every viewer.
Files written before Fix #7 may contain `~~` marks; the hook accepts them and
the audit log classifier treats them as a legacy fallback. New marks should
use `<s>`.

### Worked examples

**Insertion — adding a missing word.**

```
On-disk:  Every continuous function on a compact set attains its maximum.
Edit:     Every <mark>uniformly </mark><sup>3</sup>continuous function on a compact set attains its maximum.
```

The mark wraps only the inserted "uniformly " (including the trailing
space, which is also new). "Every " and "continuous function..." stay
bare.

**Deletion — removing a forward reference.**

```
On-disk:  The bound holds for all $n\ge 1$, as we will see in Chapter 4.
Edit:     The bound holds for all $n\ge 1$<mark><s>, as we will see in Chapter 4</s></mark><sup>5</sup>.
```

**Replacement — narrowing a word.**

```
On-disk:  Every continuous function on a compact set attains its maximum.
Edit:     Every <mark><s>continuous</s>monotone</mark><sup>4</sup> function on a compact set attains its maximum.
```

Only the changed word is wrapped. Everything else stays bare.

**Dense paragraph — multiple edits.**

```
On-disk:  The quick brown fox lazily jumps over the slow dog.
Edit:     The qu<mark>ick</mark><sup>1</sup> brown fox <mark><s>lazily</s></mark><sup>2</sup>
          jump<mark>ed</mark><sup>3</sup> over the <mark><s>slow</s>tired</mark><sup>4</sup> dog.
```

Review shorthand: "accept 1, 3, 4; reject 2."

### What you must NOT do

- Do not wrap unchanged characters. The mark covers only chars that
  differ from on-disk.
- Do not omit the `<sup>N</sup>` after the mark — it is the reference
  number used for review ("accept 1–25 except 7 and 11").
- Do not place the `<sup>` INSIDE the `<mark>` — the number lives outside
  so the highlight stays minimal.
- Do not reuse a number that already appears in the file.
- Do not reformat for the sake of reformatting. Re-flowing paragraphs,
  normalising whitespace, restyling tables — all create diff hunks the
  hook treats as changes.
- Do not leave **incidental new characters outside the mark wrapper**
  (Fix #10). If the AI inserts a new sentence preceded by a space —
  e.g. `Paragraph.<mark> New sentence.</mark><sup>N</sup>` — the leading
  space *is* new content and must sit inside the mark wrapper, not
  outside. Pre-Fix-#10 line-level coverage would let `Paragraph. <mark>New sentence.</mark><sup>N</sup>`
  through; the strict per-region check now blocks it. Pull the
  whitespace into the wrapper.

### Resolution (accept / reject) — Fix #8

When the user reviews a tracked file and tells the AI to accept or
reject existing marks, the AI removes the mark wrappers in place,
keeping either the `new` chars (accept) or the `old` chars (reject).
The result line may have **zero marks** — that's expected, because
acceptance turns a marked change into plain text.

The PreToolUse hook recognises this kind of edit as a **resolution**
and allows it without requiring a new mark wrapper around the result
line, provided every byte of the proposed file is accounted for by
one of:

- a **preserved mark** (same `N` in source and proposed, identical body);
- a **resolved source mark** whose chars at the corresponding proposed
  position match either its `new` text (accept) or its `old` text (reject);
- an **introduced mark** in proposed (new `N`) properly wrapping its body;
- an **unchanged plain-text segment**.

Any character not accounted for under one of these → the edit is not a
pure resolution, and the standard line-coverage rules apply.

**Worked example.** Source file contains:

```
It is for <mark><s>Bill</s>Jack</mark><sup>1</sup> to send a message.
```

User: "accept the change." AI rewrites the line to:

```
It is for Jack to send a message.
```

The hook walks: plain-text prefix `It is for ` matches, source mark #1
is removed and the chars `Jack` (the mark's `new`) appear in proposed
at the resolution position — accept inferred. Plain-text suffix ` to
send a message.` matches. Walk succeeds; the edit lands.

The PostToolUse audit hook then records mark #1 as `resolved` with
`decision: accepted` (since `Jack` survives in the file and `Bill`
does not).

**Mixing accept/reject with new edits.** A single edit can legitimately
resolve some marks AND introduce new marks. The walk handles this:
introduced marks are consumed in the proposed only (advancing proposed
position past them without advancing source position), while resolved
marks consume their accept-or-reject chars on the proposed side. The
edit is still recognised as a resolution provided every byte is
accounted for.

## 4. Highlight Syntax (LaTeX)

For files with extension `.tex`, the highlight wrapper is the `\tc{}`
macro wrapping only the changed characters, followed immediately by
`\tcn{N}` carrying the reference number. The macros are defined in
`tc.sty` (skill-provided; see §10).

| Change type | Pattern | Example |
|-------------|---------|---------|
| Insertion | `\tc{new}\tcn{N}` | `tes\tc{ted}\tcn{7}` |
| Deletion | `\tc{\sout{old}}\tcn{N}` | `tes\tc{\sout{ted}}\tcn{8}` |
| Replacement | `\tc{\sout{old}new}\tcn{N}` | `\tc{\sout{slow}tired}\tcn{9}` |

`\sout{}` (strikeout) comes from the `soul` package that `tc.sty` loads.

### Worked examples

**Insertion — adding a hypothesis.**

```
On-disk:  Let $f:[a,b]\to\mathbb{R}$ be a function. Then $f$ attains its supremum.
Edit:     Let $f:[a,b]\to\mathbb{R}$ be a \tc{continuous }\tcn{3}function. Then $f$ attains its supremum.
```

**Replacement — tightening a hypothesis.**

```
\tc{\sout{Every continuous }Every monotone continuous }\tcn{4}function on a compact set attains its maximum.
```

**Deletion — removing a stale reference.**

```
The bound holds for all $n\ge 1$\tc{\sout{, as we will see in Chapter 4}}\tcn{5}.
```

## 5. Numbering

### Per-file scope

Numbers in `<sup>N</sup>` (or `\tcn{N}`) are unique within a single file.
The same `<sup>1</sup>` can appear in `lecture-01.md` and `lecture-02.md`
simultaneously.

### Scan before every emission

Before emitting a new mark, scan the **current file state** for existing
mark numbers and choose `N = max(existing) + 1`. The scan target is the
file as it stands at the moment of emission, not a cached value from a
prior tool call.

The hook validates the chosen N is unique. Non-contiguous numbering
(e.g., `1, 2, 7` after the user removed `3`–`6`) is allowed — the rule
is uniqueness, not contiguity.

### Cross-file paste renumbering

When pasting content from one file (Doc A) into another (Doc B), each
inherited mark whose N collides with an existing N in Doc B is
renumbered to `max(Doc B existing) + 1, +2, ...` in order of appearance.
The mark content (chars wrapped, strikethrough, new chars) carries over
exactly; only the number changes. The scan target is the **proposed**
Doc B, so a fresh edit you make at the same time as the paste continues
the numbering past the just-pasted inherited marks.

## 6. Non-Rendering Contexts

Some constructs do not render `<mark>` or `\tc{}` inside them — fenced
code, display math, YAML front matter, GFM tables, LaTeX verbatim, math
environments, tabular. When a change falls inside one of these, the
**sibling-element rule** applies: emit one sibling mark per change on
the lines immediately above the block, using the same v2 encoding as
inline marks. Then make the actual edit inside the block.

### Markdown sibling form

```markdown
<mark><s>old</s>new</mark><sup>N</sup>
` ``python
... edited content ...
` ``
```

Multiple changes within a single block → multiple sibling lines, each
with its own `<sup>N</sup>`, stacked immediately above the block opener.

### LaTeX sibling form

```latex
\tc{\sout{old}new}\tcn{N}
\begin{equation}
  ... edited content ...
\end{equation}
```

### Enumerated supported constructs

The PreToolUse hook recognises these as non-rendering:

**Markdown / Quarto:** fenced code blocks, display math `$$...$$`, YAML
front matter (top-of-file `---`), GFM pipe tables.

**LaTeX:** verbatim, lstlisting, minted, equation/equation*,
align/align*, gather/gather*, multline/multline*, `\[...\]` display
math, tabular.

### Outside-enumerated → `/draft`

Constructs outside the enumerated list (Quarto fenced divs with
attributes like `::: callout-note`, custom LaTeX environments, complex
tabularx/longtable, nested fenced code) are documented v2 limitations.
When you must edit inside one of these:

1. Ask the user to invoke `/draft` for the current turn.
2. Make the edit without a highlight wrapper.
3. Note the edit in your reply so the user can review it without the
   numbered-mark scaffolding.

## 7. Slash Commands

The skill installs a single unified `/tc` command with subcommands, plus
`/draft` as a direct alias for the per-turn override.

### Unified `/tc`

| Subcommand | Effect |
|------------|--------|
| `/tc draft` | suspend tracking for the current turn only |
| `/tc enable <file>` | add `track-changes: true` to the file's YAML (or `% track-changes: true` magic comment for `.tex`) |
| `/tc disable <file>` | add `track-changes: false` (per-file opt-out) |
| `/tc mark [<dir>]` | drop a presence-only `.tc-tracked` marker in `<dir>` (tracks ALL files in that folder; default `<dir>` = current directory) |
| `/tc mark <dir> <file1> [<file2>...]` | drop a list-mode `.tc-tracked` marker that tracks only the listed basenames in `<dir>` |
| `/tc migrate <dir>` | run v1 → v2 mark migration on all `.md`/`.qmd`/`.tex` files under `<dir>` |
| `/tc status [<file>]` | print the activation chain for `<file>` (or current directory) |
| `/tc help` | show the subcommand list |

### Legacy alias

- **`/draft`** — same as `/tc draft`.

(Pre-Fix-#6 sessions had `/track-on` and `/track-off`. Those commands
were removed in Fix #6 — see §2 "Why no `/track-on` or `/track-off`".)

### Mechanism

The `/draft` / `/tc draft` subcommand writes a per-turn sentinel file:
`~/.claude/skills/track-changes/state/<session-id>.draft`. The sentinel
clears at the next UserPromptSubmit (or via SessionStart's 1-hour TTL
sweep for crashed sessions).

`/tc enable` and `/tc disable` modify the target file directly:

- For `.md` and `.qmd`: add or update the `track-changes:` key in the
  top-of-file YAML frontmatter. If no frontmatter block exists, prepend
  a fresh `---` ... `---` block containing only the `track-changes` key.
- For `.tex`: add or update a `% track-changes: <value>` magic comment
  in the first 10 lines. If none exists, prepend it as line 1.

These are the only file modifications the skill performs outside of
edit-time hook validation. Both are idempotent — re-running with the
same value is a no-op.

`/tc mark` (no filename args) drops a presence-only marker. `/tc mark`
with one or more filename args after `<dir>` drops a list-mode marker
naming only those basenames.

### How to use these as Claude

You should **not** invoke `/tc draft`, `/tc enable`, `/tc disable`,
`/tc mark`, `/tc migrate`, or `/draft` on your own behalf. They are
deliberate user actions. If you encounter a situation where the skill
is creating friction (the hook blocks an edit you believe should land,
or the user is editing a file that would benefit from tracking),
surface the problem in your reply and suggest the appropriate command.
Wait for the user's next prompt.

## 8. Composition with PCV

PCV Builder subagents that modify existing tracked files are subject to
the skill. New-file creation passes through (file doesn't exist on
disk; hook skips).

When the user delegates to a Builder that will modify existing
`.md`, `.qmd`, or `.tex` files in a tracked project, the user prefixes
the delegation with `/draft` (for one builder turn) or invokes
`/track-off` (for the duration of the PCV cycle). The Builder operates
without highlight requirements; subsequent turns restore the default.

## 9. The `.tc-tracked` Marker

Drop a `.tc-tracked` file in any folder whose `.md`, `.qmd`, or `.tex`
files you want tracked. The hook checks **only the file's own folder**
for the marker — no walk-up, no descent into subfolders. To track
files in a subfolder, drop a separate marker there.

### Two modes (auto-distinguished by content)

**Presence-only mode** — the marker file is empty or contains only
comment lines (`#`-prefixed) and blank lines. The hook tracks every
`.md`/`.qmd`/`.tex` file in that folder (subject to the hidden-file
exclusion in §2).

**List mode** — the marker contains one or more bare lines naming
basenames to track. The hook tracks only those listed files in that
folder. Comments (`#`) and blank lines are ignored.

### Recommended marker content (presence-only)

```
# track-changes marker (kept in git)
#
# Presence of this file activates the track-changes skill for .md / .qmd
# / .tex files in THIS folder only (no walk-up, no subfolders).
#
# This marker has no filename entries below, so it operates in
# PRESENCE-ONLY mode: every .md / .qmd / .tex file in this folder is
# tracked. To track only specific files, list their basenames below
# (one per line). To track files in a subfolder, drop a separate
# .tc-tracked there.
#
# Per-file opt-out:  add `track-changes: false` to YAML frontmatter
#                    (or `% track-changes: false` near the top for .tex).
# Per-turn disable:  invoke /draft or /tc draft.
# Hidden files:      basenames starting with `.` are excluded by default.
# Remove tracking:   delete this file.
#
# Management:
#   /tc mark [<dir>]                     presence-only marker
#   /tc mark <dir> <file1> [<file2>...]  list-mode marker
#   /tc enable <file>                    per-file YAML opt-in
#   /tc disable <file>                   per-file YAML opt-out
#   /tc status [<file>]                  inspect activation chain
#   /tc migrate <dir>                    convert v1 marks to v2
```

### Recommended marker content (list mode)

```
# track-changes marker (kept in git) — LIST MODE
#
# The non-comment lines below name the files in THIS folder to track.
# Files NOT listed here are NOT tracked, even though this marker exists.
# Comments (#) and blank lines are ignored.

README.md
intro.tex
chapter1.tex
```

Drop the marker via `/tc mark <dir>` (presence-only) or
`/tc mark <dir> <file1> [<file2>...]` (list mode). Both forms write the
self-documenting comment header automatically. `touch .tc-tracked`
(empty file) also works for presence-only mode but lacks the
explanatory header.

## 10. LaTeX Preamble Setup

The `\tc{}` and `\tcn{}` macros must be defined in your `.tex` project's
preamble. The skill ships `tc.sty`; use it via:

```latex
\usepackage{tc}
```

If `tc.sty` is not on the LaTeX search path, copy it from
`~/.claude/skills/track-changes/lib/tc.sty` into your project's
preamble directory, or define the macros inline:

```latex
\usepackage{soul}
\sethlcolor{yellow}
\newcommand{\tc}[1]{\hl{#1}}
\newcommand{\tcn}[1]{\textsuperscript{#1}}
```

### SessionStart advisory

When a session starts in a CWD containing `.tex` files, the SessionStart
hook scans the first 50 lines of each `.tex` file for any of:

- `\usepackage{tc}`
- `\newcommand{\tc}` / `\renewcommand{\tc}` / `\providecommand{\tc}`
- `\let\tc=`

If any tracked `.tex` file lacks all of these, the hook appends an
advisory to your `additionalContext` noting which files need the macro
definition. Surface this advisory to the user before beginning `.tex`
edits.

### Troubleshooting

**`! Undefined control sequence. \tc`.** The preamble is missing or the
file using `\tc{}` does not inherit it. Add `\usepackage{tc}` to the
preamble.

**Compile error involving `\hl` or `soul`.** `soul` is incompatible
with `hyperref` loaded after it, `fontspec` with non-TeX-Gyre fonts
under XeLaTeX/LuaLaTeX, and some highlight packages. Fallback to
`xcolor`-backed definitions:

```latex
\usepackage{xcolor,ulem}
\newcommand{\tc}[1]{\colorbox{yellow}{#1}}
\newcommand{\tcn}[1]{\textsuperscript{#1}}
% \sout already provided by ulem
```

The PreToolUse hook does not distinguish between definitions; it
validates only the wrapper presence and well-formedness.

For per-construct pattern lookup with rendered-output descriptions, see
`reference/highlight-syntax.md` and `reference/latex.md`.

## 11. Audit Log

When tracking is active for a file, a PostToolUse hook appends an entry
to a project-local audit log every time the file is written. The log
captures both AI-introduced marks (when they land) and AI-introduced
marks that the user has since resolved (accepted or rejected).

### Location

`<project-root>/.tc-history.md`

Where `<project-root>` is the first ancestor directory containing a
`.git/` subdirectory (walked up from the edited file). If no git root
is found, the log falls back to the marker's directory; failing that,
the edited file's own directory.

The log file is created with a header on first write. The hook never
truncates or rewrites existing entries — it is **append-only**.

### Format

```markdown
## 2026-05-23T14:32:11Z -- lectures/lecture-3.qmd  (Write)
introduced:
  - mark: 7
    type: insertion
    line: 142
    new: "uniformly "
  - mark: 8
    type: replacement
    line: 144
    old: "continuous"
    new: "monotone"

## 2026-05-23T15:18:04Z -- lectures/lecture-3.qmd  (Edit)
resolved:
  - mark: 7
    was_type: insertion
    decision: accepted
    was_new: "uniformly "
  - mark: 8
    was_type: replacement
    decision: rejected
    was_old: "continuous"
    was_new: "monotone"
```

- `introduced` entries record marks that landed in this edit.
- `resolved` entries record marks that were present before this edit
  but absent after — the user has removed the wrapper.
- `decision` is a best-effort inference based on whether the prior
  `new` or `old` chars still appear in the file. `accepted` /
  `rejected` / `ambiguous` are the possible values.

### Diffable + queryable

Because the log is a committed text file, every git workflow applies:

- **PR review:** the log diff shows the AI-suggested changes in this PR.
- **Time-window queries:** `git log --since=... -p -- .tc-history.md`.
- **Branch comparison:** `git diff main..feature -- .tc-history.md`.
- **Blame:** `git blame .tc-history.md` shows commit-level attribution.
- **Forensic walk-back:** read prior entries to see what was originally
  suggested; reconstruct the prior file state from log + git history.

### What this does and doesn't do

- Captures: every AI suggestion that lands on a tracked file; the
  user's eventual resolution (accept/reject/ambiguous) inferred from
  content.
- Does NOT capture: edits to untracked files; user-direct edits that
  do not involve mark wrappers.
- Does NOT replace git: the log is a supplement to commit history, not
  a substitute for it. The current file content is always the source of
  truth; the log is the trail.

### Cache

The hook maintains a small per-file cache under
`~/.claude/skills/track-changes/state/cache/<sha1>.marks` so it can
detect mark resolution between edits. Cache loss (e.g., fresh install)
degrades the log gracefully: only `introduced` entries are emitted
until the cache rebuilds.

### Resetting the log

Delete `.tc-history.md` to start fresh. The hook will create a new one
with the header on the next tracked edit. This is destructive — the
prior history is lost from the file but remains in git if the file was
committed.
