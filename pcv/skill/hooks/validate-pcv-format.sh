#!/usr/bin/env bash
# validate-pcv-format.sh — PCV v3.12
#
# Purpose:
#   Structural validation for PCV artifact files. Checks that required headers,
#   separators, and sections are present. Does NOT evaluate content quality —
#   that is LLM judgment, not structural checking.
#
# Usage:
#   bash validate-pcv-format.sh [--project-dir <path>] [--file <specific-file>]
#
# Arguments:
#   --project-dir <path>   Project root (default: CLAUDE_PROJECT_DIR or PWD).
#   --file <path>          Validate only this file. If omitted, all known PCV
#                          artifact files that exist in the project are checked.
#
# File types and rules:
#
#   decision-log.md / master-log.md
#     - Begins with: # Decision Log   OR   # Master Decision Log
#     - Every ## header of the form "## Something — YYYY-MM-DD" uses that date
#       format (YYYY-MM-DD, not spelled-out months or other formats).
#     - Every milestone ## entry is followed eventually by a --- separator.
#     - No duplicate "## Project Closeout" headers (indicates corruption).
#
#   build-record.md
#     - Begins with: # Build Record
#     - Required sections: ## Overview, ## Files Modified, ## Verification Status
#     - Verification Status section is not followed immediately by a blank line
#       then the next ## header with no content in between (catches "Pending"
#       left blank after verification completes).
#       Implementation: the line immediately after "## Verification Status" must
#       not be empty AND then a new ## section — i.e., there must be at least
#       one non-blank, non-## line in the section.
#
#   project-summary.md / project-summary-phase-*.md
#     - Begins with: # Project Summary
#     - Required fields present: **Author:** and **Date:**
#     - Required sections: ## Charge Summary, ## Deliverable Summary,
#       ## Verification
#
# Output:
#   Violations are written to stderr, one line per violation, format:
#     <file>:<line>: <description>    (when line number is known)
#     <file>: <description>           (when line number is not applicable)
#   stdout is empty.
#   If no violations: no output and exit 0.
#   If violations found: exit 1.
#
# Exit codes:
#   0  All checked files are structurally valid (or no known PCV files found).
#   1  One or more violations detected (details on stderr).
#   2  Argument error (bad flag or missing required value).
#
# Design constraints:
#   - Structural checks only — grep-based, no content parsing.
#   - Pure bash. No jq dependency.
#   - Fast: each check is a single grep pass over one file.

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
SPECIFIC_FILE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --project-dir)
      if [ -z "$2" ]; then
        printf 'validate-pcv-format.sh: --project-dir requires a path argument\n' >&2
        exit 2
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    --file)
      if [ -z "$2" ]; then
        printf 'validate-pcv-format.sh: --file requires a path argument\n' >&2
        exit 2
      fi
      SPECIFIC_FILE="$2"
      shift 2
      ;;
    *)
      printf 'validate-pcv-format.sh: unknown argument: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Tracking: violation counter
# ---------------------------------------------------------------------------
VIOLATIONS=0

# ---------------------------------------------------------------------------
# Helper: emit one violation to stderr and increment counter.
# Usage: violation <file> [<line>] <description>
#   If <line> is a number, include it; otherwise treat second arg as description.
# ---------------------------------------------------------------------------
violation() {
  local file="$1"
  local line_or_desc="$2"
  local desc="$3"
  if [ -n "$desc" ]; then
    printf '%s:%s: %s\n' "$file" "$line_or_desc" "$desc" >&2
  else
    printf '%s: %s\n' "$file" "$line_or_desc" >&2
  fi
  VIOLATIONS=$((VIOLATIONS + 1))
}

# ---------------------------------------------------------------------------
# Helper: get the line number of the first match of a pattern.
# Returns 0 (not found) or the line number (1-based).
# ---------------------------------------------------------------------------
first_match_line() {
  local file="$1"
  local pattern="$2"
  grep -n "$pattern" "$file" 2>/dev/null | head -1 | cut -d: -f1
}

