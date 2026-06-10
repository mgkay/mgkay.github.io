#!/usr/bin/env bash
# user-prompt-submit.sh — track-changes UserPromptSubmit hook
#
# Event:   UserPromptSubmit (fires when the HUMAN submits a new prompt — never
#          on an AI tool call).
# Purpose: v6 Fix B — this hook is the SOLE authorized writer of the /draft
#          sentinel. Each user turn it first clears any existing sentinel, then
#          — iff the human's own prompt requests drafting — writes a fresh
#          sentinel carrying the authorized marker (TC_DRAFT_AUTH_MARKER). The
#          PreToolUse gate honors a sentinel only if it carries that marker, and
#          only this hook (which the AI cannot trigger) writes it. So the AI can
#          no longer suspend its own tracking: draft-on.sh no longer writes the
#          sentinel, and a forged file lacks the marker.
#
#          "Requests drafting" = the prompt begins with `/draft` or `/tc draft`,
#          OR contains the draft-request marker embedded in commands/draft.md
#          (covers the case where a custom slash command is expanded before the
#          hook sees it).
#
#          Also clears the shared default.draft fallback and sweeps stale
#          verified-import exemption sentinels (unchanged from v5).
#
# Stdin:   UserPromptSubmit event JSON (contains a `prompt` field).
# Exit:    0 always.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=../lib/tc-common.sh
if ! source "${SCRIPT_DIR}/../lib/tc-common.sh" 2>/dev/null; then
  # Still drain stdin so the turn is not blocked.
  if [ ! -t 0 ]; then cat >/dev/null 2>&1 || true; fi
  exit 0
fi

# Capture the event payload (the prompt is needed for draft detection).
PAYLOAD=""
if [ ! -t 0 ]; then
  PAYLOAD="$(cat 2>/dev/null || true)"
fi

# --- Always clear first (the "one user turn" /draft semantic) ---------------
SENTINEL="$(tc_sentinel_path_draft 2>/dev/null || true)"
if [ -n "$SENTINEL" ]; then
  rm -f "$SENTINEL" 2>/dev/null || true
fi
SENTINEL_DEFAULT="$(tc_sentinel_path_draft_default 2>/dev/null || true)"
if [ -n "$SENTINEL_DEFAULT" ] && [ "$SENTINEL_DEFAULT" != "$SENTINEL" ]; then
  rm -f "$SENTINEL_DEFAULT" 2>/dev/null || true
fi

# --- Detect a human draft request, then (only then) write the sentinel ------
# Parse `.prompt` from the JSON payload and classify in Python (reliable JSON +
# regex; jq is not guaranteed on Windows). Exit 0 => draft requested.
if [ -n "$PAYLOAD" ]; then
  if printf '%s' "$PAYLOAD" | python -c '
import sys, json, re
try:
    p = (json.load(sys.stdin) or {}).get("prompt", "")
except Exception:
    sys.exit(1)
if not isinstance(p, str):
    sys.exit(1)
s = p.lstrip()
# Leading /draft or /tc draft (the literal-command case), or the draft-request
# marker embedded in commands/draft.md (the expanded-command case).
if re.match(r"/draft(\b|$)", s) or re.match(r"/tc\s+draft(\b|$)", s) \
        or ("TC-DRAFT-REQUEST" in p):
    sys.exit(0)
sys.exit(1)
' 2>/dev/null; then
    if tc_write_draft_sentinel 2>/dev/null; then
      tc_log "user-prompt-submit.sh: authorized /draft sentinel written (human request)"
    fi
  fi
fi

# C6 / Q4: clear stale verified-import exemption sentinels (tc_core.exempt; F2).
tc_sweep_exempt_sentinels 2>/dev/null || true

exit 0
