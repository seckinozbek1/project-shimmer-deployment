"""Salvage, then stop (D-S84): the reaper's two triggers and the controller's answer.

When Claude stops while loop instances run, the reaper (a scheduled task that needs no Claude)
reads two triggers on every run: seven-day usage at or above 95 percent in the status line's
file, and no lead heartbeat for 90 minutes while a loop instance runs. Either opens a salvage
episode: a request for every running loop instance, which its controller answers by giving the
phase in hand five minutes, stopping the workload, packing and copying the evidence, terminating
the instance and writing a done file. An instance with no answer ten minutes after its request is
terminated by the reaper. When every instance is verified gone the reaper writes the salvage
report and a top entry in FOR_SECKIN.

These checks run both triggers against fake instances (the reaper's MockProvider), a fake status
file and fixture heartbeat files, and the real controller against the controller checks' fakes.
They live in SalvageChecks, mixed into ControllerChecks, and each rule is proven by neutralise,
fail, restore, pass through SALVAGE_NEUTRALIZATIONS.
"""
from datetime import timedelta
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / 'tools'), str(ROOT / 'tools' / 'loop')):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import instance_reaper  # noqa: E402
import ordinary_final_cloud as controller  # noqa: E402
from ordinary_final_run import read, write  # noqa: E402

START = '2026-10-27T10:00:00+00:00'


def termination_lines(ledger):
    rows = [json.loads(line) for line in Path(ledger).read_text(encoding='utf8').splitlines() if line.strip()]
    return [(r['instance_name'], r['reason']) for r in rows if r['event'] == 'termination']


