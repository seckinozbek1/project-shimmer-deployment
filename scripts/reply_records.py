"""Every model reply of a run, saved once per call (S1 Part 4).

A run folder keeps, under ``<run_dir>/audit/model_replies/``, ONE JSON file per
model call, named ``<sequence>_<call_id>.json``, written by ``write`` at the one
point where the raw reply exists for every backend: inside
``AgentWrapper.call_claude``, ``call_gpt``, ``call_qwen`` and ``call_local``, and
inside ``auditor_pairs.predict`` for the Auditor896 classifier label. A call that
reaches a backend function by any route (run_task, the draft memo's direct
call_claude, the editorial board, the redaction stage, multi-round) is therefore
recorded exactly once.

What happened to a reply is decided LATER than the reply, so it is written in a
separate append-only step: ``write_outcome`` appends one line to
``outcomes.jsonl`` in the same folder, keyed by call id. A later line for the
same call id supersedes an earlier one (run_task records ``accepted_to_bus``;
phase 6 may later record ``not_promoted`` for the same call). A record with no
outcome line reads as ``not_decided``.

Sensitive (redaction-enabled) runs keep hashes and lengths only, under the same
labels the contract-violation dump writes (``sha256``, ``length_bytes``), for the
reply and for the payload; the sensitivity test is the wrapper's own
``sensitive`` flag, the one ``_persist_contract_violation_raw_text`` reads.

With no run context (the harness, probes, gate fixtures) nothing is written
anywhere: there is no fallback to ``output/``. Embedding calls are not saved.
The folder is never committed (``.gitignore`` and ``guard_secrets.py --staged``).
A write failure is logged by type and never takes a call down.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from shimmer_logging import get_logger, log_event

SCHEMA_VERSION = 1
DIRNAME = "model_replies"
OUTCOMES_NAME = "outcomes.jsonl"
# Each value is tied to code that exists today (see the call sites that write it).
OUTCOMES = (
    "accepted_to_bus",       # agent_wrapper.run_task: ok, envelope posted with its items
    "advisory_not_record",   # agent_wrapper.run_task: items_are_advisory, items withheld from the bus
    "not_promoted",          # pipeline.phase_6_synthesis: a model finding in the _withheld list
    "contract_violation",    # agent_wrapper.run_task: the reply failed the output contract
    "refused",               # agent_wrapper.run_task: a valid reply with status "refused"
    "backend_failure",       # agent_wrapper.run_task / draft memo: the backend call failed
    "classified",            # auditor_pairs.prepare_context: Auditor896 returned a relation
    "classifier_failed",     # auditor_pairs.prepare_context: Auditor896 failed
    "free_text",             # pipeline._draft_generate_with_evidence: the draft memo
    "not_decided",           # read-side default when no outcome line exists
)

_LOG = get_logger("shimmer.replies")
_LOCK = threading.Lock()
_NEXT = {}            # folder key -> next sequence number
_SENSITIVE = set()    # folder keys that have recorded a sensitive call (sticky)


def folder(run_context):
    """``<run_dir>/audit/model_replies``, or None when there is no usable run context."""
    if run_context is None:
        return None
    run_dir = getattr(run_context, "run_dir", None)
    if not isinstance(run_dir, (str, os.PathLike)):
        return None
    return Path(run_dir) / "audit" / DIRNAME


def _key(path):
    return os.path.normcase(os.path.abspath(str(path)))


def _sequence(path):
    """Next sequence number for this folder, taken under the module lock."""
    key = _key(path)
    if key not in _NEXT:
        highest = 0
        if path.is_dir():
            for entry in path.iterdir():
                head = entry.name.split("_", 1)[0]
                if entry.suffix == ".json" and head.isdigit():
                    highest = max(highest, int(head))
        _NEXT[key] = highest + 1
    value = _NEXT[key]
    _NEXT[key] = value + 1
    return value


def _digest(text):
    data = (text or "").encode("utf-8")
    return {"sha256": hashlib.sha256(data).hexdigest(), "length_bytes": len(data)}


def _now():
    return datetime.now(timezone.utc).isoformat()


def write(run_context, *, agent, call_id=None, backend, model_id, model_mode=None,
          payload=None, payload_form=None, reply=None, ok=True, error="",
          decoding=None, sensitive=False, phase="", doc_id=""):
    """Save one call's reply. Returns the call id (minted when none was given), or
    None when nothing was written (no run context, or the write failed).

    ``payload`` is the exact text sent to the backend after any outbound masking
    (None when the call ended before a request was built); its SHA-256 is taken
    over its UTF-8 bytes. ``reply`` is the raw reply text (None when there was
    none)."""
    path = folder(run_context)
    if path is None:
        return None
    call_id = str(call_id or uuid.uuid4().hex)
    try:
        with _LOCK:
            key = _key(path)
            if sensitive:
                _SENSITIVE.add(key)
            hashed = bool(sensitive) or key in _SENSITIVE
            path.mkdir(parents=True, exist_ok=True)
            sequence = _sequence(path)
            record = {
                "schema_version": SCHEMA_VERSION,
                "sequence": sequence,
                "call_id": call_id,
                "run_id": getattr(run_context, "run_id", None),
                "agent": agent,
                "backend": backend,
                "model_id": model_id,
                "model_mode": model_mode,
                "timestamp": _now(),
                "phase": phase or "",
                "doc_id": doc_id or "",
                "decoding": decoding or {},
                "backend_ok": bool(ok),
                "error_category": (str(error).split(":", 1)[0][:80] if error else None),
                "sensitive": hashed,
                "payload": None,
                "reply": None,
            }
            if not hashed and error:
                record["error"] = str(error)
            if payload is not None:
                record["payload"] = dict(_digest(payload), form=payload_form)
                if not hashed:
                    record["payload"]["text"] = payload
            if reply is not None:
                record["reply"] = _digest(reply)
                if not hashed:
                    record["reply"]["text"] = reply
            target = path / f"{sequence:06d}_{call_id}.json"
            with target.open("x", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False, sort_keys=True, indent=1, default=str)
        return call_id
    except Exception as exc:  # recording must never take a call down
        log_event(_LOG, f"reply_record_write_error error_type={type(exc).__name__}", level="warning")
        return None


def write_outcome(run_context, call_id, outcome, *, source, **detail):
    """Append what happened to a reply, keyed by its call id. Nothing is written
    with no run context or no call id. An unknown outcome is a programming error."""
    if outcome not in OUTCOMES or outcome == "not_decided":
        raise ValueError("unknown reply outcome")
    path = folder(run_context)
    if path is None or not call_id:
        return False
    row = dict(detail, call_id=str(call_id), outcome=outcome, source=source, timestamp=_now())
    try:
        with _LOCK:
            path.mkdir(parents=True, exist_ok=True)
            with (path / OUTCOMES_NAME).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        return True
    except Exception as exc:
        log_event(_LOG, f"reply_outcome_write_error error_type={type(exc).__name__}", level="warning")
        return False


def is_refusal(parsed, raw_text):
    """The refusal test auditor_pairs.compare already applies to a reply: a
    "refused" status on the parsed object or on the reply as written (the
    canonical envelope is rebuilt without it, so the wire is read too)."""
    if isinstance(parsed, dict) and parsed.get("status") == "refused":
        return True
    try:
        wire = json.loads(raw_text or "")
    except (ValueError, TypeError):
        return False
    return isinstance(wire, dict) and wire.get("status") == "refused"


def _same_item(original, finding):
    """A finding that phase 6 carries is the posted item plus stamps (agent,
    source_rule_id): the same item_id and revision, or every original field kept."""
    if not isinstance(original, dict) or not isinstance(finding, dict):
        return False
    if original.get("item_id") and original.get("item_id") == finding.get("item_id"):
        return original.get("revision") == finding.get("revision")
    return bool(original) and all(finding.get(k) == v for k, v in original.items())


def mark_not_promoted(run_context, result_lists, withheld, *, doc_id):
    """Record ``not_promoted`` for every call whose reply carried a finding in
    phase 6's ``_withheld`` list. Reads only the run_task results the phase
    already holds (their call ids); returns the call ids marked."""
    if folder(run_context) is None or not withheld:
        return []
    marked = []
    for results in result_lists or ():
        for result in results or ():
            if not isinstance(result, dict) or not result.get("ok") or not result.get("call_id"):
                continue
            if result.get("doc_id") not in (None, doc_id):
                continue
            parsed = result.get("parsed")
            items = parsed.get("items") if isinstance(parsed, dict) else None
            if not isinstance(items, list):
                continue
            hits = [f for f in withheld
                    if (f.get("agent") in (None, result.get("agent")))
                    and any(_same_item(item, f) for item in items)]
            if hits and result["call_id"] not in marked:
                write_outcome(run_context, result["call_id"], "not_promoted",
                              source="phase_6_synthesis", findings_withheld=len(hits))
                marked.append(result["call_id"])
    return marked


def records(path):
    """Every saved record in a model_replies folder, in sequence order."""
    path = Path(path)
    if not path.is_dir():
        return []
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(path.glob("*.json"))]
    return sorted(rows, key=lambda r: r.get("sequence", 0))


def outcomes(path):
    """call id -> its current outcome (the last line for that call id)."""
    current = {}
    file = Path(path) / OUTCOMES_NAME
    if file.is_file():
        for line in file.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                current[row["call_id"]] = row["outcome"]
    return current


def outcome_of(path, call_id):
    return outcomes(path).get(call_id, "not_decided")
