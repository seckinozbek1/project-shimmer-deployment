"""Gate checks 480 to 484: decision authority on tables (TABLE-AUTHORITY-A; D-642 items 4 (b), (c) and
(d), D-646, D-670). No model, no provider, no key: invented tables, invented decisions and an invented
SEM-TAB-FACTS file. Each proof is neutralise, fail, restore, pass (scripts/effect_proof.py).

  480  rule 2: an unsettled decision below its threshold with a verdict on top is kept on the pairing
       map row as a leaning with the model's own probability; a tie, no threshold and "cannot be
       settled" on top never lean; the decision's own fields are never changed; no record is written.
  481  rule 3 (D-642 (b)): Python's figure sub-steps on the shown cells (found in a cell, or one
       difference or ratio of two figures of one row or column within the cells' rounding) lower a
       settled "holds" with an unverified figure to a leaning, and never lower a "not met", never raise
       and never write or withhold a record of their own.
  482  scoring (D-646, D-670): under detection_dev, through the adapter's own labeller on a run folder,
       a leaning gives its unit holds or violates, the row is marked low_confidence and carries the
       class without leanings beside it; a row with no leaning field scores exactly as before; the
       counts and the scorer's item rows carry both; the D-670 "no contradiction" guard still holds.
  483  cell-grounded verdicts (D-642 (d)): when the table tool request ran, the cells the judge cited
       are recorded by id on the row; a cited id the table does not hold, or no cell cited, lowers the
       verdict ("holds" or "not met") and a lowered "not met" writes no record; with no request (as
       shipped) nothing is cited and nothing is lowered by it.
  484  NOT ENOUGH INFO development data (D-642 (c)): tools/scitab_nei_dev.py converts SEM-TAB-FACTS
       dev and test only (a train file is refused), maps entailed, refuted and unknown to SciTab's
       labels, keeps cell positions through spans, and writes no item until role B's leakage result
       shows zero hits for its part against the SciTab gate and quick pools (LEAKAGE_PROTOCOL).
  696  the rule carried to ContraDoc (D-907, #289): tools/contradoc_leaning.py reads the passage pair step's saved
       decisions; a pair not both FLAG and not both CLEAR is a low-confidence leaning, counted as its stronger
       order's direction, on its own labelled line beside the headline, whose v2_primary figure is the same bytes
       with and without the pair reading; tools/coverage_check.py counts a leaning-only document apart, never as
       the system's own answer.
"""
import contextlib
import inspect
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / "scripts", ROOT / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import cell_selection  # noqa: E402
import choice_decision  # noqa: E402
from effect_proof import prove_effect  # noqa: E402

TABLE = "\n".join(("## Results", "", "Table 3: Scores by model.", "", "| Model | Clothing | Bodyparts |", "|---|---|---|",
                   "| Alpha | 55.9 | 20.27 |", "| Beta | 58.50 | 30.78 |", "| Gamma | 71,2% | 45.27 |", ""))
CLAIMS = {"found": "Alpha scores 55.9 on clothing.", "difference": "Beta beats Alpha by 2.6 on clothing.",
          "ratio": "Beta is 1.5 times Alpha on bodyparts.", "percent form": "Gamma reaches 71.2% on clothing.",
          "unverified": "Alpha scores 61.3 on clothing.", "no figure": "Gamma is the best model."}


@contextlib.contextmanager
def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


@contextlib.contextmanager
def with_source(module, name, old, new):
    """`module.name` with one line of its own source changed, as a neutralisation. The changed
    function is compiled into the module's own globals, so a patch the observation makes to the
    module (a threshold, a constant) reaches it; the original is put back afterwards."""
    original = getattr(module, name)
    source = inspect.getsource(original)
    assert source.count(old) == 1, old
    exec(source.replace(old, new), vars(module))
    try:
        yield
    finally:
        setattr(module, name, original)


def decision(top, probability, settled, why):
    """A decision as choice_decision.settle writes one, over the three declared answers."""
    rest = (1 - probability) / 2
    answers = [{"label": a, "probability": probability if a == top else rest} for a in ("holds", "not met", "cannot be settled")]
    if why == choice_decision.TIE:
        answers = [{"label": "holds", "probability": .45}, {"label": "not met", "probability": .45},
                   {"label": "cannot be settled", "probability": .1}]
    return {"answers": answers, "declared_mass": .97, "top": None if why == choice_decision.TIE else top,
            "confidence": probability, "threshold": None if why == choice_decision.NO_THRESHOLD else .6, "settled": settled,
            "why": why, "decided": top if settled else choice_decision.UNSETTLED}


