#!/usr/bin/env bash
# scaffold-settings.sh — PCV v3.11 Phase 3
#
# Purpose:
#   Single source of truth for .claude/settings.json generation. Creates or
#   merges PCV permissions and hooks into a project's settings.json file.
#
# Usage:
#   bash scaffold-settings.sh [--project-dir <path>]
#
# Arguments:
#   --project-dir <path>   Target project directory (default: current directory).
#   --merge-to-global <path>
#                          Bypass project-level settings; merge PCV allow-list
#                          directly into the given settings.json (typically
#                          ~/.claude/settings.json). Hooks block is NOT
#                          written in this mode — global settings are for
#                          permissions only. (v3.14)
#
# Behavior:
#   - If .claude/settings.json exists: merge PCV entries, preserve all others.
#   - If .claude/settings.json does not exist: create with full PCV defaults.
#   - Overwrites malformed (non-JSON) files with warning to stderr.
#
# Exit codes:
#   0  Success
#   1  Error (message written to stderr)
#
# Design constraints:
#   - Pure bash JSON generation. No jq dependency.
#   - awk for merge operations; insertion content passed via temp files to
#     preserve newlines (awk -v collapses them).
#   - Handles: empty file, malformed JSON, missing permissions.allow array.

# ---------------------------------------------------------------------------
# Hardcoded PCV permission entries (allow rules)
# ---------------------------------------------------------------------------
PCV_ALLOW_ENTRIES=(
  'Read(~/.claude/agents/pcv-critic.md)'
  'Read(~/.claude/agents/pcv-research.md)'
  'Read(~/.claude/agents/pcv-builder.md)'
  'Read(~/.claude/agents/pcv-verifier.md)'
  'Read(~/.claude/skills/pcv/**)'
  'Read(**)'
  'Write(**)'
  'Edit(**)'
  'Glob(*)'
  'Grep(*)'
  'Bash(git *)'
  # v3.14: permission expansion — PCV-internal invocations pre-approved at
  # project level to prevent workflow-friction prompts during normal operation.
  # Broad home/temp-dir Read/Write/Edit patterns are intentionally excluded;
  # they belong at the global level only. Idempotency is handled by the
  # existing merge logic (jq set-subtraction on the fast path; string_in_file
  # guard on the bash fallback) — adding a duplicate entry here is a no-op.
  'Bash(rm /tmp/tmpclaude*)'
  'Bash(mkdir -p /tmp/*)'
  'Bash(bash ~/.claude/skills/pcv/hooks/*)'
  'Bash(bash ~/.claude/skills/pcv/handlers/*)'
  'Bash(git -C * *)'
)

# ---------------------------------------------------------------------------
# Hardcoded PCV hook commands
# ---------------------------------------------------------------------------
PCV_HOOK_SESSIONSTART='bash ~/.claude/skills/pcv/hooks/session-start-resume.sh'
PCV_HOOK_STOP='bash ~/.claude/skills/pcv/hooks/stop-closeout.sh'
PCV_HOOK_PRECOMPACT='bash ~/.claude/skills/pcv/hooks/pre-compact-snapshot.sh'
PCV_HOOK_SUBAGENT_STOP='bash ~/.claude/skills/pcv/hooks/subagent-stop-track.sh'
PCV_HOOK_POSTTOOLUSE='bash ~/.claude/skills/pcv/hooks/post-tool-use-format.sh'
PCV_HOOK_POSTTOOLUSE_MATCHER='Write'

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
PROJECT_DIR="${PWD}"
MERGE_TO_GLOBAL=""

while [ $# -gt 0 ]; do
  case "$1" in
    --project-dir)
      if [ -z "$2" ]; then
        printf 'scaffold-settings.sh: --project-dir requires a path argument\n' >&2
        exit 1
      fi
      PROJECT_DIR="$2"
      shift 2
      ;;
    --merge-to-global)
      if [ -z "$2" ]; then
        printf 'scaffold-settings.sh: --merge-to-global requires a path argument\n' >&2
        exit 1
      fi
      MERGE_TO_GLOBAL="$2"
      shift 2
      ;;
    *)
      printf 'scaffold-settings.sh: unknown argument: %s\n' "$1" >&2
      exit 1
      ;;
  esac
