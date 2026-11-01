"""Contract-shaped decoding for the compact producer (DECODING-B, D-S14 item 3).

The tuned producer (checkpoint 168) fails the compact extraction contract on real documents
in ways a deterministic re-ask repeats byte for byte: it writes CLM ids no owned span carries
(its training spans mostly carried them), drops the uncertainty key, answers a context-only
alias, returns one item for two owned spans, or cites the REF Python placed in the next span.
The validator (compact_contracts.producer) is right to refuse every one of them, and the
prompt bytes are pinned (EXTRACTION-A). What is left is the decoding: this module builds,
per request and from that request's own declaration, a logits constraint under which only a
reply of the declared canonical shape can be generated, with the validator unchanged behind it.

  * the envelope, then exactly one item per owned alias, in the owned order;
  * every item key present, in canonical (sorted) order, the order all 84 DEV replies use;
  * span is the item's owned alias; claims only CLM ids written in that span's text; refs only
    that span's grounded set (the validator's: REF ids in its text and the passages
    bounded_extraction.grounding placed in it); no id twice;
  * status extracted exactly when claims, questions or uncertainty is non-empty;
  * questions and uncertainty stay the model's own JSON strings (any valid escape), non-blank
    and not repeated, the two things the validator's array rule refuses;
  * or the refusal object, which stays the model's to give and the validator refuses as before.

Nothing else changes. The frozen decoding policy is untouched (greedy stays greedy; the
constraint is a logits processor beside it, not a decoding value), and where the model's own
choice is already admitted the constraint changes nothing, so a reply that was valid is
reproduced token for token. Every intervention (a step where the model's own top token was
not admitted) is counted and recorded. The declaration is config/contract_decoding.json; the
constraint is active only on the compact producer path (for_call). A dead end, which the
grammar is built never to reach, admits only the stop tokens and is recorded: the reply is
then refused by the validator, never accepted.

The same processor carries a second grammar, the general envelope of the local auditor agents
that failed their contract in L8, L11 and L12 (VERIFIER and PRACTICE_AUDITOR on local_auditor,
s5_diag_b3 K9 and K11; declared in config/envelope_decoding.json, built per call from the
agent's own contract in config/agent_contracts.json): the envelope {agent, doc_id, items},
closed before the stop token is admitted, each item opening with every key the validator
requires, in the order the agents' saved replies write them, and nothing else constrained
(EnvelopeGrammar). It does not stop a repetition inside a string or an item list that runs to
the output cap: a reply that cannot close in its allowance is truncated as before and refused
by the unchanged validator.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECLARATION = 'config/contract_decoding.json'
# The user turn of the validated shape starts with its first sorted key (compact_contracts.validated_payload).
PAYLOAD_HEAD = '{"context_only_spans":'
DONE = ('done',)
ESCAPES = {'"': '"', '\\': '\\', '/': '/', 'b': '\b', 'f': '\f', 'n': '\n', 'r': '\r', 't': '\t'}
HEX = '0123456789abcdefABCDEF'


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def canonical(value):
    """The serialisation the producer was trained and evaluated on (compact_contracts.canonical)."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def declaration(root=None):
    """(the declaration, its SHA-256 with CRLF normalised to LF); refused when unsound."""
    data = (Path(root or ROOT) / DECLARATION).read_bytes().replace(b'\r\n', b'\n')
    value = json.loads(data.decode('utf-8'))
    keys = value.get('item_keys')
    require(value.get('schema_version') == 1 and isinstance(value.get('name'), str)
            and type(value.get('version')) is int, 'Invalid contract decoding declaration')
    require(isinstance(keys, list) and keys == sorted(keys) and len(set(keys)) == len(keys),
            'The declared item keys must be the canonical (sorted) order')
    roles = [value['alias_key'], value['status_key'], *value['id_arrays'], *value['text_arrays']]
    require(sorted(roles) == keys, 'Every declared item key has exactly one role')
    require(set(value['semantic_keys']) <= set(value['id_arrays']) | set(value['text_arrays']),
            'A semantic key is an array')
    refusal = canonical(value['refusal'])
    require(refusal.startswith('{"%s":[' % value['envelope_key']), 'The refusal opens with the envelope')
    require(value.get('status') in ('active', 'off'), 'The constraint is active or off')
    return value, hashlib.sha256(data).hexdigest()


