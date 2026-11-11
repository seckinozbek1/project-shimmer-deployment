"""Proofs for the session-end hook (D-S107 item 3, D-412): tools/loop/session_end_salvage.py,
tools/loop/register_session_hook.py and the reaper's session-end rule, on fakes only.

The script runs against the reaper's MockProvider (a JSON file standing in for the provider),
fixture ledgers (the private one and R's), a temporary salvage folder, report folder, FOR_SECKIN
and log, and a fake clock. The main checkout is found in a fixture git repository with a second
worktree. The registration is proven on its dry-run XML and a fake schtasks: no task is
registered. `check()` runs the tests, then neutralises each rule in turn, requires a failure,
restores it and requires a pass.

    py -3.12 -X utf8 tools/loop/session_hook_checks.py
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import instance_reaper as reaper  # noqa: E402
import register_session_hook as hook  # noqa: E402
import session_end_salvage as ses  # noqa: E402
from cloud_run_common import no_window  # noqa: E402

START = reaper.parse_time('2026-11-09T18:00:00+00:00')
A, B, C, D, E = ('a' * 32, 'b' * 32, 'c' * 32, 'd' * 32, 'e' * 32)


class FakeClock:
    def __init__(self):
        self.t, self.sleeps = 0.0, 0

    def clock(self):
        return self.t

    def sleep(self, seconds):
        self.sleeps += 1
        self.t += seconds


class FailingSecond(reaper.MockProvider):
    """The second termination raises, carrying a message that must never be printed."""

    def __init__(self, state_path):
        super().__init__(state_path)
        self.calls = 0

    def terminate(self, instance_id):
        self.calls += 1
        if self.calls == 2:
            raise ConnectionError('provider-message-marker')
        return super().terminate(instance_id)


def launch(item, when=START):
    return dict(event='launch', instance_id=item['instance_id'], instance_name=item['name'], price_usd_per_hour=1.29,
                cap_usd=20.0, launch_requested_utc=when.isoformat(), deadline_utc=(when + timedelta(hours=5)).isoformat())


def git(root, *args):
    return subprocess.run(['git', '-C', str(root)] + list(args), capture_output=True, text=True, check=True,
                          stdin=subprocess.DEVNULL, creationflags=no_window()).stdout.strip()


class SessionHookChecks(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        base = self.base = Path(self.folder.name)
        self.state = base / 'state.json'
        self.ledger = base / 'ledger.jsonl'
        self.r_ledger = base / 'R_ledger.jsonl'
        self.log = base / 'log.jsonl'
        self.lock = base / 'session_hook.lock'
        self.seckin = base / 'FOR_SECKIN.md'
        self.seckin.write_text('# For Seckin\n\nolder entry\n', encoding='utf-8')
        self.patches = [patch.object(reaper, 'SALVAGE_DIR', base / 'salvage'),
                        patch.object(reaper, 'REPORT_DIR', base / 'reports'),
                        patch.object(reaper, 'FOR_SECKIN', self.seckin)]
        for p in self.patches:
            p.start()
        self.instances = [
            {'instance_id': A, 'name': 'shimmer-loop-one', 'status': 'active', 'type': 'gpu_1x_a10', 'region': 'us-east-1'},
            {'instance_id': B, 'name': 'shimmer-loop-two', 'status': 'active', 'type': 'gpu_1x_a10', 'region': 'us-east-1'},
            {'instance_id': C, 'name': 'someone-else', 'status': 'active', 'type': 'gpu_1x_a10', 'region': 'us-east-1'},
            {'instance_id': D, 'name': 'shimmer-loop-r', 'status': 'active', 'type': 'gpu_1x_a10', 'region': 'us-east-1'},
            {'instance_id': E, 'name': 'shimmer-loop-unrecorded', 'status': 'active', 'type': 'gpu_1x_a10',
             'region': 'us-east-1'},
        ]
        self.state.write_text(json.dumps({'instances': self.instances}), encoding='utf-8')
        budget = dict(event='budget_open', time_utc=(START - timedelta(days=1)).isoformat(), budget_usd=500,
                      hard_stop_usd=499)
        self.ledger.write_text(''.join(json.dumps(l) + '\n' for l in [budget] + [launch(i) for i in self.instances[:2]]),
                               encoding='utf-8')
        self.r_ledger.write_text(json.dumps(launch(self.instances[3])) + '\n', encoding='utf-8')
        self.provider = reaper.MockProvider(self.state)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.folder.cleanup()

    def statuses(self):
        return {i['name']: i['status'] for i in json.loads(self.state.read_text(encoding='utf-8'))['instances']}

    def terminations(self, path=None):
        rows = [json.loads(l) for l in Path(path or self.ledger).read_text(encoding='utf-8').splitlines() if l.strip()]
        return sorted((r['instance_name'], r['by'], r['reason']) for r in rows if r['event'] == 'termination')

    def run_pass(self, event_id='1074', clock=None, provider=None, kind='mock', answer_seconds=0):
        clock = clock or FakeClock()
        return ses.run(provider or self.provider, [self.ledger, self.r_ledger], self.ledger, event_id, answer_seconds,
                       now=START, clock=clock.clock, sleep=clock.sleep, log_path=self.log, provider_kind=kind,
                       lock_path=self.lock), clock

    # D-412 item 1: terminate first, no wait, the requests still written

    def test_every_loop_instance_ends_at_once_and_its_records_are_written(self):
        written = []
        real_pass = reaper.salvage_pass

        def watching(now, running, due, *a, **k):
            episode = real_pass(now, running, due, *a, **k)
            written.extend(sorted(p.name for p in (reaper.SALVAGE_DIR / 'requests').iterdir()))
            return episode

        with patch.object(reaper, 'salvage_pass', watching):
            record, clock = self.run_pass('1074')
        self.assertEqual(clock.sleeps, 0)
        self.assertEqual(written, ['shimmer-loop-one.request.json', 'shimmer-loop-r.request.json',
                                   'shimmer-loop-two.request.json', 'shimmer-loop-unrecorded.request.json'])
        self.assertEqual(self.statuses(), {'shimmer-loop-one': 'terminated', 'shimmer-loop-two': 'terminated',
                                           'someone-else': 'active', 'shimmer-loop-r': 'terminated',
                                           'shimmer-loop-unrecorded': 'terminated'})
        report = Path(record['report'])
        text = report.read_text(encoding='utf-8')
        self.assertIn('Windows event 1074 (shutdown)', text)
        self.assertIn('terminated_by_session_end', text)
        self.assertIn('Salvage and stop (D-S84): 4 loop instance(s) stopped', self.seckin.read_text(encoding='utf-8'))
        self.assertFalse((reaper.SALVAGE_DIR / 'episode.json').exists())
        log = [json.loads(l) for l in self.log.read_text(encoding='utf-8').splitlines()]
        self.assertEqual((log[-1]['event'], log[-1]['event_id'], log[-1]['loop_running']), ('shutdown', '1074', 4))

    def test_no_event_waits_for_an_answer(self):
        for event_id in ('1074', '7002', '42', '506'):
            self.state.write_text(json.dumps({'instances': self.instances}), encoding='utf-8')
            record, clock = self.run_pass(event_id)
            self.assertEqual(clock.sleeps, 0, event_id)
            self.assertEqual(record['answer_seconds'], 0)
            self.assertEqual(len(record['terminated']), 4, event_id)

    # D-412 item 3: each termination in its own try

    def test_a_failed_termination_does_not_stop_the_next(self):
        out = io.StringIO()
        with patch('sys.stdout', out):
            record, _ = self.run_pass('7002', provider=FailingSecond(self.state))
        self.assertEqual(list(record['terminate_failed'].values()), ['ConnectionError'])
        failed = next(iter(record['terminate_failed']))
        self.assertEqual(len(record['terminated']), 3)
        self.assertEqual(self.statuses()[failed], 'active')
        self.assertNotIn(failed, [name for name, _, _ in self.terminations() + self.terminations(self.r_ledger)])
        self.assertNotIn('provider-message-marker', self.log.read_text(encoding='utf-8') + out.getvalue())
        self.assertIsNone(record['report'])
        episode = json.loads((reaper.SALVAGE_DIR / 'episode.json').read_text(encoding='utf-8'))
        self.assertEqual(episode['instances'][failed]['state'], 'terminate_failed')

    # D-412 items 6 and 7: R's instances, and a listed instance no ledger records

    def test_r_launches_and_unrecorded_instances_get_their_lines(self):
        self.run_pass('1074')
        self.assertEqual(self.terminations(self.r_ledger), [('shimmer-loop-r', 'session_hook', 'session_end_shutdown')])
        self.assertEqual(self.terminations(), [('shimmer-loop-one', 'session_hook', 'session_end_shutdown'),
                                               ('shimmer-loop-two', 'session_hook', 'session_end_shutdown'),
                                               ('shimmer-loop-unrecorded', 'session_hook', 'session_end_shutdown')])

    # D-412 item 5: one pass at a time; a stale episode is closed, never applied

    def test_a_held_lock_skips_and_a_dead_one_is_replaced(self):
        self.lock.write_text(json.dumps({'pid': 1, 'epoch': time.time()}), encoding='utf-8')
        record, _ = self.run_pass('1074')
        self.assertEqual(record['skipped'], 'another_pass_holds_the_lock')
        self.assertEqual(self.statuses()['shimmer-loop-one'], 'active')
        self.lock.write_text(json.dumps({'pid': 1, 'epoch': time.time() - 300}), encoding='utf-8')
        record, _ = self.run_pass('1074')
        self.assertEqual(len(record['terminated']), 4)
        self.assertFalse(self.lock.exists())
        self.assertIn('<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>',
                      hook.task_xml('u', Path('p'), Path('s'), Path('r')))

    def stale_episode(self):
        """An episode a session end left open before a reboot, naming an instance now gone."""
        reaper._write_json(reaper.SALVAGE_DIR / 'episode.json', {
            'id': '20261108T220000Z', 'started_utc': (START - timedelta(hours=20)).isoformat(),
            'trigger': {'trigger': 'session_end', 'event': 'shutdown', 'event_id': '1074'},
            'instances': {'shimmer-loop-old': {'instance_id': 'f' * 32, 'state': 'terminated_by_session_end'}}})
        state = {'instances': [dict(self.instances[0], name='shimmer-loop-new')]}
        self.state.write_text(json.dumps(state), encoding='utf-8')
        self.ledger.write_text(self.ledger.read_text(encoding='utf-8') +
                               json.dumps(launch(state['instances'][0], START)) + '\n', encoding='utf-8')

    def test_the_reaper_closes_a_stale_session_episode_and_spares_a_newer_launch(self):
        self.stale_episode()
        heartbeat = self.base / 'beat.txt'
        heartbeat.write_text('alive', encoding='utf-8')
        with patch.object(reaper, 'HEARTBEATS', (heartbeat,)), \
                patch.object(reaper, 'LOOP_STATUS', self.base / 'no_status.json'):
            result = reaper.reap(self.provider, [self.ledger], self.ledger, now=START + timedelta(minutes=1))
        self.assertEqual(self.statuses(), {'shimmer-loop-new': 'active'})
        self.assertFalse(reaper.request_path('shimmer-loop-new').exists())
        self.assertIsNotNone(result['salvage']['report'])
        self.assertFalse((reaper.SALVAGE_DIR / 'episode.json').exists())

    def test_the_hook_closes_a_stale_episode_before_its_own(self):
        self.stale_episode()
        record, _ = self.run_pass('1074')
        self.assertTrue(record['stale_episode_closed'].endswith('20261108T220000Z_stale'))
        self.assertEqual(self.statuses(), {'shimmer-loop-new': 'terminated'})
        stale = json.loads((Path(record['stale_episode_closed']) / 'episode.json').read_text(encoding='utf-8'))
        self.assertIn('closed_stale_utc', stale)
        text = Path(record['report']).read_text(encoding='utf-8')
        self.assertIn('closed as stale first', text)
        self.assertIn('# The earlier session-end episode closed as stale', text)
        self.assertIn('## shimmer-loop-old', text)
        self.assertIn('closed as stale', self.seckin.read_text(encoding='utf-8'))

    # D-412 item 1: the first real pass of each event is marked in the log

    def test_the_first_real_pass_of_an_event_is_marked(self):
        first, _ = self.run_pass('42', kind='real')
        self.assertTrue(first['first_real_of_event'])
        self.state.write_text(json.dumps({'instances': self.instances}), encoding='utf-8')
        again, _ = self.run_pass('42', kind='real')
        self.assertFalse(again['first_real_of_event'])
        other, _ = self.run_pass('7002', kind='real')
        self.assertTrue(other['first_real_of_event'])
        mock, _ = self.run_pass('506', kind='mock')
        self.assertFalse(mock['first_real_of_event'])

    def test_events_are_named(self):
        self.assertEqual([ses.event_name(e) for e in ('1074', '7002', '4647', '42', '506', 'x')],
                         ['shutdown', 'logoff', 'logoff', 'sleep', 'standby', 'manual'])

    def test_the_cli_runs_on_the_mock_and_keeps_errors_short(self):
        out = io.StringIO()
        args = ['--event-id', '506', '--mock-state', str(self.state), '--root', str(self.base), '--ledger', str(self.ledger),
                '--append-to', str(self.ledger), '--salvage-dir', str(self.base / 'salvage'), '--report-dir',
                str(self.base / 'reports'), '--for-seckin', str(self.seckin), '--log', str(self.log), '--now', START.isoformat()]
        with patch.object(ses, 'checked_root', lambda root, finder=None: Path(root)), patch('sys.stdout', out):
            self.assertEqual(ses.main(args), 0)
        self.assertIn('"event": "standby"', out.getvalue())
        self.state.write_text(json.dumps({'instances': [], 'raise_with': 'provider-message-marker'}), encoding='utf-8')
        out = io.StringIO()
        with patch.object(ses, 'checked_root', lambda root, finder=None: Path(root)), patch('sys.stdout', out):
            self.assertEqual(ses.main(args), 1)
        self.assertNotIn('provider-message-marker', out.getvalue() + self.log.read_text(encoding='utf-8'))
        self.assertIn('RuntimeError', out.getvalue())

    # D-412 items 2 and 4: one main checkout, from either checkout

    def test_every_path_is_the_main_checkouts_from_either_checkout(self):
        if shutil.which('git') is None:
            self.skipTest('git is not installed here')
        main = self.base / 'main'
        main.mkdir()
        git(main, 'init', '-q', '-b', 'loop')
        for key, value in (('user.email', 'f@example.invalid'), ('user.name', 'f'), ('commit.gpgsign', 'false')):
            git(main, 'config', key, value)
        (main / 'x.txt').write_text('x\n', encoding='utf-8')
        git(main, 'add', 'x.txt')
        git(main, 'commit', '-q', '-m', 'x')
        git(main, 'worktree', 'add', '-q', str(self.base / 'lane'), '-b', 'lane')
        found = {ses.main_root(main).resolve(), ses.main_root(self.base / 'lane').resolve()}
        self.assertEqual(found, {main.resolve()})
        where = ses.main_paths(ses.main_root(self.base / 'lane'))
        private = main.resolve() / 'docs' / 'loop' / 'private'
        self.assertEqual((where['ledger'], where['salvage'], where['log'], where['for_seckin']),
                         (private / 'budget_ledger.jsonl', private / 'salvage', private / 'session_hook_log.jsonl',
                          private / 'FOR_SECKIN.md'))
        self.assertEqual(ses.checked_root(main), main.resolve())
        with self.assertRaises(ses.HookError):
            ses.checked_root(self.base / 'lane')
        with self.assertRaises(hook.RegisterError):
            hook.main_script(main)
        (main / 'tools' / 'loop').mkdir(parents=True)
        (main / 'tools' / 'loop' / 'session_end_salvage.py').write_text('# hook\n', encoding='utf-8')
        self.assertEqual(hook.main_script(main), main / 'tools' / 'loop' / 'session_end_salvage.py')

    # D-435: git missing, a launch newer than an open session episode, one listing

    def test_a_missing_git_falls_back_to_the_scripts_checkout_and_says_so(self):
        def no_git(start=None, runner=None):
            raise ses.HookError('The main checkout cannot be found from git (FileNotFoundError)')
        root, how = ses.resolve_root(None, finder=no_git)
        self.assertEqual(root, ses.HERE.parents[1])
        self.assertTrue(how.startswith('script_location'))
        out = io.StringIO()
        args = ['--event-id', '1074', '--mock-state', str(self.state), '--ledger', str(self.ledger),
                '--append-to', str(self.ledger), '--salvage-dir', str(self.base / 'salvage'), '--report-dir',
                str(self.base / 'reports'), '--for-seckin', str(self.seckin), '--log', str(self.log), '--now', START.isoformat()]
        with patch.object(ses, 'main_root', no_git), patch('sys.stdout', out):
            self.assertEqual(ses.main(args), 0)
        logged = json.loads(self.log.read_text(encoding='utf-8').splitlines()[-1])
        self.assertTrue(logged['root_from'].startswith('script_location'))
        self.assertEqual(len(logged['terminated']), 4)

    def test_a_newer_launch_under_an_open_session_episode_still_meets_the_triggers(self):
        self.stale_episode()
        state = json.loads(self.state.read_text(encoding='utf-8'))
        state['instances'].append(dict(self.instances[1], name='shimmer-loop-old', instance_id='f' * 32))
        self.state.write_text(json.dumps(state), encoding='utf-8')
        silent = self.base / 'beat.txt'
        silent.write_text('old', encoding='utf-8')
        old = (START - timedelta(hours=3)).timestamp()   # relative to the pass's own clock, never the wall clock
        import os
        os.utime(silent, (old, old))
        with patch.object(reaper, 'HEARTBEATS', (silent,)), \
                patch.object(reaper, 'LOOP_STATUS', self.base / 'no_status.json'):
            reaper.reap(self.provider, [self.ledger], self.ledger, now=START + timedelta(minutes=1))
        self.assertTrue(reaper.request_path('shimmer-loop-new').exists())
        request = json.loads(reaper.request_path('shimmer-loop-new').read_text(encoding='utf-8'))
        self.assertEqual(request['trigger'], 'lead_silent')
        episode = json.loads((reaper.SALVAGE_DIR / 'episode.json').read_text(encoding='utf-8'))
        self.assertEqual(episode['instances']['shimmer-loop-new']['trigger']['trigger'], 'lead_silent')
        text = reaper.salvage_report(episode, START)
        self.assertIn('- Trigger for this instance: no lead heartbeat since', text)
        self.assertIn('no lead heartbeat', reaper.episode_triggers(episode))

    def test_one_listing_before_the_first_termination(self):
        calls = []

        class Counting(reaper.MockProvider):
            def request(self, path, body=None):
                calls.append('list')
                return super().request(path, body)

            def terminate(self, instance_id):
                calls.append('terminate')
                return super().terminate(instance_id)

        self.run_pass('1074', provider=Counting(self.state))
        self.assertEqual(calls[:calls.index('terminate')], ['list'])

    # the registration

    def test_the_task_needs_no_password_and_runs_in_the_session(self):
        xml = hook.task_xml('HOST\\person', Path('C:/py/pythonw.exe'), Path('C:/repo/tools/loop/session_end_salvage.py'),
                            Path('C:/repo'))
        self.assertIn('<LogonType>InteractiveToken</LogonType>', xml)
        self.assertIn('<RunLevel>LeastPrivilege</RunLevel>', xml)
        self.assertNotIn('Password', xml)
        for provider, event in (('User32', 1074), ('Microsoft-Windows-Winlogon', 7002),
                                ('Microsoft-Windows-Kernel-Power', 42), ('Microsoft-Windows-Kernel-Power', 506)):
            self.assertIn("Provider[@Name=&apos;%s&apos;] and EventID=%d" % (provider, event), xml.replace("'", '&apos;'))
        self.assertNotIn('4647', xml)
        self.assertIn('4647', hook.task_xml('u', Path('p'), Path('s'), Path('r'), with_security=True))
        self.assertIn('--event-id $(eventId)', xml)
        self.assertIn('pythonw.exe', xml)
        self.assertEqual(xml.count('<Value name="eventId">'), 4)

    def test_registration_refuses_a_console_python_and_keeps_schtasks_output(self):
        exe = self.base / 'py' / 'python.exe'
        exe.parent.mkdir()
        exe.write_text('', encoding='utf-8')
        with self.assertRaises(hook.RegisterError):
            hook.windowless_python(exe)
        (exe.parent / 'pythonw.exe').write_text('', encoding='utf-8')
        self.assertEqual(hook.windowless_python(exe).name, 'pythonw.exe')
        result = type('R', (), {'returncode': 1, 'stdout': '', 'stderr': 'ERROR: Access is denied.'})()
        seen = []
        code, out, err = hook.register('<Task/>', runner=lambda argv, **kw: seen.append((argv, kw)) or result)
        self.assertEqual((code, err), (1, 'ERROR: Access is denied.'))
        self.assertEqual(seen[0][0][:4], ['schtasks', '/Create', '/TN', hook.TASK_NAME])
        self.assertIn('creationflags', seen[0][1])
        printed = io.StringIO()
        (self.base / 'tools' / 'loop').mkdir(parents=True)
        (self.base / 'tools' / 'loop' / 'session_end_salvage.py').write_text('# hook\n', encoding='utf-8')
        with patch.object(hook, 'register', lambda xml: (1, '', 'ERROR: Access is denied.')), \
                patch.object(hook, 'windowless_python', lambda executable=None: exe.parent / 'pythonw.exe'), \
                patch.object(ses, 'checked_root', lambda root, finder=None: Path(root)), \
                patch('sys.stdout', printed):
            self.assertEqual(hook.main(['--root', str(self.base), '--user', 'HOST\\person']), 1)
        self.assertIn('ERROR: Access is denied.', printed.getvalue())
        printed = io.StringIO()
        with patch.object(ses, 'checked_root', lambda root, finder=None: Path(root)), patch('sys.stdout', printed):
            self.assertEqual(hook.main(['--root', str(self.base / 'nowhere'), '--dry-run']), 2)
        self.assertIn('does not exist in the main checkout', printed.getvalue())

    def test_the_dry_run_registers_nothing(self):
        calls = []
        out = io.StringIO()
        (self.base / 'tools' / 'loop').mkdir(parents=True)
        (self.base / 'tools' / 'loop' / 'session_end_salvage.py').write_text('# hook\n', encoding='utf-8')
        with patch.object(hook, 'register', lambda xml, runner=None: calls.append(xml) or (0, '', '')), \
                patch.object(hook, 'windowless_python', lambda executable=None: Path('C:/py/pythonw.exe')), \
                patch.object(ses, 'checked_root', lambda root, finder=None: Path(root)), \
                patch('sys.stdout', out):
            self.assertEqual(hook.main(['--dry-run', '--user', 'HOST\\person', '--root', str(self.base)]), 0)
        self.assertEqual(calls, [])
        self.assertIn('<Task version="1.2"', out.getvalue())
        self.assertIn(str(self.base / 'tools' / 'loop' / 'session_end_salvage.py'), out.getvalue())


NEUTRALISED = (
    (ses, 'terminate_remaining', lambda *a, **k: ({}, {}),
     ('test_every_loop_instance_ends_at_once_and_its_records_are_written', 'test_no_event_waits_for_an_answer')),
    (ses, 'answered', lambda names: set(names),
     ('test_every_loop_instance_ends_at_once_and_its_records_are_written',)),
    (reaper, 'write_line', lambda paths, line: None, ('test_r_launches_and_unrecorded_instances_get_their_lines',)),
    (reaper, 'holders', lambda rec, rows_by_path: [], ('test_r_launches_and_unrecorded_instances_get_their_lines',)),
    (reaper, 'close_salvage', lambda *a, **k: None,
     ('test_every_loop_instance_ends_at_once_and_its_records_are_written',)),
    (ses, 'take_lock', lambda path, now_epoch: True, ('test_a_held_lock_skips_and_a_dead_one_is_replaced',)),
    (ses, 'LOCK_STALE_SECONDS', 10 ** 9, ('test_a_held_lock_skips_and_a_dead_one_is_replaced',)),
    (ses, 'close_stale_episode', lambda running, now: None, ('test_the_hook_closes_a_stale_episode_before_its_own',)),
    (ses, 'first_real', lambda log, event: True, ('test_the_first_real_pass_of_an_event_is_marked',)),
    (ses, 'event_name', lambda event_id: 'manual', ('test_events_are_named',)),
    (ses, 'main_root', lambda start=None, runner=None: Path(start), ('test_every_path_is_the_main_checkouts_from_either_checkout',)),
    (hook, 'main_script', lambda root: Path(root) / hook.SCRIPT,
     ('test_every_path_is_the_main_checkouts_from_either_checkout', 'test_registration_refuses_a_console_python_and_keeps_schtasks_output')),
    (ses, 'resolve_root', lambda given=None, finder=None: (_ for _ in ()).throw(ses.HookError('no git')),
     ('test_a_missing_git_falls_back_to_the_scripts_checkout_and_says_so',)),
    (ses, 'checked_root', lambda root, finder=None: Path(root).resolve(),
     ('test_every_path_is_the_main_checkouts_from_either_checkout',)),
    (reaper, 'salvage_trigger', lambda now, running, status_path=None, heartbeats=None: None,
     ('test_a_newer_launch_under_an_open_session_episode_still_meets_the_triggers',)),
    (hook, 'LOGON_TYPE', 'Password', ('test_the_task_needs_no_password_and_runs_in_the_session',)),
    (hook, 'TRIGGERS', (('System', 'User32', 1074),), ('test_the_task_needs_no_password_and_runs_in_the_session',)),
    (hook, 'windowless_python', lambda executable=None: Path(executable or sys.executable),
     ('test_registration_refuses_a_console_python_and_keeps_schtasks_output',)),
)


def _with_parallel(owner, name):
    """The task XML as it was before D-412 item 5 (Parallel), for its neutralisation."""
    original = hook.task_xml
    return lambda *a, **k: original(*a, **k).replace('IgnoreNew', 'Parallel')


def _terminate_unguarded():
    """terminate_remaining with the try removed: a failure stops the pass (D-412 item 3)."""
    def unguarded(provider, running, by_name, rows_by_path, append_path, now, event):
        for item in running:
            provider.terminate(item['instance_id'])
        return {}, {}
    return unguarded


def _waiting_run():
    """The pass as it was before D-412 item 1: every event waits for answers first."""
    original = ses.run
    return lambda provider, ledgers, append, event_id, answer_seconds=0, **k: original(
        provider, ledgers, append, event_id, 20, **k)


def _listing_again():
    """terminate_remaining listing the instances again before terminating (before D-435)."""
    original = ses.terminate_remaining

    def again(provider, running, *rest):
        return original(provider, reaper.loop_instances(provider.request('instances')['data']), *rest)
    return again


def _stale_unnamed():
    """open_episode dropping the stale episode's name from the trigger (before D-435)."""
    original = ses.open_episode
    return lambda now, event, event_id, running, stale=None: original(now, event, event_id, running)


