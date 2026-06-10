"""tc_core.activation — activation gate (relocated from v2 tc_activation, v3 C1).

Pure-Python activation resolution used by the native PreToolUse hook so the
decision is made in-process without invoking bash.

Activation precedence (most-local wins):
  1. /draft per-turn sentinel
  2. Per-file YAML / magic comment (forces on or off)
  3. Folder-local .tc-tracked marker (presence-only or list-mode)
  4. Hidden-file exclusion (basename starts with .) — when marker would
     otherwise activate
  5. Default off
"""
import os
import re

# Per-file activation key is `tc-track`. It deliberately does NOT use
# `track-changes`, which is a RESERVED Quarto YAML field (Quarto only accepts
# accept/reject/all there and errors on true/false), so the old key broke every
# .qmd/.md render. `tc-track` is an unknown key Quarto passes through untouched.
_YAML_TRUE_RE = re.compile(r'^tc-track:.*true', re.IGNORECASE)
_YAML_FALSE_RE = re.compile(r'^tc-track:.*false', re.IGNORECASE)
_TEX_MAGIC_TRUE_RE = re.compile(r'^.*%.*tc-track:.*true', re.IGNORECASE)
_TEX_MAGIC_FALSE_RE = re.compile(r'^.*%.*tc-track:.*false', re.IGNORECASE)


def tc_file_type(path):
    """Classify path by extension: md / qmd / tex / other."""
    if path.endswith('.md'):
        return 'md'
    if path.endswith('.qmd'):
        return 'qmd'
    if path.endswith('.tex'):
        return 'tex'
    return 'other'


def tc_state_dir():
    """Return the persistent state directory, creating it if needed."""
    home = os.environ.get('HOME') or os.path.expanduser('~')
    d = os.path.join(home, '.claude', 'skills', 'track-changes', 'state')
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return None
    return d


def tc_session_id():
    return os.environ.get('CLAUDE_SESSION_ID') or 'default'


# v6 Fix B (mechanical user-only /draft): the draft sentinel is honored ONLY if
# it carries this authorized marker, which is written EXCLUSIVELY by the
# UserPromptSubmit hook (user-prompt-submit.sh) when the human's own prompt
# requests drafting. UserPromptSubmit fires only on human input — the AI cannot
# trigger it — so the AI cannot author an honored sentinel. A bare/forged file
# (e.g. `touch …/<session>.draft`) lacks the marker and is ignored. This string
# MUST stay byte-identical to DRAFT_AUTH_MARKER in lib/tc-common.sh.
DRAFT_AUTH_MARKER = 'tc-draft-authorized-by=user-prompt-submit'


def _sentinel_authorized(path):
    """True iff `path` exists AND contains the authorized marker."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return DRAFT_AUTH_MARKER in f.read(4096)
    except (IOError, OSError):
        return False


def tc_sentinel_active_draft():
    """True if an AUTHORIZED /draft sentinel exists for the current session.

    Honors BOTH the session-specific sentinel (state/<session>.draft) AND the
    shared fallback (state/default.draft) for the Windows / cross-shell case
    where $CLAUDE_SESSION_ID is unset. v6: existence alone is insufficient — the
    sentinel must carry the authorized marker (see DRAFT_AUTH_MARKER).
    """
    sd = tc_state_dir()
    if not sd:
        return False
    sid = tc_session_id()
    if _sentinel_authorized(os.path.join(sd, sid + '.draft')):
        return True
    return _sentinel_authorized(os.path.join(sd, 'default.draft'))


def tc_check_yaml_override(file_path):
    """Inspect file for per-file activation override.
    Returns 'on' / 'off' / '' (no override)."""
    if not file_path or not os.path.isfile(file_path):
        return ''
    ftype = tc_file_type(file_path)
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            if ftype in ('md', 'qmd'):
                in_fm = False
                for line_no, line in enumerate(f, start=1):
                    if line_no > 50:
                        break
                    line = line.rstrip('\n').rstrip('\r')
                    if line_no == 1:
                        if line == '---':
                            in_fm = True
                            continue
                        return ''
                    if in_fm and line == '---':
                        return ''
                    if in_fm:
                        if _YAML_TRUE_RE.match(line):
                            return 'on'
                        if _YAML_FALSE_RE.match(line):
                            return 'off'
            elif ftype == 'tex':
                for line_no, line in enumerate(f, start=1):
                    if line_no > 10:
                        break
                    line = line.rstrip('\n').rstrip('\r')
                    if _TEX_MAGIC_TRUE_RE.match(line):
                        return 'on'
                    if _TEX_MAGIC_FALSE_RE.match(line):
                        return 'off'
    except (IOError, OSError):
        return ''
    return ''


def tc_find_marker(file_path):
    """Check the file's OWN directory for a .tc-tracked marker.
    Returns the marker path on hit, None otherwise."""
    if not file_path:
        return None
    d = os.path.dirname(os.path.abspath(file_path))
    marker = os.path.join(d, '.tc-tracked')
    if os.path.isfile(marker):
        return marker
    return None


def tc_marker_lists_file(marker_path, file_path):
    """Decide whether a marker activates tracking for file_path.
    Returns 'all' (presence-only), 'listed', 'off-list', or '' (parse fail)."""
    if not marker_path or not os.path.isfile(marker_path):
        return ''
    try:
        with open(marker_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except (IOError, OSError):
        return ''
    entries = []
    for line in content.splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        entries.append(s)
    if not entries:
        return 'all'
    basename = os.path.basename(file_path)
    if basename in entries:
        return 'listed'
    return 'off-list'


def tc_is_hidden_file(file_path):
    """True if basename starts with '.'."""
    if not file_path:
        return False
    return os.path.basename(file_path).startswith('.')


def tc_should_track(file_path):
    """Resolve activation for file_path.
    Returns one of: 'draft', 'off-file', 'on-file', 'on-marker-presence',
    'on-marker-listed', 'off-marker-not-listed', 'off-hidden', 'off-default'.
    Tracking is active iff the result starts with 'on-'."""
    if not file_path:
        return 'off-default'
    if tc_sentinel_active_draft():
        return 'draft'
    yaml_val = tc_check_yaml_override(file_path)
    if yaml_val == 'on':
        return 'on-file'
    if yaml_val == 'off':
        return 'off-file'
    marker = tc_find_marker(file_path)
    if marker:
        if tc_is_hidden_file(file_path):
            return 'off-hidden'
        mode = tc_marker_lists_file(marker, file_path)
        if mode == 'all':
            return 'on-marker-presence'
        if mode == 'listed':
            return 'on-marker-listed'
        if mode == 'off-list':
            return 'off-marker-not-listed'
    return 'off-default'


def is_tracking_active(reason):
    """Convenience: True if `reason` (from tc_should_track) indicates active."""
    return reason.startswith('on-')
