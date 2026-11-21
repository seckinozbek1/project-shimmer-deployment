#!/usr/bin/env python3
"""Rule tests for tools/loop/freeze_tag.py (operator order G-20261121-1559/1600; D-912, D-923).

The written freeze rule, quoted word for word from docs/loop/DECISIONS.md D-912 (the generalised form is the same
sentence with "v1.0-alpha-freeze-d" read as any tag and "dab39cc4" as any commit; the known list in brackets is the
module's KNOWN_RED):

    It tags v1.0-alpha-freeze-d on dab39cc4 only when the gate exited 0, every check ran, the reds equal the known list
    (...) and the evidence tree equals dab39cc4's tree. SKIP checks are neither pass nor red and are recorded.
    Otherwise FREEZE_REFUSED.json and one ALERT line; the tag is never moved.

freeze_tag.run() calls run_all(module) just before it creates a tag. Each clause runs the module's own functions on a small
in-memory fixture (no git repository, no real folder); a red clause means no tag, FREEZE_REFUSED.json with the reason
"rule test red: <clause>" and one ALERT line. The tests read the judge; they never change a decision of it.

    py -3.12 -X utf8 tools/loop/freeze_rule_tests.py     prints each clause and PASS or FAIL
"""
from __future__ import annotations

import io
import json
import re
import sys
import tarfile
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DECISIONS = HERE.parents[1] / 'docs' / 'loop' / 'DECISIONS.md'

QUOTE_HEAD = 'It tags v1.0-alpha-freeze-d on dab39cc4 only when the gate exited 0, every check ran, the reds equal the known list'
QUOTE_TAIL = ("and the evidence tree equals dab39cc4's tree. SKIP checks are neither pass nor red and are recorded. "
              "Otherwise FREEZE_REFUSED.json and one ALERT line; the tag is never moved.")

TREE = 'a' * 40
GIT_FILTER = None   # proofs only: a function (result, args) -> result applied to the fake git's answers, to model a blind tag check


def _rows(red=(), skip=(), drop=None, total=20):
    reds = set(red)
    nums = [n for n in range(total)] + [n for n in sorted(reds) if n >= total]
    status = {n: ('FAIL' if n in reds else ('SKIP' if n in skip else 'PASS')) for n in nums}
    text = '\n'.join(json.dumps({'number': n, 'title': 't%d' % n, 'status': status[n], 'seconds': 0.1})
                     for n in nums if n != drop) + '\n'
    counts = {k: sum(1 for v in status.values() if v == k) for k in ('PASS', 'FAIL', 'SKIP')}
    summary = {'counts': counts, 'execution_integrity_passed': True, 'not_run': [], 'reasons': []}
    return text, summary


def _judge(fz, red=None, skip=(), drop=None, exit_code=0, tree=TREE, commit_tree=TREE):
    red = list(fz.KNOWN_RED) if red is None else red
    text, summary = _rows(red, skip, drop)
    return fz.judge(text, summary, {'tree': tree}, commit_tree, exit_code)


def clause_quote(fz):
    """The quoted rule is in D-912, and its known list is the module's KNOWN_RED."""
    doc = DECISIONS.read_text(encoding='utf-8')
    assert QUOTE_HEAD in doc and QUOTE_TAIL in doc, 'the rule text is not in DECISIONS.md D-912 word for word'
    after = doc[doc.index(QUOTE_HEAD) + len(QUOTE_HEAD):]
    listed = [int(x) for x in re.match(r'\s*\(([0-9, ]+)\)', after).group(1).split(',')]
    assert listed == list(fz.KNOWN_RED), 'the known list in D-912 %s is not KNOWN_RED %s' % (listed, list(fz.KNOWN_RED))


def clause_exit_zero(fz):
    """only when the gate exited 0"""
    assert not _judge(fz)[0], 'a clean gate is refused'
    assert _judge(fz, exit_code=1)[0], 'exit 1 is not refused'
    assert _judge(fz, exit_code=2)[0], 'exit 2 is not refused'


def clause_every_check_ran(fz):
    """every check ran"""
    assert _judge(fz, drop=7)[0], 'a missing check is not refused'
    text, summary = _rows(fz.KNOWN_RED)
    assert fz.judge(text, dict(summary, not_run=[3]), {'tree': TREE}, TREE, 0)[0], 'a not_run entry is not refused'


def clause_reds_equal_known_list(fz):
    """the reds equal the known list (no more, no fewer)"""
    assert _judge(fz, red=list(fz.KNOWN_RED) + [40])[0], 'one more red is not refused'
    assert _judge(fz, red=list(fz.KNOWN_RED)[1:])[0], 'one known red turned green is not refused'
    assert not _judge(fz, red=list(fz.KNOWN_RED))[0], 'the exact known list is refused'


