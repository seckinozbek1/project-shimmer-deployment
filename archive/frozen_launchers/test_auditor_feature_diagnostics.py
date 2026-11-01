"""Exercise the live extraction guard with real torch tensors, without model weights."""
import ast
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import torch
import auditor_feature_diagnostics as d


class Fixture(torch.nn.Module):
    def __init__(self, hidden):
        super().__init__()
        self.hidden = hidden
        self.dropout = torch.nn.Dropout(.05)
        self.active_adapters = ['historical_reference']
        self.peft_config = {'historical_reference': SimpleNamespace(r=8, lora_alpha=16,
            lora_dropout=.05, inference_mode=True)}
        self.config = SimpleNamespace(_attn_implementation='eager')
        self.calls = []
        self.eval()

    def get_base_model(self):
        return SimpleNamespace(model=self)

    def forward(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(last_hidden_state=self.hidden)


class FeatureGuard(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'failure.json'
        self.row = dict(split='train', example_id='row32', input_ids=[11, 12], prompt_sha256='fixture')

    def run_guard(self, value):
        self.model = Fixture(value)
        return d.extract_train_vector(torch, np, self.model, self.row, 31, 'cpu', self.path)

    def test_valid_original_pooling_and_forward_arguments(self):
        raw = torch.arange(6144, dtype=torch.float32).reshape(1, 2, 3072)
        value = self.run_guard(raw)
        np.testing.assert_array_equal(value, raw[0, -1].numpy())
        self.assertFalse(self.path.exists())
        call = self.model.calls[0]
        self.assertEqual(call['input_ids'].tolist(), [[11, 12]])
        self.assertEqual(call['attention_mask'].tolist(), [[1, 1]])
        self.assertFalse(call['use_cache']); self.assertTrue(call['return_dict'])

    def test_nonfinite_evidence_is_durable_before_raise(self):
        raw = torch.ones((1, 2, 3072), dtype=torch.bfloat16)
        raw[0, -1, 2] = float('nan'); raw[0, -1, 4] = float('inf'); raw[0, -1, 6] = -float('inf')
        with self.assertRaisesRegex(RuntimeError, 'finite TRAIN hidden'):
            self.run_guard(raw)
        receipt = json.loads(self.path.read_text())
        self.assertEqual(receipt['row_one_based'], 32)
        self.assertEqual(receipt['raw_hidden']['shape'], [1, 2, 3072])
        vector = receipt['vector']
        self.assertEqual(vector['shape'], [3072]); self.assertEqual(vector['finite_count'], 3069)
        for name, index in [('nan', 2), ('positive_inf', 4), ('negative_inf', 6)]:
            self.assertEqual(vector[name]['indices'], [index]); self.assertEqual(vector[name]['count'], 1)
        self.assertEqual(vector['finite_statistics']['mean'], 1.)
        self.assertFalse(receipt['model']['training'])
        self.assertEqual(receipt['model']['dropout'][0]['p'], .05)
        self.assertTrue(receipt['forward_autocast']['enabled'])
        self.assertEqual(receipt['extracted_hidden']['dtype'], 'torch.bfloat16')
        self.assertEqual(receipt['vector']['dtype'], 'torch.float32')
        self.assertEqual(receipt['token_sha256'], d.digest([11, 12]))
        self.assertEqual(len(receipt['extraction_path']['sha256']), 64)

    def test_wrong_raw_shape_preserved_without_resize(self):
        for shape in [(1, 2, 3071), (1, 0, 3072), (3072,)]:
            with self.assertRaisesRegex(RuntimeError, 'raw_hidden_shape'):
                self.run_guard(torch.ones(shape))
            receipt = json.loads(self.path.read_text())
            self.assertEqual(receipt['raw_hidden']['shape'], list(shape))
            self.assertIsNone(receipt['vector'])

    def test_all_nonfinite_bounded_indices_and_strict_json(self):
        with self.assertRaises(RuntimeError):
            self.run_guard(torch.full((1, 2, 3072), float('nan')))
        receipt = json.loads(self.path.read_text())
        self.assertIsNone(receipt['vector']['finite_statistics'])
        self.assertEqual(receipt['vector']['nan']['count'], 3072)
        self.assertEqual(len(receipt['vector']['nan']['indices']), 16)
        self.assertTrue(receipt['vector']['nan']['truncated'])

    def test_diagnostic_write_failure_cannot_admit_row(self):
        with patch.object(d, 'write_diagnostic', side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError):
                self.run_guard(torch.full((1, 2, 3072), float('inf')))

    def test_non_train_denied_before_forward(self):
        self.row['split'] = 'external_dev'
        with self.assertRaisesRegex(RuntimeError, 'TRAIN-only'):
            self.run_guard(torch.ones((1, 2, 3072)))
        self.assertFalse(self.model.calls)

    def test_live_loop_calls_shared_guard_before_cache_write(self):
        path = Path(__file__).with_name('auditor_final_remote.py')
        tree = ast.parse(path.read_text())
        training = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'training')
        calls = [n for n in ast.walk(training) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == 'extract_train_vector']
        self.assertEqual(len(calls), 1)
        writes = [n for n in ast.walk(training) if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id == 'features' for t in n.targets)]
        self.assertEqual(len(writes), 1)
        self.assertLess(calls[0].lineno, writes[0].lineno)
        packaging = Path(__file__).with_name('prepare_auditor_final.py').read_text()
        self.assertIn("'auditor_feature_diagnostics.py'", packaging)


if __name__ == '__main__':
    unittest.main()
