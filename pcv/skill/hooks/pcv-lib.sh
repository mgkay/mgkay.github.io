#!/usr/bin/env bash
# pcv-lib.sh — PCV v3.11 Phase 5
#
# Shared helper functions for PCV hook scripts. Source this file near the
# top of any hook that needs JSON-shape validation, string searching, or
# settings.json allow-array manipulation.
#
# Usage:
#   source "$(dirname "$0")/pcv-lib.sh"

# Guard against double-sourcing
[[ -n "${_PCV_LIB_LOADED:-}" ]] && return 0
_PCV_LIB_LOADED=1

# ---------------------------------------------------------------------------
# Helper: basic JSON structure check — verify file starts with '{' and ends
# with '}' (after stripping whitespace). Not a full parser; catches empty
# files and obviously malformed content.
# ---------------------------------------------------------------------------
is_valid_json_shape() {
  local file="$1"
  local first_char last_nonws
  first_char="$(head -c 1 "$file" 2>/dev/null | tr -d '[:space:]')"
  # Read last 4 bytes and strip all whitespace to find final non-ws char
  last_nonws="$(tail -c 4 "$file" 2>/dev/null | tr -d '[:space:]\n\r')"
  last_nonws="${last_nonws: -1}"
  if [ "$first_char" = "{" ] && [ "$last_nonws" = "}" ]; then
    return 0
  fi
  return 1
}

# ---------------------------------------------------------------------------
# Helper: check if a literal string value is already quoted in the file.
# Escapes regex metacharacters before grepping.
# ---------------------------------------------------------------------------
string_in_file() {
  local file="$1"
  local value="$2"
  local escaped
  # Escape BRE metacharacters: . * [ ^ $ \
  # In BRE, ( ) are literal, so no escaping needed for them.
  escaped="$(printf '%s' "$value" \
    | sed 's/\\/\\\\/g' \
    | sed 's/\./\\./g' \
    | sed 's/\*/\\*/g' \
    | sed 's/\[/\\[/g' \
    | sed 's/\^/\\^/g' \
    | sed 's/\$/\\$/g')"
  grep -q "\"${escaped}\"" "$file" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Helper: normalize the allow array in the file to multi-line format.
# Detects lines where "allow" key and its array content appear on a single
# line (compact format) and expands them to one entry per line.
# This ensures append_to_allow_array can find the closing ']' on its own line.
# ---------------------------------------------------------------------------
normalize_allow_array() {
  local file="$1"
  local tmpfile
  tmpfile="$(dirname "$file")/tmpclaude_norm_$$"

  awk '
    {
      # Detect compact allow array: "allow": ["a", "b"] all on one line
      # Pattern: line contains "allow" and both [ and ] on the same line
      if (/"allow"[[:space:]]*:/ && /\[/ && /\]/) {
        # Extract the part after the opening [
        line = $0
        # Find indent prefix
        prefix = ""
        n = split(line, chars, "")
        for (i = 1; i <= n; i++) {
          if (chars[i] == " " || chars[i] == "\t") prefix = prefix chars[i]
          else break
        }
        # Split on [ to get array content
        bracket_pos = index(line, "[")
        close_pos = index(line, "]")
        inner = substr(line, bracket_pos + 1, close_pos - bracket_pos - 1)
        # Print the key line with just opening bracket
        key_part = substr(line, 1, bracket_pos)
        print key_part
        # Split on "," delimiter between quoted entries (not commas inside values)
        # Walk character-by-character, tracking quote depth
        n_items = 0
        in_quotes = 0
        paren_depth = 0
        current = ""
        len = length(inner)
        for (ci = 1; ci <= len; ci++) {
          ch = substr(inner, ci, 1)
          if (ch == "\"" && (ci == 1 || substr(inner, ci-1, 1) != "\\")) {
            in_quotes = !in_quotes
            current = current ch
          } else if (!in_quotes && ch == "(") {
            paren_depth++
            current = current ch
          } else if (!in_quotes && ch == ")") {
            paren_depth--
            current = current ch
          } else if (!in_quotes && paren_depth == 0 && ch == ",") {
            n_items++
            items[n_items] = current
            current = ""
          } else {
            current = current ch
          }
        }
        if (current != "") {
          n_items++
          items[n_items] = current
        }
        for (i = 1; i <= n_items; i++) {
          item = items[i]
          gsub(/^[[:space:]]+|[[:space:]]+$/, "", item)
          if (item != "") {
            if (i < n_items) {
              print "      " item ","
            } else {
              print "      " item
            }
          }
        }
        # Print closing bracket at same indent level as the "allow" key
        print prefix "]" substr(line, close_pos + 1)
        next
      }
      print $0
    }
  ' "$file" > "$tmpfile"

  if [ $? -ne 0 ]; then
    rm -f "$tmpfile"
    return 1
  fi
  cp "$tmpfile" "$file"
  rm -f "$tmpfile"
}

# ---------------------------------------------------------------------------
# Helper: append a new allow entry to the allow array in the target file.
# Finds the closing ']' of the allow array and inserts a new entry before it,
# adding a trailing comma to the previous last entry.
#
# Arguments:
#   $1  target file
#   $2  entry string (unquoted, e.g. Read(**))
# ---------------------------------------------------------------------------
append_to_allow_array() {
  local file="$1"
  local entry="$2"
  local tmpfile
  tmpfile="$(dirname "$file")/tmpclaude_allow_$$"

  # awk: track when we enter the allow array, buffer lines, on ']' emit
  # buffered content with trailing comma added to last item, then new entry.
  awk -v new_entry="$entry" '
    BEGIN {
      in_allow = 0
      done = 0
      buf_count = 0
    }
    {
      if (!done && !in_allow && /"allow"[[:space:]]*:/) {
        in_allow = 1
        print $0
        next
      }
      if (!done && in_allow) {
        if (/^[[:space:]]*\]/) {
          # Flush buffer: add trailing comma to last non-empty entry line,
          # then emit the new entry, then the closing bracket.
          done = 1
          in_allow = 0
          # Find last non-empty buffer line
          last_idx = 0
          for (k = 1; k <= buf_count; k++) {
            if (buf[k] ~ /[^[:space:]]/) last_idx = k
          }
          for (k = 1; k <= buf_count; k++) {
            if (k == last_idx) {
              # Add comma if not already present
              line = buf[k]
              if (line !~ /,[[:space:]]*$/) {
                sub(/[[:space:]]*$/, ",", line)
              }
              print line
            } else {
              print buf[k]
            }
          }
          printf "      \"%s\"\n", new_entry
          print $0
          next
        }
        buf[++buf_count] = $0
        next
      }
      print $0
    }
  ' "$file" > "$tmpfile"

  if [ $? -ne 0 ]; then
    rm -f "$tmpfile"
    return 1
  fi
  cp "$tmpfile" "$file"
  rm -f "$tmpfile"
}

