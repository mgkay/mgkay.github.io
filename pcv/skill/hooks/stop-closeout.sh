#!/usr/bin/env bash
# stop-closeout.sh — PCV Stop hook: closeout reminder + format enforcement
#
# Event:   Stop (fires at every Claude turn boundary, NOT on /exit or Ctrl-D)
# Purpose: When a PCV project is in verification phase without a closeout or
#          abandonment entry, force Claude to continue generating with a
#          reminder. This nudges the user to write the closeout entry before
#          leaving. Note: this hook CANNOT prevent /exit or Ctrl-D — those
#          bypass the Stop event entirely. The SessionStart resume hook (C4)
#          provides the retroactive catch on the next session.
#
#          Additionally, for projects in States 3–6 (construction through
#          closeout), validate PCV artifact format and surface violations.
#
# Payload fields (confirmed by hook-scoping-spike Check 1):
#   stop_hook_active     — "true" if another Stop hook is already running
#   last_assistant_message — final assistant turn text
#   permission_mode      — session permission mode string
#
# Exit semantics:
#   exit 0  — allow turn to end normally (non-PCV, wrong phase, closeout present, abandoned, opt-out)
#   exit 2  — force Claude to continue; stderr message is fed to Claude as context so it can
#             remind the user about the missing closeout entry or format violations
#
# Seven-state matrix:
#   State 1:  No PCV project (no pcvplans/)                                 → exit 0
#   State 2:  Planning phase (no construction-plan.md AND no lite-plan.md)  → exit 0
#   State 3:  Mid-construction (construction-plan.md, no verify)            → exit 0 then format check
#   State 4a: Verification pending, acceptance testing in progress          → exit 0 then format check
#   State 4b: Verification pending, acceptance testing not in progress      → exit 2 (REMIND closeout)
#   State 5:  Closed out (## Project Closeout in decision log)              → exit 0 then format check
#   State 6:  Abandoned (## Verification Abandoned in decision log)         → exit 0 then format check

# ---------------------------------------------------------------------------
# Inline lightweight format check (replaces validate-pcv-format.sh subprocess)
# ---------------------------------------------------------------------------
pcv_lightweight_format_check() {
  local project_dir="$1"
  local violations=""

  # Check decision log if it exists
  local dlog="$project_dir/pcvplans/logs/decision-log.md"
  if [ -f "$dlog" ]; then
    if ! head -1 "$dlog" | grep -q '^# Decision Log'; then
      violations="${violations}decision-log.md: missing '# Decision Log' header\n"
    fi
  fi

  # Check build record if it exists
  local brec="$project_dir/pcvplans/build-record.md"
  if [ -f "$brec" ]; then
    if ! head -1 "$brec" | grep -q '^# Build Record'; then
      violations="${violations}build-record.md: missing '# Build Record' header\n"
    fi
  fi

  # Check project summary if it exists
  local psum="$project_dir/pcvplans/project-summary.md"
  if [ -f "$psum" ]; then
    if ! head -1 "$psum" | grep -q '^# Project Summary'; then
      violations="${violations}project-summary.md: missing '# Project Summary' header\n"
    fi
  fi

  # Also check for phase-specific project summary
  for f in "$project_dir"/pcvplans/project-summary-*.md; do
    [ -f "$f" ] || continue
    local basename
    basename="$(basename "$f")"
    if ! head -1 "$f" | grep -q '^# Project Summary'; then
      violations="${violations}${basename}: missing '# Project Summary' header\n"
    fi
  done

  if [ -n "$violations" ]; then
    printf '%b' "$violations"
    return 1
  fi
  return 0
}

# Resolve project root: prefer CLAUDE_PROJECT_DIR, fall back to PWD
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"

# State 1: Not a PCV project
if [ ! -d "$PROJECT_DIR/pcvplans" ]; then
  exit 0
fi

# Opt-out check: honor .pcv-hooks-opted-out sentinel file
if [ -f "$PROJECT_DIR/.claude/.pcv-hooks-opted-out" ]; then
  exit 0
