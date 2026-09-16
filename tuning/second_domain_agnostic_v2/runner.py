"""Materialize immutable fold/canonical execution plans; dry-run is the only mode.

Future model work requires a separately authorized executor consuming this
artifact. This CLI cannot load models, dispatch a provider, or start training.
"""
import argparse
import random
from runtime import *


def verify_freeze():
    freeze=read(HERE/'freeze.json')
    for name,expected in freeze['files'].items():
        p=(ROOT/name).resolve();require(p.is_relative_to(HERE),'Freeze path escapes V2')
        require(p.is_file() and not p.is_symlink() and sha(p.read_bytes())==expected,'Release changed: '+name)
    for name,expected in freeze['dependency_files'].items():
        p=(ROOT/name).resolve();require(p.is_relative_to(ROOT),'Dependency path escapes repository')
        require(sha(p.read_bytes())==expected,'Frozen dependency changed: '+name)
    return sha((HERE/'freeze.json').read_bytes())


def plan(role,split_name,rows=None):
    rows=read(HERE/'dataset.json') if rows is None else rows
    splits=read(HERE/'splits.json')
    selected=splits['canonical'] if split_name=='canonical' else splits['folds'][int(split_name)]
    check_split(rows,selected)
    config=read(HERE/role/'experiment.json')
    require(config['dataset_sha256']==sha((HERE/'dataset.json').read_bytes()),'Dataset not bound to configuration')
    train=[r['example_id'] for r in rows if r['role']==role and r['example_id'] in selected['train']]
    validation=[r['example_id'] for r in rows if r['role']==role and r['example_id'] in selected['validation']]
    require(len(train)==240 and len(validation)==60,'Frozen role population changed')
    steps=[]
    for epoch in range(config['training']['data_epochs']):
        order=list(train);random.Random(config['training']['seed']+epoch).shuffle(order)
        size=config['training']['gradient_accumulation']
        for i in range(0,len(order),size):steps.append(dict(step=len(steps)+1,epoch=epoch+1,example_ids=order[i:i+size],loss_divisor=len(order[i:i+size])))
    require(len(steps)==config['training']['max_steps'],'Schedule mismatch')
    require(not set(validation)&{i for s in steps for i in s['example_ids']},'Validation in gradients')
    return dict(role=role,split=split_name,configuration_sha256=sha(config),dataset_sha256=config['dataset_sha256'],
        train_ids=train,validation_ids=validation,optimizer_schedule=steps,checkpoint_steps=config['checkpoint_steps'],
        output_directory=f'runs/second-domain-agnostic-v2/{split_name}/{role}',
        output_requirements=['adapter and identity per checkpoint','raw validation output and token IDs','per-row semantic metrics','selection decision including every failed gate','runtime and loss diagnostics'],
        total_example_visits=sum(len(s['example_ids']) for s in steps),validation_generations_planned=len(validation)*len(config['checkpoint_steps']),
        training_authorized=False,model_execution_performed=False)


def select_checkpoint(role,checkpoints):
    spec=read(HERE/role/'experiment.json');require(sorted(x['step'] for x in checkpoints)==spec['checkpoint_steps'],'Incomplete checkpoint schedule')
    admitted=[x for x in checkpoints if selection_pass(x['metrics'],spec['selection_gates'])]
    require(admitted,'No V2 checkpoint passes prospective gates')
    keys=('semantic_completeness','typed_gaps_f1') if role=='producer' else ('macro_relation_f1','accepted_semantic_outcomes')
    return sorted(admitted,key=lambda x:(-x['metrics'][keys[0]],-x['metrics'][keys[1]],x['step'],x['adapter_sha256']))[0]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--role',choices=('producer','auditor'),required=True)
    parser.add_argument('--split',choices=('canonical','0','1','2','3','4'),required=True)
    parser.add_argument('--dry-run',action='store_true',required=True)
    args=parser.parse_args();binding=verify_freeze();result=plan(args.role,args.split)
    print(json.dumps(dict(role=args.role,split=args.split,train=len(result['train_ids']),validation=len(result['validation_ids']),
        optimizer_updates=len(result['optimizer_schedule']),freeze_sha256=binding,training_executed=False),indent=2))
