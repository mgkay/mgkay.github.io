"""tc_provenance — track-changes §0 source-provenance import wrappers.

Keeps the §0 wrapper logic out of the already-large tc_analyzer.py.
Imported by tc_analyzer (stage-0 matching) and by hooks/pre_tool_use.py
(source resolution + I/O).

Responsibilities (pure, no I/O except where noted):
  - scan_wrappers(text)  : C1 — find <!-- track-changes: from=... --> ...
                           <!-- /track-changes --> pairs in proposed text.
  - slice_fragment(...)  : slice a source file's text to a #L<a>-L<b> range
                           (or whole file for a bare from=PATH).
  - matches(...)         : C3 — compare a wrapped body against a resolved
                           source slice in strict | normalized | fuzzy modes.

Mode selection (C3 design decision): the OPENING comment may carry an
optional `mode=` field, e.g.
    <!-- track-changes: from=src.txt#L1-L4 mode=strict -->
When absent, the default is `normalized`. `fuzzy` is opt-in only.

Wrapper grammar (C1):
    <!-- track-changes: from=PATH[#L<a>-L<b>] [mode=MODE] -->
    ...body...
    <!-- /track-changes -->
  - `from=PATH` is required. PATH is relative to the project root.
  - `#L<a>-L<b>` fragment is optional; a bare from=PATH means whole-file.
  - PATH may contain spaces (e.g. "Freight Transport.txt"); it is taken up
    to the optional `#` fragment or a ` mode=` token or the closing ` -->`.
"""
import os
import re

# Opening / closing wrapper comments. The opening form is parsed in two
# steps: match the comment envelope, then parse the spec body, so a path
# with spaces is handled without a brittle single regex.
_OPEN_RE = re.compile(r'<!--\s*track-changes:\s*(?P<spec>.*?)\s*-->')
_CLOSE_RE = re.compile(r'<!--\s*/track-changes\s*-->')

# Within the opening spec: from=... and an optional mode=... token.
_MODE_RE = re.compile(r'\bmode=(strict|normalized|fuzzy)\b')
_FRAG_RE = re.compile(r'#L(\d+)-L(\d+)\s*$')

# Smart-quote / dash variants normalized to ASCII (C3 normalized mode).
_SMART_MAP = {
    '‘': "'", '’': "'", '‚': "'", '‛': "'",
    '“': '"', '”': '"', '„': '"', '‟': '"',
    '–': '-', '—': '-', '‒': '-', '―': '-',
    '…': '...', ' ': ' ',
}
_SMART_TRANS = {ord(k): v for k, v in _SMART_MAP.items()}

_WS_RUN_RE = re.compile(r'\s+')

DEFAULT_MODE = 'normalized'
FUZZY_THRESHOLD = 0.85  # Levenshtein ratio at/above which fuzzy mode matches.


class Wrapper(object):
    """One scanned wrapper pair.

    Attributes:
      line_start : 1-indexed line of the opening comment.
      line_end   : 1-indexed line of the closing comment.
      body_start_line : 1-indexed line of the first body line (line_start+1).
      from_spec  : the raw `from=` value incl. any #L fragment (the audit
                   `from:` value and the sources-map key).
      path       : the PATH portion of from_spec (no fragment).
      frag       : (a, b) line range tuple, or None for whole-file.
      mode       : 'strict' | 'normalized' | 'fuzzy'.
      body       : the wrapped body text (between the comments, exclusive of
                   the comment lines; trailing newline before close stripped).
    """
    __slots__ = ('line_start', 'line_end', 'body_start_line', 'from_spec',
                 'path', 'frag', 'mode', 'body')

    def __init__(self, line_start, line_end, body_start_line, from_spec,
                 path, frag, mode, body):
        self.line_start = line_start
        self.line_end = line_end
        self.body_start_line = body_start_line
        self.from_spec = from_spec
        self.path = path
        self.frag = frag
        self.mode = mode
        self.body = body


def _parse_spec(spec):
    """Parse the opening-comment spec into (from_spec, path, frag, mode).

    Returns None if there is no usable `from=` field.
    """
    mode = DEFAULT_MODE
    mm = _MODE_RE.search(spec)
    if mm:
        mode = mm.group(1)
        spec = (spec[:mm.start()] + spec[mm.end():]).strip()
    # The remainder should be `from=...`.
    idx = spec.find('from=')
    if idx == -1:
        return None
    rest = spec[idx + len('from='):].strip()
    if not rest:
        return None
    from_spec = rest
    # Split off an #L<a>-L<b> fragment if present.
    frag = None
    path = from_spec
    fm = _FRAG_RE.search(from_spec)
    if fm:
        a = int(fm.group(1))
        b = int(fm.group(2))
        frag = (a, b)
        path = from_spec[:fm.start()].rstrip()
    return (from_spec, path, frag, mode)


