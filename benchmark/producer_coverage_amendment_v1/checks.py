"""Prospective generic fixtures: no benchmark targets or review packets."""
import unittest,tempfile
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
import semantics as s
import legacy_projection as lp
s.sys.path.insert(0,str(s.ROOT/'benchmark/machine_adjudication_v1'))
import r06

def fixture():
 text='CLM-X: Vessel capacity is 8 litres (REF-9901). CLM-Y: Vessel capacity is 9 litres (REF-9902). The reporting date is unavailable. The interpretation is unknown.'
 refs=['REF-9901','REF-9902'];g=s.atom('gap','reporting_date',refs=refs,support='The reporting date is unavailable.');u=s.atom('uncertainty','interpretation',refs=refs,support='The interpretation is unknown.')
 label=dict(status='examined',items=[dict(span='s0',claims=['CLM-X','CLM-Y'],refs=refs,gap_atoms=[g],uncertainty_atoms=[u])],source_uncertainty_present=True,review_ambiguity=False)
 return {'source_spans':[{'alias':'s0','text':text}]},label

class Checks(unittest.TestCase):
 def test_equivalence_and_generic_projection(self):
  p,l=fixture();ref=l['items'][0]['refs'];text=p['source_spans'][0]['text']
  vals=[lp.project(w,'gap','s0',ref,text) for w in ('What is the reporting date?','Reporting date was not provided.','Date of report is unavailable.')]
  self.assertTrue(all(s.normalize(v)==s.normalize(vals[0]) for v in vals))
  a=lp.project('Interpretation unknown','uncertainty','s0',ref,text);b=lp.project('The interpretation remains unresolved','uncertainty','s0',ref,text)
  self.assertEqual(s.normalize(a),s.normalize(b))
 def test_distinct_semantics(self):
  _,l=fixture();a=l['items'][0]['gap_atoms'][0]
  for k,v in [('kind','uncertainty'),('attribute','quantity'),('subject','entry:2'),('attribute','state'),('relation','after'),('unit','kg'),('refs',['REF-9902'])]:
   b=dict(a,**{k:v})
   if k=='kind':b['category']='unknown'
   self.assertNotEqual(s.normalize(a),s.normalize(b))
 def test_claim_conflict_not_epistemic(self):
  p,l=fixture();l['items'][0]['uncertainty_atoms']=[];l['source_uncertainty_present']=False
  self.assertEqual(s.validate_label(l,p)['items'][0]['claims'],['CLM-X','CLM-Y'])
  a=s.atom('uncertainty','interpretation',refs=l['items'][0]['refs'],support='CLM-X: Vessel capacity is 8 litres (REF-9901).')
  with self.assertRaises(ValueError):s.evidence(a,p['source_spans'][0]['text'],l['items'][0]['refs'])
  l['items'][0]['claims'].pop()
  with self.assertRaises(ValueError):s.validate_label(l,p)
 def test_renderer_equivalent_and_existing_contract(self):
  p,l=fixture();self.assertEqual(s.validate_label(l,p),s.render(l));b=deepcopy(l)
  b['items'][0]['gap_atoms'][0]['attribute']='date of report';b['items'][0]['gap_atoms'][0]['wording']='What date?'
  self.assertEqual(s.render(l),s.render(b))
  self.assertNotIn('draft_text',str(s.render(l)))
 def test_canonical_roundtrip(self):
  p,l=fixture()
  for a in l['items'][0]['gap_atoms']+l['items'][0]['uncertainty_atoms']:
   b=lp.project(s.render_atom(a),a['kind'],a['span'],a['refs'],p['source_spans'][0]['text']);self.assertEqual(s.normalize(a),s.normalize(b))
 def test_sequence_and_state_qualifiers(self):
  text='CLM-Z: A signal arrived (REF-9903). What entered first? The second entry interpretation is unknown.'
  a=lp.project('What entered first?','gap','s0',['REF-9903'],text);self.assertEqual(a['relation'],'first');self.assertEqual(a['category'],'explicit_question')
  b=lp.project('The second entry interpretation is unknown.','uncertainty','s0',['REF-9903'],text);self.assertEqual(b['subject'],'entry:2')
  c=lp.project('It is unclear whether the amendment was ratified.','uncertainty','s0',[],text);self.assertEqual(c['attribute'],'ratification_status')
 def test_empty_and_refusal(self):
  p={'source_spans':[{'alias':'s0','text':'Blank separator.'}]};l=dict(status='examined',items=[dict(span='s0',claims=[],refs=[],gap_atoms=[],uncertainty_atoms=[])],source_uncertainty_present=False,review_ambiguity=False)
  self.assertEqual(s.validate_label(l,p)['items'][0]['status'],'empty');l.update(status='refused',items=[]);self.assertEqual(s.validate_label(l,p),{'items':[],'status':'refused'})
 def test_unknown_qualifiers_fail_closed(self):
  for text in ('Date in kilograms is missing','Interpretation of another vessel is unknown','Quantity 25 unknown'):
   with self.assertRaises(ValueError):lp.project(text,'gap','s0',[],text)
 def test_evidence_ownership(self):
  p,l=fixture();l['items'][0]['refs']=['REF-9999']
  with self.assertRaises(ValueError):s.validate_label(l,p)
 def effect(self,obj,name,replacement,invariant):
  invariant()
  with patch.object(obj,name,replacement):
   with self.assertRaises(AssertionError):invariant()
  invariant()
 def test_effect_conflict_uncertainty(self):
  a=s.atom('uncertainty','interpretation',support='Claims conflict.')
  def inv():
   with self.assertRaises(ValueError):s.evidence(a,'Claims conflict.',[])
  self.effect(s,'evidence',lambda *args:None,inv)
 def test_effect_gap_equivalence(self):
  a=s.atom('gap','date of report');b=s.atom('gap','reporting_date')
  def inv():
   try:self.assertEqual(s.normalize(a),s.normalize(b))
   except ValueError:self.fail('Alias normalization disabled')
  self.effect(s,'ALIASES',{},inv)
 def test_effect_gap_difference(self):
  a=s.atom('gap','recording_date');b=s.atom('gap','quantity')
  def inv():self.assertNotEqual(s.material_atoms([a]),s.material_atoms([b]))
  self.effect(s,'material_atoms',lambda x:[],inv)
 def test_effect_evidence(self):
  a=s.atom('gap','recording_date',refs=['REF-9999'])
  def inv():
   with self.assertRaises(ValueError):s.evidence(a,a['support'],['REF-9901'])
  self.effect(s,'evidence',lambda *args:None,inv)
 def test_effect_rendering(self):
  _,l=fixture()
  def inv():self.assertTrue(s.render(l)['items'][0]['questions'])
  self.effect(s,'render',lambda x:{'items':[{'questions':[]}]},inv)
 def test_effect_evaluation_exclusion(self):
  r=dict(split='test',role='producer',domain='generic')
  def inv():self.assertFalse(s.eligible_metadata(r))
  self.effect(s,'eligible_metadata',lambda x:True,inv)
 def test_effect_isolation(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'packets').mkdir();(p/'gold.json').write_text('{}')
   def inv():
    with self.assertRaises(ValueError):s.isolated(p,{})
   self.effect(s,'isolated',lambda *args:None,inv)
 def test_effect_r06(self):
  rows=[dict(example_id=str(i),split='dev',document_family='f') for i in range(4)]+[dict(example_id='t'+str(i),split='train',document_family='t') for i in range(4)]
  scores=[dict(example_id=r['example_id'],accepted_outcome=r['split']=='dev') for r in rows]
  def inv():self.assertEqual(r06.family_metric(scores,rows,[r['example_id'] for r in rows])['measured'],1)
  self.effect(r06,'non_train',lambda r:True,inv)
if __name__=='__main__':unittest.main()
