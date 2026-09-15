"""Future single-role QLoRA entry. Never called by preparation or dry-run."""
import argparse
import importlib.metadata
import math
import os
from pathlib import Path
import random
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def authorization(path,action):
    require(path is not None,'Separate operator authorization required')
    permit=read(path)
    require(permit.get('experiment')==EXPERIMENT and permit.get('action')==action and permit.get('operator_authorized') is True,'Authorization scope mismatch')
    require(permit.get('experiment_freeze_sha256')==digest((HERE/'freeze.json').read_bytes()),'Authorization freeze mismatch')
    return permit

def runtime():
    require(sys.version_info[:3]==(3,12,3),'Exact Python 3.12.3 required')
    require(sys.platform=='linux','Training runtime must be Linux x86-64')
    import platform
    require(platform.machine()=='x86_64','Training architecture mismatch')
    for name,version in read(HERE/'dependency_lock.json')['packages'].items():
        require(importlib.metadata.version(name)==version,'Dependency version mismatch: '+name)
    import torch
    require(torch.cuda.is_available() and torch.cuda.device_count()==1,'Exactly one CUDA GPU required')
    require(torch.version.cuda=='12.1' and torch.cuda.is_bf16_supported(),'CUDA/BF16 requirement')
    return torch

def validate_modules(model,spec):
    found=dict(model.named_modules())
    for name in spec['architecture']['resolved_modules']:
        require(name in found and hasattr(found[name],'in_features') and hasattr(found[name],'out_features'),'Unresolved linear LoRA module: '+name)
    selected={name for name in found if name.rsplit('.',1)[-1] in MODULES}
    require(selected==set(spec['architecture']['resolved_modules']),'Unexpected target module population')
    require(not any(n.endswith(('lm_head','embed_tokens')) for n in selected),'Forbidden embedding/head adaptation')

def train(role,permit_path):
    frozen();permit=authorization(permit_path,'train')
    require(role in permit.get('roles',[]),'Role not authorized')
    manifest=read(HERE/'experiment.json')
    for k,v in manifest['environment'].items():
        require(os.environ.get(k)==v,'Set deterministic environment before process start: '+k)
    torch=runtime()
    from transformers import AutoModelForCausalLM
    from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
    from evaluation import LocalGenerator,evaluate_dev,freeze_selection
    spec=read(HERE/role/'experiment.json');args=spec['training']
    require(not (ROOT/'runs'/EXPERIMENT/'PROTECTED_ACCESS_CONSUMED.json').exists(),'Training closed after protected access')
    random.seed(7);torch.manual_seed(7);torch.cuda.manual_seed_all(7)
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False
    rows=load_rows(role,'train',gradient=True);tok=tokenizer(role)
    data=[encode(row,tok,spec['max_seq_length']) for row in rows]
    collate=TargetOnlyCollator(tok.pad_token_id,spec['max_seq_length'],tensor=True)
    # Reject resume/rerun before weights are opened; one fresh run directory per role.
    out=ROOT/spec['output_directory'];out.mkdir(parents=True,exist_ok=False)
    model=AutoModelForCausalLM.from_pretrained(PINS[role][0],revision=PINS[role][1],
        local_files_only=True,trust_remote_code=False,device_map={'':0},torch_dtype=torch.bfloat16,
        attn_implementation='eager')
    validate_modules(model,spec)
    require(model.config.model_type==spec['architecture']['family'],'Actual loaded architecture changed')
    require(getattr(model,'is_loaded_in_4bit',False),'Existing four-bit base required')
    actual_quant=model.config.quantization_config
    if hasattr(actual_quant,'to_dict'):actual_quant=actual_quant.to_dict()
    for key in ('bnb_4bit_quant_type','bnb_4bit_use_double_quant','bnb_4bit_compute_dtype'):
        require(actual_quant[key]==spec['quantization'][key],'Quantization changed: '+key)
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    model=get_peft_model(model,LoraConfig(**spec['lora']))
    model.peft_config['default'].base_model_name_or_path=PINS[role][0]
    model.peft_config['default'].revision=PINS[role][1]
    params=[p for n,p in model.named_parameters() if p.requires_grad]
    require(params and all('lora_' in n for n,p in model.named_parameters() if p.requires_grad),'Base weight update prohibited')
    require(sum(p.numel() for p in params)==spec['architecture']['adapter_parameters'],'Adapter parameter count mismatch')
    opt=torch.optim.AdamW(params,lr=args['learning_rate'],weight_decay=args['weight_decay'],
        betas=(args['adam_beta1'],args['adam_beta2']),eps=args['adam_epsilon'])
    maximum=args['max_steps'];warm=args['warmup_steps']
    schedule=torch.optim.lr_scheduler.LambdaLR(opt,lambda step:min((step+1)/warm,max(0.,(maximum-step)/max(1,maximum-warm))))
    results=[];losses=[];step=0
    for epoch in range(math.ceil(maximum/args['steps_per_epoch'])):
        order=list(range(len(data)));random.Random(7+epoch).shuffle(order)
        for start in range(0,len(order),args['gradient_accumulation']):
            group=order[start:start+args['gradient_accumulation']]
            model.train();model.config.use_cache=False;opt.zero_grad(set_to_none=True)
            loss_sum=0.
            for idx in group:
                batch={k:v.to(model.device) for k,v in collate([data[idx]]).items()}
                with torch.autocast('cuda',dtype=torch.bfloat16):loss=model(**batch).loss
                require(bool(torch.isfinite(loss).item()),'Nonfinite training loss')
                (loss/len(group)).backward();loss_sum+=float(loss.detach())
            torch.nn.utils.clip_grad_norm_(params,args['max_grad_norm'])
            opt.step();schedule.step();step+=1
            losses.append(dict(step=step,mean_loss=loss_sum/len(group),examples=len(group),diagnostic_only=True))
            if step in spec['checkpoint_steps']:
                ckpt=out/('checkpoint-'+str(step));model.save_pretrained(ckpt,safe_serialization=True)
                ident=adapter_identity(ckpt,role,step)
                model.eval();model.config.use_cache=True
                results.append(evaluate_dev(role,tok,spec,LocalGenerator(model,tok,spec),ident,out/('dev-'+str(step)+'.json')))
                write(out/'checkpoint_results.json',results);write(out/'train_loss_diagnostic.json',losses)
            if step>=maximum:break
        if step>=maximum:break
    require(step==maximum,'Bounded step schedule incomplete')
    freeze_selection(role,out,results,spec)
    write(out/'runtime.json',dict(python=sys.version,executable=sys.executable,torch=torch.__version__,
        cuda=torch.version.cuda,gpu=torch.cuda.get_device_name(),peak_vram=torch.cuda.max_memory_allocated(),optimizer_updates=step))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--role',choices=tuple(PINS),required=True);p.add_argument('--authorization',required=True)
    a=p.parse_args();train(a.role,a.authorization)
