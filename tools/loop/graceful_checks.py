#!/usr/bin/env python3
"""Proofs for tools/loop/chain_board.py and tools/loop/graceful_stop.py (D-916), on invented fixtures only.

No real folder, ledger, ALERT.md or Windows task is touched: the board reads temporary launch folders, the stop
tool gets a fake schtasks runner injected as a callable.

  board_done          FREEZE_OK and BSCORE_DONE present: overall done
  board_refused       FREEZE_REFUSED present: overall failed
  board_running       a ledger step running in the status: step running, overall running
  board_stop_file     BUNT_STOP present: overall failed
  board_never_opens   a role file that raises on open: the board is still built, nothing opened
  stop_dry_run        no --execute: no change call, no record
  stop_execute        only the declared start tasks disabled, keep tasks untouched, record and one alert line
  stop_idempotent     a second execute changes nothing
  stop_resume         re-enables exactly the tasks this tool disabled
  stop_no_kill        only /query and /change /disable|/enable are ever issued

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes).
"""
from __future__ import annotations

import builtins
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chain_board as bd  # noqa: E402
import graceful_stop as gs  # noqa: E402

STOP = ['ShimmerLaunchChain', 'ShimmerUntScitabPrepare', 'ShimmerUntContradocPrepare', 'ShimmerDevpStart']
KEEP = ['ShimmerLoopReaper', 'ShimmerFreezeTag', 'ShimmerBScore', 'ShimmerMechanismWatchdog']


# ---- board fixture
class Board:
    def __init__(self, files=(), running=False):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'main' / 'external' / 's05'
        self.roles = self.base / 'roles'
        folder = self.root / 'GATE_X'
        folder.mkdir(parents=True)
        self.roles.mkdir()
        chain = {'chain': 1, 'steps': [
            {'step': 'req', 'kind': 'request', 'done_when': {'exists': 'request/seal_request.json'}},
            {'step': 'run', 'kind': 'ledger', 'after': ['req'], 'purpose': 'p-run'}]}
        (folder / 'chain.json').write_text(json.dumps(chain), encoding='utf-8')
        (folder / 'launch.py').write_text('PURPOSES = {}\n', encoding='utf-8')
        (folder / 'request').mkdir()
        (folder / 'request' / 'seal_request.json').write_text('{}', encoding='utf-8')
        for name in files:
            target = folder / name if name.startswith('FREEZE') else self.roles / name
            target.write_text('x', encoding='utf-8')
        self.running = running
        self.config = {'folders': ['GATE_X'], 'watched': [
            {'name': 'FREEZE_OK', 'path': str(folder / 'FREEZE_OK.json'), 'role': 'final'},
            {'name': 'FREEZE_REFUSED', 'path': str(folder / 'FREEZE_REFUSED.json'), 'role': 'stop'},
            {'name': 'BSCORE_DONE', 'path': str(self.roles / 'BSCORE_DONE.json'), 'role': 'final'},
            {'name': 'BUNT_STOP', 'path': str(self.roles / 'BUNT_STOP.txt'), 'role': 'stop'},
            {'name': 'BSCORE_STOP', 'path': str(self.roles / 'BSCORE_STOP_*.txt'), 'role': 'stop'}]}

    def status(self, folder):
        return {'run': {'cost': 0.5, 'state': 'running' if self.running else 'not launched', 'phase': {}}}

    def build(self):
        return bd.build(self.config, main=self.base / 'main', trace=[], rows=[], status_fn=self.status, root=self.root)

    def close(self):
        self.tmp.cleanup()


def board_overall(files, running=False):
    b = Board(files, running)
    try:
        r = b.build()
        steps = {s['step']: s['state'] for s in r['folders'][0]['steps']}
        return r['overall'], steps['run']
    finally:
        b.close()


def observe_board_done():
    return board_overall(['FREEZE_OK.json', 'BSCORE_DONE.json'])


def expected_board_done():
    return 'done', 'ready'


