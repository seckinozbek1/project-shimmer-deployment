"""Post-termination independent evidence recomputation; no Torch or model."""
import hashlib
import json
import math
from pathlib import Path
import sys
import tarfile
import auditor_v2_execution as c
from cloud_run_common import credential_locations,write_json

ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'docs/fix/auditor_v2_diagnostic_run'
D=ROOT/'tuning/auditor_v2_diagnostic'


def lines(path):
    return [json.loads(x) for x in Path(path).read_bytes().splitlines()]


def analyze():
    assert c.read(B/'TERMINATION_VERIFIED.json')
    assert c.read(B/'instances_after.json')==[]
    assert c.read(B/'final_inventory_confirmation.json')['zero_billable_resources']
    cleanup=c.read(B/'cleanup.json')
    assert cleanup['temporary_ssh_removed'] and cleanup['local_key_material_removed']
    assert not (B/'ssh_identity').exists() and not (B/'ssh_identity.pub').exists()
    assert c.sha(B/'evidence.tar.gz')==c.read(B/'collection_integrity.json')['sha256']
    target=B/'downloaded';target.mkdir(exist_ok=True)
    with tarfile.open(B/'evidence.tar.gz') as archive:
        for member in archive.getmembers():
            assert (target/member.name).resolve().is_relative_to(target.resolve())
            assert member.isfile() or member.isdir()
        archive.extractall(target,filter='data')
    e=target/'evidence'
    status=c.read(e/'status.json')
    assert status['complete']
    assert c.sha(target/'execution_manifest.json')==c.sha(B/'execution_manifest.json')
    manifest=c.read(B/'execution_manifest.json')
    for name,digest in manifest['files'].items():
        if (target/name).is_file():assert c.sha(target/name)==digest,name
    assert c.read(target/'training_authorization.json')==c.read(B/'training_authorization.json')
    records=c.read(D/'records.json');spec=c.read(D/'experiment.json');challenges=c.read(D/'challenges.json');baseline=c.read(D/'baseline.json')
    c.validate(records,spec,challenges,baseline)
    import numpy as np
    from safetensors.numpy import load_file
    features=np.load(e/'features.npy',allow_pickle=False)
    assert features.shape==(2040,3072) and features.dtype==np.float32
    receipts=lines(e/'features.jsonl')
    assert [r['example_id'] for r in receipts]==[r['example_id'] for r in records]
    for value,receipt,row in zip(features,receipts,records):
        assert hashlib.sha256(value.tobytes()).hexdigest()==receipt['sha256']
        assert receipt['prompt_sha256']==row['prompt_sha256'] and receipt['input_tokens']==len(row['input_ids'])
    mean,std,standard=c.d.standardized(np,features)
    np.testing.assert_array_equal(mean,np.load(e/'mean.npy',allow_pickle=False))
    np.testing.assert_array_equal(std,np.load(e/'std.npy',allow_pickle=False))
    normalization=c.read(e/'normalization.json')
    assert normalization['train_ids']==[r['example_id'] for r in records[:1792]]
    assert not normalization['dev_fit'] and normalization['ddof']==0 and normalization['clamp']==1e-6
    assert normalization['mean_sha256']==c.sha(e/'mean.npy') and normalization['std_sha256']==c.sha(e/'std.npy')
    initial=load_file(str(e/'head-0.safetensors'));head=load_file(str(e/'head-200.safetensors'))
    for h in [initial,head]:
        assert set(h)=={'weight','bias'} and h['weight'].shape==(4,3072) and h['bias'].shape==(4,)
        assert all(v.dtype==np.float32 for v in h.values())
    assert all((v==0).all() for v in initial.values())
    history=lines(e/'head_training.jsonl');assert [r['step'] for r in history]==list(range(1,201))
    assert math.isclose(history[0]['ce'],math.log(4),rel_tol=1e-6) and history[0]['regularization']==0
    assert all(math.isfinite(r['loss']) and math.isclose(r['loss'],r['ce']+r['regularization']) for r in history)
    frozen=c.read(e/'frozen_final.json');assert frozen['unchanged']
    assert frozen['state_sha256']==c.read(e/'frozen_initial.json')['state_sha256']
    assert frozen['backbone_trainable']==frozen['lora_trainable']==0
    logits=standard@head['weight'].T+head['bias'];assert np.isfinite(logits).all()
    train=c.metrics([r['relation'] for r in records[:1792]],[c.CLASSES[i] for i in logits[:1792].argmax(axis=1)])
    head_result=c.read(e/'head_result.json');assert train==head_result['metrics']
    assert head_result['parameters']==12292 and head_result['updates']==200 and head_result['head_sha256']==c.sha(e/'head-200.safetensors')
    soft=logits[:1792].astype(np.float64);soft-=soft.max(axis=1,keepdims=True)
    ce=float(np.mean(np.log(np.exp(soft).sum(axis=1))-soft[np.arange(1792),[c.CLASSES.index(r['relation']) for r in records[:1792]]]))
    assert math.isclose(ce,head_result['final_ce'],abs_tol=1e-4)
    predictions={}
    for group,start,end in [('external_dev',1792,1992),('historical_dev',1992,2040)]:
        saved=lines(e/(group+'.jsonl'));assert [r['example_id'] for r in saved]==[r['example_id'] for r in records[start:end]]
        for row,vector in zip(saved,logits[start:end]):
            np.testing.assert_allclose(vector,row['logits'],rtol=1e-4,atol=2e-4)
            pred=c.CLASSES[int(vector.argmax())];assert pred==row['predicted'];predictions[row['example_id']]=pred
    result=c.evaluate(records,predictions,challenges,baseline)
    assert result==c.read(e/'results.json')
    # Verify all preflight sources remain bound; do not open the mixed V2 file.
    for name,digest in c.read(D/'bindings.json').items():
        if name!='external_dev_selected_content_sha256':assert c.sha(ROOT/name)==digest,name
    assert c.read(ROOT/'tuning/auditor_external_relation_v2/holdout_receipt.json')['consumed'] is False
    assert c.read(ROOT/'tuning/auditor_external_relation_v2/dry_run_evidence.json')['verdict']=='AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY'
    assert 'torch' not in sys.modules
    result.update(train=train,head=head_result,performance=c.read(e/'performance.json'),
                  cloud=c.read(B/'TERMINATION_VERIFIED.json'),tested_commit=manifest['source_commit'],
                  verification=dict(features=2040,updates=200,train_only_normalization=True,frozen_parameters_unchanged=True,
                                    holdout_unconsumed=True,zero_billable_resources=True,torch_imported=False))
    write_json(B/'RECOMPUTED_RESULTS.json',result)
    evidence={}
    for p in sorted(B.rglob('*')):
        if not p.is_file() or 'bundle_check' in p.parts or p.name in ('EVIDENCE_MANIFEST.json',):continue
        if p.suffix in ('.json','.jsonl','.py','.log','.md'):
            hits=credential_locations(p.read_bytes(),p.relative_to(ROOT).as_posix())
            assert not hits,hits
        evidence[p.relative_to(ROOT).as_posix()]=dict(sha256=c.sha(p),bytes=p.stat().st_size)
    write_json(B/'EVIDENCE_MANIFEST.json',evidence)
    print(json.dumps(dict(verdict=result['verdict'],conclusion=result['conclusion'],external=result['external']['macro_f1'],historical=result['historical']['macro_f1'])))
    return result


if __name__=='__main__':analyze()
