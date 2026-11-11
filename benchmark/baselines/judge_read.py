#!/usr/bin/env python3
"""J1's reading: what a judging candidate said on the pipeline's own prompts and on B1's.

Development, exposed (D-S38 P1; D-261, D-262). Reads one replay pass of doc_judge.py's J1 file on
this machine, no model. A saved judging call's reply is read in two views. `strict` is what the
pipeline would keep: a declared Finding relation and a record_verdict (`finding_record.is_finding`),
not self-hedged, through the one refusal test the judged paths use
(`paired_review.judged_item_refusal`). `judge` is what the model said, whatever relation it chose:
the Finding schema declares no relation for a contradiction in words (D-263), so strict can never
show one, and this view alone says whether the judge is right. A quote that is not in the unit is
refused in both. Then the adapters' order (common/mapping.py): an irregular answer on any unit, then
an ok one, then a refusal. A reply that ran to its allowance, or has no readable items list, is
unreadable. A call that answered nothing is silence: its item is ABSTAIN, never a detection, where
mapping.py's as-shipped line calls silence CLEAR, so accuracy here differs from `detection_dev`.
The keys are opened only by tools/score_corpus.py.

`read` computes the bar of D-262 from those figures; nobody reads it by hand. A go says the
pipeline arm is worth running on this candidate, never that it is above B1, and it is never
Shimmer's performance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _path in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines"), str(ROOT / "benchmark" / "adapters")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import doc_judge  # noqa: E402

ABSTAIN, FLAG, CLEAR, UNDECIDED = doc_judge.ABSTAIN, "FLAG", "CLEAR", "UNDECIDED"
BENCHMARKS = doc_judge.BAR_BENCHMARKS
MIN_READABLE = 0.95
MAX_FLAGGED = 0.80          # of items; C1's ContraDoc replies said VIOLATION 57 times of 57, whatever the document
MIN_B1_FLAGS = 5            # below this a precision is too few flags to hold a judge to
VIEWS = ("strict", "judge")
IRREGULAR_VERDICTS = ("VIOLATION", "ANTI_PATTERN")
OK_VERDICTS = ("ALIGNED", "COMPLIANT")
MIN_RIGHT = 2
CHANCE = 0.0125             # two variants on two benchmarks: four looks at D-241's 0.05


def reply_items(text):
    """The items of a reply's last JSON object, or None when it has no items list."""
    import bare_model
    if not isinstance(text, str):
        return None
    candidate = bare_model._last_balanced_object(bare_model._without_fences(text))
    if candidate is None:
        return None
    try:
        value, _ = bare_model._loads(candidate)
    except ValueError:
        try:
            value = json.loads(candidate, strict=False)
        except ValueError:
            return None
    items = value.get("items") if isinstance(value, dict) else None
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else None


def hedged(item):
    """The adapters' refusal test: a self-hedged answer is a refusal, not a finding."""
    return str(item.get("confidence") or "").upper() == "UNCERTAIN" or str(item.get("status") or "").lower() == "refused"


def answer(item):
    """irregular, ok or None: the record_verdict, else the agent's own verdict."""
    written = str(item.get("record_verdict") or "").strip().lower()
    if written in ("irregular", "ok"):
        return written
    verdict = str(item.get("verdict") or "").strip().upper()
    return "irregular" if verdict in IRREGULAR_VERDICTS else "ok" if verdict in OK_VERDICTS else None


def call_class(items, unit_text, fields_present=None, view="strict"):
    """One call's class from its items, by the adapters' order, in one view."""
    import finding_record
    import paired_review
    outcome = "SILENT"
    for item in items:
        if view == "strict":
            refused = (not finding_record.is_finding(item) or hedged(item)
                       or paired_review.judged_item_refusal(item, {}, fields_present, unit_text))
            said = str(item.get("record_verdict") or "").strip().lower()
        else:
            refused = hedged(item) or paired_review.quote_not_in_unit(item, unit_text)
            said = answer(item)
        if refused or said not in ("irregular", "ok"):
            outcome = "REFUSED" if outcome == "SILENT" else outcome
        elif said == "irregular":
            return FLAG
        else:
            outcome = CLEAR
    return outcome


def item_class(calls):
    """An item from its calls: settled on any unit beats refused beats silent; all unreadable abstains."""
    for wanted in (FLAG, CLEAR):
        if wanted in calls:
            return wanted, "kept_claim"
    if "REFUSED" in calls:
        return UNDECIDED, "refused"
    if "SILENT" in calls:
        return ABSTAIN, "silence"
    return ABSTAIN, "unreadable"


