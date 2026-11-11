"""D-S45 attempt 1 (D-297): ContraDoc "either base + reason" on fresh development documents.

Development, exposed. One candidate, one benchmark, one comparator, one look: a document is FLAG
when the base choice judge flags it at the threshold half A fixed, .9, or B1 judge_reason flags it;
otherwise the judge's class, B1's where the judge abstains. It is tested once against the better B1
group on the fresh set (C_BAR's rule: higher accuracy, a tie to the reasoning group, a group past
D-241's abstain floor no comparator), by the exact one-sided sign test at FIGURES' alpha. The figures
live here; a bar file names the inputs by digest and states the same figures, and a read refuses
anything else. Keys are opened only by tools/score_corpus.py. The power is stated, not tested.

  build (no model but the embedding model that ranks the pairs)
      py -3.12 benchmark/baselines/either_test.py build --workload W [...] --items I --out P [--config F]
    One prompts file for one sealed B1 run: the choice pairs of every fresh document in both orders,
    group choice_direct, and B1's own prompt for each item in J1's form, groups judge_direct and
    judge_reason. The pairs are passage_pairs.propose's first `limit`, ranked by the embedding model.
  bar (no model)
      py -3.12 benchmark/baselines/either_test.py bar --prompts P --key K [...] --ids F --items I --out BAR
  read (no model; the keys through the scorer)
      py -3.12 benchmark/baselines/either_test.py read --bar BAR --prompts P --run R --key K [...] --ids F --items I --out DIR
    Read once: the read is counted in a file fixed in code, keyed on the prompts, keys and ids.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _path in (str(HERE.parents[1] / "scripts"), str(HERE.parents[1] / "tools"), str(HERE), str(HERE.parent / "adapters")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import choice_judge  # noqa: E402
import choice_read as cr  # noqa: E402
import doc_judge  # noqa: E402
import judge_read  # noqa: E402
import pair_judge  # noqa: E402
import passage_pairs  # noqa: E402

CONFIG_PATH = HERE / "ds45_prompt.json"
BAR_SCHEMA = "either-bar-v1"
RESULT = "either_result.json"
READS_FILE = "external/s05/D-S45/either_reads.jsonl"
BENCHMARK = "contradoc"
JUDGE_GROUP, B1_GROUPS, CANDIDATE_B1 = "choice_direct", ("judge_direct", "judge_reason"), "judge_reason"
# D-297: one look, one benchmark, one candidate, one comparator, so .05 one-sided; the chance tail
# at .05 for the same reason; at most 80 percent flagged; void under 95 percent readable. The power
# is the bar's statement, computed from half A's rates (6 wins, 2 losses in 30), optimistic.
FIGURES = {"alpha_one_sided": .05, "chance_at_most": .05, "flagged_share_at_most": .8, "readable_at_least": .95,
           "judge_threshold": .9, "power_at_62": .59, "power_from": "half A: 6 wins, 2 losses of 30 against judge_direct"}


def _sha(path):
    return cr._sha(path)


def build(workloads, items_path, out, config_path=CONFIG_PATH, embed=passage_pairs.embed):
    """The one prompts file of the sealed run (see the module text)."""
    import python_only
    from common import prompt as rules_text
    config = doc_judge.check_config(json.loads(Path(config_path).read_text(encoding="utf-8")))
    groups = {g["group"]: g for g in config["models"]}
    if set(groups) != {JUDGE_GROUP, *B1_GROUPS}:
        raise ValueError("the config names the choice group and both B1 groups, and no other")
    documents, prompts, cases = {}, [], []
    for workload in workloads:
        doc_id, document, item, passages, pairs = pair_judge.proposed(workload, items_path, config["choice"]["forms"]["pair"]["limit"], embed)
        document["conventions"] = [list(c) for c in rules_text.conventions_from_bundle(Path(workload))]
        documents[doc_id] = document
        for pair in pairs:
            a, b = passages[pair["a"]], passages[pair["b"]]
            for order, first, second in (("ab", a, b), ("ba", b, a)):
                user = doc_judge.render_choice(config, "pair", {"passage_a": first["text"], "passage_b": second["text"]})
                prompts.append(choice_judge._prompt(groups[JUDGE_GROUP], doc_id, item, "pair", user, pair_id="%d-%d-%s" % (pair["a"], pair["b"], order),
                                                    pair=[pair["a"], pair["b"]], order=order, span_a=[first["start"], first["end"]],
                                                    span_b=[second["start"], second["end"]]))
        cases.append({"document_id": doc_id, "benchmark": item["benchmark"], "rule_id": item["rule_id"],
                      "rule_text": doc_judge.workload_rules(Path(workload))[item["rule_id"]], "item_id": item["item_id"]})
    spec = rules_text.load_prompt()
    b1_config = dict(config, models=[groups[g] for g in B1_GROUPS])
    prompts += doc_judge._comparator_prompts(cases, documents, b1_config, spec, int(python_only.pipeline_literal("PRODUCTION_MAX_TOKENS")))
    for number, prompt in enumerate(prompts, 1):
        prompt["prompt_id"] = "e%06d" % number
    value = {"schema": doc_judge.SCHEMA, "kind": doc_judge.KIND, "config": config, "config_sha256": doc_judge._sha(doc_judge._canonical(config)),
             "documents": documents, "prompts": prompts, "prompt_count": len(prompts), "b1_prompt": spec,
             "b1_prompt_sha256": doc_judge._sha(doc_judge._canonical(spec)), "ranked_by": "embedding",
             "reads": "the staged workloads only: no answer key, no reply, no label"}
    doc_judge._write_json(out, value)
    doc_judge.load_prompts(out)
    return value


def universe(keys, ids_path, items_path):
    """{document: [item rows]} of the fresh set, through the scorer's item table, held to the ids file:
    every listed document has its one key and item, and no key is given twice."""
    sc = doc_judge._score_corpus()
    listed = json.loads(Path(ids_path).read_text(encoding="utf-8"))["documents"]
    if len({str(Path(k).resolve()) for k in keys}) != len(keys):
        raise ValueError("a key is given twice")
    items = json.loads(Path(items_path).read_text(encoding="utf-8"))
    sources = {r["document_id"]: r["source_document_id"] for r in items["items"]}
    out, by_key = {}, {}
    for key in keys:
        table = sc.item_table(key)
        if table["document_id"] in out or table["benchmark"] != BENCHMARK:
            raise ValueError("two keys name one document, or a key of another benchmark: " + table["document_id"])
        out[table["document_id"]], by_key[table["document_id"]] = table["items"], key
    if sorted(sources.get(d) for d in out) != sorted(listed):
        raise ValueError("the keys are not the fresh set's documents")
    return out, by_key


def bar_value(prompts, keys, ids_path, items_path):
    universe(keys, ids_path, items_path)
    return {"schema": BAR_SCHEMA, "figures": FIGURES, "prompts_sha256": _sha(prompts), "ids_sha256": _sha(ids_path),
            "items_sha256": _sha(items_path), "keys_sha256": doc_judge.keys_digest(doc_judge._score_corpus(), keys)}


def open_bar(bar_path, prompts, keys, ids_path, items_path):
    bar = json.loads(Path(bar_path).read_text(encoding="utf-8"))
    if bar.get("schema") != BAR_SCHEMA or bar.get("figures") != FIGURES:
        raise ValueError("the bar states other figures than the code's")
    for name, got in (("prompts_sha256", _sha(prompts)), ("ids_sha256", _sha(ids_path)), ("items_sha256", _sha(items_path)),
                      ("keys_sha256", doc_judge.keys_digest(doc_judge._score_corpus(), keys))):
        if bar.get(name) != got:
            raise ValueError("the bar names other inputs: " + name)
    return bar


def either(judge_rows, b1_rows):
    """The candidate: FLAG when either flags; else the judge's class, B1's where the judge abstains."""
    b1 = {r["item_id"]: r for r in b1_rows}
    out = []
    for j in judge_rows:
        b = b1[j["item_id"]]
        cls = cr.FLAG if cr.FLAG in (j["cls"], b["cls"]) else (j["cls"] if j["cls"] != cr.ABSTAIN else b["cls"])
        out.append({"document_id": j["document_id"], "item_id": j["item_id"], "cls": cls, "source": "either"})
    return out


def b1_group_rows(value, seen, records, group):
    """B1's labels of one group, as J1 read them: a reply run to its allowance is unreadable."""
    return [r for r in judge_read.b1_rows(value, seen, records) if r["group"] == group]


