#!/usr/bin/env bash
# lib/migrate-v1-to-v2.sh — Migrate v1 track-changes marks to v2 in place.
#
# Walks a directory tree, finds all .md / .qmd / .tex files, and rewrites
# v1-format highlight marks to v2 format. Idempotent: files containing
# only v2 marks are left unchanged.
#
# v1 → v2 transformations (Fix #7 strikethrough encoding):
#   Markdown:
#     <mark>[N] new text</mark>              → <mark>new text</mark><sup>N</sup>
#     <mark>[N] ~~old~~ → new</mark>         → <mark><s>old</s>new</mark><sup>N</sup>
#     <mark>[N] ~~removed~~</mark>           → <mark><s>removed</s></mark><sup>N</sup>
#     <mark>[N] Edit to following block: ..</mark>
#                                            → <mark>..</mark><sup>N</sup>
#
#   LaTeX:
#     \tc{N}{new text}                       → \tc{new text}\tcn{N}
#     \tc{N}{\st{old} → new}                 → \tc{\sout{old}new}\tcn{N}
#     \tc{N}{\st{removed}}                   → \tc{\sout{removed}}\tcn{N}
#     \tc{N}{Edit to following block: ..}    → \tc{..}\tcn{N}
#     (also converts \st{} to \sout{} inside v1 mark bodies during migration)
#
# Usage:
#   bash lib/migrate-v1-to-v2.sh <directory>
#
# Exit codes:
#   0  migration completed (may have modified zero or more files)
#   1  invalid arguments
#   2  python 3 missing or migration script error
#
# The script writes a one-line summary per modified file to stdout, and a
# final tally. Files with zero v1 marks are not mentioned.

set -u

TARGET_DIR="${1:-}"
if [ -z "${TARGET_DIR}" ] || [ ! -d "${TARGET_DIR}" ]; then
  echo "usage: bash migrate-v1-to-v2.sh <directory>" >&2
  echo "  target directory must exist" >&2
  exit 1
fi

# Resolve absolute path for cleaner output.
TARGET_ABS="$(cd "${TARGET_DIR}" && pwd)"

# Python 3 probe (mirrors hooks/pre-tool-use.sh::tc_resolve_python).
resolve_python3() {
  local cand
  for cand in python3 python "py -3" py; do
    if ${cand} -c "import sys; sys.exit(0 if sys.version_info[0] >= 3 else 49)" >/dev/null 2>&1; then
      printf '%s' "${cand}"
      return 0
    fi
  done
  return 1
}

PY="$(resolve_python3)" || {
  echo "migrate-v1-to-v2.sh: ERROR — Python 3 not found on PATH" >&2
  echo "  Probed: python3, python, 'py -3', py" >&2
  exit 2
}

TC_TARGET="${TARGET_ABS}" ${PY} - <<'PYEOF'
"""
v1 → v2 migration for track-changes marks.

Walks TC_TARGET recursively for .md, .qmd, .tex files. For each file,
detects v1 marks (markdown: <mark>[N] ...</mark>; latex: \tc{N}{...}),
rewrites to v2 form, writes back in place. Reports each modified file
plus a final tally.
"""
import os, re, sys

target = os.environ['TC_TARGET']

# ---------------------------------------------------------------------------
# Markdown v1 mark detection + rewrite.
# Multi-line via re.DOTALL since <mark>...</mark> can span lines.
# ---------------------------------------------------------------------------
MD_V1_RE = re.compile(r'<mark>\[(\d+)\]\s*(.*?)</mark>', re.DOTALL)

def md_rewrite_one(match):
    """Rewrite a single v1 markdown mark to v2 form (Fix #7 <s> encoding)."""
    n = match.group(1)
    body = match.group(2)
    # Strip "Edit to following block:" prose prefix if present (sibling form).
    body = re.sub(r'^Edit to following block:\s*', '', body)
    # Replacement detection: body contains `~~...~~ \s*→\s* new`.
    rep_m = re.match(r'^\s*~~(.*?)~~\s*→\s*(.*)$', body, re.DOTALL)
    if rep_m:
        old = rep_m.group(1)
        new = rep_m.group(2)
        # v2: <mark><s>old</s>new</mark><sup>N</sup>  (no arrow, adjacent)
        return f'<mark><s>{old}</s>{new}</mark><sup>{n}</sup>'
    # Deletion: body is entirely ~~...~~  (possibly with leading/trailing ws).
    del_m = re.match(r'^\s*~~(.*?)~~\s*$', body, re.DOTALL)
    if del_m:
        return f'<mark><s>{del_m.group(1)}</s></mark><sup>{n}</sup>'
    # Default: insertion (body is plain content).
    return f'<mark>{body}</mark><sup>{n}</sup>'

def md_migrate(text):
    """Run MD_V1_RE substitution; skip any v1 mark already followed by <sup>."""
    out = []
    pos = 0
    for m in MD_V1_RE.finditer(text):
        # Check whether this match is already followed by <sup>N</sup> —
        # if so, the file was already partly migrated; skip this match to
        # avoid double-wrapping.
        tail = text[m.end():m.end()+20]
        if re.match(r'^\s*<sup>\d+</sup>', tail):
            out.append(text[pos:m.end()])
            pos = m.end()
            continue
        out.append(text[pos:m.start()])
        out.append(md_rewrite_one(m))
        pos = m.end()
    out.append(text[pos:])
    return ''.join(out)

