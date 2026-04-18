#!/usr/bin/env bash
# handlers/charge-write.sh — PCV v3.14 Gate M5 mechanical handler
#
# Writes pcvplans/charge.md from a hub-produced content file. Handler does
# not generate content — hub runs Step B2 clarification (J2 gates) and
# passes the final form via --charge-content-file.
#
# If pcv_idea.md exists at the project root, it is relocated to
# pcvplans/idea.md per SKILL.md Step B2 §7.
#
# Idempotency class: state-idempotent (per gate-inventory.md M5 row).
# Announce + execute semantics.
#
# Usage:
#   bash charge-write.sh --project-dir <absolute-path> --charge-content-file <path>
#
# Branches:
#   A  charge already on disk — no-op
#   B  charge missing         — write charge, optionally relocate idea, emit, log
#
# Exit codes:
#   0   success (any branch)
#   1   I/O failure (content missing, write error, emit, log)
#   2   argument error

set -u

# ---------------------------------------------------------------------------
# Section 1: Parse arguments
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "${SCRIPT_DIR}/lib.sh"

PROJECT_DIR=""
CHARGE_CONTENT_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project-dir)
      if [ -z "${2:-}" ]; then
        printf 'charge-write.sh: --project-dir requires a path argument\n' >&2
        exit 2
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    --charge-content-file)
      if [ -z "${2:-}" ]; then
        printf 'charge-write.sh: --charge-content-file requires a path argument\n' >&2
        exit 2
      fi
      CHARGE_CONTENT_FILE="$2"
      shift 2
      ;;
    *)
      printf 'charge-write.sh: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if [ -z "${PROJECT_DIR}" ]; then
  printf 'charge-write.sh: --project-dir required\n' >&2
  exit 2
fi

if [ -z "${CHARGE_CONTENT_FILE}" ]; then
  printf 'charge-write.sh: --charge-content-file required\n' >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Section 2: State check — charge.md presence; idea.md presence
# ---------------------------------------------------------------------------
CHARGE_FILE="${PROJECT_DIR}/pcvplans/charge.md"
IDEA_ROOT_FILE="${PROJECT_DIR}/pcv_idea.md"
IDEA_DEST_FILE="${PROJECT_DIR}/pcvplans/idea.md"

CHARGE_EXISTS="false"
IDEA_PRESENT_AT_ROOT="false"

if [ -f "${CHARGE_FILE}" ]; then
  CHARGE_EXISTS="true"
fi

if [ -f "${IDEA_ROOT_FILE}" ]; then
  IDEA_PRESENT_AT_ROOT="true"
fi

# ---------------------------------------------------------------------------
# Section 3: Decide — action path selection
# ---------------------------------------------------------------------------
BRANCH=""
ACTION=""
IDEA_RELOCATED_FIELD="na"

if [ "${CHARGE_EXISTS}" = "true" ]; then
  BRANCH="A"
  ACTION="noop"
else
  BRANCH="B"
  ACTION="write"
  if [ "${IDEA_PRESENT_AT_ROOT}" = "true" ]; then
    IDEA_RELOCATED_FIELD="true"
  else
    IDEA_RELOCATED_FIELD="false"
  fi
fi

DECISION_CONTEXT="charge_exists:${CHARGE_EXISTS};idea_relocated:${IDEA_RELOCATED_FIELD};action:${ACTION}"

# ---------------------------------------------------------------------------
# Section 4: Gate-context emission
# ---------------------------------------------------------------------------
# Branch A is state-idempotent no-op: no emit.

case "${BRANCH}" in
  A)
    :
    ;;
  B)
    emit_gate_context \
      "${PROJECT_DIR}" \
      "M5" \
      "mechanical" \
      "Write charge.md to pcvplans/" \
      "" \
      "~/.claude/skills/pcv/handlers/charge-write.sh" \
      "${DECISION_CONTEXT}" \
      "approve_only"
    EMIT_RC=$?
    if [ "${EMIT_RC}" -ne 0 ]; then
      printf 'charge-write.sh: failed to emit gate-context.json\n' >&2
      exit 1
    fi
    ;;
esac

# ---------------------------------------------------------------------------
# Section 5: Act + log + footer + exit
# ---------------------------------------------------------------------------

case "${BRANCH}" in
  A)
    printf 'charge already on disk\n'
    print_mechanical_footer
    exit 0
    ;;

  B)
    # Validate content file exists and is non-empty.
    if [ ! -f "${CHARGE_CONTENT_FILE}" ]; then
      printf 'charge-write.sh: charge content file not found: %s\n' "${CHARGE_CONTENT_FILE}" >&2
      exit 1
    fi
    content_size="$(wc -c < "${CHARGE_CONTENT_FILE}" 2>/dev/null | tr -d '[:space:]')"
    if [ -z "${content_size}" ] || [ "${content_size}" -eq 0 ]; then
      printf 'charge-write.sh: charge content file is empty: %s\n' "${CHARGE_CONTENT_FILE}" >&2
      exit 1
    fi

    # Ensure pcvplans dir exists.
    mkdir -p "${PROJECT_DIR}/pcvplans" 2>/dev/null || {
      printf 'charge-write.sh: failed to create %s/pcvplans\n' "${PROJECT_DIR}" >&2
      exit 1
    }

    # Atomic copy: write to temp then mv.
    tmp="${CHARGE_FILE}.tmp.$$"
    cp "${CHARGE_CONTENT_FILE}" "${tmp}" 2>/dev/null || {
      rm -f "${tmp}" 2>/dev/null
      printf 'charge-write.sh: failed to copy content to temp\n' >&2
      exit 1
    }
    mv -f "${tmp}" "${CHARGE_FILE}" 2>/dev/null || {
      rm -f "${tmp}" 2>/dev/null
      printf 'charge-write.sh: failed to move charge into place\n' >&2
      exit 1
    }

    # Relocate pcv_idea.md if present at root.
    if [ "${IDEA_PRESENT_AT_ROOT}" = "true" ]; then
      mv -f "${IDEA_ROOT_FILE}" "${IDEA_DEST_FILE}" 2>/dev/null || {
        # Non-fatal but report: charge written, relocation failed.
        printf 'charge-write.sh: warning: failed to relocate pcv_idea.md to pcvplans/idea.md\n' >&2
        IDEA_RELOCATED_FIELD="false"
        DECISION_CONTEXT="charge_exists:${CHARGE_EXISTS};idea_relocated:${IDEA_RELOCATED_FIELD};action:${ACTION}"
      }
    fi

    RATIONALE="charge written to pcvplans/charge.md"
    printf '%s\n' "${RATIONALE}"
    print_mechanical_footer

    log_decision "${PROJECT_DIR}" "M5 charge-write" "\
**Action:** write
**Rationale:** ${RATIONALE}
**Decision context:** ${DECISION_CONTEXT}"
    exit 0
    ;;

  *)
    printf 'charge-write.sh: internal error — no branch selected\n' >&2
    exit 1
    ;;
esac
