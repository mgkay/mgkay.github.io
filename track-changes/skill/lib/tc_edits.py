#!/usr/bin/env python3
"""tc_edits — the `/tc edits` backend (9.9.0, Phase A).

Part of the `track-changes` skill itself, not a separate cooperating skill: it reads
the same `tc_core` the hooks read, it is dispatched by `/tc edits` exactly the way
`/tc source` and `/tc manifest` dispatch to `tc_source.py` and `tc_manifest.py`, and
it owns no hook. (The seed's D7 proposed a fourth skill on the tc-polish model; the
maintainer's decision is that a subcommand of the mark protocol belongs in the skill
that owns the protocol. `/tc import` and `/tc polish` route out to other skills
because those skills do things track-changes deliberately does not — verified import
and editorial rewriting. Reporting what changed in a tracked file is core business.)

`/tc edits` serves the review habit the instructor actually has: open the document,
edit the prose until it reads right, then have the AI check the edit. Before 9.9.0
there was no tooling for it — every instance cost a manual `git diff`, a manual
proofread, a `/draft` round-trip, and hand-applied fixes.

This module answers four questions about a hand-edited tracked document and
answers them deterministically:

  1. **What changed since the AI last wrote?**  A line diff against a
     `tc_core.snapshot` generation — the file as the AI last left it. Not git:
     during a review session the working tree is dirty with BOTH instructor and
     AI edits and git cannot separate them.
  2. **What would polish say about just that?**  The tc-polish engine, run with
     `--baseline-file` pointed at the snapshot, so its existing dictated-scope
     machinery scopes to the edit. One scoping implementation, two baseline
     sources.
  3. **What would the project's own linter say about just that?**  An optional
     project-configured command (`.tc-edits.json`), with its findings bucketed by
     whether they land inside an edited span. Conventions are inherently
     project-specific; this skill is published for anyone, so it supplies the
     mechanism and the project supplies the rules.
  4. **What mark number comes next?**  `tc_core.marknum`, the one allocator.

Like `/tc polish analyze`, this command **never edits the document**. That single
property is what keeps Phase A additive: no partial resolution, no provenance
decision, no inverted invariant — the model reads the report and then emits its
corrections as ordinary track-changes marks through the always-on gate.

Phase A is CLEAN-PROSE scope. Regions are reported when a span overlaps one, and
explicitly not resolved; region resolution is Phase B.

CLI (invoked by lib/tc-cli.sh's `edits` case):
  python tc_edits.py analyze   <file> [--baseline auto|snapshot|git] [--gen N]
                                      [--no-lint] [--json]
  python tc_edits.py snapshots <file>
  python tc_edits.py restore   <file> [--gen N] [--yes]
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(_LIB_DIR)          # <skills>/track-changes
_SKILLS_DIR = os.path.dirname(_SKILL_ROOT)       # <skills>
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

# Same-directory import: tc_core ships with this module in track-changes/lib, so
# there is no discovery to do (the sibling-relative dance below is needed only for
# tc-polish, which really is a separate skill).
from tc_core import audit as tc_audit              # noqa: E402
from tc_core import cite as tc_cite                # noqa: E402  (10.0.0, C4)
from tc_core import coverage as tc_coverage        # noqa: E402  (10.0.0, C4)
from tc_core import grammar as tc_grammar          # noqa: E402
from tc_core import sourcetext as tc_sourcetext    # noqa: E402  (10.0.0, C4)
from tc_core import marknum as tc_marknum          # noqa: E402
from tc_core import snapshot as tc_snapshot        # noqa: E402
import tc_resolve                                  # noqa: E402  (10.0.0, C3)

CONFIG_BASENAME = ".tc-edits.json"
SPAN_COALESCE_GAP = 2          # unchanged lines that still join two spans
LINT_DEFAULT_TIMEOUT = 120
UNLOCATABLE_CAP = 10
_WS_RE = re.compile(r"\s+")


# ---------------------------------------------------------------------------
# Sibling-relative discovery of a co-installed COMPANION skill. Only tc-polish
# needs this now; it resolves in the source tree AND the deployed tree, the way
# verified-import finds tc_core.
# ---------------------------------------------------------------------------

def _import_from(sibling, module):
    for d in (os.path.join(_SKILLS_DIR, sibling, "lib"),
              os.path.join(os.environ.get("HOME") or os.path.expanduser("~"),
                           ".claude", "skills", sibling, "lib")):
        if not os.path.isdir(d):
            continue
        try:
            if d not in sys.path:
                sys.path.insert(0, d)
            return __import__(module, fromlist=["*"])
        except Exception:
            continue
    return None


# ---------------------------------------------------------------------------
# git helpers (read-only)
# ---------------------------------------------------------------------------

def _git(root, *args):
    try:
        return subprocess.run(["git", "-C", root, *args], capture_output=True,
                              text=True, encoding="utf-8").stdout
    except (FileNotFoundError, OSError):
        return ""


def git_root(path):
    d = os.path.dirname(os.path.abspath(path))
    try:
        r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    return (r.stdout.strip() or None) if r.returncode == 0 else None


def _rel(root, path):
    return os.path.relpath(os.path.abspath(path), root).replace(os.sep, "/")


def head_text(path):
    """The file's content at git HEAD, or None."""
    root = git_root(path)
    if not root:
        return None
    try:
        r = subprocess.run(["git", "-C", root, "show", "HEAD:%s" % _rel(root, path)],
                           capture_output=True, text=True, encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    return r.stdout if r.returncode == 0 else None


def dirty_vs_head(path):
    """True when the working copy differs from HEAD. None when undeterminable."""
    root = git_root(path)
    if not root:
        return None
    out = _git(root, "status", "--porcelain", "--", _rel(root, path))
    return bool(out.strip())


# ---------------------------------------------------------------------------
# Baseline resolution
# ---------------------------------------------------------------------------

def resolve_baseline(path, mode="auto", gen=0):
    """Return (baseline_text, info).

    info: {source, gen, captured, note, warnings[]}. `source` is one of
    'snapshot', 'git-head', or 'none'. Cold start (no snapshot) falls back to git
    HEAD LOUDLY — HEAD cannot separate the instructor's edits from the AI's, which
    is the whole reason the snapshot store exists — and stops cleanly when there
    is neither.
    """
    info = {"source": "none", "gen": None, "captured": None, "note": "",
            "warnings": []}
    if mode in ("auto", "snapshot"):
        text, entry = tc_snapshot.load(path, gen=gen)
        if text is not None:
            info.update(source="snapshot", gen=gen,
                        captured=(entry or {}).get("ts"))
            return text, info
        if mode == "snapshot":
            info["warnings"].append(
                "no snapshot generation %d for this file." % gen)
            return None, info

    if mode in ("auto", "git"):
        text = head_text(path)
        if text is not None:
            info.update(source="git-head", note=(
                "cold start: no snapshot for this file, so the baseline is git "
                "HEAD. HEAD cannot separate your edits from the AI's, so the "
                "spans below may include AI work. A snapshot is captured on the "
                "next AI write."
                if mode == "auto" else
                "baseline forced to git HEAD; it cannot separate your edits from "
                "the AI's."))
            return text, info

    info["warnings"].append(
        "no baseline available: no snapshot for this file and no committed "
        "version at git HEAD. Nothing to diff against — commit the file, or let "
        "the AI write once so a snapshot is captured.")
    return None, info


# ---------------------------------------------------------------------------
# Span computation
# ---------------------------------------------------------------------------

def _norm_ws(lines):
    return _WS_RE.sub(" ", " ".join(lines)).strip()


def _norm_eol(text):
    """CRLF / lone-CR -> LF.

    Both sides of the diff MUST agree on line endings. The snapshot store keeps
    exact bytes (so a restore is byte-faithful) and decodes them with the CRLF
    intact, while reading the working file in text mode translates them away —
    left unreconciled, that reported every line of a CRLF document as edited.
    Normalizing is also the right answer on the merits: a wholesale line-ending
    conversion is editor noise, not an edit, and should not surface as thousands
    of changed lines. Line NUMBERS are unaffected by the substitution.
    """
    return text.replace("\r\n", "\n").replace("\r", "\n")


def compute_spans(base_text, cur_text, coalesce_gap=SPAN_COALESCE_GAP):
    """Edited spans in CURRENT 1-indexed line numbers.

    Each span: {start, end, added, removed, kind}. A pure deletion has no current
    line, so it is anchored as a zero-width span at the following line
    (start > end) with added=0 — visible in the report rather than silently
    dropped.

    Two spans are merged when at most `coalesce_gap` unchanged lines separate them
    AND **none of those lines is blank**, so a paragraph reworked in three places
    reads as one span while two separately-edited paragraphs stay distinct. A line
    count alone cannot make that distinction (a markdown block boundary is exactly
    one blank line, the same distance as an untouched line inside a paragraph), and
    merging across a boundary would blur the whitespace-only classification and the
    region-overlap report.

    `kind` is 'whitespace-only' when the span's baseline and current text agree
    after collapsing whitespace (an editor reflow/reindent), else 'content'. The
    VS Code on-save formatter reformats .qmd files, and that reformatting lands
    after the snapshot and reads as an instructor edit; classifying it keeps pure
    reflow visibly separate from a real change.
    """
    base_lines = _norm_eol(base_text).split("\n")
    cur_lines = _norm_eol(cur_text).split("\n")
    sm = difflib.SequenceMatcher(a=base_lines, b=cur_lines, autojunk=False)

    raw = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        raw.append({"start": j1 + 1, "end": j2, "added": j2 - j1,
                    "removed": i2 - i1,
                    "_base": base_lines[i1:i2], "_cur": cur_lines[j1:j2]})

    merged = []
    for s in raw:
        if merged:
            prev = merged[-1]
            prev_end = max(prev["end"], prev["start"] - 1)
            between = cur_lines[prev_end:s["start"] - 1]      # 1-indexed -> slice
            if len(between) <= coalesce_gap and not any(
                    not ln.strip() for ln in between):
                prev["end"] = max(prev["end"], s["end"])
                prev["added"] += s["added"]
                prev["removed"] += s["removed"]
                prev["_base"] = prev["_base"] + s["_base"]
                prev["_cur"] = prev["_cur"] + s["_cur"]
                continue
        merged.append(dict(s))

    out = []
    for s in merged:
        kind = ("whitespace-only"
                if _norm_ws(s["_base"]) == _norm_ws(s["_cur"]) else "content")
        # 9.9.3 (FR-2): keep the span's BEFORE and AFTER text. It was already
        # computed here and thrown away, which made the report unusable for
        # actual proofreading: line numbers alone can only be reviewed by
        # someone who already remembers what the text used to say. A fresh,
        # resumed, or compacted session has no such memory, so without this the
        # review step Phase A exists to support is not self-contained.
        out.append({"start": s["start"], "end": s["end"], "added": s["added"],
                    "removed": s["removed"], "kind": kind,
                    "before": list(s["_base"]), "after": list(s["_cur"])})
    return out


def spans_cover(spans, line):
    for s in spans:
        if s["start"] <= line <= max(s["end"], s["start"]):
            return True
    return False


# ---------------------------------------------------------------------------
# Regions overlapping the edit (Phase A reports; Phase B resolves)
# ---------------------------------------------------------------------------

def _ftype(path):
    for ext, t in ((".qmd", "qmd"), (".md", "md"), (".tex", "tex")):
        if path.endswith(ext):
            return t
    return "other"


def regions_touched(cur_text, path, spans):
    """Regions whose body overlaps an edited span.

    Phase A does NOT resolve regions — `/tc accept`/`/tc reject` still own that,
    and partial resolution is Phase B. Reporting the overlap is what stops the
    model from treating region-internal text as clean prose (inline marks are
    forbidden inside a region, so a "correction" there would be blocked anyway).
    """
    try:
        regions = tc_grammar.extract_regions(cur_text, _ftype(path))
    except Exception:
        return []
    out = []
    for r in regions:
        # grammar.extract_regions -> {N, prov, src, join, start, end} with
        # 1-indexed opener/closer lines.
        start, end = r.get("start"), r.get("end")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if any(not (s["end"] < start or s["start"] > end) for s in spans):
            out.append({"n": r.get("N"), "prov": r.get("prov") or "authored",
                        "start": start, "end": end,
                        # FR-5 (10.0.0): flagged here too, so the read-only
                        # command warns as well. `analyze` is where an author
                        # finds out BEFORE deciding anything.
                        "fn_def_only": footnote_definition_only(
                            region_body_lines(cur_text, r), _ftype(path))})
    return out


# ---------------------------------------------------------------------------
# C1 (10.0.0, Phase B) — what `resolve` reports
#
# Phase A reports that a span OVERLAPS a region. Phase B needs the diff scoped
# to the region's own body, matched across the baseline by mark number, because
# that is what a dissolve is about to act on.
#
# Everything here is REPORTING. Nothing compares a count against a limit and
# nothing changes behaviour based on one — an earlier design selected among
# three outcomes by the edited proportion, and that was retired when the
# instructor pointed out the premise was false: the region was READ (that is how
# the parts needing change were found), so the unedited remainder is approved,
# not unread. Do not reintroduce a threshold here.
# ---------------------------------------------------------------------------

def region_body_lines(text, region):
    """The lines strictly between a region's opener and closer delimiters.

    `region` is a `grammar.extract_regions` dict with 1-indexed `start` (opener)
    and `end` (closer). Returns [] for a malformed or empty region rather than
    raising — a caller reporting on a document should never die on one bad
    region.
    """
    start, end = region.get("start"), region.get("end")
    if not isinstance(start, int) or not isinstance(end, int) or end <= start:
        return []
    return _norm_eol(text).split("\n")[start:end - 1]


def _words(lines):
    return sum(len(ln.split()) for ln in lines)


# FR-5 (10.0.0, C6). Pandoc hoists a footnote DEFINITION out of an enclosing
# div and renders it in the document's Footnotes section, so
# `::: {.tc-region} [^id]: text :::` renders as an EMPTY div and the note text
# appears with no highlight at all.
#
# The mark is fully functional in source and resolves correctly — this is not a
# correctness bug. It is a bug in the one guarantee Phase B leans on: "yellow is
# the visible contract", i.e. that a reviewer reading the RENDERED page sees AI
# content marked. For this construct they do not, and nothing said so.
#
# Delivered as an advisory through this module's warning channel, NOT at write
# time. Neither hook can emit a non-blocking advisory today (`post_tool_use.py`
# returns 0 on every path and writes only to its log; `pre_tool_use.py`'s
# `_emit` runs exclusively on `return 2` block paths), so a write-time warning
# would be a new surface and turning it into a block would be an unscoped
# behaviour change. LaTeX is unaffected: `\footnote{}` is inline, so there is no
# definition to hoist.
_MD_FOOTNOTE_DEF_LINE = re.compile(r"^[ ]{0,3}\[\^[^\]]+\]:")


def footnote_definition_only(body_lines, ftype):
    """True when a region's entire body is footnote definitions (md/qmd only).

    Continuation lines (indented, or blank between definitions) belong to the
    definition above, so they do not disqualify the region — a multi-line
    footnote is still wholly hoisted.
    """
    if ftype not in ("md", "qmd"):
        return False
    saw_def = False
    for ln in body_lines:
        if not ln.strip():
            continue
        if _MD_FOOTNOTE_DEF_LINE.match(ln):
            saw_def = True
            continue
        if saw_def and ln[:1] in (" ", "\t"):
            continue                      # lazy continuation of the definition
        return False
    return saw_def


def region_edits(base_text, cur_text, ftype):
    """Per-region report of what the AUTHOR changed inside each region body.

    Regions are matched across the two texts by mark number, which is stable
    under a body edit — line numbers are not, since an edit above a region
    shifts it. A region carrying no number cannot be matched or resolved and is
    skipped (a numbered region needs `tc-n`, so this only drops malformed ones).

    Returns (edited, vanished):
      edited   — one dict per CURRENT region whose body differs from its
                 baseline counterpart, or which has no counterpart.
      vanished — numbers present in the baseline and absent now: the author
                 deleted the whole region, fences and all. There is nothing to
                 resolve, and saying so is better than silence.

    Each `edited` dict carries what C1 prints and what C2 acts on:
      n, prov, src, join      region identity
      start, end              1-indexed opener/closer in the CURRENT text
      body_lines, body_words  what survives the dissolve
      edited_lines            content lines the author touched
      unedited_lines          body_lines - edited_lines: the AI text a dissolve
                              accepts. Information, not a gate.
      ws_only_lines           lines touched by whitespace-only spans, reported
                              apart so a formatter reflow never reads as content
      added, removed          raw line counts from the diff
      body_empty              True when the author deleted the entire body
                              (whitespace-only counts as empty) — C2's special
                              case, computed once here
      spans                   the content spans, for the diff display
      status                  'edited' | 'no-baseline-region'
    """
    try:
        cur_regions = tc_grammar.extract_regions(cur_text, ftype)
        base_regions = tc_grammar.extract_regions(base_text, ftype)
    except Exception:
        return [], []
    base_by_n = {r.get("N"): r for r in base_regions if r.get("N")}
    seen = set()
    edited = []

    for r in cur_regions:
        n = r.get("N")
        if not n:
            continue
        seen.add(n)
        cur_body = region_body_lines(cur_text, r)
        br = base_by_n.get(n)
        if br is None:
            # No counterpart to diff against. Report it; do not guess.
            edited.append({
                "n": n, "prov": r.get("prov") or "authored", "src": r.get("src"),
                "join": r.get("join"), "start": r.get("start"), "end": r.get("end"),
                "body_lines": len(cur_body), "body_words": _words(cur_body),
                "edited_lines": 0, "unedited_lines": len(cur_body),
                "ws_only_lines": 0, "added": 0, "removed": 0,
                "body_empty": not "".join(cur_body).strip(),
                "fn_def_only": footnote_definition_only(cur_body, ftype),
                "spans": [], "status": "no-baseline-region"})
            continue
        base_body = region_body_lines(base_text, br)
        if base_body == cur_body:
            continue
        spans = compute_spans("\n".join(base_body), "\n".join(cur_body))
        content = [s for s in spans if s.get("kind") == "content"]
        ws = [s for s in spans if s.get("kind") != "content"]

        def _touched(ss):
            # A pure deletion is anchored zero-width (start > end), so it
            # contributes no CURRENT line — deliberately, since there is no
            # current line to point at. `removed` still records it.
            return sum(max(s["end"] - s["start"] + 1, 0) for s in ss)

        edited.append({
            "n": n, "prov": r.get("prov") or "authored", "src": r.get("src"),
            "join": r.get("join"), "start": r.get("start"), "end": r.get("end"),
            "body_lines": len(cur_body), "body_words": _words(cur_body),
            "edited_lines": _touched(content),
            "unedited_lines": max(len(cur_body) - _touched(content), 0),
            "ws_only_lines": _touched(ws),
            "added": sum(s["added"] for s in content),
            "removed": sum(s["removed"] for s in content),
            "body_empty": not "".join(cur_body).strip(),
            "fn_def_only": footnote_definition_only(cur_body, ftype),
            "spans": content, "status": "edited"})

    vanished = sorted((n for n in base_by_n if n not in seen), key=_n_sort_key)
    return edited, vanished


def _n_sort_key(n):
    """Numeric where possible so 10 sorts after 9, lexical otherwise."""
    try:
        return (0, int(n), "")
    except (TypeError, ValueError):
        return (1, 0, str(n))


def render_region_edits(edited, vanished, show_diff=True):
    """The C1 report block. Returns a list of lines (the caller owns the join)."""
    L = []
    add = L.append
    if not edited and not vanished:
        add("  no edited regions.")
        return L

    for e in edited:
        head = "  region %s (%s)" % (e["n"], e["prov"])
        if e.get("src"):
            head += " src=%s" % e["src"]
        if e.get("join"):
            head += " join=%s" % e["join"]
        add(head)
        add("    lines %d-%d, body %d line(s) / %d word(s)"
            % (e["start"], e["end"], e["body_lines"], e["body_words"]))

        if e["status"] == "no-baseline-region":
            add("    ! region %s is not in the baseline — cannot tell what the "
                "author changed. Not resolvable." % e["n"])
            continue

        if e["body_empty"]:
            add("    the author deleted the entire body; dissolving removes the "
                "region and its paired gray block, leaving nothing.")
        else:
            add("    edit: %d content line(s) touched (+%d/-%d); dissolving "
                "accepts %d unedited line(s)"
                % (e["edited_lines"], e["added"], e["removed"],
                   e["unedited_lines"]))
        if e["ws_only_lines"]:
            add("    (%d whitespace-only line(s), not counted as a content "
                "change)" % e["ws_only_lines"])

        # FR-5. Stated here rather than as a general render note, because at
        # resolve time it bears directly on the premise: dissolving treats the
        # untouched remainder as reviewed, and this region rendered with NO
        # highlight, so it may never have looked like AI content on the page.
        if e.get("fn_def_only"):
            add("    ! this region's body is only a footnote definition. "
                "Pandoc hoists it into Footnotes, so the div renders EMPTY and "
                "the note text appeared with no highlight.")
            add("      If you reviewed this in the rendered page rather than "
                "the source, you may not have seen it marked at all. "
                "Dissolving is still correct — it just removes a wrapper that "
                "was never visible.")

        # C4. Present only for a green region that was actually checked — an
        # `authored` region has no provenance claim to falsify, and saying
        # "not checked" on every one of them would train the reader to skip
        # the line that matters.
        sup = e.get("support")
        if sup and sup.get("status") == "supported":
            add("    provenance: the edit introduced nothing the excerpt and "
                "the prior text do not already account for. (compared against "
                "the %s)" % ("durable audit record" if sup.get("comparand") == "audit"
                             else "snapshot baseline"))
        elif sup and sup.get("status") == "unsupported":
            if sup.get("reason"):
                add("    ! provenance: %s." % sup["reason"])
            else:
                add("    ! provenance: this edit introduced content with no "
                    "basis in the gray excerpt: %s"
                    % ", ".join(sup["tokens"][:12])
                    + (" (+%d more)" % (len(sup["tokens"]) - 12)
                       if len(sup["tokens"]) > 12 else ""))
            add("      The region is `%s`, so it claims that text came from "
                "its source. Dissolving REMOVES that claim, which is the "
                "correction — the alternative is leaving a false one in place."
                % e["prov"])
            add("      This is a conservative flag, not a proof: it cannot see "
                "contradiction, deletion, or a new claim rebuilt from words "
                "already present. Your reading is the backstop.")

        if show_diff:
            for s in e["spans"]:
                for ln in (s.get("before") or []):
                    add("      - %s" % ln)
                for ln in (s.get("after") or []):
                    add("      + %s" % ln)

    if vanished:
        # Deliberately does NOT say "the author deleted them". The baseline is
        # the AI's last write and `resolve` does not refresh it, so a region
        # this command dissolved reappears here on the next invocation until
        # the AI writes again. Both causes look identical from here, and
        # attributing the wrong one is worse than naming neither.
        add("  region(s) %s are in the baseline and no longer in the file "
            "(deleted by hand, or already resolved). Nothing to resolve."
            % ", ".join(vanished))
    return L


# ---------------------------------------------------------------------------
# Project lint hook (D6)
# ---------------------------------------------------------------------------

def config_path(path):
    """`.tc-edits.json` lookup: git root first, then the target's own directory;
    first found wins. Returns None when neither exists."""
    cands = []
    root = git_root(path)
    if root:
        cands.append(os.path.join(root, CONFIG_BASENAME))
    cands.append(os.path.join(os.path.dirname(os.path.abspath(path)),
                              CONFIG_BASENAME))
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def load_config(path):
    """(config_dict, config_path, error). Missing config is not an error."""
    p = config_path(path)
    if not p:
        return {}, None, None
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}, p, "%s is not a JSON object" % CONFIG_BASENAME
        return data, p, None
    except (OSError, ValueError) as e:
        return {}, p, "cannot read %s: %s" % (CONFIG_BASENAME, e)


