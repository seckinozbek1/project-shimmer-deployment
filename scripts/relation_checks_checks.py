"""Gate check 319: the four relations INFRA-045 appended are computed by Python (RELATIONS-A).

Constitution amendment INFRA-045 (operator-approved 2026-10-31) appends rate_mismatch,
carry_mismatch, copy_mismatch and unit_mismatch to the typed Finding record, and
scripts/relation_checks.py computes them from the document's own figures and the rules'
own words. This check EXECUTES them on one synthetic document whose vocabulary is
invented (no domain, no currency, no language is named), through four paths:

1. the planner (paired_review.plan_calls): a rate a rule states over a part, a whole and
   a percentage; a stated total in another measure than its column, and a reading in
   another measure than the band its rule states, each converted by a declared prefix; a
   table row that does not carry the figure of the unit it names; a first row that does
   not carry the column sum of the unit before. And the refusals: a tied third figure, a
   measure that does not convert, a row naming two units, and a unit before that does
   not add up on its own, each written to the refusal sink and never computed.
2. the paired review itself (pipeline._paired_convention_review, the judging call
   stubbed, no model): each relation posted on the bus as Python's record, a copy and a
   carry citing their own unit's passage and the other unit's as compared, the refusals
   on the pairing map, an amendment rendered from each record with the relation's own
   sentence, and that sentence in the second output language (tr) from the catalog.
3. a multi-round case: a unit whose text is unchanged but whose unit before changed is
   recomputed (the neighbours signature input), never reused.
4. the governed record: INFRA-045 is the next id after INFRA-044, operator-approved, and
   the four relations are appended at the end of the contract and its fallback.

Every case is proven by neutralise, fail, restore, pass (scripts/effect_proof.py). No
model, no pipeline run, no provider, no network.
"""
from __future__ import annotations

import asyncio
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from effect_proof import prove_effect  # noqa: E402
import constitution_guard  # noqa: E402
import finding_record  # noqa: E402
import localization  # noqa: E402
import paired_review  # noqa: E402
import pairing_map  # noqa: E402
import relation_checks  # noqa: E402

NEW = relation_checks.RELATIONS

DOC = "\n".join([
    "# Ledger Qx", "",
    "This ledger lists entries, batches, counts and samples.", "",
    "## Entry Alpha", "", "Lots: 12 box", "Price per box: 3 zed/box", "Line sum: 36 zed", "",
    "## Entry Beta", "", "Lots: 5 box", "Price per box: 4 zed/box", "Line sum: 20 zed", "",
    "## Entry Gamma", "", "Lots: 2 box", "Price per box: 3 zed/box", "Line sum: 6 zed", "",
    "## Entry Gamma", "", "Lots: 3 box", "Price per box: 3 zed/box", "Line sum: 9 zed", "",
    "## Batch One", "",
    "| Entry | Line sum (zed) |", "|---|---|", "| Entry Alpha | 36 |", "| Entry Beta | 25 |",
    "| Entry Gamma | 6 |", "",
    "Total line sum: 67 zed", "Levy rate: 5%", "Levy due: 4 zed", "Carriage: 6.7 zed",
    "Carriage share: 10%", "",
    "## Batch Two", "",
    "Total line sum: 40 zed", "Total spare sum: 40 zed", "Levy rate: 5%", "Levy due: 3 zed", "",
    "## Count One", "",
    "| Movement | Stock (box) |", "|---|---|", "| Opening | 10 |", "| In | 5 |", "",
    "Closing stock: 15 box", "",
    "## Count Two", "",
    "| Movement | Stock (box) |", "|---|---|", "| Opening | 18 |", "| In | 2 |", "",
    "Closing stock: 20 box", "",
    "## Count Three", "",
    "| Movement | Stock (box) |", "|---|---|", "| Opening | 20 |", "| In | 1 |", "",
    "Closing stock: 25 box", "",
    "## Count Four", "",
    "| Movement | Stock (box) |", "|---|---|", "| Opening | 21 |", "| In | 4 |", "",
    "Closing stock: 25 box", "",
    "## Sample Ash", "",
    "| Portion | Mass (g) |", "|---|---|", "| First | 1.5 |", "| Second | 2.5 |", "",
    "Total mass: 0.004 kg", "",
    "## Sample Oak", "",
    "| Portion | Mass (g) |", "|---|---|", "| First | 1.5 |", "| Second | 2.5 |", "",
    "Total mass: 4 zed", "",
    "## Probe One", "", "Reading: 0.03 g", "",
    # D-198 additions. Sample Elm: a total in another measure that no rule declares.
    "## Sample Elm", "",
    "| Portion | Weight (g) |", "|---|---|", "| First | 1 |", "| Second | 2 |", "",
    "Total weight: 0.003 kg", "",
    # Probe Two: a figure the rule names, in a measure whose base is not declared.
    "## Probe Two", "", "Signal: 0.03 zed", "",
    # Invoice Cedar: correct figures (100 plus 20 percent of it is 120) that a part-of-a-
    # whole reading would call wrong.
    "## Invoice Cedar", "", "Surcharge rate: 20%", "Plain sum: 100 zed", "Full sum: 120 zed", "",
    # Share Fir: a share of a whole of zero.
    "## Share Fir", "", "Spare share: 200%", "Spare: 5 zed", "Base sum: 0 zed", "",
    # Fee Birch and Toll Pine: an agreeing rate under a rule that also asks something else,
    # and one under a rule that asks nothing else.
    "## Fee Birch", "", "Fee rate: 10%", "Fee: 5 zed", "Base: 50 zed", "Approver: staff seven", "",
    "## Toll Pine", "", "Toll rate: 10%", "Toll: 5 zed", "Toll base: 50 zed", "",
]) + "\n"


