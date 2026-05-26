"""tc_resolve — §5 batch mark resolution (C10).

Implements the `/tc list | accept | reject | accept-all | reject-all`
subcommands. Resolution edits the tracked file directly:

  - accept => keep the mark's `new` text, strip the
    `<mark>...</mark><sup>N</sup>` wrapper (and any `<s>...</s>` /
    `~~...~~` strikethrough of the old text).
  - reject => restore the mark's `old` text, strip the wrapper.

Supports `.md` / `.qmd` (`<mark>` form) and `.tex` (`\\tc{}\\tcn{}` form).

Explicit audit attribution (F7): every resolution writes a log entry with
`decision: explicit` so a later PostToolUse Fix #8 *inference* never
overwrites the human's recorded choice. The mark cache is also updated to
the post-resolution mark set, so a subsequent edit diffs against the
already-resolved state and does not re-infer these marks.

Reuses the offset-bearing mark extractors in tc_analyzer
(`_md_extract_marks` / `_tex_extract_marks`, which return character offsets)
and the path/cache/log helpers in tc_core.audit (single source of truth; the
v2 `tc_audit` shim was removed in v3 C2). The line-based mark extractor for
the cache comes from tc_core.grammar.

Module-level regexes compiled once at import (matches house style).
Best-effort, fail-open I/O for the audit side effects: a logging failure
never aborts the resolution edit.

Public API:
    parse_ranges(spec, max_n) -> sorted list[int]
    list_marks(path) -> list[dict]                       (for `/tc list`)
    resolve(path, decision, ns) -> dict                  (accept|reject of a set)
    main(argv) -> int                                    (CLI entry)
"""
import os
import re
import sys
import json
import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import tc_analyzer            # offset-bearing mark extractors + classification
from tc_core import audit as tc_audit      # path/cache/log helpers
from tc_core import grammar as tc_grammar  # line-based mark extractor (cache)


def file_type(path):
    p = path.lower()
    if p.endswith('.md'):
        return 'md'
    if p.endswith('.qmd'):
        return 'qmd'
    if p.endswith('.tex'):
        return 'tex'
    return 'other'


# ---------------------------------------------------------------------------
# Range parsing: "1-25,!7,!11" -> {1..25} - {7,11}.
# Grammar: comma-separated terms. A term is either
#   <a>        single number
#   <a>-<b>    inclusive range (a<=b)
#   !<a>       exclude single number
#   !<a>-<b>   exclude inclusive range
# Whitespace around terms is ignored.
# ---------------------------------------------------------------------------
_RANGE_TERM_RE = re.compile(r'^(?P<bang>!)?(?P<a>\d+)(?:-(?P<b>\d+))?$')


def parse_ranges(spec, max_n=None):
    """Parse a range spec into a sorted list of ints. `max_n`, if given, is
    used only to validate (out-of-range numbers are kept; the caller decides
    what to do with numbers that have no matching mark). Raises ValueError on
    a malformed term."""
    include = set()
    exclude = set()
    if spec is None:
        return []
    for raw in spec.split(','):
        term = raw.strip()
        if not term:
            continue
        m = _RANGE_TERM_RE.match(term)
        if not m:
            raise ValueError("bad range term: %r" % term)
        a = int(m.group('a'))
        b = int(m.group('b')) if m.group('b') is not None else a
        if b < a:
            a, b = b, a
        target = exclude if m.group('bang') else include
        for v in range(a, b + 1):
            target.add(v)
    result = sorted(include - exclude)
    return result


# ---------------------------------------------------------------------------
# Mark extraction (with character offsets) reusing tc_analyzer.
# ---------------------------------------------------------------------------

def _extract_marks_with_offsets(text, ftype):
    if ftype in ('md', 'qmd'):
        return tc_analyzer._md_extract_marks(text)
    if ftype == 'tex':
        return tc_analyzer._tex_extract_marks(text)
    return []


def _preview(s, limit=60):
    one = ' '.join((s or '').split())
    if len(one) > limit:
        one = one[:limit - 3] + '...'
    return one


