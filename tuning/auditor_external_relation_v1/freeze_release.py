"""Explicitly freeze preparation artifacts; never authorizes experiment execution."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    for name in ['test_evidence.json','rebuild_evidence.json']:
        assert json.loads((HERE/name).read_text(encoding='utf8'))['passed']
    files=sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='freeze.json')
    files += [ROOT/'docs/fix/AUDITOR_EXTERNAL_RELATION_DATA_V1.md',ROOT/'docs/fix/AUDITOR_EXTERNAL_DATA_ATTRIBUTION.md',ROOT/'tools/download_auditor_external.py']
    inputs=['tuning/auditor_canonical_execution/dataset.json','tuning/auditor_canonical_execution/split.json',
            'tuning/auditor_linear_probe/experiment.json','tools/auditor_linear_core.py',
            'tuning/second_domain_agnostic_v2/runtime.py','tuning/first_domain_agnostic_v1/common.py',
            'tuning/first_domain_agnostic_v1/auditor/experiment.json','scripts/compact_contracts.py']
    value=dict(verdict='AUDITOR_EXTERNAL_RELATION_DATA_V1_NOT_READY',status='FROZEN_QUARANTINE_ONLY',
        source_commit='6cd753962c51eb076802ebe0851f2369aea624aa',data_admitted=False,
        files={p.relative_to(ROOT).as_posix():sha(p) for p in files},
        historical_input_bindings={p:sha(ROOT/p) for p in inputs},
        raw_sources='Hash-bound in source_manifest.json; deliberately not committed',
        holdout_consumed=False,weights_opened=False,training_executed=False)
    (HERE/'freeze.json').write_bytes((json.dumps(value,indent=2,sort_keys=True)+'\n').encode())

if __name__=='__main__':main()
