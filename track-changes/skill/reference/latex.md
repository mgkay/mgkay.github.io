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
the diff are covered by `\tc{...}\tcn{N}` (or fall in a non-rendering
region with a sibling). It does not validate the semantic distinction
between insertion / deletion / replacement — that is for downstream
review tooling.

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
% track-changes: true
```

or:

```latex
% track-changes: false
```

This overrides any project-level `.tc-tracked` marker for that single
file. See `SKILL.md` §2 for the full precedence chain.

## Sibling rule (non-rendering environments)

When a change falls inside one of the LaTeX non-rendering environments
(verbatim, lstlisting, minted, equation/align/gather/multline and
starred variants, `\[...\]`, tabular), emit one sibling
`\tc{...}\tcn{N}` per change on the lines immediately above the
environment opener. See `reference/highlight-syntax.md` for examples.

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
- Non-rendering contexts: `SKILL.md` §6
- Slash commands: `SKILL.md` §7
- v1 → v2 migration: `bash install.sh --migrate <dir>`
