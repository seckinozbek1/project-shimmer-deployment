"""Gate check: cell selection (P2 (b)). Python selects the rows and columns of a table that bear on
a claim. No model, no provider, no key: an invented table and invented vectors.

Each proof is neutralise, fail, restore, pass (scripts/effect_proof.py):
1. a table is read with its caption, its header and rows as wide as the header; a block with no
   separator row is no table;
2. the key columns are the leading columns of labels;
3. a named column cuts the others, the header and the key column staying;
4. a figure the claim writes names its row and column, whatever the words;
5. a claim on one row keeps the rows it does not name, up to `fill_rows`;
6. the caps hold and the selection states what they left out;
7. no table, a claim matching nothing above the caps and a tie are refused with their reason, with
   no cells; a claim matching nothing within them is shown the whole table, marked;
8. of two tables the one the claim names is chosen, and one the claim cannot tell apart is a tie;
9. the embedding ranks only what words and figures leave equal, and says so;
10. accented labels match, since the words are the one tokeniser's;
11. the module imports nothing that could read a key or a word list;
12. the replay's `select_cells` is this selection, and a claim refused is listed, not lost;
13. on the real phase 5.5 a declared claim is one narrow question, its decision in the pairing map
    row with no text, its calls counted, with run_task's trail;
14. a settled not met is a model's record (INFRA-048) through the real phase to review_data.json,
    with no amendment; holds and an unsettled decision make none; each check of the record refuses
    with its own reason, a reply on a judged path being refused; the relation stands last, carries
    no figures, counts for nothing unscreened, has its words in both languages and is re-screened;
15. no threshold asks nothing and says so; a failed or raised call is said, marks the run and
    keeps the document; the declared stop holds;
16. the question is masked against the whole document and is the measured one;
17. `[compare: cells]` is read and refused as `passages` is, and makes no unit plan.
"""
import ast
import contextlib
import inspect
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import cell_selection  # noqa: E402
import generation_observation  # noqa: E402
import pairing_map  # noqa: E402
import reply_records  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

TEXT = chr(10).join((
    "# Note", "", "Table 2: Harbour dues by quay.", "",
    "| Quay | Berth | Dues | Depth | Crane |",
    "|---|---|---|---|---|",
    "| Northern | Alpha | 61.5 | 12 | 3 |",
    "| Southern | Beta | 44.0 | 9 | 1 |",
    "| Eastern | Gamma | 70.25 | 14 | 2 |", "",
    "| not | a | table |",
    "| at | all | here |",
    "| and | no | rule |", ""))
CONFIG = {"fill_rows": 12, "max_rows": 16, "max_columns": 10}


@contextlib.contextmanager
def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


def with_source(module, name, old, new):
    """`module.name` with one line of its own source changed, as a neutralisation."""
    source = inspect.getsource(getattr(module, name))
    assert source.count(old) == 1, old
    space = dict(vars(module))
    exec(source.replace(old, new), space)
    return patched(module, name, space[name])


def pick(result):
    return {k: result.get(k) for k in ("selected", "refused", "rows", "columns", "left_out_rows", "left_out_columns", "ranked_by")}


def observe_tables():
    found = cell_selection.tables(TEXT)
    return [(t["caption"], t["header"], len(t["rows"]), {len(r) for r in t["rows"]} == {len(t["header"])}) for t in found]


def expected_tables():
    return [("Table 2: Harbour dues by quay.", ["Quay", "Berth", "Dues", "Depth", "Crane"], 3, True)]


def observe_keys():
    return cell_selection.key_columns(cell_selection.tables(TEXT)[0])


def observe_column():
    return pick(cell_selection.select(TEXT, "The crane count differs between quays.", CONFIG))


def expected_column():
    return {"selected": True, "refused": None, "rows": [0, 1, 2], "columns": [0, 1, 4], "left_out_rows": 0,
            "left_out_columns": 2, "ranked_by": "words"}


def observe_rendered():
    return cell_selection.select(TEXT, "The crane count differs between quays.", CONFIG)["cells"].splitlines()


def expected_rendered():
    return ["Table 2: Harbour dues by quay.", "| Quay | Berth | Crane |", "|---|---|---|", "| Northern | Alpha | 3 |",
            "| Southern | Beta | 1 |", "| Eastern | Gamma | 2 |"]


def observe_figure():
    return pick(cell_selection.select(TEXT, "It reached 70.25 last year.", dict(CONFIG, fill_rows=0)))


def expected_figure():
    return {"selected": True, "refused": None, "rows": [2], "columns": [0, 1, 2], "left_out_rows": 2,
            "left_out_columns": 2, "ranked_by": "words"}


