#!/usr/bin/env bash
# lib/tc-history.sh — audit log helpers for the PostToolUse hook.
#
# Provides path computation (cache + log) and the Python-backed
# mark-extractor / log-formatter used by hooks/post_tool_use.py.
#
# Cache layout:
#   ~/.claude/skills/track-changes/state/cache/<sha1>.marks    (JSON)
#   ~/.claude/skills/track-changes/state/cache/<sha1>.meta     (JSON: abs path)
#
# Log layout:
#   <project-root>/.tc-history.md  (append-only, diffable, kept in git)
#
# Project root resolution:
#   1. Walk up from file's directory looking for a .git/ subdirectory; use
#      that directory if found.
#   2. Fallback: the marker's directory (where .tc-tracked lives).
#   3. Final fallback: the file's own directory.

[[ -n "${_TC_HISTORY_LOADED:-}" ]] && return 0
_TC_HISTORY_LOADED=1

set -u

# Source tc-common.sh if not already loaded.
if [ -z "${_TC_COMMON_LOADED:-}" ]; then
  _tc_hist_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # shellcheck source=./tc-common.sh
  source "${_tc_hist_script_dir}/tc-common.sh" 2>/dev/null || true
fi

# ---------------------------------------------------------------------------
# tc_history_cache_dir — under state/cache. Created on demand.
# ---------------------------------------------------------------------------
tc_history_cache_dir() {
  local sd
  sd="$(tc_state_dir)" || return 1
  local cd="${sd}/cache"
  if [ ! -d "$cd" ]; then
    mkdir -p "$cd" 2>/dev/null || return 1
  fi
  printf '%s' "$cd"
}

# ---------------------------------------------------------------------------
# tc_history_sha1 <abs_path> — sha1 of an absolute path (cache key).
# Uses sha1sum (Linux/MSYS) or shasum (macOS); falls back to Python.
# ---------------------------------------------------------------------------
tc_history_sha1() {
  local s="${1:-}"
  if [ -z "$s" ]; then return 1; fi
  if command -v sha1sum >/dev/null 2>&1; then
    printf '%s' "$s" | sha1sum 2>/dev/null | awk '{print $1}'
    return 0
  fi
  if command -v shasum >/dev/null 2>&1; then
    printf '%s' "$s" | shasum -a 1 2>/dev/null | awk '{print $1}'
    return 0
  fi
  # Python fallback.
  local py
  for py in python3 python "py -3" py; do
    if ${py} -c "import sys; sys.exit(0 if sys.version_info[0]>=3 else 49)" >/dev/null 2>&1; then
      ${py} -c "import sys,hashlib; print(hashlib.sha1(sys.stdin.read().encode()).hexdigest())" <<< "$s" 2>/dev/null
      return $?
    fi
  done
  return 1
}

# ---------------------------------------------------------------------------
# tc_history_cache_path <abs_path> — return cache file path for <abs_path>.
# ---------------------------------------------------------------------------
tc_history_cache_path() {
  local f="${1:-}"
  if [ -z "$f" ]; then return 1; fi
  local cd h
  cd="$(tc_history_cache_dir)" || return 1
  h="$(tc_history_sha1 "$f")" || return 1
  printf '%s/%s.marks' "$cd" "$h"
}

# ---------------------------------------------------------------------------
# tc_history_find_project_root <abs_path> — walk up looking for .git/.
# Returns the project root absolute path on stdout, or empty if not found.
# ---------------------------------------------------------------------------
tc_history_find_project_root() {
  local f="${1:-}"
  if [ -z "$f" ]; then return 1; fi
  local dir
  dir="$(cd "$(dirname "$f")" 2>/dev/null && pwd)" || return 1
  local i=0
  while [ "$i" -lt 100 ]; do
    if [ -d "${dir}/.git" ]; then
      printf '%s' "$dir"
      return 0
    fi
    if [ "$dir" = "/" ] || [[ "$dir" =~ ^[A-Za-z]:/?$ ]]; then
      return 1
    fi
    local parent
    parent="$(dirname "$dir")"
    if [ "$parent" = "$dir" ]; then return 1; fi
    dir="$parent"
    i=$((i+1))
  done
  return 1
}

# ---------------------------------------------------------------------------
# tc_history_log_path <abs_path> — return the audit log path for the
# project containing <abs_path>. Prefers <project-root>/.tc-history.md
# (with project root = first ancestor containing .git/). Falls back to
# the marker's directory; then to the file's own directory.
# ---------------------------------------------------------------------------
tc_history_log_path() {
  local f="${1:-}"
  if [ -z "$f" ]; then return 1; fi
  local root
  root="$(tc_history_find_project_root "$f" 2>/dev/null || true)"
  if [ -n "$root" ]; then
    printf '%s/.tc-history.md' "$root"
    return 0
  fi
  # Fallback: marker's directory.
  local marker
  marker="$(tc_find_marker "$f" 2>/dev/null || true)"
  if [ -n "$marker" ]; then
    printf '%s/.tc-history.md' "$(dirname "$marker")"
    return 0
  fi
  # Final fallback: file's own directory.
  printf '%s/.tc-history.md' "$(cd "$(dirname "$f")" && pwd)"
}