def _default_line_pattern():
    # The near-universal `path:line[:col]` convention (gcc, ruff, eslint, mypy,
    # shellcheck — and ISE 754's lint_lecture.py).
    return r"(?P<file>[^\s:]+):(?P<line>\d+)"


def run_lint(path, spans, cfg, cfg_path):
    """Run the project lint command and bucket its findings against `spans`.

    Never raises and never fails the report: a missing executable, a timeout, or
    a bad config is LOUD (`status` + `error`) while the rest of the report still
    lands. A non-zero exit is normal — linters exit non-zero when they find
    things — and is not treated as failure.
    """
    out = {"status": "not-configured", "command": None, "in_span": [],
           "elsewhere": 0, "other_files": 0, "unlocatable": [],
           "unlocatable_total": 0, "ignored": 0, "error": None,
           "hint": ("configure a project linter in %s: "
                    '{"lint": {"command": ["python", "tools/lint.py", "{file}"]}}'
                    % CONFIG_BASENAME)}
    lint = cfg.get("lint")
    if not isinstance(lint, dict):
        return out

    cmd = lint.get("command")
    if isinstance(cmd, str):
        out["status"] = "error"
        out["error"] = ('lint.command must be an ARGUMENT LIST, not a string '
                        '(e.g. ["python", "tools/lint.py", "{file}"]). A string '
                        'would need a shell, and this command is run without '
                        'one on purpose.')
        return out
    if not (isinstance(cmd, list) and cmd and all(isinstance(a, str) for a in cmd)):
        out["status"] = "error"
        out["error"] = "lint.command must be a non-empty list of strings"
        return out

    base_dir = os.path.dirname(os.path.abspath(cfg_path)) if cfg_path \
        else os.path.dirname(os.path.abspath(path))
    cwd = os.path.abspath(os.path.join(base_dir, lint.get("cwd") or "."))
    if not os.path.isdir(cwd):
        out["status"] = "error"
        out["error"] = "lint.cwd does not exist: %s" % cwd
        return out

    try:
        target = os.path.relpath(os.path.abspath(path), cwd)
    except ValueError:
        target = os.path.abspath(path)
    argv = [a.replace("{file}", target) for a in cmd]
    out["command"] = argv
    out["cwd"] = cwd

    try:
        pattern = re.compile(lint.get("line_pattern") or _default_line_pattern())
    except re.error as e:
        out["status"] = "error"
        out["error"] = "lint.line_pattern is not a valid regex: %s" % e
        return out

    # Optional: what a FINDING line even looks like. Linters interleave findings
    # with chrome — section headers, per-file banners, a totals line, a closing
    # note — and a generic parser cannot tell them apart. Without this, chrome
    # lands in the `unlocatable` bucket and reads as five mystery findings
    # (observed against a real linter). With it, only matching lines are
    # considered at all, and a matching line that still has no parseable
    # location is correctly unlocatable rather than dropped. Absent, every
    # non-blank line is a candidate — fail-loud by default.
    finding_re = None
    try:
        if lint.get("finding_pattern"):
            finding_re = re.compile(lint["finding_pattern"])
    except re.error as e:
        out["status"] = "error"
        out["error"] = "lint.finding_pattern is not a valid regex: %s" % e
        return out

    try:
        timeout = float(lint.get("timeout") or LINT_DEFAULT_TIMEOUT)
    except (TypeError, ValueError):
        timeout = LINT_DEFAULT_TIMEOUT

    try:
        # Arg-list, no shell — see the trust model in SKILL.md.
        r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except FileNotFoundError:
        out["status"] = "error"
        out["error"] = "lint command not found: %s" % argv[0]
        return out
    except subprocess.TimeoutExpired:
        out["status"] = "error"
        out["error"] = "lint command timed out after %.0fs" % timeout
        return out
    except OSError as e:
        out["status"] = "error"
        out["error"] = "lint command failed to start: %s" % e
        return out

    out["status"] = "ok"
    out["exit"] = r.returncode
    want = os.path.basename(os.path.abspath(path)).lower()

    for raw in ((r.stdout or "") + "\n" + (r.stderr or "")).splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if finding_re is not None and not finding_re.search(line):
            out["ignored"] += 1
            continue
        m = pattern.search(line)
        if not m:
            out["unlocatable_total"] += 1
            if len(out["unlocatable"]) < UNLOCATABLE_CAP:
                out["unlocatable"].append(line.strip())
            continue
        gd = m.groupdict()
        if gd.get("file"):
            found = os.path.basename(gd["file"].replace("\\", "/")).lower()
            if found != want:
                out["other_files"] += 1
                continue
        try:
            n = int(gd.get("line"))
        except (TypeError, ValueError):
            out["unlocatable_total"] += 1
            if len(out["unlocatable"]) < UNLOCATABLE_CAP:
                out["unlocatable"].append(line.strip())
            continue
        if spans_cover(spans, n):
            out["in_span"].append({"line": n, "text": line.strip()})
        else:
            out["elsewhere"] += 1
    return out


