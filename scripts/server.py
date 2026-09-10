"""Project Shimmer M3 front door: a thin, token-gated FastAPI dock.

WHAT THIS IS (read first)
=========================
This is a small web server. It lets a known collaborator hand an external corpus
of grounding cases to Shimmer, start a review run, watch the queue, and pull the
results, all over the network, without ever touching the code or the terminal.

It is a connecting DOCK, not a hardened public production service. One collaborator,
one server, gated by a single secret token. Keep that scope in mind: every design
choice below favors "simple and visible for one person" over "scales to thousands".

HOW THE PIECES FIT
==================
1. The collaborator POSTs their .md case files plus the _corpus_ingest.json sidecar
   to /submit.
2. The server validates them against the corpus ingestion contract (Item 1). Bad
   data is rejected with 400 and never enters the pipeline.
3. Good data is queued. One job runs at a time. When a job starts, its files are
   placed into input/context/ and the existing pipeline (scripts/pipeline.py) is run
   as a SUBPROCESS, writing into its own per-run folder output/runs/<run_id>/.
4. When the run finishes, the server AUTO-CLEARS the ingested files it placed
   (using the sidecar as the manifest), so nothing stale leaks into the next run.
5. The collaborator polls /status/<run_id> and /queue, then downloads
   /results/<run_id>.

HOW TO GENERATE THE TOKEN AND ITS HASH (the operator runs this ONCE)
===================================================================
    python -c "import secrets, hashlib; t=secrets.token_hex(32); print(f'Token (give to the collaborator): {t}'); print(f'Hash (set as SHIMMER_TOKEN_HASH): {hashlib.sha256(t.encode()).hexdigest()}')"

That prints two strings. Give the first (the token) to the collaborator out of band
(a secure message, once). Set the second (the hash) as the SHIMMER_TOKEN_HASH
environment variable before starting this server. The plain token is NEVER stored
anywhere on the server: only its hash is, and a hash cannot be reversed back into
the token.

HOW TO RUN IT
=============
    set SHIMMER_TOKEN_HASH=<the hash from above>        (Windows)
    export SHIMMER_TOKEN_HASH=<the hash from above>     (macOS/Linux)
    python scripts/server.py

Then expose it with a temporary public HTTPS URL:
    cloudflared tunnel --url http://localhost:8000

ENVIRONMENT VARIABLES (operator reference)
==========================================
Every knob below is read ONCE at startup; the resolved values are printed to stderr.
Unset means the default shown in (parentheses). Set them before launching the server:
`set NAME=value` (Windows) or `export NAME=value` (macOS/Linux).

  SHIMMER_TOKEN_HASH   (required)     sha256 hash of the access token. The server
                                      refuses to start without it. Never the token value.
  SHIMMER_MODE         (integrated)   pipeline run intent: "standalone" or "integrated".
                                      integrated activates the corpus_ingest
                                      promotion-exclusion hook (grounding cases stay
                                      out of the operational review).
  SHIMMER_TASK         (review)       default task for /submit when the caller omits the
                                      "task" form field: "review" or "draft".
  SHIMMER_SENSITIVE    (false)        "true" or "false". false declares the run non-sensitive
                                      and passes --sensitivity-layer-inactive-override and
                                      --no-redaction-override (no redaction). true keeps
                                      redaction on; note the full LAW-IV layer ships inactive,
                                      so true requires the operator to have activated it or the
                                      pipeline hard-stops at its sensitivity gate, by design.
  SHIMMER_MAX_DOCS     (4)            integer; passed as --max-concurrent-docs. 4 is safe for a
                                      single-key Claude rate limit; raise it if your limits allow.
  SHIMMER_PORT         (8000)         integer; the TCP port uvicorn listens on.
  SHIMMER_HOST         (0.0.0.0)      interface to bind. 0.0.0.0 = all interfaces (a public
                                      tunnel needs this); use 127.0.0.1 to stay local-only.
  SHIMMER_AUTO_CLEAR   (true)         "true" or "false"; remove the ingested grounding files from
                                      input/context/ after each run (the sidecar is the manifest).
                                      false leaves the placed files in place for inspection.
  SHIMMER_OUTPUT_DIR   (output/runs/) custom root folder for the per-run output directories.
  SHIMMER_LOG_LEVEL    (info)         uvicorn log level: "debug", "info", or "warning".
  SHIMMER_RUN_TIMEOUT_S (0)           integer seconds; 0 means unbounded (prior behavior). When
                                      set, a run's pipeline subprocess is terminated (then killed)
                                      after this many seconds; the job is marked failed with a
                                      timeout reason and exit_code null. Cleanup still runs.
  SHIMMER_LOCAL_RUN_TIMEOUT_S (7200)  integer seconds; overrides RUN_TIMEOUT_S when
                                      SHIMMER_BACKEND_PROFILE=local. Local inference is far slower
                                      than cloud API calls, so the default is 2 hours. 0 means
                                      unbounded. Only read when the backend profile is "local".
  SHIMMER_PROVIDER_TIMEOUT_S (600)    integer seconds; per-request wall-clock timeout passed to
                                      the Anthropic and OpenAI clients (agent_wrapper.py). Read by
                                      the pipeline subprocess, not the server process itself.
  SHIMMER_MAX_UPLOAD_MB (25)          integer; per-file upload size cap in megabytes for /submit.
  SHIMMER_MAX_UPLOAD_TOTAL_MB (200)   integer; whole-submission upload size cap in megabytes.
  SHIMMER_MAX_UPLOAD_FILES (50)       integer; max number of files accepted in one /submit.
  SHIMMER_APPROVAL_WAIT_S (3600)      integer seconds; read by the pipeline subprocess (not this
                                      process) when it installs the --operator-channel file
                                      handler: how long a governed decision waits for a human to
                                      write approval_decision.json before defaulting to DEFERRED.

STEP 6: THE CONSOLE (GET /console)
====================================
The server always passes --operator-channel file to the pipeline subprocess, so a governed
decision (a deprecated-model swap, a constitution amendment) that would otherwise stop the run
is instead parked as <run>/audit/pending_approval.json and surfaced at GET /approvals. A human
decides APPROVE/DENY/DEFER via POST /approvals/{run_id}; the server only WRITES that decision
file, it never itself evaluates a governed decision (that stays in model_registry and
constitution_guard, unchanged by this server). GET /console serves scripts/ui/console.html: a
single vanilla-JavaScript page, no framework, no build step, no CDN dependency. NOTE: the STEP
6 spec's evidence text names this route "GET /"; it is served at /console instead because the
bare root collides with an existing gate check (94) that every HTTP client's own URL
normalization makes unavoidable (see the console() function's docstring for the full
explanation). The token is entered
once in the page (kept in page memory only, never a URL, never persisted) and sent as the
Authorization: Bearer header on every call the page makes. GET /health is the one route that
is NOT token-gated (by design, for external uptime checks); its body carries no SHIMMER_ value,
no path, no hash. Every non-zero pipeline exit is now mapped to a distinct status (see
_EXIT_STATUS_MAP below) rather than collapsed to "failed"; "blocked" and the "stopped_*"
statuses are governance outcomes, not errors.
"""

# ---------------------------------------------------------------------------
# IMPORTS (what each one is for)
# ---------------------------------------------------------------------------
import hashlib      # turns the token into a fixed-length fingerprint (sha256).
import hmac         # hmac.compare_digest: compares two hashes in constant time.
import io           # an in-memory bytes buffer, used to build the results .zip.
import json         # reads the _corpus_ingest.json sidecar (the file manifest).
import os           # reads the SHIMMER_TOKEN_HASH environment variable.
import re           # validates a URL-supplied run_id against the mint format.
import shutil       # copies and removes files and directories.
import subprocess   # runs the validator and the pipeline as separate programs.
import sys          # sys.executable = the exact Python running this server.
import threading    # a Lock (to guard the queue) and a background run thread.
import time         # api STEP B2: bounded polling in POST /runs/{run_id}/cancel.
import zipfile      # packages the run's deliverables into one downloadable .zip.
from datetime import datetime, timedelta, timezone   # timestamps for jobs and run ids.
from pathlib import Path                   # tidy, OS-independent file paths.
from typing import List, Optional          # 3.9-safe type hints for FastAPI.
import uuid                                # a short random suffix for run ids.

# FastAPI is the web framework. uvicorn is the program that actually serves it.
# BackgroundTasks/Depends/Header/HTTPException/UploadFile/File are FastAPI helpers
# explained at their first use below.
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import uvicorn

# ---------------------------------------------------------------------------
# PATHS (everything is anchored to the repo root, computed from THIS file)
# ---------------------------------------------------------------------------
# This file lives at <repo>/scripts/server.py, so the repo root is two levels up.
ROOT = Path(__file__).resolve().parent.parent

# productization STEP 10: make the sibling modules under scripts/ importable no
# matter HOW this file is loaded. `python scripts/server.py` puts scripts/ on
# sys.path automatically, but an external ASGI runner (`uvicorn scripts.server:app`
# from the repo root, the shape any container or process manager would use) puts
# only the repo root there, so the bare `import role_resolution` in
# _clear_system_draft raised ModuleNotFoundError the first time a draft job
# finished. Idempotent, and a no-op on the direct-launch path.
_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
CONTEXT_DIR = ROOT / "input" / "context"          # where grounding files live.
PIPELINE = ROOT / "scripts" / "pipeline.py"       # the review pipeline (subprocess).
VALIDATOR = ROOT / "corpus_ingest" / "validate_contract.py"  # the contract validator.
SIDECAR_NAME = "_corpus_ingest.json"              # the manifest the collaborator uploads.
UI_CONSOLE_PATH = ROOT / "scripts" / "ui" / "console.html"  # STEP 6: the operator console.

# The environment variable that holds the SHA-256 hash of the collaborator's token.
TOKEN_HASH_ENV = "SHIMMER_TOKEN_HASH"

# ---------------------------------------------------------------------------
# CONFIG (read ONCE from the environment at startup; see the docstring reference)
# ---------------------------------------------------------------------------
# Every value falls back to a sensible default when its variable is unset, so the
# server runs out of the box. The resolved set is printed to stderr on launch.
def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or not v.strip():
        return default
    try:
        return int(v.strip())
    except ValueError:
        return default


