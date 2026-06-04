#!/usr/bin/env python3
"""polish_engine — the deterministic core of the `polish` skill.

`polish` cleans up voice-dictated document prose (speech-recognition errors,
grammar, dropped words) and surfaces every fix as an ordinary track-changes
`<mark>`, so the existing review discipline stays intact. This module is the
*deterministic infrastructure*; the actual choice of which prose errors to fix
is the model's job, guided by SKILL.md. The engine:

  1. Computes the **dictated scope** — what the human newly dictated since the
     git baseline — by diffing baseline vs on-disk over pandoc `Str` tokens
     (document order, skipping Code/Math/RawInline). This is the source-level,
     git-authoritative answer to "what is new to polish"; it scopes the fixes
     to the new prose so an already-vetted document is not re-polished.
  2. Flags **protected tokens** in the dictated scope (the jargon/code/math
     bright line: never auto-correct an unrecognized token — leave + flag).
  3. Reports **non-rendering regions** so the skill does not attempt a fix that
     the track-changes hook would block and route to /draft.
  4. Computes the next free **mark number** so polish's fixes never collide with
     existing marks.
  5. Appends a `dictated:` **audit breadcrumb** to `.tc-history.md` (additive;
     track-changes never reads that file back — it diffs its own .marks cache).

There is no view-time "dictated lens": an earlier design shaded the new
dictation a second color in the rendered HTML via a positional manifest + a Lua
filter. It was retired because the manifest (built over the *source* token
stream) could not be trusted to align with Quarto's *executed* token stream in a
real lecture (injected caption/cross-ref text, code output), so it silently
missed changes. For "what did I change," `git diff` is the authoritative view.

Tokenization rule: token = a pandoc `Str` node, in document order; Code / Math /
RawInline carry text in a string field (not Str children) so they never enter
the stream and are protected by construction.

CLI:
  python polish_engine.py analyze <file> [--baseline-ref REF]
      -> prints a JSON report (scope, flags, regions, next mark number).
  python polish_engine.py audit <file> --runs N --mode M2 [--flagged a,b]
      -> appends a `dictated:` breadcrumb to .tc-history.md.

Best-effort and non-destructive: analyze never edits the target and writes no
files; audit only appends. Requires `pandoc` and (for M2) `git` on PATH.
"""
import argparse
import datetime
import difflib
import json
import os
import re
import subprocess
import sys

# --- tokenization (pandoc Str-node stream) ---------------------------------

_PROTECTED_INLINE = {"Code", "Math", "RawInline"}


def _walk_inlines(inlines, out):
    for el in inlines:
        if not isinstance(el, dict):
            continue
        t = el.get("t")
        if t == "Str":
            out.append(el.get("c", ""))
        elif t in _PROTECTED_INLINE:
            continue
        else:
            c = el.get("c")
            if isinstance(c, list):
                if t in ("Link", "Image") and len(c) >= 2 and isinstance(c[1], list):
                    _walk_inlines(c[1], out)
                elif all(isinstance(x, dict) and "t" in x for x in c):
                    _walk_inlines(c, out)


def _walk_blocks(blocks, out):
    for b in blocks:
        if not isinstance(b, dict):
            continue
        t = b.get("t")
        c = b.get("c")
        if t in ("CodeBlock", "RawBlock"):
            continue
        if t in ("Para", "Plain"):
            _walk_inlines(c, out)
        elif t == "Header" and isinstance(c, list) and len(c) == 3:
            _walk_inlines(c[2], out)
        elif isinstance(c, list):
            for item in c:
                if isinstance(item, list) and item and isinstance(item[0], dict) and "t" in item[0]:
                    _walk_blocks(item, out)
                elif isinstance(item, dict) and item.get("t"):
                    _walk_blocks([item], out)


