"""The commands every adapter shares.

  build  --input <benchmark file> --out <empty folder> --side development|holdout
         --max-context N --output-allowance N --token-counter <file.py> [--b1-prompt F]
         [--assignment <split file>] [--testmini <file>] [--exclude <file>]
         [the adapter's own options: FinDVer --reports; ContractNLI --frozen-sha256, --parts]
         or, for development work only, --development (no budget needed, recorded in
         parts.json; a holdout document is refused unless --side holdout is also given)
  split  --input <benchmark file> [--out F] [--exclude <file>]   the side of every document
  bands  --input <benchmark file> [--out F] [--exclude <file>] [--testmini <file>]
         [--assignment <file>] [the adapter's own options]   every document's words, length
         band and side (section 5.6, Words) over a whole input, no build needed; band totals
         for the holdout pool alone and for the development side apart
  label  --items <items.json> --arm B0|B1|B2|B3|B4 [--runs <folder>] --out <labels.json>
  score  --labels <labels.json> --bundles <build folder> --out <metrics.json>
         [--paired-with <another arm's labels.json>]

The cut budget is computed per document (section 5.3) from the bundle's own conventions
with the B1 prompt (common/prompt.py). A token counter file defines `count(text) -> int`
and `count_prompt(system, user) -> int` with the main reading agent's own tokenizer and
chat template. `label` writes the primary labels and the S-1, S-2, S-3, S-5, S-6, S-7 and S-8
analyses in one file (S-8, DEV-012: B3 and B4 as if every model-written record were absent;
for B0, B1 and B2 it equals the primary and says so); `score` scores each of them, and S-4 from the primary labels (the items
whose marked evidence lies wholly in the kept text). A B3 document whose run made a model
call over its model's context is excluded (section 5.3, D-078): its items carry basis
over_context_excluded, the labels file lists and counts them (`over_context`), every
analysis but S-7 leaves them out, and S-7 scores them ABSTAIN. `--paired-with` adds the
paired view: the documents both arms label and neither excluded. For B2, B3 and B4, `--runs` holds one run folder per
document named by its opaque document id; for B1, one bare_model.py output folder per
document, named the same way. B2's typed records are read from review_data.json, B3's and
B4's from the run's bus (common/records.py). That reading (decision DS5-8, preregistration
section 12 item 9) was attacked and recorded (docs/loop/DECISIONS.md D-055, D-056), so
mapping.BUS_READER_ADOPTED is True; with it False, B3 and B4 are refused.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
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


def _dest(option: str) -> str:
    """The argparse destination of an option name: `--reports` gives `reports`."""
    return option.lstrip("-").replace("-", "_")


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


def read_exclusions(path) -> list:
    """The source document ids a benchmark's own paper prints as in-context examples
    (section 1), as role B identified them: a JSON list, or an object whose
    `source_document_ids` is that list."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("source_document_ids") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("the exclusion file holds no list of source document ids")
    return sorted({ids.key_string(r) for r in rows})


def apply_exclusions(documents, exclude):
    """(kept documents, excluded rows): a listed document is removed with all its items."""
    if not exclude:
        return documents, []
    listed = set(read_exclusions(exclude))
    kept, gone = [], []
    for doc in documents:
        if ids.key_string(doc["source_document_id"]) in listed:
            gone.append({"source_document_id": ids.key_string(doc["source_document_id"]),
                         "document_id": doc["document_id"], "items": len(doc["items"])})
        else:
            kept.append(doc)
    return kept, sorted(gone, key=lambda r: r["document_id"])


def _own_options(adapter, adapter_options):
    unknown = sorted(set(adapter_options) - {_dest(n) for n, _h in getattr(adapter, "BUILD_OPTIONS", ())})
    if unknown:
        raise ValueError("options this adapter does not take: " + ", ".join(unknown))


