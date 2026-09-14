"""Sealed single-run observer. Imported safely; execution is remote-only."""
import contextvars
import contextlib
import functools
import importlib
import inspect
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

DUMPS = json.dumps
ATTR = contextvars.ContextVar('diagnostic_attributes', default={})
PARENT = contextvars.ContextVar('diagnostic_parent', default=None)
IN_RECORD = contextvars.ContextVar('diagnostic_recording', default=False)

def utc():
    return datetime.now(timezone.utc).isoformat()

class Recorder:
    def __init__(self, path):
        self.file = open(path,'a',encoding='utf-8',buffering=1)
        self.start = time.perf_counter()
        self.lock = threading.Lock()
        self.seq = 0
        self.phase = 'startup'
    def event(self, kind, **fields):
        if IN_RECORD.get() or self.file.closed:
            return
        token = IN_RECORD.set(True)
        try:
            with self.lock:
                self.seq += 1
                row = {'seq':self.seq,'event':kind,'utc':utc(),
                       't':time.perf_counter()-self.start,'thread':threading.get_ident(),**fields}
                self.file.write(DUMPS(row,ensure_ascii=True,separators=(',',':'))+'\n')
                return self.seq
        finally:
            IN_RECORD.reset(token)
    @contextlib.contextmanager
    def span(self, name, **fields):
        attrs = {'phase':self.phase,**ATTR.get(),**fields}
        sid = self.event('span_start',name=name,parent=PARENT.get(),**attrs)
        parent = PARENT.set(sid)
        t = time.perf_counter()
        end = {}
        try:
            yield end
        except BaseException as exc:
            end['error_type'] = type(exc).__name__
            raise
        finally:
            PARENT.reset(parent)
            self.event('span_end',span=sid,name=name,seconds=time.perf_counter()-t,**attrs,**end)
    def close(self):
        self.file.close()

def wrap(rec, obj, name, label=None):
    original = getattr(obj,name)
    label = label or name
    if inspect.iscoroutinefunction(original):
        @functools.wraps(original)
        async def measured(*args,**kwargs):
            with rec.span(label):
                return await original(*args,**kwargs)
    else:
        @functools.wraps(original)
        def measured(*args,**kwargs):
            if IN_RECORD.get():
                return original(*args,**kwargs)
            with rec.span(label):
                return original(*args,**kwargs)
    setattr(obj,name,measured)
    return original

def deny_network(rec):
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    def denied(kind):
        def fail(*args,**kwargs):
            rec.event('network_blocked',network_kind=kind,
                      frames=[{'file':Path(f.filename).name,'function':f.name,'line':f.lineno}
                              for f in traceback.extract_stack(limit=9)[:-1]])
            raise RuntimeError('Diagnostic forbids network')
        return fail
    def local_ipc(original,kind):
        def connect(sock,address):
            # Windows asyncio uses a loopback socketpair for its wake-up pipe.
            # Permit numeric loopback only, never DNS names or external addresses.
            if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):
                rec.event('local_ipc',operation=kind)
                return original(sock,address)
            return denied(kind)(sock,address)
        return connect
    socket.socket.connect = local_ipc(original_connect,'socket_connect')
    socket.socket.connect_ex = local_ipc(original_connect_ex,'socket_connect_ex')
    socket.socket.sendto = denied('socket_sendto')
    socket.create_connection = denied('create_connection')
    socket.getaddrinfo = denied('dns')
    import requests
    requests.sessions.Session.request = denied('http')
    import http.client
    http.client.HTTPConnection.connect = denied('http_connection')
    import httpx
    httpx.Client.request = denied('httpx')
    httpx.AsyncClient.request = denied('httpx_async')

class Sampler:
    def __init__(self,rec,interval=3):
        import psutil
        self.psutil = psutil
        self.proc = psutil.Process()
        self.rec = rec
        self.stop_event = threading.Event()
        self.interval = interval
        self.proc.cpu_percent(None)
        psutil.cpu_percent(None)
    def sample(self):
        p = self.psutil
        mem = p.virtual_memory()
        io = self.proc.io_counters()
        row = {'phase':self.rec.phase,'rss_bytes':self.proc.memory_info().rss,
               'process_cpu_percent':self.proc.cpu_percent(None),'system_cpu_percent':p.cpu_percent(None),
               'system_used_bytes':mem.used,'system_available_bytes':mem.available,
               'system_total_bytes':mem.total,'io_read_bytes':io.read_bytes,'io_write_bytes':io.write_bytes}
        try:
            result = subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu',
                                     '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2,
                                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            vals = result.stdout.strip().splitlines()[0].split(',')
            row['gpu'] = {k:float(v.strip()) if re.fullmatch(r'[0-9.]+',v.strip()) else None
                          for k,v in zip(('utilization_percent','memory_utilization_percent','used_mib','total_mib','power_w','temperature_c'),vals)}
        except Exception as exc:
            row['gpu_error_type'] = type(exc).__name__
        self.rec.event('resource',**row)
    def loop(self):
        while not self.stop_event.is_set():
            t = time.perf_counter()
            try:
                self.sample()
            except Exception as exc:
                self.rec.event('sampler_error',error_type=type(exc).__name__)
            self.stop_event.wait(max(0.1,self.interval-(time.perf_counter()-t)))
    def start(self):
        self.thread = threading.Thread(target=self.loop,daemon=True)
        self.thread.start()
        return self
    def stop(self):
        self.stop_event.set()
        self.thread.join(4)
        self.sample()

