"""Proofs for the live run view (Annex D D-S66), replayed from saved observations, no network.

The saved observations in `tools/ordinary_final_live_fixture.json` are what the reader itself
read, read-only, from three exposed development runs on 9 November 2026 (`--save-observations`):
P3_TRAIN_B answering its questions (40 calls kept, median 18.39 s a call, slowest 22.85 s),
T2E_TRAIN_F training (update 89 of 710 at 15.33 s an update) and AUD_TRAIN5 training again after
its questions. Each proof is run, then run with one part of the reader neutralised (it must
FAIL), then run again restored (it must pass): `check()` does all three, with sockets denied.

    py -3.12 -X utf8 tools/ordinary_final_live_checks.py
"""
import ast
import contextlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools')]
import ordinary_final_live as live
import cloud_run_common

FIXTURE = json.loads((ROOT / 'tools' / 'ordinary_final_live_fixture.json').read_text(encoding='utf8'))
DETAIL = live.observation_key('detail')
COUNTS = live.observation_key('counts')
P3_LAST = 1794205566.154148      # the 40th saved call of P3_TRAIN_B finished at this epoch
P3_ALLOWANCE = 55.18             # 3 x its median 18.39 s; its slowest call took 22.85 s
T2E_WRITTEN = 1794212308.1663232  # T2E_TRAIN_F's progress file was last written at this epoch
REPLY_MARKER = 'REPLY-TEXT-THAT-MUST-NEVER-LEAVE-THE-INSTANCE'


def make_bundle(directory, name, files, extra=None):
    bundle = Path(directory) / name
    bundle.mkdir(parents=True)
    for file, payload in dict(files, **(extra or {})).items():
        (bundle / file).write_text(json.dumps(payload), encoding='utf8')
    return bundle


def saved(name):
    run = FIXTURE['runs'][name]
    return dict(run['observations']), dict(run['bundle_files'])


def detail_answer(name):
    return json.loads(saved(name)[0][DETAIL])


def with_items(name, items, **fields):
    """The saved observations of run `name` with its detail answer's items replaced."""
    observations, files = saved(name)
    answer = detail_answer(name)
    answer['items'] = items
    answer.update(fields)
    observations[DETAIL] = json.dumps(answer)
    return observations, files


def item(n, epoch, **fields):
    row = dict(folder='evidence/run/audit/model_replies', sequence=n, call_id='c%04d' % n, agent='VERIFIER',
               doc_id='doc-%d' % (n % 3), phase='5', backend_ok=True, error_category='', finished_epoch=epoch,
               over_context=False, dead_end=False, outcome='accepted_to_bus', outcome_source='run_task')
    row.update(fields)
    return row