def agent_rows(value, by_prompt, records):
    """Per (view, group, benchmark, document, rule, item): the calls' classes; and per (group,
    benchmark) the call counts the bar reads."""
    calls = value["agent_calls"]
    per_item, counts = {}, {}
    for p in value["prompts"]:
        if p.get("form") != doc_judge.AGENT_FORM:
            continue
        seen = by_prompt.get(p["prompt_id"]) or {}
        record = records.get(seen.get("call_id")) or {}
        reply = record.get("reply") if isinstance(record.get("reply"), dict) else {}
        text = reply.get("text") if record.get("backend_ok") else None
        items = None if seen.get("length_reached_allowance") is True else reply_items(text)
        call = calls[p["source_call_id"]]
        c = counts.setdefault((p["group"], p["benchmark"]), {"calls": 0, "readable": 0, "strict_kept": 0, "judge_kept": 0, "silent": 0})
        c["calls"] += 1
        for view in VIEWS:
            cls = "UNREADABLE" if items is None else call_class(items, call["unit_text"], call["fields_present"], view)
            c[view + "_kept"] += cls in (FLAG, CLEAR)
            per_item.setdefault((view, p["group"], p["benchmark"], p["document_id"], p["rule_id"], p["item_id"]), []).append(cls)
        if items is not None:
            c["readable"] += 1
            c["silent"] += not items
    return per_item, counts


def b1_rows(value, by_prompt, records):
    """B1's rows, a reply that ran to its allowance being unreadable: it may hold a draft object."""
    rows = doc_judge._comparator_rows(value, by_prompt, records)
    for r in rows:
        if r.get("length_reached_allowance") is True:
            r.update(label=None, abstain=True, parse_failure="reached_allowance")
    return rows


# D-380: the class setting is DECLARED per item set, never read off the gold present and never
# forced to three. An undecided answer on a 2-class item is a miss for its gold class.
CLASS_SETTINGS = {"2-class": (FLAG, "CLEAR"), "3-class": (FLAG, "CLEAR", "UNDECIDED")}
# The declaration for G1's items and every set built on them (J1, T, judge 2e and 2f, the cloud
# reference's half A): no not-enough-info gold among G1's 93 SciTab claims, counted through the
# scorer (D-380 addendum); ContraDoc is binary.
G1_SETTINGS = {"scitab": "2-class", "contradoc": "2-class"}


def class_setting(settings, benchmark):
    setting = (settings or {}).get(benchmark)
    if setting not in CLASS_SETTINGS:
        raise ValueError("no declared class setting for %s (D-380): give 2-class or 3-class, not %r" % (benchmark, setting))
    return setting


def macro_f1(rows, setting):
    """Macro-F1 over the declared setting's gold classes; an abstention is wrong (common/metrics.py's
    rule). A gold class outside the declared setting is refused: the declaration does not fit."""
    from common import metrics as measures
    if setting not in CLASS_SETTINGS:
        raise ValueError("the class setting is declared per item set (D-380): give 2-class or 3-class, not %r" % (setting,))
    classes = CLASS_SETTINGS[setting]
    outside = sorted({r["gold"] for r in rows} - set(classes))
    if outside:
        raise ValueError("the set is declared %s but holds gold %s" % (setting, ", ".join(outside)))
    pairs = [(r["cls"], r["gold"]) for r in rows]
    return round(sum(measures.class_scores(pairs, c)["f1"] for c in classes) / len(classes), 6) if rows else None


