"""Frozen final Auditor contracts; pure functions, no model or provider calls."""
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path
import auditor_classifier_lora_core as c

PARAMS=dict(lora_peak_lr=1.2943234833221302e-6,head_lr=.0009721418411547451,warmup_steps=10,dropout=.05)
FORBIDDEN=('holdout','protected_final_test','producer','full_shimmer_inputs')
EVAL_HASHES={'records.json':'6ef0f387119fca3f5c9bfd7cd4b7986bddc125cfe46ac01c86763e073cba20e2','challenges.json':'fc34f439fb1bf57ec2247f5f6d2624b7438f419b8a3e09583a72e9eb3640e52d'}


def require(ok,message):
    if not ok:raise RuntimeError(message)


def config():
    return dict(params=PARAMS,updates=896,checkpoints=[448,896],evaluation_after_updates=896,seed=7,microbatch=1,accumulation=4,
        head_updates=200,normalization_rows=1792,head_fit_rows=1792,fresh_live_feature_passes=1,
        optimizer=dict(name='AdamW',betas=[.9,.999],eps=1e-8,weight_decay=0,max_grad_norm=1.,regularization=.001),
        selection='prefer_all_old_gates_pass_then_historical_f1_external_f1_min_recall_lower_step',
        quality_failure_stops_training=False,soft_budget_usd=5.,hard_budget_usd=7.,instances=1,gpus=1)


def lr(step):
    require(1<=step<=896,'optimizer update range')
    return PARAMS['lora_peak_lr']*min(1.,step/10)


def train_rows(rows):
    require(len(rows)==1792 and len({r['example_id'] for r in rows})==1792,'TRAIN population')
    require(Counter(r['relation'] for r in rows)==dict.fromkeys(c.CLASSES,448),'TRAIN balance')
    for r in rows:
        require(set(r)=={'example_id','relation','input_ids','prompt_sha256','split'} and r['split']=='train','TRAIN-only record')
        require(0<len(r['input_ids'])<=1056 and all(type(v)==int and 0<=v<32064 for v in r['input_ids']),'token contract')
    return rows


class Boundary:
    def __init__(self,root,evaluation=False):
        self.root=Path(root).resolve();self.evaluation=evaluation
        self.receipt=dict(successful_access_counts=dict.fromkeys(FORBIDDEN,0),denied_before_open=0,
            external_dev_rows=0,historical_dev_rows=0,shorter_rows=0,longer_rows=0,evaluation_opened_after_updates=None)

    def forbidden(self,path):
        v=str(path).lower().replace('\\','/')
        return any(x in v for x in ('holdout','protected','producer','/benchmark/','/input/','/full_shimmer/','/governance/'))

    def check(self,path):
        p=Path(path).resolve()
        if self.forbidden(p) or (not self.evaluation and ('evaluation_payload' in str(p) or p.name=='challenges.json' or '/auditor_classifier_lora/records.json' in p.as_posix())):
            self.receipt['denied_before_open']+=1
            raise PermissionError('Final Auditor data boundary before open')

    def install(self):
        def hook(event,args):
            if event in ('socket.connect','socket.getaddrinfo'):raise PermissionError('offline final Auditor')
            if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):self.check(os.fsdecode(args[0]))
        sys.addaudithook(hook)


def admit_evaluation(completion):
    require(completion.get('complete') is True and completion.get('updates')==896 and completion.get('checkpoints')==[448,896],'evaluation denied before full896 completion')


def validate_evaluation(rows,challenges,train):
    require(len(rows)==2040 and rows[:1792]==train,'original TRAIN/DEV binding')
    require(len({r['example_id'] for r in rows})==2040,'disjoint original IDs')
    require([r['split'] for r in rows]==['train']*1792+['external_dev']*200+['historical_dev']*48,'DEV populations')
    for part,n in [(rows[1792:1992],50),(rows[1992:],12)]:require(Counter(r['relation'] for r in part)==dict.fromkeys(c.CLASSES,n),'DEV balance')
    ext={r['example_id']:r for r in rows[1792:1992]}
    require(set(challenges)=={'shorter','longer'},'challenge names')
    for key,classes in [('shorter',c.CLASSES[:3]),('longer',[c.CLASSES[0],c.CLASSES[1],c.CLASSES[3]])]:
        ch=challenges[key];ids=ch['example_ids']
        require(ch['classes']==classes and len(ids)==len(set(ids))==75 and set(ids)<=set(ext),'challenge frozen subset')
        require(Counter(ext[i]['relation'] for i in ids)==dict.fromkeys(classes,25),'challenge balance')
    require(set(challenges['shorter']['example_ids']).isdisjoint(challenges['longer']['example_ids']),'challenge overlap')


