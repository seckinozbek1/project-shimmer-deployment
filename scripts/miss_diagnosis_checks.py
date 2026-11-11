"""Gate check: the miss diagnosis (tools/miss_diagnosis.py) puts every lost expected finding
in one loss class, from saved artifacts, through the scorer.

Every case EXECUTES the tool on run folders written into temporary folders:

1. curated: twelve run folders and their keys, written here, that reach every loss class
   the tool names (the four of scripts/fn_evidence.py, a suspension, a wrong reason, an
   unverifiable reason, an adapter item excluded or failed) and every sub-cause but the
   named fallback, through every path (ordinary, round comparison, multi-round, adapter
   items); one run arrives as a collected_evidence.tar.gz in a batch session folder beside
   a B1 entry and another as a bare archive; the whole table is compared with the
   expected one. Three more proofs on the same table: a document-level adapter item (gold
   naming no evidence unit) is read over every unit of the pairing map, its WEAKEST unit
   decides, and an uncomputable answer Python refused (`uncomputable_refused`) is named
   apart from one that left nothing;
2. the key is read only through the scorer: every opening of an answer key during the
   diagnosis is traced to the module that opened it, and only tools/score_corpus.py may;
3. the archive is unpacked safely: only evidence/, regular files, no parent or absolute
   path, and a model reply record written with its status and context fields only, never
   its payload or reply text (the adapters' over-context and setup-failure readers need
   those fields, so the record is kept and its text is not);
4. fn_evidence reads a pairing map's `undecided` list, which holds bare rule ids
   (pairing_map.pair_units): before this the classifier read objects only and called an
   undecided pair `absent`;
5. every code site the table names resolves to a line of this checkout;
6. development material: three tests of benchmark/generators (f1, f2, f3, seed 7, into a
   temporary folder) are replayed up to the first model call with the pipeline's own
   functions (convention_parser.parse_conventions, pairing_map.build_pairing_map,
   convention_assignment.assign_conventions, multi_round_rounds.review_document for
   Python's findings; each call Python planned for a model is recorded as made and as
   returning nothing), and the diagnosis must account for every planted entry exactly
   once (caught or one loss) with a code site for every loss;
7. inputs: a session folder's downloaded/evidence/run is found, a path that is neither a
   folder nor an archive and a folder with no run are refused with the reason, two run
   folders under one evidence/ are refused rather than chosen, a pair with no key and a
   pair the scorer refuses are reported as not scored, and an output folder inside the
   repository (outside output/) is refused.

Each is proven by neutralise, fail, restore, pass (scripts/effect_proof.py). No model, no
pipeline run, no provider, no network. Case 6 SKIPs when benchmark/generators/ is absent.
"""
import builtins
import contextlib
import io
import inspect
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "benchmark" / "generators"
TOOL = ROOT / "tools" / "miss_diagnosis.py"
for _path in (str(ROOT / "scripts"), str(ROOT / "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from effect_proof import prove_effect  # noqa: E402
import call_evidence  # noqa: E402
import fn_evidence  # noqa: E402


def _tool():
    import miss_diagnosis
    return miss_diagnosis


def _write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        data = json.dumps(data, indent=1)
    path.write_text(data, encoding="utf-8")
    return path


def _jsonl(path, rows):
    return _write(path, "".join(json.dumps(r) + "\n" for r in rows))


COMPLETED = {"schema_version": 1, "run_id": "fixture", "state": "completed", "started_at": "x",
             "finished_at": "2026-10-31T00:00:00+00:00", "reached_end": True, "exit_code": 0,
             "document_count": 1, "amendment_count": 0, "error_type": None}


# ---- curated fixture --------------------------------------------------------------------

def _unit(uid, paired=(), rejected=(), undecided=()):
    return {"unit_id": uid, "title": uid, "kind": "", "index": 0, "fields_present": [],
            "paired": [{"rule_id": r, "reason": "unit carries every field the rule names: x"} for r in paired],
            "rejected": [{"rule_id": r, "reason": why, "missing_count": 1} for r, why in rejected],
            "undecided": list(undecided)}


def _call(call_id, unit_id, rule_id, agent="PRACTICE_AUDITOR"):
    return call_evidence.extract({"unit_id": unit_id, "rule_id": rule_id, "task": "paired_judging"},
                                 call_id=call_id, run_id="fixture", phase="5.5", doc_id="doc_a",
                                 agent=agent, backend="local_auditor", model="fixture")


def _finding(unit, relation, rule="CONV-001", verdict="irregular", a=None, b=None, label=None):
    item = {"agent": "PRACTICE_AUDITOR", "unit_id": unit, "rule_id": rule, "relation": relation,
            "record_verdict": verdict, "source_refs": ["REF-0001"]}
    if a is not None:
        item.update(value_a=a, value_b=b, field_label=label)
    return item


def curated_run(run):
    """Run A: one document, every pairing state, call evidence, reply outcomes, Python's
    findings, a suspension. Its key is curated_key()."""
    run = Path(run)
    rules = ["CONV-001", "CONV-002", "CONV-003", "CONV-004", "CONV-005"]
    assignment = {"by_rule": {r: {"subjects": ["conformance"], "agents": ["PRACTICE_AUDITOR"],
                                  "consumer_agents": ["PRACTICE_AUDITOR"], "status": "assigned",
                                  "source_rule_id": "CONV-A0%d" % (i + 1)}
                              for i, r in enumerate(rules)},
                  "by_agent": {"PRACTICE_AUDITOR": rules}}
    units = [
        _unit("u01-alpha", paired=["CONV-001"]),                       # caught, reason confirmed
        _unit("u02-beta", paired=["CONV-001"]),                        # exposed, reply failed
        _unit("u03-gamma", rejected=[("CONV-001", "unit lacks total value")]),
        _unit("u04-delta", paired=["CONV-001"]),                       # paired, Python saw nothing
        _unit("u05-epsilon", undecided=["CONV-002"]),                  # undecided (bare id)
        _unit("u06-zeta", paired=["CONV-001"]),                        # located, wrong figures
        _unit("u07-eta", paired=["CONV-003"]),                         # suspended
        _unit("u08-theta", paired=["CONV-001"]),                       # another relation on the unit
        _unit("u09-iota", paired=["CONV-004"]),                        # paired, no consumer
    ]
    pairing = {"doc_a": {"document_id": "doc_a", "unit_count": len(units), "rule_count": 5,
                         "units": units, "calls_made": 1,
                         "judging_calls": [{"call_id": "c02", "agent": "PRACTICE_AUDITOR",
                                            "unit_id": "u02-beta", "rule_id": "CONV-001",
                                            "plan_kind": "uncomputable", "backend": "local_auditor",
                                            "model": "fixture", "notes_kept": 0, "absence_listed": 0,
                                            "absence_refused": 0, "judged_listed": 0, "judged_refused": 0,
                                            "outcome": "reply_failed"}],
                         "not_judged": [{"unit_id": "u09-iota", "rule_id": "CONV-004", "kind": "computed",
                                         "reason": "no agent declares: archival", "consumer_agents": [],
                                         "status": "unassigned"}],
                         "suspended": [{"unit_id": "u07-eta", "rule_id": "CONV-003",
                                        "source_rule_id": "CONV-A03", "detail": "unless held"}]}}
    _write(run / "audit" / "pairing_map.json", pairing)
    _write(run / "audit" / "convention_assignment.json", assignment)
    _write(run / "audit" / "run_completion.json", COMPLETED)
    _jsonl(run / "logs" / "call_evidence.jsonl", [_call("c02", "u02-beta", "CONV-001")])
    _jsonl(run / "audit" / "model_replies" / "outcomes.jsonl",
           [{"call_id": "c02", "outcome": "contract_violation", "source": "fixture", "timestamp": "x"}])
    _write(run / "audit" / "model_replies" / "000001_c02.json", {"reply": {"text": "MODEL REPLY TEXT"}})
    posts = [_finding("u01-alpha", "sum_mismatch", a=10, b=12, label="total"),
             _finding("u06-zeta", "sum_mismatch", a=10, b=13, label="total"),
             _finding("u08-theta", "product_mismatch"),
             _finding("u24-mu", "sum_mismatch", a=10, b=12, label="subtotal"),
             _finding("u25-nu", "product_mismatch")]
    _jsonl(run / "logs" / "agent_bus.jsonl", [{"sender": "fixture", "body": {
        "event": "AGENT_OUTPUT", "backend": "paired", "model": "python",
        "payload": {"agent": "PRACTICE_AUDITOR", "doc_id": "doc_a", "items": posts}}}])
    # an amendment written before amendments carried their typed record: it locates u10
    # under its rule and states no reason
    _write(run / "deliverables" / "doc_a" / "review_data.json", {"amendments": [
        {"finding_unit_id": "u10-kappa", "source_convention_ref": "CONV-A01", "convention_ref": "CONV-001"}]})
    return run


def curated_key():
    def p(unit, rule, relation, claim=None):
        e = {"unit": unit, "rule": rule, "relation": relation, "kind": "k"}
        if claim:
            e["claim"] = dict(claim, relation=relation)
        return e
    total = {"field_label": "total", "value_a": 10, "value_b": 12}
    return {"document": "doc_a.md", "task_given_to_the_pipeline": "review", "twin_of": "",
            "clean": [],
            "planted": [p("u01", "CONV-A01", "sum_mismatch", total),
                        p("u02", "CONV-A01", "sum_mismatch", total),
                        p("u03", "CONV-A01", "sum_mismatch", total),
                        p("u04", "CONV-A01", "sum_mismatch", total),
                        p("u05", "CONV-A02", "sum_mismatch", total),
                        p("u06", "CONV-A01", "sum_mismatch", total),
                        p("u07", "CONV-A03", "sum_mismatch", total),
                        p("u08", "CONV-A01", "sum_mismatch", total),
                        p("u09", "CONV-A04", "sum_mismatch", total),
                        p("u99", "CONV-A01", "sum_mismatch", total),
                        p("u03", "CONV-Z09", "sum_mismatch", total),
                        p("u10", "CONV-A01", "sum_mismatch", total),
                        p("u24", "CONV-A01", "sum_mismatch", total),
                        # no relation on the entry, so any relation locates it; its claim's
                        # relation is then the reason checked
                        {"unit": "u25", "rule": "CONV-A01", "relation": "", "kind": "k",
                         "claim": dict(total, relation="sum_mismatch")}]}


def _assignment(sources):
    return {"by_rule": {rid: {"subjects": ["conformance"], "agents": ["PRACTICE_AUDITOR"],
                              "consumer_agents": ["PRACTICE_AUDITOR"], "status": "assigned",
                              "source_rule_id": src} for rid, src in sources.items()},
            "by_agent": {"PRACTICE_AUDITOR": sorted(sources)}}


def _judging(call_id, unit, plan_kind, outcome, **counts):
    row = {"call_id": call_id, "agent": "PRACTICE_AUDITOR", "unit_id": unit, "rule_id": "CONV-001",
           "plan_kind": plan_kind, "backend": "local_auditor", "model": "fixture", "notes_kept": 0,
           "absence_listed": 0, "absence_refused": 0, "judged_listed": 0, "judged_refused": 0,
           "outcome": outcome}
    row.update(counts)
    return row


def _bus(run, items, backend="paired", model="python", doc_id="doc"):
    _jsonl(run / "logs" / "agent_bus.jsonl", [{"sender": "fixture", "body": {
        "event": "AGENT_OUTPUT", "backend": backend, "model": model,
        "payload": {"agent": "PRACTICE_AUDITOR", "doc_id": doc_id, "items": items}}}] if items else [])


def _plain_key(document, planted, **extra):
    return dict({"document": document, "task_given_to_the_pipeline": "review", "twin_of": "",
                 "clean": [], "planted": planted}, **extra)


def _p(unit, rule, relation="sum_mismatch"):
    return {"unit": unit, "rule": rule, "relation": relation, "kind": "k"}


def branch_runs(root):
    """Runs C to H and M, one per remaining branch of the tool's sub-causes and paths;
    returns the --pairs list (run, key, label)."""
    root = Path(root)
    pairs = []

    # C: every remaining fn_evidence pair state and reply outcome, one document
    c = root / "run_c"
    units = [_unit("u11-a", paired=["CONV-001"]), _unit("u12-b", paired=["CONV-001"]),
             _unit("u13-c"), _unit("u14-d", paired=["CONV-001"]), _unit("u15-e", paired=["CONV-001"]),
             _unit("u16-f", paired=["CONV-001"]), _unit("u17-g", paired=["CONV-001"]),
             _unit("u18-h", rejected=[("CONV-001", "unit lacks the declared scope field class")]),
             _unit("u19-i", rejected=[("CONV-001", "unit's class does not carry the value the rule's "
                                                   "scope declares")]),
             _unit("u20-j"), _unit("u21-k"), _unit("u22-l"), _unit("u23-m", paired=["CONV-001"]),
             _unit("u26-n", paired=["CONV-001"]), _unit("u27-o", paired=["CONV-001"])]
    _write(c / "audit" / "pairing_map.json", {"doc_c": {
        "document_id": "doc_c", "units": units,
        "judging_calls": [_judging("c11", "u11-a", "absence_judged", "judged_absence", absence_refused=1),
                          _judging("c12", "u12-b", "computed", "no_finding_to_attach"),
                          _judging("c16", "u16-f", "computed", "no_note_returned"),
                          _judging("c23", "u23-m", "uncomputable", "judged_uncomputable"),
                          # u26: one call kept nothing and refused nothing; another refused an
                          # answer and kept one. No call both kept nothing and refused.
                          _judging("c26a", "u26-n", "uncomputable", "judged_uncomputable"),
                          _judging("c26b", "u26-n", "uncomputable", "judged_uncomputable",
                                   judged_listed=1, judged_refused=1),
                          # u27: a call that kept nothing and refused one answer, whose refusal
                          # is recorded only under another rule and on another unit
                          _judging("c27", "u27-o", "uncomputable", "judged_uncomputable",
                                   judged_refused=1)],
        "uncomputable_refused": [
            {"unit_id": "u26-n", "rule_id": "CONV-001", "relation": "missing_field",
             "reason": "quote not in the unit"},
            {"unit_id": "u27-o", "rule_id": "CONV-009", "relation": "missing_field",
             "reason": "another rule's refusal"}],
        "absence": [{"unit_id": "u15-e", "rule_id": "CONV-001", "field": "x", "path": "computed"}]}})
    _write(c / "audit" / "convention_assignment.json", _assignment({"CONV-001": "CONV-C01"}))
    _write(c / "audit" / "run_completion.json", COMPLETED)
    whole = call_evidence.extract({"document_map": [{"unit_id": "u13-c"}],
                                   "document_text": "a whole document text", "task": "review"},
                                  call_id="c13", run_id="fixture", phase="5", doc_id="doc_c",
                                  agent="PRACTICE_AUDITOR", backend="local_auditor", model="fixture",
                                  rendered={"convention_ids": ["CONV-001"]})
    _jsonl(c / "logs" / "call_evidence.jsonl", [_call("c11", "u11-a", "CONV-001"),
                                                _call("c12", "u12-b", "CONV-001"), whole,
                                                _call("c14", "u14-d", "CONV-001"),
                                                _call("c23", "u23-m", "CONV-001"),
                                                _call("c26a", "u26-n", "CONV-001"),
                                                _call("c26b", "u26-n", "CONV-001"),
                                                _call("c27", "u27-o", "CONV-001")])
    _jsonl(c / "audit" / "model_replies" / "outcomes.jsonl",
           [{"call_id": "c14", "outcome": "accepted_to_bus", "source": "fixture", "timestamp": "x"}])
    _bus(c, [dict(_finding("u22-l", "missing_field", rule="CONV-008"), source_rule_id="CONV-C08")],
         doc_id="doc_c")
    _write(c / "deliverables" / "doc_c" / "review_data.json", {"amendments": []})
    pairs.append(("run_c", c, _plain_key("doc_c.md", [
        _p("u11", "CONV-C01"), _p("u12", "CONV-C01"), _p("u13", "CONV-C01"), _p("u14", "CONV-C01"),
        _p("u15", "CONV-C01"), _p("u16", "CONV-C01"), _p("u17", "CONV-C01", "unit_mismatch"),
        _p("u18", "CONV-C01"), _p("u19", "CONV-C01"), _p("u20", "CONV-C01"), _p("u21", "CONV-C08"),
        _p("u23", "CONV-C01"), _p("u26", "CONV-C01"), _p("u27", "CONV-C01")])))

    # D: no pairing map; one ordinary key and one round-comparison key on it
    d = root / "run_d"
    _write(d / "audit" / "run_completion.json", COMPLETED)
    _bus(d, [])
    _write(d / "deliverables" / "doc_d" / "review_data.json", {"amendments": []})
    pairs.append(("run_d", d, _plain_key("doc_d.md", [_p("u01", "CONV-D01")])))
    pairs.append(("run_d_rounds", d, _plain_key("doc_d.md", [], prior_records=[
        {"field_label": "rate", "relation": "changed_from_prior", "value_a": 1, "value_b": 2, "unit": ""}])))

    # E: a planned pair and no call evidence file (a run before the recording)
    e = root / "run_e"
    _write(e / "audit" / "pairing_map.json", {"doc_e": {"document_id": "doc_e",
                                                        "units": [_unit("u01-a", paired=["CONV-001"])]}})
    _write(e / "audit" / "convention_assignment.json", _assignment({"CONV-001": "CONV-E01"}))
    _bus(e, [])
    _write(e / "deliverables" / "doc_e" / "review_data.json", {"amendments": []})
    pairs.append(("run_e", e, _plain_key("doc_e.md", [_p("u01", "CONV-E01")])))

    # M: a multi-round run
    m = root / "run_m"
    _write(m / "audit" / "multi_round.json", {"outcome": "reviewed", "activation": {"activated": True},
                                              "round_review": {"availability": "recorded"}})
    _write(m / "audit" / "run_completion.json", COMPLETED)
    _bus(m, [])
    pairs.append(("run_m", m, _plain_key("doc_m.md", [dict(_p("u01", "CONV-M01"), round_id="r1",
                                                            document_id="doc_m")])))

    # F, G, H: adapter-style documents (CUAD's labels)
    flag, clear, cuad_mapping = _adapter_labels()
    for name in ("f", "g", "h"):
        r = root / ("run_" + name)
        _write(r / "audit" / "pairing_map.json", {"d-" + name: {"document_id": "d-" + name, "units": [
            _unit("u01-p-00001", paired=["CONV-001"]), _unit("u02-p-00002")]}})
        _write(r / "audit" / "convention_assignment.json",
               _assignment({"CONV-001": "CONV-CAP", "CONV-002": "CONV-CAQ", "CONV-003": "CONV-CAR"}))
        if name != "g":
            _write(r / "audit" / "run_completion.json", COMPLETED)
        _jsonl(r / "logs" / "call_evidence.jsonl", [])
        _write(r / "deliverables" / ("d-" + name) / "review_data.json", {"amendments": []})
    _bus(root / "run_f", [dict(_finding("u02-p-00002", "missing_field", rule="CONV-002"),
                               source_rule_id="CONV-CAQ")],
         backend="local_auditor", model="fixture", doc_id="d-f")
    for name in ("g", "h"):
        _bus(root / ("run_" + name), [])
    _write(root / "run_h" / "audit" / "model_replies" / "000001_c80.json",
           {"call_id": "c80", "agent": "PRACTICE_AUDITOR", "backend_ok": False,
            "error_category": cuad_mapping.B3_SETUP_FAILURE_KINDS[0], "payload": {"text": "PROMPT TEXT"}})

    def item(iid, rule, gold, units, measurable=None, cut=False, **extra):
        row = {"item_id": iid, "rule_id": rule, "gold": gold,
               "location_measurable": bool(units) if measurable is None else measurable,
               "evidence_unit_ids": units, "evidence_beyond_cut": cut}
        if measurable == "absent":
            del row["location_measurable"]
        return dict(row, **extra)
    pairs.append(("run_f", root / "run_f", _plain_key("d-f.md", [], benchmark="cuad", items=[
        item("I-2", "CONV-CAR", flag, []), item("I-3", "CONV-CAP", flag, ["u01-p-00001"]),
        item("I-4", "CONV-CAQ", clear, [])])))
    pairs.append(("run_g", root / "run_g", _plain_key("d-g.md", [], benchmark="cuad", items=[
        item("I-5", "CONV-CAP", flag, ["u01-p-00001"])])))
    # H travels as a collected archive: the setup failure is read from a reply record
    # unpacked with its status fields only
    archive = _archive(root / "run_h", root / "run_h_collected_evidence.tar.gz")
    pairs.append(("run_h", archive, _plain_key("d-h.md", [], benchmark="cuad", items=[
        item("I-6", "CONV-CAP", flag, ["u01-p-00001"])])))

    # I: document-level items (gold marks no location), read over every unit of their own
    # document. CONV-001 was put to the model on both units and every answer refused;
    # CONV-002 reached a call on one unit only, so its weakest unit (never shown with it)
    # decides, and its sub-cause is read on that unit alone: the judging row of the call on
    # u01 is not the weakest unit's. The map's second document is another document's.
    i = root / "run_i"
    _write(i / "audit" / "pairing_map.json", {"d-i": {
        "document_id": "d-i",
        "units": [_unit("u01-p-00001", paired=["CONV-001", "CONV-002"]),
                  _unit("u02-p-00002", paired=["CONV-001", "CONV-002"])],
        "judging_calls": [_judging("ci1", "u01-p-00001", "uncomputable", "judged_uncomputable",
                                   judged_refused=1),
                          _judging("ci2", "u02-p-00002", "uncomputable", "judged_uncomputable",
                                   judged_refused=1),
                          _judging("ci3", "u01-p-00001", "computed", "no_note_returned",
                                   rule_id="CONV-002")],
        "uncomputable_refused": [
            {"unit_id": "u01-p-00001", "rule_id": "CONV-001", "relation": "missing_field",
             "reason": "absence claim supplies no quote"},
            {"unit_id": "u02-p-00002", "rule_id": "CONV-001", "relation": "missing_field",
             "reason": "absence claim supplies no quote"}]},
        "d-other": {"document_id": "d-other", "units": [_unit("u09-p-00009")]}})
    _write(i / "audit" / "convention_assignment.json",
           _assignment({"CONV-001": "CONV-CAP", "CONV-002": "CONV-CAQ"}))
    _write(i / "audit" / "run_completion.json", COMPLETED)
    _jsonl(i / "logs" / "call_evidence.jsonl", [_call("ci1", "u01-p-00001", "CONV-001"),
                                                _call("ci2", "u02-p-00002", "CONV-001"),
                                                _call("ci3", "u01-p-00001", "CONV-002")])
    _bus(i, [])
    _write(i / "deliverables" / "d-i" / "review_data.json", {"amendments": []})
    pairs.append(("run_i", i, _plain_key("d-i.md", [], benchmark="cuad", items=[
        item("I-7", "CONV-CAP", flag, []), item("I-8", "CONV-CAQ", flag, [])])))

    # J: a document-level item on a run whose pairing map lists no unit to read it over
    j = root / "run_j"
    _write(j / "audit" / "pairing_map.json", {"d-j": {"document_id": "d-j", "units": []}})
    _write(j / "audit" / "convention_assignment.json", _assignment({"CONV-001": "CONV-CAP"}))
    _write(j / "audit" / "run_completion.json", COMPLETED)
    _jsonl(j / "logs" / "call_evidence.jsonl", [])
    _bus(j, [])
    _write(j / "deliverables" / "d-j" / "review_data.json", {"amendments": []})
    pairs.append(("run_j", j, _plain_key("d-j.md", [], benchmark="cuad", items=[
        item("I-9", "CONV-CAP", flag, [])])))

    # K: two items with no evidence unit that are not document-level: one marking a part
    # index whose part was kept only up to mid-text (the one kept part of a document whose
    # first part did not fit, so bundle.py dropped the index and set the cut mark), one whose
    # marked evidence matched no part; and a document-level item on this document, which
    # the first item shows was cut
    k = root / "run_k"
    _write(k / "audit" / "pairing_map.json", {"d-k": {"document_id": "d-k", "units": [
        _unit("u01-p-00001", paired=["CONV-001", "CONV-002"]),
        _unit("u02-p-00002", paired=["CONV-001", "CONV-002"])]}})
    _write(k / "audit" / "convention_assignment.json",
           _assignment({"CONV-001": "CONV-CAP", "CONV-002": "CONV-CAQ", "CONV-003": "CONV-CAR"}))
    _write(k / "audit" / "run_completion.json", COMPLETED)
    _jsonl(k / "logs" / "call_evidence.jsonl", [])
    _bus(k, [])
    _write(k / "deliverables" / "d-k" / "review_data.json", {"amendments": []})
    pairs.append(("run_k", k, _plain_key("d-k.md", [], benchmark="cuad", items=[
        item("I-10", "CONV-CAP", flag, [], measurable=True, cut=True, document_units=1),
        item("I-11", "CONV-CAQ", flag, [], measurable=True),
        item("I-13", "CONV-CAR", flag, [], measurable=False)])))

    # L: a document-level item on a run that saved no pairing map, and an item whose key
    # does not state location_measurable
    l_run = root / "run_l"
    _write(l_run / "audit" / "convention_assignment.json",
           _assignment({"CONV-001": "CONV-CAP", "CONV-002": "CONV-CAQ"}))
    _write(l_run / "audit" / "run_completion.json", COMPLETED)
    _jsonl(l_run / "logs" / "call_evidence.jsonl", [])
    _bus(l_run, [])
    _write(l_run / "deliverables" / "d-l" / "review_data.json", {"amendments": []})
    pairs.append(("run_l", l_run, _plain_key("d-l.md", [], benchmark="cuad", items=[
        item("I-12", "CONV-CAP", flag, []), item("I-14", "CONV-CAQ", flag, [], measurable="absent")])))
    out = []
    for label, run, key in pairs:
        key_path = _write(root / "keys" / label / "answer_key.json", key)
        out.append({"run": str(run), "key": str(key_path), "label": label})
    return out


def _adapter_gold():
    """CUAD's FLAG label, read from its adapter, so the fixture key states it as the
    adapter would."""
    sys.path.insert(0, str(ROOT / "benchmark" / "adapters"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("shimmer_check_cuad", ROOT / "benchmark" / "adapters" / "cuad" / "adapter.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SPEC.labels[module.mapping.FLAG]


def _adapter_labels():
    """CUAD's FLAG and CLEAR labels and its mapping module, from its adapter."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("shimmer_check_cuad", ROOT / "benchmark" / "adapters" / "cuad" / "adapter.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SPEC.labels[module.mapping.FLAG], module.SPEC.labels[module.mapping.CLEAR], module.mapping


def curated_benchmark_run(run):
    """Run B: an adapter-style document whose B3 run made a call over its model's context,
    so the adapter excludes it. Its key is curated_benchmark_key()."""
    run = Path(run)
    _write(run / "audit" / "pairing_map.json", {"d-x": {"document_id": "d-x", "units": [
        _unit("u01-p-00001", paired=["CONV-001"])]}})
    _write(run / "audit" / "convention_assignment.json", {"by_rule": {"CONV-001": {
        "status": "assigned", "consumer_agents": ["PRACTICE_AUDITOR"], "source_rule_id": "CONV-CAP"}}})
    _write(run / "audit" / "run_completion.json", COMPLETED)
    _jsonl(run / "logs" / "call_evidence.jsonl", [])
    _jsonl(run / "logs" / "agent_bus.jsonl", [])
    _write(run / "audit" / "model_replies" / "000001_c90.json",
           {"call_id": "c90", "context": {"prompt_tokens": 9000, "max_new_tokens": 512,
                                          "model_context": 8192, "over_context": True}})
    _write(run / "deliverables" / "d-x" / "review_data.json", {"amendments": []})
    return run


def curated_benchmark_key():
    return {"document": "d-x.md", "task_given_to_the_pipeline": "review", "twin_of": "", "planted": [],
            "clean": [], "benchmark": "cuad", "input_format": "input-format-v1-draft",
            "items": [{"item_id": "I-1", "rule_id": "CONV-CAP", "gold": _adapter_gold(),
                       "location_measurable": True, "evidence_unit_ids": ["u01-p-00001"],
                       "evidence_beyond_cut": False}]}


def _archive(run_dir, archive):
    """A collected_evidence.tar.gz as the controller packs it: evidence/run/..., plus a
    member outside evidence/ and one that names a parent path."""
    with tarfile.open(archive, "w:gz") as tar:
        for p in sorted(Path(run_dir).rglob("*")):
            if p.is_file():
                tar.add(p, arcname="evidence/run/" + p.relative_to(run_dir).as_posix(), recursive=False)
        for name, body in (("project/output/stray.json", b"{}"), ("../escape.txt", b"x"),
                           ("evidence/../../escape2.txt", b"x")):
            info = tarfile.TarInfo(name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    return archive


def curated_session(root):
    """A batch session folder: entry 00 a collected archive of run A (B3), entry 01 a B1
    entry with no pipeline run folder; and the key root holding item_a's key."""
    root = Path(root)
    staged = curated_run(root / "staging" / "run_a")
    session = root / "session"
    e0 = session / "batch" / "00_item_a_B3"
    e0.mkdir(parents=True)
    _archive(staged, e0 / "collected_evidence.tar.gz")
    _write(e0 / "collection_integrity.json", {"sha256": "x"})
    _write(e0 / "seal_entry.json", {"index": 0, "item": "item_a", "arm": "B3", "paired_with": 1})
    e1 = session / "batch" / "01_item_a_B1"
    e1.mkdir(parents=True)
    with tarfile.open(e1 / "collected_evidence.tar.gz", "w:gz") as tar:
        body = b"{}"
        info = tarfile.TarInfo("evidence/b1/tuned/b1_summary.json")
        info.size = len(body)
        tar.addfile(info, io.BytesIO(body))
    _write(e1 / "collection_integrity.json", {"sha256": "y"})
    _write(e1 / "seal_entry.json", {"index": 1, "item": "item_a", "arm": "B1", "paired_with": 0})
    keys = root / "keys"
    _write(keys / "item_a" / "answer_key.json", curated_key())
    return session, keys


def run_curated(td):
    """The diagnosis over the curated batch session and run B, as the command line runs it."""
    td = Path(td)
    session, keys = curated_session(td / "cur")
    run_b = curated_benchmark_run(td / "cur" / "run_b")
    key_b = _write(td / "cur" / "keys_b" / "d-x" / "answer_key.json", curated_benchmark_key())
    pairs = _write(td / "cur" / "pairs.json", branch_runs(td / "cur" / "branches"))
    out = td / "out"
    with contextlib.redirect_stdout(io.StringIO()):
        status = _tool().main(["--out-dir", str(out), "--session", str(session), "--key-root", str(keys),
                               "--pair", str(run_b), str(key_b), "--pairs", str(pairs)])
    return status, json.loads((out / "miss_diagnosis.json").read_text(encoding="utf-8")), out


def observe_curated():
    with tempfile.TemporaryDirectory(prefix="shimmer_miss_cur_") as td:
        status, report, out = run_curated(td)
        agg = report["aggregate"]
        return {"status": status,
                "runs": [(r["label"], r["scored"], r.get("arm"), r.get("expected"), r.get("caught_location"),
                          r.get("losses"), r.get("false_positives"), (r.get("note") or "")[:24])
                         for r in report["runs"]],
                "overall": {k: v for k, v in agg["overall"].items() if v},
                "losses": sorted((l["run"], l["entry"].get("unit") or l["entry"].get("field_label") or "",
                                  l["entry"].get("rule") or "", l["loss_class"], l["sub_cause"])
                                 for l in report["losses"]),
                "unreached_sub_causes": sorted(set(_tool().SITES) - {l["sub_cause"] for l in report["losses"]}),
                "markdown": (out / "miss_diagnosis.md").is_file(),
                "scorer_printout": sorted(p.name for p in (out / "scorer").iterdir())}


PD, UP, AB, UN = (fn_evidence.PRESENT_IN_PAYLOAD, fn_evidence.PRESENT_UPSTREAM,
                  fn_evidence.ABSENT_FROM_CORPUS, fn_evidence.UNKNOWN)


def expected_curated():
    tool = _tool()
    note = "benchmark items read fro"
    return {"status": 0,
            "runs": [("00_run_b", True, None, 1, 0, 1, 0, note),
                     ("run_c", True, None, 14, 0, 14, 0, ""),
                     ("run_d", True, None, 1, 0, 1, 0, ""),
                     ("run_d_rounds", True, None, 1, 0, 1, 0, ""),
                     ("run_e", True, None, 1, 0, 1, 0, ""),
                     ("run_m", True, None, 1, 0, 1, 0, ""),
                     ("run_f", True, None, 2, 0, 2, 1, note),
                     ("run_g", True, None, 1, 0, 1, 0, note),
                     ("run_h", True, None, 1, 0, 1, 0, note),
                     ("run_i", True, None, 2, 0, 2, 0, note),
                     ("run_j", True, None, 1, 0, 1, 0, note),
                     ("run_k", True, None, 3, 0, 3, 0, note),
                     ("run_l", True, None, 2, 0, 2, 0, note),
                     ("00_item_a_B3", True, "B3", 14, 5, 13, 0, ""),
                     ("01_item_a_B1", False, "B1", None, None, None, None, "not scored: B1 arm: the ")],
            "overall": {PD: 9, UP: 14, AB: 2, UN: 11, tool.SUSPENDED: 1, tool.WRONG_REASON: 3,
                        tool.UNVERIFIABLE: 1, tool.EXCLUDED: 3},
            "losses": sorted([
                ("00_item_a_B3", "u02", "CONV-A01", PD, "exposed_reply_failed"),
                ("00_item_a_B3", "u03", "CONV-A01", UP, "never_paired_missing_field"),
                ("00_item_a_B3", "u03", "CONV-Z09", UN, "rule_unmappable"),
                ("00_item_a_B3", "u04", "CONV-A01", UP, "paired_computed_no_irregularity"),
                ("00_item_a_B3", "u05", "CONV-A02", UP, "never_paired_undecided"),
                ("00_item_a_B3", "u06", "CONV-A01", tool.WRONG_REASON, "wrong_reason_figures"),
                ("00_item_a_B3", "u07", "CONV-A03", tool.SUSPENDED, "suspended_by_condition"),
                ("00_item_a_B3", "u08", "CONV-A01", UP, "near_miss_other_relation"),
                ("00_item_a_B3", "u09", "CONV-A04", UP, "paired_not_judged"),
                ("00_item_a_B3", "u10", "CONV-A01", tool.UNVERIFIABLE, "reason_untyped_amendment"),
                ("00_item_a_B3", "u99", "CONV-A01", AB, "unit_not_in_document"),
                ("00_item_a_B3", "u24", "CONV-A01", tool.WRONG_REASON, "wrong_reason_field_label"),
                ("00_item_a_B3", "u25", "CONV-A01", tool.WRONG_REASON, "wrong_reason_relation"),
                ("00_run_b", "", "CONV-CAP", tool.EXCLUDED, "excluded_over_context"),
                ("run_c", "u11", "CONV-C01", PD, "exposed_absence_refused"),
                ("run_c", "u12", "CONV-C01", PD, "exposed_python_found_no_disagreement"),
                ("run_c", "u13", "CONV-C01", PD, "exposed_whole_document_only"),
                ("run_c", "u14", "CONV-C01", PD, "exposed_reply_kept_no_matching_finding"),
                ("run_c", "u15", "CONV-C01", UP, "paired_absence_computed"),
                ("run_c", "u16", "CONV-C01", UP, "paired_judging_call_not_recorded"),
                ("run_c", "u17", "CONV-C01", UP, "relation_python_never_writes"),
                ("run_c", "u18", "CONV-C01", UP, "never_paired_scope_field"),
                ("run_c", "u19", "CONV-C01", UP, "never_paired_scope_value"),
                ("run_c", "u20", "CONV-C01", UP, "no_pairing_entry"),
                ("run_c", "u21", "CONV-C08", AB, "rule_not_loaded"),
                ("run_c", "u23", "CONV-C01", PD, "exposed_uncomputable_nothing_kept"),
                # one call kept nothing and refused nothing, another refused and kept: the
                # same row decides, so nothing was refused by a call that kept nothing
                ("run_c", "u26", "CONV-C01", PD, "exposed_uncomputable_nothing_kept"),
                # the call refused, but no refusal is recorded for its own rule and unit
                ("run_c", "u27", "CONV-C01", PD, "exposed_uncomputable_nothing_kept"),
                ("run_d", "u01", "CONV-D01", UN, "no_pairing_map"),
                ("run_d_rounds", "rate", "", UN, "round_row_not_unit_rule"),
                ("run_e", "u01", "CONV-E01", UN, "run_predates_call_evidence"),
                # document-level items: read over every unit, the weakest unit decides
                ("run_f", tool.DOCUMENT_LEVEL, "CONV-CAR", UP, "no_pairing_entry"),
                ("run_i", tool.DOCUMENT_LEVEL, "CONV-CAP", PD, "exposed_uncomputable_refused"),
                ("run_i", tool.DOCUMENT_LEVEL, "CONV-CAQ", UP, "paired_computed_no_irregularity"),
                ("run_j", "", "CONV-CAP", UN, "item_without_evidence_unit"),
                ("run_k", "", "CONV-CAP", UN, "evidence_cut_undecided"),
                ("run_k", "", "CONV-CAQ", UN, "item_evidence_unmatched"),
                ("run_k", "", "CONV-CAR", UN, "document_level_on_cut_document"),
                ("run_l", "", "CONV-CAP", UN, "no_pairing_map"),
                ("run_l", "", "CONV-CAQ", UN, "item_location_unstated"),
                ("run_f", "u01-p-00001", "CONV-CAP", UP, "paired_computed_no_irregularity"),
                ("run_g", "", "CONV-CAP", tool.EXCLUDED, "run_failed"),
                ("run_h", "", "CONV-CAP", tool.EXCLUDED, "excluded_setup_failure"),
                ("run_m", "u01", "CONV-M01", UN, "multi_round_unscoped")]),
            # the one fallback no saved artifact reaches today: fn_evidence names three
            # UNKNOWN reasons and the tool maps each; a fourth would land here, named
            "unreached_sub_causes": ["unknown_other"],
            "markdown": True,
            "scorer_printout": ["00_item_a_B3.txt", "00_run_b.txt", "run_c.txt", "run_d.txt",
                                "run_d_rounds.txt", "run_e.txt", "run_f.txt", "run_g.txt", "run_h.txt",
                                "run_i.txt", "run_j.txt", "run_k.txt", "run_l.txt", "run_m.txt"]}


# ---- neutralisations --------------------------------------------------------------------

def classifier_blind():
    """fn_evidence loses the pairing map: the never-paired and paired causes cannot be read."""
    real = fn_evidence.load_run_artifacts

    def blind(run_dir):
        arts = real(run_dir)
        arts["pairing"] = None
        return arts
    return patch.object(fn_evidence, "load_run_artifacts", blind)


def tool_reads_the_key():
    """The tool opens the key itself before handing it to the scorer."""
    tool = _tool()
    real = tool.score_through_scorer

    def peeking(run_dir, key_path):
        json.loads(Path(key_path).read_text(encoding="utf-8"))
        return real(run_dir, key_path)
    return patch.object(tool, "score_through_scorer", peeking)


def every_member_unpacked():
    """The archive filter dropped: every member unpacked whole, reply records with their
    text, members outside evidence/ too."""
    tool = _tool()
    return _two_patches(
        patch.object(tool, "_safe_members", lambda archive: [m for m in archive.getmembers()
                                                            if ".." not in m.name]),
        patch.object(tool, "_is_reply_record", lambda parts: False))


@contextlib.contextmanager
def _two_patches(a, b):
    with a, b:
        yield


def undecided_as_objects_only():
    """fn_evidence back to reading objects only: a bare undecided rule id is not seen."""
    return patch.object(fn_evidence, "_pair_rule_id",
                        lambda p: p.get("rule_id") if isinstance(p, dict) else None)


def stale_site():
    """A cause site whose line has gone (as after a rename)."""
    tool = _tool()
    sites = dict(tool.SITES)
    sites["never_paired_missing_field"] = [("scripts/pairing_map.py", "def a_function_that_is_gone(")]
    return patch.object(tool, "SITES", sites)


def document_level_unread():
    """The tool back to reading a document-level adapter item over no unit: every item whose
    gold names no evidence unit is UNKNOWN again, whatever the run saved."""
    return patch.object(_tool(), "document_units", lambda arts, document_id: [])


def document_level_strongest():
    """A document-level item decided by its STRONGEST unit, as a located item is: an item
    whose rule reached a call on one unit only reads as shown to a model."""
    tool = _tool()

    def strongest(rule, units, arts):
        rows = [fn_evidence.classify({"unit": uid, "rule": rule}, arts) for uid in units]
        best = min(rows, key=lambda ev: tool._STRENGTH.index(ev["class"]))
        return dict(best, unit_ids=list(units))
    return patch.object(tool, "document_level_class", strongest)


def cut_read_as_document_level():
    """Every item with no evidence unit read as a whole-document property: an item whose
    evidence fell beyond the cut, or matched no part, reads as reaching a payload."""
    return patch.object(_tool(), "document_level", lambda item: True)


def cut_read_as_absent():
    """An item marked beyond the cut filed as absent from the corpus, though its part may
    have been kept up to mid-text."""
    return patch.object(_tool(), "cut_item_loss", lambda: (
        fn_evidence.ABSENT_FROM_CORPUS, "evidence_beyond_cut", "the evidence lies wholly beyond the cut"))


def unstated_as_unmatched():
    """A key with no location_measurable read as one whose evidence matched no part."""
    return patch.object(_tool(), "unstated_location_loss", lambda: (
        "item_evidence_unmatched", "the gold marks evidence and none of it matched a part"))


def cut_document_unseen():
    """The key's other items never read for a cut: a document-level item on a cut document
    is read over its units as if whole."""
    return patch.object(_tool(), "cut_document", lambda bench: False)


def subcause_over_every_unit():
    """A document-level item's sub-cause read over every unit, the stronger ones too."""
    tool = _tool()
    real = tool.document_level_class

    def every(rule, units, arts):
        return dict(real(rule, units, arts), unit_ids=list(units))
    return patch.object(tool, "document_level_class", every)


def refused_from_any_unkept_call():
    """Any uncomputable call that kept nothing counts as refusing, whatever its own row
    says it refused."""
    return patch.object(_tool(), "refused_calls", lambda unkept: list(unkept))


def refusals_unfiltered():
    """Every uncomputable refusal counted, whatever its rule and unit."""
    tool = _tool()

    def unfiltered(arts, rule_id, unit_ids):
        out = {}
        for row in tool._doc_lists(arts, "uncomputable_refused"):
            why = str(row.get("reason") or "no reason recorded")
            out[why] = out.get(why, 0) + 1
        return out
    return patch.object(tool, "uncomputable_refusals", unfiltered)


def no_map_as_no_unit():
    """A run with no pairing map reported as a map listing no unit."""
    return patch.object(_tool(), "no_map_loss", lambda: (
        "item_without_evidence_unit", "the run's pairing map lists no unit to read it over"))


def every_document_read():
    """A document-level item read over every document's units in the map."""
    tool = _tool()

    def every(arts, document_id):
        out = []
        for entry in ((arts or {}).get("pairing") or {}).values():
            for u in (entry.get("units") if isinstance(entry, dict) else None) or []:
                if u.get("unit_id") not in out:
                    out.append(u.get("unit_id"))
        return out
    return patch.object(tool, "document_units", every)


def refusals_unread():
    """The pairing map's `uncomputable_refused` list unread: a refused answer looks like an
    answer that left nothing."""
    tool = _tool()
    real = tool._doc_lists

    def blind(arts, key):
        return iter(()) if key == "uncomputable_refused" else real(arts, key)
    return patch.object(tool, "_doc_lists", blind)


def upstream_losses_dropped():
    """The tool drops every never-asked loss (fn_evidence's second class), so the entries
    no call carried vanish from the table."""
    tool = _tool()
    real = tool.losses_for_run

    def dropping(result, run_dir):
        losses, caught, alarms = real(result, run_dir)
        return [l for l in losses if l["loss_class"] != fn_evidence.PRESENT_UPSTREAM], caught, alarms
    return patch.object(tool, "losses_for_run", dropping)


# ---- key reads traced -------------------------------------------------------------------

def _opener():
    """The first frame outside pathlib and this module: the module that asked for the file."""
    for frame in inspect.stack()[2:]:
        name = Path(frame.filename).name
        if name in ("pathlib.py", "_local.py", Path(__file__).name) or "pathlib" in frame.filename:
            continue
        return name
    return "?"


def observe_key_reads():
    """Every open of a file named answer_key.json during the curated diagnosis, by the
    module that opened it."""
    seen = set()
    real_open = builtins.open
    real_read = Path.read_text

    def traced_open(file, *a, **k):
        if Path(str(file)).name == "answer_key.json":
            seen.add(_opener())
        return real_open(file, *a, **k)

    def traced_read(self, *a, **k):
        if self.name == "answer_key.json":
            seen.add(_opener())
        return real_read(self, *a, **k)
    with tempfile.TemporaryDirectory(prefix="shimmer_miss_keys_") as td:
        session, keys = curated_session(Path(td) / "cur")
        with patch.object(builtins, "open", traced_open), patch.object(Path, "read_text", traced_read):
            with contextlib.redirect_stdout(io.StringIO()):
                _tool().main(["--out-dir", str(Path(td) / "out"), "--session", str(session),
                              "--key-root", str(keys)])
    return sorted(seen)


# ---- archive safety ---------------------------------------------------------------------

def observe_unpack():
    with tempfile.TemporaryDirectory(prefix="shimmer_miss_tar_") as td:
        td = Path(td)
        staged = curated_run(td / "staging")
        archive = _archive(staged, td / "collected_evidence.tar.gz")
        into = td / "unpacked"
        found = _tool().resolve_run(str(archive), into)
        files = sorted(p.relative_to(into).as_posix() for p in into.rglob("*") if p.is_file())
        replies = [f for f in files if "model_replies" in f and not f.endswith("outcomes.jsonl")]
        return {"run_dir": found["run_dir"] is not None and Path(found["run_dir"]).name == "run",
                "reply_records": replies,
                "reply_text": any("MODEL REPLY TEXT" in (into / f).read_text(encoding="utf-8") for f in replies),
                "outcomes_kept": any(f.endswith("model_replies/outcomes.jsonl") for f in files),
                "outside_evidence": [f for f in files if not f.startswith("evidence/")],
                "escaped": (td / "escape.txt").exists() or (td.parent / "escape2.txt").exists()}


UNPACK = {"run_dir": True, "reply_records": ["evidence/run/audit/model_replies/000001_c02.json"],
          "reply_text": False, "outcomes_kept": True, "outside_evidence": [], "escaped": False}


# ---- inputs ---------------------------------------------------------------------------

def observe_inputs():
    """How each kind of argument resolves, and what a pair that cannot be scored says."""
    tool = _tool()
    with tempfile.TemporaryDirectory(prefix="shimmer_miss_in_") as td:
        td = Path(td)
        curated_run(td / "session" / "downloaded" / "evidence" / "run")
        two = td / "two" / "evidence"
        for name in ("a", "b"):
            _write(two / name / "audit" / "run_completion.json", COMPLETED)
        (td / "empty").mkdir()
        multi = td / "multi"
        _write(multi / "audit" / "multi_round.json", {"outcome": "reviewed"})
        key = _write(td / "keys" / "plain.json", _plain_key("doc.md", [_p("u01", "CONV-X01")]))
        found = {name: tool.resolve_run(str(path), td / ("work_" + name)) for name, path in
                 (("downloaded", td / "session"), ("missing", td / "nothing.txt"), ("empty", td / "empty"))}
        two_runs = tool._run_in_evidence(two)
        report, _md = tool.diagnose([{"run": str(td / "session"), "key": str(td / "keys" / "absent.json")},
                                     {"run": str(multi), "key": str(key)}], td / "out")
        return {"downloaded": (found["downloaded"]["how"],
                               found["downloaded"]["run_dir"] is not None
                               and Path(found["downloaded"]["run_dir"]).name == "run"),
                "missing": found["missing"]["reason"].startswith("not a folder or a .tar.gz archive"),
                "empty": found["empty"]["reason"].startswith("no run folder, downloaded/evidence"),
                "two_runs": (two_runs[0], two_runs[1].startswith("2 run folders under")),
                "notes": [r.get("note", "").split(" at ")[0].split(": the scorer refused")[0]
                          + (": the scorer refused" if "the scorer refused" in r.get("note", "") else "")
                          for r in report["runs"]],
                "out_dir": [tool._refuse_out_dir(ROOT / "scripts") is not None,
                            tool._refuse_out_dir(ROOT / "output" / "diagnosis") is None,
                            tool._refuse_out_dir(td / "anywhere") is None]}


INPUTS = {"downloaded": ("downloaded", True), "missing": True, "empty": True, "two_runs": (None, True),
          "notes": ["not scored: no answer key", "not scored: the scorer refused"],
          "out_dir": [True, True, True]}


def evidence_never_found():
    """The run folder is never found inside an evidence/ folder."""
    return patch.object(_tool(), "_run_in_evidence", lambda evidence: (None, "not looked for"))


# ---- fn_evidence undecided --------------------------------------------------------------

def observe_undecided():
    with tempfile.TemporaryDirectory(prefix="shimmer_miss_und_") as td:
        run = curated_run(Path(td) / "run")
        arts = fn_evidence.load_run_artifacts(run)
        return {"status": list(fn_evidence._pair_status(arts, "u05-epsilon", "CONV-002")),
                "class": fn_evidence.classify({"unit": "u05", "rule": "CONV-A02"}, arts)["class"]}


UNDECIDED = {"status": ["undecided", "the rule names no field label of the document"], "class": UP}


# ---- sites ------------------------------------------------------------------------------

def observe_sites():
    tool = _tool()
    resolved = {name: tool.sites_for(name) for name in tool.SITES}
    return {"names": len(resolved), "not_found": sorted(s for v in resolved.values() for s in v if "NOT FOUND" in s)}


# ---- development material ---------------------------------------------------------------

FAMILIES = (("f1", 7), ("f2", 7), ("f3", 7))


def _test_bundle(test_dir):
    """The flawed bundle of one generated test (not its twin or a probe), named by the
    generator's own role reader (benchmark/generators/bundle.py _roles). The generator
    reads its own output there; the diagnosis under test never does."""
    if str(ROOT / "benchmark") not in sys.path:
        sys.path.insert(0, str(ROOT / "benchmark"))
    from generators import bundle as gen_bundle
    files = {}
    for b in sorted(Path(test_dir).iterdir()):
        if b.is_dir():
            files[b.name] = {p.relative_to(b).as_posix(): p.read_text(encoding="utf-8")
                             for p in b.rglob("*") if p.is_file()}
    return Path(test_dir) / gen_bundle._roles(files)["base"]


def replay_run_folder(bundle, run):
    """A run folder replayed from a bundle up to the first model call, with the pipeline's
    own functions. Python's findings are posted as Python's; each call Python planned for a
    model is recorded in logs/call_evidence.jsonl and the pairing map's judging_calls as made
    and returning nothing. A fixture for the diagnosis, never a run and never a measurement
    of Shimmer: no model answered anything."""
    import convention_assignment
    import convention_parser
    import finding_record
    import multi_round_rounds
    import pairing_map
    bundle, run = Path(bundle), Path(run)
    targets = json.loads((bundle / "context" / "_review_targets.json").read_text(encoding="utf-8"))["targets"]
    with tempfile.TemporaryDirectory(prefix="shimmer_replay_conv_") as td:
        conv = Path(td) / "input" / "conventions"
        conv.mkdir(parents=True)
        for p in sorted((bundle / "conventions").iterdir()):
            (conv / p.name).write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
        registry = convention_parser.parse_conventions(Path(td)).as_dict()
    rules = [r for r in registry["conventions"] if isinstance(r, dict)]
    agents = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    assignment = convention_assignment.assign_conventions(rules, agents)
    for rid, row in assignment["by_rule"].items():
        row["source_rule_id"] = finding_record.source_rule_id_for(rid, registry)
    pairing_all, evidence, posts = {}, [], []
    for name in targets:
        doc_id = name.rsplit(".", 1)[0]
        text = (bundle / "context" / name).read_text(encoding="utf-8")
        pairing = pairing_map.build_pairing_map(text, rules, document_id=doc_id, convention_registry=registry)
        refused = []
        rows, found, _n = multi_round_rounds.review_document({"id": doc_id, "text": text}, rules, {},
                                                             round_id="replay", refusals=refused)
        doc_map = [{"unit_id": u["unit_id"]} for u in pairing["units"]]
        judging = []
        for row in rows:
            for ask in row.get("needs_model") or []:
                consumers = assignment["by_rule"].get(ask["rule_id"], {}).get("consumer_agents") or ["VERIFIER"]
                cid = "replay%04d" % len(evidence)
                evidence.append(call_evidence.extract(
                    {"unit_id": ask["unit_id"], "rule_id": ask["rule_id"], "document_map": doc_map,
                     "task": "paired_judging"}, call_id=cid, run_id="replay", phase="5.5", doc_id=doc_id,
                    agent=consumers[0], backend="replay", model="none"))
                judging.append({"call_id": cid, "agent": consumers[0], "unit_id": ask["unit_id"],
                                "rule_id": ask["rule_id"], "plan_kind": ask.get("kind"), "backend": "replay",
                                "model": "none", "notes_kept": 0, "absence_listed": 0, "absence_refused": 0,
                                "judged_listed": 0, "judged_refused": 0, "outcome": "no_note_returned"})
        # RELATIONS-A: the paired review writes the comparisons it refused, as here.
        pairing.update(calls_made=len(judging), judging_calls=judging, relation_refusals=refused)
        pairing_all[doc_id] = pairing
        items = [f for f in found if finding_record.is_finding(f)] + list(pairing.get("missing_field_findings") or [])
        posts.append({"sender": "replay", "body": {"event": "AGENT_OUTPUT", "backend": "paired",
                                                   "model": "python",
                                                   "payload": {"agent": "replay", "doc_id": doc_id,
                                                               "items": items}}})
        _write(run / "deliverables" / doc_id / "review_data.json", {"amendments": []})
    _write(run / "audit" / "pairing_map.json", pairing_all)
    _write(run / "audit" / "convention_assignment.json", assignment)
    _write(run / "audit" / "run_completion.json", COMPLETED)
    _jsonl(run / "logs" / "call_evidence.jsonl", evidence)
    _jsonl(run / "logs" / "agent_bus.jsonl", posts)
    return run


def observe_development():
    """The diagnosis over replayed generator tests: per run, every planted entry caught or
    lost exactly once, and every loss with a resolved code site."""
    with tempfile.TemporaryDirectory(prefix="shimmer_miss_dev_") as td:
        td = Path(td)
        pairs = []
        for family, seed in FAMILIES:
            out = td / "gen" / family
            out.mkdir(parents=True)
            subprocess.run([sys.executable, "-B", "-X", "utf8", str(GEN / "generate.py"), "one", family,
                            str(seed), "--out", str(out)], check=True, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, cwd=str(out))
            test_dir = next(p for p in out.iterdir() if p.is_dir())
            base = _test_bundle(test_dir)
            run = replay_run_folder(base, td / "runs" / family)
            pairs.append({"run": str(run), "key": str(base / "answer_key.json"), "label": family})
        _write(td / "pairs.json", pairs)
        with contextlib.redirect_stdout(io.StringIO()):
            _tool().main(["--out-dir", str(td / "out"), "--pairs", str(td / "pairs.json")])
        report = json.loads((td / "out" / "miss_diagnosis.json").read_text(encoding="utf-8"))
    runs = report["runs"]
    by_run = {}
    for loss in report["losses"]:
        by_run[loss["run"]] = by_run.get(loss["run"], 0) + 1
    located_losses = {}
    for loss in report["losses"]:
        if loss["loss_class"] in (_tool().WRONG_REASON, _tool().UNVERIFIABLE):
            located_losses[loss["run"]] = located_losses.get(loss["run"], 0) + 1
    return {"families": sorted(r["family"] for r in runs),
            "all_scored": all(r["scored"] for r in runs),
            "accounted": all(r["caught_location"] + by_run.get(r["label"], 0)
                             - located_losses.get(r["label"], 0) == r["expected"] for r in runs),
            "expected_positive": all(r["expected"] > 0 for r in runs),
            "sites_resolved": all(l["cause_sites"] and not any("NOT FOUND" in s for s in l["cause_sites"])
                                  for l in report["losses"]),
            "classes_known": all(l["loss_class"] in report["loss_classes"] for l in report["losses"]),
            "summary": {r["label"]: (r["expected"], r["caught_location"], r["losses"]) for r in runs}}


def expected_development(observed_summary):
    return {"families": [f for f, _s in FAMILIES], "all_scored": True, "accounted": True,
            "expected_positive": True, "sites_resolved": True, "classes_known": True,
            "summary": observed_summary}


# ---- a run made before INFRA-045, scored now (D-198) --------------------------------------

def _scored_found(run, key):
    """Whether the scorer locates the key's one entry on the run."""
    import score_corpus
    result = {}
    with contextlib.redirect_stdout(io.StringIO()):
        score_corpus.score(str(key), str(run), key_path=str(key), result=result)
    return [e["found"] for e in result["entries"]]


def observe_pre_infra_045():
    """A model-written rate_mismatch record on the planted unit, on a run whose pairing map
    carries no relation_refusals (made before INFRA-045) and on one that does. The first is
    scored as the record read it then (not located; reported apart), the second like any
    relation."""
    out = {}
    with tempfile.TemporaryDirectory(prefix="shimmer_miss_pre045_") as td:
        for name, refusals in (("before", False), ("after", True)):
            run = Path(td) / name
            entry = {"document_id": "doc_r", "units": [_unit("u01-a", paired=["CONV-001"])]}
            if refusals:
                entry["relation_refusals"] = []
            _write(run / "audit" / "pairing_map.json", {"doc_r": entry})
            _write(run / "audit" / "convention_assignment.json", _assignment({"CONV-001": "CONV-R01"}))
            _write(run / "audit" / "run_completion.json", COMPLETED)
            _bus(run, [_finding("u01-a", "rate_mismatch", a=3.35, b=4.0, label="levy due")],
                 backend="local_auditor", model="fixture", doc_id="doc_r")
            _write(run / "deliverables" / "doc_r" / "review_data.json", {"amendments": []})
            key = _write(Path(td) / ("key_" + name) / "answer_key.json",
                         _plain_key("doc_r.md", [_p("u01", "CONV-R01", "rate_mismatch")]))
            out[name] = _scored_found(run, key)
    return out


PRE_INFRA_045 = {"before": [False], "after": [True]}


def every_run_read_as_current():
    """Neutralised: a run made before INFRA-045 is read under the current record."""
    import score_corpus
    return patch.object(score_corpus, "run_predates_infra_045", lambda run_dir: False)


class MissDiagnosisChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        result = prove_effect(name=name, validate=lambda: TOOL.is_file(), observe=observe,
                              check=lambda: ("PASS" if observe() == expected() else "FAIL", name),
                              neutralise=neutralise)
        MissDiagnosisChecks.evidence.append(result)

    def test_every_loss_class_is_reached_from_saved_artifacts(self):
        """Neutralised: fn_evidence loses the pairing map."""
        self.prove("loss_classes", observe_curated, expected_curated, classifier_blind)

    def test_a_document_level_item_is_read_over_every_unit(self):
        """Neutralised: an item whose gold names no evidence unit is read over no unit."""
        self.prove("document_level_read", observe_curated, expected_curated, document_level_unread)

    def test_a_document_level_item_takes_its_weakest_unit(self):
        """Neutralised: the strongest unit decides, as for a located item."""
        self.prove("document_level_weakest", observe_curated, expected_curated, document_level_strongest)

    def test_a_refused_answer_is_named_apart(self):
        """Neutralised: the pairing map's refusals of uncomputable answers are unread."""
        self.prove("uncomputable_refused_named", observe_curated, expected_curated, refusals_unread)

    def test_a_cut_or_unmatched_item_is_not_document_level(self):
        """Neutralised: every item with no evidence unit read as document-level."""
        self.prove("cut_not_document_level", observe_curated, expected_curated, cut_read_as_document_level)

    def test_a_partly_kept_cut_item_is_not_called_absent(self):
        """Neutralised: an item marked beyond the cut filed absent from the corpus."""
        self.prove("cut_not_absent", observe_curated, expected_curated, cut_read_as_absent)

    def test_an_unstated_location_is_named_apart(self):
        """Neutralised: no location_measurable read as matched no part."""
        self.prove("location_unstated", observe_curated, expected_curated, unstated_as_unmatched)

    def test_a_document_level_item_on_a_cut_document_is_not_read_as_whole(self):
        """Neutralised: the key's cut marks on other items unread."""
        self.prove("document_level_cut_document", observe_curated, expected_curated, cut_document_unseen)

    def test_a_document_level_sub_cause_is_read_on_its_weakest_units(self):
        """Neutralised: the sub-cause read over every unit."""
        self.prove("document_level_weakest_sub_cause", observe_curated, expected_curated,
                   subcause_over_every_unit)

    def test_a_refusal_is_decided_from_the_same_call(self):
        """Neutralised: any call that kept nothing counts as refusing."""
        self.prove("refusal_same_call", observe_curated, expected_curated, refused_from_any_unkept_call)

    def test_a_refusal_is_read_for_its_own_rule_and_unit(self):
        """Neutralised: refusals counted whatever their rule and unit."""
        self.prove("refusal_own_rule_unit", observe_curated, expected_curated, refusals_unfiltered)

    def test_a_run_with_no_pairing_map_says_so(self):
        """Neutralised: no map reported as a map with no unit."""
        self.prove("document_level_no_map", observe_curated, expected_curated, no_map_as_no_unit)

    def test_a_document_level_item_reads_its_own_document(self):
        """Neutralised: every document's units read."""
        self.prove("document_level_own_document", observe_curated, expected_curated, every_document_read)

    def test_the_key_is_read_only_through_the_scorer(self):
        """Neutralised: the tool opens the key itself."""
        self.prove("key_through_scorer", observe_key_reads, lambda: ["score_corpus.py"], tool_reads_the_key)

    def test_the_archive_is_unpacked_safely(self):
        """Neutralised: every evidence member unpacked, model reply records too."""
        self.prove("archive_unpacked_safely", observe_unpack, lambda: UNPACK, every_member_unpacked)

    def test_each_kind_of_input_resolves_or_says_why_not(self):
        """Neutralised: the run folder is never found inside evidence/."""
        self.prove("inputs", observe_inputs, lambda: INPUTS, evidence_never_found)

    def test_an_undecided_pair_is_read_as_undecided(self):
        """Neutralised: fn_evidence reads objects only."""
        self.prove("undecided_read", observe_undecided, lambda: UNDECIDED, undecided_as_objects_only)

    def test_every_code_site_resolves(self):
        """Neutralised: one site's line is gone."""
        self.prove("sites_resolve", observe_sites, lambda: {"names": len(_tool().SITES), "not_found": []},
                   stale_site)

    def test_a_run_before_infra_045_is_scored_as_its_record_read_it(self):
        """Neutralised: every run read under the current record (D-198, fix 11)."""
        self.prove("pre_infra_045", observe_pre_infra_045, lambda: PRE_INFRA_045,
                   every_run_read_as_current)

    def test_replayed_development_tests_are_accounted_for(self):
        """Neutralised: the tool drops every never-asked loss."""
        if not (GEN / "generate.py").is_file():
            self.skipTest("benchmark/generators/ is not in this tree")
        summary = observe_development()["summary"]
        self.prove("development_accounted", observe_development, lambda: expected_development(summary),
                   upstream_losses_dropped)


def check():
    MissDiagnosisChecks.evidence = []
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MissDiagnosisChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:200]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    skipped = "; development case skipped: %s" % result.skipped[0][1] if result.skipped else ""
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: every loss class and every sub-cause "
                    "but the named fallback reached on fourteen curated run folders over the ordinary, round, "
                    "multi-round and adapter-item paths (one through a batch session's collected archive "
                    "beside a B1 entry reported not scored); a document-level item read over every "
                    "unit of its own document with its weakest unit deciding and its sub-cause read on "
                    "the weakest units only; an item cut, unmatched or with its location unstated kept apart from a "
                    "document-level one and never called absent; a document-level item on a document "
                    "the key shows cut named; a run with no pairing map named; a refused uncomputable answer named apart, "
                    "decided from the same call and its own rule and unit; the key opened only by tools/score_corpus.py; "
                    "the archive unpacked under evidence/ only, reply records without their text; an "
                    "undecided pair read as undecided; every code site resolved; replayed generator "
                    "tests f1 to f3 accounted for entry by entry; a run made before INFRA-045 "
                    "scored as its record read the four relations (D-198)%s"
                    % (len(MissDiagnosisChecks.evidence), skipped))


if __name__ == "__main__":
    status, detail = check()
    print(status, detail)
    sys.exit(0 if status == "PASS" else 1)
