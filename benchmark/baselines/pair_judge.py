"""P2 (a), find then judge, measured on a replay: Python proposes pairs of passages of one
document (scripts/passage_pairs.py), the model judges each pair seeing both, in both orders.

An evaluation tool, not a review and not an arm (development, exposed). It rides doc_judge.py's
replay pass (form `pair`), so no bound controller file changes. `keep` means the step stays in the
harness; it is no target met, and `not_kept` says little about a moderate judge on 60 documents.

  build (no model; the embedding model on this machine)
      py -3.12 benchmark/baselines/pair_judge.py build --workload W [--workload W ...]
          --items ITEMS.json [--items ...] --out prompts.json [--config F]
    One prompt per proposed pair and order. A document's pairs are the first `pair.limit` of
    passage_pairs.propose, ranked by the embedding model. Reads no key.

  read (no model; the keys only through tools/score_corpus.py)
      py -3.12 benchmark/baselines/pair_judge.py read --prompts P --run R --key K [--key K ...]
          --bar BAR.json --b1 J1_RESULT.json --source SOURCE.json --out DIR
    A pair is flagged in a view: `both_orders` when both its calls say contradict (the bar's view),
    `either_order` when one does. A document is flagged when a pair is.

    Two counts of a flag, side by side. By DOCUMENT: right on a gold document, false on a clear
    one, as B1 is counted, so the two compare. By PLACE, on gold documents with two separate
    marked passages only: `partner` when a flagged pair holds the marked sentence and the sentence
    the source says it contradicts; `touch` when a flagged pair holds the marked sentence alone,
    reported and never counted as placed, since an arbitrary sentence touches most of 40 pairs;
    `wrong_place` otherwise, `none` with no flag. A document whose marks a pair cannot hold is
    `one_passage`, one with no usable partner `no_partner`, one with no marked passage
    `not_measurable`, whatever was flagged on them.

    Beside them: a Python-only control (the same number of documents flagged by the top pair's
    score alone), the rate of contradict calls on clear documents, order agreement, flagged pairs
    per document, cannot-tell calls, replies run to the allowance, and pair precision.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "scripts"), str(HERE.parents[1] / "tools")]

import doc_judge  # noqa: E402
import passage_pairs  # noqa: E402

CONFIG_PATH = HERE / "pair_judge_prompt.json"
VIEWS = ("both_orders", "either_order")
BAR_VIEW = "both_orders"
RESULT_FILE = "pair_scores.json"
BENCHMARK = "contradoc"
# D-274's bar and D-276's change to it, here and not in the bar file: the file names the inputs,
# and read refuses one stating any other figure.
BAR = {"readable_at_least": .95, "flagged_share_at_most": .8, "placed_at_least": 5, "chance_at_most": .05,
       "b1_flags_for_precision": 5}


_words_allowed = False   # a proof's switch: the measured file is ranked by the embedding model alone


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def proposed(workload, items_path, limit, embed):
    """A workload's document with its first `limit` pairs, ranked by the embedding model alone."""
    workload = Path(workload)
    target = doc_judge._targets(workload)
    path = workload / "context" / target
    doc_id = path.stem
    text = doc_judge._document_text(path)
    item = doc_judge._items(items_path, doc_id)[0]
    passages = passage_pairs.passages(text)
    vectors = embed(passages)
    if not vectors and not _words_allowed:
        raise ValueError("the embedding model gave no vectors for " + doc_id + ": no fallback to words here")
    pairs = passage_pairs.propose(passages, limit, vectors)
    document = {"benchmark": item["benchmark"], "target": target, "text": text, "sha256": doc_judge._sha(text),
                "conventions": [], "top_score": pairs[0]["score"] if pairs else 0.0}
    return doc_id, document, item, passages, pairs