# ---------------------------------------------------------------------------
# Polish integration (D5)
# ---------------------------------------------------------------------------

def run_polish(path, baseline_text):
    """tc-polish's dictated-scope analysis against the SNAPSHOT baseline.

    Materializes the baseline to a temp file and calls the engine's
    `analyze(..., baseline_file=...)` (9.9.0/D5), so polish's existing scoping
    machinery does the work and there is only one implementation of "what is new".
    Absent tc-polish, or absent pandoc, the block reports why it was skipped and
    the rest of the report still lands.
    """
    res = {"status": "skipped", "reason": None}
    engine = _import_from("tc-polish", "polish_engine")
    if engine is None:
        res["reason"] = ("tc-polish is not co-installed; polish analysis "
                         "skipped.")
        return res
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix="tc-edits-baseline-", suffix=".txt")
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(baseline_text)
        rep = engine.analyze(path, baseline_file=tmp)
        res = {"status": "ok",
               "dictated_tokens": rep.get("dictated_tokens", []),
               "flagged_protected": rep.get("flagged_protected", []),
               "nonrendering_summary": rep.get("nonrendering_summary"),
               "warnings": rep.get("warnings", [])}
    except Exception as e:
        res = {"status": "skipped",
               "reason": "polish analysis failed (%s). pandoc is required and "
                         "must be on PATH." % e}
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass
    return res


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

