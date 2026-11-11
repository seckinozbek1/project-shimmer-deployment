"""Proofs for tools/loop/standing_orders_check.py and the standing-orders block of
tools/loop/session_start.py (D-S110 items 2 and 3a), on fixtures in a temporary folder only: a
git repository with a loop branch and a bare origin, a private folder with a tablet, a ledger,
a reaper status, a spend store, FOR_SECKIN and a scoreboard, and run folders under external/.
Nothing private is read. `check()` runs the tests, then neutralises each rule in turn, requires a
failure, restores it and requires a pass.

    py -3.12 -X utf8 tools/loop/standing_orders_checks.py
"""
from __future__ import annotations

import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import standing_orders_check as soc  # noqa: E402
import session_start  # noqa: E402
import instance_reaper  # noqa: E402
from cloud_run_common import no_window  # noqa: E402

LOOP = 'loop/fixture'
HEAD = '| # | Order | Source, since | How it is proven to hold now |\n|---|---|---|---|\n'


def _git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, creationflags=no_window())
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def state(value):
    """A checker's state, booleans read as kept and broken."""
    return soc._verdict(value)[0]


GUARD = "'''A fixture guard: one rule each, the shape of the real one.'''\n\n\ndef scan_line(line):\n    return ['marker'] if 'FIXTURE-REFUSED' + '-VALUE' in line else []\n\n\ndef is_refused_path(name):\n    return '/model_replies/' in '/' + name\n"


def order(n, text, proof):
    return '| %d | %s | D-S0, 9 Nov | %s |\n' % (n, text, proof)


class Fixture:
    def __init__(self, folder):
        base = Path(folder)
        self.root = base / 'repo'
        self.root.mkdir()
        _git(self.root, 'init', '-q', '-b', LOOP)
        for key, value in (('user.email', 'fixture@example.invalid'), ('user.name', 'fixture'),
                           ('commit.gpgsign', 'false'), ('core.autocrlf', 'false')):
            _git(self.root, 'config', key, value)
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts' / 'guard_secrets.py').write_text(GUARD, encoding='utf-8')
        (self.root / 'docs' / 'loop').mkdir(parents=True)
        self.commit('docs/loop/HELDOUT_OPENINGS.md',
                    '| Part | k | Alpha | Tuning pass record (commit) |\n|---|---|---|---|\n', 'scripts/guard_secrets.py')
        self.first = _git(self.root, 'rev-parse', '--short=8', 'HEAD')
        self.private = self.root / 'docs' / 'loop' / 'private'
        self.private.mkdir()

    def commit(self, path, text, *more):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')
        for p in (path,) + more:
            _git(self.root, 'add', p)
        _git(self.root, 'commit', '-q', '-m', 'commit ' + path)
        return _git(self.root, 'rev-parse', '--short=8', 'HEAD')

    def write(self, name, text):
        (self.private / name).write_text(text, encoding='utf-8')

    def ctx(self):
        return soc.Context(self.root, self.private, LOOP)


def launch_folder(root, name, when, receipt=None, region='us-east-1', digest=None, instance=None, under=None,
                  uploaded=False):
    folder = root / 'external' / name
    folder.mkdir(parents=True)
    (folder / 'launch.json').write_text(json.dumps({'epoch': when.timestamp(), 'region': region,
                                                    'instance_id': instance or name}), encoding='utf-8')
    if receipt is not None:
        (folder / 'asset_copy_receipt.json').write_text(json.dumps(receipt), encoding='utf-8')
    if digest:
        (folder / 'asset_copy_declaration.json').write_text(json.dumps({'assets_sha256': digest}), encoding='utf-8')
    if uploaded:
        (folder / 'assets_transfer_timing.json').write_text(json.dumps({'seconds': 600.0, 'returncode': 0}),
                                                           encoding='utf-8')
    return folder


AFTER = datetime(2026, 11, 9, 16, 0, tzinfo=timezone.utc)
SCOREBOARD_HEAD = ('## Benchmark rows\n\n| Row | Time | Primary metric (D-S99) | Class setting | System (95% CI) | '
                   'Gap to (a) / (b) |\n|---|---|---|---|---|---|\n')


