"""Seal or verify local-only Producer V3 design; no training entry point."""
from local_common import *
import argparse
sys.path.insert(0,str(ROOT/'tools'))
from cloud_run_common import credential_locations

REPORT=ROOT/'docs/fix/PRODUCER_TUNING_V3_DESIGN.md'
VERDICT='PRODUCER_TUNING_V3_DESIGN_READY'

def preservation():
    manifest=read(HERE/'historical_preservation.json')
    for name,digest in manifest['files'].items():assert sha(ROOT/name)==digest,name
    for name,entry in manifest['metadata_only'].items():
        st=(ROOT/name).stat();assert st.st_size==entry['size'] and st.st_mtime_ns==entry['mtime_ns'],name
    excluded=read(ROOT/'tuning/second_tuning_eval_runtime_v2_1/excluded_binary_metadata.json')
    count=0
    for name,entry in excluded.items():
        if not name.endswith('.safetensors'):continue
        st=(ROOT/name).stat();assert st.st_size==entry['size'] and st.st_mtime_ns==entry['mtime_ns'];count+=1
    receipts=[ROOT/'runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json',
              ROOT/'runs/second-domain-agnostic-v2/PROTECTED_ACCESS_CONSUMED.json',
              ROOT/'docs/fix/first_real_tuning_20260916/downloaded/runs/first-domain-agnostic-tuning-v1/PROTECTED_ACCESS_CONSUMED.json']
    assert not any(p.exists() for p in receipts)
    return dict(historical_byte_hashes_verified=len(manifest['files']),protected_artifacts_metadata_verified=len(manifest['metadata_only']),weight_metadata_verified=count,weight_bytes_opened=0,protected_receipt='UNCONSUMED',
        preservation_scope_note='Initial inventory byte-hashed the existing protected evaluator wrapper and protected_population manifest without parsing/execution. No protected target-label files were opened; subsequent checks are metadata-only.')

def seal():
    assert not (HERE/'freeze.json').exists(),'Already frozen; verify instead'
    history=preservation();assert read(HERE/'dry_run_evidence.json')['passed']
    assert read(HERE/'review_adjudication.json')['passed'] and read(HERE/'leakage_audit.json')['passed']
    spec=read(HERE/'experiment.json');assert not spec['training_authorized']
    assert len(list(HERE.glob('**/experiment.json')))==1
    paths=sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts)+[REPORT]
    for p in paths:
        findings=credential_locations(p.read_bytes(),str(p.relative_to(ROOT)))
        if findings:
            for h in findings:print('WARNING: Possible API key detected in '+h['file']+':'+str(h['line'])+'. Do not push. Rotate the key immediately.')
            raise SystemExit(1)
    write(HERE/'security_scan.json',dict(files_scanned=len(paths),credential_findings=0,model_weights_in_release=0))
    paths.append(HERE/'security_scan.json')
    dependencies=['tuning/second_domain_agnostic_v2/runtime.py','tuning/first_domain_agnostic_v1/common.py',
        'benchmark/producer_coverage_amendment_v3/semantics.py','benchmark/producer_coverage_amendment_v3/structural.py',
        'scripts/compact_contracts.py','scripts/bounded_extraction.py','tools/cloud_run_common.py','benchmark/task_semantics/core.py']
    dependencies += ['tuning/second_tuning_eval_runtime_v2_1/'+n for n in ('freeze.json','eval_runtime.py','config_state.py','remote_preflight.py','telemetry_worker.py')]
    write(HERE/'freeze.json',dict(name='producer-targeted-v3.0',verdict=VERDICT,source_head='e712bb9d5d64f4af2181154e595383216ef51cf1',
        files={p.relative_to(ROOT).as_posix():sha(p) for p in paths},dependency_files={name:sha(ROOT/name) for name in dependencies},
        preservation=history,training_authorized=False,cloud_authorized=False,model_generation_authorized=False,
        human_reviewed=False,independent_final_benchmark=False,stop_rule=spec['final_stop_rule']))
    return verify()

def verify():
    freeze=read(HERE/'freeze.json')
    for section in ('files','dependency_files'):
        for name,digest in freeze[section].items():
            p=(ROOT/name).resolve();assert p.is_relative_to(ROOT) and p.is_file() and not p.is_symlink()
            assert sha(p)==digest,name
    preservation()
    return dict(verdict=freeze['verdict'],release_sha256=sha(HERE/'freeze.json'),bound_files=len(freeze['files']),training_authorized=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--seal',action='store_true');args=parser.parse_args()
    print(json.dumps(seal() if args.seal else verify(),indent=2))
