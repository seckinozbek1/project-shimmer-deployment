"""Gate check 585: the SEM-TAB-FACTS adapter builds a separate auxiliary validation set (D-798 item 4).

benchmark/adapters/semtabfacts/adapter.py is run on its two hand-written XML fixtures (invented, no real
item): `freeze` over a dev and a test part, then the common `build` over the frozen file. One observation
holds what the check proves:

  - the bundle shape is SciTab's claim-against-a-table bundle (one table document, its caption line and
    pipe table, one `[compare: cells]` rule per statement, the four bundle files, the item table);
  - spanning cells are expanded over every row and column they span;
  - entailed, refuted and unknown reach supports, refutes and not enough info through the declaration
    in config/semtabfacts_aux_val.json, read at call time;
  - every evidence mark is stripped: no written file holds one;
  - a span outside the grid, a missing type and an unknown type value are refused on the record and
    counted by reason;
  - the set is apart from SciTab: its own benchmark name and ids, its own set name on every record and
    on the headline, the SciTab adapter refuses its frozen file and its item table.

Each proof is neutralise, fail, restore, pass (scripts/effect_proof.py). No model, no provider, no key.
"""
from __future__ import annotations

import contextlib
import inspect
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "benchmark" / "adapters"
for _p in (ROOT / "scripts", ADAPTERS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from effect_proof import prove_effect  # noqa: E402

FIXTURES = ADAPTERS / "semtabfacts" / "fixtures"
# A token only an evidence mark of the fixtures carries: its type value (the attribute name
# statement_id is also a refusal row's key, so it is no sign of a mark).
EVIDENCE_TOKENS = ("relevant",)


def _modules():
    from common import cli, ids
    from scitab import adapter as scitab
    from semtabfacts import adapter as semtab
    return semtab, scitab, cli, ids


@contextlib.contextmanager
def patched(owner, name, value):
    old = getattr(owner, name)
    setattr(owner, name, value)
    try:
        yield
    finally:
        setattr(owner, name, old)


@contextlib.contextmanager
def with_source(module, name, old, new):
    """`module.name` with one line of its own source changed, compiled into the module's globals."""
    original = getattr(module, name)
    source = inspect.getsource(original)
    assert source.count(old) == 1, old
    exec(source.replace(old, new), vars(module))
    try:
        yield
    finally:
        setattr(module, name, original)


@contextlib.contextmanager
def declared(change):
    """The adapter reading a changed copy of its declaration (config/semtabfacts_aux_val.json)."""
    semtab = _modules()[0]
    cfg = json.loads(semtab.CONFIG_PATH.read_text(encoding="utf-8"))
    change(cfg)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "semtabfacts_aux_val.json"
        path.write_text(json.dumps(cfg), encoding="utf-8")
        with patched(semtab, "CONFIG_PATH", path):
            yield


@contextlib.contextmanager
def all_of(*managers):
    with contextlib.ExitStack() as stack:
        for m in managers:
            stack.enter_context(m)
        yield


def _error(exc):
    return "error: " + type(exc).__name__


def observe():
    semtab, scitab, cli, ids = _modules()
    out = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        frozen_path = tmp / "frozen.json"
        try:
            frozen = semtab.freeze({"dev": FIXTURES / "dev", "test": FIXTURES / "test"}, frozen_path)
        except Exception as exc:  # noqa: BLE001 - the observation records what broke, never raises
            return {"freeze": _error(exc)}
        out["frozen"] = {"set_name": frozen["set_name"], "benchmark": frozen["benchmark"], "looks": len(frozen["looks"]),
                         "counts": frozen["counts"], "refused_by_reason": frozen["refusals"]["by_reason"],
                         "refusal_rows": [{k: r[k] for k in ("reason", "part", "document", "statements")}
                                          | {"table_id": r.get("table_id"), "statement_id": r.get("statement_id")}
                                          for r in frozen["refusals"]["rows"]],
                         "evidence_marks_stripped": frozen["evidence_marks_stripped"],
                         "grids": {"%s/%s" % (t["document"], t["table_id"]): t["grid"] for t in frozen["tables"]}}
        build = tmp / "bundles"
        try:
            cli.build(semtab, frozen_path, build, development=True)
        except Exception as exc:  # noqa: BLE001
            out["build"] = _error(exc)
            return out
        items = json.loads((build / "items.json").read_text(encoding="utf-8"))
        parts = json.loads((build / "parts.json").read_text(encoding="utf-8"))
        source_of = {i["item_id"]: i["source_item_id"] for i in items["items"]}
        bundles = {}
        for folder in sorted(p for p in build.iterdir() if p.is_dir()):
            key = json.loads((folder / "answer_key.json").read_text(encoding="utf-8"))
            text = (folder / "context" / (folder.name + ".md")).read_text(encoding="utf-8")
            rules = (folder / "conventions" / "rules.md").read_text(encoding="utf-8")
            bundles[folder.name] = {
                "files": sorted(str(p.relative_to(folder)).replace("\\", "/") for p in folder.rglob("*") if p.is_file()),
                "table_lines": [line for line in text.split("\n") if line.startswith("|")],
                "caption_line": text.split("\n")[6] if text.count("\n") > 6 else None,
                "rule_headings_declared": sorted({line.endswith("[compare: cells]") for line in rules.split("\n")
                                                  if line.startswith("## CONV-")}),
                "key_benchmark": key["benchmark"],
                "gold": {source_of[i["item_id"]]: i["gold"] for i in key["items"]}}
        out["bundles"] = {b["gold"] and sorted(b["gold"])[0].rsplit("/", 1)[0]: b for b in bundles.values()}
        out["items"] = {"benchmark": items["benchmark"],
                        "ids": sorted((i["source_item_id"], i["item_id"]) for i in items["items"])}
        out["parts"] = {"benchmark": parts["benchmark"], "input_check_set": parts["input_check"]["set_name"],
                        "sides": sorted({d["side"] for d in parts["documents"]}),
                        "set_names": sorted({d["set_name"] for d in parts["documents"]}),
                        "source_parts": sorted(d["source_part"] for d in parts["documents"])}
        written = [frozen_path] + sorted(p for p in build.rglob("*") if p.is_file())
        out["evidence_in_output"] = sorted(
            str(p.relative_to(tmp)).replace("\\", "/") for p in written
            if any(t in p.read_text(encoding="utf-8") for t in EVIDENCE_TOKENS))
        try:
            scitab.read_source(frozen_path)
            out["scitab_reads_frozen"] = "read"
        except Exception as exc:  # noqa: BLE001
            out["scitab_reads_frozen"] = _error(exc)
        try:
            cli.label(scitab, build / "items.json", "B0")
            out["scitab_labels_items"] = "labelled"
        except Exception as exc:  # noqa: BLE001
            out["scitab_labels_items"] = _error(exc)
        pairs = [("supports", "supports"), ("refutes", "refutes"), ("supports", "not enough info")]
        head = semtab.headline(pairs, setting="3-class")
        out["headline"] = {"measure": head["headline_measure"], "value": round(head["headline_value"], 6),
                           "never_merged_with": head["never_merged_with"]}
    return out


def expected():
    _semtab, _scitab, _cli, ids = _modules()
    t1, t2 = "90001/Table 1", "90002/Table 2"
    sources = [t1 + "/1", t1 + "/2", t1 + "/3", t2 + "/1", t2 + "/2"]
    files = ["answer_key.json", "context/_review_targets.json", "context/%s.md", "conventions/rules.md"]

    def bundle(doc, gold, table_lines, caption):
        name = ids.opaque_document_id("semtabfacts", doc)
        return {"files": sorted(f % name if "%s" in f else f for f in files), "table_lines": table_lines,
                "caption_line": caption, "rule_headings_declared": [True], "key_benchmark": "semtabfacts",
                "gold": gold}
    return {
        "frozen": {"set_name": "semtabfacts_aux_val", "benchmark": "semtabfacts", "looks": 0,
                   "counts": {"documents": 2, "tables": 2, "statements": 5,
                              "by_class": {"not enough info": 2, "refutes": 1, "supports": 2},
                              "by_part": {"dev": {"not enough info": 1, "refutes": 1, "supports": 1},
                                          "test": {"not enough info": 1, "supports": 1}}},
                   "refused_by_reason": {"missing_type": {"files": 0, "tables": 0, "statements": 1},
                                         "span_outside_grid": {"files": 0, "tables": 1, "statements": 2},
                                         "unknown_type": {"files": 0, "tables": 0, "statements": 1}},
                   "refusal_rows": [
                       {"reason": "missing_type", "part": "test", "document": "90002", "statements": 1,
                        "table_id": "Table 2", "statement_id": "3"},
                       {"reason": "span_outside_grid", "part": "test", "document": "90002", "statements": 2,
                        "table_id": "Table 3", "statement_id": None},
                       {"reason": "unknown_type", "part": "test", "document": "90002", "statements": 1,
                        "table_id": "Table 2", "statement_id": "4"}],
                   "evidence_marks_stripped": 3,
                   "grids": {t1: [["Line", "Output", "Output"], ["A", "12.5", "14.0"], ["A", "9.0", "11.5"]],
                             t2: [["Bench", "Width"], ["North", "40"]]}},
        "bundles": {
            t1: bundle(t1, {t1 + "/1": "supports", t1 + "/2": "refutes", t1 + "/3": "not enough info"},
                       ["| Line | Output | Output |", "|---|---|---|", "| A | 12.5 | 14.0 |", "| A | 9.0 | 11.5 |"],
                       "Pump output by line and shift."),
            t2: bundle(t2, {t2 + "/1": "supports", t2 + "/2": "not enough info"},
                       ["| Bench | Width |", "|---|---|", "| North | 40 |"], "Bench sizes.")},
        "items": {"benchmark": "semtabfacts",
                  "ids": sorted((s, ids.opaque_item_id("semtabfacts", s)) for s in sources)},
        "parts": {"benchmark": "semtabfacts", "input_check_set": "semtabfacts_aux_val", "sides": ["development"],
                  "set_names": ["semtabfacts_aux_val"], "source_parts": ["dev", "test"]},
        "evidence_in_output": [],
        "scitab_reads_frozen": "error: ValueError",
        "scitab_labels_items": "error: ValueError",
        "headline": {"measure": "semtabfacts_aux_val 3-class macro-F1 over supports, refutes, not enough info "
                                "(auxiliary validation set)",
                     "value": round((2 / 3 + 1 + 0) / 3, 6), "never_merged_with": ["scitab"]},
    }


def _swap_entailed_refuted(cfg):
    cfg["gold_values"]["entailed"], cfg["gold_values"]["refuted"] = "refutes", "supports"


def proofs():
    semtab = _modules()[0]
    return [
        ("bundle shape: the table as one caption-and-table part", lambda: with_source(
            semtab, "part_text", 'return scitab.caption_line(table["caption"]) + "\\n\\n" + bundle.render_table(header, body)',
            'return bundle.render_table(header, body)')),
        ("spanning cells expanded over their rows and columns", lambda: with_source(
            semtab, "grid", "for c in range(c0, c1 + 1):", "for c in range(c0, c0 + 1):")),
        ("types mapped through the declaration read at call time", lambda: declared(_swap_entailed_refuted)),
        ("evidence marks stripped before any cell is read", lambda: all_of(
            patched(semtab, "strip_evidence", lambda root: 0),
            with_source(semtab, "_cell_text", 'return value if value is not None else "".join(cell.itertext())',
                        'return value + "".join(" [%s]" % e.get("type") for e in cell.iter(EVIDENCE_TAG))'))),
        ("a span outside the grid refused and counted", lambda: with_source(
            semtab, "grid", "if r0 < 0 or c0 < 0 or r1 >= height:", "if r0 < 0 or c0 < 0:")),
        ("a missing type refused and counted", lambda: with_source(
            semtab, "_statements", "else MISSING_TYPE if not key", "else UNKNOWN_TYPE if not key")),
        ("an unknown type value refused and counted", lambda: with_source(
            semtab, "_statements", "else UNKNOWN_TYPE if key not in gold_values else None)",
            "else None if key not in gold_values else None)")),
        ("its own benchmark name and ids, apart from SciTab", lambda: patched(semtab, "BENCHMARK", "scitab")),
        ("its own set name on the headline", lambda: declared(lambda cfg: cfg.update(set_name="scitab_aux_val"))),
    ]


def validate():
    return all((FIXTURES / p).is_file() for p in ("dev/90001.xml", "test/90002.xml")) and _modules()[0].CONFIG_PATH.is_file()


def run_check(number=585):
    rows = proofs()
    for name, neutralise in rows:
        prove_effect(name=name, validate=validate, observe=observe,
                     check=lambda name=name: ("PASS" if observe() == expected() else "FAIL", name),
                     neutralise=neutralise)
    return "PASS", ("%d proofs, each neutralise, fail, restore, pass: SEM-TAB-FACTS dev and test freeze to one set "
                    "(semtabfacts_aux_val) and build SciTab's claim-against-a-table bundle with spans expanded, "
                    "types mapped from config, evidence stripped, refusals counted by reason, and the set apart "
                    "from SciTab" % len(rows))


if __name__ == "__main__":
    print(run_check())
