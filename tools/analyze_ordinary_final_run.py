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
EXPOSED_NO_MANIFEST='exposed, no manifest'
# Annex B.4: both reasons, every report, whenever the bundle's own review scope withholds it.
FACT_CHECKER_REASONS=(
    'switched off, not deleted: deleting the agent needs operator approval under the constitution and cannot be '
    'undone without code, while keeping it leaves LAW-III checks 87 and 127 unchanged and one cleared declaration '
    'restores it',
    'stays off: it returned five substantively wrong items in v7 and v8, byte-identical, and none correct in v5 '
    '(runs 110990c1, 6f896263, a6649672)')
ROLE_SEPARATION=('Role separation: separate sessions and folders on one Windows account; not enforced by the '
                 'operating system (Annex A, 11.2 options not in place; Annex B.11).')
NOT_SCORED=('not computed by this tool: scoring belongs to the scorer (role C for a sealed test, '
            'tools/score_corpus.py for an exposed one); this report makes no quality claim')
DOES_NOT_SHOW=('This report shows run health and cost only. It shows no quality: no recall, attribution or '
               'false-positive figure is computed here, one run is not a measurement of variation, and a '
               'greedy repeat of the same run measures nothing (11.11).')


def withheld_agents(bundle):
    """The audit agents the bundle's OWN review scope withholds, read from its project archive."""
    archive=Path(bundle)/'project.tar.gz'
    if not archive.exists() and (Path(bundle)/'seal_entry.json').exists():
        # A batch run folder: the archive stays in the entry's own bundle.
        archive=Path(read(Path(bundle)/'seal_entry.json').get('bundle',''))/'project.tar.gz'
    try:
        with tarfile.open(archive) as tar:
            scope=json.loads(tar.extractfile('config/review_scope.json').read())
        return list(scope.get('withheld_audit_agents') or [])
    except (OSError, KeyError, ValueError, tarfile.TarError):
        return None


def report_fields(bundle, manifest, record, launch, status, receipt):
    """Every field 11.12 lists, plus B.1's purpose and sealed-or-exposed lines, the
    SHIMMER_INST_FINDER value, B.4's FACT_CHECKER withholding with both reasons, the
    instance type and price, and IV.10's role-separation sentence for a sealed run. A field
    that does not apply says why."""
    record=record or {}
    report=record.get('report') or {}
    exposure=record.get('exposure') or 'exposed'
    sealed=exposure=='sealed'
    withheld=withheld_agents(bundle)
    if withheld is None:
        fact_checker='not determined: the bundle has no readable config/review_scope.json'
    elif 'FACT_CHECKER' in withheld:
        fact_checker='FACT_CHECKER withheld for this run. '+'; '.join(FACT_CHECKER_REASONS)+'.'
    else:
        fact_checker='FACT_CHECKER ran: not withheld in this bundle\'s config/review_scope.json'
    authors=report.get('authors') or {}
    from datetime import datetime, timezone
    rows=[
        ('Purpose',record.get('purpose') or 'not recorded: the launch predates the S2 launch record'),
        ('Sealed or exposed','Sealed test' if sealed else 'Exposed test, development only'),
        ('Date and time (UTC)',datetime.fromtimestamp(launch['epoch'],timezone.utc).isoformat()),
        ('Code commit',manifest['source_commit']),
        ('Test version',report.get('test_version') or manifest.get('workload',{}).get('name') or 'not declared at launch'),
        ('Test manifest hash',record.get('test_manifest_sha256') or EXPOSED_NO_MANIFEST),
        ('Authors (test, key, scorer)',', '.join(str(authors.get(k) or 'not declared at launch') for k in ('test','key','scorer'))),
        ('Scorer version',report.get('scorer_version') or NOT_SCORED),
        ('Models and checkpoints','; '.join(m['model_id']+'@'+m['revision'][:12] for m in manifest.get('models',[]))
            +'; adapter receipts: Producer 168 x%s, Auditor 896 x%s'%(status['producer168_receipts'],status['auditor896_receipts'])),
        ('Decoding settings','; '.join('%s: %s'%(k,v.get('status')) for k,v in sorted((manifest.get('decoding_policy') or {}).items()))
            or 'not recorded in the manifest'),
        ('Backend and machine','local open-weight models on one rented GPU; %s in %s'%(launch.get('instance_type','gpu_1x_a10'),
            launch.get('region','us-east-1'))),
        ('Instance type and price','%s at %s dollars an hour'%(launch.get('instance_type','gpu_1x_a10'),launch['hourly_rate'])),
        ('Cost','%.4f dollars estimated (infrastructure, from launch to confirmed empty inventory; not an invoice)'
            %status['cost_estimates']['combined_estimate']),
        ('Location and reason-confirmed recall',NOT_SCORED),
        ('Attribution',NOT_SCORED),
        ('False positives in every deliverable',NOT_SCORED),
        ('Clean-twin result',NOT_SCORED),
        ('Layer that produced each catch',NOT_SCORED),
        ('Catches that depended on a directive',NOT_SCORED),
        ('Model-text review verdicts','not part of this tool: every model text is reviewed by the scorer\'s review (11.8, B.1)'),
        ('Agents withheld or settings changed',fact_checker+' SHIMMER_INST_FINDER='+str(manifest.get('environment',{}).get('SHIMMER_INST_FINDER'))
            +' (the operator\'s INST_FINDER setting, sealed in the manifest).'),
        ('SHIMMER_INST_FINDER',str(manifest.get('environment',{}).get('SHIMMER_INST_FINDER'))),
        ('Multi-round','declared and sealed with case manifest '+str(manifest.get('case_manifest_sha256'))
            if manifest.get('multi_round') else 'not applicable: no multi-round run was declared'),
        ('Asset copy','MATCH: the sealed archive was read from the operator-declared copy' if receipt.get('used')
            else 'no MATCH (%s): the archive was uploaded'%(receipt.get('state') or 'no declaration for this bundle')),
        ('Role separation',ROLE_SEPARATION if sealed else 'not applicable: an exposed run claims no role separation'),
        ('What the result does not show',DOES_NOT_SHOW),
    ]
    return rows


