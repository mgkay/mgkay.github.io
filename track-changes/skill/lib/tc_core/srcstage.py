"""tc_core.srcstage — pending-source staging, citekey resolution, and the
source-verification sentinel (v9, source-validation discipline).

Data-only engine for the `/tc source` flow. Three concerns, all pure state /
filesystem helpers — no sys.exit, no argparse, no printing:

1. Pending-source records (transient). `/tc source` resolves + slices a source
   and stages a one-shot, target-keyed record; the track-changes PreToolUse
   hook loads it, verifies the proposed gray `.tc-verbatim` block is contained
   in the staged slice, and clears it on a verified landing. The lifecycle is
   the verified-import pending-import lifecycle exactly (target-keyed sha1
   state file, TTL, fail-closed re-read, crash-recovery sweep). These records
   are TRANSIENT scaffolding — the DURABLE evidence is the `sourced:` audit
   entry the hook writes to `.tc-history.md` (see tc_core.audit), NOT anything
   this module persists.

2. Citekey resolution (resolve_citekey) — map a BibTeX-style `@citekey` +
   locator to a concrete source file path, so `/tc source @daskin2013 p.114`
   works. Fail-closed: unresolvable keys return (None, <description>) naming
   both resolution mechanisms for the CLI's error message.

3. The verification sentinel (source-ok) — one-shot and sha-bound exactly like
   tc_core.exempt. Written by the verification path AFTER byte-containment
   passes, keyed to the target doc and the sha256 of the NORMALIZED gray text;
   consumed by the SAME write in tc_analyzer. A stale sentinel cannot authorize
   different bytes (sha binding) and cannot be replayed (one-shot unlink on any
   read).

os.path (not pathlib) throughout, mirroring the rest of the package.
"""
import os
import re
import json
import time
import hashlib

from .sourcetext import normalize


# ---------------------------------------------------------------------------
# State-tree helpers. All srcstage state lives under the same track-changes
# state root as the exemption sentinels and pending-imports, one subdir over,
# so a single install owns it.
#   state/source/     — transient pending-source records (TTL 600 s)
#   state/source-ok/  — one-shot verification sentinels (TTL 120 s)
# ---------------------------------------------------------------------------

_PENDING_TTL_DEFAULT = 600   # seconds — wide staging window (resolve + convert)
_SENTINEL_TTL_DEFAULT = 120  # seconds — mirrors tc_core.exempt


def _state_dir(sub):
    home = os.environ.get('HOME') or os.path.expanduser('~')
    d = os.path.join(home, '.claude', 'skills', 'track-changes', 'state', sub)
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return None
    return d


def _key(target_path):
    return hashlib.sha1(
        os.path.abspath(target_path).encode('utf-8')).hexdigest()


def _safe_unlink(p):
    try:
        os.remove(p)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Pending-source records — mirrors vi_verify's pending-import lifecycle.
# ---------------------------------------------------------------------------

def _pending_dir():
    return _state_dir('source')


def _pending_path(target_path):
    d = _pending_dir()
    if not d:
        return None
    return os.path.join(d, _key(target_path) + '.json')


def stage(target_path, source_path, locator_str=None, citekey=None,
          ttl=_PENDING_TTL_DEFAULT):
    """Write a one-shot pending-source record keyed on the target file.

    Record: {target, source_path, locator, citekey, expires}
      - target      : abspath of the tracked document being written
      - source_path : resolved abspath of the source file
      - locator     : the verbatim locator string ('' when whole-file)
      - citekey     : the `@key` used, or None when the source was a raw path
      - expires     : wall-clock deadline (time.time() + ttl)

    Returns the record on success, None on I/O failure."""
    p = _pending_path(target_path)
    if not p:
        return None
    rec = {
        'target': os.path.abspath(target_path),
        'source_path': os.path.abspath(source_path),
        'locator': locator_str or '',
        'citekey': citekey,
        'expires': time.time() + ttl,
    }
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(rec, f)
        return rec
    except OSError:
        return None


