"""Recompute ordinary-run component/wait summaries from collected evidence only."""
import argparse
import json
from pathlib import Path
import sys


def rows(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf8').splitlines() if s] if Path(path).exists() else []


def supplement(raw, scheduler):
    groups={}
    retained={}
    for r in raw:
        if r['event']=='retention_snapshot':retained.update(r['call_counts'])
    for r in raw:
        if r['event']!='model_call':continue
        r=dict(r)
        if r.get('call_id') in retained:r['retained_count']=retained[r['call_id']]
        name=r['agent'];g=groups.setdefault(name,[]);g.append(r)
    per_agent={}
    for name,calls in groups.items():
        values={}
        for key in ['input_tokens','output_tokens','total_service_seconds','generation_seconds','emitted_count','retained_count']:
            known=[r[key] for r in calls if r.get(key) is not None]
            values[key]=dict(value=sum(known) if known else None,measured_calls=len(known))
        per_agent[name]=dict(calls=len(calls),metrics=values,
            counts={k:sum(r.get(k) is True for r in calls) for k in ['truncated','cap_hit','contract_valid','empty_output','refused']})
        measured=[r for r in calls if r.get('generation_seconds',0) is not None and r.get('generation_seconds',0)>0 and r.get('output_tokens') is not None]
        per_agent[name]['decode_tokens_per_second']=(sum(r['output_tokens'] for r in measured)/sum(r['generation_seconds'] for r in measured)) if measured else None
    ready=[r for r in scheduler if r['event']=='ready']
    assigned=[r for r in scheduler if r['event']=='assigned']
    return dict(per_agent=per_agent,
        dependency_wait_task_seconds=sum(r['dependency_wait_s'] for r in ready) if ready else None,
        resource_wait_task_seconds=sum(r['scheduler_wait_s'] for r in assigned) if assigned else None,
        interpretation='Task wait sums are not pipeline wall-clock; use the scheduler DAG and interval unions.',
        deterministic_nonmodel_cpu_seconds=None,
        deterministic_cpu_unavailable='Process CPU includes model kernels, embeddings and telemetry; no isolated measurement')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir',type=Path)
    parser.add_argument('--scripts',type=Path,default=Path(__file__).resolve().parents[1]/'scripts')
    args=parser.parse_args()
    sys.path.insert(0,str(args.scripts))
    import model_telemetry
    native=model_telemetry.recompute(args.run_dir)
    value=supplement(rows(args.run_dir/'logs/model_telemetry.jsonl'),rows(args.run_dir/'audit/execution_topology.jsonl'))
    value['native_summary']='model_telemetry_summary.json'
    (args.run_dir/'audit/ordinary_final_summary.json').write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf8')
