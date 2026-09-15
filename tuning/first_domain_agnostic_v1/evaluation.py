"""DEV-only selection and bound BASE/adapter output evidence. No API backend."""
from datetime import datetime, timezone
from pathlib import Path
import time
from common import *

def score(row, raw, truncated=False):
    _,_,_,core=dependencies()
    result=core.evaluate(scoring_record(row),raw,truncated=truncated)
    if result.get('reason_basis')=='canonical_authored_rubric':
        result['reason_basis']='exact_frozen_machine_curated_rationale'
    # Arbitrary alternative rationale remains unassessed; no fuzzy truth inference.
    return result

def f1(value):
    den=2*value['tp']+value['fp']+value['fn']
    return 2*value['tp']/den if den else 1.

def selection_metrics(role, scores):
    require(scores and all(s['role']==role and s['split']=='dev' for s in scores),'DEV-only selection')
    catastrophic={
        'invented_evidence':sum(s['catastrophic']['invented_evidence'] for s in scores),
        'unrouted_rule_attribution':sum(s['catastrophic']['invented_rule'] for s in scores),
        'confident_wrong_match_divergence':sum(s['catastrophic']['incorrect_confident_judgment'] for s in scores),
        'truncation':sum(s['truncated'] for s in scores),
        'producer_source_copy':sum(s.get('copied_source_violation',False) for s in scores),
        'governance_violations':0,
    }
    semantic=[]
    for s in scores:
        if role=='producer':
            semantic.append(sum([f1(s[k]) for k in ('claims','information_gaps','uncertainty','evidence')]+[float(s['semantic_completeness'])])/5)
        else:
            relation=s['refusal_correct'] if s['expected_refusal'] else s['relation_correct']
            reason=s['refusal_correct'] if s['expected_refusal'] else s.get('reason_correct') is True
            semantic.append((float(relation)+f1(s['evidence'])+float(s['refusal_correct'])+float(reason))/4)
    return dict(catastrophic=catastrophic,catastrophic_pass=not any(catastrophic.values()),
        contract_rate=sum(s['contract_valid'] for s in scores)/len(scores),
        semantic_score=sum(semantic)/len(semantic),
        unassessed_reasons=sum(not s['expected_refusal'] and s.get('reason_correct') is None for s in scores if role=='auditor'))

class LocalGenerator:
    """Already-loaded local model only. Never dispatches to provider SDKs."""
    def __init__(self,model,tok,spec):
        self.model,self.tok,self.spec=model,tok,spec
    def __call__(self,prompt):
        import torch
        inputs=self.tok(prompt,add_special_tokens=False,return_tensors='pt').to(self.model.device)
        torch.cuda.synchronize();start=time.perf_counter()
        with torch.inference_mode():
            output=self.model.generate(**inputs,**self.spec['generation'],
                eos_token_id=self.spec['terminal_token_ids'],pad_token_id=self.tok.pad_token_id)
        torch.cuda.synchronize();wall=time.perf_counter()-start
        ids=output[0,inputs['input_ids'].shape[1]:].tolist()
        terminal=bool(ids and ids[-1] in self.spec['terminal_token_ids'])
        return dict(raw_output=self.tok.decode(ids,skip_special_tokens=True),
            raw_output_with_special_tokens=self.tok.decode(ids,skip_special_tokens=False),output_token_ids=ids,
            input_tokens=inputs['input_ids'].shape[1],output_tokens=len(ids),latency_seconds=wall,
            stop_reason='eos' if terminal else 'length',truncated=not terminal,
            ttft_seconds=None,ttft_unavailable_reason='nonstreaming fixed local evaluator')

def evaluate_rows(rows,tok,spec,generate,identity,destination):
    require(identity['role']==spec['role'],'Evaluation role mismatch')
    results=[]
    for row in rows:
        require(row['role']==spec['role'],'Mixed evaluation roles')
        prompt=tok.apply_chat_template(messages(row),tokenize=False,add_generation_prompt=True)
        output=generate(prompt)
        metrics=score(row,output['raw_output'],output['truncated'])
        try: parsed=dependencies()[3].strict_json(output['raw_output'])
        except (ValueError,TypeError):parsed=None
        results.append(dict(example_id=row['example_id'],role=row['role'],split=row['split'],
            prompt=prompt,prompt_sha256=digest(prompt.encode()),**output,parsed=parsed,
            contract_result=metrics['contract_valid'],semantic_metrics=metrics,evidence_metrics=metrics['evidence'],
            identity=identity,generation_settings=spec['generation']))
    write(destination,results)
    return results

