"""Read-only projections of a saved run folder for the console (loop S7, items 1 and 2).

Each function reads files a run already wrote and returns a JSON-safe dict. The
server's routes are thin wrappers around them (scripts/server.py), so the same
projection is checked with and without fastapi (scripts/console_view_checks.py).

Nothing here writes, calls a model, opens the network, reads `benchmark/`, a
scorer output or an answer key. Reply and payload TEXT is never read into a view
(DS7-1): a reply record's sizes and outcome are, its text is not.

The sealed filter (Annex B.8, plan closure 2). `exposure(run_dir)` reads, in the
run folder and up to three parent folders (the cloud layout
`<session>/downloaded/evidence/run`), `run_record.json` and `seal.json`. A run
is sealed when a marker says `exposure: sealed`, when a `seal.json` on that path
does not say `exposure: exposed`, or when a marker on that path cannot be read
(fail closed). A sealed run's views carry counts and timings only: no finding
text, no unit id, no rule id, no reason, no per-flaw row.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import run_report_text

SEALED = "sealed"
EXPOSED = "exposed"
# Parent folders the marker walk climbs above the run folder (closure 2).
WALK_LEVELS = 3
MARKER_NAMES = ("run_record.json", "seal.json")
NOT_KNOWN = "not known"
NOT_PRESENT = "not present in this installation"
TEST_CHANGE_REQUESTS = Path("docs") / "test_change_requests.md"
# The fields of one saved reply record a view may carry: metadata only, never text.
REPLY_FIELDS = ("sequence", "call_id", "agent", "backend", "model_id", "model_mode",
                "phase", "doc_id", "timestamp", "backend_ok", "error_category", "sensitive")
_TCR_HEADING = re.compile(r"^### (TCR-\d+)\.\s*(.*)$")
_TCR_FIELD = re.compile(r"^- \*\*([^*]+)\*\*:\s?(.*)$")


def _json_dict(path):
    """The JSON object in `path`, or None when it cannot be read as one."""
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _jsonl(path):
    """Every JSON object line of `path`; a line that does not parse is skipped."""
    rows = []
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return rows
    for line in lines:
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def path_chain(run_dir):
    """The run folder, then up to WALK_LEVELS parent folders."""
    run_dir = Path(run_dir)
    return [run_dir] + list(run_dir.parents)[:WALK_LEVELS]


def exposure(run_dir):
    """`sealed` or `exposed` for this run folder (module docstring, closure 2)."""
    for folder in path_chain(run_dir):
        for name in MARKER_NAMES:
            path = folder / name
            if not path.is_file():
                continue
            record = _json_dict(path)
            if record is None:
                return SEALED
            value = record.get("exposure")
            if value == SEALED:
                return SEALED
            if name == "seal.json" and value != EXPOSED:
                return SEALED
    return EXPOSED


def _base(run_dir):
    state = exposure(run_dir)
    out = {"exposure": state}
    if state == SEALED:
        out["sealed_note"] = run_report_text.SEALED_NOTE
    return out


def replies(run_dir):
    """Saved model replies: per call metadata, sizes and outcome; counts by outcome."""
    import reply_records
    out = _base(run_dir)
    sealed = out["exposure"] == SEALED
    folder = Path(run_dir) / "audit" / reply_records.DIRNAME
    calls, unreadable = [], 0
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            record = _json_dict(path)
            if record is None:
                unreadable += 1
                continue
            row = {key: record.get(key) for key in REPLY_FIELDS}
            for part in ("payload", "reply"):
                value = record.get(part)
                row[part + "_bytes"] = value.get("length_bytes") if isinstance(value, dict) else None
            calls.append(row)
    latest = {}
    for line in _jsonl(folder / reply_records.OUTCOMES_NAME):
        if line.get("call_id"):
            latest[str(line["call_id"])] = line.get("outcome")
    by_outcome = {}
    for row in calls:
        row["outcome"] = latest.get(str(row.get("call_id")), "not_decided")
        by_outcome[row["outcome"]] = by_outcome.get(row["outcome"], 0) + 1
    stamps = sorted(r["timestamp"] for r in calls if isinstance(r.get("timestamp"), str))
    out.update(recorded=folder.is_dir(), count=len(calls), unreadable_records=unreadable,
               by_outcome=by_outcome, first_call_at=stamps[0] if stamps else None,
               last_call_at=stamps[-1] if stamps else None)
    if not sealed:
        by_agent = {}
        for row in calls:
            key = str(row.get("agent") or "?")
            by_agent[key] = by_agent.get(key, 0) + 1
        out.update(by_agent=by_agent, calls=calls)
    return out


def _output_language(run_dir):
    import run_options
    try:
        return run_options.saved(run_dir).output_language
    except (OSError, ValueError, TypeError):
        return "en"


def model_findings(run_dir, bus_findings=None):
    """The master's model findings per document, each item carrying the mark; and
    the producer counts (summary_generators.findings_provenance) over the run's
    bus findings when they are given."""
    import finding_record
    import localization
    from amendment_render import MODEL_FINDINGS_KEY
    from run_context import DELIVERABLE_FILENAMES
    out = _base(run_dir)
    sealed = out["exposure"] == SEALED
    language = _output_language(run_dir)
    documents, total, masters = [], 0, 0
    root = Path(run_dir) / "deliverables"
    folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    for folder in folders:
        master = _json_dict(folder / DELIVERABLE_FILENAMES["amendments_json"])
        if master is None:
            continue
        masters += 1
        items = [f for f in master.get(MODEL_FINDINGS_KEY) or [] if isinstance(f, dict)]
        total += len(items)
        if sealed:
            continue
        shown = []
        for item in items:
            shown.append({
                "agent": item.get("agent") or "",
                "rule_id": finding_record.resolved_rule_id(item) or "",
                "source_rule_id": item.get("source_rule_id") or "",
                "unit_id": item.get("unit_id") or "",
                "relation": item.get("relation"),
                "field_label": item.get("field_label") or "",
                "value_a": item.get("value_a"), "unit_a": item.get("unit_a"),
                "value_b": item.get("value_b"), "unit_b": item.get("unit_b"),
                "model_claimed_verdict": item.get("model_claimed_verdict"),
                "line": finding_record.reader_line(item, output_language=language),
                "model_wrote": str(item.get("explanation") or item.get("reasoning") or ""),
                "reader_notes": [localization.message(n, language) for n in item.get("reader_notes") or []],
                "written_by": finding_record.WRITTEN_BY_MODEL,
                "checked_by_python": False, "promoted": False,
                "mark": finding_record.MODEL_FINDING_MARK})
        documents.append({"doc_id": master.get("document_id") or folder.name, "count": len(items),
                          "items": shown})
    out.update(count=total, documents_with_a_master=masters,
               mark=finding_record.MODEL_FINDING_MARK)
    if not sealed:
        out["documents"] = documents
    if bus_findings is not None:
        import summary_generators
        provenance = summary_generators.findings_provenance(bus_findings)
        if sealed:
            provenance = {k: v for k, v in provenance.items() if isinstance(v, int)}
        out["provenance"] = provenance
    return out


def _fact_checker(run_dir, run_id, root):
    """FACT_CHECKER's withholding for this run: from the run's own activation
    record when it is valid, else from this installation's current review scope,
    labelled as such."""
    import routing_view
    activation = routing_view.read_activation(run_dir, run_id)
    reasons = list(run_report_text.FACT_CHECKER_REASONS)
    if activation.get("recorded"):
        rows = [r for r in activation.get("decisions") or [] if r.get("agent") == "FACT_CHECKER"]
        withheld = any(r.get("reason") == "operator_withheld_for_corpus" for r in rows)
        called = any(r.get("actual_call") for r in rows)
        state = "withheld" if withheld else ("called" if called else "not_reached")
        return {"source": "run_activation_record", "state": state,
                "reasons": reasons if withheld else []}
    scope = _json_dict(Path(root) / "config" / "review_scope.json") or {}
    withheld = "FACT_CHECKER" in (scope.get("withheld_audit_agents") or [])
    return {"source": "current_review_scope", "state": "withheld" if withheld else "not_withheld",
            "reasons": reasons if withheld else []}


def switches(run_dir, run_id, root):
    """INST_FINDER's setting for this run (audit/agent_switches.json) and
    FACT_CHECKER's withholding with the two Annex B.4 reasons. Settings, not
    results: a sealed run shows them too."""
    out = _base(run_dir)
    path = Path(run_dir) / "audit" / "agent_switches.json"
    if not path.is_file():
        inst = {"availability": "not_recorded"}
    else:
        record = _json_dict(path)
        if record is None or not isinstance(record.get("switched_off"), list):
            inst = {"availability": "invalid"}
        else:
            if record.get("refusal"):
                state = "off_refused"
            elif record.get("setting") == "off" and record.get("ratified_by"):
                state = "off_ratified"
            else:
                state = "on"
            inst = {"availability": "recorded", "state": state, "setting": record.get("setting"),
                    "variable": record.get("variable"), "value": record.get("value"),
                    "switched_off": record["switched_off"],
                    "ratified_by": record.get("ratified_by"), "refusal": record.get("refusal")}
    out.update(inst_finder=inst, fact_checker=_fact_checker(run_dir, run_id, root))
    return out


def _found(run_dir, name):
    """(folder, object) for the nearest `name` on the run's path, or (None, None)."""
    for folder in path_chain(run_dir):
        if (folder / name).is_file():
            return folder, _json_dict(folder / name)
    return None, None