def write_report(bundle, rows):
    # B.1: the report starts with the purpose line and the sealed-or-exposed line.
    lines=['Purpose: '+rows[0][1],rows[1][1]+'.','','# Run report','']
    lines.extend('- **%s.** %s'%(k,v) for k,v in rows[2:])
    (Path(bundle)/'RUN_REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')


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
    manifest=read(BASE/'execution_manifest.json')
    run_record=read(BASE/'run_record.json') if (BASE/'run_record.json').exists() else None
    copy_receipt=read(BASE/'asset_copy_receipt.json') if (BASE/'asset_copy_receipt.json').exists() else {}
    record=dict(event='infrastructure_cost',provider='Lambda',instance_type=launch.get('instance_type','gpu_1x_a10'),hourly_rate=launch['hourly_rate'],
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
        cost_estimates=costs,within_hard_ceiling=costs['combined_estimate']<=manifest['hard_ceiling_usd'],
        exactly_one_instance=True,maximum_one_workload_invocation=True,full_run_retried=False,
        protected_data_accessed=bool(manifest.get('protected_test')) and bool(completions),
        multi_round_declared=bool(manifest.get('multi_round')),
        multi_round_executed=bool(manifest.get('multi_round')) and bool(list(target.rglob('audit/multi_round.json'))),
        inventory_empty=True,temporary_ssh_removed=True,
        evidence_verified=True,quality_claim=None,subsequent_roadmap_work_started=False)
    rows=report_fields(BASE,manifest,run_record,launch,status,copy_receipt)
    status['report']={k:v for k,v in rows}
    write(BASE/'FINAL_STATUS.json',status)
    write_report(BASE,rows)
    print(json.dumps(status,indent=2))


def analyze_batch(bundle):
    """One report per batch run folder that collected its evidence, in schedule order."""
    folders=sorted(p for p in (Path(bundle)/'batch').iterdir() if (p/'collection_integrity.json').exists())
    for folder in folders:
        analyze(folder)
    return folders


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=BASE)
    parser.add_argument('--batch',action='store_true',help='analyse every batch run folder of this session')
    arguments=parser.parse_args()
    if arguments.batch:analyze_batch(arguments.bundle)
    else:analyze(arguments.bundle)