def review(claim, made, contracts=None, ask_request=None, text=TABLE):
    """cell_selection.review on one unit: (records, the pairing map row of its one decision, calls)."""
    rule = {"id": "CONV-T1", "category": "conv-t1", "severity": "required", "compare": "cells", "rule": claim}
    units = [{"unit_id": "u01", "index": 0, "text": text}]
    with patched(cell_selection, "threshold_of", lambda config: .6):
        records, calls = cell_selection.review(units, rule, None, lambda prompt: made, cell_selection.load_config(),
                                               contracts={} if contracts is None else contracts, ask_request=ask_request)
    return records, (calls["decisions"] or [None])[0], calls


def lean_view(row):
    return None if row is None else (row["decided"], row["settled"], row.get("leaning"), row.get("leaning_why"),
                                     None if row.get("leaning_confidence") is None else round(row["leaning_confidence"], 3))


# ---------- 480: rule 2, the leaning of an unsettled verdict --------------------------------------

def observe_leaning():
    below = choice_decision.BELOW_THRESHOLD
    cases = {"below, holds on top": decision("holds", .55, False, below),
             "below, not met on top": decision("not met", .5, False, below),
             "below, unclear on top": decision("cannot be settled", .5, False, below),
             "tie": decision("holds", .45, False, choice_decision.TIE),
             "no threshold": decision("holds", .9, False, choice_decision.NO_THRESHOLD),
             "settled holds": decision("holds", .9, True, None)}
    out = {}
    for name, made in cases.items():
        records, row, calls = review(CLAIMS["no figure"], made)
        out[name] = [lean_view(row), len(records), calls["leanings"]]
    return out


def expected_leaning():
    u = choice_decision.UNSETTLED
    return {"below, holds on top": [(u, False, "holds", ["below_threshold"], .55), 0, 1],
            "below, not met on top": [(u, False, "not met", ["below_threshold"], .5), 0, 1],
            "below, unclear on top": [(u, False, None, [], None), 0, 0],
            "tie": [(u, False, None, [], None), 0, 0],
            "no threshold": [(u, False, None, [], None), 0, 0],
            "settled holds": [("holds", True, None, [], None), 0, 0]}


def observe_leaning_on_the_real_phase():
    """The real phase 5.5 (cell_selection_checks' mocked run): the leaning reaches the pairing map."""
    import cell_selection_checks as csc
    run = csc._phase(lambda wrapper, prompt, n: decision("holds", .55, False, choice_decision.BELOW_THRESHOLD))
    row = (run["document"].get("cell_claims") or [{}])[0]
    got = (row.get("decisions") or [{}])[0]
    return [got.get("leaning"), got.get("leaning_why"), got.get("settled"), row.get("leanings")]


def proofs_480():
    return [
        ("only below the threshold", observe_leaning, expected_leaning,
         lambda: with_source(cell_selection, "leaning_of", 'if decision.get("why") != choice_decision.BELOW_THRESHOLD or top not in LEANABLE:',
                             "if top not in LEANABLE:")),
        ("only a verdict on top", observe_leaning, expected_leaning,
         lambda: patched(cell_selection, "LEANABLE", ("holds", "not met", "cannot be settled"))),
        ("the leaning is kept", observe_leaning, expected_leaning,
         lambda: patched(cell_selection, "leaning_of", lambda d, check=None, cited=None: (None, None, []))),
        ("the decision is never changed", observe_leaning, expected_leaning,
         lambda: with_source(cell_selection, "_row", '"settled": decision["settled"],', '"settled": decision["settled"] or bool(leaning_of(decision)[0]),')),
        ("on the real phase", observe_leaning_on_the_real_phase, lambda: ["holds", ["below_threshold"], False, 1],
         lambda: patched(cell_selection, "leaning_of", lambda d, check=None, cited=None: (None, None, []))),
    ]


# ---------- 481: rule 3, the figure sub-steps ----------------------------------------------------

def observe_figures():
    config = cell_selection.load_config()
    return {name: cell_selection.figure_check(cell_selection.select(TABLE, claim, config)["cells"], claim)
            for name, claim in sorted(CLAIMS.items())}


def expected_figures():
    one = {"written": 1, "in_cells": 1, "one_step": 0, "unverified": 0}
    step = {"written": 1, "in_cells": 0, "one_step": 1, "unverified": 0}
    return {"difference": step, "found": one, "no figure": {"written": 0, "in_cells": 0, "one_step": 0, "unverified": 0},
            "percent form": one, "ratio": step, "unverified": {"written": 1, "in_cells": 0, "one_step": 0, "unverified": 1}}


def observe_lowering():
    out = {}
    for name, claim, made in (("holds, unverified", CLAIMS["unverified"], decision("holds", .9, True, None)),
                              ("holds, one step", CLAIMS["difference"], decision("holds", .9, True, None)),
                              ("not met, unverified", CLAIMS["unverified"], decision("not met", .9, True, None)),
                              ("below, unverified", CLAIMS["unverified"], decision("holds", .5, False, choice_decision.BELOW_THRESHOLD))):
        records, row, _calls = review(claim, made)
        out[name] = [lean_view(row), len(records), (row.get("figures") or {}).get("unverified")]
    return out


