"""tc_manifest — the `/tc manifest` source-manifest generator (v9).

Regenerate `<doc-dir>/validation/<doc-stem>.sources.md` for a tracked document
from the DURABLE `sourced:` evidence in the project's `.tc-history.md` (E1: the
audit log is the evidence home, so a manifest survives deletion of the transient
gray `.tc-verbatim` scaffolding and of the green region itself). The manifest is
regenerated WHOLE-FILE and DETERMINISTIC: no generation timestamp, live sections
ordered by region N ascending, removed entries in audit (file) order, so a
re-run over the same log is byte-identical.

Each `sourced:` audit entry whose region number N is still a LIVE `sourced`
region in the document becomes a `## Region [N] — <tc-src>` section (source
link + locator, excerpt blockquote, supported-text blockquote, back-link). An
entry whose region no longer exists in the document is REPORTED — never dropped
— under `## Resolved/removed regions`.

Usage:
    tc_manifest.py [<doc>]

  No <doc> ⇒ the working-file default (the most-recently-modified tracked-active
  md/qmd/tex under the project scope), resolved by the vi_verify-mirrored
  helpers below (copied, not imported — verified-import may be absent).

Exit codes:
    0  manifest written (path + counts printed to stdout)
    1  no sourced-region evidence recorded for the doc (nothing written)
    2  usage / doc missing / audit log unreadable
(Python-missing is exit 2, handled by the tc-cli.sh shell layer.)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tc_core import audit, grammar, sourcetext  # noqa: E402


_USAGE = 'usage: /tc manifest [<doc>]'


def _err(msg):
    sys.stderr.write('tc manifest: ' + msg + '\n')


def _emit(text):
    """UTF-8 stdout emission (mirrors tc_source._emit / the hooks' _emit).

    The reported path and counts are ASCII, but keep the same encoded-bytes
    write so a Windows console codec (cp1252) never mangles or crashes on a
    non-ASCII path component."""
    line = text if text.endswith('\n') else text + '\n'
    try:
        sys.stdout.buffer.write(line.encode('utf-8'))
        sys.stdout.buffer.flush()
    except (AttributeError, ValueError):
        sys.stdout.write(line)


# ---------------------------------------------------------------------------
# Working-file resolution. COPIED from tc_source.py (which itself copies
# verified-import's vi_verify.py, mirroring tc-cli.sh's tc_resolve_working_file)
# — verified-import may be absent, so track-changes carries its own copy. Keep
# these in sync with tc_source / vi_verify if that resolution logic changes.
# ---------------------------------------------------------------------------

# 'validation' holds generated evidence (manifests, annotated twins) - never a
# working-file candidate.
_PRUNE_DIRS = {'.git', 'node_modules', 'validation'}
_TRACK_EXTS = {'.md', '.qmd', '.tex'}


def nearest_tc_tracked_dir(file_path):
    """Walk up from file_path's directory for a `.tc-tracked` marker. Return
    the first ancestor directory containing one, else None. Mirrors
    tc_source.nearest_tc_tracked_dir."""
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


def _git_root(start_dir):
    """Walk up from start_dir for a `.git` directory; return the root or None.
    Mirrors tc_source._git_root."""
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


def _yaml_override(path):
    """Return 'on'/'off'/'' from per-file YAML frontmatter (md/qmd) or magic
    comment (tex). Mirrors tc_source._yaml_override."""
    ext = os.path.splitext(path)[1].lower()
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            head = [next(f, '') for _ in range(50)]
    except (OSError, StopIteration):
        return ''
    if ext == '.tex':
        for line in head[:10]:
            ls = line.strip()
            if '%' in ls and 'track-changes:' in ls:
                if 'true' in ls:
                    return 'on'
                if 'false' in ls:
                    return 'off'
        return ''
    if not head or head[0].strip() != '---':
        return ''
    for line in head[1:]:
        if line.strip() == '---':
            break
        ls = line.strip()
        if ls.startswith('track-changes:'):
            if 'true' in ls:
                return 'on'
            if 'false' in ls:
                return 'off'
    return ''


def _is_tracked(path):
    """Lightweight activation probe for working-file selection. Mirrors
    tc_source._is_tracked."""
    base = os.path.basename(path)
    if base.startswith('.'):
        return _yaml_override(path) == 'on'
    ov = _yaml_override(path)
    if ov == 'on':
        return True
    if ov == 'off':
        return False
    return nearest_tc_tracked_dir(path) is not None


def resolve_working_file():
    """Most-recently-modified tracked-active md/qmd/tex under the project scope
    (git root of CWD, else CWD). Mirrors tc_source.resolve_working_file.
    Returns the path or None."""
    scope = _git_root(os.getcwd()) or os.getcwd()
    best = None
    best_mtime = -1.0
    for root, dirs, files in os.walk(scope):
        dirs[:] = [d for d in dirs
                   if d not in _PRUNE_DIRS and not d.startswith('.')]
        for fn in files:
            if os.path.splitext(fn)[1].lower() not in _TRACK_EXTS:
                continue
            full = os.path.join(root, fn)
            if not _is_tracked(full):
                continue
            try:
                mt = os.path.getmtime(full)
            except OSError:
                continue
            if mt > best_mtime:
                best_mtime = mt
                best = full
    return best


def _ftype_of(path):
    """Target format by extension (mirrors tc_source._ftype_of): 'tex' | 'qmd'
    | 'md' (the default)."""
    ext = os.path.splitext(path or '')[1].lower()
    if ext == '.tex':
        return 'tex'
    if ext == '.qmd':
        return 'qmd'
    return 'md'


def _strip_at(arg):
    """Strip a single leading `@` — Claude's file-reference prefix — from the
    doc argument (mirrors tc_source._strip_at)."""
    if arg and arg.startswith('@'):
        return arg[1:]
    return arg


# ---------------------------------------------------------------------------
# Manifest rendering helpers.
# ---------------------------------------------------------------------------

def _fwd(path):
    """A path with forward slashes (POSIX-style manifest links on all OSes)."""
    return path.replace(os.sep, '/').replace('\\', '/')


def _rel_link(target_path, base_dir):
    """os.path.relpath(target_path, base_dir), forward-slashed. Falls back to a
    forward-slashed absolute path when relpath is impossible (a different
    Windows drive raises ValueError)."""
    try:
        return _fwd(os.path.relpath(target_path, base_dir))
    except ValueError:
        return _fwd(os.path.abspath(target_path))


def _page_anchor(locator):
    """`#page=<a>` for a PDF page locator (first page), else ''. Uses the shared
    sourcetext.parse_locator so the recognized forms match staging exactly."""
    if not locator or locator == 'whole':
        return ''
    try:
        kind, rng = sourcetext.parse_locator(locator)
    except ValueError:
        return ''
    if kind == 'pages' and rng:
        return '#page=%d' % rng[0]
    return ''


def _blockquote(text):
    """Markdown blockquote lines for `text` (each line prefixed `> `; a blank
    line becomes `>`). Empty text ⇒ a single `> (none recorded)` line."""
    if not text:
        return ['> (none recorded)']
    out = []
    for ln in text.split('\n'):
        out.append('> ' + ln if ln else '>')
    return out


def _first100(text):
    """First 100 chars of `text` with internal whitespace runs collapsed to a
    single space (a stable one-line preview for the removed-region list)."""
    return ' '.join(text.split())[:100]


def _loc_display(locator):
    return locator if locator else 'whole file'


def _render_manifest(doc, entries):
    """Build the manifest text + the (live, removed, malformed) counts.

    `entries` is audit.read_sourced_entries(doc) — good dicts have `n`,
    malformed dicts carry {'malformed': True}. Returns (text, live_count,
    removed_count, malformed_count)."""
    val_dir = os.path.join(os.path.dirname(doc), 'validation')

    good = [e for e in entries if not e.get('malformed')]
    malformed = len(entries) - len(good)

    # Live `sourced` regions still present in the document (N -> region dict).
    try:
        with open(doc, 'r', encoding='utf-8', errors='replace') as f:
            doc_text = f.read()
    except OSError:
        doc_text = ''
    live_regions = {}
    for r in grammar.extract_regions(doc_text, _ftype_of(doc)):
        if r.get('prov') != 'sourced' or r.get('N') is None:
            continue
        try:
            live_regions[int(r['N'])] = r
        except (TypeError, ValueError):
            continue

    # Group good entries by N in file order (for duplicate-N supersession).
    by_n = {}
    for e in good:
        by_n.setdefault(e['n'], []).append(e)

    live_ns = sorted(n for n in by_n if n in live_regions)
    removed = [e for e in good if e['n'] not in live_regions]

    doc_base = os.path.basename(doc)
    doc_link = _rel_link(doc, val_dir)

    out = []
    out.append('# Source manifest — %s' % doc_base)
    out.append('')
    out.append('Generated by `/tc manifest` from the `sourced:` evidence in '
               '`.tc-history.md`. Regenerate after changes; do not edit by '
               'hand.')
    out.append('')

    for n in live_ns:
        group = by_n[n]
        entry = group[-1]        # latest by file order wins the live section
        superseded = group[:-1]
        src_link = _rel_link(entry['from'], val_dir) + _page_anchor(
            entry['locator'])
        src_name = os.path.basename(entry['from']) or entry['from']

        out.append('## Region [%d] — %s' % (n, entry['tc_src']))
        out.append('')
        out.append('Source: [%s](%s) — %s'
                   % (src_name, src_link, _loc_display(entry['locator'])))
        out.append('')
        out.append('Excerpt:')
        out.append('')
        out.extend(_blockquote(entry['excerpt']))
        out.append('')
        out.append('Supports:')
        out.append('')
        out.extend(_blockquote(entry['supports']))
        out.append('')
        out.append('Back to document: [%s](%s) (region %d)'
                   % (doc_base, doc_link, n))
        if superseded:
            out.append('')
            out.append('_Superseded earlier evidence for region %d:_' % n)
            for s in superseded:
                out.append('- %s — excerpt: "%s" (recorded %s)'
                           % (s['tc_src'], _first100(s['excerpt']),
                              s['timestamp']))
        out.append('')

    if removed:
        out.append('## Resolved/removed regions')
        out.append('')
        for e in removed:
            out.append('- [%d] %s — excerpt: "%s"'
                       % (e['n'], e['tc_src'], _first100(e['excerpt'])))
        out.append('')

    counts = '_Counts: %d live, %d resolved/removed' % (len(live_ns),
                                                        len(removed))
    if malformed:
        counts += ', %d malformed audit %s' % (
            malformed, 'entry' if malformed == 1 else 'entries')
    counts += '._'
    out.append(counts)

    text = '\n'.join(out) + '\n'
    return (text, len(live_ns), len(removed), malformed)


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

def cmd_manifest(argv):
    """Resolve the doc, read its sourced evidence, and (re)generate the
    manifest. Returns an exit code (0 wrote; 1 no evidence; 2 usage/missing/
    unreadable)."""
    # `$ARGUMENTS` may expand to a single empty/whitespace-only token; treat it
    # as no argument (working-file default).
    if len(argv) == 1 and not argv[0].strip():
        argv = []
    if len(argv) > 1:
        _err('too many arguments.\n' + _USAGE)
        return 2

    # --- Resolve the target doc: explicit arg (must exist) else working file.
    if argv:
        doc_arg = _strip_at(argv[0])
        doc = os.path.abspath(doc_arg)
        if not os.path.isfile(doc):
            _err('document not found: %s (it must be an existing tracked file)'
                 % doc_arg)
            return 2
    else:
        wf = resolve_working_file()
        if not wf:
            scope = _git_root(os.getcwd()) or os.getcwd()
            _err('no <doc> given and no tracked file found under %s; '
                 'pass an explicit <doc>.' % scope)
            return 2
        doc = os.path.abspath(wf)

    # --- Read the durable sourced evidence (audit log is the evidence home).
    try:
        entries = audit.read_sourced_entries(doc)
    except OSError as e:
        _err('could not read the audit log for %s: %s' % (doc, e))
        return 2

    good = [e for e in entries if not e.get('malformed')]
    malformed = len(entries) - len(good)
    if not good:
        extra = (' (%d malformed audit %s ignored)'
                 % (malformed, 'entry' if malformed == 1 else 'entries')
                 ) if malformed else ''
        _err('no sourced-region evidence recorded for %s%s' % (doc, extra))
        return 1

    # --- Regenerate the manifest whole-file (deterministic).
    text, live, removed, malformed = _render_manifest(doc, entries)

    val_dir = os.path.join(os.path.dirname(doc), 'validation')
    stem = os.path.splitext(os.path.basename(doc))[0]
    out_path = os.path.join(val_dir, stem + '.sources.md')
    try:
        os.makedirs(val_dir, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
    except OSError as e:
        _err('could not write manifest %s: %s' % (out_path, e))
        return 2

    counts = '%d live, %d resolved/removed' % (live, removed)
    if malformed:
        counts += ', %d malformed' % malformed
    _emit('tc manifest: wrote %s (%s)' % (out_path, counts))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    return cmd_manifest(argv)


if __name__ == '__main__':
    sys.exit(main())
