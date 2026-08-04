# `/tc edits` — report what the author changed

*(9.9.0; 9.9.3 frictions; 9.11.1 report wording; 9.11.2 region review. 10.0.0's `resolve` was withdrawn — see the end of "Reviewing a REGION you edited".)*

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

## Reviewing a REGION you edited

**This is the case the command exists for, and the one most easily got wrong.**

For a substantial passage the AI writes a single numbered **region** rather than
inline marks. It resolves as one unit — `/tc accept N` or `/tc reject N`,
all-or-nothing, and that is unchanged. What makes it workable is that the region
**body is editable before resolution**:

> **Edit the body → `/tc edits <file>` → done.** The command commits the author's
> edits and accepts the regions they edited, **which keeps the body AS THE AUTHOR
> LEFT IT.**

**The author never commits by hand (9.13.0).** 8.1.0 requires resolution to run on
COMMITTED CONTENT; it never required the *human* to be the one who commits, and
conflating those cost two manual commits per review round — at the two moments the
author is trying to finish. `/tc edits` now commits their edits (message
`Instructor edits: <basename>`, which tc-polish's baseline resolver matches) and
then accepts; `/tc accept`/`/tc reject` likewise commit the file rather than
refusing. Only ever the named file, never `-a`. `TC_NO_AUTOCOMMIT=1` restores the
old refusal.

**Do not offer to run `git commit` for the author, and do not suggest they run it.**
The tooling does it. Telling them otherwise recreates the friction this removed.

`accept` never inspected who wrote the body. So the author's rewrite survives, the
AI lines they left alone survive, and **a passage they deleted stays deleted** —
deletion *is* how a portion is rejected, in the editor where they are already
working. There is no partial-accept or partial-reject command because there is no
need for one. The unedited remainder is approved by the act of having read the
region looking for the parts that needed changing.

`/tc edits` supports this by naming the region an edited span landed in and showing
what changed *inside* it. It still only reports.

### Ordering: polish AFTER the accept, never before

**Do not "fix up" the author's edit while it is still inside the region.** Measured
against the real gate: inside a region body every line counts as already covered by
the region's own number, so an AI edit there is accepted **with no mark** — nothing
in the *document* shows it, and `accept` would then absorb it into the author's own
prose. (Editing a line, adding a line, and rewriting the whole body were all allowed
unmarked; only deletion is separately gated.)

**It is no longer untraceable (9.12.0), but it is still unmarked.** Every AI write
that changes a region body is now recorded in `.tc-history.md` under
`region-body:`, and `/tc accept N` **warns** when the log shows that region's body
was modified after it was created. That makes ignoring this rule *visible* — it does
not make it harmless. The warning is advisory, exit code unchanged: it names the
risk and the author rules on it. Absence of a record means **not recorded**, never
"clean" — a region predating 9.12.0 has no entries.

So the rule stands as a rule, and the correct move is unchanged: accept first, then
mark corrections.

Once `accept` removes the wrapper the body is ordinary prose again and the normal
rule applies: an unmarked change to it is refused, so the correction must be a
mark the author can review. Hence:

> **author edits → `/tc edits <file>` (commits + accepts) → THEN mark corrections
> → `/tc accept` (commits + resolves)**

Two commands, both the author's. Every commit in between is the tooling's.

**Run `/tc edits` BEFORE proposing any correction, not after.** That ordering is
what puts the author's text in its own commit and yours in another — measured: in
the documented flow one commit carries only their edits and a later one carries
only your marks. If the author asks for corrections *without* running `/tc edits`
first, both authorships land in a single commit. Nothing is lost and the commit is
honest (both changes really did precede it), but the attribution the invariant asks
for is gone, and it cannot be recovered afterwards. So when an author asks for
proofreading on a file they have hand-edited, run `/tc edits` first.

A resolved number is freed, so the first correction may reuse the region's own
number. Take the next free number from the report rather than assuming.

### Green regions are checked, and the check is honest

For a `sourced` or `transcript` region, `/tc accept` compares content the body
**gained** since the write gate saw it against the durable excerpt record, and names
anything unaccounted for *before* accept removes the provenance claim. An edit must
not quietly widen a claim the citation is standing behind.

**It is a conservative flag, not a proof.** It cannot see a contradiction, a
deletion, or a new claim rebuilt from words already present, and a swapped
quantifier or single digit can slip through. Absent a durable record it reports
`not-checked` rather than passing silently. The author's reading is the backstop,
the same standing the 9.1.0 citation scanner ships with.

### Still atomic

`/tc accept` and `/tc reject` remain the only region resolutions, both
all-or-nothing, and no inline marks belong inside a region. An edited **inline
mark** is reported, not resolved — "accept all but the edit" is not meaningful for a
few characters inside a `<mark>` — and it stays in the pending list.

> **Withdrawn: the `resolve` subcommand.** 10.0.0 added a `resolve`/`dissolve`
> subcommand for exactly this, and it was withdrawn before deployment: `/tc accept N`
> on an author-edited region already produces byte-identically what it produced, so
> all it bought was one commit per session, in exchange for inverting the 8.1.0
> committed-content invariant. **This file documented it through 9.11.1** — shipped
> instructions for something argparse rejects, in the file the model reads — because
> TC-AI-19's derived check only ever opened `README.md` and `GUIDE.md`. It now globs
> the whole shipped doc surface. If any text still tells you to resolve a region with
> anything but `/tc accept`, that text is wrong.

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

- **`/tc edits <file>` does not edit the document, ever.** `/tc edits restore` is the
  only writing subcommand, and it is named for it.
- **It does not resolve anything.** `/tc accept` / `/tc reject` own every resolution —
  inline marks and regions alike, edited or not.
- It does not know your conventions; your linter does.
- It does not suspend tracking. `/draft` remains user-only; every AI correction
  written after this report is tracked.