def expected_lowering():
    return {"holds, unverified": [("holds", True, "holds", ["figure_unverified"], .9), 0, 1],
            "holds, one step": [("holds", True, None, [], None), 0, 0],
            "not met, unverified": [("not met", True, None, [], None), 1, 1],
            "below, unverified": [(choice_decision.UNSETTLED, False, "holds", ["below_threshold", "figure_unverified"], .5), 0, 1]}


def proofs_481():
    return [
        ("one arithmetic step", observe_figures, expected_figures,
         lambda: patched(cell_selection, "_one_step", lambda value, half, a, b: False)),
        ("within the cells' rounding", observe_figures, expected_figures,
         lambda: patched(cell_selection, "_overlaps", lambda low, high, value, half: low <= value <= high and high - low < 1e-9)),
        ("a written figure in a cell", observe_figures, expected_figures,
         lambda: with_source(cell_selection, "figure_check", "if value in shown:", "if False:")),
        ("an unverified figure lowers a holds", observe_lowering, expected_lowering,
         lambda: with_source(cell_selection, "leaning_of", 'if verdict == HOLDS_LABEL and check and check.get("unverified"):', "if False:")),
        ("never a not met", observe_lowering, expected_lowering,
         lambda: with_source(cell_selection, "leaning_of", 'if verdict == HOLDS_LABEL and check and check.get("unverified"):',
                             'if check and check.get("unverified"):')),
    ]


# ---------- 482: scoring with and without leanings -----------------------------------------------

def _adapter_checks():
    import adapter_checks
    return adapter_checks


def _label(tmp, doc, rules, rows, units, records=()):
    """The adapter's own detection_dev labeller on a synthetic run folder (adapter_checks' fixture)."""
    ac = _adapter_checks()
    det = ac._det()
    root = Path(tmp) / ("runs-%s" % doc)
    pairing = dict(ac._units_pairing(units), **{det.CELL_CLAIMS_KEY: rows})
    lines = [ac._bus_line("PRACTICE_AUDITOR", doc, [], "paired", "python"),
             ac._bus_line("PRACTICE_AUDITOR", doc, list(records), ac._MODEL_BACKEND, ac._MODEL_ID)]
    ac._incomplete_run(root, doc, completion=ac._completion(), bus_lines=lines, pairing=pairing)
    adapter = ac._adapter("scitab")
    items = [{"item_id": "i-%s" % rule, "document_id": doc, "rule_id": rule, "benchmark": "scitab"} for rule in rules]
    out = det.label_pipeline_arm(adapter.SPEC, items, root, "B3")
    return {r["rule_id"]: r for r in out["labels"]}, out, det


def observe_scoring():
    u = ["u01-p-00001", "u02-p-00002"]

    def d(decided, settled, leaning=None, unit=u[0]):
        row = {"unit_id": unit, "decided": decided, "settled": settled, "confidence": .55}
        if leaning is not False:
            row.update(leaning=leaning)
        return row
    rows = [{"rule_id": "CONV-lean-holds", "decisions": [d("cannot be settled", False, "holds")]},
            {"rule_id": "CONV-lean-notmet", "decisions": [d("cannot be settled", False, "not met")]},
            {"rule_id": "CONV-lowered-holds", "decisions": [d("holds", True, "holds")]},
            {"rule_id": "CONV-settled", "decisions": [d("holds", True)]},
            {"rule_id": "CONV-old-row", "decisions": [d("holds", False, False)]}]
    rules = [r["rule_id"] for r in rows]
    with tempfile.TemporaryDirectory() as tmp:
        labelled, out, det = _label(tmp, "d-lean", rules, rows, u[:1])
        view = {rule: (labelled[rule]["label"], labelled[rule]["label_without_leanings"], labelled[rule]["low_confidence"])
                for rule in rules}
        counts = out["counts"]["detection_dev"]
        mark = {_adapter_checks()._common()["records"].SCREENED_FIELD: True}
        guarded = [_adapter_checks()._rec("ok" + x, "CONV-ST", "ok", unit=x, relation="contradiction", **mark) for x in u]
        labelled_guard, _o, _d = _label(tmp, "d-guard", ["CONV-ST"], [], u, guarded)
    return {"rows": view, "counts": (counts["low_confidence_rows"], counts["moved_by_leanings"]),
            "guard": labelled_guard["CONV-ST"]["label"]}


