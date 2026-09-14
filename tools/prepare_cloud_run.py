#!/usr/bin/env python3
"""Seal a local-only experiment. Never connects to a provider or loads a model."""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
import types
import zipfile
from email.parser import BytesParser
from pathlib import Path

from cloud_run_common import (InvalidPreparation, credential_locations, digest,
    extract_source, json_bytes, require, safe_name, write_json)
from cloud_run_watchdog import operator_preflight

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / 'cloud_run'
BASELINE = '15d0721fbc24cd38fdaa6bc4969d7b18ad66387e'
RUNTIME = {'python': '3.12.3', 'pip': '24.0', 'platform': 'linux_x86_64', 'glibc_min': '2.35',
           'torch': '2.5.1+cu121', 'cuda_runtime': '12.1',
           'gpu_name': 'NVIDIA A100-SXM4-40GB', 'gpu_count': 1, 'minimum_vram_mib': 40000,
           'instance_class': 'gpu_1x_a100_sxm4', 'python_venv_required': True,
           'minimum_free_disk_gib': 40}
TOPOLOGY = {'schema_version': 1, 'lanes': [{'name': 'primary', 'device': 'cuda:0', 'resident_limit': 2}]}
ARGV = ['--backend-profile', 'local', '--activation-profile', 'dense', '--review-mode', 'paired',
        '--task', 'review', '--mode', 'standalone', '--non-interactive', '--skip-confirmation',
        '--sensitivity-layer-inactive-override', '--no-redaction-override',
        '--execution-topology', 'dependency_dag', '--topology-config', 'topology.json',
        '--agent-briefs', 'enabled', '--input-language', 'auto', '--output-language', 'en']


def git(root, *args):
    # The staged scan is mandatory BEFORE every git operation, including reads.
    scan = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMRT', '-z'],
                          cwd=root, capture_output=True, check=True)
    for name in scan.stdout.decode('utf-8').split('\0'):
        if not name:
            continue
        staged = subprocess.run(['git', 'show', ':' + name], cwd=root,
                                capture_output=True, check=True)
        hits = credential_locations(staged.stdout, name)
        require(not hits, 'possible staged credential: ' + name +
                (':' + str(hits[0]['line']) if hits else '') + '; stop without printing values')
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, check=True, timeout=30)
    return result.stdout


def normalized(data):
    return data.replace(b'\r\n', b'\n')


