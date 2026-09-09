"""Promotion-exclusion helper (M1).

Reads the corpus ingestion sidecar (`_corpus_ingest.json`, defined by CONTRACT.md)
and returns the set of filenames marked grounding-only, so the pipeline can keep
them out of operational promotion. Ingested cases are retrieved precedent, not the
document under review; they must never be promoted to operational and never
amended.

Self-contained: stdlib only (pathlib, json). Imports nothing from pipeline.py or
any other Shimmer module, so the integration logic stays in the integration module.

Graceful absence: standalone Shimmer (no external ingestion) has no sidecar, so a
missing or unparseable sidecar yields an empty set with no error and no warning,
and the pipeline runs exactly as before.
"""

from __future__ import annotations

import json
from pathlib import Path

SIDECAR_NAME = "_corpus_ingest.json"
GROUNDING_ROLE = "context_grounding"


def context_grounding_filenames(context_dir: Path) -> set[str]:
    """Return the set of `entry["file"]` values in `context_dir/_corpus_ingest.json`
    whose `entry["role"]` is `context_grounding`.

    Returns an empty set if the sidecar is absent, unreadable, or not parseable,
    or if it has no grounding entries. Never raises, never warns."""
    sidecar = Path(context_dir) / SIDECAR_NAME
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # OSError: absent/unreadable. ValueError: not valid JSON. Either way the
        # base pipeline behavior (no exclusions) is correct.
        return set()
    if not isinstance(data, dict):
        return set()
    cases = data.get("cases")
    if not isinstance(cases, list):
        return set()
    grounding = set()
    for entry in cases:
        if not isinstance(entry, dict):
            continue
        if entry.get("role") == GROUNDING_ROLE:
            fname = entry.get("file")
            if isinstance(fname, str) and fname:
                grounding.add(fname)
    return grounding
