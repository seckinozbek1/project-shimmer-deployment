"""Gate check 323: the honesty items that must be settled before preregistration version 3
freezes (loop Annex D D-S23 item 5, docs/loop/stages/AFTER_V1_PLAN.md step 4).

Open item 22: the pairing map's band record and the finding it describes agree below the
band. For every comparison, in the band's measure or another, on the document's own units,
the record's low-side verdict is the one the finding path reached: a comparison below the
band the record calls conditional carries `conditional_on` on its finding, and one it calls
firm carries none. The verdict says nothing about a comparison above or inside the band.
Run on the shape of the input format's own unit-price example in neutral words, through the
real readers, no model.

Open item 16, defects 1 and 3: a date window's field label keeps its own line's word order
(it joined a set, so the order changed between processes and an exact-text comparison could
fail on a correct finding); and a file opening with a UTF-8 byte-order mark keeps its first
heading, so a conventions file, text or JSON, does not yield zero rules, there or at intake.

Open item 25: an amendment states the severity its rule declares, which a reader sees in
the findings file, the docx and the server; a rule that declares none keeps `required`.

Open item 80: both summaries count, and the document summary lists, the model findings the
master lists, proven with VERIFIER, FACT_CHECKER, LEGAL_ANALYST and STYLE_GUARDIAN through the
real phase 6; a model's untyped item is in neither. A declared field of the wrong shape, each
rule id alias included, is removed by the one decoder and named in `unreadable_fields`, so the
listed cases stop nothing through the real phase 6 and phase 7's reader. A shape is proven only
where listed in MALFORMED_IDS.

Each proof is neutralise, fail, restore, pass (effect_proof).

    py -3.12 -X utf8 scripts/honesty_items_checks.py
"""
from __future__ import annotations

import sys
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_wrapper import decode_items
import convention_parser as cp
import audit_synthesizer
import finding_record
import honest_output_checks as hoc
import intake_wizard
import judged_refusal_checks as jrc
import paired_review as pr
import pairing_map as pm
import reference_tables as rt
import relation_checks
import text_extract
import uncomputable_judgment_checks as ujc
import verifiability_gate

# PRE-AUTHORED, NOT MODEL OUTPUT. The stated rate and the rate worked out from the sum and
# the count are both below the band; the rule names the stated rate only.
UNIT = "## Part P-100\n\nPart group: Alpha\nCount: 4 box\nGauge rate: 5 zed/box\nPart sum: 20 zed\n"
TABLE = "| Part group | Rate band (zed/box) |\n|---|---|\n| Alpha | 8 to 15 |\n| Beta | 3 to 6 |\n"
RULE = "The gauge rate must lie within the rate band for the part group."


def observe_band_record():
    """Each comparison below the band, as the record and as the finding state it."""
    known = rt.document_unit_tokens(UNIT)
    tables = rt.parse_tables(TABLE, ref_id="REF-0002", document_id="ref", known_units=known)
    labels = pm.unit_fields(UNIT)
    records = rt.band_conditions_for_unit(tables, UNIT, [{"id": "CONV-001", "rule": RULE}], vocabulary=labels)
    scalars, columns, _ = pr.extract_fields(UNIT, known_units=known)
    checks = pr.compute_checks(scalars, columns, rule_text=RULE, reference_bands=rt.bands_for_unit(tables, UNIT, RULE),
                               vocabulary=labels, unit_labels=labels, unit_text=UNIT)
    below = [c for c in checks if c["relation"] == "below_band"]
    return {"record": sorted((r["compared_fields"] == ["gauge rate"], r["low_side_verdict"]) for r in records),
            "finding": sorted((c.get("stated_field") == "gauge rate", "model" if c.get("conditional_on") else "fire")
                              for c in below)}


def check_band_record():
    o = observe_band_record()
    ok = bool(o["record"]) and o["record"] == o["finding"]
    return ("PASS" if ok else "FAIL", "band record: %s" % ("agrees with the findings" if ok else o))