# ---------------------------------------------------------------------------
# Validator: decision-log.md / master-log.md
# ---------------------------------------------------------------------------
validate_decision_log() {
  local file="$1"

  # Rule 1: File begins with "# Decision Log" or "# Master Decision Log"
  # Allow subtitle after the heading (e.g. "# Decision Log — Phase 2 ...").
  local first_line
  first_line="$(head -1 "$file" 2>/dev/null)"
  case "$first_line" in
    "# Decision Log"*|"# Master Decision Log"*) ;;
    *) violation "$file" 1 "file must begin with '# Decision Log' or '# Master Decision Log'; found: $first_line" ;;
  esac

  # Rule 2: Date format on milestone ## headers.
  # Pattern: "## <title> — <date>" where date must be YYYY-MM-DD.
  # We accept only the em-dash (—) variant per spec.
  # Check: any ## line containing " — " must have YYYY-MM-DD at end.
  # Lines matching "## .* — " but NOT ending in YYYY-MM-DD are violations.
  while IFS= read -r match; do
    local lineno text
    lineno="${match%%:*}"
    text="${match#*:}"
    # Check date portion: must end with 4-digit-dash-2-digit-dash-2-digit
    if printf '%s' "$text" | grep -qE -- '— [0-9]{4}-[0-9]{2}-[0-9]{2}( \[MILESTONE:[A-Z_0-9]+\])?$'; then
      : # valid
    else
      violation "$file" "$lineno" "milestone header date must be YYYY-MM-DD format: $text"
    fi
  done <<HERE
$(grep -n '^## .*—' "$file" 2>/dev/null)
HERE

  # Rule 3: Every ## milestone entry must be followed by a --- separator.
  # Approach: collect all ## header line numbers, then for each check that
  # a "^---$" line appears before the next ## header (or EOF).
  # We do a single sequential pass through the file, tracking state.
  local in_entry=0
  local entry_line=0
  local has_sep=0
  local current_line=0
  while IFS= read -r line; do
    current_line=$((current_line + 1))
    case "$line" in
      "## "*)
        if [ $in_entry -eq 1 ] && [ $has_sep -eq 0 ]; then
          violation "$file" "$entry_line" "milestone entry '$(sed -n "${entry_line}p" "$file" 2>/dev/null)' has no '---' separator before next entry"
        fi
        in_entry=1
        entry_line=$current_line
        has_sep=0
        ;;
      "---")
        has_sep=1
        ;;
    esac
  done < "$file"
  # Check final entry
  if [ $in_entry -eq 1 ] && [ $has_sep -eq 0 ]; then
    violation "$file" "$entry_line" "last milestone entry has no '---' separator"
  fi

  # Rule 4: No duplicate "## Project Closeout" headers.
  local closeout_count
  closeout_count="$(grep -c '^## \(\[TEST\] \)\?Project Closeout' "$file" 2>/dev/null || true)"
  if [ "$closeout_count" -gt 1 ]; then
    violation "$file" "duplicate '## Project Closeout' headers found ($closeout_count occurrences — possible corruption)"
  fi
}

# ---------------------------------------------------------------------------
# Validator: build-record.md
# ---------------------------------------------------------------------------
validate_build_record() {
  local file="$1"

  # Rule 1: File begins with "# Build Record"
  # Allow subtitle after the heading (e.g. "# Build Record — Phase 2 ...").
  local first_line
  first_line="$(head -1 "$file" 2>/dev/null)"
  case "$first_line" in
    "# Build Record"*) ;;
    *) violation "$file" 1 "file must begin with '# Build Record'; found: $first_line" ;;
  esac

  # Rule 2: Required sections present
  for section in "## Overview" "## Files Modified" "## Verification Status"; do
    if ! grep -q "^${section}$" "$file" 2>/dev/null; then
      violation "$file" "missing required section: $section"
    fi
  done

  # Rule 3: Verification Status section must not be blank.
  # Check: the line after "## Verification Status" must not be the next ## header
  # with no content lines in between (allowing blank lines, but requiring at
  # least one non-blank, non-## content line before the next ## or EOF).
  if grep -q '^## Verification Status$' "$file" 2>/dev/null; then
    local found_content=0
    local past_header=0
    while IFS= read -r line; do
      if [ $past_header -eq 0 ]; then
        if [ "$line" = "## Verification Status" ]; then
          past_header=1
        fi
        continue
      fi
      # past_header=1: we are inside the Verification Status section
      case "$line" in
        "## "*)
          # Reached next section header — stop scanning
          break
          ;;
        "")
          : # blank line — continue
          ;;
        *)
          found_content=1
          break
          ;;
      esac
    done < "$file"
    if [ $found_content -eq 0 ]; then
      local vs_line
      vs_line="$(first_match_line "$file" '^## Verification Status$')"
      violation "$file" "${vs_line:-?}" "'## Verification Status' section has no content (may be left as 'Pending')"
    fi
  fi
}

