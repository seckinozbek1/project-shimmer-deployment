"""Inbox watcher (supervisor 19 November 2026 13:24, item 3; prepared, not yet wired into the lead's start).

    py -3.12 -X utf8 tools/loop/inbox_watch_exit.py [--timeout 1700] [--step 5]
    py -3.12 -X utf8 tools/loop/inbox_watch_exit.py --proof

Blocks until docs/loop/private/SUPERVISOR_INBOX.md (main checkout, tools/loop/shared_paths.py) gets a new entry,
or until the timeout, then exits 0. The lead runs it in the background (Monitor, or Bash with run_in_background),
so the line it prints starts a new turn when the supervisor writes. A change of size or modification time alone
is not enough: the lead's own `Read:` lines change both, so the watcher compares the newest heading (the file is
newest first) and the number of headings with what it saw at its start, and keeps waiting when only the body
changed. Output, one line, never the entry body:

    INBOX_NEW: <newest heading>          a new entry arrived
    INBOX_TIMEOUT: no new entry in N s   the timeout passed
    INBOX_ERROR: <kind>                  the file could not be read (still exit 0, never holds the lead)
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def inbox_path():
    import shared_paths
    return shared_paths.private_dir() / 'SUPERVISOR_INBOX.md'


def snapshot(path):
    """(size, mtime_ns, newest heading, number of headings), or None when the file is missing."""
    try:
        st = os.stat(path)
        text = Path(path).read_text(encoding='utf-8', errors='replace')
    except FileNotFoundError:
        return None
    heads = [ln for ln in text.splitlines() if ln.startswith('## ')]
    return st.st_size, st.st_mtime_ns, heads[0] if heads else '', len(heads)


def watch(path, timeout, step, clock=time.monotonic, sleep=time.sleep):
    start = snapshot(path)
    end = clock() + max(0.0, timeout)
    last = start
    while True:
        left = end - clock()
        if left <= 0:
            return 'INBOX_TIMEOUT: no new entry in %.0f s' % timeout
        sleep(min(step, left))
        now = snapshot(path)
        if now is None or now[:2] == (last or (None, None))[:2]:
            continue
        last = now
        if start is None or now[2] != start[2] or now[3] > start[3]:
            return 'INBOX_NEW: %s' % now[2][3:].strip()


def say(text):
    sys.stdout.buffer.write((text + '\n').encode('utf-8'))
    sys.stdout.flush()


def proof():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / 'SUPERVISOR_INBOX.md'
        p.write_text('# inbox\n\n## 2026-11-19 13:00 +0300: old\nbody\n', encoding='utf-8')
        assert watch(p, 0.3, 0.05).startswith('INBOX_TIMEOUT'), 'no change must time out'

        def read_line_only():
            time.sleep(0.1)
            p.write_text('# inbox\n\n## 2026-11-19 13:00 +0300: old\nRead: 13:01 by the lead\nbody\n', encoding='utf-8')
        t = threading.Thread(target=read_line_only)
        t.start()
        out = watch(p, 0.6, 0.05)
        t.join()
        assert out.startswith('INBOX_TIMEOUT'), 'a Read: line alone must not wake: %s' % out

        def new_entry():
            time.sleep(0.1)
            p.write_text('# inbox\n\n## 2026-11-19 13:30 +0300: new order\nx\n\n## 2026-11-19 13:00 +0300: old\n',
                         encoding='utf-8')
        t = threading.Thread(target=new_entry)
        t.start()
        out = watch(p, 2.0, 0.05)
        t.join()
        assert out == 'INBOX_NEW: 2026-11-19 13:30 +0300: new order', out
    print('inbox_watch_exit proof: PASS (timeout, Read-line-only change ignored, new heading printed)')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeout', type=float, default=1700.0, help='seconds; under the 30 minute Monitor cap')
    ap.add_argument('--step', type=float, default=5.0)
    ap.add_argument('--proof', action='store_true')
    args = ap.parse_args(argv)
    if args.proof:
        return proof()
    try:
        say(watch(inbox_path(), args.timeout, args.step))
    except Exception as exc:  # never hold the lead on a broken watch
        say('INBOX_ERROR: %s' % type(exc).__name__)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