class StandingOrdersChecks(unittest.TestCase):
    def setUp(self):
        if shutil.which('git') is None:
            self.skipTest('no git')
        self.folder = tempfile.TemporaryDirectory()
        self.fx = Fixture(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    # the tablet

    def test_the_tablet_is_read_and_an_unreadable_row_fails(self):
        text = HEAD + order(1, 'a', 'script: x') + order(2, 'b', 'record: y') + order(3, 'c', 'broken today: z') + \
            order(4, '(withdrawn as redundant)', 'none') + order(5, 'd', 'maybe: w') + '| 6 | too | few |\n'
        orders, problems = soc.parse_tablet(text)
        self.assertEqual([(o['number'], o['kind']) for o in orders],
                         [(1, 'script'), (2, 'record'), (3, 'broken today'), (4, 'withdrawn')])
        self.assertEqual(len(problems), 2)
        self.assertFalse(soc.run(self.fx.ctx(), text, gate_runner=lambda n: {})['ok'])

    def test_records_declared_broken_and_withdrawn_orders(self):
        ctx = self.fx.ctx()
        judge = lambda proof, text='x': soc.judge({'number': 99, 'order': text, 'proof': proof,
                                                   'kind': soc.parse_tablet(HEAD + order(99, text, proof))[0][0]['kind']}, ctx)
        self.assertEqual(judge('record: the brief')[0], 'unchecked')
        self.assertEqual(judge('broken today: empty signal')[0], 'broken')
        self.assertEqual(judge('none', '(withdrawn, D-1)')[0], 'withdrawn')

    def test_a_checker_bound_to_a_renumbered_order_fails(self):
        state, evidence = soc.judge({'number': 1, 'order': 'Free disk at or above 30 GB.', 'proof': 'script: x',
                                     'kind': 'script'}, self.fx.ctx())
        self.assertEqual(state, 'unable')
        self.assertIn('does not match its text', evidence)

    def test_gate_checks_named_in_a_proof_are_run(self):
        ctx = self.fx.ctx()
        o = {'number': 77, 'order': 'x', 'proof': 'script: gate check 174 and gate checks 176, 213; record: y',
             'kind': 'script'}
        self.assertEqual(soc.gate_numbers(o['proof']), [174, 176, 213])
        self.assertEqual(soc.gate_numbers('script: check 174 (a phrase, not a gate check)'), [])
        self.assertEqual(soc.judge(o, ctx, gate_runner=lambda n: {k: 'MISSING' for k in n})[0], 'unable')
        self.assertEqual(soc.judge(o, ctx, gate_runner=lambda n: {k: 'PASS' for k in n})[0], 'kept')
        self.assertEqual(soc.judge(o, ctx, gate_runner=lambda n: {k: ('FAIL' if k == 176 else 'PASS') for k in n})[0], 'broken')
        none = {'number': 78, 'order': 'x', 'proof': 'script: something unnamed', 'kind': 'script'}
        self.assertEqual(soc.judge(none, ctx, gate_runner=lambda n: {}), ('not_built', 'a script proof with no '
                         'checker and no gate check named'))

    # the registered checkers

    def test_image_every_east_launch_since_5_november_starts_from_the_copy(self):
        root = self.fx.root
        match = {'declared': True, 'state': 'MATCH', 'used': True}
        seed = {'declared': True, 'state': 'MISSING', 'seeded': True, 'used': False}
        launch_folder(root, 'old', datetime(2026, 11, 1, tzinfo=timezone.utc), {'declared': False})
        launch_folder(root, 'first_seed', AFTER, seed, digest='d2', uploaded=True)
        launch_folder(root, 'after_seed', AFTER + timedelta(minutes=1), match, digest='d2')
        launch_folder(root, 'session', AFTER + timedelta(minutes=2), match, digest='d1')
        launch_folder(root, 'session/batch/00_entry', AFTER + timedelta(minutes=2), None, instance='session')
        launch_folder(root, 'west', AFTER, {'declared': False}, region='us-west-1')
        launch_folder(root, 'reasoned', AFTER + timedelta(minutes=3),
                      {'declared': False, 'upload_reason': 'seed of a missing digest'}, uploaded=True)
        launch_folder(root, 'absent', AFTER + timedelta(minutes=4), {'declared': False, 'absence_reason': 'sealed run'},
                      uploaded=True)
        # D-467 item 1: a launch that uploaded nothing is not judged (it ended before the probe), and
        # a MISSING copy is an admitted upload whether its seed failed or was never reached.
        launch_folder(root, 'ended_before_probe', AFTER + timedelta(minutes=4, seconds=1),
                      {'declared': True, 'state': None, 'used': False}, digest='d1')
        launch_folder(root, 'seed_failed', AFTER + timedelta(minutes=4, seconds=2),
                      {'declared': True, 'state': 'MISSING', 'seeded': False, 'used': False}, digest='d3', uploaded=True)
        launch_folder(root, 'seed_never_reached', AFTER + timedelta(minutes=4, seconds=3),
                      {'declared': True, 'state': 'MISSING', 'seeded': False, 'used': False}, digest='d3', uploaded=True)
        # D-464 item 1: the controller's own recorded fallbacks are kept; a probe past its deadline,
        # then the next launch from the copy.
        launch_folder(root, 'probe_timeout', AFTER + timedelta(minutes=4, seconds=10),
                      {'declared': True, 'state': 'PROBE_TIMEOUT', 'used': False}, digest='d1', uploaded=True)
        launch_folder(root, 'after_timeout', AFTER + timedelta(minutes=4, seconds=20), match, digest='d1')
        for n, receipt in enumerate(({'declared': True, 'state': 'UNREACHABLE', 'used': False},
                                     {'declared': True, 'state': 'MISMATCH', 'suspect': True, 'used': False},
                                     {'declared': True, 'state': 'MISSING', 'seeded': False, 'used': False,
                                      'seed_refused': 'the filesystem has no room for the archive'},
                                     {'declared': True, 'state': 'USE_FAILED', 'used': False})):
            launch_folder(root, 'fallback_%d' % n, AFTER + timedelta(minutes=4, seconds=30 + n), receipt, digest='d1',
                          uploaded=True)
        fresh = root / 'external' / 'D-S56' / 'x'
        fresh.mkdir(parents=True)
        (fresh / 'launch.json').write_text('{not json', encoding='utf-8')   # never read: it would be unable
        verdict, evidence = soc.check_image(self.fx.ctx())
        self.assertEqual(verdict, 'kept', evidence)
        self.assertIn('14 us-east-1 launches', evidence)
        self.assertIn('1 outside us-east-1 not covered', evidence)
        up = dict(uploaded=True)
        launch_folder(root, 'upload', AFTER + timedelta(minutes=5), {'declared': False, 'state': None}, **up)
        launch_folder(root, 'probe_failed', AFTER + timedelta(minutes=6), {'declared': True, 'state': None}, **up)
        launch_folder(root, 'unused', AFTER + timedelta(minutes=7), {'declared': True, 'state': 'MATCH', 'used': False}, **up)
        launch_folder(root, 'free_text', AFTER + timedelta(minutes=8), {'declared': False, 'upload_reason': 'faster'}, **up)
        # a fallback is kept only as the controller records it
        launch_folder(root, 'mismatch_unmarked', AFTER + timedelta(minutes=9),
                      {'declared': True, 'state': 'MISMATCH', 'used': False}, **up)
        launch_folder(root, 'timeout_undeclared', AFTER + timedelta(minutes=11), {'declared': False, 'state': 'PROBE_TIMEOUT'},
                      **up)
        verdict, evidence = soc.check_image(self.fx.ctx())
        self.assertEqual(verdict, 'broken')
        bad = ' '.join(soc.judge_launches(self.fx.ctx(), soc.image_launches(root))[0])   # the evidence shows six
        evidence = evidence + ' ' + bad
        for name in ('upload', 'probe_failed', 'unused', 'free_text', 'mismatch_unmarked', 'timeout_undeclared'):
            self.assertIn('external/' + name, evidence)
        for name in ('probe_timeout', 'after_timeout', 'fallback_', '00_entry', 'ended_before_probe', 'seed_failed',
                     'seed_never_reached'):
            self.assertNotIn(name, evidence)
        self.assertIn('6 of 20 us-east-1 launches', evidence)
        self.fx.write('STANDING_ORDERS.md', HEAD + order(1, 'image', 'script: receipts') + order(2, 'two', 'record: r'))
        out = io.StringIO()
        with patch('sys.stdout', out):
            code = soc.main(['--root', str(root), '--private', str(self.fx.private), '--loop-ref', LOOP, '--only', '1'])
        self.assertEqual(code, 1)
        self.assertIn('order 1 BROKEN', out.getvalue())
        self.assertNotIn('order 2', out.getvalue())
        self.assertFalse((self.fx.private / soc.LAST).exists())
        refusals = soc.launch_refusals(self.fx.ctx(), numbers=(1,))
        self.assertEqual([(n, s) for n, s, _ in refusals], [(1, 'broken')])

    def test_api_key_runs_need_one_evet_one_chain_and_a_rule_key(self):
        fx = self.fx
        fx.write('FOR_SECKIN.md', '# For Seckin\n\n## 2026-11-09 19:00 +0300: SORU: paid run\n\nSeckin: evet (19:05)\n\n'
                                  '## 2026-11-09 19:10 +0300: another\n\nno answer\n')
        names = {'SHIMMER_CONFIG_PATH'}
        line = lambda run, heading, key='SHIMMER_CONFIG_PATH', chain=(): json.dumps(
            {'event': 'close', 'run_id': run, 'time_utc': AFTER.isoformat(), 'key_source': key,
             'seckin_approved_heading': heading, 'chain_run_ids_before': list(chain)})
        old = json.dumps({'complete': True, 'run_id': 'pre', 'time_utc': '2026-11-09T09:08:00+00:00'})
        good = '## 2026-11-09 19:00 +0300: SORU: paid run'
        fx.write('cloud_reference_spend.jsonl', '\n'.join([old, line('r1', good), line('r2', good, chain=['r1'])]))
        self.assertEqual(state(soc.check_api_key(fx.ctx(), names)), 'kept')
        ledger_lines = [json.dumps({'event': kind, 'time_utc': AFTER.isoformat(), 'cap_usd': 60}) for kind in
                        ('ceiling', 'reserve', 'skipped')]
        fx.write('cloud_reference_spend.jsonl', '\n'.join([old, line('r1', good)] + ledger_lines))
        self.assertEqual(state(soc.check_api_key(fx.ctx(), names)), 'kept')   # not runs: no heading needed
        fx.write('cloud_reference_spend.jsonl', '\n'.join([old, line('r1', good), line('r6', '')] + ledger_lines))
        self.assertEqual(state(soc.check_api_key(fx.ctx(), names)), 'broken')   # a close with no heading
        for bad in (line('r3', good), line('r4', '## 2026-11-09 19:10 +0300: another'), line('r5', good, key='env var')):
            fx.write('cloud_reference_spend.jsonl', '\n'.join([old, line('r1', good), bad]))
            self.assertFalse(soc.check_api_key(fx.ctx(), names)[0], bad)

    def test_budget_marks(self):
        fx = self.fx
        budget = lambda b, h, w=270: json.dumps(dict({'event': 'budget_change', 'budget_usd': b, 'hard_stop_usd': h,
                                                      'time_utc': '2026-11-09T14:30:00+00:00'},
                                                     **({'warning_usd': w} if w is not None else {})))
        fx.write('cloud_reference_spend.jsonl', json.dumps({'event': 'ceiling', 'time_utc': '2026-11-09T20:00:00+00:00',
                                                            'ceiling_usd': 60, 'warning_usd': 50}) + '\n')
        status = lambda spend, when=None, error=None: fx.write('reaper_status.json', json.dumps(
            {'total_spend_usd': spend, 'last_run_utc': (when or datetime.now(timezone.utc)).isoformat(), 'error': error}))
        fx.write('budget_ledger.jsonl', budget(300, 299) + '\n')
        fx.write('FOR_SECKIN.md', '# For Seckin\n')
        status(100)
        verdict, evidence = soc.check_budget(fx.ctx())
        self.assertEqual(state((verdict, evidence)), 'kept')
        self.assertIn('budget 300', evidence)
        self.assertIn('warning 270', evidence)
        fx.write('budget_ledger.jsonl', budget(300, 299, None) + '\n')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'unable')   # no warning_usd: never a code 270
        fx.write('budget_ledger.jsonl', budget(500, 499, 450) + '\n')
        status(280)
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'kept')     # the line's 450, not 270
        fx.write('budget_ledger.jsonl', budget(300, 299) + '\n')
        fx.write('budget_ledger.jsonl', json.dumps({'event': 'launch'}) + '\n')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'broken')   # no budget line the reaper can read
        fx.write('budget_ledger.jsonl', budget(300, 299) + '\n')
        status(100, error='ConnectionError')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'unable')
        status(280, datetime.now(timezone.utc) - timedelta(hours=1))
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'unable')   # a stale reading
        status(280)
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'broken')
        fx.write('FOR_SECKIN.md', '# For Seckin\n\n## 2026-11-09 19:00 +0300: D-270 is about something else\n')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'broken')   # a heading alone is not the warning
        warning = ('## 2026-11-09 19:00 +0300: UYARI: Lambda harcaması 270 USD\n\nHarcama 280.10 USD; 300 USD olunca '
                   'durur.\n')
        fx.write('FOR_SECKIN.md', '# For Seckin\n\n' + warning)
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'kept')
        status(310)
        crossed = '## 2026-11-09 20:00 +0300: 300 doları geçtik\n'
        fx.write('FOR_SECKIN.md', '# For Seckin\n\n' + warning + '\n' + crossed)
        intent = lambda when=None: json.dumps(dict({'event': 'launch_intent'}, **({'time_utc': when} if when else {})))
        fx.write('budget_ledger.jsonl', budget(300, 299) + '\n' + intent('2026-11-09T16:00:00+00:00') + '\n')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'kept')     # the intent came before the crossing
        fx.write('budget_ledger.jsonl', budget(300, 299) + '\n' + intent('2026-11-09T18:00:00+00:00') + '\n')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'broken')
        fx.write('budget_ledger.jsonl', budget(300, 299) + '\n' + intent() + '\n')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'broken')   # an untimed intent counts as after
        fx.write('FOR_SECKIN.md', '# For Seckin\n\n' + warning + '\n' + crossed + '\nSeckin: devam (20:10)\n')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'kept')     # his answer stands under the heading

    def test_budget_line_fields_cover_the_real_lines(self):
        """D-464 item 3: every field the loop's budget lines carry (named here from the lines as written
        on 9 November) is declared, so the reaper's status names none as unknown."""
        carried = ('a10_price_source', 'a10_reference_price_usd_per_hour', 'allocations_usd', 'budget_usd', 'event',
                   'five_hour_usage_launch_limit_percent', 'hard_stop_usd', 'loop_start_utc', 'orphans',
                   'previous_budget_usd', 'previous_hard_stop_usd', 'running_instances_at_open',
                   'seven_day_usage_launch_limit_percent', 'source', 'storage_forecast_days', 'storage_forecast_usd',
                   'storage_usd_per_day', 'time_utc', 'usage_five_hour', 'usage_seven_day', 'warning_usd')
        self.assertEqual(sorted(set(carried) - set(instance_reaper.BUDGET_LINE_FIELDS)), [])

    def test_a_salvage_entry_is_never_lost(self):
        """D-468: the salvage entry goes to FOR_SECKIN under the same lock; while the lock is held it
        is retried, then written to the episode's own fallback file, never dropped."""
        import os
        fx = self.fx
        target = fx.private / 'FOR_SECKIN.md'
        lock = fx.private / 'FOR_SECKIN.md.lock'
        episode = fx.private / 'salvage' / 'ep1'
        fx.write('FOR_SECKIN.md', '# For Seckin\n\n## older\n')
        waits = []
        entry = '## 2026-11-10 01:30 UTC Salvage and stop (D-S84): 1 loop instance(s) stopped\n'
        with patch.object(instance_reaper, 'FOR_SECKIN', target):
            self.assertEqual(instance_reaper.note_salvage(entry, episode, sleep=waits.append), 'for_seckin')
            self.assertTrue(target.read_text(encoding='utf-8').startswith('# For Seckin\n\n## 2026-11-10 01:30'))
            self.assertFalse(lock.exists())
            lock.write_text('{}', encoding='utf-8')   # another writer holds it throughout
            where = instance_reaper.note_salvage(entry, episode, sleep=waits.append)
        self.assertEqual(Path(where), episode / instance_reaper.SALVAGE_NOTE_FALLBACK)
        self.assertEqual(Path(where).read_text(encoding='utf-8'), entry + '\n')
        self.assertEqual(len(waits), 4)   # five tries, four waits between them, before the fallback
        self.assertEqual(target.read_text(encoding='utf-8').count('Salvage and stop'), 1)
        self.assertIn('note_salvage(entry, folder)', Path(instance_reaper.__file__).read_text(encoding='utf-8'))

    def test_for_seckin_written_under_its_lock_by_a_move(self):
        """D-467 item 3: the reaper writes FOR_SECKIN only under its lock, by one move; a held lock
        writes nothing (the next pass retries), a stale one is replaced, and the lock is released."""
        import os
        fx = self.fx
        target = fx.private / 'FOR_SECKIN.md'
        lock = fx.private / 'FOR_SECKIN.md.lock'
        fx.write('FOR_SECKIN.md', '# For Seckin\n\n## 2026-11-09 19:00 +0300: older\n')
        entry = lambda old: ['## 2026-11-10 01:00 +0300 new\n']
        moves = []
        real_replace = os.replace
        with patch.object(instance_reaper, 'FOR_SECKIN', target), \
                patch.object(instance_reaper.os, 'replace', lambda a, b: (moves.append((Path(a).name, Path(b).name)),
                                                                          real_replace(a, b))[1]):
            lock.write_text('{}', encoding='utf-8')
            with self.assertRaises(instance_reaper.ForSeckinLocked):
                instance_reaper.put_on_top(entry)
            self.assertNotIn('new', target.read_text(encoding='utf-8'))
            os.utime(lock, (0, 0))   # a lock left by a dead writer
            self.assertEqual(instance_reaper.put_on_top(entry), ['## 2026-11-10 01:00 +0300 new\n'])
        text = target.read_text(encoding='utf-8')
        self.assertTrue(text.startswith('# For Seckin\n\n## 2026-11-10 01:00 +0300 new'))
        self.assertIn('older', text)
        self.assertFalse(lock.exists())
        self.assertEqual(moves, [('FOR_SECKIN.md.%d.tmp' % os.getpid(), 'FOR_SECKIN.md')])
        self.assertEqual(sorted(p.name for p in fx.private.glob('FOR_SECKIN.md.*')), [])
        def refused(a, b):
            raise PermissionError('the file is open elsewhere')
        with patch.object(instance_reaper, 'FOR_SECKIN', target), patch.object(instance_reaper.os, 'replace', refused):
            with self.assertRaises(PermissionError):
                instance_reaper.put_on_top(entry)
        self.assertEqual(sorted(p.name for p in fx.private.glob('FOR_SECKIN.md.*')), [])   # no tmp, no lock left
        self.assertEqual(target.read_text(encoding='utf-8'), text)

    def test_budget_reads_both_ceilings_and_the_reaper_writes_both_warnings(self):
        """D-S121, D-464 items 3 and 4: Lambda 300 / 299 / 270 from the budget line, the API 60 / 50 from
        the store's ceiling line; at each warning the reaper's pass writes one FOR_SECKIN entry, once,
        in the form order 3 reads, and order 3 then holds."""
        fx = self.fx
        now = datetime.now(timezone.utc)
        fx.write('budget_ledger.jsonl', json.dumps({'event': 'budget_change', 'budget_usd': 300, 'hard_stop_usd': 299,
                                                    'warning_usd': 270, 'time_utc': '2026-11-09T14:30:00+00:00'}) + '\n')
        store = fx.private / 'cloud_reference_spend.jsonl'
        ceiling = json.dumps({'event': 'ceiling', 'time_utc': '2026-11-09T20:00:00+00:00', 'ceiling_usd': 60,
                              'warning_usd': 50})
        spent = lambda usd: json.dumps({'event': 'close', 'run_id': 'r%d' % usd, 'spent_usd': usd,
                                        'time_utc': '2026-11-09T21:00:00+00:00'})
        fx.write('FOR_SECKIN.md', '# For Seckin\n\n## 2026-11-09 19:00 +0300: an older entry\n')
        status = {'total_spend_usd': 100.0, 'budget_usd': 300.0, 'warning_usd': 270.0,
                  'last_run_utc': now.isoformat(), 'error': None}
        fx.write('reaper_status.json', json.dumps(status))
        fx.write('cloud_reference_spend.jsonl', '')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'unable')   # no ceiling line
        fx.write('cloud_reference_spend.jsonl', ceiling + '\n' + spent(52) + '\n')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'broken')   # API at 52 of 60, warning 50, no entry
        fx.write('cloud_reference_spend.jsonl', ceiling + '\n' + spent(61) + '\n')
        self.assertEqual(state(soc.check_budget(fx.ctx())), 'broken')   # past the API ceiling
        fx.write('cloud_reference_spend.jsonl', ceiling + '\n' + spent(52) + '\n')
        status['total_spend_usd'] = 280.0
        fx.write('reaper_status.json', json.dumps(status))
        with patch.object(instance_reaper, 'FOR_SECKIN', fx.private / 'FOR_SECKIN.md'):
            written = instance_reaper.note_warnings(status, store, now)
            again = instance_reaper.note_warnings(status, store, now)
        text = (fx.private / 'FOR_SECKIN.md').read_text(encoding='utf-8')
        self.assertEqual((sorted(written), again), (['API', 'Lambda'], []))
        self.assertTrue(text.startswith('# For Seckin\n\n## '))
        self.assertIn('an older entry', text)
        self.assertEqual(text.count('UYARI:'), 2)
        verdict, evidence = soc.check_budget(fx.ctx())
        self.assertEqual(state((verdict, evidence)), 'kept', evidence)
        self.assertIn('API 52.00 of 60', evidence)
        with patch.object(instance_reaper, 'FOR_SECKIN', fx.private / 'FOR_SECKIN.md'):
            fx.write('FOR_SECKIN.md', '# For Seckin\n')
            status['total_spend_usd'] = 100.0
            fx.write('cloud_reference_spend.jsonl', ceiling + '\n' + spent(10) + '\n')
            self.assertEqual(instance_reaper.note_warnings(status, store, now), [])   # below both warnings

    def test_the_fresh_read_waits_for_a_passing_row(self):
        fx = self.fx
        self.assertEqual(state(soc.check_fresh_read(fx.ctx())), 'nothing_yet')
        before = (datetime.now(timezone.utc) - timedelta(hours=2)).astimezone(timezone(timedelta(hours=3)))
        after = (datetime.now(timezone.utc) + timedelta(hours=2)).astimezone(timezone(timedelta(hours=3)))
        line = lambda when, gap: SCOREBOARD_HEAD + '| r1 | %s | binary judgment accuracy | 2 classes | 60 [50, 70] | %s |\n' % (
            when.strftime('%Y-%m-%d %H:%M'), gap)
        fx.commit('docs/loop/FRESH_ATTEMPTS.json', json.dumps({'attempts': [{'attempt': 1}]}))
        fx.write('GATE_SCOREBOARD.md', line(before, '3 / 4'))
        self.assertEqual(state(soc.check_fresh_read(fx.ctx())), 'broken')
        fx.write('GATE_SCOREBOARD.md', line(after, 'passed'))
        self.assertEqual(state(soc.check_fresh_read(fx.ctx())), 'broken')   # passed only after the read
        fx.write('GATE_SCOREBOARD.md', line(before, 'passed'))
        self.assertEqual(state(soc.check_fresh_read(fx.ctx())), 'kept')

    def test_scoreboard_rows_name_metric_setting_and_interval(self):
        fx = self.fx
        fx.write('GATE_SCOREBOARD.md', SCOREBOARD_HEAD + '| (none yet) | | | | | |\n')
        self.assertEqual(state(soc.check_metric(fx.ctx())), 'nothing_yet')
        fx.write('GATE_SCOREBOARD.md', SCOREBOARD_HEAD + '| r1 | 2026-11-09 19:00 | macro-F1 | 3 classes | 61.2 [55.0, 67.1] | x |\n')
        self.assertEqual(state(soc.check_metric(fx.ctx())), 'kept')
        fx.write('GATE_SCOREBOARD.md', SCOREBOARD_HEAD + '| r2 | 2026-11-09 19:00 | accuracy | 3 classes | 61.2 [55.0, 67.1] | x |\n')
        self.assertEqual(state(soc.check_metric(fx.ctx())), 'broken')
        fx.write('GATE_SCOREBOARD.md', SCOREBOARD_HEAD + '| r3 | 2026-11-09 19:00 | macro-F1 | | 61.2 | x |\n')
        self.assertEqual(state(soc.check_metric(fx.ctx())), 'broken')

    def test_the_page_follows_the_newest_row(self):
        fx = self.fx
        origin = Path(self.folder.name) / 'origin.git'
        _git(fx.root, 'init', '-q', '--bare', str(origin))
        _git(fx.root, 'remote', 'add', 'origin', str(origin))
        fx.commit('docs/progress/index.html', '<html></html>\n')
        _git(fx.root, 'push', '-q', 'origin', '%s:refs/heads/main' % LOOP)
        _git(fx.root, 'fetch', '-q', 'origin', 'main')
        pushed = datetime.fromisoformat(_git(fx.root, 'log', '-1', '--format=%cI', 'refs/remotes/origin/main'))
        row = lambda t: SCOREBOARD_HEAD + '| r1 | %s | macro-F1 | 3 classes | 61 [55, 67] | x |\n' % t.strftime('%Y-%m-%d %H:%M')
        local = pushed.astimezone(timezone(timedelta(hours=3)))
        fx.write('GATE_SCOREBOARD.md', row(local - timedelta(hours=1)))
        self.assertEqual(state(soc.check_page(fx.ctx())), 'kept')
        fx.write('GATE_SCOREBOARD.md', row(local + timedelta(hours=1)))
        self.assertEqual(state(soc.check_page(fx.ctx())), 'broken')

    def test_no_key_shaped_value_on_the_loop_branch(self):
        fx = self.fx
        self.assertEqual(state(soc.check_keys(fx.ctx())), 'kept')
        fx.commit('tools/conf.py', 'api' + '_key = "' + 'x' * 20 + '"\n')  # built here, never written in this file
        self.assertEqual(state(soc.check_keys(fx.ctx())), 'broken')

    def test_keys_since_the_last_check_merges_included_by_guard_secrets_rules(self):
        fx = self.fx
        fx.commit('tools/old.py', 'api' + '_key = "' + 'y' * 20 + '"\n')
        head = _git(fx.root, 'rev-parse', LOOP)
        fx.write(soc.LAST, json.dumps({'loop_head': head}))
        ctx = fx.ctx()
        self.assertEqual(state(soc.check_keys(ctx)), 'kept')   # before the last check's head
        self.assertEqual(ctx.notes['loop_head'], head)
        _git(fx.root, 'checkout', '-q', '-b', 'lane/x')
        fx.commit('tools/lane.py', 'value = "FIXTURE-REFUSED-VALUE"\n')
        _git(fx.root, 'checkout', '-q', LOOP)
        _git(fx.root, 'merge', '-q', '--no-ff', '-m', 'merge lane/x', 'lane/x')
        kept, evidence = soc.check_keys(fx.ctx())
        self.assertEqual(kept, False)
        self.assertIn('tools/lane.py', evidence)
        fx.write(soc.LAST, json.dumps({'loop_head': _git(fx.root, 'rev-parse', LOOP)}))
        fx.commit('run/audit/model_replies/r.json', '{}\n')
        kept, evidence = soc.check_keys(fx.ctx())
        self.assertEqual(kept, False)
        self.assertIn('a path guard_secrets refuses', evidence)

    def test_heldout_openings_are_at_their_alpha(self):
        fx = self.fx
        head = '| Part | k | Alpha | Tuning pass record (commit) |\n|---|---|---|---|\n'
        fx.commit('docs/loop/HELDOUT_OPENINGS.md', head + '| judge | 2 | 0.0125 | %s |\n' % fx.first)
        self.assertEqual(state(soc.check_heldout(fx.ctx())), 'kept')
        fx.commit('docs/loop/HELDOUT_OPENINGS.md', head + '| judge | 2 | 0.025 | %s |\n' % fx.first)
        self.assertEqual(state(soc.check_heldout(fx.ctx())), 'broken')
        fx.commit('docs/loop/HELDOUT_OPENINGS.md', head + '| judge | 1 | 0.025 | not a commit |\n')
        self.assertEqual(state(soc.check_heldout(fx.ctx())), 'broken')

    def test_free_disk_floor(self):
        usage = namedtuple('usage', 'total used free')
        with patch.object(soc.shutil, 'disk_usage', lambda p: usage(0, 0, 40 * 2 ** 30)):
            self.assertEqual(state(soc.check_disk(self.fx.ctx())), 'kept')
        with patch.object(soc.shutil, 'disk_usage', lambda p: usage(0, 0, 20 * 2 ** 30)):
            self.assertEqual(state(soc.check_disk(self.fx.ctx())), 'broken')

    def test_states_follow_the_status_check(self):
        done = lambda code: (lambda *a, **k: type('R', (), {'returncode': code, 'stdout': 'claims 1: X\n'})())
        with patch.object(soc.subprocess, 'run', done(0)):
            self.assertEqual(state(soc.check_states(self.fx.ctx())), 'kept')
        with patch.object(soc.subprocess, 'run', done(1)):
            self.assertEqual(state(soc.check_states(self.fx.ctx())), 'broken')

    def test_the_reaper_runs_and_the_sign_out_task_runs_the_main_hook(self):
        fx = self.fx
        hook = fx.root / 'tools' / 'loop' / 'session_end_salvage.py'
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text('# hook\n', encoding='utf-8')
        other = fx.root.parent / 'lane' / 'session_end_salvage.py'
        other.parent.mkdir(parents=True, exist_ok=True)
        other.write_text('# hook\n', encoding='utf-8')
        fresh = datetime.now(timezone.utc).isoformat()
        (fx.private / 'reaper_status.json').write_text(json.dumps({'last_run_utc': fresh, 'error': None}), encoding='utf-8')
        task = lambda script: (lambda name: '<Task><Exec><Arguments>-X utf8 "%s" --event-id $(eventId)</Arguments>'
                                            '</Exec></Task>' % script)
        with patch.object(soc, 'schtasks_xml', task(hook)):
            self.assertEqual(state(soc.check_salvage_tasks(fx.ctx())), 'kept')
        with patch.object(soc, 'schtasks_xml', task(other)):
            self.assertEqual(state(soc.check_salvage_tasks(fx.ctx())), 'broken')
        with patch.object(soc, 'schtasks_xml', task(fx.root / 'gone.py')):
            self.assertEqual(state(soc.check_salvage_tasks(fx.ctx())), 'broken')
        with patch.object(soc, 'schtasks_xml', lambda name: None if name == soc.SESSION_TASK else '<Task/>'):
            self.assertEqual(state(soc.check_salvage_tasks(fx.ctx())), 'broken')
        old = (datetime.now(timezone.utc) - timedelta(minutes=40)).isoformat()
        (fx.private / 'reaper_status.json').write_text(json.dumps({'last_run_utc': old, 'error': None}), encoding='utf-8')
        with patch.object(soc, 'schtasks_xml', task(hook)):
            self.assertEqual(state(soc.check_salvage_tasks(fx.ctx())), 'broken')

    # the run, the command line and the session-start block

    def test_the_run_writes_its_result_and_the_session_start_prints_it(self):
        fx = self.fx
        fx.write('STANDING_ORDERS.md', '# Standing orders\n\n' + HEAD + order(1, '[public] one', 'record: a') +
                 order(2, 'two', 'broken today: b') + order(3, '(withdrawn, D-1)', 'none'))
        self.assertIn('No standing-orders check result yet', session_start.standing_orders_block(fx.private))
        out = io.StringIO()
        with patch('sys.stdout', out):
            code = soc.main(['--root', str(fx.root), '--private', str(fx.private), '--loop-ref', LOOP])
        self.assertEqual(code, 1)
        self.assertIn('standing orders: 0 kept, 0 kept in part, 0 code proven, not the order, 0 nothing to check yet, '
                      '1 broken, 0 check not built, 0 unable to check, 1 not checked by code, 1 withdrawn, 0 unreadable: '
                      'FAIL', out.getvalue())
        saved = json.loads((fx.private / soc.LAST).read_text(encoding='utf-8'))
        page = [(o['n'], o['public'], o['text'], o['proof'], o['page_state']) for o in saved['orders']]
        self.assertEqual(page, [(1, True, 'one', 'record', 'not_checked'), (2, False, 'two', 'broken today', 'broken'),
                                (3, False, '(withdrawn, D-1)', 'none', 'withdrawn')])
        self.assertEqual(saved['checked_utc'], saved['time_utc'])
        block = session_start.standing_orders_block(fx.private)
        self.assertIn('1. [public] one', block)
        self.assertIn('2. two', block)
        self.assertIn('0 kept, 0 kept in part', block)
        self.assertIn('1 broken', block)
        self.assertIn('order 2 BROKEN', block)
        self.assertNotIn('STALE', block)
        fx.write('STANDING_ORDERS.md', '# Standing orders\n\n' + HEAD + order(1, '[public] one', 'record: changed'))
        self.assertIn('the tablet changed', session_start.standing_orders_block(fx.private))
        saved['time_utc'] = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        self.assertTrue(any('hours old' in r for r in session_start.stale_reasons(saved, '')))

    def test_a_script_not_built_yet_is_not_built_and_never_blocks(self):
        orders, problems = soc.parse_tablet(HEAD + order(57, 'snapshot', 'script (to build): a run names its snapshot'))
        self.assertEqual(problems, [])
        verdict, evidence = soc.judge(orders[0], self.fx.ctx(), lambda numbers: {})
        self.assertEqual(verdict, 'not_built')
        self.assertTrue(soc.run(self.fx.ctx(), HEAD + order(57, 'snapshot', 'script (to build): x'))['ok'])

    def test_a_suspension_must_quote_its_reading_and_time(self):
        fx = self.fx
        tablet = HEAD + order(14, 'Free disk', 'record: the disk') + order(15, 'Other', 'record: r')
        base = '# Decisions\n\n## D-001. One\n\n- **Narrows.** order 14 to 20 GB: %s\n'
        fx.commit('docs/loop/DECISIONS.md', base % 'the disk is short')
        result = soc.run(fx.ctx(), tablet)
        self.assertEqual([o['state'] for o in result['orders']], ['broken', 'unchecked'])
        self.assertIn('D-001', result['orders'][0]['line'])
        for half in ('read "free 11.9 GiB" from check_disk', 'read at 22:11 from check_disk'):
            fx.commit('docs/loop/DECISIONS.md', base % half)
            self.assertEqual(soc.run(fx.ctx(), tablet)['orders'][0]['state'], 'broken', half)
        fx.commit('docs/loop/DECISIONS.md', base % 'read "free 11.9 GiB" at 22:11 from check_disk')
        self.assertEqual([o['state'] for o in soc.run(fx.ctx(), tablet)['orders']], ['unchecked', 'unchecked'])

    def test_partial_and_code_proven_orders_are_labelled(self):
        ctx = self.fx.ctx()
        for number, expected in ((24, 'kept_in_part'), (50, 'kept_in_part'), (23, 'code_only'), (26, 'code_only'),
                                 (52, 'code_only')):
            o = {'number': number, 'order': 'x', 'proof': 'script: gate check 174', 'kind': 'script'}
            self.assertEqual(soc.judge(o, ctx, gate_runner=lambda n: {k: 'PASS' for k in n})[0], expected, number)
        with patch.dict(soc.CHECKERS, {19: ('machine type', lambda ctx: (True, 'factor_record_checks: PASS'))}):
            o = {'number': 19, 'order': 'One machine type per compared figure', 'proof': 'script: x', 'kind': 'script'}
            self.assertEqual(soc.judge(o, ctx)[0], 'code_only')
        o = {'number': 77, 'order': 'x', 'proof': 'script: gate check 174', 'kind': 'script'}
        self.assertEqual(soc.judge(o, ctx, gate_runner=lambda n: {k: 'PASS' for k in n})[0], 'kept')

    def test_the_ledger_orders_run_the_ledger_tools(self):
        fx = self.fx
        calls = []

        def tool(ctx, script, extra=()):
            calls.append(script)
            return tool.codes[script], '%s: last line' % script
        tool.codes = {'request_ledger_check.py': 0, 'issue_deferral_check.py': 0}
        with patch.object(soc, '_ledger_tool', tool):
            self.assertEqual(state(soc.check_ledger(fx.ctx())), 'unable')   # no saved issue list
            fx.write(soc.ISSUES_FILE, '[]')
            self.assertEqual(state(soc.check_ledger(fx.ctx())), 'kept')
            self.assertEqual(state(soc.check_deferral_issues(fx.ctx())), 'kept_in_part')
            tool.codes['issue_deferral_check.py'] = 1
            self.assertEqual(state(soc.check_ledger(fx.ctx())), 'broken')
            self.assertEqual(state(soc.check_deferral_issues(fx.ctx())), 'broken')
        last = {'code': 1, 'line': 'specification items 9, ledger rows 9, missing 0, unmatched 0: FAIL'}
        with patch.object(soc, '_ledger_tool', lambda ctx, script, extra=(): (last['code'], last['line'])):
            self.assertEqual(state(soc.check_ledger_rows(fx.ctx())), 'kept_in_part')
            last['line'] = 'specification items 9, ledger rows 8, missing 1, unmatched 0: FAIL'
            self.assertEqual(state(soc.check_ledger_rows(fx.ctx())), 'broken')
        self.assertIn('request_ledger_check.py', calls)

    def test_unable_to_check_blocks_only_orders_1_to_3(self):
        def raises(ctx):
            raise OSError('unreadable')
        with patch.dict(soc.CHECKERS, {3: ('Budget', raises), 14: ('disk', raises)}):
            three = soc.run(self.fx.ctx(), HEAD + order(3, 'Budget 500', 'script: ledger'))
            fourteen = soc.run(self.fx.ctx(), HEAD + order(14, 'Free disk', 'script: disk'))
        self.assertEqual(three['orders'][0]['state'], 'unable')
        self.assertFalse(three['ok'])
        self.assertEqual(fourteen['orders'][0]['state'], 'unable')
        self.assertTrue(fourteen['ok'])

    def test_order_1_from_the_launch_checks_landing_with_the_history_once(self):
        fx = self.fx
        root = fx.root
        upload = {'declared': False, 'state': None}
        launch_folder(root, 'before', AFTER, upload, uploaded=True)
        self.assertEqual(state(soc.check_image(fx.ctx())), 'broken')   # not landed: every launch since 5 Nov
        fx.commit(soc.LAUNCH_CHECK, '# the records check\n')
        ctx = fx.ctx()
        verdict, evidence = soc.check_image(ctx)
        self.assertEqual(verdict, 'nothing_yet')
        self.assertIn('history since 5 Nov, reported once: 1 of 1', evidence)
        self.assertEqual(soc.launch_refusals(ctx, numbers=(1,)), [])        # the history never blocks
        fx.write(soc.LAST, json.dumps({'order1_history_reported': ctx.notes['order1_history_reported']}))
        verdict, evidence = soc.check_image(fx.ctx())
        self.assertIn('was reported at', evidence)
        later = datetime.now(timezone.utc) + timedelta(hours=1)
        launch_folder(root, 'after_copy', later, {'declared': True, 'state': 'MATCH', 'used': True})
        self.assertEqual(state(soc.check_image(fx.ctx())), 'kept')
        launch_folder(root, 'after', later + timedelta(minutes=1), upload, uploaded=True)
        self.assertEqual(state(soc.check_image(fx.ctx())), 'broken')
        bad = root / 'external' / 'broken_record'
        bad.mkdir()
        (bad / 'launch.json').write_text('{not json', encoding='utf-8')
        self.assertEqual(state(soc.check_image(fx.ctx())), 'unable')



