"""Proofs for tools/loop/issue_deferral_check.py (loop D-S24 item 4), on fixtures only: a
small issue list in gh's JSON shape, a ledger table and a DECISIONS.md, all in memory or in a
temporary folder. Nothing private is read and nothing is fetched. `check()` runs the tests,
then neutralises each of the script's four failing rules in turn ((a) unplanned issues, (b) a
loop-deferred honesty-or-release issue after v1, (c) a SCHEDULED or DEFERRED row with no issue,
(d) a deferral marker line with no issue), requires its proof to fail, restores it and
requires a pass.

    py -3.12 -X utf8 tools/loop/issue_deferral_check_checks.py
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import issue_deferral_check as deferral  # noqa: E402


def issue(number, labels=(), milestone=None):
    return {'number': number, 'title': 'issue %d' % number, 'body': 'operator: Annex D D-S1 item 1',
            'labels': [{'id': 'L%d' % k, 'name': name, 'description': '', 'color': 'ffffff'}
                       for k, name in enumerate(labels)],
            'milestone': {'number': 1, 'title': milestone, 'description': '', 'dueOn': None} if milestone else None}


def clean_issues():
    return [
        issue(1, ['loop'], 'S05'),
        issue(2, ['loop', 'operator-deferred'], None),
        issue(3, ['loop-deferred'], 'S06'),
        issue(4, ['honesty-or-release', 'operator-deferred'], 'S08'),
        issue(5, ['honesty-or-release', 'loop-deferred'], 'S11'),
        issue(6, ['honesty-or-release'], 'S14'),
        issue(7, ['loop-deferred'], 'Someday'),
    ]


HEADER = '| Id | Request | Source | Stage | Status | Last change | Evidence or where |\n|---|---|---|---|---|---|---|\n'


def row(rid, status, evidence):
    return '| %s | request | source | S6 | %s | 2026-11-02T11:00+0300 | %s |' % (rid, status, evidence)


def clean_rows():
    return [
        row('D-S1', 'DONE', 'D-001'),
        row('D-S2.1', 'SCHEDULED', 'S6, issue #3'),
        row('D-S2.2', 'DEFERRED (operator)', '#2'),
        row('D-S2.3', 'RUNNING', 'lane'),
        row('D-S2.4', 'BLOCKED', 'outside'),
    ]


def decision(number, *lines):
    return '## D-%03d. Decision %d\n\n- **When, stage.** 2026-11-02 10:00 +0300.\n%s\n' % (
        number, number, ''.join(line + '\n' for line in lines))


def clean_decisions():
    return '# Loop decisions\n\n' + '\n'.join([
        decision(12, '- **What.** Moved to S6 with no issue named, before markers existed.'),
        decision(178, '- **Defers.** grandfathered, names nothing.'),
        decision(179, '- **What.** Applies a rule; moves nothing.'),
        decision(180, '- **Moves.** The dry runs to S8-later (#140).', '- **Drops.** The reserve, #141 and #142.'),
        decision(181, 'Skips: the image step, see #143.', '```', '- **Drops.** inside a code block, not read.', '```'),
    ])


def run(issues=None, rows=None, decisions=None):
    return deferral.check(json.dumps(clean_issues() if issues is None else issues),
                          HEADER + '\n'.join(clean_rows() if rows is None else rows) + '\n',
                          clean_decisions() if decisions is None else decisions)


class IssueDeferralChecks(unittest.TestCase):
    def assertPasses(self, **parts):
        failed, lines = run(**parts)
        self.assertFalse(failed, '\n'.join(lines))
        return lines

    def assertFailsWith(self, text, **parts):
        failed, lines = run(**parts)
        self.assertTrue(failed, '\n'.join(lines))
        self.assertTrue(any(line.startswith(text) for line in lines[:-1]), '%r not in:\n%s' % (text, '\n'.join(lines)))
        self.assertTrue(lines[-1].endswith(': FAIL'))
        self.assertEqual(sum(1 for line in lines if line.startswith('open issues ')), 1)

    def test_clean_fixture_passes_with_one_count_line(self):
        lines = self.assertPasses()
        self.assertEqual(lines, [
            'open issues 7, ledger rows 5, decisions 5 (2 before D-179 grandfathered, 3 marker lines read); '
            'unplanned issues 0, loop-deferred honesty issues after v1 0, scheduled or deferred rows without an '
            'issue 0, deferring decisions without an issue 0: PASS'])

    def test_a_an_issue_neither_planned_nor_deferred_fails(self):
        self.assertFailsWith('UNPLANNED ISSUE #8: no operator-deferred or loop-deferred label and no stage milestone '
                             '(milestone: none)', issues=clean_issues() + [issue(8, ['loop', 'deferred'])])
        self.assertFailsWith('UNPLANNED ISSUE #9:', issues=clean_issues() + [issue(9, ['loop'], 'S03')])
        self.assertFailsWith('UNPLANNED ISSUE #10:', issues=clean_issues() + [issue(10, ['loop'], 'S15')])
        self.assertPasses(issues=clean_issues() + [issue(11, ['loop'], 'S14')])

    def test_b_a_loop_deferred_honesty_issue_after_v1_fails(self):
        for milestone in sorted(deferral.AFTER_V1_MILESTONES):
            number = 20 + int(milestone[1:])
            self.assertFailsWith('LOOP-DEFERRED HONESTY ISSUE #%d: honesty-or-release in %s (after v1)'
                                 % (number, milestone),
                                 issues=clean_issues() + [issue(number, ['honesty-or-release', 'loop-deferred'], milestone)])
        self.assertEqual(deferral.AFTER_V1_MILESTONES, {'S06', 'S08', 'S09', 'S12', 'S14'})
        self.assertPasses(issues=clean_issues() + [issue(40, ['honesty-or-release', 'loop-deferred'], 'S13'),
                                                   issue(41, ['honesty-or-release', 'operator-deferred'], 'S06')])

    def test_c_a_scheduled_or_deferred_row_without_issue_fails(self):
        self.assertFailsWith('LEDGER ROW WITHOUT ISSUE D-S2.1: SCHEDULED and names no issue',
                             rows=[row('D-S2.1', 'SCHEDULED', 'S6') if r.startswith('| D-S2.1 ') else r
                                   for r in clean_rows()])
        self.assertFailsWith('LEDGER ROW WITHOUT ISSUE D-S2.2: DEFERRED and names no issue',
                             rows=[row('D-S2.2', 'DEFERRED (operator)', 'issue &#38; S6, C#9') if r.startswith('| D-S2.2 ')
                                   else r for r in clean_rows()])
        self.assertPasses(rows=clean_rows() + [row('D-S2.5', 'RUNNING', 'no issue needed')])

    def test_d_a_deferral_marker_from_d179_without_issue_fails(self):
        for marker in ('- **Moves.** L13 to S6.', '- **Defers.** the replay.', '- **Drops.** the reserve.',
                       '- **Skips.** the image.', 'Moves: L13 to S6.', 'Drops: the reserve.'):
            self.assertFailsWith('DECISION WITHOUT ISSUE D-182: "%s" line names no issue'
                                 % marker.lstrip('- *').split('.')[0].split(':')[0],
                                 decisions=clean_decisions() + '\n' + decision(182, marker))
        self.assertFailsWith('DECISION WITHOUT ISSUE D-179:',
                             decisions=clean_decisions().replace('Applies a rule; moves nothing.',
                                                                 'Applies a rule.\n- **Moves.** one step to S6.'))
        self.assertPasses(decisions=clean_decisions() + '\n' + decision(182, '- **What.** moves nothing marked.'))
        self.assertPasses(decisions=clean_decisions() + '\n' + decision(78,'- **Drops.** old, no issue.'))

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            issues, ledger, decisions = folder / 'issues.json', folder / 'ledger.md', folder / 'DECISIONS.md'
            issues.write_text('﻿' + json.dumps(clean_issues()), encoding='utf-8')
            ledger.write_text(HEADER + '\n'.join(clean_rows()) + '\n', encoding='utf-8')
            decisions.write_text(clean_decisions(), encoding='utf-8')
            args = ['--issues', str(issues), '--ledger', str(ledger), '--decisions', str(decisions)]
            out = io.StringIO()
            with patch('sys.stdout', out):
                self.assertEqual(deferral.main(args), 0)
            issues.write_text(json.dumps(clean_issues() + [issue(8)]), encoding='utf-8')
            with patch('sys.stdout', out):
                self.assertEqual(deferral.main(args), 1)
            self.assertIn('UNPLANNED ISSUE #8', out.getvalue())
            issues.write_text(json.dumps({'not': 'a list'}), encoding='utf-8')
            with patch('sys.stderr', io.StringIO()), self.assertRaises(SystemExit) as stop:
                deferral.main(args)
            self.assertEqual(stop.exception.code, 2)


NEUTRALISED = (
    ('unplanned_issues', lambda issues: [], ('test_a_an_issue_neither_planned_nor_deferred_fails',)),
    ('loop_deferred_honesty', lambda issues: [], ('test_b_a_loop_deferred_honesty_issue_after_v1_fails',)),
    ('rows_without_issue', lambda rows: [], ('test_c_a_scheduled_or_deferred_row_without_issue_fails',)),
    ('markers_without_issue', lambda blocks: ([], sum(1 for n, _ in blocks if n < 179), 3),
     ('test_d_a_deferral_marker_from_d179_without_issue_fails',)),
)


def passes(*names):
    suite = unittest.TestSuite(IssueDeferralChecks(n) for n in names) if names else \
        unittest.defaultTestLoader.loadTestsFromTestCase(IssueDeferralChecks)
    return unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite).wasSuccessful()


def check():
    if not passes():
        return 'FAIL', 'tools/loop/issue_deferral_check_checks.py does not pass'
    proofs = []
    for attribute, mutant, names in NEUTRALISED:
        with patch.object(deferral, attribute, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        if not (failed and restored):
            return 'FAIL', 'issue_deferral_check.%s neutralised: failed=%s, restored pass=%s' % (attribute, failed, restored)
        proofs.append(attribute)
    return 'PASS', ('the issue deferral check fails on an open issue neither planned in a stage nor labelled '
                    'deferred, a loop-deferred honesty-or-release issue after v1, a SCHEDULED or DEFERRED ledger '
                    'row naming no issue and a deferral marker from D-179 on naming no issue, and passes a clean '
                    'fixture; neutralised, failed, restored, passed: ' + ', '.join(proofs))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