class Contract:
    """One request's declaration: the owned aliases in order and, per alias, the ids each id
    array admits."""

    def __init__(self, aliases, ids):
        require(aliases and len(set(aliases)) == len(aliases), 'A request owns distinct aliases')
        self.aliases = tuple(aliases)
        self.ids = {alias: {field: tuple(sorted(set(values))) for field, values in ids[alias].items()}
                    for alias in self.aliases}

    @classmethod
    def from_binding(cls, owned, citable, spec):
        """The validator's own sets (compact_contracts.producer): claims are the CLM ids in the
        span's text; refs the REF ids in its text and the passages Python placed in it."""
        import bounded_extraction
        aliases, ids = [], {}
        for span in owned:
            alias = bounded_extraction.wire_id(span)
            found = {field: set(re.findall(pattern, span.text)) for field, pattern in spec['id_arrays'].items()}
            found['refs'] = found.get('refs', set()) | set((citable or {}).get(alias, ()))
            aliases.append(alias)
            ids[alias] = found
        return cls(aliases, ids)

    @classmethod
    def from_rendered(cls, prompt, spec):
        """The declaration read back from a rendered prompt's canonical user payload (a replay,
        which has no binding): the aliases of its source spans and the ids in their shown text.
        The shown text carries Python's markers, so refs are the placed passages the model was
        shown; with one copy of each passage that is the binding's set exactly, otherwise a
        subset of it."""
        payload, spans = payload_spans(prompt)
        aliases, ids = [], {}
        for span in spans:
            aliases.append(span['alias'])
            ids[span['alias']] = {field: set(re.findall(pattern, span['text']))
                                  for field, pattern in spec['id_arrays'].items()}
        return cls(aliases, ids)

    def digest(self):
        return hashlib.sha256(canonical(dict(aliases=list(self.aliases),
                                             ids={a: {f: list(v) for f, v in d.items()} for a, d in self.ids.items()}))
                              .encode('utf-8')).hexdigest()


def payload_spans(prompt):
    """(payload, source spans) of the canonical user payload inside a rendered prompt; refused
    when there is none or it is not canonical."""
    start = prompt.find(PAYLOAD_HEAD)
    require(start >= 0, 'No compact producer payload in the prompt')
    payload, end = json.JSONDecoder().raw_decode(prompt, start)
    require(canonical(payload) == prompt[start:end], 'The compact producer payload is not canonical')
    spans = payload.get('source_spans')
    require(isinstance(spans, list) and spans and all(isinstance(s, dict) and isinstance(s.get('alias'), str)
                                                      and isinstance(s.get('text'), str) for s in spans),
            'The compact producer payload has no source spans')
    return payload, spans


