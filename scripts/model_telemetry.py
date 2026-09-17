"""Payload-free raw telemetry and deterministic derivation. No inference imports."""
from collections import defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import threading
import time
import uuid
from functools import wraps

LOCK = threading.RLock()


def observe_dispatch(function):
    @wraps(function)
    def dispatch(self, *args, **kwargs):
        started, stamp = time.perf_counter(), now()
        context = getattr(self, 'run_context', None)
        with LOCK:
            if context is not None:
                context._active_model_calls = getattr(context, '_active_model_calls', 0) + 1
        result, failure = None, None
        try:
            result = function(self, *args, **kwargs)
            return result
        except BaseException as exc:
            failure = type(exc).__name__
            raise
        finally:
            with LOCK:
                if context is not None:
                    context._active_model_calls -= 1
            end, end_stamp = time.perf_counter(), now()
            self._backend_timing = dict(start=started, end=end, started_at=stamp, finished_at=end_stamp)
            emit(getattr(self, 'run_context', None), 'backend_invocation',
                call_id=getattr(self, '_cost_call_id', None) or getattr(self, '_generation_call_id', None),
                agent=self.name, backend=self.backend, model_id=self.model,
                start_monotonic_s=started, end_monotonic_s=end,
                backend_success=getattr(result, 'ok', False), failure_category=failure,
                usage=getattr(result, 'usage', None))
    return dispatch


def current_context():
    import run_completion
    completion = run_completion._ACTIVE.get()
    return completion.run_context if completion is not None else None


def retention(results, retained, agent, doc_id, scope):
    context = current_context()
    if context is None:
        return
    kept = {id(item) for item in retained}
    # Snapshot, not an additive counter: synthesis may read an envelope twice.
    counts = {}
    for result in results:
        call_id = result.get('call_id')
        if call_id and result.get('agent') == agent and result.get('ok') and (doc_id is None or result.get('doc_id') == doc_id) and (scope is None or result.get('scope') == scope):
            counts[call_id] = sum(id(item) in kept for item in (result.get('parsed') or {}).get('items', []))
    emit(context, 'retention_snapshot', consumer='current_revision_results', agent=agent, doc_id=doc_id, scope=scope,
         call_counts=counts, retained_total=len(retained))


def semantic_encode(model, texts, **kwargs):
    """Embedding invocations retain original inputs/options; count only, no text."""
    context = current_context()
    started, stamp, failure = time.perf_counter(), now(), None
    try:
        return model.encode(texts, **kwargs)
    except BaseException as exc:
        failure = type(exc).__name__
        raise
    finally:
        end = time.perf_counter()
        emit(context, 'model_call', call_id=uuid.uuid4().hex, agent='EMBEDDING', logical_role='semantic_embedding',
            backend='sentence_transformers', designation='other', model_id=getattr(model, '_shimmer_model_id', None),
            model_revision=None, task_id=None, wave_id=None, phase=None, parent_call_ids=[],
            start_monotonic_s=started, end_monotonic_s=end, started_at=stamp, completed_at=now(),
            total_service_seconds=end-started, input_tokens=None, output_tokens=None,
            input_text_count=len(texts), backend_success=failure is None, contract_valid=None,
            emitted_count=None, retained_count=None, failure_category=failure,
            unavailable={'tokens':'Embedding tokenizer usage not exposed','phase':'No scheduler semantic task binding',
                         'model_revision':'Embedding loader does not pin revision','semantically_complete':'No deterministic quality oracle'})


def now():
    return datetime.now(timezone.utc).isoformat()


def emit(context, event, **fields):
    if context is None:
        return
    row = dict(schema_version=1, run_id=context.run_id, event=event,
               monotonic_s=time.perf_counter(), utc=now(), **fields)
    with LOCK:
        path = context.logs_dir() / 'model_telemetry.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a', encoding='utf8') as stream:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')


