"""The commands every adapter shares.

  build  --input <benchmark file> --out <empty folder> [--cut-budget N --token-counter F]
  split  --input <benchmark file> [--out F]          the side of every document (section 1)
  label  --items <items.json> --arm B0|B1|B2|B3|B4 [--runs <folder>] --out <labels.json>
  score  --labels <labels.json> --bundles <build folder> --out <metrics.json>

`label` writes the primary labels and the S-1 and S-2 analyses in one file; `score`
scores each of them. For B2, B3 and B4, `--runs` holds one run folder per document,
named by its opaque document id; for B1, one bare_model.py output folder per document,
named the same way. A token counter file defines `count(text) -> int` with the main
reading agent's own tokenizer; without --cut-budget no cut is applied and the build
records it.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from . import bundle, mapping, metrics


def load_counter(path):
    spec = importlib.util.spec_from_file_location("adapter_token_counter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "count", None)):
        raise ValueError("the token counter file defines no count(text)")
    return module.count


def build(adapter, input_path, out_dir, cut_budget=None, token_counter=None) -> dict:
    records = adapter.read_source(input_path)
    cut = None
    if cut_budget is not None:
        if token_counter is None:
            raise ValueError("--cut-budget needs --token-counter (the model's own tokenizer)")
        cut = (int(cut_budget), load_counter(token_counter) if isinstance(token_counter, (str, Path))
               else token_counter)
    return bundle.write_bundles(out_dir, adapter.BENCHMARK, adapter.documents(records), cut)


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
    b.add_argument("--cut-budget", type=int)
    b.add_argument("--token-counter")
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
    if args.command == "build":
        print(json.dumps(build(adapter, args.input, args.out, args.cut_budget, args.token_counter),
                         indent=2))
        return 0
    if args.command == "split":
        rows = adapter.split_rows(adapter.read_source(args.input), args)
        if args.out:
            _write(args.out, {"benchmark": adapter.BENCHMARK, "documents": rows})
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
            return 3
        return 0
    if args.command == "score":
        labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
        result = score(adapter, labels, args.bundles)
        _write(args.out, result)
        print(json.dumps({k: v["headline"] for k, v in result.items()}, indent=2))
        return 0
    return 2
