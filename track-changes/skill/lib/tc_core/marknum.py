"""tc_core.marknum — the canonical mark-number allocator (9.9.0, seed C4).

track-changes has a SINGLE per-file mark-number space shared by inline marks and
whole-region insertions. Two skills now mint numbers into it (tc-polish since v5,
tc-edits since 9.9.0), and a hand-split of a region mints a third way, so the
computation has to live in exactly one place or the numbers collide. It did once:
before 9.6.0 the polish engine counted only inline `<sup>N</sup>` and reported
"next = 1" for a document whose §3 already held regions 14-29.

This module is that one place. `polish_engine.next_mark_n` delegates here (keeping a
local copy only as a degraded-mode fallback for a tc-polish installed against an
older track-changes), and a test asserts the two agree so the fallback cannot
quietly drift.

The four forms that occupy the number space:
    markdown inline   ...</mark><sup>N</sup>
    LaTeX  inline     \\tcn{N}
    markdown region   ::: {.tc-region tc-n="N" ...}
    LaTeX  region     \\begin{tcregion}{N}
"""
import re

_MD_NUM_RE = re.compile(r"</mark><sup>(\d+)</sup>")
_TEX_NUM_RE = re.compile(r"\\tcn\{(\d+)\}")
_MD_REGION_NUM_RE = re.compile(r'tc-n\s*=\s*"(\d+)"')
_TEX_REGION_NUM_RE = re.compile(r"\\begin\{tcregion\}\{(\d+)\}")


def used_numbers(text):
    """Every mark number occupied in `text`, across all four forms, sorted."""
    nums = ([int(x) for x in _MD_NUM_RE.findall(text)]
            + [int(x) for x in _TEX_NUM_RE.findall(text)]
            + [int(x) for x in _MD_REGION_NUM_RE.findall(text)]
            + [int(x) for x in _TEX_REGION_NUM_RE.findall(text)])
    return sorted(set(nums))


def next_mark_n(text):
    """The next free mark number: max(all used) + 1, or 1 in a document with none.

    Deliberately max+1 rather than lowest-unused — mark numbers are a review
    shorthand ("accept 1-25 except 7 and 11") and reusing a resolved number would
    make an audit-log range ambiguous across time.
    """
    nums = used_numbers(text)
    return (nums[-1] + 1) if nums else 1
