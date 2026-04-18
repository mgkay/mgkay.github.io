#!/usr/bin/env bash
# handlers/scope-creep-trigger.sh — PCV v3.14 Gate M8 mechanical handler
#
# Mechanical arithmetic trigger for the scope-creep check
# (per pcv-common.md Scope-Creep Check, lines 192–220).
#
# Evaluates three thresholds against proposed-scope metadata passed by the hub:
#   - new_files_count        >= 3
#   - changed_files_count    >= 3
#   - out_of_plan_decisions  == true
#
# If any threshold is met, emits a gate-context for the follow-on judgment gate
# J16-scope-creep-response (the a/b/c response is a judgment gate presented by
# the hub; this handler only makes the trigger deterministic). If no threshold
# is met, emits nothing and exits 1 so the hub can skip J16.
#
# Idempotency class: repeatable (per MakePlan Assumption #9 and gate-inventory
# M8 row — each invocation evaluates fresh inputs; no state persists between
# runs).
#
# Usage:
#   bash scope-creep-trigger.sh \
#     --project-dir <absolute-path> \
#     --new-files-count <N> \
#     --changed-files-count <N> \
#     --out-of-plan-decisions <true|false>
#
# Exit codes:
#   0   at least one threshold met; gate-context emitted for J16, log entry
#       appended, hub should present J16
#   1   all thresholds below; no gate-context, no log entry, hub skips J16
#   2   argument error (missing, unknown, or malformed flag/value)

set -u  # undefined vars are errors; do NOT use set -e (errors are per-command)

# ---------------------------------------------------------------------------
# Section 1: Parse arguments
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "${SCRIPT_DIR}/lib.sh"

PROJECT_DIR=""
NEW_FILES_COUNT=""
CHANGED_FILES_COUNT=""
OUT_OF_PLAN=""

while [ $# -gt 0 ]; do
  case "$1" in
    --project-dir)
      if [ -z "${2:-}" ]; then
        printf 'scope-creep-trigger.sh: --project-dir requires a path argument\n' >&2
        exit 2
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    --new-files-count)
      if [ -z "${2:-}" ]; then
        printf 'scope-creep-trigger.sh: --new-files-count requires an integer argument\n' >&2
        exit 2
      fi
      NEW_FILES_COUNT="$2"
      shift 2
      ;;
    --changed-files-count)
      if [ -z "${2:-}" ]; then
        printf 'scope-creep-trigger.sh: --changed-files-count requires an integer argument\n' >&2
        exit 2
      fi
      CHANGED_FILES_COUNT="$2"
      shift 2
      ;;
    --out-of-plan-decisions)
      if [ -z "${2:-}" ]; then
        printf 'scope-creep-trigger.sh: --out-of-plan-decisions requires "true" or "false"\n' >&2
        exit 2
      fi
      OUT_OF_PLAN="$2"
      shift 2
      ;;
    *)
      printf 'scope-creep-trigger.sh: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

# Required-flag presence checks.
if [ -z "${PROJECT_DIR}" ]; then
  printf 'scope-creep-trigger.sh: --project-dir required\n' >&2
  exit 2
fi
if [ -z "${NEW_FILES_COUNT}" ]; then
  printf 'scope-creep-trigger.sh: --new-files-count required\n' >&2
  exit 2
fi
if [ -z "${CHANGED_FILES_COUNT}" ]; then
  printf 'scope-creep-trigger.sh: --changed-files-count required\n' >&2
  exit 2
fi
if [ -z "${OUT_OF_PLAN}" ]; then
  printf 'scope-creep-trigger.sh: --out-of-plan-decisions required\n' >&2
  exit 2
fi

# Integer validation (non-negative integers only) for the two count arguments.
case "${NEW_FILES_COUNT}" in
  ''|*[!0-9]*)
    printf 'scope-creep-trigger.sh: --new-files-count must be a non-negative integer (got: %s)\n' \
      "${NEW_FILES_COUNT}" >&2
    exit 2
    ;;
