"""Single source of truth for per-run output paths (genesis Part XXVII section A).

Every run writes ONLY into its own run-scoped folder:

    output/runs/<UTC-timestamp>__<run-id>/
        deliverables/   per-document deliverables
        logs/           agent_bus.jsonl, cost_tracker.{jsonl,json}, run_summary_*.md
        audit/          reference_index.json, audit_synthesis.md, delta_proposals.json,
                        contract_violations/, run_completion.json, run_identity.json

Two runs never overwrite each other: each gets a distinct folder (timestamp +
random UUID, unique even within the same second). Server folders use the UUID alone;
the persisted identity stays fixed when a CLI folder gains a readable label.
Modeled on durable_paths.py:
every per-run writer derives its path from a RunContext rather than hardcoding an
output/ subpath.

Firewall (INFRA-029/030): the protected DURABLE class lives under durable/ and is
NEVER written here. Per-run cleanup is confined to output/runs/ and is
structurally incapable of reaching durable/ — this module only ever builds paths
under output/runs/, never under durable/ or config/.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_DIRNAME = "output"
RUNS_DIRNAME = "runs"
IDENTITY_FILENAME = "run_identity.json"
# STRUCTURAL: new opaque UUIDs and the legacy server identifiers still in URLs.
SERVER_RUN_ID_RE = re.compile(r"^(?:[0-9a-f]{32}|\d{8}_\d{6}__[0-9a-f]{6})\Z")
_SAFE_RECORDED_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}\Z")

# BP-16: each document's artifacts live in deliverables/<doc_id>/, and the
# filename inside drops the doc-name prefix (the folder already names the
# document). These are the canonical basenames; the writer (amendment_render)
# and the pipeline both read them here so the two cannot drift.
DELIVERABLE_FILENAMES = {
    "context_summary": "grounding_summary.md",
    "operative_summary": "document_summary.md",
    "amendments_json": "review_data.json",
    "amendments_md": "review_findings.md",
    "amendments_docx": "tracked_changes.docx",
    "per_agent_deliverable": "reviewed_document.md",
}
# Top-level index written at deliverables/_run_summary.md (BP-16).
RUN_SUMMARY_NAME = "_run_summary.md"
# In draft mode the generated memo is preserved inside its own subfolder under
# this name (not the slug-prefixed source name).
DRAFT_MEMO_NAME = "memo.md"


def runs_root(project_root) -> Path:
    """The parent of every run folder: <project_root>/output/runs/."""
    return Path(project_root) / OUTPUT_DIRNAME / RUNS_DIRNAME


def new_run_id() -> str:
    """One opaque UUID format for new CLI and server runs (32 lowercase hex)."""
    return uuid.uuid4().hex


def _stamp(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


def run_dirname(now: datetime, run_id: str) -> str:
    return f"{_stamp(now)}__{run_id}"


def date_run_dirname(now: datetime, slug: str) -> str:
    """A human-readable run folder name: <YYYY-MM-DD>__<slug>. The slug is supplied by
    the caller (the draft question, or the review document count and type)."""
    slug = re.sub(r"[^a-z0-9]+", "_", (slug or "run").lower()).strip("_") or "run"
    return f"{now.strftime('%Y-%m-%d')}__{slug[:60]}"


def rename_run(run_ctx: "RunContext", slug: str, *, now=None) -> "RunContext":
    """Rename a finished run folder from its provisional timestamp name to a
    human-readable <date>__<slug>. On collision (same date + slug), the original run id
    is appended to keep it unique. If the move fails (e.g. an open handle), the original
    RunContext is returned unchanged. Safe to call only after all run writes are done."""
    now = now or datetime.now(timezone.utc)
    root = runs_root(run_ctx.project_root)
    target = root / date_run_dirname(now, slug)
    if target == run_ctx.run_dir:
        return run_ctx
    if target.exists():
        target = root / f"{date_run_dirname(now, slug)}__{run_ctx.run_id}"
    # A rename belongs wholly to this project's run root, including after path
    # resolution. A caller-supplied external output folder is never moved here.
    resolved_root = root.resolve()
    if run_ctx.run_dir.resolve().parent != resolved_root or target.resolve().parent != resolved_root:
        return run_ctx
    try:
        shutil.move(str(run_ctx.run_dir), str(target))
    except OSError:
        return run_ctx
    return RunContext(project_root=run_ctx.project_root, run_id=run_ctx.run_id, run_dir=target)


@dataclass
class RunContext:
    """Per-run output paths. Construct once at run start via create_run()."""
    project_root: Path
    run_id: str
    run_dir: Path

    # --- subdirectories ---
    def deliverables_dir(self) -> Path:
        return self.run_dir / "deliverables"

    def doc_deliverables_dir(self, doc_id: str) -> Path:
        """BP-16: the per-document subfolder under deliverables/ that holds one
        document's artifacts (named after the document)."""
        return self.deliverables_dir() / doc_id

    def logs_dir(self) -> Path:
        return self.run_dir / "logs"

    def audit_dir(self) -> Path:
        return self.run_dir / "audit"

    def contract_violations_dir(self) -> Path:
        return self.audit_dir() / "contract_violations"

    # --- per-artifact paths ---
    def bus_path(self) -> Path:
        return self.logs_dir() / "agent_bus.jsonl"

    def cost_jsonl_path(self) -> Path:
        return self.logs_dir() / "cost_tracker.jsonl"

    def cost_json_path(self) -> Path:
        return self.logs_dir() / "cost_tracker.json"

    def reference_index_path(self) -> Path:
        return self.audit_dir() / "reference_index.json"

    def audit_synthesis_path(self) -> Path:
        return self.audit_dir() / "audit_synthesis.md"

    def delta_proposals_path(self) -> Path:
        return self.audit_dir() / "delta_proposals.json"

    def run_summary_path(self, now=None) -> Path:
        now = now or datetime.now(timezone.utc)
        return self.logs_dir() / f"run_summary_{now.strftime('%Y%m%d_%H%M%S')}.md"

    def status_path(self) -> Path:
        """productization STEP 2: the disk-backed run-state record the server
        writes on every job transition (queued, running, completed, failed,
        interrupted). Lives directly under the run folder, not under logs/ or
        audit/, so it survives independently of what a run actually produced."""
        return self.run_dir / "status.json"

    def ensure(self) -> "RunContext":
        """Create the run folders and preserve their identity independently of naming."""
        if not _safe_id(self.run_id):
            raise ValueError("run context contains an invalid identity")
        for d in (self.deliverables_dir(), self.logs_dir(),
                  self.audit_dir(), self.contract_violations_dir()):
            d.mkdir(parents=True, exist_ok=True)
        path = self.audit_dir() / IDENTITY_FILENAME
        if path.exists():
            if _identity_record(path, strict=True) != self.run_id:
                raise ValueError("run context conflicts with its recorded identity")
        else:
            temp = path.with_suffix(".json.tmp")
            temp.write_text(json.dumps({"schema_version": 1, "run_id": self.run_id}) + "\n", encoding="utf-8")
            temp.replace(path)
        return self


