"""CPU tensors and a fake backbone only. No model load, text data or CUDA work."""
from contextlib import nullcontext
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch
import final_models


class ClassifierCPUChecks(unittest.TestCase):
    def classifier(self, tensor):
        obj=object.__new__(final_models.Classifier)
        obj.torch=torch;obj.failed=False;obj.device='cpu';obj._shimmer_identity={'fixture':True}
        obj.mean=torch.zeros(3072);obj.std=torch.ones(3072)
        obj.head=torch.nn.Linear(3072,4)
        with torch.no_grad():
            obj.head.weight.zero_();obj.head.bias.copy_(torch.tensor([0.,1.,2.,3.]))
        backbone=SimpleNamespace(model=lambda **kwargs:SimpleNamespace(last_hidden_state=tensor))
        obj.model=SimpleNamespace(get_base_model=lambda:backbone)
        obj.audit=SimpleNamespace(unchanged=lambda:True)
        return obj

    def test_final_prompt_token_and_class_order(self):
        obj=self.classifier(torch.ones(1,2,3072))
        with patch.object(torch,'autocast',side_effect=lambda *a,**k:nullcontext()):
            self.assertEqual(obj.predict([1,2]),'ADDITION')

    def test_shape_nonfinite_normalization_and_sticky_stop(self):
        fixtures=[torch.ones(1,2,3071),torch.full((1,2,3072),float('nan')),torch.ones(1,2,3072)]
        for index,tensor in enumerate(fixtures):
            obj=self.classifier(tensor)
            if index==2:obj.std.zero_()
            with tempfile.TemporaryDirectory() as folder,patch.object(torch,'autocast',side_effect=lambda *a,**k:nullcontext()):
                with self.assertRaises(RuntimeError):obj.predict([1,2],folder)
                receipt=json.loads((Path(folder)/'admission_failure.json').read_text())
                self.assertTrue(receipt['failed']);self.assertTrue(obj.failed)
                with self.assertRaisesRegex(RuntimeError,'No inference retry'):obj.predict([1,2])

    def test_state_mutation_refuses_before_forward(self):
        obj=self.classifier(torch.ones(1,2,3072));obj.audit.unchanged=lambda:False
        with self.assertRaisesRegex(RuntimeError,'Frozen state mutated'):obj.predict([1,2])


if __name__=='__main__':unittest.main()
