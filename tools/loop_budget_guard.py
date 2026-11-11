"""Loop budget guard, instance-type rule and ledger writer for every loop launch path (IV.3).

Nothing here calls a provider. The controller reads the live price and the inventory
through the allowlisted adapter and hands them in; this module only decides.

The guard always reads the ledgers the reaper reads (the private ledger and R's ledger,
tools/loop/instance_reaper.py) beside any it is given, needs a `budget_open` line among
them, and refuses a launch whose own ledger is not one the reaper reads, so a wrong or new
path can never read as zero spend while the reaper kills the unrecorded instance. It
refuses a launch, in one line, when:
  * the inventory lists a loop instance no ledger read records as running: its cap could
    not be counted among the running caps (the reaper ends such an instance);
  * the per-run cap formula leaves less than the forecast:
        cap = min(1.5 x forecast, ceiling - spend - caps of running loop instances
                  - storage forecast),  ceiling = min(hard stop, budget - 1),
    where the budget and the hard stop are read from the ledgers' latest `budget_open` or
    `budget_change` line (`instance_reaper.budget_figures`: its `hard_stop_usd`, else its
    `budget_usd` less the one-dollar margin), never from a number in this file; with no
    hard stop on the line, or one above the budget less the margin, this is the IV.3
    formula `budget - spend - caps - storage - 1`;
  * the capped run time (cap / live price) does not cover the forecast time plus the
    run's stop reserve (the runner stops its workload that long before the ceiling).
"Spend + forecast + storage passes the budget" needs no refusal of its own: the cap rule
already keeps it at or below the ceiling, which is at most the budget less one dollar and
at most the hard stop, the spend at which the reaper ends every loop instance. Spend is counted once per launch by instance id or name across
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
# Constants of the loop's budget rule (IV.3), not run settings: the one-dollar margin
# (the reaper's own), the cap and forecast factors and the type-rule factor. The total
# budget is not one of them: it is read from the ledger (D-S9).
RESERVE_USD = instance_reaper.MARGIN_USD
# D-S95: no maximum number of loop instances (D-S17's count limit is removed). Each running loop
# instance is still counted once, its cap among the running caps, and the total budget's hard
# stop is the only limit.
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


def per_run_cap(forecast, spend, running_caps, storage_forecast, ceiling, overrun=0.0):
    """IV.3: min(1.5 x forecast, ceiling - spend - running caps - storage forecast - overrun).

    `ceiling` is `cap_ceiling(budget, hard stop)`, never more than the budget less the
    one-dollar margin, so this is at most
    min(1.5 x forecast, budget - spend - running caps - storage forecast - overrun - 1).
    `overrun` is `overrun_reserve` (D-382 item 5): with no count limit, it keeps the time each
    instance can run past its due moment, before the reaper ends it, inside the ceiling."""
    return min(CAP_FACTOR * forecast, ceiling - spend - running_caps - storage_forecast - overrun)


def overrun_reserve(running, hourly_rate):
    """D-382 item 5, D-401 item 2: per running loop instance and for this one, its price times the
    time it can run past its due moment before the reaper ends it: one reaper period and a margin.
    A running record with no price is counted at this launch's price. A limit: while Seckin is
    logged off the reaper's period is unbounded (instance_reaper.REAPER_PERIOD_SECONDS)."""
    seconds = instance_reaper.REAPER_PERIOD_SECONDS + instance_reaper.REAPER_MARGIN_SECONDS
    rates = [float(rec.get('price_usd_per_hour') or hourly_rate) for rec in running] + [float(hourly_rate)]
    return sum(rate * seconds / 3600 for rate in rates)


def cap_ceiling(budget, hard_stop):
    """The cap's ceiling: min(hard stop, budget - 1). The hard stop is the ledger's
    (`instance_reaper.budget_figures`, which admits any stop up to the budget); a line
    naming a stop above the budget less IV.3's one-dollar margin never removes that
    margin from the cap."""
    return min(hard_stop, budget - RESERVE_USD)


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
    """The A10's last recorded price (the type rule's reference): the latest, by its own
    `time_utc` (read order breaks a tie), of the budget lines (`budget_open` or
    `budget_change`) that carry `a10_reference_price_usd_per_hour`. A line with no readable
    time is skipped, as `instance_reaper.budget_figures` skips it."""
    timed = []
    for path in ledgers:
        for row in instance_reaper.read_ledger(path):
            if row.get('event') not in instance_reaper.BUDGET_EVENTS or row.get('a10_reference_price_usd_per_hour') is None:
                continue
            try:
                moment = instance_reaper.parse_time(row['time_utc'])
            except (KeyError, TypeError, ValueError):
                continue
            timed.append((moment, len(timed), row['a10_reference_price_usd_per_hour']))
    refuse(bool(timed), 'No recorded A10 reference price in the ledgers given')
    return number(max(timed, key=lambda item: (item[0], item[1]))[2], 'A10 reference price')