def label_rows(view_rows, keys, out, left_out, tag):
    """Each row's class turned into a label file and read back through the scorer."""
    sc = doc_judge._score_corpus()
    by_doc = {}
    for r in view_rows:
        by_doc.setdefault(r["document_id"], []).append(r)
    scored = []
    for key in keys:
        table = sc.item_table(key)
        doc_id, benchmark = table["document_id"], table["benchmark"]
        mine = {r["item_id"]: r for r in by_doc.get(doc_id, ())}
        if not mine:
            continue
        spec = doc_judge._adapter(benchmark).SPEC
        folder = Path(out) / "labels" / tag / doc_id
        for item in table["items"]:
            r = mine.get(item["item_id"])
            if r is None:
                continue
            name = r["label"] if "label" in r else (doc_judge.label_name(spec, r["cls"]) if r["cls"] != ABSTAIN else None)
            doc_judge._write_json(folder / "labels" / (item["item_id"] + ".json"), {
                "arm": "B1", "schema": "b1-label-v2", "item_id": item["item_id"], "document_id": doc_id, "rule_id": item["rule_id"],
                "benchmark": benchmark, "label": name, "abstain": name is None, "evidence": None, "reason": None, "view": tag})
        labelled = sc.benchmark_labels(key, folder, arm="B1")
        if labelled.get("availability") != "labelled" or labelled.get("arm") != "B1":
            raise ValueError("the scorer did not label %s as a B1 folder: %s" % (doc_id, labelled.get("availability")))
        for item in labelled["items"]:
            r = mine.get(item["item_id"])
            if r is None or item["item_id"] in left_out:
                continue
            scored.append({"document_id": doc_id, "item_id": item["item_id"], "benchmark": benchmark, "gold": item["gold_class"],
                           "cls": item["b1_class"], "source": r.get("source", "b1_label"), "was_refused": False,
                           "written_cls": item["b1_class"]})
    return scored


def figures(rows, settings):
    """Each benchmark's figures, its macro-F1 in the item set's declared class setting (D-380)."""
    out = {}
    for benchmark in BENCHMARKS:
        mine = [r for r in rows if r["benchmark"] == benchmark]
        if mine:
            setting = class_setting(settings, benchmark)
            out[benchmark] = dict(doc_judge.metrics(mine), macro_f1=macro_f1(mine, setting), class_setting=setting)
    return out


def agent_row(m, counts, b1, c1_net):
    """D-263's conditions on one variant and benchmark, in the judge view."""
    chance = doc_judge.chance_tail(m["strata"], m["flag_tp"]) if m["flag_tp"] + m["flag_fp"] else 1.0
    flagged = m["flag_tp"] + m["flag_fp"]
    b1_flags = b1["flag_tp"] + b1["flag_fp"]
    net = m["flag_tp"] - m["flag_fp"]
    row = {"readable": counts["readable"] >= MIN_READABLE * counts["calls"], "not_flagging_everything": flagged <= MAX_FLAGGED * m["items"],
           "two_right_from_two_documents": m["flag_tp"] >= MIN_RIGHT and m["flag_tp_documents"] >= MIN_RIGHT,
           "net_above_c1": net > c1_net, "above_chance": chance <= CHANCE,
           "precision_at_least_b1": b1_flags < MIN_B1_FLAGS or m["flag_tp"] * b1_flags >= b1["flag_tp"] * flagged}
    return dict(row, passes=all(row.values()), chance=round(chance, 6), right=m["flag_tp"], false=m["flag_fp"],
                b1_right=b1["flag_tp"], b1_false=b1["flag_fp"], flagged_share=round(flagged / m["items"], 4) if m["items"] else None, net=net)


def paired_with_baseline(rows, flagged):
    """Items only one arm got right, this arm against a saved flag list: reported, no condition."""
    wins = losses = 0
    for r in rows:
        theirs = (r["document_id"], r["item_id"]) in flagged
        mine_right, theirs_right = (r["cls"] == FLAG) == (r["gold"] == FLAG), theirs == (r["gold"] == FLAG)
        wins += mine_right and not theirs_right
        losses += theirs_right and not mine_right
    return {"only_this_arm_right": wins, "only_baseline_right": losses}


def decide(rows):
    """go when any variant passes on any benchmark, naming the variant J2 would use: the one with
    the higher net right flags over the benchmarks it passes, a tie going to the direct form."""
    passing = {}
    for benchmark, groups in rows.items():
        for group, row in groups.items():
            if row["passes"]:
                passing[group] = passing.get(group, 0) + row["net"]
    if not passing:
        return "drop", None
    best = max(passing.values())
    tied = sorted(g for g, v in passing.items() if v == best)
    return "go", ("judge_direct" if "judge_direct" in tied else tied[0])


def refusal(out, bar, digest, keys_digest, measurement):
    """None, or why this pass gets no reading. The bar file's own digest is in the decision."""
    if (Path(out) / "j1_result.json").exists():
        return "this folder already holds a J1 result: the first reading stands"
    if digest != bar["prompts_sha256"]:
        return "the prompts are not the ones the bar file names"
    if keys_digest != bar["keys_sha256"]:
        return "the keys are not the ones the bar file names"
    if measurement.get("complete") is not True or measurement.get("prompts_sha256") != digest:
        return "the pass did not finish on these prompts: a decision says what follows"
    return None


