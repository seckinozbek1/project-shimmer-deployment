"""Independent local recomputation after confirmed termination; no model or training."""
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tarfile
from collections import Counter

ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/fix/auditor_linear_probe_run';D=ROOT/'tuning/auditor_linear_probe'
os.environ.update(USE_TORCH='0',USE_TF='0',USE_FLAX='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
sys.path.insert(0,str(ROOT/'tools'))
import auditor_linear_core as c
from cloud_run_common import credential_locations,write_json
from auditor_linear_local import preserve
sys.path.insert(0,str(ROOT/'tuning/second_domain_agnostic_v2'));import runtime as r

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def lines(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf8').splitlines() if x.strip()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def analyze():
    assert (B/'TERMINATION_VERIFIED.json').exists() and read(B/'instances_after.json')==[]
    assert read(B/'final_inventory_confirmation.json')['zero_billable_resources'] is True
    cleanup=read(B/'cleanup.json');assert cleanup['temporary_ssh_removed'] and cleanup['local_key_material_removed']
    assert not (B/'ssh_identity').exists() and not (B/'ssh_identity.pub').exists()
    history=preserve();termination=read(B/'TERMINATION_VERIFIED.json');manifest=read(B/'manifest.json')
    result=dict(history=history,termination=termination,source_commit=manifest['source_commit'],zero_resources=True)
    if not (B/'collection_integrity.json').exists():
        result.update(verdict='AUDITOR_LINEAR_PROBE_INDETERMINATE',reason='Evidence archive unavailable');write_json(B/'RECOMPUTED_RESULTS.json',result);return result
    assert sha(B/'evidence.tar.gz')==read(B/'collection_integrity.json')['sha256']
    downloaded=B/'downloaded';downloaded.mkdir(exist_ok=True)
    with tarfile.open(B/'evidence.tar.gz') as archive:
        for member in archive.getmembers():
            target=(downloaded/member.name).resolve();assert target.is_relative_to(downloaded.resolve()) and not member.issym() and not member.islnk()
        archive.extractall(downloaded,filter='data')
    E=downloaded/'evidence';status=read(E/'status.json') if (E/'status.json').exists() else {}
    result['remote_status']=status
    if status.get('verdict')=='AUDITOR_LINEAR_PROBE_INDETERMINATE' or not (E/'full_dev_scored.jsonl').exists():
        result.update(verdict='AUDITOR_LINEAR_PROBE_INDETERMINATE',reason=status.get('reason','Complete integrated evidence absent'))
        result['available_artifacts']=[p.name for p in E.iterdir()] if E.exists() else []
        result['partial_counts']={name:len(lines(E/name)) if (E/name).exists() else 0 for name in ['features.jsonl','head_training.jsonl','controls_1.jsonl','controls_2.jsonl','full_dev.jsonl']}
        write_json(B/'RECOMPUTED_RESULTS.json',result);return result
    import numpy as np
    from safetensors.numpy import load_file
    spec=read(D/'experiment.json');rows=read(D/'dataset.json');split=read(D/'split.json');records=read(D/'records.json');by={x['example_id']:x for x in rows};rec={x['example_id']:x for x in records};ids=[x['example_id'] for x in rows]
    execution=read(B/'execution_manifest.json')
    for p in (downloaded/'tools').glob('*.py'):assert sha(p)==execution['files'][p.relative_to(downloaded).as_posix()]
    for p in (downloaded/'tuning/auditor_linear_probe').iterdir():
        if p.is_file():assert sha(p)==execution['files'][p.relative_to(downloaded).as_posix()]
    assert read(E/'frozen_initial.json')['state_sha256']==read(E/'frozen_final.json')['state_sha256']
    assert read(E/'frozen_final.json')['unchanged'] and read(E/'frozen_final.json')['parameter_state_unchanged']
    for name in ['backbone_trainable','lora_trainable']:assert read(E/'frozen_final.json')[name]==0
    features=np.load(E/'features.npy',allow_pickle=False);assert features.shape==(300,3072) and features.dtype==np.float32
    feature_receipts=lines(E/'features.jsonl');assert [x['example_id'] for x in feature_receipts]==ids
    for v,receipt in zip(features,feature_receipts):assert c.digest(v.tobytes())==receipt['sha256']
    tr=[ids.index(i) for i in split['train']];mean,std,standard=c.standardized(np,features,tr)
    np.testing.assert_array_equal(mean,np.load(E/'mean.npy',allow_pickle=False));np.testing.assert_array_equal(std,np.load(E/'std.npy',allow_pickle=False))
    norm=read(E/'normalization.json');assert norm['train_ids']==split['train'] and not norm['dev_fit'] and norm['mean_sha256']==sha(E/'mean.npy') and norm['std_sha256']==sha(E/'std.npy')
    initial=load_file(str(E/'head-0.safetensors'));head=load_file(str(E/'head-200.safetensors'))
    assert set(head)=={'weight','bias'} and head['weight'].shape==(5,3072) and head['bias'].shape==(5,) and sum(v.size for v in head.values())==15365
    assert all((v==0).all() for v in initial.values())
    assert sha(E/'head-200.safetensors')==status['head_sha256']==read(E/'head_train_result.json')['head_sha256']
    training=lines(E/'head_training.jsonl');assert [x['step'] for x in training]==list(range(1,201))
    assert math.isclose(training[0]['ce'],math.log(5),rel_tol=1e-6) and training[0]['regularization']==0
    for x in training:assert all(math.isfinite(x[k]) for k in ['ce','regularization','loss']) and math.isclose(x['loss'],x['ce']+x['regularization'])
    opt=read(E/'optimizer.json');assert opt['train_ids']==split['train'] and opt['parameters']==15365 and opt['updates']==200 and opt['batch']==240 and opt['lr']==.01 and opt['betas']==[.9,.999] and opt['eps']==1e-8 and opt['weight_decay']==0
    train_logits=standard[tr]@head['weight'].T+head['bias'];train_expected=[by[i]['relation'] for i in split['train']]
    train_metrics=c.classification(train_expected,[c.CLASSES[i] for i in train_logits.argmax(axis=1)])
    assert train_metrics==read(E/'head_train_result.json')['metrics']
    soft=train_logits.astype(np.float64);soft-=soft.max(axis=1,keepdims=True);lognorm=np.log(np.exp(soft).sum(axis=1));ce=float(np.mean(lognorm-soft[np.arange(240),[c.CLASSES.index(x) for x in train_expected]]));reg=float(.001*np.mean(head['weight']**2))
    assert math.isclose(ce,read(E/'head_train_result.json')['final_ce'],abs_tol=1e-4) and math.isclose(reg,read(E/'head_train_result.json')['final_regularization'],abs_tol=1e-6)
    tok=r.old.tokenizer('auditor');scored_sets=[]
    for label,expected_ids in [('controls_1',spec['control_ids']),('controls_2',spec['control_ids']),('full_dev',split['validation'])]:
        raw=lines(E/(label+'.jsonl'));saved=lines(E/(label+'_scored.jsonl'));assert [x['example_id'] for x in raw]==expected_ids and len(raw)==len(saved)
        scored=[]
        for x,y in zip(raw,saved):
            assert x=={k:v for k,v in y.items() if k!='metrics'}
            i=ids.index(x['example_id']);row=by[x['example_id']];record=rec[x['example_id']]
            assert x['normalized_prompt']==record['normalized_prompt'] and x['alias_map']==record['alias_map']
            assert x['feature_sha256']==c.digest(features[i].tobytes()) and x['standardized_sha256']==c.digest(standard[i].tobytes())
            logits=standard[i]@head['weight'].T+head['bias'];np.testing.assert_allclose(logits,x['head_logits'],rtol=1e-4,atol=2e-4)
            assert c.CLASSES[int(logits.argmax())]==x['raw_head_class']
            prefix=tok.decode(x['refusal_prefix_tokens'],skip_special_tokens=True);assert prefix==x['refusal_prefix_text'] and len(x['refusal_prefix_tokens'])<=16
            branch=c.probe_state(prefix,x['refusal_prefix_tokens'][-1] in spec['generation']['eos_token_id']);assert branch==x['refusal_veto']
            assert c.route(branch,x['raw_head_class'])==x['final_routed_class']
            assert tok.decode(x['generated_reason_tokens'],skip_special_tokens=True)==x['raw_generated_reason']
            if x['stop_reason']=='reason_quote':
                parsed=c.parse_reason(x['raw_generated_reason']);assert parsed==x['parsed_reason']
                assert c.assemble(row['input'],x['final_routed_class'],parsed['reason'])==x['assembled_json']
                assert x['forced_prefix']==c.forced_prefix(x['final_routed_class'])
            if x['stop_reason']=='refusal':assert x['assembled_json']==c.REFUSAL
            if x['assembled_json']:assert tok(x['assembled_json'],add_special_tokens=False)['input_ids']+[spec['generation']['eos_token_id'][-1]]==x['final_token_ids']
            assert len(x['final_token_ids'])==x['final_token_count']
            metrics=r.score(row,x['assembled_json'],x['error'] is not None);assert metrics==y['metrics'];scored.append(dict(x,metrics=metrics))
        scored_sets.append(scored)
    ignore={'seconds','probe_seconds','reason_seconds','memory'}
    for a,b in zip(scored_sets[0],scored_sets[1]):assert {k:v for k,v in a.items() if k not in ignore}=={k:v for k,v in b.items() if k not in ignore}
    full=scored_sets[2];metrics=r.aggregate([x['metrics'] for x in full]);head_metrics=c.classification([by[x['example_id']]['relation'] for x in full],[x['raw_head_class'] for x in full]);nr=c.nonregression(metrics)
    assert read(E/'metrics.json')==dict(raw_head=head_metrics,final_auditor=metrics,nonregression=nr)
    passed=r.selection_pass(metrics,spec['model']['selection_gates']) and all(nr.values());verdict='AUDITOR_LINEAR_PROBE_PASS' if passed else 'AUDITOR_LINEAR_PROBE_FAIL';assert verdict==status['verdict']
    budget=read(downloaded/'budget.json');timeline=lines(E/'budget_timeline.jsonl')
    assert all(x['continue_run'] and x['epoch']<budget['workload_deadline_epoch'] for x in timeline)
    assert training[-1]['epoch']<budget['workload_deadline_epoch']
    assert read(B/'MANDATORY_WORK_FINISHED.json')['epoch']<budget['workload_deadline_epoch']
    assert termination['billable_duration_upper_bound_seconds']<=3300,'55-minute budget invalidation'
    head_pass=head_metrics['macro_f1']>=.75 and all(x['recall']>=.6 for x in head_metrics['per_class'].values())
    # Contract-invalid explanations can lower valid non-refusal coverage without
    # any routing error. Do not mislabel that as changed refusal/evidence routing.
    routing_regressed=any(not nr[k] for k in ['evidence_f1','refusal_precision','refusal_recall','over_refusal_rate'])
    diagnostic='FULL_AUDITOR_SUCCESS' if passed else 'ROUTING_NONREGRESSION_FAILURE' if routing_regressed else 'EXPLANATION_FAILURE' if head_pass else 'CLASSIFIER_FAILURE'
    failures=[]
    for x in full:
        if not x['metrics']['accepted_outcome']:
            row=by[x['example_id']]
            failures.append(dict(example_id=x['example_id'],expected=row['relation'],raw_head=x['raw_head_class'],routed=x['final_routed_class'],scored_relation=x['metrics']['predicted_relation'],
                relation_correct=x['metrics']['relation_correct'],reason_correct=x['metrics']['reason_correct'],evidence=x['metrics']['evidence'],error=x['error'],
                generated_reason=x['parsed_reason'].get('reason'),expected_reason=None if row['relation']=='INSUFFICIENT_EVIDENCE' else row['semantic_target']['items'][0]['reasoning'],catastrophic=x['metrics']['catastrophic']))
    failed_gates=[]
    for k,v in spec['model']['selection_gates']['minimum'].items():
        if metrics[k] is None or metrics[k]<v:failed_gates.append(dict(gate=k,actual=metrics[k],minimum=v))
    for k,v in spec['model']['selection_gates']['maximum'].items():
        if metrics[k] is None or metrics[k]>v:failed_gates.append(dict(gate=k,actual=metrics[k],maximum=v))
    for k,v in spec['model']['selection_gates']['per_class_recall'].items():
        if metrics['per_class_recall'][k]<v:failed_gates.append(dict(gate='recall_'+k,actual=metrics['per_class_recall'][k],minimum=v))
    for k,v in metrics['catastrophic'].items():
        if v:failed_gates.append(dict(gate=k,actual=v,maximum=0))
    for k,v in nr.items():
        if not v:failed_gates.append(dict(gate='nonregression_'+k,actual=metrics[k]))
    substantive=[x for x in full if x['generated_reason_tokens']]
    routing=dict(raw_head_refusals=sum(x['raw_head_class']=='INSUFFICIENT_EVIDENCE' for x in full),veto_refusals=sum(x['refusal_veto']=='refusal' for x in full),final_refusals=sum(x['metrics']['predicted_refusal'] for x in full),probe_correct=sum((x['refusal_veto']=='refusal')==x['metrics']['expected_refusal'] for x in full),disagreements=[x['example_id'] for x in full if x['raw_head_class']!=x['final_routed_class']])
    perf=dict(feature_seconds=sum(x['seconds'] for x in feature_receipts),feature_tokens=sum(x['input_tokens'] for x in feature_receipts),head_seconds=read(E/'head_train_result.json')['seconds'],
        full_dev_seconds=status['full_dev_seconds'],probe_seconds=sum(x['probe_seconds'] for x in full),reason_seconds=sum(x['reason_seconds'] for x in full),reason_tokens=sum(len(x['generated_reason_tokens']) for x in full),reasons=len(substantive),
        peak_vram_allocated=max(x['memory']['max_memory_allocated'] for x in full),peak_vram_reserved=max(x['memory']['max_memory_reserved'] for x in full))
    telemetry=lines(E/'telemetry.jsonl');gpu=[float(x['gpu'].split(',')[0]) for x in telemetry if x.get('gpu')]
    perf.update(gpu_utilization_mean=sum(gpu)/len(gpu) if gpu else None,cpu_percent_mean=sum(x['cpu_percent'] for x in telemetry)/len(telemetry),peak_rss=max(x['rss'] for x in telemetry),peak_host_ram=max(x['host_ram_used'] for x in telemetry))
    result.update(verdict=verdict,diagnostic=diagnostic,head_sha256=sha(E/'head-200.safetensors'),features=dict(count=300,dimension=3072,train_only_normalization=True),head_training=dict(updates=200,initial_ce=training[0]['ce'],final_ce=ce,final_regularization=reg,train_metrics=train_metrics),raw_head=head_metrics,routing=routing,final_auditor=metrics,nonregression=nr,performance=perf,failed_gates=failed_gates)
    write_json(B/'FAILURE_DIAGNOSIS.json',dict(failed_rows=failures,wrong_relations=sum(not x['relation_correct'] for x in failures),correct_relation_failed_reason=sum(x['relation_correct'] and x['reason_correct'] is not True for x in failures),note='Saved-output local diagnosis; no retuning, generation or semantic rescoring.'))
    write_json(B/'RECOMPUTED_RESULTS.json',result)
    write_json(B/'selection.json',dict(verdict=verdict,eligible_checkpoints=[200] if passed else [],selected_checkpoint=200 if passed else None,
        selected_head_sha256=result['head_sha256'] if passed else None,candidate_head_sha256=result['head_sha256'],mean_sha256=sha(E/'mean.npy'),std_sha256=sha(E/'std.npy'),
        frozen_adapter_sha256=spec['adapter_hashes']['adapter_model.safetensors'],source_commit=manifest['source_commit'],historical_standalone_auditor_eligible=False))
    write_json(B/'POST_RUN_VERIFICATION.json',dict(passed=True,raw_rows=70,dev_rows=60,control_pairs=5,head_updates=200,head_parameters=15365,features=300,backbone_lora_unchanged=True,train_only=True,history_unchanged=True,head_sha256=result['head_sha256']))
    return result


if __name__=='__main__':
    result=analyze();print(json.dumps(result,indent=2))
