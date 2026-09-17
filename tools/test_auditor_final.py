"""Local contract tests only: no cloud, model, data evaluation or training."""
import ast
import copy
import math
import unittest
from pathlib import Path
import auditor_final_core as f
import auditor_classifier_lora_core as c
import auditor_optuna_hpo as h


def metric(f1,rec):return dict(macro_f1=f1,minimum_class_recall=rec)


class FinalContracts(unittest.TestCase):
    def test_selected_values(self):
        saved=c.read(Path(__file__).resolve().parents[1]/'docs/fix/auditor_optuna_hpo_run/SELECTED_HYPERPARAMETERS.json')
        self.assertEqual(saved,f.PARAMS)

    def test_warmup(self):
        self.assertEqual(f.lr(1),f.PARAMS['lora_peak_lr']/10)
        self.assertEqual(f.lr(10),f.PARAMS['lora_peak_lr'])
        self.assertEqual(f.lr(896),f.PARAMS['lora_peak_lr'])
        for step in (0,897):
            with self.assertRaises(RuntimeError):f.lr(step)

    def test_two_complete_passes(self):
        ids=[str(i) for i in range(1792)];plan=c.schedule(ids)
        self.assertEqual(len(plan),896)
        for start in [0,448]:self.assertEqual(sorted(i for row in plan[start:start+448] for i in row['example_ids']),sorted(ids))

    def test_evaluation_gate(self):
        for step in [0,448,895]:
            with self.assertRaises(RuntimeError):f.admit_evaluation(dict(complete=True,updates=step,checkpoints=[448,896]))
        f.admit_evaluation(dict(complete=True,updates=896,checkpoints=[448,896]))
        with self.assertRaises(RuntimeError):f.admit_evaluation(dict(complete=False,updates=896,checkpoints=[448,896]))

    def test_data_boundary(self):
        b=f.Boundary(Path.cwd())
        for p in ['evaluation_payload/records.json','tuning/auditor_classifier_lora/records.json','x/challenges.json','data/holdout.json','protected/test.json','producer/adapter.safetensors','input/run.json','benchmark/key.json']:
            with self.assertRaises(PermissionError):b.check(p)
        b.check('tuning/auditor_final/records_train_only.json')
        e=f.Boundary(Path.cwd(),evaluation=True);e.check('evaluation_payload/records.json')
        for p in ['holdout/records.json','producer/weights','protected/test.json']:
            with self.assertRaises(PermissionError):e.check(p)
        self.assertEqual(e.receipt['successful_access_counts'],dict.fromkeys(f.FORBIDDEN,0))

    def test_numerical_ce_gate(self):
        gate=h.Stability(.01);gate.update([.1]*4)
        with self.assertRaises(h.Instability):gate.update([20]*4)
        with self.assertRaises(h.Instability):gate.micro(math.nan)

    def test_final_update_identical_except_bound(self):
        root=Path(__file__).resolve().parent
        def get(p,klass):
            tree=ast.parse((root/p).read_text());cl=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==klass)
            return ast.dump(next(n for n in cl.body if isinstance(n,ast.FunctionDef) and n.name=='update'),include_attributes=False)
        old=get('auditor_optuna_hpo_backend.py','TorchBackend').replace('value=80','value=896').replace('trial update contract','final update contract').replace('value=40','value=448')
        self.assertEqual(old,get('auditor_final_backend.py','FinalBackend'))

    def test_selection_does_not_reject_old_gate_failure(self):
        def row(step,hist,ext,passes=False):return dict(step=step,identity=dict(step=step),metrics=dict(historical=metric(hist,.4),external=metric(ext,.4),all_old_quality_gates_pass=passes))
        self.assertEqual(f.select([row(448,.5,.8),row(896,.6,.7)])['selected_step'],896)
        self.assertEqual(f.select([row(448,.5,.8,True),row(896,.6,.7)])['selected_step'],448)
        self.assertEqual(f.select([row(448,.6,.8),row(896,.6,.8)])['selected_step'],448)

    def test_scoring_and_applicability(self):
        rows=[dict(example_id=str(i),relation=k) for i,k in enumerate(c.CLASSES)]
        predictions=[dict(example_id=str(i),predicted=k,ce=.5) for i,k in enumerate(c.CLASSES)]
        m=f.score(rows,predictions);self.assertEqual(m['macro_f1'],1);self.assertEqual(m['minimum_class_recall'],1)
        self.assertEqual(m['mean_ce'],.5);self.assertIsNone(m['refusal_recall']);self.assertIsNone(m['evidence_f1'])
        predictions[2]['predicted']='MATCH';m=f.score(rows,predictions)
        self.assertEqual(m['classification_error_counts']['false_match'],1)
        self.assertEqual(m['classification_error_counts']['wrong_match_or_divergence'],1)
        self.assertIsNone(m['catastrophic']['confident_wrong_match_divergence'])

    def test_train_schema_excludes_metadata(self):
        rows=[dict(example_id=str(i),relation=c.CLASSES[i%4],split='train',input_ids=[1],prompt_sha256='x') for i in range(1792)]
        f.train_rows(rows);rows[0]['source']='forbidden metadata'
        with self.assertRaises(RuntimeError):f.train_rows(rows)


if __name__=='__main__':unittest.main()