def _rule(rid, own, text, scope=None):
    rule = {"id": rid, "category": own, "severity": "required", "subjects": ["conformance"],
            "rule": text}
    if scope:
        rule["scope"] = list(scope)
    return rule


RULES = [
    _rule("CONV-001", "conv-qa", "The line sum must equal the lots times the price per box."),
    _rule("CONV-002", "conv-qb", "The total line sum must equal the sum of the line sum column."),
    _rule("CONV-003", "conv-qc", "The levy due must equal the levy rate applied to the batch's stated total."),
    _rule("CONV-004", "conv-qd", "Each entry of a batch must carry the line sum of the unit it names."),
    _rule("CONV-005", "conv-qe",
          "The carriage share must equal the carriage as a percentage of the batch's stated total."),
    _rule("CONV-006", "conv-qf",
          "The closing stock must equal the sum of the stock column, and the opening row must "
          "carry the sum of the stock column of the count before it."),
    _rule("CONV-007", "conv-qg", "The total mass must equal the sum of the mass column."),
    _rule("CONV-008", "conv-qh", "The reading must lie between 10 mg and 60 mg."),
    # D-198 (open item 76): the rules about measures, each declaring by its scope the
    # figure it governs; a unit mismatch is attributed to them, not to CONV-007 or CONV-008.
    _rule("CONV-009", "conv-qi", "Each total mass must be written in the measure of the column it adds up.",
          scope=["total mass"]),
    _rule("CONV-010", "conv-qj", "Each reading must be written in the measure its range is given in.",
          scope=["reading"]),
    _rule("CONV-011", "conv-qk", "The full sum must equal the plain sum plus the surcharge at the surcharge rate."),
    _rule("CONV-012", "conv-ql", "The fee must equal the fee rate of the base, and the approver must be named."),
    _rule("CONV-013", "conv-qm", "The toll must equal the toll rate of the toll base."),
    _rule("CONV-014", "conv-qn", "The signal must lie between 10 mzed and 60 mzed."),
    _rule("CONV-015", "conv-qo", "The total weight must equal the sum of the weight column."),
    _rule("CONV-016", "conv-qp", "The spare share must equal the spare as a percentage of the base sum."),
]
REGISTRY = {"conventions": RULES}


def _units(text=DOC):
    return {u["unit_id"]: u for u in pairing_map.split_units(text, document_id="ledger_qx")}


def _plans(text=DOC):
    units = _units(text)
    vocab = set()
    for u in units.values():
        vocab |= pairing_map.unit_fields(u["text"])
    pairing = pairing_map.build_pairing_map(text, RULES, document_id="ledger_qx", convention_registry=REGISTRY)
    pairs, _ = paired_review.pairs_from_map(pairing)
    refusals = []
    plans = paired_review.plan_calls(
        units, pairs, {r["id"]: r for r in RULES}, vocab,
        needed_fields_for=lambda t: pairing_map.needed_fields(t, vocab),
        known_units=set(), relation_refusal_sink=refusals)
    return plans, refusals


def _check_row(unit_id, rule_id, c):
    return (unit_id, rule_id, c["relation"], c.get("stated_field"), c.get("computed"),
            c.get("computed_unit"), c.get("stated"), c.get("stated_unit"), c.get("compared_unit_id", ""))


def observe_planner():
    plans, refusals = _plans()
    rows = sorted(_check_row(p["unit"]["unit_id"], p["rule"]["id"], c)
                  for p in plans for c in p["checks"]
                  if c["relation"] in NEW or c["relation"] == "sum_mismatch")
    return {"checks": rows,
            "refusals": sorted((r["unit_id"], r["rule_id"], r["relation"], r["reason"]) for r in refusals)}


