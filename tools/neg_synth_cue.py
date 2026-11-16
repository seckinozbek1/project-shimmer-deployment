#!/usr/bin/env python3
"""The cue-only check of the synthetic negotiation items (D-707; NEG_FINAL_ITEMS_METHOD.md section 2, after
Gururangan et al. 2018): can a set's labels be read from surface cues of the wording alone?

A bag-of-words multinomial logistic regression over each proposal's round-k wording alone (no round context, no
positions), with its length and its article's number of competing wordings as the only other features, trained
and scored with 5-fold cross-validation grouped by item (folds by the SHA-256 order of the item ids, so a fold
never splits an item). Targets: the fate, the conflict and M10's class (movable or settled, AM-3). The method's
rule (`baseline: majority`) flags a target when the cue model's macro-F1 beats the majority class's by the
declared margin (0.10) or its 95 percent item-cluster bootstrap lower bound lies above the majority class's. That
baseline gives every class but one an F1 of zero, so on balanced classes a model with no cue at all clears it
(proof 459: a cue-free fixture, lower bound 0.12 against 0.10). The declared alternative (`baseline:
permutation`) compares with the same model trained on labels shuffled across items: flagged at the margin over
the null's mean, or when the lower bound lies above the null's highest run. Both flags are always written;
`config/neg_synth.json` declares which one rejects a batch: the permutation null since D-714 (Seckin, 16 November
2026), the majority-class figure and flag reported beside it as information only.

A learned diagnostic in pure Python, never a keyword table (WORDS-A). Run by role V in its own folder; it prints
and writes aggregates only, never a text, an id or a per-item row.

    screen --set-dir <S set folder> --out <V>/cue_check.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import neg_synth as ns  # noqa: E402

SCHEMA = "neg-synth-cue-v1"
BASELINES = ("majority", "permutation")


def rows_of_builds(builds, cfg):
    """One row per proposal: its item, its wording, its article's count of wordings, and its three targets."""
    rows = []
    for b in builds:
        item, key = ns.sna.build_item(b)
        for a in item["articles"]:
            for p in a["proposals"]:
                k = key["proposals"][p["id"]]
                rows.append({"item": item["item_id"], "text": p["text"], "siblings": len(a["proposals"]),
                             "fate": k["fate"], "conflict": k["conflict"], "m10": ns.m10_class(cfg, k["fate"])})
    return rows


def rows_of_set(set_dir, cfg):
    return rows_of_builds([json.loads(p.read_text(encoding="utf-8"))
                           for p in sorted(Path(set_dir).glob("build/*/build.json"))], cfg)


