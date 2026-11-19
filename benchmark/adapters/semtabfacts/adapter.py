"""SEM-TAB-FACTS adapter (SemEval-2021 Task 9): an auxiliary validation set holding a not-enough-info
class (D-798 item 4). Its own benchmark name (`semtabfacts`, so ids of its own) and its own set name
(`semtabfacts_aux_val`); never mixed into, sampled with, or reported as a SciTab set or score.

The bundle is the one the SciTab adapter writes (scitab/adapter.py): one item per statement; the
document is the table with its caption, one part (the caption line, a blank line, the table as a
pipe-delimited Markdown table, row 0 the header); one rule per statement with SciTab's own rule text and
its `compare: cells` declaration; FLAG = refutes, UNDECIDED = not enough info, CLEAR = supports.

Two steps. `freeze` reads the XML files of the declared parts (dev and test, the files that carry the
gold statement types: dev v1.1 output and the posted test ground truth), refuses on the record what it
cannot read (counted by reason: a span outside the grid, a missing type, an unknown type value and the
rest of REASONS), strips every evidence mark before any cell is read (gold side information), and
writes one frozen file with its digest and an empty look counter. `build`, `split`, `bands`, `label`
and `score` are the common commands (common/cli.py) over that frozen file alone.

Everything the set declares (set name, parts, the type-to-class map, side, span fill, report line) is
read at call time from config/semtabfacts_aux_val.json; none of it is written here.

    py -3.12 -X utf8 benchmark/adapters/semtabfacts/adapter.py freeze --part dev=<folder> \
        --part test=<folder> --out <frozen file>
    py -3.12 -X utf8 benchmark/adapters/semtabfacts/adapter.py build --input <frozen file> \
        --out <empty folder> --development
    py -3.12 -X utf8 benchmark/adapters/semtabfacts/adapter.py score ... --class-setting 3-class
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))

from common import bundle, cli, detection, ids, mapping, metrics  # noqa: E402
from scitab import adapter as scitab  # noqa: E402  (the bundle form this set shares, never its data)

BENCHMARK = "semtabfacts"
CONFIG_PATH = HERE.parents[2] / "config" / "semtabfacts_aux_val.json"
FROZEN_FORMAT = "semtabfacts-frozen-v1"

# --- source schema --------------------------------------------------------------------
# From role B's count of element and attribute names only (no file was opened here).
# PROVISIONAL until a freeze runs on the fetched files: the nesting (rows and statements
# inside their table, evidence inside a cell) is assumed, and a statement outside any
# table is refused on the record, never guessed onto one.
DOCUMENT_TAG = "document"
TABLE_TAG, TABLE_ID = "table", "id"
CAPTION_TAG, CAPTION_TEXT = "caption", "text"
ROW_TAG = "row"
CELL_TAG, CELL_TEXT = "cell", "text"
ROW_START, ROW_END, COL_START, COL_END = "row-start", "row-end", "col-start", "col-end"
EVIDENCE_TAG = "evidence"          # statement_id, type, version: gold side information, stripped
STATEMENTS_TAG, STATEMENT_TAG = "statements", "statement"
STATEMENT_ID, STATEMENT_TEXT, STATEMENT_TYPE = "id", "text", "type"
# ---------------------------------------------------------------------------------------

# Refusal reasons, a closed set. Each refusal row names ids only, never text.
UNREADABLE_XML = "unreadable_xml"                  # the file does not parse
NOT_A_DOCUMENT = "not_a_document"                  # the root element is not `document`
NO_TABLE_ID = "no_table_id"                        # a table without an id
DUPLICATE_TABLE = "duplicate_table"                # one document and table id twice in the set
NO_CELLS = "no_cells"                              # a table with no cell
SPAN_UNREADABLE = "span_unreadable"                # a span attribute missing, not an integer, or start after end
SPAN_OUTSIDE_GRID = "span_outside_grid"            # a span before row or column 0 or past the table's last row
OVERLAPPING_CELLS = "overlapping_cells"            # two cells claim one grid position
STATEMENT_OUTSIDE_TABLE = "statement_outside_table"
NO_STATEMENT_ID = "no_statement_id"
DUPLICATE_STATEMENT_ID = "duplicate_statement_id"  # every statement sharing the id is refused
EMPTY_STATEMENT = "empty_statement"
MISSING_TYPE = "missing_type"                      # absent or empty (an input file, not a gold one)
UNKNOWN_TYPE = "unknown_type"                      # a value the declared map does not hold
REASONS = (UNREADABLE_XML, NOT_A_DOCUMENT, NO_TABLE_ID, DUPLICATE_TABLE, NO_CELLS, SPAN_UNREADABLE,
           SPAN_OUTSIDE_GRID, OVERLAPPING_CELLS, STATEMENT_OUTSIDE_TABLE, NO_STATEMENT_ID,
           DUPLICATE_STATEMENT_ID, EMPTY_STATEMENT, MISSING_TYPE, UNKNOWN_TYPE)
SPAN_FILLS = ("repeat", "first")


class Refused(ValueError):
    """A set this adapter refuses as a whole (a config, a frozen file, a part folder)."""


class _TableRefusal(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


# ---------------------------------------------------------------------------
# the declaration, read at call time


def config(path=None) -> dict:
    """config/semtabfacts_aux_val.json, checked: this benchmark's name, a set name apart from every
    name it is never used with, a type map onto exactly SciTab's bundle classes, one header row."""
    cfg = json.loads(Path(path or CONFIG_PATH).read_text(encoding="utf-8"))
    never = [str(n) for n in cfg.get("never_with") or ()]
    name = str(cfg.get("set_name") or "")
    if cfg.get("benchmark") != BENCHMARK or not name:
        raise Refused("the set declaration names another benchmark or no set name")
    if BENCHMARK in never or any(name == n or name.startswith(n) for n in never):
        raise Refused("the set name %r is not apart from %s" % (name, ", ".join(never)))
    values = cfg.get("gold_values") or {}
    if set(values.values()) != set(cfg.get("classes") or ()) or set(cfg["classes"]) != set(scitab.CLASSES):
        raise Refused("the type map must reach exactly the bundle classes %s" % ", ".join(scitab.CLASSES))
    if cfg.get("span_fill") not in SPAN_FILLS:
        raise Refused("span_fill must be one of %s" % ", ".join(SPAN_FILLS))
    if cfg.get("header_rows") != 1:
        raise Refused("the claim-against-a-table bundle has one header row")
    if cfg.get("side") not in (ids.DEVELOPMENT, ids.HOLDOUT):
        raise Refused("the set's side is development or holdout")
    return cfg