def clause_tree_equals(fz):
    """the evidence tree equals the commit's tree"""
    assert _judge(fz, tree='b' * 40)[0], 'a different evidence tree is not refused'
    assert not _judge(fz, tree=TREE, commit_tree=TREE)[0], 'the equal tree is refused'


def clause_skip_recorded(fz):
    """SKIP checks are neither pass nor red and are recorded"""
    reasons, facts = _judge(fz, skip=(1, 3))
    assert not reasons, 'a SKIP check refuses the freeze'
    assert facts['skip'] == [1, 3], 'the skipped checks are not recorded'
    assert facts['pass'] == facts['checks'] - len(fz.KNOWN_RED) - 2, 'a SKIP counted as pass or red'


def clause_refused_file_and_one_alert(fz):
    """Otherwise FREEZE_REFUSED.json and one ALERT line"""
    alerts = []
    with tempfile.TemporaryDirectory() as tmp:
        for _ in range(2):
            fz._refuse(tmp, 'v-rule-test', TREE, ['rule fixture'], {'extra': [9]}, lambda key, text: alerts.append(text))
        body = json.loads((Path(tmp) / fz.REFUSED_NAME).read_text(encoding='utf-8'))
    assert body['reasons'] == ['rule fixture'], 'FREEZE_REFUSED.json does not carry the reasons'
    assert len(alerts) == 1, '%d ALERT lines for one refusal, not one' % len(alerts)


def clause_tag_never_moved(fz):
    """the tag is never moved: a tag on another commit refuses, and no tag command is run"""
    calls = []
    other = 'c' * 40
    commit = 'd' * 40

    def fake_git(repo, *args):
        calls.append(args)
        if args[:3] == ('rev-parse', '-q', '--verify'):
            return 0, other, ''
        if args[:1] == ('rev-parse',) and args[-1].endswith('^{commit}'):
            return 0, commit, ''
        if args[:1] == ('rev-parse',):
            return 0, TREE, ''
        return 0, '', ''
    text, summary = _rows(fz.KNOWN_RED)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / 'launch.py').write_text("COMMIT = 'dddddddd'\nBUNDLE = 'GR_rule'\n", encoding='utf-8')
        run = folder / 'run_part' / 'GR_rule'
        run.mkdir(parents=True)
        (run / 'workload_return.json').write_text('{"exit_code": 0}', encoding='utf-8')
        with tarfile.open(run / 'collected_evidence.tar.gz', 'w:gz') as tf:
            for name, data in (('evidence/gate/results.jsonl', text), ('evidence/gate/summary.json', json.dumps(summary)),
                               ('evidence/gate/git_checkout.json', json.dumps({'tree': TREE}))):
                raw = data.encode('utf-8')
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                tf.addfile(info, io.BytesIO(raw))
        real = fz.git
        fz.git = lambda repo, *args: GIT_FILTER(fake_git(repo, *args), args) if GIT_FILTER else fake_git(repo, *args)
        try:
            state, _ = fz.run(folder, 'v-rule-test', tmp, alert=lambda key, text: None)
        finally:
            fz.git = real
    assert state == 'refused', 'a tag on another commit is not refused (%s)' % state
    assert not [c for c in calls if c[:1] == ('tag',)], 'a tag command was run'


CLAUSES = (('the rule is quoted from D-912 and its known list is KNOWN_RED', clause_quote),
           ('only when the gate exited 0', clause_exit_zero),
           ('every check ran', clause_every_check_ran),
           ('the reds equal the known list', clause_reds_equal_known_list),
           ('the evidence tree equals the commit tree', clause_tree_equals),
           ('SKIP checks are neither pass nor red and are recorded', clause_skip_recorded),
           ('otherwise FREEZE_REFUSED.json and one ALERT line', clause_refused_file_and_one_alert),
           ('the tag is never moved', clause_tag_never_moved))


def run_all(fz):
    """[(clause, True/False, detail)] for every clause; an exception is a red clause."""
    out = []
    fz._IN_RULE_TESTS = True
    try:
        for name, fn in CLAUSES:
            try:
                fn(fz)
                out.append((name, True, ''))
            except Exception as exc:  # noqa: BLE001 - any failure is a red clause
                out.append((name, False, '%s: %s' % (type(exc).__name__, str(exc)[:200])))
    finally:
        fz._IN_RULE_TESTS = False
    return out


def first_red(fz):
    """The first red clause as 'name' or None."""
    for name, ok, _ in run_all(fz):
        if not ok:
            return name
    return None


if __name__ == '__main__':
    sys.path.insert(0, str(HERE))
    import freeze_tag as module
    results = run_all(module)
    for name, ok, detail in results:
        print('%s  %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    raise SystemExit(0 if all(ok for _, ok, _ in results) else 1)