def score(rows,predictions,classes=None):
    classes=c.CLASSES if classes is None else classes
    by={p['example_id']:p for p in predictions}
    expected=[r['relation'] for r in rows];pred=[by[r['example_id']]['predicted'] for r in rows]
    m=c.metrics(expected,pred,classes)
    m.update(per_class_recall={k:v['recall'] for k,v in m['per_class'].items()},minimum_class_recall=min(v['recall'] for v in m['per_class'].values()),
        confusion_matrix=[[m['confusion'][a][b] for b in c.CLASSES] for a in classes],classes=classes,prediction_classes=c.CLASSES,
        mean_ce=sum(by[r['example_id']]['ce'] for r in rows)/len(rows),classifier_contract_validity=1.,substantive_non_refusal_coverage=1.,
        refusal_precision=None,refusal_recall=None,contract_validity=None,evidence_precision=None,evidence_recall=None,evidence_f1=None,
        accepted_semantic_outcomes=None,refusal_and_explanation_metrics_applicability='not applicable: four-way substantive classifier; no refusal/explanation/CONFIDENT field',
        catastrophic=dict(nonfinite_logits=0,invalid_class=0,invented_evidence=None,confident_wrong_match_divergence=None,truncation=None,producer_source_copy=None,governance_violations=None),
        classification_error_counts=dict(total=sum(a!=b for a,b in zip(expected,pred)),false_match=sum(a!='MATCH' and b=='MATCH' for a,b in zip(expected,pred)),wrong_match_or_divergence=sum(a!=b and b in ('MATCH','DIVERGENCE') for a,b in zip(expected,pred))))
    return m


def evaluate(rows,predictions,challenges):
    require(len(predictions)==248 and {p['example_id'] for p in predictions}=={r['example_id'] for r in rows[1792:]},'248 evaluation predictions')
    for p in predictions:
        require(len(p['logits'])==4 and all(math.isfinite(v) for v in p['logits']) and math.isfinite(p['ce']),'finite evaluation')
        require(p['predicted']==c.CLASSES[max(range(4),key=lambda i:p['logits'][i])],'argmax contract')
    result=dict(external=score(rows[1792:1992],predictions),historical=score(rows[1992:],predictions))
    by={r['example_id']:r for r in rows}
    for key,ch in challenges.items():result[key]=score([by[i] for i in ch['example_ids']],predictions,ch['classes'])
    result['old_quality_gates']=dict(external=result['external']['macro_f1']>=.75 and result['external']['minimum_class_recall']>=.60,
        historical=result['historical']['macro_f1']>=.70 and result['historical']['minimum_class_recall']>=.60,
        shorter=result['shorter']['macro_f1']>=.70,longer=result['longer']['macro_f1']>=.70)
    result['all_old_quality_gates_pass']=all(result['old_quality_gates'].values())
    return result


def select(results):
    require(sorted(r['step'] for r in results)==[448,896],'both planned candidates required')
    def key(r):
        m=r['metrics'];minimum=min(m[k]['minimum_class_recall'] for k in ['external','historical'])
        return (not m['all_old_quality_gates_pass'],-m['historical']['macro_f1'],-m['external']['macro_f1'],-minimum,r['step'])
    winner=min(results,key=key)
    return dict(verdict='AUDITOR_FINAL_WORKFLOW_COMPLETE',selected_step=winner['step'],selected_identity=winner['identity'],
        all_old_quality_gates_pass=winner['metrics']['all_old_quality_gates_pass'],
        reason='Finite complete candidate; prefer all old gates passing, then historical macro F1, external macro F1, minimum co-primary recall, lower step.',
        final_test_consumed=False,further_tuning_authorized=False)
