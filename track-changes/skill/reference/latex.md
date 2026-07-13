# LaTeX Reference

Lookup reference for using the `track-changes` skill in `.tex` files.
Complements `SKILL.md` §4 (LaTeX encoding) and §10 (preamble setup),
and `reference/highlight-syntax.md` (the cross-language syntax tables).

## The two macros

The skill defines two macros, both provided by `tc.sty`:

| Macro | Role | Renders as |
|-------|------|-----------|
| `\tc{<content>}` | highlight wrapper | yellow background behind `<content>` |
| `\tcn{<N>}` | reference number | small superscript `N` |

The strikeout role is played by `\sout{}` from `soul` (which `tc.sty`
loads transitively). When `soul` is incompatible with your project,
substitute `ulem`'s `\sout` via the fallback preamble.

## Three change types

```latex
% Insertion — wrap only the inserted chars
The function $f$ is \tc{uniformly }\tcn{3}continuous on $[a,b]$.

% Deletion — wrap only the removed chars, with \sout inside
The bound holds for all $n\ge 1$\tc{\sout{, as we will see in Chapter 4}}\tcn{5}.

% Replacement — \sout the old chars, follow with new chars, all inside one \tc
\tc{\sout{Every continuous }Every monotone continuous }\tcn{4}function on a compact set attains its maximum.
```

The PreToolUse hook validates that any added or removed characters in
the diff are covered by `\tc{...}\tcn{N}`. It does not validate the
semantic distinction between insertion / deletion / replacement — that
is for downstream review tooling.

## Preamble — recommended

```latex
\usepackage{tc}
```

`tc.sty` is installed at `~/.claude/skills/track-changes/lib/tc.sty`.
To make it discoverable by your LaTeX engine, copy it into:

- Your project's preamble directory (alongside the main `.tex` file or
  in an `inputs/` subdirectory loaded by `\input{}`), OR
- A system-wide TEXMF directory (`kpsewhich --var-value=TEXMFHOME`
  points to a per-user location; copying `tc.sty` under
  `$TEXMFHOME/tex/latex/local/` and running `mktexlsr` makes it
  available globally).

## Preamble — inline definition

If you do not want to install `tc.sty`, define the macros inline:

```latex
\usepackage{soul}
\sethlcolor{yellow}
\newcommand{\tc}[1]{\hl{#1}}
\newcommand{\tcn}[1]{\textsuperscript{#1}}
```

## Preamble — `xcolor` fallback (for `soul` incompatibility)

`soul` is known to interact poorly with:

- **`hyperref`** loaded after `soul` — link rendering breaks inside
  `\hl{}` regions.
- **`fontspec`** with non-TeX-Gyre fonts under XeLaTeX or LuaLaTeX —
  `\hl{}` does not handle these fonts.
- **Other highlight or color packages** — conflicting macro
  definitions or color-stack interactions.

If your manuscript compiles with errors involving `\hl` or `soul`,
substitute:

```latex
\usepackage{xcolor,ulem}
\newcommand{\tc}[1]{\colorbox{yellow}{#1}}
\newcommand{\tcn}[1]{\textsuperscript{#1}}
% \sout already provided by ulem
```

The protocol's source-side syntax is unchanged; only the rendering
backend differs. The hook validates wrapper presence, not the choice of
backend.

## Magic comment for per-file opt-in/opt-out

For `.tex` files (no native YAML frontmatter), the per-file activation
override is a magic comment in the first 10 lines:

```latex
% tc-track: true
```

or:

```latex
% tc-track: false
```

This overrides any project-level `.tc-tracked` marker for that single
file. See `SKILL.md` §2 for the full precedence chain.

## Non-rendering environments and brand-new blocks → `/draft`

v3 has **no sibling mechanism for LaTeX.** The brand-new-block sibling
form (a `<mark>` line above the construct) is **Markdown/Quarto only**;
it does not apply to `.tex`. So both of these LaTeX cases route to
`/draft` (the per-turn override), not to a sibling mark:

