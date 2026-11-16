"""The run's record of what the document reader read (#280, #281 gap 13).

`pipeline._load_corpus` notes every file it reads here (`note`). A file whose text is empty is an
EMPTY INPUT: a missing library, a scan with no text layer, a file that could not be read or one
with no text. It is not reviewed, and it is never dropped silently any more: it gets a WARN line in
the run at once, a row in `audit/reader_layers.json` (`write`, called by `pipeline.main` after the
corpus is loaded) and a section of `_run_summary.md` (`summary_lines`, read back from that file, so
a summary written outside a run has none). Every document with a layer record
(scripts/document_layers.py) is listed with its record the same way. Names and counts only; no
document text and no author's name is written.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import document_layers
import text_extract

FILENAME = "reader_layers.json"
NO_TEXT = "no text was read from the file"

_SEEN: list = []


def empty_reason(record) -> str:
    """Why a file gave no text: the first unread main-text layer's note, else no text read."""
    for layer in (record or {}).get("layers", []):
        if layer["name"] == "main text" and not layer["read"] and layer["note"]:
            return layer["note"]
    return NO_TEXT


def note(where, path, text) -> None:
    """Record one file `_load_corpus` read from the folder `where`."""
    path = Path(path)
    record = text_extract.last_layer_record(path) or text_extract.layer_record(path)
    empty = not text.strip()
    _SEEN.append({"where": where, "name": path.name, "empty": empty, "record": record,
                  "reason": empty_reason(record) if empty else ""})
    if empty:
        print(f"[reader] WARN: EMPTY INPUT {path.name!r} in {where}: not reviewed; {empty_reason(record)}",
              file=sys.stderr, flush=True)


def write(audit_dir) -> dict:
    """Write the run's reader record and start the next one. Returns what was written."""
    rows = list(_SEEN)
    _SEEN.clear()
    data = {"documents": [r for r in rows if r["record"] is not None and not r["empty"]],
            "empty_inputs": [{k: r[k] for k in ("where", "name", "reason", "record")} for r in rows if r["empty"]]}
    audit_dir = Path(audit_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / FILENAME).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def summary_lines(deliv_dir) -> list[str]:
    """The run summary's reader sections, from this run's audit record; none without one."""
    import localization
    try:
        data = json.loads((Path(deliv_dir).parent / "audit" / FILENAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    lines = []
    empty = data.get("empty_inputs") or []
    if empty:
        lines += ["", localization.text("## Empty input"), "",
                  localization.text("These files gave no text, so nothing of them was reviewed."), ""]
        for row in empty:
            lines.append(localization.message("- %s (%s): empty input, not reviewed; %s"
                                              % (row["name"], row["where"], row["reason"])))
    documents = data.get("documents") or []
    if documents:
        lines += ["", localization.text("## What the reader read"), ""]
        for row in documents:
            lines += ["### %s (%s)" % (row["name"], row["where"]), ""]
            lines += [localization.message(line) for line in document_layers.reader_lines(row["record"])]
            lines.append("")
    return lines
