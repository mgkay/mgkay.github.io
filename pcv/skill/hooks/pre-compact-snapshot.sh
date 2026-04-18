#!/usr/bin/env bash
# pre-compact-snapshot.sh — PCV v3.12 PreCompact state snapshot
#
# Purpose:
#   On each PreCompact event, write a minimal JSON snapshot of the current PCV
#   project state to pcvplans/logs/pcv-state.json. The SessionStart resume hook
#   (C4) reads this file to inject a one-line status into additionalContext on
#   session restart.
#
# Survival assumption:
#   pcvplans/logs/pcv-state.json lives on disk. Compaction operates on conversation
#   context only; it does not touch files under pcvplans/logs/. The snapshot
#   therefore survives compaction by construction.
#
# Advisory nature and race tolerance:
#   This snapshot is advisory infrastructure. The last_decision_entry_header
#   field may reflect a partially-written decision-log entry if a write race
#   occurs; this is tolerated by the SessionStart resume hook. Correctness lives
#   in the on-disk PCV files, not in the snapshot.
#
# Atomic write:
#   The hook writes to pcvplans/logs/pcv-state.json.tmp and renames via mv to
#   guarantee the snapshot file is never half-written. Mid-write interruption
#   leaves either the old file intact (if mv has not yet run) or a complete new
#   file (if mv succeeded). .tmp file is never left behind after a successful
#   run.
#
# Event:
#   PreCompact
#
# Expected payload fields (confirmed by C1 spike probe):
#   (PreCompact payload not probed directly; script treats stdin as advisory and
#   does not depend on any payload field — project state is derived from disk.)
#
# Snapshot payload fields written to pcv-state.json:
#   phase                          — "single" | "<phase-dir-basename>" (multi-phase)
#   milestone                      — "charging" | "planning" | "constructing" |
#                                    "verifying" | "complete"
#   last_decision_entry_header     — last "## " header line from decision-log.md,
#                                    or "none" if file absent or no headers found
#   current_make_plan_exists       — "true" | "false"
#   current_construction_plan_exists — "true" | "false"
#   snapshot_timestamp             — ISO-8601 UTC timestamp at time of write
#
# Exit semantics:
#   Always exits 0. This script never blocks or signals an error.
#   Non-PCV directories, opt-out marker, empty stdin, and missing files all
#   produce a silent exit 0.

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

# ── 5. Determine phase ───────────────────────────────────────────────────────
#
# Multi-phase detection: look for pcvplans/logs/master-log.md one directory above
# PROJECT_DIR. If found, the current cwd basename is the phase name; otherwise
# the project is single-phase.

PARENT_DIR="$(dirname "${PROJECT_DIR}")"
MASTER_LOG="${PARENT_DIR}/pcvplans/logs/master-log.md"

if [ -f "${MASTER_LOG}" ]; then
  PHASE="$(basename "${PROJECT_DIR}")"
else
  PHASE="single"
fi

# ── 6. Determine milestone ───────────────────────────────────────────────────
#
# Logic (in order of precedence):
#   No make-plan.md                                         → charging
#   make-plan.md exists, no construction-plan.md            → planning
#   construction-plan.md exists, decision-log has no
#     "## Verification" header                              → constructing
#   decision-log has "## Verification" but no
#     "## Project Closeout" header                          → verifying
#   decision-log has "## Project Closeout" header           → complete

MAKE_PLAN="${PROJECT_DIR}/pcvplans/make-plan.md"
CONSTRUCTION_PLAN="${PROJECT_DIR}/pcvplans/construction-plan.md"
DECISION_LOG="${LOGS_DIR}/decision-log.md"

if [ ! -f "${MAKE_PLAN}" ]; then
  MILESTONE="charging"
elif [ ! -f "${CONSTRUCTION_PLAN}" ]; then
  MILESTONE="planning"
