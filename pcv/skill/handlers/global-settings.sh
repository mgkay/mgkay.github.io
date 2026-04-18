#!/usr/bin/env bash
# handlers/global-settings.sh — PCV v3.14 Gate M4 mechanical handler
#
# Ensures ~/.claude/settings.json has at least 3 allow rules. If minimal,
# proposes/auto-merges PCV default permissions via scaffold-settings.sh
# invoked with --merge-to-global (v3.14 new flag).
#
# Idempotency class: state-idempotent (per gate-inventory.md M4 row).
# Announce + execute semantics.
#
# Usage:
#   bash global-settings.sh --project-dir <absolute-path>
#
# Branches:
#   A  ≥3 allow rules already present — no-op
#   B  <3 rules + test_mode=true      — auto-merge via scaffold, emit, log
#   C  <3 rules + test_mode=false     — emit prompt for hub, no action
#
# Exit codes:
#   0   success (any branch)
#   1   I/O failure (scaffold invocation, emit, log)
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
        printf 'global-settings.sh: --project-dir requires a path argument\n' >&2
        exit 2
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    *)
      printf 'global-settings.sh: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if [ -z "${PROJECT_DIR}" ]; then
  printf 'global-settings.sh: --project-dir required\n' >&2
  exit 2
fi

# Optional override for testing: PCV_GLOBAL_SETTINGS_FILE env var points to
# an alternate settings.json (avoids clobbering real ~/.claude/settings.json
# in unit tests). If unset, default to the real location.
GLOBAL_SETTINGS="${PCV_GLOBAL_SETTINGS_FILE:-${HOME}/.claude/settings.json}"

# ---------------------------------------------------------------------------
# Section 2: State check — count allow rules in global settings
# ---------------------------------------------------------------------------
SETTINGS_EXISTS="false"
ALLOW_COUNT=0

if [ -f "${GLOBAL_SETTINGS}" ]; then
  SETTINGS_EXISTS="true"

  # Extract the permissions.allow array and count its string entries.
  # Strategy: isolate the text between `"allow": [` and the matching `]`,
  # then count quoted strings. Portable (no jq dependency).
  allow_block="$(awk '
    BEGIN { in_allow = 0; depth = 0 }
    {
      line = $0
      if (in_allow == 0) {
        # Look for "allow" followed by colon and [
        if (match(line, /"allow"[[:space:]]*:[[:space:]]*\[/)) {
          in_allow = 1
          # Print from the [ onward
          idx = RSTART + RLENGTH - 1
          rest = substr(line, idx)
          print rest
          # Count brackets on this line portion (after the opener)
          for (i = 2; i <= length(rest); i++) {
            c = substr(rest, i, 1)
            if (c == "[") depth++
            else if (c == "]") {
              if (depth == 0) { exit }
              depth--
            }
          }
          next
        }
      } else {
        # Track bracket nesting to find the closing ].
        printed = 0
        for (i = 1; i <= length(line); i++) {
          c = substr(line, i, 1)
          if (c == "[") depth++
          else if (c == "]") {
            if (depth == 0) {
              # Print up to and including the current position.
              print substr(line, 1, i)
              printed = 1
              exit
            }
            depth--
          }
        }
        if (!printed) print line
      }
    }
  ' "${GLOBAL_SETTINGS}" 2>/dev/null)"

  # Count occurrences of quoted strings in the extracted block. Each
  # quoted string corresponds to one allow rule.
  if [ -n "${allow_block}" ]; then
    ALLOW_COUNT="$(printf '%s' "${allow_block}" | grep -o '"[^"]*"' | wc -l | tr -d '[:space:]')"
    if [ -z "${ALLOW_COUNT}" ]; then
      ALLOW_COUNT=0
    fi
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
BRANCH=""
ACTION=""

if [ "${ALLOW_COUNT}" -ge 3 ]; then
  BRANCH="A"
  ACTION="noop-established"
elif [ "${TEST_MODE}" = "true" ]; then
  BRANCH="B"
  ACTION="auto-merge"
else
  BRANCH="C"
  ACTION="prompt"
fi

DECISION_CONTEXT="settings_exists:${SETTINGS_EXISTS};allow_count:${ALLOW_COUNT};test_mode:${TEST_MODE};action:${ACTION}"

# ---------------------------------------------------------------------------
# Section 4: Gate-context emission
# ---------------------------------------------------------------------------
# Branch A is state-idempotent no-op: no emit.

case "${BRANCH}" in
  A)
    :
    ;;
  B|C)
    if [ "${BRANCH}" = "C" ]; then
      emit_gate_context \
        "${PROJECT_DIR}" \
        "M4" \
        "mechanical" \
        "Global ~/.claude/settings.json has fewer than 3 allow rules. Propose adding PCV defaults?" \
        "approve,skip" \
        "~/.claude/skills/pcv/handlers/global-settings.sh" \
        "${DECISION_CONTEXT}" \
        "approve_only"
    else
      emit_gate_context \
        "${PROJECT_DIR}" \
        "M4" \
        "mechanical" \
        "Auto-merging PCV default permissions to global settings (test mode)" \
        "approve,skip" \
        "~/.claude/skills/pcv/handlers/global-settings.sh" \
        "${DECISION_CONTEXT}" \
        "approve_only"
    fi
    EMIT_RC=$?
    if [ "${EMIT_RC}" -ne 0 ]; then
      printf 'global-settings.sh: failed to emit gate-context.json\n' >&2
      exit 1
    fi
    ;;
esac

# ---------------------------------------------------------------------------
# Section 5: Act + log + footer + exit
# ---------------------------------------------------------------------------

case "${BRANCH}" in
  A)
    printf 'global settings established (%s allow rules)\n' "${ALLOW_COUNT}"
    print_mechanical_footer
    exit 0
    ;;

  B)
    # Auto-merge via scaffold-settings.sh --merge-to-global.
    SCAFFOLD="${HOME}/.claude/skills/pcv/hooks/scaffold-settings.sh"
    if [ ! -f "${SCAFFOLD}" ]; then
      printf 'global-settings.sh: scaffold-settings.sh not found at %s\n' "${SCAFFOLD}" >&2
      exit 1
    fi

    bash "${SCAFFOLD}" --merge-to-global "${GLOBAL_SETTINGS}" >&2
    SCAFFOLD_RC=$?
    if [ "${SCAFFOLD_RC}" -ne 0 ]; then
      printf 'global-settings.sh: scaffold-settings.sh --merge-to-global failed (exit %d)\n' "${SCAFFOLD_RC}" >&2
      exit 1
    fi

    RATIONALE="auto-merging proposed perms to global settings (test mode)"
    printf '%s\n' "${RATIONALE}"
    print_mechanical_footer

    log_decision "${PROJECT_DIR}" "M4 global-settings" "\
**Action:** auto-merge
**Rationale:** ${RATIONALE}
**Decision context:** ${DECISION_CONTEXT}"
    exit 0
    ;;

  C)
    printf 'global-settings prompt emitted (awaiting hub-relayed response)\n' >&2
    exit 0
    ;;

  *)
    printf 'global-settings.sh: internal error — no branch selected\n' >&2
    exit 1
    ;;
esac
