"""Proofs for tools/loop/asset_copy_launch_check.py (D-S107 item 1), on a fixture ledger and fixture
bundles only. Each rule is proven by neutralise, fail, restore, pass in `check()`, which gate check 350
runs.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import asset_copy_launch_check as copy_check  # noqa: E402


def bundle(root, name, *, digest='a' * 64, exposure='exposed', declared=False, state=None, seeded=False,
           used=False, uploaded=True):
    """A launched bundle with its receipt and upload timing; returns the instance name it launched as."""
    folder = Path(root) / name
    folder.mkdir(parents=True)
    (folder / 'execution_manifest.json').write_text(json.dumps(dict(name=name, assets_archive=dict(
        sha256=digest, bytes=22_250_000_000))), encoding='utf-8')
    (folder / 'LAUNCH_INTENT.json').write_text('{}', encoding='utf-8')
    (folder / 'seal.json').write_text(json.dumps(dict(exposure=exposure)), encoding='utf-8')
    (folder / 'asset_copy_receipt.json').write_text(json.dumps(dict(declared=declared, state=state, seeded=seeded,
                                                                    used=used)), encoding='utf-8')
    if uploaded:
        (folder / 'assets_transfer_timing.json').write_text(json.dumps(dict(seconds=3780, returncode=0)), encoding='utf-8')
    key = hashlib.sha256((folder / 'execution_manifest.json').read_bytes()).hexdigest()[:8]
    return 'shimmer-loop-x-' + key


def ledger_lines(path, launches):
    rows = []
    for n, (name, when, region) in enumerate(launches):
        rows.append(dict(event='launch', instance_name=name, time_utc=when, launch_requested_utc=when, region=region,
                         price_usd_per_hour=1.29, purpose='p%d' % n))
        rows.append(dict(event='termination', instance_name=name, actual_minutes=90, actual_cost=1.94))
    Path(path).write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')


class AssetCopyLaunchChecks(unittest.TestCase):
    def test_an_upload_the_copy_could_have_spared_is_listed_with_its_cost(self):
        """Since 5 November, in us-east-1, exposed: an undeclared upload counts, and so does a declared
        upload of a digest an earlier launch had already seeded; the first declared seed of a new digest,
        a launch that used the copy, a sealed run, another region and a launch before 5 November do not.
        Each is listed with its 63 minutes and 1.35 USD at 1.29 an hour."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'bundles'
            names = dict(
                undeclared=bundle(root, 'undeclared'),
                seed=bundle(root, 'seed', declared=True, state='MISSING', seeded=True),
                again=bundle(root, 'again', declared=True, state='MISSING'),
                used=bundle(root, 'used', declared=True, state='MATCH', used=True, uploaded=False),
                sealed=bundle(root, 'sealed', exposure='sealed'),
                west=bundle(root, 'west'),
                before=bundle(root, 'before'))
            ledger = Path(tmp) / 'ledger.jsonl'
            ledger_lines(ledger, [(names['before'], '2026-11-04T23:00:00+00:00', 'us-east-1'),
                                  (names['undeclared'], '2026-11-06T09:00:00+00:00', 'us-east-1'),
                                  (names['seed'], '2026-11-07T09:00:00+00:00', 'us-east-1'),
                                  (names['again'], '2026-11-08T09:00:00+00:00', 'us-east-1'),
                                  (names['used'], '2026-11-08T10:00:00+00:00', 'us-east-1'),
                                  (names['sealed'], '2026-11-08T11:00:00+00:00', 'us-east-1'),
                                  (names['west'], '2026-11-08T12:00:00+00:00', 'us-west-1')])
            result = copy_check.check(ledger, root)
            self.assertEqual(sorted(r['bundle'] for r in result['findings']), ['again', 'undeclared'])
            self.assertEqual(result['launches_read'], 6)
            self.assertEqual((result['upload_minutes'], result['upload_cost_usd']), (126.0, 2.71))
            with open(os.devnull, 'w') as sink, patch('sys.stdout', sink):
                self.assertEqual(copy_check.main(['--ledger', str(ledger), '--bundles', str(root)]), 1)
            clean = Path(tmp) / 'clean.jsonl'
            ledger_lines(clean, [(names['used'], '2026-11-08T10:00:00+00:00', 'us-east-1')])
            with open(os.devnull, 'w') as sink, patch('sys.stdout', sink):
                self.assertEqual(copy_check.main(['--ledger', str(clean), '--bundles', str(root)]), 0)


NEUTRALISED = [
    # Every launch read as one that could not have used the copy.
    ('could_have_used', lambda row, sealed: False, ['test_an_upload_the_copy_could_have_spared_is_listed_with_its_cost']),
    # A sealed run counted as one that could have read the copy.
    ('sealed_bundle', lambda found, row: False, ['test_an_upload_the_copy_could_have_spared_is_listed_with_its_cost']),
]


def passes(*names):
    loader = unittest.defaultTestLoader
    suite = (unittest.TestSuite(AssetCopyLaunchChecks(n) for n in names) if names
             else loader.loadTestsFromTestCase(AssetCopyLaunchChecks))
    with open(os.devnull, 'w') as sink:
        result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
    return result.wasSuccessful() and result.testsRun > 0


def check():
    if not passes():
        return 'FAIL', 'tools/loop/asset_copy_launch_check_checks.py does not pass'
    proofs = []
    for attribute, mutant, names in NEUTRALISED:
        with patch.object(copy_check, attribute, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        if not (failed and restored):
            return 'FAIL', 'asset_copy_launch_check.%s neutralised: failed=%s, restored pass=%s' % (attribute, failed, restored)
        proofs.append(attribute)
    return 'PASS', ('a loop launch since 5 November in us-east-1 that uploaded the archive while the copy could have '
                    'been used is listed with its minutes and cost, and none other; neutralised, failed, restored, '
                    'passed: ' + ', '.join(proofs))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
