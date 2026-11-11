"""DECODING-B proofs for the envelope constraint of the local auditor agents, with no real model.

The fixture tokenizer and stand-in model of contract_decoding_checks, writing as their top
choice each envelope failure shape L8, L11 and L12 recorded for VERIFIER and PRACTICE_AUDITOR
on local_auditor (s5_diag_b3 K9 and K11): the envelope left unclosed (the stop token after the
items), the reply stopped inside an item, an item closed without a required key (VERIFIER's
reasoning, PRACTICE_AUDITOR's explanation), a raw control character inside a string, and text
running on after a string that closed too early; ARCHIVIST's item without its confidence key
and EDITOR_CLERK's item without `kind` on local_producer (the shape the K8 stamp, removed at the
S5 close, used to supply). Each shape is written twice: with the
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
# S10 item 2.1 a: the one input this module's tests need that a tree may lack is the replay tool
# (the container image ships no benchmark/); the test that needs it skips naming it, and the gate
# check runs the rest.
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
# Two saved valid replies (L12 24) write the explanation last, after the figures: the model's
# own completion of the same shape.
P_EXPLANATION_LAST = P_NO_EXPLANATION[:-3] + ', "explanation": "The figures differ."}]}'
V_NO_REASONING = V_VALID.replace(', "reasoning": "Paragraph one matches the extraction."', '')
P_EARLY_QUOTE = P_VALID.replace('"The unit names no reviewer.", "ref_ids"',
                                '"The unit names ", no reviewer for it.", "ref_ids"')
P_EARLY_QUOTE_FIXED = P_VALID.replace('"The unit names no reviewer.", "ref_ids"', '"The unit names ", "ref_ids"')


def archivist_item(**extra):
    """An inventory item in the key order most saved valid ARCHIVIST items write: the confidence
    key (as the declared alias) first, the rest in the model's own order."""
    value = dict(confident='CONFIDENT', document_count=2, document_names=['a', 'b'], element='Review cycle',
                 description='Both documents state a review cycle.', kind='inventory', ref='REF-0005', ref_ids=['REF-0005'])
    value.update(extra)
    return value


A_VALID = envelope('ARCHIVIST', [archivist_item()])
# ARCHIVIST's two saved replies without a confidence key (L8 06, L12 21, the same document) opened
# their item with the element and never wrote one.
A_NO_CONFIDENCE = envelope('ARCHIVIST', [{k: v for k, v in archivist_item().items() if k != 'confident'}])
A_NO_CONFIDENCE = A_NO_CONFIDENCE.replace('{"document_count"', '{"element": "Review cycle", "document_count"', 1)     .replace(', "element": "Review cycle"', '', 1)
A_FIXED = envelope('ARCHIVIST', [dict([('confident', 'CONFIDENT'), ('element', 'Review cycle')]
                                      + [(k, v) for k, v in archivist_item().items() if k not in ('confident', 'element')])])


def editor_clerk_item(**extra):
    """An editorial observation in the key order 21 of the 49 saved valid EDITOR_CLERK items
    write: the confidence key (as the declared alias) first, the rest in sorted order."""
    value = dict(confident='CONFIDENT', kind='editorial_observation', rationale='The heading names no owner.',
                 ref='REF-0010', ref_ids=['REF-0010'], verdict='concern')
    value.update(extra)
    return value


E_VALID = envelope('EDITOR_CLERK', [editor_clerk_item()])
# EDITOR_CLERK's twelve saved replies without a kind (L8 30, L11 02, 04, 08, and the eight the
# removed K8 stamp accepted in L12 and L12b) wrote the confidence key, then ref, rationale,
# ref_ids and verdict, and closed the item.
E_NO_KIND = envelope('EDITOR_CLERK', [dict((k, editor_clerk_item()[k]) for k in
                                           ('confident', 'ref', 'rationale', 'ref_ids', 'verdict'))])