# A figure in another measure than the band: the finding reads it through
# relation_checks.band_unit_checks, not paired_review._band_comparisons.
OTHER_UNIT = "## Part P-200\n\nPart group: Alpha\nGauge rate: 5 mg\nPart sum: 20 zed\n"
OTHER_TABLE = "| Part group | Rate band (g) |\n|---|---|\n| Alpha | 8 to 15 |\n| Beta | 3 to 6 |\n"


def observe_band_other_measure():
    known = rt.document_unit_tokens(OTHER_UNIT + OTHER_TABLE)
    tables = rt.parse_tables(OTHER_TABLE, ref_id="REF-0002", document_id="ref", known_units=known)
    labels = pm.unit_fields(OTHER_UNIT)
    records = rt.band_conditions_for_unit(tables, OTHER_UNIT, [{"id": "CONV-001", "rule": RULE}],
                                          vocabulary=labels, known_units=known)
    scalars, columns, _ = pr.extract_fields(OTHER_UNIT, known_units=known)
    checks = pr.compute_checks(scalars, columns, rule_text=RULE, reference_bands=rt.bands_for_unit(tables, OTHER_UNIT, RULE),
                               vocabulary=labels, unit_labels=labels, unit_text=OTHER_UNIT)
    return {"record": [r["compared_fields"] for r in records],
            "finding": [[c.get("stated_field")] for c in checks if c["relation"] == "below_band"]}


def check_band_other_measure():
    o = observe_band_other_measure()
    ok = bool(o["finding"]) and o["record"] == o["finding"]
    return ("PASS" if ok else "FAIL", "band record, another measure: %s" % ("names the compared figure" if ok else o))


# The document writes the two-word unit twice, the unit once, so the unit's own tokens read
# its figure in another measure than the document's tokens do, and the band's measure is
# the shorter one: the finding path, on the document's tokens, compares nothing.
DOC_TEXT = "Used 3 wide box here and 4 wide box there.\n"
KNOWN_UNIT = "## Part P-300\n\nPart group: Alpha\nGauge rate: 5 wide box\n"
KNOWN_TABLE = "| Part group | Rate band (wide) |\n|---|---|\n| Alpha | 8 to 15 |\n| Beta | 3 to 6 |\n"
_EXTRACT = pr.extract_fields


def observe_band_known_units():
    known = rt.document_unit_tokens(DOC_TEXT + KNOWN_UNIT)
    tables = rt.parse_tables(KNOWN_TABLE, ref_id="REF-0002", document_id="ref", known_units=known)
    labels = pm.unit_fields(KNOWN_UNIT)
    records = rt.band_conditions_for_unit(tables, KNOWN_UNIT, [{"id": "CONV-001", "rule": RULE}],
                                          vocabulary=labels, known_units=known)
    scalars, columns, _ = _EXTRACT(KNOWN_UNIT, known_units=known)
    bands = rt.bands_for_unit(tables, KNOWN_UNIT, RULE)
    checks = pr.compute_checks(scalars, columns, rule_text=RULE, reference_bands=bands,
                               vocabulary=labels, unit_labels=labels, unit_text=KNOWN_UNIT)
    return {"bands": len(bands), "record": [r["compared_fields"] for r in records],
            "finding": [c.get("stated_field") for c in checks if c["relation"] == "below_band"]}


def check_band_known_units():
    o = observe_band_known_units()
    ok = o["bands"] == 1 and o["record"] == [[]] and o["finding"] == []
    return ("PASS" if ok else "FAIL", "band record, the document's units: %s" % ("as the finding reads them" if ok else o))


# Words whose document order is not their alphabetical order, so a sorted label fails too,
# and a heading above them writes the same words the other way round.
DATE_UNIT = ("## Beta yarrow close, start mid alpha zeta\n\nStart mid alpha zeta: see below\n"
             "Zeta alpha mid start: 2026-01-01\nYarrow beta close: 2026-03-01\n")
DATE_RULE = "The zeta alpha mid start and the yarrow beta close must be under a year apart."
BOM_RULES = "\ufeff## CONV-B01 Entries [required]\n\nEvery entry must state its reading.\n"
BOM_TEXT = "\ufeff## Entry\n\nReading: 3 units\n"
BOM_JSON = "\ufeff" + json.dumps({"conventions": [{"id": "CONV-B02", "rule": "Every entry must state its reading."}]})