class Grammar:
    """The canonical reply language of one request, as a character-level recognizer: step(state,
    ch) is the next state or None. States are tuples, so a token is tried by walking its
    characters without touching the state it started from."""

    def __init__(self, contract, spec):
        self.contract, self.spec = contract, spec
        self.keys = spec['item_keys']
        self.semantic = set(spec['semantic_keys'])
        self.statuses = spec['status_values']
        self.open = '{"%s":[' % spec['envelope_key']
        self.refusal = canonical(spec['refusal'])[len(self.open):]

    def start(self):
        return ('lit', self.open, ('items',))

    def last_semantic(self, j):
        return not any(k in self.semantic for k in self.keys[j + 1:])

    # --- descriptors: what comes next, resolved into a consuming state
    def resolve(self, desc):
        kind = desc[0]
        if kind == 'key':
            _, k, j, it = desc
            if j == len(self.keys):
                last = k + 1 == len(self.contract.aliases)
                return ('lit', '}' + (']}' if last else ',{'), DONE if last else ('key', k + 1, 0, (False, None)))
            return ('lit', ('' if j == 0 else ',') + '"%s":' % self.keys[j], ('value', k, j, it))
        if kind == 'value':
            _, k, j, it = desc
            key = self.keys[j]
            if key == self.spec['alias_key']:
                return ('lit', '"%s"' % self.contract.aliases[k], ('key', k, j + 1, it))
            if key == self.spec['status_key']:
                nonempty, _ = it
                choices = ((self.statuses['semantic'],) if nonempty
                           else tuple(sorted((self.statuses['semantic'], self.statuses['none']))))
                return ('lit', '"', ('choice', k, j, '', choices, it))
            array = 'ids' if key in self.spec['id_arrays'] else 'strs'
            return ('lit', '[', (array, k, j, (), True, it))
        return desc

    def close_rule(self, j, it, used):
        """(may the array close now, may it take another element) for key j of an item."""
        key = self.keys[j]
        if key not in self.semantic:
            return True, True
        nonempty, status = it
        if status == self.statuses['none']:
            return not used, False
        if status == self.statuses['semantic'] and not nonempty and self.last_semantic(j) and not used:
            return False, True
        return True, True

    def after_array(self, k, j, it, used):
        key = self.keys[j]
        nonempty, status = it
        if key in self.semantic and used:
            nonempty = True
        return self.resolve(('key', k, j + 1, (nonempty, status)))

    def step(self, state, ch):
        kind = state[0]
        if kind == 'lit':
            _, rest, nxt = state
            if ch != rest[0]:
                return None
            return ('lit', rest[1:], nxt) if len(rest) > 1 else self.resolve(nxt)
        if kind == 'items':
            if ch == '{':
                return self.resolve(('key', 0, 0, (False, None)))
            if ch == self.refusal[0]:
                return ('lit', self.refusal[1:], DONE)
            return None
        if kind in ('ids', 'strs'):
            _, k, j, used, first, it = state
            may_close, may_add = self.close_rule(j, it, used)
            if ch == ']' and may_close:
                return self.after_array(k, j, it, used)
            element = ('id', k, j, used, '', it) if kind == 'ids' else ('str', k, j, used, '', None, it)
            if kind == 'ids' and not self.remaining(k, j, used):
                may_add = False
            if not may_add:
                return None
            if first and ch == '"':
                return element
            if not first and ch == ',':
                return ('lit', '"', element)
            return None
        if kind == 'id':
            _, k, j, used, partial, it = state
            left = self.remaining(k, j, used)
            if ch == '"':
                return ('ids', k, j, used + (partial,), False, it) if partial in left else None
            grown = partial + ch
            return ('id', k, j, used, grown, it) if any(c.startswith(grown) for c in left) else None
        if kind == 'str':
            _, k, j, used, content, esc, it = state
            if esc is None:
                if ch == '"':
                    return ('strs', k, j, used + (content,), False, it) if content.strip() and content not in used else None
                if ch == '\\':
                    return ('str', k, j, used, content, '', it)
                if ch < ' ':
                    return None
                return ('str', k, j, used, content + ch, None, it)
            if esc == '':
                if ch in ESCAPES:
                    return ('str', k, j, used, content + ESCAPES[ch], None, it)
                return ('str', k, j, used, content, 'u', it) if ch == 'u' else None
            if ch not in HEX:
                return None
            digits = esc[1:] + ch
            if len(digits) == 4:
                return ('str', k, j, used, content + chr(int(digits, 16)), None, it)
            return ('str', k, j, used, content, 'u' + digits, it)
        if kind == 'choice':
            _, k, j, partial, choices, it = state
            if ch == '"':
                return self.resolve(('key', k, j + 1, (it[0], partial))) if partial in choices else None
            grown = partial + ch
            return ('choice', k, j, grown, choices, it) if any(c.startswith(grown) for c in choices) else None
        return None

    def remaining(self, k, j, used):
        return [c for c in self.contract.ids[self.contract.aliases[k]][self.keys[j]] if c not in used]

    def free(self, state):
        """True inside a JSON string's free text, where any character but a quote, a backslash or
        a control character keeps the state a string."""
        return state[0] == 'str' and state[5] is None

    def next_chars(self, state):
        """The characters a non-free state admits (a small set)."""
        kind = state[0]
        if kind == 'lit':
            return {state[1][0]}
        if kind == 'items':
            return {'{', self.refusal[0]}
        if kind in ('ids', 'strs'):
            return {'"', ',', ']'}
        if kind == 'id':
            left = self.remaining(state[1], state[2], state[3])
            return {c[len(state[4])] for c in left if c.startswith(state[4]) and len(c) > len(state[4])} | {'"'}
        if kind == 'choice':
            return {c[len(state[3])] for c in state[4] if c.startswith(state[3]) and len(c) > len(state[3])} | {'"'}
        if kind == 'str':
            return set(ESCAPES) | {'u'} if state[5] == '' else set(HEX)
        return set()

    def walk(self, state, text):
        for ch in text:
            state = self.step(state, ch)
            if state is None:
                return None
        return state


    def accepting(self, state):
        """True where the stop token is admitted: the reply is complete."""
        return state == DONE

    def unrestricted(self, state):
        return False


def accepts(contract, spec, text):
    """True when `text` is a complete reply of the request's canonical language."""
    return Grammar(contract, spec).walk(Grammar(contract, spec).start(), text) == DONE


