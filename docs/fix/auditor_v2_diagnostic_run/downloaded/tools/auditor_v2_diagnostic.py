"""One-off diagnostic preparation and four-way scoring. No cloud/model entry point."""
import hashlib
import json
import re
from pathlib import Path

import auditor_linear_core as core

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tuning/auditor_v2_diagnostic'
V2 = ROOT / 'tuning/auditor_external_relation_v2'
CLASSES = core.CLASSES[:4]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_bytes((json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n').encode())


def select_dev(stream, allowed):
    """Route opaque IDs before deserializing; excluded labels/text are never decoded.

    The frozen release interleaves all splits in one JSONL. Reading its transport
    envelopes is unavoidable; no excluded record is parsed, retained or evaluated.
    """
    result = {}
    pattern = re.compile(rb'"example_id":"([a-f0-9]{64})"')
    for line in stream:
        match = pattern.search(line)
        if not match:
            raise ValueError('Missing opaque routing ID')
        identifier = match[1].decode('ascii')
        if identifier not in allowed:
            continue
        row = json.loads(line)
        assert row['split'] == 'dev' and row['example_id'] == identifier
        assert identifier not in result
        result[identifier] = row
    assert set(result) == set(allowed)
    return [result[i] for i in allowed]


def metrics(expected, predicted, average_classes=None):
    average_classes = CLASSES if average_classes is None else average_classes
    assert expected and len(expected) == len(predicted)
    assert set(expected) <= set(average_classes) <= set(CLASSES)
    # A previous five-way probe may predict refusal: count it as an error, never
    # remove that row or average an extra fifth class into substantive metrics.
    assert set(predicted) <= set(core.CLASSES)
    per = {}
    for label in average_classes:
        tp = sum(a == b == label for a, b in zip(expected, predicted))
        support = expected.count(label)
        count = predicted.count(label)
        per[label] = dict(support=support, predicted=count, recall=tp/support if support else 0,
                          f1=2*tp/(support+count) if support+count else 0)
    return dict(count=len(expected), macro_f1=sum(x['f1'] for x in per.values())/len(per),
                accuracy=sum(a == b for a, b in zip(expected, predicted))/len(expected), per_class=per,
                confusion={a: {b: sum(x == a and y == b for x, y in zip(expected, predicted))
                               for b in core.CLASSES} for a in average_classes})


def passes(value, f1, recall):
    return value['macro_f1'] >= f1 and all(v['recall'] >= recall for v in value['per_class'].values())


def evaluate(records, predictions, challenges):
    assert set(predictions) == {r['example_id'] for r in records if r['split'] != 'train'}
    assert set(predictions.values()) <= set(CLASSES)
    by = {r['example_id']: r for r in records}
    def score(ids, labels=None):
        return metrics([by[i]['relation'] for i in ids], [predictions[i] for i in ids], labels)
    external = score([i for i, r in by.items() if r['split'] == 'external_dev'])
    historical = score([i for i, r in by.items() if r['split'] == 'historical_dev'])
    challenge = {k: score(v['example_ids'], v['classes']) for k, v in challenges.items()}
    ext = passes(external, .75, .60) and all(v['macro_f1'] >= .70 for v in challenge.values())
    hist = passes(historical, .70, .60)
    if ext and hist:
        conclusion = 'EXTERNAL_DATA_GENERALIZATION_SUPPORTED'
    elif ext and not hist:
        conclusion = 'SOURCE_FAMILY_OR_DISTRIBUTION_OVERFIT'
    elif not passes(external, .75, .60) and not hist:
        conclusion = 'RELATION_REPRESENTATION_STILL_INSUFFICIENT'
    else:
        conclusion = 'INCONCLUSIVE_MIXED_GATES'
    return dict(external=external, historical=historical, challenges=challenge,
                external_pass=ext, historical_pass=hist, success=ext and hist, conclusion=conclusion)


def standardized(np, features):
    assert features.shape == (2040, 3072) and features.dtype == np.float32
    assert np.isfinite(features).all()
    train = features[:1792]
    mean = np.mean(train, axis=0, dtype=np.float32)
    std = np.maximum(np.std(train, axis=0, ddof=0, dtype=np.float32), np.float32(1e-6))
    result = (features-mean)/std
    assert np.isfinite(result).all()
    return mean, std, result


def train_one_head(torch, features, labels):
    """Future execution primitive only; never called by preparation or tests."""
    assert features.shape == (1792, 3072) and labels.shape == (1792,)
    assert features.dtype == torch.float32 and not features.requires_grad
    assert labels.bincount(minlength=4).tolist() == [448]*4
    torch.manual_seed(7)
    head = torch.nn.Linear(3072, 4, device=features.device, dtype=torch.float32)
    with torch.no_grad():
        head.weight.zero_()
        head.bias.zero_()
    assert sum(p.numel() for p in head.parameters()) == 12292
    optimizer = torch.optim.Adam(head.parameters(), lr=.01, betas=(.9, .999), eps=1e-8, weight_decay=0)
    for _ in range(200):
        optimizer.zero_grad(set_to_none=True)
        loss = torch.nn.functional.cross_entropy(head(features), labels) + .001*head.weight.square().mean()
        assert bool(torch.isfinite(loss).item())
        loss.backward()
        optimizer.step()
    return head


def prepare():
    import os
    import sys
    os.environ.update(USE_TORCH='0', USE_TF='0', USE_FLAX='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    sys.path.insert(0, str(ROOT/'tuning/second_domain_agnostic_v2'))
    import runtime
    frozen = read(V2/'freeze.json')['files']
    bindings = {}
    def bound(path):
        relative = path.relative_to(ROOT).as_posix()
        value = sha(path)
        if relative in frozen:
            assert value == frozen[relative]
        bindings[relative] = value
        return read(path)
    spec = bound(V2/'experiment.json')
    split = bound(V2/'split.json')
    challenges = bound(V2/'dev_challenges.json')
    receipt = bound(V2/'holdout_receipt.json')
    assert receipt['consumed'] is False and receipt['evaluations'] == 0
    merged_path = V2/'merged_four_way_train.jsonl'
    bindings[merged_path.relative_to(ROOT).as_posix()] = sha(merged_path)
    assert sha(merged_path) == frozen[merged_path.relative_to(ROOT).as_posix()]
    train = [json.loads(line) for line in merged_path.read_bytes().splitlines()]
    historical = bound(ROOT/'tuning/auditor_canonical_execution/dataset.json')
    historical_split = bound(ROOT/'tuning/auditor_canonical_execution/split.json')
    htrain = [r for r in historical if r['example_id'] in historical_split['train'] and r['relation'] in CLASSES]
    hdev = [r for r in historical if r['example_id'] in historical_split['validation'] and r['relation'] in CLASSES]
    assert train[:192] == htrain and len(htrain) == 192 and len(train) == 1792 and len(hdev) == 48
    assert {r['example_id'] for r in train[192:]} == set(split['train'])
    with (V2/'external_four_way_view.jsonl').open('rb') as stream:
        dev = select_dev(stream, split['dev'])
    assert len(dev) == 200
    assert not set(split['holdout']) & {r['example_id'] for r in train+dev+hdev}
    # Bind only authorized content, never hash or deserialize HOLDOUT records.
    bindings['external_dev_selected_content_sha256'] = core.digest(dev)
    tok = runtime.old.tokenizer('auditor')
    records = []
    for group, rows, count in [('train', train, 448), ('external_dev', dev, 50), ('historical_dev', hdev, 12)]:
        assert {c: sum(r['relation'] == c for r in rows) for c in CLASSES} == {c: count for c in CLASSES}
        for row in rows:
            value, _ = core.normalized_input(row['input'])
            prompt = tok.apply_chat_template(runtime.task_messages(dict(role='auditor', input=value)), tokenize=False, add_generation_prompt=True)
            ids = tok(prompt, add_special_tokens=False)['input_ids']
            assert 0 < len(ids) <= 1056
            if 'lengths' in row:
                assert core.digest(prompt.encode()) == row['lengths']['prompt_sha256']
            records.append(dict(example_id=row['example_id'], split=group, relation=row['relation'],
                                input_ids=ids, prompt_sha256=core.digest(prompt.encode())))
    assert len({r['example_id'] for r in records}) == 2040
    old_path = ROOT/'docs/fix/auditor_linear_probe_run/downloaded/evidence/full_dev.jsonl'
    bindings[old_path.relative_to(ROOT).as_posix()] = sha(old_path)
    old = {r['example_id']: r for r in [json.loads(x) for x in old_path.read_bytes().splitlines()]}
    baseline = metrics([r['relation'] for r in hdev], [old[r['example_id']]['raw_head_class'] for r in hdev])
    baseline.update(prediction_field='raw_head_class', example_ids=[r['example_id'] for r in hdev],
                    comparison='Four substantive classes only; refusal predictions count as errors; no explanation scoring.')
    write('baseline.json', baseline)
    write('records.json', records)
    write('challenges.json', challenges)
    write('bindings.json', bindings)
    write('experiment.json', dict(name='AUDITOR_V2_ONE_OFF_CLASSIFICATION_DIAGNOSTIC',
        status='PREPARED_ONLY', data_verdict='AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY', data_admitted=False,
        one_off_data_exception=True, execution_authorized=False, cloud_launch_authorized=False,
        model_id=spec['model_id'], revision=spec['revision'], adapter_hashes=spec['adapter_hashes'], asset_hashes=spec['asset_hashes'],
        base_weight_sha256='e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a',
        architecture='frozen checkpoint120 backbone and LoRA -> final prompt token 3072 features -> TRAIN-only normalization -> four-way linear head',
        head=spec['head'], standardization=spec['standardization'], classes=CLASSES,
        training=dict(historical=192, external=1600, total=1792),
        co_primary=dict(external_dev=dict(rows=200, macro_f1=.75, every_class_recall=.60),
                        historical_dev=dict(rows=48, macro_f1=.70, every_class_recall=.60)),
        challenge_gates=dict(shorter=.70, longer=.70), challenge_macro_definition='Mean over the three declared supported classes; fourth-class predictions still count as errors.',
        refusal='Separate and unchanged; not invoked or trained', explanations=False, lora_updates=False,
        holdout_consumed=False, maximum_candidates=1, updates=200, no_dev_selection=True,
        unassigned_outcomes='INCONCLUSIVE_MIXED_GATES; never success',
        insufficiency_rule='Both primary gate predicates fail; report exact margins, no claim of statistical materiality.'))
    write('preflight.json', dict(status='LOCAL_PREPARATION_COMPLETE_NOT_LAUNCH_AUTHORIZED',
        exact_row_counts=dict(train=1792, external_dev=200, historical_dev=48, total=2040),
        historical_dev_co_primary=True, provenance_in_prompts=False,
        prompt_transport='Only input_ids feed the model; ID, label and split are never prompt fields.',
        holdout_consumed=False, holdout_labels_decoded=False, holdout_metrics=False,
        holdout_routing='Mixed JSONL scanned as opaque bytes for example_id only; only 200 allowlisted DEV records deserialized. Excluded bytes not retained/exported.',
        training=False, inference=False, cloud_launched=False, torch_imported='torch' in sys.modules,
        prompt_max_tokens=max(len(r['input_ids']) for r in records),
        price=dict(provider='Lambda', gpu='A10 24GB', usd_per_gpu_hour=1.29, checked_date='2026-09-17',
                   source='https://lambda.ai/instances', taxes_excluded=True, region_capacity_verified=False),
        projection=dict(feature_seconds=431.2246539374465, head_seconds=2.760562536106667,
                        wall_minutes=[15,30], cost_usd=[.3225,.645],
                        basis='Frozen V2 projection from prior A10 throughput; setup/transfers uncertain; not a measured run'),
        next_boundary='Separate cloud/execution authorization and launch-time budget/capacity check required; this package has no launcher.'))
    assert 'torch' not in sys.modules
    print(json.dumps(dict(status='PREPARED_ONLY', baseline_macro_f1=baseline['macro_f1'], records=len(records))))


if __name__ == '__main__':
    prepare()
