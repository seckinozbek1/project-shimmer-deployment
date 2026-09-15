"""Fresh V2 typed review; imports V1 validators without editing historical data."""
from pathlib import Path
import sys,json,re
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'benchmark/machine_adjudication_v1'))
import importlib.util
spec=importlib.util.spec_from_file_location('v1_review_controls',ROOT/'benchmark/machine_adjudication_v1/review.py')
v1=importlib.util.module_from_spec(spec);spec.loader.exec_module(v1)
import atoms
read,write,sha=v1.read,v1.write,v1.sha
WORK=ROOT/'output/machine_review_v2'
PROTOCOL='machine-agent-review-v2'


def packets():return {p.stem:read(p) for p in sorted((WORK/'reviewer_A/packets').glob('*.json'))}


def validate(value,packet,slot=None):
    if value.get('protocol')!=PROTOCOL:raise ValueError('V2 protocol required')
    if type(value.get('source_uncertainty_present')) is not bool or type(value.get('review_ambiguity')) is not bool:
        raise ValueError('Separate source uncertainty and review ambiguity required')
    if 'ambiguity' in value:raise ValueError('Legacy conflated ambiguity field prohibited')
    legacy=dict(value,ambiguity=value['review_ambiguity'])
    v1.validate(legacy,packet,slot)
    if packet['input']['role']=='producer':
        if not isinstance(value.get('gap_atoms'),list) or not isinstance(value.get('uncertainty_atoms'),list):
            raise ValueError('Typed producer atoms required')
        spans={s['alias']:s['text'] for s in packet['input']['source_spans']}
        items={i['span']:i for i in value['semantic_target'].get('items',[])}
        for alias,item in items.items():
            if set(item['refs'])!=set(re.findall(r'\bREF-\d{4,}\b',spans[alias])):
                raise ValueError('All owned per-span evidence refs required')
        for atom in value['gap_atoms']+value['uncertainty_atoms']:
            alias=atom['span']
            if alias not in items:raise ValueError('Atom without owned target item')
            atoms.ground(atom,spans[alias],alias,items[alias]['refs'])
        if any(a['type']!='missing_information' for a in value['gap_atoms']):raise ValueError('Wrong gap type')
        if any(a['type']=='missing_information' for a in value['uncertainty_atoms']):raise ValueError('Gap is not uncertainty')
        for alias,item in items.items():
            if len(item['questions'])!=sum(a['span']==alias for a in value['gap_atoms']):raise ValueError('Gap wording/atom cardinality mismatch')
            if len(item['uncertainty'])!=sum(a['span']==alias for a in value['uncertainty_atoms']):raise ValueError('Uncertainty wording/atom cardinality mismatch')
        if len(atoms.material(value['gap_atoms']))!=len(value['gap_atoms']) or len(atoms.material(value['uncertainty_atoms']))!=len(value['uncertainty_atoms']):
            raise ValueError('Duplicate semantic atom')
        if value['source_uncertainty_present']!=bool(value['uncertainty_atoms']):raise ValueError('Source uncertainty flag contradicts atoms')
    return True


def material(value,role):
    legacy=dict(value,ambiguity=value['review_ambiguity'])
    result=v1.material(legacy,role)
    result['source_uncertainty_present']=value['source_uncertainty_present']
    if role=='producer':
        if 'items' in result:
            for i in result['items']:i.pop('questions');i.pop('uncertainty')
        result['gaps']=atoms.material(value['gap_atoms']);result['uncertainty']=atoms.material(value['uncertainty_atoms'])
    return result


def consensus(values,role):
    from collections import Counter
    hashes=[sha(material(v,role)) for v in values];key,n=Counter(hashes).most_common(1)[0]
    return dict(state='unanimous' if n==3 else 'majority' if n==2 else 'no_majority',
      selected_slot=values[hashes.index(key)]['slot'] if n>=2 else None,
      agreeing_slots=[v['slot'] for v,h in zip(values,hashes) if h==key] if n>=2 else [],
      material_hashes=dict(zip([v['slot'] for v in values],hashes)))


def candidate(row,label,valid,dispute):
    return (row['split'] in ('train','dev') and row['domain'] not in ('astronomy','ecology') and len(valid)==3
      and all(valid.values()) and label['valid'] and not label['review']['review_ambiguity'] and not dispute)


def verify_isolation(folder,hashes):
    folder=Path(folder)
    for path in (folder/'packets').iterdir():
        if path.is_symlink() or path.name not in hashes or sha(path.read_bytes())!=hashes[path.name]:raise ValueError('Packet isolation drift')
    if {p.name for p in (folder/'packets').iterdir()}!=set(hashes):raise ValueError('Packet population drift')
    for name in ('authored_gold.json','v1_reviews','post_freeze','gold_target.json'):
        if (folder/name).exists():raise ValueError('Unapproved review context')
