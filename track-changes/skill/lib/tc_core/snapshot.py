"""tc_core.snapshot — "the file as the AI last left it" side-store (9.9.0, D1).

The baseline the `/tc edits` workflow needs is not git: during a review session the
working tree is dirty with BOTH instructor and AI edits, and git cannot separate them.
Nor is it reconstructable from `.tc-history.md` — the audit log returns early for a
`/draft` write (post_tool_use.py), so it is blind to exactly the AI edits most likely to
collide with an instructor's.

So the baseline is captured directly: the PostToolUse hook fires on every Claude write,
and it snapshots the file's exact bytes. The hook does NOT fire for the human's IDE
edits, so the snapshot is precisely "state as of the last AI write" — the line the diff
should be drawn at.

Storage (settled in lite-plan-9.9.0 C1): `<state>/snapshots/<sha1(abspath)>.snap.<gen>`,
alongside the existing `.marks` cache in `<state>/cache/`. Per-USER state, not per-repo:
  * the `.marks` cache already establishes user-state as the home for derived state;
  * a repo-side store needs a `.gitignore` entry in every consumer repo and will
    eventually be committed by accident;
  * a snapshot is a verbatim copy of document content, so a repo-side store is a
    standing privacy hazard (a PII-bearing draft would land in git).
The cost is that snapshots do not survive a clone or a machine switch — the documented
cold-start case, where the caller falls back to git HEAD and says so.

Generations: `GENERATIONS` per file, gen 0 newest. Three, not one, because the store
doubles as an undo buffer (`restore`) and because an AI write between the instructor's
edit and `/tc edits` would otherwise absorb that edit into the only baseline there is.

Everything here is best-effort: no function raises for an I/O problem — they return
None / [] / False so a hook can never be broken by a snapshot failure.
"""
import hashlib
import json
import os
import time

GENERATIONS = 3
SNAP_MAX_BYTES = 4 * 1024 * 1024      # a lecture is ~100 KB; refuse the absurd
PRUNE_AGE_DAYS = 30
_PRUNE_INTERVAL_S = 3600              # at most one prune sweep an hour


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _state_dir(home=None):
    home = home or os.environ.get('HOME') or os.path.expanduser('~')
    return os.path.join(home, '.claude', 'skills', 'track-changes', 'state')


def snapshot_dir(home=None, create=True):
    """The snapshot store directory, or None if it cannot be created."""
    d = os.path.join(_state_dir(home), 'snapshots')
    if not create:
        return d
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return None
    return d


def _key(abs_file):
    return hashlib.sha1(os.path.abspath(abs_file).encode('utf-8')).hexdigest()


def _paths(abs_file, home=None, create=True):
    """(<dir>, <key>, <meta_path>) or (None, None, None)."""
    d = snapshot_dir(home, create=create)
    if d is None:
        return None, None, None
    k = _key(abs_file)
    return d, k, os.path.join(d, k + '.meta.json')


def _gen_path(d, k, gen):
    return os.path.join(d, '%s.snap.%d' % (k, gen))


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def _read_meta(meta_path):
    try:
        with open(meta_path, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get('gens'), list):
            return data
    except (OSError, ValueError):
        pass
    return None


def _write_meta(meta_path, meta):
    try:
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, indent=2, sort_keys=True)
            f.write('\n')
        return True
    except OSError:
        return False


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------

def save(abs_file, tool=None, home=None, data=None):
    """Capture `abs_file`'s current bytes as generation 0.

    Returns the new gen-0 metadata dict, or None when nothing was stored (file
    unreadable, over `SNAP_MAX_BYTES`, or no writable state dir).

    A save whose bytes are IDENTICAL to the current gen 0 refreshes that
    generation's timestamp instead of rotating, so a no-op write cannot burn the
    undo history. `data` (bytes) overrides reading from disk — used by tests and
    by callers that already hold the content.
    """
    abs_file = os.path.abspath(abs_file)
    if data is None:
        try:
            if os.path.getsize(abs_file) > SNAP_MAX_BYTES:
                return None
            with open(abs_file, 'rb') as f:
                data = f.read()
        except OSError:
            return None
    if len(data) > SNAP_MAX_BYTES:
        return None

    d, k, meta_path = _paths(abs_file, home)
    if d is None:
        return None

    digest = hashlib.sha256(data).hexdigest()
    meta = _read_meta(meta_path) or {'path': abs_file, 'gens': []}
    meta['path'] = abs_file
    gens = [g for g in meta.get('gens', []) if isinstance(g, dict)]

    # Identical to gen 0 -> refresh in place, no rotation.
    if gens and gens[0].get('gen') == 0 and gens[0].get('sha256') == digest \
            and os.path.isfile(_gen_path(d, k, 0)):
        gens[0]['ts'] = _now()
        if tool:
            gens[0]['tool'] = tool
        meta['gens'] = gens
        _write_meta(meta_path, meta)
        _maybe_prune(home)
        return dict(gens[0])

    # Rotate: GENERATIONS-2 -> GENERATIONS-1, ... , 0 -> 1. Drop the oldest.
    try:
        oldest = _gen_path(d, k, GENERATIONS - 1)
        if os.path.exists(oldest):
            os.remove(oldest)
        for g in range(GENERATIONS - 2, -1, -1):
            src = _gen_path(d, k, g)
            if os.path.exists(src):
                os.replace(src, _gen_path(d, k, g + 1))
        with open(_gen_path(d, k, 0), 'wb') as f:
            f.write(data)
    except OSError:
        return None

    entry = {'gen': 0, 'ts': _now(), 'sha256': digest, 'size': len(data)}
    if tool:
        entry['tool'] = tool
    shifted = []
    for g in gens:
        ng = g.get('gen', 0) + 1
        if ng < GENERATIONS:
            g = dict(g)
            g['gen'] = ng
            shifted.append(g)
    meta['gens'] = [entry] + shifted
    _write_meta(meta_path, meta)
    _maybe_prune(home)
    return dict(entry)


