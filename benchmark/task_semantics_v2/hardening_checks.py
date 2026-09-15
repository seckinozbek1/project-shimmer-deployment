"""Synthetic interface tests are not independent human reviews."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import hardening as h

BASE=h.read(h.V1/'seed.json')
EXT=h.read(h.HERE/'extension.json')
ROWS=BASE+EXT
META=h.read(h.HERE/'metadata.json')
POLICY=h.read(h.HERE/'domain_holdout.json')
P=next(r for r in EXT if r['role']=='producer' and r['abstract_relation']=='EXTRACTED')
A=next(r for r in EXT if r['role']=='auditor' and r['abstract_relation']=='MATCH')


def synthetic_response(row,reviewer='synthetic-interface-reviewer-1'):
    p=h.packet(row)
    return dict(packet_id=p['packet_id'],input_sha256=p['input_sha256'],reviewer_id=reviewer,
        reviewer_kind='human',independence_attestation=True,reviewed_at='2026-09-15T12:00:00+00:00',
        semantic_target=deepcopy(row['gold_target']),semantic_judgment=row['abstract_relation'],
        reason_components=['preserved_claim'],rationale='Synthetic test of review ingestion; NOT an actual human review.',
        ambiguity=False,formatting_judgment='valid',review_version=h.VERSION)


class HardeningTests(unittest.TestCase):
    def test_baseline_and_freeze(self):
        self.assertGreaterEqual(h.verify_baseline(),30);self.assertTrue(h.verify_freeze())

    def test_all_gold(self):
        self.assertEqual(h.validate(ROWS,META,POLICY)['examples'],736)
        for row in ROWS:
            with self.subTest(example=row['example_id']):self.assertTrue(h.baseline.evaluate(row,json.dumps(row['gold_target']))['accepted_outcome'])

    def test_all_compound_negatives(self):
        index={r['example_id']:r for r in ROWS}
        candidates=h.read(h.HERE/'compound_negatives.json')
        self.assertEqual(len(candidates),432)
        for item in candidates:
            parent=index[item['parent_id']]
            self.assertEqual(item['split'],parent['split']);self.assertEqual(item['derivation_group'],parent['derivation_group'])
            with self.subTest(candidate=item['candidate_id']):self.assertFalse(h.baseline.evaluate(parent,item['raw'])['accepted_outcome'])

    def test_structural_and_producer_coverage(self):
        self.assertEqual(len({r['template_family'] for r in EXT}),12)
        self.assertEqual(len({r['document_family'] for r in EXT}),48)
        self.assertEqual(sum(r['role']=='producer' and r['abstract_relation']=='EXTRACTED' for r in EXT),96)
        self.assertTrue(any(len(r['owned_aliases'])>1 for r in EXT if r['role']=='producer'))
        self.assertEqual(sum(bool(r['context_only_aliases']) for r in EXT),48)
        self.assertTrue(any(sum(len(i['questions']) for i in r['gold_target']['items'])>1 for r in EXT if r['role']=='producer'))

    def test_packet_allowlist(self):
        original=h.packet(P)
        row=deepcopy(P);row.update(gold_relation='CANARY_GOLD',split='CANARY_SPLIT',hard_negative_tags=['CANARY_TRANSFORMATION'])
        row['adjudication']={'future_unknown_answer':'CANARY_ANSWER'}
        row['gold_target']={'new_unknown_label':'CANARY_TARGET'}
        self.assertEqual(h.packet(row),original)
        raw=json.dumps(original)
        for marker in ('CANARY','gold_target','abstract_relation','parent_id','template_family','split_plan'):
            self.assertNotIn(marker,raw)

    def test_all_exported_packets_blinded(self):
        mapping=h.read(h.HERE/'review_admin_mapping.json')['packet_to_examples']
        files=list((h.HERE/'review_packets').glob('*.json'))
        self.assertEqual(len(files),len(mapping))
        for file in files:
            p=h.read(file)
            self.assertEqual(p['input_sha256'],h.digest(p['input']))
            self.assertEqual(set(p['input'])-{'extraction'},set(h.review_input(P)))
            self.assertNotIn('gold_target',p['input'])

    def test_packet_changes_when_review_input_changes(self):
        row=deepcopy(P);row['source_text']+=' Different source.'
        self.assertNotEqual(h.packet(row)['input_sha256'],h.packet(P)['input_sha256'])

    def test_review_pending(self):
        self.assertEqual(h.adjudication_state(P,[])['state'],'pending')
        self.assertTrue(all(v['independent_review_state']=='pending' for v in META.values()))

    def test_review_journal_append_only(self):
        with tempfile.TemporaryDirectory() as folder:
            first=synthetic_response(P)
            self.assertEqual(h.ingest_review(first,[P],folder)['state'],'first_review_received')
            with self.assertRaises(ValueError):h.ingest_review(first,[P],folder)
            second=synthetic_response(P,'synthetic-interface-reviewer-2')
            self.assertEqual(h.ingest_review(second,[P],folder)['state'],'agreed')
            self.assertEqual(len(list(Path(folder).glob('*-final.json'))),1)
        with self.assertRaises(PermissionError):h.ingest_review(first,[P],h.HERE/'review_packets')

    def test_first_second_review(self):
        first=synthetic_response(P);second=synthetic_response(P,'synthetic-interface-reviewer-2')
        self.assertEqual(h.adjudication_state(P,[first])['state'],'first_review_received')
        self.assertEqual(h.adjudication_state(P,[first,second])['state'],'agreed')

    def test_no_self_or_machine_review(self):
        for field,value in [('reviewer_id','expansion-author-assistant'),('reviewer_kind','machine'),('independence_attestation',False)]:
            r=synthetic_response(P);r[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):h.adjudication_state(P,[r])
        r=synthetic_response(P)
        with self.assertRaises(ValueError):h.adjudication_state(P,[r,r])

    def test_review_binding_version_and_date(self):
        for field,value in [('input_sha256','wrong'),('packet_id','wrong'),('review_version','wrong'),('reviewed_at','2026-09-15')]:
            r=synthetic_response(P);r[field]=value
            with self.assertRaises(ValueError):h.adjudication_state(P,[r])

    def test_disagreement_and_resolution(self):
        first=synthetic_response(P);second=synthetic_response(P,'synthetic-interface-reviewer-2')
        second['ambiguity']=True
        self.assertEqual(h.adjudication_state(P,[first,second])['state'],'disagreement')
        resolution=dict(final_target=P['gold_target'],rationale='Synthetic explicit resolution.',adjudicator_id='synthetic-resolver',input_sha256=h.packet(P)['input_sha256'],
                        adjudicator_kind='human',independence_attestation=True,review_version=h.VERSION,adjudicated_at='2026-09-15T12:00:00+00:00')
        self.assertEqual(h.adjudication_state(P,[first,second],resolution)['state'],'adjudicated')
        with tempfile.TemporaryDirectory() as folder:
            h.ingest_review(first,[P],folder);h.ingest_review(second,[P],folder)
            self.assertEqual(h.resolve_review(h.packet(P)['packet_id'],[P],folder,resolution)['state'],'adjudicated')
        resolution['input_sha256']='wrong'
        with self.assertRaises(ValueError):h.adjudication_state(P,[first,second],resolution)

    def test_semantic_formatting_separate(self):
        first=synthetic_response(P);second=synthetic_response(P,'synthetic-interface-reviewer-2')
        second['formatting_judgment']='not_assessed'
        state=h.adjudication_state(P,[first,second])
        self.assertEqual(state['state'],'agreed');self.assertEqual(state['formatting_judgments'],['valid','not_assessed'])

    def test_invalid_adjudicated_contract(self):
        first=synthetic_response(P);first['semantic_target']={'bad':'wire'}
        second=deepcopy(first);second['reviewer_id']='synthetic-interface-reviewer-2'
        with self.assertRaises(ValueError):h.adjudication_state(P,[first,second])

    def test_reason_paraphrase_review(self):
        obj=deepcopy(A['gold_target']);obj['items'][0]['reasoning']='All source observations remain faithfully represented.'
        raw=json.dumps(obj);p=h.packet(A)
        self.assertIsNone(h.baseline.evaluate(A,raw)['reason_correct'])
        review=dict(packet_id=p['packet_id'],input_sha256=p['input_sha256'],raw_sha256=h.digest(raw.encode()),
            reviewer_id='synthetic-interface-reviewer',reviewer_kind='human',independence_attestation=True,
            reviewed_at='2026-09-15T12:00:00+00:00',components=['preserved_claim','gap_preserved'],correct=True,
            rationale='Synthetic rubric interface test; not an independent review of this dataset.')
        self.assertTrue(h.assess_reason(A,raw,review)['accepted_outcome'])
        review['raw_sha256']='wrong'
        with self.assertRaises(ValueError):h.assess_reason(A,raw,review)

    def test_domain_holdout(self):
        held=[r for r in ROWS if r['domain'] in POLICY['held_out_domains']]
        self.assertEqual(len(held),72)
        self.assertTrue(all(r['split'] not in ('train','dev') for r in held))
        changed=deepcopy(ROWS);changed[0]['domain']='astronomy'
        with self.assertRaisesRegex(ValueError,'Domain-holdout'):h.validate(changed,META,POLICY)

    def test_unseen_templates(self):
        manifest=h.read(h.HERE/'unseen_templates.json')
        self.assertEqual(len(manifest['unseen_examples']),368)
        training=set(manifest['training_templates'])
        self.assertTrue(all(r['template_family'] not in training for r in ROWS if r['example_id'] in manifest['unseen_examples']))

    def test_training_view(self):
        manifest=h.read(h.HERE/'training_view/manifest.json')
        self.assertEqual(len(manifest['allowed_ids']),368)
        for name in ('train.json','dev.json'):
            rows=h.load_training_file(h.HERE/'training_view',name,manifest)
            self.assertEqual(len(rows),184)
        for name in ('../extension.json','../../durable/anything','labels.json','test.json','sealed_adversarial.json'):
            with self.assertRaises(PermissionError):h.load_training_file(h.HERE/'training_view',name,manifest)

    def test_training_hash_tamper(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);h.write(root/'train.json',[P])
            manifest=dict(allowed_files={'train.json':'wrong'},allowed_ids=[P['example_id']],held_out_domains=[])
            with self.assertRaises(ValueError):h.load_training_file(root,'train.json',manifest)

    def test_sealed_default_cannot_read(self):
        with patch.object(h,'read') as read:
            with self.assertRaises(PermissionError):h.read_sealed(Path(tempfile.gettempdir())/'nonexistent-vault','development',{})
            read.assert_not_called()

    def test_sealed_inside_repo_rejected(self):
        with self.assertRaises(PermissionError):h.read_sealed(h.HERE/'labels','final_evaluation',{})

    def test_sealed_missing_permit(self):
        with self.assertRaises(PermissionError):h.read_sealed(Path(tempfile.gettempdir())/'vault','final_evaluation',{})

    def test_sealed_population_pending(self):
        manifest=h.read(h.HERE/'sealed_final_manifest.json')
        self.assertEqual(manifest['populated_examples'],0);self.assertIsNone(manifest['labels_sha256'])

    def test_synthetic_final_mode_and_append_only(self):
        # Temporary, clearly synthetic store; never populates the real manifest.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);h.write(root/'labels.json',[P]);binding=h.digest((root/'labels.json').read_bytes())
            h.write(root/'manifest.json',dict(state='independently_populated',independence_attestation=True,note='synthetic test only',labels_sha256=binding))
            candidates=[dict(example_id=P['example_id'],raw=json.dumps(P['gold_target']),truncated=False,completed=True)]
            permit=dict(purpose='final_evaluation_only',operator_authorized=True,acceptance_registration_sha256='synthetic-test-registration',
                        model_candidate_sha256=h.digest(candidates),labels_sha256=binding)
            result=h.final_evaluate(root,'final_evaluation',permit,candidates,'synthetic-1')
            self.assertEqual(result['accepted_count'],1)
            with self.assertRaises(FileExistsError):h.final_evaluate(root,'final_evaluation',permit,candidates,'synthetic-1')
            h.write(root/'labels.json',[])
            with self.assertRaises(ValueError):h.read_sealed(root,'final_evaluation',permit)

    def test_final_result_excludes_answers(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):h.append_final_result(folder,'run',{'gold_target':'not allowed'}, {})

    def test_public_seed_cannot_be_sealed(self):
        with tempfile.TemporaryDirectory() as folder:
            attestation=dict(contributor_kind='human',independent_material=True,contributor_id='synthetic-contributor',operator_authorized=True)
            with self.assertRaises(ValueError):h.seal_contribution(folder,[P],attestation)

    def test_seal_synthetic_contribution_interface(self):
        with tempfile.TemporaryDirectory() as folder:
            row=deepcopy(P);row['provenance']['privacy']='independent_synthetic_sealed'
            row['adjudication'].update(state='independently_reviewed',first_id='synthetic-source-author',second_id='synthetic-second-reviewer',second_judgment=row['gold_target'])
            attestation=dict(contributor_kind='human',independent_material=True,contributor_id='synthetic-contributor',operator_authorized=True)
            manifest=h.seal_contribution(folder,[row],attestation)
            self.assertEqual(manifest['examples'],1)
            with self.assertRaises(FileExistsError):h.seal_contribution(folder,[row],attestation)

    def test_role_and_target_judgment_consistency(self):
        response=synthetic_response(P);response['semantic_judgment']='MATCH'
        with self.assertRaises(ValueError):h.adjudication_state(P,[response])
        response['semantic_judgment']='EMPTY'
        with self.assertRaises(ValueError):h.adjudication_state(P,[response])

    def test_sealed_answer_exposure(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'public.json';marker='Synthetic protected answer for boundary test only.'
            h.write(path,dict(answer=marker))
            with self.assertRaisesRegex(ValueError,'Sealed answer exposure'):h.audit_public_artifacts([path],{h.digest(marker.encode())})
            self.assertEqual(h.audit_public_artifacts([path],set())['sealed_answer_findings'],0)
            h.write(path,dict(nested=P['gold_target']))
            with self.assertRaises(ValueError):h.audit_public_artifacts([path],{h.digest(P['gold_target'])})

    def test_family_statistics(self):
        rows=[r for r in EXT if r['role']=='auditor']
        scores=[h.baseline.evaluate(r,json.dumps(r['gold_target'])) for r in rows]
        result=h.family_statistics(scores,rows,draws=100)
        self.assertEqual(result['document_family']['group_count'],48)
        self.assertEqual(result['template_family']['group_count'],12)
        self.assertEqual(result['domain']['group_count'],10)
        self.assertEqual(result['document_family']['macro_accepted_outcome'],1)
        self.assertIn('aggregate.evidence.precision',result['document_family']['metric_macros'])
        small=h.family_statistics(scores[:2],rows,draws=100)
        self.assertIsNone(small['document_family']['exploratory_cluster_bootstrap95'])

    def test_family_weight_not_row_weight(self):
        a=deepcopy(P);b=deepcopy(P);b['example_id']='different';b['document_family']='different'
        s=h.baseline.evaluate(a,json.dumps(a['gold_target']));t=h.baseline.evaluate(b,'bad')
        result=h.family_statistics([s]*20+[t],[a,b],draws=100)
        self.assertEqual(result['document_family']['macro_accepted_outcome'],.5)

    def test_acceptance_registration(self):
        spec=h.read(h.HERE/'acceptance_specification.json')
        self.assertEqual(h.acceptance([],spec,{})['verdict'],'NOT_REGISTERED')
        self.assertTrue(all(v==0 for v in spec['catastrophic_limits'].values()))
        self.assertIn('per_class_recall',spec['thresholds']['auditor'])
        self.assertIn('heldout_domain_floor',spec['thresholds']['shared'])
        score=h.baseline.evaluate(A,'invalid',truncated=True)
        self.assertEqual(h.acceptance([score],spec,{})['catastrophic_counts']['truncation'],1)

    def test_governance_existing_boundary(self):
        policy=dict(producer_family='qwen2',auditor_family='llama',self_audit=False,privacy='authored_public_synthetic',operator_authorized=True,
                    training=False,multi_round=False,paid_api=False,provenance_verified=True)
        self.assertTrue(h.baseline.governance(policy))
        for key,value in [('auditor_family','qwen2'),('self_audit',True),('privacy','operator_private'),('operator_authorized',False),('training',True),('paid_api',True),('provenance_verified',False)]:
            with self.assertRaises(ValueError):h.baseline.governance(dict(policy,**{key:value}))

    def test_effect_proofs(self):
        # Allowlist neutralised: newly introduced metadata now leaks; restore fixes it.
        r=deepcopy(P);r['new_answer_field']='BLINDING_CANARY'
        def blinding():return 'BLINDING_CANARY' not in json.dumps(h.packet(r))
        self.assertTrue(blinding())
        with patch.object(h,'review_input',lambda row:row):self.assertFalse(blinding())
        self.assertTrue(blinding())
        rows=deepcopy(ROWS);rows[0]['domain']='astronomy'
        def domain_gate():
            try:h.validate(rows,META,POLICY);return False
            except ValueError:return True
        self.assertTrue(domain_gate())
        modified=deepcopy(POLICY);modified['held_out_domains']=[];modified['training_access_domains'].append('astronomy')
        # Neutralise the domain exclusion while family/ancestry checks remain live.
        h.validate(rows,META,modified)
        self.assertTrue(domain_gate())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);h.write(root/'labels.json',[P])
            manifest=dict(allowed_files={},allowed_ids=[P['example_id']],held_out_domains=[])
            def denied():
                try:h.load_training_file(root,'labels.json',manifest);return False
                except PermissionError:return True
            self.assertTrue(denied())
            manifest['allowed_files']['labels.json']=h.digest((root/'labels.json').read_bytes())
            self.assertFalse(denied())
            manifest['allowed_files'].clear();self.assertTrue(denied())


if __name__=='__main__':unittest.main()
