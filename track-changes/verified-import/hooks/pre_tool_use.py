"""hooks/pre_tool_use.py — verified-import PreToolUse gate (v4, LLM-judgment).

This hook runs on Write/Edit/MultiEdit to an existing file. It is the enabler
for a `/tc import` operation: when a live, target-keyed pending-import exists for
the file being written, it writes a one-shot, sha-bound exemption sentinel via
tc_core.exempt.write over the EXACT proposed file bytes the track-changes gate
will hash (tc_analyzer._build_proposed + tc_core.exempt.content_sha —
byte-for-byte mirror, see #LEARN in the decision log), appends an `imported:`
audit entry, clears the pending-import, and ALLOWS the write (exit 0). The
converted block lands clean (no <mark>) because track-changes consumes the
sentinel.

v4 paradigm shift (Q1/Q3): there is NO mechanical faithfulness gate. The LLM
does a best-effort faithful import and self-judges significant-vs-minor; if it
introduced a genuinely significant change it wraps that span in a track-changes
mark itself (and that mark survives, since the exemption only suppresses the
whole-file <mark>-requirement for this single write). The v3 normalized_equal
content-word check + fail-closed FAIL branch are removed.

8.2.0 coverage gate: one mechanical check returns, narrower than v3's --
COMPLETENESS, not equivalence. Every source content token (word/number/
subscripted id, per tc_core.coverage) must appear somewhere in the proposed
write; rewording and reformatting still pass, but an import that DROPS content
is blocked (exit 2) with the missing tokens named, and the pending-import is
preserved so a corrected retry still verifies. Explicit override:
`/tc import --allow-partial` stores allow_partial on the record; the hook then
lands the write and records the override + dropped list in the audit entry.
Fail-closed: if the source cannot be re-read at write time, block.

When there is NO live pending-import for the target, this is an ordinary edit:
the hook is a no-op passthrough (exit 0) and track-changes handles it normally.

F2 ordering: this hook MUST run BEFORE track-changes' PreToolUse on the same
write (it writes the sentinel track-changes consumes). Registration/order is
owned by the installer; this hook is correct assuming it runs first.

T3/D3 (fail-closed dependency): verified-import depends on track-changes'
tc_core. If tc_core cannot be imported while a pending-import is live, the
import write must NOT silently bypass the mark gate — the hook emits a clear
"install track-changes first" error and exits 2.

Exit codes:
  0  allow (no pending-import, off-scope, or a clean verified import)
  2  block (track-changes/tc_core unavailable while a pending-import is live)
"""
import os
import sys
import json
import time
import difflib

# Make this skill's own lib importable (vi_verify), then locate track-changes'
# lib for tc_core + tc_analyzer.
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(_HOOK_DIR)              # verified-import/
_LIB_DIR = os.path.join(_SKILL_ROOT, 'lib')
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

# track-changes/lib candidates: a sibling layout (project tree / co-deploy) and
# the canonical deployed location.
_TC_LIB_CANDIDATES = [
    os.path.normpath(os.path.join(_SKILL_ROOT, '..', 'track-changes', 'lib')),
    os.path.join(os.environ.get('HOME') or os.path.expanduser('~'),
                 '.claude', 'skills', 'track-changes', 'lib'),
]
for _cand in _TC_LIB_CANDIDATES:
    if os.path.isdir(_cand) and _cand not in sys.path:
        sys.path.insert(0, _cand)


def _log(msg):
    """Best-effort timestamped log to track-changes' state/tc.log."""
    try:
        home = os.environ.get('HOME') or os.path.expanduser('~')
        d = os.path.join(home, '.claude', 'skills', 'track-changes', 'state')
        os.makedirs(d, exist_ok=True)
        ts = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        with open(os.path.join(d, 'tc.log'), 'a', encoding='utf-8') as f:
            f.write('%s verified-import/pre_tool_use.py: %s\n' % (ts, msg))
    except Exception:
        pass


def _read_payload():
    # Mirror track-changes' _read_payload: read stdin as raw bytes, decode
    # UTF-8 explicitly (Windows stdin codec may not be UTF-8).
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
        try:
            data = sys.stdin.read()
        except Exception:
            return None
        if not data:
            return None
        try:
            return json.loads(data)
        except ValueError:
            return None
    if not raw:
        return None
    try:
        data = raw.decode('utf-8')
    except UnicodeDecodeError:
        try:
            data = raw.decode('utf-8', errors='replace')
        except Exception:
            return None
    try:
        return json.loads(data)
    except ValueError:
        return None