class SalvageChecks:
    def salvage_fixture(self, folder, names, start, deadline_minutes=600):
        launch = lambda n, name: dict(event='launch', instance_id=format(n + 1, '032x'), instance_name=name,
                                      price_usd_per_hour=1.29, cap_usd=20.0, launch_requested_utc=start.isoformat(),
                                      deadline_utc=(start + timedelta(minutes=deadline_minutes)).isoformat())
        return self.two_loop_instances(folder, [launch(n, name) for n, name in enumerate(names)])

    def usage(self, percent):
        write(instance_reaper.LOOP_STATUS, dict(time_utc=START, seven_day_used_percentage=percent))

    def test_salvage_usage_trigger_requests_every_instance_then_reports(self):
        """Trigger (a): usage at 96 percent. The first pass terminates nothing and writes a request
        for each of two loop instances; one controller answers (done file, instance gone), the
        other never does and is terminated ten minutes after its request. Then both are verified
        gone, the report names the trigger, each instance, what was finished and lost, the cost,
        the packs and how each resumes, FOR_SECKIN gets a top entry, and the episode is closed."""
        start = instance_reaper.parse_time(START)
        ledger, state, provider = self.salvage_fixture('usage', ['shimmer-loop-one', 'shimmer-loop-two'], start)
        self.usage(96)
        instance_reaper.FOR_SECKIN.write_text('# For Seckin\n\nolder entry\n', encoding='utf8')
        status = instance_reaper.reap(provider, [ledger], ledger, now=start + timedelta(minutes=10))
        self.assertEqual(status['terminated'], [])
        self.assertEqual(status['salvage']['trigger'], 'usage')
        self.assertEqual(status['salvage']['states'], {'shimmer-loop-one': 'waiting', 'shimmer-loop-two': 'waiting'})
        for name in ('shimmer-loop-one', 'shimmer-loop-two'):
            self.assertEqual(instance_reaper.salvage_request(name)['trigger'], 'usage')
        # Controller one answers: its instance is gone and its done file names its pack.
        instance_reaper.write_salvage_done('shimmer-loop-one', dict(
            run_folder='/runs/one', evidence=['/runs/one/collected_evidence.tar.gz'], finished=['workload'],
            unfinished=[], terminated=True, actual_minutes=16, actual_cost=0.344, stopped_by='ordinary_workload'))
        mock = read(state)
        mock['instances'][0]['status'] = 'terminated'
        write(state, mock)
        status = instance_reaper.reap(provider, [ledger], ledger, now=start + timedelta(minutes=15))
        self.assertEqual(status['terminated'], [])
        self.assertEqual(status['salvage']['states'], {'shimmer-loop-one': 'salvaged', 'shimmer-loop-two': 'waiting'})
        self.assertIsNone(status['salvage']['report'])
        status = instance_reaper.reap(provider, [ledger], ledger, now=start + timedelta(minutes=21))
        self.assertEqual(status['terminated'], [dict(instance_name='shimmer-loop-two', reason='salvage_no_answer')])
        self.assertEqual(termination_lines(ledger), [('shimmer-loop-two', 'salvage_no_answer')])
        self.assertEqual([i['status'] for i in read(state)['instances']], ['terminated', 'terminated'])
        report = Path(status['salvage']['report'])
        self.assertEqual(report.name, 'SALVAGE_REPORT_20261027T101000Z.md')
        text = report.read_text(encoding='utf8')
        for expected in ('seven-day usage at 96.0 percent', '## shimmer-loop-one', '## shimmer-loop-two',
                         '`/runs/one/collected_evidence.tar.gz`', 'Finished: workload.', 'no answer within 600 s',
                         'Cost: 0.34 USD (16 minutes)', 'Cost: 0.45 USD (21 minutes)', 'Verified gone: yes',
                         'Resume: re-seal'):
            self.assertIn(expected, text)
        self.assertNotIn('Verified gone: no', text)
        top = instance_reaper.FOR_SECKIN.read_text(encoding='utf8').splitlines()
        self.assertEqual(top[0], '# For Seckin')
        self.assertTrue(top[2].startswith('## 2026-10-27 10:21 UTC Salvage and stop (D-S84): 2 loop instance(s) stopped'))
        self.assertIn(report.name, top[4])
        self.assertIn('older entry', top)
        # Closed: the episode and its requests moved into its own folder, so a later pass is quiet.
        self.assertFalse((instance_reaper.SALVAGE_DIR / 'episode.json').exists())
        self.assertTrue((instance_reaper.SALVAGE_DIR / '20261027T101000Z' / 'episode.json').exists())
        self.assertIsNone(instance_reaper.salvage_request('shimmer-loop-two'))
        self.assertIsNone(instance_reaper.reap(provider, [ledger], ledger, now=start + timedelta(minutes=26))['salvage'])

    def test_salvage_ends_an_instance_with_no_answer_after_ten_minutes(self):
        """D-S84 item 2: a run that does not answer within ten minutes of its request is
        terminated anyway (left alone at nine minutes), verified gone and reported."""
        start = instance_reaper.parse_time(START)
        ledger, state, provider = self.salvage_fixture('silent_controller', ['shimmer-loop-mute'], start)
        self.usage(99)
        status = instance_reaper.reap(provider, [ledger], ledger, now=start)
        self.assertEqual((status['terminated'], status['salvage']['states']), ([], {'shimmer-loop-mute': 'waiting'}))
        status = instance_reaper.reap(provider, [ledger], ledger, now=start + timedelta(minutes=9))
        self.assertEqual(status['terminated'], [])
        status = instance_reaper.reap(provider, [ledger], ledger, now=start + timedelta(minutes=10))
        self.assertEqual(status['terminated'], [dict(instance_name='shimmer-loop-mute', reason='salvage_no_answer')])
        self.assertEqual(read(state)['instances'][0]['status'], 'terminated')
        self.assertIn('no answer within 600 s of the request: terminated anyway', Path(status['salvage']['report']).read_text())

    def test_salvage_silence_trigger_fires_only_after_ninety_minutes_with_an_instance_running(self):
        """Trigger (b): usage below the stop. A heartbeat 30 minutes old fires nothing; a
        heartbeat 91 minutes old fires nothing while no loop instance runs; with one running it
        opens the episode (trigger lead_silent) and writes the instance's request."""
        now = instance_reaper.utc_now()
        ledger, state, provider = self.salvage_fixture('silence', ['shimmer-loop-alone'], now - timedelta(minutes=100))
        self.usage(50)
        beat = instance_reaper.HEARTBEATS[0]
        set_age = lambda minutes: os.utime(beat, (time.time() - minutes * 60,) * 2)
        set_age(30)
        self.assertIsNone(instance_reaper.reap(provider, [ledger], ledger, now=now)['salvage'])
        set_age(91.5)
        idle = self.root / 'silence' / 'idle.json'
        write(idle, dict(instances=[]))
        self.assertIsNone(instance_reaper.reap(instance_reaper.MockProvider(idle), [ledger], ledger, now=now)['salvage'])
        status = instance_reaper.reap(provider, [ledger], ledger, now=now)
        self.assertEqual(status['salvage']['trigger'], 'lead_silent')
        self.assertEqual(status['terminated'], [])
        request = instance_reaper.salvage_request('shimmer-loop-alone')
        self.assertEqual(request['trigger'], 'lead_silent')
        self.assertEqual(read(instance_reaper.SALVAGE_DIR / 'episode.json')['trigger']['silent_minutes'], 91)

    def test_the_controller_answers_a_salvage_request_with_its_pack_and_a_verified_stop(self):
        """D-S84 item 2 on the real controller: a request that arrives while the workload runs
        gives it 300 s, then the controller stops the workload, packs, hashes and copies the
        evidence to its run folder, terminates and verifies the instance, closes the ledger,
        and answers with a done file naming the pack, the unfinished workload and the stop."""
        def arriving(name):
            if not (self.base / 'ordinary_workload_status.json').exists():  # the workload is in hand
                return None
            path = instance_reaper.request_path(name)
            if not path.exists():
                instance_reaper._write_json(path, dict(episode='fixture', trigger='usage', requested_utc=START))
            return instance_reaper.salvage_request(name)
        with patch.object(controller, 'salvage_requested', arriving):
            transport, console, failure = self.execute(polls={'ordinary_workload': ['RUNNING'] * 60})
        self.assertIsNotNone(failure)
        self.assertEqual(failure['message'], 'Salvage requested: the phase in hand was given 300 s')
        self.assertEqual(transport.started.count('ordinary_workload'), 1)
        self.assertIn('stop_workload', transport.started)
        self.assertIn('pack_evidence', transport.started)
        seen = read(self.base / 'salvage_request_seen.json')
        self.assertEqual(seen['phase'], 'ordinary_workload')
        timing = read(self.base / 'ordinary_workload_status.json')
        self.assertEqual(timing['remote_work'], 'stopped for salvage (D-S84)')
        self.assertGreaterEqual(timing['last_poll_epoch'] - seen['epoch'], 300)
        self.assert_torn_down()
        done = json.loads(instance_reaper.request_path('shimmer-loop-fixture', 'done').read_text(encoding='utf8'))
        self.assertTrue(done['terminated'])
        self.assertEqual(done['unfinished'], ['workload'])
        self.assertEqual(done['stopped_by'], 'ordinary_workload')
        self.assertEqual(done['evidence'], [(self.base / 'collected_evidence.tar.gz').resolve().as_posix()])
        self.assertIsNotNone(done['actual_cost'])

    def test_no_new_phase_starts_once_a_salvage_request_is_seen(self):
        """A request already there before the workload: no new phase starts (the workload is
        never launched), the stop and collection phases still run and the instance is ended."""
        instance_reaper._write_json(instance_reaper.request_path('shimmer-loop-fixture'), dict(episode='fixture', trigger='lead_silent',
                                                                           requested_utc=START))
        transport, console, failure = self.execute()
        self.assertEqual(failure['message'], 'Salvage requested: no new phase is started')
        self.assertEqual(transport.started.count('ordinary_workload'), 0)
        self.assertIn('pack_evidence', transport.started)
        self.assert_torn_down()
        done = json.loads(instance_reaper.request_path('shimmer-loop-fixture', 'done').read_text(encoding='utf8'))
        self.assertTrue(done['terminated'])


