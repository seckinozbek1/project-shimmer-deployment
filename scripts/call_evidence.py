"""Call evidence: what a model call was shown, recorded as structural identifiers.

The payload sent to a model used to be built and then discarded: nothing saved
reconstructed which units, headings or references a call actually saw, so a rule the
model was never asked and a rule the model failed to answer landed in one recall
number and were told apart by hand. This module records, per call, the structural
identifiers of what was exposed, and nothing else:

  call_id             minted per call (uuid4 hex), carried on the cost row and the
                      bus post the call produces, so the three artifacts join
  run_id, ts, phase, doc_id, agent, backend, model
  task                the work payload's own task name
  unit_id             the reviewed unit (a paired or polish call); None for a call
                      that sees a whole document
  neighbour_unit_ids  the unit ids supplied as context beside the reviewed unit
                      (the units immediately before and after it in document_map,
                      present only when the payload carried their text)
  heading_unit_id     the unit whose heading opens the reviewed passage (units are
                      heading-delimited sections, so this is the reviewed unit's own
                      id when the document map lists it)
  document_unit_ids   every unit id the payload's document map listed (orientation)
  reference_ids       every REF-* / WEB-REF-* id in the reference excerpt supplied
  reference_ids_rendered
                      the ids whose passage the budgeted renderer actually kept whole
                      in the bytes sent (bus_reader.rendered_line_ids over the finished
                      REFERENCE_INDEX section): the renderer leaves out passages over
                      its budget, so a supplied id is not always a rendered one
  payload_document_id the payload's own document_id field (a unit id on a paired
                      call, the document id on a whole-document call); doc_id above
                      is the value run_task was given, the per-document position in
                      the phases that pass one
  rule_ids            every convention id the call was asked to evaluate against
  rule_ids_rendered   the ids whose rule line survived whole in the CONVENTION_REGISTRY
                      section (the renderer keeps the first 40 rules and clips the
                      section to a token budget); a rule requested but not rendered
                      never reached the call as text
  payload_rule_id     the payload's own rule_id (a paired or polish call carries the
                      rule's text in the payload itself, which is never clipped)
  convention_text_truncated, reference_text_truncated
                      whether the token clip cut those sections
  bus_messages_rendered, bus_messages_dropped
                      how many recent bus messages reached the prompt whole and how many
                      were dropped for budget (counts; the classifier never relies on
                      bus context as evidence, so this is a recorded blind spot, not
                      a classification input)
  payload_keys        the payload's field NAMES (so "preceding_unit_text" being
                      present is on the record without its content)
  document_text_chars, document_text_truncated
                      how much of a whole-document payload reached the call, and
                      whether the token-budget clip cut it (a whole-document call
                      cannot prove a unit was inside a clipped text; the classifier
                      treats that as unknown)
  prompt_chars        the assembled prompt's length, a count

NEVER text. No unit text, no rule text, no reference text, no heading title. This
file must not become a second copy of the document; gate check 204 asserts that no
passage of the fixture document or its rule appears in the record.

Written to <run>/logs/call_evidence.jsonl, append-only, by AgentWrapper.run_task just
before dispatch. A wrapper with no run context (the harness outside a run) records
nothing and says so in its return value.
"""

from __future__ import annotations

import json
import threading

_WRITE_LOCK = threading.RLock()
from datetime import datetime, timezone
from pathlib import Path

EVIDENCE_FILENAME = "call_evidence.jsonl"

RECORD_FIELDS = (
    "call_id", "run_id", "ts", "phase", "doc_id", "agent", "backend", "model", "task",
    "payload_document_id", "unit_id", "neighbour_unit_ids", "heading_unit_id",
    "document_unit_ids", "reference_ids", "reference_ids_rendered", "rule_ids",
    "rule_ids_rendered", "payload_rule_id", "convention_text_truncated",
    "reference_text_truncated", "bus_messages_rendered", "bus_messages_dropped",
    "payload_keys", "document_text_chars", "document_text_truncated", "prompt_chars",
)

# The marker _truncate_doc leaves in a clipped document text (pipeline.py). Read
# here as a structural flag only; the text around it is never copied.
TRUNCATION_MARKER = "[truncated for token budget]"


def _ids_from(entries, key):
    out = []
    for e in entries or []:
        v = e.get(key) if isinstance(e, dict) else None
        if isinstance(v, str) and v and v not in out:
            out.append(v)
    return out


