#!/usr/bin/env python3
"""decap.py -- fix stray mid-sentence capitalization from voice dictation.

Ships with the track-changes suite as a side-of-protocol dictation pre-clean
tool. It is NOT part of the mark protocol and is NOT invoked by Claude's edit
tools — it runs as an author-invoked editor selection filter (selection →
stdin → stdout → replaces selection), so it is inherently untracked.

Apply decap ONLY to fresh, unmarked dictation — never to a selection
containing <mark>/\\tc{} (it is regex over raw text and will corrupt mark
syntax). Composes with /tc polish: run decap first, then /tc polish.

Rule: lowercase the leading capital of a word UNLESS it is
  - the first word of a sentence (start of text, or after . ! ? or a newline);
  - a protected proper noun / term (tools/decap_protect.txt, one per line);
  - ALL-CAPS (acronym: US, DC, LTL, VRP, ...);
  - camelCase / has an internal capital (JuMP, CairoMakie, DCs);
  - a single letter (I, U, S) or the pronoun "I" / its contractions.

Imperfect by design: a proper noun NOT in the protect list will be lowercased
-- add it to tools/decap_protect.txt and re-run. Always eyeball the result.
"""
import sys
import os
import re

PROTECT = {
    "i", "i'm", "i've", "i'd", "i'll",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday",
}

_side = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "decap_protect.txt")
if os.path.exists(_side):
    with open(_side, encoding="utf-8") as fh:
        for line in fh:
            w = line.strip()
            if w and not w.startswith("#"):
                PROTECT.add(w.lower())

# Words exclude '.' so sentence-ending periods stay in the gap (and so are
# detected as sentence boundaries). "U.S." then splits into single letters
# U / S, both left alone by the single-letter rule.
WORD = re.compile(r"[A-Za-z][A-Za-z'']*")


def fix_word(w, sentence_start):
    if sentence_start:
        return w
    if w.lower() in PROTECT or w.rstrip(".''").lower() in PROTECT:
        return w
    letters = re.sub(r"[^A-Za-z]", "", w)
    if len(letters) <= 1:                    # single letter: I, U, S, a
        return w
    if letters.isupper():                    # acronym: US, DC, LTL, VRP
        return w
    if any(c.isupper() for c in w[1:]):      # camelCase: JuMP, DCs
        return w
    if w[0].isupper():
        return w[0].lower() + w[1:]
    return w


def main():
    text = sys.stdin.read()
    out, last, first = [], 0, True
    for m in WORD.finditer(text):
        gap = text[last:m.start()]
        out.append(gap)
        sentence_start = (first
                          or bool(re.search(r"[.!?]\s*$", gap))
                          or "\n" in gap)
        out.append(fix_word(m.group(), sentence_start))
        last = m.end()
        first = False
    out.append(text[last:])
    sys.stdout.write("".join(out))


if __name__ == "__main__":
    main()
