#!/usr/bin/env bash
# session-start.sh — track-changes SessionStart hook
#
# Event:   SessionStart (fires once per Claude Code session boot)
# Purpose: Three responsibilities on every session start (MakePlan Rev 3 §3
#          Pattern 1; ConstructionPlan §2; Decision Log E5 / E6):
#
#   R1. Load the deployed SKILL.md content into `additionalContext` so the
#       fresh session sees the track-changes protocol immediately.
#
#   R2. Scan the CWD (single-level, non-recursive — bounded cost per
#       MakePlan D6) for *.tex files; for each, inspect the first 50 lines
#       for any of \newcommand{\tc} / \renewcommand{\tc} /
#       \providecommand{\tc} / \let\tc= . Accumulate .tex files missing all
#       four forms; if non-empty, append a preamble advisory to
#       additionalContext (Decision Log E5).
#
#   R3. Sweep $(tc_state_dir)/*.draft: rm any whose mtime is older than 1h
#       (3600s). Preserves recent sentinels from concurrent active sessions
#       (Decision Log E6).
#
# Stdin:   Hook event JSON payload (drained but not parsed — session ID is
#          resolved via tc_session_id from $CLAUDE_SESSION_ID).
# Stdout:  Single hookSpecificOutput JSON envelope:
#          {"hookSpecificOutput":{"hookEventName":"SessionStart",
#           "additionalContext":"<SKILL.md content [+ advisory]>"}}
# Stderr:  (none under normal operation; best-effort logging to tc.log)
# Exit:    0 on success; 1 only on catastrophic failure (cannot create
#          state dir AND cannot emit any JSON). Soft-fail throughout so a
#          missing SKILL.md or quirky filesystem does not break the session.

set -u

# ---------------------------------------------------------------------------
# Source the shared library so we get tc_session_id, tc_state_dir, tc_log.
# Resolve script dir robustly: works whether invoked from the project root,
# the deployed skill dir (~/.claude/skills/track-changes/), or any other cwd.
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=../lib/tc-common.sh
if ! source "${SCRIPT_DIR}/../lib/tc-common.sh" 2>/dev/null; then
  # Cannot source the library — emit a minimal valid JSON so Claude Code's
  # hook contract is still honored, then exit. Without the lib we cannot
  # perform R3 (state-dir sweep) but R1/R2 are still partially possible if
  # we hard-code the SKILL.md path; v1 chooses to fail soft and silent.
  printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":""}}\n'
  exit 0
fi

# Drain stdin if a payload was piped in (Claude Code may send the event
# JSON on stdin; we do not parse it in v1, but reading prevents SIGPIPE
# on the caller — matches stop.sh / user-prompt-submit.sh style).
if [ ! -t 0 ]; then
  cat >/dev/null 2>&1 || true
fi

# ---------------------------------------------------------------------------
# tc_json_escape — escape a string for JSON-double-quoted embedding.
# Prefers `jq -Rs .` when available (cleanest one-shot escape that handles
# all control chars + backslashes + quotes + multibyte correctly). Falls
# back to a pure-bash escaper if jq is missing on the target system.
#
# Input: arbitrary string (may contain newlines, backslashes, quotes, tabs).
# Output: a JSON string literal *including* the surrounding double quotes,
#         e.g. "hello\nworld" — caller embeds it as-is in the envelope.
# ---------------------------------------------------------------------------
tc_json_escape() {
  local s="${1:-}"
  if command -v jq >/dev/null 2>&1; then
    # -R: raw input. -s: slurp into one string. .: identity (jq emits the
    # JSON-encoded form by default). printf %s avoids a trailing newline
    # that jq would otherwise consume into the string.
    printf '%s' "$s" | jq -Rs .
  else
    # Bash-only fallback. Order matters: escape backslash first so we do
    # not re-escape the backslashes we introduce for quotes/newlines/tabs.
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    s="${s//$'\n'/\\n}"
    printf '"%s"' "$s"
  fi
}

# ---------------------------------------------------------------------------
# R1 — Load SKILL.md content.
#
# Resolution order (first hit wins):
#   1. $HOME/.claude/skills/track-changes/SKILL.md (the deployed location)
#   2. $SCRIPT_DIR/../SKILL.md (project-root layout — pre-install fixtures
#      and the construction-time test harness)
#
# If neither exists, emit a minimal advisory string so fixture tests see a
# non-empty additionalContext (rather than silent failure).
# ---------------------------------------------------------------------------
SKILL_CONTENT=""
SKILL_PATH=""

CANDIDATE_DEPLOYED="${HOME}/.claude/skills/track-changes/SKILL.md"
CANDIDATE_PROJECT="${SCRIPT_DIR}/../SKILL.md"

if [ -f "${CANDIDATE_DEPLOYED}" ]; then
  SKILL_PATH="${CANDIDATE_DEPLOYED}"
elif [ -f "${CANDIDATE_PROJECT}" ]; then
  SKILL_PATH="${CANDIDATE_PROJECT}"
fi

if [ -n "${SKILL_PATH}" ]; then
  # Read the full file. cat is the simplest portable reader; failure to read
  # (permissions, race) falls through to the missing-file advisory below.
  SKILL_CONTENT="$(cat "${SKILL_PATH}" 2>/dev/null || true)"
fi

