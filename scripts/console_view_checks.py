"""Loop S7 gate checks: the console's new routes and views (plan items 1 to 3).

Each check runs the live path on the committed synthetic fixture
(scripts/fixtures/console/, exposed, no real names, no benchmark data) copied
into a temporary folder. The saved model replies are NOT in the committed
fixture (plan closure 1: an audit/model_replies path is never staged); they are
written at run time by the real writer, reply_records.write, into the copy.

Every check is proven inside itself by effect_proof.prove_effect: observe, then
neutralise the code under test, observe a changed outcome and a FAIL, restore,
observe the original outcome and a PASS again.

Route checks need fastapi and report SKIP with the reason under an interpreter
without it; the view check needs Node and reports SKIP without it. Nothing here
starts a pipeline, calls a model, opens the network, or reads benchmark/, a
scorer output or an answer key. Writes go to temporary folders only.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import console_views
import finding_record
import run_report_text
from effect_proof import ProofFailure, prove_effect

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_RUNS = Path(__file__).resolve().parent / "fixtures" / "console" / "runs"
RUN_ID = "0c0501e00c0501e00c0501e00c0501e0"
DOC = "sample_ledger"
# The fixture's identifiers and words that a sealed view must never carry.
SEALED_FORBIDDEN = ("u03-zone-beta", "u02-zone-alpha", "u01-zone-alpha", "u02-zone-beta",
                    "CONV-001", "CONV-002", "CONV-003", "LEDGER-1", "LEDGER-2",
                    "rate looks higher", "STYLE_GUARDIAN", "ledger_round_1",
                    "Location and reason-confirmed recall", "recall row value")
# Text the replies written at run time carry; no route or view may show it.
REPLY_SECRETS = ("payload text that the console never shows", "reply text that the console never shows")
# Fixed clock for those replies and their outcomes, inside the fixture run's
# recorded window (status.json and audit/run_completion.json: 09:00:05 to 09:41:10).
REPLY_TIMES = ("2026-10-29T09:06:12+00:00", "2026-10-29T09:18:40+00:00", "2026-10-29T09:33:05+00:00")
OUTCOME_TIMES = ("2026-10-29T09:06:13+00:00", "2026-10-29T09:18:41+00:00", "2026-10-29T09:39:50+00:00")
# The mark as written in finding_record, read once at import so a neutralised mark
# is compared with the real one, never with itself.
MARK = finding_record.MODEL_FINDING_MARK
REASONS = run_report_text.FACT_CHECKER_REASONS
TCR_PATH = console_views.TEST_CHANGE_REQUESTS
# Exactly these answer without a token (plan closure 3, DS7-5).
EXEMPT = frozenset({"/health", "/console"})
FASTAPI_DOCS = ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc")
# Node runs with the Windows no-window flag: a gate started detached has no console
# for it to inherit (HIDDEN-A, S7 close).
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SKIP_FASTAPI = ("SKIP", "fastapi absent: this route check runs under an interpreter with fastapi "
                        "(the loop venv); skipped as not applicable here")


def _has_fastapi():
    return importlib.util.find_spec("fastapi") is not None


def _fixture_json(*parts):
    return json.loads(FIXTURE_RUNS.parent.joinpath(*parts).read_text(encoding="utf-8"))


def run_window():
    """(start, end) of the fixture run as its status.json records it."""
    status = _fixture_json("runs", RUN_ID, "status.json")
    return status["started_at"], status["completed_at"]


def _write_replies(run_dir):
    """Three calls through the real writer, with outcomes, into a temporary copy.
    The writer's clock is held to fixed times inside the fixture run's recorded
    window (REPLY_TIMES, then OUTCOME_TIMES, in call order), so every copy carries
    the same bytes and no record is stamped with the time it was written."""
    import reply_records
    stamps = iter(REPLY_TIMES + OUTCOME_TIMES)
    with patch.object(reply_records, "_now", lambda: next(stamps)):
        _write_reply_records(reply_records, run_dir)


def _write_reply_records(reply_records, run_dir):
    ctx = SimpleNamespace(run_dir=str(run_dir), run_id=RUN_ID)
    reply_records.write(ctx, agent="PROCESSOR", call_id="call-0001", backend="local",
                        model_id="fixture-model", model_mode="adapter", payload=REPLY_SECRETS[0],
                        payload_form="messages", reply=REPLY_SECRETS[1], phase="3-4", doc_id=DOC)
    reply_records.write(ctx, agent="VERIFIER", call_id="call-0002", backend="local",
                        model_id="fixture-model", model_mode="base", payload=REPLY_SECRETS[0],
                        reply=REPLY_SECRETS[1], phase="5", doc_id=DOC)
    reply_records.write(ctx, agent="PRACTICE_AUDITOR", call_id="call-0003", backend="local",
                        model_id="fixture-model", payload=REPLY_SECRETS[0], reply=None, ok=False,
                        error="backend_error: fixture", phase="5.5", doc_id=DOC)
    reply_records.write_outcome(ctx, "call-0001", "accepted_to_bus", source="fixture")
    reply_records.write_outcome(ctx, "call-0002", "accepted_to_bus", source="fixture")
    reply_records.write_outcome(ctx, "call-0002", "not_promoted", source="fixture")


def _copy_fixture(runs_dir):
    shutil.copytree(FIXTURE_RUNS, runs_dir, dirs_exist_ok=True)
    run_dir = Path(runs_dir) / RUN_ID
    _write_replies(run_dir)
    return run_dir


def _times_inside_the_run_window():
    """The fixture's run files agree on one window and every fixed reply and
    outcome time falls inside it."""
    start, end = run_window()
    completion = _fixture_json("runs", RUN_ID, "audit", "run_completion.json")
    telemetry = [json.loads(line) for line in FIXTURE_RUNS.joinpath(RUN_ID, "logs", "model_telemetry.jsonl")
                 .read_text(encoding="utf-8").splitlines() if line.strip()]
    marks = {row.get("event"): row.get("utc") for row in telemetry}
    return (completion.get("started_at") == start and completion.get("finished_at") == end
            and marks.get("pipeline_start") == start and marks.get("pipeline_end") == end
            and all(start <= t <= end for t in REPLY_TIMES + OUTCOME_TIMES))


def _final_status_rows():
    """The report rows of the committed fixture session's FINAL_STATUS.json."""
    return _fixture_json("session", "FINAL_STATUS.json")["report"]


def _make_session(folder, exposure):
    """A cloud session folder around a run, from the committed fixture session
    (scripts/fixtures/console/session/): its FINAL_STATUS.json and
    execution_manifest.json copied as they are, its run_record.json with the
    exposure added, and a seal.json carrying only the exposure."""
    folder.mkdir(parents=True, exist_ok=True)
    session = FIXTURE_RUNS.parent / "session"
    record = dict(_fixture_json("session", "run_record.json"), exposure=exposure)
    (folder / "run_record.json").write_text(json.dumps(record), encoding="utf-8")
    (folder / "seal.json").write_text(json.dumps({"exposure": exposure}), encoding="utf-8")
    for name in ("FINAL_STATUS.json", "execution_manifest.json"):
        shutil.copy2(session / name, folder / name)


