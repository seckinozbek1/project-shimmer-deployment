"""Build reviewed selection artifacts; no journal submissions or model execution."""
from pathlib import Path
import json
import zipfile
import cohort as c


def main():
    c.old.verify_frozen()
    if (c.HERE/'freeze.json').exists():
        c.verify_frozen()
    rows = c.old.records()
    index = {r['example_id']: r for r in rows}
    first, second, parts = c.selection(rows)
    composition = lambda ids: c.old.composition([index[i] for i in ids])
    c.write(c.HERE/'cohort.json', dict(revision=c.REVISION, profile=c.PROFILE, ids=first,
            access_categories=parts, composition=composition(first), category_composition={k:composition(v) for k,v in parts.items()}))
    c.write(c.HERE/'double_review.json', dict(revision=c.REVISION, ids=second, composition=composition(second)))
    eligible_families = {r['document_family'] for r in rows if r['split'] in ('train','dev') or c.is_held(r)}
    selected_families = set(composition(first)['document_family'])
    c.write(c.HERE/'selection_metadata.json', dict(revision=c.REVISION, seed=c.SEED, algorithm=c.choose.__doc__,
            approved_allocation=dict(train=78, dev=40, held_out=72, additional_evaluation=2),
            missing_without_additional_evaluation=['attributed_dialogue','scope_notice'],
            max_families_under_allocation=len(eligible_families)+2, selected_families=len(selected_families),
            family_upper_bound_proof='20 TRAIN + 20 DEV + 12 mandatory held-out families + at most one family per extra evaluation row = 54.',
            dropped_families=sorted({r['document_family'] for r in rows}-selected_families),
            dropped_reason='Non-held-out TEST/public-adversarial families outside the two authorized additional evaluation slots.',
            producer_policy='All 48 TRAIN/DEV producers are substantive extraction; mandatory held-out empty/refusal rows retained.',
            double_policy='At least four refusal cases per role, twelve gaps and twelve uncertainty cases, then maximum family diversity and difficult source proxies.',
            acceptance_sha256=c.digest((c.old.HERE/'acceptance_registration.json').read_bytes())))
    c.write(c.HERE/'evaluation_population.json', dict(revision=c.REVISION, ids=[i for i in first if index[i]['split']!='train'],
            note='114 selected non-TRAIN evaluation rows: 40 DEV, 72 held-out, two additional evaluation. No criterion changed.'))
    exports = {}
    for slot, ids in [(1, first),(2, second)]:
        name = f'reviewer_{slot}_first_tuning_v1_cohort_v2'
        folder = c.HERE/name
        folder.mkdir(exist_ok=True)
        files = c.export_files(ids)
        if any(p.name not in files for p in folder.iterdir()):
            raise ValueError('Unapproved existing export content')
        for filename, raw in files.items():
            (folder/filename).write_bytes(raw)
        c.audit_export(folder, ids)
        with zipfile.ZipFile(c.HERE/(name+'.zip'), 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for filename, raw in sorted(files.items()):
                info = zipfile.ZipInfo(filename,(1980,1,1,0,0,0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                z.writestr(info,raw)
        exports[name] = dict(slot=slot, ids=ids, packet_ids=[c.h.packet(index[i])['packet_id'] for i in ids],
                            binding=c.export_binding(ids), files={name:c.digest(raw) for name,raw in files.items()},
                            archive_sha256=c.digest((c.HERE/(name+'.zip')).read_bytes()),
                            archive_bytes=(c.HERE/(name+'.zip')).stat().st_size)
    c.write(c.HERE/'export_admin_manifest.json', exports)
    c.write(c.HERE/'resolution_envelope.template.json',dict(binding=dict(revision=c.REVISION,
            cohort_sha256=c.cohort_hash(),exports_sha256=c.digest((c.HERE/'export_admin_manifest.json').read_bytes())),
            packet_id=None,resolution={}))
    old_exports = c.read(c.old.HERE/'export_admin_manifest.json')
    c.write(c.HERE/'supersession.json', dict(status='SUPERSEDED_BEFORE_HUMAN_REVIEW',
            previous_cohort_sha256=c.digest((c.old.HERE/'cohort.json').read_bytes()),
            previous_exports={name:m['archive_sha256'] for name,m in old_exports.items()},
            replacement_revision=c.REVISION, replacement_cohort_sha256=c.cohort_hash(),
            human_reviews_started=False, human_work_discarded=False,
            old_artifacts_preserved=True, old_submissions_accepted=False,
            instruction='Distribute only cohort-v2 ZIPs. Legacy entry points are historical, not the active review workflow.'))
    c.write(c.HERE/'reviewer_registry.template.json',c.read(c.old.HERE/'reviewer_registry.template.json'))
    c.write(c.HERE/'training_access_template.json',dict(revision=c.REVISION,allowed_ids=[],
            candidate_train_ids=parts['train'],candidate_dev_ids=parts['dev'],
            excluded_evaluation_ids=parts['held_out']+parts['additional_evaluation'],
            maximum_train=78,maximum_dev=40,maximum_total=118,training_authorized=False,
            dev_usage='Validation/tuning decisions; do not merge automatically into gradient training.',
            required='Actual accepted independent labels; no authored-only or unbound labels.'))
    c.write(c.HERE/'readiness.json',dict(status='FIRST_TUNING_EXPERIMENT_REVIEW_PENDING',
            revision=c.REVISION, first_reviews=0,second_reviews=0,eligible_training=0,
            final_model_acceptance_ready=False,training_authorized=False))
    files=[p for p in c.HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='freeze.json']
    c.write(c.HERE/'freeze.json',dict(revision=c.REVISION,profile=c.PROFILE,
            acceptance_sha256=c.digest((c.old.HERE/'acceptance_registration.json').read_bytes()),
            hashes={p.relative_to(c.HERE).as_posix():c.digest(p.read_bytes()) for p in sorted(files)}))
    c.write(c.ROOT/'benchmark/first_tuning_review_active.json',dict(revision=c.REVISION,
            directory=c.HERE.relative_to(c.ROOT).as_posix(),freeze_sha256=c.digest((c.HERE/'freeze.json').read_bytes()),
            supersession='SUPERSEDED_BEFORE_HUMAN_REVIEW',previous_revision='first-tuning-experiment-v1'))
    print(json.dumps(dict(first=composition(first),second=composition(second))))


if __name__ == '__main__':
    main()
