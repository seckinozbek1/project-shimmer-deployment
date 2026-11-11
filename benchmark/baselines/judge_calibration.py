"""The trained judge's calibration (D-S54 item 1, D-S62 item 5): a temperature and a threshold, fitted
on development material only, never the fresh test set and never half B.

    py -3.12 benchmark/baselines/judge_calibration.py calibrate --prompts P --run R --key K ... \
        --items I --source S --b1 B --out DIR

Reads the session's last pass (`pair_judge.finished_pass`): the trained group's decisions (`--group`,
`choice_trained` by default; `choice_direct` on a read-development file whose one group took the
adapter) on half A's
ContraDoc documents (`choice_read.halves` over the bar's items), the documents the fresh read never
counts. The fresh test is ContraDoc's, so its threshold is ContraDoc's.

The temperature. Each decision's probabilities are scaled by `choice_decision.tempered`, the one
function the read uses too, and T is the value of GRID that gives the gold answer the highest mean
log probability, a tie going to the value nearest 1. A pair's gold comes from the scorer only
(`score_corpus.marked_passages`, as `choice_read.reach` reads it): in a document with a
contradiction, the pair holding the marked passage and its partner is "contradicts", both orders;
every pair of a document with none is "does not"; every other pair of a contradiction document is
left out (the key does not say it is compatible), and so is every decision that is not one. The
counts of each are written beside the result.

The threshold. `choice_read.choose_threshold` on the tempered rows, C_BAR's own rule against the
comparator B1 group (`choice_read.comparator`). The temperature never changes which answer is top, so
it is chosen first and the threshold after it. When no value qualifies, no calibration is written and
the read cannot run: nothing falls back to a value outside the bar's grid.

Deterministic from its inputs alone (the read refits it and refuses a difference): the session's
prompts and run (half A's rows), the keys, the bar's items file, the source file (the partner
passage), the B1 folder (the comparator), and the build's items file (the staged id to source id
map). A grid, no randomness, no clock.

The output is `judge-calibration-v1` exactly (fresh_test.calibration reads it): adapter_weights_sha256
(the adapter the trained group's pass applied, from its measurement), temperature, threshold,
fitted_on_documents (SOURCE ids, read from the build's items file; a half A document with no
mapping refuses the fit), development_only. The fit's record (counts, losses) goes beside it.
"""
import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "scripts"), str(HERE.parents[1] / "tools")]

SCHEMA = "judge-calibration-v1"
GRID = tuple(round(math.exp(math.log(0.25) + k * (math.log(8.0) - math.log(0.25)) / 400), 6) for k in range(401))
MIN_ROWS = 20
BENCHMARK = "contradoc"
TRAINED_GROUP = "choice_trained"
CONTRADICTS, DOES_NOT = "contradicts", "does not"
FLOOR = 1e-12


def _cd():
    import choice_decision
    return choice_decision


def gold_probability(decision, gold, t):
    """The probability of the gold answer once `decision` is tempered at `t`."""
    tempered = _cd().tempered(decision, t)
    return next(a["probability"] for a in tempered["answers"] if a["label"] == gold)


def mean_nll(rows, t):
    return math.fsum(-math.log(max(gold_probability(d, g, t), FLOOR)) for d, g in rows) / len(rows)


def fit_temperature(rows):
    """{temperature, rows, nll_at_1, nll} over [(decision, gold label)]."""
    rows = list(rows)
    if len(rows) < MIN_ROWS:
        raise ValueError("a temperature is fitted on at least %d decisions, not %d" % (MIN_ROWS, len(rows)))
    for decision, gold in rows:
        if gold not in {a["label"] for a in decision["answers"]}:
            raise ValueError("a gold answer is not one of its decision's answers")
    best = min(GRID, key=lambda t: (round(mean_nll(rows, t), 12), abs(math.log(t))))
    return {"temperature": best, "rows": len(rows), "nll_at_1": mean_nll(rows, 1.0), "nll": mean_nll(rows, best),
            "grid": [GRID[0], GRID[-1], len(GRID)]}


def pair_gold(rows, documents, by_key, texts, source, sc, passages):
    """[(row, gold label or None)] and the counts, gold read through the scorer only."""
    out, counts = [], {"contradicts": 0, "does not": 0, "left_out_other_pairs": 0, "left_out_no_decision": 0}
    marks = {}
    for document, items in documents.items():
        flagged = [i["item_id"] for i in items if sc.item_is_flag(by_key[document], i["item_id"])]
        if flagged:
            sentences = [p["text"] for p in passages(texts[document]["text"])]
            places = [sc.marked_passages(by_key[document], item, sentences, source) for item in flagged]
            marks[document] = places
        else:
            marks[document] = None
    for row in rows:
        if row["document_id"] not in documents:
            continue
        if row["decision"] is None:
            counts["left_out_no_decision"] += 1
            continue
        places = marks[row["document_id"]]
        if places is None:
            out.append((row, DOES_NOT))
            counts["does not"] += 1
            continue
        a, b = row["pair"]
        if any((a in m["marked"] and b in m["partner"]) or (a in m["partner"] and b in m["marked"]) for m in places):
            out.append((row, CONTRADICTS))
            counts["contradicts"] += 1
        else:
            counts["left_out_other_pairs"] += 1
    return out, counts