def call_record(wrapper, result, started, started_at, error=None):
    """One canonical call receipt. Unknown semantics are never inferred from EOS."""
    result = result or {}
    usage = getattr(wrapper, '_generation_usage', {})
    if not getattr(wrapper, '_generation_call_id', None) and not result.get('call_id') and not usage:
        emit(getattr(wrapper, 'run_context', None), 'semantic_task_without_dispatch',
             agent=wrapper.name, failure_category=error)
        return
    parsed = result.get('parsed')
    items = parsed.get('items') if isinstance(parsed, dict) else None
    identity = getattr(wrapper, '_model_identity', {})
    duration = time.perf_counter() - started
    timing = getattr(wrapper, '_backend_timing', {})
    service_start = timing.get('start', started)
    service_end = timing.get('end', started+duration)
    generation = usage.get('generation_seconds')
    count = usage.get('output_tokens')
    valid = getattr(wrapper, '_observed_contract_valid', None)
    row = dict(call_id=result.get('call_id') or getattr(wrapper, '_generation_call_id', None) or uuid.uuid4().hex,
        agent=wrapper.name, logical_role=wrapper.name, backend=wrapper.backend,
        model_id=wrapper.model, designation={'local_producer': 'producer', 'local_auditor': 'auditor'}.get(wrapper.backend),
        model_revision=None, adapter_checkpoint=None, adapter_sha256=None, head_sha256=None,
        normalization_sha256=None, runtime_engine=None, **{})
    row.update(identity)
    row.update(task_id=getattr(wrapper, '_observation_task', None),
        wave_id=getattr(wrapper, '_observation_wave', None), phase=getattr(wrapper, '_telemetry_phase', None),
        parent_call_ids=getattr(wrapper, '_parent_call_ids', []),
        queued_at=None, started_at=timing.get('started_at', started_at), first_token_at=None,
        generation_finished_at=usage.get('generation_finished_at'), completed_at=now(),
        start_monotonic_s=service_start, end_monotonic_s=service_end,
        queue_wait_seconds=None, dependency_wait_seconds=None,
        time_to_first_token_seconds=usage.get('time_to_first_token_seconds'),
        generation_seconds=generation, decode_seconds=None, total_service_seconds=service_end-service_start,
        enclosing_task_seconds=duration,
        input_tokens=usage.get('input_tokens'), output_tokens=count,
        requested_max_output_tokens=usage.get('requested_max_output_tokens'),
        finish_reason=usage.get('finish_reason'), cap_hit=usage.get('cap_hit'), truncated=usage.get('truncated'),
        tokens_per_second=count/generation if count is not None and generation and generation > 0 else None,
        throughput_basis='generation including prefill', backend_success=usage.get('backend_success'),
        contract_valid=valid, semantically_complete=result.get('complete'),
        emitted_count=len(items) if isinstance(items, list) else None,
        retained_count=None, refused=isinstance(parsed, dict) and parsed.get('status') == 'refused',
        empty_output=None if items is None else not bool(items),
        retry_count=getattr(wrapper, '_partition_attempt', usage.get('backend_retry_count')),
        failure_category=error or ('contract_invalid' if valid is False else
            'backend_failure' if usage.get('backend_success') is False else None),
        unavailable={})
    for key, value in row.items():
        if value is None:
            row['unavailable'][key] = ('Join scheduler task events' if key in
                {'queued_at','queue_wait_seconds','dependency_wait_seconds'} else
                'No deterministic downstream retention receipt' if key == 'retained_count' else
                'Not reported or not deterministically observable')
    emit(getattr(wrapper, 'run_context', None), 'model_call', **row)


def union(intervals):
    result = []
    for start, end in sorted(intervals):
        if not (math.isfinite(start) and math.isfinite(end) and end >= start):
            raise ValueError('Invalid timing interval')
        if result and start <= result[-1][1]:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return sum(b-a for a,b in result)


