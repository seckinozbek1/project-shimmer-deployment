"""Gate checks for S2b items 3 to 6 (multi-round enablement, pipeline lane).

No model, provider, network or GPU. The multi-round case phase runs for real
(multi_round_phase.execute with the pipeline's own wrapper factory,
pipeline._build_wrapper), and the model boundary is replaced below run_task by the
same stand-ins check 276 uses (reply_records_checks.backends): run_task, call_local
and the reply-record writer all execute. The case material is a declared two-round
fixture written here; its replies are authored, labelled as such, and measure
nothing about model quality.

Each item is proven by neutralise, fail, restore, pass (effect_proof). The S2
checker round 1 items add: each signature input (a rule, a vocabulary label, a
known unit) proven to matter by removing it from SIGNATURE_INPUTS; reused model
asks rebased; the production convention-parse path run once on a temporary
project root; the round findings on the bus; a renamed figure with no unit.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import uuid
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import multi_round as mr
import multi_round_rounds as rounds
import paired_review as pr
import pairing_map as pm
import reply_records

ROOT = Path(__file__).resolve().parent.parent

RULES = [{"id": "CONV-001", "category": "conv-m01", "severity": "required",
          "rule": "A reading must lie between 10 units and 60 units."}]


def round_text(beta):
    return ("## Entry Alpha\n\nReading: 61 units\n\n"
            "## Entry Beta\n\nReading: %s units\n\n"
            "## Entry Gamma\n\nReading: 5 units\n" % beta)


def documents(beta_r2=70):
    return [{"id": "case_r1", "name": "case_r1.md", "text": round_text(40)},
            {"id": "case_r2", "name": "case_r2.md", "text": round_text(beta_r2)}]


def manifest(docs):
    sources = []
    for rnd, doc in (("r1", docs[0]), ("r2", docs[1])):
        quote = "Reading: 61 units"
        start = doc["text"].index(quote)
        sources.append({"source_id": "s_" + rnd, "round_id": rnd, "actor_id": "actor_a", "issue_id": "issue_a",
                        "document_id": doc["id"], "unit_id": "u01-entry-alpha", "char_start": start,
                        "char_end": start + len(quote), "quote": quote, "state": "accepted"})
    return {"schema_version": 1, "case_id": "declared_case", "fixture": False,
            "rounds": [{"round_id": "r1", "sequence": 1, "document_ids": [docs[0]["id"]]},
                       {"round_id": "r2", "sequence": 2, "document_ids": [docs[1]["id"]]}],
            "actors": [{"actor_id": "actor_a"}], "issues": [{"issue_id": "issue_a"}], "sources": sources}


def authored_replies(case_id="declared_case"):
    """PRE-AUTHORED REPLIES, NOT MODEL OUTPUT: the strategic layer's two calls on a
    strategic_options request, one option resting on the computed movement."""
    movement = "movement.r1.r2.actor_a.issue_a"
    proposals = [{"record_id": "option_a", "type": "STRATEGIC_OPTION", "state": "accepted",
                  "confidence": "UNCERTAIN", "action": "declared", "upside": "declared", "risk": "declared",
                  "uncertainty": "declared", "assumptions": ["declared"], "source_ids": ["s_r1", "s_r2"],
                  "interpretation_ids": [movement], "trajectory_ids": [movement], "actor_ids": ["actor_a"],
                  "issue_ids": ["issue_a"], "round_ids": ["r1", "r2"], "option_ids": [],
                  "ref": "option_a", "kind": "finding"}]
    decisions = [{"target_record_id": "option_a", "state": "accepted", "confidence": "UNCERTAIN",
                  "source_ids": ["s_r1", "s_r2"], "ref": "option_a", "kind": "review"}]
    return (json.dumps({"agent": "PROCESSOR", "doc_id": case_id, "items": proposals}),
            json.dumps({"agent": "VERIFIER", "doc_id": case_id, "items": decisions}))


# Open item 35: what the stand-in local backend returns if the case phase asks it
# anything. Shaped as L6m's capped reply was: the instructions echoed back, no
# envelope. PRE-AUTHORED, NOT MODEL OUTPUT.
CAPPED_REPLY = ("Do not repeat adjacent deliverables or adopt their conclusions; preserve competing "
                "interpretations and identify missing evidence. " * 40)
# The factory of the latest mocked run, for the neutralisation that restores a
# model call in the case phase (_records_from_processor).
_FACTORY = []


def mocked_multi_round_run(out_root, *, beta_r2=70, plan_spy=None, replies=None, seen=None,
                           case_manifest=None, registry_overrides=None, **phase_arguments):
    """The real case phase, the pipeline's own wrapper factory, stand-in backends."""
    import pipeline as pl
    from harness.run_agent import build_orchestrator
    from reference_builder import ReferenceIndex
    from reply_records_checks import backends
    registry = json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    registry = dict(registry)
    registry["PROCESSOR"] = dict(registry["PROCESSOR"], backend="local_producer", model="fixture-producer")
    registry["VERIFIER"] = dict(registry["VERIFIER"], backend="local_auditor", model="fixture-auditor")
    for name, (backend, model) in (registry_overrides or {}).items():
        registry[name] = dict(registry[name], backend=backend, model=model)
    orch = build_orchestrator(root=ROOT, out_root=Path(out_root), registry=registry)
    ctx = orch.run_context
    docs = documents(beta_r2)
    record = mr.begin(ctx, case_manifest or manifest(docs))
    refs = ReferenceIndex.open(ROOT, index_path=ctx.reference_index_path())
    if replies is None:
        replies = [CAPPED_REPLY, CAPPED_REPLY]
    import multi_round_phase
    real_plan_calls = pr.plan_calls

    def spy(units, pairs, *args, **kwargs):
        if plan_spy is not None:
            plan_spy.append(sorted({u for u, _ in pairs}))
        return real_plan_calls(units, pairs, *args, **kwargs)

    def factory(name):
        return pl._build_wrapper(name, orch, {})
    _FACTORY[:] = [factory]
    with backends(local=replies, seen=seen), patch.object(pr, "plan_calls", spy), \
            contextlib.redirect_stderr(io.StringIO()):
        code = multi_round_phase.execute(ctx, record, docs, refs, factory,
                                         sensitive=False, convention_registry={"conventions": RULES},
                                         **phase_arguments)
    return {"code": code, "record": record, "ctx": ctx, "run_dir": ctx.run_dir}


