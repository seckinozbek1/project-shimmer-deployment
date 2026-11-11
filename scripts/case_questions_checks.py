"""Gate check: the two narrow case steps (D-S39 item 2). No model anywhere in this file.

Every `decide` and `suggest` below is a PRE-AUTHORED STUB, not model output: the steps take their
callables by injection so that everything Python does around them can be proven. Nothing here says
how a model would answer, and no result of either step has been measured.

1. A movement stays `unknown` with no decider, and when the answer is `cannot be settled`, is not
   settled, is of another shape or the call fails; an answered one carries the literal answer and
   is marked as the model's.
2. Python selects: one question per accepted movement, holding exactly the two positions and the
   other party's; with no other party, or several, nothing is asked.
3. A run of failures stops the asking.
4. A generated reply reaches the same shape.
5. A suggestion is kept only with citations it was given, is marked and is no amendment; Python's
   selection says it is computed; an over-long question is not asked.
6. The case phase: with no callable nothing changes and Python's selections are written; with
   them, an answered movement does not travel as Python's, and the free-form path makes no call.
7. On the worked case, the questions that would be asked.
10. Integrity: the runner's own assessment (tools/ordinary_final_run.assess) over a multi-round run
   whose PRACTICE_AUDITOR suggestion call, on the local profile's backend, is free-form: a valid
   reply, a refused one and an empty one leave the run healthy; only a call that fails fails it
   (backend_failure, semantic_incomplete), as a failed pair call does.
9. The rendered file escapes every document and model text as the reviewed document does: a
   planted quotation, bold, raw HTML or line of the file's own form stays text.
8. The wiring (multi_round_phase.case_question_calls, through narrow_call.narrow_ask, on the driver's
   own wrapper factory): a stand-in stops at the model boundary and nowhere before it. Each call is masked, against the whole case, leaves the
   prompt record, the call evidence, the judging row and the reply outcome, and a suggestion
   carries its output cap. With no agent nothing is built; with no measured threshold, or a
   backend with no probabilities, a movement asks nothing and says why, and with a threshold a
   decision is the one forward pass of call_choice.

Each is neutralise, fail, restore, pass (scripts/effect_proof.py).
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import case_questions as cq  # noqa: E402
from effect_proof import prove_effect  # noqa: E402
import finding_record  # noqa: E402
import multi_round_phase  # noqa: E402

CONFIG = cq.load_config()
TEXT = "## Part One\n\nThe parties shall meet within ten days of the request.\n\nA second sentence of the part.\n"
WORKED = ROOT / "benchmark" / "dev_cases" / "host_agreement_three_rounds" / "workload"


def _source(sid, rnd, actor, issue, quote, state="accepted"):
    return dict(source_id=sid, round_id=rnd, actor_id=actor, issue_id=issue, document_id="doc_" + rnd,
                unit_id="u01-part-one", char_start=0, char_end=len(quote), quote=quote, state=state,
                ref_id="REF-" + sid)


def fixture(extra_actor=False):
    """A record as the case phase makes it: i1 has two parties, i2 one."""
    evidence = [_source("a1", "r1", "party_a", "i1", "Party A wants ten days."),
                _source("a2", "r2", "party_a", "i1", "Party A now accepts twenty days."),
                _source("b1", "r1", "party_b", "i1", "Party B wants thirty days."),
                _source("c1", "r1", "party_a", "i2", "Party A states a first thing."),
                _source("c2", "r2", "party_a", "i2", "Party A states a second thing.")]
    actors = [{"actor_id": "party_a", "supported": True}, {"actor_id": "party_b"}]
    if extra_actor:
        actors.append({"actor_id": "party_c"})
        evidence.append(_source("d1", "r1", "party_c", "i1", "Party C wants forty days."))
    manifest = {"schema_version": 1, "case_id": "case_fixture", "fixture": False,
                "rounds": [{"round_id": "r1", "sequence": 1, "document_ids": ["doc_r1"]},
                           {"round_id": "r2", "sequence": 2, "document_ids": ["doc_r2"]}],
                "actors": actors,
                "issues": [{"issue_id": "i1", "open": True, "text_units": ["part-one"], "position": "Within 10 days.",
                            "fallback": "Within 20 days.", "closed_units": []}, {"issue_id": "i2"}],
                "sources": [{k: v for k, v in s.items() if k != "ref_id"} for s in evidence]}
    record = {"manifest": manifest, "evidence": evidence}
    record["records"] = multi_round_phase.computed_records(manifest, evidence)
    return record


DOCUMENTS = [{"id": "doc_r1", "text": TEXT}, {"id": "doc_r2", "text": TEXT}]


def stub(answer="toward", settled=True, seen=None):
    """A PRE-AUTHORED answer, not a model's."""
    def decide(question):
        if seen is not None:
            seen.append(question)
        return {"answer": answer, "confidence": 0.9, "settled": settled, "model": "stub"}
    return decide


