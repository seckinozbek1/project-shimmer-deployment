"""Loop budget guard, instance-type rule and ledger writer for every loop launch path (IV.3).

Nothing here calls a provider. The controller reads the live price and the inventory
through the allowlisted adapter and hands them in; this module only decides.

The guard always reads the ledgers the reaper reads (the private ledger and R's ledger,
tools/loop/instance_reaper.py) beside any it is given, needs a `budget_open` line among
them, and refuses a launch whose own ledger is not one the reaper reads, so a wrong or new
path can never read as zero spend while the reaper kills the unrecorded instance. It
refuses a launch, in one line, when:
  * another loop instance runs (an open launch in a ledger, or a `shimmer-loop-` name
    in the provider inventory the caller listed);
  * the per-run cap formula leaves less than the forecast:
        cap = min(1.5 x forecast, 50 - spend - caps of running loop instances
                  - storage forecast - 1);
  * the capped run time (cap / live price) does not cover the forecast time plus the
    run's stop reserve (the runner stops its workload that long before the ceiling).
"Spend + forecast + storage passes 50" needs no refusal of its own: the cap rule already
keeps it at or below 49. Spend is counted once per launch by instance id or name across
every ledger read (the reaper's own reading, so a line copied from R's ledger with
`copied_from` is not counted twice). The forecast is the measured basis in minutes times
the live price times 1.3.

Ledger lines carry exactly the declared IV.3 fields (and the reaper's `by` and `reason`,
the lead's `copied_from`) and nothing else: no test content, ever. A purpose is a short
identifier, never prose.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
_LOOP = str(ROOT / 'tools' / 'loop')
if _LOOP not in sys.path:
    sys.path.append(_LOOP)
import instance_reaper  # noqa: E402  (the reaper's ledger reading is the one reading)

PREFIX = instance_reaper.PREFIX
# Constants of the loop's budget rule (IV.3), not run settings: the total budget, the
# one-dollar margin, the cap and forecast factors and the type-rule factor.
BUDGET_USD = 50.0
RESERVE_USD = 1.0
CAP_FACTOR = 1.5
FORECAST_FACTOR = 1.3
TYPE_RULE_FACTOR = 2.0
PREFERRED_TYPE = 'gpu_1x_a10'
PREFERRED_REGION = 'us-east-1'
POLL_LIMIT_SECONDS = 1800
POLL_INTERVAL_SECONDS = 60
EVENTS = ('launch_intent', 'launch', 'termination')
LEDGER_FIELDS = ('event', 'time_utc', 'launch_requested_utc', 'instance_id', 'instance_name', 'type', 'region',
                 'price_usd_per_hour', 'purpose', 'forecast_usd', 'cap_usd', 'deadline_utc', 'actual_minutes',
                 'actual_cost', 'by', 'reason', 'copied_from')
PURPOSE = re.compile(r'[a-z0-9][a-z0-9-]{0,39}')
R_INPUT_FIELDS = ('spend_usd', 'storage_forecast_usd', 'allocation_left_usd', 'forecast_usd', 'cap_usd', 'instance_type')
# The run's own needs, not an instance type's: the VRAM the frozen checkpoints were
# admitted with on the A10, and the host floors the runner has always required.
RUN_GPU_TOTAL_BYTES = 23_000_000_000
RUN_GPU_FREE_BYTES = 20 * 2**30
RUN_RAM_AVAILABLE_BYTES = 40 * 2**30
RUN_DISK_FREE_BYTES = 30 * 2**30
HOST_FRACTION = 0.95


class GuardRefusal(RuntimeError):
    """A one-line refusal. Messages carry figures and field names only."""


def refuse(condition, message):
    if not condition:
        raise GuardRefusal(message)


def utc(epoch):
    return datetime.fromtimestamp(float(epoch), timezone.utc).isoformat()


def number(value, name, positive=True):
    refuse(type(value) in (int, float) and math.isfinite(value) and (value > 0 if positive else value >= 0),
           'Invalid ' + name)
    return float(value)


def instance_name(tag):
    """Every loop instance is named `shimmer-loop-<tag>`; the reaper acts on that prefix only."""
    refuse(isinstance(tag, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,40}', tag) is not None, 'Invalid instance tag')
    return PREFIX + tag


def forecast_usd(minutes, hourly_rate):
    """IV.3: the measured basis in minutes, times the live price, times 1.3."""
    return number(minutes, 'forecast minutes') / 60 * number(hourly_rate, 'hourly rate') * FORECAST_FACTOR


def per_run_cap(forecast, spend, running_caps, storage_forecast, budget=BUDGET_USD):
    """IV.3: min(1.5 x forecast, budget - spend - running caps - storage forecast - 1)."""
    return min(CAP_FACTOR * forecast, budget - spend - running_caps - storage_forecast - RESERVE_USD)


def reaper_ledgers():
    """The ledgers the scheduled reaper reads, resolved at call time."""
    return [Path(instance_reaper.PRIVATE_LEDGER), Path(instance_reaper.R_LEDGER)]


def same_path(a, b):
    return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


def ledger_set(ledgers, reaped=None):
    """The ledgers given, plus the reaper's, each once."""
    out = []
    for path in [*map(Path, ledgers), *(reaper_ledgers() if reaped is None else map(Path, reaped))]:
        if not any(same_path(path, seen) for seen in out):
            out.append(path)
    return out


