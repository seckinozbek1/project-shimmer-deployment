"""Measure the envelope constraint (DECODING-B) on saved replies, offline: tokenizer only, no model.

    py -3.12 -X utf8 tools/envelope_decoding_measure.py --records <run>/audit/model_replies
        [--records <another run's folder> ...]
        [--out measurement.json]

For every saved reply of a declared envelope agent (config/envelope_decoding.json) in the reply
records given, whose outcome (outcomes.jsonl) says whether the run accepted it: the reply is
walked character by character through the agent's envelope grammar and fed token by token
(the encoding of the reply by its backend's tokenizer, then the backend's stop token) through the real ContractProcessor,
the model's choice standing in as the top logit, counting every step where that token was not
admitted. A valid reply must pass with 0 interventions; a failed one shows where the
constraint first acts. The tokenizer is read from the local cache only (never fetched).
Prints and writes counts, call ids, step numbers and state kinds only, never a reply's text.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'scripts') not in sys.path:
    sys.path.insert(0, str(ROOT / 'scripts'))

import contract_decoding as cd  # noqa: E402

# The tokenizer of each declared backend's model (the local cache only).
TOKENIZERS = {'local_auditor': 'unsloth/Phi-3.5-mini-instruct-bnb-4bit',
              'local_producer': 'unsloth/Qwen2.5-7B-Instruct-bnb-4bit'}
FAILED = 'contract_violation'
NEVER_READ = ('benchmark/keys',)


def records(folder):
    """(record, outcome) for each reply record in one model_replies folder."""
    folder = Path(folder)
    for part in NEVER_READ:
        if (ROOT / part).resolve() in (folder.resolve(), *folder.resolve().parents):
            raise ValueError('a key folder is never read: ' + part)
    outcomes = {}
    if (folder / 'outcomes.jsonl').is_file():
        for line in (folder / 'outcomes.jsonl').read_text(encoding='utf-8').splitlines():
            if line.strip():
                row = json.loads(line)
                outcomes[row.get('call_id')] = row.get('outcome')
    for path in sorted(folder.glob('*.json')):
        record = json.loads(path.read_text(encoding='utf-8'))
        yield record, outcomes.get(record.get('call_id'))


def longest_whitespace(grammar, text):
    state, run, best = grammar.start(), 0, 0
    for ch in text:
        structural = state is not None and not grammar.free(state) and not grammar.unrestricted(state)
        state = grammar.step(state, ch) if state is not None else None
        run = run + 1 if structural and ch in cd.WHITESPACE else 0
        best = max(best, run)
    return best


def first_break(grammar, text):
    """(character offset, the state's kind) where the walk first leaves the language, or None."""
    state = grammar.start()
    for i, ch in enumerate(text):
        nxt = grammar.step(state, ch)
        if nxt is None:
            return i, state[0] if state[0] != 'gap' else 'gap>' + state[2][0]
        state = nxt
    return None if grammar.accepting(state) else (len(text), 'end>' + state[0])


def measure(folders, tok, stops, width=None, root=None, agents=None):
    """`tok` and `stops` are one tokenizer and stop list, or a map from backend to each;
    `agents`, when given, limits the measurement to those declared agents."""
    import torch
    spec, digest = cd.envelope_declaration(root)
    counts = collections.Counter()
    whitespace = collections.Counter()
    acted, failed = [], []
    for folder in folders:
        for record, outcome in records(folder):
            agent = record.get('agent')
            if agent not in spec['agents'] or record.get('backend') != spec['agents'][agent]['backend'] \
                    or (agents and agent not in agents):
                continue
            reply = (record.get('reply') or {}).get('text')
            if not isinstance(reply, str):
                counts[(agent, 'no_reply_text')] += 1
                continue
            valid = outcome not in (FAILED, None)
            group = 'valid' if valid else ('failed' if outcome == FAILED else 'no_outcome')
            contract = cd.EnvelopeContract.for_agent(agent, spec, root=root)
            grammar = cd.EnvelopeGrammar(contract, spec)
            counts[(agent, group, 'replies')] += 1
            accepted = cd.envelope_accepts(contract, spec, reply)
            counts[(agent, group, 'inside_the_language')] += int(accepted)
            if valid and accepted:
                whitespace[agent] = max(whitespace[agent], longest_whitespace(grammar, reply))
            backend = record.get('backend')
            used = tok[backend] if isinstance(tok, dict) else tok
            ends = stops[backend] if isinstance(stops, dict) else stops
            constraint = cd.envelope_constraint(agent, used, 1, ends, 'measurement', root=root)
            ids = [ends[0]]
            for token in used.encode(reply, add_special_tokens=False) + [ends[0]]:
                scores = torch.zeros((1, width or len(used)))
                scores[0, token] = 1.0
                constraint.processor(torch.tensor([ids]), scores)
                ids.append(token)
            seen = constraint.summary()
            counts[(agent, group, 'with_intervention')] += int(bool(seen['interventions']))
            counts[(agent, group, 'dead_end')] += int(bool(seen['dead_end']))
            row = dict(call_id=record.get('call_id'), run_id=record.get('run_id'), agent=agent, outcome=outcome,
                       steps=seen['steps'], interventions=seen['interventions'],
                       first_intervention_step=seen['first_intervention_step'], leaves_at=first_break(grammar, reply))
            if valid and seen['interventions']:
                acted.append(row)
            if not valid:
                failed.append(row)
    return {'declaration_sha256': digest,
            'counts': {'/'.join(k): v for k, v in sorted(counts.items())},
            'longest_whitespace_run_in_valid_replies': dict(whitespace),
            'whitespace_run_max': spec['whitespace_run_max'],
            'valid_replies_with_intervention': acted, 'failed_replies': failed,
            'reads': 'reply records: reply text walked and tokenized in memory; nothing of it is written'}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='envelope_decoding_measure.py', allow_abbrev=False,
                                     description=__doc__.split('\n\n')[0])
    parser.add_argument('--records', action='append', required=True)
    parser.add_argument('--out', default=None)
    parser.add_argument('--agents', default=None, help='comma-separated declared agents to measure (default: all)')
    args = parser.parse_args(argv)
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    from transformers import AutoTokenizer
    import decoding_policy
    tok = {backend: AutoTokenizer.from_pretrained(name, local_files_only=True) for backend, name in TOKENIZERS.items()}
    stops = {backend: list(decoding_policy.policy(backend)['kwargs']['eos_token_id']) for backend in TOKENIZERS}
    result = measure(args.records, tok, stops, agents={a for a in (args.agents or '').split(',') if a} or None)
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0 if not result['valid_replies_with_intervention'] else 1


if __name__ == '__main__':
    sys.exit(main())