if [ -z "${SKILL_CONTENT}" ]; then
  SKILL_CONTENT="Track-changes notice: SKILL.md could not be located at \$HOME/.claude/skills/track-changes/SKILL.md or relative to the hook script. The track-changes protocol is not in context for this session — install the skill or check the deployment path."
fi

# ---------------------------------------------------------------------------
# R2 — .tex preamble advisory scan (Decision Log E5).
#
# Single-level glob of *.tex in CWD (non-recursive — bounded cost). For each
# match, read the first 50 lines; check whether any of the four \tc-defining
# forms is present. Accumulate paths lacking all four; if non-empty, build
# an advisory and append it to SKILL_CONTENT below.
#
# Pattern checks use grep -E with `\\` to anchor a literal backslash. We
# bound the search to the first 50 lines so an enormous .tex file (e.g., a
# thesis) does not cost more than a few KB to inspect.
# ---------------------------------------------------------------------------
MISSING_TEX_FILES=""
TEX_FOUND_ANY=0

# Enable nullglob so an empty match expands to nothing rather than the
# literal pattern. shopt is bash-specific; safe under set -u.
shopt -s nullglob 2>/dev/null || true

for tex_file in ./*.tex; do
  TEX_FOUND_ANY=1
  # Read first 50 lines (head is portable). If head fails (unlikely), skip.
  HEAD_50="$(head -n 50 "${tex_file}" 2>/dev/null || true)"

  # v2 accepts any of:
  #   \usepackage{tc}     — the recommended form (tc.sty does the rest)
  #   \newcommand{\tc}    \renewcommand{\tc}    \providecommand{\tc}
  #   \let\tc=            \let\tc =
  if printf '%s' "${HEAD_50}" | grep -qE '\\usepackage\{[^}]*\btc\b[^}]*\}|\\(newcommand|renewcommand|providecommand)\{\\tc\}|\\let\\tc[[:space:]]*=' 2>/dev/null; then
    : # Definition present — skip.
  else
    rel_path="${tex_file#./}"
    if [ -z "${MISSING_TEX_FILES}" ]; then
      MISSING_TEX_FILES="${rel_path}"
    else
      MISSING_TEX_FILES="${MISSING_TEX_FILES}, ${rel_path}"
    fi
  fi
done

shopt -u nullglob 2>/dev/null || true

# Build advisory only if at least one .tex file is missing the macro.
ADVISORY=""
if [ -n "${MISSING_TEX_FILES}" ]; then
  ADVISORY="

## Track-changes notice

The following .tex files lack the \\tc macro definition required for highlight rendering: ${MISSING_TEX_FILES}. Before reviewing AI-introduced edits in these files, add this line to each file's preamble:

\\usepackage{tc}

(tc.sty is installed at \$HOME/.claude/skills/track-changes/lib/tc.sty; copy it into your project's preamble path if it is not on the LaTeX search path. For the inline-definition or xcolor-fallback alternatives, see SKILL.md §10 and reference/latex.md.)"
fi

# Final additionalContext payload.
ADDITIONAL_CONTEXT="${SKILL_CONTENT}${ADVISORY}"

# ---------------------------------------------------------------------------
# R3 — Stale-sentinel sweep.
#
# Enumerate *.draft + *.track-on + *.track-off; rm anything older than 3600s.
# Recent sentinels from concurrent active sessions are preserved.
# Portability: GNU stat (`stat -c %Y`) Linux + Git-bash; BSD stat on macOS.
# ---------------------------------------------------------------------------
STATE_DIR="$(tc_state_dir 2>/dev/null || true)"
if [ -n "${STATE_DIR}" ] && [ -d "${STATE_DIR}" ]; then
  NOW_EPOCH="$(date +%s 2>/dev/null || true)"
  if [ -n "${NOW_EPOCH}" ]; then
    shopt -s nullglob 2>/dev/null || true
    # Sweep .draft (current) and any stale .track-on / .track-off left over
    # from pre-Fix#6 installs.
    for sentinel in "${STATE_DIR}"/*.draft "${STATE_DIR}"/*.track-on "${STATE_DIR}"/*.track-off; do
      MTIME="$(stat -c %Y "${sentinel}" 2>/dev/null || stat -f %m "${sentinel}" 2>/dev/null || true)"
      if [ -z "${MTIME}" ]; then
        continue
      fi
      AGE=$((NOW_EPOCH - MTIME))
      if [ "${AGE}" -gt 3600 ]; then
        rm -f "${sentinel}" 2>/dev/null || true
        tc_log "session-start.sh: swept stale sentinel ${sentinel} (age ${AGE}s)"
      fi
    done
    shopt -u nullglob 2>/dev/null || true
  fi
fi

# ---------------------------------------------------------------------------
# Emit the SessionStart hook output JSON.
#
# Contract: {"hookSpecificOutput": {"hookEventName": "SessionStart",
#            "additionalContext": "<string>"}}
#
# We escape ADDITIONAL_CONTEXT once via tc_json_escape (which returns the
# value already wrapped in double quotes), then inline it into the envelope.
# ---------------------------------------------------------------------------
ESCAPED_CTX="$(tc_json_escape "${ADDITIONAL_CONTEXT}")"

printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":%s}}\n' \
  "${ESCAPED_CTX}"

exit 0
