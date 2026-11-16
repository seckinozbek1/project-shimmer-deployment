"""The effect of INFRA-055 (a well-formed "does not contradict" answer kept, D-652, D-657, D-669) on ContraDoc,
read from saved run folders only (D-652 item 1 as amended). No model, no provider, no answer key, no label, no
score: it counts what the saved replies said and what today's rule would keep, and bounds how many document labels
the fix could move.

    py -3.12 -X utf8 tools/contradoc_ok_effect.py --out OUT.json RUN_DIR [RUN_DIR ...]

RUN_DIR is a run folder holding audit/pairing_map.json and audit/model_replies/. For every judging call the
pairing map names (`judging_calls`), the reply record's text is read by tools/answer_form.last_object (the one
tolerant JSON rule), and every item of relation `contradiction` is classed by its `record_verdict`:
- irregular: unchanged by INFRA-055 (INFRA-046 and INFRA-047 still apply);
- ok: refused before INFRA-055 (CONTRADICTION_NOT_IRREGULAR), kept now when it names no second unit and any
  quote_b it writes stands in the unit. With no quote and no quote_b it is kept for certain; with one, the
  unit text decides, which the run folder does not hold, so it is counted apart (`ok_kept_if_quotes_stand`);
- anything else (missing, unknown): refused before and now.

Document level, two upper bounds on label changes (a bound, since the irregular side reads replies, not the bus):
- `each` (detection_dev, ContraDoc's declared reading): a document can turn CLEAR only when every unit of its
  unit list has an ok answer kept now and no unit has an irregular contradiction answer;
- v2_primary (the frozen reading, D-476): a refused ok answer made the document ABSTAIN where silence reads "not
  contradictory" (benchmark/adapters/common/mapping.py), so a document can move only when it holds an ok answer
  and no irregular one.
Shares carry exact (Clopper-Pearson) 95 percent intervals. Counts only: no document id, unit id or text.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import answer_form as af  # noqa: E402

SCHEMA = "contradoc-ok-effect-v1"
CONTRADICTION = "contradiction"
IRREGULAR, OK = "irregular", "ok"
# paired_review.CONTRADICTION_NOT_IRREGULAR, held equal by check 485 (the scripts are not imported here).
CONTRADICTION_NOT_IRREGULAR = "contradiction not marked irregular"
OK_KEPT, OK_IF_QUOTES, OK_REFUSED = "ok_kept_now", "ok_kept_if_quotes_stand", "ok_refused_now"
REFUSAL_LISTS = ("absence_refused", "uncomputable_refused", "relation_refusals")
Z95 = 0.05


def _binom_cdf(k, n, p):
    """P(X <= k) for X ~ Binomial(n, p), summed in log space."""
    if p <= 0:
        return 1.0
    if p >= 1:
        return 0.0 if k < n else 1.0
    total = 0.0
    for i in range(0, k + 1):
        total += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                          + i * math.log(p) + (n - i) * math.log1p(-p))
    return min(1.0, total)


def _bisect(fn, target, lo=0.0, hi=1.0):
    """The p in [lo, hi] where the decreasing fn(p) crosses target."""
    for _ in range(200):
        mid = (lo + hi) / 2
        if fn(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def exact_interval(k, n, alpha=Z95):
    """Clopper-Pearson interval of k successes in n, or None for n == 0."""
    if n <= 0:
        return None
    lower = 0.0 if k == 0 else _bisect(lambda p: _binom_cdf(k - 1, n, p), 1 - alpha / 2)
    upper = 1.0 if k == n else _bisect(lambda p: _binom_cdf(k, n, p), alpha / 2)
    return [round(lower, 4), round(upper, 4)]


def share(k, n):
    return {"count": k, "of": n, "share": round(k / n, 4) if n else None, "interval95": exact_interval(k, n)}


def verdict_of(item):
    return str(item.get("record_verdict") or "").strip().lower()


def ok_class(item):
    """What INFRA-055 does with an ok contradiction answer, without the unit text: refused when it names a
    second unit (paired_review: CONTRADICTION_SECOND_UNIT_NOT_CHECKED), kept when it writes no quote and no
    quote_b, else kept only when its quotes stand in the unit (counted apart)."""
    if str(item.get("compared_unit_id") or ""):
        return OK_REFUSED
    quotes = [item.get(f) for f in ("quote", "quote_b")]
    if any(isinstance(q, str) and q.strip() for q in quotes):
        return OK_IF_QUOTES
    return OK_KEPT


def each_can_turn_clear(units, ok_units, irregular_units):
    """ContraDoc's `each` reading: CLEAR only when every unit holds, so only when every unit of the list has an ok
    answer kept now and no unit an irregular one (a unit with both is a conflict, never CLEAR)."""
    return bool(units) and set(units) <= set(ok_units) and not irregular_units


def v2_can_move(ok_units, irregular_units):
    """v2_primary: a refused ok answer was a refusal, ABSTAIN; kept, it is "not contradictory" unless an irregular
    record stands in the document."""
    return bool(ok_units) and not irregular_units


def _items(record):
    reply = (record or {}).get("reply")
    text = reply.get("text") if isinstance(reply, dict) else None
    value, why, _ = af.last_object(text)
    if value is None:
        return None, why
    items = value.get("items")
    return ([i for i in items if isinstance(i, dict)] if isinstance(items, list) else []), None


def _records(run_dir):
    out = {}
    folder = Path(run_dir) / "audit" / "model_replies"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if record.get("call_id"):
            out[record["call_id"]] = record
    return out


def read_run(run_dir):
    """{documents: [...per-document counts...]} of one run folder; refused when it holds no pairing map."""
    path = Path(run_dir) / "audit" / "pairing_map.json"
    if not path.is_file():
        raise ValueError("a run folder holds audit/pairing_map.json")
    pairing = json.loads(path.read_text(encoding="utf-8"))
    records = _records(run_dir)
    documents = []
    for entry in pairing.values():
        if not isinstance(entry, dict):
            continue
        units = [u.get("unit_id") for u in entry.get("units") or [] if u.get("unit_id")]
        doc = {"units": len(units), "judging_calls": 0, "calls_unread": 0, "contradiction_answers": 0,
               "irregular": 0, "ok": 0, "other_verdict": 0, OK_KEPT: 0, OK_IF_QUOTES: 0, OK_REFUSED: 0,
               "refused_not_irregular_saved": 0, "refusals_saved": 0}
        ok_units, irregular_units = set(), set()
        for call in entry.get("judging_calls") or []:
            doc["judging_calls"] += 1
            items, why = _items(records.get(call.get("call_id")))
            if items is None:
                doc["calls_unread"] += 1
                continue
            for item in items:
                if str(item.get("relation") or "") != CONTRADICTION:
                    continue
                doc["contradiction_answers"] += 1
                verdict = verdict_of(item)
                if verdict == IRREGULAR:
                    doc["irregular"] += 1
                    irregular_units.add(call.get("unit_id"))
                elif verdict == OK:
                    doc["ok"] += 1
                    kind = ok_class(item)
                    doc[kind] += 1
                    if kind != OK_REFUSED:
                        ok_units.add(call.get("unit_id"))
                else:
                    doc["other_verdict"] += 1
        for name in REFUSAL_LISTS:
            for refusal in entry.get(name) or []:
                doc["refusals_saved"] += 1
                if refusal.get("reason") == CONTRADICTION_NOT_IRREGULAR:
                    doc["refused_not_irregular_saved"] += 1
        doc["each_can_turn_clear"] = each_can_turn_clear(units, ok_units, irregular_units)
        doc["v2_can_move"] = v2_can_move(ok_units, irregular_units)
        documents.append(doc)
    return {"run": Path(run_dir).name, "documents": documents}


COUNT_FIELDS = ("units", "judging_calls", "calls_unread", "contradiction_answers", "irregular", "ok", "other_verdict",
                OK_KEPT, OK_IF_QUOTES, OK_REFUSED, "refused_not_irregular_saved", "refusals_saved")


def effect(run_dirs):
    runs = [read_run(r) for r in run_dirs]
    docs = [d for r in runs for d in r["documents"]]
    totals = {f: sum(d[f] for d in docs) for f in COUNT_FIELDS}
    n_docs = len(docs)
    return {
        "schema": SCHEMA, "runs": len(runs), "documents": n_docs, "totals": totals,
        "ok_share_of_contradiction_answers": share(totals["ok"], totals["contradiction_answers"]),
        "ok_share_of_judging_calls": share(totals["ok"], totals["judging_calls"]),
        "each_can_turn_clear": share(sum(1 for d in docs if d["each_can_turn_clear"]), n_docs),
        "v2_can_move": share(sum(1 for d in docs if d["v2_can_move"]), n_docs),
        # A moved document leaves ABSTAIN, which accuracy counts wrong, for CLEAR: it can only gain.
        "accuracy_change_bound_points": {
            "each": [0.0, round(100.0 * sum(1 for d in docs if d["each_can_turn_clear"]) / n_docs, 2) if n_docs else None],
            "v2_primary": [0.0, round(100.0 * sum(1 for d in docs if d["v2_can_move"]) / n_docs, 2) if n_docs else None]},
        "reads": "saved reply records and pairing maps only; no answer key, no label, no score; counts only",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args(argv)
    value = effect(args.runs)
    args.out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"runs": value["runs"], "documents": value["documents"], "ok": value["totals"]["ok"],
                      "contradiction_answers": value["totals"]["contradiction_answers"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
