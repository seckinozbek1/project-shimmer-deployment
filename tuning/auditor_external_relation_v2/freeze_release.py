"""Freeze reviewed local V2 preparation artifacts without experiment admission."""
from local_utils import *
def main():
    assert read(HERE/'test_evidence.json')['passed'] and read(HERE/'rebuild_evidence.json')['passed']
    files=sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='freeze.json')
    files += [ROOT/'tools/download_auditor_external_v2.py',ROOT/'docs/fix/AUDITOR_EXTERNAL_RELATION_DATA_V2.md']
    inputs=['tuning/auditor_external_relation_v1/freeze.json','tuning/auditor_canonical_execution/dataset.json',
        'tuning/auditor_canonical_execution/split.json','tuning/auditor_linear_probe/experiment.json','tools/auditor_linear_core.py',
        'tuning/second_domain_agnostic_v2/runtime.py','tuning/first_domain_agnostic_v1/common.py',
        'tuning/first_domain_agnostic_v1/auditor/experiment.json','scripts/compact_contracts.py']
    write('freeze.json',dict(verdict='AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY',status='FROZEN_PREPARATION_NOT_ADMITTED',
        source_commit='dca2d64cfe666928f70da07ecfc8038437a3f6ec',data_admitted=False,holdout_consumed=False,
        files={p.relative_to(ROOT).as_posix():sha(p) for p in files},input_bindings={p:sha(ROOT/p) for p in inputs}))
if __name__=='__main__':main()