def pandoc_tokens(text):
    """Return the ordered list of pandoc Str-node strings for markdown `text`."""
    try:
        js = subprocess.run(
            ["pandoc", "-f", "markdown", "-t", "json"],
            input=text, capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError("pandoc is required (and must be on PATH): %s" % e)
    doc = json.loads(js)
    out = []
    _walk_blocks(doc.get("blocks", []), out)
    return out


# --- track-changes mark stripping (so unresolved marks don't pollute diff) --

# Reduce a mark to its *effective accepted text* before tokenizing:
#   insertion  <mark>NEW</mark><sup>N</sup>            -> NEW
#   deletion   <mark><s>OLD</s></mark><sup>N</sup>     -> (removed)
#   replacement<mark><s>OLD</s>NEW</mark><sup>N</sup>  -> NEW
_MARK_RE = re.compile(r"<mark>(.*?)</mark><sup>\d+</sup>", re.DOTALL)
_DEL_INNER_RE = re.compile(r"<s>.*?</s>", re.DOTALL)
_TEX_MARK_RE = re.compile(r"\\tc\{(.*?)\}\\tcn\{\d+\}", re.DOTALL)
_TEX_SOUT_RE = re.compile(r"\\sout\{.*?\}", re.DOTALL)


def strip_marks(text):
    """Remove track-changes mark wrappers, leaving effective accepted prose."""
    def _md(m):
        body = m.group(1)
        return _DEL_INNER_RE.sub("", body)  # drop struck text, keep NEW
    def _tex(m):
        body = m.group(1)
        return _TEX_SOUT_RE.sub("", body)
    text = _MARK_RE.sub(_md, text)
    text = _TEX_MARK_RE.sub(_tex, text)
    return text


# --- git baseline ----------------------------------------------------------

def _git_root(path):
    d = os.path.dirname(os.path.abspath(path))
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, encoding="utf-8", check=True)
        return r.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_baseline(path, ref="HEAD"):
    """Return (text, info). text is the file content at `ref`, or None if the
    file is untracked / has no committed version. info carries warnings."""
    root = _git_root(path)
    info = {"git_root": root, "warnings": []}
    if not root:
        info["warnings"].append("not a git repository — no baseline; treating whole file as M1")
        return None, info
    rel = os.path.relpath(os.path.abspath(path), root).replace(os.sep, "/")
    try:
        r = subprocess.run(["git", "-C", root, "show", "%s:%s" % (ref, rel)],
                           capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError:
        info["warnings"].append("git not available — no baseline; treating whole file as M1")
        return None, info
    if r.returncode != 0:
        info["warnings"].append("no committed baseline for this file at %s — treating whole file as M1 (untracked/new)" % ref)
        return None, info
    # Dirty-tree honesty (F5a): we cannot distinguish prior uncommitted
    # non-dictation edits from this session's dictation via git alone.
    st = subprocess.run(["git", "-C", root, "status", "--porcelain", "--", rel],
                        capture_output=True, text=True, encoding="utf-8")
    if st.stdout.strip():
        info["warnings"].append(
            "working tree has uncommitted changes to this file; ALL changes since "
            "%s are treated as new dictated input. Commit a baseline first to "
            "scope only this session's dictation." % ref)
    info["baseline_ref"] = ref
    return r.stdout, info


# --- protected-token classification (F4 bright line) -----------------------

_GREEK_OR_NONASCII_RE = re.compile(r"[^\x00-\x7f]")
_DIGIT_LETTER_MIX_RE = re.compile(r"(?=.*[A-Za-z])(?=.*\d)")
_ALLCAPS_RE = re.compile(r"^[A-Z]{2,}$")
_PUNCT_STRIP_RE = re.compile(r"^[^\w$\\]+|[^\w$\\]+$", re.UNICODE)

# Typographic punctuation that is ordinary English prose, not a symbol/jargon
# signal: smart single/double quotes, en/em dashes, ellipsis. These are folded
# to ASCII before the non-ASCII test so contractions/possessives dictated with
# a smart apostrophe (it's, they're, item's) stay eligible for polishing rather
# than being mis-flagged as protected. Genuine symbols/Greek (αvhq) and units
# like the prime ′ are intentionally NOT folded, so they remain protected.
_TYPOGRAPHIC_TO_ASCII = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-", "―": "-",
    "…": "...",
})


def _load_allowlist(path):
    """Domain-term allowlist: project .polish-allowlist (one term per line) plus
    a built-in seed. User-extensible."""
    seed = {"LTL", "TLC", "Kcu", "ppi", "qmax", "totlogcost", "Logjam",
            "Logentics", "makeLogjam", "Julia", "Quarto", "ISE"}
    terms = set(seed)
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    s = line.strip()
                    if s and not s.startswith("#"):
                        terms.add(s)
        except OSError:
            pass
    return terms


def is_protected_token(tok, allowlist):
    """True if `tok` is NOT positively identifiable as English prose and must be
    left untouched + flagged. Conservative: when in doubt, protect."""
    core = _PUNCT_STRIP_RE.sub("", tok)
    if not core:
        return False
    if core in allowlist:
        return True
    if _ALLCAPS_RE.match(core):
        return True                       # acronym: LTL, TLC
    if "_" in core:
        return True                       # code-ish: total_cost, q_max
    if _DIGIT_LETTER_MIX_RE.match(core) and re.search(r"\d", core):
        return True                       # q0, x1, q0star
    if _GREEK_OR_NONASCII_RE.search(core.translate(_TYPOGRAPHIC_TO_ASCII)):
        return True                       # αvhq, q₀ (genuine symbols/Greek; not smart quotes)
    if "$" in tok or "\\" in tok:
        return True                       # stray math/tex remnant
    return False


