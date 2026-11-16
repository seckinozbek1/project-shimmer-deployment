"""Two cost figures for a planned Lambda step (#298, D-676 item 5, D-628 A, the 16 November audit row 6).

Given a planned step (its minutes forecast by component, the instance type, how many launches, the storage
it holds) and the saving measures declared for it, this prints the cost WITHOUT the measures and the cost
WITH them, and names every measure with what it changes and the evidence it rests on. It launches nothing
and calls no provider.

Prices are never typed in. The hourly price is read from the provider inventory file the launch flow writes
(`provider_inventory.json`: `tools/console_cloud_inventory.py`, the sealer's `--inputs-from` folder), from
`instance_types[].metadata.hourly_rate` of the named type; the storage price from the file system storage
record the progress page reads (`docs/loop/private/filesystem_storage.json`, `usd_per_gb_month`, read from
the provider's billing page). A step file that carries a price, rate, cost or USD key is refused. Both
figures are the budget guard's own IV.3 forecast (`loop_budget_guard.forecast_usd`: minutes / 60 x price x
1.3) plus the storage share, so they are the figures the guard will check at launch.

The step file (JSON):
  {"step": "<name>", "instance_type": "gpu_1x_a10", "launches": 1,
   "minutes": {"boot": 6, "upload": 37, "install": 6, "seed": 0, "workload": 20, "return": 3},
   "storage": {"gib": 0, "hours": 0},
   "measures": [{"name": "asset_copy", "keeps_minutes": 2, "source": "D-057: every launch read MATCH"}, ...]}
Every component but `workload` is paid once per launch; `workload` is the step's whole work. Measures:
  asset_copy        the assets come from the persistent file system: `upload` becomes `keeps_minutes`
  image_layers      the ready-to-run image (IMAGE-A): `install` becomes `keeps_minutes`
  warm_file_system  the inputs are already on the file system: `seed` becomes `keeps_minutes`; holding them
                    there may add storage (`adds_storage`: {gib, hours})
  batching          the work runs in `launches` launches instead of the step's own number
  smaller_set       the workload is cut to `fraction` of itself (this changes what is measured: say so)
Each measure names its `source` (a decision, a run record, a measurement); a measure listed twice, an
unknown one or one without a source is refused.

    py -3.12 -X utf8 tools/loop/step_cost.py --step docs/loop/stages/lambda_working_store/move_all.json
    py -3.12 -X utf8 tools/loop/step_cost.py --step S --inventory <provider_inventory.json> [--json out.json]

With no --inventory the newest one by its own `observed_at` is taken from the main checkout's sealing inputs
(external/s05/*/inputs, external/s05/*/*, output/cloud/*/inputs) and this repository's docs/fix bundles; the
path and its age are printed. Proofs: tools/loop/step_cost_checks.py (checks 500 and 501).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import loop_budget_guard as guard  # noqa: E402  (the IV.3 forecast and the spend limits are the guard's)
import shared_paths  # noqa: E402

PER_LAUNCH = ('boot', 'upload', 'install', 'seed', 'return')
COMPONENTS = PER_LAUNCH + ('workload',)
MEASURES = {
    'asset_copy': ('upload', 'the assets come from the persistent file system, not an upload from the laptop'),
    'image_layers': ('install', 'the ready-to-run image layers (IMAGE-A): no environment build or wheel install'),
    'warm_file_system': ('seed', 'the inputs are already on the persistent file system: nothing is seeded'),
    'batching': (None, 'the work runs in fewer launches, so the per-launch minutes are paid fewer times'),
    'smaller_set': ('workload', 'the workload is cut to a fraction of itself; this changes what is measured'),
}
HOURS_PER_MONTH = 730.0          # the provider's billing month: 365 x 24 / 12 hours
STALE_DAYS = 2.0
PRICE_KEY = re.compile(r'(price|rate|usd|cost|dollar)', re.I)
STORAGE_RECORD = 'filesystem_storage.json'
INVENTORY_NAME = 'provider_inventory.json'


class StepCostError(Exception):
    """A step file, inventory or storage record this tool refuses."""


def refuse(condition, message):
    if not condition:
        raise StepCostError(message)


def minutes_value(value, name):
    refuse(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
           and value >= 0, 'Invalid minutes for %s' % name)
    return float(value)


def price_keys(value, where='step'):
    """Every key in the step file that names a price, a rate, a cost or USD: prices are never typed in."""
    found = []
    if isinstance(value, dict):
        for key, inner in value.items():
            if PRICE_KEY.search(str(key)):
                found.append('%s.%s' % (where, key))
            found.extend(price_keys(inner, '%s.%s' % (where, key)))
    elif isinstance(value, list):
        for i, inner in enumerate(value):
            found.extend(price_keys(inner, '%s[%d]' % (where, i)))
    return found


def storage_value(value, name):
    if value is None:
        return 0.0, 0.0
    refuse(isinstance(value, dict) and set(value) <= {'gib', 'hours'}, 'Invalid storage for %s: {gib, hours}' % name)
    return minutes_value(value.get('gib', 0), name + ' gib'), minutes_value(value.get('hours', 0), name + ' hours')


def read_step(step):
    """The step, checked: components, launches, storage and measures (each once, known, with a source)."""
    refuse(isinstance(step, dict), 'The step file is not an object')
    typed = price_keys(step)
    refuse(not typed, 'A price is never typed in; it is read from the provider inventory and the storage record '
                      '(remove: %s)' % ', '.join(typed))
    refuse(isinstance(step.get('step'), str) and step['step'].strip(), 'The step names itself (step)')
    refuse(isinstance(step.get('instance_type'), str) and step['instance_type'], 'The step names its instance_type')
    launches = step.get('launches', 1)
    refuse(isinstance(launches, int) and not isinstance(launches, bool) and launches >= 1, 'Invalid launches')
    minutes = step.get('minutes')
    refuse(isinstance(minutes, dict) and set(minutes) <= set(COMPONENTS),
           'minutes holds only %s' % ', '.join(COMPONENTS))
    parts = {c: minutes_value(minutes.get(c, 0), c) for c in COMPONENTS}
    gib, hours = storage_value(step.get('storage'), 'storage')
    measures, seen = [], set()
    for entry in step.get('measures') or []:
        refuse(isinstance(entry, dict), 'A measure is an object')
        name = entry.get('name')
        refuse(name in MEASURES, 'Unknown saving measure %r (known: %s)' % (name, ', '.join(MEASURES)))
        refuse(name not in seen, 'Saving measure %s is listed twice' % name)
        seen.add(name)
        refuse(isinstance(entry.get('source'), str) and entry['source'].strip(),
               'Saving measure %s names its source (a decision, a run record or a measurement)' % name)
        component = MEASURES[name][0]
        measure = dict(name=name, source=entry['source'].strip(), does=MEASURES[name][1])
        if name == 'batching':
            into = entry.get('launches')
            refuse(isinstance(into, int) and not isinstance(into, bool) and 1 <= into <= launches,
                   'batching names the launches the work runs in, at least 1 and at most the step\'s %d' % launches)
            measure['launches'] = into
        elif name == 'smaller_set':
            fraction = entry.get('fraction')
            refuse(isinstance(fraction, (int, float)) and not isinstance(fraction, bool) and 0 < fraction <= 1,
                   'smaller_set names the fraction of the workload kept, above 0 and at most 1')
            measure['fraction'] = float(fraction)
        else:
            keeps = minutes_value(entry.get('keeps_minutes', 0), name + ' keeps_minutes')
            refuse(keeps <= parts[component], '%s keeps %.1f minutes of %s, more than the %.1f planned'
                   % (name, keeps, component, parts[component]))
            measure['keeps_minutes'] = keeps
            if name == 'warm_file_system':
                measure['adds_gib'], measure['adds_hours'] = storage_value(entry.get('adds_storage'), name)
            else:
                refuse('adds_storage' not in entry, 'Only warm_file_system adds storage')
        if component:
            measure['component'] = component
        measures.append(measure)
    return dict(step=step['step'].strip(), instance_type=step['instance_type'], launches=launches,
                minutes=parts, storage_gib=gib, storage_hours=hours, measures=measures)


def read_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise StepCostError('The %s cannot be read: %s' % (what, Path(path).name)) from None


def observed(inventory):
    text = inventory.get('observed_at') if isinstance(inventory, dict) else None
    try:
        when = datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        raise StepCostError('The provider inventory carries no readable observed_at') from None
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def hourly_rate(inventory, instance_type):
    """The named type's hourly price from the inventory's instance types, and its capacity regions."""
    refuse(isinstance(inventory, dict) and isinstance(inventory.get('instance_types'), list),
           'The provider inventory has no instance_types list')
    for row in inventory['instance_types']:
        meta = row.get('metadata') if isinstance(row, dict) else None
        if isinstance(meta, dict) and meta.get('type') == instance_type:
            rate = meta.get('hourly_rate')
            refuse(isinstance(rate, (int, float)) and not isinstance(rate, bool) and math.isfinite(rate) and rate > 0,
                   'The provider inventory gives no hourly price for %s' % instance_type)
            return float(rate), list(row.get('regions') or [])
    raise StepCostError('The provider inventory does not list %s' % instance_type)


def storage_price(record):
    refuse(isinstance(record, dict), 'The storage record is not an object')
    price = record.get('usd_per_gb_month')
    refuse(isinstance(price, (int, float)) and not isinstance(price, bool) and math.isfinite(price) and price > 0,
           'The storage record gives no usd_per_gb_month')
    return float(price)


def figure(per_launch, launches, workload, gib_hours, rate, price):
    minutes = launches * sum(per_launch.values()) + workload
    compute = guard.forecast_usd(minutes, rate) if minutes else 0.0
    storage = gib_hours * price / HOURS_PER_MONTH
    return dict(minutes=round(minutes, 2), launches=launches, compute_usd=round(compute, 4),
                storage_usd=round(storage, 4), usd=round(compute + storage, 4))


def estimate(step, inventory, record=None, limits=None, now=None):
    """The two figures for a step already read by `read_step`: without and with its saving measures."""
    rate, regions = hourly_rate(inventory, step['instance_type'])
    when = observed(inventory)
    needs_storage = step['storage_gib'] * step['storage_hours'] > 0 or any(
        m.get('adds_gib', 0) * m.get('adds_hours', 0) > 0 for m in step['measures'])
    price = storage_price(record) if needs_storage else (storage_price(record) if record else 0.0)
    base = dict(step['minutes'])
    per = {c: base[c] for c in PER_LAUNCH}
    gib_hours = step['storage_gib'] * step['storage_hours']
    without = figure(per, step['launches'], base['workload'], gib_hours, rate, price)
    saved_per, launches, workload = dict(per), step['launches'], base['workload']
    changes = []
    for m in step['measures']:
        if m['name'] == 'batching':
            changes.append('%d launches become %d' % (launches, m['launches']))
            launches = m['launches']
        elif m['name'] == 'smaller_set':
            changes.append('workload %.1f -> %.1f min' % (workload, workload * m['fraction']))
            workload = workload * m['fraction']
        else:
            c = m['component']
            changes.append('%s %.1f -> %.1f min a launch' % (c, saved_per[c], m['keeps_minutes']))
            saved_per[c] = m['keeps_minutes']
            if m['name'] == 'warm_file_system' and m['adds_gib'] * m['adds_hours'] > 0:
                # storage held for the warm file system adds GiB-hours to the step's own
                gib_hours += m['adds_gib'] * m['adds_hours']
                changes[-1] += ', storage +%.1f GiB for %.0f h' % (m['adds_gib'], m['adds_hours'])
        m['changes'] = changes[-1]
    with_ = figure(saved_per, launches, workload, gib_hours, rate, price)
    limits = limits or guard.read_spend_limits()
    pre = limits['step_preapproved_usd']
    now = now or datetime.now(timezone.utc)
    return dict(step=step['step'], instance_type=step['instance_type'], hourly_rate=rate, capacity_regions=regions,
                inventory_observed_at=when.isoformat(), inventory_age_days=round((now - when).total_seconds() / 86400, 2),
                storage_usd_per_gb_month=price, forecast_factor=guard.FORECAST_FACTOR,
                without=without, with_measures=with_, saved_usd=round(without['usd'] - with_['usd'], 4),
                measures=[dict(m) for m in step['measures']], step_preapproved_usd=pre,
                without_within_preapproval=without['usd'] <= pre + guard.LIMIT_TOLERANCE_USD,
                with_within_preapproval=with_['usd'] <= pre + guard.LIMIT_TOLERANCE_USD,
                limits_decision=limits['decision'])


def inventory_candidates(main=None):
    """Every provider inventory the launch flow wrote, in the main checkout and in this repository."""
    paths = []
    if main is not None:
        main = Path(main)
        for pattern in ('external/s05/*/inputs/' + INVENTORY_NAME, 'external/s05/*/*/' + INVENTORY_NAME,
                        'output/cloud/*/inputs/' + INVENTORY_NAME):
            paths.extend(main.glob(pattern))
    paths.extend(ROOT.glob('docs/fix/ordinary_final_cloud_run*/' + INVENTORY_NAME))
    return paths


def newest_inventory(paths):
    best = None
    for path in paths:
        try:
            when = observed(read_json(path, 'provider inventory'))
        except StepCostError:
            continue
        if best is None or when > best[0]:
            best = (when, path)
    refuse(best is not None, 'No provider inventory found; read one with tools/console_cloud_inventory.py --out <path>')
    return best[1]


def lines(result):
    w, s = result['without'], result['with_measures']
    out = ['Step %s on %s at %.2f USD an hour (provider inventory, observed %s, %.1f days old)'
           % (result['step'], result['instance_type'], result['hourly_rate'], result['inventory_observed_at'],
              result['inventory_age_days'])]
    if result['inventory_age_days'] > STALE_DAYS:
        out.append('  The inventory is older than %.0f days: read a fresh one (tools/console_cloud_inventory.py, '
                   'read only) before the launch is asked for' % STALE_DAYS)
    out.append('  Without the saving measures: %.1f min in %d launch(es), %.2f USD (compute %.2f, storage %.2f)'
               % (w['minutes'], w['launches'], w['usd'], w['compute_usd'], w['storage_usd']))
    out.append('  With the saving measures:    %.1f min in %d launch(es), %.2f USD (compute %.2f, storage %.2f)'
               % (s['minutes'], s['launches'], s['usd'], s['compute_usd'], s['storage_usd']))
    if result['measures']:
        out.append('  Measures: ' + '; '.join('%s (%s; %s)' % (m['name'], m['changes'], m['source'])
                                              for m in result['measures']))
    else:
        out.append('  Measures: none declared, so both figures are the same')
    out.append('  Saved: %.2f USD. Both are IV.3 forecasts (x%.1f) plus storage at %.2f USD per GiB a month. '
               'Per-step pre-approval %.2f USD (%s): without %s, with %s'
               % (result['saved_usd'], result['forecast_factor'], result['storage_usd_per_gb_month'],
                  result['step_preapproved_usd'], result['limits_decision'],
                  'within' if result['without_within_preapproval'] else 'ABOVE, ask Seckin',
                  'within' if result['with_within_preapproval'] else 'ABOVE, ask Seckin'))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--step', type=Path, required=True, help='the planned step (JSON, see the module text)')
    parser.add_argument('--inventory', type=Path, default=None, help='a provider_inventory.json the launch flow wrote')
    parser.add_argument('--storage-record', type=Path, default=None,
                        help='the storage record (default: the main checkout\'s docs/loop/private/%s)' % STORAGE_RECORD)
    parser.add_argument('--json', type=Path, default=None, help='also write the figures here')
    args = parser.parse_args(argv)
    try:
        step = read_step(read_json(args.step, 'step file'))
        main_root = None
        try:
            main_root = shared_paths.main_checkout()
        except shared_paths.MainCheckoutError:
            pass
        inventory_path = args.inventory or newest_inventory(inventory_candidates(main_root))
        record_path = args.storage_record or (main_root.joinpath(*shared_paths.PRIVATE, STORAGE_RECORD)
                                              if main_root else None)
        record = read_json(record_path, 'storage record') if record_path and Path(record_path).is_file() else None
        result = estimate(step, read_json(inventory_path, 'provider inventory'), record)
    except (StepCostError, guard.GuardRefusal) as exc:
        print('Step cost refused: %s' % exc, flush=True)
        return 2
    result['inventory'] = Path(inventory_path).name if args.inventory is None else str(args.inventory)
    print('\n'.join(lines(result)), flush=True)
    print('  Inventory read: %s' % inventory_path, flush=True)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