def expected_scoring():
    return {"rows": {"CONV-lean-holds": ("supports", "not enough info", True),
                     "CONV-lean-notmet": ("refutes", "not enough info", True),
                     "CONV-lowered-holds": ("supports", "not enough info", True),
                     "CONV-settled": ("supports", "supports", False),
                     "CONV-old-row": ("not enough info", "not enough info", False)},
            "counts": (3, 3), "guard": "ABSTAIN"}


def observe_scorer_rows():
    """tools/score_corpus.benchmark_items carries the class without leanings and the mark."""
    import score_corpus
    ac = _adapter_checks()
    det = ac._det()
    u = ["u01-p-00001"]
    rows = [{"rule_id": "CONV-a", "decisions": [{"unit_id": u[0], "decided": "cannot be settled", "settled": False, "leaning": "holds"}]}]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "run"
        pairing = dict(ac._units_pairing(u), **{det.CELL_CLAIMS_KEY: rows})
        lines = [ac._bus_line("PRACTICE_AUDITOR", "d-sc", [], "paired", "python")]
        ac._incomplete_run(root, "d-sc", completion=ac._completion(), bus_lines=lines, pairing=pairing)
        key = {"benchmark": "scitab", "document": "d-sc.md", "items": [{"item_id": "i-a", "rule_id": "CONV-a", "gold": "supports"}]}
        got = score_corpus.benchmark_items(key, root / "d-sc", scoring="detection_dev")
    item = (got.get("items") or [{}])[0]
    return [item.get("b3_class"), item.get("b3_class_without_leanings"), item.get("low_confidence")]


def proofs_482():
    det = _adapter_checks()._det()
    return [
        ("a leaning gives its unit a state", observe_scoring, expected_scoring,
         lambda: patched(det, "CELL_LEANABLE", ())),
        ("the figure without leanings beside", observe_scoring, expected_scoring,
         lambda: with_source(det, "cell_state", "if not with_leanings:", "if False:")),
        ("the leaning is read from the pairing map", observe_scoring, expected_scoring,
         lambda: with_source(det, "cell_decisions", 'if decision.get(CELL_LEANING_KEY) in CELL_LEANABLE else None', "if False else None")),
        ("the low-confidence mark", observe_scoring, expected_scoring,
         lambda: with_source(det, "classify", 'low = plain["class"] != out["class"] or bool(set(deciding) & leaning_units)', "low = False")),
        ("the D-670 guard holds beside", observe_scoring, expected_scoring,
         lambda: patched(det, "no_state_ok", lambda reading, record: False)),
        ("the scorer's rows carry both", observe_scorer_rows, lambda: ["CLEAR", "UNDECIDED", True],
         lambda: with_source(det, "classify", 'class_without_leanings=plain["class"]', 'class_without_leanings=out["class"]')),
    ]


# ---------- 483: the cells the judge cites ------------------------------------------------------

def _request(reply):
    import table_tool_checks as ttc

    def ask_request(spec):
        return lambda prompt: reply
    return {ttc.JUDGE: ttc.CONTRACT_ON}, ask_request


def observe_citations():
    out = {}
    for name, reply, made in (("cited, holds", "difference(r2c2, r1c2)", decision("holds", .9, True, None)),
                              ("a cell not in the table", "difference(r9c9, r1c2)", decision("holds", .9, True, None)),
                              ("no cell cited", "NONE", decision("holds", .9, True, None)),
                              ("not met, cell missing", "difference(r9c9, r1c2)", decision("not met", .9, True, None)),
                              ("not met, cited", "difference(r2c2, r1c2)", decision("not met", .9, True, None))):
        contracts, ask_request = _request(reply)
        records, row, _calls = review(CLAIMS["difference"], made, contracts, ask_request)
        out[name] = [lean_view(row), row.get("cited_cells"), row.get("cited_missing"), len(records)]
    records, row, _calls = review(CLAIMS["difference"], decision("holds", .9, True, None))
    out["no request"] = [lean_view(row), "cited_cells" in row, len(records)]
    return out


def expected_citations():
    return {"cited, holds": [("holds", True, None, [], None), ["r1c2", "r2c2"], 0, 0],
            "a cell not in the table": [("holds", True, "holds", ["cited_cell_missing"], .9), [], 1, 0],
            "no cell cited": [("holds", True, "holds", ["no_cell_cited"], .9), [], 0, 0],
            "not met, cell missing": [("not met", True, "not met", ["cited_cell_missing"], .9), [], 1, 0],
            "not met, cited": [("not met", True, None, [], None), ["r1c2", "r2c2"], 0, 1],
            "no request": [("holds", True, None, [], None), False, 0]}