def list_marks(path):
    """Return a list of {N, type, line, old, new, preview} for every mark in
    the file, in document order. Raises IOError if the file cannot be read."""
    ftype = file_type(path)
    if ftype == 'other':
        raise ValueError("unsupported file type: %s" % path)
    with open(path, 'r', encoding='utf-8', newline='') as f:
        text = f.read()
    text = text.replace('\r\n', '\n')
    marks = _extract_marks_with_offsets(text, ftype)
    out = []
    for m in marks:
        t = m['type']
        if t == 'deletion':
            preview = '[delete] ' + _preview(m['old'])
        elif t == 'replacement':
            preview = _preview(m['old']) + ' -> ' + _preview(m['new'])
        else:
            preview = _preview(m['new'])
        line_no = 1 + text.count('\n', 0, m['start'])
        out.append({'N': m['N'], 'type': t, 'line': line_no,
                    'old': m['old'], 'new': m['new'], 'preview': preview})
    return out


# ---------------------------------------------------------------------------
# Resolution: rewrite the file applying accept/reject to a set of mark Ns.
# ---------------------------------------------------------------------------

def _resolved_replacement(mark, decision):
    """Return the literal text that should replace the whole
    <mark>...</mark><sup>N</sup> (or \\tc{...}\\tcn{N}) span for the given
    decision. accept => keep new; reject => restore old."""
    if decision == 'accept':
        return mark['new']
    # reject
    return mark['old']


def _owned_line_empty_span(text, start, end, repl):
    """Fix #6: detect a resolved mark that OWNED its own line and whose
    replacement collapses the line to empty, returning the span to remove so
    no orphan blank line remains.

    The mark owns its line when, on the ORIGINAL `text`:
      - the chars from the line start (after the preceding '\\n' or BOF) up to
        `start` are all whitespace, AND
      - the chars from `end` to the line end (next '\\n' or EOF) are all
        whitespace, AND
      - `repl` (the resolution text) is empty or whitespace-only.

    Returns a (seg_start, seg_end) pair to remove instead of [start:end]:
      - Base case: remove the mark line through its trailing '\\n' (inclusive),
        dropping the empty line that an '' replacement would otherwise leave.
        At EOF (no trailing '\\n') the span stops at end-of-text.
      - Block-paragraph case: when the owned line is flanked by blank-line
        separators on BOTH sides (a brand-new-block / deleted-paragraph
        sibling), the two separators would collapse to two adjacent blank
        lines (triple-spacing). Consume ONE following blank line too so a
        single separator remains.

    Returns None when the mark is mid-line (inline) or leaves non-empty
    content on the line — those keep the ordinary [start:end] splice.
    """
    if repl.strip() != '':
        return None
    # Line start: just after the previous '\n' (or beginning of file).
    nl_before = text.rfind('\n', 0, start)
    line_start = 0 if nl_before == -1 else nl_before + 1
    # Leading chars on the line before the mark must be whitespace.
    if text[line_start:start].strip() != '':
        return None
    # Line end: the next '\n' at or after `end` (or EOF).
    nl_after = text.find('\n', end)
    at_eof = nl_after == -1
    line_end = len(text) if at_eof else nl_after
    # Trailing chars on the line after the mark must be whitespace.
    if text[end:line_end].strip() != '':
        return None
    if at_eof:
        return (line_start, line_end)
    swallow_end = nl_after + 1  # swallow the mark line's own trailing newline

    # Block-paragraph collapse: only when the owned line is flanked by blank
    # lines on BOTH sides. "Preceded by a blank line" => the char before
    # line_start is a '\n' that terminates an empty line (line_start-1 is '\n'
    # and the line before it is also empty/BOF). Practically: line_start >= 1
    # and text[line_start-1] == '\n'. "Followed by a blank line" => the line
    # starting at swallow_end is empty (next char is '\n' or EOF-with-no-text).
    preceded_blank = line_start >= 1 and text[line_start - 1] == '\n'
    next_nl = text.find('\n', swallow_end)
    if next_nl == -1:
        followed_blank = text[swallow_end:].strip() == '' and swallow_end < len(text)
        follow_end = len(text)
    else:
        followed_blank = text[swallow_end:next_nl].strip() == ''
        follow_end = next_nl + 1
    if preceded_blank and followed_blank:
        swallow_end = follow_end
    return (line_start, swallow_end)


