"""Offline controller gates; never constructs a live provider."""
import ast,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import auditor_final_retry_cloud as cloud

class RetryTests(unittest.TestCase):
 def test_consumed_marker_stops_before_provider(self):
  with tempfile.TemporaryDirectory() as folder:
   base=Path(folder);(base/'LAUNCH_INTENT.json').touch()
   m=dict(source_commit='fixture',region='us-east-1',instance=dict(type='gpu_1x_a10'),hourly_rate=1.29,soft_usd=5,hard_usd=7,workload_deadline_seconds=18000,watchdog_deadline_seconds=19000)
   values={'manifest.json':m,'LOCAL_GATES.json':dict(passed=True,execution_manifest_sha256='fixture'),'bundle_check_results.json':dict(passed=True),'execution_manifest.json':dict(local_source_hashes={},seal_sha256='fixture'),'training_authorization.json':dict(operator_authorized=True,action='auditor-final-training-evaluation',execution_manifest_sha256='fixture',seal_sha256='fixture',source_commit='fixture')}
   with patch.object(cloud,'BASE',base),patch.object(cloud,'read',side_effect=lambda p:values[p.name]),patch.object(cloud,'sha',return_value='fixture'),patch.object(cloud,'git',return_value=b''),patch.object(cloud,'LambdaExperiment') as provider:
    with self.assertRaisesRegex(Exception,'consumed'):cloud.execute()
    provider.assert_not_called()
 def test_authorization_refused_before_provider(self):
  with tempfile.TemporaryDirectory() as folder:
   base=Path(folder)
   m=dict(source_commit='fixture',region='us-east-1',instance=dict(type='gpu_1x_a10'),hourly_rate=1.29,soft_usd=5,hard_usd=7,workload_deadline_seconds=18000,watchdog_deadline_seconds=19000)
   values={'manifest.json':m,'LOCAL_GATES.json':dict(passed=True,execution_manifest_sha256='fixture'),'bundle_check_results.json':dict(passed=True),'execution_manifest.json':dict(local_source_hashes={}), 'training_authorization.json':dict(operator_authorized=False)}
   with patch.object(cloud,'BASE',base),patch.object(cloud,'read',side_effect=lambda p:values[p.name]),patch.object(cloud,'sha',return_value='fixture'),patch.object(cloud,'LambdaExperiment') as provider:
    with self.assertRaisesRegex(Exception,'Explicit retry authorization'):cloud.execute()
    provider.assert_not_called()
 def test_delayed_evaluation_and_single_launch_structure(self):
  source=Path(cloud.__file__).read_text();tree=ast.parse(source)
  launches=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='instance-operations/launch']
  self.assertEqual(len(launches),1)
  self.assertLess(source.index('admit_evaluation(completion)'),source.index("path=ROOT/'tuning/auditor_classifier_lora'/name"))
  self.assertIn('independent_inventory_confirmation.json',source)
  self.assertIn('tuning/first_domain_agnostic_v1',source)
  self.assertNotIn("BASE=ROOT/'docs/fix/auditor_final_run'",source)

if __name__=='__main__':unittest.main()
