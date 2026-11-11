"""The one narrow call of the judging path (P2, D-S41), for every step that makes one.

A passage pair, a cell claim and a multi-round case question skip run_task, so what run_task does
for a call is done here: the masking (LAW-IV, INFRA-041), the audit trail (the prompt record, the
call evidence, the activation row, the judging row and the reply's outcome) and the cost scope.
The driver's `_narrow_ask` delegates here, and the case phase comes here directly: the statements
of the driver's `main` that hold the case phase are pinned as they are (check 261).
"""
import uuid

import agent_activation
import call_evidence
import paired_review
import passage_pairs
import reply_records
import run_options
from shimmer_logging import get_logger, log_event

_LOG = get_logger("shimmer.narrow_call")


def narrow_ask(run_context, run_id, doc, wrapper, agent, rule, judging_calls, *, task, plan_kind, context, send,
               decided, answer_of, outcome_of, seen, call_of, phase="5.5", trigger_source="convention_declaration"):
    """`ask(user)`, masked against the whole document, its trail written as run_task writes it, its
    outcome recorded, its answer handed back (None for a failed call). `send(stable, dynamic)`
    makes the call."""

    def ask(user):
        call_id = uuid.uuid4().hex
        # LAW-IV: this call skips run_task, so its masking is applied here (INFRA-041).
        stable, dynamic = passage_pairs.outbound(wrapper, user, context=context)
        # The audit trail run_task writes, as the draft memo's direct call writes it.
        try:
            run_options.record_prompt(run_context, call_id, wrapper.name, stable, dynamic)
            call_evidence.record(run_context, call_evidence.extract(
                {"task": task, "document_id": str(doc["id"]), "rule_id": rule["id"]},
                call_id=call_id, run_id=run_id or "", phase=phase, doc_id=str(doc["id"]),
                agent=wrapper.name, backend=wrapper.backend, model=wrapper.model or "",
                prompt_chars=len(stable) + len(dynamic)))
        except Exception as e:
            log_event(_LOG, f"call_evidence_write_error error_type={type(e).__name__}",
                      level="warning", agent=wrapper.name, run_id=run_id or "")
        wrapper._cost_phase, wrapper._cost_doc_id, wrapper._cost_call_id = phase, str(doc["id"]), call_id
        r = None
        try:
            r = agent_activation.direct_call(
                wrapper, call_id, lambda: send(stable, dynamic),
                reason=task, source_phase=phase, doc_id=doc["id"],
                consumer="model_finding_not_promoted", trigger_source=trigger_source,
                evidence={"rule_id": rule["id"], "doc_id": str(doc["id"])},
                outcome="decided" if decided else "free_text")
        finally:
            wrapper._cost_phase, wrapper._cost_doc_id, wrapper._cost_call_id = "", "", ""
            judging_calls.setdefault(agent, []).append(paired_review.judging_call_record(
                {"ok": bool(getattr(r, "ok", False)), "call_id": call_id,
                 "backend": getattr(r, "backend", wrapper.backend), "model": getattr(r, "model", wrapper.model)},
                agent=agent, unit_id=None, rule_id=rule["id"], plan_kind=plan_kind,
                notes_kept=0, has_note=False))
        reply_records.write_outcome(run_context, call_id, outcome_of(r), source=task,
                                    truncated=(getattr(r, "usage", None) or {}).get("truncated"))
        seen.update(backend=getattr(r, "backend", None), model=getattr(r, "model", None))
        call_of[user] = call_id
        return answer_of(r)
    return ask
