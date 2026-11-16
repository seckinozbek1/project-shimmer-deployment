"""Proofs for tools/loop/disk_sweep.py (D-611, issue #266), on a fixture git repository in a temporary
folder only; the real tree is never read. Every refusal is proven by neutralise, fail, restore, pass in
`check()`, which gate check 385 runs.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import disk_sweep as ds  # noqa: E402
import register_disk_sweep as reg  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud_run_common import no_window  # noqa: E402  (D-079, HIDDEN-A)

GIT = ['git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', '-c', 'commit.gpgsign=false']


def cfg():
    config = ds.load_config()
    config['kinds'] = [k for k in config['kinds'] if k['name'] in ('python_bytecode_cache', 'refused_seal_folder')]
    for kind in config['kinds']:
        kind['min_age_days'] = 0
    return config


def put(root, rel, text='x'):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def fixture(tmp):
    """A repository with one candidate per refusal, each refused by that guard alone, plus ones that go."""
    root = Path(tmp) / 'repo'
    root.mkdir()
    subprocess.run(['git', 'init', '-q', str(root)], check=True, creationflags=no_window())
    put(root, 'tracked/__pycache__/t.pyc', 'tracked')
    put(root, 'README.md', 'r')
    subprocess.run(['git', '-C', str(root), 'add', '-f', 'README.md', 'tracked/__pycache__/t.pyc'], check=True, creationflags=no_window())
    subprocess.run(GIT[:1] + ['-C', str(root)] + GIT[1:] + ['commit', '-q', '-m', 'fixture'], check=True, creationflags=no_window())
    put(root, 'goes/__pycache__/a.pyc', 'aaaa')                                  # nothing refuses it
    put(root, 'named/__pycache__/n.pyc', 'bbbb')                                 # a seal names its file
    put(root, 'bundle1/seal.json', json.dumps({'file': 'named/__pycache__/n.pyc'}))
    put(root, 'digested/__pycache__/d.pyc', 'dddd-digest')                       # a request holds its digest
    put(root, 'req/REQUEST_1.md', 'digest ' + sha('dddd-digest'))
    put(root, 'sealed/seal.json', '{}')                                          # a pycache beside a seal
    put(root, 'sealed/__pycache__/s.pyc', 'ssss')
    put(root, 'holds/__pycache__/manifest.json', '{}')                           # a pycache holding a manifest
    put(root, 'fp/__pycache__/fingerprints.json.gz', 'ffff')                     # a fingerprint inside
    put(root, 'docs/loop/p/__pycache__/p.pyc', 'pppp')                           # protected areas
    put(root, 'config/__pycache__/c.pyc', 'cccc')
    put(root, 'durable/__pycache__/u.pyc', 'uuuu')
    put(root, 'private/__pycache__/v.pyc', 'vvvv')
    put(root, 'unmatched/other_dir/keep.txt', 'kkkk')                             # no kind matches it
    # an open launch's folder (a refused-seal kind that holds the manifest the ledger's name is keyed by)
    open_manifest = '{"run": "open"}'
    put(root, 'external/open.refused_1/execution_manifest.json', open_manifest)
    closed_manifest = '{"run": "closed"}'
    put(root, 'external/closed.refused_1/execution_manifest.json', closed_manifest)
    rows = [
        {'event': 'launch_intent', 'instance_name': 'shimmer-loop-x-' + sha(open_manifest)[:8]},
        {'event': 'launch', 'instance_name': 'shimmer-loop-x-' + sha(open_manifest)[:8]},
        {'event': 'launch', 'instance_name': 'shimmer-loop-x-' + sha(closed_manifest)[:8]},
        {'event': 'termination', 'instance_name': 'shimmer-loop-x-' + sha(closed_manifest)[:8]},
    ]
    ledger = Path(tmp) / 'budget_ledger.jsonl'
    ledger.write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
    return root, ledger


def run(root, ledger, log, apply, clock=lambda: '2026-11-13T00:00:00+00:00'):
    return ds.sweep(root, cfg(), ledger, log, apply, clock=clock, free=lambda p: 40 << 30)


def planned(result):
    return {Path(r['path']).relative_to(result_root(result)).as_posix() for r in result['plan']}


def result_root(result):
    return Path(result['_root'])


def sweep(root, ledger, log, apply):
    result = run(root, ledger, log, apply)
    result['_root'] = str(root)
    return result


class DiskSweepChecks(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root, self.ledger = fixture(self._tmp.name)
        self.log = Path(self._tmp.name) / 'disk_sweep_log.jsonl'

    def exists(self, rel):
        return (self.root / rel).exists()

    def test_a_dry_run_plans_the_regenerable_and_deletes_nothing(self):
        """Only the bytecode cache nothing refuses, and the closed launch's refused folder, are planned;
        a dry run removes nothing and writes no log."""
        result = sweep(self.root, self.ledger, self.log, False)
        self.assertEqual(planned(result), {'goes/__pycache__', 'external/closed.refused_1'})
        self.assertTrue(all(self.exists(p) for p in ('goes/__pycache__', 'external/closed.refused_1')))
        self.assertFalse(self.log.exists())

    def test_a_path_a_seal_names_is_kept(self):
        result = sweep(self.root, self.ledger, self.log, True)
        self.assertTrue(self.exists('named/__pycache__/n.pyc'))
        self.assertIn('named', ' '.join(r['path'] for r in result['refused']).replace('\\', '/'))

    def test_a_file_whose_digest_a_request_holds_is_kept(self):
        sweep(self.root, self.ledger, self.log, True)
        self.assertTrue(self.exists('digested/__pycache__/d.pyc'))

    def test_a_tracked_file_is_kept(self):
        sweep(self.root, self.ledger, self.log, True)
        self.assertTrue(self.exists('tracked/__pycache__/t.pyc'))

    def test_an_open_launch_folder_is_kept_and_a_closed_one_goes(self):
        sweep(self.root, self.ledger, self.log, True)
        self.assertTrue(self.exists('external/open.refused_1/execution_manifest.json'))
        self.assertFalse(self.exists('external/closed.refused_1'))

    def test_an_unreadable_ledger_keeps_everything(self):
        os.remove(self.ledger)
        result = ds.sweep(self.root, cfg(), self.ledger, self.log, False, free=lambda p: 1 << 40)
        self.assertEqual(result['plan'], [])
        with self.assertRaises(ds.SweepError):
            ds.sweep(self.root, cfg(), self.ledger, self.log, True, free=lambda p: 1 << 40)

    def test_an_unmatched_path_is_kept(self):
        context = ds.make_context(self.root, cfg(), self.ledger)
        stray = ds.Candidate(self.root / 'unmatched' / 'other_dir', cfg()['kinds'][0])
        self.assertEqual(ds.refusal(context, stray), 'matched by no declared kind')
        sweep(self.root, self.ledger, self.log, True)
        self.assertTrue(self.exists('unmatched/other_dir/keep.txt'))

    def test_the_protected_areas_a_private_folder_and_sealed_places_are_kept(self):
        sweep(self.root, self.ledger, self.log, True)
        for rel in ('docs/loop/p/__pycache__/p.pyc', 'config/__pycache__/c.pyc', 'durable/__pycache__/u.pyc',
                    'private/__pycache__/v.pyc', 'sealed/__pycache__/s.pyc', 'holds/__pycache__/manifest.json',
                    'fp/__pycache__/fingerprints.json.gz'):
            self.assertTrue(self.exists(rel), rel)

    def test_the_log_line_is_complete(self):
        sweep(self.root, self.ledger, self.log, True)
        lines = [json.loads(x) for x in self.log.read_text(encoding='utf-8').splitlines()]
        self.assertEqual({l['path'] for l in lines}, {'goes/__pycache__', 'external/closed.refused_1'})
        for line in lines:
            self.assertEqual(set(line), {'time_utc', 'path', 'bytes', 'kind', 'reason', 'regenerate'})
            self.assertTrue(all(line[k] not in (None, '') for k in line))
            self.assertEqual(line['time_utc'], '2026-11-13T00:00:00+00:00')
        self.assertEqual({l['path']: l['bytes'] for l in lines}['goes/__pycache__'], 4)

    def test_the_post_check_catches_a_removed_referenced_path(self):
        context = ds.make_context(self.root, cfg(), self.ledger)
        self.assertEqual(ds.post_check(context.index), [])
        (self.root / 'named' / '__pycache__' / 'n.pyc').unlink()
        self.assertEqual(len(ds.post_check(context.index)), 1)

    def test_a_deleted_referenced_path_fails_the_run_end_to_end(self):
        """With the reference guard in place the run's post-check is empty; with it gone a seal-named file is
        deleted and the run's own post-check says so."""
        self.assertEqual(sweep(self.root, self.ledger, self.log, True)['post_check_missing'], [])
        other = tempfile.mkdtemp(dir=self._tmp.name)
        root, ledger = fixture(other)
        with patch.object(ds, '_g_referenced', lambda c, k, n: None):
            result = sweep(root, ledger, Path(other) / 'log.jsonl', True)
        self.assertFalse((root / 'named' / '__pycache__' / 'n.pyc').exists())
        self.assertTrue(result['post_check_missing'])


    def test_the_main_checkout_variable_names_the_sweep_root(self):
        """DELETE-SAFE-A (operator 16 Nov 2026 15:58, item 2): SHIMMER_MAIN_CHECKOUT names the main checkout the
        sweep's --apply needs, from a folder git cannot read; a worktree named there is refused."""
        import shared_paths
        main = Path(self._tmp.name) / 'named_main'
        (main / '.git').mkdir(parents=True)
        elsewhere = Path(self._tmp.name) / 'elsewhere'
        elsewhere.mkdir()
        with patch.dict(os.environ, {shared_paths.ENV: str(main)}):
            self.assertEqual(ds.main_root(elsewhere), main.resolve())
        lane = Path(self._tmp.name) / 'lane'
        lane.mkdir()
        (lane / '.git').write_text('gitdir: elsewhere\n', encoding='utf-8')
        with patch.dict(os.environ, {shared_paths.ENV: str(lane)}), self.assertRaises(ds.SweepError):
            ds.main_root(elsewhere)