PLANNER = {
    "checks": [
        # the rate: 5% of the stated 67 is 3.35, not 4 (the rule names the levy due first)
        ("u05-batch-one", "CONV-003", "rate_mismatch", "levy due", 3.35, "zed", 4.0, "zed", ""),
        # the copy: Entry Beta states 20, the batch row carries 25
        ("u05-batch-one", "CONV-004", "copy_mismatch", "line sum row2", 20.0, "zed", 25.0, "zed",
         "u02-entry-beta"),
        # the carry: Count One adds up to 15, Count Two opens at 18
        ("u08-count-two", "CONV-006", "carry_mismatch", "stock row1", 15.0, "box", 18.0, "box",
         "u07-count-one"),
        # Count Three does not add up (21 against 25): its own sum mismatch
        ("u09-count-three", "CONV-006", "sum_mismatch", "closing stock", 21.0, "box", 25.0, "box", ""),
        # the measures: 0.004 kg is 4 g, the column's measure; 0.03 g is 30 mg, the band's;
        # each attributed to the rule whose scope declares the figure (D-198, open item 76),
        # not to the sum rule CONV-007 or the band rule CONV-008
        ("u11-sample-ash", "CONV-009", "unit_mismatch", "total mass", 4.0, "g", 0.004, "kg", ""),
        ("u13-probe-one", "CONV-010", "unit_mismatch", "reading", 30.0, "mg", 0.03, "g", ""),
    ],
    "refusals": [
        # Batch Two: the rule's stated total could be either of two totals
        ("u06-batch-two", "CONV-003", "rate_mismatch", "rate_third_figure_tied"),
        # Batch One's third row names two units headed Entry Gamma
        ("u05-batch-one", "CONV-004", "copy_mismatch", "copy_subject_ambiguous"),
        # Count Four: the count before does not add up, so what it carries is undecided
        ("u10-count-four", "CONV-006", "carry_mismatch", "carry_source_does_not_add_up"),
        # Sample Oak: a total in zed over a column in g does not convert
        ("u12-sample-oak", "", "unit_mismatch", "unit_not_convertible"),
        # D-198. Sample Elm: no rule declares the total weight or its measure
        ("u14-sample-elm", "", "unit_mismatch", "unit_rule_undeclared"),
        # Probe Two: the signal the band rule names is in a measure whose base is undeclared
        ("u15-probe-two", "CONV-014", "unit_mismatch", "unit_not_convertible"),
        # Invoice Cedar: 100 plus 20 percent of it is 120, so the figures fit a reading other
        # than a part of a whole, and no rate record is minted on the correct document
        ("u16-invoice-cedar", "CONV-011", "rate_mismatch", "rate_reading_ambiguous"),
        # Share Fir: a share of a whole of zero
        ("u17-share-fir", "CONV-016", "rate_mismatch", "rate_part_whole_undecided"),
    ],
}


PLANNER = {k: sorted(v) for k, v in PLANNER.items()}


def _patched(target, name, value):
    return patch.object(target, name, value)


def no_rate():
    return _patched(relation_checks, "rate_checks", lambda *a, **k: [])


def tie_broken():
    return _patched(relation_checks, "unique_best", lambda scored: scored[0][1])


def nothing_converts():
    return _patched(relation_checks, "conversion_factor", lambda a, b: None)


def no_band_measure():
    return _patched(relation_checks, "band_unit_checks", lambda *a, **k: [])


def no_copy():
    return _patched(relation_checks, "copy_checks", lambda *a, **k: [])


def first_source_taken():
    return _patched(relation_checks, "one_source", lambda sources: sources[0] if sources else None)


def no_carry():
    return _patched(relation_checks, "carry_checks", lambda *a, **k: [])


def source_assumed_to_add_up():
    return _patched(relation_checks, "source_adds_up", lambda column_sum, totals: True)


def rule_words_ignored():
    """The rule gate gone: every label of the unit counts as named by every rule."""
    return _patched(relation_checks, "named_labels",
                    lambda rule_text, labels: {tuple(lb): i for i, lb in enumerate(labels)})


def unit_by_sum_rule():
    """D-198 neutralised: a unit mismatch takes the first paired rule, as before."""
    return _patched(relation_checks, "measure_rule",
                    lambda check, rule_ids, rules_by_id: (list(rule_ids)[0], None))


def other_reading_ignored():
    """D-198 neutralised: the figures' other plain reading is not looked at."""
    return _patched(relation_checks, "other_reading_fits", lambda small, large, fraction: False)


