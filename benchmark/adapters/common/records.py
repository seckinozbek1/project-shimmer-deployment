"""The one record reader: a run's typed records for one document, from either form a run
writes them in (preregistration section 5.1; loop plan S5, R22 and item 0.8).

  bus           B3 and B4: the run's bus, ``logs/agent_bus.jsonl`` (docs/OUTPUT_FORMAT.md
                section 5). Every line whose ``body.payload.items`` is a list and whose
                ``body.payload.doc_id`` is the document is read. Each item that is a typed
                record (below) is copied and stamped ``written_by`` from the line that
                carried it: ``python`` exactly when ``body.backend`` is ``paired`` or
                ``computed`` and ``body.model`` starts with ``python``, ``model`` otherwise
                (section 5.4); a ``written_by`` the item carries itself is replaced. Each
                record is also stamped ``envelope_agent``, the envelope's ``agent``, so a
                reader can tell which agent's post carried it (D-066: a record from a
                partial delivery is marked).
                Supersession is within one agent and document: of the records with the same
                envelope ``agent``, the same ``doc_id`` and the same ``item_id``, only the
                highest ``revision`` is kept, a later ``ts`` and then the later line winning
                a tie (section 5.3). A judged absence appears twice (section 5.5): the
                model's raw reply, a line with a ``call_id`` that a judging-call record names
                with ``plan_kind`` ``absence_judged`` (in ``audit/pairing_map.json`` or in a
                bus line's ``body.judging_calls``), and, if Python kept the answer, Python's
                stamped copy (``body.stamped_by`` ``python``). Only the stamped copy is
                counted; the raw copy's records are listed apart (``raw_judged_absence``)
                and decide nothing. D-068: a kept answer on a plan Python could compute
                nothing for has one copy only, Python's stamped copy (``body.stamped_by``
                ``python``, ``body.judged_path`` ``uncomputable``); the model's own post of
                that call withholds its items. It is counted like any model's record.
  review_data   B2: ``deliverables/<document id>/review_data.json`` under its typed-record
                key ``findings``, each record carrying the ``written_by`` stamp B2 writes.
                Supersession by ``item_id`` alone (the file holds one document and no agent),
                the highest ``revision`` kept and the later record winning a tie.

A typed record is an object that carries a ``record_verdict`` field, or that carries the
UNCERTAIN marker (a truthy ``uncertain``, or ``confidence`` equal to ``UNCERTAIN`` once
uppercased) and names a rule (``source_rule_id`` or ``rule_id``). The same rule applies to
both forms, so the same records give the same labels whichever form holds them.

Standard library only; nothing from the repository is imported (the adapters are portable).
"""
from __future__ import annotations

import json
from pathlib import Path

BUS = "bus"
REVIEW_DATA = "review_data"
SOURCES = (BUS, REVIEW_DATA)

# --- run output names (docs/OUTPUT_FORMAT.md, output-format-v1-draft) ------------------
BUS_FILE = ("logs", "agent_bus.jsonl")    # section 5
REVIEW_DATA_FILE = "review_data.json"     # section 7, B2's form
DELIVERABLES_DIR = "deliverables"         # <run>/deliverables/<document id>/
TYPED_RECORDS_KEY = "findings"            # the key B2 writes its typed records under
PAIRING_MAP_FILE = ("audit", "pairing_map.json")
COMPUTED_BACKENDS = ("paired", "computed")  # section 5.4
PYTHON_MODEL_PREFIX = "python"
JUDGED_ABSENCE_PLAN = "absence_judged"    # section 5.6 plan_kind
RECORD_ID_FIELD = "item_id"
REVISION_FIELD = "revision"
TIME_FIELD = "ts"
WRITTEN_BY_FIELD = "written_by"
ENVELOPE_AGENT_FIELD = "envelope_agent"   # the agent of the envelope that carried a bus record
UNCERTAIN_FIELD, UNCERTAIN_VALUE, UNCERTAIN_FLAG_FIELD = "confidence", "UNCERTAIN", "uncertain"
# ---------------------------------------------------------------------------------------


def written_by(backend, model) -> str:
    """Section 5.4: `python` only for a computed backend with a model id starting `python`."""
    if str(backend or "") in COMPUTED_BACKENDS and str(model or "").startswith(PYTHON_MODEL_PREFIX):
        return "python"
    return "model"


def has_uncertain_marker(item) -> bool:
    return (bool(item.get(UNCERTAIN_FLAG_FIELD))
            or str(item.get(UNCERTAIN_FIELD, "")).upper() == UNCERTAIN_VALUE)


def is_typed_record(item) -> bool:
    """A record section 5.1 reads: it carries a record_verdict, or it is a refusal (the
    UNCERTAIN marker) that names a rule."""
    if not isinstance(item, dict):
        return False
    if "record_verdict" in item:
        return True
    return has_uncertain_marker(item) and bool(item.get("source_rule_id") or item.get("rule_id"))


def _revision(record) -> int:
    try:
        return int(record.get(REVISION_FIELD) or 0)
    except (TypeError, ValueError):
        return 0