MODE = os.environ.get("SHIMMER_MODE", "integrated")        # standalone | integrated
TASK_DEFAULT = os.environ.get("SHIMMER_TASK", "review")    # review | draft (per /submit)
SENSITIVE = _env_bool("SHIMMER_SENSITIVE", False)          # redaction on/off for the run
MAX_DOCS = _env_int("SHIMMER_MAX_DOCS", 4)                 # --max-concurrent-docs
PORT = _env_int("SHIMMER_PORT", 8000)                      # uvicorn listen port
HOST = os.environ.get("SHIMMER_HOST", "0.0.0.0")           # uvicorn bind interface
AUTO_CLEAR = _env_bool("SHIMMER_AUTO_CLEAR", True)         # clear ingested files after a run
LOG_LEVEL = os.environ.get("SHIMMER_LOG_LEVEL", "info")    # uvicorn log level
# Per-run output root: a custom SHIMMER_OUTPUT_DIR, else the default output/runs/.
RUNS_DIR = Path(os.environ.get("SHIMMER_OUTPUT_DIR") or (ROOT / "output" / "runs"))
# productization STEP 3: timeouts and upload limits, all read once at startup.
RUN_TIMEOUT_S = _env_int("SHIMMER_RUN_TIMEOUT_S", 0)        # 0 = unbounded (prior behavior)
LOCAL_RUN_TIMEOUT_S = _env_int("SHIMMER_LOCAL_RUN_TIMEOUT_S", 7200)  # 2 hours for local mode

# api STEP A1: the two review modes the pipeline offers (--review-mode), named
# here so /submit can validate the field without importing pipeline.py.
REVIEW_MODES = ("paired", "wide")


def _backend_profile() -> str:
    """The resolved backend profile, "local" or "cloud".

    Read live from the environment (not frozen at import) because
    _effective_run_timeout and check_local_model_availability already read
    SHIMMER_BACKEND_PROFILE live, and a second, import-time copy of the same
    knob would be a way for the two to disagree. Anything that is not exactly
    "local" is the cloud profile, matching those two readers.
    """
    return "local" if os.environ.get("SHIMMER_BACKEND_PROFILE") == "local" else "cloud"


def _default_review_mode() -> str:
    """The review mode a submission gets when the caller names none: paired under
    the local profile, wide under cloud.

    This MIRRORS pipeline.resolve_review_mode(None, backend_profile) rather than
    importing it: pipeline.py is a large module and /health must not pay to
    import it. The mirror is pinned to the original by a gate check, so the two
    cannot drift apart silently.
    """
    return "paired" if _backend_profile() == "local" else "wide"


def _effective_run_timeout() -> int:
    """Return the active run timeout: LOCAL_RUN_TIMEOUT_S when the backend profile
    is 'local', otherwise RUN_TIMEOUT_S. Both support 0 = unbounded."""
    if os.environ.get("SHIMMER_BACKEND_PROFILE") == "local":
        return LOCAL_RUN_TIMEOUT_S
    return RUN_TIMEOUT_S


def check_local_model_availability():
    """When SHIMMER_BACKEND_PROFILE=local, verify that the required packages
    (torch, transformers) are importable and that both model IDs resolve to
    a local cache entry. Returns (ok: bool, detail: str)."""
    if os.environ.get("SHIMMER_BACKEND_PROFILE") != "local":
        return True, "not in local mode"
    problems = []
    for pkg in ("torch", "transformers"):
        try:
            __import__(pkg)
        except ImportError:
            problems.append(f"{pkg} is not installed")
    if problems:
        return False, "; ".join(problems)
    from pipeline import _LOCAL_PROFILE
    model_ids = sorted(set(m for _, m in _LOCAL_PROFILE.values()))
    import importlib
    transformers = importlib.import_module("transformers")
    for mid in model_ids:
        try:
            transformers.AutoTokenizer.from_pretrained(mid, local_files_only=True)
        except Exception:
            problems.append(f"model {mid} not found in local cache")
    if problems:
        return False, "; ".join(problems)
    return True, f"packages ok, models cached: {model_ids}"


MAX_UPLOAD_MB = _env_int("SHIMMER_MAX_UPLOAD_MB", 25)       # per-file cap
MAX_UPLOAD_TOTAL_MB = _env_int("SHIMMER_MAX_UPLOAD_TOTAL_MB", 200)  # whole-submission cap
MAX_UPLOAD_FILES = _env_int("SHIMMER_MAX_UPLOAD_FILES", 50) # file-count cap per submission

# The server's own run_id mint format ("%Y%m%d_%H%M%S__<6 hex>", see _new_run_id):
# /status and /results validate against this before building any path from a
# caller-supplied run_id, so a value like "../.." is rejected with 404 before it
# is ever used in a path expression.
_RUN_ID_RE = re.compile(r"^\d{8}_\d{6}__[0-9a-f]{6}$")

# productization STEP 6: exit-code -> status mapping. Replaces the old blanket
# "any non-zero exit is failed" collapse. "blocked" and the three "stopped_*"
# entries are governance outcomes (the pipeline refused or paused ON PURPOSE),
# never rendered as errors by the console. Exit 5 is deliberately overloaded
# upstream (pipeline.py: a redaction BLOCK at run-end, OR a draft-mode phase-0
# generation failure); this map cannot distinguish the two by exit code alone,
# so the console note tells the operator to check the log tail (see /runs and
# the run detail's logs_path). Sourced from pipeline.py's own `return N` exit
# points: 0 success (or 5 if a redaction BLOCK), 2 snapshot conflict
# (--save-snapshot only), 3 model-gate stop, 4 redaction-gate stop, 5 blocked
# (dual meaning, see above), 6 sensitivity-layer-inactive refusal, 7 operator
# abort (meta-signature decline). Anything else non-zero is a plain failure.
_EXIT_STATUS_MAP = {
    0: "completed",
    2: "snapshot_conflict",
    3: "stopped_model_approval",
    4: "stopped_redaction_gate",
    5: "blocked",
    6: "refused_sensitivity_layer_inactive",
    7: "operator_abort",
}
# Exit codes whose status is a governance outcome, not a failure: the console
# must render these distinctly from a crash (item 4 of STEP 6).
GOVERNANCE_STATUSES = {"blocked", "stopped_model_approval", "stopped_redaction_gate",
                       "refused_sensitivity_layer_inactive"}


def _status_for_exit_code(exit_code):
    """Map a raw pipeline exit code to its distinct status string. None (a run
    timeout, exit_code never observed) is handled by the caller before this is
    reached; here exit_code is always an int. Any code not in the table above,
    zero or non-zero, that is not otherwise a known governance/success code is
    "failed"."""
    if exit_code == 0:
        return "completed"
    return _EXIT_STATUS_MAP.get(exit_code, "failed")


def _config_summary() -> str:
    """The resolved config as one stderr line (the operator's at-a-glance check)."""
    return (f"[server] mode={MODE}, task={TASK_DEFAULT}, sensitive={str(SENSITIVE).lower()}, "
            f"max_docs={MAX_DOCS}, port={PORT}, host={HOST}, "
            f"auto_clear={str(AUTO_CLEAR).lower()}, output_dir={RUNS_DIR}, "
            f"log_level={LOG_LEVEL}, run_timeout_s={_effective_run_timeout()}, "
            f"max_upload_mb={MAX_UPLOAD_MB}, max_upload_total_mb={MAX_UPLOAD_TOTAL_MB}, "
            f"max_upload_files={MAX_UPLOAD_FILES}")

# ---------------------------------------------------------------------------
# THE APP
# ---------------------------------------------------------------------------
# FastAPI() builds the web application object. Routes (the URLs the server answers)
# are attached to it with decorators like @app.post("/submit") below.
app = FastAPI(title="Project Shimmer front door", version="1.0")


# ---------------------------------------------------------------------------
# TOKEN AUTH (the gate)
# ---------------------------------------------------------------------------
# This is the gate. Anyone with the URL but not the token gets rejected here. We
# store only the token's sha256 HASH (in an environment variable), never the token
# itself, so even someone who reads the server's environment cannot recover it.
def _check_token(authorization):
    """The core token check. `authorization` is the raw value of the request's
    Authorization header (the string "Bearer <token>"), or None if absent.

    Raises HTTPException(401) if: the server has no token hash configured, the
    header is missing or malformed, or the token does not match. Returns None on a
    correct token. Kept as a plain function (not tied to FastAPI internals) so the
    verify gate can call it directly to prove 401 behavior."""
    stored_hash = os.environ.get(TOKEN_HASH_ENV)
    if not stored_hash:
        # No hash configured: the server cannot authenticate anyone, so refuse all.
        raise HTTPException(status_code=401, detail="server has no token configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing or malformed Authorization header")
    token = authorization[len("Bearer "):].strip()
    # Hash what the caller sent, then compare to the stored hash. compare_digest is
    # used instead of == so the comparison time does not leak how many characters matched.
    sent_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(sent_hash, stored_hash):
        raise HTTPException(status_code=401, detail="invalid token")
    return None


# A FastAPI "dependency": FastAPI runs this before a protected route. Header(...)
# tells FastAPI to pull the Authorization header out of the request for us. If
# _check_token raises, FastAPI turns it into the 401 response automatically.
async def verify_token(authorization: Optional[str] = Header(default=None)):
    _check_token(authorization)


# ---------------------------------------------------------------------------
# THE QUEUE (a Python list in memory, mirrored to disk per run)
# ---------------------------------------------------------------------------
# The queue is a list of "job" dictionaries. Each job records its run id, current
# status, timestamps, an error message if it failed, and the filenames submitted.
# JOBS is the source of truth for the LIVE process.
#
# productization STEP 2 added a disk mirror, so a restart no longer loses the
# queue (this comment used to say "No database, no files, no persistence", which
# stopped being true in the same file). There is still no database and no queue
# file: every job's record is written to its OWN run folder as
# <run>/status.json by _write_status on each status transition, and
# _rebuild_jobs_from_disk() reads those files back at import to repopulate JOBS.
# A run that was "running" when the process died is rewritten as "interrupted"
# rather than being reported as still in flight, and an orphaned staging dir for
# a job that is no longer running is removed. Gate checks 88 to 91 cover exactly
# that path.
JOBS = []                      # the public job records (returned by /queue, /status).
JOBS_LOCK = threading.Lock()   # guards JOBS: HTTP requests arrive on many threads.
_STAGING = {}                  # private: run_id -> staging dir holding validated uploads.
                                # (productization STEP 2: guarded by JOBS_LOCK like JOBS)

