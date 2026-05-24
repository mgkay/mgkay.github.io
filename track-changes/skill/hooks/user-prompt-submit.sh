#!/usr/bin/env bash
# user-prompt-submit.sh — track-changes UserPromptSubmit hook
#
# Event:   UserPromptSubmit (fires when the user submits a new prompt)
# Purpose: Defensive clearing of the current session's /draft sentinel at
#          the start of every user turn. Behaviorally identical to stop.sh
#          — separate script for clarity in settings.json registration
#          (ConstructionPlan §2). The double-clear ensures the "one user
#          turn" semantic for /draft holds even if Stop was missed (user
#          interrupt, timeout, crash); rm -f is idempotent so the race
#          between Stop and UserPromptSubmit is harmless.
#
# Stdin:   Hook event JSON payload (drained but not parsed in v1).
# Stdout:  (none)
# Stderr:  (none under normal operation)
# Exit:    0 always.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=../lib/tc-common.sh
if ! source "${SCRIPT_DIR}/../lib/tc-common.sh" 2>/dev/null; then
  exit 0
fi

# Drain stdin if a payload was piped in.
if [ ! -t 0 ]; then
  cat >/dev/null 2>&1 || true
fi

# Compute the sentinel path and unlink it idempotently.
SENTINEL="$(tc_sentinel_path 2>/dev/null || true)"
if [ -n "$SENTINEL" ]; then
  rm -f "$SENTINEL" 2>/dev/null || true
  tc_log "user-prompt-submit.sh: cleared sentinel $SENTINEL"
fi

exit 0