def create_run(project_root, *, now=None, run_id=None) -> RunContext:
    """Create a fresh run folder under output/runs/ and return its RunContext.

    A non-None run_id/now is accepted for reproducible tests; otherwise a UTC
    timestamp and a random run id are generated so two runs never collide.
    """
    now = now or datetime.now(timezone.utc)
    rid = run_id or new_run_id()
    if not _safe_id(rid):
        raise ValueError("invalid run identity")
    rd = runs_root(project_root) / run_dirname(now, rid)
    return RunContext(project_root=Path(project_root), run_id=rid, run_dir=rd).ensure()


def _safe_id(value):
    return isinstance(value, str) and _SAFE_RECORDED_ID_RE.fullmatch(value) is not None


def _identity_record(path, *, strict=False):
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        if strict:
            raise ValueError("run identity record is unreadable") from None
        return None
    rid = record.get("run_id") if isinstance(record, dict) else None
    if _safe_id(rid) and (not strict or record.get("schema_version") == 1):
        return rid
    if strict:
        raise ValueError("run identity record is malformed")
    return None


def _recorded_run_id(run_dir):
    identity = run_dir / "audit" / IDENTITY_FILENAME
    if identity.exists():
        return _identity_record(identity, strict=True)
    # Completion owns the pipeline's recorded identity. Older server metadata
    # owns its published identifier. Neither is reconstructed from a folder slug.
    for path in (run_dir / "audit" / "run_completion.json", run_dir / "status.json"):
        rid = _identity_record(path)
        if rid:
            return rid
    # Old renamed CLI runs predate both records, but their actual calls may still
    # name one run id. Read it without changing those historical artifacts.
    evidence = run_dir / "logs" / "call_evidence.jsonl"
    ids = set()
    if evidence.is_file():
        for line in evidence.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            rid = row.get("run_id") if isinstance(row, dict) else None
            if _safe_id(rid):
                ids.add(rid)
    if len(ids) > 1:
        raise ValueError("run call evidence contains conflicting identities")
    return next(iter(ids)) if ids else None


def for_run_dir(project_root, run_dir) -> RunContext:
    """Open an existing run by recorded identity, without creating or rewriting it."""
    run_dir = Path(run_dir)
    rid = _recorded_run_id(run_dir)
    if rid is None:
        # Bare server paths can be opened before status.json is first written.
        # Preserve legacy URL ids whole as well as the new UUID format.
        if SERVER_RUN_ID_RE.fullmatch(run_dir.name):
            rid = run_dir.name
        else:
            # Retain the old path-only fallback for runs with no identity evidence.
            rid = run_dir.name.split("__", 1)[1] if "__" in run_dir.name else run_dir.name
    return RunContext(project_root=Path(project_root), run_id=rid, run_dir=run_dir)


def start_run_in(project_root, run_dir) -> RunContext:
    """Start in a caller-pinned folder, preserving a recorded or published identity.

    A fresh arbitrary folder label is a location, not a run id. Give it the same
    generated UUID as an automatic run and persist that identity before work.
    """
    run_dir = Path(run_dir)
    rid = _recorded_run_id(run_dir)
    if rid is None:
        rid = run_dir.name if SERVER_RUN_ID_RE.fullmatch(run_dir.name) else new_run_id()
    return RunContext(project_root=Path(project_root), run_id=rid, run_dir=run_dir).ensure()


def latest_run(project_root) -> "RunContext | None":
    """The most recent run folder by modification time, or None. Sorting by mtime (not
    by name) is robust to human-readable <date>__<slug> folder names, which do not encode
    the time of day and so are not chronologically sortable by name."""
    root = runs_root(project_root)
    if not root.is_dir():
        return None
    runs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
    if not runs:
        return None
    return for_run_dir(project_root, runs[-1])
