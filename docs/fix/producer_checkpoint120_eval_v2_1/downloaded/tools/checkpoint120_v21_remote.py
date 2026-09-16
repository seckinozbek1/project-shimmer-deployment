"""Single Producer evaluation integration; no training or optimizer construction."""
import argparse
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import random
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'tuning/second_tuning_eval_runtime_v2_1'
OLD = ROOT / 'tuning/second_tuning_eval_runtime_v2'
OUT = ROOT / 'evidence'
sys.path.insert(0, str(RUNTIME))
import eval_runtime as ev
sys.path.append(str(OLD))
import audit
r = audit.frozen

def read(path): return json.loads(Path(path).read_text())
def write(name, value): r.write(OUT / name, value)
def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024*1024), b''): h.update(block)
    return h.hexdigest()

def boundary(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        p = Path(os.fsdecode(args[0])).resolve()
        parts = {s.lower() for s in p.parts}
        if 'auditor' in parts or p.name in ('protected_eval.py', 'PROTECTED_ACCESS_CONSUMED.json') or p in (ROOT/'benchmark/task_semantics/seed.json', ROOT/'benchmark/task_semantics_v2/extension.json'):
            raise PermissionError('Auditor/protected boundary')
        if p in (ROOT/'tuning/second_domain_agnostic_v2/train.py', ROOT/'tuning/first_domain_agnostic_v1/train.py'):
            raise PermissionError('Training executor forbidden')

sys.addaudithook(boundary)

def scope():
    manifest = read(ROOT/'execution_manifest.json')
    for name, expected in manifest['files'].items():
        p = (ROOT/name).resolve()
        ev.require(p.is_relative_to(ROOT) and sha(p) == expected, 'Execution source changed: '+name)
    protocol = read(RUNTIME/'protocol.json')
    ev.require(sha(RUNTIME/'freeze.json') == manifest['runtime_release_sha256'], 'Runtime freeze changed')
    ev.require(sha(ROOT/'tuning/second_domain_agnostic_v2/freeze.json') == protocol['frozen_v2_sha256'], 'Original freeze changed')
    frozen = read(RUNTIME/'freeze.json')
    ev.require(sha(OLD/'freeze.json')==protocol['runtime_parent_sha256'],'Parent runtime binding changed')
    for name, expected in dict(frozen['files'],**frozen['dependency_files']).items():
        if name in manifest['files']: ev.require(sha(ROOT/name) == expected, 'Frozen runtime member changed')
    permit = read(ROOT/'evaluation_authorization.json')
    ev.authorize(permit, protocol, manifest['runtime_release_sha256'])
    ev.require(permit['maximum_instances'] == 1 and permit['hard_budget_usd'] == 3 and not permit['auditor'], 'Cloud scope mismatch')
    rows = read(ROOT/'producer_dev.json')
    ev.require([x['example_id'] for x in rows] == protocol['dev_ids'] and all(x['role']=='producer' for x in rows), 'Producer DEV only')
    records = read(OLD/'prepared_dev.json')
    ev.validate_records(records, protocol)
    for name, expected in protocol['adapter']['files'].items(): ev.require(sha(ROOT/'adapter'/name)==expected, 'Adapter hash mismatch')
    return manifest, protocol, permit, rows, records

def preflight():
    manifest, protocol, permit, rows, records = scope()
    ev.require(sys.version_info[:3] == (3,12,3) and platform.machine()=='x86_64' and sys.platform=='linux', 'Pinned platform mismatch')
    lock = read(ROOT/'tuning/first_domain_agnostic_v1/dependency_lock.json')['packages']
    for name, version in lock.items(): ev.require(importlib.metadata.version(name)==version, 'Dependency mismatch: '+name)
    os.environ['USE_TORCH']='1'
    import torch, psutil, shutil
    ev.require(torch.cuda.is_available() and torch.cuda.device_count()==1 and torch.cuda.is_bf16_supported() and torch.version.cuda=='12.1', 'Single BF16 CUDA 12.1 GPU required')
    ev.require(psutil.virtual_memory().total>=32*2**30 and shutil.disk_usage(ROOT).free>=40*2**30, 'RAM/disk insufficient')
    write('preflight.json', dict(passed=True,python=sys.version,versions=lock,gpu=torch.cuda.get_device_name(),bf16=True,gpu_count=1,manifest=manifest,optimizer_created=False))

def acquire():
    scope()
    ev.require(read(OUT/'preflight.json')['passed'], 'Preflight absent')
    os.environ.update(HF_HUB_OFFLINE='0',TRANSFORMERS_OFFLINE='0')
    from huggingface_hub import snapshot_download
    spec=read(ROOT/'tuning/second_domain_agnostic_v2/producer/experiment.json')
    expected=dict(spec['asset_hashes'],**spec['base_weight_hashes'])
    start=time.time()
    path=Path(snapshot_download(spec['model_id'],revision=spec['revision'],allow_patterns=list(expected)))
    for name,value in expected.items(): ev.require(sha(path/name)==value,'Base hash mismatch')
    write('acquisition.json',dict(path=str(path),seconds=time.time()-start,files=expected,producer_only=True))

def execute():
    manifest, protocol, permit, rows, records=scope()
    session=ev.EvaluationSession(permit,protocol,manifest['runtime_release_sha256'])
    budget_worker=subprocess.Popen([sys.executable,str(Path(__file__)),'budget_watch','--pid',str(os.getpid())])
    required=read(ROOT/'tuning/first_domain_agnostic_v1/experiment.json')['environment']
    for k,v in required.items(): ev.require(os.environ.get(k)==v,'Deterministic environment: '+k)
    os.environ.update(USE_TORCH='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    import torch
    from transformers import AutoModelForCausalLM
    import peft
    from peft import LoraConfig,get_peft_model,prepare_model_for_kbit_training
    from peft.utils.save_and_load import set_peft_model_state_dict,get_peft_model_state_dict
    from safetensors.torch import load_file
    def no_training(*args,**kwargs): raise PermissionError('Training/optimizer execution forbidden')
    torch.optim.Optimizer.__init__=no_training
    torch.Tensor.backward=no_training
    torch.autograd.backward=no_training
    def offline(event,args):
        if event in ('socket.connect','socket.getaddrinfo'): raise PermissionError('Offline evaluation')
    sys.addaudithook(offline)
    spec=read(ROOT/'tuning/second_domain_agnostic_v2/producer/experiment.json')
    path=Path(read(OUT/'acquisition.json')['path'])
    for name,value in dict(spec['asset_hashes'],**spec['base_weight_hashes']).items(): ev.require(sha(path/name)==value,'Acquired asset changed')
    torch.use_deterministic_algorithms(True);torch.backends.cuda.matmul.allow_tf32=False
    random.seed(spec['training']['seed']);torch.manual_seed(spec['training']['seed']);torch.cuda.manual_seed_all(spec['training']['seed'])
    tok=r.old.tokenizer('producer')
    by_id={x['example_id']:x for x in rows}
    for row in records:
        prompt=tok.apply_chat_template(r.task_messages(by_id[row['example_id']]),tokenize=False,add_generation_prompt=True)
        ev.require(prompt==row['prompt'] and tok(prompt,add_special_tokens=False)['input_ids']==row['input_ids'], 'Remote prompt/token mismatch')
    model=AutoModelForCausalLM.from_pretrained(str(path),local_files_only=True,trust_remote_code=False,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='eager')
    ev.require(model.config.model_type=='qwen2' and model.is_loaded_in_4bit,'Wrong base')
    selected={n for n in dict(model.named_modules()) if n.rsplit('.',1)[-1] in r.old.MODULES}
    ev.require(selected==set(spec['architecture']['resolved_modules']),'LoRA target mismatch')
    quant=model.config.quantization_config.to_dict()
    for k in ('bnb_4bit_quant_type','bnb_4bit_use_double_quant','bnb_4bit_compute_dtype'): ev.require(quant[k]==spec['quantization'][k],'Quantization mismatch')
    model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    model=get_peft_model(model,LoraConfig(**spec['lora']))
    model.peft_config['default'].base_model_name_or_path=spec['model_id'];model.peft_config['default'].revision=spec['revision']
    saved=load_file(str(ROOT/'adapter/adapter_model.safetensors'),device='cpu')
    state=get_peft_model_state_dict(model)
    ev.require(set(saved)==set(state),'Adapter key mismatch')
    ev.require(all(saved[k].shape==state[k].shape and saved[k].dtype==state[k].dtype for k in saved),'Adapter shape/dtype mismatch')
    loaded=set_peft_model_state_dict(model,saved,adapter_name='default')
    ev.require(not loaded.unexpected_keys,'Unexpected adapter keys')
    ev.require(all(torch.equal(get_peft_model_state_dict(model)[k].detach().cpu(),saved[k]) for k in saved),'Loaded adapter differs')
    ev.require(model.active_adapters==['default'],'Wrong active adapter')
    model.eval();model.config.use_cache=True
    write('peft_preflight.json',dict(active_adapters=model.active_adapters,adapter_hashes=protocol['adapter']['files'],
        adapter_parameters=[dict(name=n,device=str(p.device),dtype=str(p.dtype),requires_grad=p.requires_grad) for n,p in model.named_parameters() if 'lora_' in n],
        sources={str(Path(inspect.getsourcefile(fn)).relative_to(Path(peft.__file__).parent)):sha(inspect.getsourcefile(fn)) for fn in (prepare_model_for_kbit_training,set_peft_model_state_dict)},
        preparation_source=inspect.getsource(prepare_model_for_kbit_training),optimizer_created=False,training_updates=0,adapter_tensor_identity=True))
    del saved,state
    import remote_preflight
    try:
        remote_preflight.run(session,model,torch,
            lambda receipt:write('REAL_RUNTIME_CONTEXT_PREFLIGHT.json',receipt),
            lambda:write('TEARDOWN_REQUIRED.json',dict(reason='Context preflight NO_GO; process exits to controller finally collection/termination')))
    except BaseException as exc:
        write('status.json',dict(status='CHECKPOINT120_EVALUATION_NO_GO',checkpoint_result='PRODUCER_CHECKPOINT120_INDETERMINATE',reason='REAL_RUNTIME_CONTEXT_PREFLIGHT: '+type(exc).__name__))
        raise
    trace,trace_hash=audit.historical_trace_callback()
    ev.require(trace_hash=='f59e5cbd306a88500c65a5b9e23df0cf6623697b1deecdf7fbf5b9916b8a86b5','Historical trace changed')
    stop=OUT/'telemetry.stop'
    sampler=subprocess.Popen([sys.executable,str(RUNTIME/'telemetry_worker.py'),'--pid',str(os.getpid()),'--output',str(OUT/'telemetry.jsonl'),'--stop-file',str(stop)])
    prepared_by_id={x['example_id']:x for x in records}
    class BoundRows(ev.DurableRows):
        def append(self,value):
            source=prepared_by_id[value['example_id']]
            value.update(prompt=source['prompt'],input_ids=source['input_ids'],attention_mask=source['attention_mask'],
                base_identity=dict(model_id=protocol['model_id'],revision=protocol['revision'],files=protocol['base_weight_hashes']))
            super().append(value)
    score=lambda identifier,raw,truncated:r.score(by_id[identifier],raw,truncated=truncated)
    def run(label,record,reference=False,probe=False):
        write('progress.json',dict(phase=label,example_id=record['example_id'],epoch=time.time()))
        sink=BoundRows(OUT/(label+'.jsonl'))
        try:
            if probe:
                with ev.cache_probe(model,torch) as observations:
                    result=ev.evaluate_records(model,tok,torch,[record],protocol,sink,score,reference_trace=trace if reference else None)
                write(label+'_cache.json',observations)
            else: result=ev.evaluate_records(model,tok,torch,[record],protocol,sink,score,reference_trace=trace if reference else None)
            write(label+'_scored.json',result)
            return observations if probe else result[0]
        finally: sink.close()
    try:
        controls=[next(x for x in records if x['example_id']==i) for i in protocol['control_ids']]
        observations={mode:run('cache_'+mode,controls[0],reference=mode=='reference',probe=True) for mode in ('reference','optimized')}
        session.admit_cache(observations);write('cache_admission.json',dict(passed=True,observations=observations))
        reference=[];optimized=[]
        for i,row in enumerate(controls):
            reference.append(run('control_reference_'+str(i),row,True))
            optimized.append(run('control_optimized_'+str(i),row))
        receipt=session.admit_control(reference,optimized)
        receipt['decoded_identity']=all(a['raw_output']==b['raw_output'] and a['raw_output_with_special_tokens']==b['raw_output_with_special_tokens'] for a,b in zip(reference,optimized))
        receipt['stop_identity']=all(a['stop_reason']==b['stop_reason'] for a,b in zip(reference,optimized))
        receipt['pass_gate']=receipt['pass_gate'] and receipt['decoded_identity'] and receipt['stop_identity']
        write('control_admission.json',receipt)
        if not receipt['pass_gate']:
            write('status.json',dict(status='CHECKPOINT120_EVALUATION_NO_GO',checkpoint_result='PRODUCER_CHECKPOINT120_INDETERMINATE',reason='Control gate failed',full_dev_rows=0));return
        launch=read(ROOT/'budget.json');remaining=launch['workload_deadline_epoch']-time.time()
        projected=60*288/receipt['optimized_tokens_per_second']
        ev.require(remaining>projected,'Admitted full evaluation cannot fit workload reserve')
        write('admitted.json',dict(status='CHECKPOINT120_EVALUATION_ADMITTED',remaining_seconds=remaining,projected_generation_seconds=projected))
        sink=BoundRows(OUT/'full_dev.jsonl')
        try: results=session.complete_dev(model,tok,torch,records,sink,score)
        finally:sink.close()
        write('full_dev_scored.json',results)
        metrics=r.aggregate([x['metrics'] for x in results]);passed=r.selection_pass(metrics,spec['selection_gates'])
        write('metrics.json',metrics)
        write('status.json',dict(status='COMPLETED',checkpoint_result='PRODUCER_CHECKPOINT120_PASS' if passed else 'PRODUCER_CHECKPOINT120_FAIL',full_dev_rows=60))
    except Exception as exc:
        write('status.json',dict(status='CHECKPOINT120_EVALUATION_NO_GO' if not session.cache_verified or not session.control_receipt else 'INTERRUPTED',checkpoint_result='PRODUCER_CHECKPOINT120_INDETERMINATE',reason=type(exc).__name__+': '+str(exc)))
        raise
    finally:
        stop.touch();sampler.wait(timeout=10)

def budget_watch():
    budget=read(ROOT/'budget.json');pid=int(sys.argv[sys.argv.index('--pid')+1]);checked=False
    while True:
        try:os.kill(pid,0)
        except ProcessLookupError:return
        now=time.time();stop=now>=budget['workload_deadline_epoch']
        if now>=budget['soft_epoch'] and not checked:
            checked=True
            rows=[]
            p=OUT/'full_dev.jsonl'
            if p.exists():
                for line in p.read_text().splitlines():
                    try:rows.append(json.loads(line))
                    except ValueError:pass
            rate=sum(x['output_tokens'] for x in rows)/sum(x['generation_seconds'] for x in rows) if rows else 0
            remaining=(60-len(rows))*288/rate if rate else None
            allowed=bool((OUT/'admitted.json').exists() and remaining is not None and now+remaining<budget['workload_deadline_epoch'])
            write('soft_budget_decision.json',dict(continue_evaluation=allowed,completed_rows=len(rows),projected_remaining_seconds=remaining,epoch=now))
            stop=stop or not allowed
        if stop:
            write('budget_stop.json',dict(epoch=now,reason='Budget admission/cutoff',checkpoint_result='PRODUCER_CHECKPOINT120_INDETERMINATE'))
            os.kill(pid,signal.SIGTERM);return
        time.sleep(2)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('preflight','acquire','execute','budget_watch'));parser.add_argument('--pid',type=int);args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.action=='execute':
        marker=OUT/'EVALUATION_ATTEMPTED'
        with marker.open('x'):pass
    globals()[args.action]()