# ---------------------------------------------------------------------------
# LaTeX v1 mark detection.
# v1 form: \tc{N}{body}  — body uses balanced braces and may contain \st{}.
# We scan for \tc{<digits>}{ and walk braces to find the matching close.
# ---------------------------------------------------------------------------
TEX_V1_HEAD = re.compile(r'\\tc\{(\d+)\}\{')

def tex_extract_body(text, body_start):
    """From position right after the opening { of the body, return (body_end_excl, body_text).
    body_end_excl is the index of the matching closing brace (exclusive).
    Handles \{ \} \\ escapes and nested {...}.
    """
    depth = 1
    i = body_start
    L = len(text)
    while i < L and depth > 0:
        c = text[i]
        if c == '\\' and i + 1 < L:
            i += 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i, text[body_start:i]
        i += 1
    # Unmatched — return EOF as end.
    return L, text[body_start:L]

def tex_rewrite_body(body):
    """Convert a v1 body to v2 inner content.
    Strips 'Edit to following block:' prefix. Detects \st{...} → patterns
    for replacement, lone \st{...} for deletion. Converts \st → \sout.
    Returns the new inner content (what goes inside \tc{...}).
    """
    # Strip sibling prefix.
    body = re.sub(r'^Edit to following block:\s*', '', body)
    # Replacement: \st{old} → new   (the rest of body after the arrow)
    rep_m = re.match(r'^\s*\\st\{(.*?)\}\s*→\s*(.*)$', body, re.DOTALL)
    if rep_m:
        old = rep_m.group(1)
        new = rep_m.group(2)
        return f'\\sout{{{old}}}{new}'
    # Deletion: body is just \st{...}
    del_m = re.match(r'^\s*\\st\{(.*?)\}\s*$', body, re.DOTALL)
    if del_m:
        return f'\\sout{{{del_m.group(1)}}}'
    # Convert any inline \st to \sout (defensive).
    body = re.sub(r'\\st\{', r'\\sout{', body)
    return body

def tex_migrate(text):
    """Walk text, find v1 \tc{N}{...} marks, rewrite to \tc{...}\tcn{N}."""
    out = []
    pos = 0
    while True:
        m = TEX_V1_HEAD.search(text, pos)
        if not m:
            out.append(text[pos:])
            return ''.join(out)
        # Check if this is already v2 form: \tc{...}\tcn{N} would not match
        # this regex since v2's \tc takes one arg, not \tc{N}{. So if we
        # match TEX_V1_HEAD, it's v1.
        n = m.group(1)
        body_start = m.end()
        body_end, body = tex_extract_body(text, body_start)
        if body_end >= len(text) and text[body_end-1] != '}':
            # Unmatched braces — leave as-is and advance past the head.
            out.append(text[pos:m.end()])
            pos = m.end()
            continue
        # Check whether the original \tc was already followed by \tcn{N}
        # (already migrated). The character right after body_end (the
        # closing brace) should NOT be \tcn for unmigrated form.
        tail_start = body_end + 1
        tail = text[tail_start:tail_start+20]
        if re.match(r'^\\tcn\{\d+\}', tail):
            out.append(text[pos:tail_start])
            pos = tail_start
            continue
        new_inner = tex_rewrite_body(body)
        out.append(text[pos:m.start()])
        out.append(f'\\tc{{{new_inner}}}\\tcn{{{n}}}')
        pos = body_end + 1  # past the closing brace

# ---------------------------------------------------------------------------
# Walk the tree.
# ---------------------------------------------------------------------------
modified_count = 0
scanned_count = 0
modified_files = []

for root, dirs, files in os.walk(target):
    # Skip common noise dirs.
    dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', '__pycache__', '.venv', 'venv')]
    for fn in files:
        ext = os.path.splitext(fn)[1].lower()
        if ext not in ('.md', '.qmd', '.tex'):
            continue
        path = os.path.join(root, fn)
        try:
            with open(path, 'r', encoding='utf-8', newline='') as f:
                orig = f.read()
        except (IOError, UnicodeDecodeError):
            continue
        scanned_count += 1
        if ext in ('.md', '.qmd'):
            new_text = md_migrate(orig)
        else:
            new_text = tex_migrate(orig)
        if new_text != orig:
            try:
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    f.write(new_text)
                modified_count += 1
                rel = os.path.relpath(path, target)
                # Count rough number of changes (heuristic: count <sup> or \tcn) added.
                if ext in ('.md', '.qmd'):
                    n_changes = len(re.findall(r'<sup>\d+</sup>', new_text)) - len(re.findall(r'<sup>\d+</sup>', orig))
                else:
                    n_changes = len(re.findall(r'\\tcn\{\d+\}', new_text)) - len(re.findall(r'\\tcn\{\d+\}', orig))
                modified_files.append((rel, n_changes))
            except IOError as e:
                print(f"  ERROR writing {path}: {e}", file=sys.stderr)

print(f"track-changes migration: scanned {scanned_count} file(s), modified {modified_count}")
for rel, n in modified_files:
    print(f"  {rel}: {n} mark(s) migrated v1 → v2")
PYEOF

exit $?