def require_reaped(ledger, reaped=None):
    """A launch's own ledger must be one the reaper reads, or the reaper would find no
    deadline for the instance and its cost would be counted nowhere."""
    refuse(any(same_path(ledger, r) for r in (reaper_ledgers() if reaped is None else reaped)),
           'The launch ledger is not one the reaper reads')


def ledger_state(ledgers, now_epoch):
    """(spend, running launches, running caps, rows), each launch counted once by id or name."""
    rows = []
    for path in ledgers:
        rows.extend(instance_reaper.read_ledger(path))
    now = datetime.fromtimestamp(float(now_epoch), timezone.utc)
    by_name, closed, spend = instance_reaper.ledger_view(rows, now)
    running = [rec for rec in by_name.values()
               if rec['ident'] not in closed and (rec.get('event') == 'launch' or rec.get('launch_requested_utc'))]
    caps = sum(float(rec.get('cap_usd') or 0) for rec in running)
    return spend, running, caps, rows


def a10_reference_rate(ledgers):
    """The A10's last recorded price (the type rule's reference), from the ledger's opening line."""
    rate = None
    for path in ledgers:
        for row in instance_reaper.read_ledger(path):
            if row.get('event') == 'budget_open' and row.get('a10_reference_price_usd_per_hour') is not None:
                rate = row['a10_reference_price_usd_per_hour']
    refuse(rate is not None, 'No recorded A10 reference price in the ledgers given')
    return number(rate, 'A10 reference price')


def read_r_inputs(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    refuse(isinstance(value, dict) and all(k in value for k in R_INPUT_FIELDS), 'R_INPUTS.json lacks a budget field')
    return {k: value[k] for k in R_INPUT_FIELDS}


def check(*, ledgers, forecast_minutes, hourly_rate, storage_forecast_usd, now_epoch, reserve_minutes,
          provider_names=(), instance_type=None, r_inputs=None, reaped=None, budget=BUDGET_USD):
    """Decide one loop launch. Returns the cap and the figures it rests on, or refuses.

    `reaped` replaces the reaper's ledgers only for a mocked launch (the rehearsal and the
    fixtures); a real launch reads the reaper's own."""
    ledgers = ledger_set([Path(p) for p in ledgers], reaped)
    forecast = forecast_usd(forecast_minutes, hourly_rate)
    storage = number(storage_forecast_usd, 'storage forecast', positive=False)
    reserve = number(reserve_minutes, 'reserve minutes', positive=False)
    spend, running, running_caps, rows = ledger_state(ledgers, now_epoch)
    refuse(any(r.get('event') == 'budget_open' for r in rows), 'No budget_open line in the loop ledgers')
    if r_inputs is not None:
        r = read_r_inputs(r_inputs)
        spend = max(spend, number(r['spend_usd'], 'R spend', positive=False))
        storage = max(storage, number(r['storage_forecast_usd'], 'R storage forecast', positive=False))
        refuse(instance_type is None or r['instance_type'] == instance_type, 'Instance type differs from R_INPUTS.json')
        refuse(forecast <= number(r['allocation_left_usd'], 'R allocation', positive=False),
               'Forecast %.2f dollars exceeds the allocation left %.2f dollars' % (forecast, r['allocation_left_usd']))
    others = sorted(n for n in provider_names if str(n).startswith(PREFIX))
    refuse(not running and not others, 'Another loop instance is running; at most one at a time')
    cap = per_run_cap(forecast, spend, running_caps, storage, budget)
    if r_inputs is not None:
        cap = min(cap, number(r['cap_usd'], 'R cap'))
    refuse(cap >= forecast, 'Per-run cap %.2f dollars leaves less than the forecast %.2f dollars' % (cap, forecast))
    capped_minutes = cap / hourly_rate * 60
    refuse(capped_minutes >= forecast_minutes + reserve,
           'Capped run time %.1f min does not cover the forecast %.1f min and the %.1f min stop reserve'
           % (capped_minutes, forecast_minutes, reserve))
    return dict(forecast_usd=round(forecast, 4), cap_usd=round(cap, 4), capped_minutes=round(capped_minutes, 2),
                spend_usd=round(spend, 4), running_caps_usd=round(running_caps, 4), storage_forecast_usd=storage)


def undeclared(fields):
    """The field names a ledger line may not carry."""
    return set(fields) - set(LEDGER_FIELDS)


def ledger_line(event, **fields):
    """One ledger line with exactly the declared fields; anything else is refused, never dropped."""
    refuse(event in EVENTS, 'Unknown ledger event')
    extra = undeclared(fields)
    refuse(not extra, 'Ledger line field outside IV.3: ' + ','.join(sorted(extra)))
    refuse(str(fields.get('instance_name', '')).startswith(PREFIX), 'Ledger line without a loop instance name')
    if 'purpose' in fields:
        refuse(isinstance(fields['purpose'], str) and PURPOSE.fullmatch(fields['purpose']) is not None,
               'Purpose must be a short identifier (lower case, digits, hyphens)')
    if event == 'launch_intent':
        refuse(fields.get('deadline_utc') and fields.get('launch_requested_utc'), 'Intent needs a deadline and a request time')
    return dict(event=event, **fields)


def append(path, line):
    refuse('event' in line and not undeclared(line), 'Ledger line field outside IV.3')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(line, sort_keys=True) + '\n')


