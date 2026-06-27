---
name: tc-polish
description: Opt-in, default-OFF skill for cleaning up AND editorially improving VOICE-DICTATED document prose in existing .md/.qmd files, WITHOUT destabilizing track-changes. Does the full copy-editor pass — speech-recognition errors, grammar, dropped words, PLUS meaning-preserving restructuring (split run-ons, reorder for flow, tighten wordiness, smooth awkward phrasing). AI changes surface as ordinary track-changes <mark> marks (reviewable via /tc accept|reject). Bright lines: improve freely but NEVER change meaning; and NEVER auto-correct an unrecognized token (jargon/code/math/domain term) — leave it and flag it. Invoke explicitly with /tc polish [file] (or /tc-polish [file]) — the invocation is the opt-in (no marker). On a track-changes-tracked file, fixes surface as marks; on an untracked file, polish offers a one-time direct edit (no marks) or to enable tracking first. Sits on top of track-changes + verified-import; modifies neither.
---

# polish

`polish` cleans up and **editorially improves voice-dictated** document input. It
does the full pass a good copy-editor would: the corrections — speech-recognition
errors, ordinary grammar, dropped/missing words — **and** the editorial work —
splitting over-long sentences, reordering clauses for flow, tightening wordiness,
smoothing awkward phrasing — **all without changing meaning** (§3). On a
track-changes-tracked document it surfaces every change as an ordinary
**track-changes `<mark>`**, so the existing review discipline stays fully intact
(on an untracked throwaway it can instead apply changes directly, with a full
change summary — §1, §5a). It **orchestrates** track-changes; it does not invent a
parallel marking system.

This is safe to make aggressive because polish only ever sees the **dictated
scope** — the prose you newly added since the baseline (§2, §6). Already-vetted,
committed prose is out of scope and is never re-edited, so the editorial pass acts
only on your own fresh words, never on the verified corpus.

One reviewable channel:

- **AI polish** — surfaced as **ordinary track-changes `<mark>` marks**
  (reviewable via `/tc accept|reject`). These go through track-changes' *existing*
  PreToolUse hook, unchanged.

`polish` adds **new files only**. It does not modify track-changes or
verified-import source — the "don't destabilize the workflow" constraint is met
by construction, not by discipline.

> **No view-time "dictated lens."** An earlier version of polish also shaded the
> author's *entire new dictation* a second color in the rendered HTML
> (`?dictated=1`), via a positional manifest + a Quarto Lua filter. It was
> **retired (2026-06-02)** after the first real-lecture test. The manifest is
> built over the *source* token stream, but the filter runs over Quarto's
> *executed* token stream, and in a real lecture those streams diverge (Quarto
> injects caption / cross-reference text and code output as `Str` nodes the
> source lacks) — so the positional lens silently mislanded or dropped spans: it
> missed a dictated `## 2.` heading rename that was plainly in `git diff`. For
> "what did I change," **`git diff` is the authoritative view** (§8). Do not
> reintroduce the lens without first solving the diff at the *executed*
> (post-render) token level — a positional source-side manifest cannot be trusted.

---

## 1. Activation (explicit invocation; tracked → marks, untracked → ask)

`polish` never fires unbidden — it runs only when you **explicitly invoke**
`/tc polish [file]`. The invocation itself is the opt-in; there is **no separate
`.polish-on` marker or `polish-on:` key** (removed 2026-06-02 — superfluous for a
manually-invoked command).

What happens next depends on whether the file is **track-changes-tracked**.
`analyze` reports this as `tracked: true|false`, computed via track-changes' own
`tc_core.activation` (the module its hook uses) — so it always matches what the
hook will enforce, and it is CRLF-safe (unlike the bash `/tc status`, which
misreports Windows-CRLF files).

- **`tracked: true`** → **mark mode**: fixes surface as track-changes marks (§4),
  validated and logged by the existing hook. The default for any maintained
  deliverable — for a tracked lecture `/tc polish <file>` just works.
