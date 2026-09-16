"""One authorized linear-head candidate; frozen backbone/LoRA; no resume."""
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

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence'
D=ROOT/'tuning/auditor_linear_probe'
def boundary(event,args):
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        path=Path(os.fsdecode(args[0])).resolve()
        if 'protected' in path.name.lower() or 'producer' in {p.lower() for p in path.parts}:
            raise PermissionError('Producer/protected artifact forbidden')
        if path.is_relative_to(ROOT/'benchmark') and path.suffix not in ('.py','.pyc'):
            raise PermissionError('Benchmark data forbidden')
sys.addaudithook(boundary)
sys.path.insert(0,str(ROOT/'tools'))
import auditor_linear_core as c
sys.path.insert(0,str(ROOT/'tuning/second_domain_agnostic_v2'))
import runtime as r
sys.path.insert(0,str(ROOT/'tuning/auditor_canonical_execution'))
import eval_runtime as ev


def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def write(name,value):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf8') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def append(name,value):
    with (OUT/name).open('a',encoding='utf8') as f:f.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())


def scope():
    manifest=read(ROOT/'execution_manifest.json');permit=read(ROOT/'training_authorization.json')
    for name,digest in manifest['files'].items():assert sha(ROOT/name)==digest,name
    assert permit['action']=='auditor-linear-head-only' and permit['operator_authorized'] and permit['updates']==200
    assert permit['trainable_parameters']==15365 and permit['maximum_instances']==1 and permit['hard_budget_usd']==3
    assert permit['design_commit']=='25f7dc0cb1bd11d652debbec52940f84e9d64193'
    assert permit['backbone_updates']==permit['lora_updates']==permit['producer_execution']==permit['protected_access']==False
    spec=read(D/'experiment.json');rows=read(D/'dataset.json');split=read(D/'split.json');records=read(D/'records.json')
    assert len(rows)==300 and all(x['role']=='auditor' for x in rows)
    assert len(split['train'])==240 and len(split['validation'])==60 and not set(split['train'])&set(split['validation'])
    assert set(split['train']+split['validation'])=={x['example_id'] for x in rows}
    for group,n in [('train',48),('validation',12)]:assert {cl:sum(x['relation']==cl for x in rows if x['example_id'] in split[group]) for cl in c.CLASSES}=={cl:n for cl in c.CLASSES}
    assert sha(ROOT/'adapter/adapter_model.safetensors')=='733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6'
    assert sha(ROOT/'adapter/adapter_config.json')=='af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6'
    assert spec['model']['model_id']=='unsloth/Phi-3.5-mini-instruct-bnb-4bit'
    assert spec['model']['revision']=='5c20803aa197416f43fb455e55c85178775320cb'
    assert spec['model']['base_weight_hashes']=={'model.safetensors':'e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a'}
    assert sha(D/'dataset.json')==spec['original_dataset_sha256'] and sha(D/'split.json')==spec['original_split_sha256']
    assert sha(D/'binding.json')==permit['binding_sha256']
    assert spec['head']==dict(input_dim=3072,classes=c.CLASSES,parameters=15365,updates=200,lr=.01,regularization=.001,seed=7)
    return spec,rows,split,records


def preflight():
    scope();assert sys.platform=='linux' and sys.version_info[:3]==(3,12,3)
    os.environ['USE_TORCH']='1'
    import torch
    for name,version in read(ROOT/'tuning/first_domain_agnostic_v1/dependency_lock.json')['packages'].items():assert importlib.metadata.version(name)==version,(name,version)
    assert torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported() and torch.version.cuda=='12.1'
    assert 'A10' in torch.cuda.get_device_name() and 'A100' not in torch.cuda.get_device_name()
    write('preflight.json',dict(passed=True,gpu=torch.cuda.get_device_name(),gpu_count=1,python=sys.version))


