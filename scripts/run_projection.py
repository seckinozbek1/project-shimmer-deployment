"""Deterministic single-run projections. Missing measurements stay unknown."""
import argparse
import json
import math
from pathlib import Path


def schedule(nodes, capacity, bound="low"):
    if isinstance(capacity,bool) or not isinstance(capacity,int) or capacity < 1:
        raise ValueError("Measured positive concurrency capacity required")
    pending={n["id"]:n for n in nodes}
    if len(pending)!=len(nodes):raise ValueError("Duplicate node ID")
    if any(p not in pending for n in nodes for p in n["parents"]):raise ValueError("Unknown dependency")
    done, running, clock = {}, [], 0.0
    while pending or running:
        ready=[n for n in nodes if n["id"] in pending and all(p in done for p in n["parents"])]
        for node in ready[:capacity-len(running)]:
            duration=node["seconds"][bound]
            if not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<0:
                raise ValueError("Invalid service duration")
            running.append((clock+duration,node["id"]))
            del pending[node["id"]]
        if not running:raise ValueError("Dependency cycle")
        clock=min(t for t,k in running)
        finished=[(t,k) for t,k in running if t==clock]
        done.update({k:t for t,k in finished})
        running=[(t,k) for t,k in running if t!=clock]
    return clock


def topology(nodes):
    levels, path, durations={}, {}, {}
    pending=list(nodes)
    while pending:
        ready=[n for n in pending if all(p in levels for p in n["parents"])]
        if not ready:raise ValueError("Missing dependency or cycle")
        for n in ready:
            p=max(n["parents"],key=lambda k:durations[k],default=None)
            levels[n["id"]]=1+max((levels[k] for k in n["parents"]),default=0)
            durations[n["id"]]=(n.get("seconds") or {}).get("low",0)+(durations[p] if p else 0)
            path[n["id"]]=(path[p] if p else [])+[n["id"]]
            pending.remove(n)
    end=max(durations,key=durations.get,default=None)
    return dict(semantic_waves=max(levels.values(),default=0),critical_path=path[end] if end else [],
                critical_path_seconds=durations[end] if end else 0)


def project(spec):
    nodes=spec["nodes"]
    if len({n["id"] for n in nodes})!=len(nodes):raise ValueError("Duplicate node ID")
    graph=topology(nodes)
    missing=[n["id"]+": representative latency" for n in nodes if n.get("seconds") is None]
    for k in ["measured_capacity","cpu_seconds","warm_load_seconds","cold_load_seconds","retry_overhead_seconds"]:
        if spec.get(k) is None:missing.append(k)
    result=dict(classification="PROJECTION_NOT_BENCHMARK",call_count=len(nodes),**graph,
                projected_wall_seconds=None,projected_generation_seconds=None,
                projected_truncation_count=spec.get("measured_truncation_count"),
                contract_refusal_risk=spec.get("measured_contract_refusal_risk"),
                local_resource_envelope=spec.get("resource_envelope"),
                assumptions=spec.get("assumptions",[]),missing_measurements=missing,
                target_assessment="LOCAL_TARGET_INDETERMINATE")
    if missing:
        result["critical_path_seconds"]=None
        return result
    for key in ["cpu_seconds","warm_load_seconds","cold_load_seconds","retry_overhead_seconds"]:
        if not isinstance(spec[key],(int,float)) or not math.isfinite(spec[key]) or spec[key]<0:
            raise ValueError("Invalid overhead duration")
    if any(n["seconds"]["low"]>n["seconds"]["high"] for n in nodes):
        raise ValueError("Latency range is reversed")
    walls={}
    for mode in ["warm","cold"]:
        walls[mode]=[schedule(nodes,spec["measured_capacity"],bound)+spec["cpu_seconds"]+
                     spec[mode+"_load_seconds"]+spec["retry_overhead_seconds"] for bound in ["low","high"]]
    result["projected_wall_seconds"]=walls
    result["projected_generation_seconds"]=[sum(n["seconds"][b] for n in nodes) for b in ["low","high"]]
    if walls["warm"][0]>=600:
        result["target_assessment"]="LOCAL_TARGET_PROJECTED_NOT_MET"
    elif walls["cold"][1]<600 and spec.get("quality_gate_passed") is True and spec.get("measured_truncation_count")==0 and spec.get("resource_gate_passed") is True:
        result["target_assessment"]="LOCAL_TARGET_PROJECTED_MET"
    return result


def costs(*,rate,active_seconds,setup_seconds=0,preparation_seconds=0,idle_seconds=0,
          storage_network_usd=0,accepted_runs=1,acceptance_probability=1):
    values=[rate,active_seconds,setup_seconds,preparation_seconds,idle_seconds,storage_network_usd]
    if any(not math.isfinite(x) or x<0 for x in values) or accepted_runs<=0 or not 0<acceptance_probability<=1:
        raise ValueError("Invalid cost assumptions")
    marginal=rate*active_seconds/3600/acceptance_probability
    return dict(marginal_cost_per_accepted_run=marginal,
                fully_loaded_cost_per_accepted_run=marginal+(rate*(setup_seconds+preparation_seconds+idle_seconds)/3600+storage_network_usd)/accepted_runs,
                classification="ARITHMETIC_ASSUMPTION_NOT_OBSERVED_COST")


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("input",type=Path);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();result=project(json.loads(a.input.read_text(encoding="utf-8")))
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":main()
