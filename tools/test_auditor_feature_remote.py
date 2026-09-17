"""No-cloud tests of the diagnostic stage boundaries and success telemetry."""
import ast
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np
import torch
import auditor_feature_diagnostics as d
import auditor_feature_remote as remote
from test_auditor_feature_diagnostics import Fixture


class DiagnosticContracts(unittest.TestCase):
    def test_all_pass_bounded_order_with_fresh_prefix(self):
        calls=[]
        def observe(stage, sequence, index):calls.append((stage,index));return True
        verdict=remote.stages(observe,lambda:calls.append(('reset',None)),lambda *_:self.fail('unexpected isolation'))
        self.assertEqual(verdict,'REMOTE_BLOCKER_NOT_REPRODUCED')
        self.assertEqual(calls[:6],[('A',31),('A',31),('B',29),('B',30),('B',31),('B',32)])
        self.assertEqual(calls[6],('reset',None))
        self.assertEqual(calls[7:],[('C',i) for i in range(32)])

    def test_each_failure_prevents_later_expansion(self):
        for fail_at in [1,2,3,6,7,38]:
            calls=[];isolated=[]
            def observe(stage,sequence,index):calls.append((stage,index));return len(calls)!=fail_at
            def isolate(stage,index):isolated.append((stage,index));return remote.VERDICTS[1]
            self.assertEqual(remote.stages(observe,lambda:None,isolate),remote.VERDICTS[1])
            self.assertEqual(len(calls),fail_at);self.assertEqual(isolated,[calls[-1]])

    def test_success_records_raw_and_vector_state(self):
        raw=torch.ones((1,2,3072),dtype=torch.bfloat16)
        model=Fixture(raw);row=dict(split='train',example_id='fixture32',input_ids=[1,2],prompt_sha256='fixture')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'receipt.json'
            value=d.extract_train_vector(torch,np,model,row,31,'cpu',path,record_success=True)
            receipt=json.loads(path.read_text())
            self.assertEqual(receipt['event'],'train_feature_valid')
            self.assertEqual(receipt['raw_hidden']['shape'],[1,2,3072])
            self.assertEqual(receipt['vector']['finite_count'],3072)
            self.assertEqual(receipt['model_before']['active_adapters'],['historical_reference'])
            self.assertTrue(receipt['forward_autocast']['inference_mode'])
            self.assertFalse(receipt['forward_autocast']['grad_enabled'])
            self.assertEqual(receipt['vector']['nan']['count'],0)
            self.assertTrue(np.array_equal(value,np.ones(3072,dtype=np.float32)))

    def test_no_training_calls_in_remote_diagnostic(self):
        tree=ast.parse(Path(remote.__file__).read_text())
        forbidden={'fit_head','normalize','training','evaluation','run_study','update','step','backward','Adam','AdamW','SGD'}
        calls={n.func.id if isinstance(n.func,ast.Name) else n.func.attr for n in ast.walk(tree)
               if isinstance(n,ast.Call) and isinstance(n.func,(ast.Name,ast.Attribute))}
        # dict.update only records evidence/model references, not optimizer work.
        self.assertFalse((forbidden-{'update'}) & calls)
        source=Path(remote.__file__).read_text()
        self.assertIn("torch.Tensor.backward = no_training",source)
        self.assertIn("choices=['scope','preflight','acquire','execute']",source)

    def test_controller_single_launch_and_collection_before_termination(self):
        source=Path(__file__).with_name('auditor_feature_cloud.py').read_text()
        self.assertEqual(source.count("provider.request('instance-operations/launch'"),1)
        self.assertIn("(BASE/'LAUNCH_INTENT.json').open('x')",source)
        self.assertIn("tools/auditor_feature_remote.py execute",source)
        self.assertNotIn("remote('final_training'",source)
        self.assertNotIn("remote('final_evaluation'",source)
        self.assertLess(source.index("transport('evidence_download'"),source.index("(BASE/'TERMINATE_REQUEST').touch()"))
        self.assertIn("independent=LambdaExperiment(CREDENTIAL)",source)


if __name__=='__main__':unittest.main()
