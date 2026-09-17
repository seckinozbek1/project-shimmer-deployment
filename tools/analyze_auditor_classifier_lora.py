"""After verified teardown, recompute checkpoint logits/metrics and selection."""
import hashlib
import json
import math
from pathlib import Path
import sys
import tarfile
import auditor_classifier_lora_core as c
from cloud_run_common import write_json,credential_locations

ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/fix/auditor_classifier_lora_run';D=ROOT/'tuning/auditor_classifier_lora'


def lines(p):return [json.loads(x) for x in Path(p).read_bytes().splitlines()]


def analyze():
    assert c.read(B/'TERMINATION_VERIFIED.json') and c.read(B/'final_inventory_confirmation.json')['zero_billable_resources']
    assert c.read(B/'instances_after.json')==[]
    assert c.read(B/'cleanup.json')['temporary_ssh_removed'] and c.read(B/'cleanup.json')['local_key_material_removed']
    assert not (B/'ssh_identity').exists() and not (B/'ssh_identity.pub').exists()
    assert c.sha(B/'evidence.tar.gz')==c.read(B/'collection_integrity.json')['sha256']
    target=B/'downloaded';target.mkdir(exist_ok=True)
    with tarfile.open(B/'evidence.tar.gz') as archive:
        for m in archive.getmembers():
            assert (target/m.name).resolve().is_relative_to(target.resolve()) and (m.isfile() or m.isdir())
        archive.extractall(target,filter='data')
    E=target/'evidence';status=c.read(E/'status.json')
    assert c.sha(target/'execution_manifest.json')==c.sha(B/'execution_manifest.json')
    manifest=c.read(B/'execution_manifest.json')
    for name,digest in manifest['files'].items():
        if (target/name).is_file():assert c.sha(target/name)==digest,name
    for name,digest in c.read(B/'preservation_before.json').items():assert c.sha(ROOT/name)==digest,name
    if not status['complete']:
        result=dict(status,selected=None,passing=[],cloud=c.read(B/'TERMINATION_VERIFIED.json'))
        write_json(B/'RECOMPUTED_RESULTS.json',result);return result
    assert status['updates']==896 and status['examples']==3584 and status['passes']==2
    records=c.read(D/'records.json');spec=c.read(D/'experiment.json');challenges=c.read(D/'challenges.json');plan=c.read(D/'schedule.json')
    c.validate(records,spec,challenges,plan)
    inventory=c.read(E/'parameter_inventory.json');assert c.inventory(inventory['items'])==inventory['counts']
    assert inventory['historical_adapter_loaded'] is False
    optimizer=c.read(E/'optimizer.json');assert optimizer['config']==spec['optimizer']
    assert optimizer['groups']==[dict(lr=1e-4,parameters=c.LORA_PARAMS),dict(lr=.01,parameters=c.HEAD_PARAMS)]
    history=lines(E/'training.jsonl');assert len(history)==896
    for row,batch in zip(history,plan):
        assert all(row[k]==batch[k] for k in ['step','epoch','example_ids'])
        assert row['examples_processed']==row['step']*4 and row['lrs']==[1e-4,.01]
        assert all(math.isfinite(row[k]) for k in ['ce','regularization','loss','gradient_norm'])
        assert math.isclose(row['ce']+row['regularization'],row['loss'],abs_tol=1e-6)
    assert math.isclose(history[0]['ce'],math.log(4),abs_tol=1e-6) and history[0]['regularization']==0
    import numpy as np
    from safetensors.numpy import load_file
    init=c.read(E/'initialization.json');assert init['fresh_lora'] and init['head_zero'] and init['lora_B_zero'] and not init['historical_adapter_loaded']
    for step in [0,448,896]:
        identity=c.read(E/f'checkpoint-{step}/identity.json')
        assert c.sha(E/f'checkpoint-{step}/adapter_model.safetensors')==identity['lora_sha256']
        assert c.sha(E/f'checkpoint-{step}/head.safetensors')==identity['head_sha256']
        assert c.sha(E/f'checkpoint-{step}/adapter_config.json')==identity['config_sha256']
        weights=load_file(str(E/f'checkpoint-{step}/adapter_model.safetensors'))
        assert len(weights)==448 and sum(v.size for v in weights.values())==c.LORA_PARAMS
        assert all('.lora_A.' in n or '.lora_B.' in n for n in weights)
        if step==0:
            assert all((v==0).all() for n,v in weights.items() if '.lora_B.' in n)
            assert all((v==0).all() for v in load_file(str(E/'checkpoint-0/head.safetensors')).values())
        config=c.read(E/f'checkpoint-{step}/adapter_config.json')
        for key in ['r','lora_alpha','lora_dropout','bias','task_type']:assert config[key]==spec['lora'][key]
        assert set(config['target_modules'])==set(c.TARGETS)
    checkpoints=[]
    for step in [448,896]:
        folder=E/f'checkpoint-{step}';saved=c.read(folder/'results.json');identity=c.read(folder/'identity.json')
        features=np.load(folder/'dev_features.npy',allow_pickle=False);assert features.shape==(248,3072) and features.dtype==np.float32
        head=load_file(str(folder/'head.safetensors'));assert head['weight'].shape==(4,3072) and head['bias'].shape==(4,)
        logits=features@head['weight'].T+head['bias'];predictions={}
        outputs=lines(folder/'external_dev.jsonl')+lines(folder/'historical_dev.jsonl')
        assert [r['example_id'] for r in outputs]==[r['example_id'] for r in records[1792:]]
        for x,feature,vector in zip(outputs,features,logits):
            assert hashlib.sha256(feature.tobytes()).hexdigest()==x['feature_sha256']
            np.testing.assert_allclose(vector,x['logits'],rtol=2e-4,atol=1e-3)
            pred=c.CLASSES[int(vector.argmax())];assert pred==x['predicted'];predictions[x['example_id']]=pred
        m=c.evaluate(records,predictions,challenges);assert m==saved['metrics']
        assert saved['base_state_sha256']==init['base_state_sha256']
        assert saved['optimizer_unchanged_by_eval'] and saved['parameters_unchanged_by_eval'] and saved['rng_restored'] and not saved['gradients_during_eval']
        checkpoints.append(dict(identity,complete=True,metrics=m))
    final=c.read(E/'frozen_final.json');assert final['base_state_sha256']==init['base_state_sha256'] and final['base_unchanged'] and not final['historical_adapter_loaded']
    selection=c.select(checkpoints,896);assert selection==c.read(E/'selection.json')
    assert selection['verdict']==status['verdict']
    assert 'torch' not in sys.modules
    result=dict(selection,checkpoints=checkpoints,cloud=c.read(B/'TERMINATION_VERIFIED.json'),tested_commit=manifest['source_commit'],trainable=inventory['counts'],
        training=dict(examples=3584,unique_examples=1792,passes=2,updates=896,first_ce=history[0]['ce'],final_update_ce=history[-1]['ce'],**c.read(E/'performance.json')),
        verification=dict(base_unchanged=True,historical_adapter_unloaded_and_unchanged=True,train_only_gradients=True,no_normalization=True,holdout_unconsumed=True,preservation=True,zero_billable_resources=True))
    write_json(B/'RECOMPUTED_RESULTS.json',result)
    if result['selected']:write_json(B/'SELECTED_CLASSIFIER.json',dict(result['selected'],integration_authorized=False,immutable=True))
    print(json.dumps(selection));return result


if __name__=='__main__':analyze()
