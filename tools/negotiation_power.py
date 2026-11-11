#!/usr/bin/env python3
"""The power of each negotiation claim, by simulation (D-S102 item 8; plan sections 2.7 and 7; D-395).

Run before the freeze at the minimum counts (8 headline cases, 12 movement rows and 2 open issues
each), and again at the freeze on the frozen counts. The plan's rule, written before any figure:
a claim whose simulated power is below 0.8 is reported as an indicator, never a claim.

Each simulated set draws:
- the key's labels from the class shares;
- each arm's answers. A row is answered `no_answer` at the arm's refusal rate. Otherwise it is right
  with the arm's agreement for that case, else another label at random.
- the arms' agreements per case: a case effect on the logit scale, with the intra-case correlation
  `icc`. The arms share a fraction `rho` of that effect, so that hard cases are hard for both.
- round 3: a good suggestion per open issue at each arm's good rate, with the same case effect.

Each set is scored by tools/score_negotiation.py's own `test_claim`: the BCa, exact below 10,000
distinct resamples; the jackknife cross-check; the permutation p; and, for C2 and C4, the recall
and coverage conditions. All at opening 1's alpha. The power of a claim is the share of sets in
which it is shown. No case text and no key is read.

    py -3.12 tools/negotiation_power.py [--freeze FREEZE.json] [--sims 100]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("score_negotiation", HERE / "score_negotiation.py")
score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(score)

# The assumptions, written before any figure (plan section 2.7).
ASSUMED = {"agreement": {"system": 0.70, "B1": 0.55, "cloud": 0.75},
           "no_answer": {"system": 0.0, "B1": 0.05, "cloud": 0.02},
           # A row the key labels with a movement answered not_computable instead: the system's refusals
           # (D-319's rule refuses many such rows), B1's and the cloud's own "cannot be told" (D-419).
           "over_not_computable": {"system": 0.30, "B1": 0.10, "cloud": 0.05},
           "good_rate": {"system": 0.50, "B1": 0.30},
           "rho": 0.5}
SHARES = {"moved_toward": 0.3, "moved_away": 0.2, "unchanged_from_prior": 0.1, "not_computable": 0.4}


def _logit(p):
    return math.log(p / (1 - p))


def _expit(x):
    return 1 / (1 + math.exp(-x))


def _spread(icc):
    return math.sqrt(icc / (1 - icc) * (math.pi ** 2 / 3)) if icc > 0 else 0.0


def simulate_set(shares, case_sizes, open_per_case, icc, rng, assumed=ASSUMED):
    """({arm: {case: Counter of (key, predicted)}}, {arm: {case: (good, n, U, refused)}})."""
    labels, weights = zip(*sorted(shares.items()))
    sd, rho = _spread(icc), assumed["rho"]
    positions, round3 = {a: {} for a in assumed["agreement"]}, {a: {} for a in assumed["good_rate"]}
    for i, n in enumerate(case_sizes):
        case = "c%02d" % i
        shared = rng.gauss(0, 1)
        keys = rng.choices(labels, weights=weights, k=n)
        for arm, agreement in assumed["agreement"].items():
            effect = sd * (math.sqrt(rho) * shared + math.sqrt(1 - rho) * rng.gauss(0, 1))
            p = _expit(_logit(agreement) + effect)
            rows = []
            for k in keys:
                if rng.random() < assumed["no_answer"][arm]:
                    rows.append((k, score.NO_ANSWER))
                elif k in score.MOVEMENTS and rng.random() < assumed["over_not_computable"][arm]:
                    rows.append((k, "not_computable"))
                elif rng.random() < p:
                    rows.append((k, k))
                else:
                    rows.append((k, rng.choice([x for x in score.LABELS if x != k])))
            positions[arm][case] = Counter(rows)
        for arm, rate in assumed["good_rate"].items():
            effect = sd * (math.sqrt(rho) * shared + math.sqrt(1 - rho) * rng.gauss(0, 1))
            p = _expit(_logit(rate) + effect)
            good = sum(1 for _ in range(open_per_case) if rng.random() < p)
            round3[arm][case] = (good, open_per_case, 2 * good, 0)
    return positions, round3


def power(case_sizes, open_per_case, *, shares=SHARES, iccs=(0.2, 0.5), sims=1000, seed=20261109, assumed=ASSUMED,
          resamples=None, only=None):
    rng = random.Random(seed)
    out = {}
    for icc in iccs:
        shown = Counter()
        for _ in range(sims):
            positions, round3 = simulate_set(shares, case_sizes, open_per_case, icc, rng, assumed)
            for name, feature, figure, other in score.CLAIMS:
                if only and name not in only:
                    continue
                if feature == "positions":
                    extra = {"recall": score.movement_recall, "coverage": score.coverage} if name in score.PRECISION_CLAIMS else None
                    result = score.test_claim(name, score.FIGURES[figure], positions["system"], positions[other], 1,
                                              extra=extra, resamples=resamples)
                else:
                    result = score.test_claim(name, score.good_rate, round3["system"], round3[other], 1, resamples=resamples)
                # Power is read as if every claim were a claim: an indicator's numbers are the same.
                ok = all(result.get(k) is not None for k in ("difference", "lower", "jackknife_lower", "permutation_p")) \
                    and result["lower"] > 0 and result["jackknife_lower"] > 0 and result["permutation_p"] <= result["alpha"] \
                    and all(result[k] >= 0 for k in result if k.endswith("_upper") and result[k] is not None)
                shown[name] += bool(ok)
        out[str(icc)] = {name: shown[name] / sims for name, *_ in score.CLAIMS if not only or name in only}
    return {"alpha": score.alpha_for(1), "assumed": assumed, "shares": shares, "iccs": list(iccs), "sims": sims,
            "cases": len(case_sizes), "rows_per_case": sorted(set(case_sizes)), "open_issues_per_case": open_per_case,
            "exact_bootstrap": score._distinct_resamples(len(case_sizes)) < score.EXACT_LIMIT,
            "power": out, "below_0_8_at_any_icc": below_at_any_icc(out), "claim_by_plan_rule": claim_by_plan_rule(out)}


POWER_FLOOR = 0.8


def below_at_any_icc(power_by_icc):
    """The claims whose simulated power is below 0.8 at one correlation or more (D-437)."""
    names = sorted({n for v in power_by_icc.values() for n in v})
    return [n for n in names if any(v.get(n, 0.0) < POWER_FLOOR for v in power_by_icc.values())]


def claim_by_plan_rule(power_by_icc):
    """{claim: claim or indicator} by the plan's rule (section 2.7, D-414, D-430 item 1): only a primary
    claim can be a claim, and only at 0.8 or more at every correlation simulated; the rest are indicators.
    It is the scorer's own rule (`score_negotiation.c1_status`) on the same figures."""
    below = set(below_at_any_icc(power_by_icc))
    names = sorted({n for v in power_by_icc.values() for n in v})
    return {n: ("claim" if n in score.PRIMARY and n not in below else "indicator") for n in names}


