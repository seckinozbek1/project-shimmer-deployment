"""Proofs for tools/loop/step_cost.py (#298, D-676 item 5, D-628 A), on fixtures only: temporary step files,
inventories and storage records; no network, no provider, no ledger. Each proof is run as built (passes),
neutralised (must fail), restored (passes again).

    py -3.12 -X utf8 tools/loop/step_cost_checks.py 500
    py -3.12 -X utf8 tools/loop/step_cost_checks.py 501
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import loop_budget_guard as guard  # noqa: E402
import step_cost as sc  # noqa: E402

LIMITS = dict(step_preapproved_usd=5.0, remaining_limit_usd=140.0, remaining_baseline_usd=197.0,
              remaining_ceiling_usd=337.0, decision='D-708')
NOW = sc.datetime(2026, 11, 16, 20, 0, tzinfo=sc.timezone.utc)


def inventory(a10=1.29, observed='2026-11-16T18:10:15+00:00', extra=True):
    rows = [dict(metadata=dict(type='gpu_1x_a10', hourly_rate=a10), regions=['us-east-1'])]
    if extra:
        rows.append(dict(metadata=dict(type='gpu_1x_h100_pcie', hourly_rate=3.79), regions=[]))
        rows.append(dict(metadata=dict(type='gpu_1x_norate'), regions=[]))
    return dict(read_only=True, observed_at=observed, instances=[], images=[], instance_types=rows)


def step(**over):
    value = dict(step='fixture', instance_type='gpu_1x_a10', launches=3,
                 minutes=dict(boot=6, upload=37, install=6, seed=4, workload=60, **{'return': 3}),
                 storage=dict(gib=0, hours=0),
                 measures=[dict(name='asset_copy', keeps_minutes=2, source='D-057: every launch read MATCH'),
                           dict(name='image_layers', keeps_minutes=1, source='IMAGE-A, M1 receipt'),
                           dict(name='warm_file_system', keeps_minutes=0, adds_storage=dict(gib=10, hours=730),
                                source='fs listing 16 Nov'),
                           dict(name='batching', launches=1, source='one launch for the three parts'),
                           dict(name='smaller_set', fraction=0.5, source='half the items, named in the plan')])
    value.update(over)
    return value


RECORD = dict(usd_per_gb_month=0.2)


def refused(call, needle):
    try:
        call()
    except sc.StepCostError as exc:
        assert needle in str(exc), str(exc)
        return
    raise AssertionError('not refused: ' + needle)


def run_estimate(value, inv=None, record=RECORD):
    return sc.estimate(sc.read_step(value), inv or inventory(), record, LIMITS, now=NOW)


# ---- check 500: prices are read from the inventory and the storage record, never typed in ----

def proof_price_is_read_from_the_inventory(base):
    """The hourly price is the inventory's for the named type: a different price in the inventory moves both
    figures by exactly its ratio, and the type's own row is used, not another's."""
    low = run_estimate(step(measures=[]), inventory(1.29))
    high = run_estimate(step(measures=[]), inventory(2.58))
    assert low['hourly_rate'] == 1.29 and high['hourly_rate'] == 2.58, (low['hourly_rate'], high['hourly_rate'])
    assert abs(high['without']['compute_usd'] - 2 * low['without']['compute_usd']) < 1e-3, (low, high)
    assert abs(low['without']['compute_usd'] - guard.forecast_usd(3 * 56 + 60, 1.29)) < 1e-3, low['without']


def proof_a_typed_price_is_refused(base):
    """A step file that carries a price, a rate, a cost or a USD figure, at any depth, is refused."""
    refused(lambda: sc.read_step(step(hourly_rate=0.5)), 'never typed in')
    nested = step()
    nested['measures'][0]['saves_usd'] = 1.0
    refused(lambda: sc.read_step(nested), 'measures[0].saves_usd')
    refused(lambda: sc.read_step(step(storage=dict(gib=1, hours=1, price_per_gib=0.2))), 'never typed in')


def proof_an_unlisted_or_unpriced_type_is_refused(base):
    """A type the inventory does not list, or lists with no price, is refused; nothing falls back to a price."""
    refused(lambda: run_estimate(step(instance_type='gpu_8x_unknown', measures=[])), 'does not list gpu_8x_unknown')
    refused(lambda: run_estimate(step(instance_type='gpu_1x_norate', measures=[])), 'no hourly price')
    refused(lambda: sc.hourly_rate(dict(observed_at='x'), 'gpu_1x_a10'), 'no instance_types')


def proof_storage_is_priced_from_the_record(base):
    """Storage is priced at the record's usd_per_gb_month: doubling it doubles the storage share; a step
    that holds storage with no readable price in the record is refused."""
    held = step(measures=[], storage=dict(gib=100, hours=730))
    one = run_estimate(held, record=dict(usd_per_gb_month=0.2))
    two = run_estimate(held, record=dict(usd_per_gb_month=0.4))
    assert abs(one['without']['storage_usd'] - 20.0) < 1e-6, one['without']
    assert abs(two['without']['storage_usd'] - 40.0) < 1e-6, two['without']
    refused(lambda: run_estimate(held, record=dict(note='no price')), 'usd_per_gb_month')
    refused(lambda: run_estimate(held, record=None), 'not an object')


def proof_the_newest_inventory_is_taken_by_its_own_time(base):
    """With no inventory named, the newest by its own observed_at is taken, whatever the file order."""
    paths = []
    for name, when in (('a', '2026-11-16T18:10:15+00:00'), ('b', '2026-09-19T10:00:00+00:00'),
                       ('c', '2026-11-16T11:31:27+00:00')):
        p = Path(base) / name / sc.INVENTORY_NAME
        p.parent.mkdir()
        p.write_text(json.dumps(inventory(observed=when)), encoding='utf-8')
        paths.append(p)
    for order in (paths, paths[::-1], [paths[1], paths[0], paths[2]]):
        assert sc.newest_inventory(order) == paths[0], sc.newest_inventory(order)
    refused(lambda: sc.newest_inventory([]), 'No provider inventory found')


# ---- check 501: two figures, without and with the declared measures, every measure named ----

def proof_both_figures_follow_the_declared_measures(base):
    """Without: 3 launches x 56 per-launch minutes + 60 workload = 228 min. With asset copy (37 -> 2), image
    layers (6 -> 1), warm file system (4 -> 0, +10 GiB for 730 h), batching (3 -> 1) and a half set: 12 + 30
    = 42 min, plus 2.00 USD of storage. Each figure is the guard's IV.3 forecast at the inventory price."""
    r = run_estimate(step())
    assert r['without']['minutes'] == 228.0 and r['without']['launches'] == 3, r['without']
    assert r['with_measures']['minutes'] == 42.0 and r['with_measures']['launches'] == 1, r['with_measures']
    assert abs(r['without']['usd'] - round(guard.forecast_usd(228, 1.29), 4)) < 1e-6, r['without']
    assert abs(r['with_measures']['compute_usd'] - round(guard.forecast_usd(42, 1.29), 4)) < 1e-6, r['with_measures']
    assert abs(r['with_measures']['storage_usd'] - 2.0) < 1e-6, r['with_measures']
    assert abs(r['saved_usd'] - (r['without']['usd'] - r['with_measures']['usd'])) < 1e-6, r
    assert [m['name'] for m in r['measures']] == list(sc.MEASURES), r['measures']
    # 6.37 USD without is above the 5 USD pre-approval, 3.17 with is within it: the measures decide the question
    assert r['without_within_preapproval'] is False and r['with_within_preapproval'] is True, r
    none = run_estimate(step(measures=[]))
    assert none['without'] == none['with_measures'], none


