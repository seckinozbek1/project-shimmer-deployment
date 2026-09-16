"""Read only the preserved run-1 TRAIN/DEV evidence; never protected targets."""
import os
os.environ.update(USE_TORCH='0', USE_TF='0', USE_FLAX='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
V1 = ROOT / 'tuning/first_domain_agnostic_v1'
sys.path.insert(0, str(V1))
import common as old


def components(target, tok):
    """Partition actual serialized-target tokens by midpoint character offset.

    Field values include escaped typed atoms. JSON keys/punctuation, span,
    severity and confidence are structural. Native termination is separate.
    No sum of independently tokenized fragments masquerades as target tokens.
    """
    text = old.canonical(target).decode()
    ranges = []
    mapping = dict(claims='claims', questions='gaps', uncertainty='uncertainty',
                   refs='refs', ref_ids='refs', finding='relation', reasoning='reason', status='status')
    decoder = json.JSONDecoder()
    for match in re.finditer(r'"(claims|questions|uncertainty|refs|ref_ids|finding|reasoning|status)":', text):
        start = match.end()
        _, length = decoder.raw_decode(text[start:])
        ranges.append((start, start + length, mapping[match[1]]))
    encoded = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    counts = Counter()
    for a, b in encoded['offset_mapping']:
        midpoint = (a + b) / 2
        counts[next((kind for lo, hi, kind in ranges if lo <= midpoint < hi), 'structural_json')] += 1
    assert sum(counts.values()) == len(encoded['input_ids'])
    return counts


def atom(value):
    try:
        prefix, payload = value.split(': ', 1)
        return dict(json.loads(payload), kind=prefix)
    except (ValueError, TypeError):
        return None


def taxonomy(gold, predicted):
    """Conservative one-to-one matching; raw questions are rendering failures.

    Match exact atoms first, then same attribute/referent with wrong type,
    then referent-only substitutions, then attribute substitutions. Unmatched
    gold/predictions are omission/extra. Invalid whole JSON is not repaired.
    """
    expected = [(i['span'], x) for i in gold['items'] for x in i['questions']]
    actual = [(i.get('span'), x) for i in predicted.get('items', []) for x in i.get('questions', [])]
    misplaced = [(i.get('span'), x) for i in predicted.get('items', []) for x in i.get('uncertainty', []) if x.startswith('Gap:')]
    errors = []; used = set(); remaining = []
    for g in expected:
        match = next((j for j, p in enumerate(actual) if j not in used and g == p), None)
        if match is None: remaining.append(g)
        else: used.add(match)
    for g in remaining:
        if g in misplaced:
            misplaced.remove(g); errors.append(dict(category='wrong_type_or_field', gold=g, predicted=g)); continue
        rendered_match = None
        for j,p in enumerate(actual):
            if j in used or atom(p[1]) is not None or p[0]!=g[0]: continue
            try:
                interpretations=old.dependencies()[2].interpretations(p[1],p[1],p[0],[])
                if g[1] in [old.dependencies()[2].canonical_atom(a) for a in interpretations]: rendered_match=j;break
            except ValueError: pass
        if rendered_match is not None:
            used.add(rendered_match)
            errors.append(dict(category='rendering_error',gold=g,predicted=actual[rendered_match]));continue
        ga = atom(g[1]); candidates = []
        for j, p in enumerate(actual):
            if j in used: continue
            pa = atom(p[1])
            if pa is None: continue
            diff = {k for k in set(ga) | set(pa) if ga.get(k) != pa.get(k)}
            if g[0] != p[0]: diff.add('span')
            if diff <= {'kind', 'category', 'state'}: priority, category = 0, 'wrong_type_or_state'
            elif diff <= {'subject', 'ordinal', 'scope', 'span'}: priority, category = 1, 'wrong_referent'
            elif diff <= {'attribute'}: priority, category = 2, 'wrong_attribute'
            else: continue
            candidates.append((priority, j, category))
        if candidates:
            _, j, category = min(candidates); used.add(j)
            errors.append(dict(category=category, gold=g, predicted=actual[j]))
        else:
            errors.append(dict(category='omission', gold=g))
    for j, p in enumerate(actual):
        if j not in used:
            errors.append(dict(category='rendering_error' if atom(p[1]) is None else 'extra_gap', predicted=p))
    errors.extend(dict(category='extra_gap_wrong_field', predicted=p) for p in misplaced)
    return errors


def run():
    result = dict(scope='run-1 TRAIN/DEV only', inputs={}, roles={}, producer_rows=[])
    for role in ('producer', 'auditor'):
        tok = old.tokenizer(role)
        role_result = {}
        for split in ('train', 'dev'):
            path = V1 / role / (split + '.json')
            rows = old.read(path); result['inputs'][str(path.relative_to(ROOT))] = old.digest(path.read_bytes())
            counts = Counter(); lengths = {}; classes = Counter(); signatures = Counter(); ref_features=Counter(); supervised=0
            for row in rows:
                target = row.get('canonical_target', row.get('semantic_target'))
                cls = ('INSUFFICIENT_EVIDENCE' if target.get('status') == 'refused' else
                       target['items'][0]['finding'] if role == 'auditor' else 'EXTRACTED')
                counts.update(components(target, tok)); classes[cls] += 1
                supervised+=old.encode(row,tok)['lengths']['target']
                ref_features[(cls,len(row['input']['required_refs']))]+=1
                lengths.setdefault(cls, []).append(len(tok(old.canonical(target).decode(), add_special_tokens=False)['input_ids']))
                if role == 'producer':
                    signatures.update(x for i in target['items'] for x in i['questions'])
            role_result[split] = dict(rows=len(rows), classes=dict(classes), target_components=dict(counts),
                target_component_percent={k: round(100*v/sum(counts.values()), 4) for k, v in counts.items()},
                supervised_tokens=supervised,native_termination_tokens=supervised-sum(counts.values()),
                supervised_component_percent={k:100*v/supervised for k,v in dict(counts,native_termination=supervised-sum(counts.values())).items()},
                target_lengths_by_class={k:dict(min=min(v), max=max(v), mean=mean(v)) for k,v in lengths.items()},
                required_reference_features=[dict(relation=k[0],required_refs=k[1],count=v) for k,v in sorted(ref_features.items())],
                gap_types=dict(signatures))
        evidence_dir = ROOT / 'docs/fix/first_real_tuning_20260916/downloaded/runs/first-domain-agnostic-tuning-v1' / role
        role_result['checkpoints'] = {}
        for step in ((16,) if role == 'producer' else (12, 24)):
            path = evidence_dir / f'dev-{step}.json'; evidence = old.read(path)
            result['inputs'][str(path.relative_to(ROOT))] = old.digest(path.read_bytes())
            goldrows = {x['example_id']:x for x in old.read(V1 / role / 'dev.json')}
            dist = Counter(); summary = Counter()
            for row in evidence:
                score = row['semantic_metrics']; summary['rows'] += 1
                for key in ('contract_valid', 'accepted_outcome', 'expected_refusal', 'predicted_refusal'):
                    summary[key] += int(score[key])
                summary['over_refusals'] += int(score['predicted_refusal'] and not score['expected_refusal'])
                parsed = row['parsed']
                if role == 'auditor':
                    dist['REFUSAL' if score['predicted_refusal'] else 'INVALID' if not score['contract_valid'] else parsed['items'][0]['finding']] += 1
                else:
                    errors = taxonomy(goldrows[row['example_id']]['canonical_target'], parsed) if parsed else [dict(category='contract_error_unparsed')]
                    gold = goldrows[row['example_id']]['canonical_target']
                    result['producer_rows'].append(dict(example_id=row['example_id'], accepted=score['accepted_outcome'],
                        contract_valid=score['contract_valid'], errors=errors,
                        claims=score['claims'], uncertainty=score['uncertainty'], evidence=score['evidence'],
                        historical_gap_counts=score['information_gaps'],
                        expected_gaps=len([x for i in gold['items'] for x in i['questions']])))
            role_result['checkpoints'][str(step)] = dict(summary, predicted_relations=dict(dist))
        result['roles'][role] = role_result
    result['producer_error_counts'] = dict(Counter(e['category'] for r in result['producer_rows'] for e in r['errors']))
    result['method'] = 'Atom-level exclusive taxonomy. Source-policy equivalence identifies raw-question rendering failures for diagnosis only; outputs/scores are never repaired. Contract error separate from unobservable atom omissions. Multiple errors per row permitted.'
    old.write(HERE / 'run1_audit.json', result)
    print(json.dumps(dict(producer_errors=result['producer_error_counts'], roles={k:dict(train=v['train']['classes'], checkpoints=v['checkpoints'], tokens=v['train']['target_component_percent']) for k,v in result['roles'].items()}), indent=2))


if __name__ == '__main__': run()
