"""Verify downloaded final-workflow evidence after teardown; no model forward/training."""
import hashlib
import json
import math
import sys
import tarfile
from collections import Counter
from pathlib import Path
import auditor_final_core as f
import auditor_classifier_lora_core as c

ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/fix/auditor_final_run';D=ROOT/'tuning/auditor_final'


def write(name,value):(B/name).write_bytes((json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode())


def close(a,b):return math.isclose(a,b,rel_tol=2e-6,abs_tol=2e-6)


def analyze():
    f.require((B/'TERMINATION_VERIFIED.json').exists(),'verified termination first')
    f.require(c.read(B/'instances_after.json')==[] and c.read(B/'final_inventory_confirmation.json')['zero_billable_resources'],'empty inventory')
    independent=c.read(B/'independent_inventory_confirmation.json')
    f.require(independent['instances']==[] and independent['temporary_ssh_registration_absent'] and independent['local_key_material_absent'],'independent cleanup check')
    f.require(not (B/'ssh_identity').exists() and not (B/'ssh_identity.pub').exists(),'keys absent')
    for name,digest in c.read(B/'preservation_before.json').items():f.require(c.sha(ROOT/name)==digest,'historical preservation')
    archive=B/'evidence.tar.gz';f.require(c.sha(archive)==c.read(B/'collection_integrity.json')['sha256'],'archive hash')
    target=B/'downloaded';target.mkdir(exist_ok=True)
    with tarfile.open(archive,'r:gz') as tar:
        for m in tar.getmembers():f.require((target/m.name).resolve().is_relative_to(target.resolve()) and (m.isfile() or m.isdir()),'safe archive')
        tar.extractall(target,filter='data')
    e=target/'evidence';manifest=c.read(B/'execution_manifest.json')
    f.require(c.sha(target/'execution_manifest.json')==c.sha(B/'execution_manifest.json'),'executed manifest')
    for name,digest in manifest['files'].items():f.require(c.sha(target/name)==digest,'downloaded executed source '+name)
    events=[json.loads(line) for line in (e/'events.jsonl').read_bytes().splitlines()] if (e/'events.jsonl').exists() else []
    training=c.read(e/'training_status.json') if (e/'training_status.json').exists() else dict(complete=False,updates=0,error='before training status')
    rows=f.train_rows(c.read(D/'records_train_only.json'));plan=c.schedule([r['example_id'] for r in rows]);updates=[r for r in events if r['event']=='update']
    f.require(len(updates)==training['updates'],'completed update count')
    micros={}
    for r in events:
        if r['event']=='microbatch':micros.setdefault(r['update'],[]).append(r)
    for i,r in enumerate(updates,1):
        batch=plan[i-1];f.require(r['update']==i and r['example_ids']==batch['example_ids'] and r['epoch']==batch['epoch'],'TRAIN schedule')
        mb=micros[i];f.require(len(mb)==4 and [x['example_id'] for x in mb]==batch['example_ids'],'microbatch schedule')
        f.require(close(r['ce'],sum(x['ce']['max'] for x in mb)/4),'TRAIN CE recomputation')
        f.require(r['actual_lora_lr']==f.lr(i) and r['actual_head_lr']==f.PARAMS['head_lr'] and r['dropout']==.05,'selected settings')
        f.require(r['train_mode'] and r['post_clip_norm']<=1.00001,'mode/clipping')
        f.require(close(r['pre_clip_norm'],math.hypot(r['head_gradient_norm'],r['lora_gradient_norm'])),'gradient composition')
        for k in ['ce','head_gradient_norm','lora_gradient_norm','head_parameter_norm','lora_parameter_norm','head_parameter_delta_norm','lora_parameter_delta_norm']:
            f.require(math.isfinite(r[k]),'finite telemetry')
    for name in ['training_data_access.json','evaluation_data_access.json']:
        if (e/name).exists():
            access=c.read(e/name);f.require(access['successful_access_counts']==dict.fromkeys(f.FORBIDDEN,0) and access['denied_before_open']==0,'forbidden access receipt')
    result=dict(verdict='AUDITOR_FINAL_INCOMPLETE',training=training,source_commit=manifest['source_commit'],params=f.PARAMS,
        training_updates_verified=len(updates),zero_billable_resources=True,ssh_cleanup=True,historical_evidence_preserved=True,collection_sha256=c.sha(archive),checkpoints=[],selected=None)
    if not training['complete'] and (e/'train_features.npy').exists():
        sys.path.insert(0,str(ROOT/'.tmp/auditor_hpo_deps'))
        import numpy as np
        good=[r for r in events if r['event']=='feature'];features=np.load(e/'train_features.npy',allow_pickle=False)
        f.require([r['index'] for r in good]==list(range(len(good))) and [r['example_id'] for r in good]==[r['example_id'] for r in rows[:len(good)]],'completed feature prefix')
        for record,vector in zip(good,features):f.require(np.isfinite(vector).all() and hashlib.sha256(vector.tobytes()).hexdigest()==record['feature_sha256'],'finite saved feature prefix')
        initialization=c.read(e/'initialization.json');f.require(initialization['base_state_sha256']==c.read(D/'runtime_contract.json')['base_state_sha256'] and initialization['canonical_adapter_sha256']==c.sha(D/'canonical_adapter/adapter_model.safetensors'),'initial base/adapter identity')
        old_path=ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/downloaded/evidence/current_train_features.npy'
        f.require(c.sha(old_path)=='06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287','prior successful TRAIN-only cache identity')
        old_receipt_path=old_path.with_suffix('.jsonl')
        prior_manifest=c.read(ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/EVIDENCE_MANIFEST.json')
        bound=next(r for r in prior_manifest['retained_text'] if r['path']==old_receipt_path.relative_to(ROOT).as_posix())
        f.require(c.sha(old_receipt_path)==bound['sha256'],'prior feature-row receipt identity')
        old_receipts=[json.loads(line) for line in old_receipt_path.read_bytes().splitlines()]
        f.require([r['example_id'] for r in old_receipts]==[r['example_id'] for r in rows],'same prior feature row order')
        f.require(all(r['token_sha256']==old_receipts[i]['token_sha256'] for i,r in enumerate(good)),'same observed token inputs')
        old=np.load(old_path,allow_pickle=False);count=len(good)
        result['feature_failure_evidence']=dict(completed_valid_rows=count,attempted_row_one_based=count+1,inferred_attempted_example_id=rows[count]['example_id'],
            completed_prefix_matches_prior_cache_bitwise=bool(np.array_equal(features[:count],old[:count])),completed_prefix_max_abs_difference=float(np.max(np.abs(features[:count]-old[:count]))) if count else None,
            prior_attempted_row_finite=bool(np.isfinite(old[count]).all()),offending_current_tensor_saved=False,
            normalization_created=(e/'mean.npy').exists(),head_fit_created=(e/'head_fit.json').exists(),optimizer_created=(e/'optimizer_initial.json').exists(),
            failure='Combined hidden shape==(3072,) and finite-value guard; offending shape/values not recorded, so exact cause remains unisolated.',
            incomplete_feature_file_reusable=False,unwritten_rows_are_not_observations=True)
        f.require(not (B/'TRAINING_RELEASE.json').exists() and not (B/'evaluation_transfer_timing.json').exists(),'no evaluation payload released')
        f.require(not any((e/f'checkpoint-{step}').exists() for step in [0,448,896]),'no candidate checkpoints')
    if training['complete']:
        f.admit_evaluation(c.read(e/'TRAINING_COMPLETE.json'));f.require(len(updates)==896,'896 updates')
        f.require(Counter(i for r in updates for i in r['example_ids'])==Counter({r['example_id']:2 for r in rows}),'two full TRAIN passes')
        feature_events=[r for r in events if r['event']=='feature'];f.require([r['example_id'] for r in feature_events]==[r['example_id'] for r in rows],'one full feature pass')
        f.require(len([r for r in events if r['event']=='head_fit'])==200,'fresh head200')
        f.require(len([r for r in events if r['event']=='control_parity'])==16,'16 parity controls')
        optimizer=c.read(e/'optimizer_initial.json');f.require(optimizer['state_empty'] and optimizer['gradients_empty'] and optimizer['seed']==7 and optimizer['params']==f.PARAMS,'fresh optimizer')
        sys.path.insert(0,str(ROOT/'.tmp/auditor_hpo_deps'))
        import numpy as np
        f.require(np.__version__==c.read(D/'runtime_contract.json')['packages']['numpy'],'pinned local normalization arithmetic')
        from safetensors.numpy import load_file
        features=np.load(e/'train_features.npy',allow_pickle=False);mean=np.load(e/'mean.npy',allow_pickle=False);std=np.load(e/'std.npy',allow_pickle=False)
        f.require(features.shape==(1792,3072) and features.dtype==np.float32 and np.isfinite(features).all(),'saved full TRAIN features')
        f.require(np.array_equal(mean,features.mean(axis=0,dtype=np.float32)) and np.array_equal(std,np.maximum(features.std(axis=0,ddof=0,dtype=np.float32),np.float32(1e-6))),'TRAIN-only normalization recomputation')
        for record,vector in zip(feature_events,features):f.require(hashlib.sha256(vector.tobytes()).hexdigest()==record['feature_sha256'],'feature row binding')
        for step in [0,448,896]:
            folder=e/f'checkpoint-{step}';identity=c.read(folder/'identity.json')
            for p,k in [(folder/'classifier_fork/adapter_model.safetensors','lora_sha256'),(folder/'classifier_fork/adapter_config.json','config_sha256'),(folder/'head.safetensors','head_sha256'),(e/'mean.npy','mean_sha256'),(e/'std.npy','std_sha256')]:f.require(c.sha(p)==identity[k],'checkpoint hash')
            arrays=load_file(str(folder/'classifier_fork/adapter_model.safetensors'));head=load_file(str(folder/'head.safetensors'))
            f.require(len(arrays)==448 and sum(x.size for x in arrays.values())==14942208 and all(np.isfinite(x).all() for x in [*arrays.values(),*head.values()]),'finite saved candidate')
            if step:
                state=c.read(folder/'optimizer_state.json');f.require(state['parameters_with_state']==450 and state['min_step']==state['max_step']==step and state['moments_finite'],'Adam states')
        result['normalization_verified']=True
        # Opening actual DEV/challenge data is permitted only after verified896 completion.
        if (e/'status.json').exists() and c.read(e/'status.json')['complete']:
            release=c.read(B/'TRAINING_RELEASE.json');access=c.read(e/'evaluation_data_access.json');completion=c.read(e/'TRAINING_COMPLETE.json')
            f.require(completion['epoch']<=release['epoch']<=access['evaluation_open_epoch'] and access['evaluation_opened_after_updates']==896,'delayed evaluation chronology')
            f.require([access[k] for k in ['external_dev_rows','historical_dev_rows','shorter_rows','longer_rows']]==[200,48,75,75],'evaluation populations')
            for name,digest in f.EVAL_HASHES.items():f.require(c.sha(ROOT/'tuning/auditor_classifier_lora'/name)==digest,'original evaluation data unchanged')
            records=c.read(ROOT/'tuning/auditor_classifier_lora/records.json');challenges=c.read(ROOT/'tuning/auditor_classifier_lora/challenges.json');f.validate_evaluation(records,challenges,rows)
            checkpoints=[]
            for step in [448,896]:
                saved=c.read(e/f'checkpoint-{step}/results.json');predictions=c.read(e/f'checkpoint-{step}/predictions.json')
                f.require([p['example_id'] for p in predictions]==[r['example_id'] for r in records[1792:]],'evaluation order')
                for p,row in zip(predictions,records[1792:]):
                    v=p['logits'];maximum=max(v);ce=math.log(sum(math.exp(x-maximum) for x in v))+maximum-v[c.CLASSES.index(row['relation'])]
                    f.require(close(ce,p['ce']) and p['expected']==row['relation'] and p['train_mode'] is False,'saved logits CE/labels/mode')
                recomputed=f.evaluate(records,predictions,challenges);f.require(recomputed==saved['metrics'],'recomputed final metrics')
                checkpoints.append(saved)
            selection=f.select(checkpoints);f.require(selection==c.read(e/'selection.json'),'best usable selection')
            result.update(verdict=selection['verdict'],selected=selection,checkpoints=checkpoints,delayed_evaluation_verified=True,evaluation_data_access=access)
            selected=dict(selection['selected_identity'],source_commit=manifest['source_commit'],hyperparameters=f.PARAMS,checkpoint_path=(e/f"checkpoint-{selection['selected_step']}").relative_to(ROOT).as_posix(),normalization_paths=[(e/n).relative_to(ROOT).as_posix() for n in ['mean.npy','std.npy']],base=c.read(D/'runtime_contract.json'),quality_gates_passed=selection['all_old_quality_gates_pass'],final_test_consumed=False,automatic_further_training=False)
            write('SELECTED_FINAL_AUDITOR.json',selected)
    launch=c.read(B/'launch.json');end=c.read(B/'final_inventory_confirmation.json')['epoch'];rate=c.read(B/'manifest.json')['hourly_rate']
    result.update(duration_upper_bound_seconds=end-launch['epoch'],hourly_rate=rate,estimated_cost_upper_bound_usd=(end-launch['epoch'])*rate/3600,
        numerical_summary=dict(completed_updates=len(updates),max_completed_mean_ce=max((r['ce'] for r in updates),default=None),max_post_clip_norm=max((r['post_clip_norm'] for r in updates),default=None),
            head_and_lora_nonzero_deltas_every_update=all(r['head_parameter_delta_norm']>0 and r['lora_parameter_delta_norm']>0 for r in updates) if updates else None),
        limitations=('Independent saved-logit metrics/CE, schedules, numeric artifacts and hashes verified.' if result['selected'] else 'No checkpoint evaluation exists; no quality metrics can be reported. Saved failure evidence/source/artifact hashes verified.')+' No model forward or new training. Refusal/explanation/evidence-generation metrics are not applicable.')
    write('RECOMPUTED_RESULTS.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['checkpoints','evaluation_data_access']},indent=2))


if __name__=='__main__':analyze()
