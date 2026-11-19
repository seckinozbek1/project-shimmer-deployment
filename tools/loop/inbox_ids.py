"""Ids on SUPERVISOR_INBOX entries (D-793 item 3, Seckin 19 November 2026 14:34). Read-only: the inbox is never
rewritten here.

docs/loop/private/SUPERVISOR_INBOX.md of the main checkout (found only through tools/loop/shared_paths.py) holds its
entries newest first; each entry starts with a line beginning `## ` and carries its id in that heading as
`[id G-20261119-1437]`. An entry is read when one of its lines starts with `Read:`.

    py -3.12 -X utf8 tools/loop/inbox_ids.py missing     # entries without an id (exit 1 when any)
    py -3.12 -X utf8 tools/loop/inbox_ids.py unread      # entries with no Read: line (exit 1 when any)
    py -3.12 -X utf8 tools/loop/inbox_ids.py seen ID     # exit 0 read, 1 not yet read, 2 no entry has that id

Entries are listed in file order (newest first), one line each: the id (or `-`) and the heading, cut to 120 characters.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import shared_paths  # noqa: E402

INBOX = 'SUPERVISOR_INBOX.md'
ID_RE = re.compile(r'\[id\s+([^\]\s]+)\s*\]')


def inbox_path():
    return shared_paths.private_dir() / INBOX


def entries(text):
    """[{heading, id or None, read}] in file order."""
    out = []
    for line in text.splitlines():
        if line.startswith('## '):
            m = ID_RE.search(line)
            out.append({'heading': line[3:].strip(), 'id': m.group(1) if m else None, 'read': False})
        elif out and line.lstrip().startswith('Read:'):
            out[-1]['read'] = True
    return out


def load(path=None):
    return entries(Path(path or inbox_path()).read_text(encoding='utf-8', errors='replace'))


def show(entry):
    return '%s  %s' % (entry['id'] or '-', entry['heading'][:120])


def seen(rows, wanted):
    """'read', 'unread' or 'absent' for one id."""
    hits = [e for e in rows if e['id'] == wanted]
    if not hits:
        return 'absent'
    return 'read' if any(e['read'] for e in hits) else 'unread'


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ('missing', 'unread', 'seen') or (argv[0] == 'seen') != (len(argv) == 2) \
            or len(argv) > 2:
        print('usage: inbox_ids.py missing | unread | seen ID')
        return 2
    try:
        rows = load()
    except shared_paths.MainCheckoutError as exc:
        print(str(exc))
        return 2
    except OSError as exc:
        print('cannot read %s (%s)' % (INBOX, type(exc).__name__))
        return 2
    if argv[0] == 'seen':
        state = seen(rows, argv[1])
        print('%s %s' % (argv[1], state))
        return {'read': 0, 'unread': 1}.get(state, 2)
    picked = [e for e in rows if (e['id'] is None if argv[0] == 'missing' else not e['read'])]
    for e in picked:
        print(show(e))
    print('%d of %d entries %s' % (len(picked), len(rows), 'without an id' if argv[0] == 'missing' else 'unread'))
    return 1 if picked else 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    raise SystemExit(main())
