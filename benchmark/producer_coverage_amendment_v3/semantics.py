"""Finite source-span semantics and existing-wire renderer; no dataset access."""
from pathlib import Path
import re,json,hashlib,sys
from structural import semantic_segments
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import compact_contracts as cc
import bounded_extraction as ex
POLICY='producer-semantic-policy-v3';PROTOCOL='producer-coverage-amendment-v3';RENDERER='producer-target-renderer-v3'
FIELDS={'kind','category','subject','attribute','ordinal','relation','state','scope','unit','span','refs','support','origin'}
ATTRS={'recording_time','event_time','submission_time','authorization_time','observation_time','reporting_time','effective_time','date_unspecified','recorder','interpretation','ratification_status','entry_order','entry_content','entry_presence','recording_occurrence','submission_occurrence','event_occurrence'}
ALIASES={'recording_date':'recording_time','event_date':'event_time','submission_date':'submission_time','authorization_date':'authorization_time','observation_date':'observation_time','reporting_date':'reporting_time'}
ORDINALS={'first':1,'second':2,'third':3,'next':'next','following':'next','previous':'previous','prior':'previous','later':'later'}

def read(p):
 import access_guard
 if not access_guard._default().installed:raise PermissionError('Use the guarded V3 phase entry point')
 return json.loads(Path(p).read_text(encoding='utf8'))