# One saved valid reply (L12 31) writes the same keys and then kind, last: the model's own
# completion of the same shape.
E_KIND_LAST = E_NO_KIND[:-3] + ', "kind": "editorial_observation"}]}'
# Each failure shape, as (agent, the model's top choice, the valid reply it ranked next, the
# validator's reasons in the runs).
KINDS = {
    'K11_envelope_unclosed': ('VERIFIER', V_VALID[:-1], V_VALID, ['not a canonical envelope {agent:str, doc_id:str, items:list}']),
    'K11_stopped_inside_an_item': ('VERIFIER', V_VALID[:V_VALID.index(', "ref_ids"')], V_VALID,
                                   ['no JSON object found in output']),
    'K9_missing_explanation': ('PRACTICE_AUDITOR', P_NO_EXPLANATION, P_EXPLANATION_LAST, ['items[0].explanation']),
    'K11_missing_required_key': ('VERIFIER', V_NO_REASONING, V_VALID, ['items[0].reasoning']),
    'K11_control_character_in_a_string': ('VERIFIER', V_VALID.replace('one matches', 'one\nmatches'),
                                          V_VALID.replace('one matches', 'one\\nmatches'),
                                          ['json parse failure: Invalid control character']),
    'K9_text_after_an_early_quote': ('PRACTICE_AUDITOR', P_EARLY_QUOTE, P_EARLY_QUOTE_FIXED,
                                     ['not a canonical envelope {agent:str, doc_id:str, items:list}']),
    'K10_missing_confidence': ('ARCHIVIST', A_NO_CONFIDENCE, A_FIXED, ['items[0].confidence']),
    'K8_missing_kind': ('EDITOR_CLERK', E_NO_KIND, E_KIND_LAST, ['items[0].kind']),
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
    'auditor_explanation_last': ('PRACTICE_AUDITOR', P_EXPLANATION_LAST),
    'archivist_inventory': ('ARCHIVIST', A_VALID),
    'archivist_other_order_and_runtime_key': ('ARCHIVIST', envelope('ARCHIVIST', [
        dict([('confident', 'CONFIDENT'), ('ref', 'REF-0005'), ('kind', 'inventory'), ('title', None), ('ts', 'x')])])),
    'editor_clerk_observation': ('EDITOR_CLERK', E_VALID),
    'editor_clerk_canonical_confidence': ('EDITOR_CLERK', envelope('EDITOR_CLERK', [
        dict([('confidence', 'UNCERTAIN')] + [(k, v) for k, v in editor_clerk_item().items() if k != 'confident'])])),
    'editor_clerk_kind_last': ('EDITOR_CLERK', E_KIND_LAST.replace('"confident"', '"confidence"')),
    'editor_clerk_empty': ('EDITOR_CLERK', envelope('EDITOR_CLERK', [])),
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
        them; the backend is the agent's local-profile backend (its `local` block in the
        registry, D-S57 item 2); a declared alias is admitted."""
        spec, _ = cd.envelope_declaration()
        self.assertEqual(tuple(spec['core_required']), agent_wrapper.CORE_ITEM_REQUIRED)
        self.assertEqual(spec['status'], 'active')
        registry = json.loads((ROOT / 'config' / 'agent_registry.json').read_text(encoding='utf-8'))['agents']
        declared = cd.declared_contracts()
        for agent, row in spec['agents'].items():
            contract, _ = contract_of(agent)
            # A contract key that is also a core key (EDITOR_CLERK's ref) is checked once.
            self.assertEqual(list(contract.required), spec['core_required'] + [
                k for k in declared['contracts'][agent]['required'] if k not in spec['core_required']])
            self.assertIn('confident', contract.spellings[contract.required.index('confidence')])
            self.assertEqual(registry[agent]['local']['backend'], row['backend'])
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
        archivist, _ = contract_of('ARCHIVIST')
        self.assertEqual(archivist.leading, ('confidence',))
        reordered = envelope('ARCHIVIST', [dict([('confidence', 'UNCERTAIN'), ('kind', 'inventory'), ('ref', 'REF-1')])])
        self.assertTrue(cd.envelope_accepts(archivist, spec, reordered))
        for name, text in {'confidence_not_first': A_NO_CONFIDENCE,
                           'kind_missing': envelope('ARCHIVIST', [dict(confident='CONFIDENT', ref='REF-1')]),
                           'duplicate_key': A_VALID.replace('"document_count": 2', '"document_count": 2, "document_count": 3'),
                           'confidence_twice': envelope('ARCHIVIST', [dict(confident='CONFIDENT', confidence='CONFIDENT',
                                                                           ref='REF-1', kind='inventory')])}.items():
            self.assertFalse(cd.envelope_accepts(archivist, spec, text), name)
        clerk, _ = contract_of('EDITOR_CLERK')
        self.assertEqual(clerk.leading, ('confidence',))
        self.assertEqual(clerk.required, ('ref', 'kind', 'confidence', 'verdict', 'rationale'))
        for name, text in {'kind_missing': E_NO_KIND,
                           'kind_empty': envelope('EDITOR_CLERK', [editor_clerk_item(kind='')]),
                           'kind_null': envelope('EDITOR_CLERK', [editor_clerk_item(kind=None)]),
                           'confidence_not_first': envelope('EDITOR_CLERK', [dict(
                               [('kind', 'editorial_observation')]
                               + [(k, v) for k, v in editor_clerk_item().items() if k != 'kind'])]),
                           'one_of_two_items_without_kind': envelope('EDITOR_CLERK', [
                               editor_clerk_item(), json.loads(E_NO_KIND)['items'][0]])}.items():
            self.assertFalse(cd.envelope_accepts(clerk, spec, text), name)

    def test_editor_clerk_missing_kind_is_prevented_through_the_wrapper(self):
        """The cause the removed K8 stamp papered over, fixed where it arises: call_local on
        EDITOR_CLERK (local_producer), the stand-in writing the saved shape without `kind` as its
        top choice, returns the reply the model ranked next (kind written last, as one saved
        valid reply writes it), and the envelope validator, which supplies nothing, accepts it.
        Neutralised by dropping EDITOR_CLERK from the declaration and by letting an item close
        before every required key is written."""
        tok = EnvelopeTokenizer()
        model = base.StandInModel(tok, E_NO_KIND, E_KIND_LAST)
        w = object.__new__(agent_wrapper.AgentWrapper)
        w.name, w.backend, w.model, w.cost_tracker = 'EDITOR_CLERK', 'local_producer', 'fixture', None
        w._optimized_semantics = True
        with tempfile.TemporaryDirectory() as tmp:
            w.run_context = SimpleNamespace(run_dir=tmp, run_id='fixture', logs_dir=lambda: Path(tmp) / 'logs')
            with patch.dict(os.environ, SHIMMER_MODEL_MODE='base'), \
                    patch.object(agent_wrapper, '_load_qwen', return_value=(tok, model)):
                result = w.call_local('plain prompt', max_new_tokens=CAP)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.raw_text, E_KIND_LAST)
        self.assertEqual(reasons('EDITOR_CLERK', result.raw_text), [])
        self.assertEqual(reasons('EDITOR_CLERK', E_NO_KIND), ['items[0].kind'])
        self.assertEqual(result.usage['decoding_constraint']['agent'], 'EDITOR_CLERK')
        self.assertGreaterEqual(result.usage['decoding_constraint']['interventions'], 1)

    def test_the_wrapper_carries_the_constraint_and_records_it(self):
        """call_local on VERIFIER and PRACTICE_AUDITOR (local_auditor) and ARCHIVIST and
        EDITOR_CLERK (local_producer): generate() receives the frozen decoding kwargs unchanged
        plus the logits processor, the reply is the valid one, and the reply record and the usage
        carry the constraint with the agent. CITATION_RESOLVER (local_producer, undeclared), an
        unbound PROCESSOR and a VERIFIER bound to the compact auditor contract carry none."""
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

        with tempfile.TemporaryDirectory() as tmp:
            for agent, backend, (intended, fallback) in (
                    ('VERIFIER', 'local_auditor', (KINDS['K11_envelope_unclosed'][1], V_VALID)),
                    ('PRACTICE_AUDITOR', 'local_auditor', (P_NO_EXPLANATION, P_EXPLANATION_LAST)),
                    ('ARCHIVIST', 'local_producer', (A_NO_CONFIDENCE, A_FIXED)),
                    ('EDITOR_CLERK', 'local_producer', (E_NO_KIND, E_KIND_LAST))):
                policy = decoding_policy.policy(backend)['kwargs']
                result, sent = call(wrapper(agent, backend), intended, fallback, Path(tmp) / agent)
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
            for name, plain in (('CITATION_RESOLVER', wrapper('CITATION_RESOLVER', 'local_producer')),
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
        language, a reply the run accepted only through a value Python supplied (the removed K8
        kind stamp, read from the run's observation log) is counted apart and listed with the
        failed ones, another agent's record is not read, and nothing of a reply is written."""
        sys.path.insert(0, str(ROOT / 'tools'))
        import envelope_decoding_measure as measure
        import reply_records
        with tempfile.TemporaryDirectory() as tmp:
            context = SimpleNamespace(run_dir=str(Path(tmp) / 'run'), run_id='r')
            rows = [(agent, text, 'accepted_to_bus') for agent, text in VALID_FORMS.values()]
            rows += [('PRACTICE_AUDITOR', P_NO_EXPLANATION, 'contract_violation'),
                     ('CITATION_RESOLVER', V_VALID[:-1], 'accepted_to_bus'), ('EDITOR_CLERK', E_NO_KIND, 'accepted_to_bus')]
            for i, (agent, text, outcome) in enumerate(rows):
                call = reply_records.write(context, agent=agent, call_id='c%02d' % i,
                                           backend='local_producer' if agent in ('CITATION_RESOLVER', 'ARCHIVIST', 'EDITOR_CLERK')
                                           else 'local_auditor',
                                           model_id='m', payload='prompt', payload_form='rendered_prompt', reply=text)
                reply_records.write_outcome(context, call, outcome, source='fixture')
            stamped = 'c%02d' % (len(rows) - 1)
            logs = Path(tmp) / 'run' / 'logs'
            logs.mkdir()
            (logs / 'generation_observation.jsonl').write_text(json.dumps(dict(
                agent='EDITOR_CLERK', call_id=stamped, contract_valid=True,
                contract_normalized=['items[0].confident->confidence', 'items[0].kind<-editorial_observation'])) + '\n',
                encoding='utf-8')
            result = measure.measure([Path(tmp) / 'run' / 'audit' / 'model_replies'], EnvelopeTokenizer(), [EOS])
        self.assertEqual(result['valid_replies_with_intervention'], [])
        self.assertEqual(sum(v for k, v in result['counts'].items() if k.endswith('/valid/replies')), len(VALID_FORMS))
        self.assertEqual(sum(v for k, v in result['counts'].items() if k.endswith('/valid/inside_the_language')), len(VALID_FORMS))
        self.assertEqual((result['counts']['EDITOR_CLERK/stamped/replies'],
                          result['counts']['EDITOR_CLERK/stamped/inside_the_language']), (1, 0))
        self.assertEqual([(r['call_id'], r['stamped'], r['leaves_at'][1]) for r in result['failed_replies']],
                         [('c%02d' % len(VALID_FORMS), False, 'gap>K'), (stamped, True, 'gap>K')])
        self.assertTrue(all(r['interventions'] >= 1 for r in result['failed_replies']))
        self.assertNotIn('CITATION_RESOLVER', json.dumps(result))
        self.assertNotIn('no reviewer', json.dumps(result))
        self.assertNotIn('names no owner', json.dumps(result))

    def test_replay_extracts_and_validates_auditor_prompts(self):
        """replay_prompts extract --agents keeps the named local_auditor agents' calls, with each
        prompt's agent and backend, counted under the set its --call-ids entry names; run validates their replies with the envelope validator and,
        on the constrained path, builds the envelope constraint of the prompt's own agent; a
        prompts file mixing models is refused."""
        base.need(self, base.REPLAY_TOOL)  # S10 item 2.1 a: the image ships no benchmark/
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
                    model = base.StandInModel(tok, P_NO_EXPLANATION, P_EXPLANATION_LAST)
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

    def test_roles_file_replays_each_prompt_on_its_own_checkpoint(self):
        """D-S57: extract --checkpoints tuned,base writes each producer role prompt once per
        checkpoint, adjacent, the saved reply the tuned row's reference only; run prepares each
        checkpoint's backend once before the first call, sends each row to its own checkpoint,
        judges every reply by its agent's own contract and counts the pairs (valid on both, on
        one only, on neither) per set; an agent with no contract, a constrained path on a
        non-compact prompt and a missing backend are refused."""
        base.need(self, base.REPLAY_TOOL)
        import hashlib
        import reply_records
        import replay_prompts
        valid = envelope('LEGAL_ANALYST', [dict(ref='REF-0001', kind='finding', confidence='CONFIDENT', claim_id='CLM-1',
                                                verdict='GROUNDED', reasoning='Stated in the passage.', ref_ids=['REF-0001'])])
        broken = valid.replace(', "reasoning": "Stated in the passage."', '')
        with tempfile.TemporaryDirectory() as tmp:
            context = SimpleNamespace(run_dir=str(Path(tmp) / 'run'), run_id='r')
            ids = [reply_records.write(context, agent='LEGAL_ANALYST', call_id='la%d' % i, backend='local_producer',
                                       model_id='m', model_mode='final', payload='<user>role prompt %d<assistant>' % i,
                                       payload_form='rendered_prompt', reply=valid, decoding={'max_new_tokens': CAP})
                   for i in range(2)]
            folder = Path(tmp) / 'run' / 'audit' / 'model_replies'
            value = replay_prompts.extract([folder], Path(tmp) / 'roles.json', checkpoints=['tuned', 'base'],
                                           call_ids={i: 'legal_analyst' for i in ids})
            self.assertEqual(value['prompt_count'], 4)
            rows = value['prompts']
            self.assertEqual([(r['checkpoint'], r['pair_of']) for r in rows],
                             [('tuned', rows[0]['pair_of']), ('base', rows[0]['pair_of']),
                              ('tuned', rows[2]['pair_of']), ('base', rows[2]['pair_of'])])
            self.assertEqual(rows[0]['reference_reply_sha256'], hashlib.sha256(valid.encode()).hexdigest())
            self.assertIsNone(rows[1]['reference_reply_sha256'])
            self.assertNotIn(valid, (Path(tmp) / 'roles.json').read_text(encoding='utf-8'))
            with self.assertRaisesRegex(ValueError, 'not with --agents'):
                replay_prompts.extract([folder], Path(tmp) / 'x.json', checkpoints=['tuned'], agents={'VERIFIER'})
            with self.assertRaisesRegex(ValueError, 'each checkpoint once'):
                replay_prompts.extract([folder], Path(tmp) / 'x.json', checkpoints=['tuned', 'tuned'])
            events = []
            tok = EnvelopeTokenizer()

            class Backend:
                def __init__(self, name, replies):
                    self.name, self.replies = name, list(replies)

                def prepare(self):
                    events.append(('prepare', self.name))
                    return {'model_id': 'fixture', 'digest': self.name, 'checkpoint': {'checkpoint': self.name}}

                def count(self, text):
                    return len(tok.encode(text))

                def max_context(self):
                    return 10 ** 6

                def generate(self, text, attention, max_new_tokens, constraint=False, agent=None):
                    events.append(('generate', self.name))
                    return {'text': self.replies.pop(0), 'output_tokens': 7, 'attention': attention,
                            'prefill': {'chunks': 0}, 'truncated': False}

                def release(self):
                    events.append(('release', self.name))
            reader = dict(decoding=decoding_policy.policy('local_producer'), model_id='fixture', model_mode='final',
                          max_new_tokens=CAP)
            backends = {'tuned': Backend('tuned', [valid, valid]), 'base': Backend('base', [broken, valid])}
            result = replay_prompts.run(Path(tmp) / 'roles.json', Path(tmp) / 'out', paths=['sdpa'], backend=backends,
                                        reader={'tuned': reader, 'base': reader})
            self.assertEqual(events[:2], [('prepare', 'tuned'), ('prepare', 'base')])
            self.assertEqual([e[1] for e in events if e[0] == 'generate'], ['tuned', 'base', 'tuned', 'base'])
            pairs = result['pairs']['sdpa']['legal_analyst']
            self.assertEqual((pairs['pairs'], pairs['both_valid'], pairs['a_only_valid'], pairs['b_only_valid'],
                              pairs['neither_valid'], pairs['byte_identical']), (2, 1, 1, 0, 0, 1))
            self.assertEqual(result['validity']['sdpa']['legal_analyst@base']['valid'], 1)
            self.assertEqual(result['validity']['sdpa']['legal_analyst@tuned']['valid'], 2)
            self.assertEqual(result['reference']['sdpa']['legal_analyst@tuned']['byte_identical'], 2)
            self.assertNotIn('legal_analyst@base', result['reference'].get('sdpa', {}))
            self.assertEqual(len(list((Path(tmp) / 'out' / 'audit' / 'model_replies').glob('*.json'))), 4)
            self.assertNotIn('Stated in the passage', (Path(tmp) / 'out' / replay_prompts.MEASUREMENT_FILE).read_text(encoding='utf-8'))
            with self.assertRaisesRegex(ValueError, 'compact producer prompts only'):
                replay_prompts.run(Path(tmp) / 'roles.json', Path(tmp) / 'o2', paths=['sdpa_constrained'], backend=backends,
                                   reader={'tuned': reader, 'base': reader})
            with self.assertRaisesRegex(ValueError, 'one backend per checkpoint'):
                replay_prompts.run(Path(tmp) / 'roles.json', Path(tmp) / 'o3', paths=['sdpa'], backend={'tuned': backends['tuned']},
                                   reader={'tuned': reader, 'base': reader})
            other = json.loads((Path(tmp) / 'roles.json').read_text(encoding='utf-8'))
            for row in other['prompts']:
                row['agent'] = 'NO_SUCH_AGENT'
            (Path(tmp) / 'other.json').write_text(json.dumps(other), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'no contract'):
                replay_prompts.run(Path(tmp) / 'other.json', Path(tmp) / 'o4', paths=['sdpa'], backend=backends,
                                   reader={'tuned': reader, 'base': reader})

    def test_producer_replays_select_and_write_their_bars(self):
        """benchmark/baselines/producer_replays.py: one call per prompt digest, a refused prompt
        always selected before the hashed order, a stamped one labelled, the roles file paired on
        both checkpoints and the EDITOR_CLERK file an envelope file, each with its bar; no reply
        text in either selection."""
        base.need(self, base.REPLAY_TOOL)
        import reply_records
        sys.path.insert(0, str(Path(base.REPLAY_TOOL).parent))
        import producer_replays
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'root' / 'L0' / 'entry'
            context = SimpleNamespace(run_dir=str(run), run_id='r')
            for i, (agent, outcome) in enumerate([('LEGAL_ANALYST', 'accepted_to_bus'), ('LEGAL_ANALYST', 'contract_violation'),
                                                  ('LEGAL_ANALYST', 'accepted_to_bus'), ('EDITOR_CLERK', 'accepted_to_bus'),
                                                  ('EDITOR_CLERK', 'accepted_to_bus'), ('PROCESSOR', 'accepted_to_bus')]):
                reply_records.write(context, agent=agent, call_id='c%d' % i, backend='local_producer', model_id='m',
                                    model_mode='final', payload='prompt %d' % (i if i != 2 else 0),
                                    payload_form='rendered_prompt', reply='SECRET REPLY %d' % i,
                                    decoding={'max_new_tokens': CAP})
                reply_records.write_outcome(context, 'c%d' % i, outcome, source='fixture')
            logs = run / 'logs'
            logs.mkdir(parents=True)
            (logs / 'generation_observation.jsonl').write_text(json.dumps({'call_id': 'c4', 'contract_normalized': ['kind <- finding']}) + '\n', encoding='utf-8')
            bar = producer_replays.roles(Path(tmp) / 'root', ['L0'], 1, Path(tmp) / 'roles')
            chosen = json.loads((Path(tmp) / 'roles' / 'call_ids.json').read_text(encoding='utf-8'))
            self.assertEqual([(c['agent'], c['call_id'], c['status']) for c in chosen],
                             [('EDITOR_CLERK', 'c4', 'stamped'), ('LEGAL_ANALYST', 'c1', 'failed')])
            self.assertEqual(bar['distinct_saved']['LEGAL_ANALYST'], 2)
            self.assertEqual(bar['prompt_count'], 4)
            self.assertEqual(bar['rules'], producer_replays.ROLES_BAR['rules'])
            clerk = producer_replays.editor_clerk(Path(tmp) / 'root', ['L0'], Path(tmp) / 'clerk')
            self.assertEqual(clerk['prompt_count'], 2)
            self.assertEqual(clerk['selected'], {'EDITOR_CLERK': {'valid': 1, 'stamped': 1}})
            prompts = json.loads((Path(tmp) / 'clerk' / 'replay_prompts.json').read_text(encoding='utf-8'))['prompts']
            self.assertTrue(all(p['envelope'] is True for p in prompts))
            for name in ('roles', 'clerk'):
                for file in ('call_ids.json', 'bar.json', 'replay_prompts.json'):
                    self.assertNotIn('SECRET REPLY', (Path(tmp) / name / file).read_text(encoding='utf-8'))
            with self.assertRaises(ValueError):
                producer_replays.folders(Path(tmp) / 'root', ['L9'])


