"""The ontology store's first reader (ontology chain, job 1).

WHAT THIS IS. `ontology/stores/` has been written at the end of every run since
build B1 and read back by nothing: `graph.json` and `gnn_state.json` are derived
from it and consumed by no agent, no phase and no deliverable. This module is the
first read path that exists for a human rather than for the next write. It answers
one question, the one the store can actually answer today: WHICH AGENT PRODUCED
WHICH FINDING UNDER WHICH RULE, and when, in which run.

WHAT IT IS GOOD FOR, stated here so the route and the console do not have to
overclaim. Three things, all modest:

  1. Attribution after the fact. A provision captured from a past run names the
     agent whose Finding the amendment rested on, the rule that governed it and
     the run it came from. That is an audit answer ("who said this, under what
     rule, when"), not an analytical one.
  2. Coverage. Which rules and which agents the store has ever seen, so an
     operator can tell that a rule has never produced a captured provision, which
     usually means it never fired rather than that it always passed.
  3. Proof the store is not write-only. Until now nothing could show an operator
     what was held. A store nobody can inspect is indistinguishable from a store
     that is silently broken.

WHAT IT IS NOT. It is not retrieval, not relevance, not a cross-run signal the
review draws on, and it does not make any past finding easier to find again while
reviewing. It reads provenance of things already decided. The long-range case (a
term defined at the start of a document and used at the end) is untouched by it:
that needs relations BETWEEN provisions, which the store does not hold.

NOT MEASURED, and cannot be today: the store is empty (`provisions.jsonl` is zero
bytes at this commit) because the only writer is run-end capture and no run has
been made since the store was scoped. Every function here is proved on fixtures
in the verify gate. The first real content arrives on the first run after the
move to a GPU box. Nothing here is known to be useful on real content; it is
known to be correct on fixtures.

Deterministic, local, stdlib only, no model calls, read-only: nothing in this
module writes any store file.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import ontology_store
from ontology_store import DEFAULT_SCOPE

ROOT = Path(__file__).resolve().parent.parent
OGE_STORES_DIR = ROOT / "ontology" / "stores"

# The provenance fields a reader surfaces. Deliberately not the whole record: a
# provision's own text (original_text / proposed_text / comment) is content, and
# this reader's whole subject is provenance, so the summary carries identifiers
# and never a passage. A caller that wants the text reads the record itself.
SUMMARY_FIELDS = ("id", "document_id", "ref_id", "convention_ref", "agent", "run",
                  "time", "revision", "stub")


def _provenance_of(record):
    """The provenance struct of a stored record, or an empty dict. A record written
    before the struct existed (or a hand-written fixture) carries none; that is
    reported as absent rather than filled in with a guess."""
    p = record.get("provenance")
    return p if isinstance(p, dict) else {}


def summarize_record(record):
    """One stored provision as a flat provenance summary: who produced it, under
    which rule, in which run, at which revision. Carries no provision text."""
    prov = _provenance_of(record)
    return {
        "id": record.get("id"),
        "document_id": record.get("document_id"),
        "ref_id": record.get("ref_id"),
        "convention_ref": record.get("convention_ref"),
        "agent": prov.get("agent"),
        "run": prov.get("run"),
        "time": prov.get("time"),
        "revision": record.get("revision"),
        "stub": bool(record.get("stub")),
    }


def read_store(stores_dir=None, *, scope=DEFAULT_SCOPE, live_path=None):
    """Open the scoped store read-only. Separate from the summary functions so a
    caller (the route, the CLI, a gate check) binds the scope once, the way every
    other reader of this layer does."""
    d = Path(stores_dir) if stores_dir else OGE_STORES_DIR
    return ontology_store.ProvisionStore(
        live_path=Path(live_path) if live_path else d / ontology_store.LIVE_FILENAME,
        scope=scope)


def provenance_summary(store, *, limit=None):
    """The store's provenance, read through the scoped storage layer.

    Returns counts plus a flat list of per-provision summaries, newest capture
    first (by the provenance time, which the capture hook stamps; records with no
    time sort last rather than being dropped). `limit` caps the list only; the
    counts always describe the whole scope, so a truncated list never makes the
    store look smaller than it is.

    An EMPTY store returns zeros and an empty list, which is the honest answer and
    the state of every store in this repository today. It is not an error.
    """
    records = store.current()
    rows = [summarize_record(r) for r in records]
    rows.sort(key=lambda r: (r["time"] is None, r["time"] or "", r["id"] or ""), reverse=False)
    rows.reverse()
    by_agent = Counter(r["agent"] for r in rows if r["agent"])
    by_rule = Counter(r["convention_ref"] for r in rows if r["convention_ref"])
    by_run = Counter(r["run"] for r in rows if r["run"])
    return {
        "scope": store.scope,
        "provision_count": len(rows),
        "stub_count": sum(1 for r in rows if r["stub"]),
        "without_provenance": sum(1 for r in rows if not r["agent"] and not r["run"]),
        "agents": [{"agent": a, "provisions": n} for a, n in by_agent.most_common()],
        "rules": [{"convention_ref": c, "provisions": n} for c, n in by_rule.most_common()],
        "runs": [{"run": r, "provisions": n} for r, n in by_run.most_common()],
        "superseded_in_live": len(store.superseded()),
        "log_events": len(store.log_entries()),
        "provisions": rows[:limit] if limit else rows,
        "truncated": bool(limit and len(rows) > limit),
    }


def provision_history(store, provision_id):
    """Every revision of one provision id in this scope, oldest first, as provenance
    summaries. This is what makes supersession legible to a human: the storage layer
    has recorded it since W7 and nothing could show it."""
    return [summarize_record(r) for r in store.history(provision_id)]


def render_text(summary, *, history=None):
    """The human-readable rendering used by the CLI inspector. Plain text, no colour,
    no table library: it is read in a terminal and pasted into a report."""
    lines = []
    lines.append("Ontology store, scope %s" % summary["scope"])
    if summary["provision_count"] == 0:
        lines.append("")
        lines.append("  EMPTY. No provision has been captured in this scope.")
        lines.append("  The only writer is run-end capture, so an empty store means no run has")
        lines.append("  finished since the store was created, not that anything is broken.")
        return "\n".join(lines)
    lines.append("")
    lines.append("  provisions: %d (%d stubs, %d without provenance)"
                 % (summary["provision_count"], summary["stub_count"],
                    summary["without_provenance"]))
    lines.append("  superseded revisions still in the live store: %d"
                 % summary["superseded_in_live"])
    lines.append("  log events: %d" % summary["log_events"])
    if summary["agents"]:
        lines.append("")
        lines.append("  by agent:")
        for a in summary["agents"]:
            lines.append("    %-24s %d" % (a["agent"], a["provisions"]))
    if summary["rules"]:
        lines.append("")
        lines.append("  by rule:")
        for c in summary["rules"]:
            lines.append("    %-24s %d" % (c["convention_ref"], c["provisions"]))
    if summary["runs"]:
        lines.append("")
        lines.append("  by run:")
        for r in summary["runs"]:
            lines.append("    %-24s %d" % (r["run"], r["provisions"]))
    lines.append("")
    lines.append("  provisions (newest capture first):")
    for r in summary["provisions"]:
        lines.append("    %s" % (r["id"] or "(no id)"))
        lines.append("      rule %s, agent %s, run %s, revision %s%s"
                     % (r["convention_ref"] or "none", r["agent"] or "none",
                        r["run"] or "none", r["revision"],
                        ", stub" if r["stub"] else ""))
    if summary["truncated"]:
        lines.append("    ... list truncated; the counts above describe the whole scope")
    if history:
        lines.append("")
        lines.append("  history of %s (oldest first):" % history[0]["id"])
        for h in history:
            lines.append("    revision %s: agent %s, run %s, time %s"
                         % (h["revision"], h["agent"] or "none", h["run"] or "none",
                            h["time"] or "none"))
    return "\n".join(lines)


def main(argv=None):
    """The operator's inspect-at-any-point path: read what the store holds, now,
    without starting a run and without loading a model.

        py -3.9 -X utf8 scripts/ontology_reader.py
        py -3.9 -X utf8 scripts/ontology_reader.py --json
        py -3.9 -X utf8 scripts/ontology_reader.py --provision "<document>::<REF-0001>"
    """
    import argparse

    ap = argparse.ArgumentParser(
        description="Inspect what the ontology store holds (read-only, no run, no model).")
    ap.add_argument("--stores-dir", default=None,
                    help="override ontology/stores (a test or a copied store)")
    ap.add_argument("--scope", default=DEFAULT_SCOPE, help="storage scope to read")
    ap.add_argument("--provision", default=None,
                    help="also show every revision of this provision id")
    ap.add_argument("--limit", type=int, default=None, help="cap the provision list")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = ap.parse_args(argv)

    store = read_store(args.stores_dir, scope=args.scope)
    summary = provenance_summary(store, limit=args.limit)
    history = provision_history(store, args.provision) if args.provision else None
    if args.json:
        out = dict(summary)
        if history is not None:
            out["history"] = history
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(render_text(summary, history=history))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