def analyze(path, baseline="auto", gen=0, lint=True):
    path = os.path.abspath(path)
    # Every key is present on EVERY exit path, including the no-baseline one, so
    # a caller (or the renderer) never has to special-case a partial report.
    report = {"file": path, "warnings": [], "spans": [], "lines_changed": 0,
              "content_spans": 0, "regions_touched": [], "dirty_vs_head": None,
              "next_mark_n": None,
              "polish": {"status": "skipped", "reason": "no baseline"},
              "lint": {"status": "skipped", "reason": "no baseline"}}

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        cur_text = f.read()

    base_text, binfo = resolve_baseline(path, baseline, gen)
    report["baseline"] = binfo
    report["warnings"].extend(binfo.get("warnings", []))
    if base_text is None:
        report["status"] = "no-baseline"
        return report

    spans = compute_spans(base_text, cur_text)
    report["spans"] = spans
    report["lines_changed"] = sum(max(s["added"], s["removed"]) for s in spans)
    report["content_spans"] = sum(1 for s in spans if s["kind"] == "content")
    report["status"] = "ok" if spans else "no-edits"

    dirty = dirty_vs_head(path)
    report["dirty_vs_head"] = dirty

    # Absorption hazard. The snapshot is "the file at the moment of the LAST AI
    # write", so an AI write between the instructor's edit and this command
    # absorbs that edit into the baseline and the diff comes back empty. Two
    # independent signals catch it: a dirty tree (the edit is uncommitted), and
    # a DIFFERING previous generation (an AI write intervened) — the second is
    # what covers the case where the edit was already committed, which
    # dirty-vs-HEAD alone misses.
    if not spans and binfo.get("source") == "snapshot":
        cur_raw, _ = tc_snapshot.load_bytes(path, gen=gen)
        prev_raw, _ = tc_snapshot.load_bytes(path, gen=gen + 1)
        prev_differs = (prev_raw is not None and cur_raw is not None
                        and prev_raw != cur_raw)
        report["prev_generation_differs"] = prev_differs
        if dirty or prev_differs:
            report["warnings"].append(
                "No change since the last AI write (snapshot captured %s), but "
                "%s. If you edited BEFORE that write, your edits were absorbed "
                "into this baseline: re-run with `--gen %d` to diff against the "
                "generation before it, or `--baseline git` to diff against HEAD."
                % (binfo.get("captured") or "?",
                   "the file is uncommitted" if dirty
                   else "an AI write happened since the previous snapshot",
                   gen + 1))

    report["regions_touched"] = regions_touched(cur_text, path, spans)
    # 9.10.0: the region-SCOPED diff, beside the overlap answer. `regions_touched`
    # says a span met a region; this says what changed INSIDE it, matched across
    # the baseline by mark number. Read-only, like everything else here — the
    # provenance check belongs on `/tc accept`, where the resolution happens.
    try:
        report["region_edits"], report["regions_vanished"] = region_edits(
            base_text, cur_text, _ftype(path))
    except Exception:
        report["region_edits"], report["regions_vanished"] = [], []
    if report["regions_touched"]:
        report["warnings"].append(
            "An edited span overlaps %d tracked region(s). Phase A does NOT "
            "resolve regions and inline marks are forbidden inside one — resolve "
            "them with /tc accept or /tc reject instead."
            % len(report["regions_touched"]))

    report["next_mark_n"] = tc_marknum.next_mark_n(cur_text)

    report["polish"] = (run_polish(path, base_text) if spans
                        else {"status": "skipped", "reason": "no edited span"})

    cfg, cfg_path, cfg_err = load_config(path)
    report["config"] = cfg_path
    if lint and not os.environ.get("TC_EDITS_NO_LINT"):
        if cfg_err:
            report["lint"] = {"status": "error", "error": cfg_err}
        else:
            report["lint"] = run_lint(path, spans, cfg, cfg_path)
    else:
        report["lint"] = {"status": "disabled",
                          "error": None,
                          "reason": ("TC_EDITS_NO_LINT is set" if
                                     os.environ.get("TC_EDITS_NO_LINT")
                                     else "--no-lint")}
    return report


