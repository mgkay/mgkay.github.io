#!/usr/bin/env python3
"""annotate_source_pdf.py -- annotate PDF source twins with the verbatim
excerpts a tracked document sourced from them (track-changes v9).

Second-layer evidence for the source-validation discipline. The FIRST layer is
the in-document gray/green marks; the SECOND layer is the self-validating
`validation/` folder — the machine-generated source manifest
(`/tc manifest`) plus the annotated PDF twins this tool produces. For every
document source that has a PDF form, it highlights the exact excerpt each
`sourced` region quoted and regenerates a trailing summary page, so a reviewer
can open one PDF per source and see, in place, everything the document drew
from it.

Ships with the track-changes suite as a side-of-protocol author/reviewer tool
(like tools/decap.py): it is NOT invoked by Claude's edit tools and does NOT go
through the mark protocol. It only READS the audit evidence
(`.tc-history.md` `sourced:` entries, via tc_core.audit) and the source files,
and WRITES twins into `validation/` — it never touches an original source.

Behavior (one document argument; audit evidence only — the manifest is
generated from the same data, so it is never needed as input):

  * Group the document's `sourced:` entries by source file.
  * Obtain a PDF form per source:
      - `.pdf`             -> used directly, READ-ONLY;
      - LibreOffice-convertible (`.docx/.pptx/.doc/.ppt/.odt/.odp`)
                           -> cached render `validation/<stem>.rendered.pdf`,
                              re-rendered when missing or the source is newer
                              (soffice discovered on PATH then the standard
                              Windows install globs). soffice missing -> the
                              affected sources are REPORTED as skipped and the
                              run exits nonzero, but other sources continue;
      - text (`.md/.qmd/.tex/.txt/...`)
                           -> reported not-annotatable ("evidence lives in the
                              manifest"); NOT an error.
  * Open the PDF form with PyMuPDF (fitz, lazy import). An empty text layer
    across all pages -> "image-based (no text layer)" report + skip (nonzero
    exit); OCR is out of scope.
  * For each entry's excerpt: search the locator's page range FIRST, then all
    pages; raw search then a normalized-fallback (longest trimmed line + word
    chunks of the shared tc_core.sourcetext.normalize form) so a quotation that
    wraps across a line break still highlights. Highlight rects get a yellow
    annot titled 'track-changes' with content '[region N] <doc basename>'. Zero
    rects -> UNMATCHED (reported + nonzero exit).
  * Build the twin `validation/<source-name>.annotated.pdf` FRESH each run from
    the CURRENT source PDF (never from a previous twin — that alone guarantees
    the summary regenerates rather than accumulating): copy, highlight, then
    append summary page(s). The original source is never modified (asserted by
    a sha256 before/after).

Exit: 0 = every excerpt matched and nothing skipped; 1 = any unmatched, scanned
/ image-based source, missing source, render failure, or soffice-skip; 2 =
usage / document missing / no `sourced:` evidence / PyMuPDF not installed.
"""
import glob
import hashlib
import os
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.join(os.path.dirname(_HERE), 'lib')
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from tc_core import audit, sourcetext  # noqa: E402


# Extension classes (lower-case, leading dot).
_TEXT_EXTS = ('.md', '.qmd', '.tex', '.txt', '.markdown', '.rmd')
_RENDER_EXTS = ('.docx', '.pptx', '.doc', '.ppt', '.odt', '.odp')

# LibreOffice fixed page geometry for the appended summary (US Letter, pt).
_SUM_W, _SUM_H = 612.0, 792.0
_SUM_LEFT = 50.0
_SUM_TOP = 60.0
_SUM_BOTTOM = 748.0
_SUM_LH = 13.0
_SUM_FONTSIZE = 9.0
_SUM_WRAP = 105  # chars per summary line before a hard wrap


# ---------------------------------------------------------------------------
# UTF-8 stdout emission (mirrors tc_source.py / the hooks' _emit). Source
# slices and excerpts carry math / em-dashes / Greek; a Windows console codec
# (cp1252) would mangle or crash on them, so write encoded bytes directly.
# ---------------------------------------------------------------------------