# ---------- observations ------------------------------------------------------------------

def _round_posts(run_dir):
    """S2 checker H4: the round findings as the run bus carries them."""
    import finding_record
    bus = Path(run_dir) / "logs" / "agent_bus.jsonl"
    out = []
    lines = bus.read_text(encoding="utf-8").splitlines() if bus.is_file() else []
    for line in lines:
        msg = json.loads(line)
        body = msg.get("body") or {}
        if msg.get("channel") != "multi_round" or body.get("event") != "AGENT_OUTPUT":
            continue
        payload = body.get("payload") or {}
        if payload.get("agent") != rounds.FINDINGS_AGENT:
            continue  # the case phase's own PROCESSOR and VERIFIER outputs
        items = payload.get("items") or []
        out.append((payload.get("doc_id"), finding_record.written_by(body.get("backend"), body.get("model")),
                    sorted((i.get("unit_id"), i.get("relation")) for i in items),
                    len({i.get("item_id") for i in items}) == len(items)))
    return out


def observe_reuse():
    spy = []
    with tempfile.TemporaryDirectory(prefix="shimmer_rounds_reuse_") as td:
        run = mocked_multi_round_run(td, plan_spy=spy)
        saved = rounds.read(run["run_dir"]) or {}
        out = {"code": run["code"], "outcome": run["record"].get("outcome"),
               "round_review": run["record"].get("round_review"), "plan_units": spy, "rounds": [],
               "bus": _round_posts(run["run_dir"])}
        for rnd in saved.get("rounds", []):
            doc = rnd["documents"][0]
            out["rounds"].append({
                "round_id": rnd["round_id"],
                "status": {u["unit_id"]: u["status"] for u in doc["units"]},
                "reused_from": {u["unit_id"]: (u.get("reused_from") or {}).get("round_id") for u in doc["units"]},
                "pairs_computed": doc["pairs_computed"],
                "findings": sorted((f["unit_id"], f["relation"], f.get("value_a")) for f in doc["findings"])})
        return out


def check_reuse():
    o = observe_reuse()
    if len(o["rounds"]) != 2 or o["code"] != 0:
        return "FAIL", "case phase did not record two rounds"
    r1, r2 = o["rounds"]
    ok = (set(r1["status"].values()) == {"computed"}
          and r2["status"] == {"u01-entry-alpha": "reused", "u02-entry-beta": "computed", "u03-entry-gamma": "reused"}
          and r2["reused_from"]["u01-entry-alpha"] == "r1" and r2["reused_from"]["u03-entry-gamma"] == "r1"
          and o["plan_units"] == [["u01-entry-alpha", "u02-entry-beta", "u03-entry-gamma"], ["u02-entry-beta"]]
          and r2["pairs_computed"] == 1 and r1["pairs_computed"] == 3
          and r2["findings"] == [("u01-entry-alpha", "above_band", 61.0), ("u02-entry-beta", "above_band", 70.0),
                                 ("u03-entry-gamma", "below_band", 5.0)]
          and r1["findings"] == [("u01-entry-alpha", "above_band", 61.0), ("u03-entry-gamma", "below_band", 5.0)]
          and o["round_review"] == {"record": "audit/round_reuse.json", "availability": "recorded",
                                    "bus_envelopes": 2}
          # H4: every round document's findings are on the bus, written by Python,
          # each with its own item id so no round supersedes another.
          and o["bus"] == [("case_r1", "python", [("u01-entry-alpha", "above_band"),
                                                  ("u03-entry-gamma", "below_band")], True),
                           ("case_r2", "python", [("u01-entry-alpha", "above_band"),
                                                  ("u02-entry-beta", "above_band"),
                                                  ("u03-entry-gamma", "below_band")], True)])
    return ("PASS" if ok else "FAIL", "only the changed unit's pairs recomputed in round 2; findings on the bus")


# ---------- S2 checker A10: what the signature covers, the parse path, needs_model --------

RULE_CHANGED = dict(RULES[0], rule="A reading must lie between 10 units and 65 units.")
SCOPED_RULE = {"id": "CONV-002", "category": "conv-m02", "severity": "required",
               "rule": "[scope: reading] Each entry must say how the reading was taken."}