@contextlib.contextmanager
def _served(runs_dir=None, with_docs=True):
    """A real scripts/server.py module isolated in a temporary root, the fixture
    copied in, replies written, a fresh token. Yields (client, headers, server, root)."""
    from fastapi.testclient import TestClient
    from startup_submit_checks import _isolated_server
    with tempfile.TemporaryDirectory(prefix="shimmer_console_views_") as tmp:
        root = Path(tmp)
        server = _isolated_server(root)
        if runs_dir is not None:
            server.RUNS_DIR = Path(runs_dir(root))
        _copy_fixture(server.RUNS_DIR)
        server._rebuild_jobs_from_disk()
        if with_docs:
            (root / "docs").mkdir()
            shutil.copy2(ROOT / console_views.TEST_CHANGE_REQUESTS, root / console_views.TEST_CHANGE_REQUESTS)
        access = secrets.token_urlsafe(24)
        with patch.dict(os.environ, {"SHIMMER_TOKEN_HASH": hashlib.sha256(access.encode()).hexdigest()}):
            yield TestClient(server.app), {"Authorization": "Bearer " + access}, server, root


def _get(client, headers, path):
    response = client.get("/runs/" + RUN_ID + path, headers=headers)
    return {"status": response.status_code, "body": response.json() if response.status_code == 200 else None}


def _proved(name, observe, verdict, neutralise, what):
    """Run the proof and return the check's own PASS with what was neutralised."""
    try:
        proof = prove_effect(name=name, validate=lambda: (FIXTURE_RUNS / RUN_ID / "status.json").is_file(),
                             observe=observe, check=lambda: verdict(observe()), neutralise=neutralise)
    except ProofFailure as exc:
        # BASELINE_FAILED is the code under test failing; any other category is the
        # proof not holding. Either way the check does not pass.
        return ("FAIL", "%s: %s" % (exc.category, verdict(observe())[1]))
    return ("PASS", "%s; neutralised (%s): FAIL; restored: PASS" % (verdict(proof["restored"])[1], what))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def check_replies_route():
    if not _has_fastapi():
        return SKIP_FASTAPI
    with _served() as (client, headers, _server, _root):
        def observe():
            return {"anonymous": client.get("/runs/" + RUN_ID + "/replies").status_code,
                    "authorised": _get(client, headers, "/replies")}

        def verdict(o):
            body = (o["authorised"] or {}).get("body") or {}
            text = json.dumps(body)
            calls = body.get("calls") or []
            ok = (o["anonymous"] == 401 and o["authorised"]["status"] == 200 and body.get("count") == 3
                  and body.get("by_outcome") == {"accepted_to_bus": 1, "not_promoted": 1, "not_decided": 1}
                  and [c.get("sequence") for c in calls] == [1, 2, 3]
                  and all(set(console_views.REPLY_FIELDS) <= set(c) for c in calls)
                  and calls[0]["payload_bytes"] == len(REPLY_SECRETS[0].encode()) and calls[2]["reply_bytes"] is None
                  and not any(s in text for s in REPLY_SECRETS) and '"text"' not in text
                  and body.get("exposure") == "exposed"
                  and [c.get("timestamp") for c in calls] == list(REPLY_TIMES)
                  and body.get("first_call_at") == REPLY_TIMES[0] and body.get("last_call_at") == REPLY_TIMES[-1]
                  and _times_inside_the_run_window())
            return ("PASS" if ok else "FAIL",
                    "GET /runs/{run_id}/replies: 401 without a token; 3 calls with metadata, sizes and the latest "
                    "outcome, counts by outcome, no reply or payload text; call times are the fixed fixture times, "
                    "inside the run window that status.json, audit/run_completion.json and the telemetry agree on")
        return _proved("replies_route", observe, verdict,
                       lambda: patch.object(console_views, "REPLY_FIELDS", console_views.REPLY_FIELDS + ("reply",)),
                       "the projection widened to carry the reply record")


def check_model_findings_route():
    if not _has_fastapi():
        return SKIP_FASTAPI
    with _served() as (client, headers, _server, _root):
        def observe():
            return {"anonymous": client.get("/runs/" + RUN_ID + "/model-findings").status_code,
                    "authorised": _get(client, headers, "/model-findings")}

        def verdict(o):
            body = (o["authorised"] or {}).get("body") or {}
            items = [i for d in body.get("documents") or [] for i in d.get("items") or []]
            prov = body.get("provenance") or {}
            ok = (o["anonymous"] == 401 and body.get("count") == 1 and len(items) == 1
                  and all(i.get("mark") == MARK for i in items)
                  and body.get("mark") == MARK
                  and all(i.get("written_by") == "model" and i.get("promoted") is False
                          and i.get("checked_by_python") is False and "confidence" not in i
                          and "record_verdict" not in i for i in items)
                  and items[0]["unit_id"] == "u03-zone-beta" and items[0]["model_wrote"]
                  and prov.get("computed") == 1 and prov.get("model") == 1
                  and prov.get("model_agents") == ["STYLE_GUARDIAN"])
            return ("PASS" if ok else "FAIL",
                    "GET /runs/{run_id}/model-findings: 401 without a token; the master's model finding with "
                    "MODEL_FINDING_MARK, written_by model, not promoted, not checked; producer counts from the bus")
        return _proved("model_findings_route", observe, verdict,
                       lambda: patch.object(finding_record, "MODEL_FINDING_MARK", ""),
                       "the mark emptied")