- **Editing inside a non-rendering environment** — verbatim, lstlisting,
  minted, equation/align/gather/multline and starred variants, `\[...\]`,
  tabular. A change inside one of these can't be inline-wrapped without
  breaking the environment, and v3 dropped the in-construct sibling form.
- **Adding a brand-new LaTeX block** — `\section{}`, or a new
  `equation`/`align`/`tabular`/`verbatim` environment.

In either case the hook blocks the unwrapped change and suggests
`/draft`; make the edit under `/draft` and note it in your reply for
review. This is a documented v3 limitation. See `SKILL.md` §6.

## Source-grounded regions and verbatim scaffolding (v9)

`tc.sty` provides two region-level environments beyond the inline
`\tc`/`\tcn` pair. The `tcregion` change-bar (v6) now carries a second
optional argument, and a new `tcverbatim` environment holds a verbatim
source excerpt for side-by-side confirmation.

### `tcregion` — the source locator argument

The environment takes `{N}[<prov>][<src>]` (arg spec `m o o`). The first
optional argument is the provenance; v9 adds two source-grounded values,
`transcript` and `sourced`, which share a green bar (`tcbarsourced`). The
second optional argument is a source locator, printed after the `[N]` head
as `sourced: <src>` in the bar color:

```latex
\begin{tcregion}{7}[sourced][@daskin2013 p.114]
The p-median objective minimizes demand-weighted distance ...
\end{tcregion}
```

The locator renders whenever supplied, but is meaningful only with the
`sourced`/`transcript` provenances. The `{N}` and `{N}[<prov>]` forms parse
exactly as before — the second bracket is independent and optional.

As of 9.1.0, a `tcregion` with the `sourced` provenance must contain a
reader-facing citation in its body — a `\cite`-family command (`\cite{key}`,
`\citep{key}`, `\autocite{key}`, …) or `\footnote{…}` — enforced by the
track-changes hook at the write (the exact key when the source was staged by
`@citekey`); `tc-src` metadata alone does not satisfy it.

### `tcverbatim` — confirmation scaffolding

`tcverbatim` frames a verbatim source excerpt in a gray left bar with a
muted `\footnotesize` body, self-labeled to mark it as temporary:

```latex
\begin{tcverbatim}{Freight Transport.docx p. 12}
The excerpt lifted verbatim from the source, quoted here so the
source-grounded refinement beside it can be confirmed at a glance.
\end{tcverbatim}
```

The mandatory argument is the citation; the head prints
`<citation> — delete after confirming` in gray. The block is not numbered,
is ignored by the mark protocol, and is deleted per project policy once the
refinement is confirmed. Like `tcregion`, it is `framed`-based, so it
tolerates paragraph breaks and display math inside.

As of 9.1.1, `\tcsrckey{…}` marks the load-bearing sentence inside a
`tcverbatim` context block — emphasis (bold + underline), not a new color; the
whole block stays gray, and the write-time containment check strips the marker
syntax before verifying the excerpt against the source.

## Compatibility notes

- The `\tc{}` macro takes a single mandatory argument. v1 took two
  arguments (`\tc{N}{content}`) — v2's signature is incompatible. Run
  `bash install.sh --migrate <dir>` to convert v1 marks to v2 in place.
- `\sout{}` from `soul` and `\sout{}` from `ulem` are interchangeable
  for the strikeout role. The skill assumes one of them is available.
- The hook does not check for `\usepackage{tc}` in the file; it
  validates the marks' shape regardless of whether they will compile.
  The SessionStart preamble advisory (SKILL.md §10) is the path for
  flagging missing preamble setup.

## Cross-references

- Full protocol: `SKILL.md`
- Markdown encoding: `SKILL.md` §3 and `reference/highlight-syntax.md`
- LaTeX encoding: `SKILL.md` §4
- Activation mechanisms: `SKILL.md` §2
- Numbering: `SKILL.md` §5
- Non-rendering contexts (LaTeX → `/draft`): `SKILL.md` §6
- Slash commands: `SKILL.md` §7
- v1 → v2 migration: `bash install.sh --migrate <dir>`
