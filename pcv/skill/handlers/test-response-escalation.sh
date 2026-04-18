#!/usr/bin/env bash
# handlers/test-response-escalation.sh — PCV v3.14 Gate M7 mechanical handler
#
# Injects scripted critic-escalation responses during test mode (Step 6
# critic-gate escalations). Reads the response mapping file pointed to by
# session-state test_responses_path and echoes the value for key E<N> (or
# E<phase>-<N> for multi-phase projects) on stdout.
#
# Mirrors M6 (test-response-clarification.sh) structurally; differs only in
# argument name (--escalation), key prefix (E vs Q), and gate_id (M7 vs M6).
#
# Idempotency class: repeatable (per gate-inventory.md M7 row). Each invocation
# reads the responses file fresh; no cross-invocation state aside from the
# decision-log append.
#
# Usage:
#   bash test-response-escalation.sh --project-dir <absolute-path> \
#                                    --escalation <N> [--phase <N>]
#
# Exit codes:
#   0   successful inject (stdout = response value; log + gate-context emitted)
#   1   fallback signal (no response available; hub should accept proposed
#       resolution or fall back to interactive prompting)
#   2   argument error

set -u

# ---------------------------------------------------------------------------
# Section 1: Parse arguments
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "${SCRIPT_DIR}/lib.sh"

PROJECT_DIR=""
ESCALATION=""
PHASE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project-dir)
      if [ -z "${2:-}" ]; then
        printf 'test-response-escalation.sh: --project-dir requires a path argument\n' >&2
        exit 2
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    --escalation)
      if [ -z "${2:-}" ]; then
        printf 'test-response-escalation.sh: --escalation requires an integer argument\n' >&2
        exit 2
      fi
      ESCALATION="$2"
      shift 2
      ;;
    --phase)
      if [ -z "${2:-}" ]; then
        printf 'test-response-escalation.sh: --phase requires an integer argument\n' >&2
        exit 2
      fi
      PHASE="$2"
      shift 2
      ;;
    *)
      printf 'test-response-escalation.sh: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if [ -z "${PROJECT_DIR}" ]; then
  printf 'test-response-escalation.sh: --project-dir required\n' >&2
  exit 2
fi
if [ -z "${ESCALATION}" ]; then
  printf 'test-response-escalation.sh: --escalation required\n' >&2
  exit 2
fi

# Basic integer validation on --escalation and --phase.
case "${ESCALATION}" in
  ''|*[!0-9]*)
    printf 'test-response-escalation.sh: --escalation must be a positive integer (got: %s)\n' "${ESCALATION}" >&2
    exit 2
    ;;
esac
if [ -n "${PHASE}" ]; then
  case "${PHASE}" in
    ''|*[!0-9]*)
      printf 'test-response-escalation.sh: --phase must be a positive integer (got: %s)\n' "${PHASE}" >&2
      exit 2
      ;;
  esac
fi

# ---------------------------------------------------------------------------
# Section 2: State check — read session-state and compute lookup key
# ---------------------------------------------------------------------------
TEST_MODE="false"
TEST_RESPONSES_PATH=""
while IFS= read -r ss_line; do
  case "${ss_line}" in
    test_mode=*)             TEST_MODE="${ss_line#test_mode=}" ;;
    test_responses_path=*)   TEST_RESPONSES_PATH="${ss_line#test_responses_path=}" ;;
  esac
done < <(read_session_state "${PROJECT_DIR}")

# Key computation: single-phase E<N>; multi-phase E<phase>-<N>.
if [ -n "${PHASE}" ]; then
  KEY="E${PHASE}-${ESCALATION}"
else
  KEY="E${ESCALATION}"
fi

# ---------------------------------------------------------------------------
# Section 3: Decide — action path selection
# ---------------------------------------------------------------------------
#
# Branch priority (mirrors M6):
#   A  test_mode=false                       — inactive, no emit, exit 1
#   B  test_mode=true, no responses_path     — warn, exit 1
#   C  test_mode=true, path set, file bad    — warn, exit 1
#   D  test_mode=true, key present           — inject, log, emit, exit 0
#   E  test_mode=true, key missing/empty     — fallback-accept-first, emit, exit 1

BRANCH=""
MATCH="false"
ACTION=""
RESPONSE_VALUE=""
LOOKUP_RC=0

if [ "${TEST_MODE}" != "true" ]; then
  BRANCH="A"
  ACTION="inactive"
elif [ -z "${TEST_RESPONSES_PATH}" ]; then
  BRANCH="B"
  ACTION="fallback-accept-first"
elif [ ! -f "${TEST_RESPONSES_PATH}" ] || [ ! -r "${TEST_RESPONSES_PATH}" ]; then
  BRANCH="C"
  ACTION="fallback-accept-first"
else
  RESPONSE_VALUE="$(_pcv_test_response_lookup "${TEST_RESPONSES_PATH}" "${KEY}")"
  LOOKUP_RC=$?
  if [ "${LOOKUP_RC}" -eq 0 ] && [ -n "${RESPONSE_VALUE}" ]; then
    BRANCH="D"
    ACTION="inject"
    MATCH="true"
  else
    BRANCH="E"
    ACTION="fallback-accept-first"
  fi
fi

DECISION_CONTEXT="test_mode:${TEST_MODE};responses_path:${TEST_RESPONSES_PATH};key:${KEY};match:${MATCH};action:${ACTION}"

# ---------------------------------------------------------------------------
# Section 4: Gate-context emission
# ---------------------------------------------------------------------------
# Branch A (inactive) emits no gate-context: state is non-applicable per spec.
# Branches B/C/D/E all emit so the hub has a consistent artifact.

case "${BRANCH}" in
  A)
    : # no emit
    ;;
  B|C|D|E)
    emit_gate_context \
      "${PROJECT_DIR}" \
      "M7" \
      "mechanical" \
      "Inject test response for E${ESCALATION}?" \
      "" \
      "~/.claude/skills/pcv/handlers/test-response-escalation.sh" \
      "${DECISION_CONTEXT}" \
      "freeform"
    EMIT_RC=$?
    if [ "${EMIT_RC}" -ne 0 ]; then
      printf 'test-response-escalation.sh: failed to emit gate-context.json\n' >&2
      exit 1
    fi
    ;;
esac

# ---------------------------------------------------------------------------
# Section 5: Act + log + footer + exit
# ---------------------------------------------------------------------------

case "${BRANCH}" in
  A)
    printf 'test mode not active; use interactive escalation\n' >&2
    exit 1
    ;;

  B)
    printf 'test mode active but PCV_TEST_RESPONSES unset\n' >&2
    exit 1
    ;;

  C)
    printf 'test responses file not readable: %s\n' "${TEST_RESPONSES_PATH}" >&2
    exit 1
    ;;

  D)
    # Inject the scripted response verbatim on stdout, then the footer.
    printf '%s\n' "${RESPONSE_VALUE}"
    print_mechanical_footer

    log_decision "${PROJECT_DIR}" "M7 test-response-escalation" "\
**Key:** ${KEY}
**Response:** ${RESPONSE_VALUE}
**Decision context:** ${DECISION_CONTEXT}"
    exit 0
    ;;

  E)
    printf 'no test response for %s; hub should accept first option\n' "${KEY}" >&2
    exit 1
    ;;

  *)
    printf 'test-response-escalation.sh: internal error — no branch selected\n' >&2
    exit 1
    ;;
esac