def critical_path(nodes):
    """Observed DAG: dependency AND lane-order edges, service plus explicit gaps.

    Returns one of possibly tied longest paths. Contribution is descriptive,
    not the counterfactual speedup from removing a model or role.
    """
    pending = {n['id']: n for n in nodes}
    if len(pending) != len(nodes):
        raise ValueError('Duplicate DAG identity')
    done = {}
    origin = min((n['start'] for n in nodes), default=0)
    while pending:
        progress = False
        for key, n in list(pending.items()):
            parents = n.get('parents', [])
            if any(p not in done for p in parents):
                continue
            if n['end'] < n['start'] or any(done[p]['end'] > n['start'] + 1e-6 for p in parents):
                raise ValueError('DAG timing violates dependency')
            parent = max(parents, key=lambda p: (done[p]['end'], p), default=None)
            prior = done[parent] if parent else dict(path=[], end=origin, service=0, gap=0)
            done[key] = dict(path=prior['path']+[key], end=n['end'],
                service=prior['service']+n['end']-n['start'],
                gap=prior['gap']+n['start']-prior['end'])
            del pending[key]
            progress = True
        if not progress:
            raise ValueError('Missing dependency or cycle')
    end = max(done, key=lambda k: (done[k]['end'], k), default=None)
    chosen = done[end] if end else dict(path=[], service=0, gap=0, end=origin)
    return dict(members=chosen['path'], service_seconds=chosen['service'],
        gap_seconds=chosen['gap'], elapsed_seconds=chosen['end']-origin,
        interpretation='Observed dependency and lane order; gaps separate; not counterfactual marginal latency')


def cost(records):
    infrastructure, api = [], []
    for row in records:
        if row.get('event') == 'infrastructure_cost':
            seconds = row['active_end_epoch']-row['active_start_epoch']
            rate = row['hourly_rate']
            if not all(math.isfinite(v) and v >= 0 for v in (seconds, rate)):
                raise ValueError('Invalid infrastructure cost interval')
            infrastructure.append(seconds * rate / 3600)
        if row.get('event') == 'api_cost' and row.get('estimated_cost') is not None:
            api.append(row['estimated_cost'])
    return dict(infrastructure_estimate=sum(infrastructure) if infrastructure else None,
        model_api_estimate=sum(api) if api else None,
        combined_estimate=sum(infrastructure)+sum(api) if infrastructure and api else None,
        invoice=False, unavailable='Missing cost categories remain unknown; record explicit zero when applicable')


