"""DECODING-B proofs: contract-shaped decoding for the compact producer, with no real model.

A fixture tokenizer and a stand-in model whose logits would write each failure kind the L7,
L8, L10 and L11 diagnosis found (s5_diag_b3 K3 to K7: an invented CLM id, a dropped
uncertainty key, a context-only alias, one item for two owned spans, the neighbouring span's
REF, a runaway id list to the cap). Each kind is written twice: with the constraint, the reply
is the valid one the model ranked next and compact_contracts.producer (unchanged) accepts it;
with the constraint off, the same model writes the failure and the validator refuses it with
the reason the runs recorded. The real wrapper path (call_local on a bound compact producer)
carries the constraint into generate() beside the frozen decoding kwargs and records it on the
reply record and the call's usage; a call that is not the compact producer's carries none.
The replay path measures validity, interventions and agreement with a reference. With the
producer's tokenizer in the local cache (never fetched), every frozen DEV reply of checkpoint
168 is inside the constrained language, character by character on all 84 rows and token by
token on the first 12, with no intervention.
"""
import hashlib
import json
import os
import re
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
import bounded_extraction as extraction
import compact_contracts as cc
import contract_decoding as cd
import decoding_policy
from reference_builder import ReferenceIndex

EOS, PAD, UNK = 0, 1, 2
# Multi-character pieces, some crossing a boundary the grammar cares about, so a token is
# admitted only when its WHOLE text keeps the reply in the language.
PIECES = ['{"items":[', '{"claims":[', '"questions":[', '"refs":[', '"span":"', '"status":"',
          '"uncertainty":[', 'extracted', 'empty', 'refused', '"],"', '"]', '","', '],"', ']}', ']}]}',
          ',{', '}', 'CLM-', 'REF-', '"CLM-', '"REF-', 'Gap: ', '\\"', '\\n', '\n', 'missing ', 'date']
FIXTURE = json.loads((ROOT / 'docs/fix/compact_contract_ab/fixture.json').read_text(encoding='utf-8'))
DEV_REPLIES = ROOT / 'docs/fix/producer_tuning_v3_run/downloaded/evidence/checkpoint-168/full_dev.jsonl'
PRODUCER_TOKENIZER = 'unsloth/Qwen2.5-7B-Instruct-bnb-4bit'
DEV_TOKEN_ROWS = 12


class Encoding(dict):
    def to(self, device):
        return self


class FixtureTokenizer:
    """Printable ASCII one character a token, the PIECES above, and three special tokens."""
    chat_template = 'fixture'

    def __init__(self):
        pieces = []
        for piece in [chr(c) for c in range(32, 127)] + PIECES:
            if piece not in pieces:
                pieces.append(piece)
        self.vocab = ['<eos>', '<pad>', '<unk>'] + pieces
        self.index = {p: i for i, p in enumerate(self.vocab) if i > UNK}
        self.longest = max(len(p) for p in self.index)

    def __len__(self):
        return len(self.vocab)

    def encode(self, text, add_special_tokens=False):
        ids, i = [], 0
        while i < len(text):
            for size in range(min(self.longest, len(text) - i), 0, -1):
                if text[i:i + size] in self.index:
                    ids.append(self.index[text[i:i + size]])
                    i += size
                    break
            else:
                ids.append(UNK)
                i += 1
        return ids

    def decode(self, ids, skip_special_tokens=True):
        """Special tokens (EOS, PAD and any id past the vocabulary, such as the frozen policy's
        stop token) decode to nothing when skipped."""
        ids = ids.tolist() if hasattr(ids, 'tolist') else ids
        return ''.join('' if ((i in (EOS, PAD) or i >= len(self.vocab)) and skip_special_tokens) else
                       '<special>' if i >= len(self.vocab) else
                       '�' if i == UNK else self.vocab[i] for i in ids)

    def batch_decode(self, sequences, skip_special_tokens=True):
        return [self.decode(s, skip_special_tokens) for s in sequences]

    def __call__(self, text, return_tensors=None, add_special_tokens=False):
        ids = self.encode(text)
        return Encoding(input_ids=torch.tensor([ids]), attention_mask=torch.ones((1, len(ids)), dtype=torch.long))

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        return ''.join('<%s>%s' % (m['role'], m['content']) for m in messages) + '<assistant>'


