"""Validate and display advisory proposals; never infer a strategy from movement."""
from copy import deepcopy
import html
import json
from pathlib import Path
import multi_round as mr
import run_options

MODES = {"trajectory_only", "decision_support", "strategic_options", "recommendation"}
TYPES = {"OBSERVED", "INTERPRETED", "DERIVED", "STRATEGIC_OPTION", "RECOMMENDATION"}


def mode(manifest):
    selected = manifest.get("decision_support_mode", "trajectory_only")
    mr.require(isinstance(selected, str) and selected in MODES, "decision_support_mode")
    if selected == "recommendation":
        mr.require(manifest.get("allow_recommendations") is True, "recommendations_require_explicit_permission")
    return selected


def validate(record, layer):
    selected = mode(record["manifest"])
    mr.require(isinstance(layer, dict) and type(layer.get("schema_version")) is int and layer["schema_version"] == 1, "strategy_schema")
    mr.require(layer.get("mode") == selected, "strategy_mode_mismatch")
    mr.require(layer.get("state") in {"trajectory_only", "decision_support", "strategic_options", "recommendation",
               "recommendation_unavailable", "insufficient_evidence"}, "strategy_state")
    rows = mr.index(layer.get("items"), "record_id")
    mr.require(not set(rows).intersection(r["record_id"] for r in record["records"]), "strategy_identity_collision")
    mr.validate_records(record["manifest"], record["evidence"], record["records"])
    sources = mr.index(record["evidence"], "source_id")
    interpretations = {r["record_id"]: r for r in record["records"] if r["state"] == "accepted" and r["category"] != "recommendation"}
    trajectories = {k: r for k, r in interpretations.items() if r["kind"] in {"movement", "trajectory"}}
    if selected in {"trajectory_only", "decision_support"}:
        mr.require(not rows, "strategy_not_available")
        mr.require(layer["state"] == selected, "strategy_state_mode_mismatch")
    if selected == "strategic_options":
        mr.require(layer["state"] != "recommendation", "recommendation_not_requested")
    if layer["state"] in {"insufficient_evidence", "recommendation_unavailable"}:
        mr.require(not any(r.get("state") == "accepted" for r in rows.values()), "unavailable_strategy_cannot_be_accepted")
    for row in rows.values():
        mr.require("category" not in row, "strategy_cannot_override_claim_type")
        if "case_id" in row:
            mr.require(row["case_id"] == record["manifest"]["case_id"], "strategy_case_identity")
        mr.require(row.get("type") in {"STRATEGIC_OPTION", "RECOMMENDATION"}, "strategy_type")
        mr.require(row.get("confidence") in {"CONFIDENT", "UNCERTAIN"}, "strategy_uncertainty")
        mr.require(row.get("state") in mr.STATES, "strategy_item_state")
        for key in ("action", "upside", "risk", "uncertainty"):
            mr.require(isinstance(row.get(key), str) and bool(row[key].strip()), "strategy_" + key)
        mr.require(isinstance(row.get("assumptions"), list) and all(isinstance(a, str) and a.strip() for a in row["assumptions"]), "strategy_assumptions")
        for key, known in (("source_ids", sources), ("interpretation_ids", interpretations), ("trajectory_ids", trajectories)):
            ids = row.get(key)
            mr.require(isinstance(ids, list) and ids and all(isinstance(i, str) and i in known for i in ids)
                       and len(set(ids)) == len(ids), "strategy_" + key)
        mr.require(all(sources[s]["state"] == "accepted" for s in row["source_ids"]), "strategy_unaccepted_evidence")
        if "ref_ids" in row:
            mr.require(isinstance(row["ref_ids"], list) and set(row["ref_ids"]) == {sources[s]["ref_id"] for s in row["source_ids"]}, "strategy_reference_binding")
        for link in row["interpretation_ids"] + row["trajectory_ids"]:
            mr.require(set(interpretations[link]["source_ids"]).issubset(row["source_ids"]), "strategy_incomplete_evidence")
            if interpretations[link]["confidence"] == "UNCERTAIN":
                mr.require(row["confidence"] == "UNCERTAIN", "strategy_cannot_erase_uncertainty")
        for field, source_field, catalog in (("actor_ids", "actor_id", "actors"), ("issue_ids", "issue_id", "issues"), ("round_ids", "round_id", "rounds")):
            ids = row.get(field)
            declared = {r[source_field] for r in record["manifest"][catalog]}
            mr.require(isinstance(ids, list) and ids and all(isinstance(i, str) and i in declared for i in ids)
                       and len(ids) == len(set(ids)), "strategy_scope")
            mr.require(set(ids) == {sources[s][source_field] for s in row["source_ids"]}, "strategy_evidence_scope")
        options = row.get("option_ids", [])
        mr.require(isinstance(options, list) and all(isinstance(i, str) for i in options) and len(set(options)) == len(options), "strategy_option_links")
        if row["type"] == "RECOMMENDATION":
            mr.require(selected == "recommendation" and bool(options), "recommendation_not_requested")
            for key in options:
                option = rows.get(key)
                mr.require(option is not None and option.get("type") == "STRATEGIC_OPTION", "recommendation_option")
                if row["state"] == "accepted":
                    mr.require(option.get("state") == "accepted", "recommendation_unaccepted_option")
                for field in ("source_ids", "interpretation_ids", "trajectory_ids"):
                    mr.require(set(option[field]).issubset(row[field]), "recommendation_provenance")
                mr.require(set(option["assumptions"]).issubset(row["assumptions"]), "recommendation_assumptions")
                if option["confidence"] == "UNCERTAIN":
                    mr.require(row["confidence"] == "UNCERTAIN", "recommendation_cannot_erase_uncertainty")
        else:
            mr.require(not options, "option_cannot_recommend_itself")
        # Persisted accepted advice must have an independent review, not only a producer assertion.
        if layer.get("reviewed") is True and row["state"] == "accepted":
            mr.require(row.get("review_state") == "accepted", "strategy_review_missing")
            for prefix in ("producer", "reviewer"):
                for field in ("agent", "backend", "model", "call_id"):
                    mr.require(isinstance(row.get(prefix + "_" + field), str) and row[prefix + "_" + field], "strategy_call_provenance")
            mr.require(row["producer_backend"] != row["reviewer_backend"] and row["producer_model"] != row["reviewer_model"], "strategy_independent_review")
            mr.require(row["producer_agent"] == "PROCESSOR" and row["reviewer_agent"] == "VERIFIER"
                       and row["producer_call_id"] != row["reviewer_call_id"], "strategy_review_identity")
    return deepcopy(layer)


