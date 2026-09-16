"""Post-termination independent raw-output verification; no model execution."""
import hashlib
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/producer_checkpoint120_eval_v2_1'
RT=ROOT/'tuning/second_tuning_eval_runtime_v2_1'
OLD=ROOT/'tuning/second_tuning_eval_runtime_v2'
sys.path.insert(0,str(RT))
import eval_runtime as ev
import release
sys.path.append(str(OLD))
import audit
r=audit.frozen
sys.path.insert(0,str(ROOT/'tools'))
from cloud_run_common import credential_locations

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf8').splitlines() if x.strip()]
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
def write(name,value):r.write(BASE/name,value)

def main():
    termination=read(BASE/'TERMINATION_VERIFIED.json')
    assert read(BASE/'instances_after.json')==[] and read(BASE/'FINAL_INVENTORY.json')['zero_billable_instances']
    assert all(read(BASE/'cleanup.json')[k] for k in ('temporary_ssh_removed','local_key_material_removed'))
    assert sha(BASE/'evidence.tar.gz')==read(BASE/'collection_integrity.json')['sha256']
    preservation=release.verify()
    # This authorized cloud task permits fresh byte hashing of historical weights,
    # without loading tensors; strengthen the earlier local-only metadata check.
    historical=read(OLD/'historical_preservation.json')
    for name,expected in historical.items():assert sha(ROOT/name)==expected,name
    data=BASE/'downloaded';out=data/'evidence';manifest=read(BASE/'manifest.json')
    assert read(data/'execution_manifest.json')==read(BASE/'execution_manifest.json')
    assert sha(data/'tools/checkpoint120_v21_remote.py')==read(BASE/'execution_manifest.json')['files']['tools/checkpoint120_v21_remote.py']
    assert sha(data/'tuning/second_tuning_eval_runtime_v2_1/freeze.json')==manifest['release_sha256']==preservation['release_sha256']
    assert read(data/'evaluation_authorization.json')==read(BASE/'evaluation_authorization.json')
    protocol=read(RT/'protocol.json');prepared=read(OLD/'prepared_dev.json');ev.validate_records(prepared,protocol)
    prepared_by={x['example_id']:x for x in prepared}
    gold={x['example_id']:x for x in r.read(audit.FROZEN/'dataset.json') if x['role']=='producer'}
    tok=r.old.tokenizer('producer')
    context=read(out/'REAL_RUNTIME_CONTEXT_PREFLIGHT.json');assert context['passed'] and context['state_restored'] and context['generation_calls']==0
    cache=read(out/'cache_admission.json');assert cache['passed'] and ev.cache_effect_gate(cache['observations'])
    peft=read(out/'peft_preflight.json');assert peft['adapter_tensor_identity'] and peft['adapter_hashes']==protocol['adapter']['files']
    for name,value in protocol['base_weight_hashes'].items():assert read(out/'acquisition.json')['files'][name]==value
    def verify_row(item):
        source=prepared_by[item['example_id']]
        assert item['role']=='producer' and item['split']=='canonical' and item['checkpoint']==120
        assert item['adapter']==protocol['adapter']
        assert item['base_identity']==dict(model_id=protocol['model_id'],revision=protocol['revision'],files=protocol['base_weight_hashes'])
        for key in ('prompt','input_ids','attention_mask'):assert item[key]==source[key]
        assert item['prompt_sha256']==hashlib.sha256(source['prompt'].encode()).hexdigest()
        assert item['input_ids_sha256']==ev.digest(source['input_ids'])
        ids=item['output_token_ids'];assert item['output_tokens']==len(ids) and 0<len(ids)<=288
        assert tok.decode(ids,skip_special_tokens=True)==item['raw_output']
        assert tok.decode(ids,skip_special_tokens=False)==item['raw_output_with_special_tokens']
        eos=ids[-1] in protocol['generation_kwargs']['eos_token_id']
        assert item['stop_reason']==('eos' if eos else 'length') and item['truncated']==(not eos)
        assert math.isfinite(item['generation_seconds']) and item['generation_seconds']>0
        return r.score(gold[item['example_id']],item['raw_output'],truncated=not eos)
    def verify_set(raw,scored):
        assert len(raw)==len(scored)
        for a,b in zip(raw,scored):
            assert a=={k:v for k,v in b.items() if k!='metrics'}
            score=verify_row(a);assert score==b['metrics'];a['metrics']=score
        return raw
    reference=[];optimized=[]
    for i in range(6):
        for mode,target in (('reference',reference),('optimized',optimized)):
            label='control_'+mode+'_'+str(i)
            evidence=verify_set(rows(out/(label+'.jsonl')),read(out/(label+'_scored.json')))
            assert len(evidence)==1 and evidence[0]['example_id']==protocol['control_ids'][i]
            target.extend(evidence)
    for mode in ('reference','optimized'):
        verify_set(rows(out/('cache_'+mode+'.jsonl')),read(out/('cache_'+mode+'_scored.json')))
    controls=ev.control_gate(reference,optimized,protocol)
    controls['decoded_identity']=all(a['raw_output']==b['raw_output'] and a['raw_output_with_special_tokens']==b['raw_output_with_special_tokens'] for a,b in zip(reference,optimized))
    controls['stop_identity']=all(a['stop_reason']==b['stop_reason'] for a,b in zip(reference,optimized))
    controls['pass_gate']=controls['pass_gate'] and controls['decoded_identity'] and controls['stop_identity']
    assert controls==read(out/'control_admission.json') and controls['pass_gate']
    def rate(values):return sum(len(x['output_token_ids']) for x in values)/sum(x['generation_seconds'] for x in values)
    assert rate(optimized)>=4.438538339317307 and rate(optimized)/rate(reference)>=2
    assert read(out/'admitted.json')['status']=='CHECKPOINT120_EVALUATION_ADMITTED'
    full=verify_set(rows(out/'full_dev.jsonl'),read(out/'full_dev_scored.json'))
    assert len(full)==60 and [x['example_id'] for x in full]==protocol['dev_ids']
    assert all(x['runtime']=='second-tuning-eval-runtime-v2_1' for x in full)
    metrics=r.aggregate([x['metrics'] for x in full]);assert metrics==read(out/'metrics.json')
    gates=read(audit.FROZEN/'producer/experiment.json')['selection_gates']
    failures=[]
    for name,value in metrics['catastrophic'].items():
        if value:failures.append(dict(gate='catastrophic.'+name,actual=value,maximum=0))
    for section,compare in (('minimum',lambda a,b:a>=b),('maximum',lambda a,b:a<=b)):
        for name,threshold in gates[section].items():
            value=metrics.get(name)
            if not isinstance(value,(int,float)) or not math.isfinite(value) or not compare(value,threshold):failures.append(dict(gate=name,actual=value,**{section:threshold}))
    passed=not failures;assert passed==r.selection_pass(metrics,gates)
    verdict='PRODUCER_CHECKPOINT120_PASS' if passed else 'PRODUCER_CHECKPOINT120_FAIL'
    assert read(out/'status.json')==dict(status='COMPLETED',checkpoint_result=verdict,full_dev_rows=60)
    described=[audit.describe(x,gold[x['example_id']],288) for x in full]
    efficiency=audit.summarize(described,'COMPLETE_FRESH_DEV_V2_1')
    accepted=[x for x in described if x['accepted'] and x['contract_valid']]
    groups={name:[x for x in accepted if pred(x)] for name,pred in (
        ('correct_refusal',lambda x:x['refused']),('correct_empty',lambda x:not x['refused'] and x['efficiency']['required_atoms']==0),
        ('substantive_nonempty',lambda x:x['efficiency']['required_atoms']>0))}
    accepted_groups={k:dict(count=len(v),token_cost=audit.distribution(x['tokens'] for x in v)) for k,v in groups.items()}
    history_raw=rows(audit.PILOT/'downloaded/evidence/producer_raw_dev.jsonl')
    comparisons={}
    for step in (60,120):
        old=[x for x in history_raw if x['step']==step];label='COMPLETE_HISTORICAL_DEV' if step==60 else 'PARTIAL_PREFIX_ONLY'
        scores=[r.score(gold[x['example_id']],x['raw_output'],truncated=x['stop_reason']!='eos') for x in old]
        summary=audit.summarize([audit.describe(x,gold[x['example_id']],288) for x in old],label)
        # Prefix-only descriptive metric table is explicitly scoped; never used
        # for a full checkpoint verdict or gate/selection decision.
        historical_metrics=r.aggregate(scores)
        comparisons[str(step)]=dict(scope=label,rows=len(old),summary=summary,metrics=historical_metrics,
            generation_seconds=sum(x['latency_seconds'] for x in old),tokens_per_second=sum(len(x['output_token_ids']) for x in old)/sum(x['latency_seconds'] for x in old))
    same42=sum(x['output_token_ids']==full[i]['output_token_ids'] for i,x in enumerate([x for x in history_raw if x['step']==120]))
    fields=context['owned_config_fields']
    result=dict(verdict=verdict,admission='CHECKPOINT120_EVALUATION_ADMITTED',source_commit=manifest['source_commit'],runtime_release_sha256=manifest['release_sha256'],
        cloud=dict(provider='Lambda Cloud',region=manifest['region'],gpu=manifest['instance']['gpu_type'],hourly_rate=manifest['hourly_rate'],termination=termination),
        context=dict(passed=True,state_restored=True,owned_fields=len(fields),none_fields=sum(x['is_none'] for x in fields),identity_groups=len({x['identity_group'] for x in fields})),
        cache=cache,controls=controls,control_details=[dict(example_id=a['example_id'],tokens=len(a['output_token_ids']),reference_seconds=a['generation_seconds'],optimized_seconds=b['generation_seconds'],token_identity=a['output_token_ids']==b['output_token_ids'],semantic_identity=a['metrics']==b['metrics']) for a,b in zip(reference,optimized)],
        full_dev=dict(count=60,generation_seconds=sum(x['generation_seconds'] for x in full),output_tokens=sum(x['output_tokens'] for x in full),tokens_per_second=rate(full),metrics=metrics,failed_gates=failures,efficiency=efficiency,accepted_groups=accepted_groups),
        historical_comparison=comparisons,historical_prefix_token_identity=dict(scope='PARTIAL_PREFIX_ONLY',equal=same42,total=42),
        archive_sha256=sha(BASE/'evidence.tar.gz'),historical_files_byte_verified=len(historical),runtime_preservation=preservation,
        AUDITOR_STATUS='UNTOUCHED',PROTECTED_RECEIPT_STATUS='UNCONSUMED',next_action='Stop Producer tuning branch; no automatic retraining' if not passed else 'Propose separately authorized Auditor canonical execution')
    write('RECOMPUTED_RESULTS.json',result);write('RECOMPUTED_PER_ROW.json',described)
    files=[p for p in BASE.rglob('*') if p.is_file() and 'bundle_check' not in p.parts and p.suffix in ('.py','.json','.jsonl','.md','.log')]
    for p in files:
        hits=credential_locations(p.read_bytes(),str(p.relative_to(ROOT)))
        if hits:
            for x in hits:print('WARNING: Possible API key detected in '+x['file']+':'+str(x['line'])+'. Do not push. Rotate the key immediately.')
            raise SystemExit(1)
    write('POST_RUN_VERIFICATION.json',dict(passed=True,raw_rows_recomputed=74,control_pairs_verified=6,full_rows_verified=60,failed_gates=failures,credential_files_scanned=len(files),credential_findings=0,zero_instances=True,archive_hash_verified=True))
    print(json.dumps({k:v for k,v in result.items() if k not in ('historical_comparison',)},indent=2))

if __name__=='__main__':main()
