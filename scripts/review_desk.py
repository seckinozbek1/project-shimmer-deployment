"""The v1.05 review desk's read-only projections (docs/loop/stages/V105_UI_DESIGN.md, step 1).

Three answers the desk page (scripts/ui/desk.html, served at GET /console?view=desk) needs that the
existing routes do not give, each read from files that already exist and never written:

  inputs_listing      the files in place under input/conventions, input/context and
                      input/operational: names, sizes and times only, never content.
  progress_reading    PROGRESS-A's four values for a local run: documents done against the
                      total, time elapsed, the current rate and the remaining time at that
                      rate, each measured from the run folder and the job record, or
                      stated as not measurable with the reason.
  reviewed_document   one document's reviewed_document.md (READABLE-A), the name matched
                      against the run's own deliverables listing before any path is built.

scripts/server.py wraps each one in a token-gated route (GET /inputs,
GET /runs/{run_id}/progress, GET /runs/{run_id}/reviewed/{doc_id}); the sealed refusal and
the run id validation stay the server's own. Nothing here starts a run, calls a model or
touches the network.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

INPUT_FOLDERS = ("conventions", "context", "operational")
# A listing is capped per folder so a very large corpus cannot make one response huge.
LIST_CAP = 500
REVIEWED_NAME = "reviewed_document.md"
# The pipeline's own nominal phase total ([progress] phase=N/TOTAL, scripts/pipeline.py).
NOMINAL_PHASES = 9


def inputs_listing(input_root):
    """{folder: {"files": [{"name", "bytes", "modified"}], "count", "truncated"}} for each
    declared input folder; a missing folder is listed as absent, never invented."""
    root = Path(input_root)
    out = {}
    for name in INPUT_FOLDERS:
        folder = root / name
        if not folder.is_dir():
            out[name] = {"present": False, "files": [], "count": 0, "truncated": False}
            continue
        files = []
        for path in sorted(folder.rglob("*")):
            rel = path.relative_to(folder)
            if any(part.startswith(".") for part in rel.parts) or not path.is_file():
                continue
            stat = path.stat()
            files.append({"name": rel.as_posix(), "bytes": stat.st_size,
                          "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat()})
        out[name] = {"present": True, "files": files[:LIST_CAP], "count": len(files),
                     "truncated": len(files) > LIST_CAP}
    return out


def parse_progress(text):
    """The key=value body of a pipeline [progress] line (server._progress_string keeps it on
    the job) as a dict; an empty dict for None or a body with no pairs."""
    out = {}
    for token in str(text or "").split():
        if "=" in token:
            key, value = token.split("=", 1)
            out[key] = value
    return out


def _fraction(value):
    """(done, total) from an N/TOTAL string, or (None, None)."""
    try:
        done, total = str(value).split("/", 1)
        return float(done), int(total)
    except (ValueError, TypeError):
        return None, None


def _time(value):
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def documents_done(run_dir):
    """Documents whose deliverables folder holds at least one file: the same test
    server._documents_for_run uses for a document's `done`."""
    root = Path(run_dir) / "deliverables"
    if not root.is_dir():
        return 0
    return sum(1 for d in root.iterdir() if d.is_dir() and any(p.is_file() for p in d.rglob("*")))


def _reader_line(done, total, elapsed_s):
    """The one-line reading from the tracked PROGRESS-A reader (tools/ordinary_final_progress
    count_reading) when this installation carries it."""
    tools = str(Path(__file__).resolve().parents[1] / "tools")
    if tools not in sys.path:
        sys.path.append(tools)
    try:
        from ordinary_final_progress import count_reading
    except Exception:  # an installation without the loop tools still answers the four values.
        return None
    baseline = ("every document is done" if total and done >= total
                else "no remaining time can be read without a total")
    return count_reading("review", done, total or 0, elapsed_s or 0, "documents", baseline)


def progress_reading(job, run_dir, now=None):
    """PROGRESS-A's four values for one local run, measured, never estimated.

    done      documents with deliverables on disk (documents_done).
    total     the pipeline's own document count from its latest [progress] line
              (doc=M/DOCS or docs=N); None when the run has not said it yet.
    elapsed   seconds from the job's started_at to its completed_at, or to now while live.
    rate      documents per minute so far; remaining minutes at that rate.
    Each value that cannot be measured is None with its reason in `not_measurable`."""
    job = job or {}
    now = now or datetime.now(timezone.utc)
    fields = parse_progress(job.get("progress"))
    done = documents_done(run_dir)
    total = None
    if "doc" in fields:
        _, total = _fraction(fields["doc"])
    if total is None and str(fields.get("docs", "")).isdigit():
        total = int(fields["docs"])
    phase, phase_total = _fraction(fields.get("phase"))
    started, ended = _time(job.get("started_at")), _time(job.get("completed_at"))
    why = {}
    elapsed = None
    if started is None:
        why["elapsed"] = "the run has not started"
    else:
        elapsed = max(0.0, ((ended or now) - started).total_seconds())
    if total is None:
        why["total"] = "the pipeline has not reported its document count yet"
    rate = remaining = None
    if elapsed and done:
        rate = done / (elapsed / 60.0)
    else:
        why["rate"] = ("no document has finished yet, so there is no rate to read" if started
                       else "the run has not started")
    if rate and total is not None:
        remaining = max(0.0, (total - done) / rate)
    else:
        why["remaining"] = "needs both a rate and a total"
    return {
        "measured_from": "documents with deliverables in the run folder; the total from the pipeline's own [progress] line",
        "documents_done": done, "documents_total": total,
        "elapsed_seconds": None if elapsed is None else round(elapsed, 1),
        "rate_documents_per_minute": None if rate is None else round(rate, 3),
        "remaining_minutes": None if remaining is None else round(remaining, 1),
        "phase": fields.get("phase"),
        "phase_note": (None if phase is None else
                       "phase %g of a nominal %d (the pipeline's own phase labels, not a share of the work)"
                       % (phase, phase_total or NOMINAL_PHASES)),
        "status": fields.get("status"),
        "not_measurable": why,
        "reading": _reader_line(done, total, elapsed),
    }


def reviewed_document(run_dir, doc_id):
    """The text of deliverables/<doc_id>/reviewed_document.md. doc_id must be the exact name
    of one of the run's deliverables folders; LookupError otherwise, and when the file is
    not written yet."""
    root = Path(run_dir) / "deliverables"
    names = {d.name for d in root.iterdir() if d.is_dir()} if root.is_dir() else set()
    if doc_id not in names:
        raise LookupError("document not found for this run")
    path = root / doc_id / REVIEWED_NAME
    if not path.is_file():
        raise LookupError("reviewed_document.md is not written for this document yet")
    return path.read_text(encoding="utf-8", errors="replace")