def signature_text(*, extra="", gamma_unit="units", lead=""):
    return (lead + "## Entry Alpha\n\nReading: 61 units\n\n"
            "## Entry Beta\n\nReading: 40 units\n%s\n"
            "## Entry Gamma\n\nReading: 5 %s\n" % (extra, gamma_unit))


def _second_round(text_r2, *, rules_r1=None, rules_r2=None):
    """Round 1 on the base text, round 2 on `text_r2`, one shared reuse table."""
    earlier = {}
    rules_r1 = rules_r1 or RULES
    rounds.review_document({"id": "d1", "text": signature_text()}, rules_r1, earlier, round_id="r1")
    rows, _, _ = rounds.review_document({"id": "d2", "text": text_r2}, rules_r2 or rules_r1, earlier,
                                        round_id="r2")
    return rows


# Open item 35 (L6m round 3): a rule whose pairing is its DECLARED scope, so a label
# its text names can change without changing which units it pairs with. The
# vocabulary reaches a unit's computation only through such named labels.
SCOPED_DECLARED = dict(SCOPED_RULE, scope=["reading"])
NAMED_LABEL = "Entry taken: 3 units\n"      # words the scoped rule's text holds
UNNAMED_LABEL = "Batch note: 3 units\n"     # words no paired rule's text holds


def _findings(rows_and_found):
    return sorted(json.dumps(f, sort_keys=True, default=str) for f in rows_and_found)


def observe_signature():
    """Round 2 status of Entry Alpha, whose own text never changes."""
    def alpha(rows):
        return next(r["status"] for r in rows if r["unit_id"].endswith("entry-alpha"))
    scoped = RULES + [SCOPED_DECLARED]
    # The unnamed label's round 2 with reuse against the same round computed fresh.
    earlier = {}
    rounds.review_document({"id": "d1", "text": signature_text()}, scoped, earlier, round_id="r1")
    _, reused, _ = rounds.review_document({"id": "d2", "text": signature_text(extra=UNNAMED_LABEL)},
                                          scoped, earlier, round_id="r2")
    _, fresh, _ = rounds.review_document({"id": "d2", "text": signature_text(extra=UNNAMED_LABEL)},
                                         scoped, {}, round_id="r2")
    return {"unchanged": alpha(_second_round(signature_text())),
            "rule": alpha(_second_round(signature_text(), rules_r2=[RULE_CHANGED])),
            "vocabulary": alpha(_second_round(signature_text(extra=NAMED_LABEL), rules_r1=scoped)),
            "vocabulary_unnamed": alpha(_second_round(signature_text(extra=UNNAMED_LABEL), rules_r1=scoped)),
            "unnamed_reuse_equals_fresh": _findings(reused) == _findings(fresh) and bool(fresh),
            "known_units": alpha(_second_round(signature_text(gamma_unit="kg")))}


def check_signature():
    o = observe_signature()
    ok = o == {"unchanged": "reused", "rule": "computed", "vocabulary": "computed",
               "vocabulary_unnamed": "reused", "unnamed_reuse_equals_fresh": True,
               "known_units": "computed"}
    return ("PASS" if ok else "FAIL", "a changed rule, a label a paired rule names, or a known unit recomputes "
                                      "an unchanged unit; a label no paired rule names does not, and the reuse "
                                      "equals a fresh computation")


def _whole_vocabulary(rules, vocabulary):
    """Neutralisation: the signature covers the document's whole vocabulary, as
    before open item 35."""
    return sorted(" ".join(label) for label in vocabulary)


def observe_moved_asks():
    """A unit inserted before the others moves every id; the reused rows' model asks follow."""
    rows = _second_round(signature_text(lead="## Entry Zero\n\nReading: 30 units\n\n"),
                         rules_r1=RULES + [SCOPED_RULE])
    return [(r["unit_id"], r["status"], sorted({n["unit_id"] for n in r.get("needs_model") or []}))
            for r in rows]


def check_moved_asks():
    o = observe_moved_asks()
    reused = [r for r in o if r[1] == "reused"]
    ok = len(reused) == 3 and all(ids == [unit_id] for unit_id, _, ids in reused)
    return ("PASS" if ok else "FAIL", "a reused unit's model asks name this round's unit id")


class _Ctx:
    """The two things review_rounds reads from a run context."""

    def __init__(self, root):
        self.project_root = root

    def audit_dir(self):
        return Path(self.project_root) / "audit"


CONVENTIONS_MD = ("# Review conventions\n\n## CONV-M01 Reading range [required]\n\n"
                  "A reading must lie between 10 units and 60 units.\n")


def observe_parse():
    """The production path: no registry passed, so the round review compiles the
    operator's conventions from input/conventions under the run's project root."""
    with tempfile.TemporaryDirectory(prefix="shimmer_rounds_parse_") as td:
        conv = Path(td) / "input" / "conventions"
        conv.mkdir(parents=True)
        (conv / "review_conventions.md").write_text(CONVENTIONS_MD, encoding="utf-8")
        docs = documents()
        rec = rounds.review_rounds(_Ctx(td), manifest(docs), docs)
        return {"availability": rec.get("availability"),
                "rounds": [([u["status"] for u in r["documents"][0]["units"]],
                            sorted((f["unit_id"], f["relation"]) for f in r["documents"][0]["findings"]))
                           for r in rec.get("rounds", [])]}


