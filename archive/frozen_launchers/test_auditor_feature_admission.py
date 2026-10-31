"""Offline admission regression: saved TRAIN observations and synthetic CPU tensors."""
import ast
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import numpy as np
import torch
import auditor_feature_diagnostics as d
from test_auditor_feature_diagnostics import Fixture
from analyze_auditor_blocker_closure import cost_usd

ROOT = Path(__file__).resolve().parents[1]
D = ROOT/'tuning/auditor_final'
H = ROOT/'docs/fix/auditor_classifier_lora_current_runtime_run/downloaded/evidence'


class AdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((D/'records_train_only.json').read_text())
        cls.features = np.load(H/'current_train_features.npy', mmap_mode='r', allow_pickle=False)
        assert hashlib.sha256((H/'current_train_features.npy').read_bytes()).hexdigest() == '06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'failure.json'
        self.gate = d.HistoricalAdmission(np, self.rows, D/'historical_train_features.jsonl')

    def extract(self, value, index=0, raw=None):
        row = self.rows[index]
        if raw is None:
            raw = torch.from_numpy(value.copy()).reshape(1,1,-1).expand(1,len(row['input_ids']),-1)
        model = Fixture(raw)
        result = d.extract_train_vector(torch,np,model,row,index,'cpu',self.path,admission=self.gate)
        return result

    def admit_saved_prefix(self, n):
        for i in range(n):
            self.gate.check_input(i,self.rows[i])
            self.assertIsNone(self.gate.vector_reason(self.features[i],i))
            self.gate.accepted += 1

    def test_exact_live_copy_passes_without_evidence_or_substitution(self):
        value = self.features[0].copy()
        got = self.extract(value)
        self.assertEqual(value.tobytes(),got.tobytes())
        self.assertFalse(np.shares_memory(got,value))
        self.assertEqual(self.gate.accepted,1)
        self.assertFalse(self.path.exists())
        self.assertFalse(hasattr(self.gate,'features'))

    def test_all_1792_saved_rows_complete_and_persistence_corruption_fails(self):
        self.admit_saved_prefix(1792)
        self.assertEqual(self.gate.require_complete(self.features)['rows'],1792)
        corrupted = self.features.copy(); corrupted[1791,0] += 1
        with self.assertRaisesRegex(RuntimeError,'persistence mismatch'):
            self.gate.require_complete(corrupted)

    def test_finite_drift_is_durable_and_latched(self):
        value = self.features[0].copy(); value[0] = np.nextafter(value[0],np.float32(np.inf))
        with self.assertRaisesRegex(RuntimeError,'historical_finite_drift'):
            self.extract(value)
        receipt = json.loads(self.path.read_text())
        self.assertEqual(receipt['reason'],'historical_finite_drift')
        self.assertTrue(receipt['capture_complete'])
        self.assertEqual(np.load(self.path.with_suffix('.npy'),allow_pickle=False).tobytes(),value.tobytes())
        self.assertTrue(self.path.with_suffix('.pt').exists())
        with self.assertRaisesRegex(RuntimeError,'latched'):
            self.extract(self.features[0])
        with self.assertRaises(RuntimeError): self.gate.require_complete(self.features)
        self.assertEqual(self.gate.accepted,0)

    def test_late_finite_drift_beyond_prefix_stops(self):
        self.admit_saved_prefix(100)
        value = self.features[100].copy(); value[0] += 1
        with self.assertRaisesRegex(RuntimeError,'historical_finite_drift'): self.extract(value,100)
        self.assertEqual(self.gate.accepted,100)
        self.assertEqual(json.loads(self.path.read_text())['row_one_based'],101)

    def test_wrong_raw_shape_stops_and_saves_raw(self):
        with self.assertRaisesRegex(RuntimeError,'raw_hidden_shape'):
            self.extract(None,raw=torch.ones(1,1,3071))
        self.assertTrue(self.gate.failed)
        self.assertTrue(self.path.with_suffix('.pt').exists())
        self.assertFalse(self.path.with_suffix('.npy').exists())

    def test_nan_and_both_infinities_stop(self):
        for bad in [np.nan,np.inf,-np.inf]:
            self.gate = d.HistoricalAdmission(np,self.rows,D/'historical_train_features.jsonl')
            value = self.features[0].copy();value[2]=bad
            with self.assertRaisesRegex(RuntimeError,'finite TRAIN hidden'): self.extract(value)
            self.assertTrue(self.gate.failed)
            self.assertEqual(self.gate.accepted,0)

    def test_dtype_and_vector_shape_refused(self):
        self.assertEqual(self.gate.vector_reason(self.features[0].astype(np.float64),0),'historical_vector_dtype')
        self.assertEqual(self.gate.vector_reason(self.features[0].reshape(1,-1),0),'historical_vector_shape')

    def test_missing_changed_or_reordered_reference_refused(self):
        with self.assertRaises(FileNotFoundError): d.HistoricalAdmission(np,self.rows,self.path)
        self.path.write_bytes((D/'historical_train_features.jsonl').read_bytes()+b'\n')
        with self.assertRaisesRegex(RuntimeError,'receipt identity'): d.HistoricalAdmission(np,self.rows,self.path)
        rows = copy.deepcopy(self.rows); rows[0]['input_ids'][0] += 1
        with self.assertRaisesRegex(RuntimeError,'input binding'): d.HistoricalAdmission(np,rows,D/'historical_train_features.jsonl')
        with self.assertRaises(RuntimeError): self.gate.check_input(1,self.rows[1])

    def test_partial_admission_never_unlocks_downstream(self):
        self.admit_saved_prefix(32)
        downstream=Mock()
        with self.assertRaises(RuntimeError):
            self.gate.require_complete(self.features); downstream()
        downstream.assert_not_called()

    def test_diagnostic_io_failure_cannot_admit(self):
        value=self.features[0].copy();value[0]+=1
        with patch.object(d,'write_diagnostic',side_effect=OSError('fixture')):
            with self.assertRaises(OSError): self.extract(value)
        self.assertTrue(self.gate.failed)
        with self.assertRaises(RuntimeError): self.gate.require_complete(self.features)

    def test_detail_capture_failure_keeps_minimal_evidence(self):
        value=self.features[0].copy();value[0]+=1
        with patch.object(d,'tensor_summary',side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError): self.extract(value)
        self.assertEqual(json.loads(self.path.read_text())['reason'],'historical_finite_drift')
        self.assertFalse(json.loads(self.path.read_text())['capture_complete'])
        self.assertTrue(self.path.with_suffix('.npy').exists())
        self.assertTrue(self.gate.failed)

    def test_failed_receipt_upgrade_preserves_previous_durable_receipt(self):
        d.write_diagnostic(self.path,dict(reason='historical_finite_drift'))
        with patch.object(d.os,'replace',side_effect=OSError('fixture disk failure')):
            with self.assertRaises(OSError): d.write_diagnostic(self.path,dict(detail='upgrade'))
        self.assertEqual(json.loads(self.path.read_text())['reason'],'historical_finite_drift')

    def test_raw_capture_failure_still_stops_with_vector_and_reason(self):
        value=self.features[0].copy();value[0]+=1
        with patch.object(torch,'save',side_effect=RuntimeError('fixture device unavailable')):
            with self.assertRaisesRegex(RuntimeError,'historical_finite_drift'): self.extract(value)
        receipt=json.loads(self.path.read_text())
        self.assertFalse(receipt['capture_complete'])
        self.assertEqual(receipt['admission']['raw_capture_error'],'RuntimeError')
        self.assertIn('vector_file_sha256',receipt['admission'])
        self.assertTrue(self.gate.failed)

    def test_saved_failed_run_refused_at_first_drift_row11(self):
        failed=np.load(ROOT/'docs/fix/auditor_final_run/downloaded/evidence/train_features.npy',mmap_mode='r',allow_pickle=False)
        for i in range(10):
            self.gate.check_input(i,self.rows[i])
            self.assertIsNone(self.gate.vector_reason(failed[i],i));self.gate.accepted+=1
        with self.assertRaisesRegex(RuntimeError,'historical_finite_drift'): self.extract(failed[10],10)
        self.assertEqual(self.gate.accepted,10)
        self.assertEqual(json.loads(self.path.read_text())['row_one_based'],11)

    def test_actual_production_loop_stops_before_normalize_on_bad_row(self):
        tree=ast.parse((ROOT/'tools/auditor_final_remote.py').read_text())
        training=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='training')
        body=next(n for n in training.body if isinstance(n,ast.Try)).body
        loop=next(n for n in body if isinstance(n,ast.For) and ast.unparse(n.iter)=='enumerate(rows)')
        complete=next(n for n in body if 'admission.require_complete(features)' in ast.unparse(n) and isinstance(n,ast.Expr))
        norm=next(n for n in body if isinstance(n,ast.Assign) and 'current.normalize' in ast.unparse(n))
        self.assertLess(loop.lineno,complete.lineno);self.assertLess(complete.lineno,norm.lineno)
        source=ast.unparse(loop)
        self.assertIn('admission=admission',source)
        self.assertLess(source.index('extract_train_vector('),source.index('features[i] = vector'))
        downstream_calls=[n.lineno for n in ast.walk(training) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ('normalize','fit_head','new_optimizer','update')]
        self.assertTrue(all(complete.lineno < line for line in downstream_calls))
        failed=self.features[0].copy();failed[0]+=1
        def synthetic(torch_arg,np_arg,model,row,i,device,path,admission):
            return self.extract(failed,i)
        features=np.full((1792,3072),np.nan,np.float32)
        current=SimpleNamespace(normalize=Mock(side_effect=AssertionError('must not fit')))
        env=dict(rows=self.rows,budget=SimpleNamespace(check=Mock()),features=features,
                 extract_train_vector=synthetic,torch=torch,np=np,model=None,OUT=Path(self.tmp.name),
                 admission=self.gate,emit=Mock(),fork=None,hashlib=hashlib,write=Mock(),current=current)
        with self.assertRaisesRegex(RuntimeError,'historical_finite_drift'):
            exec(compile(ast.Module(body=[loop,complete,norm],type_ignores=[]),'production-loop','exec'),env)
        current.normalize.assert_not_called();env['write'].assert_not_called()
        self.assertTrue(np.isnan(features).all())

    def test_cost_is_dollars_per_hour_not_per_second(self):
        self.assertEqual(cost_usd(3600,1.29),1.29)
        self.assertAlmostEqual(cost_usd(623.1199488639832,1.29),.2232846483429273)
        with self.assertRaises(RuntimeError): cost_usd(-1,1.29)


if __name__=='__main__': unittest.main()