done

if [ -n "${MERGE_TO_GLOBAL}" ]; then
  # Global-merge mode: target directly (no project .claude/ prefix).
  SETTINGS_FILE="${MERGE_TO_GLOBAL}"
  CLAUDE_DIR="$(dirname "${SETTINGS_FILE}")"
else
  CLAUDE_DIR="${PROJECT_DIR}/.claude"
  SETTINGS_FILE="${CLAUDE_DIR}/settings.json"
fi

# ---------------------------------------------------------------------------
# Source shared helper library
# ---------------------------------------------------------------------------
source "$(dirname "$0")/pcv-lib.sh"

# ---------------------------------------------------------------------------
# Ensure .claude/ directory exists
# ---------------------------------------------------------------------------
mkdir -p "${CLAUDE_DIR}"
if [ $? -ne 0 ]; then
  printf 'scaffold-settings.sh: failed to create directory: %s\n' "${CLAUDE_DIR}" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Helper: emit the full PCV settings.json (fresh create path)
# ---------------------------------------------------------------------------
emit_full_settings() {
  printf '{\n'
  printf '  "permissions": {\n'
  printf '    "allow": [\n'
  local count=${#PCV_ALLOW_ENTRIES[@]}
  local i=0
  for entry in "${PCV_ALLOW_ENTRIES[@]}"; do
    i=$((i + 1))
    if [ $i -lt $count ]; then
      printf '      "%s",\n' "$entry"
    else
      printf '      "%s"\n' "$entry"
    fi
  done
  printf '    ]\n'
  printf '  },\n'
  printf '  "hooks": {\n'
  printf '    "SessionStart": [\n'
  printf '      {\n'
  printf '        "hooks": [\n'
  printf '          {\n'
  printf '            "type": "command",\n'
  printf '            "command": "%s"\n' "${PCV_HOOK_SESSIONSTART}"
  printf '          }\n'
  printf '        ]\n'
  printf '      }\n'
  printf '    ],\n'
  printf '    "Stop": [\n'
  printf '      {\n'
  printf '        "hooks": [\n'
  printf '          {\n'
  printf '            "type": "command",\n'
  printf '            "command": "%s"\n' "${PCV_HOOK_STOP}"
  printf '          }\n'
  printf '        ]\n'
  printf '      }\n'
  printf '    ],\n'
  printf '    "PreCompact": [\n'
  printf '      {\n'
  printf '        "hooks": [\n'
  printf '          {\n'
  printf '            "type": "command",\n'
  printf '            "command": "%s"\n' "${PCV_HOOK_PRECOMPACT}"
  printf '          }\n'
  printf '        ]\n'
  printf '      }\n'
  printf '    ],\n'
  printf '    "SubagentStop": [\n'
  printf '      {\n'
  printf '        "hooks": [\n'
  printf '          {\n'
  printf '            "type": "command",\n'
  printf '            "command": "%s"\n' "${PCV_HOOK_SUBAGENT_STOP}"
  printf '          }\n'
  printf '        ]\n'
  printf '      }\n'
  printf '    ],\n'
  printf '    "PostToolUse": [\n'
  printf '      {\n'
  printf '        "matcher": "%s",\n' "${PCV_HOOK_POSTTOOLUSE_MATCHER}"
  printf '        "hooks": [\n'
  printf '          {\n'
  printf '            "type": "command",\n'
  printf '            "command": "%s"\n' "${PCV_HOOK_POSTTOOLUSE}"
  printf '          }\n'
  printf '        ]\n'
  printf '      }\n'
  printf '    ]\n'
  printf '  }\n'
  printf '}\n'
}

# ---------------------------------------------------------------------------
# Helper: write one hook event block to stdout (no trailing comma or newline
# after the closing ']').
# ---------------------------------------------------------------------------
emit_hook_event_block() {
  local event="$1"
  local cmd="$2"
  printf '    "%s": [\n' "$event"
  printf '      {\n'
  printf '        "hooks": [\n'
  printf '          {\n'
  printf '            "type": "command",\n'
  printf '            "command": "%s"\n' "$cmd"
  printf '          }\n'
  printf '        ]\n'
  printf '      }\n'
  printf '    ]'
}

# ---------------------------------------------------------------------------
# Helper: write one hook event block WITH a matcher field (e.g., PostToolUse).
# Same as emit_hook_event_block but inserts "matcher" before "hooks" array.
# ---------------------------------------------------------------------------
emit_hook_event_block_with_matcher() {
  local event="$1"
  local cmd="$2"
  local matcher="$3"
  printf '    "%s": [\n' "$event"
  printf '      {\n'
  printf '        "matcher": "%s",\n' "$matcher"
  printf '        "hooks": [\n'
  printf '          {\n'
  printf '            "type": "command",\n'
  printf '            "command": "%s"\n' "$cmd"
  printf '          }\n'
  printf '        ]\n'
  printf '      }\n'
  printf '    ]'
}


# ---------------------------------------------------------------------------
# Helper: insert lines from a content file before the last '}' line in the
# target file. Uses awk to read insertion content via a second input file,
# preserving all newlines. Writes to a temp file then moves into place.
#
# Arguments:
#   $1  target file to modify
#   $2  content file whose lines to insert before the last '}'
# ---------------------------------------------------------------------------
insert_file_before_last_brace() {
  local target="$1"
  local content_file="$2"
  local tmpfile
  tmpfile="${CLAUDE_DIR}/tmpclaude_ibrace_$$"

  awk '
    FNR == NR {
      # First file pass: read target into lines array
      lines[NR] = $0
      total = NR
      next
    }
    # Second file pass: read insertion content into ins array
    {
      ins[++ins_count] = $0
    }
    END {
      # Find last line in target that is just a closing brace
      last_brace = 0
      for (i = total; i >= 1; i--) {
        if (lines[i] ~ /^[[:space:]]*\}[[:space:]]*$/) {
          last_brace = i
          break
        }
      }
      # Find the last non-empty line before last_brace to stitch the leading
      # comma onto (avoids comma on its own line).
      last_content = 0
      for (i = last_brace - 1; i >= 1; i--) {
        if (lines[i] ~ /[^[:space:]]/) {
          last_content = i
          break
        }
      }
      # Determine if we should stitch the leading comma
      stitch = (ins_count > 0 && ins[1] ~ /^,[[:space:]]*$/) ? 1 : 0
      for (i = 1; i <= total; i++) {
        if (i == last_brace) {
          for (j = 1; j <= ins_count; j++) {
            # Skip first insertion line (comma) if we stitched it onto last_content
            if (stitch && j == 1) continue
            print ins[j]
          }
        }
        if (stitch && i == last_content) {
          # Stitch leading comma onto this line
          line = lines[i]
          sub(/[[:space:]]*$/, ",", line)
          print line
        } else {
          print lines[i]
        }
      }
    }
  ' "$target" "$content_file" > "$tmpfile"

  if [ $? -ne 0 ]; then
    rm -f "$tmpfile"
    return 1
  fi
  cp "$tmpfile" "$target"
  rm -f "$tmpfile"
}

