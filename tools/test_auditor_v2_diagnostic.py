"""Local contract tests; synthetic arrays only, no model or training."""
import io
import json
import unittest
from unittest.mock import patch

import auditor_v2_diagnostic as d


class DiagnosticTests(unittest.TestCase):
    def test_excluded_record_never_deserialized(self):
        excluded = b'{"example_id":"' + b'a'*64 + b'", UNPARSEABLE_EXCLUDED_PAYLOAD}\n'
        selected = dict(example_id='b'*64, split='dev', relation='MATCH')
        line = json.dumps(selected, separators=(',', ':')).encode()+b'\n'
        original = json.loads
        with patch.object(d.json, 'loads', wraps=original) as decoder:
            self.assertEqual(d.select_dev(io.BytesIO(excluded+line), ['b'*64]), [selected])
            self.assertEqual(decoder.call_count, 1)

    def test_missing_and_duplicate_dev_fail(self):
        row = b'{"example_id":"'+b'b'*64+b'","split":"dev"}\n'
        for data in [b'', row+row]:
            with self.assertRaises(AssertionError):
                d.select_dev(io.BytesIO(data), ['b'*64])

    def test_fourway_macro_and_refusal_errors(self):
        result = d.metrics(d.CLASSES, ['MATCH', 'DIVERGENCE', 'OMISSION', 'INSUFFICIENT_EVIDENCE'])
        self.assertEqual(result['macro_f1'], .75)
        self.assertEqual(result['accuracy'], .75)

    def test_coprimary_decisions(self):
        records = [dict(example_id=group+str(i), split=group, relation=c)
                   for group in ['external_dev', 'historical_dev'] for i, c in enumerate(d.CLASSES)]
        correct = {r['example_id']: r['relation'] for r in records}
        challenges = {name: dict(example_ids=['external_dev'+str(i) for i in indices],
                                 classes=[d.CLASSES[i] for i in indices])
                      for name, indices in [('shorter', [0,1,2]), ('longer', [0,1,3])]}
        self.assertTrue(d.evaluate(records, correct, challenges)['success'])
        for ext, hist, conclusion in [(False, True, 'SOURCE_FAMILY_OR_DISTRIBUTION_OVERFIT'),
                                      (True, True, 'RELATION_REPRESENTATION_STILL_INSUFFICIENT'),
                                      (True, False, 'INCONCLUSIVE_MIXED_GATES')]:
            pred = dict(correct)
            for group, fail in [('external_dev', ext), ('historical_dev', hist)]:
                if fail:
                    pred.update({group+str(i): d.CLASSES[(i+1)%4] for i in range(4)})
            result = d.evaluate(records, pred, challenges)
            self.assertFalse(result['success'])
            self.assertEqual(result['conclusion'], conclusion)

    def test_train_only_normalization(self):
        import numpy as np
        values = np.zeros((2040,3072), dtype=np.float32)
        values[1792:] = 123
        mean, std, result = d.standardized(np, values)
        self.assertTrue((mean == 0).all())
        self.assertTrue((std == np.float32(1e-6)).all())
        self.assertTrue((result[:1792] == 0).all())

    def test_prepared_bindings_and_scope(self):
        records = d.read(d.OUT/'records.json')
        spec = d.read(d.OUT/'experiment.json')
        original = d.read(d.V2/'experiment.json')
        self.assertEqual(spec['head'], original['head'])
        self.assertEqual(spec['standardization'], original['standardization'])
        self.assertFalse(spec['execution_authorized'])
        self.assertFalse(spec['cloud_launch_authorized'])
        self.assertEqual([r['split'] for r in records], ['train']*1792+['external_dev']*200+['historical_dev']*48)
        for row in records:
            self.assertEqual(set(row), {'example_id','split','relation','input_ids','prompt_sha256'})
        for name, digest in d.read(d.OUT/'bindings.json').items():
            if name != 'external_dev_selected_content_sha256':
                self.assertEqual(d.sha(d.ROOT/name), digest)
        self.assertFalse(d.read(d.V2/'holdout_receipt.json')['consumed'])


if __name__ == '__main__':
    unittest.main()