def observe_date_label():
    pair = pr.date_pair_for_rule(DATE_UNIT, DATE_RULE)
    return [pair[1], pair[3]] if pair else None


def check_date_label():
    o = observe_date_label()
    ok = o == ["zeta alpha mid start", "yarrow beta close"]
    return ("PASS" if ok else "FAIL", "date label: %s" % ("in the document's order" if ok else o))


def observe_bom():
    with tempfile.TemporaryDirectory(prefix="shimmer_bom_") as td:
        rules = Path(td) / "rules.md"
        rules.write_text(BOM_RULES, encoding="utf-8", newline="")
        document = Path(td) / "doc.md"
        document.write_text(BOM_TEXT, encoding="utf-8", newline="")
        parsed = cp._parse_text(rules, [0])
        rules_json = Path(td) / "rules.json"
        rules_json.write_text(BOM_JSON, encoding="utf-8", newline="")
        loose = Path(td) / "house_style.md"
        loose.write_text(BOM_RULES, encoding="utf-8", newline="")
        text = text_extract.extract_text(document)
        return {"rules": len(parsed), "categories": [r.category for r in parsed], "clean_text": text.startswith("## Entry"),
                "json_rules": len(cp._parse_json(rules_json, [0])),
                "wizard_sees_rules": intake_wizard._carries_rule_headings(loose),
                "wizard_counts": intake_wizard.summarize_conventions([loose]).get("rules")}


def check_bom():
    o = observe_bom()
    ok = (o["rules"] == 1 and o["clean_text"] and o["categories"] == ["conv-b01"] and o["json_rules"] == 1
          and o["wizard_sees_rules"] is True and o["wizard_counts"] == 1)
    return ("PASS" if ok else "FAIL", "byte-order mark: %s" % ("the first heading is kept" if ok else o))


def observe_summary_model_count():
    """Open item 80: a model finding from an agent outside the convention review, through
    the real phase 6, in the document's summary and in the master."""
    def item(agent):
        return dict(hoc.model_finding(), ref=agent.lower() + "_fixture")

    untyped = {"rationale": "An item with no relation.", "suggested_edit": "Reword.", "ref": "untyped_fixture",
               "kind": "finding", "confidence": "CONFIDENT"}
    no_verdict = {k: v for k, v in dict(hoc.model_finding(), ref="no_verdict_fixture").items() if k != "record_verdict"}
    with tempfile.TemporaryDirectory(prefix="shimmer_summary_count_") as td:
        run = hoc.mocked_run(td, audit_items={"VERIFIER": [item("VERIFIER")], "FACT_CHECKER": [item("FACT_CHECKER")]},
                             production_items=[item("LEGAL_ANALYST")], style_extras=[untyped, no_verdict])
        summary = Path(run["files"]["document_summary.md"]).read_text(encoding="utf-8")
        grounding = Path(run["files"]["grounding_summary.md"]).read_text(encoding="utf-8")
        master = json.loads(Path(run["files"]["review_data.json"]).read_text(encoding="utf-8"))
    said = re.search(r"Written by a model \((.*?)\), not checked by Python and not promoted, listed apart under each category: (\d+)", summary)
    ground = re.search(r"Items written by a model \((.*?)\), not checked by Python and not promoted: (\d+)", grounding)
    unit = hoc.model_finding()["unit_id"]
    return {"agents": said.group(1) if said else None, "summary": int(said.group(2)) if said else None,
            "grounding": int(ground.group(2)) if ground else None, "listed": len(hoc._model_lines(summary, unit)),
            "empty_lines": sum(1 for ln in summary.splitlines() if ln.startswith("-  (")),
            "master": len(master.get("model_findings_not_promoted") or [])}


