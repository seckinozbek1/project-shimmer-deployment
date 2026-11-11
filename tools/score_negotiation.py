#!/usr/bin/env python3
"""Score the negotiation features on the held-out cases (D-S102 item 8; D-389, D-395).

docs/loop/stages/NEGOTIATION_MEASUREMENT_PLAN.md sections 3, 4 and 7, in code:

- **Labels** (section 3.2). Each arm's answers become labels by the plan's one mapping. The
  system's `position_gaps` rows are read off each run's audit/multi_round.json. B1's and the cloud
  reference's answers come from benchmark/baselines/negotiation_b1.py `answers`. A row an arm left
  without an answer is `no_answer`, never in the key: it counts as a missed true label.
- **Positions** (section 3.3). Macro-F1 averaged over the key's classes only, movement precision,
  movement recall and coverage, with the two floors on the same rows.
- **Round 3** (section 4.5). The good-suggestion rate, mean U over all open issues and over the
  good ones, and each arm's refusal rate. Python's checks are applied alike to every arm, including
  the plan's one rule mapping a quote to the agreed unit whose text holds it (`quote_unit_closed`).
- **Intervals and tests** (section 2.7).
  - The BCa cluster bootstrap over cases. It is exact (every distinct resample, weighted) when the
    distinct resamples number fewer than 10,000, else 10,000 seeded draws.
  - The cross-check is a jackknife over cases of the pooled difference, at the claim's own alpha.
  - A cluster permutation test (sign flips per case, exact below 10,000 arrangements) of the paired
    difference, at the same alpha.
  - Resamples whose figure is undefined are counted.
- **Claims** (section 7). C1 to C4, each read on the headline cases only.
  - A claim is shown only when its figure is defined, the BCa lower bound and the jackknife lower
    bound lie above zero, and the permutation p is at most the alpha.
  - For C2 and C4 (precision) it also needs the paired recall difference and the paired coverage
    difference not below zero at the same alpha (their BCa upper bounds at or above zero).
  - The alpha is 0.05 / 2^k / 5 at opening k.
  - A claim the plan lists as an indicator (`INDICATORS`, written before the freeze from the power
    simulation at the minimum counts) is reported with the same numbers and never called shown.

Nothing is scored without a committed line for the opening in docs/loop/HELDOUT_OPENINGS.md naming
the frozen set's digest and the configuration's digest (`refuse_without_opening`), and k is at
most 2.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("moved_toward", "moved_away", "unchanged_from_prior", "not_computable")
MOVEMENTS = ("moved_toward", "moved_away", "unchanged_from_prior")
NO_ANSWER = "no_answer"
HEADLINE_SUBSETS = ("F", "S")
MAX_OPENINGS = 2
CLAIMS = (("C1", "positions", "macro_f1", "B1"), ("C2", "positions", "movement_precision", "B1"),
          ("C3", "positions", "macro_f1", "cloud"), ("C4", "positions", "movement_precision", "cloud"),
          ("C5", "round3", "good_rate", "B1"))
PRECISION_CLAIMS = ("C2", "C4")
# D-414: one primary claim, C1, at the first opening's full alpha (0.05 / 2^k, one-sided). C2 to C5 are
# indicators: tested and reported the same way, never called shown.
PRIMARY = ("C1",)
# Written before the freeze (plan sections 2.7 and 7; D-395, D-414, D-419): C2 to C5 by the lead's ruling.
# C1's status is decided at the frozen headline count by its power record (`c1_status`), which the
# scorer requires before it scores.
INDICATORS = frozenset({"C2", "C3", "C4", "C5"})
MIN_POWER_SIMS = 1000
POWER_RECORD = "docs/loop/stages/NEGOTIATION_POWER_C1.json"
RESAMPLES = 10000
EXACT_LIMIT = 10000
SEED = 20261109
OPENINGS = "docs/loop/HELDOUT_OPENINGS.md"
_OPENING = re.compile(r"negotiation-heldout\s+opening\s+k=(\d+)\s+set=([0-9a-f]{64})\s+config=([0-9a-f]{64})")
# The system's equality tolerance on two gaps (paired_review._close) against the key's (0.5 percent).
SYSTEM_TOLERANCE, KEY_TOLERANCE = "relative 1e-6", "0.5 percent of the larger gap"


# ---------------------------------------------------------------------------
# section 3.2: every outcome to a label


def system_label(row):
    """The system's gap row to a label: a movement as written, any `not_computed` (whatever its why)
    to not_computable, anything else to no_answer."""
    if not isinstance(row, dict):
        return NO_ANSWER
    outcome = row.get("outcome")
    if outcome in MOVEMENTS:
        return outcome
    if outcome == "not_computed":
        return "not_computable"
    return NO_ANSWER


def system_answers(run_dir):
    record = json.loads((Path(run_dir) / "audit" / "multi_round.json").read_text(encoding="utf-8"))
    case = record["manifest"]["case_id"]
    return {(case, r["issue_id"], tuple(r["rounds"])): system_label(r) for r in record.get("position_gaps") or []}


def reply_answers(answers):
    """{(case_id, issue_id, rounds): label} from an answers file's movement rows. One model group only:
    two groups' rows for one key would overwrite each other (D-419 gap 6)."""
    groups = {r.get("group") for r in answers["rows"]}
    if len(groups) > 1:
        raise ValueError("an answers file holds more than one model group: %s" % sorted(map(str, groups)))
    out = {}
    for r in answers["rows"]:
        if r.get("form") == "movement":
            label = r.get("label")
            out[(r["case_id"], r["issue_id"], tuple(r["rounds"]))] = label if label in LABELS else NO_ANSWER
    return out


def pairs(key_rows, predictions):
    """{case_id: [(key label, predicted label)]}: every key row; an arm's missing row is no_answer."""
    out = {}
    for r in key_rows:
        k = (r["case_id"], r["issue_id"], tuple(r["rounds"]))
        out.setdefault(r["case_id"], []).append((r["label"], predictions.get(k, NO_ANSWER)))
    return out


# ---------------------------------------------------------------------------
# section 3.3: the figures, from a confusion count


def counts(rows):
    return Counter(rows)


