"""Single source of truth for per-run output paths (genesis Part XXVII section A).

Every run writes ONLY into its own run-scoped folder:

    output/runs/<UTC-timestamp>__<run-id>/
        deliverables/   per-document deliverables
        logs/           agent_bus.jsonl, cost_tracker.{jsonl,json}, run_summary_*.md
        audit/          reference_index.json, audit_synthesis.md, delta_proposals.json,
                        contract_violations/

Two runs never overwrite each other: each gets a distinct folder (timestamp +
random run id, unique even within the same second). Modeled on durable_paths.py:
every per-run writer derives its path from a RunContext rather than hardcoding an
output/ subpath.

Firewall (INFRA-029/030): the protected DURABLE class lives under durable/ and is
NEVER written here. Per-run cleanup is confined to output/runs/ and is
structurally incapable of reaching durable/ — this module only ever builds paths
under output/runs/, never under durable/ or config/.
"""

from __future__ import annotations

import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_DIRNAME = "output"
RUNS_DIRNAME = "runs"

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
    """A short, collision-resistant run id (8 hex chars)."""
    return uuid.uuid4().hex[:8]


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
        """Create the run folder and its standard subdirectories."""
        for d in (self.deliverables_dir(), self.logs_dir(),
                  self.audit_dir(), self.contract_violations_dir()):
            d.mkdir(parents=True, exist_ok=True)
        return self


def create_run(project_root, *, now=None, run_id=None) -> RunContext:
    """Create a fresh run folder under output/runs/ and return its RunContext.

    A non-None run_id/now is accepted for reproducible tests; otherwise a UTC
    timestamp and a random run id are generated so two runs never collide.
    """
    now = now or datetime.now(timezone.utc)
    rid = run_id or new_run_id()
    rd = runs_root(project_root) / run_dirname(now, rid)
    return RunContext(project_root=Path(project_root), run_id=rid, run_dir=rd).ensure()


def for_run_dir(project_root, run_dir) -> RunContext:
    """Build a RunContext around an EXISTING run folder (no mkdir of a new run)."""
    run_dir = Path(run_dir)
    rid = run_dir.name.split("__", 1)[1] if "__" in run_dir.name else run_dir.name
    return RunContext(project_root=Path(project_root), run_id=rid, run_dir=run_dir)


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
