"""tc_core.websource — capture a dated snapshot of a web page as a local source.

Data-ish module for the 9.2 web-source citation flow. `/tc source <url>` fetches
a page AT STAGE TIME (never in the always-on hook), writes a durable dated
snapshot under the document's private `validation/sources/`, extracts its text,
and returns metadata the CLI stages as a pending-source record. From there the
snapshot is treated as an ordinary local file source: the hook verifies gray
excerpts against the snapshot text (normalized-exact containment, network-free),
and the audit / manifest carry the URL + access date + snapshot.

stdlib only (subprocess, urllib, socket, ipaddress, hashlib) — NO argparse and
NO browser/network at import time; importing this module is side-effect-free.
Two capture paths:
  1. discovered headless Chrome/Chromium/Edge `--print-to-pdf` → a `.pdf`
     snapshot (a visual twin the annotator can highlight);
  2. fallback `urllib` fetch → a `.html` snapshot (text-only, loud stderr
     notice) when no browser is found or the render fails/times out.

Security (MakePlan §7b F4/F5):
  * `validate_url` is an SSRF gate — http/https only; the host is resolved and
    any loopback / private / link-local / metadata (169.254.169.254) / reserved
    address is REJECTED before any fetch. `TC_SOURCE_ALLOW_LOCAL=1` (test
    opt-in only) permits LOOPBACK, never private/link-local/metadata.
  * The browser is invoked as an ARGUMENT LIST with `shell=False`; the URL is
    always one argv element — never a shell string. No `shell=True` anywhere.
  * REDIRECT SSRF (red-team): the fetch follows redirects MANUALLY and re-runs
    `validate_url` on every hop (`_fetch_validated`); auto-redirect is disabled.
    The browser is pointed at the validated terminal URL, not the raw input, so
    a page that 3xx-redirects to a private/metadata target cannot be followed.
  * Documented residuals (author-supplied-URL threat model): the browser could
    still follow a re-redirect issued by the already-validated terminal URL at
    its own fetch time (the urllib fallback body is always the validated one);
    and DNS rebinding (a hostname re-resolving to a private IP between the
    validate lookup and the connect lookup) is not fully pinned — both require
    attacker-controlled infrastructure aimed at a domain the author chose to
    cite. See build-record-9.2.0.
"""
import glob
import hashlib
import http.client
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urljoin

from . import sourcetext


class WebSourceError(Exception):
    """A web source could not be captured or has no extractable text. Raised
    fail-closed at stage time so a URL that cannot be turned into verifiable
    local snapshot text never becomes a pending source."""


# ---------------------------------------------------------------------------
# UTF-8 stderr notice (mirrors sourcetext / hook _emit): snapshot notices carry
# URLs; a Windows console codec (cp1252) would mangle or crash on non-ASCII, so
# write encoded bytes directly.
# ---------------------------------------------------------------------------

def _notice(msg):
    line = msg if msg.endswith('\n') else msg + '\n'
    try:
        sys.stderr.buffer.write(line.encode('utf-8'))
        sys.stderr.buffer.flush()
    except (AttributeError, ValueError):
        sys.stderr.write(line)


# ---------------------------------------------------------------------------
# SSRF gate.
# ---------------------------------------------------------------------------

def validate_url(url):
    """Return `(ok, reason)`. Never raises.

    Accept ONLY an `http`/`https` URL whose host resolves entirely to routable
    public addresses. Reject (with a clear reason) any non-http(s) scheme, a
    host that will not resolve, or a host resolving to a loopback / private /
    link-local / metadata (169.254.169.254) / reserved / multicast /
    unspecified address — the SSRF classes an attacker would use to reach the
    fetcher's own network or a cloud metadata endpoint.

    Exception: with `TC_SOURCE_ALLOW_LOCAL=1` (set only by the test harness so
    localhost fixtures can be served) a LOOPBACK address is permitted; private,
    link-local, and metadata addresses STAY rejected."""
    parts = urlsplit(url)
    scheme = (parts.scheme or '').lower()
    if scheme not in ('http', 'https'):
        return (False, "unsupported URL scheme %r — only http:// and https:// "
                       "are allowed" % (parts.scheme or ''))
    host = parts.hostname
    if not host:
        return (False, "URL %r has no host" % url)

    try:
        infos = socket.getaddrinfo(host, parts.port or None)
    except socket.gaierror:
        return (False, "cannot resolve host %r" % host)
    if not infos:
        return (False, "cannot resolve host %r" % host)

    allow_local = os.environ.get('TC_SOURCE_ALLOW_LOCAL') == '1'
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return (False, "host %r resolved to an unparseable address %r"
                           % (host, ip_str))
        if ip.is_loopback:
            if allow_local:
                continue  # test opt-in permits loopback only
            return (False, "refuses loopback address %s for host %r (SSRF "
                           "guard)" % (ip, host))
        if ip.is_link_local:
            # 169.254/16 (incl. the 169.254.169.254 cloud-metadata address)
            # and fe80::/10 — never permitted, even with the local opt-in.
            return (False, "refuses link-local/metadata address %s for host "
                           "%r (SSRF guard)" % (ip, host))
        if ip.is_private:
            return (False, "refuses private address %s for host %r (SSRF "
                           "guard)" % (ip, host))
        if ip.is_multicast or ip.is_reserved or ip.is_unspecified:
            return (False, "refuses non-routable address %s for host %r (SSRF "
                           "guard)" % (ip, host))
    return (True, 'ok')


