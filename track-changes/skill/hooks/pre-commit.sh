#!/usr/bin/env bash
# hooks/pre-commit.sh — track-changes OPTIONAL git pre-commit advisory (§8).
#
# Scans the staged tracked .md / .qmd / .tex files for UNRESOLVED track-changes
# marks (`<mark>…</mark><sup>N</sup>` for Markdown/Quarto, `\tc{}\tcn{N}` for
# LaTeX) and prints a warning listing each file and its outstanding mark
# numbers. Exits non-zero as an ADVISORY so the commit is interrupted and the
# author can decide; it is never a hard failure beyond that single advisory
# exit.
#
# This is a GIT hook, NOT a Claude Code hook. It is **default OFF** and is
# **never** auto-wired into .git/hooks by install.sh. Opt in explicitly:
#
#   bash install.sh --enable-pre-commit [<repo>]
#       Installs this script as <repo>/.git/hooks/pre-commit (copy). Default
#       <repo> is the current directory's git repo.
#
#   - or, manually, from the repo root:
#       ln -s ~/.claude/skills/track-changes/hooks/pre-commit.sh \
#             .git/hooks/pre-commit
#       chmod +x .git/hooks/pre-commit
#
# Bypass a single commit without removing the hook:
#
#   git commit --no-verify        (skips ALL pre-commit hooks for this commit)
#
# Behavior contract (best-effort, never block beyond the intended advisory):
#   - No git, not a repo, or no staged tracked files -> exit 0 (silent).
#   - Staged tracked files but no unresolved marks    -> exit 0 (silent).
#   - One or more unresolved marks                    -> warn + exit 1.
#   - Any internal error (python missing, parse fail) -> exit 0 (fail-open):
#       a broken advisory must never block the user's commit.
#
# Exit codes:
#   0  no unresolved marks found (or unable to check; fail-open)
#   1  unresolved marks found (advisory — override with `git commit --no-verify`)

set -u

# Never let an unexpected error abort someone's commit. The only intended
# non-zero exit is the advisory (exit 1) emitted explicitly below.
trap 'exit 0' ERR

# Allow an env opt-out even when the hook is installed (e.g. CI), without
# editing .git/hooks: TC_PRECOMMIT=0 disables the check.
if [ "${TC_PRECOMMIT:-1}" = "0" ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Require git + a work tree. Fail-open if either is absent.
# ---------------------------------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  exit 0
fi
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Collect the staged (to-be-committed) tracked files with a tracked extension.
# --cached = the index (what `git commit` will record); we also restrict to
# Added/Copied/Modified/Renamed (drop deletions, which have no content).
# ---------------------------------------------------------------------------
mapfile_compat() {
  # Portable replacement for `mapfile` (absent in old bash): read NUL-delimited
  # paths from stdin into the named array.
  local __arr="$1"
  eval "${__arr}=()"
  local line
  while IFS= read -r -d '' line; do
    eval "${__arr}+=(\"\$line\")"
  done
}

STAGED=()
while IFS= read -r -d '' f; do
  case "$f" in
    *.md|*.qmd|*.tex) STAGED+=("$f") ;;
  esac
done < <(git diff --cached --name-only --diff-filter=ACMR -z 2>/dev/null)

if [ "${#STAGED[@]}" -eq 0 ]; then
  exit 0
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"

