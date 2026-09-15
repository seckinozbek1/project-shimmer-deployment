"""Generic projection checks before any V2 gold comparison; no benchmark targets."""
import unittest
import projection as p
import atoms as a


class ProjectionChecks(unittest.TestCase):
    def test_recorder_is_not_recording_date(self):
        text='The date is absent. When was this recorded? The recorder is unnamed. Who recorded it?'
        self.assertEqual(p.project('Who recorded it?',text,'s0',[],'gap')['target'],'recorder')
        self.assertEqual(p.project('When was this recorded?',text,'s0',[],'gap')['target'],'recording_date')

    def test_unknown_referent_and_unit_not_discarded(self):
        for wording in ('Date of another record is missing','Date in kilograms is missing','Quantity is missing','Uncertain date','Conflicting date'):
            with self.assertRaises(ValueError):p.project(wording,'The date is absent.','s0',[],'gap')

    def test_supported_synonyms(self):
        text='The reporting date is unavailable.'
        values=[p.project(w,text,'s0',[],'gap') for w in ('What is the reporting date?','Date of report is not provided.')]
        self.assertEqual(a.material(values[:1]),a.material(values[1:]))

    def test_no_extra_uncertainty(self):
        with self.assertRaises(ValueError):p.project('interpretation uncertain','The date is absent.','s0',[],'uncertainty')
        with self.assertRaises(ValueError):p.project('no uncertainty','The interpretation remains uncertain.','s0',[],'uncertainty')


if __name__=='__main__':unittest.main()
