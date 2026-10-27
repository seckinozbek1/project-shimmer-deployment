"""Gate checks for S2a (honest deliverables): points 1 to 7, the reader-check
rounds 1 and 2 items (RC1 to RC18, RD1 to RD18), and the S2 checker round 1 items
(A4, A5, A8, C3/H5). Check 278 runs every proof here.

Every proof runs the REAL writers on a mocked run: the real phase-6 synthesis,
the real run-summary writer, the real audit synthesizer, the server's own
findings reader (its function definitions, executed without starting the app)
and the console's own marking function (executed under Node, as the shipped
localization checks do). No model, provider, network or GPU is touched: the
computed findings are minted by paired_review.finding_from_check, the model's
findings are authored envelopes posted under a model backend, and the phase-6
wrapper factory is replaced by a function that refuses to build a wrapper.

Each point is proven by neutralise, fail, restore, pass (effect_proof). The console
proof needs Node on PATH; without it that one proof is skipped and the PASS detail
says so rather than claiming the console.

    py -3.12 -X utf8 scripts/honest_output_checks.py                # run the proofs
    py -3.12 -X utf8 scripts/honest_output_checks.py --write DIR    # write one mocked
                                                                    # run's deliverables

--write DIR writes the deliverables of one mocked run in each output language under
DIR/en and DIR/tr (the run folder, deliverables and audit synthesis, with three
distinct escalations and two content-free copies on the bus), for a human reader
to inspect. It runs no proof, contacts nothing, and writes nothing outside DIR.
"""
from __future__ import annotations

import ast
import asyncio
import contextlib
import io
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import amendment_render
import audit_synthesizer
import finding_record
import localization as loc
import paired_review as pr
import summary_generators

ROOT = Path(__file__).resolve().parent.parent

DOC_TEXT = ("# Returned batch sheet\n\nBatch: B-7. Readings for review.\n\n"
            "## Entry Alpha\n\nSample identifier: S-ALPHA\nReading: 61 units\n\n"
            "## Entry Beta\n\nSample identifier: S-BETA\nReading: 40 units\nTotal weight: 9 kg\n\n"
            "| Line | Weight |\n|---|---|\n| L1 | 3 kg |\n| L2 | 5 kg |\n\n"
            "## Entry Gamma\n\nReading: 12 units\n")
RULES = [
    {"id": "CONV-001", "category": "conv-h01", "severity": "required",
     "rule": "A reading must lie between 10 units and 60 units."},
    {"id": "CONV-002", "category": "conv-h02", "severity": "required",
     "rule": "Every entry must state its sample identifier.",
     "scope": ["reading"], "requires": ["sample identifier"]},
    {"id": "CONV-003", "category": "conv-h03", "severity": "required",
     "rule": "The total weight must equal the sum of the weights listed."},
]
GARBLED = ("against the range against", "values against a stated", " gives ",
           "against a stated range")
# PRE-AUTHORED, NOT MODEL OUTPUT: the sentence a judging model returns when paired
# review asks it whether a computed disagreement is material.
# (Authored for the fixture; no model wrote it. It is labelled in every deliverable
# as a model's note because, in a real run, a model would have.)
AUTHORED_JUDGMENT = "The difference is material under the rule."


def _unit(units, slug):
    return next(u for u in units if slug in u)


def computed_findings(doc_id="batch_sheet", text=DOC_TEXT, refs=None):
    """Typed findings minted by the real Python path (the template proofs use these;
    the mocked run gets its computed findings from the real phase 5.5 instead)."""
    units = pr.unit_texts_for(text, doc_id)
    alpha, beta, gamma = (_unit(units, s) for s in ("entry-alpha", "entry-beta", "entry-gamma"))
    refs = refs or {}
    band = {"relation": "above_band", "computed": 61.0, "computed_unit": "units", "stated": None,
            "stated_unit": "units", "band_low": 10.0, "band_high": 60.0, "agrees": False,
            "basis": "reading against the range the rule states", "stated_field": "reading"}
    scalars, columns, rows = pr.extract_fields(units[beta]["text"])
    total = next(c for c in pr.compute_checks(scalars, columns, row_counts=rows)
                 if c["relation"] == "sum_mismatch")
    absent = pr._absence_check(("sample", "identifier"))
    return [
        pr.finding_from_check(unit_id=alpha, rule=RULES[0], check=band, source_rule_id="CONV-H01",
                              refs=[refs[alpha]] if alpha in refs else ["REF-0002"]),
        pr.finding_from_check(unit_id=beta, rule=RULES[2], check=total, source_rule_id="CONV-H03",
                              refs=[refs[beta]] if beta in refs else ["REF-0002"]),
        dict(pr.finding_from_check(unit_id=gamma, rule=RULES[1], check=absent, source_rule_id="CONV-H02",
                                   refs=[refs[gamma]] if gamma in refs else ["REF-0002"]),
             absence_path="computed"),
    ]


def model_finding(doc_id="batch_sheet"):
    """PRE-AUTHORED, NOT MODEL OUTPUT: a wide-review model finding whose figures
    the unit it names does not state (a realistic model error)."""
    units = pr.unit_texts_for(DOC_TEXT, doc_id)
    return {"kind": "finding", "record_verdict": "irregular", "rule_id": "CONV-003", "unit_id": _unit(units, "entry-alpha"),
            "relation": "sum_mismatch", "value_a": 4, "unit_a": "units", "value_b": 5, "unit_b": "units",
            "source_refs": ["REF-0002"], "ref": "REF-0002", "confidence": "CONFIDENT",
            "explanation": "The model reads the counts as not adding up."}


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = []

    def emit(self, record):
        self.events.append(record.getMessage())


def prior_case_items(doc_id="batch_sheet"):
    """PRE-AUTHORED, NOT MODEL OUTPUT. (a) A record shaped as Python's
    earlier-version comparison posts it (backend computed, model python). (b) Two
    items a model wrote in wide mode with figures of its own: one claiming an
    earlier-version relation AND `provenance: computed` (S2 checker A4), one claiming
    a band breach (A5). The figures 99 and 77 appear nowhere else in the run."""
    units = pr.unit_texts_for(DOC_TEXT, doc_id)
    alpha, beta, gamma = (_unit(units, s) for s in ("entry-alpha", "entry-beta", "entry-gamma"))
    python_prior = {"kind": "finding", "record_verdict": "ok", "rule_id": "CONV-001", "unit_id": gamma,
                    "relation": "changed_from_prior", "value_a": 12, "unit_a": "units", "value_b": 11,
                    "unit_b": "units", "field_label": "reading", "delta": 1, "provenance": "computed",
                    "source_refs": ["REF-0001"], "ref": "REF-0001", "confidence": "CONFIDENT",
                    "explanation": "The reading changed from 11 units to 12 units."}
    model_prior = dict(python_prior, unit_id=alpha, value_a=99, value_b=98,
                       explanation="The model says the reading moved.")
    model_band = {"kind": "finding", "record_verdict": "irregular", "rule_id": "CONV-001", "unit_id": beta,
                  "relation": "above_band", "value_a": 77, "unit_a": "units", "value_b": 60, "unit_b": "units",
                  "source_refs": ["REF-0002"], "ref": "REF-0002", "confidence": "CONFIDENT",
                  "explanation": "The model says the reading is above the range."}
    return python_prior, [model_prior, model_band]


