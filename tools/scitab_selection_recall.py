"""SCITAB_INSIDE (d): how well Python's cell selection (scripts/cell_selection.py, with no embedding, as
benchmark/baselines/doc_judge.select_cells) recovers SciTabAlign's human cell rationales (Ho et al., arXiv
2506.10486; MIT, github.com/Alab-NII/SciTabAlign). No model, no provider.

Run ONLY in role B's own folder (LEAKAGE_PROTOCOL): SciTabAlign's claims are SciTab claims, the gate
set's source, so the lead's side never reads which of them are kept. Role B gives `--exclude`, its
exclusion file of every gate-set and quick-subset paper and table (the `papers` and `tables` lists of
gate_set.py's exclusion shape), and the tool refuses without it. It prints and writes counts and
averages only: no claim id, no paper or table id, no text, no label.

    py -3.12 -X utf8 tools/scitab_selection_recall.py --input RECORDS.json --exclude EXCLUDE.json --out OUT.json
    py -3.12 -X utf8 tools/scitab_selection_recall.py --self-test

RECORDS.json is a list of SciTab-shaped records (the SciTab adapter's fields: `paper_id`, `table_id`, `id`,
`claim`, `table_caption`, `table_column_names`, `table_content_values`) each with `rationale_cells`, a list of
[row, column] indexes into `table_content_values` (0-based content rows, no header row) and its columns.
SciTabAlign's own data.zip is not read here: its field names and index base are confirmed when role B opens
it, and `to_records` is written then against what it holds (a stated step, not guessed now). A rationale
index outside its table refuses the whole run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "scripts", ROOT / "benchmark" / "adapters", ROOT / "benchmark" / "baselines"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def excluded(record, exclusion):
    """True when the record's paper or table is in role B's exclusion file."""
    return (str(record.get("paper_id")) in set(map(str, exclusion.get("papers") or []))
            or str(record.get("table_id")) in set(map(str, exclusion.get("tables") or [])))


def selected_cells(record):
    """{(row, column)} Python's selection shows for the record's claim, on the document text the SciTab
    adapter builds (`part_text`), or None when the selection refuses (its reason counted)."""
    import cell_selection
    from scitab import adapter
    chosen = cell_selection.select(adapter.part_text(record), record["claim"], cell_selection.load_config())
    if not chosen["selected"]:
        return None, chosen["refused"]
    return {(r, c) for r in chosen["rows"] for c in chosen["columns"]}, chosen["selected_by"]


def gold_cells(record):
    rows, cols = len(record["table_content_values"]), len(record["table_column_names"])
    cells = {(int(r), int(c)) for r, c in record["rationale_cells"]}
    if not cells or any(not (0 <= r < rows and 0 <= c < cols) for r, c in cells):
        raise SystemExit("a rationale is empty or indexes outside its table: check the index base before reading")
    return cells


def measure(records, exclusion, select=selected_cells):
    kept = [r for r in records if not excluded(r, exclusion)]
    rows, refused, by = [], {}, {}
    for record in kept:
        gold = gold_cells(record)
        chosen, how = select(record)
        if chosen is None:
            refused[how] = refused.get(how, 0) + 1
            continue
        by[how] = by.get(how, 0) + 1
        hit = len(chosen & gold)
        p, r = hit / len(chosen) if chosen else 0.0, hit / len(gold)
        rows.append(dict(p=p, r=r, f=2 * p * r / (p + r) if p + r else 0.0, all_gold=hit == len(gold)))
    mean = lambda k: round(sum(x[k] for x in rows) / len(rows), 4) if rows else None
    return {"label": "cell selection against SciTabAlign rationales (SCITAB_INSIDE (d)); counts only, role B's side",
            "records": len(records), "excluded": len(records) - len(kept), "measured": len(rows),
            "selection_refused": refused, "selected_by": by,
            "precision_mean": mean("p"), "recall_mean": mean("r"), "f1_mean": mean("f"),
            "every_rationale_cell_shown": sum(1 for x in rows if x["all_gold"])}


def self_test():
    """The arithmetic and the exclusion on invented records, with an injected selection."""
    rec = dict(paper_id="p1", table_id="t1", id="c1", claim="x", table_caption="c", table_column_names=["a", "b"],
               table_content_values=[["1", "2"], ["3", "4"]], rationale_cells=[[0, 1], [1, 1]])
    out = measure([rec, dict(rec, paper_id="gate", table_id="t2")], {"papers": ["gate"], "tables": []},
                  select=lambda r: ({(0, 1), (0, 0)}, "named"))
    assert out["excluded"] == 1 and out["measured"] == 1
    assert out["precision_mean"] == 0.5 and out["recall_mean"] == 0.5 and out["every_rationale_cell_shown"] == 0
    try:
        gold_cells(dict(rec, rationale_cells=[[5, 0]]))
    except SystemExit:
        return "self-test passed"
    raise AssertionError("an index outside the table was not refused")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", type=Path)
    ap.add_argument("--exclude", type=Path, help="role B's exclusion file; the tool refuses without it")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        print(self_test())
        return 0
    if not (args.input and args.exclude and args.out):
        ap.error("--input, --exclude and --out are required (the exclusion file is role B's)")
    result = measure(json.loads(args.input.read_text(encoding="utf-8")), json.loads(args.exclude.read_text(encoding="utf-8")))
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