def check_switches_route():
    if not _has_fastapi():
        return SKIP_FASTAPI
    spec = importlib.util.spec_from_file_location("console_checks_analysis",
                                                  ROOT / "tools" / "analyze_ordinary_final_run.py")
    import sys
    tools = str(ROOT / "tools")
    added = tools not in sys.path
    if added:
        sys.path.insert(0, tools)
    try:
        analysis = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(analysis)
    finally:
        if added:
            sys.path.remove(tools)
    if analysis.FACT_CHECKER_REASONS is not run_report_text.FACT_CHECKER_REASONS:
        return ("FAIL", "tools/analyze_ordinary_final_run.py keeps its own copy of the Annex B.4 reasons")
    with _served() as (client, headers, server, root):
        run_dir = server.RUNS_DIR / RUN_ID
        switches = run_dir / "audit" / "agent_switches.json"
        activation = run_dir / "audit" / "agent_activation.json"
        original_switch, original_activation = switches.read_bytes(), activation.read_bytes()
        (root / "config").mkdir(exist_ok=True)
        (root / "config" / "review_scope.json").write_text(json.dumps({"withheld_audit_agents": ["FACT_CHECKER"]}),
                                                         encoding="utf-8")

        def variant(record):
            switches.write_text(json.dumps(dict(json.loads(original_switch), **record)), encoding="utf-8")
            return (_get(client, headers, "/switches")["body"] or {}).get("inst_finder", {}).get("state")

        def observe():
            out = {"anonymous": client.get("/runs/" + RUN_ID + "/switches").status_code,
                   "authorised": _get(client, headers, "/switches")}
            out["off_ratified"] = variant({"setting": "off", "switched_off": ["INST_FINDER"], "ratified_by": "INFRA-099"})
            out["off_refused"] = variant({"setting": "off", "refusal": "[inst-finder-switch] STOP: fixture"})
            switches.unlink()
            out["missing"] = (_get(client, headers, "/switches")["body"] or {}).get("inst_finder")
            switches.write_bytes(original_switch)
            activation.unlink()
            out["no_activation"] = (_get(client, headers, "/switches")["body"] or {}).get("fact_checker")
            activation.write_bytes(original_activation)
            return out

        def verdict(o):
            body = (o["authorised"] or {}).get("body") or {}
            fc = body.get("fact_checker") or {}
            ok = (o["anonymous"] == 401 and body.get("inst_finder", {}).get("state") == "on"
                  and fc.get("source") == "run_activation_record" and fc.get("state") == "withheld"
                  and tuple(fc.get("reasons") or ()) == REASONS and len(REASONS) == 2
                  and o["off_ratified"] == "off_ratified" and o["off_refused"] == "off_refused"
                  and o["missing"] == {"availability": "not_recorded"}
                  and (o["no_activation"] or {}).get("source") == "current_review_scope"
                  and (o["no_activation"] or {}).get("state") == "withheld")
            return ("PASS" if ok else "FAIL",
                    "GET /runs/{run_id}/switches: 401 without a token; INST_FINDER on, off and ratified, off and "
                    "refused, not recorded; FACT_CHECKER withheld from the run's activation record with both B.4 "
                    "reasons, else from the current review scope, said so; one copy of the reasons, imported by "
                    "the analysis module")
        return _proved("switches_route", observe, verdict,
                       lambda: patch.object(run_report_text, "FACT_CHECKER_REASONS", ()),
                       "the shared B.4 reasons emptied")


def check_report_route():
    if not _has_fastapi():
        return SKIP_FASTAPI
    with _served() as (client, headers, server, root):
        session = root / "session"

        def observe():
            plain = _get(client, headers, "/report")
            moved = session / "downloaded" / "evidence"
            _make_session(session, "exposed")
            moved.mkdir(parents=True, exist_ok=True)
            shutil.copytree(server.RUNS_DIR / RUN_ID, moved / RUN_ID, dirs_exist_ok=True)
            saved = server.RUNS_DIR
            server.RUNS_DIR = moved
            try:
                cloud = _get(client, headers, "/report")
            finally:
                server.RUNS_DIR = saved
                shutil.rmtree(session, ignore_errors=True)
            return {"anonymous": client.get("/runs/" + RUN_ID + "/report").status_code,
                    "plain": plain, "cloud": cloud}

        def verdict(o):
            plain = (o["plain"] or {}).get("body") or {}
            cloud = (o["cloud"] or {}).get("body") or {}
            cost = plain.get("cost") or {}
            ok = (o["anonymous"] == 401 and plain.get("source") == "run_folder"
                  and plain.get("note") == "no cloud report for this run" and plain.get("rows") == []
                  and cost.get("model_calls_with_a_cost_line") == 3 and cost.get("model_api_usd") == 0
                  and cost.get("infrastructure_usd") is None and plain.get("purpose") == console_views.NOT_KNOWN
                  and plain.get("budget", {}).get("hard_usd") == console_views.NOT_KNOWN
                  and cloud.get("source") == "final_status"
                  and [r["label"] for r in cloud.get("rows") or []] == list(_final_status_rows())
                  and cloud.get("purpose") == "console fixture"
                  and cloud.get("budget") == {"soft_usd": 2.0, "hard_usd": 3.0, "within_hard_ceiling": True}
                  and cloud.get("cost", {}).get("combined_usd") == 0.1234)
            return ("PASS" if ok else "FAIL",
                    "GET /runs/{run_id}/report: 401 without a token; a local run reads its own cost lines and "
                    "says no cloud report and not known; a cloud layout three levels up gives the 11.12 rows, "
                    "cost and budget")
        return _proved("report_route", observe, verdict,
                       lambda: patch.object(console_views, "_found", lambda run_dir, name: (None, None)),
                       "the report file walk returns nothing")


def check_test_change_requests_route():
    if not _has_fastapi():
        return SKIP_FASTAPI
    source = (ROOT / console_views.TEST_CHANGE_REQUESTS).read_text(encoding="utf-8")
    headings = sum(1 for line in source.splitlines() if line.startswith("### TCR-"))
    with _served() as (client, headers, _server, root):
        def observe():
            present = client.get("/test-change-requests", headers=headers).json()
            target = root / TCR_PATH
            held = target.read_bytes()
            target.unlink()
            absent = client.get("/test-change-requests", headers=headers).json()
            target.write_bytes(held)
            return {"anonymous": client.get("/test-change-requests").status_code,
                    "present": present, "absent": absent}

        def verdict(o):
            entries = o["present"].get("entries") or []
            ok = (o["anonymous"] == 401 and o["present"].get("present") is True
                  and o["present"].get("count") == headings == len(entries) and headings > 0
                  and all(e["id"].startswith("TCR-") and "Decision" in e["fields"] and "Proposal" in e["fields"]
                          for e in entries)
                  and o["absent"] == {"present": False, "message": console_views.NOT_PRESENT,
                                      "count": 0, "entries": []})
            return ("PASS" if ok else "FAIL",
                    "GET /test-change-requests: 401 without a token; every TCR entry of docs/test_change_requests.md "
                    "as a row with its fields; 'not present in this installation' when the file is absent")
        return _proved("test_change_requests_route", observe, verdict,
                       lambda: patch.object(console_views, "TEST_CHANGE_REQUESTS", Path("docs") / "absent.md"),
                       "the route reads another file")


def check_multi_round_reuse_route():
    if not _has_fastapi():
        return SKIP_FASTAPI
    with _served() as (client, headers, _server, _root):
        def observe():
            return {"anonymous": client.get("/runs/" + RUN_ID + "/multi-round").status_code,
                    "authorised": _get(client, headers, "/multi-round")}

        def verdict(o):
            body = (o["authorised"] or {}).get("body") or {}
            reuse = body.get("round_reuse") or {}
            units = [u for r in reuse.get("rounds") or [] for d in r.get("documents") or [] for u in d.get("units") or []]
            ok = (o["anonymous"] == 401 and "activation" in body and reuse.get("availability") == "recorded"
                  and reuse.get("units_reused") == 1 and reuse.get("units_computed") == 3
                  and [u["status"] for u in units] == ["computed", "computed", "reused", "computed"]
                  and units[2]["reused_from"] == {"round_id": "r1", "document_id": "ledger_round_1",
                                                  "unit_id": "u01-zone-alpha"}
                  and units[1]["needs_model"] == 1 and reuse.get("case_id") == "fixture-case")
            return ("PASS" if ok else "FAIL",
                    "GET /runs/{run_id}/multi-round keeps the case record and gains audit/round_reuse.json as a "
                    "rounds table: units reused and recomputed, where each reused unit came from")
        return _proved("multi_round_reuse_route", observe, verdict,
                       lambda: patch.object(console_views, "round_reuse", lambda run_dir: {"availability": "not_recorded"}),
                       "the reuse reader answers not recorded")