def macro_f1(c):
    """Over the key's classes only; a prediction of another label (no_answer among them) is a miss
    for the true class. None when the key holds fewer than two classes."""
    c = c if isinstance(c, Counter) else counts(c)
    classes = sorted({k for k, _ in c})
    if len(classes) < 2:
        return None
    scores = []
    for cl in classes:
        tp = c[(cl, cl)]
        fp = sum(n for (k, p), n in c.items() if p == cl and k != cl)
        fn = sum(n for (k, p), n in c.items() if k == cl and p != cl)
        scores.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return sum(scores) / len(scores)


def movement_precision(c):
    c = c if isinstance(c, Counter) else counts(c)
    said = sum(n for (k, p), n in c.items() if p in MOVEMENTS)
    return None if not said else sum(n for (k, p), n in c.items() if p in MOVEMENTS and k == p) / said


def movement_recall(c):
    c = c if isinstance(c, Counter) else counts(c)
    moved = sum(n for (k, p), n in c.items() if k in MOVEMENTS)
    return None if not moved else sum(n for (k, p), n in c.items() if k in MOVEMENTS and k == p) / moved


def coverage(c):
    c = c if isinstance(c, Counter) else counts(c)
    moved = sum(n for (k, p), n in c.items() if k in MOVEMENTS)
    return None if not moved else sum(n for (k, p), n in c.items() if k in MOVEMENTS and p in MOVEMENTS) / moved


FIGURES = {"macro_f1": macro_f1, "movement_precision": movement_precision, "movement_recall": movement_recall,
           "coverage": coverage}


def floors(rows):
    """The two floors on the same rows: an arm answering not_computable on every row, and one
    answering the key's most common label on every row (a tie goes to the first in alphabetical order)."""
    keys = [k for k, _ in rows]
    majority = max(sorted(set(keys)), key=keys.count) if keys else None
    return {"all_not_computable": macro_f1([(k, "not_computable") for k in keys]),
            "majority_label": majority, "majority": macro_f1([(k, majority) for k in keys])}


# ---------------------------------------------------------------------------
# section 2.7: resampling over cases


def _norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_ppf(p):
    lo, hi = -10.0, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if _norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if x > (a + 1) / (a + b + 2):
        return 1 - _betainc(b, a, 1 - x)
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b + lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(200):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1 + num * d
        d = 1 / (d if abs(d) > 1e-30 else 1e-30)
        c = 1 + num / (c if abs(c) > 1e-30 else 1e-30)
        f *= c * d
        if abs(1 - c * d) < 1e-12:
            break
    return front * (f - 1)


def _t_ppf(p, df):
    def cdf(t):
        ib = _betainc(df / 2, 0.5, df / (df + t * t))
        return 1 - 0.5 * ib if t > 0 else 0.5 * ib
    lo, hi = -100.0, 100.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _distinct_resamples(n):
    return math.comb(2 * n - 1, n)


_EXACT_CACHE = {}


def resamples_of(n, *, resamples=None, seed=SEED):
    """[(weights per case, probability)]: every distinct bootstrap resample of n cases with its
    multinomial probability when they number fewer than EXACT_LIMIT, else seeded draws of equal weight."""
    resamples = RESAMPLES if resamples is None else resamples
    if _distinct_resamples(n) < EXACT_LIMIT:
        if (n, EXACT_LIMIT) in _EXACT_CACHE:
            return _EXACT_CACHE[(n, EXACT_LIMIT)]
        out = []
        total = n ** n
        for combo in itertools.combinations_with_replacement(range(n), n):
            w = [0] * n
            for i in combo:
                w[i] += 1
            ways = math.factorial(n)
            for x in w:
                ways //= math.factorial(x)
            out.append((w, ways / total))
        _EXACT_CACHE[(n, EXACT_LIMIT)] = out
        return out
    rng = random.Random(seed)
    out = []
    for _ in range(resamples):
        w = [0] * n
        for _ in range(n):
            w[rng.randrange(n)] += 1
        out.append((w, 1.0 / resamples))
    return out


def _combine(parts, weights):
    total = None
    for part, w in zip(parts, weights):
        if w == 0:
            continue
        if isinstance(part, Counter):
            scaled = Counter({k: v * w for k, v in part.items()})
            total = scaled if total is None else total + scaled
        else:
            scaled = tuple(x * w for x in part)
            total = scaled if total is None else tuple(a + b for a, b in zip(total, scaled))
    return total


def bca(statistic, parts, *, alpha=0.05, resamples=None, seed=SEED):
    """(estimate, lower, upper, undefined): the BCa interval, two-sided 1 - alpha, of statistic over
    the sum of `parts` (one per case), resampled over cases. `undefined` is the probability mass of
    resamples whose statistic is undefined, which are left out."""
    n = len(parts)
    estimate = statistic(_combine(parts, [1] * n))
    if estimate is None or n < 2:
        return estimate, None, None, 0.0
    draws, undefined = [], 0.0
    for w, prob in resamples_of(n, resamples=resamples, seed=seed):
        v = statistic(_combine(parts, w))
        if v is None:
            undefined += prob
        else:
            draws.append((v, prob))
    if not draws:
        return estimate, None, None, undefined
    draws.sort()
    mass = sum(p for _, p in draws)
    below = sum(p for v, p in draws if v < estimate) + 0.5 * sum(p for v, p in draws if v == estimate)
    z0 = _norm_ppf(min(max(below / mass, 1e-9), 1 - 1e-9))
    jack = [statistic(_combine(parts, [0 if j == i else 1 for j in range(n)])) for i in range(n)]
    jack = [j for j in jack if j is not None]
    mean = sum(jack) / len(jack) if jack else estimate
    num = sum((mean - j) ** 3 for j in jack)
    den = 6 * (sum((mean - j) ** 2 for j in jack) ** 1.5)
    a = num / den if den else 0.0

    def bound(p):
        z = _norm_ppf(p)
        target = _norm_cdf(z0 + (z0 + z) / (1 - a * (z0 + z))) * mass
        run = 0.0
        for v, pr in draws:
            run += pr
            if run >= target:
                return v
        return draws[-1][0]
    return estimate, bound(alpha / 2), bound(1 - alpha / 2), undefined


def jackknife_lower(statistic, parts, alpha):
    """The one-sided 1 - alpha lower bound of the pooled statistic from a jackknife over cases (t on
    cases less one degree of freedom), or None when any leave-one-out figure is undefined."""
    n = len(parts)
    estimate = statistic(_combine(parts, [1] * n))
    loo = [statistic(_combine(parts, [0 if j == i else 1 for j in range(n)])) for i in range(n)]
    if estimate is None or n < 3 or any(x is None for x in loo):
        return None
    mean = sum(loo) / n
    se = math.sqrt((n - 1) / n * sum((x - mean) ** 2 for x in loo))
    return estimate - _t_ppf(1 - alpha, n - 1) * se