def proof_every_measure_is_named_with_its_source(base):
    """The printed figures name both totals, every measure with what it changes and its source, and say so
    when no measure is declared; a figure above the pre-approval says to ask Seckin."""
    text = '\n'.join(sc.lines(run_estimate(step())))
    for needle in ('Without the saving measures: 228.0 min in 3 launch(es)', 'With the saving measures:    42.0 min',
                   'asset_copy (upload 37.0 -> 2.0 min a launch; D-057', 'batching (3 launches become 1',
                   'smaller_set (workload 60.0 -> 30.0 min', 'warm_file_system (seed 4.0 -> 0.0 min a launch, storage '
                   '+10.0 GiB for 730 h', 'image_layers (install 6.0 -> 1.0'):
        assert needle in text, (needle, text)
    plain = '\n'.join(sc.lines(run_estimate(step(measures=[]))))
    assert 'none declared, so both figures are the same' in plain, plain
    big = step(measures=[], launches=1, minutes=dict(workload=600))
    assert 'ABOVE, ask Seckin' in '\n'.join(sc.lines(run_estimate(big))), big


def proof_a_bad_measure_is_refused(base):
    """An unknown measure, one listed twice, one with no source, one keeping more minutes than planned, a
    batching into more launches than the step has and a smaller set of nothing are each refused."""
    def with_measures(*entries):
        return step(measures=list(entries))
    refused(lambda: sc.read_step(with_measures(dict(name='prefix_magic', source='x'))), 'Unknown saving measure')
    twice = dict(name='asset_copy', keeps_minutes=1, source='x')
    refused(lambda: sc.read_step(with_measures(twice, dict(twice))), 'listed twice')
    refused(lambda: sc.read_step(with_measures(dict(name='asset_copy', keeps_minutes=1))), 'names its source')
    refused(lambda: sc.read_step(with_measures(dict(name='asset_copy', keeps_minutes=40, source='x'))),
            'more than the 37.0 planned')
    refused(lambda: sc.read_step(with_measures(dict(name='batching', launches=4, source='x'))), 'at most the step')
    refused(lambda: sc.read_step(with_measures(dict(name='smaller_set', fraction=0, source='x'))), 'above 0')


