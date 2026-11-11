"""LAW-IV privacy redaction stage (relocated + collapsed in Phase 1c).

This is the final privacy pass (Mechanism 1), run when the sensitivity layer is active, that used to live in the
editorial-side pipeline as `phase_9_redaction`. It now lives in the privacy home so
the editorial side holds NO privacy logic. The pipeline calls INTO this module for
the redaction pass (editorial->privacy direction, allowed); this module imports
nothing editorial (no pipeline / ladder / amendment_render / convention schema).

COLLAPSE (Phase 1c): the three-agent tier ladder (CLERK / AUTHORITY / GATE, T1-T5)
was the EDITORIAL review board mistakenly imposed on privacy. Privacy needs no
tiers, no escalation, no model self-test gate. It is collapsed to a SINGLE agent,
REDACTOR (derived from the proposing clerk). REDACTOR proposes redaction spans for
the judgment cases; the deterministic `redaction_detect` + operator rules catch the
regular-shaped PII every run; the scrubber consumes the merged result and VERIFIES
absence by grep (a survivor BLOCKs). The dropped AUTHORITY/GATE behavior was only
model self-checks (approve-a-subset + adversarial re-identification + binary gate);
no deterministic privacy guarantee lived there. Dropping them also removes the old
model-veto NOT_APPLIED path that could ship a document UNREDACTED, so the collapse
STRENGTHENS LAW-IV: every proposed + detected span is now applied and verified.

BOUNDARY (shape (a), from Phase 1b): the editorial RENDER stays on the pipeline
side. The pipeline injects `build_wrapper(name)` (closes over the orchestrator + keys),
`render_deliverable(scrubbed_master, body_text, doc, info, scrub)` (closes over
amendment_render, the reviewed document and the convention registry) and
`unit_ids(text, doc_id)`. This module never imports those; it only calls the injected
functions. So there is no privacy->editorial edge.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Neutral infrastructure (the generic agent runner + canonical envelope decoder);
# agent_wrapper imports nothing editorial, so this is not a privacy->editorial edge
# (same shape as scrub.py importing text_extract).
from agent_wrapper import decode_items, is_envelope
import agent_activation

from . import redaction_detect
from .rules import redaction_rules
from .scrub import (scrub_master_and_body, scrub_text_artifacts_and_verify, _redact_obj, _redact_text,
                    _merge_redaction_proposals)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _truncate(text: str, max_chars: int) -> str:
    """Local copy (privacy home owns its helpers; importing the editorial pipeline's
    _truncate would be a privacy->editorial edge)."""
    t = text or ""
    return t if len(t) <= max_chars else t[:max_chars]


# One structured object is the SINGLE source of truth for both the machine-readable
# bus message and the human console notice, so the two can never disagree.
ESCALATION_SCHEMA = "operator_escalation/v1"

# internal failure_kind -> (message verb, remediation hint). The public taxonomy on
# the object collapses the two contract_violation_* kinds to "contract_violation".
_REDACTION_FAILURE = {
    "contract_violation_parse": (
        "failed to parse",
        "The redactor ran but its output could not be parsed as JSON, even after "
        "tolerant extraction. Inspect the raw output below, then re-run; if the local "
        "model keeps emitting malformed output, repair or replace the Qwen redaction backend."),
    "contract_violation_fields": (
        "failed to satisfy the redaction contract",
        "The redactor ran and returned JSON, but it does not match the required "
        "redactions contract (a span plus its category). Inspect the raw output below, "
        "then re-run; repair the model or prompt if it persists."),
    "redactor_unavailable": (
        "failed to reach the redaction backend",
        "The local Qwen redaction backend was unreachable. Make it reachable (install/"
        "repair torch + transformers and the model) and re-run, or re-run with "
        "--no-redaction-override to consciously waive redaction for a non-sensitive run "
        "(logged to the governance ledger)."),
    "no_resolvable_redaction": (
        "returned items but none resolved to a valid redaction",
        "The redactor returned a valid wrapper with items, but NONE resolved to a usable "
        "redaction (a span plus a replacement / method=REDACT / a redaction category) - "
        "e.g. redactions mis-tagged as kind='finding'. This is NOT a clean 'nothing to "
        "redact' result, so it is BLOCKED rather than silently passed. Inspect the persisted "
        "raw output, fix the redactor prompt/model, and re-run."),
    "span_dropped": (
        "an approved redaction span could not be located in any shipped artifact",
        "A span the redactor proposed produced ZERO substitutions across every "
        "operator-facing artifact, even after normalized matching (al-prefix, "
        "intervening connective text, whitespace, diacritics). A span that cannot be located "
        "is a FAILED substitution, never a silent zero-match: the run BLOCKS so the operator "
        "decides. See `detail.dropped_spans`. Fix the redactor span text/prompt or the matcher, "
        "then re-run."),
    "no_operator_rule": (
        "no operator redaction rule is in force",
        "Redaction is required but NO operator rule compiled, so there is nothing the "
        "operator has declared redactable. The engine does NOT invent default categories "
        "(operator-sovereignty). Supply a compiling redaction convention, or re-run with "
        "--no-redaction-override to consciously declare redact-nothing for THIS run "
        "(logged to the governance ledger). Never a silent default; never a silent ship."),
    "pii_survives_in_deliverable": (
        "an approved redaction span SURVIVED in a shipped artifact after apply",
        "After applying redactions, the post-apply verification grep found an approved span "
        "still present in an operator-facing artifact (deliverable / summary / master / "
        "rendered docx text). 'Applied' must mean verified-absent everywhere shippable, so "
        "this BLOCKS rather than reporting success. See `detail.survivors` for the artifact(s) "
        "and span(s). This is a LAW-IV safety stop."),
}


# Failure kinds that surface to the operator under their own name (the two
# contract_violation_* kinds collapse to "contract_violation"; everything else
# passes through verbatim).
_REDACTION_PUBLIC_KINDS = frozenset({
    "redactor_unavailable", "no_resolvable_redaction",
    "span_dropped", "pii_survives_in_deliverable", "no_operator_rule",
})


def build_redaction_escalation(*, doc_id, document_name, stage, failure_kind,
                               raw_output_path, detail=None):
    """Build the structured, machine-readable operator-escalation object for a
    redaction that could not be confirmed clean (LAW-IV). Reusable schema
    (`operator_escalation/v1`); the bus message and the console notice both derive
    from this one object. `detail` (optional) carries application-layer specifics
    (e.g. dropped spans / survivors per artifact) without changing the schema."""
    public_kind = (failure_kind if failure_kind in _REDACTION_PUBLIC_KINDS
                   else "contract_violation")
    verb, remediation = _REDACTION_FAILURE.get(
        failure_kind, _REDACTION_FAILURE["contract_violation_fields"])
    esc = {
        "schema": ESCALATION_SCHEMA,
        "kind": "REDACTION_BLOCKED",
        "severity": "BLOCK",
        "needs_operator": True,
        "phase": "redaction",
        "stage": stage,                  # the step that failed, e.g. REDACTOR
        "doc_id": doc_id,
        "document_name": document_name,
        "failure_kind": public_kind,     # contract_violation | redactor_unavailable | span_dropped | pii_survives_in_deliverable
        "raw_output_path": raw_output_path,
        "message": f"redaction did not pass: {verb}",
        "remediation": remediation,
    }
    if detail is not None:
        esc["detail"] = detail
    return esc


def render_escalation_notice(esc):
    """Human-readable BLOCK notice, derived from the SAME structured escalation
    object so console and bus never disagree."""
    lines = [
        "",
        "================ REDACTION BLOCK (LAW-IV) ================",
        f"  BLOCKED deliverable: {esc['document_name']!r} (doc id: {esc['doc_id']})",
        f"  Why:    {esc['message']}  (failure_kind = {esc['failure_kind']})",
        f"  Where:  phase {esc['phase']!r}, step {esc['stage']}",
    ]
    if esc.get("raw_output_path"):
        lines.append(f"  Raw output: {esc['raw_output_path']}")
    lines.append(f"  Next:   {esc['remediation']}")
    lines.append("  This deliverable was NOT confirmed clean - it is BLOCKED, not skipped.")
    lines.append("=========================================================")
    return "\n".join(lines)


def _post_redaction_block(orch, esc):
    """Post the structured escalation to the bus (machine-readable, type ESCALATE)
    AND print the human notice derived from the same object."""
    orch._post_orchestrator(
        recipient="OPERATOR", channel="escalation", msg_type="ESCALATE",
        body={"event": "REDACTION_BLOCKED", "escalation": esc},
        constitution_check={"laws_consulted": ["LAW-IV", "LAW-V"], "result": "UNRESOLVED",
                            "resolution": "redaction could not be confirmed clean; operator must decide"})
    print(render_escalation_notice(esc), file=sys.stderr, flush=True)


def _post_redaction(orch, doc_id, event, body):
    """Post an auditable redaction-decision event to the run bus (LAW-IV)."""
    orch._post_orchestrator(
        recipient="OPERATOR", channel="redaction", msg_type="INFORM",
        body={"event": event, "document_id": doc_id, **body},
        constitution_check={"laws_consulted": ["LAW-IV", "LAW-V"], "result": "RESOLVED",
                            "resolution": "redaction screening at the output boundary"})


_REDACTION_CATEGORY_HINTS = ("confiden", "redact", "privacy", "pii")


def _norm_redaction_category(cat) -> str:
    """Normalize a redaction category string so 'conv-confidentiality' and
    'confidentiality' do not diverge: strip a leading 'conv-' and lowercase."""
    c = str(cat or "").strip().lower()
    if c.startswith("conv-"):
        c = c[len("conv-"):]
    return c


def _is_redaction_proposal(it) -> bool:
    """STRUCTURAL redaction detection (defense in depth): an item is a redaction
    proposal if it carries a non-empty `span` AND any redaction signal - a
    `replacement`, method=REDACT/MASK/REMOVE, or a redaction `category` - OR it is
    explicitly kind='redaction'. A free-text `kind` label from a 7B is never the
    SOLE gate on this safety-critical filter (a redaction mis-tagged kind='finding'
    is still detected and applied)."""
    if not isinstance(it, dict):
        return False
    if str(it.get("kind", "")).strip().lower() == "redaction":
        return True
    span = it.get("span")
    if not (isinstance(span, str) and span.strip()):
        return False
    method = str(it.get("method", "")).strip().lower()
    cat = _norm_redaction_category(it.get("category"))
    return (bool(it.get("replacement"))
            or method in ("redact", "mask", "remove")
            or any(h in cat for h in _REDACTION_CATEGORY_HINTS))


def _classify_redactor_items(items):
    """Classify the redactor's decoded items into a redaction outcome (no model call):
      ([], ...)                          -> ("NONE", [])     legitimate 'nothing to redact'
      non-empty, none is a redaction     -> ("BLOCK", [])    non-empty-but-unresolved (LOUD, never silent)
      one or more redaction proposals    -> ("PROPOSE", reds) the structurally-detected redactions
    Each returned redaction has its category normalized."""
    items = [it for it in (items or []) if isinstance(it, dict)]
    if not items:
        return ("NONE", [])
    reds = []
    for it in items:
        if _is_redaction_proposal(it):
            r = dict(it)
            r["category"] = _norm_redaction_category(it.get("category"))
            reds.append(r)
    if not reds:
        return ("BLOCK", [])
    return ("PROPOSE", reds)


def _persist_redactor_output(run_ctx, stage, doc_id, result) -> "str | None":
    """Persist a redactor's raw + parsed output to the run audit dir on EVERY path
    (not only on contract violation), so a future anomaly is diagnosable from disk,
    not only the bus. Returns the path, or None if run_ctx is unavailable / the write
    failed (best-effort, never raises)."""
    if run_ctx is None:
        return None
    try:
        out_dir = run_ctx.audit_dir() / "redaction"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{stage}_{doc_id}.json"
        path.write_text(json.dumps({
            "stage": stage, "doc_id": doc_id, "ok": result.get("ok"),
            "error": result.get("error"), "parsed": result.get("parsed"),
            "raw_text": result.get("raw_text", ""),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)
    except Exception:
        return None


def _run_spans(*proposal_lists):
    """The spans every document's artifacts are scrubbed and grepped with: every span
    proposed in the run, in every written form. Only identical strings collapse.
    `_merge_redaction_proposals` is not used here: it exists to keep one attribution per
    document, and this list has no need to drop anything."""
    out, seen = [], set()
    for proposals in proposal_lists:
        for item in proposals or []:
            span = str(item.get("span") or item.get("text") or "").strip() if isinstance(item, dict) else ""
            if span and span not in seen:
                seen.add(span)
                # The span alone: every other key of a proposal came from a model.
                out.append({"span": span})
    return out


def _neutral_unit_ids(doc, spans, unit_ids):
    """Unit ids that carry a span, as redaction items: a unit id writes its heading's words
    (lowercased, cut at 40 characters, non-ASCII letters dropped), in a form no span
    matcher reads, and it is copied into every finding and amendment. So each id is
    derived again from the scrubbed text and the old id is scrubbed as an exact string,
    whatever form the heading took, the survivor grep then reading for it like any span.
    Units pair by position. If the scrub changed how many there are, no pairing can be
    trusted, so every id of the document takes one no unit of the scrubbed text can have,
    and all its findings are shown after the document rather than under the wrong part."""
    if unit_ids is None:
        return []
    before = list(unit_ids(doc.get("text", ""), doc["id"]))
    after = list(unit_ids(_redact_text(doc.get("text", ""), spans)[0], doc["id"]))
    pairs = zip(before, after) if len(before) == len(after) else (
        (old, old.split("-", 1)[0] + "-no-longer-a-part") for old in before)
    return [{"span": old, "neutral_id": new} for old, new in pairs if old != new]


def _detected_in_grounding(info, rules):
    """The authorised shapes in the context passages a document's grounding summary shows
    whole. The passages phase 6 recorded, never the file: its header carries the run's own
    date, which re-rendered files write again, so reading it would block every run."""
    return [item for passage in info.get("grounding_passages") or []
            for item in redaction_detect.detect(_PROJECT_ROOT, str(passage), rules, warn_sink=[])]


def _no_span_at_all(redactions, scrub_spans):
    """Nothing of this document's own and nothing in the run: nothing to apply or render."""
    return not redactions and not scrub_spans


