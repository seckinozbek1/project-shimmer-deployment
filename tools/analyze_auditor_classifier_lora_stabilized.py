"""Local post-teardown verification, saved-logit recomputation and evidence manifest."""
import json
import math
from pathlib import Path
import tarfile
import numpy as np
import auditor_classifier_lora_core as c
import auditor_classifier_lora_stable as stable
import auditor_classifier_lora_fork as fork
import auditor_v2_execution as previous
from cloud_run_common import write_json,credential_locations

ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/fix/auditor_classifier_lora_stabilized_run';D=ROOT/'tuning/auditor_classifier_lora_fork'
def lines(p):return [json.loads(x) for x in p.read_bytes().splitlines()] if p.exists() else []


def analyze():
    termination=c.read(B/'TERMINATION_VERIFIED.json')
    assert c.read(B/'final_inventory_confirmation.json')['zero_billable_resources']
    assert c.read(B/'instances_after.json')==[]
    assert c.read(B/'cleanup.json')['temporary_ssh_removed'] and c.read(B/'cleanup.json')['local_key_material_removed']
    assert not (B/'ssh_identity').exists() and not (B/'ssh_identity.pub').exists()
    assert c.sha(B/'evidence.tar.gz')==c.read(B/'collection_integrity.json')['sha256']
    target=B/'downloaded';target.mkdir(exist_ok=True)
    with tarfile.open(B/'evidence.tar.gz') as archive:
        for m in archive.getmembers():assert (target/m.name).resolve().is_relative_to(target.resolve()) and (m.isfile() or m.isdir())
        archive.extractall(target,filter='data')
    E=target/'evidence';manifest=c.read(B/'execution_manifest.json')
    assert c.sha(target/'execution_manifest.json')==c.sha(B/'execution_manifest.json')
    for name,digest in manifest['files'].items():
        if (target/name).is_file():assert c.sha(target/name)==digest,name
    for name,digest in c.read(B/'preservation_before.json').items():assert c.sha(ROOT/name)==digest,name
    status=c.read(E/'status.json') if (E/'status.json').exists() else dict(verdict='AUDITOR_CLASSIFIER_LORA_INDETERMINATE',complete=False,updates=0)
    records=c.read(ROOT/'tuning/auditor_classifier_lora/records.json');plan=c.read(ROOT/'tuning/auditor_classifier_lora/schedule.json')
    challenges=c.read(ROOT/'tuning/auditor_classifier_lora/challenges.json');baseline=c.read(D/'train_baseline.json')
    history=lines(E/'training.jsonl');assert len(history)==status['updates']
    for row,batch in zip(history,plan):
        assert all(row[k]==batch[k] for k in ['step','epoch','example_ids'])
        assert math.isfinite(row['ce']) and row['ce']<=13.862943611198906
    numerical=lines(E/'numerical_health.jsonl');parity=lines(E/'update0_parity.jsonl');outputs=lines(E/'update0_predictions.jsonl')
    control_events=[x for x in parity if x['event']=='control_parity']
    update0=dict(passed=False,controls_compared=len(control_events),max_hidden_error=max([x['max_errors']['hidden'] for x in control_events],default=None),max_logit_error=max([x['max_errors']['logits'] for x in control_events],default=None),rows_observed=len(outputs),failure_events=[x for x in parity if x['event']=='NO_GO'])
    if len(outputs)>=32:
        reference=outputs[:16];candidate=outputs[16:32];controls=c.read(D/'update0_controls.json')
        assert [x['example_id'] for x in reference]==[x['example_id'] for x in candidate]==controls['example_ids']
        a=np.asarray([x['logits'] for x in reference],dtype=np.float32);b=np.asarray([x['logits'] for x in candidate],dtype=np.float32)
        expected=np.asarray(controls['logits'],dtype=np.float32)
        np.testing.assert_allclose(a,b,rtol=1e-4,atol=2e-4)
        assert [x['active_adapters'] for x in reference]==[['historical_reference']]*16 and [x['active_adapters'] for x in candidate]==[['classifier_fork']]*16
        ce=float(stable.ce_numpy(np,b,np.asarray(controls['labels'])).mean(dtype=np.float32))
        update0.update(reference_fork_passed=len(control_events)==16,reference_fork_argmax_identity=bool(np.array_equal(a.argmax(axis=1),b.argmax(axis=1))),
            max_normalized_error=max([x['max_errors']['normalized'] for x in control_events],default=None),max_ce_error=max([x['ce_error'] for x in control_events],default=None),
            cached_control_max_logit_error=float(np.max(np.abs(b-expected))),cached_control_logits_pass=bool(np.allclose(b,expected,rtol=1e-4,atol=2e-4)),
            cached_control_argmax_matches=int(np.sum(b.argmax(axis=1)==expected.argmax(axis=1))),control_ce=ce,expected_control_ce=controls['expected_ce'],full_train_baseline_run=False)
    if (E/'update0_summary.json').exists():
        assert c.read(E/'update0_summary.json')['passed'] and len(outputs)==1824 and len(control_events)==16
        reference=outputs[:16];candidate=outputs[16:32]
        assert [x['example_id'] for x in reference]==[x['example_id'] for x in candidate]==c.read(D/'update0_controls.json')['example_ids']
        for a,b in zip(reference,candidate):
            assert a['active_adapters']==['historical_reference'] and b['active_adapters']==['classifier_fork']
            np.testing.assert_allclose(a['logits'],b['logits'],rtol=1e-4,atol=2e-4);assert a['predicted']==b['predicted']
        full=outputs[32:];assert [x['example_id'] for x in full]==baseline['example_ids']
        vectors=np.asarray([x['logits'] for x in full],dtype=np.float32);pred=vectors.argmax(axis=1).tolist()
        assert pred==baseline['predicted_indices']
        labels=np.asarray([c.CLASSES.index(x) for x in baseline['labels']])
        ce=float(stable.ce_numpy(np,vectors,labels).mean(dtype=np.float32))
        assert baseline['ce_range'][0]<=ce<=baseline['ce_range'][1]
        assert previous.metrics(baseline['labels'],[c.CLASSES[i] for i in pred])==baseline['metrics']
        update0.update(passed=True,train_ce=ce,argmax_identity=True)
    inventory=None
    if (E/'parameter_inventory.json').exists():
        inv=c.read(E/'parameter_inventory.json');normalized=[dict(x,name=x['name'].replace('.classifier_fork.','.default.')) for x in inv['items']]
        inventory=c.inventory(normalized);assert inventory==inv['counts'] and inv['reference_removed']
        optimizer=c.read(E/'optimizer.json');assert optimizer['config']==c.read(D/'experiment.json')['optimizer']
        assert optimizer['groups']==[dict(lr=1e-4,parameters=14942208),dict(lr=1e-3,parameters=12292)]
    checkpoints=[]
    for step in [448,896]:
        folder=E/f'checkpoint-{step}'
        if not (folder/'results.json').exists():continue
        saved=c.read(folder/'results.json');identity=c.read(folder/'identity.json')
        assert c.sha(folder/'classifier_fork/adapter_model.safetensors')==identity['lora_sha256']
        assert c.sha(folder/'head.safetensors')==identity['head_sha256']
        assert c.sha(folder/'classifier_fork/adapter_config.json')==identity['config_sha256']
        out=lines(folder/'external_dev.jsonl')+lines(folder/'historical_dev.jsonl')
        assert [x['example_id'] for x in out]==[r['example_id'] for r in records[1792:]]
        predictions={}
        for x in out:
            vector=np.asarray(x['logits'],dtype=np.float32);assert vector.shape==(4,) and np.isfinite(vector).all()
            pred=c.CLASSES[int(vector.argmax())];assert pred==x['predicted'];predictions[x['example_id']]=pred
        metrics=c.evaluate(records,predictions,challenges);assert metrics==saved['metrics']
        assert saved['base_state_sha256']==c.read(E/'initialization.json')['base_state_sha256']
        checkpoints.append(dict(identity,complete=True,metrics=metrics))
    admission=c.read(E/'admission20.json') if (E/'admission20.json').exists() else None
    partial=None
    if not history and (E/'finite_partial_state.safetensors').exists():
        tensors=fork.inventory(E/'finite_partial_state.safetensors')
        adapter={k.replace('.classifier_fork.','.'):v for k,v in tensors.items() if '.classifier_fork.' in k}
        head={k.removeprefix('head.'):v for k,v in tensors.items() if k.startswith('head.')}
        assert adapter==c.read(D/'adapter_copy.json')['tensors']
        assert head==fork.inventory(ROOT/c.read(D/'experiment.json')['initialization_artifacts']['head-200.safetensors']['path'])
        assert not (E/'optimizer.json').exists()
        partial=dict(finite_partial_state_sha256=c.sha(E/'finite_partial_state.safetensors'),fork_tensors=448,fork_values_unchanged=True,head_values_unchanged=True,partial_tensor_parameters=sum(math.prod(v['shape']) for v in tensors.values()),optimizer_created=False,training_updates=0,reference_removal_reached=False,final_base_hash_available=False)
        write_json(B/'PARTIAL_STATE_VERIFICATION.json',partial)
    if status['complete']:
        assert len(history)==896 and update0['passed'] and admission['passed'] and not admission['dev_evaluated']
        assert len([x for x in numerical if x['event']=='update_complete'])==896
        assert not any(x['event']=='STOP' for x in numerical)
        final=c.read(E/'frozen_final.json');assert final['base_unchanged'] and final['historical_adapter_unchanged']
        assert final['base_state_sha256']==c.read(E/'initialization.json')['base_state_sha256']
        selection=c.select(checkpoints,896);assert selection==c.read(E/'selection.json') and selection['verdict']==status['verdict']
    else:selection=dict(verdict='AUDITOR_CLASSIFIER_LORA_INDETERMINATE',selected=None,passing=[])
    telemetry=lines(E/'telemetry.jsonl');durations=[x['update_seconds'] for x in history]
    gpu=[list(map(float,x['gpu'].split(','))) for x in telemetry if x.get('gpu') and len(x['gpu'].split(','))==3]
    result=dict(selection,cloud=termination,tested_commit=manifest['source_commit'],update0=update0,admission20=admission,trainable=inventory,
        training=dict(updates=len(history),first_ce=history[0]['ce'] if history else None,last_ce=history[-1]['ce'] if history else None,
            median_update_seconds=float(np.median(durations)) if durations else None,p95_update_seconds=float(np.percentile(durations,95)) if durations else None,
            peak_allocated_gib=max([x['peak_allocated_gib'] for x in history],default=None)),
        checkpoints=checkpoints,status=status,numerical_failures=[x for x in numerical if x['event']=='STOP'],telemetry_samples=len(telemetry),
        gpu_telemetry=dict(scope='whole remote model workload, including load and preflight',mean_utilization_percent=float(np.mean([x[0] for x in gpu])) if gpu else None,p95_utilization_percent=float(np.percentile([x[0] for x in gpu],95)) if gpu else None,peak_device_memory_mib=max([x[1] for x in gpu],default=None)),
        partial_state=partial,historical_preservation_verified=True,holdout_unconsumed=True,zero_billable_resources=True)
    write_json(B/'RECOMPUTED_RESULTS.json',result)
    if selection['selected']:write_json(B/'SELECTED_CLASSIFIER.json',dict(selection['selected'],immutable=True,integration_authorized=False))
    print(json.dumps(result,indent=2));return result


if __name__=='__main__':analyze()
