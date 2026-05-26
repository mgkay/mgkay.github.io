"""tc_settings_merge.py — merge the track-changes + verified-import suite hook
registrations into ~/.claude/settings.json (Fix #14; v3 two-skill split).

Used by the bootstrap installer so the curl-based deployment doesn't need
to inline ~80 lines of jq. The local `bash install.sh` still uses its own
jq merge — this Python version is the behavioral equivalent for remote
installs and MUST track install.sh's `merge_settings` (it strips BOTH suite
signatures, then concatenates the patch's groups in order).

v3 registers TWO skills: the always-on `track-changes` mark-gate (5 events)
and the opt-in `verified-import` hook (PreToolUse only). The v3 patch lists
verified-import's PreToolUse group BEFORE track-changes' (F2: verified-import
writes the exemption sentinel that track-changes consumes, so it must run
first). The merge preserves the patch's per-event group order, so that
VI-before-TC ordering is honored on disk.

Usage:
    python tc_settings_merge.py <patch_path> <settings_path>

Behavior:
- If <settings_path> doesn't exist, writes the patch verbatim (pretty-printed).
- Otherwise: Option-A "update-on-upgrade" merge. For each event in the patch,
  the existing SUITE-owned groups are STRIPPED and replaced by the patch's
  groups; non-suite groups (third-party hooks) are preserved. A group is
  identified as suite-owned if any of its `hooks[].command` fields contains
  EITHER the `track-changes/hooks/` OR the `verified-import/hooks/` substring.
  Stripping BOTH signatures makes the merge:
    * idempotent — a re-run strips then re-adds exactly the same suite groups
      per event (no duplicates, in particular no duplicated verified-import
      group, which a single-signature strip would leave behind on re-run); and
    * replace-on-upgrade — a v2 install registered a single `track-changes`
      PreToolUse group; this strips it and lays down the v3 two-skill set
      (verified-import then track-changes) in its place, with no stale entries;
      it also self-repairs a stale v1-era `bash …/pre-tool-use.sh`
      registration into the patch's `python …/pre_tool_use.py` command.
- Backs up the existing settings.json to a `.bak.YYYYMMDDTHHMMSSZ` sibling
  file before writing.

Exit codes:
    0  merge succeeded (or was a no-op)
    1  bad arguments
    2  invalid JSON in patch or settings
"""
import json
import os
import sys
import time
import shutil


# Suite hook-command signatures. A group whose `hooks[].command` carries
# EITHER substring is owned by the v3 suite (mirrors install.sh's
# TC_HOOK_SIGNATURE / VI_HOOK_SIGNATURE). SIGNATURE is retained as an alias of
# the track-changes signature for back-compat with any importer.
TC_SIGNATURE = 'track-changes/hooks/'
VI_SIGNATURE = 'verified-import/hooks/'
SUITE_SIGNATURES = (TC_SIGNATURE, VI_SIGNATURE)
SIGNATURE = TC_SIGNATURE


def _is_suite_group(group):
    """True if `group` (a dict containing `hooks`) has any hook whose command
    mentions either suite signature (track-changes OR verified-import)."""
    if not isinstance(group, dict):
        return False
    for h in group.get('hooks', []) or []:
        cmd = (h or {}).get('command', '') or ''
        if any(sig in cmd for sig in SUITE_SIGNATURES):
            return True
    return False


def _has_suite_entry(event_groups):
    """True if any entry in `event_groups` (a list of dicts containing
    `hooks`) has a hook whose command mentions either suite signature."""
    if not isinstance(event_groups, list):
        return False
    return any(_is_suite_group(group) for group in event_groups)


def _strip_suite_groups(event_groups):
    """Return the subset of `event_groups` whose groups are NOT suite-owned
    (i.e., drop any group carrying the track-changes OR verified-import
    signature, preserve all third-party groups). Order is preserved."""
    if not isinstance(event_groups, list):
        return []
    return [g for g in event_groups if not _is_suite_group(g)]


def merge(patch_path, settings_path):
    # Load patch.
    try:
        with open(patch_path, 'r', encoding='utf-8') as f:
            patch = json.load(f)
    except (IOError, ValueError) as e:
        print(f'error: cannot read patch {patch_path}: {e}', file=sys.stderr)
        return 2

    new_hooks = (patch or {}).get('hooks') or {}
    if not new_hooks:
        print('error: patch has no .hooks section', file=sys.stderr)
        return 2

    # Fresh write if settings.json doesn't exist.
    if not os.path.isfile(settings_path):
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(patch, f, indent=2)
            f.write('\n')
        print(f'created {settings_path} with {len(new_hooks)} hook events')
        return 0

    # Existing settings: load + validate.
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except (IOError, ValueError) as e:
        print(f'error: existing {settings_path} is not valid JSON: {e}', file=sys.stderr)
        print('  fix the file (or move it aside) and re-run the installer', file=sys.stderr)
        return 2

    # Back up.
    ts = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    backup = f'{settings_path}.bak.{ts}'
    try:
        shutil.copy2(settings_path, backup)
    except (IOError, OSError) as e:
        print(f'warning: could not back up settings.json: {e}', file=sys.stderr)
        # Continue anyway — the merge is read-then-write so a crash mid-write
        # is the only loss vector, and that's narrow.

    # Option-A update-on-upgrade merge: per event, replace SUITE-owned groups
    # (track-changes OR verified-import) with the patch's groups, preserving any
    # third-party groups. The patch's per-event group order is preserved on the
    # right-hand side, so PreToolUse keeps the patch's verified-import-before-
    # track-changes ordering (F2). Always writes, so a stale `bash …` suite
    # registration is rewritten to the patch's `python …` command
    # (self-repairing) while remaining idempotent.
    settings.setdefault('hooks', {})
    added_events = []
    updated_events = []
    for event, groups in new_hooks.items():
        existing = settings['hooks'].get(event, [])
        had_suite = _has_suite_entry(existing)
        settings['hooks'][event] = _strip_suite_groups(existing) + list(groups)
        if had_suite:
            updated_events.append(event)
        else:
            added_events.append(event)

    # Write.
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')

    # Tally registered suite hook entries (for reporting): track-changes (5) +
    # verified-import (1) = 6 on a clean install.
    total = 0
    for groups in (settings.get('hooks') or {}).values():
        for group in groups or []:
            for h in (group or {}).get('hooks', []) or []:
                cmd = (h or {}).get('command', '') or ''
                if any(sig in cmd for sig in SUITE_SIGNATURES):
                    total += 1

    if added_events:
        print(f'added {len(added_events)} new event(s) into {settings_path}: {", ".join(added_events)}')
    if updated_events:
        print(f'updated {len(updated_events)} existing event(s) in {settings_path}: {", ".join(updated_events)}')
    if not added_events and not updated_events:
        print(f'{settings_path}: no suite events to merge (patch empty)')
    print(f'total suite hook entries registered: {total}')
    return 0


def main():
    if len(sys.argv) != 3:
        print('usage: python tc_settings_merge.py <patch.json> <settings.json>', file=sys.stderr)
        return 1
    return merge(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    sys.exit(main())