def zero_whole_computed():
    """D-198 neutralised: a share of a zero whole is minted with no computed figure, as before."""
    real = relation_checks._rate_check

    def old(scalars, named, rate_label, part, whole, scale, *, unit_text=""):
        out = real(scalars, named, rate_label, part, whole, scale, unit_text=unit_text)
        if out is None:
            out = {"relation": relation_checks.RATE, "computed": None, "computed_unit": scalars[rate_label][1],
                   "stated": scalars[rate_label][0], "stated_unit": scalars[rate_label][1], "agrees": False,
                   "basis": "", "stated_field": " ".join(rate_label),
                   "rate_fields": [" ".join(rate_label), " ".join(part), " ".join(whole)],
                   "rate_figures": [scalars[rate_label][0], scalars[part][0], scalars[whole][0]]}
        return out
    return _patched(relation_checks, "_rate_check", old)


def band_refusal_dropped():
    """D-198 neutralised: an unconvertible measure on the band path is skipped silently."""
    real = relation_checks.band_unit_checks

    def silent(*a, **k):
        k["refuse_labels"] = ()
        return real(*a, **k)
    return _patched(relation_checks, "band_unit_checks", silent)


def observe_settling():
    """D-198 (fix 6): which plans each rate rule keeps. Fee Birch's rule also names the
    approver, so its uncomputable call stays; Toll Pine's names nothing but the rate."""
    plans, _refusals = _plans()
    return sorted((p["unit"]["unit_id"], p["rule"]["id"], p["kind"]) for p in plans
                  if p["unit"]["unit_id"] in ("u18-fee-birch", "u19-toll-pine"))


SETTLING = [("u18-fee-birch", "CONV-012", "uncomputable")]


def every_producer_settles():
    """D-198 neutralised: any rate, copy or carry check settles its rule, as before."""
    return _patched(paired_review, "rule_settled_by", lambda *a, **k: True)


# Measures whose letters read as a prefix and a base no declaration names (D-198, fix 7)
# are refused; declared ones convert.
CONVERSION_PAIRS = (("ha", "a"), ("dB", "B"), ("min", "in"), ("cd", "d"), ("mL", "L"), ("kg", "g"))


def observe_conversions():
    return {"%s/%s" % pair: relation_checks.conversion_factor(*pair) for pair in CONVERSION_PAIRS}


CONVERSIONS = {"ha/a": None, "dB/B": None, "min/in": None, "cd/d": None, "mL/L": 0.001, "kg/g": 1000.0}


def letters_read_as_prefixes():
    """D-198 neutralised: every token read by its letters, as before."""
    def by_letters(token):
        out = [("", token)]
        for prefix in relation_checks.conversions()["prefixes"]:
            if token.startswith(prefix) and len(token) > len(prefix):
                out.append((prefix, token[len(prefix):]))
        return out
    return _patched(relation_checks, "_prefix_split", by_letters)


# ---- 2. the paired review --------------------------------------------------------------

def _review_run(td):
    import convention_assignment
    import pipeline
    from harness.run_agent import build_orchestrator

    agents = {"PRACTICE_AUDITOR": {"subjects": ["conformance"]}}
    assignment = convention_assignment.assign_conventions(RULES, agents)
    doc = {"id": "ledger_qx", "name": "ledger_qx.md", "text": DOC}
    # Phase 5.5 places each unit at its own passage; here every unit is placed.
    doc["_unit_refs"] = {uid: "REF-%04d" % (900 + i) for i, uid in enumerate(sorted(_units()))}
    pairing = pairing_map.build_pairing_map(DOC, RULES, document_id=doc["id"], convention_registry=REGISTRY)

    async def stub_run_one(wrapper, payload, objectives, **kw):
        return {"ok": True, "parsed": [], "agent": wrapper.name}

    orch = build_orchestrator(root=ROOT, out_root=td)
    with patch.object(pipeline, "_run_one", stub_run_one):
        asyncio.run(pipeline._paired_convention_review(
            orch, {}, doc, pairing, REGISTRY, [], "objectives", {doc["id"]: 1}, 1, None,
            context_refs=[], convention_assignment=assignment))
    posted = []
    for m in orch.bus.read_all():
        body = m.get("body") or {}
        if body.get("event") == "AGENT_OUTPUT" and body.get("backend") == "paired":
            who = finding_record.written_by(body.get("backend"), body.get("model"))
            for it in (body.get("payload") or {}).get("items") or []:
                if finding_record.is_finding(it) and it.get("relation") in NEW:
                    posted.append(dict(it, _who=who))
    saved = json.loads((orch.run_context.audit_dir() / "pairing_map.json").read_text(encoding="utf-8"))
    return doc, posted, saved.get(doc["id"]) or {}


