"""Verify the frozen quarantine release without datasets, tokenizer or model loading."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def check_identity(data,expected):
    if hashlib.sha256(data).hexdigest()!=expected:
        raise ValueError('Frozen artifact hash mismatch')

def main():
    f=json.loads((HERE/'freeze.json').read_text(encoding='utf8'))
    for path,expected in f['files'].items():
        check_identity((ROOT/path).read_bytes(),expected)
    for path,expected in f['historical_input_bindings'].items():
        check_identity((ROOT/path).read_bytes(),expected)
    for filename in ['examples.jsonl','substantive_relation_view.jsonl','merged_auditor_view.jsonl']:
        rows=[json.loads(x) for x in (HERE/filename).read_text(encoding='utf8').splitlines()]
        assert len({r['example_id'] for r in rows})==len(rows)
    receipt=json.loads((HERE/'holdout_receipt.json').read_text(encoding='utf8'))
    assert not receipt['consumed'] and not receipt['admitted'] and receipt['evaluation_count']==0
    e=json.loads((HERE/'experiment.json').read_text(encoding='utf8'))
    assert not e['execution_authorized'] and not e['data_admitted'] and not e['training_authorized'] and not e['cloud_authorized']
    try:check_identity(b'altered artifact','0'*64)
    except ValueError:pass
    else:raise AssertionError('Tamper fixture admitted')
    print(json.dumps(dict(files_verified=len(f['files']),historical_inputs_verified=len(f['historical_input_bindings']),
                         holdout_unconsumed=True,tamper_fixture_rejected=True,verdict=f['verdict'])))

if __name__=='__main__':main()