else
  # construction-plan exists — check decision log for phase markers
  HAS_VERIFICATION="false"
  HAS_CLOSEOUT="false"
  if [ -f "${DECISION_LOG}" ]; then
    if grep -q "^## Verification" "${DECISION_LOG}"; then
      HAS_VERIFICATION="true"
    fi
    if grep -q "^## Project Closeout" "${DECISION_LOG}"; then
      HAS_CLOSEOUT="true"
    fi
  fi

  if [ "${HAS_CLOSEOUT}" = "true" ]; then
    MILESTONE="complete"
  elif [ "${HAS_VERIFICATION}" = "true" ]; then
    MILESTONE="verifying"
  else
    MILESTONE="constructing"
  fi
fi

# ── 7. Capture make/construction-plan existence flags ───────────────────────

if [ -f "${MAKE_PLAN}" ]; then
  MAKE_PLAN_EXISTS="true"
else
  MAKE_PLAN_EXISTS="false"
fi

if [ -f "${CONSTRUCTION_PLAN}" ]; then
  CONSTRUCTION_PLAN_EXISTS="true"
else
  CONSTRUCTION_PLAN_EXISTS="false"
fi

# ── 8. Extract last "## " header from decision log ──────────────────────────

LAST_HEADER="none"
if [ -f "${DECISION_LOG}" ]; then
  LAST_HEADER_RAW="$(grep "^## " "${DECISION_LOG}" | tail -1)"
  if [ -n "${LAST_HEADER_RAW}" ]; then
    # Strip leading "## " prefix and any trailing whitespace for compact JSON value
    LAST_HEADER="$(printf '%s' "${LAST_HEADER_RAW}" | sed 's/^## //' | sed 's/[[:space:]]*$//')"
  fi
fi

# ── 8b. Extract milestones_reached array from decision log ──────────────────

MILESTONES_JSON="[]"
if [ -f "${DECISION_LOG}" ]; then
  MILESTONE_TAGS="$(grep -oE '\[MILESTONE:[A-Z_0-9]+\]' "${DECISION_LOG}" 2>/dev/null | sed 's/\[MILESTONE://;s/\]//' | sort -u)"
  if [ -n "${MILESTONE_TAGS}" ]; then
    MILESTONES_JSON="["
    FIRST=1
    while IFS= read -r tag; do
      [ -z "$tag" ] && continue
      if [ $FIRST -eq 1 ]; then
        MILESTONES_JSON="${MILESTONES_JSON}\"${tag}\""
        FIRST=0
      else
        MILESTONES_JSON="${MILESTONES_JSON},\"${tag}\""
      fi
    done <<HERE
${MILESTONE_TAGS}
HERE
    MILESTONES_JSON="${MILESTONES_JSON}]"
  fi
fi

# ── 9. Capture timestamp ─────────────────────────────────────────────────────

TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date +"%Y-%m-%dT%H:%M:%SZ")"

# ── 10. Sanitize string values for JSON (escape backslash and double-quote) ──
#
# Values from the decision log may contain characters that break JSON string
# literals. Escape \ first, then ".

sanitize_json() {
  printf '%s' "$1" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g'
}

PHASE_SAFE="$(sanitize_json "${PHASE}")"
MILESTONE_SAFE="$(sanitize_json "${MILESTONE}")"
LAST_HEADER_SAFE="$(sanitize_json "${LAST_HEADER}")"
TIMESTAMP_SAFE="$(sanitize_json "${TIMESTAMP}")"

# ── 11. Write snapshot atomically ────────────────────────────────────────────

TMP_FILE="${LOGS_DIR}/pcv-state.json.tmp"
FINAL_FILE="${LOGS_DIR}/pcv-state.json"

printf '{\n  "phase": "%s",\n  "milestone": "%s",\n  "last_decision_entry_header": "%s",\n  "current_make_plan_exists": "%s",\n  "current_construction_plan_exists": "%s",\n  "snapshot_timestamp": "%s",\n  "milestones_reached": %s\n}\n' \
  "${PHASE_SAFE}" \
  "${MILESTONE_SAFE}" \
  "${LAST_HEADER_SAFE}" \
  "${MAKE_PLAN_EXISTS}" \
  "${CONSTRUCTION_PLAN_EXISTS}" \
  "${TIMESTAMP_SAFE}" \
  "${MILESTONES_JSON}" \
  > "${TMP_FILE}"

mv "${TMP_FILE}" "${FINAL_FILE}"

exit 0