# api STEP B2 (cancellation): before this step, the live subprocess.Popen
# object for a running job existed ONLY as a local variable inside _run_job,
# reachable solely by the run-timeout Timer's own closure (see the comment
# above that Timer below) -- nothing outside that one function could reach
# it, so nothing outside could ever ask it to stop. _PROCS is that missing
# place: run_id -> Popen, registered the moment Popen succeeds, removed in
# _run_job's own `finally` (terminal or not, so a run that crashes before
# reaching its own cleanup never leaves a stale entry). Guarded by the SAME
# JOBS_LOCK the rest of the job bookkeeping already uses, not a second lock,
# so a caller that holds JOBS_LOCK can always safely look here too.
_PROCS = {}
# run_id -> threading.Event, set by POST /runs/{run_id}/cancel the instant a
# RUNNING job is asked to stop. _run_job's post-subprocess bookkeeping checks
# this (alongside the existing `timed_out` Event from the run-timeout path)
# to tell "the caller cancelled this" apart from "the child process crashed
# or exited non-zero on its own" -- both end with the same subprocess exit
# mechanics (terminate/kill), so the DISTINCTION has to be recorded
# separately, not inferred from the exit code. Removed alongside _PROCS.
_CANCELLED = {}


def _now_iso():
    """Current UTC time as an ISO-8601 string, for the job timestamps."""
    return datetime.now(timezone.utc).isoformat()