def scan_wrappers(text):
    """C1 — scan `text` for wrapper pairs.

    Returns a list of Wrapper objects in document order. Unbalanced or
    malformed (no `from=`) openings are skipped. Newlines are normalized to
    '\\n' by the caller before scanning; line numbers are 1-indexed.
    """
    wrappers = []
    pos = 0
    n = len(text)
    while pos < n:
        om = _OPEN_RE.search(text, pos)
        if not om:
            break
        parsed = _parse_spec(om.group('spec'))
        if parsed is None:
            pos = om.end()
            continue
        from_spec, path, frag, mode = parsed
        cm = _CLOSE_RE.search(text, om.end())
        if not cm:
            break  # no closing sentinel; nothing further to pair
        # Body is the text between the end of the opening comment and the
        # start of the closing comment, with one bounding newline trimmed on
        # each side so the body lines align with what the author wrote.
        body = text[om.end():cm.start()]
        if body.startswith('\n'):
            body = body[1:]
        if body.endswith('\n'):
            body = body[:-1]
        line_start = 1 + text.count('\n', 0, om.start())
        line_end = 1 + text.count('\n', 0, cm.start())
        wrappers.append(Wrapper(
            line_start=line_start,
            line_end=line_end,
            body_start_line=line_start + 1,
            from_spec=from_spec,
            path=path,
            frag=frag,
            mode=mode,
            body=body,
        ))
        pos = cm.end()
    return wrappers


# ---------------------------------------------------------------------------
# Unresolved-with-reason marker (C4/C5 shared mechanism).
#
# A `sources` map value can be:
#   - a resolved slice STRING  (verified path),
#   - None                     (generic unverified — unchanged v1 behavior),
#   - an unresolved-with-reason marker (this tagged dict) carrying a SPECIFIC,
#     actionable message (binary rejection C5 / not-found C4).
#
# The marker is a plain JSON-serializable dict so it survives the daemon
# socket round-trip (tc_daemon serializes `sources` to JSON). Both the daemon
# path and the in-process analyze(...) path produce the same block message.
# ---------------------------------------------------------------------------
_UNRESOLVED_TAG = '__tc_unresolved__'


def unresolved(reason):
    """Build an unresolved-with-reason source-map marker (JSON-serializable)."""
    return {_UNRESOLVED_TAG: True, 'reason': str(reason)}


def unresolved_reason(value):
    """If `value` is an unresolved-with-reason marker, return its reason
    string; otherwise return None. Tolerant of the JSON round-trip (a plain
    dict with the tag key)."""
    if isinstance(value, dict) and value.get(_UNRESOLVED_TAG):
        r = value.get('reason')
        return r if isinstance(r, str) else ''
    return None


# Text-source allowlist (C5 / FIX-3). Case-insensitive extension gate; only
# these formats are eligible to be imported from. A binary/non-text format
# (e.g. .docx, .pdf) is rejected without any read/decode attempt.
TEXT_SOURCE_EXTS = frozenset({'.md', '.markdown', '.qmd', '.rmd', '.tex', '.txt'})

# Bytes to sniff for a NUL byte / UTF-8 validity once the extension passes.
_SNIFF_BYTES = 8192


def is_text_source(path):
    """C5 (FIX-3) — is `path` an eligible text source for §0 import?

    Returns (ok, reason):
      - ok=True, reason='' when the extension is in TEXT_SOURCE_EXTS
        (case-insensitive) AND a small head of the file decodes as UTF-8 with
        no NUL byte (catches a mislabeled binary that wears a text extension).
      - ok=False, reason=<short phrase naming the rejected extension or the
        content problem> otherwise.

    Pure function: never raises. A missing/unreadable file is NOT this
    function's concern (extension gate passes, content sniff is skipped on an
    open error) — the caller's resolution step reports not-found.
    """
    ext = os.path.splitext(path or '')[1].lower()
    if ext not in TEXT_SOURCE_EXTS:
        shown = ext if ext else '(no extension)'
        return (False, 'is a binary/non-text format (%s)' % shown)
    # Extension passes; sniff a small head for a NUL byte / UTF-8 decode
    # failure (a mislabeled binary). An open error is left to the resolver.
    try:
        with open(path, 'rb') as f:
            head = f.read(_SNIFF_BYTES)
    except (IOError, OSError):
        return (True, '')
    if b'\x00' in head:
        return (False, 'contains a NUL byte (mislabeled binary)')
    try:
        head.decode('utf-8')
    except UnicodeDecodeError:
        # A multibyte char may straddle the sniff boundary; only flag when the
        # error is not at the very tail of the truncated head.
        try:
            head.decode('utf-8', errors='strict')
        except UnicodeDecodeError as e:
            if e.start < len(head) - 4:
                return (False, 'is not valid UTF-8 text (mislabeled binary)')
    return (True, '')