def observe_fill():
    return [cell_selection.select(TEXT, "The Northern quay has the deepest berth.", dict(CONFIG, fill_rows=n))["rows"] for n in (12, 2, 0)]


def expected_fill():
    return [[0, 1, 2], [0, 1], [0]]


def observe_caps():
    result = cell_selection.select(TEXT, "Dues 61.5 and crane figures for the Northern quay.", dict(CONFIG, max_columns=3, max_rows=2))
    return [len(result["columns"]) <= 3, len(result["rows"]) <= 2, result["left_out_columns"], result["left_out_rows"], result["refused"]]


def expected_caps():
    return [True, True, 2, 1, None]


def observe_refused():
    select = cell_selection.select
    tied = chr(10).join(("| Quay | Red | Blue | Note |", "|---|---|---|---|", "| One | 1 | 2 | x |", "| Two | 3 | 4 | y |"))
    return {"no table": (select("Plain words only here.", "Any claim at all.", CONFIG)["refused"]),
            "no match": select(TEXT, "Rainfall was unusually heavy.", dict(CONFIG, max_rows=2))["refused"],
            "tie": select(tied, "Red and blue differ.", dict(CONFIG, max_columns=2))["refused"],
            "no cells": select(TEXT, "Rainfall was unusually heavy.", dict(CONFIG, max_columns=2))["cells"]}


def expected_refused():
    return {"no table": "no_table", "no match": "no_match", "tie": "tie", "no cells": ""}


def observe_whole():
    result = cell_selection.select(TEXT, "Rainfall was unusually heavy.", CONFIG)
    named = cell_selection.select(TEXT, "The crane count differs.", CONFIG)
    return [result["selected_by"], result["rows"], result["columns"], result["refused"], named["selected_by"]]


def expected_whole():
    return ["whole_table", [0, 1, 2], [0, 1, 2, 3, 4], None, "labels"]


def observe_two_tables():
    other = chr(10).join(("Table 3: Rainfall by month.", "", "| Month | Rainfall |", "|---|---|", "| March | 20 |", "| April | 30 |", ""))
    same = chr(10).join(("| Quay | Dues |", "|---|---|", "| One | 1 |", "| Two | 2 |", "", "text", "",
                         "| Quay | Dues |", "|---|---|", "| One | 5 |", "| Two | 6 |", ""))
    named = cell_selection.select(TEXT + chr(10) + other, "Rainfall in April was low.", CONFIG)
    return [named["table"], named["cells"].splitlines()[0], cell_selection.select(same, "The dues rose.", CONFIG)["refused"]]


def expected_two_tables():
    return [1, "Table 3: Rainfall by month.", "tie"]


def _vectors(items):
    """A vector per text: the claim first, then rows, then columns; `Beta` lies nearest the claim."""
    return [[1.0, 0.0] if ("Beta" in item["text"] or item["text"].startswith("The ")) else [0.0, 1.0] for item in items]


def observe_embedding():
    claim = "The quay figures stand."
    words = cell_selection.select(TEXT, claim, dict(CONFIG, fill_rows=1))
    ranked = cell_selection.select(TEXT, claim, dict(CONFIG, fill_rows=1), _vectors)
    held = cell_selection.select(TEXT, "The Northern quay stands.", dict(CONFIG, fill_rows=1), _vectors)
    return {"words": (words["rows"], words["ranked_by"]), "embedding": (ranked["rows"], ranked["ranked_by"]), "words first": held["rows"]}


def expected_embedding():
    return {"words": ([0], "words"), "embedding": ([1], "words_and_embedding"), "words first": [0]}


def observe_accent():
    text = chr(10).join(("| Bölge | Değer |", "|---|---|", "| İzmir Körfezi | 7 |", "| Muğla | 9 |"))
    return [cell_selection.select(text, "Körfezi değeri arttı.", dict(CONFIG, fill_rows=0))["rows"],
            cell_selection.select(TEXT, "The cranes differ.", CONFIG)["columns"]]


def _baselines():
    folder = str(ROOT / "benchmark" / "baselines")
    if folder not in sys.path:
        sys.path.insert(0, folder)
    import choice_judge
    import doc_judge
    return choice_judge, doc_judge


