#!/usr/bin/env python3
"""TEST HELPER, NOT PART OF THE PRODUCT. This script exists only so a person
can look at the console (scripts/ui/console.html) in a browser without a real
pipeline run, a real model call, or a real API key. It stubs the pipeline
subprocess entirely: no document is actually reviewed, nothing is sent to any
model. Nothing it does is part of Shimmer's real surface; it is not imported
by anything, not covered by the verify gate, and safe to delete at any time.

One command to start, one to stop:

    py -3.9 -X utf8 tools/console_preview.py
    (Ctrl+C in the same terminal to stop; all state is thrown away)

It starts a real server (scripts/server.py, unmodified) on 127.0.0.1:8731,
generates a fresh throwaway access token, seeds one run in each reachable
state, and prints the token and the URL to open. All run data is written
under a fresh temp directory (deleted automatically on a clean Ctrl+C).
"""
import atexit
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

RUNS_DIR = Path(tempfile.mkdtemp(prefix="shimmer_console_preview_"))
atexit.register(lambda: shutil.rmtree(RUNS_DIR, ignore_errors=True))

TOKEN = secrets.token_hex(16)
os.environ["SHIMMER_TOKEN_HASH"] = hashlib.sha256(TOKEN.encode()).hexdigest()
os.environ["SHIMMER_OUTPUT_DIR"] = str(RUNS_DIR)
os.environ["SHIMMER_PORT"] = "8731"
os.environ["SHIMMER_HOST"] = "127.0.0.1"
os.environ["SHIMMER_LOG_LEVEL"] = "warning"
os.environ["SHIMMER_APPROVAL_WAIT_S"] = "3600"


class _FakeProc:
    """Stands in for subprocess.Popen. Emits scripted [progress] lines, then
    exits 0 after a short run, so a run submitted through the console moves
    through queued -> running -> completed for real, with real timing,
    without spawning the actual pipeline or loading any model. terminate()/
    kill() genuinely stop the line stream (a threading.Event), the way a
    real killed subprocess would close its stdout, so cancellation is real."""

    def __init__(self, *a, **k):
        self.returncode = 0
        self._lines = [
            "[progress] event=start docs=2 status=running\n",
            "[progress] phase=1/9 status=running\n",
            "[progress] phase=3/9 status=running\n",
            "[progress] phase=5/9 status=running\n",
            "[progress] phase=5.5/9 doc=1/2 agent=PRACTICE_AUDITOR status=running\n",
        ]
        self._sent = 0
        self.stdout = self
        self._stopped = threading.Event()

    def __iter__(self):
        return self

    def __next__(self):
        if self._stopped.is_set():
            raise StopIteration
        if self._sent < len(self._lines):
            line = self._lines[self._sent]
            self._sent += 1
            self._stopped.wait(timeout=6)
            if self._stopped.is_set():
                raise StopIteration
            return line
        self._stopped.wait(timeout=2)
        raise StopIteration

    def wait(self, timeout=None):
        return self.returncode

    def terminate(self):
        self.returncode = -15
        self._stopped.set()

    def kill(self):
        self.returncode = -9
        self._stopped.set()


import server  # noqa: E402  (import BEFORE the Popen monkeypatch: asyncio's
# own windows_events module subclasses the real subprocess.Popen during
# FastAPI's import chain, so replacing it first breaks unrelated stdlib
# imports. Patch only after everything real has finished importing.)

subprocess.Popen = lambda *a, **k: _FakeProc(*a, **k)
server.subprocess.Popen = subprocess.Popen


# ---------------------------------------------------------------------------
# Fixture builders: hand-crafted run directories for states a single manual
# submission cannot reach in one sitting (governance stop, crash, timeout, a
# finished run with findings already on the bus). Each one matches the exact
# on-disk shape server.py itself reads: status.json (_STATUS_FIELDS), audit/,
# logs/, deliverables/. Run ids must satisfy server._RUN_ID_RE: YYYYMMDD_HHMMSS__
# plus 6 LOWERCASE HEX characters, or the route 404s.
# ---------------------------------------------------------------------------