# ---------------------------------------------------------------------------
# The sealed filter (item 2)
# ---------------------------------------------------------------------------
PER_FLAW_GETS = ("/findings", "/pairs", "/amendments", "/amendment-refusals", "/contract-violations",
                 "/references", "/deliverables", "/deliverables/" + DOC, "/log",
                 # S7 close (adversarial 1): document names and rule ids, refused too.
                 "/undated-documents", "/convention-assignment")
# /activation since the S7 close (adversarial 1): the fixture's PRACTICE_AUDITOR
# decision carries a unit id and a rule id in its evidence, as the pipeline's do.
NEW_VIEWS = ("/replies", "/model-findings", "/switches", "/report", "/multi-round", "/activation")
# A pending governed question written into the sealed run, its payload naming a
# unit and a rule: GET /approvals keeps its timings only.
PENDING_APPROVAL = {"topic": "amendment_review", "asked_at": "2026-10-29T09:20:00+00:00",
                    "payload": {"message": "u03-zone-beta under CONV-002: rate looks higher",
                                "unit_id": "u03-zone-beta", "rule_id": "CONV-002"}}


def _write_pending_approval(run_dir):
    (Path(run_dir) / "audit" / "pending_approval.json").write_text(json.dumps(PENDING_APPROVAL), encoding="utf-8")


def _sealed_observation(client, headers):
    out = {path: _get(client, headers, path) for path in NEW_VIEWS}
    out["per_flaw"] = {path: client.get("/runs/" + RUN_ID + path, headers=headers).status_code
                       for path in PER_FLAW_GETS}
    out["evidence"] = client.post("/runs/" + RUN_ID + "/evidence", headers=headers,
                                  json={"expected": [{"unit": "u03-zone-beta", "rule": "CONV-002"}]}).status_code
    approvals = client.get("/approvals", headers=headers)
    out["approvals"] = approvals.json() if approvals.status_code == 200 else {"status": approvals.status_code}
    # The run record and the run list (S7 close): a sealed run's documents as counts only.
    record = client.get("/runs/" + RUN_ID, headers=headers)
    out["run"] = record.json() if record.status_code == 200 else {"status": record.status_code}
    listing = client.get("/runs", headers=headers)
    out["runs"] = [r for r in (listing.json().get("runs") or [] if listing.status_code == 200 else [])
                   if r.get("run_id") == RUN_ID]
    return out


def _sealed_verdict(o):
    text = json.dumps({k: o[k] for k in NEW_VIEWS + ("approvals", "run", "runs")})
    # The document's own id names sealed material on the run record and the run list.
    leaks = [w for w in SEALED_FORBIDDEN + REPLY_SECRETS if w in text]
    leaks += [DOC] if DOC in json.dumps({k: o[k] for k in ("run", "runs")}) else []
    run_records = [o["run"]] + list(o["runs"])
    bodies = [(o[k] or {}).get("body") or {} for k in NEW_VIEWS]
    rows = [r["label"] for r in (o["/report"]["body"] or {}).get("rows") or []]
    activation = (o["/activation"] or {}).get("body") or {}
    pending = [a for a in (o["approvals"] or {}).get("approvals") or [] if a.get("run_id") == RUN_ID]
    ok = (not leaks and all(b.get("exposure") == "sealed" for b in bodies)
          and activation.get("decisions") == [] and len(activation.get("agent_states") or []) == 4
          and (activation.get("decision_counts") or {}).get("dispatch_attempts") == 3
          and (activation.get("decision_counts") or {}).get("non_calls") == 1
          and len(run_records) == 2
          and all(r.get("documents") == [] and r.get("document_count") == 1 and r.get("files") == []
                  and r.get("file_count") == 1 and r.get("exposure") == "sealed" for r in run_records)
          and len(pending) == 1 and pending[0].get("asked_at") == PENDING_APPROVAL["asked_at"]
          and pending[0].get("payload") == {} and pending[0].get("topic") is None
          and all(o[k]["status"] == 200 for k in NEW_VIEWS)
          and (o["/replies"]["body"] or {}).get("count") == 3 and "calls" not in (o["/replies"]["body"] or {})
          and (o["/model-findings"]["body"] or {}).get("count") == 1
          and "documents" not in (o["/model-findings"]["body"] or {})
          and set(rows) <= set(run_report_text.SEALED_REPORT_ROWS) and "Purpose" in rows
          and (o["/multi-round"]["body"] or {}).get("round_reuse", {}).get("units_reused") == 1
          and set(o["/multi-round"]["body"] or {}) <= {"recorded", "availability", "outcome", "exposure",
                                                       "round_reuse"}
          and all(code == 403 for code in o["per_flaw"].values()) and o["evidence"] == 403)
    return ("PASS" if ok else "FAIL", "leaks=%s" % leaks)


