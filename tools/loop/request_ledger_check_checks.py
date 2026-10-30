"""Proofs for tools/loop/request_ledger_check.py (loop D-S16 item 1), on fixtures in a
temporary folder: a tiny specification, ledger and DECISIONS.md, and a git repository with
one commit. Nothing private is read. `check()` runs the tests, then neutralises each of the
script's three failing rules in turn (coverage (c), evidence (d), stale RUNNING rows (e)),
requires a failure, restores it and requires a pass.

    py -3.12 -X utf8 tools/loop/request_ledger_check_checks.py
"""
from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import request_ledger_check as ledger_check  # noqa: E402
from cloud_run_common import no_window  # noqa: E402

TR = timezone(timedelta(hours=3))
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=TR)

SPEC = """# PART I. SOMETHING ELSE

| Id | Requirement | Carried by |
|---|---|---|
| X9 | A table outside Annex C is not read | nowhere |

# ANNEX C. REQUIREMENTS

| Id | Requirement | Carried by |
|---|---|---|
| R1 | First requirement | S1 |
| D1 | Second requirement | S2 |

# ANNEX D. DECISIONS

**D-S1. One request with no items.** Do it once.

**D-S2. Numbered items.** Intro text with a choice (b) that is not an item.
1. **First.** Plain item, naming group (a) only once.
2. **Second, with a lettered list.**
   a. One.
   b. Two.
3. **Third.** Show this:

```
1. a numbered line inside a code block is not an item
```

**D-S2 item 4. A later entry for one item.** It has items of its own.
1. Sub one.
2. Sub two.

**D-S3. Letters inside a sentence.**
1. **Inline.** (a) first part; (b) second part; (c) third part.

---

# ANNEX E. NOT READ

**D-S9. Never read here either?** It is an entry, so it is read.
"""

DECISIONS = """# Decisions

## D-001. The first decision

- **When, stage.** 2026-10-30 10:00 +0300.
"""

HEADER = '| Id | Request | Source | Stage | Status | Last change | Evidence or where |\n|---|---|---|---|---|---|---|\n'


def row(rid, status='DONE', evidence='D-001', last='2026-11-02T11:00+0300'):
    return '| %s | request | source | S5 | %s | %s | %s |' % (rid, status, last, evidence)


def ledger_rows(commit):
    return [
        row('C-R1'),
        row('C-D1', evidence='`%s`' % commit),
        row('D-S1', evidence='`docs/file.md` and `private_note.md`'),
        row('D-S2.1', status='RUNNING (standing)', evidence='Standing', last='2026-10-01T10:00+0300'),
        row('D-S2.2a', status='RUNNING', evidence='work in progress'),
        row('D-S2.2b', status='RUNNING', evidence='lane `lane/x` running', last='2026-10-01T10:00+0300'),
        row('D-S2.3', status='SCHEDULED', evidence='S6'),
        row('D-S2.4.1', status='SCHEDULED', evidence='S7'),
        row('D-S2.4.2', status='DEFERRED', evidence='deferral entry'),
        row('D-S3.1', status='RUNNING', evidence='L12 running', last='2026-10-01T10:00+0300'),
        row('D-S9', status='SCHEDULED', evidence='S14'),
        row('N-2026-10-30-0000', evidence='D-001'),
    ]


class Fixture:
    def __init__(self, folder):
        self.root = Path(folder) / 'repo'
        self.private = Path(folder) / 'private'
        (self.root / 'docs').mkdir(parents=True)
        self.private.mkdir()
        (self.root / 'docs' / 'file.md').write_text('x\n', encoding='utf-8')
        (self.private / 'sub').mkdir()
        (self.private / 'sub' / 'private_note.md').write_text('x\n', encoding='utf-8')
        git = ['git', '-C', str(self.root), '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
               '-c', 'commit.gpgsign=false']
        for argv in (['init', '-q'], ['add', 'docs/file.md'], ['commit', '-q', '-m', 'fixture']):
            subprocess.run(git + argv, stdin=subprocess.DEVNULL, capture_output=True, check=True,
                           creationflags=no_window())
        self.commit = subprocess.run(git + ['rev-parse', '--short=10', 'HEAD'], stdin=subprocess.DEVNULL,
                                     capture_output=True, text=True, check=True,
                                     creationflags=no_window()).stdout.strip()

    def run(self, rows):
        text = HEADER + '\n'.join(rows) + '\n'
        return ledger_check.check(SPEC, text, DECISIONS, self.root, self.private, NOW)


class RequestLedgerChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.fixture = Fixture(cls.folder.name)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def rows(self):
        return ledger_rows(self.fixture.commit)

    def assertPasses(self, rows):
        failed, lines = self.fixture.run(rows)
        self.assertFalse(failed, '\n'.join(lines))
        return lines

    def assertFailsWith(self, rows, text):
        failed, lines = self.fixture.run(rows)
        self.assertTrue(failed, '\n'.join(lines))
        self.assertTrue(any(text in line for line in lines), '%r not in:\n%s' % (text, '\n'.join(lines)))
        self.assertTrue(lines[-1].endswith('FAIL'))

    def replaced(self, rid, new):
        return [new if r.startswith('| %s |' % rid) else r for r in self.rows()]

    def test_a_items_are_read_from_the_specification(self):
        items = ledger_check.specification_items(SPEC)
        got = {i['id']: (i['subs'], i['form']) for i in items}
        self.assertEqual(got, {
            'C-R1': ([], None), 'C-D1': ([], None), 'D-S1': ([], None),
            'D-S2.1': ([], None), 'D-S2.2': (['D-S2.2a', 'D-S2.2b'], 'list'), 'D-S2.3': ([], None),
            'D-S2.4.1': ([], None), 'D-S2.4.2': ([], None),
            'D-S3.1': (['D-S3.1a', 'D-S3.1b', 'D-S3.1c'], 'inline'), 'D-S9': ([], None)})

    def test_b_f_the_fixture_ledger_passes_with_one_count_line(self):
        lines = self.assertPasses(self.rows())
        self.assertEqual(lines[-1], 'specification items 15, ledger rows 12, missing 0, unmatched 0, duplicate 0, '
                                    'unresolved evidence 0, stale running 0: PASS')
        self.assertIn('N-2026-10-30-0000', lines[1])

    def test_c_a_removed_row_fails_and_its_restoration_passes(self):
        rows = self.rows()
        for index, line in enumerate(rows):
            if line.startswith('| N-'):
                continue
            rid = line.split('|')[1].strip()
            self.assertFailsWith(rows[:index] + rows[index + 1:], rid)
        self.assertPasses(rows)

    def test_c_unmatched_and_duplicate_rows_fail_and_notes_are_exempt(self):
        self.assertFailsWith(self.rows() + [row('D-S2.5')], 'UNMATCHED (no specification item): D-S2.5')
        self.assertFailsWith(self.rows() + [row('C-X9')], 'UNMATCHED (no specification item): C-X9')
        self.assertFailsWith(self.rows() + [row('D-S1')], 'DUPLICATE id: D-S1')
        self.assertPasses(self.rows() + [row('N-2026-10-31-0000', evidence='D-001')])

    def test_c_letters_in_a_sentence_may_be_one_row_a_list_never(self):
        rows = [r for r in self.rows() if not r.startswith('| D-S3.1 |')]
        self.assertFailsWith(rows, 'D-S3.1 (or each of D-S3.1a, D-S3.1b, D-S3.1c)')
        each = [row('D-S3.1%s' % letter, status='SCHEDULED', evidence='S6') for letter in 'abc']
        self.assertPasses(rows + each)
        self.assertFailsWith(rows + each[:2], 'MISSING (no row): D-S3.1c')
        listed = [r for r in self.rows() if not r.startswith('| D-S2.2')] + [row('D-S2.2', status='SCHEDULED')]
        self.assertFailsWith(listed, 'MISSING (no row): D-S2.2a')

    def test_d_every_done_pointer_must_resolve(self):
        self.assertFailsWith(self.replaced('C-R1', row('C-R1', evidence='D-002')),
                             'UNRESOLVED C-R1: no heading "## D-002." in DECISIONS.md')
        self.assertFailsWith(self.replaced('C-D1', row('C-D1', evidence='`0123abc`')),
                             'UNRESOLVED C-D1: commit 0123abc does not exist')
        self.assertFailsWith(self.replaced('D-S1', row('D-S1', evidence='`docs/absent.md`')),
                             'UNRESOLVED D-S1: path docs/absent.md does not exist')
        self.assertFailsWith(self.replaced('D-S1', row('D-S1', evidence='`absent_note.md`')),
                             'UNRESOLVED D-S1: path absent_note.md does not exist')
        self.assertFailsWith(self.replaced('D-S1', row('D-S1', evidence='done, see the report')),
                             'UNRESOLVED D-S1: DONE without an evidence pointer')
        self.assertPasses(self.replaced('D-S1', row('D-S1', evidence='`docs/loop/private/sub/private_note.md`')))
        self.assertPasses(self.replaced('C-R1', row('C-R1', status='SCHEDULED', evidence='D-999')))

    def test_e_an_old_running_row_naming_nothing_running_is_stale(self):
        old = '2026-11-01T11:59+0300'
        self.assertFailsWith(self.replaced('D-S2.2a', row('D-S2.2a', status='RUNNING', evidence='work', last=old)),
                             'STALE RUNNING D-S2.2a')
        self.assertFailsWith(self.replaced('D-S2.2a', row('D-S2.2a', status='RUNNING', evidence='work', last='soon')),
                             'STALE RUNNING D-S2.2a: no readable Last change')
        self.assertPasses(self.replaced('D-S2.2a', row('D-S2.2a', status='RUNNING', evidence='work',
                                                      last='2026-11-01T12:01+0300')))
        for named in ('L13 running', 'lane `lane/s05-x`', 'agent install-6bc', 'C0 run 2', 'role R1', 'lane-s05'):
            self.assertPasses(self.replaced('D-S2.2a', row('D-S2.2a', status='RUNNING', evidence=named, last=old)))

    def test_cli_exit_codes(self):
        folder = Path(self.folder.name)
        spec, decisions, ledger = folder / 'spec.md', folder / 'DECISIONS.md', self.fixture.private / 'ledger.md'
        spec.write_text(SPEC, encoding='utf-8')
        decisions.write_text(DECISIONS, encoding='utf-8')
        args = ['--root', str(self.fixture.root), '--spec', str(spec), '--decisions', str(decisions),
                '--ledger', str(ledger), '--now', NOW.isoformat()]
        out = io.StringIO()
        ledger.write_text(HEADER + '\n'.join(self.rows()) + '\n', encoding='utf-8')
        with patch('sys.stdout', out):
            self.assertEqual(ledger_check.main(args), 0)
        ledger.write_text(HEADER + '\n'.join(self.rows()[1:]) + '\n', encoding='utf-8')
        with patch('sys.stdout', out):
            self.assertEqual(ledger_check.main(args), 1)
        self.assertIn('missing 1', out.getvalue())


