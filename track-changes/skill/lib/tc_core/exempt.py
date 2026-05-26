"""tc_core.exempt — one-shot write-exemption sentinel (v3, F2).

verified-import names the exact bytes it is about to write to a tracked file;
the track-changes PreToolUse gate consumes the sentinel and passes that single
write through clean (no <mark> required). The sentinel is bound to
(target path, content sha256) so it cannot exempt any other write, is one-shot
(deleted on consume), and expires after a short TTL (crash recovery).

This is the v3 successor to v2's inline §0 import wrappers: the exemption now
lives out-of-band, so the imported block lands clean with no inline markers.
"""
import os
import json
import time
import hashlib

_TTL_DEFAULT = 120  # seconds


def _dir():
    home = os.environ.get('HOME') or os.path.expanduser('~')
    d = os.path.join(home, '.claude', 'skills', 'track-changes', 'state', 'exempt')
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return None
    return d


def content_sha(text):
    """sha256 of the proposed file content (str or bytes)."""
    if isinstance(text, str):
        text = text.encode('utf-8')
    return hashlib.sha256(text).hexdigest()


def _key(target_path):
    return hashlib.sha1(os.path.abspath(target_path).encode('utf-8')).hexdigest()


def _safe_unlink(p):
    try:
        os.remove(p)
    except OSError:
        pass


def write(target_path, content_sha_hex, ttl=_TTL_DEFAULT):
    """Record a one-shot exemption for (target_path, content_sha_hex)."""
    d = _dir()
    if not d:
        return False
    rec = {'path': os.path.abspath(target_path),
           'sha': content_sha_hex,
           'expires': time.time() + ttl}
    try:
        with open(os.path.join(d, _key(target_path) + '.json'), 'w',
                  encoding='utf-8') as f:
            json.dump(rec, f)
        return True
    except OSError:
        return False


def consume(target_path, content_sha_hex):
    """One-shot check: True iff a live sentinel matches (path, sha).

    Deletes the sentinel regardless of match (it is single-use), so a second
    write to the same path is no longer exempt.
    """
    d = _dir()
    if not d:
        return False
    p = os.path.join(d, _key(target_path) + '.json')
    if not os.path.isfile(p):
        return False
    try:
        with open(p, 'r', encoding='utf-8') as f:
            rec = json.load(f)
    except (OSError, ValueError):
        _safe_unlink(p)
        return False
    ok = (rec.get('sha') == content_sha_hex
          and os.path.abspath(rec.get('path', '')) == os.path.abspath(target_path)
          and float(rec.get('expires', 0)) >= time.time())
    _safe_unlink(p)
    return ok


def sweep():
    """Remove expired sentinels (crash-recovery; call from SessionStart)."""
    d = _dir()
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