def source_files(root, expected):
    require(re.fullmatch('[0-9a-f]{40}', expected), 'expected commit must be full SHA')
    require(git(root, 'rev-parse', 'HEAD').decode().strip() == expected, 'source HEAD mismatch')
    tracked = git(root, 'ls-files', '-z').decode().split('\0')[:-1]
    with tarfile.open(fileobj=io.BytesIO(git(root, 'archive', '--format=tar', expected))) as archive:
        originals = {m.name: archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
    changes = []
    files = {}
    for name in tracked:
        require(name in originals, 'tracked addition differs from expected commit: ' + name)
        original = originals[name]
        path = root / name
        require(path.is_file() and not path.is_symlink(), 'tracked file missing or linked: ' + name)
        current = normalized(path.read_bytes())
        require(current == normalized(original), 'tracked source changed: ' + name)
        # Ship runtime source and the one synthetic corpus, never operator state.
        include = (name.startswith(('scripts/', 'config/', 'corpus_ingest/')) or
                   name.startswith('benchmark/corpora/clinical_reference/') or
                   name in ('requirements.txt', 'genesis.md', 'tools/run_local_demo.py', 'tools/score_corpus.py'))
        if name.endswith('_checks.py') or name.startswith('scripts/verify_') or '/fixtures/' in name:
            include = False
        if include:
            hits = credential_locations(original, name)
            require(not hits, 'possible credential: ' + name + (':' + str(hits[0]['line']) if hits else ''))
            files[name] = normalized(original)
    require('scripts/pipeline.py' in files, 'missing pipeline')
    untracked = git(root, 'ls-files', '--others', '--exclude-standard', '-z').decode().split('\0')[:-1]
    status = {'branch': git(root, 'branch', '--show-current').decode().strip(),
              'head': expected, 'local_tracking_commit': git(root, 'rev-parse', '@{u}').decode().strip(),
              'remote_contacted': False, 'remote_tip_live_verified': False,
              'approved_fixture_changes': changes, 'untracked_files_untouched': untracked,
              'history': git(root, 'log', '--format=%h %s', '-12').decode().splitlines()}
    verification = root / 'output/cloud_prep_audit/source_remote_verification.json'
    if verification.is_file():
        value = json.loads(verification.read_text())
        if value.get('source_commit') == expected:
            status['prior_live_remote_verification'] = value
        else:
            status['prior_live_remote_verification_matches_source'] = False
    return files, status


def behavioral_proof(files, directory):
    """Exercise the real parser/decorator with an inert body; never pipeline.main."""
    scripts = directory / 'scripts'
    scripts.mkdir(parents=True)
    for name in ('agent_activation', 'execution_topology', 'execution_scheduler'):
        (scripts / (name + '.py')).write_bytes(files['scripts/' + name + '.py'])
    source = files['scripts/pipeline.py'].decode('utf-8-sig')
    tree = ast.parse(source)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_build_arg_parser')
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    require(any(ast.unparse(d) == 'execution_topology.entrypoint' for d in main.decorator_list), 'DAG entry adapter missing')
    sys.path.insert(0, str(scripts))
    old = {n: sys.modules.pop(n, None) for n in ('agent_activation', 'execution_scheduler', 'execution_topology', 'agent_wrapper')}
    try:
        import agent_activation
        import execution_topology as topology
        scope = {'argparse': argparse, 'agent_activation': agent_activation}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), 'sealed_parser', 'exec'), scope)
        argv = list(ARGV)
        top = directory / 'topology.json'
        write_json(top, TOPOLOGY)
        argv[argv.index('--topology-config')+1] = str(top)
        args = scope['_build_arg_parser']().parse_args(argv)
        require(args.task == 'review' and args.mode == 'standalone', 'wrong workload entry')
        require(args.execution_topology == 'dependency_dag', 'serial selected')
        require(not args.multi_round and args.multi_round_manifest is None, 'multi-round active')
        require((args.agent_briefs, args.input_language, args.output_language) == ('enabled', 'auto', 'en'), 'run options changed')
        guards = []
        for node in main.body:
            if isinstance(node, ast.If) and ast.unparse(node.test) in (
                    'args.multi_round or args.multi_round_manifest', 'multi_manifest is not None', 'multi_record is not None'):
                taken = bool(eval(compile(ast.Expression(node.test), 'guard', 'eval'),
                                  {'args': args, 'multi_manifest': None, 'multi_record': None}))
                require(not taken, 'multi-round guard active')
                guards.append({'line': node.lineno, 'expression': ast.unparse(node.test), 'taken': taken})
        require(len(guards) == 3, 'multi-round guard contract drift')
        # Only the cache-presence dependency is stubbed, not the actual decorator.
        sys.modules['agent_wrapper'] = types.SimpleNamespace(_QWEN_MODELS={})
        observed = {}
        def probe(argv):
            runtime = topology.ACTIVE.get()
            require(runtime is not None and not topology.reference_prewarm_enabled(), 'DAG inactive')
            require(len(runtime.scheduler.workers) == 1, 'worker count changed')
            observed.update(dag_entry_selected=True, reference_serial_selected=False, workers=1,
                            resident_limit=2, fixture_body_only=True)
            return 0
        probe.__globals__['_build_arg_parser'] = scope['_build_arg_parser']
        require(topology.entrypoint(probe)(argv) == 0 and topology.ACTIVE.get() is None, 'DAG cleanup failed')
        for forbidden in (['--task', 'draft'], ['--multi-round']):
            bad = argv + forbidden
            with __import__('contextlib').redirect_stderr(io.StringIO()):
                try:
                    topology.entrypoint(probe)(bad)
                except SystemExit as exc:
                    require(exc.code != 0, 'isolation guard failed')
                else:
                    raise InvalidPreparation('forbidden path accepted')
        topology_source = files['scripts/execution_topology.py'].decode()
        for marker in ('rolling_bus_visibility_and_governance_order', 'prior_phase_results_bus_and_governance_must_be_complete',
                       'execution_topology.jsonl', 'generation_start', 'model_resident'):
            require(marker in topology_source, 'missing telemetry/dependency: ' + marker)
        return {**observed, 'guards': guards, 'multi_round_inactive': True, 'draft_rejected': True,
                'semantic_edges_preserved': True, 'scheduler_telemetry': True,
                'actual_parallelism_measured': False, 'options': vars(args)}
    finally:
        sys.path.remove(str(scripts))
        for name, module in old.items():
            sys.modules.pop(name, None)
            if module is not None:
                sys.modules[name] = module