NEVER = lambda ctx, *a: (True, 'neutralised')
NEUTRALISED = (
    (soc, 'KINDS', ('script', 'record', 'broken today', 'maybe'), ('test_the_tablet_is_read_and_an_unreadable_row_fails',)),
    (soc, 'CHECKERS', {n: ('', f) for n, (_, f) in soc.CHECKERS.items()}, ('test_a_checker_bound_to_a_renumbered_order_fails',)),
    (soc, 'gate_numbers', lambda proof: [], ('test_gate_checks_named_in_a_proof_are_run',)),
    (soc, 'GATE_CHECK', re.compile(r'\bchecks?\s+(\d{1,3})(?:\s*(?:,|and)\s*(\d{1,3}))*'),
     ('test_gate_checks_named_in_a_proof_are_run',)),
    (soc, 'unquoted_suspensions', lambda ctx: {}, ('test_a_suspension_must_quote_its_reading_and_time',)),
    (soc, 'QUOTED', re.compile('.'), ('test_a_suspension_must_quote_its_reading_and_time',)),
    (soc, 'READ_TIME', re.compile('.'), ('test_a_suspension_must_quote_its_reading_and_time',)),
    (soc, 'BLOCKING_UNABLE', frozenset(), ('test_unable_to_check_blocks_only_orders_1_to_3',)),
    (soc, 'blocks', lambda number, state: state in ('broken', 'not_built', 'unable'),
     ('test_unable_to_check_blocks_only_orders_1_to_3', 'test_a_script_not_built_yet_is_not_built_and_never_blocks')),
    (soc, 'launch_check_landing', lambda ctx: None, ('test_order_1_from_the_launch_checks_landing_with_the_history_once',)),
    (soc, 'SKIP_DIRS', (), ('test_image_every_east_launch_since_5_november_starts_from_the_copy',)),
    (soc, 'RECEIPT_UPLOAD_REASONS', ('another region', 'sealed run', 'seed of a missing digest', 'faster'),
     ('test_image_every_east_launch_since_5_november_starts_from_the_copy',)),
    (soc, 'answered', lambda lines, heading: True, ('test_budget_marks',)),
    (soc, 'budget_figures', lambda rows: (500.0, 499.0), ('test_budget_marks',)),
    (soc, 'first_commit_time', lambda ctx, paths: datetime.now(timezone.utc) + timedelta(days=1),
     ('test_the_fresh_read_waits_for_a_passing_row',)),
    (soc, 'PARTIAL', {}, ('test_partial_and_code_proven_orders_are_labelled',)),
    (soc, 'check_ledger', NEVER, ('test_the_ledger_orders_run_the_ledger_tools',)),
    (soc, 'check_ledger_rows', NEVER, ('test_the_ledger_orders_run_the_ledger_tools',)),
    (soc, 'check_deferral_issues', NEVER, ('test_the_ledger_orders_run_the_ledger_tools',)),
    (soc, 'launch_refusals', lambda ctx, numbers=(1, 2, 3): [],
     ('test_image_every_east_launch_since_5_november_starts_from_the_copy',)),
    (soc, 'warning_entries', lambda lines, warning, stop, kind=None: [l for l in lines if l.startswith('## ')
                                                                       and soc._names(l, warning)],
     ('test_budget_marks',)),
    (soc, 'uploaded', lambda folder: True, ('test_image_every_east_launch_since_5_november_starts_from_the_copy',)),
    (instance_reaper, 'FOR_SECKIN_LOCK_STALE_SECONDS', 10 ** 12, ('test_for_seckin_written_under_its_lock_by_a_move',)),
    (instance_reaper, 'put_on_top', lambda entries_for: (lambda old: (Path(instance_reaper.FOR_SECKIN).write_text(
        chr(10).join(entries_for(old)) + old, encoding='utf-8'), entries_for(old))[1])(
        Path(instance_reaper.FOR_SECKIN).read_text(encoding='utf-8')), ('test_for_seckin_written_under_its_lock_by_a_move',)),
    (instance_reaper, 'SALVAGE_NOTE_ATTEMPTS', 1, ('test_a_salvage_entry_is_never_lost',)),
    (instance_reaper, 'note_salvage', lambda entry, folder, sleep=None: 'for_seckin', ('test_a_salvage_entry_is_never_lost',)),
    (soc, 'RECEIPT_FALLBACK_STATES', (), ('test_image_every_east_launch_since_5_november_starts_from_the_copy',)),
    (soc, 'fallback_recorded', lambda receipt: receipt.get('state') in ('MISMATCH', 'MISSING', 'PROBE_TIMEOUT'), ('test_image_every_east_launch_since_5_november_starts_from_the_copy',)),
    (soc, 'warning_figure', lambda rows: 270.0, ('test_budget_marks',)),
    (soc, 'api_budget', lambda ctx, seckin: (True, 'API 52.00 of 60'), ('test_budget_reads_both_ceilings_and_the_reaper_writes_both_warnings',)),
    (instance_reaper, 'note_warnings', lambda status, store, now: ['API', 'Lambda'], ('test_budget_reads_both_ceilings_and_the_reaper_writes_both_warnings',)),
    (instance_reaper, 'warnings_due', lambda status, store: [], ('test_budget_reads_both_ceilings_and_the_reaper_writes_both_warnings',)),
    (instance_reaper, 'BUDGET_LINE_FIELDS', instance_reaper.BUDGET_LINE_FIELDS[:9], ('test_budget_line_fields_cover_the_real_lines',)),
    (soc, 'REAPER_STALE_MINUTES', 10 ** 6, ('test_budget_marks',)),
    (soc, 'guard_rules', lambda ctx: ((lambda line: []), (lambda name: False)),
     ('test_keys_since_the_last_check_merges_included_by_guard_secrets_rules',)),
    (soc, 'key_span', lambda ctx: (['--since=24.hours', ctx.loop_ref], 'in the last 24 hours'),
     ('test_keys_since_the_last_check_merges_included_by_guard_secrets_rules',)),
    (session_start, 'stale_reasons', lambda last, text, now=None: [],
     ('test_the_run_writes_its_result_and_the_session_start_prints_it',)),
    (soc, 'check_image', NEVER, ('test_image_every_east_launch_since_5_november_starts_from_the_copy',)),
    (soc, 'check_api_key', NEVER, ('test_api_key_runs_need_one_evet_one_chain_and_a_rule_key',)),
    (soc, 'SPEND_EVENTS', (None, 'close', 'ceiling', 'reserve', 'skipped'),
     ('test_api_key_runs_need_one_evet_one_chain_and_a_rule_key',)),
    (soc, 'check_budget', NEVER, ('test_budget_marks',)),
    (soc, 'check_fresh_read', NEVER, ('test_the_fresh_read_waits_for_a_passing_row',)),
    (soc, 'check_metric', NEVER, ('test_scoreboard_rows_name_metric_setting_and_interval',)),
    (soc, 'check_page', NEVER, ('test_the_page_follows_the_newest_row',)),
    (soc, 'check_keys', NEVER, ('test_no_key_shaped_value_on_the_loop_branch',)),
    (soc, 'check_heldout', NEVER, ('test_heldout_openings_are_at_their_alpha',)),
    (soc, 'DISK_FLOOR', 0, ('test_free_disk_floor',)),
    (soc, 'check_salvage_tasks', NEVER, ('test_the_reaper_runs_and_the_sign_out_task_runs_the_main_hook',)),
    (soc, 'REAPER_STALE_MINUTES', 10 ** 6, ('test_the_reaper_runs_and_the_sign_out_task_runs_the_main_hook',)),
    (soc, 'check_states', NEVER, ('test_states_follow_the_status_check',)),
    (soc, 'KINDS', ('script', 'record', 'broken today'), ('test_a_script_not_built_yet_is_not_built_and_never_blocks',)),
    (soc, 'PUBLIC_TAG', '[private]', ('test_the_run_writes_its_result_and_the_session_start_prints_it',)),
    (session_start, 'standing_orders_block', lambda private=None: '', ('test_the_run_writes_its_result_and_the_session_start_prints_it',)),
)


