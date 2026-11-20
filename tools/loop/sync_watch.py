"""Issue and remote freshness, checked by the 15-minute watchdog (Seckin, 18 November 2026 13:53, via the lead 13:56).

    py -3.12 -X utf8 tools/loop/sync_watch.py           # one check, one trace line, the result on screen

(1) Issue updates: the newest decision (a `## D-` heading of docs/loop/DECISIONS.md and its "Written <time>"
    line) or verified result (a `## <time>: ...` entry of docs/loop/private/FOR_SECKIN.md) that is more than 60
    minutes old must have a GitHub issue update after it. The issues are read with
    `gh issue list --repo <origin> --state all --limit 30 --json number,updatedAt`, where <origin> is the main
    checkout's origin and must be the project repository (seckinozbek1/project-shimmer-deployment, owner and name);
    any other origin is refused
    and gh is not called. Otherwise ALERT.md "issue update due: D-xxx" (or the result's time).
    Every issue update is a full sweep (Seckin 20 November 2026 13:27, D-839), so the update counts as done only
    when the last sweep record (docs/loop/private/issue_sweep.json "at", written by tools/loop/issue_sweep.py
    record) is newer than that decision or result; a missing record, an older one, or one over 24 hours old
    alerts "issue sweep due". The sweep record is a local file; nothing is fetched for it.
(2) Commits: those on the lead tip (HEAD of the main checkout) on no backup-private ref
    (`git log HEAD --not --remotes=backup-private`) alert once one is over 2 hours old; the commit of the newest
    green gate (an external/s05/ROUTE_GATE_*/<folder>/evidence/result.json of arm G with execution integrity passed,
    no failing and no unexpected check, its commit read from evidence/gate/git_checkout.json beside it) that is not
    on origin/main (`git merge-base --is-ancestor --end-of-options <commit> refs/remotes/origin/main`, the commit
    first checked as 7 to 40 hex digits) alerts once the gate result
    is over 1 hour old. The gate commit is the one the instance built from the bound tree and is never in the
    local repository, and the public main is an export (tools/loop/export_public_tree.py), so the gate also counts
    as pushed when its bound source commit (the gate folder's launch.py COMMIT) is named as exported in
    PUSH_RECORD.md ("snapshot commit of loop <id>") or an export report (export_*.json, source_commit), or when
    an exported commit's tree equals the gate's tree (git_checkout.json tree). The private check reads only refs/remotes/backup-private/*, the public check only
    refs/remotes/origin/main; nothing is fetched or pushed (the local remote-tracking refs are what is read).

Each run writes one trace line (mechanism sync_watch) to docs/loop/private/mechanism_trace.jsonl.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mechanism_common as mc  # noqa: E402

NAME = 'sync_watch'
PROJECT_OWNER = 'seckinozbek1'
PROJECT_REPO = 'project-shimmer-deployment'
COMMIT = re.compile(r'[0-9a-f]{7,40}')
ISSUE_GRACE_MIN = 60
SWEEP_RECORD = 'issue_sweep.json'     # written by tools/loop/issue_sweep.py record at the end of a full sweep
SWEEP_STALE_H = 24
BACKUP_LATE_H = 2
ORIGIN_LATE_H = 1
BACKUP_REFS = '--remotes=backup-private'
ORIGIN_MAIN = 'refs/remotes/origin/main'
DECISION = re.compile(r'^## (D-\d+)\b')
WRITTEN = re.compile(r'Written (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) ?([+-]\d{4})')
RESULT = re.compile(r'^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) ?([+-]\d{4}):')


def _time(day_minute, zone):
    return dt.datetime.strptime('%s %s' % (day_minute, zone), '%Y-%m-%d %H:%M %z')


def run(argv):
    """(exit code, stdout) of a read-only git or gh call."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120,
                              creationflags=mc.no_window())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)
    return done.returncode, done.stdout or ''


def decision_events(text):
    """[(id, time)] of every `## D-` heading with a "Written <time>" line within the next three lines."""
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        m = DECISION.match(line)
        if not m:
            continue
        for follow in lines[i + 1:i + 4]:
            w = WRITTEN.search(follow)
            if w:
                out.append((m.group(1), _time(w.group(1), w.group(2))))
                break
    return out


def result_events(text):
    return [('result %s' % m.group(1), _time(m.group(1), m.group(2)))
            for m in (RESULT.match(line) for line in text.splitlines()) if m]


def _read(path):
    try:
        return Path(path).read_text(encoding='utf-8')
    except OSError:
        return ''


def origin_repo(main, runner):
    """owner/name of the main checkout's origin when it is the project repository, else None."""
    rc, url = runner(['git', '-C', str(main), 'remote', 'get-url', 'origin'])
    m = re.search(r'github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?\s*$', url.strip()) if rc == 0 else None
    if not m or m.group(1) != PROJECT_OWNER or m.group(2) != PROJECT_REPO:
        return None
    return '%s/%s' % (m.group(1), m.group(2))


