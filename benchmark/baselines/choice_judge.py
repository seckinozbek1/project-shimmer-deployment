"""D-S41 on a replay: narrow questions decided from a model's next-token probabilities.

An evaluation tool, not a review and not an arm (development, exposed). It rides doc_judge.py's
replay pass (form `choice`), so no bound controller file changes. A pass saves each question's
probabilities on its reply record; no threshold is applied and nothing here scores anything.

  build (no model; the embedding model on this machine when pairs are built)
      py -3.12 benchmark/baselines/choice_judge.py build [--pairs-from PROMPTS.json]
          [--pair-workload W --pair-items I ...] [--claim-workload W --claim-items I ...]
          [--permuted-half-a] --out prompts.json [--config F]
    Pairs: the first `limit` pairs of passage_pairs.propose, in both orders, as pair_judge.py
    builds them (contradicts, does not, cannot tell). --pairs-from takes the same pairs from a
    prompts file pair_judge.py built, each document's text and passages as they stand there, so a
    decision is measured on the very pairs a reply was and nothing is encoded again.
    --permuted-half-a adds, for half A's documents and claims alone (the bar's split), the same
    questions with the answer lines moved, marked `order_control`, after every other prompt. They
    ride the same pass; choice_read.py reports how far the answers moved and reads them for nothing
    else. Claims: one prompt per rule of a workload,
    the claim read back out of its adapter's RULE_TEMPLATE and put on the cells
    doc_judge.select_cells chose (holds, not met, cannot be settled). Reads no key.

  decisions (no model, no key)
      py -3.12 benchmark/baselines/choice_judge.py decisions --prompts P --run R --out F
    Each half A prompt with the decision its reply record saved, or None for a failed call; half B
    is the reader's alone. A pass that is not complete, or not of these prompts, is refused.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / "scripts"), str(HERE.parents[1] / "tools")]

import doc_judge  # noqa: E402
import pair_judge  # noqa: E402
import passage_pairs  # noqa: E402

CONFIG_PATH = HERE / "choice_judge_prompt.json"


def _prompt(group, doc_id, item, kind, user, **fields):
    return dict({"form": doc_judge.CHOICE_FORM, "choice": kind, "group": group["group"], "backend": group["backend"],
                 "agent": group["agent"], "checkpoint": group["checkpoint"], "benchmark": item["benchmark"],
                 "document_id": doc_id, "item_id": item["item_id"], "rule_id": item["rule_id"], "system": None,
                 "max_new_tokens": 0, "user": user, "user_sha256": doc_judge._sha(user)}, **fields)


def _pair_prompts(config, doc_id, document, item, passages, pairs):
    out = []
    for group in config["models"]:
        for pair in pairs:
            a, b = passages[pair["a"]], passages[pair["b"]]
            for order, first, second in (("ab", a, b), ("ba", b, a)):
                user = doc_judge.render_choice(config, "pair", {"passage_a": first["text"], "passage_b": second["text"]})
                out.append(_prompt(group, doc_id, item, "pair", user, pair_id="%d-%d-%s" % (pair["a"], pair["b"], order),
                                   pair=[pair["a"], pair["b"]], order=order, span_a=[first["start"], first["end"]],
                                   span_b=[second["start"], second["end"]]))
    return out


def _pairs_from(config, path):
    """(documents, prompts) of the pairs a pair_judge.py file holds, in its own order."""
    value = doc_judge.read_file(path)
    documents, prompts, seen = {}, [], set()
    for p in value["prompts"]:
        key = (p["document_id"], p.get("pair_id"))
        if p.get("form") != doc_judge.PAIR_FORM or key in seen:
            continue
        seen.add(key)
        document = documents[p["document_id"]] = value["documents"][p["document_id"]]
        first, second = doc_judge.pair_passages(document, p)
        user = doc_judge.render_choice(config, "pair", {"passage_a": first, "passage_b": second})
        for group in config["models"]:
            prompts.append(_prompt(group, p["document_id"], p, "pair", user, pair_id=p["pair_id"], pair=p["pair"], order=p["order"],
                                   span_a=p["span_a"], span_b=p["span_b"]))
    if not prompts:
        raise ValueError("the file holds no pair prompt")
    return documents, prompts


def order_controls(config, documents, prompts):
    """Each half A prompt again with its answer lines moved. The split is the bar's, per benchmark."""
    import choice_read
    half_a = {d for a, _ in choice_read.split(documents).values() for d in a}
    out = []
    for p in prompts:
        if p["document_id"] in half_a:
            moved = dict(p, order_control=True, pair_id=str(p.get("pair_id") or "claim") + "-order")
            moved["user"] = doc_judge.choice_user(config, documents[p["document_id"]], moved)
            moved["user_sha256"] = doc_judge._sha(moved["user"])
            out.append(moved)
    return out


def claim_of(benchmark, rule_text):
    """The claim inside a rule, read against its adapter's RULE_TEMPLATE: the rest of that template
    tells a model how to answer in another form than this one."""
    template = getattr(doc_judge._adapter(benchmark), "RULE_TEMPLATE", "")
    if template.count("{claim}") != 1:
        raise ValueError("the adapter of %s declares no claim template" % benchmark)
    head, tail = template.split("{claim}")
    if not (rule_text.startswith(head) and rule_text.endswith(tail)) or len(rule_text) <= len(head) + len(tail):
        raise ValueError("a rule is not its adapter's claim template")
    return rule_text[len(head):len(rule_text) - len(tail)]


