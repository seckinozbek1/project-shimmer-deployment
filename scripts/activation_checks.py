"""Executed activation evidence checks, with model dispatch replaced at the boundary."""
import asyncio
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import tempfile
import traceback
import itertools
from types import SimpleNamespace
from unittest.mock import patch

import agent_activation as activation
import agent_wrapper as aw
import pipeline
from effect_proof import prove_effect, ProofFailure
from harness.run_agent import build_orchestrator
from reference_builder import ReferenceIndex

ROOT = Path(__file__).resolve().parent.parent


def _fixture_mask(stable, dynamic, **kwargs):
    return stable.replace("routing-fixture-span", "[REDACTED]"), dynamic.replace("routing-fixture-span", "[REDACTED]")


@patch.dict(os.environ, {"SHIMMER_BACKEND_PROFILE": "local"})
def _exercise(profile="sparse", assignment="one", scenario="wide", audited=True):
    calls = []
    with tempfile.TemporaryDirectory() as temporary:
        orch = build_orchestrator(ROOT, Path(temporary))
        for name, (backend, model) in pipeline._LOCAL_PROFILE.items():
            orch.registry[name].update(backend=backend, model=model)
        # The disposable fixture starts from the same empty bus. Freeze only its
        # timestamps/call identities so prompt parity is byte-comparable.
        orch.bus.path.write_text("", encoding="utf-8")
        post = orch.bus.post
        orch.bus.post = lambda message: post(dict(message, timestamp="2026-01-01T00:00:00+00:00"))
        ctx = orch.run_context
        audit = activation.initialize(ctx, orch.registry, profile) if audited else None
        doc = {"id": "probe", "name": "probe.md", "text": "## Entry A\nA declared source passage.\n"}
        registry = {"conventions": [{"id": "CONV-001", "subjects": ["conformance"],
                    "category": "operator-rule", "severity": "required", "rule": "Review the declared source."}]}
        assignment_data = {
            "by_rule": {"CONV-001": {"status": "assigned", "consumer_agents": ["PRACTICE_AUDITOR"]}},
            "by_agent": {"PRACTICE_AUDITOR": ["CONV-001"], "STYLE_GUARDIAN": []}}
        if assignment == "unknown":
            assignment_data = None
        elif assignment == "untagged":
            assignment_data["by_rule"]["CONV-001"]["status"] = "untagged"

        def dispatch(wrapper, stable, dynamic, **kwargs):
            calls.append({"agent": wrapper.name, "call_id": wrapper._cost_call_id,
                          "prompt": hashlib.sha256((stable + dynamic).encode()).hexdigest(),
                          "egress_masked": "routing-fixture-span" not in stable + dynamic and "[REDACTED]" in stable + dynamic})
            if scenario == "exception":
                raise RuntimeError("fixture failure")
            if scenario == "contract":
                return aw.CallResult(wrapper.backend, wrapper.model, "not a valid envelope")
            if scenario == "backend":
                return aw.CallResult(wrapper.backend, wrapper.model, "", ok=False, error="fixture")
            items = []
            if wrapper.name.startswith("EDITOR_"):
                items = [{"ref": "REF-001", "kind": "editorial_observation", "verdict": "sound", "rationale": "Fixture observation.",
                          "confidence": 0.2 if scenario == "escalate" else 0.9,
                          "out_of_mandate": scenario == "mandate"}]
            return aw.CallResult(wrapper.backend, wrapper.model,
                json.dumps({"agent": wrapper.name, "doc_id": doc["id"], "items": items}))

        keys = {"offline_fixture": True}
        identities = itertools.count(1)
        with patch.object(aw.AgentWrapper, "dispatch", dispatch), patch.object(
                aw.uuid, "uuid4", lambda: SimpleNamespace(hex="%032x" % next(identities))):
            if scenario in ("wide", "paired_unresolved"):
                asyncio.run(pipeline.phase_5_5_convention_review(
                    orch, keys, [doc], "Fixture objective", registry, ReferenceIndex(ROOT),
                    review_mode="paired" if scenario == "paired_unresolved" else "wide",
                    convention_assignment=assignment_data))
            elif scenario in ("board", "escalate", "mandate", "sensitive", "missing_master"):
                master = Path(temporary) / "master.json"
                master.write_text('{"amendments": []}', encoding="utf-8")
                deliverables = {} if scenario == "missing_master" else {doc["id"]: {"amendments_json": str(master)}}
                pipeline.phase_6_5_editorial_review(orch, keys, [doc], deliverables, ctx, registry,
                    run_is_non_sensitive=scenario != "sensitive",
                    board_tunables={"max_rounds": 5 if scenario == "mandate" else 2, "max_tokens": 100,
                                    "confidence_threshold": 0.7, "out_of_mandate_trigger": True})
            elif scenario == "roster":
                for name in orch.registry:
                    pipeline._build_wrapper(name, orch, keys).run_task(
                        work_payload={"task": "fixture_identity", "document_id": doc["id"]})
            elif scenario == "production":
                production = asyncio.run(pipeline.phase_3_4_content_production(
                    orch, keys, [doc], [], "Fixture objective", registry, ReferenceIndex(ROOT), []))
                asyncio.run(pipeline.phase_5_audit(orch, keys, [doc], production,
                    "Fixture objective", registry, ReferenceIndex(ROOT)))
            elif scenario == "deepen":
                wrapper = pipeline._build_wrapper("LEGAL_ANALYST", orch, keys)
                findings = [{"item_id": "item-%d" % n, "claim_id": "claim-%d" % n,
                             "reasoning": "Fixture finding."} for n in range(8)]
                asyncio.run(pipeline._deepen_legal_analyst_findings_local(
                    wrapper, findings, doc, None, "Fixture objective"))
            elif scenario in ("polish", "polish_empty"):
                item = {"relation": pipeline.finding_record.relations()[0],
                        "record_verdict": "irregular", "unit_id": "entry-a", "rule_id": "CONV-001"}
                findings = [] if scenario == "polish_empty" else [
                    {"kind": "extraction"}, dict(item, record_verdict="ok"), item]
                result, count = asyncio.run(pipeline._polish_findings(
                    orch, keys, doc, findings, {}, {}, "Fixture objective", registry))
                assert result == findings and count == 0
            elif scenario in ("redact", "redact_waived", "redact_no_rules"):
                from sensitivity_layer.redaction_stage import run_redaction_phase
                red_registry = {"conventions": [] if scenario == "redact_no_rules" else [
                    {"id": "CONV-X", "category": "conv-confidentiality", "action": "flag",
                     "rule": "must not contain an individual's identity number"}]}
                master = Path(temporary) / "master.json"
                master.write_text('{"amendments": []}', encoding="utf-8")
                summary = run_redaction_phase(orch, [doc],
                    {doc["id"]: {"amendments_json": str(master)}}, ctx, red_registry,
                    build_wrapper=lambda name: pipeline._build_wrapper(name, orch, keys),
                    render_deliverable=lambda *args: None,
                    redaction_enabled=scenario != "redact_waived")
                expected = {"redact": "NONE", "redact_waived": "SKIPPED", "redact_no_rules": "BLOCKED"}
                assert summary[doc["id"]]["state"] == expected[scenario]
            else:
                wrapper = pipeline._build_wrapper("PROCESSOR", orch, keys)
                arguments = {}
                payload = {"task": "per_document_analysis", "document_id": doc["id"]}
                if scenario in ("masked_egress", "masking_refusal"):
                    wrapper.backend = "claude_api"
                    payload["document_text"] = "routing-fixture-span"
                    def refuse(*args, **kwargs):
                        raise PermissionError("fixture masking refusal")
                    wrapper.outbound_masker = refuse if scenario == "masking_refusal" else _fixture_mask
                if scenario == "bad_budget":
                    wrapper.contract = {}
                    wrapper.backend = "local_producer"
                    arguments["max_tokens"] = None
                try:
                    wrapper.run_task(work_payload=payload, **arguments)
                except (RuntimeError, TypeError, PermissionError):
                    if scenario not in ("exception", "bad_budget", "masking_refusal"):
                        raise
        rows = json.loads(audit.path.read_text(encoding="utf-8"))["decisions"] if audit else []
        # This observation joins independently intercepted dispatches to saved audit
        # rows. Counting only written records could certify a disconnected recorder.
        actual = [row for row in rows if row["actual_call"]]
        joined = sorted((r["agent"], r["call_id"]) for r in actual) == sorted(
            (r["agent"], r["call_id"]) for r in calls)
        return {
            "calls": [c["agent"] for c in calls], "prompts": [c["prompt"] for c in calls],
            "egress_masked": bool(calls) and all(c["egress_masked"] for c in calls),
            "joined": joined,
            "rows": [{k: r[k] for k in ("agent", "eligible", "activated", "reason", "state",
                                        "actual_call", "refire_count", "refire_limit", "evidence", "doc_id")}
                     for r in rows],
        }


