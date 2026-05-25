#!/usr/bin/env bash
# lib/tc-cli.sh — unified dispatcher for the /tc slash command.
#
# Invoked from commands/tc.md with the user-supplied arguments. Dispatches
# to the appropriate backend script (lib/draft-on.sh, lib/track-on.sh,
# lib/track-off.sh, lib/migrate-v1-to-v2.sh, install.sh --mark) or to an
# inline implementation (enable, disable, status, help).
#
# Subcommands:
#   /tc draft                      — per-turn suspend tracking (= /draft)
#   /tc enable <file>              — add `track-changes: true` to file's
#                                    frontmatter (or `% track-changes: true`
#                                    for .tex)
#   /tc disable <file>             — add `track-changes: false`
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
  /tc enable <file>       Add `track-changes: true` to the file
  /tc disable <file>      Add `track-changes: false` to the file

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
  /tc help                This message
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
# tc_run_resolve <subcommand> <file> [<ranges>]
# Dispatch §5 batch resolution to lib/tc_resolve.py.
# ---------------------------------------------------------------------------
tc_run_resolve() {
  local py
  if ! py="$(tc_resolve_python)"; then
    echo "tc: ERROR — Python 3 not found" >&2
    return 2
  fi
  ${py} "${SCRIPT_DIR}/tc_resolve.py" "$@"
}

# ---------------------------------------------------------------------------
# tc_enable_disable <file> <true|false>
# Add (or update) the per-file `track-changes` override.
#   .md / .qmd : YAML frontmatter key `track-changes: <bool>`
#   .tex       : magic comment `% track-changes: <bool>` (top of file)
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

  # Resolve Python (mirrors tc_resolve_python in pre-tool-use.sh).
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
        # Look for existing track-changes key in the YAML body.
        key_re = re.compile(r'^(\s*track-changes\s*:\s*)(\S+)(.*)$', re.MULTILINE)
        if key_re.search(body):
            new_body = key_re.sub(lambda mm: f"{mm.group(1)}{value}{mm.group(3)}", body)
            text = head + new_body + foot + text[m.end():]
        else:
            # Append the key to the frontmatter body.
            if body and not body.endswith('\n'):
                body += '\n'
            new_body = body + f"track-changes: {value}"
            text = head + new_body + foot + text[m.end():]
    else:
        # Prepend a fresh frontmatter block. Add a blank line after the
        # closing --- only if the file doesn't already start with a blank.
        first_line_blank = text.startswith('\n') or text == ''
        sep = '' if first_line_blank else '\n'
        text = f"---\ntrack-changes: {value}\n---\n{sep}{text}"

elif ftype == 'tex':
    # Look for an existing `% track-changes: ...` magic comment in the
    # first 10 lines.
    lines = text.split('\n', 10)
    found_idx = -1
    for i in range(min(len(lines), 10)):
        if re.search(r'%\s*track-changes\s*:', lines[i]):
            found_idx = i
            break
    if found_idx >= 0:
        lines[found_idx] = re.sub(
            r'%\s*track-changes\s*:\s*\S+.*',
            f'% track-changes: {value}',
            lines[found_idx]
        )
        text = '\n'.join(lines)
    else:
        # Prepend as line 1.
        text = f"% track-changes: {value}\n" + text

if text == orig:
    print(f"tc: {path} already has track-changes: {value} (no change)")
else:
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    print(f"tc: wrote track-changes: {value} to {path}")
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
          echo "    (no track-changes key in this file)"
        else
          echo "    track-changes: ${yaml_val}"
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
if [ $# -lt 1 ]; then
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
    # No args         → drop presence-only marker in CWD
    # One arg (dir)   → drop presence-only marker in <dir>
    # One arg (file)  → if it's a file (not dir), treat as: mark CWD with this file listed
    # Multi-args      → first arg is dir, remainder are listed basenames
    dir="${1:-.}"
    if [ $# -ge 1 ] && [ -d "$1" ]; then
      shift  # consume dir arg; remaining args are listed basenames
    elif [ $# -ge 1 ] && [ ! -d "$1" ]; then
      # First arg isn't a directory — assume CWD and treat args as basenames.
      dir="."
    fi
    if [ $# -ge 1 ]; then
      # List-mode marker.
      bash "${SKILL_DIR}/install.sh" --mark-files "${dir}" "$@"
    else
      bash "${SKILL_DIR}/install.sh" --mark "${dir}"
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
    tc_status "${1:-.}"
    ;;
  list)
    if [ $# -lt 1 ]; then
      echo "tc list: missing file argument" >&2
      echo "usage: /tc list <file>" >&2
      exit 1
    fi
    tc_run_resolve list "$1"
    ;;
  accept|reject)
    if [ $# -lt 2 ]; then
      echo "tc ${sub}: missing arguments" >&2
      echo "usage: /tc ${sub} <file> <ranges>   (e.g. 1-25,!7,!11)" >&2
      exit 1
    fi
    tc_run_resolve "${sub}" "$1" "$2"
    ;;
  accept-all|reject-all)
    if [ $# -lt 1 ]; then
      echo "tc ${sub}: missing file argument" >&2
      echo "usage: /tc ${sub} <file>" >&2
      exit 1
    fi
    tc_run_resolve "${sub}" "$1"
    ;;
  help|--help|-h)
    print_usage
    ;;
  *)
    echo "tc: unknown subcommand: ${sub}" >&2
    print_usage >&2
    exit 1
    ;;
esac