def check_parse():
    o = observe_parse()
    ok = (o["availability"] == "recorded"
          and o["rounds"] == [(["computed"] * 3, [("u01-entry-alpha", "above_band"), ("u03-entry-gamma", "below_band")]),
                              (["reused", "computed", "reused"],
                               [("u01-entry-alpha", "above_band"), ("u02-entry-beta", "above_band"),
                                ("u03-entry-gamma", "below_band")])])
    return ("PASS" if ok else "FAIL", "with no registry passed, the operator's conventions are compiled and used")


def _without(name):
    return patch.object(rounds, "SIGNATURE_INPUTS", tuple(n for n in rounds.SIGNATURE_INPUTS if n != name))


def observe_replies():
    """The calls the case phase still makes: the strategic layer's, on an explicit
    strategic_options request (open item 35 removed the trajectory calls)."""
    with tempfile.TemporaryDirectory(prefix="shimmer_rounds_replies_") as td:
        docs = documents()
        case = dict(manifest(docs), decision_support_mode="strategic_options")
        run = mocked_multi_round_run(td, replies=list(authored_replies()), case_manifest=case)
        folder = reply_records.folder(run["ctx"])
        rows = reply_records.records(folder)
        current = reply_records.outcomes(folder)
        layer = run["record"].get("strategic_layer") or {}
        items = layer.get("items") or []
        return {"code": run["code"], "outcome": run["record"].get("outcome"),
                "strategic_state": layer.get("state"),
                "records": [(r["agent"], r["backend"], r["phase"], bool(r["reply"] and r["reply"].get("text")))
                            for r in rows],
                "call_ids_unique": len({r["call_id"] for r in rows}) == len(rows),
                "outcomes": [current.get(r["call_id"], "not_decided") for r in rows],
                # The strategic items name the very calls whose replies were saved,
                # and the trajectory records name none.
                "records_name_saved_calls": bool(items) and sorted(
                    {i.get("producer_call_id") for i in items} | {i.get("reviewer_call_id") for i in items})
                    == sorted(r["call_id"] for r in rows),
                "trajectory_names_no_call": all(
                    not any(k.endswith("_call_id") for k in rec) for rec in run["record"]["records"])}


def check_replies():
    o = observe_replies()
    ok = (o["code"] == 0 and o["outcome"] == "reviewed" and o["strategic_state"] == "strategic_options"
          and o["records"] == [("PROCESSOR", "local_producer", "multi_round", True),
                               ("VERIFIER", "local_auditor", "multi_round", True)]
          and o["call_ids_unique"] and o["outcomes"] == ["advisory_not_record"] * 2
          and o["records_name_saved_calls"] and o["trajectory_names_no_call"])
    return ("PASS" if ok else "FAIL", "one saved record per multi-round call, outcome advisory_not_record")


# ---------- open item 35: the case records are computed, no model is asked -------------------

def observe_no_model_call():
    """The real case phase on the declared two-round case, with the stand-in local
    backend holding a capped, envelope-less reply (as L6m's) for any call."""
    seen = {"claude": [], "gpt": [], "local": []}
    with tempfile.TemporaryDirectory(prefix="shimmer_rounds_oi35_") as td:
        run = mocked_multi_round_run(td, replies=[CAPPED_REPLY, CAPPED_REPLY], seen=seen)
        saved = mr.read_saved(run["run_dir"], run["ctx"].run_id)
        bus = Path(run["run_dir"]) / "logs" / "agent_bus.jsonl"
        posts = [json.loads(line)["body"] for line in bus.read_text(encoding="utf-8").splitlines()] \
            if bus.is_file() else []
        reviewed = [(b.get("backend"), b.get("model")) for b in posts if b.get("event") == "MULTI_ROUND_REVIEWED"]
        view = saved.get("view") or {}
        return {"code": run["code"], "outcome": saved.get("outcome"),
                "activated": (saved.get("activation") or {}).get("activated"),
                "reason": (saved.get("activation") or {}).get("reason"),
                "model_sent": sum(len(v) for v in seen.values()),
                "replies_saved": len(reply_records.records(reply_records.folder(run["ctx"]))),
                "records": sorted((r["record_id"], r["state"], r.get("movement"), r.get("value"), r.get("unit"),
                                   r.get("written_by")) for r in run["record"]["records"]),
                "comparisons": [(c["movement_id"], c.get("delta"), c.get("unit"), c["typed_position_equal"])
                                for c in view.get("structural_comparisons", [])],
                "bus": reviewed}


# D-319: one actor, so no computed gap between parties and no figure on a position.
OI35_RECORDS = sorted([
    ("position.r1.actor_a.issue_a", "accepted", None, None, None, "python"),
    ("position.r2.actor_a.issue_a", "accepted", None, None, None, "python"),
    ("movement.r1.r2.actor_a.issue_a", "accepted", "unknown", None, None, "python")])