class RegistrationChecks(unittest.TestCase):
    def test_the_task_runs_daily_in_the_main_checkout_and_starts_on_demand_only_when_low(self):
        xml = reg.task_xml('user', 'pythonw', 'script', 'root')
        self.assertIn('<DaysInterval>1</DaysInterval>', xml)
        self.assertIn('InteractiveToken', xml)
        self.assertIn('--apply</Arguments>', xml)
        calls = []

        class Usage:
            def __init__(self, gib):
                self.free = int(gib * (1 << 30))

        class Done:
            returncode, stdout, stderr = 0, 'ok', ''

        runner = lambda argv, **kw: calls.append(argv) or Done()   # noqa: E731
        self.assertEqual(reg.run_now_if_low('r', free=lambda p: Usage(40), runner=runner)[0], False)
        self.assertEqual(calls, [])
        self.assertEqual(reg.run_now_if_low('r', free=lambda p: Usage(20), runner=runner)[0], True)
        self.assertEqual(calls[0][:2], ['schtasks', '/Run'])


def passing_tests():
    return [n for n in dir(DiskSweepChecks) if n.startswith('test_')]


# (attribute, mutant, the tests that must then fail): each guard gone, one at a time.
OFF = lambda *a, **k: None   # noqa: E731
NEUTRALISED = [
    ('_g_referenced', OFF, ['test_a_path_a_seal_names_is_kept', 'test_a_file_whose_digest_a_request_holds_is_kept']),
    ('_g_tracked', OFF, ['test_a_tracked_file_is_kept']),
    ('_g_open_launch', OFF, ['test_an_open_launch_folder_is_kept_and_a_closed_one_goes',
                             'test_an_unreadable_ledger_keeps_everything']),
    ('_g_unmatched', OFF, ['test_an_unmatched_path_is_kept']),
    ('_g_protected', OFF, ['test_the_protected_areas_a_private_folder_and_sealed_places_are_kept']),
    ('_g_private', OFF, ['test_the_protected_areas_a_private_folder_and_sealed_places_are_kept']),
    ('_g_sealed', OFF, ['test_the_protected_areas_a_private_folder_and_sealed_places_are_kept']),
    ('_g_fingerprint', OFF, ['test_the_protected_areas_a_private_folder_and_sealed_places_are_kept']),
    ('post_check', lambda index: [], ['test_the_post_check_catches_a_removed_referenced_path',
                                      'test_a_deleted_referenced_path_fails_the_run_end_to_end']),
    ('log_line', lambda when, rel, row: {'time_utc': when, 'path': rel, 'bytes': row['bytes'], 'kind': row['kind']},
     ['test_the_log_line_is_complete']),
    # DELETE-SAFE-A: the root read from git alone, SHIMMER_MAIN_CHECKOUT ignored.
    ('main_root', lambda start=HERE, runner=None: __import__('shared_paths').from_git(start),
     ['test_the_main_checkout_variable_names_the_sweep_root']),
]


def passes(*names):
    suite = unittest.TestSuite(DiskSweepChecks(n) for n in (names or passing_tests()))
    if not names:
        suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(RegistrationChecks))
    with open(os.devnull, 'w') as sink:
        result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
    return result.wasSuccessful() and result.testsRun > 0


def check():
    if not passes():
        return 'FAIL', 'tools/loop/disk_sweep_checks.py does not pass'
    proofs = []
    for attribute, mutant, names in NEUTRALISED:
        with patch.object(ds, attribute, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        if not (failed and restored):
            return 'FAIL', 'disk_sweep.%s neutralised: failed=%s, restored pass=%s' % (attribute, failed, restored)
        proofs.append(attribute)
    return 'PASS', ('the sweep deletes only what a declared kind matches and nothing refused (a path named in a seal, '
                    'a digest in a request, a tracked file, an open launch folder, an unmatched path, a protected, '
                    'private, sealed or fingerprint place), logs each deletion in full and its post-check catches a '
                    'removed referenced path; neutralised, failed, restored, passed: ' + ', '.join(proofs))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
