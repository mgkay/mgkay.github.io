---
name: track-changes
description: Source-preserving edit protocol. Tracks Claude-introduced changes to existing .md, .qmd, and .tex files by wrapping only the changed characters in a <mark> highlight followed by a <sup>N</sup> reference number, so the human author can accept or reject each change individually. Default-OFF; opt in per folder via .tc-tracked marker, per file via YAML frontmatter `tc-track: true` (or `% tc-track: true` for .tex). Per-turn override via /draft. Unified /tc command for all operations (/tc mark, /tc enable, /tc disable, /tc migrate, /tc status, /tc list, /tc accept, /tc reject, /tc draft, /tc import, /tc polish, /tc source, /tc manifest). Edits to tracked files append to a project-local .tc-history.md audit log. Verbatim/converted source import is the separate opt-in verified-import skill (/tc import).
---

# track-changes

The SessionStart hook injects a small **digest** (`reference/digest.md`:
activation rules + mark grammar + `/tc` commands) into context; the full
spec in this `SKILL.md` is lazy-loaded on demand from the digest's
`SKILL.md §N` pointers.

The track-changes skill is **default-off**. It activates for Write, Edit,
and MultiEdit on existing files with extension `.md`, `.qmd`, or `.tex`
only when one of the opt-in mechanisms in §2 is in effect. When active,
the PreToolUse hook blocks any write that adds or removes content without
an appropriate numbered highlight wrapper. When inactive, the hook is
silent and passes through.

track-changes is one of **two co-installed skills**. The always-on
track-changes skill (this file) gates ordinary edits with marks; its
opt-in counterpart **`verified-import`** handles the one deliberate
operation that should *not* be mark-wrapped — pulling content from a
source file into a tracked document via `/tc import` (see §0).

## Quick Install

Two skills install together as one suite: **track-changes** (always-on
mark protocol) and **verified-import** (opt-in `/tc import`, loaded only when
invoked). track-changes is the dependency — verified-import imports its
shared `tc_core`.

Remote install via the bootstrap (4.0.0): from any Claude Code session,
say `Read https://mgkay.github.io/track-changes/bootstrap.md and follow
the installation instructions inside it.` Claude Code downloads both
skills' files and merges **six hook registrations** into
`~/.claude/settings.json` — five for track-changes plus one PreToolUse for
verified-import, stacked **before** track-changes' in a single matcher group
so the two run sequentially and a verified import lands clean. The merge strips
both hook signatures before re-adding, so a re-run is idempotent. See <https://mgkay.github.io/track-changes/> for the
landing page and version history.

Local install (developer path): `bash install.sh` from the project root
installs both skills and merges the same six hooks.

## 0. Importing from a source (the verified-import skill)

When the author asks you to **import** a passage **from a source file**
into a tracked document — rather than write or edit prose yourself — that
is the job of the separate, opt-in **`verified-import`** skill, not the
mark protocol. Invoke it with:

```
/tc import <source>[#L<a>-L<b>] [<target>]
```

`/tc import` reads the source (a whole text file or a `#L<a>-L<b>` line
range), prints it with an instruction to convert it to the target
document's format, and you write the converted block. The block lands
**clean (no `<mark>`)** by default — a `verified-import` PreToolUse hook
writes a one-shot exemption signal this track-changes skill honors, and an
`imported:` entry is appended to `.tc-history.md` (§11). There is **no
mechanical content gate**: you import faithfully and, using your judgment,
wrap only a genuinely *significant* change (an added or removed sentence or
clause, or a changed quantity, term, or formula) in a mark for the author;
pure formatting differences (`\section{Methods}` ↔ `## Methods`) need none.

**Text sources only.** `/tc import` accepts only text sources (`.md`,
`.markdown`, `.qmd`, `.rmd`, `.tex`, `.txt`); a binary/non-text source is
rejected. Converting a Word/PDF/slide original into text is an upstream,
separately reviewed activity — do that conversion first (to a vetted text
file), then `/tc import` from it. See the **verified-import** skill's
`SKILL.md` for the full contract.

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

**Two skills, one suite.** track-changes is the always-on mark-gate for
in-place edits to vetted prose (and any AI-authored glue). Importing
content *from a source file* is the separate opt-in **`verified-import`**
skill (§0), which lands its verified output clean via an exemption this
skill honors. SessionStart injects a compact `reference/digest.md` (mark
rules + `/tc` commands + lazy-load pointers); this full `SKILL.md` is
loaded on demand, so keep its §-numbering stable for the digest's
`SKILL.md §N` references.

## 2. Activation

The skill is **off by default**. It activates per Write/Edit/MultiEdit
according to the following mechanisms, in precedence order (most-local
wins):

1. **`/draft` (per turn).** When the user invokes `/draft` (or `/tc
   draft`), the skill is suspended for the current user turn regardless
   of any other mechanism. Auto-clears at the start of the next user
   prompt.

   > **v7 guarantee — `/draft` is user-only AND shadow-proof.** The
   > UserPromptSubmit hook matches `/draft` on the **raw prompt before
   > command routing**, so a third-party skill named `draft` cannot
   > intercept or shadow it. The sentinel is written exclusively by that
   > hook in response to the human's own prompt; the AI cannot self-suspend.

