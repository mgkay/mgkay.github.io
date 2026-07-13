"""tc_core.audit — PostToolUse audit-log analyzer (v3; narrowed from v2 tc_audit).

Diffs current marks vs the prior cache and appends introduced/resolved entries
to .tc-history.md. Mark extraction/classification now comes from tc_core.grammar
(single source of truth). v3 removes the §0 imported-region scan and §7
cross-file lineage scan (those features left track-changes); the result dict
retains empty `imported`/`lineage` keys for caller back-compat.

Public API:
    record(source_text, tool_name, ftype, abs_file_path, log_path,
           cache_path, rel_path_for_log) -> dict
      -> {'introduced': [...], 'resolved': [...], 'imported': [],
          'lineage': [], 'wrote_log': bool}
"""
import os
import re
import json
import datetime
import hashlib

from . import grammar


def _infer_decision(prior_mark, current_text):
    """Best-effort accept/reject inference by substring search."""
    t = prior_mark.get('type', '')
    old = prior_mark.get('old', '')
    new = prior_mark.get('new', '')
    in_text_new = bool(new) and new in current_text
    in_text_old = bool(old) and old in current_text
    if t == 'insertion':
        return 'accepted' if in_text_new else 'rejected'
    if t == 'deletion':
        return 'rejected' if in_text_old else 'accepted'
    if t == 'replacement':
        if in_text_new and not in_text_old:
            return 'accepted'
        if in_text_old and not in_text_new:
            return 'rejected'
        return 'ambiguous'
    return 'ambiguous'


def _fmt_str(s):
    """Quote a string for the log entry."""
    if not s:
        return '""'
    if '\n' in s or '"' in s or len(s) > 200:
        indented = '\n'.join('      ' + ln for ln in s.split('\n'))
        return '|\n' + indented
    return '"' + s.replace('\\', '\\\\') + '"'


# ---------------------------------------------------------------------------
# Path helpers (ports of lib/tc-history.sh).
# ---------------------------------------------------------------------------

def _state_dir(home=None):
    h = home or os.environ.get('HOME') or os.path.expanduser('~')
    d = os.path.join(h, '.claude', 'skills', 'track-changes', 'state')
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return None
    return d


def cache_path_for(abs_file, home=None):
    sd = _state_dir(home)
    if sd is None:
        return None
    cache_dir = os.path.join(sd, 'cache')
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError:
        return None
    sha = hashlib.sha1(abs_file.encode('utf-8')).hexdigest()
    return os.path.join(cache_dir, sha + '.marks')


def find_project_root(abs_file):
    """Walk up from abs_file's directory looking for .git/. Return the root or None."""
    if not abs_file:
        return None
    d = os.path.dirname(os.path.abspath(abs_file))
    for _ in range(100):
        if os.path.isdir(os.path.join(d, '.git')):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def log_path_for(abs_file, marker_path=None):
    """Project root -> .tc-history.md, fallback to marker dir, then file's own dir."""
    root = find_project_root(abs_file)
    if root:
        return os.path.join(root, '.tc-history.md')
    if marker_path:
        return os.path.join(os.path.dirname(marker_path), '.tc-history.md')
    return os.path.join(os.path.dirname(os.path.abspath(abs_file)), '.tc-history.md')


# ---------------------------------------------------------------------------
# Main entry point.
# ---------------------------------------------------------------------------

