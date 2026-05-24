#!/usr/bin/env bash
# tc-common.sh — track-changes shared bash library
#
# Sourced by all four track-changes hook scripts (session-start.sh,
# pre-tool-use.sh, stop.sh, user-prompt-submit.sh). Provides session-ID
# resolution, state-directory management, sentinel-file path computation
# and existence check, CRLF normalization, file-type dispatch, and mark-
# number extraction helpers used by the PreToolUse highlight verifier.
#
# Usage:
#   source "$(dirname "$0")/../lib/tc-common.sh"
#
# All paths use forward slashes (MSYS / Git Bash on Windows; native on
# macOS/Linux). The sentinel state directory lives under
# $HOME/.claude/skills/track-changes/state/ — see MakePlan D1, D4.

# Guard against double-sourcing when multiple hook scripts source this file
# in the same shell instance.
[[ -n "${_TC_COMMON_LOADED:-}" ]] && return 0
_TC_COMMON_LOADED=1

set -u

# ---------------------------------------------------------------------------
# tc_session_id — resolve the current Claude Code session ID.
#
# Reads $CLAUDE_SESSION_ID if set (the documented env var per the SessionStart
# hook payload). Falls back to "default" so the skill remains functional in
# environments that do not expose the variable (single-session use, manual
# script invocation, fixture tests). See MakePlan §5 "Open at construction
# time — Sentinel session-ID source": this fallback is the chosen safe
# default; the SessionStart hook may be enhanced to canonicalize later.
# ---------------------------------------------------------------------------
tc_session_id() {
  printf '%s' "${CLAUDE_SESSION_ID:-default}"
}

# ---------------------------------------------------------------------------
# tc_state_dir — return the path to the sentinel state directory, creating
# it (and its parents) if absent. Uses forward slashes for MSYS compat.
# ---------------------------------------------------------------------------
tc_state_dir() {
  local dir="${HOME}/.claude/skills/track-changes/state"
  if [ ! -d "$dir" ]; then
    mkdir -p "$dir" 2>/dev/null || return 1
  fi
  printf '%s' "$dir"
}

# ---------------------------------------------------------------------------
# Sentinel path helpers — v3 only retains the .draft per-turn sentinel.
# /track-on and /track-off were removed in Fix #6 because session-scoped
# toggles reintroduced internal-file friction. The deliberate-invocation
# principle is now served entirely by file-level YAML and folder markers.
# ---------------------------------------------------------------------------
tc_sentinel_path_draft() {
  local dir
  dir="$(tc_state_dir)" || return 1
  printf '%s/%s.draft' "$dir" "$(tc_session_id)"
}

# Backwards-compatible alias: callers expecting "the" sentinel get .draft.
tc_sentinel_path() {
  tc_sentinel_path_draft
}

# Existence check: return 0 if .draft sentinel is present.
tc_sentinel_active_draft() {
  local p; p="$(tc_sentinel_path_draft)" || return 2; [ -f "$p" ]
}

# Backwards-compatible: tc_sentinel_active == draft sentinel check.
tc_sentinel_active() {
  tc_sentinel_active_draft
}

# ---------------------------------------------------------------------------
# tc_find_marker <file_path> — check the file's OWN directory for a
# .tc-tracked marker. No walk-up — markers are folder-local in v3.
# Echoes the marker path on success; non-zero exit + empty on miss.
# ---------------------------------------------------------------------------
tc_find_marker() {
  local file="${1:-}"
  if [ -z "$file" ]; then return 1; fi
  local dir
  dir="$(cd "$(dirname "$file")" 2>/dev/null && pwd)" || return 1
  if [ -f "${dir}/.tc-tracked" ]; then
    printf '%s/.tc-tracked' "$dir"
    return 0
  fi
  return 1
}