def comparator(figures):
    """C_BAR's rule over {group: figures}: the higher accuracy, a tie to the reasoning group, a group
    past D-241's abstain floor no comparator. None when none is one."""
    fit = [g for g in B1_GROUPS if figures[g]["abstain"] <= doc_judge.BAR_MAX_B1_ABSTAIN * figures[g]["items"]]
    return max(fit, key=lambda g: (figures[g]["accuracy"], g == "judge_reason")) if fit else None


def tests(candidate, other, wins, losses):
    """Every item of the bar."""
    if other["flagged"]:
        precision = candidate["precision"] is not None and candidate["right"] * other["flagged"] >= other["right"] * candidate["flagged"]
    else:
        precision = candidate["false"] == 0
    # One-sided: with more losses than wins the p-value is at least .5, so it never passes.
    return {"sign_test": cr.sign_test(wins, losses) <= FIGURES["alpha_one_sided"], "precision": precision,
            "chance": candidate["chance_tail"] <= FIGURES["chance_at_most"],
            "flagged": candidate["flagged"] <= FIGURES["flagged_share_at_most"] * candidate["items"]}


def reads_path():
    return cr.repository_root() / READS_FILE


def read_key(bar):
    return doc_judge._sha(json.dumps({k: bar[k] for k in ("prompts_sha256", "ids_sha256", "items_sha256", "keys_sha256")}, sort_keys=True))


