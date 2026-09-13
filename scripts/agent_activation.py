"""Run-scoped activation evidence. Routing facts, never interpretation of prose.

The reference and conditional profiles currently retain the same conservative
production policy. Existing phase gates own their decisions. This module records
those decisions and observes the actual wrapper/dispatch boundary independently.
It adds nothing to model prompts or the agent bus.
"""
from __future__ import annotations

from functools import wraps
import json
from pathlib import Path
import threading
import time

PROFILES = ("dense", "sparse")
_LOCK = threading.RLock()
_PURPOSES = {
    "PROCESSOR": "draft_auditors_and_per_agent_report",
    "VERIFIER": "amendments_audit_synthesis_report_bus",
    "FACT_CHECKER": "amendments_audit_synthesis_web_references_report_bus",
    "ARCHIVIST": "structural_inventory_legal_wide_practice_bus",
    "INST_FINDER": "institution_registry_audit_bus_context",
    "CITATION_RESOLVER": "citation_graph_audit_bus_context",
    "SPEECH_ACT_TAGGER": "per_agent_report_bus_context",
    "LEGAL_ANALYST": "legal_findings_amendments_report_bus",
    "PRACTICE_AUDITOR": "convention_findings_amendments_audit_synthesis",
    "STYLE_GUARDIAN": "wording_findings_amendments",
    "REDACTOR": "privacy_scrub",
    "AMENDMENT_DRAFTER": "allowed_wording_fields",
}


class ActivationAudit:
    def __init__(self, run_context, agents, profile="dense"):
        if profile not in PROFILES:
            raise ValueError("unknown activation profile")
        self.path = Path(run_context.audit_dir()) / "agent_activation.json"
        self.data = {
            "schema_version": 1, "run_id": run_context.run_id,
            "activation_mode": profile,
            "policy": "conservative_reference_with_existing_phase_gates",
            "actual_call_definition": "wrapper dispatch attempted; successful generation is a separate cost/backend outcome",
            "agents": list(agents), "decisions": [],
        }
        self._write()

    def _write(self):
        self.data["agent_states"] = []
        for agent in self.data["agents"]:
            rows = [r for r in self.data["decisions"] if r["agent"] == agent]
            calls = [r for r in rows if r["actual_call"]]
            self.data["agent_states"].append({
                "agent": agent, "state": rows[-1]["state"] if rows else "phase_not_reached",
                "eligible": rows[-1]["eligible"] if rows else None,
                "activated": any(r["activated"] for r in rows),
                "actual_calls": len(calls),
                "decision_ids": [r["decision_id"] for r in rows],
            })
        self.path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.path.with_suffix(".json.tmp")
        pending.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        pending.replace(self.path)

    def decision(self, agent, *, eligible, activated, reason, source_phase,
                 evidence=None, trigger_source="phase_schedule", decision_kind="structural",
                 refire_count=0, refire_limit=0, consumer="bus_and_phase_consumer",
                 doc_id="", state=None):
        if activated and not eligible:
            raise ValueError("ineligible agent cannot activate")
        if decision_kind not in ("structural", "governed-semantic", "escalation"):
            raise ValueError("unknown activation decision kind")
        if refire_count < 0 or refire_count > refire_limit:
            raise ValueError("activation exceeds declared repeat bound")
        with _LOCK:
            row = dict(
                decision_id=len(self.data["decisions"]) + 1, agent=agent,
                eligible=bool(eligible), activated=bool(activated),
                activation_mode=self.data["activation_mode"], reason=reason,
                evidence=evidence or {}, trigger_source=trigger_source,
                decision_kind=decision_kind, source_phase=str(source_phase),
                refire_count=refire_count, refire_limit=refire_limit,
                downstream_consumer=consumer, doc_id=str(doc_id or ""),
                state=state or ("activated_not_dispatched" if activated else
                                "eligible_inactive" if eligible else "ineligible"),
                actual_call=False, call_id=None,
            )
            self.data["decisions"].append(row)
            self._write()
            return row

    def update(self, row, **fields):
        with _LOCK:
            row.update(fields)
            self._write()


