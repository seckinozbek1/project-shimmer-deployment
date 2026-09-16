"""Operational envelope for frozen canonical V2; no experiment adaptation."""
import argparse,functools,hashlib,importlib.util,json,os,platform,shutil,subprocess,sys,threading,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'tuning/second_domain_agnostic_v2';OUT=ROOT/'evidence'
sys.path.insert(0,str(BASE))
import runtime as r
import runner

def write(name,value):r.write(OUT/name,value)
def filehash(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def boundary(event,args):
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        p=Path(os.fsdecode(args[0])).resolve()
        denied=[ROOT/'benchmark/task_semantics/seed.json',ROOT/'benchmark/task_semantics_v2/extension.json',ROOT/'tuning/first_domain_agnostic_v1/protected_eval.py']
        if p in denied:raise PermissionError('Protected component forbidden in canonical pilot')

sys.addaudithook(boundary)

def check_scope():
    permit=r.read(ROOT/'pilot_scope.json')
    r.require(permit['operator_authorized'] is True and permit['splits']==['canonical'] and permit['roles']==['producer','auditor'],'Canonical-only pilot scope')
    binding=runner.verify_freeze();r.require(binding==permit['release_sha256'],'Release binding')
    r.require(not permit['protected_access'] and permit['maximum_instances']==1,'Scope mismatch')
    for role in permit['roles']:
        authorization=r.read(ROOT/(role+'_authorization.json'))
        r.require(authorization['split']=='canonical' and authorization['role']==role and authorization['release_sha256']==binding,'Role permit binding')
        plan=runner.plan(role,'canonical')
        splits=r.read(BASE/'splits.json')
        r.require(splits['canonical']['train']==splits['folds'][0]['train'] and splits['canonical']['validation']==splits['folds'][0]['validation'],'Canonical is not frozen fold0')
        r.require(len(plan['train_ids'])==240 and len(plan['validation_ids'])==60 and len(plan['optimizer_schedule'])==120,'Wrong pilot workload')
    for name in ('benchmark/task_semantics/seed.json','benchmark/task_semantics_v2/extension.json','tuning/first_domain_agnostic_v1/protected_eval.py'):
        r.require(not (ROOT/name).exists(),'Protected file in runtime bundle')
    return binding

def preflight():
    binding=check_scope()
    r.require(sys.version_info[:3]==(3,12,3) and sys.platform=='linux' and platform.machine()=='x86_64','Pinned runtime mismatch')
    import importlib.metadata
    lock=r.read(ROOT/'tuning/first_domain_agnostic_v1/dependency_lock.json')
    for name,version in lock['packages'].items():r.require(importlib.metadata.version(name)==version,'Dependency mismatch: '+name)
    for p in ROOT.rglob('*.py'):
        if '.venv' not in p.parts:compile(p.read_text(),str(p),'exec')
    os.environ['USE_TORCH']='1'
    import torch,transformers,peft,bitsandbytes,accelerate,psutil
    r.require(torch.cuda.is_available() and torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported(),'Single BF16 GPU required')
    r.require(torch.version.cuda=='12.1','CUDA mismatch')
    r.require(psutil.virtual_memory().total>=32*2**30 and shutil.disk_usage(ROOT).free>=40*2**30,'RAM/disk prerequisite')
    write('PRE_ACQUISITION_CHECKPOINT.json',dict(python=sys.version,executable=sys.executable,release_sha256=binding,
        versions={k:importlib.metadata.version(k) for k in lock['packages']},gpu=torch.cuda.get_device_name(),
        gpu_count=torch.cuda.device_count(),bf16=True,cuda=torch.version.cuda,host_ram=psutil.virtual_memory().total,
        disk_free=shutil.disk_usage(ROOT).free,source_compile=True,schedules_verified=True,model_acquisition_started=False))

def acquire():
    r.require((OUT/'PRE_ACQUISITION_CHECKPOINT.json').exists(),'Pre-acquisition gate missing')
    # Acquisition is its own process; offline execution resumes in fresh workers.
    os.environ['HF_HUB_OFFLINE']='0';os.environ['TRANSFORMERS_OFFLINE']='0'
    from huggingface_hub import snapshot_download
    for role in ('producer','auditor'):
        spec=r.read(BASE/role/'experiment.json');start=time.time()
        p=Path(snapshot_download(spec['model_id'],revision=spec['revision'],allow_patterns=list(spec['asset_hashes'])+list(spec['base_weight_hashes'])))
        expected=dict(spec['asset_hashes'],**spec['base_weight_hashes'])
        for name,digest in expected.items():r.require(filehash(p/name)==digest,'Pinned model asset mismatch')
        write('acquisition_'+role+'.json',dict(role=role,model=spec['model_id'],revision=spec['revision'],seconds=time.time()-start,
            files={name:dict(sha256=digest,bytes=(p/name).stat().st_size) for name,digest in expected.items()}))

def train(role):
    check_scope()
    spec=importlib.util.spec_from_file_location('frozen_v2_train',BASE/'train.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    events=[];stop=threading.Event();started=time.time();state=dict(role=role,step=0,generations=0,phase='initializing');thread=None
    def event(kind,**values):
        events.append(dict(kind=kind,epoch=time.time(),**values));write(role+'_events.json',events)
        write('progress.json',dict(state,elapsed_seconds=time.time()-started))
    patched=False;torch=None;last_step=time.time()
    def install(frame):
        nonlocal patched,thread,torch,last_step
        if patched or 'AutoModelForCausalLM' not in frame.f_locals or 'get_peft_model' not in frame.f_locals:return
        patched=True;torch=frame.f_locals['torch'];model_class=frame.f_locals['AutoModelForCausalLM']
        original_load=model_class.from_pretrained
        def load(*a,**kw):
            begin=time.time();model=original_load(*a,**kw);torch.cuda.synchronize()
            event('model_load',seconds=time.time()-begin,architecture=model.config.model_type)
            generate=model.generate
            def measured_generate(*args,**kwargs):
                caller=sys._getframe(1)
                while caller and not (caller.f_code.co_filename==str(BASE/'train.py') and caller.f_code.co_name=='execute'):caller=caller.f_back
                r.require(caller is not None,'Generation outside frozen executor')
                row=caller.f_locals['row'];tok=caller.f_locals['tok']
                state['phase']='validation';begin=time.time();torch.cuda.synchronize()
                output=generate(*args,**kwargs);torch.cuda.synchronize();wall=time.time()-begin
                ids=output[0,kwargs['input_ids'].shape[1]:].tolist();raw=tok.decode(ids,skip_special_tokens=True)
                record=dict(example_id=row['example_id'],step=state['step'],raw_output=raw,
                    raw_output_with_special_tokens=tok.decode(ids,skip_special_tokens=False),output_token_ids=ids,
                    latency_seconds=wall,stop_reason='eos' if ids and ids[-1] in caller.f_locals['spec']['terminal_token_ids'] else 'length')
                try:record['parsed']=r.core.strict_json(raw)
                except (ValueError,TypeError):record['parsed']=None
                # Durable per-row raw output precedes the frozen metric call and
                # survives any later aggregation/selection failure.
                with (OUT/(role+'_raw_dev.jsonl')).open('a') as f:f.write(json.dumps(record)+'\n');f.flush();os.fsync(f.fileno())
                state['generations']+=1;event('generation',example_id=row['example_id'],step=state['step'],seconds=wall,tokens=len(ids),stop_reason=record['stop_reason'])
                return output
            model.generate=measured_generate
            return model
        model_class.from_pretrained=load
        original_step=torch.optim.AdamW.step
        @functools.wraps(original_step)
        def step(optimizer,*args,**kwargs):
            nonlocal last_step
            caller=sys._getframe(1);begin=time.time();value=original_step(optimizer,*args,**kwargs);torch.cuda.synchronize()
            state['step']+=1;state['phase']='training'
            event('optimizer_step',step=state['step'],optimizer_seconds=time.time()-begin,step_wall_seconds=time.time()-last_step,
                learning_rate=optimizer.param_groups[0]['lr'])
            last_step=time.time();return value
        torch.optim.AdamW.step=step
        def sample():
            import psutil
            process=psutil.Process()
            with (OUT/(role+'_telemetry.jsonl')).open('w') as f:
                while not stop.is_set():
                    try:
                        gpu=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
                        f.write(json.dumps(dict(epoch=time.time(),gpu=gpu.stdout.strip(),allocated=torch.cuda.memory_allocated(),reserved=torch.cuda.memory_reserved(),
                            rss=process.memory_info().rss,host_ram_used=psutil.virtual_memory().used,cpu_percent=process.cpu_percent()))+'\n');f.flush()
                    except Exception:pass
                    stop.wait(1)
        thread=threading.Thread(target=sample,daemon=True);thread.start()
    recorded_parameters=False;last_loss_step=0
    def trace(frame,what,arg):
        nonlocal recorded_parameters,last_loss_step
        if frame.f_code.co_filename==str(BASE/'train.py') and frame.f_code.co_name=='execute' and what=='line':
            install(frame)
            if not recorded_parameters and 'parameters' in frame.f_locals:
                model=frame.f_locals['model'];recorded_parameters=True
                event('trainable_parameters',count=sum(p.numel() for p in frame.f_locals['parameters']),lora_only=all('lora_' in n for n,p in model.named_parameters() if p.requires_grad))
            losses=frame.f_locals.get('losses',[])
            if losses and losses[-1]['step']!=last_loss_step:
                last_loss_step=losses[-1]['step'];event('loss',**losses[-1])
        return trace if frame.f_code.co_filename==str(BASE/'train.py') else None
    sys.settrace(trace);status='COMPLETED'
    try:module.execute(role,'canonical',ROOT/(role+'_authorization.json'))
    except Exception as exc:
        status='RUNTIME_FAILED';write(role+'_failure.json',dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    finally:
        sys.settrace(None);stop.set()
        if thread:thread.join(timeout=7)
        run=ROOT/'runs/second-domain-agnostic-v2/canonical'/role
        if status=='COMPLETED' and (run/'SELECTION_REJECTED.json').exists():status='ROLE_SELECTION_FAILED'
        write(role+'_status.json',dict(status=status,optimizer_steps=state['step'],seconds=time.time()-started,generations=state['generations'],
            peak_allocated=0 if torch is None else torch.cuda.max_memory_allocated(),peak_reserved=0 if torch is None else torch.cuda.max_memory_reserved(),
            observer_only=True,protected_accesses=0))
    return 0 if status in ('COMPLETED','ROLE_SELECTION_FAILED') else 2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','acquire','train']);p.add_argument('--role',choices=['producer','auditor']);a=p.parse_args();OUT.mkdir(exist_ok=True)
    if a.action=='preflight':preflight()
    elif a.action=='acquire':acquire()
    else:raise SystemExit(train(a.role))
