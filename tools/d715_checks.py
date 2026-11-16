#!/usr/bin/env python3
"""Checks 507 to 509 (lane neg-structure, second task): D-715 items 1 and 2 (Seckin 16 November 2026 22:31).

507, item 1: the negotiation bar passes only when every party structure the set holds meets every NEG_BAR.md
    line and class floor, and overall does too, beside both record kinds (D-711); a structure, or overall,
    that misses a line or whose block is missing fails the bar, and the reading names it.
508, item 1: a set needs MIN_ITEMS_PER_STRUCTURE headline items of each structure it holds (declared once in
    tools/score_neg_advisor.py, equal to MIN_CELL: a smaller cell has no figure), else the reading is refused,
    on the scorer's report as on the reading itself.
509, item 2: whenever the table judge names a cell, its record says which: on the cell-claim path every id the
    table tool request's lines named, run or refused (`cells_named`, `cells_named_by: request`), and with no
    request `cells_named` empty, `cells_named_by: no_text` (the choice decision writes no text); on the
    document-review methods every id the reason_first rationale or the stepwise evidence step names, also when
    the step is refused. The record changes no prompt and no score: the questions asked and the detection_dev
    labels are byte for byte the same with the record and without it.
Each proof neutralised, failed, restored and passed (scripts/effect_proof.py). No model, no item.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "scripts"), str(ROOT / "tools"), str(ROOT / "benchmark" / "baselines")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from effect_proof import prove_effect  # noqa: E402

# ---------------------------------------------------------------------------
# 507 and 508: the bar per structure


def _sc():
    import neg_advisor_checks as base
    return base.sc


def _block(good=True):
    sc = _sc()
    figs = {f: {"estimate": 0.9 if good else 0.1, "lower": 0.5} for f in sc.BAR_FIGURES}
    figs["M8"] = {"estimate": 1.0, "lower": 1.0}
    floors = [{"line": line, "figure": fig, "class": cls, "value": 0.9, "rows": 10, "floor": 0.6, "met": True}
              for line, fig, cls in sc.CLASS_FLOORS]
    return {"items": 5, "figures": figs, "floors": floors, "drops": {"share": 0.0}}


def _keys(counts):
    """Headline keys: `counts` {structure: n}, the first structure's items complete, the others missing notes."""
    out = {}
    for at, (structure, n) in enumerate(counts.items()):
        for k in range(n):
            out["%s-%d" % (structure, k)] = {"part": "P", "structure": structure,
                                            "record_kind": "complete" if at == 0 else "missing_notes"}
    return out


def observe_per_structure_pass():
    sc = _sc()
    keys = _keys({"two_singles": 5, "three_or_more": 5})
    kinds = {"complete": _block(), "missing_notes": _block()}
    cases = {"all met": {"two_singles": _block(), "three_or_more": _block(), "overall": _block()},
             "one structure misses": {"two_singles": _block(False), "three_or_more": _block(), "overall": _block()},
             "overall misses": {"two_singles": _block(), "three_or_more": _block(), "overall": _block(False)},
             "a structure's block missing": {"two_singles": _block(), "overall": _block()}}
    out = {}
    for name, blocks in cases.items():
        reading = sc.neg_bar_reading(keys, kinds, blocks)
        out[name] = [reading["passed"], reading.get("structures_failing"), sorted(reading.get("structures") or {})]
    return out


def expected_per_structure_pass():
    names = ["overall", "three_or_more", "two_singles"]
    return {"all met": [True, [], names], "one structure misses": [False, ["two_singles"], names],
            "overall misses": [False, ["overall"], names], "a structure's block missing": [False, ["three_or_more"], names]}


def observe_minimum_per_structure():
    sc = _sc()
    kinds = {"complete": _block(), "missing_notes": _block()}
    blocks = {"two_singles": _block(), "three_or_more": _block(), "overall": _block()}
    out = {"one place": sc.MIN_ITEMS_PER_STRUCTURE == sc.MIN_CELL}
    for name, counts in (("five each", {"two_singles": 5, "three_or_more": 5}),
                         ("four of one", {"two_singles": 5, "three_or_more": 4})):
        reading = sc.neg_bar_reading(_keys(counts), kinds, blocks)
        out[name] = [reading["passed"], (reading.get("refused") or "")[:60]]
    return out


def expected_minimum_per_structure():
    return {"one place": True, "five each": [True, ""],
            "four of one": [False, "the set holds fewer than 5 headline items of three_or_more ("]}