def code_sha256():
    """This file's SHA-256 with CRLF made LF, so a record names the code it was simulated with."""
    import hashlib
    return hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--freeze", type=Path, help="the frozen set's FREEZE.json; without it, the minimum counts")
    parser.add_argument("--sims", type=int, default=1000)
    parser.add_argument("--cases", type=int, default=8, help="headline cases when no FREEZE.json is given")
    parser.add_argument("--only", default="", help="claims to simulate, comma separated (default all)")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.freeze:
        freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
        head = [c for c, s in freeze["subsets"].items() if s in score.HEADLINE_SUBSETS]
        sizes = [sum(1 for r in freeze["movement_key"] if r["case_id"] == c) for c in head]
        opens = max(1, round(sum(1 for c, _ in freeze["open_issues"] if c in head) / max(1, len(head))))
        # The headline's own class shares (F and S), never the whole key's (D-419 gap 9).
        result = power(sizes, opens, shares=freeze["headline_class_shares"], sims=args.sims,
                       only=[c for c in args.only.split(",") if c] or None)
        result["set_sha256"] = freeze["set_sha256"]
    else:
        result = power([12] * args.cases, 2, sims=args.sims, only=[c for c in args.only.split(",") if c] or None)
    result["code_sha256"] = code_sha256()
    result["only"] = [c for c in args.only.split(",") if c] or None
    text = json.dumps(result, indent=1)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
