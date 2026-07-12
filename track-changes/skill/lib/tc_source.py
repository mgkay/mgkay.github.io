"""tc_source — the `/tc source` staging CLI (v9, source-validation discipline).

The engine for the track-changes-native `/tc source` command. It is the
source-validation twin of verified-import's `vi_verify.cmd_import`: resolve a
document source (path or `@citekey`), slice it by a locator, stage a one-shot
target-keyed pending-source record, then print the resolved slice plus an
instruction telling Claude to write ONE edit that pairs a temporary gray
`.tc-verbatim` scaffolding block (verbatim by construction — the track-changes
PreToolUse hook re-reads the source and refuses a fabricated excerpt) with a
green `sourced` region carrying the interpretation.

Unlike verified-import, this lives in track-changes' OWN lib so the always-on
gate can refuse unverified gray blocks even where verified-import is absent
(MakePlan Dilemma C). It imports the resolution / slice / staging helpers from
`tc_core` (sourcetext, srcstage, grammar). The working-file + source-path
resolution helpers are COPIED from vi_verify.py (same as vi_verify itself
mirrors tc-cli.sh's tc_resolve_working_file) rather than imported, because
verified-import may not be installed.

Usage:
    tc_source.py <file>#<locator> [<target>]
    tc_source.py @<citekey> [<locator>] [<target>]

  <locator> = L<a>-L<b> (text lines) | p.<a>[-<b>] (PDF pages) | absent (whole).

Exit codes: 0 staged; 1 usage / resolution / extraction / staging error.
(Python-missing is exit 2, handled by the tc-cli.sh shell layer.)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tc_core import sourcetext, srcstage, grammar  # noqa: E402


_USAGE = ('usage: /tc source <file>#<locator> [<target>]\n'
          '   or: /tc source @<citekey> [<locator>] [<target>]')


def _err(msg):
    sys.stderr.write('tc source: ' + msg + '\n')


def _emit(text):
    """UTF-8 stdout emission (mirrors vi_verify.cmd_import / the hooks' _emit).

    The source slice and instruction may carry non-ASCII (math symbols,
    em-dashes, Greek); a Windows console codec (cp1252) would otherwise mangle
    or crash on them, so write the encoded bytes directly."""
    line = text if text.endswith('\n') else text + '\n'
    try:
        sys.stdout.buffer.write(line.encode('utf-8'))
        sys.stdout.buffer.flush()
    except (AttributeError, ValueError):
        sys.stdout.write(line)


# ---------------------------------------------------------------------------
# Working-file + source-path resolution. COPIED from verified-import's
# vi_verify.py (which itself mirrors tc-cli.sh's tc_resolve_working_file) —
# verified-import may be absent, so track-changes carries its own copy. Keep
# these in sync with vi_verify if that resolution logic changes.
# ---------------------------------------------------------------------------

# 'validation' holds generated evidence (manifests, annotated twins) - never a
# working-file candidate.
_PRUNE_DIRS = {'.git', 'node_modules', 'validation'}
_TRACK_EXTS = {'.md', '.qmd', '.tex'}


def nearest_tc_tracked_dir(file_path):
    """Walk up from file_path's directory for a `.tc-tracked` marker. Return
    the first ancestor directory containing one, else None. Mirrors
    vi_verify.nearest_tc_tracked_dir."""
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


def resolution_candidates(file_path):
    """Ordered candidate base directories for a RELATIVE source path,
    de-duplicated by realpath (first existing wins). Mirrors
    vi_verify.resolution_candidates:
      1. the directory of the target/working file,
      2. the nearest ancestor `.tc-tracked` marker directory,
      3. the git project root,
      4. the current working directory."""
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
    """Resolve a source PATH to an existing file. Mirrors
    vi_verify.resolve_source_path. Returns (resolved_path or None, tried_dirs).
    An absolute path is honored as-is; a relative path probes the ordered
    candidate base dirs, first existing join wins (realpath-normalized)."""
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


def _yaml_override(path):
    """Return 'on'/'off'/'' from per-file YAML frontmatter (md/qmd) or magic
    comment (tex). Mirrors vi_verify._yaml_override."""
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
    vi_verify._is_tracked."""
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
    (git root of CWD, else CWD). Mirrors vi_verify.resolve_working_file.
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
    """Target format by extension (mirrors vi_verify._ftype_of): 'tex' | 'qmd'
    | 'md' (the default)."""
    ext = os.path.splitext(path or '')[1].lower()
    if ext == '.tex':
        return 'tex'
    if ext == '.qmd':
        return 'qmd'
    return 'md'


# ---------------------------------------------------------------------------
# Argument parsing.
# ---------------------------------------------------------------------------

def _strip_at(arg):
    """Strip a single leading `@` — Claude's file-reference prefix — from a
    TARGET argument (mirrors vi_verify's @-strip). Only a leading `@` is
    removed; an `@` elsewhere is kept."""
    if arg and arg.startswith('@'):
        return arg[1:]
    return arg


def _split_path_locator(arg):
    """Split a `<file>#<locator>` argument into (path, locator_str). The
    locator is the text after the LAST `#`; absent `#` ⇒ whole file ('')."""
    idx = arg.rfind('#')
    if idx == -1:
        return (arg, '')
    return (arg[:idx], arg[idx + 1:])


def _looks_like_locator(tok):
    """True iff `tok` parses as a concrete (non-whole) locator — used to tell a
    locator token from a target arg in the `@citekey` form. Recognizes
    `L<a>-L<b>`, `p.<a>`, `p<a>`, `p.<a>-<b>` (via sourcetext.parse_locator)."""
    try:
        kind, _ = sourcetext.parse_locator(tok)
    except ValueError:
        return False
    return kind != 'whole'


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

def cmd_source(argv):
    """Resolve + slice a source, stage a pending-source record, and print the
    slice + gray/green write instruction. Returns an exit code (0 staged;
    1 usage/resolution/extraction/staging error)."""
    if not argv:
        _err(_USAGE)
        return 1

    citekey = None
    locator_str = ''
    src_path_arg = None
    target_arg = None

    if argv[0].startswith('@'):
        # `@<citekey> [<locator>] [<target>]`.
        citekey = argv[0][1:]
        if not citekey:
            _err('empty citekey.\n' + _USAGE)
            return 1
        rest = list(argv[1:])
        if rest and _looks_like_locator(rest[0]):
            locator_str = rest[0]
            rest = rest[1:]
        target_arg = rest[0] if rest else None
    else:
        # `<file>#<locator> [<target>]`.
        src_path_arg, locator_str = _split_path_locator(argv[0])
        target_arg = argv[1] if len(argv) > 1 else None
        # Validate the locator now so garbage yields a clean usage error
        # (before any resolution / filesystem work).
        try:
            sourcetext.parse_locator(locator_str)
        except ValueError as e:
            _err('%s\n%s' % (e, _USAGE))
            return 1

    target_arg = _strip_at(target_arg)

    # --- Resolve the target: explicit arg (must exist) else the working file.
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

    # --- Resolve the source (path form vs citekey form).
    if citekey is not None:
        resolved, tried = srcstage.resolve_citekey(citekey, target)
        if not resolved:
            # `tried` already names both mechanisms (.bib + .tc-sources.json).
            _err(tried)
            return 1
    else:
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

    # --- Validate the extension against sourcetext's supported set BEFORE
    #     staging, so an unsupported source is refused up front.
    ext = os.path.splitext(resolved)[1].lower()
    if ext not in sourcetext._SUPPORTED_EXTS:
        _err('unsupported source extension %r for %s; supported: %s'
             % (ext, resolved, ', '.join(sourcetext._SUPPORTED_EXTS)))
        return 1

    # --- Extract the slice NOW (fail-closed): staging must never succeed on an
    #     unreadable source, so a scanned PDF / missing library / bad locator
    #     is caught here with an actionable message.
    try:
        slice_text = sourcetext.extract_text(resolved, locator_str or None)
    except sourcetext.ScannedPdfError as e:
        _err('%s. Re-stage against a text-based source or a PDF with a text '
             'layer.' % e)
        return 1
    except (ValueError, RuntimeError) as e:
        _err(str(e))
        return 1
    except (OSError, UnicodeDecodeError) as e:
        _err('could not read source %s: %s' % (resolved, e))
        return 1

    if not sourcetext.normalize(slice_text):
        _err('the staged slice is empty (locator %r selects no text in %s); '
             'check the range.'
             % (locator_str or 'whole file', resolved))
        return 1

    # --- Stage the one-shot pending-source record.
    rec = srcstage.stage(target, resolved, locator_str or '', citekey=citekey)
    if rec is None:
        _err('could not stage the pending-source record (state dir '
             'unwritable). Is track-changes installed?')
        return 1

    _emit(_render(rec, target, resolved, locator_str, slice_text))
    return 0


def _render(rec, target, resolved, locator_str, slice_text):
    """Build the staged banner + source slice + gray/green write instruction.

    `<EXPECTED>` (= srcstage.expected_src) is the canonical `tc-src` display
    value; it is printed VERBATIM into the green region opener AND used as the
    gray block's citation label so the author can copy both directly. `<NEXT_N>`
    is grammar.scan_max_n(target)+1 (the next free mark number)."""
    expected = srcstage.expected_src(rec)          # the tc-src value + label
    display = expected
    tgt_ftype = _ftype_of(target)
    target_fmt = {'tex': 'LaTeX', 'qmd': 'Quarto Markdown'}.get(
        tgt_ftype, 'Markdown')
    loc_disp = locator_str if locator_str else 'whole file'

    # Read the target to compute the next free mark number.
    try:
        with open(target, 'r', encoding='utf-8', errors='replace') as f:
            target_text = f.read()
    except OSError:
        target_text = ''
    next_n = grammar.scan_max_n(target_text, tgt_ftype) + 1

    # Format-specific delimiters for the two blocks.
    if tgt_ftype == 'tex':
        gray_open = '\\begin{tcverbatim}{%s}' % display
        gray_close = '\\end{tcverbatim}'
        green_open = '\\begin{tcregion}{%d}[sourced][%s]' % (next_n, expected)
        green_close = '\\end{tcregion}'
    else:
        gray_open = ('::: {.tc-verbatim tc-cite="%s"}' % display)
        gray_close = ':::'
        green_open = ('::: {.tc-region tc-n="%d" tc-prov="sourced" '
                      'tc-src="%s"}' % (next_n, expected))
        green_close = ':::'

    out = []
    out.append('tc source: staged %s (%s) -> %s'
               % (os.path.basename(resolved), loc_disp, target))
    out.append('')
    out.append('--- SOURCE SLICE (%s) ---' % loc_disp)
    out.append(slice_text)
    out.append('--- END SOURCE SLICE ---')
    out.append('')
    out.append(
        'Write ONE edit into %s (%s) that adds, in this exact order:'
        % (target, target_fmt))
    out.append('')
    out.append(
        '  1. A TEMPORARY gray verbatim block quoting ONLY text that appears '
        'VERBATIM in the source slice above. Copy the exact words — the '
        'track-changes hook re-reads the source and REFUSES a fabricated or '
        'paraphrased excerpt (fail-closed):')
    out.append('')
    out.append(gray_open)
    out.append('<the exact quotation you are relying on, copied from the slice>')
    out.append(gray_close)
    out.append('')
    out.append(
        '  2. IMMEDIATELY AFTER it, a green `sourced` region carrying YOUR '
        'interpretation / paraphrase of that quotation:')
    out.append('')
    out.append(green_open)
    out.append('<your sourced prose, supported by the verbatim quotation above>')
    out.append(green_close)
    out.append('')
    out.append('Rules:')
    out.append(
        '  - The gray block is VERBATIM BY CONSTRUCTION: quote only words '
        'present in the slice above. Exactly ONE gray block per write; run '
        '`/tc source` again to stage another source.')
    out.append(
        '  - `tc-src` MUST be exactly `%s` and `tc-n` MUST be `%d` (the next '
        'free mark number) — the hook rejects a mismatch.'
        % (expected, next_n))
    out.append(
        '  - The gray block is SCAFFOLDING: delete it once you have confirmed '
        'the green region, leaving only the sourced region. A quotation meant '
        'to REMAIN in the document is ordinary quoted text WITH a citation, '
        'not a green region.')
    return '\n'.join(out)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    return cmd_source(argv)


if __name__ == '__main__':
    sys.exit(main())
