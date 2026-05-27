"""vi_verify — verified-import source resolution and pending-import staging
(v4, LLM-judgment model).

This module is the engine for the `verified-import` skill's `/import`
command and its PreToolUse hook. It is a simplified, prose-normalized rebirth
of v2's `tc_provenance` (which left track-changes in v3 C2): the source-path
resolution + fragment-slice + text-source gate are ported here; the §0 inline
wrapper-scanning machinery and the v3 markup-stripping content-word
faithfulness gate are both dropped.

Two roles:

1. CLI (`main`) — the `/import` command path. Resolves + slices the source,
   resolves the target (explicit arg or the working file), stages a one-shot,
   target-keyed pending-import record under the track-changes state tree, and
   prints the resolved slice + a conversion instruction for Claude.

2. Library — the verified-import PreToolUse hook imports `load_pending` and
   `clear_pending` to detect and consume a live pending-import.

Verification model (v4, Q1/Q3):
  - There is NO mechanical content gate. The LLM does a best-effort faithful
    import and self-judges significant-vs-minor. A clean import lands clean
    (the hook writes a sha-bound exemption sentinel unconditionally when a
    pending-import is live); if the conversion introduced a genuinely
    significant content change, the LLM wraps that part in a track-changes
    mark for the author. "Verified" is redefined from "mechanically proven
    content-word-equal" to "LLM-asserted faithful, with significant changes
    marked for review." The v3 `normalized_equal` / `strip_markup` /
    `_content_words` machinery is removed as dead code.
"""
import os
import re
import sys
import json
import time
import hashlib


# ---------------------------------------------------------------------------
# Text-source allowlist (v2 FIX-3). Case-insensitive extension gate; only
# these formats are eligible to be imported from. A binary/non-text format
# (e.g. .docx, .pdf) is rejected without any read/decode attempt.
# ---------------------------------------------------------------------------
TEXT_SOURCE_EXTS = frozenset({'.md', '.markdown', '.qmd', '.rmd', '.tex', '.txt'})
_SNIFF_BYTES = 8192


# ---------------------------------------------------------------------------
# Source-path resolution + slicing (ported from v2 tc_provenance, simplified:
# wrapper-scanning dropped).
# ---------------------------------------------------------------------------

def is_text_source(path):
    """Is `path` an eligible text source for import?

    Returns (ok, reason):
      - ok=True, reason='' when the extension is in TEXT_SOURCE_EXTS
        (case-insensitive) AND a small head decodes as UTF-8 with no NUL byte.
      - ok=False, reason=<short phrase> otherwise (binary extension, NUL byte,
        or non-UTF-8 content — a mislabeled binary).

    Pure function: never raises. A missing/unreadable file is NOT this
    function's concern (extension gate passes, content sniff skipped on open
    error) — the caller's resolution step reports not-found.
    """
    ext = os.path.splitext(path or '')[1].lower()
    if ext not in TEXT_SOURCE_EXTS:
        shown = ext if ext else '(no extension)'
        return (False, 'is a binary/non-text format (%s)' % shown)
    try:
        with open(path, 'rb') as f:
            head = f.read(_SNIFF_BYTES)
    except (IOError, OSError):
        return (True, '')
    if b'\x00' in head:
        return (False, 'contains a NUL byte (mislabeled binary)')
    try:
        head.decode('utf-8')
    except UnicodeDecodeError as e:
        # A multibyte char may straddle the sniff boundary; only flag when the
        # error is not at the very tail of the truncated head.
        if e.start < len(head) - 4:
            return (False, 'is not valid UTF-8 text (mislabeled binary)')
    return (True, '')


def nearest_tc_tracked_dir(file_path):
    """Walk up from file_path's directory for a `.tc-tracked` marker. Return
    the first ancestor directory containing one, else None. Pure filesystem
    probe; never raises."""
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
    """Walk up from start_dir for a `.git` directory; return the root or None."""
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


