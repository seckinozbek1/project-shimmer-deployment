#!/usr/bin/env python3
"""Freeze tag after a green full gate (D-902, D-911; Seckin G-20261121-1214 and -1216).

Usage: py -3.12 -X utf8 tools/loop/freeze_tag.py FOLDER TAG [--repo REPO] [--strict-skips]

FOLDER is a finished full-gate launch folder (external/s05/ROUTE_GATE_*); TAG is the local annotated tag to create
(today v1.0-alpha-freeze-d on the folder's COMMIT). Meant to run every few minutes under a per-user scheduled task
(after_gate.cmd in the folder runs it once); a run that finds nothing to decide is silent and writes nothing.

What it reads, all from the folder (read-only; the tarball is read member by member in memory, never extracted):
  launch.py            the literals COMMIT and BUNDLE (read as text, never run)
  run_part/<BUNDLE>    the highest-suffix run folder (tools/loop/run_folder_pick.candidates): workload_return.json and
                       collected_evidence.tar.gz holding evidence/gate/results.jsonl, summary.json, git_checkout.json

States, in this order:
  done      FREEZE_OK.json is there and the tag exists: nothing happens (idempotent).
  pending   no run folder, no workload_return.json or no evidence tarball yet: nothing happens, nothing is written.
  ok        every rule below holds: the annotated tag is created on COMMIT and FREEZE_OK.json is written.
  refused   a finished gate broke a rule: FREEZE_REFUSED.json is written, one dated line goes to the top of
            docs/loop/private/ALERT.md (once per distinct reason set), and nothing is tagged.

The rules (all must hold):
  - workload_return.json exit_code is 0;
  - results.jsonl has one line per check, numbers unique, and as many lines as summary.json counts (every check ran);
    summary.json says execution_integrity_passed, no not_run and no reasons; an optional --expected-total N also pins the count;
  - the checks whose status is not PASS and not SKIP (FAIL, ERROR, BADFIXTURE, WARN, anything else) are EXACTLY the
    known red list KNOWN_RED, no more and no fewer (a known red that turned green also refuses: the list is then stale and
    the lead decides); SKIP checks are the gate's own declared skips, recorded in FREEZE_OK.json; --strict-skips refuses any;
  - the evidence's git_checkout.json tree equals the tree of COMMIT (the gate ran the commit it is named for);
  - the tag does not exist yet, or already points at COMMIT. A tag that points elsewhere is never moved or deleted.
  - just before a tag is created, tools/loop/freeze_rule_tests.py runs the written rule (D-912) clause by clause against this
    module's own functions; a red clause refuses with the reason "rule test red: <clause>" (D-923).

The tag is never moved or deleted. Times come from the clock at the moment of the write.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_folder_pick  # noqa: E402
import mechanism_common as mc  # noqa: E402

KNOWN_RED = (28, 31, 118, 121, 146, 193, 257, 325, 333, 338, 348)   # ROUTE_GATE_D_dab39cc4/README.txt (D-902)
OK_NAME = 'FREEZE_OK.json'
REFUSED_NAME = 'FREEZE_REFUSED.json'
_IN_RULE_TESTS = False   # set by freeze_rule_tests while it runs the module's own functions
EVIDENCE = ('evidence/gate/results.jsonl', 'evidence/gate/summary.json', 'evidence/gate/git_checkout.json')


def clock():
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def git(repo, *args):
    p = subprocess.run(['git', '-C', str(repo)] + list(args), capture_output=True, text=True, creationflags=mc.no_window())  # HIDDEN-A (D-079, D-924)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def literal(text, name):
    m = re.search(r"^%s\s*=\s*'([^']+)'" % name, text, re.M)
    return m.group(1) if m else None


def read_evidence(tarball):
    """{member: bytes} for the three gate files, read from the tarball without extracting anything."""
    out = {}
    with tarfile.open(tarball, 'r:gz') as tf:
        for name in EVIDENCE:
            try:
                f = tf.extractfile(name)
            except KeyError:
                f = None
            if f is not None:
                out[name] = f.read()
    return out


def judge(results_text, summary, checkout, commit_tree, exit_code, expected_total=None, strict_skips=False):
    """(reasons, facts) from the gate's files. reasons is a list of strings; empty means every rule holds."""
    reasons = []
    rows, numbers = [], []
    for raw in results_text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
            rows.append((int(row['number']), str(row['status'])))
            numbers.append(int(row['number']))
        except (ValueError, KeyError, TypeError):
            reasons.append('a results line is unreadable')
    if exit_code != 0:
        reasons.append('workload exit code %r, not 0' % (exit_code,))
    if len(set(numbers)) != len(numbers):
        reasons.append('check numbers repeat in results.jsonl')
    counts = summary.get('counts') or {}
    if sum(int(v) for v in counts.values()) != len(rows):
        reasons.append('missing checks: results.jsonl has %d lines, summary.json counts %d'
                       % (len(rows), sum(int(v) for v in counts.values())))
    if expected_total is not None and len(rows) != expected_total:
        reasons.append('results.jsonl has %d checks, %d expected' % (len(rows), expected_total))
    if not summary.get('execution_integrity_passed'):
        reasons.append('summary.json: execution integrity not passed')
    if summary.get('not_run'):
        reasons.append('summary.json: not_run %s' % sorted(summary['not_run']))
    if summary.get('reasons'):
        reasons.append('summary.json: reasons %s' % summary['reasons'])
    non_pass = sorted(n for n, s in rows if s not in ('PASS', 'SKIP'))
    skipped = sorted(n for n, s in rows if s == 'SKIP')
    extra = sorted(set(non_pass) - set(KNOWN_RED))
    gone = sorted(set(KNOWN_RED) - set(non_pass))
    if extra:
        reasons.append('unexpected non-PASS checks: %s' % extra)
    if gone:
        reasons.append('known red checks not red (list stale or check not run): %s' % gone)
    if skipped and strict_skips:
        reasons.append('skipped checks under --strict-skips: %s' % skipped)
    if not checkout or checkout.get('tree') != commit_tree:
        reasons.append('evidence git_checkout tree %r is not the commit tree %r' % ((checkout or {}).get('tree'), commit_tree))
    facts = {'checks': len(rows), 'pass': sum(1 for _, s in rows if s == 'PASS'), 'skip': skipped,
             'non_pass': non_pass, 'extra': extra, 'gone': gone, 'known_red': list(KNOWN_RED)}
    return reasons, facts


