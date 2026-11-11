"""Loop instance reaper: terminate loop instances that outlive their recorded deadline.

Loop machinery, not product code. It runs every five minutes from a per-user Windows
scheduled task, so termination never depends on a Claude Code session staying alive.

What it does on every run:
1. Reads the loop's private ledger and role R's ledger (JSON lines).
2. Lists instances through the provider (observation and termination only; it can
   never launch anything).
3. Terminates every instance whose name starts with ``shimmer-loop-`` that is past its
   recorded deadline, or that has no recorded deadline, and every loop instance once
   total loop spend reaches the hard stop. The budget and the hard stop are read from the
   ledger's latest ``budget_open`` or ``budget_change`` line (``budget_figures``), never
   from a number in this file: the hard stop is that line's ``hard_stop_usd``, else its
   ``budget_usd`` less the one-dollar margin. With no budget line at all, no loop launch
   is allowed (the budget guard refuses one), so every loop instance found is terminated.
   Spend is the total over every launch, so the hard stop counts every running loop
   instance together, however many run: there is no maximum number of loop instances
   (D-S95, which removed D-S17's count limit); each is judged on its own record.
4. Closes every launch the ledger still holds open past its recorded deadline when no
   instance of that name is listed: an intent whose launch created no instance
   (reason ``intent_without_instance``) or a launch whose instance is gone (reason
   ``instance_not_listed_charged_to_deadline``). An open launch accrues spend only to its
   recorded deadline, and the closing line's ``actual_cost`` is that same charge: the price
   times the minutes from the launch request to the deadline. It is a CEILING, not a
   measurement (the instance may have cost less, or nothing), counted as actual spend and
   never refunded; its reason says it was charged that way.
5. Salvage, then stop (D-S84), with no Claude involved. Two triggers are read on every run:
   seven-day usage at or above ``USAGE_STOP_PERCENT`` in ``.claude/loop_status.json``, and no
   lead heartbeat (the continue hook's state, LOOP_STATE or FOR_SECKIN written) for
   ``SILENCE_MINUTES`` while a loop instance runs. Either opens a salvage episode
   (``salvage/episode.json``): every running loop instance gets a request file its controller
   polls (``salvage_request``). The controller gives the item in hand ``SALVAGE_ITEM_SECONDS``,
   stops the workload, packs and copies the evidence to its run folder, terminates and verifies
   its instance, and answers with a done file (``write_salvage_done``). An instance with no
   answer ``SALVAGE_ANSWER_SECONDS`` after its request is terminated here (reason
   ``salvage_no_answer``). Once every instance of the episode is verified gone, a report is
   written (``SALVAGE_REPORT_<time>.md``) and a top entry put in FOR_SECKIN.
6. Appends one ledger line per termination or closure and writes ``reaper_status.json``. A
   line for a launch a ledger records goes to EVERY ledger file that holds a launch line for
   that launch (the private ledger, R's, or both for a copied line), so a launch recorded
   only in R's ledger is closed where R's guard reads it; a line for a listed loop instance
   no ledger records goes to the append ledger (by default the private one). A line it
   writes carries only declared ledger fields (``tools/loop_budget_guard.LEDGER_FIELDS``,
   which declares its ``by`` and ``reason``).

It never touches an instance without the loop prefix, and it never prints a key: every
provider error is reduced to its class name before it reaches output.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'shimmer-loop-'
# D-S95: no maximum number of loop instances (D-S17 item 1's limit, raised to sixteen by D-S79,
# is removed). Every instance stays under this reaper, its ledger line, its deadline and the
# budget rules; the total budget and its hard stop are the only limit.
# The margin between the budget and the hard stop when a budget line names no hard stop
# (IV.3's one dollar). The budget itself is never a code constant.
MARGIN_USD = 1.0
BUDGET_EVENTS = ('budget_open', 'budget_change')
# The fields a budget line may carry, declared once (D-S121: `warning_usd`, the Lambda warning), so no
# reader refuses or drops one: budget_figures reads budget_usd and hard_stop_usd, warning_figure
# warning_usd, the guard the A10 reference price.
BUDGET_LINE_FIELDS = ('event', 'time_utc', 'loop_start_utc', 'budget_usd', 'hard_stop_usd', 'warning_usd',
                      'storage_usd_per_day', 'a10_reference_price_usd_per_hour', 'note',
                      # every other field the real budget lines carry (D-464 item 3): read by no rule here
                      'source', 'previous_budget_usd', 'previous_hard_stop_usd', 'allocations_usd',
                      'five_hour_usage_launch_limit_percent', 'seven_day_usage_launch_limit_percent',
                      'usage_five_hour', 'usage_seven_day', 'a10_price_source', 'orphans',
                      'running_instances_at_open', 'storage_forecast_days', 'storage_forecast_usd')
PRIVATE_LEDGER = ROOT / 'docs' / 'loop' / 'private' / 'budget_ledger.jsonl'
R_LEDGER = Path.home() / 'local' / 'shimmer-roles' / '_handoff' / 'R_ledger.jsonl'
STATUS = ROOT / 'docs' / 'loop' / 'private' / 'reaper_status.json'
# D-S84: salvage, then stop. Every path is a module name so a proof can point it at fixtures.
PRIVATE = ROOT / 'docs' / 'loop' / 'private'
LOOP_STATUS = ROOT / '.claude' / 'loop_status.json'
HEARTBEATS = (PRIVATE / 'continue_hook_state.json', PRIVATE / 'LOOP_STATE.md', PRIVATE / 'FOR_SECKIN.md')
FOR_SECKIN = PRIVATE / 'FOR_SECKIN.md'
REPORT_DIR = PRIVATE
# D-412 item 2: one salvage folder for the reaper, every controller's poll and the sign-out hook:
# docs/loop/private/salvage of the MAIN checkout, found through git's common directory (the path rule
# of tools/loop/cloud_reference_spend.store_path), whichever checkout a tool runs from. Resolved at
# use, never at import; a proof or `--salvage-dir` sets SALVAGE_DIR instead.
SALVAGE_DIR = None


_RESOLVED = {}


def main_private():
    """docs/loop/private of the MAIN checkout, through git's common directory, resolved once per
    process for each checkout (D-436 item 4); a git failure raises SpendStoreError."""
    if ROOT not in _RESOLVED:
        import cloud_reference_spend
        _RESOLVED[ROOT] = cloud_reference_spend.store_path(ROOT).parent
    return _RESOLVED[ROOT]


def salvage_dir():
    """The one shared salvage folder (D-412 item 2)."""
    if SALVAGE_DIR is not None:
        return Path(SALVAGE_DIR)
    return main_private() / 'salvage'



USAGE_STOP_PERCENT = 95
SILENCE_MINUTES = 90
SALVAGE_ITEM_SECONDS = 300
SALVAGE_ANSWER_SECONDS = 600
# The scheduled task's period (it runs every five minutes) and a margin for one late run: the time
# an instance can run past the moment it is due before this reaper ends it, which the budget guard
# reserves per running instance (D-382 item 5, D-401 item 2). A limit, stated: the task runs only
# while Seckin is logged on to this machine, so while he is logged off the period is unbounded and
# the instance's own deadline and watchdog are what end it (an open question to him).
REAPER_PERIOD_SECONDS = 300
REAPER_MARGIN_SECONDS = 120


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(value):
    return datetime.fromisoformat(str(value).replace('Z', '+00:00'))


def read_ledger(path):
    rows = []
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:
        return rows
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def ledger_view(rows, now):
    """Return per-instance records keyed by name, the closed launches (launch key to the
    termination line that closed it), and total spend counted once per launch.

    A launch is identified by its instance id when known, else by its name. Each launch is
    counted once across both ledgers: a closed launch by its recorded actual cost, an open
    one by its price times the minutes since the launch request, never past its recorded
    deadline (rounded up, which overstates slightly and is safe). The storage share accrues
    from the loop's start.
    """
    launches = {}
    terminations = []
    storage_rate = 0.0
    loop_start = None
    for row in rows:
        event = row.get('event')
        if event == 'budget_open':
            storage_rate = float(row.get('storage_usd_per_day') or 0.0)
            loop_start = row.get('loop_start_utc') or loop_start
        elif event == 'launch_intent' and row.get('instance_name', '').startswith(PREFIX):
            ident = row.get('instance_id') or row['instance_name']
            launches.setdefault(ident, {}).update(row)
        elif event == 'launch' and row.get('instance_name', '').startswith(PREFIX):
            ident = row.get('instance_id') or row['instance_name']
            # A launch line carries the id once the provider returned it; merge any
            # intent recorded under the name alone.
            merged = launches.pop(row['instance_name'], {})
            merged.update(launches.get(ident, {}))
            merged.update(row)
            launches[ident] = merged
        elif event == 'termination' and (row.get('instance_id') or row.get('instance_name')):
            terminations.append(row)
    # A termination closes a launch when it names the launch's instance id OR its instance
    # name. An intent whose launch line was never written (the request succeeded but its
    # reply was lost, or the controller died before writing it) is keyed by its name, while
    # the termination that ends it (the controller's recovery, or this reaper) carries the
    # id: matching on either keeps such a launch from staying open, and charged, for good.
    # A name match counts only for a termination at or after the launch request, so a later
    # launch reusing a name is never closed by an earlier termination.
    closed = {}
    for ident, rec in launches.items():
        for row in terminations:
            by_id = row.get('instance_id') and row.get('instance_id') in (ident, rec.get('instance_id'))
            by_name = row.get('instance_name') and row.get('instance_name') == rec.get('instance_name')
            if by_name and not by_id:
                start = rec.get('launch_requested_utc') or rec.get('time_utc')
                try:
                    by_name = not start or not row.get('time_utc') or parse_time(row['time_utc']) >= parse_time(start)
                except (ValueError, TypeError):
                    by_name = False
            if by_id or by_name:
                closed[ident] = row
    spend = 0.0
    by_name = {}
    for ident, rec in launches.items():
        by_name[rec.get('instance_name')] = dict(rec, ident=ident)
        if ident in closed and closed[ident].get('actual_cost') is not None:
            spend += float(closed[ident]['actual_cost'])
        elif ident in closed:
            spend += accrued(rec, parse_time(closed[ident].get('time_utc', now.isoformat())))
        elif rec.get('event') == 'launch' or rec.get('launch_requested_utc'):
            # An open launch accrues only to its recorded deadline: an intent whose launch
            # created no instance would otherwise accrue for ever. Charging to the deadline
            # overstates such an intent (it cost nothing), which is the safe side; an
            # instance still running past it is ended, and charged its real minutes, by the
            # reaper's next pass.
            spend += accrued(rec, now, to_deadline=True)
    if loop_start and storage_rate:
        days = max(0.0, (now - parse_time(loop_start)).total_seconds() / 86400)
        spend += storage_rate * days
    return by_name, closed, spend


def budget_figures(rows):
    """(budget_usd, hard_stop_usd) from the latest budget line, or (None, None).

    Lines are ordered by their own ``time_utc`` (read order breaks a tie). A line with no
    readable time, or whose figures are not finite positive numbers with the stop at or
    below the budget, is skipped."""
    timed = []
    for index, row in enumerate(rows):
        if row.get('event') not in BUDGET_EVENTS:
            continue
        try:
            budget = float(row['budget_usd'])
            stop = float(row['hard_stop_usd']) if row.get('hard_stop_usd') is not None else budget - MARGIN_USD
            moment = parse_time(row['time_utc'])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(budget) and math.isfinite(stop) and 0 < stop <= budget:
            timed.append((moment, index, budget, stop))
    if timed:
        latest = max(timed, key=lambda item: (item[0], item[1]))
        return latest[2], latest[3]
    return None, None


def warning_figure(rows):
    """The Lambda warning (`warning_usd`, D-S121) of the latest budget line that names one with a
    readable time, or None. A budget line may carry it; every reader of budget lines admits it."""
    timed = []
    for index, row in enumerate(rows):
        if row.get('event') not in BUDGET_EVENTS or row.get('warning_usd') is None:
            continue
        try:
            value = float(row['warning_usd'])
            moment = parse_time(row['time_utc'])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            timed.append((moment, index, value))
    return max(timed, key=lambda item: (item[0], item[1]))[2] if timed else None


def recorded_deadline(rec):
    """The record's deadline as a time, or None when it has none or it does not parse."""
    try:
        return parse_time(rec['deadline_utc']) if rec.get('deadline_utc') else None
    except (TypeError, ValueError):
        return None