def summarize(raw, scheduler=()):
    calls = [dict(r) for r in raw if r['event'] == 'model_call']
    recorded_ids = {r['call_id'] for r in calls}
    for r in raw:
        if r['event'] == 'physical_backend_receipt' and r['call_id'] not in recorded_ids:
            calls.append(dict(r, agent=r['agent'], designation=r.get('designation'), wave_id=None,
                task_id=None, parent_call_ids=[], emitted_count=None, retained_count=None,
                contract_valid=None, failure_category=None if r['backend_success'] else 'backend_failure'))
            recorded_ids.add(r['call_id'])
    retained = {}
    for row in raw:
        if row['event'] == 'retention_snapshot':
            retained.update(row['call_counts'])
    for row in calls:
        if row['call_id'] in retained:
            row['retained_count'] = retained[row['call_id']]
    intervals = [(r['start_monotonic_s'], r['end_monotonic_s']) for r in calls]
    changes = [(a,1) for a,b in intervals] + [(b,-1) for a,b in intervals]
    active = maximum = 0
    for _, delta in sorted(changes):
        active += delta
        maximum = max(maximum, active)
    totals = defaultdict(float)
    agents = defaultdict(float)
    for r in calls:
        totals[r.get('designation') or 'other'] += r['total_service_seconds']
        agents[r['agent']] += r['total_service_seconds']
    task_events = defaultdict(dict)
    for event in scheduler:
        if 'task' in event:
            task_events[event['task']][event['event']] = event
    nodes, lane_last = [], {}
    for key, events in sorted(task_events.items(), key=lambda kv: kv[1].get('task_start', {}).get('monotonic_s', float('inf'))):
        if not {'task_start', 'task_end', 'queued'} <= events.keys():
            continue
        start, end = events['task_start'], events['task_end']
        lane = start.get('worker')
        parents = [e['parent'] for e in events['queued']['edges']]
        if lane in lane_last:
            parents.append(lane_last[lane])
        nodes.append(dict(id=key, start=start['monotonic_s'], end=end['monotonic_s'], parents=sorted(set(parents))))
        lane_last[lane] = key
    try:
        path = critical_path(nodes) if nodes else None
        path_error = None if nodes else 'No complete scheduler DAG'
    except ValueError as exc:
        path, path_error = None, str(exc)
    by_call = {r['call_id']: r for r in calls}
    handoffs = []
    for r in calls:
        for parent_id in r.get('parent_call_ids', []):
            p = by_call.get(parent_id)
            if p is not None:
                handoffs.append(dict(parent=parent_id, child=r['call_id'],
                    seconds=r['start_monotonic_s']-p['end_monotonic_s'],
                    parent_role=p.get('designation'), child_role=r.get('designation')))
    resources = [r for r in raw if r['event'] == 'resource_sample']
    def series(key):
        vals = [r[key] for r in resources if isinstance(r.get(key), (float,int))]
        return dict(samples=len(vals), peak=max(vals) if vals else None,
                    median=statistics.median(vals) if vals else None)
    begins = [r for r in raw if r['event'] == 'pipeline_start']
    ends = [r for r in raw if r['event'] == 'pipeline_end']
    phases, opened = [], {}
    for e in scheduler:
        if e['event'] == 'phase_enter':
            opened[e['phase']] = e['monotonic_s']
        elif e['event'] == 'phase_exit' and e['phase'] in opened:
            phases.append(dict(phase=e['phase'], seconds=e['monotonic_s']-opened.pop(e['phase'])))
    def known_sum(key):
        values = [r[key] for r in calls if r.get(key) is not None]
        return dict(value=sum(values) if values else None, measured_calls=len(values), total_calls=len(calls))
    membership = set(path['members']) if path else set()
    contributions = defaultdict(float)
    for r in calls:
        if r.get('task_id') in membership:
            contributions[r.get('designation') or 'other'] += r['total_service_seconds']
    generations = [(r['start_monotonic_s'],r['end_monotonic_s']) for r in raw if r['event']=='generation_interval']
    pair_rows = [r for r in raw if r['event']=='auditor_pair']
    coverage = [r for r in raw if r['event']=='auditor_pair_coverage']
    joined = [item for r in raw if r['event']=='auditor_verifier_join' for item in r['findings']]
    pair_call_ids = {r['classifier_call_id'] for r in pair_rows}
    pair_calls = [r for r in calls if r['call_id'] in pair_call_ids]
    waves = {}
    for r in calls:
        wave = r.get('wave_id')
        if wave:
            interval = waves.setdefault(wave,dict(start=r['start_monotonic_s'],end=r['end_monotonic_s'],call_ids=[]))
            interval['start']=min(interval['start'],r['start_monotonic_s'])
            interval['end']=max(interval['end'],r['end_monotonic_s'])
            interval['call_ids'].append(r['call_id'])
    barriers=[]
    for e in scheduler:
        if e['event']=='phase_enter':
            required=e.get('required_tasks',[])
            auditor_tasks={r['task_id'] for r in calls if r.get('designation')=='auditor' and r.get('task_id') in required}
            auditor_ends=[task_events[t]['task_end']['monotonic_s'] for t in auditor_tasks if 'task_end' in task_events[t]]
            barriers.append(dict(consumer_phase=e['phase'],required_task_ids=required,
                auditor_task_ids=sorted(auditor_tasks), consumer_enter_monotonic_s=e['monotonic_s'],
                after_latest_auditor_seconds=e['monotonic_s']-max(auditor_ends) if auditor_ends else None,
                interpretation='Observed completion-to-consumer interval, not counterfactual avoidable wait'))
    pairing=dict(producer_items=sum(r['producer_items'] for r in coverage),pairs_constructed=len(pair_rows),
        eligible_producer_items=sum(r.get('eligible_producer_items',0) for r in coverage),
        unavailable=sum(r['unavailable_items'] for r in coverage),classifier_calls=len(pair_calls),
        classifier_forwards=sum(r.get('forward_attempted') is True for r in pair_rows),
        forward_count_unknown=sum(r.get('forward_attempted') is None for r in pair_rows),
        classifier_failures=sum(r['classifier_status']=='failed' for r in pair_rows),
        relation_distribution={label:sum(r.get('auditor_relation')==label for r in pair_rows)
                               for label in ('MATCH','DIVERGENCE','OMISSION','ADDITION')},
        classifier_service_seconds=sum(r['total_service_seconds'] for r in pair_calls),
        joined_findings=sum(r['auditor_pair_id'] is not None for r in joined),
        unjoined_findings=sum(r['auditor_pair_id'] is None for r in joined),
        agreements=sum(r['agreement']=='agree' for r in joined),disagreements=sum(r['agreement']=='disagree' for r in joined),
        producer_to_auditor=[h for h in handoffs if h['child'] in pair_call_ids],
        auditor_to_verifier=[h for h in handoffs if h['parent'] in pair_call_ids],
        interpretation='Advisory pair and independent finding layers; disagreement is not an error label')
    return dict(schema_version=1, pipeline_wall_seconds=ends[-1]['monotonic_s']-begins[0]['monotonic_s'] if begins and ends else None,
        process_cpu_seconds=ends[-1].get('process_cpu_seconds') if ends else None,
        call_wall_union_seconds=union(intervals), service_totals=dict(totals), per_agent_service=dict(agents),
        semantic_critical_path=path, critical_path_unavailable=path_error,
        critical_path_model_service=dict(contributions), generation_wall_union_seconds=union(generations) if generations else None,
        auditor_pairing=pairing, wave_intervals=waves, consumer_barriers=barriers,
        phase_latencies=phases, wave_count=len({r['wave_id'] for r in calls if r.get('wave_id')}),
        maximum_concurrency=maximum, handoffs=handoffs,
        scheduler_wait_seconds=sum(e.get('scheduler_wait_s',0) for e in scheduler if e['event']=='assigned'),
        scheduler_lane_idle_seconds=sum(e.get('worker_idle_s',0) for e in scheduler if e['event']=='assigned'),
        scheduler_timing_available=bool(scheduler),
        input_tokens=known_sum('input_tokens'), output_tokens=known_sum('output_tokens'),
        emitted=known_sum('emitted_count'), retained=known_sum('retained_count'),
        counts={key:sum(r.get(key) is True for r in calls) for key in ('cap_hit','truncated','contract_valid','empty_output','refused')},
        failed_calls=sum(r.get('failure_category') is not None for r in calls),
        resources={k:series(k) for k in ('gpu_utilization','vram_used_bytes','gpu_power_watts','process_cpu_percent','system_cpu_percent',
            'process_rss_bytes','system_ram_used_bytes','system_ram_free_bytes','swap_used_bytes','cuda_allocated_bytes','cuda_reserved_bytes')},
        model_lifecycle=[e for e in scheduler if e['event'] in {'model_load_start','model_load_end','model_resident','model_evicted'}],
        costs=cost(raw), caveats=['Service sums include overlap; wall union does not.',
            'EOS establishes transport completion, not semantic correctness.',
            'Resource peaks are sampled peaks at recorded intervals; CPU time includes inference and telemetry.'])


