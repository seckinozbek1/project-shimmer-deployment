"""Deterministic authored semantics, strict contracts, no model or pipeline run."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import bounded_extraction as ex
import compact_contracts as cc
from agent_wrapper import AgentWrapper

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT/'docs/fix/compact_contract_ab/fixture.json').read_text())
REFS = ['REF-0001','REF-0002']
REASON = 'Both labeled capacities and the missing reporting date are preserved without additions or omissions.'


def extraction_wire(spans):
    import re
    return dict(items=[dict(span=ex.wire_id(s), claims=re.findall(r'\bCLM-[A-Za-z0-9-]+', s.text),
                           questions=[], uncertainty=[], status='extracted' if 'CLM-' in s.text else 'empty',
                           refs=re.findall(r'\bREF-\d{4,}\b', s.text)) for s in spans])


def representative_producer():
    obj = extraction_wire(ex.ledger(FIXTURE['source'], FIXTURE['doc']))
    obj['items'][0]['questions'] = ['What is the reporting date?']
    return obj


def representative_auditor():
    return dict(items=[dict(finding='MATCH', ref_ids=REFS, reasoning=REASON, severity='low', confidence='CONFIDENT')])


def wrapper(name):
    w = object.__new__(AgentWrapper)
    w.name = name
    w.contract = json.loads((ROOT/'config/agent_contracts.json').read_text())['contracts'][name]
    return w


class ProducerChecks(unittest.TestCase):
    def hydrate(self, source, value=None):
        spans = ex.ledger(source, 'fixture')
        result = cc.producer(value or extraction_wire(spans), spans, 'fixture')
        self.assertEqual(''.join(i['draft_text'] for i in result['items']), source)
        self.assertEqual([i['source_start'] for i in result['items']], sorted(s.start for s in spans))
        return result

    def test_normal_claim(self):
        self.assertEqual(self.hydrate('CLM-003: Capacity 7 (REF-0003).')['items'][0]['claims_referenced'], ['CLM-003'])

    def test_separate_spans_and_reverse_wire_order(self):
        source = '## Alpha\nCLM-001: A.\n\n## Beta\nCLM-002: B.'
        spans = ex.ledger(source,'fixture'); self.assertGreater(len(spans),1)
        obj = extraction_wire(spans); obj['items'].reverse(); self.hydrate(source,obj)

    def test_missing_date(self):
        result = cc.producer(representative_producer(), ex.ledger(FIXTURE['source'],FIXTURE['doc']),FIXTURE['doc'])
        self.assertEqual(result['items'][0]['open_questions'], ['What is the reporting date?'])
        self.assertEqual(result['items'][0]['draft_text'], FIXTURE['source'])

    def test_explicit_empty_semantics(self):
        self.assertEqual(self.hydrate('Section heading')['items'][0]['extraction_status'],'empty')

    def test_question_gap(self):
        source='Which date applies?'; obj=extraction_wire(ex.ledger(source,'fixture'))
        obj['items'][0].update(questions=[source],status='extracted')
        self.assertEqual(self.hydrate(source,obj)['items'][0]['open_questions'],[source])

    def bad(self, edit):
        spans=ex.ledger(FIXTURE['source'],FIXTURE['doc']); obj=representative_producer(); edit(obj)
        with self.assertRaises(ValueError): cc.producer(obj,spans,FIXTURE['doc'])

    def test_duplicate_semantic_observation(self):
        self.bad(lambda o:o['items'][0]['claims'].append('CLM-001'))

    def test_malformed_alias(self):
        self.bad(lambda o:o['items'][0].update(span=['s0']))

    def test_outside_owned_alias(self):
        self.bad(lambda o:o['items'][0].update(span='sffff'))
        spans=ex.ledger('## Alpha\nCLM-001: A.\n\n## Beta\nCLM-002: B.','fixture')
        with self.assertRaises(ValueError):cc.producer(extraction_wire(spans),spans[:1],'fixture')

    def test_omitted_owned_span(self):
        self.bad(lambda o:o.update(items=[]))

    def test_copied_source_prose(self):
        self.bad(lambda o:o['items'][0].update(draft_text=FIXTURE['source']))
        self.bad(lambda o:o['items'][0].update(span=FIXTURE['source']))

    def test_duplicate_ownership(self):
        self.bad(lambda o:o['items'].append(copy.deepcopy(o['items'][0])))

    def test_refusal_and_incomplete_status(self):
        self.bad(lambda o:o.update(status='refused',items=[]))
        self.bad(lambda o:o['items'][0].update(status='incomplete'))

    def test_unknown_claim_and_evidence(self):
        self.bad(lambda o:o['items'][0].update(claims=['CLM-999']))
        self.bad(lambda o:o['items'][0].update(refs=['REF-9999']))

    def test_empty_cannot_hide_semantics(self):
        self.bad(lambda o:o['items'][0].update(status='empty'))

    def test_live_canonical_validator_and_prompt(self):
        w=wrapper('PROCESSOR'); cc.bind_producer(w,ex.ledger(FIXTURE['source'],FIXTURE['doc']),FIXTURE['doc'])
        obj,missing=w.parse_contract_output(json.dumps(representative_producer()))
        self.assertEqual(missing,[]); self.assertEqual(obj['items'][0]['draft_text'],FIXTURE['source'])
        self.assertEqual(w._output_contract_text(),cc.PRODUCER)
        self.assertNotIn('draft_text',w._role_anchor_text())


class AuditorChecks(unittest.TestCase):
    def adapt(self, obj=None, **kw):
        return cc.auditor(obj if obj is not None else representative_auditor(),FIXTURE['doc'],REFS,REFS,**kw)

    def test_authored_match_reason_both_refs(self):
        item=self.adapt()['items'][0]
        self.assertEqual(item['finding'],'MATCH'); self.assertEqual(item['reasoning'],REASON)
        self.assertEqual(item['ref_ids'],REFS); self.assertNotIn('CONV-001',json.dumps(item))

    def test_real_divergence(self):
        changed=copy.deepcopy(FIXTURE['extraction'])
        changed['items'][0]['draft_text']=FIXTURE['source'].replace('130','140')
        self.assertNotEqual(changed['items'][0]['draft_text'],FIXTURE['source'])
        prompt=cc.auditor_prompt(FIXTURE['source'],changed,REFS)
        self.assertIn('130',prompt);self.assertIn('140',prompt)
        obj=representative_auditor(); obj['items'][0].update(finding='DIVERGENCE',severity='medium',reasoning='Extraction changes the reported capacity from 130 to 140; planned capacity remains 120.')
        self.assertEqual(self.adapt(obj)['items'][0]['finding'],'DIVERGENCE')

    def test_insufficient_evidence_refused(self):
        with self.assertRaises(ValueError): self.adapt(dict(items=[],status='refused'))

    def test_two_evidence_refs_preserved(self):
        self.assertEqual(self.adapt()['items'][0]['ref_ids'],REFS)

    def test_missing_reference(self):
        obj=representative_auditor(); obj['items'][0]['ref_ids']=REFS[:1]
        with self.assertRaises(ValueError):self.adapt(obj)

    def test_ungrounded_rule(self):
        for field,value in [('rule_id','CONV-001'),('reasoning','CONV-001 requires equality')]:
            obj=representative_auditor();obj['items'][0][field]=value
            with self.assertRaises(ValueError):self.adapt(obj)

    def test_malformed_envelope(self):
        with self.assertRaises(ValueError):self.adapt(dict(items={}))

    def test_valid_empty_only_for_empty_input(self):
        self.assertEqual(cc.auditor(dict(items=[]),'empty',[],[],empty_input=True)['items'],[])
        with self.assertRaises(ValueError):self.adapt(dict(items=[]))

    def test_concise_complete_canonical(self):
        w=wrapper('VERIFIER');cc.bind_auditor(w,FIXTURE['doc'],REFS)
        obj,missing=w.parse_contract_output(json.dumps(representative_auditor()))
        self.assertEqual(missing,[]);self.assertEqual(obj['items'][0]['paragraph'],1)

    def test_verbose_reason_no_validator_relaxation(self):
        obj=representative_auditor();obj['items'][0]['reasoning']=REASON+' The extraction retains the planned label, reported label, units, quantities and unanswered date question.'*12
        self.assertEqual(self.adapt(obj)['items'][0]['reasoning'],obj['items'][0]['reasoning'])

    def test_truncated_or_prefix_never_recovered(self):
        w=wrapper('VERIFIER');cc.bind_auditor(w,FIXTURE['doc'],REFS)
        raw=json.dumps(representative_auditor())
        for broken in (raw[:-1],raw+'{"items":[', 'prefix '+raw):
            self.assertTrue(w.parse_contract_output(broken)[1])

    def test_unknown_evidence_and_no_reason(self):
        for changes in [dict(ref_ids=REFS+['REF-9999']),dict(reasoning='REF-9999 supports this'),dict(reasoning=''),dict(finding='irregular')]:
            obj=representative_auditor();obj['items'][0].update(changes)
            with self.assertRaises(ValueError):self.adapt(obj)

    def test_old_remote_outputs_still_refused(self):
        evidence=json.loads((ROOT/'docs/fix/remote_short_burst_secure_20260915/evidence/probe/probe.json').read_text())
        for call in evidence['calls']:
            if call['label'] not in {'compact_processor','independent_auditor'}:continue
            w=wrapper('PROCESSOR' if call['role']=='active_producer' else 'VERIFIER')
            if w.name=='PROCESSOR':cc.bind_producer(w,ex.ledger(FIXTURE['source'],FIXTURE['doc']),FIXTURE['doc'])
            else:cc.bind_auditor(w,FIXTURE['doc'],REFS)
            self.assertTrue(w.parse_contract_output(call['raw_text'])[1])

    def test_maintained_probe_uses_measured_prompt_builders(self):
        import ast
        tree=ast.parse((ROOT/'tools/remote_short_burst_probe.py').read_text())
        functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in {'producer_prompt','audit_prompt'}]
        scope=dict(cc=cc,json=json,doc=FIXTURE['doc'],source=FIXTURE['source'],spans=ex.ledger(FIXTURE['source'],FIXTURE['doc']))
        exec(compile(ast.Module(body=functions,type_ignores=[]),'live_probe_prompt_builders','exec'),scope)
        self.assertEqual(scope['producer_prompt'](None,True),cc.producer_prompt(scope['spans'],scope['spans'],FIXTURE['doc']))
        self.assertEqual(scope['audit_prompt'](None,FIXTURE['extraction']),cc.auditor_prompt(FIXTURE['source'],FIXTURE['extraction'],REFS))


if __name__ == '__main__': unittest.main()
