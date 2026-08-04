"""tc_core — shared library for the track-changes suite (v3+).

Single source of truth, hosted inside the track-changes skill and imported by
verified-import and tc-polish (both of which depend on track-changes being
installed).

MODULES below is the package's own declaration of what it consists of. It
exists so a DEPLOYED tree can be checked for completeness on a machine that has
no source tree and no test suite: `lib/tc_selfcheck.py` imports every name here
and reports any that is missing or unimportable, and `install.sh` /
`bootstrap.md` Step 4 both run it (9.9.2).

Keep MODULES in step with the directory — TC-AG-5 asserts the two agree, so a
module added to the package but not declared here fails the suite. The reason
this list lives beside the modules rather than in the deployment scripts: 9.9.0
added `marknum` and `snapshot` to the package and to NEITHER remote manifest,
so `/tc edits` raised ImportError on first use and the PostToolUse snapshot
silently stored nothing (9.9.1 post-mortem).
"""

MODULES = (
    "grammar",      # mark parse / classify / extract / numbering
    "activation",   # per-file YAML + .tc-tracked + /draft resolution
    "audit",        # .tc-history.md introduced/resolved analyzer (PostToolUse)
    "exempt",       # one-shot write-exemption sentinel (verified-import -> track-changes, F2)
    "coverage",     # import-fidelity content-token comparison (8.2.0)
    "sourcetext",   # source normalize + extract_text (text/pdf/docx) (9.0.0)
    "srcstage",     # pending-source staging + citekey resolution (9.0.0)
    "cite",         # reader-facing citation detector (9.1.0)
    "websource",    # web-source capture: validate_url/discover_browser/capture (9.2.0)
    "marknum",      # single mark-number allocator, shared with tc-polish (9.9.0)
    "snapshot",     # per-user snapshot store backing /tc edits (9.9.0)
)