class StandInModel:
    """A model whose top choice continues `intended` (the failure) and whose next choice
    continues `fallback` (a valid reply sharing the failure's prefix up to its error), with
    the end of a reply ranked as the stop token generate() was given (the frozen policy's in
    the wrapper). The logits run past the vocabulary, as a real model's padded head does.
    Greedy: generate() takes the argmax after the logits processors, as transformers' greedy
    search does."""
    device = 'cpu'
    config = SimpleNamespace(max_position_embeddings=10 ** 6)

    def __init__(self, tok, intended, fallback):
        self.tok, self.intended, self.fallback = tok, intended, fallback
        self.generation_config = SimpleNamespace(eos_token_id=[EOS])
        self.calls, self.end = [], EOS

    def next_token(self, target, text):
        rest = target[len(text):]
        if not rest:
            return self.end
        return self.tok.encode(rest[:self.tok.longest])[0]

    def scores(self, text):
        scores = torch.zeros((1, max(len(self.tok) + 3, self.end + 1)))
        for target, value in ((self.fallback, 5.0), (self.intended, 10.0)):
            if target.startswith(text):
                scores[0, self.next_token(target, text)] = value
        return scores

    def generate(self, input_ids, max_new_tokens, logits_processor=None, eos_token_id=None, **kwargs):
        self.calls.append(dict(kwargs, logits_processor=logits_processor, eos_token_id=eos_token_id,
                               max_new_tokens=max_new_tokens))
        ids, start = input_ids, int(input_ids.shape[1])
        stop = set(eos_token_id or [EOS])
        self.end = min(stop)
        for _ in range(max_new_tokens):
            scores = self.scores(self.tok.decode(ids[0, start:].tolist()))
            for processor in logits_processor or ():
                scores = processor(ids, scores)
            token = int(scores[0].argmax())
            ids = torch.cat([ids, torch.tensor([[token]])], dim=1)
            if token in stop:
                break
        return ids


def spec():
    return cd.declaration()[0]


def owned_spans():
    """Two owned spans (s0, s40) and their context neighbour (s80): s0 places REF-0001, s40
    places REF-0002 (Python's grounding), and no span writes a CLM id."""
    a = 'The first entry is recorded. Its date is not given in the record.'
    b = 'The second entry follows. It names no reviewer for the amendment.'
    return [extraction.Span('s0', 0, 64, 'u01', 1, a[:64]), extraction.Span('s40', 64, 128, 'u02', 2, b[:64])], \
        {'s0': ['REF-0001'], 's40': ['REF-0002']}


def item(span, claims=(), questions=(), refs=(), uncertainty=(), status=None, drop=()):
    value = dict(claims=list(claims), questions=list(questions), refs=list(refs), span=span,
                 status=status or ('extracted' if claims or questions or uncertainty else 'empty'),
                 uncertainty=list(uncertainty))
    return {k: v for k, v in value.items() if k not in drop}


