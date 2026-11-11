"""The cloud reference's half A figures in each benchmark's paper metric, with item counts and 95 percent
bootstrap intervals (D-S99 items 1 to 4), from the same scored rows as cloud_reference_score.json:
the reader's own functions (judge_read.agent_rows, item_class, b1_rows, label_rows) and the scorer, keys
passed to tools/score_corpus.py only.

SciTab: 3-class macro-F1 over the FIXED three gold classes (an absent class scores F1 0, its support 0
noted), resampled over tables (a SciTab document is one table), since claims cluster by table.
ContraDoc: binary judgment accuracy (an ABSTAIN wrong), with precision, recall and F1 of the
contradictory class (FLAG), resampled over documents. Percentile intervals, 10,000 resamples, seed 20261109.

    python score_intervals.py <checkout holding the code> <out folder>
"""
import json
import random
import subprocess
import sys
from pathlib import Path

CODE = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
sys.path[:0] = [str(CODE / "scripts"), str(CODE / "tools"), str(CODE / "benchmark" / "baselines"),
                str(CODE / "benchmark" / "adapters")]
import cloud_reference as cr  # noqa: E402
import judge_read  # noqa: E402
import reply_records  # noqa: E402

RESAMPLES = 10000
SEED = 20261109


def main_checkout(code):
    done = subprocess.run(["git", "-C", str(code), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                          capture_output=True, text=True, check=True)
    return Path(done.stdout.strip()).resolve().parent


MAIN = main_checkout(CODE)
PROMPTS = MAIN / "external/s05/J1/j1_prompts.json"
BAR = MAIN / "external/s05/J1/j1_bar.json"
ITEMS = CODE / "benchmark/baselines/g1_bar_items.json"
KEYS = sorted(str(p) for p in (MAIN / "external/s05/G1/build").glob("*/*/answer_key.json"))
RUNS = {"reference": CODE / "output/cloud_reference/opus48-half-a-1",
        "j1_local": MAIN / "external/s05/J1/ev/evidence/b1/j1"}


def scored_rows(run_dir, split, tag):
    """{(group, view): scored rows} on half A, view in b1, judge, strict."""
    value, bar = cr.load(PROMPTS, BAR)
    measurement = json.loads((Path(run_dir) / cr.MEASUREMENT_FILE).read_text(encoding="utf-8"))
    records = {r.get("call_id"): r for r in reply_records.records(Path(run_dir) / "audit" / "model_replies")}
    by_prompt = {r["prompt_id"]: r for r in measurement["rows"]}
    per_item, _ = judge_read.agent_rows(value, by_prompt, records)
    left_out = set(bar.get("left_out") or ())
    out = {}
    for group in cr.GROUP_ORDER:
        for view in judge_read.VIEWS:
            rows = []
            for (v, g, benchmark, document_id, rule_id, item_id), calls in per_item.items():
                if (v, g) == (view, group):
                    cls, source = judge_read.item_class(calls)
                    rows.append({"document_id": document_id, "item_id": item_id, "benchmark": benchmark, "cls": cls,
                                 "source": source})
            out[(group, view)] = judge_read.label_rows(cr.half_a_rows(rows, split), KEYS, OUT / "labels", left_out,
                                                       "%s_%s_%s" % (tag, group, view))
        bare = [dict(r, cls=None) for r in judge_read.b1_rows(value, by_prompt, records) if r["group"] == group]
        out[(group, "b1")] = judge_read.label_rows(cr.half_a_rows(bare, split), KEYS, OUT / "labels", left_out,
                                                   "%s_%s_b1" % (tag, group))
    return out


def f1(rows, c):
    tp = sum(1 for r in rows if r["cls"] == c and r["gold"] == c)
    fp = sum(1 for r in rows if r["cls"] == c and r["gold"] != c)
    fn = sum(1 for r in rows if r["cls"] != c and r["gold"] == c)
    p = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    return (2 * p * rc / (p + rc) if p + rc else 0.0), p, rc, tp, fp, fn


def macro_fixed(rows, classes):
    return sum(f1(rows, c)[0] for c in classes) / len(classes)


def accuracy(rows):
    return sum(1 for r in rows if r["cls"] == r["gold"]) / len(rows) if rows else None


def interval(rows, stat, rng):
    """Percentile 95 percent interval of `stat` over resampled clusters (documents)."""
    clusters = {}
    for r in rows:
        clusters.setdefault(r["document_id"], []).append(r)
    keys = sorted(clusters)
    values = []
    for _ in range(RESAMPLES):
        sample = [r for k in (rng.choice(keys) for _ in keys) for r in clusters[k]]
        values.append(stat(sample))
    values.sort()
    return [round(values[int(0.025 * RESAMPLES)], 4), round(values[int(0.975 * RESAMPLES) - 1], 4)]


def main():
    value, bar = cr.load(PROMPTS, BAR)
    split, _ = cr.halves(value, ITEMS, KEYS)
    rng = random.Random(SEED)
    result = {"label": cr.LABEL, "labels": ["a paid cloud model on development items already read", "exposed",
                                            "in-sample: half A chose C's thresholds (REPORT_COMPARABILITY 3a)",
                                            "not Shimmer's performance"],
              "method": __doc__.split("\n\n")[1].replace("\n", " "), "resamples": RESAMPLES, "seed": SEED, "runs": {}}
    gold_classes = {}
    collected = {name: scored_rows(run_dir, split, name) for name, run_dir in RUNS.items()}
    for rows_by in collected.values():
        for rows in rows_by.values():
            for r in rows:
                gold_classes.setdefault(r["benchmark"], set()).add(r["gold"])
    result["gold_classes_seen"] = {b: sorted(c) for b, c in gold_classes.items()}
    fixed = sorted(gold_classes.get("scitab", ()))
    result["scitab_fixed_classes"] = fixed
    for name, rows_by in collected.items():
        result["runs"][name] = {}
        for (group, view), rows in sorted(rows_by.items()):
            entry = {}
            for benchmark in ("scitab", "contradoc"):
                mine = [r for r in rows if r["benchmark"] == benchmark]
                if not mine:
                    continue
                tables = len({r["document_id"] for r in mine})
                if benchmark == "scitab":
                    support = {c: sum(1 for r in mine if r["gold"] == c) for c in fixed}
                    present = sorted({r["gold"] for r in mine})
                    entry[benchmark] = {
                        "items": len(mine), "tables": tables, "gold_support": support,
                        "macro_f1_fixed_three": round(macro_fixed(mine, fixed), 4),
                        "macro_f1_classes_present": round(macro_fixed(mine, present), 4),
                        "interval_95_over_tables": interval(mine, lambda s: macro_fixed(s, fixed), rng),
                        "abstain": sum(1 for r in mine if r["cls"] == "ABSTAIN")}
                else:
                    f, p, rc, tp, fp, fn = f1(mine, "FLAG")
                    entry[benchmark] = {
                        "items": len(mine), "documents": tables, "accuracy": round(accuracy(mine), 4),
                        "interval_95_over_documents": interval(mine, accuracy, rng),
                        "contradictory_precision": round(p, 4), "contradictory_recall": round(rc, 4),
                        "contradictory_f1": round(f, 4), "tp": tp, "fp": fp, "fn": fn,
                        "abstain": sum(1 for r in mine if r["cls"] == "ABSTAIN")}
            result["runs"][name]["%s/%s" % (group, view)] = entry
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cloud_reference_intervals.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n",
                                                        encoding="utf-8")
    print("written")


main()