def nearest_tc_tracked_dir(file_path):
    """C4 — walk up from file_path's directory for a `.tc-tracked` marker.
    Return the first ancestor directory containing one, else None. Pure
    filesystem probe; never raises."""
    if not file_path:
        return None
    try:
        cur = os.path.dirname(os.path.abspath(file_path))
    except Exception:
        return None
    for _ in range(100):
        try:
            if os.path.isfile(os.path.join(cur, '.tc-tracked')):
                return cur
        except OSError:
            pass
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def resolution_candidates(file_path, find_project_root=None):
    """C4 — ordered candidate base directories for a RELATIVE from= path,
    de-duplicated by realpath, first existing wins (caller joins w.path):
      1. the directory of the edited file (dirname(file_path)),
      2. the nearest ancestor `.tc-tracked` marker directory,
      3. the git project root.
    `find_project_root` is an optional callable (pass tc_audit.find_project_root
    to avoid a circular import here)."""
    cands = []
    seen = set()

    def _add(d):
        if not d:
            return
        try:
            rp = os.path.realpath(d)
        except Exception:
            rp = d
        if rp in seen:
            return
        seen.add(rp)
        cands.append(d)

    if file_path:
        _add(os.path.dirname(os.path.abspath(file_path)))
    _add(nearest_tc_tracked_dir(file_path))
    if find_project_root is not None:
        try:
            _add(find_project_root(file_path))
        except Exception:
            pass
    return cands


def resolve_source_path(rel_or_abs_path, file_path, find_project_root=None):
    """C4 — resolve a from= PATH to an existing file.

    Returns (resolved_path or None, tried_dirs). An absolute path is honored
    as-is (returned if it exists, else (None, [])). For a relative path, the
    ordered candidate base dirs are probed; the first whose join is an existing
    file wins (realpath-normalized). `tried_dirs` lists the candidate base dirs
    probed (for the not-found did-you-mean message)."""
    if rel_or_abs_path and os.path.isabs(rel_or_abs_path):
        if os.path.isfile(rel_or_abs_path):
            return (os.path.realpath(rel_or_abs_path), [])
        return (None, [])
    tried = resolution_candidates(file_path, find_project_root)
    for base in tried:
        cand = os.path.join(base, rel_or_abs_path)
        try:
            if os.path.isfile(cand):
                return (os.path.realpath(cand), tried)
        except OSError:
            pass
    return (None, tried)


def slice_fragment(source_text, frag):
    """Return the source slice for a fragment.

    frag is None (whole file) or an (a, b) 1-indexed inclusive line range.
    Line endings are normalized to '\\n'. Out-of-range bounds are clamped;
    an inverted range yields ''.
    """
    text = source_text.replace('\r\n', '\n').replace('\r', '\n')
    if frag is None:
        return text
    a, b = frag
    lines = text.split('\n')
    if a < 1:
        a = 1
    if b > len(lines):
        b = len(lines)
    if b < a:
        return ''
    return '\n'.join(lines[a - 1:b])


def _normalize(s):
    """Normalized-mode canonical form: ASCII-fold smart punctuation,
    normalize EOL, collapse all whitespace runs (incl. newlines) to a single
    space, and strip. This tolerates paragraph reflow and indentation drift
    while still rejecting added/removed words."""
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    s = s.translate(_SMART_TRANS)
    s = _WS_RUN_RE.sub(' ', s)
    return s.strip()


def _levenshtein_ratio(a, b):
    """SequenceMatcher-free Levenshtein similarity ratio in [0, 1].
    Uses the classic (1 - dist/maxlen) formulation."""
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    # Two-row DP.
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        ca = a[i - 1]
        for j in range(1, lb + 1):
            cost = 0 if ca == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    dist = prev[lb]
    maxlen = la if la > lb else lb
    return 1.0 - (float(dist) / float(maxlen))


def matches(wrapped_body, source_slice, mode=DEFAULT_MODE):
    """C3 — does `wrapped_body` match `source_slice` under `mode`?

    Modes:
      strict     : byte-exact after EOL normalization only.
      normalized : (default) ASCII-fold + collapse whitespace + reflow.
      fuzzy      : normalized form, then Levenshtein ratio >= FUZZY_THRESHOLD.
    """
    if mode == 'strict':
        a = wrapped_body.replace('\r\n', '\n').replace('\r', '\n')
        b = source_slice.replace('\r\n', '\n').replace('\r', '\n')
        return a == b
    na = _normalize(wrapped_body)
    nb = _normalize(source_slice)
    if mode == 'fuzzy':
        if na == nb:
            return True
        return _levenshtein_ratio(na, nb) >= FUZZY_THRESHOLD
    # normalized (default)
    return na == nb