# ---------------------------------------------------------------------------
# Human-readable rendering
# ---------------------------------------------------------------------------

DIFF_MAX_LINES = 40


def _span_diff_lines(span, limit=DIFF_MAX_LINES):
    """A span's before/after as `-`/`+` lines, truncated LOUDLY (9.9.3, FR-2).

    Plain -/+ rather than a unified diff with @@ hunks: the span header already
    states the line range, and hunk offsets computed within a span would be
    relative to the span, which is more confusing than useful. A truncation is
    always announced — a silently shortened diff would be worse than none, since
    the reviewer would believe they had seen the whole edit.
    """
    before = span.get("before") or []
    after = span.get("after") or []
    if not before and not after:
        return []
    lines = ["-%s" % b for b in before] + ["+%s" % a for a in after]
    if len(lines) <= limit:
        return lines
    keep = max(limit - 1, 1)
    return lines[:keep] + ["... %d more diff line(s) (--no-diff to suppress "
                           "the diff entirely)" % (len(lines) - keep)]


def render(rep, show_diff=True):
    L = []
    add = L.append
    add("tc edits — %s" % rep["file"])
    b = rep.get("baseline") or {}
    if b.get("source") == "snapshot":
        add("  baseline: snapshot gen %s, captured %s"
            % (b.get("gen"), b.get("captured")))
    elif b.get("source") == "git-head":
        add("  baseline: git HEAD")
    else:
        add("  baseline: NONE")
    if b.get("note"):
        add("            %s" % b["note"])

    if rep.get("status") == "no-baseline":
        for w in rep.get("warnings", []):
            add("  ! %s" % w)
        return "\n".join(L)

    spans = rep.get("spans", [])
    if not spans:
        add("  no changes since the baseline.")
    else:
        add("  %d edited span(s), %d line(s) changed (%d content, %d "
            "whitespace-only):"
            % (len(spans), rep.get("lines_changed", 0),
               rep.get("content_spans", 0),
               len(spans) - rep.get("content_spans", 0)))
        for s in spans:
            where = ("line %d (deletion)" % s["start"]
                     if s["end"] < s["start"]
                     else "lines %d-%d" % (s["start"], s["end"]))
            add("    - %-22s +%-4d -%-4d  %s"
                % (where, s["added"], s["removed"], s["kind"]))
            if show_diff:
                for line in _span_diff_lines(s):
                    add("        %s" % line)

    # 9.10.0: the region-scoped diff, when there is one. It supersedes the bare
    # overlap line for those regions — saying what changed inside beats saying
    # that something did.
    _detailed = {e["n"] for e in rep.get("region_edits", [])}
    if rep.get("region_edits") or rep.get("regions_vanished"):
        for line in render_region_edits(rep.get("region_edits", []),
                                        rep.get("regions_vanished", []),
                                        show_diff=show_diff):
            add(line)
    for r in rep.get("regions_touched", []):
        if r["n"] in _detailed:
            continue
        add("  region %s (%s) at lines %d-%d overlaps an edited span"
            % (r["n"], r["prov"], r["start"], r["end"]))
        if r.get("fn_def_only"):
            add("    ! renders INVISIBLE: the body is only a footnote "
                "definition, which Pandoc hoists into Footnotes, so the div "
                "renders empty and the note text carries no highlight (FR-5)")
    # 9.9.3 (FR-10): silence read as "nothing overlaps". Inline marks are
    # deliberately out of scope (D8) but the report never said so, so a span
    # that ended on a mark's line looked like a clean miss. Say it.
    if spans and not rep.get("regions_touched"):
        add("  no tracked REGION overlaps an edited span (inline marks are not "
            "checked — see /tc list)")

    p = rep.get("polish") or {}
    if p.get("status") == "ok":
        # 9.9.3 (FR-6): the bare token count read like a proposal and was never
        # actionable — "31 token(s) new" only restates what the span counts
        # already say. Report whether polish has anything to PROPOSE, and keep
        # the count as the subordinate detail it is.
        # 9.11.1: this line is named for what it REPORTS. Its only payload is
        # the protected-token set — jargon/code/math that must never be
        # auto-corrected — but it was labelled "polish", so the empty branch
        # ("nothing flagged in the edited text") meant *no un-correctable
        # tokens* and read as *no errors found*. Nearly opposite messages, and
        # the reassuring one was the wrong one: measured on a fixture carrying a
        # doubled "the" and "weights is" for "weights are", it printed exactly
        # that. Same defect 9.9.3 fixed on the region line above (D8/FR-10),
        # never carried across.
        #
        # "run /tc polish for the full editorial pass" is gone with it. In THIS
        # flow the editorial pass is the model reading these spans, now — the
        # pointer sent the reader away at the moment the work should start. The
        # polish-vs-edits distinction belongs in reference/tc-edits.md and on
        # the landing page, where someone choosing between two commands looks.
        toks = p.get("dictated_tokens") or []
        flagged = p.get("flagged_protected") or []
        if flagged:
            add("  protected: %d token(s) to leave alone (jargon/code/math — "
                "never auto-correct): %s" % (len(flagged), ", ".join(flagged)))
            add("    (%d token(s) new in the edited text)" % len(toks))
        else:
            add("  protected: none in the edited text (%d new token(s))"
                % len(toks))
    else:
        add("  protected: skipped — %s" % (p.get("reason") or "?"))

    li = rep.get("lint") or {}
    if li.get("status") == "ok":
        add("  lint: %d finding(s) INSIDE your edit, %d elsewhere in this file, "
            "%d in other files"
            % (len(li.get("in_span", [])), li.get("elsewhere", 0),
               li.get("other_files", 0)))
        for f in li.get("in_span", []):
            add("    ! %s" % f["text"])
        if li.get("unlocatable_total"):
            # 9.9.3 (FR-7): a site-scoped finding has no file or line BY
            # CONSTRUCTION, so no finding_pattern can ever classify it. Naming
            # the config first made a normal, unfixable class of output look
            # like a misconfiguration.
            add("    %d line(s) with no file/line to place them — site-scoped "
                "findings have none by construction, so these are shown as-is "
                "(if a locatable finding is in here, refine lint.finding_pattern "
                "in %s):" % (li["unlocatable_total"], CONFIG_BASENAME))
            for u in li.get("unlocatable", []):
                add("      ? %s" % u)
    elif li.get("status") == "error":
        add("  lint: FAILED — %s" % li.get("error"))
    elif li.get("status") == "disabled":
        add("  lint: disabled (%s)" % li.get("reason"))
    else:
        add("  lint: not configured. %s" % li.get("hint", ""))

    if rep.get("next_mark_n"):
        add("  next mark number: %d" % rep["next_mark_n"])

    # 9.11.1: state the remaining work instead of letting the report end on a
    # list of clean-looking checks. Every line above reports something MECHANICAL
    # (spans, protected tokens, region overlap, lint) and none of it is a
    # proofread, so a reader reaching the end had no cue that the actual review
    # had not happened yet. Printed only when there is prose to read: with no
    # content span the instruction is noise, and the empty-diff and
    # whitespace-only cases already say what they are.
    if any(s.get("kind") == "content" for s in spans):
        n = rep.get("next_mark_n")
        add("  NOT PROOFREAD: nothing above has been checked for grammar, "
            "dropped words, or sense.")
        add("    Read the span diffs, then mark any correction%s."
            % ("" if not n else " as %d+" % n))
    for w in rep.get("warnings", []):
        add("  ! %s" % w)
    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_snapshots(args):
    gens = tc_snapshot.list_gens(args.file)
    if not gens:
        print("no snapshots for %s" % os.path.abspath(args.file))
        print("A snapshot is captured on every AI write to a tracked file.")
        return 0
    print("snapshots for %s" % os.path.abspath(args.file))
    for g in gens:
        print("  gen %d  %s  %d bytes  %s"
              % (g.get("gen"), g.get("ts"), g.get("size", 0),
                 g.get("tool", "")))
    return 0


