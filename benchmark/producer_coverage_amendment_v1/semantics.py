"""Frozen typed policy and existing-wire canonical renderer; no dataset reads."""
from pathlib import Path
import json,re,hashlib,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import compact_contracts as cc
import bounded_extraction as ex
POLICY='producer-semantic-policy-v1';PROTOCOL='producer-coverage-amendment-v1';RENDERER='producer-target-renderer-v1'
ATTRS={'reporting_date','recording_date','observation_date','effective_time','recorder','interpretation','ratification_status','entry_content','entry_order','quantity','identity','state'}
ALIASES={'date_of_report':'reporting_date','report_date':'reporting_date','reporting_date':'reporting_date','recorded_date':'recording_date','status_of_ratification':'ratification_status','who_recorded':'recorder'}
FIELDS={'kind','category','subject','attribute','relation','scope','unit','span','refs','origin','support'}
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def digest(v):return hashlib.sha256(v if isinstance(v,bytes) else json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def slug(v):return re.sub(r'[^a-z0-9]+','_',v.lower()).strip('_')
def atom(kind,attribute,span='s0',refs=(),support='The delivery date is absent.',**kw):
 return dict(kind=kind,category='missing_information' if kind=='gap' else 'unknown',subject='owned_record',attribute=attribute,relation=None,scope='owned_record',unit=None,span=span,refs=list(refs),origin='source_explicit',support=support,**kw)
def normalize(a):
 if set(a)-{'wording'}!=FIELDS:raise ValueError('Exact typed fields required')
 n={k:a[k] for k in FIELDS-{'support'}}
 n['attribute']=ALIASES.get(slug(n['attribute']),slug(n['attribute']))
 if n['attribute'] not in ATTRS:raise ValueError('Unsupported attribute')
 if n['kind'] not in ('gap','uncertainty') or n['category'] not in ({'missing_information','explicit_question'} if n['kind']=='gap' else {'unknown'}):raise ValueError('Unsupported semantic category')
 if n['origin']!='source_explicit':raise ValueError('Inferred atom prohibited')
 if n['relation'] not in (None,'first','next','before','after'):raise ValueError('Unsupported order relation')
 if not re.fullmatch(r'owned_record|amendment|entry:[1-9][0-9]*|entity:[a-z0-9_]+',n['subject']):raise ValueError('Subject must be explicit structured referent')
 if not isinstance(a['support'],str) or not a['support'].strip():raise ValueError('Source support required')
 for k in ('scope','span'):
  if not isinstance(n[k],str) or not n[k]:raise ValueError('Binding required')
 if n['unit'] is not None and (not isinstance(n['unit'],str) or not n['unit']):raise ValueError('Unit must be null or explicit')
 if not isinstance(n['refs'],list) or any(not re.fullmatch(r'REF-[0-9]{4,}',x) for x in n['refs']) or len(set(n['refs']))!=len(n['refs']):raise ValueError('Invalid refs')
 n['refs']=sorted(n['refs']);return n

def material_atoms(values):return sorted(json.dumps(normalize(a),sort_keys=True) for a in values)
def evidence(a,text,refs):
 n=normalize(a)
 if a['support'] not in text:raise ValueError('Support absent from owned source')
 if set(n['refs'])!=set(refs):raise ValueError('Required owned refs not preserved')
 cue=a['support'].lower()
 if n['kind']=='uncertainty' and not re.search(r'uncertain|unclear|unknown|unresolved|undetermined|not known',cue):raise ValueError('Conflict alone is not epistemic uncertainty')
 if n['kind']=='gap' and not re.search(r'\?|missing|unavailable|not (?:supplied|provided|recorded)|absent|unnamed|no .*period',cue):raise ValueError('No explicit gap/question support')
 return n

def render_atom(a):
 n=normalize(a);head={'missing_information':'Missing information','explicit_question':'Explicit question','unknown':'Explicit unknown'}[n['category']]
 return head+': '+'; '.join(str(n[k]) if n[k] is not None else 'none' for k in ('subject','attribute','relation','scope','unit'))+'.'

def render(label):
 if label['status']=='refused':
  if label['items']:raise ValueError('Refusal cannot carry items')
  return {'items':[],'status':'refused'}
 result=[]
 for i in label['items']:
  atoms=i['gap_atoms']+i['uncertainty_atoms']
  if len(set(material_atoms(atoms)))!=len(atoms):raise ValueError('Duplicate semantic atom')
  q=sorted(render_atom(a) for a in i['gap_atoms']);u=sorted(render_atom(a) for a in i['uncertainty_atoms'])
  result.append(dict(span=i['span'],claims=sorted(i['claims']),questions=q,uncertainty=u,status='extracted' if i['claims'] or q or u else 'empty',refs=sorted(i['refs'])))
 return {'items':result}

def validate_label(label,packet):
 if set(label)!={'status','items','source_uncertainty_present','review_ambiguity'}:raise ValueError('Exact label schema required')
 if type(label['review_ambiguity']) is not bool or type(label['source_uncertainty_present']) is not bool:raise ValueError('Distinct boolean uncertainty fields required')
 wire=render(label)
 if label['status']=='refused':
  if label['source_uncertainty_present']:raise ValueError('Refusal cannot fabricate atoms')
  return wire
 if label['status']!='examined':raise ValueError('Unknown status')
 spans=packet['source_spans'];by={s['alias']:s for s in spans}
 if [i['span'] for i in label['items']]!=[s['alias'] for s in spans]:raise ValueError('Owned alias coverage/order')
 for i in label['items']:
  if set(i)!={'span','claims','refs','gap_atoms','uncertainty_atoms'}:raise ValueError('Exact item schema')
  text=by[i['span']]['text'];refs=re.findall(r'\bREF-\d{4,}\b',text)
  if set(i['refs'])!=set(refs):raise ValueError('All owned evidence required')
  if set(i['claims'])!=set(re.findall(r'\bCLM-[A-Za-z0-9-]+',text)):raise ValueError('All explicit claims including contradictions required')
  for kind,key in [('gap','gap_atoms'),('uncertainty','uncertainty_atoms')]:
   for a in i[key]:
    if a['kind']!=kind or a['span']!=i['span']:raise ValueError('Atom ownership/kind')
    evidence(a,text,refs)
 if label['source_uncertainty_present']!=any(i['uncertainty_atoms'] for i in label['items']):raise ValueError('Source uncertainty flag mismatch')
 owned=tuple(ex.Span(s['alias'],int(s['alias'][1:],16),int(s['alias'][1:],16)+len(s['text']),'',None,s['text']) for s in spans)
 cc.producer(wire,owned,'blind-packet')
 return wire

def material(label):
 return dict(status=label['status'],review_ambiguity=label['review_ambiguity'],source_uncertainty_present=label['source_uncertainty_present'],items=[dict(span=i['span'],claims=sorted(i['claims']),refs=sorted(i['refs']),gaps=material_atoms(i['gap_atoms']),uncertainty=material_atoms(i['uncertainty_atoms'])) for i in label['items']])

def eligible_metadata(row):return row['split'] in ('train','dev') and row['role']=='producer' and row['domain'] not in ('astronomy','ecology') and not row.get('provenance',{}).get('public_regression',False)

def isolated(folder,hashes):
 folder=Path(folder)
 for p in folder.rglob('*'):
  if p.is_symlink() or any(x in p.name.lower() for x in ('gold','target_answer','v2_answer','authored','comparison')):raise ValueError('Forbidden reviewer input')
 actual={p.name:digest(p.read_bytes()) for p in (folder/'packets').glob('*.json')}
 if actual!=hashes:raise ValueError('Packet population/hash mismatch')