def permutation_p(statistic_pair, paired_parts, *, resamples=None, seed=SEED):
    """The one-sided p of the paired difference by sign flips per case: each case's two arms swapped
    or not. Exact over every arrangement below EXACT_LIMIT, else seeded draws. Undefined arrangements
    count against the claim."""
    n = len(paired_parts)
    observed = statistic_pair(paired_parts)
    if observed is None:
        return None
    if 2 ** n <= EXACT_LIMIT:
        arrangements = itertools.product((False, True), repeat=n)
        total = 2 ** n
    else:
        rng = random.Random(seed)
        total = RESAMPLES if resamples is None else resamples
        arrangements = ([rng.random() < 0.5 for _ in range(n)] for _ in range(total))
    hits = 0
    for flips in arrangements:
        swapped = [(b, a) if f else (a, b) for (a, b), f in zip(paired_parts, flips)]
        v = statistic_pair(swapped)
        if v is None or v >= observed - 1e-12:
            hits += 1
    return hits / total


# ---------------------------------------------------------------------------
# section 4: round 3


def _quote_norm(text):
    """The plan's one rule for matching a quote to a unit: curly quote marks made straight, every run
    of whitespace one space, trimmed; case kept."""
    text = str(text or "")
    # The four curly quote marks (left and right, single and double), by code point.
    for a, b in ((chr(0x2018), "'"), (chr(0x2019), "'"), (chr(0x201C), '"'), (chr(0x201D), '"')):
        text = text.replace(a, b)
    return " ".join(text.split())


def quote_unit_closed(quote, units, closed):
    """True when the quote stands in the text of a last-round unit the case declares agreed.
    `units` is [(unit slug, text)] of the last round, `closed` the declared closed slugs."""
    q = _quote_norm(quote)
    return bool(q) and any(slug in closed and q in _quote_norm(text) for slug, text in units)


def system_suggestions(run_dir):
    """{(case_id, issue_id): {kept, refusal, quote}} from one multi-round run's case-questions layer."""
    record = json.loads((Path(run_dir) / "audit" / "multi_round.json").read_text(encoding="utf-8"))
    case = record["manifest"]["case_id"]
    support = (record.get("case_questions") or {}).get("support") or []
    quotes = {r.get("issue_id"): r.get("quote") for r in support if r.get("item") == "suggestion"}
    out = {}
    for row in support:
        if row.get("item") == "outcome" and row.get("issue_id"):
            kept = row.get("outcome") == "suggested"
            out[(case, row["issue_id"])] = {"kept": kept, "refusal": None if kept else row.get("reason") or row.get("outcome"),
                                            "quote": quotes.get(row["issue_id"]) if kept else None}
    return out


def reply_suggestions(answers):
    return {(r["case_id"], r["issue_id"]): {"kept": bool(r.get("kept")), "refusal": r.get("refusal"), "quote": r.get("quote")}
            for r in answers["rows"] if r.get("form") == "suggestion"}


def apply_closed_rule(python, case_units):
    """Every arm alike: a kept suggestion whose quote stands in an agreed unit is refused
    (`quote_in_agreed_text`). `case_units` is {case_id: (units, closed slugs)}."""
    out = {}
    for key, v in python.items():
        units, closed = case_units.get(key[0], ([], set()))
        if v.get("kept") and quote_unit_closed(v.get("quote"), units, closed):
            v = dict(v, kept=False, refusal="quote_in_agreed_text")
        out[key] = v
    return out


def round3_parts(open_issues, python, sheet):
    """{case_id: (good, n, U over all, refused)} per case: good only when Python kept it and the
    settled sheet passes Q, P and A; U from the sheet, 0 when not good; a missing answer is not good."""
    graded = {(g["case_id"], g["issue_id"]): g for g in sheet}
    out = {}
    for case_id, issue_id in open_issues:
        kept = (python.get((case_id, issue_id)) or {}).get("kept") is True
        g = graded.get((case_id, issue_id)) or {}
        good = kept and all(g.get(c) is True for c in ("Q", "P", "A"))
        u = int(g.get("U") or 0) if good else 0
        a = out.get(case_id, (0, 0, 0, 0))
        out[case_id] = (a[0] + good, a[1] + 1, a[2] + u, a[3] + (not kept))
    return out


def good_rate(part):
    return None if not part or not part[1] else part[0] / part[1]


def round3_figures(parts):
    total = _combine(list(parts.values()), [1] * len(parts)) if parts else (0, 0, 0, 0)
    good, n, u, refused = total
    return {"good_rate": good / n if n else None, "u_all": u / n if n else None, "u_good": u / good if good else None,
            "refusal_rate": refused / n if n else None, "n": n}


# ---------------------------------------------------------------------------
# section 7: openings and claims


def alpha_for(k, claims=None):
    """0.05 / 2^k shared among the primary claims (D-414: one, so 0.025 at the first opening)."""
    claims = len(PRIMARY) if claims is None else claims
    if type(k) is not int or not 1 <= k <= MAX_OPENINGS:
        raise ValueError("an opening is 1 or %d" % MAX_OPENINGS)
    return 0.05 / (2 ** k) / claims