def observe_replay():
    """The replay's `select_cells` is this selection, the same on a second reading, and a claim it
    refuses is listed in the prompts file with its reason, the rest still built."""
    choice_judge, doc_judge = _baselines()
    claim = "The crane count differs between quays."
    first, second = doc_judge.select_cells(TEXT, claim), doc_judge.select_cells(TEXT, claim)
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        work = folder / "workload"
        (work / "context").mkdir(parents=True)
        (work / "conventions").mkdir()
        (work / "context" / "d.md").write_text(TEXT, encoding="utf-8")
        (work / "_review_targets.json").write_text(json.dumps({"targets": ["d.md"]}), encoding="utf-8")
        template = doc_judge._adapter("scitab").RULE_TEMPLATE
        said = {"CONV-a": claim, "CONV-b": "Rainfall was heavy."}
        (work / "conventions" / "rules.md").write_text("# Rules" + chr(10) + "".join(
            chr(10) + "## %s Claim [required] [conformance]" % rule + chr(10) * 2 + template.format(claim=text) + chr(10)
            for rule, text in said.items()), encoding="utf-8")
        items = folder / "items.json"
        items.write_text(json.dumps({"benchmark": "scitab", "items": [
            {"benchmark": "scitab", "document_id": "d", "item_id": rule[-1], "rule_id": rule} for rule in said]}), encoding="utf-8")
        real = cell_selection.load_config
        with patched(cell_selection, "load_config", lambda: dict(real(), max_rows=2)):
            value = choice_judge.build(folder / "p.json", claim_workloads=[work], claim_items=[items])
    return {"cells": first == second and first["cells"] == "\n".join(expected_rendered()), "shape": sorted(first),
            "prompts": [p["item_id"] for p in value["prompts"]], "refused": value["refused_claims"], "counts": value["cell_counts"]}


def expected_replay():
    return {"cells": True, "shape": ["cells", "columns", "of_columns", "of_rows", "rows", "selected_by"], "prompts": ["a"],
            "refused": [{"document_id": "d", "item_id": "b", "rule_id": "CONV-b", "reason": "no_match"}],
            "counts": {"labels": 1, "refused": 1}}


CLAIM_RULE = {"id": "CONV-020", "category": "conv-h20", "severity": "required", "compare": "cells",
              "rule": "The Northern quay has the highest dues of the three quays."}
QUAY_UNIT = chr(10).join(("## Entry Quays", "", "Table 2: Harbour dues by quay.", "",
                          "| Quay | Dues | Depth |", "|---|---|---|", "| Northern | 61.5 | 12 |", "| Southern | 44.0 | 9 |",
                          "| Eastern | 70.25 | 14 |", ""))


def _decision(decided="not met", settled=True):
    return {"decided": decided, "settled": settled, "why": None if settled else "below_threshold", "confidence": .9,
            "threshold": .7, "declared_mass": .95, "top": decided,
            "answers": [{"label": a, "probability": p} for a, p in (("holds", .05), ("not met", .9), ("cannot be settled", .05))]}


def _phase(choose, threshold=.7, mask=None, rules=None):
    """The real phase 5.5 on a mocked run with a declared claim: (the pairing map's document, a
    review_data.json, the reader's file, run context, what the backend was sent, audit rows)."""
    import agent_wrapper
    import harness.run_agent as run_agent
    import honest_output_checks as hoc
    import passage_pairs
    from unittest.mock import patch
    sent = []

    def call_choice(self, prompt, answers, value):
        sent.append({"prompt": prompt, "answers": [a["label"] for a in answers], "threshold": value})
        result = choose(self, prompt, len(sent))
        return result if isinstance(result, agent_wrapper.CallResult) else agent_wrapper.CallResult(self.backend, "fixture-auditor", "", parsed=result)
    real = run_agent.build_orchestrator

    def orchestrator(**kwargs):
        orch = real(**kwargs)
        if mask:
            orch.outbound_masker = mask
        return orch
    text = chr(10).join((hoc.DOC_TEXT, QUAY_UNIT))
    with tempfile.TemporaryDirectory() as td, patch.object(agent_wrapper.AgentWrapper, "call_choice", call_choice), \
            patched(cell_selection, "threshold_of", lambda config: threshold), patch.object(passage_pairs, "embed", lambda items: None), \
            patch.object(run_agent, "build_orchestrator", orchestrator):
        run = hoc.mocked_run(Path(td), style_guardian=False, text=text, rules=rules or (hoc.RULES + [CLAIM_RULE]))
        folder = Path(run["run_dir"])
        document = json.loads(next(folder.rglob("pairing_map.json")).read_text(encoding="utf-8"))["batch_sheet"]
        data = json.loads(next(folder.rglob("review_data.json")).read_text(encoding="utf-8"))
        reader = next(folder.rglob("reviewed_document.md")).read_text(encoding="utf-8")
        audit = json.loads((folder / "audit" / "agent_activation.json").read_text(encoding="utf-8"))["decisions"]
        outcomes = reply_records.outcomes(folder / "audit" / "model_replies")
        path = folder / "logs" / "call_evidence.jsonl"
        evidence = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.is_file() else []
    return {"document": document, "data": data, "reader": reader, "context": run["ctx"], "sent": sent, "audit": audit,
            "outcomes": outcomes, "evidence": evidence}


