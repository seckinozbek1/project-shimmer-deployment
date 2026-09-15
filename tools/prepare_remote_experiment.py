"""Fail-fast bounded experiment preparation. No provisioning or transport.

The default CLI performs local runtime/source/dependency checks only. Expensive
stages require --execute and are restricted to the ordinary short-burst harness.
An existing compatible environment is required; no implicit environment rebuild.
"""
from __future__ import annotations
import argparse
import json
import importlib.metadata
from pathlib import Path
import subprocess
import sys
import time

from cloud_run_common import digest, verify_files, write_json
import runtime_contract as runtime


def prepare(root, manifest, output, *, candidate_commands=None, install=None,
            acquire=None, hydrate=None, infer=None, runner=subprocess.run,
            profile='experiment'):
    """The only route to callbacks is through all required hard gates.

    Callbacks receive the final selection. No callback resolves its own Python.
    A failed attempt cannot retain a readiness marker from an earlier attempt.
    """
    root, output = Path(root).absolute(), Path(output).absolute()
    output.mkdir(parents=True, exist_ok=False)
    evidence = {'ready': False, 'stages': [], 'stage_observations': [], 'multi_round': False}
    def stage(name, action):
        begin = time.time()
        try:
            value = action()
        except Exception:
            evidence['stage_observations'].append(dict(name=name, start_epoch=begin, seconds=time.time()-begin, passed=False))
            raise
        evidence['stage_observations'].append(dict(name=name, start_epoch=begin, seconds=time.time()-begin, passed=True, result=value))
        evidence['stages'].append(name)
        write_json(output / 'preparation.json', evidence)
        return value
    try:
        selection = stage('resolve_runtime', lambda: runtime.resolve(
            candidate_commands, root=root, profile=profile, runner=runner))
        evidence['interpreter'] = selection
        stage('source_integrity', lambda: verify_files(root, manifest, exact=False))
        # The manifest must cover every source file that compilation/import can consume.
        required = {p.relative_to(root).as_posix() for folder in ('scripts', 'tools', 'corpus_ingest')
                    for p in (root / folder).rglob('*.py') if '__pycache__' not in p.parts}
        if not required <= set(manifest):
            raise runtime.RuntimeContractError('Source integrity manifest omits executable source')
        evidence['source_preflight'] = stage('source_compile_import', lambda:
            runtime.subprocess_check(selection, root, runner=runner))
        dependencies = stage('dependency_check', lambda:
            runtime.subprocess_check(selection, root, dependencies=True, runner=runner))
        if dependencies['missing']:
            if install is None:
                raise runtime.RuntimeContractError('Missing declared dependencies: ' + ', '.join(dependencies['missing']))
            stage('install_missing_dependencies', lambda: install(selection, dependencies['missing']))
            dependencies = stage('dependency_recheck', lambda:
                runtime.subprocess_check(selection, root, dependencies=True, runner=runner))
            if not dependencies['dependencies_ready']:
                raise runtime.RuntimeContractError('Dependencies remain unavailable after explicit installation')
        evidence['dependencies'] = dependencies
        write_json(output / 'PRE_INFERENCE_CHECKPOINT.json', dict(
            interpreter=selection, source_integrity_passed=True,
            source_preflight=evidence['source_preflight'], dependencies=dependencies,
            all_green=dependencies['dependencies_ready'], epoch=time.time(), multi_round=False))
        for name, action in (('model_acquisition', acquire), ('model_hydration', hydrate), ('bounded_inference', infer)):
            if action is not None:
                stage(name, lambda action=action: action(selection))
        evidence['ready'] = True
        write_json(output / 'preparation.json', evidence)
        write_json(output / 'READY.json', evidence)
        return evidence
    except Exception as exc:
        evidence['failed_stage'] = len(evidence['stages'])
        evidence['error'] = str(exc) if isinstance(exc, runtime.RuntimeContractError) else type(exc).__name__
        write_json(output / 'preparation.json', evidence)
        raise


