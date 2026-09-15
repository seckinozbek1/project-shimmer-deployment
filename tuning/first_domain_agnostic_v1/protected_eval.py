"""Future one-shot protected BASE/TUNED evaluation, after BOTH selection freezes.

Kept outside the training bundle along with protected-population metadata.
Authored datasets are never opened by preparation or the local dry-run.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from evaluation import verify_selection,LocalGenerator,paired_variants
from train import authorization,runtime

def claim_access(run_root,open_sources):
    run_root=Path(run_root)
    selected={role:verify_selection(role,run_root/role) for role in PINS}
    receipt=dict(experiment=EXPERIMENT,phase='POST_SELECTION_PROTECTED_ONESHOT',
        selected={r:digest(v) for r,v in selected.items()},timestamp=datetime.now(timezone.utc).isoformat())
    # Exclusive marker is durable BEFORE opening any target. Failed runs stay consumed.
    with (run_root/'PROTECTED_ACCESS_CONSUMED.json').open('xb') as f:f.write(canonical(receipt))
    return selected,open_sources()

def protected_records():
    meta=read(HERE/'protected_population.json')
    records=[]
    for name,sha in meta['target_source_hashes'].items():
        records.extend(checked(ROOT/name,sha))
    by={r['example_id']:r for r in records}
    result=[by[r['example_id']] for r in meta['metadata']]
    require(len(result)==114 and all(r['split']!='train' for r in result),'Protected population boundary')
    for row,m in zip(result,meta['metadata']):
        require(row['split']==m['split'] and row['role']==m['role'],'Protected metadata binding')
    return result

def execute(permit_path):
    frozen();authorization(permit_path,'protected_evaluation');torch=runtime()
    for name,sha in read(HERE/'experiment.json')['protected_component_hashes'].items():
        require(digest((ROOT/name).read_bytes())==sha,'Protected evaluator component changed')
    root=ROOT/'runs'/EXPERIMENT
    selected,records=claim_access(root,protected_records)
    from transformers import AutoModelForCausalLM
    from peft import PeftModel
    _,_,_,core=dependencies()
    import gc,time
    scores={'base':[],'tuned':[]}
    for role in PINS:
        spec=read(HERE/role/'experiment.json');tok=tokenizer(role)
        base=AutoModelForCausalLM.from_pretrained(PINS[role][0],revision=PINS[role][1],local_files_only=True,
             trust_remote_code=False,device_map={'':0},torch_dtype=torch.bfloat16,attn_implementation='eager')
        chosen=selected[role]['selected'];adapter=root/role/('checkpoint-'+str(chosen['step']))
        model=PeftModel.from_pretrained(base,adapter,is_trainable=False);model.eval()
        generator=LocalGenerator(model,tok,spec)
        for variant,ctx in paired_variants(model):
            with ctx:
                for record in [r for r in records if r['role']==role]:
                    # Render the protected input with the SAME role policy/template.
                    packet=dict(role=role,production_contract='semantic-task-v1',
                        source_spans=[dict(alias=core.ex.wire_id(s),text=s.text) for s in core.owned(record)],
                        context_only_spans=[dict(alias=core.ex.wire_id(s),text=s.text) for s in core.ex.ledger(record['source_text'],record['example_id'],record['ledger_max_chars']) if core.ex.wire_id(s) in record['context_only_aliases']],
                        supplied_refs=record['supplied_refs'],required_refs=record['required_refs'],routed_rules=record['routed_rules'])
                    if role=='auditor':packet['extraction']=record['extraction_text']
                    prompt=tok.apply_chat_template(messages(dict(role=role,input=packet)),tokenize=False,add_generation_prompt=True)
                    output=generator(prompt);metric=core.evaluate(record,output['raw_output'],truncated=output['truncated'])
                    try:parsed=core.strict_json(output['raw_output'])
                    except ValueError:parsed=None
                    scores[variant].append(dict(example_id=record['example_id'],prompt=prompt,**output,parsed=parsed,
                        metrics=metric,generation_settings=spec['generation'],
                        identity=chosen['identity'] if variant=='tuned' else dict(role=role,base_model=PINS[role][0],revision=PINS[role][1],adapter=None)))
                    write(root/('protected-'+variant+'.json'),scores[variant])
        del generator,model,base;gc.collect();torch.cuda.empty_cache()
    # Existing 27 criteria and R06 are evaluated separately; human coverage stays 0.
    sys.path.insert(0,str(ROOT/'benchmark/first_tuning_experiment_v1'))
    import registration
    sys.path.insert(0,str(ROOT/'benchmark/machine_adjudication_v1'))
    import r06
    acceptance=checked(ROOT/'benchmark/first_tuning_experiment_v1/acceptance_registration.json',read(HERE/'experiment.json')['acceptance_sha256'])
    meta=read(HERE/'protected_population.json')['metadata']
    for variant,outputs in scores.items():
        measures,cats=registration.performance_metrics([r['metrics'] for r in outputs])
        family=r06.evaluate_registered([r['metrics'] for r in outputs],meta,[r['example_id'] for r in meta],acceptance)
        measures.update(R01=0.,R02=0.,R03=0.,R04=0.,R05=0.,R06=family['measured'])
        cats['governance_violations']=0
        criteria={c['id']:dict(measured=measures[c['id']],passed=None if measures[c['id']] is None else (measures[c['id']]==c['value'] if c['operator']=='==' else measures[c['id']]>=c['value'])) for c in acceptance['criteria']}
        breakdown={}
        by_id={r['example_id']:r for r in records}
        for field in ('domain','template_family','document_family','role'):
            groups={}
            for output in outputs:
                key=by_id[output['example_id']][field]
                groups.setdefault(key,[]).append(output['metrics'])
            breakdown[field]={k:dict(count=len(v),accepted=sum(s['accepted_outcome'] for s in v),
                contract_valid=sum(s['contract_valid'] for s in v),truncated=sum(s['truncated'] for s in v)) for k,v in groups.items()}
        write(root/('protected-'+variant+'-acceptance.json'),dict(criteria=criteria,R06=family,breakdown=breakdown,
            R07=dict(counts=cats,passed=all(cats.get(k,0)==0 for k in acceptance['catastrophic_limits'])),
            human_review_status='PENDING',human_reviews=0,final_model_acceptance=False,
            scope='development-inclusive; historical authored target diagnostics; no curation feedback'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--authorization',required=True);a=p.parse_args();execute(a.authorization)
