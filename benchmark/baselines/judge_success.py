"""The judge's success rule in code (D-S72, D-330): the threshold rule, the held-out gate, the test.

    tuning_thresholds(...)   each judge's threshold per benchmark on half A, by ONE rule for both
    require_opening(...)     refuses unless the held-out ledger and the tuning pass are committed
    heldout_sign_test(...)   the one-sided sign test at alpha 0.05 / 2^k, on the benchmark named first
    beside(result)           B1's figures and the D-S73 bars, written beside every result

The threshold rule. Both judges, the untrained base and the trained one, take their threshold on half A
from `choice_read.choose_threshold`, C_BAR's own rule, on rows at temperature 1: both tempered the
same way (not at all), so the comparison is of the judges, not of two calibrations. The calibration's
temperature (judge_calibration.py) is the product's, for the fresh read, and is not used here.

The held-out gate. Scoring a held-out part is refused unless `docs/loop/HELDOUT_OPENINGS.md` AS
COMMITTED (read from git, not from the working tree) has a row naming the part and the attempt, and a
tuning-pass record AS COMMITTED states `passed: true` for that attempt. The k of that row sets the alpha.
Under D-330 the judge has no held-out part today (TRAIN_JUDGE_DATA.md, the success rule); the gate and
the test stand for a reserve, should one exist.
"""
import json
import math
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = "docs/loop/HELDOUT_OPENINGS.md"
HELDOUT_BENCHMARK = "scitab"     # named in advance (D-330 item 2): ContraDoc's reach caps any gain
ALPHA = 0.05
# Written beside every result (D-330 item 5, D-S73). Settings differ from Shimmer's and are stated.
BESIDE = {
    "b1": {"scitab": {"macro_f1": 0.838, "items": 93, "what": "B1, Phi-4 bare with its own reasoning, J1 (D-277), development claims"},
           "contradoc": {"accuracy": 0.567, "items": 60, "what": "B1, Phi-4 bare with its own reasoning, J1 (D-277), development documents"}},
    "bars": {"scitab": {"macro_f1": 0.65, "what": "MACE (2026 preprint), three classes, an 8B planner and executor with a 20B verifier, "
                                                   "on the whole SciTab set; Shimmer scores development subsets"},
             "contradoc": {"accuracy": 0.681, "what": "LLaMA3.2-90B, one judge-and-quote prompt on all 891 documents (Tan et al. 2026); "
                                                       "not an agentic system; Shimmer scores development subsets"}},
    "note": "Bars from target-table (D-330), being checked by table-check; never a like-for-like claim (D-S73).",
}


def beside(result):
    return dict(result, beside=BESIDE)


def tuning_thresholds(benchmark, documents, judges, forms, keys, out, left_out, b1, cr):
    """{judge: (threshold, figures)} on half A: `judges` is {name: rows at temperature 1}, every judge
    put through the same `choose_threshold`."""
    return {name: cr.choose_threshold(benchmark, documents, rows, forms, keys, out, left_out, b1, "success_%s_%s" % (name, benchmark))
            for name, rows in sorted(judges.items())}


def committed(path, repo=ROOT, show=None):
    """`path`'s text at HEAD, or None when it is not committed."""
    if show is not None:
        return show(path)
    result = subprocess.run(["git", "-C", str(repo), "show", "HEAD:" + path], capture_output=True)
    return result.stdout.decode("utf-8") if result.returncode == 0 else None


def opening_row(ledger_text, part, attempt):
    """The ledger's row for (part, attempt): {k, alpha, ...}, or None."""
    for line in (ledger_text or "").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0] == part and cells[3] == str(attempt) and re.fullmatch(r"\d+", cells[1]):
            return {"part": part, "k": int(cells[1]), "alpha": cells[2], "attempt": cells[3], "cells": cells}
    return None


def require_opening(part, attempt, tuning_record, repo=ROOT, show=None):
    """The ledger row, or ValueError: the opening and the tuning pass must both be committed."""
    row = opening_row(committed(LEDGER, repo, show), part, attempt)
    if row is None:
        raise ValueError("no committed held-out opening for %s attempt %s in %s" % (part, attempt, LEDGER))
    record = committed(tuning_record, repo, show)
    if record is None:
        raise ValueError("the tuning-pass record is not committed: " + tuning_record)
    value = json.loads(record)
    if value.get("attempt") != str(attempt) or value.get("part") != part or value.get("passed") is not True:
        raise ValueError("the committed tuning-pass record does not show this attempt passed its tuning part")
    return row


def sign_test(wins, losses):
    """One-sided P of at least `wins` successes in wins + losses fair flips."""
    n = wins + losses
    return math.fsum(math.comb(n, i) for i in range(wins, n + 1)) / 2 ** n if n else 1.0


def heldout_sign_test(part, attempt, tuning_record, wins, losses, benchmark, repo=ROOT, show=None):
    """The held-out result on the named benchmark at alpha 0.05 / 2^k; refused before any count is used
    unless the opening and the tuning pass are committed."""
    row = require_opening(part, attempt, tuning_record, repo, show)
    if benchmark != HELDOUT_BENCHMARK:
        raise ValueError("the held-out test is on %s, named in advance" % HELDOUT_BENCHMARK)
    alpha = ALPHA / 2 ** row["k"]
    p = sign_test(wins, losses)
    return beside({"part": part, "attempt": attempt, "k": row["k"], "alpha": alpha, "wins": wins, "losses": losses, "p": p,
                   "passed": p <= alpha, "benchmark": benchmark})