def read(prompts_path, run_dir, keys, bar_path, baseline_path, out, settings=G1_SETTINGS):
    """J1's read. `settings` is the item set's declared class setting per benchmark (D-380): G1's
    for the real read, 2-class on both benchmarks."""
    import reply_records
    out = Path(out)
    bar = json.loads(Path(bar_path).read_text(encoding="utf-8"))
    digest = hashlib.sha256(Path(prompts_path).read_bytes()).hexdigest()
    sc = doc_judge._score_corpus()
    value = doc_judge.read_file(prompts_path)
    run_dir = Path(run_dir)
    measurement = json.loads((run_dir / doc_judge.MEASUREMENT_FILE).read_text(encoding="utf-8"))
    refused = refusal(out, bar, digest, doc_judge.keys_digest(sc, keys), measurement)
    if refused:
        raise ValueError(refused)
    records = {r.get("call_id"): r for r in reply_records.records(run_dir / "audit" / "model_replies")}
    by_prompt = {r["prompt_id"]: r for r in measurement["rows"]}
    per_item, counts = agent_rows(value, by_prompt, records)
    b1 = b1_rows(value, by_prompt, records)
    left_out = set(bar.get("left_out") or ())
    groups = [g["group"] for g in value["config"]["models"]]
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    qwen = {(f["document_id"], f["item_id"]) for f in baseline["flags"]["qwen_tuned"][doc_judge.COMPARATOR] if f["cls"] == FLAG}
    result = {"schema": "judge-read-v1", "prompts_sha256": digest, "models": measurement.get("models"), "views": {}, "rows": {}, "paired": {}}
    c1_items = {k[5] for k in per_item}
    for group in groups:
        result["views"][group] = {}
        for view in VIEWS:
            rows = []
            for (v, g, benchmark, document_id, rule_id, item_id), calls in per_item.items():
                if (v, g) == (view, group):
                    cls, source = item_class(calls)
                    rows.append({"document_id": document_id, "item_id": item_id, "benchmark": benchmark, "cls": cls, "source": source})
            scored = label_rows(rows, keys, out, left_out, "%s_%s" % (group, view))
            result["views"][group][view] = figures(scored, settings)
            for benchmark in BENCHMARKS:
                got = result["views"][group][view].get(benchmark, {}).get("items")
                if got != bar["items"][benchmark]:
                    raise ValueError("%s %s %s scored %s items, not the bar's %s" % (group, view, benchmark, got, bar["items"][benchmark]))
        mine = [dict(r, cls=None) for r in b1 if r["group"] == group]
        bare = label_rows(mine, keys, out, left_out, group + "_b1")
        result["views"][group].update(b1_all=figures(bare, settings),
                                     b1_on_agent_items=figures([r for r in bare if r["item_id"] in c1_items], settings))
        result["paired"][group] = {b: paired_with_baseline([r for r in bare if r["benchmark"] == b], qwen) for b in BENCHMARKS}
    product_b1 = next(g["group"] for g in value["config"]["models"] if g.get("reasoning"))
    for benchmark in BENCHMARKS:
        result["rows"][benchmark] = {
            g: agent_row(result["views"][g]["judge"][benchmark], counts[(g, benchmark)],
                         result["views"][product_b1]["b1_on_agent_items"][benchmark], bar["c1_net"][benchmark])
            for g in groups}
    result["call_counts"] = {"%s/%s" % k: v for k, v in counts.items()}
    result["seconds"] = measurement.get("seconds")
    result["verdict"], result["variant_for_j2"] = decide(result["rows"])
    result["means"] = "whether the pipeline arm is worth running on this candidate; never above B1, never Shimmer's performance"
    doc_judge._write_json(out / "j1_result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(prog="judge_read.py", allow_abbrev=False, description=__doc__.split("\n\n")[0])
    parser.add_argument("--prompts", required=True)
    parser.add_argument("--run", required=True, help="the pass folder (evidence/b1/<pass name>)")
    parser.add_argument("--key", action="append", required=True)
    parser.add_argument("--bar", required=True, help="j1_bar.json, D-262's digests and C1's right flags")
    parser.add_argument("--baseline", required=True, help="G1's g1_scores.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = read(args.prompts, args.run, args.key, args.bar, args.baseline, args.out)
    except Exception as exc:
        print("judge_read stopped: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 4
    print(json.dumps({"verdict": result["verdict"], "variant_for_j2": result["variant_for_j2"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
