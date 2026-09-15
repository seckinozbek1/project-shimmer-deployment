"""Frozen, offline semantic-task evaluation; imports the production adapters.

No generation, training, provider client, hidden key or operator-state access.
Gold lives beside this module, outside the production source-layer roots.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import bounded_extraction as ex
import compact_contracts as cc

VERSION = 'semantic-task-v1'
GROUPS = ('document_family', 'template_family', 'derivation_group',
          'paraphrase_family', 'renamed_family', 'near_duplicate_family')
SPLITS = ('train', 'dev', 'test', 'sealed_adversarial', 'regression')
ERRORS = ('prompt_contract_defect', 'parser_adapter_defect',
          'model_semantic_capability_error', 'evidence_selection_error',
          'instruction_following_formatting_error', 'truncation_output_efficiency_error',
          'unsupported_hallucination_attribution_error')
STATES = {
    'extracted': 'accepted extraction; all owned aliases covered',
    'examined_empty': 'accepted examined-empty; never missing ownership',
    'semantic_refusal': 'recognized refusal wire; production acceptance remains false',
    'incomplete': 'not accepted; coverage or transport incomplete',
    'malformed': 'not accepted; technical/contract failure',
    'fidelity': 'accepted comparison; finding remains MATCH/DIVERGENCE/OMISSION/ADDITION',
}


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else
                          json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def strict_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def owned(record):
    spans = ex.ledger(record['source_text'], record['example_id'], record['ledger_max_chars'])
    return tuple(s for s in spans if ex.wire_id(s) in record['owned_aliases'])


def render_task(record):
    """Use frozen production builders; target/adjudication never enter input.

    For fidelity the ORIGINAL is the owned source, not neighboring context.
    Supplied neighboring refs remain distractors in the record/evidence scorer.
    """
    spans = ex.ledger(record['source_text'],record['example_id'],record['ledger_max_chars'])
    if record['role']=='producer':
        return cc.producer_prompt(owned(record),spans,record['example_id'])
    source=''.join(s.text for s in owned(record))
    extracted={'items':[{'draft_text':record['extraction_text']}]} if record['extraction_text'] else {'items':[]}
    return cc.auditor_prompt(source,extracted,record['required_refs']) + '\n' + json.dumps({
        'boundary_context_only': [s.text for s in spans if ex.wire_id(s) in record['context_only_aliases']],
        'supplied_refs': record['supplied_refs'], 'unrouted_rule_distractors': record['distractor_rules'],
        'scope': 'Compare only ORIGINAL and EXTRACTION. Context is not owned and no policy rule is routed.'})


def classify(record, raw, truncated=False):
    """Refusal is a valid *outcome*, never production semantic acceptance."""
    try:
        obj = strict_json(raw)
    except (ValueError, TypeError):
        return ('incomplete' if truncated else 'malformed'), False, None
    if truncated:
        return 'incomplete', False, obj
    if obj == {'items': [], 'status': 'refused'}:
        return 'semantic_refusal', True, obj
    try:
        if record['role'] == 'producer':
            cc.producer(obj, owned(record), record['example_id'])
            state = 'extracted' if any(i['status'] == 'extracted' for i in obj['items']) else 'examined_empty'
        else:
            cc.auditor(obj, record['example_id'], record['required_refs'], record['supplied_refs'],
                       empty_input=not record['source_text'] and not record['extraction_text'])
            state = 'fidelity' if obj['items'] else 'examined_empty'
        return state, True, obj
    except (ValueError, TypeError, KeyError):
        # Coverage is distinct only if each supplied item independently meets
        # the production contract. Bad items must not masquerade as incomplete.
        if record['role'] == 'producer' and isinstance(obj, dict) and set(obj) == {'items'} and isinstance(obj['items'], list):
            try:
                aliases = [i['span'] for i in obj['items']]
                if len(aliases) == len(set(aliases)) and set(aliases) < set(record['owned_aliases']):
                    cc.producer(obj, tuple(s for s in owned(record) if ex.wire_id(s) in aliases), record['example_id'])
                    return 'incomplete', False, obj
            except (ValueError, TypeError, KeyError):
                pass
        return 'malformed', False, obj


def pr(actual, expected):
    actual, expected = set(actual), set(expected)
    tp = len(actual & expected)
    return dict(tp=tp, fp=len(actual-expected), fn=len(expected-actual),
                precision=tp/len(actual) if actual else (1.0 if not expected else 0.0),
                recall=tp/len(expected) if expected else 1.0)


def evidence(actual, expected, allowed):
    result = pr(actual, expected)
    result['invented'] = len(set(actual)-set(allowed))
    result['hallucinated_rate'] = result['invented']/max(1, len(set(actual)))
    return result


def observations(obj, role):
    """Diagnostic fields from whole parse only, never repaired prefixes."""
    items = obj.get('items', []) if isinstance(obj, dict) else []
    items = [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
    def values(key):
        return [(i.get('span', '') if isinstance(i.get('span', ''), str) else '<invalid-alias>', x) for i in items for x in
                (i.get(key, []) if isinstance(i.get(key), list) else []) if isinstance(x, str)]
    return items, values


def evaluate(record, raw, *, truncated=False, completed=True, reason_review=None):
    state, contract, obj = classify(record, raw, truncated)
    items, vals = observations(obj, record['role'])
    gold = record['gold_target']
    golditems, goldvals = observations(gold, record['role'])
    refusal = state == 'semantic_refusal'
    expected_refusal = record['expected_refusal']
    refs_key = 'refs' if record['role'] == 'producer' else 'ref_ids'
    selected = [v for _, v in vals(refs_key)]
    expected = [v for _, v in goldvals(refs_key)]
    ev = evidence(selected, expected, record['supplied_refs'])
    rules = set(re.findall(r'\bCONV-[A-Za-z0-9-]+', raw))
    result = dict(example_id=record['example_id'], role=record['role'],
                  family=record['document_family'], split=record['split'],
                  state=state, transport_complete=bool(completed and not truncated),
                  truncated=bool(truncated), contract_valid=contract,
                  production_accepted=contract and not refusal and completed and not truncated,
                  expected_refusal=expected_refusal, predicted_refusal=refusal,
                  refusal_correct=refusal == expected_refusal,
                  over_refusal=refusal and not expected_refusal,
                  under_refusal=expected_refusal and not refusal,
                  unsupported_forced_answer=expected_refusal and bool(items),
                  insufficient_evidence_recognized=refusal if expected_refusal else None,
                  evidence=ev, unrouted_rule_count=len(rules-set(record['routed_rules'])),
                  raw_sha256=digest(raw.encode('utf-8')))
    if record['role'] == 'producer':
        aliases = [i.get('span') for i in items]
        aliases_valid = all(isinstance(a, str) and a in record['owned_aliases'] for a in aliases)
        ownership = aliases_valid and len(aliases) == len(set(aliases)) and set(aliases) == set(record['owned_aliases'])
        copied = any('draft_text' in i or 'section_id' in i for i in items)
        copied |= bool(re.search(r'"(?:draft_text|section_id)"\s*:', raw))
        copied |= any(len(s.text.strip()) >= 24 and s.text.strip() in raw for s in owned(record))
        scores = {k: pr(vals(k), goldvals(k)) for k in ('claims', 'questions', 'uncertainty')}
        semantic = all(s['fp'] == s['fn'] == 0 for s in scores.values()) and ownership
        empty_correct = (state == 'examined_empty') == (record['abstract_relation'] == 'EMPTY')
        result.update(exact_alias_valid=aliases_valid, ownership_valid=ownership,
                      claims=scores['claims'], information_gaps=scores['questions'],
                      uncertainty=scores['uncertainty'], examined_empty_correct=empty_correct,
                      copied_source_violation=bool(copied), semantic_completeness=semantic)
        semantic &= not copied and empty_correct
    else:
        predicted = items[0].get('finding') if len(items) == 1 else None
        relation = predicted == record['abstract_relation']
        # Canonical authored rationale is an explicit rubric entry. Other prose
        # requires a hash-bound independent review; lexical similarity is never truth.
        reason = items[0].get('reasoning') if len(items) == 1 else None
        correctness = True if golditems and reason == golditems[0]['reasoning'] else None
        if reason_review is not None:
            if (reason_review.get('raw_sha256') != result['raw_sha256'] or
                reason_review.get('example_id') != record['example_id'] or
                reason_review.get('state') not in ('independently_reviewed', 'adjudicated') or
                not reason_review.get('reviewer_id') or not reason_review.get('rationale') or
                type(reason_review.get('correct')) is not bool):
                raise ValueError('Unbound or unadjudicated reason review')
            correctness = reason_review['correct']
        uncertainty_correct = bool(items and golditems and items[0].get('confidence') == golditems[0]['confidence'])
        result.update(expected_relation=record['abstract_relation'], predicted_relation=predicted,
                      relation_correct=relation, reason_correct=correctness,
                      reason_basis='canonical_authored_rubric' if correctness is True and reason_review is None else
                      ('independent_review' if reason_review else 'unassessed'),
                      uncertainty_preserved=uncertainty_correct,
                      incorrect_confident_judgment=bool(items and predicted in ('MATCH','DIVERGENCE') and
                                                       not relation and items[0].get('confidence') == 'CONFIDENT'))
        semantic = relation and correctness is True and uncertainty_correct
        if not golditems and not expected_refusal:
            semantic = state == 'examined_empty'
    if expected_refusal:
        semantic = refusal
    result['semantic_correct'] = bool(semantic and ev['fp'] == ev['fn'] == 0 and not result['unrouted_rule_count'])
    result['accepted_outcome'] = bool(result['semantic_correct'] and contract and completed and not truncated)
    result['semantic_accepted'] = result['accepted_outcome'] and not refusal
    errors = []
    if truncated: errors.append(ERRORS[5])
    if not contract: errors.append(ERRORS[4])
    if ev['fp'] or ev['fn']: errors.append(ERRORS[3])
    if ev['invented'] or result['unrouted_rule_count']: errors.append(ERRORS[6])
    if not result['semantic_correct']: errors.append(ERRORS[2])
    result['error_classes'] = errors
    result['catastrophic'] = dict(invented_evidence=ev['invented'] > 0,
        invented_rule=result['unrouted_rule_count'] > 0,
        incorrect_confident_judgment=result.get('incorrect_confident_judgment', False),
        silent_gap_omission=result.get('information_gaps', {}).get('fn', 0) > 0)
    return result


def validate_record(record):
    import jsonschema
    jsonschema.Draft202012Validator(read(Path(__file__).with_name('record.schema.json'))).validate(record)
    if record['versions'] != {k: VERSION for k in ('schema','task','adapter','validator')}:
        raise ValueError('Version mismatch')
    if record['provenance']['privacy'] != 'authored_public_synthetic' or record['provenance']['rights'] != 'project_authored':
        raise ValueError('Seed provenance/privacy unsupported')
    adjudication = record['adjudication']
    if adjudication['final_target'] != record['gold_target']:
        raise ValueError('Unresolved target')
    if adjudication['state'] == 'authored_single':
        if adjudication['first_judgment'] != record['gold_target']:
            raise ValueError('Single author target mismatch')
        if adjudication['second_id'] is not None or adjudication['second_judgment'] is not None or adjudication['agreement'] != 'not_reviewed':
            raise ValueError('Fabricated independent agreement')
    else:
        if not adjudication['second_id'] or adjudication['second_id'] == adjudication['first_id'] or adjudication['second_judgment'] is None:
            raise ValueError('Independent review missing')
        agree = adjudication['first_judgment'] == adjudication['second_judgment']
        if adjudication['agreement'] != ('agree' if agree else 'disagree'):
            raise ValueError('Adjudication disagreement mismatch')
        if not agree and adjudication['state'] != 'adjudicated':
            raise ValueError('Unresolved disagreement')
    spans = ex.ledger(record['source_text'], record['example_id'], record['ledger_max_chars'])
    aliases = {ex.wire_id(s) for s in spans}
    if not set(record['owned_aliases']) <= aliases or set(record['owned_aliases']) & set(record['context_only_aliases']):
        raise ValueError('Ownership mapping invalid')
    if set(record['owned_aliases']) | set(record['context_only_aliases']) != aliases:
        raise ValueError('Unclassified source span')
    if set(record['required_refs']) - set(record['supplied_refs']):
        raise ValueError('Unavailable required evidence')
    if set(record['supplied_refs']) != set(re.findall(r'\bREF-\d{4,}\b', record['source_text'])):
        raise ValueError('Evidence provenance missing')
    if record['routed_rules']:
        raise ValueError('Fidelity task does not route policy rules')
    scored = evaluate(record, json.dumps(record['gold_target']))
    if not scored['accepted_outcome']:
        raise ValueError('Malformed, inconsistent or unsupported gold target')
    state = scored['state']
    if record['role'] == 'producer' and not record['expected_refusal']:
        uncertainty = any(i['uncertainty'] for i in record['gold_target']['items'])
    else:
        uncertainty = any(i.get('confidence') == 'UNCERTAIN' for i in record['gold_target']['items'])
    if uncertainty != record['expected_uncertainty']:
        raise ValueError('Uncertainty state mismatch')
    expected_state = 'semantic_refusal' if record['expected_refusal'] else (
        'examined_empty' if record['abstract_relation'] == 'EMPTY' else
        ('extracted' if record['role'] == 'producer' else 'fidelity'))
    if state != expected_state or record['expected_refusal'] != (record['abstract_relation'] == 'INSUFFICIENT_EVIDENCE'):
        raise ValueError('Invalid refusal/relation state')
    if record['role'] == 'producer' and not record['expected_refusal']:
        for item in record['gold_target']['items']:
            text = next(s.text for s in spans if ex.wire_id(s) == item['span'])
            if set(item['claims']) != set(re.findall(r'\bCLM-[A-Za-z0-9-]+', text)):
                raise ValueError('Missing explicit claim target')
        target_refs = {r for i in record['gold_target']['items'] for r in i['refs']}
        if target_refs != set(record['required_refs']):
            raise ValueError('Missing evidence target')


def leakage(records, regression_hashes=None):
    if regression_hashes is None:
        public = read(ROOT/'docs/fix/compact_contract_ab/fixture.json')
        regression_hashes = {digest(' '.join(public['source'].split()).encode('utf-8'))}
    ids, groups, hashes = {}, {}, {}
    for row in records:
        validate_record(row)
        ident, split = row['example_id'], row['split']
        if ident in ids: raise ValueError('Duplicate example ID')
        ids[ident] = row
        for field in GROUPS:
            key = (field, row[field])
            if key in groups and groups[key] != split:
                raise ValueError('Cross-split family leakage: ' + field)
            groups[key] = split
        # Source and extraction separately: an extraction can leak an earlier source.
        for content in (row['source_text'], row['extraction_text']):
            if not content.strip(): continue
            value = digest(' '.join(content.split()).encode('utf-8'))
            if value in hashes and hashes[value] != split:
                raise ValueError('Exact duplicate leakage')
            hashes[value] = split
            if value in regression_hashes and split != 'regression':
                raise ValueError('Public regression contamination')
        if row['provenance']['public_regression'] and split != 'regression':
            raise ValueError('Public regression descendant contamination')
    for row in records:
        visited, current = set(), row
        while current['parent_id'] is not None:
            parent = current['parent_id']
            if parent not in ids or parent in visited: raise ValueError('Broken or cyclic ancestry')
            visited.add(parent)
            ancestor = ids[parent]
            if ancestor['split'] != row['split']: raise ValueError('Cross-split ancestry')
            if ancestor['derivation_group'] != row['derivation_group']: raise ValueError('Disconnected derivation')
            if ancestor['provenance']['public_regression'] and not row['provenance']['public_regression']:
                raise ValueError('Regression ancestry hidden')
            current = ancestor
    return dict(examples=len(records), cross_split_findings=0, ancestry_findings=0,
                exact_duplicate_findings=0, family_groups=len(groups))


def verify_freeze():
    manifest = read(ROOT/'config/semantic_task_contract_v1.json')
    for path, expected in manifest['hashes'].items():
        if digest((ROOT/path).read_bytes()) != expected:
            raise ValueError('Frozen production authority drift: ' + path)
    for role, prompt in [('producer',cc.PRODUCER),('auditor',cc.AUDITOR)]:
        if digest(prompt.encode('utf-8')) != manifest['prompt_hashes'][role]:
            raise ValueError('Frozen prompt drift')
    return True


def select_for_tuning(records, splits=('train', 'dev')):
    """Public seed controls; not an OS security boundary or a claim of blindness."""
    if not set(splits) <= {'train','dev'}:
        raise ValueError('Held-out and regression labels excluded from tuning export')
    leakage(records)
    return [r for r in records if r['split'] in splits]


def adjudicate(record, reviewer_id, judgment, rationale, *, final_target=None):
    from copy import deepcopy
    if not reviewer_id or reviewer_id == record['adjudication']['first_id'] or not rationale:
        raise ValueError('Independent reviewer and rationale required')
    result = deepcopy(record)
    a = result['adjudication']
    agree = a['first_judgment'] == judgment
    if not agree and final_target is None:
        raise ValueError('Disagreement requires explicit resolution')
    a.update(second_id=reviewer_id,second_judgment=judgment,agreement='agree' if agree else 'disagree',
             state='independently_reviewed' if agree else 'adjudicated',rationale=rationale,
             final_target=judgment if agree else final_target)
    result['gold_target'] = deepcopy(a['final_target'])
    validate_record(result)
    return result


def governance(policy):
    if (policy['producer_family'] == policy['auditor_family'] or policy['self_audit'] or
        policy['privacy'] != 'authored_public_synthetic' or not policy['operator_authorized'] or
        policy['training'] or policy['multi_round'] or policy['paid_api'] or not policy['provenance_verified']):
        raise ValueError('Governance boundary rejected')
    return True


def wilson(k, n):
    if not n: return None
    z = 1.959963984540054
    centre = (k/n + z*z/(2*n))/(1+z*z/n)
    delta = z*math.sqrt(k/n*(1-k/n)/n + z*z/(4*n*n))/(1+z*z/n)
    return [max(0, centre-delta), min(1, centre+delta)]


def aggregate(results):
    def block(rows):
        metrics = {}
        for key in sorted({k for r in rows for k,v in r.items() if isinstance(v, bool)}):
            values = [r[key] for r in rows if isinstance(r.get(key), bool)]
            metrics[key] = dict(n=len(values), count=sum(values), rate=sum(values)/len(values))
        for key in ('claims','information_gaps','uncertainty','evidence'):
            selected = [r[key] for r in rows if isinstance(r.get(key), dict)]
            if selected:
                counts = {k: sum(s[k] for s in selected) for k in ('tp','fp','fn')}
                metrics[key] = dict(counts, precision=counts['tp']/max(1,counts['tp']+counts['fp']),
                                    recall=counts['tp']/max(1,counts['tp']+counts['fn']))
        for relation in ('MATCH','DIVERGENCE','OMISSION','ADDITION','INSUFFICIENT_EVIDENCE'):
            actual = [r['example_id'] for r in rows if (r.get('predicted_relation') == relation or
                      relation == 'INSUFFICIENT_EVIDENCE' and r['predicted_refusal'])]
            expected = [r['example_id'] for r in rows if (r.get('expected_relation') == relation or
                        relation == 'INSUFFICIENT_EVIDENCE' and r['expected_refusal'])]
            metrics['class_'+relation] = pr(actual, expected)
        metrics['catastrophic_counts'] = dict(Counter(k for r in rows for k,v in r['catastrophic'].items() if v))
        metrics['accepted_outcome_descriptive_wilson95'] = wilson(sum(r['accepted_outcome'] for r in rows),len(rows))
        return metrics
    families = sorted({r['family'] for r in results})
    return dict(n=len(results), aggregate=block(results),
                per_role={role:block([r for r in results if r['role']==role]) for role in ('producer','auditor')},
                per_family={f:block([r for r in results if r['family']==f]) for f in families},
                interval_warning='Descriptive only: correlated authored rows are not independent model trials; use family breakdown.')


def acceptance(results, registration, run=None):
    """No defaults that can silently declare a model accepted."""
    if (registration.get('state') != 'preregistered' or not registration.get('registered_before_run') or
        not registration.get('rationale') or not registration.get('dataset_sha256') or
        not registration.get('minimum_families') or not registration.get('minimum_contract_rate')):
        return {'decision':'NOT_PREREGISTERED'}
    if (not run or run.get('dataset_sha256') != registration['dataset_sha256'] or
        not run.get('registration_sha256') == digest(registration) or
        not run.get('governance_verified') or not run.get('independent_labels_verified') or
        not run.get('blind_holdout_verified') or run.get('public_seed', True)):
        return {'decision':'UNVERIFIED_EVALUATION_CONTEXT'}
    if len({r['family'] for r in results}) < registration['minimum_families']:
        return {'decision':'INSUFFICIENT_FAMILIES'}
    good = all(not r['truncated'] and not any(r['catastrophic'].values()) and r['accepted_outcome'] for r in results)
    good &= sum(r['contract_valid'] for r in results)/max(1,len(results)) >= registration['minimum_contract_rate']
    return {'decision':'PASS' if good else 'FAIL', 'governance_requires_separate_verified_gate':True}