def _held_no_other_span(redactions, rep, body_red, doc):
    """No span of its own, and no other document's span met in its text or artifacts."""
    return not redactions and not rep["total_subs"] and body_red == doc.get("text", "")


def _only_others(redactions):
    """True for a document with no span of its own: what it reports as applied came from
    other documents' spans, and it says so instead of 0 spans and nothing else."""
    return not redactions


def _unknown_documents(op_docs, read_docs):
    """The documents whose redactor gave no usable reply: what it would have marked in
    them is unknown, so the report of every document that reached the scrub says so."""
    return [doc["id"] for doc in op_docs if doc["id"] not in read_docs]


def run_redaction_phase(orch, op_docs, deliverables, run_ctx, convention_registry,
                        *, build_wrapper, render_deliverable, redaction_enabled=True, unit_ids=None):
    """FINAL privacy pass (LAW-IV), run when the sensitivity layer is active, regardless of whether
    anything is redacted. The SINGLE Qwen agent REDACTOR proposes redaction spans and
    APPLIES the operator redaction rules (LAW-IV's own phrase, "content marked for
    redaction") - the model does NOT judge sensitivity on its own; it applies the
    rules the operator declared (INFRA-038). The deterministic `redaction_detect`
    catches operator-authorized regular shapes every run; the two are merged.

    When a redaction is detected/proposed it is applied THROUGH the canonical
    amendments master and the .md/.docx are re-rendered from it (INFRA-033) via the
    injected `render_deliverable` callback, so the formats stay consistent. Writes
    only inside the run folder (run_ctx); never touches durable/. Every decision is
    posted to the run bus.

    Collapse note (Phase 1c): there is no AUTHORITY/GATE approval/self-test stage and
    no NOT_APPLIED path. Every proposed + deterministically-detected span is applied
    and VERIFIED ABSENT by the post-apply grep gate (a survivor or an unlocatable span
    BLOCKs). This is strictly safer than the old model-veto path.

    Degrades safely (INFRA-034): the agent runs on the local Qwen backend; if it is
    unreachable, run_task returns ok=False and the phase BLOCKs that document with
    redactor_unavailable - it never crashes a keyless environment. (The Qwen-required
    startup gate is INFRA-035.)

    When redaction is WAIVED for the run (operator passed --no-redaction-override at
    the startup gate), this phase still runs structurally but performs no redaction:
    it records REDACTION_SKIPPED (operator_waived) per document on the bus.

    Every document's spans are proposed first; then every document that reaches the scrub
    is scrubbed, and grepped, with every span of the run (`_run_spans`), as a precaution:
    a context passage can hold text any document's span names. A document held or blocked
    at the redactor is scrubbed with what is known, and is BLOCKED if a known span survives
    or its render fails. Only a document's
    own spans must be located in it.

    `build_wrapper(name)`, `render_deliverable(scrubbed_master, body_text, doc, info, scrub)`
    and `unit_ids(text, doc_id)` (the document's unit ids, in order) are injected by the
    pipeline (shape (a)); `scrub(obj)` scrubs every free-text string of an object with the
    same spans, so the pipeline can render from scrubbed inputs. This module imports
    nothing editorial."""
    summary = {}
    if not redaction_enabled:
        for doc in op_docs:
            agent_activation.not_called(run_ctx, "REDACTOR", eligible=False,
                reason="operator_waived_redaction", source_phase="9", doc_id=doc["id"],
                consumer="privacy_scrub")
            _post_redaction(orch, doc["id"], "REDACTION_SKIPPED", {"reason": "operator_waived"})
            summary[doc["id"]] = {"redacted": False, "state": "SKIPPED", "reason": "operator_waived"}
        return summary
    # OPERATOR REDACTION RULES (INFRA-038): compile the machine-usable rule set the
    # redactor APPLIES, and REPORT whether the operator's rules are in force or only
    # the defaults apply. A redaction-intent convention that fails to compile is
    # surfaced LOUDLY (console + a structured bus note) - never a silent fallback.
    rr = redaction_rules(convention_registry)
    red_rules = rr["rules"]
    print(f"[redaction-rules] operator_in_force={rr['operator_in_force']} source={rr['source']} "
          f"({len(rr['operator_rules'])} operator rule(s))", file=sys.stderr)
    # 1c defense-in-depth: never run with NO operator rule in force. The pre-run gate
    # already hard-stops (or the operator declared redact-nothing, which waives
    # redaction_enabled). If we somehow reach here with no operator rule, BLOCK every
    # doc - never silently default, never silently ship unredacted.
    if not rr["operator_in_force"]:
        for doc in op_docs:
            agent_activation.not_called(run_ctx, "REDACTOR", eligible=False,
                reason="no_operator_redaction_rule", source_phase="9", doc_id=doc["id"],
                consumer="privacy_scrub")
            esc = build_redaction_escalation(
                doc_id=doc["id"], document_name=doc["name"], stage="REDACT_RULES",
                failure_kind="no_operator_rule", raw_output_path=None,
                detail={"warnings": rr["warnings"]})
            _post_redaction_block(orch, esc)
            summary[doc["id"]] = {"redacted": False, "state": "BLOCKED",
                                  "failure_kind": esc["failure_kind"], "escalation": esc}
        return summary
    for w in rr["warnings"]:
        print(f"[redaction-rules] WARNING: convention {w['id']} ({w['category']}) is redaction-intent "
              f"but did NOT compile: {w['reason']} - operator rule NOT applied.", file=sys.stderr)
    orch._post_orchestrator(
        recipient="OPERATOR", channel="redaction", msg_type="INFORM",
        body={"event": "REDACTION_RULES_COMPILED", "source": rr["source"],
              "operator_in_force": rr["operator_in_force"],
              "operator_rule_ids": [r.get("id") for r in rr["operator_rules"]],
              "warnings": rr["warnings"]},
        constitution_check={"laws_consulted": ["LAW-IV", "LAW-V"], "result": "RESOLVED",
                            "resolution": "operator redaction rules compiled for the redaction pass"})
    # Two passes: every document's spans are proposed first, then every document's
    # artifacts are scrubbed with all of them (see `run_spans` below). The deterministic
    # spans are read from the text alone, before any redactor call, so a document whose
    # redactor reply is refused or held below still gives them to the run. The passages a
    # grounding summary shows are read too: they come from context documents, which are
    # not documents under review, so nothing else would look at them.
    detected, quoted = {}, []
    for doc in op_docs:
        unapplied = []
        detected[doc["id"]] = (redaction_detect.detect(_PROJECT_ROOT, doc["text"], rr["operator_rules"],
                                                       warn_sink=unapplied), unapplied)
        quoted += _detected_in_grounding(deliverables.get(doc["id"]) or {}, rr["operator_rules"])
    pending, held = [], []
    for doc in op_docs:
        info = deliverables.get(doc["id"]) or {}
        master_path = info.get("amendments_json")
        if not master_path:
            agent_activation.not_called(run_ctx, "REDACTOR", reason="no_readable_master",
                source_phase="9", doc_id=doc["id"], state="no_execution_path")
            continue
        try:
            master = json.loads(Path(master_path).read_text(encoding="utf-8"))
        except Exception:
            agent_activation.not_called(run_ctx, "REDACTOR", reason="unreadable_master",
                source_phase="9", doc_id=doc["id"], state="no_execution_path")
            esc = build_redaction_escalation(
                doc_id=doc["id"], document_name=doc["name"], stage="REDACT_APPLY",
                failure_kind="pii_survives_in_deliverable", raw_output_path=None,
                detail={"unreadable_master": True})
            _post_redaction_block(orch, esc)
            summary[doc["id"]] = {"redacted": False, "state": "BLOCKED",
                                  "failure_kind": esc["failure_kind"], "escalation": esc}
            held.append({"doc": doc, "info": info, "master": None})
            continue
        amendments = master.get("amendments", [])
        reachable = {"doc": doc, "info": info, "master": master}

        redactor = build_wrapper("REDACTOR")
        redactor_r = redactor.run_task(
            work_payload={"task": "apply_redaction_rules", "document_id": doc["id"],
                          "document_name": doc["name"], "amendments": amendments,
                          # Operator redaction rules + the document spans to apply
                          # them to (minimal read-radius unblind for rule application).
                          "redaction_rules": red_rules,
                          "document_text": _truncate(doc["text"], 4000)},
            run_objectives="Apply the OPERATOR REDACTION RULES (in your context) to the spans of "
                           "this document and its deliverable. For EVERY span that matches a rule, emit "
                           "one item with kind=\"redaction\" (NEVER kind=\"finding\"), span set to the "
                           "exact matched text (verbatim), category set to the matched rule's category "
                           "verbatim, replacement=\"[REDACTED]\", method=\"REDACT\", and rule_id set to "
                           "the id of the rule that matched (e.g. CONV-006 or RED-DFLT-001). Emit ONE "
                           "item per DISTINCT sensitive span - a named individual is its own span, an "
                           "identity/ID number is its own SEPARATE span, and a company name and a "
                           "financial figure are each their own span. NEVER merge a person's name with "
                           "an adjacent ID number (or a company with a figure) into a single span; split "
                           "them into separate items, each with its own exact verbatim span text. Do NOT "
                           "judge whether content is 'sensitive' on your own - apply the rules as written. "
                           "If and only if NO span matches any rule, return items: [].",
            channel="redaction", max_tokens=1024,
            convention_registry=convention_registry,
            # productization STEP 4: cost dimensions. Redaction is a per-document
            # phase; doc["id"] matches _persist_redactor_output's own doc_id below.
            phase="redaction", doc_id=str(doc["id"]),
            activation={"reason": "operator_redaction_rules_in_force", "source_phase": "9",
                        "consumer": "privacy_scrub", "trigger_source": "privacy_stage",
                        "evidence": {"operator_in_force": True, "redaction_enabled": True}})
        # Persist the redactor's raw + parsed output on EVERY path (INFRA-038 gap
        # close): diagnosable from disk, not only the bus.
        redactor_raw_path = _persist_redactor_output(run_ctx, "REDACTOR", doc["id"], redactor_r)
        # LAW-IV strict gate (INFRA-037): the redactor result must be a CONTRACT-VALID
        # canonical wrapper, or the run BLOCKS and escalates - never silently skipped.
        # Distinguish a backend that could not be reached (redactor_unavailable) from a
        # model that ran but produced unparseable / non-wrapper output (contract_violation).
        parsed = redactor_r.get("parsed")
        if not (redactor_r.get("ok") and is_envelope(parsed)):
            if not redactor_r.get("ok") and redactor_r.get("error") == "contract_violation":
                miss = redactor_r.get("contract_missing") or []
                parse_failed = any(str(m).startswith("json parse failure")
                                   or str(m) == "no JSON object found in output" for m in miss)
                failure_kind = ("contract_violation_parse" if parse_failed
                                else "contract_violation_fields")
            elif not redactor_r.get("ok"):
                failure_kind = "redactor_unavailable"
            else:
                failure_kind = "contract_violation_fields"  # ok but not a wrapper
            esc = build_redaction_escalation(
                doc_id=doc["id"], document_name=doc["name"], stage="REDACTOR",
                failure_kind=failure_kind,
                raw_output_path=redactor_r.get("raw_text_path") or redactor_raw_path)
            # M5 fix: distinguish a FORMAT failure (the redactor's OWN output is
            # malformed / non-conforming: unparseable JSON or missing the required
            # span+category fields) from a PRIVACY violation (sensitive spans survive
            # in a shipped artifact, caught by the post-apply grep below). A format
            # failure is the local model misbehaving, NOT evidence that PII shipped:
            # the deliverable is HELD with a WARNING and the run is NOT hard-stopped
            # (the pipeline logs the warning to the governance ledger). A real survivor
            # still BLOCKs. esc["failure_kind"] collapses the two contract_violation_*
            # kinds to the public "contract_violation"; redactor_unavailable keeps its
            # own name and therefore still BLOCKs (a backend that never ran cannot be
            # confirmed clean). LAW-IV is unchanged: this only re-routes a model-format
            # failure away from the privacy-violation hard stop.
            if esc["failure_kind"] == "contract_violation":
                # Downgrade the shared escalation object so it reads as a warning, not
                # a BLOCK: it is held for operator attention, but the run continues.
                esc["kind"] = "REDACTION_HELD_WARNING"
                esc["severity"] = "WARNING"
                esc["needs_operator"] = False
                esc["message"] = f"redaction held (format failure, not a privacy violation): {esc['message']}"
                _post_redaction(orch, doc["id"], "REDACTION_HELD_WARNING",
                                {"failure_kind": esc["failure_kind"], "escalation": esc})
                summary[doc["id"]] = {"redacted": False, "state": "HELD_WARNING",
                                      "failure_kind": esc["failure_kind"], "escalation": esc}
            else:
                _post_redaction_block(orch, esc)
                summary[doc["id"]] = {"redacted": False, "state": "BLOCKED",
                                      "failure_kind": esc["failure_kind"], "escalation": esc}
            held.append(reachable)
            continue
        # Valid wrapper. Detect redactions STRUCTURALLY (span + replacement/method/
        # category), not by the kind tag alone - a redaction mis-tagged kind='finding'
        # is still applied. Classify into NONE / BLOCK / PROPOSE:
        #   - items:[]                 -> legitimate REDACTION_NONE
        #   - items but none resolve   -> BLOCK (non-empty-but-unresolved; never a
        #                                 silent NONE - this was the silent-pass bug)
        outcome, redactor_reds = _classify_redactor_items(decode_items(parsed))
        if outcome == "BLOCK":
            esc = build_redaction_escalation(
                doc_id=doc["id"], document_name=doc["name"], stage="REDACTOR",
                failure_kind="no_resolvable_redaction",
                raw_output_path=redactor_r.get("raw_text_path") or redactor_raw_path)
            _post_redaction_block(orch, esc)
            summary[doc["id"]] = {"redacted": False, "state": "BLOCKED",
                                  "failure_kind": esc["failure_kind"], "escalation": esc,
                                  "reason": "non-empty but no item resolved to a valid redaction"}
            held.append(reachable)
            continue
        # 1b: DETERMINISTIC local detection for operator-AUTHORIZED regular shapes
        # (identifier / figure) + name-via-local-cues. Runs over the document text,
        # authorized purely by the operator rules (engine never judges sensitivity).
        # UNION with the model's proposals, de-duped by normalized span - the model
        # still proposes; detection guarantees authorized shapes are never missed.
        # ZERO: collect the operator rules that authorise NO detector at all.
        # Seven of the reference redaction rules are in this state and it is the
        # CORRECT answer for them (they name an address, a date of birth, a
        # location, free text: content no shape detector finds), but a rule that
        # compiled and can never fire must not be silent. LAW-IV's direction
        # again: an unapplied redaction rule leaves protected content in the
        # deliverable and shows nowhere.
        det_items, _unapplied = detected[doc["id"]]
        if _unapplied:
            # Posted to the bus, this module's own reporting idiom, rather than
            # logged: a log line is not an operator-facing artifact and this has
            # to reach the same place every other redaction outcome does.
            _post_redaction(orch, doc["id"], "REDACTION_RULE_UNAPPLIED",
                            {"count": len(_unapplied), "rules": _unapplied})
        redactions = _merge_redaction_proposals(
            det_items, redactor_reds if outcome == "PROPOSE" else [])
        pending.append({"doc": doc, "info": info, "master": master, "amendments": amendments,
                        "redactor_r": redactor_r, "redactor_raw_path": redactor_raw_path,
                        "redactions": redactions,
                        "proposed": redactor_reds if outcome == "PROPOSE" else []})

    # Every document that reaches the scrub is scrubbed, and grepped, with every span of
    # the run. A precaution: a document's grounding summary quotes context documents, and
    # a context document can hold text a span of any document names, so a span approved
    # in one document is not shipped in another's deliverable in any form the matcher reads. Only a document's OWN
    # spans must be located in it (a span of another document need not occur here). A
    # document whose redactor gave no usable reply adds only its deterministic spans, so
    # what the model would have marked in it is unknown, and the other documents' reports says so.
    run_spans = _run_spans(*[items for items, _ in detected.values()], quoted, *[p["proposed"] for p in pending])
    read_docs = {p["doc"]["id"] for p in pending}
    spans_unknown_from = _unknown_documents(op_docs, read_docs)
    def spans_for(doc):
        # This document's own ids, listed first so that a merged range holding an id and a
        # span inside it takes the neutral id, not the placeholder.
        return _neutral_unit_ids(doc, run_spans, unit_ids) + run_spans

    for h in held:
        # A held or blocked document's files are scrubbed with what is known; it keeps its
        # state unless a known span survives or the render fails. With no readable master
        # there is nothing to render.
        doc, info = h["doc"], h["info"]
        doc_spans = spans_for(doc)
        if h["master"] is None:
            located, by_artifact, body_red = {}, {}, _redact_text(doc.get("text", ""), doc_spans)[0]
        else:
            scrubbed_master, body_red, located, by_artifact = scrub_master_and_body(
                h["master"], doc_spans, doc.get("text", ""), own=[])
            try:
                render_deliverable(scrubbed_master, body_red, doc, info,
                                   lambda obj, spans=doc_spans: _redact_obj(obj, spans)[0])
            except Exception as e:
                # This loop runs first: a raise here must not stop the other documents.
                esc = build_redaction_escalation(
                    doc_id=doc["id"], document_name=doc["name"], stage="REDACT_APPLY",
                    failure_kind="pii_survives_in_deliverable", raw_output_path=None,
                    detail={"render_failed": type(e).__name__})
                _post_redaction_block(orch, esc)
                summary[doc["id"]].update(state="BLOCKED", first_failure_kind=summary[doc["id"]].get("failure_kind"),
                                          failure_kind=esc["failure_kind"], escalation=esc)
                scrub_text_artifacts_and_verify(doc_spans, info, located, by_artifact,
                                                also=("amendments_json", "amendments_md"))
                info["scrubbed_body"] = body_red
                continue
        rep = scrub_text_artifacts_and_verify(doc_spans, info, located, by_artifact)
        info["scrubbed_body"] = body_red
        summary[doc["id"]]["known_spans_applied"] = True
        if rep["survivors"]:
            # A known span still in a file is a real survivor, whatever held the document.
            esc = build_redaction_escalation(
                doc_id=doc["id"], document_name=doc["name"], stage="REDACT_APPLY",
                failure_kind="pii_survives_in_deliverable", raw_output_path=None,
                detail={"survivors": rep["survivors"], "by_artifact": rep["by_artifact"]})
            _post_redaction_block(orch, esc)
            summary[doc["id"]].update(state="BLOCKED", first_failure_kind=summary[doc["id"]].get("failure_kind"),
                                      failure_kind=esc["failure_kind"], escalation=esc)
    for p in pending:
        doc, info, master, amendments, redactions = (p["doc"], p["info"], p["master"], p["amendments"],
                                                      p["redactions"])
        redactor_r, redactor_raw_path = p["redactor_r"], p["redactor_raw_path"]
        scrub_spans = spans_for(doc)
        unknown = {"spans_unknown_from": spans_unknown_from} if spans_unknown_from else {}
        if _no_span_at_all(redactions, scrub_spans):
            # genuine NONE: the redactor found nothing AND no authorized shape detected
            _post_redaction(orch, doc["id"], "REDACTION_NONE",
                            {"screened_amendments": len(amendments), "raw_output_path": redactor_raw_path,
                             **unknown})
            summary[doc["id"]] = {"redacted": False, "state": "NONE", "redactions": 0, **unknown}
            continue

        # APPLY across EVERY operator-facing artifact, conserve spans (a span that lands
        # nowhere BLOCKS - never a silent zero-match), then VERIFY by re-grepping every
        # shipped artifact. Shape (a) hand-back: this privacy home PRODUCES the scrubbed
        # master + body, the pipeline RENDERS the deliverable via the injected
        # render_deliverable callback (editorial: write_amendment_deliverables +
        # _category_for_conv), then this home scrubs the text artifacts and VERIFIES.
        # The scrubber never renders and never looks up conventions; no privacy->editorial edge.
        scrubbed_master, body_red, located, by_artifact = scrub_master_and_body(
            master, scrub_spans, doc.get("text", ""), own=redactions)
        master.clear(); master.update(scrubbed_master)
        info["scrubbed_body"] = body_red
        try:
            render_deliverable(scrubbed_master, body_red, doc, info,
                               lambda obj, spans=scrub_spans: _redact_obj(obj, spans)[0])
        except Exception as e:
            # A file left unrendered may still hold what it held: never a silent pass, and
            # never a crash that leaves later documents unscrubbed and unreported.
            esc = build_redaction_escalation(
                doc_id=doc["id"], document_name=doc["name"], stage="REDACT_APPLY",
                failure_kind="pii_survives_in_deliverable",
                raw_output_path=redactor_r.get("raw_text_path") or redactor_raw_path,
                detail={"render_failed": type(e).__name__})
            _post_redaction_block(orch, esc)
            summary[doc["id"]] = {"redacted": False, "state": "BLOCKED",
                                  "failure_kind": esc["failure_kind"], "escalation": esc}
            # Its files are still scrubbed, the master's own too, since no render rewrote
            # them: blocked is not left as written. The docx, a binary file, stays as it was.
            scrub_text_artifacts_and_verify(scrub_spans, info, located, by_artifact,
                                            also=("amendments_json", "amendments_md"))
            continue
        rep = scrub_text_artifacts_and_verify(scrub_spans, info, located, by_artifact)
        if rep["dropped"]:
            esc = build_redaction_escalation(
                doc_id=doc["id"], document_name=doc["name"], stage="REDACT_APPLY",
                failure_kind="span_dropped",
                raw_output_path=redactor_r.get("raw_text_path") or redactor_raw_path,
                detail={"dropped_spans": rep["dropped"], "by_artifact": rep["by_artifact"]})
            _post_redaction_block(orch, esc)
            summary[doc["id"]] = {"redacted": False, "state": "BLOCKED",
                                  "failure_kind": esc["failure_kind"], "escalation": esc}
            continue
        if rep["survivors"]:
            esc = build_redaction_escalation(
                doc_id=doc["id"], document_name=doc["name"], stage="REDACT_APPLY",
                failure_kind="pii_survives_in_deliverable",
                raw_output_path=redactor_r.get("raw_text_path") or redactor_raw_path,
                detail={"survivors": rep["survivors"], "by_artifact": rep["by_artifact"]})
            _post_redaction_block(orch, esc)
            summary[doc["id"]] = {"redacted": False, "state": "BLOCKED",
                                  "failure_kind": esc["failure_kind"], "escalation": esc}
            continue
        if _held_no_other_span(redactions, rep, body_red, doc):
            # This document has no span of its own and no other document's span
            # occurred in its text or artifacts (verified absent above): a genuine NONE.
            _post_redaction(orch, doc["id"], "REDACTION_NONE",
                            {"screened_amendments": len(amendments), "raw_output_path": redactor_raw_path,
                             "run_spans_checked": len(scrub_spans), **unknown})
            summary[doc["id"]] = {"redacted": False, "state": "NONE", "redactions": 0, **unknown}
            continue
        # APPLIED means: every proposed span located and VERIFIED ABSENT from every
        # shipped artifact. Report spans, not documents; reconcile so proposed/applied
        # cannot silently diverge.
        _post_redaction(orch, doc["id"], "REDACTION_APPLIED",
                        {"proposed_spans": rep["proposed"], "applied_spans": rep["applied"],
                         "substitutions": rep["total_subs"], "by_artifact": rep["by_artifact"],
                         "only_other_documents_spans": _only_others(redactions), **unknown})
        # A document with no span of its own that held another document's reports that
        # plainly, not as "0 spans applied" and nothing else.
        summary[doc["id"]] = {"redacted": True, "state": "APPLIED",
                              "proposed_spans": rep["proposed"], "applied_spans": rep["applied"],
                              "substitutions": rep["total_subs"],
                              "only_other_documents_spans": _only_others(redactions), **unknown}
    # Whatever state a document ended in, its report says what is unknown.
    if spans_unknown_from:
        for entry in summary.values():
            entry["spans_unknown_from"] = spans_unknown_from
    return summary
