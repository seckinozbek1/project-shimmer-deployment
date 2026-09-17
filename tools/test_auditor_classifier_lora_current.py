import ast
import math
import unittest
from pathlib import Path
import numpy as np
import auditor_classifier_lora_current_core as current
import auditor_classifier_lora_core as c
import auditor_classifier_lora_stable as stable
import test_auditor_classifier_lora_fork as fixtures

ROOT=Path(__file__).resolve().parents[1]


class Tests(unittest.TestCase):
    def fixture(self):
        g,rows,select,observe,remove,verify,state,events=fixtures.Tests().fixture()
        g.baseline['metrics']=c.metrics(g.baseline['labels'],g.baseline['labels'])
        return current.CurrentPreflight(np,{'example_ids':g.controls['example_ids']},g.baseline,events.append),rows,select,observe,remove,verify,state,events

    def test_01_current_parity_success_no_old_controls(self):
        g,rows,select,observe,remove,verify,_,_=self.fixture()
        self.assertTrue(g.run(rows,select,observe,remove,verify)['passed'])

    def test_02_mismatch_blocks_and_no_retry(self):
        g,rows,select,observe,remove,verify,state,_=self.fixture()
        def bad(row):
            v=observe(row)
            if state['slot']=='classifier_fork':v['hidden']+=1
            return v
        with self.assertRaises(stable.NumericalStop):g.run(rows,select,bad,remove,verify)
        with self.assertRaises(stable.NumericalStop):g.run(rows,select,observe,remove,verify)

    def test_03_current_baseline_only(self):
        g,rows,select,observe,remove,verify,_,_=self.fixture();g.baseline['ce_range']=[5,6]
        with self.assertRaises(stable.NumericalStop):g.run(rows,select,observe,remove,verify)

    def test_04_reference_removal_required(self):
        g,rows,select,observe,remove,verify,_,_=self.fixture()
        with self.assertRaises(stable.NumericalStop):g.run(rows,select,observe,remove,lambda:False)

    def test_05_current_ceiling_formula(self):
        self.assertEqual(current.ceilings(.1)['mean_update_ce_ceiling'],10*math.log(4))
        self.assertEqual(current.ceilings(2)['mean_update_ce_ceiling'],40)
        self.assertEqual(current.ceilings(2)['microbatch_ce_ceiling'],160)
        for value in [float('nan'),float('inf'),-1]:
            with self.assertRaises(stable.NumericalStop):current.ceilings(value)

    def test_06_train_normalization_only(self):
        rows=[{'split':'train'} for _ in range(1792)]
        features=np.zeros((1792,3072),dtype=np.float32)
        mean,std=current.normalize(np,features,rows)
        np.testing.assert_array_equal(mean,np.zeros(3072,dtype=np.float32))
        np.testing.assert_array_equal(std,np.full(3072,1e-6,dtype=np.float32))
        rows[0]['split']='external_dev'
        with self.assertRaises(stable.NumericalStop):current.normalize(np,features,rows)

    def test_07_head_fit_frozen_configuration(self):
        text=(ROOT/'tools/auditor_classifier_lora_current_core.py').read_text()
        for value in ['range(1,201)','torch.optim.Adam(','lr=.01','betas=(.9,.999)','eps=1e-8','weight_decay=0','head.weight.zero_()','head.bias.zero_()']:
            self.assertIn(value,text)
        self.assertNotIn('stable.update0(',text)

    def test_08_remote_order_no_old_anchor(self):
        text=(ROOT/'tools/auditor_classifier_lora_current_remote.py').read_text()
        order=['extraction_begin=','mean_np,std_np=current.normalize','head=current.fit_head','receipt=fork.create_fork','parity.run(','opt=parity.optimizer']
        self.assertEqual([text.index(x) for x in order],sorted(text.index(x) for x in order))
        self.assertNotIn('spec[\'initialization_artifacts\']',text)
        tree=ast.parse(text)
        self.assertNotIn('generate',[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)])

    def test_09_bound_data_and_controls(self):
        d=ROOT/'tuning/auditor_classifier_lora_current_runtime'
        for p,h in c.read(d/'data_bindings.json').items():self.assertEqual(c.sha(ROOT/p),h)
        controls=c.read(d/'controls.json');self.assertEqual(len(controls['example_ids']),16)
        self.assertEqual(set(controls),{'example_ids','selection','rtol','atol'})
        self.assertEqual(c.read(d/'experiment.json')['training']['updates'],896)

    def test_10_optimizer_before_current_gates_denied(self):
        g,*_=self.fixture()
        with self.assertRaises(stable.NumericalStop):g.optimizer(None,None,None,None)


if __name__=='__main__':unittest.main()
