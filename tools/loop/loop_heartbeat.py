"""Two-way heartbeats between the lead and the supervisor (D-793 item 3, Seckin 19 November 2026 14:34).

The lead writes docs/loop/private/LOOP_HEARTBEAT.txt of the main checkout (found only through tools/loop/shared_paths.py)
at least every 15 minutes; the supervisor writes SUPERVISOR_HEARTBEAT.txt beside it.

    py -3.12 -X utf8 tools/loop/loop_heartbeat.py beat     # one line: local time with offset, session id
    py -3.12 -X utf8 tools/loop/loop_heartbeat.py check    # the age of both heartbeats

`beat` writes exactly one line, `<ISO local time with offset> session <id>`, the id read from the `session:` line of
docs/loop/private/LEAD.lock (`unknown` when the lock or the line is absent). `check` prints the age in minutes of each
heartbeat, read from the first token of its first line (the file's modification time when that token is no time);
an absent file is reported as absent, not as an error. It exits 1 only when the loop heartbeat is present and older
than STALE_MINUTES (20), else 0.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import shared_paths  # noqa: E402

LOOP = 'LOOP_HEARTBEAT.txt'
SUPERVISOR = 'SUPERVISOR_HEARTBEAT.txt'
LOCK = 'LEAD.lock'
STALE_MINUTES = 20


def now():
    return dt.datetime.now().astimezone().replace(microsecond=0)


def session_id(private):
    try:
        lines = (Path(private) / LOCK).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return 'unknown'
    for line in lines:
        key, sep, value = line.partition(':')
        if sep and key.strip() == 'session' and value.strip():
            return value.strip().split()[0]
    return 'unknown'


def beat(private=None, at=None):
    private = Path(private or shared_paths.private_dir())
    line = '%s session %s\n' % ((at or now()).isoformat(), session_id(private))
    tmp = private / (LOOP + '.tmp')
    tmp.write_text(line, encoding='utf-8', newline='\n')
    os.replace(tmp, private / LOOP)
    return line.strip()


def stamp(path):
    """The heartbeat's time, or None when the file is absent."""
    try:
        first = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()[:1]
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    token = first[0].split()[0] if first and first[0].split() else ''
    try:
        t = dt.datetime.fromisoformat(token)
        return t if t.tzinfo else t.astimezone()
    except ValueError:
        return dt.datetime.fromtimestamp(mtime).astimezone()


def check(private=None, at=None):
    """(exit code, lines)."""
    private = Path(private or shared_paths.private_dir())
    at = at or now()
    lines, code = [], 0
    for label, name in (('loop', LOOP), ('supervisor', SUPERVISOR)):
        t = stamp(private / name)
        if t is None:
            lines.append('%s heartbeat: absent (%s)' % (label, name))
            continue
        age = (at - t).total_seconds() / 60.0
        stale = label == 'loop' and age > STALE_MINUTES
        code = 1 if stale else code
        lines.append('%s heartbeat: %.1f minutes old (%s)%s' % (label, age, t.isoformat(),
                                                             ', STALE over %d minutes' % STALE_MINUTES if stale else ''))
    return code, lines


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv not in (['beat'], ['check']):
        print('usage: loop_heartbeat.py beat|check')
        return 2
    try:
        if argv == ['beat']:
            print(beat())
            return 0
        code, lines = check()
    except shared_paths.MainCheckoutError as exc:
        print(str(exc))
        return 2
    for line in lines:
        print(line)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