- **`tracked: false`** (or `null` — track-changes not importable) → **ask the
  author** which they want:
  - **(a) Enable tracking first** (`/tc enable <file>` / `/tc mark <dir>`), then
    re-invoke for mark mode — for anything they will maintain and re-review; **or**
  - **(b) One-time direct polish** — fixes applied straight into the file, **no
    marks** (for a genuine throwaway; §5a).
  **Lead with (a):** a forgotten-to-track deliverable must not silently lose its
  review trail. Take (b) only on the author's explicit choice.

---

## 2. Scope — what polish fixes (M2 vs M1)

Run `bash lib/polish-cli.sh analyze <file>` first. It reports the scope.

### M2 — diff-scoped (the default, recommended path)
A prior committed baseline exists (`git` HEAD, or `--baseline-ref`). The engine
diffs baseline vs on-disk over pandoc `Str` tokens and reports the **dictated
scope** — the prose newly dictated since the baseline.
- **Polish ONLY the new (dictated) prose**, under the §3 safety rules, so an
  already-vetted document is not re-polished.

### M1 — whole-document / first-draft
No baseline (untracked/new file, or the whole doc is new dictation). Scope = the
whole document's prose. **Not recommended on a large, already-vetted doc** —
commit a baseline first to get M2 scoping. The engine prints this note.

The diff is source-level and git-authoritative; it only **scopes** the fixes —
it is not a rendered overlay (§6, §8).

---

## 3. The safety rules (bright lines — non-negotiable)

1. **Never auto-correct an unrecognized token.** If a token is not positively
   identifiable as English prose — code-ish, symbol-ish, a known domain term,
   inside `$…$`/code fence/`:::` — **leave it untouched and flag it** in your
   reply; never silently change it. The engine pre-computes these as
   `flagged_protected` (all-caps acronyms like `LTL`/`TLC`; digit+letter or
   underscore tokens like `q0`/`q_max`/`totlogcost`; non-ASCII/Greek like `αvhq`;
   and an extensible allowlist in `.polish-allowlist`). Inline math, code, and
   raw spans are excluded from the prose token stream entirely. **When in doubt,
   do not touch.**