def observe_review():
    with tempfile.TemporaryDirectory(prefix="shimmer_relations_review_") as td:
        doc, posted, entry = _review_run(td)
    unit_texts = paired_review.unit_texts_for(DOC, doc["id"])
    rules_by_id = {r["id"]: r for r in RULES}
    amendments, _added = paired_review.ensure_amendments_for_findings(
        [], posted, unit_texts=unit_texts, rules_by_id=rules_by_id, unit_refs=doc["_unit_refs"])
    by_key = {(a["finding_unit_id"], a["finding_relation"]): a for a in amendments}
    rows = []
    for it in sorted(posted, key=lambda i: (i["unit_id"], i["relation"])):
        a = by_key.get((it["unit_id"], it["relation"])) or {}
        lead = (a.get("comment") or "").split(". Computed in code")[0] + "."
        rows.append({"unit": it["unit_id"], "relation": it["relation"], "verdict": it["record_verdict"],
                     "written_by": it["_who"], "value_a": it.get("value_a"), "value_b": it.get("value_b"),
                     "field": it.get("field_label"), "cites": it.get("source_refs"),
                     "compared": it.get("compared_with_refs", []), "lead": lead,
                     "lead_tr": localization.message(lead, "tr")})
    return {"records": rows,
            "refusals": sorted((r["unit_id"], r["relation"], r["reason"])
                               for r in entry.get("relation_refusals") or []),
            "refusal_count": entry.get("relation_refusals_count")}


def expected_review():
    ref = {uid: "REF-%04d" % (900 + i) for i, uid in enumerate(sorted(_units()))}

    def row(unit, relation, a, b, field, lead, lead_tr, compared=()):
        return {"unit": unit, "relation": relation, "verdict": "irregular", "written_by": "python",
                "value_a": a, "value_b": b, "field": field, "cites": [ref[unit]],
                "compared": [ref[c] for c in compared], "lead": lead, "lead_tr": lead_tr}

    return {"records": [
        row("u05-batch-one", "copy_mismatch", 20.0, 25.0, "line sum row2",
            "Unit u05-batch-one (Batch One) under rule CONV-004 (operator's id CONV-QD): the line sum "
            "row2 carries 25 zed, but unit u02-entry-beta states its line sum as 20 zed.",
            "u05-batch-one (Batch One) birimi, CONV-004 (operatörün kimliği CONV-QD) kuralı: 'line sum "
            "row2' değeri 25 zed; ancak u02-entry-beta birimi kendi 'line sum' değerini 20 zed olarak "
            "belirtiyor.", compared=["u02-entry-beta"]),
        row("u05-batch-one", "rate_mismatch", 3.35, 4.0, "levy due",
            "Unit u05-batch-one (Batch One) under rule CONV-003 (operator's id CONV-QC): 'levy rate' (5) "
            "of 'total line sum' (67) gives 3.35 zed, but the stated levy due is 4 zed.",
            "u05-batch-one (Batch One) birimi, CONV-003 (operatörün kimliği CONV-QC) kuralı: 'total line "
            "sum' (67) değerine 'levy rate' (5) uygulandığında 3.35 zed çıkıyor; ancak belirtilen 'levy "
            "due' değeri 4 zed."),
        row("u08-count-two", "carry_mismatch", 15.0, 18.0, "stock row1",
            "Unit u08-count-two (Count Two) under rule CONV-006 (operator's id CONV-QF): the stock row1 "
            "carries 18 box, but the values under 'stock' in unit u07-count-one add up to 15 box.",
            "u08-count-two (Count Two) birimi, CONV-006 (operatörün kimliği CONV-QF) kuralı: 'stock "
            "row1' değeri 18 box; ancak u07-count-one birimindeki 'stock' altındaki değerlerin toplamı "
            "15 box.", compared=["u07-count-one"]),
        row("u11-sample-ash", "unit_mismatch", 4.0, 0.004, "total mass",
            "Unit u11-sample-ash (Sample Ash) under rule CONV-009 (operator's id CONV-QI): the total mass "
            "is written as 0.004 kg, in another measure than the g its comparison uses; read in that "
            "measure it is 4.0 g.",
            "u11-sample-ash (Sample Ash) birimi, CONV-009 (operatörün kimliği CONV-QI) kuralı: 'total "
            "mass' değeri 0.004 kg olarak yazılmış; bu, karşılaştırmanın kullandığı g ölçüsünden farklı. "
            "O ölçüyle okunduğunda değeri 4.0 g."),
        row("u13-probe-one", "unit_mismatch", 30.0, 0.03, "reading",
            "Unit u13-probe-one (Probe One) under rule CONV-010 (operator's id CONV-QJ): the reading is "
            "written as 0.03 g, in another measure than the mg its comparison uses; read in that "
            "measure it is 30.0 mg.",
            "u13-probe-one (Probe One) birimi, CONV-010 (operatörün kimliği CONV-QJ) kuralı: 'reading' "
            "değeri 0.03 g olarak yazılmış; bu, karşılaştırmanın kullandığı mg ölçüsünden farklı. O "
            "ölçüyle okunduğunda değeri 30.0 mg."),
    ], "refusals": sorted((u, rel, why) for u, _r, rel, why in PLANNER["refusals"]),
        "refusal_count": len(PLANNER["refusals"])}