def install(rec, pipeline):
    import agent_wrapper as aw
    import embedding_store as es
    import transformers
    import sentence_transformers as st
    import torch
    original_dispatch = aw.AgentWrapper.dispatch
    def dispatch(self,*args,**kwargs):
        if self.backend not in ('local_producer','local_auditor','qwen_local'):
            rec.event('provider_blocked',agent=self.name,backend=self.backend)
            raise RuntimeError('Diagnostic forbids provider dispatch')
        attr = ATTR.set({**ATTR.get(),'call_id':getattr(self,'_cost_call_id',''),
                        'phase':getattr(self,'_cost_phase','') or rec.phase,
                        'agent':self.name,'model':self.model,'backend':self.backend,
                        'max_output_tokens':kwargs.get('max_new_tokens')})
        try:
            with rec.span('dispatch') as end:
                result = original_dispatch(self,*args,**kwargs)
                end.update({k:v for k,v in (result.usage or {}).items()
                            if k in ('input_tokens','output_tokens','truncated')})
                end['ok'] = bool(result.ok)
                return result
        finally:
            ATTR.reset(attr)
    aw.AgentWrapper.dispatch = dispatch
    run_task = aw.AgentWrapper.run_task
    def task(self,**kwargs):
        # Whitelist structural identifiers; no work_payload fields are persisted.
        attr = ATTR.set({'phase':kwargs.get('phase') or rec.phase,'agent':self.name,
                        'doc_id':kwargs.get('doc_id','')})
        try:
            with rec.span('run_task'):
                return run_task(self,**kwargs)
        finally:
            ATTR.reset(attr)
    aw.AgentWrapper.run_task = task
    generation_load = aw._load_qwen
    ordinal = {}
    token_classes = set()
    def load(model_id):
        import execution_topology
        context = getattr(execution_topology.WORK, "context", None)
        residents = context.worker.residents if context is not None else aw._QWEN_MODELS
        cached = model_id in residents
        ordinal[model_id] = ordinal.get(model_id,0) + int(not cached)
        with rec.span('generation_load',model=model_id,cached=cached,load_ordinal=ordinal[model_id]) as end:
            tok,model = generation_load(model_id)
            end.update(device=str(model.device),resident_models=len(residents),
                       allocated_mib=torch.cuda.memory_allocated()/2**20 if torch.cuda.is_available() else 0,
                       reserved_mib=torch.cuda.memory_reserved()/2**20 if torch.cuda.is_available() else 0,
                       placement=sorted(set(str(v) for v in getattr(model,'hf_device_map',{}).values())))
            if type(tok) not in token_classes:
                wrap(rec,type(tok),'__call__','generation_tokenize')
                wrap(rec,type(tok),'decode','generation_decode')
                token_classes.add(type(tok))
            if not getattr(model,'_diagnostic_installed',False):
                generate = model.generate
                def measured_generate(*args,**kwargs):
                    ids = kwargs.get('input_ids')
                    with rec.span('generate',input_tokens=int(ids.shape[-1]) if ids is not None else None,
                                  input_device=str(ids.device) if ids is not None else 'unknown',
                                  budget=kwargs.get('max_new_tokens')) as done:
                        out = generate(*args,**kwargs)
                        done['output_tokens'] = int(out.shape[-1]-ids.shape[-1])
                        done['truncated'] = done['output_tokens'] >= kwargs['max_new_tokens']
                        return out
                model.generate = measured_generate
                model._diagnostic_installed = True
            return tok,model
    aw._load_qwen = load
    wrap(rec,aw,'_evict_generation_models','eviction')
    wrap(rec,aw,'_local_checkpoint_path','checkpoint_resolution')
    for cls,label in ((transformers.AutoTokenizer,'tokenizer_load'),
                      (transformers.AutoModelForCausalLM,'causal_weights_load')):
        original = cls.from_pretrained
        def from_pretrained(*args,_original=original,_label=label,**kwargs):
            with rec.span(_label):
                return _original(*args,**kwargs)
        cls.from_pretrained = from_pretrained
    embed_load = es._load_model
    def load_embedding(module,name):
        with rec.span('embedding_load',model=name,cached=name in es._MODEL_CACHE) as end:
            model = embed_load(module,name)
            end['available'] = model is not None
            end['device'] = str(model.device) if model is not None else 'unavailable'
            return model
    es._load_model = load_embedding
    wrap(rec,st.SentenceTransformer,'encode','embedding_encode')
    wrap(rec,st.SentenceTransformer,'tokenize','embedding_tokenize')
    for name in ('get_or_build','build_store','load_store','query_store','is_store_stale'):
        wrap(rec,es,name,'embedding_'+name)
    # Log only the known phase marker, never an arbitrary log message.
    log_event = pipeline.log_event
    def event(logger,message,**kwargs):
        match = re.match(r'phase_start phase=([0-9.\-]+)',message)
        if match:
            rec.phase = match.group(1)
            rec.event('phase_marker',phase=rec.phase)
        return log_event(logger,message,**kwargs)
    pipeline.log_event = event
    phase_done = pipeline.log_phase_done
    def done(logger,phase,**kwargs):
        rec.event('existing_phase_done',phase=str(phase),duration_ms=kwargs.get('duration_ms',0))
        return phase_done(logger,phase,**kwargs)
    pipeline.log_phase_done = done
    progress = pipeline._emit_progress
    def emit_progress(**kwargs):
        phase = kwargs.get('phase')
        if phase is not None:
            phase = '3-4' if str(phase) in ('3','4') else str(phase)
            if phase != rec.phase:
                rec.phase = phase
                rec.event('phase_marker',phase=phase)
        return progress(**kwargs)
    pipeline._emit_progress = emit_progress
    for name in ('_populate_operational','_load_corpus','_build_reference_index','parse_conventions',
                 'write_registry','_prior_comparison','_normalize_finding',
                 '_semantic_filter_context_refs','_provision_aware_context_refs',
                 'phase_3_4_content_production','phase_5_audit','phase_5_5_convention_review',
                 'phase_6_synthesis','phase_6_5_editorial_review','_dispatch_rank',
                 'write_deliverables_run_summary','render_context_summary','render_operative_summary'):
        if hasattr(pipeline,name):
            wrap(rec,pipeline,name,'pipeline.'+name)
        else:
            rec.event('missing_hook',name=name)
    selections = {
        'paired_review':['compute_checks','plan_calls','dedupe','ensure_amendments_for_findings','suppress_contradicted_amendments'],
        'pairing_map':['build_pairing_map','write_pairing_map'],
        'text_extract':['extract_pages','extract_text'],
        'semantic_ensemble':['decide','vote_sbert','vote_keybert','vote_tfidf','vote_bow','vote_word_overlap'],
        'amendment_render':['write_amendment_deliverables','render_amendments_md','render_amendments_docx'],
        'ontology_capture':['capture_run'], 'ontology_graph':['build_graph'], 'ontology_gnn':['gnn_update'],
    }
    for mod,names in selections.items():
        obj = importlib.import_module(mod)
        for name in names:
            if hasattr(obj,name):
                wrap(rec,obj,name,mod+'.'+name)
            else:
                rec.event('missing_hook',name=mod+'.'+name)
    for obj,names in ((pipeline.ReferenceIndex,('save','build_from_document')),
                      (pipeline.TopOrchestrator,('boot','deliberation_round','run_summary'))):
        for name in names:
            if hasattr(obj,name):
                wrap(rec,obj,name,obj.__name__+'.'+name)
    # File-level timings, not raw OS I/O service time. JSON serialization is nested.
    for name in ('read_text','write_text','read_bytes','write_bytes'):
        wrap(rec,Path,name,'file.'+name)
    for name in ('dump','dumps','load','loads'):
        wrap(rec,json,name,'json.'+name)