def proofs_483():
    import table_tools
    return [
        ("the cited cells are recorded", observe_citations, expected_citations,
         lambda: patched(cell_selection, "cited_cells", lambda rows: None)),
        ("a cited cell must exist", observe_citations, expected_citations,
         lambda: patched(cell_selection, "ID_NOT_VALID", "never")),
        ("a verdict must cite a cell", observe_citations, expected_citations,
         lambda: with_source(cell_selection, "leaning_of", 'elif not cited.get("cells"):', "elif False:")),
        ("a lowered not met writes no record", observe_citations, expected_citations,
         lambda: with_source(cell_selection, "review", 'if row["leaning"]:     # TABLE-AUTHORITY-A rule 4', "if False:  #")),
        ("Python's own id rule", observe_citations, expected_citations,
         lambda: patched(table_tools, "ID_NOT_VALID", "id_unknown")),
    ]


# ---------- 484: the NOT ENOUGH INFO development builder ------------------------------------------

SEMTAB_XML = """<document>
 <table id="Table 1">
  <caption text="Yield by site and year."></caption>
  <row row="0">
   <cell col-end="0" col-start="0" row-end="0" row-start="0" text="Site"></cell>
   <cell col-end="2" col-start="1" row-end="0" row-start="0" text="Yield"></cell>
  </row>
  <row row="1">
   <cell col-end="0" col-start="0" row-end="1" row-start="1" text="North"></cell>
   <cell col-end="1" col-start="1" row-end="1" row-start="1" text="12.5"></cell>
   <cell col-end="2" col-start="2" row-end="1" row-start="1" text="14.0"></cell>
  </row>
  <statements>
   <statement id="0" text="North yields 12.5." type="entailed"></statement>
   <statement id="1" text="North yields 99." type="refuted"></statement>
   <statement id="2" text="North was irrigated." type="unknown"></statement>
  </statements>
 </table>
</document>
"""


def _nei():
    import scitab_nei_dev
    return scitab_nei_dev


def _clear_file(tmp, nei, name, hits=0, part=None, cosine="applied", fmt=None):
    path = Path(tmp) / ("leakage_result_%s.json" % name)
    result = {"format": fmt or nei.leakage_format(), "thresholds": nei.leakage_thresholds(), "cosine_rule": cosine,
              "fingerprint_parts": [part or nei.PART], "candidates": 352,
              "candidates_by_part": ({part or nei.PART: hits} if hits else {}), "excluded_candidates": hits}
    path.write_text(json.dumps(result), encoding="utf-8")
    return path


def observe_nei():
    nei = _nei()
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        dev = tmp / "semtab" / "extracted" / "dev" / "v1.1" / "output"
        dev.mkdir(parents=True)
        (dev / "100.xml").write_text(SEMTAB_XML, encoding="utf-8")
        train = tmp / "semtab" / "extracted" / "train" / "output"
        train.mkdir(parents=True)
        (train / "200.xml").write_text(SEMTAB_XML, encoding="utf-8")
        try:
            records = nei.convert([dev])
        except nei.Refused as exc:
            records = []
            out["refused"] = str(exc).split(":")[0]
        out["records"] = [(r["label"], r["table_column_names"], r["table_content_values"], r["paper_id"] != "") for r in records]
        out["counts"] = nei.counts(records)
        try:
            nei.convert([train])
            out["train"] = "read"
        except nei.Refused as exc:
            out["train"] = str(exc).split(":")[0]
        target = tmp / "out" / "nei_dev.json"
        for name, clear in (("no clearance", None), ("a hit", _clear_file(tmp, nei, "hit", hits=1)),
                            ("cosine not applied", _clear_file(tmp, nei, "cosine", cosine="no vectors in the fingerprints: not applied")),
                            ("another part", _clear_file(tmp, nei, "part", part="other")), ("zero hits", _clear_file(tmp, nei, "clear"))):
            try:
                nei.write(records, target, clear)
                out[name] = target.is_file()
                target.unlink()
            except nei.Refused as exc:
                out[name] = str(exc).split(":")[0]
    return out


def expected_nei():
    nei = _nei()
    rows = [["North", "12.5", "14.0"]]
    header = ["Site", "Yield", ""]
    return {"records": [("supports", header, rows, True), ("refutes", header, rows, True), ("not enough info", header, rows, True)],
            "counts": {"claims": 3, "tables": 1, "papers": 1, "by_label": {"not enough info": 1, "refutes": 1, "supports": 1}},
            "train": nei.NOT_DEV_OR_TEST, "no clearance": nei.NO_CLEARANCE, "a hit": nei.NOT_CLEAR,
            "cosine not applied": nei.NOT_CLEAR, "another part": nei.NOT_CLEAR, "zero hits": True}


