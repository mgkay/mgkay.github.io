"""tc_core.sourcetext — source extraction + THE shared normalization (v9).

Data-only module for the source-validation discipline: read a document source
(text / PDF / docx), slice it by a locator, and test whether a proposed gray
excerpt is (normalized-exact) contained in that slice. Pure functions — no
sys.exit, no argparse. stdlib only at import time; PyMuPDF (`fitz`) and
python-docx (`docx`) are imported LAZILY inside the extractor branches, so
importing this module never requires either package.

`normalize()` is THE single normalization shared by the write-time hook, the
PDF annotator, and the tests. Keeping one implementation is a hard requirement:
containment is a normalized-exact substring test (MakePlan Dilemma B / F3), and
the hook, annotator, and fixtures must agree byte-for-byte on the folded form.
"""
import re
import unicodedata

from . import coverage

# Text sources are line-addressable; page locators are meaningless for them.
_TEXT_EXTS = ('.md', '.qmd', '.tex', '.txt', '.markdown', '.rmd')
_SUPPORTED_EXTS = _TEXT_EXTS + ('.pdf', '.docx')

_SOFT_HYPHEN = '­'
# Hyphen at a line break ("exam-\nple" -> "example"): a hyphen followed by any
# run of whitespace that includes a newline.
_HYPHEN_LINEBREAK_RE = re.compile(r'-\s*\n\s*')
# Every Unicode whitespace run collapses to a single ASCII space.
_WS_RUN_RE = re.compile(r'\s+', re.UNICODE)
# NFKC folds the standard space separators (NBSP, em/en spaces, …) to U+0020,
# but a handful of format/space code points are NOT whitespace-classed and are
# not decomposed by NFKC; map the ones that read as spaces explicitly so a run
# built from them still collapses. (Zero-width space, word joiner, BOM.)
_EXTRA_SPACE_MAP = {
    '​': ' ',  # ZERO WIDTH SPACE
    '﻿': ' ',  # ZERO WIDTH NO-BREAK SPACE / BOM
    '⁠': ' ',  # WORD JOINER
}
_EXTRA_SPACE_TABLE = {ord(k): v for k, v in _EXTRA_SPACE_MAP.items()}


def normalize(text):
    """THE shared normalization for the hook, annotator, and tests.

    Pipeline (case is PRESERVED throughout):
      1. Unicode NFKC fold (collapses ligatures such as ﬁ→fi, and most exotic
         space separators to U+0020).
      2. Drop soft hyphens (U+00AD).
      3. Join hyphen-linebreak splits ("exam-\\nple" → "example").
      4. Collapse every Unicode whitespace run — plus the residual zero-width
         space characters NFKC leaves behind — to a single ASCII space.
      5. Strip leading/trailing whitespace.
    """
    text = unicodedata.normalize('NFKC', text)
    text = text.replace(_SOFT_HYPHEN, '')
    text = _HYPHEN_LINEBREAK_RE.sub('', text)
    text = text.translate(_EXTRA_SPACE_TABLE)
    text = _WS_RUN_RE.sub(' ', text)
    return text.strip()


# Locator grammar --------------------------------------------------------------
_LINES_RE = re.compile(r'^L(\d+)-L(\d+)$')
# p.<a> | p<a> | p.<a>-<b> | p.<a>-p.<b>  (dot optional, trailing "p"/"p." on the
# range end optional).
_PAGES_RE = re.compile(r'^p\.?(\d+)(?:-p?\.?(\d+))?$')


def parse_locator(s):
    """Parse a locator string to a (kind, span) tuple:
      'L<a>-L<b>'                  → ('lines', (a, b))
      'p.<a>' / 'p<a>'             → ('pages', (a, a))
      'p.<a>-<b>' / 'p.<a>-p.<b>'  → ('pages', (a, b))
      '' / None                    → ('whole', None)
    Anything else raises ValueError with a clear message."""
    if s is None:
        return ('whole', None)
    s = s.strip()
    if not s:
        return ('whole', None)
    m = _LINES_RE.match(s)
    if m:
        return ('lines', (int(m.group(1)), int(m.group(2))))
    m = _PAGES_RE.match(s)
    if m:
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) is not None else a
        return ('pages', (a, b))
    raise ValueError(
        "unrecognized locator %r: expected 'L<a>-L<b>' for text lines, "
        "'p.<a>' / 'p.<a>-<b>' for pages, or empty for the whole file" % (s,))


class ScannedPdfError(Exception):
    """A PDF has no extractable text in the requested range (image-based /
    scanned — no text layer). Raised fail-closed so a fabricated excerpt can
    never verify against an unreadable source."""


def _ext(path):
    dot = path.rfind('.')
    return path[dot:].lower() if dot != -1 else ''


