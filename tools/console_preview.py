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

REGISTRY_DIR = Path(tempfile.mkdtemp(prefix="shimmer_console_preview_registry_"))
atexit.register(lambda: shutil.rmtree(REGISTRY_DIR, ignore_errors=True))
REGISTRY_PATH = REGISTRY_DIR / "convention_registry.json"

TOKEN = secrets.token_hex(16)
os.environ["SHIMMER_TOKEN_HASH"] = hashlib.sha256(TOKEN.encode()).hexdigest()
os.environ["SHIMMER_OUTPUT_DIR"] = str(RUNS_DIR)
os.environ["SHIMMER_CONVENTION_REGISTRY"] = str(REGISTRY_PATH)
os.environ["SHIMMER_PORT"] = "8731"
os.environ["SHIMMER_HOST"] = "127.0.0.1"
os.environ["SHIMMER_LOG_LEVEL"] = "warning"
os.environ["SHIMMER_APPROVAL_WAIT_S"] = "3600"

# A throwaway registry, never the real repository's config/convention_registry.json
# (SHIMMER_CONVENTION_REGISTRY points server.py here instead; see server.py's own
# docstring table and docs/api/CONSOLE_LAYOUT_PLAN.md "Item 3"/"Item 4"). Covers the
# rule ids the fixtures below already cite, so the pairing-map source_rule_id fix and
# GET /rules/{rule_id} are both genuinely demonstrable, not just present in the code.
REGISTRY_PATH.write_text(json.dumps({
    "schema_version": "1.0.0",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "source_files": ["review_conventions.md"],
    "conventions": [
        {"id": "CONV-001", "category": "conv-a02", "rule": "A stated tonnage figure must not exceed the reference table's upper bound for its category.",
         "source_file": "review_conventions.md", "source_location": "section 2", "severity": "required", "action": "flag"},
        {"id": "CONV-003", "category": "conv-b01", "rule": "A total must equal the sum of its stated parts, within the configured tolerance.",
         "source_file": "review_conventions.md", "source_location": "section 3", "severity": "required", "action": "flag"},
        {"id": "CONV-007", "category": "conv-c03", "rule": "A stated tonnage figure must not fall below the reference table's lower bound for its category.",
         "source_file": "review_conventions.md", "source_location": "section 4", "severity": "required", "action": "flag"},
    ],
}, indent=2), encoding="utf-8")


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

# The real Popen, kept for the one child this helper genuinely spawns (the
# headless browser of --screenshots); everything else, i.e. the pipeline, is
# the fake below.
_REAL_POPEN = subprocess.Popen
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


def _write_log(run_dir, lines):
    """logs/pipeline_stdout.log, the file GET /runs/{id}/log streams and
    _run_record's has_log field checks for. server.py's _run_job creates
    this file unconditionally the moment the subprocess starts, before
    reading any output, so every REAL run past queued has one, even a run
    that crashed in its first second. Earlier fixtures in this file skipped
    writing it for every terminal state but one, which is why the console's
    log panel 404d on all of them, an unrealistic gap in this harness, not a
    real one in what the pipeline produces (docs/api/CONSOLE_LAYOUT_PLAN.md
    "Item 1")."""
    logs = run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "pipeline_stdout.log").write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def _build_awaiting_approval_no_content():
    """A pending approval with neither message nor payload, the shape
    _pending_approval_for's own defaults allow (server.py: message defaults
    to "", payload defaults to {}). Demonstrates the fix for Approve/Deny
    rendering with nothing above them: the console must say the basis for
    the decision is missing, not present two bare buttons."""
    run_id = "20260910_130500__c3f001"
    run_dir = RUNS_DIR / run_id
    _write_status(
        run_dir, run_id, "running",
        submitted_at=_now(9), started_at=_now(8), completed_at=None,
        progress="phase=6.5/9 status=running",
    )
    audit = run_dir / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    (audit / "pending_approval.json").write_text(json.dumps({
        "topic": "",
        "asked_at": _now(1),
        "payload": {},
    }, indent=2), encoding="utf-8")
    FIXTURES.append(("awaiting_approval, no message or payload", run_id))


