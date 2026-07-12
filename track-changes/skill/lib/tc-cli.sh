#!/usr/bin/env bash
# lib/tc-cli.sh — unified dispatcher for the /tc slash command.
#
# Invoked from commands/tc.md with the user-supplied arguments. Dispatches
# to the appropriate backend script (lib/draft-on.sh, lib/migrate-v1-to-v2.sh)
# or to an inline implementation (enable, disable, mark, status, help). The
# `mark` case writes the .tc-tracked marker directly via lib/tc-mark.sh — it
# does NOT shell out to install.sh (install.sh is not deployed into the skill
# dir post-split; see the C8-fix dispatch entry in the decision log).
#
# Subcommands:
#   /tc draft                      — per-turn suspend tracking (= /draft)
#   /tc enable <file>              — add `tc-track: true` to file's
#                                    frontmatter (or `% tc-track: true`
#                                    for .tex)
#   /tc disable <file>             — add `tc-track: false`
#   /tc mark [<dir>] [<file> ...]  — drop .tc-tracked marker in <dir>
#                                    (default CWD); with filename args, the
#                                    marker lists ONLY those basenames as
#                                    tracked (list mode); without filename
#                                    args the marker is presence-only (all
#                                    files in folder tracked)
#   /tc migrate <dir>              — run v1 → v2 migration on <dir>
#   /tc status [<file>]            — print activation chain for <file>
#                                    (or CWD)
#   /tc list <file>                — list each mark with N + content preview
#   /tc accept <file> <ranges>     — accept marks (keep new; strip wrapper)
#   /tc reject <file> <ranges>     — reject marks (restore old; strip wrapper)
#                                    ranges syntax: 1-25,!7,!11
#   /tc accept-all <file>          — accept every mark in <file>
#   /tc reject-all <file>          — reject every mark in <file>
#   /tc coverage <doc> <source> [--units N,N,...]
#                                  — audit: per-unit content-token coverage
#                                    of <doc> against <source> (8.2.0)
#   /tc help                       — print this usage
#
# Fix #6 removed /tc on and /tc off — session-scope toggles reintroduced
# the internal-file friction problem. Use folder marker (bulk) or
# per-file YAML (selective); /draft remains as per-turn override.
#
# Exit codes:
#   0  — command succeeded
#   1  — usage error (bad subcommand or missing required arg)
#   2  — operation error (file write failed, etc.)

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=./tc-common.sh
if ! source "${SCRIPT_DIR}/tc-common.sh" 2>/dev/null; then
  echo "tc: ERROR — cannot source ${SCRIPT_DIR}/tc-common.sh" >&2
  exit 2
fi