def observe_minimum_on_the_report():
    """The scorer's own report on built fixture items: four items of one structure refuse its reading."""
    import neg_structure_checks as nsc
    sc = _sc()
    builds = nsc.many(nsc.build(record_kind="complete")) + nsc.many(
        nsc.two_parties(("single", "single"), item_id="fx-two", record_kind="missing_notes", masked_party="BETA"), 4)
    reading = sc.report(*nsc.bar_set(builds), resamples=20)["neg_bar"]
    return [reading["passed"], (reading.get("refused") or "")[:60]]


def expected_minimum_on_the_report():
    return [False, "the set holds fewer than 5 headline items of two_singles (D-"]


def proofs_507():
    sc = _sc()
    return [("every structure and overall count toward the pass", observe_per_structure_pass,
             expected_per_structure_pass, lambda: patch.object(sc, "BAR_READ_ON", ("kinds",))),
            ("overall counts toward the pass", observe_per_structure_pass, expected_per_structure_pass,
             lambda: patch.object(sc, "BAR_READ_ON", ("kinds", "structures")))]


def proofs_508():
    sc = _sc()
    return [("a minimum per structure, declared once", observe_minimum_per_structure, expected_minimum_per_structure,
             lambda: patch.object(sc, "MIN_ITEMS_PER_STRUCTURE", 1)),
            ("the minimum holds on the scorer's report", observe_minimum_on_the_report, expected_minimum_on_the_report,
             lambda: patch.object(sc, "MIN_ITEMS_PER_STRUCTURE", 1))]


# ---------------------------------------------------------------------------
# 509: the cells the judge names, recorded, read by nothing


def _tac():
    import table_authority_checks as tac
    return tac


def _cell_rows():
    """{case: the cell decision row} of cell_selection.review on the fixture table, with the questions asked."""
    import cell_selection
    tac = _tac()
    out, prompts = {}, []
    made = tac.decision("holds", .9, True, None)
    rule = {"id": "CONV-T1", "category": "conv-t1", "severity": "required", "compare": "cells",
            "rule": tac.CLAIMS["difference"]}
    units = [{"unit_id": "u01", "index": 0, "text": tac.TABLE}]
    for name, reply in (("cited", "difference(r2c2, r1c2)"), ("one not in the table", "difference(r9c9, r1c2)"),
                        ("none cited", "NONE"), ("no request", None)):
        contracts, ask_request = ({}, None) if reply is None else tac._request(reply)
        asked = []

        def ask(prompt):
            asked.append(prompt)
            return made
        with tac.patched(cell_selection, "threshold_of", lambda config: .6):
            _records, calls = cell_selection.review(units, rule, None, ask, cell_selection.load_config(),
                                                    contracts=contracts, ask_request=ask_request)
        out[name] = calls["decisions"][0]
        prompts.append(asked)
    return out, prompts


def observe_cell_claim_named():
    rows, _prompts = _cell_rows()
    return {name: [row.get("cells_named"), row.get("cells_named_by"), row.get("cited_cells")] for name, row in rows.items()}


def expected_cell_claim_named():
    return {"cited": [["r1c2", "r2c2"], "request", ["r1c2", "r2c2"]],
            "one not in the table": [["r1c2", "r9c9"], "request", []],
            "none cited": [[], "request", []],
            "no request": [[], "no_text", None]}


def _labels(rows):
    """detection_dev's labels of the rows (table_authority_checks' adapter fixture), as canonical bytes."""
    tac = _tac()
    unit = "u01-p-00001"
    pairing = [{"rule_id": "CONV-%d" % n, "decisions": [dict(row, unit_id=unit)]} for n, row in enumerate(rows)]
    with tempfile.TemporaryDirectory() as tmp:
        labelled, out, _det = tac._label(tmp, "d-cells", [p["rule_id"] for p in pairing], pairing, [unit])
    view = {rule: {k: v for k, v in row.items() if k != "item_id"} for rule, row in labelled.items()}
    return json.dumps([view, out["counts"]], sort_keys=True, default=str)


def observe_no_score_and_no_prompt_moves():
    """With the record and with it left out: the same questions asked, the same leaning fields, the same labels."""
    import cell_selection
    with_rows, with_prompts = _cell_rows()
    with patch.object(cell_selection, "named_cells", lambda request_rows: None):
        without_rows, without_prompts = _cell_rows()
    strip = lambda row: {k: v for k, v in row.items() if k not in ("cells_named", "cells_named_by")}
    return {"prompts the same": with_prompts == without_prompts,
            "rows the same but the record": [strip(r) for r in with_rows.values()] == list(without_rows.values()),
            "labels byte for byte": _labels(with_rows.values()) == _labels(without_rows.values()),
            "the record present": all("cells_named" in r for r in with_rows.values())}


def expected_no_score_and_no_prompt_moves():
    return {"prompts the same": True, "rows the same but the record": True, "labels byte for byte": True,
            "the record present": True}


