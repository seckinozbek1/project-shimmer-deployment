"""Re-screen the answers a saved run KEPT on a judged path with today's
`paired_review.judged_item_refusal` (R1, operator decision D-S22 item 1 (d)).

Reads only saved artifacts: the run's pairing map (`audit/pairing_map.json`, for each unit's
parsed fields), its bus (`logs/agent_bus.jsonl`, Python's stamped copies of the kept answers:
`stamped_by: python` with `judged_path: uncomputable`, `passage_pair` or `cell_claim`, or `absence_path: judged`) and the
workload the run was sealed from (`_review_targets.json` and `context/`, for the unit text the
quote check reads, and for whether an earlier version is declared: a file the manifest's
`prior` list names (role_resolution.manifest_prior) that is in `context/` and is not itself a
target; this re-states `pipeline._prior_docs_for`'s rule and does not call it). No model, no network, no answer key, no label, no
score: it counts records and names them by item id, never by text.

Usage:
  py -3.12 tools/judged_rescreen.py --out OUT.json RUN_DIR WORKLOAD_DIR [RUN_DIR WORKLOAD_DIR ...]

RUN_DIR is a run folder (holding audit/ and logs/); its benchmark is read from the first name
of the form NN_<benchmark>_<id>_<arm> on its path.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pairing_map  # noqa: E402
import paired_review  # noqa: E402
import role_resolution  # noqa: E402

KINDS = {paired_review.NO_QUOTE_ABSENCE_RELATION: "a_absence_no_quote",
         paired_review.NO_FIGURES_FIGURE_RELATION: "b_figure_no_figures",
         paired_review.PRIOR_RELATION_NO_EARLIER_VERSION: "c_prior_undeclared",
         paired_review.CONTRADICTION_NOT_IRREGULAR: "d_contradiction_not_irregular",
         paired_review.CONTRADICTION_NEEDS_TWO_QUOTES: "e_contradiction_one_quote",
         paired_review.CONTRADICTION_NO_UNIT_TEXT: "e_contradiction_no_unit_text",
         paired_review.CONTRADICTION_QUOTE_TOO_SHORT: "e_contradiction_short_quote",
         paired_review.CONTRADICTION_SECOND_QUOTE_NOT_IN_UNIT: "f_contradiction_second_quote",
         paired_review.CONTRADICTION_SAME_PASSAGE: "g_contradiction_one_passage",
         paired_review.CONTRADICTION_SECOND_UNIT_NOT_CHECKED: "h_contradiction_second_unit",
         paired_review.CLAIM_NOT_FROM_CELLS: "i_claim_no_selection",
         paired_review.CLAIM_RULE_NOT_CELLS: "i_claim_rule_not_cells",
         paired_review.CLAIM_NOT_IRREGULAR: "i_claim_not_irregular",
         paired_review.CLAIM_NOT_THE_RULE: "i_claim_not_the_rule",
         paired_review.CLAIM_CELLS_NOT_IN_UNIT: "i_claim_cells_not_in_unit",
         paired_review.RULE_NOT_MET_NOT_FROM_RULE_CHECK: "i_rule_not_met_no_rule_check",
         paired_review.RULE_NOT_MET_PLAN_NOT_UNCOMPUTABLE: "i_rule_not_met_plan_not_uncomputable",
         paired_review.RULE_NOT_MET_NOT_IRREGULAR: "i_rule_not_met_not_irregular",
         paired_review.RULE_NOT_MET_QUOTE_NOT_UNIT: "i_rule_not_met_quote_not_unit"}
_ENTRY = re.compile(r"^\d+_([a-z0-9]+)_[0-9a-f]+_B\d$")


def benchmark_of(run_dir: Path) -> str:
    for part in run_dir.resolve().parts:
        m = _ENTRY.match(part)
        if m:
            return m.group(1)
    return "unknown"


def repo_relative(path: Path) -> str:
    """The path relative to the repository (checkout) that holds it, with forward slashes;
    as given when no enclosing checkout is found."""
    path = Path(path).resolve()
    for parent in path.parents:
        if (parent / ".git").exists():
            return path.relative_to(parent).as_posix()
    return str(path)


def kept_items(run_dir: Path):
    """Python's stamped copies of the answers kept on a judged path, once per item id."""
    seen, out = set(), []
    with (run_dir / "logs" / "agent_bus.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                body = json.loads(line).get("body") or {}
            except ValueError:
                continue
            if body.get("event") != "AGENT_OUTPUT" or body.get("stamped_by") != "python":
                continue
            payload = body.get("payload") or {}
            for item in payload.get("items") or []:
                if not isinstance(item, dict):
                    continue
                written = item.get(paired_review.JUDGED_PATH_FIELD)
                path = ("uncomputable" if written == paired_review.JUDGED_PATH_UNCOMPUTABLE
                        else "passage_pair" if written == paired_review.JUDGED_PATH_PASSAGE_PAIR
                        else "cell_claim" if written == paired_review.JUDGED_PATH_CELL_CLAIM
                        else "absence_judged" if item.get("absence_path") == "judged" else None)
                key = item.get("item_id")
                if path is None or key in seen:
                    continue
                seen.add(key)
                out.append((path, item))
    return out


def rescreen(run_dir: Path, workload: Path) -> dict:
    run_dir, workload = Path(run_dir), Path(workload)
    maps = json.loads((run_dir / "audit" / "pairing_map.json").read_text(encoding="utf-8"))
    manifest = json.loads((workload / "_review_targets.json").read_text(encoding="utf-8"))
    context = workload / "context"
    names = {p.name for p in context.iterdir() if p.is_file()}
    targets = role_resolution.manifest_targets(manifest)
    # The rule pipeline._prior_docs_for applies, re-stated: declared, present, not a target.
    prior_declared = bool((role_resolution.manifest_prior(manifest) - targets) & names)
    units, fields = {}, {}
    for doc_id, entry in maps.items():
        source = next((context / n for n in sorted(targets) if Path(n).stem == doc_id), None)
        if source is None or not source.is_file():
            raise SystemExit("no target document for %s in %s" % (doc_id, context))
        text = source.read_text(encoding="utf-8")
        for unit in pairing_map.split_units(text, document_id=doc_id):
            units[unit["unit_id"]] = unit.get("text", "")
        for unit in entry.get("units") or []:
            fields[unit.get("unit_id")] = unit.get("fields_present") or []
    refused = []
    by_kind = {k: 0 for k in KINDS.values()}
    by_path = {}
    other = 0
    kept = kept_items(run_dir)
    for path, item in kept:
        by_path[path] = by_path.get(path, 0) + 1
        # A saved cell record holds its own cells and claim, and the bus keeps no selection or rule
        # text: what can be read again is whether those cells stand in the unit.
        cell = path == "cell_claim"
        rule = ({"id": item.get("rule_id"), "compare": "cells", "rule": item.get("quote_b")} if cell
                else {"id": item.get("rule_id")})
        reason = paired_review.judged_item_refusal(
            item, rule, fields.get(item.get("unit_id")),
            units.get(item.get("unit_id"), ""), prior_declared=prior_declared,
            second_unit_text=units.get(item.get("compared_unit_id")),
            selected_cells=item.get("quote") if cell else None)
        if reason is None:
            continue
        kind = KINDS.get(reason, "other:" + reason)
        if kind in by_kind:
            by_kind[kind] += 1
        else:
            other += 1
        refused.append({"item_id": item.get("item_id"), "unit_id": item.get("unit_id"),
                        "rule_id": item.get("rule_id"), "source_rule_id": item.get("source_rule_id"),
                        "relation": item.get("relation"), "path": path, "kind": kind})
    return {"run": repo_relative(run_dir), "benchmark": benchmark_of(run_dir),
            "prior_declared": prior_declared, "kept_before": len(kept), "kept_by_path": by_path,
            "refused_now": len(refused), "refused_by_kind": by_kind, "refused_other": other,
            "kept_after": len(kept) - len(refused), "refused": refused}


def summarise(runs):
    out = {}
    for r in runs:
        b = out.setdefault(r["benchmark"], {"runs": 0, "kept_before": 0, "refused_now": 0,
                                            "refused_by_kind": {k: 0 for k in KINDS.values()},
                                            "refused_other": 0, "kept_after": 0})
        b["runs"] += 1
        for key in ("kept_before", "refused_now", "refused_other", "kept_after"):
            b[key] += r[key]
        for k, n in r["refused_by_kind"].items():
            b["refused_by_kind"][k] += n
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True)
    parser.add_argument("pairs", nargs="+", help="RUN_DIR WORKLOAD_DIR, repeated")
    args = parser.parse_args(argv)
    if len(args.pairs) % 2:
        parser.error("give a WORKLOAD_DIR for every RUN_DIR")
    runs = [rescreen(Path(a), Path(b)) for a, b in zip(args.pairs[::2], args.pairs[1::2])]
    report = {"rule": "paired_review.judged_item_refusal (R1, D-S22 item 1 (d))",
              "reasons": {v: k for k, v in KINDS.items()},
              "by_benchmark": summarise(runs), "runs": runs}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name, b in sorted(report["by_benchmark"].items()):
        print("%s runs=%d kept_before=%d refused_now=%d %s other=%d kept_after=%d" % (
            name, b["runs"], b["kept_before"], b["refused_now"],
            " ".join("%s=%d" % kv for kv in sorted(b["refused_by_kind"].items())),
            b["refused_other"], b["kept_after"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
