"""Build a TRAIN-only diagnostic bundle. Never creates cloud resources."""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
import auditor_classifier_lora_core as c
import auditor_classifier_lora_fork as fork
from cloud_run_common import require, credential_locations, write_json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/auditor_feature_remote_run'
PAYLOAD=ROOT/'.tmp/auditor_feature_payload'
TOOLS=['auditor_feature_remote.py','auditor_feature_diagnostics.py','auditor_final_remote.py',
       'auditor_final_core.py','auditor_classifier_lora_core.py','auditor_classifier_lora_current_core.py',
       'auditor_classifier_lora_fork.py','auditor_classifier_lora_stable.py']


def git(*args):
    staged=subprocess.run(['git','diff','--cached','--no-ext-diff'],cwd=ROOT,capture_output=True,check=True).stdout
    require(not credential_locations(staged,'staged diff'),'Possible credential detected; stop')
    return subprocess.run(['git',*args],cwd=ROOT,capture_output=True,check=True).stdout.decode().strip()


def prepare():
    import numpy as np
    require(not (BASE/'LAUNCH_INTENT.json').exists(),'authorization consumed')
    require(all(x.startswith('?? ') for x in git('status','--porcelain').splitlines()),'commit reviewed tracked source before bundling')
    PAYLOAD.mkdir(exist_ok=False);data=PAYLOAD/'diagnostic_payload';data.mkdir()
    rows=c.read(ROOT/'tuning/auditor_final/records_train_only.json')
    original=c.read(ROOT/'docs/fix/auditor_final_run/execution_manifest.json')
    require(c.sha(ROOT/'tuning/auditor_final/records_train_only.json')==original['files']['tuning/auditor_final/records_train_only.json'],'failed-run token source')
    require(len(rows)==1792 and all(r['split']=='train' for r in rows),'TRAIN source')
    write_json(data/'rows.json',rows[:33])
    source=ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/downloaded/evidence/current_train_features.npy'
    require(c.sha(source)=='06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287','historical cache hash')
    prior_manifest=c.read(ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/EVIDENCE_MANIFEST.json')
    prior_receipt=source.with_suffix('.jsonl')
    bound=next(x for x in prior_manifest['retained_text'] if x['path']==prior_receipt.relative_to(ROOT).as_posix())
    require(c.sha(prior_receipt)==bound['sha256'],'historical receipt hash')
    receipts=[json.loads(x) for x in source.with_suffix('.jsonl').read_bytes().splitlines()]
    require(all(receipts[i]['example_id']==r['example_id'] and receipts[i]['token_sha256']==fork.token_hash(r['input_ids']) for i,r in enumerate(rows[:33])),'historical row/token binding')
    historical=np.load(source,allow_pickle=False)[:33].copy();np.save(data/'historical33.npy',historical,allow_pickle=False)
    local_root=ROOT/'docs/fix/auditor_feature_blocker/gpu_rows30_33'
    receipt=c.read(local_root/'probe.json');local=[]
    for index,item in zip(range(29,33),receipt['forward_rows']):
        value=np.load(local_root/f'row-{index+1}.npy',allow_pickle=False)
        require(item['token_sha256']==fork.token_hash(rows[index]['input_ids']) and __import__('hashlib').sha256(value.tobytes()).hexdigest()==item['feature_sha256'],'local vector binding')
        local.append(value)
    np.save(data/'local30_33.npy',np.stack(local),allow_pickle=False)
    write_json(data/'comparison_provenance.json',dict(historical_full_cache_sha256=c.sha(source),local_receipt_sha256=c.sha(local_root/'probe.json'),source_train_sha256=c.sha(ROOT/'tuning/auditor_final/records_train_only.json'),local_receipts=receipt['forward_rows']))
    shutil.copyfile(ROOT/'tuning/auditor_final/runtime_contract.json',data/'runtime_contract.json')
    adapter=data/'canonical_adapter';adapter.mkdir()
    for name,digest in [('adapter_model.safetensors',fork.SOURCE_SHA),('adapter_config.json',fork.CONFIG_SHA)]:
        source=ROOT/'tuning/auditor_final/canonical_adapter'/name
        require(c.sha(source)==digest,'adapter identity');shutil.copyfile(source,adapter/name)
    (PAYLOAD/'tools').mkdir()
    for name in TOOLS:shutil.copyfile(ROOT/'tools'/name,PAYLOAD/'tools'/name)
    files={p.relative_to(PAYLOAD).as_posix():c.sha(p) for p in PAYLOAD.rglob('*') if p.is_file()}
    for name in files:
        if Path(name).suffix not in ('.npy','.safetensors'):
            require(not credential_locations((PAYLOAD/name).read_bytes(),name),'Possible credential detected; stop')
    source_commit=git('rev-parse','HEAD')
    manifest=dict(source_commit=source_commit,parent_results_commit='459d694',files=files,maximum_prefix_row=32,train_payload_rows=33,optimizer_updates=0,stages=['A:32 twice','B:30-33 if A passes','C:1-32 from fresh load if B passes'])
    write_json(PAYLOAD/'execution_manifest.json',manifest);write_json(BASE/'execution_manifest.json',manifest)
    with zipfile.ZipFile(BASE/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in [*files,'execution_manifest.json']:archive.write(PAYLOAD/name,name)
    check=subprocess.run([sys.executable,'-B','tools/auditor_feature_remote.py','scope'],cwd=PAYLOAD,capture_output=True)
    require(not credential_locations(check.stdout+check.stderr,'scope'),'Possible credential detected; stop')
    (BASE/'bundle_check.log').write_bytes(check.stdout+check.stderr);require(check.returncode==0,'bundle scope')
    write_json(BASE/'bundle_check_results.json',dict(passed=True,rows=33,maximum_prefix_row=32,no_evaluation_payload=True))
    live=c.read(BASE/'live_preflight.json');require(live['instances']==[],'initial inventory')
    choice=next(x for x in live['a10'] if x['metadata']['type']=='gpu_1x_a10' and 'us-east-1' in x['regions'])
    require(choice['metadata']['hourly_rate']==1.29,'authorized price')
    old_image=c.read(ROOT/'docs/fix/auditor_final_run/manifest.json')['image']
    image=next(x for x in c.read(BASE/'images.json') if x==old_image)
    rate=1.29;hard=2/rate*3600
    write_json(BASE/'manifest.json',dict(source_commit=source_commit,bundle_sha256=c.sha(BASE/'runtime_bundle.zip'),instance=choice['metadata'],image=image,region='us-east-1',hourly_rate=rate,soft_usd=1.,hard_usd=2.,soft_seconds=1/rate*3600,hard_seconds=hard,workload_deadline_seconds=hard-900,watchdog_deadline_seconds=hard-180,termination_deadline_seconds=hard,reserve_seconds=900,name='shimmer-auditor-feature-diagnostic'))
    write_json(BASE/'diagnostic_authorization.json',dict(operator_authorized=True,action='auditor-feature-diagnostic-only',source_commit=source_commit,execution_manifest_sha256=c.sha(BASE/'execution_manifest.json'),instances=1,region='us-east-1',hourly_rate=rate,soft_usd=1,hard_usd=2,optimizer_updates=0,launch_epoch=0,workload_deadline_epoch=0,request_attachment='88e1927a-4fc9-4c34-97c8-e4baea828218'))
    print('Diagnostic bundle verified; no resources launched.')


if __name__=='__main__':prepare()