def _new_run_id():
    """A run id: a readable timestamp plus a short random suffix, e.g.
    20260625_143022__a8f3b2. The timestamp makes runs sort chronologically; the
    random suffix guarantees two runs in the same second never collide."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{stamp}__{uuid.uuid4().hex[:6]}"


def _find_job(run_id):
    """Return the job dict for a run id, or None. Caller holds JOBS_LOCK."""
    return next((j for j in JOBS if j["run_id"] == run_id), None)


# ---------------------------------------------------------------------------
# STEP 2: run state on disk (productization). The JOBS list above is now a
# read-through CACHE over a per-run status.json; the file is the durable
# record, JOBS is what /status and /queue answer from without touching disk
# on every request. A job dict, plus "exit_code", is what gets written.
# ---------------------------------------------------------------------------
_STATUS_FIELDS = ("run_id", "status", "task", "submitted_at", "started_at",
                   "completed_at", "exit_code", "error", "progress", "files",
                   "sensitive", "review_mode", "question")


def _status_path(run_id):
    # Delegates to run_context.RunContext.status_path() (the single source of
    # truth for this path shape) rather than reimplementing it, so the server
    # and any future pipeline-side writer of status.json can never drift.
    import run_context as _rc
    return _rc.for_run_dir(ROOT, RUNS_DIR / run_id).status_path()


def _write_status(job):
    """Atomically write this job's status.json (temp file then replace, as
    cost_tracker.py::_persist_snapshot does). Best-effort: a write failure
    (e.g. the run folder not created yet) never raises into the caller, since
    JOBS (in-memory) remains the source of truth for the live process."""
    try:
        path = _status_path(job["run_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {k: job.get(k) for k in _STATUS_FIELDS}
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass


def _rebuild_jobs_from_disk():
    """Scan RUNS_DIR for status.json files and rebuild JOBS from them (called once
    at import). A job found in "running" state has no live process behind it (the
    server that ran it is gone, this is a fresh process start), so it is rewritten
    as "interrupted", a new terminal status, both in memory and back to its
    status.json. Also removes orphaned staging dirs (the ingest_<run_id>_ prefix in
    the system temp dir) for any run that is not running, and applies the existing
    _auto_clear / _clear_system_draft cleanup for whatever an interrupted run left
    behind in input/context/."""
    import tempfile as _tempfile

    jobs = []
    interrupted_any = False
    if RUNS_DIR.is_dir():
        for run_dir in sorted(RUNS_DIR.iterdir()):
            if not run_dir.is_dir():
                continue
            sp = run_dir / "status.json"
            if not sp.exists():
                continue
            try:
                record = json.loads(sp.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            job = {k: record.get(k) for k in _STATUS_FIELDS}
            job.setdefault("run_id", run_dir.name)
            if job.get("status") == "running":
                job["status"] = "interrupted"
                job["error"] = job.get("error") or "server restarted while this run was in progress"
                job["completed_at"] = job.get("completed_at") or _now_iso()
                _write_status(job)
                interrupted_any = True
            jobs.append(job)

    with JOBS_LOCK:
        JOBS.clear()
        JOBS.extend(jobs)
        running_ids = {j["run_id"] for j in JOBS if j["status"] == "running"}

    # Orphaned staging dirs: any ingest_<run_id>_* temp dir whose run is not
    # currently running (there is no currently-running job right after a fresh
    # import, but a run_id could still legitimately be "queued" with staged
    # uploads awaiting the worker thread -- those are NOT orphans and are left
    # alone; only dirs whose run_id is absent from JOBS entirely, or terminal,
    # are removed).
    tmp_root = Path(_tempfile.gettempdir())
    try:
        entries = list(tmp_root.iterdir())
    except OSError:
        entries = []
    known_run_ids = {j["run_id"] for j in jobs}
    for p in entries:
        if not p.is_dir() or not p.name.startswith("ingest_"):
            continue
        # ingest_<run_id>_<random>: run_id itself contains "__", so split on the
        # trailing "_<random>" suffix mkdtemp appended is unsafe; instead check
        # membership by prefix against every known non-running run_id.
        rid = next((r for r in known_run_ids if p.name.startswith(f"ingest_{r}_")), None)
        if rid is not None and rid in running_ids:
            continue  # a genuinely running job's staging dir (not possible at
                       # fresh import, kept for safety if this is ever re-run).
        if rid is None:
            continue  # not a recognizable job staging dir; leave it alone.
        shutil.rmtree(p, ignore_errors=True)

    if interrupted_any:
        _auto_clear()
        _clear_system_draft()


def _progress_string(line):
    """Return the `key=value ...` body of a pipeline `[progress]` line, or None for any
    other line. Stored on the job and returned by GET /status."""
    s = line.strip()
    if s.startswith("[progress]"):
        return s[len("[progress]"):].strip()
    return None


def _start_next_job():
    """Start the next queued job IF nothing is currently running. Called after every
    submission and after every run finishes, so the queue drains one job at a time.

    Picking the job and flipping it to 'running' happens under the lock; the actual
    work runs in a separate background thread so the HTTP request that triggered this
    returns immediately."""
    with JOBS_LOCK:
        if any(j["status"] == "running" for j in JOBS):
            return  # one at a time: a job is already running, leave the rest queued.
        nxt = next((j for j in JOBS if j["status"] == "queued"), None)
        if nxt is None:
            return  # nothing waiting.
        nxt["status"] = "running"
        nxt["started_at"] = _now_iso()
        run_id = nxt["run_id"]
        _write_status(nxt)
    # daemon=True so this thread never blocks the server from shutting down.
    threading.Thread(target=_run_job, args=(run_id,), daemon=True).start()


def _auto_clear():
    """Remove the ingested files placed in input/context/ for the run that just
    finished.

    Auto-clear prevents stale ingested cases from leaking into the next run. The sidecar
    is the manifest: ONLY files it names are removed, plus the sidecar itself. The
    operator's own context files (anything not listed in the sidecar) are never
    touched. A missing or unreadable sidecar means nothing to clear."""
    sidecar = CONTEXT_DIR / SIDECAR_NAME
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for entry in data.get("cases", []):
        if isinstance(entry, dict):
            fname = entry.get("file")
            if isinstance(fname, str) and fname:
                # Use only the basename, so a crafted "file" can never point outside
                # input/context/ (defense against path traversal).
                target = CONTEXT_DIR / Path(fname).name
                try:
                    target.unlink()
                except OSError:
                    pass  # already gone or not a file: nothing to do.
    try:
        sidecar.unlink()
    except OSError:
        pass


def _clear_system_draft():
    """Remove a SYSTEM-generated draft memo and its manifest so a draft job's artifacts
    do not leak into the next job (the server is stateless per job). Delegates to the
    canonical role_resolution.clear_system_draft so the rule lives in one place."""
    import role_resolution
    role_resolution.clear_system_draft(CONTEXT_DIR)


def _run_job(run_id):
    """The background worker for one job. Runs on its own thread (see
    _start_next_job). Steps: place this job's validated files into input/context/,
    run the pipeline as a subprocess writing to output/runs/<run_id>/, record the
    outcome, auto-clear, then start the next queued job.

    api STEP B2: registers the subprocess in _PROCS the moment it starts (so a
    concurrent POST /runs/{run_id}/cancel can find and terminate it) and
    checks _CANCELLED after the subprocess exits, to record "cancelled" as
    its own status rather than folding a deliberate stop into "failed"."""
    out_dir = RUNS_DIR / run_id
    error = None
    exit_code = None
    cancel_event = threading.Event()
    with JOBS_LOCK:
        _CANCELLED[run_id] = cancel_event
        job = _find_job(run_id)
        task = (job or {}).get("task") or "review"
        question = (job or {}).get("question") or ""
        job_sensitive = (job or {}).get("sensitive")
        if job_sensitive is None:
            job_sensitive = SENSITIVE
        # api STEP A1: resolved at submit time and stored on the job, so a job
        # queued under one profile keeps the mode it was accepted with even if
        # the environment changes before the worker picks it up.
        job_review_mode = (job or {}).get("review_mode") or _default_review_mode()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)

        # Place this job's files into input/context/ at RUN START (not at submit
        # time), so that while one job runs, a second queued job's files are not
        # sitting in input/context/ corrupting the first. The files were validated
        # and staged at submit time; here we just copy them in.
        with JOBS_LOCK:
            staging = _STAGING.get(run_id)
        if staging and Path(staging).is_dir():
            for p in sorted(Path(staging).iterdir()):
                if p.is_file():
                    shutil.copy2(p, CONTEXT_DIR / p.name)

        # Run the existing pipeline as a SEPARATE program. We use sys.executable (the
        # same Python running this server). The flags come from the resolved CONFIG:
        #   --output-dir   : pin the run folder so we know exactly where results land.
        #   --mode MODE    : SHIMMER_MODE (default integrated). integrated activates the
        #       M1 promotion exclusion (grounding cases stay out of the operational review).
        #   --max-concurrent-docs MAX_DOCS : SHIMMER_MAX_DOCS (default 4). 4 is safe for a
        #       single-key Claude rate limit; raise it if your limits allow.
        #   --task TASK    : this job's task (review default, or draft). For draft we also
        #       pass --question; phase 0 generates a memo and reviews it.
        #   --review-mode MODE : this job's review mode (api STEP A1). Always passed
        #       explicitly, never left to the pipeline's own default, so the mode the
        #       caller was told they got (in the /submit response and in status.json)
        #       is provably the mode the child ran.
        #   --non-interactive --skip-confirmation : never wait for a human at the prompt.
        # When the run is NOT sensitive (SHIMMER_SENSITIVE=false, the default) we also pass:
        #   --sensitivity-layer-inactive-override : the full LAW-IV outbound masking layer
        #       ships built but INACTIVE (INFRA-038); the pipeline hard-stops rather than
        #       start silently with it off, so we declare the run non-sensitive (logged to
        #       the governance ledger).
        #   --no-redaction-override : declare the run redact-nothing (no Stage-3a scrub).
        # A sensitive run (SHIMMER_SENSITIVE=true) passes NEITHER override, so redaction
        # runs; that path requires the operator to have activated the LAW-IV layer.
        argv = [sys.executable, "-X", "utf8", str(PIPELINE),
                "--output-dir", str(out_dir),
                "--mode", MODE,
                "--task", task,
                "--max-concurrent-docs", str(MAX_DOCS),
                "--non-interactive", "--skip-confirmation",
                # productization STEP 6: file-backed operator channel. A governed
                # decision (model-gate stop, constitution amendment) that would
                # otherwise deny/stop unconditionally under --non-interactive now
                # parks as <run>/audit/pending_approval.json and waits for a human
                # to answer via POST /approvals/{run_id} (see GET /approvals).
                "--operator-channel", "file",
                "--review-mode", job_review_mode]
        if question:
            # R6: a review run may carry an optional framing question too (folded
            # into every agent's run objectives and echoed in the deliverables);
            # draft still requires one (validated in submit).
            argv += ["--question", question]
        _bp = os.environ.get("SHIMMER_BACKEND_PROFILE")
        if _bp:
            argv += ["--backend-profile", _bp]
        if not job_sensitive:
            argv += ["--sensitivity-layer-inactive-override", "--no-redaction-override"]
        # Stream the merged output so the latest [progress] line can be stored on the job
        # (returned by GET /status) while the run is in flight. We keep a bounded tail for
        # the failure message, AND (productization STEP 6 item 5) write the complete
        # merged stream to <run>/logs/pipeline_stdout.log as it arrives, so the operator
        # can inspect the full run, not just a 2000-character tail.
        proc = subprocess.Popen(
            argv, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        # api STEP B2: the moment the child exists, register its handle where a
        # concurrent HTTP request can find it. Guarded by JOBS_LOCK, matching
        # every other write to run-scoped shared state in this function.
        with JOBS_LOCK:
            _PROCS[run_id] = proc
        log_dir = out_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "pipeline_stdout.log"
        # productization STEP 3: run timeout. The `for line in proc.stdout` loop
        # below blocks until the child closes stdout (i.e. exits), so a plain
        # proc.wait(timeout=...) placed AFTER that loop would never fire on a
        # genuinely hung child. Instead, a daemon Timer fires termination (then
        # kill) if the run outlives RUN_TIMEOUT_S; this unblocks the read loop
        # by closing the child's stdout, so the loop below exits either way and
        # timed_out is checked afterward to decide the outcome. RUN_TIMEOUT_S=0
        # (default) means no Timer is armed at all: unbounded, prior behavior.
        timed_out = threading.Event()
        timer = None
        eff_timeout = _effective_run_timeout()
        if eff_timeout > 0:
            def _on_timeout():
                timed_out.set()
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
            timer = threading.Timer(eff_timeout, _on_timeout)
            timer.daemon = True
            timer.start()
        try:
            tail = []
            # productization STEP 6 item 5: the full merged stream is appended to
            # <run>/logs/pipeline_stdout.log line by line as it arrives (never
            # buffered fully in memory the way `tail` deliberately is), so a run
            # detail view can link the complete log regardless of outcome.
            with open(log_path, "a", encoding="utf-8", errors="replace") as logf:
                for line in proc.stdout:
                    tail.append(line)
                    if len(tail) > 300:
                        del tail[:100]
                    logf.write(line)
                    logf.flush()
                    prog = _progress_string(line)
                    if prog is not None:
                        with JOBS_LOCK:
                            j = _find_job(run_id)
                            if j is not None:
                                j["progress"] = prog
                                _write_status(j)
            proc.wait()
        finally:
            if timer is not None:
                timer.cancel()
            # api STEP B2: _PROCS' entry is only ever valid while this function
            # is between spawning proc and recording its outcome; remove it as
            # soon as the subprocess has exited (terminal or not) so a cancel
            # request arriving after this point correctly finds nothing to
            # terminate, rather than a handle to an already-dead process.
            with JOBS_LOCK:
                _PROCS.pop(run_id, None)
        if cancel_event.is_set():
            # api STEP B2: a caller asked this run to stop. The subprocess was
            # already terminated/killed by the cancel route (the same
            # sequence _on_timeout uses below); this is a DELIBERATE stop, not
            # a timeout and not an organic non-zero exit, so it must not be
            # reported as either. exit_code is recorded for reference but is
            # not what decides the status below (see the outcome block).
            error = "cancelled by request"
            exit_code = proc.returncode
        elif timed_out.is_set():
            error = f"run timeout after {eff_timeout}s"
            exit_code = None
        else:
            exit_code = proc.returncode
            if proc.returncode != 0:
                error = f"pipeline exited {proc.returncode}: {''.join(tail).strip()[-2000:]}"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    # Record the outcome under the lock. productization STEP 6: a governance
    # outcome (blocked, stopped_model_approval, stopped_redaction_gate,
    # refused_sensitivity_layer_inactive, snapshot_conflict, operator_abort) is
    # a distinct status, not "failed": the pipeline refused or paused ON
    # PURPOSE. A run timeout has no exit_code to map (still "failed", with the
    # timeout reason already in `error`); any other non-zero code not in the
    # map is a plain "failed". api STEP B2: a caller-requested cancel is its
    # OWN status, "cancelled", checked FIRST and never run through
    # _status_for_exit_code: terminate()/kill() leaves an arbitrary returncode
    # (negative on POSIX, platform-defined on Windows) that means nothing
    # under that table and must never be misread as a governance code or a
    # plain failure.
    with JOBS_LOCK:
        job = _find_job(run_id)
        if job is not None:
            if cancel_event.is_set():
                job["status"] = "cancelled"
            elif exit_code is None:
                job["status"] = "failed"
            else:
                job["status"] = _status_for_exit_code(exit_code)
            job["error"] = error
            job["exit_code"] = exit_code
            job["completed_at"] = _now_iso()
            _write_status(job)
        _CANCELLED.pop(run_id, None)

    # Auto-clear the placed ingested files (success OR failure), then drop the staging.
    # SHIMMER_AUTO_CLEAR=false leaves the placed files in input/context/ for inspection.
    if AUTO_CLEAR:
        _auto_clear()
        _clear_system_draft()
    with JOBS_LOCK:
        staging = _STAGING.pop(run_id, None)
    if staging:
        shutil.rmtree(staging, ignore_errors=True)

    # Pick up the next queued job, if any.
    _start_next_job()


# ---------------------------------------------------------------------------
# api STEP A1: reading the STRUCTURED review back off a finished run.
#
# /results ships a zip of markdown and .docx: the right thing for a person, the
# wrong thing for a consumer program, which then has to parse prose to find out
# what the review actually decided. The three helpers below read the run's own
# artifacts and return the TYPED records instead:
#
#   the Finding records   live on the append-only message bus
#                         (<run>/logs/agent_bus.jsonl), inside the canonical
#                         envelope's items[] (INFRA-037). finding_record.is_finding
#                         decides what is one; nothing here re-implements that test.
#   the pairing map       lives at <run>/audit/pairing_map.json, one object per
#                         document, written at phase 5.5 before any judging.
#   the live counters     come from the pairing map (pairs planned) and from
#                         <run>/logs/cost_tracker.jsonl (one line per model call),
#                         both of which grow while the run is in flight, so a
#                         poller sees the review progressing rather than a
#                         binary queued/completed.
#
# All three read off DISK rather than out of JOBS, for the same reason
# _pending_approvals does: the artifacts are written by the pipeline SUBPROCESS,
# a different process from this server.
# ---------------------------------------------------------------------------
def _validated_run_dir(run_id):
    """The run folder for a caller-supplied run_id, or HTTPException(404).

    run_id is validated against the server's own mint format FIRST (exactly as
    /status and /results do, _RUN_ID_RE) so a value like "../.." is rejected
    before it is ever used in a path expression. A well-formed id with no run
    folder is the same 404: a caller learns only "not found" either way."""
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=404, detail="run_id not found")
    run_dir = RUNS_DIR / run_id
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail="run_id not found")
    return run_dir


def _project_finding(item, *, agent, doc_id):
    """One Finding record as a flat, stable API object.

    Field names are the Finding record's own (finding_record's module docstring),
    with two fallbacks for records minted before those names settled: `claim_id`
    stands in for `rule_id`, and `ref_ids` for `source_refs`. Both appear on real
    bus traffic, so reading only the canonical name would silently drop findings."""
    refs = item.get("source_refs")
    if not isinstance(refs, list):
        refs = item.get("ref_ids") if isinstance(item.get("ref_ids"), list) else []
    return {
        "agent": agent,
        "doc_id": doc_id,
        "item_id": item.get("item_id"),
        "revision": item.get("revision"),
        "rule_id": item.get("rule_id") or item.get("claim_id") or "",
        "source_rule_id": item.get("source_rule_id") or "",
        "unit_id": item.get("unit_id") or "",
        "relation": item.get("relation"),
        "record_verdict": item.get("record_verdict"),
        "value_a": item.get("value_a"),
        "unit_a": item.get("unit_a"),
        "value_b": item.get("value_b"),
        "unit_b": item.get("unit_b"),
        "source_refs": [str(r) for r in refs],
        "explanation": item.get("explanation") or "",
        # R6 / INFRA-044: the optional comparison fields of a prior-version record.
        "field_label": item.get("field_label") or "",
        "delta": item.get("delta"),
        "band_distance_change": item.get("band_distance_change"),
        "provenance": item.get("provenance") or "",
    }


def _bus_findings(run_dir):
    """Every Finding record on this run's bus, superseded revisions removed.

    INFRA-037: a higher `revision` for the same `item_id` supersedes the earlier
    one, which is how the verifiability gate downgrades an ungrounded finding
    (it appends revision+1 rather than editing the append-only bus). Returning
    both revisions would report a finding that the run has already withdrawn, so
    the last-highest revision per item_id wins and a record with no item_id is
    kept as-is (there is nothing to supersede it by). Order is bus order, which
    is chronological."""
    import finding_record as _fr

    bus = run_dir / "logs" / "agent_bus.jsonl"
    if not bus.is_file():
        return []
    out, by_item = [], {}
    try:
        lines = bus.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue  # a partially written last line while the run is live.
        body = msg.get("body")
        payload = body.get("payload") if isinstance(body, dict) else None
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            continue
        agent = payload.get("agent") or msg.get("sender") or ""
        doc_id = payload.get("doc_id") or ""
        for item in items:
            if not _fr.is_finding(item):
                continue
            record = _project_finding(item, agent=agent, doc_id=doc_id)
            key = record["item_id"]
            if not key:
                out.append(record)
                continue
            prior = by_item.get(key)
            if prior is not None:
                prior_rev = prior["revision"] if isinstance(prior["revision"], int) else -1
                this_rev = record["revision"] if isinstance(record["revision"], int) else -1
                if this_rev < prior_rev:
                    continue
                out[out.index(prior)] = record
                by_item[key] = record
                continue
            by_item[key] = record
            out.append(record)
    return out


def _pairing_map(run_dir):
    """This run's pairing map as written, keyed by document id, or {}."""
    path = run_dir / "audit" / "pairing_map.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _pairs_view(pairing):
    """One document's pairing map with every document-derived string removed.

    Kept: the counts, the unit ids, the rule ids, and the REASON each rule was
    paired, rejected or left undecided (the reason is the whole point of the map:
    it is the record of why a rule was or was not applied).

    Dropped: `title` (the unit's own heading, lifted verbatim from the document),
    `fields_present` and `field_vocabulary` (the document's own field labels).
    `missing_field_findings` is reduced to a count, because those are Finding
    records and /findings is where Finding records are served; shipping them in
    a second shape here would be two answers to one question."""
    units = []
    for entry in pairing.get("units") or []:
        units.append({
            "unit_id": entry.get("unit_id"),
            "kind": entry.get("kind"),
            "paired": [{"rule_id": p.get("rule_id"), "reason": p.get("reason")}
                       for p in entry.get("paired") or []],
            "rejected": [{"rule_id": p.get("rule_id"), "reason": p.get("reason")}
                         for p in entry.get("rejected") or []],
            "undecided": list(entry.get("undecided") or []),
            # R6: integers only; the labels and reasons carry document text.
            "prior_hit_count": int((entry.get("prior_comparisons") or {}).get("hit_count") or 0),
            "prior_check_count": len((entry.get("prior_comparisons") or {}).get("checks") or []),
            "prior_refused_count": len((entry.get("prior_comparisons") or {}).get("refused") or []),
        })
    return {
        "document_id": pairing.get("document_id"),
        "unit_count": pairing.get("unit_count"),
        "rule_count": pairing.get("rule_count"),
        "pair_count": pairing.get("pair_count"),
        "rejected_count": pairing.get("rejected_count"),
        "undecided_count": pairing.get("undecided_count"),
        "unmatched_units": list(pairing.get("unmatched_units") or []),
        "missing_field_finding_count": len(pairing.get("missing_field_findings") or []),
        "units": units,
    }


