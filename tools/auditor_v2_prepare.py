"""Verify frozen preflight, test implementation, and seal exact execution payload."""
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import auditor_v2_execution as c
from auditor_v2_cloud import git
from cloud_run_common import require,credential_locations,write_json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/auditor_v2_diagnostic_run'
D=ROOT/'tuning/auditor_v2_diagnostic'


def local():
    for name,digest in c.read(D/'manifest.json')['files'].items():assert c.sha(ROOT/name)==digest,name
    records=c.read(D/'records.json');spec=c.read(D/'experiment.json')
    c.validate(records,spec,c.read(D/'challenges.json'),c.read(D/'baseline.json'))
    # Do not rerun preparation: consume its bound records, never reopen mixed V2.
    for name,digest in c.read(D/'bindings.json').items():
        if name!='external_dev_selected_content_sha256':assert c.sha(ROOT/name)==digest,name
    os.environ.update(USE_TORCH='0',USE_TF='0',USE_FLAX='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    sys.path.insert(0,str(ROOT/'tuning/second_domain_agnostic_v2'))
    import runtime
    tok=runtime.old.tokenizer('auditor')
    for row in records:
        prompt=tok.decode(row['input_ids'],skip_special_tokens=False,clean_up_tokenization_spaces=False)
        assert tok(prompt,add_special_tokens=False)['input_ids']==row['input_ids']
    # Reconstruct all authorized TRAIN and historical DEV prompts from input only.
    train=[json.loads(x) for x in (ROOT/'tuning/auditor_external_relation_v2/merged_four_way_train.jsonl').read_bytes().splitlines()]
    historical={r['example_id']:r for r in c.read(ROOT/'tuning/auditor_canonical_execution/dataset.json')}
    by={r['example_id']:r for r in records}
    for row in train+[historical[r['example_id']] for r in records[1992:]]:
        normalized,_=c.d.core.normalized_input(row['input'])
        prompt=tok.apply_chat_template(runtime.task_messages(dict(role='auditor',input=normalized)),tokenize=False,add_generation_prompt=True)
        assert tok(prompt,add_special_tokens=False)['input_ids']==by[row['example_id']]['input_ids']
        # Arbitrary outer provenance, label, ID, split cannot affect this builder.
        altered=dict(row,relation='FORBIDDEN_LABEL',dataset='FORBIDDEN_PROVENANCE',split='FORBIDDEN_SPLIT',example_id='FORBIDDEN_ID')
        normalized2,_=c.d.core.normalized_input(altered['input'])
        assert runtime.task_messages(dict(role='auditor',input=normalized2))==runtime.task_messages(dict(role='auditor',input=normalized))
    assert 'torch' not in sys.modules
    result=dict(passed=True,records=2040,train=1792,external_dev=200,historical_dev=48,
        provenance_exclusion=True,all_token_ids_roundtrip_bound=True,external_dev_uses_unchanged_preflight_binding=True,
        mixed_v2_file_opened=False,holdout_access=False,torch_imported=False)
    write_json(BASE/'LOCAL_GATES.json',result)
    return result


def prepare():
    require(not (BASE/'LAUNCH_INTENT.json').exists(),'One-off authorization already consumed')
    local()
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tools','-p','test_auditor_v2*.py'],capture_output=True)
    require(not credential_locations(result.stdout+result.stderr,'tests'),'Possible credential; stop')
    (BASE/'local_tests.log').write_bytes(result.stdout+result.stderr);require(result.returncode==0,'Tests failed')
    live=c.read(BASE/'live_capacity.json');require(live['instances']==[],'Inventory nonempty')
    choices=[x for x in live['a10'] if x['metadata']['type']=='gpu_1x_a10' and x['architecture']=='x86_64' and x['regions']]
    require(len(choices)==1,'NO_GO: no suitable A10')
    choice=choices[0];rate=choice['metadata']['hourly_rate'];require(rate>0,'Invalid rate')
    region='us-east-1' if 'us-east-1' in choice['regions'] else choice['regions'][0]
    image=next(x for x in c.read(BASE/'images.json') if x['region']==region and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    hard=1.50/rate*3600;soft=.75/rate*3600;work=hard-600
    require(1800<work and (1800+600)*rate/3600<1.5,'NO_GO: projection exceeds hard ceiling')
    names=['tools/auditor_v2_remote.py','tools/auditor_v2_execution.py','tools/auditor_v2_diagnostic.py','tools/auditor_linear_core.py',
        'tuning/first_domain_agnostic_v1/dependency_lock.json','tuning/second_tuning_eval_runtime_v2_1/telemetry_worker.py']
    names+=['tuning/auditor_v2_diagnostic/'+n for n in ['records.json','experiment.json','challenges.json','baseline.json']]
    head=git('rev-parse','HEAD').decode().strip();blobs={}
    for name in names:
        value=(ROOT/name).read_bytes();require(not credential_locations(value,name),'Possible credential; stop')
        require(value.replace(b'\r\n',b'\n')==git('show',head+':'+name).replace(b'\r\n',b'\n'),'Uncommitted payload '+name)
        blobs[name]=value
    spec=c.read(D/'experiment.json')
    adapter=ROOT/'docs/fix/auditor_canonical_tuning_run/downloaded/evidence/checkpoint-120'
    for name,digest in spec['adapter_hashes'].items():
        require(c.sha(adapter/name)==digest,'Adapter mismatch');blobs['adapter/'+name]=(adapter/name).read_bytes()
    manifest=dict(source_commit=head,files={k:c.hashlib.sha256(v).hexdigest() for k,v in blobs.items()},rows=2040,holdout_rows=0,
                  producer_payloads=0,protected_files=0,credentials=0)
    manifest_bytes=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    blobs['execution_manifest.json']=manifest_bytes
    permit=dict(action='auditor-v2-one-head-classification-only',operator_authorized=True,request_attachment='1c5d2f2a-3534-4fc2-a2b8-0ac4a12f3536',
        updates=200,trainable_parameters=12292,maximum_instances=1,hard_budget_usd=1.5,soft_budget_usd=.75,
        backbone_updates=False,lora_updates=False,producer_execution=False,protected_access=False,generation=False,holdout_access=False,
        provider='https://cloud.lambda.ai',execution_manifest_sha256=c.hashlib.sha256(manifest_bytes).hexdigest())
    with zipfile.ZipFile(BASE/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,value in blobs.items():z.writestr(name,value)
    (BASE/'execution_manifest.json').write_bytes(manifest_bytes);write_json(BASE/'training_authorization.json',permit)
    cloud=dict(source_commit=head,bundle_sha256=c.sha(BASE/'runtime_bundle.zip'),instance=choice['metadata'],region=region,image=image,
        hourly_rate=rate,soft_usd=.75,hard_usd=1.5,soft_seconds=soft,hard_seconds=hard,reserve_seconds=600,
        workload_deadline_seconds=work,watchdog_deadline_seconds=hard-120,termination_deadline_seconds=hard,
        projected_workload_seconds=1800,projected_seconds_with_reserve=2400,projected_cost=2400*rate/3600,name='shimmer-auditor-v2-diagnostic')
    write_json(BASE/'manifest.json',cloud)
    check=BASE/'bundle_check';check.mkdir(exist_ok=True)
    with zipfile.ZipFile(BASE/'runtime_bundle.zip') as z:z.extractall(check)
    write_json(check/'training_authorization.json',permit)
    result=subprocess.run([sys.executable,'-B','tools/auditor_v2_remote.py','scope'],cwd=check,capture_output=True)
    require(not credential_locations(result.stdout+result.stderr,'bundle tests'),'Possible credential; stop')
    (BASE/'bundle_check.log').write_bytes(result.stdout+result.stderr);require(result.returncode==0,'Packaged scope failed')
    write_json(BASE/'bundle_check_results.json',dict(passed=True,members=len(blobs)))
    print(json.dumps(cloud,indent=2))


if __name__=='__main__':
    if '--local-only' in sys.argv:print(local())
    else:prepare()
