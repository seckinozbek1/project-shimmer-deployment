"""Structured JSON-lines logging (productization STEP 4).

Every diagnostic in this codebase was a bare print(..., file=sys.stderr); this
module gives pipeline.py and agent_wrapper.py a stdlib logging.Logger whose
records are formatted as one JSON object per line, still written to stderr, so
existing tooling that reads the stderr stream (a terminal, a redirected log
file, the server's tail capture) keeps working unchanged. Each record carries
run_id, phase, agent, doc_id, event, level, ts.

The [progress] line (scripts/server.py::_progress_string,
scripts/chat.py::parse_progress) is NOT touched by this module: it is emitted
by a separate, unchanged print() call and its format stays byte-identical
(W5). This module is for the surrounding diagnostic banners, not the
machine-parsed progress contract.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class _JsonLinesFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "run_id": getattr(record, "run_id", ""),
            "phase": getattr(record, "phase", ""),
            "agent": getattr(record, "agent", ""),
            "doc_id": getattr(record, "doc_id", ""),
            "event": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "shimmer") -> logging.Logger:
    """Return the named logger, configured once (idempotent: a second call
    with the same name does not attach a second handler). stderr only, JSON
    lines, level INFO by default (WARNING and above always visible)."""
    logger = logging.getLogger(name)
    if not any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, _JsonLinesFormatter)
               for h in logger.handlers):
        handler = logging.StreamHandler(stream=sys.stderr)
        handler.setFormatter(_JsonLinesFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def log_event(logger: logging.Logger, event: str, *, level: str = "info",
              run_id: str = "", phase: str = "", agent: str = "", doc_id: str = "") -> None:
    """Emit one structured event. `event` is a short machine-greppable name
    (e.g. "phase_done", "model_unknown_priced"), never prompt or document text
    (W8) -- callers pass only short identifiers/counts in `event`, never raw
    model output."""
    fn = getattr(logger, level.lower(), logger.info)
    fn(event, extra={"run_id": run_id, "phase": phase, "agent": agent, "doc_id": doc_id})


def log_phase_done(logger: logging.Logger, phase: str, *, run_id: str = "", duration_ms: int = 0) -> None:
    """The phase_done event: one per pipeline.main phase call, carrying how
    long that phase's asyncio.run(...) took. duration_ms is embedded in the
    event string (not a separate JSON field) so no schema change is needed for
    consumers that only grep the JSON-lines stream for "phase_done"."""
    log_event(logger, f"phase_done phase={phase} duration_ms={duration_ms}",
              run_id=run_id, phase=phase)