def _cmd_restore(args):
    path = os.path.abspath(args.file)
    text, entry = tc_snapshot.load(path, gen=args.gen)
    if text is None:
        sys.stderr.write("tc edits: no snapshot generation %d for %s\n"
                         % (args.gen, path))
        return 2
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        cur = f.read()
    diff = list(difflib.unified_diff(
        cur.splitlines(), text.splitlines(),
        fromfile="%s (on disk now)" % os.path.basename(path),
        tofile="%s (snapshot gen %d, %s)" % (os.path.basename(path), args.gen,
                                             (entry or {}).get("ts")),
        lineterm="", n=1))
    if not diff:
        print("tc edits: on-disk content already matches snapshot gen %d; "
              "nothing to restore." % args.gen)
        return 0
    print("tc edits: restoring %s from snapshot gen %d (%s) would change:"
          % (path, args.gen, (entry or {}).get("ts")))
    for line in diff[:200]:
        print("  %s" % line)
    if len(diff) > 200:
        print("  ... %d more diff line(s)" % (len(diff) - 200))
    if not args.yes:
        print("\nNo change made. Re-run with --yes to restore. "
              "(The current bytes are saved as a new snapshot generation first, "
              "so the restore is itself undoable.)")
        return 0
    if tc_snapshot.restore(path, gen=args.gen) is None:
        sys.stderr.write("tc edits: restore failed.\n")
        return 2
    print("\nrestored.")
    return 0


