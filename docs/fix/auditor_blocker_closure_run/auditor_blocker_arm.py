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
    return closure.authorize(ROOT)


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



import auditor_blocker_support as closure
Budget.check=closure.budget_check

def execute(arm):
    OUT.mkdir(exist_ok=True)
    with (OUT/'ARM_ATTEMPTED').open('x') as stream:stream.write('One diagnostic arm; no resume/retry.\n')
    boundary=f.Boundary(ROOT);boundary.install();completed=0;budget=None
    result=dict(arm=arm,status="INCOMPLETE",forwards=0,matched_rows=0,optimizer_updates=0,process=closure.process_identity())
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
        prior=np.load(ROOT/'closure_payload/historical32.npy',allow_pickle=False)
        f.require(prior.shape==(32,3072) and prior.dtype==np.float32 and np.isfinite(prior).all(),'Bound historical prefix')
        begin=time.perf_counter()
        for i,row in enumerate(rows[:32]):
            budget.check('fresh_train_features')
            raw=mask=vector=None
            result['forwards']=i+1
            if arm=='O':
                try:
                    with torch.inference_mode():
                        ids=torch.tensor([row['input_ids']],device='cuda',dtype=torch.long)
                        with torch.autocast('cuda',dtype=torch.bfloat16):
                            raw=model.get_base_model().model(input_ids=ids,attention_mask=(mask:=torch.ones_like(ids)),use_cache=False,return_dict=True).last_hidden_state
                            hidden=raw[0,-1]
                        vector=hidden.float().cpu().numpy().copy()
                except Exception:
                    why='wrong_raw_shape' if raw is not None and tuple(raw.shape)!=(1,len(row['input_ids']),3072) else 'forward_or_index_exception'
                    closure.capture(ROOT,OUT,torch,np,model,row,i,raw,None,vector,ids if raw is not None else None,mask,why,prior[i])
                    if why=='wrong_raw_shape':raise closure.Divergence(i,why)
                    raise
                closure.admit(ROOT,OUT,torch,np,model,row,i,raw,hidden,vector,ids,mask,prior[i])
            else:
                import auditor_blocker_helper as helper
                def boundary_callback(raw,hidden,vector,ids,mask,failure):
                    if failure and failure.startswith('forward_or_extraction_exception:'):
                        closure.capture(ROOT,OUT,torch,np,model,row,i,raw,hidden,vector,ids,mask,failure,prior[i])
                        return
                    closure.admit(ROOT,OUT,torch,np,model,row,i,raw,hidden,vector,ids,mask,prior[i])
                vector=helper.extract_train_vector(torch,np,model,row,i,'cuda',OUT/f'row-{i+1:02d}.json',record_success=True,boundary_callback=boundary_callback)
            f.require(vector.shape==(3072,) and np.isfinite(vector).all(),'finite TRAIN hidden')
            features[i]=vector;features.flush();budget.features=i+1
            emit(dict(event='feature',index=i,example_id=row['example_id'],token_sha256=fork.token_hash(row['input_ids']),feature_sha256=hashlib.sha256(vector.tobytes()).hexdigest(),norm=float(np.linalg.norm(vector.astype(np.float64)))))
            result['matched_rows']=i+1
            del raw,mask
        result['status']='MATCHES'
    except closure.Divergence as exc:
        result.update(status='DIVERGES',first_divergence_index=exc.index,reason=exc.reason)
    except Exception as exc:
        result.update(status='INCOMPLETE',error_type=type(exc).__name__)
        raise
    finally:
        result['data_access']=boundary.receipt
        result['finished_epoch']=time.time()
        write('result.json',result)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('arm',choices=['O','D']);args=parser.parse_args()
    f.require(os.environ.get('AUDITOR_CLOSURE_ARM')==args.arm,'Supervisor arm identity')
    OUT=ROOT/'evidence'/args.arm
    execute(args.arm)