EXTRA = (
    (ses, 'terminate_remaining', lambda *_: _listing_again(), ('test_one_listing_before_the_first_termination',)),
    (ses, 'open_episode', lambda *_: _stale_unnamed(), ('test_the_hook_closes_a_stale_episode_before_its_own',)),
    (reaper, 'episode_triggers', lambda *_: (lambda episode: reaper.trigger_words(episode['trigger'])),
     ('test_the_hook_closes_a_stale_episode_before_its_own', 'test_a_newer_launch_under_an_open_session_episode_still_meets_the_triggers')),
    (reaper, '_instance_lines', lambda *_: (lambda name, entry: (['## ' + name, ''], entry.get('done') or {})),
     ('test_a_newer_launch_under_an_open_session_episode_still_meets_the_triggers',)),
    (hook, 'task_xml', _with_parallel, ('test_a_held_lock_skips_and_a_dead_one_is_replaced',)),
    (ses, 'terminate_remaining', lambda *_: _terminate_unguarded(), ('test_a_failed_termination_does_not_stop_the_next',)),
    (ses, 'run', lambda *_: _waiting_run(), ('test_no_event_waits_for_an_answer',)),
)


def _reaper_applies_every_episode():
    """salvage_pass with the session-end rule removed (D-412 item 5)."""
    original = reaper.salvage_pass

    def applied(now, running, due, *a, **k):
        path = reaper.SALVAGE_DIR / 'episode.json'
        try:
            episode = reaper._read_json(path)
        except ValueError:
            episode = None
        if episode and episode.get('trigger', {}).get('trigger') == 'session_end':
            episode['trigger']['trigger'] = 'session_end_unscoped'
            reaper._write_json(path, episode)
        return original(now, running, due, *a, **k)
    return applied


