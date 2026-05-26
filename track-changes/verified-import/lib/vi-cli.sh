#!/usr/bin/env bash
# lib/vi-cli.sh — thin launcher for the /import slash command.
#
# Resolves a Python 3 interpreter (same probe as track-changes' tc-cli.sh) and
# invokes lib/vi_verify.py in CLI `import` mode with the user's arguments:
#
#   /import <source>[#L<a>-L<b>] [<target>]
#
# vi_verify.py resolves + slices the source, resolves the target (the explicit
# arg or the working file), stages a one-shot pending-import under the
# track-changes state tree, and prints the source slice + a faithful-conversion
# instruction. The verified-import PreToolUse hook then verifies the converted
# write and signals a clean-import exemption that track-changes honors.
#
# Exit codes:
#   0  — staged successfully
#   1  — usage error / source or target unresolved / non-text source
#   2  — Python 3 not found

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve a working Python 3 command (mirrors tc-cli.sh tc_resolve_python).
VI_PY=""
for cand in python3 python "py -3" py; do
  if ${cand} -c "import sys; sys.exit(0 if sys.version_info[0] >= 3 else 49)" >/dev/null 2>&1; then
    VI_PY="${cand}"
    break
  fi
done

if [ -z "${VI_PY}" ]; then
  echo "verified-import: ERROR — Python 3 not found on PATH." >&2
  exit 2
fi

# shellcheck disable=SC2086
exec ${VI_PY} "${SCRIPT_DIR}/vi_verify.py" import "$@"
