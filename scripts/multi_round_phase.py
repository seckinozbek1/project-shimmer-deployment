"""Explicit positioning phase. The case records are computed in Python.

No direct provider/generation API, and no model call on the trajectory path.
Open item 35 (loop S5, INC-023): the phase used to send PROCESSOR the whole case
(manifest, every bound source, the long free-form multi-round contract) in one
call and ask for every position and movement record at once, then send VERIFIER
the same with the proposals added. On real execution (L6m, the synthetic family 4
case) that prompt was 15,795 tokens, the tuned producer's reply ran to its
4,096-token output cap after 944 seconds without an envelope, and the phase
refused the case (agent_output_unavailable); the negotiation case was refused the
same way. The checkpoint was evaluated only on the two-turn compact extraction
shape (EXTRACTION-A); a free-form synthesis of a whole case is outside it, and no
narrower question exists here that it was evaluated on. So no model is asked.

What the records say is what Python can establish from the operator's own
declarations and nothing more (computed_records):
- one POSITION record per declared (round, actor, issue) with its source spans: the
  declared quote as written, accepted only when it rests on exactly one source the
  operator declared accepted; several statements for one triple stay `unresolved`
  (Python never chooses between them), an unaccepted source `insufficient_evidence`;
  a numeric position (value and unit) only when the quote states exactly one figure
  with a unit, read by paired_review.quantities, the paired review's own reader;
- one MOVEMENT record between consecutive declared positions of the same actor and
  issue, carrying both positions' sources, with movement `unknown`: concession,
  hardening and reversal are semantic judgments, never concluded from figures
  (multi_round.project computes the structural comparison, typed equality and
  delta, from the two positions).
Every record carries `written_by: python` and `provenance: computed`, and the
records reach the run bus under backend `computed`, model `python`.

Open item 39: under the multi-round argv no topology runtime exists, so the run's
phase_latencies are empty; the phase records its own step times instead, measured
with time.perf_counter in seconds rounded to microseconds, as `timings` in
audit/multi_round.json (step_timings): each round's review, the whole round review,
the record computation, and the whole phase up to its last write. They are
measurements, never inputs, and change no other field.

The strategic layer (strategic_support.execute) keeps its explicit, optional model
calls for the decision-support modes; a trajectory_only case makes none. The two narrow
steps of scripts/case_questions.py are built here (case_question_calls) from the wrapper
factory the driver gives, once `agent` in config/case_questions.json names an agent.
_call and _items are its agent boundary: a reply that is not ok, is truncated, or
is not the expected envelope is refused there, as before.

accept_review is the loader for PRE-AUTHORED envelopes (multi_round's offline
proofs and the labelled fixture): a reviewer may withhold a proposal, never
rewrite or invent one. Production does not call it.
"""
from copy import deepcopy
import hashlib
import json
import time

import multi_round as mr

WRITTEN_BY = "python"


def _items(reply, agent, case_id):
    mr.require(reply.get("ok") is True and not reply.get("truncated"), "agent_output_unavailable")
    payload = reply.get("parsed")
    mr.require(isinstance(payload, dict) and payload.get("agent") == agent
               and payload.get("doc_id") == case_id, "agent_envelope_identity")
    items = payload.get("items")
    mr.require(isinstance(items, list), "agent_envelope_items")
    return deepcopy(items)


def _call(wrapper, contract, payload, case_id, objectives):
    # Each wrapper is newly constructed by the pipeline factory. No shared
    # registry/contract mutation and no contract change on ordinary calls.
    wrapper.contract = deepcopy(contract)
    return wrapper.run_task(work_payload=payload, run_objectives=objectives,
        channel="multi_round", doc_id=case_id, phase="multi_round", recent_bus_limit=0,
        items_are_advisory=True,
        activation={"reason": "explicit_multi_round_request", "source_phase": "multi_round",
                    "refire_limit": 0})


def _record_id(kind, *parts):
    """A readable identifier when it fits multi_round.identifier, else a digest."""
    readable = ".".join((kind,) + parts)
    if mr.identifier(readable):
        return readable
    return kind + "." + hashlib.sha256(json.dumps(parts).encode("utf-8")).hexdigest()[:32]


