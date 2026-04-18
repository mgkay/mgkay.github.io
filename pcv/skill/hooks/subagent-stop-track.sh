#!/usr/bin/env bash
# subagent-stop-track.sh — PCV v3.11 Phase 1 SubagentStop builder tracker
#
# Purpose:
#   On each SubagentStop event, if the subagent_type is "builder" (or contains
#   "builder"), append one tab-separated line to pcvplans/logs/builder-tracker.log
#   in the current PCV project. Used to track builder subagent completions for
#   Phase 1 verification and future Phase 2/3 analytics.
#
# Event:
#   SubagentStop
#
# Expected payload fields (confirmed by C1 spike probe):
#   subagent_type  — type of subagent that stopped (e.g., "builder", "general-purpose")
#   model          — model used by the subagent (e.g., "claude-opus-4-5")
#   status         — completion status (e.g., "success", "error")
#
# Exit semantics:
#   Always exits 0. This script never blocks or signals an error.
#   Non-PCV directories, opt-out marker, empty stdin, and missing fields all
#   produce a silent exit 0. Only builder-type subagents produce log output.
#
# Tracking file format:
#   $PROJECT_DIR/pcvplans/logs/builder-tracker.log
#   One line per builder subagent stop:
#     TIMESTAMP<TAB>subagent_type<TAB>model<TAB>status
#   Example:
#     2026-04-07T14:23:01Z	builder	claude-opus-4-5	success
#
# Pure bash: no jq, no Python, no Node. Uses grep/sed for JSON field extraction.

# ── 1. Read stdin (event payload JSON; may be empty or absent) ──────────────

PAYLOAD=""
if [ ! -t 0 ]; then
  PAYLOAD="$(cat)"
fi

# ── 2. Resolve canonical project root ───────────────────────────────────────

if [ -n "${CLAUDE_PROJECT_DIR}" ]; then
  PROJECT_DIR="${CLAUDE_PROJECT_DIR}"
else
  PROJECT_DIR="${PWD}"
fi

LOGS_DIR="${PROJECT_DIR}/pcvplans/logs"

# ── 3. PCV-detect: if logs dir absent, not a PCV project — exit silently ────

if [ ! -d "${LOGS_DIR}" ]; then
  exit 0
fi

# ── 4. Opt-out check: honor .pcv-hooks-opted-out sentinel file ──────────────

if [ -f "${PROJECT_DIR}/.claude/.pcv-hooks-opted-out" ]; then
  exit 0
fi

# ── 5. Extract fields from JSON payload (pure grep/sed, no jq) ──────────────

# Helper: extract a string value for a given key from $PAYLOAD.
# Handles both "key":"value" and "key": "value" (with optional space).
extract_field() {
  local key="$1"
  local value
  value="$(printf '%s' "${PAYLOAD}" \
    | grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" \
    | sed "s/\"${key}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\"/\1/" \
    | head -1)"
  if [ -z "${value}" ]; then
    printf 'unknown'
  else
    printf '%s' "${value}"
  fi
}

SUBAGENT_TYPE="$(extract_field "subagent_type")"
MODEL="$(extract_field "model")"
STATUS="$(extract_field "status")"

# ── 6. Filter: only log builder-type subagents ───────────────────────────────

case "${SUBAGENT_TYPE}" in
  *builder*)
    : ;;  # fall through to logging
  *)
    exit 0
    ;;
esac

# ── 7. Append tracker line ───────────────────────────────────────────────────

TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")"
TRACKER_FILE="${LOGS_DIR}/builder-tracker.log"

printf '%s\t%s\t%s\t%s\n' \
  "${TIMESTAMP}" \
  "${SUBAGENT_TYPE}" \
  "${MODEL}" \
  "${STATUS}" \
  >> "${TRACKER_FILE}"

exit 0