def extract_text(path, locator_str=None):
    """Return the source text for `path`, sliced by `locator_str`.

    Dispatch is by (case-insensitive) extension:
      * text (.md/.qmd/.tex/.txt/.markdown/.rmd): UTF-8, newline-preserving;
        a 'lines' locator slices (1-indexed inclusive, clamped, line endings
        normalized to \\n — via coverage.read_slice); 'whole' returns the whole
        file; a 'pages' locator is a ValueError (pages are meaningless here).
      * .pdf (lazy `import fitz`): a 'pages' locator selects a 1-indexed
        inclusive, clamped page range; 'whole' is all pages; a 'lines' locator
        is a ValueError. Page texts are concatenated; an empty result raises
        ScannedPdfError.
      * .docx (lazy `import docx`): all paragraph texts joined with '\\n'; the
        locator is accepted as citation metadata only (no slicing); an empty
        document returns ''.
      * any other extension → ValueError naming the supported set.

    A missing PyMuPDF/python-docx surfaces as an actionable RuntimeError, never
    a silent failure.
    """
    kind, span = parse_locator(locator_str)
    ext = _ext(path)

    if ext in _TEXT_EXTS:
        if kind == 'pages':
            raise ValueError(
                "page locator %r is meaningless for the text file %s; use "
                "'L<a>-L<b>' or the whole file" % (locator_str, path))
        frag = span if kind == 'lines' else None
        return coverage.read_slice(path, frag)

    if ext == '.pdf':
        if kind == 'lines':
            raise ValueError(
                "line locator %r is meaningless for the PDF %s; use "
                "'p.<a>' / 'p.<a>-<b>' or the whole file" % (locator_str, path))
        try:
            import fitz  # PyMuPDF — lazy
        except ImportError as exc:
            raise RuntimeError(
                "reading a PDF source requires PyMuPDF; install it with "
                "`pip install PyMuPDF`") from exc
        doc = fitz.open(path)
        try:
            page_count = doc.page_count
            if kind == 'pages':
                a, b = span
                if a < 1:
                    a = 1
                if b > page_count:
                    b = page_count
                lo, hi = a, b
            else:  # whole
                lo, hi = 1, page_count
            parts = []
            for i in range(lo - 1, hi):
                if 0 <= i < page_count:
                    parts.append(doc.load_page(i).get_text())
            result = ''.join(parts)
        finally:
            doc.close()
        if not result.strip():
            raise ScannedPdfError(
                "%s has no extractable text in the requested range — it is "
                "image-based (no text layer); OCR is out of scope" % (path,))
        return result

    if ext == '.docx':
        try:
            import docx  # python-docx — lazy
        except ImportError as exc:
            raise RuntimeError(
                "reading a .docx source requires python-docx; install it with "
                "`pip install python-docx`") from exc
        document = docx.Document(path)
        return '\n'.join(p.text for p in document.paragraphs)

    raise ValueError(
        "unsupported source extension %r for %s; supported: %s"
        % (ext, path, ', '.join(_SUPPORTED_EXTS)))


# Inline "source anchor" markers (9.1.1) — the author wraps the load-bearing
# sentence inside a contextual gray excerpt so a reviewer sees which part is the
# actual proposed source. The markers are stripped before the verbatim
# containment check: only the marker SYNTAX is removed, the inner text stays and
# must still be verbatim-contained in the source — so an anchor cannot smuggle
# non-source text past the check.
_ANCHOR_MD = re.compile(r'\[([^\]]*)\]\{\s*\.tc-src-key\s*\}')
_ANCHOR_TEX = re.compile(r'\\tcsrckey\{([^}]*)\}')


def strip_anchor(text, ftype):
    """Remove source-anchor marker SYNTAX (keeping the inner text) so a gray
    excerpt carrying an anchored load-bearing sentence still verifies verbatim
    against the plain source. md/qmd: `[sentence]{.tc-src-key}`; tex:
    `\\tcsrckey{sentence}`."""
    if not text:
        return text
    if ftype == 'tex':
        return _ANCHOR_TEX.sub(r'\1', text)
    return _ANCHOR_MD.sub(r'\1', text)


def anchor_text(text, ftype):
    """Inner text of the FIRST source-anchor marker in `text`, or None if there
    is no anchor. When a contextual excerpt marks its load-bearing sentence,
    THAT anchor — not the whole context block — is the precise sourced span: it
    is what the durable audit/manifest records and what the annotator highlights
    in the source. Containment still verifies the whole block (the context is
    real source too); the anchor just pinpoints the citation's support."""
    if not text:
        return None
    m = (_ANCHOR_TEX if ftype == 'tex' else _ANCHOR_MD).search(text)
    return m.group(1).strip() if m else None


def contains(excerpt, slice_text):
    """True iff the normalized `excerpt` is a substring of the normalized
    `slice_text`. An excerpt that normalizes to empty is never contained (an
    empty gray block must not verify)."""
    ne = normalize(excerpt)
    if not ne:
        return False
    return ne in normalize(slice_text)