def check_summary_model_count():
    o = observe_summary_model_count()
    ok = (o["summary"] == o["grounding"] == o["listed"] == o["master"] == 4 and not o["empty_lines"]
          and all(name in (o["agents"] or "") for name in ("VERIFIER", "FACT_CHECKER", "LEGAL_ANALYST")))
    return ("PASS" if ok else "FAIL", "summary count: %s" % ("the master's" if ok else o))


MALFORMED_IDS = ({"rule_id": ["CONV-001"]}, {"procedure_id": ["CONV-001"]}, {"conv_id": ["CONV-001"]},
                 {"convention_ref": ["CONV-001"]}, {"unit_id": ["u1"]}, {"compared_unit_id": ["u1"]},
                 {"source_refs": 5}, {"ref_ids": 5}, {"item_id": ["a"]}, {"verdict": ["VIOLATION"]},
                 {"recommendation": ["Fix."]}, {"source_url": ["x"]})


def observe_malformed_ids():
    """A model can write any JSON in an id field; through the real phase 6 none stops the run."""
    items = [dict(hoc.model_finding(), ref="malformed_%d" % n, **fields) for n, fields in enumerate(MALFORMED_IDS)]
    with tempfile.TemporaryDirectory(prefix="shimmer_model_ids_") as td:
        try:
            run = hoc.mocked_run(td, style_extras=items)
        except TypeError as e:
            return {"raised": str(e)}
        master = json.loads(Path(run["files"]["review_data.json"]).read_text(encoding="utf-8"))
    kept = master.get("model_findings_not_promoted") or []
    decoded = decode_items({"agent": "PRACTICE_AUDITOR", "doc_id": "d", "items": [dict(i, verdict="VIOLATION") for i in items]})
    try:
        hosts = audit_synthesizer._count_disputed_by_source([dict(f, verdict="DISPUTED") for f in decoded])
    except (TypeError, AttributeError) as e:
        return {"raised": str(e)}
    return {"master": len(kept), "named": sorted(k for f in kept for k in f.get("unreadable_fields") or []),
            "hosts": bool(hosts)}


def check_malformed_ids():
    o = observe_malformed_ids()
    ok = o.get("master") == 1 + len(MALFORMED_IDS) and o.get("named") == sorted(k for f in MALFORMED_IDS for k in f)
    return ("PASS" if ok else "FAIL", "malformed ids: %s" % ("kept, named, nothing stopped" if ok else o))


def observe_supersession():
    """An `item_id` a model wrote in another shape still joins its revisions: the gate's
    downgrade supersedes the ungrounded item, leaving one current item."""
    out = {}
    for name, value in (("string", "FC:1"), ("number", 7), ("list", ["a"])):
        item = {"kind": "finding", "ref": "x", "confidence": "CONFIDENT", "verdict": "CONFIRMED",
                "item_id": value, "revision": 1, "ts": "2026-01-01T00:00:00Z"}
        results = [{"agent": "FACT_CHECKER", "ok": True, "parsed": {"agent": "FACT_CHECKER", "doc_id": "d", "items": [item]}}]
        verifiability_gate.apply_verifiability_gate(results)
        out[name] = [i.get("confidence") for i in decode_items(results[0]["parsed"])]
    return out


def check_supersession():
    o = observe_supersession()
    ok = all(v == ["UNCERTAIN"] for v in o.values())
    return ("PASS" if ok else "FAIL", "supersession: %s" % ("one current item" if ok else o))


def _judged_items(quote):
    claim = dict(jrc._claim(quote), rule_id=["CONV-001"])
    figures = {"kind": "finding", "record_verdict": "irregular", "relation": "sum_mismatch", "quote": quote,
               "value_a": [5, 7], "value_b": 12, "explanation": "The parts do not add up."}
    return [claim, figures, dict(figures, value_a=12, value_b=[5, 7])]


def _judged_absence_reply(payload, call_id):
    items = _judged_items(jrc.ABSENCE_KEPT_QUOTE) if jrc.ABSENCE_UNIT in str(payload.get("unit_id") or "") else []
    return {"ok": True, "backend": "local_auditor", "model": "fixture-auditor", "call_id": call_id, "raw_text": "",
            "item_count": len(items), "parsed": {"agent": "PRACTICE_AUDITOR", "items": items}}


