"""Post-termination raw-output recomputation; never evaluates protected data."""
import hashlib,json,math,shutil,sys,tarfile
from collections import Counter
from pathlib import Path,PurePosixPath
from statistics import mean,median
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/fix/second_tuning_canonical_pilot';FROZEN=ROOT/'tuning/second_domain_agnostic_v2'
sys.path.insert(0,str(FROZEN));sys.path.insert(0,str(ROOT/'tools'))
import runtime as r
from runner import verify_freeze,plan,select_checkpoint
from audit_run1 import taxonomy,atom
from cloud_run_common import credential_locations

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def write(name,value):r.write(BASE/name,value)
def extract():
    r.require((BASE/'TERMINATION_VERIFIED.json').exists() and read(BASE/'instances_after.json')==[],'Terminate and verify zero instances before analysis')
    r.require(digest(BASE/'evidence.tar.gz')==read(BASE/'collection_integrity.json')['sha256'],'Archive changed')
    dest=BASE/'downloaded';dest.mkdir(exist_ok=True)
    with tarfile.open(BASE/'evidence.tar.gz','r:gz') as archive:
        for member in archive.getmembers():
            name=PurePosixPath(member.name)
            r.require(not name.is_absolute() and '..' not in name.parts and '\\' not in member.name and ':' not in member.name,'Archive path unsafe')
            target=(dest/Path(*name.parts)).resolve();r.require(target.is_relative_to(dest.resolve()),'Archive escapes evidence root')
            r.require(member.isdir() or member.isfile(),'Archive links/special files forbidden')
            if member.isdir():target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                if target.exists():r.require(digest(target)==hashlib.sha256(archive.extractfile(member).read()).hexdigest(),'Existing extraction differs');continue
                with archive.extractfile(member) as source,target.open('xb') as out:shutil.copyfileobj(source,out)
    return dest

def failed_gates(metrics,gate):
    failures=[]
    for key,value in metrics['catastrophic'].items():
        if value:failures.append('catastrophic.'+key)
    for key,minimum in gate['minimum'].items():
        value=metrics.get(key)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<minimum:failures.append(key+' below '+str(minimum))
    for key,maximum in gate['maximum'].items():
        value=metrics.get(key)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value>maximum:failures.append(key+' above '+str(maximum))
    for key,minimum in gate.get('per_class_recall',{}).items():
        value=metrics['per_class_recall'].get(key)
        if value is None or value<minimum:failures.append('recall.'+key+' below '+str(minimum))
    return failures

