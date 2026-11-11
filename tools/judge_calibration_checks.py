"""Proofs of the trained judge's calibration (benchmark/baselines/judge_calibration.py), on invented
decisions and stand-ins for the reader and the scorer only: no key, no model.

    py -3.12 -X utf8 tools/judge_calibration_checks.py [--judge-source DIR]

`--judge-source` names the tree holding scripts/choice_decision.py's `tempered` and
benchmark/baselines/fresh_test.py's `calibration` (lane/choice-2 until merged). Each proof that can
be neutralised is, and the neutralised form must fail. Exit 1 on any failure.
"""
import argparse
import importlib.util
import json
import math
import random
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILED, PASSED = [], []


def proof(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    (PASSED if ok else FAILED).append(name)


def raises(fn, text):
    try:
        fn()
    except ValueError as exc:
        return text in str(exc)
    return False


def decision(probabilities):
    labels = ["contradicts", "does not", "cannot tell"]
    return {"answers": [{"label": l, "probability": p} for l, p in zip(labels, probabilities)]}


def planted(n, sharpness, accuracy, seed):
    """Decisions whose top answer is right `accuracy` of the time, stated with `sharpness`."""
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        top = rng.randrange(2)
        gold = ["contradicts", "does not"][top if rng.random() < accuracy else 1 - top]
        logits = [rng.gauss(0, .3) for _ in range(3)]
        logits[top] += sharpness
        weights = [math.exp(v) for v in logits]
        rows.append((decision([w / sum(weights) for w in weights]), gold))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--judge-source", default=str(ROOT))
    args = parser.parse_args(argv)
    source = Path(args.judge_source).resolve()
    sys.path[:0] = [str(source / "scripts"), str(source / "benchmark" / "baselines"), str(source / "tools")]
    import choice_decision  # noqa: F401  (the source's, before the module puts this tree first)
    import fresh_test  # noqa: F401
    spec = importlib.util.spec_from_file_location("judge_calibration", ROOT / "benchmark" / "baselines" / "judge_calibration.py")
    c = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c)
    import choice_decision as cd
    import fresh_test as ft

    over = planted(400, 6.0, .7, 7)
    fitted = c.fit_temperature(over)
    proof("an overconfident judge is softened: T above 1", fitted["temperature"] > 1.5)
    proof("the fit lowers the gold answer's negative log probability", fitted["nll"] < fitted["nll_at_1"])
    under = planted(400, .6, .9, 8)
    proof("an underconfident judge is sharpened: T below 1", c.fit_temperature(under)["temperature"] < 1)
    proof("the fit tempers through choice_decision.tempered itself",
          abs(c.gold_probability(over[0][0], over[0][1], 2.0)
              - next(a["probability"] for a in cd.tempered(over[0][0], 2.0)["answers"] if a["label"] == over[0][1])) < 1e-12)
    proof("the same rows give the same temperature", c.fit_temperature(over) == fitted)
    proof("refused: too few decisions", raises(lambda: c.fit_temperature(over[:5]), "at least"))
    proof("refused: a gold answer outside the decision", raises(lambda: c.fit_temperature([(over[0][0], "maybe")] * 30), "gold answer"))
    real_grid = c.GRID
    c.GRID = (1.0,)
    try:
        stuck = c.fit_temperature(over)
        caught = not (stuck["temperature"] > 1.5)
    finally:
        c.GRID = real_grid
    proof("neutralised: a grid of one temperature is caught", caught)

    # Gold through the scorer only: the marked and partner pair is contradicts, both orders; a
    # document with no contradiction gives does not; other pairs and failed calls are left out.
    sc = types.SimpleNamespace(item_is_flag=lambda key, item: key == "k_flag",
                               marked_passages=lambda key, item, sentences, src: {"marked": [0], "partner": [2]})
    documents = {"dflag": [{"item_id": "i1"}], "dclean": [{"item_id": "i2"}]}
    by_key = {"dflag": "k_flag", "dclean": "k_clean"}
    texts = {"dflag": {"text": "s"}, "dclean": {"text": "s"}}
    rows = [{"document_id": "dflag", "pair": [0, 2], "decision": decision([.6, .3, .1])},
            {"document_id": "dflag", "pair": [2, 0], "decision": decision([.6, .3, .1])},
            {"document_id": "dflag", "pair": [0, 1], "decision": decision([.2, .7, .1])},
            {"document_id": "dclean", "pair": [0, 1], "decision": decision([.2, .7, .1])},
            {"document_id": "dclean", "pair": [1, 2], "decision": None},
            {"document_id": "fresh", "pair": [0, 1], "decision": decision([.2, .7, .1])}]
    gold, counts = c.pair_gold(rows, documents, by_key, texts, "src", sc, lambda text: [{"text": "a"}, {"text": "b"}, {"text": "c"}])
    proof("gold: the marked pair is contradicts in both orders, the clean document's pairs do not",
          [(r["document_id"], tuple(r["pair"]), g) for r, g in gold]
          == [("dflag", (0, 2), "contradicts"), ("dflag", (2, 0), "contradicts"), ("dclean", (0, 1), "does not")])
    proof("gold: other pairs and failed calls are counted, not labelled",
          counts == {"contradicts": 2, "does not": 1, "left_out_other_pairs": 1, "left_out_no_decision": 1})
    proof("gold: a document outside half A is never read", all(r["document_id"] != "fresh" for r, _ in gold))

    # The whole fit on stand-ins for the reader: the file it writes is fresh_test's own form.
    def stand_ins(threshold):
        many = [{"document_id": "d%d" % i, "pair": [0, 2] if i % 2 else [0, 1], "choice": "pair", "prompt_id": "p%d" % i,
                 "decision": decision([.9, .05, .05] if i % 3 else [.05, .9, .05])} for i in range(60)]
        known = {"contradoc": {"d%d" % i: [{"item_id": "i%d" % i}] for i in range(60)}}
        cr = types.SimpleNamespace(universe=lambda keys, items: (known, set(), {"d%d" % i: ("k_flag" if i % 2 else "k_clean") for i in range(60)}),
                                   halves=lambda ids: (set(sorted(ids)[:30]), set(sorted(ids)[30:])),
                                   comparator=lambda b, docs, by_key, b1, left_out: ({"group": "judge_reason"}, {}),
                                   choose_threshold=lambda *a: (threshold, {"flagged": 3} if threshold is not None else None))
        fake_ft = types.SimpleNamespace(choice_rows=lambda value, seen, records, group, t: [dict(r, decision=cd.tempered(r["decision"], t)) for r in many],
                                        calibration=ft.calibration)
        pj = types.SimpleNamespace(finished_pass=lambda prompts, run: ({"documents": {r["document_id"]: {"text": "s"} for r in many},
                                                                        "config": {"choice": {"forms": {}}}}, {}, {}))
        return cr, fake_ft, pj
    with tempfile.TemporaryDirectory() as folder:
        run = Path(folder) / "run"
        run.mkdir()
        build_items = Path(folder) / "build_items.json"
        build_items.write_text(json.dumps({"items": [{"document_id": "d%d" % i, "source_document_id": "src_%d" % i} for i in range(60)]}),
                               encoding="utf-8")
        (run / "replay_measurement.json").write_text(json.dumps({"models": {"choice_trained": {"adapter_applied": True, "adapter_sha256": "a" * 64}}}),
                                                     encoding="utf-8")
        cr, fake_ft, pj = stand_ins(.85)
        record = c.calibrate("p", run, ["k"], "i", "s", "b1", Path(folder) / "out", build_items, cr=cr, ft=fake_ft, pj=pj, sc=sc,
                             passages=lambda text: [{"text": "a"}, {"text": "b"}, {"text": "c"}])
        written = json.loads((Path(folder) / "out" / "calibration.json").read_text(encoding="utf-8"))
        proof("the calibration is fresh_test's own form, and it reads it back", ft.calibration(Path(folder) / "out" / "calibration.json") == written)
        proof("it names the adapter the trained pass applied and half A's SOURCE ids only",
              written["adapter_weights_sha256"] == "a" * 64 and written["fitted_on_documents"] == sorted("src_%d" % i for i in sorted(range(60), key=lambda i: "d%d" % i)[:30])
              and written["development_only"] is True)
        again = c.calibrate("p", run, ["k"], "i", "s", "b1", Path(folder) / "again", build_items, cr=cr, ft=fake_ft, pj=pj, sc=sc,
                            passages=lambda text: [{"text": "a"}, {"text": "b"}, {"text": "c"}])
        proof("a refit from the same rows gives the same calibration, byte for byte",
              (Path(folder) / "again" / "calibration.json").read_bytes() == (Path(folder) / "out" / "calibration.json").read_bytes() and again == record)
        partial = Path(folder) / "partial_items.json"
        partial.write_text(json.dumps({"items": [{"document_id": "d1", "source_document_id": "src_1"}]}), encoding="utf-8")
        proof("refused: a half A document with no source id", raises(lambda: c.calibrate("p", run, ["k"], "i", "s", "b1", Path(folder) / "part", partial,
                                                                                        cr=cr, ft=fake_ft, pj=pj, sc=sc,
                                                                                        passages=lambda text: [{"text": "a"}, {"text": "b"}, {"text": "c"}]),
                                                                    "no single source id"))
        proof("the record states the gold counts and the fit", record["written"] and set(record["gold_counts"]) >= {"contradicts", "does not"})
        cr, fake_ft, pj = stand_ins(None)
        record = c.calibrate("p", run, ["k"], "i", "s", "b1", Path(folder) / "none", build_items, cr=cr, ft=fake_ft, pj=pj, sc=sc,
                             passages=lambda text: [{"text": "a"}, {"text": "b"}, {"text": "c"}])
        proof("no threshold qualifies: no calibration is written", not record["written"] and not (Path(folder) / "none" / "calibration.json").exists())
        (run / "replay_measurement.json").write_text(json.dumps({"models": {"choice_trained": {"adapter_applied": False}}}), encoding="utf-8")
        cr, fake_ft, pj = stand_ins(.85)
        (run / "replay_measurement.json").write_text(json.dumps({"models": {"choice_direct": {"adapter_applied": True, "adapter_sha256": "b" * 64}}}),
                                                     encoding="utf-8")
        named = c.calibrate("p", run, ["k"], "i", "s", "b1", Path(folder) / "named", build_items, group="choice_direct", cr=cr, ft=fake_ft, pj=pj, sc=sc,
                            passages=lambda text: [{"text": "a"}, {"text": "b"}, {"text": "c"}])
        proof("a named group's adapter is the one the calibration names",
              named["written"] and json.loads((Path(folder) / "named" / "calibration.json").read_text(encoding="utf-8"))["adapter_weights_sha256"] == "b" * 64)
        (run / "replay_measurement.json").write_text(json.dumps({"models": {"choice_trained": {"adapter_applied": False}}}), encoding="utf-8")
        proof("refused: a pass that applied no adapter", raises(lambda: c.calibrate("p", run, ["k"], "i", "s", "b1", Path(folder) / "noad", build_items, cr=cr,
                                                                                     ft=fake_ft, pj=pj, sc=sc,
                                                                                     passages=lambda text: [{"text": "a"}, {"text": "b"}, {"text": "c"}]),
                                                                "no adapter"))
    print("judge calibration checks: %d proofs passed%s" % (len(PASSED), ", FAILED %d" % len(FAILED) if FAILED else ", all passed"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