def source_ids(documents, build_items):
    """The source document ids of staged `documents`, from a build's items file; refused when one has none."""
    value = json.loads(Path(build_items).read_text(encoding="utf-8"))
    rows = value["items"] if isinstance(value, dict) else value
    mapping = {}
    for row in rows:
        mapping.setdefault(row["document_id"], set()).add(str(row["source_document_id"]))
    missing = [d for d in documents if len(mapping.get(d, ())) != 1]
    if missing:
        raise ValueError("a half A document has no single source id in the build's items: " + ", ".join(sorted(missing)[:5]))
    return sorted(next(iter(mapping[d])) for d in documents)


def calibration_value(adapter_sha256, temperature, threshold, sources):
    return {"schema": SCHEMA, "adapter_weights_sha256": adapter_sha256, "temperature": temperature, "threshold": threshold,
            "fitted_on_documents": sorted(sources), "development_only": True}


def trained_adapter(run, group=TRAINED_GROUP):
    """The adapter the trained group's pass applied, from the pass's own measurement."""
    measurement = json.loads((Path(run) / "replay_measurement.json").read_text(encoding="utf-8"))
    model = (measurement.get("models") or {}).get(group) or {}
    if not model.get("adapter_applied") or not model.get("adapter_sha256"):
        raise ValueError("the trained group's pass applied no adapter")
    return model["adapter_sha256"]


def calibrate(prompts, run, keys, items, source, b1, out, build_items, *, group=TRAINED_GROUP, cr=None, ft=None, pj=None, sc=None,
              passages=None):
    """Fit on half A, write the calibration and its record; returns the record. Nothing is written
    when no threshold qualifies."""
    if cr is None:
        import choice_read as cr
        import fresh_test as ft
        import pair_judge as pj
        import passage_pairs
        import doc_judge
        sc, passages = doc_judge._score_corpus(), passage_pairs.passages
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "calibration.json").exists():
        raise ValueError("this folder already holds a calibration")
    known, left_out, by_key = cr.universe(keys, items)
    half_a, _half_b = cr.halves(known[BENCHMARK])
    documents = {d: known[BENCHMARK][d] for d in half_a}
    sources = source_ids(documents, build_items)
    value, seen, records = pj.finished_pass(prompts, run)
    texts = value["documents"]
    rows = [r for r in ft.choice_rows(value, seen, records, group, 1.0) if r["choice"] == "pair" and r["document_id"] in documents]
    gold, counts = pair_gold(rows, documents, by_key, texts, source, sc, passages)
    fitted = fit_temperature([(row["decision"], label) for row, label in gold])
    t = fitted["temperature"]
    tempered = ft.choice_rows(value, seen, records, group, t)
    tempered = [r for r in tempered if r["document_id"] in documents]
    b1_row, _ = cr.comparator(BENCHMARK, documents, by_key, b1, left_out)
    if b1_row is None:
        raise ValueError("no B1 group is a comparator on half A")
    forms = value["config"]["choice"]["forms"]
    threshold, figures = cr.choose_threshold(BENCHMARK, documents, tempered, forms, keys, out, left_out, b1_row, "calibration_%s" % t)
    record = {"half_a_documents": len(documents), "gold_counts": counts, "temperature_fit": fitted, "threshold": threshold,
              "threshold_figures": figures, "written": threshold is not None}
    (out / "calibration_record.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    if threshold is None:
        return record
    calibration = calibration_value(trained_adapter(run, group), t, threshold, sources)
    (out / "calibration.json").write_text(json.dumps(calibration, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    ft.calibration(out / "calibration.json")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("calibrate")
    for name in ("--prompts", "--run", "--items", "--source", "--b1", "--out", "--build-items"):
        c.add_argument(name, required=True)
    c.add_argument("--key", action="append", required=True)
    c.add_argument("--group", default=TRAINED_GROUP, help="the model group that took the adapter (choice_direct on a read-development file)")
    args = parser.parse_args(argv)
    record = calibrate(args.prompts, args.run, args.key, args.items, args.source, args.b1, args.out, args.build_items, group=args.group)
    print(json.dumps({k: record[k] for k in ("half_a_documents", "gold_counts", "threshold", "written")} | {"temperature": record["temperature_fit"]["temperature"]}))
    return 0 if record["written"] else 2


if __name__ == "__main__":
    sys.exit(main())