def analyze():
    data=extract();binding=verify_freeze();manifest=read(BASE/'manifest.json');r.require(binding==manifest['release_sha256'],'Release changed')
    r.require(digest(data/'tuning/second_domain_agnostic_v2/freeze.json')==digest(FROZEN/'freeze.json'),'Remote freeze differs')
    r.require(digest(data/'tools/second_tuning_remote.py')==digest(ROOT/'tools/second_tuning_remote.py'),'Remote observer differs')
    receipts=[ROOT/'runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json',
        ROOT/'runs/second-domain-agnostic-v2/PROTECTED_ACCESS_CONSUMED.json',
        ROOT/'docs/fix/first_real_tuning_20260916/downloaded/runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json']
    r.require(not any(p.exists() for p in receipts),'Protected receipt consumed')
    r.require(read(BASE/'cleanup.json')==dict(temporary_ssh_removed=True,local_key_material_removed=True,role_permits_removed=True),'Incomplete cleanup')
    rows={x['example_id']:x for x in read(FROZEN/'dataset.json')};roles={};invalid=False
    for role in ('producer','auditor'):
        spec=read(FROZEN/role/'experiment.json');expected=plan(role,'canonical');run=data/'runs/second-domain-agnostic-v2/canonical'/role
        status_path=data/'evidence'/(role+'_status.json')
        if not status_path.exists() and not run.exists():roles[role]=dict(status='NOT_RUN',selected=None);invalid=True;continue
        status=read(status_path) if status_path.exists() else dict(status='INTERRUPTED',optimizer_steps=0,seconds=None,peak_allocated=0,peak_reserved=0)
        checkpoints=[]
        if (run/'RUN_BINDING.json').exists():r.require(read(run/'RUN_BINDING.json')==dict(release_sha256=binding,plan=expected),'Unbound run')
        if status['status'] in ('RUNTIME_FAILED','INTERRUPTED') or status['optimizer_steps']!=120:invalid=True
        saved=read(run/'checkpoint_metrics.json') if (run/'checkpoint_metrics.json').exists() else []
        for result in saved:
            step=result['step'];evidence=read(run/f'validation-{step}.json')
            r.require([v['example_id'] for v in evidence]==expected['validation_ids'],'Wrong DEV IDs/order')
            scores=[];distribution=Counter();gap_counts=Counter();gap_rows=[]
            for item in evidence:
                row=rows[item['example_id']];score=r.score(row,item['raw_output'],item['truncated'])
                r.require(score==item['metrics'],'Row metric disagreement')
                identity=item['identity'];r.require(identity['release_sha256']==binding and identity['role']==role and identity['split']=='canonical' and identity['step']==step,'Wrong checkpoint identity')
                scores.append(score)
                if role=='auditor':distribution['MALFORMED_OTHER' if not score['contract_valid'] else score['predicted_relation']]+=1
                else:
                    try:parsed=r.core.strict_json(item['raw_output']);valid_json=True
                    except (ValueError,TypeError):parsed=None;valid_json=False
                    if not valid_json:errors=[dict(category='invalid_json')]
                    elif not isinstance(parsed,dict) or not isinstance(parsed.get('items',[]),list) or any(not isinstance(i,dict) for i in parsed.get('items',[])):errors=[dict(category='contract_shape_error')]
                    else:
                        clean={'items':[dict(i,questions=[x for x in i.get('questions',[]) if isinstance(x,str)] if isinstance(i.get('questions',[]),list) else [],
                            uncertainty=[x for x in i.get('uncertainty',[]) if isinstance(x,str)] if isinstance(i.get('uncertainty',[]),list) else []) for i in parsed.get('items',[])]}
                        rendering=[]
                        # Diagnostic-only serialization equivalence: strict
                        # frozen scores/raw outputs are never normalized.
                        for predicted in clean['items']:
                            gold=next((i for i in r.target(row)['items'] if i['span']==predicted.get('span')),None)
                            if gold is None:continue
                            for index,value in enumerate(predicted['questions']):
                                equivalent=next((x for x in gold['questions'] if x!=value and atom(value) is not None and atom(value)==atom(x)),None)
                                if equivalent is not None:
                                    rendering.append(dict(category='rendering_error',gold=[gold['span'],equivalent],predicted=[gold['span'],value],detail='Noncanonical typed-string serialization'))
                                    predicted['questions'][index]=equivalent
                        errors=rendering+taxonomy(r.target(row),clean)
                    gap_counts.update(e['category'] for e in errors);gap_rows.append(dict(example_id=row['example_id'],contract_valid=score['contract_valid'],accepted=score['accepted_outcome'],errors=errors))
            metrics=r.aggregate(scores);r.require(metrics==result['metrics'],'Checkpoint metrics differ')
            for filename,digest_value in evidence[0]['identity']['files'].items():r.require(digest(run/f'checkpoint-{step}'/filename)==digest_value,'Adapter changed')
            checkpoints.append(dict(step=step,gate='PASS' if r.selection_pass(metrics,spec['selection_gates']) else 'FAIL',failed_gates=failed_gates(metrics,spec['selection_gates']),
                metrics=metrics,contracts=sum(s['contract_valid'] for s in scores),accepted=sum(s['accepted_outcome'] for s in scores),
                relation_distribution=dict(distribution),gap_taxonomy=dict(gap_counts),gap_rows=gap_rows))
        chosen=None
        if len(saved)==2:
            try:chosen=select_checkpoint(role,saved)
            except ValueError:r.require((run/'SELECTION_REJECTED.json').exists(),'Missing selection rejection')
            else:r.require(read(run/'SELECTION_FREEZE.json')['selected']==chosen,'Selected checkpoint differs')
        else:invalid=True
        event_path=data/'evidence'/(role+'_events.json');events=read(event_path) if event_path.exists() else []
        telemetry_path=data/'evidence'/(role+'_telemetry.jsonl')
        telemetry=[json.loads(x) for x in telemetry_path.read_text().splitlines()] if telemetry_path.exists() else []
        loss_events=[e for e in events if e['kind']=='loss'];generations=[e for e in events if e['kind']=='generation']
        steps=[e for e in events if e['kind']=='optimizer_step'];ordinary=[e['step_wall_seconds'] for e in steps if e['step'] not in (1,61)]
        parameters=[e for e in events if e['kind']=='trainable_parameters']
        training_windows=[]
        if parameters and any(e['step']==60 for e in steps):
            training_windows.append(next(e['epoch'] for e in steps if e['step']==60)-parameters[0]['epoch'])
        dev60=[e for e in generations if e['step']==60]
        if len(dev60)==60 and any(e['step']==120 for e in steps):
            training_windows.append(next(e['epoch'] for e in steps if e['step']==120)-dev60[-1]['epoch'])
        if status['status']=='INTERRUPTED':
            status['optimizer_steps']=len(steps)
            status['peak_allocated']=max((x['allocated'] for x in telemetry),default=0)
            status['peak_reserved']=max((x['reserved'] for x in telemetry),default=0)
        rawpath=data/'evidence'/(role+'_raw_dev.jsonl')
        raw=[json.loads(line) for line in rawpath.read_text().splitlines()] if rawpath.exists() else []
        r.require([e['step'] for e in steps]==list(range(1,len(steps)+1)) and len(steps)<=120,'Unexpected optimizer schedule')
        r.require([e['step'] for e in loss_events]==[e['step'] for e in steps],'Missing loss observations')
        for checkpoint_step in (60,120):
            partial=[x for x in raw if x['step']==checkpoint_step]
            r.require([x['example_id'] for x in partial]==expected['validation_ids'][:len(partial)] and len(partial)<=60,'Wrong raw DEV prefix')
        r.require(all(x['step'] in (60,120) for x in raw),'Unexpected DEV checkpoint')
        for item in raw:
            if (run/f"validation-{item['step']}.json").exists():
                frozen=next(x for x in read(run/f"validation-{item['step']}.json") if x['example_id']==item['example_id'])
                r.require(item['raw_output']==frozen['raw_output'] and item['output_token_ids']==frozen['output_token_ids'],'Durable raw generation differs')
        roles[role]=dict(status=status['status'],selected=None if chosen is None else chosen['step'],checkpoint_results=checkpoints,
            selection_status='NOT_EVALUABLE_INCOMPLETE' if len(saved)!=2 else 'ROLE_SELECTION_FAILED' if chosen is None else 'SELECTED',
            controller_wall_seconds=read(BASE/(role+'_training_timing.json'))['seconds'],
            role_wall_seconds=status['seconds'],generation_seconds=sum(e['seconds'] for e in generations),
            non_generation_seconds=None if status['seconds'] is None else status['seconds']-sum(e['seconds'] for e in generations),
            training_window_seconds=sum(training_windows) if len(training_windows)==2 else None,
            training_window_definition='Parameter-proof event to update 60, plus last DEV-60 generation to update 120; includes minor setup/aggregation overhead; excludes model load and generation.',
            ordinary_step_wall_median=median(ordinary) if ordinary else None,optimizer_updates=status['optimizer_steps'],
            peak_allocated_vram_gib=status['peak_allocated']/2**30,peak_reserved_vram_gib=status['peak_reserved']/2**30,
            peak_vram_measurement='Sampled telemetry lower bound' if status['status']=='INTERRUPTED' else 'CUDA high-water mark',
            loss_start=loss_events[0]['loss'] if loss_events else None,loss_end=loss_events[-1]['loss'] if loss_events else None,
            model_load_seconds=sum(e['seconds'] for e in events if e['kind']=='model_load'),
            trainable_parameter_proof=[e for e in events if e['kind']=='trainable_parameters'],
            telemetry_samples=len(telemetry),peak_rss_bytes=max((x['rss'] for x in telemetry),default=0),
            raw_generations=len(raw),generation_by_checkpoint={str(step):dict(count=sum(e['step']==step for e in generations),seconds=sum(e['seconds'] for e in generations if e['step']==step),tokens=sum(e['tokens'] for e in generations if e['step']==step),stop_reasons=dict(Counter(e['stop_reason'] for e in generations if e['step']==step))) for step in (60,120)})
    protected_receipts=list(data.rglob('PROTECTED_ACCESS_CONSUMED.json'));r.require(not protected_receipts,'Unexpected protected receipt')
    verdict='SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE' if invalid else 'SECOND_TUNING_CANONICAL_PILOT_PASS' if all(x['selected'] for x in roles.values()) else 'SECOND_TUNING_CANONICAL_PILOT_FAIL'
    result=dict(verdict=verdict,FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=verdict=='SECOND_TUNING_CANONICAL_PILOT_PASS',roles=roles,
        source_commit=manifest['source_commit'],release_sha256=binding,cloud=read(BASE/'TERMINATION_VERIFIED.json'),
        protected_accesses=0,other_cv_folds_executed=0,run1_reference='Frozen run1_audit.json, read as historical evidence only; not rescored',
        invalidation_reason='BUDGET_RUNTIME_INTERRUPTION' if (BASE/'OPERATOR_BUDGET_STOP.json').exists() else None,
        frozen_configuration_changed=False,paid_inference_apis=False,second_instance=False,full_pipeline=False,multi_round=False,pushed=False)
    write('RECOMPUTED_RESULTS.json',result)
    security=[];hashes={}
    for p in data.rglob('*'):
        if not p.is_file():continue
        hashes[str(p.relative_to(data))]=digest(p)
        if p.suffix=='.safetensors':
            with p.open('rb') as f:count=int.from_bytes(f.read(8),'little');r.require(count<10*1024*1024,'Invalid adapter header');content=f.read(count)
        else:content=p.read_bytes()
        security.extend(credential_locations(content,str(p.relative_to(data))))
    if security:
        for item in security:print('WARNING: Possible API key detected in '+item['file']+':'+str(item['line'])+'. Do not push. Rotate the key immediately.')
        raise SystemExit(1)
    write('EVIDENCE_HASHES.json',hashes);write('ARTIFACT_SECURITY_SCAN.json',dict(findings=0,files=len(hashes),adapter_headers_scanned=True,values_printed=False))
    print(json.dumps(dict(verdict=verdict,selected={k:v['selected'] for k,v in roles.items()},cost=result['cloud']['estimated_cost_upper_bound_usd']),indent=2))

if __name__=='__main__':analyze()
