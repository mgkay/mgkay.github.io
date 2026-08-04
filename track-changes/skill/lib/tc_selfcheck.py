"""tc_selfcheck — verify a DEPLOYED track-changes tree is complete and loadable.

Why this exists (9.9.2). 9.9.0 added two `tc_core` modules to the package and to
neither deployment manifest. `install.sh` copied what it was told to copy and
reported "install complete"; the tree it produced could not run `/tc edits` at
all, and its PostToolUse snapshot silently stored nothing. Nothing in the build,
the 721-test suite, or the install itself looked at the deployed artifact.

This module is the install-time gate that closes that. It is deliberately usable
where no source tree and no test suite exist — a user's machine installing from
the Pages bootstrap — so it derives "what should be here" from something that
ships WITH the package (`tc_core.MODULES`) rather than from a remote manifest.

Two checks:

  1. DECLARED   every module named in `tc_core.MODULES` is present and imports.
                Catches a module that was never packaged (the 9.9.0 defect).
  2. PRESENT    every `*.py` actually deployed under lib/, lib/tc_core/, hooks/,
                and the sibling verified-import / tc-polish skills imports
                cleanly. Catches a module that shipped but cannot load — a bad
                intra-package import, a syntax error under the target Python.

Check 1 needs the declaration because a missing FILE leaves nothing to walk;
check 2 needs the walk because a declaration cannot describe files it does not
know about. Neither subsumes the other.

Stdlib only, no network. Every module in the suite imports clean in a bare
environment (no third-party imports at module scope), so a failure here is a
real defect, not a missing optional dependency.

Usage:
    python tc_selfcheck.py [--root <track-changes-skill-dir>] [--quiet]

    --root   the installed track-changes skill directory. Defaults to this
             file's own parent's parent, i.e. the tree this file is part of.
    --quiet  print only failures and the summary line.

Exit codes:
    0  every declared module present and importable; every deployed module imports
    1  one or more modules missing or unimportable (each named on stderr)
    2  the tree is unusable (no lib/, no tc_core package) — nothing to check
"""

import argparse
import importlib
import os
import sys
import traceback


