"""Sealed, offline future workload. No provisioner, acquisition, or automatic final run."""
import argparse
import importlib.metadata
import json
import os
import platform
import sys
import time
from pathlib import Path
import auditor_optuna_hpo as h

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'tuning/auditor_optuna_hpo'


def forbidden_path(path):
    value=str(path).lower().replace('\\','/')
    name=value.rsplit('/',1)[-1]
    return any(k in value for k in h.FORBIDDEN) or name in ('dev.json','dev.jsonl','test.json','test.jsonl') or any(k in value for k in ('challenges.json','/auditor_classifier_lora/records.json','/auditor_v2_diagnostic/records.json','/auditor_canonical_execution/dataset.json','finite_partial_state'))


def install_audit(receipt):
    def audit(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):
            raise PermissionError('offline HPO workload')
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)) and forbidden_path(os.fsdecode(args[0])):
            receipt['denied_before_open']+=1
            raise PermissionError('forbidden HPO data before open')
    sys.addaudithook(audit)


def scope():
    seal=json.loads((D/'seal.json').read_bytes())
    for name,digest in seal['files'].items():
        p=(ROOT/name).resolve()
        h.require(p.is_relative_to(ROOT) and not forbidden_path(name),'payload scope')
        h.require(h.sha(p)==digest,'payload binding: '+name)
    boundary=h.DataBoundary({ROOT/n:v for n,v in seal['files'].items()})
    read=lambda name:boundary.read(D/name)
    spec=read('experiment.json');h.require(spec==h.config(),'frozen HPO configuration')
    rows=read('records_train_only.json');split=read('split.json')
    h.require(len(rows)==1792 and all(set(r)=={'example_id','relation','input_ids','prompt_sha256','split'} and r['split']=='train' for r in rows),'TRAIN-only payload')
    h.require({r['example_id'] for r in rows}=={r['example_id'] for r in split['assignments']},'split ID binding')
    h.require(h.digest(split['assignments'])==split['split_sha256'],'split hash')
    h.require(read('schedule.json')==h.schedule(split),'frozen order')
    artifacts=read('artifacts.json')
    h.require(set(artifacts)==set(h.ARTIFACT_HASHES)|{'adapter_model.safetensors','adapter_config.json'},'exact artifact set')
    for name,record in artifacts.items():
        path=(ROOT/record['path']).resolve()
        h.require(path.is_relative_to(ROOT) and not forbidden_path(path),'clean artifact path')
        h.require(h.sha(path)==record['sha256'],'artifact hash')
        if name in h.ARTIFACT_HASHES:h.require(record['sha256']==h.ARTIFACT_HASHES[name],'current-runtime artifact')
    return seal,boundary,rows,split,artifacts


def authorize(permit,seal_sha):
    h.require(permit.get('operator_authorized') is True and permit.get('action')=='auditor-optuna-train-only-hpo','separate HPO authorization required')
    h.require(permit.get('seal_sha256')==seal_sha,'authorization seal')
    h.require(permit.get('instances')==permit.get('gpus')==permit.get('n_jobs')==1,'single instance/GPU/study')
    h.require(permit.get('max_trials')==15 and permit.get('max_updates')==80,'authorization caps')
    h.require(permit.get('soft_budget_usd',0)>0 and permit.get('hard_budget_usd',0)>=permit['soft_budget_usd'],'budget authorization')
    h.require(permit.get('full_training_authorized') is False,'HPO-only authorization')
    h.require(permit.get('provider')=='https://cloud.lambda.ai' and permit.get('region')=='us-east-1' and permit.get('instance_type')=='gpu_1x_a10','fixed future destination')
    launch=permit.get('launch_epoch',0);rate=permit.get('hourly_rate',0);deadline=permit.get('workload_deadline_epoch',0)
    h.require(launch>0 and rate>0 and launch<deadline<=launch+permit['hard_budget_usd']/rate*3600-600,'hard budget with teardown reserve')


