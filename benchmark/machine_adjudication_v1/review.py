"""Gold-free machine review validation, exact structured consensus and freeze."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
WORK=ROOT/'output/machine_review_v1'
PROTOCOL='machine-agent-review-v1'
REASONS={'preserved_claim','missing_claim','added_claim','changed_label','changed_quantity','changed_unit',
         'gap_preserved','gap_omitted','evidence_insufficient','unsupported_attribution','ambiguity','uncertainty_preserved','uncertainty_omitted'}
sys.path.insert(0,str(ROOT/'scripts'))
import compact_contracts as cc
import bounded_extraction as ex


def read(path):
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=unique)


def sha(value):
    if not isinstance(value,bytes):value=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    return hashlib.sha256(value).hexdigest()


def write(path,value,exclusive=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x' if exclusive else 'w',encoding='utf-8') as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n')


def packets():
    return {p.stem:read(p) for p in sorted((WORK/'reviewer_A/packets').glob('*.json'))}


def effective(slot,ident):
    folder=WORK/('reviewer_'+slot)
    primary=folder/'reviews'/(ident+'.json')
    value=read(primary)
    repair=folder/'repairs'/(ident+'.json')
    if repair.exists():
        corrected=read(repair)
        if (corrected.get('original_sha256')!=sha(primary.read_bytes()) or
            corrected.get('repair_kind')!='schema_only_judgment_enum' or corrected.get('repair_attempt')!=1):
            raise ValueError('Unbound or excessive repair')
        rest={k:v for k,v in corrected.items() if k not in ('original_sha256','repair_kind','repair_attempt','semantic_judgment')}
        if rest!={k:v for k,v in value.items() if k!='semantic_judgment'}:
            raise ValueError('Schema repair altered semantic content')
        value=corrected
    return value


def machine_provenance(value):
    if value.get('provenance') not in ('independent_machine_agent_review','machine_agent_adjudication'):
        raise ValueError('Explicit machine provenance required')
    if value.get('human') is True or value.get('reviewer_kind')=='human' or value.get('independence_attestation') is True:
        raise ValueError('Machine output cannot claim human provenance')


def validate(value,packet,slot=None):
    machine_provenance(value)
    required={'packet_id','binding','slot','provenance','run_id','reviewed_at','input_sha256',
              'semantic_target','semantic_judgment','reason_components','ambiguity','rationale'}
    if not required<=set(value):raise ValueError('Machine review fields missing')
    if value['packet_id']!=packet['packet_id'] or value['input_sha256']!=packet['input_sha256']:
        raise ValueError('Packet/input binding mismatch')
    if value['binding']!=packet['response_template']['binding']:
        raise ValueError('Obsolete cohort/export binding')
    if slot and value['slot']!=slot:raise ValueError('Agent slot mismatch')
    if not isinstance(value['run_id'],str) or not value['run_id']:raise ValueError('Run identifier required')
    if datetime.fromisoformat(value['reviewed_at']).tzinfo is None:raise ValueError('Timestamp requires timezone')
    if type(value['ambiguity']) is not bool or not isinstance(value['rationale'],str) or not value['rationale'].strip():
        raise ValueError('Ambiguity and rationale required')
    if not isinstance(value['reason_components'],list) or not set(value['reason_components'])<=REASONS:
        raise ValueError('Unknown typed reason')
    obj=value['semantic_target'];inp=packet['input']
    if obj=={'items':[],'status':'refused'}:
        if value['semantic_judgment']!='INSUFFICIENT_EVIDENCE':raise ValueError('Refusal judgment mismatch')
        return True
    if inp['role']=='producer':
        spans=tuple(ex.Span(s['alias'],int(s['alias'][1:],16),int(s['alias'][1:],16)+len(s['text']),s['alias'],None,s['text']) for s in inp['source_spans'])
        cc.producer(obj,spans,packet['packet_id'])
        judgment='EXTRACTED' if any(i['status']=='extracted' for i in obj['items']) else 'EMPTY'
        if any(len(s['text'].strip())>=24 and s['text'].strip() in json.dumps(obj) for s in inp['source_spans']):
            raise ValueError('Producer source copying')
    else:
        owned_refs=set(re.findall(r'\bREF-\d{4,}\b',' '.join(s['text'] for s in inp['source_spans'])))
        cc.auditor(obj,packet['packet_id'],inp['required_refs'],sorted(owned_refs))
        judgment=obj['items'][0]['finding']
    if value['semantic_judgment']!=judgment:raise ValueError('Semantic judgment contradicts target')
    return True


def normal_string(text):
    return ' '.join(text.split())  # whitespace only; no similarity-based agreement


def material(value,role):
    obj=value['semantic_target']
    result=dict(judgment=value['semantic_judgment'],ambiguity=value['ambiguity'])
    if obj=={'items':[],'status':'refused'}:
        result['refused']=True
    elif role=='producer':
        result['items']=sorted([dict(span=i['span'],status=i['status'],**{k:sorted(set(normal_string(v) for v in i[k])) for k in ('claims','questions','uncertainty','refs')}) for i in obj['items']],key=lambda i:i['span'])
    else:
        result['items']=[dict(finding=i['finding'],refs=sorted(set(i['ref_ids'])),confidence=i['confidence']) for i in obj['items']]
    if role=='auditor':result['reason_components']=sorted(set(value['reason_components']))
    return result


def consensus(values,role):
    keys=[sha(material(v,role)) for v in values]
    counts=Counter(keys);key,n=counts.most_common(1)[0]
    return dict(state='unanimous' if n==3 else 'majority' if n==2 else 'no_majority',
                agreeing_slots=[v['slot'] for v,k in zip(values,keys) if k==key] if n>=2 else [],
                selected_slot=next(v['slot'] for v,k in zip(values,keys) if k==key) if n>=2 else None,
                material_hashes=dict(zip([v['slot'] for v in values],keys)))


def verify_clean_workspace(folder,expected_packet_hashes):
    folder=Path(folder)
    if {p.name for p in folder.iterdir()}-{'packets','INSTRUCTIONS.md','MACHINE_SCHEMA.json','reviews','repairs',
            'serialize_review_A.py','serialize_reviews.py','serialize_review.py','schema_feedback.json','PRIMARY_HASHES.json'}:
        raise ValueError('Unapproved reviewer workspace content')
    actual={p.name:sha(p.read_bytes()) for p in (folder/'packets').iterdir() if p.is_file()}
    if actual!=expected_packet_hashes:raise ValueError('Reviewer packet isolation drift')
    for p in (folder/'packets').iterdir():
        if p.is_symlink():raise ValueError('Isolation symlink')


def verify_pre_gold(path):
    manifest=read(path)
    if manifest['phase']!='MACHINE_LABELS_FROZEN_BEFORE_GOLD':raise ValueError('Pre-gold freeze required')
    for name,expected in manifest['hashes'].items():
        if sha((Path(path).parent/name).read_bytes())!=expected:raise ValueError('Machine evidence freeze drift')
    return manifest