def passes(*names):
    suite = unittest.TestSuite(SessionHookChecks(n) for n in names) if names else \
        unittest.defaultTestLoader.loadTestsFromTestCase(SessionHookChecks)
    return unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite).wasSuccessful()


def check():
    if not passes():
        return 'FAIL', 'tools/loop/session_hook_checks.py does not pass'
    proofs = []
    cases = [(o, n, m, t) for o, n, m, t in NEUTRALISED]
    cases += [(o, n, make(o, n), t) for o, n, make, t in EXTRA]
    cases.append((reaper, 'salvage_pass', _reaper_applies_every_episode(),
                  ('test_the_reaper_closes_a_stale_session_episode_and_spares_a_newer_launch',)))
    for owner, name, mutant, names in cases:
        with patch.object(owner, name, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        if not (failed and restored):
            return 'FAIL', '%s.%s neutralised: failed=%s, restored pass=%s' % (owner.__name__, name, failed, restored)
        proofs.append(name)
    return 'PASS', ('the session-end hook terminates every loop instance (none other) at once on a sign-out, shutdown, '
                    'sleep or standby event with no wait, after writing the salvage requests; each termination in its '
                    'own try; one ledger line per instance it ends (R\'s ledger for R\'s launch, the append ledger for '
                    'an unrecorded one); one pass at a time; a stale session-end episode closed, never applied to a '
                    'newer launch, by the reaper and the hook; every path the main checkout\'s from either checkout; '
                    'the first real pass of each event marked in its log; registered as an interactive-token task with '
                    'no password, only the main checkout\'s script, only through pythonw.exe, schtasks\' error kept; '
                    'a missing git falls back to the script\'s checkout and says so; a worktree refused as --root; a newer launch under '
                    'an open session episode still meets the triggers; one listing before the first termination (D-435); '
                    'neutralised, failed, restored, passed: ' + ', '.join(proofs))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
