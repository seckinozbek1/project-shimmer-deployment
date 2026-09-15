"""Prospective generic heading tests; no project data reads."""
import unittest
from unittest.mock import patch
import semantics as s
import structural as st

class HeadingChecks(unittest.TestCase):
 def test_structural_positions(self):
  for text in ('Pending matters\nA container holds water.', 'Unknowns', '| Status | Owner |', 'Open questions\nA memo contains a note.'):
   self.assertEqual(s.interpretations(text), [])
  text='Pending matters: The event date is unavailable.'
  self.assertEqual(s.interpretations(text)[0]['kind'],'gap')
 def test_content_retained(self):
  for text in ('The status is unknown.','No further submission was recorded.','The event date remains unavailable.','Three matters remain unresolved.','The quantity remains provisional.'):
   self.assertEqual(st.semantic_segments(text),[text])
  self.assertEqual(s.interpretations('No further submission was recorded.')[0]['state'],'not_recorded')
  self.assertEqual(s.interpretations('The event date remains unavailable.')[0]['attribute'],'event_time')
  for text in ('The status is unknown.','Three matters remain unresolved.'):
   with self.assertRaisesRegex(ValueError,'outside frozen ontology'):s.interpretations(text)
 def test_content_even_in_heading_position(self):
  text='The event date is unknown.: A box exists.'
  self.assertEqual(s.interpretations(text)[0]['kind'],'uncertainty')
 def test_no_invented_neighbor(self):
  self.assertEqual(s.interpretations('Unknowns: The event date is known.'),[])
  self.assertEqual(s.interpretations('Pending issues: The event date is absent.')[0]['kind'],'gap')
 def test_negation_modality_retained(self):
  for text in ('The event date is not unknown.','The quantity may remain provisional.','No issues remain unresolved.'):
   self.assertEqual(st.semantic_segments(text),[text])
  self.assertFalse(s.interpretations('The event date is not unknown.'))
 def test_offsets(self):
  text='  Pending matters: The event date is absent.\n|Status| The entry is unknown. |'
  for seg in st.segments(text):self.assertEqual(text[seg['start']:seg['end']],seg['text'])
 def test_effect_heading_lexical_false_positive(self):
  def inv():self.assertEqual(s.interpretations('Uncertain items: The event date is absent.')[0]['kind'],'gap')
  inv()
  with patch.object(s,'semantic_segments',lambda text:[text]):
   with self.assertRaises(AssertionError):inv()
  inv()
 def test_effect_content_proposition(self):
  def inv():self.assertEqual(len(s.interpretations('The event date is unknown.')),1)
  inv()
  with patch.object(s,'semantic_segments',lambda text:[]):
   with self.assertRaises(AssertionError):inv()
  inv()