class Sampler:
    def __init__(self, context, interval=2.0):
        if interval < 1:
            raise ValueError('Resource interval must be at least one second')
        self.context, self.interval, self.stop = context, interval, threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True, name='shimmer-resources')
        self.thread.start()

    def run(self):
        try:
            import psutil
            process = psutil.Process()
            process.cpu_percent(None)
            psutil.cpu_percent(None)
        except ImportError:
            psutil = process = None
        while not self.stop.wait(self.interval):
            row = dict(sampling_interval_seconds=self.interval, gpu_utilization=None, vram_used_bytes=None,
                gpu_power_watts=None, gpu_identity=None, cuda_allocated_bytes=None, cuda_reserved_bytes=None,
                process_cpu_percent=None, system_cpu_percent=None, process_rss_bytes=None,
                system_ram_used_bytes=None, system_ram_free_bytes=None, swap_used_bytes=None, unavailable={})
            row['active_semantic_calls'] = getattr(self.context, '_active_model_calls', 0)
            scheduler = getattr(self.context, '_telemetry_scheduler', None)
            row['queued_calls'] = max(0, len(scheduler.tasks)-len(scheduler.outcomes)-len(scheduler._inflight)) if scheduler else None
            if psutil:
                mem = psutil.virtual_memory()
                row.update(process_cpu_percent=process.cpu_percent(None), system_cpu_percent=psutil.cpu_percent(None),
                    process_rss_bytes=process.memory_info().rss, system_ram_used_bytes=mem.used,
                    system_ram_free_bytes=mem.available, swap_used_bytes=psutil.swap_memory().used)
            try:
                answer = subprocess.run(['nvidia-smi','--query-gpu=uuid,name,utilization.gpu,memory.used,power.draw',
                    '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=1, check=True)
                gpus = []
                for line in answer.stdout.splitlines():
                    uid, name, util, mem, power = [s.strip() for s in line.split(',')]
                    def number(s):
                        try: return float(s)
                        except ValueError: return None
                    gpus.append(dict(uuid=uid, name=name, utilization=number(util), memory_mib=number(mem), power_watts=number(power)))
                row['gpus'] = gpus
                if len(gpus) == 1:
                    g = gpus[0]
                    row.update(gpu_identity=g['uuid']+'/'+g['name'], gpu_utilization=g['utilization'],
                        vram_used_bytes=g['memory_mib']*1024**2 if g['memory_mib'] is not None else None, gpu_power_watts=g['power_watts'])
            except (OSError, subprocess.SubprocessError):
                pass
            torch = sys.modules.get('torch')
            if torch is not None and torch.cuda.is_initialized():
                row['cuda_allocated_bytes'] = sum(torch.cuda.memory_allocated(i) for i in range(torch.cuda.device_count()))
                row['cuda_reserved_bytes'] = sum(torch.cuda.memory_reserved(i) for i in range(torch.cuda.device_count()))
            row['unavailable'] = {k:'Sampler provider unavailable or multi-device scalar undefined' for k,v in row.items() if v is None}
            emit(self.context, 'resource_sample', **row)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)


def recompute(run_dir):
    directory = Path(run_dir)
    def read(path):
        return [json.loads(line) for line in path.read_text(encoding='utf8').splitlines() if line] if path.exists() else []
    raw = read(directory/'logs/model_telemetry.jsonl')
    raw += [dict(event='api_cost', estimated_cost=r['cost_usd']) for r in read(directory/'logs/cost_tracker.jsonl') if 'cost_usd' in r]
    raw += read(directory/'audit/infrastructure_cost.jsonl')
    value = summarize(raw, read(directory/'audit/execution_topology.jsonl'))
    path = directory/'audit/model_telemetry_summary.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n', encoding='utf8')
    return value


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Recompute summary from saved raw evidence; never run a model')
    parser.add_argument('run_dir')
    recompute(parser.parse_args().run_dir)