def _emit(text=''):
    line = text if text.endswith('\n') else text + '\n'
    try:
        sys.stdout.buffer.write(line.encode('utf-8'))
        sys.stdout.buffer.flush()
    except (AttributeError, ValueError):
        sys.stdout.write(line)


def _err(msg):
    sys.stderr.write('annotate_source_pdf: ' + msg + '\n')


# ---------------------------------------------------------------------------
# LibreOffice discovery — the minimal find_tool pattern from ISE754's
# source_lib.py (PATH first, then the standard Windows install globs). Not
# imported (that is a separate repo); the few needed lines are replicated.
# ---------------------------------------------------------------------------

_SOFFICE_WIN_GLOBS = (
    r'C:\Program Files\LibreOffice\program\soffice.exe',
    r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
)


def find_soffice():
    """Resolve the LibreOffice `soffice` executable, or None. PATH first, then
    the standard Windows install locations (the installer often omits PATH)."""
    p = shutil.which('soffice')
    if p:
        return p
    if os.name == 'nt':
        for pat in _SOFFICE_WIN_GLOBS:
            for cand in sorted(glob.glob(pat), reverse=True):
                if os.path.isfile(cand):
                    return cand
    return None


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

def _ext(path):
    dot = path.rfind('.')
    return path[dot:].lower() if dot != -1 else ''


def _sha256(path):
    """sha256 hexdigest of a file's bytes, or None when unreadable."""
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def render_source_pdf(source, validation_dir, soffice):
    """Return (cache_pdf_path, status) for a LibreOffice-convertible source,
    rendering to `validation/<stem>.rendered.pdf` when the cache is missing or
    the source is newer. `status` is 'cache hit' or 'rendered'. Raises
    RuntimeError on a render failure."""
    stem = os.path.splitext(os.path.basename(source))[0]
    cache = os.path.join(validation_dir, stem + '.rendered.pdf')
    cmt, smt = _mtime(cache), _mtime(source)
    if (os.path.isfile(cache) and cmt is not None and smt is not None
            and cmt >= smt):
        return cache, 'cache hit'
    os.makedirs(validation_dir, exist_ok=True)
    res = subprocess.run(
        [soffice, '--headless', '--convert-to', 'pdf',
         '--outdir', validation_dir, source],
        capture_output=True, text=True, timeout=600)
    produced = os.path.join(validation_dir, stem + '.pdf')
    if res.returncode != 0 or not os.path.isfile(produced):
        raise RuntimeError(
            'soffice failed on %s: rc=%s; stderr=%s'
            % (os.path.basename(source), res.returncode,
               (res.stderr or '').strip()[:300]))
    # soffice writes <stem>.pdf; adopt it under the .rendered.pdf cache name.
    if os.path.abspath(produced) != os.path.abspath(cache):
        try:
            os.replace(produced, cache)
        except OSError:
            shutil.copyfile(produced, cache)
    return cache, 'rendered'


def _locator_page_indices(locator, page_count):
    """0-indexed page hints from a locator string, clamped to the document, or
    [] when the locator carries no usable page range (whole / lines / garbage /
    'whole' sentinel written by the audit writer)."""
    if not locator or locator == 'whole':
        return []
    try:
        kind, span = sourcetext.parse_locator(locator)
    except ValueError:
        return []
    if kind != 'pages' or not span:
        return []
    a, b = span
    if a < 1:
        a = 1
    if b > page_count:
        b = page_count
    if a > b:
        return []
    return list(range(a - 1, b))


def _norm_chunks(excerpt, size=8):
    """Non-overlapping `size`-word chunks of the normalized excerpt (each >= 3
    words, or the whole thing when shorter). Used by the normalized fallback."""
    words = sourcetext.normalize(excerpt).split(' ')
    words = [w for w in words if w]
    if not words:
        return []
    if len(words) <= size:
        return [' '.join(words)] if len(words) >= 3 else []
    chunks = []
    i = 0
    while i < len(words):
        piece = words[i:i + size]
        if len(piece) >= 3:
            chunks.append(' '.join(piece))
        i += size
    return chunks


