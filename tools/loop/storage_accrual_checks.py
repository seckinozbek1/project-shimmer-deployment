#!/usr/bin/env python3
"""Gate proof for check 709 (D-946): storage accrues piecewise at the rate each budget_change line declares.

Fixture ledgers only (no real ledger, no provider, no model). Proofs, on tools/loop/instance_reaper.ledger_view:
  piecewise   a budget_open at 0.13 a day and a budget_change at 0.99 from day 10: the storage share at day 20 is
              0.13 x 10 + 0.99 x 10, the total is not lower than the old reading (0.13 x 20)
  no_change   a ledger with no storage row reads exactly the old figure (rate x days since the loop start)
  lower_row   a row declaring a rate below the opening rate never lowers the total below the old reading
  figures     the budget, the hard stop and the warning read from the ledger are the same with and without the row
Each proof is run as built (passes), with the accrual neutralised (must fail), restored and run again.
"""
from __future__ import annotations

import contextlib
import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import instance_reaper as ir  # noqa: E402

START = datetime(2026, 10, 1, tzinfo=timezone.utc)
NOW = START + timedelta(days=20)


def _open(rate=0.13):
    return {'event': 'budget_open', 'time_utc': START.isoformat(), 'loop_start_utc': START.isoformat(),
            'storage_usd_per_day': rate, 'budget_usd': 601.0, 'hard_stop_usd': 600.0, 'warning_usd': 463.0}


def _change(day, rate=None):
    row = {'event': 'budget_change', 'time_utc': (START + timedelta(days=day)).isoformat(),
           'budget_usd': 601.0, 'hard_stop_usd': 600.0, 'warning_usd': 463.0}
    if rate is not None:
        row['storage_usd_per_day'] = rate
    return row


def _old_total(rows):
    """The reading before D-946, written out here: the opening rate x days since the loop start."""
    rate = [float(r.get('storage_usd_per_day') or 0) for r in rows if r.get('event') == 'budget_open'][-1]
    return rate * 20


def _total(rows):
    return ir.ledger_view(rows, NOW)[2]


def observe_piecewise():
    rows = [_open(), _change(5), _change(10, 0.99)]
    new = _total(rows)
    return {'exact': abs(new - (0.13 * 10 + 0.99 * 10)) < 1e-9, 'not_lower': new >= _old_total(rows) - 1e-12}


def expected_piecewise():
    return {'exact': True, 'not_lower': True}


def observe_no_change():
    rows = [_open(), _change(5)]
    return {'same': abs(_total(rows) - _old_total(rows)) < 1e-9}


def expected_no_change():
    return {'same': True}


def observe_lower_row():
    rows = [_open(), _change(10, 0.05)]
    new = _total(rows)
    return {'not_lower': new >= _old_total(rows) - 1e-12}


def expected_lower_row():
    return {'not_lower': True}


def observe_figures():
    plain, with_row = [_open(), _change(5)], [_open(), _change(5), _change(10, 0.99)]
    return {'same': (ir.budget_figures(plain), ir.warning_figure(plain)) == (ir.budget_figures(with_row),
                                                                           ir.warning_figure(with_row)),
            'values': ir.budget_figures(with_row) == (601.0, 600.0) and ir.warning_figure(with_row) == 463.0}


def expected_figures():
    return {'same': True, 'values': True}


def _old_accrual(base, start, now, changes):
    return base * (now - start).total_seconds() / 86400


def _no_floor_accrual(base, start, now, changes):
    """Piecewise but taking each declared rate as is (the floor at the opening rate neutralised)."""
    rate, total, cursor = base, 0.0, start
    for moment, declared in sorted(changes):
        if start < moment < now:
            total += rate * (moment - cursor).total_seconds() / 86400
            cursor = moment
        rate = declared
    return total + rate * (now - cursor).total_seconds() / 86400


@contextlib.contextmanager
def _patched(fn):
    saved = ir.storage_accrual
    ir.storage_accrual = fn
    try:
        yield
    finally:
        ir.storage_accrual = saved


PROOFS = ("piecewise", "no_change", "lower_row", "figures")
NEUTRALISATIONS = {
    "flat_rate_only": (_old_accrual, ("piecewise",)),
    "declared_rate_unfloored": (_no_floor_accrual, ("lower_row",)),
}


def run_709():
    space = globals()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            first = {n: space["observe_" + n]() for n in PROOFS}
            broken = {}
            for name, (fn, names) in NEUTRALISATIONS.items():
                with _patched(fn):
                    broken[name] = {n: space["observe_" + n]() for n in names}
            again = {n: space["observe_" + n]() for n in PROOFS}
    except Exception as exc:
        return "FAIL", "%s %s" % (type(exc).__name__, str(exc)[:300])
    for n in PROOFS:
        want = space["expected_" + n]()
        if first[n] != want:
            return "FAIL", "%s as built: %s" % (n, first[n])
        if again[n] != want:
            return "FAIL", "%s after restore: %s" % (n, again[n])
    for name, (_fn, names) in NEUTRALISATIONS.items():
        for n in names:
            if broken[name][n] == space["expected_" + n]():
                return "FAIL", "%s still passes when %s is neutralised" % (n, name)
    return "PASS", "%d proofs, %d neutralisations, fail, restore, pass: storage accrues piecewise at each " \
        "budget_change rate, never below the old reading (%s)" % (len(PROOFS), len(NEUTRALISATIONS), ", ".join(PROOFS))


if __name__ == "__main__":
    status, detail = run_709()
    print("709", status, detail)
    sys.exit(0 if status == "PASS" else 1)
