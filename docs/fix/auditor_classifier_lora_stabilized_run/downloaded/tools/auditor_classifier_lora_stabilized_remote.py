"""Step120-initialized classifier fork only. There is no autoregressive-generation entry point."""
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

ROOT=Path(__file__).resolve().parents[1];D=ROOT/'tuning/auditor_classifier_lora_fork';OUT=ROOT/'evidence'
read,sha=c.read,c.sha


def write(name,value):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def append(name,value):
    with (OUT/name).open('a',encoding='utf8') as f:f.write(json.dumps(value,allow_nan=False)+'\n');f.flush()


import auditor_classifier_lora_fork as fork
import auditor_classifier_lora_stable as stable
DATA=ROOT/'tuning/auditor_classifier_lora'

def scope():
    m=read(ROOT/'execution_manifest.json');permit=read(ROOT/'training_authorization.json')
    assert permit['action']=='step120-classifier-fork-only' and permit['operator_authorized']
    assert permit['source_commit']==m['source_commit'] and permit['execution_manifest_sha256']==sha(ROOT/'execution_manifest.json')
    assert permit['request_attachment']=='6234692b-4bf4-495e-952f-5d48d5219d6c'
    assert permit['maximum_instances']==1 and permit['soft_budget_usd']==2.5 and permit['hard_budget_usd']==3.5
    assert permit['updates']==896 and not any(permit[k] for k in ['generation','holdout_access','producer_execution','protected_access','base_updates'])
    for name,digest in m['files'].items():
        p=(ROOT/name).resolve();assert p.is_relative_to(ROOT) and sha(p)==digest,name
        assert not any(x in name.lower() for x in ['producer','protected','holdout','features.npy'])
    records=read(DATA/'records.json');spec=read(D/'experiment.json');challenges=read(DATA/'challenges.json');plan=read(DATA/'schedule.json')
    assert len(records)==2040 and [r['split'] for r in records]==['train']*1792+['external_dev']*200+['historical_dev']*48
    assert all(set(r)=={'example_id','split','relation','input_ids','prompt_sha256'} for r in records)
    assert plan==c.schedule([r['example_id'] for r in records[:1792]])
    assert spec['optimizer']['head_lr']==.001 and spec['optimizer']['lora_lr']==.0001 and spec['training']['updates']==896
    assert sha(DATA/'records.json')==permit['records_sha256']
    assert sha(D/'experiment.json')==permit['spec_sha256']
    for p,h in read(D/'runtime_bindings.json').items():assert sha(ROOT/p)==h
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
    with (OUT/'TRAINING_ATTEMPTED').open('x') as f:f.write('One authorized attempt, no resume\n')
    os.environ.update(USE_TORCH='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    import torch,numpy as np
    from transformers import AutoModelForCausalLM
    from peft import PeftModel,prepare_model_for_kbit_training
    from safetensors.torch import load_file,save_file
    def offline(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('Offline workload')
    sys.addaudithook(offline)
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.manual_seed(7);torch.cuda.manual_seed_all(7);np.random.seed(7)
    budget=read(ROOT/'budget.json');stopped=[False];completed=0;eval_done=0;times=[];checkpoints=[];preflight_rows=0;preflight_times=[]
    signal.signal(signal.SIGTERM,lambda *_:stopped.__setitem__(0,True))
    def gate(phase):
        now=time.time();per_row=max(.5,float(np.mean(preflight_times[-64:]))*1.3) if preflight_times else .5
        remaining=c.remaining_seconds(completed,times,496-eval_done)+max(0,1824-preflight_rows)*per_row
        good=not stopped[0] and now+remaining<budget['workload_deadline_epoch']
        value=dict(epoch=now,phase=phase,updates=completed,eval_rows=eval_done,preflight_rows=preflight_rows,remaining_seconds=remaining,
                   estimated_usd=(now-budget['launch_epoch'])*budget['hourly_rate']/3600,
                   projected_total_usd=(now-budget['launch_epoch']+remaining+600)*budget['hourly_rate']/3600,
                   soft_reached=now>=budget['soft_epoch'],continue_run=good)
        append('budget_timeline.jsonl',value);write('progress.json',value)
        assert good,'Mandatory remaining work plus reserve cannot fit'
    def emit(value):append('numerical_health.jsonl',value)
    sampler=subprocess.Popen([sys.executable,str(ROOT/'tuning/second_tuning_eval_runtime_v2_1/telemetry_worker.py'),'--pid',str(os.getpid()),'--output',str(OUT/'telemetry.jsonl'),'--stop-file',str(OUT/'telemetry.stop')])
    model=None;head=None;audit=None;opt=None
    try:
        gate('load');begin=time.perf_counter();path=Path(read(OUT/'acquisition.json')['path'])
        base=AutoModelForCausalLM.from_pretrained(str(path),local_files_only=True,trust_remote_code=False,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='eager')
        assert base.config.architectures==['LlamaForCausalLM'] and base.config.hidden_size==3072 and base.is_loaded_in_4bit
        base.config.use_cache=False
        base=prepare_model_for_kbit_training(base,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':True})
        receipt=read(D/'adapter_copy.json');reference=ROOT/receipt['source_path'];candidate=ROOT/receipt['fork_path']
        model=PeftModel.from_pretrained(base,str(reference),adapter_name=fork.REFERENCE,is_trainable=False)
        model.load_adapter(str(candidate),adapter_name=fork.CANDIDATE,is_trainable=False)
        head=torch.nn.Linear(3072,4,device='cuda',dtype=torch.float32)
        assets=spec['initialization_artifacts']
        head.load_state_dict(load_file(str(ROOT/assets['head-200.safetensors']['path']),device='cuda'))
        mean=torch.tensor(np.load(ROOT/assets['mean.npy']['path'],allow_pickle=False),device='cuda',dtype=torch.float32)
        std=torch.tensor(np.load(ROOT/assets['std.npy']['path'],allow_pickle=False),device='cuda',dtype=torch.float32)
        fork.freeze_slots(model,head)
        audit=stable.FrozenAudit(torch,model);frozen=audit.initial_hash
        write('initialization.json',dict(base_state_sha256=frozen,source_adapter_sha256=sha(reference/'adapter_model.safetensors'),fork_initializer_sha256=sha(candidate/'adapter_model.safetensors'),load_seconds=time.perf_counter()-begin))
        original_observe=fork.torch_observe
        def observe(*args):
            nonlocal preflight_rows
            gate('update0');t=time.perf_counter();v=original_observe(*args)
            preflight_times.append(time.perf_counter()-t);preflight_rows+=1
            row=args[-1]
            append('update0_predictions.jsonl',dict(sequence=preflight_rows,example_id=row['example_id'],active_adapters=model.active_adapters,logits=v['logits'].tolist(),predicted=c.CLASSES[int(v['logits'].argmax())]))
            return v
        fork.torch_observe=observe
        def parity_emit(v):append('update0_parity.jsonl',v)
        parity=fork.remote_preflight(torch,np,model,head,mean,std,records[:1792],read(D/'update0_controls.json'),read(D/'train_baseline.json'),parity_emit,ROOT,read(D/'runtime_bindings.json'),receipt)
        fork.torch_observe=original_observe
        assert preflight_rows==1824 and audit.unchanged(full=True)
        write('update0_summary.json',dict(passed=True,reference_removed=True,active_adapters=model.active_adapters,controls=16,train_rows=1792,optimizer_created=False,seconds=sum(preflight_times)))
        items=[dict(name=n,shape=list(p.shape),numel=p.numel(),dtype=str(p.dtype),trainable=p.requires_grad) for n,p in model.named_parameters()]
        items += [dict(name='head.'+n,shape=list(p.shape),numel=p.numel(),dtype=str(p.dtype),trainable=p.requires_grad) for n,p in head.named_parameters()]
        normalized=[dict(x,name=x['name'].replace('.classifier_fork.','.default.')) for x in items]
        counts=c.inventory(normalized);write('parameter_inventory.json',dict(items=items,counts=counts,reference_removed=True))
        health=stable.HealthGate(spec['numerical_gate']['mean_update_ce_ceiling'],emit)
        opt=parity.optimizer(torch,model,head,health)
        write('optimizer.json',dict(config=spec['optimizer'],groups=[dict(lr=g['lr'],parameters=sum(p.numel() for p in g['params'])) for g in opt.param_groups]))
        def save(step):
            folder=OUT/f'checkpoint-{step}';folder.mkdir(exist_ok=False)
            model.save_pretrained(folder,safe_serialization=True,selected_adapters=[fork.CANDIDATE])
            adapter=folder/fork.CANDIDATE
            assert (adapter/'adapter_model.safetensors').exists()
            save_file({k:v.detach().cpu().contiguous() for k,v in head.state_dict().items()},str(folder/'head.safetensors'))
            value=dict(step=step,lora_sha256=sha(adapter/'adapter_model.safetensors'),head_sha256=sha(folder/'head.safetensors'),config_sha256=sha(adapter/'adapter_config.json'),adapter_subdirectory=fork.CANDIDATE)
            write(f'checkpoint-{step}/identity.json',value);return value
        save(0);by={r['example_id']:r for r in records}
        def trainable_hash():
            h=hashlib.sha256()
            for n,p in list(model.named_parameters())+list(head.named_parameters()):
                if p.requires_grad:h.update(n.encode());h.update(p.detach().cpu().contiguous().numpy().tobytes())
            return h.hexdigest()
        def evaluate(step):
            nonlocal eval_done
            gate('checkpoint_save');identity=save(step);assert audit.unchanged(full=True)
            assert sha(reference/'adapter_model.safetensors')==fork.SOURCE_SHA
            rng=(torch.get_rng_state(),torch.cuda.get_rng_state_all());before=trainable_hash()
            model.eval();head.eval();predictions={};start=time.perf_counter()
            with torch.inference_mode():
                for group,rows in [('external_dev',records[1792:1992]),('historical_dev',records[1992:])]:
                    for row in rows:
                        gate('eval_'+str(step));ids=torch.tensor([row['input_ids']],dtype=torch.long,device='cuda')
                        with torch.autocast('cuda',dtype=torch.bfloat16):h=model.get_base_model().model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,return_dict=True).last_hidden_state[:,-1,:]
                        with torch.autocast('cuda',enabled=False):z=(h.float()-mean)/std;logits=head(z)
                        assert bool(torch.isfinite(h).all()) and bool(torch.isfinite(z).all()) and bool(torch.isfinite(logits).all())
                        vector=logits[0].cpu().numpy();pred=c.CLASSES[int(vector.argmax())];predictions[row['example_id']]=pred;eval_done+=1
                        append(f'checkpoint-{step}/{group}.jsonl',dict(example_id=row['example_id'],logits=vector.tolist(),predicted=pred))
            assert before==trainable_hash() and all(p.grad is None for p in list(model.parameters())+list(head.parameters()))
            torch.set_rng_state(rng[0]);torch.cuda.set_rng_state_all(rng[1]);model.train();head.train()
            result=dict(identity,complete=True,metrics=c.evaluate(records,predictions,challenges),base_state_sha256=frozen,parameters_unchanged_by_eval=True,rng_restored=True,classification_seconds=time.perf_counter()-start)
            write(f'checkpoint-{step}/results.json',result);checkpoints.append(result)
        for batch in plan:
            gate('train');start=time.perf_counter()
            fork.prospective_update(torch,model,head,mean,std,[by[i] for i in batch['example_ids']],batch,opt,health,lambda:audit.unchanged(full=batch['step'] in (20,448,896)))
            torch.cuda.synchronize();wall=time.perf_counter()-start;times.append(wall);completed=health.next_update-1
            append('training.jsonl',dict(step=completed,epoch=batch['epoch'],example_ids=batch['example_ids'],ce=health.update_means[-1],update_seconds=wall,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30))
            if completed==20:write('admission20.json',dict(passed=health.admitted20(),base_unchanged=audit.unchanged(full=True),dev_evaluated=False))
            if completed in (448,896):evaluate(completed)
        assert completed==896 and audit.unchanged(full=True) and sha(reference/'adapter_model.safetensors')==fork.SOURCE_SHA
        result=c.select(checkpoints,completed);write('selection.json',result)
        write('frozen_final.json',dict(base_state_sha256=frozen,base_unchanged=True,historical_adapter_unchanged=True,reference_removed=True))
        write('performance.json',dict(training_seconds=sum(times),median_update_seconds=float(np.median(times)),p95_update_seconds=float(np.percentile(times,95)),peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30))
        write('status.json',dict(result,complete=True,updates=completed))
    except Exception as exc:
        write('status.json',dict(verdict='AUDITOR_CLASSIFIER_LORA_INDETERMINATE',complete=False,updates=completed,error_type=type(exc).__name__,error_message=str(exc),preflight_rows=preflight_rows))
        # Preserve finite partial trainable state without replacing any valid checkpoint.
        if model is not None and head is not None:
            tensors={n:p.detach().cpu().contiguous() for n,p in model.named_parameters() if '.classifier_fork.' in n}
            tensors.update({'head.'+n:p.detach().cpu().contiguous() for n,p in head.named_parameters()})
            if tensors and all(bool(torch.isfinite(v).all()) for v in tensors.values()):save_file(tensors,str(OUT/'finite_partial_state.safetensors'))
        raise
    finally:
        (OUT/'telemetry.stop').touch()
        try:sampler.wait(timeout=10)
        except subprocess.TimeoutExpired:sampler.terminate()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['scope','preflight','acquire','execute']);globals()[p.parse_args().action]()