def loop_inventory(inventory):
    """The names of the loop instances in a provider inventory. Any instance that is not a
    loop instance refuses the launch, as an inventory that was not empty always did."""
    names = [str(item.get('name') or '') for item in inventory]
    refuse(all(n.startswith(PREFIX) for n in names), 'Provider inventory holds an instance that is not a loop instance')
    return sorted(names)


def refuse_foreign_inventory(inventory):
    """Before any guard decision: only loop instances listed (any number of them, D-S95)."""
    return loop_inventory(inventory)


def read_r_inputs(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    refuse(isinstance(value, dict) and all(k in value for k in R_INPUT_FIELDS), 'R_INPUTS.json lacks a budget field')
    return {k: value[k] for k in R_INPUT_FIELDS}


import cloud_reference_spend as cloud_spend  # noqa: E402  (tools/loop, put on the path above)


def spend_store_path():
    """D-401 items 4 and 11: the cloud reference's one spend store, by its own path rule
    (`cloud_reference_spend.store_path`: docs/loop/private/ of the main checkout, from git's common
    directory)."""
    try:
        return cloud_spend.store_path(ROOT)
    except cloud_spend.SpendStoreError as exc:
        refuse(False, str(exc))


def cloud_spend_refusal(store):
    """D-401 item 11: refuse a launch while `lead_may_spend` gives a reason (a handed-back role C
    spend file not yet appended, an absent or unreadable store). Under D-S121 the API spend has its
    own ceiling in the store (`cloud_reference_spend.api_room`) and never counts toward Lambda's."""
    try:
        cloud_spend.read(store)     # an absent or unreadable store refuses, never read as no spend
    except cloud_spend.SpendStoreError as exc:
        refuse(False, str(exc))
    reason = cloud_spend.lead_may_spend(store)
    refuse(reason is None, reason or '')
    return True


# F1 (D-421): the standing orders a launch is held to before it is requested: 1 (the filesystem
# copy), 2 (the API key and its approvals) and 3 (the budget and its warnings), by the
# standing-orders check's own checkers, read on the MAIN checkout.
LAUNCH_ORDER_NUMBERS = (1, 2, 3)


def standing_orders_root():
    """The main checkout, whose external/ and private records the standing orders read."""
    return spend_store_path().parents[3]


def standing_orders_failures(root):
    """[(order, state, evidence)] for each of standing orders 1 to 3 that stops a launch on `root`
    (broken, or unable to check), by the standing-orders check's one call for it (`launch_refusals`;
    a checker's state is a word such as 'broken', never read for truthiness)."""
    import standing_orders_check as orders
    return list(orders.launch_refusals(orders.Context(root), LAUNCH_ORDER_NUMBERS))


def standing_orders_refusal(root=None):
    """F1: refuse a launch while standing order 1, 2 or 3 does not hold (one line naming each)."""
    failures = standing_orders_failures(standing_orders_root() if root is None else root)
    refuse(not failures, 'A standing order does not hold before this launch: ' +
           '; '.join('order %s %s: %s' % (number, state, evidence) for number, state, evidence in failures))
    return True


COMPARISONS_NAME = 'comparisons.jsonl'


def comparison_registry():
    """D-401 item 1 (d), D-436 item 2: the one record of each comparison's machine type, in the MAIN
    checkout's private folder, found through git's common directory as the spend store is."""
    return spend_store_path().parent / COMPARISONS_NAME


def comparison_recorded(name, registry=None):
    """The machine type recorded for comparison `name`, or None (the sealer's early, read-only check)."""
    path = Path(registry or comparison_registry())
    if not path.is_file():
        return None
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    return next((r['type'] for r in rows if r.get('comparison') == name), None)


def claim_comparison(name, machine, now_epoch, registry=None):
    """D-S95 item 5, D-401 item 1 (d): at launch, after the guard's decision and under the ledger
    lock, the first launch of a comparison records its machine type; every later one must be on
    that type, else it is refused before any instance."""
    refuse(isinstance(name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', name) is not None,
           'A comparison name is lower case letters, digits and hyphens')
    path = Path(registry or comparison_registry())
    known = comparison_recorded(name, path)
    if known is not None:
        refuse(known == machine, 'Comparison %s runs on %s; this launch would run on %s' % (name, known, machine))
        return dict(name=name, type=known, first=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(dict(comparison=name, type=machine, time_utc=utc(now_epoch)), sort_keys=True) + '\n')
    return dict(name=name, type=machine, first=True)


def check(*, ledgers, forecast_minutes, hourly_rate, storage_forecast_usd, now_epoch, reserve_minutes,
          provider_names=(), instance_type=None, r_inputs=None, reaped=None, spend_store=None):
    """Decide one loop launch. Returns the cap and the figures it rests on, or refuses.

    `reaped` replaces the reaper's ledgers only for a mocked launch (the rehearsal and the
    fixtures); a real launch reads the reaper's own. The cloud reference's API spend counts with
    Lambda's (D-401): a real launch reads the shared spend store (`spend_store_path`); a mocked one
    reads only the store it is given."""
    ledgers = ledger_set([Path(p) for p in ledgers], reaped)
    forecast = forecast_usd(forecast_minutes, hourly_rate)
    storage = number(storage_forecast_usd, 'storage forecast', positive=False)
    reserve = number(reserve_minutes, 'reserve minutes', positive=False)
    spend, running, running_caps, rows = ledger_state(ledgers, now_epoch)
    if reaped is None:
        # F1: a real launch is held to standing orders 1 to 3 first; a mocked one reads no real record.
        standing_orders_refusal()
    store = spend_store if spend_store is not None else (spend_store_path() if reaped is None else None)
    if store is not None:
        cloud_spend_refusal(store)   # D-S121: the API's ceiling is its own; nothing is added to Lambda's
    refuse(any(r.get('event') == 'budget_open' for r in rows), 'No budget_open line in the loop ledgers')
    budget, hard_stop = instance_reaper.budget_figures(rows)
    refuse(budget is not None and hard_stop is not None, 'No readable budget line in the loop ledgers')
    warning = instance_reaper.warning_figure(rows)
    if r_inputs is not None:
        r = read_r_inputs(r_inputs)
        spend = max(spend, number(r['spend_usd'], 'R spend', positive=False))
        storage = max(storage, number(r['storage_forecast_usd'], 'R storage forecast', positive=False))
        refuse(instance_type is None or r['instance_type'] == instance_type, 'Instance type differs from R_INPUTS.json')
        refuse(forecast <= number(r['allocation_left_usd'], 'R allocation', positive=False),
               'Forecast %.2f dollars exceeds the allocation left %.2f dollars' % (forecast, r['allocation_left_usd']))
    recorded = {rec.get('instance_name') for rec in running}
    listed = {str(n) for n in provider_names if str(n).startswith(PREFIX)}
    unrecorded = sorted(listed - recorded)
    refuse(not unrecorded, 'A loop instance no ledger records is running (%s); its cap cannot be counted'
           % ', '.join(unrecorded))
    ceiling = cap_ceiling(budget, hard_stop)
    overrun = overrun_reserve(running, hourly_rate)
    cap = per_run_cap(forecast, spend, running_caps, storage, ceiling, overrun)
    if r_inputs is not None:
        cap = min(cap, number(r['cap_usd'], 'R cap'))
    refuse(cap >= forecast, 'Per-run cap %.2f dollars leaves less than the forecast %.2f dollars' % (cap, forecast))
    capped_minutes = cap / hourly_rate * 60
    refuse(capped_minutes >= forecast_minutes + reserve,
           'Capped run time %.1f min does not cover the forecast %.1f min and the %.1f min stop reserve'
           % (capped_minutes, forecast_minutes, reserve))
    return dict(forecast_usd=round(forecast, 4), cap_usd=round(cap, 4), capped_minutes=round(capped_minutes, 2),
                spend_usd=round(spend, 4), running_caps_usd=round(running_caps, 4), storage_forecast_usd=storage,
                overrun_reserve_usd=round(overrun, 4), warning_usd=warning,
                warning_reached=warning is not None and spend + running_caps + forecast >= warning,
                budget_usd=budget, hard_stop_usd=hard_stop, cap_ceiling_usd=ceiling)


def require_purpose(purpose):
    """A launch purpose is a short identifier (lower case, digits, hyphens, at most 40),
    never prose. The launch plan is refused on it before any provider call; the ledger
    line checks it again."""
    refuse(isinstance(purpose, str) and PURPOSE.fullmatch(purpose) is not None,
           'Purpose must be a short identifier (lower case, digits, hyphens)')
    return purpose


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
        require_purpose(fields['purpose'])
    if event == 'launch_intent':
        refuse(fields.get('deadline_utc') and fields.get('launch_requested_utc'), 'Intent needs a deadline and a request time')
    return dict(event=event, **fields)


def append(path, line):
    refuse('event' in line and not undeclared(line), 'Ledger line field outside IV.3')
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(json.dumps(line, sort_keys=True) + '\n')


# ---- one launch decision at a time (A12) -------------------------------------------------

def pid_alive(pid):
    """True if a process with this id runs, False if none does, None when it cannot be told.
    Observation only: on Windows the process is opened for a query and never signalled
    (os.kill there would end it)."""
    if type(pid) is not int or pid <= 0:
        return None
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            error = ctypes.get_last_error()
            return True if error == 5 else False if error == 87 else None  # access denied / no such process
        try:
            code = ctypes.c_ulong()
            if not kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)):
                return None
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def lock_holder(lock, now_epoch=None):
    """One clause naming a held lock's age, its holder's pid and whether that pid runs, read
    from what the lock holds; never the lock's removal."""
    try:
        held = json.loads(Path(lock).read_text(encoding='utf-8'))
        pid, created = held['pid'], float(held['created_epoch'])
    except (OSError, ValueError, TypeError, KeyError):
        return 'holder unreadable'
    age = max(0.0, (time.time() if now_epoch is None else now_epoch) - created)
    state = {True: 'running', False: 'not running', None: 'state unknown'}[pid_alive(pid)]
    return 'held %.0f s, since %s, by pid %s (%s)' % (age, utc(created), pid, state)


