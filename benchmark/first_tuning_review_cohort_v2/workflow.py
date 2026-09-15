"""Bound envelopes around the unchanged v2 human submission journal.

The native journal stays compatible with v2. An independent envelope receipt
binds each native submission to this export and its exact bytes. Partial writes
or use of the legacy CLI fail closed at coverage, never yielding training labels.
"""
from pathlib import Path
import json
import cohort as c


def protect_journal(journal):
    journal = Path(journal).resolve()
    if journal.is_relative_to((c.ROOT/'benchmark').resolve()):
        raise ValueError('Use a separate administrative journal outside benchmark exports')
    return journal


def assert_human(identity, registry):
    person = registry.get('reviewers', {}).get(identity, {})
    if (person.get('human') is not True or person.get('operator_verified') is not True or
        person.get('independent_of_authorship') is not True or person.get('is_operator') is not False):
        raise ValueError('Operator-verified independent human required')


def bound_state(journal):
    """Validate every persisted response and final receipt before any coverage."""
    journal = protect_journal(journal)
    exports = c.manifests()[2]
    state = {}
    if not journal.exists():
        return state
    top = {p.name for p in journal.iterdir()}
    if not top <= {'native', 'receipts', 'resolutions'}:
        raise ValueError('Obsolete/unbound journal layout')
    native = journal/'native'
    receipts = journal/'receipts'
    submissions = list(native.glob('*-submission-*.json'))
    expected_receipts = set()
    for path in submissions:
        receipt = receipts/path.name
        if not receipt.is_file():
            raise ValueError('Unbound native submission; legacy import rejected')
        envelope = c.read(receipt)
        name = c.check_binding(envelope, exports)
        review = c.read(path)
        if envelope['review'] != review:
            raise ValueError('Submission receipt mismatch')
        ident = review['packet_id']
        expected_name = ident+'-submission-'+c.digest(review['reviewer_id'])[:20]+'.json'
        if path.name != expected_name:
            raise ValueError('Native submission filename mismatch')
        slots = state.setdefault(ident, {})
        if name in slots:
            raise ValueError('Repeated export slot cannot substitute for independent double review')
        slots[name] = envelope
        expected_receipts.add(path.name)
    if {p.name for p in receipts.glob('*')} != expected_receipts:
        raise ValueError('Orphaned submission receipt')
    expected_resolutions = set()
    for path in native.glob('*-final.json'):
        final = c.read(path)
        ident = path.name[:-len('-final.json')]
        if ident not in state or len(state[ident]) != 2:
            raise ValueError('Final without two bound independent export slots')
        if sorted(final.get('submission_hashes', [])) != sorted(c.digest(e['review']) for e in state[ident].values()):
            raise ValueError('Final submission hashes differ')
        if final.get('resolution') is not None:
            receipt = journal/'resolutions'/path.name
            envelope = c.read(receipt)
            check_resolution_binding(envelope, ident)
            if envelope['resolution'] != final['resolution']:
                raise ValueError('Resolution receipt mismatch')
            expected_resolutions.add(path.name)
    if {p.name for p in (journal/'resolutions').glob('*')} != expected_resolutions:
        raise ValueError('Orphaned resolution receipt')
    known = {p.name for p in submissions} | {p.name for p in native.glob('*-final.json')}
    if {p.name for p in native.glob('*')} != known:
        raise ValueError('Unknown native journal artifact')
    return state


def append_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)


def ingest(envelope, journal, registry):
    c.verify_frozen()
    name = c.check_binding(envelope)
    journal = protect_journal(journal)
    state = bound_state(journal)
    review = envelope['review']
    assert_human(review.get('reviewer_id'), registry)
    ident = review['packet_id']
    slots = state.get(ident, {})
    if name in slots:
        raise ValueError('Export slot already submitted')
    rows = c.old.records()
    row = next(r for r in rows if c.h.packet(r)['packet_id'] == ident)
    # Validate before the unchanged journal mutates; malformed labels cannot count.
    c.h.adjudication_state(row, [e['review'] for e in slots.values()] + [review])
    if not c.h.baseline.classify(row, json.dumps(review.get('semantic_target')))[1]:
        raise ValueError('Invalid reviewed target')
    result = c.h.ingest_review(review, rows, journal/'native')
    filename = ident+'-submission-'+c.digest(review['reviewer_id'])[:20]+'.json'
    append_json(journal/'receipts'/filename, envelope)
    bound_state(journal)
    return result