def _judged_uncomputable_reply(payload, call_id, kwargs):
    if payload.get("rule_id") != ujc.RULE_ID:
        return None
    items = _judged_items(ujc.KEPT_QUOTE)
    return {"ok": True, "backend": ujc.BACKEND, "model": ujc.MODEL, "call_id": call_id, "raw_text": "",
            "item_count": len(items), "parsed": {"agent": "PRACTICE_AUDITOR", "items": items}}


def observe_judged_shapes():
    """A judged reply's lists, through the real phase 5.5 on both judged paths."""
    out = {}
    with tempfile.TemporaryDirectory(prefix="shimmer_judged_shapes_") as td:
        for name, kwargs in (("absence", dict(rules=jrc.ABSENCE_RULES, absence_reply=_judged_absence_reply)),
                             ("uncomputable", dict(text=ujc.TEXT, rules=ujc.RULES, other_reply=_judged_uncomputable_reply))):
            folder = Path(td) / name
            folder.mkdir()
            try:
                hoc.mocked_run(folder, style_guardian=False, **kwargs)
                out[name] = "ran"
            except TypeError as e:
                out[name] = "raised: %s" % e
    return out


def check_judged_shapes():
    o = observe_judged_shapes()
    ok = o == {"absence": "ran", "uncomputable": "ran"}
    return ("PASS" if ok else "FAIL", "judged shapes: %s" % ("nothing stopped" if ok else o))


SEVERITY_FINDING = {"kind": "finding", "record_verdict": "irregular", "relation": "sum_mismatch", "unit_id": "u01-x",
                    "rule_id": "CONV-R01", "value_a": 40, "value_b": 41, "unit_a": "units", "unit_b": "units",
                    "source_refs": ["REF-0001"]}


def observe_severity():
    out = {}
    for name, rule in (("recommended", {"severity": "recommended"}), ("required", {"severity": "required"}),
                       ("undeclared", {})):
        built, _ = pr.ensure_amendments_for_findings([], [dict(SEVERITY_FINDING)], rules_by_id={"CONV-R01": rule})
        out[name] = [a.get("severity") for a in built]
    return out


def check_severity():
    o = observe_severity()
    ok = o == {"recommended": ["recommended"], "required": ["required"], "undeclared": ["required"]}
    return ("PASS" if ok else "FAIL", "severity: %s" % ("the rule's own" if ok else o))


def _no_labels(real):
    """band_unit_checks as it stands, but with no comparison labels: the record's reader
    then sees none, while the finding still fires, since its caller reads the rest."""
    def wrapped(*args, **kwargs):
        checks = real(*args, **kwargs)
        return [{k: v for k, v in c.items() if k != "_labels"} for c in checks]
    return wrapped


