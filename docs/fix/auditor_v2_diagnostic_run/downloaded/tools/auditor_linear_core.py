"""Pure linear-probe contracts, shared by local tests, remote run and analysis."""
import copy
import hashlib
import json
import math
import re
from collections import Counter

CLASSES = ['MATCH', 'DIVERGENCE', 'OMISSION', 'ADDITION', 'INSUFFICIENT_EVIDENCE']
INPUT_KEYS = {'context_only_spans', 'delivery_complete', 'extraction', 'production_contract', 'required_refs', 'role', 'routed_rules', 'source_spans', 'supplied_refs'}
REF = re.compile(r'(?<![A-Za-z0-9_-])REF-\d+(?![A-Za-z0-9_-])')
REFUSAL = '{"items":[],"status":"refused"}'
OPEN = '{"items":[{'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def normalized_input(value):
    assert set(value) == INPUT_KEYS and value['role'] == 'auditor', 'Unreviewed classifier input field'
    mapping = {}
    texts = [s['text'] for s in value['source_spans']] + [value['extraction']] + [s['text'] for s in value['context_only_spans']] + value['required_refs'] + value['supplied_refs']
    for text in texts:
        for match in REF.finditer(text):
            old = match.group()
            if old not in mapping:
                mapping[old] = f'REF-{len(mapping)+1:04d}'
    def replace(obj):
        if isinstance(obj, str):
            return REF.sub(lambda m: mapping[m.group()], obj)
        if isinstance(obj, list):
            return [replace(x) for x in obj]
        if isinstance(obj, dict):
            return {k: replace(v) for k, v in obj.items()}
        return obj
    result = replace(copy.deepcopy(value))
    assert len(mapping) == len(set(mapping.values()))
    return result, mapping


def probe_state(text, terminal=False):
    if terminal:
        if text == REFUSAL:
            return 'refusal'
        raise ValueError('Unexpected terminal refusal prefix')
    if text.startswith(OPEN):
        return 'nonempty'
    if REFUSAL.startswith(text) or OPEN.startswith(text):
        return 'waiting'
    raise ValueError('Unexpected canonical prefix')


def parse_reason(text):
    """Return exact first completed JSON string and same-token spill, never repair."""
    escaped = False
    for index, char in enumerate(text):
        if ord(char) < 32:
            return dict(state='malformed')
        if char == '"' and not escaped:
            try:
                value = json.loads('"' + text[:index+1])
                value.encode('utf8')
            except (ValueError, UnicodeError):
                return dict(state='malformed')
            return dict(state='complete', reason=value, escaped_reason=text[:index], spill=text[index+1:])
        escaped = not escaped if char == '\\' else False
    return dict(state='waiting')


def forced_prefix(relation):
    assert relation in CLASSES[:4]
    return '{"items":[{"confidence":"CONFIDENT","finding":' + json.dumps(relation) + ',"reasoning":"'


def assemble(value, relation, reason):
    refs = value['required_refs']
    assert len(refs) == len(set(refs)) and set(refs) <= set(value['supplied_refs']), 'Invalid required refs'
    assert all(REF.fullmatch(x) for x in refs), 'Invalid reference identifier'
    assert relation in CLASSES[:4] and isinstance(reason, str)
    return canonical(dict(items=[dict(confidence='CONFIDENT', finding=relation, reasoning=reason, ref_ids=refs, severity='low' if relation == 'MATCH' else 'medium')]))


def route(branch, predicted):
    assert branch in ('refusal', 'nonempty') and predicted in CLASSES
    return 'INSUFFICIENT_EVIDENCE' if branch == 'refusal' else predicted


def classification(expected, predicted):
    assert len(expected) == len(predicted) and len(expected) > 0
    assert set(expected + predicted) <= set(CLASSES)
    matrix = {c: {p: sum(a == c and b == p for a, b in zip(expected, predicted)) for p in CLASSES} for c in CLASSES}
    per = {}
    for c in CLASSES:
        tp = matrix[c][c]; support = expected.count(c); count = predicted.count(c)
        precision = tp/count if count else 0.; recall = tp/support if support else 0.
        per[c] = dict(precision=precision, recall=recall, f1=2*tp/(support+count) if support+count else 0., support=support, predicted=count)
    return dict(count=len(expected), confusion=matrix, per_class=per, accuracy=sum(a == b for a, b in zip(expected, predicted))/len(expected),
                **{'macro_'+k: sum(v[k] for v in per.values())/5 for k in ('precision','recall','f1')})


def nonregression(metrics):
    wanted = dict(evidence_f1=1., refusal_precision=1., refusal_recall=1., over_refusal_rate=0., substantive_non_refusal_coverage=1.)
    return {k: metrics.get(k) == v for k, v in wanted.items()}


def standardized(np, features, train_indices):
    assert features.shape == (300,3072) and len(train_indices) == len(set(train_indices)) == 240
    train = features[train_indices]
    mean = np.mean(train, axis=0, dtype=np.float32)
    std = np.maximum(np.std(train, axis=0, ddof=0, dtype=np.float32), np.float32(1e-6))
    transformed = (features-mean)/std
    assert np.isfinite(transformed).all()
    return mean, std, transformed


def objective(torch, head, features, labels):
    ce = torch.nn.functional.cross_entropy(head(features), labels)
    regularization = .001*head.weight.square().mean()
    return ce, regularization


def train_head(torch, features, labels, callback):
    assert features.shape == (240,3072) and labels.shape == (240,)
    assert features.dtype == torch.float32 and sorted(labels.bincount(minlength=5).tolist()) == [48]*5
    torch.manual_seed(7)
    head = torch.nn.Linear(3072,5,device=features.device,dtype=torch.float32)
    with torch.no_grad():
        head.weight.zero_(); head.bias.zero_()
    assert sum(p.numel() for p in head.parameters()) == 15365
    opt = torch.optim.Adam(head.parameters(),lr=.01,betas=(.9,.999),eps=1e-8,weight_decay=0)
    callback(0,head,None,None)
    for step in range(1,201):
        opt.zero_grad(set_to_none=True)
        ce, reg = objective(torch,head,features,labels)
        assert bool(torch.isfinite(ce+reg).item())
        (ce+reg).backward();opt.step()
        callback(step,head,float(ce.detach()),float(reg.detach()))
    return head


def final_feature(torch, model, input_ids):
    assert not model.training and all(not p.requires_grad for p in model.parameters())
    with torch.inference_mode():
        ids = torch.tensor([input_ids],dtype=torch.long,device=model.device)
        result = model.get_base_model().model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,output_hidden_states=False,return_dict=True)
        value = result.last_hidden_state[0,-1].detach().float().cpu().numpy().copy()
    assert value.shape == (3072,)
    return value


def remaining_seconds(features_left, outputs_left, feature_seconds=1., generated_rate=7.):
    assert all(math.isfinite(x) and x >= 0 for x in [features_left,outputs_left,feature_seconds]) and generated_rate > 0
    # Full cap plus prefix veto: conservative model-token upper bound per output.
    return features_left*max(1.,feature_seconds) + outputs_left*208/min(7.,generated_rate) + 90
