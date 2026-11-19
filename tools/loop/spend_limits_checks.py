"""Proofs for the operator's spending limits (D-708) in tools/loop_budget_guard.py, on fixtures only: a
temporary ledger, temporary limit files and the repository's own config/loop_spend_limits.json read as
it is. No network, no real ledger, no instance. Each proof is run as built (passes), neutralised (must
fail), restored (passes again).

    py -3.12 -X utf8 tools/loop/spend_limits_checks.py
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import loop_budget_guard as guard  # noqa: E402
import fs_listing as fs  # noqa: E402

START = 1_800_000_000.0
RATE = 1.29
HARD_STOP = 600.0      # the ledger's budget line (the reaper's hard stop), above every declared remaining ceiling


def minutes_for(usd, rate=RATE):
    """The forecast minutes whose IV.3 forecast (minutes / 60 x rate x 1.3) is `usd`."""
    return usd * 60 / (rate * guard.FORECAST_FACTOR)


def ledger_with_spend(base, spend):
    """A budget line at the real figures (601, hard stop 600) and one closed launch that cost `spend`."""
    path = Path(base) / 'budget_ledger.jsonl'
    t = guard.utc(START - 86400)
    lines = [dict(event='budget_open', time_utc=t, loop_start_utc=t, budget_usd=HARD_STOP + 1.0, hard_stop_usd=HARD_STOP,
                  storage_usd_per_day=0.0, a10_reference_price_usd_per_hour=RATE),
             dict(event='launch', time_utc=t, launch_requested_utc=t, instance_id='e' * 32,
                  instance_name='shimmer-loop-past', price_usd_per_hour=RATE, deadline_utc=guard.utc(START - 3600)),
             dict(event='termination', time_utc=guard.utc(START - 3600), instance_id='e' * 32,
                  instance_name='shimmer-loop-past', actual_cost=float(spend))]
    path.write_text(''.join(json.dumps(l) + '\n' for l in lines), encoding='utf-8')
    return path


def decide(ledger, usd, limits, **kw):
    return guard.check(ledgers=[ledger], forecast_minutes=minutes_for(usd), hourly_rate=RATE, storage_forecast_usd=0.0,
                       now_epoch=START, reserve_minutes=5.0, reaped=[ledger], spend_limits=limits, **kw)


def refusal(call):
    try:
        call()
    except guard.GuardRefusal as exc:
        return str(exc)
    return None


def limits_file(base, step, limit, baseline=197.0):
    path = Path(base) / 'loop_spend_limits.json'
    path.write_text(json.dumps(dict(version=1, decision='D-708', step_preapproved_usd=step, remaining_limit_usd=limit,
                                    remaining_baseline_usd=baseline)), encoding='utf-8')
    return path


def proof_step_five_admitted_five_point_oh_one_refused(base):
    """The declared per-step pre-approval is 5 USD: a 5.00 USD step goes ahead with no question, a 5.01 USD
    step is refused and sent to Seckin, unless his approval of at least its forecast names its decision."""
    limits = guard.read_spend_limits()            # the repository's one declared source, as it is
    assert limits['step_preapproved_usd'] == 5.0, limits
    ledger = ledger_with_spend(base, 250.0)
    admitted = decide(ledger, 5.00, limits)
    assert round(admitted['forecast_usd'], 2) == 5.00 and admitted['step_rule'] == 'pre-approved', admitted
    assert admitted['step_preapproved_usd'] == 5.0 and admitted['spend_limits_decision'] == limits['decision'], admitted
    said = refusal(lambda: decide(ledger, 5.01, limits))
    assert said and 'per-step pre-approval' in said and 'ask Seckin' in said, said
    # his word, recorded under a decision, admits exactly what it approves
    assert decide(ledger, 5.01, limits, step_approval=dict(usd=6.0, source='D-999'))['step_rule'] == 'approved'
    assert 'approved in D-999' in (refusal(lambda: decide(ledger, 5.01, limits,
                                                          step_approval=dict(usd=5.005, source='D-999'))) or '')
    assert 'names the decision' in (refusal(lambda: decide(ledger, 5.01, limits,
                                                           step_approval=dict(usd=6.0, source='yes'))) or '')


def declared_history_entry(limits):
    """The history entry of config/loop_spend_limits.json that the top-level figures come from: the newest one
    naming a remaining_limit_usd, which must carry the top-level decision and limit (else the file disagrees)."""
    raw = json.loads(Path(guard.SPEND_LIMITS).read_text(encoding='utf-8'))
    named = [h for h in raw.get('history') or [] if 'remaining_limit_usd' in h]
    return named[-1] if named else None


def proof_remaining_limit_from_the_declared_baseline(base):
    """The remaining-spend limit is the declared one from the declared baseline (D-749: 203 USD from 197, ceiling
    400; D-708 was 140, ceiling 337), read from the file as it is, never typed in here: a spend 9 USD under the
    ceiling still admits a 4 USD step; a spend 4 USD under it refuses that step by the remaining limit, though
    the budget's own hard stop would admit it; the cap never passes the ceiling."""
    limits = guard.read_spend_limits()
    ceiling = limits['remaining_ceiling_usd']
    assert ceiling == limits['remaining_baseline_usd'] + limits['remaining_limit_usd'], limits
    newest = declared_history_entry(limits)
    assert newest and (newest['decision'], newest['remaining_limit_usd'])         == (limits['decision'], limits['remaining_limit_usd']), (newest, limits)
    assert ceiling + 10.0 < HARD_STOP, limits          # the fixture's hard stop must lie above the ceiling
    overrun = guard.overrun_reserve([], RATE)
    under = decide(ledger_with_spend(base, ceiling - 9.0), 4.0, limits)
    assert under['remaining_ceiling_usd'] == ceiling and under['cap_usd'] >= under['forecast_usd'], under
    assert abs(under['remaining_left_usd'] - (9.0 - overrun)) < 1e-6, under
    tight = ledger_with_spend(base, ceiling - 4.0)
    said = refusal(lambda: decide(tight, 4.0, limits))
    expected = '%.2f dollars from the %.2f dollar baseline' % (limits['remaining_limit_usd'],
                                                              limits['remaining_baseline_usd'])
    assert said and 'remaining-spend limit' in said and expected in said, said
    assert decide(tight, 4.0, None)['cap_usd'] >= 4.0       # the hard stop alone admits it: the limit refused it
    near = decide(ledger_with_spend(base, ceiling - 5.5), 4.0, limits)
    assert near['cap_usd'] <= 5.5 - overrun + 1e-6 < guard.CAP_FACTOR * near['forecast_usd'], near