def evaluate_dev(role,tok,spec,generate,identity,destination):
    rows=load_rows(role,'dev')
    evidence=evaluate_rows(rows,tok,spec,generate,identity,destination)
    return dict(identity=identity,role=role,step=identity['step'],
        dev_ids=[r['example_id'] for r in rows],dataset_sha256=spec['dataset_sha256'],
        evidence_sha256=digest(Path(destination).read_bytes()),evidence_file=Path(destination).name,
        metrics=selection_metrics(role,[r['semantic_metrics'] for r in evidence]))

def select(role,results,spec):
    require(len(results)==len(spec['checkpoint_steps']),'Missing checkpoint evaluations')
    require(sorted(r['step'] for r in results)==spec['checkpoint_steps'],'Unexpected checkpoint schedule')
    expected=[r['example_id'] for r in load_rows(role,'dev')]
    for r in results:
        require(r['role']==role and r['identity']['role']==role and r['dev_ids']==expected and r['dataset_sha256']==spec['dataset_sha256'], 'Unbound DEV selection')
    admitted=[r for r in results if r['metrics']['catastrophic_pass'] and r['metrics']['contract_rate']==1.]
    require(admitted,'No checkpoint passes catastrophic and contract gates')
    return sorted(admitted,key=lambda r:(-r['metrics']['semantic_score'],r['step'],r['identity']['sha256']))[0]

def freeze_selection(role,run_dir,results,spec):
    run_dir=Path(run_dir)
    require(not (run_dir.parent/'PROTECTED_ACCESS_CONSUMED.json').exists(),'Selection closed after protected access')
    chosen=select(role,results,spec)
    adapter=run_dir/('checkpoint-'+str(chosen['step']))
    verify_adapter(adapter,chosen['identity'],role)
    evidence=run_dir/chosen['evidence_file']
    require(digest(evidence.read_bytes())==chosen['evidence_sha256'],'DEV evidence changed')
    value=dict(experiment=EXPERIMENT,role=role,selected=chosen,
        all_checkpoint_results=results,experiment_freeze_sha256=digest((HERE/'freeze.json').read_bytes()),
        selected_at=datetime.now(timezone.utc).isoformat(),protected_accesses_before_selection=0,
        selection_scope='DEV only; not model acceptance')
    path=run_dir/'SELECTION_FREEZE.json'
    with path.open('xb') as f:f.write(canonical(value))
    return value

def verify_selection(role,run_dir):
    run_dir=Path(run_dir);value=read(run_dir/'SELECTION_FREEZE.json')
    require(value['experiment']==EXPERIMENT and value['role']==role,'Selection role binding')
    require(value['experiment_freeze_sha256']==digest((HERE/'freeze.json').read_bytes()),'Selection experiment binding')
    spec=read(HERE/role/'experiment.json')
    chosen=select(role,value['all_checkpoint_results'],spec)
    require(chosen==value['selected'],'Selection was not deterministic DEV winner')
    for result in value['all_checkpoint_results']:
        evidence=checked(run_dir/result['evidence_file'],result['evidence_sha256'])
        require([r['example_id'] for r in evidence]==result['dev_ids'],'DEV evidence population')
        require(all(r['identity']==result['identity'] for r in evidence),'DEV adapter binding')
        rescored=[score(row,item['raw_output'],item['truncated']) for row,item in zip(load_rows(role,'dev'),evidence)]
        require(selection_metrics(role,rescored)==result['metrics'],'Fabricated selection metrics')
        verify_adapter(run_dir/('checkpoint-'+str(result['step'])),result['identity'],role)
    return value

def paired_variants(model):
    """Same loaded base, tokenizer, prompt and settings; adapter toggling only."""
    from contextlib import nullcontext
    return [('base',model.disable_adapter()),('tuned',nullcontext())]
