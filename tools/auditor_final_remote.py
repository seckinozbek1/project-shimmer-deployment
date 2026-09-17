"""One offline final training stage, then a separately gated offline evaluation stage."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import signal
import sys
import time
from pathlib import Path
import auditor_final_core as f
import auditor_classifier_lora_core as c

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'tuning/auditor_final';OUT=ROOT/'evidence'


def write(name,value):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf8') as stream:
        json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())


def emit(value):
    with (OUT/'events.jsonl').open('a',encoding='utf8') as stream:stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush()


def scope():
    seal=c.read(D/'seal.json')
    for name,digest in seal['files'].items():
        p=(ROOT/name).resolve();f.require(p.is_relative_to(ROOT) and c.sha(p)==digest,'sealed file '+name)
    f.require(c.read(D/'experiment.json')==f.config(),'frozen final configuration')
    rows=f.train_rows(c.read(D/'records_train_only.json'))
    f.require(c.read(D/'schedule.json')==c.schedule([r['example_id'] for r in rows]),'two-pass schedule')
    return rows,c.read(D/'runtime_contract.json')


def authorize():
    permit=c.read(ROOT/'training_authorization.json');manifest=c.read(ROOT/'execution_manifest.json')
    f.require(permit['operator_authorized'] and permit['action']=='auditor-final-training-evaluation','final authorization')
    f.require(permit['source_commit']==manifest['source_commit'] and permit['execution_manifest_sha256']==c.sha(ROOT/'execution_manifest.json'),'execution identity')
    f.require(permit['seal_sha256']==c.sha(D/'seal.json') and permit['instances']==permit['gpus']==1,'one instance sealed workflow')
    f.require(permit['updates']==896 and permit['soft_budget_usd']==5 and permit['hard_budget_usd']==7,'caps')
    f.require(permit['params']==f.PARAMS and permit['evaluation_after_updates']==896,'frozen hyperparameters/evaluation gate')
    f.require(permit['launch_epoch']<permit['workload_deadline_epoch']<=permit['launch_epoch']+7/permit['hourly_rate']*3600-600,'teardown reserve')
    for name,digest in manifest['files'].items():f.require(c.sha(ROOT/name)==digest,'execution manifest binding')
    return permit


def runtime():
    rows,contract=scope();permit=authorize()
    f.require(sys.platform=='linux' and platform.machine()=='x86_64' and platform.python_version()==contract['python'],'exact runtime')
    for name,version in contract['packages'].items():f.require(importlib.metadata.version(name)==version,'package '+name)
    os.environ.update(USE_TORCH='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
    import torch
    import numpy as np
    f.require(torch.cuda.device_count()==1 and 'A10' in torch.cuda.get_device_name() and 'A100' not in torch.cuda.get_device_name(),'one A10')
    f.require(torch.cuda.is_bf16_supported() and torch.version.cuda==contract['cuda_runtime'],'CUDA/BF16')
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.manual_seed(7);torch.cuda.manual_seed_all(7);np.random.seed(7)
    return rows,contract,permit,torch,np


def load_base(torch,contract):
    from transformers import AutoModelForCausalLM
    from peft import prepare_model_for_kbit_training
    p=ROOT/'base_model'
    for name,digest in dict(contract['asset_hashes'],**{'model.safetensors':contract['base_weight_sha256']}).items():f.require(c.sha(p/name)==digest,'base asset')
    base=AutoModelForCausalLM.from_pretrained(str(p),local_files_only=True,trust_remote_code=False,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='eager')
    f.require(base.config.architectures==['LlamaForCausalLM'] and base.config.hidden_size==3072 and base.is_loaded_in_4bit,'base architecture')
    quant=base.config.quantization_config
    if hasattr(quant,'to_dict'):quant=quant.to_dict()
    f.require(quant['bnb_4bit_quant_type']=='nf4','NF4');base.config.use_cache=False
    return prepare_model_for_kbit_training(base,use_gradient_checkpointing=True,gradient_checkpointing_kwargs={'use_reentrant':True})


class Budget:
    def __init__(self,permit):
        self.permit=permit;self.stopped=False;self.updates=0;self.times=[];self.features=0;self.evaluations=0;self.phase='initialization'
        signal.signal(signal.SIGTERM,lambda *_:setattr(self,'stopped',True))

    def check(self,phase,remaining=None):
        self.phase=phase;now=time.time()
        if remaining is None:
            rate=max(6.,sum(self.times[-32:])/len(self.times[-32:])*1.35) if self.times else 6.
            remaining=(896-self.updates)*rate+max(0,1792-self.features)*.65+max(0,496-self.evaluations)*.65+180
        p=self.permit;good=not self.stopped and now+remaining<p['workload_deadline_epoch']
        receipt=dict(epoch=now,phase=phase,updates=self.updates,feature_rows=self.features,eval_rows=self.evaluations,remaining_seconds=remaining,
            estimated_usd=(now-p['launch_epoch'])*p['hourly_rate']/3600,projected_with_reserve_usd=(now-p['launch_epoch']+remaining+900)*p['hourly_rate']/3600,
            soft_reached=(now-p['launch_epoch'])*p['hourly_rate']/3600>=5,continue_run=good)
        write('progress.json',receipt)
        f.require(good,'genuine budget/resource stop; preserve evidence, no retry')


def training():
    OUT.mkdir(exist_ok=True)
    with (OUT/'TRAINING_ATTEMPTED').open('x') as stream:stream.write('One authorized final attempt; no resume/retry.\n')
    boundary=f.Boundary(ROOT);boundary.install();completed=0;budget=None
    try:
        rows,contract,permit,torch,np=runtime();budget=Budget(permit);budget.check('load')
        from peft import PeftModel
        from safetensors.torch import save_file
        import auditor_classifier_lora_fork as fork
        import auditor_classifier_lora_current_core as current
        import auditor_classifier_lora_stable as stable
        import auditor_optuna_hpo as h
        from auditor_final_backend import FinalBackend
        base=load_base(torch,contract);reference=D/'canonical_adapter'
        f.require(c.sha(reference/'adapter_model.safetensors')==fork.SOURCE_SHA and c.sha(reference/'adapter_config.json')==fork.CONFIG_SHA,'canonical source')
        model=PeftModel.from_pretrained(base,str(reference),adapter_name=fork.REFERENCE,is_trainable=False)
        head=torch.nn.Linear(3072,4,device='cuda',dtype=torch.float32);fork.freeze_slots(model,head)
        inventory=fork.inventory(reference/'adapter_model.safetensors');current.verify_adapter(torch,model,fork.REFERENCE,inventory)
        audit=stable.FrozenAudit(torch,model);f.require(audit.initial_hash==contract['base_state_sha256'],'runtime base function')
        write('initialization.json',dict(base_state_sha256=audit.initial_hash,canonical_adapter_sha256=fork.SOURCE_SHA,fresh_features=True,hpo_initializer_loaded=False))
        features=np.lib.format.open_memmap(OUT/'train_features.npy',mode='w+',dtype=np.float32,shape=(1792,3072))
        begin=time.perf_counter()
        for i,row in enumerate(rows):
            budget.check('fresh_train_features')
            with torch.inference_mode():
                ids=torch.tensor([row['input_ids']],device='cuda',dtype=torch.long)
                with torch.autocast('cuda',dtype=torch.bfloat16):hidden=model.get_base_model().model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,return_dict=True).last_hidden_state[0,-1]
                vector=hidden.float().cpu().numpy().copy()
            f.require(vector.shape==(3072,) and np.isfinite(vector).all(),'finite TRAIN hidden')
            features[i]=vector;features.flush();budget.features=i+1
            emit(dict(event='feature',index=i,example_id=row['example_id'],token_sha256=fork.token_hash(row['input_ids']),feature_sha256=hashlib.sha256(vector.tobytes()).hexdigest(),norm=float(np.linalg.norm(vector.astype(np.float64)))))
        mean_np,std_np=current.normalize(np,features,rows)
        np.save(OUT/'mean.npy',mean_np,allow_pickle=False);np.save(OUT/'std.npy',std_np,allow_pickle=False)
        write('normalization.json',dict(train_rows=1792,dev_fit_rows=0,fresh_feature_passes=1,feature_seconds=time.perf_counter()-begin,
            features_sha256=c.sha(OUT/'train_features.npy'),mean_sha256=c.sha(OUT/'mean.npy'),std_sha256=c.sha(OUT/'std.npy'),ddof=0,std_clamp=1e-6,
            std_quantiles={str(q):float(np.percentile(std_np,q)) for q in [0,1,5,50,95,100]},clamped_dimensions=int((std_np<=1e-6).sum())))
        z=np.asarray((features-mean_np)/std_np,dtype=np.float32);x=torch.tensor(z,device='cuda');labels=torch.tensor([c.CLASSES.index(r['relation']) for r in rows],device='cuda')
        def callback(step,head,ce,reg):
            budget.check('fresh_head_fit');f.require(all(not p.requires_grad and p.grad is None for p in model.parameters()),'frozen head-fit backbone')
            if step:emit(dict(event='head_fit',update=step,ce=ce,regularization=reg,train_rows=1792))
        head=current.fit_head(torch,x,labels,callback)
        with torch.inference_mode():
            fitted=head(x);fit_ce=float(torch.nn.functional.cross_entropy(fitted,labels));cached=fitted.cpu().numpy().copy()
        save_file({k:v.detach().cpu().contiguous() for k,v in head.state_dict().items()},str(OUT/'head-200.safetensors'))
        metrics=h.metrics([r['relation'] for r in rows],[c.CLASSES[i] for i in cached.argmax(axis=1)], [fit_ce]*1792)
        write('head_fit.json',dict(updates=200,rows=1792,ce=fit_ce,metrics=metrics,deterministic_repeat_forward_gradients_all_200=True,head_sha256=c.sha(OUT/'head-200.safetensors')))
        del x,labels,fitted
        model.load_adapter(str(reference),adapter_name=fork.CANDIDATE,is_trainable=False);fork.freeze_slots(model,head)
        current.verify_adapter(torch,model,fork.CANDIDATE,inventory)
        mean=torch.tensor(mean_np,device='cuda');std=torch.tensor(std_np,device='cuda')
        controls=c.read(D/'controls.json')['example_ids'];by={r['example_id']:r for r in rows};index={r['example_id']:i for i,r in enumerate(rows)}
        observed={}
        for slot in [fork.REFERENCE,fork.CANDIDATE]:
            model.set_adapter(slot);fork.freeze_slots(model,head);observed[slot]=[]
            for identifier in controls:
                budget.check('control_parity');v=fork.torch_observe(torch,np,model,head,mean,std,by[identifier]);observed[slot].append(v)
                f.require(np.allclose(v['hidden'],features[index[identifier]],rtol=1e-4,atol=2e-4) and np.allclose(v['logits'],cached[index[identifier]],rtol=1e-4,atol=2e-4),'fresh extraction/head consistency')
        for i,identifier in enumerate(controls):
            a,b=(observed[slot][i] for slot in [fork.REFERENCE,fork.CANDIDATE])
            errors={k:float(np.max(np.abs(a[k]-b[k]))) for k in ['hidden','normalized','logits']}
            f.require(all(np.allclose(a[k],b[k],rtol=1e-4,atol=2e-4) for k in errors),'reference/fork parity')
            emit(dict(event='control_parity',example_id=identifier,max_errors=errors))
        model.delete_adapter(fork.REFERENCE);model.set_adapter(fork.CANDIDATE);fork.freeze_slots(model,head)
        f.require(set(model.peft_config)=={fork.CANDIDATE} and audit.unchanged(full=True),'clean isolated fork')
        backend=FinalBackend(torch,np,model,head,mean,std,rows,dict(assignments=[dict(example_id=r['example_id'],split='inner_train') for r in rows]),audit,emit)
        initial=backend.state_hash();backend.clear_gradients();backend.set_dropout(.05);backend.seed(7);backend.new_optimizer(f.PARAMS)
        f.require(backend.state_hash()==initial and backend.gradients_empty() and backend.optimizer_empty(),'fresh optimizer/gradient/state')
        write('optimizer_initial.json',dict(state_empty=True,gradients_empty=True,seed=7,initial_parameter_sha256=initial,params=f.PARAMS,groups=[dict(lr=g['lr'],numel=sum(p.numel() for p in g['params'])) for g in backend.opt.param_groups]))
        gate=h.Stability(fit_ce);write('stability_thresholds.json',dict(baseline_ce=fit_ce,mean_ceiling=gate.mean_ceiling,micro_ceiling=gate.micro_ceiling))
        def optimizer_receipt(step):
            states=list(backend.opt.state.values());steps=[int(s['step'].item()) for s in states]
            f.require(len(states)==450 and set(steps)=={step},'optimizer step correctness')
            f.require(all(bool(torch.isfinite(s[k]).all()) for s in states for k in ['exp_avg','exp_avg_sq']),'finite Adam state')
            return dict(parameters_with_state=len(states),min_step=min(steps),max_step=max(steps),moments_finite=True)
        def save(step):
            folder=OUT/f'checkpoint-{step}';folder.mkdir(exist_ok=False)
            model.save_pretrained(folder,safe_serialization=True,selected_adapters=[fork.CANDIDATE])
            save_file({k:v.detach().cpu().contiguous() for k,v in head.state_dict().items()},str(folder/'head.safetensors'))
            identity=dict(step=step,lora_sha256=c.sha(folder/fork.CANDIDATE/'adapter_model.safetensors'),config_sha256=c.sha(folder/fork.CANDIDATE/'adapter_config.json'),head_sha256=c.sha(folder/'head.safetensors'),mean_sha256=c.sha(OUT/'mean.npy'),std_sha256=c.sha(OUT/'std.npy'),base_state_sha256=audit.initial_hash)
            write(f'checkpoint-{step}/identity.json',identity)
            if step:write(f'checkpoint-{step}/optimizer_state.json',optimizer_receipt(step))
        save(0)
        control=controls[0];diag=[0,1,2,5,10,20,40,80,160,224,448,672,896]
        emit(dict(event='diagnostic',update=0,**backend.diagnostic(control,0,gate)['telemetry']))
        for batch in c.read(D/'schedule.json'):
            budget.check('training');step=batch['step'];backend.set_lrs(f.lr(step),f.PARAMS['head_lr']);start=time.perf_counter()
            receipt=backend.update(batch['example_ids'],step,gate);torch.cuda.synchronize();wall=time.perf_counter()-start
            completed=step;budget.updates=step;budget.times.append(wall)
            emit(dict(event='update',update=step,epoch=batch['epoch'],example_ids=batch['example_ids'],seconds=wall,**receipt))
            if step in diag:emit(dict(event='diagnostic',update=step,**backend.diagnostic(control,step,gate)['telemetry']))
            if step in [448,896]:save(step)
        f.require(completed==896 and audit.unchanged(full=True) and c.sha(reference/'adapter_model.safetensors')==fork.SOURCE_SHA,'completed unchanged base/source')
        write('TRAINING_COMPLETE.json',dict(complete=True,updates=896,checkpoints=[448,896],epoch=time.time(),source_commit=permit['source_commit'],seal_sha256=c.sha(D/'seal.json'),evaluation_rows_opened=0))
        write('training_status.json',dict(complete=True,updates=896,training_seconds=sum(budget.times),median_update_seconds=float(np.median(budget.times)),max_memory_gib=torch.cuda.max_memory_allocated()/2**30))
    except Exception as exc:
        write('training_status.json',dict(complete=False,updates=completed,error_type=type(exc).__name__,error=str(exc)))
        raise
    finally:write('training_data_access.json',boundary.receipt)


def evaluation():
    completion=c.read(OUT/'TRAINING_COMPLETE.json');f.admit_evaluation(completion)
    with (OUT/'EVALUATION_ATTEMPTED').open('x') as stream:stream.write('Evaluate saved448/896 only, after896.\n')
    boundary=f.Boundary(ROOT,evaluation=True);boundary.install()
    try:
        train,contract,permit,torch,np=runtime()
        f.require(completion['source_commit']==permit['source_commit'] and completion['seal_sha256']==c.sha(D/'seal.json'),'completed execution identity')
        budget=Budget(permit);budget.features=1792;budget.updates=896;budget.check('evaluation_load')
        for name,digest in f.EVAL_HASHES.items():f.require(c.sha(ROOT/'evaluation_payload'/name)==digest,'post-training frozen evaluation payload')
        rows=c.read(ROOT/'evaluation_payload/records.json');challenges=c.read(ROOT/'evaluation_payload/challenges.json');f.validate_evaluation(rows,challenges,train)
        boundary.receipt.update(external_dev_rows=200,historical_dev_rows=48,shorter_rows=75,longer_rows=75,evaluation_opened_after_updates=896,evaluation_open_epoch=time.time())
        from peft import PeftModel
        from safetensors.torch import load_file
        import auditor_classifier_lora_fork as fork
        import auditor_classifier_lora_stable as stable
        base=load_base(torch,contract);head=torch.nn.Linear(3072,4,device='cuda',dtype=torch.float32)
        mean=torch.tensor(np.load(OUT/'mean.npy',allow_pickle=False),device='cuda');std=torch.tensor(np.load(OUT/'std.npy',allow_pickle=False),device='cuda')
        model=None;results=[]
        for step in [448,896]:
            folder=OUT/f'checkpoint-{step}';identity=c.read(folder/'identity.json')
            for p,k in [(folder/fork.CANDIDATE/'adapter_model.safetensors','lora_sha256'),(folder/fork.CANDIDATE/'adapter_config.json','config_sha256'),(folder/'head.safetensors','head_sha256'),(OUT/'mean.npy','mean_sha256'),(OUT/'std.npy','std_sha256')]:f.require(c.sha(p)==identity[k],'checkpoint identity')
            if model is None:model=PeftModel.from_pretrained(base,str(folder/fork.CANDIDATE),adapter_name=fork.CANDIDATE,is_trainable=False)
            else:
                model.delete_adapter(fork.CANDIDATE);model.load_adapter(str(folder/fork.CANDIDATE),adapter_name=fork.CANDIDATE,is_trainable=False)
            model.set_adapter(fork.CANDIDATE);head.load_state_dict(load_file(str(folder/'head.safetensors'),device='cuda'));fork.freeze_slots(model,head)
            audit=stable.FrozenAudit(torch,model);f.require(audit.initial_hash==contract['base_state_sha256'],'evaluation frozen base')
            predictions=[]
            with torch.inference_mode():
                for row in rows[1792:]:
                    budget.check('evaluate_'+str(step));ids=torch.tensor([row['input_ids']],device='cuda',dtype=torch.long)
                    with torch.autocast('cuda',dtype=torch.bfloat16):hidden=model.get_base_model().model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,return_dict=True).last_hidden_state[:,-1,:]
                    with torch.autocast('cuda',enabled=False):
                        z=(hidden.float()-mean)/std;logits=head(z);ce=torch.nn.functional.cross_entropy(logits,torch.tensor([c.CLASSES.index(row['relation'])],device='cuda'))
                    f.require(all(bool(torch.isfinite(v).all()) for v in [hidden,z,logits,ce]),'nonfinite evaluation')
                    vector=logits[0].cpu().tolist();p=dict(example_id=row['example_id'],split=row['split'],expected=row['relation'],logits=vector,predicted=c.CLASSES[int(logits.argmax())],ce=float(ce),train_mode=False)
                    predictions.append(p);emit(dict(event='evaluation',checkpoint=step,**p));budget.evaluations+=1
            f.require(audit.unchanged(full=True) and all(p.grad is None for p in model.parameters()) and all(p.grad is None for p in head.parameters()),'evaluation mutation')
            result=dict(step=step,identity=identity,metrics=f.evaluate(rows,predictions,challenges),evaluation_after_updates=896)
            write(f'checkpoint-{step}/predictions.json',predictions);write(f'checkpoint-{step}/results.json',result);results.append(result)
        selection=f.select(results);write('selection.json',selection)
        write('status.json',dict(selection,complete=True,updates=896,eval_forward_rows=496,epoch=time.time()))
    except Exception as exc:
        write('status.json',dict(complete=False,updates=896,error_type=type(exc).__name__,error=str(exc)));raise
    finally:write('evaluation_data_access.json',boundary.receipt)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['scope','training','evaluation']);args=parser.parse_args()
    if args.action=='scope':scope();print('Final scope passed; evaluation payload not accessed')
    else:globals()[args.action]()