def execute(permit_path,base_path,output):
    # No permit is created by preparation. No Windows/local model execution possible.
    permit=json.loads(Path(permit_path).read_bytes());authorize(permit,h.sha(D/'seal.json'))
    h.require(sys.platform=='linux' and platform.machine()=='x86_64','future Linux GPU only')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with (output/'HPO_ATTEMPTED').open('x') as f:f.write('one sequential study; no resume or retry\n')
    access=dict(access_counts=dict.fromkeys(h.FORBIDDEN,0),denied_before_open=0)
    install_audit(access)
    seal,boundary,rows,split,artifacts=scope()
    read=lambda n:boundary.read(D/n)
    expected=read('runtime_contract.json');baseline=read('current_train_baseline.json');controls=read('controls.json')['example_ids']
    h.require(platform.python_version()==expected['python'],'Python compatibility')
    for name,version in expected['packages'].items():h.require(importlib.metadata.version(name)==version,'package compatibility '+name)
    for name,version in read('optuna_dependencies.json').items():h.require(importlib.metadata.version(name)==version,'HPO package '+name)
    os.environ.update(USE_TORCH='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    import torch
    import numpy as np
    import optuna
    from transformers import AutoModelForCausalLM
    from peft import PeftModel,prepare_model_for_kbit_training
    from safetensors.torch import load_file
    import auditor_classifier_lora_fork as fork
    import auditor_classifier_lora_current_core as current
    import auditor_classifier_lora_stable as stable
    from auditor_optuna_hpo_backend import TorchBackend
    h.require(torch.cuda.device_count()==1 and 'A10' in torch.cuda.get_device_name() and 'A100' not in torch.cuda.get_device_name(),'one A10')
    h.require(torch.cuda.get_device_properties(0).total_memory>=22*2**30 and torch.cuda.is_bf16_supported(),'GPU capability')
    h.require(torch.version.cuda==expected['cuda_runtime'],'CUDA compatibility')
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.manual_seed(7);torch.cuda.manual_seed_all(7);np.random.seed(7)
    def budget_gate():
        h.require(time.time()<permit['workload_deadline_epoch'],'budget workload stop; preserve evidence and terminate externally')
    backend=None
    def emit(value):
        budget_gate()
        if backend is not None:value.setdefault('trial',getattr(backend,'trial_number',None))
        with (output/'events.jsonl').open('a') as f:f.write(json.dumps(value,allow_nan=False)+'\n')
    budget_gate();base_path=Path(base_path)
    for name,digest in dict(expected['asset_hashes'],**{'model.safetensors':expected['base_weight_sha256']}).items():h.require(h.sha(base_path/name)==digest,'pinned base file')
    model=AutoModelForCausalLM.from_pretrained(str(base_path),local_files_only=True,trust_remote_code=False,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='eager')
    h.require(model.config.architectures==['LlamaForCausalLM'] and model.config.hidden_size==3072 and model.is_loaded_in_4bit,'pinned architecture')
    quantization=model.config.quantization_config
    if hasattr(quantization,'to_dict'):quantization=quantization.to_dict()
    h.require(quantization['bnb_4bit_quant_type']=='nf4','NF4')
    model.config.use_cache=False
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':True})
    adapter_path=(ROOT/artifacts['adapter_model.safetensors']['path']).parent
    model=PeftModel.from_pretrained(model,str(adapter_path),adapter_name=fork.REFERENCE,is_trainable=False)
    model.load_adapter(str(adapter_path),adapter_name=fork.CANDIDATE,is_trainable=False)
    head=torch.nn.Linear(3072,4,device='cuda',dtype=torch.float32)
    head.load_state_dict(load_file(str(ROOT/artifacts['head-200.safetensors']['path']),device='cuda'),strict=True)
    fork.freeze_slots(model,head)
    adapter_inventory=fork.inventory(adapter_path/'adapter_model.safetensors')
    current.verify_adapter(torch,model,fork.REFERENCE,adapter_inventory);current.verify_adapter(torch,model,fork.CANDIDATE,adapter_inventory)
    audit=stable.FrozenAudit(torch,model)
    h.require(audit.initial_hash==expected['base_state_sha256'],'prepared base function hash')
    mean_np=np.load(ROOT/artifacts['mean.npy']['path'],allow_pickle=False);std_np=np.load(ROOT/artifacts['std.npy']['path'],allow_pickle=False)
    features=np.load(ROOT/artifacts['current_train_features.npy']['path'],allow_pickle=False)
    h.require(features.shape==(1792,3072) and features.dtype==np.float32 and np.isfinite(features).all(),'feature cache')
    h.require(mean_np.shape==std_np.shape==(3072,) and mean_np.dtype==std_np.dtype==np.float32 and np.isfinite(mean_np).all() and np.isfinite(std_np).all() and (std_np>=1e-6).all(),'normalization cache')
    backend=TorchBackend(torch,np,model,head,torch.tensor(mean_np,device='cuda'),torch.tensor(std_np,device='cuda'),rows,split,audit,emit)
    actual=dict(expected,python=platform.python_version(),platform=sys.platform+'_'+platform.machine(),cuda_runtime=torch.version.cuda,packages={n:importlib.metadata.version(n) for n in expected['packages']},base_state_sha256=audit.initial_hash)
    admission=h.ReuseAdmission(np,features,mean_np,std_np,head.weight.detach().cpu().numpy(),head.bias.detach().cpu().numpy(),rows,controls,expected,baseline)
    def select(slot):
        model.set_adapter(fork.REFERENCE if slot=='reference' else fork.CANDIDATE);fork.freeze_slots(model,head)
    def remove():
        model.delete_adapter(fork.REFERENCE);select(fork.CANDIDATE)
        h.require(set(model.peft_config)=={fork.CANDIDATE},'reference removed')
    try:
        result=admission.run(actual,backend.observe,select,remove);backend.admitted=True
        emit(dict(event='reuse_admitted',**result))
        study,winner=h.run_study(optuna,backend,split,result['ce'],emit,storage='sqlite:///'+str(output/'study.sqlite3'))
        h.require(audit.unchanged(full=True),'final frozen base')
        (output/'winner.json').write_text(json.dumps(winner,indent=2)+'\n')
        (output/'trials.json').write_text(json.dumps([dict(number=t.number,state=t.state.name,params=t.params,value=t.value,attrs=t.user_attrs) for t in study.trials],indent=2)+'\n')
    finally:
        (output/'data_access.json').write_text(json.dumps(dict(access,boundary=boundary.receipt()),indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['scope','execute']);parser.add_argument('--permit');parser.add_argument('--base-path');parser.add_argument('--output')
    args=parser.parse_args()
    if args.action=='scope':scope();print('HPO scope passed; no model loaded')
    else:execute(args.permit,args.base_path,args.output)