def load(target_path):
    """Return the live pending-source record for `target_path`, or None.

    Mirrors vi_verify.load_pending exactly: returns None (and unlinks) when the
    record is missing, unparseable, for a different path, or expired. A live
    record for a foreign path is not unlinked (only an expired record is);
    since files are keyed by sha1(target) a foreign match is a collision /
    tampering edge, not the normal path. Does NOT consume a live record — the
    hook clears it explicitly after writing the verification sentinel."""
    p = _pending_path(target_path)
    if not p or not os.path.isfile(p):
        return None
    try:
        with open(p, 'r', encoding='utf-8') as f:
            rec = json.load(f)
    except (OSError, ValueError):
        _safe_unlink(p)
        return None
    try:
        same = (os.path.abspath(rec.get('target', ''))
                == os.path.abspath(target_path))
        live = float(rec.get('expires', 0)) >= time.time()
    except (TypeError, ValueError):
        _safe_unlink(p)
        return None
    if not same or not live:
        if not live:
            _safe_unlink(p)
        return None
    return rec


def clear(target_path):
    """Delete the pending-source record for `target_path` (one-shot consume)."""
    p = _pending_path(target_path)
    if p:
        _safe_unlink(p)


def expected_src(rec):
    """The canonical `tc-src` display value a staged record requires on its
    green sourced region. Single source of truth (the `/tc source` CLI prints
    the SAME value so the author can copy it verbatim into the region opener):

      @citekey locator   when the record was citekey-staged WITH a locator
      @citekey           when citekey-staged with no locator (whole source)
      basename#locator   when path-staged WITH a locator
      basename           when path-staged whole-file

    `rec` is a pending-source record (see stage): keys `citekey`, `locator`,
    `source_path`."""
    citekey = rec.get('citekey')
    locator = (rec.get('locator') or '').strip()
    if citekey:
        if locator:
            return '@%s %s' % (citekey, locator)
        return '@%s' % citekey
    base = os.path.basename(rec.get('source_path') or '')
    if locator:
        return '%s#%s' % (base, locator)
    return base


def sweep():
    """Remove expired pending-source records (crash recovery)."""
    d = _pending_dir()
    if not d:
        return
    now = time.time()
    try:
        names = os.listdir(d)
    except OSError:
        return
    for name in names:
        if not name.endswith('.json'):
            continue
        p = os.path.join(d, name)
        try:
            with open(p, 'r', encoding='utf-8') as f:
                rec = json.load(f)
            if float(rec.get('expires', 0)) < now:
                _safe_unlink(p)
        except (OSError, ValueError):
            _safe_unlink(p)


# ---------------------------------------------------------------------------
# Citekey resolution — map an `@citekey` to a concrete source file.
#
# Search order (MakePlan §4b F5):
#   a. .bib files the document ITSELF references (\bibliography /
#      \addbibresource / Quarto `bibliography:`), relative to the doc dir;
#   b. else/also *.bib in the doc's directory, then in the git project root.
#   For each .bib in that order, the entry whose key matches EXACTLY (case-
#   sensitive) is read; its `file`/`localfile` field (JabRef forms) yields the
#   path; first existing file wins.
#   c. Fallback: the first `.tc-sources.json` walking up from the doc dir; a
#      JSON object citekey -> path, paths relative to the map file's dir.
#   d. Nothing → (None, tried) with a human-readable summary naming both
#      mechanisms.
# ---------------------------------------------------------------------------

