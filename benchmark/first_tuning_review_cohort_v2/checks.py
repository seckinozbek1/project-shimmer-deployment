"""Deterministic selection and boundary tests; no fake human submissions."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import cohort as c
import workflow as w

ROWS=c.old.records()
INDEX={r['example_id']:r for r in ROWS}
FIRST,SECOND,EXPORTS=c.manifests()
F=[INDEX[i] for i in FIRST['ids']]
S=[INDEX[i] for i in SECOND['ids']]


class Checks(unittest.TestCase):
    def test_frozen_inputs_acceptance_and_active_revision(self):
        self.assertTrue(c.verify_frozen())
        p=c.read(c.old.HERE/'acceptance_registration.json')
        self.assertEqual(p,c.old.profile());self.assertEqual(len(p['criteria']),27)
        self.assertEqual(p['derived_hard_gate']['id'],'R07')
        self.assertEqual(p['catastrophic_limits'],c.read(c.h.HERE/'acceptance_specification.json')['catastrophic_limits'])
        self.assertEqual(len(p['catastrophic_limits']),6)
        self.assertTrue(all(v==0 for v in p['catastrophic_limits'].values()))

    def test_reproducible_including_reversed_input(self):
        expected=(FIRST['ids'],SECOND['ids'],FIRST['access_categories'])
        self.assertEqual(c.selection(ROWS),expected)
        self.assertEqual(c.selection(list(reversed(ROWS))),expected)

    def test_exact_allocation_unique_disjoint(self):
        self.assertEqual(len(F),192);self.assertEqual(len(set(FIRST['ids'])),192)
        parts=FIRST['access_categories']
        self.assertEqual({k:len(v) for k,v in parts.items()},dict(train=78,dev=40,held_out=72,additional_evaluation=2))
        self.assertEqual(sorted(i for ids in parts.values() for i in ids),FIRST['ids'])
        for split in ('train','dev'):
            self.assertTrue(all(INDEX[i]['split']==split and not c.is_held(INDEX[i]) for i in parts[split]))

    def test_mandatory_held_out(self):
        self.assertEqual(set(FIRST['access_categories']['held_out']),{r['example_id'] for r in ROWS if c.is_held(r)})
        self.assertEqual(Counter(r['domain'] for r in F if c.is_held(r)),{'astronomy':36,'ecology':36})

    def test_additional_evaluation_exact_templates(self):
        extra=[INDEX[i] for i in FIRST['access_categories']['additional_evaluation']]
        self.assertEqual({(r['split'],r['template_family']) for r in extra},{('test','attributed_dialogue'),('sealed_adversarial','scope_notice')})

    def test_role_counts_each_access_category(self):
        self.assertEqual(Counter(r['role'] for r in F),{'producer':96,'auditor':96})
        for name,expected in [('train',(32,46)),('dev',(16,24)),('held_out',(48,24)),('additional_evaluation',(0,2))]:
            rs=[INDEX[i] for i in FIRST['access_categories'][name]]
            self.assertEqual((sum(r['role']=='producer' for r in rs),sum(r['role']=='auditor' for r in rs)),expected)

    def test_substantive_tuning_producers_only(self):
        producers=[r for r in F if r['split'] in ('train','dev') and r['role']=='producer']
        self.assertEqual(len(producers),48)
        self.assertTrue(all(r['abstract_relation']=='EXTRACTED' for r in producers))

    def test_template_domain_and_unseen_coverage(self):
        self.assertEqual(len({r['template_family'] for r in F}),16)
        self.assertEqual(len({r['domain'] for r in F}),10)
        self.assertEqual(sum(r['split'] in ('test','sealed_adversarial') for r in F),74)

    def test_family_maximum_mathematical_bound(self):
        eligible={r['document_family'] for r in ROWS if r['split'] in ('train','dev') or c.is_held(r)}
        self.assertEqual(len(eligible),52)
        self.assertEqual(len({r['document_family'] for r in F}),len(eligible)+2)
        meta=c.read(c.HERE/'selection_metadata.json')
        self.assertEqual(len(meta['dropped_families']),26)
        self.assertEqual(set(meta['dropped_families']),{r['document_family'] for r in ROWS}-{r['document_family'] for r in F})

    def test_first_semantic_coverage(self):
        stats=c.old.composition(F)
        self.assertGreaterEqual(stats['refusals'],12)
        self.assertEqual(stats['information_gaps'],72)
        self.assertEqual(stats['uncertainty'],60)
        self.assertEqual(set(stats['abstract_relation']),{'MATCH','DIVERGENCE','OMISSION','ADDITION','EXTRACTED','EMPTY','INSUFFICIENT_EVIDENCE'})

    def test_double_count_subset_balance(self):
        self.assertEqual(len(S),48);self.assertEqual(len(set(SECOND['ids'])),48)
        self.assertTrue(set(SECOND['ids'])<=set(FIRST['ids']))
        self.assertEqual(Counter(r['role'] for r in S),{'producer':24,'auditor':24})

    def test_double_hard_case_minima(self):
        stats=c.old.composition(S)
        self.assertGreaterEqual(stats['refusals'],8)
        self.assertGreaterEqual(stats['information_gaps'],12)
        self.assertGreaterEqual(stats['uncertainty'],12)
        self.assertTrue({'context_ownership','contradictory_source','evidence_selection','multi_span'}<=set(stats['features']))
        self.assertTrue({'MATCH','DIVERGENCE','OMISSION','ADDITION','EXTRACTED','INSUFFICIENT_EVIDENCE'}<=set(stats['abstract_relation']))

    def test_double_max_families_and_templates_domains(self):
        self.assertEqual(len({r['document_family'] for r in S}),48)
        self.assertEqual(len({r['template_family'] for r in S}),16)
        self.assertEqual(len({r['domain'] for r in S}),10)
        self.assertTrue(any(c.is_held(r) for r in S));self.assertTrue(any(r['split']=='train' for r in S));self.assertTrue(any(r['split']=='dev' for r in S))

    def test_supersession_explicit_hashes_preserved(self):
        m=c.read(c.HERE/'supersession.json')
        self.assertEqual(m['status'],'SUPERSEDED_BEFORE_HUMAN_REVIEW')
        self.assertFalse(m['human_reviews_started']);self.assertFalse(m['human_work_discarded'])
        for name,sha in m['previous_exports'].items():
            self.assertEqual(c.digest((c.old.HERE/(name+'.zip')).read_bytes()),sha)

    def test_exports_blank_exact_inputs_no_hidden_fields(self):
        for name,manifest in EXPORTS.items():
            c.audit_export(c.HERE/name,manifest['ids'])
            for ident in manifest['ids']:
                original=c.h.packet(INDEX[ident]);p=json.loads((c.HERE/name/(original['packet_id']+'.json')).read_text(encoding='utf-8'))
                self.assertEqual(p['input'],original['input'])
                self.assertEqual(p['response_template']['review'],original['response_template'])
                self.assertIsNone(p['response_template']['review']['semantic_target'])
                self.assertEqual(set(p),set(original))
                self.assertEqual(set(p['response_template']),{'binding','review'})

    def test_archives_exact_safe_members_and_hashes(self):
        for name,m in EXPORTS.items():
            expected=c.export_files(m['ids'])
            self.assertEqual(c.digest((c.HERE/(name+'.zip')).read_bytes()),m['archive_sha256'])
            with zipfile.ZipFile(c.HERE/(name+'.zip')) as z:
                self.assertEqual(len(z.namelist()),len(set(z.namelist())))
                self.assertEqual(set(z.namelist()),set(expected))
                for member in z.namelist():self.assertEqual(z.read(member),expected[member])

    def test_current_binding_passes_without_implying_human_review(self):
        for name,m in EXPORTS.items():
            envelope=c.packet(INDEX[m['ids'][0]],m['binding'])['response_template']
            self.assertEqual(c.check_binding(envelope),name)
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):w.ingest(envelope,folder,{'reviewers':{}})
                self.assertEqual(list(Path(folder).iterdir()),[])

    def test_legacy_packet_id_coincidence_rejected(self):
        previous=set(c.read(c.old.HERE/'cohort.json')['ids'])
        common=next(i for i in FIRST['ids'] if i in previous)
        with self.assertRaises(ValueError):c.check_binding(c.h.packet(INDEX[common])['response_template'])
        manifest=next(m for m in EXPORTS.values() if common in m['ids'])
        envelope=c.packet(INDEX[common],manifest['binding'])['response_template']
        for field,value in [('revision','first-tuning-experiment-v1'),('cohort_sha256','obsolete'),('payload_sha256','obsolete')]:
            altered=deepcopy(envelope);altered['binding'][field]=value
            with self.assertRaises(ValueError):c.check_binding(altered)

    def test_foreign_packet_assignment_rejected(self):
        m=next(m for m in EXPORTS.values() if m['slot']==2)
        ident=next(i for i in FIRST['ids'] if i not in m['ids'])
        envelope=c.packet(INDEX[ident],m['binding'])['response_template']
        with self.assertRaises(ValueError):c.check_binding(envelope)

    def test_old_journal_cannot_count(self):
        with tempfile.TemporaryDirectory() as folder:
            c.write(Path(folder)/'old-submission.json',{'packet_id':'blank-obsolete'})
            with self.assertRaises(ValueError):w.coverage(folder,{'reviewers':{}})

    def test_unreceipted_native_cannot_count(self):
        with tempfile.TemporaryDirectory() as folder:
            c.write(Path(folder)/'native'/'blank-submission-blank.json',{'packet_id':'blank-unbound'})
            with self.assertRaises(ValueError):w.coverage(folder,{'reviewers':{}})

    def test_resolution_binding_rejects_old(self):
        with self.assertRaises(ValueError):w.check_resolution_binding({'packet_id':'blank','resolution':{}},'blank')
        envelope=dict(packet_id='blank',binding=w.resolution_binding(),resolution={})
        w.check_resolution_binding(envelope,'blank')
        envelope['binding']['exports_sha256']='obsolete'
        with self.assertRaises(ValueError):w.check_resolution_binding(envelope,'blank')

    def test_no_journal_inside_any_benchmark_export(self):
        with self.assertRaises(ValueError):w.protect_journal(c.HERE/'reviewer_1_first_tuning_v1_cohort_v2'/'journal')

    def test_zero_real_review_and_training_status(self):
        with tempfile.TemporaryDirectory() as folder:
            result=w.coverage(Path(folder)/'absent',{'reviewers':{}})
            self.assertEqual(result['status'],'FIRST_TUNING_EXPERIMENT_REVIEW_PENDING')
            self.assertEqual(result['reviewed_accepted'],0);self.assertEqual(result['first_reviews_valid'],0)
            manifest=w.export_training(result,Path(folder)/'training')
            self.assertEqual(manifest['allowed_ids'],[])
            self.assertEqual(c.read(Path(folder)/'training'/'train.json'),[])
            self.assertEqual(c.read(Path(folder)/'training'/'dev.json'),[])
            self.assertFalse(result['final_model_acceptance_ready'])

    def test_maximum_tuning_pool_and_evaluation_exclusion(self):
        # Set membership only, not fake reviews or labels accepted into a journal.
        potential=c.training_candidates(ROWS,{i:None for i in FIRST['ids']})
        self.assertEqual(Counter(r['split'] for r in potential),{'train':78,'dev':40})
        self.assertTrue(all(not c.is_held(r) for r in potential))
        self.assertFalse(set(FIRST['access_categories']['additional_evaluation']) & {r['example_id'] for r in potential})

    def test_unselected_authored_rows_never_automatically_eligible(self):
        potential=c.training_candidates(ROWS,{r['example_id']:None for r in ROWS})
        self.assertEqual(len(potential),118)

    def test_held_out_exclusion_effect(self):
        row=deepcopy(next(r for r in F if c.is_held(r)));row['split']='train'
        accepted={row['example_id']:None}
        def invariant():self.assertEqual(c.training_candidates([row],accepted),[])
        with patch.object(c,'is_held',return_value=False):
            with self.assertRaises(AssertionError):invariant()
        invariant()

    def test_superseded_rejection_effect(self):
        m=next(iter(EXPORTS.values()))
        stale=c.packet(INDEX[m['ids'][0]],deepcopy(m['binding']))['response_template']
        stale['binding']['revision']='first-tuning-experiment-v1'
        with tempfile.TemporaryDirectory() as folder:
            def invariant():
                with patch.object(w,'assert_human',side_effect=AssertionError('Obsolete input reached human gate')):
                    with self.assertRaises(ValueError):w.ingest(stale,folder,{'reviewers':{}})
            # No human submission is made; reaching the human gate is the canary.
            with patch.object(c,'check_binding',return_value=next(iter(EXPORTS))):
                with self.assertRaises(AssertionError):invariant()
            invariant()

    def test_admin_filename_allowlist_effect(self):
        m=next(iter(EXPORTS.values()))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,raw in c.export_files(m['ids']).items():(root/name).write_bytes(raw)
            (root/'unexpected_admin.json').write_text('{}',encoding='utf-8')
            def invariant():
                with self.assertRaises(ValueError):c.audit_export(root,m['ids'])
            with patch.object(c,'check_names',return_value=None):
                with self.assertRaises(AssertionError):invariant()
            invariant()

    def test_blank_gold_byte_guard_effect(self):
        m=next(iter(EXPORTS.values()))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,raw in c.export_files(m['ids']).items():(root/name).write_bytes(raw)
            path=next(root.glob('*.json'));value=c.read(path)
            value['response_template']['review']['semantic_target']={'synthetic_forbidden_answer':'CANARY'}
            c.write(path,value)
            def invariant():
                with self.assertRaises(ValueError):c.audit_export(root,m['ids'])
            with patch.object(c,'check_bytes',return_value=None):
                with self.assertRaises(AssertionError):invariant()
            invariant()


if __name__=='__main__':
    unittest.main()
