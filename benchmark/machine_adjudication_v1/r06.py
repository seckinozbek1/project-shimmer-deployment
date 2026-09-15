"""Maintained R06 population adapter; frozen numeric profile stays unchanged.

The registered first-experiment evaluation population expressly includes selected
DEV/TEST/public-adversarial material, excluding TRAIN. Apply that same population
to family sample counts AND observations. DEV is labelled development-inclusive,
not an independently blind final generalization claim.
"""
from collections import defaultdict


def non_train(row):
    return row['split'] in ('dev', 'test', 'sealed_adversarial')


def family_metric(scores, metadata, eligible_ids, minimum=4, threshold=.80):
    index = {r['example_id']: r for r in metadata}
    eligible = set(eligible_ids)
    if not eligible <= set(index):
        raise ValueError('Unknown eligible evaluation ID')
    population = {i for i in eligible if non_train(index[i])}
    groups = defaultdict(set)
    for i in population:
        groups[index[i]['document_family']].add(i)
    observed = {}
    for score in scores:
        ident = score.get('example_id')
        if ident not in index:
            raise ValueError('Unknown saved-output ID')
        if not non_train(index[ident]):
            continue  # TRAIN cannot affect samples, outcomes, completeness or R06.
        if ident not in population or ident in observed:
            raise ValueError('Out-of-population or duplicate evaluation output')
        if type(score.get('accepted_outcome')) is not bool:
            raise ValueError('A measured accepted-outcome boolean is required')
        observed[ident] = score['accepted_outcome']
    families = {}
    for family, ids in sorted(groups.items()):
        if len(ids) < minimum:
            families[family] = dict(status='insufficient_sample_for_family_gate', sample=len(ids))
        elif not ids <= set(observed):
            families[family] = dict(status='INSUFFICIENT_MEASUREMENT', sample=len(ids))
        else:
            families[family] = dict(status='measured', sample=len(ids), rate=sum(observed[i] for i in ids)/len(ids))
    rates = [v['rate'] for v in families.values() if v['status']=='measured']
    complete = population == set(observed) and bool(population)
    measured = min(rates) if complete and rates else None
    return dict(population=sorted(population), population_scope='registered non-TRAIN DEV/TEST/public-adversarial; development-inclusive',
                families=families, measurement_complete=complete, measured=measured,
                passed=None if measured is None else measured>=threshold,
                minimum_sample=minimum, threshold=threshold, training_predictions_used=False)


def evaluate_registered(scores, metadata, eligible_ids, acceptance):
    criterion = next(r for r in acceptance['criteria'] if r['id']=='R06')
    if criterion['operator']!='>=':
        raise ValueError('Unsupported frozen R06 operator')
    return family_metric(scores, metadata, eligible_ids,
            acceptance['sufficiently_sampled_family']['minimum_independently_reviewed_examples'], criterion['value'])
