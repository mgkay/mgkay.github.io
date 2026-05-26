"""tc_core.grammar — mark grammar (single source of truth, v3).

Parse / classify / extract / number the change-mark wrappers:
  - Markdown / Quarto:  <mark>BODY</mark><sup>N</sup>
  - LaTeX:              \\tc{BODY}\\tcn{N}

where BODY is one of:
  insertion    NEW
  deletion     <s>OLD</s>          (md)   \\sout{OLD}          (tex)
  replacement  <s>OLD</s>NEW       (md)   \\sout{OLD}NEW       (tex)

Pre-Fix-#7 markdown deletions/replacements used `~~OLD~~`; still accepted.

Consolidated from the duplicated copies in v2's tc_analyzer.py and
tc_audit.py so the two skills share one grammar.
"""
import re

# Wrapper detection.
MD_MARK_RE = re.compile(r'<mark>(.*?)</mark><sup>(\d+)</sup>', re.DOTALL)
TEX_HEAD_RE = re.compile(r'\\tc\{')
TEX_TCN_AFTER_RE = re.compile(r'\\tcn\{(\d+)\}')

# Body classification.
_MD_S_REP_RE = re.compile(r'^<s>(.*?)</s>(.+)$', re.DOTALL)
_MD_S_DEL_RE = re.compile(r'^<s>(.*?)</s>\s*$', re.DOTALL)
_MD_TILDE_REP_RE = re.compile(r'^~~(.*?)~~(.+)$', re.DOTALL)
_MD_TILDE_DEL_RE = re.compile(r'^~~(.*?)~~\s*$', re.DOTALL)
_TEX_SOUT_REP_RE = re.compile(r'^\\sout\{(.*?)\}(.+)$', re.DOTALL)
_TEX_SOUT_DEL_RE = re.compile(r'^\\sout\{(.*?)\}\s*$', re.DOTALL)

# Number-only scanners (numbering uniqueness).
MD_NUMS_RE = re.compile(r'</mark><sup>(\d+)</sup>')
TEX_NUMS_RE = re.compile(r'\\tcn\{(\d+)\}')


def classify_md(body):
    m = _MD_S_REP_RE.match(body)
    if m:
        return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    m = _MD_S_DEL_RE.match(body)
    if m:
        return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    m = _MD_TILDE_REP_RE.match(body)
    if m:
        return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    m = _MD_TILDE_DEL_RE.match(body)
    if m:
        return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    return {'type': 'insertion', 'old': '', 'new': body}


def classify_tex(body):
    m = _TEX_SOUT_REP_RE.match(body)
    if m:
        return {'type': 'replacement', 'old': m.group(1), 'new': m.group(2)}
    m = _TEX_SOUT_DEL_RE.match(body)
    if m:
        return {'type': 'deletion', 'old': m.group(1), 'new': ''}
    return {'type': 'insertion', 'old': '', 'new': body}


def extract_marks(text, ftype):
    """Return list of dicts {N(str), type, line(1-indexed), old, new}.

    Behavior is byte-identical to v2 tc_audit._extract_marks (the A-O tests
    guard this).
    """
    marks = []
    if ftype in ('md', 'qmd'):
        for m in MD_MARK_RE.finditer(text):
            body = m.group(1)
            n = m.group(2)
            line_no = 1 + text.count('\n', 0, m.start())
            entry = classify_md(body)
            entry['N'] = n
            entry['line'] = line_no
            marks.append(entry)
    elif ftype == 'tex':
        pos = 0
        L = len(text)
        while pos < L:
            mh = TEX_HEAD_RE.search(text, pos)
            if not mh:
                break
            if text[mh.start():mh.start() + 5] == '\\tcn{':
                pos = mh.end()
                continue
            body_start = mh.end()
            depth = 1
            i = body_start
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
                        break
                i += 1
            if depth != 0:
                pos = mh.end()
                continue
            body = text[body_start:i]
            tail = text[i + 1:i + 1 + 30]
            tm = TEX_TCN_AFTER_RE.match(tail)
            if not tm:
                pos = i + 1
                continue
            n = tm.group(1)
            line_no = 1 + text.count('\n', 0, mh.start())
            entry = classify_tex(body)
            entry['N'] = n
            entry['line'] = line_no
            marks.append(entry)
            pos = i + 1 + len(tm.group(0))
    return marks


def scan_max_n(text, ftype):
    """Largest existing mark number in `text` (0 if none). Use max()+1 for the
    next mark; the gate enforces uniqueness, not contiguity."""
    rx = TEX_NUMS_RE if ftype == 'tex' else MD_NUMS_RE
    nums = [int(n) for n in rx.findall(text)]
    return max(nums) if nums else 0
