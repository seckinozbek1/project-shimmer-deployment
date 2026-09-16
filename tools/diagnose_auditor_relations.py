"""Offline saved-evidence diagnosis. Tokenizer only; no models, training or network."""
import hashlib
import json
import math
import os
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(USE_TORCH='0', USE_TF='0', USE_FLAX='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'tuning/second_domain_agnostic_v2'))
import runtime as r

BASE = ROOT / 'docs/fix/auditor_canonical_tuning_run'
OUT = ROOT / 'docs/fix/auditor_relation_diagnosis'
DATA = ROOT / 'tuning/auditor_canonical_execution'
CLASSES = list(r.CLASSES)


def read(p):
    return json.loads(p.read_text(encoding='utf8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dist(v):
    v = list(v)
    return dict(n=len(v), minimum=min(v), mean=statistics.mean(v), median=statistics.median(v), maximum=max(v))


def append_report(result):
    path = ROOT/'docs/fix/AUDITOR_RELATION_FAILURE_DIAGNOSIS.md'
    marker = '<!-- GENERATED DIAGNOSTIC APPENDICES -->'
    prose = path.read_text(encoding='utf8').split(marker)[0].rstrip()
    lines = [prose, '', marker, '', '## Appendix A. Exact confusion cells and row IDs', '',
             'IDs below are complete dataset IDs; an em dash denotes an empty cell. Counts are computed from saved scored evidence and checked against raw JSON findings.', '']
    for step, item in result['confusion'].items():
        lines += [f'### Step{step}', '', '| Expected | Predicted | Count | Row IDs |', '|---|---|---:|---|']
        for expected, predictions in item['confusion_ids'].items():
            for predicted, ids in predictions.items():
                lines.append(f'| {expected} | {predicted} | {len(ids)} | '+(', '.join(ids) or '—')+' |')
        lines.append('')
    lines += ['## Appendix B. All 32 failed step120 rows', '',
        '“Supports predicted” below distinguishes the relation type asserted by the prose from support in the actual source/extraction. A true fragment is not a complete correct reason. Evidence flags evaluate ID selection, not entailment of the reason. Exact saved scorer reason_correct is null for every row below; semantic annotations do not change it.', '']
    for f in result['failures']:
        lines += [f"### {f['id']}", '', f"Expected **{f['expected']}**; predicted **{f['predicted']}**. Category **{f['taxonomy']}**. Catastrophe: **{f['catastrophe']}**.", '',
                  'Evidence refs (generated and expected, identical): `'+', '.join(f['evidence_refs'])+'`.', '',
                  '**Expected reason:** '+f['expected_reason'], '', '**Generated reason, exact:** '+f['generated_reason'], '',
                  '**Assessment:** '+f['note'], '',
                  '| Requested diagnostic | Finding |', '|---|---|',
                  '| Evidence selection correct | Yes |', '| Refusal/status correct | Yes |',
                  '| Only relation label wrong | No |',
                  f"| Relation and reason both wrong | {'Yes' if f['relation_and_reason_wrong'] else 'No; correct relation, reversed reason'} |",
                  f"| Reason supports expected class | {'Yes at relation-type level only; direction is wrong' if f['reason_supports_expected'] else 'No complete source-grounded account of the expected relation'} |",
                  '| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |',
                  '| Merely label-token mapping | No |',
                  f"| Directionality | {f['orientation']} |", '', '**Owned source, exact:**', '', '```text',
                  '\n'.join(s['text'] for s in f['source_spans']), '```', '', '**Extraction, exact:**', '', '```text', f['extraction'], '```', '']
        if f['quoted_content_membership']:
            lines += ['Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):', '', '| Quoted text | Literally in source | Literally in extraction |', '|---|---|---|']
            for q in f['quoted_content_membership']:
                lines.append(f"| {q['text'].replace('|', '/')} | {q['in_source']} | {q['in_extraction']} |")
            lines.append('')
    lines += ['## Appendix C. Complete dataset feature summaries', '',
              'Each numeric cell is mean [minimum, maximum]. All 300 individual feature records, exact categorical counts and source hashes are in diagnosis.json. Token-field attribution is approximate at subword boundaries; total token counts are exact.', '']
    for name, groups in result['dataset_summary'].items():
        lines += [f'### {name}', '', '| Class | n | Target tokens | Prompt tokens | Reason words | Reason chars | Refs | Source spans |', '|---|---:|---|---|---|---|---|---|']
        for c, v in groups.items():
            cells = []
            for key in ('target_tokens', 'prompt_tokens', 'reason_words', 'reason_characters', 'refs', 'source_spans'):
                d = v['numeric'][key]
                cells.append(f"{d['mean']:.3f} [{d['minimum']}, {d['maximum']}]")
            lines.append(f"| {c} | {v['count']} | "+' | '.join(cells)+' |')
        lines.append('')
        for c, v in groups.items():
            lines += [f'#### {name}: {c}', '']
            for k, value in v['categorical'].items():
                lines.append(f'- {k}: '+json.dumps(value, ensure_ascii=False))
            lines += ['- Relation-content target-token positions, zero-based: '+json.dumps(v['relation_positions']),
                      '- Token-field counts: '+json.dumps(v['token_categories']),
                      '- Class-exclusive extraction words with document frequency >=3: '+json.dumps(result['exclusive_lexical_markers'][name][c]), '']
    lines += ['## Appendix D. Training class windows and preservation', '',
              'Class counts in four ten-update windows (40 exposures per window):', '', '```json', json.dumps(result['training_class_windows'], indent=2), '```', '',
              f"Historical manifest: {result['historical_text_hashes_verified']} text files hash-verified. Canonical labels/split and all historical artifacts remain unchanged.", '',
              '```json', json.dumps(result['source_hashes'], indent=2), '```', '']
    path.write_text('\n'.join(lines), encoding='utf8')


def main():
    # Verify historical text without touching protected targets or model weights.
    manifest = read(BASE / 'EVIDENCE_MANIFEST.json')
    for name, entry in manifest['text_files'].items():
        assert sha(ROOT / name) == entry['sha256'], name
    rows = read(DATA / 'dataset.json')
    split = read(DATA / 'split.json')
    by = {x['example_id']: x for x in rows}
    assert len(rows) == 300 and all(x['role'] == 'auditor' for x in rows)
    tok = r.old.tokenizer('auditor')
    evidence = {}
    for step in (60, 120):
        directory = BASE / f'downloaded/evidence/checkpoint-{step}'
        scored = read(directory / 'full_dev_scored.json')
        raw = [json.loads(line) for line in (directory / 'full_dev.jsonl').read_text().splitlines()]
        assert len(raw) == len(scored) == 60
        assert [x['example_id'] for x in raw] == split['validation']
        for a, b in zip(raw, scored):
            assert a == {k: v for k, v in b.items() if k != 'metrics'}
            # No new scoring of historical outputs; use saved metrics as-is.
            assert json.loads(a['raw_output']).get('items', [{}]) == json.loads(b['raw_output']).get('items', [{}])
            m = b['metrics']
            obj = json.loads(a['raw_output'])
            predicted = 'INSUFFICIENT_EVIDENCE' if obj == dict(items=[], status='refused') else obj['items'][0]['finding']
            assert m['expected_relation'] == by[a['example_id']]['relation']
            assert m['predicted_relation'] == predicted
        matrix = {c: {p: [x['example_id'] for x in scored if x['metrics']['expected_relation'] == c and x['metrics']['predicted_relation'] == p] for p in CLASSES} for c in CLASSES}
        counts = Counter(x['metrics']['predicted_relation'] for x in scored)
        evidence[str(step)] = dict(confusion_ids=matrix, distribution={c: counts[c] for c in CLASSES},
            entropy_bits=-sum(n / 60 * math.log2(n / 60) for n in counts.values()),
            diversity=len(counts), correct=sum(x['metrics']['relation_correct'] for x in scored),
            wrong_substantive=sum(not x['metrics']['relation_correct'] and not x['metrics']['expected_refusal'] for x in scored))
        if step == 120:
            final = scored

    # Explicit analyst annotations, based on source/extraction/expected/generated
    # text review. These are diagnostic assertions, never scorer replacements.
    reversed_complete = {'047', '137', '152', '157', '162'}
    reversed_partial = {'277', '282'}
    reversal_reason_only = {'156'}
    special = {
        '058': 'False preservation: the added supervisor approval is not addressed; the reason describes only retained material.',
        '138': 'False replacement: two existing source claims are concatenated as a replacement for one; added inspector verification is ignored.',
        '140': 'Source heading is called an unsupported addition although it occurs in the source and is absent from extraction; headings are explicitly non-propositional.',
        '141': 'Changed uncertainty is treated as an addition; the claim that all original qualifications remain is false.',
        '142': 'False preservation: the stated uncertainty was omitted, contradicting the reason.',
        '147': 'False preservation: the stated uncertainty was omitted, contradicting the reason.',
        '151': 'Changed uncertainty is treated as addition alongside an unchanged gap; original uncertainty no longer remains.',
        '156': 'Exact source-to-extraction replacement is reversed: unclear -> clear is described as clear -> unclear.',
        '160': 'Extraction-only structural footer is treated as a substantive addition; the prompt explicitly excludes structural headings as new facts.',
        '280': 'Two qualifications present in both sides are concatenated and called an unsupported addition; source annotation markers interrupt the literal substring but not its meaning.',
        '161': 'Changed uncertainty is treated as addition; original unknown status was replaced, not retained.',
        '276': 'Old wording of a changed question is falsely called an addition; reversing orientation still yields DIVERGENCE.',
        '281': 'Old wording of a changed status is falsely called an addition; reversing orientation still yields DIVERGENCE.',
    }
    failures = []
    for saved in final:
        m = saved['metrics']
        if m['accepted_outcome']:
            continue
        row = by[saved['example_id']]
        num = row['example_id'][-3:]
        got = json.loads(saved['raw_output'])['items'][0]
        gold = r.target(row)['items'][0]
        source = '\n'.join(s['text'] for s in row['input']['source_spans'])
        quotes = re.findall(r'"([^\"]+)"', got['reasoning'])
        orient = ('complete_reversed_comparison' if num in reversed_complete else
                  'partial_reversed_omission' if num in reversed_partial else
                  'reversed_replacement_reason' if num in reversal_reason_only else 'not_explained_by_orientation')
        note = special.get(num, 'Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.')
        if num in reversed_complete:
            note = 'Identifies exactly the missing source content, but calls it an unsupported extraction addition. Both label and directional reason reverse the comparison.'
        if num in reversed_partial:
            note = 'Calls one omitted qualification an addition; two qualifications were omitted. Reversal-compatible fragment, but not a complete account even after reversal.'
        failures.append(dict(id=row['example_id'], expected=m['expected_relation'], predicted=m['predicted_relation'],
            evidence_refs=got['ref_ids'], expected_refs=gold['ref_ids'], expected_reason=gold['reasoning'], generated_reason=got['reasoning'],
            source_spans=row['input']['source_spans'], extraction=row['input']['extraction'],
            evidence_selection_correct=m['evidence']['fp'] == m['evidence']['fn'] == 0,
            refusal_status_correct=m['refusal_correct'], only_relation_label_wrong=False,
            relation_and_reason_wrong=not m['relation_correct'], reason_supports_expected=m['relation_correct'],
            reason_fully_correct_for_expected=False,
            reason_rhetorically_supports_predicted=True, reason_source_grounded_for_predicted=False,
            merely_label_token_mapping=False, taxonomy='C' if m['relation_correct'] else 'B',
            orientation=orient, note=note, saved_reason_correct=m['reason_correct'],
            catastrophe=m['catastrophic']['confident_wrong_match_divergence'],
            quoted_content_membership=[dict(text=q, in_source=q in source, in_extraction=q in row['input']['extraction']) for q in quotes]))
    assert len(failures) == 32
    assert Counter(x['taxonomy'] for x in failures) == {'B': 31, 'C': 1}
    assert all(x['evidence_selection_correct'] and x['refusal_status_correct'] for x in failures)
    assert {x['id'][-3:] for x in failures if x['catastrophe']} == {'058', '138', '142', '147'}
    prefix_counts = Counter()
    for saved in final:
        expected = 'refusal' if saved['metrics']['predicted_refusal'] else 'nonempty'
        for n in range(1, 17):
            prefix = tok.decode(saved['output_token_ids'][:n], skip_special_tokens=True)
            found = 'refusal' if prefix == '{"items":[],"status":"refused"}' else 'nonempty' if prefix.startswith('{"items":[{') else None
            if found:
                assert found == expected
                if found == 'refusal':
                    assert saved['output_token_ids'][n] in read(DATA/'evaluation_protocol.json')['generation_kwargs']['eos_token_id']
                    n += 1
                prefix_counts[f'{found}_{n}_tokens'] += 1
                break
        else:
            raise AssertionError('Saved branch exceeds proposed prefix cap')

    features = []
    for row in rows:
        obj = r.target(row)
        answer = r.old.canonical(obj).decode()
        messages = r.task_messages(row)
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        full = tok.apply_chat_template(messages + [dict(role='assistant', content=answer)], tokenize=False, add_generation_prompt=False)
        encoded = r.encode(row, tok)
        offsets = tok(full, add_special_tokens=False, return_offsets_mapping=True)
        assert offsets['input_ids'] == encoded['input_ids']
        a = len(prompt)
        categories = []
        for key, category in [('finding', 'relation'), ('reasoning', 'reason'), ('ref_ids', 'evidence')]:
            pattern = r'"' + key + r'":(\[[^\]]*\]|"(?:\\.|[^"\\])*")'
            match = re.search(pattern, answer)
            if match:
                left, right = match.span(1)
                if category in ('relation', 'reason'):
                    left += 1
                    right -= 1
                categories.append((a + left, a + right, category))
        counts = Counter()
        relation_positions = []
        for pos, (token, (left, right)) in enumerate(zip(offsets['input_ids'][encoded['prompt_length']:], offsets['offset_mapping'][encoded['prompt_length']:])):
            if token in tok.all_special_ids:
                category = 'termination'
            else:
                overlaps = [(max(0, min(right, hi) - max(left, lo)), cat) for lo, hi, cat in categories]
                overlap, category = max(overlaps, default=(0, 'structure'))
                if not overlap:
                    category = 'structure'
            counts[category] += 1
            if category == 'relation':
                relation_positions.append(pos)
        assert sum(counts.values()) == encoded['target_length']
        item = obj['items'][0] if obj['items'] else {}
        ext = row['input']['extraction']
        source = '\n'.join(s['text'] for s in row['input']['source_spans'])
        features.append(dict(id=row['example_id'], split='TRAIN' if row['example_id'] in split['train'] else 'DEV', relation=row['relation'],
            target_tokens=encoded['target_length'], prompt_tokens=encoded['prompt_length'],
            reason_characters=len(item.get('reasoning', '')), reason_words=len(item.get('reasoning', '').split()),
            refs=len(item.get('ref_ids', [])), required_refs=len(row['input']['required_refs']), source_spans=len(row['input']['source_spans']),
            template_family=row['template_family'], rendering_template=row['rendering_template'], structure=row['semantic_signature']['structure'],
            transformation=row['reason_difficulty'], domain=row['domain'], id_mod5=int(row['example_id'][-3:]) % 5,
            first_ref_mod20=int(row['input']['required_refs'][0].split('-')[1]) % 20 if row['input']['required_refs'] else None,
            delivery_complete=row['input']['delivery_complete'], status=obj.get('status', 'absent'),
            target_prefix=answer[:55], relation_token_positions=relation_positions, token_categories=dict(counts),
            extraction_characters=len(ext), source_characters=len(source), extraction_source_length_ratio=len(ext)/len(source),
            lexical_markers={term: term.lower() in ext.lower() for term in ['supervisor', 'independent inspector', 'witness', 'approved', 'verified', 'missing', 'unknown', 'uncertain', 'referred to', 'date or entry']},
            exact_required_refs=item.get('ref_ids', []) == row['input']['required_refs']))
    summaries = {}
    assert all(f['id_mod5'] == CLASSES.index(f['relation']) for f in features)
    visible_refs = [f for f in features if f['first_ref_mod20'] is not None]
    assert len(visible_refs) == 288 and all(f['first_ref_mod20'] == 4*CLASSES.index(f['relation']) for f in visible_refs)
    assert all(f['exact_required_refs'] for f in features if f['relation'] != 'INSUFFICIENT_EVIDENCE')
    numeric = ['target_tokens', 'prompt_tokens', 'reason_characters', 'reason_words', 'refs', 'required_refs', 'source_spans', 'extraction_characters', 'source_characters', 'extraction_source_length_ratio']
    categorical = ['template_family', 'rendering_template', 'structure', 'transformation', 'domain', 'id_mod5', 'first_ref_mod20', 'delivery_complete', 'status', 'target_prefix']
    for split_name in ('TRAIN', 'DEV'):
        summaries[split_name] = {}
        for c in CLASSES:
            group = [f for f in features if f['split'] == split_name and f['relation'] == c]
            summaries[split_name][c] = dict(count=len(group), numeric={k: dist(f[k] for f in group) for k in numeric},
                categorical={k: dict(Counter(str(f[k]) for f in group)) for k in categorical},
                markers={k: sum(f['lexical_markers'][k] for f in group) for k in group[0]['lexical_markers']},
                token_categories={k: sum(f['token_categories'].get(k, 0) for f in group) for k in ['relation', 'reason', 'evidence', 'structure', 'termination']},
                relation_positions=sorted({tuple(f['relation_token_positions']) for f in group}))
    objective = {}
    for name in ('TRAIN', 'DEV'):
        group = [f for f in features if f['split'] == name]
        total = sum(f['target_tokens'] for f in group)
        counts = {k: sum(f['token_categories'].get(k, 0) for f in group) for k in ['relation', 'reason', 'evidence', 'structure', 'termination']}
        objective[name] = dict(target_tokens=total, counts=counts, pooled_shares={k: v/total for k, v in counts.items()},
            mean_example_shares={k: statistics.mean(f['token_categories'].get(k, 0)/f['target_tokens'] for f in group) for k in counts})
    training = [json.loads(line) for line in (BASE / 'downloaded/evidence/training.jsonl').read_text().splitlines()]
    trajectory = {}
    for lo, hi in [(1, 10), (51, 60), (61, 70), (111, 120)]:
        group = [x for x in training if lo <= x['step'] <= hi]
        trajectory[f'{lo}-{hi}'] = dict(mean_loss=statistics.mean(x['loss'] for x in group), minimum=min(x['loss'] for x in group), maximum=max(x['loss'] for x in group))
    plan = read(DATA/'execution_plan.json')
    order = {str(step): dict(Counter(by[i]['relation'] for u in plan['optimizer_schedule'] if step-9 <= u['step'] <= step for i in u['example_ids'])) for step in (10, 60, 70, 120)}
    lexical = {}
    for split_name, ids in [('TRAIN', split['train']), ('DEV', split['validation'])]:
        documents = {c: Counter() for c in CLASSES}
        for row in rows:
            if row['example_id'] in ids:
                text = re.sub(r'REF-\d+', '', row['input']['extraction'])
                documents[row['relation']].update(set(re.findall(r'[a-z]+', text.lower())))
        lexical[split_name] = {c: {w:n for w,n in sorted(documents[c].items()) if n >= 3 and not any(documents[other][w] for other in CLASSES if other != c)} for c in CLASSES}
    relation_corrected = []
    reason_corrected = []
    for saved in final:
        m = saved['metrics']; obj = json.loads(saved['raw_output']); gold = r.target(by[saved['example_id']])
        other_ok = m['contract_valid'] and m['refusal_correct'] and m['evidence']['fp'] == m['evidence']['fn'] == 0
        same_reason = obj == gold if m['expected_refusal'] else obj['items'][0]['reasoning'] == gold['items'][0]['reasoning']
        # Algebraic counterfactual using the unchanged acceptance predicate;
        # saved objects and historical metrics are never modified or rescored.
        if other_ok and same_reason:
            relation_corrected.append(saved['example_id'])
        if other_ok and m['relation_correct']:
            reason_corrected.append(saved['example_id'])
    assert len(relation_corrected) == 28 and len(reason_corrected) == 29
    result = dict(historical_text_hashes_verified=len(manifest['text_files']), confusion=evidence, failures=failures,
        decomposition=dict(A=0, B=31, C=1, D=0, E=0),
        orientation=dict(label_swap_compatible=10, fully_reversed_wrong_labels=5, partially_reversed_wrong_labels=2,
                         wrong_labels_not_fully_explained_by_reversal=26, reversed_reason_only=1),
        counterfactual=dict(current=sum(x['metrics']['accepted_outcome'] for x in final), relation_only_frozen_acceptance=len(relation_corrected),
            reason_only_perfect_correction=len(reason_corrected), perfect_relation_existing_reason_evidence=len(relation_corrected),
            relation_corrected_ids=relation_corrected, reason_corrected_ids=reason_corrected),
        features=features, dataset_summary=summaries, exclusive_lexical_markers=lexical, objective=objective, trajectory=trajectory, training_class_windows=order,
        saved_prefix_feasibility=dict(prefix_counts),
        source_hashes={str(p.relative_to(ROOT)): sha(p) for p in [DATA/'dataset.json', DATA/'split.json', DATA/'execution_plan.json', ROOT/'tuning/second_domain_agnostic_v2/runtime.py', ROOT/'tools/auditor_canonical_remote.py']})
    OUT.mkdir(exist_ok=True)
    (OUT/'diagnosis.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf8')
    append_report(result)
    print(json.dumps({k: result[k] for k in ('decomposition', 'orientation', 'counterfactual', 'objective', 'trajectory')}, indent=2))


if __name__ == '__main__':
    main()
