"""Aggregate future five-fold evidence at both predeclared checkpoints."""
import argparse
from runtime import *
from runner import verify_freeze,plan


def collect(directory):
    binding=verify_freeze();result={}
    rows={r['example_id']:r for r in read(HERE/'dataset.json')}
    for role in ('producer','auditor'):
        checkpoints=read(HERE/role/'experiment.json')['checkpoint_steps'];role_metrics={str(s):[] for s in checkpoints}
        for fold in range(5):
            folder=directory/str(fold)/role;expected=plan(role,str(fold))
            saved=read(folder/'RUN_BINDING.json')
            require(saved['release_sha256']==binding and saved['plan']==expected,'Unbound fold evidence')
            for step in checkpoints:
                evidence=read(folder/f'validation-{step}.json')
                require([r['example_id'] for r in evidence]==expected['validation_ids'],'Fold validation population changed')
                scores=[]
                for item in evidence:
                    ident=item['identity']
                    require(ident['role']==role and ident['split']==str(fold) and ident['step']==step and ident['release_sha256']==binding,'Wrong fold/checkpoint identity')
                    current=score(rows[item['example_id']],item['raw_output'],item['truncated'])
                    require(current==item['metrics'],'Nonreproducible semantic metrics')
                    scores.append(current)
                role_metrics[str(step)].append(aggregate(scores))
        result[role]={step:dict(per_fold=folds,summary=cv_summary(folds)) for step,folds in role_metrics.items()}
    return dict(release_sha256=binding,selection_use='Robustness reporting only; canonical split and hyperparameters remain frozen.',roles=result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--runs',type=Path,default=ROOT/'runs/second-domain-agnostic-v2')
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    write(args.output,collect(args.runs))
