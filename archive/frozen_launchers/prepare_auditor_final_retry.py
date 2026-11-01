"""Prepare the explicitly authorized single final retry; never reads evaluation data."""
import hashlib,json,subprocess,sys,zipfile
from pathlib import Path
import auditor_final_core as f
import auditor_classifier_lora_core as c
from auditor_final_retry_cloud import git
from cloud_run_common import credential_locations
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/auditor_final_retry_run'
PAYLOAD=ROOT/'.tmp/auditor_final_retry_payload'
BASELINE='04cdb026484b38c4319b9d58a94e3fc20198c61c'

def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes((json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n').encode())

def prepare():
 import numpy as np
 from auditor_feature_diagnostics import HistoricalAdmission,HISTORICAL_RECEIPTS_SHA256
 f.require(not (BASE/'LAUNCH_INTENT.json').exists() and not PAYLOAD.exists(),'Fresh retry only')
 f.require(all(line.startswith('?? ') for line in git('status','--porcelain').decode().splitlines()),'Clean tracked source required')
 git('merge-base','--is-ancestor',BASELINE,'HEAD')
 source_commit=git('rev-parse','HEAD').decode().strip()
 old=c.read(ROOT/'tuning/auditor_final/seal.json')
 names=list(old['files'])+['tools/auditor_feature_diagnostics.py','tuning/auditor_final/historical_train_features.jsonl','tuning/first_domain_agnostic_v1/experiment.json']
 PAYLOAD.mkdir(parents=True)
 for name in names:
  value=(ROOT/name).read_bytes()
  if name.endswith('adapter_model.safetensors'):
   f.require(hashlib.sha256(value).hexdigest()==old['files'][name],'Canonical adapter unchanged')
  else:
   f.require(value==git('show',BASELINE+':'+name),'Reviewed baseline changed: '+name)
   f.require(not credential_locations(value,name),'Possible credential; stop')
  target=PAYLOAD/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(value)
 rows=f.train_rows(c.read(PAYLOAD/'tuning/auditor_final/records_train_only.json'))
 HistoricalAdmission(np,rows,PAYLOAD/'tuning/auditor_final/historical_train_features.jsonl')
 f.require(c.read(ROOT/'docs/fix/auditor_optuna_hpo_run/SELECTED_HYPERPARAMETERS.json')==f.PARAMS,'Frozen four HPO values')
 files={name:c.sha(PAYLOAD/name) for name in names}
 seal=dict(files=files,scope='one explicitly authorized final Auditor retry; 1792 exact admissions then896; delayed evaluation only',baseline_commit=BASELINE,admission_reference_sha256=HISTORICAL_RECEIPTS_SHA256)
 write(PAYLOAD/'tuning/auditor_final/seal.json',seal);write(BASE/'retry_seal.json',seal)
 files['tuning/auditor_final/seal.json']=c.sha(BASE/'retry_seal.json')
 local_files=names+['tools/prepare_auditor_final_retry.py','tools/auditor_final_retry_cloud.py','tools/test_auditor_final_retry.py','tools/cloud_run_common.py','tools/cloud_run_watchdog.py','tools/lambda_experiment_provider.py','tools/run_remote_experiment.py','tools/test_auditor_feature_admission.py','tools/test_auditor_feature_diagnostics.py']
 manifest=dict(source_commit=source_commit,baseline_commit=BASELINE,seal_sha256=c.sha(BASE/'retry_seal.json'),files=files,local_source_hashes={name:c.sha(ROOT/name) for name in local_files},train_rows=1792,admission='exact FP32 byte SHA-256 for all1792 plus persisted recheck',admission_reference_sha256=HISTORICAL_RECEIPTS_SHA256,evaluation_payload_initially_absent=True,evaluation_bindings=f.EVAL_HASHES,updates=896,params=f.PARAMS)
 write(BASE/'execution_manifest.json',manifest);write(PAYLOAD/'execution_manifest.json',manifest)
 test=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-m','unittest','discover','-s','tools','-p','test_auditor_feature*.py','-v'],cwd=ROOT,capture_output=True)
 (BASE/'admission_tests.log').write_bytes(test.stdout+test.stderr);f.require(test.returncode==0,'Admission tests')
 for pattern,label in [('test_auditor_final.py','final_contract_tests'),('test_auditor_final_retry.py','retry_tests')]:
  test=subprocess.run([str(ROOT/'.venv/Scripts/python.exe'),'-m','unittest','discover','-s','tools','-p',pattern,'-v'],cwd=ROOT,capture_output=True)
  (BASE/(label+'.log')).write_bytes(test.stdout+test.stderr);f.require(test.returncode==0,label)
 scope=subprocess.run([sys.executable,'-B','tools/auditor_final_remote.py','scope'],cwd=PAYLOAD,capture_output=True)
 (BASE/'bundle_check.log').write_bytes(scope.stdout+scope.stderr);f.require(scope.returncode==0,'Packaged scope')
 f.require(not (PAYLOAD/'evaluation_payload').exists(),'No evaluation payload')
 with zipfile.ZipFile(BASE/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as archive:
  for name in files:archive.write(PAYLOAD/name,name)
  archive.write(PAYLOAD/'execution_manifest.json','execution_manifest.json')
 with zipfile.ZipFile(BASE/'runtime_bundle.zip') as archive:
  f.require(set(archive.namelist())==set(files)|{'execution_manifest.json'},'Exact bundle members')
  for name,digest in files.items():f.require(hashlib.sha256(archive.read(name)).hexdigest()==digest,'Bundle identity')
 live=c.read(BASE/'live_preflight.json');choice=live['a10'];rate=choice['metadata']['hourly_rate']
 f.require(live['instances']==[] and 'us-east-1' in choice['regions'] and live['pinned_image_available'] and 0<rate<=1.29,'Provider prerequisites')
 hard=7/rate*3600;soft=5/rate*3600
 write(BASE/'manifest.json',dict(source_commit=source_commit,baseline_commit=BASELINE,bundle_sha256=c.sha(BASE/'runtime_bundle.zip'),instance=choice['metadata'],region='us-east-1',image=live['image'],hourly_rate=rate,soft_usd=5.,hard_usd=7.,soft_seconds=soft,hard_seconds=hard,workload_deadline_seconds=hard-900,watchdog_deadline_seconds=hard-180,termination_deadline_seconds=hard,reserve_seconds=900,name='shimmer-auditor-final-retry'))
 write(BASE/'training_authorization.json',dict(operator_authorized=True,action='auditor-final-training-evaluation',source_commit=source_commit,execution_manifest_sha256=c.sha(BASE/'execution_manifest.json'),seal_sha256=c.sha(BASE/'retry_seal.json'),instances=1,gpus=1,updates=896,params=f.PARAMS,evaluation_after_updates=896,soft_budget_usd=5.,hard_budget_usd=7.,launch_epoch=0,hourly_rate=rate,workload_deadline_epoch=0,provider='https://cloud.lambda.ai',region='us-east-1',instance_type='gpu_1x_a10',authorization='Explicit user final retry attachment f7f8ae24-a268-4aa8-8c9d-ecc0ebcc0fe9; one launch; all1792 exact admission;896 updates; delayed DEV; no second paid attempt, protected test, Producer, full Shimmer or push'))
 write(BASE/'bundle_check_results.json',dict(passed=True,execution_manifest_sha256=c.sha(BASE/'execution_manifest.json'),payload_files=len(files),evaluation_payload_absent=True,reviewed_baseline_byte_identity=True))
 write(BASE/'LOCAL_GATES.json',dict(passed=True,execution_manifest_sha256=c.sha(BASE/'execution_manifest.json'),logs={name:c.sha(BASE/name) for name in ['admission_tests.log','final_contract_tests.log','retry_tests.log','bundle_check.log']}))
 write(BASE/'preservation_before.json',{name:c.sha(ROOT/name) for name in ['tuning/auditor_final/seal.json','docs/fix/auditor_final_run/EVIDENCE_MANIFEST.json','docs/fix/auditor_blocker_closure_run/EVIDENCE_MANIFEST.json','tuning/auditor_optuna_hpo/seal.json','docs/fix/auditor_optuna_hpo_run/SELECTED_HYPERPARAMETERS.json']})
 print(json.dumps(dict(prepared=True,source_commit=source_commit,manifest_sha256=c.sha(BASE/'execution_manifest.json'),bundle_sha256=c.sha(BASE/'runtime_bundle.zip'),provider_launches=0)))

if __name__=='__main__':prepare()
