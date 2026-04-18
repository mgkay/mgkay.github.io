#!/usr/bin/env bash
# session-start-resume.sh — PCV v3.11 Phase 2 SessionStart routing injection
#
# Purpose:
#   On each SessionStart event, derive the full PCV project state from disk
#   and emit a pre-formatted display block via additionalContext. The block
#   includes a progress checklist (■/□ per milestone) and a ROUTING ACTION
#   line that tells the hub which protocol to load. This subsumes the Phase 1
#   one-line resume string — routing and resumption are unified in one output.
#
# Event:
#   SessionStart
#
# Expected payload fields (confirmed by C1 spike probe):
#   cwd              — working directory at session start (MSYS path on Windows)
#   hook_event_name  — "SessionStart"
#   model            — model name for the session
#   session_id       — unique session identifier
#   source           — session origin: "startup" | "resume" | "compact" (or similar)
#   transcript_path  — path to the session transcript file
#
# Project state detection (disk-based, in precedence order):
#   1. Lite         — pcvplans/lite-plan.md exists
#   2. Phase subfolder — parent dir has pcvplans/logs/master-log.md
#   3. Multi-phase root — pcvplans/logs/master-log.md exists AND ≥1 subdir has
#                         pcvplans/charge.md
#   4. Single-phase — pcvplans/charge.md exists in PROJECT_DIR
#   5. Not PCV      — none of the above (silent exit 0)
#
# Output (stdout):
#   Single hookSpecificOutput JSON envelope; additionalContext is a multi-line
#   pre-formatted display block with version header, checklist, and routing
#   action line. Valid JSON with \n escapes for newlines.
#
# Exit semantics:
#   Always exits 0. Non-PCV directories, opt-out marker, and all error paths
#   produce silent exit 0. A stderr log line is emitted on unexpected errors.
#   Partial JSON is never written to stdout.

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — BOOTSTRAP: stdin, project dir, PCV-detect, opt-out
# ════════════════════════════════════════════════════════════════════════════

# ── 1.1 Read stdin (event payload JSON; may be empty or absent) ─────────────

PAYLOAD=""
if [ ! -t 0 ]; then
  PAYLOAD="$(cat)"
fi

# ── 1.2 Resolve canonical project root ──────────────────────────────────────

if [ -n "${CLAUDE_PROJECT_DIR}" ]; then
  PROJECT_DIR="${CLAUDE_PROJECT_DIR}"
else
  PROJECT_DIR="${PWD}"
fi

LOGS_DIR="${PROJECT_DIR}/pcvplans/logs"

# ── 1.3 PCV-detect: if logs dir absent, not a PCV project — exit silently ───

if [ ! -d "${LOGS_DIR}" ]; then
  exit 0
fi

# ── 1.4 Opt-out check: honor .pcv-hooks-opted-out sentinel file ─────────────

if [ -f "${PROJECT_DIR}/.claude/.pcv-hooks-opted-out" ]; then
  # ── v3.14 opt-out + test-mode stderr warning ──
  # When opt-out marker is present AND PCV_AUTO_APPROVE=1 is set, the
  # session-state sentinel will NOT be written (because we early-exit
  # here). That silently degrades test mode to interactive. Warn so the
  # operator can detect and resolve the conflict. Warning-only; no error.
  if [ "${PCV_AUTO_APPROVE}" = "1" ]; then
    printf '%s\n' "PCV warning: hooks opted out AND PCV_AUTO_APPROVE=1 is set. Session-state sentinel will NOT be written; test mode may silently degrade to interactive. To enable test mode, remove .claude/.pcv-hooks-opted-out or set PCV_AUTO_APPROVE=0." >&2
  fi
  # ── end v3.14 opt-out + test-mode stderr warning ──
  exit 0
fi

# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — HELPERS: JSON sanitization, milestone checkers, name extraction
# ════════════════════════════════════════════════════════════════════════════

# Sanitize a string for embedding in a JSON string value.
# Escapes: backslash → \\, double-quote → \", newline → \n.
sanitize_json() {
  printf '%s' "$1" \
    | sed 's/\\/\\\\/g' \
    | sed 's/"/\\"/g' \
    | tr '\n' '|' \
    | sed 's/|/\\n/g'
}