def proofs_484():
    nei = _nei()
    return [
        ("labels mapped", observe_nei, expected_nei, lambda: patched(nei, "LABELS", {"entailed": "supports", "refuted": "refutes",
                                                                                     "unknown": "refutes"})),
        ("cell positions kept through spans", observe_nei, expected_nei,
         lambda: with_source(nei, "_grid", 'for col in range(start, end + 1)', 'for col in range(start, start + 1)')),
        ("dev and test only", observe_nei, expected_nei, lambda: patched(nei, "_admitted", lambda path: True)),
        ("no item without role B's clearance", observe_nei, expected_nei, lambda: patched(nei, "clearance_refusal", lambda path: None)),
        ("zero hits for its own part", observe_nei, expected_nei,
         lambda: with_source(nei, "clearance_refusal", "if hits or result.get(\"excluded_candidates\"):", "if False:")),
        ("the cosine rule applied", observe_nei, expected_nei,
         lambda: with_source(nei, "clearance_refusal", 'if result.get("cosine_rule") != "applied":', "if False:")),
    ]


# ---------- 696: ContraDoc's leaning line (D-907) ------------------------------------------------

CDOC_RULE = "CONV-CDOC-01"
CDOC_CLASSES = {"contradicts": "FLAG", "does not": "CLEAR", "cannot tell": "UNDECIDED"}


def _cl():
    import contradoc_leaning
    return contradoc_leaning


def _coverage():
    import coverage_check
    return coverage_check


def pair_row(top, probability, settled=True, why=None, passages=(0, 1)):
    """One order's saved decision row, as passage_pairs.decision_row writes it."""
    rest = (1 - probability) / 2
    return {"passages": list(passages), "decided": top if settled else choice_decision.UNSETTLED, "settled": settled,
            "why": why, "confidence": probability, "threshold": .6 if why != choice_decision.NO_THRESHOLD else None,
            "declared_mass": .97, "answers": {a: (probability if a == top else rest) for a in CDOC_CLASSES}}


def both(first, second):
    """A pair's two orders, the second with its passages turned round."""
    return [first, dict(second, passages=list(reversed(first["passages"])))]


FLAG_ORDER, CLEAR_ORDER = pair_row("contradicts", .9), pair_row("does not", .9)
UNCLEAR_ORDER = pair_row("cannot tell", .8)
# The four fixture documents: (pairs, v2_primary record kept?, gold).
CDOC_DOCS = {"d-det": (both(FLAG_ORDER, FLAG_ORDER), True, "contradictory"),
             "d-lean": (both(FLAG_ORDER, UNCLEAR_ORDER), False, "contradictory"),
             "d-clear": (both(CLEAR_ORDER, CLEAR_ORDER), False, "not contradictory"),
             "d-clean": (both(CLEAR_ORDER, UNCLEAR_ORDER), False, "not contradictory")}


def _pair_entry(decisions, kept=0):
    return {"rule_id": CDOC_RULE, "form": "decision", "made": len(decisions), "reused": 0, "failed": 0,
            "unreadable": 0, "refused": [], "stopped": None, "raised": None, "not_asked": None, "kept": kept,
            "decisions": decisions}


def cdoc_runs(tmp, with_pairs=True):
    """[{key, run}] of the four synthetic ContraDoc runs; `with_pairs` False leaves the pair decisions out, as a run
    the leaning reading had nothing to read in."""
    ac = _adapter_checks()
    mark = {ac._common()["records"].SCREENED_FIELD: True}
    unit = "u01-p-00001"
    root = Path(tmp) / ("cdoc-%s" % with_pairs)
    out = []
    for doc, (decisions, kept, gold) in CDOC_DOCS.items():
        records = [ac._rec("r-" + doc, CDOC_RULE, "irregular", unit=unit, relation="contradiction", **mark)] if kept else []
        pairing = dict(ac._units_pairing([unit]), passage_pairs=[_pair_entry(decisions if with_pairs else [], int(kept))])
        lines = [ac._bus_line("PRACTICE_AUDITOR", doc, records, "paired", "python")]
        ac._incomplete_run(root, doc, completion=ac._completion(), bus_lines=lines, pairing=pairing)
        key = root / ("%s.key.json" % doc)
        key.write_text(json.dumps({"benchmark": "contradoc", "document": doc + ".md",
                                   "items": [{"item_id": "i-" + doc, "rule_id": CDOC_RULE, "gold": gold}]}), encoding="utf-8")
        out.append({"key": str(key), "run": str(root / doc)})
    return out


def _independent_headline(pairs):
    """The v2_primary figure straight from the scorer's rows and the adapter's metrics, no pair reading."""
    import score_corpus
    adapter = score_corpus._adapter_for("contradoc")
    labelled = []
    for pair in pairs:
        key = json.loads(Path(pair["key"]).read_text(encoding="utf-8"))
        for r in score_corpus.benchmark_items(key, Path(pair["run"]))["items"]:
            labelled.append((adapter.SPEC.label(r["b3_class"]), adapter.SPEC.label(r["gold_class"])))
    return adapter.metrics.accuracy(labelled)["accuracy"]


