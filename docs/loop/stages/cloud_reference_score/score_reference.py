"""Score the cloud reference and J1's local pass on half A, through cloud_reference.read (judge_read's
functions, the scorer) and J1's bar functions (judge_read.agent_row, decide) on half A counts.
Keys are passed to tools/score_corpus.py only (through label_rows and choice_read.universe)."""
import hashlib
import json
import sys
from pathlib import Path

CODE = Path(sys.argv[1])
OUT = Path(sys.argv[2])
sys.path[:0] = [str(CODE / "scripts"), str(CODE / "tools"), str(CODE / "benchmark" / "baselines"),
                str(CODE / "benchmark" / "adapters")]
import cloud_reference as cr  # noqa: E402
import judge_read  # noqa: E402
import reply_records  # noqa: E402

def main_checkout(code):
    """The main checkout, from git's common directory of the tree that holds the code."""
    import subprocess
    done = subprocess.run(["git", "-C", str(code), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                          capture_output=True, text=True, check=True)
    return Path(done.stdout.strip()).resolve().parent


def relative(path):
    """A path as the repository names it: relative to the checkout that holds it, never absolute."""
    path = Path(path).resolve()
    for root in (CODE.resolve(), MAIN):
        if path.is_relative_to(root):
            return path.relative_to(root).as_posix()
    return path.name


MAIN = main_checkout(CODE)
PROMPTS = MAIN / "external/s05/J1/j1_prompts.json"
BAR = MAIN / "external/s05/J1/j1_bar.json"
ITEMS = CODE / "benchmark/baselines/g1_bar_items.json"
KEYS = sorted(str(p) for p in (MAIN / "external/s05/G1/build").glob("*/*/answer_key.json"))
RUNS = {"reference": CODE / "output/cloud_reference/opus48-half-a-1",
        "j1_local": MAIN / "external/s05/J1/ev/evidence/b1/j1"}


def bar_rows(run_dir, split):
    """J1's bar (agent_row, decide) on half A: counts and B1-on-agent-items from half A prompts only."""
    value, bar = cr.load(PROMPTS, BAR)
    value_a = dict(value, prompts=[p for p in value["prompts"] if p["document_id"] in split[p["benchmark"]][0]])
    measurement = json.loads((Path(run_dir) / cr.MEASUREMENT_FILE).read_text(encoding="utf-8"))
    records = {r.get("call_id"): r for r in reply_records.records(Path(run_dir) / "audit" / "model_replies")}
    by_prompt = {r["prompt_id"]: r for r in measurement["rows"]}
    per_item, counts = judge_read.agent_rows(value_a, by_prompt, records)
    left_out = set(bar.get("left_out") or ())
    groups = [g["group"] for g in value["config"]["models"]]
    rows, figures = {}, {}
    agent_items = {k[5] for k in per_item}
    for group in groups:
        mine = []
        for (v, g, benchmark, document_id, rule_id, item_id), calls in per_item.items():
            if (v, g) == ("judge", group):
                cls, source = judge_read.item_class(calls)
                mine.append({"document_id": document_id, "item_id": item_id, "benchmark": benchmark, "cls": cls,
                             "source": source})
        judged = judge_read.figures(judge_read.label_rows(mine, KEYS, OUT / "bar_labels", left_out,
                                                          "%s_%s_judge" % (Path(run_dir).name, group)),
                                    judge_read.G1_SETTINGS)
        bare = [dict(r, cls=None) for r in judge_read.b1_rows(value_a, by_prompt, records) if r["group"] == group]
        bare_scored = judge_read.label_rows(bare, KEYS, OUT / "bar_labels", left_out, "%s_%s_b1" % (Path(run_dir).name, group))
        figures[group] = {"judge": judged,
                          "b1_on_agent_items": judge_read.figures([r for r in bare_scored if r["item_id"] in agent_items],
                                                                judge_read.G1_SETTINGS)}
    product_b1 = next(g["group"] for g in value["config"]["models"] if g.get("reasoning"))
    for benchmark in judge_read.BENCHMARKS:
        rows[benchmark] = {g: judge_read.agent_row(figures[g]["judge"][benchmark], counts[(g, benchmark)],
                                                   figures[product_b1]["b1_on_agent_items"][benchmark],
                                                   bar["c1_net"][benchmark]) for g in groups}
    verdict, variant = judge_read.decide(rows)
    return {"rows": rows, "verdict": verdict, "variant_for_j2": variant,
            "call_counts": {"%s/%s" % k: v for k, v in counts.items()}}


def main():
    value, bar = cr.load(PROMPTS, BAR)
    split, _ = cr.halves(value, ITEMS, KEYS)
    out = {"label": cr.LABEL, "labels": ["a paid cloud model on development items already read", "exposed",
                                         "in-sample: half A chose C's thresholds (REPORT_COMPARABILITY 3a)",
                                         "not Shimmer's performance"],
           "half": "A", "half_a_documents": {b: sorted(a) for b, (a, bb) in split.items()},
           "prompts_sha256": cr.sha(PROMPTS), "bar_sha256": cr.sha(BAR), "items_sha256": cr.sha(ITEMS),
           "keys": len(KEYS), "code": {}, "runs": {}}
    import subprocess
    for f in ("benchmark/baselines/cloud_reference.py", "benchmark/baselines/judge_read.py", "tools/score_corpus.py",
              "benchmark/baselines/doc_judge.py", "benchmark/baselines/choice_read.py"):
        out["code"][f] = subprocess.run(["git", "-C", str(CODE), "hash-object", f], capture_output=True, text=True).stdout.strip()
    for name, run_dir in RUNS.items():
        figures = cr.read(PROMPTS, BAR, ITEMS, run_dir, KEYS, OUT / name, name)
        measurement = json.loads((run_dir / cr.MEASUREMENT_FILE).read_text(encoding="utf-8"))
        out["runs"][name] = {"run_dir": relative(run_dir), "measurement_sha256": cr.sha(run_dir / cr.MEASUREMENT_FILE),
                             "models": figures["models"], "views": figures["views"],
                             "bar_on_half_a": bar_rows(run_dir, split)}
        if name == "reference":
            out["runs"][name].update(spent_usd=measurement["spent_usd"], seconds=measurement["seconds"],
                                     sent=measurement["sent"], complete=measurement["complete"],
                                     reached_allowance=sum(1 for r in measurement["rows"] if r.get("length_reached_allowance")),
                                     input_tokens=sum(r.get("input_tokens") or 0 for r in measurement["rows"]),
                                     output_tokens=sum(r.get("output_tokens") or 0 for r in measurement["rows"]))
    (OUT / "cloud_reference_score.json").write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n",
                                                    encoding="utf-8")
    print("written")


main()