def pins(path):
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    result = {}
    for line in Path(path).read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        req = Requirement(line)
        spec = list(req.specifier)
        require(len(spec) == 1 and spec[0].operator == '==' and '*' not in spec[0].version and not req.url,
                'dependency is not exactly pinned')
        key = canonicalize_name(req.name)
        require(key not in result, 'duplicate dependency')
        result[key] = spec[0].version
    return result


def validate_wheels(directory, locked):
    """Validate exact Linux/CPython wheels AND dependency closure, entirely offline."""
    from packaging.requirements import Requirement
    from packaging.specifiers import SpecifierSet
    from packaging.utils import canonicalize_name, parse_wheel_filename
    directory = Path(directory)
    require(directory.is_dir(), 'Linux CPython 3.12 wheelhouse missing; build locally before provisioning')
    found, metadata = {}, {}
    for path in sorted(directory.glob('*.whl')):
        name, version, _, tags = parse_wheel_filename(path.name)
        name = canonicalize_name(name)
        require(name in locked and str(version) == locked[name] and name not in found, 'wheel pin mismatch or duplicate: ' + name)
        compatible = False
        for tag in tags:
            platform_ok = tag.platform == 'any' or tag.platform == 'linux_x86_64'
            if tag.platform.startswith('manylinux') and tag.platform.endswith('_x86_64'):
                match = re.match(r'manylinux_(\d+)_(\d+)_x86_64', tag.platform)
                platform_ok = bool(match and tuple(map(int, match.groups())) <= (2, 35)) or tag.platform.startswith(('manylinux1_', 'manylinux2010_', 'manylinux2014_'))
            python_ok = tag.interpreter in ('py3', 'py312', 'cp312') and tag.abi in ('none', 'abi3', 'cp312')
            if tag.abi == 'abi3' and re.fullmatch(r'cp3\d+', tag.interpreter):
                python_ok = int(tag.interpreter[3:]) <= 12
            compatible |= platform_ok and python_ok
        require(compatible, 'wheel is not compatible with target: ' + name)
        with zipfile.ZipFile(path) as archive:
            names = [n for n in archive.namelist() if n.count('/') == 1 and n.endswith('.dist-info/METADATA')]
            require(len(names) == 1, 'wheel metadata missing')
            meta = BytesParser().parsebytes(archive.read(names[0]))
            require(canonicalize_name(meta['Name']) == name and meta['Version'] == str(version), 'wheel identity mismatch')
            require(SpecifierSet(meta.get('Requires-Python', '')).contains('3.12.3'), 'wheel Python requirement mismatch')
            metadata[name] = meta.get_all('Requires-Dist', [])
        found[name] = {'filename': path.name, 'sha256': digest(path)}
    require(set(found) == set(locked), 'wheelhouse missing pinned packages: ' + ','.join(sorted(set(locked)-set(found))))
    env = {'python_version': '3.12', 'python_full_version': '3.12.3', 'sys_platform': 'linux',
           'os_name': 'posix', 'platform_machine': 'x86_64', 'platform_system': 'Linux',
           'implementation_name': 'cpython', 'implementation_version': '3.12.3',
           'platform_python_implementation': 'CPython', 'extra': ''}
    for name, requirements in metadata.items():
        extras = ('', 'standard') if name == 'uvicorn' else ('',)
        for text in requirements:
            req = Requirement(text)
            if req.marker and not any(req.marker.evaluate({**env, 'extra': extra}) for extra in extras):
                continue
            key = canonicalize_name(req.name)
            require(not req.url and key in locked and req.specifier.contains(locked[key]), 'dependency closure fails: ' + name + ' -> ' + key)
    return found