def write_json(path, obj):
    tmp = path.with_name(path.name + '.writing')
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(path)


def run(folder, tag, repo, strict_skips=False, expected_total=None, alert=None):
    """Returns (state, detail). alert is a callable(key, text) or None."""
    folder, repo = Path(folder), Path(repo)
    ok_file = folder / OK_NAME
    rc, existing, _ = git(repo, 'rev-parse', '-q', '--verify', 'refs/tags/%s^{commit}' % tag)
    if ok_file.exists() and rc == 0:
        return 'done', 'FREEZE_OK.json and tag %s exist' % tag
    launch_text = (folder / 'launch.py').read_text(encoding='utf-8')
    short, bundle = literal(launch_text, 'COMMIT'), literal(launch_text, 'BUNDLE')
    if not short or not bundle:
        return 'refused', _refuse(folder, tag, None, ['launch.py has no COMMIT or BUNDLE literal'], {}, alert)
    rc2, commit, err = git(repo, 'rev-parse', '--verify', short + '^{commit}')
    if rc2 != 0:
        return 'refused', _refuse(folder, tag, short, ['commit %s not found in the repository' % short], {}, alert)
    found = run_folder_pick.candidates(folder / 'run_part', bundle)
    if not found:
        return 'pending', 'no run folder yet'
    run_dir = found[-1][1]
    wr, tarball = run_dir / 'workload_return.json', run_dir / 'collected_evidence.tar.gz'
    if not wr.is_file() or not tarball.is_file():
        return 'pending', 'workload_return.json or collected_evidence.tar.gz not there yet'
    try:
        exit_code = json.loads(wr.read_text(encoding='utf-8')).get('exit_code')
    except (OSError, ValueError):
        exit_code = 'unreadable'
    try:
        ev = read_evidence(tarball)
    except (OSError, tarfile.TarError, EOFError):
        ev = {}
    missing = [n for n in EVIDENCE if n not in ev]
    if missing:
        return 'refused', _refuse(folder, tag, commit, ['evidence members missing: %s' % missing], {}, alert)
    try:
        summary = json.loads(ev[EVIDENCE[1]].decode('utf-8'))
        checkout = json.loads(ev[EVIDENCE[2]].decode('utf-8'))
    except ValueError:
        return 'refused', _refuse(folder, tag, commit, ['summary.json or git_checkout.json unreadable'], {}, alert)
    _, tree, _ = git(repo, 'rev-parse', commit + '^{tree}')
    reasons, facts = judge(ev[EVIDENCE[0]].decode('utf-8'), summary, checkout, tree, exit_code, expected_total, strict_skips)
    if rc == 0 and existing != commit:
        reasons.append('tag %s already exists on %s, not %s (never moved)' % (tag, existing[:8], commit[:8]))
    if reasons:
        return 'refused', _refuse(folder, tag, commit, reasons, facts, alert)
    preexisting = rc == 0
    if not preexisting and not _IN_RULE_TESTS:
        try:   # D-923: the written rule (D-912) is tested against this code just before a tag is made
            import freeze_rule_tests
            red = freeze_rule_tests.first_red(sys.modules[__name__])
        except Exception as exc:  # noqa: BLE001 - tests that cannot run are a red clause: no tag
            red = 'the rule tests could not run (%s)' % type(exc).__name__
        if red:
            return 'refused', _refuse(folder, tag, commit, ['rule test red: %s' % red], facts, alert)
    if not preexisting:
        msg = 'Freeze %s: full gate green on %s with the known red list only (D-902)' % (tag, commit[:8])
        rc3, _, err = git(repo, 'tag', '-a', tag, commit, '-m', msg)
        if rc3 != 0:
            return 'refused', _refuse(folder, tag, commit, ['git tag failed: %s' % err[:200]], facts, alert)
    write_json(ok_file, {'tag': tag, 'commit': commit, 'tree': tree, 'time': clock(), 'tag_preexisting': preexisting,
                         'counts': {'checks': facts['checks'], 'pass': facts['pass'], 'skip': len(facts['skip']),
                                    'known_red': len(KNOWN_RED)},
                         'skipped': facts['skip'], 'known_red': list(KNOWN_RED), 'run_folder': run_dir.name,
                         'evidence_sha256': hashlib.sha256(tarball.read_bytes()).hexdigest()})
    stale = folder / REFUSED_NAME
    if stale.exists():
        stale.rename(folder / ('FREEZE_REFUSED.superseded_%s.json' % dt.datetime.now().strftime('%Y%m%d%H%M%S')))
    return 'ok', 'tag %s created on %s' % (tag, commit[:8])