def accrued(rec, until, to_deadline=False):
    """Price times the minutes from the launch request to `until` (rounded up); with
    `to_deadline`, never past the record's own deadline."""
    start = rec.get('launch_requested_utc') or rec.get('time_utc')
    price = rec.get('price_usd_per_hour')
    if not start or price is None:
        return 0.0
    deadline = recorded_deadline(rec) if to_deadline else None
    if deadline is not None and deadline < until:
        until = deadline
    minutes = max(0, math.ceil((until - parse_time(start)).total_seconds() / 60))
    return float(price) * minutes / 60


def _same_file(a, b):
    try:
        return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))
    except OSError:
        return str(a) == str(b)


def _request_time(row):
    return row.get('launch_requested_utc') or row.get('time_utc')


def holders(rec, rows_by_path):
    """The ledger files that hold a launch line (an intent or a launch) for this launch: one
    carrying its instance id, or its name with the same launch request time (a later launch
    reusing a name is another launch). Each file once, in reading order."""
    out = []
    for path, rows in rows_by_path:
        for row in rows:
            if row.get('event') not in ('launch_intent', 'launch'):
                continue
            same_id = bool(rec.get('instance_id')) and row.get('instance_id') == rec.get('instance_id')
            same_name = (row.get('instance_name') == rec.get('instance_name')
                         and _request_time(row) is not None and _request_time(row) == _request_time(rec))
            if same_id or same_name:
                out.append(path)
                break
    return out


