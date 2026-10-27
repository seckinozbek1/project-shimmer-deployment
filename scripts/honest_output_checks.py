"""Gate checks for S2a (honest deliverables), points 1 to 7.

Every proof runs the REAL writers on a mocked run: the real phase-6 synthesis,
the real run-summary writer, the real audit synthesizer, the server's own
findings reader (its function definitions, executed without starting the app)
and the console's own marking function (executed under Node, as the shipped
localization checks do). No model, provider, network or GPU is touched: the
computed findings are minted by paired_review.finding_from_check, the model's
findings are authored envelopes posted under a model backend, and the phase-6
wrapper factory is replaced by a function that refuses to build a wrapper.

Each point is proven by neutralise, fail, restore, pass (effect_proof).

    py -3.12 -X utf8 scripts/honest_output_checks.py                # run the proofs
    py -3.12 -X utf8 scripts/honest_output_checks.py --write DIR    # write one mocked
                                                                    # run's deliverables
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
            "## Entry Beta\n\nSample identifier: S-BETA\nReading: 4 units\nLine total: 9 kg\n\n"
            "## Entry Gamma\n\nReading: 12 units\n")
RULES = [
    {"id": "CONV-001", "category": "conv-h01", "severity": "required",
     "rule": "A reading must not exceed the upper bound recorded for its batch."},
    {"id": "CONV-002", "category": "conv-h02", "severity": "required",
     "rule": "Every entry must state its sample identifier."},
    {"id": "CONV-003", "category": "conv-h03", "severity": "required",
     "rule": "Line totals must equal the sum of the line weights."},
]
GARBLED = ("against the range against", "values against a stated", " gives ",
           "against a stated range")


def _unit(units, slug):
    return next(u for u in units if slug in u)


def computed_findings(doc_id="batch_sheet", text=DOC_TEXT):
    """Typed findings minted by the real Python path, one per relation family."""
    units = pr.unit_texts_for(text, doc_id)
    alpha, beta, gamma = (_unit(units, s) for s in ("entry-alpha", "entry-beta", "entry-gamma"))
    band = {"relation": "above_band", "computed": 61.0, "computed_unit": "units", "stated": None,
            "stated_unit": "units", "band_low": 10.0, "band_high": 60.0, "agrees": False,
            "basis": "reading against the range against the matched row in the reference corpus",
            "stated_field": "reading", "ref_id": "REF-0001"}
    total = {"relation": "sum_mismatch", "computed": 8.0, "computed_unit": "kg", "stated": 9.0,
             "stated_unit": "kg", "agrees": False, "basis": "sum of 2 values under line weight",
             "stated_field": "line total"}
    absent = pr._absence_check(("sample", "identifier"))
    return [
        pr.finding_from_check(unit_id=alpha, rule=RULES[0], check=band, source_rule_id="CONV-H01",
                              refs=["REF-0002"]),
        pr.finding_from_check(unit_id=beta, rule=RULES[2], check=total, source_rule_id="CONV-H03",
                              refs=["REF-0002"]),
        dict(pr.finding_from_check(unit_id=gamma, rule=RULES[1], check=absent, source_rule_id="CONV-H02",
                                   refs=["REF-0002"]), absence_path="computed"),
    ]


def model_finding(doc_id="batch_sheet"):
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


def mocked_run(out_root, *, style_guardian=True, index_unit_passages=True, language="en"):
    """One mocked run through the real phase 6 and run summary. Returns a dict
    with the run folder, the deliverables map and the captured run-log events."""
    import pipeline as pl
    import reference_builder as rb
    import run_options
    from harness.run_agent import build_orchestrator
    doc = {"id": "batch_sheet", "name": "batch_sheet.md", "text": DOC_TEXT}
    registry = {"conventions": RULES}
    envelopes = [{"scope": "doc", "doc_id": doc["id"], "agent": "PRACTICE_AUDITOR", "ok": True,
                  "backend": "paired", "model": "python+model",
                  "parsed": {"agent": "PRACTICE_AUDITOR", "doc_id": doc["id"], "items": computed_findings()}}]
    if style_guardian:
        envelopes.append({"scope": "doc", "doc_id": doc["id"], "agent": "STYLE_GUARDIAN", "ok": True,
                          "backend": "local_auditor", "model": "fixture-auditor", "call_id": "fixture-call-1",
                          "parsed": {"agent": "STYLE_GUARDIAN", "doc_id": doc["id"], "items": [model_finding()]}})
    out_root = Path(out_root)
    orch = build_orchestrator(root=ROOT, out_root=out_root)
    run_options.configure(orch.run_context, "auto", language, "enabled")
    index = rb.ReferenceIndex.open(ROOT, index_path=out_root / "refs.json")
    index.add(input_type="context", document_id="reference", document_name="reference.md",
              location={"page": 1}, text_excerpt="Upper bound for batch B-7: 60 units.")
    index.add(input_type="operational", document_id=doc["id"], document_name=doc["name"],
              location={"page": 1, "paragraph": 1}, text_excerpt="# Returned batch sheet Batch: B-7. Readings for review.")
    if index_unit_passages:
        for heading in ("## Entry Alpha", "## Entry Beta", "## Entry Gamma"):
            body = DOC_TEXT.split(heading, 1)[1].split("\n## ", 1)[0]
            index.add(input_type="operational", document_id=doc["id"], document_name=doc["name"],
                      location={"page": 1}, text_excerpt=heading + body)
    index.save()
    # The envelopes reach the bus the way phase 5.5 posts them: under each one's
    # own backend and model (paired/python for Python's records, the model's own
    # backend for a model reply), through the real wrapper method.
    with contextlib.redirect_stderr(io.StringIO()):
        for env in envelopes:
            pl._build_wrapper(env["agent"], orch, {}).post_to_bus(
                recipient="ORCHESTRATOR", channel="main", msg_type="INFORM",
                body={"event": "AGENT_OUTPUT", "backend": env["backend"], "model": env["model"],
                      "payload": env["parsed"]},
                constitution_check={"laws_consulted": ["LAW-V"], "result": "RESOLVED"})
    capture = _Capture()
    logger = logging.getLogger("shimmer.pipeline")
    logger.addHandler(capture)
    try:
        with patch.object(pl, "_build_wrapper", side_effect=AssertionError("no model wrapper in this proof")), \
                contextlib.redirect_stderr(io.StringIO()):
            deliverables = asyncio.run(pl.phase_6_synthesis(
                orch, {}, [doc], [], [], envelopes, "declared proof", registry, index,
                embed_store=None, max_concurrent_docs=1))
            pl.write_deliverables_run_summary(orch.run_context.deliverables_dir(), [doc], deliverables,
                                              total_cost_usd=0.0, task="review")
    finally:
        logger.removeHandler(capture)
    run_dir = orch.run_context.run_dir
    return {"run_dir": run_dir, "ctx": orch.run_context, "deliverables": deliverables, "doc": doc,
            "events": capture.events,
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
    return [ln for ln in text.splitlines() if "sum_mismatch" in ln and unit_id in ln]


# ---------- observations (each executes the real consumer; no verdicts) -----------------

def observe_marks():
    mark = finding_record.MODEL_FINDING_MARK
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_marks_") as td:
        run = mocked_run(td)
        unit = model_finding()["unit_id"]
        files = {name: _read(path) for name, path in run["files"].items()}
        master = json.loads(files["review_data.json"])
        records = server_findings(run["run_dir"])
        console = console_marks(records)
        return {
            "document_summary": all(mark in ln for ln in _model_lines(files["document_summary.md"], unit))
                                and bool(_model_lines(files["document_summary.md"], unit)),
            "reviewed_document": any(mark in ln for ln in _model_lines(files["reviewed_document.md"], unit)),
            "review_findings": mark in files["review_findings.md"]
                               and any(mark in ln for ln in _model_lines(files["review_findings.md"], unit)),
            "master_model_findings": [f.get("unit_id") for f in master.get("model_findings_not_promoted", [])],
            "master_amendment_pairs": sorted("%s|%s|%s" % (a["finding_unit_id"], a["finding_rule_id"],
                                                          a.get("finding_value_a")) for a in master["amendments"]),
            "run_summary": mark in _read(run["run_summary"]),
            "server_written_by": sorted({(r["relation"], r.get("written_by")) for r in records}),
            "console_model_marked": None if console is None else [bool(b) and mark in b for b, a in console],
        }


def check_marks():
    o = observe_marks()
    unit = model_finding()["unit_id"]
    ok = (o["document_summary"] and o["reviewed_document"] and o["review_findings"] and o["run_summary"]
          and o["master_model_findings"] == [unit]
          and "%s|CONV-003|4" % unit not in o["master_amendment_pairs"]
          and ("sum_mismatch", "model") in o["server_written_by"]
          and ("above_band", "python") in o["server_written_by"]
          and (o["console_model_marked"] is None or True in o["console_model_marked"]))
    return ("PASS" if ok else "FAIL", "model finding marked in every reader-facing file")


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
          and "3 computed by Python" in a["sentence"] and "0 written by a model (no model agent)" in a["sentence"]
          and a["log"] == "findings_provenance computed=3 model=0 model_agents=none"
          and "1 written by a model (STYLE_GUARDIAN)" in b["sentence"] and "STYLE_GUARDIAN" in b["body"]
          and b["log"] == "findings_provenance computed=3 model=1 model_agents=STYLE_GUARDIAN"
          and not b["names_practice_auditor"])
    # S2a-3 inside S2a-2: the Turkish rendering of both generated sentences.
    for row in (a, b):
        ok = ok and row["tr_sentence"] != row["sentence"] and "computed by Python" not in row["tr_sentence"]
        ok = ok and row["tr_body"] != row["body"] and "computed by Python" not in row["tr_body"]
    ok = ok and "model ajanı yok" in a["tr_sentence"]
    return ("PASS" if ok else "FAIL", "producer sentence generated from the run")


# Every English sentence this stage writes that a Turkish reader also receives.
def _localized_samples():
    prov_none = summary_generators.findings_provenance([])
    prov = {"total": 2, "computed": 1, "model": 1, "model_agents": ["STYLE_GUARDIAN"]}
    texts = [summary_generators.context_findings_sentence(3, prov_none, "x.md"),
             summary_generators.context_findings_sentence(3, prov, "x.md"),
             summary_generators.operative_findings_sentence(prov),
             finding_record.MODEL_FINDING_MARK, finding_record.COMPUTED_FINDING_MARK,
             amendment_render.MODEL_FINDINGS_HEADING, summary_generators.RELATIONS_FOUND_HEADING,
             summary_generators.RELATIONS_MODEL_HEADING, audit_synthesizer.AUDIT_COUNT_NOTE,
             "## Audit-trail patterns (not document findings)", "- audit-trail patterns: "]
    return texts + [a["comment"] for a in template_amendments()]


def observe_catalog():
    return [{"en": t, "tr": loc.message(t, "tr")} for t in _localized_samples()]


def check_catalog():
    rows = observe_catalog()
    english = ("computed by Python", "written by a model", "Computed in code", "Grounded in",
               "under rule", "Not promoted", "Relations found", "audit-trail", "Model findings")
    ok = all(r["tr"] != r["en"] and not any(w in r["tr"] for w in english) for r in rows)
    return ("PASS" if ok else "FAIL", "%d Turkish renderings" % len(rows))


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
        dict(base, relation="product_mismatch", computed=20.0, computed_unit="EUR", stated=25.0, stated_unit="EUR",
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
        lead = amendment["comment"].split(". Computed in code")[0]
        out.append({"relation": item["relation"], "lead": lead, "explanation": item["explanation"],
                    "comment": amendment["comment"], "tr": loc.message(amendment["comment"], "tr")})
    return out


def check_templates():
    rows = observe_templates()
    bad = []
    for item, row in zip(template_cases(), rows):
        lead = row["lead"]
        need = [item["unit_id"], "CONV-001 (CONV-H01)"]
        relation, unit_b = item["relation"], item.get("unit_b")
        if relation == "licence_missing":
            need.append("a reference the rule requires is not present")
        elif unit_b == "required":            # a declared field the unit does not state
            need += ["'%s'" % item["field_label"], "is not stated in this unit"]
        elif unit_b == "rows":                # a column filled in fewer rows than the table has
            need += ["'%s'" % item["field_label"], "%s of %s rows" % (item["value_a"], item["value_b"])]
        else:                                 # two figures, each with its unit, and the relation
            fig = lambda v, u: ("%s %s" % (v, u)) if u not in ("1", None) else str(v)
            need += [fig(item["value_a"], item.get("unit_a")), fig(item["value_b"], unit_b)]
            need.append({"above_band": "above the upper bound", "below_band": "below the lower bound",
                         "ratio_out_of_range": "outside the permitted bound", "sum_mismatch": "add up to",
                         "product_mismatch": "multiply to", "date_window": "longer than the allowed"}[relation])
        sentences = [s for s in re.split(r"(?<=[a-z0-9'])\. (?=[A-Z])", lead + ".") if s.strip()]
        if (not all(n in lead for n in need) or any(g in row["comment"] for g in GARBLED)
                or len(sentences) > 2 or row["explanation"] != lead + "."
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
                         "sentences": ["The location is the passage of unit" in a["comment"] for a in absent],
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


def observe_audit_synthesis():
    from message_bus import MessageBus
    from run_context import RunContext
    with tempfile.TemporaryDirectory(prefix="shimmer_honest_audit_") as td:
        ctx = RunContext(project_root=Path(td), run_id="auditfixture", run_dir=Path(td) / "run")
        ctx.ensure()
        bus = MessageBus.open(ctx.bus_path())
        for _ in range(3):
            bus.post({"sender": "ORCHESTRATOR", "sender_role": "orchestrator", "recipient": "OPERATOR",
                      "channel": "escalation", "type": "ESCALATE", "body": {"topic": "TOPIC-1"},
                      "constitution_check": {"laws_consulted": ["LAW-V"], "result": "RESOLVED"}})
        audit_synthesizer.AuditSynthesizer(project_root=Path(td), bus=bus, run_context=ctx).synthesize()
        text = _read(ctx.audit_synthesis_path())
        tr = audit_synthesizer._render_md(dict(generated_at="x", bus_messages=3, delta_proposals=[],
                                               findings=[dict(severity="high", category="governance",
                                                              summary="escalation topic 'TOPIC-1' recurred 3 times")]),
                                          output_language="tr")
        return {"count_line": next((ln for ln in text.splitlines() if "patterns" in ln and ln.startswith("- ")), ""),
                "says_not_document": "not findings about the document under review" in text,
                "old_label": "- findings: " in text, "heading": "## Audit-trail patterns (not document findings)" in text,
                "tr_says_not_document": "belge hakkındaki bulgular değildir" in tr}


def check_audit_synthesis():
    o = observe_audit_synthesis()
    ok = (o["count_line"].startswith("- audit-trail patterns: 1 (") and o["says_not_document"]
          and not o["old_label"] and o["heading"] and o["tr_says_not_document"])
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
        return {"found_section": sorted(set(re.findall(r"- (\w+): \d", found))),
                "model_section": sorted(set(re.findall(r"- (\w+): \d", model))),
                "model_marked": finding_record.MODEL_FINDING_MARK in model,
                "scorer_found": next((ln for ln in lines if ln.startswith("relations found")), ""),
                "scorer_model": next((ln for ln in lines if ln.startswith("model-only")), ""),
                "scorer_confirmed": confirmed.getvalue().splitlines()[0] if confirmed.getvalue() else ""}


def check_relations():
    o = observe_relations()
    ok = (o["found_section"] == ["above_band", "missing_field", "sum_mismatch"]
          and o["model_section"] == ["sum_mismatch"] and o["model_marked"]
          and o["scorer_found"] == "relations found : above_band=1, missing_field=1, sum_mismatch=1"
          and "sum_mismatch=1" in o["scorer_model"]
          and o["scorer_confirmed"] == "relations found : above_band=1, missing_field=1, sum_mismatch=2")
    return ("PASS" if ok else "FAIL", "model-only relations listed apart")


# ---------- the proofs ---------------------------------------------------------------------

def _old_relation_clause(item):
    return "%s against the range against the matched row gives %s %s" % (
        item.get("field_label"), item.get("value_a"), item.get("unit_a"))


def _old_context_sentence(n, provenance, name):
    return ("This document was reviewed against %d conventions. %d findings were produced by "
            "PRACTICE_AUDITOR and STYLE_GUARDIAN. The context references below are filtered for "
            "topical relevance to %s." % (n, provenance["total"], name))


class _CatalogWithout:
    """The catalog with this stage's Turkish rows removed (the neutralisation)."""

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

    def test_s2a2_producer_sentence_from_the_run(self):
        self.prove("s2a2_producer", observe_producer, check_producer,
                   lambda: patch.object(summary_generators, "context_findings_sentence", _old_context_sentence))

    def test_s2a3_turkish_catalog_covers_every_new_sentence(self):
        self.prove("s2a3_catalog", observe_catalog, check_catalog, _CatalogWithout)

    def test_s2a4_templates_read_as_plain_english(self):
        self.prove("s2a4_templates", observe_templates, check_templates,
                   lambda: patch.object(pr, "relation_clause", _old_relation_clause))

    def test_s2a5_absence_points_to_its_unit(self):
        self.prove("s2a5_absence", observe_absence_location, check_absence_location,
                   lambda: patch.object(pr, "ABSENCE_RELATIONS", ()))

    def test_s2a6_audit_synthesis_says_what_it_counts(self):
        self.prove("s2a6_audit", observe_audit_synthesis, check_audit_synthesis,
                   lambda: patch.object(audit_synthesizer, "AUDIT_COUNT_NOTE", ""))

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
    return "PASS", ("%d S2a proofs, each neutralise, fail, restore, pass: model findings marked in "
                    "every reader-facing file and the console, producer sentence from the run, "
                    "Turkish catalog, plain templates, absence location, audit-synthesis count, "
                    "model-only relations apart" % result.testsRun)


def write_mocked_deliverables(target):
    """Write one mocked run's deliverables (English and Turkish) under `target`."""
    from message_bus import MessageBus
    target = Path(target)
    for language in ("en", "tr"):
        run = mocked_run(target / language, language=language)
        ctx = run["ctx"]
        bus = MessageBus.open(ctx.bus_path())
        for _ in range(3):   # one audit-trail pattern, so the count line has something to count
            bus.post({"sender": "ORCHESTRATOR", "sender_role": "orchestrator", "recipient": "OPERATOR",
                      "channel": "escalation", "type": "ESCALATE", "body": {"topic": "TOPIC-1"},
                      "constitution_check": {"laws_consulted": ["LAW-V"], "result": "RESOLVED"}})
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
