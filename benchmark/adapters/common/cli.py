"""The commands every adapter shares.

  build  --input <benchmark file> --out <empty folder> --side development|holdout
         --max-context N --output-allowance N --token-counter <file.py> [--b1-prompt F]
         [--assignment <split file>] [--testmini <file>]
         or, for synthetic or development work only, --development (no budget needed,
         side unchecked unless --side is given; recorded in parts.json)
  split  --input <benchmark file> [--out F]     the side of every document (section 1)
  label  --items <items.json> --arm B0|B1|B2|B3|B4 [--runs <folder>] --out <labels.json>
  score  --labels <labels.json> --bundles <build folder> --out <metrics.json>

The cut budget is computed per document (section 5.3) from the bundle's own conventions
with the B1 prompt (common/prompt.py). A token counter file defines `count(text) -> int`
and `count_prompt(system, user) -> int` with the main reading agent's own tokenizer and
chat template. `label` writes the primary labels and the S-1 and S-2 analyses in one
file; `score` scores each of them. For B2, B3 and B4, `--runs` holds one run folder per
document named by its opaque document id; for B1, one bare_model.py output folder per
document, named the same way. B3 and B4 are refused while the typed-record key of the
pipeline's output is not settled (preregistration section 12 item 9).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from . import bundle, cut, ids, mapping, metrics, prompt

EXIT_FAULT = 3
EXIT_REFUSED = 4


def load_counter(path):
    spec = importlib.util.spec_from_file_location("adapter_token_counter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ("count", "count_prompt"):
        if not callable(getattr(module, name, None)):
            raise ValueError("the token counter file defines no " + name)
    return module


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def budget_function(counter, max_context, output_allowance, b1_prompt=None):
    """budget_for(doc) -> (budget, prompt overhead) for one document (section 5.3)."""
    spec = prompt.load_prompt(b1_prompt)

    def budget_for(doc):
        conventions = prompt.conventions_from_text(bundle.render_rules(doc["rules"]))
        items = [{"item_id": i["item_id"], "rule_id": i["rule_id"], "benchmark": doc["benchmark"]}
                 for i in doc["items"]]
        overhead = prompt.overhead(spec, items, conventions, counter.count_prompt)
        return cut.budget(max_context, overhead, output_allowance), overhead
    return budget_for


def build(adapter, input_path, out_dir, *, side=None, max_context=None, output_allowance=None,
          token_counter=None, b1_prompt=None, development=False, assignment=None,
          testmini=None) -> dict:
    budget_given = [v is not None for v in (max_context, output_allowance, token_counter)]
    if not development:
        if side not in (ids.DEVELOPMENT, ids.HOLDOUT):
            raise ValueError("--side development|holdout is required (or --development)")
        if not all(budget_given):
            raise ValueError("--max-context, --output-allowance and --token-counter are required: "
                             "the cut rule (section 5.3) is never skipped outside --development")
    elif any(budget_given) and not all(budget_given):
        raise ValueError("give all of --max-context, --output-allowance and --token-counter, or none")
    options = {"side": side, "assignment": assignment, "testmini": testmini,
               "development": development}
    records = adapter.read_source(input_path)
    documents = adapter.documents(records, options)
    for doc in documents:
        doc["benchmark"] = adapter.BENCHMARK
    extra = {"development_build": bool(development)}
    cut_plan = None
    if all(budget_given):
        counter = load_counter(token_counter) if isinstance(token_counter, (str, Path)) else token_counter
        cut_plan = (counter.count, budget_function(counter, max_context, output_allowance, b1_prompt))
        extra["cut_inputs"] = {
            "max_context": int(max_context), "output_allowance": int(output_allowance),
            "b1_prompt_sha256": _sha(b1_prompt or prompt.DEFAULT_PROMPT),
            "token_counter_sha256": _sha(token_counter) if isinstance(token_counter, (str, Path)) else None}
    if assignment:
        extra["assignment_sha256"] = _sha(assignment)
    if testmini:
        extra["testmini_sha256"] = _sha(testmini)
    return bundle.write_bundles(out_dir, adapter.BENCHMARK, documents, cut_plan,
                                declared_side=side if side in (ids.DEVELOPMENT, ids.HOLDOUT) else None,
                                build_extra=extra)


def label(adapter, items_path, arm, runs_root=None) -> dict:
    items = mapping.read_items(items_path)
    foreign = sorted({str(i.get("benchmark")) for i in items} - {adapter.BENCHMARK})
    if foreign:
        raise ValueError("items of another benchmark: " + ", ".join(foreign))
    if arm == "B0":
        primary = mapping.label_b0(adapter.SPEC, items)
    elif arm == "B1":
        primary = mapping.label_b1(adapter.SPEC, items, runs_root)
    elif arm in mapping.ARMS:
        if arm in mapping.PIPELINE_ARMS and not mapping.TYPED_RECORDS_SETTLED:
            raise mapping.Refused(
                "arm %s is refused: the key that carries the pipeline's typed records in "
                "review_data.json is not settled (preregistration section 12 item 9); the "
                "provisional key %r is what B2 writes" % (arm, mapping.TYPED_RECORDS_KEY))
        primary = mapping.label_pipeline_arm(adapter.SPEC, items, runs_root, arm)
    else:
        raise ValueError("unknown arm " + repr(arm))
    return {"primary": primary, "S-1": mapping.sensitivity_s1(adapter.SPEC, primary),
            "S-2": mapping.sensitivity_s2(adapter.SPEC, primary)}


def score(adapter, labels: dict, bundles_dir) -> dict:
    return {name: metrics.score_arm(adapter.SPEC, result, bundles_dir, adapter.headline)
            for name, result in labels.items()}


def faults_of(labels: dict) -> list:
    primary = labels["primary"]
    found = [("%s: %s" % (d["document_id"], f)) for d in primary["documents"] for f in d["faults"]]
    found += [("%s: %s" % (r["item_id"], f)) for r in primary["labels"] for f in r["faults"]]
    return found


def _write(path, data):
    bundle.write_json(Path(path), data)


def main(adapter, argv=None) -> int:
    parser = argparse.ArgumentParser(prog=adapter.BENCHMARK, description=adapter.__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--input", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--side", choices=(ids.DEVELOPMENT, ids.HOLDOUT))
    b.add_argument("--max-context", type=int)
    b.add_argument("--output-allowance", type=int)
    b.add_argument("--token-counter")
    b.add_argument("--b1-prompt")
    b.add_argument("--assignment", help="the frozen split file written by `split --out` (ContraDoc)")
    b.add_argument("--testmini", help="FinDVer: the testmini file; overlapping reports are refused")
    b.add_argument("--development", action="store_true",
                   help="synthetic or development work only: no budget needed, recorded")
    s = sub.add_parser("split")
    s.add_argument("--input", required=True)
    s.add_argument("--out")
    for name, help_text in getattr(adapter, "SPLIT_OPTIONS", ()):
        s.add_argument(name, help=help_text)
    lab = sub.add_parser("label")
    lab.add_argument("--items", required=True)
    lab.add_argument("--arm", required=True, choices=mapping.ARMS)
    lab.add_argument("--runs")
    lab.add_argument("--out", required=True)
    sc = sub.add_parser("score")
    sc.add_argument("--labels", required=True)
    sc.add_argument("--bundles", required=True)
    sc.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            print(json.dumps(build(
                adapter, args.input, args.out, side=args.side, max_context=args.max_context,
                output_allowance=args.output_allowance, token_counter=args.token_counter,
                b1_prompt=args.b1_prompt, development=args.development,
                assignment=args.assignment, testmini=args.testmini), indent=2))
            return 0
        if args.command == "split":
            rows = adapter.split_rows(adapter.read_source(args.input), args)
            if args.out:
                _write(args.out, {"benchmark": adapter.BENCHMARK, "input_sha256": _sha(args.input),
                                  "documents": rows})
            else:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            return 0
        if args.command == "label":
            if args.arm != "B0" and not args.runs:
                parser.error("--runs is required for arm " + args.arm)
            labels = label(adapter, args.items, args.arm, args.runs)
            _write(args.out, labels)
            found = faults_of(labels)
            print(json.dumps(labels["primary"]["counts"], indent=2))
            if found:
                print("adapter faults (%d): %s" % (len(found), "; ".join(found[:10])), file=sys.stderr)
                return EXIT_FAULT
            return 0
        if args.command == "score":
            labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
            result = score(adapter, labels, args.bundles)
            _write(args.out, result)
            print(json.dumps({k: v["headline"] for k, v in result.items()}, indent=2))
            return 0
    except (mapping.Refused, ValueError) as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return EXIT_REFUSED
    return 2
