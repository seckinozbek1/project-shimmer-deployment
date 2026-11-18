"""Role hand-back watch, run by the 15-minute watchdog (the lead, 18 November 2026 16:05: N35 done 12:39 and N36
done 14:17 waited over an hour before the lead took them up).

    py -3.12 -X utf8 tools/loop/handback_watch.py        # one check, one trace line, the result on screen

The folders, the name patterns, the delay and the acknowledgement file come from config/handback_watch.json; the
roles root is resolved as that file's roots_location says (the environment variable SHIMMER_ROLES_ROOT, else the
folder beside the main checkout), never typed in code. In each declared folder it lists the files whose names
match a declared pattern (*_DONE.json, *_HANDBACK.json) with their modification times: names and times only, no
file in a role folder is ever opened, and a link or junction is never followed. A hand-back is acknowledged when
docs/loop/private/handback_ack.json (written by the lead, {name: ack time}; the name is the file name, or
<folder>/<file name>) holds an ack time at or after the file's modification time. Every unacknowledged hand-back
older than late_minutes (10) writes ALERT.md "role hand-back not taken up: <name> since <time>" once per file and
version (its modification time), and each run writes one trace line (mechanism handback_watch).
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mechanism_common as mc  # noqa: E402

NAME = 'handback_watch'
ONCE = 10 ** 9          # the alert's repeat interval: once per file and version
REPARSE_POINT = 0x400


def config_path():
    return Path(__file__).resolve().parents[2] / 'config' / 'handback_watch.json'


def load_config(path=None):
    return json.loads(Path(path or config_path()).read_text(encoding='utf-8'))


def roles_root(cfg, environ=None):
    where = cfg['roots_location']
    value = str((os.environ if environ is None else environ).get(where['env']) or '').strip()
    return Path(value) if value else Path(mc.MAIN).parent / where['sibling_of_main_checkout']


def is_link(entry):
    try:
        st = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    return entry.is_symlink() or bool(getattr(st, 'st_file_attributes', 0) & REPARSE_POINT)


def matches(name, patterns):
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def listing(root, folders, patterns):
    """[(folder, name, mtime as aware datetime)]: names and times only, never a file's content, no link followed."""
    out = []
    for folder in folders:
        base = Path(root) / folder
        if any(is_link_path(Path(root), base)):
            continue
        try:
            entries = list(os.scandir(base))
        except OSError:
            continue
        for entry in entries:
            if not matches(entry.name, patterns) or is_link(entry) or not entry.is_file(follow_symlinks=False):
                continue
            mtime = entry.stat(follow_symlinks=False).st_mtime
            out.append((folder, entry.name, dt.datetime.fromtimestamp(mtime).astimezone()))
    return sorted(out)


def is_link_path(root, path):
    """Yield True for each step from root to path that is a link or junction."""
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        try:
            st = os.lstat(current)
        except OSError:
            yield False
            continue
        yield os.path.islink(current) or bool(getattr(st, 'st_file_attributes', 0) & REPARSE_POINT)


def read_acks(path):
    try:
        acks = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return acks if isinstance(acks, dict) else {}


def parse_time(text):
    try:
        t = dt.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.astimezone()


def acknowledged(acks, folder, name, mtime):
    for key in ('%s/%s' % (folder, name), name):
        t = parse_time(acks.get(key))
        if t is not None and t >= mtime:
            return True
    return False


def check(now=None, cfg=None, root=None, private=None):
    """The listing, the alerts and one trace line; returns the trace line's details."""
    now = now or mc.now()
    cfg = cfg or load_config()
    root = Path(root or roles_root(cfg))
    ack_file = Path(private) / Path(cfg['ack_file']).name if private else Path(mc.MAIN) / cfg['ack_file']
    acks = read_acks(ack_file)
    late_s = 60 * cfg.get('late_minutes', 10)
    seen, late = [], []
    for folder, name, mtime in listing(root, cfg['folders'], cfg['patterns']):
        if acknowledged(acks, folder, name, mtime):
            continue
        row = {'name': '%s/%s' % (folder, name), 'since': mtime.isoformat(timespec='seconds')}
        seen.append(row)
        if (now - mtime).total_seconds() > late_s:
            late.append(row)
            mc.alert('handback:%s:%s' % (row['name'], row['since']), 'role hand-back not taken up: %s since %s'
                     % (row['name'], mtime.strftime('%Y-%m-%d %H:%M')), every=ONCE)
    details = {'unacknowledged': seen, 'late': late, 'late_minutes': cfg.get('late_minutes', 10)}
    mc.trace(NAME, 'alert' if late else 'ok', **details)
    return dict(details, result='alert' if late else 'ok')


if __name__ == '__main__':
    print(json.dumps(check(), indent=1, default=str))