def _methods_rows(reply_of_step):
    import reasoning_methods_checks as rmc
    out = {}
    for group in ("choice_reason_first", "choice_stepwise"):
        with tempfile.TemporaryDirectory() as folder:
            seen = rmc.a_pass(folder, {"text": reply_of_step}, groups={group}, pairs=False, claims=True)
            row = rmc._rows_of(seen, group)[0]
            out[group] = {"named": [s.get("cells_named") for s in row["steps"] if "cells_named" in s],
                          "refused": (row.get("method_refused") or {}).get("reason"),
                          "users": [c["user"] for c in seen["calls"]],
                          "decision": (seen["by_call"].get(row.get("call_id")) or {}).get("decision")}
    return out


def _reply(step, user):
    if step == "rationale":
        return "Reasoning: R2C2 is above R1C2 in the F1 column.\nAnswer: Yes"
    return "Cells: R9C9, R2C2"


def observe_methods_named():
    rows = _methods_rows(_reply)
    return {g: [r["named"], r["refused"]] for g, r in rows.items()}


def expected_methods_named():
    return {"choice_reason_first": [[["R2C2", "R1C2"]], None], "choice_stepwise": [[["R9C9", "R2C2"]], "cell_not_shown"]}


def observe_methods_unmoved():
    import reasoning_methods as rm
    with_record = _methods_rows(_reply)
    with patch.object(rm, "named_cells", lambda text: []):
        without = _methods_rows(_reply)
    return {g: [with_record[g]["users"] == without[g]["users"],
                json.dumps(with_record[g]["decision"], sort_keys=True) == json.dumps(without[g]["decision"], sort_keys=True),
                with_record[g]["refused"] == without[g]["refused"]] for g in with_record}


def expected_methods_unmoved():
    return {"choice_reason_first": [True, True, True], "choice_stepwise": [True, True, True]}


@contextmanager
def _record_into_the_score():
    """Neutralisation of the identity proofs: the record written into a field the scorer reads (the leaning),
    so a record that moved a score would be seen."""
    import cell_selection
    with patch.object(cell_selection, "named_cells", lambda request_rows: {"leaning": "not met", "cells_named": []}):
        yield


@contextmanager
def _record_into_the_prompt():
    import reasoning_methods as rm
    real = rm.render

    def render(template, values):
        return real(template, values) + "\n" + ",".join(rm.named_cells(json.dumps(values, default=str)))
    with patch.object(rm, "render", render):
        yield


def proofs_509():
    import cell_selection
    import reasoning_methods as rm
    return [("the cell claim's named cells recorded", observe_cell_claim_named, expected_cell_claim_named,
             lambda: patch.object(cell_selection, "named_cells", lambda request_rows: None)),
            ("refused lines' ids recorded too", observe_cell_claim_named, expected_cell_claim_named,
             lambda: _tac().with_source(cell_selection, "named_cells", "for row in request_rows for a in",
                                        'for row in request_rows if row.get("ok") for a in')),
            ("no score and no prompt moves (cell claim)", observe_no_score_and_no_prompt_moves,
             expected_no_score_and_no_prompt_moves, _record_into_the_score),
            ("the methods' named cells recorded, also when refused", observe_methods_named, expected_methods_named,
             lambda: patch.object(rm, "named_cells", lambda text: [])),
            ("no prompt and no decision moves (methods)", observe_methods_unmoved, expected_methods_unmoved,
             _record_into_the_prompt)]


PROOFS = {507: proofs_507, 508: proofs_508, 509: proofs_509}
SAYS = {507: "the negotiation bar passes only when every structure the set holds and overall meet every line and floor, "
             "beside both record kinds; a failing or missing structure is named",
        508: "a set needs MIN_ITEMS_PER_STRUCTURE (= MIN_CELL, declared once) headline items of each structure it holds, "
             "else the reading is refused, on the report too",
        509: "every cell id the table judge names is recorded (the request's lines run or refused; none with no request, "
             "the choice writes no text; the methods' rationale and evidence step, refused or not), and the questions, "
             "decisions and detection_dev labels are byte for byte the same without the record"}


def run_check(number):
    proofs = PROOFS[number]()
    for name, observe, expected, neutralise in proofs:
        prove_effect(name=name, validate=lambda: True, observe=observe,
                     check=lambda observe=observe, expected=expected, name=name: (
                         "PASS" if observe() == expected() else "FAIL", name),
                     neutralise=neutralise)
    return "PASS", "%d proofs, each neutralise, fail, restore, pass, no model and no item: %s" % (len(proofs), SAYS[number])


if __name__ == "__main__":
    for n in [int(a) for a in sys.argv[1:]] or sorted(PROOFS):
        print(n, run_check(n))