def _run_folder_cost(run_dir):
    import model_telemetry
    run_dir = Path(run_dir)
    lines = [r for r in _jsonl(run_dir / "logs" / "cost_tracker.jsonl") if "cost_usd" in r]
    infra = [r for r in _jsonl(run_dir / "audit" / "infrastructure_cost.jsonl")
             if r.get("event") == "infrastructure_cost"]
    records = infra + [dict(event="api_cost", estimated_cost=r["cost_usd"]) for r in lines]
    try:
        cost = model_telemetry.cost(records)
    except (KeyError, TypeError, ValueError):
        cost = {"infrastructure_estimate": None, "model_api_estimate": None, "combined_estimate": None}
    return {"source": "run_folder", "model_calls_with_a_cost_line": len(lines),
            "model_api_usd": cost.get("model_api_estimate"),
            "infrastructure_usd": cost.get("infrastructure_estimate"),
            "combined_usd": cost.get("combined_estimate"), "invoice": False}


def report(run_dir):
    """The run report: the 11.12 rows of a FINAL_STATUS.json on the run's path,
    else none; cost from that file, else from the run folder's own cost lines;
    budget from an execution_manifest.json on the path, else not known."""
    out = _base(run_dir)
    sealed = out["exposure"] == SEALED
    final_dir, final = _found(run_dir, "FINAL_STATUS.json")
    _, record = _found(run_dir, "run_record.json")
    _, manifest = _found(run_dir, "execution_manifest.json")
    rows = []
    if isinstance(final, dict) and isinstance(final.get("report"), dict):
        rows = [{"label": str(k), "value": str(v)} for k, v in final["report"].items()]
        if sealed:
            rows = [r for r in rows if r["label"] in run_report_text.SEALED_REPORT_ROWS]
        out["source"] = "final_status"
    else:
        out["source"] = "run_folder"
        out["note"] = "no cloud report for this run"
    estimates = final.get("cost_estimates") if isinstance(final, dict) else None
    if isinstance(estimates, dict):
        cost = {"source": "final_status", "model_api_usd": estimates.get("model_api_estimate"),
                "infrastructure_usd": estimates.get("infrastructure_estimate"),
                "combined_usd": estimates.get("combined_estimate"), "invoice": False}
    else:
        cost = _run_folder_cost(run_dir)
    budget = {"soft_usd": NOT_KNOWN, "hard_usd": NOT_KNOWN, "within_hard_ceiling": NOT_KNOWN}
    if isinstance(manifest, dict):
        for key, field in (("soft_usd", "soft_budget_usd"), ("hard_usd", "hard_ceiling_usd")):
            if isinstance(manifest.get(field), (int, float)):
                budget[key] = manifest[field]
    if isinstance(final, dict) and isinstance(final.get("within_hard_ceiling"), bool):
        budget["within_hard_ceiling"] = final["within_hard_ceiling"]
    purpose = record.get("purpose") if isinstance(record, dict) else None
    out.update(purpose=purpose or NOT_KNOWN, rows=rows, cost=cost, budget=budget,
               report_found=final_dir is not None)
    return out