def _type_key(value) -> str:
    return str(value or "").strip().lower()


# ---------------------------------------------------------------------------
# reading one XML file


def strip_evidence(root) -> int:
    """Remove every evidence element from the parsed tree before anything is read: the marks are gold
    side information and never reach a record. Returns how many were removed."""
    removed = 0
    for parent in list(root.iter()):
        for child in list(parent):
            if child.tag == EVIDENCE_TAG:
                parent.remove(child)
                removed += 1
    return removed


def _cell_text(cell) -> str:
    """The cell's text: its `text` attribute, else the element's own text content."""
    value = cell.get(CELL_TEXT)
    return value if value is not None else "".join(cell.itertext())


def _span(cell):
    try:
        r0, r1, c0, c1 = (int(str(cell.get(a)).strip()) for a in (ROW_START, ROW_END, COL_START, COL_END))
    except ValueError:
        raise _TableRefusal(SPAN_UNREADABLE)
    if r0 > r1 or c0 > c1:
        raise _TableRefusal(SPAN_UNREADABLE)
    return r0, r1, c0, c1


def grid(table, span_fill):
    """(rows of cell text, holes) of one table. The grid is as tall as the table's rows and as wide as
    its widest span; each spanning cell is expanded over every position its row and column span covers
    (`repeat`: its text at each; `first`: its text at the first, empty over the rest). A position no
    cell covers is an empty cell, counted as a hole."""
    rows = table.findall(ROW_TAG)
    cells = [c for r in rows for c in r.findall(CELL_TAG)]
    if not cells:
        raise _TableRefusal(NO_CELLS)
    height = len(rows)
    spans = []
    for cell in cells:
        r0, r1, c0, c1 = _span(cell)
        if r0 < 0 or c0 < 0 or r1 >= height:
            raise _TableRefusal(SPAN_OUTSIDE_GRID)
        spans.append((r0, r1, c0, c1, _cell_text(cell)))
    width = max(s[3] for s in spans) + 1
    filled = {}
    for r0, r1, c0, c1, text in spans:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if (r, c) in filled:
                    raise _TableRefusal(OVERLAPPING_CELLS)
                filled[(r, c)] = text if (span_fill == "repeat" or (r, c) == (r0, c0)) else ""
    out = [[filled.get((r, c), "") for c in range(width)] for r in range(height)]
    return out, height * width - len(filled)


