"""Fresh classifier LoRA only. There is no autoregressive-generation entry point."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import auditor_classifier_lora_core as c

ROOT=Path(__file__).resolve().parents[1];D=ROOT/'tuning/auditor_classifier_lora';OUT=ROOT/'evidence'
read,sha=c.read,c.sha


def write(name,value):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def append(name,value):
    with (OUT/name).open('a',encoding='utf8') as f:f.write(json.dumps(value,allow_nan=False)+'\n');f.flush()


def scope():
    m=read(ROOT/'execution_manifest.json');permit=read(ROOT/'training_authorization.json')
    assert permit['action']=='fresh-auditor-classifier-lora-only' and permit['operator_authorized']
    assert permit['source_commit']==m['source_commit'] and permit['execution_manifest_sha256']==sha(ROOT/'execution_manifest.json')
    assert permit['request_attachment']=='775f836d-d349-488b-b201-66129661f3cc'
    assert permit['maximum_instances']==1 and permit['soft_budget_usd']==2 and permit['hard_budget_usd']==3
    assert permit['updates']==896 and permit['trainable_parameters']==c.LORA_PARAMS+c.HEAD_PARAMS
    assert not any(permit[k] for k in ['base_updates','historical_adapter_loaded','generation','holdout_access','producer_execution','protected_access'])
    assert not (ROOT/'adapter').exists()
    for name,digest in m['files'].items():
        p=(ROOT/name).resolve();assert p.is_relative_to(ROOT) and sha(p)==digest,name
        assert not any(x in name.lower() for x in ['checkpoint-120','producer','protected','holdout'])
    records=read(D/'records.json');spec=read(D/'experiment.json');challenges=read(D/'challenges.json');plan=read(D/'schedule.json')
    c.validate(records,spec,challenges,plan)
    assert sha(D/'records.json')==permit['records_sha256']
    return records,spec,challenges,plan


def preflight():
    scope();assert sys.platform=='linux' and platform.machine()=='x86_64' and sys.version_info[:3]==(3,12,3)
    import torch,psutil
    for name,version in read(ROOT/'tuning/first_domain_agnostic_v1/dependency_lock.json')['packages'].items():assert importlib.metadata.version(name)==version
    assert torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported() and torch.version.cuda=='12.1'
    assert 'A10' in torch.cuda.get_device_name() and 'A100' not in torch.cuda.get_device_name()
    assert torch.cuda.get_device_properties(0).total_memory>=22*2**30 and psutil.virtual_memory().available>=16*2**30
    assert shutil.disk_usage(ROOT).free>=20*2**30
    write('preflight.json',dict(passed=True,gpu=torch.cuda.get_device_name(),python=sys.version,disk_free=shutil.disk_usage(ROOT).free,ram_available=psutil.virtual_memory().available))


def acquire():
    _,spec,_,_=scope()
    from huggingface_hub import snapshot_download
    expected=dict(spec['asset_hashes'],**{'model.safetensors':spec['base_weight_sha256']});begin=time.time()
    path=Path(snapshot_download(spec['model_id'],revision=spec['revision'],allow_patterns=list(expected)))
    for name,digest in expected.items():assert sha(path/name)==digest,name
    write('acquisition.json',dict(path=str(path),files=expected,seconds=time.time()-begin))


def execute():
    records,spec,challenges,plan=scope();OUT.mkdir(exist_ok=True)
    with (OUT/'TRAINING_ATTEMPTED').open('x') as f:f.write('One authorized attempt; no resume\n')
    os.environ.update(USE_TORCH='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    import torch,numpy as np
    from transformers import AutoModelForCausalLM
    from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
    from safetensors.torch import save_file
    def offline(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('Offline workload')
    sys.addaudithook(offline)
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.manual_seed(7);torch.cuda.manual_seed_all(7);np.random.seed(7)
    budget=read(ROOT/'budget.json');stopped=[False];completed=0;eval_done=0;times=[];checkpoints=[]
    signal.signal(signal.SIGTERM,lambda *_:stopped.__setitem__(0,True))
    def gate(phase):
        now=time.time();remaining=c.remaining_seconds(completed,times,496-eval_done)
        good=not stopped[0] and now+remaining<budget['workload_deadline_epoch']
        value=dict(epoch=now,phase=phase,updates=completed,eval_rows=eval_done,remaining_seconds=remaining,
                   estimated_usd=(now-budget['launch_epoch'])*budget['hourly_rate']/3600,
                   projected_total_usd=(now-budget['launch_epoch']+remaining+600)*budget['hourly_rate']/3600,
                   soft_reached=now>=budget['soft_epoch'],continue_run=good)
        append('budget_timeline.jsonl',value);write('progress.json',value)
        assert good,'Remaining mandatory work and teardown cannot fit budget'
    sampler=subprocess.Popen([sys.executable,str(ROOT/'tuning/second_tuning_eval_runtime_v2_1/telemetry_worker.py'),'--pid',str(os.getpid()),'--output',str(OUT/'telemetry.jsonl'),'--stop-file',str(OUT/'telemetry.stop')])
    try:
        gate('load');begin=time.perf_counter();path=Path(read(OUT/'acquisition.json')['path'])
        base=AutoModelForCausalLM.from_pretrained(str(path),local_files_only=True,trust_remote_code=False,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='eager')
        assert base.config.architectures==['LlamaForCausalLM'] and base.config.hidden_size==3072 and base.is_loaded_in_4bit
        base.config.use_cache=False
        # This only freezes/casts base tensors and installs checkpointing hooks.
        base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':True})
        torch.manual_seed(7);torch.cuda.manual_seed_all(7)
        model=get_peft_model(base,LoraConfig(**spec['lora']))
        model.peft_config['default'].base_model_name_or_path=spec['model_id'];model.peft_config['default'].revision=spec['revision']
        torch.manual_seed(7);head=torch.nn.Linear(3072,4,device='cuda',dtype=torch.float32)
        with torch.no_grad():head.weight.zero_();head.bias.zero_()
        items=[dict(name=n,shape=list(p.shape),numel=p.numel(),dtype=str(p.dtype),trainable=p.requires_grad) for n,p in model.named_parameters()]
        items += [dict(name='head.'+n,shape=list(p.shape),numel=p.numel(),dtype=str(p.dtype),trainable=p.requires_grad) for n,p in head.named_parameters()]
        counts=c.inventory(items);assert list(model.peft_config)==['default']
        assert all(torch.count_nonzero(p).item()==0 for n,p in model.named_parameters() if '.lora_B.' in n)
        write('parameter_inventory.json',dict(items=items,counts=counts,historical_adapter_loaded=False))
        lora=[p for p in model.parameters() if p.requires_grad];head_params=list(head.parameters());params=lora+head_params
        opt=torch.optim.AdamW([dict(params=lora,lr=1e-4),dict(params=head_params,lr=1e-2)],betas=(.9,.999),eps=1e-8,weight_decay=0)
        assert len({id(p) for group in opt.param_groups for p in group['params']})==len(params)
        write('optimizer.json',dict(config=spec['optimizer'],groups=[dict(lr=g['lr'],parameters=sum(p.numel() for p in g['params'])) for g in opt.param_groups]))
        def state_hash(state):
            h=hashlib.sha256()
            def visit(v):
                if torch.is_tensor(v):
                    x=v.detach().cpu().contiguous();h.update(str((x.dtype,tuple(x.shape))).encode());h.update(x.reshape(-1).view(torch.uint8).numpy().tobytes())
                elif isinstance(v,dict):
                    for k in sorted(v,key=str):h.update(str(k).encode());visit(v[k])
                elif isinstance(v,(list,tuple)):
                    for x in v:visit(x)
                else:h.update(repr(v).encode())
            visit(state);return h.hexdigest()
        def frozen_hash():return state_hash({n:v for n,v in model.state_dict().items() if '.lora_' not in n})
        frozen=frozen_hash()
        def save(step):
            folder=OUT/f'checkpoint-{step}';folder.mkdir(exist_ok=False)
            model.save_pretrained(folder,safe_serialization=True)
            save_file({k:v.detach().cpu().contiguous() for k,v in head.state_dict().items()},str(folder/'head.safetensors'))
            value=dict(step=step,lora_sha256=sha(folder/'adapter_model.safetensors'),head_sha256=sha(folder/'head.safetensors'),config_sha256=sha(folder/'adapter_config.json'))
            write(f'checkpoint-{step}/identity.json',value);return value
        initial=save(0)
        write('initialization.json',dict(seed=7,head_zero=True,lora_B_zero=True,fresh_lora=True,historical_adapter_loaded=False,initial=initial,base_state_sha256=frozen,load_seconds=time.perf_counter()-begin))
        by={r['example_id']:r for r in records};train_ids={r['example_id'] for r in records[:1792]}
        def forward(row):
            ids=torch.tensor([row['input_ids']],dtype=torch.long,device='cuda')
            with torch.autocast('cuda',dtype=torch.bfloat16):
                hidden=model.get_base_model().model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,return_dict=True).last_hidden_state[0,-1]
            return head(hidden.float().unsqueeze(0)),hidden
        def evaluate(step):
            nonlocal eval_done
            gate('checkpoint_save');identity=save(step);assert frozen_hash()==frozen
            assert all(not p.requires_grad and p.grad is None for n,p in model.named_parameters() if '.lora_' not in n)
            rng=(torch.get_rng_state(),torch.cuda.get_rng_state_all());opt_before=state_hash(opt.state_dict())
            parameters_before=state_hash({n:p for n,p in model.named_parameters() if p.requires_grad})
            model.eval();head.eval();predictions={};features=[];timing={}
            with torch.inference_mode():
                for group,rows in [('external_dev',records[1792:1992]),('historical_dev',records[1992:])]:
                    start=time.perf_counter()
                    for row in rows:
                        gate('eval_'+str(step));logits,hidden=forward(row);vector=logits[0].float().cpu().numpy();value=hidden.detach().float().cpu().numpy().copy()
                        assert np.isfinite(vector).all() and np.isfinite(value).all()
                        prediction=c.CLASSES[int(vector.argmax())];predictions[row['example_id']]=prediction;features.append(value);eval_done+=1
                        append(f'checkpoint-{step}/{group}.jsonl',dict(example_id=row['example_id'],logits=vector.tolist(),predicted=prediction,feature_sha256=hashlib.sha256(value.tobytes()).hexdigest()))
                    timing[group]=time.perf_counter()-start
            np.save(OUT/f'checkpoint-{step}/dev_features.npy',np.stack(features),allow_pickle=False)
            assert opt_before==state_hash(opt.state_dict())
            assert parameters_before==state_hash({n:p for n,p in model.named_parameters() if p.requires_grad})
            assert all(p.grad is None for p in params)
            torch.set_rng_state(rng[0]);torch.cuda.set_rng_state_all(rng[1]);model.train();head.train()
            result=dict(identity,complete=True,metrics=c.evaluate(records,predictions,challenges),base_state_sha256=frozen,optimizer_unchanged_by_eval=True,parameters_unchanged_by_eval=True,gradients_during_eval=False,rng_restored=True,classification_seconds=timing)
            write(f'checkpoint-{step}/results.json',result);checkpoints.append(result)
        model.train();head.train();training_wall=0.
        for batch in plan:
            gate('train');start=time.perf_counter();opt.zero_grad(set_to_none=True);ce_sum=0.;reg_sum=0.
            assert batch['step']==completed+1 and set(batch['example_ids'])<=train_ids
            for identifier in batch['example_ids']:
                row=by[identifier];assert row['split']=='train'
                logits,_=forward(row);label=torch.tensor([c.CLASSES.index(row['relation'])],device='cuda')
                ce=torch.nn.functional.cross_entropy(logits,label);reg=.001*head.weight.square().mean()
                assert bool(torch.isfinite(ce+reg).item());((ce+reg)/4).backward();ce_sum+=float(ce.detach());reg_sum+=float(reg.detach())
            grad=torch.nn.utils.clip_grad_norm_(params,1.);assert bool(torch.isfinite(grad).item())
            opt.step();opt.zero_grad(set_to_none=True);torch.cuda.synchronize();wall=time.perf_counter()-start;times.append(wall);training_wall+=wall;completed+=1
            append('training.jsonl',dict(step=completed,epoch=batch['epoch'],example_ids=batch['example_ids'],examples_processed=completed*4,ce=ce_sum/4,regularization=reg_sum/4,loss=(ce_sum+reg_sum)/4,lrs=[g['lr'] for g in opt.param_groups],gradient_norm=float(grad),update_seconds=wall,training_seconds=training_wall,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30))
            if completed in (448,896):evaluate(completed)
        assert completed==896 and frozen_hash()==frozen
        result=c.select(checkpoints,completed)
        write('selection.json',result);write('frozen_final.json',dict(base_state_sha256=frozen,base_unchanged=True,historical_adapter_loaded=False))
        write('performance.json',dict(training_seconds=training_wall,median_update_seconds=float(np.median(times)),p95_update_seconds=float(np.percentile(times,95)),peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30))
        write('status.json',dict(result,complete=True,updates=completed,examples=completed*4,passes=2))
    except Exception as exc:
        write('status.json',dict(verdict='AUDITOR_CLASSIFIER_LORA_INDETERMINATE',diagnostic='RELATION_ADAPTATION_INDETERMINATE',complete=False,updates=completed,error_type=type(exc).__name__))
        raise
    finally:
        (OUT/'telemetry.stop').touch()
        try:sampler.wait(timeout=10)
        except subprocess.TimeoutExpired:sampler.terminate()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['scope','preflight','acquire','execute']);globals()[p.parse_args().action]()
