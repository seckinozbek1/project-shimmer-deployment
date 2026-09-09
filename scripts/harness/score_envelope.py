"""Score a batch of harness results: compliance, verdict accuracy, latency.

Envelope compliance is the fraction of calls that came back as a valid canonical
envelope (INFRA-037) with no missing contract field. It is deliberately not the
same as "the agent said something useful": an empty but valid envelope is a
legitimate hold and counts as compliant, because that is what the contract says.

Verdict accuracy is scored only where the caller supplied an expected verdict,
per agent per case, in the harness's own case list. Nothing here reads the
operator's answer key; the expected value is whatever the harness was told.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

VERDICT_FIELDS = ("verdict", "status", "result", "assessment")


def verdict_of(item):
    """The item's verdict field, as a lowercase string, or None."""
    if not isinstance(item, dict):
        return None
    for field in VERDICT_FIELDS:
        v = item.get(field)
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
    return None


def verdicts_in(record):
    parsed = record.get("parsed") or {}
    items = parsed.get("items") or []
    return [v for v in (verdict_of(i) for i in items) if v]


def score(records, expected=None):
    """records: run_agent result dicts. expected: {unit_id: verdict} or None."""
    expected = {k: str(v).lower() for k, v in (expected or {}).items()}
    by_key = defaultdict(list)
    for r in records:
        by_key[(r.get("agent", "?"), r.get("profile", "?"), r.get("model") or "-")].append(r)

    rows = []
    for (agent, profile, model), rs in sorted(by_key.items()):
        compliant = sum(1 for r in rs if r.get("envelope_ok"))
        latencies = [r.get("latency_s", 0.0) for r in rs]
        judged = graded = 0
        for r in rs:
            want = expected.get(r.get("unit_id"))
            if not want:
                continue
            got = verdicts_in(r)
            if not got:
                judged += 1
                continue
            judged += 1
            if any(want == g or want in g for g in got):
                graded += 1
        rows.append({
            "agent": agent,
            "profile": profile,
            "model": model,
            "calls": len(rs),
            "envelope_compliant": compliant,
            "envelope_compliance_rate": round(compliant / len(rs), 3) if rs else 0.0,
            "backend_errors": sum(1 for r in rs if r.get("error") == "backend_error"
                                  or (r.get("error") and not r.get("ok")
                                      and r.get("error") != "contract_violation")),
            "contract_violations": sum(1 for r in rs if r.get("error") == "contract_violation"),
            "items_total": sum(r.get("item_count", 0) for r in rs),
            "verdicts_judged": judged,
            "verdicts_correct": graded,
            "verdict_accuracy": round(graded / judged, 3) if judged else None,
            "median_latency_s": round(statistics.median(latencies), 3) if latencies else 0.0,
        })
    return rows


def render(rows):
    out = ["%-26s %-6s %-24s %5s %8s %8s %9s" % (
        "agent", "prof", "model", "calls", "envelope", "verdict", "median s")]
    for r in rows:
        out.append("%-26s %-6s %-24s %5d %7.0f%% %8s %9.1f" % (
            r["agent"], r["profile"], r["model"][:24], r["calls"],
            100 * r["envelope_compliance_rate"],
            "-" if r["verdict_accuracy"] is None else "%.0f%%" % (100 * r["verdict_accuracy"]),
            r["median_latency_s"]))
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("results", help="JSON file of run_agent result records")
    p.add_argument("--expected", default=None,
                   help="JSON file mapping unit_id to the expected verdict")
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)

    records = json.loads(Path(a.results).read_text(encoding="utf-8"))
    expected = json.loads(Path(a.expected).read_text(encoding="utf-8")) if a.expected else None
    rows = score(records, expected)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print(render(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
