"""DECODING-B proofs for the envelope constraint of the local auditor agents, with no real model.

The fixture tokenizer and stand-in model of contract_decoding_checks, writing as their top
choice each envelope failure shape L8, L11 and L12 recorded for VERIFIER and PRACTICE_AUDITOR
on local_auditor (s5_diag_b3 K9 and K11): the envelope left unclosed (the stop token after the
items), the reply stopped inside an item, an item closed without a required key (VERIFIER's
reasoning, PRACTICE_AUDITOR's explanation), a raw control character inside a string, and text
running on after a string that closed too early. Each shape is written twice: with the
constraint the reply is the valid one the model ranked next, and the envelope validator
(agent_wrapper.parse_contract_output and _contract_missing, unchanged) accepts it; with the
constraint off the same model writes the failure and the validator refuses it with the reason
the runs recorded. A reply that runs to the output cap is not prevented (the constraint cannot
make a reply shorter), and is refused as before. A valid reply, fenced, pretty-printed or with
text after the envelope, is never changed. The real call_local carries the constraint for a
declared agent and records it; every other call carries none. Check 297.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / 'scripts'), str(ROOT / 'benchmark' / 'baselines')):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import torch

import agent_wrapper
import compact_contracts as cc
import contract_decoding as cd
import contract_decoding_checks as base
import decoding_policy

EOS = base.EOS
# Pieces that cross the boundaries the envelope grammar cares about, so a token is admitted only
# when its WHOLE text keeps the reply in the language.
PIECES = ['{"agent": "', '", "doc_id": "', '", "items": [', '{"ref": "', '", "kind": "', '", "confidence": "',
          '"}]}', '"}, {', '", "', '": "', '": ', ', "', '"explanation"', '"value_a"', '"reasoning"',
          '```json\n', '\n```', '  ', '\n  ', '}]}', ']}', 'REF-', 'CONFIDENT', 'finding', '\\n', '\n']
CAP = 400
AUDITOR_STOPS = decoding_policy.policy('local_auditor')['kwargs']['eos_token_id']


class EnvelopeTokenizer(base.FixtureTokenizer):
    """Printable ASCII one character a token, the PIECES above, and three special tokens."""

    def __init__(self):
        pieces = []
        for piece in [chr(c) for c in range(32, 127)] + PIECES:
            if piece not in pieces:
                pieces.append(piece)
        self.vocab = ['<eos>', '<pad>', '<unk>'] + pieces
        self.index = {p: i for i, p in enumerate(self.vocab) if i > base.UNK}
        self.longest = max(len(p) for p in self.index)


def envelope(agent, items, doc='d1', indent=None):
    return json.dumps(dict(agent=agent, doc_id=doc, items=items), indent=indent)


def verifier_item(**extra):
    value = dict(ref='REF-0001', kind='finding', confidence='CONFIDENT', paragraph=1, finding='MATCH',
                 severity='low', reasoning='Paragraph one matches the extraction.', ref_ids=['REF-0001'])
    value.update(extra)
    return value


def auditor_item(drop=(), **extra):
    value = dict(ref='REF-0002', kind='finding', confidence='CONFIDENT', procedure_id='CONV-001', verdict='VIOLATION',
                 relation='missing_field', record_verdict='irregular',
                 explanation='The unit names no reviewer.', ref_ids=['REF-0002'])
    value.update(extra)
    return {k: v for k, v in value.items() if k not in drop}


V_VALID = envelope('VERIFIER', [verifier_item()])
P_VALID = envelope('PRACTICE_AUDITOR', [auditor_item()])
# PRACTICE_AUDITOR's three saved replies without an explanation wrote the figures where the
# explanation belonged (L8 08, L11 14, L12 18).
P_NO_EXPLANATION = envelope('PRACTICE_AUDITOR', [auditor_item(drop=('explanation', 'ref_ids'), value_a=23.6, unit_a='mL',
                                                              value_b=24.4, unit_b='mL', ref_ids=['REF-0002'])])
V_NO_REASONING = V_VALID.replace(', "reasoning": "Paragraph one matches the extraction."', '')
P_EARLY_QUOTE = P_VALID.replace('"The unit names no reviewer.", "ref_ids"',
                                '"The unit names ", no reviewer for it.", "ref_ids"')
P_EARLY_QUOTE_FIXED = P_VALID.replace('"The unit names no reviewer.", "ref_ids"', '"The unit names ", "ref_ids"')
# Each failure shape, as (agent, the model's top choice, the valid reply it ranked next, the
# validator's reasons in the runs).
KINDS = {
    'K11_envelope_unclosed': ('VERIFIER', V_VALID[:-1], V_VALID, ['not a canonical envelope {agent:str, doc_id:str, items:list}']),
    'K11_stopped_inside_an_item': ('VERIFIER', V_VALID[:V_VALID.index(', "ref_ids"')], V_VALID,
                                   ['no JSON object found in output']),
    'K9_missing_explanation': ('PRACTICE_AUDITOR', P_NO_EXPLANATION, P_VALID, ['items[0].explanation']),
    'K11_missing_required_key': ('VERIFIER', V_NO_REASONING, V_VALID, ['items[0].reasoning']),
    'K11_control_character_in_a_string': ('VERIFIER', V_VALID.replace('one matches', 'one\nmatches'),
                                          V_VALID.replace('one matches', 'one\\nmatches'),
                                          ['json parse failure: Invalid control character']),
    'K9_text_after_an_early_quote': ('PRACTICE_AUDITOR', P_EARLY_QUOTE, P_EARLY_QUOTE_FIXED,
                                     ['not a canonical envelope {agent:str, doc_id:str, items:list}']),
}
# A valid reply in every form the saved valid replies take: compact, pretty-printed, fenced, with
# a note after the envelope, the fence closed and a stray brace after it, enumerated values the
# contract does not declare (which the validator accepts), and the declared confidence alias.
VALID_FORMS = {
    'compact_verifier': ('VERIFIER', V_VALID),
    'pretty_verifier': ('VERIFIER', envelope('VERIFIER', [verifier_item(paragraph='2', finding='MISSING_FIELD',
                                                                        rule_id='CONV-001', value_a=3, unit_a='m')], indent=2)),
    'fenced_auditor': ('PRACTICE_AUDITOR', '```json\n' + P_VALID + '\n```'),
    'note_after': ('VERIFIER', V_VALID + '\n\n(Note: one paragraph.)'),
    'stray_brace_after_fence': ('PRACTICE_AUDITOR', '```json\n' + P_VALID + '\n```\n}\n'),
    'undeclared_verdict_value': ('PRACTICE_AUDITOR', envelope('PRACTICE_AUDITOR', [auditor_item(verdict='UNCERTAIN')])),
    'empty_items':('PRACTICE_AUDITOR', envelope('PRACTICE_AUDITOR', [])),
    'two_items': ('VERIFIER', envelope('VERIFIER', [verifier_item(), verifier_item(ref='REF-0003', severity='HIGH')])),
}


def validator(agent):
    """The envelope validator as the run applies it: agent_wrapper's parser on a wrapper that
    carries the agent's contract, unchanged."""
    wrapper = object.__new__(agent_wrapper.AgentWrapper)
    wrapper.name, wrapper.contract = agent, cd.declared_contracts()['contracts'][agent]
    return wrapper