def build(adapter, input_path, out_dir, *, side=None, max_context=None, output_allowance=None,
          token_counter=None, b1_prompt=None, development=False, assignment=None,
          testmini=None, exclude=None, synthetic=False, **adapter_options) -> dict:
    """Build the bundles. `adapter_options` are the adapter's own BUILD_OPTIONS (FinDVer's
    --reports; ContractNLI's --frozen-sha256 and --parts), passed to its `documents` with
    the input path. A development build that declares no side refuses a holdout document
    (D-039 item 14). `synthetic` serves the checks' hand-written fixtures alone, which mix
    sides on purpose: with `development` it lifts that refusal and the adapter's input
    check (ContractNLI's frozen file). It is a keyword of this function only, never an
    option of the command line, and parts.json records it."""
    _own_options(adapter, adapter_options)
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
               "development": development, "input_path": str(input_path)}
    options.update({k: v for k, v in adapter_options.items() if v is not None})
    lifted = bool(development and synthetic)
    check_input = getattr(adapter, "check_input", None)
    input_check = None
    if check_input is not None and not lifted:
        input_check = check_input(input_path, side, options)
        options["frozen_for"] = input_check["frozen_for"]
    records = adapter.read_source(input_path)
    documents = adapter.documents(records, options)
    documents, excluded = apply_exclusions(documents, exclude)
    for doc in documents:
        doc["benchmark"] = adapter.BENCHMARK
    extra = {"development_build": bool(development)}
    if lifted:
        extra["synthetic_fixture_build"] = True
    if input_check is not None:
        extra["input_check"] = input_check
    if exclude:
        extra["exclusion_sha256"] = _sha(exclude)
        extra["excluded_documents"] = excluded
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
    declared = side if side in (ids.DEVELOPMENT, ids.HOLDOUT) else None
    return bundle.write_bundles(out_dir, adapter.BENCHMARK, documents, cut_plan,
                                declared_side=declared, build_extra=extra,
                                refuse_holdout=declared is None and not lifted)


REMOVED_OVERLAP = "removed_overlap"


def _band_totals(rows) -> dict:
    per_band = {}
    for name, _lower in ids.LENGTH_BANDS:
        mine = [r for r in rows if r["length_band"] == name]
        per_band[name] = {"documents": len(mine), "items": sum(r["items"] for r in mine),
                          "median_words": statistics.median([r["words"] for r in mine]) if mine else None}
    return per_band


def bands(adapter, input_path, *, exclude=None, testmini=None, assignment=None,
          **adapter_options) -> dict:
    """Every document's words, length band and side by the one word rule (section 5.6,
    Words), over a whole input with no build: what role B stratifies the holdout sample by
    and writes S8's B_SIZES.json from (D-039 item 7). Each document carries its side as a
    build would record it (the hash rule, ContraDoc's frozen `--assignment`, FinDVer's
    official split, ContractNLI's frozen file, checked as a build checks it); a FinDVer
    holdout filing that `--testmini` also holds is `removed_overlap`, a holdout input of
    FinDVer needs `--testmini`, and a ContraDoc input needs `--assignment`, as a holdout
    build does (it is never regrouped from the input it is given). Per band, the documents, decisions (items) and median
    words are totalled for the holdout pool alone (`holdout_pool_bands`, what B_SIZES.json
    is written from) and for the development side apart (`development_bands`); a document
    on neither (an overlap, or a side no build could declare) is in neither total. No
    text is written."""
    _own_options(adapter, adapter_options)
    overlap_of = getattr(adapter, "overlapping_documents", None)
    if testmini and overlap_of is None:
        raise ValueError("options this adapter does not take: testmini")
    # not a development build: ContraDoc reads its groups from the frozen --assignment
    # alone and refuses without it, exactly as a holdout build does (section 1)
    options = {"side": None, "development": False, "input_path": str(input_path),
               "assignment": assignment}
    options.update({k: v for k, v in adapter_options.items() if v is not None})
    extra = {}
    check_input = getattr(adapter, "check_input", None)
    if check_input is not None:
        declared = ids.HOLDOUT if options.get("frozen_sha256") else None
        extra["input_check"] = check_input(input_path, declared, options)
        options["frozen_for"] = extra["input_check"]["frozen_for"]
    documents = adapter.documents(adapter.read_source(input_path), options)
    documents, excluded = apply_exclusions(documents, exclude)
    overlap = set(overlap_of(testmini)) if testmini else set()
    if overlap_of is not None and not testmini and any(d["side"] == ids.HOLDOUT for d in documents):
        raise ValueError("the holdout pool of %s needs --testmini (section 1 removes overlapping "
                         "documents)" % adapter.BENCHMARK)
    rows = []
    for doc in sorted(documents, key=lambda d: d["document_id"]):
        if bundle.is_empty(doc):
            continue
        source = ids.key_string(doc["source_document_id"])
        side = doc["side"]
        if side == ids.HOLDOUT and source in overlap:
            side = REMOVED_OVERLAP
        words = sum(int(p["words"]) if "words" in p else ids.word_count(p["text"]) for p in doc["parts"])
        rows.append({"document_id": doc["document_id"], "source_document_id": source,
                     "side": side, "words": words, "length_band": ids.length_band(words),
                     "items": len(doc["items"])})
    sides = {}
    for r in rows:
        sides[r["side"]] = sides.get(r["side"], 0) + 1
    for name, path in (("testmini_sha256", testmini), ("assignment_sha256", assignment),
                       ("exclusion_sha256", exclude)):
        if path:
            extra[name] = _sha(path)
    return dict({"benchmark": adapter.BENCHMARK, "input_sha256": _sha(input_path),
                 "word_rule": "preregistration section 5.6, Words",
                 "holdout_pool_bands": _band_totals([r for r in rows if r["side"] == ids.HOLDOUT]),
                 "development_bands": _band_totals([r for r in rows if r["side"] == ids.DEVELOPMENT]),
                 "documents_by_side": dict(sorted(sides.items())),
                 "excluded_documents": excluded, "documents": rows}, **extra)


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
        if arm in mapping.PIPELINE_ARMS and not mapping.BUS_READER_ADOPTED:
            raise mapping.Refused(
                "arm %s is refused: reading the pipeline's typed records from the run's bus "
                "(common/records.py, decision DS5-8, preregistration section 12 item 9) "
                "takes effect only after its checker attack is recorded" % arm)
        primary = mapping.label_pipeline_arm(adapter.SPEC, items, runs_root, arm)
    else:
        raise ValueError("unknown arm " + repr(arm))
    return {"primary": primary, "S-1": mapping.sensitivity_s1(adapter.SPEC, primary),
            "S-2": mapping.sensitivity_s2(adapter.SPEC, primary),
            "S-3": mapping.sensitivity_s3(adapter.SPEC, primary),
            "S-5": mapping.sensitivity_s5(adapter.SPEC, primary),
            "S-6": mapping.sensitivity_s6(adapter.SPEC, primary),
            "S-7": mapping.sensitivity_s7(adapter.SPEC, primary),
            "S-8": mapping.sensitivity_s8(adapter.SPEC, primary)}


