"""Post-teardown verification of fresh current-runtime artifacts and saved logits."""
import json
import math
from pathlib import Path
import tarfile
import numpy as np
from safetensors.numpy import load_file
import auditor_classifier_lora_core as c
import auditor_classifier_lora_current_core as current
import auditor_classifier_lora_stable as stable
import auditor_classifier_lora_fork as fork
from cloud_run_common import write_json

ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run';D=ROOT/'tuning/auditor_classifier_lora_current_runtime'
def lines(p):return [json.loads(x) for x in p.read_bytes().splitlines()] if p.exists() else []


def analyze():
    termination=c.read(B/'TERMINATION_VERIFIED.json');assert c.read(B/'final_inventory_confirmation.json')['zero_billable_resources'] and c.read(B/'instances_after.json')==[]
    cleanup=c.read(B/'cleanup.json');assert cleanup['temporary_ssh_removed'] and cleanup['local_key_material_removed']
    assert not (B/'ssh_identity').exists() and not (B/'ssh_identity.pub').exists()
    assert c.sha(B/'evidence.tar.gz')==c.read(B/'collection_integrity.json')['sha256']
    target=B/'downloaded';target.mkdir(exist_ok=True)
    with tarfile.open(B/'evidence.tar.gz') as archive:
        for m in archive.getmembers():assert (target/m.name).resolve().is_relative_to(target.resolve()) and (m.isfile() or m.isdir())
        archive.extractall(target,filter='data')
    E=target/'evidence';manifest=c.read(B/'execution_manifest.json')
    assert c.sha(target/'execution_manifest.json')==c.sha(B/'execution_manifest.json')
    for name,h in manifest['files'].items():
        assert not any(x in name for x in ['head-200','mean.npy','std.npy','features.npy','train_baseline'])
        if (target/name).exists():assert c.sha(target/name)==h
    for name,h in c.read(B/'preservation_before.json').items():assert c.sha(ROOT/name)==h
    status=c.read(E/'status.json') if (E/'status.json').exists() else dict(verdict='AUDITOR_CLASSIFIER_LORA_INDETERMINATE',complete=False,updates=0)
    records=c.read(ROOT/'tuning/auditor_classifier_lora/records.json');train=records[:1792];plan=c.read(ROOT/'tuning/auditor_classifier_lora/schedule.json');challenges=c.read(ROOT/'tuning/auditor_classifier_lora/challenges.json')
    features_meta=lines(E/'current_train_features.jsonl');head_training=lines(E/'head_training.jsonl');head_result=None;normalization=None
    if (E/'normalization.json').exists():
        assert len(features_meta)==1792
        features=np.load(E/'current_train_features.npy',allow_pickle=False)
        for index,(row,meta,value) in enumerate(zip(train,features_meta,features)):
            assert meta['index']==index and meta['example_id']==row['example_id'] and meta['token_sha256']==fork.token_hash(row['input_ids'])
            assert meta['prompt_sha256']==row['prompt_sha256'] and meta['feature_sha256']==__import__('hashlib').sha256(value.tobytes()).hexdigest() and np.isfinite(value).all()
        mean,std=current.normalize(np,features,train)
        np.testing.assert_array_equal(mean,np.load(E/'mean.npy',allow_pickle=False));np.testing.assert_array_equal(std,np.load(E/'std.npy',allow_pickle=False))
        normalization=c.read(E/'normalization.json');assert not normalization['dev_fit'] and normalization['train_ids']==[r['example_id'] for r in train]
        assert normalization['mean_sha256']==c.sha(E/'mean.npy') and normalization['std_sha256']==c.sha(E/'std.npy') and normalization['feature_sha256']==c.sha(E/'current_train_features.npy')
    if (E/'head_result.json').exists():
        head_result=c.read(E/'head_result.json');assert len(head_training)==200 and [x['step'] for x in head_training]==list(range(1,201))
        assert all(math.isfinite(x['ce']) and math.isfinite(x['regularization']) and math.isclose(x['ce']+x['regularization'],x['loss']) for x in head_training)
        zero=load_file(str(E/'head-0.safetensors'));assert all(np.count_nonzero(v)==0 for v in zero.values())
        head=load_file(str(E/'head-200.safetensors'));assert c.sha(E/'head-200.safetensors')==head_result['head_sha256']
        _,logits=stable.fp32_numpy(np,features,head['weight'],head['bias'],mean,std)
        saved=lines(E/'head_train_predictions.jsonl');assert [r['example_id'] for r in saved]==[r['example_id'] for r in train]
        np.testing.assert_allclose(logits,np.asarray([r['logits'] for r in saved],dtype=np.float32),rtol=1e-4,atol=2e-4)
        labels=np.asarray([c.CLASSES.index(r['relation']) for r in train]);ce=float(stable.ce_numpy(np,logits,labels).mean(dtype=np.float32))
        metrics=c.metrics([r['relation'] for r in train],[c.CLASSES[i] for i in logits.argmax(axis=1)])
        assert metrics==head_result['metrics'] and math.isclose(ce,head_result['ce'],rel_tol=1e-4,abs_tol=1e-4)
        assert head_result['repeat_forward_and_gradients_all_200']
    parity=lines(E/'update0_parity.jsonl');controls=[r for r in parity if r['event']=='control_parity'];outputs=lines(E/'update0_predictions.jsonl')
    live=dict(controls=len(controls),max_hidden_error=max([x['max_errors']['hidden'] for x in controls],default=None),max_normalized_error=max([x['max_errors']['normalized'] for x in controls],default=None),max_logit_error=max([x['max_errors']['logits'] for x in controls],default=None),max_ce_error=max([x['ce_error'] for x in controls],default=None))
    baseline=None;ceiling=None
    if (E/'update0_summary.json').exists():
        baseline=c.read(E/'update0_summary.json');assert baseline['passed'] and len(controls)==16 and len(outputs)==1824
        a=outputs[:16];b=outputs[16:32]
        assert [x['example_id'] for x in a]==[x['example_id'] for x in b]==c.read(D/'controls.json')['example_ids']
        for left,right in zip(a,b):
            np.testing.assert_allclose(left['logits'],right['logits'],rtol=1e-4,atol=2e-4);assert left['predicted']==right['predicted']
        live.update(passed=True,argmax_identity=True)
        out=outputs[32:];assert [x['example_id'] for x in out]==[r['example_id'] for r in train]
        vector=np.asarray([x['logits'] for x in out],dtype=np.float32);ce=float(stable.ce_numpy(np,vector,labels).mean(dtype=np.float32))
        metrics=c.metrics([r['relation'] for r in train],[c.CLASSES[i] for i in vector.argmax(axis=1)])
        assert metrics==head_result['metrics']==baseline['metrics']
        assert vector.argmax(axis=1).tolist()==logits.argmax(axis=1).tolist() and math.isclose(ce,baseline['ce'],abs_tol=1e-6)
        ceiling=c.read(E/'runtime_ceilings.json');assert ceiling==current.ceilings(baseline['ce'])
    history=lines(E/'training.jsonl');assert len(history)==status['updates']
    for row,batch in zip(history,plan):
        assert all(row[k]==batch[k] for k in ['step','epoch','example_ids'])
        assert math.isfinite(row['ce']) and row['ce']<=ceiling['mean_update_ce_ceiling']
    inventory=None
    if (E/'parameter_inventory.json').exists():
        inv=c.read(E/'parameter_inventory.json');inventory=c.inventory([dict(x,name=x['name'].replace('.classifier_fork.','.default.')) for x in inv['items']]);assert inventory==inv['counts']
        assert inv['reference_removed'] and not any('historical_reference' in x['name'] for x in inv['items'])
        optimizer=c.read(E/'optimizer.json');assert optimizer['config']==c.read(D/'experiment.json')['optimizer']
        assert optimizer['groups']==[dict(lr=1e-4,parameters=14942208),dict(lr=1e-3,parameters=12292)]
    if (E/'checkpoint-0/identity.json').exists():
        initial=c.read(E/'checkpoint-0/identity.json')
        assert initial['lora_sha256']==fork.SOURCE_SHA and initial['config_sha256']==fork.CONFIG_SHA
        assert c.sha(E/'checkpoint-0/classifier_fork/adapter_model.safetensors')==initial['lora_sha256']
        assert c.sha(E/'checkpoint-0/head.safetensors')==initial['head_sha256']==head_result['head_sha256']
        assert initial['mean_sha256']==normalization['mean_sha256'] and initial['std_sha256']==normalization['std_sha256']
        provenance=c.read(E/'fork_provenance.json');assert provenance['exact_equal'] and provenance['source_unchanged'] and provenance['tensors_compared']==448
    checkpoints=[]
    for step in [448,896]:
        folder=E/f'checkpoint-{step}'
        if not (folder/'results.json').exists():continue
        saved=c.read(folder/'results.json');identity=c.read(folder/'identity.json')
        assert c.sha(folder/'classifier_fork/adapter_model.safetensors')==identity['lora_sha256'] and c.sha(folder/'head.safetensors')==identity['head_sha256']
        assert identity['mean_sha256']==normalization['mean_sha256'] and identity['std_sha256']==normalization['std_sha256']
        out=lines(folder/'external_dev.jsonl')+lines(folder/'historical_dev.jsonl');assert [x['example_id'] for x in out]==[r['example_id'] for r in records[1792:]]
        predictions={}
        for x in out:
            vector=np.asarray(x['logits'],dtype=np.float32);assert np.isfinite(vector).all();pred=c.CLASSES[int(vector.argmax())];assert pred==x['predicted'];predictions[x['example_id']]=pred
        metrics=c.evaluate(records,predictions,challenges);assert metrics==saved['metrics']
        checkpoints.append(dict(identity,complete=True,metrics=metrics))
    numerical=lines(E/'numerical_health.jsonl');admission=c.read(E/'admission20.json') if (E/'admission20.json').exists() else None
    failures=[];context=None
    for event in numerical:
        if event['event']=='microbatch_boundary':context=dict(update=event['update'],microbatch=event['microbatch'])
        if event['event']=='STOP':failures.append(dict(event,**(context or {})))
    partial=None
    if (E/'finite_partial_state.safetensors').exists():
        inv=fork.inventory(E/'finite_partial_state.safetensors')
        assert len(inv)==450 and sum(math.prod(v['shape']) for v in inv.values())==14954500
        assert all(v['dtype']=='F32' for v in inv.values())
        partial=dict(sha256=c.sha(E/'finite_partial_state.safetensors'),tensors=450,parameters=14954500,selected=False)
    if status['complete']:
        assert head_result and baseline['passed'] and admission['passed'] and not admission['dev_evaluated'] and len(history)==896
        assert not any(x['event']=='STOP' for x in numerical)
        final=c.read(E/'frozen_final.json');assert final['base_unchanged'] and final['historical_adapter_unchanged'] and final['base_state_sha256']==c.read(E/'initialization.json')['base_state_sha256']
        selection=c.select(checkpoints,896);assert selection==c.read(E/'selection.json') and selection['verdict']==status['verdict']
    else:selection=dict(verdict='AUDITOR_CLASSIFIER_LORA_INDETERMINATE',selected=None,passing=[])
    telemetry=lines(E/'telemetry.jsonl');gpu=[list(map(float,x['gpu'].split(','))) for x in telemetry if x.get('gpu') and len(x['gpu'].split(','))==3];durations=[x['update_seconds'] for x in history]
    result=dict(selection,tested_commit=manifest['source_commit'],cloud=termination,status=status,head_rebase=dict(features=len(features_meta),head_updates=len(head_training),normalization=normalization,head_result=head_result),live_parity=live,current_baseline=baseline,ceilings=ceiling,admission20=admission,trainable=inventory,
        training=dict(updates=len(history),first_ce=history[0]['ce'] if history else None,final_ce=history[-1]['ce'] if history else None,median_update_seconds=float(np.median(durations)) if durations else None,p95_update_seconds=float(np.percentile(durations,95)) if durations else None,peak_allocated_gib=max([x['peak_allocated_gib'] for x in history],default=None)),
        checkpoints=checkpoints,numerical_failures=failures,partial_state=partial,admission20_status='PASS' if admission and admission['passed'] else 'FAIL_NUMERICAL_STOP' if failures else 'NOT_REACHED',gpu_telemetry=dict(samples=len(gpu),scope='whole workload including extraction/head/preflight',mean_utilization_percent=float(np.mean([x[0] for x in gpu])) if gpu else None,peak_device_memory_mib=max([x[1] for x in gpu],default=None)),historical_preservation_verified=True,old_cached_anchor_used=False,holdout_unconsumed=True,zero_billable_resources=True)
    write_json(B/'RECOMPUTED_RESULTS.json',result)
    if selection['selected']:write_json(B/'SELECTED_CLASSIFIER.json',dict(selection['selected'],mean_sha256=normalization['mean_sha256'],std_sha256=normalization['std_sha256'],immutable=True,integration_authorized=False))
    print(json.dumps({k:result[k] for k in ['verdict','status','live_parity','training','numerical_failures']},indent=2));return result


if __name__=='__main__':analyze()
