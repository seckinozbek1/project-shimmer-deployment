"""Generic pre-review grammar/renderer fixtures, unrelated to target packets."""
import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from copy import deepcopy
import semantics as s
s.sys.path.insert(0,str(s.ROOT/'benchmark/machine_adjudication_v1'));import r06

def one(text,**expected):
 values=s.interpretations(text)
 if len(values)!=1:raise AssertionError((text,'not uniquely interpreted',values))
 a=values[0]
 for k,v in expected.items():
  if a[k]!=v:raise AssertionError((k,a[k],v))
 s.ground(a,text,[]);return a

class Checks(unittest.TestCase):
 def test_generic_absence_forms(self):
  for text,attr,state in [('No second submission was recorded.','recording_occurrence','not_recorded'),('The third entry was not submitted.','submission_occurrence','not_submitted'),('No later entry appears.','entry_presence','absent'),('The first entry is absent.','entry_presence','absent'),('The event date remains unspecified.','event_time','unspecified'),('The observation date was not provided.','observation_time','unspecified')]:
   one(text,attribute=attr,state=state)
 def test_nonoccurrence_not_missing_information_or_unknown(self):
  a=one('No inspection occurred.',category='explicit_nonoccurrence',attribute='event_occurrence',state='did_not_occur')
  b=one('It is unknown whether an inspection occurred.',category='unknown',attribute='event_occurrence')
  c=one('The event date is missing.',category='missing_information',attribute='event_time')
  self.assertNotEqual(s.normalize(a),s.normalize(b));self.assertNotEqual(s.normalize(a),s.normalize(c))
 def test_temporal_roles_positive_and_distinct(self):
  values=[]
  for role,attribute in [('recording','recording_time'),('event','event_time'),('submission','submission_time'),('authorization','authorization_time'),('observation','observation_time'),('reporting','reporting_time')]:
   values.append(one('The '+role+' date is unavailable.',attribute=attribute))
  self.assertEqual(len({s.digest(s.normalize(v)) for v in values}),6)
  a=one('When was this recorded?',attribute='recording_time');self.assertEqual(a['subject'],'owned_record')
  self.assertEqual(s.interpretations('The date is absent.')[0]['attribute'],'date_unspecified')
 def test_order_content(self):
  one('What came next?',attribute='entry_order',ordinal='next',category='explicit_question')
  one('What did the second entry contain?',attribute='entry_content',ordinal=2)
  one('What was entered first?',attribute='entry_content',ordinal=1)
  one('What followed?',attribute='entry_order',ordinal='next')
  for x,y in [('What came first?','What came next?'),('Which entry was previous?','Which entry was later?')]:
   self.assertNotEqual(s.normalize(one(x)),s.normalize(one(y)))
 def test_unambiguous_and_ambiguous_deictics(self):
  text='The second entry exists. What did this entry contain?'
  values=s.interpretations('What did this entry contain?',text);self.assertEqual(values[0]['ordinal'],2);s.ground(values[0],text,[])
  with self.assertRaises(ValueError):s.interpretations('What did that entry contain?','The first entry and second entry exist. What did that entry contain?')
  with self.assertRaises(ValueError):s.interpretations('What did this entry contain?','Two entries exist. What did this entry contain?')
 def test_no_unsupported_gaps_or_uncertainty(self):
  for text in ('CLM-Q: Signal was high. CLM-R: Signal was low. These assertions conflict.','The event happened yesterday.','The recording date is known.','It is not unknown whether an event occurred.'):
   self.assertFalse(s.interpretations(text))
 def test_absence_unknown_second_distinct(self):
  a=one('No second entry appears.');b=one('The second entry is unknown.')
  self.assertEqual(a['ordinal'],2);self.assertEqual(b['ordinal'],2);self.assertNotEqual(s.normalize(a),s.normalize(b))
 def test_missing_vs_unknown_time(self):
  self.assertNotEqual(s.normalize(one('The event date is missing.')),s.normalize(one('The event date is unknown.')))
 def test_exact_support_refs_and_owner(self):
  text='The event date is unavailable.';a=one(text)
  with self.assertRaises(ValueError):s.ground(a,'The recording date is unavailable.',[])
  with self.assertRaises(ValueError):s.ground(dict(a,refs=['REF-9911']),text,['REF-9912'])
  with self.assertRaises(ValueError):s.ground(dict(a,attribute='recording_time'),text,[])
  with self.assertRaises(ValueError):s.ground(dict(a,subject='submission'),text,[])
 def test_cropped_negation_does_not_reverse(self):
  with self.assertRaises(ValueError):s.ground(s.make('uncertainty','event_occurrence','unknown whether the event occurred.',subject='event'),'It is not unknown whether the event occurred.',[])
 def test_canonical_determinism_distinction_and_contract(self):
  text='CLM-Q: A tank holds 7 litres (REF-9911). CLM-R: The same tank holds 8 litres (REF-9912). The event date is absent.'
  refs=['REF-9911','REF-9912'];a=s.interpretations('The event date is absent.',text,refs=refs)[0]
  label=dict(status='examined',items=[dict(span='s0',claims=['CLM-R','CLM-Q'],refs=list(reversed(refs)),gap_atoms=[a],uncertainty_atoms=[])],source_uncertainty_present=False,review_ambiguity=False)
  wire=s.validate_label(label,{'source_spans':[dict(alias='s0',text=text)]});b=deepcopy(label);b['items'][0]['gap_atoms'][0]['attribute']='event_date';b['items'][0]['gap_atoms'][0]['wording']='Which day?'
  self.assertEqual(s.digest(wire),s.digest(s.render(b)))
  b['items'][0]['gap_atoms'][0]['attribute']='recording_time';self.assertNotEqual(s.render(label),s.render(b))
  b=deepcopy(label);b['items'][0]['claims'].pop()
  with self.assertRaises(ValueError):s.validate_label(b,{'source_spans':[dict(alias='s0',text=text)]})
 def test_context_temporal_resolution(self):
  text='The date is absent. When was this recorded?'
  self.assertEqual(s.interpretations('The date is absent.',text)[0]['attribute'],'recording_time')
  text+=' When did the event happen?'
  self.assertEqual(s.interpretations('The date is absent.',text)[0]['attribute'],'date_unspecified')
 def test_negation_scope_and_embedding(self):
  for text in ('The entry is not absent.','No doubt the event occurred.','It is false that it is unknown whether the event occurred.'):
   self.assertFalse(s.interpretations(text))
  one('The event did not occur.',attribute='event_occurrence',state='did_not_occur')
 def test_temporal_uncertainty_and_ordinal_submission(self):
  one('The submission date is unknown.',attribute='submission_time',category='unknown')
  one('It is unknown when this was recorded.',attribute='recording_time',category='unknown')
  one('When was the second submission submitted?',attribute='submission_time',subject='submission',ordinal=2)
 def test_named_deictic_and_unrelated_context(self):
  with self.assertRaises(ValueError):s.interpretations('What did this entry contain?','Entry A and entry B exist. What did this entry contain?')
  with self.assertRaises(ValueError):s.interpretations('What did that entry contain?')
  text='The date is absent. An unrelated entry asks: When was this recorded?'
  self.assertEqual(s.interpretations('The date is absent.',text)[0]['attribute'],'date_unspecified')
 def test_schema_types_and_missing_atoms(self):
  a=one('What was entered first?')
  with self.assertRaises(ValueError):s.normalize(dict(a,ordinal=1.0))
  with self.assertRaises(ValueError):s.normalize(dict(a,refs=[{}]))
  with self.assertRaises(ValueError):s.normalize(dict(a,relation='before'))
  text='CLM-Q: Valve is open (REF-9911). The event date is unknown.'
  label=dict(status='examined',items=[dict(span='s0',claims=['CLM-Q'],refs=['REF-9911'],gap_atoms=[],uncertainty_atoms=[])],source_uncertainty_present=False,review_ambiguity=False)
  with self.assertRaises(ValueError):s.validate_label(label,{'source_spans':[dict(alias='s0',text=text)]})
 def test_prospective_legacy_projection(self):
  import legacy_projection as lp
  source='The recording date is absent. When was this recorded?'
  a=lp.project('When was this recorded?','gap','s0',[],source)
  b=lp.project('The recording date is unavailable.','gap','s0',[],source)
  self.assertEqual(s.normalize(a),s.normalize(b))
  self.assertEqual(s.normalize(a),s.normalize(lp.project(s.canonical_atom(a),'gap','s0',[],source)))
  with self.assertRaises(ValueError):lp.project('Perhaps the moon means something','gap','s0',[],source)
 def effect(self,obj,name,value,invariant):
  invariant()
  with patch.object(obj,name,value):
   with self.assertRaises(AssertionError):invariant()
  invariant()
 def test_effect_absence_support(self):
  def inv():self.assertTrue(s.interpretations('No third submission was recorded.'))
  self.effect(s,'interpretations',lambda *a,**k:[],inv)
 def test_effect_absence_unknown(self):
  a=one('No second entry appears.');b=one('The second entry is unknown.')
  def inv():self.assertNotEqual(s.material_atoms([a]),s.material_atoms([b]))
  self.effect(s,'material_atoms',lambda x:[],inv)
 def test_effect_deictic_resolution(self):
  def inv():
   with self.assertRaises(ValueError):s.resolve_subject('that entry','First entry. Second entry.','entry_content')
  self.effect(s,'resolve_subject',lambda *a:('entry',1),inv)
 def test_effect_recording_event(self):
  def inv():self.assertNotEqual(s.temporal('recording date'),s.temporal('event date'))
  self.effect(s,'temporal',lambda *a:'date_unspecified',inv)
 def test_effect_order_content(self):
  a=one('What came next?');b=one('What did the second entry contain?')
  def inv():self.assertNotEqual(s.canonical_atom(a),s.canonical_atom(b))
  self.effect(s,'canonical_atom',lambda a:'gap',inv)
 def test_effect_exact_support(self):
  a=one('The event date is missing.')
  def inv():
   with self.assertRaises(ValueError):s.ground(a,'Different source.',[])
  self.effect(s,'ground',lambda *a:True,inv)
 def test_effect_evaluation_exclusion(self):
  row=dict(role='producer',split='test',domain='generic',features=dict(substantive=True))
  def inv():self.assertFalse(s.eligible_metadata(row))
  self.effect(s,'eligible_metadata',lambda r:True,inv)
 def test_effect_isolation(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'packets').mkdir();(p/'authored.json').write_text('{}')
   def inv():
    with self.assertRaises(ValueError):s.isolated(p,{})
   self.effect(s,'isolated',lambda *a:None,inv)
 def test_effect_r06_train_exclusion(self):
  rows=[dict(example_id=str(i),split='dev',document_family='f') for i in range(4)]+[dict(example_id='t'+str(i),split='train',document_family='t') for i in range(4)]
  scores=[dict(example_id=r['example_id'],accepted_outcome=r['split']=='dev') for r in rows]
  def inv():self.assertEqual(r06.family_metric(scores,rows,[r['example_id'] for r in rows])['measured'],1)
  self.effect(r06,'non_train',lambda r:True,inv)
if __name__=='__main__':unittest.main()