# ---------------------------------------------------------------------------
# Validator: project-summary.md (including project-summary-phase-*.md)
# ---------------------------------------------------------------------------
validate_project_summary() {
  local file="$1"

  # Rule 1: File begins with "# Project Summary"
  # Allow subtitle after the heading (e.g. "# Project Summary — Phase 2 ...").
  local first_line
  first_line="$(head -1 "$file" 2>/dev/null)"
  case "$first_line" in
    "# Project Summary"*) ;;
    *) violation "$file" 1 "file must begin with '# Project Summary'; found: $first_line" ;;
  esac

  # Rule 2: Required fields
  for field in '\*\*Author:\*\*' '\*\*Date:\*\*'; do
    local display_field
    display_field="$(printf '%s' "$field" | sed 's/\\//g')"
    if ! grep -q "$field" "$file" 2>/dev/null; then
      violation "$file" "missing required field: $display_field"
    fi
  done

  # Rule 3: Required sections
  for section in "## Charge Summary" "## Deliverable Summary" "## Verification"; do
    if ! grep -q "^${section}$" "$file" 2>/dev/null; then
      violation "$file" "missing required section: $section"
    fi
  done
}

# ---------------------------------------------------------------------------
# Dispatch: determine file type from basename and run the right validator.
# Returns 1 if file type is unknown (not a PCV artifact), 0 otherwise.
# ---------------------------------------------------------------------------
validate_file() {
  local file="$1"
  local base
  base="$(basename "$file")"

  case "$base" in
    decision-log.md|master-log.md)
      validate_decision_log "$file"
      ;;
    build-record.md)
      validate_build_record "$file"
      ;;
    project-summary.md|project-summary-phase-*.md)
      validate_project_summary "$file"
      ;;
    *)
      # Not a known PCV artifact — skip silently per spec
      return 1
      ;;
  esac
  return 0
}

# ---------------------------------------------------------------------------
# MAIN LOGIC
# ---------------------------------------------------------------------------

if [ -n "$SPECIFIC_FILE" ]; then
  # ---- Single-file mode: --file was specified --------------------------------
  if [ ! -f "$SPECIFIC_FILE" ]; then
    # File doesn't exist — nothing to validate; exit 0 silently
    exit 0
  fi
  validate_file "$SPECIFIC_FILE"
  # If unknown type, validate_file returns 1 but VIOLATIONS stays 0 — exit 0
else
  # ---- Full-project mode: scan all known PCV artifact locations ---------------
  LOGS_DIR="${PROJECT_DIR}/pcvplans/logs"

  CANDIDATE_FILES=(
    "${LOGS_DIR}/decision-log.md"
    "${LOGS_DIR}/master-log.md"
    "${PROJECT_DIR}/pcvplans/build-record.md"
    "${PROJECT_DIR}/pcvplans/project-summary.md"
  )

  # Also pick up project-summary-phase-*.md if any exist
  for f in "${PROJECT_DIR}/pcvplans/project-summary-phase-"*.md; do
    if [ -f "$f" ]; then
      CANDIDATE_FILES+=("$f")
    fi
  done

  for file in "${CANDIDATE_FILES[@]}"; do
    if [ -f "$file" ]; then
      validate_file "$file"
    fi
  done
fi

# ---------------------------------------------------------------------------
# Exit
# ---------------------------------------------------------------------------
if [ "$VIOLATIONS" -gt 0 ]; then
  exit 1
fi
exit 0
