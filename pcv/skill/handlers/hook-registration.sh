#!/usr/bin/env bash
# handlers/hook-registration.sh — PCV v3.14 Gate M1 mechanical handler
#
# Reference implementation for M2–M8. Establishes the canonical pattern:
#   parse args -> state check -> decide -> gate-context emit ->
#   act + log + footer -> exit.
#
# Idempotency class: state-idempotent (per gate-inventory.md M1 row).
# Announce + execute semantics (no approval wait), per Q1 resolution.
#
# Usage:
#   bash hook-registration.sh --project-dir <absolute-path>
#
# Exit codes:
#   0   success (any branch A/B/C/D)
#   1   I/O failure (scaffold-settings.sh invocation failed, or log/emit I/O)
#   2   argument error (missing or unknown flag)

set -u  # undefined vars are errors; do NOT use set -e (errors are per-command)

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
        printf 'hook-registration.sh: --project-dir requires a path argument\n' >&2
        exit 2
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    *)
      printf 'hook-registration.sh: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if [ -z "${PROJECT_DIR}" ]; then
  printf 'hook-registration.sh: --project-dir required\n' >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Section 2: State check (state-idempotent entry)
# ---------------------------------------------------------------------------
SETTINGS_FILE="${PROJECT_DIR}/.claude/settings.json"
OPTOUT_MARKER="${PROJECT_DIR}/.claude/.pcv-hooks-opted-out"
CHARGE_FILE="${PROJECT_DIR}/pcvplans/charge.md"

HOOKS_PRESENT="false"
OPTED_OUT="false"
CHARGE_MENTIONS_HOOK_REDESIGN="false"

# Check for all 5 hook types in settings.json.
if [ -f "${SETTINGS_FILE}" ]; then
  if grep -q '"SessionStart"' "${SETTINGS_FILE}" 2>/dev/null \
     && grep -q '"Stop"' "${SETTINGS_FILE}" 2>/dev/null \
     && grep -q '"PreCompact"' "${SETTINGS_FILE}" 2>/dev/null \
     && grep -q '"SubagentStop"' "${SETTINGS_FILE}" 2>/dev/null \
     && grep -q '"PostToolUse"' "${SETTINGS_FILE}" 2>/dev/null; then
    HOOKS_PRESENT="true"
  fi
fi

# Check for opt-out marker.
if [ -f "${OPTOUT_MARKER}" ]; then
  OPTED_OUT="true"
fi

# ---------------------------------------------------------------------------
# Section 3: Decide — action path selection
# ---------------------------------------------------------------------------
#
# Branch priority:
#   A (hooks already present)  — no-op
#   B (opt-out marker present) — no-op
#   C (charge mentions hook redesign) — defer (write opt-out marker)
#   D (normal install) — invoke scaffold-settings.sh
#
# Charge keyword detection (case-insensitive):
#   - "hook redesign" or "redesign hook"
#   - "hook-based session state"
#   - "SC2" within +/-200 chars of "hook"
#   - "session state sentinel" or "sentinel file" co-occurring with "hook"
# Missing charge file => treat as no-match (Branch D); warn to stderr.

ACTION="noop"
BRANCH=""

if [ "${HOOKS_PRESENT}" = "true" ]; then
  BRANCH="A"
  ACTION="noop"
elif [ "${OPTED_OUT}" = "true" ]; then
  BRANCH="B"
  ACTION="noop"
else
  # Need to inspect charge for keyword match.
  if [ ! -f "${CHARGE_FILE}" ]; then
    printf 'PCV hook-registration: charge.md not found, defaulting to install path\n' >&2
    CHARGE_MENTIONS_HOOK_REDESIGN="false"
  else
    # Lowercase, NUL-safe read into a single scalar for co-occurrence checks.
    charge_lc="$(tr '[:upper:]' '[:lower:]' < "${CHARGE_FILE}" 2>/dev/null)"

    matched="false"

    # Direct phrase matches.
    case "${charge_lc}" in
      *"hook redesign"*|*"redesign hook"*|*"hook-based session state"*)
        matched="true"
        ;;
    esac

    # "session state sentinel" or "sentinel file" co-occurring with "hook".
    if [ "${matched}" = "false" ]; then
      case "${charge_lc}" in
        *"session state sentinel"*|*"sentinel file"*)
          case "${charge_lc}" in
            *"hook"*) matched="true" ;;
          esac
          ;;
      esac
    fi

    # "SC2" within +/-200 chars of "hook": use awk over case-preserved text
    # (SC2 is uppercase; "hook" is lowercase in charge_lc — but we need the
    # original text to find SC2 exactly, since lowercasing makes "sc2"). We
    # search charge_lc for the lowercased tokens.
    if [ "${matched}" = "false" ]; then
      # awk: slurp whole file as one string, then for each occurrence of "sc2"
      # check whether "hook" occurs within +/-200 chars.
      proximity_hit="$(printf '%s' "${charge_lc}" \
        | awk '
          {
            text = text $0 "\n"
          }
          END {
            n = length(text)
            pos = 1
            while ((idx = index(substr(text, pos), "sc2")) > 0) {
              abs_idx = pos + idx - 1
              lo = abs_idx - 200
              if (lo < 1) lo = 1
              hi = abs_idx + 200 + 2  # +2 to include remainder of "sc2" token
              if (hi > n) hi = n
              window = substr(text, lo, hi - lo + 1)
              if (index(window, "hook") > 0) { print "1"; exit }
              pos = abs_idx + 3
            }
          }
        ' 2>/dev/null)"
      if [ "${proximity_hit}" = "1" ]; then
        matched="true"
      fi
    fi

    CHARGE_MENTIONS_HOOK_REDESIGN="${matched}"
  fi

  if [ "${CHARGE_MENTIONS_HOOK_REDESIGN}" = "true" ]; then
    BRANCH="C"
    ACTION="defer"
  else
    BRANCH="D"
    ACTION="install"
  fi
