"""15-minute watchdog over every standing mechanism (supervisor batch 2026-11-18 12:30 item E; audit D fix 2).

    py -3.12 -X utf8 tools/loop/mechanism_watchdog.py          # one check, one trace line
    py -3.12 -X utf8 tools/loop/mechanism_watchdog.py --print  # the same, and the table on screen

Run by the Windows task ShimmerMechanismWatchdog every 15 minutes (pyw.exe, no window). For each mechanism
it reads that mechanism's own last evidence (a trace line, a status file, a log line or a report file),
compares its age with the expected period plus a slack, and appends one line to
docs/loop/private/mechanism_trace.jsonl (mechanism mechanism_watchdog) with every age. When any mechanism
is overdue it writes one dated line at the top of docs/loop/private/ALERT.md naming all overdue ones: at
once when the overdue set changes, otherwise at most every 3 hours. It reads only, except the one launch chain
pass below; it stops and deletes nothing.

Evidence (age is measured from the last SUCCESSFUL run where a run can fail):
  resource_reading   trace line mechanism resource_reading                  every 30 min, late after 45 min
  reaper             reaper_status.json last_run_utc                       every 5 min,  late after 15 min
  records_backup     backup_log.jsonl tool backup_records, pushed true      every 3 h,    late after 3 h 30
  branch_backup      backup_log.jsonl backup_private run, nothing refused   every 1 h,    late after 1 h 30
  compliance         newest compliance/COMPLIANCE_*.md (file time)          every 2 h,    late after 2 h 30
  drive_backup       trace line drive_paced, an archive confirmed on Drive  every 24 h,   late after 26 h
  restore_drill      trace line restore_drill, result PASS                  every 24 h,   late after 26 h
  backup_coverage    trace line backup_coverage, the check completed        every 24 h,   late after 26 h
  launch_chain       trace line launch_chain, a pass completed or locked    every 3 min,  late after 15 min

It also copies the Lambda reaper's last result (listed, terminated, error, spend) into its trace line and
writes ALERT.md when the reaper's last run ended in an error (hourly at most) or terminated a machine (once
per run). The reaper itself stays the one task that can terminate (ShimmerLoopReaper, every 5 minutes).

Launch chain rule (Seckin 18 Nov 13:40, "Bekletilmesin"): it runs launch_chain.waiting (the chain's dry-run
reading of every launch folder with a chain.json); any planned step whose prerequisites have held for more than
5 minutes with no launch writes ALERT.md and starts tools/loop/launch_chain.py once for real: an ordinary pass
(holds and refusal pauses are kept), detached, hidden and out of this task's job object (CREATE_BREAKAWAY_FROM_JOB,
without it when refused) so the task's 5-minute limit never cuts an admit short. The chain's reading here is
bounded: 60 s a status call, 180 s in all; its first-seen times are written only when no pass holds the chain lock.
That one start is the only thing the watchdog starts; it stops and deletes nothing.

Issue and remote freshness (Seckin 13:53): every run also calls tools/loop/sync_watch.py check (its own trace
line): a decision or verified result over 60 minutes old with no GitHub issue update after it, commits on the
lead tip on no backup-private ref for over 2 hours, and the newest green gate's commit not on origin/main an hour
after the gate each write ALERT.md. It reads local refs only and never fetches or pushes.

Role hand-backs (the lead 16:05): every run also calls tools/loop/handback_watch.py check (its own trace line):
each *_DONE.json or *_HANDBACK.json in the role exchange folders config/handback_watch.json declares (names and
modification times only, never a file's content) that the lead has not acknowledged in
docs/loop/private/handback_ack.json and that is over 10 minutes old writes ALERT.md "role hand-back not taken
up: <name> since <time>", once per file.

Planned steps (Seckin 21:46, nothing silently waits): every run also calls tools/loop/promise_watch.py check (its
own trace line): each step in docs/loop/private/PLANNED_STEPS.jsonl 5 minutes past its expected start with no
launch, each failed launch with no new launch within 5 minutes, and each role session whose exit file shows exit
while its expected output does not exist writes ALERT.md once per cause.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mechanism_common as mc  # noqa: E402

NAME = 'mechanism_watchdog'
MIN = 60
H = 3600
LIMITS = {   # name: (expected period s, late after s)
    'resource_reading': (30 * MIN, 45 * MIN),
    'reaper': (5 * MIN, 15 * MIN),
    'records_backup': (3 * H, 3 * H + 30 * MIN),
    'branch_backup': (1 * H, 1 * H + 30 * MIN),   # lead 14:08: ShimmerBranchBackup every hour
    'compliance': (2 * H, 2 * H),     # lead 14:24: 120 min now that ShimmerComplianceCheck starts it every 2 h
    'followthrough': (24 * H, 26 * H),
    'checker_check': (24 * H, 26 * H),
    'disk_sweep_dry_run': (24 * H, 26 * H),
    'loop_recovery': (10 * MIN, 25 * MIN),
    'drive_backup': (24 * H, 26 * H),
    'restore_drill': (24 * H, 26 * H),
    'backup_coverage': (24 * H, 26 * H),
    'launch_chain': (3 * MIN, 15 * MIN),
}
REPEAT_S = 3 * H
CHAIN_LATE_MIN = 5


def parse_time(text):
    if not text:
        return None
    try:
        t = dt.datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def read_jsonl(path):
    out = []
    try:
        with open(path, encoding='utf-8') as f:
            for raw in f:
                raw = raw.strip()
                if raw:
                    try:
                        out.append(json.loads(raw))
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


def newest(times):
    times = [t for t in times if t is not None]
    return max(times) if times else None


def evidence(private=None):
    """{mechanism: (last successful time or None, note)}."""
    private = Path(private or mc.PRIVATE)
    trace = read_jsonl(private / 'mechanism_trace.jsonl')
    log = read_jsonl(private / 'backup_log.jsonl')
    out = {}

    def from_trace(name, ok=lambda line: True):
        return newest(parse_time(x.get('time')) for x in trace if x.get('mechanism') == name and ok(x))

    out['resource_reading'] = (from_trace('resource_reading'), 'trace')
    try:
        status = json.loads((private / 'reaper_status.json').read_text(encoding='utf-8'))
        out['reaper'] = (parse_time(status.get('last_run_utc')), 'error: %s' % status.get('error'))
    except (OSError, ValueError):
        out['reaper'] = (None, 'reaper_status.json unreadable')
    out['records_backup'] = (newest(parse_time(x.get('time')) for x in log
                                    if x.get('tool') == 'backup_records' and x.get('pushed') is True),
                             'backup_log')
    branch = [x for x in log if 'time_utc' in x and 'remote' in x and not x.get('dry_run')]
    ok_branch = [x for x in branch if not x.get('refused')]
    last_any = branch[-1] if branch else None
    out['branch_backup'] = (newest(parse_time(x.get('time_utc')) for x in ok_branch),
                            'last run: %s pushed, %s refused' % (
                                len(last_any.get('pushed') or []) if last_any else '-',
                                len(last_any.get('refused') or []) if last_any else '-'))
    reports = sorted((private / 'compliance').glob('COMPLIANCE_*.md'), key=lambda p: p.stat().st_mtime)
    report_time = dt.datetime.fromtimestamp(reports[-1].stat().st_mtime).astimezone() if reports else None
    started = from_trace('compliance_checker', lambda x: x.get('result') in ('started', 'ok'))
    failed = [x for x in trace if x.get('mechanism') == 'compliance_checker' and x.get('result') == 'failed']
    out['compliance'] = (newest([report_time, started]),
                         '%s; task ShimmerComplianceCheck last start %s%s' % (
                             reports[-1].name if reports else 'no report',
                             started.isoformat(timespec='minutes') if started else 'never',
                             '; last failure %s' % failed[-1].get('time') if failed else ''))
    out['drive_backup'] = (newest(parse_time(x.get('archive_time') or x.get('time')) for x in trace
                                  if x.get('mechanism') == 'drive_paced' and x.get('result') == 'cloud_confirmed'),
                           'confirmed on Google Drive (server md5 in the Drive app metadata)')
    drills = [x for x in trace if x.get('mechanism') == 'restore_drill']
    out['restore_drill'] = (from_trace('restore_drill', lambda x: x.get('result') == 'PASS'),
                            'last result: %s' % (drills[-1].get('result') if drills else 'never ran'))
    out['followthrough'] = (from_trace('followthrough_checker', lambda x: x.get('result') == 'ok'), 'trace')
    out['checker_check'] = (from_trace('checker_of_checkers', lambda x: x.get('result') == 'ok'), 'trace')
    out['disk_sweep_dry_run'] = (from_trace('disk_sweep_dry_run', lambda x: x.get('result') == 'ok'), 'trace')
    out['loop_recovery'] = (from_trace('loop_recovery'), 'trace')
    out['backup_coverage'] = (from_trace('backup_coverage', lambda x: x.get('result') in ('ok', 'faults')),
                              'trace')
    out['launch_chain'] = (from_trace('launch_chain', lambda x: x.get('result') in ('ok', 'locked')), 'trace')
    return out


DETACHED, NEW_GROUP, BREAKAWAY = 0x00000008, 0x00000200, 0x01000000


def start_chain_pass(popen=None):
    """launch_chain.py once for real (an ordinary pass: holds and refusal pauses are kept), detached, hidden, and
    out of the watchdog task's job object (CREATE_BREAKAWAY_FROM_JOB) so the task's end does not end it; without
    breakaway when the job refuses it. Its pid."""
    import subprocess
    import launch_chain
    popen = popen or subprocess.Popen
    script = Path(__file__).resolve().parent / 'launch_chain.py'
    kw = dict(cwd=str(mc.MAIN), env=launch_chain.child_env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
              stderr=subprocess.DEVNULL)
    argv = launch_chain.interpreter() + [str(script)]
    base = DETACHED | NEW_GROUP | mc.no_window()
    try:
        return popen(argv, creationflags=base | BREAKAWAY, **kw).pid
    except OSError:
        return popen(argv, creationflags=base, **kw).pid


def chain_check(t=None, root=None, start=None):
    """The launch chain rule: steps ready more than CHAIN_LATE_MIN minutes with no launch alert and start one pass."""
    import launch_chain
    try:
        late, errors = launch_chain.waiting(root=root, t=t, minutes=CHAIN_LATE_MIN)
    except Exception as exc:  # noqa: BLE001 - the watchdog's other checks still run and trace
        return {'late': [], 'errors': {'*': '%s: %s' % (type(exc).__name__, exc)}, 'started': None, 'alert_written': False}
    started, written = None, False
    if late:
        names = ['%s %s' % (x['folder'], x['step']) for x in late]
        written = mc.alert('launch_chain:late:' + ','.join(sorted(names)),
                           'Launch chain: ready for more than %d minutes with no launch: %s. The watchdog started '
                           'launch_chain.py once; read mechanism_trace.jsonl (mechanism launch_chain) for its result.'
                           % (CHAIN_LATE_MIN, '; '.join('%s (%s since %s: %s)' % (n, x['state'], x['ready_since'][11:16],
                                                                                  x['why'][:120])
                                                         for n, x in zip(names, late))))
        started = (start or start_chain_pass)()
    return {'late': late, 'errors': errors, 'started': started, 'alert_written': written}


def reaper_view(private=None):
    """The Lambda reaper's own last result (it runs every 5 minutes as ShimmerLoopReaper): listed machines,
    terminations, error, spend."""
    try:
        s = json.loads((Path(private or mc.PRIVATE) / 'reaper_status.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return {'error': 'reaper_status.json unreadable (%s)' % type(exc).__name__}
    return {k: s.get(k) for k in ('last_run_utc', 'listed', 'loop_running', 'terminated', 'error', 'total_spend_usd')}


def check(t=None, private=None):
    t = t or mc.now()
    rows = {}
    for name, (last, note) in evidence(private).items():
        period, late = LIMITS[name]
        age = None if last is None else (t - last).total_seconds()
        rows[name] = {'last': last.astimezone().isoformat(timespec='seconds') if last else None,
                      'age_min': None if age is None else round(age / 60, 1),
                      'late_after_min': late // 60, 'overdue': age is None or age > late, 'note': note}
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--print', action='store_true')
    args = ap.parse_args(argv)
    rows = check()
    overdue = sorted(n for n, r in rows.items() if r['overdue'])
    written = False
    if overdue:
        parts = ['%s (%s)' % (n, 'never' if rows[n]['age_min'] is None else 'last %s, %.0f min ago, late after %d min'
                              % (rows[n]['last'][:16].replace('T', ' '), rows[n]['age_min'], rows[n]['late_after_min']))
                 for n in overdue]
        written = mc.alert('watchdog:' + ','.join(overdue),
                           'Mechanism watchdog (task ShimmerMechanismWatchdog): overdue: ' + '; '.join(parts) + '.',
                           every=REPEAT_S)
    reaper = reaper_view()
    if reaper.get('error'):
        mc.alert('reaper:error', 'Lambda reaper (task ShimmerLoopReaper) could not finish its last run: %s. Running '
                 'machines may not be watched; check reaper_status.json.' % str(reaper['error'])[:200])
    if reaper.get('terminated'):
        mc.alert('reaper:terminated:%s' % reaper.get('last_run_utc'), 'Lambda reaper (task ShimmerLoopReaper) '
                 'terminated %d machine(s) at %s: %s.' % (len(reaper['terminated']), reaper.get('last_run_utc'),
                                                          str(reaper['terminated'])[:300]), every=10 ** 9)
    chain = chain_check()
    try:
        import sync_watch
        sync = sync_watch.check()['result']        # its own trace line (mechanism sync_watch)
    except Exception as exc:  # noqa: BLE001 - the watchdog's own line is still written
        sync = 'error %s: %s' % (type(exc).__name__, str(exc)[:200])
    try:
        import handback_watch
        handback = handback_watch.check()['result']    # its own trace line (mechanism handback_watch)
    except Exception as exc:  # noqa: BLE001 - the watchdog's own line is still written
        handback = 'error %s: %s' % (type(exc).__name__, str(exc)[:200])
    try:
        import promise_watch
        promise = promise_watch.check()['result']      # its own trace line (mechanism promise_watch)
    except Exception as exc:  # noqa: BLE001 - the watchdog's own line is still written
        promise = 'error %s: %s' % (type(exc).__name__, str(exc)[:200])
    mc.trace(NAME, 'alert' if overdue or reaper.get('error') or chain['late'] else 'ok', overdue=overdue,
             alert_written=written, mechanisms=rows, reaper=reaper, launch_chain=chain, sync_watch=sync,
             handback_watch=handback, promise_watch=promise)
    if args.print:
        for n, r in rows.items():
            print('%-17s %-8s last %-25s age_min %-8s %s' % (n, 'OVERDUE' if r['overdue'] else 'ok', r['last'],
                                                             r['age_min'], r['note']))
        print('launch chain: %d late, started pid %s, errors %s' % (len(chain['late']), chain['started'], chain['errors']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