def acquire_lock(ledger):
    """An exclusive lock beside the ledger, held from the guard's decision through the intent
    line, so two controllers can never both pass the guard for one free slot. The lock holds
    its pid and creation time. A lock left by a crash is reported, in one line, with its
    age, its pid and whether that pid still runs, so the operator can act; it is never
    broken here.

    One lock per launch ledger, not one across ledgers: the lead and role R never launch at
    the same time (by procedure), and the controller reads the provider inventory again
    under this lock just before the guard, so a launch through the other ledger is seen
    there as a running loop instance."""
    lock = Path(str(ledger) + '.lock')
    try:
        with open(lock, 'x', encoding='utf-8') as handle:
            now = time.time()
            handle.write(json.dumps(dict(pid=os.getpid(), created_epoch=now, time_utc=utc(now))) + '\n')
    except FileExistsError:
        raise GuardRefusal('Another launch holds the ledger lock (' + lock.name + ', ' + lock_holder(lock)
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
                gpu_count=int(meta.get('gpu_count') or 1),
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


# D-S78 item 2: a step a faster type shortens may name its types, an A100, an H100 or more than
# one GPU, in its own order. The A10-first order, the 30-minute poll and the twice-the-A10-price
# limit do not apply to them; the cap rule and the total budget still do (check), and the
# x86_64 architecture stays, since the sealed wheels are built for it.
TYPE_RULES = ('a10_first', 'declared')


def declared_candidates(inventory, types, gpus=1):
    """The sealed candidate list of a declared order: each type in it offered now, x86_64, at a
    live price, with at least the run's VRAM on its first GPU and exactly the GPUs the run needs
    (`gpus_needed_match`, D-382 item 4); its live price is its rate cap."""
    refuse(isinstance(types, list) and types and len(set(types)) == len(types)
           and all(isinstance(t, str) and t for t in types), 'Declared instance types must be a list without repeats')
    by_type = {x['metadata']['type']: x for x in inventory}
    out = []
    for name in types:
        entry = by_type.get(name)
        refuse(entry is not None and x_any(entry), 'Declared instance type not offered: %s' % name)
        refuse(gpu_bytes(entry['metadata'].get('gpu_type')) >= RUN_GPU_TOTAL_BYTES,
               'Declared instance type has less GPU memory than the run needs: %s' % name)
        refuse(gpus_needed_match(entry, gpus), 'Declared instance type has another GPU count than the run needs: %s' % name)
        out.append(candidate(entry))
    return out


GPU_SPEED_ORDER = Path(__file__).resolve().parent / 'cloud_run' / 'gpu_speed_order.json'


def speed_order(spec):
    """D-S95: the declared order of GPU models (`order`, the provider's published generations),
    fastest first. It decides only which offered types are candidates and their order before any
    measurement; a measured type is ranked by `measured_tiers`."""
    order = list(spec['order'])
    refuse(order and len(set(order)) == len(order) and all(isinstance(t, str) and t for t in order),
           'The GPU speed order is a list without repeats')
    return order


def gpus_needed_match(entry, gpus):
    """Never more than the run needs (D-S95): a type with exactly the run's GPU count."""
    return int(entry['metadata'].get('gpu_count') or 1) == gpus


def fastest_candidates(inventory, order, gpus=1):
    """D-S79, D-S95: the default sealed order, fastest first. Every x86_64 type offered whose GPU
    model is in `order` (from `speed_order`) and holds the run's VRAM, with exactly the GPUs the
    run needs (`gpus`, never more), by that order, then price; the A10 comes first only where
    nothing faster is offered. No price factor applies: the cap rule and the total budget do."""
    refuse(isinstance(order, list) and order and len(set(order)) == len(order), 'The GPU speed order is a list without repeats')
    refuse(type(gpus) is int and gpus >= 1, 'The GPUs a run needs is a whole number of at least one')
    rank = {token: i for i, token in enumerate(order)}
    eligible = [x for x in inventory if x_any(x) and gpu_token(x['metadata'].get('gpu_type')) in rank
                and gpus_needed_match(x, gpus) and gpu_bytes(x['metadata'].get('gpu_type')) >= RUN_GPU_TOTAL_BYTES]
    refuse(eligible, 'No offered instance type is in the GPU speed order with the GPUs the run needs')
    eligible.sort(key=lambda x: (rank[gpu_token(x['metadata'].get('gpu_type'))], x['metadata']['hourly_rate'],
                                 x['metadata']['type']))
    return [candidate(x) for x in eligible]


A10_FACTOR = 1.0  # the reference machine's own time factor (D-382 item 1)


def measured_tiers(candidates, spec, reference_run=False):
    """D-S95, D-S96 item 2, D-382 item 1: a run leaves the A10 only for a machine type whose
    reference-set pair is measured: `spec['measured']`, keyed by machine type, each entry's time
    factor against the A10 (its provenance is checked at sealing, factor_record.check_measured).
    The kept types are ranked by that factor, the A10 counting 1.0, so a type measured slower than
    the A10 ranks below it; a tie keeps the given order. The reference-set run itself, the one that
    makes a pair, may take any offered type, in the given order. Refuses when nothing is left:
    until a pair is measured, every launch stays on the A10. Only single-GPU types are rentable
    until the runner's hardware projection changes (D-382 item 3): the sealer refuses --gpus
    above 1, so `gpus` here is always 1 today."""
    if reference_run:
        return list(candidates)
    measured = spec.get('measured') or {}
    factor = lambda c: A10_FACTOR if c['type'] == PREFERRED_TYPE else measured[c['type']]['time_factor']
    kept = [c for c in candidates if c['type'] == PREFERRED_TYPE or c['type'] in measured]
    refuse(kept, 'No offered machine type has its reference-set pair: run the D-S82 reference set on the new type '
                 'beside the A10 first')
    return [c for _, c in sorted(enumerate(kept), key=lambda item: (-factor(item[1]), item[0]))]


def x_any(entry):
    meta = entry.get('metadata') or {}
    return (entry.get('architecture') == 'x86_64' and int(meta.get('gpu_count') or 1) >= 1
            and type(meta.get('hourly_rate')) in (int, float) and meta['hourly_rate'] > 0)


def offered_declared(entry_by_type, cand):
    entry = entry_by_type.get(cand['type'])
    if entry is None or not x_any(entry) or entry['metadata']['hourly_rate'] > cand['max_hourly_rate']:
        return None
    regions = list(entry.get('regions') or [])
    if not regions:
        return None
    return PREFERRED_REGION if PREFERRED_REGION in regions else sorted(regions)[0], entry['metadata']['hourly_rate'], entry


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
                    interval=POLL_INTERVAL_SECONDS, type_rule='a10_first'):
    """Prefer gpu_1x_a10 in us-east-1, polling the free inventory for up to `poll_seconds`;
    then the sealed candidates in order, in any region, each at no more than its sealed rate
    cap and twice the A10's reference price. Returns (candidate, region, live rate, polls).
    Under a declared order (D-S78 item 2) one read of the inventory: the first sealed type
    offered at no more than its sealed rate, us-east-1 first, with no poll and no A10 limit."""
    refuse(type_rule in TYPE_RULES, 'Unknown instance type rule')
    if type_rule == 'declared':
        refuse(isinstance(candidates, list) and candidates, 'No sealed instance candidates')
        by_type = {x['metadata']['type']: x for x in list_types()}
        for cand in candidates:
            found = offered_declared(by_type, cand)
            if found:
                return cand, found[0], found[1], 1
        raise GuardRefusal('No declared instance type offered at its sealed rate; poll again later')
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
