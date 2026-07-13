# track-changes — session digest

Source-preserving edit protocol. When active, wrap ONLY the changed characters
of an AI edit in a highlight + reference number so the author can accept/reject
each change. Default-OFF. (Full spec lives in `SKILL.md`, lazy-loaded on demand.)

## Activation (most-local rule wins)
1. `/draft` (or `/tc draft`) sentinel → tracking **suspended this turn**.
   **v6: USER-ONLY — the AI cannot self-invoke `/draft` or write the sentinel
   (only the UserPromptSubmit hook does, on the human's prompt).** Everything the
   AI writes to a tracked deliverable is tracked regardless of approval.
2. Per-file override (top of file): `tc-track: true`/`false` in YAML
   frontmatter (`.md`/`.qmd`); `% tc-track: true`/`false` magic comment in
   first 10 lines (`.tex`). Per-file `false` overrides a folder marker.
3. Folder-local `.tc-tracked` marker in the file's OWN directory (no walk-up):
   empty/comments-only = **presence mode** (all `.md`/`.qmd`/`.tex` in that
   folder); listed basenames = **list mode** (only those files).
4. Hidden files (basename starts with `.`) are excluded even under a marker.
5. Otherwise **OFF**. Tracking fires only for Write/Edit/MultiEdit on EXISTING
   `.md`/`.qmd`/`.tex` files.

## Mark grammar (wrap only the changed chars; mark numbers per-file unique)
| Change | Markdown / Quarto | LaTeX |
|--------|-------------------|-------|
| insertion | `<mark>NEW</mark><sup>N</sup>` | `\tc{NEW}\tcn{N}` |
| deletion | `<mark><s>OLD</s></mark><sup>N</sup>` | `\tc{\sout{OLD}}\tcn{N}` |
| replacement | `<mark><s>OLD</s>NEW</mark><sup>N</sup>` | `\tc{\sout{OLD}NEW}\tcn{N}` |

`<sup>N</sup>` sits OUTSIDE the `</mark>`. Next N = highest existing mark + 1.

**Provenance (v6+; v7 transcript, v9 sourced):** `<mark tc-prov="imported">…`
/ `\tc[imported]{…}` for a verbatim `/tc import` slice;
`tc-prov="transcript"` (v7) for AI wording over the instructor's own spoken
transcript; `tc-prov="sourced"` (v9) for AI text supported by a document
source (carries `tc-src`; verified vs a gray excerpt — see §Source-validation);
default (absent) = `authored`. Region numbers share the single mark-number
space. A transcript/sourced region is conventionally preceded by a TEMPORARY
gray `.tc-verbatim` block quoting the raw source — scaffolding, not a region:
resolution commands ignore it; delete it once confirmed.

**Whole-region insertion (v6, Fix D)** — a MULTI-block new region as ONE tracked
unit (the path for large new content; no `/draft`):
| | Markdown / Quarto | LaTeX |
|---|---|---|
| region | `::: {.tc-region tc-n="N" tc-prov="authored"}` … `:::` | `\begin{tcregion}{N}[authored]` … `\end{tcregion}` |
One number N; `/tc accept|reject N` resolves it atomically; no inline marks
inside. **Single brand-new block** (one heading/fenced/`:::`) → still a sibling
`<mark>…</mark><sup>N</sup>` on the line ABOVE. A brand-new LaTeX block → use a
`tcregion` (replaces the old `/draft` routing).

## `/tc` commands
`/tc draft` · `/tc enable <file>` · `/tc disable <file>` · `/tc mark [<dir>]` ·
`/tc migrate <dir>` · `/tc status [<file>]` · `/tc list [<file>]` ·
`/tc accept [<file>] <ranges>` · `/tc reject [<file>] <ranges>` ·
`/tc accept-all [<file>]` · `/tc reject-all [<file>]` · `/tc help` ·
`/tc import [--allow-partial] <source>[#L<a>-L<b>] [<target>]` ·
`/tc coverage <doc> <source> [--units N,N,…]` · `/tc polish [<file>]` ·
`/tc source <file>#<loc>|@citekey [<target>]` · `/tc manifest [<doc>]`.
Ranges use `1-25,!7` syntax. Omit `<file>` on a resolution command to use the
working file (most-recently-modified tracked file). Bare `/tc` prints the menu.
`/draft` = suspend this turn — **USER-ONLY (v6, v7-confirmed shadow-proof: the
UserPromptSubmit hook fires on the raw prompt before command routing, so no
skill named `draft` can intercept it); the AI cannot invoke it.**

## Limits & pointers
- **Committed-content invariant (v7):** `accept`/`reject`/`*-all` REFUSE on a
  file with uncommitted changes (exit 3) — commit instructor tweaks (own
  commit) and AI corrections (own MARKED commit) FIRST, then resolve. AI
  polish of instructor edits is marked BEFORE resolution, never applied
  during it. `list` is not gated; `TC_FORCE=1` is a human-only override.
- Editing INSIDE code/math/tables (non-rendering contexts): wrap the whole block
  as a `tcregion` / `.tc-region` insertion (v6), or ask the user to `/draft`.
- Verbatim/converted **source import**: use `/tc import` (routes to the `verified-import` skill; lands clean via sha-bound exemption). **Coverage-gated (8.2.0):** a write that DROPS a source content token is blocked with the missing tokens named (pending import preserved — fix and retry); `--allow-partial` is the explicit, audited override. Whole-document audit: `/tc coverage <doc> <source>`.
- **Source-validation (v9):** AI text supported by a document source = green `sourced` region + a TEMPORARY gray `.tc-verbatim` excerpt (verbatim by construction). Stage with `/tc source`; the hook re-reads the source and REFUSES unstaged/fabricated/paraphrased gray, >1 gray/write, or missing/wrong `tc-src` (fail-closed on scanned/unreadable). Durable evidence = `sourced:` audit entries; manifest = `/tc manifest`. **9.1.0:** the green `sourced` region MUST carry a reader-facing citation (the exact key when staged by `@citekey`, else any `[@key]`/`^[…]`/`\cite`/`\footnote` token; tokens in code/comments/verbatim don't count) and CANNOT land without its verified gray excerpt; editing a sourced region must keep its citation. **9.1.1:** a gray excerpt may carry contiguous context with the load-bearing sentence marked (`.tc-src-key` / `\tcsrckey`); keep a sourced region SCOPED to what the source supports (an inference built on top of it is authored, not sourced). A quote meant to STAY = quoted text + citation or `/tc import`, not green. Full rules → `SKILL.md §16`.
- Companion `decap` tool (author-side dictation capitalization pre-clean, OUTSIDE the mark protocol; run on fresh unmarked dictation only) — see `SKILL.md §Companion`.
- Lazy-load from `SKILL.md` on demand: activation-precedence edge cases →
  `SKILL.md §2 (Activation)`; worked mark examples + resolution walk →
  `SKILL.md §3 (Highlight Syntax)`; LaTeX preamble / `\tc` macro setup →
  `SKILL.md §10 (LaTeX Preamble Setup)` and `reference/latex.md`; audit-log
  format → `SKILL.md §11 (Audit Log)`.