def _build_governance_stop():
    run_id = "20260910_120000__90ba01"
    run_dir = RUNS_DIR / run_id
    _write_status(
        run_dir, run_id, "stopped_model_approval",
        submitted_at=_now(31), started_at=_now(30), completed_at=_now(20), exit_code=3,
        error="the model gate stopped this run for operator approval",
    )
    _write_log(run_dir, [
        "[progress] event=start docs=1 status=running",
        "[progress] phase=1/9 status=running",
        "[progress] phase=3/9 status=running",
        "[progress] phase=5/9 status=running",
        "[progress] phase=6/9 status=running",
        "model_gate: a deprecated model assignment needs operator approval",
        "wait window closed with no decision recorded",
        "run stopped: stopped_model_approval",
    ])
    FIXTURES.append(("governance stop (stopped_model_approval)", run_id))


def _build_governance_stop_redaction_gate():
    """A second governance stop, a DIFFERENT code than _build_governance_stop:
    proves the human-view sentence is looked up per code (GOVERNANCE_SENTENCES_HUMAN
    in console.html) rather than one fixed sentence reused for all four, which
    was the bug this fixture exists to demonstrate is fixed."""
    run_id = "20260910_121500__d4d9c1"
    run_dir = RUNS_DIR / run_id
    _write_status(
        run_dir, run_id, "stopped_redaction_gate",
        submitted_at=_now(28), started_at=_now(27), completed_at=_now(19), exit_code=4,
        error="the redaction gate stopped this run before completion",
    )
    _write_log(run_dir, [
        "[progress] event=start docs=1 status=running",
        "[progress] phase=1/9 status=running",
        "[progress] phase=3/9 status=running",
        "[progress] phase=5/9 status=running",
        "[progress] phase=5.5/9 status=running",
        "[progress] phase=6/9 status=running",
        "[progress] phase=6.5/9 status=running",
        "[progress] phase=7/9 status=running",
        "[progress] phase=9/9 status=running",
        "redaction_gate: privacy check stopped the run before completion",
        "run stopped: stopped_redaction_gate",
    ])
    FIXTURES.append(("governance stop (stopped_redaction_gate)", run_id))


def _build_crashed():
    run_id = "20260910_120100__ca5501"
    run_dir = RUNS_DIR / run_id
    _write_status(
        run_dir, run_id, "failed",
        submitted_at=_now(26), started_at=_now(25), completed_at=_now(18), exit_code=1,
        error="Traceback (most recent call last):\n  File \"scripts/pipeline.py\", line 512, in run\n    raise RuntimeError('synthetic crash for console preview')\nRuntimeError: synthetic crash for console preview",
    )
    _write_log(run_dir, [
        "[progress] event=start docs=1 status=running",
        "[progress] phase=1/9 status=running",
        "Traceback (most recent call last):",
        "  File \"scripts/pipeline.py\", line 512, in run",
        "    raise RuntimeError('synthetic crash for console preview')",
        "RuntimeError: synthetic crash for console preview",
    ])
    FIXTURES.append(("crashed", run_id))