# --- non-rendering region detection (F3) -----------------------------------

_FENCE_RE = re.compile(r"^\s{0,3}(```|~~~)")
_DISPLAY_MATH_RE = re.compile(r"^\s*\$\$\s*$")
_QFD_OPEN_RE = re.compile(r"^\s*:::+\s*\S.*$")
_QFD_CLOSE_RE = re.compile(r"^\s*:::+\s*$")
_YAML_RE = re.compile(r"^---\s*$")


def nonrendering_line_ranges(text):
    """Return [(start_line, end_line, kind)] (1-indexed, inclusive) of regions a
    track-changes fix may not be placed inside (the hook blocks → /draft)."""
    lines = text.split("\n")
    n = len(lines)
    out = []
    i = 0
    # YAML frontmatter (only at very top)
    if n and _YAML_RE.match(lines[0]):
        j = 1
        while j < n and not _YAML_RE.match(lines[j]):
            j += 1
        out.append((1, min(j + 1, n), "yaml"))
        i = j + 1
    while i < n:
        line = lines[i]
        if _FENCE_RE.match(line):
            fence = _FENCE_RE.match(line).group(1)
            close = re.compile(r"^\s{0,3}" + re.escape(fence) + r"\s*$")
            j = i + 1
            while j < n and not close.match(lines[j]):
                j += 1
            out.append((i + 1, min(j + 1, n), "fenced-code"))
            i = j + 1
            continue
        if _DISPLAY_MATH_RE.match(line):
            j = i + 1
            while j < n and not _DISPLAY_MATH_RE.match(lines[j]):
                j += 1
            out.append((i + 1, min(j + 1, n), "display-math"))
            i = j + 1
            continue
        if _QFD_OPEN_RE.match(line):
            j = i + 1
            while j < n and not _QFD_CLOSE_RE.match(lines[j]):
                j += 1
            out.append((i + 1, min(j + 1, n), "quarto-div"))
            i = j + 1
            continue
        i += 1
    return out


# --- mark numbering (F6) ----------------------------------------------------

_MD_NUM_RE = re.compile(r"</mark><sup>(\d+)</sup>")
_TEX_NUM_RE = re.compile(r"\\tcn\{(\d+)\}")


def next_mark_n(text):
    nums = [int(x) for x in _MD_NUM_RE.findall(text)] + \
           [int(x) for x in _TEX_NUM_RE.findall(text)]
    return (max(nums) + 1) if nums else 1


# --- audit breadcrumb (F1) --------------------------------------------------

_AUDIT_HEADER = (
    "# track-changes history\n"
    "#\n"
    "# Append-only audit log of AI-introduced and AI-introduced-then-resolved\n"
    "# marks for tracked files in this project. Each entry records one\n"
    "# Write/Edit/MultiEdit. Diffable + greppable + git-committed.\n"
    "#\n"
    "# Generated and maintained by the track-changes skill PostToolUse hook.\n"
    "# Do not edit by hand (append-only). To reset: delete this file.\n"
)


def _history_path(file_path):
    root = _git_root(file_path)
    if root:
        return os.path.join(root, ".tc-history.md")
    return os.path.join(os.path.dirname(os.path.abspath(file_path)), ".tc-history.md")


def append_dictated_breadcrumb(file_path, runs, mode, baseline, flagged):
    """Append a `dictated:` block to .tc-history.md (additive; distinct key)."""
    lp = _history_path(file_path)
    root = _git_root(file_path)
    rel = os.path.relpath(os.path.abspath(file_path), root).replace(os.sep, "/") \
        if root else os.path.basename(file_path)
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = ["\n## %s -- %s  (polish)" % (ts, rel),
             "dictated:",
             "  - runs: %d" % runs,
             "    mode: %s" % mode,
             "    baseline: %s" % (baseline or "none")]
    if flagged:
        lines.append("    flagged: [%s]" % ", ".join(flagged))
    entry = "\n".join(lines) + "\n"
    try:
        if not os.path.exists(lp):
            with open(lp, "w", encoding="utf-8") as f:
                f.write(_AUDIT_HEADER)        # F1: write the canonical header
        with open(lp, "a", encoding="utf-8") as f:
            f.write(entry)
        return lp
    except OSError:
        return None


# --- track-changes activation (reuse track-changes' authoritative module) ---