class HonestyItemsChecks(unittest.TestCase):
    def test_an_amendment_states_its_rules_severity(self):
        from effect_proof import prove_effect
        prove_effect(name="severity", validate=lambda: finding_record.is_finding(SEVERITY_FINDING),
                     observe=observe_severity, check=check_severity,
                     neutralise=lambda: patch.object(pr, "severity_of_rule", lambda rule_id, rules: ""))

    def test_a_date_label_keeps_the_documents_order(self):
        from effect_proof import prove_effect
        prove_effect(name="date_label", validate=lambda: pr.date_pair_for_rule("", "") is None,
                     observe=observe_date_label, check=check_date_label,
                     neutralise=lambda: patch.object(pr, "_in_document_order", lambda words, text: sorted(words)))

    def test_a_date_label_is_read_from_its_own_line(self):
        from effect_proof import prove_effect
        real = pr._label_lines_with_dates
        prove_effect(name="date_label_line", validate=lambda: len(real(DATE_UNIT)[0][0]) == 3,
                     observe=observe_date_label, check=check_date_label,
                     neutralise=lambda: patch.object(pr, "_label_lines_with_dates", lambda text: [
                         (routes[:2], dates, has_time) for routes, dates, has_time in real(text)]))

    def test_a_byte_order_mark_drops_nothing(self):
        from effect_proof import prove_effect
        prove_effect(name="byte_order_mark", validate=lambda: BOM_RULES.startswith("\ufeff"),
                     observe=observe_bom, check=check_bom,
                     neutralise=lambda: patch.object(text_extract, "TEXT_ENCODING", "utf-8"))

    def test_the_band_record_agrees_with_the_finding(self):
        from effect_proof import prove_effect
        prove_effect(name="band_record", validate=lambda: rt.low_side_condition("", None, (), ()) == ((), "fire"),
                     observe=observe_band_record, check=check_band_record,
                     neutralise=lambda: patch.object(rt, "_compared_labels", lambda scalars, columns, band: [()]))

    def test_the_band_record_names_a_figure_in_another_measure(self):
        from effect_proof import prove_effect
        prove_effect(name="band_other_measure", validate=lambda: relation_checks.converted(5, "mg", "g") == 0.005,
                     observe=observe_band_other_measure, check=check_band_other_measure,
                     neutralise=lambda: patch.object(relation_checks, "band_unit_checks",
                                                     _no_labels(relation_checks.band_unit_checks)))

    def test_a_models_malformed_ids_stop_nothing(self):
        from effect_proof import prove_effect
        prove_effect(name="malformed_ids", validate=lambda: finding_record.is_finding(dict(hoc.model_finding(), **MALFORMED_IDS[0])),
                     observe=observe_malformed_ids, check=check_malformed_ids,
                     neutralise=lambda: patch.object(finding_record, "with_readable_ids", lambda item: item))

    def test_a_malformed_item_id_still_joins_its_revisions(self):
        from effect_proof import prove_effect
        prove_effect(name="supersession", validate=lambda: finding_record.with_readable_ids({"item_id": 7})["item_id"] == "7",
                     observe=observe_supersession, check=check_supersession,
                     neutralise=lambda: patch.object(finding_record, "_item_id_text", lambda value: None))

    def test_a_judged_replys_lists_stop_nothing(self):
        from effect_proof import prove_effect
        prove_effect(name="judged_shapes", validate=lambda: finding_record.is_finding(_judged_items("q")[1]),
                     observe=observe_judged_shapes, check=check_judged_shapes,
                     neutralise=lambda: patch.object(pr, "_key_part", lambda value: value))

    def test_a_clean_item_keeps_its_identity(self):
        item = hoc.model_finding()
        self.assertIs(finding_record.with_readable_ids(item), item)

    def test_the_summary_counts_the_masters_model_findings(self):
        import pipeline as pl
        from effect_proof import prove_effect
        prove_effect(name="summary_model_count", validate=lambda: finding_record.is_finding(hoc.model_finding()),
                     observe=observe_summary_model_count, check=check_summary_model_count,
                     neutralise=lambda: patch.object(pl, "SUMMARY_ONLY_FINDING_AGENTS", ()))

    def test_the_band_record_reads_the_documents_units(self):
        from effect_proof import prove_effect
        prove_effect(name="band_known_units", validate=lambda: "wide box" in rt.document_unit_tokens(DOC_TEXT),
                     observe=observe_band_known_units, check=check_band_known_units,
                     neutralise=lambda: patch.object(pr, "extract_fields", lambda text, known_units=None: _EXTRACT(text)))


def run_checks():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HonestyItemsChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:160]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d proofs, all but one plain test neutralise, fail, restore, pass: the band record agrees with the finding below "
                    "the band, in the band's measure or another, on the document's units (open item 22); a date "
                    "label in its own line's order and a byte-order mark that drops nothing in a text, JSON or "
                    "intake read, for a UTF-8 mark (open item 16); an amendment states its rule's severity (open item 25); both "
                    "summaries count and list the master's model findings, and the listed malformed fields stop "
                    "nothing, on the judged paths too, with a malformed item id still joining its revisions (open "
                    "item 80)" % result.testsRun)


if __name__ == "__main__":
    status, detail = run_checks()
    print(status, detail)
    sys.exit(0 if status == "PASS" else 1)