def observe_cdoc_headline():
    """(a) The headline block is the same bytes with the pair decisions and without them, and is the v2_primary
    figure the scorer gives alone."""
    cl = _cl()
    with tempfile.TemporaryDirectory() as tmp:
        with_pairs = cl.score(cdoc_runs(tmp, True))
        without = cl.score(cdoc_runs(tmp, False))
        independent = _independent_headline(cdoc_runs(tmp + "/x", True))
    same = json.dumps(with_pairs["headline"], sort_keys=True) == json.dumps(without["headline"], sort_keys=True)
    return [same, with_pairs["headline"]["accuracy"] == independent, independent]


def expected_cdoc_headline():
    return [True, True, .75]


def observe_cdoc_pairs():
    """(b) Each pair kind read as the rule says, with and without the post hoc threshold."""
    cl = _cl()
    no_t = pair_row("contradicts", .5, False, choice_decision.NO_THRESHOLD)
    below = pair_row("contradicts", .5, False, choice_decision.BELOW_THRESHOLD)
    cases = {"FLAG/FLAG": both(FLAG_ORDER, FLAG_ORDER), "CLEAR/CLEAR": both(CLEAR_ORDER, CLEAR_ORDER),
             "FLAG/UNDECIDED": both(FLAG_ORDER, UNCLEAR_ORDER), "CLEAR/FLAG stronger CLEAR": both(FLAG_ORDER, pair_row("does not", .95)),
             "below threshold leans": both(below, UNCLEAR_ORDER), "no threshold never leans": both(no_t, UNCLEAR_ORDER),
             "one order only": [FLAG_ORDER]}
    out = {name: list(cl.pair_reading(orders, CDOC_CLASSES)) for name, orders in cases.items()}
    out["settled again at .4"] = list(cl.pair_reading([no_t, no_t], CDOC_CLASSES, .4))
    out["settled again at .6"] = list(cl.pair_reading([no_t, no_t], CDOC_CLASSES, .6))
    return out


def expected_cdoc_pairs():
    return {"FLAG/FLAG": ["detection", None, "FLAG"], "CLEAR/CLEAR": ["clear", None, "CLEAR"],
            "FLAG/UNDECIDED": ["leaning", "FLAG/UNDECIDED", "FLAG"], "CLEAR/FLAG stronger CLEAR": ["leaning", "CLEAR/FLAG", "CLEAR"],
            "below threshold leans": ["leaning", "UNDECIDED/UNDECIDED", "FLAG"],
            "no threshold never leans": ["leaning", "UNDECIDED/UNDECIDED", None],
            "one order only": ["leaning", "FAILED/FLAG", "FLAG"],
            "settled again at .4": ["detection", None, "FLAG"], "settled again at .6": ["leaning", "UNDECIDED/UNDECIDED", "FLAG"]}


def observe_cdoc_lines():
    """(b) The leaning line moves, the headline does not, and the counts say why."""
    cl = _cl()
    with tempfile.TemporaryDirectory() as tmp:
        got = cl.score(cdoc_runs(tmp, True))
    w, p = got["with_leanings"], got["pairs"]
    return [got["headline"]["accuracy"], w["accuracy"], w["low_confidence_items"], w["moved_and_right"],
            p["detections"], p["clear"], p["leanings_by_kind"], p["leanings_by_direction"], got["documents_by_reading"]]


def expected_cdoc_lines():
    return [.75, 1.0, 1, 1, 1, 1, {"CLEAR/UNDECIDED": 1, "FLAG/UNDECIDED": 1}, {"CLEAR": 1, "FLAG": 1},
            {"all_clear": 1, "detection": 1, "leaning_only": 2}]


def observe_cdoc_coverage():
    """Coverage: a leaning-only document is counted apart and never answered; an all-clear decision-form document and
    a reply-form document are judged absences, as before."""
    cov = _coverage()
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        docs = {"d-lean": [_pair_entry(both(FLAG_ORDER, UNCLEAR_ORDER))],
                "d-clear": [_pair_entry(both(CLEAR_ORDER, CLEAR_ORDER))],
                "d-reply": [{"rule_id": CDOC_RULE, "made": 2, "failed": 0, "unreadable": 0, "refused": [], "kept": 0,
                             "one_order_only": 1}]}
        for doc, rows in docs.items():
            (runs / doc / "audit").mkdir(parents=True)
            (runs / doc / "audit" / "pairing_map.json").write_text(json.dumps({doc: {"passage_pairs": rows}}), encoding="utf-8")
        labels = Path(tmp) / "labels.json"
        labels.write_text(json.dumps({"primary": {"labels": [{"document_id": d, "basis": "silent", "class": "CLEAR"}
                                                             for d in docs]}}), encoding="utf-8")
        got = cov.counts(labels, str(runs))
    return got


