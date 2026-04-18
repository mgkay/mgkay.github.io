#!/usr/bin/env bash
# tech-permissions-scan.sh — PCV v3.11 Phase 3
#
# Purpose:
#   Detect technology-specific permissions needed for construction. Replaces
#   the analytical scan in construction-protocol.md §2.5.
#
# Usage:
#   bash tech-permissions-scan.sh [--project-dir <path>]
#
# Arguments:
#   --project-dir <path>   Project directory to scan (default: current directory).
#
# Behavior:
#   1. Reads charge.md (required — exits 1 if missing).
#   2. Reads construction-plan.md or lite-plan.md (optional — skips gracefully).
#   3. Greps combined content for technology keywords (case-insensitive).
#   4. Maps detected keywords to Bash permission patterns.
#   5. Reads .claude/settings.json, checks which patterns already exist.
#   6. Adds missing patterns directly to settings.json.
#   7. Outputs "Added: [list]" or "No new permissions needed."
#
# Exit codes:
#   0  Success (even if no permissions were added)
#   1  Error (message written to stderr)
#
# Idempotent: Safe to re-run — will not duplicate existing entries.
#
# Design constraints:
#   - Pure bash. No jq dependency.
#   - Follows scaffold-settings.sh style for settings.json manipulation.
#   - Direct edit of settings.json (does not call scaffold-settings.sh).
#   - "go/Go" uses word-boundary matching (\bgo\b) to avoid false positives
#     (e.g., "algorithm", "cargo", "django").

# ---------------------------------------------------------------------------
# Technology keyword patterns (extended regex, case-insensitive) and their
# corresponding Bash permission strings. Parallel arrays — indices must match.
# ---------------------------------------------------------------------------
TECH_PATTERNS=(
  'julia'
  'python|pip'
  'npm|node'
  'cargo|rust'
  '\bmake\b|makefile'
  '\bgo\b'
  '\bpip\b'
  '\byarn\b'
  'docker'
)

TECH_PERMS=(
  'Bash(julia *)'
  'Bash(python *)'
  'Bash(npm *)'
  'Bash(cargo *)'
  'Bash(make *)'
  'Bash(go *)'
  'Bash(pip *)'
  'Bash(yarn *)'
  'Bash(docker *)'
)

# ---------------------------------------------------------------------------
# Source shared helper library
# ---------------------------------------------------------------------------
source "$(dirname "$0")/pcv-lib.sh"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
PROJECT_DIR="${PWD}"

while [ $# -gt 0 ]; do
  case "$1" in
    --project-dir)
      if [ -z "$2" ]; then
        printf 'tech-permissions-scan.sh: --project-dir requires a path argument\n' >&2
        exit 1
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    *)
      printf 'tech-permissions-scan.sh: unknown argument: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

CLAUDE_DIR="${PROJECT_DIR}/.claude"
SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
CHARGE_FILE="${PROJECT_DIR}/pcvplans/charge.md"

# ---------------------------------------------------------------------------
# Validate required inputs
# ---------------------------------------------------------------------------
if [ ! -f "${CHARGE_FILE}" ]; then
  printf 'tech-permissions-scan.sh: charge.md not found at %s\n' "${CHARGE_FILE}" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Collect scan files
# ---------------------------------------------------------------------------
SCAN_FILES=("${CHARGE_FILE}")

if [ -f "${PROJECT_DIR}/pcvplans/construction-plan.md" ]; then
  SCAN_FILES+=("${PROJECT_DIR}/pcvplans/construction-plan.md")
elif [ -f "${PROJECT_DIR}/pcvplans/lite-plan.md" ]; then
  SCAN_FILES+=("${PROJECT_DIR}/pcvplans/lite-plan.md")
fi

# ---------------------------------------------------------------------------
# Build combined content in a temp file.
# Use CLAUDE_DIR if it exists, otherwise fall back to PROJECT_DIR.
# ---------------------------------------------------------------------------
if [ -d "${CLAUDE_DIR}" ]; then
  COMBINED="${CLAUDE_DIR}/tmpclaude_scan_$$"
else
  COMBINED="${PROJECT_DIR}/tmpclaude_scan_$$"
fi

for f in "${SCAN_FILES[@]}"; do
  cat "$f" >> "${COMBINED}"
  printf '\n' >> "${COMBINED}"
done