def proof_a_real_launch_reads_the_file_at_call_time(base):
    """A real launch (no `reaped`) reads config/loop_spend_limits.json at the moment of the decision: the same
    call refuses a 4 USD step under a file that says 3 and admits it once the file says 5, with no restart."""
    ledger = ledger_with_spend(base, 250.0)
    saved = {name: getattr(guard, name) for name in ('SPEND_LIMITS', 'reaper_ledgers', 'standing_orders_refusal')}
    guard.SPEND_LIMITS = limits_file(base, 3.0, 140.0)
    guard.reaper_ledgers = lambda: [ledger]
    guard.standing_orders_refusal = lambda root=None: True
    store = Path(base) / 'cloud_reference_spend.jsonl'
    store.write_text('', encoding='utf-8')
    try:
        real = lambda: guard.check(ledgers=[ledger], forecast_minutes=minutes_for(4.0), hourly_rate=RATE,
                                   storage_forecast_usd=0.0, now_epoch=START, reserve_minutes=5.0, spend_store=store)
        said = refusal(real)
        assert said and 'above the 3.00 dollar per-step pre-approval' in said, said
        limits_file(base, 5.0, 140.0)
        assert real()['step_rule'] == 'pre-approved'
        # a figure that is not a number refuses the launch, never read as no limit
        Path(guard.SPEND_LIMITS).write_text('{"step_preapproved_usd": "five"}', encoding='utf-8')
        said = refusal(real)
        assert said == 'Invalid per-step pre-approval', said
    finally:
        for name, value in saved.items():
            setattr(guard, name, value)