def write_line(paths, line):
    for path in paths:
        with open(path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(line, sort_keys=True) + '\n')


def loop_instances(listed):
    """The listed instances that are loop instances and not already ending: every one of
    them, however many, is judged on its own record."""
    return [item for item in listed
            if str(item.get('name') or '').startswith(PREFIX)
            and item.get('status') not in ('terminated', 'terminating')]


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return None


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=1, sort_keys=True), encoding='utf-8')
    os.replace(temporary, path)


def usage_percent(path=None):
    """Seven-day usage from the status line's file, or None when it cannot be read."""
    try:
        value = json.loads(Path(path or LOOP_STATUS).read_text(encoding='utf-8')).get('seven_day_used_percentage')
    except (OSError, ValueError, AttributeError):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def last_heartbeat(paths=None):
    """The latest time any lead heartbeat file was written, or None when none exists."""
    times = []
    for path in (HEARTBEATS if paths is None else paths):
        try:
            times.append(datetime.fromtimestamp(Path(path).stat().st_mtime, timezone.utc))
        except OSError:
            pass
    return max(times) if times else None


def usage_stop(usage):
    """Trigger (a): seven-day usage at or above the stop percentage."""
    return usage is not None and usage >= USAGE_STOP_PERCENT


def lead_silent(now, beat):
    """Trigger (b): no heartbeat for SILENCE_MINUTES (none at all counts as silent)."""
    return beat is None or (now - beat).total_seconds() >= SILENCE_MINUTES * 60