def empty(record, state=None):
    selected = mode(record["manifest"])
    return {"schema_version": 1, "mode": selected,
            "state": state or (selected if selected in {"trajectory_only", "decision_support"} else "recommendation_unavailable"),
            "items": [], "reviewed": False}


def reviewed(record, proposals, decisions, producer, reviewer):
    layer = dict(schema_version=1, mode=mode(record["manifest"]), state=mode(record["manifest"]), items=deepcopy(proposals))
    validate(record, layer)
    verdicts = mr.index(decisions, "target_record_id")
    mr.require(set(verdicts).issubset({r["record_id"] for r in proposals}), "strategy_unknown_review_target")
    for row in layer["items"]:
        verdict = verdicts.get(row["record_id"])
        if verdict is None:
            row.update(state="unresolved", confidence="UNCERTAIN", review_state="missing")
        else:
            mr.require(verdict.get("state") in mr.STATES and verdict.get("confidence") in {"CONFIDENT", "UNCERTAIN"}, "strategy_review_state")
            mr.require(set(verdict.get("source_ids", [])) == set(row["source_ids"]), "strategy_review_sources")
            row["review_state"] = verdict["state"]
            if verdict["state"] != "accepted":
                row["state"] = verdict["state"]
            if verdict["confidence"] == "UNCERTAIN":
                row["confidence"] = "UNCERTAIN"
        for prefix, call in (("producer", producer), ("reviewer", reviewer)):
            for field in ("agent", "backend", "model", "call_id"):
                row[prefix + "_" + field] = call.get(field)
        row["ref_ids"] = [s["ref_id"] for s in record["evidence"] if s["source_id"] in row["source_ids"]]
        row["case_id"] = record["manifest"]["case_id"]
    # Refused options cannot leave a recommendation accepted. Preserve rejected rows for audit.
    by_id = {r["record_id"]: r for r in layer["items"]}
    for row in layer["items"]:
        if row["type"] == "RECOMMENDATION" and any(by_id[o]["state"] != "accepted" for o in row["option_ids"]):
            row.update(state="unresolved", confidence="UNCERTAIN")
    layer["reviewed"] = True
    accepted_types = {r["type"] for r in layer["items"] if r["state"] == "accepted"}
    layer["state"] = ("recommendation" if "RECOMMENDATION" in accepted_types else
                      "strategic_options" if "STRATEGIC_OPTION" in accepted_types else "insufficient_evidence")
    # Validation still binds rejected recommendation links but does not promote them.
    return validate(record, layer)


