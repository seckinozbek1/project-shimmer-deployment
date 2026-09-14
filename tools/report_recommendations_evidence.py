"""Derive diagnostic graphs and explicitly qualified projections, locally."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"scripts"))
from run_projection import project, schedule, topology, costs


CONSUMERS={
    "ARCHIVIST":("semantic","typed inventory","LEGAL_ANALYST and PRACTICE_AUDITOR"),
    "INST_FINDER":("semantic audit obligation","typed institution records","audit bus only"),
    "CITATION_RESOLVER":("semantic audit obligation","typed citation records","audit bus only"),
    "PROCESSOR":("bounded semantic extraction plus deterministic reconstruction","source spans and semantic fields","VERIFIER and FACT_CHECKER"),
    "SPEECH_ACT_TAGGER":("semantic","typed tags","audit bus and per-agent report"),
    "LEGAL_ANALYST":("semantic, conditional deepening","typed findings and human reasoning","deepening, synthesis, amendments"),
    "VERIFIER":("independent semantic verification","typed findings","synthesis, amendments"),
    "FACT_CHECKER":("independent semantic verification","typed findings","synthesis, amendments"),
    "PRACTICE_AUDITOR":("conditional semantic or exact computed comparison","typed findings and attributed reasons","synthesis, amendments"),
    "EDITOR_CLERK":("conditional editorial hierarchy","typed observations","board and operator report"),
}


def build(directory):
    source=ROOT/"output/cloud_collected/a100_optimized_retry_20260914"
    evidence=source/"recovered/evidence/run"
    rows=[json.loads(x) for x in (evidence/"audit/execution_topology.jsonl").read_text().splitlines()]
    starts={r["task"]:r["monotonic_s"] for r in rows if r["event"]=="generation_start"}
    durations={r["task"]:r["monotonic_s"]-starts[r["task"]] for r in rows if r["event"]=="generation_end"}
    queued=[r for r in rows if r["event"]=="queued"]
    before=[];after=[];wave_groups={}
    for r in queued:
        phase=r["phase"];wave=0 if r["agent"] in {"ARCHIVIST","INST_FINDER","CITATION_RESOLVER"} else 1 if phase=="3" else 2 if phase=="5" else 3 if phase=="5.5" else 4
        wave_groups.setdefault(wave,[]).append(r["task"])
    for r in queued:
        kind,fields,consumer=CONSUMERS[r["agent"]]
        base=dict(id=r["task"],agent=r["agent"],phase=r["phase"],model=r["model"],
                  classification=kind,consumer_fields=fields,consumer=consumer,
                  seconds=dict(low=durations[r["task"]],high=durations[r["task"]]))
        before.append(dict(base,parents=[e["parent"] for e in r["edges"]],
                           edge_reason="rolling_bus_visibility_and_governance_order"))
        wave=next(k for k,v in wave_groups.items() if r["task"] in v)
        after.append(dict(base,parents=wave_groups.get(wave-1,[]),
                          edge_reason=["boot governance and source ledger","accepted corpus inventory",
                                       "source and PROCESSOR extraction","phase barrier retained for ordered audit evidence",
                                       "complete findings, deterministic synthesis and editorial input"][wave]))
    summary=json.loads((source/"RECOVERED_RUN_SUMMARY.json").read_text())
    data=dict(schema_version=1,source_commit=summary["source_commit"],historical_classification="DIAGNOSTIC_NON_BENCHMARK",
              before=before,after_wave_only_counterfactual=after,
              after_note="Actual PROCESSOR expands into partitions; exact eligible comparisons disappear. Counts require current source planning. Legal deepening and editorial escalation are conditional additions.",
              before_topology=topology(before),after_wave_only_topology=topology(after),
              generation_seconds_preserved=sum(durations.values()),
              same_service_counterfactuals={str(n):schedule(after,n) for n in [1,2,4]},
              cost_arithmetic=costs(rate=1.99,active_seconds=120),
              cap_cause_assessment=dict(proved=["raw local prompts bypassed native chat templates",
                  "all task submissions serialized by runtime lock and predecessor chain",
                  "PROCESSOR regenerates source text; 8192 tokens did not prevent cap saturation"],
                  hypotheses=["new briefs changed response behavior","EOS/template mismatch caused repetition"],
                  causal_ablation="not performed; no single cause explains 5 to 18 cap hits conclusively"))
    directory.mkdir(parents=True,exist_ok=True)
    (directory/"dependency_graph.json").write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    spec=dict(nodes=[dict(n,seconds=None) for n in after],measured_capacity=None,cpu_seconds=None,
              warm_load_seconds=None,cold_load_seconds=None,retry_overhead_seconds=None,
              assumptions=["Graph replays historical task shape only, not predicted semantic outcomes.",
                           "Partition counts, exact-comparison eligibility and conditional work must be supplied for a concrete input."],
              resource_envelope="Observed laptop GPU: 8 GiB. Real model probe unavailable due OpenMP initialization conflict.")
    (directory/"projection_input.json").write_text(json.dumps(spec,indent=2)+"\n",encoding="utf-8")
    (directory/"projection.json").write_text(json.dumps(project(spec),indent=2)+"\n",encoding="utf-8")
    # Hash historical inputs without modifying or repackaging them.
    hashes={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source.rglob("*") if p.is_file()}
    (directory/"preserved_evidence_hashes.json").write_text(json.dumps(hashes,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"before_waves":data["before_topology"]["semantic_waves"],
                      "after_waves":data["after_wave_only_topology"]["semantic_waves"],
                      "same_service_counterfactuals":data["same_service_counterfactuals"]}))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,required=True)
    build(p.parse_args().output)
