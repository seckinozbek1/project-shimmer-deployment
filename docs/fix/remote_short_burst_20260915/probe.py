"""Authorized bounded ordinary probe; no pipeline imports or provider inference."""
import json, os, sys, time, threading, subprocess, socket
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'evidence'
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT/'scripts'))
def write(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, default=str)+'\n')
def main():
    import torch, transformers, psutil
    import agent_wrapper as aw, bounded_extraction as ex, execution_topology as et
    from execution_scheduler import Lane, Task
    from constitution import Constitution
    from message_bus import MessageBus
    from run_context import for_run_dir
    def blocked(*args, **kwargs): raise RuntimeError('Network prohibited during inference')
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    cfg=json.loads((ROOT/'config/local_models.json').read_text())
    pins=json.loads((ROOT/'models.json').read_text())
    families={}
    for role in ('active_producer','active_auditor'):
        checkpoint=aw._local_checkpoint_path(cfg[role])
        assert Path(checkpoint).name == pins[cfg[role]]
        families[role]=transformers.AutoConfig.from_pretrained(checkpoint,local_files_only=True).model_type
    assert len(set(families.values()))==2
    data=dict(classification='BOUNDED_REMOTE_ORDINARY_NOT_BENCHMARK',multi_round=False,full_pipeline=False,
              source_commit='c514d5b68a13a18858608ee176f308d922236541',families=families,calls=[],loads=[],bursts=[],
              generation_policy=dict(max_new_tokens=384,max_time_seconds=25,do_sample=False,seed=7),
              topology=dict(name='report_optimized',device='cuda:0',resident_limit=2,owners=1),
              runtime=dict(torch=torch.__version__,transformers=transformers.__version__,cuda=torch.version.cuda))
    write('probe.json',data)
    rt=et.Runtime([Lane('primary',device='cuda:0',resident_limit=2,memory_gib=24)])
    rt.optimized=True
    rt.run_context=for_run_dir(ROOT,OUT/'wrapper')
    bus=MessageBus.open(OUT/'wrapper/bus.jsonl')
    constitution=Constitution.load(ROOT/'config/constitution.json')
    contracts=json.loads((ROOT/'config/agent_contracts.json').read_text())['contracts']
    stop=threading.Event(); samples=[]; phase=['readiness']; failure=[]
    def sample():
        while not stop.is_set():
            mem=psutil.virtual_memory()
            row=dict(epoch=time.time(),phase=phase[0],available_ram_gib=mem.available/2**30,
                     ram_used_gib=mem.used/2**30,cpu_percent=psutil.cpu_percent(),rss_gib=psutil.Process().memory_info().rss/2**30)
            try:
                p=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
                util,used,total,temp=map(float,p.stdout.strip().split(','))
                row.update(gpu_utilization_percent=util,vram_used_mib=used,vram_total_mib=total,temperature_c=temp)
                if used/total>.94 or mem.available<3*2**30 or temp>=85:
                    failure.append('resource_guard');write('resource_guard.json',row)
            except Exception: row['gpu_sample_unavailable']=True
            samples.append(row);write('resources.json',samples)
            if failure: os._exit(3)
            stop.wait(1)
    thread=threading.Thread(target=sample,daemon=True);thread.start()
    counter=[0]
    def task(label,action,model=''):
        counter[0]+=1
        def owned(context):
            et.WORK.context=context
            phase[0]=label
            try:return action()
            finally:et.WORK.context=None
        return Task('probe-%02d'%counter[0],owned,sequence=counter[0],model=model,phase=label)
    def run_one(t):
        result=rt.scheduler.run([t])[t.id];rt.write()
        if result.exception:raise result.exception
        if result.state!='completed':raise RuntimeError(result.state)
        return result.value
    def load(role):
        def action():
            begin=time.perf_counter();tok,model=aw._load_qwen(cfg[role])
            model.generation_config.do_sample=False;model.generation_config.max_time=25.0
            data['loads'].append(dict(role=role,seconds=time.perf_counter()-begin,device=str(model.device),
                 device_map=model.hf_device_map,allocated_mib=torch.cuda.memory_allocated()/2**20,
                 residents=list(rt.scheduler.workers[0].residents)))
            write('probe.json',data)
        run_one(task('load_'+role,action,cfg[role]))
    def wrapper(name,role):
        w=aw.AgentWrapper(name,constitution,bus,{name:dict(backend='local_producer' if role=='active_producer' else 'local_auditor',model=cfg[role])},contracts,keys={'offline_probe':True},run_context=rt.run_context)
        return rt.attach(w)
    doc='bounded-local-fixture'
    source=('CLM-001: Planned capacity is 120 units (REF-0001). '
            'CLM-002: Reported capacity is 130 units (REF-0002). '
            'The reporting date is not supplied.\n')
    spans=ex.ledger(source,doc)
    assert len(ex.partitions(spans))==1
    def producer_prompt(w,compact):
        instruction='Extract every explicit CLM-* claim id and missing information without inventing facts.\n'
        if compact:return instruction+w._output_contract_text()+'\n'+json.dumps(ex.payload(dict(document_id=doc),spans,spans))
        return instruction+w._output_contract_text()+'\nDocument id: '+doc+'\nReturn one item for the paragraph, section_id=paragraph-1, extraction_method=verbatim. Copy all source exactly into draft_text.\nSOURCE:\n'+source
    fixture=dict(agent='PROCESSOR',doc_id=doc,items=[dict(draft_text=source,claims_referenced=['CLM-001','CLM-002'],open_questions=['What is the reporting date?'])])
    def audit_prompt(w,parsed):
        return ('Compare original with producer extraction. Identify omission, addition or divergence; otherwise MATCH. Verify both figures and missing reporting date. Cite REF-0001 and REF-0002. Use paragraph=1, severity=low if MATCH and explain evidence. Do not certify incomplete extraction.\n'+w._output_contract_text()+'\nDocument id: '+doc+'\nORIGINAL:\n'+source+'\nPRODUCER:\n'+json.dumps(parsed))
    def call_task(label,role,parsed=None,compact=True):
        w=wrapper('PROCESSOR' if role=='active_producer' else 'VERIFIER',role)
        if role=='active_producer' and compact:w._source_adapter=lambda obj:ex.hydrate(obj,spans,doc)
        prompt=producer_prompt(w,compact) if role=='active_producer' else audit_prompt(w,parsed)
        def action():
            torch.manual_seed(7);begin=time.perf_counter()
            result=w.dispatch(prompt,max_new_tokens=384)
            row=dict(label=label,role=role,wall_seconds=time.perf_counter()-begin,usage=result.usage,raw_text=result.raw_text,backend_ok=result.ok)
            data['calls'].append(row);write('probe.json',data)
            obj,missing=w.parse_contract_output(result.raw_text)
            items=(obj or {}).get('items',[]) if isinstance(obj,dict) else []
            if role=='active_producer':
                reconstructed=''.join(x.get('draft_text','') for x in items)==source
                claims={v for x in items for v in x.get('claims_referenced',[])}
                questions=' '.join(v for x in items for v in x.get('open_questions',[])).lower()
                semantic=reconstructed and claims=={'CLM-001','CLM-002'} and 'date' in questions
            else:
                reconstructed=None
                semantic=bool(items) and all(x.get('finding')=='MATCH' and {'REF-0001','REF-0002'}<=set(x.get('ref_ids',[])) for x in items)
            row.update(parsed=obj,contract_valid=not missing,contract_missing=missing,accepted_items=len(items) if not missing else 0,
                       source_reconstructed_exactly=reconstructed,semantic_fixture_checks=semantic,
                       accepted=bool(result.ok and not missing and result.usage.get('truncated') is False and semantic))
            write('probe.json',data)
            return row
        return task(label,action,cfg[role])
    try:
        load('active_producer')
        compact=run_one(call_task('compact_processor','active_producer'))
        run_one(call_task('source_copy_reference','active_producer',compact=False))
        load('active_auditor')
        run_one(call_task('independent_auditor','active_auditor',fixture))
        start=time.perf_counter()
        p=run_one(call_task('serial_producer','active_producer'))
        if p['accepted']:
            between=time.perf_counter()
            a=run_one(call_task('serial_auditor','active_auditor',p['parsed']))
            data['serial_path']=dict(wall_seconds=time.perf_counter()-start,producer_seconds=p['wall_seconds'],auditor_seconds=a['wall_seconds'],accepted=p['accepted'] and a['accepted'],interstage_plus_dispatch_seconds=time.perf_counter()-start-p['wall_seconds']-a['wall_seconds'])
        else:data['serial_path']=dict(status='blocked_producer_not_accepted')
        if compact['accepted'] and all(r['accepted'] for r in data['calls'] if r['label']=='independent_auditor'):
            for capacity in (1,2):
                tasks=[call_task('capacity%d_producer'%capacity,'active_producer'),call_task('capacity%d_auditor'%capacity,'active_auditor',fixture)]
                begin=time.perf_counter()
                if capacity==1: rows=[run_one(t) for t in tasks]
                else:
                    results=rt.scheduler.run(tasks);rt.write()
                    rows=[results[t.id].value for t in tasks]
                data['bursts'].append(dict(requested_capacity=capacity,actual_capacity=1,wall_seconds=time.perf_counter()-begin,calls=[r['label'] for r in rows]))
            data['single_run_parallel_speedup']=data['bursts'][0]['wall_seconds']/data['bursts'][1]['wall_seconds']
        data['concurrency4']='not_admitted: one device owner has one execution thread; no real capacity 2'
        data['residency_load_counts']=rt.scheduler.workers[0].loads
        data['finished_epoch']=time.time()
        write('probe.json',data)
    finally:
        rt.close();stop.set();thread.join(5);write('resources.json',samples)
if __name__=='__main__':
    try:main()
    except BaseException as e:
        import traceback
        write('failure.json',dict(type=type(e).__name__,traceback=traceback.format_exc()))
        raise
