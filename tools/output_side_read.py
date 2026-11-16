"""The output side's development measurement, read (D-663 (b), D-672, docs/loop/stages/PARSE_SWEEP_DEV_MEASUREMENT.md):
counts only, from the two passes' saved records, never a text. No model and no provider.

    py -3.12 -X utf8 tools/output_side_read.py --before ANSWERS_BEFORE.json --after ANSWERS_AFTER.json \
        --after-run PASS_FOLDER --out OUT.json

ANSWERS_* are tools/reread_replies.py `advisor` outputs of the two passes (the same score-time reader for both,
so the only difference is the output side); PASS_FOLDER is the after pass's folder (replay_measurement.json and
audit/model_replies/). Per group (system_advice, validate, system_audit, judge) it reports:
- drops by field and reason, before and after (`drops` of every row, summed), several_objects_last_read apart
  (a count, never a drop), and the rows read;
- after only, from the reply records: the schema constraint's steps, interventions, first intervention step and
  dead ends per call; the choice decisions' declared mass, ties (unsettled), the share whose top answer was also
  the model's own top token over the whole vocabulary, and the top answer's probability in the plan's bins;
- seconds per call and per group, from the measurement rows;
- the bar written before the run: after, no drop on system_advice and validate except not_asked; no unsettled
  audit or judge decision but ties; no dead end. A bar line not met is named, with the count.
Standard library only.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

SCHEMA = "output-side-read-v1"
SCHEMA_GROUPS = ("system_advice", "validate")
CHOICE_GROUPS = ("system_audit", "judge")
NOT_ASKED = "not_asked"
SEVERAL = "several_objects_last_read"
TIE = "tie"
BINS = ((0.33, 0.5), (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0))
MEASUREMENT_FILE = "replay_measurement.json"
AUDIT_FIELD, AUDIT_GROUP = "audit", "system_audit"


def _bin(p):
    for lo, hi in BINS:
        if lo <= p < hi or (hi == 1.0 and p == 1.0):
            return "%.2f-%.2f" % (lo, hi)
    return "below-0.33"


def top_is_model_top(decision):
    """True when the top declared answer was also the likeliest token of the whole vocabulary: its share of the
    declared answers times the declared mass is above the likeliest undeclared token's probability."""
    probs = [float(a.get("probability") or 0) for a in decision.get("answers") or []]
    mass = decision.get("declared_mass")
    if not probs or not isinstance(mass, (int, float)):
        return False
    other = (decision.get("undeclared_top") or {}).get("probability")
    return other is None or max(probs) * float(mass) > float(other)


def drops_by_group(answers):
    """{group: {rows, drops: {field: {reason: n}}, several}} of an answers file. The reader counts the auditor's
    drops on the advice row they audit (field `audit`); they are the system_audit group's and counted there."""
    out = defaultdict(lambda: {"rows": 0, "drops": defaultdict(Counter), "several": 0})
    for row in answers.get("rows") or []:
        out[row.get("group")]["rows"] += 1
        for field, reasons in (row.get("drops") or {}).items():
            block = out[AUDIT_GROUP if field == AUDIT_FIELD else row.get("group")]
            for reason, n in (reasons or {}).items():
                if reason == SEVERAL:
                    block["several"] += n
                else:
                    block["drops"][field][reason] += n
    return {g: {"rows": b["rows"], "several": b["several"], "drops": {f: dict(c) for f, c in b["drops"].items()},
                "dropped": sum(sum(c.values()) for c in b["drops"].values())} for g, b in out.items()}