def mocked_run(out_root, *, style_guardian=True, index_unit_passages=True, language="en", prior_case=False):
    """One mocked run, faithful to a real one where it matters: the computed
    findings come from the REAL phase 5.5 paired review (pairing map, planner,
    arithmetic, mint, bus post under paired/python); only the judging model's
    sentence is authored (`_run_one` returns it, as a model reply would). The model
    finding is an authored wide-review reply posted under its model backend. Then
    the real phase 6, the run summary, and the INST_FINDER record main() writes."""
    import pipeline as pl
    import reference_builder as rb
    import run_options
    import uuid
    from harness.run_agent import build_orchestrator
    doc = {"id": "batch_sheet", "name": "batch_sheet.md", "text": DOC_TEXT}
    registry = {"conventions": RULES}
    out_root = Path(out_root)
    orch = build_orchestrator(root=ROOT, out_root=out_root)
    run_options.configure(orch.run_context, "auto", language, "enabled")
    # As main() does: every registered agent gets an activation record.
    import agent_activation
    agent_activation.initialize(orch.run_context, json.loads(
        (ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8")).get("agents", {}), "dense")
    pl._inst_finder_startup_guard(orch.run_context, ROOT)
    index = rb.ReferenceIndex.open(ROOT, index_path=out_root / "refs.json")
    index.add(input_type="context", document_id="reference", document_name="reference.md",
              location={"page": 1, "paragraph": 1}, text_excerpt="Readings for batch B-7 lie between 10 and 60 units.")
    index.add(input_type="operational", document_id=doc["id"], document_name=doc["name"],
              location={"page": 1, "paragraph": 1}, text_excerpt="# Returned batch sheet Batch: B-7. Readings for review.")
    if index_unit_passages:
        for n, heading in enumerate(("## Entry Alpha", "## Entry Beta", "## Entry Gamma"), start=2):
            body = DOC_TEXT.split(heading, 1)[1].split("\n## ", 1)[0]
            index.add(input_type="operational", document_id=doc["id"], document_name=doc["name"],
                      location={"page": 1, "paragraph": n}, text_excerpt=heading + body)
    index.save()

    def record_call(agent, call_id, source_phase):
        """What run_task's activation observation records for a dispatched call."""
        audit = agent_activation.get(orch.run_context)
        if audit is not None:
            row = audit.decision(agent, eligible=True, activated=True, reason="selected_paired_plan",
                                 source_phase=source_phase, doc_id=doc["id"])
            audit.update(row, actual_call=True, call_id=call_id, state="completed", outcome="accepted")

    async def judging_reply(wrapper, payload, run_objectives, *args, **kwargs):
        call_id = uuid.uuid4().hex
        record_call(wrapper.name, call_id, "5.5")
        return {"ok": True, "backend": "local_auditor", "model": "fixture-auditor",
                "call_id": call_id, "raw_text": "", "item_count": 1,
                "parsed": {"agent": wrapper.name, "doc_id": doc["id"],
                           "items": [{"explanation": AUTHORED_JUDGMENT}]}}
    capture = _Capture()
    logger = logging.getLogger("shimmer.pipeline")
    logger.addHandler(capture)
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            with patch.object(pl, "_run_one", judging_reply):
                conv_review = asyncio.run(pl.phase_5_5_convention_review(
                    orch, {}, [doc], "declared proof", registry, index, embed_store=None,
                    max_concurrent_docs=1, review_mode="paired"))
            python_prior, model_extras = prior_case_items(doc["id"]) if prior_case else (None, [])
            posts = []
            if prior_case:
                posts.append({"scope": "doc", "doc_id": doc["id"], "agent": "PRACTICE_AUDITOR", "ok": True,
                              "backend": "computed", "model": "python",
                              "parsed": {"agent": "PRACTICE_AUDITOR", "doc_id": doc["id"], "items": [python_prior]}})
            if style_guardian:
                record_call("STYLE_GUARDIAN", "fixture-call-1", "5.5")
                posts.append({"scope": "doc", "doc_id": doc["id"], "agent": "STYLE_GUARDIAN", "ok": True,
                              "backend": "local_auditor", "model": "fixture-auditor", "call_id": "fixture-call-1",
                              "parsed": {"agent": "STYLE_GUARDIAN", "doc_id": doc["id"],
                                         "items": [model_finding()] + model_extras}})
            for env in posts:
                pl._build_wrapper(env["agent"], orch, {}).post_to_bus(
                    recipient="ORCHESTRATOR", channel="main", msg_type="INFORM",
                    body={"event": "AGENT_OUTPUT", "backend": env["backend"], "model": env["model"],
                          "payload": env["parsed"]},
                    constitution_check={"laws_consulted": ["LAW-V"], "result": "RESOLVED"})
            conv_review = list(conv_review) + posts
            with patch.object(pl, "_build_wrapper", side_effect=AssertionError("no model wrapper in phase 6")):
                deliverables = asyncio.run(pl.phase_6_synthesis(
                    orch, {}, [doc], [], [], conv_review, "declared proof", registry, index,
                    embed_store=None, max_concurrent_docs=1))
            pl.write_deliverables_run_summary(orch.run_context.deliverables_dir(), [doc], deliverables,
                                              total_cost_usd=0.0, task="review")
    finally:
        logger.removeHandler(capture)
    run_dir = orch.run_context.run_dir
    return {"run_dir": run_dir, "ctx": orch.run_context, "deliverables": deliverables, "doc": doc,
            "events": capture.events, "refs": out_root / "refs.json",
            "files": {name: (run_dir / "deliverables" / doc["id"] / name) for name in
                      ("document_summary.md", "grounding_summary.md", "reviewed_document.md",
                       "review_findings.md", "review_data.json")},
            "run_summary": run_dir / "deliverables" / "_run_summary.md"}


def server_findings(run_dir):
    """The server's own findings reader, executed from its source definitions
    (no FastAPI import, no app start)."""
    tree = ast.parse((ROOT / "scripts" / "server.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_project_finding", "_bus_findings")]
    scope = {"json": json}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "server_findings", "exec"), scope)
    return scope["_bus_findings"](Path(run_dir))


def console_marks(records, language="en"):
    """The console's own writtenByHtml, executed under Node with the shipped catalog."""
    if shutil.which("node") is None:
        return None
    html = (ROOT / "scripts" / "ui" / "console.html").read_text(encoding="utf-8")
    match = re.search(r"function writtenByHtml\(f, before\) \{.*?\n\}\n", html, re.DOTALL)
    paren = re.search(r"function mutedParen\(.*?\n\}\n", html, re.DOTALL)
    if match is None or paren is None:
        return {"error": "console function missing"}
    script = "\n".join([
        "var sessionStorage={getItem:function(){return null;},setItem:function(){}};",
        (ROOT / "scripts" / "ui" / "localization_catalog.js").read_text(encoding="utf-8"),
        (ROOT / "scripts" / "ui" / "localization.js").read_text(encoding="utf-8"),
        "function escapeHtml(s){return String(s);} var ui=ShimmerLocale.text;",
        paren.group(0), match.group(0),
        "ShimmerLocale.select(%s);" % json.dumps(language),
        "var rows=%s; console.log(JSON.stringify(rows.map(function(f){return [writtenByHtml(f,true),writtenByHtml(f,false)];})));"
        % json.dumps(records)])
    with tempfile.TemporaryDirectory(prefix="shimmer_console_marks_") as td:
        path = Path(td) / "marks.js"
        path.write_text(script, encoding="utf-8")
        result = subprocess.run(["node", str(path)], capture_output=True, text=True, timeout=30,
                                encoding="utf-8")
    if result.returncode != 0:
        return {"error": result.stderr[-300:]}
    return json.loads(result.stdout)


def _read(path):
    return Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""


def _model_lines(text, unit_id):
    return [ln for ln in text.splitlines() if "total does not match its parts" in ln and unit_id in ln]


# ---------- observations (each executes the real consumer; no verdicts) -----------------

def observe_marks():
    mark = finding_record.MODEL_FINDING_MARK
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_marks_") as td:
        run = mocked_run(td)
        unit = model_finding()["unit_id"]
        files = {name: _read(path) for name, path in run["files"].items()}
        master = json.loads(files["review_data.json"])
        records = server_findings(run["run_dir"])
        return {
            "document_summary": all(mark in ln for ln in _model_lines(files["document_summary.md"], unit))
                                and bool(_model_lines(files["document_summary.md"], unit)),
            "reviewed_document": any(mark in ln for ln in _model_lines(files["reviewed_document.md"], unit)),
            "review_findings": mark in files["review_findings.md"]
                               and any(mark in ln for ln in _model_lines(files["review_findings.md"], unit)),
            "master_model_findings": [f.get("unit_id") for f in master.get("model_findings_not_promoted", [])],
            "master_model_checked_fields": sorted({k for f in master.get("model_findings_not_promoted", [])
                                                   for k in finding_record.CHECKED_SOUNDING_FIELDS if k in f}),
            "master_model_flags": [(f.get("checked_by_python"), f.get("promoted"), f.get("model_claimed_verdict"))
                                   for f in master.get("model_findings_not_promoted", [])],
            "master_amendment_pairs": sorted("%s|%s|%s" % (a["finding_unit_id"], a["finding_rule_id"],
                                                          a.get("finding_value_a")) for a in master["amendments"]),
            "run_summary": mark in _read(run["run_summary"]),
            "server_written_by": sorted({(r["relation"], r.get("written_by")) for r in records}),
        }


def check_marks():
    o = observe_marks()
    unit = model_finding()["unit_id"]
    ok = (o["document_summary"] and o["reviewed_document"] and o["review_findings"] and o["run_summary"]
          and o["master_model_findings"] == [unit]
          and o["master_model_checked_fields"] == [] and o["master_model_flags"] == [(False, False, "irregular")]
          and "%s|CONV-003|4" % unit not in o["master_amendment_pairs"]
          and ("sum_mismatch", "model") in o["server_written_by"]
          and ("above_band", "python") in o["server_written_by"])
    return ("PASS" if ok else "FAIL", "model finding marked in every reader-facing file")


CONSOLE_SKIPPED = "console proof skipped: node is not on PATH"


def node_available():
    return shutil.which("node") is not None


def observe_console():
    """S2 checker H5/C3: the console's own marking function on the server's records,
    in both output languages: per record, who wrote it and which mark each side shows."""
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_console_") as td:
        run = mocked_run(td)
        records = server_findings(run["run_dir"])
    out = {"records": len(records)}
    for language in ("en", "tr"):
        shown = console_marks(records, language)
        model_mark = loc.message(finding_record.MODEL_FINDING_MARK, language)
        python_mark = loc.message(finding_record.COMPUTED_FINDING_MARK, language)
        if not isinstance(shown, list):
            out[language] = shown
            continue
        out[language] = [(r.get("written_by"), model_mark in before, python_mark in after)
                         for r, (before, after) in zip(records, shown)]
    return out


def check_console():
    o = observe_console()
    ok = o["records"] > 0
    for language in ("en", "tr"):
        rows = o.get(language)
        ok = (ok and isinstance(rows, list) and len(rows) == o["records"]
              and any(w == "model" for w, _, _ in rows) and any(w == "python" for w, _, _ in rows)
              # every model record carries the model mark, and no Python record does
              and all(model == (w == "model") for w, model, _ in rows)
              and all(python == (w == "python") for w, _, python in rows))
    return ("PASS" if ok else "FAIL", "the console marks every model record and no Python record, en and tr")


def observe_producer():
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_producer_") as td:
        computed_only = mocked_run(Path(td) / "a", style_guardian=False)
        mixed = mocked_run(Path(td) / "b", style_guardian=True)
        out = {}
        for name, run in (("computed_only", computed_only), ("mixed", mixed)):
            grounding = _read(run["files"]["grounding_summary.md"])
            summary = _read(run["files"]["document_summary.md"])
            sentence = next((ln for ln in grounding.splitlines() if ln.startswith("This document was reviewed")), "")
            body = next((ln for ln in summary.splitlines() if ln.startswith("Findings below come from")), "")
            log = next((e for e in run["events"] if e.startswith("findings_provenance ")), "")
            out[name] = {"sentence": sentence, "body": body, "log": log,
                         "names_style_guardian": "STYLE_GUARDIAN" in sentence + body,
                         "names_practice_auditor": "PRACTICE_AUDITOR" in sentence + body,
                         "tr_sentence": loc.message(sentence, "tr"), "tr_body": loc.message(body, "tr")}
        return out


def check_producer():
    o = observe_producer()
    a, b = o["computed_only"], o["mixed"]
    ok = (not a["names_style_guardian"] and not a["names_practice_auditor"]
          and "computed by Python from the document's figures: 3." in a["sentence"]
          and "Items written by a model (no model agent), not checked by Python and not promoted: 0." in a["sentence"]
          and "in total" not in a["sentence"] + b["sentence"]
          and a["log"] == "findings_provenance computed=3 model=0 model_agents=none"
          and "Items written by a model (STYLE_GUARDIAN), not checked by Python and not promoted: 1." in b["sentence"]
          and "STYLE_GUARDIAN" in b["body"]
          and b["log"] == "findings_provenance computed=3 model=1 model_agents=STYLE_GUARDIAN"
          and not b["names_practice_auditor"])
    # S2a-3 inside S2a-2: the tr rendering of both generated sentences.
    for row in (a, b):
        ok = ok and row["tr_sentence"] != row["sentence"] and "computed by Python" not in row["tr_sentence"]
        ok = ok and row["tr_body"] != row["body"] and "computed by Python" not in row["tr_body"]
    ok = ok and "model ajanı yok" in a["tr_sentence"]
    return ("PASS" if ok else "FAIL", "producer sentence generated from the run")


# Every English sentence this stage writes that a tr reader also receives.
def _localized_samples():
    prov_none = summary_generators.findings_provenance([])
    prov = {"total": 2, "computed": 1, "model": 1, "model_agents": ["STYLE_GUARDIAN"]}
    texts = [summary_generators.context_findings_sentence(3, prov_none, "x.md"),
             summary_generators.context_findings_sentence(3, prov, "x.md"),
             summary_generators.operative_findings_sentence(prov),
             finding_record.MODEL_FINDING_MARK, finding_record.COMPUTED_FINDING_MARK,
             amendment_render.MODEL_FINDINGS_HEADING, summary_generators.RELATIONS_FOUND_HEADING,
             summary_generators.RELATIONS_MODEL_HEADING, audit_synthesizer.AUDIT_COUNT_NOTE,
             "## Audit-trail patterns (not document findings)", "- audit-trail patterns: ",
             "**Findings computed by Python:**", "**Written by a model, not checked by Python, not promoted:**",
             "The model wrote: ", "The unit it names does not state these figures.", "A model's note (model: ",
             "Proposed amendments", "**Justification:**", "**Location:**",
             audit_synthesizer.KIND_WORDS["propose_amendment"], audit_synthesizer.ACTION_WORDS["add_amendment"]]
    sums = computed_findings()
    return texts + [a["comment"] for a in template_amendments()] + [
        pr.amendment_from_finding(sums[1], unit_texts=pr.unit_texts_for(DOC_TEXT, "batch_sheet"),
                                  unit_refs={sums[1]["unit_id"]: "REF-0004"},
                                  rule_texts={"CONV-003": RULES[2]["rule"]})["comment"]]


def observe_catalog():
    return [{"en": t, "tr": loc.message(t, "tr")} for t in _localized_samples()]


def check_catalog():
    rows = observe_catalog()
    english = ("computed by Python", "written by a model", "Computed in code", "Grounded in",
               "under rule", "Not promoted", "Relations found", "audit-trail", "Model findings",
               "Checked in code", "compared with", "reads:", "add up to", "The model wrote",
               "Proposed amendments", "Justification", "change proposal", "the operator decides")
    ok = all(r["tr"] != r["en"] and not any(w in r["tr"] for w in english) for r in rows)
    return ("PASS" if ok else "FAIL", "%d tr renderings" % len(rows))


def template_cases():
    """One irregular check per relation family, through the real mint."""
    units = pr.unit_texts_for(DOC_TEXT, "batch_sheet")
    alpha = _unit(units, "entry-alpha")
    base = {"agrees": False, "basis": "internal comparison basis gives against the range against"}
    checks = [
        dict(base, relation="above_band", computed=61.0, computed_unit="units", stated=None, stated_unit="units",
             band_low=10.0, band_high=60.0, stated_field="reading"),
        dict(base, relation="below_band", computed=4.0, computed_unit="units", stated=None, stated_unit="units",
             band_low=10.0, band_high=60.0, stated_field="reading"),
        dict(base, relation="ratio_out_of_range", computed=0.7, computed_unit="1", stated=0.5, stated_unit="1",
             stated_field="share"),
        dict(base, relation="sum_mismatch", computed=8.0, computed_unit="kg", stated=9.0, stated_unit="kg",
             stated_field="line total"),
        dict(base, relation="product_mismatch", computed=20.0, computed_unit="points", stated=25.0, stated_unit="points",
             stated_field="line price"),
        pr._absence_check(("sample", "identifier")),
        dict(base, relation="missing_field", computed=2, computed_unit="values", stated=4, stated_unit="rows",
             stated_field="weight"),
        dict(base, relation="date_window", computed=48.0, computed_unit="hours", stated=24.0, stated_unit="hours",
             stated_field="fault logged"),
        dict(base, relation="licence_missing", computed=0, computed_unit="values", stated=1, stated_unit="required",
             stated_field="certificate"),
    ]
    return [pr.finding_from_check(unit_id=alpha, rule=RULES[0], check=c, source_rule_id="CONV-H01",
                                  refs=["REF-0002"]) for c in checks]


def template_amendments():
    units = pr.unit_texts_for(DOC_TEXT, "batch_sheet")
    return [pr.amendment_from_finding(item, unit_texts=units, unit_refs={}) for item in template_cases()]


def observe_templates():
    out = []
    for item, amendment in zip(template_cases(), template_amendments()):
        lead = re.split(r"\. (?:Computed in code|Checked in code|Reported by the agent)", amendment["comment"])[0]
        out.append({"relation": item["relation"], "lead": lead, "explanation": item["explanation"],
                    "comment": amendment["comment"], "tr": loc.message(amendment["comment"], "tr")})
    return out


def check_templates():
    rows = observe_templates()
    bad = []
    for item, row in zip(template_cases(), rows):
        lead = row["lead"]
        need = [item["unit_id"], "CONV-001 (operator's id CONV-H01)"]
        relation, unit_b = item["relation"], item.get("unit_b")
        if relation == "licence_missing":
            need.append("a reference the rule requires is not present")
        elif unit_b == "required":            # a declared field the unit does not state
            need += ["'%s'" % item["field_label"], "is not stated in this unit"]
        elif unit_b == "rows":                # a column filled in fewer rows than the table has
            need += ["'%s'" % item["field_label"], "%s of %s rows" % (item["value_a"], item["value_b"])]
        else:                                 # two figures, each with its unit, and the relation
            tokens = pr._number_tokens(pr.unit_texts_for(DOC_TEXT, "batch_sheet")[item["unit_id"]]["text"])
            fig = lambda v, u: pr._figure(v, u, tokens)
            need += [fig(item["value_a"], item.get("unit_a")), fig(item["value_b"], unit_b)]
            need.append({"above_band": "above the upper bound", "below_band": "below the lower bound",
                         "ratio_out_of_range": "outside the permitted bound", "sum_mismatch": "add up to",
                         "product_mismatch": "comes to", "date_window": "longer than the allowed"}[relation])
        sentences = [s for s in re.split(r"(?<=[a-z0-9'])\. (?=[A-Z])", lead + ".") if s.strip()]
        if (not all(n in lead for n in need) or any(g in row["comment"] for g in GARBLED)
                or len(sentences) > 2 or row["explanation"] != pr.computed_sentence(item)
                or not lead.startswith("Unit %s (Entry Alpha) under rule" % item["unit_id"])
                or row["tr"] == row["comment"] or "under rule" in row["tr"]):
            bad.append(row["relation"])
    return ("FAIL" if bad else "PASS", "templates: %s" % (bad or "all plain"))


def observe_absence_location():
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_absence_") as td:
        out = {}
        for name, indexed in (("indexed", True), ("not_indexed", False)):
            run = mocked_run(Path(td) / name, style_guardian=False, index_unit_passages=indexed)
            master = json.loads(_read(run["files"]["review_data.json"]))
            refs = json.loads(_read(Path(td) / name / "refs.json")).get("entries", [])
            gamma_ref = next((e["ref_id"] for e in refs if "## Entry Gamma" in e.get("text_excerpt", "")), None)
            absent = [a for a in master["amendments"] if a.get("finding_relation") == "missing_field"]
            out[name] = {"locations": [a["location"] for a in absent], "gamma_ref": gamma_ref,
                         "sentences": [("passage %s." % gamma_ref) in a["comment"] for a in absent],
                         "unknown": ["could not find the passage of unit" in a["comment"] for a in absent],
                         "header_ref_used": any(a["location"] == "REF-0002" for a in absent)}
        return out


def check_absence_location():
    o = observe_absence_location()
    i, n = o["indexed"], o["not_indexed"]
    ok = (i["locations"] == [i["gamma_ref"]] and i["gamma_ref"] and i["sentences"] == [True]
          and not i["header_ref_used"]
          and n["locations"] == ["document-level"] and n["unknown"] == [True] and not n["header_ref_used"])
    return ("PASS" if ok else "FAIL", "absence amendment points to its unit")


def _section(text, heading):
    """The lines under a level-2 heading, up to the next level-2 heading."""
    if heading not in text:
        return None
    body = text.split(heading, 1)[1]
    return body.split("\n## ", 1)[0]


def observe_prior_sections():
    """S2 checker A4/A5: an earlier-version section driven by Python's own record,
    with a model's prior claim (provenance written by the model) and a model's
    band claim in the same run."""
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_prior_") as td:
        run = mocked_run(td, prior_case=True)
        units = pr.unit_texts_for(DOC_TEXT, "batch_sheet")
        gamma = _unit(units, "entry-gamma")
        master = json.loads(_read(run["files"]["review_data.json"]))
        out = {"master_prior_units": sorted(f.get("unit_id") for f in master.get("prior_comparisons") or []),
               "master_prior_values": sorted(f.get("value_a") for f in master.get("prior_comparisons") or [])}
        for name in ("document_summary.md", "review_findings.md"):
            text = _read(run["files"][name])
            section = _section(text, "## Compared with the earlier version")
            out[name] = None if section is None else {
                "python_prior": gamma in section,
                "model_prior": "99" in section,
                "model_band": "77" in section,
                "python_band": "61" in section,
                "model_items_elsewhere": "99" in text.replace(section, "") and "77" in text.replace(section, ""),
            }
        return out


def check_prior_sections():
    o = observe_prior_sections()
    ok = o["master_prior_units"] == [_unit(pr.unit_texts_for(DOC_TEXT, "batch_sheet"), "entry-gamma")] \
        and o["master_prior_values"] == [12]
    ok = ok and o["document_summary.md"] == {"python_prior": True, "model_prior": False, "model_band": False,
                                             "python_band": True, "model_items_elsewhere": True}
    rf = o["review_findings.md"]
    ok = ok and rf is not None and rf["python_prior"] and not rf["model_prior"] and not rf["model_band"]
    return ("PASS" if ok else "FAIL", "only Python's records in the earlier-version and band sections")


def observe_unplaced():
    """S2 checker A8: no unit passage indexed, so Python can place no unit."""
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_unplaced_") as td:
        run = mocked_run(td, style_guardian=False, index_unit_passages=False)
        records = [r for r in server_findings(run["run_dir"]) if r.get("written_by") == "python"]
        master = json.loads(_read(run["files"]["review_data.json"]))
        return {"findings": sorted((r.get("unit_id"), r.get("relation"), r.get("ref"), tuple(r.get("source_refs") or []))
                                   for r in records),
                "amendments": sorted((a.get("finding_unit_id"), a["location"], tuple(a.get("ref_ids") or []),
                                      pr.GROUND_UNPLACED.split("; ", 1)[1] in a["comment"],
                                      "cited passage" in a["comment"])
                                     for a in master["amendments"])}


def check_unplaced():
    o = observe_unplaced()
    ok = (len(o["findings"]) == 3 and all(ref in (None, "document-level") and refs == ()
                                          for _, _, ref, refs in o["findings"])
          and len(o["amendments"]) == 3
          and all(loc_ == "document-level" and refs == () and says and not cited
                  for _, loc_, refs, says, cited in o["amendments"]))
    return ("PASS" if ok else "FAIL", "an unplaced unit's finding and amendment cite no other passage")


LOTS = "## Lot 1\n\nReading: 3 units\n\n## Lot 12\n\nReading: 4 units\n"


def observe_heading_match():
    """S2 checker A8: a heading placed only where it opens a passage as a whole line."""
    units = pr.unit_texts_for(LOTS, "lots")
    prefix = pr.unit_passage_refs(units, [{"document_id": "lots", "ref_id": "REF-0012",
                                           "text_excerpt": "## Lot 12\n\nReading: 4 units"}], "lots")
    inside = pr.unit_passage_refs(units, [{"document_id": "lots", "ref_id": "REF-0050",
                                           "text_excerpt": "An introduction naming ## Lot 1 in passing."}], "lots")
    return {"units": sorted(units), "prefix": prefix, "inside": inside}


def check_heading_match():
    o = observe_heading_match()
    lot12 = next(u for u in o["units"] if u.endswith("lot-12"))
    ok = o["prefix"] == {lot12: "REF-0012"} and o["inside"] == {}
    return ("PASS" if ok else "FAIL", "'## Lot 1' is not placed at '## Lot 12' or inside another passage")


def post_escalations(bus, *, distinct, copies):
    """Escalations shaped as orchestrator.escalate posts them ({topic, payload}):
    `distinct` different payloads on one topic, and `copies` identical messages
    with no topic and no content (the shape RD3 found counted as a recurrence)."""
    for n in range(distinct):
        bus.post({"sender": "ORCHESTRATOR", "sender_role": "orchestrator", "recipient": "OPERATOR",
                  "channel": "escalation", "type": "ESCALATE",
                  "body": {"topic": "model_approval", "payload": {"agent": "AGENT_%d" % n, "reason": "deprecated"}},
                  "constitution_check": {"laws_consulted": ["LAW-0"], "result": "UNRESOLVED"}})
    for _ in range(copies):
        bus.post({"sender": "ORCHESTRATOR", "sender_role": "orchestrator", "recipient": "OPERATOR",
                  "channel": "escalation", "type": "ESCALATE", "body": {},
                  "constitution_check": {"laws_consulted": ["LAW-V"], "result": "RESOLVED"}})


def observe_audit_synthesis():
    from message_bus import MessageBus
    from run_context import RunContext
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_audit_") as td:
        ctx = RunContext(project_root=Path(td), run_id="auditfixture", run_dir=Path(td) / "run")
        ctx.ensure()
        bus = MessageBus.open(ctx.bus_path())
        post_escalations(bus, distinct=0, copies=3)
        empty = audit_synthesizer.AuditSynthesizer(project_root=Path(td), bus=bus, run_context=ctx).synthesize()
        ctx2 = RunContext(project_root=Path(td), run_id="auditfixture2", run_dir=Path(td) / "run2")
        ctx2.ensure()
        bus2 = MessageBus.open(ctx2.bus_path())
        post_escalations(bus2, distinct=3, copies=0)
        real = audit_synthesizer.AuditSynthesizer(project_root=Path(td), bus=bus2, run_context=ctx2).synthesize()
        text = _read(ctx.audit_synthesis_path())
        tr = audit_synthesizer._render_md(dict(generated_at="x", bus_messages=3, delta_proposals=[],
                                               findings=[dict(severity="high", category="governance",
                                                              summary="escalation topic 'TOPIC-1' recurred 3 times")]),
                                          output_language="tr")
        return {"count_line": next((ln for ln in text.splitlines() if "patterns" in ln and ln.startswith("- ")), ""),
                "says_not_document": "not findings about the document under review" in text,
                "old_label": "- findings: " in text, "heading": "## Audit-trail patterns (not document findings)" in text,
                "tr_says_not_document": "belge hakkındaki bulgular değildir" in tr,
                "copies_patterns": len(empty["findings"]), "copies_deltas": len(empty["delta_proposals"]),
                "copies_line": "- escalation messages with no topic or no content (not counted as a pattern): 3" in text,
                "distinct_patterns": len(real["findings"]), "distinct_deltas": len(real["delta_proposals"]),
                "tr_one_term": ("üst makama iletme" in tr and "yükseltme" not in tr and "Üst karar" not in tr
                                and "Yüksek" not in tr)}


def check_audit_synthesis():
    o = observe_audit_synthesis()
    ok = (o["count_line"].startswith("- audit-trail patterns: 0 (") and o["says_not_document"]
          and not o["old_label"] and o["heading"] and o["tr_says_not_document"]
          and o["copies_patterns"] == 0 and o["copies_deltas"] == 0 and o["copies_line"]
          and o["distinct_patterns"] == 1 and o["distinct_deltas"] == 1 and o["tr_one_term"])
    return ("PASS" if ok else "FAIL", "audit synthesis says what it counts")


def observe_relations():
    import importlib.util
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_relations_") as td:
        run = mocked_run(td)
        text = _read(run["run_summary"])
        found, model = text.split("## Relations found (computed by Python)", 1)[-1].split(
            "## Relations a model reported", 1) if "## Relations a model reported" in text else (text, "")
        spec = importlib.util.spec_from_file_location("score_corpus_s2a", ROOT / "tools" / "score_corpus.py")
        scorer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scorer)
        findings = scorer._load_bus_findings(run["run_dir"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scorer._print_relation_breakdown(findings)
        lines = out.getvalue().splitlines()
        confirmed = io.StringIO()
        with contextlib.redirect_stdout(confirmed):
            scorer._print_relation_breakdown(findings, [f for f in findings if f.get("relation") == "sum_mismatch"
                                                        and f.get("_written_by") == "model"])
        return {"found_section": sorted(set(re.findall(r"- ([^:\n]+): \d", found))),
                "model_section": sorted(set(re.findall(r"- ([^:\n]+): \d", model))),
                "model_marked": finding_record.MODEL_FINDING_MARK in model,
                "mentions_scorer": "scorer" in text,
                "scorer_found": next((ln for ln in lines if ln.startswith("relations found")), ""),
                "scorer_model": next((ln for ln in lines if ln.startswith("model-only")), ""),
                "scorer_confirmed": confirmed.getvalue().splitlines()[0] if confirmed.getvalue() else ""}


def check_relations():
    o = observe_relations()
    ok = (o["found_section"] == ["above the allowed range", "required field missing", "total does not match its parts"]
          and o["model_section"] == ["total does not match its parts"] and o["model_marked"] and not o["mentions_scorer"]
          and o["scorer_found"] == "relations found : above_band=1, missing_field=1, sum_mismatch=1"
          and "sum_mismatch=1" in o["scorer_model"]
          and o["scorer_confirmed"] == "relations found : above_band=1, missing_field=1, sum_mismatch=2")
    return ("PASS" if ok else "FAIL", "model-only relations listed apart")


def _passages(refs_path):
    """REF id -> excerpt, read from the run's own reference index file."""
    return {e["ref_id"]: e.get("text_excerpt", "") for e in json.loads(_read(refs_path)).get("entries", [])}


def observe_reader_check():
    """Reader check round 1, read off one English and one tr mocked run."""
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_reader_") as td:
        en = mocked_run(Path(td) / "en")
        tr = mocked_run(Path(td) / "tr", language="tr")
        passages = _passages(en["refs"])
        master = json.loads(_read(en["files"]["review_data.json"]))
        units = pr.unit_texts_for(DOC_TEXT, "batch_sheet")
        by_unit = {a["finding_unit_id"]: a for a in master["amendments"]}
        files = {k: _read(v) for k, v in en["files"].items()}
        tr_files = {k: _read(v) for k, v in tr["files"].items()}
        audit = audit_synthesizer._render_md(dict(
            generated_at="x", bus_messages=3, findings=[dict(severity="high", category="governance",
                                                             summary="escalation topic 'model_approval' recurred 3 times")],
            delta_proposals=[dict(id="DELTA-1", kind="propose_amendment", trigger="repeated escalation: model_approval",
                                  proposed_change={"action": "add_amendment", "target": "constitution"},
                                  requires_operator_approval=True)]))
        refs_entries = json.loads(_read(en["refs"])).get("entries", [])
        cited = {e["ref_id"]: e.get("cited_by") for e in refs_entries}
        alpha = by_unit.get(_unit(units, "entry-alpha"), {})
        beta = by_unit.get(_unit(units, "entry-beta"), {})
        return {
            # RC1: the sum names its addends, and they are in the unit's own text
            "sum_names_addends": "'weight' (3 + 5 kg) add up to 8 kg, but the stated total weight is 9 kg" in beta.get("comment", ""),
            "addends_in_unit": all(t in units[_unit(units, "entry-beta")]["text"] for t in ("3 kg", "5 kg")),
            # RC2/RC3: each amendment sits at its own unit's passage, and the summary cites the same
            "located_at_own_passage": sorted(
                (uid, uid in by_unit and units[uid]["text"].splitlines()[0] in passages.get(by_unit[uid]["location"], ""))
                for uid in by_unit),
            "summary_cites_own_passages": all(
                ("cites %s" % a["location"]) in files["document_summary.md"] for a in master["amendments"]),
            "header_or_reference_located": [a["location"] for a in master["amendments"]
                                            if a["location"] in ("REF-0001", "REF-0002")],
            # RC5: the per-agent record names the backend and model the run recorded
            "per_agent_backend": ("Backend `paired`, model `python`." in files["reviewed_document.md"]
                                  and "Notes written by a model, not checked by Python: `fixture-auditor`."
                                  in files["reviewed_document.md"]),
            # RD1/RD4/RD6: the note is quoted and names its model; the counts keep notes apart
            "note_named": ('A model\'s note (model: fixture-auditor), not checked by Python: "%s"' % AUTHORED_JUDGMENT
                           in alpha.get("comment", "")),
            "note_counts": ("Model-written notes attached to Python's findings (model: fixture-auditor), not checked "
                            "by Python: 2." in files["grounding_summary.md"]
                            and "Items written by a model (STYLE_GUARDIAN), not checked by Python and not promoted: 1."
                            in files["grounding_summary.md"]),
            # RD2: the model item's citation, applicability and missing addends, in words
            "model_item_notes": all(n in files["document_summary.md"] and n in files["review_findings.md"] for n in (
                "It cites REF-0002, which is the passage of Returned batch sheet, not this unit's own passage (REF-0003).",
                "Python's pairing map found that rule CONV-003 does not apply to this unit: unit lacks total weight.",
                "The model names no addends for this sum.")),
            # RD7: the rule and the passage named apart
            "ground_wording": ("Rule CONV-001 (operator's id CONV-H01); passage REF-0003." in alpha.get("comment", "")
                               and "Grounded in" not in json.dumps(master)),
            # RD8: the evidence line is a sentence, not a key dump
            "evidence_plain": ("Python's record: " in files["review_findings.md"]
                               and "derived_from:" not in files["review_findings.md"]
                               and "finding_value_a" not in files["review_findings.md"]),
            # RD9: relation words
            "relation_words": ("above the allowed range" in files["document_summary.md"]
                               and "above_band" not in files["document_summary.md"] + _read(en["run_summary"])
                               and "toplam uyuşmazlığı" in _read(tr["run_summary"])),
            # RD11: the reference index records who cites what
            "cited_by": all(cited.get(a["location"]) for a in master["amendments"]),
            # RD12/RD16: the rule book is called that, its words labelled
            "rules_applied": ("## Rules applied" in files["grounding_summary.md"]
                              and "reference corpus establishes" not in files["grounding_summary.md"]
                              and "kuralın özgün metni: " in tr_files["document_summary.md"]),
            # RD13: every registered agent, and INST_FINDER's recorded calls
            "all_agents": all(("- %s: " % a) in files["reviewed_document.md"]
                              for a in ("INST_FINDER", "AMENDMENT_DRAFTER", "REDACTOR", "ARCHIVIST")),
            "inst_finder_calls": "- INST_FINDER model calls in this run: 0 (it produced no output)" in _read(en["run_summary"]),
            # RD14: an absence is checked, not computed from figures
            "absence_mark": ("required field: sample identifier; found: none; cites REF-0005 (Checked in code"
                             in files["document_summary.md"]),
            # RD15: the tr band sentence quotes the document's own field name
            "tr_field_quoted": "'reading' değeri 61 units" in tr_files["review_findings.md"],
            # RD18: figures as written, the second id explained, flagged passages
            "as_written": "the reading is 61 units, above the upper bound of 60 units" in alpha.get("comment", ""),
            "flagged_title": files["review_findings.md"].splitlines()[0].endswith(": Flagged passages"),
            # RC6/RC12: a model's line is apart and carries no verdict; an absence says what was checked
            "model_apart": "**Written by a model, not checked by Python, not promoted:**" in files["document_summary.md"],
            "model_line_verdict": any("irregular" in ln and "u01-entry-alpha" in ln and "total does not match its parts" in ln
                                      for ln in files["document_summary.md"].splitlines()),
            "figures_note": "The unit it names does not state these figures." in files["document_summary.md"],
            "absence_wording": ("Checked in code: the field is absent" in json.dumps(master)
                                and "required field: sample identifier; found: none" in files["document_summary.md"]),
            # RC9/RC15: governance wording and no placeholders
            "audit_words": [w for w in ("propose_amendment", "add_amendment", "[HIGH]", "True", "<document>") if w in audit],
            "placeholders": [w for w in ("/?)", "para ?", "setting not recorded") if w in
                             files["document_summary.md"] + files["grounding_summary.md"] + _read(en["run_summary"])],
            # RC16/RC17: names, the rule's words, the per-agent title
            "names_and_rule_words": ("(Entry Beta)" in beta.get("comment", "")
                                     and 'Rule CONV-003 reads: "' in beta.get("comment", "")),
            "per_agent_title": "raw reply for this document" in files["reviewed_document.md"].splitlines()[0],
            # RC4/RC11/RC13/RC14: the tr findings file has the English layout and no raw dump
            "tr_layout": ("### Değişiklik 1 [" in tr_files["review_findings.md"]
                          and "- değişiklikler: 3" in tr_files["review_findings.md"]
                          and "İnceleme: işaretlenen bölümler" in tr_files["review_findings.md"]
                          and "```json" not in tr_files["review_findings.md"]
                          and "model_findings_not_promoted" not in tr_files["review_findings.md"]
                          and "written_by" not in tr_files["review_findings.md"]
                          and "\\n" not in tr_files["review_findings.md"]),
            "tr_band_grammar": "olan aralığın üzerindedir" in tr_files["review_findings.md"],
            "placeholder_left": [w for w in ("AUTHORED FIXTURE", "TOPIC-1") if w in
                                 json.dumps(master) + files["review_findings.md"] + tr_files["review_findings.md"]],
            # RC18: no em or en dash in any reader-facing file, either language
            "dashes": sum(text.count(chr(0x2014)) + text.count(chr(0x2013)) for text in
                          list(files.values()) + list(tr_files.values())
                          + [_read(en["run_summary"]), _read(tr["run_summary"]), audit]),
            "tr_untranslated": [w for w in ("Computed in code", "Grounded in", "under rule", "Checked in code",
                                            "figure:", "compared with:", "verdict=", "unit=")
                                if w in tr_files["review_findings.md"] + tr_files["document_summary.md"]],
        }


def check_reader_check():
    o = observe_reader_check()
    expected_located = sorted((u, True) for u, _ in o["located_at_own_passage"])
    ok = (o["sum_names_addends"] and o["addends_in_unit"]
          and len(o["located_at_own_passage"]) == 3 and o["located_at_own_passage"] == expected_located
          and o["summary_cites_own_passages"] and o["header_or_reference_located"] == []
          and o["per_agent_backend"] and o["model_apart"] and not o["model_line_verdict"]
          and o["figures_note"] and o["absence_wording"] and o["audit_words"] == []
          and o["placeholders"] == [] and o["names_and_rule_words"] and o["per_agent_title"]
          and o["tr_layout"] and o["tr_band_grammar"] and o["tr_untranslated"] == []
          and o["dashes"] == 0)
    rd = ("note_named", "note_counts", "model_item_notes", "ground_wording", "evidence_plain", "relation_words",
          "cited_by", "rules_applied", "all_agents", "inst_finder_calls", "absence_mark", "tr_field_quoted",
          "as_written", "flagged_title")
    ok = ok and all(o[k] for k in rd) and o["placeholder_left"] == []
    return ("PASS" if ok else "FAIL", "reader check rounds 1 and 2 items closed: %s" % (
        [k for k in rd if not o[k]] or "all"))


def _json_block_renderer(payload, document_name, category_for_conv, **kwargs):
    """The removed tr layout (JSON blocks), as a neutralisation."""
    return "# x\n```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```\n" + "\n".join(
        "### Değişiklik %d" % i for i, _ in enumerate(payload.get("amendments", []), 1))


# ---------- the proofs ---------------------------------------------------------------------

def _old_relation_clause(item):
    return "%s against the range against the matched row gives %s %s" % (
        item.get("field_label"), item.get("value_a"), item.get("unit_a"))


def _old_context_sentence(n, provenance, name):
    return ("This document was reviewed against %d conventions. %d findings were produced by "
            "PRACTICE_AUDITOR and STYLE_GUARDIAN. The context references below are filtered for "
            "topical relevance to %s." % (n, provenance["total"], name))


class _CatalogWithout:
    """The catalog with this stage's tr rows removed (the neutralisation)."""

    def __enter__(self):
        self.saved = loc.catalog()
        stripped = dict(self.saved)
        stripped["_messages"] = [r for r in self.saved["_messages"]
                                 if "under\\ rule" not in r["pattern"] and "computed\\ by\\ Python" not in r["pattern"]
                                 and "Computed\\ in\\ code" not in r["pattern"] and "model's\\ note" not in r["pattern"]]
        for key in [k for k in stripped if isinstance(k, str) and ("audit-trail" in k or "written by a model" in k.lower()
                                                                     or "Relations " in k or "Model findings" in k
                                                                     or "Computed by Python" in k or "no model agent" in k)]:
            stripped.pop(key)
        self.patch = patch.object(loc, "catalog", lambda: stripped)
        self.patch.__enter__()
        return self

    def __exit__(self, *exc):
        return self.patch.__exit__(*exc)


class HonestOutputChecks(unittest.TestCase):
    def prove(self, name, observe, check, neutralise):
        from effect_proof import prove_effect
        validate = lambda: all(finding_record.is_finding(f) for f in computed_findings() + [model_finding()])
        prove_effect(name=name, validate=validate, observe=observe, check=check, neutralise=neutralise)

    def test_s2a1_model_findings_marked_everywhere(self):
        self.prove("s2a1_marks", observe_marks, check_marks,
                   lambda: patch.object(finding_record, "written_by", lambda backend, model: "python"))

    def test_c3_console_marks_every_model_record(self):
        if not node_available():
            self.skipTest(CONSOLE_SKIPPED)
        self.prove("c3_console", observe_console, check_console,
                   lambda: patch.object(finding_record, "written_by", lambda backend, model: "python"))

    def test_s2a2_producer_sentence_from_the_run(self):
        self.prove("s2a2_producer", observe_producer, check_producer,
                   lambda: patch.object(summary_generators, "context_findings_sentence", _old_context_sentence))

    def test_s2a3_tr_catalog_covers_every_new_sentence(self):
        self.prove("s2a3_catalog", observe_catalog, check_catalog, _CatalogWithout)

    def test_s2a4_templates_read_as_plain_english(self):
        self.prove("s2a4_templates", observe_templates, check_templates,
                   lambda: patch.object(pr, "relation_clause", _old_relation_clause))

    def test_s2a5_absence_points_to_its_unit(self):
        self.prove("s2a5_absence", observe_absence_location, check_absence_location,
                   lambda: patch.object(pr, "unit_passage_refs", lambda *a, **k: None))

    def test_s2a6_audit_synthesis_says_what_it_counts(self):
        self.prove("s2a6_audit", observe_audit_synthesis, check_audit_synthesis,
                   lambda: patch.object(audit_synthesizer, "AUDIT_COUNT_NOTE", ""))

    # Reader check round 1: each mechanism, neutralised alone, must fail the check.
    def test_rc1_sum_names_its_addends(self):
        self.prove("rc1_addends", observe_reader_check, check_reader_check,
                   lambda: patch.object(pr, "RELATION_DETAIL_FIELDS", ()))

    def test_rc2_rc3_amendment_and_finding_sit_at_the_units_passage(self):
        self.prove("rc2_rc3_location", observe_reader_check, check_reader_check,
                   lambda: patch.object(pr, "unit_passage_refs", lambda *a, **k: {}))

    def test_rc6_rc7_model_items_apart_without_checked_fields(self):
        self.prove("rc6_rc7_model_items", observe_reader_check, check_reader_check,
                   lambda: patch.object(finding_record, "reader_line", finding_record.typed_line))

    def test_rc9_audit_wording(self):
        self.prove("rc9_audit_words", observe_reader_check, check_reader_check,
                   lambda: patch.object(audit_synthesizer, "KIND_WORDS", {}))

    def test_rc12_absence_says_what_was_checked(self):
        self.prove("rc12_absence", observe_reader_check, check_reader_check,
                   lambda: patch.object(pr, "ABSENCE_PROVENANCE",
                                        "Computed in code from the figures in this unit, not judged by a model."))

    def test_rc14_tr_findings_file_has_the_english_layout(self):
        self.prove("rc14_tr_layout", observe_reader_check, check_reader_check,
                   lambda: patch.object(amendment_render, "_render_md", _json_block_renderer))

    def test_rc16_units_named_and_rules_quoted(self):
        self.prove("rc16_names", observe_reader_check, check_reader_check,
                   lambda: patch.object(pr, "_unit_title", lambda record: ""))

    def test_rc18_no_dashes_in_reader_files(self):
        self.prove("rc18_dashes", observe_reader_check, check_reader_check,
                   lambda: patch.object(amendment_render, "MODEL_FINDINGS_HEADING",
                                        "## Written by a model " + chr(0x2014) + " not checked by Python"))

    # Reader check round 2: each mechanism, neutralised alone, must fail the check.
    def test_rd1_rd4_rd6_note_writer_named_and_counted(self):
        self.prove("rd1_note_writer", observe_reader_check, check_reader_check,
                   lambda: patch.object(pr, "stamp_note_writer", lambda item, reply: item))

    def test_rd2_model_item_notes(self):
        self.prove("rd2_model_notes", observe_reader_check, check_reader_check,
                   lambda: patch.object(pr, "model_item_notes", lambda *a, **k: []))

    def test_rd3_escalation_copies_are_not_a_pattern(self):
        self.prove("rd3_escalations", observe_audit_synthesis, check_audit_synthesis,
                   lambda: patch.object(audit_synthesizer, "escalation_key",
                                        lambda body: ("model_approval", __import__("uuid").uuid4().hex)))

    def test_rd7_rule_and_passage_named_apart(self):
        self.prove("rd7_ground", observe_reader_check, check_reader_check,
                   lambda: patch.object(pr, "GROUND_AT_PASSAGE", "Grounded in %s at %s."))

    def test_rd8_evidence_in_words(self):
        self.prove("rd8_evidence", observe_reader_check, check_reader_check,
                   lambda: patch.object(amendment_render, "evidence_sentence", lambda a, **k: ""))

    def test_rd9_relations_in_words(self):
        self.prove("rd9_relations", observe_reader_check, check_reader_check,
                   lambda: patch.object(finding_record, "relation_words", lambda rel, verdict="irregular", **k: str(rel)))

    def test_rd11_reference_index_records_citations(self):
        import reference_builder
        self.prove("rd11_cited_by", observe_reader_check, check_reader_check,
                   lambda: patch.object(reference_builder.ReferenceIndex, "cite", lambda self, ref, agent: None))

    def test_rd12_rd16_rule_book_named_and_quoted(self):
        self.prove("rd12_rules", observe_reader_check, check_reader_check,
                   lambda: patch.object(summary_generators, "RULES_APPLIED_HEADING",
                                        "## What the reference corpus establishes about this document's topics"))

    def test_rd13_every_registered_agent(self):
        import agent_activation
        self.prove("rd13_agents", observe_reader_check, check_reader_check,
                   lambda: patch.object(agent_activation, "initialize", lambda *a, **k: None))

    def test_rd14_absence_is_checked_not_computed(self):
        self.prove("rd14_absence_mark", observe_reader_check, check_reader_check,
                   lambda: patch.object(finding_record, "CHECKED_ABSENCE_MARK", finding_record.COMPUTED_FINDING_MARK))

    def test_rd18_figures_as_written_and_flagged_title(self):
        self.prove("rd18_written", observe_reader_check, check_reader_check,
                   lambda: patch.object(pr, "_written", lambda value, tokens: None))

    # S2 checker round 1: each mechanism, neutralised alone, must fail the check.
    def test_a4_a5_model_items_kept_out_of_the_prior_and_band_sections(self):
        self.prove("a4_a5_prior", observe_prior_sections, check_prior_sections,
                   lambda: patch.object(finding_record, "stamp_written_by",
                                        lambda results, items: [dict(i, written_by="python") if isinstance(i, dict)
                                                                else i for i in items or []]))

    def test_a8_unplaced_unit_cites_nothing_of_another(self):
        self.prove("a8_unplaced", observe_unplaced, check_unplaced,
                   lambda: patch.object(pr, "unit_ref_for", lambda doc, unit_id: pr._NO_UNIT_REF))

    def test_a8_heading_matched_as_a_whole_line(self):
        self.prove("a8_heading", observe_heading_match, check_heading_match,
                   lambda: patch.object(pr, "opens_with", lambda passage, head: head in passage))

    def test_s2a7_model_only_relations_listed_apart(self):
        self.prove("s2a7_relations", observe_relations, check_relations,
                   lambda: patch.object(finding_record, "is_model_written", lambda item: False))


def check():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HonestOutputChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:160]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    ran = result.testsRun - len(result.skipped)
    console = ("the console in en and tr" if not result.skipped
               else "NOT the console (" + CONSOLE_SKIPPED + ")")
    return "PASS", ("%d S2a proofs, each neutralise, fail, restore, pass: model findings marked in "
                    "the markdown deliverables, review_data.json, the server's records and %s; "
                    "producer sentence from the run, tr catalog, plain templates, absence location, "
                    "audit-synthesis count, model-only relations apart, model items kept out of the "
                    "prior-comparison and band sections, unplaced units cite nothing of another's, "
                    "and the reader-check rounds 1 and 2 items" % (ran, console))


def write_mocked_deliverables(target):
    """Write one mocked run's deliverables (English and tr) under `target`."""
    from message_bus import MessageBus
    target = Path(target)
    for language in ("en", "tr"):
        run = mocked_run(target / language, language=language)
        ctx = run["ctx"]
        bus = MessageBus.open(ctx.bus_path())
        # Three distinct escalations on one topic (a real pattern) and two
        # content-free copies (counted apart, never a pattern).
        post_escalations(bus, distinct=3, copies=2)
        audit_synthesizer.AuditSynthesizer(project_root=target / language, bus=bus,
                                           run_context=ctx).synthesize()
        print(language, run["run_dir"])


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--write":
        write_mocked_deliverables(sys.argv[2])
    else:
        status, detail = check()
        print(status, detail)
        sys.exit(0 if status == "PASS" else 1)