def changed_files():
    """Every stored file whose bytes on disk differ from its newest snapshot.

    9.9.3 (FR-1). Deliberately NOT the working-file heuristic the resolution
    subcommands use (`tc_resolve_working_file` = most-recently-modified tracked
    file). That heuristic exists because no last-edited state was available;
    here it is: the store records a sha per baseline, so "which files did the
    author change since the AI last wrote" is answerable exactly rather than
    guessed. Comparing shas means no snapshot content is read for files that
    have not changed.
    """
    out = []
    for entry in tc_snapshot.list_files():
        path = entry["path"]
        stored = (entry.get("gen0") or {}).get("sha256")
        cur = tc_snapshot.current_sha256(path)
        if cur is None or stored is None:
            continue
        if cur != stored:
            out.append(path)
    return out


def _cmd_analyze_all(args):
    """Bare `/tc edits` — report every file with a delta (9.9.3, FR-1)."""
    files = changed_files()
    if not files:
        print("tc edits: no author edits since the last AI write "
              "(%d file(s) have a baseline)."
              % len(tc_snapshot.list_files()))
        return 0
    reports = []
    for i, path in enumerate(files):
        rep = analyze(path, baseline=args.baseline, gen=args.gen,
                      lint=not args.no_lint)
        reports.append(rep)
        if not args.json:
            if i:
                print("")
            print(render(rep, show_diff=not args.no_diff))
    if args.json:
        print(json.dumps(reports, indent=2, ensure_ascii=False))
    elif len(files) > 1:
        print("\ntc edits: %d file(s) changed since the last AI write."
              % len(files))
    return 0


def _cmd_diff(args):
    """`/tc edits diff` — the store's missing read path (9.9.3, FR-3)."""
    path = os.path.abspath(args.file)
    if not os.path.isfile(path):
        sys.stderr.write("tc edits: file not found: %s\n" % path)
        return 2
    text, entry = tc_snapshot.load(path, gen=args.gen)
    if text is None:
        sys.stderr.write("tc edits: no snapshot generation %d for %s\n"
                         % (args.gen, path))
        return 2
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        cur = f.read()
    diff = list(difflib.unified_diff(
        _norm_eol(text).split("\n"), _norm_eol(cur).split("\n"),
        fromfile="%s (snapshot gen %d, %s)" % (os.path.basename(path), args.gen,
                                               (entry or {}).get("ts")),
        tofile="%s (on disk now)" % os.path.basename(path),
        lineterm="", n=3))
    if not diff:
        print("tc edits: no difference between %s and snapshot gen %d."
              % (path, args.gen))
        return 0
    for line in diff:
        print(line)
    return 0


def _cmd_show(args):
    """`/tc edits show` — print a stored generation verbatim (9.9.3, FR-3)."""
    path = os.path.abspath(args.file)
    text, entry = tc_snapshot.load(path, gen=args.gen)
    if text is None:
        sys.stderr.write("tc edits: no snapshot generation %d for %s\n"
                         % (args.gen, path))
        return 2
    sys.stderr.write("tc edits: %s snapshot gen %d (%s, %d bytes)\n"
                     % (path, args.gen, (entry or {}).get("ts"),
                        (entry or {}).get("size", 0)))
    sys.stdout.write(text)
    if text and not text.endswith("\n"):
        sys.stdout.write("\n")
    return 0


