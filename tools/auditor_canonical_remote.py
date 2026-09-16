"""One prospectively authorized fresh Auditor canonical run; no resume or alternate flow."""
import argparse,ast,hashlib,importlib.metadata,json,math,os,platform,random,signal,statistics,subprocess,sys,time
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evidence';V3=ROOT/'tuning/auditor_canonical_execution';RT=V3
def boundary(event,args):
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        p=Path(os.fsdecode(args[0])).resolve()
        if 'producer' in {s.lower() for s in p.parts} or 'protected' in p.name.lower():raise PermissionError('Forbidden Producer/protected artifact')
        if p.is_relative_to(ROOT/'benchmark') and p.suffix not in ('.py','.pyc'):raise PermissionError('Benchmark data forbidden')
sys.addaudithook(boundary)
sys.path.insert(0,str(RT));import eval_runtime as ev
sys.path.insert(0,str(ROOT/'tuning/second_domain_agnostic_v2'));import runtime as r
sys.path.insert(0,str(V3));import selection
def read(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()
def write(name,value):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def append(name,value):
    with (OUT/name).open('a') as f:f.write(json.dumps(value,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())

def scope():
    m=read(ROOT/'execution_manifest.json');permit=read(ROOT/'training_authorization.json')
    for name,digest in m['files'].items():
        p=(ROOT/name).resolve();assert p.is_relative_to(ROOT) and sha(p)==digest,name
    assert sha(V3/'freeze.json')==permit['execution_freeze_sha256']==m['execution_freeze_sha256']
    binding=read(V3/'source_binding.json')
    assert binding['source_release_sha256']==permit['source_release_sha256']=='bb27d49234fcc30cf02438ac0ce1c43dc690cf514aa9ebbe8d4ae4f6341aa78d'
    assert binding['source_dataset_sha256']==permit['dataset_sha256']=='0e7532aa9cbca8cffad99faae03656cbbdb0dbf3fc489b18d142b5a000dfbc12'
    assert sha(V3/'dataset.json')==binding['export_sha256']
    assert permit['operator_authorized'] and permit['action']=='auditor-canonical-fresh-training' and permit['maximum_instances']==1 and permit['hard_budget_usd']==3
    assert not permit['producer_execution'] and not permit['protected_access'] and permit['fresh_adapter'] and permit['gpu_type']=='gpu_1x_a10'
    spec=read(V3/'experiment.json');rows=read(V3/'dataset.json');split=read(V3/'split.json');plan=read(V3/'execution_plan.json');protocol=read(V3/'evaluation_protocol.json');records=read(V3/'prepared_dev.json')
    assert len(rows)==300 and all(x['role']=='auditor' and r.sha(x)==binding['row_hashes'][x['example_id']] for x in rows)
    assert spec['dataset_sha256']==binding['source_dataset_sha256'] and spec['checkpoint_steps']==[60,120] and spec['training']['max_steps']==120
    assert len(split['train'])==240 and len(split['validation'])==60 and plan['role']=='auditor' and plan['split']=='canonical'
    from collections import Counter
    assert len(plan['optimizer_schedule'])==120 and Counter(i for u in plan['optimizer_schedule'] for i in u['example_ids'])==Counter({i:2 for i in split['train']})
    assert not set(split['validation'])&set(split['train'])
    assert plan['validation_ids']==split['validation'] and plan['train_ids']==split['train']
    r.check_split(rows,split);ev.validate_records(records,protocol);ev.validate_generation(protocol['generation_kwargs'],protocol)
    for name,digest in read(V3/'freeze.json')['files'].items():assert sha(ROOT/name)==digest,name
    return spec,rows,split,plan,protocol,records


def preflight():
    scope();assert sys.platform=='linux' and platform.machine()=='x86_64' and sys.version_info[:3]==(3,12,3)
    lock=read(ROOT/'tuning/first_domain_agnostic_v1/dependency_lock.json')['packages']
    for name,version in lock.items():assert importlib.metadata.version(name)==version,(name,version)
    os.environ['USE_TORCH']='1'
    import torch,psutil,shutil
    assert torch.cuda.is_available() and torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported() and torch.version.cuda=='12.1'
    assert 'A10' in torch.cuda.get_device_name() and 'A100' not in torch.cuda.get_device_name()
    assert psutil.virtual_memory().total>=32*2**30 and shutil.disk_usage(ROOT).free>=40*2**30
    write('preflight.json',dict(passed=True,python=sys.version,versions=lock,gpu=torch.cuda.get_device_name(),gpu_count=1,bf16=True))

def acquire():
    spec,*_=scope();assert read(OUT/'preflight.json')['passed']
    os.environ.update(HF_HUB_OFFLINE='0',TRANSFORMERS_OFFLINE='0')
    from huggingface_hub import snapshot_download
    expected=dict(spec['asset_hashes'],**spec['base_weight_hashes']);start=time.time()
    path=Path(snapshot_download(spec['model_id'],revision=spec['revision'],allow_patterns=list(expected)))
    for name,value in expected.items():assert sha(path/name)==value,name
    write('acquisition.json',dict(path=str(path),seconds=time.time()-start,files=expected,auditor_only=True))

def per_pass_speed(first,second,minimum):
    rates=[]
    for rows in (first,second):
        assert len(rows)==5 and all(math.isfinite(x['generation_seconds']) and x['generation_seconds']>0 for x in rows)
        rate=sum(x['output_tokens'] for x in rows)/sum(x['generation_seconds'] for x in rows)
        assert rate>=minimum,'Individual optimized control pass below floor'
        rates.append(rate)
    return rates

def execute():
    spec,rows,split,plan,protocol,records=scope();args=spec['training']
    assert sys.gettrace() is None and sys.getprofile() is None
    for k,v in read(ROOT/'environment.json').items():assert os.environ.get(k)==v,k
    os.environ.update(USE_TORCH='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    import torch,numpy as np
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
    from peft.utils.save_and_load import get_peft_model_state_dict
    def offline(event,values):
        if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('Offline after acquisition')
    sys.addaudithook(offline)
    path=Path(read(OUT/'acquisition.json')['path'])
    for name,value in dict(spec['asset_hashes'],**spec['base_weight_hashes']).items():assert sha(path/name)==value
    tok=AutoTokenizer.from_pretrained(str(path),local_files_only=True,trust_remote_code=False)
    encoded={x['example_id']:r.encode(x,tok) for x in rows};by={x['example_id']:x for x in rows}
    assert max(len(x['input_ids']) for x in encoded.values())==1052
    assert all(len(x['input_ids'])<=1056 and x['target_length']<=192 and all(v==-100 for v in x['labels'][:x['prompt_length']]) for x in encoded.values())
    for row in records:
        prefix=tok.apply_chat_template(r.task_messages(by[row['example_id']]),tokenize=True,add_generation_prompt=True)
        assert prefix==row['input_ids']
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    random.seed(7);np.random.seed(7);torch.manual_seed(7);torch.cuda.manual_seed_all(7)
    begin=time.time()
    model=AutoModelForCausalLM.from_pretrained(str(path),local_files_only=True,trust_remote_code=False,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='eager')
    assert model.config.model_type=='llama' and model.is_loaded_in_4bit
    selected={n for n in dict(model.named_modules()) if n.rsplit('.',1)[-1] in spec['lora']['target_modules']}
    assert selected==set(spec['architecture']['resolved_modules'])
    quant=model.config.quantization_config.to_dict()
    for k in ('bnb_4bit_quant_type','bnb_4bit_use_double_quant','bnb_4bit_compute_dtype'):assert quant[k]==spec['quantization'][k]
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    # Seed immediately before fresh LoRA construction. No load_adapter or old weights.
    torch.manual_seed(7);torch.cuda.manual_seed_all(7)
    model=get_peft_model(model,LoraConfig(**spec['lora']))
    model.peft_config['default'].base_model_name_or_path=spec['model_id'];model.peft_config['default'].revision=spec['revision']
    params=[p for n,p in model.named_parameters() if p.requires_grad]
    assert all('lora_' in n for n,p in model.named_parameters() if p.requires_grad)
    assert sum(p.numel() for p in params)==spec['architecture']['adapter_parameters']==14942208
    assert all(torch.count_nonzero(p).item()==0 for n,p in model.named_parameters() if 'lora_B' in n)
    def save_checkpoint(step):
        directory=OUT/f'checkpoint-{step}';directory.mkdir(exist_ok=False)
        model.save_pretrained(directory,safe_serialization=True)
        for p in directory.iterdir():
            if p.is_file():
                with p.open('rb') as f:os.fsync(f.fileno())
        identity=dict(experiment='auditor-canonical-v2',step=step,files={name:sha(directory/name) for name in ('adapter_config.json','adapter_model.safetensors')})
        write(f'checkpoint-{step}/identity.json',identity);return identity
    initial=save_checkpoint(0)
    write('loaded_architecture.json',dict(model_type=model.config.model_type,architectures=model.config.architectures,config_sha256=sha(path/'config.json'),quantization=quant));write('initialization.json',dict(seed=7,fresh_lora=True,old_adapter_loaded=False,lora_B_all_zero=True,adapter=initial,model_load_seconds=time.time()-begin,trainable_parameters=14942208))
    opt=torch.optim.AdamW(params,lr=args['learning_rate'],betas=(args['adam_beta1'],args['adam_beta2']),eps=args['adam_epsilon'],weight_decay=args['weight_decay'])
    total=args['max_steps'];warm=args['warmup_steps']
    scheduler=torch.optim.lr_scheduler.LambdaLR(opt,lambda s:min((s+1)/warm,max(0.,(total-s)/max(1,total-warm))))
    write('optimizer_config.json',dict(training=args,initial_learning_rate=opt.param_groups[0]['lr'],scheduler_state=scheduler.state_dict(),schedule=plan['optimizer_schedule']))
    from binding import RawSink as Sink, control_gate
    budget=read(ROOT/'budget.json');checkpoints=[];completed_updates=0;training_wall=0.;step_times=[];eval_outputs=0;generated_tokens=0;generation_wall=0.
    stop_requested=[False]
    signal.signal(signal.SIGTERM,lambda signum,frame:stop_requested.__setitem__(0,True))
    sampler=subprocess.Popen([sys.executable,str(ROOT/'tuning/second_tuning_eval_runtime_v2_1/telemetry_worker.py'),'--pid',str(os.getpid()),'--output',str(OUT/'telemetry.jsonl'),'--stop-file',str(OUT/'telemetry.stop')])
    watchdog=subprocess.Popen([sys.executable,str(Path(__file__)),'budget_watch','--pid',str(os.getpid())])
    def digest_state(value):
        h=hashlib.sha256()
        def visit(x):
            if torch.is_tensor(x):
                v=x.detach().cpu().contiguous();h.update(str((v.dtype,tuple(v.shape))).encode());h.update(v.reshape(-1).view(torch.uint8).numpy().tobytes())
            elif isinstance(x,dict):
                for k in sorted(x,key=str):h.update(str(k).encode());visit(x[k])
            elif isinstance(x,(list,tuple)):
                for v in x:visit(v)
            else:h.update(repr(x).encode())
        visit(value);return h.hexdigest()
    def rng():return (random.getstate(),np.random.get_state(),torch.get_rng_state(),torch.cuda.get_rng_state_all())
    def restore_rng(state):random.setstate(state[0]);np.random.set_state(state[1]);torch.set_rng_state(state[2]);torch.cuda.set_rng_state_all(state[3])
    def state_receipt():
        return dict(parameters=ev.parameter_state(model),adapter_digest=digest_state(get_peft_model_state_dict(model)),
            gradients=digest_state([p.grad for p in params]),optimizer=digest_state(opt.state_dict()),scheduler=digest_state(scheduler.state_dict()),
            training=[m.training for m in model.modules()],active_adapters=list(model.active_adapters),completed_updates=completed_updates)
    def progress(phase):
        write('progress.json',dict(phase=phase,step=completed_updates,eval_outputs=eval_outputs,epoch=time.time(),training_seconds=training_wall,
            remaining_updates=120-completed_updates,remaining_generations=144-eval_outputs,
            measured_seconds_per_update=statistics.median(step_times[-32:]) if len(step_times)>=8 else None,
            measured_generation_tokens_per_second=generated_tokens/generation_wall if generation_wall else None))
    def budget_gate(phase):
        assert not stop_requested[0],'Budget stop requested; halted at durable boundary'
        now=time.time();step_rate=max(10,statistics.median(step_times[-32:])) if len(step_times)>=8 else 10
        rate=min(protocol['minimum_planning_tokens_per_second'],generated_tokens/generation_wall) if generation_wall else protocol['minimum_planning_tokens_per_second']
        remaining=(120-completed_updates)*step_rate+(144-eval_outputs)*192/rate
        receipt=dict(epoch=now,phase=phase,step=completed_updates,eval_outputs=eval_outputs,estimated_cost=(now-budget['launch_epoch'])*budget['hourly_rate']/3600,
            projected_remaining_seconds=remaining,continue_run=now+remaining<budget['workload_deadline_epoch'])
        append('budget_timeline.jsonl',receipt)
        assert receipt['continue_run'],'Mandatory work no longer fits hard-budget reserve'
        progress(phase)
    def evaluate(step,identity):
        nonlocal eval_outputs,generated_tokens,generation_wall
        folder=OUT/f'checkpoint-{step}';cp=deepcopy(protocol);cp['adapter']=identity
        before=state_receipt();saved_rng=rng();rng_before=digest_state(saved_rng)
        assert step not in {x['step'] for x in checkpoints} and model not in ev._PREFLIGHTS
        receipt=ev.real_runtime_context_preflight(model,torch);write(f'checkpoint-{step}/context_preflight.json',receipt)
        score=lambda i,raw,trunc:r.score(by[i],raw,truncated=trunc)
        controls=[next(x for x in records if x['example_id']==i) for i in cp['control_ids']]
        def run(label,subset,probe=False):
            nonlocal eval_outputs,generated_tokens,generation_wall
            durable=ev.DurableRows(folder/(label+'.jsonl'));bound=Sink(durable,step,identity,subset)
            try:
                if probe:
                    with ev.cache_probe(model,torch) as observations:result=ev.evaluate_records(model,tok,torch,subset,cp,bound,score)
                else:result=ev.evaluate_records(model,tok,torch,subset,cp,bound,score)
                eval_outputs+=len(result);generated_tokens+=sum(x['output_tokens'] for x in result);generation_wall+=sum(x['generation_seconds'] for x in result)
                write(f'checkpoint-{step}/{label}_scored.json',result)
                progress(f'checkpoint-{step}:{label}')
                return (result,observations) if probe else result
            finally:durable.close()
        # Two identical optimized cache observations satisfy the frozen effect
        # checker; its legacy dictionary labels do not imply traced execution.
        _,one=run('cache_1',controls[:1],True);_,two=run('cache_2',controls[:1],True)
        assert ev.cache_effect_gate(dict(reference=one,optimized=two))
        write(f'checkpoint-{step}/cache_admission.json',dict(passed=True,optimized_passes=[one,two],tracing=False))
        first=run('controls_1',controls);second=run('controls_2',controls)
        admitted=control_gate(first,second,cp,identity,step)
        admitted['per_pass_tokens_per_second']=per_pass_speed(first,second,0.0)
        write(f'checkpoint-{step}/control_admission.json',admitted);budget_gate(f'checkpoint-{step}:admitted')
        # Persist one exclusive file across all60 rows; per-row progress/budget,
        # no reuse of any cache/control outputs.
        durable=ev.DurableRows(folder/'full_dev.jsonl');bound=Sink(durable,step,identity,records);results=[]
        try:
            for row in records:
                result=ev.evaluate_records(model,tok,torch,[row],cp,bound,score);results.extend(result);eval_outputs+=1
                generated_tokens+=result[0]['output_tokens'];generation_wall+=result[0]['generation_seconds']
                budget_gate(f'checkpoint-{step}:DEV-{len(results)}')
        finally:durable.close()
        assert len(results)==60 and [x['example_id'] for x in results]==cp['dev_ids']
        write(f'checkpoint-{step}/full_dev_scored.json',results)
        metrics=r.aggregate([x['metrics'] for x in results]);write(f'checkpoint-{step}/metrics.json',metrics)
        restore_rng(saved_rng);after=state_receipt();assert before==after and digest_state(rng())==rng_before,'Evaluation altered training state'
        write(f'checkpoint-{step}/state_restoration.json',dict(passed=True,before=before,after=after,rng_sha256=rng_before,restored_rng_sha256=digest_state(rng())))
        checkpoint=dict(step=step,metrics=metrics,adapter_sha256=r.sha(identity['files']),identity=identity)
        checkpoints.append(checkpoint);write('checkpoints.json',checkpoints)
        # Retire the successful checkpoint context only after complete evaluation
        # and exact state restoration. This permits a fresh lifecycle at120,
        # never retry of a failed checkpoint or resume of partial output.
        ev._PREFLIGHTS.pop(model)
        write(f'checkpoint-{step}/status.json',dict(complete=True,rows=60,passes=r.selection_pass(metrics,spec['selection_gates'])))
    try:
        for update in plan['optimizer_schedule']:
            assert update['step']==completed_updates+1 and len(update['example_ids'])==4 and update['loss_divisor']==4
            budget_gate('training');start=time.perf_counter();model.train();model.config.use_cache=False;opt.zero_grad(set_to_none=True);loss_sum=0.;lr=opt.param_groups[0]['lr']
            for identifier in update['example_ids']:
                assert identifier in split['train'] and identifier not in split['validation']
                datum=encoded[identifier];batch={k:torch.tensor([datum[k]],dtype=torch.long,device=model.device) for k in ('input_ids','attention_mask','labels')}
                with torch.autocast('cuda',dtype=torch.bfloat16):loss=model(**batch).loss
                assert bool(torch.isfinite(loss).item())
                (loss/4).backward();loss_sum+=float(loss.detach());del batch,loss
            torch.nn.utils.clip_grad_norm_(params,1.);opt.step();scheduler.step();torch.cuda.synchronize()
            wall=time.perf_counter()-start;training_wall+=wall;step_times.append(wall);completed_updates=update['step']
            append('training.jsonl',dict(step=completed_updates,epoch=update['epoch'],example_ids=update['example_ids'],examples_processed=completed_updates*4,
                loss=loss_sum/4,learning_rate=lr,next_learning_rate=opt.param_groups[0]['lr'],step_seconds=wall,training_seconds=training_wall,epoch_seconds=time.time(),
                memory_allocated=torch.cuda.memory_allocated(),memory_reserved=torch.cuda.memory_reserved(),max_memory_allocated=torch.cuda.max_memory_allocated(),max_memory_reserved=torch.cuda.max_memory_reserved()))
            if completed_updates in spec['checkpoint_steps']:evaluate(completed_updates,save_checkpoint(completed_updates))
        assert completed_updates==120 and len(checkpoints)==2 and eval_outputs==144
        chosen=selection.select(checkpoints,spec);write('selection.json',chosen)
        if chosen['verdict']=='AUDITOR_TUNING_PASS':
            import shutil
            destination=OUT/'selected_adapter';destination.mkdir(exist_ok=False)
            for name in ('adapter_config.json','adapter_model.safetensors'):
                source=OUT/f"checkpoint-{chosen['selected_step']}"/name;shutil.copyfile(source,destination/name);assert sha(source)==sha(destination/name)
            verdict='AUDITOR_TUNING_PASS'
        else:verdict='AUDITOR_TUNING_FAIL'
        write('status.json',dict(verdict=verdict,training_updates=120,checkpoint_rows={'60':60,'120':60},training_seconds=training_wall,selection=chosen))
    except BaseException as exc:
        write('status.json',dict(verdict='AUDITOR_TUNING_INDETERMINATE',step=completed_updates,error_type=type(exc).__name__,reason=str(exc)))
        raise
    finally:
        (OUT/'telemetry.stop').touch();sampler.wait(timeout=10);watchdog.terminate();watchdog.wait(timeout=10)

def budget_watch():
    budget=read(ROOT/'budget.json');pid=int(sys.argv[sys.argv.index('--pid')+1])
    while True:
        try:os.kill(pid,0)
        except ProcessLookupError:return
        now=time.time();stop=now>=budget['workload_deadline_epoch'];remaining=None
        if now>=budget['soft_epoch']:
            try:
                progress=read(OUT/'progress.json');step_rate=max(10,progress.get('measured_seconds_per_update') or 10)
                rate=min(6.0,progress.get('measured_generation_tokens_per_second') or 6.0)
                remaining=progress['remaining_updates']*step_rate+progress['remaining_generations']*192/rate
                stop=stop or now+remaining>=budget['workload_deadline_epoch']
                write('soft_budget_decision.json',dict(epoch=now,continue_run=not stop,progress=progress,projected_remaining_seconds=remaining))
            except (OSError,ValueError):pass
        if stop:
            write('budget_stop.json',dict(epoch=now,verdict='AUDITOR_TUNING_INDETERMINATE',projected_remaining_seconds=remaining));os.kill(pid,signal.SIGTERM);return
        time.sleep(5)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['preflight','acquire','execute','budget_watch']);parser.add_argument('--pid',type=int);a=parser.parse_args();OUT.mkdir(exist_ok=True)
    if a.action=='execute':
        with (OUT/'TRAINING_ATTEMPTED').open('x'):pass
    globals()[a.action]()
