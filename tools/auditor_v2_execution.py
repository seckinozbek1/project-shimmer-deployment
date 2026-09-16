"""Strict execution contracts for the single authorized V2 diagnostic."""
import json
import hashlib
from collections import Counter
from pathlib import Path
import auditor_v2_diagnostic as d

CLASSES = d.CLASSES


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def metrics(expected, predicted, classes=None):
    result = d.metrics(expected, predicted, classes)
    for value in result['per_class'].values():
        # diagonal TP = recall * support (integer in exact arithmetic)
        tp = round(value['recall']*value['support'])
        value['precision'] = tp/value['predicted'] if value['predicted'] else 0.
    for key in ('precision', 'recall'):
        result['macro_'+key] = sum(v[key] for v in result['per_class'].values())/len(result['per_class'])
    return result


def evaluate(records, predictions, challenges, baseline):
    result = d.evaluate(records, predictions, challenges)
    by = {r['example_id']: r for r in records}
    def score(ids, classes=None):
        return metrics([by[i]['relation'] for i in ids], [predictions[i] for i in ids], classes)
    for key in ('external', 'historical'):
        result[key] = score([r['example_id'] for r in records if r['split'] == key+'_dev'])
    result['challenges'] = {k: score(v['example_ids'], v['classes']) for k, v in challenges.items()}
    result['baseline_macro_f1'] = baseline['macro_f1']
    result['historical_macro_f1_delta'] = result['historical']['macro_f1']-baseline['macro_f1']
    result['verdict'] = 'AUDITOR_V2_DIAGNOSTIC_PASS' if result['success'] else 'AUDITOR_V2_DIAGNOSTIC_FAIL'
    return result


def validate(records, spec, challenges, baseline):
    assert len(records) == 2040 and len({r['example_id'] for r in records}) == 2040
    assert [r['split'] for r in records] == ['train']*1792+['external_dev']*200+['historical_dev']*48
    for rows, n in [(records[:1792],448),(records[1792:1992],50),(records[1992:],12)]:
        assert Counter(r['relation'] for r in rows) == {c:n for c in CLASSES}
    for r in records:
        assert set(r) == {'example_id','split','relation','input_ids','prompt_sha256'}
        assert 0 < len(r['input_ids']) <= 1056 and all(type(i) is int and 0 <= i < 32064 for i in r['input_ids'])
    assert spec['head'] == dict(initialization='zero',learning_rate=.01,optimizer='Adam',outputs=4,parameters=12292,regularization=.001,seed=7,updates=200)
    assert spec['standardization'] == dict(clamp=1e-6,ddof=0,train_only=True)
    assert spec['model_id'] == 'unsloth/Phi-3.5-mini-instruct-bnb-4bit'
    assert spec['revision'] == '5c20803aa197416f43fb455e55c85178775320cb'
    assert spec['classes'] == CLASSES
    ext = {r['example_id']:r for r in records[1792:1992]}
    for name, classes in [('shorter',CLASSES[:3]),('longer',[CLASSES[0],CLASSES[1],CLASSES[3]])]:
        value = challenges[name]
        assert value['classes'] == classes
        assert len(value['example_ids']) == len(set(value['example_ids'])) == 75
        assert set(value['example_ids']) <= set(ext)
        assert Counter(ext[i]['relation'] for i in value['example_ids']) == {c:25 for c in classes}
    assert set(challenges['shorter']['example_ids']).isdisjoint(challenges['longer']['example_ids'])
    assert baseline['example_ids'] == [r['example_id'] for r in records[1992:]]
    assert abs(baseline['macro_f1']-.5991505914106533) < 1e-12


def train(torch, x, labels, callback):
    assert x.shape == (1792,3072) and x.dtype == torch.float32 and not x.requires_grad
    assert labels.shape == (1792,) and labels.bincount(minlength=4).tolist() == [448]*4
    torch.manual_seed(7)
    head = torch.nn.Linear(3072,4,device=x.device,dtype=torch.float32)
    with torch.no_grad():
        head.weight.zero_(); head.bias.zero_()
    assert sum(p.numel() for p in head.parameters()) == 12292
    opt = torch.optim.Adam(head.parameters(),lr=.01,betas=(.9,.999),eps=1e-8,weight_decay=0)
    callback(0,head,None,None)
    for step in range(1,201):
        opt.zero_grad(set_to_none=True)
        ce = torch.nn.functional.cross_entropy(head(x),labels)
        reg = .001*head.weight.square().mean()
        assert bool(torch.isfinite(ce+reg).item())
        (ce+reg).backward(); opt.step()
        callback(step,head,float(ce.detach()),float(reg.detach()))
    return head