def safetensor_header(path):
    with path.open('rb') as stream:
        size = struct.unpack('<Q', stream.read(8))[0]
        require(0 < size < 100_000_000, 'invalid safetensors header')
        header = json.loads(stream.read(size))
    tensors = {k: v for k, v in header.items() if k != '__metadata__'}
    require(bool(tensors), 'empty safetensors')
    end = path.stat().st_size - 8 - size
    for tensor in tensors.values():
        a, b = tensor['data_offsets']
        require(0 <= a <= b <= end and isinstance(tensor['shape'], list), 'invalid tensor offsets')
    return len(tensors)


def model_manifest(cache, revisions):
    result = []
    for model, revision in sorted(revisions.items()):
        require(re.fullmatch('[0-9a-f]{40}', revision), 'model revision not immutable')
        snapshot = Path(cache) / ('models--' + model.replace('/', '--')) / 'snapshots' / revision
        require(snapshot.is_dir(), 'fixed local model snapshot missing: ' + model)
        files = {}
        for path in sorted(snapshot.rglob('*')):
            rel = path.relative_to(snapshot).as_posix()
            if not path.is_file() or rel.startswith(('onnx/', 'openvino/', 'imgs/')):
                continue
            if path.suffix not in ('.json', '.txt', '.model', '.safetensors'):
                continue
            require(safe_name(rel), 'unsafe model member')
            if path.suffix == '.json':
                json.loads(path.read_text(encoding='utf-8'))
            if path.suffix == '.safetensors':
                safetensor_header(path)
            files[rel] = {'sha256': digest(path), 'bytes': path.stat().st_size,
                          'delivery': 'bundled' if model == 'BAAI/bge-m3' and rel == 'model.safetensors' else 'hub'}
        require(all(n in files for n in ('config.json', 'tokenizer_config.json', 'model.safetensors')), 'incomplete model cache: ' + model)
        require('tokenizer.json' in files or 'tokenizer.model' in files or 'sentencepiece.bpe.model' in files
                or {'vocab.json', 'merges.txt'} <= files.keys(), 'tokenizer vocabulary missing: ' + model)
        for name in files:
            if name.endswith('.safetensors.index.json'):
                index = json.loads((snapshot / name).read_text(encoding='utf-8'))
                require(all(n in files for n in index['weight_map'].values()), 'missing model shard')
        result.append({'model': model, 'revision': revision, 'files': files})
    return result


def make_source(files, path):
    with Path(path).open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w', format=tarfile.USTAR_FORMAT) as tar:
            for name, data in sorted(files.items()):
                require(safe_name(name), 'unsafe source path')
                entry = tarfile.TarInfo(name)
                entry.size, entry.mode, entry.mtime = len(data), 0o644, 0
                tar.addfile(entry, io.BytesIO(data))


