#!/usr/bin/env bash
# handlers/test-response-clarification.sh — PCV v3.14 Gate M6 mechanical handler
#
# Injects scripted clarification responses during test mode (Step 4 planning
# clarification questions). Reads the response mapping file pointed to by
# session-state test_responses_path and echoes the value for key Q<N> (or
# Q<phase>-<N> for multi-phase projects) on stdout.
#
# Idempotency class: repeatable (per gate-inventory.md M6 row). Each invocation
# reads the responses file fresh; no cross-invocation state aside from the
# decision-log append.
#
# Usage:
#   bash test-response-clarification.sh --project-dir <absolute-path> \
#                                       --question <N> [--phase <N>]
#
# Exit codes:
#   0   successful inject (stdout = response value; log + gate-context emitted)
#   1   fallback signal (no response available; hub should accept first option
#       or fall back to interactive prompting)
#   2   argument error

set -u

# ---------------------------------------------------------------------------
# Section 1: Parse arguments
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "${SCRIPT_DIR}/lib.sh"

PROJECT_DIR=""
QUESTION=""
PHASE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project-dir)
      if [ -z "${2:-}" ]; then
        printf 'test-response-clarification.sh: --project-dir requires a path argument\n' >&2
        exit 2
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    --question)
      if [ -z "${2:-}" ]; then
        printf 'test-response-clarification.sh: --question requires an integer argument\n' >&2
        exit 2
      fi
      QUESTION="$2"
      shift 2
      ;;
    --phase)
      if [ -z "${2:-}" ]; then
        printf 'test-response-clarification.sh: --phase requires an integer argument\n' >&2
        exit 2
      fi
      PHASE="$2"
      shift 2
      ;;
    *)
      printf 'test-response-clarification.sh: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if [ -z "${PROJECT_DIR}" ]; then
  printf 'test-response-clarification.sh: --project-dir required\n' >&2
  exit 2
fi
if [ -z "${QUESTION}" ]; then
  printf 'test-response-clarification.sh: --question required\n' >&2
  exit 2
fi

# Basic integer validation on --question and --phase.
case "${QUESTION}" in
  ''|*[!0-9]*)
    printf 'test-response-clarification.sh: --question must be a positive integer (got: %s)\n' "${QUESTION}" >&2
    exit 2
    ;;
esac
if [ -n "${PHASE}" ]; then
  case "${PHASE}" in
    ''|*[!0-9]*)
      printf 'test-response-clarification.sh: --phase must be a positive integer (got: %s)\n' "${PHASE}" >&2
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

# Key computation: single-phase Q<N>; multi-phase Q<phase>-<N>.
if [ -n "${PHASE}" ]; then
  KEY="Q${PHASE}-${QUESTION}"
else
  KEY="Q${QUESTION}"
fi

# ---------------------------------------------------------------------------
# Section 3: Decide — action path selection
# ---------------------------------------------------------------------------
#
# Branch priority:
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
      "M6" \
      "mechanical" \
      "Inject test response for Q${QUESTION}?" \
      "" \
      "~/.claude/skills/pcv/handlers/test-response-clarification.sh" \
      "${DECISION_CONTEXT}" \
      "freeform"
    EMIT_RC=$?
    if [ "${EMIT_RC}" -ne 0 ]; then
      printf 'test-response-clarification.sh: failed to emit gate-context.json\n' >&2
      exit 1
    fi
    ;;
esac

# ---------------------------------------------------------------------------
# Section 5: Act + log + footer + exit
# ---------------------------------------------------------------------------

case "${BRANCH}" in
  A)
    printf 'test mode not active; use interactive clarification\n' >&2
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

    log_decision "${PROJECT_DIR}" "M6 test-response-clarification" "\
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
    printf 'test-response-clarification.sh: internal error — no branch selected\n' >&2
    exit 1
    ;;
esac