def _numeric(position, in_gaps):
    """(value, unit) of a position only when it takes part in a computed gap between the parties
    (position_gaps: all four quotes of two consecutive rounds are the same sentence with only the
    figure changed), else (None, why) with the reason that gap was not computed. The unit is that
    sentence with its figure shown as [figure]: Python reads no unit from words, so a position never
    carries a figure or a unit its gap record does not."""
    value, unit = in_gaps.get(position["record_id"], (None, "not_in_a_computed_gap"))
    if value is None or not mr.finite_number(value) or not isinstance(unit, str) or not unit:
        return None, unit if value is None else "not_in_a_computed_gap"
    return value, unit


def _position_state(sources):
    """Accepted only on exactly one source the operator declared accepted. Several
    statements for one (round, actor, issue) stay unresolved: Python never chooses
    between them."""
    if len(sources) > 1:
        return "unresolved"
    return "accepted" if sources[0]["state"] == "accepted" else "insufficient_evidence"


def computed_records(manifest, evidence):
    """Position and movement records from the declared, bound sources. No model."""
    rounds = {r["round_id"]: r["sequence"] for r in manifest["rounds"]}
    actor_order = [a["actor_id"] for a in manifest["actors"]]
    issue_order = [i["issue_id"] for i in manifest["issues"]]
    by_triple = {}
    for s in evidence:
        by_triple.setdefault((s["round_id"], s["actor_id"], s["issue_id"]), []).append(s)
    case_id = manifest["case_id"]
    positions = []
    for key in sorted(by_triple, key=lambda k: (rounds[k[0]], actor_order.index(k[1]),
                                                issue_order.index(k[2]))):
        round_id, actor_id, issue_id = key
        sources = by_triple[key]
        quotes = [s["quote"] for s in sources]
        state = _position_state(sources)
        row = {"record_id": _record_id("position", round_id, actor_id, issue_id),
               "case_id": case_id, "kind": "position", "state": state,
               "category": "observed_evidence",
               "confidence": "CONFIDENT" if state == "accepted" else "UNCERTAIN",
               "actor_id": actor_id, "issue_id": issue_id, "round_id": round_id,
               "source_ids": [s["source_id"] for s in sources],
               "ref_ids": [s["ref_id"] for s in sources],
               "position": "\n".join(quotes), "text": "\n".join(quotes),
               "written_by": WRITTEN_BY, "provenance": "computed"}
        positions.append(row)
    # D-S46 item 2, D-319: the gap between the parties is computed first, and a position carries a
    # figure only when it takes part in one; otherwise the figure is left out, with the reason.
    import position_gaps
    trajectories, gap_rows = position_gaps.gaps(manifest, positions)
    in_gaps = position_gaps.figures_in_gaps(trajectories, gap_rows, positions)
    for row in positions:
        value, unit = _numeric(row, in_gaps)
        if value is None:
            row["figure_left_out"] = unit
        else:
            row["value"], row["unit"] = value, unit
    movements = []
    for actor_id in actor_order:
        for issue_id in issue_order:
            held = [p for p in positions if p["actor_id"] == actor_id and p["issue_id"] == issue_id]
            for previous, current in zip(held, held[1:]):
                both = previous["state"] == "accepted" and current["state"] == "accepted"
                movements.append({
                    "record_id": _record_id("movement", previous["round_id"], current["round_id"],
                                            actor_id, issue_id),
                    "case_id": case_id, "kind": "movement",
                    "state": "accepted" if both else "insufficient_evidence",
                    "category": "observed_evidence", "confidence": "UNCERTAIN",
                    "movement": "unknown",
                    "actor_id": actor_id, "issue_id": issue_id,
                    "round_id": current["round_id"], "previous_round_id": previous["round_id"],
                    "previous_position_id": previous["record_id"],
                    "current_position_id": current["record_id"],
                    "source_ids": previous["source_ids"] + current["source_ids"],
                    "ref_ids": previous["ref_ids"] + current["ref_ids"],
                    "text": previous["text"] + "\n" + current["text"],
                    "written_by": WRITTEN_BY, "provenance": "computed"})
    records = positions + movements
    for r in records:
        r.update(item_id=r["record_id"], revision=1, ref=r["record_id"])
    # The trajectories computed above (position_gaps); nothing from words.
    records += trajectories
    return mr.validate_records(manifest, evidence, records)