PAIRED_KEY = "paired"


def _scored(adapter, labels: dict, bundles_dir, gone=()) -> dict:
    """Every analysis of one labels file, each without the documents in `gone`, and S-4 from
    the primary labels. Every analysis but S-7 leaves out the documents this arm excluded
    for a model call over its model's context (section 5.3); S-7 scores them ABSTAIN."""
    spec = adapter.SPEC
    out = {}
    for name, result in labels.items():
        view = mapping.scored_view(spec, result)
        if gone:
            view = mapping.restrict(spec, view, gone)
        out[name] = metrics.score_arm(spec, view, bundles_dir, adapter.headline)
        if "s8_applies" in result:     # S-8 (DEV-012) says whether it differs from the primary
            out[name]["s8_applies"], out[name]["note"] = result["s8_applies"], result.get("note")
    if "primary" in labels:
        view = mapping.scored_view(spec, labels["primary"])
        if gone:
            view = mapping.restrict(spec, view, gone)
        out["S-4"] = metrics.score_arm(spec, metrics.without_evidence_beyond_cut(view, bundles_dir),
                                       bundles_dir, adapter.headline)
    return out


def score(adapter, labels: dict, bundles_dir, paired_with=None) -> dict:
    """Every analysis in the labels file, and S-4 from the primary labels (section 5.3).
    A document excluded from this arm for a model call over its model's context is left
    out of every analysis but S-7, which scores its items ABSTAIN; every arm that excludes
    nothing is scored on all its documents.

    `paired_with` (another arm's labels file, as `label` writes it) adds the paired view
    (open point 12.14, D-078): every analysis again, on the documents both files label and
    neither arm excluded, with the documents left out and why. Comparisons of B3 with any
    arm read this view; S-7 is not in it, since it is the reading on all documents."""
    out = _scored(adapter, labels, bundles_dir)
    if paired_with is not None:
        mine, other = labels["primary"], paired_with["primary"]
        own_docs = {r["document_id"] for r in mine["labels"]}
        other_docs = {r["document_id"] for r in other["labels"]}
        excluded = mapping.over_context_excluded(mine) | mapping.over_context_excluded(other)
        gone = (own_docs ^ other_docs) | excluded
        analyses = _scored(adapter, {k: v for k, v in labels.items() if k != "S-7"}, bundles_dir, gone)
        out[PAIRED_KEY] = {
            "arm": mine["arm"], "with_arm": other["arm"],
            "documents": len((own_docs & other_docs) - excluded),
            "left_out_over_context": {"this_arm": sorted(mapping.over_context_excluded(mine) & own_docs),
                                      "other_arm": sorted(mapping.over_context_excluded(other) & own_docs)},
            "left_out_not_in_both": sorted(own_docs - other_docs),
            "analyses": analyses}
    return out


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
                   help="development work only: no budget needed, recorded; a holdout "
                        "document is refused unless --side holdout is also given")
    b.add_argument("--exclude", help="the source document ids the benchmark's own paper prints "
                                     "as in-context examples (section 1), as role B identified them")
    for name, help_text in getattr(adapter, "BUILD_OPTIONS", ()):
        b.add_argument(name, help=help_text)
    s = sub.add_parser("split")
    s.add_argument("--input", required=True)
    s.add_argument("--out")
    s.add_argument("--exclude", help="as for build: a listed document is marked excluded")
    for name, help_text in getattr(adapter, "SPLIT_OPTIONS", ()):
        s.add_argument(name, help=help_text)
    bd = sub.add_parser("bands")
    bd.add_argument("--input", required=True)
    bd.add_argument("--out")
    bd.add_argument("--exclude", help="as for build: a listed document is left out")
    bd.add_argument("--testmini", help="FinDVer: the testmini file; a holdout report it also "
                                       "holds is removed_overlap and in no total")
    bd.add_argument("--assignment", help="ContraDoc: the frozen split file, as for a holdout "
                                         "build; required, the input is never regrouped")
    for name, help_text in getattr(adapter, "BUILD_OPTIONS", ()):
        bd.add_argument(name, help=help_text)
    lab = sub.add_parser("label")
    lab.add_argument("--items", required=True)
    lab.add_argument("--arm", required=True, choices=mapping.ARMS)
    lab.add_argument("--runs")
    lab.add_argument("--out", required=True)
    sc = sub.add_parser("score")
    sc.add_argument("--labels", required=True)
    sc.add_argument("--bundles", required=True)
    sc.add_argument("--out", required=True)
    sc.add_argument("--paired-with", help="another arm's labels file: adds the paired view, on "
                                          "the documents both label and neither arm excluded "
                                          "for a call over its model's context (section 5.3)")
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            print(json.dumps(build(
                adapter, args.input, args.out, side=args.side, max_context=args.max_context,
                output_allowance=args.output_allowance, token_counter=args.token_counter,
                b1_prompt=args.b1_prompt, development=args.development,
                assignment=args.assignment, testmini=args.testmini, exclude=args.exclude,
                **{_dest(n): getattr(args, _dest(n))
                   for n, _h in getattr(adapter, "BUILD_OPTIONS", ())}), indent=2))
            return 0
        if args.command == "split":
            rows = adapter.split_rows(adapter.read_source(args.input), args)
            if getattr(adapter, "check_input", None) is not None:
                adapter.check_input(args.input, getattr(args, "official", None),
                                    {"frozen_sha256": getattr(args, "frozen_sha256", None)})
            if args.exclude:
                listed = set(read_exclusions(args.exclude))
                for row in rows:
                    if ids.key_string(row["source_document_id"]) in listed:
                        row["side"] = "excluded_demonstration"
            if args.out:
                _write(args.out, {"benchmark": adapter.BENCHMARK, "input_sha256": _sha(args.input),
                                  "exclusion_sha256": _sha(args.exclude) if args.exclude else None,
                                  "documents": rows})
            else:
                print(json.dumps(rows, indent=2, ensure_ascii=False))
            return 0
        if args.command == "bands":
            result = bands(adapter, args.input, exclude=args.exclude, testmini=args.testmini,
                           assignment=args.assignment,
                           **{_dest(n): getattr(args, _dest(n))
                              for n, _h in getattr(adapter, "BUILD_OPTIONS", ())})
            if args.out:
                _write(args.out, result)
            print(json.dumps({k: result[k] for k in ("benchmark", "documents_by_side",
                                                     "holdout_pool_bands", "development_bands")},
                             indent=2))
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
            other = (json.loads(Path(args.paired_with).read_text(encoding="utf-8"))
                     if args.paired_with else None)
            result = score(adapter, labels, args.bundles, other)
            _write(args.out, result)
            shown = {k: v["headline"] for k, v in result.items() if k != PAIRED_KEY}
            if PAIRED_KEY in result:
                shown[PAIRED_KEY] = {k: v["headline"] for k, v in result[PAIRED_KEY]["analyses"].items()}
            print(json.dumps(shown, indent=2))
            return 0
    except (mapping.Refused, ValueError) as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return EXIT_REFUSED
    return 2