def reasons(agent, reply, truncated=False):
    """The validator's reasons for a reply ([] when it holds its contract); a truncated reply also
    carries run_task's own completeness reason (under the optimized semantics)."""
    parsed, missing = validator(agent).parse_contract_output(reply)
    missing = list(missing) if parsed is not None or missing else ['no JSON object found in output']
    return missing + (['response completeness not established'] if truncated else [])


def contract_of(agent):
    spec = cd.envelope_declaration()[0]
    return cd.EnvelopeContract.for_agent(agent, spec, root=ROOT), spec


def decode(agent, intended, fallback, constrained, cap=CAP):
    """(reply, record, truncated) from the stand-in model writing `intended`."""
    tok = EnvelopeTokenizer()
    model = base.StandInModel(tok, intended, fallback)
    prompt = tok('<prompt>')['input_ids']
    record, extra = None, {}
    if constrained:
        constraint = cd.envelope_constraint(agent, tok, prompt.shape[1], [EOS], 'fixture')
        extra, record = constraint.generate_kwargs(), constraint.record
    out = model.generate(prompt, cap, eos_token_id=[EOS], **extra)
    generated = out[0, prompt.shape[1]:].tolist()
    truncated = len(generated) >= cap and generated[-1] != EOS
    return tok.decode(generated), record, truncated