def record(source_text, tool_name, ftype, abs_file_path, log_path,
           cache_path, rel_path_for_log):
    """Diff current marks vs prior cache, append a log entry for introduced +
    resolved marks, then write the new cache state. Best-effort: I/O errors are
    swallowed; the user's workflow is never blocked."""
    result = {'introduced': [], 'resolved': [], 'imported': [],
              'lineage': [], 'wrote_log': False}
    current_marks = grammar.extract_marks(source_text, ftype)
    current_by_n = {m['N']: m for m in current_marks}

    prior_by_n = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                prior_data = json.load(f)
            prior_by_n = {m['N']: m for m in prior_data.get('marks', [])}
        except (IOError, ValueError):
            prior_by_n = {}

    introduced = [m for n, m in current_by_n.items() if n not in prior_by_n]
    resolved = [m for n, m in prior_by_n.items() if n not in current_by_n]
    result['introduced'] = introduced
    result['resolved'] = resolved

    def _write_cache():
        try:
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({'file': abs_file_path, 'marks': current_marks}, f)
        except IOError:
            pass

    if not introduced and not resolved:
        _write_cache()
        return result

    ts = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = [f"\n## {ts} -- {rel_path_for_log}  ({tool_name})"]
    if introduced:
        lines.append("introduced:")
        for m in introduced:
            lines.append(f"  - mark: {m['N']}")
            lines.append(f"    type: {m['type']}")
            lines.append(f"    line: {m['line']}")
            if m['type'] in ('deletion', 'replacement'):
                lines.append(f"    old: {_fmt_str(m.get('old', ''))}")
            if m['type'] in ('insertion', 'replacement'):
                lines.append(f"    new: {_fmt_str(m.get('new', ''))}")
    if resolved:
        lines.append("resolved:")
        for m in resolved:
            decision = _infer_decision(m, source_text)
            lines.append(f"  - mark: {m['N']}")
            lines.append(f"    was_type: {m.get('type', '?')}")
            lines.append(f"    decision: {decision}")
            if m.get('old', ''):
                lines.append(f"    was_old: {_fmt_str(m['old'])}")
            if m.get('new', ''):
                lines.append(f"    was_new: {_fmt_str(m['new'])}")
    entry = '\n'.join(lines) + '\n'

    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if not os.path.exists(log_path):
            header = (
                "# track-changes history\n"
                "#\n"
                "# Append-only audit log of AI-introduced and AI-introduced-then-resolved\n"
                "# marks for tracked files in this project. Each entry records one\n"
                "# Write/Edit/MultiEdit. Diffable + greppable + git-committed.\n"
                "#\n"
                "# Generated and maintained by the track-changes skill PostToolUse hook.\n"
                "# Do not edit by hand (append-only). To reset: delete this file.\n"
            )
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(header)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(entry)
        result['wrote_log'] = True
    except IOError:
        pass

    _write_cache()
    return result


# ---------------------------------------------------------------------------
# v9 source-validation: the durable `sourced:` evidence entry.
#
# Written by the track-changes PreToolUse hook after a gray `.tc-verbatim`
# excerpt verifies (normalized-exact containment) against its staged source and
# the accompanying green sourced region carries the expected tc-src. Mirrors
# verified-import's _write_import_audit shape exactly (timestamp, project-root
# relative path via find_project_root/log_path_for, _fmt_str quoting, header on
# first write, append-only, best-effort — never raises).
# ---------------------------------------------------------------------------

