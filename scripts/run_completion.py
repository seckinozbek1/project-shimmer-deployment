"""Pipeline completion evidence, independent of the server's process status.

The entry-point decorator records every normal return or catchable exception.
Only an explicit end-of-work mark followed by return code 0 means completed.
A hard kill leaves running evidence, which never establishes completion.
"""
from __future__ import annotations

import json
import sys
import time
import model_telemetry
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps

_ACTIVE = ContextVar("shimmer_run_completion", default=None)
COMPLETION_NAME = "run_completion.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


class RunCompletion:
    def __init__(self, run_context):
        self.run_context = run_context
        self.cpu_start = time.process_time()
        model_telemetry.emit(run_context, 'pipeline_start')
        self.resource_sampler = model_telemetry.Sampler(run_context)
        self.record = {"schema_version": 1, "run_id": run_context.run_id,
                       "state": "running", "started_at": _now(), "finished_at": None,
                       "reached_end": False, "exit_code": None,
                       "document_count": None, "amendment_count": None,
                       "error_type": None}
        self._write()

    def _write(self):
        path = self.run_context.audit_dir() / COMPLETION_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(self.record, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)

    def reached_end(self, *, document_count, amendment_count):
        """Called only after the pipeline finishes its final required work."""
        self.record.update(reached_end=True, document_count=document_count,
                           amendment_count=amendment_count)

    def finish(self, exit_code, error=None):
        self.resource_sampler.close()
        model_telemetry.emit(self.run_context, 'pipeline_end', process_cpu_seconds=time.process_time()-self.cpu_start)
        if error is not None:
            state = "interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "failed"
        else:
            state = "completed" if self.record["reached_end"] and exit_code == 0 else "stopped"
        if getattr(self.run_context, "semantic_incomplete", False):
            self.record["semantic_complete"] = False
            if state == "completed":
                state = "stopped"
        self.record.update(state=state, exit_code=exit_code, finished_at=_now(),
                           error_type=type(error).__name__ if error is not None else None)
        self._write()
        model_telemetry.recompute(self.run_context.run_dir)


def begin(run_context):
    """Start evidence inside a tracked entry point, after the run folder exists."""
    completion = RunCompletion(run_context)
    _ACTIVE.set(completion)
    return completion


def tracked(entry_point):
    """Persist terminal evidence without changing returns or swallowing errors.

    Context-local state isolates concurrent and nested invocations. Snapshot-only
    commands never call begin and therefore create no run completion artifact.
    """
    @wraps(entry_point)
    def run(*args, **kwargs):
        token = _ACTIVE.set(None)
        exit_code, error = None, None
        try:
            exit_code = entry_point(*args, **kwargs)
            return exit_code
        except BaseException as exc:
            error = exc
            if isinstance(exc, SystemExit) and isinstance(exc.code, int):
                exit_code = exc.code
            raise
        finally:
            completion = _ACTIVE.get()
            try:
                if completion is not None:
                    completion.finish(exit_code, error)
            except OSError as exc:
                # Keep the original return or exception, and never expose error
                # text that could contain source material or credentials.
                print("[pipeline] completion record could not be saved: %s" % type(exc).__name__,
                      file=sys.stderr)
            finally:
                _ACTIVE.reset(token)
    return run


def read(run_dir):
    """A valid completion record, or None for absent, old or malformed evidence."""
    from pathlib import Path
    path = Path(run_dir) / "audit" / COMPLETION_NAME
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        return None
    state = record.get("state")
    if not isinstance(state, str) or state not in {"running", "completed", "stopped", "interrupted", "failed"}:
        return None
    if record["state"] == "completed" and (record.get("reached_end") is not True
            or type(record.get("exit_code")) is not int or record["exit_code"] != 0
            or not isinstance(record.get("finished_at"), str) or not record["finished_at"]):
        return None
    return record
