"""The negotiation advisor judge's calibration against the checker (D-656 item 1: "replaced or calibrated on
non-pilot items until the checker's agreement is recorded at or above the plan's floor"), on development material
only. No model and no provider: it reads the judge's saved choice decisions (CHOICE-A: each grade's probability,
D-672) and the checker's grades, and fits one additive log-probability offset per grade.

    py -3.12 -X utf8 tools/neg_judge_calibration.py rows --prompts P --run R --out ROWS.json
    py -3.12 -X utf8 tools/neg_judge_calibration.py fit --rows ROWS.json --checker SHEET.json \
        --exclude-items PILOT_IDS.json --out CAL.json
    py -3.12 -X utf8 tools/neg_judge_calibration.py compare --rows A.json --rows B.json --checker SHEET.json \
        --exclude-items PILOT_IDS.json --out CMP.json

Why an offset and not a temperature. The pilot's judge gave every counter grade 2 (D-653: kappa 0.0 on 10
entries, the checker never gave 2). A temperature (choice_decision.tempered) never changes which answer is top,
so it cannot move one grade; a per-grade offset is the smallest change that can (a prior shift: grade g's log
probability plus b_g, b_2 fixed at 0). Both offsets come from GRID; the fit maximises the scorer's own kappa
(tools/score_neg_advisor.agreement, the AM-1 rule), a tie going to the smaller total offset.

How it is judged. Leave one ITEM out: each item's entries are graded by offsets fitted on the other items
only, so no entry is graded by offsets that saw it; the out-of-fold kappa is the figure, with a 95 percent
percentile interval from a seeded bootstrap over items (entries of one item move together). The judge is at
the floor when the out-of-fold kappa is at or above score_neg_advisor.KAPPA_FLOOR (0.60, plan line 4) on at
least MIN_ENTRIES entries from at least MIN_ITEMS items; otherwise `below_floor`, and the next step is a
second round or a replacement judge (`compare` reads several candidates' decisions the same way).

What it refuses. Any row or checker entry of an item named in --exclude-items (the pilot's frozen items and
their replies, D-654, D-656: "neither the pilot's 24 items nor their replies are used to calibrate it"); an
entry the checker graded twice or not at all; a decision without the three declared grades. Counts, figures
and offsets only are written; no entry text.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

SCHEMA = "neg-judge-calibration-v1"
ROWS_SCHEMA = "neg-judge-decisions-v1"
GRADES = ("0", "1", "2")
GRID = tuple(round(-8 + 0.25 * k, 2) for k in range(65))
MIN_ENTRIES, MIN_ITEMS = 30, 6
RESAMPLES, SEED = 2000, "20261116-neg-judge-calibration"
UNGRADED = "no grade"


def _sc():
    import score_neg_advisor
    return score_neg_advisor


def log_probabilities(decision):
    import math
    answers = {str(a.get("label")): a.get("probability") for a in (decision or {}).get("answers") or []}
    if sorted(answers) != sorted(GRADES) or not all(isinstance(p, (int, float)) and p >= 0 for p in answers.values()):
        raise ValueError("a judge decision holds the three declared grades with their probabilities")
    return {g: (math.log(answers[g]) if answers[g] > 0 else float("-inf")) for g in GRADES}


def grade(logs, offsets):
    """The grade with the highest offset log probability; a tie is UNGRADED, never broken by order."""
    scored = {g: logs[g] + offsets.get(g, 0.0) for g in GRADES}
    best = max(scored.values())
    top = [g for g in GRADES if scored[g] == best]
    return top[0] if len(top) == 1 else UNGRADED


def fit(rows):
    """{offsets, kappa} maximising the scorer's kappa over `rows` [(logs, checker grade)]."""
    best, best_key = None, None
    reference = [r for _, r in rows]
    for b0 in GRID:
        for b1 in GRID:
            offsets = {"0": b0, "1": b1, "2": 0.0}
            k = _sc()._kappa(reference, [grade(l, offsets) for l, _ in rows])
            key = (k if k is not None else -2.0, -(abs(b0) + abs(b1)), -b0, -b1)
            if best_key is None or key > best_key:
                best, best_key = offsets, key
    return {"offsets": best, "kappa": best_key[0] if best_key[0] > -2 else None}


def excluded_item(item_id, excluded):
    """True for an item the calibration may never read (the pilot's, D-656)."""
    return str(item_id) in excluded


def _paired(rows_value, sheet, excluded):
    graded = Counter(str(e.get("entry_id")) for e in sheet.get("entries") or [])
    twice = [e for e, n in graded.items() if n > 1]
    if twice:
        raise ValueError("the checker graded %d entries more than once" % len(twice))
    checker = {str(e["entry_id"]): str(e.get("grade")) for e in sheet.get("entries") or []}
    if any(g not in GRADES for g in checker.values()):
        raise ValueError("a checker grade is not one of %s" % ", ".join(GRADES))
    out = []
    for row in rows_value.get("rows") or []:
        if excluded_item(row.get("item_id"), excluded):
            raise ValueError("a judge decision belongs to an excluded item (the pilot is never calibrated on, D-656)")
        entry = str(row.get("entry_id"))
        if entry not in checker:
            continue
        out.append((str(row["item_id"]), log_probabilities(row.get("decision")), checker[entry]))
    if any(excluded_item(e.get("item_id"), excluded) for e in sheet.get("entries") or [] if e.get("item_id") is not None):
        raise ValueError("a checker entry belongs to an excluded item (D-656)")
    return out