def committed_text(root, rel):
    try:
        return subprocess.run(["git", "-C", str(root), "show", "HEAD:" + rel], capture_output=True, text=True,
                              encoding="utf-8", check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def refuse_without_opening(k, set_sha256, config_sha256, *, text):
    if text is None:
        return "the openings ledger is not committed"
    if type(k) is not int or not 1 <= k <= MAX_OPENINGS:
        return "opening %r: at most %d openings" % (k, MAX_OPENINGS)
    for m in _OPENING.finditer(text):
        if int(m.group(1)) == k and m.group(2) == set_sha256 and m.group(3) == config_sha256:
            return None
    return "no committed opening line names k=%d, this set and this configuration" % k


def _paired_stat(fn):
    def stat(pairs_):
        a = fn(_combine([p[0] for p in pairs_], [1] * len(pairs_)))
        b = fn(_combine([p[1] for p in pairs_], [1] * len(pairs_)))
        return None if a is None or b is None else a - b
    return stat


def _paired_parts(system, other):
    cases = sorted(set(system) & set(other))
    return cases, [(system[c], other[c]) for c in cases]


_CELLS = [(k, p) for k in LABELS for p in LABELS + (NO_ANSWER,)]
_CELL = {c: i for i, c in enumerate(_CELLS)}


def _matrix(parts):
    """One row per case: a confusion count over _CELLS, or a round-3 tuple as written."""
    import numpy as np
    if all(isinstance(x, Counter) for x in parts):
        m = np.zeros((len(parts), len(_CELLS)))
        for i, c in enumerate(parts):
            for cell, n in c.items():
                if cell in _CELL:
                    m[i, _CELL[cell]] = n
        return m
    return np.array([list(x) for x in parts], dtype=float)


def _vec_macro_f1(m):
    import numpy as np
    scores, present = [], []
    for cl in LABELS:
        tp = m[:, _CELL[(cl, cl)]]
        total = sum(m[:, _CELL[(cl, p)]] for p in LABELS + (NO_ANSWER,))
        fp = sum(m[:, _CELL[(k, cl)]] for k in LABELS if k != cl)
        f1 = np.where(tp > 0, 2 * tp / np.maximum(2 * tp + fp + (total - tp), 1e-300), 0.0)
        scores.append(f1)
        present.append(total > 0)
    s, pr = np.array(scores), np.array(present)
    k = pr.sum(axis=0)
    return np.where(k >= 2, (s * pr).sum(axis=0) / np.maximum(k, 1), np.nan)


def _vec_precision(m):
    import numpy as np
    said = sum(m[:, _CELL[(k, p)]] for k in LABELS for p in MOVEMENTS)
    right = sum(m[:, _CELL[(p, p)]] for p in MOVEMENTS)
    return np.where(said > 0, right / np.maximum(said, 1e-300), np.nan)


def _vec_recall(m):
    import numpy as np
    moved = sum(m[:, _CELL[(k, p)]] for k in MOVEMENTS for p in LABELS + (NO_ANSWER,))
    right = sum(m[:, _CELL[(k, k)]] for k in MOVEMENTS)
    return np.where(moved > 0, right / np.maximum(moved, 1e-300), np.nan)


def _vec_coverage(m):
    import numpy as np
    moved = sum(m[:, _CELL[(k, p)]] for k in MOVEMENTS for p in LABELS + (NO_ANSWER,))
    said = sum(m[:, _CELL[(k, p)]] for k in MOVEMENTS for p in MOVEMENTS)
    return np.where(moved > 0, said / np.maximum(moved, 1e-300), np.nan)


def _vec_good_rate(m):
    import numpy as np
    return np.where(m[:, 1] > 0, m[:, 0] / np.maximum(m[:, 1], 1e-300), np.nan)


def _vector(fn):
    """The numpy form of a figure, for the resampling loops; None for any other statistic."""
    return {macro_f1: _vec_macro_f1, movement_precision: _vec_precision, movement_recall: _vec_recall,
            coverage: _vec_coverage, good_rate: _vec_good_rate}.get(fn)


def _pair_bca(fn, paired, alpha, resamples=None):
    """BCa of the paired difference: each case's part is its (system, other) pair, summed per arm. The
    resamples run in numpy for the scorer's own figures, and in Python for any other statistic."""
    n = len(paired)
    vec = _vector(fn)
    if vec is not None and n >= 2:
        return _pair_bca_numpy(fn, vec, paired, alpha, resamples)

    def stat(combined):
        return None if combined is None else combined

    def diff_of_weights(w):
        a = fn(_combine([p[0] for p in paired], w))
        b = fn(_combine([p[1] for p in paired], w))
        return None if a is None or b is None else a - b
    estimate = diff_of_weights([1] * n)
    if estimate is None or n < 2:
        return estimate, None, None, 0.0
    draws, undefined = [], 0.0
    for w, prob in resamples_of(n, resamples=resamples):
        v = diff_of_weights(w)
        if v is None:
            undefined += prob
        else:
            draws.append((v, prob))
    if not draws:
        return estimate, None, None, undefined
    draws.sort()
    mass = sum(p for _, p in draws)
    below = sum(p for v, p in draws if v < estimate) + 0.5 * sum(p for v, p in draws if v == estimate)
    z0 = _norm_ppf(min(max(below / mass, 1e-9), 1 - 1e-9))
    jack = [diff_of_weights([0 if j == i else 1 for j in range(n)]) for i in range(n)]
    jack = [j for j in jack if j is not None]
    mean = sum(jack) / len(jack) if jack else estimate
    num = sum((mean - j) ** 3 for j in jack)
    den = 6 * (sum((mean - j) ** 2 for j in jack) ** 1.5)
    a = num / den if den else 0.0

    def bound(p):
        z = _norm_ppf(p)
        target = _norm_cdf(z0 + (z0 + z) / (1 - a * (z0 + z))) * mass
        run = 0.0
        for v, pr in draws:
            run += pr
            if run >= target:
                return v
        return draws[-1][0]
    return estimate, bound(alpha / 2), bound(1 - alpha / 2), undefined


def _pair_bca_numpy(fn, vec, paired, alpha, resamples):
    """The same BCa as _pair_bca's loop, with every resample's sums taken at once."""
    import numpy as np
    n = len(paired)
    a_m, b_m = _matrix([p[0] for p in paired]), _matrix([p[1] for p in paired])

    def diff(weights):
        w = np.asarray(weights, dtype=float)
        if w.ndim == 1:
            w = w[None, :]
        return vec(w @ a_m) - vec(w @ b_m)
    estimate = float(diff([1] * n)[0])
    if math.isnan(estimate):
        return None, None, None, 0.0
    draws = resamples_of(n, resamples=resamples)
    w = np.array([d[0] for d in draws], dtype=float)
    prob = np.array([d[1] for d in draws])
    values = diff(w)
    ok = ~np.isnan(values)
    undefined = float(prob[~ok].sum())
    if not ok.any():
        return estimate, None, None, undefined
    values, prob = values[ok], prob[ok]
    order = np.argsort(values, kind="stable")
    values, prob = values[order], prob[order]
    mass = prob.sum()
    below = prob[values < estimate].sum() + 0.5 * prob[values == estimate].sum()
    z0 = _norm_ppf(min(max(below / mass, 1e-9), 1 - 1e-9))
    jack = diff(np.ones((n, n)) - np.eye(n))
    jack = jack[~np.isnan(jack)]
    mean = jack.mean() if jack.size else estimate
    num = float(((mean - jack) ** 3).sum())
    den = 6 * float(((mean - jack) ** 2).sum()) ** 1.5
    a = num / den if den else 0.0
    cum = np.cumsum(prob)

    def bound(p):
        z = _norm_ppf(p)
        target = _norm_cdf(z0 + (z0 + z) / (1 - a * (z0 + z))) * mass
        idx = int(np.searchsorted(cum, target - 1e-15))
        return float(values[min(idx, len(values) - 1)])
    return estimate, bound(alpha / 2), bound(1 - alpha / 2), undefined


def _pair_jackknife_lower(fn, paired, alpha):
    n = len(paired)

    def diff(w):
        a = fn(_combine([p[0] for p in paired], w))
        b = fn(_combine([p[1] for p in paired], w))
        return None if a is None or b is None else a - b
    estimate = diff([1] * n)
    loo = [diff([0 if j == i else 1 for j in range(n)]) for i in range(n)]
    if estimate is None or n < 3 or any(x is None for x in loo):
        return None
    mean = sum(loo) / n
    se = math.sqrt((n - 1) / n * sum((x - mean) ** 2 for x in loo))
    return estimate - _t_ppf(1 - alpha, n - 1) * se


def _permutation_p_numpy(vec, paired, *, resamples=None, seed=SEED):
    """permutation_p's sign flips with every arrangement's sums taken at once."""
    import numpy as np
    n = len(paired)
    a_m, b_m = _matrix([p[0] for p in paired]), _matrix([p[1] for p in paired])
    observed = float(vec(np.ones((1, n)) @ a_m)[0] - vec(np.ones((1, n)) @ b_m)[0])
    if math.isnan(observed):
        return None
    if 2 ** n <= EXACT_LIMIT:
        flips = np.array(list(itertools.product((0.0, 1.0), repeat=n)))
    else:
        rng = random.Random(seed)
        total = RESAMPLES if resamples is None else resamples
        flips = np.array([[1.0 if rng.random() < 0.5 else 0.0 for _ in range(n)] for _ in range(total)])
    sys_sum = (1 - flips) @ a_m + flips @ b_m
    other_sum = flips @ a_m + (1 - flips) @ b_m
    values = vec(sys_sum) - vec(other_sum)
    hits = np.isnan(values) | (values >= observed - 1e-12)
    return float(hits.sum()) / len(flips)


def test_claim(name, fn, system, other, k, *, extra=None, resamples=None):
    """One claim on the paired parts: the BCa (one-sided at alpha), the jackknife cross-check and the
    permutation p, each at the claim's alpha; `extra` the precision claims' recall and coverage figures."""
    alpha = alpha_for(k)
    cases, paired = _paired_parts(system, other)
    estimate, lower, _, undefined = _pair_bca(fn, paired, 2 * alpha, resamples=resamples)
    jack = _pair_jackknife_lower(fn, paired, alpha)
    vec = _vector(fn)
    p = (_permutation_p_numpy(vec, paired, resamples=resamples) if vec is not None
         else permutation_p(_paired_stat(fn), paired, resamples=resamples))
    out = {"claim": name, "difference": estimate, "lower": lower, "jackknife_lower": jack, "permutation_p": p,
           "alpha": alpha, "undefined_mass": undefined, "cases": len(cases),
           "indicator": name in INDICATORS}
    ok = (estimate is not None and lower is not None and jack is not None and p is not None
          and lower > 0 and jack > 0 and p <= alpha)
    for label, efn in (extra or {}).items():
        e_est, _, e_upper, e_undef = _pair_bca(efn, paired, 2 * alpha, resamples=resamples)
        out[label + "_difference"] = e_est
        out[label + "_upper"] = e_upper
        ok = ok and e_est is not None and e_upper is not None and e_upper >= 0
    out["shown"] = bool(ok) and not out["indicator"]
    return out


def headline(by_case, subsets):
    return {c: rows for c, rows in by_case.items() if subsets.get(c) in HEADLINE_SUBSETS}


def report(key_rows, arms, subsets, k, *, resamples=None):
    """The positions figures of every arm on the headline cases, the floors, R apart, the claims."""
    by_arm = {arm: {c: counts(rows) for c, rows in pairs(key_rows, preds).items()} for arm, preds in arms.items()}
    head = {arm: headline(parts, subsets) for arm, parts in by_arm.items()}
    first = next(iter(head))
    rows_head = [(r["label"], r["label"]) for r in key_rows if subsets.get(r["case_id"]) in HEADLINE_SUBSETS]
    shaped = sum(1 for c in head[first] if subsets.get(c) == "S")
    out = {"arms": {}, "floors": floors(rows_head), "claims": {},
           "s_share": shaped / len(head[first]) if head[first] else None,
           "tolerance": {"system": SYSTEM_TOLERANCE, "key": KEY_TOLERANCE}}
    for arm, parts in head.items():
        out["arms"][arm] = {}
        names = sorted(parts)
        for name, fn in FIGURES.items():
            est, lo, hi, undefined = bca(fn, [parts[c] for c in names], resamples=resamples)
            out["arms"][arm][name] = {"value": est, "lower": lo, "upper": hi, "undefined_mass": undefined}
        real = [p for c, p in by_arm[arm].items() if subsets.get(c) == "R"]
        out["arms"][arm]["real_indicator"] = ({n: fn(_combine(real, [1] * len(real))) for n, fn in FIGURES.items()}
                                              if real else None)
        out["arms"][arm]["n_rows"] = sum(sum(p.values()) for p in parts.values())
        out["arms"][arm]["n_cases"] = len(parts)
        # Every arm's no_answer count, the system's included (D-419 gap 13).
        out["arms"][arm]["no_answer"] = sum(n for p in parts.values() for (key, pred), n in p.items() if pred == NO_ANSWER)
    for name, feature, figure, other in CLAIMS:
        if feature == "positions" and "system" in head and other in head:
            extra = {"recall": movement_recall, "coverage": coverage} if name in PRECISION_CLAIMS else None
            out["claims"][name] = test_claim(name, FIGURES[figure], head["system"], head[other], k, extra=extra,
                                             resamples=resamples)
    return out


def round3_report(open_issues, pythons, sheets, subsets, k, *, resamples=None):
    out = {"arms": {}, "claims": {}}
    head = {}
    for arm in pythons:
        parts = round3_parts(open_issues, pythons[arm], sheets.get(arm) or [])
        head[arm] = {c: p for c, p in parts.items() if subsets.get(c) in HEADLINE_SUBSETS}
        names = sorted(head[arm])
        figures = round3_figures(head[arm])
        _, lo, hi, _ = bca(good_rate, [head[arm][c] for c in names], resamples=resamples)
        figures["good_rate_interval"] = [lo, hi]
        real = {c: p for c, p in parts.items() if subsets.get(c) == "R"}
        figures["real_indicator"] = round3_figures(real) if real else None
        out["arms"][arm] = figures
    if "system" in head and "B1" in head:
        out["claims"]["C5"] = test_claim("C5", good_rate, head["system"], head["B1"], k, resamples=resamples)
    return out


def _committed_power_code():
    """The committed tools/negotiation_power.py: (its SHA-256 with CRLF made LF, its ASSUMED), or None."""
    text = committed_text(ROOT, "tools/negotiation_power.py")
    if text is None:
        return None
    import ast
    assumed = None
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "ASSUMED" for t in node.targets):
            assumed = ast.literal_eval(node.value)
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest(), assumed