# --- the general envelope of the local auditor agents (config/envelope_decoding.json)
ENVELOPE_DECLARATION = 'config/envelope_decoding.json'
CONTRACTS = 'config/agent_contracts.json'
WHITESPACE = ' \t\n\r'
DIGITS = '0123456789'
# The characters a structural (non-string, non-tail) state can admit: printable ASCII and JSON
# whitespace. Keys, literals, numbers and escapes are ASCII; anything else is string content.
STRUCTURAL = [chr(c) for c in range(32, 127)] + list('\t\n\r')
TAIL = ('tail',)
NUMBER = {  # phase: {character class: next phase}; terminal phases end at any other character
    'sign': {'0': 'zero', '1': 'int'},
    'zero': {'.': 'dot', 'e': 'e'},
    'int': {'0': 'int', '1': 'int', '.': 'dot', 'e': 'e'},
    'dot': {'0': 'frac', '1': 'frac'},
    'frac': {'0': 'frac', '1': 'frac', 'e': 'e'},
    'e': {'+': 'esign', '0': 'exp', '1': 'exp'},
    'esign': {'0': 'exp', '1': 'exp'},
    'exp': {'0': 'exp', '1': 'exp'},
}
NUMBER_END = ('zero', 'int', 'frac', 'exp')


def _number_class(ch):
    if ch == '0':
        return '0'
    if ch in DIGITS:
        return '1'
    if ch in 'eE':
        return 'e'
    if ch in '+-':
        return '+'
    return ch


def envelope_declaration(root=None):
    """(the envelope declaration, its SHA-256 with CRLF normalised to LF); refused when unsound."""
    data = (Path(root or ROOT) / ENVELOPE_DECLARATION).read_bytes().replace(b'\r\n', b'\n')
    value = json.loads(data.decode('utf-8'))
    require(value.get('schema_version') == 1 and isinstance(value.get('name'), str)
            and type(value.get('version')) is int, 'Invalid envelope decoding declaration')
    require(value.get('envelope_keys') == ['agent', 'doc_id', 'items'], 'The envelope keys are agent, doc_id, items')
    require(isinstance(value.get('agents'), dict) and value['agents']
            and all(isinstance(v, dict) and isinstance(v.get('backend'), str) for v in value['agents'].values()),
            'Each declared agent names its backend')
    require(all(isinstance(v.get('leading_keys', []), list) and all(isinstance(k, str) for k in v.get('leading_keys', []))
                for v in value['agents'].values()), 'Leading keys are a list of key names')
    core = list(value.get('core_required') or []) + list(value.get('core_optional') or []) + list(value.get('runtime_optional') or [])
    require(core and len(set(core)) == len(core), 'The core keys are distinct')
    require(type(value.get('whitespace_run_max')) is int and value['whitespace_run_max'] > 0,
            'The whitespace run is bounded')
    require(all(isinstance(f, str) and f.startswith('```') for f in value.get('fences') or []), 'A fence opens with ```')
    require(value.get('status') in ('active', 'off'), 'The constraint is active or off')
    return value, hashlib.sha256(data).hexdigest()


def declared_contracts(root=None):
    return json.loads((Path(root or ROOT) / CONTRACTS).read_text(encoding='utf-8'))


class EnvelopeContract:
    """One agent's envelope: its name, the validator's required item keys (the core keys, then
    the contract's `required`), the spellings admitted for each (a declared core alias in its
    canonical key's place), how many of them lead every item in that order (`leading`, the
    order the agent's saved valid items write them), and the other declared field names an item
    may carry. Keys after the leading ones come in any order, each at most once, and the item
    closes only when every required key is written."""

    def __init__(self, agent, required, spellings, optional, leading=None):
        require(isinstance(agent, str) and agent and required, 'An envelope contract names its agent and keys')
        self.agent = agent
        self.required = tuple(required)
        self.spellings = tuple(tuple(s) for s in spellings)
        self.leading = self.required if leading is None else tuple(leading)
        require(self.leading == self.required[:len(self.leading)] or
                (set(self.leading) <= set(self.required) and len(set(self.leading)) == len(self.leading)),
                'The leading keys are required keys')
        spelled = {key: names for key, names in zip(self.required, self.spellings)}
        self.optional = tuple(sorted(set(optional) - set(self.required) - {s for names in self.spellings for s in names}))
        rest = tuple(k for k in self.required if k not in self.leading)
        self.lead_spellings = tuple(spelled[k] for k in self.leading)
        self.pool = rest + self.optional
        self.pool_spellings = tuple(spelled.get(k, (k,)) for k in self.pool)
        self.pool_required = sum(1 << i for i, k in enumerate(self.pool) if k in rest)

    @classmethod
    def for_agent(cls, agent, spec, contract=None, root=None):
        """The agent's contract as the validator reads it (agent_wrapper._contract_missing:
        CORE_ITEM_REQUIRED, then the contract's `required`), with its declared fields, the
        finding_record fields and the runtime-owned keys as the optional names, and the leading
        keys its declaration names (every required key when it names none)."""
        declared = declared_contracts(root)
        contract = contract if isinstance(contract, dict) and contract else declared['contracts'][agent]
        required = list(spec['core_required']) + [k for k in contract.get('required', []) if k not in spec['core_required']]
        aliases = declared.get('core_field_aliases') or {}
        spellings = [[key] + sorted(a for a, canonical_key in aliases.items() if canonical_key == key) for key in required]
        record = declared.get('finding_record') or {}
        optional = list(spec['core_optional']) + list(spec.get('runtime_optional') or [])             + [k for k in contract.get('fields', {}) if k != 'finding_record'] + list(record.get('fields') or [])
        return cls(agent, required, spellings, optional, spec['agents'].get(agent, {}).get('leading_keys'))

    def digest(self):
        return hashlib.sha256(canonical(dict(agent=self.agent, required=list(self.required),
                                             spellings=[list(s) for s in self.spellings], leading=list(self.leading),
                                             optional=list(self.optional))).encode('utf-8')).hexdigest()


