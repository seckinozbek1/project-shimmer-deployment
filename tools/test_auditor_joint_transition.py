"""Local algebra and preserved-evidence checks; no model or optimizer execution."""
import json
import unittest
import numpy as np
import analyze_auditor_joint_transition as a


class TransitionTests(unittest.TestCase):
    def test_delta_is_not_difference_of_norms(self):
        x={'w':np.array([1.,0.],dtype=np.float32)}
        y={'w':np.array([0.,1.],dtype=np.float32)}
        result=a.delta_group(x,y,1.)
        self.assertEqual(result['norm_change'],0.)
        self.assertAlmostEqual(result['delta_norm'],2**.5)

    def test_ce_bound(self):
        rng=np.random.default_rng(7)
        def ce(logits,y):
            m=logits.max()
            return m+np.log(np.exp(logits-m).sum())-logits[y]
        for _ in range(100):
            w=rng.normal(size=(4,19));b=rng.normal(size=4)
            dw=rng.normal(size=(4,19));db=rng.normal(size=4)
            z=rng.normal(size=19);y=int(rng.integers(4))
            change=abs(ce((w+dw)@z+b+db,y)-ce(w@z+b,y))
            self.assertLessEqual(change,a.ce_head_change_bound(dw,db,np.linalg.norm(z),y)+1e-12)

    def test_first_step_clipping_is_not_parameter_trust_region(self):
        g=np.array([.01,-.02]);clipped=.27*g;eps=1e-8;lr=1e-4
        delta=lr*clipped/(np.abs(clipped)+eps)
        self.assertTrue(np.all(np.abs(delta)>.999*lr))
        self.assertGreater(np.linalg.norm(delta),100*np.linalg.norm(lr*clipped))

    def test_saved_input_bindings_and_findings(self):
        result=json.loads((a.OUT/'results.json').read_text())
        for path,digest in result['bindings'].items():
            self.assertEqual(a.c.sha(a.ROOT/path),digest,path)
        self.assertFalse(result['torch_imported'])
        self.assertEqual(result['normalization']['counts']['1e-06'],0)
        self.assertGreater(result['counterfactual']['old_head_ce_on_actual_post_z_lower_bound'],120)
        self.assertEqual(result['verdict'],'AUDITOR_JOINT_TRAINING_STABILIZATION_UNISOLATED')


if __name__=='__main__':unittest.main()
