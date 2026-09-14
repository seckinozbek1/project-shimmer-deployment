"""Case-scoped typed positioning. No semantic classification is computed here.

The input is operator-declared identity and source spans. PROCESSOR supplies
interpretations and VERIFIER reviews them through the existing agent boundary.
All projections below also accept pre-authored envelopes for offline proofs.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path

BASELINE = "47c63aca09603ab5c7ad662753d647397a623ce8"
STATES = {"accepted", "rejected", "refused", "unresolved", "insufficient_evidence",
          "not_comparable", "unknown"}
KINDS = {"position", "movement", "unresolved_issue", "trajectory", "decision_support"}
MOVEMENTS = {"concession", "hardening", "reversal", "stable", "ambiguous", "unknown"}
CATEGORIES = {"observed_evidence", "semantic_interpretation", "recommendation"}


class InvalidState(ValueError):
    """Structural refusal; messages contain field names, never source content."""


def require(ok, reason):
    if not ok:
        raise InvalidState(reason)


def identifier(value):
    return isinstance(value, str) and 0 < len(value) <= 128 and all(
        c.isascii() and (c.isalnum() or c in "_-.") for c in value)


def finite_number(value):
    try:
        return type(value) in (float, int) and math.isfinite(value)
    except OverflowError:
        return False


def index(rows, key):
    require(isinstance(rows, list), "expected_list")
    out = {}
    for row in rows:
        require(isinstance(row, dict) and identifier(row.get(key)), "invalid_identity")
        require(row[key] not in out, "duplicate_identity")
        out[row[key]] = row
    return out


def validate_manifest(value):
    require(isinstance(value, dict) and value.get("schema_version") == 1, "schema_version")
    require(identifier(value.get("case_id")), "case_identity")
    require(type(value.get("fixture")) is bool, "fixture_declaration")
    require(type(value.get("allow_recommendations", False)) is bool, "advice_declaration")
    rounds = index(value.get("rounds"), "round_id")
    actors = index(value.get("actors"), "actor_id")
    issues = index(value.get("issues"), "issue_id")
    sources = index(value.get("sources"), "source_id")
    require(len(rounds) >= 2 and actors and issues, "case_needs_rounds_actors_issues")
    orders, docs = set(), set()
    for r in rounds.values():
        n = r.get("sequence")
        require(type(n) is int and 0 < n <= 10000 and n not in orders, "round_order")
        orders.add(n)
        ids = r.get("document_ids")
        require(isinstance(ids, list) and all(identifier(x) for x in ids), "round_documents")
        require(len(ids) == len(set(ids)) and not docs.intersection(ids), "document_round_collision")
        docs.update(ids)
    for s in sources.values():
        require(s.get("round_id") in rounds and s.get("actor_id") in actors
                and s.get("issue_id") in issues, "source_identity_link")
        require(s.get("document_id") in rounds[s["round_id"]]["document_ids"], "source_round_link")
        require(identifier(s.get("unit_id")), "source_unit")
        require(type(s.get("char_start")) is int and type(s.get("char_end")) is int
                and 0 <= s["char_start"] < s["char_end"], "source_span")
        require(isinstance(s.get("quote"), str) and s["quote"], "source_quote")
        require(s.get("state") in STATES, "source_state")
    return deepcopy(value)


def activation(requested=False, *, eligible=None, reached=False, reason=None):
    require(type(requested) is bool, "explicit_activation_required")
    require(eligible is None or type(eligible) is bool, "eligible_state")
    require(type(reached) is bool and (not reached or eligible is True), "activation_transition")
    if not requested:
        return {"requested": False, "eligible": False, "activated": False,
                "state": "not_requested", "reason": None}
    state = "refused" if eligible is False else "activated" if reached else "phase_not_reached"
    return {"requested": True, "eligible": eligible, "activated": reached and eligible is True,
            "state": state, "reason": reason}


def normalize_request(requested, manifest):
    require(type(requested) is bool, "explicit_activation_required")
    if not requested:
        require(manifest is None, "manifest_requires_explicit_request")
        return None
    return validate_manifest(manifest)


def write_record(ctx, record):
    require(record.get("run_id") == ctx.run_id, "run_identity")
    path = ctx.multi_round_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def begin(ctx, manifest):
    record = {"schema_version": 1, "run_id": ctx.run_id, "baseline_commit": BASELINE,
              "activation": activation(True), "manifest": validate_manifest(manifest),
              "fixture": manifest["fixture"], "records": [], "evidence": []}
    write_record(ctx, record)
    return record


def bind_sources(manifest, documents, reference_index):
    """Exact operator span validation, then existing REF index allocation."""
    docs = index(documents, "id")
    evidence = []
    for source in manifest["sources"]:
        s = deepcopy(source)
        require(s["document_id"] in docs, "missing_source_document")
        doc = docs[s["document_id"]]
        text = doc.get("text", "")
        require(text[s["char_start"]:s["char_end"]] == s["quote"], "source_span_mismatch")
        entry = reference_index.add(input_type="operational", document_id=s["document_id"],
            document_name=doc.get("name", s["document_id"]),
            location={"char_start": s["char_start"], "char_end": s["char_end"], "unit_id": s["unit_id"]},
            text_excerpt=s["quote"])
        s["ref_id"] = entry.ref_id
        evidence.append(s)
    reference_index.save()
    return evidence


def validate_records(manifest, evidence, records):
    """Validate identity/evidence graphs, not the meaning of any claim."""
    validate_manifest(manifest)
    sources = index(evidence, "source_id")
    declared = index(manifest["sources"], "source_id")
    require(set(sources) == set(declared), "evidence_inventory")
    for sid, s in sources.items():
        require(all(s.get(k) == v for k, v in declared[sid].items()), "evidence_binding")
        require(identifier(s.get("ref_id")), "evidence_reference")
    rows = index(records, "record_id")
    rounds = index(manifest["rounds"], "round_id")
    actors = index(manifest["actors"], "actor_id")
    issues = index(manifest["issues"], "issue_id")
    for row in rows.values():
        require(all(v is None or type(v) in (str, bool, int, float) or
                    isinstance(v, list) and all(x is None or type(x) in (str, bool, int, float) for x in v)
                    for v in row.values()), "flat_record_required")
        require(row.get("kind") in KINDS and row.get("state") in STATES, "record_kind_state")
        require(row.get("case_id") == manifest["case_id"], "record_case")
        require(row.get("confidence") in {"CONFIDENT", "UNCERTAIN"}, "record_confidence")
        require(row.get("category") in CATEGORIES, "claim_category")
        if row["category"] == "recommendation":
            require(manifest.get("allow_recommendations") is True and row["kind"] == "decision_support", "advice_not_requested")
        require(isinstance(row.get("text"), str), "claim_text")
        require(row.get("actor_id") in actors and row.get("issue_id") in issues, "record_actor_issue")
        require(row.get("round_id") in rounds, "record_round")
        refs = row.get("source_ids")
        require(isinstance(refs, list) and all(identifier(s) for s in refs) and len(refs) == len(set(refs)) and
                all(s in sources for s in refs), "record_sources")
        participants = row.get("actor_ids", [row["actor_id"]])
        require(isinstance(participants, list) and participants and all(a in actors for a in participants)
                and row["actor_id"] in participants, "claim_participants")
        if row["kind"] in {"position", "movement"}:
            require(participants == [row["actor_id"]], "single_actor_position")
        for sid in refs:
            s = sources[sid]
            require(s["actor_id"] in participants and s["issue_id"] == row["issue_id"], "evidence_actor_issue")
            require(rounds[s["round_id"]]["sequence"] <= rounds[row["round_id"]]["sequence"], "future_round_evidence")
        if row["state"] == "accepted":
            require(refs and all(sources[s]["state"] == "accepted" for s in refs), "insufficient_evidence")
        if row["kind"] == "position":
            require(all(sources[s]["round_id"] == row["round_id"] for s in refs), "evidence_wrong_round")
            require(isinstance(row.get("position"), str), "typed_position")
            if "value" in row:
                require(finite_number(row["value"])
                        and isinstance(row.get("unit"), str) and row["unit"], "numeric_position")
        else:
            prior = row.get("previous_round_id")
            require(prior in rounds and rounds[prior]["sequence"] < rounds[row["round_id"]]["sequence"], "comparison_order")
            if row["state"] == "accepted":
                support = {sources[s]["round_id"] for s in refs}
                require(prior in support and row["round_id"] in support, "cross_round_evidence")
                require(all({prior, row["round_id"]}.issubset({sources[s]["round_id"] for s in refs
                            if sources[s]["actor_id"] == actor}) for actor in participants), "participant_round_evidence")
            if row["kind"] == "movement":
                require(row.get("movement") in MOVEMENTS, "movement_category")
                for key, rid in [("previous_position_id", prior), ("current_position_id", row["round_id"])]:
                    p = rows.get(row.get(key))
                    if row.get(key) is None and row["state"] != "accepted":
                        continue
                    require(p is not None and p["kind"] == "position" and p["actor_id"] == row["actor_id"]
                            and p["issue_id"] == row["issue_id"] and p["round_id"] == rid, "movement_position_link")
                    if row["state"] == "accepted":
                        require(p["state"] == "accepted" and set(p["source_ids"]).issubset(refs), "movement_support")
    return deepcopy(records)


def project(record):
    """One master, all operator views. Absence never carries a position forward."""
    manifest = record["manifest"]
    rows = validate_records(manifest, record["evidence"], record["records"])
    rounds = sorted(manifest["rounds"], key=lambda r: r["sequence"])
    accepted = [r for r in rows if r["state"] == "accepted"]
    positions = [r for r in accepted if r["kind"] == "position"]
    timeline = [{"round_id": r["round_id"], "sequence": r["sequence"],
                 "positions": [p for p in positions if p["round_id"] == r["round_id"]]} for r in rounds]
    comparisons = []
    for m in accepted:
        if m["kind"] != "movement":
            continue
        by_id = {p["record_id"]: p for p in positions}
        previous, current = by_id[m["previous_position_id"]], by_id[m["current_position_id"]]
        comparison = {"movement_id": m["record_id"], "category": "derived_structural_comparison",
                      "typed_position_equal": previous["position"] == current["position"],
                      "previous_position_id": previous["record_id"], "current_position_id": current["record_id"]}
        if "value" in previous and "value" in current and previous["unit"] == current["unit"]:
            delta = current["value"] - previous["value"]
            if finite_number(delta):
                comparison.update(delta=delta, unit=current["unit"])
            else:
                comparison["delta_state"] = "not_comparable"
        comparisons.append(comparison)
    return {"case_id": manifest["case_id"], "rounds": rounds, "actors": manifest["actors"], "issues": manifest["issues"],
            "timeline": timeline, "current_positions": timeline[-1]["positions"],
            "actor_history": {a["actor_id"]: [p for r in timeline for p in r["positions"] if p["actor_id"] == a["actor_id"]] for a in manifest["actors"]},
            "issue_history": {i["issue_id"]: [p for r in timeline for p in r["positions"] if p["issue_id"] == i["issue_id"]] for i in manifest["issues"]},
            "missing_sequences": [n for n in range(1, rounds[-1]["sequence"]) if n not in {r["sequence"] for r in rounds}],
            "movements": [r for r in accepted if r["kind"] == "movement"],
            "unresolved": [r for r in rows if r["state"] != "accepted" or r["kind"] == "unresolved_issue"],
            "trajectory": [r for r in accepted if r["kind"] == "trajectory"],
            "decision_support": [r for r in accepted if r["kind"] == "decision_support"],
            "structural_comparisons": comparisons, "evidence": record["evidence"], "records": rows}


def read_saved(run_dir, run_id):
    from run_context import RunContext
    path = RunContext(Path(run_dir).parent, run_id, Path(run_dir)).multi_round_path()
    if not path.exists():
        try:
            status = json.loads((Path(run_dir) / "status.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            status = {}
        if (isinstance(status, dict) and status.get("multi_round") is True) or (
                Path(run_dir) / "audit/multi_round_request.json").exists():
            return {"recorded": False, "activation": activation(True, eligible=False, reason="missing_case_record"),
                    "availability": "unavailable"}
        return {"recorded": False, "activation": activation(), "availability": "not_recorded"}
    try:
        r = json.loads(path.read_text(encoding="utf-8"))
        require(r["run_id"] == run_id and r["schema_version"] == 1, "run_identity")
        require(r.get("baseline_commit") == BASELINE, "baseline_identity")
        require(r["fixture"] == r["manifest"]["fixture"] and type(r["fixture"]) is bool, "fixture_identity")
        validate_manifest(r["manifest"])
        a = r["activation"]
        require(a == activation(True, eligible=a["eligible"], reached=a["activated"], reason=a["reason"]), "activation_record")
        view = project(r) if a["activated"] else None
        if view is not None:
            refs = json.loads((Path(run_dir) / "audit/reference_index.json").read_text(encoding="utf-8"))
            by_ref = index(refs["entries"], "ref_id")
            for s in r["evidence"]:
                entry = by_ref.get(s["ref_id"])
                require(entry is not None and entry["document_id"] == s["document_id"] and
                        all(entry["location"].get(k) == s[k] for k in ["unit_id", "char_start", "char_end"]), "saved_reference_binding")
        return {"recorded": True, "run_id": run_id, "activation": a, "fixture": r["fixture"], "view": view,
                "availability": "recorded", "outcome": r.get("outcome", "phase_not_completed"), "baseline_commit": BASELINE}
    except (OSError, ValueError, KeyError, TypeError):
        return {"recorded": False, "availability": "invalid", "activation": activation(True, eligible=False, reason="invalid_saved_state")}
