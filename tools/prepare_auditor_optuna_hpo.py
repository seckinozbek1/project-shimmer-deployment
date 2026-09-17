"""Local-only preparation: TRAIN/tokenizer/metadata; never loads model tensors."""
import json
import os
import sys
from pathlib import Path
from collections import Counter
import auditor_optuna_hpo as h

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'tuning/auditor_optuna_hpo'
B=ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run'
E=B/'downloaded/evidence'


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n'
    path.write_bytes(raw.encode())


def prepare():
    from auditor_optuna_hpo_remote import install_audit
    process_access=dict(access_counts=dict.fromkeys(h.FORBIDDEN,0),denied_before_open=0)
    install_audit(process_access)
    names=[ROOT/'tuning/auditor_external_relation_v2/merged_four_way_train.jsonl',E/'current_train_features.jsonl',E/'current_train_baseline.json',
           ROOT/'tuning/auditor_classifier_lora_current_runtime/experiment.json',ROOT/'tuning/auditor_classifier_lora_current_runtime/controls.json',
           ROOT/'tuning/first_domain_agnostic_v1/dependency_lock.json',E/'initialization.json',E/'checkpoint-0/identity.json']
    boundary=h.DataBoundary({p:h.sha(p) for p in names})
    rows=boundary.read(names[0],jsonl=True);receipts=boundary.read(names[1],jsonl=True)
    baseline=boundary.read(names[2]);spec=boundary.read(names[3]);controls=boundary.read(names[4]);lock=boundary.read(names[5]);initialization=boundary.read(names[6]);identity=boundary.read(names[7])
    split=h.freeze_split(rows)
    h.require([r['example_id'] for r in rows]==baseline['example_ids']==[r['example_id'] for r in receipts],'TRAIN order')
    h.require([r['relation'] for r in rows]==baseline['labels'],'TRAIN labels')
    os.environ.update(USE_TORCH='0',USE_TF='0',USE_FLAX='0',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    sys.path.insert(0,str(ROOT/'tuning/second_domain_agnostic_v2'))
    import runtime
    from auditor_linear_core import normalized_input
    import auditor_classifier_lora_fork as fork
    tok=runtime.old.tokenizer('auditor')
    records=[]
    for row,receipt in zip(rows,receipts):
        value,_=normalized_input(row['input'])
        prompt=tok.apply_chat_template(runtime.task_messages(dict(role='auditor',input=value)),tokenize=False,add_generation_prompt=True)
        ids=tok(prompt,add_special_tokens=False)['input_ids']
        prompt_sha=__import__('hashlib').sha256(prompt.encode()).hexdigest()
        h.require(prompt_sha==receipt['prompt_sha256'] and fork.token_hash(ids)==receipt['token_sha256'],'current runtime prompt/token binding')
        records.append(dict(example_id=row['example_id'],relation=row['relation'],input_ids=ids,prompt_sha256=prompt_sha,split='train'))
    h.require('torch' not in sys.modules,'no local model runtime')
    # Hash-only reads, never safetensors/NumPy deserialization or model weights loading.
    artifacts={}
    for name,digest in h.ARTIFACT_HASHES.items():
        p=E/name;h.require(h.sha(p)==digest,'current artifact identity')
        artifacts[name]=dict(path=p.relative_to(ROOT).as_posix(),sha256=digest)
    for name in ['adapter_model.safetensors','adapter_config.json']:
        p=E/'checkpoint-0/classifier_fork'/name
        expected=identity['lora_sha256'] if name.endswith('safetensors') else identity['config_sha256']
        h.require(h.sha(p)==expected,'clean checkpoint0 adapter')
        artifacts[name]=dict(path=p.relative_to(ROOT).as_posix(),sha256=expected)
    contract=dict(python=lock['python'],platform=lock['platform'],cuda_runtime=lock['cuda_runtime'],packages=lock['packages'],
        architecture='LlamaForCausalLM',model_id=spec['model_id'],revision=spec['revision'],base_weight_sha256=spec['base_weight_sha256'],asset_hashes=spec['asset_hashes'],
        base_state_sha256=initialization['base_state_sha256'],quantization='NF4',base_autocast='bfloat16',classifier_dtype='float32',attn_implementation='eager',
        base_preparation=spec['base_preparation'],gradient_checkpointing=spec['gradient_checkpointing'])
    for name,value in [('split.json',split),('records_train_only.json',records),('experiment.json',h.config()),('frozen_model.json',spec),('runtime_contract.json',contract),
                       ('artifacts.json',artifacts),('controls.json',controls),('current_train_baseline.json',baseline),('schedule.json',h.schedule(split))]:
        write(D/name,value)
    (D/'.gitattributes').write_bytes(b'* -text\n')
    counts={s:dict(rows=sum(r['split']==s for r in split['assignments']),by_class=dict(Counter(r['relation'] for r in split['assignments'] if r['split']==s)),by_source=dict(Counter(r['source_family'] for r in split['assignments'] if r['split']==s))) for s in ('inner_train','inner_val')}
    write(D/'preparation_receipt.json',dict(counts=counts,source_bindings={p.relative_to(ROOT).as_posix():h.sha(p) for p in names},data_access=boundary.receipt(),
        process_audit=process_access,prompt_source_fields=['normalized input only'],all_1792_prompt_token_hashes_match=True,local_model_load=False,model_inference=False,model_training=False,cloud_resources_created=0,
        initializer_exposure='head-200 supervised fit and normalization previously used all TRAIN including INNER_VAL; HPO selection diagnostic only',source_commit='00d5dcd'))
    print(json.dumps(dict(counts=counts,split_hash=split['split_sha256'],access_counts=boundary.access_counts),indent=2))


if __name__=='__main__':prepare()
