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


HEX64 = r'[0-9a-f]{64}'
CASE_MANIFEST = 'case_manifest.json'
EXPOSED_NO_MANIFEST = 'exposed, no manifest'
# The live case manifest (S2b item 2): the multi-round manifest schema version 1 of
# scripts/multi_round.py, with exactly these top-level fields, `fixture` false, and every
# source span measured on the bundled LF-normalised document bytes. A fixture (synthetic,
# pre-authored outputs, documents carried inside the file) is refused in a live run.
LIVE_CASE_FIELDS = frozenset({'schema_version', 'case_id', 'fixture', 'allow_recommendations',
                              'decision_support_mode', 'rounds', 'actors', 'issues', 'sources'})


def _multi_round_module():
    try:
        import multi_round
    except ImportError:
        sys.path.append(str(Path(__file__).resolve().parents[1]/'scripts'))
        import multi_round
    return multi_round


def validate_live_case_manifest(value, documents=None):
    """The live case manifest, or a one-line refusal naming the rule, never the content.

    `documents` maps a document id (a context file name without its extension) to its
    LF-normalised text; with it, every round's documents must exist and every source quote
    must equal the text between char_start and char_end exactly, as bind_sources requires
    at run time, so a sealed case cannot fail forty minutes into a rented instance."""
    require(isinstance(value, dict), 'Case manifest must be an object')
    require(set(value) <= LIVE_CASE_FIELDS, 'Case manifest carries a field outside the live schema')
    require(value.get('fixture') is False, 'Fixture case manifest refused in a live run')
    mr = _multi_round_module()
    try:
        checked = mr.validate_manifest(value)
    except mr.InvalidState as exc:
        raise RuntimeError('Invalid case manifest: ' + str(exc)) from None
    if documents is not None:
        for round_ in checked['rounds']:
            for doc in round_['document_ids']:
                require(doc in documents, 'Case document missing from the bundle: a round names an absent document')
        for source in checked['sources']:
            text = documents[source['document_id']]
            require(text[source['char_start']:source['char_end']] == source['quote'],
                    'Case source span does not match the bundled document text')
    return checked


def argv_for(manifest):
    """The one sealed flag list for the workload the manifest declares."""
    return MULTI_ROUND_ARGV if manifest.get('multi_round') is True else ARGV


def admit_workload(manifest, seal, base=None):
    """Replaces the old blanket refusal ('Excluded workload') of multi-round and protected
    tests: each is admitted exactly when it is DECLARED in the manifest, SEALED (bound by a
    hash the seal covers) and VALID, and an undeclared one is refused as before. A bundle can
    never claim more than it was sealed with."""
    require(type(manifest.get('multi_round')) is bool and type(manifest.get('protected_test')) is bool,
            'Workload declaration must be explicit')
    exposure = seal.get('exposure', 'exposed')
    require(exposure in ('exposed', 'sealed'), 'Unknown exposure in the seal')
    if exposure == 'sealed':
        # Sealed runs only: declared sealed, the test archive hash the bundle was built from
        # equals the seal's, and the code commit equals the seal's (the frozen tag's commit,
        # resolved by the controller before launch).
        require(isinstance(seal.get('test_manifest_sha256'), str) and re.fullmatch(HEX64, seal['test_manifest_sha256'])
                and isinstance(manifest.get('test_archive_sha256'), str)
                and seal.get('test_archive_sha256') == manifest['test_archive_sha256']
                and seal.get('code_commit') == manifest['source_commit'], 'Sealed declaration not bound to its test')
    else:
        # Exposed runs behave as before: no protected test.
        require(manifest['protected_test'] is False, 'Protected test requires a sealed run')
        require(seal.get('test_manifest_sha256', EXPOSED_NO_MANIFEST) == EXPOSED_NO_MANIFEST,
                'An exposed run carries no test manifest')
    support = manifest.get('support_files', {})
    if manifest['multi_round']:
        digest = manifest.get('case_manifest_sha256')
        require(isinstance(digest, str) and re.fullmatch(HEX64, digest) and support.get(CASE_MANIFEST) == digest,
                'Multi-round declared without its sealed case manifest')
        if base is not None:
            require(sha(Path(base)/CASE_MANIFEST) == digest, 'Case manifest changed')
            case = read(Path(base)/CASE_MANIFEST)
            require(isinstance(case, dict) and case.get('fixture') is False, 'Fixture case manifest refused in a live run')
            require(set(case) <= LIVE_CASE_FIELDS, 'Case manifest carries a field outside the live schema')
    else:
        require('case_manifest_sha256' not in manifest and CASE_MANIFEST not in support,
                'Case manifest sealed without a multi-round declaration')
    require(manifest['argv'] == argv_for(manifest), 'Run flags changed')
    return dict(multi_round=manifest['multi_round'], protected_test=manifest['protected_test'], exposure=exposure)


