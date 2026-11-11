"""Stop every loop instance when Seckin's Windows session ends (D-S107 item 3, D-412).

A Task Scheduler task registered in his own session (logon type InteractiveToken: it runs only
while he is logged on and needs no stored password, `register_session_hook.py`) starts this
script on the events that end or suspend the session:

  System, User32 1074          a shutdown or restart was initiated (also a sign-out started by a
                               program); Windows then closes programs, and a logoff follows 1074
                               by about 4.6 to 9.2 s, so there is no time to wait for anything.
  System, Winlogon 7002        a user logoff notification.
  System, Kernel-Power 42      the system is entering sleep; the task may only run after resume.
  System, Kernel-Power 506     modern standby entered (a closed lid on such laptops).
  Security 4647                user-initiated logoff: optional (`--with-security-4647`), since a
                               task subscribing to the Security log may need rights a standard
                               user lacks.

One pass, terminate first (D-412 item 1):
1. A lock beside the salvage folder admits one pass at a time (the task's MultipleInstancesPolicy
   is IgnoreNew as well); a lock older than the task's time limit is a dead pass and is replaced.
2. A session-end salvage episode (D-S84) is opened naming every running loop instance, and the
   reaper's own `salvage_pass` writes a request for each, so a controller that is still alive
   sees why its instance went. An open session-end episode from before (left open over a reboot)
   that does not name every running instance is closed as stale, never applied to a newer launch.
3. Every loop instance listed is terminated at once through the provider, with no wait for an
   answer, each in its own try: a failure is recorded by its class name and the next one is
   still terminated. One ledger line each (`by` `session_hook`, reason `session_end_<event>`),
   written to every ledger holding the launch as the reaper writes them (R's ledger for a launch
   only R recorded), or to the append ledger for an instance no ledger records.
4. The episode is closed with the reaper's `close_salvage` when every instance is verified gone;
   otherwise the reaper closes it on its next run (an instance whose termination failed is then
   ended by the reaper after its request goes unanswered).
5. One line in `docs/loop/private/session_hook_log.jsonl`: the event, its id, the provider (real
   or a mock), the seconds used, what was done and whether it is the first real pass for that
   event, so the first real sign-out, shutdown and sleep record how much time each one gave.

Every path (the ledgers, the salvage folder, the reports, FOR_SECKIN, the log, the lock) is the
MAIN checkout's, found through git's common directory, whichever checkout the script runs from
(D-412 items 2 and 4). It never touches an instance without the loop prefix, never prints a key (a
provider error is reduced to its class name) and starts no child itself but git, through
`no_window` (HIDDEN-A).

What this costs, stated: a normal shutdown or sign-out ends the instances WITHOUT their
controllers' packs (whatever a run folder already collected stays); when the provider cannot be
reached in time, each instance is bounded only by its own recorded deadline, which the reaper
enforces at its next run. A trigger can also fire at the wrong moment: a shutdown that is then
cancelled, an updater's restart, or an S3 sleep handled only after resume still stop every loop
instance, and R's instances are stopped too.

    py -3.12 -X utf8 tools/loop/session_end_salvage.py --event-id 1074
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import instance_reaper as reaper  # noqa: E402
from cloud_run_common import no_window  # noqa: E402

EVENT_NAMES = {'1074': 'shutdown', '7002': 'logoff', '4647': 'logoff', '42': 'sleep', '506': 'standby'}
LOG_NAME = 'session_hook_log.jsonl'
LOCK_NAME = 'session_hook.lock'
# The task's ExecutionTimeLimit is two minutes; a lock older than this belongs to a dead pass.
LOCK_STALE_SECONDS = 180
POLL_SECONDS = 1


class HookError(RuntimeError):
    pass


def event_name(event_id):
    return EVENT_NAMES.get(str(event_id).strip(), 'manual')


def main_root(start=HERE, runner=subprocess.run):
    """The main checkout, from git's common directory as seen from `start` (D-412 item 4)."""
    try:
        done = runner(['git', '-C', str(start), 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                      capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
                      creationflags=no_window())
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HookError('The main checkout cannot be found from git (%s)' % type(exc).__name__)
    if done.returncode != 0 or not done.stdout.strip():
        raise HookError('The main checkout cannot be found from git')
    return Path(done.stdout.strip()).resolve().parent


def checked_root(root, finder=None):
    """A --root given by hand must be the main checkout itself, never a worktree (D-435)."""
    root = Path(root).resolve()
    found = (finder or main_root)(root).resolve()
    if found != root:
        raise HookError('--root %s is not the main checkout (git names %s)' % (root, found))
    return root


def resolve_root(given=None, finder=None):
    """(root, how). With git unreadable the script's own checkout is used, which registration
    guarantees is the main checkout's (D-435: a missing git never fails silently)."""
    if given:
        return checked_root(given, finder), 'given'
    try:
        return (finder or main_root)(HERE), 'git'
    except HookError as exc:
        return HERE.parents[1], 'script_location (%s)' % exc


def main_paths(root):
    private = Path(root) / 'docs' / 'loop' / 'private'
    return {'private': private, 'ledger': private / 'budget_ledger.jsonl', 'salvage': private / 'salvage',
            'reports': private, 'for_seckin': private / 'FOR_SECKIN.md', 'log': private / LOG_NAME}


def salvage_folder():
    """The one shared salvage folder: the reaper's when it resolves one (lane/tiers), else SALVAGE_DIR."""
    resolve = getattr(reaper, 'salvage_dir', None)
    return Path(resolve()) if callable(resolve) else Path(reaper.SALVAGE_DIR)


def take_lock(path, now_epoch):
    """True when this pass holds the lock; a lock older than LOCK_STALE_SECONDS is replaced."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({'pid': os.getpid(), 'epoch': now_epoch})
    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                held = float(json.loads(path.read_text(encoding='utf-8')).get('epoch'))
            except (OSError, ValueError, TypeError, AttributeError):
                held = path.stat().st_mtime if path.exists() else 0.0
            if now_epoch - held < LOCK_STALE_SECONDS:
                return False
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(body)
        return True
    return False


# The stale episode's instances, handed to the new episode so its report gives each a section (D-439).
STALE_INSTANCES = {}


def close_stale_episode(running, now):
    """An open session-end episode that does not name every running loop instance is from an
    earlier session: it is moved into its own folder, closed as stale, and never applied."""
    folder = salvage_folder()
    path = folder / 'episode.json'
    try:
        episode = reaper._read_json(path)
    except ValueError:
        episode = None
    if not episode or (episode.get('trigger') or {}).get('trigger') != 'session_end':
        return None
    if {item['name'] for item in running} <= set(episode.get('instances') or {}):
        return None
    episode['closed_stale_utc'] = now.isoformat()
    target = folder / (str(episode.get('id')) + '_stale')
    target.mkdir(parents=True, exist_ok=True)
    reaper._write_json(target / 'episode.json', episode)
    for name in episode.get('instances') or {}:
        for kind in ('request', 'done'):
            source = reaper.request_path(name, kind)
            if source.exists():
                os.replace(source, target / source.name)
    path.unlink()
    STALE_INSTANCES.clear()
    STALE_INSTANCES.update(episode.get('instances') or {})
    return str(target)


def open_episode(now, event, event_id, running, stale=None):
    """Write the session-end episode naming every running instance, unless one is open. A stale
    episode closed first is named in the trigger, so its report says so (D-435)."""
    path = salvage_folder() / 'episode.json'
    if path.exists():
        return
    instances = {item['name']: {'instance_id': item.get('instance_id'), 'type': item.get('type'),
                                'region': item.get('region')} for item in running}
    trigger = {'trigger': 'session_end', 'event': event, 'event_id': str(event_id)}
    record = {'id': now.strftime('%Y%m%dT%H%M%SZ'), 'started_utc': now.isoformat(), 'trigger': trigger,
              'instances': instances}
    if stale:
        trigger['stale_episode_closed'] = str(stale)
        record['stale_instances'] = dict(STALE_INSTANCES)
    reaper._write_json(path, record)


def answered(names):
    """The instance names whose controller wrote its done file."""
    return {name for name in names if reaper.request_path(name, 'done').exists()}


def wait_for_answers(names, seconds, clock=time.monotonic, sleep=time.sleep):
    """Poll the done files until every instance answered or the seconds run out (a hand run only)."""
    end = clock() + seconds
    done = answered(names)
    while len(done) < len(names) and clock() < end:
        sleep(POLL_SECONDS)
        done = answered(names)
    return done


def terminate_remaining(provider, running, by_name, rows_by_path, append_path, now, event):
    """Terminate every loop instance of the one listing already read (no second listing before
    the first termination, D-435), each in its own try; one ledger line for each termination made.
    Returns ({name: (minutes, cost)}, {name: error class})."""
    listed = {item['name']: item for item in running}
    costs, failures = {}, {}
    for name, item in listed.items():
        rec = by_name.get(name)
        try:
            provider.terminate(item['instance_id'])
        except Exception as exc:  # the next instance is still terminated; never the message itself
            failures[name] = type(exc).__name__
            continue
        minutes = cost = None
        if rec is not None and rec.get('launch_requested_utc') and rec.get('price_usd_per_hour') is not None:
            minutes = max(0, math.ceil((now - reaper.parse_time(rec['launch_requested_utc'])).total_seconds() / 60))
            cost = round(float(rec['price_usd_per_hour']) * minutes / 60, 4)
        line = {'event': 'termination', 'by': 'session_hook', 'time_utc': now.isoformat(),
                'instance_id': item['instance_id'], 'instance_name': name, 'reason': 'session_end_' + event,
                'type': item.get('type'), 'region': item.get('region'),
                'actual_minutes': minutes, 'actual_cost': cost}
        targets = (reaper.holders(rec, rows_by_path) if rec is not None else []) or [Path(append_path)]
        reaper.write_line(targets, line)
        costs[name] = (minutes, cost)
    return costs, failures


def first_real(log, event):
    """True when the log holds no earlier real pass for this event."""
    try:
        lines = Path(log).read_text(encoding='utf-8').splitlines()
    except OSError:
        return True
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('provider') == 'real' and row.get('event') == event and not row.get('skipped'):
            return False
    return True


def append_log(log, record):
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(record, sort_keys=True) + '\n')


def run(provider, ledger_paths, append_path, event_id, answer_seconds=0, now=None,
        clock=time.monotonic, sleep=time.sleep, log_path=None, provider_kind='mock', lock_path=None, root_from='given'):
    """One session-end pass, terminate first. Returns its record (also appended to the log)."""
    started = now or reaper.utc_now()
    tick = clock()
    event = event_name(event_id)
    log = Path(log_path) if log_path else salvage_folder().parent / LOG_NAME
    record = {'event_id': str(event_id), 'event': event, 'started_utc': started.isoformat(),
              'provider': provider_kind, 'answer_seconds': answer_seconds or 0, 'root_from': root_from}
    lock = Path(lock_path) if lock_path else salvage_folder().parent / LOCK_NAME
    if not take_lock(lock, time.time()):
        record.update(skipped='another_pass_holds_the_lock', seconds_used=round(clock() - tick, 3))
        append_log(log, record)
        return record
    try:
        rows, rows_by_path = [], []
        for path in ledger_paths:
            if any(reaper._same_file(path, seen) for seen, _ in rows_by_path):
                continue
            read = reaper.read_ledger(path)
            rows_by_path.append((Path(path), read))
            rows.extend(read)
        by_name, _closed, _spend = reaper.ledger_view(rows, started)
        running = reaper.loop_instances(provider.request('instances')['data'])
        record['loop_running'] = len(running)
        record['first_real_of_event'] = provider_kind == 'real' and first_real(log, event)
        if running:
            stale = close_stale_episode(running, started)
            if stale:
                record['stale_episode_closed'] = stale
            open_episode(started, event, event_id, running, stale)
            episode = reaper.salvage_pass(started, running, [])
            names = [item['name'] for item in running]
            done = wait_for_answers(names, answer_seconds, clock, sleep) if answer_seconds else answered(names)
            costs, failures = terminate_remaining(provider, running, by_name, rows_by_path, append_path, started, event)
            for name, entry in episode['instances'].items():
                if name in done:
                    entry.update(state='salvaged', done=reaper._read_json(reaper.request_path(name, 'done')))
                elif name in failures:
                    entry.update(state='terminate_failed', error=failures[name])
                elif entry.get('state') in (None, 'waiting'):
                    entry.update(state='terminated_by_session_end', reason='session_end_' + event)
            record.update(answered=sorted(done), terminated=sorted(costs), terminate_failed=failures,
                          report=reaper.close_salvage(provider, episode, started, rows, costs))
    finally:
        try:
            lock.unlink()
        except OSError:
            pass
    record['seconds_used'] = round(clock() - tick, 3)
    append_log(log, record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description='Stop every loop instance at session end (D-S107 item 3, D-412).')
    parser.add_argument('--event-id', default='manual', help='the Windows event id that started the task')
    parser.add_argument('--answer-seconds', type=float, default=0,
                        help='seconds to wait for the controllers before terminating (default 0: terminate first)')
    parser.add_argument('--mock-state', help='JSON file standing in for the provider (proofs only)')
    parser.add_argument('--root', help='the main checkout (default: found through git from this script)')
    parser.add_argument('--ledger', action='append', help='ledger to read (repeatable); default: private and R ledgers')
    parser.add_argument('--append-to', help='ledger for a loop instance no ledger records (default the private one)')
    parser.add_argument('--salvage-dir', help='the D-S84 salvage folder (default the main checkout\'s)')
    parser.add_argument('--report-dir', help='folder for SALVAGE_REPORT_<time>.md (default the main checkout\'s)')
    parser.add_argument('--for-seckin', help='file that receives the top entry (default the main checkout\'s)')
    parser.add_argument('--log', help='the run log (default the main checkout\'s session_hook_log.jsonl)')
    parser.add_argument('--now', help='ISO time to use instead of the clock (proofs only)')
    args = parser.parse_args(argv)
    log = Path(args.log) if args.log else None
    try:
        root, how = resolve_root(args.root)
        where = main_paths(root)
        log = log or where['log']
        reaper.SALVAGE_DIR = Path(args.salvage_dir) if args.salvage_dir else where['salvage']
        reaper.REPORT_DIR = Path(args.report_dir) if args.report_dir else where['reports']
        reaper.FOR_SECKIN = Path(args.for_seckin) if args.for_seckin else where['for_seckin']
        ledgers = [Path(p) for p in args.ledger] if args.ledger else [where['ledger'], reaper.R_LEDGER]
        append_path = Path(args.append_to) if args.append_to else where['ledger']
        now = reaper.parse_time(args.now) if args.now else None
        provider = reaper.MockProvider(args.mock_state) if args.mock_state else reaper.real_provider()
        record = run(provider, ledgers, append_path, args.event_id, args.answer_seconds, now=now, log_path=log,
                     provider_kind='mock' if args.mock_state else 'real', root_from=how)
        code = 0
    except Exception as exc:  # never let a provider message (which could echo a header) out
        record = {'event_id': args.event_id, 'event': event_name(args.event_id), 'error': type(exc).__name__,
                  'time_utc': datetime.now(timezone.utc).isoformat()}
        if log is not None:
            append_log(log, record)
        code = 1
    print(json.dumps(record, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
