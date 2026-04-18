#!/usr/bin/env bash
# handlers/plan-tier.sh — PCV v3.14 Gate M2 mechanical handler
#
# Ensures ~/.claude/pcv-config.json has plan_tier set. Repeatable per
# MakePlan Assumption #9: each invocation reads/prompts as needed; writes
# config once.
#
# Idempotency class: repeatable (per gate-inventory.md M2 row).
# Announce + execute semantics (non-blocking).
#
# Usage:
#   bash plan-tier.sh --project-dir <absolute-path>
#
# Branches:
#   A  config present, fresh (≤6 months) — read silently, no log, no emit
#   B  config present, stale (>6 months) — read with rationale, emit, log
#   C  config missing, test_mode=true    — auto-write "pro", emit, log
#   D  config missing, test_mode=false   — emit prompt for hub, no write
#
# Exit codes:
#   0   success (any branch)
#   1   I/O failure (emit or log)
#   2   argument error

set -u

# ---------------------------------------------------------------------------
# Section 1: Parse arguments
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "${SCRIPT_DIR}/lib.sh"

PROJECT_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project-dir)
      if [ -z "${2:-}" ]; then
        printf 'plan-tier.sh: --project-dir requires a path argument\n' >&2
        exit 2
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    *)
      printf 'plan-tier.sh: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if [ -z "${PROJECT_DIR}" ]; then
  printf 'plan-tier.sh: --project-dir required\n' >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Section 2: State check — read pcv-config.json and session-state
# ---------------------------------------------------------------------------
CONFIG_FILE="${HOME}/.claude/pcv-config.json"

CONFIG_EXISTS="false"
STALE="false"
TIER_READ=""
SET_DATE=""

if [ -f "${CONFIG_FILE}" ]; then
  CONFIG_EXISTS="true"

  # Parse plan_tier (string value).
  raw_tier="$(grep -o '"plan_tier"[[:space:]]*:[[:space:]]*"[^"]*"' "${CONFIG_FILE}" 2>/dev/null | head -n 1)"
  if [ -n "${raw_tier}" ]; then
    TIER_READ="$(printf '%s' "${raw_tier}" | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/')"
  fi

  # Parse plan_tier_set_date (string value, YYYY-MM-DD).
  raw_date="$(grep -o '"plan_tier_set_date"[[:space:]]*:[[:space:]]*"[^"]*"' "${CONFIG_FILE}" 2>/dev/null | head -n 1)"
  if [ -n "${raw_date}" ]; then
    SET_DATE="$(printf '%s' "${raw_date}" | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/')"
  fi

  # Determine staleness: >6 months (~180 days) since SET_DATE.
  if [ -n "${SET_DATE}" ]; then
    # Compute days between SET_DATE and today. Use date arithmetic
    # via epoch seconds (portable across GNU date and MSYS bash on Windows).
    set_epoch="$(date -d "${SET_DATE}" +%s 2>/dev/null)"
    if [ -z "${set_epoch}" ]; then
      # Fallback: cannot parse date — treat as stale to be safe.
      STALE="true"
    else
      now_epoch="$(date +%s)"
      diff_days=$(( (now_epoch - set_epoch) / 86400 ))
      if [ "${diff_days}" -gt 180 ]; then
        STALE="true"
      fi
    fi
  else
    # Config exists but no date field — treat as stale.
    STALE="true"
  fi
fi

# Read session-state for test_mode.
TEST_MODE="false"
while IFS= read -r ss_line; do
  case "${ss_line}" in
    test_mode=*) TEST_MODE="${ss_line#test_mode=}" ;;
  esac
done < <(read_session_state "${PROJECT_DIR}")

# ---------------------------------------------------------------------------
# Section 3: Decide — action path selection
# ---------------------------------------------------------------------------
#
# Branch priority:
#   A (exists + fresh)      — silent read, no log, no emit
#   B (exists + stale)      — read with rationale, emit, log
#   C (missing + test_mode) — auto-write "pro", emit, log
#   D (missing + !test_mode)— emit prompt only, no write, no log

BRANCH=""
ACTION=""

if [ "${CONFIG_EXISTS}" = "true" ]; then
  if [ "${STALE}" = "false" ]; then
    BRANCH="A"
    ACTION="read"
  else
    BRANCH="B"
    ACTION="read-stale"
  fi
else
  if [ "${TEST_MODE}" = "true" ]; then
    BRANCH="C"
    ACTION="auto-write"
  else
    BRANCH="D"
    ACTION="prompt"
  fi
fi

DECISION_CONTEXT="config_exists:${CONFIG_EXISTS};stale:${STALE};test_mode:${TEST_MODE};action:${ACTION}"

# ---------------------------------------------------------------------------
# Section 4: Gate-context emission
# ---------------------------------------------------------------------------
# Branch A is a state-stable silent read: no emit per spec.

case "${BRANCH}" in
  A)
    # No gate-context emission for fresh read.
    :
    ;;
  B|C|D)
    if [ "${BRANCH}" = "D" ]; then
      emit_gate_context \
        "${PROJECT_DIR}" \
        "M2" \
        "mechanical" \
        "Plan tier? (a) Pro (b) Max 5x (c) Max 20x (d) API" \
        "a,b,c,d" \
        "~/.claude/skills/pcv/handlers/plan-tier.sh" \
        "${DECISION_CONTEXT}" \
        "letter"
    else
      emit_gate_context \
        "${PROJECT_DIR}" \
        "M2" \
        "mechanical" \
        "Plan tier configuration check" \
        "" \
        "~/.claude/skills/pcv/handlers/plan-tier.sh" \
        "${DECISION_CONTEXT}" \
        "approve_only"
    fi
    EMIT_RC=$?
    if [ "${EMIT_RC}" -ne 0 ]; then
      printf 'plan-tier.sh: failed to emit gate-context.json\n' >&2
      exit 1
    fi
    ;;