def write_sourced_entry(abs_file_path, rec, region_n, src_display,
                        excerpt, supports):
    """Append a `sourced:` audit entry to the project's `.tc-history.md`.

    Fields:
      - n:       the green sourced region's mark number (region_n)
      from:      the staged source path (rec['source_path'])
      locator:   the staged locator, or 'whole' when the source was whole-file
      citekey:   the staged @citekey (omitted when the source was a raw path)
      tc-src:    the canonical display value (srcstage.expected_src(rec))
      url/accessed/snapshot:  web sources only (9.2) — emitted when the staged
                 record carries a `url` (a file source omits all three). `url`
                 is the captured page URL, `accessed` the YYYY-MM-DD access
                 date, `snapshot` the snapshot file's basename. `from` then
                 names the LOCAL snapshot; `snapshot` is its basename so the
                 manifest can build a relative `sources/<file>` link. Read from
                 `rec` (rec['url']/rec['accessdate']/basename of
                 rec['source_path']) — NOT extra params — so the hook's existing
                 six-argument call needs no change.
      excerpt:   the verified gray-block body (the quoted source text)
      supports:  the green sourced region's body (the AI text it supports)

    Returns True on success, False on any failure (best-effort; never raises)."""
    try:
        import datetime
        abs_path = os.path.abspath(abs_file_path)
        log_path = log_path_for(abs_path)
        root = find_project_root(abs_path)
        if root:
            try:
                rel = os.path.relpath(abs_path, root).replace(os.sep, '/')
            except ValueError:
                rel = os.path.basename(abs_path)
        else:
            rel = os.path.basename(abs_path)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime(
            '%Y-%m-%dT%H:%M:%SZ')
        src = rec.get('source_path', '')
        locator = rec.get('locator') or 'whole'
        citekey = rec.get('citekey')
        url = rec.get('url')
        lines = [f"\n## {ts} -- {rel}  (source-validation)"]
        lines.append("sourced:")
        lines.append(f"  - n: {region_n}")
        lines.append(f"    from: {_fmt_str(src)}")
        lines.append(f"    locator: {locator}")
        if citekey:
            lines.append(f"    citekey: {citekey}")
        lines.append(f"    tc-src: {_fmt_str(src_display)}")
        if url:
            # Web source: URL + access date + snapshot basename (the snapshot is
            # `from`; its basename is the manifest's relative-link target).
            lines.append(f"    url: {_fmt_str(url)}")
            lines.append(f"    accessed: {rec.get('accessdate') or ''}")
            lines.append(f"    snapshot: {os.path.basename(src)}")
        lines.append(f"    excerpt: {_fmt_str(excerpt)}")
        lines.append(f"    supports: {_fmt_str(supports)}")
        entry = '\n'.join(lines) + '\n'
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if not os.path.exists(log_path):
            header = (
                "# track-changes history\n"
                "#\n"
                "# Append-only audit log of AI-introduced and AI-introduced-then-resolved\n"
                "# marks for tracked files in this project. Each entry records one\n"
                "# Write/Edit/MultiEdit, explicit /tc resolution, verified import, or\n"
                "# verified source excerpt. Diffable + greppable + git-committed.\n"
                "#\n"
                "# Generated and maintained by the track-changes / verified-import skills.\n"
                "# Do not edit by hand (append-only). To reset: delete this file.\n"
            )
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(header)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(entry)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# v9 source-validation: the durable `sourced:` evidence READER.
#
# The faithful inverse of write_sourced_entry (above): parse the project's
# `.tc-history.md` for `sourced:` entries whose header names `abs_file_path`
# (the project-root-relative key computed EXACTLY as the writer does), and
# return them as dicts for `/tc manifest`. The serialized shape is the writer's
# own output: a header line `## <ts> -- <rel>  (source-validation)`, then a
# `sourced:` section of `  - n: <N>` items with `    <key>: <value>` fields
# where `from`/`tc-src`/`excerpt`/`supports` are _fmt_str-quoted (short strings
# as `"…"` with `\`→`\\` escaping, longer / multiline strings as a `|` block of
# 6-space-indented lines) and `n`/`locator`/`citekey` are bare.
#
# Best-effort: a malformed item (non-integer `n`) is collected as
# {'malformed': True, ...} rather than raised, so the manifest can report a
# malformed COUNT. Missing log / no matching entries ⇒ []. A hard file read
# failure (OSError) PROPAGATES (the manifest maps it to its exit 2).
# ---------------------------------------------------------------------------

_SV_HEADER_RE = re.compile(
    r'^##\s+(?P<ts>\S+)\s+--\s+(?P<rel>.*?)\s+\((?P<kind>[^)]*)\)\s*$')
_SV_ITEM_RE = re.compile(r'^  - (?P<key>\w[\w-]*):[ ]?(?P<val>.*)$')
_SV_FIELD_RE = re.compile(r'^    (?P<key>\w[\w-]*):[ ]?(?P<val>.*)$')


def _unfmt_str(tok):
    """Inverse of _fmt_str for an INLINE value token (the text after `key: `).

    _fmt_str emits `""` for empty, and otherwise EITHER `"…"` (a short,
    single-line string with `\\`→`\\\\` escaping and never a literal quote or
    newline) OR the `|` block form. This undoes the inline cases; the block form
    is handled by the line walker (a bare `|` token triggers block collection
    there, so it never reaches here)."""
    if tok == '""':
        return ''
    if len(tok) >= 2 and tok[0] == '"' and tok[-1] == '"':
        return tok[1:-1].replace('\\\\', '\\')
    return tok


def _sv_consume_value(valtok, lines, j):
    """Resolve a field/item value that may be an inline token or a `|` block.

    `valtok` is the text after `key: `; `lines` is the entry body; `j` is the
    index of the line AFTER the key line. Returns (value, next_index). A `|`
    token collects the following 6-space-indented lines (the _fmt_str block
    form), stripping the 6-space prefix; an internal blank line is kept only
    when a further indented line follows before the block ends."""
    if valtok == '|':
        block = []
        n = len(lines)
        while j < n:
            ln = lines[j]
            if ln.startswith('      '):
                block.append(ln[6:])
                j += 1
            elif ln.strip() == '':
                k = j + 1
                cont = False
                while k < n:
                    if lines[k].strip() == '':
                        k += 1
                        continue
                    cont = lines[k].startswith('      ')
                    break
                if cont:
                    block.append('')
                    j += 1
                else:
                    break
            else:
                break
        return ('\n'.join(block), j)
    return (_unfmt_str(valtok), j)


