"""Score saved candidate outputs offline; never generate or export held-out gold.

Input: JSON list of {example_id, raw, truncated, completed, provenance}.
Provenance must be authored_diagnostic or generated_model, with source_run_id.
Generated records additionally require model_id and model_revision. Metrics are
reported separately by provenance; no tokenizer-authored/model conflation.
"""
import argparse
import json
from pathlib import Path
import core as c
from run_gate import validate_artifacts


def score_saved(candidates, records, split):
    c.verify_freeze();validate_artifacts(records);c.leakage(records)
    index={r['example_id']:r for r in records if r['split']==split}
    seen=set();results=[]
    for value in candidates:
        required={'example_id','raw','truncated','completed','provenance','source_run_id'}
        if not required<=set(value) or value['example_id'] in seen or value['example_id'] not in index:
            raise ValueError('Missing, duplicate or wrong-split candidate')
        if type(value['truncated']) is not bool or type(value['completed']) is not bool or not isinstance(value['raw'],str):
            raise ValueError('Invalid transport metadata')
        if not value['source_run_id'] or value['provenance'] not in ('authored_diagnostic','generated_model'):
            raise ValueError('Candidate provenance missing')
        if value['provenance']=='generated_model' and (not value.get('model_id') or not value.get('model_revision')):
            raise ValueError('Generated model identity missing')
        seen.add(value['example_id'])
        result=c.evaluate(index[value['example_id']],value['raw'],truncated=value['truncated'],completed=value['completed'])
        result.update(provenance=value['provenance'],source_run_id=value['source_run_id'])
        results.append(result)
    if not results:raise ValueError('No candidate observations')
    return dict(results=results,by_provenance={p:c.aggregate([r for r in results if r['provenance']==p])
                for p in sorted({r['provenance'] for r in results})},
                coverage=dict(supplied=len(results),expected=len(index),missing_examples=sorted(set(index)-seen)),
                model_acceptance='NOT_ASSESSED_PUBLIC_SEED',production_execution=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('candidates',type=Path);parser.add_argument('--split',required=True,choices=c.SPLITS[:-1])
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    result=score_saved(c.read(args.candidates),c.read(Path(__file__).with_name('seed.json')),args.split)
    c.write(args.out,result)