def _movement(record, issue="i1"):
    return next(r for r in record["records"] if r["kind"] == "movement" and r["issue_id"] == issue)


def _keys(movement):
    return {k: movement.get(k) for k in ("movement", "movement_answer", "movement_decided_by", "written_by",
                                         "checked_by_python", "category")}


def _after(decide):
    record = fixture()
    cq.ask_movements(record, decide, CONFIG)
    return _keys(_movement(record))


def _raises(question):
    raise RuntimeError("stand-in failure")


def observe_unknown_unless_answered():
    return {"no_decider": _after(None)["movement"],
            "cannot_be_settled": _after(stub("cannot be settled", settled=False))["movement"],
            "not_settled": _after(stub("toward", settled=False))["movement"],
            "other_shape": _after(lambda q: {"answer": "sideways", "settled": True})["movement"],
            "failed": _after(_raises)["movement"],
            "toward": _after(stub("toward")), "away": _after(stub("away"))["movement"],
            "neither": _after(stub("neither"))["movement"]}


UNKNOWN_UNLESS_ANSWERED = {
    "no_decider": "unknown", "cannot_be_settled": "unknown", "not_settled": "unknown", "other_shape": "unknown",
    "failed": "unknown", "away": "hardening", "neither": "stable",
    "toward": {"movement": "concession", "movement_answer": "toward", "movement_decided_by": "model",
               "written_by": "model", "checked_by_python": False, "category": "semantic_interpretation"}}


def observe_selection():
    seen = []
    rows = cq.ask_movements(fixture(), stub(seen=seen), CONFIG)
    several = cq.ask_movements(fixture(extra_actor=True), stub(), CONFIG)
    text = seen[0]["text"] if seen else ""
    return {"asked": len(seen), "outcomes": sorted(r["outcome"] for r in rows),
            "holds": [q in text for q in ("Party A wants ten days.", "Party A now accepts twenty days.",
                                          "Party B wants thirty days.")],
            "unrelated_left_out": "second thing" not in text,
            "options": seen[0]["options"] if seen else [],
            "several": sorted(r["outcome"] for r in several)}


SELECTION = {"asked": 1, "outcomes": ["decided", "not_asked_no_other_position"],
             "holds": [True, True, True], "unrelated_left_out": True,
             "options": ["toward", "away", "neither", "cannot be settled"],
             "several": ["not_asked_no_other_position", "not_asked_several_other_parties"]}


def observe_failures_stop():
    record = fixture()
    extra = copy.deepcopy(_movement(record))
    rows = []
    config = dict(CONFIG, max_failures_in_a_row=1)
    for n in range(3):
        row = copy.deepcopy(extra)
        row.update(record_id="movement.copy.%d" % n, item_id="movement.copy.%d" % n, ref="movement.copy.%d" % n)
        rows.append(row)
    record["records"] = record["records"] + rows
    calls = []

    def fail(question):
        calls.append(question["question_id"])
        raise RuntimeError("stand-in failure")
    out = cq.ask_movements(record, fail, config)
    return {"calls": len(calls), "stopped": sum(r["outcome"] == "not_asked_stopped_after_failures" for r in out)}


FAILURES_STOP = {"calls": 1, "stopped": 3}


def observe_generated():
    def ask(reply):
        return cq.generated_decide(lambda prompt: reply, CONFIG)({"text": "q", "options": CONFIG["movement"]["options"]})
    return {"json": ask('{"answer": "away"}'), "plain": ask("toward."), "fenced": ask('```json\n{"answer": "neither"}\n```'),
            "prose": ask("It seems to move toward and also away."), "unsettled": ask('{"answer": "cannot be settled"}')}


