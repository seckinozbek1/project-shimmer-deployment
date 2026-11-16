"""SCITAB_INSIDE (b), TABLE-AUTHORITY-A rule 2 as a what-if from records (D-642 item 4 (b)): what the
development SciTab score would be if an unsettled cell decision whose top answer is "holds" or "not met"
(unsettled only because it fell below the measured threshold) were read as a leaning, against the same
runs read as they are. Development runs only (G1 SciTab rows), never the quick subset or a gate set;
labelled "what-if from records, not a system run". No model, no provider, nothing written to a run.

    py -3.12 -X utf8 tools/scitab_leaning_whatif.py --pairs PAIRS.json --g1-documents G1_SCITAB_IDS.json --out OUT.json
    py -3.12 -X utf8 tools/scitab_leaning_whatif.py --self-test

PAIRS.json is [{"key": <a bundle's answer_key.json>, "run": <its run folder, holding audit/pairing_map.json>}].
Each run folder is copied to a temporary folder, its pairing map's cell decisions rewritten there by
`leaned` (the one rule, below), and both the original and the copy labelled by the scorer's own route
(tools/score_corpus.benchmark_items, scoring detection_dev, the adapter's labeller): the key is read
only there, and this tool prints aggregates only (2-class macro-F1 by judge_read.macro_f1, counts),
never an item id, a gold label or any text.

HALF A ONLY (D-296, D-646): G1's half B is spent, never read again as a test and given to no worker, so
this tool reads half A's SciTab runs alone until Seckin rules otherwise. `--g1-documents` is the list of
all 29 G1 SciTab document ids (ids only, no gold: D-239's 29 tables); the halves are recomputed from it
by choice_read.halves, the one split, and every pair whose document is in half B, or in neither half,
refuses the whole run before any key is read. The output says `half: "A"`.
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "tools", ROOT / "scripts", ROOT / "benchmark" / "adapters", ROOT / "benchmark" / "baselines"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

PAIRING_MAP = ("audit", "pairing_map.json")
LEANABLE = ("holds", "not met")          # the cell step's declared answers that carry a verdict
SETTING = "2-class"                      # G1's SciTab declaration (judge_read.G1_SETTINGS)
G1_SCITAB_DOCUMENTS = 29                 # D-239: 95 claims in 29 tables (93 scored); the split needs them all
HALF_B_SPENT = "half B is spent (D-296): this what-if reads G1 half A only"


def half_a(g1_documents):
    """G1 SciTab's half A, by choice_read.halves over all 29 document ids (the one split); refused
    when the list is not the whole set, since the halves depend on every id."""
    import choice_read
    ids = sorted({str(d) for d in g1_documents})
    if len(ids) != G1_SCITAB_DOCUMENTS:
        raise SystemExit("--g1-documents must list all %d G1 SciTab documents, it lists %d" % (G1_SCITAB_DOCUMENTS, len(ids)))
    a, b = choice_read.halves(ids)
    return a, b


def document_of(key):
    """The document id a key names, as score_corpus.benchmark_items reads it."""
    return str(key.get("document") or "").rsplit(".", 1)[0]


def admit_half_a(keys, a, b):
    """Refuse before any read when a key is not a G1 SciTab half A document."""
    for key in keys:
        doc = document_of(key)
        if str(key.get("benchmark")) != "scitab":
            raise SystemExit("a key is not a SciTab key")
        if doc in b:
            raise SystemExit(HALF_B_SPENT)
        if doc not in a:
            raise SystemExit("a key names a document in neither G1 SciTab half")


def below_threshold_reason():
    """choice_decision's own word for a decision unsettled by its threshold, never typed twice."""
    import choice_decision
    return choice_decision.BELOW_THRESHOLD


def leaned(decision, below=None):
    """(decision as read under TABLE-AUTHORITY-A rule 2, leaned?). Only an unsettled decision whose
    reason is the threshold (never a tie, never "no threshold") and whose top answer by its recorded
    probabilities is "holds" or "not met" gains the row fields the built rule writes
    (scripts/cell_selection._row: `leaning`, `leaning_confidence`, `leaning_why`), its decision left
    unsettled as recorded, so the scorer reads it as detection_dev reads a leaning; everything else
    is returned unchanged."""
    below = below or below_threshold_reason()
    if not isinstance(decision, dict) or decision.get("settled") is not False or decision.get("why") != below:
        return decision, False
    answers = decision.get("answers")
    if not isinstance(answers, dict) or not answers:
        return decision, False
    ranked = sorted(answers.items(), key=lambda kv: -float(kv[1]))
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return decision, False
    top, probability = ranked[0]
    if top not in LEANABLE:
        return decision, False
    return dict(decision, leaning=top, leaning_confidence=float(probability), leaning_why=[below]), True