def initialize(run_context, agents, profile="dense"):
    audit = ActivationAudit(run_context, agents, profile)
    run_context.activation_audit = audit
    return audit


def get(run_context):
    return getattr(run_context, "activation_audit", None)


def not_called(run_context, agent, *, reason, source_phase, eligible=True,
               evidence=None, state=None, **fields):
    audit = get(run_context)
    if audit is not None:
        return audit.decision(agent, eligible=eligible, activated=False, reason=reason,
                              source_phase=source_phase, evidence=evidence,
                              state=state, **fields)


def observe_task(method):
    """Observe requests and outcomes; dispatch_called separately proves dispatch.

    A caller without a pipeline activation session retains its old behavior.
    Raised failures are recorded by type only, never exception text or payload.
    """
    @wraps(method)
    def observed(self, *args, **kwargs):
        audit = get(getattr(self, "run_context", None))
        if audit is None:
            return method(self, *args, **kwargs)
        payload = kwargs.get("work_payload") or {}
        payload = payload if isinstance(payload, dict) else {}
        task = payload.get("task", "unspecified")
        details = dict(kwargs.get("activation") or {})
        details.setdefault("reason", "reference_scheduled" if audit.data["activation_mode"] == "dense"
                           else "conservative_retained")
        details.setdefault("source_phase", kwargs.get("phase") or task)
        details.setdefault("doc_id", payload.get("document_id") or kwargs.get("doc_id") or "")
        details.setdefault("evidence", {"task": task, "expertise_exclusion": "not_established"})
        details.setdefault("consumer", _PURPOSES.get(self.name, "advisory_board_and_deliverable"))
        row = audit.decision(self.name, eligible=True, activated=True, **details)
        self._activation_observation = row
        started = time.monotonic()
        try:
            result = method(self, *args, **kwargs)
        except BaseException as exc:
            audit.update(row, state="execution_failure" if row["actual_call"] else "pre_dispatch_failure",
                         error_type=type(exc).__name__, elapsed_seconds=time.monotonic() - started)
            raise
        else:
            audit.update(row, state="completed" if result.get("ok") else "execution_failure",
                         outcome="accepted" if result.get("ok") else
                                 "contract_violation" if result.get("error") == "contract_violation" else "backend_failure",
                         truncated=bool(result.get("truncated")),
                         recovered=(result.get("parse_trace") or {}).get("path") == "recovery",
                         elapsed_seconds=time.monotonic() - started)
            return result
        finally:
            self._activation_observation = None
    return observed


def dispatch_called(wrapper, call_id):
    audit = get(getattr(wrapper, "run_context", None))
    row = getattr(wrapper, "_activation_observation", None)
    if audit is not None and row is not None:
        audit.update(row, actual_call=True, call_id=call_id, state="dispatch_started")


def call_dispatch(wrapper, call_id, *args, **kwargs):
    """Mark dispatch after its arguments have been successfully prepared."""
    dispatch_called(wrapper, call_id)
    return wrapper.dispatch(*args, **kwargs)


def direct_call(wrapper, call_id, call, *, reason, source_phase, evidence=None):
    """The free-text Draft entry bypasses run_task and has no envelope contract."""
    audit = get(getattr(wrapper, "run_context", None))
    if audit is None:
        return call()
    row = audit.decision(wrapper.name, eligible=True, activated=True, reason=reason,
                         source_phase=source_phase, evidence=evidence,
                         consumer="draft_memo_then_review", trigger_source="task_mode")
    audit.update(row, actual_call=True, call_id=call_id, state="dispatch_started")
    try:
        result = call()
    except BaseException as exc:
        audit.update(row, state="execution_failure", error_type=type(exc).__name__)
        raise
    audit.update(row, state="completed" if result.ok else "execution_failure",
                 outcome="free_text" if result.ok else "backend_failure")
    return result