def verify(base):
    base = Path(base).resolve()
    manifest = read(base/'execution_manifest.json')
    seal = read(base/'seal.json')
    require(seal['execution_manifest_sha256'] == sha(base/'execution_manifest.json'), 'Manifest seal mismatch')
    require(manifest['max_runs'] == 1 and manifest['model_mode'] == 'final', 'Ordinary final run only')
    admit_workload(manifest, seal, base)
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
# A declared multi-round Review: the ordinary flags under `reference_serial` (D-011 choice 3:
# the topology code is not widened), no topology configuration, and the sealed case manifest.
MULTI_ROUND_ARGV = ['--backend-profile', 'local', '--activation-profile', 'dense',
                    '--review-mode', 'paired', '--task', 'review', '--mode', 'standalone',
                    '--non-interactive', '--skip-confirmation', '--sensitivity-layer-inactive-override',
                    '--no-redaction-override', '--execution-topology', 'reference_serial',
                    '--agent-briefs', 'enabled', '--input-language', 'auto', '--output-language', 'en',
                    '--multi-round', '--multi-round-manifest', CASE_MANIFEST]


def selected_candidate(manifest, permit):
    """The sealed instance candidate the authorization names; nothing outside the list."""
    matches = [c for c in manifest['instance_candidates'] if c['type'] == permit.get('instance_type')]
    require(len(matches) == 1 and permit.get('instance_candidate') == matches[0], 'Instance authorization mismatch')
    return matches[0]


def authorization(base, manifest, permit, now=None):
    now = time.time() if now is None else now
    require(permit.get('operator_authorized') is True and
            permit.get('action') == 'one-ordinary-final-cloud-run', 'New explicit authorization required')
    require(permit.get('execution_manifest_sha256') == sha(Path(base)/'execution_manifest.json'), 'Authorization manifest mismatch')
    require(permit.get('seal_sha256') == sha(Path(base)/'seal.json'), 'Authorization seal mismatch')
    require(permit.get('source_commit') == manifest['source_commit'], 'Authorization source mismatch')
    require(permit.get('soft_budget_usd') == manifest['soft_budget_usd'] and
            permit.get('hard_ceiling_usd') == manifest['hard_ceiling_usd'], 'Budget authorization mismatch')
    require(permit.get('multi_round') == manifest['multi_round'], 'Workload authorization mismatch')
    candidate = selected_candidate(manifest, permit)
    require(permit.get('provider') == 'Lambda' and isinstance(permit.get('region'), str)
            and re.fullmatch(r'[a-z]+-[a-z]+-[0-9]+', permit['region']), 'Instance authorization mismatch')
    require(isinstance(permit.get('instance_id'),str) and
            re.fullmatch(r'[a-f0-9]{32}|[a-f0-9-]{36}',permit['instance_id']), 'Instance ID required')
    require(0 < permit['hourly_rate'] <= candidate['max_hourly_rate'], 'Price exceeds ceiling')
    start = permit['active_start_epoch']
    require(isinstance(start, (int, float)) and 0 < start <= now, 'Invalid billing start')
    require(now < start + manifest['hard_ceiling_usd']/permit['hourly_rate']*3600 - manifest['workload_stop_reserve_seconds'],
            'Insufficient execution/collection reserve')


def assess(completion, raw, multi_round=None):
    """Run health. A declared multi-round run (D-011 choice 11) also needs its saved case
    record (multi_round.read_saved) to show outcome `reviewed` and activation `activated`;
    quality is reported separately and is never a pass."""
    reasons = []
    if multi_round is not None:
        if not (isinstance(multi_round, dict) and multi_round.get('outcome') == 'reviewed'):
            reasons.append('multi_round_not_reviewed')
        if not (isinstance(multi_round, dict) and (multi_round.get('activation') or {}).get('activated') is True):
            reasons.append('multi_round_not_activated')
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


def failure_identity(exc, project):
    """Exception type, class module, raising frame and innermost project frame.

    File basenames, line numbers and function names only, never message text:
    the type-only receipt of run 88323b86 could not say where its RuntimeError
    was raised, and the cause had to be re-derived from source."""
    import traceback
    frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ is not None else []
    def label(frame):
        return Path(frame.filename).name+':'+str(frame.lineno)+':'+frame.name
    def inside(frame):
        # Same rule as scripts/model_telemetry.project_frame: a pseudo-filename
        # resolves against the working directory, which IS the project during a
        # run, and an in-tree virtual environment holds library code; either
        # would report a foreign frame as the project origin.
        name = str(frame.filename)
        if name.startswith('<') or not name.endswith('.py'):
            return False
        try:
            path = Path(name).resolve()
            relative = path.relative_to(Path(project).resolve())
        except (OSError, ValueError):
            return False
        return path.is_file() and relative.parts[0] not in {'.venv', 'venv', 'site-packages', '.tmp'}
    origin = next((f for f in reversed(frames) if inside(f)), None)
    return {'error_type': type(exc).__name__, 'error_module': type(exc).__module__,
            'error_frame': label(frames[-1]) if frames else None,
            'error_origin': label(origin) if origin else None}


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