# Extract project name from charge.md in a given directory.
# Usage: extract_project_name /path/to/dir
# Outputs the Project Name field value, or the directory basename as fallback.
extract_project_name() {
  local dir="$1"
  local name=""
  if [ -f "${dir}/pcvplans/charge.md" ]; then
    name="$(grep -m1 '^Project Name:' "${dir}/pcvplans/charge.md" | sed 's/^Project Name:[[:space:]]*//')"
  fi
  if [ -z "${name}" ] || printf '%s' "${name}" | grep -qi '<REPLACE>'; then
    name="$(basename "${dir}")"
  fi
  printf '%s' "${name}"
}

# Read PCV version from VERSION file.
# Outputs version string, or "unknown" if missing.
read_pcv_version() {
  local ver_file="${HOME}/.claude/skills/pcv/VERSION"
  if [ -f "${ver_file}" ]; then
    head -1 "${ver_file}"
  else
    printf 'unknown'
  fi
}

# Check if a decision log contains a given header pattern.
# Usage: log_has_marker /path/to/decision-log.md "^## Construction Complete"
# Returns 0 (true) or 1 (false).
log_has_marker() {
  local logfile="$1"
  local pattern="$2"
  [ -f "${logfile}" ] && grep -q "${pattern}" "${logfile}"
}

# Compute milestone marks for a standard 5-milestone single-phase checklist.
# Usage: compute_phase_milestones /path/to/phase-dir
# Sets global variables: M_CHARGE M_MAKE M_CONST M_BUILD M_VERIFY
# and milestone summary ROUTE_STATE: "planning"|"make_done"|"const_done"|
# "building"|"verifying"|"complete"
compute_phase_milestones() {
  local dir="$1"
  local logfile="${dir}/pcvplans/logs/decision-log.md"

  # Charge validated: pcvplans/charge.md exists with non-placeholder Project Name
  local raw_name=""
  if [ -f "${dir}/pcvplans/charge.md" ]; then
    raw_name="$(grep -m1 '^Project Name:' "${dir}/pcvplans/charge.md" | sed 's/^Project Name:[[:space:]]*//')"
    if [ -n "${raw_name}" ] && ! printf '%s' "${raw_name}" | grep -qi '<REPLACE>'; then
      M_CHARGE="■"
    else
      M_CHARGE="□"
    fi
  else
    M_CHARGE="□"
  fi

  # MakePlan approved: pcvplans/make-plan.md exists
  if [ -f "${dir}/pcvplans/make-plan.md" ]; then
    M_MAKE="■"
  else
    M_MAKE="□"
  fi

  # ConstructionPlan approved: pcvplans/construction-plan.md exists
  if [ -f "${dir}/pcvplans/construction-plan.md" ]; then
    M_CONST="■"
  else
    M_CONST="□"
  fi

  # Construction complete: decision log has ^## Construction Complete
  if log_has_marker "${logfile}" "^## Construction Complete"; then
    M_BUILD="■"
  else
    M_BUILD="□"
  fi

  # Verification complete: decision log has ^## Project Closeout or ^## Phase Complete
  if log_has_marker "${logfile}" "^## Project Closeout\|^## Phase Complete"; then
    M_VERIFY="■"
  else
    M_VERIFY="□"
  fi

  # Derive route state from milestone marks
  if [ "${M_VERIFY}" = "■" ]; then
    ROUTE_STATE="complete"
  elif [ "${M_BUILD}" = "■" ]; then
    ROUTE_STATE="verifying"
  elif [ "${M_CONST}" = "■" ]; then
    ROUTE_STATE="building"
  elif [ "${M_MAKE}" = "■" ]; then
    ROUTE_STATE="make_done"
  elif [ "${M_CHARGE}" = "■" ]; then
    ROUTE_STATE="planning"
  else
    ROUTE_STATE="charging"
  fi
}

# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PROJECT TYPE DETECTION (disk-based, precedence order)
# ════════════════════════════════════════════════════════════════════════════

PCV_VERSION="$(read_pcv_version)"
PROJECT_TYPE=""   # lite | phase_sub | multi_root | single | none
DISPLAY_BLOCK=""  # accumulates the pre-formatted output

# ── 3.1 Lite detection ───────────────────────────────────────────────────────