def c1_status(power_record, freeze, *, committed_code=None):
    """"claim" or "indicator", from C1's committed power record at the frozen headline count, or why
    scoring is refused (D-419, D-430):
    - the record must name this set, its headline case count, alpha 0.025 and at least MIN_POWER_SIMS sets;
    - its code digest and assumptions must be the committed tools/negotiation_power.py's (`committed_code`,
      (sha256, ASSUMED));
    - C1 is a claim only when its power is at least 0.8 at every correlation simulated; any one below makes
      it an indicator.
    The record of opening 1 governs both openings."""
    if not isinstance(power_record, dict):
        return None, "no committed power record for C1"
    if committed_code is None or power_record.get("code_sha256") != committed_code[0] \
            or power_record.get("assumed") != committed_code[1]:
        return None, "C1's power record is not of the committed simulation code and its assumptions"
    head = sum(1 for s in freeze["subsets"].values() if s in HEADLINE_SUBSETS)
    if power_record.get("set_sha256") != freeze["set_sha256"] or power_record.get("cases") != head:
        return None, "C1's power record is not for this frozen set and its headline count"
    if (power_record.get("sims") or 0) < MIN_POWER_SIMS or power_record.get("alpha") != alpha_for(1):
        return None, "C1's power record has fewer than %d sets or another alpha" % MIN_POWER_SIMS
    values = [v.get("C1") for v in (power_record.get("power") or {}).values()]
    if not values or any(v is None for v in values):
        return None, "C1's power record holds no C1 figure"
    return ("claim" if all(v >= 0.8 for v in values) else "indicator"), None