def _skill_root_default():
    """The track-changes skill dir containing this file (…/track-changes)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _py_files(directory):
    """Sorted module stems of the *.py files directly in `directory`.

    __init__ and anything under __pycache__ are skipped: the former is the
    package itself (imported implicitly), the latter is build residue.
    """
    if not os.path.isdir(directory):
        return []
    out = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".py"):
            continue
        if name == "__init__.py":
            continue
        out.append(name[:-3])
    return out


def _try_import(modname, search_paths):
    """Import `modname` with `search_paths` prepended. -> (ok, detail).

    Each import runs with sys.path and sys.modules restored afterwards, so one
    module's failure cannot contaminate the next one's attempt.
    """
    saved_path = list(sys.path)
    saved_modules = set(sys.modules)
    try:
        for p in reversed(search_paths):
            if p not in sys.path:
                sys.path.insert(0, p)
        importlib.import_module(modname)
        return True, ""
    except Exception:
        lines = traceback.format_exception_only(*sys.exc_info()[:2])
        return False, "".join(lines).strip().replace("\n", " ")
    finally:
        sys.path[:] = saved_path
        for name in set(sys.modules) - saved_modules:
            sys.modules.pop(name, None)


def run(root, quiet=False, out=None, err=None):
    """Check the deployed tree at `root`. -> exit code (0 / 1 / 2)."""
    out = out or sys.stdout
    err = err or sys.stderr

    lib = os.path.join(root, "lib")
    core = os.path.join(lib, "tc_core")
    if not os.path.isdir(lib) or not os.path.isdir(core):
        err.write(
            "tc_selfcheck: not a track-changes tree: expected %s and %s\n"
            % (lib, core)
        )
        return 2

    # tc_core.MODULES is the package's declaration of itself. If the package
    # cannot even be imported there is nothing further to say.
    ok, detail = _try_import("tc_core", [lib])
    if not ok:
        err.write("tc_selfcheck: cannot import the tc_core package: %s\n" % detail)
        return 2
    saved_path = list(sys.path)
    try:
        if lib not in sys.path:
            sys.path.insert(0, lib)
        declared = tuple(getattr(importlib.import_module("tc_core"), "MODULES", ()))
    finally:
        sys.path[:] = saved_path
        sys.modules.pop("tc_core", None)

    failures = []   # (label, reason)
    checked = 0

    # --- Check 1: every DECLARED tc_core module is present and importable. ---
    if not declared:
        err.write(
            "tc_selfcheck: tc_core declares no MODULES — cannot verify package "
            "completeness (expected a MODULES tuple in tc_core/__init__.py)\n"
        )
        failures.append(("tc_core.MODULES", "declaration missing or empty"))
    for mod in declared:
        checked += 1
        label = "tc_core.%s" % mod
        path = os.path.join(core, "%s.py" % mod)
        if not os.path.isfile(path):
            failures.append((label, "declared in tc_core.MODULES but NOT DEPLOYED "
                                    "(missing %s)" % path))
            continue
        ok, detail = _try_import(label, [lib])
        if ok:
            if not quiet:
                out.write("  ok   %s\n" % label)
        else:
            failures.append((label, detail))

    # --- Check 2: everything actually deployed imports cleanly. ---
    # (root, subdir, search paths) — the sibling skills import tc_core from
    # track-changes/lib, mirroring how they are wired at runtime.
    skills_dir = os.path.dirname(root)
    groups = [
        (os.path.join(root, "hooks"), [os.path.join(root, "hooks"), lib]),
        (lib, [lib]),
        (os.path.join(skills_dir, "verified-import", "lib"),
         [os.path.join(skills_dir, "verified-import", "lib"), lib]),
        (os.path.join(skills_dir, "verified-import", "hooks"),
         [os.path.join(skills_dir, "verified-import", "hooks"),
          os.path.join(skills_dir, "verified-import", "lib"), lib]),
        (os.path.join(skills_dir, "tc-polish", "lib"),
         [os.path.join(skills_dir, "tc-polish", "lib"), lib]),
    ]
    for directory, search in groups:
        for mod in _py_files(directory):
            # tc_selfcheck importing itself is a no-op worth skipping.
            if directory == lib and mod == "tc_selfcheck":
                continue
            checked += 1
            label = os.path.join(os.path.basename(os.path.dirname(directory)),
                                 os.path.basename(directory), mod + ".py")
            ok, detail = _try_import(mod, search)
            if ok:
                if not quiet:
                    out.write("  ok   %s\n" % label)
            else:
                failures.append((label, detail))
    # tc_core's own deployed modules, including any not declared (drift the
    # other way: shipped but unlisted).
    for mod in _py_files(core):
        if mod in declared:
            continue
        checked += 1
        label = "tc_core.%s" % mod
        ok, detail = _try_import(label, [lib])
        if ok:
            if not quiet:
                out.write("  ok   %s  (deployed but NOT declared in tc_core.MODULES)\n"
                          % label)
        else:
            failures.append((label, detail))

    if failures:
        err.write("\ntc_selfcheck: FAILED - %d of %d module(s) unusable in %s\n"
                  % (len(failures), checked, root))
        for label, reason in failures:
            err.write("  FAIL %s\n       %s\n" % (label, reason))
        err.write(
            "\nA module that is 'declared but NOT DEPLOYED' was added to the package\n"
            "and left out of a deployment manifest. Fix install.sh (REQUIRED_FILES +\n"
            "the copy block) and bootstrap.md (download list), then reinstall.\n"
        )
        return 1

    out.write("tc_selfcheck: OK - %d module(s) present and importable in %s\n"
              % (checked, root))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="tc_selfcheck",
        description="Verify a deployed track-changes tree is complete and loadable.")
    ap.add_argument("--root", default=None,
                    help="installed track-changes skill dir (default: this file's tree)")
    ap.add_argument("--quiet", action="store_true",
                    help="print only failures and the summary line")
    args = ap.parse_args(argv)
    root = args.root or _skill_root_default()
    return run(os.path.abspath(root), quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