# ---------------------------------------------------------------------------
# Resolve a working Python 3 (mirrors the probe used elsewhere in the skill).
# If none is found we fall back to a grep-based mark count.
# ---------------------------------------------------------------------------
resolve_python3() {
  local cand bin
  for cand in python3 python "py -3" py; do
    # Skip the Windows "App Execution Alias" python stub under
    # .../Microsoft/WindowsApps/ (executing it hangs the probe; 9.8.1).
    # command -v resolves a path only, so it cannot hang.
    bin="${cand%% *}"
    case "$(command -v "${bin}" 2>/dev/null)" in
      */Microsoft/WindowsApps/*) continue ;;
    esac
    if ${cand} -c "import sys; sys.exit(0 if sys.version_info[0] >= 3 else 49)" >/dev/null 2>&1; then
      printf '%s' "${cand}"
      return 0
    fi
  done
  return 1
}
PY="$(resolve_python3 || true)"

# Locate this script's directory so we can import the analyzer's extractors
# (whether running from the skill tree or a copy in .git/hooks). We try the
# skill's canonical lib path first, then a sibling ../lib of this script.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
LIB_CANDIDATES=(
  "${HOME}/.claude/skills/track-changes/lib"
  "${SCRIPT_DIR}/../lib"
)
LIB_DIR=""
for d in "${LIB_CANDIDATES[@]}"; do
  if [ -f "${d}/tc_analyzer.py" ]; then
    LIB_DIR="${d}"
    break
  fi
done

# ---------------------------------------------------------------------------
# For each staged file, count unresolved marks and list their numbers.
# Emits one "PATH<TAB>N1,N2,..." line per file with marks; nothing otherwise.
# Prefers the analyzer extractors (accurate N + type); falls back to grep.
# ---------------------------------------------------------------------------
scan_one_python() {
  local f="$1"
  TC_FILE="$f" TC_LIBDIR="${LIB_DIR}" ${PY} - <<'PYEOF'
import os, sys, re
path = os.environ['TC_FILE']
libdir = os.environ.get('TC_LIBDIR', '')
if libdir and libdir not in sys.path:
    sys.path.insert(0, libdir)
try:
    import tc_analyzer
except Exception:
    sys.exit(3)  # signal: fall back to grep
try:
    with open(path, 'r', encoding='utf-8', newline='') as fh:
        text = fh.read()
except Exception:
    sys.exit(0)  # unreadable -> no marks reported (fail-open)
text = text.replace('\r\n', '\n')
ext = os.path.splitext(path)[1].lower()
try:
    if ext in ('.md', '.qmd'):
        marks = tc_analyzer._md_extract_marks(text)
    elif ext == '.tex':
        marks = tc_analyzer._tex_extract_marks(text)
    else:
        marks = []
except Exception:
    sys.exit(3)  # extractor failed -> fall back to grep
ns = [str(m['N']) for m in marks]
if ns:
    sys.stdout.write(','.join(ns))
PYEOF
}

scan_one_grep() {
  # Coarse fallback: count <sup>N</sup> immediately after </mark>, and \tcn{N}.
  # Reports the numbers it can recover; never errors.
  local f="$1"
  grep -oE '</mark><sup>[0-9]+</sup>|\\tcn\{[0-9]+\}' "$f" 2>/dev/null \
    | grep -oE '[0-9]+' \
    | paste -sd, - 2>/dev/null
}

FOUND=0
REPORT=""
for f in "${STAGED[@]}"; do
  ns=""
  rc=0
  if [ -n "${PY}" ] && [ -n "${LIB_DIR}" ]; then
    ns="$(scan_one_python "$f")" || rc=$?
    if [ "${rc}" = "3" ]; then
      ns="$(scan_one_grep "$f")"
    fi
  else
    ns="$(scan_one_grep "$f")"
  fi
  if [ -n "${ns}" ]; then
    FOUND=$((FOUND + 1))
    REPORT="${REPORT}  ${f}: marks ${ns}"$'\n'
  fi
done

if [ "${FOUND}" -eq 0 ]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Advisory warning. Mirrors the PreToolUse style at commit time.
# ---------------------------------------------------------------------------
{
  printf 'track-changes: warning — unresolved marks in %d staged tracked file(s):\n' "${FOUND}"
  printf '%s' "${REPORT}"
  printf 'Resolve them (/tc accept|reject), drop them, or pass --no-verify to commit anyway:\n'
  printf '  git commit --no-verify\n'
} >&2

exit 1