def tracking_status(file_path):
    """Return (tracked: bool|None, reason: str), reusing track-changes' OWN
    `tc_core.activation` — the module its PreToolUse hook uses — so polish never
    disagrees with what the hook actually enforces (and inherits its CRLF-safe
    frontmatter parsing; the bash `/tc status` path does not strip \\r and
    misreports CRLF files). The per-turn /draft suspend is deliberately ignored:
    we report the file's *inherent* tracking (is it a tracked deliverable?), not
    whether this one turn happens to be drafted. tracked=None if track-changes is
    not importable — caller should then treat the file as untracked and say so."""
    tc_lib = os.path.join(
        os.environ.get("HOME") or os.path.expanduser("~"),
        ".claude", "skills", "track-changes", "lib")
    try:
        if tc_lib not in sys.path:
            sys.path.insert(0, tc_lib)
        from tc_core.activation import (
            tc_check_yaml_override, tc_find_marker, tc_marker_lists_file,
            tc_is_hidden_file)
    except Exception:
        return None, "track-changes-unavailable"
    try:
        yaml_val = tc_check_yaml_override(file_path)
        if yaml_val == "on":
            return True, "on-file"
        if yaml_val == "off":
            return False, "off-file"
        marker = tc_find_marker(file_path)
        if marker and not tc_is_hidden_file(file_path):
            mode = tc_marker_lists_file(marker, file_path)
            if mode in ("all", "listed"):
                return True, "on-marker"
            if mode == "off-list":
                return False, "off-marker-not-listed"
        return False, "off-default"
    except Exception:
        return None, "track-changes-error"


# --- analyze ----------------------------------------------------------------

def analyze(file_path, baseline_ref="HEAD"):
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        current_raw = f.read()
    allowlist = _load_allowlist(
        os.path.join(os.path.dirname(os.path.abspath(file_path)), ".polish-allowlist"))

    current_text = strip_marks(current_raw)
    current_tokens = pandoc_tokens(current_text)

    base_text, ginfo = git_baseline(file_path, baseline_ref)
    tracked, treason = tracking_status(file_path)
    nr = nonrendering_line_ranges(current_raw)
    nr_kinds = {}
    for (_s, _e, _k) in nr:
        nr_kinds[_k] = nr_kinds.get(_k, 0) + 1
    report = {
        "file": os.path.abspath(file_path),
        "tracked": tracked,
        "tracking_reason": treason,
        "warnings": ginfo.get("warnings", []),
        "next_mark_n": next_mark_n(current_raw),
        # Compact summary first (what the workflow / sub-agent reads); the full
        # list stays available but need not be forwarded into a prompt.
        "nonrendering_summary": {"count": len(nr), "kinds": nr_kinds},
        "nonrendering_regions": [
            {"start": s, "end": e, "kind": k} for (s, e, k) in nr],
    }

    if base_text is None:
        # M1: no baseline. Whole-document prose is in scope.
        report["mode"] = "M1"
        report["dictated_tokens"] = []
        report["flagged_protected"] = sorted(
            {t for t in current_tokens if is_protected_token(t, allowlist)})
        report["note"] = ("M1 (no baseline): polish operates on the whole "
                          "document's prose. For a large already-vetted doc, "
                          "commit a baseline first to scope fixes to new dictation.")
        return report

    base_tokens = pandoc_tokens(strip_marks(base_text))
    sm = difflib.SequenceMatcher(a=base_tokens, b=current_tokens, autojunk=False)
    dictated = set()
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            dictated.update(range(j1, j2))
    dictated = sorted(dictated)

    report["mode"] = "M2"
    report["baseline_ref"] = ginfo.get("baseline_ref", baseline_ref)
    report["dictated_tokens"] = [current_tokens[i] for i in dictated]
    report["flagged_protected"] = sorted(
        {current_tokens[i] for i in dictated
         if is_protected_token(current_tokens[i], allowlist)})
    return report


# --- CLI --------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(prog="polish_engine")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="compute dictated scope + flags")
    a.add_argument("file")
    a.add_argument("--baseline-ref", default="HEAD")
    au = sub.add_parser("audit", help="append a dictated: breadcrumb")
    au.add_argument("file")
    au.add_argument("--runs", type=int, default=1)
    au.add_argument("--mode", default="M2")
    au.add_argument("--baseline", default="HEAD")
    au.add_argument("--flagged", default="")
    args = p.parse_args(argv)

    if args.cmd == "analyze":
        rep = analyze(args.file, args.baseline_ref)
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "audit":
        flagged = [s for s in (args.flagged.split(",") if args.flagged else []) if s]
        lp = append_dictated_breadcrumb(args.file, args.runs, args.mode,
                                        args.baseline, flagged)
        print(json.dumps({"history": lp}))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
