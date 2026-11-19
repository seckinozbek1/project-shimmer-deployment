"""Per-session state files for the panel, checked before they are taken (D-791, Seckin standing rule 19 November 2026).

Each Claude Code session of this project writes its state into one shared folder, a file named for itself:

    py -3.12 -X utf8 tools/loop/session_state.py write --session-name lead --state "..." [--session-id ID]
    py -3.12 -X utf8 tools/loop/session_state.py collect          # one JSON summary: taken and refused

The folder is docs/loop/private/panel/sessions/ of the main checkout, found through tools/loop/shared_paths.py (so a
worktree or a role start reaches the same folder). Each file is headed by the project name (the main checkout's
folder name, read from git through shared_paths, never typed), the session name, the session id when given, and the
local time with its offset; then the state line.

`collect` takes a file only after the first check, that it comes from a session opened for this project:
  - the file is a plain file (not a link) and a JSON object,
  - its project field equals this repository's name,
  - its session name equals the file name,
  - its session id, when present, is a plain id and `<id>.jsonl` exists in this repository's Claude Code project
    folder (~/.claude/projects/<the main checkout path with every non-alphanumeric character replaced by a dash>,
    matched without regard to case). Only existence is checked; the session file is never opened.
Anything else is listed as refused, by file name and reason, and its content is never passed on.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import shared_paths  # noqa: E402

SESSIONS = ('docs', 'loop', 'private', 'panel', 'sessions')
NAME_RX = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')
ID_RX = re.compile(r'^[A-Za-z0-9][A-Za-z0-9-]{3,79}$')


def project_name(main):
    """This repository's name: the main checkout's folder name."""
    return Path(main).name


def claude_folder_name(main):
    """The Claude Code project folder name for a checkout path: every non-alphanumeric character becomes a dash."""
    return re.sub(r'[^A-Za-z0-9]', '-', str(Path(main)))


def projects_root_default():
    return Path.home() / '.claude' / 'projects'


def sessions_dir(main):
    return Path(main).joinpath(*SESSIONS)


def is_link(path):
    text = str(path)
    return os.path.islink(text) or bool(getattr(os.path, 'isjunction', lambda p: False)(text))


def write(name, state, session_id=None, main=None, now=None):
    """Write sessions/<name>.json (replaced whole each time); returns its path."""
    if not NAME_RX.match(name or ''):
        raise ValueError('session name must be letters, digits, dot, dash or underscore')
    if session_id is not None and not ID_RX.match(session_id):
        raise ValueError('session id must be letters, digits and dashes')
    main = Path(main) if main else shared_paths.main_checkout()
    now = now or dt.datetime.now().astimezone()
    record = {'project': project_name(main), 'session': name}
    if session_id:
        record['session_id'] = session_id
    record['time'] = now.isoformat(timespec='seconds')
    record['state'] = str(state)
    folder = sessions_dir(main)
    if is_link(folder):
        raise ValueError('the sessions folder is a link; refused')
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (name + '.json')
    tmp = folder / ('.' + name + '.json.tmp')
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    os.replace(tmp, path)
    return path


def claude_folder(main, projects_root):
    """This repository's Claude Code project folder under projects_root, matched without regard to case; or None."""
    want = claude_folder_name(main).casefold()
    try:
        for entry in os.scandir(projects_root):
            if entry.name.casefold() == want and entry.is_dir(follow_symlinks=False):
                return Path(entry.path)
    except OSError:
        return None
    return None


def same_project(rec, project):
    return rec.get('project') == project


def session_known(folder, sid):
    """The session file exists in this repository's Claude Code project folder (existence only, never opened)."""
    return (folder / (sid + '.jsonl')).is_file()


def refusal(path, project, folder):
    """None when the file is taken, else the reason it is refused."""
    if is_link(path) or not path.is_file():
        return 'not a plain file'
    try:
        rec = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return 'not a readable JSON file'
    if not isinstance(rec, dict):
        return 'not a JSON object'
    if not same_project(rec, project):
        return 'project is not this repository'
    if rec.get('session') != path.stem:
        return 'session name does not match the file name'
    sid = rec.get('session_id')
    if sid is not None:
        if not isinstance(sid, str) or not ID_RX.match(sid):
            return 'session id is not a plain id'
        if folder is None:
            return 'no Claude Code project folder for this repository'
        if not session_known(folder, sid):
            return 'session id not found among this repository\'s Claude Code sessions'
    return None


def collect(main=None, projects_root=None):
    """Check every file in the sessions folder; return the summary (taken records, refused names and reasons)."""
    main = Path(main) if main else shared_paths.main_checkout()
    project = project_name(main)
    folder = claude_folder(main, Path(projects_root) if projects_root else projects_root_default())
    sdir = sessions_dir(main)
    taken, refused = [], []
    if is_link(sdir):
        refused.append({'name': sdir.name, 'reason': 'the sessions folder is a link'})
    elif sdir.is_dir():
        for path in sorted(sdir.glob('*.json')):
            why = refusal(path, project, folder)
            if why:
                refused.append({'name': path.name, 'reason': why})
                continue
            rec = json.loads(path.read_text(encoding='utf-8'))
            taken.append({'session': rec['session'], 'time': rec.get('time'), 'state': rec.get('state')})
    return {'project': project, 'taken': len(taken), 'refused': len(refused),
            'taken_names': [t['session'] for t in taken], 'refused_files': refused, 'sessions': taken}


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    w = sub.add_parser('write')
    w.add_argument('--session-name', required=True)
    w.add_argument('--state', required=True)
    w.add_argument('--session-id')
    sub.add_parser('collect')
    args = ap.parse_args(argv)
    try:
        if args.cmd == 'write':
            print('written: %s' % write(args.session_name, args.state, args.session_id))
            return 0
        summary = collect()
    except (ValueError, OSError, shared_paths.MainCheckoutError) as exc:
        print(str(exc))
        return 2
    sys.stdout.buffer.write((json.dumps(summary, ensure_ascii=False, indent=1) + '\n').encode('utf-8'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