def refuse_freeze(freeze):
    """Why a FREEZE file cannot be scored, or None: a dry run, or a pass with no embedding test."""
    if freeze.get("dry_run") is not False or not freeze.get("embedding"):
        return "the freeze is a dry run or ran with no embedding test"
    return None


CONFIGURATION_FIELDS = ("execution_manifest_sha256", "b1_prompts_sha256", "b1_model_digests", "cloud_prompts_sha256",
                        "cloud_model_id", "power_record_sha256")


def refuse_records(configuration, *, b1=None, cloud=None, b1_measurement=None, system_cases=(), frozen_cases=(),
                   failed_cases=(), power_sha256=None):
    """Why the arms' own records do not match the configuration of the opening line, or None (D-419 gap 5,
    D-430 item 3). It fails closed: a configuration missing any field, a missing arm, B1's answers without
    their pass's measurement, cloud answers with no model id, each refuse."""
    missing = [f for f in CONFIGURATION_FIELDS if not configuration.get(f)]
    if missing:
        return "the configuration lacks %s" % ", ".join(missing)
    if b1 is None or cloud is None:
        return "an arm is missing: %s" % ", ".join(n for n, a in (("B1", b1), ("cloud", cloud)) if a is None)
    if b1_measurement is None:
        return "B1's answers come without their pass's measurement"
    if not cloud.get("model_id"):
        return "the cloud reference's answers carry no model id"
    if power_sha256 != configuration.get("power_record_sha256"):
        return "C1's power record is not the configuration's"
    if b1 is not None and b1.get("prompts_sha256") != configuration.get("b1_prompts_sha256"):
        return "B1's answers are not of the configuration's prompts file"
    if cloud is not None and cloud.get("prompts_sha256") != configuration.get("cloud_prompts_sha256"):
        return "the cloud reference's answers are not of the configuration's prompts file"
    if cloud is not None and cloud.get("model_id") != configuration.get("cloud_model_id"):
        return "the cloud reference's model is not the configuration's"
    if b1_measurement is not None:
        digests = {g: m.get("digest") for g, m in (b1_measurement.get("models") or {}).items()}
        if digests != configuration.get("b1_model_digests"):
            return "B1's model digests are not the configuration's"
    missing = sorted(set(frozen_cases) - set(system_cases) - set(failed_cases))
    if missing:
        return "no system run for frozen case(s) %s, and no status record names a failure" % ", ".join(missing)
    return None