def check_sealed_filter():
    """Both layouts of closure 2: a marker in the run folder itself, and the cloud
    layout with seal.json three levels up; plus an unreadable marker (sealed) and a
    seal.json that says exposed (exposed)."""
    if not _has_fastapi():
        return SKIP_FASTAPI
    results = {}
    layouts = {
        "run_folder_marker": lambda root: root / "runs",
        "cloud_session": lambda root: root / "session" / "downloaded" / "evidence",
    }
    for name, runs in layouts.items():
        with _served(runs_dir=runs) as (client, headers, server, root):
            run_dir = server.RUNS_DIR / RUN_ID
            if name == "run_folder_marker":
                (run_dir / "run_record.json").write_text(json.dumps({"exposure": "sealed"}), encoding="utf-8")
                (run_dir / "FINAL_STATUS.json").write_text(json.dumps({"report": _final_status_rows()}), encoding="utf-8")
            else:
                _make_session(root / "session", "sealed")
                (root / "session" / "run_record.json").unlink()
            _write_pending_approval(run_dir)
            observe = lambda: _sealed_observation(client, headers)  # noqa: E731
            status, results[name] = _proved("sealed_filter_" + name, observe, _sealed_verdict,
                                            lambda: patch.object(console_views, "exposure", lambda run_dir: "exposed"),
                                            "exposure always read as exposed")
            if status != "PASS":
                return ("FAIL", "%s: %s" % (name, results[name]))
            if name == "run_folder_marker":
                # Each reduction on its own (S7 close, adversarial 1): the activation
                # decisions and the pending question passed through unreduced.
                unreduced = {"sealed_activation": lambda record: dict(record, exposure="sealed"),
                             "sealed_approval": lambda record: dict(record, exposure="sealed"),
                             "sealed_run_record": lambda record: dict(record, exposure="sealed")}
                for reducer in ("sealed_activation", "sealed_approval", "sealed_run_record"):
                    status, detail = _proved(
                        "sealed_filter_" + reducer, observe, _sealed_verdict,
                        lambda reducer=reducer: patch.object(console_views, reducer, unreduced[reducer]),
                        "console_views.%s returns its input" % reducer)
                    if status != "PASS":
                        return ("FAIL", "%s: %s" % (reducer, detail))
                    results[reducer] = detail[detail.index("neutralised ("):]
            if name == "cloud_session":
                seal = root / "session" / "seal.json"
                seal.write_text("{", encoding="utf-8")
                unreadable = console_views.exposure(run_dir)
                seal.write_text(json.dumps({"exposure": "exposed"}), encoding="utf-8")
                exposed = console_views.exposure(run_dir)
                seal.write_text(json.dumps({"purpose": "no exposure field"}), encoding="utf-8")
                silent = console_views.exposure(run_dir)
                if (unreadable, exposed, silent) != ("sealed", "exposed", "sealed"):
                    return ("FAIL", "marker edge cases read %s" % ((unreadable, exposed, silent),))
                # The /evidence refusal on its own: the route-level guard neutralised.
                seal.write_text(json.dumps({"exposure": "sealed"}), encoding="utf-8")

                def observe_evidence():
                    return client.post("/runs/" + RUN_ID + "/evidence", headers=headers,
                                       json={"expected": [{"unit": "u03-zone-beta", "rule": "CONV-002"}]}).status_code

                try:
                    prove_effect(name="evidence_refuses_sealed", validate=lambda: True, observe=observe_evidence,
                                 check=lambda: ("PASS" if observe_evidence() == 403 else "FAIL", "evidence"),
                                 neutralise=lambda: patch.object(server, "_refuse_sealed", lambda run_dir: None))
                except ProofFailure as exc:
                    return ("FAIL", "POST /evidence on a sealed run: %s" % exc.category)
    return ("PASS", "a sealed run (marker in the run folder; seal.json three levels up in the cloud layout; "
                    "an unreadable or silent seal.json) shows counts and timings only on every new route and "
                    "on /activation (decisions as counts, no evidence), GET /approvals keeps a pending "
                    "question's timings only, GET /runs/{run_id} and GET /runs carry the run's document "
                    "and file counts and no document or file name, the report keeps only the allowlisted rows, per-flaw routes "
                    "(with /undated-documents and /convention-assignment) and POST /evidence answer 403; "
                    "neutralised (exposure read as exposed; the activation, approval and run-record "
                    "reductions each returning their input; the /evidence guard removed): FAIL; "
                    "restored: PASS. "
                    + " | ".join("%s: %s" % kv for kv in results.items()))


# ---------------------------------------------------------------------------
# Every route needs a token except exactly /health and /console (DS7-5)
# ---------------------------------------------------------------------------
_PARAMS = {"run_id": RUN_ID, "doc_id": DOC, "provision_id:path": "fixture", "provision_id": "fixture",
           "conflict_id": "fixture", "rule_id": "CONV-001"}


def _answers_without_a_token(client, app):
    import re
    open_paths, seen = set(), []
    for route in app.routes:
        methods = sorted(set(getattr(route, "methods", None) or ()) - {"HEAD", "OPTIONS"})
        path = getattr(route, "path", None)
        if not path or not methods:
            continue
        url = re.sub(r"\{([^}]+)\}", lambda m: _PARAMS.get(m.group(1), "fixture"), path)
        for method in methods:
            kwargs = {"json": {}} if method in ("POST", "PUT", "PATCH") else {}
            status = client.request(method, url, **kwargs).status_code
            seen.append((method, path, status))
            if status != 401:
                open_paths.add(path)
    docs = {path: client.get(path).status_code for path in FASTAPI_DOCS}
    return {"open": sorted(open_paths), "routes": len(seen), "docs": docs}


def check_all_routes_need_a_token():
    if not _has_fastapi():
        return SKIP_FASTAPI
    with _served() as (client, _headers, server, _root):
        def observe():
            return _answers_without_a_token(client, server.app)

        def verdict(o):
            ok = (set(o["open"]) == EXEMPT and o["routes"] >= 30
                  and all(code == 404 for code in o["docs"].values()))
            return ("PASS" if ok else "FAIL",
                    "every one of %d registered method-and-route pairs answers 401 without a token except "
                    "exactly %s; FastAPI's %s answer 404" % (o["routes"], sorted(EXEMPT), ", ".join(FASTAPI_DOCS)))

        @contextlib.contextmanager
        def ungated_route():
            saved = list(server.app.router.routes)
            server.app.add_api_route("/zq-ungated-probe", lambda: {"open": True}, methods=["GET"])
            try:
                yield
            finally:
                server.app.router.routes[:] = saved

        @contextlib.contextmanager
        def docs_switched_on():
            # FastAPI's defaults, as server.py had them before the three were set to None.
            app = server.app
            saved_routes = list(app.router.routes)
            saved = (app.openapi_url, app.docs_url, app.redoc_url, app.openapi_schema)
            app.openapi_url, app.docs_url, app.redoc_url = "/openapi.json", "/docs", "/redoc"
            app.setup()
            try:
                yield
            finally:
                app.router.routes[:] = saved_routes
                app.openapi_url, app.docs_url, app.redoc_url, app.openapi_schema = saved

        route = _proved("all_routes_need_a_token", observe, verdict, ungated_route,
                        "an ungated route added to the live app")
        if route[0] != "PASS":
            return route
        docs = _proved("fastapi_docs_need_a_token", observe, verdict, docs_switched_on,
                       "FastAPI's own /openapi.json, /docs and /redoc switched back on")
        if docs[0] != "PASS":
            return docs
        return ("PASS", route[1] + "; " + docs[1][docs[1].index("neutralised ("):])


# ---------------------------------------------------------------------------
# The views: console.html's own functions, run in Node on the projections
# ---------------------------------------------------------------------------
_HARNESS = r"""
const fs=require('fs'),vm=require('vm'),path=require('path');
const [htmlPath,uiDir,inputPath]=process.argv.slice(2);
const html=fs.readFileSync(htmlPath,'utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const parser={exports:{},module:{}};
vm.runInNewContext(process.binding('natives')['internal/deps/acorn/acorn/dist/acorn'],parser);
const body=parser.exports.parse(script,{ecmaVersion:2022}).body[0].expression.callee.body.body;
const context={sessionStorage:{getItem:()=>null,setItem(){}},console};
vm.createContext(context);
for(const f of ['localization_catalog.js','localization.js'])vm.runInContext(fs.readFileSync(path.join(uiDir,f),'utf8'),context);
context.ui=context.ShimmerLocale.text;context.displayValue=context.ShimmerLocale.value;
const wanted=new Set(['REPLY_OUTCOME_LABELS','TCR_FIELD_LABELS','SEALED_NOTE_TEXT']);
for(const n of body){
  if(n.type==='FunctionDeclaration'||(n.type==='VariableDeclaration'&&n.declarations.some(d=>wanted.has(d.id.name))))
    vm.runInContext(script.slice(n.start,n.end),context);
}
const cases=JSON.parse(fs.readFileSync(inputPath,'utf8'));
const out=cases.map(c=>{context.ShimmerLocale.select(c.lang);return context[c.fn](c.data);});
process.stdout.write(JSON.stringify(out));
"""