class EnvelopeGrammar:
    """The envelope language of one agent's call, as a character-level recognizer with the
    Grammar interface (start, step, walk, free, next_chars, accepting, unrestricted). States
    are small tuples that carry no text, so the admitted tokens of a state are computed once
    per tokenizer and agent (signature)."""

    def __init__(self, contract, spec):
        self.contract, self.spec = contract, spec
        self.ws = spec['whitespace_run_max']
        self.fences = tuple(spec['fences'])
        self.lexemes = ('"agent"', ':', '"%s"' % contract.agent, ',', '"doc_id"', ':', None, ',', '"items"', ':', '[')
        self.signature = hashlib.sha256(('%s|%s|%d|%s' % (contract.digest(), canonical(self.fences), self.ws,
                                                         canonical(spec['envelope_keys']))).encode('utf-8')).hexdigest()

    def start(self):
        return ('lead', '', 0)

    def gap(self, desc):
        return ('gap', 0, desc)

    def names(self, j, opt):
        """The key spellings admitted at item position j (a leading key's own spellings, then
        every pool key not yet written)."""
        if j < len(self.contract.leading):
            return self.contract.lead_spellings[j]
        return tuple(n for i, names in enumerate(self.contract.pool_spellings) if not opt >> i & 1 for n in names)

    def after_key(self, j, opt, name):
        if j < len(self.contract.leading):
            return ('K', j + 1, opt)
        index = next(i for i, names in enumerate(self.contract.pool_spellings) if name in names)
        return ('K', j, opt | 1 << index)

    def required_value(self, j, name):
        if j < len(self.contract.leading):
            return True
        index = next(i for i, names in enumerate(self.contract.pool_spellings) if name in names)
        return bool(self.contract.pool_required >> index & 1)

    def closable(self, j, opt):
        return j == len(self.contract.leading) and opt & self.contract.pool_required == self.contract.pool_required

    # what comes next (whitespace allowed before it), entered with its first character
    def enter(self, desc, ch):
        kind = desc[0]
        if kind == 'E':
            i = desc[1]
            nxt = ('E', i + 1) if i + 1 < len(self.lexemes) else ('ITEMS', True)
            text = self.lexemes[i]
            if text is None:
                return ('s', False, False, None, nxt) if ch == '"' else None
            if ch != text[0]:
                return None
            return ('lit', text[1:], nxt) if len(text) > 1 else self.gap(nxt)
        if kind == 'ITEMS':
            if ch == '{' and desc[1]:
                return self.gap(('K', 0, 0))
            if ch == ']':
                return self.gap(('CLOSE',))
            if ch == ',' and not desc[1]:
                return self.gap(('ISTART',))
            return None
        if kind == 'ISTART':
            return self.gap(('K', 0, 0)) if ch == '{' else None
        if kind == 'K':
            _, j, opt = desc
            if j == 0 and opt == 0:
                return ('kn', '', j, opt) if ch == '"' else None
            if ch == '}' and self.closable(j, opt):
                return self.gap(('ITEMS', False))
            if ch == ',' and self.names(j, opt):
                return self.gap(('KQ', j, opt))
            return None
        if kind == 'KQ':
            return ('kn', '', desc[1], desc[2]) if ch == '"' else None
        if kind == 'COLON':
            _, j, opt, name = desc
            if ch != ':':
                return None
            return self.gap(('V', self.required_value(j, name), True, self.after_key(j, opt, name)))
        if kind == 'V':
            _, req, arr_ok, after = desc
            if ch == '"':
                return ('s', req, False, None, after)
            if ch == '-':
                return ('n', 'sign', after)
            if ch in DIGITS:
                return ('n', 'zero' if ch == '0' else 'int', after)
            if ch == 't':
                return ('lit', 'rue', after)
            if ch == 'f':
                return ('lit', 'alse', after)
            if ch == 'n' and not req:
                return ('lit', 'ull', after)
            if ch == '[' and arr_ok:
                return self.gap(('ARR', True, after))
            return None
        if kind == 'ARR':
            _, first, after = desc
            if ch == ']':
                return self.gap(after)
            element = ('V', False, False, ('ARR', False, after))
            if first:
                return self.enter(element, ch)
            return self.gap(element) if ch == ',' else None
        if kind == 'CLOSE':
            return TAIL if ch == '}' else None
        return None

    def step(self, state, ch):
        kind = state[0]
        if kind == 'tail':
            return TAIL
        if kind == 'gap':
            _, n, desc = state
            if ch in WHITESPACE:
                return ('gap', n + 1, desc) if n < self.ws else None
            return self.enter(desc, ch)
        if kind == 'lead':
            _, fence, n = state
            if (n == 0 or not fence) and any(f.startswith(fence + ch) for f in self.fences):
                return ('lead', fence + ch, 0)
            if fence and fence not in self.fences:
                return None
            if ch in WHITESPACE:
                return ('lead', fence, n + 1) if n < self.ws else None
            return self.gap(('E', 0)) if ch == '{' else None
        if kind == 'lit':
            _, rest, nxt = state
            if ch != rest[0]:
                return None
            return ('lit', rest[1:], nxt) if len(rest) > 1 else self.gap(nxt)
        if kind == 'kn':
            _, partial, j, opt = state
            names = self.names(j, opt)
            if ch == '"':
                return self.gap(('COLON', j, opt, partial)) if partial in names else None
            grown = partial + ch
            return ('kn', grown, j, opt) if any(n.startswith(grown) for n in names) else None
        if kind == 's':
            _, req, nonempty, esc, after = state
            if esc is None:
                if ch == '"':
                    return self.gap(after) if nonempty or not req else None
                if ch == '\\':
                    return ('s', req, nonempty, '', after)
                if ch < ' ':
                    return None
                return state if nonempty else ('s', req, True, None, after)
            if esc == '':
                if ch in ESCAPES:
                    return ('s', req, True, None, after)
                return ('s', req, nonempty, 'u', after) if ch == 'u' else None
            if ch not in HEX:
                return None
            digits = esc[1:] + ch
            return ('s', req, True, None, after) if len(digits) == 4 else ('s', req, nonempty, 'u' + digits, after)
        if kind == 'n':
            _, phase, after = state
            nxt = NUMBER[phase].get(_number_class(ch))
            if nxt is not None:
                return ('n', nxt, after)
            return self.step(self.gap(after), ch) if phase in NUMBER_END else None
        return None

    def walk(self, state, text):
        for ch in text:
            state = self.step(state, ch)
            if state is None:
                return None
        return state

    def free(self, state):
        return state[0] == 's' and state[3] is None

    def next_chars(self, state):
        return {ch for ch in STRUCTURAL if self.step(state, ch) is not None}

    def accepting(self, state):
        return state == TAIL

    def unrestricted(self, state):
        return state == TAIL


