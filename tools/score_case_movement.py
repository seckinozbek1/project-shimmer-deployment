#!/usr/bin/env python3
"""Score a multi-round case's computed gaps between the parties against an expected-movement key.

The key (for example benchmark/dev_cases/host_agreement_three_rounds/EXPECTED_MOVEMENT.json) gives,
per declared issue and pair of consecutive rounds, `moved_toward`, `moved_away`,
`unchanged_from_prior` or `not_computed`. The run's own rows are `position_gaps` in its
audit/multi_round.json. Only the scorer reads a key.

    py -3.12 tools/score_case_movement.py --run <run folder> --key <EXPECTED_MOVEMENT.json>
"""
import argparse
import json
from pathlib import Path


def score(rows, key):
    """{"rows": [...], "per_issue": {issue: (matched, of)}, "matched", "of"}. A key entry the run has no
    row for counts as missed; a run row the key does not name is listed apart."""
    by_pair = {(r["issue_id"], tuple(r["rounds"])): r for r in rows}
    out, per_issue, unkeyed = [], {}, []
    for issue, entries in key["issues"].items():
        for entry in entries:
            row = by_pair.pop((issue, tuple(entry["rounds"])), None)
            got = row["outcome"] if row else "no_row"
            ok = got == entry["expected"]
            out.append({"issue_id": issue, "rounds": entry["rounds"], "expected": entry["expected"], "got": got, "ok": ok})
            hit, total = per_issue.get(issue, (0, 0))
            per_issue[issue] = (hit + ok, total + 1)
    unkeyed = [{"issue_id": k[0], "rounds": list(k[1]), "got": r["outcome"]} for k, r in sorted(by_pair.items())]
    return {"rows": out, "per_issue": per_issue, "matched": sum(r["ok"] for r in out), "of": len(out),
            "unkeyed": unkeyed}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    args = parser.parse_args(argv)
    record = json.loads((args.run / "audit" / "multi_round.json").read_text(encoding="utf-8"))
    result = score(record.get("position_gaps") or [], json.loads(args.key.read_text(encoding="utf-8")))
    for row in result["rows"]:
        print("%-24s %s  expected %-21s got %-21s %s" % (row["issue_id"], "-".join(row["rounds"]), row["expected"],
                                                         row["got"], "ok" if row["ok"] else "MISS"))
    for issue, (hit, total) in result["per_issue"].items():
        print("issue %-24s %d of %d" % (issue, hit, total))
    print("matched %d of %d; rows the key does not name: %d" % (result["matched"], result["of"], len(result["unkeyed"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
