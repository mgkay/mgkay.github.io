# `/tc edits` — report what the author changed, and resolve what they edited

*(9.9.0 Phase A; 9.9.3 frictions; 10.0.0 Phase B — `resolve`)*

*Reference for the `/tc edits` subcommand of `track-changes`. Lazy-loaded; `SKILL.md §17` is the summary.*

`/tc edits` serves the review loop the author actually uses: **open the document,
edit the prose until it reads right, then have the AI check the edit** — rather
than dictating every correction and having the AI apply it.

The protocol already blessed that loop in prose ("hand-tweak, then AI-verified
accept") but had no tooling for it. Every instance cost a manual `git diff`, a
manual proofread, a `/draft` round-trip, and hand-applied fixes — and dictation-grade
errors (`dimesional`, `is might be`, a missing verb) still reached the file.

## What it does

```
/tc edits <file>
```

1. **Diffs** the file against a snapshot of *the file as the AI last left it*.
2. **Reports the edited spans** — line ranges, added/removed counts, and whether
   each span is a real content change or whitespace-only.
3. **Runs tc-polish's mechanical scan** scoped to those spans (`--baseline-file`, so
   polish's own dictated-scope machinery works against the snapshot instead of git),
   and reports the **`protected:`** line — tokens the model must *leave alone*
   (domain jargon, code, math).
4. **Runs the project's linter** over the file and reports only the findings that
   land *inside* the edit.
5. **Reports any tracked region** an edited span overlaps.
6. **Reports the next free mark number.**
7. **States that nothing has been proofread** (`NOT PROOFREAD`), whenever there is at
   least one content span.

It **does not edit the document.** The model then writes corrections as ordinary
`<mark>…</mark><sup>N</sup>` marks, which land through the always-on PreToolUse gate
like any other AI edit and are reviewed with `/tc accept` / `/tc reject`.

**Every line of the report is MECHANICAL, and the last line says so (9.11.1).**
Nothing above `NOT PROOFREAD` is a reading of the prose: the spans say what moved,
`protected:` says what not to touch, the region and lint lines say what was hit. The
proofread is the model reading the span diffs — *this* invocation, not a later one.

`protected:` was called `polish:` through 9.11.0, and its empty branch printed
`nothing flagged in the edited text`. Its only payload was and is the protected-token
set, so that meant *"no un-correctable tokens"* and read as *"no errors found"* —
measured on prose carrying a doubled `the` and `weights is` for `weights are`, which
a mechanical scan does not and cannot catch. The line also pointed at `/tc polish`
"for the full editorial pass", sending the reader away at the moment the pass should
be starting. **`protected: none` means nothing needed protecting, never that nothing
needed fixing.**

## The one rule for the model

**The author's own text lands CLEAN. Only YOUR corrections get marks.**

An edited span is the *author's* writing. It is not AI-authored content and must
never be wrapped in a mark or a `tc-prov="authored"` region — doing so would
misattribute the author's prose to the AI and defeat the entire point of the color
system. What gets a mark is the *correction you propose to it*, wrapped so it shows
exactly which characters you changed:

```
tes<mark>ted</mark><sup>62</sup>            insertion
<mark><s>dimesional</s>dimensional</mark><sup>63</sup>   replacement
```

Nothing outside the reported spans is touched.

**When the author's OWN text contains a defect (9.9.3).** The rule above says never
to *mark* their prose; it does not say to leave an error standing. The convention:

- **Unambiguous mechanical errors** — a misspelling, an obvious typo, a doubled
  word — are corrected as ordinary marks, exactly like any other AI correction. The
  mark shows precisely which characters changed, so the author can reject it in one
  gesture if they disagree.
- **Anything touching meaning** — a claim that now reads oddly, a redundancy the
  rewrite introduced, a number that looks wrong — is **flagged in conversation and
  held**, never silently edited. The author decides.

The line is whether a competent copy-editor could make the change without knowing
what the author meant.

## Where it sits in the sequence

```
edit  →  /tc edits  →  review the new marks  →  /tc accept  →  commit / render
```

`/tc edits` is **not** a substitute for a project's own checkpoint command. A
checkpoint (regenerate, render, commit, push) does not polish and does not lint at
authorship time; that is exactly the gap this fills.

## The baseline (why a snapshot, not git)

During a review session the working tree is dirty with **both** the author's edits
and the AI's, in one diff that git cannot separate. So track-changes captures the
baseline directly: its PostToolUse hook fires on every AI write to a tracked file —
including `/draft` writes, which the audit log never sees — and stores the file's
exact bytes in a per-user side-store. The hook does **not** fire for the author's
IDE edits, so the snapshot is precisely "state as of the last AI write."

No user action, no commit prerequisite, no `--begin` command. Three generations are
kept per file, which also makes the store an undo buffer:

```
/tc edits snapshots <file>          list the stored generations
/tc edits restore <file> [--gen N]  show the diff; --yes to actually restore
```

### Two limits, stated plainly

**Absorption.** The snapshot is the file *at the moment of the last AI write*. If
you edit and then have the AI write something else before running `/tc edits`, your
edits are absorbed into the baseline and the diff comes back empty. The command
detects this — an empty diff while the file is uncommitted, or while the previous
snapshot generation differs — and tells you to re-run with `--gen 1` or
`--baseline git`. Run `/tc edits` **before** asking the AI for anything else.

**Editor reformatting.** An on-save formatter (footnote renumbering, inline→reference
conversion, fence normalization) runs *after* the snapshot, so its changes appear in
the diff as if you made them. This is noise, not corruption — your real edits are
still there. Spans whose text is unchanged after collapsing whitespace are labelled
`whitespace-only` so pure reflow stays visibly separate from content.

**Cold start.** On a fresh clone there is no snapshot; the command falls back to git
HEAD and **says so**, because HEAD cannot separate your edits from the AI's.

## The project linter (optional)

Conventions are project-specific and this skill is published for anyone, so the
skill supplies the mechanism and the project supplies the rules. Put a
`.tc-edits.json` at your repository root (or beside the document — repo root wins
when both exist):

```json
{
  "lint": {
    "command": ["python", "tools/lint_lecture.py", "{file}"],
    "cwd": ".",
    "line_pattern": "(?P<file>[^\\s:]+):(?P<line>\\d+)",
    "timeout": 120
  }
}
```

- `{file}` is replaced with the document's path; `cwd` is relative to the config.
- `line_pattern` parses each output line. The default matches the near-universal
  `path:line` convention (gcc, ruff, eslint, mypy, shellcheck). A `file` group, when
  present, must match the document's basename, so a multi-file linter's findings for
  other files are counted separately rather than mis-attributed.
- Findings are bucketed: **inside your edit** (listed in full), **elsewhere in this
  file** (counted only — a pre-existing backlog is not this edit's problem), **other
  files** (counted), and **unlocatable** (listed, never silently dropped).
- A non-zero exit is normal — linters exit non-zero when they find things. A missing
  executable, a timeout, or a malformed config is loud and non-fatal: the rest of the
  report still lands.

Why lint here rather than at commit time: conventions checked at commit time are
checked *after* the text is written and the moment of authorship has passed.
Checking at edit time is where it changes what gets written.

### Trust model — read before enabling

`.tc-edits.json` runs a **project-supplied command**, which puts it on the same
footing as a repository's build scripts or a `.vscode/tasks.json`. The mitigations
are: the command is executed as an **argument list with no shell**, a string
`command` is refused outright, the exact argv is **printed before it runs**, and the
config must live in the document's own repository. Opt out with `--no-lint` or
`TC_EDITS_NO_LINT=1`.

**Do not run `/tc edits` with lint enabled in a repository you would not build.**

## Two phases, two commands

**`/tc edits <file>` reports and never writes.** That is Phase A, and it covers
edits to clean (unwrapped) prose — the dominant case as a document matures and
its marks get resolved. Where an edited span overlaps a tracked **region**, it
names the region and stops.

**`/tc edits resolve <file> [<ranges>]` acts.** That is Phase B (10.0.0), and it
is the subject of the section below.

## Resolving a region you edited (10.0.0)

```
/tc edits resolve <file> [<ranges>]
```

**Dissolves** every region whose body you edited: the wrapper goes, the body
stays. Your edits and the AI text you left alone both become clean prose; a
paired gray `.tc-verbatim` excerpt goes with it (the 9.3.0 rule) and `tc-join`
is honoured. A region you emptied entirely leaves nothing behind — no fence
pair, no orphaned blank lines.

### Why dissolve, and not "accept the part I didn't touch"

An edited span is **your** writing, and the provenance model says author material
lands clean and untracked. So that text stops being AI content. The parts you did
*not* touch are AI text you have just reviewed — which is what `accept` means.
Both halves become clean prose, so the region has nothing left to assert.

This is why there is no reject branch: **anything you disagree with, you delete
before invoking.** Deletion *is* how a portion is refused, and it happens in the
editor where you are already working.

### The surface has no flags, deliberately

`<file>` is **required** — bare `/tc edits` reports every changed file, which is
right for a report and catastrophic for a mutation. There is no `--yes`: nothing
in this family prompts, so a confirmation flag would name a mechanism that does
not exist, and `/tc edits <file>` is already the look-first step. There is no
`--dry-run`: it would only duplicate that. All three are *rejected* by argparse
rather than ignored, so a stale invocation fails loudly.

### A narrower invariant, not none

8.1.0 makes `accept`/`reject` refuse on a file with uncommitted changes, because
approval could otherwise attach to content the reviewer never read. `resolve`
runs **only** on a dirty file — your uncommitted edits are its whole input — so
that gate cannot apply. Three things replace it:

1. **An AI baseline must exist.** No snapshot, no resolve (exit 3). It does *not*
   fall back to git HEAD: HEAD cannot separate your edits from the AI's, and this
   operation accepts text on the strength of that separation.
2. **The resolution is journaled** — the baseline's sha256 and the pre-resolution
   body land in `.tc-history.md`, which is git-committed. git never saw the
   pre-resolution state, so that is the only durable handle on what was approved.
3. **It is undoable** — the pre-resolution bytes are saved first:
   `/tc edits restore <file> --gen 0 --yes`.

### Ordering

`resolve` leaves the file dirty, and `accept`/`reject` refuse on a dirty file. So:

> **resolve everything you mean to → commit → accept the rest**

Any further hand edit restarts the cycle, which is why it is worth batching the
resolves rather than interleaving them with accepts. The command says so whenever
anything is left pending.

### Green regions are checked, and the check is honest

For a `sourced` or `transcript` region, the content your edit **introduced** is
compared against the gray excerpt plus the text already standing in the region.
Anything unaccounted for is named on screen *before* the dissolve — which then
removes a provenance claim that has become false. That is the correction; the
alternative is leaving a false claim in place.

**It is a conservative flag, not a proof.** It cannot see a contradiction, a
deletion, or a new claim rebuilt from words already present, and a swapped
quantifier or single digit can slip through. Your reading is the backstop, the
same standing the 9.1.0 citation scanner ships with.

### Still atomic

`/tc accept` and `/tc reject` are unchanged for a region you have **not** edited:
all-or-nothing, no inline marks inside. An edited **inline mark** is reported,
not resolved — "accept all but the edit" is not meaningful for a few characters
inside a `<mark>` — and it stays in the pending list.

## Options

| flag | effect |
|---|---|
| `--baseline auto` | snapshot, else git HEAD (default) |
| `--baseline snapshot` | snapshot only; fail if absent |
| `--baseline git` | force git HEAD |
| `--gen N` | diff against snapshot generation N (0 = newest) |
| `--no-lint` | skip the project lint step |
| `--no-diff` | counts only; omit each span's before/after text (9.9.3) |
| `--json` | emit the raw report object (spans carry `before`/`after` since 9.9.3) |

## Subcommands

| form | effect |
|---|---|
| `/tc edits` | **(9.9.3)** report every tracked file whose bytes differ from its newest snapshot. No path needed. Zero deltas prints a plain message and exits 0. |
| `/tc edits <file>` | report that one file (unchanged behavior) |
| `/tc edits snapshots <file>` | list stored generations |
| `/tc edits diff <file> [--gen N]` | **(9.9.3)** unified diff of the file on disk against a stored generation. Read-only. |
| `/tc edits show <file> [--gen N]` | **(9.9.3)** print a stored generation verbatim to stdout (metadata goes to stderr, so it pipes). Read-only. |
| `/tc edits restore <file> [--gen N] [--yes]` | overwrite the file from a generation (the current bytes are snapshotted first) |
| `/tc edits resolve <file> [<ranges>]` | **(10.0.0)** dissolve the regions you edited. See above. |

Bare `/tc edits` does **not** use the most-recently-modified working-file heuristic
that `/tc status`, `/tc list`, `/tc accept`, and `/tc reject` use. That heuristic
exists because those commands have no better information; this one does — the
snapshot store records a hash per baseline, so it can name exactly which files
changed rather than guess.

## Reading the report (9.9.3)

Each span prints its **before and after** text beneath the line range:

```
    - lines 971-974          +2    -3     content
        -The proximity of the minisum location to the location <mark><s>choosen</s>chosen</mark><sup>3</sup> for
        +The proximity of the minisum location to the location chosen for
```

This is what makes the report reviewable by a session that never saw the baseline.
Before 9.9.3 the report gave line numbers only, which could be reviewed *only* by
whoever still remembered what the text used to say — so a fresh, resumed, or
compacted context could not review at all. Long diffs truncate with an explicit
count; they are never shortened silently.

## What this skill does not do

- **`/tc edits <file>` does not edit the document, ever.** Only
  `/tc edits resolve` and `/tc edits restore` write, and both are named for it.
- It does not resolve **inline marks**, or regions you have not edited —
  `/tc accept` / `/tc reject` own those.
- It does not know your conventions; your linter does.
- It does not suspend tracking. `/draft` remains user-only; every AI correction
  written after this report is tracked.
