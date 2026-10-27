"""Loop instance reaper: terminate loop instances that outlive their recorded deadline.

Loop machinery, not product code. It runs every five minutes from a per-user Windows
scheduled task, so termination never depends on a Claude Code session staying alive.

What it does on every run:
1. Reads the loop's private ledger and role R's ledger (JSON lines).
2. Lists instances through the provider (observation and termination only; it can
   never launch anything).
3. Terminates every instance whose name starts with ``shimmer-loop-`` that is past its
   recorded deadline, or that has no recorded deadline, and every loop instance once
   total loop spend reaches the hard stop (49 USD).
4. Appends one ledger line per termination and writes ``reaper_status.json``.

It never touches an instance without the loop prefix, and it never prints a key: every
provider error is reduced to its class name before it reaches output.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'shimmer-loop-'
HARD_STOP_USD = 49.0
PRIVATE_LEDGER = ROOT / 'docs' / 'loop' / 'private' / 'budget_ledger.jsonl'
R_LEDGER = Path.home() / 'local' / 'shimmer-roles' / '_handoff' / 'R_ledger.jsonl'
STATUS = ROOT / 'docs' / 'loop' / 'private' / 'reaper_status.json'


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
    """Return per-instance records keyed by name, and total spend counted once per launch.

    A launch is identified by its instance id when known, else by its name. Each launch is
    counted once across both ledgers: a closed launch by its recorded actual cost, an open
    one by its price times the minutes since the launch request (rounded up, which
    overstates slightly and is safe). The storage share accrues from the loop's start.
    """
    launches = {}
    closed = {}
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
        elif event == 'termination':
            ident = row.get('instance_id') or row.get('instance_name')
            if ident:
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
            spend += accrued(rec, now)
    if loop_start and storage_rate:
        days = max(0.0, (now - parse_time(loop_start)).total_seconds() / 86400)
        spend += storage_rate * days
    return by_name, closed, spend


def accrued(rec, until):
    start = rec.get('launch_requested_utc') or rec.get('time_utc')
    price = rec.get('price_usd_per_hour')
    if not start or price is None:
        return 0.0
    minutes = max(0, math.ceil((until - parse_time(start)).total_seconds() / 60))
    return float(price) * minutes / 60


def reap(provider, ledger_paths, append_path, now=None, hard_stop=HARD_STOP_USD):
    """One reaper pass. Returns a status dict with no key material."""
    now = now or utc_now()
    rows = []
    for path in ledger_paths:
        rows.extend(read_ledger(path))
    by_name, closed, spend = ledger_view(rows, now)
    listed = provider.request('instances')['data']
    running = [item for item in listed
               if str(item.get('name') or '').startswith(PREFIX)
               and item.get('status') not in ('terminated', 'terminating')]
    terminated = []
    for item in running:
        name = item['name']
        rec = by_name.get(name)
        if spend >= hard_stop:
            reason = 'hard_stop_spend_reached'
        elif rec is None or not rec.get('deadline_utc'):
            reason = 'no_recorded_deadline'
        elif now >= parse_time(rec['deadline_utc']):
            reason = 'deadline_passed'
        else:
            continue
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
        with open(append_path, 'a', encoding='utf-8') as handle:
            handle.write(json.dumps(line, sort_keys=True) + '\n')
        terminated.append({'instance_name': name, 'reason': reason})
    return {'last_run_utc': now.isoformat(), 'listed': len(listed),
            'loop_running': len(running), 'terminated': terminated,
            'total_spend_usd': round(spend, 4), 'hard_stop_usd': hard_stop, 'error': None}


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


def main(argv=None):
    parser = argparse.ArgumentParser(description='Terminate loop instances past their deadline.')
    parser.add_argument('--mock-state', help='JSON file standing in for the provider (proofs only)')
    parser.add_argument('--ledger', action='append', help='ledger to read (repeatable); default: private and R ledgers')
    parser.add_argument('--append-to', help='ledger that receives termination lines; default: the private ledger')
    parser.add_argument('--status', help='status file; default: docs/loop/private/reaper_status.json')
    parser.add_argument('--now', help='ISO time to use instead of the clock (proofs only)')
    args = parser.parse_args(argv)
    ledgers = [Path(p) for p in args.ledger] if args.ledger else [PRIVATE_LEDGER, R_LEDGER]
    append_path = Path(args.append_to) if args.append_to else PRIVATE_LEDGER
    status_path = Path(args.status) if args.status else STATUS
    now = parse_time(args.now) if args.now else utc_now()
    try:
        provider = MockProvider(args.mock_state) if args.mock_state else real_provider()
        status = reap(provider, ledgers, append_path, now=now)
        code = 0
    except Exception as exc:  # never let a provider message (which could echo a header) out
        status = {'last_run_utc': now.isoformat(), 'error': type(exc).__name__}
        code = 1
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=1, sort_keys=True), encoding='utf-8')
    print(json.dumps(status, sort_keys=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
