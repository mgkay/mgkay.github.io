#!/usr/bin/env bash
# lib/draft-on.sh — DEPRECATED in v6 (Fix B: /draft is mechanically user-only).
#
# In v1–v5 this script wrote the /draft suspension sentinel, and the AI could
# invoke it (directly via the Bash tool, or via commands/draft.md's fallback) to
# suspend its own tracking — the exact bypass v6 closes. The sentinel is now
# written ONLY by the UserPromptSubmit hook (hooks/user-prompt-submit.sh) when
# the HUMAN's own prompt requests drafting, and it carries an authorized marker
# the PreToolUse gate checks. This script therefore NO LONGER writes a sentinel:
# running it (by anyone) cannot suspend tracking. Retained as a clear no-op so
# any lingering reference fails safe rather than silently re-opening the bypass.

set -u

echo "track-changes: /draft is user-only (v6). This script no longer suspends" >&2
echo "tracking. To draft, the USER types /draft (or /tc draft) as their prompt;" >&2
echo "the UserPromptSubmit hook authorizes it. The AI cannot self-suspend —" >&2
echo "author content as <mark> edits, a whole-region insertion, or via /tc import." >&2
exit 0
