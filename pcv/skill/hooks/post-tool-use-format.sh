#!/usr/bin/env bash
# post-tool-use-format.sh — PCV PostToolUse hook: real-time format enforcement
#
# Event:   PostToolUse (fires after every tool call by Claude)
# Purpose: When Claude writes a known PCV artifact, validate its format
#          immediately and return a correction instruction if violations
#          are found. This catches format errors at write time rather than
#          waiting for the Stop hook at end of turn.
#
# Payload fields (confirmed by hook-scoping-spike C1):
#   tool_name            — name of the tool that was called (e.g. "Write")
#   tool_input.file_path — absolute path of the written file
#   tool_response        — tool response object
#   cwd, session_id, permission_mode, hook_event_name, tool_use_id, transcript_path
#
# Exit semantics (advisory PostToolUse):
#   exit 0  — no action needed (non-PCV, not a PCV artifact, no violations, opt-out)
#   exit 2  — continuation message; stderr text is fed to Claude to prompt correction
#
# PCV artifact detection (basename match):
#   decision-log.md, master-log.md, build-record.md, project-summary*.md

# Read full stdin payload
PAYLOAD=$(cat)

# Resolve project root: prefer CLAUDE_PROJECT_DIR, fall back to PWD
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"

# PCV detect: exit 0 silently if not a PCV project
if [ ! -d "$PROJECT_DIR/pcvplans" ]; then
  exit 0
fi

# Opt-out check: honor .pcv-hooks-opted-out sentinel file
if [ -f "$PROJECT_DIR/.claude/.pcv-hooks-opted-out" ]; then
  exit 0
fi

# Extract file_path from payload: use jq if available, else grep/sed fallback
FILE_PATH=""
if command -v jq >/dev/null 2>&1; then
  FILE_PATH=$(printf '%s' "$PAYLOAD" | jq -r '.tool_input.file_path // empty')
else
  FILE_PATH=$(printf '%s' "$PAYLOAD" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/"file_path"[[:space:]]*:[[:space:]]*"//;s/"$//')
fi

# If no file path extracted, nothing to check
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Get the basename for artifact matching
BASENAME=$(basename "$FILE_PATH")

# Check if file is a known PCV artifact
IS_PCV_ARTIFACT=0
case "$BASENAME" in
  decision-log.md)
    IS_PCV_ARTIFACT=1
    ;;
  master-log.md)
    IS_PCV_ARTIFACT=1
    ;;
  build-record.md)
    IS_PCV_ARTIFACT=1
    ;;
  project-summary*.md)
    IS_PCV_ARTIFACT=1
    ;;
esac

# Not a PCV artifact — exit silently
if [ "$IS_PCV_ARTIFACT" -eq 0 ]; then
  exit 0
fi

# Run format validation on the specific file
FORMAT_OUTPUT=$(bash ~/.claude/skills/pcv/hooks/validate-pcv-format.sh --file "$FILE_PATH" 2>&1)
FORMAT_EXIT=$?

# No violations — exit cleanly
if [ "$FORMAT_EXIT" -ne 1 ]; then
  exit 0
fi

# Violations found — exit 2 with correction instruction
echo "PCV format violation(s) detected in $BASENAME. Please fix before proceeding:
$FORMAT_OUTPUT
To suppress this check permanently, create .claude/.pcv-hooks-opted-out in the project root." >&2
exit 2