# The pipeline phase that runs the convention review. A cost_tracker line
# carrying this phase is a judging call; anything else is another phase's work.
_REVIEW_PHASE = "5.5"


def _model_call_counts(run_dir):
    """(total model calls, calls made in the review phase) from cost_tracker.jsonl.

    One line per call, appended as the run proceeds, so both numbers are live."""
    path = run_dir / "logs" / "cost_tracker.jsonl"
    if not path.is_file():
        return 0, 0
    total, in_phase = 0, 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0, 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        total += 1
        if str(record.get("phase") or "") == _REVIEW_PHASE:
            in_phase += 1
    return total, in_phase


def _review_progress(run_dir, review_mode):
    """The three counters GET /status adds, derived from the run's own artifacts.

      pairs_planned          every (unit, rule) pair the map decided could apply,
                             summed over the run's documents.
      model_calls            model calls made so far, all phases.
      pairs_arithmetic_only  pairs the run settled without asking a model, i.e.
                             planned pairs minus judging calls. This is meaningful
                             ONLY in paired mode, where a call is made per pair
                             that Python could not settle; in wide mode a phase-5.5
                             call is a whole-document review and subtracting it
                             from a pair count would be arithmetic on unlike
                             things, so it is reported as null rather than as a
                             number that looks true and is not."""
    planned = 0
    for pairing in _pairing_map(run_dir).values():
        if isinstance(pairing, dict) and isinstance(pairing.get("pair_count"), int):
            planned += pairing["pair_count"]
    total_calls, phase_calls = _model_call_counts(run_dir)
    arithmetic_only = None
    if review_mode == "paired":
        arithmetic_only = max(0, planned - phase_calls)
    return {"pairs_planned": planned,
            "pairs_arithmetic_only": arithmetic_only,
            "model_calls": total_calls}