def calibrate(rows_value, sheet, excluded, *, resamples=RESAMPLES):
    paired = _paired(rows_value, sheet, set(map(str, excluded)))
    items = sorted({i for i, _, _ in paired})
    reference = [g for _, _, g in paired]
    raw = [grade(l, {}) for _, l, _ in paired]
    oof = []
    for held in items:
        trained = fit([(l, g) for i, l, g in paired if i != held]) if len(items) > 1 else {"offsets": {}}
        oof.extend((held, grade(l, trained["offsets"]), g) for i, l, g in paired if i == held)
    whole = fit([(l, g) for _, l, g in paired]) if paired else {"offsets": None, "kappa": None}
    sc = _sc()
    by_item = defaultdict(list)
    for item, predicted, gold in oof:
        by_item[item].append((predicted, gold))
    rng = random.Random(SEED)
    draws = []
    for _ in range(resamples if len(items) > 1 else 0):
        pick = [by_item[rng.choice(items)] for _ in items]
        pairs = [p for group in pick for p in group]
        k = sc._kappa([g for _, g in pairs], [p for p, _ in pairs])
        if k is not None:
            draws.append(k)
    draws.sort()
    interval = ([round(draws[int(0.025 * (len(draws) - 1))], 4), round(draws[int(0.975 * (len(draws) - 1))], 4)]
                if draws else None)
    measured = sc.agreement([g for _, _, g in oof], [p for _, p, _ in oof]) if oof else None
    enough = len(paired) >= MIN_ENTRIES and len(items) >= MIN_ITEMS
    at_floor = bool(enough and measured and sc.at_bar(measured))
    return {"schema": SCHEMA, "entries": len(paired), "items": len(items), "floor": sc.KAPPA_FLOOR,
            "minimum": {"entries": MIN_ENTRIES, "items": MIN_ITEMS}, "enough": enough,
            "uncalibrated": sc.agreement(reference, raw) if paired else None,
            "out_of_fold": measured, "out_of_fold_interval95": interval, "resamples": len(draws),
            "offsets": whole["offsets"], "in_sample_kappa": whole.get("kappa"),
            "grades": {"checker": dict(Counter(reference)), "uncalibrated": dict(Counter(raw)),
                       "out_of_fold": dict(Counter(p for _, p, _ in oof))},
            "verdict": "at_floor" if at_floor else ("below_floor" if enough else "too_few_entries"),
            "excluded_items": len(set(map(str, excluded))),
            "reads": "the judge's saved choice decisions and the checker's grades; development items only"}


def rows_from_pass(prompts_path, run_dir):
    """The judge's decisions of a negotiation advisor pass folder: per judge prompt its entry, item and the
    decision on its reply record (no text)."""
    prompts = json.loads(Path(prompts_path).read_text(encoding="utf-8"))
    by_id = {p["prompt_id"]: p for p in prompts.get("prompts") or [] if p.get("form") == "judge"}
    measurement = json.loads((Path(run_dir) / "replay_measurement.json").read_text(encoding="utf-8"))
    records = {}
    folder = Path(run_dir) / "audit" / "model_replies"
    for path in sorted(folder.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        records[record.get("call_id")] = record
    rows, missing = [], 0
    for row in measurement.get("rows") or []:
        p = by_id.get(row.get("prompt_id"))
        if p is None:
            continue
        decision = (records.get(row.get("call_id")) or {}).get("decision")
        if not isinstance(decision, dict):
            missing += 1
            continue
        rows.append({"entry_id": p["entry"]["entry_id"], "item_id": p["item_id"], "arm": p["entry"].get("arm"),
                     "decision": {"answers": [{"label": a["label"], "probability": a["probability"]}
                                              for a in decision.get("answers") or []],
                                  "declared_mass": decision.get("declared_mass")}})
    return {"schema": ROWS_SCHEMA, "rows": rows, "without_decision": missing}


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("rows", allow_abbrev=False)
    r.add_argument("--prompts", required=True, type=Path)
    r.add_argument("--run", required=True, type=Path)
    r.add_argument("--out", required=True, type=Path)
    for name in ("fit", "compare"):
        f = sub.add_parser(name, allow_abbrev=False)
        f.add_argument("--rows", required=True, type=Path, action="append")
        f.add_argument("--checker", required=True, type=Path)
        f.add_argument("--exclude-items", required=True, type=Path)
        f.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "rows":
        value = rows_from_pass(args.prompts, args.run)
        print(json.dumps({"rows": len(value["rows"]), "without_decision": value["without_decision"]}))
    else:
        excluded = _read(args.exclude_items)
        sheet = _read(args.checker)
        results = [calibrate(_read(p), sheet, excluded) for p in args.rows]
        if args.command == "fit" and len(results) != 1:
            parser.error("fit reads one --rows; compare reads several")
        value = results[0] if args.command == "fit" else {"schema": SCHEMA + "-compare", "candidates": [
            dict(r, rows_file=p.name) for r, p in zip(results, args.rows)]}
        print(json.dumps([{"entries": x["entries"], "verdict": x["verdict"],
                           "kappa": (x["out_of_fold"] or {}).get("kappa")} for x in results]))
    args.out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