VALID = cd.canonical(dict(items=[item('s0', questions=['Gap: missing date'], refs=['REF-0001']), item('s40')]))
RUNAWAY = '{"items":[{"claims":[' + ','.join('"CLM-%d"' % i for i in range(1, 400))
# Each failure kind the diagnosis found, written as the model's top choice, beside the valid
# reply it ranked next, and the validator's reason in the runs.
KINDS = {
    'K3_invented_claim_id': (cd.canonical(dict(items=[item('s0', claims=['CLM-0001'], refs=['REF-0001']), item('s40')])),
                             'Ungrounded claim id'),
    'K3_runaway_id_list': (RUNAWAY, 'not a JSON reply'),
    'K4_missing_uncertainty': (cd.canonical(dict(items=[item('s0', questions=['Gap: missing date'], refs=['REF-0001'],
                                                             drop=('uncertainty',)), item('s40')])),
                               'Exact compact extraction fields required'),
    'K5_context_alias': (cd.canonical(dict(items=[item('s80', questions=['Gap: missing date'], refs=['REF-0001']),
                                                  item('s40')])), 'Invalid or duplicate owned alias'),
    'K6_one_item_for_two_spans': (cd.canonical(dict(items=[item('s0', questions=['Gap: missing date'], refs=['REF-0001'])])),
                                  'Incomplete partition coverage'),
    'K7_neighbour_ref': (cd.canonical(dict(items=[item('s0', questions=['Gap: missing date'], refs=['REF-0002']), item('s40')])),
                         'Ungrounded extraction evidence'),
}
CAP = 160


def reason(reply, owned, citable):
    """None when compact_contracts.producer accepts the reply, else its reason."""
    try:
        cc.producer(json.loads(reply), owned, 'doc', citable)
    except ValueError as exc:
        return str(exc)
    return None


def decode_kind(intended, constrained):
    """(reply, record) from the stand-in model writing `intended`, with or without the constraint."""
    tok = FixtureTokenizer()
    owned, citable = owned_spans()
    model = StandInModel(tok, intended, VALID)
    prompt = tok('<prompt>')['input_ids']
    record, extra = None, {}
    if constrained:
        constraint = cd.Constraint(cd.Contract.from_binding(owned, citable, spec()), spec(), 'fixture', tok,
                                   prompt.shape[1], [EOS], 'binding')
        extra, record = constraint.generate_kwargs(), constraint.record
    out = model.generate(prompt, CAP, eos_token_id=[EOS], **extra)
    return tok.decode(out[0, prompt.shape[1]:].tolist()), record