def envelope_accepts(contract, spec, text):
    """True when `text` is a complete reply of the agent's envelope language (the envelope
    closed; anything after it is the tail)."""
    grammar = EnvelopeGrammar(contract, spec)
    return grammar.accepting(grammar.walk(grammar.start(), text) or ('none',))


class TokenTable:
    """Each token's text as it extends a decoded reply (an anchor token keeps a leading space a
    SentencePiece tokenizer would drop), indexed by first character, with the tokens that are
    pure string content precomputed. Built once per tokenizer."""

    _CACHE = {}

    def __init__(self, tok):
        anchor = tok.encode('{', add_special_tokens=False)[-1]
        head = tok.decode([anchor], skip_special_tokens=True)
        size = len(tok)
        texts = tok.batch_decode([[anchor, t] for t in range(size)], skip_special_tokens=True)
        self.size = size
        self.strings = [s[len(head):] if s.startswith(head) else tok.decode([t], skip_special_tokens=True)
                        for t, s in enumerate(texts)]
        self.by_first = {}
        self.quote_tokens = []
        safe = []
        for t, s in enumerate(self.strings):
            if not s:
                continue
            self.by_first.setdefault(s[0], []).append(t)
            special = next((c for c in s if c in '"\\' or c < ' '), None)
            if special is None:
                safe.append(t)
            elif special in '"\\':
                self.quote_tokens.append(t)
        self.safe = safe
        self.admitted_cache = {}

    @classmethod
    def of(cls, tok):
        entry = cls._CACHE.get(id(tok))
        if entry is None or entry[0] is not tok:
            entry = (tok, cls(tok))
            cls._CACHE[id(tok)] = entry
        return entry[1]