print_usage() {
  cat <<'USAGE'
/tc — track-changes unified command

Turn control:
  /tc draft               Suspend tracking for the current turn only

Per-file opt-in / opt-out (adds YAML frontmatter or magic comment):
  /tc enable <file>       Add `tc-track: true` to the file
  /tc disable <file>      Add `tc-track: false` to the file

Per-folder activation:
  /tc mark [<dir>]                    Drop presence-only .tc-tracked marker
                                      in <dir> (tracks ALL files in that
                                      folder; default <dir> = current dir).
  /tc mark <dir> <file1> [<file2>...] Drop list-mode .tc-tracked marker
                                      that tracks only the listed basenames
                                      in <dir>.

Migration:
  /tc migrate <dir>       Convert v1 marks to v2 in all .md/.qmd/.tex files

Batch resolution (edits the file; writes explicit audit attribution):
  /tc list <file>                 List each mark with its N + content preview
  /tc accept <file> <ranges>      Accept marks: keep the new text, strip the
                                  <mark>...</mark><sup>N</sup> wrapper
  /tc reject <file> <ranges>      Reject marks: restore the old text, strip
                                  the wrapper
                                  ranges: comma-separated, e.g. 1-25,!7,!11
                                  (inclusive ranges; !N excludes N)
  /tc accept-all <file>           Accept every mark in <file>
  /tc reject-all <file>           Reject every mark in <file>

Diagnostics:
  /tc status [<file>]     Show the activation chain for <file> (or CWD)
  /tc coverage <doc> <source> [--units N,N,...]
                          Audit import completeness: for each source unit
                          (<!-- slide N --> marker, or the whole file), report
                          % of content tokens covered by <doc> and list any
                          missing ones (--slides accepted as an alias).
                          Exit non-zero when content was dropped.
  /tc help                This message

Cooperating skills (routes to the installed companion skill):
  /tc import [--allow-partial] <source>[#L<a>-L<b>] [<target>]
                          Run verified-import: resolve and slice a text source,
                          print the slice + conversion instruction, you convert
                          faithfully and write only the converted block; lands
                          clean via sha-bound exemption; self-mark only
                          significant/meaning-altering changes. The write is
                          coverage-gated (8.2.0): dropping a source content
                          token blocks the import and names what is missing;
                          --allow-partial is the explicit override (recorded
                          in the audit log with the dropped tokens).
  /tc polish [<file>]     Run tc-polish: dictation cleanup + full editorial
                          pass; changes surface as track-changes marks;
                          never changes meaning; never auto-corrects a flagged
                          protected token.
USAGE
}

# ---------------------------------------------------------------------------
# tc_resolve_python — resolve a working Python 3 command (echoes it) or
# returns non-zero. Mirrors the probe used by tc_enable_disable.
# ---------------------------------------------------------------------------
tc_resolve_python() {
  local cand
  for cand in python3 python "py -3" py; do
    if ${cand} -c "import sys; sys.exit(0 if sys.version_info[0] >= 3 else 49)" >/dev/null 2>&1; then
      printf '%s' "${cand}"
      return 0
    fi
  done
  return 1
}

# ---------------------------------------------------------------------------
# tc_resolve_working_file — resolve the "working file" when a resolution
# subcommand is given no <file> argument (Fix #4).
#
# Design decision (dispatch log, honored exactly): no IDE-open env var is
# exposed to a bash slash command in this harness (only $CLAUDE_SESSION_ID),
# and no "last-edited file" state exists. So the working file is defined as
# the MOST-RECENTLY-MODIFIED tracked-active .md/.qmd/.tex file under the
# project scope:
#   - Scope:      the git root of the CWD if resolvable, else the CWD.
#   - Candidates: .md/.qmd/.tex files under scope whose tc_should_track
#                 returns 0 (tracking active). Skip .git/, node_modules/,
#                 and hidden directories.
#   - Pick:       the newest by mtime.
#
# Echoes the chosen path and returns 0; returns non-zero (no output) when
# there is no candidate.
# ---------------------------------------------------------------------------
tc_resolve_working_file() {
  local scope
  scope="$(git -C . rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -z "${scope}" ]; then
    scope="$(pwd)"
  fi

  # Collect candidate files (bounded, portable). Prune .git, node_modules,
  # and any hidden directory; match the three tracked extensions.
  local best="" best_mtime=-1
  local f mtime reason
  while IFS= read -r f; do
    [ -z "${f}" ] && continue
    # Activation gate: tracking must be ON for this file.
    reason="$(tc_should_track "${f}" 2>/dev/null || true)"
    case "${reason}" in
      on-*) ;;
      *) continue ;;
    esac
    # mtime in epoch seconds (GNU stat then BSD stat fallback).
    mtime="$(stat -c %Y "${f}" 2>/dev/null || stat -f %m "${f}" 2>/dev/null || echo 0)"
    if [ "${mtime}" -gt "${best_mtime}" ]; then
      best_mtime="${mtime}"
      best="${f}"
    fi
  done <<EOF
$(find "${scope}" \
    \( -name .git -o -name node_modules -o -name '.*' \) -prune -o \
    -type f \( -name '*.md' -o -name '*.qmd' -o -name '*.tex' \) -print \
    2>/dev/null)
EOF

  if [ -z "${best}" ]; then
    return 1
  fi
  printf '%s' "${best}"
  return 0
}

# ---------------------------------------------------------------------------
# tc_default_working_file <subcommand> — echo the working file (Fix #4),
# emitting the informational/error lines on stderr. Returns 0 with the path
# on stdout, or 1 (after printing the clear error) when no candidate exists.
# ---------------------------------------------------------------------------
tc_default_working_file() {
  local sub="$1"
  local scope wf
  scope="$(git -C . rev-parse --show-toplevel 2>/dev/null || pwd)"
  if wf="$(tc_resolve_working_file)"; then
    echo "tc ${sub}: no <file> given — using ${wf} (most-recently-modified tracked file)." >&2
    printf '%s' "${wf}"
    return 0
  fi
  echo "tc ${sub}: no tracked file found under ${scope}; specify <file> explicitly." >&2
  return 1
}

