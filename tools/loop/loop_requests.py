"""Request files to the supervisor, one per request, with an id and an answer-by time (D-793 item 3, Seckin
19 November 2026 14:34).

The lead writes each request as its own file in docs/loop/private/requests/ of the main checkout (found only through
tools/loop/shared_paths.py):

    REQ-<YYYYMMDD-HHMM>-<n>.md       n counts from 1 within that minute

holding these header lines, then the body:

    id: REQ-20261119-1500-1
    written: 2026-11-19T15:00:12+03:00
    answer_by: 2026-11-19T15:30:12+03:00
    subject: one line
    body:
    free text

The supervisor answers with ACK-<same id>.md in the same folder (its content is not read here; existence answers).

    py -3.12 -X utf8 tools/loop/loop_requests.py new --subject S --body B [--answer-in MINUTES | --answer-by ISO]
    py -3.12 -X utf8 tools/loop/loop_requests.py list
    py -3.12 -X utf8 tools/loop/loop_requests.py overdue

`new` prints the id. `list` prints one line per request: open, answered or overdue. `overdue` prints one line per
unanswered request past its answer_by and exits 1 when there is any (the line an emergency wake fires on), else
prints `no overdue request` and exits 0. No remote API is called; a request whose header cannot be read is listed as
unreadable and counts as overdue (it can never be shown answered in time).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import shared_paths  # noqa: E402

FOLDER = 'requests'
ACK = 'ACK-'
ID_RE = re.compile(r'^REQ-(\d{8})-(\d{4})-(\d+)$')
DEFAULT_MINUTES = 30


def now():
    return dt.datetime.now().astimezone().replace(microsecond=0)


def folder():
    return shared_paths.private_dir() / FOLDER


def parse_time(text):
    try:
        t = dt.datetime.fromisoformat(str(text).strip())
    except ValueError:
        return None
    return t if t.tzinfo else t.astimezone()


def one_line(text):
    return ' '.join(str(text).split())


def new(subject, body, answer_by, at=None, where=None):
    """Write one request file and return its id; the file is created exclusively, never overwritten."""
    at = at or now()
    where = where or folder()
    where.mkdir(parents=True, exist_ok=True)
    stamp = at.strftime('%Y%m%d-%H%M')
    n = 1
    while True:
        rid = 'REQ-%s-%d' % (stamp, n)
        path = where / (rid + '.md')
        try:
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            n += 1
            continue
        break
    text = ('id: %s\nwritten: %s\nanswer_by: %s\nsubject: %s\nbody:\n%s\n'
            % (rid, at.isoformat(), answer_by.isoformat(), one_line(subject), str(body).rstrip()))
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    return rid


def header(path):
    out = {}
    try:
        lines = Path(path).read_text(encoding='utf-8', errors='replace').splitlines()
    except OSError:
        return out
    for line in lines:
        if line.strip() == 'body:':
            break
        key, sep, value = line.partition(':')
        if sep:
            out[key.strip()] = value.strip()
    return out


def requests(where=None, at=None):
    """[{id, subject, answer_by, status}] oldest first; status open, answered, overdue or unreadable."""
    where = where or folder()
    at = at or now()
    try:
        names = sorted(os.listdir(where))
    except OSError:
        return []
    acks = {n[len(ACK):-len('.md')] for n in names if n.startswith(ACK) and n.endswith('.md')}
    rows = []
    for name in names:
        if not (name.startswith('REQ-') and name.endswith('.md')) or not ID_RE.match(name[:-3]):
            continue
        rid = name[:-3]
        head = header(where / name)
        due = parse_time(head.get('answer_by', ''))
        if rid in acks:
            status = 'answered'
        elif due is None or head.get('id') != rid:
            status = 'unreadable'
        elif at > due:
            status = 'overdue'
        else:
            status = 'open'
        rows.append({'id': rid, 'subject': head.get('subject', ''), 'answer_by': head.get('answer_by', ''),
                     'status': status})
    return rows


def overdue_lines(where=None, at=None):
    return ['OVERDUE %s answer_by %s: %s' % (r['id'], r['answer_by'] or '(unreadable)', r['subject'])
            for r in requests(where, at) if r['status'] in ('overdue', 'unreadable')]


def main(argv=None):
    ap = argparse.ArgumentParser(prog='loop_requests.py')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('new')
    p.add_argument('--subject', required=True)
    p.add_argument('--body', default='')
    g = p.add_mutually_exclusive_group()
    g.add_argument('--answer-in', type=int, default=None, help='minutes from now (default %d)' % DEFAULT_MINUTES)
    g.add_argument('--answer-by', default=None, help='ISO time with offset')
    sub.add_parser('list')
    sub.add_parser('overdue')
    args = ap.parse_args(argv)
    try:
        if args.cmd == 'new':
            at = now()
            if args.answer_by:
                due = parse_time(args.answer_by)
                if due is None:
                    print('answer_by is not an ISO time: %s' % args.answer_by)
                    return 2
            else:
                due = at + dt.timedelta(minutes=DEFAULT_MINUTES if args.answer_in is None else args.answer_in)
            print(new(args.subject, args.body, due, at=at))
            return 0
        if args.cmd == 'list':
            rows = requests()
            for r in rows:
                print('%-10s %s answer_by %s: %s' % (r['status'], r['id'], r['answer_by'], r['subject']))
            counts = {s: sum(r['status'] == s for r in rows) for s in ('open', 'answered', 'overdue', 'unreadable')}
            print('open %(open)d, answered %(answered)d, overdue %(overdue)d, unreadable %(unreadable)d' % counts)
            return 0
        lines = overdue_lines()
        for line in lines:
            print(line)
        if not lines:
            print('no overdue request')
        return 1 if lines else 0
    except shared_paths.MainCheckoutError as exc:
        print(str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