# ---------------------------------------------------------------------------
def paired_excerpt(cur_text, ftype, region_start_line):
    """The gray `.tc-verbatim` body paired with the region opening at
    `region_start_line`, or None when there is none.

    Uses `tc_resolve`'s own 9.3.0 adjacency pairing so the block the support
    check reads is exactly the block the dissolve will remove. Two independent
    notions of "paired" would eventually disagree, and the disagreement would be
    silent: the check would score against one excerpt while another was deleted.

    The 9.1.1 source anchor (`[...]{.tc-src-key}` / `\\tcsrckey{...}`) is
    stripped to its inner text, so the anchor contributes source vocabulary and
    not markup.
    """
    try:
        grays = tc_resolve._extract_verbatim_with_offsets(cur_text, ftype)
        span = tc_resolve._paired_gray_span(region_start_line, grays, cur_text)
        if span is None:
            return None
        for b in tc_grammar.extract_verbatim_blocks(cur_text, ftype):
            s, e = b.get('start'), b.get('end')
            if not s or not e:
                continue
            starts = tc_resolve._line_starts(cur_text)
            if starts[s - 1] == span[0]:
                return tc_sourcetext.strip_anchor(b.get('body') or '', ftype)
    except Exception:
        return None
    return None


def gate_body_for(path, n):
    """The region body as the WRITE GATE last saw it, or None. (9.10.0)

    `write_sourced_entry` stores `supports:` — the green body at gate time —
    into `.tc-history.md`, which is git-committed and so survives everything the
    snapshot store does not.

    THERE IS NO FALLBACK, and that is the point. An earlier draft fell back to
    git HEAD on the reasoning that `/tc accept` runs on a clean file, so HEAD
    must be a byte-exact baseline. **False.** 8.1.0 forces the author to commit
    THEIR OWN EDITS before `accept` will run, so HEAD contains them: the check
    would compare the author's text against itself and always report
    "supported" — a check that cannot fail, which is worse than none. Absent a
    record the honest answer is "not checked".

    `include_transcript=True` because a transcript gloss is logged under its own
    key; without it this would silently cover `sourced` regions only.
    """
    try:
        entries = tc_audit.read_sourced_entries(os.path.abspath(path),
                                                include_transcript=True)
    except Exception:
        return None
    best = None
    for ent in entries:                      # file order; last wins = newest
        if ent.get("malformed"):
            continue
        if str(ent.get("n")) == str(n) and (ent.get("supports") or "").strip():
            best = ent["supports"]
    return best


def support_check(path, region_n, prov, cur_body, cur_text, ftype,
                  region_start_line):
    """Is the content this region gained since the write gate accounted for?

    Spec of record: `pcvplans/gate-b-c5-support-check.md`. Returns
    {status, tokens, reason} with status in
    'supported' | 'unsupported' | 'not-checked'.

    9.10.0: called from `/tc accept` rather than a withdrawn `resolve`, and the
    comparand is the durable audit record rather than a snapshot. `accept` is
    the only way a green region resolves, so this is the last moment anything
    can say the region's provenance claim has stopped being true.

    IT INFORMS; IT DOES NOT GATE. Accept proceeds either way — resolving is what
    *removes* a claim that has gone false, so a flag is not a reason to stop.
    What it buys is that the drift is named before that happens. Charge
    acceptance 7's guarantee is "never SILENTLY", not "never wrong": see the
    blind spots in `coverage.unsupported_tokens`.
    """
    if prov not in ("sourced", "transcript"):
        return {"status": "not-checked", "tokens": [], "reason": ""}

    gate_body = gate_body_for(path, region_n)
    if not gate_body:
        return {"status": "not-checked", "tokens": [],
                "reason": "no durable audit record for region %s, so there is "
                          "nothing to compare against (regions predating v9, "
                          "or a pruned log)" % region_n}

    spans = compute_spans(gate_body, "\n".join(cur_body))
    added = [ln for sp in spans if sp.get("kind") == "content"
             for ln in (sp.get("after") or [])]
    if not added:
        return {"status": "supported", "tokens": [],
                "reason": "unchanged since the write gate saw it"}

    excerpt = paired_excerpt(cur_text, ftype, region_start_line)
    # Fail closed both ways. 9.1.0 already makes green-without-gray a violation;
    # `accept` must not be the path that launders one, and an excerpt that
    # normalizes to empty verifies nothing (mirroring `sourcetext.contains`).
    if excerpt is None:
        return {"status": "unsupported", "tokens": [],
                "reason": "no paired gray excerpt found — a green region "
                          "without its excerpt cannot be checked"}
    if not excerpt.strip():
        return {"status": "unsupported", "tokens": [],
                "reason": "the paired gray excerpt is empty"}

    toks = tc_coverage.unsupported_tokens(
        "\n".join(added), excerpt, gate_body, ftype,
        strip_citations=tc_cite.strip_citations)
    if toks:
        return {"status": "unsupported", "tokens": toks, "reason": ""}
    return {"status": "supported", "tokens": [], "reason": ""}


def main(argv=None):
    p = argparse.ArgumentParser(prog="tc_edits")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="report what changed since the AI last wrote")
    # 9.9.3 (FR-1): optional. With no path, report every file with a delta.
    a.add_argument("file", nargs="?")
    a.add_argument("--baseline", choices=["auto", "snapshot", "git"],
                   default="auto")
    a.add_argument("--gen", type=int, default=0,
                   help="snapshot generation (0 = newest)")
    a.add_argument("--no-lint", action="store_true")
    a.add_argument("--no-diff", action="store_true",
                   help="counts only; omit each span's before/after text")
    a.add_argument("--json", action="store_true")

    s = sub.add_parser("snapshots", help="list stored snapshot generations")
    s.add_argument("file")

    r = sub.add_parser("restore", help="restore the file from a snapshot")
    r.add_argument("file")
    r.add_argument("--gen", type=int, default=0)
    r.add_argument("--yes", action="store_true")

    # 9.9.3 (FR-3): the store had no read path — list + restore only. `diff` is
    # the primitive FR-2 needs; `show` prints a generation verbatim.
    d = sub.add_parser("diff", help="diff the file on disk against a snapshot")
    d.add_argument("file")
    d.add_argument("--gen", type=int, default=0)

    sh = sub.add_parser("show", help="print a stored snapshot generation")
    sh.add_argument("file")
    sh.add_argument("--gen", type=int, default=0)

    args = p.parse_args(argv)

    if args.cmd == "analyze":
        if args.file is None:
            return _cmd_analyze_all(args)
        if not os.path.isfile(args.file):
            sys.stderr.write("tc edits: file not found: %s\n" % args.file)
            return 2
        rep = analyze(args.file, baseline=args.baseline, gen=args.gen,
                      lint=not args.no_lint)
        if args.json:
            print(json.dumps(rep, indent=2, ensure_ascii=False))
        else:
            print(render(rep, show_diff=not args.no_diff))
        return 0
    if args.cmd == "snapshots":
        return _cmd_snapshots(args)
    if args.cmd == "restore":
        if not os.path.isfile(args.file):
            sys.stderr.write("tc edits: file not found: %s\n" % args.file)
            return 2
        return _cmd_restore(args)
    if args.cmd == "diff":
        return _cmd_diff(args)
    if args.cmd == "show":
        return _cmd_show(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
