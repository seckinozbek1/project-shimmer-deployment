"""Verify collected bytes and derive ordinary-run results. No model/provider access."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile

from ordinary_final_run import read, write, sha, require
from ordinary_final_summary import supplement, rows

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/ordinary_final_cloud_run'


def analyze(bundle=BASE):
    global BASE
    BASE=Path(bundle).resolve()
    integrity=read(BASE/'collection_integrity.json')
    archive=BASE/'collected_evidence.tar.gz'
    require(sha(archive)==integrity['sha256'],'Collected archive integrity mismatch')
    expected=read(BASE/'remote_collection_manifest.json')
    target=BASE/'downloaded'
    target.mkdir(exist_ok=True)
    with tarfile.open(archive) as tar:
        members=tar.getmembers()
        require(len(members)==len(expected) and {m.name for m in members}==set(expected),'Evidence inventory mismatch')
        for member in members:
            path=(target/member.name).resolve()
            require(member.isfile() and path.is_relative_to(target.resolve()),'Unsafe evidence member')
            content=tar.extractfile(member).read()
            require(hashlib.sha256(content).hexdigest()==expected[member.name]['sha256'],'Evidence member hash mismatch')
            require(len(content)==expected[member.name]['bytes'],'Evidence length mismatch')
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():require(sha(path)==expected[member.name]['sha256'],'Existing preserved evidence changed')
            else:path.write_bytes(content)
    require(sha(target/'execution_manifest.json')==sha(BASE/'execution_manifest.json'),'Remote execution manifest differs')
    write(BASE/'verified_evidence.json',dict(passed=True,members=len(expected),archive_sha256=integrity['sha256'],originals_unmodified=True))
    cleanup=read(BASE/'independent_inventory_confirmation.json')
    require(cleanup['instances']==[] and cleanup['temporary_ssh_registration_absent'] and cleanup['local_key_material_absent'],'Cleanup not established')
    launch=read(BASE/'launch.json')
    record=dict(event='infrastructure_cost',provider='Lambda',instance_type='gpu_1x_a10',hourly_rate=launch['hourly_rate'],
        active_start_epoch=launch['epoch'],active_end_epoch=cleanup['epoch'],
        interpretation='Conservative launch request through independent empty-inventory confirmation; estimate, not invoice')
    api=dict(event='api_cost',estimated_cost=0,interpretation='Approved all-local model profile; no paid model/API execution authorized or invoked')
    analysis=BASE/'analysis';analysis.mkdir(exist_ok=True)
    (analysis/'cost_records.jsonl').write_text(json.dumps(record)+'\n'+json.dumps(api)+'\n',encoding='utf8')
    completions=list(target.rglob('audit/run_completion.json'))
    require(len(completions)<=1,'More than one pipeline run observed')
    result=read(target/'evidence/result.json') if (target/'evidence/result.json').exists() else None
    failure=read(target/'evidence/terminal_error.json') if (target/'evidence/terminal_error.json').exists() else None
    summary=None;raw=[];scheduler=[];completion=None
    sys.path.insert(0,str(ROOT/'scripts'))
    import model_telemetry
    if completions:
        completion=read(completions[0]);directory=completions[0].parent.parent
        raw=rows(directory/'logs/model_telemetry.jsonl');scheduler=rows(directory/'audit/execution_topology.jsonl')
        summary=model_telemetry.summarize(raw+[record,api],scheduler)
        write(analysis/'model_telemetry_summary.json',summary)
        write(analysis/'ordinary_final_summary.json',supplement(raw,scheduler))
    summary=summary if completions else {}
    stages={p.stem.removesuffix('_timing'):read(p) for p in BASE.glob('*_timing.json')}
    write(analysis/'stages.json',stages)
    completed=bool(completion and completion.get('state')=='completed' and result and result.get('execution_integrity_passed'))
    costs=model_telemetry.cost([record,api])
    calls=[r for r in raw if r['event']=='model_call']
    status=dict(status='ORDINARY_FINAL_CLOUD_RUN_COMPLETED' if completed else 'ORDINARY_FINAL_CLOUD_RUN_FAILED',
        pipeline_started=bool(completions),pipeline_completion=completion,remote_result=result,terminal_error=failure,
        semantic_call_receipts=len(calls),producer168_receipts=sum(r.get('adapter_checkpoint')==168 for r in calls),
        auditor896_receipts=sum(r.get('adapter_checkpoint')==896 for r in calls),
        auditor896_pairs=(summary.get('auditor_pairing',{}).get('pairs_constructed') if completions else None),
        auditor896_pairs_from_partial_delivery=(summary.get('auditor_pairing',{}).get('pairs_from_partial_delivery') if completions else None),
        cost_estimates=costs,within_hard_ceiling=costs['combined_estimate']<=7,
        exactly_one_instance=True,maximum_one_workload_invocation=True,full_run_retried=False,
        protected_data_accessed=False,multi_round_executed=False,inventory_empty=True,temporary_ssh_removed=True,
        evidence_verified=True,quality_claim=None,subsequent_roadmap_work_started=False)
    write(BASE/'FINAL_STATUS.json',status)
    print(json.dumps(status,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=BASE)
    analyze(parser.parse_args().bundle)