def _refusal(reason, part, document, table_id=None, statement_id=None, statements=0, tables=0, files=0):
    row = {"reason": reason, "part": part, "document": document, "files": files, "tables": tables,
           "statements": statements}
    if table_id is not None:
        row["table_id"] = table_id
    if statement_id is not None:
        row["statement_id"] = statement_id
    return row


def _statements(table, gold_values, part, document, table_id, refusals):
    kept, seen = [], {}
    for st in table.iter(STATEMENT_TAG):
        sid = (st.get(STATEMENT_ID) or "").strip()
        seen.setdefault(sid, []).append(st)
    for sid, group in seen.items():
        if not sid:
            refusals.append(_refusal(NO_STATEMENT_ID, part, document, table_id, statements=len(group)))
            continue
        if len(group) > 1:
            refusals.append(_refusal(DUPLICATE_STATEMENT_ID, part, document, table_id, sid, statements=len(group)))
            continue
        st = group[0]
        text = bundle.normalise_space(st.get(STATEMENT_TEXT) or "")
        key = _type_key(st.get(STATEMENT_TYPE))
        reason = (EMPTY_STATEMENT if not text else MISSING_TYPE if not key
                  else UNKNOWN_TYPE if key not in gold_values else None)
        if reason:
            refusals.append(_refusal(reason, part, document, table_id, sid, statements=1))
            continue
        kept.append({"id": sid, "text": text, "type": key})
    return kept


def read_file(path, part, cfg):
    """(tables, refusals, evidence marks stripped) of one XML file. The file's stem is the document id."""
    document = Path(path).stem
    refusals = []
    try:
        root = ET.parse(str(path)).getroot()
    except ET.ParseError:
        return [], [_refusal(UNREADABLE_XML, part, document, files=1)], 0
    if root.tag != DOCUMENT_TAG:
        return [], [_refusal(NOT_A_DOCUMENT, part, document, files=1)], 0
    stripped = strip_evidence(root)
    gold_values = {_type_key(k): v for k, v in cfg["gold_values"].items()}
    tables = []
    in_tables = set()
    for table in root.iter(TABLE_TAG):
        in_tables.update(id(st) for st in table.iter(STATEMENT_TAG))
        table_id = (table.get(TABLE_ID) or "").strip()
        n_statements = sum(1 for _ in table.iter(STATEMENT_TAG))
        if not table_id:
            refusals.append(_refusal(NO_TABLE_ID, part, document, statements=n_statements, tables=1))
            continue
        try:
            cells, holes = grid(table, cfg["span_fill"])
        except _TableRefusal as exc:
            refusals.append(_refusal(exc.reason, part, document, table_id, statements=n_statements, tables=1))
            continue
        caption = table.find(CAPTION_TAG)
        tables.append({"part": part, "document": document, "table_id": table_id,
                       "caption": "" if caption is None else (caption.get(CAPTION_TEXT) or ""),
                       "grid": cells, "holes": holes,
                       "statements": _statements(table, gold_values, part, document, table_id, refusals)})
    outside = [st for st in root.iter(STATEMENT_TAG) if id(st) not in in_tables]
    if outside:
        refusals.append(_refusal(STATEMENT_OUTSIDE_TABLE, part, document, statements=len(outside)))
    return tables, refusals, stripped