# ---------------------------------------------------------------------------
# Headless-browser discovery — the find_tool pattern (PATH first, then per-OS
# install globs) shared with annotate_source_pdf.py / ISE754 source_lib.py.
# ---------------------------------------------------------------------------

_BROWSER_PATH_CANDIDATES = (
    'chrome', 'google-chrome', 'chromium', 'chromium-browser', 'msedge')


def _browser_install_globs():
    if os.name == 'nt':
        return (
            r'C:\Program Files*\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files*\Microsoft\Edge\Application\msedge.exe',
        )
    if sys.platform == 'darwin':
        return (
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
        )
    return (
        '/usr/bin/google-chrome',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
    )


def discover_browser():
    """Resolve a headless-capable Chrome/Chromium/Edge executable, or None.
    PATH candidates first, then the per-OS standard install locations (the
    installer often omits PATH). `TC_SOURCE_NO_BROWSER=1` forces None so the
    tests (and any author who prefers it) exercise the HTML fetch fallback."""
    if os.environ.get('TC_SOURCE_NO_BROWSER') == '1':
        return None
    for name in _BROWSER_PATH_CANDIDATES:
        p = shutil.which(name)
        if p:
            return p
    if os.name == 'nt':
        for pat in _browser_install_globs():
            for cand in sorted(glob.glob(pat), reverse=True):
                if os.path.isfile(cand):
                    return cand
    else:
        for cand in _browser_install_globs():
            if os.path.isfile(cand):
                return cand
    return None


# ---------------------------------------------------------------------------
# Snapshot naming.
# ---------------------------------------------------------------------------

_SLUG_HOST_RE = re.compile(r'[^a-z0-9.-]')
_SLUG_HOST_MAX = 60


def slug(url):
    """Stable, filename-safe base for a URL: `<host>-<sha256(url)[:10]>`. The
    host (lowercased, sanitized to [a-z0-9.-]) is readable; the 10-char hash of
    the FULL url guarantees uniqueness WITHOUT leaking any query/path/token into
    the filename (privacy). Bounded length."""
    host = (urlsplit(url).hostname or '').lower()
    host = _SLUG_HOST_RE.sub('-', host)[:_SLUG_HOST_MAX]
    if not host:
        host = 'web'
    digest = hashlib.sha256(url.encode('utf-8')).hexdigest()[:10]
    return '%s-%s' % (host, digest)


# ---------------------------------------------------------------------------
# Capture.
# ---------------------------------------------------------------------------

_UA = 'track-changes/9.2 (+source-capture)'
_BROWSER_TIMEOUT = 45
_FETCH_TIMEOUT = 20


