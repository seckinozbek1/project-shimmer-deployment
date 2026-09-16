"""Future, separately authorized local executor. Never imported by dry-run.

No provider SDK, download, protected evaluation, resume, or automatic retry.
Authorization must bind one role/split and the exact reviewed release hash.
"""
import argparse
import importlib.metadata
import os
from pathlib import Path
import random
import sys
from runtime import *
from runner import plan, verify_freeze, select_checkpoint


def authorize(path,role,split,binding):
    permit=read(path)
    require(permit.get('experiment')=='second-domain-agnostic-v2' and permit.get('action')=='train', 'Wrong authorization scope')
    require(permit.get('operator_authorized') is True and permit.get('release_sha256')==binding,'Unbound training authorization')
    require(permit.get('role')==role and str(permit.get('split'))==split,'Role/fold authorization mismatch')


def adapter_identity(path,role,split,step,binding):
    hashes={name:sha((path/name).read_bytes()) for name in ('adapter_config.json','adapter_model.safetensors')}
    return dict(role=role,split=split,step=step,release_sha256=binding,files=hashes,sha256=sha(hashes))


def execute(role,split,authorization):
    binding=verify_freeze();authorize(authorization,role,split,binding)
    require(read(HERE/'freeze.json')['readiness']=='SECOND_TUNING_EXPERIMENT_DESIGN_READY','Release is not design-ready')
    receipts=[ROOT/'runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json',
        ROOT/'runs/second-domain-agnostic-v2/PROTECTED_ACCESS_CONSUMED.json',
        ROOT/'docs/fix/first_real_tuning_20260916/downloaded/runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json']
    require(not any(p.exists() for p in receipts),'Training closed after protected access')
    # All runtime/environment requirements are checked before a model is read.
    import platform
    require(sys.version_info[:3]==(3,12,3) and sys.platform=='linux' and platform.machine()=='x86_64','Pinned Linux Python 3.12.3 runtime required')
    lock=read(ROOT/'tuning/first_domain_agnostic_v1/dependency_lock.json')
    for name,version in lock['packages'].items():require(importlib.metadata.version(name)==version,'Dependency mismatch: '+name)
    required_env=read(ROOT/'tuning/first_domain_agnostic_v1/experiment.json')['environment']
    for name,value in required_env.items():require(os.environ.get(name)==value,'Set deterministic environment before launch: '+name)
    # runtime.py disables model backends for ordinary imports. Only this explicit
    # authorized entry enables torch, before importing Transformers itself.
    require('transformers' not in sys.modules,'Executor must start in a fresh process')
    os.environ['USE_TORCH']='1'
    import torch
    require(torch.cuda.is_available() and torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported(),'One BF16 CUDA device required')
    require(torch.version.cuda=='12.1','Pinned CUDA runtime required')
    from transformers import AutoModelForCausalLM
    from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
    spec=read(HERE/role/'experiment.json');run_plan=plan(role,split)
    rows={r['example_id']:r for r in read(HERE/'dataset.json')}
    tok=old.tokenizer(role)
    data={i:encode(rows[i],tok) for i in run_plan['train_ids']}
    maximum=spec['max_seq_length']
    require(all(len(e['input_ids'])<=maximum for e in data.values()),'Truncation forbidden')
    collate=old.TargetOnlyCollator(tok.pad_token_id,maximum,tensor=True)
    output=ROOT/run_plan['output_directory'];output.mkdir(parents=True,exist_ok=False)
    write(output/'RUN_BINDING.json',dict(release_sha256=binding,plan=run_plan))
    # Block network after local dependency/preflight checks, before model load.
    def offline(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('Local-only training')
    sys.addaudithook(offline)
    for name,expected in spec['base_weight_hashes'].items():
        base_path=old.cached(role)/name
        # Streaming avoids a multi-GB buffer and happens only in this separately
        # authorized future executor, never during the present dry-run.
        digest=__import__('hashlib').sha256()
        with base_path.open('rb') as stream:
            for block in iter(lambda:stream.read(8*1024*1024),b''):digest.update(block)
        require(digest.hexdigest()==expected,'Pinned base weight hash mismatch')
    args=spec['training'];random.seed(args['seed']);torch.manual_seed(args['seed']);torch.cuda.manual_seed_all(args['seed'])
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False
    model=AutoModelForCausalLM.from_pretrained(str(old.cached(role)),local_files_only=True,trust_remote_code=False,
        device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='eager')
    require(model.config.model_type==spec['architecture']['family'] and getattr(model,'is_loaded_in_4bit',False),'Wrong local base architecture/quantization')
    modules=dict(model.named_modules());selected={n for n in modules if n.rsplit('.',1)[-1] in old.MODULES}
    require(selected==set(spec['architecture']['resolved_modules']),'Target module mismatch')
    quant=model.config.quantization_config
    if hasattr(quant,'to_dict'):quant=quant.to_dict()
    for k in ('bnb_4bit_quant_type','bnb_4bit_use_double_quant','bnb_4bit_compute_dtype'):require(quant[k]==spec['quantization'][k],'Quantization mismatch')
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    model=get_peft_model(model,LoraConfig(**spec['lora']))
    model.peft_config['default'].base_model_name_or_path=spec['model_id'];model.peft_config['default'].revision=spec['revision']
    parameters=[p for n,p in model.named_parameters() if p.requires_grad]
    require(all('lora_' in n for n,p in model.named_parameters() if p.requires_grad),'Base parameter update forbidden')
    require(sum(p.numel() for p in parameters)==spec['architecture']['adapter_parameters'],'Adapter size mismatch')
    opt=torch.optim.AdamW(parameters,lr=args['learning_rate'],betas=(args['adam_beta1'],args['adam_beta2']),eps=args['adam_epsilon'],weight_decay=args['weight_decay'])
    total=args['max_steps'];warm=args['warmup_steps']
    scheduler=torch.optim.lr_scheduler.LambdaLR(opt,lambda s:min((s+1)/warm,max(0.,(total-s)/max(1,total-warm))))
    checkpoints=[];losses=[]
    for update in run_plan['optimizer_schedule']:
        model.train();model.config.use_cache=False;opt.zero_grad(set_to_none=True);loss_sum=0.
        for identifier in update['example_ids']:
            batch={k:v.to(model.device) for k,v in collate([data[identifier]]).items()}
            with torch.autocast('cuda',dtype=torch.bfloat16):loss=model(**batch).loss
            require(bool(torch.isfinite(loss).item()),'Nonfinite loss')
            (loss/update['loss_divisor']).backward();loss_sum+=float(loss.detach())
        torch.nn.utils.clip_grad_norm_(parameters,args['max_grad_norm']);opt.step();scheduler.step()
        step=update['step'];losses.append(dict(step=step,loss=loss_sum/update['loss_divisor']))
        if step not in spec['checkpoint_steps']:continue
        checkpoint=output/f'checkpoint-{step}';model.save_pretrained(checkpoint,safe_serialization=True)
        identity=adapter_identity(checkpoint,role,split,step,binding)
        model.eval();model.config.use_cache=True;results=[]
        for identifier in run_plan['validation_ids']:
            row=rows[identifier];prompt=tok.apply_chat_template(task_messages(row),tokenize=False,add_generation_prompt=True)
            inputs=tok(prompt,add_special_tokens=False,return_tensors='pt').to(model.device)
            with torch.inference_mode():ids=model.generate(**inputs,**spec['generation'],eos_token_id=spec['terminal_token_ids'],pad_token_id=tok.pad_token_id)[0,inputs['input_ids'].shape[1]:].tolist()
            terminal=bool(ids and ids[-1] in spec['terminal_token_ids']);raw=tok.decode(ids,skip_special_tokens=True)
            results.append(dict(example_id=identifier,identity=identity,prompt_sha256=sha(prompt.encode()),raw_output=raw,output_token_ids=ids,truncated=not terminal,metrics=score(row,raw,truncated=not terminal)))
        metrics=aggregate([r['metrics'] for r in results])
        write(output/f'validation-{step}.json',results)
        checkpoints.append(dict(step=step,adapter_sha256=identity['sha256'],metrics=metrics))
        write(output/'checkpoint_metrics.json',checkpoints);write(output/'loss_diagnostics.json',losses)
    try:chosen=select_checkpoint(role,checkpoints)
    except ValueError as exc:
        write(output/'SELECTION_REJECTED.json',dict(reason=str(exc),release_sha256=binding));return
    write(output/'SELECTION_FREEZE.json',dict(selected=chosen,release_sha256=binding,role=role,split=split))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role',choices=('producer','auditor'),required=True)
    parser.add_argument('--split',choices=('canonical','0','1','2','3','4'),required=True)
    parser.add_argument('--authorization',required=True)
    args=parser.parse_args();execute(args.role,args.split,args.authorization)