# ---------------------------------------------------------------------------
# tc_run_resolve <subcommand> <file> [<ranges>]
# Dispatch §5 batch resolution to lib/tc_resolve.py.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# tc_require_clean <file> <sub>
# Committed-content invariant (v7, 2026-07-12): a mark may be RESOLVED only
# from committed state. Rationale: an open mark/region is editable right up
# to resolution, so approval could otherwise attach to content the reviewer
# never read (observed live: an AI polish edit applied and accepted in one
# step). Requiring a clean file means (1) instructor tweaks land as their own
# attributable commit, (2) any AI polish lands as its own MARKED commit, and
# (3) git history shows exactly the text each approval covered. Marks
# accumulate across commits and resolve in batches — that is the intended
# workflow, not a cost. Read-only subcommands (list) are not gated.
# Human-only override for genuine edge cases: TC_FORCE=1.
# Fail-open outside a git repo (the invariant is meaningless there).
# ---------------------------------------------------------------------------
tc_require_clean() {
  local file="$1" sub="$2" dir top
  [ "${TC_FORCE:-0}" = "1" ] && return 0
  dir="$(dirname -- "${file}")"
  top="$(git -C "${dir}" rev-parse --show-toplevel 2>/dev/null)" || return 0
  if ! git -C "${dir}" ls-files --error-unmatch -- "$(basename -- "${file}")" >/dev/null 2>&1; then
    echo "tc ${sub}: BLOCKED — ${file} is not committed (untracked)." >&2
    echo "Resolution runs only on committed content; commit the file first." >&2
    return 3
  fi
  if ! git -C "${dir}" diff --quiet HEAD -- "$(basename -- "${file}")" 2>/dev/null; then
    echo "tc ${sub}: BLOCKED — ${file} has uncommitted changes." >&2
    echo "Marks resolve only from COMMITTED content, so the approved text is" >&2
    echo "exactly what git history shows was reviewed. Sequence:" >&2
    echo "  1. commit the file as it stands (instructor tweaks as their own" >&2
    echo "     commit; any AI corrections as MARKED edits in their own commit)," >&2
    echo "  2. review the diff(s)," >&2
    echo "  3. re-run /tc ${sub}." >&2
    echo "(Human-only override: TC_FORCE=1 — never for AI use.)" >&2
    return 3
  fi
  return 0
}

tc_run_resolve() {
  local py
  case "$1" in
    accept|reject|accept-all|reject-all)
      tc_require_clean "$2" "$1" || return 3 ;;
  esac
  if ! py="$(tc_resolve_python)"; then
    echo "tc: ERROR — Python 3 not found" >&2
    return 2
  fi
  ${py} "${SCRIPT_DIR}/tc_resolve.py" "$@"
}

# ---------------------------------------------------------------------------
# tc_enable_disable <file> <true|false>
# Add (or update) the per-file `tc-track` override.
#   .md / .qmd : YAML frontmatter key `tc-track: <bool>`
#   .tex       : magic comment `% tc-track: <bool>` (top of file)
# Idempotent: if the file already declares the same value, no-op.
# ---------------------------------------------------------------------------
tc_enable_disable() {
  local file="$1" value="$2"
  if [ ! -f "${file}" ]; then
    echo "tc: ERROR — file not found: ${file}" >&2
    return 2
  fi
  local ftype
  ftype="$(tc_file_type "${file}")"
  case "${ftype}" in
    md|qmd|tex) ;;
    *) echo "tc: ERROR — file extension not supported: ${file} (must be .md, .qmd, or .tex)" >&2; return 2 ;;
  esac

  # Resolve Python (mirrors the interpreter resolution in pre_tool_use.py).
  local py=""
  local cand
  for cand in python3 python "py -3" py; do
    if ${cand} -c "import sys; sys.exit(0 if sys.version_info[0] >= 3 else 49)" >/dev/null 2>&1; then
      py="${cand}"
      break
    fi
  done
  if [ -z "${py}" ]; then
    echo "tc: ERROR — Python 3 not found" >&2
    return 2
  fi

  TC_FILE="${file}" TC_VALUE="${value}" TC_FTYPE="${ftype}" ${py} - <<'PYEOF'
