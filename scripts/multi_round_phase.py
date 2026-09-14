"""Explicit positioning phase using existing governed agent execution.

No direct provider/generation API. Tests supply authored replies at the agent
boundary; production callers supply the pipeline's existing wrapper factory.
"""
from copy import deepcopy
import json
from pathlib import Path

import multi_round as mr


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


def execute(ctx, record, documents, reference_index, wrapper_factory, *, sensitive,
            run_objectives=""):
    """Called only on explicit request, after the ordinary startup governance gates.

Sensitive cases refuse before binding sources or constructing wrappers. This
matches the current advisory editorial limitation: no new privacy release path.
The case path returns before ordinary ontology/end-work capture.
"""
    mr.require(record["run_id"] == ctx.run_id, "run_identity")
    try:
        mr.require(sensitive is False, "sensitive_multi_round_unavailable")
        manifest = mr.validate_manifest(record["manifest"])
        mr.require(not manifest["fixture"], "fixture_requires_offline_test_adapter")
        record["evidence"] = mr.bind_sources(manifest, documents, reference_index)
        record["activation"] = mr.activation(True, eligible=True, reached=True)
        mr.write_record(ctx, record)
        contracts = json.loads((Path(__file__).resolve().parent.parent / "config" /
                               "multi_round_contracts.json").read_text(encoding="utf-8"))
        producer = wrapper_factory("PROCESSOR")
        verifier = wrapper_factory("VERIFIER")
        # Same backend means no independent audit family. The existing local
        # profiles explicitly distinguish producer and auditor implementations.
        mr.require(producer.backend != verifier.backend and producer.model != verifier.model,
                   "independent_review_unavailable")
        reply = _call(producer, contracts["PROCESSOR"],
                      {"case": manifest, "evidence": record["evidence"]}, manifest["case_id"], run_objectives)
        proposed = _items(reply, "PROCESSOR", manifest["case_id"])
        mr.validate_records(manifest, record["evidence"], proposed)
        reviewed = _call(verifier, contracts["VERIFIER"],
                         {"case": manifest, "evidence": record["evidence"], "proposals": proposed},
                         manifest["case_id"], run_objectives)
        decisions = _items(reviewed, "VERIFIER", manifest["case_id"])
        records = accept_review(manifest, record["evidence"], proposed, decisions,
                                producer=reply, verifier=reviewed)
        record["records"] = records
        mr.project(record)
        mr.write_record(ctx, record)
        import strategic_support
        record["strategic_layer"] = strategic_support.execute(record, None, wrapper_factory,
                                                              _call, _items, run_objectives)
        # The canonical accepted/refused records reach the existing run bus.
        producer.post_to_bus(recipient="ORCHESTRATOR", channel="multi_round", msg_type="INFORM",
            body={"event": "MULTI_ROUND_REVIEWED", "payload": {
                "agent": "PROCESSOR", "doc_id": manifest["case_id"], "items": records}},
            constitution_check={"laws_consulted": ["LAW-I", "LAW-II", "LAW-III", "LAW-IV", "LAW-V"],
                                "result": "RESOLVED", "resolution": "case-scoped reviewed output; no durable promotion"})
        record["outcome"] = "reviewed"
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
        mr.write_record(ctx, record)
        return 8


def accept_review(manifest, evidence, proposed, decisions, *, producer, verifier):
    """A reviewer may withhold a proposal, never rewrite or invent one."""
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