def observe_product():
    """The real phase 5.5: one narrow question with the claim and the cells, the decision in the
    pairing map row with no text, no finding, its calls counted, and its trail."""
    run = _phase(lambda wrapper, prompt, n: _decision())
    if not run["document"]["cell_claims"]:
        return "no row"
    row = run["document"]["cell_claims"][0]
    decision = row["decisions"][0]
    prompt = run["sent"][0]["prompt"]
    findings = [f for f in run["data"].get("model_findings_not_promoted") or [] if f.get("rule_id") == "CONV-020"]
    pair = [c for c in run["document"]["judging_calls"] if c["plan_kind"] == "cell_claim"]
    calls = [r for r in run["audit"] if r["reason"] == "cell_claim"]
    evidence = [e for e in run["evidence"] if e.get("task") == "cell_claim"]
    return {"sent": len(run["sent"]), "answers": run["sent"][0]["answers"], "threshold": run["sent"][0]["threshold"],
            "shows": ["| Northern | 61.5 |" in prompt, "Depth" in prompt, CLAIM_RULE["rule"] in prompt, "JSON" in prompt],
            "row": (row["made"], row["not_met"], row["kept"], decision["decided"], decision["confidence"], decision["columns"]),
            "no text": "Northern" in json.dumps({k: v for k, v in row.items() if k != "decision_notes"}), "findings": len(findings), "calls_made": run["document"]["calls_made"] >= 1,
            "judging": [c["outcome"] for c in pair], "audit": [(r["downstream_consumer"], r["doc_id"]) for r in calls],
            "evidence": [(e["doc_id"], e["payload_rule_id"]) for e in evidence], "outcomes": sorted(run["outcomes"].values())}


def expected_product():
    return {"sent": 1, "answers": ["holds", "not met", "cannot be settled"], "threshold": .7,
            "shows": [True, False, True, False], "row": (1, 1, 1, "not met", .9, [0, 1]), "no text": False, "findings": 1,
            "calls_made": True, "judging": ["judged_cell_claim"], "audit": [("model_finding_not_promoted", "batch_sheet")],
            "evidence": [("batch_sheet", "CONV-020")], "outcomes": ["not_promoted"]}


def observe_no_threshold():
    run = _phase(lambda wrapper, prompt, n: _decision(), threshold=None)
    row = run["document"]["cell_claims"][0]
    return {"sent": len(run["sent"]), "said": row["not_asked"], "reader": "no threshold has been measured for deciding that" in run["reader"],
            "not judged": [e["why"] for e in run["document"]["not_judged"] if e.get("kind") == "cell_claim"]}


def expected_no_threshold():
    return {"sent": 0, "said": "no question asked: no threshold measured for cell_claim", "reader": True, "not judged": ["cells_no_threshold"]}


def observe_failures():
    """A failed call marks the run and is said; a raised one keeps the document and names its type."""
    import agent_wrapper

    def failed(wrapper, prompt, n):
        return agent_wrapper.CallResult(wrapper.backend, "fixture-auditor", "", ok=False, error="fixture")

    def raised(wrapper, prompt, n):
        raise MemoryError("the card is full")
    out = {}
    for name, choose in (("failed", failed), ("raised", raised)):
        try:
            run = _phase(choose)
        except MemoryError:
            out[name] = "the document was lost"
            continue
        row = run["document"]["cell_claims"][0]
        out[name] = [row["failed"], row["raised"], [e["why"] for e in run["document"]["not_judged"] if e.get("kind") == "cell_claim"],
                     bool(run["data"].get("amendments")), getattr(run["context"], "semantic_incomplete", False)]
    return out


def expected_failures():
    return {"failed": [1, None, ["cells_some_failed"], True, True], "raised": [0, "MemoryError", ["failed"], True, True]}


def observe_stop():
    """The declared number of failed calls in a row stops the rule."""
    units = [{"unit_id": "u%d" % n, "text": TEXT} for n in range(8)]
    config = dict(cell_selection.load_config(), stop_after_failed_calls=3)
    with patched(cell_selection, "threshold_of", lambda c: .7):
        _, calls = cell_selection.review(units, {"id": "R", "rule": "The crane count differs."}, None, lambda user: None, config)
    return [calls["made"], calls["failed"], calls["stopped"]]


def expected_stop():
    return [3, 3, "stopped after 3 failed calls in a row, 0 of 8 tables decided"]