def _emit(msg):
    """Write a message to stderr as UTF-8 (non-ASCII survives any codec)."""
    text = msg if msg.endswith('\n') else msg + '\n'
    try:
        sys.stderr.buffer.write(text.encode('utf-8'))
        sys.stderr.buffer.flush()
    except Exception:
        try:
            sys.stderr.write(text)
        except Exception:
            sys.stderr.write(text.encode('utf-8', 'replace').decode('ascii', 'replace'))


def _added_block(source_text, proposed_text):
    """Return the inserted/changed content as a single string — the proposed
    lines tagged '+' by a unified diff against the current source. This is the
    block recorded in the `imported:` audit entry (the content the write adds)."""
    src_lines = source_text.replace('\r\n', '\n').split('\n')
    prop_lines = proposed_text.replace('\r\n', '\n').split('\n')
    added = []
    for dl in difflib.unified_diff(src_lines, prop_lines, lineterm=''):
        if dl.startswith('+++') or dl.startswith('---') or dl.startswith('@@'):
            continue
        if dl.startswith('+'):
            added.append(dl[1:])
    return '\n'.join(added)


def _write_import_audit(abs_file_path, rec, added_block, dropped=None):
    """Append an `imported:` audit entry (best-effort), mirroring the entry
    shape used by track-changes' tc_resolve._write_explicit_audit (timestamp,
    relative path, find_project_root, log_path_for). When the import landed
    under an --allow-partial override WITH missing tokens, `dropped` carries
    the missing-token list and the entry records the override (8.2.0)."""
    try:
        from tc_core import audit as tc_audit
        import datetime
        abs_path = os.path.abspath(abs_file_path)
        log_path = tc_audit.log_path_for(abs_path)
        root = tc_audit.find_project_root(abs_path)
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
        rng = rec.get('range', 'whole-file')
        lines = [f"\n## {ts} -- {rel}  (verified-import)"]
        lines.append("imported:")
        lines.append(f"  - from: {tc_audit._fmt_str(src)}")
        lines.append(f"    range: {rng}")
        lines.append(f"    verified: true")
        if dropped:
            lines.append(f"    allow_partial: true")
            lines.append(f"    dropped: {tc_audit._fmt_str(', '.join(dropped))}")
        lines.append(f"    new: {tc_audit._fmt_str(added_block)}")
        entry = '\n'.join(lines) + '\n'
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if not os.path.exists(log_path):
            header = (
                "# track-changes history\n"
                "#\n"
                "# Append-only audit log of AI-introduced and AI-introduced-then-resolved\n"
                "# marks for tracked files in this project. Each entry records one\n"
                "# Write/Edit/MultiEdit, explicit /tc resolution, or verified import.\n"
                "#\n"
                "# Generated and maintained by the track-changes / verified-import skills.\n"
                "# Do not edit by hand (append-only). To reset: delete this file.\n"
            )
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(header)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(entry)
        return True
    except Exception as e:
        _log('import audit write failed: %s' % e)
        return False