def resolve(path, decision, ns):
    """Apply `decision` ('accept' | 'reject') to the marks whose N is in
    `ns` (a collection of string or int values). Edits the file in place,
    writes an explicit-attribution audit entry, and updates the mark cache.

    Returns a dict:
      {'resolved': [N...], 'not_found': [N...], 'remaining': [N...],
       'wrote_file': bool, 'wrote_log': bool}
    """
    if decision not in ('accept', 'reject'):
        raise ValueError("decision must be 'accept' or 'reject'")
    ftype = file_type(path)
    if ftype == 'other':
        raise ValueError("unsupported file type: %s" % path)
    want = set(str(n) for n in ns)

    with open(path, 'r', encoding='utf-8', newline='') as f:
        original = f.read()
    text = original.replace('\r\n', '\n')
    marks = _extract_marks_with_offsets(text, ftype)
    by_n = {m['N']: m for m in marks}

    resolved = []
    not_found = sorted((n for n in want if n not in by_n), key=_n_key)

    # Apply replacements right-to-left so earlier offsets stay valid.
    targets = [m for m in marks if m['N'] in want]
    targets.sort(key=lambda m: m['start'], reverse=True)
    new_text = text
    resolved_marks = []
    for m in targets:
        repl = _resolved_replacement(m, decision)
        # Fix #6: if the mark owned its own line and the replacement collapses
        # that line to empty, swallow the whole line (incl. its trailing '\n')
        # so no orphan blank line remains. Detection uses the ORIGINAL `text`
        # (offsets are valid there); the splice into `new_text` is safe under
        # the right-to-left order because an owned line carries no other mark.
        span = _owned_line_empty_span(text, m['start'], m['end'], repl)
        if span is not None:
            seg_start, seg_end = span
            new_text = new_text[:seg_start] + repl + new_text[seg_end:]
        else:
            new_text = new_text[:m['start']] + repl + new_text[m['end']:]
        resolved.append(m['N'])
        resolved_marks.append(m)
    resolved = sorted(set(resolved), key=_n_key)

    wrote_file = False
    if new_text != text:
        # Preserve the file's original EOL convention (best-effort): if the
        # original used CRLF, re-apply it. Otherwise write LF.
        out_text = new_text
        if '\r\n' in original and '\r\n' not in out_text:
            out_text = out_text.replace('\n', '\r\n')
        with open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(out_text)
        wrote_file = True

    remaining = sorted((m['N'] for m in marks if m['N'] not in want), key=_n_key)

    # Audit attribution (explicit) + cache update. Best-effort.
    wrote_log = _write_explicit_audit(path, ftype, decision, resolved_marks,
                                      new_text)
    _update_cache(path, ftype, new_text)

    return {'resolved': resolved, 'not_found': not_found,
            'remaining': remaining, 'wrote_file': wrote_file,
            'wrote_log': wrote_log}


def _n_key(n):
    try:
        return (0, int(n))
    except (TypeError, ValueError):
        return (1, str(n))


# ---------------------------------------------------------------------------
# Audit side effects.
# ---------------------------------------------------------------------------

def _write_explicit_audit(path, ftype, decision, resolved_marks, post_text):
    """Append a `resolved:` block carrying `decision: explicit` (F7) so a
    later Fix #8 inference never re-classifies these marks. Best-effort."""
    if not resolved_marks:
        return False
    abs_path = os.path.abspath(path)
    log_path = tc_audit.log_path_for(abs_path)
    root = tc_audit.find_project_root(abs_path)
    if root:
        try:
            rel = os.path.relpath(abs_path, root).replace(os.sep, '/')
        except ValueError:
            rel = os.path.basename(abs_path)
    else:
        rel = os.path.basename(abs_path)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lines = [f"\n## {ts} -- {rel}  (/tc {decision})"]
    lines.append("resolved:")
    for m in sorted(resolved_marks, key=lambda mm: _n_key(mm['N'])):
        lines.append(f"  - mark: {m['N']}")
        lines.append(f"    was_type: {m.get('type', '?')}")
        lines.append(f"    decision: explicit")
        lines.append(f"    action: {'accepted' if decision == 'accept' else 'rejected'}")
        if m.get('old', ''):
            lines.append(f"    was_old: {tc_audit._fmt_str(m['old'])}")
        if m.get('new', ''):
            lines.append(f"    was_new: {tc_audit._fmt_str(m['new'])}")
    entry = '\n'.join(lines) + '\n'
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if not os.path.exists(log_path):
            header = (
                "# track-changes history\n"
                "#\n"
                "# Append-only audit log of AI-introduced and AI-introduced-then-resolved\n"
                "# marks for tracked files in this project. Each entry records one\n"
                "# Write/Edit/MultiEdit or explicit /tc resolution. Diffable + greppable.\n"
                "#\n"
                "# Generated and maintained by the track-changes skill.\n"
                "# Do not edit by hand (append-only). To reset: delete this file.\n"
            )
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(header)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(entry)
        return True
    except (IOError, OSError):
        return False