# ---- one launch decision at a time (A12) -------------------------------------------------

def acquire_lock(ledger):
    """An exclusive lock beside the ledger, held from the guard's decision through the intent
    line, so two controllers can never both pass the guard for one free slot. A lock left by
    a crash is reported with its holder and time, never broken silently."""
    lock = Path(str(ledger) + '.lock')
    try:
        with open(lock, 'x', encoding='utf-8') as handle:
            handle.write(json.dumps(dict(pid=os.getpid(), time_utc=utc(time.time()))) + '\n')
    except FileExistsError:
        raise GuardRefusal('Another launch holds the ledger lock (' + lock.name
                           + '); remove it only if no launch is running') from None
    return lock


def release_lock(lock):
    if lock is not None:
        Path(lock).unlink(missing_ok=True)


# ---- the general cloud path while the loop is open (A11) ---------------------------------

def loop_open(ledgers=None):
    """True while a loop ledger opened by `budget_open` has not been closed by `budget_close`."""
    state = None
    for path in (reaper_ledgers() if ledgers is None else ledgers):
        for row in instance_reaper.read_ledger(path):
            if row.get('event') == 'budget_open':
                state = True
            elif row.get('event') == 'budget_close':
                state = False
    return bool(state)


def refuse_while_loop_open(ledgers=None):
    """The general cloud path spends outside the loop's ledger, so it does not launch while
    the loop's budget is open."""
    refuse(not loop_open(ledgers), 'The loop budget is open: the general cloud path does not launch until it is closed')


# ---- the instance-type rule (IV.3, R3) ------------------------------------------------

def gpu_bytes(description):
    """VRAM from the provider's GPU description ('A10 (24 GB PCIe)'), or 0 if unstated."""
    found = re.search(r'(\d+(?:\.\d+)?)\s*GB', str(description or ''))
    return int(float(found.group(1)) * 1e9) if found else 0


def gpu_token(description):
    """The GPU model token the hardware check matches ('A10', 'A100', 'H100')."""
    found = re.match(r'\s*([A-Za-z0-9]+)', str(description or ''))
    return found.group(1) if found else ''


def candidate(entry):
    """One sealed instance candidate from a projected inventory entry, at its live price."""
    meta = entry['metadata']
    return dict(type=meta['type'], max_hourly_rate=meta['hourly_rate'], gpu_token=gpu_token(meta.get('gpu_type')),
                gpu_bytes=gpu_bytes(meta.get('gpu_type')), min_cpu=int(meta.get('cpu') or 0),
                min_ram_bytes=int(HOST_FRACTION * float(meta.get('ram_gib') or 0)) * 2**30,
                run_gpu_total_bytes=RUN_GPU_TOTAL_BYTES, run_gpu_free_bytes=RUN_GPU_FREE_BYTES,
                run_ram_available_bytes=RUN_RAM_AVAILABLE_BYTES, run_disk_free_bytes=RUN_DISK_FREE_BYTES)