def passes(*names):
    suite = unittest.TestSuite(StandingOrdersChecks(n) for n in names) if names else \
        unittest.defaultTestLoader.loadTestsFromTestCase(StandingOrdersChecks)
    return unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite).wasSuccessful()


def check():
    if shutil.which('git') is None:
        return 'SKIP', 'git is not installed here; every proof runs on a fixture git repository'
    if not passes():
        return 'FAIL', 'tools/loop/standing_orders_checks.py does not pass'
    proofs = []
    for owner, name, mutant, names in NEUTRALISED:
        with patch.object(owner, name, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        if not (failed and restored):
            return 'FAIL', '%s.%s neutralised: failed=%s, restored pass=%s' % (owner.__name__, name, failed, restored)
        proofs.append(name)
    return 'PASS', ('the standing-orders check reads the tablet (an unreadable row fails), checks every script-proven '
                    'order (the registered checkers, guarded by their order\'s text, and the gate checks a proof names), '
                    'prints record orders as not checked by code, keeps check not built, unable to check (blocking orders 1 to 3 only) '
                    'and nothing to check yet apart from broken, cuts order 1 at the launch check landing with the history '
                    'once, reads order 10 since the last check with the guard_secrets rules, the order 3 warning in its '
                    'form and the reaper freshness, fails on a broken order and writes its result, '
                    'which the session start prints with the tablet; neutralised, failed, restored, passed: '
                    + ', '.join(proofs))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