def load(abs_file, gen=0, home=None):
    """Return (text, meta_entry) for `gen`, or (None, None).

    Text is decoded utf-8 with errors='replace' — the stored form is raw bytes so
    line endings and encoding survive exactly; decoding is only for diffing.
    """
    raw, entry = load_bytes(abs_file, gen=gen, home=home)
    if raw is None:
        return None, None
    return raw.decode('utf-8', errors='replace'), entry


def load_bytes(abs_file, gen=0, home=None):
    """Return (bytes, meta_entry) for `gen`, or (None, None)."""
    d, k, meta_path = _paths(abs_file, home, create=False)
    if d is None:
        return None, None
    p = _gen_path(d, k, gen)
    try:
        with open(p, 'rb') as f:
            raw = f.read()
    except OSError:
        return None, None
    entry = None
    meta = _read_meta(meta_path)
    if meta:
        for g in meta.get('gens', []):
            if isinstance(g, dict) and g.get('gen') == gen:
                entry = dict(g)
                break
    return raw, entry


def list_gens(abs_file, home=None):
    """Metadata for every stored generation whose file is actually present,
    newest first. [] when there is no store for this file."""
    d, k, meta_path = _paths(abs_file, home, create=False)
    if d is None:
        return []
    meta = _read_meta(meta_path)
    out = []
    for g in (meta or {}).get('gens', []):
        if not isinstance(g, dict):
            continue
        gen = g.get('gen')
        if not isinstance(gen, int):
            continue
        if os.path.isfile(_gen_path(d, k, gen)):
            out.append(dict(g))
    out.sort(key=lambda g: g['gen'])
    return out


def list_files(home=None):
    """Every file the store holds a baseline for, as {path, gen0} dicts (9.9.3).

    `gen0` is that file's newest generation metadata (sha256 / size / ts / tool),
    so a caller can decide whether the file has changed by hashing it once —
    without loading any snapshot content.

    This is what lets bare `/tc edits` report "the currently changed files"
    instead of guessing a most-recently-modified one: the store already knows
    precisely which files have baselines. Entries whose meta is unreadable, whose
    gen-0 blob is missing, or whose recorded path no longer exists on disk are
    skipped — a stale store must degrade to "fewer files", never to an error.
    """
    d = snapshot_dir(home, create=False)
    if not d or not os.path.isdir(d):
        return []
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return []
    for name in names:
        if not name.endswith('.meta.json'):
            continue
        meta = _read_meta(os.path.join(d, name))
        if not meta:
            continue
        path = meta.get('path')
        if not path or not os.path.isfile(path):
            continue
        k = name[:-len('.meta.json')]
        gen0 = None
        for g in meta.get('gens', []):
            if isinstance(g, dict) and g.get('gen') == 0:
                gen0 = g
                break
        if gen0 is None or not os.path.isfile(_gen_path(d, k, 0)):
            continue
        out.append({'path': path, 'gen0': dict(gen0)})
    out.sort(key=lambda e: e['path'])
    return out


def current_sha256(abs_file):
    """sha256 of `abs_file`'s bytes on disk now, or None if unreadable (9.9.3).

    Comparing this against a stored gen-0 sha is how "has this file changed since
    the AI last wrote it" is answered without reading either snapshot.
    """
    try:
        with open(abs_file, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def restore(abs_file, gen=0, home=None):
    """Overwrite `abs_file` with generation `gen`, after first capturing the
    CURRENT bytes as a new generation (so the restore is itself undoable).

    Returns the restored meta entry, or None when the generation is absent or
    the write fails. Callers own the confirmation prompt — this function does
    not ask.
    """
    abs_file = os.path.abspath(abs_file)
    raw, entry = load_bytes(abs_file, gen=gen, home=home)
    if raw is None:
        return None
    save(abs_file, tool='pre-restore', home=home)
    # `save` rotated, so the requested generation moved down by one unless it
    # was a no-op refresh. Re-read from the bytes we already hold instead of
    # re-resolving the generation.
    try:
        with open(abs_file, 'wb') as f:
            f.write(raw)
    except OSError:
        return None
    return entry


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------

def _maybe_prune(home=None):
    """Run a prune sweep at most once an hour, guarded by a stamp file. Never
    raises; never blocks a write for long."""
    d = snapshot_dir(home)
    if d is None:
        return
    stamp = os.path.join(d, '.last-prune')
    try:
        if os.path.exists(stamp) and (time.time() - os.path.getmtime(stamp)) < _PRUNE_INTERVAL_S:
            return
        with open(stamp, 'w', encoding='utf-8') as f:
            f.write(_now())
    except OSError:
        return
    try:
        prune(home=home)
    except Exception:
        pass


def prune(home=None, max_age_days=PRUNE_AGE_DAYS):
    """Delete snapshot generations (and orphaned metadata) older than
    `max_age_days`. Returns the number of files removed."""
    d = snapshot_dir(home, create=False)
    if d is None or not os.path.isdir(d):
        return 0
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    try:
        names = os.listdir(d)
    except OSError:
        return 0
    for name in names:
        if not (name.endswith('.meta.json') or '.snap.' in name):
            continue
        p = os.path.join(d, name)
        try:
            if os.path.getmtime(p) < cutoff:
                os.remove(p)
                removed += 1
        except OSError:
            continue
    return removed