def summarize(events, scheduler, lifecycle):
    """Measured overlap, not inferred DAG parallelism; failed runs stay non-benchmarks."""
    spans = {r['seq']: r for r in events if r['event'] == 'span_start'}
    ends = [r for r in events if r['event'] == 'span_end']
    generation = [r for r in ends if r.get('name') == 'generate']
    boundaries = []
    for row in ends:
        if row.get('name') == 'dispatch' and row['span'] in spans:
            boundaries += [(spans[row['span']]['t'], 1), (row['t'], -1)]
    active = peak = 0
    for _, delta in sorted(boundaries):
        active += delta
        peak = max(active, peak)
    times = {r['event']: r['epoch'] for r in lifecycle}
    finops = None
    if 'first_generation_start' in times and 'instance_reported_running' in times:
        finops = times['first_generation_start'] - times['instance_reported_running']
    closed = [r for r in scheduler if r['event'] == 'scheduler_closed']
    wall = max((r['t'] for r in events if r['event'] == 'process_finish'), default=None)
    return {'model_calls': len([r for r in ends if r.get('name') == 'dispatch']),
            'generation_seconds': sum(r['seconds'] for r in generation),
            'actual_max_concurrent_calls': peak, 'observer_cold_wall_seconds': wall,
            'wall_delta_vs_1958_second_baseline': wall - 1958 if wall is not None else None,
            'provisioned_to_first_generation_seconds': finops,
            'scheduler_wait_seconds': sum(r.get('scheduler_wait_s', 0) for r in scheduler),
            'dependency_wait_seconds': sum(r.get('dependency_wait_s', 0) for r in scheduler),
            'barrier_wait_seconds': sum(r.get('barrier_wait_s', 0) for r in scheduler),
            'worker_idle_seconds': sum(r.get('worker_idle_s', 0) for r in scheduler),
            'semantic_critical_path': closed[-1].get('critical_path', []) if closed else [],
            'semantic_critical_path_service_seconds': closed[-1].get('critical_path_service_s') if closed else None,
            'model_residency_events': [r for r in scheduler if r['event'] in ('model_load_start', 'model_load_end', 'model_resident', 'model_evicted')],
            'quality_equivalence': 'not established by timing or DAG selection'}