def observe_record():
    """The real phase 5.5 to review_data.json: a model's record with the claim and the selected
    cells, marked and not promoted, its decision in Python's note, no amendment from it, and the
    reader shown both."""
    run = _phase(lambda wrapper, prompt, n: _decision())
    found = [f for f in run["data"].get("model_findings_not_promoted") or [] if f.get("relation") == "claim_not_met"]
    amendments = [a for a in run["data"].get("amendments") or [] if "CONV-020" in json.dumps(a)]
    item = found[0] if found else {}
    return {"found": len(found), "who": (item.get("written_by"), item.get("promoted"), item.get("checked_by_python")),
            "evidence": ("| Northern | 61.5 |" in str(item.get("quote")), item.get("quote_b") == CLAIM_RULE["rule"]),
            "note": any("wrote no text: not met, confidence 0.900" in str(n) for n in item.get("reader_notes") or []),
            "amendments": len(amendments), "reader": ("the selected cells do not meet the claim" in run["reader"], CLAIM_RULE["rule"] in run["reader"])}


def expected_record():
    return {"found": 1, "who": ("model", False, False), "evidence": (True, True), "note": True, "amendments": 0, "reader": (True, True)}


def _claim_item(**fields):
    cells = "Table 2: Harbour dues by quay." + chr(10) + "| Quay | Crane |" + chr(10) + "|---|---|" + chr(10) + "| Northern | 3 |"
    return dict({"item_id": "x", "unit_id": "u1", "rule_id": "R", "relation": "claim_not_met", "record_verdict": "irregular",
                 "quote": cells, "quote_b": "The crane count differs."}, **fields)


def _claim_refusal(item=None, rule=None, cells=True, unit=TEXT):
    review = passage_pairs_module().paired_review
    item = item or _claim_item()
    rule = rule or {"id": "R", "compare": "cells", "rule": "The crane count differs."}
    return review.judged_item_refusal(item, rule, None, unit, selected_cells=item["quote"] if cells else None)


def observe_refusals():
    """Each thing Python can check of the record, on the one test, each with its own reason; a
    reply on a judged path, which passes no selection, is refused whatever it writes."""
    other = _claim_item(quote=_claim_item()["quote"].replace("| Northern | 3 |", "| Northern | 2 |"))
    return {"kept": _claim_refusal(), "a reply": _claim_refusal(cells=False),
            "another rule": _claim_refusal(rule={"id": "R", "rule": "The crane count differs."}),
            "not irregular": _claim_refusal(_claim_item(record_verdict="ok")),
            "another claim": _claim_refusal(_claim_item(quote_b="Something else stands here.")),
            "no claim": _claim_refusal(_claim_item(quote_b="")),
            "cells of two rows": _claim_refusal(other), "no unit": _claim_refusal(unit="")}


def expected_refusals():
    review = passage_pairs_module().paired_review
    return {"kept": None, "a reply": review.CLAIM_NOT_FROM_CELLS, "another rule": review.CLAIM_RULE_NOT_CELLS,
            "not irregular": review.CLAIM_NOT_IRREGULAR, "another claim": review.CLAIM_NOT_THE_RULE, "no claim": review.CLAIM_NOT_THE_RULE,
            "cells of two rows": review.CLAIM_CELLS_NOT_IN_UNIT, "no unit": review.CLAIM_CELLS_NOT_IN_UNIT}


def observe_relation():
    """The relation is appended last, in the contract and the fallback, carries no figures, and
    the benchmark reader counts an unscreened one for nothing."""
    import finding_record as fr
    sys.path.insert(0, str(ROOT))
    from benchmark.adapters.common import records
    bare = _claim_item()
    marked = dict(bare, text_screened=True)
    # INFRA-051 appended rule_not_met after it: claim_not_met keeps its place, the one before.
    return {"last": (tuple(fr.relations()[-2:]), tuple(fr._FALLBACK["relations"][-2:])), "figures": "claim_not_met" in fr.figure_relations(),
            "finding": (fr.is_finding(bare), fr.is_finding(marked)), "benchmark": (records.is_typed_record(bare), records.is_typed_record(marked)),
            "held equal": records.TEXT_RELATIONS == fr.TEXT_RELATIONS}


def expected_relation():
    return {"last": (("claim_not_met", "rule_not_met"), ("claim_not_met", "rule_not_met")), "figures": False, "finding": (False, True), "benchmark": (False, True), "held equal": True}