def case_units(set_root, case_id):
    """([(unit slug, text)] of the case's last round, the declared closed slugs) from the frozen set."""
    import sys as _sys
    if str(ROOT / "scripts") not in _sys.path:
        _sys.path.insert(0, str(ROOT / "scripts"))
    import pairing_map
    for sub in ("real", "synthetic"):
        folder = Path(set_root) / sub
        for case_dir in (folder.iterdir() if folder.is_dir() else []):
            m_path = case_dir / "case_manifest.json"
            if not m_path.is_file():
                continue
            manifest = json.loads(m_path.read_text(encoding="utf-8"))
            if manifest.get("case_id") != case_id:
                continue
            last = max(manifest["rounds"], key=lambda r: r["sequence"])
            units = []
            for doc_id in last["document_ids"]:
                text = (case_dir / "context" / (doc_id + ".md")).read_text(encoding="utf-8")
                units += [(u["unit_id"].split("-", 1)[-1], u["text"]) for u in pairing_map.split_units(text, document_id=doc_id)]
            closed = {s for i in manifest["issues"] for s in i.get("closed_units") or []}
            return units, closed
    return [], set()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--opening", type=int, required=True)
    parser.add_argument("--freeze", type=Path, required=True, help="the set's FREEZE.json")
    parser.add_argument("--set", type=Path, required=True, help="the frozen set's folder (round-3 units)")
    parser.add_argument("--configuration", type=Path, required=True, help="the configuration record named in the opening line")
    parser.add_argument("--power", type=Path, default=ROOT / POWER_RECORD, help="C1's committed power record")
    parser.add_argument("--system-run", type=Path, action="append", default=[],
                        help="each system entry's run folder (a folder, one per case): one holding audit/multi_round.json, "
                             "or a failed entry's, whose bundle holds its case manifest and FINAL_STATUS.json")
    parser.add_argument("--b1-answers", type=Path)
    parser.add_argument("--b1-measurement", type=Path)
    parser.add_argument("--cloud-answers", type=Path)
    parser.add_argument("--sheet", type=Path, action="append", default=[], help="ARM=settled round-3 sheet (JSON list)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    config_sha = hashlib.sha256(args.configuration.read_bytes()).hexdigest()
    why = (refuse_freeze(freeze)
           or refuse_without_opening(args.opening, freeze["set_sha256"], config_sha, text=committed_text(ROOT, OPENINGS)))
    try:
        rel = args.power.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        rel = None
    # The power record is read from the commit, not from the working tree (D-430 item 6).
    power_text = committed_text(ROOT, rel) if rel else None
    power_record = json.loads(power_text) if power_text else None
    power_sha = hashlib.sha256(power_text.replace("\r\n", "\n").encode("utf-8")).hexdigest() if power_text else None
    status, power_why = c1_status(power_record, freeze, committed_code=_committed_power_code())
    why = why or power_why
    if why:
        raise SystemExit("refused: " + why)
    configuration = json.loads(args.configuration.read_text(encoding="utf-8"))
    for run in args.system_run:
        if _seal_of(run) not in set(configuration.get("execution_manifest_sha256") or []):
            raise SystemExit("refused: a system run's bundle is not the configuration's: %s" % run)
    b1 = json.loads(args.b1_answers.read_text(encoding="utf-8")) if args.b1_answers else None
    cloud = json.loads(args.cloud_answers.read_text(encoding="utf-8")) if args.cloud_answers else None
    measurement = json.loads(args.b1_measurement.read_text(encoding="utf-8")) if args.b1_measurement else None
    arms, suggestions = {"system": {}}, {"system": {}}
    system_cases = set()
    why, failures = refuse_system_runs(args.system_run)
    if why:
        raise SystemExit("refused: " + why)
    failed = set(failures)
    for run in args.system_run:
        if not (Path(run) / "audit" / "multi_round.json").is_file():
            continue
        answers = system_answers(run)
        arms["system"].update(answers)
        suggestions["system"].update(system_suggestions(run))
        system_cases |= {k[0] for k in answers}
    why = refuse_records(configuration, b1=b1, cloud=cloud, b1_measurement=measurement, system_cases=system_cases,
                         frozen_cases=freeze["subsets"], failed_cases=failed, power_sha256=power_sha)
    if why:
        raise SystemExit("refused: " + why)
    if b1:
        arms["B1"], suggestions["B1"] = reply_answers(b1), reply_suggestions(b1)
    if cloud:
        arms["cloud"], suggestions["cloud"] = reply_answers(cloud), reply_suggestions(cloud)
    units = {c: case_units(args.set, c) for c in freeze["subsets"]}
    suggestions = {arm: apply_closed_rule(s, units) for arm, s in suggestions.items()}
    sheets = {}
    for item in args.sheet:
        arm, _, path = str(item).partition("=")
        sheets[arm] = json.loads(Path(path).read_text(encoding="utf-8"))
    positions = report(freeze["movement_key"], arms, freeze["subsets"], args.opening)
    if status != "claim":
        positions["claims"]["C1"].update(indicator=True, shown=False)
    round3 = round3_report([tuple(x) for x in freeze["open_issues"]], suggestions, sheets, freeze["subsets"], args.opening)
    # Every failed entry scores no_answer on all its rows (no system answer is read for it; its rows stay
    # in the frozen key), counted and named apart by kind (D-451). Only an infrastructure failure can
    # call for opening 2.
    result = {"c1_status": status, "positions": positions, "round3": round3,
              "system_failures": failure_report(failures, freeze["movement_key"]),
              "opening_2_may_be_called": any(f["kind"] == "infrastructure" for f in failures.values())}
    args.out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"c1_status": status, "C1_shown": positions["claims"]["C1"]["shown"]}))
    return 0


# A failed entry's kind, read off the entry's own records (D-437 item 1, D-451, D-456). It is
# INFRASTRUCTURE only for a cause that belongs to the runner or the machine, each named here:
# - the controller's own failure records beside FINAL_STATUS.json (written by tools/ordinary_final_cloud.py:
#   the launch, ssh, the upload, the collection, a lost instance or its deadline):
INFRASTRUCTURE_RECORDS = ("controller_failure.json", "launch_recovery_failure.json", "collection_failure.json")
# - no result from the runner at all (the instance was lost before it wrote evidence/result.json);
# - the runner's terminal error of the HOST running out of memory (its recorded error type). A CUDA
#   out-of-memory error is the system's own (the lead's ruling under D-456): its batch, context and model
#   choices set GPU memory, and PREFILL-E records it as a named failure of the run:
# read by its recorded identity (`ordinary_final_run.failure_identity`: error_type and error_module, the
# class's own module), so a pipeline class that happens to share a name is not excused:
INFRASTRUCTURE_ERRORS = (("MemoryError", "builtins"),)
# Everything else is the SYSTEM'S OWN: any other terminal error (a pipeline exception), `backend_failure`
# (a model call that failed inside the pipeline), `semantic_incomplete`, `required_contract_failure`,
# `pipeline_not_completed`, the multi-round reasons. Either kind scores no_answer on every row of its case
# and is counted and named apart; neither refuses the scoring, so the system's own failures are never
# left unscored (D-451). Only infrastructure can call for opening 2 (section 7 of the plan).
COMPLETED_STATUS = "ORDINARY_FINAL_CLOUD_RUN_COMPLETED"
FAILED_STATUS = "ORDINARY_FINAL_CLOUD_RUN_FAILED"