if [ -f "${PROJECT_DIR}/pcvplans/lite-plan.md" ]; then
  PROJECT_TYPE="lite"
fi

# ── 3.2 Phase subfolder detection (only if not Lite) ────────────────────────

if [ -z "${PROJECT_TYPE}" ]; then
  PARENT_DIR="$(dirname "${PROJECT_DIR}")"
  if [ -f "${PARENT_DIR}/pcvplans/logs/master-log.md" ]; then
    PROJECT_TYPE="phase_sub"
  fi
fi

# ── 3.3 Multi-phase root detection (only if not Lite or phase subfolder) ────

if [ -z "${PROJECT_TYPE}" ]; then
  if [ -f "${PROJECT_DIR}/pcvplans/logs/master-log.md" ]; then
    # Verify at least one subdir has pcvplans/charge.md
    for subdir in "${PROJECT_DIR}"/*/; do
      if [ -d "${subdir}" ] && [ -f "${subdir}pcvplans/charge.md" ] && [ -d "${subdir}pcvplans" ]; then
        PROJECT_TYPE="multi_root"
        break
      fi
    done
  fi
fi

# ── 3.4 Single-phase detection (fallback if charge.md exists) ───────────────

if [ -z "${PROJECT_TYPE}" ]; then
  if [ -f "${PROJECT_DIR}/pcvplans/charge.md" ]; then
    PROJECT_TYPE="single"
  fi
fi

# ── 3.5 Not a PCV project — exit silently ───────────────────────────────────

if [ -z "${PROJECT_TYPE}" ]; then
  exit 0
fi

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — ROUTING COMPUTATION AND DISPLAY BLOCK GENERATION
# ════════════════════════════════════════════════════════════════════════════

ROUTING_ACTION=""

# ── 4.1 Lite project ─────────────────────────────────────────────────────────

if [ "${PROJECT_TYPE}" = "lite" ]; then
  PROJ_NAME="$(extract_project_name "${PROJECT_DIR}")"
  LOGFILE="${PROJECT_DIR}/pcvplans/logs/decision-log.md"

  # Warn if both lite-plan.md and make-plan.md exist
  DUAL_PLAN_WARN=""
  if [ -f "${PROJECT_DIR}/pcvplans/make-plan.md" ]; then
    DUAL_PLAN_WARN="WARNING: Both lite-plan.md and make-plan.md found — routing as Lite project. Delete lite-plan.md if you intend to use full PCV."
  fi

  # Charge validated
  raw_name="$(grep -m1 '^Project Name:' "${PROJECT_DIR}/pcvplans/charge.md" 2>/dev/null | sed 's/^Project Name:[[:space:]]*//')"
  if [ -n "${raw_name}" ] && ! printf '%s' "${raw_name}" | grep -qi '<REPLACE>'; then
    L_CHARGE="■"
  else
    L_CHARGE="□"
  fi

  # Lite Plan approved (file already confirmed to exist)
  L_LITE="■"

  # Verification complete
  if log_has_marker "${LOGFILE}" "^## Project Closeout\|^## Phase Complete"; then
    L_VERIFY="■"
  else
    L_VERIFY="□"
  fi

  # Routing action
  if [ "${L_VERIFY}" = "■" ]; then
    ROUTING_ACTION="Completed Lite project. Offer version chain (§3a) or reopen (§3b)."
  else
    ROUTING_ACTION="Load construction-protocol.md (Lite path) and follow it."
  fi

  # Build display block
  DISPLAY_BLOCK="PCV v${PCV_VERSION} — ${PROJ_NAME} (Lite)"
  if [ -n "${DUAL_PLAN_WARN}" ]; then
    DISPLAY_BLOCK="${DISPLAY_BLOCK}
${DUAL_PLAN_WARN}"
  fi
  DISPLAY_BLOCK="${DISPLAY_BLOCK}
  ${L_CHARGE} Charge validated
  ${L_LITE} Lite Plan approved
  ${L_VERIFY} Verification complete

ROUTING ACTION: ${ROUTING_ACTION}"

fi  # end Lite

# ── 4.2 Phase subfolder ───────────────────────────────────────────────────────