def extract(work_payload, *, call_id, run_id, phase, doc_id, agent, backend, model,
            convention_registry=None, reference_index_excerpt=None, prompt_chars=0,
            ts=None, rendered=None):
    """Build one evidence record from what run_task is about to send. Reads only
    identifiers and counts off the payload; every text field is left where it is.
    `rendered` is the ContextPackage's own report of what its budgeted sections
    kept (bus_reader.assemble_context); None for a call built outside the package
    path (the draft memo, the arithmetic probe), where nothing was rendered by it."""
    p = work_payload if isinstance(work_payload, dict) else {}
    unit_id = p.get("unit_id") if isinstance(p.get("unit_id"), str) else None
    doc_map = p.get("document_map") or p.get("document_units") or []
    document_unit_ids = _ids_from(doc_map, "unit_id")
    neighbours = []
    heading_unit_id = None
    if unit_id and unit_id in document_unit_ids:
        heading_unit_id = unit_id
        i = document_unit_ids.index(unit_id)
        if "preceding_unit_text" in p and i > 0:
            neighbours.append(document_unit_ids[i - 1])
        if "following_unit_text" in p and i + 1 < len(document_unit_ids):
            neighbours.append(document_unit_ids[i + 1])
    reference_ids = _ids_from(reference_index_excerpt, "ref_id")
    for rid in _ids_from(p.get("reference_index_excerpt"), "ref_id"):
        if rid not in reference_ids:
            reference_ids.append(rid)
    rule_ids = []
    for c in (convention_registry or {}).get("conventions", []) if isinstance(convention_registry, dict) else []:
        cid = c.get("id") if isinstance(c, dict) else None
        if isinstance(cid, str) and cid and cid not in rule_ids:
            rule_ids.append(cid)
    for cid in list(p.get("evaluate_against") or []) + [p.get("rule_id")]:
        if isinstance(cid, str) and cid and cid not in rule_ids:
            rule_ids.append(cid)
    doc_text = p.get("document_text") if isinstance(p.get("document_text"), str) else ""
    r = rendered if isinstance(rendered, dict) else {}
    pdoc = p.get("document_id")
    prule = p.get("rule_id")
    return {
        "call_id": call_id,
        "run_id": run_id or "",
        "ts": ts or datetime.now(timezone.utc).isoformat(),
        "phase": phase or "",
        "doc_id": doc_id or "",
        "agent": agent,
        "backend": backend,
        "model": model or "",
        "task": p.get("task") if isinstance(p.get("task"), str) else None,
        "payload_document_id": pdoc if isinstance(pdoc, str) else None,
        "unit_id": unit_id,
        "neighbour_unit_ids": neighbours,
        "heading_unit_id": heading_unit_id,
        "document_unit_ids": document_unit_ids,
        "reference_ids": reference_ids,
        "reference_ids_rendered": list(r.get("reference_ids") or []),
        "rule_ids": rule_ids,
        "rule_ids_rendered": list(r.get("convention_ids") or []),
        "payload_rule_id": prule if isinstance(prule, str) else None,
        "convention_text_truncated": bool(r.get("convention_text_truncated", False)),
        "reference_text_truncated": bool(r.get("reference_text_truncated", False)),
        "bus_messages_rendered": int(r.get("bus_messages_rendered") or 0),
        "bus_messages_dropped": int(r.get("bus_messages_dropped") or 0),
        "payload_keys": sorted(str(k) for k in p.keys()),
        "document_text_chars": len(doc_text),
        "document_text_truncated": TRUNCATION_MARKER in doc_text,
        "prompt_chars": int(prompt_chars or 0),
    }


def evidence_path(run_dir):
    return Path(run_dir) / "logs" / EVIDENCE_FILENAME


def record(run_context, rec):
    """Append one record under the run's logs. Returns the path written, or None
    when there is no run context to write under (the harness outside a run)."""
    logs_dir = getattr(run_context, "logs_dir", None)
    if run_context is None or not callable(logs_dir):
        return None
    path = Path(logs_dir()) / EVIDENCE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK, path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def load(run_dir):
    """Every record of a run, in write order; None when the run has no evidence
    file at all (a run that predates the recording), which is a different fact
    from an empty list (a run that recorded and made no call)."""
    path = evidence_path(run_dir)
    if not path.is_file():
        return None
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def reconstruct(run_dir, call_id):
    """One already-executed call, from the saved record alone."""
    for rec in load(run_dir) or []:
        if rec.get("call_id") == call_id:
            return rec
    return None


def rule_reached(rec, rule_id):
    """Whether the rule's TEXT reached the call: carried in the payload itself (a
    paired or polish call, never clipped) or rendered whole in the registry section.
    A rule merely requested (in rule_ids) whose line the budget clipped did not."""
    return rec.get("payload_rule_id") == rule_id or rule_id in (rec.get("rule_ids_rendered") or [])


def calls_exposing(records, *, rule_id, unit_id):
    """The recorded calls in which `unit_id` was exposed under `rule_id`: the rule's
    text reached the call (rule_reached) AND the unit was the reviewed unit, a
    supplied neighbour, or inside an unclipped whole-document payload whose map
    lists it. A clipped whole-document call never counts: the record cannot say
    which units survived the clip. A rule requested but not rendered never counts."""
    out = []
    for r in records or []:
        if not rule_reached(r, rule_id):
            continue
        if r.get("unit_id") == unit_id or unit_id in (r.get("neighbour_unit_ids") or []):
            out.append(r)
        elif (r.get("unit_id") is None and unit_id in (r.get("document_unit_ids") or [])
              and r.get("document_text_chars", 0) > 0 and not r.get("document_text_truncated")):
            out.append(r)
    return out


def leaked_text(rec, texts, *, min_len=12):
    """The first of `texts` (each a passage of the document or rule, at least
    min_len characters) that appears anywhere in the serialised record, else None.
    Gate check 204 uses this to prove the record carries identifiers, not text."""
    blob = json.dumps(rec, ensure_ascii=False)
    for t in texts:
        t = (t or "").strip()
        if len(t) >= min_len and t in blob:
            return t
    return None
