"""Post-authorization diagnostics using the already frozen V3 semantics only."""
from collections import Counter
from datetime import datetime, timezone
import json

import access_guard

DIMENSIONS = ('claims', 'evidence', 'refusal', 'typed_gaps', 'typed_uncertainty')


def require_post():
    guard = access_guard._default()
    if not guard.installed or not guard.authorized:
        raise PermissionError('Installed, authorized V3 guard required before post-phase reads')
    return guard.verify_post_phase()


def atoms_for(label, key):
    return [atom for item in label['items'] for atom in item[key]]


def fields(target, key):
    return sorted((item.get('span', ''), value) for item in target['items'] for value in item.get(key, []))


def source_settles_extra(atom, packet, semantics, projection):
    text = next(span['text'] for span in packet['source_spans'] if span['alias'] == atom['span'])
    try:
        semantics.ground(atom, text, atom['refs'])
        projected = projection.project(atom['support'], atom['kind'], atom['span'], atom['refs'], text)
        return semantics.normalize(projected) == semantics.normalize(atom)
    except (ValueError, KeyError):
        return False


def run():
    binding = require_post()
    import semantics as s
    import review_flow as flow
    import legacy_projection as projection
    flow.verify_freeze()
    flow.policy_intact()
    out = s.HERE / 'post_freeze'
    if (out / 'legacy_comparison.json').exists() or (out / 'GOLD_COMPARISON_STARTED.json').exists():
        raise ValueError('Never overwrite post-freeze comparison')
    audit = s.read(s.HERE / 'blind_evidence/PRE_GOLD_ACCESS_AUDIT.json')
    successful = audit.get('successful_target_reads')
    governance = (audit.get('governance_pass') is True
                  and audit.get('strict_target_access_order_pass') is True
                  and successful in (0, [])
                  and audit.get('reviewer_target_exposure_detected') is False)
    s.write(out / 'GOLD_COMPARISON_STARTED.json', dict(
        started_at=datetime.now(timezone.utc).isoformat(), pre_gold_commit=binding['commit'],
        freeze_sha256=binding['manifest_sha256'], evidence_kind='training_label_curation_evidence', use='curation_only'))
    authored = s.read(s.ROOT / 'benchmark/task_semantics/seed.json') + s.read(s.ROOT / 'benchmark/task_semantics_v2/extension.json')
    index = {row['example_id']: row for row in authored}
    labels = s.read(s.HERE / 'blind_evidence/labels.json')
    canonical = s.read(s.HERE / 'blind_evidence/canonical_targets.json')
    population = s.read(s.HERE / 'population.json')
    packets = flow.packets()
    comparisons, excluded = {}, []
    candidates = {'train': [], 'dev': []}
    counts = Counter()
    for row in population['rows']:
        pid = row['packet_id']
        entry = labels[pid]
        label = entry['review']['label']
        wire = canonical[pid]
        gold = index[row['example_id']]['gold_target']
        packet = packets[pid]['input']
        spans = {span['alias']: span['text'] for span in packet['source_spans']}
        gaps, uncertainties, errors = [], [], []
        for item in gold['items']:
            for key, kind, destination in [('questions', 'gap', gaps), ('uncertainty', 'uncertainty', uncertainties)]:
                for wording in item[key]:
                    try:
                        destination.append(projection.project(wording, kind, item['span'], item['refs'], spans[item['span']]))
                    except (ValueError, KeyError) as exc:
                        errors.append(dict(field=key, span=item['span'], wording=wording, reason=str(exc)))
        machine_gaps = atoms_for(label, 'gap_atoms')
        machine_uncertainties = atoms_for(label, 'uncertainty_atoms')
        primary_valid = set(entry['primary_valid']) == set('ABC') and all(entry['primary_valid'].values())
        validated_final = False
        try:
            validated_final = s.validate_label(label, packet) == wire and entry['valid'] is True
        except ValueError:
            pass
        result = dict(example_id=row['example_id'], packet_id=pid,
                      claims=fields(wire, 'claims') == fields(gold, 'claims'),
                      evidence=fields(wire, 'refs') == fields(gold, 'refs'),
                      refusal=(wire.get('status') == 'refused') == (gold.get('status') == 'refused'),
                      typed_gaps=not any(e['field'] == 'questions' for e in errors) and s.material_atoms(machine_gaps) == s.material_atoms(gaps),
                      typed_uncertainty=not any(e['field'] == 'uncertainty' for e in errors) and s.material_atoms(machine_uncertainties) == s.material_atoms(uncertainties),
                      canonical_output_difference=wire != gold, legacy_projection_errors=errors,
                      legacy_target=gold, machine_canonical_target=wire, typed_machine_label=label)
        if all(result[key] for key in DIMENSIONS):
            classification, resolved = 'semantic_agreement', True
        elif errors:
            classification, resolved = 'legacy_projection_limitation', False
        elif not all(result[key] for key in ('claims', 'evidence', 'refusal')):
            classification, resolved = 'real_semantic_disagreement', False
        else:
            legacy_set = set(s.material_atoms(gaps + uncertainties))
            machine_set = set(s.material_atoms(machine_gaps + machine_uncertainties))
            extras = [atom for atom in machine_gaps + machine_uncertainties
                      if json.dumps(s.normalize(atom), sort_keys=True) not in legacy_set]
            supported_subset = (legacy_set < machine_set and bool(extras) and primary_valid and validated_final
                                and all(source_settles_extra(atom, packet, s, projection) for atom in extras))
            classification, resolved = ('legacy_authored_target_under_specification', True) if supported_subset else ('real_semantic_disagreement', False)
        reasons = []
        if not primary_valid:
            reasons.append('invalid_primary')
        if not validated_final:
            reasons.append('invalid_final_review')
        if label['review_ambiguity']:
            reasons.append('review_ambiguity')
        if not resolved:
            reasons.append('unresolved_legacy_diagnostic')
        if row['split'] not in candidates or not s.eligible_metadata(row):
            reasons.append('evaluation_access')
        if not governance:
            reasons.append('pre_gold_access_governance_failure')
        result.update(classification=classification, material_dispute_resolved=resolved, eligible=not reasons,
                      evidence_kind='training_label_curation_evidence', use='curation_only',
                      classification_basis='Frozen typed projection; exact claims/evidence/refusal; strict legacy subset requires three valid primaries and source-supported validated extras.')
        if reasons:
            excluded.append(dict(example_id=row['example_id'], packet_id=pid, split=row['split'], reasons=reasons))
        else:
            candidates[row['split']].append(dict(
                example_id=row['example_id'], packet_id=pid, split=row['split'], role='producer',
                domain=row['domain'], template_family=row['template_family'], document_family=row['document_family'],
                provenance='machine_adjudicated_producer_candidate_v3', evidence_kind='training_label_curation_evidence',
                use='curation_only', human_reviewed=False, training_authorized=False,
                policy=s.POLICY, renderer=s.RENDERER, input=packet, input_sha256=packets[pid]['input_sha256'],
                typed_label=label, canonical_target=wire))
        comparisons[pid] = result
        counts.update({key: int(result[key]) for key in DIMENSIONS})
        counts[classification] += 1
        counts['unresolved'] += int(not resolved)
    require_post()
    s.write(out / 'legacy_comparison.json', comparisons)
    s.write(out / 'excluded_candidates.json', excluded)
    access = out / 'machine_adjudicated_producer_candidates_v3'
    for split, rows in candidates.items():
        s.write(access / (split + '.json'), rows)
    s.write(access / 'manifest.json', dict(
        policy=s.POLICY, protocol=s.PROTOCOL, human_reviewed=False, training_authorized=False,
        provenance='machine_adjudicated_producer_candidate_v3', evidence_kind='training_label_curation_evidence',
        use='curation_only', train=len(candidates['train']), dev=len(candidates['dev']),
        allowed_ids=[row['example_id'] for rows in candidates.values() for row in rows],
        files={name: s.digest((access / name).read_bytes()) for name in ('train.json', 'dev.json')}, evaluation_data_included=False))
    summary = dict(total=len(comparisons), governance_pass=governance, legacy=dict(counts),
                   candidates={split: len(rows) for split, rows in candidates.items()},
                   evidence_kind='training_label_curation_evidence', use='curation_only', human_reviewed=False,
                   independent_generalization_evidence=False, blind_final_evaluation=False, training_authorized=False)
    s.write(out / 'legacy_summary.json', summary)
    return summary


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
