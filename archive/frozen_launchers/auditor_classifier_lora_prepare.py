"""Deterministic local preflight and sealing; never loads model weights or trains."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
import auditor_classifier_lora_core as c
from auditor_classifier_lora_cloud import git
from cloud_run_common import require,credential_locations,write_json

ROOT=Path(__file__).resolve().parents[1];D=ROOT/'tuning/auditor_classifier_lora';B=ROOT/'docs/fix/auditor_classifier_lora_run';OLD=ROOT/'tuning/auditor_v2_diagnostic'


def local():
    require(not (B/'LAUNCH_INTENT.json').exists(),'One-off authorization consumed')
    D.mkdir(exist_ok=True);B.mkdir(exist_ok=True)
    for name,digest in c.read(OLD/'manifest.json')['files'].items():assert c.sha(ROOT/name)==digest,name
    original=c.read(OLD/'experiment.json')
    spec=dict(model_id=original['model_id'],revision=original['revision'],asset_hashes=original['asset_hashes'],base_weight_sha256=original['base_weight_sha256'],
        architecture='pinned base -> fresh classifier LoRA -> final prompt-token hidden state -> four-way head',historical_adapter_loaded=False,
        lora=dict(r=8,lora_alpha=16,lora_dropout=.05,bias='none',task_type='CAUSAL_LM',target_modules=c.TARGETS,init_lora_weights=True),
        head=dict(input_dim=3072,outputs=4,parameters=c.HEAD_PARAMS,initialization='zero',dtype='float32'),
        optimizer=dict(name='AdamW',lora_lr=1e-4,head_lr=1e-2,betas=[.9,.999],eps=1e-8,weight_decay=0,max_grad_norm=1,scheduler=None,regularization=.001),
        training=dict(seed=7,passes=2,microbatch=1,accumulation=4,effective_batch=4,updates=896,checkpoints=[448,896]),
        normalization='none',classes=c.CLASSES,expected_lora_parameters=c.LORA_PARAMS,expected_total_trainable=c.LORA_PARAMS+c.HEAD_PARAMS,
        gates=original['co_primary'],challenge_gates=original['challenge_gates'],data_verdict='AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY',data_admitted=False,
        gradient_checkpointing=dict(enabled=True,use_reentrant=True),base_preparation='prepare_model_for_kbit_training; base frozen; nonquantized tensors cast to FP32 before immutable state hash')
    for name in ['records.json','challenges.json']:(D/name).write_bytes((OLD/name).read_bytes())
    records=c.read(D/'records.json');plan=c.schedule([r['example_id'] for r in records[:1792]])
    write_json(D/'experiment.json',spec);write_json(D/'schedule.json',plan)
    c.validate(records,spec,c.read(D/'challenges.json'),plan)
    historical=ROOT/'docs/fix/auditor_canonical_tuning_run/downloaded/evidence/checkpoint-120/adapter_model.safetensors'
    assert c.sha(historical)=='733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6'
    # Preserve only metadata/receipts and known binary identity; no HOLDOUT content.
    preserve=dict(c.read(ROOT/'docs/fix/auditor_v2_diagnostic_run/preservation_before.json'))
    preserve.update({historical.relative_to(ROOT).as_posix():c.sha(historical)})
    for name in ['docs/fix/AUDITOR_V2_DIAGNOSTIC_RESULTS.md','docs/fix/auditor_v2_diagnostic_run/EVIDENCE_MANIFEST.json','tuning/auditor_external_relation_v2/holdout_receipt.json']:
        preserve[name]=c.sha(ROOT/name)
    for name,digest in preserve.items():assert c.sha(ROOT/name)==digest,name
    write_json(B/'preservation_before.json',preserve)
    os.environ.update(USE_TORCH='0',USE_TF='0',USE_FLAX='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    sys.path.insert(0,str(ROOT/'tuning/second_domain_agnostic_v2'));import runtime
    sys.path.insert(0,str(ROOT/'tools'));from auditor_linear_core import normalized_input
    tok=runtime.old.tokenizer('auditor')
    for row in records:
        text=tok.decode(row['input_ids'],skip_special_tokens=False,clean_up_tokenization_spaces=False)
        assert tok(text,add_special_tokens=False)['input_ids']==row['input_ids']
    by={r['example_id']:r for r in records}
    train=[json.loads(x) for x in (ROOT/'tuning/auditor_external_relation_v2/merged_four_way_train.jsonl').read_bytes().splitlines()]
    h={r['example_id']:r for r in c.read(ROOT/'tuning/auditor_canonical_execution/dataset.json')}
    for row in train+[h[r['example_id']] for r in records[1992:]]:
        value,_=normalized_input(row['input'])
        prompt=tok.apply_chat_template(runtime.task_messages(dict(role='auditor',input=value)),tokenize=False,add_generation_prompt=True)
        assert tok(prompt,add_special_tokens=False)['input_ids']==by[row['example_id']]['input_ids']
        altered=dict(row,dataset='DO_NOT_USE',provenance='DO_NOT_USE',relation='DO_NOT_USE',split='DO_NOT_USE')
        assert normalized_input(altered['input'])[0]==value
    assert c.read(ROOT/'tuning/auditor_external_relation_v2/holdout_receipt.json')['consumed'] is False
    assert 'torch' not in sys.modules
    paths=list(D.glob('*.json'))+[ROOT/'tools'/n for n in ['auditor_classifier_lora_core.py','auditor_classifier_lora_remote.py','auditor_classifier_lora_cloud.py','auditor_classifier_lora_prepare.py','test_auditor_classifier_lora.py']]
    for p in paths:
        hits=credential_locations(p.read_bytes(),str(p));assert not hits,hits
        if p.suffix=='.py':ast.parse(p.read_text())
    result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tools','-p','test_auditor_classifier_lora.py'],capture_output=True)
    assert not credential_locations(result.stdout+result.stderr,'local tests')
    (B/'local_tests.log').write_bytes(result.stdout+result.stderr);assert result.returncode==0,'Local tests failed'
    write_json(D/'binding.json',dict(files={name:c.sha(D/name) for name in ['records.json','challenges.json','experiment.json','schedule.json']},
        original_records_sha256=c.sha(OLD/'records.json'),previous_results_commit='8a116698d2048315a254e8e1a07438ca2263a88a'))
    write_json(B/'LOCAL_GATES.json',dict(passed=True,tests=7,rows=2040,train=1792,external_dev=200,historical_dev=48,updates=896,
        checkpoint_steps=[448,896],historical_adapter_in_payload=False,holdout_access=False,old_feature_cache_used=False,provenance_exclusion=True,
        torch_imported=False,weights_loaded=False,limitations='Parameter inventory verified with deterministic architecture fixtures locally; actual loaded GPU inventory is mandatory before training.'))
    print('Local classifier-LoRA gates passed; no model load or training.')


def prepare():
    local()
    live=c.read(B/'live_capacity.json');assert live['instances']==[]
    choices=[x for x in live['a10'] if x['architecture']=='x86_64' and x['regions']];assert len(choices)==1,'NO_GO: no suitable A10'
    choice=choices[0];rate=choice['metadata']['hourly_rate'];assert rate>0
    region='us-east-1' if 'us-east-1' in choice['regions'] else choice['regions'][0]
    image=next(x for x in c.read(B/'images.json') if x['region']==region and x['family']=='lambda-stack-24-04' and x['architecture']=='x86_64')
    soft=2/rate*3600;hard=3/rate*3600;work=hard-600
    # Previous 120-update A10 run: mean4.690s, p95 5.006s/update.
    projected=900+896*6+248+180+600
    assert projected<hard,'NO_GO: conservative full workload plus teardown cannot fit'
    names=['tools/auditor_classifier_lora_core.py','tools/auditor_classifier_lora_remote.py','tuning/first_domain_agnostic_v1/dependency_lock.json','tuning/second_tuning_eval_runtime_v2_1/telemetry_worker.py']
    names += ['tuning/auditor_classifier_lora/'+n for n in ['records.json','challenges.json','experiment.json','schedule.json','binding.json']]
    commit=git('rev-parse','HEAD').decode().strip();blobs={}
    for name in names:
        value=(ROOT/name).read_bytes();assert not credential_locations(value,name)
        assert value.replace(b'\r\n',b'\n')==git('show',commit+':'+name).replace(b'\r\n',b'\n'),'Uncommitted payload '+name
        blobs[name]=value
    manifest=dict(source_commit=commit,files={k:__import__('hashlib').sha256(v).hexdigest() for k,v in blobs.items()},historical_adapter_payloads=0,holdout_rows=0,producer_payloads=0,protected_files=0,records=2040)
    content=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode();blobs['execution_manifest.json']=content
    permit=dict(action='fresh-auditor-classifier-lora-only',operator_authorized=True,request_attachment='775f836d-d349-488b-b201-66129661f3cc',source_commit=commit,
        execution_manifest_sha256=__import__('hashlib').sha256(content).hexdigest(),records_sha256=c.sha(D/'records.json'),maximum_instances=1,soft_budget_usd=2,hard_budget_usd=3,
        updates=896,trainable_parameters=c.LORA_PARAMS+c.HEAD_PARAMS,base_updates=False,historical_adapter_loaded=False,generation=False,holdout_access=False,producer_execution=False,protected_access=False,provider='https://cloud.lambda.ai')
    (B/'execution_manifest.json').write_bytes(content);write_json(B/'training_authorization.json',permit)
    with zipfile.ZipFile(B/'runtime_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
        for name,value in blobs.items():z.writestr(name,value)
    cloud=dict(source_commit=commit,bundle_sha256=c.sha(B/'runtime_bundle.zip'),instance=choice['metadata'],region=region,image=image,hourly_rate=rate,
        soft_usd=2,hard_usd=3,soft_seconds=soft,hard_seconds=hard,reserve_seconds=600,workload_deadline_seconds=work,watchdog_deadline_seconds=hard-120,termination_deadline_seconds=hard,
        projected_seconds_with_reserve=projected,projected_cost=projected*rate/3600,name='shimmer-auditor-classifier-lora',projection=dict(setup=900,seconds_per_update=6,updates=896,evaluation=248,state_hash_and_save=180,teardown=600))
    write_json(B/'manifest.json',cloud)
    check=B/'bundle_check';check.mkdir(exist_ok=True)
    with zipfile.ZipFile(B/'runtime_bundle.zip') as z:z.extractall(check)
    write_json(check/'training_authorization.json',permit)
    result=subprocess.run([sys.executable,'-B','tools/auditor_classifier_lora_remote.py','scope'],cwd=check,capture_output=True)
    assert not credential_locations(result.stdout+result.stderr,'bundle tests')
    (B/'bundle_check.log').write_bytes(result.stdout+result.stderr);assert result.returncode==0,'Sealed runtime scope failed'
    write_json(B/'bundle_check_results.json',dict(passed=True,members=len(blobs),old_adapter_absent=True))
    print(json.dumps(cloud,indent=2))


if __name__=='__main__':
    if '--local-only' in sys.argv:local()
    else:prepare()