# ---------------------------------------------------------------------------
# tc_marker_lists_file <marker_path> <file_path> — given a marker path
# and a file path, decide whether the marker activates tracking for that
# file.
#
# Marker content rules:
#   - Strip comment lines (lines whose first non-whitespace char is `#`).
#   - Strip blank lines.
#   - If nothing remains: presence-only mode → marker activates ALL files
#     in its folder. Echo "all" and return 0.
#   - Otherwise: list mode → marker activates only files whose basename
#     appears as a non-comment, non-blank line. Echo "listed" if the
#     file's basename matches; "off-list" if not.
#
# Echoes "all" | "listed" | "off-list" | "" (on parse failure).
# Returns 0 if "all" or "listed"; non-zero otherwise.
# ---------------------------------------------------------------------------
tc_marker_lists_file() {
  local marker="${1:-}" file="${2:-}"
  if [ -z "$marker" ] || [ ! -f "$marker" ]; then
    printf ''
    return 1
  fi
  # Strip comments + blank lines.
  local body
  body="$(grep -v '^\s*\(#\|$\)' "$marker" 2>/dev/null | sed 's/^\s\+//; s/\s\+$//' | grep -v '^$' || true)"
  if [ -z "$body" ]; then
    printf 'all'
    return 0
  fi
  # List mode: check whether the file's basename is in the list.
  local base
  base="$(basename "$file")"
  if printf '%s\n' "$body" | grep -Fxq -- "$base" 2>/dev/null; then
    printf 'listed'
    return 0
  fi
  printf 'off-list'
  return 1
}

# ---------------------------------------------------------------------------
# tc_is_hidden_file <file_path> — basename starts with `.`. Hidden files
# inside a marked folder are excluded from tracking by built-in convention
# (avoids friction on auto-generated cache/scratch files like .notes.md).
# A file's YAML true override can still force tracking on a hidden file.
# ---------------------------------------------------------------------------
tc_is_hidden_file() {
  local file="${1:-}"
  local base
  base="$(basename "$file")"
  case "$base" in
    .*) return 0 ;;
    *)  return 1 ;;
  esac
}

# ---------------------------------------------------------------------------
# tc_check_yaml_override <file_path> — inspect the file for per-file
# activation override.
#   .md / .qmd: look in YAML frontmatter (top-of-file --- ... ---) for
#               `track-changes: true` or `track-changes: false`.
#   .tex:       look in the first 10 lines for `% track-changes: true|false`.
# Echoes 'on' / 'off' / empty.
# ---------------------------------------------------------------------------
tc_check_yaml_override() {
  local file="${1:-}"
  if [ -z "$file" ] || [ ! -f "$file" ]; then return 0; fi
  local ftype
  ftype="$(tc_file_type "$file")"
  case "$ftype" in
    md|qmd)
      # Read up to the second --- delimiter or first 50 lines, whichever is smaller.
      local in_fm=0 line_no=0
      local val=""
      while IFS= read -r line && [ "$line_no" -lt 50 ]; do
        line_no=$((line_no + 1))
        if [ "$line_no" = "1" ]; then
          if [ "$line" = "---" ]; then in_fm=1; continue; fi
          # No frontmatter; bail.
          break
        fi
        if [ "$in_fm" = "1" ] && [ "$line" = "---" ]; then
          break
        fi
        if [ "$in_fm" = "1" ]; then
          case "$line" in
            track-changes:*true*)  val="on" ;;
            track-changes:*false*) val="off" ;;
          esac
        fi
      done < "$file"
      printf '%s' "$val"
      ;;
    tex)
      # Magic comment in the first 10 lines: % track-changes: true|false
      local line_no=0 val=""
      while IFS= read -r line && [ "$line_no" -lt 10 ]; do
        line_no=$((line_no + 1))
        case "$line" in
          *%*track-changes:*true*)  val="on"  ;;
          *%*track-changes:*false*) val="off" ;;
        esac
      done < "$file"
      printf '%s' "$val"
      ;;
    *)
      printf ''
      ;;
  esac
}