esac
case "${CHANGED_FILES_COUNT}" in
  ''|*[!0-9]*)
    printf 'scope-creep-trigger.sh: --changed-files-count must be a non-negative integer (got: %s)\n' \
      "${CHANGED_FILES_COUNT}" >&2
    exit 2
    ;;
esac

# Boolean validation: must be the literal string "true" or "false".
if [ "${OUT_OF_PLAN}" != "true" ] && [ "${OUT_OF_PLAN}" != "false" ]; then
  printf 'scope-creep-trigger.sh: --out-of-plan-decisions must be "true" or "false" (got: %s)\n' \
    "${OUT_OF_PLAN}" >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Section 2: Evaluate thresholds
# ---------------------------------------------------------------------------
#
# Per pcv-common.md Scope-Creep Check lines 198–200:
#   - new_files_count >= 3 → trigger
#   - changed_files_count >= 3 → trigger
#   - out_of_plan_decisions == true → trigger
#
# Collect the fired triggers into TRIGGERS (semicolon-space delimited) so we
# can compose a single-line rationale naming the specific threshold(s).

TRIGGERS=""

if [ "${NEW_FILES_COUNT}" -ge 3 ]; then
  TRIGGERS="new_files=${NEW_FILES_COUNT}"
fi

if [ "${CHANGED_FILES_COUNT}" -ge 3 ]; then
  if [ -z "${TRIGGERS}" ]; then
    TRIGGERS="changed_files=${CHANGED_FILES_COUNT}"
  else
    TRIGGERS="${TRIGGERS}; changed_files=${CHANGED_FILES_COUNT}"
  fi
fi

if [ "${OUT_OF_PLAN}" = "true" ]; then
  if [ -z "${TRIGGERS}" ]; then
    TRIGGERS="out_of_plan=true"
  else
    TRIGGERS="${TRIGGERS}; out_of_plan=true"
  fi
fi

# ---------------------------------------------------------------------------
# Section 3: Branch A — below threshold (no triggers fired)
# ---------------------------------------------------------------------------
if [ -z "${TRIGGERS}" ]; then
  # Diagnostic to stderr only; no gate-context, no decision-log entry.
  printf 'scope-creep check: below threshold (new=%s, changed=%s, out_of_plan=%s)\n' \
    "${NEW_FILES_COUNT}" "${CHANGED_FILES_COUNT}" "${OUT_OF_PLAN}" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Section 4: Branch B — triggered; emit gate-context for J16
# ---------------------------------------------------------------------------
RATIONALE="scope-creep: ${TRIGGERS}"

DECISION_CONTEXT="new_files:${NEW_FILES_COUNT};changed_files:${CHANGED_FILES_COUNT};out_of_plan:${OUT_OF_PLAN};triggers:${TRIGGERS}"

# Emit gate-context for the *follow-on* judgment gate. gate_type="judgment"
# because the a/b/c response the hub will present to the user is a judgment
# decision; handler_script=null for the same reason.
emit_gate_context \
  "${PROJECT_DIR}" \
  "J16-scope-creep-response" \
  "judgment" \
  "Scope-creep threshold crossed: ${RATIONALE}. Options?" \
  "approve_in_scope,defer_new_phase,reduce_scope" \
  "" \
  "${DECISION_CONTEXT}" \
  "letter"
EMIT_RC=$?
if [ "${EMIT_RC}" -ne 0 ]; then
  printf 'scope-creep-trigger.sh: failed to emit gate-context.json\n' >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Section 5: Print rationale + footer + log + exit
# ---------------------------------------------------------------------------
printf '%s\n' "${RATIONALE}"
print_mechanical_footer

log_decision "${PROJECT_DIR}" "M8 scope-creep-trigger" "\
**Trigger:** ${RATIONALE}
**Metrics:** new_files=${NEW_FILES_COUNT}; changed_files=${CHANGED_FILES_COUNT}; out_of_plan=${OUT_OF_PLAN}
**Emitted gate-context for:** J16-scope-creep-response"

exit 0
