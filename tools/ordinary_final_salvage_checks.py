"""Salvage, then stop (D-S84): the reaper's two triggers and the controller's answer.

When Claude stops while loop instances run, the reaper (a scheduled task that needs no Claude)
reads two triggers on every run: seven-day usage at or above 100 percent (the standing value since 21 November 2026 13:00 +0300, D-915;
before it the dated history: 98 until the reset of 18 November 2026, D-529, then 95, then 98 from 20 November 2026 19:37 +0300, D-857)
in the status line's file, and no lead heartbeat for 90 minutes while a loop instance runs (D-915: an off-by-default
switch in config/reaper_silence.json leaves a chain-launched instance out of the silence trigger). Either opens a salvage
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
from datetime import datetime, timedelta, timezone
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
# D-583: the freshness bound the decision recorded from the measured write gaps of the status line.
DECLARED_FRESH_SECONDS = 300


def termination_lines(ledger):
    rows = [json.loads(line) for line in Path(ledger).read_text(encoding='utf8').splitlines() if line.strip()]
    return [(r['instance_name'], r['reason']) for r in rows if r['event'] == 'termination']


class SalvageChecks:
    def salvage_fixture(self, folder, names, start, deadline_minutes=600):
        launch = lambda n, name: dict(event='launch', instance_id=format(n + 1, '032x'), instance_name=name,
                                      price_usd_per_hour=1.29, cap_usd=20.0, launch_requested_utc=start.isoformat(),
                                      deadline_utc=(start + timedelta(minutes=deadline_minutes)).isoformat())
        return self.two_loop_instances(folder, [launch(n, name) for n, name in enumerate(names)])

    def usage(self, percent, at=None):
        """The status line's reading, written at `at` (an epoch, a datetime or START)."""
        if isinstance(at, (int, float)):
            at = datetime.fromtimestamp(at, timezone.utc)
        stamp = START if at is None else at.isoformat()
        write(instance_reaper.LOOP_STATUS, dict(time_utc=stamp, seven_day_used_percentage=percent))

    def test_salvage_usage_stop_acts_only_on_a_live_reading(self):
        """D-583: the reading is taken again at the moment of decision. A fresh 100 stops (the standing
        value, D-915), a stale 100 does not stop and is reported as usage unknown with its age, a fresh 99
        does not stop, and an unreadable figure stops nothing. The silence trigger is untouched."""
        since = instance_reaper.USAGE_STOP_SINCE['until_epoch']
        fresh = DECLARED_FRESH_SECONDS   # the decision's measured bound, held equal to the reaper's constant
        self.assertEqual(instance_reaper.USAGE_FRESH_SECONDS, fresh)
        now = datetime.fromtimestamp(since + 7200, timezone.utc)
        beat_file = Path(instance_reaper.LOOP_STATUS).with_name('beat.txt')   # a heartbeat at `now`: silence stays quiet
        beat_file.write_text('beat', encoding='utf8')
        os.utime(beat_file, (now.timestamp(), now.timestamp()))
        beat = [beat_file]
        self.usage(100, at=now - timedelta(seconds=30))
        trigger = instance_reaper.salvage_trigger(now, ['x'], heartbeats=beat)
        self.assertEqual((trigger['trigger'], trigger['seven_day_used_percentage'], trigger['reading_age_seconds']),
                         ('usage', 100.0, 30.0))
        self.usage(100, at=now - timedelta(seconds=fresh + 60))
        reading = instance_reaper.usage_reading(None, now)
        self.assertEqual((reading['state'], reading['value'], reading['age_seconds']), ('stale', 100.0, fresh + 60.0))
        self.assertEqual(reading['note'], 'usage unknown, stale by %d s' % (fresh + 60))
        self.assertIsNone(instance_reaper.salvage_trigger(now, ['x'], heartbeats=beat))
        self.usage(99, at=now - timedelta(seconds=10))
        self.assertIsNone(instance_reaper.salvage_trigger(now, ['x'], heartbeats=beat))
        write(instance_reaper.LOOP_STATUS, dict(time_utc=(now - timedelta(seconds=10)).isoformat()))
        self.assertEqual(instance_reaper.usage_reading(None, now)['note'], 'usage unknown, unreadable')
        self.assertIsNone(instance_reaper.salvage_trigger(now, ['x'], heartbeats=beat))
        # One second past the bound is stale; at the bound it is fresh.
        self.usage(100, at=now - timedelta(seconds=fresh))
        self.assertEqual(instance_reaper.usage_reading(None, now)['state'], 'fresh')
        self.usage(100, at=now - timedelta(seconds=fresh + 1))
        self.assertEqual(instance_reaper.usage_reading(None, now)['state'], 'stale')
        # A reading written a moment after the clock read (small negative age) is fresh; far ahead is stale.
        self.usage(100, at=now + timedelta(seconds=1))
        self.assertEqual(instance_reaper.usage_reading(None, now)['state'], 'fresh')
        self.usage(100, at=now + timedelta(seconds=instance_reaper.USAGE_CLOCK_SKEW_SECONDS + 1))
        self.assertEqual(instance_reaper.usage_reading(None, now)['state'], 'stale')

    def test_salvage_usage_trigger_requests_every_instance_then_reports(self):
        """Trigger (a): usage at 98 percent (the D-529 threshold before the reset). The first pass terminates nothing and writes a request
        for each of two loop instances; one controller answers (done file, instance gone), the
        other never does and is terminated ten minutes after its request. Then both are verified
        gone, the report names the trigger, each instance, what was finished and lost, the cost,
        the packs and how each resumes, FOR_SECKIN gets a top entry, and the episode is closed."""
        start = instance_reaper.parse_time(START)
        ledger, state, provider = self.salvage_fixture('usage', ['shimmer-loop-one', 'shimmer-loop-two'], start)
        self.usage(98, at=start + timedelta(minutes=10))   # a live reading at the pass's own moment (D-583)
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
        for expected in ('seven-day usage at 98.0 percent', 'stop at 98 (in force until epoch 1794988800, D-529','## shimmer-loop-one', '## shimmer-loop-two',
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

    def test_salvage_usage_threshold_follows_its_dated_history(self):
        """D-529, D-857 and D-915: one function, usage_stop_percent(now), is every reader's threshold.
        Before the reset instant (18 November 2026, 11:00 +03:00, epoch 1794988800) 97.9 does not trigger
        and 98 does; from that instant 95 triggers and 94.9 does not; from 20 November 2026 19:37 +0300
        (epoch 1795192620, G-20261120-1937) the value is 98: 97.9 does not trigger and 98 does, at the
        boundary instant and until the next; from 21 November 2026 13:00 +0300 (epoch 1795255200,
        G-20261121-1300 / D-915) the standing value is 100: 99.9 does not trigger and 100 does, at the
        boundary instant and after it; one second before it 98 still holds. The status and the trigger
        name the threshold in force and why."""
        d529, d857, d915 = (entry['until_epoch'] for entry in instance_reaper.USAGE_STOP_HISTORY)
        self.assertEqual((d529, d857, d915), (1794988800, 1795192620, 1795255200))
        self.assertEqual(d915, int(datetime(2026, 11, 21, 13, 0, tzinfo=timezone(timedelta(hours=3))).timestamp()))
        self.assertEqual(instance_reaper.USAGE_STOP_SINCE['until_epoch'], d915)
        self.assertEqual(instance_reaper.USAGE_STOP_PERCENT, 100)
        utc = lambda epoch: datetime.fromtimestamp(epoch, timezone.utc)
        fires = lambda percent, epoch: (self.usage(percent, at=epoch), (instance_reaper.salvage_trigger(utc(epoch), ['x']) or {}).get('trigger') == 'usage')[1]
        # D-529: 98 before the reset.
        self.assertFalse(fires(97, d529 - 3600))
        self.assertTrue(fires(98, d529 - 3600))
        self.assertFalse(fires(97.9, d529 - 1))
        self.assertEqual(instance_reaper.usage_stop_percent(utc(d529 - 1)), 98)
        # 95 from the reset instant until the D-857 instant.
        self.assertEqual(instance_reaper.usage_stop_percent(utc(d529)), 95)
        self.assertTrue(fires(95, d529))
        self.assertTrue(fires(95, d529 + 86400))
        self.assertFalse(fires(94.9, d529 + 1))
        self.assertTrue(fires(97.9, d857 - 1))
        self.assertEqual(instance_reaper.usage_stop_percent(utc(d857 - 1)), 95)
        # D-857: the boundary instant is already 98, until the D-915 instant.
        self.assertEqual(instance_reaper.usage_stop_percent(utc(d857)), 98)
        self.assertEqual(instance_reaper.usage_stop_percent(d857), 98)   # an epoch is read too
        self.assertFalse(fires(97.9, d857))
        self.assertTrue(fires(98, d857))
        self.assertFalse(fires(97.9, d857 + 3600))
        self.assertTrue(fires(98, d915 - 1))
        self.assertEqual(instance_reaper.usage_stop_percent(utc(d915 - 1)), 98)
        # D-915: the boundary instant is already the standing 100, and it stays.
        self.assertEqual(instance_reaper.usage_stop_percent(utc(d915)), 100)
        self.assertEqual(instance_reaper.usage_stop_percent(d915), 100)
        self.assertFalse(fires(99.9, d915))
        self.assertFalse(fires(98, d915))
        self.assertTrue(fires(100, d915))
        self.assertFalse(fires(99.9, d915 + 86400))
        self.assertTrue(fires(100, d915 + 7 * 86400))
        self.usage(100.5, at=d915 + 5)
        trigger = instance_reaper.salvage_trigger(utc(d915 + 5), ['x'])
        standing = '100 (the standing value since epoch 1795255200, G-20261121-1300 / D-915)'
        self.assertEqual((trigger['stop_percent'], trigger['stop_basis']), (100, standing))
        self.assertIn('stop at ' + standing, instance_reaper.trigger_words(trigger))
        self.usage(10)
        self.assertEqual(instance_reaper.usage_stop_basis(utc(d915 - 3600)),
                         '98 (in force until epoch 1795255200, 98 until 21 November 2026 13:00 +0300, '
                         'G-20261121-1300 / D-915; 100 is the standing value)')
        self.assertEqual(instance_reaper.usage_stop_basis(utc(d857 - 3600)),
                         '95 (in force until epoch 1795192620, 95 until 20 November 2026 19:37 +0300, '
                         'G-20261120-1937 / D-857; 100 is the standing value)')
        self.assertEqual(instance_reaper.usage_stop_basis(utc(d529 - 3600)),
                         '98 (in force until epoch 1794988800, D-529, Seckin 14:16, 12 November 2026; 100 is the standing value)')

    def test_salvage_usage_stop_reads_only_the_overall_weekly_figure(self):
        """D-534: a high per-model figure in the status file beside a low seven_day_used_percentage
        triggers nothing; only the overall weekly figure is read."""
        write(instance_reaper.LOOP_STATUS, dict(time_utc=START, seven_day_used_percentage=10,
                                                seven_day_model_used_percentage=99, seven_day_opus_used_percentage=100))
        self.assertEqual(instance_reaper.usage_percent(), 10.0)
        self.assertIsNone(instance_reaper.salvage_trigger(instance_reaper.parse_time(START), ['x'],
                                                          heartbeats=[instance_reaper.LOOP_STATUS]))

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

    def test_loop_heartbeat_file_is_a_lead_heartbeat(self):
        """G-20261120-1300: the lead's LOOP_HEARTBEAT.txt is one of the reaper's heartbeat files, so a lead that beats
        it inside one long turn is not read as silent: with the three record files 100 minutes old and only
        LOOP_HEARTBEAT.txt fresh, the silence trigger stays quiet; with it old too, it fires (the threshold unchanged)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location('instance_reaper_default', instance_reaper.__file__)
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)   # the module's own default list, not the fixture's patched one
        self.assertIn('LOOP_HEARTBEAT.txt', [Path(p).name for p in fresh.HEARTBEATS])
        self.assertEqual(instance_reaper.SILENCE_MINUTES, 90)
        now = instance_reaper.utc_now()
        self.usage(50)
        folder = self.root / 'beatfile'
        folder.mkdir(parents=True, exist_ok=True)
        files = [folder / n for n in ('continue_hook_state.json', 'LOOP_STATE.md', 'FOR_SECKIN.md', 'LOOP_HEARTBEAT.txt')]
        for f in files:
            f.write_text('x', encoding='utf8')
            os.utime(f, (time.time() - 100 * 60,) * 2)
        os.utime(files[3], (time.time() - 5 * 60,) * 2)
        self.assertIsNone(instance_reaper.salvage_trigger(now, ['x'], heartbeats=files))
        os.utime(files[3], (time.time() - 100 * 60,) * 2)
        self.assertEqual((instance_reaper.salvage_trigger(now, ['x'], heartbeats=files) or {}).get('trigger'), 'lead_silent')

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

    def silence_case(self, folder, names, minutes_old=100, deadline_minutes=600):
        """D-915: a mock provider with one loop instance per name ('chain' in the name: made by the launch chain,
        else by hand), each with a purpose, a heartbeat 91.5 minutes old, usage 50, and a chain trace holding a
        launch_started line for each chain-launched purpose 80 s before its launch request."""
        now = instance_reaper.utc_now()
        start = now - timedelta(minutes=minutes_old)
        launches, trace = [], []
        for n, name in enumerate(names):
            purpose = 'dev-fix-%d' % n
            launches.append(dict(event='launch', instance_id=format(n + 1, '032x'), instance_name=name, purpose=purpose,
                                 price_usd_per_hour=1.29, cap_usd=20.0, launch_requested_utc=start.isoformat(),
                                 deadline_utc=(start + timedelta(minutes=deadline_minutes)).isoformat()))
            if 'chain' in name:
                trace.append(dict(time=(start - timedelta(seconds=80)).isoformat(), mechanism='launch_chain',
                                  result='launch_started', folder='FIXTURE', step='D%d' % n, kind='ledger', purpose=purpose))
        ledger, state, provider = self.two_loop_instances(folder, launches)
        trace_file = self.root / folder / 'mechanism_trace.jsonl'
        trace_file.write_text(''.join(json.dumps(x) + '\n' for x in trace), encoding='utf8')
        self.usage(50, at=now)
        os.utime(instance_reaper.HEARTBEATS[0], (time.time() - 91.5 * 60,) * 2)
        return now, ledger, provider, trace_file

    def silence_reap(self, folder, names, switch, **kwargs):
        config = self.root / folder / 'reaper_silence.json'
        config.parent.mkdir(parents=True, exist_ok=True)
        if switch is not None:
            config.write_text(json.dumps(dict(exempt_chain_launches=switch)), encoding='utf8')
        now, ledger, provider, trace_file = self.silence_case(folder, names, **kwargs)
        with patch.object(instance_reaper, 'SILENCE_CONFIG', config), patch.object(instance_reaper, 'CHAIN_TRACE', trace_file), \
                patch.object(instance_reaper, 'SALVAGE_DIR', self.root / folder / 'salvage'):
            status = instance_reaper.reap(provider, [ledger], ledger, now=now)
            requested = {n: (instance_reaper.salvage_request(n) or {}).get('trigger') for n in names}
        return status, requested

    def test_silence_switch_off_salvages_a_chain_launched_instance_as_before(self):
        """D-915: with exempt_chain_launches false, or the file missing or unreadable, no heartbeat for 91.5
        minutes salvages a chain-launched instance (trigger lead_silent) exactly as before; the committed config
        holds false."""
        committed = json.loads((ROOT / 'config' / 'reaper_silence.json').read_text(encoding='utf8'))
        self.assertIs(committed['exempt_chain_launches'], False)
        for number, switch in enumerate((False, None, 'unreadable', 'yes')):
            folder = 'silence_off_%d' % number
            if switch == 'unreadable':
                (self.root / folder).mkdir(parents=True, exist_ok=True)
                (self.root / folder / 'reaper_silence.json').write_text('{not json', encoding='utf8')
                switch = None
            elif switch == 'yes':
                switch = 'yes'   # only a literal true counts
            status, requested = self.silence_reap(folder, ['shimmer-loop-chain'], switch)
            self.assertEqual(status['salvage']['trigger'], 'lead_silent')
            self.assertEqual(requested, {'shimmer-loop-chain': 'lead_silent'})
            self.assertEqual(status['terminated'], [])

    def test_silence_switch_on_leaves_a_chain_launched_instance_out_of_the_silence_trigger(self):
        """D-915: with the switch true a chain-launched instance is not salvaged for silence (no episode, no
        request), but is still ended at its deadline; the usage trigger still takes it; and when a hand-launched
        instance runs beside it, the silence episode takes the hand-launched one only."""
        status, requested = self.silence_reap('silence_on_alone', ['shimmer-loop-chain'], True)
        self.assertIsNone(status['salvage'])
        self.assertEqual(requested, {'shimmer-loop-chain': None})
        self.assertEqual(status['terminated'], [])
        # Its own deadline termination stays.
        status, requested = self.silence_reap('silence_on_deadline', ['shimmer-loop-chain'], True, deadline_minutes=60)
        self.assertEqual(status['terminated'], [dict(instance_name='shimmer-loop-chain', reason='deadline_passed')])
        self.assertIsNone(status['salvage'])
        # The usage trigger stays.
        config = self.root / 'silence_on_usage' / 'reaper_silence.json'
        (self.root / 'silence_on_usage').mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps(dict(exempt_chain_launches=True)), encoding='utf8')
        now, ledger, provider, trace_file = self.silence_case('silence_on_usage', ['shimmer-loop-chain'])
        self.usage(100, at=now)
        with patch.object(instance_reaper, 'SILENCE_CONFIG', config), patch.object(instance_reaper, 'CHAIN_TRACE', trace_file), \
                patch.object(instance_reaper, 'SALVAGE_DIR', self.root / 'silence_on_usage' / 'salvage'):
            status = instance_reaper.reap(provider, [ledger], ledger, now=now)
            self.assertEqual(status['salvage']['trigger'], 'usage')
            self.assertEqual(instance_reaper.salvage_request('shimmer-loop-chain')['trigger'], 'usage')
        # Beside a hand-launched instance: only that one is taken by the silence episode.
        status, requested = self.silence_reap('silence_on_mixed', ['shimmer-loop-chain', 'shimmer-loop-hand'], True)
        self.assertEqual(status['salvage']['trigger'], 'lead_silent')
        self.assertEqual(requested, {'shimmer-loop-chain': None, 'shimmer-loop-hand': 'lead_silent'})
        self.assertEqual(sorted(status['salvage']['states']), ['shimmer-loop-hand'])

    def test_silence_switch_on_still_salvages_a_hand_launched_instance(self):
        """D-915: with the switch true, a hand-launched instance (no chain start line for its purpose) is
        salvaged for silence as before; a chain start line made long before its launch does not count."""
        status, requested = self.silence_reap('silence_hand', ['shimmer-loop-hand'], True)
        self.assertEqual(status['salvage']['trigger'], 'lead_silent')
        self.assertEqual(requested, {'shimmer-loop-hand': 'lead_silent'})
        started = [('dev-fix-0', datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc))]
        rec = dict(purpose='dev-fix-0', launch_requested_utc='2026-11-21T08:01:20+00:00')
        self.assertTrue(instance_reaper.chain_launched(rec, started))
        self.assertFalse(instance_reaper.chain_launched(dict(rec, launch_requested_utc='2026-11-21T09:00:00+00:00'), started))
        self.assertFalse(instance_reaper.chain_launched(dict(rec, launch_requested_utc='2026-11-21T07:00:00+00:00'), started))
        self.assertFalse(instance_reaper.chain_launched(dict(rec, purpose='dev-fix-1'), started))

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


_REAL_USAGE_READING = instance_reaper.usage_reading
SALVAGE_NEUTRALIZATIONS = [
    # D-583: any reading counts as live, however old (no freshness bound).
    ('test_salvage_usage_stop_acts_only_on_a_live_reading', instance_reaper, 'USAGE_FRESH_SECONDS', 10 ** 9),
    # D-583: the trigger acts on the figure whatever its state (a stale 98 stops).
    ('test_salvage_usage_stop_acts_only_on_a_live_reading', instance_reaper, 'usage_reading',
     lambda path=None, now=None: dict(_REAL_USAGE_READING(path, now), state='fresh')),
    # A per-model figure is read as the weekly one (D-534).
    ('test_salvage_usage_stop_reads_only_the_overall_weekly_figure', instance_reaper, 'usage_percent',
     lambda path=None: max(float(v) for k, v in json.loads(Path(instance_reaper.LOOP_STATUS).read_text(encoding='utf8')).items()
                           if k.endswith('used_percentage'))),
    # The history is ignored: 98 at every instant, so 95 never held between the reset and D-857.
    ('test_salvage_usage_threshold_follows_its_dated_history', instance_reaper, 'usage_stop_percent',
     lambda now=None: 98),
    # The D-857 and D-915 raises never happened: 95 at every instant, so 97.9 would trigger after them.
    ('test_salvage_usage_threshold_follows_its_dated_history', instance_reaper, 'usage_stop_percent',
     lambda now=None: 95),
    # The old reader: 98 before the reset, 95 for ever after it (D-857 not taken up).
    ('test_salvage_usage_threshold_follows_its_dated_history', instance_reaper, 'usage_stop_percent',
     lambda now=None: 98 if instance_reaper._epoch(now) < instance_reaper.USAGE_STOP_HISTORY[0]['until_epoch'] else 95),
    # Each boundary instant is read as still inside the entry before it.
    ('test_salvage_usage_threshold_follows_its_dated_history', instance_reaper, 'usage_stop_percent',
     lambda now=None: next((e['percent'] for e in instance_reaper.USAGE_STOP_HISTORY
                            if instance_reaper._epoch(now) <= e['until_epoch']), instance_reaper.USAGE_STOP_PERCENT)),
    # The standing constant left at the old 95, or at the D-857 98.
    ('test_salvage_usage_threshold_follows_its_dated_history', instance_reaper, 'USAGE_STOP_PERCENT', 95),
    ('test_salvage_usage_threshold_follows_its_dated_history', instance_reaper, 'USAGE_STOP_PERCENT', 98),
    # The D-915 raise never taken up: the first two history entries, then 98 for ever.
    ('test_salvage_usage_threshold_follows_its_dated_history', instance_reaper, 'usage_stop_percent',
     lambda now=None: next((e['percent'] for e in instance_reaper.USAGE_STOP_HISTORY[:2]
                            if instance_reaper._epoch(now) < e['until_epoch']), 98)),
    # The trigger reads the standing constant directly, not the one function.
    ('test_salvage_usage_threshold_follows_its_dated_history', instance_reaper, 'usage_stop',
     lambda usage, now=None: usage is not None and usage >= instance_reaper.USAGE_STOP_PERCENT),
    # Trigger (a) never fires.
    ('test_salvage_usage_trigger_requests_every_instance_then_reports', instance_reaper, 'usage_stop',
     lambda usage, now=None: False),
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
    # D-915: the switch reads true whatever the file says, so a chain-launched instance is never salvaged for silence.
    ('test_silence_switch_off_salvages_a_chain_launched_instance_as_before', instance_reaper, 'exempt_chain_launches',
     lambda: True),
    # D-915: the switch reads false whatever the file says, so the exemption never applies.
    ('test_silence_switch_on_leaves_a_chain_launched_instance_out_of_the_silence_trigger', instance_reaper,
     'exempt_chain_launches', lambda: False),
    # D-915: an exempt instance is dropped from the reaper altogether, so its deadline is never enforced.
    ('test_silence_switch_on_leaves_a_chain_launched_instance_out_of_the_silence_trigger', instance_reaper,
     'loop_instances', lambda listed: [i for i in listed if 'chain' not in i['name']]),
    # D-915: every instance reads as chain-launched, so a hand-launched one is exempt too.
    ('test_silence_switch_on_still_salvages_a_hand_launched_instance', instance_reaper, 'chain_launched',
     lambda rec, started: True),
]