def compared_passage_dropped():
    return _patched(paired_review, "attach_compared_unit_refs", lambda checks, doc: checks)


def refusals_not_passed():
    real = paired_review.plan_calls

    def without_sink(*a, **k):
        k.pop("relation_refusal_sink", None)
        return real(*a, **k)
    return _patched(paired_review, "plan_calls", without_sink)


def turkish_rows_missing():
    real = localization.catalog

    def without_rows():
        c = dict(real())
        c["_messages"] = [r for r in c.get("_messages", [])
                          if " carries " not in r["pattern"].replace("\\", "")
                          and "in another measure" not in r["pattern"].replace("\\", "")
                          and " gives " not in r["pattern"].replace("\\", "")]
        return c
    return _patched(localization, "catalog", without_rows)


def sentence_falls_back():
    """The relation's own sentence gone: the generic fallback renders the record."""
    real = paired_review.relation_clause

    def generic(item):
        if item.get("relation") in NEW:
            return "the computed figure is %s, compared with %s (relation %s)" % (
                item.get("value_a"), item.get("value_b"), item.get("relation"))
        return real(item)
    return _patched(paired_review, "relation_clause", generic)


# ---- 3. a multi-round case -------------------------------------------------------------

def _case_documents(before_in):
    first = DOC
    second = DOC.replace("| Opening | 10 |\n| In | 5 |\n\nClosing stock: 15 box",
                         "| Opening | 10 |\n| In | %d |\n\nClosing stock: %d box" % (before_in, 10 + before_in))
    return [{"id": "ledger_r1", "text": first}, {"id": "ledger_r2", "text": second}]


def observe_rounds():
    import multi_round_rounds as mr
    earlier = {}
    out = []
    for rid, doc in zip(("r1", "r2"), _case_documents(8)):
        rows, found, _n = mr.review_document(doc, RULES, earlier, round_id=rid)
        status = {r["unit_id"]: r["status"] for r in rows}
        carry = sorted((f["value_a"], f["value_b"]) for f in found
                       if f.get("relation") == "carry_mismatch" and f.get("unit_id") == "u08-count-two")
        out.append((rid, status.get("u07-count-one"), status.get("u08-count-two"), carry))
    return out


# Round 2 changes only Count One (its In row 5 to 8, its closing 15 to 18). Count Two's own
# text is byte-identical, and it now opens at what Count One adds up to: recomputed, the
# carry mismatch of round 1 is gone in round 2.
ROUNDS = [("r1", "computed", "computed", [(15.0, 18.0)]),
          ("r2", "computed", "computed", [])]


# D-198 (fix 1): only the copied source changes. In both rounds Entry Delta states its line
# sum in another measure (box) than the batch column (zed), so the copy is refused
# (copy_measure_differs) and, before the fix, the source was signed in neither round; in
# round 2 its figure moves from 30 to 31. Batch Three's own text, the document's labels and
# its units of measure are the same in both rounds, so only the neighbours input can
# recompute it: a changed neighbour is recomputed, never reused, whatever its copy's outcome.
SOURCE_ROUND = ["## Entry Delta", "", "Lots: 3 box", "{line}",
                "## Batch Three", "", "| Entry | Line sum (zed) |", "|---|---|", "| Entry Delta | 31 |", ""]


def observe_source_round():
    import multi_round_rounds as mr
    earlier, out = {}, []
    rules = [r for r in RULES if r["id"] == "CONV-004"]
    for rid, line in (("r1", "Line sum: 30 box\n"), ("r2", "Line sum: 31 box\n")):
        text = "\n".join(SOURCE_ROUND).replace("{line}", line) + "\n"
        rows, found, _n = mr.review_document({"id": "ledger_s" + rid, "text": text}, rules, earlier,
                                             round_id=rid, refusals=[])
        status = {r["unit_id"]: r["status"] for r in rows}
        copies = sorted((f["value_a"], f["value_b"]) for f in found if f.get("relation") == "copy_mismatch")
        out.append((rid, status.get("u02-batch-three"), copies))
    return out


SOURCE_ROUNDS = [("r1", "computed", []), ("r2", "computed", [])]


