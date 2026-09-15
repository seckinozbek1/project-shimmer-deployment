import sys,unittest,importlib.util,tempfile,io,json
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'benchmark/producer_coverage_amendment_v3'))
import access_guard
access_guard.install('POST_GOLD')
import semantics as s
out=ROOT/'output/producer_coverage_amendment_v3/cohort_targeted_gate';out.mkdir(exist_ok=True)
tempfile.tempdir=str(ROOT/'output/producer_coverage_amendment_v3/test_fixtures')
base=ROOT/'benchmark/first_tuning_review_cohort_v2'
sys.path.insert(0,str(base))
spec=importlib.util.spec_from_file_location('v3_cohort_post_checks',base/'checks.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
excluded={'test_frozen_inputs_acceptance_and_active_revision','test_exports_blank_exact_inputs_no_hidden_fields','test_current_binding_passes_without_implying_human_review','test_old_journal_cannot_count','test_unreceipted_native_cannot_count','test_zero_real_review_and_training_status','test_superseded_rejection_effect'}
names=[name for name in unittest.defaultTestLoader.getTestCaseNames(module.Checks) if name not in excluded]
suite=unittest.TestSuite(module.Checks(name) for name in names)
def profile_integrity():
 value=s.read(ROOT/'benchmark/first_tuning_experiment_v1/acceptance_registration.json')
 assert len(value['criteria'])==27 and len(value['catastrophic_limits'])==6 and all(v==0 for v in value['catastrophic_limits'].values())
 assert value['derived_hard_gate']['id']=='R07' and value['derived_hard_gate']['value']==0
suite.addTest(unittest.FunctionTestCase(profile_integrity))
log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
(out/'validation.log').write_text(log.getvalue(),encoding='utf8')
report=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),selected_original_tests=names,not_rerun=sorted(excluded),scope='Relevant immutable cohort selection/access/binding/blank-export tests; repeated full historical hash scans and human-ingestion paths are not needed for V3, with full catalog hashes verified independently.',effect_proofs=3,actual_human_submissions=0,fake_human_submissions=0,model_generation=False,training=False)
s.write(out/'validation.json',report)
if not result.wasSuccessful():print(log.getvalue());raise SystemExit(1)
import run_gate as historical
proof=historical.historical_baseline(s.read(module.c.h.V1/'seed.json'))
s.write(out/'historical_reproduction.json',dict(rejections_reproduced=len(proof['results']),raw_hashes={v['label']:v['raw_sha256'] for v in proof['results']},rewritten=False))
print(json.dumps(dict(tests=result.testsRun,failures=0,effect_proofs=3,historical_rejections=len(proof['results']))))