# ---------------------------------------------------------------------------
# Helper: add the full hooks section to a file that has no hooks key.
# Writes the block to a temp content file then calls insert_file_before_last_brace.
# ---------------------------------------------------------------------------
add_hooks_section() {
  local file="$1"
  local content_file
  content_file="${CLAUDE_DIR}/tmpclaude_hooks_content_$$"

  # The insertion goes before the final '}', so we need a leading comma on the
  # hooks section to close off whatever came before it.
  printf ',\n' > "$content_file"
  printf '  "hooks": {\n' >> "$content_file"
  emit_hook_event_block 'SessionStart' "${PCV_HOOK_SESSIONSTART}" >> "$content_file"
  printf ',\n' >> "$content_file"
  emit_hook_event_block 'Stop' "${PCV_HOOK_STOP}" >> "$content_file"
  printf ',\n' >> "$content_file"
  emit_hook_event_block 'PreCompact' "${PCV_HOOK_PRECOMPACT}" >> "$content_file"
  printf ',\n' >> "$content_file"
  emit_hook_event_block 'SubagentStop' "${PCV_HOOK_SUBAGENT_STOP}" >> "$content_file"
  printf ',\n' >> "$content_file"
  emit_hook_event_block_with_matcher 'PostToolUse' "${PCV_HOOK_POSTTOOLUSE}" "${PCV_HOOK_POSTTOOLUSE_MATCHER}" >> "$content_file"
  printf '\n  }\n' >> "$content_file"

  insert_file_before_last_brace "$file" "$content_file"
  local rc=$?
  rm -f "$content_file"
  return $rc
}

