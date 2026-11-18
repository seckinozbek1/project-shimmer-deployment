"""Run one backup job so that any failure writes ALERT.md itself (supervisor batch 2026-11-18 12:30 item D).

    py -3.12 -X utf8 tools/loop/backup_guarded.py records    # tools/loop/backup_records.py   (task ShimmerRecordsBackup, every 3 h)
    py -3.12 -X utf8 tools/loop/backup_guarded.py branches   # tools/loop/backup_private.py   (task ShimmerBranchBackup, every 1 h)
    py -3.12 -X utf8 tools/loop/backup_guarded.py coverage   # tools/loop/backup_coverage.py  (task ShimmerBackupCoverage, daily)
    py -3.12 -X utf8 tools/loop/backup_guarded.py drill      # tools/loop/restore_drill.py    (task ShimmerRestoreDrill, daily)

The job names map to fixed commands; no other command can be run through this wrapper. The wrapper waits
(60 s at a time, up to 10 minutes) while free RAM is under 2.1 GiB, runs the job hidden, reads the job's own
result (its backup_log.jsonl line, its JSON report or its drill_result.json), and appends one line to
docs/loop/private/mechanism_trace.jsonl with the exit code and the pushed, refused, held-back or failed
counts. A non-zero exit, a refused ref, a push that failed, a coverage fault or a drill that did not pass
writes a dated line at the top of docs/loop/private/ALERT.md (at most once per hour per job and outcome).
Only counts, ref names and part names outside the drive-only roots are written; never a file's content.
The wrapper deletes nothing; the jobs keep their own rules (the drill writes only into a new folder).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mechanism_common as mc  # noqa: E402

LOG = mc.PRIVATE / 'backup_log.jsonl'
JOBS = {
    'records': ('records_backup', ['backup_records.py'], 3 * 3600),
    'branches': ('branch_backup', ['backup_private.py'], 3 * 3600),
    'coverage': ('backup_coverage', ['backup_coverage.py', '--json'], 2 * 3600),
    'drill': ('restore_drill', ['restore_drill.py'], 2 * 3600),
}


def log_lines():
    try:
        return LOG.read_text(encoding='utf-8').splitlines()
    except OSError:
        return []


def new_log_records(before):
    out = []
    for raw in log_lines()[before:]:
        try:
            out.append(json.loads(raw))
        except ValueError:
            continue
    return out


def run(args, timeout):
    cmd = mc.python_cmd() + [str(HERE / args[0])] + args[1:]
    try:
        done = subprocess.run(cmd, cwd=str(mc.MAIN), capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=timeout, stdin=subprocess.DEVNULL,
                              creationflags=mc.no_window())
        return done.returncode, done.stdout or '', done.stderr or ''
    except subprocess.TimeoutExpired:
        return 124, '', 'timed out after %d s' % timeout


def summarise_records(code, out, records):
    rec = [r for r in records if r.get('tool') == 'backup_records']
    r = rec[-1] if rec else {}
    d = {'exit': code, 'pushed': r.get('pushed'), 'commit': (r.get('commit') or '')[:12] or None,
         'files': r.get('files'), 'held_back': len(r.get('held_back_for_review') or []),
         'skipped_large': r.get('skipped_large')}
    refused = [ln for ln in out.splitlines() if ln.startswith('REFUSED')]
    if refused:
        d['refusal'] = refused[0][:200]
    ok = code == 0 and r.get('pushed') is True
    why = None if ok else (d.get('refusal') or ('push failed' if rec else 'no log line written') + ', exit %d' % code)
    return ok, d, why


def summarise_branches(code, out, records):
    rec = [r for r in records if 'time_utc' in r and 'remote' in r]
    r = rec[-1] if rec else {}
    refused = r.get('refused') or []
    reasons = {}
    for item in refused:
        for reason in item.get('reasons') or []:
            key = re.sub(r'\(commit [0-9a-f]+\)', '(commit)', reason)[:80]
            reasons[key] = reasons.get(key, 0) + 1
    d = {'exit': code, 'pushed': len(r.get('pushed') or []), 'refused': len(refused),
         'unchanged': r.get('unchanged'), 'visibility': r.get('visibility'), 'refused_reasons': reasons,
         'refused_refs_first': [i.get('ref') for i in refused[:5]]}
    ok = code == 0 and bool(rec) and not refused
    why = None if ok else ('%d refused (%s), %d pushed, exit %d' % (
        len(refused), '; '.join('%s x%d' % kv for kv in reasons.items()) or 'no log line', d['pushed'], code))
    return ok, d, why


def summarise_coverage(code, out, records):
    try:
        report = json.loads(out[out.index('{'):])
    except ValueError:
        return False, {'exit': code, 'report': 'not readable', 'first_line': out.strip()[:200]}, \
            'the coverage report could not be read, exit %d' % code
    counts, faults, drive_only_faults = {}, [], 0
    for r in report.get('parts') or []:
        counts[r.get('status')] = counts.get(r.get('status'), 0) + 1
        if r.get('irreplaceable') and r.get('status') in ('STALE', 'NOT COVERED'):
            if r.get('drive_only'):
                drive_only_faults += 1
            else:
                faults.append(r.get('part'))
    d = {'exit': code, 'parts': sum(counts.values()), 'by_status': counts, 'irreplaceable_faults': len(faults)
         + drive_only_faults, 'fault_parts': faults[:12], 'drive_only_faults': drive_only_faults,
         'drive_only_in_git': (report.get('git') or {}).get('drive_only_in_git')}
    ok = code == 0
    why = None if ok else '%d irreplaceable parts STALE or NOT COVERED (%s%s), exit %d' % (
        d['irreplaceable_faults'], ', '.join(faults[:6]) or '-',
        (', plus %d drive-only' % drive_only_faults) if drive_only_faults else '', code)
    return ok, d, why


def summarise_drill(code, out, records):
    m = re.search(r'drill folder left in place: (.+)$', out.strip(), re.M)
    folder = m.group(1).strip() if m else None
    kinds = []
    if folder:
        try:
            res = json.loads((Path(folder) / 'drill_result.json').read_text(encoding='utf-8'))
            kinds = [{k: v for k, v in r.items() if k != 'mismatches'} | {'mismatches': len(r.get('mismatches') or [])}
                     for r in res.get('kinds') or []]
        except (OSError, ValueError):
            pass
    d = {'exit': code, 'folder': folder, 'kinds': kinds}
    if not folder:
        d['first_line'] = out.strip()[:200]
    ok = code == 0
    why = None if ok else 'restore drill %s: %s' % ('REFUSED' if code == 2 else 'FAIL', '; '.join(
        '%s %s (%s)' % (k.get('kind'), k.get('result'), k.get('reason') or 'part %s' % k.get('part')) for k in kinds)
        or d.get('first_line') or 'exit %d' % code)
    return ok, d, why


SUMMARY = {'records': summarise_records, 'branches': summarise_branches, 'coverage': summarise_coverage,
           'drill': summarise_drill}


LEAD_TIP = 'lane/lead-tip'


def git(*args):
    done = subprocess.run(['git', '-C', str(mc.MAIN)] + list(args), capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, creationflags=mc.no_window())
    return done.returncode, (done.stdout or '').strip()


def lead_tip_branch():
    """The lead's main checkout works on a detached HEAD, which no branch backup pushes (18 Nov: 16 commits were on
    no backup ref). Move lane/lead-tip to HEAD when that is a fast-forward; otherwise keep the old branch and name the
    new tip lane/lead-tip-<short sha>, so no backed-up commit is ever dropped from a ref."""
    code, head = git('rev-parse', 'HEAD')
    if code or not head:
        return {'lead_tip': 'unreadable'}
    code, old = git('rev-parse', '--verify', '--quiet', LEAD_TIP)
    if code or not old:
        git('branch', LEAD_TIP, head)
        return {'lead_tip': 'created', 'commit': head[:8]}
    if old == head:
        return {'lead_tip': 'current', 'commit': head[:8]}
    if git('merge-base', '--is-ancestor', old, head)[0] == 0:
        git('update-ref', 'refs/heads/' + LEAD_TIP, head, old)
        return {'lead_tip': 'moved', 'from': old[:8], 'commit': head[:8]}
    git('branch', '-f', '%s-%s' % (LEAD_TIP, head[:8]), head)
    return {'lead_tip': 'diverged', 'branch': '%s-%s' % (LEAD_TIP, head[:8]), 'commit': head[:8]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('job', choices=sorted(JOBS))
    args = ap.parse_args(argv)
    name, cmd, timeout = JOBS[args.job]
    if not mc.wait_for_ram(name):
        ram = mc.free_ram_gib()
        mc.trace(name, 'deferred_ram', ram_free_gib=ram)
        mc.alert(name + ':ram', '%s did not start: free RAM stayed under 2.1 GiB for 10 minutes (%.2f GiB). '
                 'It runs again at its next scheduled time.' % (name, ram))
        return 3
    if args.job == 'branches':
        mc.trace(name, 'lead_tip', **lead_tip_branch())
    before = len(log_lines())
    code, out, err = run(cmd, timeout)
    ok, details, why = SUMMARY[args.job](code, out, new_log_records(before))
    if code != 0 and err.strip():
        details['stderr_last'] = err.strip().splitlines()[-1][:200]
    if args.job == 'drill':
        result = 'PASS' if ok else ('REFUSED' if code == 2 else 'FAIL')
    elif args.job == 'coverage':
        result = 'ok' if ok else ('faults' if code == 1 else 'error')
    else:
        result = 'ok' if ok else 'failed'
    details['alert_written'] = False if ok else mc.alert(
        '%s:%s' % (name, result), 'BACKUP %s %s (task wrapper tools/loop/backup_guarded.py %s): %s. Evidence: '
        'docs/loop/private/mechanism_trace.jsonl and backup_log.jsonl.' % (name, result.upper(), args.job, why))
    mc.trace(name, result, **details)
    print(json.dumps({'mechanism': name, 'result': result, **details}, default=str))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