2. **Per-file YAML frontmatter or magic comment.** A file containing
   `tc-track: true` in its YAML frontmatter is tracked. A file
   containing `tc-track: false` is exempted (overrides folder
   marker). For `.tex` files (no native frontmatter), the equivalent is
   a magic comment in the first 10 lines: `% tc-track: true` or
   `% tc-track: false`. The skill provides `/tc enable <file>` and
   `/tc disable <file>` slash commands so users do not need to hand-edit
   YAML — see §7.

   > **Why `tc-track`, not `track-changes`?** `track-changes` is a
   > reserved Quarto YAML field (Quarto accepts only `accept`/`reject`/`all`
   > there and errors on `true`/`false`), so using it broke every `.qmd`/`.md`
   > render. `tc-track` is an unknown key Quarto passes through untouched.

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
folder. To force-track a hidden file, add `tc-track: true` to its
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

### Batch resolution via `/tc` (§7)

For a file with many marks, the user can resolve them in bulk through the
canonical commands rather than conversational batches:

- `/tc list <file>` — print every mark with its number, type, and a short
  content preview.
- `/tc accept <file> <ranges>` / `/tc reject <file> <ranges>` — resolve a
  set of marks. The range syntax is `1-25,!7,!11`: comma-separated inclusive
  ranges, with `!N` excluding `N`.
- `/tc accept-all <file>` / `/tc reject-all <file>` — resolve every mark.

Batch resolution edits the file directly (accept ⇒ keep the new text and
strip the `<mark>…</mark><sup>N</sup>` wrapper; reject ⇒ restore the old text
and strip the wrapper) and works for `.md` / `.qmd` (`<mark>`) and `.tex`
(`\tc{}\tcn{}`). Each decision is recorded in `.tc-history.md` with
`decision: explicit`, which the best-effort Fix #8 inference never overwrites.

**Committed-content invariant (v7, 2026-07-12).** `accept`/`reject`/
`accept-all`/`reject-all` REFUSE to run if the target file has uncommitted
changes (or is untracked) in its git repo — exit 3 with the required
sequence. Rationale: an open mark is editable right up to resolution, so
without this gate an approval can attach to content the reviewer never read
(observed live: an AI polish correction applied and accepted in one step).
The enforced workflow is therefore: commit the instructor's tweaks as their
own attributable commit; commit any AI corrections as their own MARKED
commit; review the diff(s); then resolve. Marks accumulate across commits
and resolve in batches — that is the intended rhythm, not friction.
`list` is read-only and not gated. `TC_FORCE=1` overrides — **human-only,
never for AI use** (same status as `/draft`). Outside a git repo the gate
is inert (fail-open).

When the **user explicitly** asks to accept/reject marks, prefer these
commands — that is user-authorized execution through the documented surface,
not the prohibited autonomous self-invocation (see §7).

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

## 6. Non-Rendering Contexts

Some constructs do not render `<mark>` or `\tc{}` inside them — fenced
code, display math, YAML front matter, GFM tables, LaTeX verbatim, math
environments, tabular. v3 handles them in exactly two ways: a sibling
mark for a **brand-new** Markdown/Quarto block, and `/draft` for
everything else (editing *inside* an existing construct, or adding a
brand-new LaTeX block).

### Brand-new Markdown/Quarto block (block-sibling form)

Adding a **brand-new** block-level element — an ATX heading, a fenced
code block, or a `::: {...}` Quarto div — would otherwise break the
protocol: `### Foo` must sit at column 0 to parse (so `<mark>### Foo</mark>`
breaks the heading), and wrapping a ```` ``` ```` / `:::` delimiter line in
`<mark>` breaks the fence/div. The **block-sibling form** covers this case:
put one `<mark>…</mark><sup>N</sup>` on the line immediately above the new
block, then write the block normally. The hook accepts the new block's
delimiter lines (and the heading line) as covered by that sibling mark — no
`/draft` needed.

```markdown
<mark>New subsection: Wider tables demo</mark><sup>1</sup>
### Wider tables

<mark>New column-body-outset breakout</mark><sup>2</sup>
::: {.column-body-outset}
| ... wide table ... |
:::
```

Multiple new blocks → one sibling line each, no blank line between the
sibling and the opener it covers.

**Markdown/Quarto only.** The block-sibling form covers brand-new
`.md`/`.qmd` headings, fenced-code blocks, and `:::` divs. A brand-new
LaTeX block — `\section{}`, an `equation`/`align`/`tabular`/`verbatim`
environment — is **not** auto-covered; route it to `/draft` (see below).

This applies only to a *newly added* heading/block. Editing the text of an
*existing* heading follows the normal inline rule (wrap the changed
characters: `## <mark><s>Old</s>New</mark><sup>N</sup> Section`).

### Editing inside a construct, or a new LaTeX block → `/draft`