def _refuse(folder, tag, commit, reasons, facts, alert):
    body = {'tag': tag, 'commit': commit, 'time': clock(), 'reasons': reasons,
            'differing_checks': {'unexpected_non_pass': facts.get('extra', []), 'known_red_not_red': facts.get('gone', [])},
            'facts': facts}
    path = Path(folder) / REFUSED_NAME
    try:
        same = json.loads(path.read_text(encoding='utf-8')).get('reasons') == reasons
    except (OSError, ValueError):
        same = False
    if not same:
        write_json(path, body)
        if alert is not None:
            diff = facts.get('extra', []) + facts.get('gone', [])
            alert('freeze_tag:%s:%s' % (Path(folder).name, hashlib.sha256(json.dumps(reasons).encode()).hexdigest()[:10]),
                  'freeze tag %s REFUSED for %s, nothing tagged: %s (differing checks %s). See %s in the folder.'
                  % (tag, Path(folder).name, '; '.join(reasons)[:300], diff or 'none', REFUSED_NAME))
    return '; '.join(reasons)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('folder')
    ap.add_argument('tag')
    ap.add_argument('--repo', default=str(HERE.parents[1]))
    ap.add_argument('--strict-skips', action='store_true')
    ap.add_argument('--expected-total', type=int, default=None)
    a = ap.parse_args(argv)
    state, detail = run(a.folder, a.tag, a.repo, a.strict_skips, a.expected_total,
                        alert=lambda key, text: mc.alert(key, text, every=10 ** 9))
    if state != 'pending':
        mc.trace('freeze_tag', state, folder=Path(a.folder).name, tag=a.tag, detail=detail[:300])
    print(state, detail)
    return 0 if state in ('ok', 'done', 'pending') else 1


if __name__ == '__main__':
    sys.exit(main())