# ---------------------------------------------------------------------------
# Helper: resolve jq binary location, with on-demand provisioning.
#
# Resolution order:
#   1. System PATH (command -v jq)
#   2. PCV bin directory (~/.claude/skills/pcv/bin/jq)
#   3. Download from GitHub releases to PCV bin (one-time)
#   4. Return empty string (caller falls back to pure bash)
#
# Prints the jq path on success, empty string on failure.
# ---------------------------------------------------------------------------
resolve_jq() {
  # 1. System PATH
  if command -v jq >/dev/null 2>&1; then
    echo "jq"
    return 0
  fi

  # 2. PCV bin
  local pcv_bin="$HOME/.claude/skills/pcv/bin"
  local pcv_jq="$pcv_bin/jq"
  # On Windows/MSYS, check for .exe variant
  if [ -x "$pcv_jq" ]; then
    echo "$pcv_jq"
    return 0
  fi
  if [ -x "${pcv_jq}.exe" ]; then
    echo "${pcv_jq}.exe"
    return 0
  fi

  # 3. Download from GitHub releases
  local os arch asset_name download_url
  os="$(uname -s 2>/dev/null)"
  arch="$(uname -m 2>/dev/null)"

  case "$os" in
    Linux)
      case "$arch" in
        x86_64|amd64) asset_name="jq-linux-amd64" ;;
        aarch64|arm64) asset_name="jq-linux-arm64" ;;
        *) echo ""; return 1 ;;
      esac
      ;;
    Darwin)
      case "$arch" in
        x86_64|amd64) asset_name="jq-macos-amd64" ;;
        arm64|aarch64) asset_name="jq-macos-arm64" ;;
        *) echo ""; return 1 ;;
      esac
      ;;
    MINGW*|MSYS*|CYGWIN*)
      asset_name="jq-windows-amd64.exe"
      pcv_jq="${pcv_jq}.exe"
      ;;
    *)
      echo ""; return 1
      ;;
  esac

  download_url="https://github.com/jqlang/jq/releases/latest/download/${asset_name}"

  # Create bin directory if needed
  mkdir -p "$pcv_bin" 2>/dev/null

  # Try curl first, then wget
  local dl_rc=1
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$pcv_jq" "$download_url" 2>/dev/null
    dl_rc=$?
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$pcv_jq" "$download_url" 2>/dev/null
    dl_rc=$?
  fi

  if [ $dl_rc -ne 0 ] || [ ! -f "$pcv_jq" ]; then
    rm -f "$pcv_jq" 2>/dev/null
    echo ""; return 1
  fi

  chmod +x "$pcv_jq" 2>/dev/null
  echo "$pcv_jq"
  return 0
}