# ---------------------------------------------------------------------------
# Helper: add a single hook event to an existing hooks object.
# Inserts the new event block before the closing '}' of the hooks object,
# which is the second-to-last top-level closing brace.
# ---------------------------------------------------------------------------
add_hook_event() {
  local file="$1"
  local event="$2"
  local cmd="$3"
  local tmpfile content_file
  tmpfile="${CLAUDE_DIR}/tmpclaude_hook_$$"
  content_file="${CLAUDE_DIR}/tmpclaude_hook_content_$$"

  # Build the insertion block (with leading comma to append to previous entry)
  printf ',\n' > "$content_file"
  emit_hook_event_block "$event" "$cmd" >> "$content_file"
  printf '\n' >> "$content_file"

  # awk: buffer all lines, find the second-to-last top-level closing brace,
  # insert content_file lines before it.
  awk '
    FNR == NR {
      lines[NR] = $0
      total = NR
      next
    }
    { ins[++ins_count] = $0 }
    END {
      # Find the last two lines that are solo closing braces
      count = 0
      for (i = total; i >= 1; i--) {
        if (lines[i] ~ /^[[:space:]]*\}[[:space:]]*$/) {
          count++
          if (count == 1) b1 = i
          if (count == 2) { b2 = i; break }
        }
      }
      target = b2
      for (i = 1; i <= total; i++) {
        if (i == target) {
          for (j = 1; j <= ins_count; j++) print ins[j]
        }
        print lines[i]
      }
    }
  ' "$file" "$content_file" > "$tmpfile"

  local rc=$?
  rm -f "$content_file"
  if [ $rc -ne 0 ]; then
    rm -f "$tmpfile"
    return 1
  fi
  cp "$tmpfile" "$file"
  rm -f "$tmpfile"
}

# ---------------------------------------------------------------------------
# Helper: add a single hook event WITH matcher to an existing hooks object.
# Same insertion logic as add_hook_event but uses the matcher-aware emitter.
# ---------------------------------------------------------------------------
add_hook_event_with_matcher() {
  local file="$1"
  local event="$2"
  local cmd="$3"
  local matcher="$4"
  local tmpfile content_file
  tmpfile="${CLAUDE_DIR}/tmpclaude_hook_$$"
  content_file="${CLAUDE_DIR}/tmpclaude_hook_content_$$"

  printf ',\n' > "$content_file"
  emit_hook_event_block_with_matcher "$event" "$cmd" "$matcher" >> "$content_file"
  printf '\n' >> "$content_file"

  awk '
    FNR == NR {
      lines[NR] = $0
      total = NR
      next
    }
    { ins[++ins_count] = $0 }
    END {
      count = 0
      for (i = total; i >= 1; i--) {
        if (lines[i] ~ /^[[:space:]]*\}[[:space:]]*$/) {
          count++
          if (count == 1) b1 = i
          if (count == 2) { b2 = i; break }
        }
      }
      target = b2
      for (i = 1; i <= total; i++) {
        if (i == target) {
          for (j = 1; j <= ins_count; j++) print ins[j]
        }
        print lines[i]
      }
    }
  ' "$file" "$content_file" > "$tmpfile"

  local rc=$?
  rm -f "$content_file"
  if [ $rc -ne 0 ]; then
    rm -f "$tmpfile"
    return 1
  fi
  cp "$tmpfile" "$file"
  rm -f "$tmpfile"
}

