"""Frozen role/split boundaries for a separately authorized future experiment."""
from __future__ import annotations
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPERIMENT = 'first-domain-agnostic-tuning-v1'
APPROVED = 'benchmark/producer_coverage_amendment_v3/post_freeze/balanced_role_separated_candidates_v3.json'
PINS = {
    'producer': ('unsloth/Qwen2.5-7B-Instruct-bnb-4bit', 'bdd404162d94997f390efbfa660eb3f21cbbc81d'),
    'auditor': ('unsloth/Phi-3.5-mini-instruct-bnb-4bit', '5c20803aa197416f43fb455e55c85178775320cb'),
}
ASSETS = ('config.json', 'generation_config.json', 'tokenizer.json', 'tokenizer_config.json',
          'special_tokens_map.json', 'added_tokens.json', 'merges.txt', 'vocab.json', 'tokenizer.model')
MODULES = ('q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj')

def require(condition, message):
    if not condition:
        raise ValueError(message)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')

def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value)).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, indent=2, ensure_ascii=False).encode('utf8') + b'\n')

def checked(path, expected):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'Missing or linked input: ' + str(path))
    data = path.read_bytes()
    require(digest(data) == expected, 'Hash mismatch: ' + str(path))
    return json.loads(data)

def frozen():
    manifest = read(HERE/'freeze.json')
    for name, sha in manifest['files'].items():
        p = ROOT/name
        require(p.is_file() and not p.is_symlink() and digest(p.read_bytes()) == sha,
                'Frozen experiment changed: ' + name)
    return manifest

def load_rows(role, split, *, gradient=False):
    require(role in PINS and split in ('train','dev'), 'Unapproved role/split')
    require(not gradient or split == 'train', 'DEV/evaluation cannot enter gradient dataset')
    manifest = read(HERE/role/'dataset.json')
    spec = manifest['splits'][split]
    rows = checked(HERE/role/(split+'.json'), spec['sha256'])
    require(len(rows) == spec['count'], 'Population count mismatch')
    require([r['example_id'] for r in rows] == spec['ids'], 'Population identity mismatch')
    for row in rows:
        validate_row(row, role, split, spec['row_hashes'])
    return rows

def validate_row(row, role, split, hashes):
    require(row['role'] == role and row['split'] == split, 'Role/split contamination')
    require(row['example_id'] in hashes and digest(row) == hashes[row['example_id']], 'Unapproved row')
    require(row['input']['role'] == role, 'Input role mismatch')
    require(row.get('domain') not in ('astronomy','ecology'), 'Held-out domain')

def dependencies():
    sys.path.insert(0, str(ROOT/'scripts'))
    sys.path.insert(0, str(ROOT/'benchmark/producer_coverage_amendment_v3'))
    sys.path.insert(0, str(ROOT/'benchmark/task_semantics'))
    import compact_contracts, bounded_extraction, semantics, core
    return compact_contracts, bounded_extraction, semantics, core

def target(row):
    cc, ex, semantics, core = dependencies()
    if row['role'] == 'producer':
        result = semantics.validate_label(row['typed_label'], row['input'])
        require(result == row['canonical_target'], 'Frozen renderer disagreement')
    else:
        result = row['semantic_target']
    record = scoring_record(row, result)
    state, valid, _ = core.classify(record, canonical(result).decode())
    require(valid, 'Invalid frozen target contract')
    return canonical(result).decode()

def scoring_record(row, result=None):
    packet = row['input']
    source = ''.join(s['text'] for s in packet['source_spans'])
    require([s['alias'] for s in packet['source_spans']] == ['s0'], 'Unregistered source layout')
    result = result if result is not None else row.get('canonical_target', row.get('semantic_target'))
    refused = result == {'items': [], 'status': 'refused'}
    return dict(example_id=row['example_id'], role=row['role'], split=row['split'],
        document_family=row.get('document_family',row['example_id']), source_text=source,
        ledger_max_chars=max(1,len(source)+1), owned_aliases=['s0'],
        extraction_text=packet.get('extraction',''), supplied_refs=packet['supplied_refs'],
        required_refs=packet['required_refs'], routed_rules=packet.get('routed_rules',[]),
        gold_target=result, expected_refusal=refused,
        abstract_relation=('INSUFFICIENT_EVIDENCE' if refused else
            (result['items'][0]['finding'] if row['role']=='auditor' else 'EXTRACTED')))