def step_timings(review, measured, phase_seconds):
    """The `timings` object: each round's review seconds as round_reuse.json records them,
    the steps measured in execute (round_review, records), and the whole phase."""
    import multi_round_rounds
    timings = {"unit": "seconds", "clock": "time.perf_counter",
               "rounds": [{"round_id": r.get("round_id"), "seconds": r.get("seconds")}
                          for r in (review or {}).get("rounds") or []]}
    timings.update({name: multi_round_rounds.seconds(value) for name, value in measured.items()})
    timings["phase"] = multi_round_rounds.seconds(phase_seconds)
    return timings


def version_change_record(ctx, manifest, documents):
    """What changed between the rounds, in Python, written beside the round review. Like the
    review, it never takes the case phase down: a failure is recorded by its type."""
    try:
        import version_changes
        written = version_changes.write(ctx, version_changes.case_changes(manifest, documents))
        return {"availability": "recorded", "record": "audit/" + version_changes.RECORD_NAME,
                "deliverables": [p.relative_to(ctx.run_dir).as_posix() for p in written]}
    except Exception as exc:
        return {"availability": "failed", "error_type": type(exc).__name__}


def case_question_calls(ctx, wrapper_factory, case_id, documents):
    """The keyword arguments of case_question_layer: `decide` and `suggest` through
    narrow_call.narrow_ask, so each call is masked and leaves the trail a pair call leaves. The
    agent is `agent` in config/case_questions.json and its model the registry's. Nothing is built
    for a step `case_questions.not_asked` stops: with no agent neither runs, and a decision with no
    measured threshold, or on a backend with no probabilities, asks nothing."""
    import case_questions
    import decoding_policy
    import narrow_call
    import paired_review
    import reply_records
    config = case_questions.load_config()
    agent = case_questions.agent_of(config)
    if agent is None:
        return {"why_not": case_questions.not_asked(config, gives_probabilities=False)}
    wrapper = wrapper_factory(agent)
    wrapper._optimized_semantics = True   # the model's own chat template, as measured
    wrapper._free_form_call = True        # no envelope: the answer is a decision or a small JSON
    local = wrapper.backend in decoding_policy.LOCAL_BACKENDS
    why_not = case_questions.not_asked(config, gives_probabilities=local)
    context = "\n\n".join(str(d.get("text") or "") for d in documents)
    calls, seen, call_of = {}, {}, {}

    def budget(section):
        return {("max_new_tokens" if local else "max_tokens"): config[section]["max_new_tokens"]}

    def narrow(task, send, decided, answer_of, outcome_of):
        return narrow_call.narrow_ask(ctx, ctx.run_id, {"id": case_id}, wrapper, agent, {"id": task}, calls, task=task,
                                      plan_kind=paired_review.CASE_QUESTION_PLAN, context=context, send=send,
                                      decided=decided, answer_of=answer_of, outcome_of=outcome_of, seen=seen,
                                      call_of=call_of, phase="multi_round", trigger_source="case_manifest")

    def not_promoted(question):
        # A kept suggestion ends as a kept pair does: a model's, never an amendment.
        reply_records.write_outcome(ctx, call_of.get(question["text"]), "not_promoted",
                                    source="case_suggestion", findings_withheld=1)

    made = {"why_not": why_not, "on_kept": not_promoted, "call_log": calls}
    if "movements" not in why_not:
        made["decide"] = case_questions.decider(narrow(
            "case_movement",
            lambda stable, dynamic: case_questions.call_movement(wrapper, stable, dynamic, config, budget("movement")),
            case_questions.deciding(config), lambda r: case_questions.answer_of(r, config),
            lambda r: case_questions.outcome_of(r, config)), seen, config)
    if "suggestions" not in why_not:
        made["suggest"] = case_questions.suggester(narrow(
            "case_suggestion", lambda stable, dynamic: wrapper.dispatch(stable, dynamic, **budget("suggestion")),
            False, case_questions.answer_of, case_questions.outcome_of))
    return made