def check():
    try:
        one = _exercise()
        assert one["calls"] == ["PRACTICE_AUDITOR"] and one["joined"]
        assert any(r["agent"] == "STYLE_GUARDIAN" and not r["activated"] for r in one["rows"])
        for evidence in ("unknown", "untagged"):
            outcome = _exercise(assignment=evidence)
            assert outcome["calls"] == list(pipeline.CONVENTION_REVIEW_AGENTS) and outcome["joined"]
        for scenario in ("wide", "production", "board", "escalate", "mandate", "roster",
                         "deepen", "contract", "backend", "exception", "bad_budget",
                         "polish", "polish_empty", "redact", "redact_waived", "redact_no_rules",
                         "masked_egress", "masking_refusal"):
            sparse = _exercise(scenario=scenario)
            dense = _exercise("dense", scenario=scenario)
            original = _exercise("dense", scenario=scenario, audited=False)
            assert sparse["joined"] and dense["joined"], scenario
            assert sparse["calls"] == dense["calls"] == original["calls"], scenario
            # Bus UUIDs/timestamps are pre-existing prompt variation; compare single
            # call prompts below and counts/contract outcomes for multi-call routes.
            if len(sparse["calls"]) == 1:
                assert sparse["prompts"] == dense["prompts"] == original["prompts"], scenario
            if scenario == "escalate":
                assert sparse["calls"] == list(pipeline._EDITORIAL_RANKS[:3])
                assert any(r["reason"] == "editorial_round_cap" for r in sparse["rows"])
            if scenario == "mandate":
                assert sparse["calls"] == list(pipeline._EDITORIAL_RANKS)
                assert all(r["evidence"].get("trigger") == "out_of_mandate" for r in sparse["rows"][1:])
            if scenario == "roster":
                assert len(set(sparse["calls"])) == 18
            if scenario == "deepen":
                assert len(sparse["calls"]) == pipeline.DEEPEN_MAX_FINDINGS
                assert len([r for r in sparse["rows"] if not r["activated"]]) == 2
                assert all(r["doc_id"] == "probe" for r in sparse["rows"])
            if scenario in ("contract", "backend", "exception"):
                assert sparse["rows"][-1]["state"] == "execution_failure"
            if scenario in ("bad_budget", "masking_refusal"):
                assert not sparse["calls"]
                assert sparse["rows"][-1]["state"] == "pre_dispatch_failure"
            if scenario == "masked_egress":
                assert sparse["egress_masked"] and sparse["calls"] == ["PROCESSOR"]
            if scenario == "polish":
                assert sparse["calls"] == ["AMENDMENT_DRAFTER"]
                assert [r["reason"] for r in sparse["rows"]] == [
                    "not_a_typed_finding", "finding_not_irregular", "optional_typed_irregular_polish"]
            if scenario == "polish_empty":
                assert not sparse["calls"] and sparse["rows"][0]["reason"] == "no_findings_to_polish"
            if scenario == "redact":
                assert sparse["calls"] == ["REDACTOR"]
                assert sparse["rows"][0]["reason"] == "operator_redaction_rules_in_force"
            if scenario in ("redact_waived", "redact_no_rules"):
                assert not sparse["calls"] and sparse["rows"][0]["state"] == "ineligible"
        for scenario in ("sensitive", "missing_master"):
            outcome = _exercise(scenario=scenario)
            assert outcome["calls"] == [] and outcome["joined"]
            assert len(outcome["rows"]) == 6
            assert all(r["state"] == ("ineligible" if scenario == "sensitive" else "no_execution_path")
                       for r in outcome["rows"])
        unresolved = _exercise(scenario="paired_unresolved")
        assert not unresolved["calls"] and unresolved["joined"]
        assert all(r["reason"] == "existing_pairing_refusal" for r in unresolved["rows"])

        def observe():
            result = _exercise()
            return {"calls": result["calls"], "joined": result["joined"], "rows": result["rows"]}

        def verdict():
            result = observe()
            return ("PASS" if result["calls"] == ["PRACTICE_AUDITOR"] and result["joined"] else "FAIL", "")

        def validate():
            return len(json.loads((ROOT / "config/agent_registry.json").read_text(encoding="utf-8"))["agents"]) == 18

        prove_effect(name="actual_wide_gate_and_activation_record", validate=validate,
            observe=observe, check=verdict,
            neutralise=lambda: patch.object(pipeline, "_convention_review_firing_agents",
                                           lambda assignment: list(pipeline.CONVENTION_REVIEW_AGENTS)))
        prove_effect(name="dispatch_record_join", validate=validate, observe=observe, check=verdict,
            neutralise=lambda: patch.object(activation, "dispatch_called", lambda *args: None))
        def observe_egress():
            result = _exercise(scenario="masked_egress")
            return {"calls": result["calls"], "joined": result["joined"], "masked": result["egress_masked"]}

        def egress_verdict():
            result = observe_egress()
            return ("PASS" if result["masked"] and result["joined"] else "FAIL", "")

        import sys
        prove_effect(name="masking_before_actual_dispatch", validate=validate,
            observe=observe_egress, check=egress_verdict,
            neutralise=lambda: patch.object(sys.modules[__name__], "_fixture_mask",
                                           lambda stable, dynamic, **kwargs: (stable, dynamic)))
        try:
            prove_effect(name="no_op", validate=validate, observe=observe,
                         check=verdict, neutralise=nullcontext)
        except ProofFailure as exc:
            assert exc.category == "NO_OBSERVED_EFFECT"
        else:
            raise AssertionError("no-op accepted")
        return "PASS", "actual dispatch/audit joins, conservative fallback, dense parity, bounded legal/editorial work, masking/refusal, privacy, NFR and no-op refusal"
    except Exception as exc:
        site = traceback.extract_tb(exc.__traceback__)[-1]
        return "FAIL", "activation consumer proof: " + type(exc).__name__ + " at " + str(site.lineno)


if __name__ == "__main__":
    status, detail = check()
    print(status, detail)
    raise SystemExit(0 if status == "PASS" else 1)