def build(workloads, items_paths, out, config_path=CONFIG_PATH, embed=passage_pairs.embed):
    if len(items_paths) == 1:
        items_paths = list(items_paths) * len(workloads)
    if len(workloads) != len(items_paths):
        raise ValueError("one items file, or one per workload in the same order")
    config = doc_judge.check_config(json.loads(Path(config_path).read_text(encoding="utf-8")))
    documents, prompts = {}, []
    for workload, items_path in zip(workloads, items_paths):
        doc_id, documents[doc_id], item, passages, pairs = proposed(workload, items_path, config["pair"]["limit"], embed)
        for group in config["models"]:
            for pair in pairs:
                a, b = passages[pair["a"]], passages[pair["b"]]
                for order, first, second in (("ab", a, b), ("ba", b, a)):
                    user = doc_judge.render_pair(config, first["text"], second["text"])
                    prompts.append({
                        "prompt_id": "p%06d" % (len(prompts) + 1), "form": doc_judge.PAIR_FORM,
                        "pair_id": "%d-%d-%s" % (pair["a"], pair["b"], order), "pair": [pair["a"], pair["b"]],
                        "order": order, "group": group["group"], "backend": group["backend"],
                        "agent": group["agent"], "checkpoint": group["checkpoint"],
                        "benchmark": item["benchmark"], "document_id": doc_id, "item_id": item["item_id"],
                        "rule_id": item["rule_id"], "span_a": [first["start"], first["end"]],
                        "span_b": [second["start"], second["end"]], "system": None,
                        "max_new_tokens": config["max_new_tokens"], "user": user,
                        "user_sha256": doc_judge._sha(user)})
    value = {"schema": doc_judge.SCHEMA, "kind": doc_judge.KIND, "config": config,
             "config_sha256": doc_judge._sha(doc_judge._canonical(config)), "documents": documents,
             "prompts": prompts, "prompt_count": len(prompts), "ranked_by": "embedding",
             "reads": "the staged workloads only: no answer key, no reply, no label"}
    doc_judge._write_json(out, value)
    doc_judge.load_prompts(out)
    return value


def finished_pass(prompts_path, run_dir):
    """(prompts file, {prompt id: row}, {call id: reply record}) of a whole pass. A pass that is not
    complete, or not of these prompts, is refused: a stopped pass would leave its last documents
    unflagged and count them as read."""
    import reply_records
    value = doc_judge.read_file(prompts_path)
    run_dir = Path(run_dir)
    measurement = json.loads((run_dir / doc_judge.MEASUREMENT_FILE).read_text(encoding="utf-8"))
    if measurement.get("schema") != doc_judge.MEASUREMENT_SCHEMA or measurement.get("prompts_sha256") != _digest(prompts_path):
        raise ValueError("the pass folder is not a pass of these prompts")
    if measurement.get("complete") is not True:
        raise ValueError("the pass is not complete")
    records = {r.get("call_id"): r for r in reply_records.records(run_dir / "audit" / "model_replies")}
    return value, {r["prompt_id"]: r for r in measurement.get("rows") or []}, records


def read_calls(prompts_path, run_dir):
    """Each pair prompt with its class: FLAG, CLEAR, UNDECIDED, or None when it cannot be read."""
    value, seen, records = finished_pass(prompts_path, run_dir)
    rows = []
    for p in value["prompts"]:
        row = seen.get(p["prompt_id"]) or {}
        record = records.get(row.get("call_id"))
        reply = (record or {}).get("reply") or {}
        text = reply.get("text") if isinstance(reply, dict) else None
        parsed = doc_judge.parse_reply(text, value["config"]) if record and record.get("backend_ok") else None
        cls = doc_judge.outcome_class(value["config"], parsed["outcome"]) if parsed and parsed["outcome"] else None
        rows.append({"document_id": p["document_id"], "item_id": p["item_id"], "group": p["group"],
                     "pair": tuple(p["pair"]), "order": p["order"], "cls": cls,
                     "ran_out": row.get("length_reached_allowance") is True})
    return value, rows