def _sha256(path):
    """sha256 hexdigest of a file's bytes."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _result(snapshot_path, kind, text, url, accessdate):
    return {
        'snapshot_path': snapshot_path,
        'kind': kind,
        'text': text,
        'sha': _sha256(snapshot_path),
        'url': url,
        'accessdate': accessdate,
    }


def _usable_text(path):
    """Extracted text of `path` if it exists and yields non-empty (normalized)
    text, else None — never raises (a best-effort reuse/render probe)."""
    if not os.path.isfile(path):
        return None
    try:
        text = sourcetext.extract_text(path)
    except Exception:  # noqa: BLE001 — any extractor failure = not usable
        return None
    return text if sourcetext.normalize(text) else None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Suppress urllib's automatic redirect-following so `_fetch_validated` can
    re-run the SSRF gate on every hop (red-team: a public URL 3xx-redirecting to
    169.254.169.254 must NOT be followed blindly)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # → urlopen raises HTTPError; the caller inspects Location


_REDIRECT_CODES = (301, 302, 303, 307, 308)
_MAX_HOPS = 6


def _fetch_validated(url):
    """Fetch `url` following redirects MANUALLY, re-validating each hop with
    `validate_url` before following it. Returns `(final_url, body_bytes)` for the
    terminal 2xx. Raises `WebSourceError` if any hop is a blocked target (SSRF),
    on too many hops, or on a network/HTTP error — fail-closed. This closes the
    redirect-SSRF hole: the guard is applied to every fetched address, not just
    the stated URL."""
    opener = urllib.request.build_opener(_NoRedirect)
    cur = url
    for _ in range(_MAX_HOPS + 1):
        ok, reason = validate_url(cur)
        if not ok:
            raise WebSourceError('blocked target in redirect chain: %s (%s)'
                                 % (cur, reason))
        req = urllib.request.Request(cur, headers={'User-Agent': _UA})
        try:
            resp = opener.open(req, timeout=_FETCH_TIMEOUT)
        except urllib.error.HTTPError as exc:
            if exc.code in _REDIRECT_CODES:
                loc = exc.headers.get('Location')
                exc.close()
                if not loc:
                    raise WebSourceError('redirect with no Location from %s'
                                         % cur)
                cur = urljoin(cur, loc)  # resolve relative → absolute; re-loop
                continue
            raise WebSourceError('cannot fetch %s: HTTP %s' % (cur, exc.code))
        except (urllib.error.URLError, http.client.HTTPException,
                socket.timeout, OSError, ValueError) as exc:
            raise WebSourceError('cannot fetch %s: %s' % (cur, exc))
        with resp:
            return (cur, resp.read())
    raise WebSourceError('too many redirects from %s' % url)


def capture(url, validation_dir, accessdate):
    """Fetch `url`, write a dated snapshot under `validation_dir/sources/`, and
    return `{snapshot_path, kind ('pdf'|'html'), text, sha, url, accessdate}`.

    Idempotent: an existing `<slug>-<accessdate>.{pdf,html}` that still yields
    non-empty text is reused (same evidence — no clobber, no duplicate). Else a
    discovered headless browser renders a `.pdf`; on no-browser / render
    failure / timeout / empty render it falls through to a `urllib` HTML fetch
    (loud stderr notice). Fail-closed: a rejected URL, a network error, or a
    page with no extractable text raises `WebSourceError` — no partial record.
    The browser is an argv list with `shell=False`; the URL is one element."""
    ok, reason = validate_url(url)
    if not ok:
        raise WebSourceError(reason)

    sources_dir = os.path.join(validation_dir, 'sources')
    os.makedirs(sources_dir, exist_ok=True)
    base = slug(url) + '-' + accessdate
    pdf_path = os.path.join(sources_dir, base + '.pdf')
    html_path = os.path.join(sources_dir, base + '.html')

    # Idempotent reuse of a still-valid snapshot from an earlier capture.
    for existing, kind in ((pdf_path, 'pdf'), (html_path, 'html')):
        text = _usable_text(existing)
        if text is not None:
            return _result(existing, kind, text, url, accessdate)

    # Walk the redirect chain ourselves, validating EVERY hop, and get the
    # terminal validated URL + its body (fail-closed on a blocked hop or a
    # network error). This is the SSRF boundary for BOTH capture paths: the
    # browser is pointed at `final_url` (already validated), never the raw input
    # URL, so a redirect into a private/metadata target cannot be followed.
    final_url, raw = _fetch_validated(url)

    browser = discover_browser()
    if browser:
        rendered_ok = False
        try:
            proc = subprocess.run(
                [browser, '--headless=new', '--disable-gpu', '--no-first-run',
                 '--print-to-pdf=' + pdf_path, '--print-to-pdf-no-header',
                 final_url],
                shell=False, timeout=_BROWSER_TIMEOUT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            rendered_ok = proc.returncode == 0 and os.path.isfile(pdf_path)
        except subprocess.TimeoutExpired:
            rendered_ok = False  # run() already killed the child
        except OSError:
            rendered_ok = False  # browser vanished / not executable
        if rendered_ok:
            text = _usable_text(pdf_path)
            if text is not None:
                return _result(pdf_path, 'pdf', text, url, accessdate)
        # Present but unusable → fall through to the validated body, loudly.
        _notice('tc source: browser render failed, fell back to HTML text')
    else:
        _notice('tc source: no headless browser found — captured HTML text '
                'only (no visual PDF snapshot)')

    # HTML fallback: use the body already fetched by the validated walk.
    with open(html_path, 'wb') as f:
        f.write(raw)
    try:
        text = sourcetext.extract_text(html_path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise WebSourceError('cannot extract text from %s: %s' % (url, exc))
    if not sourcetext.normalize(text):
        raise WebSourceError('no extractable text (image-only or empty page)')
    return _result(html_path, 'html', text, url, accessdate)