def resolution_binding():
    return dict(revision=c.REVISION, cohort_sha256=c.cohort_hash(),
                exports_sha256=c.digest((c.HERE/'export_admin_manifest.json').read_bytes()))


def check_resolution_binding(envelope, ident):
    if (not isinstance(envelope, dict) or set(envelope) != {'binding', 'packet_id', 'resolution'} or
        envelope['binding'] != resolution_binding() or envelope['packet_id'] != ident):
        raise ValueError('Obsolete or unbound resolution')


def resolve(envelope, journal, registry):
    c.verify_frozen()
    ident = envelope.get('packet_id')
    check_resolution_binding(envelope, ident)
    journal = protect_journal(journal)
    state = bound_state(journal)
    if len(state.get(ident, {})) != 2:
        raise ValueError('Two bound independent export slots required')
    resolution = envelope['resolution']
    assert_human(resolution.get('adjudicator_id'), registry)
    result = c.h.resolve_review(ident, c.old.records(), journal/'native', resolution)
    append_json(journal/'resolutions'/(ident+'-final.json'), envelope)
    bound_state(journal)
    return result


def coverage(journal, registry):
    c.verify_frozen()
    journal = protect_journal(journal)
    state = bound_state(journal)
    first, second, exports = c.manifests()
    rows = c.old.records()
    result = c.old.review_coverage(rows, first['ids'], second['ids'], journal/'native', registry)
    first_name = next(n for n, m in exports.items() if m['slot'] == 1)
    # A second-slot return alone is not a first review, including matching packet IDs.
    without_first = {i for i in first['ids'] if first_name not in state.get(c.h.packet(next(r for r in rows if r['example_id'] == i))['packet_id'], {})}
    for ident in without_first:
        result['accepted_targets'].pop(ident, None)
    if without_first:
        result['status'] = 'FIRST_TUNING_EXPERIMENT_REVIEW_PENDING'
    result['first_reviews_valid'] = sum(first_name in slots for slots in state.values()) if not result['invalid_review_examples'] else 0
    result['reviewed_accepted'] = len(result['accepted_targets'])
    result['cohort_revision'] = c.REVISION
    result['cohort_sha256'] = c.cohort_hash()
    return result


def export_training(coverage, destination):
    protect_journal(destination)
    rows = c.training_candidates(c.old.records(), coverage['accepted_targets'])
    # Frozen helper preserves separate TRAIN/DEV files and reviewed targets only.
    result = c.old.export_training_labels(rows, coverage, destination)
    result['cohort_revision'] = c.REVISION
    result['cohort_sha256'] = c.cohort_hash()
    result['dev_usage'] = 'Validation and tuning decisions; not automatic gradient-training input.'
    c.write(Path(destination)/'manifest.json', result)
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['submit', 'resolve', 'status'])
    parser.add_argument('--response', type=Path)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--reviewers', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    registry = c.read(args.reviewers)
    if args.action in ('submit', 'resolve'):
        if not args.response:
            parser.error('--response required')
        value = c.h.baseline.strict_json(args.response.read_text(encoding='utf-8'))
        result = (ingest if args.action == 'submit' else resolve)(value, args.journal, registry)
    else:
        if not args.out:
            parser.error('--out required')
        protect_journal(args.out)
        if args.out.resolve().is_relative_to(args.journal.resolve()):
            parser.error('Status output must be separate from the immutable journal')
        if args.out.exists() and any(args.out.iterdir()):
            parser.error('Use a fresh empty status directory; never reuse stale labels after a failed refresh')
        result = coverage(args.journal, registry)
        c.write(args.out/'coverage.json', {k:v for k,v in result.items() if k != 'accepted_targets'})
        c.write(args.out/'admin_review_targets.json', result['accepted_targets'])
        manifest = export_training(result, args.out/'training_access')
        result = dict(status=result['status'], reviewed=result['reviewed_accepted'], eligible_training=len(manifest['allowed_ids']))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
