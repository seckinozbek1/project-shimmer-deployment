"""Verify saved diagnostic artifacts after teardown; no model/provider execution."""
import hashlib
import inspect
import json
import tarfile
from pathlib import Path

import numpy as np
import auditor_classifier_lora_core as c
import auditor_feature_diagnostics as d
from cloud_run_common import credential_locations, require, write_json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/auditor_feature_remote_run'


def analyze():
    cleanup=c.read(BASE/'independent_inventory_confirmation.json')
    require(cleanup['instances']==[] and cleanup['temporary_ssh_registration_absent'] and cleanup['local_key_material_absent'],'independent cleanup')
    require(not (BASE/'ssh_identity').exists() and not (BASE/'ssh_identity.pub').exists(),'SSH material absent')
    manifest=c.read(BASE/'execution_manifest.json')
    archive=BASE/'evidence.tar.gz';collection=c.read(BASE/'collection_integrity.json')
    require(c.sha(archive)==collection['sha256'],'archive integrity')
    termination=c.read(BASE/'termination_requested.json')
    require(collection['verified_epoch']<=termination['epoch'],'verified collection before termination request')
    target=BASE/'downloaded';target.mkdir(exist_ok=True)
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar.getmembers():
            require((target/member.name).resolve().is_relative_to(target.resolve()) and (member.isfile() or member.isdir()),'safe archive members')
        if 'filter' in inspect.signature(tar.extractall).parameters:
            tar.extractall(target,filter='data')
        else:
            # Older local Python: the checks above already reject links, devices,
            # and every path escaping the verified destination.
            tar.extractall(target)
    for p in target.rglob('*'):
        if p.is_file() and p.suffix in ('.json','.jsonl','.py','.log'):
            hits=credential_locations(p.read_bytes(),p.relative_to(ROOT).as_posix())
            if hits:
                raise RuntimeError('WARNING: Possible API key detected in '+str(hits)+'. Do not push. Rotate the key immediately.')
    require(c.sha(target/'execution_manifest.json')==c.sha(BASE/'execution_manifest.json'),'executed manifest')
    for name,digest in manifest['files'].items():require(c.sha(target/name)==digest,'executed payload: '+name)
    evidence=target/'evidence';data=target/'diagnostic_payload'
    rows=c.read(data/'rows.json');result=c.read(evidence/'result.json')
    prior=np.load(data/'historical33.npy',allow_pickle=False);local=np.load(data/'local30_33.npy',allow_pickle=False)
    seen={};verified=[]
    for item in result['forwards']:
        stage=item['stage'];sequence=item['sequence'];index=item['index'];row=rows[index]
        name=f'{stage}-{sequence:02d}-row{index+1}'
        path=evidence/(name+'.json');receipt=c.read(path)
        require(c.sha(path)==item['receipt_sha256'],'forward receipt hash')
        require(receipt['source_commit']==manifest['source_commit'],'forward source identity')
        require(receipt['index']==index and receipt['row_one_based']==index+1 and receipt['example_id']==row['example_id'],'row identity')
        require(receipt['token_sha256']==d.digest(row['input_ids']) and receipt['input_ids_sha256']==d.digest([row['input_ids']]) and receipt['attention_mask_sha256']==d.digest([[1]*len(row['input_ids'])]),'input/mask binding')
        model=receipt['model']
        require(not model['training'] and model['training_module_count']==0 and model['active_adapters']==['historical_reference'],'eval reference')
        require(all(not m['disabled'] and not m['merged'] and m['active_adapters']==['historical_reference'] for m in model['adapter_layers']),'adapter layer state')
        require(all(not m['training'] for m in model['dropout']),'dropout disabled')
        require(receipt['forward_autocast']['inference_mode'] and not receipt['forward_autocast']['grad_enabled'] and receipt['forward_autocast']['enabled'] and receipt['forward_autocast']['dtype']=='torch.bfloat16','forward context')
        libraries=c.read(evidence/('libraries-'+receipt['library_identity']+'.json'))
        require(d.digest(libraries)==receipt['library_identity'] and libraries['hardware_sha256']==c.sha(evidence/'hardware.json'),'library/hardware identity')
        for filename,digest in receipt['extraction_path']['files'].items():require(c.sha(target/'tools'/filename)==digest,'extraction source hash')
        if item['valid']:
            vector=np.load(evidence/(name+'.npy'),allow_pickle=False)
            require(vector.shape==(3072,) and vector.dtype==np.float32 and np.isfinite(vector).all(),'successful vector')
            require(hashlib.sha256(vector.tobytes()).hexdigest()==item['feature_sha256'],'vector bytes')
            require(receipt['raw_hidden']['shape']==[1,len(row['input_ids']),3072] and receipt['vector']['shape']==[3072],'raw/vector shapes')
            require(receipt['vector']['finite_count']==receipt['vector']['total_count']==3072,'finite receipt')
            require(float(np.max(np.abs(vector-prior[index])))==item['historical_max_abs'] and bool(np.array_equal(vector,prior[index]))==item['historical_bitwise'],'historical comparison')
            if 29<=index<=32:
                require(float(np.max(np.abs(vector-local[index-29])))==item['local_max_abs'] and bool(np.array_equal(vector,local[index-29]))==item['local_bitwise'],'local comparison')
            if index in seen:
                require(float(np.max(np.abs(vector-seen[index])))==item['previous_cloud_max_abs'] and bool(np.array_equal(vector,seen[index]))==item['previous_cloud_bitwise'],'cloud repetition/order comparison')
            seen[index]=vector
        verified.append(dict(item,raw_shape=receipt['raw_hidden']['shape'] if receipt['raw_hidden'] else None,
            raw_dtype=receipt['raw_hidden']['dtype'] if receipt['raw_hidden'] else None,
            raw_all_finite=receipt['raw_hidden']['finite_count']==receipt['raw_hidden']['total_count'] if receipt['raw_hidden'] else None,
            pooled_dtype=receipt['extracted_hidden']['dtype'] if receipt['extracted_hidden'] else None))
    if result['verdict']=='REMOTE_BLOCKER_NOT_REPRODUCED':
        expected=[('A',31),('A',31)]+[('B',i) for i in [29,30,31,32]]+[('C',i) for i in range(32)]
        require([(r['stage'],r['index']) for r in verified]==expected and all(r['valid'] for r in verified),'complete bounded stages')
        require((evidence/'initialization-6.json').exists(),'fresh Stage C base')
    require(result['optimizer_updates']==result['dev_rows']==result['challenge_rows']==result['protected_rows']==result['producer_rows']==0,'zero forbidden work')
    require(result['data_access']['denied_before_open']==0 and all(v==0 for v in result['data_access']['successful_access_counts'].values()),'data access')
    if result['verdict']=='REMOTE_BLOCKER_NOT_REPRODUCED':
        old=ROOT/'docs/fix/auditor_final_run/downloaded/evidence'
        old_events=[json.loads(line) for line in (old/'events.jsonl').read_bytes().splitlines()]
        old_events=[item for item in old_events if item['event']=='feature']
        require(len(old_events)==31,'original validated prefix only')
        old_vectors=np.load(old/'train_features.npy',mmap_mode='r',allow_pickle=False)
        cloud_prefix=[]
        for i,item in enumerate(old_events):
            require(item['example_id']==rows[i]['example_id'] and item['token_sha256']==d.digest(rows[i]['input_ids']),'failed prefix row binding')
            require(np.isfinite(old_vectors[i]).all() and hashlib.sha256(old_vectors[i].tobytes()).hexdigest()==item['feature_sha256'],'failed prefix validated bytes')
            cloud_prefix.append(np.load(evidence/f'C-{i:02d}-row{i+1}.npy',allow_pickle=False))
        write_json(BASE/'FAILED_PREFIX_COMPARISON.json',dict(valid_failed_run_prefix_rows=31,
            failed_run_prefix_max_abs_difference=float(np.max(np.abs(np.stack(cloud_prefix)-old_vectors[:31]))),
            cloud_prefix_matches_historical_bitwise=all(x['historical_bitwise'] for x in verified if x['stage']=='C'),
            original_failing_row32_tensor_available=False))
    start=c.read(BASE/'launch.json')['epoch'];end=cleanup['epoch']
    summary=dict(verdict=result['verdict'],source_commit=manifest['source_commit'],forwards=verified,
        total_forwards=len(verified),base_unchanged=result.get('base_unchanged'),hardware=c.read(evidence/'hardware.json'),
        first_invalid_boundary=result.get('first_invalid_boundary'),archive_sha256=collection['sha256'],archive_bytes=collection['bytes'],
        downloaded_and_verified_before_termination=True,zero_billable_resources=True,temporary_ssh_removed=True,
        duration_upper_bound_seconds=end-start,estimated_cost_upper_bound_usd=(end-start)*1.29/3600,
        launch=c.read(BASE/'launch.json'),teardown=cleanup,optimizer_updates=0,
        limitations='Same pinned A10 runtime does not reconstruct the original missing tensor or original driver/allocator/transient state. No fix inferred.')
    write_json(BASE/'RECOMPUTED_RESULTS.json',summary)
    retained=[p for p in BASE.rglob('*') if p.is_file() and p.suffix in ('.json','.jsonl','.log') and p.name!='EVIDENCE_MANIFEST.json']
    write_json(BASE/'EVIDENCE_MANIFEST.json',dict(source_commit=manifest['source_commit'],archive_sha256=c.sha(archive),
        retained_text=[dict(path=p.relative_to(ROOT).as_posix(),sha256=c.sha(p),bytes=p.stat().st_size) for p in sorted(retained)]))
    print(json.dumps({k:v for k,v in summary.items() if k not in ['hardware','forwards']},indent=2))


if __name__=='__main__':analyze()