def salvage_trigger(now, running, status_path=None, heartbeats=None):
    """Which D-S84 trigger fires, or None. Neither acts while no loop instance runs."""
    if not running:
        return None
    usage = usage_percent(status_path)
    if usage_stop(usage):
        return {'trigger': 'usage', 'seven_day_used_percentage': usage}
    beat = last_heartbeat(heartbeats)
    if lead_silent(now, beat):
        return {'trigger': 'lead_silent', 'last_heartbeat_utc': beat.isoformat() if beat else None,
                'silent_minutes': None if beat is None else int((now - beat).total_seconds() // 60)}
    return None


def request_path(name, kind='request'):
    return salvage_dir() / 'requests' / (name + '.' + kind + '.json')


def salvage_request(name):
    """The reaper's salvage request for this instance name, or None. The controller polls it; a
    salvage folder that cannot be found (git unreadable) is read as no request, never a crash."""
    import cloud_reference_spend
    try:
        return _read_json(request_path(name))
    except cloud_reference_spend.SpendStoreError:
        return None
    except (OSError, ValueError):
        return {'unreadable': True}


def write_salvage_done(name, record):
    """The controller's answer: its instance is stopped, what it packed and where."""
    _write_json(request_path(name, 'done'), record)


def salvage_overdue(now, requested_utc):
    """No answer within SALVAGE_ANSWER_SECONDS of the request."""
    return (now - parse_time(requested_utc)).total_seconds() >= SALVAGE_ANSWER_SECONDS


def salvage_pass(now, running, due, status_path=None, heartbeats=None):
    """D-S84 items 1 and 2 on one reaper pass. Opens an episode when a trigger fires, writes a
    request for every running loop instance, and adds to `due` each instance whose controller
    did not answer in time or answered while it is still listed. Returns the episode or None."""
    episode_path = salvage_dir() / 'episode.json'
    try:
        episode = _read_json(episode_path)
    except ValueError:
        episode = {'id': now.strftime('%Y%m%dT%H%M%SZ'), 'started_utc': now.isoformat(),
                   'trigger': {'trigger': 'episode_file_unreadable'}, 'instances': {}}
    if episode is None:
        trigger = salvage_trigger(now, running, status_path, heartbeats)
        if trigger is None:
            return None
        episode = {'id': now.strftime('%Y%m%dT%H%M%SZ'), 'started_utc': now.isoformat(), 'trigger': trigger,
                   'instances': {}}
    reasons = {item['name']: reason for item, reason in due}
    # D-412 item 5: a session-end episode applies only to the instances it named when it opened,
    # so one left open over a reboot is closed here, never applied to a launch made after it.
    named_only = (episode.get('trigger') or {}).get('trigger') == 'session_end'
    if named_only:
        # D-435: a launch made while a session-end episode is open is still covered by the usual
        # triggers; when one fires for it, it joins the episode with that trigger named.
        unnamed = [item for item in running if item['name'] not in episode['instances']]
        later = salvage_trigger(now, unnamed, status_path, heartbeats) if unnamed else None
        for item in unnamed if later else []:
            episode['instances'][item['name']] = {'instance_id': item.get('instance_id'), 'type': item.get('type'),
                                                  'region': item.get('region'), 'trigger': later}
    for item in running:
        name = item['name']
        if named_only and name not in episode['instances']:
            continue
        entry =episode['instances'].setdefault(name, {'instance_id': item.get('instance_id'),
                                                       'type': item.get('type'), 'region': item.get('region')})
        if name in reasons:
            entry.update(state='terminated_by_reaper', reason=reasons[name])
            continue
        request = salvage_request(name)
        if request is None or request.get('unreadable'):
            own = entry.get('trigger') or episode['trigger']   # D-439: an instance that joined later keeps its own
            request = {'episode': episode['id'], 'trigger': own['trigger'],
                       'requested_utc': now.isoformat(), 'finish_item_seconds': SALVAGE_ITEM_SECONDS}
            _write_json(request_path(name), request)
        entry.setdefault('requested_utc', request.get('requested_utc') or now.isoformat())
        try:
            done = _read_json(request_path(name, 'done'))
        except ValueError:
            done = {'unreadable': True}
        if done is not None:
            entry.update(state='salvaged', done=done)
            due.append((item, 'salvage_done_still_listed'))
        elif salvage_overdue(now, entry['requested_utc']):
            entry.update(state='no_answer')
            due.append((item, 'salvage_no_answer'))
        else:
            entry['state'] = 'waiting'
    listed = {item['name'] for item in running}
    for name, entry in episode['instances'].items():
        if name not in listed and entry.get('state') in (None, 'waiting'):
            try:
                done = _read_json(request_path(name, 'done'))
            except ValueError:
                done = {'unreadable': True}
            entry.update(state='salvaged' if done is not None else 'gone_without_answer', done=done)
    _write_json(episode_path, episode)
    return episode


def _money(value):
    return 'not recorded' if value is None else '%.2f USD' % value


def salvage_report(episode, now):
    """The report's text, from the episode alone (D-S84 item 3)."""
    return _salvage_report(episode, now)


def trigger_words(trigger):
    """One trigger in words, for the report and the FOR_SECKIN entry."""
    if trigger.get('trigger') == 'usage':
        said = 'seven-day usage at %s percent (stop at %d)' % (trigger.get('seven_day_used_percentage'), USAGE_STOP_PERCENT)
    elif trigger.get('trigger') == 'lead_silent':
        said = 'no lead heartbeat since %s (%s minutes; stop at %d)' % (
            trigger.get('last_heartbeat_utc') or 'never', trigger.get('silent_minutes'), SILENCE_MINUTES)
    elif trigger.get('trigger') == 'session_end':
        said = 'the session ended: Windows event %s (%s), every loop instance terminated first (D-412)' % (
            trigger.get('event_id', 'not recorded'), trigger.get('event', 'not recorded'))
        if trigger.get('stale_episode_closed'):
            said += '; an earlier session-end episode left open was closed as stale first (`%s`)' % (
                trigger['stale_episode_closed'])
    else:
        said = str(trigger.get('trigger'))
    return said


def _instance_lines(name, entry):
    """The report section of one instance: what was finished, what was lost, the cost."""
    done = entry.get('done') or {}
    lines = ['## ' + name, '']
    if entry.get('trigger'):
        lines.append('- Trigger for this instance: ' + trigger_words(entry['trigger']) + '.')
    return lines, done


def _salvage_report(episode, now):
    trigger = episode['trigger']
    said = trigger_words(trigger)
    lines = ['# Salvage report %s (D-S84)' % episode['id'], '',
             'Written by `tools/loop/instance_reaper.py`, with no Claude involved. The next lead session reads this first.', '',
             '- Trigger: ' + said + '.',
             '- Started: %s. Closed: %s.' % (episode['started_utc'], now.isoformat()),
             '- Instances: %d.' % len(episode['instances'])]
    total = [entry.get('cost_usd') for entry in episode['instances'].values()]
    lines.append('- Cost of these instances: ' + (_money(round(sum(total), 4)) if None not in total and total else
                                                 'not recorded for every instance; see each one') + '.')
    lines.append('')
    for name, entry in sorted(episode['instances'].items()):
        head, done = _instance_lines(name, entry)
        state = entry.get('state')
        lines += head + [
                  '- Instance: %s, type %s, region %s.' % (entry.get('instance_id'), entry.get('type'), entry.get('region')),
                  '- Requested: %s.' % entry.get('requested_utc', 'no request (terminated by the reaper first)')]
        if state == 'salvaged' and not done.get('unreadable'):
            lines.append('- Outcome: salvaged by its controller: the item in hand was given %d s, the workload stopped, '
                         'the evidence packed and copied, the instance terminated%s.'
                         % (SALVAGE_ITEM_SECONDS, ' and verified gone' if done.get('terminated') else ''))
            finished = done.get('finished') or []
            unfinished = done.get('unfinished') or []
            lines.append('- Finished: ' + (', '.join(map(str, finished)) if finished else 'none') + '.')
            lines.append('- Lost: ' + (', '.join(map(str, unfinished)) if unfinished else 'nothing beyond the item in hand')
                         + '; the item in hand when the workload stopped is lost unless it is under Finished.')
            packs = done.get('evidence') or []
            lines.append('- Packs: ' + (', '.join('`%s`' % p for p in packs) if packs else 'none copied') + '.')
            lines.append('- Run folder: `%s`.' % done.get('run_folder'))
            if done.get('stopped_by'):
                lines.append('- Controller stop: ' + str(done['stopped_by']) + '.')
            resume = ('re-seal the unfinished entries (%s) as a new bundle or batch and launch it; a bundle is launched once'
                      % ', '.join(map(str, unfinished))) if unfinished else (
                      're-seal and launch the run again if its own result is not complete; a bundle is launched once')
        elif state == 'terminated_by_reaper':
            lines.append('- Outcome: terminated by the reaper for %s before any salvage answer.' % entry.get('reason'))
            lines.append('- Finished: whatever its run folder held before the stop. Lost: the rest.')
            lines.append('- Packs: none copied by a salvage answer.')
            resume = 're-seal from its last finished item or checkpoint in its run folder and launch it'
        else:
            what = {'no_answer': 'no answer within %d s of the request: terminated anyway' % SALVAGE_ANSWER_SECONDS,
                    'gone_without_answer': 'gone with no answer (its controller ended it, or it was ended elsewhere)'}
            lines.append('- Outcome: ' + what.get(state, str(state)) + '.')
            lines.append('- Finished: whatever its run folder held before the stop. Lost: the item in hand and anything '
                         'not yet collected.')
            lines.append('- Packs: none copied by a salvage answer; the run folder keeps what was already collected.')
            resume = 're-seal from its last finished item or checkpoint in its run folder and launch it'
        lines.append('- Cost: %s (%s minutes).' % (_money(entry.get('cost_usd')), entry.get('minutes', 'not recorded')))
        lines.append('- Verified gone: %s.' % ('yes' if entry.get('verified_gone') else 'no'))
        lines += ['- Resume: ' + resume + '.', '']
    stale = episode.get('stale_instances') or {}
    if stale:
        # D-439: the stale episode's own instances, each with what was finished, lost and its cost
        lines += ['# The earlier session-end episode closed as stale (%s)' % trigger.get('stale_episode_closed'), '']
        for name, entry in sorted(stale.items()):
            done = entry.get('done') or {}
            lines += ['## ' + name, '', '- State when that episode was left: %s.' % entry.get('state'),
                      '- Finished: ' + (', '.join(map(str, done.get('finished') or [])) or 'none recorded') + '.',
                      '- Lost: ' + (', '.join(map(str, done.get('unfinished') or [])) or
                                    'whatever its run folder did not already hold') + '.',
                      '- Cost: %s (%s minutes).' % (_money(entry.get('cost_usd')), entry.get('minutes', 'not recorded')), '']
    return '\n'.join(lines)


def episode_triggers(episode):
    """Every trigger of an episode in words: its own, and each later instance's (D-439)."""
    words = [trigger_words(episode['trigger'])]
    for _name, entry in sorted(episode['instances'].items()):
        if entry.get('trigger') and trigger_words(entry['trigger']) not in words:
            words.append(trigger_words(entry['trigger']))
    if episode.get('stale_instances'):
        words.append('%d instance(s) of an earlier session-end episode closed as stale' % len(episode['stale_instances']))
    return '; '.join(words)


def close_salvage(provider, episode, now, rows, costs):
    """Verify every instance of the episode gone; then write the report and the FOR_SECKIN
    entry, and move the episode's files into its own folder. Returns the report path or None."""
    if any(entry.get('state') == 'waiting' for entry in episode['instances'].values()):
        return None
    after = [item for item in provider.request('instances')['data'] if item.get('status') != 'terminated']
    names = {item.get('name') for item in after}
    for name, entry in episode['instances'].items():
        entry['verified_gone'] = name not in names
        done = entry.get('done') or {}
        if name in costs:
            entry['minutes'], entry['cost_usd'] = costs[name]
        elif done.get('actual_cost') is not None:
            entry['minutes'], entry['cost_usd'] = done.get('actual_minutes'), done['actual_cost']
        else:
            ended = [r for r in rows if r.get('event') == 'termination' and r.get('instance_name') == name]
            if ended and ended[-1].get('actual_cost') is not None:
                entry['minutes'], entry['cost_usd'] = ended[-1].get('actual_minutes'), ended[-1]['actual_cost']
    _write_json(salvage_dir() / 'episode.json', episode)
    if not all(entry['verified_gone'] for entry in episode['instances'].values()):
        return None
    report = Path(REPORT_DIR) / ('SALVAGE_REPORT_' + episode['id'] + '.md')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(salvage_report(episode, now) + '\n', encoding='utf-8')
    entry = ('## %s Salvage and stop (D-S84): %d loop instance(s) stopped\n\n'
             'Trigger: %s. Read `%s` first: what was finished, what was lost, the cost, the packs and how '
             'each run resumes.\n' % (now.strftime('%Y-%m-%d %H:%M UTC'), len(episode['instances']),
                                      episode_triggers(episode), report.name))
    folder = salvage_dir() / episode['id']
    folder.mkdir(parents=True, exist_ok=True)
    note_salvage(entry, folder)
    for name in episode['instances']:
        for kind in ('request', 'done'):
            source = request_path(name, kind)
            if source.exists():
                os.replace(source, folder / source.name)
    os.replace(salvage_dir() / 'episode.json', folder / 'episode.json')
    return str(report)


def reap(provider, ledger_paths, append_path, now=None, salvage=True):
    """One reaper pass. Returns a status dict with no key material. `salvage` False skips
    the D-S84 pass (a proof run on a mock provider names no salvage folder).

    A line about a launch a ledger records is written to every ledger file holding it
    (``holders``); `append_path` receives a line only for a listed loop instance no ledger
    records."""
    now = now or utc_now()
    rows = []
    rows_by_path = []
    for path in ledger_paths:
        if any(_same_file(path, seen) for seen, _ in rows_by_path):
            continue
        read = read_ledger(path)
        rows_by_path.append((Path(path), read))
        rows.extend(read)
    targets = lambda rec: (holders(rec, rows_by_path) if rec is not None else []) or [Path(append_path)]
    by_name, closed, spend = ledger_view(rows, now)
    budget, hard_stop = budget_figures(rows)
    listed = provider.request('instances')['data']
    running = loop_instances(listed)
    terminated = []
    due = []
    for item in running:
        rec = by_name.get(item['name'])
        if hard_stop is None:
            reason = 'no_budget_recorded'
        elif spend >= hard_stop:
            reason = 'hard_stop_spend_reached'
        elif rec is None or not rec.get('deadline_utc'):
            reason = 'no_recorded_deadline'
        elif now >= parse_time(rec['deadline_utc']):
            reason = 'deadline_passed'
        else:
            continue
        due.append((item, reason))
    salvage_error = None
    try:
        episode = salvage_pass(now, running, due) if salvage else None
    except Exception as exc:  # the deadline and the hard stop above still bound every instance
        episode, salvage_error = None, type(exc).__name__
    costs = {}
    for item, reason in due:
        name = item['name']
        rec = by_name.get(name)
        provider.terminate(item['instance_id'])
        minutes = None
        cost = None
        if rec is not None and rec.get('launch_requested_utc') and rec.get('price_usd_per_hour') is not None:
            minutes = max(0, math.ceil((now - parse_time(rec['launch_requested_utc'])).total_seconds() / 60))
            cost = round(float(rec['price_usd_per_hour']) * minutes / 60, 4)
        line = {'event': 'termination', 'by': 'reaper', 'time_utc': now.isoformat(),
                'instance_id': item['instance_id'], 'instance_name': name, 'reason': reason,
                'type': item.get('type'), 'region': item.get('region'),
                'actual_minutes': minutes, 'actual_cost': cost}
        write_line(targets(rec), line)
        terminated.append({'instance_name': name, 'reason': reason})
        costs[name] = (minutes, cost)
    # A launch still open in the ledger past its recorded deadline, with no instance of its
    # name listed, is closed here: an intent whose launch created no instance (the
    # controller died between the intent line and the launch reply), or a launch whose
    # instance is already gone. Left open, it would keep counting as a running loop instance
    # (and its cap as a running cap) in every guard decision. Its line is charged to the deadline: a ceiling, counted as
    # actual and never refunded, which its reason names. It is written to every ledger file
    # that holds the launch, so R's guard, which reads R's ledger, sees it closed too.
    listed_names = {item['name'] for item in running}
    closed_now = []
    for name, rec in by_name.items():
        deadline = recorded_deadline(rec)
        if (rec['ident'] in closed or name in listed_names or deadline is None or now < deadline
                or not (rec.get('event') == 'launch' or rec.get('launch_requested_utc'))):
            continue
        reason = ('intent_without_instance' if rec.get('event') == 'launch_intent'
                  else 'instance_not_listed_charged_to_deadline')
        start = rec.get('launch_requested_utc') or rec.get('time_utc')
        minutes = cost = None
        if start and rec.get('price_usd_per_hour') is not None:
            minutes = max(0, math.ceil((deadline - parse_time(start)).total_seconds() / 60))
            cost = round(float(rec['price_usd_per_hour']) * minutes / 60, 4)
        line = {'event': 'termination', 'by': 'reaper', 'time_utc': now.isoformat(),
                'instance_id': rec.get('instance_id'), 'instance_name': name, 'reason': reason,
                'type': rec.get('type'), 'region': rec.get('region'),
                'actual_minutes': minutes, 'actual_cost': cost}
        write_line(targets(rec), line)
        closed_now.append({'instance_name': name, 'reason': reason})
    salvage = None
    if episode is not None:
        report = None
        try:
            report = close_salvage(provider, episode, now, rows, costs)
        except Exception as exc:
            salvage_error = type(exc).__name__
        salvage = {'episode': episode['id'], 'trigger': episode['trigger'].get('trigger'), 'report': report,
                   'states': {name: entry.get('state') for name, entry in sorted(episode['instances'].items())}}
    return {'last_run_utc': now.isoformat(), 'listed': len(listed),
            'loop_running': len(running), 'terminated': terminated, 'closed_without_instance': closed_now,
            'total_spend_usd': round(spend, 4), 'budget_usd': budget, 'hard_stop_usd': hard_stop,
            'warning_usd': warning_figure(rows),
            # a budget line field not declared in BUDGET_LINE_FIELDS is named, never dropped silently
            'budget_line_fields_unknown': sorted({k for r in rows if r.get('event') in BUDGET_EVENTS for k in r}
                                                 - set(BUDGET_LINE_FIELDS)),
            'salvage': salvage, 'salvage_error': salvage_error, 'error': None}


class MockProvider:
    """A provider backed by a JSON file, for proofs. Same two calls as the real one."""
    def __init__(self, state_path):
        self.state_path = Path(state_path)

    def _load(self):
        return json.loads(self.state_path.read_text(encoding='utf-8'))

    def request(self, path, body=None):
        if path != 'instances':
            raise ValueError('mock provider: only instances may be listed')
        state = self._load()
        if state.get('raise_with'):
            # Proof hook: a provider failure whose message carries a key-shaped string.
            raise RuntimeError('provider said: ' + state['raise_with'])
        return {'data': [dict(item) for item in state['instances']]}

    def terminate(self, instance_id):
        state = self._load()
        for item in state['instances']:
            if item['instance_id'] == instance_id:
                item['status'] = 'terminated'
        self.state_path.write_text(json.dumps(state, indent=1), encoding='utf-8')


def real_provider():
    sys.path.insert(0, str(ROOT / 'tools'))
    sys.path.insert(0, str(ROOT / 'scripts'))
    from agent_wrapper import resolve_config_path  # the existing resolver, unchanged
    from cloud_run_watchdog import LambdaTermination
    path = resolve_config_path()
    if path is None:
        raise RuntimeError('no credential file resolved; set SHIMMER_CONFIG_PATH')
    return LambdaTermination(str(path))


TURKEY = timezone(timedelta(hours=3))


def figure(value):
    """A dollar figure as a heading writes it: 270 for 270.0, 50.5 for 50.5."""
    return '%g' % float(value)


def warning_marker(kind, warning):
    """The part of a warning heading that names it once (D-464 item 4): its kind and its figure."""
    return 'UYARI: %s harcaması %s USD uyarı eşiğinde' % (kind, figure(warning))


def warning_entry(kind, warning, spent, stop, now):
    """One FOR_SECKIN warning entry in the form order 3 reads (D-S103 item 2, D-S121): a heading
    naming the warning figure, an entry stating the spend in USD and the stop."""
    return ('## %s %s (D-S121)\n\n%s harcaması %.2f USD; uyarı %s USD, durma %s USD.\n'
            % (now.astimezone(TURKEY).strftime('%Y-%m-%d %H:%M +0300'), warning_marker(kind, warning), kind,
               spent, figure(warning), figure(stop)))


def warnings_due(status, store):
    """[(kind, warning, spent, stop)] for each ceiling whose warning is reached: Lambda from this
    pass's own status (accrued spend against the budget line's warning_usd), the API from the spend
    store (closed spend and running caps against its latest ceiling line). Neither is a code figure."""
    import cloud_reference_spend
    due = []
    if status.get('warning_usd') is not None and status.get('total_spend_usd') is not None \
            and status.get('budget_usd') is not None and status['total_spend_usd'] >= status['warning_usd']:
        due.append(('Lambda', status['warning_usd'], status['total_spend_usd'], status['budget_usd']))
    limits = cloud_reference_spend.ceiling(store)
    if limits is not None:
        figures = cloud_reference_spend.state(store)
        spent = figures['spent_usd'] + figures['running_caps_usd']
        if spent >= limits['warning_usd']:
            due.append(('API', limits['warning_usd'], spent, limits['ceiling_usd']))
    return due


FOR_SECKIN_LOCK_STALE_SECONDS = 120   # a writer holds it for one read and one move


class ForSeckinLocked(Exception):
    """FOR_SECKIN's lock is held by another writer; this pass writes nothing and the next retries."""


def put_on_top(entries_for):
    """Write FOR_SECKIN under its lock (`FOR_SECKIN.md.lock`, created exclusively; one older than
    FOR_SECKIN_LOCK_STALE_SECONDS is replaced) by append-and-move: the file is read, the entries
    `entries_for(old)` returns are put under its title, the result written beside it and moved over
    it in one step, so no reader sees half a file (D-467 item 3). Returns the entries written. The
    lead's own edits and the push stay the lead's step."""
    target = Path(FOR_SECKIN)
    lock = target.with_name(target.name + '.lock')
    moving = target.with_name('%s.%d.tmp' % (target.name, os.getpid()))
    for _ in range(2):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except FileNotFoundError:
                continue
            if age < FOR_SECKIN_LOCK_STALE_SECONDS:
                raise ForSeckinLocked(lock.name)
            try:
                lock.unlink()
            except FileNotFoundError:
                pass
    else:
        raise ForSeckinLocked(lock.name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(json.dumps({'pid': os.getpid(), 'epoch': time.time()}))
        try:
            old = target.read_text(encoding='utf-8')
        except FileNotFoundError:
            old = ''
        entries = entries_for(old)
        if entries:
            head, _, rest = old.partition('\n')
            block = '\n'.join(entries)
            body = (head + '\n\n' + block + '\n' + rest.lstrip('\n')) if head.startswith('# ') else (block + '\n' + old)
            moving.write_text(body, encoding='utf-8')
            os.replace(moving, target)
        return entries
    finally:
        for left in (moving, lock):   # a failed move leaves no tmp file behind (D-469)
            try:
                left.unlink()
            except FileNotFoundError:
                pass


SALVAGE_NOTE_ATTEMPTS = 5          # tries for FOR_SECKIN's lock before the fallback file
SALVAGE_NOTE_WAIT_SECONDS = 2.0
SALVAGE_NOTE_FALLBACK = 'FOR_SECKIN_ENTRY.md'


def note_salvage(entry, folder, sleep=time.sleep):
    """Put a salvage entry at the top of FOR_SECKIN under its lock (`put_on_top`, D-467 item 3).
    A salvage entry is never lost: while the lock is held it is tried SALVAGE_NOTE_ATTEMPTS times,
    SALVAGE_NOTE_WAIT_SECONDS apart, and then written to SALVAGE_NOTE_FALLBACK in the episode's own
    folder. Returns 'for_seckin' or the fallback file's path."""
    for attempt in range(SALVAGE_NOTE_ATTEMPTS):
        try:
            put_on_top(lambda old: [entry])
            return 'for_seckin'
        except ForSeckinLocked:
            if attempt + 1 < SALVAGE_NOTE_ATTEMPTS:
                sleep(SALVAGE_NOTE_WAIT_SECONDS)
    fallback = Path(folder) / SALVAGE_NOTE_FALLBACK
    fallback.parent.mkdir(parents=True, exist_ok=True)
    with fallback.open('a', encoding='utf-8') as handle:
        handle.write(entry + '\n')
    return str(fallback)


def note_warnings(status, store, now):
    """Put each warning reached at the top of FOR_SECKIN once (one entry per kind and figure),
    through `put_on_top`; returns the kinds written. The guard's warning_reached and api_room's warn
    mark the launch or run that would reach it; this pass writes the note once the spend or the
    run's cap stands. A held lock raises ForSeckinLocked: nothing is written, the next pass retries."""
    due = warnings_due(status, store)
    entries = put_on_top(lambda old: [warning_entry(kind, warning, spent, stop, now)
                                      for kind, warning, spent, stop in due if warning_marker(kind, warning) not in old])
    return [e.split(' UYARI: ', 1)[1].split(' harcaması', 1)[0] for e in entries]


def main(argv=None):
    parser = argparse.ArgumentParser(description='Terminate loop instances past their deadline.')
    parser.add_argument('--mock-state', help='JSON file standing in for the provider (proofs only)')
    parser.add_argument('--ledger', action='append', help='ledger to read (repeatable); default: private and R ledgers')
    parser.add_argument('--append-to', help='ledger that receives a line for a loop instance no ledger records '
                                            '(a recorded launch is closed in every ledger holding it); '
                                            'default: the private ledger')
    parser.add_argument('--status', help='status file; default: docs/loop/private/reaper_status.json')
    parser.add_argument('--now', help='ISO time to use instead of the clock (proofs only)')
    parser.add_argument('--salvage-dir', help='D-S84 salvage folder; with --mock-state and none given, no salvage pass')
    parser.add_argument('--loop-status', help='usage status file (default .claude/loop_status.json)')
    parser.add_argument('--heartbeat', action='append', help='lead heartbeat file (repeatable; default the three records)')
    parser.add_argument('--report-dir', help='folder for SALVAGE_REPORT_<time>.md (default docs/loop/private)')
    parser.add_argument('--for-seckin', help='file that receives the top entry (default docs/loop/private/FOR_SECKIN.md)')
    parser.add_argument('--spend-store', help='the API spend store read for its warning (default the main checkout\'s); '
                                              'with --mock-state and no --for-seckin, no warning is written')
    args = parser.parse_args(argv)
    global SALVAGE_DIR, LOOP_STATUS, HEARTBEATS, REPORT_DIR, FOR_SECKIN
    if args.salvage_dir:
        SALVAGE_DIR = Path(args.salvage_dir)
    if args.loop_status:
        LOOP_STATUS = Path(args.loop_status)
    if args.heartbeat:
        HEARTBEATS = tuple(Path(p) for p in args.heartbeat)
    if args.report_dir:
        REPORT_DIR = Path(args.report_dir)
    if args.for_seckin:
        FOR_SECKIN = Path(args.for_seckin)
    salvage = bool(args.salvage_dir) or not args.mock_state
    ledgers = [Path(p) for p in args.ledger] if args.ledger else [PRIVATE_LEDGER, R_LEDGER]
    append_path = Path(args.append_to) if args.append_to else PRIVATE_LEDGER
    status_path = Path(args.status) if args.status else STATUS
    now = parse_time(args.now) if args.now else utc_now()
    try:
        provider = MockProvider(args.mock_state) if args.mock_state else real_provider()
        status = reap(provider, ledgers, append_path, now=now, salvage=salvage)
        code = 0
    except Exception as exc:  # never let a provider message (which could echo a header) out
        status = {'last_run_utc': now.isoformat(), 'error': type(exc).__name__}
        code = 1
    if code == 0 and (args.for_seckin or not args.mock_state):
        try:
            import cloud_reference_spend
            store = Path(args.spend_store) if args.spend_store else cloud_reference_spend.store_path(ROOT)
            status['warnings_written'] = note_warnings(status, store, now)
        except Exception as exc:   # a warning note never stops the terminations
            status['warning_note_error'] = type(exc).__name__
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=1, sort_keys=True), encoding='utf-8')
    print(json.dumps(status, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