def instance_candidates(inventory, reference_rate):
    """The ordered candidate list sealed into the manifest: the A10 first, then every other
    single-GPU x86_64 type with at least the run's VRAM at a live price no more than twice
    the A10's last recorded price, cheapest first."""
    reference = number(reference_rate, 'A10 reference price')
    a10 = [x for x in inventory if x['metadata']['type'] == PREFERRED_TYPE]
    refuse(len(a10) == 1 and x_ok(a10[0]), 'gpu_1x_a10 not offered')
    others = [x for x in inventory if x['metadata']['type'] != PREFERRED_TYPE and x_ok(x)
              and gpu_bytes(x['metadata'].get('gpu_type')) >= RUN_GPU_TOTAL_BYTES
              and x['metadata']['hourly_rate'] <= TYPE_RULE_FACTOR * reference]
    others.sort(key=lambda x: (x['metadata']['hourly_rate'], x['metadata']['type']))
    return [candidate(a10[0])] + [candidate(x) for x in others]


def x_ok(entry):
    meta = entry.get('metadata') or {}
    return (entry.get('architecture') == 'x86_64' and meta.get('gpu_count', 1) == 1
            and type(meta.get('hourly_rate')) in (int, float) and meta['hourly_rate'] > 0)


def offered(entry_by_type, cand, reference, fallback):
    entry = entry_by_type.get(cand['type'])
    if entry is None or not x_ok(entry):
        return None
    rate = entry['metadata']['hourly_rate']
    if rate > cand['max_hourly_rate'] or rate > TYPE_RULE_FACTOR * reference:
        return None
    regions = list(entry.get('regions') or [])
    if not fallback:
        return (PREFERRED_REGION, rate, entry) if cand['type'] == PREFERRED_TYPE and PREFERRED_REGION in regions else None
    if not regions:
        return None
    region = PREFERRED_REGION if PREFERRED_REGION in regions else sorted(regions)[0]
    return region, rate, entry


def select_instance(list_types, candidates, reference_rate, clock, poll_seconds=POLL_LIMIT_SECONDS,
                    interval=POLL_INTERVAL_SECONDS):
    """Prefer gpu_1x_a10 in us-east-1, polling the free inventory for up to `poll_seconds`;
    then the sealed candidates in order, in any region, each at no more than its sealed rate
    cap and twice the A10's reference price. Returns (candidate, region, live rate, polls)."""
    reference = number(reference_rate, 'A10 reference price')
    refuse(isinstance(candidates, list) and candidates and candidates[0]['type'] == PREFERRED_TYPE,
           'Sealed instance candidates must start with gpu_1x_a10')
    start = clock.time()
    polls = 0
    while True:
        polls += 1
        by_type = {x['metadata']['type']: x for x in list_types()}
        found = offered(by_type, candidates[0], reference, fallback=False)
        if found:
            return candidates[0], found[0], found[1], polls
        if clock.time() - start >= poll_seconds:
            for cand in candidates:
                found = offered(by_type, cand, reference, fallback=True)
                if found:
                    return cand, found[0], found[1], polls
            raise GuardRefusal('No admissible instance type offered after %d polls; poll again later' % polls)
        clock.sleep(interval)


# ---- the general cloud path is not a loop launch path (R4) ----------------------------

LEDGER_NAMES = ('budget_ledger.jsonl', 'R_ledger.jsonl')


def refuse_general_path(names=(), argv=()):
    """The general cloud tools refuse a loop instance name and any loop ledger argument, so a
    loop launch can only go through the guarded ordinary final controller."""
    for name in names:
        refuse(not str(name or '').startswith(PREFIX),
               'The general cloud path refuses loop instance names; launch through the guarded controller')
    for token in argv:
        text = str(token)
        refuse(not text.startswith('--ledger') and not text.startswith('--r-inputs')
               and not any(text.replace('\\', '/').endswith(n) for n in LEDGER_NAMES) and 'R_INPUTS' not in text,
               'The general cloud path refuses loop ledger arguments; launch through the guarded controller')