SALVAGE_NEUTRALIZATIONS = [
    # Trigger (a) never fires.
    ('test_salvage_usage_trigger_requests_every_instance_then_reports', instance_reaper, 'usage_stop',
     lambda usage: False),
    # Trigger (b) never fires.
    ('test_salvage_silence_trigger_fires_only_after_ninety_minutes_with_an_instance_running', instance_reaper,
     'lead_silent', lambda now, beat: False),
    # Trigger (b) fires with no instance running or on a fresh heartbeat.
    ('test_salvage_silence_trigger_fires_only_after_ninety_minutes_with_an_instance_running', instance_reaper,
     'lead_silent', lambda now, beat: True),
    # A run that never answers is waited on for ever.
    ('test_salvage_ends_an_instance_with_no_answer_after_ten_minutes', instance_reaper, 'salvage_overdue',
     lambda now, requested_utc: False),
    # The controller never stops the phase in hand for a request.
    ('test_the_controller_answers_a_salvage_request_with_its_pack_and_a_verified_stop', controller, 'salvage_stop',
     lambda label, name, seen, now, starting: False),
    # The controller's answer names no pack.
    ('test_the_controller_answers_a_salvage_request_with_its_pack_and_a_verified_stop', controller, 'salvage_record',
     lambda *args: dict(terminated=True)),
    # A request seen before a phase does not refuse it.
    ('test_no_new_phase_starts_once_a_salvage_request_is_seen', controller, 'salvage_stop',
     lambda label, name, seen, now, starting: False),
]