VIEW_FUNCTIONS = ("repliesHtml", "modelFindingsHtml", "switchesHtml", "reportHtml", "roundReuseHtml",
                  "testChangesHtml", "activationSummaryHtml", "multiRoundHtml")
# Views whose sealed note is shown by the section beside them, not by the view
# itself: the multi-round heading sits above roundReuseHtml in one holder.
NOTE_SHOWN_BESIDE = ("multiRoundHtml",)
# A sealed run whose case WAS recorded, as /multi-round sends it (S7 close,
# adversarial 4): the fixture records no case master, so the view case is built
# from console_views.sealed_multi_round over a recorded case's own fields.
RECORDED_CASE = {"recorded": True, "availability": "recorded", "outcome": "reviewed", "fixture": False,
                 "run_id": RUN_ID, "activation": {"state": "activated", "reason": "operator_requested"},
                 "view": {"case_id": "fixture-case", "evidence": []}}
# English section labels a Turkish view must not show.
ENGLISH_LABELS = ("Model replies", "Written by a model", "Agent switches", "Run report", "Rounds",
                  "Test change requests", "Every saved call", "Why it is withheld", "Model API cost",
                  "not known", "switched on for this run", "Units reused from an earlier round")


def _projections(runs_dir, sealed):
    """What each route sends, built as the server builds it: the sealed reductions
    are applied when console_views.exposure reads the run as sealed, so a
    neutralised exposure reader renders a sealed run as exposed."""
    run_dir = Path(runs_dir) / RUN_ID
    if sealed:
        (run_dir / "run_record.json").write_text(json.dumps({"exposure": "sealed"}), encoding="utf-8")
    state = console_views.exposure(run_dir)
    from multi_round import read_saved
    from routing_view import read_activation
    multi, recorded, activation = read_saved(run_dir, RUN_ID), dict(RECORDED_CASE), read_activation(run_dir, RUN_ID)
    if state == console_views.SEALED:
        multi, recorded = console_views.sealed_multi_round(multi), console_views.sealed_multi_round(recorded)
        activation = console_views.sealed_activation(activation)
    else:
        activation = dict(activation, exposure=state)
    reuse = console_views.round_reuse(run_dir)
    multi = dict(multi, exposure=state, round_reuse=reuse)
    from honest_output_checks import server_findings
    return {"repliesHtml": console_views.replies(run_dir),
            "modelFindingsHtml": console_views.model_findings(run_dir, bus_findings=server_findings(run_dir)),
            "switchesHtml": console_views.switches(run_dir, RUN_ID, ROOT),
            "reportHtml": console_views.report(run_dir),
            "roundReuseHtml": multi,
            "testChangesHtml": console_views.test_change_requests(ROOT),
            "activationSummaryHtml": activation,
            "multiRoundHtml": multi,
            "multiRoundHtml:recorded": dict(recorded, exposure=state, round_reuse=reuse)}


def _render(html_path, cases):
    with tempfile.TemporaryDirectory(prefix="shimmer_console_view_js_") as tmp:
        harness = Path(tmp) / "harness.js"
        harness.write_text(_HARNESS, encoding="utf-8")
        data = Path(tmp) / "cases.json"
        data.write_text(json.dumps(cases), encoding="utf-8")
        result = subprocess.run(["node", str(harness), str(html_path), str(ROOT / "scripts" / "ui"), str(data)],
                                capture_output=True, text=True, encoding="utf-8", timeout=60,
                                creationflags=NO_WINDOW)
        if result.returncode != 0:
            raise RuntimeError("view harness failed: " + result.stderr.strip().splitlines()[-1:][0]
                               if result.stderr.strip() else "view harness failed")
        return json.loads(result.stdout)


def _views_observation(html_path):
    with tempfile.TemporaryDirectory(prefix="shimmer_console_views_js_") as tmp:
        cases, keys = [], []
        for sealed in (False, True):
            runs = Path(tmp) / ("sealed" if sealed else "exposed")
            _copy_fixture(runs)
            projections = _projections(runs, sealed)
            for lang in ("en", "tr"):
                for fn in VIEW_FUNCTIONS + (("multiRoundHtml:recorded",) if sealed else ()):
                    cases.append({"fn": fn.split(":")[0], "lang": lang, "data": projections[fn]})
                    keys.append("%s/%s/%s" % ("sealed" if sealed else "exposed", lang, fn))
        rendered = _render(html_path, cases)
    # The replies are written afresh for every observation under the fixed fixture
    # clock (REPLY_TIMES), so two observations of the same code are identical.
    return dict(zip(keys, rendered))