if [ "${PROJECT_TYPE}" = "phase_sub" ]; then
  PROJ_NAME="$(extract_project_name "${PROJECT_DIR}")"
  compute_phase_milestones "${PROJECT_DIR}"

  # Routing action table (phase subfolder variant — complete routes to transition protocol)
  case "${ROUTE_STATE}" in
    charging)
      ROUTING_ACTION="Load planning-protocol.md and follow it (begin scaffold via Step B)." ;;
    planning)
      ROUTING_ACTION="Load planning-protocol.md and follow it." ;;
    make_done)
      ROUTING_ACTION="Partially planned. Ambiguous resume state — ask the user whether they are resuming planning or proceeding to construction." ;;
    building)
      ROUTING_ACTION="Load construction-protocol.md and follow it." ;;
    verifying)
      ROUTING_ACTION="Load verification-protocol.md and follow it." ;;
    complete)
      ROUTING_ACTION="Completed phase. Load phase-transition-protocol.md and follow it (resume at Step 3 — review tentative phase plan and direction decision)." ;;
    *)
      ROUTING_ACTION="Load planning-protocol.md and follow it." ;;
  esac

  DISPLAY_BLOCK="PCV v${PCV_VERSION} — ${PROJ_NAME}
  ${M_CHARGE} Charge validated
  ${M_MAKE} MakePlan approved
  ${M_CONST} ConstructionPlan approved
  ${M_BUILD} Construction
  ${M_VERIFY} Verification complete

(This phase is part of a multi-phase project. Use /pcv from the project root to see all phases.)

ROUTING ACTION: ${ROUTING_ACTION}"

fi  # end phase_sub

# ── 4.3 Multi-phase root ─────────────────────────────────────────────────────

if [ "${PROJECT_TYPE}" = "multi_root" ]; then
  PROJ_NAME="$(extract_project_name "${PROJECT_DIR}")"

  # Collect phase subdirs in lexical order
  PHASE_DIRS=""
  for subdir in "${PROJECT_DIR}"/*/; do
    if [ -d "${subdir}" ] && [ -f "${subdir}pcvplans/charge.md" ] && [ -d "${subdir}pcvplans" ]; then
      PHASE_DIRS="${PHASE_DIRS}${subdir}
"
    fi
  done

  # Also collect tentative subdirs (pcvplans/ directory exists but no charge.md)
  TENTATIVE_DIRS=""
  for subdir in "${PROJECT_DIR}"/*/; do
    if [ -d "${subdir}" ] && [ ! -f "${subdir}pcvplans/charge.md" ] && [ -d "${subdir}pcvplans" ]; then
      TENTATIVE_DIRS="${TENTATIVE_DIRS}${subdir}
"
    fi
  done

  ACTIVE_PHASE_DIR=""
  ACTIVE_PHASE_PROTOCOL=""
  PHASE_INDEX=0
  PHASE_BLOCKS=""

  # Process confirmed (non-tentative) phases in lexical order
  while IFS= read -r pdir; do
    [ -z "${pdir}" ] && continue
    PHASE_INDEX=$((PHASE_INDEX + 1))
    pname="$(extract_project_name "${pdir}")"

    compute_phase_milestones "${pdir}"

    # Track active phase: earliest whose verification is not complete
    if [ -z "${ACTIVE_PHASE_DIR}" ] && [ "${M_VERIFY}" != "■" ]; then
      ACTIVE_PHASE_DIR="${pdir}"
      ACTIVE_PHASE_PROTOCOL="${ROUTE_STATE}"
    fi

    PHASE_BLOCKS="${PHASE_BLOCKS}
Phase ${PHASE_INDEX}: ${pname}
  ${M_CHARGE} Charge validated
  ${M_MAKE} MakePlan approved
  ${M_CONST} ConstructionPlan approved
  ${M_BUILD} Construction
  ${M_VERIFY} Verification complete"
  done <<EOF
$(printf '%s' "${PHASE_DIRS}" | sort)
EOF

  # Append tentative phases
  while IFS= read -r pdir; do
    [ -z "${pdir}" ] && continue
    PHASE_INDEX=$((PHASE_INDEX + 1))
    pname="$(basename "${pdir%/}")"
    PHASE_BLOCKS="${PHASE_BLOCKS}
Phase ${PHASE_INDEX}: ${pname} (tentative)"
  done <<EOF
