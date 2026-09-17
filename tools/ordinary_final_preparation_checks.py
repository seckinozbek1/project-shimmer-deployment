"""Deterministic preparation checks: no model, no provider, no pipeline execution."""
import ast
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import ordinary_final_run as run
import ordinary_final_watchdog as watch


class PreparationChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        (self.base/'project/input/context').mkdir(parents=True)
        (self.base/'project/input/context/fixture.md').write_text('fixture')
        self.m=dict(max_runs=1,model_mode='final',multi_round=False,protected_test=False,
            argv=run.ARGV,topology=run.TOPOLOGY,source_commit='f'*40,soft_budget_usd=5,
            environment=dict(SHIMMER_MODEL_MODE='final',SHIMMER_BACKEND_PROFILE='local',
                HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8'),
            hard_ceiling_usd=7,max_hourly_rate=1.29,project_files={
            'input/context/fixture.md':run.sha(self.base/'project/input/context/fixture.md')},support_files={})
        self.seal()
    def seal(self):
        run.write(self.base/'execution_manifest.json',self.m)
        run.write(self.base/'seal.json',dict(execution_manifest_sha256=run.sha(self.base/'execution_manifest.json')))
    def permit(self):
        return dict(operator_authorized=True,action='one-ordinary-final-cloud-run',
            execution_manifest_sha256=run.sha(self.base/'execution_manifest.json'),seal_sha256=run.sha(self.base/'seal.json'),
            source_commit=self.m['source_commit'],soft_budget_usd=5,hard_ceiling_usd=7,
            provider='Lambda',instance_type='gpu_1x_a10',instance_id='a'*32,region='us-east-1',hourly_rate=1.29,active_start_epoch=1000)
    def test_seal_and_exact_tree(self):
        self.assertEqual(run.verify(self.base),self.m)
        (self.base/'project/input/context/unapproved.md').write_text('extra')
        with self.assertRaises(RuntimeError):run.verify(self.base)
    def test_changed_workload(self):
        (self.base/'project/input/context/fixture.md').write_text('changed')
        with self.assertRaises(RuntimeError):run.verify(self.base)
    def test_changed_manifest(self):
        (self.base/'execution_manifest.json').write_text('{}')
        with self.assertRaises(RuntimeError):run.verify(self.base)
    def test_multiround_and_flags_rejected_even_if_resealed(self):
        for key,value in [('multi_round',True),('protected_test',True),('argv',run.ARGV+['--multi-round']),('max_runs',2)]:
            old=self.m[key];self.m[key]=value;self.seal()
            with self.assertRaises(RuntimeError):run.verify(self.base)
            self.m[key]=old
    def test_authorization_not_inherited(self):
        p=self.permit();run.authorization(self.base,self.m,p,now=1100)
        for key,value in [('operator_authorized',False),('action','auditor-final-training-evaluation'),('source_commit','0'*40),('hourly_rate',2),('hard_ceiling_usd',10),('region','us-west-1')]:
            changed=dict(p);changed[key]=value
            with self.assertRaises(RuntimeError):run.authorization(self.base,self.m,changed,now=1100)
        with self.assertRaises(RuntimeError):run.authorization(self.base,self.m,p,now=100000)
    def test_actual_parser_ordinary_flags(self):
        import argparse
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
        import agent_activation
        tree=ast.parse((Path(__file__).resolve().parents[1]/'scripts/pipeline.py').read_text(encoding='utf8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_build_arg_parser')
        scope=dict(argparse=argparse,agent_activation=agent_activation)
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'actual-parser','exec'),scope)
        args=scope['_build_arg_parser']().parse_args(run.ARGV)
        self.assertFalse(args.multi_round);self.assertIsNone(args.multi_round_manifest)
        self.assertEqual((args.execution_topology,args.activation_profile,args.review_mode),('report_optimized','dense','paired'))
    def raw(self):
        return [dict(event='pipeline_start'),dict(event='pipeline_end'),dict(event='model_call',adapter_checkpoint=168)]
    def completion(self):return dict(state='completed',reached_end=True,exit_code=0)
    def test_quality_targets_not_execution_errors(self):
        rows=self.raw()+[dict(event='auditor_pair_unavailable'),dict(event='auditor_verifier_join',agreement='disagree'),
            dict(event='model_call',refused=True,cap_hit=True,truncated=False,contract_valid=True)]
        self.assertTrue(run.assess(self.completion(),rows)['execution_integrity_passed'])
    def test_numerical_contract_transport_fail_closed(self):
        for r in [dict(event='auditor_pair',classifier_status='failed'),dict(event='model_call',contract_valid=False),
                  dict(event='backend_invocation',backend_success=False)]:
            self.assertFalse(run.assess(self.completion(),self.raw()+[r])['execution_integrity_passed'])
        self.assertFalse(run.assess(self.completion(),[])['execution_integrity_passed'])
        self.assertFalse(run.assess(None,self.raw())['execution_integrity_passed'])
    def test_existing_partition_recovery_is_preserved(self):
        raw=self.raw()+[dict(event='backend_invocation',agent='PROCESSOR',backend_success=False),
            dict(event='model_call',agent='PROCESSOR',contract_valid=False)]
        self.assertTrue(run.assess(self.completion(),raw)['execution_integrity_passed'])
        self.assertEqual(run.assess(self.completion(),raw)['failed_backend_attempts'],1)
        self.assertFalse(run.assess(dict(state='stopped'),raw)['execution_integrity_passed'])
    def test_cost_and_reserves(self):
        limits=watch.deadlines(1000,1.29,5,7)
        self.assertAlmostEqual((limits['ceiling']-1000)*1.29/3600,7)
        self.assertEqual(limits['ceiling']-limits['stop'],900)
        self.assertEqual(limits['ceiling']-limits['terminate'],180)
        for rate in [0,-1,float('nan'),float('inf'),2]:
            with self.assertRaises(RuntimeError):watch.deadlines(1000,rate,5,7)
    def test_watchdog_terminates_only_named_instance(self):
        provider=Mock();provider.instance.side_effect=[dict(status='active'),dict(status='terminated')]
        p=self.permit();p['instance_id']='test-instance'
        current=watch.deadlines(1000,1.29,5,7)['terminate']
        watch.watch(self.base,provider,p,self.m,now=lambda:current,sleep=lambda _:None)
        provider.terminate.assert_called_once_with('test-instance')
        self.assertTrue((self.base/'TERMINATION_VERIFIED.json').is_file())
        self.assertTrue((self.base/'STOP_WORKLOAD').is_file())
    def test_component_summary_unknowns_and_retention(self):
        from ordinary_final_summary import supplement
        raw=[dict(event='model_call',call_id='p',agent='PROCESSOR',input_tokens=10,output_tokens=8,
                  generation_seconds=2,emitted_count=3,retained_count=None),
             dict(event='retention_snapshot',call_counts={'p':2})]
        summary=supplement(raw,[dict(event='ready',dependency_wait_s=2),dict(event='assigned',scheduler_wait_s=3)])
        p=summary['per_agent']['PROCESSOR']
        self.assertEqual(p['metrics']['retained_count']['value'],2)
        self.assertEqual(p['metrics']['emitted_count']['value'],3)
        self.assertEqual(p['decode_tokens_per_second'],4)
        self.assertIsNone(p['metrics']['total_service_seconds']['value'])
        self.assertEqual((summary['dependency_wait_task_seconds'],summary['resource_wait_task_seconds']),(2,3))
    def test_runtime_bytes_and_final_environment_admitted(self):
        from types import SimpleNamespace
        path=self.base/'library.py';path.write_text('fixture')
        m=dict(packages={'fixture':'1.0'},runtime_file_hashes={'fixture':{'library.py':run.sha(path)}})
        dist=lambda _:SimpleNamespace(version='1.0',locate_file=lambda _:path)
        run.installed_runtime(m,dist)
        path.write_text('changed')
        with self.assertRaises(RuntimeError):run.installed_runtime(m,dist)
        self.m['environment']['SHIMMER_MODEL_MODE']='base';self.seal()
        with self.assertRaises(RuntimeError):run.verify(self.base)
    def test_hardware_admission(self):
        from types import SimpleNamespace as NS
        torch=NS(cuda=NS(device_count=lambda:1,get_device_properties=lambda _:NS(name='NVIDIA A10'),
                        mem_get_info=lambda _:(23*2**30,24*2**30)))
        psutil=NS(cpu_count=lambda:30,virtual_memory=lambda:NS(total=200*2**30,available=180*2**30))
        with patch.object(run.shutil,'disk_usage',return_value=NS(free=40*2**30)):
            self.assertEqual(run.hardware_admission(self.base,torch,psutil)['gpu_name'],'NVIDIA A10')
            torch.cuda.device_count=lambda:2
            with self.assertRaises(RuntimeError):run.hardware_admission(self.base,torch,psutil)


if __name__=='__main__':
    unittest.main(verbosity=2)
