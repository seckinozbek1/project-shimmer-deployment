"""Frozen source-context-aware legacy projection for post-freeze diagnostics."""
import json
import semantics as s

def project(wording,kind,span,refs,source):
 if wording.startswith(('Gap: ','Uncertainty: ')):
  head,raw=wording.split(': ',1);fields=json.loads(raw)
  a=s.make(kind,fields.pop('attribute'),source,span,refs,**fields);s.normalize(a);return a
 values=[a for a in s.interpretations(wording,source,span,refs) if a['kind']==kind]
 if len(values)!=1:raise ValueError('Legacy phrase has no unique finite semantic projection')
 return values[0]