def _search_page(page, excerpt):
    """Return a list of rects for `excerpt` on `page`. Raw search first; on a
    miss the normalized fallback (whole normalized form, longest trimmed line,
    then word chunks) so a quotation that wraps across a line break — where the
    raw copy carries hard newlines — still resolves to rects."""
    raw = excerpt.strip()
    if raw:
        rects = list(page.search_for(raw))
        if rects:
            return rects
    # Normalized fallback.
    norm = sourcetext.normalize(excerpt)
    if norm:
        rects = list(page.search_for(norm))
        if rects:
            return rects
    found = []
    lines = [ln.strip() for ln in excerpt.split('\n') if ln.strip()]
    if lines:
        longest = max(lines, key=len)
        if len(longest) >= 4:
            found.extend(page.search_for(longest))
    for chunk in _norm_chunks(excerpt):
        found.extend(page.search_for(chunk))
    return found


def find_excerpt_rects(doc, excerpt, page_indices):
    """Search `page_indices` first (the locator hint), then every other page.
    Return a list of (page_index, [rects]) for the pages that matched — empty
    when the excerpt is unmatched everywhere."""
    def _scan(indices):
        hits = []
        for pi in indices:
            rects = _search_page(doc[pi], excerpt)
            if rects:
                hits.append((pi, rects))
        return hits

    hinted = [pi for pi in page_indices if 0 <= pi < doc.page_count]
    hits = _scan(hinted)
    if hits:
        return hits
    rest = [i for i in range(doc.page_count) if i not in set(hinted)]
    return _scan(rest)


def _has_text_layer(doc):
    """True iff any page yields non-whitespace extractable text."""
    for i in range(doc.page_count):
        if doc.load_page(i).get_text().strip():
            return True
    return False


def _wrap(line, width):
    """Hard-wrap a single logical line to `width` chars (summary layout only)."""
    if len(line) <= width:
        return [line]
    out = []
    s = line
    while len(s) > width:
        cut = s.rfind(' ', 0, width)
        if cut <= 0:
            cut = width
        out.append(s[:cut])
        s = s[cut:].lstrip()
    if s:
        out.append(s)
    return out


def append_summary_pages(doc, doc_basename, rows):
    """Append fresh summary page(s) listing every entry for this source. `rows`
    is a list of dicts {n, locator, excerpt, matched}. Returns the number of
    pages appended (>= 1)."""
    import fitz  # already imported by the caller; local alias
    lines = ['Sourced from this document — %s (track-changes)' % doc_basename,
             '']
    for r in rows:
        exc = ' '.join((r['excerpt'] or '').split())[:90]
        status = 'matched' if r['matched'] else 'UNMATCHED'
        loc = r['locator'] or 'whole'
        lines.append('region %s  [%s]  %s  "%s"' % (r['n'], loc, status, exc))
    if len(rows) == 0:
        lines.append('(no sourced entries)')

    wrapped = []
    for ln in lines:
        wrapped.extend(_wrap(ln, _SUM_WRAP))

    pages = 0
    page = doc.new_page(width=_SUM_W, height=_SUM_H)
    pages += 1
    y = _SUM_TOP
    for ln in wrapped:
        if y > _SUM_BOTTOM:
            page = doc.new_page(width=_SUM_W, height=_SUM_H)
            pages += 1
            y = _SUM_TOP
        page.insert_text(fitz.Point(_SUM_LEFT, y), ln, fontsize=_SUM_FONTSIZE)
        y += _SUM_LH
    return pages