def proof_listing_cap_follows_the_declared_step(base):
    """tools/loop/fs_listing.py's own cap is the declared per-step pre-approval: 5.00 admitted, 5.01 refused;
    and it follows the file (a file saying 3 refuses a 4 USD cap)."""
    fs.check_plan(5.0, 15.0, 30.0, 0.0)
    try:
        fs.check_plan(5.01, 15.0, 30.0, 0.0)
    except fs.ListingRefusal as exc:
        assert 'per-step pre-approval' in str(exc), exc
    else:
        raise AssertionError('a 5.01 USD listing cap was admitted')
    saved = guard.SPEND_LIMITS
    guard.SPEND_LIMITS = limits_file(base, 3.0, 140.0)
    try:
        try:
            fs.check_plan(4.0, 15.0, 30.0, 0.0)
        except fs.ListingRefusal:
            pass
        else:
            raise AssertionError('the listing cap did not follow the declared figure')
    finally:
        guard.SPEND_LIMITS = saved


PROOFS = [proof_step_five_admitted_five_point_oh_one_refused, proof_remaining_limit_from_the_declared_baseline,
          proof_a_real_launch_reads_the_file_at_call_time, proof_listing_cap_follows_the_declared_step]


def run(proof):
    with tempfile.TemporaryDirectory() as t:
        proof(Path(t))


def patch_attr(obj, name, value):
    def apply():
        old = getattr(obj, name)
        setattr(obj, name, value)
        return lambda: setattr(obj, name, old)
    return apply


NEUTRALISE = {
    # the per-step rule admits everything: a 5.01 USD step goes ahead with no question
    'proof_step_five_admitted_five_point_oh_one_refused': patch_attr(guard, 'step_rule', lambda f, l, a=None: 'pre-approved'),
    # the remaining-spend refusal removed: only the cap rule is left, with another message
    'proof_remaining_limit_from_the_declared_baseline': patch_attr(guard, 'remaining_refusal', lambda committed, forecast, limits:
                                                         round(limits['remaining_ceiling_usd'] - committed, 4)),
    # a real launch no longer reads the file: no limit applies
    'proof_a_real_launch_reads_the_file_at_call_time': patch_attr(guard, 'read_spend_limits', lambda path=None: None),
    # the old constant back in the listing tool
    'proof_listing_cap_follows_the_declared_step': patch_attr(fs, 'max_cap_usd', lambda: 3.0),
}


def neutralised(proof):
    restore = NEUTRALISE[proof.__name__]()
    try:
        run(proof)
    except Exception:
        return True
    finally:
        restore()
    return False


def _declared_figures():
    limits = guard.read_spend_limits()
    return (limits['decision'], limits['remaining_limit_usd'], limits['remaining_baseline_usd'],
            limits['remaining_ceiling_usd'])


def check():
    passed = []
    for proof in PROOFS:
        try:
            run(proof)
            if not neutralised(proof):
                return 'FAIL', proof.__name__ + ' still passes when neutralised'
            run(proof)
        except Exception as exc:
            return 'FAIL', '%s: %s %s' % (proof.__name__, type(exc).__name__, str(exc)[:200])
        passed.append(proof.__name__)
    return 'PASS', ('%d proofs, each neutralise, fail, restore, pass, fixtures and the declared file only: a 5.00 USD '
                    'step admitted with no question and a 5.01 USD one refused unless approved under a decision; the '
                    'declared remaining-spend limit from the declared baseline (%s: %.0f USD from %.0f, ceiling %.0f) '
                    'refusing a forecast past it that the hard stop would admit; a real launch reading config/loop_spend_limits.json at call '
                    'time; the listing cap following the declared step'
                    % ((len(passed),) + _declared_figures()))


if __name__ == '__main__':
    status, detail = check()
    print(status, detail)
    raise SystemExit(0 if status == 'PASS' else 1)