def acquire():
    spec,*_=scope();assert read(OUT/'preflight.json')['passed']
    os.environ.update(HF_HUB_OFFLINE='0',TRANSFORMERS_OFFLINE='0')
    from huggingface_hub import snapshot_download
    model=spec['model'];expected=dict(model['asset_hashes'],**model['base_weight_hashes']);start=time.time()
    path=Path(snapshot_download(model['model_id'],revision=model['revision'],allow_patterns=list(expected)))
    for name,digest in expected.items():assert sha(path/name)==digest,name
    write('acquisition.json',dict(path=str(path),seconds=time.time()-start,files=expected))


def execute():
    spec,rows,split,records=scope();by={x['example_id']:x for x in rows};rec={x['example_id']:x for x in records}
    os.environ.update(USE_TORCH='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    import torch,numpy as np
    from transformers import AutoTokenizer,AutoModelForCausalLM,StoppingCriteria,StoppingCriteriaList
    from peft import PeftModel
    from safetensors.torch import save_file
    def offline(event,args):
        if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('Offline after acquisition')
    sys.addaudithook(offline)
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.manual_seed(7);np.random.seed(7)
    budget=read(ROOT/'budget.json');stopped=[False]
    signal.signal(signal.SIGTERM,lambda *_:stopped.__setitem__(0,True))
    outputs_done=0;features_done=0;feature_wall=0.;reason_wall=0.;reason_tokens=0;probe_wall=0.
    def gate(phase):
        elapsed=time.time()-budget['launch_epoch'];rate=reason_tokens/reason_wall if reason_wall and reason_tokens else 6.
        # Prospective per-row maximum reason allowances were tokenizer-bound locally.
        outputs_left=70-outputs_done
        seconds=(300-features_done)*max(1.,feature_wall/features_done if features_done else 1.)+outputs_left*(spec['max_reason_allowance']+16)/min(6.,rate)+60
        good=not stopped[0] and time.time()<budget['workload_deadline_epoch'] and time.time()+seconds<budget['workload_deadline_epoch']
        append('budget_timeline.jsonl',dict(epoch=time.time(),phase=phase,elapsed=elapsed,projected_remaining_seconds=seconds,continue_run=good,estimated_usd=elapsed*budget['hourly_rate']/3600))
        write('progress.json',dict(phase=phase,features=features_done,outputs=outputs_done,reason_tokens=reason_tokens,reason_seconds=reason_wall,projected_remaining_seconds=seconds))
        assert good,'Workload deadline/projection stop'
    watchdog=subprocess.Popen([sys.executable,str(Path(__file__)),'budget_watch','--pid',str(os.getpid())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    sampler=subprocess.Popen([sys.executable,str(ROOT/'tuning/second_tuning_eval_runtime_v2_1/telemetry_worker.py'),'--pid',str(os.getpid()),'--output',str(OUT/'telemetry.jsonl'),'--stop-file',str(OUT/'telemetry.stop')])
    model=None
    try:
        gate('load')
        path=Path(read(OUT/'acquisition.json')['path']);tok=AutoTokenizer.from_pretrained(str(path),local_files_only=True,trust_remote_code=False)
        for row in rows:
            rr=rec[row['example_id']];normalized,mapping=c.normalized_input(row['input'])
            for key,value in [('original',row['input']),('normalized',normalized)]:
                prompt=tok.apply_chat_template(r.task_messages(dict(role='auditor',input=value)),tokenize=False,add_generation_prompt=True)
                assert prompt==rr[key+'_prompt'] and tok(prompt,add_special_tokens=False)['input_ids']==rr[key+'_ids']
            assert mapping==rr['alias_map']
        base=AutoModelForCausalLM.from_pretrained(str(path),local_files_only=True,trust_remote_code=False,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='eager')
        model=PeftModel.from_pretrained(base,str(ROOT/'adapter'),is_trainable=False)
        model.requires_grad_(False);model.eval()
        assert model.config.model_type=='llama' and model.config.hidden_size==3072 and model.is_loaded_in_4bit
        assert all(not p.requires_grad and p.grad is None for p in model.parameters())
        def weights():
            h=hashlib.sha256()
            for name,param in model.state_dict().items():
                h.update(name.encode());v=param.detach().cpu().contiguous();h.update(str((v.dtype,tuple(v.shape))).encode());h.update(v.reshape(-1).view(torch.uint8).numpy().tobytes())
            return h.hexdigest()
        initial_weights=weights();initial_state=ev.parameter_state(model)
        write('frozen_initial.json',dict(state_sha256=initial_weights,trainable_backbone_parameters=0,trainable_lora_parameters=0,architecture=model.config.architectures,hidden_size=3072))
        write('context_preflight.json',ev.real_runtime_context_preflight(model,torch))
        features=[];ids=[x['example_id'] for x in rows]
        for identifier in ids:
            gate('feature_'+str(features_done));begin=time.perf_counter();value=c.final_feature(torch,model,rec[identifier]['normalized_ids']);torch.cuda.synchronize();wall=time.perf_counter()-begin
            assert np.isfinite(value).all();features.append(value);features_done+=1;feature_wall+=wall
            append('features.jsonl',dict(example_id=identifier,sha256=c.digest(value.tobytes()),shape=list(value.shape),dtype=str(value.dtype),seconds=wall,prompt_sha256=c.digest(rec[identifier]['normalized_prompt'].encode()),input_tokens=len(rec[identifier]['normalized_ids'])))
        features=np.stack(features);assert features.shape==(300,3072);np.save(OUT/'features.npy',features,allow_pickle=False)
        train_indices=[ids.index(i) for i in split['train']];dev_indices=[ids.index(i) for i in split['validation']]
        mean,std,standard=c.standardized(np,features,train_indices)
        np.save(OUT/'mean.npy',mean,allow_pickle=False);np.save(OUT/'std.npy',std,allow_pickle=False)
        write('normalization.json',dict(train_ids=split['train'],dev_fit=False,ddof=0,std_clamp=1e-6,dimension=3072,mean_sha256=sha(OUT/'mean.npy'),std_sha256=sha(OUT/'std.npy')))
        x=torch.tensor(standard[train_indices],device='cuda',dtype=torch.float32);labels=torch.tensor([c.CLASSES.index(by[i]['relation']) for i in split['train']],device='cuda',dtype=torch.long)
        head_start=time.perf_counter()
        def callback(step,head,ce,reg):
            assert not stopped[0] and time.time()<budget['workload_deadline_epoch']
            if step in (0,200):save_file({k:v.detach().cpu().contiguous() for k,v in head.state_dict().items()},str(OUT/f'head-{step}.safetensors'))
            if step:append('head_training.jsonl',dict(step=step,ce=ce,regularization=reg,loss=ce+reg,epoch=time.time()))
        write('optimizer.json',dict(name='Adam',lr=.01,betas=[.9,.999],eps=1e-8,weight_decay=0,updates=200,batch=240,objective='CE + 0.001 * mean(W**2)',train_ids=split['train'],parameters=15365))
        gate('head_training');head=c.train_head(torch,x,labels,callback);torch.cuda.synchronize();head_seconds=time.perf_counter()-head_start;head.eval();head.requires_grad_(False)
        with torch.inference_mode():
            ce,reg=c.objective(torch,head,x,labels);train_logits=head(x).cpu().tolist()
        train_pred=[c.CLASSES[max(range(5),key=lambda j:v[j])] for v in train_logits]
        write('head_train_result.json',dict(seconds=head_seconds,updates=200,updates_per_second=200/head_seconds,final_ce=float(ce),final_regularization=float(reg),logits=train_logits,metrics=c.classification([by[i]['relation'] for i in split['train']],train_pred),head_sha256=sha(OUT/'head-200.safetensors')))
        assert ev.parameter_state(model)==initial_state and weights()==initial_weights,'Frozen weights changed during head fit'
        generation=spec['generation']; eos=generation['eos_token_id']
        class Stop(StoppingCriteria):
            def __init__(self,start,kind):self.start=start;self.kind=kind
            def __call__(self,input_ids,scores,**kwargs):
                if stopped[0] or time.time()>=budget['workload_deadline_epoch']:return True
                out=input_ids[0,self.start:].tolist();text=tok.decode(out,skip_special_tokens=True)
                if self.kind=='probe':
                    try:return c.probe_state(text,bool(out and out[-1] in eos))!='waiting'
                    except ValueError:return True
                return c.parse_reason(text)['state']!='waiting'
        def generate(prompt_ids,maximum,kind):
            start=time.perf_counter();t=torch.tensor([prompt_ids],dtype=torch.long,device=model.device)
            settings=dict(generation,max_new_tokens=maximum)
            with ev.evaluation_state(model,torch):
                result=model.generate(input_ids=t,attention_mask=torch.ones_like(t),**settings,stopping_criteria=StoppingCriteriaList([Stop(len(prompt_ids),kind)]))
            torch.cuda.synchronize();wall=time.perf_counter()-start;out=result[0,len(prompt_ids):].tolist()
            assert not stopped[0] and time.time()<budget['workload_deadline_epoch'],'Interrupted generation'
            return out,wall
        def evaluate(identifier,phase):
            nonlocal outputs_done,reason_wall,reason_tokens,probe_wall
            gate(phase);rr=rec[identifier];row=by[identifier];index=ids.index(identifier);start=time.perf_counter()
            fresh=c.final_feature(torch,model,rr['normalized_ids']);assert np.array_equal(fresh,features[index]),'Frozen feature changed'
            standardized=(fresh-mean)/std
            with torch.inference_mode():logits=head(torch.tensor(standardized,device='cuda',dtype=torch.float32)).cpu().tolist()
            raw_class=c.CLASSES[max(range(5),key=lambda j:logits[j])]
            prefix_tokens,probe_seconds=generate(rr['original_ids'],16,'probe');probe_wall+=probe_seconds
            probe_text=tok.decode(prefix_tokens,skip_special_tokens=True);branch=c.probe_state(probe_text,bool(prefix_tokens and prefix_tokens[-1] in eos));assert branch!='waiting','Refusal prefix exhausted'
            routed=c.route(branch,raw_class);reason_ids=[];reason_raw='';forced='';seconds=0.;reason=None;parsed={};assembled=c.REFUSAL;stop='refusal';error=None
            if routed!='INSUFFICIENT_EVIDENCE':
                forced=c.forced_prefix(routed);forced_ids=tok(rr['original_prompt']+forced,add_special_tokens=False)['input_ids'];assert forced_ids[:len(rr['original_ids'])]==rr['original_ids']
                empty=c.assemble(row['input'],routed,'');allowance=192-(len(tok(empty,add_special_tokens=False)['input_ids'])+1)+2
                assert 0<allowance<=spec['max_reason_allowance']
                reason_ids,seconds=generate(forced_ids,allowance,'reason');reason_raw=tok.decode(reason_ids,skip_special_tokens=True);parsed=c.parse_reason(reason_raw);reason_wall+=seconds;reason_tokens+=len(reason_ids)
                if parsed['state']=='complete' and not any(v in eos for v in reason_ids):
                    reason=parsed['reason'];assembled=c.assemble(row['input'],routed,reason);stop='reason_quote'
                else:assembled='';stop='invalid_reason';error='Malformed, incomplete or prematurely terminated reason'
            final_tokens=tok(assembled,add_special_tokens=False)['input_ids']+[eos[-1]] if assembled else []
            if len(final_tokens)>192:stop='overflow';error='Full answer exceeds 192 tokens'
            raw=dict(example_id=identifier,normalized_prompt=rr['normalized_prompt'],alias_map=rr['alias_map'],feature_sha256=c.digest(fresh.tobytes()),standardized_sha256=c.digest(standardized.tobytes()),
                head_logits=logits,raw_head_class=raw_class,refusal_prefix_tokens=prefix_tokens,refusal_prefix_text=probe_text,refusal_veto=branch,final_routed_class=routed,
                original_prompt=rr['original_prompt'],forced_prefix=forced,generated_reason_tokens=reason_ids,raw_generated_reason=reason_raw,parsed_reason=parsed,
                required_refs=row['input']['required_refs'],assembled_json=assembled,final_token_ids=final_tokens,final_token_count=len(final_tokens),termination_source='deterministic_assembly',
                stop_reason=stop,error=error,probe_seconds=probe_seconds,reason_seconds=seconds,seconds=time.perf_counter()-start,
                memory={k:int(getattr(torch.cuda,k)()) for k in ['memory_allocated','memory_reserved','max_memory_allocated','max_memory_reserved']})
            append(phase+'.jsonl',raw) # Always fsync intermediate evidence before scorer.
            scored=dict(raw,metrics=r.score(row,assembled,error is not None));append(phase+'_scored.jsonl',scored);outputs_done+=1
            return scored
        controls=[]
        for pass_no in (1,2):controls.append([evaluate(i,'controls_'+str(pass_no)) for i in spec['control_ids']])
        ignore={'seconds','probe_seconds','reason_seconds','memory'}
        for a,b in zip(*controls):assert {k:v for k,v in a.items() if k not in ignore}=={k:v for k,v in b.items() if k not in ignore},'Control identity mismatch'
        write('controls_passed.json',dict(passed=True,pairs=5,ids=spec['control_ids']))
        begin=time.perf_counter();full=[evaluate(i,'full_dev') for i in split['validation']];dev_wall=time.perf_counter()-begin
        metrics=r.aggregate([x['metrics'] for x in full]);head_metrics=c.classification([by[x['example_id']]['relation'] for x in full],[x['raw_head_class'] for x in full]);nr=c.nonregression(metrics)
        passed=r.selection_pass(metrics,spec['model']['selection_gates']) and all(nr.values());verdict='AUDITOR_LINEAR_PROBE_PASS' if passed else 'AUDITOR_LINEAR_PROBE_FAIL'
        assert len(full)==60 and outputs_done==70
        final_weights=weights();assert initial_weights==final_weights and ev.parameter_state(model)==initial_state
        for name,dig in spec['adapter_hashes'].items():assert sha(ROOT/'adapter'/name)==dig
        write('frozen_final.json',dict(state_sha256=final_weights,unchanged=initial_weights==final_weights,backbone_trainable=0,lora_trainable=0,parameter_state_unchanged=True))
        write('metrics.json',dict(raw_head=head_metrics,final_auditor=metrics,nonregression=nr))
        write('status.json',dict(verdict=verdict,updates=200,features=300,dev_rows=60,feature_seconds=feature_wall,feature_input_tokens=sum(len(x['normalized_ids']) for x in records),head_seconds=head_seconds,
            full_dev_seconds=dev_wall,reason_seconds=reason_wall,reason_generated_tokens=reason_tokens,probe_seconds=probe_wall,head_sha256=sha(OUT/'head-200.safetensors'),final_frozen_weights_sha256=final_weights))
    except BaseException as exc:
        write('status.json',dict(verdict='AUDITOR_LINEAR_PROBE_INDETERMINATE',error_type=type(exc).__name__,reason=str(exc),features=features_done,outputs=outputs_done))
        raise
    finally:
        (OUT/'telemetry.stop').touch();sampler.wait(timeout=10);watchdog.terminate();watchdog.wait(timeout=10)


def budget_watch():
    budget=read(ROOT/'budget.json');pid=int(sys.argv[sys.argv.index('--pid')+1])
    while time.time()<budget['workload_deadline_epoch']:
        try:os.kill(pid,0)
        except ProcessLookupError:return
        time.sleep(1)
    write('budget_stop.json',dict(epoch=time.time(),reason='Minute50 workload cutoff'))
    os.kill(pid,signal.SIGTERM)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['scope','preflight','acquire','execute','budget_watch']);parser.add_argument('--pid',type=int);args=parser.parse_args();OUT.mkdir(exist_ok=True)
    if args.action=='execute':
        with (OUT/'TRAINING_ATTEMPTED').open('x'):pass
    globals()[args.action]()
