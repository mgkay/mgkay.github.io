#!/usr/bin/env bash
# handlers/git-setup.sh — PCV v3.14 Gate M3 mechanical handler
#
# Ensures project directory has git coverage (local .git OR parent .git
# within 5 levels). State-idempotent: no-op when git repo already present.
#
# Idempotency class: state-idempotent (per gate-inventory.md M3 row).
# Announce + execute semantics.
#
# Usage:
#   bash git-setup.sh --project-dir <absolute-path>
#
# Branches:
#   A  local .git present    — no-op
#   B  parent .git present   — no-op (report resolved toplevel)
#   C  no git + test_mode    — auto-init local .git, emit, log
#   D  no git + !test_mode   — emit prompt for hub, no action, no log
#
# Exit codes:
#   0   success (any branch)
#   1   I/O failure (git init, emit, or log)
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
        printf 'git-setup.sh: --project-dir requires a path argument\n' >&2
        exit 2
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    *)
      printf 'git-setup.sh: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if [ -z "${PROJECT_DIR}" ]; then
  printf 'git-setup.sh: --project-dir required\n' >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# Section 2: State check — local .git, parent .git (walk up to 5 levels)
# ---------------------------------------------------------------------------
LOCAL_GIT="false"
PARENT_GIT="false"
PARENT_TOPLEVEL=""

if [ -d "${PROJECT_DIR}/.git" ] || [ -f "${PROJECT_DIR}/.git" ]; then
  LOCAL_GIT="true"
else
  # Walk parents up to 5 levels looking for .git. Use git itself as the
  # oracle if available; otherwise manual walk.
  dir="${PROJECT_DIR}"
  for _ in 1 2 3 4 5; do
    parent="$(dirname "${dir}")"
    # Stop at filesystem root (dirname of root returns the root itself).
    if [ "${parent}" = "${dir}" ]; then
      break
    fi
    if [ -d "${parent}/.git" ] || [ -f "${parent}/.git" ]; then
      PARENT_GIT="true"
      PARENT_TOPLEVEL="${parent}"
      break
    fi
    dir="${parent}"
  done

  # Fallback: if we didn't find via manual walk, ask git (respects
  # GIT_DIR env and submodule patterns) as a secondary check. The manual
  # walk is the primary because git rev-parse can traverse arbitrary
  # depth, but we still cap reporting at 5 for spec compliance.
  if [ "${PARENT_GIT}" = "false" ]; then
    if command -v git >/dev/null 2>&1; then
      gt="$(git -C "${PROJECT_DIR}" rev-parse --show-toplevel 2>/dev/null)"
      if [ -n "${gt}" ] && [ "${gt}" != "${PROJECT_DIR}" ]; then
        # Confirm the toplevel is within 5 parent levels.
        dir="${PROJECT_DIR}"
        found_within=0
        for _ in 1 2 3 4 5; do
          parent="$(dirname "${dir}")"
          if [ "${parent}" = "${dir}" ]; then
            break
          fi
          # Normalize both paths for comparison; use realpath-lite via cd+pwd.
          parent_norm="$(cd "${parent}" 2>/dev/null && pwd)"
          gt_norm="$(cd "${gt}" 2>/dev/null && pwd)"
          if [ -n "${parent_norm}" ] && [ "${parent_norm}" = "${gt_norm}" ]; then
            PARENT_GIT="true"
            PARENT_TOPLEVEL="${gt}"
            found_within=1
            break
          fi
          dir="${parent}"
        done
        # If git says there's a repo but it's beyond 5 parents, treat as
        # no parent git for spec compliance.
        : "${found_within}"
      fi
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
#
# Branch priority:
#   A (local .git)       — no-op
#   B (parent .git)      — no-op
#   C (none + test_mode) — auto-init
#   D (none + !test_mode)— prompt

BRANCH=""
ACTION=""

if [ "${LOCAL_GIT}" = "true" ]; then
  BRANCH="A"
  ACTION="noop-local"
elif [ "${PARENT_GIT}" = "true" ]; then
  BRANCH="B"
  ACTION="noop-parent"
elif [ "${TEST_MODE}" = "true" ]; then
  BRANCH="C"
  ACTION="auto-init"
else
  BRANCH="D"
  ACTION="prompt"
fi

PARENT_GIT_FIELD="${PARENT_GIT}"
if [ "${PARENT_GIT}" = "true" ] && [ -n "${PARENT_TOPLEVEL}" ]; then
  PARENT_GIT_FIELD="${PARENT_TOPLEVEL}"
fi

DECISION_CONTEXT="local_git:${LOCAL_GIT};parent_git:${PARENT_GIT_FIELD};test_mode:${TEST_MODE};action:${ACTION}"

# ---------------------------------------------------------------------------
# Section 4: Gate-context emission
# ---------------------------------------------------------------------------
# Branches A and B are state-idempotent no-ops: no emit.

case "${BRANCH}" in
  A|B)
    :
    ;;
  C|D)
    if [ "${BRANCH}" = "D" ]; then
      emit_gate_context \
        "${PROJECT_DIR}" \
        "M3" \
        "mechanical" \
        "No git repo found in 5 parent levels. Init here?" \
        "init,skip" \
        "~/.claude/skills/pcv/handlers/git-setup.sh" \
        "${DECISION_CONTEXT}" \
        "approve_only"
    else
      emit_gate_context \
        "${PROJECT_DIR}" \
        "M3" \
        "mechanical" \
        "Initialize git repo (test mode auto-init)" \
        "init,skip" \
        "~/.claude/skills/pcv/handlers/git-setup.sh" \
        "${DECISION_CONTEXT}" \
        "approve_only"
    fi
    EMIT_RC=$?
    if [ "${EMIT_RC}" -ne 0 ]; then
      printf 'git-setup.sh: failed to emit gate-context.json\n' >&2
      exit 1
    fi
    ;;
esac

# ---------------------------------------------------------------------------
# Section 5: Act + log + footer + exit
# ---------------------------------------------------------------------------

case "${BRANCH}" in
  A)
    printf 'git repo: local\n'
    print_mechanical_footer
    exit 0
    ;;

  B)
    printf 'git repo: parent (%s)\n' "${PARENT_TOPLEVEL}"
    print_mechanical_footer
    exit 0
    ;;

  C)
    # Auto-init.
    if ! command -v git >/dev/null 2>&1; then
      printf 'git-setup.sh: git command not found\n' >&2
      exit 1
    fi
    git -C "${PROJECT_DIR}" init >&2
    INIT_RC=$?
    if [ "${INIT_RC}" -ne 0 ]; then
      printf 'git-setup.sh: git init failed (exit %d)\n' "${INIT_RC}" >&2
      exit 1
    fi

    RATIONALE="auto-init (test mode)"
    printf '%s\n' "${RATIONALE}"
    print_mechanical_footer

    log_decision "${PROJECT_DIR}" "M3 git-setup" "\
**Action:** auto-init
**Rationale:** ${RATIONALE}
**Decision context:** ${DECISION_CONTEXT}"
    exit 0
    ;;

  D)
    printf 'git-setup prompt emitted (awaiting hub-relayed response)\n' >&2
    exit 0
    ;;

  *)
    printf 'git-setup.sh: internal error — no branch selected\n' >&2
    exit 1
    ;;
esac
