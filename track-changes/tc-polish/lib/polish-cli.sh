#!/usr/bin/env bash
# polish-cli.sh — command plumbing for the `polish` skill (yellow-only).
#
# Subcommands:
#   analyze <file> [--baseline-ref REF] [--baseline-file PATH]
#       Run the engine; print a human-readable report (scope M1/M2, dictated
#       run, flagged protected tokens, non-rendering regions, next mark number,
#       warnings). The MODEL then performs the polish edits as track-changes
#       marks, honoring the report (leave+flag protected tokens; skip fixes
#       inside non-rendering regions). This command does NOT edit the document
#       and writes no files.
#   audit <file> --runs N [--mode M2] [--baseline REF] [--flagged a,b]
#       Append a `dictated:` breadcrumb to .tc-history.md (call after edits).
#
# polish has no `setup` step: /polish is explicitly invoked, so the invocation is
# the opt-in (there is no `.polish-on` marker). The only prerequisite is that the
# target is already track-changes-tracked (a `.tc-tracked` marker / `tc-track:`
# key), since AI fixes become marks via that hook. polish is yellow-only — no
# render-time "dictated lens" (retired 2026-06-02; SKILL.md §9), and the engine
# writes no manifest.
#
# Bash-safety: no command chaining; absolute paths; the engine handles all I/O.

set -u

# Force UTF-8 stdio/file I/O so the engine's report (which can contain α, ′, ᵒ,
# em-dashes from real lecture prose) prints on a Windows cp1252 console without
# UnicodeEncodeError. Pairs with the engine's explicit encoding="utf-8" on every
# pandoc/git subprocess call.
export PYTHONUTF8=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
ENGINE="$SCRIPT_DIR/polish_engine.py"

py() {
  if command -v python >/dev/null 2>&1; then python "$@"; else python3 "$@"; fi
}

cmd_analyze() {
  local file="$1"; shift || true
  if [ -z "${file:-}" ] || [ ! -f "$file" ]; then
    echo "polish: file not found: ${file:-<none>}" >&2
    return 2
  fi
  py "$ENGINE" analyze "$file" "$@"
}

cmd_audit() {
  local file="$1"; shift || true
  py "$ENGINE" audit "$file" "$@"
}

# Baseline resolver surface (9.6.0): resolve/set/clear/show pass straight through
# to the engine, which owns the git logic + the repo-tracked state file.
cmd_baseline() {
  local sub="$1"; shift || true
  py "$ENGINE" "$sub" "$@"
}

main() {
  local sub="${1:-}"; shift || true
  case "$sub" in
    analyze)              cmd_analyze "$@" ;;
    audit)                cmd_audit "$@" ;;
    resolve|set|clear|show) cmd_baseline "$sub" "$@" ;;
    *)
      echo "usage: polish-cli.sh {analyze <file> [--baseline-ref REF] [--baseline-file PATH] | audit <file> ... | resolve <file> [--ref REF] | set <file> [REF] | clear <file> | show <file>}" >&2
      return 2 ;;
  esac
}

main "$@"