def _build_crashed_with_partial_findings():
    """A crash AFTER phase 5.5 already ran: real findings and a real pairing
    map exist on disk for this run despite it never reaching outcome=succeeded.
    Demonstrates the fix for the hidden-findings gap (CONSOLE_STATE_AUDIT.md):
    the console must fetch and show these, labeled partial, not hide them
    because the outcome was not a clean completion."""
    run_id = "20260910_120300__b7a501"
    run_dir = RUNS_DIR / run_id
    _write_status(
        run_dir, run_id, "failed",
        submitted_at=_now(35), started_at=_now(34), completed_at=_now(10), exit_code=1,
        error="Traceback (most recent call last):\n  File \"scripts/pipeline.py\", line 812, in run\n    raise RuntimeError('synthetic crash after phase 5.5, for console preview')\nRuntimeError: synthetic crash after phase 5.5, for console preview",
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
                    "unit_id": "u09", "kind": "provision",
                    "paired": [{"rule_id": "CONV-007", "reason": "unit states a figure this rule checks"}],
                    "rejected": [], "undecided": [],
                    "prior_comparisons": {"hit_count": 0, "checks": [], "refused": []},
                },
            ],
        },
    }, indent=2), encoding="utf-8")
    logs = run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    bus_item = {
        "item_id": "f010", "revision": 1,
        "rule_id": "CONV-007", "source_rule_id": "CONV-C03", "unit_id": "u09",
        "value_a": 210.0, "unit_a": "kt", "value_b": 250.0, "unit_b": "kt",
        "relation": "below_band", "record_verdict": "irregular",
        "source_refs": ["REF-0090"],
        "explanation": "The stated figure falls below the reference table's lower bound for this category, found before the run crashed in a later phase.",
    }
    (logs / "agent_bus.jsonl").write_text(json.dumps({
        "sender": "PRACTICE_AUDITOR",
        "body": {"payload": {"agent": "PRACTICE_AUDITOR", "doc_id": "case_a", "items": [bus_item]}},
    }) + "\n", encoding="utf-8")
    _write_log(run_dir, [
        "[progress] event=start docs=1 status=running",
        "[progress] phase=1/9 status=running",
        "[progress] phase=3/9 status=running",
        "[progress] phase=5/9 status=running",
        "[progress] phase=5.5/9 status=running",
        "below_band: CONV-007 (CONV-C03) unit u09, 210.0 kt against 250.0 kt",
        "[progress] phase=6/9 status=running",
        "Traceback (most recent call last):",
        "  File \"scripts/pipeline.py\", line 812, in run",
        "    raise RuntimeError('synthetic crash after phase 5.5, for console preview')",
        "RuntimeError: synthetic crash after phase 5.5, for console preview",
    ])
    FIXTURES.append(("crashed, with partial findings from before the crash", run_id))


def _build_timed_out():
    run_id = "20260910_120200__7171e0"
    run_dir = RUNS_DIR / run_id
    _write_status(
        run_dir, run_id, "failed",
        submitted_at=_now(91), started_at=_now(90), completed_at=_now(0), exit_code=None,
        error="run exceeded the configured timeout and was terminated",
    )
    _write_log(run_dir, [
        "[progress] event=start docs=1 status=running",
        "[progress] phase=1/9 status=running",
        "[progress] phase=3/9 status=running",
        "[progress] phase=5/9 status=running",
        "[progress] phase=5.5/9 status=running",
        "[progress] phase=6/9 status=running",
        "run exceeded the configured timeout, terminating",
    ])
    FIXTURES.append(("timed out", run_id))


def _build_cancelled():
    run_id = "20260910_110402__29c005"
    run_dir = RUNS_DIR / run_id
    _write_status(
        run_dir, run_id, "cancelled",
        submitted_at=_now(16), started_at=_now(15), completed_at=_now(14), exit_code=-15,
        error="cancelled by operator while running",
    )
    _write_log(run_dir, [
        "[progress] event=start docs=1 status=running",
        "[progress] phase=1/9 status=running",
        "[progress] phase=3/9 status=running",
        "cancelled by operator while running",
    ])
    FIXTURES.append(("cancelled", run_id))


