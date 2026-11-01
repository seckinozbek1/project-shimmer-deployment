"""Run CPU regression and in-memory neutralize/restore; no model/cloud operations."""
import hashlib,io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import auditor_feature_diagnostics as d
import test_auditor_feature_admission as tests
BASE=ROOT/'docs/fix/auditor_blocker_closure_run'
loader=unittest.TestLoader()
suite=unittest.TestSuite(loader.loadTestsFromName(name) for name in ('test_auditor_feature_admission','test_auditor_feature_diagnostics','test_auditor_final'))
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(BASE/'admission_tests.log').write_text(stream.getvalue())
assert result.wasSuccessful(),stream.getvalue()
method='test_finite_drift_is_durable_and_latched'
stream=io.StringIO()
with patch.object(d.HistoricalAdmission,'vector_reason',return_value=None):
    neutralized=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite([tests.AdmissionTests(method)]))
(BASE/'admission_neutralized.log').write_text(stream.getvalue())
assert not neutralized.wasSuccessful() and len(neutralized.failures)==1 and not neutralized.errors
stream=io.StringIO();restored=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite([tests.AdmissionTests(method)]))
(BASE/'admission_restored.log').write_text(stream.getvalue());assert restored.wasSuccessful()
receipt=dict(passed=True,tests=result.testsRun,neutralized_failed=True,restored_passed=True,
 no_real_model_forwards=True,no_cloud_calls=True,source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['tools/auditor_feature_diagnostics.py','tools/auditor_final_remote.py','tools/test_auditor_feature_admission.py','tools/analyze_auditor_blocker_closure.py','tuning/auditor_final/historical_train_features.jsonl']},
 test_logs={p:hashlib.sha256((BASE/p).read_bytes()).hexdigest() for p in ['admission_tests.log','admission_neutralized.log','admission_restored.log']})
(BASE/'ADMISSION_VALIDATION.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(tests=result.testsRun,neutralized_failed=True,restored_passed=True)))