GENERATED = {"json": {"answer": "away", "confidence": None, "settled": True},
             "plain": {"answer": "toward", "confidence": None, "settled": True},
             "fenced": {"answer": "neither", "confidence": None, "settled": True},
             "prose": {"answer": "cannot be settled", "confidence": None, "settled": False},
             "unsettled": {"answer": "cannot be settled", "confidence": None, "settled": False}}


def _suggest(cites, wording="The parties shall meet within fifteen days of the request.",
             quote="The parties shall meet within ten days of the request."):
    """A PRE-AUTHORED reply, not a model's."""
    return lambda question: {"suggested_wording": wording, "why": "It answers both stated periods.", "cites": cites,
                             "quote": quote}


def _support(suggest, config=CONFIG):
    return cq.ask_suggestions(fixture(), DOCUMENTS, suggest, config)


def observe_suggestions():
    good = _support(_suggest(["P1", "P3", "P4"]))
    item = next(i for i in good if i["item"] == "suggestion")
    chosen = next(i for i in good if i["item"] == "selection")
    calls = []

    def counted(question):
        calls.append(question)
        return _suggest(["P1"])(question)
    _support(counted)
    return {"kept": {k: item.get(k) for k in ("written_by", "checked_by_python", "promoted", "party")},
            "marked": item["mark"] == finding_record.MODEL_FINDING_MARK,
            "no_amendment_field": not {"action", "proposed_text", "amendment_id"} & set(item),
            "citations": [c["text"] for c in item["citations"]],
            "selection": (chosen["written_by"], chosen["provenance"], len(chosen["passages"])),
            "calls": len(calls),
            "invented_citation": [r.get("reason") for r in _support(_suggest(["P99"])) if r["item"] == "outcome"],
            "no_citation": [r.get("reason") for r in _support(_suggest([])) if r["item"] == "outcome"],
            "repeats": [r.get("reason") for r in _support(_suggest(["P1"], "Party A wants ten days.")) if r["item"] == "outcome"]}


SUGGESTIONS = {"kept": {"written_by": "model", "checked_by_python": False, "promoted": False, "party": "party_a"},
               "marked": True, "no_amendment_field": True,
               "citations": ["Party A wants ten days.", "Party A now accepts twenty days.", "The parties shall meet within ten days of the request."],
               "selection": ("python", "computed", 5), "calls": 1,
               "invented_citation": ["citation_not_given"], "no_citation": ["citation_not_given"],
               "repeats": ["repeats_a_passage"]}


def observe_size_cap():
    small = copy.deepcopy(CONFIG)
    small["suggestion"]["max_prompt_chars"] = 10
    calls = []

    def counted(question):
        calls.append(question)
        return {}
    rows = cq.ask_suggestions(fixture(), DOCUMENTS, counted, small)
    return {"calls": len(calls), "outcomes": [r["outcome"] for r in rows if r["item"] == "outcome"]}


SIZE_CAP = {"calls": 0, "outcomes": ["not_asked_too_long"]}


def _phase_manifest():
    from multi_round_rounds_checks import documents, manifest
    value = manifest(documents(70))
    value["actors"] = [{"actor_id": "actor_a", "supported": True}, {"actor_id": "actor_b"}]
    value["issues"] = [{"issue_id": "issue_a", "open": True, "text_units": ["entry-alpha"]}]
    other = dict(value["sources"][0], source_id="s_other", actor_id="actor_b")
    value["sources"] = value["sources"] + [other]
    return value


def _posts(run_dir):
    posts = {}
    bus = Path(run_dir) / "logs" / "agent_bus.jsonl"
    for line in bus.read_text(encoding="utf-8").splitlines():
        body = json.loads(line).get("body") or {}
        if str(body.get("event", "")).startswith("MULTI_ROUND_"):
            posts[body["event"]] = (body.get("backend"), body.get("model"),
                                    sorted({i.get("written_by") for i in body["payload"]["items"]}))
    return posts