# ---------------------------------------------------------------------------
# the frozen set


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest_of(frozen) -> str:
    """SHA-256 of the set's content: its name, its type map, its span fill and its tables."""
    content = {k: frozen[k] for k in ("set_name", "gold_values", "span_fill", "tables")}
    return hashlib.sha256(_canonical(content)).hexdigest()


def refused_by_reason(rows) -> dict:
    out = {}
    for row in rows:
        slot = out.setdefault(row["reason"], {"files": 0, "tables": 0, "statements": 0})
        for k in ("files", "tables", "statements"):
            slot[k] += int(row[k])
    return dict(sorted(out.items()))


def counts(tables, gold_values) -> dict:
    """Counts only: documents, tables, statements, statements by class, and by class per part."""
    by_class, by_part = {}, {}
    for t in tables:
        for st in t["statements"]:
            cls = gold_values[st["type"]]
            by_class[cls] = by_class.get(cls, 0) + 1
            part = by_part.setdefault(t["part"], {})
            part[cls] = part.get(cls, 0) + 1
    return {"documents": len({t["document"] for t in tables}), "tables": len(tables),
            "statements": sum(len(t["statements"]) for t in tables),
            "by_class": dict(sorted(by_class.items())),
            "by_part": {p: dict(sorted(v.items())) for p, v in sorted(by_part.items())}}