$(printf '%s' "${TENTATIVE_DIRS}" | sort)
EOF

  # Check for completed phases missing master-log Phase Complete entries.
  # This catches the case where a session ended after verification closeout
  # but before the phase-transition protocol could write the master-log entry.
  MASTER_LOG="${PROJECT_DIR}/pcvplans/logs/master-log.md"
  CATCHUP_PHASES=""
  CATCHUP_INDEX=0
  while IFS= read -r pdir; do
    [ -z "${pdir}" ] && continue
    CATCHUP_INDEX=$((CATCHUP_INDEX + 1))
    compute_phase_milestones "${pdir}"
    if [ "${M_VERIFY}" = "■" ] && [ -f "${MASTER_LOG}" ]; then
      if ! grep -q "Phase ${CATCHUP_INDEX} Complete" "${MASTER_LOG}" 2>/dev/null; then
        pbasename="$(basename "${pdir%/}")"
        CATCHUP_PHASES="${CATCHUP_PHASES}Phase ${CATCHUP_INDEX} (${pbasename}), "
      fi
    fi
  done <<EOF
$(printf '%s' "${PHASE_DIRS}" | sort)
EOF

  # Determine routing action for the active phase
  if [ -z "${ACTIVE_PHASE_DIR}" ]; then
    # All phases complete
    ROUTING_ACTION="All phases complete. Offer version chain (§3a) or reopen (§3b)."
  else
    ACTIVE_PHASE_BASENAME="$(basename "${ACTIVE_PHASE_DIR%/}")"
    case "${ACTIVE_PHASE_PROTOCOL}" in
      charging)
        ACTIVE_PROTO="planning-protocol.md" ;;
      planning)
        ACTIVE_PROTO="planning-protocol.md" ;;
      make_done)
        ACTIVE_PROTO="planning-protocol.md (confirm planning vs construction with user)" ;;
      building)
        ACTIVE_PROTO="construction-protocol.md" ;;
      verifying)
        ACTIVE_PROTO="verification-protocol.md" ;;
      complete)
        ACTIVE_PROTO="phase-transition-protocol.md" ;;
      *)
        ACTIVE_PROTO="planning-protocol.md" ;;
    esac
    ROUTING_ACTION="Navigate to ${ACTIVE_PHASE_BASENAME}/ and resume there (earliest incomplete phase). Load ${ACTIVE_PROTO} and follow it."
  fi

  # Prepend catch-up instruction if completed phases are missing master-log entries
  if [ -n "${CATCHUP_PHASES}" ]; then
    CATCHUP_PHASES="${CATCHUP_PHASES%, }"  # trim trailing comma
    ROUTING_ACTION="FIRST: Write missing Phase Complete entries to master-log (pcvplans/logs/master-log.md) for: ${CATCHUP_PHASES}. Use the template from phase-transition-protocol.md Step 2. THEN: ${ROUTING_ACTION}"
  fi

  DISPLAY_BLOCK="PCV v${PCV_VERSION} — ${PROJ_NAME} (Multi-Phase)
${PHASE_BLOCKS}

ROUTING ACTION: ${ROUTING_ACTION}"

fi  # end multi_root

# ── 4.4 Single-phase ─────────────────────────────────────────────────────────

if [ "${PROJECT_TYPE}" = "single" ]; then
  PROJ_NAME="$(extract_project_name "${PROJECT_DIR}")"
  compute_phase_milestones "${PROJECT_DIR}"

  # Routing action table
  case "${ROUTE_STATE}" in
    charging)
      ROUTING_ACTION="Load planning-protocol.md and follow it (begin scaffold via Step B)." ;;
    planning)
      ROUTING_ACTION="Load planning-protocol.md and follow it." ;;
    make_done)
      ROUTING_ACTION="Partially planned. Ambiguous resume state — ask the user whether they are resuming planning or proceeding to construction." ;;
    building)
      ROUTING_ACTION="Load construction-protocol.md and follow it." ;;
    verifying)
      ROUTING_ACTION="Load verification-protocol.md and follow it." ;;
    complete)
      ROUTING_ACTION="Completed project. Offer version chain (§3a) or reopen (§3b)." ;;
    *)
      ROUTING_ACTION="Load planning-protocol.md and follow it." ;;
  esac

  DISPLAY_BLOCK="PCV v${PCV_VERSION} — ${PROJ_NAME}
  ${M_CHARGE} Charge validated
  ${M_MAKE} MakePlan approved
  ${M_CONST} ConstructionPlan approved
  ${M_BUILD} Construction
  ${M_VERIFY} Verification complete

