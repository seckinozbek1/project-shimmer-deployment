"""Local final-workflow sealing/packaging; never opens DEV or challenge payloads."""
import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path
import auditor_final_core as f
import auditor_classifier_lora_core as c
from auditor_classifier_lora_cloud import git
from cloud_run_common import credential_locations

ROOT=Path(__file__).resolve().parents[1];D=ROOT/'tuning/auditor_final';B=ROOT/'docs/fix/auditor_final_run'
TOOLS=['auditor_final_core.py','auditor_final_backend.py','auditor_final_remote.py','auditor_feature_diagnostics.py','auditor_final_launch_support.py','auditor_classifier_lora_core.py','auditor_classifier_lora_current_core.py','auditor_classifier_lora_fork.py','auditor_classifier_lora_stable.py','auditor_optuna_hpo.py','auditor_optuna_hpo_backend.py','test_auditor_final.py']


def write(path,value):path.write_bytes((json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode())


def seal():
    D.mkdir(exist_ok=True);B.mkdir(exist_ok=True)
    f.require(not (B/'LAUNCH_INTENT.json').exists(),'final authorization consumed')
    selected=c.read(ROOT/'docs/fix/auditor_optuna_hpo_run/SELECTED_HYPERPARAMETERS.json');f.require(selected==f.PARAMS,'selected four values')
    (D/'.gitattributes').write_bytes(b'* -text\n')
    train=ROOT/'tuning/auditor_optuna_hpo/records_train_only.json';f.train_rows(c.read(train))
    (D/'records_train_only.json').write_bytes(train.read_bytes())
    for name in ['runtime_contract.json','controls.json']:(D/name).write_bytes((ROOT/'tuning/auditor_optuna_hpo'/name).read_bytes())
    write(D/'experiment.json',f.config());write(D/'schedule.json',c.schedule([r['example_id'] for r in c.read(train)]))
    write(D/'evaluation_bindings.json',dict(files=f.EVAL_HASHES,read_policy='Do not open, hash or upload original records/challenges until verified TRAINING_COMPLETE896. Expected hashes copied from prior committed manifest.',external_dev=200,historical_dev=48,shorter=75,longer=75))
    prior=c.read(ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/execution_manifest.json')['files']
    for name,digest in f.EVAL_HASHES.items():f.require(prior['tuning/auditor_classifier_lora/'+name]==digest,'historical evaluation hash receipt')
    adapter=D/'canonical_adapter';adapter.mkdir(exist_ok=True)
    import auditor_classifier_lora_fork as fork
    for name,digest in [('adapter_model.safetensors',fork.SOURCE_SHA),('adapter_config.json',fork.CONFIG_SHA)]:
        source=ROOT/'docs/fix/auditor_canonical_tuning_run/downloaded/evidence/checkpoint-120'/name
        f.require(c.sha(source)==digest,'canonical adapter identity');(adapter/name).write_bytes(source.read_bytes())
    files=['tools/'+n for n in TOOLS]+[p.relative_to(ROOT).as_posix() for p in D.rglob('*') if p.is_file() and p.name not in ['seal.json','LOCAL_VALIDATION.json']]
    for n in files:
        if not n.endswith('.safetensors'):f.require(not credential_locations((ROOT/n).read_bytes(),n),'Possible credential; stop')
    write(D/'seal.json',dict(files={n:c.sha(ROOT/n) for n in sorted(files)},scope='one final Auditor train then evaluate; no HPO'))
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s','tools','-p','test_auditor_final.py','-v'],cwd=ROOT,capture_output=True)
    (B/'local_tests.log').write_bytes(test.stdout+test.stderr);f.require(test.returncode==0,'local final contract tests')
    scope=subprocess.run([sys.executable,'-B','tools/auditor_final_remote.py','scope'],cwd=ROOT,capture_output=True)
    (B/'local_scope.log').write_bytes(scope.stdout+scope.stderr);f.require(scope.returncode==0,'local final scope')
    write(D/'LOCAL_VALIDATION.json',dict(passed=True,tests=10,seal_sha256=c.sha(D/'seal.json'),evaluation_access=False,model_loaded=False))
    print('Final source sealed; 10 local tests and TRAIN-only scope passed; no evaluation access.')


def bundle():
    f.require(not (B/'LAUNCH_INTENT.json').exists(),'one attempt consumed')
    validation=c.read(D/'LOCAL_VALIDATION.json');f.require(validation['passed'] and validation['seal_sha256']==c.sha(D/'seal.json'),'validated source')
    commit=git('rev-parse','HEAD').decode().strip();status=git('status','--porcelain').decode()
    f.require(all(line.startswith('?? ') for line in status.splitlines()),'tracked working tree must be clean')
    write(B/'source_state.json',dict(source_commit=commit,working_tree=status,unrelated_untracked_preserved=True))
    files=dict(c.read(D/'seal.json')['files']);files['tuning/auditor_final/seal.json']=c.sha(D/'seal.json')
    for name,digest in files.items():f.require(c.sha(ROOT/name)==digest,'payload source unchanged')
    manifest=dict(source_commit=commit,seal_sha256=c.sha(D/'seal.json'),files=files,train_rows=1792,evaluation_payload_initially_absent=True,evaluation_bindings=f.EVAL_HASHES,updates=896,params=f.PARAMS)
    write(B/'execution_manifest.json',manifest)
    with zipfile.ZipFile(B/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for name in files:archive.write(ROOT/name,name)
        archive.write(B/'execution_manifest.json','execution_manifest.json')
    target=ROOT/'.tmp/auditor_final_bundle';f.require(not target.exists(),'fresh bundle check directory');target.mkdir(parents=True)
    with zipfile.ZipFile(B/'runtime_bundle.zip') as archive:archive.extractall(target)
    tested=subprocess.run([sys.executable,'-B','tools/auditor_final_remote.py','scope'],cwd=target,capture_output=True)
    (B/'bundle_check.log').write_bytes(tested.stdout+tested.stderr);f.require(tested.returncode==0,'packaged scope')
    write(B/'bundle_check_results.json',dict(passed=True,evaluation_payload_absent=True))
    write(B/'LOCAL_GATES.json',validation)
    live=c.read(B/'live_preflight.json');f.require(live['instances']==[],'empty initial inventory')
    choice=next(x for x in live['a10'] if x['metadata']['type']=='gpu_1x_a10' and 'us-east-1' in x['regions']);rate=choice['metadata']['hourly_rate'];f.require(rate==1.29,'verified price')
    image=next(x for x in c.read(B/'images.json') if x['region']=='us-east-1' and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    write(B/'training_authorization.json',dict(operator_authorized=True,action='auditor-final-training-evaluation',source_commit=commit,execution_manifest_sha256=c.sha(B/'execution_manifest.json'),seal_sha256=c.sha(D/'seal.json'),instances=1,gpus=1,updates=896,params=f.PARAMS,evaluation_after_updates=896,soft_budget_usd=5.,hard_budget_usd=7.,launch_epoch=0,hourly_rate=rate,workload_deadline_epoch=0,provider='https://cloud.lambda.ai',region='us-east-1',instance_type='gpu_1x_a10',authorization='Explicit final896 plus delayed448/896 evaluation; one instance; no retry/HPO/protected/Producer/full Shimmer/push'))
    hard=7/rate*3600;soft=5/rate*3600
    projection=dict(typical_seconds=896*6+1792*.65+900+496*.65+60+900,conservative_seconds=896*10+1792*.8+1200+496*.8+120+900)
    projection.update({k.replace('seconds','usd'):v*rate/3600 for k,v in list(projection.items())})
    write(B/'manifest.json',dict(source_commit=commit,bundle_sha256=c.sha(B/'runtime_bundle.zip'),instance=choice['metadata'],region='us-east-1',image=image,hourly_rate=rate,soft_usd=5.,hard_usd=7.,soft_seconds=soft,hard_seconds=hard,workload_deadline_seconds=hard-900,watchdog_deadline_seconds=hard-120,termination_deadline_seconds=hard,reserve_seconds=900,name='shimmer-auditor-final',projection=projection))
    preserve=['tuning/auditor_optuna_hpo/seal.json','docs/fix/auditor_optuna_hpo_run/EVIDENCE_MANIFEST.json','docs/fix/auditor_optuna_hpo_run/SELECTED_HYPERPARAMETERS.json','docs/fix/auditor_classifier_lora_current_runtime_run/EVIDENCE_MANIFEST.json']
    write(B/'preservation_before.json',{n:c.sha(ROOT/n) for n in preserve})
    print(json.dumps(dict(source_commit=commit,rate=rate,projection=projection,initial_evaluation_files=0,bundle_sha256=c.sha(B/'runtime_bundle.zip')),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['seal','bundle']);globals()[parser.parse_args().action]()