def check_no_model_call():
    o = observe_no_model_call()
    ok = (o["code"] == 0 and o["outcome"] == "reviewed" and o["activated"] is True and o["reason"] is None
          and o["model_sent"] == 0 and o["replies_saved"] == 0
          and o["records"] == OI35_RECORDS
          and o["comparisons"] == [("movement.r1.r2.actor_a.issue_a", None, None, True)]
          and o["bus"] == [("computed", "python")])
    return ("PASS" if ok else "FAIL", "the case reaches reviewed and activated with records computed in "
                                      "Python and no model call")


# ---------- open item 39: the multi-round run records its own step times ---------------------

def _measured(value):
    return type(value) is float and value >= 0 and value == round(value, 6)


def observe_timings():
    """The real case phase on the declared two-round case. The times themselves vary from
    run to run, so what is observed is their shape: which steps are recorded, that each is a
    non-negative number of seconds rounded to microseconds, that the round record's per-round
    seconds are the ones the timings carry, and that the whole phase covers its steps."""
    with tempfile.TemporaryDirectory(prefix="shimmer_rounds_oi39_") as td:
        run = mocked_multi_round_run(td)
        saved = json.loads(run["ctx"].multi_round_path().read_text(encoding="utf-8"))
        reuse = rounds.read(run["run_dir"]) or {}
    t = saved.get("timings") if isinstance(saved.get("timings"), dict) else {}
    steps = ("round_review", "records", "phase")
    per_round = [(r.get("round_id"), r.get("seconds")) for r in reuse.get("rounds") or []]
    recorded = all(_measured(t.get(k)) for k in steps)
    return {"code": run["code"], "outcome": saved.get("outcome"),
            "records": sorted((r["record_id"], r["state"], r.get("movement"), r.get("value"), r.get("unit"),
                               r.get("written_by")) for r in saved.get("records") or []),
            "fields": sorted(t), "unit": t.get("unit"), "clock": t.get("clock"),
            "steps_measured": recorded,
            "round_ids": [r for r, _ in per_round],
            "rounds_measured": bool(per_round) and all(_measured(v) for _, v in per_round),
            "rounds_match_record": [(r.get("round_id"), r.get("seconds")) for r in t.get("rounds") or []] == per_round,
            "phase_covers_steps": recorded and t["phase"] >= t["round_review"] + t["records"] - 2e-6
            and sum(v for _, v in per_round if _measured(v)) <= t["round_review"] + 2e-6}


def check_timings():
    o = observe_timings()
    ok = (o["code"] == 0 and o["outcome"] == "reviewed" and o["records"] == OI35_RECORDS
          and o["fields"] == ["clock", "phase", "records", "round_review", "rounds", "unit"]
          and o["unit"] == "seconds" and o["clock"] == "time.perf_counter"
          and o["steps_measured"] and o["round_ids"] == ["r1", "r2"] and o["rounds_measured"]
          and o["rounds_match_record"] and o["phase_covers_steps"])
    return ("PASS" if ok else "FAIL", "the multi-round record carries each round's review, the round review, the "
                                      "record computation and the whole phase in seconds rounded to microseconds")


def _records_from_processor(manifest_value, evidence):
    """Neutralisation: the case phase asks PROCESSOR for its records again, through
    the agent boundary it used before open item 35, with the same refusals."""
    import multi_round_phase as phase
    producer = _FACTORY[0]("PROCESSOR")
    contract = {"item_kind": "position", "fields": {"record_id": "id"}, "required": ["record_id"],
                "directives": ["Return canonical {agent, doc_id, items}."]}
    reply = phase._call(producer, contract, {"case": manifest_value, "evidence": evidence},
                        manifest_value["case_id"], "")
    return phase._items(reply, "PROCESSOR", manifest_value["case_id"])


# A case manifest over the same two documents exercising every rule of
# computed_records. Sources by (round, issue): a single accepted figure; a span
# holding two figures (no numeric position); a declared unaccepted source; two
# statements for one triple (never chosen between).
def _span(doc, quote, sid, rnd, issue, state="accepted"):
    start = doc["text"].index(quote)
    return {"source_id": sid, "round_id": rnd, "actor_id": "actor_a", "issue_id": issue,
            "document_id": doc["id"], "unit_id": "u01-entry-alpha", "char_start": start,
            "char_end": start + len(quote), "quote": quote, "state": state}


def rules_manifest():
    docs = documents()
    d1, d2 = docs
    two = "Reading: 61 units\n\n## Entry Beta\n\nReading: 40 units"
    sources = [_span(d1, "Reading: 61 units", "a1", "r1", "issue_a"),
               _span(d2, "Reading: 61 units", "a2", "r2", "issue_a"),
               _span(d1, two, "b1", "r1", "issue_b"),
               _span(d2, "Reading: 70 units", "b2", "r2", "issue_b"),
               _span(d1, "Reading: 40 units", "c1", "r1", "issue_c", state="unresolved"),
               _span(d2, "Reading: 70 units", "c2", "r2", "issue_c"),
               _span(d2, "Reading: 61 units", "d2a", "r2", "issue_d"),
               _span(d2, "Reading: 5 units", "d2b", "r2", "issue_d")]
    case = dict(manifest(docs), sources=sources,
                issues=[{"issue_id": i} for i in ("issue_a", "issue_b", "issue_c", "issue_d")])
    return case, docs