ROUTING ACTION: ${ROUTING_ACTION}"

fi  # end single

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4.5 — v3.14 SESSION-STATE SENTINEL WRITE
# ────────────────────────────────────────────────────────────────────────────
# Writes pcvplans/logs/session-state.json with derived project context so that
# per-gate handlers (M1–M8) and lib.sh:read_session_state can make deterministic
# decisions without re-scanning the environment or disk at every handler call.
# Additive to existing behavior. Atomic (temp file + mv). Cross-platform:
# no jq, no Python — pure bash + POSIX grep/sed/date/mkdir/printf.
# Skipped when PROJECT_TYPE=none (not a PCV project — already early-exited
# above) and when the opt-out marker is present (early-exited in Section 1.4).
# ════════════════════════════════════════════════════════════════════════════

# ── 4.5.1 JSON string escape helper (local, no external deps) ───────────────
# Escapes backslash, double-quote, newline, carriage return, tab for safe
# embedding inside a JSON double-quoted string. Writes escaped form to stdout.
_pcv_ss_json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  printf '%s' "${s}"
}

# ── 4.5.2 Derive sentinel fields ────────────────────────────────────────────

# test_mode: true iff PCV_AUTO_APPROVE=1 in env, else false (per spec)
if [ "${PCV_AUTO_APPROVE}" = "1" ]; then
  SS_TEST_MODE="true"
else
  SS_TEST_MODE="false"
fi

# test_responses_path: value of PCV_TEST_RESPONSES env var, empty if unset
SS_TEST_RESPONSES_PATH="${PCV_TEST_RESPONSES:-}"

# plan_tier: from ~/.claude/pcv-config.json key "plan_tier"; missing → "unknown"
SS_PLAN_TIER="unknown"
PCV_CONFIG_FILE="${HOME}/.claude/pcv-config.json"
if [ -f "${PCV_CONFIG_FILE}" ]; then
  # Grep for "plan_tier": "<value>" (permissive whitespace); sed-extract value.
  SS_PLAN_TIER_RAW="$(grep -o '"plan_tier"[[:space:]]*:[[:space:]]*"[^"]*"' "${PCV_CONFIG_FILE}" 2>/dev/null | head -n 1)"
  if [ -n "${SS_PLAN_TIER_RAW}" ]; then
    SS_PLAN_TIER_VAL="$(printf '%s' "${SS_PLAN_TIER_RAW}" | sed 's/.*:[[:space:]]*"\(.*\)"$/\1/')"
    if [ -n "${SS_PLAN_TIER_VAL}" ]; then
      SS_PLAN_TIER="${SS_PLAN_TIER_VAL}"
    fi
  fi
fi

# agent_config: from pcvplans/logs/decision-log.md — look for "## Agent Configuration"
# header; extract the next non-blank line (the one-line config summary).
# Missing → "v3.7-defaults".
SS_AGENT_CONFIG="v3.7-defaults"
AGENT_CONFIG_LOG="${PROJECT_DIR}/pcvplans/logs/decision-log.md"
if [ -f "${AGENT_CONFIG_LOG}" ]; then
  # awk-free approach: use sed to pick lines after first match of the header
  # up to the next --- / ## boundary, then pull first non-blank, non-header line.
  SS_AGENT_CONFIG_CANDIDATE="$(
    grep -n '^## Agent Configuration' "${AGENT_CONFIG_LOG}" 2>/dev/null \
      | head -n 1 \
      | cut -d: -f1
  )"
  if [ -n "${SS_AGENT_CONFIG_CANDIDATE}" ]; then
    # Read a small window after the header; pick first non-blank, non-header line.
    SS_AGENT_CONFIG_LINE="$(
      tail -n +"$((SS_AGENT_CONFIG_CANDIDATE + 1))" "${AGENT_CONFIG_LOG}" 2>/dev/null \
        | sed '/^[[:space:]]*$/d' \
        | grep -v '^##' \
        | grep -v '^---' \
        | head -n 1
    )"
    if [ -n "${SS_AGENT_CONFIG_LINE}" ]; then
      SS_AGENT_CONFIG="${SS_AGENT_CONFIG_LINE}"
    fi
  fi
