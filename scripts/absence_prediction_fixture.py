"""The declared-input fixture behind check 253 (quote prediction checked against actual run outcomes),
in its own module so a single-check file can run it without the gate (scripts/absence_reask_checks.py).
It runs the real phase 5.5 planning, quoting, bus and summary on declared documents with an injected
reply function; no model call, no network, a temporary run folder."""
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def measure(case="forecast", require=None):
    """Declared parsed inputs through real planning, quoting, bus and summary. `require(condition, what)`
    states the fixture's own premises (the gate passes its _require_fixture)."""
    if require is None:
        def require(condition, what):
            if not condition:
                raise AssertionError("the fixture's own input is not as intended: " + what)
    import asyncio
    import absence_prediction as ap
    import agent_wrapper as aw
    import convention_parser as cp
    import finding_record as fr
    import paired_review as pr
    import pairing_map as pm
    import pipeline as pl
    import reference_builder as rb
    from harness.run_agent import build_orchestrator
    from unittest.mock import patch
    with tempfile.TemporaryDirectory(prefix="shimmer_absence_prediction_") as td:
        root = Path(td)
        conventions = root / "declared.md"
        conventions.write_text(
            "## CONV-ZQ01 , conv-zq01 [required] [scope: entry]\n\n"
            "An entry carries an auxiliary mark when applicable.\n\n"
            "## CONV-ZQ02 , conv-zq02 [required] [scope: computed] [requires: seal]\n\n"
            "A computed entry requires a seal.\n", encoding="utf-8")
        rules = [r.as_dict() for r in cp._parse_text(conventions, [0])]
        require(len(rules) == 2 and pm.scope_declaration(rules[0])
                         and not pm.required_declaration(rules[0])
                         and pm.required_declaration(rules[1]),
                         "two parsed declared rules, one judged and one computed")
        sizes = [("first", 5, 5), ("second", 9, 2)] if case != "changed" else [("first", 3, 1)]
        docs = [{"id": name, "name": name + ".md", "text": "\n\n".join(
            "## Item %s\n\nEntry: yes.%s" % (i, "\nComputed: yes." if i < computed else "")
            for i in range(size))} for name, size, computed in sizes]
        for doc, (_, size, computed) in zip(docs, sizes):
            mapping = pm.build_pairing_map(doc["text"], rules, document_id=doc["id"])
            units = pr.unit_texts_for(doc["text"], doc["id"])
            pairs, dropped = pr.pairs_from_map(mapping, cap_per_unit=None)
            plans = pr.plan_calls(units, pairs, {r["id"]: r for r in rules},
                                  pm.field_vocabulary(list(units.values())))
            require(not dropped and sum(p["kind"] == "absence_judged" for p in plans) == size
                             and sum(p["kind"] == "absence_computed" for p in plans) == computed,
                             "declared documents produce the intended judged/computed plan counts")
        declared = {"kind": "finding", "record_verdict": "irregular", "relation": "missing_field",
                    "rule_id": rules[0]["id"], "unit_id": "declared", "stated_field": "auxiliary",
                    "value_a": None, "unit_a": "", "value_b": None, "unit_b": "",
                    "source_refs": ["REF-0001"], "quote": "Entry: yes.", "explanation": "Declared reply."}
        require(fr.is_finding(declared), "the injected reply is a typed Finding")
        orch = build_orchestrator(root=ROOT, out_root=root / "phase")
        index = rb.ReferenceIndex.open(ROOT, index_path=root / "refs.json")
        calls = []
        pending_seen = []

        async def respond(wrapper, payload, *args, **kwargs):
            calls.append(payload["document_text"])
            before = ap.read_report(orch.run_context.run_dir)
            pending_seen.append(bool(before and before["status"] == "incomplete"))
            if case == "interrupted" and len(calls) == 2:
                raise RuntimeError("declared interruption")
            item = dict(declared)
            if case in ("forecast", "changed", "interrupted", "failed"):
                variant = (len(calls) - 1) % 4
                if variant == 1:
                    item.pop("quote")
                elif variant == 2:
                    item["quote"] = "These words are absent."
                elif variant == 3:
                    item["stated_field"] = "entry"
            if case == "other":
                item["relation"] = "above_band"
                item.pop("quote")
            ok = not (case == "failed" and len(calls) == 1)
            items = [] if case == "empty" or not ok else [item]
            return {"ok": ok, "parsed": {"agent": wrapper.name, "items": items},
                    "backend": "fixture", "model": "fixture", "call_id": "fixture-%s" % len(calls)}

        assignment = None
        if case == "no_consumer":
            assignment = {"by_rule": {r["id"]: {"consumer_agents": [], "status": "no_consumer"} for r in rules},
                          "by_agent": {}}
        interrupted = False
        with patch.object(pl, "_run_one", respond), patch.object(
                aw.AgentWrapper, "dispatch", side_effect=AssertionError("no model dispatch")):
            try:
                asyncio.run(pl.phase_5_5_convention_review(
                    orch, {}, docs, "declared proof", {"conventions": rules}, index,
                    embed_store={"models": {}}, max_concurrent_docs=1,
                    review_mode="wide" if case == "wide" else "paired",
                    convention_assignment=assignment))
            except RuntimeError:
                if case != "interrupted":
                    raise
                interrupted = True
        run_dir = orch.run_context.run_dir
        report = ap.read_report(run_dir)
        summary_path = pl.write_deliverables_run_summary(
            run_dir / "deliverables", docs, {}, total_cost_usd=0, task="review")
        bus_path = run_dir / "logs" / "agent_bus.jsonl"
        bus = [json.loads(line) for line in bus_path.read_text(encoding="utf-8").splitlines()
               if line.strip()] if bus_path.exists() else []
        items = [i for message in bus for i in message.get("body", {}).get("payload", {}).get("items", [])]
        mapping_path = run_dir / "audit" / "pairing_map.json"
        maps = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}
        return {"report": report, "calls": len(calls), "pending_before_every_reply": all(pending_seen),
                "interrupted": interrupted,
                "bus_judged": sum(i.get("absence_path") == "judged" for i in items),
                "bus_computed": sum(i.get("absence_path") == "computed" for i in items),
                "saved_refused": sum(len(m.get("absence_refused", [])) for m in maps.values()),
                "reasked": sum(m.get("reasked_count", 0) for m in maps.values()),
                "reasked_kept": sum(r.get("kept", 0) for m in maps.values() for r in m.get("reasked", [])),
                "reasked_reasons": sorted(reason for m in maps.values() for r in m.get("reasked", [])
                                          for reason in r.get("reasons", [])),
                "refusal_reasons": sorted(i.get("reason", "") for m in maps.values()
                                          for i in m.get("absence_refused", [])),
                "summary": summary_path.read_text(encoding="utf-8"),
                "historical_missing": ap.read_report(root / "historical") is None}
