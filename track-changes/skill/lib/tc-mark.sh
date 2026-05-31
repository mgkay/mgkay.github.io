#!/usr/bin/env bash
# tc-mark.sh — track-changes .tc-tracked marker writer (shared library)
#
# Self-contained marker-writing functions shared by install.sh (--mark /
# --mark-files) and lib/tc-cli.sh (/tc mark). The marker content here is the
# single source of truth for both entry points — keep the heredoc text in
# sync with SKILL.md §9.
#
# Usage:
#   source "$(dirname "$0")/tc-mark.sh"
#   tc_mark_presence <dir> <force>            # presence-only marker
#   tc_mark_list     <dir> <force> <file>...  # list-mode marker
#
# Both functions are self-contained: they do NOT depend on the caller's
# log/warn/err helpers. They emit user-facing progress on stdout and
# warnings/errors on stderr via local printf emitters, so the same messages
# appear whether invoked from install.sh or tc-cli.sh.
#
# <force> is "1" to overwrite an existing marker, anything else to leave an
# existing marker in place (idempotent — the user may have customized it).
#
# Exit/return codes (mirror install.sh's --mark/--mark-files contract):
#   0  marker written (or already present and left in place)
#   1  argument error (target not a directory; no filenames for list mode)
#   2  write failed

# Guard against double-sourcing when both install.sh and a sourced caller
# pull this file into the same shell instance.
[[ -n "${_TC_MARK_LOADED:-}" ]] && return 0
_TC_MARK_LOADED=1

# ---------------------------------------------------------------------------
# Local emitters — self-contained (no dependency on the caller's log/warn/err).
# Keep the prefix identical to install.sh's helpers so messages read the same.
# ---------------------------------------------------------------------------
_tc_mark_log()  { printf '[track-changes] %s\n' "$*"; }
_tc_mark_warn() { printf '[track-changes] warning: %s\n' "$*" >&2; }
_tc_mark_err()  { printf '[track-changes] error: %s\n' "$*" >&2; }

# ---------------------------------------------------------------------------
# tc_mark_presence <dir> <force> — write a presence-only .tc-tracked marker at
# <dir> with the documented self-describing content (SKILL.md §9). Idempotent:
# if a .tc-tracked file already exists at <dir> and <force> != 1, leave it
# alone (the user may have customized the comment) and report.
# ---------------------------------------------------------------------------
tc_mark_presence() {
  local dir="$1" force="${2:-0}"
  if [ ! -d "${dir}" ]; then
    _tc_mark_err "--mark: target is not a directory: ${dir}"
    return 1
  fi
  local marker="${dir}/.tc-tracked"
  if [ -f "${marker}" ] && [ "${force}" -ne 1 ]; then
    _tc_mark_log "${marker} already exists — leaving in place (use --force to overwrite)"
    return 0
  fi
  cat > "${marker}" <<'TCMARKER'
# track-changes marker (kept in git)
#
# Presence of this file activates the track-changes skill for .md / .qmd
# / .tex files in THIS folder only (no walk-up, no subfolders).
#
# This marker has no filename entries below, so it operates in
# PRESENCE-ONLY mode: every .md / .qmd / .tex file in this folder is
# tracked. To track only specific files, replace this comment with a
# list of filenames (one per line). To track files in a subfolder, drop
# a separate .tc-tracked there.
#
# The track-changes skill (~/.claude/skills/track-changes/) requires
# Claude to wrap every edit it introduces in a <mark> highlight followed
# by a <sup>N</sup> reference number, so the human author retains visual
# review control over AI-introduced changes.
#
# Per-file opt-out:   add `tc-track: false` to YAML frontmatter
#                     (or `% tc-track: false` near the top for .tex).
# Per-turn disable:   invoke /draft or /tc draft in Claude Code.
# Hidden files:       basenames starting with `.` are excluded by default.
# Remove tracking:    delete this file.
#
# Install / management:
#   /tc mark [<dir>]                     drop a presence-only marker
#   /tc mark <dir> <file1> [<file2>...]  drop a list-mode marker
#   /tc enable <file>                    per-file YAML opt-in
#   /tc disable <file>                   per-file YAML opt-out
#   /tc status [<file>]                  inspect activation chain
#   /tc migrate <dir>                    convert v1 marks to v2
TCMARKER
  if [ $? -ne 0 ]; then
    _tc_mark_err "failed to write ${marker}"
    return 2
  fi
  _tc_mark_log "wrote ${marker}"
  _tc_mark_log "  track-changes is now active for .md/.qmd/.tex files in this folder"
  _tc_mark_log "  (no walk-up, no subfolders — drop separate markers per folder)"
  return 0
}

# ---------------------------------------------------------------------------
# tc_mark_list <dir> <force> <file1> [<file2> ...] — write a list-mode marker.
# ---------------------------------------------------------------------------
tc_mark_list() {
  local dir="$1" force="${2:-0}"; shift 2
  if [ ! -d "${dir}" ]; then
    _tc_mark_err "--mark-files: target is not a directory: ${dir}"
    return 1
  fi
  if [ $# -lt 1 ]; then
    _tc_mark_err "--mark-files: at least one filename required"
    return 1
  fi
  local marker="${dir}/.tc-tracked"
  if [ -f "${marker}" ] && [ "${force}" -ne 1 ]; then
    _tc_mark_log "${marker} already exists — leaving in place (use --force to overwrite)"
    return 0
  fi
  {
    cat <<'TCMARKER_HEAD'
# track-changes marker (kept in git) — LIST MODE
#
# The non-comment lines below name the files in THIS folder to track.
# Files NOT listed here are NOT tracked, even though this marker exists.
# Comments (#) and blank lines are ignored.
#
# Per-file opt-out (overrides this list): add `tc-track: false`
#   to the file's YAML frontmatter or `% tc-track: false` in .tex.
# Per-turn disable: /draft or /tc draft.
# Hidden basenames (starting with `.`) are excluded by default.
#
# Management:
#   /tc enable <file>     per-file YAML opt-in (alternative to listing)
#   /tc status <file>     inspect activation chain
#   /tc migrate <dir>     convert v1 marks to v2

TCMARKER_HEAD
    for f in "$@"; do
      printf '%s\n' "$f"
    done
  } > "${marker}"
  if [ $? -ne 0 ]; then
    _tc_mark_err "failed to write ${marker}"
    return 2
  fi
  _tc_mark_log "wrote ${marker} (list mode: $# file(s))"
  for f in "$@"; do _tc_mark_log "  - $f"; done
  return 0
}