def neutralise_board_done():
    real = bd.watch
    return patch.object(bd, 'watch', lambda e, m: dict(real(e, m), present=False, files=[]))


def observe_board_refused():
    return board_overall(['FREEZE_REFUSED.json'])[0]


def expected_board_refused():
    return 'failed'


def _as_info(**_):
    real = bd.watch
    return patch.object(bd, 'watch', lambda e, m: dict(real(e, m), role='info'))


neutralise_board_refused = _as_info


def observe_board_running():
    return board_overall([], running=True)


def expected_board_running():
    return 'running', 'running'


def neutralise_board_running():
    return patch.object(bd, 'MAP', dict(bd.MAP, running='pending'))


def observe_board_stop_file():
    return board_overall(['BUNT_STOP.txt', 'BSCORE_DONE.json', 'FREEZE_OK.json'])[0], board_overall(['BSCORE_STOP_1.txt'])[0]


def expected_board_stop_file():
    return 'failed', 'failed'


neutralise_board_stop_file = _as_info


def observe_board_never_opens():
    b = Board(['BUNT_STOP.txt', 'BSCORE_DONE.json'])
    roles = str(b.roles).lower()
    real_open, real_read = builtins.open, Path.read_text
    opened = []

    def guard(path):
        if roles in str(path).lower():
            opened.append(str(path))
            raise AssertionError('a role file was opened')

    def fake_open(file, *a, **k):
        guard(file)
        return real_open(file, *a, **k)

    def fake_read(self, *a, **k):
        guard(self)
        return real_read(self, *a, **k)
    try:
        with patch.object(builtins, 'open', fake_open), patch.object(Path, 'read_text', fake_read):
            r = b.build()
        present = {w['name']: w['present'] for w in r['watched']}
        sizes = all('size' in f and 'modified' in f for w in r['watched'] for f in w['files'])
        return r['overall'], present['BUNT_STOP'], present['BSCORE_DONE'], sizes, opened
    finally:
        b.close()


def expected_board_never_opens():
    return 'failed', True, True, True, []


def neutralise_board_never_opens():
    real = bd.stat_line

    def peek(path):
        if not Path(path).exists():
            return real(path)
        with open(path, encoding='utf-8') as f:
            f.read(1)
        return real(path)
    return patch.object(bd, 'stat_line', peek)


# ---- stop fixture
class Fake:
    def __init__(self, disabled=()):
        self.state = {n: 'Ready' for n in STOP + KEEP}
        for n in disabled:
            self.state[n] = 'Disabled'
        self.calls = []

    def __call__(self, args):
        self.calls.append(list(args))
        name = args[args.index('/tn') + 1]
        if args[0] == '/query':
            return (0, '"\\%s","N/A","%s"\n' % (name, self.state[name])) if name in self.state else (1, '')
        if args[0] == '/change':
            self.state[name] = 'Disabled' if '/disable' in args else 'Ready'
            return 0, ''
        return 1, ''

    def changes(self):
        return [c for c in self.calls if c[0] != '/query']