import os, re, sys
path = os.environ['TC_FILE']
value = os.environ['TC_VALUE']    # 'true' or 'false'
ftype = os.environ['TC_FTYPE']    # 'md' | 'qmd' | 'tex'

with open(path, 'r', encoding='utf-8', newline='') as f:
    text = f.read()
orig = text

if ftype in ('md', 'qmd'):
    # Detect existing YAML frontmatter (top-of-file --- ... ---).
    fm_re = re.compile(r'\A(---\s*\n)(.*?)(\n---\s*\n)', re.DOTALL)
    m = fm_re.match(text)
    if m:
        head, body, foot = m.group(1), m.group(2), m.group(3)
        # Look for existing tc-track key in the YAML body.
        key_re = re.compile(r'^(\s*tc-track\s*:\s*)(\S+)(.*)$', re.MULTILINE)
        if key_re.search(body):
            new_body = key_re.sub(lambda mm: f"{mm.group(1)}{value}{mm.group(3)}", body)
            text = head + new_body + foot + text[m.end():]
        else:
            # Append the key to the frontmatter body.
            if body and not body.endswith('\n'):
                body += '\n'
            new_body = body + f"tc-track: {value}"
            text = head + new_body + foot + text[m.end():]
    else:
        # Prepend a fresh frontmatter block. Add a blank line after the
        # closing --- only if the file doesn't already start with a blank.
        first_line_blank = text.startswith('\n') or text == ''
        sep = '' if first_line_blank else '\n'
        text = f"---\ntc-track: {value}\n---\n{sep}{text}"

elif ftype == 'tex':
    # Look for an existing `% tc-track: ...` magic comment in the
    # first 10 lines.
    lines = text.split('\n', 10)
    found_idx = -1
    for i in range(min(len(lines), 10)):
        if re.search(r'%\s*tc-track\s*:', lines[i]):
            found_idx = i
            break
    if found_idx >= 0:
        lines[found_idx] = re.sub(
            r'%\s*tc-track\s*:\s*\S+.*',
            f'% tc-track: {value}',
            lines[found_idx]
        )
        text = '\n'.join(lines)
    else:
        # Prepend as line 1.
        text = f"% tc-track: {value}\n" + text

if text == orig:
    print(f"tc: {path} already has tc-track: {value} (no change)")
else:
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    print(f"tc: wrote tc-track: {value} to {path}")
PYEOF
  return $?
}