class EnvelopeDecodingChecks(unittest.TestCase):
    def test_declaration_is_the_validators_own(self):
        """The core keys are the validator's CORE_ITEM_REQUIRED; each declared agent's required
        keys are its contract's `required` after them, the order every saved valid item writes
        them; the backend is the agent's local-profile backend (the pipeline's _LOCAL_PROFILE
        row, read as text); a declared alias is admitted."""
        import re
        spec, _ = cd.envelope_declaration()
        self.assertEqual(tuple(spec['core_required']), agent_wrapper.CORE_ITEM_REQUIRED)
        self.assertEqual(spec['status'], 'active')
        profile = (ROOT / 'scripts' / 'pipeline.py').read_text(encoding='utf-8')
        declared = cd.declared_contracts()
        for agent, row in spec['agents'].items():
            contract, _ = contract_of(agent)
            self.assertEqual(list(contract.required), spec['core_required'] + declared['contracts'][agent]['required'])
            self.assertIn('confident', contract.spellings[contract.required.index('confidence')])
            self.assertRegex(profile, r'"%s":\s*\("%s",' % (agent, re.escape(row['backend'])))
            for name in spec['core_optional']:
                self.assertIn(name, declared['envelope'])

    def test_each_failure_shape_is_prevented_and_the_validator_passes(self):
        for name, (agent, intended, fallback, _) in KINDS.items():
            with self.subTest(kind=name):
                self.assertEqual(reasons(agent, fallback), [])
                reply, record, truncated = decode(agent, intended, fallback, constrained=True)
                self.assertEqual(reply, fallback)
                self.assertFalse(truncated)
                self.assertEqual(reasons(agent, reply), [])
                self.assertGreaterEqual(record['interventions'], 1)
                self.assertFalse(record['dead_end'])

    def test_constraint_off_reproduces_each_failure(self):
        for name, (agent, intended, fallback, expected) in KINDS.items():
            with self.subTest(kind=name):
                reply, _, truncated = decode(agent, intended, fallback, constrained=False)
                self.assertEqual(reply, intended)
                self.assertFalse(truncated)
                found = reasons(agent, reply)
                self.assertEqual(len(found), len(expected), found)
                for got, want in zip(found, expected):
                    self.assertTrue(got.startswith(want), (got, want))

    def test_a_reply_at_the_output_cap_is_not_prevented(self):
        """An item list that runs to the cap (VERIFIER in L8 20, L12 02, 18 and 19) is truncated
        with and without the constraint, and refused by the validator both times."""
        runaway = V_VALID[:-2] + ''.join(', ' + json.dumps(verifier_item(ref='REF-%04d' % i)) for i in range(2, 60)) + ']}'
        for constrained in (False, True):
            reply, record, truncated = decode('VERIFIER', runaway, runaway, constrained=constrained)
            self.assertTrue(truncated)
            self.assertEqual(reasons('VERIFIER', reply, truncated),
                             ['not a canonical envelope {agent:str, doc_id:str, items:list}',
                              'response completeness not established'])
            if constrained:
                self.assertEqual(record['interventions'], 0)

    def test_a_valid_reply_is_never_changed(self):
        for name, (agent, text) in VALID_FORMS.items():
            with self.subTest(form=name):
                self.assertEqual(reasons(agent, text), [])
                reply, record, _ = decode(agent, text, text, constrained=True)
                self.assertEqual(reply, text)
                self.assertEqual(record['interventions'], 0)
                self.assertFalse(record['dead_end'])

    def test_language_rules(self):
        """The grammar requires what the validator requires and the envelope closed; it admits
        every form the saved valid replies take."""
        contract, spec = contract_of('PRACTICE_AUDITOR')
        item = auditor_item()
        for name, (agent, text) in VALID_FORMS.items():
            self.assertTrue(cd.envelope_accepts(contract_of(agent)[0], spec, text), name)
        aliased = dict((('confident' if k == 'confidence' else k), v) for k, v in item.items())
        self.assertTrue(cd.envelope_accepts(contract, spec, envelope('PRACTICE_AUDITOR', [aliased])))
        bad = {
            'required_null': envelope('PRACTICE_AUDITOR', [dict(item, explanation=None)]),
            'required_empty': envelope('PRACTICE_AUDITOR', [dict(item, explanation='')]),
            'required_missing': P_NO_EXPLANATION,
            'required_out_of_order': envelope('PRACTICE_AUDITOR', [dict([('kind', 'finding')] + [(k, v) for k, v in item.items() if k != 'kind'])]),
            'nested_object': envelope('PRACTICE_AUDITOR', [dict(item, record={'a': 1})]),
            'array_of_objects': envelope('PRACTICE_AUDITOR', [dict(item, ref_ids=[{'a': 1}])]),
            'undeclared_key': envelope('PRACTICE_AUDITOR', [dict(item, colour='blue')]),
            'other_agent': envelope('VERIFIER', [item]),
            'extra_top_level_key': P_VALID[:-1] + ', "note": "x"}',
            'top_level_order': json.dumps(dict(doc_id='d1', agent='PRACTICE_AUDITOR', items=[item])),
            'item_not_an_object': envelope('PRACTICE_AUDITOR', ['text']),
            'unclosed': P_VALID[:-1],
            'text_before': 'Here it is: ' + P_VALID,
            'long_whitespace_run': P_VALID.replace(', "kind"', ',' + ' ' * (spec['whitespace_run_max'] + 1) + '"kind"'),
        }
        for name, text in bad.items():
            self.assertFalse(cd.envelope_accepts(contract, spec, text), name)
        duplicate = P_VALID.replace('"ref_ids": ["REF-0002"]', '"ref_ids": ["REF-0002"], "ref_ids": []')
        self.assertFalse(cd.envelope_accepts(contract, spec, duplicate))

    def test_the_wrapper_carries_the_constraint_and_records_it(self):
        """call_local on VERIFIER and PRACTICE_AUDITOR (local_auditor): generate() receives the
        frozen decoding kwargs unchanged plus the logits processor, the reply is the valid one,
        and the reply record and the usage carry the constraint with the agent. EDITOR_CLERK
        (local_producer), an unbound PROCESSOR and a VERIFIER bound to the compact auditor
        contract carry none."""
        tok = EnvelopeTokenizer()

        def call(wrapper, intended, fallback, run_dir):
            model = base.StandInModel(tok, intended, fallback)
            wrapper.run_context = SimpleNamespace(run_dir=str(run_dir), run_id='fixture',
                                                  logs_dir=lambda: Path(run_dir) / 'logs')
            with patch.dict(os.environ, SHIMMER_MODEL_MODE='base'), \
                    patch.object(agent_wrapper, '_load_qwen', return_value=(tok, model)):
                result = wrapper.call_local('plain prompt', max_new_tokens=CAP)
            return result, model.calls[0]

        def wrapper(name, backend):
            w = object.__new__(agent_wrapper.AgentWrapper)
            w.name, w.backend, w.model, w.cost_tracker = name, backend, 'fixture', None
            w._optimized_semantics = True
            return w

        policy = decoding_policy.policy('local_auditor')['kwargs']
        with tempfile.TemporaryDirectory() as tmp:
            for agent, (intended, fallback) in (('VERIFIER', (KINDS['K11_envelope_unclosed'][1], V_VALID)),
                                                ('PRACTICE_AUDITOR', (P_NO_EXPLANATION, P_VALID))):
                result, sent = call(wrapper(agent, 'local_auditor'), intended, fallback, Path(tmp) / agent)
                self.assertTrue(result.ok, result.error)
                self.assertEqual(result.raw_text, fallback)
                self.assertEqual(reasons(agent, result.raw_text), [])
                self.assertEqual({k: sent[k] for k in policy}, policy)
                self.assertEqual([type(p).__name__ for p in sent['logits_processor']], ['ContractProcessor'])
                usage = result.usage['decoding_constraint']
                spec = cd.envelope_declaration()[0]
                self.assertEqual((usage['name'], usage['version'], usage['source'], usage['agent']),
                                 (spec['name'], spec['version'], 'contract', agent))
                self.assertEqual(usage['contract_sha256'], contract_of(agent)[0].digest())
                self.assertGreaterEqual(usage['interventions'], 1)
                record = json.loads(next((Path(tmp) / agent / 'audit' / 'model_replies').glob('*.json')).read_text(encoding='utf-8'))
                self.assertEqual(record['decoding_constraint'], usage)
                self.assertEqual(record['decoding']['decoding_kwargs'], policy)
            bound = wrapper('VERIFIER', 'local_auditor')
            cc.bind_auditor(bound, 'd1', ['REF-0001'])
            for name, plain in (('EDITOR_CLERK', wrapper('EDITOR_CLERK', 'local_producer')),
                                ('PROCESSOR', wrapper('PROCESSOR', 'local_producer')), ('VERIFIER_compact', bound)):
                result, sent = call(plain, V_VALID, V_VALID, Path(tmp) / name)
                self.assertIsNone(sent['logits_processor'])
                self.assertNotIn('decoding_constraint', result.usage)
                record = json.loads(next((Path(tmp) / name / 'audit' / 'model_replies').glob('*.json')).read_text(encoding='utf-8'))
                self.assertNotIn('decoding_constraint', record)

    def test_admitted_tokens_are_kept_per_state_and_equal_a_fresh_computation(self):
        """The envelope grammar's states carry no text, so each state's admitted tokens are kept
        on the token table; a kept answer equals one computed afresh, token for token."""
        tok = EnvelopeTokenizer()
        constraint = cd.envelope_constraint('VERIFIER', tok, 1, [EOS], 'fixture')
        processor, grammar = constraint.processor, constraint.processor.grammar
        state = grammar.start()
        for ch in V_VALID[:120]:
            ids, free = processor.admitted(state)
            fresh, fresh_free = processor._admitted(state)
            self.assertEqual(sorted(ids), sorted(fresh))
            self.assertEqual(free is None, fresh_free is None)
            state = grammar.step(state, ch)
        self.assertGreater(len(processor.table.admitted_cache), 10)

    def test_the_saved_reply_measurement(self):
        """tools/envelope_decoding_measure.py on reply records: a valid reply in each saved form
        passes token by token with 0 interventions, a failed one is acted on where it leaves the
        language, another agent's record is not read, and nothing of a reply is written."""
        sys.path.insert(0, str(ROOT / 'tools'))
        import envelope_decoding_measure as measure
        import reply_records
        with tempfile.TemporaryDirectory() as tmp:
            context = SimpleNamespace(run_dir=str(Path(tmp) / 'run'), run_id='r')
            rows = [(agent, text, 'accepted_to_bus') for agent, text in VALID_FORMS.values()]
            rows += [('PRACTICE_AUDITOR', P_NO_EXPLANATION, 'contract_violation'), ('EDITOR_CLERK', V_VALID[:-1], 'accepted_to_bus')]
            for i, (agent, text, outcome) in enumerate(rows):
                call = reply_records.write(context, agent=agent, call_id='c%02d' % i,
                                           backend='local_producer' if agent == 'EDITOR_CLERK' else 'local_auditor',
                                           model_id='m', payload='prompt', payload_form='rendered_prompt', reply=text)
                reply_records.write_outcome(context, call, outcome, source='fixture')
            result = measure.measure([Path(tmp) / 'run' / 'audit' / 'model_replies'], EnvelopeTokenizer(), [EOS])
        self.assertEqual(result['valid_replies_with_intervention'], [])
        self.assertEqual(sum(v for k, v in result['counts'].items() if k.endswith('/valid/replies')), len(VALID_FORMS))
        self.assertEqual(sum(v for k, v in result['counts'].items() if k.endswith('/valid/inside_the_language')), len(VALID_FORMS))
        self.assertEqual([(r['call_id'], r['leaves_at'][1]) for r in result['failed_replies']], [('c%02d' % len(VALID_FORMS), 'kn')])
        self.assertGreaterEqual(result['failed_replies'][0]['interventions'], 1)
        self.assertNotIn('EDITOR_CLERK', json.dumps(result))
        self.assertNotIn('no reviewer', json.dumps(result))

    def test_replay_extracts_and_validates_auditor_prompts(self):
        """replay_prompts extract --agents keeps the named local_auditor agents' calls, with each
        prompt's agent and backend, counted under the set its --call-ids entry names; run validates their replies with the envelope validator and,
        on the constrained path, builds the envelope constraint of the prompt's own agent; a
        prompts file mixing models is refused."""
        import hashlib
        import reply_records
        import replay_prompts
        with tempfile.TemporaryDirectory() as tmp:
            context = SimpleNamespace(run_dir=str(Path(tmp) / 'run'), run_id='r')
            kept = reply_records.write(context, agent='PRACTICE_AUDITOR', call_id='pa', backend='local_auditor', model_id='m',
                                       payload='<user>judge<assistant>', payload_form='rendered_prompt', reply=P_NO_EXPLANATION,
                                       decoding={'max_new_tokens': CAP})
            reply_records.write(context, agent='EDITOR_CLERK', call_id='ec', backend='local_producer', model_id='m',
                                payload='prompt two', payload_form='rendered_prompt', reply='R2')
            folder = Path(tmp) / 'run' / 'audit' / 'model_replies'
            value = replay_prompts.extract([folder], Path(tmp) / 'p.json', agents={'PRACTICE_AUDITOR', 'VERIFIER'},
                                           call_ids={kept: 'failed'})
            self.assertEqual(value['prompt_count'], 1)
            self.assertEqual((value['prompts'][0]['agent'], value['prompts'][0]['backend'], value['prompts'][0]['source_call_id']),
                             ('PRACTICE_AUDITOR', 'local_auditor', kept))
            self.assertNotIn(P_NO_EXPLANATION, (Path(tmp) / 'p.json').read_text(encoding='utf-8'))
            tok = EnvelopeTokenizer()

            class Backend:
                def prepare(self):
                    return {'model_id': 'fixture', 'digest': 'd', 'checkpoint': 'base'}

                def count(self, text):
                    return len(tok.encode(text))

                def max_context(self):
                    return 10 ** 6

                def generate(self, text, attention, max_new_tokens, constraint=False, agent=None):
                    model = base.StandInModel(tok, P_NO_EXPLANATION, P_VALID)
                    ids = tok(text)['input_ids']
                    built = cd.for_prompt(text, tok, ids.shape[1], [EOS], agent=agent) if constraint else None
                    out = model.generate(ids, max_new_tokens, eos_token_id=[EOS], **(built.generate_kwargs() if built else {}))
                    generated = out[0, ids.shape[1]:].tolist()
                    result = {'text': tok.decode(generated), 'output_tokens': len(generated),
                              'attention': attention, 'prefill': {'chunks': 0}, 'truncated': generated[-1] != EOS}
                    if built is not None:
                        result['decoding_constraint'] = built.summary()
                    return result
            reader = dict(decoding=decoding_policy.policy('local_auditor'), model_id='fixture', model_mode='base',
                          max_new_tokens=CAP)
            result = replay_prompts.run(Path(tmp) / 'p.json', Path(tmp) / 'out', paths=['sdpa', 'sdpa_constrained'],
                                        backend=Backend(), reader=reader)
            text = (Path(tmp) / 'out' / replay_prompts.MEASUREMENT_FILE).read_text(encoding='utf-8')
            self.assertNotIn('no reviewer', text)
            self.assertEqual(result['validity']['sdpa']['failed'],
                             dict(contract_prompts=1, replied=1, valid=0, reasons={'items[0].explanation': 1}))
            self.assertEqual(result['validity']['sdpa_constrained']['failed'],
                             dict(contract_prompts=1, replied=1, valid=1, reasons={}))
            self.assertEqual(result['reference']['sdpa']['failed']['byte_identical'], 1)
            self.assertEqual(result['constraint']['sdpa_constrained']['failed']['calls_with_intervention'], 1)
            mixed = json.loads((Path(tmp) / 'p.json').read_text(encoding='utf-8'))
            other = dict(mixed['prompts'][0], prompt_id='p0002', backend='local_producer', agent='PROCESSOR')
            mixed['prompts'].append(other)
            mixed['prompt_count'] = 2
            (Path(tmp) / 'mixed.json').write_text(json.dumps(mixed), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'one model'):
                replay_prompts.run(Path(tmp) / 'mixed.json', Path(tmp) / 'out2', paths=['sdpa'], backend=Backend(), reader=reader)
            self.assertEqual(hashlib.sha256(P_NO_EXPLANATION.encode()).hexdigest(), value['prompts'][0]['reference_reply_sha256'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