class ContractDecodingChecks(unittest.TestCase):
    def test_declaration_is_the_validators_own(self):
        """The id patterns are the validator's regexes; the item keys its field set, in the
        canonical order every frozen DEV reply uses; the refusal the contract's own; and the
        status rule the validator's."""
        import ast
        import inspect
        value = spec()
        tree = ast.parse(inspect.getsource(cc.producer))
        literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        for pattern in value['id_arrays'].values():
            self.assertIn(pattern, literals)
        fields = next(n for n in ast.walk(tree) if isinstance(n, ast.Set)
                      and {getattr(e, 'value', None) for e in n.elts} >= {'span', 'claims'})
        self.assertEqual(sorted(e.value for e in fields.elts), value['item_keys'])
        self.assertIn(cd.canonical(value['refusal']), cc.PRODUCER)
        self.assertTrue({value['status_values']['semantic'], value['status_values']['none']} <= literals)
        rows = [json.loads(line) for line in DEV_REPLIES.read_text(encoding='utf-8').splitlines() if line.strip()]
        self.assertEqual(len(rows), 84)
        for row in rows:
            self.assertEqual(cd.canonical(json.loads(row['raw_output'])), row['raw_output'])

    def test_each_failure_kind_is_prevented_and_the_validator_passes(self):
        owned, citable = owned_spans()
        self.assertIsNone(reason(VALID, owned, citable))
        for name, (intended, expected) in KINDS.items():
            with self.subTest(kind=name):
                reply, record = decode_kind(intended, constrained=True)
                self.assertEqual(reply, VALID)
                self.assertIsNone(reason(reply, owned, citable))
                self.assertGreaterEqual(record['interventions'], 1)
                self.assertFalse(record['dead_end'])

    def test_constraint_off_reproduces_each_failure(self):
        owned, citable = owned_spans()
        for name, (intended, expected) in KINDS.items():
            with self.subTest(kind=name):
                reply, _ = decode_kind(intended, constrained=False)
                self.assertNotEqual(reply, VALID)
                if expected == 'not a JSON reply':
                    self.assertEqual(len(FixtureTokenizer().encode(reply)), CAP)  # truncated at the cap
                    with self.assertRaises(ValueError):
                        json.loads(reply)
                else:
                    self.assertEqual(reply, intended)
                    self.assertEqual(reason(reply, owned, citable), expected)

    def test_a_valid_reply_is_never_changed(self):
        """Where the model's top choice is admitted, nothing changes: the same reply, no
        intervention. The refusal stays the model's to give (and the validator's to refuse)."""
        refusal = cd.canonical(spec()['refusal'])
        for intended in (VALID, refusal):
            reply, record = decode_kind(intended, constrained=True)
            self.assertEqual(reply, intended)
            self.assertEqual(record['interventions'], 0)
        owned, citable = owned_spans()
        self.assertIn('refusal is not acceptance', reason(refusal, owned, citable))

    def test_language_rules(self):
        """The grammar refuses what the validator refuses and admits what it accepts."""
        owned, citable = owned_spans()
        contract = cd.Contract.from_binding(owned, citable, spec())
        self.assertEqual(contract.ids['s0'], {'claims': (), 'refs': ('REF-0001',)})
        good = [VALID, cd.canonical(dict(items=[item('s0', uncertainty=['Uncertainty: \\u00e9 "x"']), item('s40')])),
                cd.canonical(dict(items=[item('s0', questions=['a', 'b'], refs=['REF-0001']), item('s40', refs=['REF-0002'])]))]
        bad = [cd.canonical(dict(items=[item('s0', questions=['a', 'a']), item('s40')])),       # repeated
               cd.canonical(dict(items=[item('s0', questions=[' ']), item('s40')])),            # blank
               cd.canonical(dict(items=[item('s0', status='extracted'), item('s40')])),         # status mismatch
               cd.canonical(dict(items=[item('s0', questions=['a'], status='empty'), item('s40')])),
               cd.canonical(dict(items=[item('s0', refs=['REF-0001', 'REF-0001']), item('s40')])),
               cd.canonical(dict(items=[item('s40'), item('s0')])),                              # order
               VALID[:-1], VALID + ' ', json.dumps(json.loads(VALID))]                            # incomplete, trailing, spaced
        for text in good:
            self.assertTrue(cd.accepts(contract, spec(), text), text)
            self.assertIsNone(reason(text, owned, citable), text)
        for text in bad:
            self.assertFalse(cd.accepts(contract, spec(), text), text)

    def test_the_wrapper_carries_the_constraint_and_records_it(self):
        """call_local on a PROCESSOR bound by compact_contracts.bind_producer with the validated
        messages: generate() receives the frozen decoding kwargs unchanged plus the logits
        processor; the reply passes the wrapper's own source adapter (the validator); the reply
        record and the usage carry the constraint. A call that is not the compact producer's
        (unbound PROCESSOR, VERIFIER on local_auditor) carries none."""
        real = FIXTURE['real_document']
        text, doc = real['source'], real['doc']
        spans = extraction.ledger(text, doc)
        owned = spans[:2]
        index = ReferenceIndex(ROOT)
        index.index_document(input_type='operational', document_id=doc, document_name=doc + '.md', text=text)
        system, user, citable, supplied = cc.validated_messages(text, owned, spans,
                                                                [e.as_dict() for e in index.find_by_document(doc)])
        contract = cd.Contract.from_binding(owned, citable, spec())
        valid = cd.canonical(dict(items=[item(a) for a in contract.aliases]))
        invented = cd.canonical(dict(items=[item(contract.aliases[0], claims=['CLM-7'])]
                                     + [item(a) for a in contract.aliases[1:]]))
        tok = FixtureTokenizer()

        def call(wrapper, intended, run_dir):
            model = StandInModel(tok, intended, valid)
            wrapper.run_context = SimpleNamespace(run_dir=str(run_dir), run_id='fixture',
                                                  logs_dir=lambda: Path(run_dir) / 'logs')
            with patch.dict(os.environ, SHIMMER_MODEL_MODE='base'), \
                    patch.object(agent_wrapper, '_load_qwen', return_value=(tok, model)):
                result = wrapper.dispatch(system, user, max_new_tokens=CAP) if getattr(wrapper, '_compact_messages', None) \
                    else wrapper.call_local('plain prompt', max_new_tokens=CAP)
            return result, model.calls[0]

        def wrapper(name, backend):
            w = object.__new__(agent_wrapper.AgentWrapper)
            w.name, w.backend, w.model, w.cost_tracker = name, backend, 'fixture', None
            w._optimized_semantics = True
            return w

        policy = decoding_policy.policy('local_producer')['kwargs']
        with tempfile.TemporaryDirectory() as tmp:
            bound = wrapper('PROCESSOR', 'local_producer')
            cc.bind_producer(bound, owned, doc, citable=citable, messages=(system, user, supplied))
            result, sent = call(bound, invented, Path(tmp) / 'bound')
            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.raw_text, valid)
            bound._source_adapter(json.loads(result.raw_text))  # the validator, unchanged
            self.assertEqual({k: sent[k] for k in policy}, policy)
            processors = sent['logits_processor']
            self.assertEqual([type(p).__name__ for p in processors], ['ContractProcessor'])
            usage = result.usage['decoding_constraint']
            self.assertEqual((usage['name'], usage['version'], usage['source']),
                             (spec()['name'], spec()['version'], 'binding'))
            self.assertEqual(usage['contract_sha256'], contract.digest())
            self.assertGreaterEqual(usage['interventions'], 1)
            record = json.loads(next((Path(tmp) / 'bound' / 'audit' / 'model_replies').glob('*.json')).read_text(encoding='utf-8'))
            self.assertEqual(record['decoding_constraint'], usage)
            self.assertEqual(record['decoding']['decoding_kwargs'], policy)
            for name, backend in (('PROCESSOR', 'local_producer'), ('VERIFIER', 'local_auditor')):
                plain = wrapper(name, backend)
                result, sent = call(plain, valid, Path(tmp) / name)
                self.assertIsNone(sent['logits_processor'])
                self.assertNotIn('decoding_constraint', result.usage)
                record = json.loads(next((Path(tmp) / name / 'audit' / 'model_replies').glob('*.json')).read_text(encoding='utf-8'))
                self.assertNotIn('decoding_constraint', record)

    def test_rendered_declaration_matches_the_binding(self):
        """A replay reads the declaration back from the rendered prompt's canonical payload: the
        same aliases and claim sets as the binding, and refs that are the binding's (every
        passage indexed once, so the shown markers are the whole grounded set)."""
        real = FIXTURE['real_document']
        text, doc = real['source'], real['doc']
        spans = extraction.ledger(text, doc)
        index = ReferenceIndex(ROOT)
        index.index_document(input_type='operational', document_id=doc, document_name=doc + '.md', text=text)
        entries = [e.as_dict() for e in index.find_by_document(doc)]
        checked = 0
        for owned in extraction.partitions(spans, cc.request_size()):
            system, user, citable, supplied = cc.validated_messages(text, owned, spans, entries)
            rendered = FixtureTokenizer().apply_chat_template([{'role': 'system', 'content': system},
                                                                {'role': 'user', 'content': user}])
            bound = cd.Contract.from_binding(owned, citable, spec())
            read = cd.Contract.from_rendered(rendered, spec())
            self.assertEqual(read.aliases, bound.aliases)
            self.assertEqual(read.ids, bound.ids)
            checked += 1
        self.assertGreater(checked, 1)
        with self.assertRaises(RuntimeError):
            cd.Contract.from_rendered('no payload here', spec())

    def test_replay_measures_validity_interventions_and_reference(self):
        """replay_prompts.run with the constrained path beside sdpa, on a backend whose model is
        the stand-in (the real constraint, built from the prompt's payload): sdpa reproduces
        the saved failure byte for byte and the validator refuses it; sdpa_constrained passes."""
        import replay_prompts
        owned, citable = owned_spans()
        source = [(s.id, s.text.replace('recorded.', 'recorded (REF-0001).') if s.id == 's0' else
                   s.text + ' (REF-0002)') for s in owned]
        payload = cc.validated_payload(source, [('s80', 'Context.')], ['REF-0001', 'REF-0002'])
        prompt = '<system>' + cc.validated_system() + '<user>' + cc.canonical(payload) + '<assistant>'
        failure = KINDS['K3_invented_claim_id'][0]
        tok = FixtureTokenizer()

        class Backend:
            def prepare(self):
                return {'model_id': 'fixture', 'digest': 'd', 'checkpoint': 'tuned'}

            def count(self, text):
                return len(tok.encode(text))

            def max_context(self):
                return 10 ** 6

            def generate(self, text, attention, max_new_tokens, constraint=False):
                model = StandInModel(tok, failure, VALID)
                ids = tok(text)['input_ids']
                extra, built = {}, None
                if constraint:
                    built = cd.for_prompt(text, tok, ids.shape[1], [EOS])
                    extra = built.generate_kwargs()
                out = model.generate(ids, max_new_tokens, eos_token_id=[EOS], **extra)
                result = {'text': tok.decode(out[0, ids.shape[1]:].tolist()), 'output_tokens': 1,
                          'attention': attention, 'prefill': {'chunks': 0}}
                if built is not None:
                    result['decoding_constraint'] = built.summary()
                return result
        reader = dict(decoding=decoding_policy.policy('local_producer'), model_id='fixture', model_mode='final',
                      max_new_tokens=CAP)
        with tempfile.TemporaryDirectory() as tmp:
            prompts = Path(tmp) / 'replay_prompts.json'
            prompts.write_text(json.dumps(dict(schema=replay_prompts.SCHEMA, prompt_count=1, prompts=[dict(
                prompt_id='p0001', set='records', prompt=prompt, prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
                max_new_tokens=CAP, reference_reply_sha256=hashlib.sha256(failure.encode()).hexdigest())])), encoding='utf-8')
            result = replay_prompts.run(prompts, Path(tmp) / 'out', paths=['sdpa', 'sdpa_constrained'],
                                        backend=Backend(), reader=reader)
            text = (Path(tmp) / 'out' / replay_prompts.MEASUREMENT_FILE).read_text(encoding='utf-8')
        self.assertNotIn('CLM-0001', text)
        self.assertNotIn('Gap: missing', text)
        self.assertEqual(result['validity']['sdpa']['records'],
                         dict(compact_prompts=1, replied=1, valid=0, reasons={'Ungrounded claim id': 1}))
        self.assertEqual(result['validity']['sdpa_constrained']['records'],
                         dict(compact_prompts=1, replied=1, valid=1, reasons={}))
        self.assertEqual(result['reference']['sdpa']['records']['byte_identical'], 1)
        self.assertEqual(result['reference']['sdpa_constrained']['records']['differ'], ['p0001'])
        self.assertEqual(result['constraint']['sdpa_constrained']['records']['calls_with_intervention'], 1)
        self.assertNotIn('sdpa', result['constraint'])
        self.assertEqual(result['comparisons']['sdpa_constrained_vs_sdpa']['all']['differ'], 1)

    def test_replay_extract_dev_and_call_ids(self):
        """--dev adds the 84 DEV rows (prompts held to the protocol's digests, the protocol's cap,
        the frozen replies' digests as references), each a compact producer prompt; --call-ids
        keeps only the listed calls and refuses one it cannot find."""
        import reply_records
        import replay_prompts
        with tempfile.TemporaryDirectory() as tmp:
            context = SimpleNamespace(run_dir=str(Path(tmp) / 'run'), run_id='r')
            kept = reply_records.write(context, agent='PROCESSOR', call_id='keep', backend='local_producer', model_id='m',
                                       payload='prompt one', payload_form='rendered_prompt', reply='R1',
                                       decoding={'max_new_tokens': 1536})
            reply_records.write(context, agent='PROCESSOR', call_id='drop', backend='local_producer', model_id='m',
                                payload='prompt two', payload_form='rendered_prompt', reply='R2')
            folder = Path(tmp) / 'run' / 'audit' / 'model_replies'
            value = replay_prompts.extract([folder], Path(tmp) / 'p.json', call_ids={kept}, dev=True)
            self.assertEqual(value['prompt_count'], 85)
            first = value['prompts'][0]
            self.assertEqual((first['set'], first['source_call_id'], first['max_new_tokens'], first['reference_reply_sha256']),
                             ('records', 'keep', 1536, hashlib.sha256(b'R1').hexdigest()))
            dev = value['prompts'][1:]
            self.assertEqual({p['set'] for p in dev}, {'dev'})
            self.assertEqual({p['max_new_tokens'] for p in dev}, {288})
            self.assertTrue(all(replay_prompts.is_compact(p['prompt']) for p in dev))
            self.assertEqual(len(replay_prompts.load_prompts(Path(tmp) / 'p.json')), 85)
            self.assertNotIn('"R1"', (Path(tmp) / 'p.json').read_text(encoding='utf-8'))
            with self.assertRaisesRegex(ValueError, 'no producer prompt'):
                replay_prompts.extract([folder], Path(tmp) / 'q.json', call_ids={'missing'})

    def test_frozen_dev_replies_are_inside_the_constrained_language(self):
        """Every frozen DEV reply of checkpoint 168 (84 rows) is a complete reply of its own
        request's constrained language; 75 pass the validator and 9 are the model's refusal.
        With the producer's tokenizer in the local cache, the first 12 rows are fed token by
        token through the real processor: every token the checkpoint wrote is admitted and the
        constraint intervenes nowhere."""
        rows = [json.loads(line) for line in DEV_REPLIES.read_text(encoding='utf-8').splitlines() if line.strip()]
        value = spec()
        valid = refused = 0
        for row in rows:
            contract = cd.Contract.from_rendered(row['prompt'], value)
            self.assertTrue(cd.accepts(contract, value, row['raw_output']), row['example_id'])
            why = cd.validate_rendered(row['prompt'], row['raw_output'])
            valid += why is None
            refused += row['raw_output'] == cd.canonical(value['refusal'])
        self.assertEqual((valid, refused), (75, 9))
        try:
            os.environ.setdefault('HF_HUB_OFFLINE', '1')
            from transformers import AutoTokenizer
            tok = AutoTokenizer.from_pretrained(PRODUCER_TOKENIZER, local_files_only=True)
        except Exception:
            return
        eos = decoding_policy.policy('local_producer')['kwargs']['eos_token_id']
        for row in rows[:DEV_TOKEN_ROWS]:
            constraint = cd.for_prompt(row['prompt'], tok, len(row['input_ids']), eos)
            ids = list(row['input_ids'])
            for token in row['output_token_ids']:
                scores = torch.zeros((1, 152064))
                scores[0, token] = 1.0
                kept = constraint.processor(torch.tensor([ids]), scores)
                self.assertTrue(bool(torch.isfinite(kept[0, token])), (row['example_id'], len(ids)))
                ids.append(token)
            self.assertEqual(constraint.summary()['interventions'], 0)
            self.assertFalse(constraint.summary()['dead_end'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
