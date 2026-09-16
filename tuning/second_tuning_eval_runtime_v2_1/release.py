"""Prospective V2.1 freeze. Never opens model weights or contacts a provider."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'tuning/second_tuning_eval_runtime_v2'
REPORT=ROOT/'docs/fix/EVALUATION_RUNTIME_NULLABILITY_FIX.md'

def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def digest(path):
    path=Path(path)
    if path.suffix in ('.safetensors','.bin','.pt','.pth','.onnx'):
        raise PermissionError('No weight access in nullability release')
    return hashlib.sha256(path.read_bytes()).hexdigest()

def history():
    entries=read(HERE/'historical_preservation.json')
    for name,expected in entries.items():
        p=(ROOT/name).resolve()
        if not p.is_relative_to(ROOT) or digest(p)!=expected:raise ValueError('Historical file changed: '+name)
    exclusions=read(HERE/'excluded_binary_metadata.json')
    for name,expected in exclusions.items():
        st=(ROOT/name).stat()
        if (st.st_size,st.st_mtime_ns)!=(expected['size'],expected['mtime_ns']):raise ValueError('Excluded artifact metadata changed: '+name)
    for name in ('runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json','runs/second-domain-agnostic-v2/PROTECTED_ACCESS_CONSUMED.json','docs/fix/first_real_tuning_20260916/downloaded/runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json'):
        if (ROOT/name).exists():raise ValueError('Protected receipt changed')
    return dict(byte_verified_files=len(entries),metadata_only_files=len(exclusions),weight_bytes_opened=0)

def semantic_binding():
    before=read(OLD/'protocol.json');after=read(HERE/'protocol.json')
    for key in ('name','runtime_parent_sha256','real_runtime_context_preflight'):
        before.pop(key,None);after.pop(key,None)
    if before!=after:raise ValueError('Task semantics changed')
    if read(HERE/'protocol.json')['runtime_parent_sha256']!=digest(OLD/'freeze.json'):raise ValueError('Parent runtime binding changed')
    adapter=read(OLD/'adapter_binding.json')
    if adapter['files']!=after['adapter']['files']:raise ValueError('Adapter hash binding changed')
    return True

def freeze():
    destination=HERE/'freeze.json'
    if destination.exists():raise ValueError('Already frozen; no overwrite')
    preserved=history();semantic_binding()
    tests=read(HERE/'test_results.json')
    if not tests['passed'] or tests['tests']!=92 or tests['effect_proof_count']!=11:raise ValueError('Required tests/effects missing')
    if tests['torch_imported'] or tests['model_weight_reads'] or tests['real_model_generations']:raise ValueError('Local-only constraint violated')
    files=[p for p in HERE.iterdir() if p.is_file() and p.name!='freeze.json']+[REPORT]
    # Bind reused exact prompts, tokenizer/metric/config source and prior tests.
    dependencies=set(read(OLD/'freeze.json')['files'])
    prior=read(ROOT/'tuning/second_domain_agnostic_v2/freeze.json')
    dependencies.update(name.replace('\\','/') for name in prior['dependency_files']
                        if name.endswith('.py') or name.endswith('dependency_lock.json'))
    dependencies.update(('tuning/second_domain_agnostic_v2/runtime.py','tuning/second_domain_agnostic_v2/producer/experiment.json',
                         'tuning/second_domain_agnostic_v2/freeze.json','tools/second_tuning_remote.py','tools/checkpoint120_remote.py'))
    dependencies={name for name in dependencies if 'auditor' not in Path(name).parts and 'protected_eval' not in name}
    value=dict(name='second-tuning-eval-runtime-v2_1',verdict='EVALUATION_RUNTIME_NULLABILITY_FIX_READY',
        historical_v2_freeze_sha256=digest(OLD/'freeze.json'),source_head_before_changes='5bb23f1f0d5a2bee1e57e326e8b4689af63a9d1d',
        cloud_authorized=False,model_execution_authorized=False,training_authorized=False,
        real_runtime_context_preflight_required=True,semantics_unchanged=True,history=preserved,
        adapter_hash=read(HERE/'protocol.json')['adapter']['files']['adapter_model.safetensors'],
        files={p.relative_to(ROOT).as_posix():digest(p) for p in sorted(files)},
        dependency_files={name:digest(ROOT/name) for name in sorted(dependencies)})
    with destination.open('x',encoding='utf8',newline='\n') as stream:stream.write(json.dumps(value,indent=2)+'\n')
    return verify()

def verify():
    frozen=read(HERE/'freeze.json')
    for section in ('files','dependency_files'):
        for name,expected in frozen[section].items():
            p=(ROOT/name).resolve()
            if not p.is_relative_to(ROOT) or digest(p)!=expected:raise ValueError('Release binding changed: '+name)
    preserved=history();semantic_binding()
    return dict(verdict=frozen['verdict'],release_sha256=digest(HERE/'freeze.json'),bound_files=len(frozen['files'])+len(frozen['dependency_files']),
                history=preserved,protected_receipt='UNCONSUMED',cloud_authorized=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('freeze','verify'));args=parser.parse_args()
    print(json.dumps(freeze() if args.action=='freeze' else verify(),indent=2))