class LiveViewProofs(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def snapshot(self, name, observations, files, now, extra=None):
        bundle = make_bundle(self.directory.name, name, files, extra)
        return live.snapshot_for(bundle, observations=observations, now=now), bundle

    # --- the saved runs, replayed ------------------------------------------------------------

    def test_replay_reproduces_each_saved_runs_reading(self):
        observations, files = saved('P3_TRAIN_B')
        snap, _ = self.snapshot('P3_TRAIN_B', observations, files, P3_LAST + 10)
        self.assertEqual(snap['counts'], dict(passed=40, refused=0, out_of_memory=0, crashed=0))
        seconds = [r['seconds'] for r in snap['rows']]
        self.assertIsNone(seconds[0])
        self.assertEqual([round(s, 2) for s in seconds[1:4]], [16.68, 19.99, 19.98])
        self.assertEqual(snap['expected_records'], 704)
        self.assertEqual(len(snap['documents']), 20)
        self.assertIn('reply records measured', snap['progress'])
        self.assertIn('40 of 704 calls finished', live.summary_line(snap))
        self.assertIn('40 of the passed returned with no outcome recorded', live.summary_line(snap))
        observations, files = saved('T2E_TRAIN_F')
        snap, _ = self.snapshot('T2E_TRAIN_F', observations, files, T2E_WRITTEN + 5)
        self.assertEqual(sum(snap['counts'].values()), 0)
        self.assertTrue(snap['stall']['judged'])
        self.assertIn('15.3 s', snap['stall']['basis'])
        self.assertIn('training updates', snap['progress'])
        observations, files = saved('AUD_TRAIN5')
        snap, _ = self.snapshot('AUD_TRAIN5', observations, files, None)
        self.assertEqual(snap['counts']['passed'], 40)

    # --- each item's outcome --------------------------------------------------------------

    def test_each_failure_class_is_read_from_its_record(self):
        cases = [
            (dict(backend_ok=False, error_category='OutOfMemoryError'), ('out_of_memory', 'out of memory')),
            (dict(backend_ok=False, error_category='CUDA out of memory. Tried to allocate 2.00 GiB'), ('out_of_memory', 'out of memory')),
            (dict(backend_ok=False, error_category='RuntimeError'), ('crashed', 'RuntimeError')),
            (dict(outcome='backend_failure'), ('crashed', 'backend_failure')),
            (dict(over_context=True), ('refused', 'prompt_over_context')),
            (dict(dead_end=True), ('refused', 'decoding_dead_end')),
            (dict(), ('passed', '')),
        ]
        for fields, expected in cases:
            self.assertEqual(live.classify(item(1, 1.0, **fields)), expected, fields)
        self.assertEqual(live.classify(dict(backend_ok=False, oom=True, finished_epoch=1.0)), ('out_of_memory', 'out of memory'))

    def test_a_refusal_carries_its_reason(self):
        for outcome in ('refused', 'contract_violation', 'retry_skipped_deterministic'):
            self.assertEqual(live.classify(item(1, 1.0, outcome=outcome)), ('refused', outcome))
        observations, files = with_items('P3_TRAIN_B', [item(n, 100.0 + 20 * n, outcome='contract_violation' if n == 2 else 'accepted_to_bus')
                                                        for n in range(1, 5)])
        snap, _ = self.snapshot('P3_TRAIN_B', observations, files, 200.0)
        self.assertEqual(snap['reasons'], {'refused: contract_violation': 1})
        self.assertIn('(contract_violation)', '\n'.join(live.item_lines(snap)))

    # --- the alerts ---------------------------------------------------------------------

    def test_the_same_failure_repeating_is_an_alert(self):
        rows = [item(n, 100.0 + 20 * n) for n in range(1, 6)] + [item(n, 100.0 + 20 * n, outcome='contract_violation')
                                                                    for n in range(6, 9)]
        observations, files = with_items('P3_TRAIN_B', rows)
        snap, _ = self.snapshot('P3_TRAIN_B', observations, files, 270.0)
        found = live.alerts(snap, None)
        self.assertIn('ALERT P3_TRAIN_B repeated: the last 3 finished calls were refused (contract_violation)', found)
        mixed = rows[:-1] + [item(8, 260.0, outcome='refused')]
        observations, files = with_items('P3_TRAIN_B', mixed)
        snap, _ = self.snapshot('P3_TRAIN_B2', observations, files, 270.0)
        self.assertFalse([a for a in live.alerts(snap, None) if 'repeated' in a])

    def test_out_of_memory_and_a_crash_are_alerts(self):
        rows = [item(n, 100.0 + 20 * n) for n in range(1, 5)] + [item(5, 200.0, backend_ok=False, error_category='OutOfMemoryError')]
        observations, files = with_items('P3_TRAIN_B', rows)
        snap, _ = self.snapshot('P3_TRAIN_B', observations, files, 205.0)
        self.assertTrue(any(a.startswith('ALERT P3_TRAIN_B out_of_memory: 1 calls') for a in live.alerts(snap, None)))
        observations, files = with_items('P3_TRAIN_B', rows[:4], stderr_markers=dict(traceback=1, out_of_memory=0))
        snap, _ = self.snapshot('P3_TRAIN_C', observations, files, 185.0)
        self.assertTrue(any('crash: 0 calls crashed, 1 tracebacks' in a for a in live.alerts(snap, None)))
        observations, files = with_items('P3_TRAIN_B', rows[:4])
        files['ordinary_workload_status.json'] = dict(files['ordinary_workload_status.json'], exit_code=1, remote_work='exited')
        snap, _ = self.snapshot('P3_TRAIN_D', observations, files, 185.0)
        self.assertTrue(any('workload exit 1' in a for a in live.alerts(snap, None)))
        observations, files = with_items('P3_TRAIN_B', rows[:4])
        snap, _ = self.snapshot('P3_TRAIN_E', observations, files, 185.0)
        self.assertEqual(live.alerts(snap, None), [])

    def test_a_refusal_rate_above_the_development_figure_is_an_alert(self):
        rows = [item(n, 100.0 + 20 * n, outcome='refused' if n % 4 == 0 else 'accepted_to_bus') for n in range(1, 13)]
        observations, files = with_items('P3_TRAIN_B', rows)
        snap, _ = self.snapshot('P3_TRAIN_B', observations, files, 345.0)
        found = live.alerts(snap, live.development_rate('9/84'))
        self.assertIn('ALERT P3_TRAIN_B refusal_rate: 3 of 12 refused (25.0%), above the development figure 10.7%', found)
        self.assertFalse([a for a in live.alerts(snap, live.development_rate('4/12')) if 'refusal_rate' in a])
        with self.assertRaises(ValueError):
            live.development_rate('nine')

    def test_a_stall_is_judged_by_the_runs_own_measured_time_per_call(self):
        observations, files = saved('P3_TRAIN_B')
        snap, _ = self.snapshot('P3_TRAIN_B', observations, files, P3_LAST + 30)
        self.assertTrue(snap['stall']['judged'])
        self.assertFalse(snap['stall']['stalled'])
        self.assertAlmostEqual(snap['stall']['allowance_seconds'], P3_ALLOWANCE, places=1)
        snap, _ = self.snapshot('P3_TRAIN_B2', observations, files, P3_LAST + 400)
        self.assertTrue(snap['stall']['stalled'])
        self.assertTrue(any(a.startswith('ALERT P3_TRAIN_B2 stall: nothing finished for 400 s') for a in live.alerts(snap, None)))
        observations, files = with_items('P3_TRAIN_B', [item(1, 100.0), item(2, 120.0)])
        snap, _ = self.snapshot('P3_TRAIN_B3', observations, files, 5000.0)
        self.assertFalse(snap['stall']['judged'])

    def test_a_stall_in_training_is_judged_by_its_measured_seconds_per_update(self):
        observations, files = saved('T2E_TRAIN_F')
        snap, _ = self.snapshot('T2E_TRAIN_F', observations, files, T2E_WRITTEN + 30)
        self.assertFalse(snap['stall']['stalled'])
        snap, _ = self.snapshot('T2E_TRAIN_F2', observations, files, T2E_WRITTEN + 100)
        self.assertTrue(snap['stall']['stalled'])
        self.assertAlmostEqual(snap['stall']['allowance_seconds'], 45.99, places=1)

    # --- sealed bundles: counts and timings only ----------------------------------------

    def sealed_snapshot(self, name):
        observations, files = saved('P3_TRAIN_B')
        answer = detail_answer('P3_TRAIN_B')
        answer['mode'] = 'counts'
        observations = {k: v for k, v in observations.items() if k != DETAIL}
        # The remote side is not trusted to have withheld them: they are sent here on purpose.
        observations[COUNTS] = json.dumps(answer)
        files['seal.json'] = dict(files['seal.json'], exposure='sealed', test_manifest_sha256='a' * 64)
        return self.snapshot(name, observations, files, P3_LAST + 10)

    def test_a_sealed_bundle_shows_counts_and_timings_only(self):
        snap, bundle = self.sealed_snapshot('SEALED_RUN')
        self.assertEqual(snap['exposure'], 'sealed')
        self.assertEqual(snap['counts']['passed'], 40)
        for row in snap['rows']:
            self.assertEqual(set(row), {'status', 'seconds', 'finished_epoch'})
        text = live.page(snap, live.alerts(snap, None), 60) + live.summary_line(snap)
        for leaked in ('shimmer2-producer-document', 'E_EVIDENCE_REPLAY', 'model_replies'):
            self.assertNotIn(leaked, text)
        with self.assertRaises(live.SealedRefusal):
            live.item_lines(snap)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = live.main(['--bundle', str(bundle), '--items', '3', '--no-page', '--now', str(P3_LAST + 10),
                              '--observations', str(self.observations_file(bundle, 'P3_TRAIN_B'))])
        self.assertEqual(code, 2)
        self.assertIn('item detail is refused', out.getvalue())

    def observations_file(self, bundle, name):
        observations = saved(name)[0]
        observations[COUNTS] = observations.get(DETAIL)
        path = Path(self.directory.name) / (bundle.name + '_obs.json')
        path.write_text(json.dumps(observations), encoding='utf8')
        return path

    def test_whether_a_bundle_is_exposed_is_read_from_its_seal_and_fails_closed(self):
        base = Path(self.directory.name)
        cases = [(None, 'sealed'), ('not json', 'sealed'),
                 (dict(exposure='exposed', test_manifest_sha256='exposed, no manifest'), 'exposed'),
                 (dict(exposure='exposed', test_manifest_sha256='b' * 64), 'sealed'),
                 (dict(exposure='sealed', test_manifest_sha256='b' * 64), 'sealed'),
                 (dict(test_manifest_sha256='exposed, no manifest'), 'sealed')]
        for n, (seal, expected) in enumerate(cases):
            bundle = base / ('seal_%d' % n)
            bundle.mkdir()
            if seal is not None:
                (bundle / 'seal.json').write_text(seal if isinstance(seal, str) else json.dumps(seal), encoding='utf8')
            self.assertEqual(live.exposure(bundle), expected, seal)

    def test_a_sealed_bundles_page_is_never_written_inside_the_repository(self):
        snap, bundle = self.sealed_snapshot('SEALED_PAGE')
        # A stand-in repository in the temporary folder, so even a neutralised run writes nothing real.
        repository = Path(self.directory.name) / 'repository'
        target = repository / 'output' / 'live_view.html'
        with patch.object(live, 'ROOT', repository), contextlib.redirect_stdout(io.StringIO()):
            code = live.main(['--bundle', str(bundle), '--page', str(target), '--now', str(P3_LAST + 10),
                              '--observations', str(self.observations_file(bundle, 'P3_TRAIN_B'))])
            outside = live.main(['--bundle', str(bundle), '--page', str(Path(self.directory.name) / 'outside.html'),
                                 '--now', str(P3_LAST + 10),
                                 '--observations', str(self.observations_file(bundle, 'P3_TRAIN_B'))])
        self.assertEqual(code, 2)
        self.assertFalse(target.exists())
        self.assertEqual(outside, 0)

    # --- what leaves the instance, and that nothing on it changes ------------------------

    def run_remote_program(self, mode, script=None):
        tree = Path(self.directory.name) / 'instance'
        replies = tree / 'evidence' / 'run' / 'audit' / 'model_replies'
        replies.mkdir(parents=True)
        for n, (ok, error) in enumerate([(True, None), (False, 'OutOfMemoryError: CUDA out of memory'), (True, None)], 1):
            record = dict(schema_version=1, sequence=n, call_id='call%d' % n, agent='VERIFIER', doc_id='doc-a',
                          phase='5', backend_ok=ok, error_category=error.split(':')[0] if error else None,
                          error=error or '', timestamp='2026-11-09T08:00:0%d+00:00' % n,
                          payload=dict(sha256='0' * 64, length_bytes=10, text='PAYLOAD ' + REPLY_MARKER),
                          reply=dict(sha256='1' * 64, length_bytes=10, text=REPLY_MARKER),
                          context=dict(over_context=n == 3))
            (replies / ('%06d_call%d.json' % (n, n))).write_text(json.dumps(record), encoding='utf8')
        (replies / 'outcomes.jsonl').write_text(json.dumps(dict(call_id='call1', outcome='refused', source='run_task')) + '\n',
                                                encoding='utf8')
        (tree / 'workload.stderr.log').write_text('Traceback (most recent call last):\ntorch.OutOfMemoryError: ' + REPLY_MARKER + '\n',
                                                  encoding='utf8')
        before = {p: p.read_bytes() for p in tree.rglob('*') if p.is_file()}
        result = cloud_run_common.hidden_run([sys.executable, '-I', '-', mode], input=(script or live.REMOTE_SCRIPT).encode('utf8'),
                                             capture_output=True, cwd=str(tree), timeout=60)
        after = {p: p.read_bytes() for p in tree.rglob('*') if p.is_file()}
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf8', 'replace')[-400:])
        self.assertEqual(before, after)
        return result.stdout.decode('utf8')

    def test_the_remote_program_sends_no_reply_text(self):
        out = self.run_remote_program('detail')
        self.assertNotIn(REPLY_MARKER, out)
        answer = json.loads(out.splitlines()[-1])
        self.assertEqual(answer['marker'], live.MARKER)
        for row in answer['items']:
            self.assertLessEqual(set(row), set(live.ITEM_FIELDS))
        self.assertEqual([live.classify(r) for r in live.finishes(answer['items'])],
                         [('refused', 'refused'), ('out_of_memory', 'out of memory'), ('refused', 'prompt_over_context')])
        self.assertEqual(answer['stderr_markers'], dict(traceback=1, out_of_memory=1))
        counted = json.loads(self.run_remote_program_again('counts').splitlines()[-1])
        for row in counted['items']:
            self.assertLessEqual(set(row), set(live.COUNT_FIELDS))

    def run_remote_program_again(self, mode):
        import shutil
        shutil.rmtree(Path(self.directory.name) / 'instance')
        return self.run_remote_program(mode)

    def test_the_remote_program_writes_nothing_on_the_instance(self):
        self.assertTrue(live.remote_script_is_read_only(live.REMOTE_SCRIPT))
        for mutant in ("open('x', 'w').write('y')\n", "import os\nos.remove('evidence')\n",
                       "import subprocess\nsubprocess.run(['true'])\n", "open('x', 'a')\n"):
            self.assertFalse(live.remote_script_is_read_only(live.REMOTE_SCRIPT + mutant), mutant)
        command = live.remote_command('detail')
        self.assertTrue(command.startswith('cd %s && echo ' % live.REMOTE_ROOT))
        self.assertIn(' | base64 -d | python3 -I - detail # shimmer-live-view-v1 detail', command)
        with self.assertRaises(ValueError):
            live.remote_command('anything')

    def test_every_child_process_runs_without_a_window(self):
        observations, files = saved('P3_TRAIN_B')
        bundle = make_bundle(self.directory.name, 'P3_TRAIN_B', files,
                             {'activation.json': dict(metadata=dict(public_ip='198.51.100.10'))})
        starts = []

        def recorder(argv, **kwargs):
            starts.append(dict(kwargs, argv=argv))
            out = kwargs.get('stdout')
            if hasattr(out, 'write'):
                out.write(observations[DETAIL].encode('utf8'))
            return subprocess.CompletedProcess(argv, 0, stdout=b'', stderr=b'')
        with patch.object(live.subprocess, 'run', recorder), patch.object(live.progress.subprocess, 'run', recorder):
            snap = live.snapshot_for(bundle, now=P3_LAST + 10)
        self.assertEqual(snap['counts']['passed'], 40)
        self.assertTrue(starts)
        for start in starts:
            self.assertEqual(start['argv'][0], 'ssh')
            self.assertIn('creationflags', start)
            self.assertEqual(start['creationflags'], cloud_run_common.no_window())
        tree = ast.parse((ROOT / 'tools' / 'ordinary_final_live.py').read_text(encoding='utf8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ('run', 'Popen', 'call'):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'subprocess':
                    self.assertTrue(any(k.arg == 'creationflags' for k in node.keywords))

    def test_the_reader_is_not_part_of_the_bound_controller(self):
        bound = live.bound_controller_files()
        self.assertIn('tools/ordinary_final_cloud.py', bound)
        for name in ('tools/ordinary_final_live.py', 'tools/ordinary_final_live_checks.py'):
            self.assertNotIn(name, bound)
        for name in bound:
            self.assertNotIn('ordinary_final_live', (ROOT / name).read_text(encoding='utf8'))
        for manifest in list((ROOT / 'docs').rglob('execution_manifest.json'))[:400]:
            try:
                pinned = json.loads(manifest.read_text(encoding='utf8')).get('local_control_hashes') or {}
            except ValueError:
                continue
            self.assertFalse([n for n in pinned if 'ordinary_final_live' in n], manifest)

    # --- the page and the line --------------------------------------------------------------

    def test_the_page_refreshes_itself_and_escapes_what_it_shows(self):
        observations, files = with_items('P3_TRAIN_B', [item(n, 100.0 + 20 * n, doc_id='<script>x</script>') for n in range(1, 5)])
        snap, bundle = self.snapshot('P3_TRAIN_B', observations, files, 190.0)
        text = live.page(snap, ['ALERT P3_TRAIN_B stall: <b>'], 45)
        self.assertIn('<meta http-equiv="refresh" content="45">', text)
        self.assertIn('<title>Live run view</title>', text)
        self.assertIn('prefers-color-scheme: dark', text)
        self.assertNotIn('<script>', text)
        self.assertIn('&lt;script&gt;', text)
        self.assertNotIn(chr(0x2014), text + live.summary_line(snap))
        self.assertEqual(len(live.summary_line(snap).splitlines()), 1)
        target = Path(self.directory.name) / 'page' / 'index.html'
        with contextlib.redirect_stdout(io.StringIO()):
            observations_path = Path(self.directory.name) / 'o.json'
            observations_path.write_text(json.dumps(observations), encoding='utf8')
            self.assertEqual(live.main(['--bundle', str(bundle), '--page', str(target), '--now', '190',
                                        '--observations', str(observations_path)]), 0)
        self.assertTrue(target.read_text(encoding='utf8').startswith('<!doctype html>'))


class _NoEscape:
    @staticmethod
    def escape(text, quote=True):
        return str(text)


def _no_strip(snapshot):
    return snapshot


def _finishes_without_folders(items):
    rows = sorted((dict(i) for i in items if i.get('finished_epoch') is not None), key=lambda r: r['finished_epoch'])
    for row in rows:
        row['status'], row['reason'] = live.classify(row)
        row['seconds'] = None
    return rows


def _observe_without_flags(bundle, host, command, timeout=90):
    argv = ['ssh', host, command]
    with tempfile.TemporaryFile() as answer:
        live.subprocess.run(argv, stdout=answer, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=timeout)
        answer.seek(0)
        return answer.read().decode('utf8')


LEAKY_SCRIPT = live.REMOTE_SCRIPT.replace('        items.append(row)', '        row.update(raw=record)\n        items.append(row)')
WRITING_SCRIPT = live.REMOTE_SCRIPT + "open('touched', 'w').write('x')\n"

# (proof, owner, attribute, mutant): while the mutant is in place the proof must fail.
NEUTRALIZATIONS = [
    ('test_replay_reproduces_each_saved_runs_reading', live, 'finishes', _finishes_without_folders),
    ('test_each_failure_class_is_read_from_its_record', live, 'is_oom', lambda item: False),
    ('test_a_refusal_carries_its_reason', live, 'REFUSED_OUTCOMES', ()),
    ('test_the_same_failure_repeating_is_an_alert', live, 'REPEAT_RUN', 10 ** 6),
    ('test_out_of_memory_and_a_crash_are_alerts', live, 'crash_signal', lambda snapshot: None),
    ('test_a_refusal_rate_above_the_development_figure_is_an_alert', live, 'RATE_MIN_ITEMS', 10 ** 6),
    ('test_a_stall_is_judged_by_the_runs_own_measured_time_per_call', live, 'stall_allowance', lambda seconds: float('inf')),
    ('test_a_stall_in_training_is_judged_by_its_measured_seconds_per_update', live, 'STALL_FACTOR', 10 ** 6),
    ('test_a_sealed_bundle_shows_counts_and_timings_only', live, 'strip_for_sealed', _no_strip),
    ('test_whether_a_bundle_is_exposed_is_read_from_its_seal_and_fails_closed', live, 'exposure', lambda bundle: 'exposed'),
    ('test_a_sealed_bundles_page_is_never_written_inside_the_repository', live, 'inside_repository', lambda path: False),
    ('test_the_remote_program_sends_no_reply_text', live, 'REMOTE_SCRIPT', LEAKY_SCRIPT),
    ('test_the_remote_program_writes_nothing_on_the_instance', live, 'REMOTE_SCRIPT', WRITING_SCRIPT),
    ('test_every_child_process_runs_without_a_window', live, 'observe_to_file', _observe_without_flags),
    ('test_the_reader_is_not_part_of_the_bound_controller', live, 'bound_controller_files',
     lambda: sorted(['tools/ordinary_final_cloud.py', 'tools/ordinary_final_live.py'])),
    ('test_the_page_refreshes_itself_and_escapes_what_it_shows', live, 'html', _NoEscape),
]


def _single(name):
    return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(LiveViewProofs(name)).wasSuccessful()


def check():
    """Gate entry: every proof passes, and each one fails under its neutralisation and passes
    again once restored. Sockets are denied throughout."""
    def denied(*args, **kwargs):
        raise AssertionError('Network prohibited')
    with patch.object(socket.socket, 'connect', denied), patch.object(socket, 'create_connection', denied):
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(LiveViewProofs))
        if not result.wasSuccessful():
            problems = [str(case) for case, _ in list(result.failures) + list(result.errors)]
            return 'FAIL', 'live view proofs failed: ' + '; '.join(problems[:3])
        names = set(unittest.defaultTestLoader.getTestCaseNames(LiveViewProofs))
        missing = names - {n for n, _, _, _ in NEUTRALIZATIONS}
        if missing:
            return 'FAIL', 'proofs with no neutralisation: ' + ', '.join(sorted(missing))
        broken = []
        for name, owner, attribute, mutant in NEUTRALIZATIONS:
            before = _single(name)
            with patch.object(owner, attribute, mutant):
                neutralized = _single(name)
            after = _single(name)
            if not (before and not neutralized and after):
                broken.append('%s (before %s, neutralised %s, after %s)' % (name, before, neutralized, after))
        if broken:
            return 'FAIL', 'neutralise/fail/restore/pass broken: ' + '; '.join(broken)
    return 'PASS', ('%d proofs, each neutralised, failing, restored and passing: replayed readings of three exposed '
                    'runs (P3_TRAIN_B 40 calls at a median 18.4 s, T2E_TRAIN_F training at 15.3 s an update, '
                    'AUD_TRAIN5), each outcome class with its reason, the repeat, out-of-memory, crash, refusal-rate '
                    'and stall alerts, sealed bundles counts and timings only and failing closed, no reply text and '
                    'no write on the instance, no window, not in the controller binding' % result.testsRun)


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