def observe_computed_rules():
    from reference_builder import ReferenceIndex
    import multi_round_phase as phase
    case, docs = rules_manifest()
    with tempfile.TemporaryDirectory(prefix="shimmer_rounds_oi35_rules_") as td:
        refs = ReferenceIndex.open(Path(td), index_path=Path(td) / "reference_index.json")
        evidence = mr.bind_sources(mr.validate_manifest(case), docs, refs)
        rows = phase.computed_records(case, evidence)
        record = {"manifest": case, "evidence": evidence, "records": rows}
        view = mr.project(record)
        return {"rows": sorted((r["record_id"], r["state"], r["confidence"], r.get("movement"), r.get("value"),
                                tuple(r["source_ids"])) for r in rows),
                "deltas": sorted((c["movement_id"], c.get("delta")) for c in view["structural_comparisons"])}


# D-319: a position carries a figure only when it takes part in a computed gap between two parties
# (position_gaps). This case has one actor, so no position carries one, and no movement a delta.
COMPUTED_RULES = {
    "rows": sorted([
        ("position.r1.actor_a.issue_a", "accepted", "CONFIDENT", None, None, ("a1",)),
        ("position.r2.actor_a.issue_a", "accepted", "CONFIDENT", None, None, ("a2",)),
        ("position.r1.actor_a.issue_b", "accepted", "CONFIDENT", None, None, ("b1",)),
        ("position.r2.actor_a.issue_b", "accepted", "CONFIDENT", None, None, ("b2",)),
        ("position.r1.actor_a.issue_c", "insufficient_evidence", "UNCERTAIN", None, None, ("c1",)),
        ("position.r2.actor_a.issue_c", "accepted", "CONFIDENT", None, None, ("c2",)),
        ("position.r2.actor_a.issue_d", "unresolved", "UNCERTAIN", None, None, ("d2a", "d2b")),
        ("movement.r1.r2.actor_a.issue_a", "accepted", "UNCERTAIN", "unknown", None, ("a1", "a2")),
        ("movement.r1.r2.actor_a.issue_b", "accepted", "UNCERTAIN", "unknown", None, ("b1", "b2")),
        ("movement.r1.r2.actor_a.issue_c", "insufficient_evidence", "UNCERTAIN", "unknown", None, ("c1", "c2"))]),
    # A delta only where both positions are accepted and each states one figure.
    "deltas": [("movement.r1.r2.actor_a.issue_a", None), ("movement.r1.r2.actor_a.issue_b", None)]}


def check_computed_rules():
    o = observe_computed_rules()
    return ("PASS" if o == COMPUTED_RULES else "FAIL",
            "positions only from declared sources; a position carries a figure only in a computed gap between two parties, so none here; an "
            "unaccepted source or two statements are never accepted; movements are never classified")


def _first_figure(position, in_gaps):
    """Neutralisation: a position carries the first figure its span states, with the word after it,
    whether or not it takes part in a computed gap (the reading before D-319)."""
    found = pr.quantities(position["position"])
    return (found[0][0], found[0][1]) if found and found[0][1] else (None, "neutralised")


def _accepted_when_all_accepted(sources):
    """Neutralisation: a position is accepted whenever its sources are, however many
    statements it holds (Python would then choose between them)."""
    return "accepted" if all(s["state"] == "accepted" for s in sources) else "insufficient_evidence"


V1 = "## Section One\n\nAlpha count: 42 units\nBeta level: 17 units\nGamma total: 9 units\n"


# S2 checker A9: the same section with figures that carry no unit of measure.
V1_NO_UNIT = "## Section One\n\nAlpha count: 42\nBeta level: 17\nGamma total: 9\n"


def _absent(v2_lines, v1=V1):
    v2 = "## Section One\n\n" + "".join(line + "\n" for line in v2_lines)
    index = pr.prior_index(v1, lambda i: "REF-0001", known_units=set())
    units = pm.split_units(v2, document_id="v2")
    present = set()
    for unit in units:
        present |= pm.unit_fields(unit.get("text", ""))
    unit = units[0]
    scalars, _, _ = pr.extract_fields(unit.get("text", ""), known_units=set())
    slug = unit["unit_id"].split("-", 1)[1]
    hits, _ = pr.prior_lookup(index, scalars, slug)
    checks, refused = pr.absent_checks(index, present, slug, scalars=scalars, hits=hits)
    return ({c["stated_field"]: c["relation"] for c in checks},
            {r["label"]: r["reason"].split(":")[0] for r in refused})


def observe_rename():
    moved = round(17 * 1.25, 2)   # the value moved by a quarter: far outside rename_tolerance()
    return {
        "renamed_kept": _absent(["Alpha count: 42 units", "Beta score: 17 units", "Gamma total: 9 units"]),
        "renamed_moved": _absent(["Alpha count: 42 units", "Beta score: %s units" % moved, "Gamma total: 9 units"]),
        "withdrawn": _absent(["Alpha count: 42 units", "Beta level: 17 units"]),
        "withdrawn_other_measure": _absent(["Alpha count: 42 units", "Beta level: 17 units", "Delta share: 3 kg"]),
        "no_unit_renamed_moved": _absent(["Alpha count: 42", "Beta score: %s" % moved, "Gamma total: 9"], V1_NO_UNIT),
        "no_unit_withdrawn": _absent(["Alpha count: 42", "Beta level: 17"], V1_NO_UNIT),
    }


