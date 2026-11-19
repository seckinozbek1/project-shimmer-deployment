#!/usr/bin/env python3
"""Proofs for tools/loop/session_state.py (D-791): the panel takes a session's state file only after checking that
it comes from a session opened for this project.

On invented fixtures in a temporary directory: a fixture main checkout with its sessions folder, and a fixture
Claude Code projects root holding this checkout's project folder (named by the dash rule, in another case). No real
session file, private record or Claude Code folder is read.

  foreign_project_refused  a file whose project is another repository is refused with that reason, never taken
  missing_session_refused  a file naming a session id with no session file in this repository's Claude Code
                           project folder is refused with that reason, never taken
  good_file_taken          a file written by `write` (project read from the checkout, local time with offset) whose
                           session id exists in the project folder is taken, with its state

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes).

    py -3.12 -X utf8 tools/loop/session_state_checks.py
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session_state as ss  # noqa: E402

GOOD_ID = '0f1e2d3c-aaaa-bbbb-cccc-123456789abc'
MISSING_ID = '9a8b7c6d-dddd-eeee-ffff-000000000000'


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self.tmp.name)
        self.main = self.base / 'shimmer-fixture'
        ss.sessions_dir(self.main).mkdir(parents=True)
        self.projects = self.base / 'projects'
        folder = self.projects / ss.claude_folder_name(self.main).lower()   # case differs, as on this laptop
        folder.mkdir(parents=True)
        (folder / (GOOD_ID + '.jsonl')).write_text('{"never": "read"}\n', encoding='utf-8')
        (self.projects / 'c--some-other-repository').mkdir()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.tmp.cleanup()

    def put(self, name, record):
        (ss.sessions_dir(self.main) / (name + '.json')).write_text(json.dumps(record), encoding='utf-8')

    def collect(self):
        return ss.collect(main=self.main, projects_root=self.projects)


def caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return 'raised %s' % type(exc).__name__


def observe_foreign_project_refused():
    with Fixture() as f:
        f.put('lane-x', {'project': 'another-project', 'session': 'lane-x', 'time': 't', 'state': 'secret state'})
        r = f.collect()
        return r['taken'], r['refused'], r['refused_files'], 'secret state' in json.dumps(r)


def expected_foreign_project_refused():
    return 0, 1, [{'name': 'lane-x.json', 'reason': 'project is not this repository'}], False


def neutralise_foreign_project_refused():
    return patch.object(ss, 'same_project', lambda rec, project: True)


def observe_missing_session_refused():
    with Fixture() as f:
        f.put('lane-y', {'project': 'shimmer-fixture', 'session': 'lane-y', 'session_id': MISSING_ID,
                         'time': 't', 'state': 'secret state'})
        r = f.collect()
        return r['taken'], r['refused'], r['refused_files'], 'secret state' in json.dumps(r)


def expected_missing_session_refused():
    return 0, 1, [{'name': 'lane-y.json',
                   'reason': "session id not found among this repository's Claude Code sessions"}], False


def neutralise_missing_session_refused():
    return patch.object(ss, 'session_known', lambda folder, sid: True)


def observe_good_file_taken():
    with Fixture() as f:
        now = dt.datetime(2026, 11, 19, 14, 50, tzinfo=dt.timezone(dt.timedelta(hours=3)))
        path = ss.write('lead', 'Plan sürüyor.', session_id=GOOD_ID, main=f.main, now=now)
        rec = json.loads(path.read_text(encoding='utf-8'))
        r = f.collect()
        return list(rec), rec['project'], rec['time'], r['taken'], r['refused'], r['taken_names'], r['sessions']


def expected_good_file_taken():
    return (['project', 'session', 'session_id', 'time', 'state'], 'shimmer-fixture', '2026-11-19T14:50:00+03:00',
            1, 0, ['lead'], [{'session': 'lead', 'time': '2026-11-19T14:50:00+03:00', 'state': 'Plan sürüyor.'}])


def neutralise_good_file_taken():
    return patch.object(ss, 'claude_folder', lambda main, projects_root: None)


PROOFS = ('foreign_project_refused', 'missing_session_refused', 'good_file_taken')


def run_all():
    done, space = [], globals()
    for name in PROOFS:
        observe, expected, neutralise = space['observe_' + name], space['expected_' + name], space['neutralise_' + name]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                first = observe()
                with neutralise():
                    broken = caught(observe)
                again = observe()
        except Exception as exc:  # noqa: BLE001
            return 'FAIL', '%s: %s %s' % (name, type(exc).__name__, str(exc)[:300])
        if first != expected():
            return 'FAIL', '%s as built: %s' % (name, str(first)[:600])
        if broken == expected():
            return 'FAIL', '%s still passes when neutralised' % name
        if again != expected():
            return 'FAIL', '%s after restore: %s' % (name, str(again)[:400])
        done.append('%s (neutralised: %s)' % (name, str(broken)[:240]))
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass: %s' % (len(done), '; '.join(done))


if __name__ == '__main__':
    status, detail = run_all()
    sys.stdout.buffer.write(('%s %s\n' % (status, detail)).encode('utf-8'))
    raise SystemExit(0 if status == 'PASS' else 1)