# ---------------------------------------------------------------------------
# Helper: check whether content file matches an extended-regex pattern.
# Case-insensitive.
# ---------------------------------------------------------------------------
content_matches() {
  local pattern="$1"
  grep -qiE "$pattern" "${COMBINED}" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Scan for technology keywords and collect needed permissions
# ---------------------------------------------------------------------------
NEEDED_PERMS=()

idx=0
while [ $idx -lt ${#TECH_PATTERNS[@]} ]; do
  pattern="${TECH_PATTERNS[$idx]}"
  perm="${TECH_PERMS[$idx]}"
  idx=$((idx + 1))

  if content_matches "$pattern"; then
    # Avoid duplicates within the detected list
    already_needed=false
    for p in "${NEEDED_PERMS[@]}"; do
      if [ "$p" = "$perm" ]; then
        already_needed=true
        break
      fi
    done
    if [ "$already_needed" = false ]; then
      NEEDED_PERMS+=("$perm")
    fi
  fi
done

# Clean up combined temp file
rm -f "${COMBINED}"

# ---------------------------------------------------------------------------
# If no technologies detected, nothing to do
# ---------------------------------------------------------------------------
if [ ${#NEEDED_PERMS[@]} -eq 0 ]; then
  printf 'No new permissions needed.\n'
  exit 0
fi

# ---------------------------------------------------------------------------
# Check settings.json — determine which permissions are already present
# ---------------------------------------------------------------------------
MISSING_PERMS=()

if [ ! -f "${SETTINGS_FILE}" ]; then
  # No settings.json yet — all detected permissions are missing
  MISSING_PERMS=("${NEEDED_PERMS[@]}")
else
  for perm in "${NEEDED_PERMS[@]}"; do
    if ! string_in_file "${SETTINGS_FILE}" "$perm"; then
      MISSING_PERMS+=("$perm")
    fi
  done
fi

if [ ${#MISSING_PERMS[@]} -eq 0 ]; then
  printf 'No new permissions needed.\n'
  exit 0
fi

# ---------------------------------------------------------------------------
# Ensure .claude/ directory and settings.json exist before editing
# ---------------------------------------------------------------------------
if [ ! -d "${CLAUDE_DIR}" ]; then
  mkdir -p "${CLAUDE_DIR}"
  if [ $? -ne 0 ]; then
    printf 'tech-permissions-scan.sh: failed to create directory: %s\n' "${CLAUDE_DIR}" >&2
    exit 1
  fi
fi

if [ ! -f "${SETTINGS_FILE}" ]; then
  # Create a minimal valid settings.json with an empty allow array
  printf '{\n  "permissions": {\n    "allow": []\n  }\n}\n' > "${SETTINGS_FILE}"
  if [ $? -ne 0 ]; then
    printf 'tech-permissions-scan.sh: failed to create %s\n' "${SETTINGS_FILE}" >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Validate JSON shape before editing
# ---------------------------------------------------------------------------
if ! is_valid_json_shape "${SETTINGS_FILE}"; then
  printf 'tech-permissions-scan.sh: settings.json appears malformed — run scaffold-settings.sh first\n' >&2
  exit 1
fi

if ! grep -q '"allow"' "${SETTINGS_FILE}" 2>/dev/null; then
  printf 'tech-permissions-scan.sh: settings.json has no allow array — run scaffold-settings.sh first\n' >&2
  exit 1
fi

normalize_allow_array "${SETTINGS_FILE}"
if [ $? -ne 0 ]; then
  printf 'tech-permissions-scan.sh: failed to normalize allow array\n' >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Add missing permissions to settings.json
# ---------------------------------------------------------------------------
ADDED=()

for perm in "${MISSING_PERMS[@]}"; do
  append_to_allow_array "${SETTINGS_FILE}" "$perm"
  if [ $? -ne 0 ]; then
    printf 'tech-permissions-scan.sh: failed to add permission: %s\n' "$perm" >&2
    exit 1
  fi
  ADDED+=("$perm")
done

# ---------------------------------------------------------------------------
# Final validation
# ---------------------------------------------------------------------------
if ! is_valid_json_shape "${SETTINGS_FILE}"; then
  printf 'tech-permissions-scan.sh: error: post-edit JSON validation failed\n' >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
if [ ${#ADDED[@]} -gt 0 ]; then
  printf 'Added: '
  first=true
  for perm in "${ADDED[@]}"; do
    if [ "$first" = true ]; then
      printf '%s' "$perm"
      first=false
    else
      printf ', %s' "$perm"
    fi
  done
  printf '\n'
fi

exit 0