def supersede(entries) -> list:
    """`entries` are (key, record) in reading order; key None is never superseded. Of the
    records sharing a key only one is kept: the highest revision, then the later `ts`
    (compared as strings, ISO 8601), then the later entry. Reading order is kept."""
    best = {}
    for index, (key, record) in enumerate(entries):
        if key is None:
            continue
        rank = (_revision(record), str(record.get(TIME_FIELD) or ""), index)
        if key not in best or rank >= best[key][0]:
            best[key] = (rank, index)
    return [record for index, (key, record) in enumerate(entries)
            if key is None or best[key][1] == index]


def _record_key(record, *scope):
    value = record.get(RECORD_ID_FIELD)
    if value in (None, ""):
        return None
    return tuple(str(s) for s in scope) + (str(value),)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        return None, type(exc).__name__


def judged_absence_calls(pairing, document_id) -> set:
    """The call ids of the document's judged-absence calls in a pairing map."""
    if not isinstance(pairing, dict):
        return set()
    mine = pairing.get(document_id)
    mine = mine if isinstance(mine, dict) else pairing
    calls = mine.get("judging_calls") if isinstance(mine, dict) else None
    return {str(c.get("call_id")) for c in calls or []
            if isinstance(c, dict) and c.get("plan_kind") == JUDGED_ABSENCE_PLAN and c.get("call_id")}


def read_bus(run_dir, document_id) -> dict:
    """{failure_reasons, faults, records, raw_judged_absence} from the run's bus."""
    out = {"failure_reasons": [], "faults": [], "records": [], "raw_judged_absence": []}
    path = Path(run_dir).joinpath(*BUS_FILE)
    if not path.is_file():
        out["failure_reasons"].append("bus_missing")
        return out
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):
        out["failure_reasons"].append("bus_unreadable")
        return out
    posts, bad = [], 0
    absence_calls = set()
    pairing_path = Path(run_dir).joinpath(*PAIRING_MAP_FILE)
    if pairing_path.is_file():
        pairing, _error = _read_json(pairing_path)
        absence_calls |= judged_absence_calls(pairing, document_id)
    for line in lines:
        if not line.strip():
            continue
        try:
            post = json.loads(line)
        except ValueError:
            bad += 1
            continue
        body = post.get("body") if isinstance(post, dict) else None
        if not isinstance(body, dict):
            continue
        for call in body.get("judging_calls") or []:
            if (isinstance(call, dict) and call.get("plan_kind") == JUDGED_ABSENCE_PLAN
                    and call.get("call_id") and body.get("doc_id", document_id) == document_id):
                absence_calls.add(str(call["call_id"]))
        payload = body.get("payload")
        if isinstance(payload, dict) and isinstance(payload.get("items"), list) \
                and str(payload.get("doc_id")) == str(document_id):
            posts.append((body, payload))
    if bad:
        out["faults"].append("bus_lines_unreadable:%d" % bad)
    entries = []
    for body, payload in posts:
        stamp = written_by(body.get("backend"), body.get("model"))
        agent = payload.get("agent")
        records = [dict(item, **{WRITTEN_BY_FIELD: stamp, ENVELOPE_AGENT_FIELD: str(agent or "")})
                   for item in payload["items"] if is_typed_record(item)]
        raw = (not body.get("stamped_by") and body.get("call_id")
               and str(body["call_id"]) in absence_calls)
        if raw:
            out["raw_judged_absence"].extend(records)
            continue
        entries.extend((_record_key(r, agent, document_id), r) for r in records)
    out["records"] = supersede(entries)
    return out


def review_data_path(run_dir, document_id) -> Path:
    return Path(run_dir) / DELIVERABLES_DIR / str(document_id) / REVIEW_DATA_FILE


def read_review_data(run_dir, document_id) -> dict:
    """{failure_reasons, faults, records, raw_judged_absence} from B2's review_data.json."""
    out = {"failure_reasons": [], "faults": [], "records": [], "raw_judged_absence": []}
    path = review_data_path(run_dir, document_id)
    if not path.is_file():
        out["failure_reasons"].append("review_data_missing")
        return out
    data, _error = _read_json(path)
    if data is None or not isinstance(data, dict):
        out["failure_reasons"].append("review_data_unreadable")
    elif TYPED_RECORDS_KEY not in data:
        out["faults"].append("typed_records_key_absent:" + TYPED_RECORDS_KEY)
    else:
        records = data[TYPED_RECORDS_KEY]
        if not isinstance(records, list) or not all(isinstance(r, dict) for r in records):
            out["faults"].append("typed_records_not_a_list_of_objects")
        else:
            kept = [r for r in records if is_typed_record(r)]
            out["records"] = supersede([(_record_key(r), r) for r in kept])
    return out


def read_records(run_dir, document_id, source) -> dict:
    """The document's typed records from `source` (`bus` or `review_data`)."""
    if source == BUS:
        result = read_bus(run_dir, document_id)
    elif source == REVIEW_DATA:
        result = read_review_data(run_dir, document_id)
    else:
        raise ValueError("unknown record source %r (one of %s)" % (source, ", ".join(SOURCES)))
    result["source"] = source
    return result
