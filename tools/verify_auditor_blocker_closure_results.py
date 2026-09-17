"""Read-only receipt checks after the single approved diagnostic; no inference."""
import hashlib
import json
from pathlib import Path
import numpy as np
from auditor_feature_diagnostics import digest, HISTORICAL_RECEIPTS_SHA256

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/auditor_blocker_closure_run'

def read(path): return json.loads(path.read_text())
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def verify():
    m=read(BASE/'execution_manifest.json'); dest=BASE/'downloaded'
    assert sha(dest/'execution_manifest.json')==sha(BASE/'execution_manifest.json')
    for name,want in m['files'].items(): assert sha(dest/name)==want,name
    rows=read(dest/'tuning/auditor_final/records_train_only.json')
    historical=ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/downloaded/evidence'
    receipt_path=historical/'current_train_features.jsonl'
    assert sha(receipt_path)==HISTORICAL_RECEIPTS_SHA256
    old_manifest=read(historical.parents[1]/'EVIDENCE_MANIFEST.json')
    assert any(x['path']==receipt_path.relative_to(ROOT).as_posix() and x['sha256']==HISTORICAL_RECEIPTS_SHA256 for x in old_manifest['retained_text'])
    cache=historical/'current_train_features.npy'
    assert sha(cache)=='06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287'
    prior=np.load(cache,mmap_mode='r',allow_pickle=False)
    receipts=[json.loads(line) for line in receipt_path.read_bytes().splitlines()]
    for i,(row,receipt) in enumerate(zip(rows,receipts)):
        assert receipt['index']==i and receipt['example_id']==row['example_id']
        assert receipt['token_sha256']==digest(row['input_ids'])
        assert receipt['feature_sha256']==hashlib.sha256(prior[i].tobytes()).hexdigest()
    states=[]
    for arm in ('O','D'):
        folder=dest/'evidence'/arm; result=read(folder/'result.json');states.append(result)
        assert result['forwards']==result['matched_rows']==32 and result['optimizer_updates']==0
        access=result['data_access']
        assert access['denied_before_open']==0 and not any(access['successful_access_counts'].values())
        assert all(access[key]==0 for key in ('external_dev_rows','historical_dev_rows','shorter_rows','longer_rows'))
        init=read(folder/'initialization.json')
        assert init['base_state_sha256']=='d07dae6b59e73394974e2699a2f66dad8c7d57be1c800c6774eccd114f38db18'
        assert init['canonical_adapter_sha256']=='733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6'
        values=np.load(folder/'train_features.npy',mmap_mode='r',allow_pickle=False)
        events=[json.loads(line) for line in (folder/'events.jsonl').read_bytes().splitlines()]
        assert len(events)==32
        for i,event in enumerate(events):
            assert event['token_sha256']==digest(rows[i]['input_ids'])
            assert event['feature_sha256']==receipts[i]['feature_sha256']
            assert values[i].tobytes()==prior[i].tobytes()
            if arm=='D':
                r=read(folder/f'row-{i+1:02d}.json'); n=len(rows[i]['input_ids'])
                assert r['reason'] is None and r['index']==i and r['example_id']==rows[i]['example_id']
                assert r['token_sha256']==digest(rows[i]['input_ids'])
                assert r['input_ids_sha256']==digest([rows[i]['input_ids']])
                assert r['attention_mask_sha256']==digest([[1]*n])
                assert r['raw_hidden']['shape']==[1,n,3072] and r['vector']['shape']==[3072]
                for key in ('raw_hidden','extracted_hidden','vector'):
                    assert r[key]['finite_count']==r[key]['total_count']
                state=r['model']; assert not state['training'] and state['training_module_count']==0
                assert state['active_adapters']==['historical_reference']
                assert all(not x['disabled'] and not x['merged'] and x['active_adapters']==['historical_reference'] for x in state['adapter_layers'])
                assert all(not x['training'] for x in state['dropout'])
                assert all(x['compute_dtype']=='torch.bfloat16' for x in state['quantized_compute'])
                assert state['attention_implementation']=='eager' and state['deterministic_algorithms']
                assert not state['matmul_allow_tf32'] and not state['cudnn_allow_tf32']
                assert r['forward_autocast']==dict(device_type='cuda',enabled=True,dtype='torch.bfloat16',grad_enabled=False,inference_mode=True)
    assert states[0]['finished_epoch'] < states[1]['process']['observed_epoch']
    assert states[0]['process']['pid']!=states[1]['process']['pid']
    cleanup=read(BASE/'independent_inventory_confirmation.json')
    assert cleanup['instances']==[] and cleanup['local_key_material_absent'] and cleanup['temporary_ssh_registration_absent']
    assert read(BASE/'collection_integrity.json')['verified_epoch'] < read(BASE/'termination_requested.json')['epoch']
    frozen=read(BASE/'preservation.json')
    preserved={name:sha(ROOT/name)==v['sha256'] for name,v in frozen.items() if not name.startswith('tools/')}
    assert all(preserved.values())
    result=dict(passed=True,manifest_files=len(m['files']),train_reference_rows=1792,live_forward_receipts=64,
        exact_live_vectors=64,diagnostic_model_input_receipts_verified=32,sequential_fresh_processes=True,
        forbidden_access=False,collection_before_termination=True,independent_empty_inventory=True,
        preserved_frozen_files=preserved,root_cause='ROOT_CAUSE_UNRESOLVED')
    (BASE/'POST_RUN_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':verify()
