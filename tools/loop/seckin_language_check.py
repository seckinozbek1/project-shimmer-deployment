"""Check the form of what the loop writes for Seckin (D-780, his standing decision of 19 November 2026 13:09).

D-780: everything that may reach Seckin is natural Turkish with full Turkish characters, short plain sentences,
no codes, decision numbers, file names, paths, commit ids or tool words in the main text (those go only in one
closing line that starts "Teknik satır:"), no em dashes, and decisions shaped durum, soru, öneri.

This script checks the part of that rule a pattern can decide, and nothing else. It never judges the
language: whether a sentence is Turkish, natural, short or plain, and whether a decision has the durum, soru,
öneri shape, is the compliance checker's own reading (task ShimmerComplianceCheck), never a word list here.

Read, and only these:
  FOR_SECKIN.md  every entry whose heading time (`## YYYY-MM-DD HH:MM +ZZZZ: ...`) is at or after SINCE
                 (2026-11-19 13:09 +0300, the decision's own time; `--since` moves it). The main text is the
                 heading's title and every body line, except the header lines HEADER_LINES opens ("Hedefe
                 uzaklık:", "Mod ", "Bildirim kaydı:") and the one closing "Teknik satır:" line. A "Teknik
                 satır:" line that is not the entry's closing line, or a second one, is no exemption: it is
                 read as main text and counted as `technical_line_not_closing`.
  ALERT.md       every line whose first full time (`YYYY-MM-DD HH:MM +ZZZZ`) is at or after SINCE; within the
                 line, the text after "Teknik satır:" is exempt. A line with no full time is counted as
                 untimed and not read.
Flagged in the main text (PATTERNS): a decision number (`D-123`, `D-S12`), a file name with a known extension
(`x.py`, `x.md`, `x.json`, `x.cmd`, ...), a backslash path, a slash path (two slashes or more, or one with an
underscore or a dot, or one under a known top folder), a commit-like id (7 to 40 lowercase hex characters with
at least one digit and one letter), and an em dash. Full times are removed before the scan.

Printed: counts, the FOR_SECKIN headings and the ALERT times of the items with a finding, and per item the count
of each kind; never the flagged text itself. Exit 0 when nothing is flagged, 1 on a finding, 2 when a file
cannot be read. Read-only; standard library only; no network.

    py -3.12 -X utf8 tools/loop/seckin_language_check.py
    py -3.12 -X utf8 tools/loop/seckin_language_check.py --private <folder> --since "2026-11-19 13:09 +0300"

Not imported by tools/loop/standing_orders_check.py (a controller-bound file), so it changes no sealed bundle.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

TIME_FORMAT = '%Y-%m-%d %H:%M %z'
SINCE_TEXT = '2026-11-19 13:09 +0300'
SINCE = datetime.strptime(SINCE_TEXT, TIME_FORMAT)
FOR_SECKIN_NAME = 'FOR_SECKIN.md'
ALERT_NAME = 'ALERT.md'
TECHNICAL = 'Teknik satır:'
HEADER_LINES = ('Hedefe uzaklık:', 'Mod ', 'Bildirim kaydı:')
HEADING = re.compile(r'^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) ([+-]\d{4})\s*:?\s*(.*)$')
FULL_TIME = re.compile(r'(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) ([+-]\d{4})')
ISO_TIME = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?')
EXTENSIONS = ('py', 'md', 'json', 'jsonl', 'cmd', 'bat', 'ps1', 'sh', 'txt', 'log', 'html', 'csv', 'yaml', 'yml',
              'toml', 'lock', 'ipynb', 'zip', 'tar', 'gz', 'safetensors', 'bundle')
TOP_FOLDERS = ('docs', 'tools', 'scripts', 'config', 'external', 'output', 'input', 'benchmark', 'durable',
               'ontology', 'prompts', '_xfer')
EM_DASH = chr(0x2014)   # written by its code point: no em dash appears in this file
PATTERNS = (
    ('decision_number', re.compile(r'(?<![\w-])D-S?\d+\b')),
    ('file_name', re.compile(r'(?<![\w.-])[\w-][\w.-]*\.(?:%s)\b' % '|'.join(EXTENSIONS), re.IGNORECASE)),
    ('backslash_path', re.compile(r'[\w.:-]*\\[\w.\\-]+')),
    ('slash_path', re.compile(r'(?<![\w/])[\w.-]*[A-Za-z_][\w.-]*(?:/[\w.-]+)+')),
    ('commit_id', re.compile(r'(?<![\w-])(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}(?![\w-])')),
    ('em_dash', re.compile(EM_DASH)),
)
KINDS = tuple(name for name, _ in PATTERNS) + ('technical_line_not_closing',)


def _slash_path_counts(token):
    """A slash token counts as a path only with two slashes, an underscore or a dot, or a known top folder,
    so ordinary Turkish pairs ("ve/veya") are not read as paths."""
    first = token.split('/', 1)[0]
    return token.count('/') >= 2 or '_' in token or '.' in token or first in TOP_FOLDERS


def scan_text(text):
    """{kind: count} for one piece of main text (full times removed first)."""
    text = ISO_TIME.sub(' ', FULL_TIME.sub(' ', text))
    counts = {}
    for name, pattern in PATTERNS:
        found = pattern.findall(text)
        if name == 'slash_path':
            found = [t for t in found if _slash_path_counts(t)]
        if found:
            counts[name] = counts.get(name, 0) + len(found)
    return counts


def _add(total, counts):
    for k, v in counts.items():
        total[k] = total.get(k, 0) + v
    return total


def _time(date_time, zone):
    return datetime.strptime('%s %s' % (date_time, zone), TIME_FORMAT)


def for_seckin_entries(text):
    """[(heading time, title, body lines)] for every entry with a readable heading time, and the count of
    `## ` headings without one."""
    entries, untimed, current = [], 0, None
    for line in text.splitlines():
        if line.startswith('## '):
            m = HEADING.match(line)
            if m:
                current = (_time(m.group(1), m.group(2)), m.group(3).strip(), [])
                entries.append(current)
            else:
                untimed += 1
                current = None
        elif current is not None:
            current[2].append(line)
    return entries, untimed


def is_header_line(line):
    return line.startswith(HEADER_LINES)


def scan_entry(title, body):
    """{kind: count} for one FOR_SECKIN entry: its title and body, without the header lines and the one closing
    Teknik satır line."""
    lines = [ln.rstrip() for ln in body]
    content = [i for i, ln in enumerate(lines) if ln.strip() and ln.strip() != '---']
    technical = [i for i in content if lines[i].lstrip().startswith(TECHNICAL)]
    exempt = set()
    counts = scan_text(title)
    if len(technical) == 1 and content and technical[0] == content[-1]:
        exempt.add(technical[0])
    elif technical:
        counts['technical_line_not_closing'] = len(technical)
    for i in content:
        if i in exempt or is_header_line(lines[i].lstrip()):
            continue
        _add(counts, scan_text(lines[i]))
    return counts


def scan_for_seckin(text, since=None):
    """(items, read, untimed): items are (heading, counts) of the entries at or after `since` with a finding."""
    since = SINCE if since is None else since
    entries, untimed = for_seckin_entries(text)
    items, read = [], 0
    for when, title, body in entries:
        if when < since:
            continue
        read += 1
        counts = scan_entry(title, body)
        if counts:
            items.append(('%s: %s' % (when.strftime(TIME_FORMAT), title), counts))
    return items, read, untimed


def scan_alert(text, since=None):
    """(items, read, untimed): items are (line time, counts) of the timed lines at or after `since` with a
    finding; a line with no full time is untimed and not read."""
    since = SINCE if since is None else since
    items, read, untimed = [], 0, 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        m = FULL_TIME.search(stripped)
        if not m:
            untimed += 1
            continue
        when = _time('%s %s' % (m.group(1), m.group(2)), m.group(3))
        if when < since:
            continue
        read += 1
        main = stripped.split(TECHNICAL, 1)[0]
        counts = scan_text(main)
        if counts:
            items.append((when.strftime(TIME_FORMAT), counts))
    return items, read, untimed


def _counts_text(counts):
    return ', '.join('%s %d' % (k, counts[k]) for k in KINDS if counts.get(k))


def check(private, since=None):
    """(code, lines): code 0 clean, 1 a finding, 2 a file unreadable. Reads FOR_SECKIN.md and ALERT.md in
    `private`; writes nothing."""
    since = SINCE if since is None else since
    private = Path(private)
    out, code = [], 0
    sources = ((FOR_SECKIN_NAME, scan_for_seckin, 'entries'), (ALERT_NAME, scan_alert, 'lines'))
    totals = {}
    for name, scan, unit in sources:
        try:
            text = (private / name).read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as exc:
            out.append('%s: UNREADABLE (%s)' % (name, type(exc).__name__))
            code = 2
            continue
        items, read, untimed = scan(text, since)
        out.append('%s: %d %s since %s read, %d with a finding, %d untimed not read' % (
            name, read, unit, since.strftime(TIME_FORMAT), len(items), untimed))
        for label, counts in items:
            _add(totals, counts)
            out.append('  %s | %s' % (label, _counts_text(counts)))
        if items and code == 0:
            code = 1
    out.append('seckin language (D-780) form check: %s: %s' % (
        _counts_text(totals) or 'nothing flagged', {0: 'PASS', 1: 'FAIL', 2: 'UNABLE'}[code]))
    return code, out


def default_private():
    import shared_paths
    return shared_paths.private_dir()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--private', help='the private records folder (default: the main checkout\'s, by '
                                      'tools/loop/shared_paths.py)')
    ap.add_argument('--since', default=SINCE_TEXT, help='first heading time read, "YYYY-MM-DD HH:MM +ZZZZ"')
    args = ap.parse_args(argv)
    since = datetime.strptime(args.since, TIME_FORMAT)
    code, lines = check(Path(args.private) if args.private else default_private(), since)
    print('\n'.join(lines))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