def failure_report(failures, movement_key):
    """{infrastructure, own_reasons}: per kind the cases, their recorded causes and their rows of the frozen
    key, every one of which scores no_answer (D-456 item 1)."""
    out = {}
    for kind in ("infrastructure", "own_reasons"):
        cases = sorted(c for c, f in failures.items() if f["kind"] == kind)
        out[kind] = {"cases": cases, "causes": {c: failures[c]["reasons"] for c in cases},
                     "no_answer_rows": sum(1 for r in movement_key if r["case_id"] in cases)}
    return out


def failed_entry_kind(status, controller_records=()):
    """(kind, why) of an entry's FINAL_STATUS record and the controller's failure records found beside it:
    kind `infrastructure` or `own_reasons` for an entry failed or stopped, with why naming its cause; kind
    None, with why, for records that name no failed entry (none, a completed run, a state neither failed
    nor stopped). A controller failure record is infrastructure even with no FINAL_STATUS.json."""
    infra = sorted(r for r in controller_records if r in INFRASTRUCTURE_RECORDS)
    beside = ("; controller record %s beside them" % ", ".join(infra)) if infra else ""
    if isinstance(status, dict) and status.get("status") == COMPLETED_STATUS:
        return None, "its FINAL_STATUS.json says %s" % COMPLETED_STATUS
    if not isinstance(status, dict):
        if infra:
            return "infrastructure", "controller record " + ", ".join(infra) + ", no FINAL_STATUS.json"
        return None, "no FINAL_STATUS.json"
    if status.get("status") != FAILED_STATUS:
        return None, "its FINAL_STATUS.json says %s, not %s" % (status.get("status"), FAILED_STATUS)
    completion, result = status.get("pipeline_completion"), status.get("remote_result")
    # A FAILED status names a failed entry whatever the pipeline state says (a run can reach its end,
    # state "completed", and still fail its assessment, as with semantic_incomplete): its kind is then
    # infrastructure only for a cause listed above, else the system's own (nego-plan-check on f268d233).
    state = (completion or {}).get("state") if completion else None
    reasons = (result or {}).get("reasons") or []
    error = status.get("terminal_error")
    if isinstance(error, dict) and (error.get("error_type"), error.get("error_module")) in INFRASTRUCTURE_ERRORS:
        return "infrastructure", "the host ran out of memory (%s.%s)%s" % (error["error_module"], error["error_type"], beside)
    if error:
        where = error.get("error_origin") or error.get("error_frame") if isinstance(error, dict) else None
        return "own_reasons", "a pipeline exception (%s at %s)%s" % (
            error.get("error_type") if isinstance(error, dict) else "unrecorded", where or "an unrecorded place", beside)
    if reasons:
        # The runner's own assessment names why it failed: that decides the kind, and a controller
        # record (written later, at collection) is listed beside it, never in its place (D-456 item 3).
        return "own_reasons", "%s (pipeline state %s)%s" % (", ".join(reasons), state, beside)
    if infra:
        return "infrastructure", "controller record " + ", ".join(infra)
    if result is None:
        return "infrastructure", "no runner result (the instance lost before its result)"
    return "own_reasons", "no reason recorded (pipeline state %s)" % state


def refuse_system_runs(runs):
    """(why, failures): why the --system-run arguments cannot be read, or None, and {case: {kind, reasons}}
    of the failed entries (D-437 item 1, D-451). Each is a run folder; at most one per case; a run without
    its case record is a failed entry only when its bundle's case manifest and FINAL_STATUS.json name a
    failed or stopped state, of either kind; and a case with a case record in any run given is never also
    a failed entry."""
    seen, recorded, failed = {}, set(), {}
    for run in runs:
        run = Path(run)
        if not run.is_dir():
            return "a system run is not a run folder: %s" % run, {}
        record = run / "audit" / "multi_round.json"
        case = _case_of(run)
        if record.is_file():
            try:
                case = json.loads(record.read_text(encoding="utf-8")).get("manifest", {}).get("case_id") or case
            except ValueError:
                return "a system run's case record cannot be read: %s" % run, {}
            recorded.add(case)
        else:
            if not case:
                return "a system run has neither its case record nor its case manifest: %s" % run, {}
            kind, why = failed_entry_kind(_final_status(run), _controller_records(run))
            if kind is None:
                return "a system run has no case record and is no failed entry, since %s: %s" % (why, run), {}
            failed[case] = {"kind": kind, "reasons": why}
        seen.setdefault(case, []).append(str(run))
    both = sorted(c for c in failed if c in recorded)
    if both:
        return "case(s) %s have a case record in a run given and are named failed" % ", ".join(both), {}
    twice = sorted(c for c, r in seen.items() if len(r) > 1)
    if twice:
        return "two system runs for case %s: %s" % (twice[0], " and ".join(seen[twice[0]])), {}
    return None, failed


def _case_of(run):
    """The case id of the case manifest a run folder or its bundle holds, or None."""
    for folder in [Path(run)] + list(Path(run).parents)[:4]:
        if (folder / "case_manifest.json").is_file():
            return json.loads((folder / "case_manifest.json").read_text(encoding="utf-8")).get("case_id")
    return None


# The entry's root, where the controller writes FINAL_STATUS.json and its own records: the folder that
# holds both of these, never one inside `downloaded/` (what came back from the instance, D-456 item 1).
ROOT_MARKERS = ("collection_integrity.json", "seal.json")


def entry_root(run):
    """The entry root of a run folder (itself or one of its parents), or None."""
    for folder in [Path(run)] + list(Path(run).parents)[:6]:
        if "downloaded" in folder.parts:
            continue
        if all((folder / m).is_file() for m in ROOT_MARKERS):
            return folder
    return None


def _final_status(run):
    root = entry_root(run)
    if root is None or not (root / "FINAL_STATUS.json").is_file():
        return None
    return json.loads((root / "FINAL_STATUS.json").read_text(encoding="utf-8"))


def _controller_records(run):
    """The controller's failure records at the entry root, and only there."""
    root = entry_root(run)
    return [n for n in INFRASTRUCTURE_RECORDS if root is not None and (root / n).is_file()]


def _seal_of(run):
    for folder in [Path(run)] + list(Path(run).parents)[:4]:
        if (folder / "seal.json").is_file():
            return json.loads((folder / "seal.json").read_text(encoding="utf-8")).get("execution_manifest_sha256")
    return None


if __name__ == "__main__":
    raise SystemExit(main())