class Stop:
    def __init__(self, disabled=()):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.private = Path(self.tmp.name)
        (self.private / 'budget_ledger.jsonl').write_text(
            json.dumps({'event': 'launch', 'instance_name': 'inst-a', 'deadline_utc': '2026-11-21T12:00:00+00:00'}) + '\n'
            + json.dumps({'event': 'launch', 'instance_name': 'inst-b', 'deadline_utc': '2026-11-21T13:00:00+00:00'}) + '\n'
            + json.dumps({'event': 'termination', 'instance_name': 'inst-b'}) + '\n', encoding='utf-8')
        self.fake = Fake(disabled)
        self.config = {'stop': STOP, 'keep': KEEP}
        self.alerts = []

    def stop(self, execute):
        with contextlib.redirect_stdout(io.StringIO()):
            return gs.stop(self.config, self.fake, self.private, execute, alert=lambda k, t, every=0: self.alerts.append(t) or True)

    def resume(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return gs.resume(self.fake, self.private)

    def record(self):
        return gs.read_record(self.private)

    def close(self):
        self.tmp.cleanup()


def observe_stop_dry_run():
    s = Stop()
    try:
        out = s.stop(False)
        return out, s.fake.changes(), s.record(), s.alerts
    finally:
        s.close()


def expected_stop_dry_run():
    return [], [], None, []


def neutralise_stop_dry_run():
    real = gs.stop
    return patch.object(gs, 'stop', lambda config, runner, private, execute, **k: real(config, runner, private, True, **k))


def observe_stop_execute():
    s = Stop()
    try:
        done = s.stop(True)
        rec = s.record()
        return ([d['task'] for d in done], [s.fake.state[n] for n in KEEP], [s.fake.state[n] for n in STOP],
                [d['prior_state'] for d in rec['disabled']], all('/enable' in d['re_enable'] for d in rec['disabled']),
                rec['open_launches'], len(s.alerts))
    finally:
        s.close()


def expected_stop_execute():
    return (STOP, ['Ready'] * 4, ['Disabled'] * 4, ['Ready'] * 4, True,
            [{'instance_name': 'inst-a', 'deadline_utc': '2026-11-21T12:00:00+00:00'}], 1)


def neutralise_stop_execute():
    real = gs.stop
    return patch.object(gs, 'stop', lambda config, runner, private, execute, **k: real(
        dict(config, stop=config['stop'] + config['keep']), runner, private, execute, **k))


def observe_stop_idempotent():
    s = Stop()
    try:
        s.stop(True)
        before = (s.private / gs.RECORD).read_bytes()
        n_calls = len(s.fake.changes())
        again = s.stop(True)
        return again, len(s.fake.changes()) - n_calls, (s.private / gs.RECORD).read_bytes() == before, len(s.alerts)
    finally:
        s.close()


def expected_stop_idempotent():
    return [], 0, True, 1


def neutralise_stop_idempotent():
    return patch.object(gs, 'task_state', lambda name, runner: 'Ready')


def observe_stop_resume():
    s = Stop(disabled=['ShimmerDevpStart'])      # already disabled by someone else: not ours, never re-enabled
    try:
        s.stop(True)
        done = s.resume()
        again = s.resume()
        return (sorted(done), [s.fake.state[n] for n in STOP], s.record()['status'], again)
    finally:
        s.close()


def expected_stop_resume():
    return (sorted(['ShimmerLaunchChain', 'ShimmerUntContradocPrepare', 'ShimmerUntScitabPrepare']),
            ['Ready', 'Ready', 'Ready', 'Disabled'], 'resumed', [])


def neutralise_stop_resume():
    real = gs.read_record

    def everything(private):
        rec = real(private)
        if rec:
            rec['disabled'] = [{'task': n} for n in STOP]
        return rec
    return patch.object(gs, 'read_record', everything)


def observe_stop_no_kill():
    s = Stop()
    try:
        s.stop(True)
        s.resume()
        return sorted({tuple(c[:1] + [x for x in c if x in ('/disable', '/enable')]) for c in s.fake.calls})
    finally:
        s.close()


def expected_stop_no_kill():
    return [('/change', '/disable'), ('/change', '/enable'), ('/query',)]


def neutralise_stop_no_kill():
    real = gs.task_state

    def killer(name, runner):
        runner(['/end', '/tn', name])
        return real(name, runner)
    return patch.object(gs, 'task_state', killer)


PROOFS = ('board_done', 'board_refused', 'board_running', 'board_stop_file', 'board_never_opens', 'stop_dry_run',
          'stop_execute', 'stop_idempotent', 'stop_resume', 'stop_no_kill')


def caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return 'raised %s' % type(exc).__name__


def run_all():
    done, space = [], globals()
    for name in PROOFS:
        observe, expected, neutralise = space['observe_' + name], space['expected_' + name], space['neutralise_' + name]
        try:
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
        done.append('%s (neutralised: %s)' % (name, str(broken)[:100]))
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass: %s' % (len(done), '; '.join(done))


if __name__ == '__main__':
    status, detail = run_all()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