esac

# ---------------------------------------------------------------------------
# Section 5: Act + log + footer + exit
# ---------------------------------------------------------------------------

case "${BRANCH}" in
  A)
    # Fresh read — silent, no log.
    printf 'plan tier: %s (read from config)\n' "${TIER_READ}"
    print_mechanical_footer
    exit 0
    ;;

  B)
    # Stale read — note staleness, log, do not prompt (non-blocking).
    RATIONALE="plan tier: ${TIER_READ} (read from config; set date ${SET_DATE} is stale, >6 months)"
    printf '%s\n' "${RATIONALE}"
    print_mechanical_footer

    log_decision "${PROJECT_DIR}" "M2 plan-tier" "\
**Action:** read-stale
**Rationale:** ${RATIONALE}
**Decision context:** ${DECISION_CONTEXT}"
    exit 0
    ;;

  C)
    # Auto-write "pro" in test mode.
    mkdir -p "${HOME}/.claude" 2>/dev/null || {
      printf 'plan-tier.sh: failed to create %s/.claude\n' "${HOME}" >&2
      exit 1
    }
    today="$(date +%Y-%m-%d)" || { printf 'plan-tier.sh: date failed\n' >&2; exit 1; }

    tmp="${CONFIG_FILE}.tmp.$$"
    {
      printf '{\n'
      printf '  "plan_tier": "pro",\n'
      printf '  "plan_tier_set_date": "%s"\n' "${today}"
      printf '}\n'
    } > "${tmp}" 2>/dev/null || {
      rm -f "${tmp}" 2>/dev/null
      printf 'plan-tier.sh: failed to write temp config\n' >&2
      exit 1
    }
    mv -f "${tmp}" "${CONFIG_FILE}" 2>/dev/null || {
      rm -f "${tmp}" 2>/dev/null
      printf 'plan-tier.sh: failed to move temp config into place\n' >&2
      exit 1
    }

    RATIONALE="auto-pro (test mode)"
    printf '%s\n' "${RATIONALE}"
    print_mechanical_footer

    log_decision "${PROJECT_DIR}" "M2 plan-tier" "\
**Action:** auto-write
**Rationale:** ${RATIONALE}
**Decision context:** ${DECISION_CONTEXT}"
    exit 0
    ;;

  D)
    # Emit prompt only; hub handles the response.
    printf 'plan-tier prompt emitted (awaiting hub-relayed response)\n' >&2
    exit 0
    ;;

  *)
    printf 'plan-tier.sh: internal error — no branch selected\n' >&2
    exit 1
    ;;
esac
