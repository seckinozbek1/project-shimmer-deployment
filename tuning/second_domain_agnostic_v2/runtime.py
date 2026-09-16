"""Local V2 data/metric primitives. No model loader and no protected evaluator."""
import os
os.environ.update(USE_TORCH='0', USE_TF='0', USE_FLAX='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean, median, pstdev
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tuning/first_domain_agnostic_v1'))
import common as old
cc,ex,sem,core=old.dependencies()
CLASSES=('MATCH','DIVERGENCE','OMISSION','ADDITION','INSUFFICIENT_EVIDENCE')
GROUP_FIELDS=('document_family','template_family','derivation_group','paraphrase_family','renamed_family','leakage_group')


def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def sha(v): return hashlib.sha256(v if isinstance(v,bytes) else old.canonical(v)).hexdigest()
def require(v,message):
    if not v: raise ValueError(message)
def target(row): return row.get('canonical_target',row.get('semantic_target'))
def refused(obj): return obj==dict(items=[],status='refused')
def spans(row):
    return tuple(ex.Span(s['alias'],int(s['alias'][1:],16),int(s['alias'][1:],16)+len(s['text']),'',None,s['text']) for s in row['input']['source_spans'])
def contract(row,obj):
    if refused(obj): return True
    try:
        if row['role']=='producer': cc.producer(obj,spans(row),row['example_id'])
        else: cc.auditor(obj,row['example_id'],row['input']['required_refs'],row['input']['supplied_refs'])
        return True
    except (TypeError,ValueError,KeyError): return False


def encode(row,tok):
    messages=task_messages(row); answer=old.canonical(target(row)).decode()
    prefix=tok.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
    ids=tok.apply_chat_template(messages+[dict(role='assistant',content=answer)],tokenize=True,add_generation_prompt=False)
    require(ids[:len(prefix)]==prefix,'Prompt/target boundary mismatch')
    suffix=ids[len(prefix):]
    require(suffix.count(tok.eos_token_id)==1,'Native EOS mismatch')
    return dict(input_ids=ids,attention_mask=[1]*len(ids),labels=[-100]*len(prefix)+suffix,
                prompt_length=len(prefix),target_length=len(suffix))


def task_messages(row):
    messages=old.messages(row)
    if row['role']=='auditor':
        messages[0]['content'] += ('\nV2 transport clarification: delivery_complete=false means an interrupted extraction, requiring refusal. '
            'For a complete delivery, identifiable missing propositions are OMISSION, not transport incompleteness. '
            'Refuse when the owned original, referent, or comparison mapping is insufficient to determine a relation. '
            'A short extraction alone does not justify refusal. Structural readback/section headings do not introduce new speakers or facts.')
    return messages


def stats(rows):
    out={}
    for role in ('producer','auditor'):
        r=[x for x in rows if x['role']==role]
        out[role]=dict(rows=len(r),substantive=sum(x['substantive'] for x in r),
            document_families=len({x['document_family'] for x in r}),
            template_families=len({x['template_family'] for x in r}),
            derivation_families=len({x['derivation_group'] for x in r}),
            leakage_groups=len({x['leakage_group'] for x in r}),
            domains=dict(Counter(x['domain'] for x in r)),
            relations=dict(Counter(x.get('relation','REFUSAL' if refused(target(x)) else 'EMPTY' if not x['substantive'] else 'EXTRACTED') for x in r)),
            hard_negatives=sum(x['hard_negative'] for x in r),refusals=sum(refused(target(x)) for x in r),
            multi_span=sum(len(x['input']['source_spans'])>1 for x in r),
            evidence_complexity=dict(Counter(len(x['input']['required_refs']) for x in r)),
            reason_difficulty=dict(Counter(x.get('reason_difficulty','not_applicable') for x in r)))
        if role=='producer':
            labels=[x['typed_label'] for x in r]
            out[role].update(gap_bearing=sum(any(i['gap_atoms'] for i in x['items']) for x in labels),
                gap_atoms=sum(len(i['gap_atoms']) for x in labels for i in x['items']),
                uncertainty_bearing=sum(x['source_uncertainty_present'] for x in labels),
                uncertainty_atoms=sum(len(i['uncertainty_atoms']) for x in labels for i in x['items']),
                multi_claim=sum(sum(len(i['claims']) for i in x['items'])>1 for x in labels),
                gap_counts=dict(Counter(sum(len(i['gap_atoms']) for i in x['items']) for x in labels)),
                gap_attributes=dict(Counter(a['attribute'] for x in labels for i in x['items'] for a in i['gap_atoms'])))
    return out


def check_split(rows,manifest):
    by={r['example_id']:r for r in rows};train=manifest['train'];dev=manifest['validation']
    require(len(train)==len(set(train)) and len(dev)==len(set(dev)),'Duplicate membership')
    require(not set(train)&set(dev) and set(train)|set(dev)==set(by),'Population/overlap mismatch')
    a=[by[i] for i in train];b=[by[i] for i in dev]
    for field in GROUP_FIELDS:
        require(not {r[field] for r in a}&{r[field] for r in b},'Family crossing: '+field)
    for transform in (lambda r:sha(r['input']),lambda r:sha([s['text'] for s in r['input']['source_spans']])):
        require(not {transform(r) for r in a}&{transform(r) for r in b},'Exact duplicate crossing')
    for role in ('producer','auditor'):
        require(not {sha(r['semantic_signature']) for r in a if r['role']==role and r['substantive']}&
                    {sha(r['semantic_signature']) for r in b if r['role']==role and r['substantive']},'Semantic sibling crossing')
    for r in rows:
        for parent in r['parent_ids']:
            require(parent in by,'Unknown ancestry')
            require((r['example_id'] in train)==(parent in train),'Ancestry crossing')
    return dict(train=stats(a),validation=stats(b),validation_row_percent=100*len(b)/len(rows),
                validation_group_percent=100*len({r['leakage_group'] for r in b})/len({r['leakage_group'] for r in rows}))


def pr(pred,gold):
    p,g=set(pred),set(gold);tp=len(p&g)
    return dict(tp=tp,fp=len(p-g),fn=len(g-p))
def f1(c):
    d=2*c['tp']+c['fp']+c['fn'];return 2*c['tp']/d if d else 1.
def values(obj,key):
    return [(i.get('span','') if isinstance(i.get('span',''),str) else '<invalid>',v)
            for i in obj.get('items',[]) for v in (i.get(key,[]) if isinstance(i.get(key,[]),list) else []) if isinstance(v,str)]


def score(row,raw,truncated=False):
    try: obj=core.strict_json(raw)
    except (ValueError,TypeError): obj={}
    valid=not truncated and contract(row,obj)
    if not isinstance(obj,dict) or not isinstance(obj.get('items',[]),list) or any(not isinstance(i,dict) for i in obj.get('items',[])): obj={}
    gold=target(row);ref=refused(obj);expected=refused(gold)
    result=dict(example_id=row['example_id'],family=row['document_family'],leakage_group=row['leakage_group'],role=row['role'],
                contract_valid=valid,expected_refusal=expected,predicted_refusal=ref,refusal_correct=ref==expected)
    key='refs' if row['role']=='producer' else 'ref_ids'
    p=values(obj,key);g=values(gold,key)
    result['evidence']=pr(p,g)
    result['catastrophic']=dict(invented_evidence=bool({v for _,v in p}-set(row['input']['supplied_refs'])),
        invented_rule=bool(set(re.findall(r'CONV-[A-Za-z0-9-]+',raw))-set(row['input']['routed_rules'])),
        confident_wrong_match_divergence=False,truncation=bool(truncated),producer_source_copy=False,governance_violations=False)
    if row['role']=='producer':
        for key,name in [('claims','claims'),('questions','typed_gaps'),('uncertainty','typed_uncertainty')]: result[name]=pr(values(obj,key),values(gold,key))
        result['semantic_completeness']=valid and ref==expected and all(result[k]['fp']==result[k]['fn']==0 for k in ('claims','typed_gaps','typed_uncertainty','evidence'))
        texts=[s['text'] for s in row['input']['source_spans']]
        result['catastrophic']['producer_source_copy']=any(len(s)>80 and s in raw for s in texts)
        result['accepted_outcome']=result['semantic_completeness']
    else:
        predicted='INSUFFICIENT_EVIDENCE' if ref else obj.get('items',[{}])[0].get('finding','INVALID') if obj.get('items') else 'INVALID'
        result.update(expected_relation=row['relation'],predicted_relation=predicted,relation_correct=valid and predicted==row['relation'])
        result['catastrophic']['confident_wrong_match_divergence']=valid and predicted in ('MATCH','DIVERGENCE') and predicted!=row['relation'] and obj['items'][0].get('confidence')=='CONFIDENT'
        reason=None if ref else (obj.get('items',[{}])[0].get('reasoning') if obj.get('items') else None)
        expected_reason=None if expected else gold['items'][0]['reasoning']
        result['reason_correct']=True if expected and ref else True if reason==expected_reason and reason is not None else None
        result['accepted_outcome']=valid and result['relation_correct'] and result['evidence']['fp']==result['evidence']['fn']==0 and result['reason_correct'] is True
    return result


def aggregate(scores):
    require(scores,'Empty metric population');role=scores[0]['role'];require(all(s['role']==role for s in scores),'Mixed metric roles')
    n=len(scores);ratio=lambda a,b:a/b if b else None
    expected=sum(s['expected_refusal'] for s in scores);pred=sum(s['predicted_refusal'] for s in scores)
    correct=sum(s['expected_refusal'] and s['predicted_refusal'] for s in scores)
    result=dict(count=n,contract_validity=sum(s['contract_valid'] for s in scores)/n,
        accepted_semantic_outcomes=sum(s['accepted_outcome'] for s in scores)/n,
        refusal_precision=ratio(correct,pred),refusal_recall=ratio(correct,expected),
        over_refusal_rate=ratio(pred-correct,n-expected),substantive_non_refusal_coverage=ratio(sum(not s['expected_refusal'] and not s['predicted_refusal'] and s['contract_valid'] for s in scores),n-expected),
        catastrophic={k:sum(s['catastrophic'][k] for s in scores) for k in scores[0]['catastrophic']})
    for key in (('evidence','claims','typed_gaps','typed_uncertainty') if role=='producer' else ('evidence',)):
        result[key+'_f1']=f1({k:sum(s[key][k] for s in scores) for k in ('tp','fp','fn')})
    if role=='producer':result['semantic_completeness']=sum(s['semantic_completeness'] for s in scores)/n
    else:
        result['relation_accuracy']=sum(s['relation_correct'] for s in scores)/n
        result['per_class_recall']={c:ratio(sum(s['relation_correct'] and s['expected_relation']==c for s in scores),sum(s['expected_relation']==c for s in scores)) for c in CLASSES}
        result['macro_relation_f1']=mean(f1(dict(tp=sum(s['expected_relation']==c and s['predicted_relation']==c and s['contract_valid'] for s in scores),
            fp=sum(s['predicted_relation']==c and (s['expected_relation']!=c or not s['contract_valid']) for s in scores),
            fn=sum(s['expected_relation']==c and (s['predicted_relation']!=c or not s['contract_valid']) for s in scores))) for c in CLASSES)
    result['family_accepted_rates']={f:mean(s['accepted_outcome'] for s in scores if s['family']==f) for f in sorted({s['family'] for s in scores})}
    return result


def selection_pass(metrics,gate):
    if any(metrics['catastrophic'].values()):return False
    for name,minimum in gate['minimum'].items():
        value=metrics.get(name)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value<minimum:return False
    for name,maximum in gate['maximum'].items():
        value=metrics.get(name)
        if not isinstance(value,(int,float)) or not math.isfinite(value) or value>maximum:return False
    if 'per_class_recall' in gate:
        if any(not isinstance(metrics['per_class_recall'].get(c),(int,float)) or not math.isfinite(metrics['per_class_recall'][c]) or metrics['per_class_recall'][c]<v for c,v in gate['per_class_recall'].items()):return False
    return True


def cv_summary(folds):
    """Five complete folds required; report dispersion, never a selection score."""
    require(len(folds)==5,'All five folds required')
    def summarize(values):
        if any(x is None for x in values):return dict(values=values,mean=None,median=None,min=None,max=None,std=None)
        return dict(values=values,mean=mean(values),median=median(values),min=min(values),max=max(values),std=pstdev(values))
    result={}
    for key in folds[0]:
        if isinstance(folds[0][key],(int,float)) or folds[0][key] is None:result[key]=summarize([f[key] for f in folds])
        elif key in ('per_class_recall','catastrophic'):result[key]={c:summarize([f[key][c] for f in folds]) for c in folds[0][key]}
    result['family_level_variability']=summarize([v for f in folds for v in f['family_accepted_rates'].values()])
    result['interpretation']='Population SD across five frozen folds; document-level values are clustered by leakage group and are not independent replicates.'
    return result
