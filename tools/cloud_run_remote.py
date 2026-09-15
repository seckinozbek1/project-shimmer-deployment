"""Minimal remote work from an already sealed bundle. Never invoked by preparation."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from cloud_run_common import digest, extract_source, require, write_json
import runtime_contract as python_runtime


def event(base, name, epoch=None):
    epoch = time.time() if epoch is None else epoch
    with (base / 'evidence/lifecycle.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'event': name, 'epoch': epoch,
                     'utc': datetime.fromtimestamp(epoch, timezone.utc).isoformat()}) + '\n')


def hydrate(base):
    from huggingface_hub import hf_hub_download
    models = json.loads((base / 'models.json').read_text())
    cache = base / 'hf_cache/hub'
    def one(model):
        snapshot = cache / ('models--' + model['model'].replace('/', '--')) / 'snapshots' / model['revision']
        for name, spec in model['files'].items():
            if spec['delivery'] == 'bundled':
                path = snapshot / name
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(base / 'model_assets' / model['revision'] / name, path)
            else:
                path = Path(hf_hub_download(repo_id=model['model'], filename=name, revision=model['revision'],
                            cache_dir=str(cache), token=False))
            require(digest(path) == spec['sha256'] and path.stat().st_size == spec['bytes'], 'hydrated model mismatch')
        ref = snapshot.parent.parent / 'refs/main'
        ref.parent.mkdir(exist_ok=True)
        ref.write_text(model['revision'])
        return {'model': model['model'], 'revision': model['revision'], 'verified_files': len(model['files'])}
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(one, models))
    write_json(base / 'evidence/model_hydration.json', records)


def gpu_sanity(runtime):
    result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
                            capture_output=True, text=True, check=True, timeout=15)
    rows = result.stdout.strip().splitlines()
    require(len(rows) == 1, 'expected exactly one GPU')
    name, memory = [s.strip() for s in rows[0].split(',')]
    require(name == runtime['gpu_name'] and float(memory) >= runtime['minimum_vram_mib'], 'target GPU mismatch')
    return {'gpu_name': name, 'vram_mib': float(memory)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--hydrate-only', action='store_true')
    parser.add_argument('--running-epoch', type=float)
    parser.add_argument('--first-ssh-epoch', type=float)
    parser.add_argument('--deployment-start-epoch', type=float)
    args = parser.parse_args(argv)
    require(args.execute and sys.platform == 'linux', 'remote execution must be explicit')
    base = Path(__file__).resolve().parent
    contract = python_runtime.load_contract(base / 'runtime.json')
    bootstrap = python_runtime.assert_current('sealed_reference', contract)
    if args.hydrate_only:
        python_runtime.subprocess_check(bootstrap, base / 'project', contract_file=base / 'runtime.json')
        deps = python_runtime.subprocess_check(bootstrap, base, dependencies=True, contract_file=base / 'runtime.json')
        require(deps['dependencies_ready'], 'Dependencies unavailable; model acquisition refused')
        hydrate(base)
        return 0
    # Claim is atomic and permanent: failed setup never permits a second run.
    with (base / 'RUN_CLAIMED').open('x') as stream:
        stream.write('exactly one attempt\n')
    evidence = base / 'evidence'
    evidence.mkdir()
    require(args.running_epoch is not None and args.first_ssh_epoch is not None and args.deployment_start_epoch is not None,
            'billing, SSH and deployment timestamps required')
    event(base, 'instance_reported_running', args.running_epoch)
    event(base, 'first_ssh_success', args.first_ssh_epoch)
    event(base, 'deployment_start', args.deployment_start_epoch)
    runtime = json.loads((base / 'runtime.json').read_text())
    python_runtime.assert_current('sealed_reference', runtime)
    require(shutil.disk_usage(base).free >= runtime['minimum_free_disk_gib'] * 2**30, 'insufficient disk')
    gpu = gpu_sanity(runtime)
    # Only transfer integrity/options hashes are checked here. CPU audits ran locally.
    manifest = json.loads((base / 'bundle_manifest.json').read_text())
    for name, sha in manifest.items():
        require(digest(base / name) == sha, 'transferred bundle hash mismatch')
    extract_source(base / 'source.tar.gz', base / 'project', json.loads((base / 'source_manifest.json').read_text()))
    subprocess.run([sys.executable, '-m', 'venv', str(base / 'venv')], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    selected = python_runtime.resolve([str(base / 'venv/bin/python')], profile='sealed_reference', contract=runtime)
    python = selected['executable']
    write_json(evidence / 'resolved_interpreter.json', selected)
    preflight = python_runtime.subprocess_check(selected, base / 'project', contract_file=base / 'runtime.json')
    write_json(evidence / 'source_preflight.json', preflight)
    deps = python_runtime.subprocess_check(selected, base, dependencies=True, contract_file=base / 'runtime.json')
    clean = {k: v for k, v in os.environ.items() if not k.startswith(('PIP_', 'SHIMMER_', 'HF_')) and
             not any(x in k.upper() for x in ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY'))}
    clean.update(HF_HOME=str(base / 'hf_cache'), HF_HUB_CACHE=str(base / 'hf_cache/hub'),
                 HF_HUB_DISABLE_IMPLICIT_TOKEN='1', HF_HUB_DISABLE_TELEMETRY='1', PIP_CONFIG_FILE=os.devnull)
    if deps['missing']:
        subprocess.run([python, '-m', 'pip', 'install', '--no-index', '--no-deps', '--only-binary=:all:',
                    '--require-hashes', '--find-links', str(base / 'wheels'), '-r', str(base / 'install.lock')],
                   env=clean, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deps = python_runtime.subprocess_check(selected, base, dependencies=True, contract_file=base / 'runtime.json')
    require(deps['dependencies_ready'], 'Dependencies unavailable after installation')
    event(base, 'dependencies_ready')
    sanity = (f'import torch; assert torch.__version__ == {runtime['torch']!r}; '
              f'assert torch.version.cuda == {runtime['cuda_runtime']!r}; assert torch.cuda.is_available(); '
              'assert torch.cuda.device_count() == 1; '
              'x=torch.ones(1,device="cuda:0"); assert x.item()==1; torch.cuda.synchronize()')
    subprocess.run([python, '-c', sanity], env=clean, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    write_json(base / 'REMOTE_SANITY_PASSED.json', gpu)
    subprocess.run([python, str(base / 'cloud_run_remote.py'), '--execute', '--hydrate-only'], env=clean,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    event(base, 'models_ready')
    event(base, 'run_start')
    result = subprocess.run([python, str(base / 'cloud_run_observer.py')], env=clean,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    event(base, 'run_finish')
    score_code = None
    if result.returncode == 0:
        with (evidence / 'score.txt').open('w', encoding='utf-8') as stream:
            score = subprocess.run([python, str(base / 'project/tools/score_corpus.py'), '--corpus',
                    str(base / 'project/benchmark/corpora/clinical_reference'), '--run', str(evidence / 'run')],
                    env=clean, stdout=stream, stderr=subprocess.DEVNULL)
            score_code = score.returncode
    from cloud_run_observer import summarize
    def rows(name):
        path = evidence / name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    write_json(evidence / 'metrics.json', summarize(rows('events.jsonl'), rows('scheduler.jsonl'), rows('lifecycle.jsonl')))
    write_json(evidence / 'collection_hashes.json', {p.relative_to(evidence).as_posix(): digest(p) for p in sorted(evidence.rglob('*')) if p.is_file()})
    require(result.returncode == 0 and score_code == 0, 'run/scoring failed; non-benchmark')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # No exception messages, subprocess output or provider responses escape.
        print(json.dumps({'remote_failed': True, 'error_type': type(exc).__name__}))
        raise SystemExit(2)