def freeze(parts, out=None, config_path=None) -> dict:
    """The frozen set from `parts` ({declared part name: folder of XML files}); written to `out` when
    given (an existing file is refused: a frozen set is never overwritten)."""
    cfg = config(config_path)
    unknown = sorted(set(parts) - set(cfg["parts"]))
    if unknown or not parts:
        raise Refused("parts not declared for %s: %s" % (cfg["set_name"], ", ".join(unknown) or "none given"))
    tables, refusals, sources, stripped = [], [], [], 0
    for part in sorted(parts):
        files = sorted(Path(parts[part]).glob("*.xml"))
        if not files:
            raise Refused("part %s holds no XML file" % part)
        for path in files:
            t, r, s = read_file(path, part, cfg)
            tables += t
            refusals += r
            stripped += s
            sources.append({"part": part, "file": path.name,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    # one document and table id twice in the set: every copy refused, none chosen
    keys = {}
    for t in tables:
        keys.setdefault((t["document"], t["table_id"]), []).append(t)
    kept = []
    for key, group in keys.items():
        if len(group) > 1:
            for t in group:
                refusals.append(_refusal(DUPLICATE_TABLE, t["part"], t["document"], t["table_id"],
                                         statements=len(t["statements"]), tables=1))
        else:
            kept.append(group[0])
    kept.sort(key=lambda t: (t["document"], t["table_id"]))
    gold_values = {_type_key(k): v for k, v in cfg["gold_values"].items()}
    frozen = {"format": FROZEN_FORMAT, "set_name": cfg["set_name"], "benchmark": BENCHMARK,
              "decision": cfg.get("decision"), "gold_values": gold_values, "span_fill": cfg["span_fill"],
              "sources": sources, "evidence_marks_stripped": stripped, "tables": kept,
              "refusals": {"by_reason": refused_by_reason(refusals),
                           "rows": sorted(refusals, key=lambda r: (r["reason"], r["part"], r["document"],
                                                                   r.get("table_id", ""), r.get("statement_id", "")))},
              "counts": counts(kept, gold_values), "looks": [],
              "leakage_check": "pending: role B's overlap check against SciTab (D-798 item 4)"}
    frozen["digest"] = digest_of(frozen)
    if out is not None:
        out = Path(out)
        if out.exists():
            raise Refused("a frozen set is never overwritten: " + str(out))
        bundle.write_json(out, frozen)
    return frozen


def summary(frozen, out=None) -> dict:
    """What role B sends back: counts by class, refusals by reason, the digest, the look counter."""
    return {"set_name": frozen["set_name"], "digest": frozen["digest"],
            "file_sha256": hashlib.sha256(Path(out).read_bytes()).hexdigest() if out else None,
            "looks": len(frozen["looks"]), "counts": frozen["counts"],
            "refused_by_reason": frozen["refusals"]["by_reason"],
            "evidence_marks_stripped": frozen["evidence_marks_stripped"]}


def read_source(path) -> dict:
    """The frozen set, checked: this format and benchmark, the declared set name, the digest it
    carries, and the type map it was frozen under equal to the one declared now."""
    cfg = config()
    frozen = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(frozen, dict) or frozen.get("format") != FROZEN_FORMAT or frozen.get("benchmark") != BENCHMARK:
        raise Refused("not a frozen %s set" % BENCHMARK)
    if frozen.get("set_name") != cfg["set_name"]:
        raise Refused("the frozen set is %r, the declared set %r" % (frozen.get("set_name"), cfg["set_name"]))
    if frozen.get("digest") != digest_of(frozen):
        raise Refused("the frozen set's content does not match its digest")
    if frozen["gold_values"] != {_type_key(k): v for k, v in cfg["gold_values"].items()}:
        raise Refused("the type map changed since the freeze: freeze again under a new name")
    return frozen


def check_input(input_path, side, options) -> dict:
    """Recorded in parts.json (`input_check`): the set, its digest and its declared side."""
    frozen = read_source(input_path)
    return {"frozen_for": config()["side"], "set_name": frozen["set_name"], "digest": frozen["digest"],
            "file_sha256": hashlib.sha256(Path(input_path).read_bytes()).hexdigest()}


# ---------------------------------------------------------------------------
# the bundle, as SciTab's


SPEC = mapping.Spec(BENCHMARK, labels=dict(scitab.SPEC.labels), b1_labels=dict(scitab.SPEC.b1_labels),
                    s2=False, detection=detection.THREE_WAY)
CLASSES = scitab.CLASSES
BUILD_OPTIONS = scitab.BUILD_OPTIONS


def source_document_id(table) -> str:
    return "%s/%s" % (table["document"], table["table_id"])


def source_item_id(table, statement) -> str:
    return "%s/%s/%s" % (table["document"], table["table_id"], statement["id"])


def part_text(table) -> str:
    header, body = table["grid"][0], table["grid"][1:]
    return scitab.caption_line(table["caption"]) + "\n\n" + bundle.render_table(header, body)


def documents(frozen, options=None) -> list:
    cfg = config()
    declaration = bundle.build_declaration(BENCHMARK, options) or bundle.BENCHMARK_DECLARATIONS[BENCHMARK]
    out = []
    for table in frozen["tables"]:
        rules, items = [], []
        for st in table["statements"]:
            sid = source_item_id(table, st)
            item_id = ids.opaque_item_id(BENCHMARK, sid)
            rid = bundle.RULE_ID_PREFIX + item_id
            rules.append({"rule_id": rid, "name": scitab.RULE_NAME,
                          "text": scitab.rule_text(st["text"], declaration),
                          "declarations": [declaration], "shipped_text": scitab.rule_text(st["text"])})
            items.append({"item_id": item_id, "source_item_id": sid, "rule_id": rid,
                          "gold": frozen["gold_values"][st["type"]], "location_measurable": False})
        if not items:
            continue
        header, body = table["grid"][0], table["grid"][1:]
        doc_id = source_document_id(table)
        out.append({
            "document_id": ids.opaque_document_id(BENCHMARK, doc_id), "source_document_id": doc_id,
            "split_key": table["document"], "cluster": table["document"], "side": cfg["side"],
            "parts": [{"text": part_text(table), "source": {"part": "caption and table"},
                       "words": ids.word_count(scitab.caption_line(table["caption"])) + bundle.table_words(header, body)}],
            "rules": rules, "items": items,
            "record_extra": {"set_name": frozen["set_name"], "set_digest": frozen["digest"],
                             "source_part": table["part"], "semtab_document": table["document"],
                             "semtab_table_id": table["table_id"], "grid_holes": table["holes"]}})
    return out


def split_rows(frozen, _args=None) -> list:
    side = config()["side"]
    rows = [{"source_document_id": source_document_id(t), "split_key": t["document"], "side": side}
            for t in frozen["tables"] if t["statements"]]
    return sorted(rows, key=lambda r: r["source_document_id"])


def _class_settings():
    cfg = config()
    return {cfg["class_setting"]: tuple(c for c in CLASSES if c in cfg["classes"])}


CLASS_SETTINGS = _class_settings()


def headline(pairs, rows=None, answers=None, unit_text=None, *, setting=None) -> dict:
    """Our own macro-F1 over the declared setting's classes (3-class), on its own line: the set's name
    leads the measure, it is never merged with SciTab, and it is not the task's official per-table
    micro-F1."""
    cfg = config()
    settings = _class_settings()
    if setting not in settings:
        raise ValueError("%s is declared %s, not %r" % (cfg["set_name"], " or ".join(settings), setting))
    classes = settings[setting]
    outside = sorted({g for _p, g in pairs if g not in classes})
    if outside:
        raise ValueError("the set is declared %s but holds gold %s" % (setting, ", ".join(outside)))
    result = metrics.macro_f1(pairs, classes)
    measure = "%s %s macro-F1 over %s (auxiliary validation set)" % (cfg["set_name"], setting, ", ".join(classes))
    return {"headline_measure": measure, "headline_value": result["macro_f1"], "measure": measure,
            "set_name": cfg["set_name"], "class_setting": setting, "report_line": cfg["report_line"],
            "never_merged_with": list(cfg["never_with"]),
            "not_the_official_metric": "the task's official figure is micro-F1 per table averaged over tables",
            "macro_f1": result["macro_f1"], "per_class": result["per_class"],
            "zero_denominators": result["zero_denominators"], "confusion": metrics.confusion(pairs, CLASSES)}


# ---------------------------------------------------------------------------
# the command line


def freeze_main(argv) -> int:
    ap = argparse.ArgumentParser(prog=BENCHMARK + " freeze", description="freeze the declared parts into one set")
    ap.add_argument("--part", action="append", default=[], required=True,
                    help="NAME=FOLDER, a declared part (config parts) and its folder of XML files")
    ap.add_argument("--out", required=True, help="the frozen file (never overwritten)")
    args = ap.parse_args(argv)
    parts = {}
    for given in args.part:
        name, sep, folder = given.partition("=")
        if not sep or name in parts:
            ap.error("--part NAME=FOLDER, each name once")
        parts[name] = folder
    try:
        frozen = freeze(parts, args.out)
    except Refused as exc:
        print("refused: %s" % exc)
        return cli.EXIT_REFUSED
    print(json.dumps(summary(frozen, args.out), indent=2, sort_keys=True))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["freeze"]:
        return freeze_main(argv[1:])
    return cli.main(sys.modules[__name__], argv)


if __name__ == "__main__":
    sys.exit(main())