def main():
    from cloud_run_common import require, write_json
    base = Path(__file__).resolve().parent
    root = base / 'project'
    evidence = base / 'evidence'
    require(sys.platform == 'linux' and (base / 'REMOTE_SANITY_PASSED.json').is_file(), 'remote sanity required')
    require((base / 'RUN_CLAIMED').is_file() and not (evidence / 'events.jsonl').exists(), 'single-run claim missing or consumed')
    for key in list(os.environ):
        if key.startswith('SHIMMER_') or re.search(r'(API_KEY|TOKEN|SECRET|PASSWORD)$', key):
            os.environ.pop(key, None)
    os.environ.update(SHIMMER_BACKEND_PROFILE='local', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_DISABLE_TELEMETRY='1', HF_HUB_DISABLE_IMPLICIT_TOKEN='1',
                      HF_HOME=str(base / 'hf_cache'), HF_HUB_CACHE=str(base / 'hf_cache/hub'))
    os.chdir(root)
    sys.path[:0] = [str(root / 'scripts'), str(root / 'tools'), str(root)]
    rec = Recorder(evidence / 'events.jsonl')
    rec.event('process_start', pid=os.getpid(), python=sys.version.split()[0])
    original_stdout, original_stderr = sys.stdout, sys.stderr
    null = open(os.devnull, 'w', encoding='utf-8')
    sys.stdout = sys.stderr = null
    sampler, code, status = None, 1, 'ABORTED / NON-BENCHMARK'
    try:
        deny_network(rec)
        sampler = Sampler(rec).start()
        import execution_scheduler
        old_emit = execution_scheduler.Scheduler.emit
        scheduler_lock = threading.Lock()
        first = []
        def emit(self, event, **fields):
            old_emit(self, event, **fields)
            row = {'event': event, 'epoch': time.time(), **fields}
            with scheduler_lock:
                with (evidence / 'scheduler.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(DUMPS(row, sort_keys=True) + '\n')
                if event == 'generation_start' and not first:
                    first.append(row['epoch'])
                    with (evidence / 'lifecycle.jsonl').open('a', encoding='utf-8') as stream:
                        stream.write(DUMPS({'event': 'first_generation_start', 'epoch': row['epoch'], 'utc': utc()}) + '\n')
        execution_scheduler.Scheduler.emit = emit
        with rec.span('pipeline_import'):
            import pipeline
        with rec.span('instrumentation_install'):
            install(rec, pipeline)
        import run_local_demo
        args = json.loads((base / 'run_options.json').read_text())['argv']
        args[args.index('--topology-config') + 1] = str(base / 'topology.json')
        args += ['--output-dir', str(evidence / 'run'), '--sample-file', str(evidence / 'memory_peak.json')]
        rec.event('workload', corpus='clinical_reference', argv=args, multi_round=False)
        with rec.span('local_wrapper'):
            code = run_local_demo.main(args)
        if code == 0:
            status = 'RUN FINISHED / COLLECTION AND TEARDOWN PENDING'
    except BaseException as exc:
        rec.event('terminal_error', error_type=type(exc).__name__)
    finally:
        if sampler:
            sampler.stop()
        rec.event('process_finish', status=status, exit_code=code)
        rec.close()
        sys.stdout, sys.stderr = original_stdout, original_stderr
        null.close()
        write_json(evidence / 'result.json', {'classification': status, 'exit_code': code, 'completed_runs': int(code == 0),
                   'benchmark_valid': False, 'multi_round_active': False})
    return code


if __name__ == '__main__':
    raise SystemExit(main())