def _git_root(start_dir):
    """Walk up from start_dir for a `.git` directory; return the root or None.
    Mirrors vi_verify._git_root."""
    if not start_dir:
        return None
    d = os.path.abspath(start_dir)
    for _ in range(100):
        if os.path.isdir(os.path.join(d, '.git')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def _read_text(path):
    """Read a text file UTF-8 with errors='replace'; '' on any failure."""
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    except (OSError, ValueError):
        return ''


_BIBLIOGRAPHY_RE = re.compile(r'\\bibliography\s*\{([^}]*)\}')
_ADDBIBRESOURCE_RE = re.compile(
    r'\\addbibresource\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}')


def _with_bib_ext(name):
    name = name.strip()
    if not name:
        return ''
    if not name.lower().endswith('.bib'):
        name = name + '.bib'
    return name


def _yaml_frontmatter(text):
    """Return the YAML frontmatter block (the lines between the leading `---`
    fences) as a list of lines, or [] when there is none."""
    lines = text.split('\n')
    if not lines or lines[0].strip() != '---':
        return []
    out = []
    for line in lines[1:]:
        if line.strip() in ('---', '...'):
            break
        out.append(line)
    return out


def _quarto_bibliographies(text):
    """Extract bibliography file names from Quarto YAML frontmatter.

    Handles the single-value form (`bibliography: refs.bib`), the block-list
    form (`bibliography:` followed by `  - refs.bib` lines), and the inline
    flow-list form (`bibliography: [a.bib, b.bib]`)."""
    fm = _yaml_frontmatter(text)
    names = []
    i = 0
    while i < len(fm):
        line = fm[i]
        stripped = line.strip()
        if stripped.startswith('bibliography:'):
            rest = stripped[len('bibliography:'):].strip()
            if rest:
                # inline flow list or single scalar
                if rest.startswith('[') and rest.endswith(']'):
                    for item in rest[1:-1].split(','):
                        v = item.strip().strip('\'"')
                        if v:
                            names.append(v)
                else:
                    names.append(rest.strip('\'"'))
            else:
                # block list: subsequent `- item` lines
                j = i + 1
                while j < len(fm):
                    ls = fm[j].strip()
                    if ls.startswith('- '):
                        v = ls[2:].strip().strip('\'"')
                        if v:
                            names.append(v)
                        j += 1
                    elif ls == '' or ls == '-':
                        j += 1
                    else:
                        break
                i = j
                continue
        i += 1
    return names


def _doc_referenced_bibs(doc_path):
    """Ordered list of .bib abspaths the document itself references
    (\\bibliography, \\addbibresource, Quarto `bibliography:`), relative to the
    doc's directory. Non-existent references are dropped."""
    text = _read_text(doc_path)
    doc_dir = os.path.dirname(os.path.abspath(doc_path))
    names = []
    for m in _BIBLIOGRAPHY_RE.finditer(text):
        for part in m.group(1).split(','):
            nm = _with_bib_ext(part)
            if nm:
                names.append(nm)
    for m in _ADDBIBRESOURCE_RE.finditer(text):
        nm = _with_bib_ext(m.group(1))
        if nm:
            names.append(nm)
    for nm in _quarto_bibliographies(text):
        names.append(_with_bib_ext(nm))

    out = []
    for nm in names:
        if os.path.isabs(nm):
            cand = nm
        else:
            cand = os.path.join(doc_dir, nm)
        if os.path.isfile(cand):
            out.append(os.path.abspath(cand))
    return out


def _bibs_in_dir(d):
    """Sorted list of *.bib abspaths directly in directory `d`."""
    out = []
    try:
        names = os.listdir(d)
    except OSError:
        return out
    for name in sorted(names):
        if name.lower().endswith('.bib'):
            full = os.path.join(d, name)
            if os.path.isfile(full):
                out.append(os.path.abspath(full))
    return out


def _ordered_bib_files(doc_path):
    """The full ordered, de-duplicated (by abspath) list of .bib files to
    search: doc-referenced first, then *.bib in the doc dir, then *.bib in the
    git project root."""
    doc_dir = os.path.dirname(os.path.abspath(doc_path))
    ordered = []
    seen = set()

    def _add(p):
        ap = os.path.abspath(p)
        if ap in seen:
            return
        seen.add(ap)
        ordered.append(ap)

    for p in _doc_referenced_bibs(doc_path):
        _add(p)
    for p in _bibs_in_dir(doc_dir):
        _add(p)
    root = _git_root(doc_dir)
    if root:
        for p in _bibs_in_dir(root):
            _add(p)
    return ordered


def _find_entry_field_body(bibtext, key):
    """Return the field body (everything after the key + comma, up to the
    entry's matching close brace) for the entry whose key EXACTLY equals `key`
    (case-sensitive), or None. Brace-balanced from the entry-open brace."""
    for m in re.finditer(r'@\w+\s*\{', bibtext):
        open_pos = m.end() - 1  # index of the entry '{'
        depth = 0
        close_pos = None
        i = open_pos
        n = len(bibtext)
        while i < n:
            c = bibtext[i]
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    close_pos = i
                    break
            i += 1
        if close_pos is None:
            continue
        body = bibtext[open_pos + 1:close_pos]
        comma = body.find(',')
        if comma == -1:
            continue
        entry_key = body[:comma].strip()
        if entry_key == key:
            return body[comma + 1:]
    return None


_FILE_FIELD_RE = re.compile(r'\b(?:local)?file\s*=\s*', re.IGNORECASE)


def _extract_field_value(field_body):
    """Return the raw value of the first `file`/`localfile` field in a BibTeX
    entry body, or None. The value may be `{...}` (brace-balanced), `"..."`
    (quote-delimited), or bare (up to the next comma / newline)."""
    m = _FILE_FIELD_RE.search(field_body)
    if not m:
        return None
    i = m.end()
    n = len(field_body)
    while i < n and field_body[i] in ' \t':
        i += 1
    if i >= n:
        return None
    c = field_body[i]
    if c == '{':
        depth = 0
        start = i + 1
        j = i
        while j < n:
            ch = field_body[j]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return field_body[start:j]
            j += 1
        return field_body[start:]
    if c == '"':
        j = field_body.find('"', i + 1)
        if j == -1:
            return field_body[i + 1:]
        return field_body[i + 1:j]
    # bare value: up to the next comma or newline
    j = i
    while j < n and field_body[j] not in ',\n':
        j += 1
    return field_body[i:j].strip()


def _jabref_path(spec):
    """Extract the path segment from one JabRef file-field value.

    Forms: `desc:path:type` / `:path:type` / `path:type` / bare `path`. A
    leading Windows drive letter (`C:`) must not be split, so colon-separated
    segments whose predecessor is a single letter and whose text starts with a
    slash are rejoined (`C:/x.pdf`)."""
    spec = spec.strip()
    if not spec:
        return ''
    parts = spec.split(':')
    # Rejoin drive-letter splits: a single-letter part followed by a part that
    # begins with a path separator is a Windows drive prefix.
    merged = []
    i = 0
    while i < len(parts):
        p = parts[i]
        if (len(p) == 1 and p.isalpha() and i + 1 < len(parts)
                and parts[i + 1][:1] in ('/', '\\')):
            merged.append(p + ':' + parts[i + 1])
            i += 2
        else:
            merged.append(p)
            i += 1
    if len(merged) == 1:
        return merged[0].strip()
    if len(merged) == 2:
        # path:type
        return merged[0].strip()
    # desc:path:type (desc may be empty, as in `:path:type`)
    return merged[1].strip()


def _resolve_file_field(field_value, bib_dir):
    """Resolve a (possibly `;`-separated) JabRef file-field value to the first
    existing file, relative to `bib_dir`. Returns an abspath or None."""
    if not field_value:
        return None
    for spec in field_value.split(';'):
        path = _jabref_path(spec)
        if not path:
            continue
        if os.path.isabs(path):
            cand = path
        else:
            cand = os.path.join(bib_dir, path)
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


def _find_sources_map(doc_path):
    """Walk up from the doc's directory (to the git root, else the filesystem
    root; max 100 levels) for the first `.tc-sources.json`. Returns its abspath
    or None."""
    cur = os.path.dirname(os.path.abspath(doc_path))
    root = _git_root(cur)
    for _ in range(100):
        cand = os.path.join(cur, '.tc-sources.json')
        if os.path.isfile(cand):
            return os.path.abspath(cand)
        if root and os.path.abspath(cur) == os.path.abspath(root):
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _resolve_via_map(citekey, doc_path):
    """Resolve `citekey` via the nearest `.tc-sources.json`. Returns
    (path or None, map_path or None) — map_path is the map that was consulted
    (for the tried-description), None when no map was found."""
    map_path = _find_sources_map(doc_path)
    if not map_path:
        return (None, None)
    try:
        with open(map_path, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return (None, map_path)
    if not isinstance(data, dict):
        return (None, map_path)
    val = data.get(citekey)
    if not isinstance(val, str) or not val:
        return (None, map_path)
    map_dir = os.path.dirname(map_path)
    cand = val if os.path.isabs(val) else os.path.join(map_dir, val)
    if os.path.isfile(cand):
        return (os.path.abspath(cand), map_path)
    return (None, map_path)


def resolve_citekey(citekey, doc_path):
    """Resolve `@citekey` to a source file path relative to `doc_path`.

    Returns (path or None, tried_description). On success `path` is an abspath
    to an existing file. On failure `path` is None and `tried_description` is a
    human-readable summary naming BOTH resolution mechanisms (the .bib files
    scanned and the `.tc-sources.json` map consulted or its absence), for the
    caller's fail-closed error message. Keys match case-sensitively."""
    bib_files = _ordered_bib_files(doc_path)
    for bib in bib_files:
        text = _read_text(bib)
        field_body = _find_entry_field_body(text, citekey)
        if field_body is None:
            continue
        field_value = _extract_field_value(field_body)
        if not field_value:
            continue
        resolved = _resolve_file_field(field_value, os.path.dirname(bib))
        if resolved:
            return (resolved, '')

    # Fallback: .tc-sources.json map.
    mapped, map_path = _resolve_via_map(citekey, doc_path)
    if mapped:
        return (mapped, '')

    # Nothing resolved — build the two-mechanism tried summary.
    if bib_files:
        bib_desc = '.bib files scanned: %s' % ', '.join(bib_files)
    else:
        bib_desc = '.bib files scanned: none found'
    if map_path:
        map_desc = '.tc-sources.json consulted: %s (no `%s` entry)' % (
            map_path, citekey)
    else:
        map_desc = ('.tc-sources.json: none found walking up from %s'
                    % os.path.dirname(os.path.abspath(doc_path)))
    tried = ("could not resolve citekey '%s'. %s. %s."
             % (citekey, bib_desc, map_desc))
    return (None, tried)


# ---------------------------------------------------------------------------
# Verification sentinel (source-ok) — one-shot, sha-bound, exactly like
# tc_core.exempt. Written by the verification path after byte-containment
# passes; consumed by the same write in tc_analyzer.
# ---------------------------------------------------------------------------

def gray_sha_of(text):
    """sha256 hexdigest of the NORMALIZED gray text — the sentinel payload.

    Coupling the sha to sourcetext.normalize (not the raw bytes) means the
    sentinel authorizes the gray text's CONTENT, so incidental whitespace /
    ligature differences between staging and the landed block do not break the
    one-shot match, while a genuine content change (a different excerpt) yields
    a different sha and is refused."""
    return hashlib.sha256(normalize(text).encode('utf-8')).hexdigest()


def _sentinel_dir():
    return _state_dir('source-ok')


def _sentinel_path(target_path):
    d = _sentinel_dir()
    if not d:
        return None
    return os.path.join(d, _key(target_path) + '.json')


def sentinel_write(target_path, gray_sha, ttl=_SENTINEL_TTL_DEFAULT):
    """Record a one-shot verification sentinel for (target_path, gray_sha).

    `gray_sha` is a sha256 hexdigest of the normalized gray text (compute via
    gray_sha_of). Returns True on success, False on I/O failure."""
    p = _sentinel_path(target_path)
    if not p:
        return False
    rec = {'target': os.path.abspath(target_path),
           'gray_sha': gray_sha,
           'expires': time.time() + ttl}
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(rec, f)
        return True
    except OSError:
        return False


def sentinel_consume(target_path, gray_sha):
    """One-shot check: True iff a live sentinel matches (target, gray_sha).

    Deletes the sentinel on ANY read (match, mismatch, or expiry), so it is
    strictly single-use: a sentinel written for gray text A cannot authorize
    gray text B (sha mismatch → False, file gone), and a replay of the same
    payload after a successful consume finds no file and returns False. This is
    tc_core.exempt.consume's contract exactly, keyed on the normalized-gray
    sha instead of the whole-file content sha."""
    p = _sentinel_path(target_path)
    if not p or not os.path.isfile(p):
        return False
    try:
        with open(p, 'r', encoding='utf-8') as f:
            rec = json.load(f)
    except (OSError, ValueError):
        _safe_unlink(p)
        return False
    ok = (rec.get('gray_sha') == gray_sha
          and os.path.abspath(rec.get('target', '')) == os.path.abspath(target_path)
          and float(rec.get('expires', 0)) >= time.time())
    _safe_unlink(p)
    return ok


def sentinel_peek(target_path):
    """Return the live sentinel record for `target_path` without consuming it
    (diagnostics only). Returns None when missing, corrupt, or expired; never
    unlinks."""
    p = _sentinel_path(target_path)
    if not p or not os.path.isfile(p):
        return None
    try:
        with open(p, 'r', encoding='utf-8') as f:
            rec = json.load(f)
    except (OSError, ValueError):
        return None
    try:
        if float(rec.get('expires', 0)) < time.time():
            return None
    except (TypeError, ValueError):
        return None
    return rec


def sentinel_sweep():
    """Remove expired verification sentinels (crash recovery)."""
    d = _sentinel_dir()
    if not d:
        return
    now = time.time()
    try:
        names = os.listdir(d)
    except OSError:
        return
    for name in names:
        if not name.endswith('.json'):
            continue
        p = os.path.join(d, name)
        try:
            with open(p, 'r', encoding='utf-8') as f:
                rec = json.load(f)
            if float(rec.get('expires', 0)) < now:
                _safe_unlink(p)
        except (OSError, ValueError):
            _safe_unlink(p)
