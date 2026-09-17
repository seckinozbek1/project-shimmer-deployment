"""Deterministic ordinary pairing fixtures. No model/provider execution."""
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import auditor_pairs as pairs
import bounded_extraction as extraction
import final_models
import model_telemetry


class PairChecks(unittest.TestCase):
    def setUp(self):
        self.doc=dict(id='fixture-doc',text='First explicit source.\n\nSecond explicit source.')
        self.spans=extraction.ledger(self.doc['text'],self.doc['id'],max_chars=1200)
        self.item=dict(item_id='PROCESSOR:fixture:a',revision=1,claims_referenced=['CLM-1'],open_questions=[],uncertainty=[])
        self.refs=[dict(ref_id='REF-0001',document_id=self.doc['id'],input_type='operational',
                        location={},text_excerpt='First explicit source.'),
                   dict(ref_id='REF-0002',document_id=self.doc['id'],input_type='operational',
                        location={},text_excerpt='Second explicit source.')]

    def producer(self, items=None, source_ids=None):
        items=copy.deepcopy(items if items is not None else [self.item])
        return dict(ok=True,truncated=False,call_id='producer-call',parsed=dict(items=items),source_ownership=[dict(
            producer_item_id=i['item_id'],producer_revision=i['revision'],item_hash=pairs.item_hash(i),
            producer_call_id='producer-call',source_span_ids=source_ids or [self.spans[0].id]) for i in items])

    def wrapper(self, producer=None):
        return SimpleNamespace(name='VERIFIER',backend='local_auditor',run_context=None,
            _parent_call_ids=['producer-call'],_auditor_pair_request=dict(document=self.doc,
                producer=producer if producer is not None else self.producer(),references=self.refs))

    def prepare(self, wrapper, predictions=('MATCH',)):
        events=[]
        with patch.dict(os.environ,SHIMMER_MODEL_MODE='final'), \
             patch.object(pairs,'predict',side_effect=[(x,10) if isinstance(x,str) else x for x in predictions]), \
             patch.object(model_telemetry,'emit',side_effect=lambda c,event,**k:events.append(dict(event=event,**k))):
            payload=pairs.prepare_context(wrapper,dict(task=pairs.TASK))
        return payload,events

    def test_match_and_omission_single_pair(self):
        for label in ('MATCH','OMISSION'):
            payload,events=self.prepare(self.wrapper(),[label])
            record=payload['auditor_pair_context']['pairs'][0]
            self.assertEqual(record['auditor_relation'],label)
            self.assertEqual(record['source_evidence']['text'],self.spans[0].text)
            self.assertEqual(record['producer_item'],pairs.semantic_item(self.item))
            self.assertFalse(any('source_evidence' in e for e in events))

    def test_two_items_have_independent_decisions(self):
        items=[self.item,dict(self.item,item_id='PROCESSOR:fixture:b')]
        payload,_=self.prepare(self.wrapper(self.producer(items)),['MATCH','OMISSION'])
        records=payload['auditor_pair_context']['pairs']
        self.assertEqual([r['auditor_relation'] for r in records],['MATCH','OMISSION'])
        self.assertNotEqual(records[0]['pair_id'],records[1]['pair_id'])

    def test_multiple_explicit_reference_pairs(self):
        producer=self.producer([dict(self.item,ref_ids=['REF-0001','REF-0002'])]);producer['source_ownership']=[]
        payload,_=self.prepare(self.wrapper(producer),['MATCH','ADDITION'])
        records=payload['auditor_pair_context']['pairs']
        self.assertEqual(len(records),2)
        self.assertEqual([r['source_ref_ids'] for r in records],[['REF-0001'],['REF-0002']])

    def test_canonical_single_ref_requires_exact_index_binding(self):
        p=self.producer([dict(self.item,ref='REF-0001')]);p['source_ownership']=[]
        result,missing,_=pairs.build('run',self.doc,p,self.refs)
        self.assertFalse(missing);self.assertEqual(result[0]['record']['source_ref_ids'],['REF-0001'])
        p['parsed']['items'][0]['ref']='document-level'
        self.assertEqual(pairs.build('run',self.doc,p,self.refs)[0],[])

    def test_pair_id_deterministic_and_revision_bound(self):
        a=pairs.build('run',self.doc,self.producer(),self.refs)[0][0]['record']
        b=pairs.build('run',self.doc,self.producer(),self.refs)[0][0]['record']
        self.assertEqual(a['pair_id'],b['pair_id'])
        newer=pairs.build('run',self.doc,self.producer([dict(self.item,revision=2)]),self.refs)[0][0]['record']
        self.assertNotEqual(a['pair_id'],newer['pair_id'])
        with self.assertRaises(ValueError):pairs.validate(dict(a,producer_revision=99))

    def test_ownership_excludes_invalid_span_and_foreign_ref(self):
        bad=self.producer(source_ids=['nonexistent'])
        self.assertEqual(pairs.build('run',self.doc,bad,self.refs)[0],[])
        bad=self.producer([dict(self.item,ref_ids=['REF-0001'])]);bad['source_ownership']=[]
        wrong=[dict(self.refs[0],document_id='other-doc')]
        self.assertEqual(pairs.build('run',self.doc,bad,wrong)[0],[])

    def test_no_guess_from_paragraph_or_prose(self):
        p=self.producer([dict(self.item,paragraph=1,original=self.doc['text'],reasoning='REF-0001',source_span_id=self.spans[0].id)])
        p['source_ownership']=[]
        result,missing,_=pairs.build('run',self.doc,p,self.refs)
        self.assertEqual(result,[]);self.assertEqual(missing[0]['status'],'AUDITOR_PAIR_UNAVAILABLE')
        w=self.wrapper(p)
        payload,events=self.prepare(w,[])
        self.assertEqual(payload['auditor_pair_context']['pairs'],[])
        self.assertTrue(any(e['event']=='auditor_pair_unavailable' for e in events))

    def test_stale_revision_excluded(self):
        old=dict(self.item,ref_ids=['REF-0001']);new=dict(old,revision=2)
        p=self.producer([old,new]);p['source_ownership']=[]
        result,missing,_=pairs.build('run',self.doc,p,self.refs)
        self.assertEqual([p['record']['producer_revision'] for p in result],[2])
        self.assertEqual(missing[0]['reason'],'stale_or_invalid_producer_revision')

    def test_changed_revision_or_content_invalidates_receipt(self):
        for changes in (dict(revision=2),dict(claims_referenced=['CLM-CHANGED'])):
            p=self.producer();p['parsed']['items'][0].update(changes)
            self.assertEqual(pairs.build('run',self.doc,p,self.refs)[0],[])

    def test_incomplete_delivery_and_missing_refs(self):
        for changes in (dict(ok=False),dict(truncated=True),dict(truncated=None),dict(complete=False)):
            p=self.producer();p.update(changes)
            self.assertEqual(pairs.build('run',self.doc,p,self.refs)[0],[])
        result,_,_=pairs.build('run',self.doc,self.producer(),[])
        self.assertEqual(len(result),1)  # Owned span needs no invented REF.
        self.assertEqual(result[0]['record']['source_ref_ids'],[])

    def test_classifier_failure_preserved_without_findings(self):
        w=self.wrapper();payload,events=self.prepare(w,[RuntimeError('fixture numerical failure')])
        self.assertEqual(payload['auditor_pair_context']['pairs'][0]['classifier_status'],'failed')
        self.assertIsNone(payload['auditor_pair_context']['pairs'][0]['auditor_relation'])
        self.assertNotIn('findings',payload)
        self.assertEqual(sum(e['event']=='model_call' for e in events),1)

    def test_multiple_findings_not_relabelled_and_join_only_explicit(self):
        w=self.wrapper();payload,_=self.prepare(w,['MATCH'])
        pid=payload['auditor_pair_context']['pairs'][0]['pair_id']
        items=[dict(item_id='f1',finding='OMISSION',auditor_pair_id=pid),dict(item_id='f2',finding='ADDITION',paragraph=1)]
        result=dict(ok=True,call_id='verifier-call',parsed=dict(items=items))
        before=copy.deepcopy(result);events=[]
        with patch.object(model_telemetry,'emit',side_effect=lambda c,event,**k:events.append(k)):
            pairs.compare(w,result)
        self.assertEqual(result,before)
        self.assertEqual(events[0]['findings'][0]['agreement'],'disagree')
        self.assertEqual(events[0]['findings'][0]['auditor_pair_id'],pid)
        self.assertIsNone(events[0]['findings'][1]['auditor_pair_id'])

    def test_exact_identity_join_and_ambiguous_join(self):
        w=self.wrapper();self.prepare(w,['MATCH']);record=w._auditor_pair_state[0]
        fields={k:record[k] for k in ('producer_item_id','producer_revision','source_span_id')}
        self.assertEqual(pairs.finding_pair(fields,[record]),record)
        self.assertIsNone(pairs.finding_pair(dict(fields,producer_revision=0),[record]))
        self.assertIsNone(pairs.finding_pair(fields,[record,dict(record,pair_id='another')]))

    def test_empty_and_refusal_unchanged(self):
        for parsed in (dict(items=[]),dict(items=[],status='refused')):
            w=self.wrapper();self.prepare(w,['OMISSION']);result=dict(ok=False,parsed=parsed)
            before=copy.deepcopy(result);events=[]
            with patch.object(model_telemetry,'emit',side_effect=lambda c,event,**k:events.append(k)):
                pairs.compare(w,result)
            self.assertEqual(result,before);self.assertTrue(events[0]['empty'])
            self.assertEqual(events[0]['refused'],parsed.get('status')=='refused')

    def test_only_ordinary_verifier_can_activate(self):
        with patch.dict(os.environ,SHIMMER_MODEL_MODE='final'):
            for name in ('FACT_CHECKER','PRACTICE_AUDITOR','STYLE_GUARDIAN','EDITOR_DG','PROCESSOR'):
                w=self.wrapper();w.name=name
                self.assertFalse(pairs.eligible(w,dict(task=pairs.TASK)))
            self.assertFalse(pairs.eligible(self.wrapper(),dict(task='strategic_review')))
        with patch.dict(os.environ,SHIMMER_MODEL_MODE='base'):
            self.assertFalse(pairs.eligible(self.wrapper(),dict(task=pairs.TASK)))

    def test_real_serialization_and_predict_boundary_with_fake_model(self):
        pair=pairs.build('run',self.doc,self.producer(),self.refs)[0][0]
        seen=[]
        tokenizer=SimpleNamespace(apply_chat_template=lambda messages,**k:seen.append(messages) or [1,2,3])
        classifier=SimpleNamespace(model=SimpleNamespace(config=SimpleNamespace(max_position_embeddings=10)),
            predict=lambda ids,directory:'OMISSION')
        with patch.object(final_models,'resident',return_value=(tokenizer,classifier)) as loader:
            self.assertEqual(pairs.predict(pair,None),('OMISSION',3))
        loader.assert_called_once_with('auditor',None)
        value=json.loads(seen[0][1]['content'])
        self.assertEqual(len(value['source_spans']),1)
        self.assertEqual(value['source_spans'][0]['text'],self.spans[0].text)
        self.assertNotIn('relation',value)

    def test_startup_requires_runtime_artifacts_and_contract(self):
        with patch.dict(os.environ,SHIMMER_MODEL_MODE='final'),patch.object(final_models,'verify_runtime') as runtime:
            final_models.admit_ordinary();runtime.assert_called_once()
            with patch.object(pairs,'contract_self_check',return_value=False):
                with self.assertRaises(RuntimeError):final_models.admit_ordinary()
            with patch.object(final_models,'verify',side_effect=RuntimeError('mixed artifact')):
                with self.assertRaises(RuntimeError):final_models.admit_ordinary()
            with patch.object(final_models,'verify_runtime',side_effect=RuntimeError('invalid runtime')):
                with self.assertRaises(RuntimeError):final_models.admit_ordinary()

    def test_live_wrapper_receives_advisory_context_keeps_multiple_findings(self):
        from report_recommendations_checks import RecommendationChecks
        from agent_wrapper import CallResult
        fixture=RecommendationChecks();fixture.setUp()
        try:
            w=fixture.wrapper('VERIFIER');w._auditor_pair_request=self.wrapper()._auditor_pair_request
            w._parent_call_ids=['producer-call'];seen=[]
            items=[dict(paragraph=i+1,finding=label,severity='low',reasoning='fixture reason',
                        ref='document-level',kind='finding',confidence='UNCERTAIN')
                   for i,label in enumerate(('MATCH','OMISSION'))]
            def backend(prompt,**kwargs):
                seen.append(prompt)
                r=CallResult('local_auditor','fixture_a',json.dumps(dict(agent='VERIFIER',doc_id=self.doc['id'],items=items)),
                             usage=dict(truncated=False,input_tokens=10,output_tokens=10))
                w._record_cost(r);return r
            w.call_local=backend
            with patch.dict(os.environ,SHIMMER_MODEL_MODE='final'),patch.object(pairs,'predict',return_value=('ADDITION',10)):
                result=w.run_task(work_payload=dict(task=pairs.TASK,document_id=self.doc['id']),phase='5')
            self.assertTrue(result['ok'])
            self.assertEqual([i['finding'] for i in result['parsed']['items']],['MATCH','OMISSION'])
            self.assertIn('auditor_pair_context',seen[0]);self.assertIn('ADDITION',seen[0])
            raw=[json.loads(line) for line in (fixture.ctx.logs_dir()/'model_telemetry.jsonl').read_text().splitlines()]
            summary=model_telemetry.summarize(raw)
            self.assertEqual(summary['auditor_pairing']['classifier_calls'],1)
            self.assertEqual(summary['auditor_pairing']['unjoined_findings'],2)
            self.assertEqual(len(summary['auditor_pairing']['auditor_to_verifier']),1)
            self.assertGreaterEqual(summary['auditor_pairing']['auditor_to_verifier'][0]['seconds'],0)
        finally:fixture.doCleanups()

    def test_compact_ownership_is_stamped_and_survives_partition_merge(self):
        from compact_contracts import bind_producer
        from compact_contract_checks import wrapper
        w=wrapper('PROCESSOR');bind_producer(w,self.spans,self.doc['id'])
        wire=dict(items=[dict(span=extraction.wire_id(s),claims=[],questions=[],uncertainty=[],status='empty',refs=[]) for s in self.spans])
        parsed,missing=w.parse_contract_output(json.dumps(wire));self.assertFalse(missing)
        result=dict(ok=True,truncated=False,call_id='partition-call',parsed=parsed)
        pairs.stamp_ownership(w,result)
        merged=extraction.merge([result],self.doc['id'])
        built,unavailable,_=pairs.build('run',self.doc,merged,[])
        self.assertFalse(unavailable);self.assertEqual(len(built),len(self.spans))
        self.assertTrue(all(p['record']['producer_call_id']=='partition-call' for p in built))

    def test_consumer_barrier_and_wave_summary(self):
        from final_integration_checks import call
        raw=[call('p',0,2),call('a',3,5,'auditor',['p']),call('v',6,9,'auditor',['a'])]
        events=[]
        for key,start,end,parent in [('p',0,2,[]),('a',3,5,['p']),('v',6,9,['a'])]:
            events.extend([dict(event='queued',task=key,monotonic_s=start,edges=[dict(parent=p) for p in parent]),
                dict(event='task_start',task=key,monotonic_s=start,worker='lane'),
                dict(event='task_end',task=key,monotonic_s=end)])
        events.append(dict(event='phase_enter',phase='synthesis',monotonic_s=10,required_tasks=['p','a','v']))
        summary=model_telemetry.summarize(raw,events)
        self.assertEqual(summary['semantic_critical_path']['members'],['p','a','v'])
        self.assertEqual(summary['consumer_barriers'][0]['after_latest_auditor_seconds'],1)
        self.assertEqual(summary['wave_intervals']['wave-a']['end'],5)

    def test_live_failure_missing_pairs_and_refusal_preserve_verifier_behavior(self):
        from report_recommendations_checks import RecommendationChecks
        from agent_wrapper import CallResult
        fixture=RecommendationChecks();fixture.setUp()
        try:
            for unavailable in (False,True):
                for refused in (False,True):
                    wire=dict(agent='VERIFIER',doc_id=self.doc['id'],items=[])
                    if refused:wire['status']='refused'
                    outcomes=[]
                    for mode in ('base','final'):
                        w=fixture.wrapper('VERIFIER');request=self.wrapper()._auditor_pair_request
                        if unavailable:request['producer']['source_ownership']=[]
                        w._auditor_pair_request=request
                        calls=[]
                        def backend(prompt,**kwargs):
                            calls.append(prompt)
                            result=CallResult('local_auditor','fixture_a',json.dumps(wire),usage=dict(truncated=False))
                            w._record_cost(result);return result
                        w.call_local=backend
                        with patch.dict(os.environ,SHIMMER_MODEL_MODE=mode),patch.object(pairs,'predict',side_effect=RuntimeError('fixture')):
                            r=w.run_task(work_payload=dict(task=pairs.TASK,document_id=self.doc['id']))
                        self.assertEqual(len(calls),1)
                        outcomes.append((r['ok'],r['error'],r['parsed'],r['contract_missing']))
                    self.assertEqual(outcomes[0],outcomes[1])
        finally:fixture.doCleanups()


if __name__=='__main__':unittest.main()