def read(bar_path, prompts, run, keys, ids_path, items_path, out):
    bar = open_bar(bar_path, prompts, keys, ids_path, items_path)
    out = Path(out)
    if (out / RESULT).exists():
        raise ValueError("this folder already holds a result")
    key = read_key(bar)
    with cr.ReadsLock(reads_path()):
        if cr.reads_of(reads_path(), key):
            raise ValueError("this test has been read: it is read once")
        result = _read(bar, prompts, run, keys, ids_path, items_path, out)
        cr.count_read(reads_path(), key, {"inputs_sha256": key, "bar_sha256": _sha(bar_path), "result": result["result"]}, True)
    result["reads"] = cr.reads_of(reads_path(), key)
    doc_judge._write_json(out / RESULT, result)
    return result


def _read(bar, prompts, run, keys, ids_path, items_path, out):
    documents, by_key = universe(keys, ids_path, items_path)
    value, seen, records = pair_judge.finished_pass(prompts, run)
    data = cr.load(cr.BASE, {"steps": None, "files": [(prompts, run)]})
    rows = cr.within(data["rows"], BENCHMARK, documents)
    judge_view = cr.view(BENCHMARK, documents, rows, data["forms"], FIGURES["judge_threshold"])
    left_out = set()
    judge_scored, judge_figures = cr.score(judge_view, keys, out, left_out, "judge")
    b1 = {}
    for group in B1_GROUPS:
        scored = judge_read.label_rows(b1_group_rows(value, seen, records, group), keys, out, left_out, group + "_b1")
        b1[group] = {"scored": scored, "figures": cr.figures(scored)}
    candidate_scored, candidate = cr.score(either(judge_view, b1[CANDIDATE_B1]["scored"]), keys, out, left_out, "either")
    b1_replies = [r for r in judge_read.b1_rows(value, seen, records)]
    readable = {"choice_prompts": round(sum(cr.state(r) == cr.READ for r in rows) / max(len(rows), 1), 6),
                "b1_prompts": round(sum(not r["abstain"] for r in b1_replies) / max(len(b1_replies), 1), 6)}
    group = comparator({g: v["figures"] for g, v in b1.items()})
    result = {"schema": "either-result-v1", "figures": FIGURES, "documents": len(documents), "readable": readable,
              "judge": judge_figures, "b1": {g: v["figures"] for g, v in b1.items()}, "candidate": candidate, "comparator": group,
              "power_stated": FIGURES["power_at_62"], "means": "a keep says the candidate goes on; it never says the target is met"}
    if min(readable.values()) < FIGURES["readable_at_least"] or group is None:
        return dict(result, result="void")
    wins, losses = cr.discordant(candidate_scored, b1[group]["scored"])
    checks = tests(candidate, b1[group]["figures"], wins, losses)
    return dict(result, wins=wins, losses=losses, sign_test=cr.sign_test(wins, losses), tests=checks,
                result="keep" if all(checks.values()) else "drop")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--workload", action="append", required=True)
    b.add_argument("--items", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--config", default=str(CONFIG_PATH))
    for name in ("bar", "read"):
        p = sub.add_parser(name)
        p.add_argument("--prompts", required=True)
        p.add_argument("--key", action="append", required=True)
        p.add_argument("--ids", required=True)
        p.add_argument("--items", required=True)
        p.add_argument("--out", required=True)
        if name == "read":
            p.add_argument("--bar", required=True)
            p.add_argument("--run", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        value = build(args.workload, args.items, args.out, args.config)
        print("prompts", value["prompt_count"], "documents", len(value["documents"]))
    elif args.command == "bar":
        print(json.dumps(cr.write_once(args.out, bar_value(args.prompts, args.key, args.ids, args.items))))
    else:
        result = read(args.bar, args.prompts, args.run, args.key, args.ids, args.items, args.out)
        print(json.dumps({k: result.get(k) for k in ("result", "comparator", "wins", "losses", "sign_test", "tests")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