def expected_cdoc_coverage():
    return {"items": 3, "answered": 2, "post_hoc": 0, "not_answered": 1,
            "by_basis": {"judged_absence": 2, "leaning_only": 1}, "leaning_only": 1}


LEAK = ('headline = headline_line(items)',
        'headline = headline_line([(n, dict(r, b3_class=with_leanings(r["b3_class"], document_reading(pairs[n]["run"], '
        'str(json.loads(Path(pairs[n]["key"]).read_text(encoding="utf-8")).get("document") or "").rsplit(".", 1)[0], '
        'classes)))) for n, r in items])')


def proofs_696():
    cl, cov = _cl(), _coverage()
    return [
        ("the headline is the v2_primary figure alone, the same bytes with and without the pair reading",
         observe_cdoc_headline, expected_cdoc_headline, lambda: with_source(cl, "score", *LEAK)),
        ("FLAG/FLAG stays a detection, FLAG/UNDECIDED is a leaning", observe_cdoc_pairs, expected_cdoc_pairs,
         lambda: with_source(cl, "pair_reading", "if names == [FLAG, FLAG]:", "if FLAG in names:")),
        ("CLEAR/CLEAR stays clear", observe_cdoc_pairs, expected_cdoc_pairs,
         lambda: with_source(cl, "pair_reading", "if names == [CLEAR, CLEAR]:", "if CLEAR in names:")),
        ("a leaning counts as its stronger order's direction", observe_cdoc_pairs, expected_cdoc_pairs,
         lambda: with_source(cl, "pair_reading", "best = max(p for p, _d in directed)", "best = min(p for p, _d in directed)")),
        ("the post hoc threshold settles from the saved probabilities", observe_cdoc_pairs, expected_cdoc_pairs,
         lambda: with_source(cl, "order_reading", "if threshold is not None:", "if False:")),
        ("the leaning line moves while the headline does not", observe_cdoc_lines, expected_cdoc_lines,
         lambda: patched(cl, "with_leanings", lambda base, reading: base)),
        ("coverage: a leaning-only document is counted apart", observe_cdoc_coverage, expected_cdoc_coverage,
         lambda: with_source(cov, "pair_state", "return LEANING_ONLY", "return 'judged_absence'")),
        ("coverage: a leaning is never the system's own answer", observe_cdoc_coverage, expected_cdoc_coverage,
         lambda: patched(cov, "ANSWERED", cov.ANSWERED + (cov.LEANING_ONLY,))),
    ]


# ---------- running -------------------------------------------------------------------------------

PROOFS = {480: proofs_480, 481: proofs_481, 482: proofs_482, 483: proofs_483, 484: proofs_484, 696: proofs_696}
SAYS = {480: "an unsettled verdict below its threshold is kept as a leaning with the model's probability; a tie, no threshold "
             "and cannot-be-settled on top never lean; the decision is never changed; it reaches the real pairing map",
        481: "a claim figure is found in a shown cell or one difference or ratio away within the cells' rounding; an "
             "unverified figure lowers a settled holds to a leaning and never a not met",
        482: "detection_dev reads a leaning as a low-confidence state with the class without leanings beside it, an old row "
             "scores as before, the counts and the scorer's rows carry both, and the D-670 guard holds",
        483: "the cells the judge's request cited are recorded by id; a cited cell the table does not hold, or none cited, "
             "lowers the verdict and a lowered not met writes no record; with no request nothing changes",
        484: "SEM-TAB-FACTS dev and test only are converted with labels mapped and spans kept, and no item is written "
             "without role B's zero-hit leakage result for the part",
        696: "ContraDoc's headline is the v2_primary figure alone, the same bytes with and without the pair reading; a pair "
             "not both FLAG and not both CLEAR is a low-confidence leaning counted as its stronger order's direction, on "
             "its own line beside the headline; coverage counts a leaning-only document apart, never as answered"}


def validate():
    return cell_selection.CONFIG_PATH.is_file() and (ROOT / "tools" / "scitab_nei_dev.py").is_file()


def run_check(number):
    proofs = PROOFS[number]()
    for name, observe, expected, neutralise in proofs:
        prove_effect(name=name, validate=validate, observe=observe,
                     check=lambda observe=observe, expected=expected, name=name: ("PASS" if observe() == expected() else "FAIL", name),
                     neutralise=neutralise)
    return "PASS", "%d proofs, each neutralise, fail, restore, pass: %s" % (len(proofs), SAYS[number])


if __name__ == "__main__":
    for n in [int(a) for a in sys.argv[1:]] or sorted(PROOFS):
        print(n, run_check(n))