def resolution_candidates(file_path):
    """Ordered candidate base directories for a RELATIVE source path,
    de-duplicated by realpath, first existing wins (caller joins the path):
      1. the directory of the edited/working file (dirname(file_path)),
      2. the nearest ancestor `.tc-tracked` marker directory,
      3. the git project root,
      4. the current working directory (fallback when no file context).
    """
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
    base_for_git = (os.path.dirname(os.path.abspath(file_path))
                    if file_path else os.getcwd())
    _add(_git_root(base_for_git))
    _add(os.getcwd())
    return cands


def resolve_source_path(rel_or_abs_path, file_path):
    """Resolve a source PATH to an existing file.

    Returns (resolved_path or None, tried_dirs). An absolute path is honored
    as-is (returned if it exists, else (None, [])). For a relative path the
    ordered candidate base dirs are probed; the first whose join is an existing
    file wins (realpath-normalized). `tried_dirs` lists the bases probed."""
    if rel_or_abs_path and os.path.isabs(rel_or_abs_path):
        if os.path.isfile(rel_or_abs_path):
            return (os.path.realpath(rel_or_abs_path), [])
        return (None, [])
    tried = resolution_candidates(file_path)
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
    Line endings are normalized to '\\n'. Out-of-range bounds are clamped; an
    inverted range yields ''."""
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


_FRAG_RE = re.compile(r'#L(\d+)-L(\d+)\s*$')


def parse_source_arg(arg):
    """Split a `<source>[#L<a>-L<b>]` argument into (path, frag).

    frag is (a, b) or None. The path may contain spaces; the fragment, if
    present, is taken from the trailing `#L<a>-L<b>`."""
    if not arg:
        return ('', None)
    fm = _FRAG_RE.search(arg)
    if fm:
        a = int(fm.group(1))
        b = int(fm.group(2))
        return (arg[:fm.start()].rstrip(), (a, b))
    return (arg, None)


def _ftype_of(path):
    ext = os.path.splitext(path or '')[1].lower()
    if ext == '.tex':
        return 'tex'
    if ext == '.qmd':
        return 'qmd'
    return 'md'


# ---------------------------------------------------------------------------
# Pending-import staging — mirrors tc_core.exempt's dir/key/TTL pattern.
#
# A pending-import is a one-shot, target-keyed record staged by `/import` and
# consumed by the verified-import PreToolUse hook. It lives under the same
# track-changes state tree as the exemption sentinels (one subdir over) so a
# single install owns all verified-import state.
# ---------------------------------------------------------------------------

_PENDING_TTL_DEFAULT = 300  # seconds (v4 F3 — wider window for conversion;
                            # user-overridable via the ttl param)


def _pending_dir():
    home = os.environ.get('HOME') or os.path.expanduser('~')
    d = os.path.join(home, '.claude', 'skills', 'track-changes',
                     'state', 'import')
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return None
    return d


def _pending_key(target_path):
    return hashlib.sha1(
        os.path.abspath(target_path).encode('utf-8')).hexdigest()


def _pending_path(target_path):
    d = _pending_dir()
    if not d:
        return None
    return os.path.join(d, _pending_key(target_path) + '.json')


def _safe_unlink(p):
    try:
        os.remove(p)
    except OSError:
        pass


def stage_pending(target_path, source_path, frag, ttl=_PENDING_TTL_DEFAULT):
    """Write a one-shot pending-import record keyed on the target file.

    Record (v4 — slimmed per F5): EXACTLY {target, source_path, range, expires}.
    The v3 fields `source_slice_text`, `mode`, and `source_ftype` are dropped —
    with no mechanical content gate the hook no longer compares against a stored
    slice; the CLI prints the slice at stage time and the LLM converts it.

    Returns the record on success, None on I/O failure (truthy on success — the
    CLI uses the returned `range`)."""
    p = _pending_path(target_path)
    if not p:
        return None
    rng = ('L%d-L%d' % (frag[0], frag[1])) if frag else 'whole-file'
    rec = {
        'target': os.path.abspath(target_path),
        'source_path': source_path,
        'range': rng,
        'expires': time.time() + ttl,
    }
    try:
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(rec, f)
        return rec
    except OSError:
        return None


def load_pending(target_path):
    """Return the live pending-import record for `target_path`, or None.

    Record shape (v4): {target, source_path, range, expires}. Returns None (and
    unlinks) when the record is missing, unparseable, for a different path, or
    expired. Does NOT consume a live record — the hook clears it explicitly once
    it has written the clean-import exemption sentinel."""
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


def clear_pending(target_path):
    """Delete the pending-import record for `target_path` (one-shot consume)."""
    p = _pending_path(target_path)
    if p:
        _safe_unlink(p)


def sweep_pending():
    """Remove expired pending-import records (crash recovery)."""
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
# Working-file resolution (the import target default). Mirrors tc-cli.sh's
# tc_resolve_working_file: most-recently-modified tracked-active md/qmd/tex
# under the project scope (git root of CWD, else CWD). Activation here is a
# lightweight probe (YAML override / nearest .tc-tracked); the authoritative
# gate is the track-changes hook on the actual write.
# ---------------------------------------------------------------------------

_PRUNE_DIRS = {'.git', 'node_modules'}
_TRACK_EXTS = {'.md', '.qmd', '.tex'}


def _yaml_override(path):
    """Return 'on'/'off'/'' from per-file YAML frontmatter (md/qmd) or magic
    comment (tex). Lightweight mirror of tc-common.sh tc_check_yaml_override."""
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
    # md / qmd: YAML frontmatter.
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
    """Lightweight activation probe for working-file selection."""
    base = os.path.basename(path)
    if base.startswith('.'):
        ov = _yaml_override(path)
        return ov == 'on'  # hidden file tracked only via explicit YAML true
    ov = _yaml_override(path)
    if ov == 'on':
        return True
    if ov == 'off':
        return False
    return nearest_tc_tracked_dir(path) is not None


def resolve_working_file():
    """Most-recently-modified tracked-active md/qmd/tex under the project scope
    (git root of CWD, else CWD). Returns the path or None."""
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


# ---------------------------------------------------------------------------
# CLI — the `/import` command path.
# ---------------------------------------------------------------------------

def _err(msg):
    sys.stderr.write('verified-import: ' + msg + '\n')


def cmd_import(argv):
    """`vi_verify.py import <source>[#L<a>-L<b>] [<target>]`.

    Resolves + slices the source, resolves the target (explicit arg or working
    file), stages a one-shot pending-import, and prints the slice + a
    conversion instruction. Returns an exit code."""
    if not argv:
        _err('usage: import <source>[#L<a>-L<b>] [<target>]')
        return 1
    source_arg = argv[0]
    target_arg = argv[1] if len(argv) > 1 else None

    # C2 (E3): strip a single leading `@` — Claude's file-reference prefix —
    # from BOTH args before resolution, so `/import @src#L1-L2 @target` resolves
    # identically to the un-prefixed form. Only a leading `@` is stripped; an `@`
    # elsewhere in the path (e.g. a directory literally named `@foo`) is kept.
    if source_arg.startswith('@'):
        source_arg = source_arg[1:]
    if target_arg and target_arg.startswith('@'):
        target_arg = target_arg[1:]

    src_path_arg, frag = parse_source_arg(source_arg)

    # Resolve the target first so source resolution can use its directory as a
    # candidate base (the natural "import into THIS doc" case).
    if target_arg:
        target = os.path.abspath(target_arg)
        if not os.path.isfile(target):
            _err('target not found: %s (it must be an existing tracked file)'
                 % target_arg)
            return 1
    else:
        wf = resolve_working_file()
        if not wf:
            scope = _git_root(os.getcwd()) or os.getcwd()
            _err('no target given and no tracked file found under %s; '
                 'pass an explicit <target>.' % scope)
            return 1
        target = os.path.abspath(wf)

    resolved, tried = resolve_source_path(src_path_arg, target)
    if not resolved:
        if os.path.isabs(src_path_arg):
            _err('source not found: %s (absolute path does not exist)'
                 % src_path_arg)
        else:
            shown = ', '.join(tried) if tried else '(no candidate dirs)'
            _err('source not found: %s (looked in: %s)'
                 % (src_path_arg, shown))
        return 1

    ok, reason = is_text_source(resolved)
    if not ok:
        _err('source %s %s — only text sources (%s) can be imported.'
             % (src_path_arg, reason,
                ', '.join(sorted(TEXT_SOURCE_EXTS))))
        return 1

    try:
        with open(resolved, 'r', encoding='utf-8', newline='') as f:
            source_text = f.read()
    except (OSError, UnicodeDecodeError) as e:
        _err('could not read source %s: %s' % (resolved, e))
        return 1

    source_slice = slice_fragment(source_text, frag)
    if frag and source_slice == '':
        _err('source slice #L%d-L%d is empty or inverted in %s.'
             % (frag[0], frag[1], resolved))
        return 1

    rec = stage_pending(target, resolved, frag)
    if rec is None:
        _err('could not stage the pending-import record (state dir '
             'unwritable). Is track-changes installed?')
        return 1

    rng = rec['range']
    tgt_ftype = _ftype_of(target)
    target_fmt = {'tex': 'LaTeX', 'qmd': 'Quarto Markdown'}.get(
        tgt_ftype, 'Markdown')
    out = []
    out.append('verified-import: staged import of %s (%s) -> %s'
               % (os.path.basename(resolved), rng, target))
    out.append('')
    out.append('--- SOURCE SLICE (%s) ---' % rng)
    out.append(source_slice)
    out.append('--- END SOURCE SLICE ---')
    out.append('')
    out.append(
        'Convert the source slice above to %s and insert it into %s. Reproduce '
        'the content faithfully — preserve every sentence and clause; only '
        'formatting may change to match the target format. This is a verified '
        'import: it lands clean (no `<mark>`) by default. If your conversion '
        'introduces a SIGNIFICANT content change — an added or removed '
        'sentence or clause, or a changed quantity, term, or formula — wrap '
        'ONLY that change in a track-changes mark so the author reviews it '
        '(Markdown: `<mark>NEW</mark><sup>N</sup>`; LaTeX: `\\tc{NEW}\\tcn{N}`). '
        'A SIGNIFICANT change alters meaning; reflow, reformatting, and '
        'equivalent notation (e.g. `\\section{X}` → `## X`, an `equation` '
        'environment → `$$…$$`) are NOT significant and need no mark. '
        'Example: dropping the clause "at optimal lot size" IS significant (mark '
        'it); rewrapping lines or converting an equation environment to `$$…$$` '
        'is NOT. Write ONLY the converted block in this edit — do not bundle '
        'unrelated edits into the same write.'
        % (target_fmt, target))
    # Emit UTF-8 explicitly: the source slice and the instruction may contain
    # non-ASCII (math symbols, em-dashes, Greek), and a Windows console codec
    # (cp1252) would otherwise mangle or crash on them. Mirror the hooks' _emit.
    text = '\n'.join(out) + '\n'
    try:
        sys.stdout.buffer.write(text.encode('utf-8'))
        sys.stdout.buffer.flush()
    except (AttributeError, ValueError):
        sys.stdout.write(text)
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        _err('usage: vi_verify.py import <source>[#L<a>-L<b>] [<target>]')
        return 1
    cmd = argv[0]
    if cmd == 'import':
        return cmd_import(argv[1:])
    _err('unknown command: %s (expected: import)' % cmd)
    return 1


if __name__ == '__main__':
    sys.exit(main())