def _write_status(run_dir, run_id, status, **extra):
    run_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "run_id": run_id, "status": status, "task": "review",
        "submitted_at": extra.pop("submitted_at", _now()),
        "started_at": extra.pop("started_at", _now()),
        "completed_at": extra.pop("completed_at", None),
        "exit_code": extra.pop("exit_code", None),
        "error": extra.pop("error", None),
        "progress": extra.pop("progress", None),
        "files": extra.pop("files", ["doc_a.md", "doc_b.md"]),
        "sensitive": extra.pop("sensitive", False),
        "review_mode": extra.pop("review_mode", "paired"),
        "question": extra.pop("question", None),
    }
    record.update(extra)
    (run_dir / "status.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


def _now(offset_minutes=0):
    return (datetime.now(timezone.utc) - timedelta(minutes=offset_minutes)).isoformat()


FIXTURES = []  # (label, run_id), filled in as each _build_* runs.


def _build_queued():
    run_id = "20260910_141600__1ab2c3"
    _write_status(RUNS_DIR / run_id, run_id, "queued",
                   submitted_at=_now(1), started_at=None, completed_at=None)
    FIXTURES.append(("queued", run_id))


def _build_running():
    run_id = "20260910_141500__51b057"
    run_dir = RUNS_DIR / run_id
    _write_status(
        run_dir, run_id, "running",
        submitted_at=_now(4), started_at=_now(3), completed_at=None,
        progress="phase=5.5/9 doc=1/2 agent=PRACTICE_AUDITOR status=running",
    )
    audit = run_dir / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    (audit / "pairing_map.json").write_text(json.dumps({
        "case_a": {
            "document_id": "case_a",
            "unit_count": 1, "rule_count": 1,
            "pair_count": 1, "rejected_count": 0, "undecided_count": 0,
            "unmatched_units": [], "missing_field_findings": [],
            "units": [
                {
                    "unit_id": "u01", "kind": "provision",
                    "paired": [{"rule_id": "CONV-001", "reason": "unit states a figure this rule checks"}],
                    "rejected": [], "undecided": [],
                    "prior_comparisons": {"hit_count": 0, "checks": [], "refused": []},
                },
            ],
        },
    }, indent=2), encoding="utf-8")
    FIXTURES.append(("running", run_id))


def _build_awaiting_approval():
    run_id = "20260910_130000__ab9901"
    run_dir = RUNS_DIR / run_id
    _write_status(
        run_dir, run_id, "running",
        submitted_at=_now(13), started_at=_now(12), completed_at=None,
        progress="phase=6/9 status=running",
    )
    audit = run_dir / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    (audit / "pending_approval.json").write_text(json.dumps({
        "topic": "model_gate",
        "asked_at": _now(2),
        "payload": {
            "message": "The verification agent found a figure that disagrees with the reference table by more than the configured tolerance. Approve continuing with the model's reading, or deny to stop the run here.",
            "unit_id": "u07",
            "rule_id": "CONV-014",
            "value_a": "42.5",
            "value_b": "38.0",
        },
    }, indent=2), encoding="utf-8")
    FIXTURES.append(("awaiting_approval", run_id))


def _build_governance_stop():
    run_id = "20260910_120000__90ba01"
    _write_status(
        RUNS_DIR / run_id, run_id, "stopped_model_approval",
        submitted_at=_now(31), started_at=_now(30), completed_at=_now(20), exit_code=3,
        error="the model gate stopped this run for operator approval",
    )
    FIXTURES.append(("governance stop (stopped_model_approval)", run_id))


def _build_governance_stop_redaction_gate():
    """A second governance stop, a DIFFERENT code than _build_governance_stop:
    proves the human-view sentence is looked up per code (GOVERNANCE_SENTENCES_HUMAN
    in console.html) rather than one fixed sentence reused for all four, which
    was the bug this fixture exists to demonstrate is fixed."""
    run_id = "20260910_121500__d4d9c1"
    _write_status(
        RUNS_DIR / run_id, run_id, "stopped_redaction_gate",
        submitted_at=_now(28), started_at=_now(27), completed_at=_now(19), exit_code=4,
        error="the redaction gate stopped this run before completion",
    )
    FIXTURES.append(("governance stop (stopped_redaction_gate)", run_id))


def _build_crashed():
    run_id = "20260910_120100__ca5501"
    _write_status(
        RUNS_DIR / run_id, run_id, "failed",
        submitted_at=_now(26), started_at=_now(25), completed_at=_now(18), exit_code=1,
        error="Traceback (most recent call last):\n  File \"scripts/pipeline.py\", line 512, in run\n    raise RuntimeError('synthetic crash for console preview')\nRuntimeError: synthetic crash for console preview",
    )
    FIXTURES.append(("crashed", run_id))


def _build_timed_out():
    run_id = "20260910_120200__7171e0"
    _write_status(
        RUNS_DIR / run_id, run_id, "failed",
        submitted_at=_now(91), started_at=_now(90), completed_at=_now(0), exit_code=None,
        error="run exceeded the configured timeout and was terminated",
    )
    FIXTURES.append(("timed out", run_id))


def _build_cancelled():
    run_id = "20260910_110402__29c005"
    _write_status(
        RUNS_DIR / run_id, run_id, "cancelled",
        submitted_at=_now(16), started_at=_now(15), completed_at=_now(14), exit_code=-15,
        error="cancelled by operator while running",
    )
    FIXTURES.append(("cancelled", run_id))


def _build_completed_with_findings():
    run_id = "20260910_140000__f19d01"
    run_dir = RUNS_DIR / run_id
    _write_status(run_dir, run_id, "completed",
                   submitted_at=_now(46), started_at=_now(45), completed_at=_now(2), exit_code=0)

    audit = run_dir / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    (audit / "pairing_map.json").write_text(json.dumps({
        "case_a": {
            "document_id": "case_a",
            "unit_count": 3, "rule_count": 2,
            "pair_count": 2, "rejected_count": 1, "undecided_count": 0,
            "unmatched_units": [],
            "missing_field_findings": [],
            "units": [
                {
                    "unit_id": "u01", "kind": "provision",
                    "paired": [{"rule_id": "CONV-001", "reason": "unit states a figure this rule checks"}],
                    "rejected": [],
                    "undecided": [],
                    "prior_comparisons": {"hit_count": 1, "checks": ["u01"], "refused": []},
                },
                {
                    "unit_id": "u02", "kind": "provision",
                    "paired": [{"rule_id": "CONV-003", "reason": "unit states a figure this rule checks"}],
                    "rejected": [],
                    "undecided": [],
                    "prior_comparisons": {"hit_count": 0, "checks": ["u02"], "refused": []},
                },
                {
                    "unit_id": "u03", "kind": "provision",
                    "paired": [],
                    "rejected": [{"rule_id": "CONV-001", "reason": "unit does not mention a figure this rule checks"}],
                    "undecided": [],
                    "prior_comparisons": {"hit_count": 0, "checks": [], "refused": []},
                },
            ],
        }
    }, indent=2), encoding="utf-8")

    logs = run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    bus_items = [
        {
            "item_id": "f001", "revision": 1,
            "rule_id": "CONV-001", "source_rule_id": "CONV-A02", "unit_id": "u01",
            "value_a": 120.0, "unit_a": "tonnes", "value_b": 100.0, "unit_b": "tonnes",
            "relation": "above_band", "record_verdict": "irregular",
            "source_refs": ["REF-0012"],
            "explanation": "The stated figure exceeds the reference table's upper bound for this category.",
        },
        {
            "item_id": "f002", "revision": 1,
            "rule_id": "CONV-003", "source_rule_id": "CONV-B01", "unit_id": "u02",
            "value_a": 50.0, "unit_a": "EUR", "value_b": 50.0, "unit_b": "EUR",
            "relation": "sum_mismatch", "record_verdict": "ok",
            "source_refs": ["REF-0031"],
            "explanation": "The two figures agree once currency is normalised, within the configured tolerance.",
        },
    ]
    bus_lines = [
        json.dumps({
            "sender": "PRACTICE_AUDITOR",
            "body": {"payload": {"agent": "PRACTICE_AUDITOR", "doc_id": "case_a", "items": [item]}},
        })
        for item in bus_items
    ]
    (logs / "agent_bus.jsonl").write_text("\n".join(bus_lines) + "\n", encoding="utf-8")
    (logs / "pipeline_stdout.log").write_text(
        "[progress] event=start docs=1 status=running\n"
        "[progress] phase=1/9 status=running\n"
        "...\n"
        "[progress] phase=9/9 status=running\n"
        "run completed successfully\n",
        encoding="utf-8",
    )

    deliv = run_dir / "deliverables" / "case_a"
    deliv.mkdir(parents=True, exist_ok=True)
    (deliv / "review_findings.md").write_text("# Findings\n\nSee the findings table.\n", encoding="utf-8")
    (deliv / "document_summary.md").write_text("# Summary\n\nSynthetic fixture for console preview.\n", encoding="utf-8")
    FIXTURES.append(("completed, with findings", run_id))


def _build_same_document_earlier_run():
    """A second completed run of the SAME files as _build_completed_with_findings,
    submitted a day earlier: demonstrates that two runs of one document are told
    apart by the list's time column (relativeWhen, console.html), not by the
    friendly name alone, which is identical for both rows on purpose here."""
    run_id = "20260909_090000__e20f01"
    run_dir = RUNS_DIR / run_id
    _write_status(run_dir, run_id, "completed",
                   submitted_at=_now(60 * 25), started_at=_now(60 * 25 - 1),
                   completed_at=_now(60 * 24), exit_code=0)
    FIXTURES.append(("completed, same document, a day earlier", run_id))


def _seed_fixtures():
    _build_queued()
    _build_running()
    _build_awaiting_approval()
    _build_governance_stop()
    _build_governance_stop_redaction_gate()
    _build_crashed()
    _build_timed_out()
    _build_cancelled()
    _build_completed_with_findings()
    _build_same_document_earlier_run()

    # _rebuild_jobs_from_disk() already ran once at `import server` above,
    # before these fixture files existed, so JOBS is currently empty; force
    # a rebuild now that the fixtures are on disk.
    server.JOBS.clear()
    server._rebuild_jobs_from_disk()

    # _rebuild_jobs_from_disk() rewrites any on-disk "running" status to
    # "interrupted" (no live process behind it, correctly, for a real server
    # restart); push the two fixtures that need to stay live back to
    # "running" in memory AND on disk, the same pattern the real gate's own
    # fixtures use for this reason.
    with server.JOBS_LOCK:
        for _, run_id in FIXTURES:
            job = server._find_job(run_id)
            if job is not None and job.get("status") == "interrupted":
                job["status"] = "running"
                server._write_status(job)


if __name__ == "__main__":
    _seed_fixtures()
    banner = "\n".join([
        "",
        "=" * 72,
        "Console preview: a stubbed server, no model, nothing real runs.",
        "",
        f"  Open:  http://127.0.0.1:8731/console",
        f"  Token: {TOKEN}",
        "",
        "  Enter the token in the masthead's field and click Use. States",
        "  already on the run list:",
    ] + [f"    {label:<24} {run_id}" for label, run_id in FIXTURES] + [
        "",
        "  Submitting a run from the console's Submit tab also works: it",
        "  moves through queued -> running -> completed for real (about 30s),",
        "  against the stub above, still no model, nothing real.",
        "",
        "  Ctrl+C to stop. All fixture data is thrown away on exit.",
        "=" * 72,
        "",
    ])
    print(banner)
    import uvicorn
    try:
        uvicorn.run(server.app, host="127.0.0.1", port=8731, log_level="warning")
    except KeyboardInterrupt:
        pass