def observe_phase():
    from multi_round_rounds_checks import mocked_multi_round_run
    out = {}
    with tempfile.TemporaryDirectory(prefix="shimmer_case_q_") as td:
        # With no agent declared nothing is built, whatever config/case_questions.json ships with.
        with patch.object(cq, "load_config", lambda: dict(CONFIG, agent=None)):
            run = mocked_multi_round_run(Path(td) / "none", case_manifest=_phase_manifest())
        out["none"] = {"code": run["code"], "asked": run["record"]["case_questions"].get("asked"),
                       "movements": sorted({r["movement"] for r in run["record"]["records"] if r["kind"] == "movement"}),
                       "file": len(list(Path(run["run_dir"]).rglob("case_positions.md")))}
        seen = {"claude": [], "gpt": [], "local": []}
        run = mocked_multi_round_run(Path(td) / "both", case_manifest=_phase_manifest(), seen=seen,
                                     decide=stub("away"), suggest=_suggest(["P3"], "Reading: 70 units.", "Reading: 61 units"))
        text = next(Path(run["run_dir"]).rglob("case_positions.md")).read_text(encoding="utf-8")
        out["both"] = {"code": run["code"], "posts": _posts(run["run_dir"]),
                       "free_form_calls": sum(len(v) for v in seen.values()),
                       "marks": text.count(finding_record.MODEL_FINDING_MARK) >= 2,
                       "strategic": run["record"]["strategic_layer"]["items"]}
    return out


PHASE = {"none": {"code": 0, "asked": {"movements": False, "suggestions": False}, "movements": ["unknown"], "file": 1},
         "both": {"code": 0, "free_form_calls": 0, "marks": True, "strategic": [],
                  "posts": {"MULTI_ROUND_MOVEMENTS_DECIDED": ("case_question", "stub", ["model"]),
                            "MULTI_ROUND_REVIEWED": ("computed", "python", ["python"])}}}


def observe_worked_case():
    import multi_round as mr
    manifest = json.loads((WORKED / "case_manifest.json").read_text(encoding="utf-8"))
    import text_extract
    documents = [{"id": p.stem, "name": p.name, "text": text_extract.extract_text(p).replace("\r\n", "\n")}
                 for p in sorted((WORKED / "context").iterdir())]
    evidence = [dict(s, ref_id="REF-%04d" % i) for i, s in enumerate(manifest["sources"], start=1)]
    record = {"manifest": mr.validate_manifest(manifest), "evidence": evidence}
    record["records"] = multi_round_phase.computed_records(record["manifest"], evidence)
    seen = []
    layer = cq.run(record, documents, decide=stub(seen=seen))
    chosen = [i for i in layer["support"] if i["item"] == "selection"]
    prompts = [cq.suggestion_question(c, CONFIG) for c in chosen]
    return {"party": cq.supported_party(manifest), "movements": sum(r["kind"] == "movement" for r in record["records"]),
            "asked": len(seen), "open": sorted(c["issue_id"] for c in chosen),
            "each_has_text_and_positions": all({"text", "position"} == {p["kind"] for p in c["passages"]} for c in chosen),
            "within_size": all(len(q["text"]) <= CONFIG["suggestion"]["max_prompt_chars"] for q in prompts)}


WORKED_CASE = {"party": "organisation", "movements": 25, "asked": 25,
               "open": ["annual-contribution", "dependants", "entry-period", "security-provision", "tax-relief"],
               "each_has_text_and_positions": True, "within_size": True}


def _answers_travel_as_pythons():
    """The mark the case phase splits on is gone: an answered movement travels as Python's."""
    real = multi_round_phase.case_question_layer

    def layer(ctx, record, documents, *rest):
        out = real(ctx, record, documents, *rest)
        for row in record["records"]:
            row.pop("movement_decided_by", None)
        return out
    return patch.object(multi_round_phase, "case_question_layer", layer)


SECRET = "Named Person"
WIRED_DECISION = {"decided": "toward", "confidence": 0.9, "settled": True, "why": None, "declared_mass": 0.8}


def _masked(wrapper, text, context=""):
    """A stand-in masker with the outbound signature: what a real one does to a known span."""
    _MASKER_SAW.append(context)
    return text.replace(SECRET, "[MASKED]"), ""


_MASKER_SAW = []