fi

# project_type: map internal PROJECT_TYPE variable to sentinel vocabulary
# (spec: lite|phase-subfolder|multi-phase-root|single-phase|not-pcv)
case "${PROJECT_TYPE}" in
  lite)       SS_PROJECT_TYPE="lite" ;;
  phase_sub)  SS_PROJECT_TYPE="phase-subfolder" ;;
  multi_root) SS_PROJECT_TYPE="multi-phase-root" ;;
  single)     SS_PROJECT_TYPE="single-phase" ;;
  *)          SS_PROJECT_TYPE="not-pcv" ;;
esac

# written_at: ISO 8601 UTC timestamp
SS_WRITTEN_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
if [ -z "${SS_WRITTEN_AT}" ]; then
  SS_WRITTEN_AT="unknown"
fi

# ── 4.5.3 Write sentinel (skip if not-pcv — should not reach here) ──────────

if [ "${SS_PROJECT_TYPE}" != "not-pcv" ]; then
  SS_OUT="${LOGS_DIR}/session-state.json"
  SS_TMP="${SS_OUT}.tmp.$$"

  # Ensure logs dir exists (should already, but defensive)
  if mkdir -p "${LOGS_DIR}" 2>/dev/null; then
    # Escape string fields for JSON embedding
    SS_TRP_ESC="$(_pcv_ss_json_escape "${SS_TEST_RESPONSES_PATH}")"
    SS_PT_ESC="$(_pcv_ss_json_escape "${SS_PLAN_TIER}")"
    SS_AC_ESC="$(_pcv_ss_json_escape "${SS_AGENT_CONFIG}")"
    SS_PROJ_ESC="$(_pcv_ss_json_escape "${SS_PROJECT_TYPE}")"
    SS_TS_ESC="$(_pcv_ss_json_escape "${SS_WRITTEN_AT}")"

    # Write to temp file, then atomically mv. On any failure, emit warning
    # but do NOT exit non-zero — sentinel write is auxiliary to hook's
    # primary routing-injection job.
    {
      printf '{\n'
      printf '  "test_mode": %s,\n' "${SS_TEST_MODE}"
      printf '  "test_responses_path": "%s",\n' "${SS_TRP_ESC}"
      printf '  "plan_tier": "%s",\n' "${SS_PT_ESC}"
      printf '  "agent_config": "%s",\n' "${SS_AC_ESC}"
      printf '  "project_type": "%s",\n' "${SS_PROJ_ESC}"
      printf '  "written_at": "%s"\n' "${SS_TS_ESC}"
      printf '}\n'
    } > "${SS_TMP}" 2>/dev/null

    if [ -s "${SS_TMP}" ]; then
      if ! mv -f "${SS_TMP}" "${SS_OUT}" 2>/dev/null; then
        rm -f "${SS_TMP}" 2>/dev/null
        printf '%s\n' "PCV warning: failed to write session-state sentinel" >&2
      fi
    else
      rm -f "${SS_TMP}" 2>/dev/null
      printf '%s\n' "PCV warning: failed to write session-state sentinel" >&2
    fi
  else
    printf '%s\n' "PCV warning: failed to write session-state sentinel" >&2
  fi
fi

# ── end v3.14 session-state sentinel write ──

# ════════════════════════════════════════════════════════════════════════════
# SECTION 5 — OUTPUT: sanitize and emit hookSpecificOutput JSON
# ════════════════════════════════════════════════════════════════════════════

if [ -z "${DISPLAY_BLOCK}" ]; then
  # No display block generated — unexpected path; log and exit silently
  printf 'pcv: routing hook produced empty display block for type=%s\n' "${PROJECT_TYPE}" >&2
  exit 0
fi

# Sanitize the multi-line display block for JSON embedding
DISPLAY_SAFE="$(sanitize_json "${DISPLAY_BLOCK}")"

printf '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "%s"}}\n' \
  "${DISPLAY_SAFE}"

exit 0