def gpu_matches(token, name):
    """Whole-token match, so 'A10' never admits an 'A100'."""
    return bool(token) and re.search(r'(?<![A-Za-z0-9])'+re.escape(token)+r'(?![0-9])', str(name)) is not None


def hardware_admission(base, torch, psutil, candidate):
    """The selected type's requirements, read from its sealed candidate entry: its GPU, the
    run's VRAM, the host the provider advertised for that type, and the run's own floors."""
    require(torch.cuda.device_count()==1,'Exactly one GPU required')
    props=torch.cuda.get_device_properties(0)
    free,total=torch.cuda.mem_get_info(0)
    memory=psutil.virtual_memory()
    value=dict(gpu_name=props.name,gpu_total_bytes=total,gpu_free_bytes=free,
               cpu_count=psutil.cpu_count(),ram_total_bytes=memory.total,ram_available_bytes=memory.available,
               disk_free_bytes=shutil.disk_usage(base).free,instance_type=candidate['type'])
    require(gpu_matches(candidate['gpu_token'],props.name) and total>=candidate['run_gpu_total_bytes']
            and free>=candidate['run_gpu_free_bytes'],'GPU memory admission')
    require(value['cpu_count']>=candidate['min_cpu'] and memory.total>=candidate['min_ram_bytes']
            and memory.available>=candidate['run_ram_available_bytes'],'Host resource admission')
    require(value['disk_free_bytes']>=candidate['run_disk_free_bytes'],'Storage admission')
    return value


def execute(base):
    base = Path(base).resolve()
    manifest = verify(base)
    require(sys.platform == 'linux', 'Remote Linux execution only')
    permit = read(base/'operator_authorization.json')
    authorization(base, manifest, permit)
    require((base/'WATCHDOG_ARMED.json').is_file(), 'Independent operator watchdog required')
    watch = read(base/'WATCHDOG_ARMED.json')
    own = sha(base/'execution_manifest.json')
    # A batch session's watchdog names every bundle of the batch it guards.
    require((watch.get('execution_manifest_sha256') == own or own in (watch.get('batch_manifest_sha256s') or [])) and
            watch.get('instance_id') == permit.get('instance_id') and
            0 <= time.time()-watch.get('heartbeat_epoch', 0) < 30, 'Watchdog not current')
    with (base/'RUN_CLAIMED').open('x', encoding='utf8') as stream:
        stream.write(str(time.time()))
    deadline = (permit['active_start_epoch'] + manifest['hard_ceiling_usd']/permit['hourly_rate']*3600
                - manifest['workload_stop_reserve_seconds'])
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
    write(base/'hardware_admission.json',hardware_admission(base,sys.modules['torch'],psutil,
                                                           selected_candidate(manifest, permit)))
    from cloud_run_observer import Recorder, deny_network
    evidence = base/'evidence'
    evidence.mkdir(exist_ok=False)
    rec = Recorder(evidence/'network.jsonl')
    deny_network(rec)
    # Every inherited runtime flag was removed; only the manifest flags survive.
    argv = list(argv_for(manifest))
    if '--topology-config' in argv:
        argv[argv.index('--topology-config')+1] = str(base/'topology.json')
    if '--multi-round-manifest' in argv:
        argv[argv.index('--multi-round-manifest')+1] = str(base/CASE_MANIFEST)
    argv += ['--output-dir', str(evidence/'run')]
    code = 1
    try:
        import pipeline
        code = pipeline.main(argv)
    except BaseException as exc:
        write(evidence/'terminal_error.json', failure_identity(exc, project))
    finally:
        rec.close()
        import model_telemetry, run_completion
        # The runtime may rename its output folder at completion.
        directories = [p.parent.parent for p in evidence.rglob('audit/run_completion.json')]
        if len(directories) == 1:
            directory = directories[0]
            raw = [json.loads(line) for line in (directory/'logs/model_telemetry.jsonl').read_text(encoding='utf8').splitlines() if line]
            completion = run_completion.read(directory)
            saved = None
            if manifest['multi_round']:
                import multi_round
                saved = multi_round.read_saved(directory, (completion or {}).get('run_id') or directory.name)
            result = assess(completion, raw, saved)
            model_telemetry.recompute(directory)
        else:
            result = assess(None, [], {} if manifest['multi_round'] else None)
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