# ---------------------------------------------------------------------------
# api STEP B1: the run resource. GET /runs/{run_id} and GET /runs report ONE
# object per run (_run_record), replacing the separate, thinner shapes GET
# /status/{run_id} and GET /queue used to return. GET /status and GET /queue
# stay in place unchanged for this step (cancellation, approval-answering and
# deliverables are the next steps; nothing about those routes changes here).
#
# The new object adds three things the old "status" string alone could not
# say at once: a closed-set `state` (queued / running / awaiting_approval /
# stopped / cancelled) that a caller's switch can be exhaustive over; an
# `outcome` (succeeded / governance_stop / crashed / timed_out) that is
# populated only once `state` is "stopped", so a governance halt is never
# reported the same way as a crash; and `pending_approval`, the full pending
# question (not just its existence), read off the SAME pending_approval.json
# _pending_approvals() already reads, so GET /runs/{run_id} never needs a
# second call to GET /approvals to explain why a run is stalled.
# ---------------------------------------------------------------------------
def _pending_approval_for(run_dir):
    """The pending governed question for ONE run, or None. Same file-reading
    rule as _pending_approvals() below (which this now delegates to): a
    pending_approval.json with no approval_decision.json yet means a human has
    not answered. Adds `message` (split out of `payload`, since payload may or
    may not carry one depending on the topic; message is what a person reads,
    payload is what a program reads, kept as separate fields rather than
    mixed, per the human/machine constraint) and `default_on_timeout` /
    `timeout_at`, computed from SHIMMER_APPROVAL_WAIT_S, the same environment
    variable the pipeline subprocess's file-operator handler already reads for
    this exact wait (server.py's own docstring table, SHIMMER_APPROVAL_WAIT_S
    row); the pipeline's handler unconditionally defaults to DEFERRED on
    timeout regardless of topic, so default_on_timeout is always that literal
    string, stated rather than left for a caller to infer from source."""
    pending_path = run_dir / "audit" / "pending_approval.json"
    decision_path = run_dir / "audit" / "approval_decision.json"
    if not pending_path.exists() or decision_path.exists():
        return None
    try:
        record = json.loads(pending_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    asked_at = record.get("asked_at")
    timeout_at = None
    if isinstance(asked_at, str):
        try:
            asked_dt = datetime.fromisoformat(asked_at)
            wait_s = _env_int("SHIMMER_APPROVAL_WAIT_S", 3600)
            timeout_at = (asked_dt + timedelta(seconds=wait_s)).isoformat()
        except ValueError:
            timeout_at = None
    return {
        "topic": record.get("topic"),
        "message": payload.get("message") if isinstance(payload.get("message"), str) else "",
        "payload": payload,
        "asked_at": asked_at,
        "default_on_timeout": "DEFERRED",
        "timeout_at": timeout_at,
    }


# Terminal `status` strings whose outcome is "governance_stop": the pipeline
# stopped itself ON PURPOSE. Identical set to GOVERNANCE_STATUSES above; kept
# as a separate name so a reader of _outcome_for_status does not have to trace
# back to the exit-code table to see which statuses land here.
_GOVERNANCE_OUTCOME_STATUSES = GOVERNANCE_STATUSES
# Terminal `status` strings whose outcome is "crashed" rather than a
# governance stop or a timeout. snapshot_conflict and operator_abort are
# distinct governance-adjacent outcomes upstream (see _EXIT_STATUS_MAP's own
# comment) but neither is a rule refusing on purpose mid-review the way the
# four GOVERNANCE_STATUSES are, and neither is "succeeded"; "crashed" is the
# nearest of the four `outcome` values and is recorded here explicitly rather
# than left to a catch-all, so the mapping is auditable in one place.
# "interrupted" (a server restart mid-run, STEP 2) is not a pipeline decision
# at all; it is mapped here too, to "crashed", for the same reason: there is
# no fifth `outcome` value for "the server died", and "crashed" is the
# closest true statement ("something other than success and other than a
# rule happened").
_CRASHED_OUTCOME_STATUSES = {"failed", "snapshot_conflict", "operator_abort", "interrupted"}


def _outcome_for_status(status, exit_code):
    """(outcome, stop_reason) for a TERMINAL `status` string. Only called once
    `state` has already been decided to be "stopped" (see _run_record); never
    called for "queued", "running" or "awaiting_approval"."""
    if status == "completed":
        return "succeeded", None
    if status in _GOVERNANCE_OUTCOME_STATUSES:
        return "governance_stop", {"code": status, "detail": None}
    if status == "failed" and exit_code is None:
        # _run_job never observes an exit_code on a run-timeout path (the
        # subprocess is terminated/killed by the Timer, not waited on for a
        # code); exit_code is None is exactly and only that path today.
        return "timed_out", {"code": "run_timeout", "detail": None}
    if status in _CRASHED_OUTCOME_STATUSES:
        return "crashed", {"code": status, "detail": None}
    # Unrecognised status string (should not happen; every writer of
    # job["status"] uses one of the names above or _status_for_exit_code's
    # own table). Reported as crashed rather than raising, since a status
    # route must never itself throw on an unexpected but real job record.
    return "crashed", {"code": status, "detail": None}


def _state_for_job(job, run_dir):
    """The closed-set `state` for one job: queued / running /
    awaiting_approval / stopped / cancelled. api STEP B2: POST
    /runs/{run_id}/cancel is the sole writer of job["status"] = "cancelled",
    for both a queued job (never started) and a running one (subprocess
    terminated)."""
    status = job.get("status")
    if status == "queued":
        return "queued"
    if status == "cancelled":
        return "cancelled"
    if status == "running":
        if _pending_approval_for(run_dir) is not None:
            return "awaiting_approval"
        return "running"
    return "stopped"


def _documents_for_run(run_dir):
    """One entry per document the pairing map knows about, each with its own
    status (not_started / in_progress / done) and deliverables_path (non-null
    once BP-16's deliverables/<doc_id>/ exists and holds at least one file).
    A run with no pairing map yet (nothing has reached phase 5.5) returns an
    empty list, not an error: "no documents yet" and "unknown run" are
    different answers, matching the empty-but-200 convention every other
    run-scoped read on this surface already uses."""
    out = []
    deliv_root = run_dir / "deliverables"
    for pairing in _pairing_map(run_dir).values():
        if not isinstance(pairing, dict):
            continue
        doc_id = pairing.get("document_id")
        if not doc_id:
            continue
        doc_dir = deliv_root / doc_id
        done = doc_dir.is_dir() and any(p.is_file() for p in doc_dir.rglob("*"))
        out.append({
            "doc_id": doc_id,
            "status": "done" if done else "in_progress",
            "deliverables_path": f"{doc_id}/" if done else None,
        })
    return out


def _run_record(job, run_dir):
    """The complete run-resource object GET /runs/{run_id} and GET /runs
    return: everything decision one requires in one place, so a caller never
    needs a second call to understand a run's state, why it stopped (if it
    stopped), which documents are done, or what a pending approval is asking.

    api STEP B2: `state == "cancelled"` gets its own `outcome`, "cancelled" --
    a fifth value alongside the four stage-one defined (succeeded /
    governance_stop / crashed / timed_out). It is deliberately not folded
    into "crashed": a caller who asked for the stop must be able to tell
    that apart from one it did not ask for, and "succeeded" would be an
    outright false claim. `stop_reason` for a cancelled run names whether it
    was cancelled while queued (never started) or while running (subprocess
    terminated); `documents` on the same object shows whatever partial
    output the run produced before the stop -- cancelling deletes nothing on
    disk, it only stops further work, so the response says what survives
    rather than the caller having to guess."""
    state = _state_for_job(job, run_dir)
    outcome = None
    stop_reason = None
    if state == "stopped":
        outcome, stop_reason = _outcome_for_status(job.get("status"), job.get("exit_code"))
        if stop_reason is not None and stop_reason.get("detail") is None:
            stop_reason = dict(stop_reason, detail=job.get("error"))
    elif state == "cancelled":
        outcome = "cancelled"
        stop_reason = {"code": "cancelled",
                       "detail": job.get("error") or "cancelled by request"}
    record = {k: job.get(k) for k in _STATUS_FIELDS}
    record["state"] = state
    record["outcome"] = outcome
    record["stop_reason"] = stop_reason
    record["pending_approval"] = (_pending_approval_for(run_dir)
                                  if state == "awaiting_approval" else None)
    record["documents"] = _documents_for_run(run_dir)
    record["log_url"] = f"/runs/{job['run_id']}/log"
    record.update(_review_progress(run_dir, job.get("review_mode")))
    return record


# ---------------------------------------------------------------------------
# ROUTES (the URLs the server answers). All are token-gated via verify_token.
# ---------------------------------------------------------------------------
@app.post("/submit", status_code=202, dependencies=[Depends(verify_token)])
async def submit(files: List[UploadFile] = File(default=None),
                 task: Optional[str] = Form(default=None),
                 question: Optional[str] = Form(default=None),
                 sensitive: Optional[str] = Form(default=None),
                 review_mode: Optional[str] = Form(default=None)):
    """Accept a review or draft job.

    Multipart fields:
      - files:     the .md case files plus the _corpus_ingest.json sidecar. Required
                   for task=review; optional for task=draft (grounding may already sit
                   in input/context/, or be uploaded alongside the question).
      - task:      "review" (default, or SHIMMER_TASK) or "draft".
      - question:  the memo question/brief for task=draft (required there), or an
                   optional framing question for task=review (R6), forwarded to the
                   pipeline for either task, folded into every agent's run objectives
                   and echoed in the deliverables; never parsed by the code.
      - sensitive: (productization STEP 6 item 3) "true" or "false"; per-submission
                   privacy posture, defaulting to SHIMMER_SENSITIVE when omitted. false
                   (the common case) sends document text to cloud providers and waives
                   redaction for THIS run. true keeps redaction on, which today means
                   the run refuses to start (exit 6) because the LAW-IV masking layer
                   ships inactive; see the console's explanation text. The two override
                   flags (--sensitivity-layer-inactive-override, --no-redaction-override)
                   are appended in _run_job only when this job's resolved value is false,
                   exactly as the old blanket SHIMMER_SENSITIVE check did.
      - review_mode: (api STEP A1) "paired" or "wide". Omitted, it resolves the way
                   the pipeline resolves it with no --review-mode flag: paired under
                   the local backend profile, wide under cloud. Unlike `task`, an
                   unrecognised value is REJECTED with 400 rather than silently
                   falling back: the two modes differ by roughly an order of
                   magnitude in model calls, so quietly turning a typo'd "pared"
                   into a wide cloud run would spend the operator's money on a
                   mode they did not ask for.

    We write any uploads to a private temp dir, validate them against the corpus
    ingestion contract (when present), then queue the job. Files move into
    input/context/ only when the job starts (see _run_job)."""
    import tempfile  # local import: only /submit needs it.

    job_sensitive = SENSITIVE if sensitive is None else (
        sensitive.strip().lower() in {"1", "true", "yes", "y", "on"})

    task = (task or TASK_DEFAULT).strip().lower()
    if task not in ("review", "draft"):
        task = "review"

    if review_mode is None or not review_mode.strip():
        job_review_mode = _default_review_mode()
    else:
        job_review_mode = review_mode.strip().lower()
        if job_review_mode not in REVIEW_MODES:
            raise HTTPException(
                status_code=400,
                detail=f"review_mode must be one of {list(REVIEW_MODES)}, got {review_mode!r}")

    question = (question or "").strip()
    uploads = files or []
    if task == "draft" and not question:
        raise HTTPException(status_code=400, detail="task=draft requires a 'question' field")
    if task == "review" and not uploads:
        raise HTTPException(status_code=400, detail="task=review requires at least one uploaded file")

    # productization STEP 3: reject an oversized/over-count submission BEFORE any
    # staging directory or file is created, per file-count first (cheapest check).
    if len(uploads) > MAX_UPLOAD_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"too many files: {len(uploads)} > SHIMMER_MAX_UPLOAD_FILES ({MAX_UPLOAD_FILES})")

    run_id = _new_run_id()
    staging = Path(tempfile.mkdtemp(prefix=f"ingest_{run_id}_"))
    try:
        names = []
        total_bytes = 0
        max_file_bytes = MAX_UPLOAD_MB * 1024 * 1024
        max_total_bytes = MAX_UPLOAD_TOTAL_MB * 1024 * 1024
        for uf in uploads:
            data = await uf.read()
            if len(data) > max_file_bytes:
                shutil.rmtree(staging, ignore_errors=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"file {uf.filename!r} is {len(data)} bytes, over the "
                           f"SHIMMER_MAX_UPLOAD_MB ({MAX_UPLOAD_MB} MB) per-file cap")
            total_bytes += len(data)
            if total_bytes > max_total_bytes:
                shutil.rmtree(staging, ignore_errors=True)
                raise HTTPException(
                    status_code=400,
                    detail=f"submission exceeds SHIMMER_MAX_UPLOAD_TOTAL_MB "
                           f"({MAX_UPLOAD_TOTAL_MB} MB)")
            # Path(...).name strips any directory part from the client filename, so a
            # malicious name like "../../x" cannot escape the staging directory.
            dest = staging / Path(uf.filename).name
            dest.write_bytes(data)
            names.append(dest.name)

        # Validate the staged bundle ONLY when files were uploaded (a draft with no
        # files has nothing to validate; its grounding already sits in input/context/).
        if names:
            proc = subprocess.run(
                [sys.executable, "-X", "utf8", str(VALIDATOR), "--target", str(staging)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0:
                # Reject: clean up the staging directory and return the violation report.
                shutil.rmtree(staging, ignore_errors=True)
                raise HTTPException(
                    status_code=400,
                    detail={"error": "contract validation failed",
                            "report": (proc.stdout or "") + (proc.stderr or "")},
                )
    except HTTPException:
        raise  # already a clean 400, re-raise as-is.
    except Exception as e:
        shutil.rmtree(staging, ignore_errors=True)
        raise HTTPException(status_code=400, detail=f"could not accept upload: {e}")

    # Validation passed: register the staging dir and queue the job.
    with JOBS_LOCK:
        _STAGING[run_id] = staging
        new_job = {
            "run_id": run_id,
            "status": "queued",
            "task": task,
            "question": question,
            "sensitive": job_sensitive,
            "review_mode": job_review_mode,
            "progress": None,
            "submitted_at": _now_iso(),
            "started_at": None,
            "completed_at": None,
            "exit_code": None,
            "error": None,
            "files": names,
        }
        JOBS.append(new_job)
        _write_status(new_job)
    _start_next_job()
    return {"run_id": run_id, "status": "queued", "task": task, "sensitive": job_sensitive,
            "review_mode": job_review_mode, "files": names}


@app.get("/status/{run_id}", dependencies=[Depends(verify_token)])
async def status(run_id: str):
    """Return one job's record (status, timestamps, error if any). 404 if unknown.

    productization STEP 3: run_id is validated against the server's own mint
    format (_RUN_ID_RE) BEFORE any lookup, so a value like "../.." or any other
    unexpected shape is rejected with 404 up front rather than reaching the
    in-memory search (which is safe here since _find_job never builds a path
    from run_id, but every route accepting a run_id validates the same way for
    consistency, and /results does build a path from it).

    api STEP A1: the record now also carries three live counters (see
    _review_progress) alongside `review_mode`, so a poller can watch the review
    itself advance instead of only its queued/running/completed status. They are
    derived from the run folder on every call rather than stored on the job,
    because the pipeline SUBPROCESS is what writes the artifacts they come from.
    A run folder that does not exist yet yields zeroes, never an error."""
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=404, detail="run_id not found")
    with JOBS_LOCK:
        job = _find_job(run_id)
        if job is None:
            raise HTTPException(status_code=404, detail="run_id not found")
        record = dict(job)  # a copy, so the caller cannot mutate our record.
    record.update(_review_progress(RUNS_DIR / run_id, record.get("review_mode")))
    return record


@app.get("/runs/{run_id}", dependencies=[Depends(verify_token)])
async def run_detail(run_id: str):
    """api STEP B1: the complete run resource, merging what GET /status and one
    entry of GET /queue used to answer separately into one object (see
    _run_record's own docstring for the field-by-field reasoning). Same
    run_id validation and the same 404 behavior as GET /status: a malformed
    id or an unknown one is 404 either way, so a caller learns nothing about
    which case it was.

    GET /status/{run_id} is unchanged and still answers alongside this route;
    nothing about it is removed in this step."""
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=404, detail="run_id not found")
    with JOBS_LOCK:
        job = _find_job(run_id)
        if job is None:
            raise HTTPException(status_code=404, detail="run_id not found")
        job = dict(job)  # a copy, so the caller cannot mutate our record.
    return _run_record(job, RUNS_DIR / run_id)


