"""tc_settings_merge.py — merge track-changes hook registrations into
~/.claude/settings.json (Fix #14).

Used by the bootstrap installer so the curl-based deployment doesn't need
to inline ~80 lines of jq. The local `bash install.sh` still uses its own
jq merge — this Python version is the equivalent for remote installs.

Usage:
    python tc_settings_merge.py <patch_path> <settings_path>

Behavior:
- If <settings_path> doesn't exist, writes the patch verbatim (pretty-printed).
- Otherwise: idempotently appends track-changes hook entries to each event
  array. An entry is identified as track-changes-owned if its `command` field
  contains the substring `track-changes/hooks/`. Existing track-changes
  entries are LEFT IN PLACE (idempotent), but the patch's entry is added if
  no track-changes entry exists for that event.
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


SIGNATURE = 'track-changes/hooks/'


def _has_tc_entry(event_groups):
    """True if any entry in `event_groups` (a list of dicts containing
    `hooks`) has a hook whose command mentions the track-changes signature."""
    if not isinstance(event_groups, list):
        return False
    for group in event_groups:
        if not isinstance(group, dict):
            continue
        for h in group.get('hooks', []) or []:
            cmd = (h or {}).get('command', '') or ''
            if SIGNATURE in cmd:
                return True
    return False


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

    # Idempotent merge.
    settings.setdefault('hooks', {})
    added_events = []
    for event, groups in new_hooks.items():
        settings['hooks'].setdefault(event, [])
        if _has_tc_entry(settings['hooks'][event]):
            continue
        settings['hooks'][event].extend(groups)
        added_events.append(event)

    # Write.
    with open(settings_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
        f.write('\n')

    # Tally registered TC entries (for reporting).
    total = 0
    for groups in (settings.get('hooks') or {}).values():
        for group in groups or []:
            for h in (group or {}).get('hooks', []) or []:
                if SIGNATURE in ((h or {}).get('command', '') or ''):
                    total += 1

    if added_events:
        print(f'merged {len(added_events)} new event(s) into {settings_path}: {", ".join(added_events)}')
    else:
        print(f'{settings_path} already has track-changes entries for all events (idempotent no-op)')
    print(f'total track-changes hook entries registered: {total}')
    return 0


def main():
    if len(sys.argv) != 3:
        print('usage: python tc_settings_merge.py <patch.json> <settings.json>', file=sys.stderr)
        return 1
    return merge(sys.argv[1], sys.argv[2])


if __name__ == '__main__':
    sys.exit(main())