def _sv_finalize(raw, ts):
    """Convert a raw key→value item dict into a result dict. A non-integer `n`
    yields a {'malformed': True} marker (so the manifest can count it)."""
    try:
        n_int = int(str(raw.get('n')).strip())
    except (TypeError, ValueError):
        return {'malformed': True, 'timestamp': ts}
    return {
        'n': n_int,
        'from': raw.get('from', ''),
        'locator': (raw.get('locator', '') or '').strip(),
        'citekey': (raw.get('citekey') or None),
        'tc_src': raw.get('tc-src', ''),
        # Web-source fields (9.2): present only when the entry carried a `url`;
        # None/'' for a file source so callers can branch on `url`.
        'url': (raw.get('url') or None),
        'accessed': (raw.get('accessed', '') or '').strip(),
        'snapshot': (raw.get('snapshot', '') or '').strip(),
        'excerpt': raw.get('excerpt', ''),
        'supports': raw.get('supports', ''),
        'timestamp': ts,
    }


def _sv_parse_entry(body_lines, ts):
    """Parse the `sourced:` items in one entry's body (the lines after its
    header). Returns a list of finalized dicts (good or malformed), in order."""
    start = None
    for idx, ln in enumerate(body_lines):
        if ln.strip() == 'sourced:' and not ln.startswith(' '):
            start = idx + 1
            break
    if start is None:
        return []
    items = []
    raw = None
    j = start
    n = len(body_lines)
    while j < n:
        ln = body_lines[j]
        mi = _SV_ITEM_RE.match(ln)
        if mi:
            if raw is not None:
                items.append(_sv_finalize(raw, ts))
            raw = {}
            val, j = _sv_consume_value(mi.group('val'), body_lines, j + 1)
            raw[mi.group('key')] = val
            continue
        mf = _SV_FIELD_RE.match(ln)
        if mf and raw is not None:
            val, j = _sv_consume_value(mf.group('val'), body_lines, j + 1)
            raw[mf.group('key')] = val
            continue
        if ln.strip() == '':
            j += 1
            continue
        # A non-indented, non-blank line ends the `sourced:` section (e.g. a
        # sibling `resolved:` block); indented noise is skipped.
        if not ln.startswith(' '):
            break
        j += 1
    if raw is not None:
        items.append(_sv_finalize(raw, ts))
    return items


def read_sourced_entries(abs_file_path):
    """Read the project `.tc-history.md` for `sourced:` audit entries naming
    `abs_file_path`. Return a list (FILE ORDER) of dicts, each either:

      good:      {n:int, from:str, locator:str, citekey:str|None, tc_src:str,
                  url:str|None, accessed:str, snapshot:str, excerpt:str,
                  supports:str, timestamp:str}
                  (url is None + accessed/snapshot '' for a file source)
      malformed: {'malformed': True, 'timestamp': str}

    `[]` when the log is absent or has no matching sourced entries. A hard read
    failure (OSError) propagates (the caller maps it to a usage/parse exit)."""
    abs_path = os.path.abspath(abs_file_path)
    log_path = log_path_for(abs_path)
    if not log_path or not os.path.exists(log_path):
        return []
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()

    # This doc's project-root-relative key, computed EXACTLY as the writer does.
    root = find_project_root(abs_path)
    if root:
        try:
            my_rel = os.path.relpath(abs_path, root).replace(os.sep, '/')
        except ValueError:
            my_rel = os.path.basename(abs_path)
    else:
        my_rel = os.path.basename(abs_path)

    lines = text.split('\n')
    # Split into entry chunks keyed by their `## <ts> -- <rel> (<kind>)` header.
    entries = []
    cur = None
    for line in lines:
        m = _SV_HEADER_RE.match(line)
        if m:
            cur = {'ts': m.group('ts'), 'rel': m.group('rel'), 'body': []}
            entries.append(cur)
        elif cur is not None:
            cur['body'].append(line)

    results = []
    for ent in entries:
        if ent['rel'] != my_rel:
            continue
        results.extend(_sv_parse_entry(ent['body'], ent['ts']))
    return results
