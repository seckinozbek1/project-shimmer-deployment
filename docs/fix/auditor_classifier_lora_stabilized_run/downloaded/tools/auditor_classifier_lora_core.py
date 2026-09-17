"""Pure contracts: one fresh classifier LoRA, two TRAIN passes, fixed gates."""
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

CLASSES=['MATCH','DIVERGENCE','OMISSION','ADDITION']
TARGETS=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']
LORA_PARAMS=14942208
HEAD_PARAMS=12292


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def schedule(ids):
    assert len(ids)==len(set(ids))==1792
    rng=random.Random(7);result=[]
    for epoch in (1,2):
        order=list(ids);rng.shuffle(order)
        for start in range(0,len(order),4):
            result.append(dict(step=len(result)+1,epoch=epoch,example_ids=order[start:start+4]))
    assert len(result)==896
    return result


def validate(records,spec,challenges,plan):
    assert len(records)==2040 and len({r['example_id'] for r in records})==2040
    assert [r['split'] for r in records]==['train']*1792+['external_dev']*200+['historical_dev']*48
    for rows,n in [(records[:1792],448),(records[1792:1992],50),(records[1992:],12)]:
        assert Counter(r['relation'] for r in rows)=={c:n for c in CLASSES}
    for r in records:
        assert set(r)=={'example_id','split','relation','input_ids','prompt_sha256'}
        assert 0<len(r['input_ids'])<=1056 and all(type(i) is int and 0<=i<32064 for i in r['input_ids'])
    assert spec['lora']==dict(r=8,lora_alpha=16,lora_dropout=.05,bias='none',task_type='CAUSAL_LM',target_modules=TARGETS,init_lora_weights=True)
    assert spec['head']==dict(input_dim=3072,outputs=4,parameters=HEAD_PARAMS,initialization='zero',dtype='float32')
    assert spec['optimizer']==dict(name='AdamW',lora_lr=1e-4,head_lr=1e-2,betas=[.9,.999],eps=1e-8,weight_decay=0,max_grad_norm=1,scheduler=None,regularization=.001)
    assert spec['training']==dict(seed=7,passes=2,microbatch=1,accumulation=4,effective_batch=4,updates=896,checkpoints=[448,896])
    assert spec['normalization']=='none' and not spec['historical_adapter_loaded']
    assert spec['model_id']=='unsloth/Phi-3.5-mini-instruct-bnb-4bit' and spec['revision']=='5c20803aa197416f43fb455e55c85178775320cb'
    assert plan==schedule([r['example_id'] for r in records[:1792]])
    ext={r['example_id']:r for r in records[1792:1992]}
    for key,classes in [('shorter',CLASSES[:3]),('longer',[CLASSES[0],CLASSES[1],CLASSES[3]])]:
        ch=challenges[key];assert ch['classes']==classes
        assert len(ch['example_ids'])==len(set(ch['example_ids']))==75 and set(ch['example_ids'])<=set(ext)
        assert Counter(ext[i]['relation'] for i in ch['example_ids'])=={c:25 for c in classes}
    assert set(challenges['shorter']['example_ids']).isdisjoint(challenges['longer']['example_ids'])


def inventory(items):
    """Validate parameter metadata before an optimizer can be constructed."""
    lora=[];head=[]
    for x in items:
        if not x['trainable']:continue
        name=x['name']
        if name in ('head.weight','head.bias'):head.append(x)
        else:
            assert '.lora_A.default.weight' in name or '.lora_B.default.weight' in name,name
            assert any('.'+target+'.lora_' in name for target in TARGETS),name
            assert x['dtype']=='torch.float32'
            lora.append(x)
    assert len(lora)==448 and sum(x['numel'] for x in lora)==LORA_PARAMS
    assert {x['name']:x['shape'] for x in head}=={'head.weight':[4,3072],'head.bias':[4]}
    assert sum(x['numel'] for x in head)==HEAD_PARAMS and all(x['dtype']=='torch.float32' for x in head)
    return dict(base_trainable=0,classifier_lora_trainable=LORA_PARAMS,head_trainable=HEAD_PARAMS,total=LORA_PARAMS+HEAD_PARAMS)


def metrics(expected,predicted,classes=None):
    classes=CLASSES if classes is None else classes
    assert expected and len(expected)==len(predicted) and set(expected)<=set(classes) and set(predicted)<=set(CLASSES)
    per={}
    for c in classes:
        tp=sum(a==b==c for a,b in zip(expected,predicted));support=expected.count(c);count=predicted.count(c)
        per[c]=dict(support=support,predicted=count,precision=tp/count if count else 0.,recall=tp/support if support else 0.,f1=2*tp/(support+count) if support+count else 0.)
    return dict(count=len(expected),accuracy=sum(a==b for a,b in zip(expected,predicted))/len(expected),per_class=per,
        **{'macro_'+k:sum(v[k] for v in per.values())/len(per) for k in ['precision','recall','f1']},
        confusion={a:{b:sum(x==a and y==b for x,y in zip(expected,predicted)) for b in CLASSES} for a in classes})


def evaluate(records,predictions,challenges):
    assert set(predictions)=={r['example_id'] for r in records[1792:]}
    by={r['example_id']:r for r in records}
    def score(ids,classes=None):return metrics([by[i]['relation'] for i in ids],[predictions[i] for i in ids],classes)
    ext=score([r['example_id'] for r in records[1792:1992]])
    hist=score([r['example_id'] for r in records[1992:]])
    ch={k:score(v['example_ids'],v['classes']) for k,v in challenges.items()}
    def gate(m,f,rec):return m['macro_f1']>=f and all(x['recall']>=rec for x in m['per_class'].values())
    gates=dict(external=gate(ext,.75,.60),historical=gate(hist,.70,.60),shorter=ch['shorter']['macro_f1']>=.70,longer=ch['longer']['macro_f1']>=.70)
    return dict(external=ext,historical=hist,challenges=ch,gates=gates,passed=all(gates.values()),
                aspirational=dict(external=gate(ext,.80,.70),historical=hist['macro_f1']>=.75))


def select(checkpoints,updates):
    if updates!=896 or sorted(x['step'] for x in checkpoints)!=[448,896] or not all(x['complete'] for x in checkpoints):
        return dict(verdict='AUDITOR_CLASSIFIER_LORA_INDETERMINATE',diagnostic='RELATION_ADAPTATION_INDETERMINATE',selected=None,passing=[])
    eligible=[x for x in checkpoints if x['metrics']['passed']]
    def key(x):
        m=x['metrics'];minimum=min(v['recall'] for group in ['external','historical'] for v in m[group]['per_class'].values())
        return (-m['historical']['macro_f1'],-m['external']['macro_f1'],-minimum,x['step'],x['lora_sha256'],x['head_sha256'])
    selected=min(eligible,key=key) if eligible else None
    return dict(verdict='AUDITOR_CLASSIFIER_LORA_PASS' if selected else 'AUDITOR_CLASSIFIER_LORA_FAIL',
                diagnostic='RELATION_ADAPTATION_SUPPORTED' if selected else 'RELATION_ADAPTATION_FAILED',
                passing=[x['step'] for x in eligible],selected=None if selected is None else {k:selected[k] for k in ['step','lora_sha256','head_sha256']})


def remaining_seconds(updates,update_times,eval_rows_left):
    assert 0<=updates<=896 and 0<=eval_rows_left<=496
    rate=max(6.,sum(update_times[-32:])/len(update_times[-32:])*1.25) if update_times else 6.
    return (896-updates)*rate+eval_rows_left*.5+180