def observe_words():
    """The reader's line and every reason, in both languages: a new reason with none fails."""
    import finding_record as fr
    import judged_rescreen
    import reviewed_document
    review = passage_pairs_module().paired_review
    reasons = [getattr(review, n) for n in dir(review) if n.startswith("CLAIM_")]
    line = fr.reader_line(dict(_claim_item(), text_screened=True))
    catalog = (ROOT / "scripts" / "ui" / "localization_catalog.js").read_text(encoding="utf-8")
    return {"reasons": len(reasons), "no words": [r for r in reasons if r not in reviewed_document.REFUSAL_REASONS],
            "no kind": [r for r in reasons if r not in judged_rescreen.KINDS],
            "no second-language row": [r for r in reasons if ('"%s": "' % reviewed_document.REFUSAL_REASONS.get(r, r)) not in catalog],
            "line": ('the claim "The crane count differs."' in line, "| Northern | 3 |" in line),
            "rows": ['"claim_not_met": "' in catalog, '"the selected cells do not meet the claim": "' in catalog,
                     'the claim \\"{claim}\\" against the cells' in catalog, "on\\\\ the\\\\ cells\\\\ Python\\\\ selected" in catalog]}


def expected_words():
    return {"reasons": 5, "no words": [], "no kind": [], "no second-language row": [], "line": (True, True), "rows": [True, True, True, True]}


def observe_rescreen():
    """A saved record is held to the unit again: kept as it stands, refused with other cells."""
    import judged_rescreen
    text = chr(10).join(("# Note", "", "## Part one", "", TEXT))
    unit = pairing_map.split_units(text, document_id="d")[-1]["unit_id"]
    out = {}
    for name, record in (("kept", _claim_item(unit_id=unit, judged_path="cell_claim", text_screened=True)),
                         ("changed", _claim_item(unit_id=unit, judged_path="cell_claim", text_screened=True,
                                                 quote="| Quay | Crane |" + chr(10) + "| Nowhere | 99 |"))):
        with tempfile.TemporaryDirectory() as folder:
            run, workload = Path(folder) / "run", Path(folder) / "workload"
            (run / "logs").mkdir(parents=True)
            (run / "audit").mkdir()
            (workload / "context").mkdir(parents=True)
            (workload / "context" / "d.md").write_text(text, encoding="utf-8")
            (workload / "_review_targets.json").write_text(json.dumps({"targets": ["d.md"]}), encoding="utf-8")
            (run / "audit" / "pairing_map.json").write_text(json.dumps({"d": {"units": []}}), encoding="utf-8")
            (run / "logs" / "agent_bus.jsonl").write_text(json.dumps({"body": {
                "event": "AGENT_OUTPUT", "stamped_by": "python", "payload": {"items": [record]}}}) + chr(10), encoding="utf-8")
            result = judged_rescreen.rescreen(run, workload)
        out[name] = [result["kept_by_path"], [r["kind"] for r in result["refused"]]]
    return out


def expected_rescreen():
    return {"kept": [{"cell_claim": 1}, []], "changed": [{"cell_claim": 1}, ["i_claim_cells_not_in_unit"]]}


def observe_only_flag():
    """Holds and an unsettled decision are counted and reach no finding."""
    seen = []
    units = [{"unit_id": "u1", "text": TEXT}, {"unit_id": "u2", "text": TEXT}]
    answers = iter([_decision("holds"), _decision("cannot be settled", settled=False)])
    with patched(cell_selection, "threshold_of", lambda c: .7), patched(cell_selection, "finding", lambda *a: seen.append(a) or None):
        _, calls = cell_selection.review(units, {"id": "R", "rule": "The crane count differs."}, None, lambda user: next(answers), cell_selection.load_config())
    return [len(seen), calls["not_met"], calls["unsettled"], len(calls["decisions"])]


def observe_masked():
    """A sensitive run's masker sees the whole document as context, and the backend what it returned."""
    seen = []

    def masker(stable, dynamic, *, backend, agent, context=""):
        seen.append(("Entry Alpha" in context, "Northern" in stable))
        return stable.replace("Northern", "[PLACE]"), dynamic
    run = _phase(lambda wrapper, prompt, n: _decision(), mask=masker)
    return {"context": seen, "sent raw": any("Northern" in s["prompt"] for s in run["sent"])}


def expected_masked():
    return {"context": [(True, True)], "sent raw": False}


def observe_same_form():
    """The runtime's question is the measured one, word for word."""
    _, doc_judge = _baselines()
    config = cell_selection.load_config()["decision"]
    measured = json.loads((ROOT / "benchmark" / "baselines" / "choice_judge_prompt.json").read_text(encoding="utf-8"))["choice"]["forms"]["claim"]
    return [config["template"] == measured["template"], config["answers"] == measured["answers"],
            cell_selection.question(cell_selection.load_config(), "C {x}", "A") == doc_judge.render_choice({"choice": {"forms": {"claim": measured}}}, "claim", {"cells": "C {x}", "claim": "A"})]


