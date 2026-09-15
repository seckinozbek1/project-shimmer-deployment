"""Short deterministic tests, including neutralise/fail/restore/pass guards."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json
import unittest

import core as c
from build_seed import NEGATIVES, candidate

HERE = Path(__file__).resolve().parent
ROWS = c.read(HERE/'seed.json')
P = next(r for r in ROWS if r['role']=='producer' and r['abstract_relation']=='EXTRACTED')
A = next(r for r in ROWS if r['role']=='auditor' and r['abstract_relation']=='MATCH')
R = next(r for r in ROWS if r['expected_refusal'])


class DatasetTests(unittest.TestCase):
    def test_frozen_authorities(self): self.assertTrue(c.verify_freeze())

    def test_corpus_and_every_gold(self):
        self.assertEqual(c.leakage(ROWS)['examples'],448)
        for row in ROWS:
            with self.subTest(example=row['example_id']):
                self.assertTrue(c.evaluate(row,json.dumps(row['gold_target']))['accepted_outcome'])

    def test_all_negative_candidates(self):
        candidates = c.read(HERE/'negative_candidates.json')
        index = {r['example_id']:r for r in ROWS}
        self.assertEqual({x['transformation'] for x in candidates},set(NEGATIVES))
        self.assertEqual(len(candidates),576)
        for x in candidates:
            with self.subTest(candidate=x['candidate_id']):
                parent=index[x['parent_id']]
                self.assertEqual(x['split'],parent['split'])
                self.assertEqual(x['derivation_group'],parent['derivation_group'])
                self.assertFalse(c.evaluate(parent,x['raw'])['accepted_outcome'])

    def test_balanced_domains_and_roles(self):
        from collections import Counter
        self.assertEqual(set(Counter(r['domain'] for r in ROWS).values()),{56})
        self.assertEqual(set(Counter(r['split'] for r in ROWS).values()),{112})
        self.assertEqual(len({r['document_family'] for r in ROWS}),32)
        self.assertEqual(len({r['template_family'] for r in ROWS}),4)

    def test_status_transitions(self):
        for role,relation,state in [('producer','EXTRACTED','extracted'),('producer','EMPTY','examined_empty'),
                                    ('producer','INSUFFICIENT_EVIDENCE','semantic_refusal'),
                                    ('auditor','INSUFFICIENT_EVIDENCE','semantic_refusal'),('auditor','MATCH','fidelity')]:
            row=next(r for r in ROWS if r['role']==role and r['abstract_relation']==relation)
            self.assertEqual(c.classify(row,json.dumps(row['gold_target']))[:2],(state,True))
        self.assertEqual(c.classify(P,'{"items":[]}')[:2],('incomplete',False))
        self.assertEqual(c.classify(A,'{"items":[]}')[:2],('malformed',False))
        self.assertEqual(c.classify(P,'not JSON')[:2],('malformed',False))
        self.assertEqual(c.classify(P,'{"items":',True)[:2],('incomplete',False))

    def test_auditor_both_inputs_empty(self):
        row=deepcopy(A);row.update(source_text='',extraction_text='',owned_aliases=[],context_only_aliases=[],supplied_refs=[],required_refs=[])
        self.assertEqual(c.classify(row,'{"items":[]}')[:2],('examined_empty',True))
        row['extraction_text']='unexpected content'
        self.assertFalse(c.classify(row,'{"items":[]}')[1])

    def test_refusal_never_production_acceptance(self):
        result=c.evaluate(R,json.dumps(R['gold_target']))
        self.assertTrue(result['accepted_outcome']);self.assertFalse(result['production_accepted'])
        self.assertFalse(result['semantic_accepted'])
        with self.assertRaises(ValueError): c.cc.producer(R['gold_target'],c.owned(R),R['example_id'])

    def test_over_under_refusal(self):
        self.assertTrue(c.evaluate(P,'{"items":[],"status":"refused"}')['over_refusal'])
        row=deepcopy(A);row.update(expected_refusal=True,abstract_relation='INSUFFICIENT_EVIDENCE',gold_target={'items':[],'status':'refused'})
        score=c.evaluate(row,json.dumps(A['gold_target']))
        self.assertTrue(score['under_refusal']);self.assertTrue(score['unsupported_forced_answer'])

    def test_transport_independent_of_contract(self):
        score=c.evaluate(P,json.dumps(P['gold_target']),completed=False)
        self.assertTrue(score['contract_valid']);self.assertFalse(score['transport_complete']);self.assertFalse(score['accepted_outcome'])

    def test_truncation_overrides_valid_json(self):
        score=c.evaluate(A,json.dumps(A['gold_target']),truncated=True)
        self.assertEqual(score['state'],'incomplete');self.assertFalse(score['accepted_outcome'])

    def test_valid_json_wrong_semantics(self):
        obj=deepcopy(P['gold_target']);obj['items'][0]['questions']=[]
        score=c.evaluate(P,json.dumps(obj))
        self.assertTrue(score['contract_valid']);self.assertFalse(score['semantic_correct'])
        self.assertEqual(score['information_gaps']['recall'],0)
        self.assertTrue(score['catastrophic']['silent_gap_omission'])

    def test_multiple_claims_single_alias(self):
        self.assertEqual(len(P['gold_target']['items']),1)
        self.assertEqual(len(P['gold_target']['items'][0]['claims']),2)
        canonical=c.cc.producer(P['gold_target'],c.owned(P),P['example_id'])
        self.assertEqual(''.join(i['draft_text'] for i in canonical['items']),''.join(s.text for s in c.owned(P)))

    def test_no_numeric_equality_fidelity_shortcut(self):
        equal = [r for r in ROWS if r['hard_negative_tags']==['label_swap'] and r['domain']=='contracts']
        self.assertEqual(len(equal),4)
        for row in equal:
            self.assertEqual(row['abstract_relation'],'DIVERGENCE')
        unequal = [r for r in ROWS if r['abstract_relation']=='MATCH' and r['domain']=='nonsense']
        self.assertEqual(len(unequal),4)
        for row in unequal: self.assertTrue(c.evaluate(row,json.dumps(row['gold_target']))['accepted_outcome'])

    def test_evidence_precision_recall_no_repair(self):
        obj=deepcopy(A['gold_target']);obj['items'][0]['ref_ids']=['REF-0001','REF-7777']
        score=c.evaluate(A,json.dumps(obj))
        self.assertFalse(score['contract_valid']);self.assertEqual(score['evidence']['precision'],.5)
        self.assertEqual(score['evidence']['recall'],.5);self.assertEqual(score['evidence']['invented'],1)

    def test_irrelevant_available_evidence(self):
        obj=deepcopy(A['gold_target']);obj['items'][0]['ref_ids'].append('REF-9999')
        score=c.evaluate(A,json.dumps(obj))
        self.assertTrue(score['contract_valid']);self.assertEqual(score['evidence']['invented'],0)
        self.assertEqual(score['evidence']['fp'],1);self.assertFalse(score['semantic_correct'])

    def test_reason_not_fluency(self):
        obj=deepcopy(A['gold_target']);obj['items'][0]['reasoning']='A beautifully phrased, plausible explanation.'
        score=c.evaluate(A,json.dumps(obj))
        self.assertTrue(score['contract_valid']);self.assertIsNone(score['reason_correct']);self.assertFalse(score['accepted_outcome'])

    def test_hash_bound_reason_adjudication(self):
        obj=deepcopy(A['gold_target']);obj['items'][0]['reasoning']='All observations were preserved.'
        raw=json.dumps(obj)
        review=dict(raw_sha256=c.digest(raw.encode('utf-8')),example_id=A['example_id'],state='independently_reviewed',
                    reviewer_id='synthetic-test-reviewer',rationale='Synthetic test of the review interface, not a human review.',correct=True)
        self.assertTrue(c.evaluate(A,raw,reason_review=review)['accepted_outcome'])
        review['raw_sha256']='wrong'
        with self.assertRaises(ValueError):c.evaluate(A,raw,reason_review=review)

    def test_tuning_export_excludes_heldout(self):
        self.assertEqual(len(c.select_for_tuning(ROWS)),224)
        for split in ('test','sealed_adversarial','regression'):
            with self.assertRaises(ValueError):c.select_for_tuning(ROWS,[split])

    def test_adjudication_workflow(self):
        row=c.adjudicate(P,'synthetic-test-reviewer',P['gold_target'],'Interface test only.')
        self.assertEqual(row['adjudication']['state'],'independently_reviewed')
        with self.assertRaises(ValueError):c.adjudicate(P,P['adjudication']['first_id'],P['gold_target'],'not independent')
        with self.assertRaises(ValueError):c.adjudicate(P,'second',{},'Disagree')
        row=c.adjudicate(P,'second',{},'Explicit resolution for interface test.',final_target=P['gold_target'])
        self.assertEqual(row['adjudication']['state'],'adjudicated')

    def test_duplicate_id(self):
        with self.assertRaises(ValueError):c.leakage([P,P])

    def test_broken_ancestry(self):
        row=deepcopy(P);row['parent_id']='missing'
        with self.assertRaises(ValueError):c.leakage([row])

    def test_cyclic_ancestry(self):
        row=deepcopy(P);row['parent_id']=row['example_id']
        with self.assertRaises(ValueError):c.leakage([row])

    def test_cross_split_all_family_dimensions(self):
        for field in c.GROUPS:
            row=deepcopy(P);row['example_id']='other';row['split']='dev'
            for other in c.GROUPS:
                if other!=field:row[other]+='-new'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'family leakage'):
                c.leakage([P,row])

    def test_cross_split_exact_duplicate(self):
        row=deepcopy(P);row['example_id']='other';row['split']='dev'
        for field in c.GROUPS:row[field]+='-new'
        with self.assertRaisesRegex(ValueError,'Exact duplicate'):c.leakage([P,row])

    def test_regression_flag(self):
        row=deepcopy(P);row['provenance']['public_regression']=True
        with self.assertRaisesRegex(ValueError,'regression'):c.leakage([row])

    def test_regression_hash(self):
        value=c.digest(' '.join(P['source_text'].split()).encode('utf-8'))
        with self.assertRaisesRegex(ValueError,'regression'):c.leakage([P],{value})

    def test_schema_missing_fields_and_unknowns(self):
        import jsonschema
        for field in P:
            row=deepcopy(P);del row[field]
            with self.subTest(field=field),self.assertRaises(jsonschema.ValidationError):c.validate_record(row)
        row=deepcopy(P);row['unknown']='value'
        with self.assertRaises(jsonschema.ValidationError):c.validate_record(row)

    def test_invalid_gold(self):
        for kind in ('missing_ref','irrelevant_ref','context_ownership','duplicate_ownership','status_contradiction','unsupported_addition','copied_prose'):
            row=deepcopy(P);row['gold_target']=json.loads(candidate(P,kind)['raw'])
            row['adjudication']['first_judgment']=deepcopy(row['gold_target']);row['adjudication']['final_target']=deepcopy(row['gold_target'])
            with self.subTest(kind=kind),self.assertRaises(ValueError):c.validate_record(row)

    def test_missing_gold_claim(self):
        row=deepcopy(P);row['gold_target']['items'][0]['claims'].pop()
        row['adjudication']['first_judgment']=deepcopy(row['gold_target']);row['adjudication']['final_target']=deepcopy(row['gold_target'])
        with self.assertRaisesRegex(ValueError,'explicit claim'):c.validate_record(row)

    def test_privacy_rights_refusal_uncertainty(self):
        for field,value in [('privacy','operator_private'),('rights','unknown')]:
            row=deepcopy(P);row['provenance'][field]=value
            with self.assertRaises(ValueError):c.validate_record(row)
        row=deepcopy(P);row['expected_refusal']=True
        with self.assertRaises(ValueError):c.validate_record(row)
        row=deepcopy(P);row['expected_uncertainty']=False
        with self.assertRaises(ValueError):c.validate_record(row)

    def test_production_rule_attribution_gold_rejected(self):
        row=deepcopy(A);row['gold_target']['items'][0]['reasoning']+=' CONV-INVENTED'
        row['adjudication']['first_judgment']=deepcopy(row['gold_target']);row['adjudication']['final_target']=deepcopy(row['gold_target'])
        with self.assertRaises(ValueError):c.validate_record(row)

    def test_governance(self):
        policy=dict(producer_family='qwen2',auditor_family='llama',self_audit=False,privacy='authored_public_synthetic',
                    operator_authorized=True,training=False,multi_round=False,paid_api=False,provenance_verified=True)
        self.assertTrue(c.governance(policy))
        for field,value in [('auditor_family','qwen2'),('self_audit',True),('privacy','private'),('operator_authorized',False),
                            ('training',True),('multi_round',True),('paid_api',True),('provenance_verified',False)]:
            with self.subTest(field=field),self.assertRaises(ValueError):c.governance(dict(policy,**{field:value}))

    def test_acceptance_not_configured(self):
        self.assertEqual(c.acceptance([],c.read(HERE/'acceptance_registration.template.json'))['decision'],'NOT_PREREGISTERED')

    def test_error_taxonomy_and_aggregation(self):
        rows=[c.evaluate(P,'bad'),c.evaluate(A,'bad',truncated=True)]
        self.assertTrue(all(set(r['error_classes'])<=set(c.ERRORS) for r in rows))
        report=c.aggregate(rows)
        self.assertIn('per_family',report);self.assertIn('per_role',report)
        self.assertEqual(report['aggregate']['accepted_outcome']['count'],0)

    def test_strict_json_no_fences_trailing_prefix_duplicates(self):
        raw=json.dumps(A['gold_target'])
        for value in ('```json\n'+raw+'\n```',raw+' Extra',raw[:-2],'{"items":[],"items":[]}'):
            self.assertFalse(c.evaluate(A,value)['accepted_outcome'])

    def test_malformed_types_fail_closed(self):
        values=[None,[],1,{'items':[None]},{'items':{}},{'items':[{'span':{}}]}]
        obj=deepcopy(P['gold_target']);obj['items'][0]['span']={};values.append(obj)
        obj=deepcopy(A['gold_target']);obj['items'][0]['finding']=[];values.append(obj)
        for value in values:
            for row in (P,A):
                with self.subTest(value=value,role=row['role']):
                    self.assertFalse(c.evaluate(row,json.dumps(value))['accepted_outcome'])

    def test_manifest_and_negative_ancestry_drift(self):
        import run_gate
        original=c.read
        def changed(path):
            value=original(path)
            if Path(path).name=='negative_candidates.json':value[0]['split']='dev'
            return value
        with patch.object(c,'read',changed),self.assertRaises(ValueError):run_gate.validate_artifacts(ROWS)

    def test_split_plan_precedes_variants(self):
        import run_gate
        changed=deepcopy(ROWS);changed[0]['split']='dev'
        with self.assertRaisesRegex(ValueError,'after allocation'):run_gate.validate_artifacts(changed)

    def test_acceptance_cannot_promote_public_seed(self):
        registration=dict(state='preregistered',registered_before_run=True,rationale='Synthetic interface test.',
                          dataset_sha256='synthetic-hash',minimum_families=1,minimum_contract_rate=.99)
        score=c.evaluate(P,json.dumps(P['gold_target']))
        self.assertEqual(c.acceptance([score],registration)['decision'],'UNVERIFIED_EVALUATION_CONTEXT')

    def test_saved_output_interface(self):
        from evaluate_outputs import score_saved
        candidate=dict(example_id=P['example_id'],raw=json.dumps(P['gold_target']),truncated=False,completed=True,
                       provenance='authored_diagnostic',source_run_id='synthetic-interface-test')
        scored=score_saved([candidate],ROWS,'train')
        self.assertEqual(scored['coverage']['supplied'],1)
        self.assertTrue(scored['results'][0]['accepted_outcome'])
        with self.assertRaises(ValueError):score_saved([candidate,candidate],ROWS,'train')
        with self.assertRaises(ValueError):score_saved([candidate],ROWS,'test')

    def test_prompt_inputs_exclude_gold_and_context_ownership(self):
        for row in (P,A):
            rendered=c.render_task(row)
            changed=deepcopy(row);changed['gold_target']={'sentinel':'never in model input'}
            changed['adjudication']={'sentinel':'never in model input'}
            self.assertEqual(rendered,c.render_task(changed))
            self.assertNotIn('never in model input',rendered)
        self.assertIn('context_only',c.render_task(P))
        auditor=c.render_task(A)
        owned_json=auditor[len(c.cc.AUDITOR)+1:].split('\n')[0]
        self.assertNotIn('CONTEXT ONLY:',json.loads(owned_json)['ORIGINAL'])
        self.assertIn('CONV-DISTRACTOR',auditor)

    def test_effect_proofs(self):
        # Explicit observations must fail under neutralisation and pass again
        # after context-manager restoration; an exception alone is not proof.
        raw=json.dumps(A['gold_target'])+' trailing prose'
        def strict_guard():return not c.evaluate(A,raw)['accepted_outcome']
        self.assertTrue(strict_guard())
        with patch.object(c,'strict_json',lambda text:json.JSONDecoder().raw_decode(text)[0]):
            self.assertFalse(strict_guard())
        self.assertTrue(strict_guard())
        obj=deepcopy(A['gold_target']);obj['items'][0]['ref_ids'].append('REF-9999')
        def ref_guard():return not c.evaluate(A,json.dumps(obj))['accepted_outcome']
        self.assertTrue(ref_guard())
        with patch.object(c,'evidence',lambda *a:dict(tp=2,fp=0,fn=0,precision=1,recall=1,invented=0,hallucinated_rate=0)):
            self.assertFalse(ref_guard())
        self.assertTrue(ref_guard())
        other=deepcopy(next(r for r in ROWS if r['split']=='dev' and r['role']=='producer' and r['abstract_relation']=='EXTRACTED'))
        other['document_family']=P['document_family']
        def family_guard():
            try:c.leakage([P,other]);return False
            except ValueError:return True
        self.assertTrue(family_guard())
        # Disable only the actual family dimensions. Exact duplicate and
        # ancestry checks remain live; this pair has distinct source texts.
        with patch.object(c,'GROUPS',()):
            self.assertFalse(family_guard())
        self.assertTrue(family_guard())


if __name__=='__main__':unittest.main()