v3 has **no sibling escape hatch for editing inside an existing
non-rendering construct.** A change inside a fenced-code block, display
math, GFM table, YAML front matter, or any LaTeX environment — and any
brand-new LaTeX block (`\section{}`, environments) — cannot be inline-
wrapped without breaking the construct, and the in-construct sibling
mechanism was removed in v3. The hook blocks such an unwrapped change as
ordinary unwrapped content and suggests `/draft`. When you must make one
of these edits:

1. Ask the user to invoke `/draft` for the current turn.
2. Make the edit without a highlight wrapper.
3. Note the edit in your reply so the user can review it without the
   numbered-mark scaffolding.

This is a documented v3 limitation (the v2 in-construct sibling form was
dropped to simplify the analyzer).

## 7. Slash Commands

The skill installs a single unified `/tc` command with subcommands, plus
`/draft` as a direct alias for the per-turn override.

### Unified `/tc`

| Subcommand | Effect |
|------------|--------|
| `/tc draft` | suspend tracking for the current turn only |
| `/tc enable <file>` | add `tc-track: true` to the file's YAML (or `% tc-track: true` magic comment for `.tex`) |
| `/tc disable <file>` | add `tc-track: false` (per-file opt-out) |
| `/tc mark [<dir>]` | drop a presence-only `.tc-tracked` marker in `<dir>` (tracks ALL files in that folder; default `<dir>` = current directory) |
| `/tc mark <dir> <file1> [<file2>...]` | drop a list-mode `.tc-tracked` marker that tracks only the listed basenames in `<dir>` |
| `/tc migrate <dir>` | run v1 → v2 mark migration on all `.md`/`.qmd`/`.tex` files under `<dir>` |
| `/tc status [<file>]` | print the activation chain for `<file>` (or the working file / current directory) |
| `/tc list [<file>]` | list every mark in `<file>` with its number, type, and a short content preview |
| `/tc accept [<file>] <ranges>` | accept the listed marks (keep new text, strip the wrapper); range syntax `1-25,!7,!11` |
| `/tc reject [<file>] <ranges>` | reject the listed marks (restore old text, strip the wrapper) |
| `/tc accept-all [<file>]` / `/tc reject-all [<file>]` | resolve every mark |
| `/tc help` | show the subcommand list |

For the resolution subcommands (`list`/`accept`/`reject`/`accept-all`/
`reject-all`) and `status`, omitting `<file>` resolves the **working
file** — the most-recently-modified tracked file under the project (git
root, else current directory) — and the command echoes the chosen file.
`/tc enable` and `/tc disable` always require an explicit `<file>`. See §3
"Batch resolution via `/tc`" for the resolution behavior and `commands/tc.md`
for the full surface.

### Importing via `/tc import`

`/tc import` **is** a `/tc` subcommand (added in v7). It routes to the
opt-in **`verified-import`** skill (`/tc import <source>[#L<a>-L<b>]
[<target>]`, §0). Its verified output lands clean (no marks) via an
exemption this skill honors. Importing is still a **distinct operation**
from inline marks — verified-import owns the implementation; `/tc import`
is the dispatch surface.

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

- For `.md` and `.qmd`: add or update the `tc-track:` key in the
  top-of-file YAML frontmatter. If no frontmatter block exists, prepend
  a fresh `---` ... `---` block containing only the `track-changes` key.
- For `.tex`: add or update a `% tc-track: <value>` magic comment
  in the first 10 lines. If none exists, prepend it as line 1.

These are the only file modifications the skill performs outside of
edit-time hook validation. Both are idempotent — re-running with the
same value is a no-op.

`/tc mark` (no filename args) drops a presence-only marker. `/tc mark`
with one or more filename args after `<dir>` drops a list-mode marker
naming only those basenames. The marker-writing logic lives in
`lib/tc-mark.sh`, which the `/tc mark` CLI sources and runs directly (it
no longer shells out to `install.sh`).

### How to use these as Claude

You should **not** invoke `/tc draft`, `/tc enable`, `/tc disable`,
`/tc mark`, `/tc migrate`, or `/draft` on your own behalf. They are
deliberate user actions. If you encounter a situation where the skill
is creating friction (the hook blocks an edit you believe should land,
or the user is editing a file that would benefit from tracking),
surface the problem in your reply and suggest the appropriate command.
Wait for the user's next prompt.

For most commands the rule prohibits **autonomous** self-invocation but
not **user-authorized** execution: when the user explicitly directs an
action — "enable tracking on all the `.qmd` files here", "accept marks
1–10 and reject 11" — routing through the canonical `/tc` command
(`/tc enable`, `/tc mark`, `/tc accept|reject`) is the correct path; it
exercises the documented surface and keeps the audit honest.