def events_of(main, private):
    return decision_events(_read(Path(main) / 'docs' / 'loop' / 'DECISIONS.md')) + \
        result_events(_read(Path(private) / 'FOR_SECKIN.md'))


def sweep_time(private):
    """The time of the last full issue sweep (docs/loop/private/issue_sweep.json "at"), or None."""
    try:
        body = json.loads((Path(private) / SWEEP_RECORD).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return mc_time(body.get('at')) if isinstance(body, dict) else None


def sweep_check(main, private, now):
    """D-839: an issue update counts as done only when the last full sweep is newer than the decision or result
    that made it due; a missing sweep, or one over 24 hours old, is due as well. Local files only."""
    last = sweep_time(private)
    old = [e for e in events_of(main, private) if (now - e[1]).total_seconds() > ISSUE_GRACE_MIN * 60]
    newest = max(old, key=lambda e: e[1]) if old else None
    if last is None:
        due = 'no sweep recorded'
    elif (now - last).total_seconds() > SWEEP_STALE_H * 3600:
        due = 'last sweep over %d hours old' % SWEEP_STALE_H
    elif newest is not None and last < newest[1]:
        due = 'sweep older than %s' % newest[0]
    else:
        due = None
    return {'due': due, 'last_sweep': last.isoformat() if last else None,
            'event': newest[0] if newest else None, 'event_time': newest[1].isoformat() if newest else None}


def issue_check(main, private, now, runner):
    events = events_of(main, private)
    old = [e for e in events if (now - e[1]).total_seconds() > ISSUE_GRACE_MIN * 60]
    if not old:
        return {'due': None, 'note': 'no decision or result older than %d minutes' % ISSUE_GRACE_MIN}
    name, when = max(old, key=lambda e: e[1])
    repo = origin_repo(main, runner)
    if repo is None:
        return {'due': None, 'error': 'origin is not %s; gh not called' % PROJECT_REPO}
    rc, text = runner(['gh', 'issue', 'list', '--repo', repo, '--state', 'all', '--limit', '30', '--json',
                       'number,updatedAt'])
    if rc != 0:
        return {'due': None, 'error': 'gh issue list exit %d' % rc}
    try:
        issues = json.loads(text or '[]')
    except ValueError:
        return {'due': None, 'error': 'gh issue list printed no JSON'}
    updates = [mc_time(i.get('updatedAt')) for i in issues]
    newest = max((u for u in updates if u), default=None)
    due = name if newest is None or newest < when else None
    return {'due': due, 'event': name, 'event_time': when.isoformat(), 'newest_issue_update':
            newest.isoformat() if newest else None}


def mc_time(text):
    try:
        t = dt.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def backup_check(main, now, runner):
    rc, text = runner(['git', '-C', str(main), 'log', '--format=%H %ct', '-n', '300', 'HEAD', '--not', BACKUP_REFS])
    if rc != 0:
        return {'late': [], 'error': 'git log exit %d' % rc}
    commits = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].isdigit():
            commits.append((parts[0], dt.datetime.fromtimestamp(int(parts[1]), dt.timezone.utc)))
    late = [c for c, t in commits if (now - t).total_seconds() > BACKUP_LATE_H * 3600]
    return {'unbacked': len(commits), 'late': late}


def green(result):
    return (result.get('arm') == 'G' and result.get('execution_integrity_passed') is True
            and not result.get('failing') and not result.get('unexpected'))


def bound_commit(folder):
    """The gate folder's bound source commit: launch.py's COMMIT, read as a literal (never run); None if absent."""
    import ast
    try:
        tree = ast.parse((Path(folder) / 'launch.py').read_text(encoding='utf-8'))
    except (OSError, SyntaxError, ValueError):
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'COMMIT' for t in node.targets):
            try:
                value = ast.literal_eval(node.value)
            except ValueError:
                return None
            return value if isinstance(value, str) and COMMIT.fullmatch(value) else None
    return None


def newest_green_gate(root):
    """(mtime, gate commit, where, gate tree, bound source commit) of the newest green gate, or None. The gate
    commit is the one the instance built from the bound tree (evidence/gate/git_checkout.json); it is never in the
    local repository, so the bound source commit and the tree are what an export can be matched by."""
    found = []
    for path in Path(root).glob('ROUTE_GATE_*/*/evidence/result.json'):
        try:
            result = json.loads(path.read_text(encoding='utf-8'))
            checkout = json.loads((path.parent / 'gate' / 'git_checkout.json').read_text(encoding='utf-8'))
            commit = checkout['commit']
        except (OSError, ValueError, KeyError):
            continue
        if green(result):
            tree = checkout.get('tree') if isinstance(checkout.get('tree'), str) and COMMIT.fullmatch(checkout['tree']) else None
            found.append((path.stat().st_mtime, commit, str(path.relative_to(root)), tree, bound_commit(path.parents[2])))
    return max(found) if found else None


