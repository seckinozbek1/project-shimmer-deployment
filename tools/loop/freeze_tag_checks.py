#!/usr/bin/env python3
"""Proofs for tools/loop/freeze_tag.py (D-902, D-911), on invented fixtures only.

Each fixture is a temporary directory holding a throwaway git repository (one commit) and a launch folder shaped like
ROUTE_GATE_D_dab39cc4 (launch.py with COMMIT and BUNDLE, run_part/<BUNDLE>/workload_return.json and
collected_evidence.tar.gz holding evidence/gate/results.jsonl, summary.json, git_checkout.json). No real folder, tag,
ledger or ALERT.md is touched; the real repository is never opened.

  green_tags             known reds only, exit 0, tree matches: an annotated tag on the commit and FREEZE_OK.json
  unexpected_red         one more red check: no tag, FREEZE_REFUSED.json naming it, one ALERT.md line at the top
  missing_check          a results line absent from results.jsonl: no tag, REFUSED
  workload_failed        workload_return exit code 1: no tag, REFUSED
  tree_mismatch          the gate ran another tree than the commit's: no tag, REFUSED
  idempotent             a second run after success changes nothing (same tag object, same FREEZE_OK bytes)
  tag_never_moves        the tag exists on another commit: refused, the tag stays where it was
  pending_is_silent      no workload_return yet: nothing written, nothing tagged

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes).
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import freeze_tag as fz  # noqa: E402
import freeze_rule_tests as frt  # noqa: E402
import mechanism_common as mc  # noqa: E402

TAG = 'v-fixture-freeze'
BUNDLE = 'GX_fixture_FULL'
TOTAL = 60
SKIPS = (1, 3)


def sh(repo, *args):
    p = subprocess.run(['git', '-C', str(repo), '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid'] + list(args),
                       capture_output=True, text=True, creationflags=mc.no_window())
    assert p.returncode == 0, (args, p.stderr)
    return p.stdout.strip()


class Fixture:
    def __init__(self, red=None, drop=None, exit_code=0, wrong_tree=False, with_return=True, rules=False):
        self.rules = rules   # True: the real rule tests run before a tag (D-923); False: they are stepped aside so each older proof tests the judge alone
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base = Path(self.tmp.name)
        self.repo = base / 'repo'
        self.repo.mkdir()
        sh(self.repo, 'init', '-q')
        (self.repo / 'a.txt').write_text('one\n', encoding='utf-8')
        sh(self.repo, 'add', 'a.txt')
        sh(self.repo, 'commit', '-q', '-m', 'first')
        (self.repo / 'a.txt').write_text('two\n', encoding='utf-8')
        sh(self.repo, 'commit', '-q', '-am', 'second')
        self.first = sh(self.repo, 'rev-parse', 'HEAD~1')
        self.commit = sh(self.repo, 'rev-parse', 'HEAD')
        tree = sh(self.repo, 'rev-parse', 'HEAD^{tree}')
        self.folder = base / 'ROUTE_GATE_X_fixture'
        run = self.folder / 'run_part' / BUNDLE
        run.mkdir(parents=True)
        (self.folder / 'launch.py').write_text("COMMIT = '%s'\nBUNDLE = '%s'\n" % (self.commit[:8], BUNDLE), encoding='utf-8')
        red = sorted(set(fz.KNOWN_RED) | set(red or ()))
        numbers = list(range(TOTAL)) + [n for n in red if n >= TOTAL]
        status = {n: ('FAIL' if n in red else ('SKIP' if n in SKIPS else 'PASS')) for n in numbers}
        lines = [json.dumps({'number': n, 'title': 'check %d' % n, 'status': status[n], 'seconds': 0.1})
                 for n in numbers if n != drop]
        counts = {k: sum(1 for v in status.values() if v == k) for k in ('PASS', 'FAIL', 'SKIP')}   # the summary counted every check
        summary = {'arm': 'G', 'counts': counts, 'execution_integrity_passed': True, 'not_run': [], 'reasons': [], 'unexpected': []}
        checkout = {'commit': 'f' * 40, 'tree': ('0' * 40) if wrong_tree else tree, 'status_clean': True}
        with tarfile.open(run / 'collected_evidence.tar.gz', 'w:gz') as tf:
            for name, data in (('evidence/gate/results.jsonl', '\n'.join(lines) + '\n'),
                               ('evidence/gate/summary.json', json.dumps(summary)),
                               ('evidence/gate/git_checkout.json', json.dumps(checkout))):
                raw = data.encode('utf-8')
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                tf.addfile(info, io.BytesIO(raw))
        if with_return:
            (run / 'workload_return.json').write_text(json.dumps({'exit_code': exit_code}), encoding='utf-8')
        self.alerts = []

    def run(self, **kw):
        alert = lambda key, text: self.alerts.append(text)  # noqa: E731
        if self.rules:
            return fz.run(self.folder, TAG, self.repo, alert=alert, **kw)
        with patch.object(frt, 'first_red', lambda module: None):
            return fz.run(self.folder, TAG, self.repo, alert=alert, **kw)

    def tag_type(self):
        p = subprocess.run(['git', '-C', str(self.repo), 'cat-file', '-t', 'refs/tags/' + TAG], capture_output=True, text=True,
                           creationflags=mc.no_window())
        return p.stdout.strip() if p.returncode == 0 else None

    def tag_target(self):
        p = subprocess.run(['git', '-C', str(self.repo), 'rev-parse', '-q', '--verify', 'refs/tags/%s^{commit}' % TAG],
                           capture_output=True, text=True, creationflags=mc.no_window())
        return p.stdout.strip() if p.returncode == 0 else None

    def files(self):
        return (fz.OK_NAME in [p.name for p in self.folder.iterdir()], fz.REFUSED_NAME in [p.name for p in self.folder.iterdir()])

    def refused_text(self):
        p = self.folder / fz.REFUSED_NAME
        return p.read_text(encoding='utf-8') if p.exists() else ''

    def close(self):
        self.tmp.cleanup()


def caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return 'raised %s' % type(exc).__name__


# ---- green_tags
def observe_green_tags():
    f = Fixture(rules=True)
    try:
        state, _ = f.run()
        ok = json.loads((f.folder / fz.OK_NAME).read_text(encoding='utf-8')) if (f.folder / fz.OK_NAME).exists() else {}
        return state, f.tag_type(), f.tag_target() == f.commit, f.files(), ok.get('commit') == f.commit and ok.get('tag') == TAG
    finally:
        f.close()


def expected_green_tags():
    return 'ok', 'tag', True, (True, False), True


def neutralise_green_tags():
    real = fz.git

    def no_tag(repo, *args):
        if args[:1] == ('tag',):
            return 0, '', ''
        return real(repo, *args)
    return patch.object(fz, 'git', no_tag)


# ---- unexpected_red
def observe_unexpected_red():
    f = Fixture(red=[40])
    try:
        state, _ = f.run()
        text = f.refused_text()
        return state, f.tag_type(), f.files(), '40' in text, len(f.alerts), bool(f.alerts) and '40' in f.alerts[0]
    finally:
        f.close()


def expected_unexpected_red():
    return 'refused', None, (False, True), True, 1, True


def neutralise_unexpected_red():
    real = fz.judge

    def loose(*a, **k):
        reasons, facts = real(*a, **k)
        return [r for r in reasons if not r.startswith('unexpected')], facts
    return patch.object(fz, 'judge', loose)


# ---- alert_line (the shipped main writes one dated line at the top of ALERT.md)
def observe_alert_line():
    f = Fixture(red=[40])
    base = Path(tempfile.mkdtemp())
    try:
        private = base / 'private'
        private.mkdir()
        (private / 'ALERT.md').write_text('# ALERT\n\nolder line\n', encoding='utf-8')
        with patch.object(mc, 'PRIVATE', private), patch.object(mc, 'TRACE', private / 'trace.jsonl'), \
                patch.object(mc, 'ALERT', private / 'ALERT.md'), patch.object(mc, 'ALERT_STATE', private / 'st.json'), \
                contextlib.redirect_stdout(io.StringIO()):
            code = fz.main([str(f.folder), TAG, '--repo', str(f.repo)])
            code2 = fz.main([str(f.folder), TAG, '--repo', str(f.repo)])
        lines = (private / 'ALERT.md').read_text(encoding='utf-8').splitlines()
        first = [x for x in lines if x.strip()][1]
        return code, code2, 'REFUSED' in first, lines.count(first) == 1, 'older line' in lines[-1]
    finally:
        f.close()


def expected_alert_line():
    return 1, 1, True, True, True


def neutralise_alert_line():
    return patch.object(mc, 'alert', lambda *a, **k: False)


# ---- missing_check
def observe_missing_check():
    f = Fixture(drop=7)
    try:
        state, _ = f.run()
        return state, f.tag_type(), f.files(), 'missing checks' in f.refused_text()
    finally:
        f.close()


def expected_missing_check():
    return 'refused', None, (False, True), True


def neutralise_missing_check():
    real = fz.judge

    def loose(*a, **k):
        reasons, facts = real(*a, **k)
        return [r for r in reasons if not r.startswith('missing')], facts
    return patch.object(fz, 'judge', loose)


# ---- workload_failed
def observe_workload_failed():
    f = Fixture(exit_code=1)
    try:
        state, _ = f.run()
        return state, f.tag_type(), f.files()
    finally:
        f.close()


def expected_workload_failed():
    return 'refused', None, (False, True)


def neutralise_workload_failed():
    real = fz.judge

    def loose(results_text, summary, checkout, tree, exit_code, *a, **k):
        return real(results_text, summary, checkout, tree, 0, *a, **k)
    return patch.object(fz, 'judge', loose)


# ---- tree_mismatch
def observe_tree_mismatch():
    f = Fixture(wrong_tree=True)
    try:
        state, _ = f.run()
        return state, f.tag_type(), f.files()
    finally:
        f.close()


def expected_tree_mismatch():
    return 'refused', None, (False, True)


def neutralise_tree_mismatch():
    real = fz.judge

    def loose(results_text, summary, checkout, tree, *a, **k):
        return real(results_text, summary, dict(checkout, tree=tree), tree, *a, **k)
    return patch.object(fz, 'judge', loose)


# ---- idempotent
def observe_idempotent():
    f = Fixture()
    try:
        f.run()
        before = hashlib.sha256((f.folder / fz.OK_NAME).read_bytes()).hexdigest()
        obj = subprocess.run(['git', '-C', str(f.repo), 'rev-parse', 'refs/tags/' + TAG], capture_output=True, text=True,
                             creationflags=mc.no_window()).stdout.strip()
        import time
        time.sleep(1.1)   # a rewrite would carry a later clock time
        state, _ = f.run()
        after = hashlib.sha256((f.folder / fz.OK_NAME).read_bytes()).hexdigest() if (f.folder / fz.OK_NAME).exists() else None
        obj2 = subprocess.run(['git', '-C', str(f.repo), 'rev-parse', 'refs/tags/' + TAG], capture_output=True, text=True,
                              creationflags=mc.no_window()).stdout.strip()
        return state, before == after, obj == obj2
    finally:
        f.close()


def expected_idempotent():
    return 'done', True, True


def neutralise_idempotent():
    return _no_done_check()


def _no_done_check():
    real = fz.Path.exists

    def exists(self):
        if self.name == fz.OK_NAME and self.parent.name.startswith('ROUTE_GATE'):
            return False
        return real(self)
    return patch.object(fz.Path, 'exists', exists)


# ---- tag_never_moves
def observe_tag_never_moves():
    f = Fixture()
    try:
        sh(f.repo, 'tag', '-a', TAG, f.first, '-m', 'earlier')
        state, _ = f.run()
        return state, f.tag_target() == f.first, f.files()
    finally:
        f.close()


def expected_tag_never_moves():
    return 'refused', True, (False, True)


def neutralise_tag_never_moves():
    real = fz.git

    def force(repo, *args):
        if args[:3] == ('rev-parse', '-q', '--verify'):
            return 1, '', ''
        if args[:2] == ('tag', '-a'):
            args = ('tag', '-f') + args[1:]
        return real(repo, *args)
    return patch.object(fz, 'git', force)


# ---- pending_is_silent
def observe_pending_is_silent():
    f = Fixture(with_return=False)
    try:
        state, _ = f.run()
        return state, f.tag_type(), f.files(), len(f.alerts)
    finally:
        f.close()


def expected_pending_is_silent():
    return 'pending', None, (False, False), 0


def neutralise_pending_is_silent():
    return patch.object(Path, 'is_file', lambda self: True)


# ---- rule tests (D-923): the written rule of D-912, clause by clause, run before a tag is made
def _wrap_judge(drop):
    real = fz.judge

    def loose(*a, **k):
        reasons, facts = real(*a, **k)
        return [r for r in reasons if not drop(r)], facts
    return loose


def _red_clauses():
    return tuple(name for name, ok, _ in frt.run_all(fz) if not ok)


RULE_NEUTRALISE = {
    'the rule is quoted from D-912 and its known list is KNOWN_RED': lambda: patch.object(fz, 'KNOWN_RED', tuple(fz.KNOWN_RED) + (1,)),
    'only when the gate exited 0': lambda: patch.object(fz, 'judge', _wrap_judge(lambda r: r.startswith('workload exit'))),
    'every check ran': lambda: patch.object(fz, 'judge', _wrap_judge(lambda r: r.startswith('missing') or 'not_run' in r)),
    'the reds equal the known list': lambda: patch.object(fz, 'judge', _wrap_judge(lambda r: r.startswith('unexpected') or r.startswith('known red'))),
    'the evidence tree equals the commit tree': lambda: patch.object(fz, 'judge', _wrap_judge(lambda r: r.startswith('evidence git_checkout'))),
    'SKIP checks are neither pass nor red and are recorded': lambda: patch.object(
        fz, 'judge', lambda *a, **k: (lambda r, f: (r + ['skipped'] if f['skip'] else r, dict(f, skip=[])))(*fz_real_judge(*a, **k))),
    'otherwise FREEZE_REFUSED.json and one ALERT line': lambda: patch.object(fz, '_refuse', lambda *a, **k: 'no file, no alert'),
    'the tag is never moved': lambda: _tag_moves(),
}
fz_real_judge = fz.judge


def _tag_moves():
    """A tag check blind to an existing tag: the verify call answers 'absent'."""
    def blind(result, args):
        return (1, '', '') if args[:3] == ('rev-parse', '-q', '--verify') else result
    return patch.object(frt, 'GIT_FILTER', blind)


def observe_rule_tests_green():
    return _red_clauses()


def expected_rule_tests_green():
    return ()


def neutralise_rule_tests_green():
    return patch.object(fz, 'KNOWN_RED', tuple(fz.KNOWN_RED) + (1,))


def observe_each_clause_goes_red_when_neutralised():
    seen = {}
    for clause, make in RULE_NEUTRALISE.items():
        with make():
            seen[clause] = clause in _red_clauses()
    return tuple(sorted(seen.items()))


def expected_each_clause_goes_red_when_neutralised():
    return tuple(sorted((c, True) for c in RULE_NEUTRALISE))


def neutralise_each_clause_goes_red_when_neutralised():
    return patch.object(frt, 'first_red', lambda m: None) if False else patch.object(frt, 'run_all', lambda m: [])


def observe_red_rule_test_blocks_the_tag():
    f = Fixture(rules=True)
    try:
        failing = frt.CLAUSES + (('a fixture clause', lambda m: (_ for _ in ()).throw(AssertionError('red'))),)
        with patch.object(frt, 'CLAUSES', failing):
            state, _ = f.run()
        body = f.refused_text()
        return state, f.tag_type(), f.files(), 'rule test red: a fixture clause' in body, len(f.alerts)
    finally:
        f.close()


def expected_red_rule_test_blocks_the_tag():
    return 'refused', None, (False, True), True, 1


def neutralise_red_rule_test_blocks_the_tag():
    return patch.object(fz, '_IN_RULE_TESTS', True)



PROOFS = ('green_tags', 'unexpected_red', 'alert_line', 'missing_check', 'workload_failed', 'tree_mismatch', 'idempotent',
          'tag_never_moves', 'pending_is_silent', 'rule_tests_green',
          'each_clause_goes_red_when_neutralised', 'red_rule_test_blocks_the_tag')


def run_all():
    done, space = [], globals()
    for name in PROOFS:
        observe, expected, neutralise = space['observe_' + name], space['expected_' + name], space['neutralise_' + name]
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                first = observe()
                with neutralise():
                    broken = caught(observe)
                again = observe()
        except Exception as exc:  # noqa: BLE001
            return 'FAIL', '%s: %s %s' % (name, type(exc).__name__, str(exc)[:300])
        if first != expected():
            return 'FAIL', '%s as built: %s' % (name, str(first)[:600])
        if broken == expected():
            return 'FAIL', '%s still passes when neutralised' % name
        if again != expected():
            return 'FAIL', '%s after restore: %s' % (name, str(again)[:400])
        done.append('%s (neutralised: %s)' % (name, str(broken)[:120]))
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass, throwaway repository only: %s' % (len(done), '; '.join(done))


if __name__ == '__main__':
    status, detail = run_all()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
