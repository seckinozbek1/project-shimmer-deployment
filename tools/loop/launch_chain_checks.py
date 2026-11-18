#!/usr/bin/env python3
"""Check 517 (lane/launch-chain): the launch chain (tools/loop/launch_chain.py) and the watchdog's 5-minute rule
(tools/loop/mechanism_watchdog.py chain_check), Seckin 18 November 2026 13:40 ("Bekletilmesin"), with the
lead's rules of 13:48 and 13:52 and the review of 393a1d37 (the lead, 14:08).

On invented fixture folders in a temporary directory: each holds a chain.json, a fake launch.py (PURPOSES as a
literal, a `launch.py status` table from fake.json, a preflight exit code, the request and the admission written
as the real steps would, a ledger step marked running and its own controller log written, a fake budget ledger
lock taken and freed the way a starting controller does, GuardRefusals and stale refusals on request) and a fake
watch.py. No provider call, no key, no ledger of the loop: the mechanism paths point into the temporary folder.

  admit_then_part_same_move     admit in the foreground, then the part in the same pass, with its watcher
  request_then_seal_same_move   a written request is followed by its seal at once, in the same pass
  unfinished_prerequisite_stays a running seal or a seal ended with exit 2 keeps admit and the part waiting
  failed_preflight_alerts       a failing launch.py preflight writes ALERT.md and launches nothing
  lock_prevents_overlap         a held chain lock makes a second pass launch nothing; a lock left by an ended pass
                                frees with it (the file is never deleted); held by another handle in this process
                                and by another process, on Windows and on Linux alike
  request_waits_for_quiet_ledger a request waits for a quiet ledger, then its seal follows with nothing between
  stale_request_set_aside       a seal refused (non-zero) as stale renames the chain's own request aside, and the next
                                pass writes a new one
  stale_needs_nonzero_exit      a seal exiting 0 with the stale phrase leaves its request alone
  stale_three_alert             three stale refusals in a row write ALERT.md
  foreign_request_untouched     a request folder the chain did not write (the lead writing it) is left alone, alerted
  one_launch_at_a_time          two ready parts launch one after the other, never into a held ledger lock
  guard_refusal_held_retried    a GuardRefusal is not a launch: held 10 minutes, then tried again
  guard_three_alert             three GuardRefusals in a row write ALERT.md
  own_log_new_bytes_only        only the step's own log and its bytes after this launch count: a running sibling's
                                old refusal and this step's own old one hide no real launch
  lead_launches_meanwhile       a launch made by the lead between preflight and launch (a launch_intent line) is
                                seen on the fresh reading and not launched again
  killed_pass_leaves_record     a pass killed mid-launch leaves launch_started: launching, then unconfirmed, never
                                launched again
  folder_fault_contained        one folder whose status fails is traced and alerted, the next folder still launches
  dry_run_writes_nothing        --dry-run names the ready step, runs only status and writes nothing
  chain_paths_refused           '..' and absolute paths in chain.json are refused
  clear_checked                 --clear names an existing FOLDER:STEP and takes the lock
  watchdog_five_minutes         a step ready over 5 minutes alerts and starts one pass; under 5 minutes it does not
  watchdog_pass_started_apart   the watchdog's pass breaks away from the job (falling back without), has no
                                --force-retry, and its status reads are bounded
  marker_window_only            a request folder made by hand after an old marker is left alone; a chain request's
                                marker is retired once its done file is there
  timeout_unconfirmed           a ledger launch call that times out after launch_started is held unconfirmed, alerted,
                                and not tried again 11 minutes later
  ledger_step_declared          a ledger step without a purpose, or one after admit without controller_logs, is refused
  seal_follows_budget           the seal after its request is begun past the pass budget; another folder is not
  quiet_after_preflight         the quiet-ledger wait sits right before the request call: a launch line written during
                                preflight still holds the request back
  links_skipped                 a junction launch folder and a controller log reached through a junction are skipped
  repo_limited                  requires.repo outside the main checkout and its worktrees is refused, git not called
  guard_alert_quotes_line       the GuardRefusal alert quotes the refusal line from the log

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import launch_chain as lc  # noqa: E402
import mechanism_common as mc  # noqa: E402
import mechanism_watchdog as wd  # noqa: E402

REAL_IS_REPARSE = lc.is_reparse

FAKE_LAUNCH = r'''
PURPOSES = {'seal': 'fx-seal', 'part': 'fx-part', 'partA': 'fx-parta', 'partB': 'fx-partb'}
import datetime, json, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
S = json.loads((HERE / 'fake.json').read_text(encoding='utf-8'))
LOCK = Path(S['ledger_lock'])
step = sys.argv[1] if len(sys.argv) > 1 else 'status'
with open(HERE / 'calls.log', 'a', encoding='utf-8') as f:
    f.write('%s %r\n' % (step, time.time()))
def save():
    (HERE / 'fake.json').write_text(json.dumps(S), encoding='utf-8')
def own_log(name):
    log = HERE / 'admitted' / ('B_' + name) / 'controller_detached.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    return log
if step == 'status':
    if S.get('status_rc'):
        raise SystemExit(S['status_rc'])
    for name, (cost, state, phase) in S['status'].items():
        print(name, (cost, state), phase)
    raise SystemExit(0)
if step == 'preflight':
    rc = S.get('preflight_rc', 0)
    lead = S.pop('lead_launch_on_preflight', None)
    if lead:
        save()
        with open(S['ledger'], 'a', encoding='utf-8') as f:
            f.write(json.dumps({'event': 'launch_intent', 'purpose': PURPOSES[lead],
                                'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}) + '\n')
    other = S.pop('ledger_line_on_preflight', None)
    if other:
        save()
        with open(S['ledger'], 'a', encoding='utf-8') as f:
            f.write(json.dumps({'event': 'launch', 'purpose': other,
                                'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}) + '\n')
    print('preflight: free RAM 3.00 GiB; ' + ('all checks hold' if rc == 0 else 'free RAM 1.00 GiB is under 1.2'))
    raise SystemExit(rc)
if step == 'request':
    time.sleep(S.get('slow_request', 0))
    (HERE / 'request').mkdir(exist_ok=True)
    (HERE / 'request' / 'seal_request.json').write_text('{}', encoding='utf-8')
    raise SystemExit(0)
if step == 'admit':
    (HERE / 'admitted').mkdir(exist_ok=True)
    (HERE / 'admitted' / 'admission.json').write_text(json.dumps({'admitted': 2, 'requests': 2}), encoding='utf-8')
    print('started detached, pid 1')
    raise SystemExit(0)
for rel, text in S.get('touch_on_launch', {}).get(step, []):
    with open(HERE / rel, 'a', encoding='utf-8') as f:
        f.write(text + '\n')
if step in S.get('hang', []):
    S['hang'].remove(step)
    save()
    time.sleep(6)
    raise SystemExit(0)
if step in S.get('stale_once', []):
    S['stale_once'].remove(step)
    save()
    print('Seal request read copy is stale; write the request again')
    raise SystemExit(1)
print('Controller started detached')
if step in S.get('stale_rc0', []):
    print('note: a read copy is stale elsewhere, not this request')
refuse = step in S.get('refuse_once', [])
if LOCK.exists() or refuse:
    with open(own_log(step), 'a', encoding='utf-8') as f:
        f.write(S.get('refusal_line', 'GuardRefusal: Another launch holds the ledger lock') + '\n')
    if refuse:
        S['refuse_once'].remove(step)
        save()
    raise SystemExit(0)
LOCK.write_text('held', encoding='utf-8')
with open(own_log(step), 'a', encoding='utf-8') as f:
    f.write('controller started, phase activation\n')
S['status'][step] = [0.0, 'running', {}]
save()
subprocess.Popen([sys.executable, '-c', 'import time, pathlib; time.sleep(1.5); pathlib.Path(%r).unlink()' % str(LOCK)])
raise SystemExit(0)
'''

FAKE_WATCH = r'''
import sys
from pathlib import Path
with open(Path(__file__).resolve().parent / 'watch_calls.log', 'a', encoding='utf-8') as f:
    f.write(sys.argv[1] + '\n')
'''

ENDED = [0.5, 'ended', {'workload_return': {'exit_code': 0}}]
FAILED = [0.5, 'ended', {'workload_return': {'exit_code': 2}}]
RUNNING = [0.1, 'running', {}]
NOT = [0.0, 'not launched', {}]


def gate_chain(parts=('part',)):
    steps = [{'step': 'request', 'kind': 'request', 'done_when': {'exists': 'request/seal_request.json'}},
             {'step': 'seal', 'kind': 'ledger', 'after': ['request'], 'watch': True,
              'controller_logs': ['admitted/B_seal/controller_detached.log']},
             {'step': 'admit', 'kind': 'admit', 'after': ['seal'], 'admit_wait_minutes': 0.05}]
    for p in parts:
        steps.append({'step': p, 'kind': 'ledger', 'after': ['admit'], 'watch': True,
                      'controller_logs': ['admitted/B_%s/controller_detached.log' % p]})
    return {'chain': 1, 'steps': steps}


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self.tmp.name)
        self.private = self.base / 'private'
        self.private.mkdir()
        self.root = self.base / 's05'
        self.root.mkdir()
        self.patches = [patch.object(mc, 'PRIVATE', self.private), patch.object(mc, 'TRACE', self.private / 'trace.jsonl'),
                        patch.object(mc, 'ALERT', self.private / 'ALERT.md'),
                        patch.object(mc, 'ALERT_STATE', self.private / 'alert_state.json'),
                        patch.object(mc, 'MAIN', self.base), patch.object(lc, 'LOCK_POLL_S', 0.2),
                        patch.object(lc, 'POLL_S', 0.2), patch.object(lc, 'CONFIRM_WAIT_S', 4),
                        patch.object(lc, 'LEDGER_LOCK_WAIT_S', 10), patch.object(lc, 'REQUEST_QUIET_S', 1),
                        patch.object(lc, 'REQUEST_QUIET_WAIT_S', 20)]

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        lc.release_lock()
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def folder(self, name, chain, status, request=True, admitted=False, **fake):
        d = self.root / name
        d.mkdir()
        (d / 'launch.py').write_text(FAKE_LAUNCH, encoding='utf-8')
        (d / 'watch.py').write_text(FAKE_WATCH, encoding='utf-8')
        (d / 'chain.json').write_text(json.dumps(chain), encoding='utf-8')
        fake = dict(fake, status=status, ledger_lock=str(self.private / 'budget_ledger.jsonl.lock'),
                    ledger=str(self.private / 'budget_ledger.jsonl'))
        (d / 'fake.json').write_text(json.dumps(fake), encoding='utf-8')
        if request:
            (d / 'request').mkdir()
            (d / 'request' / 'seal_request.json').write_text('{}', encoding='utf-8')
        if admitted:
            (d / 'admitted').mkdir()
            (d / 'admitted' / 'admission.json').write_text(json.dumps({'admitted': 2, 'requests': 2}), encoding='utf-8')
        return d

    def calls(self, d, name='calls.log'):
        try:
            return [x.split()[0] for x in (d / name).read_text(encoding='utf-8').splitlines() if x.strip()]
        except OSError:
            return []

    def launches(self, d):
        return [x for x in self.calls(d) if x not in ('status', 'preflight')]

    def watchers(self, d, want, wait_s=8):
        end = time.time() + wait_s
        while time.time() < end and len(self.calls(d, 'watch_calls.log')) < want:
            time.sleep(0.2)
        return sorted(self.calls(d, 'watch_calls.log'))

    def results(self):
        return [x.get('result') for x in mc.read_trace() if x.get('mechanism') == lc.NAME]

    def alert_text(self):
        try:
            return mc.ALERT.read_text(encoding='utf-8')
        except OSError:
            return ''

    def state(self, folder, step):
        return lc.plan(self.root)[0][folder][step]['state']


@contextlib.contextmanager
def later(minutes):
    real = mc.now
    with patch.object(mc, 'now', lambda: real() + dt.timedelta(minutes=minutes)):
        yield


def caught(fn):
    try:
        return fn()
    except BaseException as exc:  # noqa: BLE001 - a neutralised proof may raise anything
        return 'raised %s' % type(exc).__name__


# ---- proofs ----

def observe_admit_then_part_same_move():
    with Fixture() as f:
        d = f.folder('G', gate_chain(), {'seal': ENDED, 'part': NOT})
        lc.run_once(f.root)
        return f.launches(d), (d / 'admitted' / 'admission.json').is_file(), f.watchers(d, 1), \
            f.results().count('launch'), 'admit_done' in f.results()


def expected_admit_then_part_same_move():
    return ['admit', 'part'], True, ['part'], 2, True


def neutralise_admit_then_part_same_move():
    return patch.object(lc, 'admitted_all', lambda folder, step: False)


def observe_request_then_seal_same_move():
    with Fixture() as f:
        d = f.folder('F', gate_chain(), {'seal': NOT, 'part': NOT}, request=False)
        lc.run_once(f.root)
        return f.launches(d), f.watchers(d, 1)


def expected_request_then_seal_same_move():
    return ['request', 'seal'], ['seal']


def neutralise_request_then_seal_same_move():
    return patch.object(lc, 'passes_for', lambda chain: 1)


def observe_unfinished_prerequisite_stays():
    with Fixture() as f:
        a = f.folder('R', gate_chain(), {'seal': RUNNING, 'part': NOT})
        b = f.folder('X', gate_chain(), {'seal': FAILED, 'part': NOT})
        lc.run_once(f.root)
        plans, _ = lc.plan(f.root)
        return (f.launches(a), f.launches(b), plans['R']['admit']['state'], plans['X']['seal']['state'],
                plans['X']['admit']['state'], 'X seal failed' in f.alert_text())


def expected_unfinished_prerequisite_stays():
    return [], [], 'waiting', 'failed', 'waiting', True


def neutralise_unfinished_prerequisite_stays():
    real = lc.own_state

    def lax(folder, step, status, rows=(), t=None):
        state, why = real(folder, step, status, rows, t)
        return ('done', why) if state in ('running', 'failed') else (state, why)
    return patch.object(lc, 'own_state', lax)


def observe_failed_preflight_alerts():
    with Fixture() as f:
        d = f.folder('P', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True, preflight_rc=1)
        lc.run_once(f.root)
        return f.launches(d), 'preflight_failed' in f.results(), 'P part is ready but launch.py preflight failed' in f.alert_text()


def expected_failed_preflight_alerts():
    return [], True, True


def neutralise_failed_preflight_alerts():
    real = lc.call_launch

    def ignore(folder, args, timeout):
        rc, out, err = real(folder, args, timeout)
        return (0, out, err) if args == ['preflight'] else (rc, out, err)
    return patch.object(lc, 'call_launch', ignore)


def observe_lock_prevents_overlap():
    with Fixture() as f:
        d = f.folder('L', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True)
        held, _ = lc.acquire_lock()          # another pass holds the lock (its own open handle)
        lc.run_once(f.root)
        first = (held, f.launches(d), f.results()[-1])
        lc.release_lock()                     # that pass ended (or died): the file stays, the lock is free
        lc.run_once(f.root)
        second = (f.launches(d), f.results()[-1], lc.lock_path().exists())
    with Fixture() as f:                      # the same with the holder in another process (the real case)
        d = f.folder('L', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True)
        lc.lock_path().parent.mkdir(parents=True, exist_ok=True)
        lc.lock_path().touch()                # the lock file the child opens
        code = ('import sys; sys.path.insert(0, sys.argv[1]); import launch_chain as lc; '
                'f = open(sys.argv[2], "r+b"); lc._lock_region(f, True); print("held", flush=True); sys.stdin.readline()')
        child = subprocess.Popen([sys.executable, '-c', code, str(HERE), str(lc.lock_path())], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, text=True, creationflags=mc.no_window())
        try:
            ready = child.stdout.readline().strip()
            lc.run_once(f.root)
            third = (ready, f.launches(d), f.results()[-1])
        finally:
            child.stdin.close()
            child.wait(timeout=60)
        lc.run_once(f.root)                   # the holding process ended: the lock is free again
        return first, second, third, (f.launches(d), f.results()[-1])


def expected_lock_prevents_overlap():
    return ((True, [], 'locked'), (['part'], 'ok', True), ('held', [], 'locked'), (['part'], 'ok'))


def neutralise_lock_prevents_overlap():
    return patch.object(lc, 'acquire_lock', lambda t=None: (True, None))


def observe_request_waits_for_quiet_ledger():
    with Fixture() as f:
        d = f.folder('Y', gate_chain(), {'seal': NOT, 'part': NOT}, request=False)
        other = time.time()
        stamp = dt.datetime.fromtimestamp(other, dt.timezone.utc).isoformat()
        (f.private / 'budget_ledger.jsonl').write_text(json.dumps(
            {'event': 'launch', 'purpose': 'another-folder-part', 'time_utc': stamp}) + '\n', encoding='utf-8')
        with patch.object(lc, 'REQUEST_QUIET_S', 3):
            lc.run_once(f.root)
        rows = [x.split() for x in (d / 'calls.log').read_text(encoding='utf-8').splitlines()]
        when = {s: float(t) for s, t in rows if s in ('request', 'seal')}
        between = [s for s, t in rows if 'request' in when and when['request'] < float(t) < when.get('seal', 0)]
        return f.launches(d), when.get('request', 0) - other >= 3, [s for s in between if s not in ('status', 'preflight')]


def expected_request_waits_for_quiet_ledger():
    return ['request', 'seal'], True, []


def neutralise_request_waits_for_quiet_ledger():
    return patch.object(lc, 'wait_quiet_ledger', lambda: True)


def observe_stale_request_set_aside():
    with Fixture() as f:
        d = f.folder('Z', gate_chain(), {'seal': NOT, 'part': NOT}, request=False, stale_once=['seal'])
        lc.run_once(f.root)
        time.sleep(1.2)
        lc.run_once(f.root)
        aside = sorted(p.name.split('_')[1] for p in d.glob('request_stale_*'))
        return (f.launches(d), aside, 'request_stale' in f.results(), (d / 'request' / 'seal_request.json').is_file(),
                f.state('Z', 'seal'))


def expected_stale_request_set_aside():
    return ['request', 'seal', 'request', 'seal'], ['stale'], True, True, 'running'


def neutralise_stale_request_set_aside():
    return patch.object(lc, 'set_aside', lambda folder, relative: None)


def observe_stale_needs_nonzero_exit():
    with Fixture() as f:
        d = f.folder('N', gate_chain(), {'seal': NOT, 'part': NOT}, request=False, stale_rc0=['seal'])
        lc.run_once(f.root)
        return f.launches(d), sorted(p.name for p in d.glob('request*')), f.state('N', 'seal')


def expected_stale_needs_nonzero_exit():
    return ['request', 'seal'], ['request', 'request.launch_chain.json'], 'running'


def neutralise_stale_needs_nonzero_exit():
    return patch.object(lc, 'seal_refused_stale', lambda rc, text: lc.STALE_MARK in text.lower())


def observe_stale_three_alert():
    with Fixture() as f:
        d = f.folder('S', gate_chain(), {'seal': NOT, 'part': NOT}, request=False, stale_once=['seal', 'seal', 'seal'])
        texts = []
        for _ in range(3):
            lc.run_once(f.root)
            texts.append('refused as stale' in f.alert_text())
            time.sleep(1.2)
        return f.launches(d).count('seal'), len(list(d.glob('request_stale_*'))), texts


def expected_stale_three_alert():
    return 3, 3, [False, False, True]


def neutralise_stale_three_alert():
    return patch.object(lc, 'stale_in_a_row', lambda folder_name, step_name: 0)


def observe_foreign_request_untouched():
    with Fixture() as f:
        d = f.folder('W', gate_chain(), {'seal': NOT, 'part': NOT}, request=False)
        (d / 'request').mkdir()
        (d / 'request' / 'half_written.tar').write_text('the lead is writing this', encoding='utf-8')
        lc.run_once(f.root)
        return (f.launches(d), sorted(p.name for p in d.glob('request*')),
                'was not written by the chain' in f.alert_text())


def expected_foreign_request_untouched():
    return [], ['request'], True


def neutralise_foreign_request_untouched():
    return patch.object(lc, 'chain_wrote', lambda folder, step: True)


def observe_one_launch_at_a_time():
    with Fixture() as f:
        d = f.folder('T', gate_chain(('partA', 'partB')), {'seal': ENDED, 'partA': NOT, 'partB': NOT}, admitted=True)
        (f.private / 'budget_ledger.jsonl.lock').write_text('another launch', encoding='utf-8')
        threading.Timer(3.0, lambda: (f.private / 'budget_ledger.jsonl.lock').unlink()).start()
        lc.run_once(f.root)
        plans, _ = lc.plan(f.root)
        return f.launches(d), plans['T']['partA']['state'], plans['T']['partB']['state'], 'guard_refused' in f.results()


def expected_one_launch_at_a_time():
    return ['partA', 'partB'], 'running', 'running', False


def neutralise_one_launch_at_a_time():
    stack = contextlib.ExitStack()
    stack.enter_context(patch.object(lc, 'wait_ledger_lock', lambda limit_s=None: True))
    stack.enter_context(patch.object(lc, 'confirm_launch', lambda *a: ('confirmed', 'assumed')))
    return stack


def observe_guard_refusal_held_retried():
    with Fixture() as f:
        d = f.folder('Q', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True, refuse_once=['part'])
        lc.run_once(f.root)
        first = f.state('Q', 'part')
        lc.run_once(f.root)                       # within the 10 minutes: held, not tried
        held_calls = f.launches(d).count('part')
        with later(11):
            lc.run_once(f.root)
            final = f.state('Q', 'part')
        return f.launches(d), f.results().count('guard_refused'), first, held_calls, final


def expected_guard_refusal_held_retried():
    return ['part', 'part'], 1, 'held', 1, 'running'


def neutralise_guard_refusal_held_retried():
    return patch.object(lc, 'refusal_seen', lambda *a: None)


def observe_guard_three_alert():
    with Fixture() as f:
        f.folder('V', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True, refuse_once=['part', 'part', 'part'])
        texts = []
        for k in range(3):
            with later(11 * k):
                lc.run_once(f.root)
            texts.append('was refused 3 times in a row' in f.alert_text())
        return f.results().count('guard_refused'), texts


def expected_guard_three_alert():
    return 3, [False, False, True]


def neutralise_guard_three_alert():
    return patch.object(lc, 'in_a_row', lambda *a: 0)


def observe_own_log_new_bytes_only():
    with Fixture() as f:
        d = f.folder('O', gate_chain(('partA', 'partB')), {'seal': ENDED, 'partA': RUNNING, 'partB': NOT}, admitted=True,
                     touch_on_launch={'partB': [['admitted/B_partA/controller_detached.log', 'sibling progress line']]})
        for name in ('B_partA', 'B_partB'):        # old refusals: the sibling's, and partB's own earlier attempt
            (d / 'admitted' / name).mkdir()
            (d / 'admitted' / name / 'controller_detached.log').write_text(
                'GuardRefusal: Another launch holds the ledger lock\n', encoding='utf-8')
        lc.run_once(f.root)
        return f.launches(d), 'guard_refused' in f.results(), f.state('O', 'partB')


def expected_own_log_new_bytes_only():
    return ['partB'], False, 'running'


def neutralise_own_log_new_bytes_only():
    def any_log(folder, step, offsets):         # the reviewed form: any log in the folder, read whole
        for log in Path(folder).glob('admitted/*/controller_detached.log'):
            if 'GuardRefusal' in log.read_text(encoding='utf-8'):
                return str(log), 'GuardRefusal'
        return None
    return patch.object(lc, 'refusal_seen', any_log)


def observe_lead_launches_meanwhile():
    with Fixture() as f:
        d = f.folder('M', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True, lead_launch_on_preflight='part')
        lc.run_once(f.root)
        return f.launches(d), 'already_launched' in f.results(), f.state('M', 'part')


def expected_lead_launches_meanwhile():
    return [], True, 'launching'


def neutralise_lead_launches_meanwhile():
    return patch.object(lc, 'still_not_launched', lambda folder, step: None)


def observe_killed_pass_leaves_record():
    with Fixture() as f:
        f.folder('K', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True)
        real, calls = lc.call_launch, []

        def dies_once(folder, args, timeout):
            if args == ['part']:
                calls.append(1)
                if len(calls) == 1:
                    raise KeyboardInterrupt('the task was ended mid-launch')
            return real(folder, args, timeout)
        with patch.object(lc, 'call_launch', dies_once):
            try:
                lc.run_once(f.root)
            except KeyboardInterrupt:
                pass
            soon = f.state('K', 'part')
            lc.run_once(f.root)
            with later(30):
                late = f.state('K', 'part')
                lc.run_once(f.root)
            return len(calls), soon, late, 'never confirmed' in f.alert_text()


def expected_killed_pass_leaves_record():
    return 1, 'launching', 'unconfirmed', True


def neutralise_killed_pass_leaves_record():
    return patch.object(lc, 'record_intent', lambda folder, step: None)


def observe_folder_fault_contained():
    with Fixture() as f:
        f.folder('A', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True, status_rc=1)
        b = f.folder('B', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True)
        lc.run_once(f.root)
        return f.launches(b), 'folder_error' in f.results(), 'A could not be handled' in f.alert_text()


def expected_folder_fault_contained():
    return ['part'], True, True


def neutralise_folder_fault_contained():
    return patch.object(lc, 'FOLDER_FAULTS', ())


def snapshot(folder):
    return sorted((str(p.relative_to(folder)), p.stat().st_size, p.stat().st_mtime_ns) for p in folder.rglob('*') if p.is_file())


def observe_dry_run_writes_nothing():
    with Fixture() as f:
        d = f.folder('D', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True)
        before = snapshot(f.private)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            lc.main(['--dry-run', '--root', str(f.root)])
        last = out.getvalue().strip().splitlines()[-1]
        return last.startswith('WOULD LAUNCH: D part'), sorted(set(f.calls(d))), snapshot(f.private) == before


def expected_dry_run_writes_nothing():
    return True, ['status'], True


def neutralise_dry_run_writes_nothing():
    real = lc.note_readiness
    return patch.object(lc, 'note_readiness', lambda plans, t, write=True: real(plans, t, True))


def observe_chain_paths_refused():
    with Fixture() as f:
        d = f.folder('C', gate_chain(), {'seal': ENDED, 'part': NOT})
        out = []
        for bad in ({'done_when': {'exists': '../elsewhere/seal_request.json'}}, {'done_when': {'exists': 'C:/x/y'}},
                    {'admission': '/abs/admission.json'}, {'controller_logs': ['..\\other\\log']},
                    {'requires': [{'folder': '..', 'step': 'x'}]}):
            chain = gate_chain()
            target = chain['steps'][0] if 'done_when' in bad else chain['steps'][2] if 'admission' in bad else chain['steps'][3]
            target.update(bad)
            (d / 'chain.json').write_text(json.dumps(chain), encoding='utf-8')
            out.append(caught(lambda: lc.load_chain(d) and 'accepted'))
        return out


def expected_chain_paths_refused():
    return ['raised ChainError'] * 5


def neutralise_chain_paths_refused():
    return patch.object(lc, '_relative', lambda value, what: value)


def observe_clear_checked():
    with Fixture() as f:
        f.folder('G', gate_chain(), {'seal': ENDED, 'part': NOT})
        out = [lc.clear('NOPE:part', f.root)[0], lc.clear('G:nostep', f.root)[0], lc.clear('../G:part', f.root)[0]]
        held, _ = lc.acquire_lock()
        out.append(lc.clear('G:part', f.root)[0])        # a pass holds the lock: refused
        lc.release_lock()
        out.append(lc.clear('G:part', f.root)[0])
        return out, f.results().count('cleared'), held


def expected_clear_checked():
    return [2, 2, 2, 3, 0], 1, True


def neutralise_clear_checked():
    return patch.object(lc, 'acquire_lock', lambda t=None: (True, None))


def observe_watchdog_five_minutes():
    with Fixture() as f:
        f.folder('W', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True)
        started = []
        t0 = mc.now()
        first = wd.chain_check(t=t0, root=f.root, start=lambda: started.append(1) or 99)
        early = wd.chain_check(t=t0 + dt.timedelta(minutes=4), root=f.root, start=lambda: started.append(1) or 99)
        late = wd.chain_check(t=t0 + dt.timedelta(minutes=6), root=f.root, start=lambda: started.append(1) or 99)
        return (len(first['late']), len(early['late']), [(x['folder'], x['step']) for x in late['late']],
                late['started'], len(started), 'ready for more than 5 minutes with no launch: W part' in f.alert_text())


def expected_watchdog_five_minutes():
    return 0, 0, [('W', 'part')], 99, 1, True


def neutralise_watchdog_five_minutes():
    real = lc.note_readiness

    def forgetful(plans, t, write=True):
        lc.save_state({})
        return real(plans, t, write)
    return patch.object(lc, 'note_readiness', forgetful)


def observe_watchdog_pass_started_apart():
    flags, argvs = [], []

    class Proc:
        pid = 7

    def popen(argv, creationflags=0, **kw):
        flags.append(bool(creationflags & 0x01000000))
        argvs.append(argv)
        if creationflags & 0x01000000:
            raise PermissionError('the job does not allow breakaway')
        return Proc()
    pid = wd.start_chain_pass(popen=popen)
    with Fixture() as f:
        f.folder('B', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True)
        timeouts = []
        real = lc.read_status
        with patch.object(lc, 'read_status', lambda folder, timeout=None: timeouts.append(timeout) or real(folder, timeout)):
            wd.chain_check(root=f.root, start=lambda: 0)
    refused = caught(lambda: lc.main(['--force-retry']))
    return pid, flags, any('--force-retry' in a for a in argvs), timeouts, refused


def expected_watchdog_pass_started_apart():
    return 7, [True, False], False, [60], 'raised SystemExit'


def neutralise_watchdog_pass_started_apart():
    return patch.object(wd, 'BREAKAWAY', 0)


def observe_marker_window_only():
    with Fixture() as f:
        d = f.folder('A1', gate_chain(), {'seal': NOT, 'part': NOT}, request=False)   # read first
        old = time.time() - 3600       # an old chain request call an hour ago, never retired
        (d / lc.MARKER).write_text(json.dumps({'mechanism': lc.NAME, 'request_dir': 'request', 'started_epoch': old,
                                               'ended_epoch': old + 10}), encoding='utf-8')
        (d / 'request').mkdir()          # the lead writes a request by hand now
        (d / 'request' / 'seal_source.tar').write_text('being written', encoding='utf-8')
        e = f.folder('E', gate_chain(), {'seal': NOT, 'part': NOT}, request=False)
        lc.run_once(f.root)
        marker = lc.read_marker(e)
        return (f.launches(d), sorted(p.name for p in d.glob('request*')), 'was not written by the chain' in f.alert_text(),
                f.launches(e), bool(marker.get('done_at')))


def expected_marker_window_only():
    return [], ['request', 'request.launch_chain.json'], True, ['request', 'seal'], True


def neutralise_marker_window_only():
    return patch.object(lc, 'chain_wrote', lambda folder, step, partial=False:
                        lc.read_marker(folder).get('request_dir') == lc.request_dir(step))


def observe_timeout_unconfirmed():
    with Fixture() as f, patch.dict(lc.TIMEOUT_S, {'ledger': 2}):
        d = f.folder('U', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True, hang=['part'])
        lc.run_once(f.root)
        first = f.state('U', 'part')
        with later(11):
            lc.run_once(f.root)
            again = f.state('U', 'part')
        return (f.launches(d).count('part'), first, again, 'launch_unconfirmed' in f.results(),
                'after launch_started' in f.alert_text())


def expected_timeout_unconfirmed():
    return 1, 'unconfirmed', 'unconfirmed', True, True


def neutralise_timeout_unconfirmed():
    return patch.object(lc, 'ledger_failure_result', lambda rc: 'launch_failed')


def observe_ledger_step_declared():
    with Fixture() as f:
        d = f.folder('P', gate_chain(), {'seal': ENDED, 'part': NOT})
        out = []
        for change in ({'step': 'extra'}, {'controller_logs': []}, {}):
            chain = gate_chain()
            part = chain['steps'][3]
            if 'controller_logs' in change:
                del part['controller_logs']
            if change.get('step'):
                part['step'] = change['step']      # no PURPOSES entry for it, none declared
            (d / 'chain.json').write_text(json.dumps(chain), encoding='utf-8')
            out.append(caught(lambda: lc.load_chain(d) and 'accepted'))
        return out


def expected_ledger_step_declared():
    return ['raised ChainError', 'raised ChainError', 'accepted']


def neutralise_ledger_step_declared():
    return patch.object(lc, 'check_ledger_step', lambda s, steps, purposes: None)


def observe_seal_follows_budget():
    with Fixture() as f, patch.object(lc, 'PASS_BUDGET_S', 1.5):
        a = f.folder('F', gate_chain(), {'seal': NOT, 'part': NOT}, request=False, slow_request=3)
        b = f.folder('Z2', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True)
        lc.run_once(f.root)
        return f.launches(a), f.launches(b)


def expected_seal_follows_budget():
    return ['request', 'seal'], []


def neutralise_seal_follows_budget():
    return patch.object(lc, 'seal_exempt', lambda chain, step, follow: False)


def observe_quiet_after_preflight():
    with Fixture() as f, patch.object(lc, 'REQUEST_QUIET_S', 3):
        d = f.folder('Q2', gate_chain(), {'seal': NOT, 'part': NOT}, request=False,
                     ledger_line_on_preflight='another-folder-part')
        lc.run_once(f.root)
        line = [r for r in lc.read_ledger() if r.get('purpose') == 'another-folder-part']
        when = dict(x.split() for x in (d / 'calls.log').read_text(encoding='utf-8').splitlines())
        gap = float(when.get('request', 0)) - lc.parse_time(line[0]['time_utc']).timestamp() if line else 0
        return f.launches(d), gap >= 3


def expected_quiet_after_preflight():
    return ['request', 'seal'], True


def neutralise_quiet_after_preflight():
    return patch.object(lc, 'wait_quiet_ledger', lambda: True)


def junction(link, target):
    """A junction (Windows) or a directory symlink (POSIX) at link pointing at target."""
    if os.name == 'nt':
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(str(target), str(link), target_is_directory=True)


def drop_link(link):
    """Remove a link as a link only (its target untouched): a junction by rmdir, a symlink by unlink."""
    if os.name == 'nt':
        os.rmdir(link)
    else:
        os.unlink(link)


def observe_links_skipped():
    with Fixture() as f:
        d = f.folder('G', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True,
                     touch_on_launch={'part': [['admitted/LINK/controller_detached.log', 'GuardRefusal: through a link']]})
        chain = gate_chain()
        chain['steps'][3]['controller_logs'] = ['admitted/*/controller_detached.log']
        (d / 'chain.json').write_text(json.dumps(chain), encoding='utf-8')
        outside = f.base / 'outside'
        outside.mkdir()
        (outside / 'controller_detached.log').write_text('old\n', encoding='utf-8')
        links = [f.root / 'J', d / 'admitted' / 'LINK']
        junction(links[0], d)
        junction(links[1], outside)
        try:
            names = [p.name for p in lc.chain_folders(f.root)]
            lc.run_once(f.root)
            return names, f.launches(d), 'guard_refused' in f.results(), f.state('G', 'part')
        finally:
            for link in links:          # each junction removed as a link, its target untouched
                if REAL_IS_REPARSE(link):
                    drop_link(link)


def expected_links_skipped():
    return ['G'], ['part'], False, 'running'


def neutralise_links_skipped():
    return patch.object(lc, 'is_reparse', lambda path: False)


def observe_repo_limited():
    with Fixture() as f:
        foreign = f.base / 'some-other-repo'
        foreign.mkdir()
        out, calls = [], []
        for repo in (foreign, f.base):
            d = f.folder('R' + str(len(out)), gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True)
            chain = gate_chain()
            chain['steps'][3]['requires'] = [{'commit': 'abcdef1', 'repo': str(repo)}]
            (d / 'chain.json').write_text(json.dumps(chain), encoding='utf-8')
            with patch.object(lc, 'git_is_ancestor', lambda r, c, ref: calls.append(Path(r).name) or True):
                row = lc.plan(f.root, folders=[d])[0][d.name]['part']
            out.append((row['state'], 'not the main checkout' in row['why']))
        return out, len(calls)


def expected_repo_limited():
    return [('waiting', True), ('ready', False)], 1


def neutralise_repo_limited():
    return patch.object(lc, 'repo_known', lambda repo: True)


def observe_guard_alert_quotes_line():
    with Fixture() as f, patch.object(lc, 'REPEAT_ALERT', 1):
        f.folder('Ql', gate_chain(), {'seal': ENDED, 'part': NOT}, admitted=True, refuse_once=['part'],
                 refusal_line='GuardRefusal: Another launch holds the ledger lock (budget_ledger.jsonl.lock, held 12 s, '
                              'by pid 4242 (running))')
        lc.run_once(f.root)
        return 'by pid 4242 (running)' in f.alert_text(), 'guard_refused' in f.results()


def expected_guard_alert_quotes_line():
    return True, True


def neutralise_guard_alert_quotes_line():
    real = lc.refusal_seen
    return patch.object(lc, 'refusal_seen', lambda folder, step, offsets: (lambda r: r and (r[0], 'GuardRefusal'))(
        real(folder, step, offsets)))


PROOFS = ('admit_then_part_same_move', 'request_then_seal_same_move', 'unfinished_prerequisite_stays',
          'failed_preflight_alerts', 'lock_prevents_overlap', 'request_waits_for_quiet_ledger',
          'stale_request_set_aside', 'stale_needs_nonzero_exit', 'stale_three_alert', 'foreign_request_untouched',
          'one_launch_at_a_time', 'guard_refusal_held_retried', 'guard_three_alert', 'own_log_new_bytes_only',
          'lead_launches_meanwhile', 'killed_pass_leaves_record', 'folder_fault_contained', 'dry_run_writes_nothing',
          'chain_paths_refused', 'clear_checked', 'watchdog_five_minutes', 'watchdog_pass_started_apart',
          'marker_window_only', 'timeout_unconfirmed', 'ledger_step_declared', 'seal_follows_budget',
          'quiet_after_preflight', 'links_skipped', 'repo_limited', 'guard_alert_quotes_line')


def run_all(names=None):
    done, space = [], globals()
    for name in names or PROOFS:
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
        done.append('%s (neutralised: %s)' % (name, str(broken)[:140]))
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass, no provider call: %s' % (len(done), '; '.join(done))


if __name__ == '__main__':
    status, detail = run_all(sys.argv[1:] or None)
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