fi

# ---------------------------------------------------------------------------
# Section 4: Gate-context emission (always, before action)
# ---------------------------------------------------------------------------
DECISION_CONTEXT="hooks_present:${HOOKS_PRESENT};opted_out:${OPTED_OUT};charge_mentions_hook_redesign:${CHARGE_MENTIONS_HOOK_REDESIGN};action:"
case "${ACTION}" in
  noop)    DECISION_CONTEXT="${DECISION_CONTEXT}noop" ;;
  defer)   DECISION_CONTEXT="${DECISION_CONTEXT}defer" ;;
  install) DECISION_CONTEXT="${DECISION_CONTEXT}install" ;;
esac

emit_gate_context \
  "${PROJECT_DIR}" \
  "M1" \
  "mechanical" \
  "Register PCV hooks for this project?" \
  "install,defer" \
  "~/.claude/skills/pcv/handlers/hook-registration.sh" \
  "${DECISION_CONTEXT}" \
  "approve_only"
EMIT_RC=$?
if [ "${EMIT_RC}" -ne 0 ]; then
  printf 'hook-registration.sh: failed to emit gate-context.json\n' >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Section 5: Act + log + footer + exit
# ---------------------------------------------------------------------------

case "${BRANCH}" in
  A)
    # Hooks already installed — no action, no log entry.
    printf 'hooks already installed\n'
    print_mechanical_footer
    exit 0
    ;;

  B)
    # Already opted out — no action, no log entry.
    printf 'opted out\n'
    print_mechanical_footer
    exit 0
    ;;

  C)
    # Defer: write opt-out marker with brief rationale.
    CLAUDE_DIR="${PROJECT_DIR}/.claude"
    mkdir -p "${CLAUDE_DIR}" 2>/dev/null || {
      printf 'hook-registration.sh: failed to create %s\n' "${CLAUDE_DIR}" >&2
      exit 1
    }
    {
      printf 'Opt-out generated by PCV M1 hook-registration handler.\n'
      printf 'Rationale: project charge mentions hook redesign (SC2/SC3 keyword match).\n'
      printf 'Date: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "${OPTOUT_MARKER}" 2>/dev/null
    if [ ! -f "${OPTOUT_MARKER}" ]; then
      printf 'hook-registration.sh: failed to write opt-out marker\n' >&2
      exit 1
    fi

    RATIONALE="Deferring hook install — charge mentions hook redesign (SC2/SC3)"
    printf '%s\n' "${RATIONALE}"
    print_mechanical_footer

    log_decision "${PROJECT_DIR}" "M1 hook-registration" "\
**Action:** defer
**Rationale:** ${RATIONALE}
**Decision context:** ${DECISION_CONTEXT}"
    exit 0
    ;;

  D)
    # Normal install: invoke scaffold-settings.sh.
    SCAFFOLD="${HOME}/.claude/skills/pcv/hooks/scaffold-settings.sh"
    if [ ! -f "${SCAFFOLD}" ]; then
      printf 'hook-registration.sh: scaffold-settings.sh not found at %s\n' "${SCAFFOLD}" >&2
      exit 1
    fi

    bash "${SCAFFOLD}" --project-dir "${PROJECT_DIR}" >&2
    SCAFFOLD_RC=$?
    if [ "${SCAFFOLD_RC}" -ne 0 ]; then
      printf 'hook-registration.sh: scaffold-settings.sh failed (exit %d)\n' "${SCAFFOLD_RC}" >&2
      # No log entry on failure (requirement #4).
      exit 1
    fi

    RATIONALE="Installing v3.13 hooks via scaffold-settings.sh"
    printf '%s\n' "${RATIONALE}"
    print_mechanical_footer

    log_decision "${PROJECT_DIR}" "M1 hook-registration" "\
**Action:** install
**Rationale:** ${RATIONALE}
**Decision context:** ${DECISION_CONTEXT}"
    exit 0
    ;;

  *)
    printf 'hook-registration.sh: internal error — no branch selected\n' >&2
    exit 1
    ;;
esac