def case_question_layer(ctx, record, documents, decide, suggest, why_not=None, on_kept=None, call_log=None):
    """The two narrow steps of scripts/case_questions.py. Never takes the case phase down: a
    failure is recorded by its type and leaves every movement as Python computed it."""
    import case_questions
    before = deepcopy(record["records"])
    try:
        layer = case_questions.run(record, documents, decide=decide, suggest=suggest, why_not=why_not,
                                   on_kept=on_kept)
        layer["gaps"] = list(record.get("position_gaps") or [])
        path = case_questions.write(ctx, layer, record)
        if layer["failed"]:
            # A failed call leaves a declared question unanswered, as in the passage pair step.
            import generation_observation
            generation_observation.mark_incomplete(ctx)
        return {"availability": "recorded", "record": "audit/" + case_questions.RECORD_NAME,
                "deliverable": path.relative_to(ctx.run_dir).as_posix(), "asked": layer["asked"],
                "failed": layer["failed"], "not_asked": why_not or {}, "judging_calls": call_log or {}}
    except Exception as exc:
        record["records"] = before
        return {"availability": "failed", "error_type": type(exc).__name__}


def execute(ctx, record, documents, reference_index, wrapper_factory, *, sensitive,
            run_objectives="", convention_registry=None, decide=None, suggest=None, why_not=None,
            on_kept=None, call_log=None):
    """Called only on explicit request, after the ordinary startup governance gates.

Sensitive cases refuse before binding sources or constructing wrappers. This
matches the current advisory editorial limitation: no new privacy release path.
The case path returns before ordinary ontology/end-work capture.

S2b item 3: Python reviews the declared rounds in order
(multi_round_rounds.review_rounds); a later round re-runs only the units that
changed, and the reuse is recorded in audit/round_reuse.json. The registry is the
operator's conventions, compiled from input/conventions when not passed. The round
findings are posted on the run bus (backend paired, model python) under
multi_round_rounds.FINDINGS_AGENT, one envelope per round document.

Open item 35: the typed case records are then computed by computed_records, with
no model call; see the module docstring.
"""
    mr.require(record["run_id"] == ctx.run_id, "run_identity")
    started = time.perf_counter()
    review, measured = None, {}
    try:
        mr.require(sensitive is False, "sensitive_multi_round_unavailable")
        manifest = mr.validate_manifest(record["manifest"])
        mr.require(not manifest["fixture"], "fixture_requires_offline_test_adapter")
        record["evidence"] = mr.bind_sources(manifest, documents, reference_index)
        record["activation"] = mr.activation(True, eligible=True, reached=True)
        mr.write_record(ctx, record)
        import multi_round_rounds
        try:
            step = time.perf_counter()
            review = multi_round_rounds.review_rounds(ctx, manifest, documents,
                                                      convention_registry=convention_registry)
            measured["round_review"] = time.perf_counter() - step
            record["round_review"] = {"record": "audit/" + multi_round_rounds.RECORD_NAME,
                                      "availability": review.get("availability")}
            # S2 checker H4: the computed round findings reach the run bus. A bus
            # that refuses is recorded and does not mark the review itself failed.
            try:
                record["round_review"]["bus_envelopes"] = multi_round_rounds.post_findings(
                    review, wrapper_factory(multi_round_rounds.FINDINGS_AGENT))
            except Exception as exc:
                record["round_review"]["bus"] = {"availability": "failed",
                                                 "error_type": type(exc).__name__}
        except Exception as exc:  # the computed review never takes the case phase down
            record["round_review"] = {"availability": "failed", "error_type": type(exc).__name__}
        record["version_changes"] = version_change_record(ctx, manifest, documents)
        mr.write_record(ctx, record)
        step = time.perf_counter()
        records = computed_records(manifest, record["evidence"])
        record["records"] = records
        import position_gaps
        record["position_gaps"] = position_gaps.gaps(
            manifest, [r for r in records if r["kind"] == "position"])[1]
        mr.project(record)
        measured["records"] = time.perf_counter() - step
        mr.write_record(ctx, record)
        import strategic_support
        record["strategic_layer"] = strategic_support.execute(record, None, wrapper_factory,
                                                              _call, _items, run_objectives)
        if decide is None and suggest is None:
            try:
                built = case_question_calls(ctx, wrapper_factory, manifest["case_id"], documents)
            except Exception as exc:  # recorded by its type: Python's records stand without it
                built = {"why_not": {"movements": "not_built_" + type(exc).__name__,
                                     "suggestions": "not_built_" + type(exc).__name__}}
            decide, suggest = built.get("decide"), built.get("suggest")
            why_not, on_kept, call_log = built.get("why_not"), built.get("on_kept"), built.get("call_log")
        record["case_questions"] = case_question_layer(ctx, record, documents, decide, suggest,
                                                       why_not, on_kept, call_log)
        records = record["records"]
        # A movement a model answered is the model's, so it does not travel as Python's.
        decided = [r for r in records if r.get("movement_decided_by") == "model"]
        if decided:
            wrapper_factory("PROCESSOR").post_to_bus(
                recipient="ORCHESTRATOR", channel="multi_round", msg_type="INFORM",
                body={"event": "MULTI_ROUND_MOVEMENTS_DECIDED", "backend": "case_question",
                      "model": decided[0]["movement_model"],
                      "payload": {"agent": "case_question", "doc_id": manifest["case_id"], "items": decided}},
                constitution_check={"laws_consulted": ["LAW-V"], "result": "RESOLVED",
                                    "resolution": "one fixed-answer question per movement, answered by a model; "
                                                  "not checked by Python and never promoted"})
        # The canonical records reach the existing run bus, as Python's own: the
        # envelope's backend and model say who wrote them (finding_record.written_by).
        wrapper_factory("PROCESSOR").post_to_bus(
            recipient="ORCHESTRATOR", channel="multi_round", msg_type="INFORM",
            body={"event": "MULTI_ROUND_REVIEWED", "backend": "computed", "model": WRITTEN_BY,
                  "payload": {"agent": WRITTEN_BY, "doc_id": manifest["case_id"],
                              "items": [r for r in records if r.get("movement_decided_by") != "model"]}},
            constitution_check={"laws_consulted": ["LAW-I", "LAW-II", "LAW-III", "LAW-IV", "LAW-V"],
                                "result": "RESOLVED",
                                "resolution": "case-scoped records computed in code from the operator's "
                                              "declared sources; no model judged them; no durable promotion"})
        record["outcome"] = "reviewed"
        record["timings"] = step_timings(review, measured, time.perf_counter() - started)
        mr.write_record(ctx, record)
        return 0
    except (mr.InvalidState, ValueError, KeyError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, mr.InvalidState) else "invalid_multi_round_state"
        if record["activation"]["activated"]:
            record["activation"]["reason"] = reason
        else:
            record["activation"] = mr.activation(True, eligible=False, reason=reason)
        record["outcome"] = "refused"
        record["records"] = []
        record["timings"] = step_timings(review, measured, time.perf_counter() - started)
        mr.write_record(ctx, record)
        return 8