fi

# State 2: Planning phase — no construction-plan.md AND no lite-plan.md yet
if [ ! -f "$PROJECT_DIR/pcvplans/construction-plan.md" ] && [ ! -f "$PROJECT_DIR/pcvplans/lite-plan.md" ]; then
  exit 0
fi

# Decision log path
DECISION_LOG="$PROJECT_DIR/pcvplans/logs/decision-log.md"

# States 5 and 6: Closeout or abandonment already recorded — allow (then format check)
if [ -f "$DECISION_LOG" ]; then
  if grep -q '^## Project Closeout' "$DECISION_LOG"; then
    # State 5: run format check
    FORMAT_OUTPUT=$(pcv_lightweight_format_check "$PROJECT_DIR")
    if [ $? -ne 0 ]; then
      echo "PCV format violation(s) detected. Please fix before ending the session:
$FORMAT_OUTPUT
To suppress this check permanently, create .claude/.pcv-hooks-opted-out in the project root." >&2
      exit 2
    fi
    exit 0
  fi
  if grep -q '^## Verification Abandoned' "$DECISION_LOG"; then
    # State 6: run format check
    FORMAT_OUTPUT=$(pcv_lightweight_format_check "$PROJECT_DIR")
    if [ $? -ne 0 ]; then
      echo "PCV format violation(s) detected. Please fix before ending the session:
$FORMAT_OUTPUT
To suppress this check permanently, create .claude/.pcv-hooks-opted-out in the project root." >&2
      exit 2
    fi
    exit 0
  fi
fi

# State 3 vs State 4: Check whether verification phase has been reached.
# Verification is detected by a "## Verification" header in the decision log.
# Absence of decision log is conservative: treat as mid-construction → allow (then format check).
if [ ! -f "$DECISION_LOG" ]; then
  # State 3 (no log yet): run format check
  FORMAT_OUTPUT=$(pcv_lightweight_format_check "$PROJECT_DIR")
  if [ $? -ne 0 ]; then
    echo "PCV format violation(s) detected. Please fix before ending the session:
$FORMAT_OUTPUT
To suppress this check permanently, create .claude/.pcv-hooks-opted-out in the project root." >&2
    exit 2
  fi
  exit 0
fi

if grep -q '^## Verification' "$DECISION_LOG"; then
  # State 4a vs 4b: check for acceptance-testing-pending marker
  if grep -q '^## Acceptance Testing Pending' "$DECISION_LOG"; then
    # State 4a: acceptance testing in progress — allow (then format check)
    FORMAT_OUTPUT=$(pcv_lightweight_format_check "$PROJECT_DIR")
    if [ $? -ne 0 ]; then
      echo "PCV format violation(s) detected. Please fix before ending the session:
$FORMAT_OUTPUT
To suppress this check permanently, create .claude/.pcv-hooks-opted-out in the project root." >&2
      exit 2
    fi
    exit 0
  fi

  # State 4b: verification reached, no closeout, no abandonment, no acceptance-testing marker — REMIND
  # Exit 2 forces Claude to continue generating. The stderr message is fed to
  # Claude as context, so it will remind the user about the missing entry.
  echo "PCV closeout reminder: verification phase is active but no '## Project Closeout' or '## Verification Abandoned' entry found in the decision log. Please remind the user to write one before ending the session. To suppress this reminder permanently, create .claude/.pcv-hooks-opted-out in the project root." >&2
  exit 2
fi

# State 3: Construction underway, verification not yet started — allow (then format check)
FORMAT_OUTPUT=$(pcv_lightweight_format_check "$PROJECT_DIR")
if [ $? -ne 0 ]; then
  echo "PCV format violation(s) detected. Please fix before ending the session:
$FORMAT_OUTPUT
To suppress this check permanently, create .claude/.pcv-hooks-opted-out in the project root." >&2
  exit 2
fi
exit 0