def features(row):
    words = ns.sna.norm_text(row["text"]).split()
    f = {"w:" + w: 1.0 for w in words}
    f["len:%d" % min(len(words) // 5, 8)] = 1.0
    f["siblings:%d" % row["siblings"]] = 1.0
    f["bias"] = 1.0
    return f


def train(xs, ys, classes, cue):
    w = {c: {} for c in classes}
    for _epoch in range(cue["epochs"]):
        for x, y in zip(xs, ys):
            scores = {c: sum(w[c].get(f, 0.0) * v for f, v in x.items()) for c in classes}
            top = max(scores.values())
            exp = {c: math.exp(s - top) for c, s in scores.items()}
            z = sum(exp.values())
            for c in classes:
                g = exp[c] / z - (1.0 if c == y else 0.0)
                wc = w[c]
                for f, v in x.items():
                    wc[f] = wc.get(f, 0.0) * (1 - cue["rate"] * cue["l2"]) - cue["rate"] * g * v
    return w


def predict(w, x):
    return max(sorted(w), key=lambda c: sum(w[c].get(f, 0.0) * v for f, v in x.items()))


def macro_f1(gold, pred):
    classes = sorted(set(gold))
    if not classes:
        return None
    total = 0.0
    for c in classes:
        tp = sum(1 for g, p in zip(gold, pred) if g == c and p == c)
        fp = sum(1 for g, p in zip(gold, pred) if g != c and p == c)
        fn = sum(1 for g, p in zip(gold, pred) if g == c and p != c)
        total += 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    return total / len(classes)


def folds_of(items, k):
    order = sorted(set(items), key=lambda i: hashlib.sha256(("neg-synth-cue:" + i).encode("utf-8")).hexdigest())
    return {item: n % k for n, item in enumerate(order)}


def cross_predictions(rows, target, cue, labels=None):
    """Out-of-fold predictions of the cue model and of the training folds' majority class."""
    labels = labels or [r[target] for r in rows]
    fold = folds_of([r["item"] for r in rows], cue["folds"])
    xs = [features(r) for r in rows]
    cue_pred, maj_pred = [None] * len(rows), [None] * len(rows)
    for f in range(cue["folds"]):
        train_i = [i for i, r in enumerate(rows) if fold[r["item"]] != f]
        test_i = [i for i, r in enumerate(rows) if fold[r["item"]] == f]
        if not train_i or not test_i:
            continue
        classes = sorted({labels[i] for i in train_i})
        majority = sorted(Counter(labels[i] for i in train_i).items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        w = train([xs[i] for i in train_i], [labels[i] for i in train_i], classes, cue)
        for i in test_i:
            cue_pred[i] = predict(w, xs[i])
            maj_pred[i] = majority
    keep = [i for i in range(len(rows)) if cue_pred[i] is not None]
    return keep, labels, cue_pred, maj_pred


def screen_target(rows, target, cue):
    rows = [r for r in rows if r[target] is not None]
    keep, gold, cue_pred, maj_pred = cross_predictions(rows, target, cue)
    g = [gold[i] for i in keep]
    cue_f1 = macro_f1(g, [cue_pred[i] for i in keep])
    maj_f1 = macro_f1(g, [maj_pred[i] for i in keep])
    by_item = {}
    for i in keep:
        by_item.setdefault(rows[i]["item"], []).append(i)
    items = sorted(by_item)
    rng = random.Random(cue["seed"])
    boots = []
    for _ in range(cue["bootstrap"]):
        pick = [i for it in (rng.choice(items) for _ in items) for i in by_item[it]]
        boots.append(macro_f1([gold[i] for i in pick], [cue_pred[i] for i in pick]))
    boots.sort()
    lower = boots[int(0.025 * len(boots))] if boots else None
    null = []
    for n in range(cue["permutations"]):
        prng = random.Random("%d:null:%d" % (cue["seed"], n))
        labels = [r[target] for r in rows]
        prng.shuffle(labels)
        k2, g2, c2, _m2 = cross_predictions(rows, target, cue, labels=labels)
        null.append(macro_f1([g2[i] for i in k2], [c2[i] for i in k2]))
    null_mean = sum(null) / len(null) if null else None
    flags = {
        # The method as written (NEG_FINAL_ITEMS_METHOD.md section 2): against the majority class's macro-F1.
        "majority": bool(cue_f1 - maj_f1 >= cue["margin"] or (lower is not None and lower > maj_f1)),
        # The declared alternative: against the same model trained on labels shuffled across items.
        "permutation": bool(null and (cue_f1 - null_mean >= cue["margin"] or (lower is not None and lower > max(null))))}
    return {"rows": len(keep), "items": len(items), "classes": dict(Counter(g)),
            "cue_macro_f1": round(cue_f1, 4), "majority_macro_f1": round(maj_f1, 4),
            "cue_lower_95": round(lower, 4), "permutation_null_macro_f1": round(null_mean, 4) if null else None,
            "permutation_null_max": round(max(null), 4) if null else None,
            "flag_majority": flags["majority"], "flag_permutation": flags["permutation"],
            "baseline": cue["baseline"], "flag": flags[cue["baseline"]]}


def screen(rows, cfg=None):
    cfg = cfg or ns.load_config()
    cue = cfg["screens"]["cue"]
    if cue.get("baseline") not in BASELINES:
        raise ValueError("the cue check's baseline is declared as one of %s" % (BASELINES,))
    out = {"schema": SCHEMA, "targets": {t: screen_target(rows, t, cue) for t in cue["targets"]}}
    out["flagged"] = sorted(t for t, v in out["targets"].items() if v["flag"])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("screen")
    p.add_argument("--set-dir", required=True)
    p.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    cfg = ns.load_config()
    out = screen(rows_of_set(args.set_dir, cfg), cfg)
    path = ns.na.outside_repository(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    return 2 if out["flagged"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