def execute(record, contracts, wrapper_factory, call, items, objectives):
    """Explicit optional calls through the same governed wrapper and independent audit.

    A strategy failure never deletes already validated trajectory records.
    This path is tested only with pre-authored wrappers, not real generation.
    """
    selected = mode(record["manifest"])
    if selected in {"trajectory_only", "decision_support"}:
        return empty(record)
    if not any(r["kind"] in {"movement", "trajectory"} and r["state"] == "accepted" for r in record["records"]):
        return empty(record, "insufficient_evidence")
    try:
        if contracts is None:
            contracts = json.loads((Path(__file__).resolve().parent.parent / "config/strategic_support_contracts.json").read_text(encoding="utf-8"))
        producer, verifier = wrapper_factory("PROCESSOR"), wrapper_factory("VERIFIER")
        mr.require(producer.backend != verifier.backend and producer.model != verifier.model, "strategy_independent_review")
        case_id = record["manifest"]["case_id"]
        payload = {"task": "strategic_decision_support", "mode": selected, "case": record["manifest"],
                   "evidence": record["evidence"], "interpretations_and_trajectory": record["records"]}
        reply = call(producer, contracts["PROCESSOR"], payload, case_id, objectives)
        proposed = items(reply, "PROCESSOR", case_id)
        validate(record, dict(schema_version=1, mode=selected, state=selected, items=proposed))
        reviewed_reply = call(verifier, contracts["VERIFIER"], dict(payload, proposals=proposed), case_id, objectives)
        decisions = items(reviewed_reply, "VERIFIER", case_id)
        return reviewed(record, proposed, decisions, reply, reviewed_reply)
    except Exception as exc:
        unavailable = empty(record, "recommendation_unavailable")
        unavailable["error_type"] = type(exc).__name__
        return unavailable


def project(record, language="en"):
    run_options.Options(output_language=language)
    layer = validate(record, record.get("strategic_layer", empty(record)))
    mr.require(layer.get("reviewed") is True or not layer["items"], "unreviewed_strategy_not_publishable")
    view = mr.project(record)
    nodes = [{"type": "OBSERVED", "id": s["source_id"], "text": s["quote"], "ref_ids": [s["ref_id"]],
              "actor_id": s["actor_id"], "issue_id": s["issue_id"], "round_id": s["round_id"], "state": s["state"]} for s in view["evidence"]]
    nodes += [dict(type="INTERPRETED", id=r["record_id"], text=r["text"], stage=r["kind"],
                   confidence=r["confidence"], state=r["state"], source_ids=r["source_ids"],
                   movement=r.get("movement"), movement_label=run_options.label(r.get("movement", ""), language))
              for r in view["records"] if r["category"] != "recommendation"]
    nodes += [dict(type="DERIVED", id="comparison-" + c["movement_id"], comparison=deepcopy(c)) for c in view["structural_comparisons"]]
    nodes += [deepcopy(r) for r in layer["items"]]
    for node in nodes:
        node["display_label"] = run_options.label(node["type"], language)
        node["display_state"] = run_options.label(node.get("state", ""), language)
    return dict(schema_version=1, output_language=language, state=layer["state"], layers=nodes,
                quality="UNVERIFIED", mode=layer["mode"], state_label=run_options.label(layer["state"], language))


def render_html(view):
    # Escape both authored prose and identifiers; localization never rewrites payloads.
    out = []
    for node in view["layers"]:
        out.append("<section><h3>" + html.escape(node["display_label"]) + "</h3><pre>" +
                   html.escape(json.dumps(node, ensure_ascii=False, indent=2)) + "</pre></section>")
    return "".join(out)