def observe_declaration():
    """`[compare: cells]` reads as `passages` reads, on a heading and in JSON, and is refused alike."""
    import convention_parser as parser
    line = chr(10) + "The Northern quay has the highest dues." + chr(10)

    def heading(text):
        try:
            return [r.compare for r in parser._parse_text_lines("## CONV-H20 Claim [compare: cells]" + text + line, "c.md", [0])]
        except parser.ConventionDeclarationError:
            return "refused"

    def from_json(**fields):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "c.json"
            path.write_text(json.dumps({"conventions": [dict(fields, id="C", rule="The Northern quay has the highest dues.")]}), encoding="utf-8")
            try:
                return [r.compare for r in parser._parse_json(path, [0])]
            except parser.ConventionDeclarationError:
                return "refused"
    return {"heading": heading(""), "scope": heading(" [scope: class]"), "unless": heading(" [unless: class]"),
            "json": from_json(compare="cells"), "json requires": from_json(compare="cells", requires=["class"]),
            "json other": from_json(compare="rows")}


def expected_declaration():
    return {"heading": ["cells"], "scope": "refused", "unless": "refused", "json": ["cells"], "json requires": "refused", "json other": "refused"}


def observe_not_a_plan():
    """A cells rule makes no unit plan: it is asked by this path alone."""
    import paired_review
    unit = {"unit_id": "u1", "text": TEXT}
    return len(paired_review.plan_calls({"u1": unit}, [("u1", "CONV-020")], {"CONV-020": CLAIM_RULE}, {}))


def observe_imports():
    tree = ast.parse(Path(cell_selection.__file__).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module)
    return sorted(names)


def finding_record_module():
    import finding_record
    return finding_record


def records_module():
    sys.path.insert(0, str(ROOT))
    from benchmark.adapters.common import records
    return records


def reviewed_document_module():
    import reviewed_document
    return reviewed_document


def rescreen_module():
    if str(ROOT / "tools") not in sys.path:
        sys.path.insert(0, str(ROOT / "tools"))
    import judged_rescreen
    return judged_rescreen


def passage_pairs_module():
    import passage_pairs
    return passage_pairs


def convention_parser_module():
    import convention_parser
    return convention_parser