def lean_pairing_map(pairing, below=None):
    """(a copy of `pairing` with every cell decision leaned, count of decisions leaned)."""
    pairing = copy.deepcopy(pairing)
    count = 0
    entries = pairing.values() if isinstance(pairing, dict) and "cell_claims" not in pairing else [pairing]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for row in entry.get("cell_claims") or []:
            if not isinstance(row, dict):
                continue
            decisions = []
            for d in row.get("decisions") or []:
                new, did = leaned(d, below)
                decisions.append(new)
                count += did
            row["decisions"] = decisions
    return pairing, count


def _class_name(cls):
    """A labeller class as judge_read.macro_f1 reads it (FLAG, CLEAR; anything else is wrong)."""
    return cls if cls in ("FLAG", "CLEAR") else "ABSTAIN"


def score(pairs, g1_documents):
    import score_corpus as sc
    import judge_read
    a, b = half_a(g1_documents)
    keys = [json.loads(Path(pair["key"]).read_text(encoding="utf-8")) for pair in pairs]
    admit_half_a(keys, a, b)
    base, lean, moved, leaned_total, documents = [], [], 0, 0, 0
    with tempfile.TemporaryDirectory() as tmp:
        for n, (pair, key) in enumerate(zip(pairs, keys)):
            run = Path(pair["run"])
            pm = run.joinpath(*PAIRING_MAP)
            if not pm.is_file():
                raise SystemExit("a run folder holds no audit/pairing_map.json (extract its evidence first)")
            first = sc.benchmark_items(key, run, scoring="detection_dev")
            mirror = Path(tmp) / ("run_%03d" % n)
            shutil.copytree(run, mirror)
            pairing, count = lean_pairing_map(json.loads(pm.read_text(encoding="utf-8")))
            mirror.joinpath(*PAIRING_MAP).write_text(json.dumps(pairing), encoding="utf-8")
            second = sc.benchmark_items(key, mirror, scoring="detection_dev")
            leaned_total += count
            documents += 1
            after = {r["item_id"]: r for r in second.get("items") or []}
            for r in first.get("items") or []:
                if r.get("gold_class") not in ("FLAG", "CLEAR"):
                    continue
                a = _class_name(r.get("b3_class"))
                b = _class_name((after.get(r["item_id"]) or {}).get("b3_class"))
                base.append(dict(cls=a, gold=r["gold_class"]))
                lean.append(dict(cls=b, gold=r["gold_class"]))
                moved += a != b
    right = sum(1 for x, y in zip(base, lean) if x["cls"] != y["cls"] and y["cls"] == y["gold"])
    return {"label": "what-if from records, not a system run (SCITAB_INSIDE (b), TABLE-AUTHORITY-A rule 2)",
            "half": "A", "half_a_documents": len(a), "setting": SETTING, "documents": documents, "items": len(base), "decisions_leaned": leaned_total,
            "macro_f1_as_read": judge_read.macro_f1(base, SETTING), "macro_f1_with_leanings": judge_read.macro_f1(lean, SETTING),
            "abstain_as_read": sum(1 for r in base if r["cls"] == "ABSTAIN"),
            "abstain_with_leanings": sum(1 for r in lean if r["cls"] == "ABSTAIN"),
            "items_moved": moved, "moved_and_right": right}


def self_test():
    """The rule on invented decisions: only a below-threshold unsettled decision with a verdict on top leans."""
    below = "below_threshold"
    d = dict(settled=False, why=below, decided="cannot be settled", answers={"holds": 0.5, "not met": 0.3, "cannot be settled": 0.2})
    assert leaned(d, below)[0]["leaning"] == "holds" and leaned(d, below)[1]
    assert leaned(d, below)[0]["settled"] is False, "the decision stays unsettled; the leaning is beside it"
    rows = [{"decision": {"answers": [{"label": "holds", "probability": .5}, {"label": "not met", "probability": .3},
                                      {"label": "cannot be settled", "probability": .2}], "declared_mass": .9}}]
    counts = replies_counts(rows, .6)
    assert counts["as_read"]["classes"] == {"UNDECIDED": 1} and counts["with_leanings"]["classes"] == {"CLEAR": 1}, counts
    assert counts["moved"] == 1 and counts["leaning_probability_tenths"][5] == 1, counts
    assert not leaned(dict(d, why="no_threshold"), below)[1], "no threshold never leans"
    assert not leaned(dict(d, answers={"holds": 0.4, "not met": 0.4, "cannot be settled": 0.2}), below)[1], "a tie never leans"
    assert not leaned(dict(d, answers={"cannot be settled": 0.6, "holds": 0.4}), below)[1], "Unclear on top never leans"
    assert not leaned(dict(d, settled=True), below)[1], "a settled decision is unchanged"
    pairing = {"doc": {"cell_claims": [{"rule_id": "CONV-1", "decisions": [d, dict(d, why="tie")]}]}}
    leaned_map, count = lean_pairing_map(pairing, below)
    assert count == 1 and pairing["doc"]["cell_claims"][0]["decisions"][0]["settled"] is False, "the input is not changed"
    ids = ["doc%02d" % n for n in range(G1_SCITAB_DOCUMENTS)]
    a, b = half_a(ids)
    assert len(a) == 15 and len(b) == 14 and not a & b
    admit_half_a([dict(benchmark="scitab", document=sorted(a)[0] + ".md")], a, b)
    for bad, why in (([dict(benchmark="scitab", document=sorted(b)[0] + ".md")], HALF_B_SPENT),
                     ([dict(benchmark="scitab", document="other.md")], "neither"),
                     ([dict(benchmark="contradoc", document=sorted(a)[0] + ".md")], "not a SciTab key")):
        try:
            admit_half_a(bad, a, b)
        except SystemExit as exc:
            assert why in str(exc), exc
        else:
            raise AssertionError("not refused: " + why)
    try:
        half_a(ids[:-1])
    except SystemExit:
        pass
    else:
        raise AssertionError("an incomplete document list was not refused")
    return "self-test passed"