def check_rename():
    o = observe_rename()
    kept_minted, kept_refused = o["renamed_kept"]
    moved_minted, moved_refused = o["renamed_moved"]
    gone_minted, gone_refused = o["withdrawn"]
    other_minted, other_refused = o["withdrawn_other_measure"]
    bare_minted, bare_refused = o["no_unit_renamed_moved"]
    bare_gone_minted, bare_gone_refused = o["no_unit_withdrawn"]
    ok = ("beta level" not in kept_minted and kept_refused.get("beta level") == "possible rename, not a confirmed withdrawal"
          and "beta level" not in moved_minted
          and moved_refused.get("beta level") == "possible rename with a moved value, not a confirmed withdrawal"
          and gone_minted == {"gamma total": "absent_since_prior"} and not gone_refused
          and other_minted == {"gamma total": "absent_since_prior"} and not other_refused
          # A9: with no unit on either figure, the unit cannot tell them apart, so
          # the possible rename is refused under its own reason, never minted.
          and "beta level" not in bare_minted
          and bare_refused.get("beta level") == "possible rename of a figure with no unit, not a confirmed withdrawal"
          and bare_gone_minted == {"gamma total": "absent_since_prior"} and not bare_gone_refused)
    return ("PASS" if ok else "FAIL", "renamed-and-moved refused, with or without a unit; true withdrawal minted")


# Check 261 strips exactly these five statements of main and these two parser flags,
# then compares every function hash with the pinned contract. S2b leaves all seven as
# they were at the stage base: their AST digests are pinned here, so an edit to any
# of them fails this check (and would need check 261's own change, under IV.6).
_TESTS = {"args.multi_round or args.multi_round_manifest", "multi_manifest is not None", "multi_record is not None"}
_FLAGS = {"--multi-round", "--multi-round-manifest"}


def stripped_statements(source):
    tree = ast.parse(source)
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    parser = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_build_arg_parser")
    statements = []
    for s in main.body:
        if isinstance(s, ast.Assign) and len(s.targets) == 1 and isinstance(s.targets[0], ast.Name) \
                and s.targets[0].id in {"multi_record", "multi_manifest"}:
            statements.append(s)
        elif isinstance(s, ast.If) and ast.unparse(s.test) in _TESTS:
            statements.append(s)
    flags = [s for s in parser.body if isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
             and s.value.args and isinstance(s.value.args[0], ast.Constant) and s.value.args[0].value in _FLAGS]
    return [hashlib.sha256(ast.dump(s, include_attributes=False).encode()).hexdigest()[:16]
            for s in statements + flags]


# The seven digests at the stage base (d830cee), measured with stripped_statements:
# main's two assignments and three branches, then the two parser flags, in order.
BASE_STRIPPED = ["aa2c2b68a153aedc", "6d1a31688d5f9332", "9d2477941680e5c8", "aa0cf8ac2100fc5d",
                 "172bf358a00be93b", "7ed8802292da0134", "e8ad2dcad3f0b193"]


def observe_check261_structure():
    source = (ROOT / "scripts" / "pipeline.py").read_text(encoding="utf-8")
    return {"digests": stripped_statements(source)}


def check_check261_structure():
    o = observe_check261_structure()
    ok = len(o["digests"]) == 7 and o["digests"] == BASE_STRIPPED
    return ("PASS" if ok else "FAIL", "five stripped statements and two parser flags unchanged")


class _EditedMain:
    """Neutralisation: the pipeline source as read here, with one stripped statement
    edited (the case-phase return code changed), as an S2b edit there would be."""

    def __enter__(self):
        real = Path.read_text

        def read_text(path, *args, **kwargs):
            text = real(path, *args, **kwargs)
            if Path(path).name == "pipeline.py" and Path(path).parent.name == "scripts":
                text = text.replace("            return 8\n    activation_agents", "            return 9\n    activation_agents", 1)
            return text
        self.patch = patch.object(Path, "read_text", read_text)
        self.patch.__enter__()
        return self

    def __exit__(self, *exc):
        return self.patch.__exit__(*exc)


