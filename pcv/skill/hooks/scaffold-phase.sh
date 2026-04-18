#!/usr/bin/env bash
# scaffold-phase.sh — PCV utility: create mechanical files for a new phase subfolder
#
# Purpose: Scaffolds a new phase directory inside a multi-phase PCV project,
#          replacing the manual file-creation steps in phase-transition-protocol.md §5.
#          Creates CLAUDE.md, .claude/settings.json (via scaffold-settings.sh),
#          and pcvplans/.gitkeep. Does NOT create charge.md (requires LLM synthesis).
#
# Usage:
#   bash ~/.claude/skills/pcv/hooks/scaffold-phase.sh \
#     --phase-name <name> \
#     --project-name <name> \
#     [--parent-dir <path>]
#
# Arguments:
#   --phase-name    <name>   Required. Human-readable phase name (e.g. "Permissions + Format").
#                            Lowercased and hyphenated for the directory name.
#   --project-name  <name>   Required. Project name for CLAUDE.md header line.
#   --parent-dir    <path>   Optional. Absolute path of parent directory containing
#                            phase-* subdirectories. Defaults to current working directory.
#
# Exit semantics:
#   exit 0  — phase subfolder created successfully; path printed to stdout
#   exit 1  — error (missing args, scaffold-settings.sh failure, etc.); message to stderr

# --- Argument parsing ---
PHASE_NAME=""
PROJECT_NAME=""
PARENT_DIR="$PWD"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --phase-name)
      PHASE_NAME="$2"
      shift
      shift
      ;;
    --project-name)
      PROJECT_NAME="$2"
      shift
      shift
      ;;
    --parent-dir)
      PARENT_DIR="$2"
      shift
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# --- Validate required arguments ---
if [ -z "$PHASE_NAME" ]; then
  echo "Error: --phase-name is required." >&2
  exit 1
fi

if [ -z "$PROJECT_NAME" ]; then
  echo "Error: --project-name is required." >&2
  exit 1
fi

if [ ! -d "$PARENT_DIR" ]; then
  echo "Error: --parent-dir does not exist: $PARENT_DIR" >&2
  exit 1
fi

# --- Determine next phase number ---
MAX_N=0

for DIR in "$PARENT_DIR"/phase-*/; do
  if [ -d "$DIR" ]; then
    BASENAME_DIR=$(basename "$DIR")
    # Extract numeric prefix after "phase-"
    NUM=$(printf '%s' "$BASENAME_DIR" | sed 's/^phase-\([0-9]*\)-.*/\1/')
    # Only update if NUM is purely numeric
    case "$NUM" in
      ''|*[!0-9]*)
        # not a number, skip
        ;;
      *)
        if [ "$NUM" -gt "$MAX_N" ]; then
          MAX_N="$NUM"
        fi
        ;;
    esac
  fi
done

NEXT_N=$((MAX_N + 1))

# --- Build directory name: lowercase phase-name, spaces to hyphens ---
PHASE_SLUG=$(printf '%s' "$PHASE_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
PHASE_DIR="$PARENT_DIR/phase-${NEXT_N}-${PHASE_SLUG}"

# --- Create phase directory ---
mkdir -p "$PHASE_DIR"
if [ ! -d "$PHASE_DIR" ]; then
  echo "Error: Failed to create phase directory: $PHASE_DIR" >&2
  exit 1
fi

# --- Create CLAUDE.md ---
CLAUDE_MD_PATH="$PHASE_DIR/CLAUDE.md"
printf '# %s — %s\nLanguage: [placeholder]\nWhen compacting, preserve decision log (pcvplans/logs/decision-log.md) and all files in pcvplans/.\n' \
  "$PROJECT_NAME" "$PHASE_NAME" > "$CLAUDE_MD_PATH"

if [ ! -f "$CLAUDE_MD_PATH" ]; then
  echo "Error: Failed to create CLAUDE.md at $CLAUDE_MD_PATH" >&2
  rm -rf "$PHASE_DIR"
  exit 1
fi

# --- Create .claude/settings.json via scaffold-settings.sh ---
bash ~/.claude/skills/pcv/hooks/scaffold-settings.sh --project-dir "$PHASE_DIR"
SCAFFOLD_EXIT=$?

if [ "$SCAFFOLD_EXIT" -ne 0 ]; then
  echo "Error: scaffold-settings.sh failed (exit $SCAFFOLD_EXIT). Removing partial phase directory." >&2
  rm -rf "$PHASE_DIR"
  exit 1
fi

# --- Create pcvplans/.gitkeep ---
mkdir -p "$PHASE_DIR/pcvplans"
touch "$PHASE_DIR/pcvplans/.gitkeep"

if [ ! -f "$PHASE_DIR/pcvplans/.gitkeep" ]; then
  echo "Error: Failed to create pcvplans/.gitkeep" >&2
  rm -rf "$PHASE_DIR"
  exit 1
fi

# --- Success ---
echo "Phase subfolder created at $PHASE_DIR"
exit 0