def _views_verdict(views):
    import localization
    mark_en = MARK
    mark_tr = localization.text(mark_en, "tr")
    failures = []
    for key, html in views.items():
        state, lang, fn = key.split("/")
        if any(s in html for s in REPLY_SECRETS):
            failures.append(key + ": reply text shown")
        if state == "sealed" and fn != "testChangesHtml":  # not run-scoped
            if "sealed-note" not in html and fn.split(":")[0] not in NOTE_SHOWN_BESIDE:
                failures.append(key + ": no sealed note")
            leaked = [w for w in SEALED_FORBIDDEN if w in html]
            if leaked:
                failures.append(key + ": sealed view shows " + ", ".join(leaked))
        if lang == "tr":
            english = [w for w in ENGLISH_LABELS if w in html]
            if english:
                failures.append(key + ": English label in the Turkish view: " + ", ".join(english))
    for lang, mark in (("en", mark_en), ("tr", mark_tr)):
        html = views["exposed/%s/modelFindingsHtml" % lang]
        if html.count('class="model-finding"') != 1 or html.count(mark) != 1:
            failures.append(lang + ": the model finding is not shown with its mark")
        elif html.find(mark) > html.find("u03-zone-beta"):
            failures.append(lang + ": the mark does not come before the finding")
    exposed = views["exposed/en/repliesHtml"]
    if "3 model calls were saved" not in exposed or "not promoted: 1" not in exposed:
        failures.append("replies view: counts by outcome missing")
    # At phone width the calls table stacks each row into labelled lines, so every
    # cell carries its column's label (7 columns, 3 calls).
    if 's7-stack' not in exposed or exposed.count(' data-label="') != 21:
        failures.append("replies view: the calls table does not label every cell for the phone layout")
    if views["exposed/en/switchesHtml"].count("<li>") != 2:
        failures.append("switches view: the two B.4 reasons are not listed")
    # DS7-8: the B.4 reasons are standing agent policy, shown on a sealed run too,
    # under a note that names precisely what is withheld (one text, both languages).
    import html as html_module
    if views["sealed/en/switchesHtml"].count("<li>") != 2:
        failures.append("sealed switches view: the two B.4 reasons are not listed")
    note_tr = localization.text(run_report_text.SEALED_NOTE, "tr")
    if note_tr == run_report_text.SEALED_NOTE:
        failures.append("the sealed note has no Turkish row")
    for lang, note in (("en", run_report_text.SEALED_NOTE), ("tr", note_tr)):
        shown = html_module.unescape(views["sealed/%s/switchesHtml" % lang])
        if note not in shown:
            failures.append(lang + ": the sealed note is not the shared SEALED_NOTE text")
    if "the reasons given for findings" not in run_report_text.SEALED_NOTE:
        failures.append("the sealed note does not name the findings' reasons as what is withheld")
    page = (ROOT / "scripts" / "ui" / "console.html").read_text(encoding="utf-8")
    if "var SEALED_NOTE_TEXT = %s;" % json.dumps(run_report_text.SEALED_NOTE) not in page:
        failures.append("console.html's fallback sealed note differs from run_report_text.SEALED_NOTE")
    if "TCR-001" not in views["exposed/en/testChangesHtml"]:
        failures.append("test change requests page: no entry")
    if "u01-zone-alpha" not in views["exposed/en/roundReuseHtml"]:
        failures.append("rounds view: no unit rows")
    # S7 close, adversarial 1: the exposed activation view shows each decision in
    # Developer view, the sealed one its counts only (the leak scan above).
    if "u03-zone-beta" not in views["exposed/en/activationSummaryHtml"]:
        failures.append("activation view: the exposed decisions are not shown")
    if "3 dispatch attempts" not in views["sealed/en/activationSummaryHtml"]:
        failures.append("sealed activation view: the decision counts are not shown")
    # S7 close, adversarial 4: a recorded sealed case says so, never "no valid output".
    for lang in ("en", "tr"):
        shown = views["sealed/%s/multiRoundHtml:recorded" % lang]
        if (localization.text("No valid recorded case output.", lang) in shown
                or localization.text("A case output was recorded. Outcome: ", lang) not in shown):
            failures.append(lang + ": a recorded sealed case is not shown as recorded")
    return ("FAIL" if failures else "PASS",
            "; ".join(failures) or "the eight views render the projections in English and Turkish; the model "
            "finding shows the mark first in both languages; a sealed view shows its note and no id, rule, "
            "finding reason or text (the activation view its decision counts only); a recorded sealed case "
            "is shown as recorded; the sealed switches view keeps the two B.4 reasons under the shared note "
            "(DS7-8) in both languages; no reply text anywhere; every new label has a Turkish row")


# The files that start the console's and the chat window's children (S7 close,
# adversarial 5): every start passes the no-window flag as its creationflags (HIDDEN-A).
HIDDEN_START_FILES = ("scripts/console_view_checks.py", "scripts/chat.py", "scripts/launcher_checks.py",
                      "tools/console_screenshots.py")
# What the scan counts as a start (S7 round 2, adversarial 2): subprocess's starters called on
# the module, on an alias of it or through a name imported from it, asyncio's two, and os's own
# starters, which take no creationflags and so are never hidden.
_START_NAMES = {"run", "Popen", "call", "check_call", "check_output", "getoutput", "getstatusoutput"}
_FLAGLESS_STARTS = {"getoutput", "getstatusoutput"}
_ASYNCIO_STARTS = {"create_subprocess_exec", "create_subprocess_shell"}
_OS_STARTS = {"system", "popen", "startfile", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve",
              "spawnvp", "spawnvpe", "posix_spawn", "posix_spawnp"}
WINDOWS_NO_WINDOW = 0x08000000
_FLAG_NAMES = {("subprocess", "CREATE_NO_WINDOW"), ("cloud_run_common", "CREATE_NO_WINDOW")}


def _start_scan(source):
    """(start lines, [(line, reason)]) for one source: every child-process start, and each one
    whose creationflags is not provably the no-window flag. Provably means, and only means, the
    forms the scanned files write: CREATE_NO_WINDOW or a constant holding 0x08000000, getattr
    (subprocess, "CREATE_NO_WINDOW", 0), `<flag> if os.name == "nt" else 0`, an OR with the
    flag, a name bound once in the module to one of those, or cloud_run_common.no_window()
    without keep_console."""
    import ast
    tree = ast.parse(source)
    modules = {"subprocess": set(), "os": set(), "asyncio": set(), "cloud_run_common": set()}
    imported = {}
    stores = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in modules:
                    modules[alias.name].add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module in modules:
            for alias in node.names:
                imported[alias.asname or alias.name] = (node.module, alias.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stores[node.id] = stores.get(node.id, 0) + 1
        elif isinstance(node, ast.arg):
            stores[node.arg] = stores.get(node.arg, 0) + 1

    def named(expr):
        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
            for module, aliases in modules.items():
                if expr.value.id in aliases:
                    return module, expr.attr
        if isinstance(expr, ast.Name):
            return imported.get(expr.id)
        return None

    def is_start(target):
        return target is not None and ((target[0] == "subprocess" and target[1] in _START_NAMES)
                                       or (target[0] == "asyncio" and target[1] in _ASYNCIO_STARTS)
                                       or (target[0] == "os" and target[1] in _OS_STARTS))

    bindings = {node.targets[0].id: node.value for node in tree.body
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}

    def hidden(expr, seen=()):
        if isinstance(expr, ast.Constant):
            return type(expr.value) is int and bool(expr.value & WINDOWS_NO_WINDOW)
        if isinstance(expr, (ast.Attribute, ast.Name)) and named(expr) in _FLAG_NAMES:
            return True
        if isinstance(expr, ast.Name):
            return (expr.id not in seen and stores.get(expr.id) == 1 and expr.id in bindings
                    and hidden(bindings[expr.id], seen + (expr.id,)))
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.BitOr):
            return hidden(expr.left, seen) or hidden(expr.right, seen)
        if isinstance(expr, ast.IfExp):
            windows_test = (isinstance(expr.test, ast.Compare) and named(expr.test.left) == ("os", "name")
                            and len(expr.test.ops) == 1 and isinstance(expr.test.ops[0], ast.Eq)
                            and isinstance(expr.test.comparators[0], ast.Constant)
                            and expr.test.comparators[0].value == "nt")
            off_windows = isinstance(expr.orelse, ast.Constant) and expr.orelse.value == 0
            return hidden(expr.body, seen) and (hidden(expr.orelse, seen) or (windows_test and off_windows))
        if isinstance(expr, ast.Call):
            if (isinstance(expr.func, ast.Name) and expr.func.id == "getattr" and len(expr.args) == 3
                    and not expr.keywords and isinstance(expr.args[0], ast.Name)
                    and expr.args[0].id in modules["subprocess"] and isinstance(expr.args[1], ast.Constant) and expr.args[1].value == "CREATE_NO_WINDOW"
                    and isinstance(expr.args[2], ast.Constant) and expr.args[2].value == 0):
                return True
            if named(expr.func) == ("cloud_run_common", "no_window"):
                return all(k.arg is not None and (k.arg != "keep_console"
                                                  or (isinstance(k.value, ast.Constant) and k.value.value is False))
                           for k in expr.keywords) and len(expr.args) <= 1
        return False

    starts, unhidden, called = [], [], set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_start(named(node.func)):
            target = named(node.func)
            called.add(id(node.func))
            starts.append(node.lineno)
            flags = [k for k in node.keywords if k.arg == "creationflags"]
            if target[0] == "os" or target[1] in _FLAGLESS_STARTS:
                unhidden.append((node.lineno, "%s.%s takes no creationflags" % target))
            elif not flags:
                unhidden.append((node.lineno, "no creationflags"))
            elif not hidden(flags[0].value):
                unhidden.append((node.lineno, "creationflags is not the no-window flag"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Attribute, ast.Name)) and id(node) not in called and is_start(named(node)):
            unhidden.append((node.lineno, "%s.%s referenced, not called, so its start is not seen" % named(node)))
    return starts, unhidden


