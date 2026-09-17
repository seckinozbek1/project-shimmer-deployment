"""No-model integration checks for the one-shot controller and sealed runtime."""
import ast
import unittest
from pathlib import Path
import auditor_classifier_lora_core as c

ROOT=Path(__file__).resolve().parents[1]


class Tests(unittest.TestCase):
    def test_01_authorization_and_scope(self):
        text=(ROOT/'tools/auditor_classifier_lora_stabilized_remote.py').read_text()
        self.assertIn('6234692b-4bf4-495e-952f-5d48d5219d6c',text)
        self.assertIn("permit['hard_budget_usd']==3.5",text)
        self.assertIn("permit['soft_budget_usd']==2.5",text)
        self.assertLess(text.index('parity=fork.remote_preflight'),text.index('opt=parity.optimizer'))
        self.assertIn('assert preflight_rows==1824',text)

    def test_02_no_generation(self):
        tree=ast.parse((ROOT/'tools/auditor_classifier_lora_stabilized_remote.py').read_text())
        self.assertNotIn('generate',[x.func.attr for x in ast.walk(tree) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)])

    def test_03_budget_and_single_launch(self):
        controller=(ROOT/'tools/auditor_classifier_lora_stabilized_cloud.py').read_text()
        self.assertIn("quantity=1",controller);self.assertIn("open('x') as lock",controller)
        self.assertIn("provider.request('instances')['data']==[]",controller)
        self.assertIn("TERMINATE_REQUEST",controller)
        prep=(ROOT/'tools/auditor_classifier_lora_stabilized_prepare.py').read_text()
        self.assertIn('workload_deadline_seconds=hard-600',prep);self.assertIn('watchdog_deadline_seconds=hard-120',prep)
        self.assertLess(140*60,3.5/1.29*3600)

    def test_04_schedule_and_numerical_gate(self):
        spec=c.read(ROOT/'tuning/auditor_classifier_lora_fork/experiment.json')
        self.assertEqual(spec['numerical_gate']['mean_update_ce_ceiling'],13.862943611198906)
        self.assertEqual(spec['training']['checkpoints'],[448,896])
        text=(ROOT/'tools/auditor_classifier_lora_stabilized_remote.py').read_text()
        self.assertIn('fork.prospective_update(',text);self.assertIn('if completed in (448,896):evaluate(completed)',text)
        self.assertNotIn('evaluate(20)',text)

    def test_05_selection_requires_complete(self):
        self.assertEqual(c.select([],896)['verdict'],'AUDITOR_CLASSIFIER_LORA_INDETERMINATE')
        self.assertEqual(c.select([],20)['verdict'],'AUDITOR_CLASSIFIER_LORA_INDETERMINATE')


if __name__=='__main__':unittest.main()
