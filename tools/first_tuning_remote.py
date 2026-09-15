"""Execution/telemetry envelope around the unchanged frozen tuning runner."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'tuning/first_domain_agnostic_v1'
OUT=ROOT/'evidence'
sys.path.insert(0,str(BASE))
import common as c

def write(name,value):c.write(OUT/name,value)
def utc():return datetime.now(timezone.utc).isoformat()

def preflight():
    c.require(sys.version_info[:3]==(3,12,3),'Exact Python 3.12.3 required')
    c.require(platform.machine()=='x86_64' and sys.platform=='linux','Linux x86-64 required')
    c.frozen()
    for name in c.read(BASE/'freeze.json')['files']:
        if name.endswith('.py'):compile((ROOT/name).read_text(),name,'exec')
    import train
    torch=train.runtime()
    import peft,bitsandbytes,transformers,accelerate
    mem=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemTotal:')))*1024
    c.require(mem>=32*2**30 and shutil.disk_usage(ROOT).free>=40*2**30,'RAM/disk prerequisite')
    write('PRE_ACQUISITION_CHECKPOINT.json',dict(utc=utc(),python=sys.version,executable=sys.executable,
        architecture=platform.machine(),dependencies={k:importlib.metadata.version(k) for k in c.read(BASE/'dependency_lock.json')['packages']},
        gpu=torch.cuda.get_device_name(),vram_bytes=torch.cuda.get_device_properties(0).total_memory,
        bf16=torch.cuda.is_bf16_supported(),visible_gpus=torch.cuda.device_count(),cuda=torch.version.cuda,
        host_ram_bytes=mem,disk_free_bytes=shutil.disk_usage(ROOT).free,source_integrity=True,source_compile=True,
        peft_import=True,bitsandbytes_import=True,model_acquisition_started=False))

def acquire():
    c.require((OUT/'PRE_ACQUISITION_CHECKPOINT.json').exists(),'Pre-acquisition gate absent')
    from huggingface_hub import snapshot_download
    for role,(model,revision) in c.PINS.items():
        start=time.time()
        folder=Path(snapshot_download(model,revision=revision,allow_patterns=list(c.ASSETS)+['model.safetensors']))
        spec=c.read(BASE/role/'experiment.json')
        for name,sha in spec['asset_hashes'].items():c.require(c.digest((folder/name).read_bytes())==sha,'Pinned asset mismatch')
        hashes={}
        for p in folder.iterdir():
            if p.is_file():
                h=hashlib.sha256()
                with p.open('rb') as f:
                    for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
                hashes[p.name]=dict(bytes=p.stat().st_size,sha256=h.hexdigest())
        c.require('model.safetensors' in hashes,'Pinned weights absent')
        write('acquisition_'+role+'.json',dict(role=role,model=model,revision=revision,start_epoch=start,
            end_epoch=time.time(),seconds=time.time()-start,files=hashes,bytes=sum(x['bytes'] for x in hashes.values()),
            cache_state='fresh isolated runtime snapshot acquisition',network_phase_closed=True))

def model_work(role=None,protected=False):
    from common import ROOT as checked_root
    c.require(ROOT==checked_root,'Root mismatch')
    import train,evaluation
    torch=train.runtime()
    import transformers,peft
    # Offline HF plus an executed Python socket boundary; localhost remains usable.
    def audit(event,args):
        if event=='socket.connect':
            address=args[1]
            if isinstance(address,tuple) and address[0] not in ('127.0.0.1','::1','localhost'):
                raise PermissionError('Model execution external network prohibited')
    sys.addaudithook(audit)
    phase='protected' if protected else role
    events=[];stop=threading.Event();start=time.time()
    def event(kind,**values):
        events.append(dict(kind=kind,epoch=time.time(),**values));write(phase+'_events.json',events)
    def sample():
        import psutil
        process=psutil.Process()
        with (OUT/(phase+'_telemetry.jsonl')).open('w') as f:
            while not stop.is_set():
                try:
                    p=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
                    item=dict(epoch=time.time(),gpu=p.stdout.strip(),gpu_allocated=torch.cuda.memory_allocated(),
                        gpu_reserved=torch.cuda.memory_reserved(),rss=process.memory_info().rss,
                        host_ram_used=psutil.virtual_memory().used,cpu_percent=process.cpu_percent())
                    f.write(json.dumps(item)+'\n');f.flush()
                except Exception:event('telemetry_sample_unavailable')
                stop.wait(1)
    original_load=transformers.AutoModelForCausalLM.from_pretrained
    def load(*a,**kw):
        begin=time.time();model=original_load(*a,**kw);torch.cuda.synchronize()
        event('model_load',seconds=time.time()-begin,architecture=model.config.model_type)
        return model
    transformers.AutoModelForCausalLM.from_pretrained=load
    original_validate=train.validate_modules
    def validate(model,spec):
        original_validate(model,spec);event('module_resolution',role=spec['role'],count=len(spec['architecture']['resolved_modules']))
    train.validate_modules=validate
    original_peft=peft.get_peft_model
    def adapt(*a,**kw):
        model=original_peft(*a,**kw)
        names=[n for n,p in model.named_parameters() if p.requires_grad]
        event('trainable_parameters',count=sum(p.numel() for p in model.parameters() if p.requires_grad),
            lora_only=all('lora_' in n for n in names),names=names)
        return model
    peft.get_peft_model=adapt
    original_step=torch.optim.AdamW.step;steps=0;last=time.time()
    def step(optimizer,*a,**kw):
        nonlocal steps,last
        begin=time.time();value=original_step(optimizer,*a,**kw);torch.cuda.synchronize();steps+=1
        event('optimizer_step',step=steps,optimizer_seconds=time.time()-begin,step_wall_seconds=time.time()-last)
        last=time.time();return value
    torch.optim.AdamW.step=step
    thread=threading.Thread(target=sample,daemon=True);thread.start()
    status='COMPLETED'
    try:
        if protected:
            import protected_eval
            protected_eval.execute(ROOT/'protected_authorization.json')
        else:
            train.train(role,ROOT/'training_authorization.json')
    except Exception as exc:
        message=str(exc)
        status=role.upper()+'_SELECTION_FAILED' if not protected and message=='No checkpoint passes catastrophic and contract gates' else 'RUNTIME_FAILED'
        # No provider/credential objects are present in this remote process.
        write(phase+'_failure.json',dict(type=type(exc).__name__,message=message,traceback=traceback.format_exc()))
    finally:
        stop.set();thread.join(timeout=7)
        write(phase+'_status.json',dict(status=status,role=role,utc=utc(),seconds=time.time()-start,
            optimizer_steps=steps,peak_allocated_vram_bytes=torch.cuda.max_memory_allocated(),
            peak_reserved_vram_bytes=torch.cuda.max_memory_reserved(),network_execution_blocked=True,
            forward_backward_time_separately_available=False))
    return 0 if status=='COMPLETED' or status.endswith('SELECTION_FAILED') else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','acquire','train','protected']);p.add_argument('--role',choices=['producer','auditor']);a=p.parse_args()
    OUT.mkdir(exist_ok=True)
    if a.action=='preflight':preflight()
    elif a.action=='acquire':acquire()
    else:raise SystemExit(model_work(a.role,a.action=='protected'))
