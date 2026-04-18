#!/usr/bin/env bash
# lib.sh — PCV v3.14 shared handler library
#
# Sourced by each per-gate handler (M1–M8) and by the hub for judgment-gate
# emission. Not intended for standalone execution.
#
# Usage:
#   source "$(dirname "$0")/lib.sh"

# Guard against double-sourcing
[[ -n "${_PCV_HANDLERS_LIB_LOADED:-}" ]] && return 0
_PCV_HANDLERS_LIB_LOADED=1

# ---------------------------------------------------------------------------
# read_session_state <project_dir>
# Echo KEY=VALUE pairs for: test_mode, test_responses_path, plan_tier,
# agent_config, project_type. Missing file → deterministic defaults (E2).
# Exit 0 always.
# ---------------------------------------------------------------------------
read_session_state() {
  local project_dir="$1"
  local sf="${project_dir}/pcvplans/logs/session-state.json"

  # Defaults (E2 resolution)
  local test_mode="false"
  local test_responses_path=""
  local plan_tier="unknown"
  local agent_config="v3.7-defaults"
  local project_type="unknown"

  if [ -f "${sf}" ]; then
    local raw val

    # test_mode: boolean (true/false, no quotes)
    raw="$(grep -o '"test_mode"[[:space:]]*:[[:space:]]*[a-zA-Z]\{4,5\}' "${sf}" | head -n 1)"
    if [ -n "${raw}" ]; then
      val="$(printf '%s' "${raw}" | sed 's/.*:[[:space:]]*//')"
      if [ "${val}" = "true" ] || [ "${val}" = "false" ]; then
        test_mode="${val}"
      fi
    fi

    # String fields: "key": "value"
    raw="$(grep -o '"test_responses_path"[[:space:]]*:[[:space:]]*"[^"]*"' "${sf}" | head -n 1)"
    if [ -n "${raw}" ]; then
      val="$(printf '%s' "${raw}" | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/')"
      test_responses_path="${val}"
    fi

    raw="$(grep -o '"plan_tier"[[:space:]]*:[[:space:]]*"[^"]*"' "${sf}" | head -n 1)"
    if [ -n "${raw}" ]; then
      val="$(printf '%s' "${raw}" | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/')"
      plan_tier="${val}"
    fi

    raw="$(grep -o '"agent_config"[[:space:]]*:[[:space:]]*"[^"]*"' "${sf}" | head -n 1)"
    if [ -n "${raw}" ]; then
      val="$(printf '%s' "${raw}" | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/')"
      agent_config="${val}"
    fi

    raw="$(grep -o '"project_type"[[:space:]]*:[[:space:]]*"[^"]*"' "${sf}" | head -n 1)"
    if [ -n "${raw}" ]; then
      val="$(printf '%s' "${raw}" | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/')"
      project_type="${val}"
    fi
  fi

  printf 'test_mode=%s\n' "${test_mode}"
  printf 'test_responses_path=%s\n' "${test_responses_path}"
  printf 'plan_tier=%s\n' "${plan_tier}"
  printf 'agent_config=%s\n' "${agent_config}"
  printf 'project_type=%s\n' "${project_type}"
  return 0
}

# ---------------------------------------------------------------------------
# _pcv_json_escape <string>
# Escape a string for use inside a JSON double-quoted value:
# backslash, double-quote, newline, carriage return, tab.
# Prints the escaped form to stdout (no surrounding quotes).
# ---------------------------------------------------------------------------
_pcv_json_escape() {
  local s="$1"
  # Order matters: escape backslashes first.
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  printf '%s' "${s}"
}

# ---------------------------------------------------------------------------
# _pcv_build_options_array <csv>
# Convert a comma-separated option list into a JSON array of strings.
# Empty input → "[]".
# ---------------------------------------------------------------------------
_pcv_build_options_array() {
  local csv="$1"
  if [ -z "${csv}" ]; then
    printf '[]'
    return 0
  fi
  local out="["
  local first=1
  local item escaped
  # Use 'read' with IFS=',' to split.
  local OLD_IFS="${IFS}"
  IFS=','
  # shellcheck disable=SC2206
  local arr=(${csv})
  IFS="${OLD_IFS}"
  local i
  for i in "${arr[@]}"; do
    # Strip leading/trailing whitespace
    item="$(printf '%s' "${i}" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    escaped="$(_pcv_json_escape "${item}")"
    if [ "${first}" -eq 1 ]; then
      out="${out}\"${escaped}\""
      first=0
    else
      out="${out},\"${escaped}\""
    fi
  done
  out="${out}]"
  printf '%s' "${out}"
}

# ---------------------------------------------------------------------------
# emit_gate_context <project_dir> <gate_id> <gate_type> <question>
#                   <options_csv> <handler_script> <decision_context>
#                   <expected_response_format>
# Write pcvplans/logs/gate-context.json (overwrites). Extended schema (Q6):
# 8 fields. Empty options_csv → []; empty handler_script → null.
# Exit 0 on success, 1 on I/O failure.
# ---------------------------------------------------------------------------
emit_gate_context() {
  local project_dir="$1"
  local gate_id="$2"
  local gate_type="$3"
  local question="$4"
  local options_csv="$5"
  local handler_script="$6"
  local decision_context="$7"
  local expected_response_format="$8"

  local logs_dir="${project_dir}/pcvplans/logs"
  local out="${logs_dir}/gate-context.json"

  # Ensure logs dir exists (handlers may be invoked before scaffold runs).
  mkdir -p "${logs_dir}" 2>/dev/null || return 1

  local ts
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)" || return 1

  local esc_gate_id esc_question esc_gate_type esc_handler esc_decision esc_format
  esc_gate_id="$(_pcv_json_escape "${gate_id}")"
  esc_question="$(_pcv_json_escape "${question}")"
  esc_gate_type="$(_pcv_json_escape "${gate_type}")"
  esc_decision="$(_pcv_json_escape "${decision_context}")"
  esc_format="$(_pcv_json_escape "${expected_response_format}")"

  local options_json
  options_json="$(_pcv_build_options_array "${options_csv}")"

  local handler_json
  if [ -z "${handler_script}" ]; then
    handler_json="null"
  else
    esc_handler="$(_pcv_json_escape "${handler_script}")"
    handler_json="\"${esc_handler}\""
  fi

  local tmp="${out}.tmp.$$"
  {
    printf '{\n'
    printf '  "gate_id": "%s",\n' "${esc_gate_id}"
    printf '  "question": "%s",\n' "${esc_question}"
    printf '  "options": %s,\n' "${options_json}"
    printf '  "timestamp": "%s",\n' "${ts}"
    printf '  "gate_type": "%s",\n' "${esc_gate_type}"
    printf '  "handler_script": %s,\n' "${handler_json}"
    printf '  "decision_context": "%s",\n' "${esc_decision}"
    printf '  "expected_response_format": "%s"\n' "${esc_format}"
    printf '}\n'
  } > "${tmp}" 2>/dev/null || { rm -f "${tmp}" 2>/dev/null; return 1; }

  mv -f "${tmp}" "${out}" 2>/dev/null || { rm -f "${tmp}" 2>/dev/null; return 1; }
  return 0
}

# ---------------------------------------------------------------------------
# log_decision <project_dir> <entry_type> <body_markdown>
# Append canonical decision log entry to pcvplans/logs/decision-log.md.
# Prefix header with [TEST] when session-state test_mode=true.
# Exit 0 on success.
# ---------------------------------------------------------------------------
log_decision() {
  local project_dir="$1"
  local entry_type="$2"
  local body="$3"

  local logs_dir="${project_dir}/pcvplans/logs"
  local log_file="${logs_dir}/decision-log.md"

  mkdir -p "${logs_dir}" 2>/dev/null || return 1

  # Determine test-mode prefix by parsing session-state.
  local ss_line test_mode="false"
  while IFS= read -r ss_line; do
    case "${ss_line}" in
      test_mode=*) test_mode="${ss_line#test_mode=}" ;;
    esac
  done < <(read_session_state "${project_dir}")

  local prefix=""
  if [ "${test_mode}" = "true" ]; then
    prefix="[TEST] "
  fi

  local today
  today="$(date +%Y-%m-%d)" || return 1

  {
    printf '## %s%s — %s\n' "${prefix}" "${entry_type}" "${today}"
    printf '%s\n' "${body}"
    printf -- '---\n'
  } >> "${log_file}" 2>/dev/null || return 1

  return 0
}

# ---------------------------------------------------------------------------
# print_mechanical_footer
# Emit the canonical mechanical-gate footer text on stdout. No arguments.
# ---------------------------------------------------------------------------
print_mechanical_footer() {
  printf '%s\n' "This action was taken automatically based on project context. To override, edit pcvplans/logs/session-state.json or adjust PCV settings."
}

# ---------------------------------------------------------------------------
# v3.14: test-response lookup (shared by M6, M7)
#
# _pcv_test_response_lookup <responses_path> <key>
# Parse the test-responses JSON file for the given key and echo its string
# value on stdout.
#
# Schema: the responses file is a flat JSON object mapping keys (e.g. "Q1",
# "Q2-3", "E1") to string values. Parsing uses grep + sed (no jq dependency,
# consistent with read_session_state).
#
# Exit codes:
#   0  key present with non-empty value (value echoed to stdout)
#   1  key missing, value empty, or file unreadable (stdout empty)
#   2  file exists but cannot be read (distinct from missing key)
#
# No stderr output — caller is responsible for diagnostic messaging.
# ---------------------------------------------------------------------------
_pcv_test_response_lookup() {
  local path="$1"
  local key="$2"

  if [ -z "${path}" ] || [ ! -f "${path}" ]; then
    return 1
  fi

  if [ ! -r "${path}" ]; then
    return 2
  fi

  # Build a regex that matches the exact key. The key itself contains only
  # alphanumerics and hyphens per spec (Q<N>, Q<phase>-<N>, E<N>, E<phase>-<N>),
  # so no regex metacharacter escaping is required here.
  local raw val
  raw="$(grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "${path}" 2>/dev/null | head -n 1)"
  if [ -z "${raw}" ]; then
    return 1
  fi

  val="$(printf '%s' "${raw}" | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/')"

  # Unescape minimal JSON escapes used in canonical test fixtures: \", \\, \n.
  # (Schema assumes simple string values; richer escapes are out-of-scope.)
  val="${val//\\\"/\"}"
  val="${val//\\n/$'\n'}"
  val="${val//\\\\/\\}"

  if [ -z "${val}" ]; then
    return 1
  fi

  printf '%s' "${val}"
  return 0
}