**`/draft` is the exception — it is USER-ONLY and you cannot invoke it at
all (v6, Fix B).** Authorization and verification are two separate gates
that BOTH always hold: being *authorized to act* ("go ahead, add the
example") never means your output skips tracking. **Everything you write
into a tracked deliverable is tracked, regardless of approval** — there is
no "the approval is the audit trail." Suspension is the user's lever only:
the `/draft` sentinel is written exclusively by the UserPromptSubmit hook
when the *human's own prompt* requests it, and the gate honors only a
sentinel carrying its authorized marker. Running `lib/draft-on.sh`
yourself does nothing (it no longer writes a sentinel). If you believe
some content should land untracked, **ask the user to `/draft`** — do not
attempt to arrange it. For your own authored content the honest paths are
a `<mark>` edit, a whole-region insertion (§Region), or `/tc import` for
verbatim source.

## 8. Composition with PCV

PCV Builder subagents that modify existing tracked files are subject to
the skill. New-file creation passes through (file doesn't exist on
disk; hook skips).

When a Builder modifies existing `.md`, `.qmd`, or `.tex` files in a
tracked project, its writes are tracked like any other — a Builder is the
AI and **cannot suspend tracking for itself** (v6, Fix B). If the user
wants a Builder turn to land untracked, the **user** types `/draft` as
their own prompt (the per-turn suspension; the next user turn restores the
default). The Builder should otherwise wrap new content as `<mark>` edits
or a whole-region insertion (§Region) — the region mode exists precisely so
a large new block lands as one tracked unit without anyone reaching for
`/draft`. (There is no session-scope toggle — `/track-on`/`/track-off`
were removed in Fix #6; `/tc disable <file>` gives a durable per-file
opt-out, a user action.)

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
# Per-file opt-out:  add `tc-track: false` to YAML frontmatter
#                    (or `% tc-track: false` near the top for .tex).
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
- `imported` entries (a clean, unmarked source import) are **not**
  produced by this skill's edit gate — they are appended by the
  **`verified-import`** hook when a `/tc import` write lands clean
  (§0). They share the same `.tc-history.md` log so the import trail
  rides alongside the mark trail in git history.

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

## 12. Render-time visibility of marks

Marks render as visible yellow highlights with superscript numbers in the
output HTML. If a document is shared before its marks are resolved (faculty
meeting, student preview, PR review by a non-author), everyone sees the
marks — not always desired. The skill ships two optional render-time assets
that hide marks at *view* time without mutating the source:

- `reference/tc-clean.css` — supplies the **whole-region** styling (the
  `.tc-region` change-bar / tint / margin number, §15) **and** the `no-marks`
  hiding rules: when `<body>` carries the `no-marks` class, `<mark>` highlights
  become transparent (text reads as plain prose) and the trailing `<sup>N</sup>`
  is hidden.
- `reference/tc-clean.js` — adds the `no-marks` class to `<body>` when the
  URL carries `?clean=1` (or a bare `?clean`).

**Inline marks vs. regions — what needs the CSS.** Inline `<mark>` highlights
show yellow with *no* CSS (browsers style `<mark>` by default), so they render
even if you include nothing. A **whole-region insertion** (§15) renders as a
container with the `.tc-region` class and has **no default styling** — it is
invisible (no bar, no number) unless `tc-clean.css` is actually included. If a
region "tracked silently but shows no highlight," the CSS was not wired in.

**Quarto emits `data-`-prefixed attributes.** Pandoc renders the fenced-div
key–value attributes as `data-`-prefixed HTML attributes —
`::: {.tc-region tc-n="1" tc-prov="authored"}` becomes
`<section class="… tc-region" data-tc-n="1" data-tc-prov="authored">`. The
shipped `tc-clean.css` already targets both the `data-tc-n` / `data-tc-prov`
forms (for Quarto render) and the raw `tc-n` / `tc-prov` forms (hand-written
HTML), so the margin number and imported-provenance color bind either way.

Include both assets in the rendered HTML, then append `?clean=1` to the URL when
sharing mid-review. For a Quarto HTML document, prefer **`include-in-header:
text:`** with a raw `<style>` — it is **purge-safe** (theme SCSS can drop rules
for unknown classes like `.tc-region`, but a raw header `<style>` survives):

```yaml
format:
  html:
    include-in-header:
      text: |
        <style>
        /* paste reference/tc-clean.css here, or: */
        @import url("tc-clean.css");
        </style>
    include-after-body:
      text: |
        <script src="tc-clean.js"></script>
```

The simpler `css: tc-clean.css` also works for non-theme projects, but the
header-`<style>` path is the robust default. (Copy the two files from
`~/.claude/skills/track-changes/reference/` into the project, or reference them
by path.) Removing `?clean=1` — or loading the page without it — restores the
marks unchanged. This is purely a viewing concern; the source file and its
marks are never altered.

## 13. Common pitfalls

- **Windows `/draft` sentinel (concurrency).** `/draft` writes a sentinel via
  the skill's own bash (`lib/draft-on.sh`), so activation no longer depends on
  a user-supplied shell snippet. When `$CLAUDE_SESSION_ID` is unset (common on
  Windows / cross-shell), it falls back to a shared `state/default.draft`
  sentinel; both the activation gate and the clearing hooks (UserPromptSubmit,
  SessionStart TTL) honor that path in addition to the session-specific one.
  **Limitation:** `default.draft` is shared across any concurrent sessions
  that also lack a distinct `$CLAUDE_SESSION_ID` — in that rare case one
  session's `/draft` suspends tracking for the others until the next user turn
  clears it (or the 1-hour SessionStart TTL sweep removes a stale sentinel).
  Sessions that expose a distinct session id are unaffected.
- **New Markdown/Quarto block-level elements.** Adding a brand-new heading,
  fenced code block, or `:::` div in a `.md`/`.qmd` file uses the block-sibling
  form (§6), not inline wrapping or `/draft`. (A brand-new LaTeX block is
  different — see below.)
- **Editing inside a construct, or a new LaTeX block → `/draft`.** v3 has no
  sibling escape hatch for editing *inside* an existing non-rendering construct
  (fenced code, display math, GFM table, YAML, any LaTeX environment), nor for
  a brand-new LaTeX `\section{}`/environment. Those edits route to `/draft`
  (§6) — the hook blocks an unwrapped change and suggests it. This is a
  documented v3 limitation (the v2 in-construct sibling form was removed).
- **Importing from a source → `/tc import`, not a mark.** Pulling content from a
  source file into a tracked document is the separate **`verified-import`**
  skill (§0), which lands the verified block clean. Do not hand-wrap an import
  in marks, and do not `/draft` it (that loses verification and marks on the
  surrounding glue).
- **Quarto feature interactions.** Code annotations don't combine with
  `lst-cap`; annotations mis-pair with executable chunks that print to stdout;
  hover previews / lightbox / code-annotation require serving over `http://`
  (not `file://`). The skill's own `?clean=1` toggle has no `file://`
  restriction. Full diagnostics in `reference/quarto-notes.md`.
- **Render-time sharing.** Use `?clean=1` (§12) to hide marks when sharing a
  document mid-review, instead of resolving prematurely. The CSS/JS assets are
  `reference/tc-clean.css` / `reference/tc-clean.js`.

## 14. Author workflow recipe

The protocol (§3–§6) and the audit log (§11) are well documented; the
workflow *around* them is implicit. A typical tracked-revision session runs:

1. **Author asks for a revision.** The author opts the file in (folder
   `.tc-tracked` marker via `/tc mark`, or per-file `/tc enable <file>`), then
   asks Claude for the edit in plain language — "tighten the intro", "modernize
   this example". To pull a passage *from a source file*, the author uses the
   separate `/tc import` command (§0, the verified-import skill).
2. **Claude lands marks.** Claude edits the file, wrapping only the changed
   characters in `<mark>…</mark><sup>N</sup>` (`.md`/`.qmd`) or
   `\tc{}\tcn{N}` (`.tex`). The PreToolUse hook blocks any unmarked change.
   Each landed mark is recorded as `introduced` in `.tc-history.md`. A verified
   `/tc import` (§0) is the exception: that block lands clean (no marks) and is
   recorded as `imported`.
3. **Author batch-resolves.** The author reviews the highlighted output and
   resolves in bulk through the canonical commands rather than a conversational
   batch:

   ```
   /tc list   lec-3.qmd            # see every mark + a content preview
   /tc accept lec-3.qmd 1-25,!7,!11 # accept 1–25 except 7 and 11
   /tc reject lec-3.qmd 7,11        # reject the rest
   ```

   Accept keeps the new text and strips the wrapper; reject restores the old
   text and strips the wrapper. (See §3 "Batch resolution via `/tc`".)
4. **Audit entry.** Each resolution appends a `resolved:` block with
   `decision: explicit` to `.tc-history.md` — an explicit human choice the
   best-effort Fix #8 inference will never overwrite.
5. **Commit.** The resolved file and the updated `.tc-history.md` are committed
   together, so the audit trail rides along in git history. The optional
   pre-commit hook (`hooks/pre-commit.sh`) can warn if marks are still
   outstanding at commit time.

To share a document **before** marks are resolved (faculty meeting, student
preview, non-author PR review), use `?clean=1` (§12) instead of resolving
prematurely.

## 15. Region insertion, provenance, and `/draft` (v6)

**`/draft` is user-only and cannot be self-invoked (Fix B).** It suspends
tracking for **the current user turn only** — but the suspension sentinel is
written *exclusively* by the UserPromptSubmit hook when the **human's own
prompt** requests it (and the gate honors only a sentinel carrying its
authorized marker). The AI cannot suspend its own tracking; `lib/draft-on.sh`
no longer writes anything. Tracking auto-resumes next user prompt.

Authorization and verification are separate gates that both always hold: being
told to do something never lets your output skip tracking. **Every change you
write into a tracked deliverable lands as a mark, a whole-region insertion, or a
verified `/tc import` — never plain untracked text.** Pick the path by what the
content *is*, mechanically, not by whether you were "approved":

- **Whole-region insertion (Fix D) — the path for a large new block.** A
  multi-block new region (heading + prose + `:::` div + fenced code, or several
  paragraphs) marks as **one** tracked insertion instead of a mark on every line.
  - md/qmd: wrap it in a fenced div
    `::: {.tc-region tc-n="N" tc-prov="authored"}` … `:::` — the whole region is
    highlighted as one unit, `/tc accept|reject N` resolves it atomically.
  - LaTeX: `\begin{tcregion}{N}[authored]` … `\end{tcregion}` — a colored left
    change-bar spans the region (this replaces the old "new LaTeX block →
    `/draft`" routing). Do **not** put inline marks inside a region — it is one
    atomic unit.
  This is what makes large first-pass content land tracked without anyone
  reaching for `/draft`.
- **Inline `<mark>` / `\tc{}`** when **refining** vetted content — each change
  individually reviewable.
- **`/tc import` (verified-import, §0)** for content lifted **verbatim from a source
  file**: it lands clean (attributed, typed `imported`) via an exemption this
  skill honors; you self-mark only significant changes. Verbatim is a mechanical
  operation the tool proves — never hand-type content and call it "from your
  material."

**Provenance (Fix E; extended v7, v9).** A mark or region carries an optional
provenance type: `tc-prov="authored"` (default — anything you
wrote/paraphrased), `tc-prov="imported"` (a verbatim `/tc import` slice),
`tc-prov="transcript"` (v7 — AI wording over the instructor's own spoken
class-recording transcript content: the ideas are the instructor's, the
sentences are the AI's, so it reviews between imported and authored in
scrutiny), or `tc-prov="sourced"` (v9 — AI text supported by a *document*
source, carrying a `tc-src` binding and verified against a gray verbatim
excerpt; see §16). Each provenance renders in a distinct color so the reviewer
can skim the verbatim parts and scrutinize the authored ones. Absent ⇒ authored
(every pre-v6 mark reads as authored). The grammar
(`lib/tc_core/grammar.py PROV_VALUES`) recognizes all four; resolution
commands (`accept`/`reject`/`list`) treat regions identically regardless of
provenance. A transcript or sourced region is conventionally preceded by a
TEMPORARY gray `.tc-verbatim` block quoting the raw source for side-by-side
confirmation — `.tc-verbatim` is scaffolding, not a tracked region:
resolution commands ignore it, and it is deleted by hand once its region is
accepted (a conversion's definition-of-done should gate on none remaining).
For the mechanically-verified `sourced` discipline (staging, the write-time
excerpt check, and the evidence manifest), see §16.

**The corpus-example rule (standing convention).** Worked examples lifted from
the spreadsheet/MATLAB corpus have mixed, predictable provenance: the
**scenario / statement / data** is lifted → `/tc import` (clean, `imported`); the
**Julia code is a re-implementation → new → tracked** (a region or marks,
`authored`); **AI prose → new → tracked**. So by default: *import the scenario,
track the Julia as new.* This is automatic — do not relitigate it per example.

## 16. Source-validation discipline (v9)

The transcript gray/green convention (§15) generalizes in v9 to arbitrary
**document sources**. When AI-written text is *supported by* a document — a
chapter PDF, a prior manuscript, a Word draft, a cited reference — it lands as
a green **`sourced`** region, and the supporting quotation appears beside it as
a temporary **gray `.tc-verbatim` block that is verbatim by construction**. A
`/tc source` staging command plus the always-on write-time hook mechanically
guarantee the gray block quotes the real source; a fabricated or paraphrased
excerpt is refused fail-closed. The gray/green split keeps the reviewable
authored interpretation (green) cleanly separated from the raw evidence (gray),
and makes "does this claim actually rest on the source?" a mechanical check
rather than a matter of trust.

### The `/tc source` flow

Stage the source, then write one edit pairing the two blocks:

```
/tc source <file>#<locator> [<target>]        # path form
/tc source @citekey [<locator>] [<target>]    # BibTeX-citekey form
```

The locator is `L<a>-L<b>` (text lines), `p.<a>[-<b>]` (PDF pages), or absent
(the whole source). `<file>` sources may be text (`.md`/`.qmd`/`.tex`/`.txt`),
`.pdf` (PyMuPDF), or `.docx` (python-docx). An `@citekey` resolves via the
document's `.bib` `file`/`localfile` field or a `.tc-sources.json` map (§F5;
unresolvable keys fail closed, naming both mechanisms). `<target>` defaults to
the working file.

`/tc source` prints the resolved slice together with the exact block shapes to
write. In `.md`/`.qmd`:

```
::: {.tc-verbatim tc-cite="<src>"}
<the exact quotation, copied verbatim from the slice>
:::

::: {.tc-region tc-n="N" tc-prov="sourced" tc-src="<src>"}
<your sourced prose, supported by the quotation above>
:::
```

In `.tex`:

```latex
\begin{tcverbatim}{<src>}
<the exact quotation, copied verbatim from the slice>
\end{tcverbatim}

\begin{tcregion}{N}[sourced][<src>]
<your sourced prose, supported by the quotation above>
\end{tcregion}
```

`N` is the next free mark number. `<src>` is the canonical `tc-src` value the
CLI prints for that staging — `path#locator` (or bare `path` for a whole
source), or `@citekey locator` (or bare `@citekey`) — and it must be copied
**verbatim** into the green region opener.

### The mechanical guarantee (what the hook refuses)

On the write that adds the gray+green pair, the track-changes PreToolUse hook
re-reads the staged source and enforces, fail-closed:

- a gray `.tc-verbatim` block with **no live `/tc source` staging** → blocked
  ("gray excerpt requires `/tc source` staging"). The fabricated-excerpt back
  door stays closed even for a hand-typed gray block.
- a gray block whose normalized text is **not contained** in the staged source
  slice → blocked, naming the first divergent fragment; the staging is
  preserved for a corrected retry. Containment is **normalized-exact** (Unicode
  NFKC fold, soft hyphens dropped, hyphen-linebreak splits joined, whitespace
  runs collapsed; case preserved), so an honest PDF excerpt spanning a line
  break passes while a paraphrase does not.
- **more than one** gray block in a single write → blocked (stage and write one
  source at a time; run `/tc source` again for the next).
- a green `sourced` region **missing `tc-src`, or carrying a `tc-src` different
  from the staged value** → blocked, with the expected value named.
- a **scanned/image PDF** (empty text layer) or otherwise unreadable source →
  refused at staging time with a named message; the discipline never guesses.

On success the hook writes a one-shot sentinel that covers exactly the gray
scaffolding for this write (the green region stays governed by the normal
region grammar), appends a `sourced:` entry to `.tc-history.md` (region `N`,
target, source, locator, verbatim excerpt, supported text, timestamp), and
clears the staging. A later AI edit *inside* a gray block is new added content
requiring a fresh staging; a hand edit by the author is human content, outside
the gate.

### Always-cited and always-verified (9.1.0)

`tc-prov="sourced"` is not only verified against its excerpt; it must also be
**attributed in the document itself**. Two invariants hold, enforced at the
write:

- **Always-verified (pairing).** The gate now triggers on a new gray
  `.tc-verbatim` excerpt **or** a touched `sourced` region, and a brand-new
  `sourced` region and its verified gray excerpt must land as **one pair**. A
  `sourced` region can no longer bypass verification by omitting the excerpt —
  a lone `sourced` region with no staged gray block is refused (exit 2). This
  closes the earlier hole where a `sourced` region added without a gray excerpt
  landed as an ordinary tracked region.
- **Always-cited.** The surviving green region must carry a **reader-facing
  citation** in its body:
  - **Rule A (citekey binding).** When the source was staged by `@citekey`
    (`/tc source @daskin2013 …`), the region must cite **that exact key** —
    `[@daskin2013]` in `.md`/`.qmd`, `\cite{…daskin2013…}` (any `\cite`-family
    command) in `.tex`.
  - **Rule B (general token).** Otherwise (path-staged), the region must contain
    at least one citation/footnote token for the file type: `.md`/`.qmd` —
    `[@key]` / `@key` / a Pandoc footnote (`^[…]` inline or `[^ref]`
    reference); `.tex` — any `\cite`/`\citep`/`\citet`/`\autocite`/`\parencite`/
    `\textcite`/`\footcite`/… command or `\footnote{`.

A citation that **renders nothing to a reader does not count**: a token inside a
code span or fence, inside an HTML or LaTeX comment, or inside a
`verbatim`/`\verb` context is ignored (`\nocite`, which registers a key but
prints nothing, is likewise excluded). Editing an already-present `sourced`
region needs no re-staging, but the edit **must keep a citation** — a confirmed
sourced passage cannot be edited into an unattributed one. On any failure the
write is blocked (exit 2), the staging record is preserved, and the message
names the exact expected key (Rule A) or the accepted citation forms (Rule B).

The point is that `tc-src` is **invisible provenance metadata**, stripped on
`/tc accept` — it is not a citation a reader can follow. After acceptance the
green wrapper and the gray scaffolding are gone; only the document's own
citation remains as the durable attribution. Enforcement (not prompting) is what
makes this hold when an AI agent does the authoring.

### Quotation vs. interpretation — the boundary

A green `sourced` region is for **AI-authored interpretation, paraphrase, or
synthesis** that leans on a source, and that interpretation **must itself carry
a citation** a reader can follow (Rule A/Rule B above) — the source-grounding is
not complete until the claim is attributed in the document. It is **not** a place
to park a quotation that is meant to *stay* in the document. Two cases sit
outside the discipline:

- An exact quotation the author wants to **keep** in the finished text is
  ordinary **quoted text with a citation** — write it as a normal `<mark>` edit
  (or under `/draft`), not as a green region. The gray block is transient
  scaffolding; do not use it for durable quotations.
- Lifting a **verbatim block from a source file** into the document (a slide's
  scenario, a prior section) is the separate **`/tc import`** operation (§0),
  which lands the block clean. `sourced` is for *your words supported by* the
  source, `imported` is for *the source's words placed into* the document.

### Gray lifecycle and the durable record

The gray `.tc-verbatim` block is **transient scaffolding** — it exists so the
green interpretation can be confirmed against the evidence side by side. Once
the green region is confirmed, delete the gray block. Deletion timing is a
**per-project policy**: for lecture notes, delete each gray block as its region
is confirmed; for a manuscript, keep the gray blocks through internal review
and strip them at submission. **Deleting a gray block never loses evidence** —
the `sourced:` audit entry in `.tc-history.md` is durable, and the manifest
below regenerates the full excerpt-and-support record from it on demand.

### `/tc manifest` and the `validation/` folder

`/tc manifest [<doc>]` regenerates `<doc-dir>/validation/<stem>.sources.md`
whole-file and deterministically from the `sourced:` audit entries — one
section per sourced region (source + locator as a relative link, verbatim
excerpt, supported text, a link back to the region), plus a "Resolved/removed
regions" list for entries whose region no longer exists in the document. The
manifest is **machine-generated evidence, never model-reconstructed** — do not
hand-edit it; re-run `/tc manifest` after resolving or removing regions. The
companion tool `tools/annotate_source_pdf.py` reads a document's audit entries
(or a `validation/*.sources.md` manifest) and, per source, writes an annotated
PDF **twin** under `validation/` with each verified excerpt highlighted and a
regenerated summary page — it never touches the original, reports every
unmatched excerpt (nonzero exit), and skips an image-only PDF with a clear
"no text layer" message. Committing `validation/` is per-project policy.

### Privacy note (F7)

Source excerpts and the manifests that quote them can carry material from
publisher PDFs or unpublished drafts, so keep the `validation/` folder in a
**private evidence location** — `.gitignore` it (or commit it only to a private
repo), never fold it into a public or anonymized hand-off. The `tc-src`
attributes embedded in the document itself point at local source paths and
citekeys; before an **anonymous submission**, strip them with a single
one-pass search-replace over `tc-src="…"` (and the LaTeX `[<src>]` region
argument). This is a documented per-project step, like the gray-deletion
timing above — there is no v9 mechanism that does it automatically.

## Companion tool: `decap` (author-side dictation pre-clean)

> **Apply `decap` ONLY to fresh, unmarked dictation — never to a selection
> containing `<mark>`/`\tc{}`; it is regex over raw text and will corrupt
> mark syntax.**

`decap` ships with the suite at
`~/.claude/skills/track-changes/tools/decap.py` (with protect-list
`decap_protect.txt` in the same directory). It is a deterministic stdin→stdout
text filter that removes the extraneous mid-sentence capitalization voice
dictation introduces. It runs **entirely in your editor** as a selection
filter — Claude Code is never involved and the track-changes hook never fires.
It is **inherently untracked by design**: the PreToolUse hook triggers only on
Claude's Write/Edit/MultiEdit calls; an editor selection filter bypasses it.
And it *should* be untracked — marks review AI judgment; decap exercises none
(mechanical normalization of your own dictation, no different from an
autocorrect pass you run yourself).

**Rule.** A word's leading capital is lowercased unless the word is
sentence-initial, in the protect-list, ALL-CAPS (acronym), camelCase, a
single letter, or "I" / its contractions ("I've", "I'll", etc.).

**Composition with `/tc polish`.** The two tools compose cleanly in sequence:
run `decap` on fresh dictation first (fast untracked mechanical pass, in-editor),
then ask Claude to `/tc polish` the cleaned prose (deeper editorial pass,
reviewable marks). Run `decap` before the text carries any marks.

**Protect-list.** `decap_protect.txt` lives next to the script at
`~/.claude/skills/track-changes/tools/decap_protect.txt`. One term per line;
any listed term is never lowercased regardless of position. The default list
seeds broadly-useful entries (Claude, Anthropic, Quarto, Excel, Wikipedia).
**Add your project's proper nouns and mixed-case acronyms here** — the file is
plain text, editable directly.

### VS Code setup

The filter runs through a VS Code extension that pipes the current selection
through a shell command and replaces it with the output — for example
**Edit with Shell Command** (`ryu1kn.edit-with-shell`). After installing it,
register decap as a favorite command in `settings.json`:

```json
"editWithShell.favoriteCommands": [
  { "id": "decap", "command": "python ~/.claude/skills/track-changes/tools/decap.py" }
],
"editWithShell.quickCommand1": "decap"
```

then bind it in `keybindings.json` (`Ctrl+Shift+P` → *Open Keyboard Shortcuts (JSON)*):

```json
{ "key": "ctrl+alt+c", "command": "editWithShell.runQuickCommand1", "when": "editorTextFocus" }
```

Select the fresh, unmarked text and press `Ctrl+Alt+C` — the selection is piped
through `decap.py` and replaced in place. (On Windows the extension may need the
full path, e.g. `python C:\Users\<you>\.claude\skills\track-changes\tools\decap.py`,
if it does not expand `~`.)

Or just ask Claude Code to set this up for you: it can install the extension
(`code --install-extension ryu1kn.edit-with-shell`) and add the two config
blocks above.

Any extension that filters a selection through a shell command (stdin → stdout →
replace) works; the command and binding names will differ.

### Editor-agnostic

The core is plain `stdin → stdout` — any editor that can filter a selection
through a shell command works:

- **Vim** (visual selection): `:'<,'>!python ~/.claude/skills/track-changes/tools/decap.py`
- **Emacs** (region): `M-| python ~/.claude/skills/track-changes/tools/decap.py RET`