def _build_completed_with_findings():
    run_id = "20260910_140000__f19d01"
    run_dir = RUNS_DIR / run_id
    _write_status(run_dir, run_id, "completed",
                   submitted_at=_now(46), started_at=_now(45), completed_at=_now(2), exit_code=0)

    audit = run_dir / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    # The reference index the citation surface reads: without it a REF on a
    # finding is a link with nothing behind it, which is the state the console
    # audit found and this fixture exists to exercise.
    (audit / "reference_index.json").write_text(json.dumps({"entries": [
        {"ref_id": "REF-0012", "input_type": "context",
         "document_id": "case_a", "document_name": "case_a.md",
         "location": {"paragraph": 4},
         "text_excerpt": "The upper bound for this category is 100 tonnes per declared period."},
        {"ref_id": "REF-0031", "input_type": "context",
         "document_id": "case_a", "document_name": "case_a.md",
         "location": {"paragraph": 9},
         "text_excerpt": "Amounts stated in a second currency are normalised before comparison."},
    ]}), encoding="utf-8")
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
    # night W8: the convention assignment this run's BOOT would have written
    # (audit/convention_assignment.json), shaped to exercise every state the
    # console renders: a rule assigned to a checker, a rule matched only by an
    # agent with no rule-consuming path, a rule no agent declares, and no
    # untagged rule at all, so the firing gate keeps STYLE_GUARDIAN from
    # running (the fourth visible state). Subject words are the registry's own
    # engine-side labels, not domain vocabulary.
    (audit / "convention_assignment.json").write_text(json.dumps({
        "by_rule": {
            "CONV-001": {"subjects": ["conformance"], "agents": ["PRACTICE_AUDITOR"],
                         "consumer_agents": ["PRACTICE_AUDITOR"], "status": "assigned"},
            "CONV-003": {"subjects": ["fidelity"], "agents": ["VERIFIER"],
                         "consumer_agents": [], "status": "assigned_no_consumer"},
            "CONV-004": {"subjects": ["provenance"], "agents": [],
                         "consumer_agents": [], "status": "unassigned"},
        },
        "by_agent": {"PRACTICE_AUDITOR": ["CONV-001"], "VERIFIER": ["CONV-003"],
                     "STYLE_GUARDIAN": []},
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
    # review_data.json: the amendment matching f001 (the one irregular finding
    # above; f002 is record_verdict=ok, amendment_from_finding's own gate
    # never builds one for that case). original_text is the real passage
    # (docs/api/CONSOLE_LAYOUT_PLAN.md's source fix, unit_texts_for), proving
    # the common case: all four required facts present together.
    (deliv / "review_data.json").write_text(json.dumps({
        "amendments": [
            {
                "ref": "REF-0012", "kind": "amendment", "confidence": "CONFIDENT",
                "location": "REF-0012", "convention_ref": "CONV-001",
                "source_convention_ref": "CONV-A02",
                "original_text": "## Article 2, quota volume\n\nThe declared quota volume for this category is 120 tonnes, "
                                  "consistent with the operational plan submitted alongside this filing.",
                "proposed_text": "The declared quota volume for this category is 100 tonnes, "
                                 "consistent with the operational plan submitted alongside this filing.",
                "action": "flag", "severity": "required", "finding_type": "factual",
                "ref_ids": ["REF-0012"], "derived_from": "computed_finding",
                "finding_unit_id": "u01", "finding_rule_id": "CONV-001",
                "comment": "The computed value is 120.0 tonnes, above the reference bound of 100.0 tonnes. "
                           "Computed in code from the figures in this unit, not judged by a model. "
                           "Grounded in CONV-001 (CONV-A02) at REF-0012.",
            },
        ],
    }, indent=2), encoding="utf-8")
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


def _build_completed_amendment_edge_cases():
    """A separate completed run demonstrating the two amendment edge cases
    the operator's own requirement names explicitly: a proposal with no
    reasoning recorded (must be said plainly, never shown as though
    complete), and an amendment produced BEFORE the source fix in
    paired_review.py's amendment_from_finding, still carrying the OLD shape
    (a bare unit id in original_text) exactly as it would sit on disk in a
    real run predating that fix. derived_from=computed_finding with
    original_text NOT starting "unit id " and not real prose (the raw old
    value) is exactly the shape server.py's _amendment_view flags via
    original_text_is_passage."""
    run_id = "20260910_150000__ac1d01"
    run_dir = RUNS_DIR / run_id
    _write_status(run_dir, run_id, "completed",
                   submitted_at=_now(5), started_at=_now(4), completed_at=_now(1), exit_code=0)
    audit = run_dir / "audit"
    audit.mkdir(parents=True, exist_ok=True)
    (audit / "pairing_map.json").write_text(json.dumps({
        "case_a": {
            "document_id": "case_a", "unit_count": 2, "rule_count": 2,
            "pair_count": 2, "rejected_count": 0, "undecided_count": 0,
            "unmatched_units": [], "missing_field_findings": [],
            "units": [
                {"unit_id": "u05", "kind": "provision",
                 "paired": [{"rule_id": "CONV-001", "reason": "unit states a figure this rule checks"}],
                 "rejected": [], "undecided": [],
                 "prior_comparisons": {"hit_count": 0, "checks": [], "refused": []}},
                {"unit_id": "u06", "kind": "provision",
                 "paired": [{"rule_id": "CONV-003", "reason": "unit states a figure this rule checks"}],
                 "rejected": [], "undecided": [],
                 "prior_comparisons": {"hit_count": 0, "checks": [], "refused": []}},
            ],
        },
    }, indent=2), encoding="utf-8")
    logs = run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    bus_items = [
        {"item_id": "f020", "revision": 1, "rule_id": "CONV-001", "source_rule_id": "CONV-A02",
         "unit_id": "u05", "value_a": 300.0, "unit_a": "tonnes", "value_b": 100.0, "unit_b": "tonnes",
         "relation": "above_band", "record_verdict": "irregular", "source_refs": ["REF-0050"],
         "explanation": "No reasoning was supplied with this proposal (synthetic, for the console preview)."},
        {"item_id": "f021", "revision": 1, "rule_id": "CONV-003", "source_rule_id": "CONV-B01",
         "unit_id": "u06", "value_a": 90.0, "unit_a": "EUR", "value_b": 60.0, "unit_b": "EUR",
         "relation": "sum_mismatch", "record_verdict": "irregular", "source_refs": ["REF-0060"],
         "explanation": "The stated total does not match its parts (synthetic, for the console preview)."},
    ]
    bus_lines = [json.dumps({"sender": "PRACTICE_AUDITOR",
                             "body": {"payload": {"agent": "PRACTICE_AUDITOR", "doc_id": "case_a", "items": [it]}}})
                 for it in bus_items]
    (logs / "agent_bus.jsonl").write_text("\n".join(bus_lines) + "\n", encoding="utf-8")
    deliv = run_dir / "deliverables" / "case_a"
    deliv.mkdir(parents=True, exist_ok=True)
    (deliv / "review_findings.md").write_text("# Findings\n", encoding="utf-8")
    (deliv / "document_summary.md").write_text("# Summary\n", encoding="utf-8")
    (deliv / "review_data.json").write_text(json.dumps({
        "amendments": [
            # Edge case one: no reasoning recorded (comment deliberately
            # empty, which the real contract requires >=1 CONV-*/REF-* in,
            # so this shape should not occur from a real run; included to
            # prove the console says so rather than showing a blank field
            # as though the proposal were complete).
            {
                "ref": "REF-0050", "kind": "amendment", "confidence": "CONFIDENT",
                "location": "REF-0050", "convention_ref": "CONV-001",
                "source_convention_ref": "CONV-A02",
                "original_text": "## Article 5, secondary quota\n\nThe secondary quota volume is 300 tonnes.",
                "proposed_text": "The secondary quota volume is 100 tonnes.",
                "action": "flag", "severity": "required", "finding_type": "factual",
                "ref_ids": ["REF-0050"], "derived_from": "computed_finding",
                "finding_unit_id": "u05", "finding_rule_id": "CONV-001",
                "comment": "",
            },
            # Edge case two: the PRE-FIX shape, original_text is a bare unit
            # id (what amendment_from_finding wrote before the source fix),
            # exactly as it would still sit in a real run's review_data.json
            # produced before this session's change.
            {
                "ref": "REF-0060", "kind": "amendment", "confidence": "CONFIDENT",
                "location": "REF-0060", "convention_ref": "CONV-003",
                "source_convention_ref": "CONV-B01",
                "original_text": "u06",
                "proposed_text": None,
                "action": "flag", "severity": "required", "finding_type": "factual",
                "ref_ids": ["REF-0060"], "derived_from": "computed_finding",
                "finding_unit_id": "u06", "finding_rule_id": "CONV-003",
                "comment": "The computed value is 90.0 EUR against a stated 60.0 EUR. "
                           "Computed in code from the figures in this unit, not judged by a model. "
                           "Grounded in CONV-003 (CONV-B01) at REF-0060.",
            },
        ],
    }, indent=2), encoding="utf-8")
    FIXTURES.append(("completed, amendment edge cases (no reasoning, pre-fix)", run_id))


def _seed_ontology():
    """Seed the cross-run ontology so the Agents page's four ontology sections
    have something true to show: provisions, a merged relation found by BOTH
    mechanisms (the case a reader would trust most), an answered conflict, and a
    GNN state. This harness is a throwaway local preview and is never run by the
    gate or by a real run."""
    import ontology_store as _os_mod
    import relation_extract as _rx
    import ontology_conflicts as _oc

    live = ROOT / "ontology" / "stores" / "provisions.jsonl"
    live.parent.mkdir(parents=True, exist_ok=True)
    store = _os_mod.ProvisionStore(live_path=live, scope=_os_mod.DEFAULT_SCOPE)
    if store.current():
        return                      # already seeded; never duplicate
    t = _os_mod.now_iso()
    run = "20260910_140000__f19d01"
    store.append([
        {"node": "Provision", "id": "case_a::REF-0012", "document_id": "case_a",
         "ref_id": "REF-0012", "convention_ref": "CONV-001", "stub": False,
         "provenance": _os_mod.provenance(time=t, agent="PRACTICE_AUDITOR", run=run)},
        {"node": "Provision", "id": "case_a::REF-0031", "document_id": "case_a",
         "ref_id": "REF-0031", "convention_ref": "CONV-003", "stub": False,
         "provenance": _os_mod.provenance(time=t, agent="STYLE_GUARDIAN", run=run)},
    ])
    merged = _rx.merge_relations([
        {"type": _rx.RELATION_CROSS_REFERENCE, "method": _rx.METHOD_PATTERN,
         "source": "u09-entry", "target": "u01-glossary", "pattern": "defined-term-reference"},
        {"type": _rx.RELATION_SIMILAR, "method": _rx.METHOD_SIMILARITY,
         "source": "u01-glossary", "target": "u09-entry", "score": 0.94},
        {"type": _rx.RELATION_SIMILAR, "method": _rx.METHOD_SIMILARITY,
         "source": "u03-clause", "target": "u11-clause", "score": 0.81},
    ])
    store.append(_rx.relation_records(
        merged, document_id="case_a", run_id=run,
        provenance=_os_mod.provenance(time=t, agent=None, run=run)))
    conflicts = _oc.detect_conflicts(store.current(), {"case_a::REF-0012": "CONV-009"})
    if conflicts:
        _oc.write_resolutions(store, {conflicts[0]["conflict_id"]: _oc.ANSWER_RULE},
                              run_id="operator",
                              conflicts_by_id={c["conflict_id"]: c for c in conflicts})


def _seed_fixtures():
    _seed_ontology()
    _build_queued()
    _build_running()
    _build_awaiting_approval()
    _build_awaiting_approval_no_content()
    _build_governance_stop()
    _build_governance_stop_redaction_gate()
    _build_crashed()
    _build_crashed_with_partial_findings()
    _build_timed_out()
    _build_cancelled()
    _build_completed_with_findings()
    _build_completed_amendment_edge_cases()
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


def _find_browser():
    """A Chromium-based browser for headless screenshots: Edge first (present on
    every Windows 11 machine), then Chrome. Always launched with its OWN throwaway
    user-data-dir, so it never attaches to, or touches, a browser the operator has
    open."""
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    for name in ("msedge", "google-chrome", "chromium", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("no Chromium-based browser found for screenshots (Edge or Chrome)")


def _wait_http(url, timeout_s=90.0):
    """Poll a local URL until it answers. A cold headless browser on a loaded
    machine can accept the connection well before it answers, so each attempt
    waits several seconds and the overall budget is generous; no proxy is ever
    consulted for these loopback addresses."""
    import time
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            with opener.open(url, timeout=8) as r:
                return r.read()
        except Exception as e:  # not up yet
            last = e
            time.sleep(0.5)
    raise SystemExit(f"{url} did not come up within {timeout_s}s: {last}")


# The pages the W8 report shows, in both views: (file stem, view, hash). The run
# is the "completed, with findings" fixture, which also carries the convention
# assignment (distribution, an unassigned rule, a checker the gate kept from
# running, agents no tagged rule reached).
SCREENSHOT_PAGES = [
    # (file stem, view, hash, max height in CSS px or None for the whole page).
    # The Agents page is 18 agents by nine parts, some seventeen thousand
    # pixels tall in full; its top 2600 px carry the heading, the counts and
    # the first agents with an undecided part, which is what the proof needs.
    ("runs", "human", "#/runs", None),
    ("runs", "developer", "#/runs", None),
    ("run_findings", "human", "#/runs/20260910_140000__f19d01", None),
    ("run_findings", "developer", "#/runs/20260910_140000__f19d01", None),
    ("agents", "human", "#/agents", 2600),
    ("agents", "developer", "#/agents", 2600),
    # The four ontology sections (store, GNN state, relations, candidates,
    # conflicts) render BELOW eighteen agents of nine parts each, far past the
    # 2600 px the shots above keep. These capture that region instead, which is
    # where the console audit's new work actually shows.
    ("ontology_sections", "human", "#/agents", 2600, "ontology-store-holder"),
    ("ontology_sections", "developer", "#/agents", 2600, "ontology-store-holder"),
]


async def _shoot_pages(ws_url, out_dir, settle_s=3.0):
    """Drive one browser tab over the Chrome DevTools Protocol: sign the console
    in by writing the throwaway token into sessionStorage (exactly what the
    masthead's token screen does), then for each page set the view, navigate,
    let the fetches settle, size the viewport to the page and capture it."""
    import asyncio
    import base64
    import websockets

    async with websockets.connect(ws_url, max_size=None) as ws:
        counter = [0]

        async def cmd(method, **params):
            counter[0] += 1
            msg_id = counter[0]
            await ws.send(json.dumps({"id": msg_id, "method": method, "params": params}))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == msg_id:
                    if "error" in msg:
                        raise RuntimeError(f"{method}: {msg['error']}")
                    return msg.get("result", {})

        await cmd("Page.enable")
        await cmd("Emulation.setDeviceMetricsOverride", width=1280, height=900,
                  deviceScaleFactor=1, mobile=False)
        await cmd("Page.navigate", url="http://127.0.0.1:8731/console")
        await asyncio.sleep(1.5)
        await cmd("Runtime.evaluate",
                  expression=f"sessionStorage.setItem('shimmer_console_token', {json.dumps(TOKEN)});")
        written = []
        for page in SCREENSHOT_PAGES:
            stem, view, frag, max_height = page[0], page[1], page[2], page[3]
            anchor_id = page[4] if len(page) > 4 else None
            await cmd("Runtime.evaluate",
                      expression=(f"sessionStorage.setItem('shimmer_console_view', {json.dumps(view)});"
                                  f"location.hash = {json.dumps(frag)}; location.reload();"))
            await asyncio.sleep(settle_s)
            metrics = await cmd("Page.getLayoutMetrics")
            size = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
            height = max(900, int(size.get("height") or 900))
            if max_height:
                height = min(height, max_height)
            top = 0
            if anchor_id:
                # clip from the named section's own top, so a page far taller
                # than the clip still proves the sections that matter
                res = await cmd("Runtime.evaluate", expression=(
                    "(function(){var e=document.getElementById(" + json.dumps(anchor_id) + ");"
                    "return e ? Math.max(0, Math.round(e.getBoundingClientRect().top + window.scrollY) - 40) : 0;})()"),
                    returnByValue=True)
                top = int((res.get("result") or {}).get("value") or 0)
            await cmd("Emulation.setDeviceMetricsOverride", width=1280, height=height,
                      deviceScaleFactor=1, mobile=False)
            await asyncio.sleep(0.4)
            shot = await cmd("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                             clip={"x": 0, "y": top, "width": 1280, "height": height, "scale": 1})
            target = Path(out_dir) / f"{stem}_{view}.png"
            target.write_bytes(base64.b64decode(shot["data"]))
            written.append(target)
        return written


def _capture_screenshots(out_dir):
    """night W8: prove the console against the running stubbed server the way it
    was proved before, but through a headless browser so the proof is a set of
    files a report can carry. Starts the same server this preview always starts
    (in a thread), launches a headless Edge/Chrome with a throwaway profile and a
    remote-debugging port, captures SCREENSHOT_PAGES, then stops both."""
    import asyncio
    import urllib.request
    import uvicorn

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # The browser first, its stderr kept in the throwaway profile (it is where
    # "DevTools listening on ..." and any refusal to start are written), then the
    # server in a thread; both start-ups overlap.
    browser = _find_browser()
    profile = tempfile.mkdtemp(prefix="shimmer_console_shot_profile_")
    port = 9333
    browser_log = open(Path(profile) / "browser_stderr.txt", "wb")
    # _REAL_POPEN, not subprocess.Popen: this module stubs Popen so the pipeline
    # never runs, and that stub swallowed the browser launch the first time.
    proc = _REAL_POPEN(
        [browser, "--headless=new", "--disable-gpu", "--no-first-run",
         "--no-default-browser-check", f"--remote-debugging-port={port}",
         f"--user-data-dir={profile}", "--window-size=1280,900", "about:blank"],
        stdout=browser_log, stderr=browser_log)
    config = uvicorn.Config(server.app, host="127.0.0.1", port=8731, log_level="warning")
    srv = uvicorn.Server(config)
    thread = threading.Thread(target=srv.run, daemon=True)
    thread.start()
    try:
        _wait_http("http://127.0.0.1:8731/health")
        try:
            _wait_http(f"http://127.0.0.1:{port}/json/version")
        except SystemExit:
            browser_log.flush()
            print("[screenshot] browser exit code:", proc.poll(), file=sys.stderr)
            print("[screenshot] browser stderr:",
                  (Path(profile) / "browser_stderr.txt").read_text(errors="replace")[:2000],
                  file=sys.stderr)
            raise
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
        with opener.open(req, timeout=10) as r:
            target = json.loads(r.read())
        written = asyncio.run(_shoot_pages(target["webSocketDebuggerUrl"], out_dir))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        browser_log.close()
        srv.should_exit = True
        thread.join(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)
    for p in written:
        print(f"[screenshot] {p} ({p.stat().st_size} bytes)")
    return written


if __name__ == "__main__":
    import argparse
    _ap = argparse.ArgumentParser(description="console preview (stubbed server, no model)")
    _ap.add_argument("--screenshots", metavar="DIR",
                     help="capture both views of the run list, a run's page and the Agents "
                          "page into DIR through a headless browser, then exit")
    _args = _ap.parse_args()
    _seed_fixtures()
    if _args.screenshots:
        _capture_screenshots(_args.screenshots)
        raise SystemExit(0)
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
