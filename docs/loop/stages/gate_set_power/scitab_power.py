"""SciTab's gate power, simulated in macro-F1 with the table bootstrap (GATE_SET.md section 5). No data read.

Usage: scitab_power.py SETTING TABLES SIMS RHO LEVEL [CLAIMS_PER_TABLE, default 6.1]
  SETTING 2 or 3; LEVEL the interval's level (.975 at the first claim read). The system's accuracy is
  chosen so that its expected macro-F1 is 10 points above B1's (bar a's difference, in the paper's
  metric), by a large calibration sample. Printed: P(low end above zero) and P(the bar as coded: the
  point difference at least .10 and the low end above zero).
"""
import sys

import numpy as np
from scipy.stats import norm


def macro_f1(gold, pred, k):
    """Macro-F1 over k classes for each row of 2-D arrays (bootstrap draws by items)."""
    out = 0.0
    for c in range(k):
        tp = ((pred == c) & (gold == c)).sum(axis=-1)
        fp = ((pred == c) & (gold != c)).sum(axis=-1)
        fn = ((pred != c) & (gold == c)).sum(axis=-1)
        den = 2 * tp + fp + fn
        out = out + np.where(den > 0, 2 * tp / np.maximum(den, 1), 0.0)
    return out / k


def labels(rng, gold, ok, k):
    return np.where(ok, gold, (gold + rng.integers(1, k, gold.shape)) % k)


def sample(rng, n_tables, per_table, shares, acc_b1, acc_sys, rho, sd, k):
    sizes = rng.poisson(per_table - 1, n_tables) + 1
    tab = np.repeat(np.arange(n_tables), sizes)
    gold = rng.choice(k, size=len(tab), p=shares)
    u = rng.normal(0, sd, n_tables)[tab]
    z1 = rng.normal(size=len(tab))
    z2 = rho * z1 + np.sqrt(1 - rho * rho) * rng.normal(size=len(tab))
    sc = np.sqrt(1 + sd ** 2)
    pb = labels(rng, gold, (z1 + u) / sc < norm.ppf(acc_b1), k)
    ps = labels(rng, gold, (z2 + u) / sc < norm.ppf(acc_sys), k)
    return tab, gold, pb, ps


def calibrate(rng, shares, acc_b1, rho, sd, k):
    """The system accuracy whose expected macro-F1 is 10 points above B1's."""
    best = None
    for acc in np.arange(acc_b1 + .05, min(.99, acc_b1 + .20), .0025):
        tab, gold, pb, ps = sample(rng, 20000, 6.1, shares, acc_b1, acc, rho, sd, k)
        diff = macro_f1(gold, ps, k) - macro_f1(gold, pb, k)
        if best is None or abs(diff - .10) < abs(best[1] - .10):
            best = (float(acc), float(diff))
    return best


def main():
    setting, n_tables, sims, rho, level = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5])
    per_table = float(sys.argv[6]) if len(sys.argv) > 6 else 6.1
    rng = np.random.default_rng(20261109)
    k = 3 if setting == "3" else 2
    shares = [0.373, 0.336, 0.291] if k == 3 else [0.527, 0.473]   # the paper's mix (457, 411, 356)
    acc_b1, sd, boots = (0.55 if k == 3 else 0.70), 0.6, 1000
    acc_sys, calibrated = calibrate(rng, shares, acc_b1, rho, sd, k)
    lo_q = (1 - level) / 2
    lower, joint, claims = 0, 0, []
    for _ in range(sims):
        tab, gold, pb, ps = sample(rng, n_tables, per_table, shares, acc_b1, acc_sys, rho, sd, k)
        claims.append(len(tab))
        point = macro_f1(gold, ps, k) - macro_f1(gold, pb, k)
        idx = [np.flatnonzero(tab == t) for t in range(n_tables)]
        diffs = np.empty(boots)
        for b in range(boots):
            ii = np.concatenate([idx[t] for t in rng.integers(0, n_tables, n_tables)])
            diffs[b] = macro_f1(gold[ii], ps[ii], k) - macro_f1(gold[ii], pb[ii], k)
        low = np.quantile(diffs, lo_q) > 0
        lower += low
        joint += low and point >= .10
    print("setting=%s tables=%d mean_claims=%.0f level=%.3f rho=%.1f acc_b1=%.2f acc_sys=%.4f (macro-F1 difference %.3f) "
          "P(low>0)=%.2f P(bar as coded)=%.2f sims=%d boots=%d"
          % (setting, n_tables, np.mean(claims), level, rho, acc_b1, acc_sys, calibrated, lower / sims, joint / sims, sims, boots))


main()
