"""Offline, supervised short-burst validation through Shimmer's real loader.

Never imports pipeline or reads operator documents. Authored fixture only.
The supervisor terminates its own child on low RAM or a phase timeout.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DOC = 'bounded-local-fixture'
SOURCE = ('CLM-001: Planned capacity is 120 units (REF-0001). '
          'CLM-002: Reported capacity is 130 units (REF-0002). '
          'The reporting date is not supplied.\n')


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def response_record(wrapper, result, elapsed, label):
    return dict(label=label, agent=wrapper.name, wall_seconds=elapsed,
                backend_ok=result.ok, usage=result.usage, raw_text=result.raw_text)


def worker(out, auditor_only=False):
    from local_inference_runtime import configure, runtime_evidence
    data = dict(classification='BOUNDED_REAL_MODEL_PROBE_NOT_FULL_RUN', calls=[], loads=[])
    def phase(name):
        write(out / 'phase.json', dict(name=name, started=time.time()))
        write(out / 'real_model_probe.json', data)
        print(name, flush=True)
    phase('runtime_integrity')
    data['environment'] = configure()
    # Fail closed on any attempted socket connection, including local HTTP.
    import socket
    def blocked(*args, **kwargs):
        raise RuntimeError('Network forbidden in local inference probe')
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    import torch
    import transformers
    data['runtime'] = runtime_evidence()
    sys.path.insert(0, str(ROOT / 'scripts'))
    import agent_wrapper as aw
    import bounded_extraction as ex
    from constitution import Constitution
    from message_bus import MessageBus
    from run_context import for_run_dir
    cfg = json.loads((ROOT / 'config/local_models.json').read_text())
    contracts = json.loads((ROOT / 'config/agent_contracts.json').read_text())['contracts']
    families = {}
    for role in ('active_producer', 'active_auditor'):
        checkpoint = aw._local_checkpoint_path(cfg[role])
        families[role] = transformers.AutoConfig.from_pretrained(checkpoint, local_files_only=True).model_type
    if families['active_producer'] == families['active_auditor']:
        raise RuntimeError('Independent model families required')
    data['families'] = families
    ctx = for_run_dir(ROOT, out / 'wrapper')
    bus = MessageBus.open(out / 'wrapper/bus.jsonl')
    constitution = Constitution.load(ROOT / 'config/constitution.json')
    def wrapper(name, role):
        return aw.AgentWrapper(name, constitution, bus,
            {name: dict(backend='local_producer' if role == 'active_producer' else 'local_auditor', model=cfg[role])},
            contracts, keys={'offline_probe': True}, run_context=ctx)
    def load(role):
        phase('load_' + role)
        start = time.perf_counter()
        tok, model = aw._load_qwen(cfg[role])
        data['loads'].append(dict(role=role, seconds=time.perf_counter()-start,
            resident_models=list(aw._QWEN_MODELS), device=str(model.device),
            vram_allocated_mib=torch.cuda.memory_allocated()/2**20))
        model.generation_config.do_sample = False
        model.generation_config.max_time = 25.0
        data['generation_policy'] = dict(max_time_seconds=25.0, max_new_tokens=384,
                                         do_sample=False, seed=7)
        return tok, model
    def call(w, label, prompt, native, compact=False):
        phase('generate_' + label)
        w._optimized_semantics = native
        if compact:
            import compact_contracts as cc
            cc.bind_producer(w, spans, DOC)
        elif w.name == 'VERIFIER':
            import compact_contracts as cc
            cc.bind_auditor(w, DOC, ['REF-0001','REF-0002'])
        else:
            for attr in ('_source_adapter','_compact_contract','_compact_role'):
                if hasattr(w, attr):delattr(w, attr)
        torch.manual_seed(7)
        start = time.perf_counter()
        result = w.call_local(prompt, max_new_tokens=384)
        elapsed = time.perf_counter()-start
        row = response_record(w, result, elapsed, label)
        data['calls'].append(row)
        write(out/'real_model_probe.json', data)
        parsed, missing = w.parse_contract_output(result.raw_text)
        items = (parsed or {}).get('items', []) if isinstance(parsed, dict) else []
        reconstruction = ''.join(x.get('draft_text', '') for x in items) == SOURCE if w.name == 'PROCESSOR' else None
        claims = set(x for item in items for x in item.get('claims_referenced', []))
        questions = ' '.join(x for item in items for x in item.get('open_questions', [])).lower()
        semantic = (claims == {'CLM-001', 'CLM-002'} and 'date' in questions) if w.name == 'PROCESSOR' else None
        row.update(contract_valid=not missing, contract_missing=missing,
            source_reconstructed_exactly=reconstruction, semantic_fixture_complete=semantic,
            accepted_semantic_output=(bool(result.ok and not missing and result.usage.get('truncated') is False
                                          and semantic and reconstruction) if w.name == 'PROCESSOR' else None),
            quality_review_status='fixture_checks_only' if w.name == 'PROCESSOR' else 'manual_review_required',
            parsed=parsed)
        write(out/'real_model_probe.json', data)
        return row
    spans = ex.ledger(SOURCE, DOC)
    producer = wrapper('PROCESSOR', 'active_producer')
    prompt = ('Extract the source faithfully. Return one item for the paragraph. '
              'claims_referenced must list all explicit CLM-* ids. open_questions must preserve missing information. '
              'Use ref=REF-0001, kind=extraction, confidence=UNCERTAIN and ref_ids=[REF-0001,REF-0002]. '
              'Set extraction_method=verbatim. Copy all source text exactly into draft_text. '
              'Set section_id=paragraph-1.\n' + producer._output_contract_text() +
              '\nDocument id: ' + DOC + '\nSOURCE:\n' + SOURCE)
    import compact_contracts as cc
    compact_prompt = cc.producer_prompt(spans, spans, DOC)
    if auditor_only:
        data['producer_status'] = 'not_loaded_in_this_probe'
        data['producer_auditor_path_measured'] = False
        compact = dict(parsed=dict(agent='PROCESSOR', doc_id=DOC, items=[dict(
            draft_text=SOURCE, claims_referenced=['CLM-001', 'CLM-002'],
            open_questions=['What is the reporting date?'])]))
        data['auditor_input_provenance'] = 'authored_fixture_not_model_output'
    else:
        tok, model = load('active_producer')
        call(producer, 'monolithic_raw', prompt, False)
        call(producer, 'monolithic_native', prompt, True)
        compact = call(producer, 'compact_native', compact_prompt, True, True)
        del model, tok
    # Record admission separately: shared generate calls are not a supported
    # concurrent-serving adapter. A future batching probe must not be mislabeled
    # as production lane concurrency.
    data['concurrency'] = dict(tested_capacity=1, capacity_2_status='not_admitted',
        capacity_4_status='not_admitted', reason='pending_quality_and_resource_admission',
        duplicate_model_copies=0)
    if not auditor_only and not compact.get('accepted_semantic_output'):
        data['auditor_status'] = 'blocked_incomplete_producer'
        write(out/'real_model_probe.json', data)
        phase('complete')
        return
    load('active_auditor')
    auditor = wrapper('VERIFIER', 'active_auditor')
    audit_prompt = cc.auditor_prompt(SOURCE, compact['parsed'], ['REF-0001','REF-0002'])
    call(auditor, 'independent_verifier', audit_prompt, True)
    phase('complete')


def supervise(out, auditor_only=False):
    import psutil
    if out.exists() and any(out.iterdir()):
        raise ValueError('Probe output directory must be fresh; preserve previous evidence')
    out.mkdir(parents=True, exist_ok=True)
    samples = []
    reason = None
    with (out/'worker.log').open('w', encoding='utf-8') as log:
        child = subprocess.Popen([sys.executable, '-I', '-B', '-u', str(Path(__file__).resolve()),
                                  '--worker', '--output', str(out)] + (['--auditor-only'] if auditor_only else []),
                                  cwd=ROOT, stdout=log, stderr=log,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        process = psutil.Process(child.pid)
        process.cpu_percent()
        low = 0
        while child.poll() is None:
            memory = psutil.virtual_memory()
            row = dict(time=time.time(), available_ram_gib=memory.available/2**30,
                       system_cpu_percent=psutil.cpu_percent())
            try:
                row.update(process_rss_mib=process.memory_info().rss/2**20,
                           process_cpu_percent=process.cpu_percent())
            except psutil.NoSuchProcess:
                break
            try:
                gpu = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,temperature.gpu',
                    '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=3)
                util, vram, temperature = map(float, gpu.stdout.strip().splitlines()[0].split(','))
                row.update(gpu_utilization_percent=util, vram_used_mib=vram, gpu_temperature_c=temperature)
                if temperature >= 85:
                    reason = 'gpu_temperature_guard'
            except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
                row['gpu_sample_unavailable'] = True
            try:
                phase = json.loads((out/'phase.json').read_text())
                row['phase'] = phase['name']
                limit = 180 if phase['name'] == 'runtime_integrity' else 120 if phase['name'].startswith('load_') else 45
                if time.time()-phase['started'] > limit:
                    reason = 'phase_timeout:' + phase['name']
            except (OSError, ValueError):
                pass
            samples.append(row)
            low = low+1 if memory.available < 1.25*2**30 else 0
            if low >= 2:
                reason = 'available_ram_below_1.25_gib'
            if reason:
                child.terminate()
                break
            time.sleep(1)
        code = child.wait(timeout=10)
    write(out/'resources.json', dict(samples=samples, stop_reason=reason, exit_code=code,
        sampling='approximately_1_second_plus_sensor_latency_not_instantaneous_peaks'))
    print(json.dumps(dict(exit_code=code, stop_reason=reason, output=str(out))))
    return code


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--auditor-only', action='store_true', help='Standalone authored-fixture auditor probe; no producer load')
    a = p.parse_args()
    # -I removes the script directory as well as user-site/PYTHONPATH pollution.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if a.worker:
        worker(a.output.resolve(), a.auditor_only)
    else:
        sys.exit(supervise(a.output.resolve(), a.auditor_only))