def round_reuse(run_dir):
    """audit/round_reuse.json as a rounds table: per round document, units reused
    and recomputed; per unit (exposed only) its status and where it was reused from."""
    import multi_round_rounds
    sealed = exposure(run_dir) == SEALED
    try:
        record = multi_round_rounds.read(run_dir)
    except (OSError, ValueError):
        return {"availability": "invalid"}
    if not isinstance(record, dict):
        return {"availability": "not_recorded"}
    rounds, reused, computed = [], 0, 0
    for rnd in record.get("rounds") or []:
        documents = []
        for doc in rnd.get("documents") or []:
            units = [u for u in doc.get("units") or [] if isinstance(u, dict)]
            entry = {"availability": doc.get("availability", "recorded"),
                     "units_reused": doc.get("units_reused", 0),
                     "units_computed": doc.get("units_computed", 0),
                     "pairs_computed": doc.get("pairs_computed", 0),
                     "findings": len(doc.get("findings") or [])}
            reused += entry["units_reused"] or 0
            computed += entry["units_computed"] or 0
            if not sealed:
                entry["document_id"] = doc.get("document_id")
                entry["units"] = [{"unit_id": u.get("unit_id"), "status": u.get("status"),
                                   "reused_from": u.get("reused_from"),
                                   "findings": u.get("findings", 0),
                                   "needs_model": len(u.get("needs_model") or [])} for u in units]
            documents.append(entry)
        row = {"sequence": rnd.get("sequence"), "documents": documents}
        if not sealed:
            row["round_id"] = rnd.get("round_id")
        rounds.append(row)
    out = {"availability": record.get("availability", "recorded"), "rounds": rounds,
           "units_reused": reused, "units_computed": computed}
    if not sealed:
        out.update(case_id=record.get("case_id"), rule=record.get("rule"))
    return out


