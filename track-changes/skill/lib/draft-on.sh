#!/usr/bin/env bash
# lib/draft-on.sh — slash-command sentinel writer.
#
# Invoked from commands/draft.md's `!` bash-prefix line. Encapsulates the
# sentinel-write logic so the slash-command itself is a single, quote-safe
# bash invocation (the prior inline `sh -c '...'` form had nested quoting
# issues and inconsistent $HOME/$CLAUDE_SESSION_ID inheritance across
# Windows shells / git-bash / WSL).
#
# Behavior:
#   1. Resolve the state directory from $HOME; create if absent.
#   2. Resolve the session id from $CLAUDE_SESSION_ID (fall back to "default"
#      when unset or empty — matches lib/tc-common.sh::tc_session_id).
#   3. Write a timestamped sentinel at $STATE_DIR/$SESSION.draft.
#   4. Echo the sentinel path so the user (and Claude reading the slash
#      command's output) can see exactly where it landed.
#
# Idempotent — re-running just overwrites the timestamp line.

set -u

if [ -z "${HOME:-}" ]; then
  echo "track-changes: ERROR — \$HOME is unset; cannot resolve state directory" >&2
  exit 1
fi

STATE_DIR="${HOME}/.claude/skills/track-changes/state"
if ! mkdir -p "${STATE_DIR}" 2>/dev/null; then
  echo "track-changes: ERROR — failed to create state directory ${STATE_DIR}" >&2
  exit 1
fi

SESSION="${CLAUDE_SESSION_ID:-default}"
SENTINEL="${STATE_DIR}/${SESSION}.draft"

# Timestamp in ISO-8601 UTC. `date -u +<format>` works on GNU/BSD/MSYS;
# fall back to plain `date -u` (locale-default) if the format string is
# unsupported by the local date binary.
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u 2>/dev/null || echo unknown-time)"

if ! printf '# created %s (slash command; session=%s)\n' "${TS}" "${SESSION}" > "${SENTINEL}"; then
  echo "track-changes: ERROR — failed to write sentinel ${SENTINEL}" >&2
  exit 1
fi

echo "track-changes: drafting mode active for this turn (sentinel: ${SENTINEL})"
