#!/usr/bin/env python3
"""Proofs for the D-793 loop machinery (lane/d793-loop-io): request files, two-way heartbeats, inbox ids and role
starts within limits.

On invented fixtures in a temporary directory, with shared_paths.private_dir patched to the fixture's private folder:
no real private record is read or written, no role session is started (the launch is mocked), and the one real
subprocess is tools/loop/role_start_check.py on a fixture start file.

  requests_overdue      an unanswered request past answer_by gives one OVERDUE line and exit 1; an answered past one
                        and an open future one give none
  heartbeat_two_way     beat writes one line with the LEAD.lock session; check exits 1 on a loop heartbeat over 20
                        minutes old, 0 on a fresh one, and reports an absent supervisor heartbeat without failing
  inbox_ids             missing, unread and seen read ids and Read: lines; the inbox bytes are unchanged
  start_allow_list      a start file off the allow-list is refused and never launched; the wrapper refuses it too
  start_check_pass      the real role_start_check on a fixture: PASS starts, FAIL is refused and never launched
  start_two_at_most     two live role sessions (a live mark and a cmd.exe process) refuse a third; an ended one frees
                        its slot
  start_marks_and_log   a start writes the .started mark and a role_starts.jsonl line; the wrapper writes .log, .exit
                        and an exit line
  start_hidden          the launch passes the no-window creation flag (HIDDEN-A) and starts only this tool's wrapper

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes).

    py -3.12 -X utf8 tools/loop/loop_io_checks.py
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inbox_ids as ii  # noqa: E402
import loop_heartbeat as lh  # noqa: E402
import loop_requests as lr  # noqa: E402
import role_starter as rs  # noqa: E402
import shared_paths  # noqa: E402

NOW = dt.datetime.now().astimezone().replace(microsecond=0)


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.private = Path(self.tmp.name) / 'private'
        self.starts = self.private / 'role_starts'
        self.starts.mkdir(parents=True)
        self.patch = patch.object(shared_paths, 'private_dir', lambda *a, **k: self.private)

    def __enter__(self):
        self.patch.start()
        return self

    def __exit__(self, *exc):
        self.patch.stop()
        self.tmp.cleanup()

    def start_file(self, name, guard_ok=True):
        """A fixture start file role_start_check can judge: one guard, a claude -p line with no --settings."""
        guard = self.starts / 'present.txt'
        guard.write_text('x', encoding='utf-8')
        target = guard if guard_ok else self.starts / 'absent.txt'
        (self.starts / name).write_text('@echo off\r\ncd /d %s\r\nif not exist "%s" (echo guard missing & exit /b 1)\r\n'
                                        'claude -p "fixture only"\r\n' % (self.starts, target), encoding='utf-8')

    def allow(self, names):
        (self.starts / rs.ALLOW).write_text(json.dumps(names), encoding='utf-8')

    def results(self):
        path = self.private.joinpath(*rs.RESULTS)
        try:
            return [json.loads(x)['event'] for x in path.read_text(encoding='utf-8').splitlines()]
        except OSError:
            return []


def caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return 'raised %s' % type(exc).__name__


def quiet(fn, *a):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a)


class Launcher:
    def __init__(self):
        self.calls = []

    def __call__(self, stem, where):
        self.calls.append(stem)
        return 4242


def no_processes(where):
    return set()


# requests_overdue ---------------------------------------------------------------------------------------------------
def observe_requests_overdue():
    with Fixture():
        past, future = NOW - dt.timedelta(minutes=5), NOW + dt.timedelta(minutes=30)
        late = lr.new('late one', 'body', past, at=NOW - dt.timedelta(minutes=40))
        done = lr.new('answered one', 'body', past, at=NOW - dt.timedelta(minutes=40))
        lr.new('open one', 'body', future, at=NOW)
        (lr.folder() / ('ACK-%s.md' % done)).write_text('ok', encoding='utf-8')
        lines = lr.overdue_lines(at=NOW)
        code = quiet(lr.main, ['overdue'])
        statuses = sorted(r['status'] for r in lr.requests(at=NOW))
        ids_ok = all(lr.ID_RE.match(r['id']) for r in lr.requests(at=NOW))
        return [x.split()[1] == late for x in lines], code, statuses, ids_ok, late.endswith('-1'), done.endswith('-2')


def expected_requests_overdue():
    return [True], 1, ['answered', 'open', 'overdue'], True, True, True


def neutralise_requests_overdue():
    return patch.object(lr, 'ACK', 'NOT-AN-ACK-')


# heartbeat_two_way --------------------------------------------------------------------------------------------------
def observe_heartbeat_two_way():
    with Fixture() as f:
        (f.private / lh.LOCK).write_text('status: held\nsession: fixture-session-1\n', encoding='utf-8')
        line = lh.beat(at=NOW - dt.timedelta(minutes=25))
        text = (f.private / lh.LOOP).read_text(encoding='utf-8')
        old_code, old_lines = lh.check(at=NOW)
        lh.beat(at=NOW - dt.timedelta(minutes=5))
        new_code, new_lines = lh.check(at=NOW)
        return (text.count('\n'), line.endswith('session fixture-session-1'), old_code, new_code,
                any('supervisor heartbeat: absent' in x for x in new_lines), any('STALE' in x for x in old_lines))


def expected_heartbeat_two_way():
    return 1, True, 1, 0, True, True


def neutralise_heartbeat_two_way():
    return patch.object(lh, 'STALE_MINUTES', 10 ** 6)


# inbox_ids ----------------------------------------------------------------------------------------------------------
INBOX = ('# Supervisor inbox (newest first)\n\n'
         '## 2026-11-19 15:02 +0300, supervisor [id G-20261119-1502]\nnew question\n'
         '## 2026-11-19 14:50 +0300, supervisor\nRead: 2026-11-19 14:51 by the lead\nno id here\n'
         '## 2026-11-19 14:37 +0300, supervisor [id G-20261119-1437]\nRead: 2026-11-19 14:37 by the lead\nGO\n')


def observe_inbox_ids():
    with Fixture() as f:
        path = f.private / ii.INBOX
        path.write_bytes(INBOX.encode('utf-8'))
        before = path.read_bytes(), os.path.getmtime(path)
        rows = ii.load()
        missing = [e['heading'][:16] for e in rows if e['id'] is None]
        unread = [e['id'] for e in rows if not e['read']]
        codes = (quiet(ii.main, ['missing']), quiet(ii.main, ['unread']), quiet(ii.main, ['seen', 'G-20261119-1437']),
                 quiet(ii.main, ['seen', 'G-20261119-1502']), quiet(ii.main, ['seen', 'G-19990101-0000']))
        return missing, unread, codes, (path.read_bytes(), os.path.getmtime(path)) == before


def expected_inbox_ids():
    return ['2026-11-19 14:50'], ['G-20261119-1502'], (1, 1, 0, 1, 2), True


def neutralise_inbox_ids():
    return patch.object(ii, 'ID_RE', ii.re.compile(r'\[never\s+([^\]\s]+)\]'))


# start_allow_list ---------------------------------------------------------------------------------------------------
class AllowAll(set):
    def __contains__(self, item):
        return True


def observe_start_allow_list():
    with Fixture() as f:
        f.start_file('start_x1.cmd')
        f.start_file('start_x2.cmd')
        f.allow(['start_x1.cmd'])
        launched = Launcher()
        ran = []
        code, lines = rs.start('start_x2.cmd', alive=lambda pid: False, processes=no_processes, launcher=launched)
        wrapped = rs.wrap('start_x2.cmd', runner=lambda *a, **k: ran.append(a) or SimpleNamespace(returncode=0))
        path_code, _ = rs.start('..\\start_x1.cmd', processes=no_processes, launcher=launched)
        return code, lines[0].startswith('REFUSED'), launched.calls, wrapped, ran, path_code, f.results()


def expected_start_allow_list():
    return 1, True, [], 1, [], 1, ['refused', 'wrap_refused', 'refused']


def neutralise_start_allow_list():
    return patch.object(rs, 'allowed', lambda where: AllowAll())


# start_check_pass ---------------------------------------------------------------------------------------------------
def observe_start_check_pass():
    with Fixture() as f:
        f.start_file('start_ok.cmd', guard_ok=True)
        f.start_file('start_bad.cmd', guard_ok=False)
        f.allow(['start_ok.cmd', 'start_bad.cmd'])
        launched = Launcher()
        ok, _ = rs.start('start_ok.cmd', alive=lambda pid: False, processes=no_processes, launcher=launched)
        bad, bad_lines = rs.start('start_bad.cmd', alive=lambda pid: False, processes=no_processes, launcher=launched)
        return ok, bad, 'did not pass: FAIL start_bad.cmd' in bad_lines[0], launched.calls


def expected_start_check_pass():
    return 0, 1, True, ['start_ok']


def neutralise_start_check_pass():
    return patch.object(rs, 'check_pass', lambda path, runner=None: (True, 'PASS %s' % path.name))


# start_two_at_most --------------------------------------------------------------------------------------------------
def observe_start_two_at_most():
    with Fixture() as f:
        for n in ('a', 'b', 'c', 'd'):
            f.start_file('start_%s.cmd' % n)
        f.allow(['start_a.cmd', 'start_b.cmd', 'start_c.cmd', 'start_d.cmd'])
        (f.starts / 'start_a.started').write_text('time: x\npid: 111\nfile: start_a.cmd\n', encoding='utf-8')
        launched = Launcher()
        alive = lambda pid: str(pid) == '111'
        supervisor = lambda where: {'start_b'}           # a start the supervisor made, seen as a cmd.exe process
        third, lines = rs.start('start_c.cmd', alive=alive, processes=supervisor, launcher=launched)
        (f.starts / 'start_a.exit').write_text('exit 0 x\n', encoding='utf-8')
        freed, _ = rs.start('start_c.cmd', alive=alive, processes=supervisor, launcher=launched)
        again, again_lines = rs.start('start_b.cmd', alive=alive, processes=supervisor, launcher=launched)
        return third, 'the limit is 2' in lines[0], freed, launched.calls, again, 'already running' in again_lines[0]


def expected_start_two_at_most():
    return 1, True, 0, ['start_c'], 1, True


def neutralise_start_two_at_most():
    return patch.object(rs, 'MAX_RUNNING', 99)


# start_marks_and_log ------------------------------------------------------------------------------------------------
def observe_start_marks_and_log():
    with Fixture() as f:
        f.start_file('start_m.cmd')
        f.allow(['start_m.cmd'])
        (f.starts / 'start_m.exit').write_text('exit 0 earlier\n', encoding='utf-8')     # a previous run's
        code, lines = rs.start('start_m.cmd', alive=lambda pid: False, processes=no_processes, launcher=Launcher())
        mark = rs.read_mark(f.starts / 'start_m.started')
        exit_gone = not (f.starts / 'start_m.exit').exists()

        def fake_cmd(args, **kwargs):
            kwargs['stdout'].write('role output line\n')
            return SimpleNamespace(returncode=3)
        rs.wrap('start_m.cmd', runner=fake_cmd)
        log = (f.starts / 'start_m.log').read_text(encoding='utf-8')
        ended = (f.starts / 'start_m.exit').read_text(encoding='utf-8')
        return (code, mark.get('pid'), mark.get('file'), exit_gone, 'role output line' in log, ended.startswith('exit 3 '),
                f.results(), lines[1].startswith('FOR_SECKIN: '), not (f.starts / rs.LOCK).exists())


def expected_start_marks_and_log():
    return 0, '4242', 'start_m.cmd', True, True, True, ['start', 'exit'], True, True


def neutralise_start_marks_and_log():
    return patch.object(rs, 'record', lambda entry: None)


# start_hidden -------------------------------------------------------------------------------------------------------
def observe_start_hidden():
    with Fixture() as f:
        seen = []

        def fake_popen(cmd, **kwargs):
            seen.append((cmd, kwargs.get('creationflags', 0)))
            return SimpleNamespace(pid=777)
        with patch.object(rs.subprocess, 'Popen', fake_popen):
            pid = rs.launch('start_h', f.starts)
        cmd, flags = seen[0]
        hidden = bool(flags & 0x08000000) if os.name == 'nt' else True
        return pid, hidden, cmd[-2:], Path(cmd[-3]).name, len(seen)


def expected_start_hidden():
    return 777, True, ['_wrap', 'start_h.cmd'], 'role_starter.py', 1


def neutralise_start_hidden():
    return patch.object(rs, 'no_window', lambda flags=0, keep_console=False: flags)


PROOFS = ('requests_overdue', 'heartbeat_two_way', 'inbox_ids', 'start_allow_list', 'start_check_pass',
          'start_two_at_most', 'start_marks_and_log', 'start_hidden')


def run_all(verbose=False):
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
        if verbose:
            print('%s\n  as built:    %s\n  neutralised: %s\n  restored:    %s' % (name, first, broken, again))
        if first != expected():
            return 'FAIL', '%s as built: %s' % (name, str(first)[:600])
        if broken == expected():
            return 'FAIL', '%s still passes when neutralised' % name
        if again != expected():
            return 'FAIL', '%s after restore: %s' % (name, str(again)[:400])
        done.append(name)
    return 'PASS', ('%d proofs, each neutralise, fail, restore, pass, no real record touched and no role started: %s'
                    % (len(done), ', '.join(done)))


if __name__ == '__main__':
    status, detail = run_all(verbose='-v' in sys.argv[1:])
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