2. **Improve freely, but never change meaning.** Polish does the full editorial
   pass — correct recognition/grammar/dropped-word errors **and** restructure for
   quality (split run-on sentences, reorder clauses for flow, tighten wordiness,
   smooth awkward phrasing). The one hard line is **meaning**: no hedge→absolute,
   no tightening that shifts a claim, no "improvement" that adds, drops, or alters
   a fact, number, or hedge. Every change is a **reviewable mark**, so the author
   sees and approves it. Two cases to distinguish:
   - **(a) A change that would alter the meaning of a sentence that is *correct as
     written*** (e.g. dropping a qualifier, firming a hedge, supplying a fact the
     author didn't state): do NOT apply it; leave the prose and raise it as a
     suggestion in your report.
   - **(b) A sentence that is *broken or nonsensical as written*** — an obvious
     error such as a stray question in declarative prose, a garbled clause, a
     non-sequitur, or a sentence whose subject/verb don't cohere: **MARK a proposed
     fix.** Fixing obvious errors is squarely polish's job — do NOT demote one to a
     prose-only suggestion. If the fix requires choosing among plausible intended
     meanings, mark your best reading **and** note the assumption in your report so
     the author scrutinizes that mark — but mark it. The mark is the safety net; an
     obvious error left only in your output, unmarked, is a polish failure.
   **Qualifier-preservation (hard rule for restructures).** When you restructure a
   sentence, every qualifier, hedge, scope phrase, modal, and quantifier in the
   original MUST survive *with the same force* in the replacement — temporal/scope
   phrases ("over the long run", "in practice", "for a single item"), hedges
   ("usually", "typically", "almost always"), and modals ("would", "may", "can").
   If a cleaner structure would drop or weaken any of them, do NOT make the change
   — keep the original. Dropping "over the long run", or softening
   "usually"→"generally" or "would"→"will", is a meaning change, not a polish; the
   value of a restructure is never worth a lost qualifier.
   **Do not relocate** a sentence to a different paragraph: marks cannot legibly
   show a move, so flag the relocation as a suggestion instead of applying it (W4).
3. **Fixes inside a non-rendering construct.** The engine reports
   `nonrendering_regions` (fenced code, `$$…$$`, `:::` divs, YAML, tables). A
   track-changes fix there would be **blocked by the hook and routed to /draft**.
   Do NOT attempt such a fix: **skip it and report** "fix skipped: inside
   <kind> at line N" so the author can handle it manually.
4. **Opt-in, default-OFF** (see §1).

---

## 4. How AI fixes become marks (reuse, don't reinvent)

When `polish` edits a tracked doc, each fix MUST be wrapped in the standard
track-changes grammar — the existing hook enforces it:

| Change | Markdown / Quarto |
|--------|-------------------|
| insertion (missing word) | `<mark>NEW</mark><sup>N</sup>` |
| deletion | `<mark><s>OLD</s></mark><sup>N</sup>` |
| replacement (correction or restructure) | `<mark><s>OLD</s>NEW</mark><sup>N</sup>` |

**Granularity — corrections vs restructures (W1).** Wrap **only the changed
characters** for a *correction* (a typo, a dropped word, a casing slip) — the
minimal diff. For a *restructure* (splitting, reordering, or rephrasing a
sentence), wrap the **whole affected sentence** as one replacement mark — the
entire old sentence struck, the entire new sentence following — so the change
reads as a legible one-mark-per-sentence unit instead of a scatter of
disconnected fragments. **Never** represent a structural change as a minimized
character diff; a reorder minimized token-by-token is unreadable. One restructured
sentence = one mark.

**Mark numbering (no collisions):** the engine reports `next_mark_n` (= max
existing N + 1). Assign N sequentially from there across all changes in the run.
Prefer a single `MultiEdit` so all marks are validated together; if editing
incrementally, re-read `next_mark_n` between edits. `/tc list` after polish must
show no duplicate numbers.

`/tc accept|reject` resolves polish's marks exactly as any other — polish changes
nothing about resolution.

---

## 5. The `/tc polish` workflow

`/tc polish` splits into a cheap **orchestrator** (this session) and a **Sonnet
sub-agent** that does the actual fix-finding + marking in a **fresh, minimal
context** — so the slow part (model reasoning) runs on a faster model and is not
taxed by a long main-session context.

1. **Analyze (orchestrator):** `bash lib/polish-cli.sh analyze <file>`. Read
   `tracked`, scope (M1/M2), `dictated_tokens`, `flagged_protected`,
   `nonrendering_summary`, `next_mark_n`, warnings. Also capture
   `git diff HEAD -- <file>` — the readable dictated edit.
2. **Branch on `tracked`** (§1): tracked → continue; `false`/`null` → ask the
   author (enable tracking, then re-invoke; or one-time **direct** polish, §5a).
3. **Dispatch (orchestrator → sub-agent):** spawn ONE sub-agent — **Agent tool,
   `model: sonnet`** — with a CURATED prompt. Forward ONLY:
   - the file path and the **`git diff HEAD`** (the prose to polish);
   - `next_mark_n`, `flagged_protected`, and the **mode** (mark vs direct, §5a);
   - a one-line non-rendering note from `nonrendering_summary` ("don't place a
     fix inside `$…$`/`$$…$$`, code fences, or `:::` divs") — **not** the raw
     region list;
   - the §3 bright lines and the §4 mark grammar (paste them in).
   Do NOT forward the main-session context. The sub-agent does the **full
   editorial pass** on the dictated prose — recognition/grammar/dropped-word
   corrections **and** restructuring (split run-ons, reorder for flow, tighten
   wordiness, smooth phrasing), **never changing meaning** (§3) — **preserving
   every qualifier/hedge/scope-phrase/modal verbatim in force when restructuring;
   if a cleaner structure would drop or weaken one, it does NOT make the change**
   — leaves+flags
   protected tokens, skips non-rendering-region fixes, does **not** relocate
   sentences across paragraphs (flags those as suggestions), and applies **all
   changes in a single `MultiEdit`** (corrections wrap the changed chars;
   restructures wrap the whole sentence — §4; marks numbered from `next_mark_n`;
   track-changes' hook validates them). It returns a structured summary in **four
   buckets (W2 — this is the reviewer's triage)**:
   - **Corrections** — `old → new`, one per typo/grammar/dropped-word fix.
   - **Restructures** — one line each, naming the editorial move ("split the
     run-on at 'and'", "led with the TLC definition, deferred the optimum"), so
     the author knows which marks are heavy and reviews them with more care.
   - **Left + flagged** — protected tokens left untouched.
   - **Suggested (not applied)** — changes that would alter the meaning of an
     *otherwise-correct* sentence, and sentence relocations, for the author to
     make by hand. An **obvious error** (broken/nonsensical sentence) is NOT placed
     here — it is **marked** with a best-guess fix per §3(b), with the assumption
     noted.
   *Trivial runs* (empty scope, or 1–2 obvious corrections with no restructuring)
   MAY be done inline by the orchestrator — a sub-agent isn't worth the spawn.
4. **Audit (orchestrator):** `bash lib/polish-cli.sh audit <file> --runs N --mode
   M2|M1 --flagged a,b` — appends a `dictated:` breadcrumb to `.tc-history.md`.
5. **Report (orchestrator):** relay the sub-agent's summary to the author.
6. The author reviews the marks via `/tc`, and consults **`git diff`** to re-read
   their entire new input (the authoritative "what did I change").

**Why this is fast:** the engine (`analyze` ≈ 0.4 s) and track-changes' hook
(deterministic — no LLM/network call) are already fast; the latency is model
inference, dominated by a long main-session context. A Sonnet sub-agent with a
tiny fresh context attacks both — faster model, no session-context tax — and the
single `MultiEdit` shrinks the window where a concurrent author edit forces a
re-read/retry.

### 5a. Direct mode (untracked, one-time, no marks)

Chosen when the author opts for a one-time direct polish on an **untracked** file
— a throwaway not maintained over time, which is exactly what the track-changes
review discipline is *for*, so a non-maintained doc legitimately skips it.

- **Apply the full editorial pass directly** — corrections **and** restructuring
  (split/reorder/tighten/smooth) — straight into the file, no `<mark>` wrappers.
  (On an untracked file the track-changes hook does not fire, so plain edits go
  straight through; no `/draft` needed.)
- **The §3 bright lines still hold.** Protected tokens (jargon/code/math/domain)
  are still **left + flagged**, never auto-corrected. And **never change meaning**:
  with no mark to carry it, any meaning-affecting change is **reported, not
  applied** — surfaced as a suggestion. Sentence relocations are likewise
  suggested, not applied.
- **The change summary is the only record** (no marks; maybe no `git diff` on a
  non-git scratch file), so present a **complete** one, in three buckets:
  1. **Applied** — corrections as `old → new`, and restructures as one line each
     naming the move.
  2. **Suggested, not applied** — meaning-level changes and relocations.
  3. **Left untouched** — the protected tokens.
- **No `dictated:` breadcrumb** is written (untracked ⇒ outside the track-changes
  audit). Say so in the report.

---

## 6. The dictated scope (how it's computed)

The engine computes the scope deterministically and **writes no files**:

- Tokenize the baseline (git HEAD) and the on-disk file by pandoc `Str` node, in
  document order; `Code`/`Math`/`RawInline` carry text in a string field (not
  `Str` children), so they never enter the stream and are protected by
  construction.
- `difflib` over the two token streams → the inserted/replaced tokens are the
  **dictated scope** (M2). No baseline → whole-document prose (M1).
- Existing track-changes marks are reduced to their effective accepted text
  before tokenizing, so prior unresolved marks don't pollute the scope.

This is **advisory** — it tells the model which prose is new to fix. It never
edits the document, and (unlike the retired lens) it writes no manifest and adds
no render-time markup. The source-level diff is reliable; a rendered overlay
derived from it positionally was not (see the intro callout and §8).

---

## 7. The `dictated:` audit breadcrumb

`polish` appends a `dictated:` block to the project's `.tc-history.md` (additive,
analogous to the retired `imported:` entry). track-changes **never reads
`.tc-history.md` back** (it diffs its own `.marks` cache), so this cannot perturb
the audit classifier. The block is keyed `dictated:` (distinct from
`introduced:`/`resolved:`) and records: run count, mode, baseline, and flagged
tokens. If `.tc-history.md` doesn't exist, polish writes the same canonical
header track-changes would.

---

## 8. Baseline (M2) edge cases

- **Baseline = last git commit** (`HEAD`) by default; override with
  `--baseline-ref <ref>` (e.g. a git tag used as a named checkpoint).
- **Dirty tree:** polish cannot distinguish prior uncommitted non-dictation edits
  from this session's dictation; it warns and treats ALL changes since the
  baseline as new. Commit a baseline first to scope precisely.
- **Untracked / new file:** no baseline → M1 (whole-doc), with a note.
- **Unresolved marks in the diff:** the engine strips track-changes mark wrappers
  to their effective accepted text before tokenizing, so prior marks don't
  pollute the dictated scope.
- **"What did I change?"** Use `git diff` (or `git diff --word-diff`). It is
  exact, complete, and needs no infrastructure — it is the authoritative view of
  your dictated input. polish deliberately does **not** reimplement it as a
  rendered overlay.

---

## 9. Why there is no view-time lens (the retired-feature decision)

The original charge's "real prize" was a second color showing the author's
*entire new dictated input* in the rendered document (`?dictated=1`). It shipped,
passed its Pattern-1 verification, and was **retired on first real-lecture use**
— recorded here so it is not rebuilt by reflex.

- **Mechanism that failed:** the Python engine tokenized the *source* `.qmd`; the
  Quarto Lua filter tokenized the *executed* document; a positional manifest
  mapped one onto the other by `Str`-node index. The two streams are only equal
  in plain markdown (the spike). A real lecture's executed AST contains `Str`
  nodes the source lacks — figure/table caption prefixes, cross-reference
  expansions, callout titles, and the output of every code chunk — so the indices
  drift and the lens shades the wrong words or none.
- **Evidence:** running `/tc polish` on a real dictated edit of a lecture, a
  dictated `## 2.` heading rename that was unmistakably present in `git diff` did
  **not** shade. An incomplete "see everything I changed" lens is worse than
  none: you cannot trust it, so you re-read manually anyway.
- **The verification gap:** the Pattern-1 subagent checked the lens on the spike
  and controlled markup, never on an executed lecture — the same toy-vs-real gap
  that hid two engine bugs (a `cp1252`/UTF-8 crash on `′`/`α`, and a manifest path
  that didn't resolve under Quarto). Real-content acceptance testing is what
  surfaced all three.
- **The reliable alternative:** `git diff` already answers "what did I change,"
  exactly and completely, at the source level — which is also all polish needs to
  *scope* its fixes (§6). So the diff stays (internal scoping); the rendered lens
  is gone.

If a rendered overlay is ever wanted again, it must derive from the **executed**
(post-render) token stream, not a source-side positional manifest. A source-side
lens is a standing trust hazard; do not reintroduce it.

---

## 10. Relationship to `/import`

Dictation is **not** an import. But a dictated *paraphrase of a source* is a
fidelity event: when the author says "use the source wording," **defer to
`/tc import`** (verified-import) rather than polishing a paraphrase into place.
