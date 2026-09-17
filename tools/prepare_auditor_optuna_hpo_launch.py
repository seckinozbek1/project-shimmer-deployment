"""Seal the explicitly authorized ea2b723 payload; no provider mutation."""
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path
import auditor_optuna_hpo as h
from auditor_classifier_lora_cloud import git
from cloud_run_common import credential_locations,write_json
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'tuning/auditor_optuna_hpo'
B=ROOT/'docs/fix/auditor_optuna_hpo_run'
APPROVED='ea2b72373a384e29a6344c762b8b7d12ef450741'


def prepare():
    h.require(git('rev-parse','HEAD').decode().strip()==APPROVED,'approved HEAD')
    h.require(not (B/'LAUNCH_INTENT.json').exists(),'authorization consumed')
    seal=json.loads((D/'seal.json').read_bytes())
    local=json.loads((D/'LOCAL_VALIDATION.json').read_bytes())
    h.require(local['verdict']=='AUDITOR_OPTUNA_HPO_CLEAN_READY' and local['tests']==local['passed']==59,'clean local validation')
    h.require(local['seal_sha256']==h.sha(D/'seal.json'),'local validation seal')
    names=list(seal['files'])+['tuning/auditor_optuna_hpo/seal.json','tools/auditor_optuna_hpo_launch_support.py']
    artifacts=json.loads((D/'artifacts.json').read_bytes())
    names += [r['path'] for r in artifacts.values()]
    h.require(len(artifacts)==6 and not any('finite_partial' in n for n in names),'clean artifacts only')
    blobs={}
    for name in names:
        data=(ROOT/name).read_bytes()
        if name in seal['files']:h.require(h.sha(ROOT/name)==seal['files'][name],'approved source '+name)
        if not name.endswith(('.npy','.safetensors')):h.require(not credential_locations(data,name),'Possible credential in payload '+name)
        blobs[name]=data
    for r in artifacts.values():h.require(h.sha(ROOT/r['path'])==r['sha256'],'artifact identity')
    records=json.loads(blobs['tuning/auditor_optuna_hpo/records_train_only.json'])
    h.require(len(records)==1792 and all(r['split']=='train' for r in records),'1792 TRAIN-only records')
    live=json.loads((B/'live_preflight.json').read_bytes());h.require(live['instances']==[],'initial inventory empty')
    choice=next(x for x in live['a10'] if x['metadata']['type']=='gpu_1x_a10' and x['architecture']=='x86_64' and 'us-east-1' in x['regions'])
    rate=choice['metadata']['hourly_rate'];h.require(rate==1.29,'verified hourly rate')
    images=json.loads((B/'images.json').read_bytes())
    image=next(x for x in images if x['region']=='us-east-1' and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    manifest=dict(source_commit=APPROVED,approved_seal_sha256=h.sha(D/'seal.json'),files={n:__import__('hashlib').sha256(b).hexdigest() for n,b in blobs.items()},
        rows=1792,inner_train=1432,inner_val=360,external_dev=0,historical_dev=0,challenges=0,holdout=0,protected=0,one_sequential_study=True,maximum_trials=15,maximum_updates=80)
    raw=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode();blobs['execution_manifest.json']=raw;(B/'execution_manifest.json').write_bytes(raw)
    permit=dict(operator_authorized=True,action='auditor-optuna-train-only-hpo',seal_sha256=h.sha(D/'seal.json'),source_commit=APPROVED,instances=1,gpus=1,n_jobs=1,
        max_trials=15,max_updates=80,soft_budget_usd=7.,hard_budget_usd=9.,full_training_authorized=False,provider='https://cloud.lambda.ai',region='us-east-1',instance_type='gpu_1x_a10',
        launch_epoch=0.,hourly_rate=rate,workload_deadline_epoch=0.,authorization='Explicit operator approval of clean HPO at ea2b723; no second study/instance, no forbidden DEV or final run')
    write_json(B/'training_authorization.json',permit)
    with zipfile.ZipFile(B/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for n,b in blobs.items():z.writestr(n,b)
    check=ROOT/'.tmp/auditor_hpo_execution_bundle';h.require(not check.exists(),'fresh packaging check directory');check.mkdir(parents=True)
    with zipfile.ZipFile(B/'runtime_bundle.zip') as z:z.extractall(check)
    test=subprocess.run([sys.executable,'-B','tools/auditor_optuna_hpo_remote.py','scope'],cwd=check,capture_output=True)
    h.require(not credential_locations(test.stdout+test.stderr,'packaged scope'),'Possible credential in scope log')
    (B/'bundle_check.log').write_bytes(test.stdout+test.stderr);h.require(test.returncode==0,'packaged scope')
    write_json(B/'bundle_check_results.json',dict(passed=True,files=len(blobs),train_only=True,approved_source_unchanged=True))
    write_json(B/'LOCAL_GATES.json',dict(passed=True,tests=59,clean_initializer=True,scope_passed=True,source_commit=APPROVED))
    hard=9/rate*3600;soft=7/rate*3600
    cloud=dict(source_commit=APPROVED,bundle_sha256=h.sha(B/'runtime_bundle.zip'),instance=choice['metadata'],region='us-east-1',image=image,hourly_rate=rate,
        soft_usd=7.,hard_usd=9.,soft_seconds=soft,hard_seconds=hard,workload_deadline_seconds=min(soft,hard-600),watchdog_deadline_seconds=hard-120,termination_deadline_seconds=hard,
        reserve_seconds=600,projected_seconds_with_reserve=19182,projected_cost=19182*rate/3600,name='shimmer-auditor-clean-optuna-hpo')
    h.require(cloud['projected_seconds_with_reserve']<hard,'cost fits')
    write_json(B/'manifest.json',cloud)
    write_json(B/'preservation_before.json',dict(approved_seal_sha256=h.sha(D/'seal.json'),artifacts=artifacts,
        prior_evidence_manifest_sha256=h.sha(ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/EVIDENCE_MANIFEST.json')))
    print(json.dumps(dict(bundle_sha256=cloud['bundle_sha256'],files=len(blobs),rate=rate,region='us-east-1',soft_workload_stop_seconds=cloud['workload_deadline_seconds'],hard_seconds=hard,scope_passed=True),indent=2))


if __name__=='__main__':prepare()