class MultiRoundRoundsChecks(unittest.TestCase):
    def prove(self, name, observe, check, neutralise):
        from effect_proof import prove_effect
        prove_effect(name=name, validate=lambda: mr.validate_manifest(manifest(documents())) is not None,
                     observe=observe, check=check, neutralise=neutralise)

    def test_s2b3_later_round_reruns_only_what_changed(self):
        self.prove("s2b3_reuse", observe_reuse, check_reuse,
                   lambda: patch.object(rounds, "unit_signature", lambda *a, **k: uuid.uuid4().hex))

    def test_h4_round_findings_reach_the_bus(self):
        self.prove("h4_round_bus", observe_reuse, check_reuse,
                   lambda: patch.object(rounds, "post_findings", lambda *a, **k: 2))

    def test_a10_a_changed_rule_recomputes(self):
        self.prove("a10_rule", observe_signature, check_signature, lambda: _without("rules"))

    def test_a10_a_changed_vocabulary_recomputes(self):
        self.prove("a10_vocabulary", observe_signature, check_signature, lambda: _without("vocabulary"))

    def test_oi35_a_label_no_paired_rule_names_does_not_recompute(self):
        # Neutralised: the signature covers the whole document vocabulary again.
        self.prove("oi35_named_vocabulary", observe_signature, check_signature,
                   lambda: patch.object(rounds, "named_vocabulary", _whole_vocabulary))

    def test_oi35_the_case_is_reviewed_with_no_model_call(self):
        # Neutralised: the phase asks PROCESSOR for its records, as before open item 35.
        import multi_round_phase
        self.prove("oi35_no_model_call", observe_no_model_call, check_no_model_call,
                   lambda: patch.object(multi_round_phase, "computed_records", _records_from_processor))

    def test_oi39_the_run_records_its_own_step_times(self):
        # Neutralised: the phase writes no timings object.
        import multi_round_phase
        self.prove("oi39_step_times", observe_timings, check_timings,
                   lambda: patch.object(multi_round_phase, "step_timings", lambda *a, **k: {}))

    def test_oi39_step_times_are_rounded_to_microseconds(self):
        # Neutralised: the measured intervals are written unrounded.
        self.prove("oi39_rounded", observe_timings, check_timings,
                   lambda: patch.object(rounds, "seconds", lambda elapsed: float(elapsed) + 1e-9))

    def test_oi35_two_figures_give_no_numeric_position(self):
        import multi_round_phase
        self.prove("oi35_one_figure", observe_computed_rules, check_computed_rules,
                   lambda: patch.object(multi_round_phase, "_numeric", _first_figure))

    def test_oi35_several_statements_are_never_chosen_between(self):
        import multi_round_phase
        self.prove("oi35_several_statements", observe_computed_rules, check_computed_rules,
                   lambda: patch.object(multi_round_phase, "_position_state", _accepted_when_all_accepted))

    def test_oi35_a_movement_is_never_classified(self):
        # Neutralised: Python names a movement from the figures (a falling value a
        # concession), the inference the contract forbids.
        import multi_round_phase
        real = multi_round_phase.computed_records

        def classified(manifest_value, evidence):
            rows = real(manifest_value, evidence)
            for r in rows:
                if r["kind"] == "movement":
                    r["movement"] = "stable"
            return rows
        self.prove("oi35_movement_unknown", observe_computed_rules, check_computed_rules,
                   lambda: patch.object(multi_round_phase, "computed_records", classified))

    def test_a10_a_changed_known_unit_recomputes(self):
        self.prove("a10_known_units", observe_signature, check_signature, lambda: _without("known_units"))

    def test_a10_reused_model_asks_are_rebased(self):
        self.prove("a10_asks", observe_moved_asks, check_moved_asks,
                   lambda: patch.object(rounds, "_rebase_asks", lambda asks, unit_id: asks))

    def test_a10_the_convention_parse_path_runs(self):
        import convention_parser
        self.prove("a10_parse", observe_parse, check_parse,
                   lambda: patch.object(convention_parser, "parse_conventions",
                                        lambda root: convention_parser.ConventionRegistry()))

    def test_s2b4_every_multi_round_reply_saved_once(self):
        self.prove("s2b4_replies", observe_replies, check_replies,
                   lambda: patch.object(reply_records, "write", lambda *a, **k: None))

    def test_s2b5_renamed_and_moved_is_not_withdrawn(self):
        self.prove("s2b5_rename", observe_rename, check_rename,
                   lambda: patch.object(pr, "possible_successor", lambda *a, **k: None))

    def test_a9_renamed_figure_with_no_unit_is_not_withdrawn(self):
        # Neutralised: the successor test requires a unit, as the value test does.
        real = pr.possible_successor
        self.prove("a9_no_unit_rename", observe_rename, check_rename,
                   lambda: patch.object(pr, "possible_successor",
                                        lambda unit, *a, **k: real(unit, *a, **k) if unit else None))

    def test_s2b6_check_261_statements_left_as_they_are(self):
        self.prove("s2b6_check261", observe_check261_structure, check_check261_structure, _EditedMain)


def check():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MultiRoundRoundsChecks)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful():
        problems = [str(case).split(" ")[0] + ": " + str(err).strip().splitlines()[-1][:160]
                    for case, err in list(result.failures) + list(result.errors)]
        return "FAIL", "; ".join(problems[:4])
    return "PASS", ("%d S2b and open item 35 proofs, each neutralise, fail, restore, pass: a later round "
                    "recomputes only the changed unit's pairs and records the reuse; a changed rule, a label "
                    "a paired rule names or a known unit recomputes an unchanged unit, a label no paired rule "
                    "names does not; reused model asks carry the new unit id; the convention-parse path runs; "
                    "the round findings reach the bus; the case is reviewed and activated with its records "
                    "computed in Python and no model call, a position carries a figure only in a computed gap between two parties, "
                    "several statements are never chosen between, a movement is never classified; the run "
                    "records each round's review, the round review, the record computation and the whole "
                    "phase in seconds rounded to microseconds (open item 39); every "
                    "multi-round reply (the strategic layer's) saved once as advisory_not_record; a renamed "
                    "term whose value moved, or that has no unit, is refused, not withdrawn; check 261's "
                    "stripped statements unchanged" % result.testsRun)


if __name__ == "__main__":
    status, detail = check()
    print(status, detail)