def annotate_source(pdf_form, source_path, entries, doc_basename,
                    validation_dir):
    """Highlight `entries` in a fresh copy of `pdf_form` and write the twin
    `validation/<source-name>.annotated.pdf`. Returns (matched, unmatched,
    twin_path). Never writes `source_path` (asserted by the caller)."""
    import fitz
    doc = fitz.open(pdf_form)
    try:
        rows = []
        matched = 0
        unmatched = 0
        for e in entries:
            excerpt = e.get('excerpt', '')
            page_hint = _locator_page_indices(e.get('locator', ''),
                                              doc.page_count)
            hits = find_excerpt_rects(doc, excerpt, page_hint)
            if hits:
                for pi, rects in hits:
                    # Bind the Page to a local so it is not garbage-collected
                    # out from under the annot (which would orphan it —
                    # PyMuPDF "annotation not bound to any page").
                    page = doc[pi]
                    annot = page.add_highlight_annot(rects)
                    annot.set_colors(stroke=(1, 1, 0))  # yellow
                    annot.set_info(title='track-changes',
                                   content='[region %s] %s'
                                   % (e.get('n'), doc_basename))
                    annot.update()
                matched += 1
                rows.append({'n': e.get('n'), 'locator': e.get('locator', ''),
                             'excerpt': excerpt, 'matched': True})
            else:
                unmatched += 1
                rows.append({'n': e.get('n'), 'locator': e.get('locator', ''),
                             'excerpt': excerpt, 'matched': False})
        append_summary_pages(doc, doc_basename, rows)
        os.makedirs(validation_dir, exist_ok=True)
        src_name = os.path.basename(source_path)
        twin = os.path.join(validation_dir, src_name + '.annotated.pdf')
        doc.save(twin, garbage=3, deflate=True)
    finally:
        doc.close()
    return matched, unmatched, twin


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------

_USAGE = 'usage: annotate_source_pdf.py <doc> [--validation-dir <dir>]'