# api STEP B2: how long POST /cancel waits for a RUNNING job's terminal write
# before answering, so the response reflects what actually happened rather
# than a promise. terminate() is normally fast; this is a ceiling, not an
# expected wait, and mirrors the 10s grace period _on_timeout already gives
# proc.wait() before escalating to kill().
_CANCEL_WAIT_S = 10.0


@app.post("/runs/{run_id}/cancel", dependencies=[Depends(verify_token)])
async def cancel_run(run_id: str):
    """api STEP B2: stop a run. A queued job is removed from the queue before
    it ever starts (no subprocess exists yet); a running job's subprocess is
    terminated (then killed, mirroring the existing run-timeout sequence).
    Both land on job["status"] = "cancelled", the sole writer of that status.
    A run already in a terminal state (stopped, or already cancelled) is
    refused with 409 and a reason naming its actual state, rather than a
    silent no-op: the caller asked for a state change that cannot happen,
    and is told so rather than left to infer it from an unchanged response.
    Deletes nothing on disk; whatever partial output exists stays where it
    is (see the `documents` field of the returned record)."""
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=404, detail="run_id not found")

    with JOBS_LOCK:
        job = _find_job(run_id)
        if job is None:
            raise HTTPException(status_code=404, detail="run_id not found")
        current_status = job["status"]

        if current_status == "queued":
            # Never started: no subprocess exists, nothing to terminate.
            # Remove its staging dir too, same as a finished run's cleanup.
            job["status"] = "cancelled"
            job["error"] = "cancelled before it started"
            job["completed_at"] = _now_iso()
            _write_status(job)
            staging = _STAGING.pop(run_id, None)
            record = _run_record(dict(job), RUNS_DIR / run_id)
            was_running = False
        elif current_status == "running":
            staging = None
            was_running = True
        else:
            raise HTTPException(
                status_code=409,
                detail=f"run_id {run_id!r} cannot be cancelled: its state is "
                       f"{current_status!r}, not queued or running")

    if not was_running:
        if staging:
            shutil.rmtree(staging, ignore_errors=True)
        # A cancelled QUEUED job never occupied the one-at-a-time slot, so the
        # next queued job (if any) is picked up exactly as it would be after
        # any other terminal transition.
        _start_next_job()
        return record

    # RUNNING: find the registered subprocess handle. A running job's Popen
    # is registered by _run_job the instant it exists (api STEP B2's _PROCS);
    # the only window where "running" and "no _PROCS entry" can both be true
    # is the brief gap between _start_next_job flipping the status and
    # _run_job reaching its own Popen call, so this polls briefly rather than
    # failing on a race that is not a real absence.
    proc = None
    cancel_event = None
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        with JOBS_LOCK:
            proc = _PROCS.get(run_id)
            cancel_event = _CANCELLED.get(run_id)
        if proc is not None and cancel_event is not None:
            break
        time.sleep(0.02)
    if proc is None or cancel_event is None:
        # The run finished (or crashed) in the time it took to look; nothing
        # left to cancel. Report its actual current state rather than a
        # cancellation that did not happen.
        with JOBS_LOCK:
            job = _find_job(run_id)
            job = dict(job) if job is not None else None
        if job is None:
            raise HTTPException(status_code=404, detail="run_id not found")
        raise HTTPException(
            status_code=409,
            detail=f"run_id {run_id!r} finished before the cancel request reached it; "
                   f"its state is now {job.get('status')!r}")

    cancel_event.set()
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

    # Wait (bounded) for _run_job's own thread to finish writing the terminal
    # status, so the response reflects what happened rather than a promise.
    deadline = time.monotonic() + _CANCEL_WAIT_S
    while time.monotonic() < deadline:
        with JOBS_LOCK:
            job = _find_job(run_id)
            status_now = job.get("status") if job is not None else None
        if status_now not in ("running", "queued"):
            break
        time.sleep(0.02)

    with JOBS_LOCK:
        job = _find_job(run_id)
        job = dict(job) if job is not None else None
    if job is None:
        raise HTTPException(status_code=404, detail="run_id not found")
    return _run_record(job, RUNS_DIR / run_id)


@app.post("/runs/{run_id}/approval", dependencies=[Depends(verify_token)])
async def answer_approval(run_id: str, body: dict):
    """api STEP B3: record a human's decision on one run's pending governed
    question.

    Body: {"decision": "...", "rationale": "..."}. `decision` is required and
    non-empty; `rationale` is optional. The value of `decision` is written
    through VERBATIM, never validated against a fixed enum here: the code
    that decides whether a decision counts as an approval
    (model_registry.enforce_current_models / constitution_guard._is_approved)
    already exists, is read back by the pipeline SUBPROCESS's own polling
    file-operator handler, and is not duplicated or second-guessed here.

    FIRST GOVERNANCE CONSTRAINT: this route WRITES the decision and nothing
    else. It never imports model_registry or constitution_guard, never calls
    _is_approved, never itself changes a run's state. Whether the run
    actually resumes, and which way the gate went, is decided entirely by
    the pipeline subprocess the next time its poll loop reads this file
    (_make_file_operator_handler, roughly every 2 seconds); this route
    cannot see or wait for that, only write the file the poll loop reads.

    SECOND GOVERNANCE CONSTRAINT: the response says the decision was
    RECORDED, never that it was approved. It carries `recorded: true` and
    `run_state`, the run's state as it stood the instant BEFORE this write
    (deliberately read before, not after: _pending_approval_for reports
    "awaiting_approval" only while approval_decision.json does not yet
    exist, so reading run_state after writing that file would report
    "running" -- correctly, since nothing is pending anymore, but that would
    silently answer a different question than "what was true when the
    caller asked"; the response is about the request that was just made, not
    about a race against the pipeline's next poll) -- never a claim about
    what the decision meant or what happened as a result. A caller that
    wants to see the EFFECT of the decision polls GET /runs/{run_id}
    afterward, exactly as it would for any other state change on this
    surface.

    404 for a malformed run_id, or a well-formed one with no pending
    approval on disk at all. 409 if this exact approval has ALREADY been
    answered: a decision file already sitting beside the pending file means
    a human answered this escalation once already (the pipeline's own
    handler deletes any stale decision file before writing the NEXT
    pending_approval.json for a later escalation, so "both files present"
    is unambiguous: this one was already answered and not yet consumed).
    400 if `decision` is missing or empty."""
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=404, detail="run_id not found")
    run_dir = RUNS_DIR / run_id
    audit_dir = run_dir / "audit"
    pending_path = audit_dir / "pending_approval.json"
    decision_path = audit_dir / "approval_decision.json"
    if not pending_path.exists():
        raise HTTPException(status_code=404, detail="no pending approval for this run_id")
    if decision_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"run_id {run_id!r} already has a recorded decision for this "
                   f"approval; answering the same pending question twice is refused")

    decision = str(body.get("decision", "")).strip()
    rationale = str(body.get("rationale", "")).strip()
    if not decision:
        raise HTTPException(status_code=400, detail="'decision' is required")

    # run_state is read BEFORE the write below, not after: _pending_approval_for
    # (and so _state_for_job) reads "awaiting_approval" precisely because
    # decision_path does not exist yet; the write below is what answers the
    # question, so the state that was TRUE going into this call -- the run was
    # genuinely waiting -- is what the response reports, not a state computed
    # a moment later that the write itself would have already changed.
    with JOBS_LOCK:
        job = _find_job(run_id)
        run_state = _state_for_job(dict(job), run_dir) if job is not None else None

    decided_at = _now_iso()
    record = {"decision": decision, "rationale": rationale, "decided_at": decided_at}
    audit_dir.mkdir(parents=True, exist_ok=True)
    tmp = decision_path.with_suffix(decision_path.suffix + ".tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(decision_path)

    return JSONResponse(status_code=202, content={
        "run_id": run_id,
        "recorded": True,
        "decision": decision,
        "rationale": rationale,
        "decided_at": decided_at,
        "run_state": run_state,
    })


@app.get("/findings/{run_id}", dependencies=[Depends(verify_token)])
async def findings(run_id: str):
    """The run's typed Finding records as JSON: the structured review itself.

    One object per finding, carrying the registry rule id and the OPERATOR's own
    rule id for it, the unit the finding is about, both figures with their units,
    the relation, the record verdict, the REF-*/WEB-REF-* ids it rests on, and the
    human-facing explanation. Superseded revisions are already removed
    (_bus_findings). Same token gate and the same run_id validation as every other
    run-scoped route; an unknown or malformed run_id is 404.

    A run with no findings yet (still early, or genuinely clean) is a 200 with an
    empty list, not a 404: "nothing found" and "no such run" are different answers
    and a poller must be able to tell them apart."""
    run_dir = _validated_run_dir(run_id)
    records = _bus_findings(run_dir)
    return {"run_id": run_id, "count": len(records), "findings": records}


@app.get("/pairs/{run_id}", dependencies=[Depends(verify_token)])
async def pairs(run_id: str):
    """The run's pairing map: which rules could apply to which units, and why.

    One entry per document, each carrying the counts and, per unit, the rules
    paired / rejected / left undecided with the reason recorded for each. Carries
    no document text (see _pairs_view for exactly what is dropped and why). A run
    whose map was never written (a wide-mode run that failed before phase 5.5)
    is a 200 with an empty documents list."""
    run_dir = _validated_run_dir(run_id)
    docs = [_pairs_view(p) for p in _pairing_map(run_dir).values() if isinstance(p, dict)]
    return {"run_id": run_id, "document_count": len(docs), "documents": docs}


@app.get("/queue", dependencies=[Depends(verify_token)])
async def queue():
    """Return every job, oldest submission first. Both the operator and the
    collaborator can see the whole picture: what is queued, what is running, what
    finished or failed."""
    with JOBS_LOCK:
        ordered = sorted(JOBS, key=lambda j: j["submitted_at"])
        return {"jobs": [dict(j) for j in ordered]}


@app.get("/results/{run_id}", dependencies=[Depends(verify_token)])
async def results(run_id: str):
    """Download a completed run's deliverables as a single .zip.

    Deliverables are the final output: the amendments, the summaries, the per-agent
    findings. We return a .zip (rather than JSON) because deliverables include binary
    files (.docx), which do not fit cleanly in JSON. If the run is not completed yet,
    we return 400 so the caller knows to wait.

    productization STEP 3: run_id is validated against the server's own mint
    format (_RUN_ID_RE) BEFORE building run_dir below, so a path-traversal
    attempt like run_id="../.." is rejected with 404 before it is ever used in
    a path expression."""
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=404, detail="run_id not found")
    with JOBS_LOCK:
        job = _find_job(run_id)
        if job is None:
            raise HTTPException(status_code=404, detail="run_id not found")
        if job["status"] != "completed":
            raise HTTPException(status_code=400, detail=f"run not completed (status: {job['status']})")

    run_dir = RUNS_DIR / run_id
    deliv_dir = run_dir / "deliverables"
    # Prefer the deliverables folder; fall back to the whole run tree if it is empty.
    source = deliv_dir if (deliv_dir.is_dir() and any(deliv_dir.iterdir())) else run_dir
    if not source.is_dir():
        raise HTTPException(status_code=404, detail="no output found for this run")

    # Build the zip in memory and stream it back. BP-16: deliverables/ now nests one
    # subfolder per document plus a top-level _run_summary.md; rglob walks the tree
    # recursively and relative_to() preserves the <doc_id>/ subfolders in the zip.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in source.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=str(p.relative_to(source)))
    buf.seek(0)
    return StreamingResponse(
        buf, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{run_id}_deliverables.zip"'},
    )