# ---------------------------------------------------------------------------
# Helper: add permissions section if missing. Writes block to content file
# then inserts before last '}'.
# ---------------------------------------------------------------------------
add_permissions_section() {
  local file="$1"
  local content_file
  content_file="${CLAUDE_DIR}/tmpclaude_perm_content_$$"

  printf ',\n' > "$content_file"
  printf '  "permissions": {\n' >> "$content_file"
  printf '    "allow": [\n' >> "$content_file"
  local count=${#PCV_ALLOW_ENTRIES[@]}
  local i=0
  for entry in "${PCV_ALLOW_ENTRIES[@]}"; do
    i=$((i + 1))
    if [ $i -lt $count ]; then
      printf '      "%s",\n' "$entry" >> "$content_file"
    else
      printf '      "%s"\n' "$entry" >> "$content_file"
    fi
  done
  printf '    ]\n' >> "$content_file"
  printf '  }\n' >> "$content_file"

  insert_file_before_last_brace "$file" "$content_file"
  local rc=$?
  rm -f "$content_file"
  return $rc
}

# ---------------------------------------------------------------------------
# MAIN LOGIC
# ---------------------------------------------------------------------------

JQ_CMD="$(resolve_jq)"

if [ ! -f "${SETTINGS_FILE}" ]; then
  # ---- CREATE: file does not exist ----------------------------------------

  # Global-merge mode: create permissions-only file (no hooks) and exit.
  if [ -n "${MERGE_TO_GLOBAL}" ]; then
    mkdir -p "${CLAUDE_DIR}" 2>/dev/null
    if [ -n "$JQ_CMD" ]; then
      _jq_allow_json=$( printf '%s\n' "${PCV_ALLOW_ENTRIES[@]}" | "$JQ_CMD" -R . | "$JQ_CMD" -s . )
      "$JQ_CMD" -n --argjson allow "$_jq_allow_json" \
        '{ permissions: { allow: $allow } }' > "${SETTINGS_FILE}"
    else
      {
        printf '{\n'
        printf '  "permissions": {\n'
        printf '    "allow": [\n'
        _count=${#PCV_ALLOW_ENTRIES[@]}
        _i=0
        for entry in "${PCV_ALLOW_ENTRIES[@]}"; do
          _i=$((_i + 1))
          if [ $_i -lt $_count ]; then
            printf '      "%s",\n' "$entry"
          else
            printf '      "%s"\n' "$entry"
          fi
        done
        printf '    ]\n'
        printf '  }\n'
        printf '}\n'
      } > "${SETTINGS_FILE}"
    fi
    if [ $? -ne 0 ]; then
      printf 'scaffold-settings.sh: failed to write %s\n' "${SETTINGS_FILE}" >&2
      exit 1
    fi
    printf 'scaffold-settings.sh: created %s (global-merge, permissions-only)\n' "${SETTINGS_FILE}"
    exit 0
  fi

  if [ -n "$JQ_CMD" ]; then
    # jq fast path: build JSON from arrays and hook definitions
    _jq_allow_json=$( printf '%s\n' "${PCV_ALLOW_ENTRIES[@]}" | "$JQ_CMD" -R . | "$JQ_CMD" -s . )
    "$JQ_CMD" -n \
      --argjson allow "$_jq_allow_json" \
      --arg hook_session "$PCV_HOOK_SESSIONSTART" \
      --arg hook_stop "$PCV_HOOK_STOP" \
      --arg hook_compact "$PCV_HOOK_PRECOMPACT" \
      --arg hook_subagent "$PCV_HOOK_SUBAGENT_STOP" \
      --arg hook_posttool "$PCV_HOOK_POSTTOOLUSE" \
      --arg hook_posttool_matcher "$PCV_HOOK_POSTTOOLUSE_MATCHER" \
      '{
        permissions: { allow: $allow },
        hooks: {
          SessionStart: [{ hooks: [{ type: "command", command: $hook_session }] }],
          Stop: [{ hooks: [{ type: "command", command: $hook_stop }] }],
          PreCompact: [{ hooks: [{ type: "command", command: $hook_compact }] }],
          SubagentStop: [{ hooks: [{ type: "command", command: $hook_subagent }] }],
          PostToolUse: [{ matcher: $hook_posttool_matcher, hooks: [{ type: "command", command: $hook_posttool }] }]
        }
      }' > "${SETTINGS_FILE}"
    if [ $? -ne 0 ]; then
      printf 'scaffold-settings.sh: jq create failed; falling back to pure bash\n' >&2
      emit_full_settings > "${SETTINGS_FILE}"
    fi
  else
    # Pure bash fallback
    emit_full_settings > "${SETTINGS_FILE}"
  fi
  if [ $? -ne 0 ]; then
    printf 'scaffold-settings.sh: failed to write %s\n' "${SETTINGS_FILE}" >&2
    exit 1
  fi
  printf 'scaffold-settings.sh: created %s\n' "${SETTINGS_FILE}"
  exit 0
fi

# ---- MERGE: file exists -----------------------------------------------------

# Check for empty file
file_size="$(wc -c < "${SETTINGS_FILE}" 2>/dev/null | tr -d '[:space:]')"
if [ -z "$file_size" ] || [ "$file_size" -eq 0 ]; then
  printf 'scaffold-settings.sh: warning: empty settings.json found; overwriting\n' >&2
  emit_full_settings > "${SETTINGS_FILE}"
  if [ $? -ne 0 ]; then
    printf 'scaffold-settings.sh: failed to write %s\n' "${SETTINGS_FILE}" >&2
    exit 1
  fi
  printf 'scaffold-settings.sh: created %s (replaced empty file)\n' "${SETTINGS_FILE}"
  exit 0
fi

# Check basic JSON shape
if ! is_valid_json_shape "${SETTINGS_FILE}"; then
  printf 'scaffold-settings.sh: warning: malformed JSON in %s; overwriting\n' "${SETTINGS_FILE}" >&2
  emit_full_settings > "${SETTINGS_FILE}"
  if [ $? -ne 0 ]; then
    printf 'scaffold-settings.sh: failed to write %s\n' "${SETTINGS_FILE}" >&2
    exit 1
  fi
  printf 'scaffold-settings.sh: created %s (replaced malformed JSON)\n' "${SETTINGS_FILE}"
  exit 0
fi

# ---- Merge permissions.allow entries ----------------------------------------

if [ -n "$JQ_CMD" ] && [ -n "${MERGE_TO_GLOBAL}" ]; then
  # jq fast path (global-merge): permissions-only merge, no hooks.
  _jq_allow_json=$( printf '%s\n' "${PCV_ALLOW_ENTRIES[@]}" | "$JQ_CMD" -R . | "$JQ_CMD" -s . )
  _jq_tmpmerge="${CLAUDE_DIR}/tmpclaude_merge_$$"
  "$JQ_CMD" --argjson newAllow "$_jq_allow_json" '
    .permissions //= {} |
    .permissions.allow //= [] |
    .permissions.allow = (.permissions.allow + ($newAllow - .permissions.allow))
  ' "${SETTINGS_FILE}" > "$_jq_tmpmerge"
  if [ $? -eq 0 ]; then
    cp "$_jq_tmpmerge" "${SETTINGS_FILE}"
    rm -f "$_jq_tmpmerge"
    if ! is_valid_json_shape "${SETTINGS_FILE}"; then
      printf 'scaffold-settings.sh: error: post-merge validation failed (global)\n' >&2
      exit 1
    fi
    printf 'scaffold-settings.sh: merge complete (global, permissions-only): %s\n' "${SETTINGS_FILE}"
    exit 0
  fi
  rm -f "$_jq_tmpmerge"
  printf 'scaffold-settings.sh: jq global-merge failed; falling back to pure bash\n' >&2
fi

if [ -n "$JQ_CMD" ]; then
  # jq fast path: merge allow rules and hooks in one pass
  _jq_allow_json=$( printf '%s\n' "${PCV_ALLOW_ENTRIES[@]}" | "$JQ_CMD" -R . | "$JQ_CMD" -s . )
  _jq_tmpmerge="${CLAUDE_DIR}/tmpclaude_merge_$$"
  "$JQ_CMD" \
    --argjson newAllow "$_jq_allow_json" \
    --arg hook_session "$PCV_HOOK_SESSIONSTART" \
    --arg hook_stop "$PCV_HOOK_STOP" \
    --arg hook_compact "$PCV_HOOK_PRECOMPACT" \
    --arg hook_subagent "$PCV_HOOK_SUBAGENT_STOP" \
    --arg hook_posttool "$PCV_HOOK_POSTTOOLUSE" \
    --arg hook_posttool_matcher "$PCV_HOOK_POSTTOOLUSE_MATCHER" \
    '
    # Ensure permissions.allow exists and merge new entries
    .permissions //= {} |
    .permissions.allow //= [] |
    .permissions.allow = (.permissions.allow + ($newAllow - .permissions.allow)) |

    # Define desired hooks
    ( { SessionStart: [{ hooks: [{ type: "command", command: $hook_session }] }],
        Stop: [{ hooks: [{ type: "command", command: $hook_stop }] }],
        PreCompact: [{ hooks: [{ type: "command", command: $hook_compact }] }],
        SubagentStop: [{ hooks: [{ type: "command", command: $hook_subagent }] }],
        PostToolUse: [{ matcher: $hook_posttool_matcher, hooks: [{ type: "command", command: $hook_posttool }] }]
      } ) as $newHooks |

    # Ensure hooks object exists and merge each event
    .hooks //= {} |
    reduce ($newHooks | keys[]) as $evt (.;
      if (.hooks[$evt] | any(.hooks[]?.command == $newHooks[$evt][0].hooks[0].command))
      then .
      else .hooks[$evt] = ((.hooks[$evt] // []) + $newHooks[$evt])
      end
    )
    ' "${SETTINGS_FILE}" > "$_jq_tmpmerge"
  if [ $? -eq 0 ]; then
    cp "$_jq_tmpmerge" "${SETTINGS_FILE}"
    rm -f "$_jq_tmpmerge"
    if ! is_valid_json_shape "${SETTINGS_FILE}"; then
      printf 'scaffold-settings.sh: error: post-merge validation failed — output JSON appears malformed\n' >&2
      printf 'scaffold-settings.sh: file location: %s\n' "${SETTINGS_FILE}" >&2
      exit 1
    fi
    printf 'scaffold-settings.sh: merge complete: %s\n' "${SETTINGS_FILE}"
    exit 0
  fi
  # jq merge failed — fall through to pure bash
  rm -f "$_jq_tmpmerge"
  printf 'scaffold-settings.sh: jq merge failed; falling back to pure bash\n' >&2
fi

HAS_PERMISSIONS=false
grep -q '"permissions"' "${SETTINGS_FILE}" 2>/dev/null && HAS_PERMISSIONS=true

if [ "$HAS_PERMISSIONS" = false ]; then
  add_permissions_section "${SETTINGS_FILE}"
  if [ $? -ne 0 ]; then
    printf 'scaffold-settings.sh: failed to add permissions section\n' >&2
    exit 1
  fi
  printf 'scaffold-settings.sh: added permissions section\n'
else
  HAS_ALLOW=false
  grep -q '"allow"' "${SETTINGS_FILE}" 2>/dev/null && HAS_ALLOW=true

  if [ "$HAS_ALLOW" = true ]; then
    # Normalize compact inline allow array to multi-line before merging
    normalize_allow_array "${SETTINGS_FILE}"
    for entry in "${PCV_ALLOW_ENTRIES[@]}"; do
      if ! string_in_file "${SETTINGS_FILE}" "$entry"; then
        append_to_allow_array "${SETTINGS_FILE}" "$entry"
        if [ $? -ne 0 ]; then
          printf 'scaffold-settings.sh: failed to append allow entry: %s\n' "$entry" >&2
          exit 1
        fi
        printf 'scaffold-settings.sh: added allow entry: %s\n' "$entry"
      fi
    done
  else
    printf 'scaffold-settings.sh: warning: permissions section found but no allow array; adding all PCV entries\n' >&2
    for entry in "${PCV_ALLOW_ENTRIES[@]}"; do
      append_to_allow_array "${SETTINGS_FILE}" "$entry"
    done
  fi
fi

# ---- Merge hooks ------------------------------------------------------------
# Global-merge mode: skip hooks merge entirely (permissions-only file).
if [ -n "${MERGE_TO_GLOBAL}" ]; then
  if ! is_valid_json_shape "${SETTINGS_FILE}"; then
    printf 'scaffold-settings.sh: error: post-merge validation failed (global)\n' >&2
    exit 1
  fi
  printf 'scaffold-settings.sh: merge complete (global, permissions-only): %s\n' "${SETTINGS_FILE}"
  exit 0
fi

HAS_HOOKS=false
grep -q '"hooks"' "${SETTINGS_FILE}" 2>/dev/null && HAS_HOOKS=true

if [ "$HAS_HOOKS" = false ]; then
  add_hooks_section "${SETTINGS_FILE}"
  if [ $? -ne 0 ]; then
    printf 'scaffold-settings.sh: failed to add hooks section\n' >&2
    exit 1
  fi
  printf 'scaffold-settings.sh: added hooks section\n'
else
  declare -A HOOK_MAP
  HOOK_MAP["SessionStart"]="${PCV_HOOK_SESSIONSTART}"
  HOOK_MAP["Stop"]="${PCV_HOOK_STOP}"
  HOOK_MAP["PreCompact"]="${PCV_HOOK_PRECOMPACT}"
  HOOK_MAP["SubagentStop"]="${PCV_HOOK_SUBAGENT_STOP}"

  for event in SessionStart Stop PreCompact SubagentStop; do
    cmd="${HOOK_MAP[$event]}"
    if ! string_in_file "${SETTINGS_FILE}" "$cmd"; then
      add_hook_event "${SETTINGS_FILE}" "$event" "$cmd"
      if [ $? -ne 0 ]; then
        printf 'scaffold-settings.sh: failed to add hook event: %s\n' "$event" >&2
        exit 1
      fi
      printf 'scaffold-settings.sh: added hook event: %s\n' "$event"
    fi
  done

  # PostToolUse has a matcher field — handle separately
  if ! string_in_file "${SETTINGS_FILE}" "${PCV_HOOK_POSTTOOLUSE}"; then
    add_hook_event_with_matcher "${SETTINGS_FILE}" 'PostToolUse' "${PCV_HOOK_POSTTOOLUSE}" "${PCV_HOOK_POSTTOOLUSE_MATCHER}"
    if [ $? -ne 0 ]; then
      printf 'scaffold-settings.sh: failed to add hook event: PostToolUse\n' >&2
      exit 1
    fi
    printf 'scaffold-settings.sh: added hook event: PostToolUse\n'
  fi
fi

# ---- Final validation -------------------------------------------------------
if ! is_valid_json_shape "${SETTINGS_FILE}"; then
  printf 'scaffold-settings.sh: error: post-merge validation failed — output JSON appears malformed\n' >&2
  printf 'scaffold-settings.sh: file location: %s\n' "${SETTINGS_FILE}" >&2
  exit 1
fi

printf 'scaffold-settings.sh: merge complete: %s\n' "${SETTINGS_FILE}"
exit 0