def declared_with(agent, enums=None, max_chars=None, contract=None):
    """(the envelope contract, the declaration) with an agent's row carrying `enums` and
    `max_chars` (D-S57 item 1), built from the shipped declaration."""
    import copy
    spec = copy.deepcopy(cd.envelope_declaration()[0])
    row = spec['agents'].setdefault(agent, {'backend': 'local_auditor'})
    row.update({k: v for k, v in (('enums', enums), ('max_chars', max_chars)) if v})
    return cd.EnvelopeContract.for_agent(agent, spec, contract, root=ROOT), spec


def decode_with(contract, spec, intended, fallback, cap=CAP):
    tok = EnvelopeTokenizer()
    model = base.StandInModel(tok, intended, fallback)
    prompt = tok('<prompt>')['input_ids']
    constraint = cd.Constraint(contract, spec, 'fixture', tok, prompt.shape[1], [EOS], 'fixture',
                               cd.EnvelopeGrammar(contract, spec))
    out = model.generate(prompt, cap, eos_token_id=[EOS], **constraint.generate_kwargs())
    return tok.decode(out[0, prompt.shape[1]:].tolist()), constraint.record


class EnumerationAndBoundChecks(unittest.TestCase):
    """D-S57 item 1 (lane/auditor): a declared key's value is one of its declared strings, and a
    bounded key's string has at most its declared number of characters. Measured beside it: 123 of
    1,838 valid PRACTICE_AUDITOR items wrote a verdict the contract does not declare and 36 of 74
    valid VERIFIER items a finding; three PRACTICE_AUDITOR explanations ran to 768 tokens (open
    item 47)."""

    VERDICTS = ['ALIGNED', 'ANTI_PATTERN', 'COMPLIANT', 'VIOLATION']

    def test_an_enumerated_value_is_a_declared_one(self):
        contract, spec = declared_with('PRACTICE_AUDITOR', enums={'verdict': self.VERDICTS})
        item = auditor_item()
        for verdict in self.VERDICTS:
            self.assertTrue(cd.envelope_accepts(contract, spec, envelope('PRACTICE_AUDITOR', [dict(item, verdict=verdict)])))
        for verdict in ('UNCERTAIN', 'VIOLATIONS', 'VIOL', '', 'violation'):
            self.assertFalse(cd.envelope_accepts(contract, spec, envelope('PRACTICE_AUDITOR', [dict(item, verdict=verdict)])), verdict)
        self.assertFalse(cd.envelope_accepts(contract, spec, envelope('PRACTICE_AUDITOR', [dict(item, verdict=None)])))
        # An optional enumerated key may be null; a required one may not.
        optional, spec = declared_with('PRACTICE_AUDITOR', enums={'severity': ['required', 'advisory']})
        self.assertTrue(cd.envelope_accepts(optional, spec, envelope('PRACTICE_AUDITOR', [dict(item, severity=None)])))
        self.assertTrue(cd.envelope_accepts(optional, spec, envelope('PRACTICE_AUDITOR', [dict(item, severity='advisory')])))
        self.assertFalse(cd.envelope_accepts(optional, spec, envelope('PRACTICE_AUDITOR', [dict(item, severity='high')])))
        self.assertNotEqual(contract.digest(), contract_of('PRACTICE_AUDITOR')[0].digest())

    def test_an_undeclared_value_becomes_the_declared_one_the_model_ranked_next(self):
        contract, spec = declared_with('PRACTICE_AUDITOR', enums={'verdict': self.VERDICTS})
        intended = envelope('PRACTICE_AUDITOR', [auditor_item(verdict='UNCERTAIN')])
        fallback = envelope('PRACTICE_AUDITOR', [auditor_item(verdict='COMPLIANT')])
        self.assertEqual(reasons('PRACTICE_AUDITOR', intended), [])   # the validator accepts both
        reply, record = decode_with(contract, spec, intended, fallback)
        self.assertEqual(reply, fallback)
        self.assertGreaterEqual(record['interventions'], 1)
        self.assertFalse(record['dead_end'])
        # The same model with no enumeration writes its own value, unchanged.
        plain, spec = declared_with('PRACTICE_AUDITOR')
        self.assertEqual(decode_with(plain, spec, intended, fallback)[0], intended)

    def test_a_bounded_string_ends_within_its_bound(self):
        limit = 40
        contract, spec = declared_with('PRACTICE_AUDITOR', max_chars={'explanation': limit})
        item = auditor_item()
        self.assertTrue(cd.envelope_accepts(contract, spec, envelope('PRACTICE_AUDITOR', [dict(item, explanation='x' * limit)])))
        self.assertFalse(cd.envelope_accepts(contract, spec, envelope('PRACTICE_AUDITOR', [dict(item, explanation='x' * (limit + 1))])))
        # An escape counts once.
        self.assertTrue(cd.envelope_accepts(contract, spec, envelope('PRACTICE_AUDITOR', [dict(item, explanation='\n' * limit)])))
        self.assertFalse(cd.envelope_accepts(contract, spec, envelope('PRACTICE_AUDITOR', [dict(item, explanation='')])))
        # A runaway explanation (open item 47) is closed at the bound, the reply still valid.
        long = 'The unit names no reviewer and the rule asks for one in every entry it governs.'
        intended = envelope('PRACTICE_AUDITOR', [auditor_item(explanation=long)])
        cut = long[:limit]
        fallback = envelope('PRACTICE_AUDITOR', [auditor_item(explanation=cut)])
        # The stand-in's next choice after the bound is the closing quote of the fallback.
        reply, record = decode_with(contract, spec, intended, fallback)
        self.assertEqual(reply, fallback)
        self.assertEqual(reasons('PRACTICE_AUDITOR', reply), [])
        self.assertGreaterEqual(record['interventions'], 1)
        # The admitted content tokens of a bounded state all fit.
        tok = EnvelopeTokenizer()
        constraint = cd.Constraint(contract, spec, 'fixture', tok, 1, [EOS], 'fixture', cd.EnvelopeGrammar(contract, spec))
        processor, grammar = constraint.processor, constraint.processor.grammar
        state = grammar.walk(grammar.start(), intended[:intended.index(long) + limit - 3])
        self.assertEqual(grammar.bound(state), 3)
        ids, free = processor.admitted(state)
        allowed = [t for t in range(len(processor.table.strings)) if bool(free[t])]
        self.assertTrue(allowed)
        self.assertTrue(all(len(processor.table.strings[t]) <= 3 for t in allowed))

    def test_the_declaration_is_refused_when_unsound(self):
        import copy
        spec = copy.deepcopy(cd.envelope_declaration()[0])
        for bad in ({'enums': {'verdict': ['ONE']}}, {'enums': {'verdict': ['A', 'A']}},
                    {'enums': {'verdict': ['A"', 'B']}}, {'max_chars': {'explanation': 0}},
                    {'enums': {'explanation': ['A', 'B']}, 'max_chars': {'explanation': 9}}):
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / 'config').mkdir()
                broken = copy.deepcopy(spec)
                broken['agents']['PRACTICE_AUDITOR'].update(bad)
                (Path(tmp) / cd.ENVELOPE_DECLARATION).write_text(json.dumps(broken), encoding='utf-8')
                with self.assertRaises(RuntimeError, msg=bad):
                    cd.envelope_declaration(tmp)
        with self.assertRaises(RuntimeError):
            declared_with('PRACTICE_AUDITOR', enums={'colour': ['red', 'blue']})


if __name__ == '__main__':
    unittest.main(verbosity=2)
