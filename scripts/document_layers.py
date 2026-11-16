"""The layer record of one document: which layers the reader read and which it found and could
not read, with counts (issue #280, D-666; issue #281 gap 14, D-667).

A document carries more than its main text: tracked insertions and deletions with their
authors, comments, footnotes and endnotes, and parts the reader does not take in at all (a
content control, a text box, a nested table). Before this record the run said nothing about
any of them, so a layer the reader dropped was lost without a trace. Every document the run
loads now carries one record, printed when it is loaded (`text_extract.print_layer_record`)
and written into the run summary (`summary_lines`).

The record is a plain dict, the contract shared by every format's reader:

    {"format": str,
     "layers": [{"name": str, "read": bool, "count": int, "authors": int, "note": str}],
     "lost":   [str]}

`read` says whether the reader took the layer in, `count` how many of it the document holds,
`authors` how many distinct authors it names (0 where a layer has none), and `note` anything a
reader must know about it. `lost` names every layer present (count above 0) and not read.
The record is structural: it never carries text from the document.

This module also owns the one line the .docx reader writes after a table whose cells are
merged (`merged_note`), and its reader (`merged_columns_by_table`): a merged cell repeats its
value in every row or column it spans, so a sum over such a column would count one value more
than once, and the sum is refused (`paired_review.extract_fields`).

The PDF, HTML and plain-text readers (scripts/pdf_layers.py, scripts/html_layers.py,
scripts/text_extract.py) keep records of the same shape; `reader_lines` is their report's form
(scripts/reader_report.py), `layer_record_lines` the run printout's and the summary's.
"""
from __future__ import annotations

import re

import localization

FIELDS = ("name", "read", "count", "authors", "note")


def layer(name, *, read, count, authors=0, note=""):
    """One layer row of the record."""
    return {"name": str(name), "read": bool(read), "count": int(count),
            "authors": int(authors), "note": str(note)}


def record(fmt, layers):
    """A layer record: `lost` is computed here, never written by a reader."""
    rows = [dict(row) for row in layers]
    return {"format": str(fmt), "layers": rows,
            "lost": [row["name"] for row in rows if not row["read"] and row["count"] > 0]}


def is_record(value):
    """True for a dict of the shared shape."""
    return (isinstance(value, dict) and isinstance(value.get("format"), str)
            and isinstance(value.get("layers"), list) and isinstance(value.get("lost"), list)
            and all(isinstance(row, dict) and set(FIELDS) <= set(row) for row in value["layers"]))


def layer_record_lines(record):
    """The record as lines for the run printout and the run summary, in the run's language.
    Every read layer is listed, even at 0, so a reader sees it was looked for; a layer not
    read is listed only when the document holds it."""
    lines = []
    for row in record.get("layers") or []:
        name = localization.text(row["name"])
        if row["read"]:
            if row.get("authors"):
                line = localization.text("- {layer}: read, {count} found, {authors} author(s)",
                                         layer=name, count=row["count"], authors=row["authors"])
            else:
                line = localization.text("- {layer}: read, {count} found",
                                         layer=name, count=row["count"])
        elif row["count"] > 0:
            line = localization.text("- {layer}: present, not read, {count} found",
                                     layer=name, count=row["count"])
        else:
            continue
        if row.get("note"):
            line += "; " + localization.text(row["note"])
        lines.append(line)
    lost = record.get("lost") or []
    if lost:
        lines.append(localization.text("- layers present but not read: {names}",
                                       names=", ".join(localization.text(n) for n in lost)))
    else:
        lines.append(localization.text("- layers present but not read: none"))
    return lines


def reader_lines(record):
    """The record as plain English lines for the reader's own report (scripts/reader_report.py,
    #281 gap 13), each translated there by the catalog's patterns: the format, every layer with
    its count and authors (0 included), and each lost layer on its own line."""
    lines = ["- format: %s" % record["format"]]
    for layer in record["layers"]:
        if layer["read"]:
            line = "- %s: read, %d found, %d author(s)" % (layer["name"], layer["count"], layer["authors"])
        else:
            line = "- %s: not read, %d found" % (layer["name"], layer["count"])
        if layer["note"]:
            line += "; " + layer["note"]
        lines.append(line)
    lines += ["- lost: %s" % name for name in record["lost"]] or ["- lost: nothing"]
    return lines

def summary_lines(docs):
    """The run summary's section: each document's record, under its name. Documents carrying
    no record (a caller that built its own dicts) add nothing, so such a summary is as before."""
    carried = [d for d in docs or () if is_record(d.get("layer_record"))]
    if not carried:
        return []
    lines = ["", localization.text("## Layers read"), ""]
    for doc in carried:
        rec = doc["layer_record"]
        lines.append(localization.text("- {name} ({format}):", name=doc.get("name") or doc.get("id"),
                                       format=rec["format"]))
        lines += ["  " + line for line in layer_record_lines(rec)]
    return lines


# ---------------------------------------------------------------------------
# merged table cells

_NOTE = "(merged cells repeat their value in column {columns})"
_NOTE_LINE = re.compile(r"^\(merged cells repeat their value in column (\d+(?:, \d+)*)\)$")
_TABLE_ROW = re.compile(r"^[ \t]*\|(.+)\|[ \t]*$")


def merged_note(columns):
    """The line written right after a table: the 1-based columns where a merged cell repeats
    its value. Empty when none."""
    columns = sorted({int(c) for c in columns})
    return _NOTE.format(columns=", ".join(str(c) for c in columns)) if columns else ""


def merged_columns_by_table(text):
    """[set of 0-based column indexes] for each table in the text, in the order
    `pairing_map._table_blocks` finds them: the columns the line right after the table names."""
    out, in_table = [], False
    for line in (text or "").splitlines():
        if _TABLE_ROW.match(line):
            if not in_table:
                out.append(set())
                in_table = True
            continue
        if in_table:
            m = _NOTE_LINE.match(line.strip())
            if m:
                out[-1] = {int(c) - 1 for c in m.group(1).split(", ")}
        in_table = False
    return out