def sealed_multi_round(result):
    """What /multi-round keeps for a sealed run: whether a case was recorded and its outcome."""
    return {key: result.get(key) for key in ("recorded", "availability", "outcome")}


# The agent-level fields /activation keeps for a sealed run: who was called and how often.
SEALED_AGENT_STATE_FIELDS = ("agent", "state", "eligible", "activated", "actual_calls")
# What /activation keeps of the completion record for a sealed run: state, timings, counts.
SEALED_COMPLETION_FIELDS = ("state", "started_at", "finished_at", "reached_end", "exit_code",
                            "document_count", "amendment_count")


def sealed_activation(result):
    """What /activation keeps for a sealed run (loop S7 close, adversarial 1): the
    routing profile, each agent's state and call count, and the decisions as counts.
    A decision's evidence carries unit ids, rule ids, finding indexes and item ids
    (scripts/pipeline.py), and its reason, document and call id are per-flaw too, so
    no decision row is kept."""
    rows = result.get("decisions") or []
    completion = result.get("completion")
    return dict(_base_sealed(),
                run_id=result.get("run_id"), recorded=result.get("recorded"),
                availability=result.get("availability"), activation_mode=result.get("activation_mode"),
                completion=({k: completion.get(k) for k in SEALED_COMPLETION_FIELDS}
                            if isinstance(completion, dict) else None),
                agent_states=[{k: s.get(k) for k in SEALED_AGENT_STATE_FIELDS}
                              for s in result.get("agent_states") or []],
                decisions=[],
                decision_counts={
                    "decisions": len(rows),
                    "dispatch_attempts": sum(1 for r in rows if r.get("actual_call") is True),
                    "non_calls": sum(1 for r in rows if r.get("activated") is False),
                    "failures": sum(1 for r in rows
                                    if r.get("state") in ("execution_failure", "pre_dispatch_failure")),
                    "recovered": sum(1 for r in rows if r.get("recovered") is True),
                    "capped": sum(1 for r in rows if r.get("truncated") is True)})


# What a pending governed question keeps for a sealed run: when it was asked and
# what happens if nobody answers. Its topic, message and payload are withheld.
SEALED_APPROVAL_FIELDS = ("asked_at", "default_on_timeout", "timeout_at")


def sealed_approval(pending):
    """A sealed run's pending question for GET /approvals and GET /runs/{run_id}: the
    payload of a governed question can carry a finding, a rule or a unit, so only its
    timings are kept, with the same keys present and the rest emptied."""
    return dict(_base_sealed(), topic=None, message="", payload={},
                **{k: pending.get(k) for k in SEALED_APPROVAL_FIELDS})


def _base_sealed():
    return {"exposure": SEALED, "sealed_note": run_report_text.SEALED_NOTE}


def test_change_requests(root):
    """docs/test_change_requests.md as rows: id, title and the entry's own fields."""
    path = Path(root) / TEST_CHANGE_REQUESTS
    if not path.is_file():
        return {"present": False, "message": NOT_PRESENT, "count": 0, "entries": []}
    entries, current = [], None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        heading = _TCR_HEADING.match(line)
        if heading:
            current = {"id": heading.group(1), "title": heading.group(2).strip(), "fields": {}}
            entries.append(current)
            continue
        if line.startswith("## "):
            current = None
            continue
        field = _TCR_FIELD.match(line)
        if current is not None and field:
            current["fields"][field.group(1).strip()] = field.group(2).strip()
    decided = sum(1 for e in entries if e["fields"].get("Decision"))
    return {"present": True, "source": TEST_CHANGE_REQUESTS.as_posix(), "count": len(entries),
            "decided": decided, "entries": entries}