def flagged_pairs(rows, view):
    """The pairs of one document's calls flagged in `view`."""
    orders = {}
    for r in rows:
        orders.setdefault(r["pair"], []).append(r["cls"])
    wanted = all if view == BAR_VIEW else any
    return {pair for pair, classes in orders.items() if len(classes) == 2 and wanted(c == "FLAG" for c in classes)}


def place(pairs, marks):
    """Where a gold document's flags stand. `marks` is the scorer's {marked, partner, references}."""
    marked, partner = set(marks["marked"]), set(marks["partner"])
    if not marked:
        return "not_measurable"
    if not partner:
        return "no_partner"
    if marked == partner and len(marked) == 1:
        return "one_passage"
    if not pairs:
        return "none"
    if any((a in marked and b in partner) or (a in partner and b in marked) for a, b in pairs):
        return "partner"
    return "touch" if any(set(p) & marked for p in pairs) else "wrong_place"


def counts(flags, gold, places):
    """The document and place counts of one view. `flags` is {document: pairs}."""
    right = sum(1 for d, pairs in flags.items() if pairs and gold[d])
    false = sum(1 for d, pairs in flags.items() if pairs and not gold[d])
    tally = {}
    for d in gold:
        if gold[d]:
            tally[places[d]] = tally.get(places[d], 0) + 1
    items, golds = len(gold), sum(gold.values())
    placed = tally.get("partner", 0)
    return {"items": items, "gold": golds, "right": right, "false": false, "flagged": right + false,
            "net": right - false, "placed": placed, "flagged_with_two_marks": placed + tally.get("touch", 0) + tally.get("wrong_place", 0),
            "places": tally, "precision": round(right / (right + false), 6) if right + false else None,
            "chance_tail": round(doc_judge.chance_tail([(items, golds, right + false)], right), 6)}


def control(value, gold, flagged):
    """The Python-only control: the `flagged` documents with the highest top pair score."""
    ranked = sorted(gold, key=lambda d: (-value["documents"][d].get("top_score", 0.0), d))[:flagged]
    right = sum(gold[d] for d in ranked)
    return {"flagged": flagged, "right": right, "false": flagged - right, "net": 2 * right - flagged}


def comparator(path):
    """The same model bare, from J1's result: per group its figures on the 60 documents; the group
    with the higher net is the one to beat, and B1 past the abstain floor is no comparator."""
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for group, views in sorted((result.get("views") or {}).items()):
        m = views["b1_all"][BENCHMARK]
        rows.append({"group": group, "right": m["flag_tp"], "false": m["flag_fp"], "abstain": m["abstain"],
                     "items": m["items"], "net": m["flag_tp"] - m["flag_fp"]})
    if not rows:
        raise ValueError("no comparator in the J1 result")
    return max(rows, key=lambda r: (r["net"], r["group"])), rows


def verdict(row, readable, b1, python, bar=BAR):
    """The bar, written before any reply: every condition, then keep or not_kept; void when B1 is
    no comparator."""
    b1_flags = b1["right"] + b1["false"]
    tests = {"readable": readable >= bar["readable_at_least"],
             "flagged": row["flagged"] <= bar["flagged_share_at_most"] * row["items"],
             "placed": row["placed"] >= bar["placed_at_least"],
             "placed_share": 2 * row["placed"] >= row["flagged_with_two_marks"],
             "net_above_b1": row["net"] > b1["net"],
             "precision": b1_flags < bar["b1_flags_for_precision"] or row["right"] * b1_flags >= b1["right"] * row["flagged"],
             "net_above_python": row["net"] > python["net"],
             "chance": row["chance_tail"] <= bar["chance_at_most"]}
    void = b1["abstain"] > doc_judge.BAR_MAX_B1_ABSTAIN * b1["items"]
    return {"tests": tests, "void": void, "result": "void" if void else "keep" if all(tests.values()) else "not_kept",
            "means": "whether the step stays in the harness; no target is met by it"}


