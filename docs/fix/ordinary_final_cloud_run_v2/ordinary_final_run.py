"""Sealed ordinary run admission and evidence assessment. No provisioning API.

Import and --verify are model-free. --execute requires a new manifest-bound
operator authorization and consumes one exclusive claim before any model load.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import threading
import time


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def require(value, message):
    if not value:
        raise RuntimeError(message)


def cache_ref_bytes(model):
    """Hub refs are exact revision bytes, not newline-terminated text files."""
    revision = model['revision']
    require(isinstance(revision, str) and re.fullmatch(r'[0-9a-f]{40}', revision),
            'Invalid pinned cache revision')
    return revision.encode('ascii')


def admit_cache_ref(directory, model):
    expected = cache_ref_bytes(model)
    require(model['cache_ref'] == dict(bytes=len(expected), sha256=hashlib.sha256(expected).hexdigest()),
            'Cache ref manifest mismatch')
    require((Path(directory)/'refs/main').read_bytes() == expected,
            'Cache ref must equal exact pinned revision bytes (no whitespace)')


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n', encoding='utf8')


def verify(base):
    base = Path(base).resolve()
    manifest = read(base/'execution_manifest.json')
    seal = read(base/'seal.json')
    require(seal['execution_manifest_sha256'] == sha(base/'execution_manifest.json'), 'Manifest seal mismatch')
    require(manifest['max_runs'] == 1 and manifest['model_mode'] == 'final', 'Ordinary final run only')
    require(manifest['multi_round'] is False and manifest['protected_test'] is False, 'Excluded workload')
    require(manifest['argv'] == ARGV, 'Run flags changed')
    require(manifest['topology'] == TOPOLOGY, 'Residency topology changed')
    for key,value in {'SHIMMER_MODEL_MODE':'final','SHIMMER_BACKEND_PROFILE':'local',
                      'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','CUBLAS_WORKSPACE_CONFIG':':4096:8'}.items():
        require(manifest['environment'].get(key)==value,'Runtime environment changed: '+key)
    project = base/'project'
    expected = manifest['project_files']
    # A fresh allowlisted project is essential: ambient input/durable data must
    # never join the selected corpus, even if the expected files still match.
    actual = {p.relative_to(project).as_posix() for p in project.rglob('*') if p.is_file()}
    require(actual == set(expected), 'Unexpected or missing project files')
    for name, digest in expected.items():
        p = project/name
        require(not p.is_symlink() and sha(p) == digest, 'Project hash mismatch: '+name)
    for name, digest in manifest['support_files'].items():
        require(sha(base/name) == digest, 'Support hash mismatch: '+name)
    return manifest


ARGV = ['--backend-profile', 'local', '--activation-profile', 'dense',
        '--review-mode', 'paired', '--task', 'review', '--mode', 'standalone',
        '--non-interactive', '--skip-confirmation', '--sensitivity-layer-inactive-override',
        '--no-redaction-override', '--execution-topology', 'report_optimized',
        '--topology-config', 'topology.json', '--agent-briefs', 'enabled',
        '--input-language', 'auto', '--output-language', 'en']
TOPOLOGY = {'schema_version': 1, 'lanes': [
    {'name': 'primary', 'device': 'cuda:0', 'resident_limit': 1}]}


def authorization(base, manifest, permit, now=None):
    now = time.time() if now is None else now
    require(permit.get('operator_authorized') is True and
            permit.get('action') == 'one-ordinary-final-cloud-run', 'New explicit authorization required')
    require(permit.get('execution_manifest_sha256') == sha(Path(base)/'execution_manifest.json'), 'Authorization manifest mismatch')
    require(permit.get('seal_sha256') == sha(Path(base)/'seal.json'), 'Authorization seal mismatch')
    require(permit.get('source_commit') == manifest['source_commit'], 'Authorization source mismatch')
    require(permit.get('soft_budget_usd') == manifest['soft_budget_usd'] and
            permit.get('hard_ceiling_usd') == manifest['hard_ceiling_usd'], 'Budget authorization mismatch')
    require(permit.get('provider') == 'Lambda' and permit.get('instance_type') == 'gpu_1x_a10'
            and permit.get('region') == 'us-east-1', 'Instance authorization mismatch')
    require(isinstance(permit.get('instance_id'),str) and
            re.fullmatch(r'[a-f0-9]{32}|[a-f0-9-]{36}',permit['instance_id']), 'Instance ID required')
    require(0 < permit['hourly_rate'] <= manifest['max_hourly_rate'], 'Price exceeds ceiling')
    start = permit['active_start_epoch']
    require(isinstance(start, (int, float)) and 0 < start <= now, 'Invalid billing start')
    require(now < start + manifest['hard_ceiling_usd']/permit['hourly_rate']*3600 - 900,
            'Insufficient execution/collection reserve')


def assess(completion, raw):
    reasons = []
    if not (completion and completion.get('state') == 'completed' and
            completion.get('reached_end') is True and completion.get('exit_code') == 0):
        reasons.append('pipeline_not_completed')
    if not (sum(r['event']=='pipeline_start' for r in raw)==1 and
            sum(r['event']=='pipeline_end' for r in raw)==1 and
            any(r['event']=='model_call' and r.get('adapter_checkpoint')==168 for r in raw)):
        reasons.append('required_telemetry_missing')
    if any(r['event'] == 'auditor_pair' and r.get('classifier_status') == 'failed' for r in raw):
        reasons.append('auditor_pair_failure')
    # PROCESSOR already has a bounded partition-recovery contract. Its terminal
    # merged completeness is enforced by RunCompletion; a recovered attempt must
    # remain visible without undoing that existing policy.
    if any(r['event'] == 'model_call' and r.get('contract_valid') is False and r.get('agent')!='PROCESSOR' for r in raw):
        reasons.append('required_contract_failure')
    if any(r['event'] == 'backend_invocation' and r.get('backend_success') is False and r.get('agent')!='PROCESSOR' for r in raw):
        reasons.append('backend_failure')
    # Refusal, unavailable ownership and structural disagreement are observations,
    # never fabricated findings or new semantic rejection criteria.
    return {'execution_integrity_passed': not reasons, 'reasons': reasons,
            'failed_backend_attempts':sum(r['event']=='backend_invocation' and r.get('backend_success') is False for r in raw),
            'collection_and_teardown_pending': True, 'quality_claim': None}


def installed_runtime(manifest, distribution=None):
    if distribution is None:
        import importlib.metadata
        distribution=importlib.metadata.distribution
    for package,version in manifest['packages'].items():
        require(distribution(package).version==version,'Package mismatch: '+package)
    for package,files in manifest['runtime_file_hashes'].items():
        dist=distribution(package)
        for name,digest in files.items():
            require(sha(dist.locate_file(name))==digest,'Installed runtime hash mismatch: '+package)


def hardware_admission(base, torch, psutil):
    require(torch.cuda.device_count()==1,'Exactly one GPU required')
    props=torch.cuda.get_device_properties(0)
    free,total=torch.cuda.mem_get_info(0)
    memory=psutil.virtual_memory()
    value=dict(gpu_name=props.name,gpu_total_bytes=total,gpu_free_bytes=free,
               cpu_count=psutil.cpu_count(),ram_total_bytes=memory.total,ram_available_bytes=memory.available,
               disk_free_bytes=shutil.disk_usage(base).free)
    require('A10' in props.name and total>=23_000_000_000 and free>=20*2**30,'A10 memory admission')
    require(value['cpu_count']>=30 and memory.total>=190*2**30 and memory.available>=40*2**30,'Host resource admission')
    require(value['disk_free_bytes']>=30*2**30,'Storage admission')
    return value


def execute(base):
    base = Path(base).resolve()
    manifest = verify(base)
    require(sys.platform == 'linux', 'Remote Linux execution only')
    permit = read(base/'operator_authorization.json')
    authorization(base, manifest, permit)
    require((base/'WATCHDOG_ARMED.json').is_file(), 'Independent operator watchdog required')
    watch = read(base/'WATCHDOG_ARMED.json')
    require(watch.get('execution_manifest_sha256') == sha(base/'execution_manifest.json') and
            watch.get('instance_id') == permit.get('instance_id') and
            0 <= time.time()-watch.get('heartbeat_epoch', 0) < 30, 'Watchdog not current')
    with (base/'RUN_CLAIMED').open('x', encoding='utf8') as stream:
        stream.write(str(time.time()))
    deadline = permit['active_start_epoch'] + manifest['hard_ceiling_usd']/permit['hourly_rate']*3600 - 900
    def budget_stop():
        time.sleep(max(0, deadline-time.time()))
        write(base/'BUDGET_WORKLOAD_STOP.json', {'epoch':time.time(), 'completed':False})
        # A blocked CUDA call must not outlive the collection reserve. Raw
        # telemetry is append-and-close; this is never reported as completion.
        os._exit(124)
    threading.Thread(target=budget_stop, name='ordinary-budget-stop', daemon=True).start()
    project = base/'project'
    for key in list(os.environ):
        if key.startswith(('SHIMMER_', 'HF_', 'TRANSFORMERS_')) or key.endswith(('API_KEY','TOKEN','SECRET','PASSWORD')):
            os.environ.pop(key, None)
    os.environ.update(manifest['environment'])
    os.environ.update(HF_HOME=str(base/'hf_cache'), HF_HUB_CACHE=str(base/'hf_cache/hub'),
                      PYTHONDONTWRITEBYTECODE='1')
    # Fresh cache refs are bound to the exact snapshots; no ambient cache used.
    cache = base/'hf_cache/hub'
    for model in manifest['models']:
        directory = cache/('models--'+model['model_id'].replace('/','--'))
        admit_cache_ref(directory, model)
        snapshot = directory/'snapshots'/model['revision']
        require({p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file()} == set(model['files']), 'Unsealed cache files')
        for name, entry in model['files'].items():
            require(sha(snapshot/name) == entry['sha256'], 'Model cache hash mismatch')
    sys.path[:0] = [str(project/'scripts'), str(project/'tools')]
    os.chdir(project)
    # Verify all pinned packages before importing pipeline/model libraries.
    installed_runtime(manifest)
    import final_models
    final_models.admit_ordinary()
    import psutil
    write(base/'hardware_admission.json',hardware_admission(base,sys.modules['torch'],psutil))
    from cloud_run_observer import Recorder, deny_network
    evidence = base/'evidence'
    evidence.mkdir(exist_ok=False)
    rec = Recorder(evidence/'network.jsonl')
    deny_network(rec)
    # Every inherited runtime flag was removed; only the manifest flags survive.
    argv = list(ARGV)
    argv[argv.index('--topology-config')+1] = str(base/'topology.json')
    argv += ['--output-dir', str(evidence/'run')]
    code = 1
    try:
        import pipeline
        code = pipeline.main(argv)
    except BaseException as exc:
        write(evidence/'terminal_error.json', {'error_type': type(exc).__name__})
    finally:
        rec.close()
        import model_telemetry, run_completion
        # The runtime may rename its output folder at completion.
        directories = [p.parent.parent for p in evidence.rglob('audit/run_completion.json')]
        if len(directories) == 1:
            directory = directories[0]
            raw = [json.loads(line) for line in (directory/'logs/model_telemetry.jsonl').read_text(encoding='utf8').splitlines() if line]
            result = assess(run_completion.read(directory), raw)
            model_telemetry.recompute(directory)
        else:
            result = assess(None, [])
        result['pipeline_exit_code'] = code
        write(evidence/'result.json', result)
    return 0 if code == 0 and result['execution_integrity_passed'] else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        raise SystemExit(execute(args.bundle))
    verify(args.bundle)
    print('Sealed project verified; no execution authorized or performed')