def messages(row):
    cc, _, semantics, _ = dependencies()
    instruction = cc.PRODUCER if row['role']=='producer' else cc.AUDITOR
    if row['role']=='producer':
        instruction += '\nUse producer-semantic-policy-v3 canonical Gap/Uncertainty JSON strings. '
        instruction += 'Preserve absence, temporal role, order/content and epistemic distinctions. '
        instruction += 'Structural headings alone are not propositions. '
        instruction += 'Each Gap/Uncertainty object has category, subject, attribute, ordinal, relation, state, scope and unit; use exact finite policy values.'
        instruction += '\nFinite attributes: '+','.join(sorted(semantics.ATTRS))+'. '
        instruction += 'Gap categories: missing_information, explicit_question, explicit_nonoccurrence; uncertainty category: unknown. '
        instruction += 'Subjects: owned_record, entry, amendment, submission, event. Ordinal: null,1,2,3,next,previous,later. '
        instruction += 'State: unspecified,requested,absent,not_recorded,not_submitted,did_not_occur,unknown. '
        instruction += 'scope=owned_record; relation=null; unit=null. Canonical strings begin Gap: or Uncertainty: followed by the JSON object. '
        instruction += 'Conflict is not epistemic uncertainty; absence is not unknown occurrence; recording, event, submission and authorization times differ. '
        instruction += 'Order differs from content; first, next, previous and later retain their source meanings.'
    return [{'role':'system','content':instruction},
            {'role':'user','content':canonical(row['input']).decode()}]

def cached(role, cache=None):
    name, revision = PINS[role]
    root = Path(cache) if cache else Path.home()/'.cache/huggingface/hub'
    return root/('models--'+name.replace('/','--'))/'snapshots'/revision

def tokenizer(role, cache=None):
    from transformers import AutoTokenizer
    spec = read(HERE/role/'experiment.json')
    path = cached(role,cache)
    for name, sha in spec['asset_hashes'].items():
        require(digest((path/name).read_bytes()) == sha, 'Pinned tokenizer/config mismatch')
    return AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)

def encode(row, tok, maximum=None):
    msgs = messages(row)
    answer = target(row)
    prompt = tok.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True)
    rendered = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    text = tok.apply_chat_template(msgs+[{'role':'assistant','content':answer}], tokenize=False, add_generation_prompt=False)
    ids = tok(text, add_special_tokens=False, truncation=False)['input_ids']
    require(ids[:len(prompt)] == prompt, 'Assistant boundary is not an exact token prefix')
    require(ids == tok.apply_chat_template(msgs+[{'role':'assistant','content':answer}], tokenize=True, add_generation_prompt=False), 'Duplicate special-token handling')
    suffix = ids[len(prompt):]
    require(suffix and tok.eos_token_id in suffix, 'Missing native terminal token')
    require(suffix.count(tok.eos_token_id)==1, 'Duplicate target EOS')
    decoded = tok.decode(suffix, skip_special_tokens=False)
    require(decoded.startswith(answer), 'Decoded assistant target mismatch')
    require(maximum is None or len(ids)<=maximum, 'Sequence exceeds frozen ceiling; truncation forbidden')
    labels = [-100]*len(prompt)+suffix
    return dict(input_ids=ids, attention_mask=[1]*len(ids), labels=labels,
        prompt_length=len(prompt), prompt=rendered, target=answer,
        lengths=dict(raw_input=len(tok(canonical(row['input']).decode(),add_special_tokens=False)['input_ids']),
                     rendered_prompt=len(prompt),target=len(suffix),total=len(ids)),
        terminal=decoded[len(answer):])

class TargetOnlyCollator:
    def __init__(self, pad_id, maximum, tensor=False):
        self.pad_id,self.maximum,self.tensor=pad_id,maximum,tensor
    def __call__(self, rows):
        width=max(len(r['input_ids']) for r in rows)
        require(width<=self.maximum,'Collator refuses truncation')
        batch={k:[] for k in ('input_ids','attention_mask','labels')}
        for r in rows:
            n=len(r['input_ids']); p=r['prompt_length']
            require(r['labels'][:p]==[-100]*p and r['labels'][p:]==r['input_ids'][p:], 'Target-only mask mismatch')
            for key,pad in [('input_ids',self.pad_id),('attention_mask',0),('labels',-100)]:
                batch[key].append(r[key]+[pad]*(width-n))
        if self.tensor:
            import torch
            return {k:torch.tensor(v,dtype=torch.long) for k,v in batch.items()}
        return batch

def adapter_identity(directory, role, step):
    directory=Path(directory)
    names=('adapter_config.json','adapter_model.safetensors')
    hashes={name:digest((directory/name).read_bytes()) for name in names}
    return dict(experiment=EXPERIMENT,role=role,step=step,base_model=PINS[role][0],
                revision=PINS[role][1],files=hashes,sha256=digest(hashes))

def verify_adapter(directory, identity, role):
    require(identity==adapter_identity(directory,role,identity['step']), 'Adapter identity/hash mismatch')
    cfg=read(Path(directory)/'adapter_config.json')
    require(cfg['base_model_name_or_path']==PINS[role][0], 'Adapter base mismatch')
    require(cfg.get('revision')==PINS[role][1], 'Adapter revision mismatch')
    return identity
