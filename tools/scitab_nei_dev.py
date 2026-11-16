"""NOT ENOUGH INFO development material for SciTab (D-642 item 4 (c); SCITAB_NEI_SOURCES.md).

SciTab's own NOT ENOUGH INFO claims all sit in the holdout pool the gate and its quick subset are drawn
from, so none of them can become development material (that would change the holdout: Seckin's
decision alone). This tool builds the class from development material only: SEM-TAB-FACTS (SemEval-2021
Task 9, CC BY 4.0, `external/semtab/SOURCES.json`), its dev and test ground-truth files and nothing
else (its training files are refused; they hold no `unknown` statement anyway). Each statement
becomes one SciTab-shaped claim record (the fields `benchmark/adapters/scitab/adapter.py` reads), so
the existing adapter builds it as it builds SciTab:

    entailed -> supports      refuted -> refutes      unknown -> not enough info

Cell positions are kept: a cell spanning columns or rows writes its text at its first position and an
empty cell over the rest of its span, and a table whose rows do not fill the same positions is refused
(`ragged`), never padded. Row 0 is the header.

LEAKAGE_PROTOCOL. SEM-TAB-FACTS is a new development part. No item is written until role B's leakage
result for that part against the SciTab gate and quick pools is given (`--clearance`): the result
must be the tool's own format and thresholds, with the cosine rule applied, the part among its
fingerprint parts, and zero candidates hit (the outcome rule fixed in SCITAB_NEI_SOURCES.md before any
count: on any hit nothing is dropped after the fact, it goes to Seckin). Without it the tool prints
counts only. The tool never opens a gate set, a quick subset, a key or a role folder; it reads the
SEM-TAB files it is given.

    py -3.12 -X utf8 tools/scitab_nei_dev.py count --source external/semtab/extracted/dev/v1.1/output \
        --source external/semtab/extracted/test_groundtruth
    py -3.12 -X utf8 tools/scitab_nei_dev.py build --source ... --clearance ROLE_B_RESULT.json --out OUT.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "benchmark" / "adapters"

PART = "semtab"                      # the part name of external/semtab/fingerprint/count.json
LABELS = {"entailed": "supports", "refuted": "refutes", "unknown": "not enough info"}
SOURCE_NAME = "SEM-TAB-FACTS (SemEval-2021 Task 9), CC BY 4.0"
# Refusal reasons, the tool's own closed set (the first word of each message).
NOT_DEV_OR_TEST, RAGGED, NO_CLEARANCE, NOT_CLEAR = "not_dev_or_test", "ragged", "no_clearance", "not_clear"


class Refused(ValueError):
    """A source or a write this tool refuses: its message starts with the reason."""


def _admitted(path):
    """Only SEM-TAB-FACTS dev ground truth (extracted/dev/.../output) and test ground truth
    (extracted/test_groundtruth); never a training file."""
    parts = [p.lower() for p in Path(path).parts]
    if any("train" in p for p in parts):
        return False
    for i in range(len(parts) - 1):
        if parts[i] == "extracted" and parts[i + 1] == "test_groundtruth":
            return True
        if parts[i] == "extracted" and parts[i + 1] == "dev" and parts[-1] == "output":
            return True
    return False


def _text(value):
    return " ".join(str(value or "").split())


def _grid(table):
    """[[cell text]] of one <table>, row by row, every position of a span filled (text at its first
    position, "" over the rest), or Refused(ragged) when the rows do not fill the same positions."""
    grid = {}
    for row in table.findall("row"):
        for cell in row.findall("cell"):
            r0, r1 = int(cell.get("row-start")), int(cell.get("row-end"))
            start, end = int(cell.get("col-start")), int(cell.get("col-end"))
            text = _text(cell.get("text"))
            for r in range(r0, r1 + 1):
                for col in range(start, end + 1):
                    grid.setdefault(r, {})[col] = text if (r == r0 and col == start) else ""
    if not grid:
        raise Refused(RAGGED + ": a table with no cell")
    width = max(max(cols) for cols in grid.values()) + 1
    rows = []
    for r in sorted(grid):
        if sorted(grid[r]) != list(range(width)):
            raise Refused(RAGGED + ": row %d does not fill the table's %d positions" % (r, width))
        rows.append([grid[r][c] for c in range(width)])
    return rows


def _records_of(path):
    tree = ET.parse(path)
    article = "semtab-" + Path(path).stem
    out = []
    for n, table in enumerate(tree.getroot().iter("table")):
        grid = _grid(table)
        caption = table.find("caption")
        table_id = "%s-t%d" % (article, n)
        statements = table.find("statements")
        for statement in (statements.findall("statement") if statements is not None else []):
            label = LABELS.get(str(statement.get("type") or "").strip().lower())
            if label is None:
                continue
            out.append({"id": "%s-s%s" % (table_id, statement.get("id")), "table_id": table_id, "paper_id": article,
                        "table_caption": _text(caption.get("text") if caption is not None else ""),
                        "table_column_names": grid[0], "table_content_values": grid[1:],
                        "claim": _text(statement.get("text")), "label": label,
                        "source": SOURCE_NAME, "source_part": "test" if "test_groundtruth" in Path(path).parts else "dev"})
    return out


def convert(sources):
    """Every claim record of the admitted SEM-TAB folders, in file order."""
    records = []
    for source in sources:
        source = Path(source)
        if not _admitted(source):
            raise Refused(NOT_DEV_OR_TEST + ": %s is not SEM-TAB-FACTS dev or test ground truth" % source.name)
        for path in sorted(source.glob("*.xml")):
            records.extend(_records_of(path))
    if len({r["id"] for r in records}) != len(records):
        raise Refused(RAGGED + ": a claim id twice")
    return records


def counts(records):
    """Counts only: claims, tables, papers and claims by label."""
    by = {}
    for r in records:
        by[r["label"]] = by.get(r["label"], 0) + 1
    return {"claims": len(records), "tables": len({r["table_id"] for r in records}),
            "papers": len({r["paper_id"] for r in records}), "by_label": dict(sorted(by.items()))}


def _gate_leakage():
    if str(ADAPTERS) not in sys.path:
        sys.path.insert(0, str(ADAPTERS))
    from common import gate_leakage
    return gate_leakage


def leakage_format():
    return _gate_leakage().FORMAT


def leakage_thresholds():
    return _gate_leakage().THRESHOLDS


def clearance_refusal(path):
    """Why role B's leakage result does not admit the part, or None when it does."""
    if path is None:
        return NO_CLEARANCE + ": no leakage result from role B (LEAKAGE_PROTOCOL step 4)"
    result = json.loads(Path(path).read_text(encoding="utf-8"))
    if result.get("format") != leakage_format() or result.get("thresholds") != leakage_thresholds():
        return NOT_CLEAR + ": the result is not gate_leakage's own format and thresholds"
    if result.get("cosine_rule") != "applied":
        return NOT_CLEAR + ": the cosine rule was not applied"
    if PART not in (result.get("fingerprint_parts") or []):
        return NOT_CLEAR + ": the fingerprint holds no %s part" % PART
    hits = int((result.get("candidates_by_part") or {}).get(PART) or 0)
    if hits or result.get("excluded_candidates"):
        return NOT_CLEAR + ": %d gate or quick-subset candidates hit; nothing is dropped after a count, it goes to Seckin" % max(
            hits, int(result.get("excluded_candidates") or 0))
    return None


def write(records, out, clearance):
    """Write the records only under a clearing leakage result; else Refused."""
    refusal = clearance_refusal(clearance)
    if refusal:
        raise Refused(refusal)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return counts(records)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=("count", "build"))
    ap.add_argument("--source", action="append", default=[], type=Path)
    ap.add_argument("--clearance", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    try:
        records = convert(args.source)
        if args.command == "count":
            print(json.dumps(counts(records), indent=1, sort_keys=True))
            return 0
        if not args.out:
            ap.error("build needs --out")
        print(json.dumps(write(records, args.out, args.clearance), indent=1, sort_keys=True))
        return 0
    except Refused as exc:
        print("refused: %s" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
