"""tc_core — shared library for the track-changes + verified-import skills (v3).

Single source of truth, hosted inside the track-changes skill and imported by
verified-import (which depends on track-changes being installed):

  - grammar:    mark parse / classify / extract / numbering
  - activation: per-file YAML + .tc-tracked + /draft resolution
  - audit:      .tc-history.md introduced/resolved analyzer (PostToolUse)
  - exempt:     one-shot write-exemption sentinel (verified-import -> track-changes, F2)
"""
