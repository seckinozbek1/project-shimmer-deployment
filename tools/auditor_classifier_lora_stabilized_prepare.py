"""Seal the authorized final runtime, preserving all earlier preparation artifacts."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import auditor_classifier_lora_core as c
from auditor_classifier_lora_cloud import git
from cloud_run_common import credential_locations,write_json

ROOT=Path(__file__).resolve().parents[1];B=ROOT/'docs/fix/auditor_classifier_lora_stabilized_run';D=ROOT/'tuning/auditor_classifier_lora_fork'


def prepare():
    assert not (B/'LAUNCH_INTENT.json').exists(),'One authorization already consumed'
    for folder in ['auditor_classifier_lora_stable','auditor_classifier_lora_fork']:
        seal=c.read(ROOT/'tuning'/folder/'seal.json')
        for p,h in seal['files'].items():assert c.sha(ROOT/p)==h,p
    for p,h in c.read(D/'runtime_bindings.json').items():assert c.sha(ROOT/p)==h,p
    for p,h in c.read(D/'bindings.json').items():assert c.sha(ROOT/p)==h,p
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tools','-p','test_auditor_classifier_lora*.py'],capture_output=True)
    assert not credential_locations(result.stdout+result.stderr,'tests')
    (B/'local_tests.log').write_bytes(result.stdout+result.stderr);assert result.returncode==0
    live=c.read(B/'live_capacity.json');assert live['instances']==[]
    choices=[x for x in live['a10'] if x['architecture']=='x86_64' and x['regions']];assert len(choices)==1,'A10 unavailable'
    choice=choices[0];rate=choice['metadata']['hourly_rate'];assert rate>0
    region='us-east-1' if 'us-east-1' in choice['regions'] else choice['regions'][0]
    image=next(x for x in c.read(B/'images.json') if x['region']==region and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    soft=2.5/rate*3600;hard=3.5/rate*3600;projected=140*60
    assert projected<hard and hard-600>130*60,'Complete workload cannot fit with reserve'
    names=['tools/'+n for n in ['auditor_classifier_lora_stabilized_remote.py','auditor_classifier_lora_core.py','auditor_classifier_lora_fork.py','auditor_classifier_lora_stable.py','auditor_v2_execution.py','auditor_v2_diagnostic.py','auditor_linear_core.py']]
    names+=['tuning/first_domain_agnostic_v1/dependency_lock.json','tuning/second_tuning_eval_runtime_v2_1/telemetry_worker.py']
    names+=['tuning/auditor_classifier_lora/'+n for n in ['records.json','schedule.json','challenges.json']]
    names+=['tuning/auditor_classifier_lora_fork/'+n for n in ['experiment.json','adapter_copy.json','runtime_bindings.json','update0_controls.json','train_baseline.json']]
    names+=list(c.read(D/'runtime_bindings.json'))
    commit=git('rev-parse','HEAD').decode().strip();blobs={}
    for name in sorted(set(names)):
        assert not any(x in name.lower() for x in ['holdout','producer','protected','features.npy'])
        p=ROOT/name;value=p.read_bytes()
        if p.suffix not in ('.safetensors','.npy'):
            assert not credential_locations(value,name)
            # Exact committed runtime code/metadata, never unreviewed working edits.
            assert value.replace(b'\r\n',b'\n')==git('show',commit+':'+name).replace(b'\r\n',b'\n'),name
        blobs[name]=value
    manifest=dict(source_commit=commit,files={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()},records=2040,train=1792,external_dev=200,historical_dev=48,holdout_rows=0)
    content=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode();blobs['execution_manifest.json']=content
    permit=dict(action='step120-classifier-fork-only',operator_authorized=True,request_attachment='6234692b-4bf4-495e-952f-5d48d5219d6c',source_commit=commit,
        execution_manifest_sha256=hashlib.sha256(content).hexdigest(),records_sha256=c.sha(ROOT/'tuning/auditor_classifier_lora/records.json'),spec_sha256=c.sha(D/'experiment.json'),
        maximum_instances=1,soft_budget_usd=2.5,hard_budget_usd=3.5,updates=896,base_updates=False,generation=False,holdout_access=False,producer_execution=False,protected_access=False,provider='https://cloud.lambda.ai')
    (B/'execution_manifest.json').write_bytes(content);write_json(B/'training_authorization.json',permit)
    with zipfile.ZipFile(B/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,value in blobs.items():z.writestr(name,value)
    cloud=dict(source_commit=commit,bundle_sha256=c.sha(B/'runtime_bundle.zip'),instance=choice['metadata'],region=region,image=image,hourly_rate=rate,
        soft_usd=2.5,hard_usd=3.5,soft_seconds=soft,hard_seconds=hard,reserve_seconds=600,workload_deadline_seconds=hard-600,watchdog_deadline_seconds=hard-120,termination_deadline_seconds=hard,
        projected_seconds_with_reserve=projected,projected_cost=projected*rate/3600,name='shimmer-auditor-classifier-stabilized')
    write_json(B/'manifest.json',cloud)
    check=B/'bundle_check';check.mkdir(exist_ok=True)
    with zipfile.ZipFile(B/'runtime_bundle.zip') as z:z.extractall(check)
    write_json(check/'training_authorization.json',permit)
    result=subprocess.run([sys.executable,'-B','tools/auditor_classifier_lora_stabilized_remote.py','scope'],cwd=check,capture_output=True)
    assert not credential_locations(result.stdout+result.stderr,'bundle tests')
    (B/'bundle_check.log').write_bytes(result.stdout+result.stderr);assert result.returncode==0,'Packaged scope failed'
    write_json(B/'bundle_check_results.json',dict(passed=True,members=len(blobs),records=2040,historical_reference_readonly=True))
    write_json(B/'LOCAL_GATES.json',dict(passed=True,tests_log='local_tests.log',sealed_fork_verified=True,cloud_authorization_attachment=permit['request_attachment']))
    print(json.dumps(cloud))


if __name__=='__main__':prepare()
