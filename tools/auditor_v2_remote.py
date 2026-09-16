"""Single classification-only run. No generation, refusal, or adapter training."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import auditor_v2_execution as c
import auditor_linear_core as old

ROOT = Path(__file__).resolve().parents[1]
D = ROOT/'tuning/auditor_v2_diagnostic'
OUT = ROOT/'evidence'
read, sha = c.read, c.sha


def write(name,value):
    OUT.mkdir(exist_ok=True)
    path=OUT/name
    with path.open('w',encoding='utf8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def append(name,value):
    with (OUT/name).open('a',encoding='utf8') as f:
        f.write(json.dumps(value,allow_nan=False)+'\n');f.flush()


def scope():
    manifest=read(ROOT/'execution_manifest.json')
    for name,digest in manifest['files'].items():
        path=(ROOT/name).resolve()
        assert path.is_relative_to(ROOT) and sha(path)==digest,name
    permit=read(ROOT/'training_authorization.json')
    assert permit['action']=='auditor-v2-one-head-classification-only' and permit['operator_authorized']
    assert permit['request_attachment']=='1c5d2f2a-3534-4fc2-a2b8-0ac4a12f3536'
    assert permit['updates']==200 and permit['trainable_parameters']==12292
    assert permit['hard_budget_usd']==1.50 and permit['soft_budget_usd']==.75 and permit['maximum_instances']==1
    assert permit['execution_manifest_sha256']==sha(ROOT/'execution_manifest.json')
    assert not any(permit[k] for k in ['backbone_updates','lora_updates','producer_execution','protected_access','generation','holdout_access'])
    spec=read(D/'experiment.json');records=read(D/'records.json');challenges=read(D/'challenges.json');baseline=read(D/'baseline.json')
    c.validate(records,spec,challenges,baseline)
    for name,digest in spec['adapter_hashes'].items():assert sha(ROOT/'adapter'/name)==digest
    return spec,records,challenges,baseline


def preflight():
    scope()
    assert sys.platform=='linux' and sys.version_info[:3]==(3,12,3)
    import torch
    for name,version in read(ROOT/'tuning/first_domain_agnostic_v1/dependency_lock.json')['packages'].items():
        assert importlib.metadata.version(name)==version,(name,version)
    assert torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported() and torch.version.cuda=='12.1'
    assert 'A10' in torch.cuda.get_device_name() and 'A100' not in torch.cuda.get_device_name()
    write('preflight.json',dict(passed=True,gpu=torch.cuda.get_device_name(),python=sys.version))


def acquire():
    spec,*_=scope()
    from huggingface_hub import snapshot_download
    expected=dict(spec['asset_hashes'],**{'model.safetensors':spec['base_weight_sha256']})
    start=time.time()
    path=Path(snapshot_download(spec['model_id'],revision=spec['revision'],allow_patterns=list(expected)))
    for name,digest in expected.items():assert sha(path/name)==digest,name
    write('acquisition.json',dict(path=str(path),seconds=time.time()-start,files=expected))


def execute():
    spec,records,challenges,baseline=scope()
    OUT.mkdir(exist_ok=True)
    # Exclusive durable intent is consumed before model loading; no resume/retry.
    with (OUT/'RUN_ONCE.json').open('x') as f:json.dump(dict(epoch=time.time()),f)
    budget=read(ROOT/'budget.json');stopped=[False]
    signal.signal(signal.SIGTERM,lambda *_:stopped.__setitem__(0,True))
    os.environ.update(USE_TORCH='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    import torch,numpy as np
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from peft import PeftModel
    from safetensors.torch import save_file
    def offline(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('Offline execution')
    sys.addaudithook(offline)
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.manual_seed(7);np.random.seed(7)
    done=0;feature_wall=0.;total_tokens=0
    def gate(phase):
        remaining=(2040-done)*max(1.,feature_wall/done if done else 1.)+90
        now=time.time()
        good=not stopped[0] and now+remaining<budget['workload_deadline_epoch']
        value=dict(epoch=now,phase=phase,features=done,projected_remaining_seconds=remaining,
                   estimated_usd=(now-budget['launch_epoch'])*budget['hourly_rate']/3600,
                   soft_reached=now>=budget['soft_epoch'],continue_run=good)
        append('budget_timeline.jsonl',value);write('progress.json',value)
        assert good,'Budget projection/deadline stop'
    sampler=subprocess.Popen([sys.executable,str(ROOT/'tuning/second_tuning_eval_runtime_v2_1/telemetry_worker.py'),
        '--pid',str(os.getpid()),'--output',str(OUT/'telemetry.jsonl'),'--stop-file',str(OUT/'telemetry.stop')])
    try:
        gate('load');begin=time.perf_counter()
        path=Path(read(OUT/'acquisition.json')['path'])
        tok=AutoTokenizer.from_pretrained(str(path),local_files_only=True,trust_remote_code=False)
        for r in records:
            assert tok(tok.decode(r['input_ids'],skip_special_tokens=False,clean_up_tokenization_spaces=False),add_special_tokens=False)['input_ids']==r['input_ids']
        base=AutoModelForCausalLM.from_pretrained(str(path),local_files_only=True,trust_remote_code=False,
            device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='eager')
        model=PeftModel.from_pretrained(base,str(ROOT/'adapter'),is_trainable=False)
        model.requires_grad_(False);model.eval()
        assert model.config.architectures==['LlamaForCausalLM'] and model.config.hidden_size==3072 and model.is_loaded_in_4bit
        assert all(not p.requires_grad and p.grad is None for p in model.parameters())
        def weights():
            h=hashlib.sha256()
            for name,p in model.state_dict().items():
                v=p.detach().cpu().contiguous();h.update(name.encode());h.update(str((v.dtype,tuple(v.shape))).encode());h.update(v.reshape(-1).view(torch.uint8).numpy().tobytes())
            return h.hexdigest()
        initial=weights();load_wall=time.perf_counter()-begin
        write('frozen_initial.json',dict(state_sha256=initial,backbone_trainable=0,lora_trainable=0,load_seconds=load_wall))
        features=[]
        for row in records:
            gate('features');begin=time.perf_counter()
            value=old.final_feature(torch,model,row['input_ids']);torch.cuda.synchronize()
            wall=time.perf_counter()-begin;feature_wall+=wall;done+=1;total_tokens+=len(row['input_ids'])
            assert value.dtype==np.float32 and np.isfinite(value).all();features.append(value)
            append('features.jsonl',dict(example_id=row['example_id'],sha256=hashlib.sha256(value.tobytes()).hexdigest(),
                prompt_sha256=row['prompt_sha256'],input_tokens=len(row['input_ids']),seconds=wall))
        features=np.stack(features);np.save(OUT/'features.npy',features,allow_pickle=False)
        mean,std,standard=c.d.standardized(np,features)
        for name,value in [('mean',mean),('std',std)]:np.save(OUT/(name+'.npy'),value,allow_pickle=False)
        write('normalization.json',dict(train_ids=[r['example_id'] for r in records[:1792]],dev_fit=False,ddof=0,clamp=1e-6,
            mean_sha256=sha(OUT/'mean.npy'),std_sha256=sha(OUT/'std.npy')))
        gate('head');x=torch.tensor(standard[:1792],device='cuda',dtype=torch.float32)
        labels=torch.tensor([c.CLASSES.index(r['relation']) for r in records[:1792]],device='cuda',dtype=torch.long)
        def callback(step,head,ce,reg):
            assert not stopped[0] and time.time()<budget['workload_deadline_epoch']
            if step in (0,200):save_file({k:v.detach().cpu().contiguous() for k,v in head.state_dict().items()},str(OUT/('head-'+str(step)+'.safetensors')))
            if step:append('head_training.jsonl',dict(step=step,ce=ce,regularization=reg,loss=ce+reg))
        begin=time.perf_counter();head=c.train(torch,x,labels,callback);torch.cuda.synchronize();head_wall=time.perf_counter()-begin
        weight=head.weight.detach().cpu().numpy();bias=head.bias.detach().cpu().numpy()
        train_logits=standard[:1792]@weight.T+bias
        with torch.inference_mode():final_ce=float(torch.nn.functional.cross_entropy(head(x),labels))
        train_metrics=c.metrics([r['relation'] for r in records[:1792]],[c.CLASSES[i] for i in train_logits.argmax(axis=1)])
        write('head_result.json',dict(parameters=12292,updates=200,seconds=head_wall,updates_per_second=200/head_wall,
            final_ce=final_ce,initial_ce=read_first_loss(),metrics=train_metrics,head_sha256=sha(OUT/'head-200.safetensors')))
        predictions={};eval_wall={}
        for group,start,end in [('external_dev',1792,1992),('historical_dev',1992,2040)]:
            gate(group);begin=time.perf_counter();logits=standard[start:end]@weight.T+bias
            for row,vector in zip(records[start:end],logits):
                label=c.CLASSES[int(vector.argmax())];predictions[row['example_id']]=label
                append(group+'.jsonl',dict(example_id=row['example_id'],logits=vector.tolist(),predicted=label))
            eval_wall[group]=time.perf_counter()-begin
        final=weights();assert initial==final
        assert all(not p.requires_grad and p.grad is None for p in model.parameters())
        write('frozen_final.json',dict(state_sha256=final,unchanged=True,backbone_trainable=0,lora_trainable=0))
        write('results.json',c.evaluate(records,predictions,challenges,baseline))
        write('performance.json',dict(load_seconds=load_wall,feature_seconds=feature_wall,feature_vectors=done,
            feature_tokens=total_tokens,input_tokens_per_second=total_tokens/feature_wall,head_seconds=head_wall,
            classification_seconds=eval_wall,peak_allocated_gib=torch.cuda.max_memory_allocated()/2**30,
            peak_reserved_gib=torch.cuda.max_memory_reserved()/2**30))
        write('status.json',dict(complete=True,verdict=read(OUT/'results.json')['verdict']))
    except Exception as exc:
        write('status.json',dict(complete=False,verdict='AUDITOR_V2_DIAGNOSTIC_INDETERMINATE',error_type=type(exc).__name__))
        raise
    finally:
        (OUT/'telemetry.stop').touch()
        try:sampler.wait(timeout=10)
        except subprocess.TimeoutExpired:sampler.terminate()


def read_first_loss():
    with (OUT/'head_training.jsonl').open() as f:return json.loads(f.readline())['ce']


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['scope','preflight','acquire','execute'])
    globals()[parser.parse_args().action]()