def proof_the_command_prints_both_figures(base):
    """The command line reads the files it is given, prints both figures and writes them as JSON; a typed price
    exits 2 with the refusal and writes nothing."""
    inv = Path(base) / 'inv.json'
    inv.write_text(json.dumps(inventory()), encoding='utf-8')
    rec = Path(base) / 'rec.json'
    rec.write_text(json.dumps(RECORD), encoding='utf-8')
    good = Path(base) / 'step.json'
    good.write_text(json.dumps(step()), encoding='utf-8')
    out = Path(base) / 'out.json'
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        code = sc.main(['--step', str(good), '--inventory', str(inv), '--storage-record', str(rec), '--json', str(out)])
    assert code == 0 and 'Without the saving measures: 228.0 min' in said.getvalue(), said.getvalue()
    assert json.loads(out.read_text(encoding='utf-8'))['with_measures']['minutes'] == 42.0
    bad = Path(base) / 'bad.json'
    bad.write_text(json.dumps(step(price=1)), encoding='utf-8')
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        code = sc.main(['--step', str(bad), '--inventory', str(inv), '--json', str(Path(base) / 'bad_out.json')])
    assert code == 2 and 'never typed in' in said.getvalue() and not (Path(base) / 'bad_out.json').exists(), said.getvalue()


def patch_attr(owner, name, value):
    def apply():
        saved = getattr(owner, name)
        setattr(owner, name, value)
        return lambda: setattr(owner, name, saved)
    return apply


_hourly, _read_step, _lines, _newest = sc.hourly_rate, sc.read_step, sc.lines, sc.newest_inventory


def _no_measures(value):
    read = _read_step(value)
    read['measures'] = []
    return read


def _without_refuse():
    saved = sc.refuse
    sc.refuse = lambda condition, message: None
    return lambda: setattr(sc, 'refuse', saved)


NEUTRALISE = {
    # a fixed price typed into the tool in place of the inventory's
    'proof_price_is_read_from_the_inventory': patch_attr(sc, 'hourly_rate', lambda inv, t: (1.29, [])),
    # the typed-price scan removed
    'proof_a_typed_price_is_refused': patch_attr(sc, 'price_keys', lambda value, where='step': []),
    # an unlisted or unpriced type falls back to a price
    'proof_an_unlisted_or_unpriced_type_is_refused': patch_attr(
        sc, 'hourly_rate', lambda inv, t: _hourly(inv, t) if t == 'gpu_1x_a10' else (1.29, [])),
    # a storage price typed into the tool
    'proof_storage_is_priced_from_the_record': patch_attr(sc, 'storage_price', lambda record: 0.2),
    # the first inventory found, not the newest
    'proof_the_newest_inventory_is_taken_by_its_own_time': patch_attr(
        sc, 'newest_inventory', lambda paths: paths[0] if paths else _newest(paths)),
    # the declared measures dropped
    'proof_both_figures_follow_the_declared_measures': patch_attr(sc, 'read_step', _no_measures),
    # the measures line left out of the print
    'proof_every_measure_is_named_with_its_source': patch_attr(
        sc, 'lines', lambda result: [l for l in _lines(result) if not l.startswith('  Measures')]),
    # every refusal of a bad measure removed
    'proof_a_bad_measure_is_refused': _without_refuse,
    # the figures not printed
    'proof_the_command_prints_both_figures': patch_attr(sc, 'lines', lambda result: []),
}

GROUPS = {
    500: [proof_price_is_read_from_the_inventory, proof_a_typed_price_is_refused,
          proof_an_unlisted_or_unpriced_type_is_refused, proof_storage_is_priced_from_the_record,
          proof_the_newest_inventory_is_taken_by_its_own_time],
    501: [proof_both_figures_follow_the_declared_measures, proof_every_measure_is_named_with_its_source,
          proof_a_bad_measure_is_refused, proof_the_command_prints_both_figures],
}


def run(proof):
    with tempfile.TemporaryDirectory() as base:
        proof(base)


def neutralised(proof):
    restore = NEUTRALISE[proof.__name__]()
    try:
        run(proof)
    except Exception:
        return True
    finally:
        restore()
    return False


def check(number):
    passed = []
    for proof in GROUPS[number]:
        try:
            run(proof)
            if not neutralised(proof):
                return 'FAIL', proof.__name__ + ' still passes when neutralised'
            run(proof)
        except Exception as exc:
            return 'FAIL', '%s: %s %s' % (proof.__name__, type(exc).__name__, str(exc)[:200])
        passed.append(proof.__name__)
    what = {500: 'the hourly price read from the provider inventory for the named type, the storage price from the '
                 'storage record, a typed price at any depth refused, an unlisted or unpriced type refused, the '
                 'newest inventory taken by its own observed_at',
            501: 'both figures as the guard\'s IV.3 forecast, without and with asset copy, image layers, warm file '
                 'system, batching and a smaller set, every measure printed with its change and source, bad '
                 'measures refused, the command printing both and refusing a typed price'}[number]
    return 'PASS', '%d proofs, each neutralise, fail, restore, pass, fixtures only: %s' % (len(passed), what)


if __name__ == '__main__':
    status, detail = check(int(sys.argv[1]) if len(sys.argv) > 1 else 500)
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