# ---------------------------------------------------------------------------------------------------
# D-646 on saved replies: the cell question's own decisions of a finished replay pass (G1 SciTab, half A
# only), read again at K1's recorded threshold (.6, D-477) as they were and with TABLE-AUTHORITY-A rule 2's
# leanings. The counts need no gold and are printed at once; the two macro-F1 figures, side by side,
# are read through the scorer only when the G1 keys are given and their digest is the pinned one
# (benchmark/baselines/g1_bar_items.json `keys_sha256`): after the 16 November loss (D-704, D-705) G1's
# keys must be rebuilt and proven equal first. Reads no text of any prompt and prints no id.

K1_CELL_THRESHOLD = 0.6        # D-477: choice_decision cell_claim .6, chosen on G1 half A from this pass
G1_ITEMS = ROOT / "benchmark" / "baselines" / "g1_bar_items.json"
READINGS = ("as_read", "with_leanings")
HOLDS, NOT_MET = "holds", "not met"


def _reply_decisions(run):
    """{call id: decision} of a pass folder's reply records (audit/model_replies), backend_ok only."""
    out = {}
    for path in sorted((Path(run) / "audit" / "model_replies").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("backend_ok") and isinstance(record.get("decision"), dict):
            out[record.get("call_id")] = record["decision"]
    return out


def replies_rows(prompts_path, run, g1_items=G1_ITEMS):
    """[{document_id, rule_id, decision}] of the pass's SciTab claim questions on G1 half A, the order
    controls and the left-out claims set aside. A row of half B refuses the whole read (D-296)."""
    import choice_read
    prompts = json.loads(Path(prompts_path).read_text(encoding="utf-8"))
    by_id = {p["prompt_id"]: p for p in prompts["prompts"]}
    documents = prompts.get("documents") or {}
    half_a_ids, half_b_ids = choice_read.split(documents)["scitab"]
    listed = json.loads(Path(g1_items).read_text(encoding="utf-8"))
    measurement = json.loads((Path(run) / "replay_measurement.json").read_text(encoding="utf-8"))
    if measurement.get("complete") is not True:
        raise SystemExit("the pass is not complete")
    decisions = _reply_decisions(run)
    rows, controls = [], 0
    for row in measurement.get("rows") or []:
        prompt = by_id.get(row.get("prompt_id"))
        if prompt is None:
            raise SystemExit("a pass row names a prompt the prompts file does not hold")
        if prompt.get("benchmark") != "scitab" or prompt.get("choice") != "claim":
            continue
        if prompt.get("order_control"):
            controls += 1
            continue
        if prompt["document_id"] in half_b_ids:
            raise SystemExit(HALF_B_SPENT)
        if prompt["document_id"] not in half_a_ids:
            raise SystemExit("a pass row names a document in neither G1 SciTab half")
        if prompt.get("item_id") in set(listed.get("left_out") or []):
            continue
        rows.append({"document_id": prompt["document_id"], "rule_id": prompt["rule_id"], "item_id": prompt.get("item_id"),
                     "decision": decisions.get(row.get("call_id"))})
    return rows, controls, len(half_a_ids)


def read_claim(decision, threshold, with_leanings):
    """(class, source) of one claim: CLEAR, FLAG, UNDECIDED or ABSTAIN (a failed call or a tie), and
    `leaning` when rule 2 read it."""
    import choice_decision
    if decision is None:
        return "ABSTAIN", "failed"
    made = choice_decision.settle(decision, threshold)
    if made["why"] == choice_decision.TIE:
        return "ABSTAIN", "tie"
    if made["settled"]:
        return {HOLDS: "CLEAR", NOT_MET: "FLAG"}.get(made["decided"], "UNDECIDED"), "settled"
    if with_leanings and made["why"] == choice_decision.BELOW_THRESHOLD and made["top"] in LEANABLE:
        return {HOLDS: "CLEAR", NOT_MET: "FLAG"}[made["top"]], "leaning"
    return "UNDECIDED", made["why"]


def replies_counts(rows, threshold=K1_CELL_THRESHOLD):
    """Counts only, no gold: each reading's classes and sources, the leanings by answer, and the
    leanings' own probabilities in tenths."""
    out = {}
    for reading in READINGS:
        classes, sources = {}, {}
        for r in rows:
            cls, source = read_claim(r["decision"], threshold, reading == "with_leanings")
            classes[cls] = classes.get(cls, 0) + 1
            sources[source] = sources.get(source, 0) + 1
        out[reading] = {"classes": dict(sorted(classes.items())), "sources": dict(sorted(sources.items()))}
    tenths = [0] * 10
    for r in rows:
        cls, source = read_claim(r["decision"], threshold, True)
        if source == "leaning":
            top = max(a["probability"] for a in r["decision"]["answers"])
            tenths[min(9, int(top * 10))] += 1
    out["leaning_probability_tenths"] = tenths
    out["moved"] = sum(1 for r in rows if read_claim(r["decision"], threshold, False) != read_claim(r["decision"], threshold, True))
    return out


def replies_scores(rows, keys, threshold=K1_CELL_THRESHOLD, g1_items=G1_ITEMS):
    """Both readings through the scorer, side by side, and the leanings' accuracy apart. Refused
    unless the keys are G1's by the pinned digest."""
    import choice_read
    import doc_judge
    sc = doc_judge._score_corpus()
    listed = json.loads(Path(g1_items).read_text(encoding="utf-8"))
    if not doc_judge._pinned(g1_items):
        raise SystemExit("the items file is not the pinned one (doc_judge.BAR_ITEMS_SHA256)")
    if doc_judge.keys_digest(sc, keys) != listed.get("keys_sha256"):
        raise SystemExit("the keys are not G1's by the pinned keys_sha256: rebuild and prove them first (D-704, D-705)")
    item_of = {}
    for key in keys:
        table = sc.item_table(key)
        for i in table["items"]:
            item_of[(table["document_id"], i["rule_id"])] = i["item_id"]
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        for reading in READINGS:
            view = []
            for r in rows:
                cls, source = read_claim(r["decision"], threshold, reading == "with_leanings")
                view.append({"document_id": r["document_id"], "item_id": item_of.get((r["document_id"], r["rule_id"])),
                             "cls": cls, "source": source})
            scored, figures = choice_read.score([v for v in view if v["item_id"]], keys, tmp, set(listed.get("left_out") or []), reading)
            leaning = [s for s in scored if s.get("source") == "leaning"]
            out[reading] = {"macro_f1": figures["macro_f1"], "accuracy": figures["accuracy"], "items": figures["items"],
                            "leanings": len(leaning), "leanings_right": sum(1 for s in leaning if s["cls"] == s["gold"])}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--replies", nargs=2, metavar=("PROMPTS", "RUN"),
                    help="D-646 on saved replies: the pass's prompts file and its folder (G1 SciTab half A)")
    ap.add_argument("--key", action="append", default=[], help="with --replies: every G1 key, proven by its pinned digest")
    ap.add_argument("--pairs", type=Path)
    ap.add_argument("--g1-documents", type=Path, help="all 29 G1 SciTab document ids, a JSON list (ids only)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        print(self_test())
        return 0
    if args.replies:
        rows, controls, half_a_documents = replies_rows(*args.replies)
        result = {"label": "what-if from saved replies, not a system run (D-646, TABLE-AUTHORITY-A rule 2)", "half": "A",
                  "half_a_documents": half_a_documents, "claims": len(rows), "order_controls_set_aside": controls,
                  "threshold": K1_CELL_THRESHOLD, "setting": SETTING, "counts": replies_counts(rows),
                  "scores": replies_scores(rows, args.key) if args.key else
                  "not read: G1's keys were lost on 16 November (D-704); give every G1 key, rebuilt and proven by keys_sha256"}
        text = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.out:
            args.out.write_text(text, encoding="utf-8", newline="\n")
        print(text, end="")
        return 0
    if not args.pairs or not args.out or not args.g1_documents:
        ap.error("--pairs, --g1-documents and --out are required")
    result = score(json.loads(args.pairs.read_text(encoding="utf-8")), json.loads(args.g1_documents.read_text(encoding="utf-8")))
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