# ---------------------------------------------------------------------------
# tc_should_track <file_path> — resolve activation for this file. Echoes
# one of the reason codes below and returns 0 iff tracking is ON.
#
#   draft               — /draft active (suspend for current turn)
#   off-file            — file YAML/magic-comment = false (overrides marker)
#   on-file             — file YAML/magic-comment = true (overrides marker)
#   on-marker-presence  — folder marker is presence-only (tracks all in folder)
#   on-marker-listed    — folder marker lists this file's basename
#   off-marker-not-listed — folder marker is in list mode but file not listed
#   off-hidden          — hidden file in marked folder (built-in exclusion)
#   off-default         — no marker, no YAML, default off
#
# Precedence: /draft > file YAML > folder marker > default off. The hidden-
# file exclusion applies only when activation would otherwise come from the
# marker (not when forced on by file YAML).
# ---------------------------------------------------------------------------
tc_should_track() {
  local file="${1:-}"
  if [ -z "$file" ]; then printf 'off-default'; return 1; fi

  # 1. Per-turn /draft override (highest precedence).
  if tc_sentinel_active_draft 2>/dev/null; then
    printf 'draft'
    return 1
  fi

  # 2. Per-file YAML / magic comment — overrides marker either way.
  local yaml_val
  yaml_val="$(tc_check_yaml_override "$file")"
  case "$yaml_val" in
    on)  printf 'on-file'; return 0 ;;
    off) printf 'off-file'; return 1 ;;
  esac

  # 3. Folder-local marker.
  local marker
  marker="$(tc_find_marker "$file" 2>/dev/null || true)"
  if [ -n "$marker" ]; then
    # Hidden-file built-in exclusion (only when YAML didn't force on above).
    if tc_is_hidden_file "$file"; then
      printf 'off-hidden'
      return 1
    fi
    local mode
    mode="$(tc_marker_lists_file "$marker" "$file" 2>/dev/null || true)"
    case "$mode" in
      all)      printf 'on-marker-presence';  return 0 ;;
      listed)   printf 'on-marker-listed';    return 0 ;;
      off-list) printf 'off-marker-not-listed'; return 1 ;;
    esac
  fi

  # 4. Default off.
  printf 'off-default'
  return 1
}

# ---------------------------------------------------------------------------
# tc_normalize_eol <file> — strip carriage returns from line endings and
# emit normalized content to stdout. Per MakePlan D1 / Q7 the only whitespace
# normalization applied before diffing is CRLF -> LF; all other whitespace
# (trailing spaces, indentation, EOF newline) is preserved.
# ---------------------------------------------------------------------------
tc_normalize_eol() {
  local file="${1:-}"
  if [ -z "$file" ] || [ ! -f "$file" ]; then
    return 1
  fi
  sed 's/\r$//' "$file"
}

# ---------------------------------------------------------------------------
# tc_file_type <path> — classify a file by its extension. Echoes one of
# md, qmd, tex, or other. Used by the PreToolUse hook to dispatch to the
# correct highlight-syntax matcher (markdown <mark> vs LaTeX \tc{}).
# ---------------------------------------------------------------------------
tc_file_type() {
  local path="${1:-}"
  case "$path" in
    *.md)  printf 'md'  ;;
    *.qmd) printf 'qmd' ;;
    *.tex) printf 'tex' ;;
    *)     printf 'other' ;;
  esac
}

# ---------------------------------------------------------------------------
# tc_extract_mark_numbers <file> — emit all highlight mark numbers found in
# the given file, one per line, in file order. v2 syntax:
#   .md / .qmd: matches </mark><sup>N</sup>
#   .tex:       matches \tcn{N}
# Used by tc_max_n and by the PreToolUse duplicate-N check.
# ---------------------------------------------------------------------------
tc_extract_mark_numbers() {
  local file="${1:-}"
  if [ -z "$file" ] || [ ! -f "$file" ]; then
    return 1
  fi
  local ftype
  ftype="$(tc_file_type "$file")"
  case "$ftype" in
    md|qmd)
      # </mark><sup>N</sup> where N is one or more digits
      grep -oE '</mark><sup>[0-9]+</sup>' "$file" 2>/dev/null \
        | grep -oE '[0-9]+'
      ;;
    tex)
      # \tcn{N} where N is one or more digits
      grep -oE '\\tcn\{[0-9]+\}' "$file" 2>/dev/null \
        | grep -oE '[0-9]+'
      ;;
    *)
      return 0
      ;;
  esac
}

# ---------------------------------------------------------------------------
# tc_max_n <file> — emit the maximum mark number present in the file, or 0
# if the file has no marks (or is off-scope). Sort numerically and take tail.
# ---------------------------------------------------------------------------
tc_max_n() {
  local file="${1:-}"
  local max
  max="$(tc_extract_mark_numbers "$file" 2>/dev/null | sort -n | tail -1)"
  if [ -z "$max" ]; then
    printf '0'
  else
    printf '%s' "$max"
  fi
}

# ---------------------------------------------------------------------------
# tc_log <msg> — append a timestamped log line to the state-directory log
# file. Best-effort; failure to write is silently swallowed so logging
# cannot break a hook.
# ---------------------------------------------------------------------------
tc_log() {
  local msg="${1:-}"
  local dir
  dir="$(tc_state_dir)" || return 0
  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
  printf '%s %s\n' "$ts" "$msg" >> "$dir/tc.log" 2>/dev/null || true
}
