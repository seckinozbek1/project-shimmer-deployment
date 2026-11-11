"""Proofs for tools/loop/status_evidence_check.py (loop D-S101 item 3), on fixtures in a
temporary folder only: a git repository with a loop branch of three commits and a side branch
that is not its ancestor, a private folder with one file, two run folders (one with a result,
one without), a DECISIONS.md whose sections name some ids and not others, and records written
here. Nothing private is read, nothing fetched. `check()` runs the tests, then neutralises each
rule in turn, requires a failure, restores it and requires a pass.

    py -3.12 -X utf8 tools/loop/status_evidence_check_checks.py
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
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import status_evidence_check as sec  # noqa: E402
from cloud_run_common import no_window  # noqa: E402

LOOP = 'loop/fixture'
DECISIONS = ('# Decisions\n\n'
             '## D-001. The first decision\n\n- Applies D-S1 and Annex C R1; closes stage S1.\n\n'
             '## D-002. The second decision\n\n- About something else entirely.\n')
LEDGER_HEAD = ('| Id | Request | Source | Stage | Status | Last change | Evidence or where |\n'
               '|---|---|---|---|---|---|---|\n')
STATE_TABLE = ('| # | Loose end | State | Owner | Blocks |\n'
               '|---|---|---|---|---|\n')


def _git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, creationflags=no_window())
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


class Fixture:
    def __init__(self, folder):
        self.root = Path(folder) / 'repo'
        self.root.mkdir()
        _git(self.root, 'init', '-q', '-b', LOOP)
        _git(self.root, 'config', 'user.email', 'fixture@example.invalid')
        _git(self.root, 'config', 'user.name', 'fixture')
        _git(self.root, 'config', 'commit.gpgsign', 'false')
        _git(self.root, 'config', 'core.autocrlf', 'false')
        (self.root / 'docs').mkdir()
        (self.root / 'docs' / 'a.md').write_text('a\n', encoding='utf-8')
        _git(self.root, 'add', 'docs/a.md')
        _git(self.root, 'commit', '-q', '-m', 'first')
        self.first = _git(self.root, 'rev-parse', '--short=8', 'HEAD')
        (self.root / 'tools').mkdir()
        (self.root / 'tools' / 't.py').write_text('t = 1\n', encoding='utf-8')
        _git(self.root, 'add', 'tools/t.py')
        _git(self.root, 'commit', '-q', '-m', 'second')
        self.second = _git(self.root, 'rev-parse', '--short=8', 'HEAD')
        _git(self.root, 'checkout', '-q', '-b', 'side', self.first)
        (self.root / 'docs' / 'side.md').write_text('side\n', encoding='utf-8')
        _git(self.root, 'add', 'docs/side.md')
        _git(self.root, 'commit', '-q', '-m', 'side')
        self.side = _git(self.root, 'rev-parse', '--short=8', 'HEAD')
        _git(self.root, 'checkout', '-q', LOOP)
        self.private = self.root / 'docs' / 'loop' / 'private'
        self.private.mkdir(parents=True)
        (self.private / 'note.md').write_text('note\n', encoding='utf-8')
        (self.root / 'runs' / 'good' / 'evidence').mkdir(parents=True)
        (self.root / 'runs' / 'good' / 'evidence' / 'result.json').write_text('{"exit": 0}', encoding='utf-8')
        (self.root / 'runs' / 'empty').mkdir(parents=True)
        (self.root / 'runs' / 'empty' / 'log.txt').write_text('x', encoding='utf-8')
        (self.root / 'runs' / 'blank').mkdir(parents=True)
        (self.root / 'runs' / 'blank' / 'result.json').write_text('{}', encoding='utf-8')
        (self.root / 'runs' / 'deep' / 'a' / 'b').mkdir(parents=True)
        (self.root / 'runs' / 'deep' / 'a' / 'b' / 'result.json').write_text('{"x": 1}', encoding='utf-8')
        (self.root / 'runs' / 'top').mkdir(parents=True)
        (self.root / 'runs' / 'top' / 'FINAL_STATUS.json').write_text('{"state": "completed"}', encoding='utf-8')
        (self.private / 'empty.md').write_text('', encoding='utf-8')
        (self.private / 'sub').mkdir()
        (self.private / 'sub' / 'deep.md').write_text('deep\n', encoding='utf-8')
        self.decisions = Path(folder) / 'DECISIONS.md'
        self.decisions.write_text(DECISIONS, encoding='utf-8')

    def repo(self):
        return sec.Repository(self.root, self.private, LOOP)


def row(rid, status, evidence):
    return '| %s | r | s | after v1 | %s | 2026-11-09T10:00+0300 | %s |' % (rid, status, evidence)


def wheres(claims):
    return [c.where for c in claims]


class StatusEvidenceChecks(unittest.TestCase):
    def setUp(self):
        if shutil.which('git') is None:
            self.skipTest('no git')
        self.folder = tempfile.TemporaryDirectory()
        self.fixture = Fixture(self.folder.name)
        self.headings = {'D-001', 'D-002'}
        self.sections = sec.decision_sections(DECISIONS)

    def tearDown(self):
        self.folder.cleanup()

    def failures(self, name, items, lenient=True, source=None):
        return sec.check([(name, items, lenient, source)], self.headings, self.fixture.repo(), self.sections)[1]

    def assertFails(self, name, items, fragment, lenient=True, source=None):
        found = self.failures(name, items, lenient, source)
        self.assertTrue(any(fragment in f for f in found), 'expected %r in %r' % (fragment, found))

    def assertPasses(self, name, items, lenient=True, source=None):
        self.assertEqual(self.failures(name, items, lenient, source), [])

    # claim forms

    def test_markdown_claim_forms_are_read_and_prose_is_not(self):
        text = '\n'.join([
            '- **Done** D-001',
            'Merged: `docs/a.md`',
            '| 3 | step | (verified, D-001) |',
            '| 4 | step | closed | D-001 |',
            'Status: applied, D-001.',
            '| 6 | step | done (D-001); checked |',
            'The scores were measured (D-001) on the set.',
            '**Bitti.** D-001',
            'B rolü bitti (19:22, D-001).',
            'CLOSED by D-001',
            '| 11 | step | the work is done by the lead |',
            'Every consequence of a change that is not yet done: what it is.',
            'States: done (evidence named), verified (checked).',
            'loop-base and loop/s03 (not yet merged) were not pushed.',
            '```',
            'DONE inside a fence is not read',
            '```',
        ])
        found = sec.markdown_claims(text)
        self.assertEqual(wheres(found), ['line %d' % n for n in range(1, 11)])
        self.assertPasses('for seckin', found)

    def test_a_claim_with_no_evidence_fails(self):
        self.assertFails('return brief', sec.markdown_claims('- **Done.** The gate set was built.'),
                         'no evidence named')

    def test_a_branch_name_is_no_evidence(self):
        self.assertFails('plan', sec.markdown_claims('**Merged:** `lane/x` into the loop branch'),
                         'no evidence named')

    def test_a_claim_naming_a_missing_decision_fails(self):
        self.assertFails('loose ends', sec.markdown_claims('DONE (D-999)'), 'no heading "## D-999."')

    def test_a_missing_file_fails_and_an_existing_one_passes(self):
        self.assertFails('loose ends', sec.markdown_claims('Done: `docs/missing.md`'), 'path docs/missing.md')
        self.assertPasses('loose ends', sec.markdown_claims('Done: `note.md` and `runs/good`'))

    def test_a_path_tracked_on_the_loop_branch_counts_when_the_disk_lags(self):
        fx = self.fixture
        claim = sec.markdown_claims('Done: `tools/t.py`')
        self.assertPasses('loose ends', claim)
        (fx.root / 'tools' / 't.py').unlink()  # the checkout's disk lags the loop branch
        self.assertPasses('loose ends', claim)
        # a path neither on disk nor tracked still fails
        self.assertFails('loose ends', sec.markdown_claims('Done: `tools/never.py`'), 'nor on %s' % LOOP)
        # a tracked file that is empty on the branch fails
        (fx.root / 'tools' / 'blank.py').write_text('', encoding='utf-8')
        _git(fx.root, 'add', 'tools/blank.py')
        _git(fx.root, 'commit', '-q', '-m', 'blank')
        (fx.root / 'tools' / 'blank.py').unlink()
        self.assertFails('loose ends', sec.markdown_claims('Done: `tools/blank.py`'), 'is empty on %s' % LOOP)

    def test_a_run_folder_must_hold_a_result(self):
        self.assertFails('return brief', sec.markdown_claims('(verified, `runs/empty`)'), 'holds no non-empty')
        self.assertPasses('return brief', sec.markdown_claims('(verified, `runs/good`)'))

    def test_a_commit_must_be_an_ancestor_of_the_loop_branch(self):
        self.assertFails('loose ends', sec.markdown_claims('DONE `%s`' % self.fixture.side), 'is not an ancestor')
        self.assertFails('loose ends', sec.markdown_claims('| 25 | a lane | done (%s) | x |' % self.fixture.side),
                         'is not an ancestor')
        self.assertPasses('loose ends', sec.markdown_claims('DONE `%s`' % self.fixture.second))

    def test_a_push_record_commit_may_be_on_the_pushed_ref(self):
        fx = self.fixture
        claim = sec.markdown_claims('(merged, `%s`)' % fx.side)
        # no origin yet: the side commit is on neither the loop branch nor origin's main
        self.assertFails('push record', claim, 'or refs/remotes/origin/main')
        origin = Path(self.folder.name) / 'origin.git'
        _git(fx.root, 'init', '-q', '--bare', str(origin))
        _git(fx.root, 'remote', 'add', 'origin', str(origin))
        _git(fx.root, 'push', '-q', 'origin', 'side:refs/heads/main')
        _git(fx.root, 'fetch', '-q', 'origin', 'main')
        self.assertPasses('push record', claim)
        # only the push record reads the pushed ref
        self.assertFails('loose ends', claim, 'is not an ancestor of %s' % LOOP)
        # a commit on no pushed ref still fails there
        _git(fx.root, 'checkout', '-q', '-b', 'other', fx.first)
        (fx.root / 'docs' / 'other.md').write_text('o\n', encoding='utf-8')
        _git(fx.root, 'add', 'docs/other.md')
        _git(fx.root, 'commit', '-q', '-m', 'other')
        other = _git(fx.root, 'rev-parse', '--short=8', 'HEAD')
        _git(fx.root, 'checkout', '-q', LOOP)
        self.assertFails('push record', sec.markdown_claims('(merged, `%s`)' % other), 'or refs/remotes/origin/main')

    def test_a_push_record_commit_on_a_local_side_branch_only_fails(self):
        # the looser rule of 8704b9ce (any local branch) accepted this; the pushed ref does not
        fx = self.fixture
        origin = Path(self.folder.name) / 'origin.git'
        _git(fx.root, 'init', '-q', '--bare', str(origin))
        _git(fx.root, 'remote', 'add', 'origin', str(origin))
        _git(fx.root, 'push', '-q', 'origin', '%s:refs/heads/main' % LOOP)
        _git(fx.root, 'fetch', '-q', 'origin', 'main')
        self.assertTrue(_git(fx.root, 'branch', '--list', 'side'))
        self.assertFails('push record', sec.markdown_claims('(merged, `%s`)' % fx.side), 'or refs/remotes/origin/main')

    def test_a_commit_must_have_changed_the_tracked_path_it_is_cited_for(self):
        first, second = self.fixture.first, self.fixture.second
        self.assertFails('loose ends', sec.markdown_claims('DONE `%s` `tools/t.py`' % first), 'changed tools/t.py')
        # the second commit holds docs/a.md but did not change it
        self.assertFails('loose ends', sec.markdown_claims('DONE `%s` `docs/a.md`' % second), 'changed docs/a.md')
        self.assertPasses('loose ends', sec.markdown_claims('DONE `%s` `tools/t.py`' % second))
        self.assertPasses('loose ends', sec.markdown_claims('DONE `%s` `%s` `docs/a.md` `tools/t.py`' % (first, second)))
        # an untracked private file is checked for existence only
        self.assertPasses('loose ends', sec.markdown_claims('DONE `%s` `note.md`' % first))

    def test_a_bare_digest_is_no_pointer_and_a_bare_commit_is(self):
        self.assertFails('return brief', sec.markdown_claims('DONE, digest 0deadbe1'), 'no evidence named')
        self.assertPasses('return brief', sec.markdown_claims('DONE at %s' % self.fixture.second))
        self.assertFails('return brief', sec.markdown_claims('DONE at %s' % self.fixture.side), 'is not an ancestor')

    # gaps 6 and 9: empty or out-of-scope evidence; what is no pointer

    def test_empty_files_and_empty_results_fail(self):
        self.assertFails('loose ends', sec.markdown_claims('Done: `empty.md`'), 'is empty')
        self.assertFails('loose ends', sec.markdown_claims('(done, `runs/blank`)'), 'holds no non-empty')
        self.assertFails('loose ends', sec.markdown_claims('(done, `runs/deep`)'), 'holds no non-empty')
        self.assertPasses('loose ends', sec.markdown_claims('(done, `runs/top`)'))

    def test_paths_outside_the_root_or_searched_below_are_refused(self):
        absolute = (self.fixture.private / 'note.md').as_posix()
        self.assertFails('loose ends', sec.markdown_claims('Done: `%s`' % absolute), 'does not exist inside')
        self.assertFails('loose ends', sec.markdown_claims('Done: `../repo/docs/a.md`'), 'does not exist inside')
        self.assertFails('loose ends', sec.markdown_claims('Done: `deep.md`'), 'does not exist inside')
        self.assertPasses('loose ends', sec.markdown_claims('Done: `sub/deep.md` and `note.md`'))

    def test_entry_ids_and_short_ids_are_no_pointers_and_a_missing_commit_fails(self):
        self.assertFails('loose ends', sec.markdown_claims('DONE (D-S101, D-35)'), 'no evidence named')
        self.assertFails('loose ends', sec.markdown_claims('DONE `abcdef12`'), 'commit abcdef12 does not exist')

    # gap 8: each claim form alone

    FORM_SAMPLES = (
        'CLOSED by D-001',                     # 0 capitals
        '**Done** D-001',                      # 1 bold
        '(verified, D-001)',                   # 2 bracketed
        'it was measured (D-001) on the set',  # 3 word (pointer)
        'Merged: `docs/a.md`',                 # 4 label
        'the Status: applied, D-001.',         # 5 Status:
        '| 6 | step | done; D-001 |',          # 6 a cell opening with the word
    )

    def test_each_claim_form_reads_a_line_no_other_form_reads(self):
        self.assertEqual(len(self.FORM_SAMPLES), len(sec.CLAIM_FORMS))
        for index, sample in enumerate(self.FORM_SAMPLES):
            matched = [i for i, form in enumerate(sec.CLAIM_FORMS) if form.search(sample)]
            self.assertEqual(matched, [index], sample)

    def test_each_claim_form_is_read(self):
        for sample in self.FORM_SAMPLES:
            self.assertTrue(sec.claims_in_line(sample), sample)

    # gap 10: the ledger's status vocabulary

    def test_a_ledger_status_outside_the_vocabulary_fails(self):
        text = LEDGER_HEAD + '\n'.join([
            row('D-S1', 'Done', 'D-001'),
            row('D-S1.2', 'DONE(x)', 'D-001'),
            row('D-S1.3', 'MERGED', 'D-001'),
            row('D-S1.4', 'RUNNING (standing)', 'D-001'),
            row('D-S1.5', 'SCHEDULED (step 5)', 'D-001'),
            row('D-S1.6', 'DONE', 'D-001'),
        ]) + '\n'
        errors = sec.ledger_status_errors(text)
        self.assertEqual([e.split(':')[0] for e in errors], ['row D-S1', 'row D-S1.2', 'row D-S1.3'])
        found = sec.check([('ledger', sec.ledger_claims(text), False, None, errors)], self.headings,
                          self.fixture.repo(), self.sections)[1]
        self.assertEqual(len(found), 3)

    # the State column

    def test_a_state_column_is_read_by_its_cell(self):
        text = STATE_TABLE + '\n'.join([
            '| 1 | a thing | done (D-001) | lead | none |',
            '| 2 | Done: a label in another cell | in progress | lead | none |',
            '| 3 | a thing | requested | lead | none |',
            '| 4 | a thing | done | lead | none |',
            '| 5 | a thing | verified (`runs/good`) | lead | none |',
            '| 6 | a thing | merged (D-001) | lead | none |',
            '| 7 | a thing | uygulandı (D-001) | lead | none |',
        ])
        found = sec.markdown_claims(text, state_column=True)
        self.assertEqual(wheres(found), ['line 3 (State)', 'line 6 (State)', 'line 7 (State)', 'line 8 (State)',
                                         'line 9 (State)'])
        fails = self.failures('loose ends', found)
        self.assertEqual([f.split(':')[0] for f in fails], ['loose ends line 6 (State)'])

    # a record with state words and no claim

    def test_a_record_with_state_words_and_no_claim_fails(self):
        source = 'The work was merged into the loop branch.\n'
        self.assertFails('push record', sec.markdown_claims(source), 'no claim in a declared form', source=source)
        quiet = 'Nothing here states a finished state.\n'
        self.assertPasses('push record', sec.markdown_claims(quiet), source=quiet)

    # the ledger, and decisions that must name the claim's own id

    def test_ledger_done_and_verified_rows_must_resolve(self):
        text = LEDGER_HEAD + '\n'.join([
            row('D-S1.2', 'DONE', 'D-001'),
            row('D-S2', 'DONE', 'D-999'),
            row('D-S3', 'VERIFIED', 'checked by an agent'),
            row('D-S1.4', 'DONE', 'D-001; `%s`' % self.fixture.side),
            row('D-S5', 'RUNNING', 'nothing here'),
        ]) + '\n'
        found = self.failures('ledger', sec.ledger_claims(text), lenient=False)
        self.assertEqual(sorted(f.split(':')[0] for f in found),
                         ['ledger row D-S1.4', 'ledger row D-S2', 'ledger row D-S3'])

    def test_ledger_verified_row_is_read(self):
        text = LEDGER_HEAD + row('D-S3', 'VERIFIED', 'checked by an agent') + '\n'
        self.assertFails('ledger', sec.ledger_claims(text), 'no evidence named', lenient=False)

    def test_a_decision_must_name_the_rows_own_id(self):
        text = LEDGER_HEAD + '\n'.join([
            row('D-S1.3', 'DONE', 'D-001'),             # D-001 names D-S1
            row('D-S7', 'DONE', 'D-002'),               # D-002 names nothing of D-S7
            row('D-S7.1', 'DONE', 'D-002 and D-001'),   # neither names D-S7
            row('D-S1.5', 'DONE', 'D-002 and D-001'),   # one of them names D-S1
            row('C-R1', 'DONE', 'D-001'),               # D-001 names R1
            row('C-R2', 'DONE', 'D-001'),               # it does not name R2
            row('N-2026-11-09-1000', 'DONE', 'D-002'),  # a note carries no id to name
        ]) + '\n'
        found = self.failures('ledger', sec.ledger_claims(text), lenient=False)
        self.assertEqual(sorted(f.split(':')[0] for f in found), ['ledger row C-R2', 'ledger row D-S7', 'ledger row D-S7.1'])
        self.assertTrue(all('unrelated' in f for f in found))

    # PROGRESS.json

    def test_progress_done_objects_need_related_evidence(self):
        data = {'stages': [{'id': 'S0', 'status': 'done', 'name': 'Setup'},
                           {'id': 'S1', 'status': 'done', 'name': 'Clean (D-001)'},
                           {'id': 'S2', 'status': 'done', 'name': 'Other (D-002)'},
                           {'id': 'S3', 'status': 'running', 'name': 'Later'}],
                'current': {'x': [{'name': 'a task', 'status': 'verified', 'evidence': ['`docs/a.md`']}]}}
        found = self.failures('progress', sec.progress_claims(data))
        self.assertEqual(len(found), 2, found)
        self.assertIn('(S0)', found[0])
        self.assertIn('no evidence named', found[0])
        self.assertIn('unrelated', found[1])

    def test_an_object_naming_its_own_id_is_not_evidence(self):
        data = [{'id': 'D-001', 'status': 'done', 'name': 'see D-001'}]
        self.assertFails('progress', sec.progress_claims(data), 'no evidence named')

    # closed issues

    def test_closed_issues_need_evidence_in_their_comments(self):
        issues = [{'number': 1, 'stateReason': 'COMPLETED', 'comments': [{'body': 'Fixed by D-001.'}]},
                  {'number': 2, 'stateReason': 'COMPLETED', 'comments': []},
                  {'number': 3, 'stateReason': 'NOT_PLANNED', 'comments': []},
                  {'number': 4, 'stateReason': 'COMPLETED', 'comments': [{'body': 'see D-999'}]}]
        items, not_planned = sec.issue_claims(issues)
        self.assertEqual(not_planned, 1)
        found = self.failures('issues', items)
        self.assertEqual(sorted(f.split(':')[0] for f in found), ['issues issue #2', 'issues issue #4'])

    # the command line

    def test_cli_reads_each_record_and_exits_on_failure(self):
        fx = self.fixture
        folder = Path(self.folder.name)
        files = {name: folder / name for name in ('ledger.md', 'brief.md', 'seckin.md', 'push.md', 'plan.md',
                                                  'loose.md', 'progress.json', 'closed.json')}
        files['ledger.md'].write_text(LEDGER_HEAD + row('D-S1', 'DONE', 'D-001') + '\n', encoding='utf-8')
        files['brief.md'].write_text('- **Done** D-001\n', encoding='utf-8')
        files['seckin.md'].write_text('**Bitti.** D-001\n', encoding='utf-8')
        files['push.md'].write_text('| ref | old | new |\n', encoding='utf-8')
        files['plan.md'].write_text('1. **Merged:** D-001\n', encoding='utf-8')
        files['loose.md'].write_text(STATE_TABLE + '| 1 | x | done (D-001) | lead | none |\n', encoding='utf-8')
        files['progress.json'].write_text(json.dumps({'stages': [{'id': 'S1', 'status': 'done',
                                                                  'name': 'x (D-001)'}]}), encoding='utf-8')
        files['closed.json'].write_text(json.dumps([{'number': 1, 'stateReason': 'COMPLETED',
                                                     'comments': [{'body': 'D-001'}]}]), encoding='utf-8')
        args = ['--root', str(fx.root), '--loop-ref', LOOP, '--private', str(fx.private),
                '--decisions', str(fx.decisions), '--ledger', str(files['ledger.md']),
                '--return-brief', str(files['brief.md']), '--for-seckin', str(files['seckin.md']),
                '--push-record', str(files['push.md']), '--plan', str(files['plan.md']),
                '--loose-ends', str(files['loose.md']), '--progress', str(files['progress.json']),
                '--closed-issues', str(files['closed.json'])]
        out = io.StringIO()
        with patch('sys.stdout', out):
            self.assertEqual(sec.main(args), 0)
        self.assertIn('records read 8; claims 7, unresolved 0', out.getvalue())
        self.assertIn('claims per record: ledger 1, loose ends 1, return brief 1, for seckin 1, push record 0, '
                      'plan 1, progress 1, issues 1', out.getvalue())
        files['brief.md'].write_text('- **Done** nothing named\n', encoding='utf-8')
        with patch('sys.stdout', out):
            self.assertEqual(sec.main(args), 1)
        self.assertIn('UNRESOLVED return brief line 1', out.getvalue())
        with patch('sys.stdout', out):
            self.assertEqual(sec.main(args[:4] + ['--loop-ref', 'no/such']), 1)
        files['brief.md'].write_text('- **Done** D-001\n', encoding='utf-8')
        no_issues = [a for a in args if a not in ('--closed-issues', str(files['closed.json']))]
        out = io.StringIO()
        with patch('sys.stdout', out):
            self.assertEqual(sec.main(no_issues), 1)
        self.assertIn('UNRESOLVED issues: absent, and not named with --skip', out.getvalue())
        out = io.StringIO()
        with patch('sys.stdout', out):
            self.assertEqual(sec.main(no_issues + ['--skip', 'issues']), 0)
        self.assertIn('not read (skipped by the caller): issues', out.getvalue())
        out = io.StringIO()
        every = sum((['--skip', name] for name in sec.RECORDS), [])
        with patch('sys.stdout', out):
            self.assertEqual(sec.main(args[:8] + every), 1)
        self.assertIn('no record was read', out.getvalue())
        # the default DECISIONS.md is read from the loop branch itself: none there, so it fails
        with patch('sys.stdout', out):
            self.assertEqual(sec.main([a for a in args if a not in ('--decisions', str(fx.decisions))]), 1)
        self.assertIn('no decision heading', out.getvalue())


MD = ('test_markdown_claim_forms_are_read_and_prose_is_not', 'test_a_claim_with_no_evidence_fails')
NEVER = re.compile(r'(?!x)x')

NEUTRALISED = (
    ('claims_in_line', lambda line: False, MD),
    ('no_evidence', lambda found: False, ('test_a_claim_with_no_evidence_fails',
                                          'test_progress_done_objects_need_related_evidence')),
    ('decision_resolves', lambda value, headings: True, ('test_a_claim_naming_a_missing_decision_fails',
                                                         'test_closed_issues_need_evidence_in_their_comments')),
    ('decision_names', lambda section, own_id: True, ('test_a_decision_must_name_the_rows_own_id',
                                                      'test_progress_done_objects_need_related_evidence')),
    ('PUSH_RECORDS', (), ('test_a_push_record_commit_may_be_on_the_pushed_ref',)),
    ('Repository.is_pushed', lambda self, digest: True, ('test_a_push_record_commit_on_a_local_side_branch_only_fails',)),
    ('Repository.is_pushed', lambda self, digest: False, ('test_a_push_record_commit_may_be_on_the_pushed_ref',)),
    ('Repository.is_ancestor', lambda self, digest: True, ('test_a_commit_must_be_an_ancestor_of_the_loop_branch',)),
    ('Repository.commit_changes', lambda self, digest, path: True,
     ('test_a_commit_must_have_changed_the_tracked_path_it_is_cited_for',)),
    ('Repository.tracked', lambda self, path: False, ('test_a_path_tracked_on_the_loop_branch_counts_when_the_disk_lags',)),
    ('Repository.tracked_has_content', lambda self, path: True,
     ('test_a_path_tracked_on_the_loop_branch_counts_when_the_disk_lags',)),
    ('Repository.locate', lambda self, token: Path(__file__), ('test_a_missing_file_fails_and_an_existing_one_passes',)),
    ('run_folder_holds_result', lambda folder, depth=3: True, ('test_a_run_folder_must_hold_a_result',)),
    ('LEDGER_STATES', ('DONE',), ('test_ledger_verified_row_is_read',)),
    ('state_column_claims', lambda text: {}, ('test_a_state_column_is_read_by_its_cell',)),
    ('STATE_WORDS', ('done', 'verified'), ('test_a_state_column_is_read_by_its_cell',)),
    ('holds_state_words', lambda text: False, ('test_a_record_with_state_words_and_no_claim_fails',)),
    ('BRANCH', NEVER, ('test_a_branch_name_is_no_evidence',)),
    ('file_has_content', lambda path: True, ('test_empty_files_and_empty_results_fail',)),
    ('inside_scope', lambda rel: True, ('test_paths_outside_the_root_or_searched_below_are_refused',)),
    ('fence_toggles', lambda line: False, ('test_markdown_claim_forms_are_read_and_prose_is_not',)),
    ('NOT_CLAIMED_REASONS', (), ('test_closed_issues_need_evidence_in_their_comments',)),
    ('Repository.tracked', lambda self, path: True,
     ('test_a_commit_must_have_changed_the_tracked_path_it_is_cited_for',)),
    ('nothing_read', lambda counts: False, ('test_cli_reads_each_record_and_exits_on_failure',)),
    ('ledger_status_errors', lambda text: [], ('test_a_ledger_status_outside_the_vocabulary_fails',)),
    ('progress_claims', lambda data: [], ('test_progress_done_objects_need_related_evidence',)),
    ('issue_claims', lambda issues: ([], 0), ('test_closed_issues_need_evidence_in_their_comments',)),
)


FORM_NEUTRALISED = tuple(
    ('CLAIM_FORMS[%d]' % index, tuple(f for i, f in enumerate(sec.CLAIM_FORMS) if i != index),
     ('test_each_claim_form_is_read',))
    for index in range(len(sec.CLAIM_FORMS)))


def passes(*names):
    suite = unittest.TestSuite(StatusEvidenceChecks(n) for n in names) if names else \
        unittest.defaultTestLoader.loadTestsFromTestCase(StatusEvidenceChecks)
    return unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite).wasSuccessful()


def _target(attribute):
    if '.' in attribute:
        owner, name = attribute.split('.')
        return getattr(sec, owner), name
    return sec, attribute


def check():
    if shutil.which('git') is None:
        return 'SKIP', 'git is not installed here; every proof runs on a fixture git repository'
    if not passes():
        return 'FAIL', 'tools/loop/status_evidence_check_checks.py does not pass'
    proofs = []
    for attribute, mutant, names in NEUTRALISED + FORM_NEUTRALISED:
        owner, name = _target(attribute.split('[')[0])
        with patch.object(owner, name, mutant):
            failed = not passes(*names)
        restored = passes(*names)
        if not (failed and restored):
            return 'FAIL', 'status_evidence_check.%s neutralised: failed=%s, restored pass=%s' % (
                attribute, failed, restored)
        proofs.append(attribute)
    return 'PASS', ('a finished-state claim (done, verified, closed, merged, measured, applied, and the Turkish '
                    'words) in the ledger, LOOSE_ENDS (its State column), the return brief, FOR_SECKIN, the push '
                    'record, AFTER_V1_PLAN, PROGRESS.json or a closed issue fails when it names no evidence or a '
                    'pointer that does not resolve (a decision heading that names the claim\'s own id, a commit '
                    'that is an ancestor of the loop branch and changed the tracked path it is cited for, a file, '
                    'a run folder with a result), and a record with state words but no claim fails; neutralised, '
                    'failed, restored, passed: ' + ', '.join(proofs))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == 'PASS' else 1)