def main():
    payload = _read_payload()
    if payload is None:
        return 0
    tool_name = (payload.get('tool_name') or '').strip()
    if tool_name not in ('Write', 'Edit', 'MultiEdit'):
        return 0
    ti = payload.get('tool_input') or {}
    file_path = (ti.get('file_path') or '').strip()
    if not file_path:
        return 0
    # Only act on an existing file (a new-file write has nothing to import into
    # vs. and track-changes already passes those through).
    if not os.path.isfile(file_path):
        return 0

    # Import vi_verify (this skill's own lib — always present beside the hook).
    try:
        import vi_verify
    except Exception as e:
        # Our own engine is missing: cannot verify. Fail-closed only if a
        # pending-import might exist; but without vi_verify we cannot even read
        # it. Treat as a hard configuration error.
        _emit('verified-import: internal error — cannot import vi_verify (%s).' % e)
        return 2

    # Is there a live pending-import for THIS target? Cheap check first: if
    # none, this is an ordinary edit — pass through (track-changes handles it).
    rec = vi_verify.load_pending(file_path)
    if rec is None:
        return 0

    # A pending-import exists -> this is a verified-import operation. From here
    # on, tc_core is REQUIRED (we must write the exemption sentinel track-changes
    # consumes). T3/D3: if it is unavailable, fail closed.
    try:
        from tc_core import exempt as tc_exempt  # noqa: F401
        from tc_core import coverage as tc_coverage
        import tc_analyzer
    except Exception as e:
        _log('tc_core/tc_analyzer import failed with a live pending-import: %s' % e)
        _emit('verified-import: track-changes is not installed or is outdated '
              '— install track-changes first (or update it; verified-import '
              'depends on its tc_core, incl. tc_core.coverage as of 8.2.0). '
              'Aborting the import write to avoid bypassing the mark gate.')
        return 2

    # Build the proposed full-file text IDENTICALLY to how the track-changes
    # gate builds the text it hashes (same _build_proposed). Read the current
    # source the same way (raw bytes, UTF-8, newline-preserving) so the diff and
    # the hash see the same content.
    try:
        with open(file_path, 'r', encoding='utf-8', newline='') as f:
            source_text = f.read()
    except (IOError, OSError) as e:
        _log('cannot read target %s: %s' % (file_path, e))
        _emit('verified-import: cannot read target %s (%s).' % (file_path, e))
        return 2

    proposed_text = tc_analyzer._build_proposed(source_text, payload, tool_name)
    if proposed_text is None:
        # Unsupported tool shape — let it pass to track-changes.
        return 0

    # v4: a live pending-import is sufficient — there is no content gate. The
    # LLM converted faithfully and self-marked any significant change. Capture
    # the added block only to populate the audit `new:` field (the slice is no
    # longer stored on the record).
    added_block = _added_block(source_text, proposed_text)

    # 8.2.0 coverage gate: no source content token may be missing from the
    # proposed write. Re-resolve the source slice from the live record (the v4
    # record stores no text), tokenize both sides, and block (exit 2, pending
    # PRESERVED so a corrected retry still verifies) when content was dropped
    # -- unless the record carries the explicit --allow-partial override.
    allow_partial = bool(rec.get('allow_partial'))
    src_arg = rec.get('source_path', '')
    resolved_src, _tried = vi_verify.resolve_source_path(src_arg, file_path)
    if not resolved_src:
        # Fail-closed: source moved/deleted between staging and write time --
        # coverage cannot be verified, so the import must not land unchecked.
        _log('coverage: cannot re-resolve source %s for %s' % (src_arg, file_path))
        _emit('verified-import: cannot re-read the import source %s to verify '
              'coverage -- re-run `/tc import` to re-stage (or add '
              '`--allow-partial`).' % src_arg)
        return 2
    try:
        src_slice = tc_coverage.read_slice(
            resolved_src, tc_coverage.parse_range(rec.get('range')))
    except (OSError, UnicodeDecodeError) as e:
        _log('coverage: cannot read source slice %s: %s' % (resolved_src, e))
        _emit('verified-import: cannot re-read the import source %s to verify '
              'coverage (%s) -- re-run `/tc import` to re-stage (or add '
              '`--allow-partial`).' % (resolved_src, e))
        return 2
    dropped = tc_coverage.missing_tokens(src_slice, proposed_text)
    if dropped and not allow_partial:
        _log('coverage: blocked %s -- %d missing token(s): %s'
             % (file_path, len(dropped), ', '.join(dropped)))
        _emit('coverage: import blocked -- %d source content token(s) missing '
              'from %s: %s\n'
              'The import dropped content; restore it and retry (the pending '
              'import is still live). If this is legitimate rewording/'
              'reformatting, re-run: /tc import --allow-partial <source> '
              '[<target>]' % (len(dropped), file_path, ', '.join(dropped)))
        return 2

    # Write the one-shot exemption sentinel over the proposed bytes, in the SAME
    # way track-changes computes the sha it consumes (#LEARN): sha256 over the
    # proposed file bytes via tc_core.exempt.content_sha, no extra
    # normalization. track-changes' gate does the same _build_proposed and
    # consumes this sentinel, so the import write lands clean (no <mark>). Any
    # <mark> the LLM added for a significant change survives — the exemption
    # only suppresses the unmarked-content block for this single write.
    try:
        content_sha = tc_exempt.content_sha(proposed_text)
        wrote = tc_exempt.write(file_path, content_sha)
    except Exception as e:
        _log('exempt.write failed: %s' % e)
        _emit('verified-import: could not record the clean-import exemption (%s). '
              'Aborting to avoid an unmarked write.' % e)
        return 2
    if not wrote:
        _emit('verified-import: could not record the clean-import exemption '
              '(state dir unwritable). Aborting to avoid an unmarked write.')
        return 2

    _write_import_audit(file_path, rec, added_block,
                        dropped=(dropped if allow_partial else None))
    vi_verify.clear_pending(file_path)
    _log('verified import %s (exempt sha %s)' % (file_path, content_sha[:12]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