class ContractProcessor:
    """The logits processor of one constrained call (transformers' __call__(input_ids, scores)
    contract, batch of one): every token whose text would leave the request's canonical language
    is set to -inf; the stop tokens are admitted only once the reply is complete. It reads the
    reply as the caller will (the tokenizer's decode of the generated ids, special tokens
    skipped) and counts every step where the model's own top token was not admitted."""

    def __init__(self, contract, spec, tok, prompt_tokens, eos_ids, record, grammar=None):
        import torch
        self.torch, self.tok, self.prompt_tokens = torch, tok, int(prompt_tokens)
        self.grammar = grammar if grammar is not None else Grammar(contract, spec)
        self.table = TokenTable.of(tok)
        eos = eos_ids if isinstance(eos_ids, (list, tuple)) else [eos_ids]
        self.eos = [int(e) for e in eos if e is not None]
        require(self.eos, 'A constrained call needs its stop tokens')
        self.safe = torch.zeros(self.table.size, dtype=torch.bool)
        self.safe[torch.tensor(self.table.safe, dtype=torch.long)] = True
        self.everything = torch.ones(self.table.size, dtype=torch.bool)
        self.text, self.state = '', self.grammar.start()
        self.counts = record
        record.update(steps=0, interventions=0, first_intervention_step=None, dead_end=False)

    def state_of(self, text):
        if text.startswith(self.text) and self.state is not None:
            state = self.grammar.walk(self.state, text[len(self.text):])
        else:
            state = self.grammar.walk(self.grammar.start(), text)
        self.text, self.state = text, state
        return state

    def admitted(self, state):
        """The admitted token ids (a list) beside the free-text mask (a bool tensor or None).
        A grammar whose states carry no text (a `signature`) has each state's answer computed
        once per tokenizer and kept on the token table."""
        grammar, table = self.grammar, self.table
        if state is None or state == DONE:
            return [], None
        if grammar.unrestricted(state):
            return [], self.everything
        signature = getattr(grammar, 'signature', None)
        if signature is None:
            return self._admitted(state)
        key = (signature, state)
        found = table.admitted_cache.get(key)
        if found is None:
            ids, free = self._admitted(state)
            found = table.admitted_cache[key] = (ids, free is not None)
        return found[0], (self.safe if found[1] else None)

    def _admitted(self, state):
        grammar, table = self.grammar, self.table
        ids = []
        if grammar.free(state):
            for t in table.quote_tokens:
                if grammar.walk(state, table.strings[t]) is not None:
                    ids.append(t)
            return ids, self.safe
        for ch in grammar.next_chars(state):
            for t in table.by_first.get(ch, ()):
                if grammar.walk(state, table.strings[t]) is not None:
                    ids.append(t)
        return ids, None

    def __call__(self, input_ids, scores):
        torch = self.torch
        require(input_ids.shape[0] == 1 and scores.shape[0] == 1, 'Contract decoding runs a batch of one')
        generated = input_ids[0, self.prompt_tokens:].tolist()
        state = self.state_of(self.tok.decode(generated, skip_special_tokens=True))
        ids, free = self.admitted(state)
        width = int(scores.shape[-1])
        mask = torch.zeros(width, dtype=torch.bool)
        if free is not None:
            mask[:min(width, self.table.size)] = free[:width]
        if ids:
            mask[torch.tensor([t for t in ids if t < width], dtype=torch.long)] = True
        stops = torch.tensor([e for e in self.eos if e < width], dtype=torch.long)
        if state is not None and self.grammar.accepting(state):
            mask[stops] = True
        elif not bool(mask.any()):
            self.counts['dead_end'] = True
            mask[stops] = True
        top = int(scores[0].argmax())
        self.counts['steps'] += 1
        if not bool(mask[top]):
            self.counts['interventions'] += 1
            if self.counts['first_intervention_step'] is None:
                self.counts['first_intervention_step'] = self.counts['steps']
        return scores.masked_fill(~mask.to(scores.device).unsqueeze(0), float('-inf'))


class Constraint:
    """One constrained call: its processor, the generate() keyword that carries it, and the
    record that goes on the reply record and the call's usage (name, version, declaration
    digest, request digest, and what the processor counted)."""

    def __init__(self, contract, spec, digest, tok, prompt_tokens, eos_ids, source, grammar=None):
        scope = dict(owned_aliases=len(contract.aliases)) if grammar is None else dict(agent=contract.agent)
        self.record = dict(name=spec['name'], version=spec['version'], declaration_sha256=digest,
                           contract_sha256=contract.digest(), **scope, source=source)
        self.processor = ContractProcessor(contract, spec, tok, prompt_tokens, eos_ids, self.record, grammar)

    def generate_kwargs(self):
        from transformers import LogitsProcessorList
        return dict(logits_processor=LogitsProcessorList([self.processor]))

    def summary(self):
        return dict(self.record)


