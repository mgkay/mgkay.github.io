# track-changes — session digest

Source-preserving edit protocol. When active, wrap ONLY the changed characters
of an AI edit in a highlight + reference number so the author can accept/reject
each change. Default-OFF. (Full spec lives in `SKILL.md`, lazy-loaded on demand.)

## Activation (most-local rule wins)
1. `/draft` (or `/tc draft`) sentinel → tracking **suspended this turn**.
2. Per-file override (top of file): `track-changes: true`/`false` in YAML
   frontmatter (`.md`/`.qmd`); `% track-changes: true`/`false` magic comment in
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

**Brand-new block** (Markdown/Quarto only — a new heading, fenced-code block, or
`:::` div) can't be inline-wrapped without breaking rendering: put a sibling
`<mark>…</mark><sup>N</sup>` on the line ABOVE it. A brand-new LaTeX
`\section{}` / `\begin{env}` is NOT auto-covered — use `/draft`.

## `/tc` commands
`/tc draft` · `/tc enable <file>` · `/tc disable <file>` · `/tc mark [<dir>]` ·
`/tc migrate <dir>` · `/tc status [<file>]` · `/tc list [<file>]` ·
`/tc accept [<file>] <ranges>` · `/tc reject [<file>] <ranges>` ·
`/tc accept-all [<file>]` · `/tc reject-all [<file>]` · `/tc help`.
Ranges use `1-25,!7` syntax. Omit `<file>` on a resolution command to use the
working file (most-recently-modified tracked file). Bare `/tc` prints the menu.
`/draft` = suspend this turn.

## Limits & pointers
- Editing INSIDE code/math/tables (non-rendering contexts): v3 does not sibling
  these — use `/draft` and note the change in the audit log.
- Verbatim/converted **source import** is a separate skill: `verified-import` `/import`.
- Lazy-load from `SKILL.md` on demand: activation-precedence edge cases →
  `SKILL.md §2 (Activation)`; worked mark examples + resolution walk →
  `SKILL.md §3 (Highlight Syntax)`; LaTeX preamble / `\tc` macro setup →
  `SKILL.md §10 (LaTeX Preamble Setup)` and `reference/latex.md`; audit-log
  format → `SKILL.md §11 (Audit Log)`.
