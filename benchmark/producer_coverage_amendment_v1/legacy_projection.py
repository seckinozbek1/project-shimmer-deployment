"""Prospective diagnostic projection; not a reviewer or source label generator."""
import re
import semantics as s
WORDS=set('the a an is are was were be been it its of for in on to from by and or not no provided supplied unavailable missing absent remains remain unknown uncertain unresolved unclear whether what when who does do did take effect effective time period date reporting report recording recorded observation recorder unnamed interpretation entry first second third next followed entered before after ratified ratification status amendment statements source conflict conflicting'.split())
def project(wording,kind,span,refs,source):
 if wording.startswith(('Missing information: ','Explicit question: ','Explicit unknown: ')):
  head,body=wording.split(': ',1);values=body.rstrip('.').split('; ')
  if len(values)!=5:raise ValueError('Malformed canonical target')
  subject,attribute,relation,scope,unit=values
  a=s.atom(kind,attribute,span,refs,source);a.update(subject=subject,relation=None if relation=='none' else relation,scope=scope,unit=None if unit=='none' else unit,category={'Missing information':'missing_information','Explicit question':'explicit_question','Explicit unknown':'unknown'}[head]);s.normalize(a);return a
 t=wording.lower();tokens=set(re.findall(r'[a-z]+',t))
 if tokens-WORDS or re.search(r'\d',t):raise ValueError('Unsupported legacy qualifier/vocabulary')
 subject='owned_record'
 if 'amendment' in tokens:subject='amendment'
 for word,number in [('first',1),('second',2),('third',3)]:
  if re.search(word+r'\s+entry',t):subject='entry:'+str(number)
 relation=None
 if 'interpretation' in tokens:attribute='interpretation'
 elif tokens & {'ratified','ratification'}:attribute='ratification_status'
 elif 'who' in tokens or 'recorder' in tokens:attribute='recorder'
 elif tokens & {'effective','effect','period'}:attribute='effective_time'
 elif 'date' in tokens:
  attribute='reporting_date' if tokens & {'report','reporting'} else 'observation_date' if 'observation' in tokens else 'recording_date'
 elif tokens & {'entered','followed'}:
  attribute='entry_content';relation='first' if 'first' in tokens else 'next' if 'followed' in tokens or 'next' in tokens else None
  if relation is None:raise ValueError('Unresolved sequence relation')
 else:raise ValueError('No uniquely supported legacy attribute')
 a=s.atom(kind,attribute,span,refs,source);a.update(subject=subject,relation=relation)
 if kind=='gap' and attribute=='entry_content':a['category']='explicit_question' if re.search(r'CLM-',source) else 'missing_information'
 if kind=='uncertainty' and not tokens & {'unknown','uncertain','unclear','unresolved'}:raise ValueError('No explicit legacy epistemic cue')
 s.normalize(a);return a