NEUTRALISED = (
    ('coverage', lambda items, rows: ([], [], [], []),
     ('test_c_a_removed_row_fails_and_its_restoration_passes', 'test_c_unmatched_and_duplicate_rows_fail_and_notes_are_exempt')),
    ('unresolved_evidence', lambda *args, **kwargs: [], ('test_d_every_done_pointer_must_resolve',)),
    ('stale_running', lambda rows, now: [], ('test_e_an_old_running_row_naming_nothing_running_is_stale',)),
)


def passes(*names):
    suite = unittest.TestSuite(RequestLedgerChecks(n) for n in names) if names else \
        unittest.defaultTestLoader.loadTestsFromTestCase(RequestLedgerChecks)
    return unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite).wasSuccessful()


def check():
    if not passes():
        return 'FAIL', 'tools/loop/request_ledger_check_checks.py does not pass'
    proofs = []
    for attribute, mutant, names in NEUTRALISED:
        with patch.object(ledger_check, attribute, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        if not (failed and restored):
            return 'FAIL', 'request_ledger_check.%s neutralised: failed=%s, restored pass=%s' % (attribute, failed, restored)
        proofs.append(attribute)
    return 'PASS', ('the request ledger check reads Annex C and every D-S item from a fixture specification, '
                    'fails on a removed, unmatched or duplicate row, an unresolved DONE pointer and a stale '
                    'RUNNING row, and passes once restored; neutralised, failed, restored, passed: ' + ', '.join(proofs))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