def accept_review(manifest, evidence, proposed, decisions, *, producer, verifier):
    """Pre-authored envelopes only. A reviewer may withhold a proposal, never rewrite or invent one."""
    mr.validate_records(manifest, evidence, proposed)
    decisions_by_id = mr.index(decisions, "target_record_id")
    mr.require(set(decisions_by_id).issubset({r["record_id"] for r in proposed}), "review_unknown_target")
    result = []
    for item in proposed:
        r = deepcopy(item)
        d = decisions_by_id.get(r["record_id"])
        if d is None:
            r.update(state="unresolved", confidence="UNCERTAIN", review_state="missing")
        else:
            mr.require(d.get("state") in mr.STATES and d.get("confidence") in {"CONFIDENT", "UNCERTAIN"}, "review_state")
            mr.require(isinstance(d.get("source_ids"), list) and set(d["source_ids"]) == set(r["source_ids"]), "review_evidence")
            # No promotion of a producer refusal or uncertainty by Python.
            r["review_state"] = d["state"]
            if d["state"] != "accepted":
                r["state"] = d["state"]
            if d["confidence"] == "UNCERTAIN":
                r["confidence"] = "UNCERTAIN"
        for prefix, call in [("producer", producer), ("reviewer", verifier)]:
            for field in ["agent", "backend", "model", "call_id"]:
                mr.require(isinstance(call.get(field), str) and call[field], "missing_call_provenance")
                r[prefix + "_" + field] = call[field]
        r["ref_ids"] = [s["ref_id"] for s in evidence if s["source_id"] in r["source_ids"]]
        r.update(item_id=r["record_id"], revision=1, ref=r["record_id"])
        result.append(r)
    # A rejected position cannot leave a dependent movement accepted.
    by_id = {r["record_id"]: r for r in result}
    for r in result:
        if r["kind"] == "movement" and r["state"] == "accepted" and any(
                by_id[r[k]]["state"] != "accepted" for k in ["previous_position_id", "current_position_id"]):
            r.update(state="unresolved", confidence="UNCERTAIN", review_state="position_not_accepted")
    return mr.validate_records(manifest, evidence, result)
