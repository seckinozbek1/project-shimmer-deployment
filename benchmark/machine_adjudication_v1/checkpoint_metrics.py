"""Maintained first-experiment saved-output adapter (never runs a model).

Preserves every frozen threshold and human readiness check. Machine label
readiness never sets R01/R02 or the legacy human-ready status to passing.
"""
import sys
from pathlib import Path
import r06

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'benchmark/first_tuning_experiment_v1'))
import registration as legacy


def evaluate(scores,rows,coverage,governance_violations=0):
    index={r['example_id']:r for r in rows}
    if any(s.get('example_id') not in index for s in scores):
        raise ValueError('Unknown checkpoint score ID')
    # Apply registered evaluation population before EVERY performance metric.
    selected=[s for s in scores if r06.non_train(index[s['example_id']])]
    result=legacy.evaluate_thresholds(selected,rows,coverage,governance_violations)
    spec=legacy.read(legacy.HERE/'acceptance_registration.json');legacy.verify_profile(spec)
    family=r06.evaluate_registered(selected,rows,coverage['accepted_targets'],spec)
    result['criteria']['R06']=dict(measured=family['measured'],passed=family['passed'])
    result['families']=family['families'];result['r06_population']=family['population']
    result['measurement_complete']=result['measurement_complete'] and family['measurement_complete']
    result['promising_checkpoint']=(coverage['status']=='FIRST_TUNING_EXPERIMENT_REVIEW_READY'
        and result['measurement_complete'] and result['R07']['passed']
        and all(v['passed'] is True for v in result['criteria'].values()))
    result['population_adapter']='r06-non-train-v1'
    return result


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser(description='Evaluate existing saved scores only; no inference or training')
    parser.add_argument('--scores',type=Path,required=True)
    parser.add_argument('--rows',type=Path,required=True)
    parser.add_argument('--coverage',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    value=evaluate(legacy.read(args.scores),legacy.read(args.rows),legacy.read(args.coverage))
    legacy.write(args.out,value)
    print(json.dumps(dict(population_adapter=value['population_adapter'],promising_checkpoint=value['promising_checkpoint'],training_authorized=False)))