def refused_source_not_signed():
    """D-198 neutralised: only the sources of copies computed this round are signed, as before."""
    def computed_only(unit, rules, units_by_id, known_units=None):
        out = set()
        for rule in rules or ():
            text = rule.get("rule", "") if isinstance(rule, dict) else ""
            before = relation_checks.carry_sources(unit, text, units_by_id)
            if before:
                out.add(before)
            for check in relation_checks.copy_checks(unit, text, units_by_id):
                out.add(check["compared_unit_id"])
        return sorted(out)
    return _patched(relation_checks, "cross_unit_sources", computed_only)


def neighbours_not_signed():
    import multi_round_rounds as mr
    return _patched(mr, "SIGNATURE_INPUTS", tuple(n for n in mr.SIGNATURE_INPUTS if n != "neighbours"))


# ---- 4. the governed record ------------------------------------------------------------

def _constitution():
    return json.loads((ROOT / "config" / "constitution.json").read_text(encoding="utf-8"))


def observe_record():
    """The record as it stood when INFRA-045 was the newest amendment: a later append does
    not change whether this one was the verified next id."""
    current = _constitution()
    ids = [a.get("id") for a in current["amendments"]]
    if "INFRA-045" in ids:
        current["amendments"] = current["amendments"][:ids.index("INFRA-045") + 1]
    before = copy.deepcopy(current)
    before["amendments"] = [a for a in before["amendments"] if a.get("id") != "INFRA-045"]
    delta = next((a for a in current["amendments"] if a.get("id") == "INFRA-045"), {})
    ids = [a.get("id") for a in current["amendments"]]
    contract = json.loads((ROOT / "config" / "agent_contracts.json").read_text(encoding="utf-8"))
    rel = list(contract["finding_record"]["relations"])
    fallback = list(finding_record._FALLBACK["relations"])
    return {"append": constitution_guard.verify_amendment_append(before, current),
            "follows": ids.index("INFRA-045") == ids.index("INFRA-044") + 1 if "INFRA-045" in ids else False,
            "approval": (delta.get("operator_approved"), (delta.get("approval") or {}).get("date"),
                         (delta.get("approval") or {}).get("words")),
            "names_all": all(r in json.dumps(delta) for r in NEW),
            "tail": rel[:rel.index(NEW[-1]) + 1][-4:] if NEW[-1] in rel else [],
            "fallback_tail": fallback[:fallback.index(NEW[-1]) + 1][-4:] if NEW[-1] in fallback else [],
            "declared": all(r in finding_record.relations() for r in NEW)}


RECORD = {"append": {"ok": True, "errors": []}, "follows": True,
          "approval": (True, "2026-10-31", "Ben simdiden onayliyorum yapalim."),
          "names_all": True, "tail": list(NEW), "fallback_tail": list(NEW), "declared": True}


def approval_marker_removed():
    real = _constitution

    def unapproved():
        data = real()
        for a in data["amendments"]:
            if a.get("id") == "INFRA-045":
                a["operator_approved"] = False
        return data
    return _patched(sys.modules[__name__], "_constitution", unapproved)


class RelationChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        result = prove_effect(name=name, validate=lambda: bool(DOC and RULES), observe=observe,
                              check=lambda: ("PASS" if observe() == expected() else "FAIL", name),
                              neutralise=neutralise)
        RelationChecks.evidence.append(result)

    # 1. the planner
    def test_a_rate_the_rule_states_is_computed(self):
        """Neutralised: no rate is computed."""
        self.prove("rate", observe_planner, lambda: PLANNER, no_rate)

    def test_a_tied_third_figure_is_refused(self):
        """Neutralised: the tie is broken by taking the first."""
        self.prove("rate_tie_refused", observe_planner, lambda: PLANNER, tie_broken)

    def test_a_figure_in_another_measure_is_converted(self):
        """Neutralised: no measure converts."""
        self.prove("unit_converted", observe_planner, lambda: PLANNER, nothing_converts)

    def test_a_figure_in_another_measure_than_its_band_is_found(self):
        """Neutralised: the band's measure is not compared."""
        self.prove("band_measure", observe_planner, lambda: PLANNER, no_band_measure)

    def test_a_row_that_does_not_carry_its_source_is_found(self):
        """Neutralised: no copy is computed."""
        self.prove("copy", observe_planner, lambda: PLANNER, no_copy)

    def test_a_row_naming_two_units_is_refused(self):
        """Neutralised: the first unit of that heading is taken."""
        self.prove("copy_ambiguity_refused", observe_planner, lambda: PLANNER, first_source_taken)

    def test_a_first_row_that_does_not_carry_the_unit_before_is_found(self):
        """Neutralised: no carry is computed."""
        self.prove("carry", observe_planner, lambda: PLANNER, no_carry)

    def test_a_unit_before_that_does_not_add_up_is_refused(self):
        """Neutralised: the unit before is assumed to add up."""
        self.prove("carry_source_refused", observe_planner, lambda: PLANNER, source_assumed_to_add_up)

    def test_only_what_a_rule_names_is_compared(self):
        """Neutralised: every label counts as named by every rule."""
        self.prove("rule_gate", observe_planner, lambda: PLANNER, rule_words_ignored)

    # D-198 (the fresh review's fixes and open item 76)
    def test_a_unit_mismatch_belongs_to_the_rule_declaring_the_measure(self):
        """Neutralised: the unit mismatch takes the first paired rule (open item 76)."""
        self.prove("unit_rule_declared", observe_planner, lambda: PLANNER, unit_by_sum_rule)

    def test_figures_that_fit_another_reading_are_refused(self):
        """Neutralised: the other plain reading is not looked at (fix 2)."""
        self.prove("rate_reading_ambiguous", observe_planner, lambda: PLANNER, other_reading_ignored)

    def test_a_share_of_a_zero_whole_is_refused(self):
        """Neutralised: the share is minted with no computed figure (fix 5)."""
        self.prove("rate_zero_whole", observe_planner, lambda: PLANNER, zero_whole_computed)

    def test_an_unconvertible_band_measure_is_refused_on_the_record(self):
        """Neutralised: the band path skips it silently (fix 8)."""
        self.prove("band_measure_refused", observe_planner, lambda: PLANNER, band_refusal_dropped)

    def test_an_agreeing_rate_settles_only_a_rule_that_asks_nothing_else(self):
        """Neutralised: any produced check settles its rule (fix 6)."""
        self.prove("settling", observe_settling, lambda: SETTLING, every_producer_settles)

    def test_only_declared_bases_take_a_prefix(self):
        """Neutralised: tokens read as prefixes by their letters (fix 7)."""
        self.prove("declared_bases", observe_conversions, lambda: CONVERSIONS, letters_read_as_prefixes)

    def test_a_unit_whose_copied_source_changed_is_recomputed(self):
        """Neutralised: a refused copy's source is not signed (fix 1)."""
        self.prove("copy_source_signed", observe_source_round, lambda: SOURCE_ROUNDS,
                   refused_source_not_signed)

    # 2. the paired review
    def test_a_copy_or_carry_cites_the_other_units_passage_as_compared(self):
        """Neutralised: the compared passage is not attached."""
        self.prove("compared_passage", observe_review, expected_review, compared_passage_dropped)

    def test_the_refusals_reach_the_pairing_map(self):
        """Neutralised: the paired review passes no refusal sink."""
        self.prove("refusals_recorded", observe_review, expected_review, refusals_not_passed)

    def test_each_record_renders_its_own_sentence(self):
        """Neutralised: the relation's sentence falls back to the generic one."""
        self.prove("sentence", observe_review, expected_review, sentence_falls_back)

    def test_each_sentence_has_its_turkish_row(self):
        """Neutralised: the catalog's new rows removed."""
        self.prove("turkish_rows", observe_review, expected_review, turkish_rows_missing)

    # 3. multi-round
    def test_a_unit_whose_neighbour_changed_is_recomputed(self):
        """Neutralised: the neighbours input left out of the signature."""
        self.prove("neighbours_signed", observe_rounds, lambda: ROUNDS, neighbours_not_signed)

    # 4. the governed record
    def test_the_amendment_is_the_verified_next_id(self):
        """Neutralised: INFRA-045 without its approval marker."""
        self.prove("infra_045", observe_record, lambda: RECORD, approval_marker_removed)


def check():
    RelationChecks.evidence = []
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RelationChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:200]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: a rate a rule states, a stated "
                    "total and a reading in another measure than their column and band (converted by a "
                    "declared prefix), a table row that does not carry the unit it names, and a first "
                    "row that does not carry the unit before, each computed only for a rule naming "
                    "them; a tied third figure, a measure that does not convert, a row naming two units "
                    "and a unit before that does not add up refused into the pairing map, never guessed; "
                    "the paired review posting each as Python's record, a copy and a carry citing the "
                    "other unit's passage as compared, an amendment with the relation's own sentence and "
                    "its row for the second output language (tr); a multi-round unit whose neighbour changed recomputed; INFRA-045 "
                    "the verified next id, operator-approved, its four relations appended; and (D-198) a "
                    "unit mismatch attributed to the rule declaring its figure or refused, figures that "
                    "fit another reading and a zero whole refused, an unconvertible band measure "
                    "refused, an agreeing rate settling only a rule that asks nothing else, prefixes "
                    "only before declared bases, and a refused copy's changed source recomputed"
                    % result.testsRun)


if __name__ == "__main__":
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == "PASS" else 1)