def after_records(run_dir):
    run_dir = Path(run_dir)
    measurement = json.loads((run_dir / MEASUREMENT_FILE).read_text(encoding="utf-8"))
    records = {}
    folder = run_dir / "audit" / "model_replies"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        record = json.loads(path.read_text(encoding="utf-8"))
        records[record.get("call_id")] = record
    groups = defaultdict(lambda: {"calls": 0, "failed": 0, "seconds": 0.0, "constrained": 0, "steps": 0,
                                  "interventions": 0, "calls_with_intervention": 0, "first_intervention_steps": [],
                                  "dead_ends": 0, "decisions": 0, "ties": 0, "unsettled_not_tie": 0,
                                  "top_is_model_top": 0, "declared_mass": [], "top_bins": Counter()})
    for row in measurement.get("rows") or []:
        g = groups[row.get("group")]
        g["calls"] += 1
        g["seconds"] += float(row.get("seconds") or 0)
        record = records.get(row.get("call_id")) or {}
        if row.get("failure") or not record.get("backend_ok", False):
            g["failed"] += 1
        constraint = record.get("decoding_constraint")
        if isinstance(constraint, dict):
            g["constrained"] += 1
            g["steps"] += int(constraint.get("steps") or 0)
            g["interventions"] += int(constraint.get("interventions") or 0)
            if constraint.get("interventions"):
                g["calls_with_intervention"] += 1
            if constraint.get("first_intervention_step") is not None:
                g["first_intervention_steps"].append(int(constraint["first_intervention_step"]))
            g["dead_ends"] += 1 if constraint.get("dead_end") else 0
        decision = record.get("decision")
        if isinstance(decision, dict):
            g["decisions"] += 1
            if decision.get("why") == TIE:
                g["ties"] += 1
            elif not decision.get("settled", True) and decision.get("why") != "no_threshold":
                g["unsettled_not_tie"] += 1
            probs = [float(a.get("probability") or 0) for a in decision.get("answers") or []]
            top = max(probs) if probs else 0.0
            g["top_bins"][_bin(top)] += 1
            mass = decision.get("declared_mass")
            if isinstance(mass, (int, float)):
                g["declared_mass"].append(float(mass))
                if top_is_model_top(decision):
                    g["top_is_model_top"] += 1
    out = {}
    for name, g in groups.items():
        masses = sorted(g.pop("declared_mass"))
        firsts = sorted(g.pop("first_intervention_steps"))
        g["top_bins"] = dict(g["top_bins"])
        g["seconds"] = round(g["seconds"], 3)
        g["seconds_per_call"] = round(g["seconds"] / g["calls"], 3) if g["calls"] else None
        g["declared_mass_median"] = masses[len(masses) // 2] if masses else None
        g["declared_mass_min"] = masses[0] if masses else None
        g["first_intervention_step_median"] = firsts[len(firsts) // 2] if firsts else None
        out[name] = g
    return out


def bar(after_drops, records):
    lines = []
    for group in SCHEMA_GROUPS:
        drops = (after_drops.get(group) or {}).get("drops") or {}
        n = sum(v for reasons in drops.values() for r, v in reasons.items() if r != NOT_ASKED)
        lines.append({"line": "%s: no drop but not_asked" % group, "count": n, "met": n == 0})
    for group in CHOICE_GROUPS:
        n = (records.get(group) or {}).get("unsettled_not_tie", 0)
        lines.append({"line": "%s: no unsettled decision but ties" % group, "count": n, "met": n == 0})
    dead = sum(g.get("dead_ends", 0) for g in records.values())
    lines.append({"line": "no dead end", "count": dead, "met": dead == 0})
    missing = [g for g in SCHEMA_GROUPS + CHOICE_GROUPS if not (records.get(g) or {}).get("calls")]
    lines.append({"line": "every group ran in the after pass", "count": len(missing), "met": not missing})
    return {"lines": lines, "met": all(l["met"] for l in lines)}


def read(before, after, after_run):
    b, a = drops_by_group(before), drops_by_group(after)
    records = after_records(after_run)
    return {"schema": SCHEMA, "before": b, "after": a, "after_records": records, "bar": bar(a, records),
            "change_in_drops": {g: (a.get(g, {}).get("dropped", 0) - b.get(g, {}).get("dropped", 0))
                                for g in sorted(set(a) | set(b))},
            "reads": "counts only: answers files of tools/reread_replies.py and the after pass's records"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--after-run", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    value = read(load(args.before), load(args.after), args.after_run)
    args.out.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"bar_met": value["bar"]["met"], "change_in_drops": value["change_in_drops"]}))
    return 0 if value["bar"]["met"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