def active(root=None):
    """The declaration when the constraint is active, else None."""
    spec, digest = declaration(root)
    return (spec, digest) if spec['status'] == 'active' else None


def for_call(wrapper, tok, prompt_tokens, eos_ids, root=None):
    """The constraint of one local call, or None when the call is not the compact producer's.
    The compact producer is the PROCESSOR on local_producer bound with the validated messages
    by compact_contracts.bind_producer (report_optimized), which sets the owned spans, the
    grounding and the messages together; its declaration is that binding's own owned spans
    and grounding, the validator's sets. A wrapper carrying messages without a binding (no
    owned spans: a fixture that sets the prompt turns alone) has no declaration to decode
    under and gets none. A declared envelope agent (config/envelope_decoding.json: VERIFIER and
    PRACTICE_AUDITOR on local_auditor, ARCHIVIST and EDITOR_CLERK on local_producer) gets the
    envelope constraint of its own contract
    (for_envelope); every other call gets none."""
    envelope = for_envelope(wrapper, tok, prompt_tokens, eos_ids, root)
    if envelope is not None:
        return envelope
    if getattr(wrapper, 'name', None) != 'PROCESSOR' or getattr(wrapper, 'backend', None) != 'local_producer':
        return None
    owned = getattr(wrapper, '_owned_source_spans', None)
    if not getattr(wrapper, '_compact_messages', None) or not owned:
        return None
    found = active(root)
    if found is None:
        return None
    spec, digest = found
    contract = Contract.from_binding(owned, getattr(wrapper, '_compact_grounding', None), spec)
    return Constraint(contract, spec, digest, tok, prompt_tokens, eos_ids, 'binding')


def envelope_constraint(agent, tok, prompt_tokens, eos_ids, source, contract=None, root=None):
    """The envelope constraint of one call of a declared agent, built from its own contract."""
    spec, digest = envelope_declaration(root)
    require(agent in spec['agents'], 'No envelope declaration for agent %s' % agent)
    built = EnvelopeContract.for_agent(agent, spec, contract, root)
    return Constraint(built, spec, digest, tok, prompt_tokens, eos_ids, source, EnvelopeGrammar(built, spec))


def for_envelope(wrapper, tok, prompt_tokens, eos_ids, root=None):
    """The envelope constraint of a local call, or None: the agent and its backend must be
    declared, the declaration active, and the call an ordinary contract call (a wrapper bound to
    a compact contract, with its own source adapter, answers another shape and gets none)."""
    spec, _ = envelope_declaration(root)
    name = getattr(wrapper, 'name', None)
    declared = spec['agents'].get(name)
    if spec['status'] != 'active' or declared is None or getattr(wrapper, 'backend', None) != declared['backend']:
        return None
    if getattr(wrapper, '_compact_contract', None) or getattr(wrapper, '_source_adapter', None) \
            or getattr(wrapper, '_compact_messages', None):
        return None
    return envelope_constraint(name, tok, prompt_tokens, eos_ids, 'contract', getattr(wrapper, 'contract', None), root)


def for_prompt(prompt, tok, prompt_tokens, eos_ids, root=None, agent=None):
    """The constraint of a replayed compact producer prompt (no binding): its declaration read
    back from the prompt's own canonical payload (Contract.from_rendered). With `agent`, a
    declared envelope agent's replayed prompt: the envelope constraint of its own contract."""
    if agent is not None:
        return envelope_constraint(agent, tok, prompt_tokens, eos_ids, 'rendered_prompt', root=root)
    spec, digest = declaration(root)
    contract = Contract.from_rendered(prompt, spec)
    return Constraint(contract, spec, digest, tok, prompt_tokens, eos_ids, 'rendered_prompt')


def validate_rendered(prompt, reply, doc='replay'):
    """None when `reply` passes compact_contracts.producer UNCHANGED for the request the rendered
    prompt carries (owned spans rebuilt from the payload: the alias names the offset, the shown
    text is the span's text), else the validator's own reason. The refs Python placed are
    the markers in the shown text, so no grounding map is passed."""
    import bounded_extraction
    import compact_contracts
    _, spans = payload_spans(prompt)
    owned = []
    for span in spans:
        alias = span['alias']
        require(re.fullmatch(r's[0-9a-f]+', alias) is not None, 'An owned alias names its offset')
        start = int(alias[1:], 16)
        owned.append(bounded_extraction.Span(alias, start, start + len(span['text']), '', None, span['text']))
    try:
        compact_contracts.producer(json.loads(reply), owned, doc)
    except ValueError as exc:
        return str(exc).split(':', 1)[0][:80] or type(exc).__name__
    return None
