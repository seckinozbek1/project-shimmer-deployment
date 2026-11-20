#!/usr/bin/env python3
"""Check 519 (lane/launch-chain): the watchdog's issue and remote freshness checks (tools/loop/sync_watch.py),
Seckin 18 November 2026 13:53.

On invented fixtures in a temporary directory: a DECISIONS.md and a FOR_SECKIN.md with written times, a gate
folder with an evidence result, and a fake runner standing in for git and gh (it records every argument list, so
the proofs also see that nothing is fetched or pushed and that the private and public remotes are never mixed).
Proofs:

  issue_update_due      a decision or result over 60 minutes old with no issue update after it alerts "issue update
                        due: D-xxx"; an issue update after it, or an event under 60 minutes, does not
  origin_only           gh is called only for the project repository, owner and name pinned; another origin is
                        refused and gh not called
  unbacked_commits      commits on the lead tip on no backup-private ref alert after 2 hours, read from the
                        backup-private refs only
  green_gate_on_origin  the newest green gate's commit not on origin/main alerts after 1 hour; a red gate is
                        ignored; a commit on origin/main does not alert; only origin/main is read
  gate_commit_checked   a gate commit that is not 7 to 40 hex digits never reaches git; a good one follows
                        --end-of-options
  exported_gate_counts_pushed  a green gate whose bound source commit PUSH_RECORD.md names as exported, or whose
                        tree is an exported commit's tree, counts as pushed (no alert); another export, or none,
                        still alerts
  issue_sweep_due       D-839: no sweep record alerts "issue sweep due"; a record older than the decision alerts;
                        a fresh record does not; a record over 24 hours old alerts with no decision at all
  sweep_record          tools/loop/issue_sweep.py record writes the per-milestone counts from a faked gh api reply
                        (project origin only, another origin refused and gh not called), and line gives the
                        FOR_SECKIN line and the panel REL gh object; the fresh record then clears the sweep alert

Each proof is run as built (passes), neutralised (must fail), restored and run again (passes).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mechanism_common as mc  # noqa: E402
import sync_watch as sw  # noqa: E402

NOW = dt.datetime(2026, 11, 18, 14, 0, tzinfo=dt.timezone(dt.timedelta(hours=3)))
PROJECT = 'https://github.com/seckinozbek1/project-shimmer-deployment.git'


def stamp(minutes_ago):
    return (NOW - dt.timedelta(minutes=minutes_ago)).strftime('%Y-%m-%d %H:%M %z')


class Fake:
    def __init__(self, origin=PROJECT, issues=(), unbacked=(), on_origin=(), trees=None):
        self.origin, self.issues, self.unbacked, self.on_origin = origin, list(issues), list(unbacked), set(on_origin)
        self.trees = dict(trees or {})     # local commit: its tree (git rev-parse <commit>^{tree})
        self.calls = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        if argv[:1] == ['gh']:
            return 0, json.dumps([{'number': n, 'updatedAt': u} for n, u in self.issues])
        if 'get-url' in argv:
            return 0, self.origin + '\n'
        if 'log' in argv:
            if '--remotes=backup-private' not in argv:
                return 0, ''     # the fake's other remotes hold every commit
            return 0, ''.join('%s %d\n' % (sha, int((NOW - dt.timedelta(hours=h)).timestamp())) for sha, h in self.unbacked)
        if 'merge-base' in argv:
            return (0 if argv[-2] in self.on_origin and argv[-1] == 'refs/remotes/origin/main' else 1), ''
        if 'rev-parse' in argv and argv[-1].endswith('^{tree}'):
            tree = self.trees.get(argv[-1][:-len('^{tree}')])
            return (0, tree + '\n') if tree else (1, '')
        return 1, ''

    def pushed_or_fetched(self):
        return any(a in ('push', 'fetch', 'pull') for argv in self.calls for a in argv)


class Fixture:
    def __init__(self, decisions='', results='', sweep_min=1):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.base = Path(self.tmp.name)
        (self.base / 'docs' / 'loop' / 'private').mkdir(parents=True)
        self.private = self.base / 'docs' / 'loop' / 'private'
        (self.base / 'docs' / 'loop' / 'DECISIONS.md').write_text(decisions, encoding='utf-8')
        (self.private / 'FOR_SECKIN.md').write_text(results, encoding='utf-8')
        if sweep_min is not None:     # the other proofs run with a fresh sweep record, so only their own alert shows
            (self.private / 'issue_sweep.json').write_text(json.dumps(
                {'at': (NOW - dt.timedelta(minutes=sweep_min)).isoformat(), 'closed': 0, 'updated': 0,
                 'milestones': {}}), encoding='utf-8')
        self.root = self.base / 'external' / 's05'
        self.root.mkdir(parents=True)
        self.patches = [patch.object(mc, 'PRIVATE', self.private), patch.object(mc, 'TRACE', self.private / 'trace.jsonl'),
                        patch.object(mc, 'ALERT', self.private / 'ALERT.md'),
                        patch.object(mc, 'ALERT_STATE', self.private / 'alert_state.json'),
                        patch.object(mc, 'MAIN', self.base)]

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def gate(self, name, commit, hours_ago, tree=None, bound=None, **result):
        ev = self.root / name / 'ex_part' / 'evidence'
        (ev / 'gate').mkdir(parents=True)
        body = dict({'arm': 'G', 'execution_integrity_passed': True, 'failing': [], 'unexpected': []}, **result)
        (ev / 'result.json').write_text(json.dumps(body), encoding='utf-8')
        (ev / 'gate' / 'git_checkout.json').write_text(json.dumps(dict({'commit': commit}, **({'tree': tree} if tree else {}))),
                                                        encoding='utf-8')
        if bound:
            (self.root / name / 'launch.py').write_text("COMMIT = '%s'  # the bound source commit\n" % bound, encoding='utf-8')
        t = (NOW - dt.timedelta(hours=hours_ago)).timestamp()
        os.utime(ev / 'result.json', (t, t))

    def check(self, fake):
        return sw.check(now=NOW, main=self.base, private=self.private, root=self.root, runner=fake)

    def alert_text(self):
        try:
            return mc.ALERT.read_text(encoding='utf-8')
        except OSError:
            return ''

    def traces(self):
        return [x.get('result') for x in mc.read_trace() if x.get('mechanism') == sw.NAME]


def decisions(*entries):
    return ''.join('## %s: a decision\nWritten %s by the lead.\n- What: x\n\n' % (d, stamp(m)) for d, m in entries)


def results(*minutes):
    return '# For Seckin\n\n' + ''.join('## %s: a verified result\n\ntext\n\n' % stamp(m) for m in minutes)


def iso_ago(minutes):
    return (NOW - dt.timedelta(minutes=minutes)).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def caught(fn):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        return 'raised %s' % type(exc).__name__


def observe_issue_update_due():
    out = []
    for ds, rs, issue_min in (([('D-900', 90)], [], 100),        # decision 90 min old, issue before it: due
                              ([('D-900', 90)], [], 80),         # issue after it: not due
                              ([('D-900', 30)], [], 100),        # decision under 60 minutes: not yet
                              ([('D-900', 120)], [75], 100)):    # the newer verified result is due
        with Fixture(decisions(*ds), results(*rs)) as f:
            r = f.check(Fake(issues=[(7, iso_ago(issue_min))]))
            out.append((r['issues'].get('due'), 'issue update due: ' in f.alert_text(), f.traces()))
    return out


def expected_issue_update_due():
    return [('D-900', True, ['alert']), (None, False, ['ok']), (None, False, ['ok']),
            ('result %s' % stamp(75)[:16], True, ['alert'])]


def neutralise_issue_update_due():
    return patch.object(sw, 'decision_events', lambda text: [])


def observe_origin_only():
    out = []
    for origin in (PROJECT, 'https://github.com/seckinozbek1/some-other-repo.git',
                   'https://github.com/someone-else/project-shimmer-deployment.git'):
        with Fixture(decisions(('D-901', 90))) as f:
            fake = Fake(origin=origin)
            r = f.check(fake)
            gh = [c for c in fake.calls if c[0] == 'gh']
            out.append((r['issues'].get('due'), len(gh), gh[0][gh[0].index('--repo') + 1] if gh else None))
    return out


def expected_origin_only():
    return [('D-901', 1, 'seckinozbek1/project-shimmer-deployment'), (None, 0, None), (None, 0, None)]


def neutralise_origin_only():
    return patch.object(sw, 'PROJECT_OWNER', 'someone-else')


def observe_unbacked_commits():
    with Fixture() as f:
        fake = Fake(unbacked=[('a' * 40, 1), ('b' * 40, 3)])
        r = f.check(fake)
        logs = [c for c in fake.calls if 'log' in c]
        return (r['backup_private'], 'not on any backup-private ref' in f.alert_text(),
                all('--remotes=backup-private' in c and not any('origin' in a for a in c) for c in logs),
                fake.pushed_or_fetched())


def expected_unbacked_commits():
    return {'unbacked': 2, 'late': ['b' * 40]}, True, True, False


def neutralise_unbacked_commits():
    return patch.object(sw, 'BACKUP_REFS', '--remotes=origin')


def observe_green_gate_on_origin():
    out = []
    for gates, on_origin in (([('ROUTE_GATE_old', 'c' * 40, 5, {}), ('ROUTE_GATE_new', 'd' * 40, 2, {}),
                               ('ROUTE_GATE_red', 'e' * 40, 1.5, {'unexpected': [12]})], ()),
                             ([('ROUTE_GATE_new', 'd' * 40, 2, {})], ('d' * 40,)),
                             ([('ROUTE_GATE_new', 'd' * 40, 0.5, {})], ())):
        with Fixture() as f:
            for g in gates:
                f.gate(g[0], g[1], g[2], **g[3])
            fake = Fake(on_origin=on_origin)
            r = f.check(fake)
            bases = [c for c in fake.calls if 'merge-base' in c]
            out.append((r['origin_main'].get('late'), r['origin_main'].get('commit'),
                        'not on origin/main' in f.alert_text(),
                        all(c[-1] == 'refs/remotes/origin/main' for c in bases), fake.pushed_or_fetched()))
    return out


def expected_green_gate_on_origin():
    return [('d' * 40, 'd' * 40, True, True, False), (None, 'd' * 40, False, True, False),
            (None, 'd' * 40, False, True, False)]


def neutralise_green_gate_on_origin():
    return patch.object(sw, 'green', lambda result: result.get('arm') == 'G')


def observe_gate_commit_checked():
    out = []
    for commit in ('--output=/tmp/x', 'zz12345', 'f' * 41, 'abc1234'):
        with Fixture() as f:
            f.gate('ROUTE_GATE_new', commit, 2)
            fake = Fake()
            r = f.check(fake)
            bases = [c for c in fake.calls if 'merge-base' in c]
            out.append((len(bases), bool(r['origin_main'].get('error')),
                        all(c[c.index('--end-of-options') + 1] == commit for c in bases if '--end-of-options' in c)
                        and all('--end-of-options' in c for c in bases)))
    return out


def expected_gate_commit_checked():
    return [(0, True, True), (0, True, True), (0, True, True), (1, False, True)]


def neutralise_gate_commit_checked():
    import re
    return patch.object(sw, 'COMMIT', re.compile(r'.+'))


PUSH_ENTRY = ('# Push record\n\n## 2026-11-18 14:47 +0300: the code snapshot of loop %s\n\nmain 3680687 to 843112c2: one '
              'snapshot commit of loop %s made by tools/loop/export_public_tree.py. Tree bbc463f2.\n')
GATE_COMMIT = 'a905015e47af6e0b5d81df6b0e44229ab17c0034'     # built on the instance: in no local repository
TREE = 'e880f3e152f5986cbadaafe9445313aac29d33fb'


def observe_exported_gate_counts_pushed():
    out = []
    for record, bound, tree, trees in (
            (PUSH_ENTRY % ('3ca7fe8e', '3ca7fe8e'), '3ca7fe8e', None, {}),          # bound commit named as exported
            (PUSH_ENTRY % ('3ca7fe8e', '3ca7fe8e'), None, TREE, {'3ca7fe8e': TREE}),  # exported tree equals the gate's
            (PUSH_ENTRY % ('90c3ed36', '90c3ed36'), '3ca7fe8e', TREE, {'90c3ed36': 'f' * 40}),  # another export only
            ('', None, None, {})):                                                     # no export at all
        with Fixture() as f:
            (f.private / 'PUSH_RECORD.md').write_text(record, encoding='utf-8')
            f.gate('ROUTE_GATE_x', GATE_COMMIT, 2, tree=tree, bound=bound)
            fake = Fake(trees=trees)
            r = f.check(fake)['origin_main']
            out.append((r.get('late'), bool(r.get('exported')), 'not on origin/main' in f.alert_text(),
                        fake.pushed_or_fetched()))
    return out


def expected_exported_gate_counts_pushed():
    return [(None, True, False, False), (None, True, False, False), (GATE_COMMIT, False, True, False),
            (GATE_COMMIT, False, True, False)]


def neutralise_exported_gate_counts_pushed():
    return patch.object(sw, 'exported_sources', lambda private: [])


def observe_issue_sweep_due():
    out = []
    for ds, sweep_min in (([('D-902', 90)], None),          # no sweep record: due
                          ([('D-902', 90)], 120),           # the sweep is older than the decision: due
                          ([('D-902', 90)], 10),            # a fresh sweep after the decision: not due
                          ([], 25 * 60)):                   # no decision, but the last sweep is over 24 hours old
        with Fixture(decisions(*ds), sweep_min=sweep_min) as f:
            fake = Fake(issues=[(7, iso_ago(5))])            # the issue update itself is after the decision
            r = f.check(fake)
            out.append((bool(r['issue_sweep'].get('due')), r['issue_sweep'].get('last_sweep') is not None,
                        'issue sweep due: ' in f.alert_text(), f.traces(), fake.pushed_or_fetched()))
    return out


def expected_issue_sweep_due():
    return [(True, False, True, ['alert'], False), (True, True, True, ['alert'], False),
            (False, True, False, ['ok'], False), (True, True, True, ['alert'], False)]


def neutralise_issue_sweep_due():
    return patch.object(sw, 'sweep_time', lambda private: NOW)


MILESTONES = [{'title': 'v1.0-alpha', 'open_issues': 4, 'closed_issues': 11, 'description': 'not read'},
              {'title': 'v1.0-beta', 'open_issues': 7, 'closed_issues': 2},
              {'title': 'v1.0', 'open_issues': 9, 'closed_issues': 0},
              {'title': 'v1.1', 'open_issues': 3, 'closed_issues': 1}]


class FakeGhApi(Fake):
    def __call__(self, argv):
        if argv[:2] == ['gh', 'api']:
            self.calls.append(list(argv))
            return 0, json.dumps(MILESTONES)
        return super().__call__(argv)


def observe_sweep_record():
    import issue_sweep
    out = []
    for origin in (PROJECT, 'https://github.com/someone-else/project-shimmer-deployment.git'):
        with Fixture(sweep_min=None) as f:
            fake = FakeGhApi(origin=origin)
            try:
                issue_sweep.record(5, 3, main=f.base, private=f.private, runner=fake, now=NOW)
            except issue_sweep.SweepError:
                pass
            body = issue_sweep.load(f.private)
            gh = [c for c in fake.calls if c[0] == 'gh']
            line = issue_sweep.for_seckin_line(body) if body else None
            panel = issue_sweep.panel_gh(body) if body else None
            fresh = f.check(Fake(issues=[(7, iso_ago(5))]))['issue_sweep'].get('due') if body else 'no record'
            out.append((body and body['milestones'], line, panel and panel['alpha'], panel and panel['v11']['open'],
                        [c[2] for c in gh], fresh, fake.pushed_or_fetched()))
    return out


def expected_sweep_record():
    at = NOW.isoformat(timespec='seconds')
    return [({'v1.0-alpha': {'open': 4, 'closed': 11}, 'v1.0-beta': {'open': 7, 'closed': 2},
              'v1.0': {'open': 9, 'closed': 0}, 'v1.1': {'open': 3, 'closed': 1}},
             'GitHub taraması: 5 konu kapandı, 3 güncellendi; açık: v1.0-alpha 4, v1.0-beta 7, v1.0 9, v1.1 3',
             {'open': 4, 'closed': 11, 'at': at}, 3,
             ['repos/seckinozbek1/project-shimmer-deployment/milestones?state=all&per_page=100'], None, False),
            (None, None, None, None, [], 'no record', False)]


def neutralise_sweep_record():
    import issue_sweep
    return patch.object(issue_sweep, 'milestone_counts', lambda main=None, runner=None: {})


PROOFS = ('issue_update_due', 'origin_only', 'unbacked_commits', 'green_gate_on_origin', 'gate_commit_checked',
          'exported_gate_counts_pushed', 'issue_sweep_due', 'sweep_record')


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
        done.append('%s (neutralised: %s)' % (name, str(broken)[:160]))
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass, no git or gh call: %s' % (len(done), '; '.join(done))


if __name__ == '__main__':
    status, detail = run_all()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