def _parse_args(argv):
    """Return (doc, validation_dir_override) or (None, None) on a usage error
    (already reported)."""
    doc = None
    vdir = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('-h', '--help'):
            _emit(_USAGE)
            return ('__help__', None)
        if a == '--validation-dir':
            if i + 1 >= len(argv):
                _err('--validation-dir requires a directory argument.\n'
                     + _USAGE)
                return (None, None)
            vdir = argv[i + 1]
            i += 2
            continue
        if a.startswith('--validation-dir='):
            vdir = a.split('=', 1)[1]
            i += 1
            continue
        if doc is None:
            doc = a
            i += 1
            continue
        _err('unexpected argument: %s\n%s' % (a, _USAGE))
        return (None, None)
    if doc is None:
        _err('a document argument is required.\n' + _USAGE)
        return (None, None)
    return (doc, vdir)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    doc_arg, vdir = _parse_args(argv)
    if doc_arg == '__help__':
        return 0
    if doc_arg is None:
        return 2

    doc_path = os.path.abspath(doc_arg)
    if not os.path.isfile(doc_path):
        _err('document not found: %s' % doc_arg)
        return 2

    doc_basename = os.path.basename(doc_path)
    validation_dir = os.path.abspath(vdir) if vdir else os.path.join(
        os.path.dirname(doc_path), 'validation')

    # Ensure PyMuPDF is available up front (exit 2 = install action needed).
    try:
        import fitz  # noqa: F401
    except ImportError:
        _err('reading/annotating PDFs requires PyMuPDF; install it with '
             '`pip install PyMuPDF`.')
        return 2

    # Read the durable sourced: evidence for this document.
    try:
        entries = audit.read_sourced_entries(doc_path)
    except OSError as e:
        _err('could not read the audit log for %s: %s' % (doc_basename, e))
        return 2

    good = [e for e in entries if not e.get('malformed')]
    malformed = len(entries) - len(good)
    if not good:
        if malformed:
            _err('no usable sourced: evidence for %s (%d malformed entr%s in '
                 'the audit log).'
                 % (doc_basename, malformed,
                    'y' if malformed == 1 else 'ies'))
        else:
            _err('no sourced: evidence for %s in the project .tc-history.md. '
                 'Nothing to annotate.' % doc_basename)
        return 2

    # Group by source file, preserving first-appearance order for a stable,
    # deterministic report; sort the group keys for a stable per-run ordering.
    groups = {}
    for e in good:
        src = e.get('from', '')
        groups.setdefault(src, []).append(e)

    soffice = None  # resolved lazily on the first render-needing source
    soffice_looked = False

    total_matched = 0
    total_unmatched = 0
    n_scanned = 0
    n_soffice_skip = 0
    n_missing = 0
    n_render_err = 0
    n_text = 0
    n_annotated_sources = 0

    _emit('annotate_source_pdf: %s — %d sourced entr%s across %d source%s'
          % (doc_basename, len(good), 'y' if len(good) == 1 else 'ies',
             len(groups), '' if len(groups) == 1 else 's'))
    if malformed:
        _emit('  note: %d malformed audit entr%s skipped'
              % (malformed, 'y' if malformed == 1 else 'ies'))
    _emit('  validation dir: %s' % validation_dir)
    _emit('')

    for src in sorted(groups, key=lambda s: s.lower()):
        ents = groups[src]
        name = os.path.basename(src) or src
        ext = _ext(src)

        if ext in _TEXT_EXTS:
            n_text += 1
            _emit('  %s: text source — evidence lives in the manifest '
                  '(%d entr%s, not annotatable)'
                  % (name, len(ents), 'y' if len(ents) == 1 else 'ies'))
            continue

        if not os.path.isfile(src):
            n_missing += 1
            _emit('  %s: SKIPPED — source not found at %s' % (name, src))
            continue

        # Obtain a PDF form.
        if ext == '.pdf':
            pdf_form = src
            render_note = 'native pdf'
        elif ext in _RENDER_EXTS:
            if not soffice_looked:
                soffice = find_soffice()
                soffice_looked = True
            if not soffice:
                n_soffice_skip += 1
                _emit('  %s: SKIPPED — LibreOffice not found — cannot render %s'
                      % (name, name))
                continue
            try:
                pdf_form, render_note = render_source_pdf(
                    src, validation_dir, soffice)
            except (RuntimeError, subprocess.SubprocessError, OSError) as e:
                n_render_err += 1
                _emit('  %s: SKIPPED — render failed: %s' % (name, e))
                continue
        else:
            n_soffice_skip += 1  # unknown binary type: treat as a skip
            _emit('  %s: SKIPPED — unsupported source type %r' % (name, ext))
            continue

        # Protect the original source: capture its bytes before we open it.
        src_sha_before = _sha256(src)

        # Open + verify the text layer.
        try:
            probe = fitz.open(pdf_form)
        except Exception as e:  # noqa: BLE001 — any fitz open failure
            n_render_err += 1
            _emit('  %s: SKIPPED — could not open PDF form: %s' % (name, e))
            continue
        try:
            has_text = _has_text_layer(probe)
        finally:
            probe.close()
        if not has_text:
            n_scanned += 1
            _emit('  %s: SKIPPED — image-based (no text layer): %s'
                  % (name, name))
            continue

        # Annotate a fresh copy and write the twin.
        try:
            matched, unmatched, twin = annotate_source(
                pdf_form, src, ents, doc_basename, validation_dir)
        except Exception as e:  # noqa: BLE001
            n_render_err += 1
            _emit('  %s: SKIPPED — annotation failed: %s' % (name, e))
            continue

        # Assert the original source was never modified.
        src_sha_after = _sha256(src)
        if src_sha_before is not None and src_sha_before != src_sha_after:
            _err('INTERNAL: source %s changed on disk during annotation — '
                 'aborting (twin at %s may be untrustworthy).' % (name, twin))
            return 2

        n_annotated_sources += 1
        total_matched += matched
        total_unmatched += unmatched
        _emit('  %s: annotated %d excerpt%s, %d unmatched (%s) -> %s'
              % (name, matched, '' if matched == 1 else 's', unmatched,
                 render_note, os.path.basename(twin)))

    _emit('')
    _emit('summary: %d source%s annotated; %d matched, %d UNMATCHED; '
          '%d text-only, %d scanned, %d soffice-skip, %d missing, '
          '%d render-error'
          % (n_annotated_sources, '' if n_annotated_sources == 1 else 's',
             total_matched, total_unmatched, n_text, n_scanned,
             n_soffice_skip, n_missing, n_render_err))

    if (total_unmatched or n_scanned or n_soffice_skip or n_missing
            or n_render_err):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