def digest(v):return hashlib.sha256(v if isinstance(v,bytes) else json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
def make(kind,attribute,support,span='s0',refs=(),**kw):
 a=dict(kind=kind,category='missing_information' if kind=='gap' else 'unknown',subject='owned_record',attribute=attribute,ordinal=None,relation=None,state='unspecified' if kind=='gap' else 'unknown',scope='owned_record',unit=None,span=span,refs=list(refs),support=support,origin='source_explicit')
 a.update(kw);return a

def normalize(a):
 if set(a)-{'wording'}!=FIELDS:raise ValueError('Exact typed atom fields required')
 n={k:a[k] for k in FIELDS-{'support'}};n['attribute']=ALIASES.get(n['attribute'],n['attribute'])
 if n['origin']!='source_explicit':raise ValueError('Inferred origin prohibited')
 if n['attribute'] not in ATTRS:raise ValueError('Unsupported attribute')
 if n['kind'] not in ('gap','uncertainty'):raise ValueError('Unsupported atom kind')
 if n['category'] not in ({'missing_information','explicit_question','explicit_nonoccurrence'} if n['kind']=='gap' else {'unknown'}):raise ValueError('Unsupported category')
 if n['subject'] not in ('owned_record','entry','amendment','submission','event'):raise ValueError('Unsupported referent')
 if (n['ordinal'] is not None and type(n['ordinal']) not in (str,int)) or n['ordinal'] not in (None,1,2,3,'next','previous','later'):raise ValueError('Unsupported ordinal')
 if n['relation'] is not None:raise ValueError('Unsupported order relation')
 if n['state'] not in ('unspecified','requested','absent','not_recorded','not_submitted','did_not_occur','unknown'):raise ValueError('Unsupported state')
 if n['scope']!='owned_record' or n['unit'] is not None:raise ValueError('Unsupported scope/unit cannot be inferred')
 if not isinstance(n['span'],str) or not n['span'] or not isinstance(a['support'],str) or not a['support'].strip():raise ValueError('Owned source support required')
 if not isinstance(n['refs'],list) or any(not isinstance(r,str) or not re.fullmatch(r'REF-\d{4,}',r) for r in n['refs']) or len(set(n['refs']))!=len(n['refs']):raise ValueError('Invalid refs')
 n['refs']=sorted(n['refs']);return n

def ordinal(text):
 for word,value in ORDINALS.items():
  if re.search(r'\b'+word+r'\b',text):return value
 return None

def resolve_subject(text,context,attribute):
 """Resolve only named ordinal or single structural deictic referents."""
 low=text.lower();ordn=ordinal(low)
 if re.search(r'\b(?:this|that)\s+(?:entry|submission)\b',low):
  mentions=set(re.findall(r'\b(first|second|third)\s+(?:entry|submission)\b',context.lower()))
  named=set(re.findall(r'\b(?:entry|submission)\s+([a-z]|[0-9]+)\b',context.lower()))
  if len(named)>1 or len(mentions)+len(named)>1:raise ValueError('Ambiguous named deictic referents')
  if len(mentions)>1:raise ValueError('Ambiguous deictic entry')
  if len(mentions)==1:ordn=ORDINALS[next(iter(mentions))]
  elif re.search(r'\b(?:two|three|multiple|several|[2-9])\s+(?:entries|submissions)\b',context.lower()):raise ValueError('Ambiguous deictic plurality')
  elif not named and not re.search(r'\b(?:an?|one|single|the)\s+(?:entry|submission)\b',context.lower()):raise ValueError('No unique antecedent for deictic referent')
 if re.search(r'\bsubmission\b',low):return 'submission',ordn
 if ordn is not None or re.search(r'\bentry\b',low):return 'entry',ordn
 if 'amendment' in low or attribute in ('effective_time','ratification_status') and 'amendment' in context.lower():return 'amendment',None
 if re.search(r'\b(?:this|that)\s+submission\b',low):return 'submission',ordn
 # Bare this/it in a recording question denotes the single owned record,
 # not an arbitrarily selected assertion within it.
 return 'owned_record',None

def temporal(text,context=''):
 low=text.lower()
 roles=[('observation_time',r'observ(?:ation|ed|ing)'),('recording_time',r'record(?:ing|ed)'),('submission_time',r'submi(?:ssion|tted|t)'),('authorization_time',r'authori[sz](?:ation|ed)|approv(?:al|ed)'),('reporting_time',r'report(?:ing)?'),('event_time',r'event|happen(?:ed)?|occurr?(?:ed|ence)?'),('effective_time',r'effective|take effect')]
 found=[attr for attr,pattern in roles if re.search(r'\b(?:'+pattern+r')\b',low)]
 if len(found)==1:return found[0]
 if len(found)>1:raise ValueError('Multiple temporal roles in support; use complete specific clause')
 # An unqualified absent date inherits only a unique explicit temporal-role
 # question in the same owned record; never a date from another owner.
 pos=context.lower().find(low)
 if pos<0:return 'date_unspecified'
 following=context.lower()[pos+len(low):].lstrip()
 if not re.match(r'(?:when|what)\b',following):return 'date_unspecified'
 questions=re.findall(r'[^.!?\n]*\?',context.lower());context_roles=set()
 for q in questions:
  if re.search(r'\bwhen\b|\bdate\b|\btime\b',q):
   for attr,pattern in roles:
    if re.search(r'\b(?:'+pattern+r')\b',q):context_roles.add(attr)
 return next(iter(context_roles)) if len(context_roles)==1 else 'date_unspecified'

def interpretations(support,context=None,span='s0',refs=()):
 """Finite grammar over exact source clauses, not keyword whitelist equality."""
 context=support if context is None else context
 clauses=semantic_segments(support);answers=[]
 for raw in clauses:
  t=raw.strip().lower()
  if not t:continue
  # Do not erase negation of an epistemic cue or infer absence from unknown.
  epistemic=bool(re.search(r'\b(?:unknown|unclear|uncertain|unresolved|undetermined)\b|not known',t))
  if re.search(r'not\s+(?:unknown|unclear|uncertain|unresolved|absent|missing|unavailable|unspecified)|(?:false|incorrect|untrue)\s+that|not true that|no doubt|denied that',t):continue
  absent=bool(re.search(r'\bno\s+|\babsent\b|\bmissing\b|\bunavailable\b|\bunspecified\b|\bunnamed\b|not\s+(?:provided|supplied|recorded|submitted)|did not (?:occur|happen)|without',t))
  question='?' in t
  attr=None;category=None;state=None;kind=None
  if epistemic:
   kind='uncertainty';category='unknown';state='unknown'
   if re.search(r'\bdate\b|\btime\b|\bwhen\b',t):attr=temporal(t,context)
   elif 'interpretation' in t:attr='interpretation'
   elif re.search(r'ratifi',t):attr='ratification_status'
   elif re.search(r'submitt|submission',t):attr='submission_occurrence'
   elif re.search(r'record(?:ed|ing)',t) and 'whether' in t:attr='recording_occurrence'
   elif re.search(r'occurr|happen',t):attr='event_occurrence'
   elif 'entry' in t or 'claim' in t:attr='entry_presence'
   elif re.search(r'\bdate\b|\btime\b',t):attr=temporal(t,context)
  elif absent:
   kind='gap';category='missing_information';state='unspecified'
   if re.search(r'\bdate\b|\btime\b|\bperiod\b',t):attr=temporal(t,context)
   elif 'recorder' in t or 'who' in t:attr='recorder'
   elif re.search(r'ratifi',t):attr='ratification_status'
   elif re.search(r'not\s+recorded|no\s+.*recorded',t):attr='recording_occurrence';category='explicit_nonoccurrence';state='not_recorded'
   elif re.search(r'not\s+submitted|no\s+.*submitted',t):attr='submission_occurrence';category='explicit_nonoccurrence';state='not_submitted'
   elif re.search(r'no\s+.*(?:occurred|happened)|did not (?:occur|happen)',t):attr='event_occurrence';category='explicit_nonoccurrence';state='did_not_occur'
   elif re.search(r'\b(?:entry|claim|submission)\b',t):attr='entry_presence';category='explicit_nonoccurrence';state='absent'
  elif question:
   kind='gap';category='missing_information';state='unspecified'
   if re.search(r'\bwho\b.*record',t):attr='recorder'
   elif re.search(r'\bwhen\b|\bdate\b|\btime\b',t):attr=temporal(t,context)
   elif re.search(r'\bwhat\b.*(?:entered|contain|say|state)',t):attr='entry_content';category='explicit_question';state='requested'
   elif re.search(r'\bwhat\b.*(?:came|comes|followed|follows)|sequence position|which.*(?:first|next|previous|later)',t):attr='entry_order';category='explicit_question';state='requested'
  if attr is None:
   if epistemic or absent:raise ValueError('Content-bearing proposition outside frozen ontology; unresolved, not structural')
   continue
  subject,ordn=resolve_subject(t,context,attr)
  if attr=='entry_order':
   subject='entry';ordn=ordn or ('next' if re.search(r'follow',t) else None)
  if attr=='entry_content':subject='entry'
  if attr.endswith('_occurrence') and subject=='owned_record':subject='submission' if attr=='submission_occurrence' else 'event' if attr=='event_occurrence' else 'owned_record'
  a=make(kind,attr,support,span,refs,category=category,state=state,subject=subject,ordinal=ordn)
  answers.append(a)
 unique={json.dumps(normalize(a),sort_keys=True):a for a in answers}
 return list(unique.values())

def ground(a,text,refs):
 normalize(a)
 if a['support'] not in text:raise ValueError('Exact support not present in owned source')
 if set(a['refs'])!=set(refs):raise ValueError('All required owned refs must match')
 candidates=interpretations(a['support'],text,a['span'],refs)
 if normalize(a) not in [normalize(v) for v in candidates]:raise ValueError('Typed interpretation not supported by finite source grammar')
 # A cropped fragment cannot reverse the complete clause's negation/modality.
 for match in re.finditer(re.escape(a['support']),text):
  left=max(text.rfind(x,0,match.start()) for x in '.!?;\n')+1
  ends=[pos for x in '.!?;\n' if (pos:=text.find(x,match.end()))>=0]
  right=min(ends)+1 if ends else len(text)
  clause=text[left:right]
  full=interpretations(clause,text,a['span'],refs)
  if normalize(a) in [normalize(v) for v in full]:return True
 raise ValueError('Support omits material clause context')

def canonical_atom(a):
 n=normalize(a)
 return ('Gap' if a['kind']=='gap' else 'Uncertainty')+': '+json.dumps({k:n[k] for k in ('category','subject','attribute','ordinal','relation','state','scope','unit')},sort_keys=True,separators=(',',':'))
def material_atoms(values):return sorted(json.dumps(normalize(a),sort_keys=True) for a in values)
def render(label):
 if label['status']=='refused':
  if label['items']:raise ValueError('Refusal has no items')
  return {'items':[],'status':'refused'}
 items=[]
 for i in label['items']:
  atoms=i['gap_atoms']+i['uncertainty_atoms']
  if len(set(material_atoms(atoms)))!=len(atoms):raise ValueError('Duplicate semantic atom')
  q=sorted(canonical_atom(a) for a in i['gap_atoms']);u=sorted(canonical_atom(a) for a in i['uncertainty_atoms'])
  items.append(dict(span=i['span'],claims=sorted(i['claims']),questions=q,uncertainty=u,status='extracted' if i['claims'] or q or u else 'empty',refs=sorted(i['refs'])))
 return {'items':items}
def validate_label(label,packet):
 if set(label)!={'status','items','source_uncertainty_present','review_ambiguity'}:raise ValueError('Exact label schema')
 if type(label['source_uncertainty_present']) is not bool or type(label['review_ambiguity']) is not bool:raise ValueError('Distinct booleans required')
 wire=render(label)
 if label['status']=='refused':
  if label['source_uncertainty_present']:raise ValueError('Refusal has no fabricated atoms')
  return wire
 if label['status']!='examined':raise ValueError('Unknown status')
 spans=packet['source_spans'];by={v['alias']:v['text'] for v in spans}
 owned_refs=set(re.findall(r'\bREF-\d{4,}\b',' '.join(by.values())))
 if not owned_refs<=set(packet.get('supplied_refs',owned_refs)) or not set(packet.get('required_refs',[]))<=owned_refs:raise ValueError('Packet evidence boundary mismatch')
 if [i['span'] for i in label['items']]!=list(by):raise ValueError('Exact ownership/order required')
 for i in label['items']:
  if set(i)!={'span','claims','refs','gap_atoms','uncertainty_atoms'}:raise ValueError('Exact item fields')
  text=by[i['span']];refs=sorted(set(re.findall(r'\bREF-\d{4,}\b',text)))
  if sorted(i['refs'])!=refs:raise ValueError('All owned refs required')
  if sorted(i['claims'])!=sorted(set(re.findall(r'\bCLM-[A-Za-z0-9-]+',text))):raise ValueError('Every explicit claim including conflicts required')
  for kind,key in [('gap','gap_atoms'),('uncertainty','uncertainty_atoms')]:
   for a in i[key]:
    if a['kind']!=kind or a['span']!=i['span']:raise ValueError('Atom ownership/kind mismatch')
    ground(a,text,refs)
   expected=interpretations(text,text,i['span'],refs)
  if set(material_atoms(expected))!=set(material_atoms(i['gap_atoms']+i['uncertainty_atoms'])):raise ValueError('Finite supported semantic coverage incomplete')
 if label['source_uncertainty_present']!=any(i['uncertainty_atoms'] for i in label['items']):raise ValueError('Source uncertainty flag mismatch')
 owned=tuple(ex.Span(v['alias'],int(v['alias'][1:],16),int(v['alias'][1:],16)+len(v['text']),'',None,v['text']) for v in spans)
 cc.producer(wire,owned,'curation-only')
 return wire

def material(label):return dict(status=label['status'],review_ambiguity=label['review_ambiguity'],source_uncertainty_present=label['source_uncertainty_present'],items=[dict(span=i['span'],claims=sorted(i['claims']),refs=sorted(i['refs']),gaps=material_atoms(i['gap_atoms']),uncertainty=material_atoms(i['uncertainty_atoms'])) for i in label['items']])
def eligible_metadata(r):return r['role']=='producer' and r['split'] in ('train','dev') and r['domain'] not in ('astronomy','ecology') and r['features']['substantive']
def isolated(folder,hashes):
 for p in Path(folder).rglob('*'):
  if p.is_symlink() or any(x in p.name.lower() for x in ('gold','authored','comparison','prior_answer')):raise ValueError('Forbidden reviewer input')
 if {p.name:digest(p.read_bytes()) for p in (Path(folder)/'packets').glob('*.json')}!=hashes:raise ValueError('Packet/hash population mismatch')