def _update_cache(path, ftype, post_text):
    """Rewrite the mark cache to the post-resolution mark set so a subsequent
    PostToolUse `record()` sees no spurious diff for the resolved marks (and
    therefore does not run Fix #8 inference over them). Best-effort."""
    abs_path = os.path.abspath(path)
    cache_path = tc_audit.cache_path_for(abs_path)
    if not cache_path:
        return
    current_marks = tc_grammar.extract_marks(post_text, ftype)
    prior = {}
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                prior = json.load(f)
        except (IOError, ValueError):
            prior = {}
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({'file': abs_path, 'marks': current_marks,
                       'imported_keys': prior.get('imported_keys', []),
                       'lineage_keys': prior.get('lineage_keys', [])}, f)
    except (IOError, OSError):
        pass


# ---------------------------------------------------------------------------
# CLI entry point. Invoked by lib/tc-cli.sh:
#   tc_resolve.py list       <file>
#   tc_resolve.py accept     <file> <ranges>
#   tc_resolve.py reject     <file> <ranges>
#   tc_resolve.py accept-all <file>
#   tc_resolve.py reject-all <file>
# ---------------------------------------------------------------------------

def _cmd_list(path):
    try:
        marks = list_marks(path)
    except (IOError, OSError):
        sys.stderr.write(f"tc: ERROR -- cannot read file: {path}\n")
        return 2
    except ValueError as e:
        sys.stderr.write(f"tc: ERROR -- {e}\n")
        return 2
    if not marks:
        print(f"tc: no marks in {path}")
        return 0
    print(f"tc: {len(marks)} mark(s) in {path}")
    for m in marks:
        print(f"  [{m['N']}] line {m['line']} ({m['type']}): {m['preview']}")
    return 0


def _cmd_resolve(path, decision, spec, all_marks=False):
    try:
        existing = list_marks(path)
    except (IOError, OSError):
        sys.stderr.write(f"tc: ERROR -- cannot read file: {path}\n")
        return 2
    except ValueError as e:
        sys.stderr.write(f"tc: ERROR -- {e}\n")
        return 2
    existing_ns = [m['N'] for m in existing]
    if all_marks:
        ns = existing_ns
    else:
        max_n = 0
        for n in existing_ns:
            try:
                max_n = max(max_n, int(n))
            except ValueError:
                pass
        try:
            wanted_ints = parse_ranges(spec, max_n)
        except ValueError as e:
            sys.stderr.write(f"tc: ERROR -- {e}\n")
            return 1
        wanted = set(str(i) for i in wanted_ints)
        ns = [n for n in existing_ns if n in wanted]
        # Numbers requested but with no matching mark are reported below.
        missing = sorted((str(i) for i in wanted_ints if str(i) not in set(existing_ns)),
                         key=_n_key)
        if missing:
            sys.stderr.write("tc: note -- no mark for: %s\n" % ', '.join(missing))
    if not ns:
        print(f"tc: no matching marks to {decision} in {path}")
        return 0
    try:
        res = resolve(path, decision, ns)
    except (IOError, OSError):
        sys.stderr.write(f"tc: ERROR -- cannot write file: {path}\n")
        return 2
    except ValueError as e:
        sys.stderr.write(f"tc: ERROR -- {e}\n")
        return 2
    verb = 'accepted' if decision == 'accept' else 'rejected'
    print("tc: %s mark(s) %s in %s: %s"
          % (len(res['resolved']), verb, path,
             ', '.join(res['resolved']) or '(none)'))
    if res['remaining']:
        print("tc: %d mark(s) remain: %s"
              % (len(res['remaining']), ', '.join(res['remaining'])))
    return 0


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: tc_resolve.py "
                         "list|accept|reject|accept-all|reject-all <file> [ranges]\n")
        return 1
    sub = argv[0]
    path = argv[1]
    if sub == 'list':
        return _cmd_list(path)
    if sub == 'accept-all':
        return _cmd_resolve(path, 'accept', None, all_marks=True)
    if sub == 'reject-all':
        return _cmd_resolve(path, 'reject', None, all_marks=True)
    if sub in ('accept', 'reject'):
        if len(argv) < 3:
            sys.stderr.write(f"tc {sub}: missing <ranges> argument "
                             f"(e.g. 1-25,!7,!11)\n")
            return 1
        return _cmd_resolve(path, sub, argv[2])
    sys.stderr.write(f"tc_resolve.py: unknown subcommand: {sub}\n")
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
