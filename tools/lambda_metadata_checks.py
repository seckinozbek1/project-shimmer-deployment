"""Offline response-boundary, artifact and installer proofs. Synthetic values only."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import cloud_run_watchdog as watchdog
import lambda_experiment_provider as provider
import run_remote_experiment as controller
import prepare_remote_experiment as preparation
from cloud_run_common import InvalidPreparation, METADATA_FIELDS, credential_locations


class SecurityChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=self.enterContext(tempfile.TemporaryDirectory());self.base=Path(self.tmp)
        self.mark='SYNTHETIC-'+''.join(['future','-sentinel','-only'])
        self.raw=dict(id='a'*32,name='bounded-fixture',status='active',ip='192.0.2.1',
            region=dict(name='us-east-1',unneeded=self.mark),instance_type=dict(name='gpu_1x_a10',
            gpu_description='A10',price_cents_per_hour=129,specs=dict(gpus=1,vcpus=30,memory_gib=200,storage_gib=1400,extra=self.mark)),
            jupyter_token=self.mark,jupyter_url='https://example.invalid/?'+'token='+self.mark,
            api_key='sk-'+'proj-'+('SYNTHETIC'*4),temporary_password=self.mark,
            nested=[dict(private=[self.mark])],arbitrary_future_field=self.mark)
        self.enterContext(patch.object(watchdog,'load_credential',return_value='TEST_CREDENTIAL_PLACEHOLDER'))
        self.enterContext(patch.object(provider,'load_credential',return_value='TEST_CREDENTIAL_PLACEHOLDER'))
        self.enterContext(patch.object(watchdog.shutil,'which',return_value='curl'))
        self.run=self.enterContext(patch.object(watchdog.subprocess,'run'))
        self.run.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(dict(data=[self.raw]))+'\n200',stderr=self.mark)
        self.client=provider.LambdaExperiment()

    def assert_clean(self,value):
        encoded=json.dumps(value)
        self.assertNotIn(self.mark,encoded)
        self.assertNotIn(self.raw['api_key'],encoded)
        self.assertFalse(credential_locations(encoded.encode(),'synthetic-output'))

    def test_public_request_drops_known_unknown_and_nested_fields(self):
        result=self.client.request('instances')
        self.assert_clean(result)
        self.assertEqual(set(result['data'][0])-METADATA_FIELDS,set())
        self.assertEqual(result['data'][0]['public_ip'],'192.0.2.1')
        self.assertNotIn('jupyter_token',json.dumps(result))

    def test_status_polling_and_artifact_sweep(self):
        stream=io.StringIO()
        with contextlib.redirect_stdout(stream):
            for _ in range(3):
                state=controller.poll_state(self.client,'a'*32,self.base)
                print(json.dumps(state))
        self.assert_clean(stream.getvalue())
        for path in self.base.iterdir():self.assert_clean(json.loads(path.read_text()))

    def test_termination_proof_without_raw_metadata(self):
        self.run.return_value.stdout=json.dumps(dict(data=[]))+'\n200'
        self.assertTrue(controller.termination(self.client,'a'*32,self.base,1,1.29))
        proof=json.loads((self.base/'TERMINATION_VERIFIED.json').read_text())
        self.assertEqual(proof['metadata']['status'],'terminated');self.assert_clean(proof)

    def test_http_and_exception_failure_paths_do_not_echo_payload(self):
        for endpoint in ('instances','images'):
            for error in (False,True):
                self.run.side_effect=OSError(self.mark) if error else None
                self.run.return_value.stdout=json.dumps(dict(error=self.mark))+'\n403'
                stream=io.StringIO()
                with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                    with self.assertRaises(InvalidPreparation) as caught:self.client.request(endpoint)
                self.assert_clean(str(caught.exception));self.assert_clean(stream.getvalue())
        self.run.side_effect=None

    def test_invalid_operational_value_cannot_leak_in_exception(self):
        self.raw['ip']=self.mark
        self.run.return_value.stdout=json.dumps(dict(data=[self.raw]))+'\n200'
        with self.assertRaises(InvalidPreparation) as caught:self.client.request('instances')
        self.assert_clean(str(caught.exception))

    def test_inventory_discards_irrelevant_cpu_and_multigpu_rows(self):
        raw=dict(cpu=dict(instance_type=dict(specs=dict(gpus=0),gpu_description='N/A',unexpected=self.mark)),
                 cluster=dict(instance_type=dict(specs=dict(gpus=8),unexpected=self.mark)))
        self.assertEqual(provider.project_response('instance-types',raw),[])

    def test_launch_and_inventory_response_allowlists(self):
        raw=dict(instance_ids=['a'*32],new_field=self.mark,instances=[self.raw])
        self.assert_clean(provider.project_response('instance-operations/launch',raw))
        inventory=dict(any_key=dict(instance_type=self.raw['instance_type'],regions_with_capacity_available=[self.raw['region']],extra=self.mark))
        self.assert_clean(provider.project_response('instance-types',inventory))
        self.assert_clean(provider.project_response('ssh-keys',dict(id='b'*32,name='fixture',private=self.mark)))

    def test_metadata_neutralise_fail_restore_pass(self):
        original=watchdog.provider_instance
        with patch.object(watchdog,'provider_instance',side_effect=lambda value:value):
            with self.assertRaises(AssertionError):self.test_public_request_drops_known_unknown_and_nested_fields()
        self.assertIs(watchdog.provider_instance,original)
        self.test_public_request_drops_known_unknown_and_nested_fields()

    def test_controller_has_no_raw_transport_or_direct_provider_json(self):
        source=Path(controller.__file__).read_text()
        for forbidden in ('cloud.lambda.ai','response.stdout','row[\'jupyter','json.dumps(raw','json.dump(raw'):
            self.assertNotIn(forbidden,source)
        self.assertIn('safe_metadata(provider.instance(',source)

    def test_reviewed_bundle_rejects_untracked_member(self):
        root=self.base/'root';out=self.base/'out';out.mkdir();(root/'config').mkdir(parents=True);(root/'tools').mkdir()
        for name in controller.CONFIGS:(root/'config'/name).write_text('{}')
        (root/'tools/example.py').write_text('value=1\n')
        files={'tools/example.py':dict(sha256='unused',bytes=8)}
        tracked=['config/'+name for name in controller.CONFIGS]+['tools/example.py']
        with patch.object(controller,'source_manifest',return_value={'source_files':files}),patch.object(controller,'git',return_value='\0'.join(tracked).encode()):
            review=controller.bundle(root,out);self.assertEqual(review['file_count'],5)
        with patch.object(controller,'source_manifest',return_value={'source_files':files}),patch.object(controller,'git',return_value=b''):
            with self.assertRaises(InvalidPreparation):controller.bundle(root,out)

    def test_install_plan_pinned_closure_and_existing_refusal(self):
        root=self.base;folder=root/'tools/cloud_run';folder.mkdir(parents=True)
        (folder/'runtime.lock').write_text('psutil==7.0.0\npackaging==25.0\n')
        selected=dict(executable=str(root/'python'),profile='experiment');calls=[];existing={}
        def run(args,**kwargs):
            calls.append(args)
            if '--report' in args:
                Path(args[args.index('--report')+1]).write_text(json.dumps(dict(install=[dict(metadata=dict(name='psutil',version='7.0.0',description=self.mark)),dict(metadata=dict(name='packaging',version='25.0'))])))
            return SimpleNamespace(stdout=json.dumps(existing),returncode=0)
        preparation.install_missing(selected,['psutil'],root,root,run)
        self.assertNotIn(self.mark,(root/'dependency_install_plan.json').read_text())
        self.assertIn('packaging==25.0',calls[-1]);self.assertIn('--no-deps',calls[-1])
        self.assertTrue(all(c[0]==selected['executable'] for c in calls))
        calls.clear();existing['packaging']='24.0'
        with self.assertRaisesRegex(ValueError,'existing or undeclared'):preparation.install_missing(selected,['psutil'],root,root,run)
        self.assertFalse(any('--no-deps' in c for c in calls))


if __name__=='__main__':unittest.main()
