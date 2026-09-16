"""Post-termination evidence verification and local no-model failure reproduction."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/fix/producer_checkpoint120_eval_runtime_v2'
RT=ROOT/'tuning/second_tuning_eval_runtime_v2'
sys.path.insert(0,str(RT))
import release
import checks
import eval_runtime as ev
sys.path.insert(0,str(ROOT/'tools'))
from cloud_run_common import credential_locations

def read(path):return json.loads(Path(path).read_text())
def main():
    termination=read(BASE/'TERMINATION_VERIFIED.json')
    assert read(BASE/'instances_after.json')==[] and read(BASE/'FINAL_INVENTORY.json')['zero_billable_instances']
    assert all(read(BASE/'cleanup.json')[k] for k in ('temporary_ssh_removed','local_key_material_removed'))
    integrity=read(BASE/'collection_integrity.json')
    assert release.digest(BASE/'evidence.tar.gz')==integrity['sha256']
    history=release.verify()
    data=BASE/'downloaded';evidence=data/'evidence'
    manifest=read(BASE/'execution_manifest.json')
    assert read(data/'execution_manifest.json')==manifest
    assert release.digest(data/'tools/checkpoint120_remote.py')==manifest['files']['tools/checkpoint120_remote.py']
    assert release.digest(data/'tuning/second_tuning_eval_runtime_v2/freeze.json')==manifest['runtime_release_sha256']
    assert read(data/'evaluation_authorization.json')==read(BASE/'evaluation_authorization.json')
    preflight=read(evidence/'preflight.json');peft=read(evidence/'peft_preflight.json')
    assert preflight['passed'] and not preflight['optimizer_created'] and peft['adapter_tensor_identity']
    protocol=read(RT/'protocol.json')
    assert peft['adapter_hashes']==protocol['adapter']['files']
    acquisition=read(evidence/'acquisition.json')
    for name,value in protocol['base_weight_hashes'].items():assert acquisition['files'][name]==value
    rawfiles=list(evidence.glob('cache_*.jsonl'))+list(evidence.glob('control_*.jsonl'))+list(evidence.glob('full_dev.jsonl'))
    assert all(not p.read_text().strip() for p in rawfiles)
    assert not (evidence/'control_admission.json').exists() and not (evidence/'admitted.json').exists()
    assert not (evidence/'cache_admission.json').exists()
    # Reproduce the exact frozen entry failure with the missing state case.
    model=checks.Model();model.child.generation_config=None
    before=[m.training for m in model.modules()]
    failure=None;entered=False
    try:
        with ev.evaluation_state(model,checks.TorchFacade()):entered=True
    except TypeError as exc:failure=str(exc)
    assert failure=='vars() argument must have __dict__ attribute'
    assert not entered and not model.calls and before==[m.training for m in model.modules()]
    source=Path(sys.executable).parent/'Lib/site-packages/transformers/modeling_utils.py'
    lines=source.read_text(encoding='utf8').splitlines()
    matches=[(i+1,line.strip()) for i,line in enumerate(lines) if 'self.generation_config = GenerationConfig.from_model_config(config) if self.can_generate() else None' in line]
    assert len(matches)==1
    security_count=0
    for p in BASE.rglob('*'):
        if p.is_file() and p.suffix in ('.py','.json','.jsonl','.md','.log'):
            hits=credential_locations(p.read_bytes(),str(p.relative_to(ROOT)))
            if hits:
                for hit in hits:print('WARNING: Possible API key detected in '+hit['file']+':'+str(hit['line'])+'. Do not push. Rotate the key immediately.')
                raise SystemExit(1)
            security_count+=1
    result=dict(checkpoint_result='PRODUCER_CHECKPOINT120_INDETERMINATE',admission='CHECKPOINT120_EVALUATION_NO_GO',
        invalidating_issue='Frozen evaluation_state snapshots vars(None) for a non-generating module generation_config',
        exact_remote_object_not_instrumented=True,local_none_reproduction=True,reproduction_generations=0,context_entered=False,
        pinned_source=dict(path='transformers/modeling_utils.py',sha256=release.digest(source),line=matches[0][0],statement=matches[0][1]),
        cache_preflight='INTERRUPTED_BEFORE_GENERATION',reference_controls=0,optimized_controls=0,full_dev_rows=0,
        tokens_identity_6_of_6=None,semantic_identity_6_of_6=None,reference_tokens_per_second=None,optimized_tokens_per_second=None,speed_ratio=None,
        metrics=None,adapter_tensor_identity_verified=True,adapter_devices=sorted({x['device'] for x in peft['adapter_parameters']}),
        adapter_dtypes=sorted({x['dtype'] for x in peft['adapter_parameters']}),adapter_active=peft['active_adapters'],
        cache_helper_mentions_use_cache='use_cache' in peft['preparation_source'],historical_verification=history,
        termination=termination,security_files_scanned=security_count,credential_findings=0,
        AUDITOR_STATUS='UNTOUCHED',PROTECTED_RECEIPT_STATUS='UNCONSUMED',no_second_instance=True,
        next_action='Local-only runtime state-snapshot correction and real pinned-module fixture proof in a new prospective freeze; no automatic cloud retry')
    (BASE/'RECOMPUTED_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