def run_checks():
    module = cell_selection
    proofs = [
        ("tables", observe_tables, expected_tables,
         lambda: patched(pairing_map, "_TABLE_SEP", pairing_map.re.compile(r"^.*$"))),
        ("key columns", observe_keys, lambda: [0, 1],
         lambda: patched(module, "key_columns", lambda table: [0])),
        ("a named column", observe_column, expected_column,
         lambda: with_source(module, "select", "wanted_columns = named_columns or others", "wanted_columns = others")),
        ("header and key column stay", observe_rendered, expected_rendered,
         lambda: with_source(module, "select", "columns_shown = sorted(set(keys) | set(kept_columns))", "columns_shown = sorted(kept_columns)")),
        ("a figure names its cell", observe_figure, expected_figure,
         lambda: patched(module, "figures", lambda text: set())),
        ("rows kept for a comparison", observe_fill, expected_fill,
         lambda: with_source(module, "select", 'fill = max(config["fill_rows"] - len(named_rows), 0)', "fill = 0")),
        ("the caps", observe_caps, expected_caps,
         lambda: patched(module, "_cut", lambda order, scores, cap: (list(order), False))),
        ("refusals", observe_refused, expected_refused,
         lambda: with_source(module, "select", "if column_tie or row_tie:", "if False:")),
        ("no match is refused above the caps", observe_refused, expected_refused,
         lambda: patched(module, "_within_caps", lambda table, config: True)),
        ("no match within the caps is the whole table", observe_whole, expected_whole,
         lambda: patched(module, "_within_caps", lambda table, config: False)),
        ("two tables", observe_two_tables, expected_two_tables,
         lambda: with_source(module, "select", "if strength.count(best) > 1:", "if False:")),
        ("the embedding settles ties only", observe_embedding, expected_embedding,
         lambda: patched(module, "_embedded", lambda table, keys, claim, embed_with: (None, None))),
        ("one tokeniser", observe_accent, lambda: [[0], [0, 1, 4]],
         lambda: patched(module, "_tokens", lambda text: set(str(text).lower().split()))),
        ("a claim refused is listed", observe_replay, expected_replay,
         lambda: patched(module, "_within_caps", lambda table, config: True)),
        ("the replay's selection is this one", observe_replay, expected_replay,
         lambda: patched(module, "render", lambda table, rows, columns: "other cells")),
        ("the product path", observe_product, expected_product,
         lambda: patched(cell_selection, "declared", lambda rules: [])),
        ("the record reaches review_data as a model's", observe_record, expected_record,
         lambda: patched(cell_selection, "finding", lambda *a: None)),
        ("the record needs Python's mark", observe_record, expected_record,
         lambda: patched(passage_pairs_module().paired_review, "mark_screened", lambda item: item)),
        ("the decision's note", observe_record, expected_record,
         lambda: with_source(passage_pairs_module().paired_review, "model_item_notes", ' + ((pairing or {}).get("cell_claims") or [])', "")),
        ("a reply cannot write it", observe_refusals, expected_refusals,
         lambda: with_source(passage_pairs_module().paired_review, "_cell_claim_refusal", 'if selected_cells is None or item.get("quote") != selected_cells:', "if False:")),
        ("only under a declared rule", observe_refusals, expected_refusals,
         lambda: with_source(passage_pairs_module().paired_review, "_cell_claim_refusal", 'if (rule or {}).get("compare") != "cells":', "if False:")),
        ("irregular always", observe_refusals, expected_refusals,
         lambda: with_source(passage_pairs_module().paired_review, "_cell_claim_refusal", 'if str(item.get("record_verdict") or "").strip().lower() != "irregular":', "if False:")),
        ("the rule's own claim", observe_refusals, expected_refusals,
         lambda: with_source(passage_pairs_module().paired_review, "_cell_claim_refusal", 'if not str(item.get("quote_b") or "").strip() or item.get("quote_b") != (rule or {}).get("rule"):', "if False:")),
        ("the cells stand in the unit", observe_refusals, expected_refusals,
         lambda: patched(passage_pairs_module().paired_review, "_cells_stand_in", lambda cells, text: True)),
        ("the relation's place", observe_relation, expected_relation,
         lambda: patched(finding_record_module(), "TEXT_RELATIONS", ("contradiction",))),
        ("the benchmark reader", observe_relation, expected_relation,
         lambda: patched(records_module(), "TEXT_RELATIONS", ("contradiction",))),
        ("the reasons' words", observe_words, expected_words,
         lambda: patched(reviewed_document_module(), "REFUSAL_REASONS", {})),
        ("the reader's line", observe_words, expected_words,
         lambda: patched(finding_record_module(), "CELL_RELATIONS", ())),
        ("a saved record is re-screened", observe_rescreen, expected_rescreen,
         lambda: with_source(rescreen_module(), "kept_items", 'else "cell_claim" if written == paired_review.JUDGED_PATH_CELL_CLAIM', "")),
        ("holds and unsettled make no record", observe_only_flag, lambda: [0, 0, 1, 2],
         lambda: with_source(cell_selection, "review", 'if cls != "FLAG":', "if False:")),
        ("no threshold asks nothing", observe_no_threshold, expected_no_threshold,
         lambda: with_source(cell_selection, "review", "if threshold_of(config) is None:", "if False:")),
        ("failed and raised calls", observe_failures, expected_failures,
         lambda: patched(cell_selection, "CAUGHT", ())),
        ("the run is not called complete", observe_failures, expected_failures,
         lambda: patched(generation_observation, "mark_incomplete", lambda context: None)),
        ("the stop", observe_stop, expected_stop,
         lambda: with_source(cell_selection, "review", 'if streak >= config["stop_after_failed_calls"]:', "if False:")),
        ("masked against the document", observe_masked, expected_masked,
         lambda: patched(passage_pairs_module(), "outbound", lambda wrapper, text, context="": (text, ""))),
        ("the question measured", observe_same_form, lambda: [True, True, True],
         lambda: patched(cell_selection, "question", lambda config, cells, claim, contracts=None: "another question")),
        ("the declaration", observe_declaration, expected_declaration,
         lambda: patched(convention_parser_module(), "_refuse_compare_beside", lambda *a: None)),
        ("not a unit plan", observe_not_a_plan, lambda: 0,
         lambda: with_source(passage_pairs_module().paired_review, "plan_calls", 'if (rules_by_id.get(rule_id) or {}).get("compare"):', "if False:")),
        ("no key, no word list", observe_imports, lambda: ["choice_decision", "json", "judge_agent", "math", "paired_review", "pairing_map", "pathlib", "re"],
         lambda: patched(module, "__file__", str(ROOT / "scripts" / "cell_selection_checks.py"))),
    ]
    results = []
    for name, observe, expected, neutralise in proofs:
        results.append(prove_effect(name=name, validate=lambda: cell_selection.CONFIG_PATH.is_file(), observe=observe,
                                    check=lambda: ("PASS" if observe() == expected() else "FAIL", name),
                                    neutralise=neutralise))
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: a table is read with its caption, its key columns stay, "
                    "named columns cut the rest, a written figure names its cell, unnamed rows stay for a comparison up to the "
                    "declared fill, the caps hold and say so, a claim matching nothing is the whole table within the caps, no table, no match above them and a tie are refused, and the embedding only "
                    "settles what words and figures leave equal" % len(results))


if __name__ == "__main__":
    print(json.dumps(run_checks()))