def install_missing(selected, missing, root, output, runner=subprocess.run):
    """Resolve only missing core packages and their pinned dependency closure.

    A dry-run plan is validated before mutation. Existing distributions cannot
    be replaced, and every proposed package/version must be in runtime.lock.
    """
    lock = root / 'tools/cloud_run/runtime.lock'
    pins = dict(line.split('==', 1) for line in lock.read_text().splitlines()
                if '==' in line and not line.startswith('#'))
    pins = {k.lower().replace('_', '-'):v for k,v in pins.items()}
    plan = output / 'dependency_install_plan.json'
    index = ['--index-url', 'https://pypi.org/simple', '--extra-index-url', 'https://download.pytorch.org/whl/cu121']
    runner(runtime.command(selected, '-m', 'pip', 'install', '--dry-run', '--report', plan,
        '--only-binary=:all:', '--constraint', lock, *index,
        *[name+'=='+pins[name] for name in missing]), check=True)
    raw_plan = json.loads(plan.read_text(encoding='utf-8'))
    proposed = [dict(metadata=dict(name=item['metadata']['name'], version=item['metadata']['version']))
                for item in raw_plan['install']]
    # Package README descriptions can contain public badge query tokens. They
    # are unnecessary evidence: retain only the installation decision fields.
    write_json(plan, dict(install=proposed, projection='package names and versions only'))
    del raw_plan
    # Query the selected environment, never the bootstrap environment.
    query = 'import importlib.metadata as m,json;print(json.dumps({d.metadata["Name"].lower().replace("_","-"):d.version for d in m.distributions()}))'
    current = runner(runtime.command(selected, '-I', '-c', query), capture_output=True, text=True, check=True)
    installed = json.loads(current.stdout)
    names=[]
    for item in proposed:
        name=item['metadata']['name'].lower().replace('_','-'); version=item['metadata']['version']
        if name not in pins or version != pins[name] or name in installed:
            raise runtime.RuntimeContractError('Dependency plan would change an existing or undeclared distribution: '+name)
        names.append(name+'=='+version)
    if names:
        runner(runtime.command(selected, '-m', 'pip', 'install', '--no-deps', '--only-binary=:all:', *index, *names), check=True)


def main(argv=None, runner=subprocess.run):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--interpreter', action='append', help='Candidate absolute Python path; every candidate is queried')
    p.add_argument('--execute', action='store_true', help='Requires separate cloud/model authorization')
    p.add_argument('--install-missing', action='store_true', help='Explicitly install missing core packages at declared pins')
    args = p.parse_args(argv)
    root = args.root.absolute()
    source = json.loads(args.manifest.read_text())
    manifest = {name: item['sha256'] for name, item in source['source_files'].items()}
    # Verify the contract/lock as well as code, before either can authorize downloads.
    for name in ('tools/cloud_run/runtime.json', 'tools/cloud_run/runtime.lock'):
        if name not in manifest:
            p.error('Source manifest must include runtime contract and dependency lock')
    def install(selected, missing):
        install_missing(selected, missing, root, args.output.absolute(), runner)
    def acquire(selected):
        runner(runtime.command(selected, root / 'tools/remote_experiment_models.py', '--execute', '--root', root, '--output', args.output.absolute() / 'model_acquisition.json'), check=True)
    def infer(selected):
        runner(runtime.command(selected, root / 'tools/remote_short_burst_probe.py', '--execute', '--output', args.output.absolute() / 'probe'), check=True)
    # Checking locally cannot install even if --install-missing was accidentally supplied.
    report = prepare(root, manifest, args.output, candidate_commands=args.interpreter, runner=runner,
        install=install if args.execute and args.install_missing else None,
        acquire=acquire if args.execute else None, infer=infer if args.execute else None)
    print(json.dumps(report))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({'preparation_failed': True, 'error': str(exc) if isinstance(exc, runtime.RuntimeContractError) else type(exc).__name__}))
        raise SystemExit(2)