# ---------------------------------------------------------------------------
# STEP 6: the operator console and its supporting routes.
# ---------------------------------------------------------------------------
@app.get("/console", response_class=HTMLResponse)
async def console():
    """Serve the operator console: one static HTML file, vanilla JavaScript,
    no framework, no build step, no CDN dependency (see scripts/ui/console.html).
    UNGATED like /health, because the browser has no token yet the first time
    it loads this page; the console itself asks for the token before it calls
    any other route.

    CONFLICT NOTE (recorded per CLAUDE.md's "surface conflicts, do not paper
    over them"): the STEP 6 spec's evidence text names this route "GET /".
    Serving it at the bare root collides with an existing, pre-STEP-6 gate
    check (94, productization STEP 3d): "GET /status/../.." is verified by
    every HTTP client (httpx included, RFC 3986 dot-segment removal) into a
    request for literal path "/" BEFORE it is ever sent, client-side, with no
    way for server code to tell the two apart; registering a route at "/"
    would flip that check's first assertion from 404 (no route matched) to
    200 (the console matched), which is check_94 as it always existed, not
    something this step may touch (W2: never weaken, skip, or re-order an
    existing check). Between the spec's literal path and W2 (a repository-wide
    hard rule for every step), W2 wins: the console is served at /console
    instead, still ungated, still reachable with one predictable URL, and
    /status + /results keep exactly their pre-existing traversal behavior
    (proven by check_94, unmodified) with no route ever registered at bare
    "/" to collide with it."""
    if not UI_CONSOLE_PATH.exists():
        raise HTTPException(status_code=500, detail="console.html missing")
    return HTMLResponse(content=UI_CONSOLE_PATH.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    """Unauthenticated liveness probe. Returns a status, this server's declared
    API version (app.version, a plain string constant), and, since api STEP A1,
    the two facts a caller needs BEFORE it can submit anything: which backend
    profile this server is running ("local" or "cloud") and which review mode a
    submission gets when it names none. Both are short enumerated words, not
    environment values: no SHIMMER_ name or value, no path, no hash, no token,
    no upload limit, no output directory, nothing else about configuration.
    Deliberately the one ungated route other than the console shell, for an
    external uptime check that has no token."""
    return JSONResponse({"status": "ok", "version": app.version,
                         "backend_profile": _backend_profile(),
                         "default_review_mode": _default_review_mode()})


@app.get("/runs", dependencies=[Depends(verify_token)])
async def runs():
    """api STEP B1: every run as the complete run-resource object (_run_record),
    oldest submission first. This is the list side of GET /runs/{run_id}: a
    caller reading this route and a caller reading one run's detail parse an
    identical per-run shape, so nothing is lost by reading the list instead of
    polling each run individually. This is a behavior change from before this
    step, when GET /runs returned the same thin shape as GET /queue (still
    true of /queue, unchanged in this step; see that route)."""
    with JOBS_LOCK:
        ordered = [dict(j) for j in sorted(JOBS, key=lambda j: j["submitted_at"])]
    return {"runs": [_run_record(j, RUNS_DIR / j["run_id"]) for j in ordered]}


def _pending_approvals():
    """Scan RUNS_DIR for every run with a pending_approval.json and NO
    approval_decision.json yet (a decision file present means it was already
    answered; _make_file_operator_handler deletes any stale decision file
    before writing a fresh pending_approval.json for the NEXT escalation, so
    "pending with no decision file" is exactly "awaiting a human"). Reads
    directly off disk (not JOBS) since the pending/decision files are written
    by the pipeline SUBPROCESS, a different process than this server."""
    out = []
    if not RUNS_DIR.is_dir():
        return out
    for run_dir in sorted(RUNS_DIR.iterdir()):
        if not run_dir.is_dir():
            continue
        pending_path = run_dir / "audit" / "pending_approval.json"
        decision_path = run_dir / "audit" / "approval_decision.json"
        if not pending_path.exists() or decision_path.exists():
            continue
        try:
            record = json.loads(pending_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({
            "run_id": run_dir.name,
            "topic": record.get("topic"),
            "payload": record.get("payload"),
            "asked_at": record.get("asked_at"),
        })
    return out


@app.get("/approvals", dependencies=[Depends(verify_token)])
async def approvals():
    """Every run currently awaiting a governed decision (see _pending_approvals).
    An empty list is the common case: most runs never hit a governed decision."""
    return {"approvals": _pending_approvals()}


@app.post("/approvals/{run_id}", dependencies=[Depends(verify_token)])
async def decide_approval(run_id: str, body: dict):
    """Record a human's decision on one run's pending governed question.

    Body: {"decision": "APPROVE"|"DENY"|"DEFER"..., "rationale": "..."}. Writes
    <run>/audit/approval_decision.json ATOMICALLY (temp file then replace, the
    same pattern as _write_status) and does nothing else: this route NEVER
    itself evaluates whether the decision is an approval (that stays entirely
    in model_registry.enforce_current_models / constitution_guard._is_approved,
    read back by the pipeline subprocess's file-operator-handler poll loop).
    Gate check (c) proves this by hashing config/ and durable/governance/
    before and after a call here and asserting neither tree changed."""
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=404, detail="run_id not found")
    run_dir = RUNS_DIR / run_id
    audit_dir = run_dir / "audit"
    pending_path = audit_dir / "pending_approval.json"
    if not pending_path.exists():
        raise HTTPException(status_code=404, detail="no pending approval for this run_id")

    decision = str(body.get("decision", "")).strip()
    rationale = str(body.get("rationale", "")).strip()
    if not decision:
        raise HTTPException(status_code=400, detail="'decision' is required")

    record = {"decision": decision, "rationale": rationale, "decided_at": _now_iso()}
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_path = audit_dir / "approval_decision.json"
    tmp = decision_path.with_suffix(decision_path.suffix + ".tmp")
    tmp.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(decision_path)
    return {"run_id": run_id, "decision": decision, "rationale": rationale}


# ---------------------------------------------------------------------------
# STEP 2: rebuild JOBS from disk at IMPORT time (not only when run as __main__),
# so a fresh process (whether started as a server or imported by the gate/tests)
# picks up whatever status.json files a prior process left behind, rewrites any
# "running" job as "interrupted", and clears orphaned staging dirs. This module
# is only ever imported once per process under normal operation.
# ---------------------------------------------------------------------------
_rebuild_jobs_from_disk()


# ---------------------------------------------------------------------------
# STARTUP (only when you run this file directly: python scripts/server.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Refuse to start without a token hash: an open dock would let anyone in.
    if not os.environ.get(TOKEN_HASH_ENV):
        print(
            "Refusing to start: the {env} environment variable is not set.\n"
            "Generate a token and its hash with:\n"
            "  python -c \"import secrets, hashlib; t=secrets.token_hex(32); "
            "print(f'Token (give to the collaborator): {{t}}'); "
            "print(f'Hash (set as {env}): {{hashlib.sha256(t.encode()).hexdigest()}}')\"\n"
            "Then set {env} to the printed hash and start the server again."
            .format(env=TOKEN_HASH_ENV),
            file=sys.stderr,
        )
        sys.exit(1)

    # Refuse to start in local mode if the required models are not available.
    local_ok, local_detail = check_local_model_availability()
    if not local_ok:
        print(
            f"Refusing to start in local mode: {local_detail}.\n"
            f"Install the required packages (pip install torch transformers bitsandbytes "
            f"accelerate) and download the models before starting the server.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Echo the resolved configuration so the operator can confirm every knob at a glance.
    print(_config_summary(), file=sys.stderr)
    print(f"Shimmer front door starting on http://{HOST}:{PORT}", file=sys.stderr)
    print(f"Expose it publicly with:  cloudflared tunnel --url http://localhost:{PORT}",
          file=sys.stderr)
    # HOST 0.0.0.0 means listen on all network interfaces, not just localhost. A public
    # tunnel needs this to forward traffic from the internet to your server.
    uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL)
