"""Deterministic preparation checks. No fake human submissions are executed."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import registration as r

ROWS=r.records();INDEX={x['example_id']:x for x in ROWS}
FIRST=r.read(r.HERE/'cohort.json')['ids'];SECOND=r.read(r.HERE/'double_review.json')['ids']


class PreparationChecks(unittest.TestCase):
    def test_frozen_input_and_profile(self):self.assertTrue(r.verify_frozen())

    def test_exact_27_and_derived_r07(self):
        p=r.read(r.HERE/'acceptance_registration.json')
        self.assertEqual(len(p['criteria']),27)
        self.assertEqual({x['id'] for x in p['criteria']},{'P'+str(i).zfill(2) for i in range(1,12)}|{'A'+str(i).zfill(2) for i in range(1,11)}|{'R'+str(i).zfill(2) for i in range(1,7)})
        self.assertEqual(p['derived_hard_gate']['id'],'R07');self.assertEqual(p['derived_hard_gate']['value'],0)

    def test_exact_operator_values(self):
        p=r.profile();values={c['id']:(c['operator'],c['value']) for c in p['criteria']}
        self.assertEqual([values['P'+str(i).zfill(2)][1] for i in range(1,12)],[.95,.95,.95,.95,1.,.98,.95,.95,.95,.99,.95])
        self.assertEqual([values['A'+str(i).zfill(2)][1] for i in range(1,11)],[.95,.93,.90,.95,.95,.90,1.,.98,.99,.95])
        self.assertEqual([values['R'+str(i).zfill(2)][1] for i in range(1,7)],[1.,.25,1.,1.,64,.80])
        for key in ('P05','A07','R01','R03','R04'):self.assertEqual(values[key][0],'==')

    def test_six_zero_constraints_unchanged(self):
        limits=r.profile()['catastrophic_limits']
        self.assertEqual(limits,r.read(r.h.HERE/'acceptance_specification.json')['catastrophic_limits'])
        self.assertEqual(len(limits),6);self.assertTrue(all(v==0 for v in limits.values()))

    def test_registration_tampering(self):
        p=r.profile();p['criteria'][0]['value']=.90
        with self.assertRaises(ValueError):r.verify_profile(p)

    def test_separate_first_final_decisions(self):
        p=r.profile()
        self.assertFalse(p['sealed_final_required_for_first_experiment'])
        final=p['final_model_acceptance']
        self.assertFalse(final['ready']);self.assertTrue(final['genuine_independent_sealed_material_required'])
        self.assertTrue(final['external_account_acl_required']);self.assertTrue(final['final_numeric_thresholds_unchanged'])
        self.assertFalse(p['training_authorized'])

    def test_selection_reproducible_order_independent(self):
        self.assertEqual(r.selection(ROWS),(FIRST,SECOND))
        self.assertEqual(r.selection(list(reversed(ROWS))),(FIRST,SECOND))
        self.assertNotEqual(FIRST,sorted(INDEX)[:192])

    def test_192_unique_mandatory_72(self):
        self.assertEqual(len(FIRST),192);self.assertEqual(len(set(FIRST)),192)
        held={x['example_id'] for x in ROWS if x['domain'] in ('astronomy','ecology')}
        self.assertEqual(len(held),72);self.assertTrue(held<=set(FIRST))

    def test_role_balance_exact_feasible_optimum(self):
        self.assertEqual(Counter(INDEX[i]['role'] for i in FIRST),{'producer':96,'auditor':96})
        self.assertEqual(Counter(INDEX[i]['role'] for i in SECOND),{'producer':24,'auditor':24})

    def test_maximum_family_diversity(self):
        self.assertEqual(len({INDEX[i]['document_family'] for i in FIRST}),len({x['document_family'] for x in ROWS}))
        self.assertEqual(len({INDEX[i]['document_family'] for i in FIRST}),80)
        self.assertEqual(len({INDEX[i]['document_family'] for i in SECOND}),48)

    def test_template_domain_unseen_coverage(self):
        self.assertEqual(len({INDEX[i]['template_family'] for i in FIRST}),16)
        self.assertEqual(len({INDEX[i]['domain'] for i in FIRST}),10)
        self.assertEqual(sum(INDEX[i]['split'] in ('test','sealed_adversarial') for i in FIRST),114)
        self.assertEqual(len({INDEX[i]['template_family'] for i in SECOND}),16)

    def test_second_subset_and_semantic_strata(self):
        self.assertEqual(len(SECOND),48);self.assertEqual(len(set(SECOND)),48);self.assertTrue(set(SECOND)<=set(FIRST))
        feature=set().union(*(r.feature_set(INDEX[i]) for i in SECOND))
        for key in ('refusal:producer','refusal:auditor','information_gap','uncertainty','context_ownership','contradictory_source','relation:MATCH','relation:DIVERGENCE','relation:OMISSION','relation:ADDITION'):
            self.assertIn(key,feature)

    def test_substantive_producer_priority(self):
        self.assertEqual(sum(INDEX[i]['role']=='producer' and INDEX[i]['abstract_relation']=='EXTRACTED' for i in FIRST),72)

    def test_remaining_packets_preserved(self):
        self.assertEqual(len(set(INDEX)-set(FIRST)),544)
        self.assertEqual(len(list((r.h.HERE/'review_packets').glob('*.json'))),736)

    def test_export_exact_blank_bytes(self):
        manifest=r.read(r.HERE/'export_admin_manifest.json')
        for name,value in manifest.items():
            audit=r.audit_export(r.HERE/name,value['packet_ids'])
            self.assertEqual(audit['gold_findings'],0)
            for ident in value['packet_ids']:
                p=r.read(r.HERE/name/(ident+'.json'))
                self.assertIsNone(p['response_template']['semantic_target'])
                self.assertIsNone(p['response_template']['semantic_judgment'])
                self.assertIsNone(p['response_template']['reviewer_id'])
                self.assertFalse(p['response_template']['independence_attestation'])

    def test_reviewer_two_never_first_answer(self):
        for ident in r.read(r.HERE/'export_admin_manifest.json')['reviewer_2_first_tuning_v1']['packet_ids']:
            self.assertEqual((r.HERE/'reviewer_1_first_tuning_v1'/(ident+'.json')).read_bytes(),(r.HERE/'reviewer_2_first_tuning_v1'/(ident+'.json')).read_bytes())

    def test_archive_exact_file_set_and_bytes(self):
        for name,manifest in r.read(r.HERE/'export_admin_manifest.json').items():
            path=r.HERE/(name+'.zip')
            self.assertEqual(r.digest(path.read_bytes()),manifest['archive_sha256'])
            with zipfile.ZipFile(path) as z:
                self.assertIsNone(z.testzip());self.assertEqual(set(z.namelist()),set(manifest['files']))
                self.assertEqual(len(z.namelist()),len(set(z.namelist())))
                for member in z.namelist():
                    self.assertNotIn('/',member);self.assertNotIn('..',member)
                    self.assertEqual(z.read(member),(r.HERE/name/member).read_bytes())

    def test_export_rejects_admin_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);shutil.copyfile(r.HERE/'reviewer_instructions.md',root/'INSTRUCTIONS.md')
            r.write(root/'admin_mapping.json',{'not_allowed':'admin data'})
            with self.assertRaises(ValueError):r.audit_export(root,[])

    def test_export_unknown_future_gold_field(self):
        ident=r.h.packet(INDEX[FIRST[0]])['packet_id']
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,value in r.expected_export_files([ident]).items():(root/name).write_bytes(value)
            p=r.read(root/(ident+'.json'));p['future_unknown_answer']='GOLD_CANARY_FOR_EXPORT_TEST'
            r.write(root/(ident+'.json'),p)
            with self.assertRaises(ValueError):r.audit_export(root,[ident])

    def test_hash_bound_journal_compatibility_without_submissions(self):
        for ident in FIRST:
            p=r.h.packet(INDEX[ident]);export=r.read(r.HERE/'reviewer_1_first_tuning_v1'/(p['packet_id']+'.json'))
            self.assertEqual(export,p)
            self.assertEqual(export['response_template']['review_version'],r.h.VERSION)
            # Blank templates cannot be mistaken for completed human reviews.
            with self.assertRaises((ValueError,TypeError)):
                r.h.validate_review(export['response_template'],p,{INDEX[ident]['adjudication']['first_id']})

    def test_no_human_submissions_no_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            coverage=r.review_coverage(ROWS,FIRST,SECOND,folder,{'reviewers':{}})
            self.assertEqual(coverage['status'],'FIRST_TUNING_EXPERIMENT_REVIEW_PENDING')
            self.assertEqual(coverage['first_reviews_valid'],0);self.assertEqual(coverage['designated_second_reviews_valid'],0)
            self.assertFalse(coverage['final_model_acceptance_ready']);self.assertEqual(list(Path(folder).iterdir()),[])

    def test_empty_training_manifest(self):
        coverage={'accepted_targets':{}}
        manifest=r.eligible_training(ROWS,coverage)
        self.assertEqual(manifest['allowed_ids'],[])
        self.assertEqual(len(manifest['categories']['authored_only']),368)
        self.assertEqual(len(manifest['categories']['held_out_domain']),72)

    def test_training_access_partition_math_not_human_review(self):
        # Abstract set-membership fixture, not journal input or review coverage.
        hypothetical={'accepted_targets':{i:{} for i in FIRST}}
        manifest=r.eligible_training(ROWS,hypothetical)
        self.assertEqual(len(manifest['allowed_ids']),78)
        self.assertTrue(all(INDEX[i]['split'] in ('train','dev') for i in manifest['allowed_ids']))
        self.assertTrue(all(INDEX[i]['domain'] not in ('astronomy','ecology') for i in manifest['allowed_ids']))

    def test_training_export_initially_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            manifest=r.export_training_labels(ROWS,{'accepted_targets':{}},folder)
            self.assertEqual(manifest['allowed_ids'],[])
            for name in ('train.json','dev.json'):self.assertEqual(r.read(Path(folder)/name),[])

    def test_27_thresholds_evaluable_without_false_pass(self):
        coverage=r.review_coverage(ROWS,FIRST,SECOND,r.HERE/'no_submissions_exist')
        result=r.evaluate_thresholds([],ROWS,coverage)
        self.assertEqual(len(result['criteria']),27);self.assertFalse(result['promising_checkpoint'])
        self.assertIsNone(result['criteria']['P01']['passed']);self.assertFalse(result['criteria']['R01']['passed'])

    def test_metrics_gold_math_is_not_review_or_model_evidence(self):
        scores=[r.h.baseline.evaluate(INDEX[i],json.dumps(INDEX[i]['gold_target'])) for i in FIRST if INDEX[i]['split']!='train']
        metrics,cat=r.performance_metrics(scores)
        for key in ['P'+str(i).zfill(2) for i in range(1,12)]+['A'+str(i).zfill(2) for i in range(1,11)]:
            self.assertEqual(metrics[key],1.,key)
        self.assertTrue(all(v==0 for v in cat.values()))

    def test_minimum_family_rule_and_no_exclusion_of_bad_family(self):
        ids=[i for i in FIRST if INDEX[i]['document_family']=='v2-compact_table-astronomy']
        scores=[r.h.baseline.evaluate(INDEX[i],json.dumps(INDEX[i]['gold_target'])) for i in ids[:4]]
        scores[-1]['accepted_outcome']=False
        coverage=dict(status='FIRST_TUNING_EXPERIMENT_REVIEW_PENDING',accepted_targets={i:{} for i in ids[:4]},
                      reviewed_accepted=0,designated_second_reviews_valid=0,reviewed_templates=0,reviewed_held_out=0,reviewed_unseen_templates=0)
        result=r.evaluate_thresholds(scores,ROWS,coverage)
        self.assertEqual(result['criteria']['R06']['measured'],.75);self.assertFalse(result['criteria']['R06']['passed'])
        coverage['accepted_targets']={i:{} for i in ids[:3]}
        result=r.evaluate_thresholds(scores[:3],ROWS,coverage)
        self.assertEqual(result['families']['v2-compact_table-astronomy']['status'],'insufficient_sample_for_family_gate')
        self.assertIsNone(result['criteria']['R06']['passed'])

    def test_catastrophic_failure_count(self):
        row=next(INDEX[i] for i in FIRST if INDEX[i]['role']=='auditor')
        score=r.h.baseline.evaluate(row,'invalid',truncated=True)
        coverage=r.review_coverage(ROWS,FIRST,SECOND,r.HERE/'no_submissions_exist')
        result=r.evaluate_thresholds([score],ROWS,coverage,governance_violations=1)
        self.assertFalse(result['R07']['passed']);self.assertEqual(result['R07']['counts']['truncation'],1)
        self.assertEqual(result['R07']['counts']['governance_violations'],1)

    def test_governance_equivalence(self):
        p=dict(producer_family='qwen2',auditor_family='llama',self_audit=False,privacy='authored_public_synthetic',
               operator_authorized=True,training=False,multi_round=False,paid_api=False,provenance_verified=True)
        self.assertTrue(r.h.baseline.governance(p))
        for key,value in [('auditor_family','qwen2'),('self_audit',True),('privacy','operator_private'),('training',True),('paid_api',True),('provenance_verified',False)]:
            with self.assertRaises(ValueError):r.h.baseline.governance(dict(p,**{key:value}))

    def test_export_effect_proofs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);original=r.expected_export_files([])
            (root/'INSTRUCTIONS.md').write_bytes(original['INSTRUCTIONS.md'])
            (root/'unknown_admin.json').write_text('{"unforeseen_label":"CANARY"}',encoding='utf-8')
            def rejects():
                try:r.audit_export(root,[]);return False
                except ValueError:return True
            self.assertTrue(rejects())
            with patch.object(r,'expected_export_files',return_value=dict(original,**{'unknown_admin.json':(root/'unknown_admin.json').read_bytes()})):
                self.assertFalse(rejects())
            self.assertTrue(rejects())
        ident=r.h.packet(INDEX[FIRST[0]])['packet_id']
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);approved=r.expected_export_files([ident])
            for name,data in approved.items():(root/name).write_bytes(data)
            filename=ident+'.json';obj=json.loads(approved[filename]);obj['response_template']['semantic_target']={'forbidden_prior_answer':'CANARY'}
            r.write(root/filename,obj)
            def rejects_answer():
                try:r.audit_export(root,[ident]);return False
                except ValueError:return True
            self.assertTrue(rejects_answer())
            with patch.object(r,'expected_export_files',return_value=dict(approved,**{filename:(root/filename).read_bytes()})):
                self.assertFalse(rejects_answer())
            self.assertTrue(rejects_answer())


if __name__=='__main__':unittest.main()
