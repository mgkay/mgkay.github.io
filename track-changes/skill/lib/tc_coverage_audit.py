"""tc_coverage_audit.py — the `/tc coverage` command (audit mode, 8.2.0).

Thin CLI wrapper over tc_core.coverage: whole-document completeness check of
a target document against a source/staging file. For each source unit
(`<!-- slide N -->` marker; the whole file when no markers), report the % of
content tokens covered and list the missing ones. Run it before declaring a
document done.

Usage:
    tc_coverage_audit.py <doc> <source> [--units N,N,...]

`--slides` is accepted as an alias for `--units` (continuity with the
reference ISE754 coverage_check.py).

Exit codes: 0 all requested units fully covered; 1 any unit dropped content
(or a requested unit was not found); 2 usage / read error.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tc_core import coverage  # noqa: E402

_USAGE = 'usage: /tc coverage <doc> <source> [--units N,N,...]'


def _out(text):
    """UTF-8-safe print (mirrors the suite's _emit convention)."""
    line = text if text.endswith('\n') else text + '\n'
    try:
        sys.stdout.buffer.write(line.encode('utf-8'))
        sys.stdout.buffer.flush()
    except (AttributeError, ValueError):
        sys.stdout.write(line)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    units_arg = ''
    pos = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ('--units', '--slides'):
            if i + 1 >= len(argv):
                sys.stderr.write('%s missing value\n%s\n' % (a, _USAGE))
                return 2
            units_arg = argv[i + 1]
            i += 2
            continue
        if a.startswith('--units=') or a.startswith('--slides='):
            units_arg = a.split('=', 1)[1]
            i += 1
            continue
        pos.append(a)
        i += 1
    if len(pos) != 2:
        sys.stderr.write(_USAGE + '\n')
        return 2
    doc_path, src_path = pos

    try:
        doc_text = coverage.read_slice(doc_path)
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write('tc coverage: cannot read %s (%s)\n' % (doc_path, e))
        return 2
    try:
        src_text = coverage.read_slice(src_path)
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write('tc coverage: cannot read %s (%s)\n' % (src_path, e))
        return 2

    doc_tokens = coverage.tokenize(doc_text)
    units = coverage.parse_units(src_text)

    if not units:
        # No unit markers: audit the whole source as one unit (reported, not
        # silently skipped).
        _out('tc coverage: no unit markers (<!-- slide N -->) in %s -- '
             'auditing the whole source as one unit.' % src_path)
        units = {0: src_text}
        want = [0]
        label = {0: 'source'}
    else:
        if units_arg:
            try:
                want = [int(s) for s in units_arg.split(',') if s.strip()]
            except ValueError:
                sys.stderr.write('tc coverage: bad --units value: %s\n'
                                 % units_arg)
                return 2
        else:
            want = sorted(units)
        label = {n: 'unit %d' % n for n in units}
        for n in want:
            label.setdefault(n, 'unit %d' % n)

    any_missing = False
    for n in want:
        if n not in units:
            _out('%s: NOT FOUND in %s' % (label[n], src_path))
            any_missing = True
            continue
        src = coverage.tokenize(units[n])
        missing = sorted(src - doc_tokens)
        cov = 100 * (len(src) - len(missing)) // max(1, len(src))
        flag = '' if not missing else '  <-- review'
        _out('%s: %d%% covered, %d missing%s'
             % (label[n], cov, len(missing), flag))
        if missing:
            any_missing = True
            _out('    ' + ', '.join(missing))
    return 1 if any_missing else 0


if __name__ == '__main__':
    sys.exit(main())