def copy_asset(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    # A real copy keeps a sealed bundle independent of operator-owned caches.
    shutil.copyfile(source, target)


def prepare(args):
    require(re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}', args.experiment_id), 'invalid experiment ID')
    from cloud_run_common import budget_deadlines
    budget_deadlines(args.hourly_rate, 1)
    destination = Path(args.output).resolve() / args.experiment_id
    require(not destination.exists(), 'experiment destination exists; never overwrite evidence')
    destination.mkdir(parents=True)
    report = {'experiment_id': args.experiment_id, 'ready_to_provision': False, 'checks': {}, 'blockers': []}
    def check(name, action):
        try:
            result = action()
            report['checks'][name] = {'passed': True}
            return result
        except (InvalidPreparation, OSError, ValueError, subprocess.CalledProcessError) as exc:
            # Exception strings from external programs or files can contain secrets.
            detail = str(exc) if isinstance(exc, InvalidPreparation) else type(exc).__name__
            report['checks'][name] = {'passed': False, 'reason': detail}
            report['blockers'].append(name + ': ' + detail)
            return None
    source = check('repository', lambda: source_files(ROOT, args.expected_commit))
    if source is None:
        write_json(destination / 'PREPARATION_REPORT.json', report)
        return destination, report
    files, repository = source
    control = check('local_operator_deployment_prerequisites', lambda: operator_preflight(
                    getattr(args, 'credential_file', None), getattr(args, 'identity_file', None)))
    if control:
        write_json(destination / 'operator_readiness.json', control)
    write_json(destination.parent / (args.experiment_id + '_local_repository_audit.json'), repository)
    public_repository = {k: v for k, v in repository.items() if k != 'untracked_files_untouched'}
    public_repository['untracked_file_count_excluded'] = len(repository.get('untracked_files_untouched', []))
    write_json(destination / 'repository_state.json', public_repository)
    # Stage only the comparison corpus into the source image, locally.
    corpus = 'benchmark/corpora/clinical_reference/'
    for name, data in list(files.items()):
        if name.startswith(corpus) and name.endswith('.md'):
            files['input/' + name[len(corpus):]] = data
    files['input/context/_review_targets.json'] = json_bytes({'source': 'operator', 'targets': ['result_sheet.md'],
                                                            'grounding': ['analyte_reference_ranges.md'], 'prior': []})
    with tempfile.TemporaryDirectory(prefix='shimmer-prep-') as tmp:
        proof = check('behavioral_isolation_and_DAG', lambda: behavioral_proof(files, Path(tmp)))
    if proof:
        proof['options']['topology_config'] = 'topology.json'
        write_json(destination / 'behavioral_proof.json', proof)
    write_json(destination / 'topology.json', TOPOLOGY)
    write_json(destination / 'run_options.json', {'argv': ARGV, 'max_runs': 1})
    write_json(destination / 'runtime.json', RUNTIME)
    write_json(destination / 'experiment.json', {'experiment_id': args.experiment_id, 'source_commit': args.expected_commit,
        'workload': 'clinical_reference', 'classification': 'PREPARED / NOT RUN', 'max_runs': 1,
        'hourly_rate_usd': args.hourly_rate, 'soft_budget_usd': 5, 'absolute_budget_usd': 10,
        'termination_reserve_seconds': 120, 'billing_includes_setup_and_collection': True,
        'model_delivery': 'concurrent fixed hub downloads; locally converted BGE safetensors bundled',
        'target_instance_class': RUNTIME['instance_class']})
    write_json(destination / 'comparison_baseline.json', {'classification': 'COMPLETED / AUTHORITATIVE BASELINE',
        'cold_wall_seconds': 1958, 'model_calls': 20, 'generation_seconds': 1920.789, 'generation_percent': 98.18,
        'gpu_utilization_median_percent': 41, 'peak_vram_gib': 8.23, 'ram_storage_pressure': 'not meaningful',
        'multi_round_active': False, 'amendments': 3, 'quality_equivalence': 'not broadly established',
        'gpu': '1 x A100-SXM4 40 GB'})
    write_json(destination / 'evidence_classification.json', {
        'a100_smoke_20260914': 'COMPLETED / AUTHORITATIVE BASELINE',
        'a100_optimized_20260914': 'ABORTED / NON-BENCHMARK',
        args.experiment_id: 'PREPARED / NOT RUN', 'historical_evidence_modified': False})
    write_json(destination / 'credential_disposition.json', {'file': 'scripts/verify_session1.py',
        'lines': [3387, 3900, 4087, 5080], 'classification': 'FALSE POSITIVE / SYNTHETIC TEST FIXTURES',
        'proof': 'Explicit non-real literals; discovery stub or _FakeAnthropicClient installed before use.',
        'change': 'Four literals replaced by TEST_CREDENTIAL_PLACEHOLDER; no credentials rotated.'})
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
    write_json(destination / 'source_manifest.json', manifest)
    make_source(files, destination / 'source.tar.gz')
    def verify_source():
        with tempfile.TemporaryDirectory(prefix='shimmer-source-') as tmp:
            extract_source(destination / 'source.tar.gz', Path(tmp), manifest)
        return True
    check('source_archive_hashes', verify_source)
    locked = pins(ASSETS / 'runtime.lock')
    def dependency_pins():
        from packaging.specifiers import SpecifierSet
        required = pins(ROOT / 'requirements.txt')
        require(all(k in locked and SpecifierSet('==' + v).contains(locked[k]) for k, v in required.items()), 'runtime pins differ from source requirements')
        require(locked == pins(ROOT / 'output/a100_smoke_20260914/collected/runtime_frozen.txt'), 'runtime differs from completed baseline')
        return True
    check('dependency_pins_match_completed_baseline', dependency_pins)
    shutil.copyfile(ASSETS / 'runtime.lock', destination / 'runtime.lock')
    wheels = check('offline_linux_wheelhouse', lambda: validate_wheels(args.wheelhouse, locked))
    if wheels:
        for item in wheels.values():
            copy_asset(Path(args.wheelhouse) / item['filename'], destination / 'wheels' / item['filename'])
        write_json(destination / 'wheel_manifest.json', wheels)
        (destination / 'install.lock').write_text(''.join(f'{name}=={locked[name]} --hash=sha256:{wheels[name]["sha256"]}\n' for name in sorted(locked)), encoding='utf-8')
    revisions = json.loads((ASSETS / 'models.json').read_text())
    def check_models():
        config = json.loads(files['config/local_models.json'])
        require(set(revisions) == {config['active_producer'], config['active_auditor'], 'BAAI/bge-m3'}, 'model IDs changed')
        old = json.loads((ROOT / 'output/a100_optimized_20260914/model_hydration.json').read_text())
        require(revisions == {m['model']: m['revision'] for m in old}, 'model revisions changed')
        return model_manifest(args.model_cache, revisions)
    models = check('fixed_models_and_local_cache', check_models)
    if models:
        write_json(destination / 'models.json', models)
        for model in models:
            for name, item in model['files'].items():
                if item['delivery'] == 'bundled':
                    src = Path(args.model_cache) / ('models--' + model['model'].replace('/', '--')) / 'snapshots' / model['revision'] / name
                    copy_asset(src, destination / 'model_assets' / model['revision'] / name)
    for name in ('cloud_run_common.py', 'cloud_run_observer.py', 'cloud_run_remote.py'):
        shutil.copyfile(ROOT / 'tools' / name, destination / name)
    (destination / 'launch.sh').write_text('#!/bin/bash\nset -euo pipefail\ncd -- "$(dirname -- "$0")"\nexec venv/bin/python cloud_run_observer.py\n', encoding='utf-8')
    (destination / 'score.sh').write_text('#!/bin/bash\nset -euo pipefail\ncd -- "$(dirname -- "$0")"\nexec venv/bin/python project/tools/score_corpus.py --corpus project/benchmark/corpora/clinical_reference --run evidence/run\n', encoding='utf-8')
    write_json(destination / 'collection_manifest.json', {'roots': ['evidence'], 'exclude': ['project', 'venv', 'hf_cache', 'wheels'],
        'required': ['events.jsonl', 'lifecycle.jsonl', 'result.json', 'score.txt', 'metrics.json'],
        'run_artifacts': ['run/audit/execution_topology.json', 'run/audit/execution_topology.jsonl', 'run/audit/run_options.json'],
        'teardown_required': ['instance_id', 'termination_requested_utc', 'termination_verified_utc', 'status', 'hourly_rate'],
        'completion_requires': 'exit zero, one finished run, scoring, collected hashes, provider termination verified'})
    def tests():
        result = subprocess.run([sys.executable, str(ROOT / 'tools/cloud_run_checks.py'), '--json'], cwd=ROOT, capture_output=True)
        require(result.returncode == 0, 'offline preparation/deployment tests failed (run tools/cloud_run_checks.py for counts)')
        value = json.loads(result.stdout)
        require(value['passed'] and value['tests_run'] > 0, 'invalid test report')
        write_json(destination / 'local_validation.json', value)
        return value
    validation = check('local_test_suite', tests)
    def scan_bundle():
        hits = []
        for path in destination.rglob('*'):
            if path.is_file() and path.suffix in ('.json', '.jsonl', '.py', '.sh', '.txt', '.lock'):
                hits.extend(credential_locations(path.read_bytes(), path.relative_to(destination).as_posix()))
        require(not hits, 'possible credential in bundle: ' + (hits[0]['file'] + ':' + str(hits[0]['line']) if hits else ''))
        return True
    check('bundle_credential_scan', scan_bundle)
    report['source_commit'] = args.expected_commit
    report['source_sha256'] = digest(destination / 'source.tar.gz')
    report['local_validation'] = validation
    report['ready_to_provision'] = not report['blockers']
    write_json(destination / 'PREPARATION_REPORT.json', report)
    if report['ready_to_provision']:
        bundle_manifest = {p.relative_to(destination).as_posix(): digest(p) for p in sorted(destination.rglob('*')) if p.is_file()}
        write_json(destination / 'bundle_manifest.json', bundle_manifest)
        write_json(destination / 'READY_TO_PROVISION.json', {'ready_to_provision': True,
            'source_commit': args.expected_commit, 'source_hash': report['source_sha256'], 'experiment_id': args.experiment_id,
            'workload': 'clinical_reference', 'topology_mode': 'dependency_dag', 'agent_briefs': 'enabled',
            'input_language': 'auto', 'output_language': 'en', 'multi_round_inactive': True,
            'model_revisions': revisions, 'validation_results': report['checks'], 'expected_remote_runtime': RUNTIME,
            'bundle_manifest_sha256': digest(destination / 'bundle_manifest.json')})
    return destination, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment-id', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--hourly-rate', type=float, required=True)
    parser.add_argument('--credential-file', type=Path, help='Optional local private Python config; only loaded status is retained')
    parser.add_argument('--identity-file', type=Path, required=True, help='Local prepared SSH identity; never included in the bundle')
    parser.add_argument('--model-cache', default=str(Path.home() / '.cache/huggingface/hub'))
    parser.add_argument('--wheelhouse', default=str(ROOT / 'output/cloud_wheels/linux_cp312'))
    parser.add_argument('--output', default=str(ROOT / 'output/cloud_ready'))
    args = parser.parse_args(argv)
    try:
        destination, report = prepare(args)
        print(json.dumps({'bundle': str(destination), 'ready_to_provision': report['ready_to_provision'], 'blockers': report['blockers']}))
        return 0 if report['ready_to_provision'] else 2
    except (InvalidPreparation, OSError) as exc:
        print(json.dumps({'ready_to_provision': False, 'error': str(exc) if isinstance(exc, InvalidPreparation) else type(exc).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