def read(prompts_path, run_dir, keys, bar_path, b1_path, source, out):
    sc = doc_judge._score_corpus()
    out = Path(out)
    if (out / RESULT_FILE).exists():
        raise ValueError("this folder already holds a result")
    bar = json.loads(Path(bar_path).read_text(encoding="utf-8"))
    if bar.get("thresholds") != BAR:
        raise ValueError("the bar states other figures than D-276's")
    for name, got in (("prompts_sha256", _digest(prompts_path)), ("b1_sha256", _digest(b1_path)),
                      ("source_sha256", _digest(source)), ("keys_sha256", doc_judge.keys_digest(sc, keys))):
        if bar.get(name) != got:
            raise ValueError("the bar names other inputs: " + name)
    value, rows = read_calls(prompts_path, run_dir)
    gold, places_of, marks = {}, {}, {}
    for key in keys:
        table = sc.item_table(key)
        doc_id = table["document_id"]
        if doc_id not in value["documents"]:
            continue
        item = table["items"][0]
        gold[doc_id] = bool(sc.item_is_flag(key, item["item_id"]))
        passages = passage_pairs.passages(value["documents"][doc_id]["text"])
        marks[doc_id] = sc.marked_passages(key, item["item_id"], [p["text"] for p in passages], source)
    if set(gold) != set(value["documents"]):
        raise ValueError("the keys do not cover the prompts' documents")
    readable = sum(r["cls"] is not None for r in rows) / len(rows)
    clear_calls = [r for r in rows if not gold[r["document_id"]]]
    both = {}
    for r in rows:
        both.setdefault((r["document_id"], r["pair"]), []).append(r["cls"])
    two = [c for c in both.values() if len(c) == 2 and None not in c]
    result = {"schema": "pair-judge-read-v1", "prompts_sha256": bar["prompts_sha256"], "calls": len(rows),
              "readable": round(readable, 6), "ran_to_allowance": sum(r["ran_out"] for r in rows),
              "cannot_tell": sum(r["cls"] == "UNDECIDED" for r in rows),
              "contradict_calls": sum(r["cls"] == "FLAG" for r in rows),
              "contradict_rate_on_clear": round(sum(r["cls"] == "FLAG" for r in clear_calls) / max(len(clear_calls), 1), 6),
              "orders_agree": round(sum(c[0] == c[1] for c in two) / max(len(two), 1), 6), "views": {}}
    for view in VIEWS:
        flags = {d: flagged_pairs([r for r in rows if r["document_id"] == d], view) for d in gold}
        for d in gold:
            if gold[d]:
                places_of[d] = place(flags[d], marks[d])
        row = counts(flags, gold, places_of)
        pairs = sum(len(p) for p in flags.values())
        holding = sum(1 for d in gold if gold[d] for p in flags[d] if set(p) & set(marks[d]["marked"]))
        row.update(pairs_flagged=pairs, pairs_on_marked=holding,
                   pairs_per_flagged_document=round(pairs / max(row["flagged"], 1), 3))
        result["views"][view] = row
    b1, b1_rows = comparator(b1_path)
    python = control(value, gold, result["views"][BAR_VIEW]["flagged"])
    result.update(b1=b1, b1_rows=b1_rows, python_control=python,
                  verdict=verdict(result["views"][BAR_VIEW], readable, b1, python))
    doc_judge._write_json(out / RESULT_FILE, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--workload", action="append", required=True)
    b.add_argument("--items", action="append", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--config", default=str(CONFIG_PATH))
    r = sub.add_parser("read")
    r.add_argument("--prompts", required=True)
    r.add_argument("--run", required=True)
    r.add_argument("--key", action="append", required=True)
    r.add_argument("--bar", required=True)
    r.add_argument("--b1", required=True)
    r.add_argument("--source", required=True)
    r.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        value = build(args.workload, args.items, args.out, args.config)
        print("prompts", value["prompt_count"], "documents", len(value["documents"]))
    else:
        print(json.dumps(read(args.prompts, args.run, args.key, args.bar, args.b1, args.source, args.out)["verdict"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
