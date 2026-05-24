#!/usr/bin/env bash
# stop.sh — track-changes Stop hook (no-op on sentinel as of Post-Closeout Fix #3)
#
# Event:   Stop (fires at Claude turn boundaries — but observed to ALSO
#          fire mid-response between commentary segments and subsequent
#          tool calls. The original design (MakePlan Rev 4 D4 / E2) had
#          Stop as the primary `/draft` sentinel clearing path on the
#          assumption that Stop only fires at end-of-response; that turned
#          out to be wrong in practice on the user's Windows / Git-bash
#          install, causing single `/draft` invocations to be cleared mid-
#          turn before subsequent tool calls could see them.
#
# Purpose (post-fix): drain stdin; otherwise no-op. The `/draft` sentinel
# is now cleared only by:
#   - UserPromptSubmit (fires at the START of the user's next prompt —
#     matches the "one user turn" semantics precisely)
#   - SessionStart (1h-TTL sweep for stale sentinels from crashed sessions
#     or sessions that exited without UserPromptSubmit firing)
#
# Stdin:   Hook event JSON payload (drained, not parsed).
# Stdout:  (none)
# Stderr:  (none)
# Exit:    0 always.

set -u

# Drain stdin if a payload was piped in (avoids SIGPIPE on caller).
if [ ! -t 0 ]; then
  cat >/dev/null 2>&1 || true
fi

# Optional diagnostic log line so the user can confirm Stop fired but did
# not clear the sentinel. Source the library best-effort; failures are
# silent (never break the turn).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if source "${SCRIPT_DIR}/../lib/tc-common.sh" 2>/dev/null; then
  tc_log "stop.sh: fired (sentinel-clear delegated to UserPromptSubmit + SessionStart-TTL)"
fi

exit 0