def _unflagged_starts(sources):
    """(number of starts, ["file:line (reason)"]) over `sources`."""
    count, found = 0, []
    for name, source in sorted(sources.items()):
        starts, unhidden = _start_scan(source)
        count += len(starts)
        found.extend("%s:%d (%s)" % (name, line, reason) for line, reason in sorted(unhidden))
    return count, found


# Each neutralisation changes ONE real source in memory, never on disk: (what, file, needle,
# replacement, appended). The scan must FAIL naming that file, and then pass on the originals.
_HIDDEN_NEUTRALISATIONS = (
    ("the chat window's flag dropped", "scripts/chat.py",
     "bufsize=1,\n                creationflags=NO_WINDOW)", "bufsize=1)", ""),
    ("the chat window's flag set to 0", "scripts/chat.py",
     "creationflags=NO_WINDOW)", "creationflags=0)", ""),
    ("the launcher checks' NO_WINDOW bound to 0", "scripts/launcher_checks.py",
     'NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0', "NO_WINDOW = 0", ""),
    ("the screenshot server's no_window() given keep_console", "tools/console_screenshots.py",
     "creationflags=no_window())", "creationflags=no_window(keep_console=True))", ""),
    ("a start through a name imported from subprocess", "scripts/console_view_checks.py", None, None,
     '\nfrom subprocess import Popen as _Started\n_Started(["x"])\n'),
    ("an os.system start", "scripts/console_view_checks.py", None, None, '\nos.system("x")\n'),
    ("an asyncio start with no flag", "scripts/console_view_checks.py", None, None,
     '\nimport asyncio\nasyncio.create_subprocess_exec("x")\n'),
)


def _children_hidden():
    import sys
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import cloud_run_common
    # The helper the screenshot server's start calls is accepted only because it ORs in the flag:
    # executed here, as on Windows.
    with patch.object(cloud_run_common, "windows", lambda: True):
        if not (cloud_run_common.no_window() & WINDOWS_NO_WINDOW and cloud_run_common.no_window(4) & 4
                and not cloud_run_common.no_window(keep_console=True) & WINDOWS_NO_WINDOW):
            return ("FAIL", "cloud_run_common.no_window does not OR in 0x08000000 on Windows")
    sources = {name: (ROOT / name).read_text(encoding="utf-8") for name in HIDDEN_START_FILES}
    for what, name, needle, replacement, appended in _HIDDEN_NEUTRALISATIONS:
        changed = dict(sources)
        if needle is not None:
            if changed[name].count(needle) != 1:
                return ("FAIL", "%s: the start moved, so the neutralisation cannot be applied" % what)
            changed[name] = changed[name].replace(needle, replacement)
        changed[name] += appended
        found = _unflagged_starts(changed)[1]
        if not found:
            return ("FAIL", "neutralised (%s) and the scan still passes" % what)
        if any(not entry.startswith(name + ":") for entry in found):
            return ("FAIL", "neutralised (%s): the scan names another file: %s" % (what, found))
    count, found = _unflagged_starts(sources)
    if found:
        return ("FAIL", "child processes started without the no-window flag: %s" % found)
    return ("PASS", "every child-process start in %s (%d found; the scan counts subprocess's starters called on "
                    "the module, an alias or an imported name, asyncio's two and os's own, which are never hidden) "
                    "passes creationflags provably the no-window flag (CREATE_NO_WINDOW, a name bound once to it, "
                    "or cloud_run_common.no_window(), executed: it ORs in 0x08000000 on Windows); neutralised in "
                    "memory (%s): each FAIL naming the changed file; originals: PASS"
            % (", ".join(HIDDEN_START_FILES), count, "; ".join(n[0] for n in _HIDDEN_NEUTRALISATIONS)))


def check_console_views():
    hidden = _children_hidden()
    if hidden[0] != "PASS":
        return hidden
    if shutil.which("node") is None:
        return ("SKIP", "node is not on PATH: the console view proof runs console.html's own functions in Node; "
                        + hidden[1])
    html_path = ROOT / "scripts" / "ui" / "console.html"
    state = {"path": html_path}

    def observe():
        return _views_observation(state["path"])

    @contextlib.contextmanager
    def replaced(needle, replacement, what):
        with tempfile.TemporaryDirectory(prefix="shimmer_console_unmarked_") as tmp:
            copy = Path(tmp) / "console.html"
            source = html_path.read_text(encoding="utf-8")
            if source.count(needle) != 1:
                raise RuntimeError(what + " moved")
            copy.write_text(source.replace(needle, replacement), encoding="utf-8")
            state["path"] = copy
            try:
                yield
            finally:
                state["path"] = html_path

    # S7 close, adversarial 6: the sealed note and the sealed rendering have their
    # own neutralisations beside the mark's.
    proofs = (
        (lambda: replaced("escapeHtml(ui(f.mark || data.mark))", '""', "the mark site"),
         "the mark removed from the view"),
        (lambda: replaced('if (!data || data.exposure !== "sealed") return "";', 'return "";', "the sealed note"),
         "sealedNoteHtml never shows the note"),
        (lambda: patch.object(console_views, "exposure", lambda run_dir: console_views.EXPOSED),
         "a sealed run's projections built as exposed"),
    )
    details = []
    for neutralise, what in proofs:
        status, detail = _proved("console_views", observe, _views_verdict, neutralise, what)
        if status != "PASS":
            return (status, detail)
        details.append(detail)
    return ("PASS", details[0] + "; " + "; ".join(d[d.index("neutralised ("):] for d in details[1:])
            + ". " + hidden[1])


CHECKS = (check_replies_route, check_model_findings_route, check_switches_route, check_report_route,
          check_test_change_requests_route, check_multi_round_reuse_route, check_sealed_filter,
          check_all_routes_need_a_token, check_console_views)


if __name__ == "__main__":
    for fn in CHECKS:
        print(fn.__name__, fn())