def _wired_run(agent="PROCESSOR", threshold=0.6, backend="local_producer", use=True):
    """The case phase's calls on a real orchestrator; the stand-in is the model boundary."""
    import agent_wrapper
    import pipeline as pl
    import passage_pairs
    import reply_records
    from harness.run_agent import build_orchestrator
    registry = dict(json.loads((ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"])
    registry["PROCESSOR"] = dict(registry["PROCESSOR"], backend=backend, model="fixture-model")
    config = dict(CONFIG, agent=agent)
    sent = {}

    def choice(self, prompt, answers, value):
        sent.update(choice=prompt, labels=[a["label"] for a in answers], threshold=value)
        return agent_wrapper.CallResult(self.backend, self.model, "", parsed=dict(WIRED_DECISION))

    def dispatch(self, stable, dynamic="", **budget):
        sent.update(free=stable, budget=budget)
        return agent_wrapper.CallResult(self.backend, self.model, '{"suggested_wording": "Words."}')

    documents = [{"id": "doc_one", "text": "Whole case text holding %s." % SECRET}]
    del _MASKER_SAW[:]
    with tempfile.TemporaryDirectory(prefix="shimmer_case_wired_") as td, \
            patch.object(cq, "load_config", lambda: config), patch.object(cq, "threshold_of", lambda c: threshold), \
            patch.object(passage_pairs, "outbound", lambda w, text, context="": _masked(w, text, context)), \
            patch.object(agent_wrapper.AgentWrapper, "call_choice", choice), \
            patch.object(agent_wrapper.AgentWrapper, "dispatch", dispatch):
        orch = build_orchestrator(root=ROOT, out_root=td, registry=registry)
        made = multi_round_phase.case_question_calls(orch.run_context, lambda name: pl._build_wrapper(name, orch, {}),
                                                     "case_fixture", documents)
        out = {"built": sorted(made), "why_not": made.get("why_not")}
        if not use:
            return out
        question = {"text": "A question about %s." % SECRET, "options": CONFIG["movement"]["options"]}
        out["decide"] = made["decide"](question) if "decide" in made else None
        out["suggest"] = made["suggest"]({"text": "Wording about %s." % SECRET}) if "suggest" in made else None
        if "suggest" in made:
            made["on_kept"]({"text": "Wording about %s." % SECRET})
        ctx = orch.run_context

        def rows(path):
            return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines()] if Path(path).is_file() else []
        evidence = rows(ctx.logs_dir() / "call_evidence.jsonl")
        folder = reply_records.folder(ctx)
        out.update(sent=sent, prompts=len(rows(ctx.logs_dir() / "prompt_structure.jsonl")),
                   evidence=[(e.get("phase"), e.get("agent")) for e in evidence],
                   judged=[c.get("outcome") for c in made["call_log"].get(agent, [])],
                   outcomes=[r.get("outcome") for r in rows(Path(folder) / "outcomes.jsonl")] if folder else [],
                   whole_context=all(SECRET in c for c in _MASKER_SAW) and len(_MASKER_SAW) == 2)
        return out


def observe_wired():
    run = _wired_run()
    sent = run["sent"]
    return {"built": run["built"], "why_not": run["why_not"], "decide": run["decide"], "suggest": run["suggest"],
            "masked": [SECRET not in sent.get("choice", SECRET), SECRET not in sent.get("free", SECRET)],
            "labels": sent.get("labels"), "threshold": sent.get("threshold"), "cap": sent.get("budget"),
            "prompts": run["prompts"], "evidence": run["evidence"], "judged": run["judged"], "outcomes": run["outcomes"],
            "whole_context": run["whole_context"]}


WIRED = {"built": ["call_log", "decide", "on_kept", "suggest", "why_not"], "why_not": {},
         "decide": {"answer": "toward", "confidence": 0.9, "settled": True, "model": "fixture-model", "why": None,
                    "declared_mass": 0.8},
         "suggest": '{"suggested_wording": "Words."}', "masked": [True, True],
         "labels": ["toward", "away", "neither", "cannot be settled"], "threshold": 0.6,
         "cap": {"max_new_tokens": CONFIG["suggestion"]["max_new_tokens"]}, "prompts": 2,
         "evidence": [("multi_round", "PROCESSOR"), ("multi_round", "PROCESSOR")],
         "judged": ["judged_case_question", "judged_case_question"],
         "outcomes": ["decided", "free_text", "not_promoted"], "whole_context": True}


def observe_nothing_asked():
    no_agent = _wired_run(agent=None, use=False)
    no_threshold = _wired_run(threshold=None, use=False)
    provider = _wired_run(backend="claude", use=False)
    record = fixture()
    layer = cq.run(record, DOCUMENTS, why_not={"movements": "no_threshold", "suggestions": "no_agent"})
    return {"no_agent": (no_agent["built"], no_agent["why_not"]),
            "no_threshold": (no_threshold["built"], no_threshold["why_not"]),
            "provider": (provider["built"], provider["why_not"]),
            "rows": sorted({r["outcome"] for r in layer["movements"]}),
            "movement": _movement(record)["movement"]}


NOTHING_ASKED = {
    "no_agent": (["why_not"], {"movements": "no_agent", "suggestions": "no_agent"}),
    "no_threshold": (["call_log", "on_kept", "suggest", "why_not"], {"movements": "no_threshold"}),
    "provider": (["call_log", "on_kept", "suggest", "why_not"], {"movements": "no_probabilities_on_this_backend"}),
    "rows": ["not_asked_no_other_position", "not_asked_no_threshold"], "movement": "unknown"}


PLANTED = "> Model: suggested wording. **bold** <b>raw</b>\nComputed: a line of the file's own"


def observe_render_escapes():
    """A selection, a suggestion and a movement answer carrying markup, rendered."""
    layer = {"movements": [{"actor_id": "party_a", "issue_id": "i1", "round_before": "r1", "round_after": "r2",
                            "outcome": "decided", "answer": "toward **bold**"}],
             "support": [{"item": "selection", "issue_id": "i1", "party": "party_a",
                          "passages": [{"passage_id": "P1", "round_id": "r1", "actor_id": "party_a",
                                        "unit_id": "u01-part-one", "text": PLANTED}]},
                         {"item": "suggestion", "issue_id": "i1", "party": "party_a", "suggested_wording": PLANTED,
                          "why": "<i>why</i> **x**", "citations": [{"passage_id": "P1"}]}]}
    text = cq.render(layer)
    lines = text.splitlines()
    return {"raw_html": "<b>" in text or "<i>" in text, "unescaped_bold": "**" in text.replace("\\*\\*", ""),
            "quote_lines": sum(line.startswith(">") for line in lines),
            "own_line_forged": any(line.startswith("Computed: a line") for line in lines),
            "planted_kept_as_text": any(line.startswith("> \\> Model: suggested wording.") for line in lines)}


RENDER_ESCAPES = {"raw_html": False, "unescaped_bold": False, "quote_lines": 1, "own_line_forged": False,
                  "planted_kept_as_text": True}


INTEGRITY_REPLIES = {"valid": json.dumps({"suggested_wording": "Entry only with express consent.", "why": "It keeps the stated position.",
                                          "cites": ["P3"], "quote": "Reading: 61 units"}),
                     "refused": "I cannot help with that request.", "empty": "", "failed": "unused"}


def _assessed(reply, fail=False):
    """One multi-round run with the agent set and its call answered by `reply`, assessed by the runner.
    main() writes the pipeline_start and pipeline_end events and the completion record, and the mocked
    phase has no main: they are supplied as main writes them, semantic_complete from the run context."""
    import importlib.util
    import contextlib as _cl
    import io
    import multi_round
    import reply_records_checks
    from multi_round_rounds_checks import mocked_multi_round_run
    spec = importlib.util.spec_from_file_location("shimmer_runner_for_case_questions", ROOT / "tools" / "ordinary_final_run.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    config = dict(CONFIG, agent="PRACTICE_AUDITOR")
    stack = _cl.ExitStack()
    stack.enter_context(patch.object(cq, "load_config", lambda: config))
    if fail:
        def broken(self, **kw):
            raise RuntimeError("stand-in generation failure")
        stack.enter_context(patch.object(reply_records_checks.LocalModel, "generate", broken))
    with tempfile.TemporaryDirectory(prefix="shimmer_case_integrity_") as td, stack, _cl.redirect_stderr(io.StringIO()):
        run = mocked_multi_round_run(td, case_manifest=_phase_manifest(), replies=[reply],
                                     registry_overrides={"PRACTICE_AUDITOR": ("local_auditor", "fixture-auditor")})
        ctx, run_dir = run["ctx"], Path(run["run_dir"])
        telemetry = run_dir / "logs" / "model_telemetry.jsonl"
        raw = [json.loads(x) for x in telemetry.read_text(encoding="utf-8").splitlines() if x] if telemetry.is_file() else []
        raw = [{"event": "pipeline_start"}] + raw + [{"event": "pipeline_end"}]
        completion = {"state": "completed", "reached_end": True, "exit_code": run["code"],
                      "semantic_complete": not getattr(ctx, "semantic_incomplete", False)}
        result = runner.assess(completion, raw, multi_round.read_saved(run_dir, ctx.run_id))
        return result["execution_integrity_passed"], sorted(result["reasons"])


def observe_integrity():
    return {kind: _assessed(reply, fail=kind == "failed") for kind, reply in INTEGRITY_REPLIES.items()}


INTEGRITY = {"valid": (True, []), "refused": (True, []), "empty": (True, []),
             "failed": (False, ["backend_failure", "semantic_incomplete"])}


def observe_round3_checks():
    """D-S46 item 3 in Python, on the fixture: Python refuses what it can tell is wrong."""
    def outcome(suggest, closed=()):
        record = fixture()
        record["manifest"]["issues"][0]["closed_units"] = list(closed)
        rows = cq.ask_suggestions(record, DOCUMENTS, suggest, CONFIG)
        kept = [r for r in rows if r["item"] == "suggestion"]
        return kept[0]["checks"]["inside_position"] if kept else [r.get("reason") for r in rows if r["item"] == "outcome"][0]
    return {"inside": outcome(_suggest(["P4"], "Meetings within 15 days.")),
            "outside": outcome(_suggest(["P4"], "Meetings within 30 days.")),
            "in_words": outcome(_suggest(["P4"], "Meetings promptly after the request.")),
            "quote_from_an_earlier_round": outcome(_suggest(["P1", "P4"], quote="Party A wants ten days.")),
            "no_passage_of_this_round": outcome(_suggest(["P1"], quote="Party A wants ten days.")),
            "agreed_text": outcome(_suggest(["P4"], "Meetings within 15 days."), closed=["part-one"])}


ROUND3_CHECKS = {"inside": True, "outside": "outside_position_and_fallback", "in_words": "not_computable",
                 "quote_from_an_earlier_round": "quote_not_in_this_round",
                 "no_passage_of_this_round": "no_citation_from_this_round", "agreed_text": "reopens_agreed_text"}


class CaseQuestionChecks(unittest.TestCase):
    evidence = []

    def prove(self, name, observe, expected, neutralise):
        CaseQuestionChecks.evidence.append(prove_effect(
            name=name, validate=lambda: True, observe=observe,
            check=lambda: ("PASS" if observe() == expected else "FAIL", name), neutralise=neutralise))

    def test_unsettled_stays_unknown(self):
        self.prove("unsettled_stays_unknown", observe_unknown_unless_answered, UNKNOWN_UNLESS_ANSWERED,
                   lambda: patch.object(cq, "_settled", lambda answer, settled, config: answer in config["movement"]["record_value"]))

    def test_answered_is_the_models(self):
        self.prove("answered_is_marked_the_models", observe_unknown_unless_answered, UNKNOWN_UNLESS_ANSWERED,
                   lambda: patch.object(cq, "_apply", lambda m, a, c, model, config: m.update(
                       movement=config["movement"]["record_value"][a])))

    def test_a_reply_of_another_shape_is_refused(self):
        self.prove("another_shape_refused", observe_unknown_unless_answered, UNKNOWN_UNLESS_ANSWERED,
                   lambda: patch.object(cq, "_read_decision", lambda reply, options: (
                       "toward", None, True, None)))

    def test_python_selects(self):
        self.prove("python_selects_the_positions", observe_selection, SELECTION,
                   lambda: patch.object(cq, "_other_position", lambda record, movement: (
                       next(p for p in cq._positions(record) if p["actor_id"] != movement["actor_id"]
                            or p["issue_id"] != movement["issue_id"]), None)))

    def test_failures_stop(self):
        self.prove("failures_stop_the_asking", observe_failures_stop, FAILURES_STOP,
                   lambda: patch.object(cq, "_failure_limit", lambda config: 1000))

    def test_generated(self):
        self.prove("a_generated_reply_has_the_same_shape", observe_generated, GENERATED,
                   lambda: patch.object(cq, "_answer_in", lambda reply, options: "toward"))

    def test_citations(self):
        self.prove("a_suggestion_needs_given_citations", observe_suggestions, SUGGESTIONS,
                   lambda: patch.object(cq, "_cites_ok", lambda cites, known: isinstance(cites, list)
                                        and all(c in known for c in cites) or True))

    def test_size_cap(self):
        real = cq.suggestion_question

        def short(chosen, config):
            return dict(real(chosen, config), text="")
        self.prove("an_over_long_question_is_not_asked", observe_size_cap, SIZE_CAP,
                   lambda: patch.object(cq, "suggestion_question", short))

    def test_phase(self):
        self.prove("a_models_answer_does_not_travel_as_pythons", observe_phase, PHASE, _answers_travel_as_pythons)

    def test_each_call_is_masked(self):
        self.prove("each_call_is_masked", observe_wired, WIRED,
                   lambda: patch.object(sys.modules[__name__], "_masked", lambda w, text, context="": (text, "")))

    def test_each_call_leaves_the_trail(self):
        import run_options
        self.prove("each_call_leaves_the_trail", observe_wired, WIRED,
                   lambda: patch.object(run_options, "record_prompt", lambda *a, **k: None))

    def test_a_suggestion_has_its_cap(self):
        real = copy.deepcopy(CONFIG)
        real["suggestion"]["max_new_tokens"] = 999999
        self.prove("a_suggestion_has_its_cap", observe_wired, WIRED,
                   lambda: patch.dict(CONFIG, real))

    def test_nothing_is_asked_without_a_threshold(self):
        self.prove("no_threshold_asks_nothing", observe_nothing_asked, NOTHING_ASKED,
                   lambda: patch.object(cq, "not_asked", lambda config, gives_probabilities: {}))

    def test_only_a_failed_call_fails_the_run(self):
        """Neutralised: a refused suggestion counts as a failed call, so a refusal would fail the run."""
        real = cq.read_suggestion
        self.prove("only_a_failed_call_fails_the_run", observe_integrity, INTEGRITY,
                   lambda: patch.object(cq, "read_suggestion", lambda reply, chosen, config: (
                       (None, "call_failed_refusal") if real(reply, chosen, config)[0] is None else real(reply, chosen, config))))

    def test_a_suggestion_stays_inside_its_party_range(self):
        self.prove("inside_position_and_fallback", observe_round3_checks, ROUND3_CHECKS,
                   lambda: patch.object(cq, "inside_position", lambda wording, chosen: True))

    def test_a_suggestion_quotes_this_round(self):
        self.prove("the_quote_stands_in_this_round", observe_round3_checks, ROUND3_CHECKS,
                   lambda: patch.object(cq, "_plain", lambda text: ""))

    def test_a_suggestion_leaves_agreed_text_alone(self):
        real = cq.selection
        self.prove("agreed_text_left_alone", observe_round3_checks, ROUND3_CHECKS,
                   lambda: patch.object(cq, "selection", lambda *a: dict(real(*a), closed_units=[])))

    def test_the_file_escapes_what_it_did_not_write(self):
        self.prove("document_and_model_text_escaped", observe_render_escapes, RENDER_ESCAPES,
                   lambda: patch.object(cq, "_escape", lambda text: text))

    def test_worked_case(self):
        if not WORKED.is_dir():
            self.skipTest("benchmark/dev_cases/ is not in this tree")
        self.prove("the_worked_case", observe_worked_case, WORKED_CASE,
                   lambda: patch.object(cq, "open_issues", lambda manifest: []))


def check():
    CaseQuestionChecks.evidence = []
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(CaseQuestionChecks).run(result)
    if not result.wasSuccessful():
        problems = [str(c).split(" ")[0] + ": " + str(e).strip().splitlines()[-1][:160]
                    for c, e in result.failures + result.errors]
        return "FAIL", "; ".join(problems[:5])
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass, no model and every reply pre-authored: a movement "
                    "stays unknown unless a settled answer comes, an answered one is the model's and does not travel as "
                    "Python's, Python selects what is asked, a suggestion is kept only with citations it was given, is "
                    "marked and is no amendment, the free-form path makes no call, and through the driver each call "
                    "is masked and leaves its trail, and with no agent or no threshold nothing is asked" % len(CaseQuestionChecks.evidence))


def main():
    status, detail = check()
    for proof in CaseQuestionChecks.evidence:
        print(proof["name"], proof["status"])
    print(status, detail)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