def _claim_prompts(config, workload, items_path):
    workload = Path(workload)
    target = doc_judge._targets(workload)
    doc_id = Path(target).stem
    text = doc_judge._document_text(workload / "context" / target)
    rows = {r.get("rule_id"): r for r in doc_judge._items(items_path, doc_id)}
    rules = doc_judge.workload_rules(workload)
    if set(rows) != set(rules):
        raise ValueError("the item table and the rules of %s differ" % doc_id)
    benchmark = {str(r.get("benchmark")).lower() for r in rows.values()}
    if len(benchmark) != 1:
        raise ValueError("the items of %s name more than one benchmark" % doc_id)
    benchmark = benchmark.pop()
    document = {"benchmark": benchmark, "target": target, "text": text, "sha256": doc_judge._sha(text), "conventions": []}
    out, refused, chosen = [], [], {}
    for rule_id, rule_text in rules.items():
        claim = claim_of(benchmark, rule_text)
        try:
            chosen[rule_id] = (claim, doc_judge.select_cells(text, claim))
        except doc_judge.CellsRefused as exc:
            refused.append({"document_id": doc_id, "item_id": rows[rule_id]["item_id"], "rule_id": rule_id, "reason": str(exc)})
    for group in config["models"]:
        for rule_id, (claim, cells) in chosen.items():
            user = doc_judge.render_choice(config, "claim", {"cells": cells["cells"], "claim": claim})
            out.append(_prompt(group, doc_id, dict(rows[rule_id], benchmark=benchmark), "claim", user, claim=claim,
                               selection={k: v for k, v in cells.items() if k != "cells"}))
    return doc_id, document, out, refused


def cell_counts(prompts, refused):
    """Claims by how their cells were chosen, each once, and those refused: a whole table is
    reported apart, since it is no selection."""
    ways = {p["item_id"]: p["selection"]["selected_by"] for p in prompts if p.get("choice") == "claim"}
    out = {way: list(ways.values()).count(way) for way in sorted(set(ways.values()))}
    out["refused"] = len(refused)
    return out


def _paired(workloads, items):
    workloads, items = list(workloads or ()), list(items or ())
    if len(workloads) != len(items):
        raise ValueError("one items file per workload, in the same order")
    return list(zip(workloads, items))


def build(out, *, pair_workloads=(), pair_items=(), claim_workloads=(), claim_items=(), config_path=CONFIG_PATH,
          embed=passage_pairs.embed, pairs_from=None, permuted_half_a=False):
    config = doc_judge.check_config(json.loads(Path(config_path).read_text(encoding="utf-8")))
    documents, prompts = _pairs_from(config, pairs_from) if pairs_from else ({}, [])
    refused = []
    for workload, items_path in _paired(pair_workloads, pair_items):
        doc_id, document, item, passages, pairs = pair_judge.proposed(
            workload, items_path, config["choice"]["forms"]["pair"]["limit"], embed)
        documents[doc_id] = document
        prompts += _pair_prompts(config, doc_id, document, item, passages, pairs)
    for workload, items_path in _paired(claim_workloads, claim_items):
        doc_id, document, made, not_asked = _claim_prompts(config, workload, items_path)
        refused += not_asked
        if doc_id in documents:
            raise ValueError("a document is named twice: " + doc_id)
        documents[doc_id] = document
        prompts += made
    if not prompts:
        raise ValueError("no prompt to build")
    if permuted_half_a:
        prompts += order_controls(config, documents, prompts)
    for number, prompt in enumerate(prompts, 1):
        prompt["prompt_id"] = "d%06d" % number
    value = {"schema": doc_judge.SCHEMA, "kind": doc_judge.KIND, "config": config,
             "config_sha256": doc_judge._sha(doc_judge._canonical(config)), "documents": documents, "prompts": prompts,
             "prompt_count": len(prompts), "refused_claims": refused, "cell_counts": cell_counts(prompts, refused), "reads": "the staged workloads only: no answer key, no reply, no label"}
    doc_judge._write_json(out, value)
    doc_judge.load_prompts(out)
    return value


def decisions(prompts_path, run_dir):
    """Each half A prompt's identifiers with the decision its reply record saved. No key, no score.
    Half B's decisions are read by choice_read.py's read-b alone, once: none is listed here."""
    import choice_read
    value, seen, records = pair_judge.finished_pass(prompts_path, run_dir)
    half_a = {d for a, _ in choice_read.split(value["documents"]).values() for d in a}
    rows = []
    for p in value["prompts"]:
        if p["document_id"] not in half_a:
            continue
        record = records.get((seen.get(p["prompt_id"]) or {}).get("call_id")) or {}
        rows.append({"prompt_id": p["prompt_id"], "choice": p.get("choice"), "group": p["group"], "document_id": p["document_id"],
                     "item_id": p["item_id"], "rule_id": p["rule_id"], "pair": p.get("pair"), "order": p.get("order"),
                     "order_control": p.get("order_control") is True,
                     "decision": record.get("decision") if record.get("backend_ok") else None})
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    for name in ("--pair-workload", "--pair-items", "--claim-workload", "--claim-items"):
        b.add_argument(name, action="append")
    b.add_argument("--pairs-from")
    b.add_argument("--permuted-half-a", action="store_true")
    b.add_argument("--out", required=True)
    b.add_argument("--config", default=str(CONFIG_PATH))
    d = sub.add_parser("decisions")
    d.add_argument("--prompts", required=True)
    d.add_argument("--run", required=True)
    d.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        value = build(args.out, pair_workloads=args.pair_workload, pair_items=args.pair_items, claim_workloads=args.claim_workload,
                      claim_items=args.claim_items, config_path=args.config, pairs_from=args.pairs_from, permuted_half_a=args.permuted_half_a)
        print("prompts", value["prompt_count"], "documents", len(value["documents"]))
    else:
        rows = decisions(args.prompts, args.run)
        doc_judge._write_json(args.out, rows)
        print("decisions", sum(r["decision"] is not None for r in rows), "of", len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