# The export tool (tools/loop/export_public_tree.py) publishes a source commit's tree as one public commit, so the
# public main never holds the loop's own commits. What was exported is read from the records it leaves: the
# PUSH_RECORD.md entry's "snapshot commit of loop <id>" and any export report (export_*.json, its source_commit)
# in the private folder.
EXPORTED_OF = re.compile(r'snapshot commit of loop ([0-9a-f]{7,40})\b')


def exported_sources(private):
    found = set(EXPORTED_OF.findall(_read(Path(private) / 'PUSH_RECORD.md')))
    for report in sorted(Path(private).glob('export_*.json')):
        try:
            value = json.loads(report.read_text(encoding='utf-8')).get('source_commit')
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(value, str):
            found.add(value)
    return sorted(c for c in found if COMMIT.fullmatch(c))


def exported_match(main, tree, bound, exported, runner):
    """Why the gate counts as pushed through an export, or None: its bound source commit is an exported one, or
    an exported commit's tree equals the gate's tree."""
    for c in exported:
        if bound and (c.startswith(bound) or bound.startswith(c)):
            return 'bound source commit %s was exported (PUSH_RECORD.md or an export report)' % bound
    if tree:
        for c in exported:
            rc, out = runner(['git', '-C', str(main), 'rev-parse', '--verify', '--quiet', c + '^{tree}'])
            if rc == 0 and out.strip() == tree:
                return 'the gate tree %s is the tree of exported commit %s' % (tree[:12], c)
    return None


def origin_check(main, root, now, runner, private=None):
    gate = newest_green_gate(root)
    if gate is None:
        return {'late': None, 'note': 'no green gate result found'}
    mtime, commit, where, tree, bound = gate
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        return {'late': None, 'gate': where, 'error': 'the gate commit is not 7 to 40 hex digits; git not called'}
    rc, _ = runner(['git', '-C', str(main), 'merge-base', '--is-ancestor', '--end-of-options', commit, ORIGIN_MAIN])
    age_h = (now.timestamp() - mtime) / 3600
    on_origin = rc == 0
    exported = None if on_origin else exported_match(main, tree, bound, exported_sources(private or mc.PRIVATE), runner)
    pushed = on_origin or bool(exported)
    return {'gate': where, 'commit': commit, 'bound_commit': bound, 'on_origin_main': on_origin, 'exported': exported,
            'age_h': round(age_h, 2), 'late': commit if not pushed and age_h > ORIGIN_LATE_H else None}


def check(now=None, main=None, private=None, root=None, runner=None):
    """Both checks, the alerts, and one trace line; returns the trace line's details."""
    now = now or mc.now()
    main = Path(main or mc.MAIN)
    private = Path(private or mc.PRIVATE)
    root = Path(root or main / 'external' / 's05')
    runner = runner or run
    issues = issue_check(main, private, now, runner)
    sweep = sweep_check(main, private, now)
    backup = backup_check(main, now, runner)
    origin = origin_check(main, root, now, runner, private)
    if issues.get('due'):
        mc.alert('sync:issue:%s' % issues['due'], 'issue update due: %s (written %s; newest issue update %s).'
                 % (issues['due'], issues['event_time'][:16].replace('T', ' '), issues['newest_issue_update']))
    if sweep.get('due'):
        mc.alert('sync:sweep:%s' % (sweep['event'] or sweep['due']), 'issue sweep due: %s (last sweep %s). Sweep '
                 'all open issues, then run tools/loop/issue_sweep.py record and line (D-839).'
                 % (sweep['due'], sweep['last_sweep'] or 'none'))
    if backup.get('late'):
        mc.alert('sync:backup:%s' % backup['late'][0][:12], 'Commits on the lead tip not on any backup-private ref '
                 'for over %d hours: %d (oldest late %s). Run tools/loop/backup_private.py.'
                 % (BACKUP_LATE_H, len(backup['late']), backup['late'][-1][:12]))
    if origin.get('late'):
        mc.alert('sync:origin:%s' % origin['late'][:12], 'The green gate commit %s (%s) is not on origin/main %.1f '
                 'hours after its gate; push it through the pre-push scan when the operator says to push.'
                 % (origin['late'][:12], origin['gate'], origin['age_h']))
    result = 'alert' if issues.get('due') or sweep.get('due') or backup.get('late') or origin.get('late') else 'ok'
    details = {'issues': issues, 'issue_sweep': sweep, 'backup_private': backup, 'origin_main': origin}
    mc.trace(NAME, result, **details)
    return dict(details, result=result)


if __name__ == '__main__':
    print(json.dumps(check(), indent=1, default=str))