# ---------------------------------------------------------------------------
# tc_status <file-or-dir>
# Show which activation mechanism applies to <file-or-dir> and what the
# resolved state is. Uses tc_should_track if a file is given; reports
# the marker walk-up for a directory.
# ---------------------------------------------------------------------------
tc_status() {
  local target="${1:-.}"
  if [ ! -e "${target}" ]; then
    echo "tc: ERROR — path not found: ${target}" >&2
    return 2
  fi
  echo "track-changes status:"
  echo "  Target:   ${target}"
  echo ""
  echo "  Per-turn sentinel:"
  if tc_sentinel_active_draft 2>/dev/null; then
    echo "    /draft       ACTIVE (suspends tracking this turn)"
  else
    echo "    /draft       (none)"
  fi
  echo ""
  if [ -f "${target}" ]; then
    local ftype
    ftype="$(tc_file_type "${target}")"
    case "${ftype}" in
      md|qmd|tex)
        echo "  Per-file YAML / magic comment:"
        local yaml_val
        yaml_val="$(tc_check_yaml_override "${target}")"
        if [ -z "${yaml_val}" ]; then
          echo "    (no tc-track key in this file)"
        else
          echo "    tc-track: ${yaml_val}"
        fi
        echo ""
        echo "  Folder marker (same directory only):"
        local marker
        marker="$(tc_find_marker "${target}" 2>/dev/null || true)"
        if [ -n "${marker}" ]; then
          local mmode
          mmode="$(tc_marker_lists_file "${marker}" "${target}" 2>/dev/null || true)"
          case "${mmode}" in
            all)      echo "    found: ${marker} (presence-only — tracks all files in folder)" ;;
            listed)   echo "    found: ${marker} (list mode — file's basename IS listed)" ;;
            off-list) echo "    found: ${marker} (list mode — file's basename NOT listed)" ;;
            *)        echo "    found: ${marker} (could not parse marker content)" ;;
          esac
        else
          echo "    (no .tc-tracked marker in file's own folder)"
        fi
        echo ""
        local reason
        reason="$(tc_should_track "${target}" 2>/dev/null || printf 'off-default')"
        case "${reason}" in
          on-*)  echo "  RESOLVED: tracking ACTIVE  (${reason})" ;;
          draft) echo "  RESOLVED: tracking SUSPENDED for this turn (${reason})" ;;
          *)     echo "  RESOLVED: tracking INACTIVE (${reason})" ;;
        esac
        ;;
      *)
        echo "  (file extension not tracked: ${target})"
        ;;
    esac
  else
    # Directory: report this folder's marker (if any) plus mode.
    echo "  Folder marker (this directory only):"
    local marker_path="${target}/.tc-tracked"
    if [ -f "${marker_path}" ]; then
      local mmode
      mmode="$(tc_marker_lists_file "${marker_path}" "${target}/_probe_" 2>/dev/null || true)"
      case "${mmode}" in
        all)      echo "    found: ${marker_path} (presence-only — tracks all files in this folder)" ;;
        listed|off-list)
          echo "    found: ${marker_path} (list mode)"
          echo "    listed basenames:"
          grep -v '^\s*\(#\|$\)' "${marker_path}" 2>/dev/null | sed 's/^/      /' || true
          ;;
        *) echo "    found: ${marker_path}" ;;
      esac
    else
      echo "    (no .tc-tracked marker in this directory)"
    fi
  fi
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------
# Fix #5: bare `/tc` prints the compact menu. tc.md runs `bash tc-cli.sh
# $ARGUMENTS`; with no input $ARGUMENTS may expand to nothing (no positional
# args) OR to a single empty/whitespace-only argument. Treat both the same:
# print the menu and exit 0.
if [ $# -lt 1 ]; then
  print_usage
  exit 0
fi
# Whitespace-only first arg (e.g. `$ARGUMENTS` expanding to "") → treat as
# no args: print the menu and exit 0.
if [ $# -eq 1 ] && [ -z "${1//[[:space:]]/}" ]; then
  print_usage
  exit 0
fi

sub="$1"
shift

case "${sub}" in
  draft)
    bash "${SCRIPT_DIR}/draft-on.sh"
    ;;
  enable)
    if [ $# -lt 1 ]; then
      echo "tc enable: missing file argument" >&2
      echo "usage: /tc enable <file>" >&2
      exit 1
    fi
    tc_enable_disable "$1" "true"
    ;;
  disable)
    if [ $# -lt 1 ]; then
      echo "tc disable: missing file argument" >&2
      echo "usage: /tc disable <file>" >&2
      exit 1
    fi
    tc_enable_disable "$1" "false"
    ;;
  mark)
    # /tc mark [<dir>] [<file1> ...]
    # No args             → drop presence-only marker in CWD
    # <dir>               → drop presence-only marker in <dir>
    # <dir> <file1> ...   → drop list-mode marker in <dir> listing those basenames
    #
    # The first positional is ALWAYS the target DIRECTORY. If it is supplied but
    # is not an existing directory (a file, or a path that doesn't exist), that
    # is a hard error: `mark` writes a folder marker and never silently retargets
    # to CWD (mirrors `migrate`, the other directory operation). To opt a single
    # file in, use `/tc enable <file>`; to list a file under a folder marker,
    # name its directory first: `/tc mark <dir> <basename>`.
    dir="."
    if [ $# -ge 1 ]; then
      if [ ! -d "$1" ]; then
        echo "tc mark: '$1' is not a directory" >&2
        echo "  'mark' writes a folder marker; its first argument must be an existing directory." >&2
        echo "  To track a single file:         /tc enable <file>" >&2
        echo "  To list files under a folder:   /tc mark <dir> <file> [<file>...]" >&2
        exit 1
      fi
      dir="$1"
      shift  # consume dir arg; remaining args are listed basenames
    fi
    # Write the marker directly via the shared lib (install.sh is NOT deployed
    # into the skill dir post-split, so the old `bash install.sh --mark` path
    # would fail). /tc mark has no --force, so pass force=0 (idempotent).
    if ! source "${SCRIPT_DIR}/tc-mark.sh" 2>/dev/null; then
      echo "tc: ERROR — cannot source ${SCRIPT_DIR}/tc-mark.sh" >&2
      exit 2
    fi
    if [ $# -ge 1 ]; then
      # List-mode marker.
      tc_mark_list "${dir}" 0 "$@"
    else
      tc_mark_presence "${dir}" 0
    fi
    ;;
  migrate)
    if [ $# -lt 1 ]; then
      echo "tc migrate: missing directory argument" >&2
      echo "usage: /tc migrate <dir>" >&2
      exit 1
    fi
    bash "${SCRIPT_DIR}/migrate-v1-to-v2.sh" "$1"
    ;;
  status)
    # Fix #4: a missing target resolves to the working file (when one
    # exists); otherwise fall back to CWD (status of "." is meaningful).
    if [ $# -lt 1 ]; then
      if wf="$(tc_default_working_file status)"; then
        tc_status "${wf}"
      else
        tc_status "."
      fi
    else
      tc_status "$1"
    fi
    ;;
  list)
    # Fix #4: missing <file> → working file (zero args, no ranges).
    if [ $# -lt 1 ]; then
      if ! wf="$(tc_default_working_file list)"; then
        exit 1
      fi
      tc_run_resolve list "${wf}"
    else
      tc_run_resolve list "$1"
    fi
    ;;
  accept|reject)
    # Arg shapes:
    #   /tc accept <file> <ranges>   (explicit file)
    #   /tc accept <ranges>          (file omitted; first positional is RANGES)
    # Disambiguation: a single argument that looks like a ranges spec
    # (matches ^!?\d, e.g. "1-5" or "!7,11") is treated as ranges and the
    # working file is resolved (Fix #4). A single argument that does NOT look
    # like ranges is treated as a file with missing ranges (usage error).
    if [ $# -ge 2 ]; then
      tc_run_resolve "${sub}" "$1" "$2"
    elif [ $# -eq 1 ] && printf '%s' "$1" | grep -qE '^!?[0-9]'; then
      # Ranges-only form: resolve the working file.
      if ! wf="$(tc_default_working_file "${sub}")"; then
        exit 1
      fi
      tc_run_resolve "${sub}" "${wf}" "$1"
    else
      echo "tc ${sub}: missing arguments" >&2
      echo "usage: /tc ${sub} <file> <ranges>   (e.g. 1-25,!7,!11)" >&2
      echo "   or: /tc ${sub} <ranges>          (uses the working file)" >&2
      exit 1
    fi
    ;;
  accept-all|reject-all)
    # Fix #4: missing <file> → working file (these take no ranges).
    if [ $# -lt 1 ]; then
      if ! wf="$(tc_default_working_file "${sub}")"; then
        exit 1
      fi
      tc_run_resolve "${sub}" "${wf}"
    else
      tc_run_resolve "${sub}" "$1"
    fi
    ;;
  coverage)
    # /tc coverage <doc> <source> [--units N,N,...]  (8.2.0 audit mode)
    if [ $# -lt 2 ]; then
      echo "tc coverage: missing arguments" >&2
      echo "usage: /tc coverage <doc> <source> [--units N,N,...]" >&2
      exit 1
    fi
    if ! py="$(tc_resolve_python)"; then
      echo "tc: ERROR — Python 3 not found" >&2
      exit 2
    fi
    ${py} "${SCRIPT_DIR}/tc_coverage_audit.py" "$@"
    ;;
  import)
    VI="$HOME/.claude/skills/verified-import/lib/vi-cli.sh"
    [ -f "$VI" ] || { echo "tc import: verified-import not installed — reinstall the track-changes suite (see bootstrap)." >&2; exit 2; }
    exec bash "$VI" "$@" ;;
  polish)
    PC="$HOME/.claude/skills/tc-polish/lib/polish-cli.sh"
    [ -f "$PC" ] || { echo "tc polish: tc-polish not installed — reinstall the track-changes suite (see bootstrap)." >&2; exit 2; }
    bash "$PC" analyze "$@"
    echo "tc polish: follow tc-polish SKILL.md bright-line rules — improve freely, never change meaning, never auto-correct a flagged protected token." ;;
  help|--help|-h)
    print_usage
    ;;
  *)
    echo "tc: unknown subcommand: ${sub}" >&2
    print_usage >&2
    exit 1
    ;;
esac
