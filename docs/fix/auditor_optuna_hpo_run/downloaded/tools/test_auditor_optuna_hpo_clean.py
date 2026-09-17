"""Clean initialization provenance tests; fixtures contain no real model weights."""
import json
import sys
import unittest
from pathlib import Path
import numpy as np
import auditor_optuna_hpo as h
import clean_auditor_hpo_initialization as clean


class CleanTests(unittest.TestCase):
    def test_fit_population_and_exclusion(self):
        split=json.loads((clean.D/'split.json').read_bytes())
        assignments=split['assignments'];ids=[r['example_id'] for r in assignments]
        features=np.zeros((1792,3),dtype=np.float32)
        for i,r in enumerate(assignments):
            if r['split']=='inner_val':features[i]=np.nan
        x,y,fit_ids=clean.select_fit_inputs(features,ids,assignments)
        self.assertEqual(x.shape,(1432,3));self.assertEqual(len(y),1432)
        self.assertTrue(np.isfinite(x).all());self.assertEqual(np.bincount(y).tolist(),[358]*4)
        poisoned=[dict(r,relation='DO_NOT_READ') if r['split']=='inner_val' else r for r in assignments]
        xx,yy,ii=clean.select_fit_inputs(features,ids,poisoned)
        self.assertTrue(np.array_equal(x,xx));self.assertTrue(np.array_equal(y,yy));self.assertEqual(fit_ids,ii)

    def test_frozen_receipt(self):
        f=json.loads((clean.C/'FROZEN.json').read_bytes())
        self.assertEqual(len(f['fit_ids']),1432)
        self.assertEqual(f['initialization_inner_val_feature_contributions'],0)
        self.assertEqual(f['initialization_inner_val_label_contributions'],0)
        self.assertEqual(f['inner_val_gradient_rows'],0)
        self.assertEqual(f['head_spec'],clean.HEAD_SPEC)
        self.assertEqual(f['source_sha256'],h.sha(Path(clean.__file__)))

    def test_repeat_hashes(self):
        f=json.loads((clean.C/'FROZEN.json').read_bytes())
        for name,digest in f['artifacts'].items():
            self.assertEqual(h.sha(clean.C/name),digest)
            self.assertEqual(h.sha(clean.C/'repeat_verification'/name),digest)
        self.assertEqual(f['deterministic_repeats'],2);self.assertTrue(f['arrays_bitwise_equal'])

    def test_freeze_precedes_validation(self):
        r=json.loads((clean.C/'fit_receipt.json').read_bytes());events=[e['event'] for e in r['events']]
        self.assertLess(events.index('initialization_frozen'),events.index('inner_val_information_only_evaluation'))
        m=json.loads((clean.C/'starting_metrics.json').read_bytes())
        self.assertEqual(m['freeze_sha256'],h.sha(clean.C/'FROZEN.json'))
        self.assertFalse(m['artifacts_changed_after_validation'])

    def test_no_old_initializer(self):
        a=json.loads((clean.D/'artifacts.json').read_bytes())
        self.assertNotIn('head-200.safetensors',a);self.assertNotIn('mean.npy',a);self.assertNotIn('std.npy',a)
        for name in ['hpo_head-200.safetensors','hpo_mean.npy','hpo_std.npy']:
            self.assertIn('/clean_initialization/',a[name]['path'])
            self.assertEqual(a[name]['sha256'],h.ARTIFACT_HASHES[name])

    def test_final_training_population(self):
        m=dict(macro_f1=.8,minimum_class_recall=.6,ce=.3)
        winner=h.freeze_winner([dict(metrics=m,stable=True,updates=80,representation_drift=0.,params=dict(lora_peak_lr=1e-5,head_lr=1e-4,warmup_steps=10,dropout=0.),trial_number=0)])
        d=winner['future_separate_design']
        self.assertEqual(d['normalization_fit_rows'],1792);self.assertEqual(d['head_fit_rows'],1792)
        self.assertEqual(d['head_updates'],200);self.assertFalse(d['reuse_hpo_head']);self.assertTrue(d['clean_classifier_fork'])
        self.assertEqual(d['updates'],896);self.assertFalse(winner['full_training_auto_execute'])

    def test_no_initial_exposure_flags(self):
        self.assertFalse(h.config()['initial_head_exposed_to_inner_val'])
        self.assertFalse(h.config()['normalization_exposed_to_inner_val'])

    def test_fit_exact_recipe_and_trace(self):
        trace=json.loads((clean.C/'fit_trace.json').read_bytes())
        self.assertEqual([r['update'] for r in trace],list(range(1,201)))
        self.assertTrue(all(r['gradient_rows']==1432 for r in trace))
        self.assertEqual(clean.HEAD_SPEC['lr'],.01);self.assertEqual(clean.HEAD_SPEC['betas'],[.9,.999])
        self.assertEqual(clean.HEAD_SPEC['weight_decay'],0)

    def test_clean_access_receipt(self):
        r=json.loads((clean.C/'fit_receipt.json').read_bytes())
        self.assertEqual(r['access']['access_counts'],dict.fromkeys(h.FORBIDDEN,0))
        self.assertEqual(r['access']['denied_before_open'],0)
        self.assertFalse(r['backbone_loaded']);self.assertFalse(r['backbone_inference']);self.assertFalse(r['cloud'])
        self.assertNotIn('torch',sys.modules)

    def test_baseline_train_only(self):
        b=json.loads((clean.C/'inner_train_baseline.json').read_bytes())
        split=json.loads((clean.D/'split.json').read_bytes())
        expected={r['example_id'] for r in split['assignments'] if r['split']=='inner_train'}
        self.assertEqual(set(b['example_ids']),expected);self.assertEqual(len(b['predicted_indices']),1432)
        self.assertAlmostEqual(b['ce'],.06518124947326996)

    def test_normalization_recomputed_exactly_from_inner_train(self):
        f=json.loads((clean.C/'FROZEN.json').read_bytes())
        ids=[json.loads(line)['example_id'] for line in (clean.E/'current_train_features.jsonl').read_bytes().splitlines()]
        fit=set(f['fit_ids']);indices=[i for i,x in enumerate(ids) if x in fit]
        self.assertEqual(len(indices),1432)
        features=np.load(clean.E/'current_train_features.npy',mmap_mode='r',allow_pickle=False)
        x=features[indices]
        self.assertTrue(np.array_equal(x.mean(axis=0,dtype=np.float32),np.load(clean.C/'hpo_mean.npy',allow_pickle=False)))
        self.assertTrue(np.array_equal(np.maximum(x.std(axis=0,ddof=0,dtype=np.float32),np.float32(1e-6)),np.load(clean.C/'hpo_std.npy',allow_pickle=False)))

    def test_search_pruner_objective_unchanged(self):
        old=json.loads((clean.C/'unchanged_search.json').read_bytes())['previous_configuration']
        new=h.config()
        for key in old:
            if key not in ['initial_head_exposed_to_inner_val','normalization_exposed_to_inner_val']:
                self.assertEqual(old[key],new[key],key)

    def test_compatibility_baseline_ignores_inner_val_labels(self):
        rows=[dict(example_id=str(i),relation=h.CLASSES[i%4] if i<1432 else 'DO_NOT_READ') for i in range(1792)]
        features=np.zeros((1792,3),np.float32)
        baseline=dict(example_ids=[str(i) for i in range(1432)],predicted_indices=[0]*1432,ce_range=[1.38,1.39],metrics=dict(macro_f1=.1))
        gate=h.ReuseAdmission(np,features,np.zeros(3,np.float32),np.ones(3,np.float32),np.zeros((4,3),np.float32),np.zeros(4,np.float32),rows,[str(i) for i in range(16)],{},baseline)
        observe=lambda r:dict(hidden=np.zeros(3,np.float32),standardized=np.zeros(3,np.float32),logits=np.zeros(4,np.float32))
        receipt=gate.run({},observe,lambda x:None,lambda:None)
        self.assertEqual(receipt['rows'],1792)
        self.assertEqual(sum(map(sum,receipt['metrics']['confusion_matrix'])),1432)


if __name__=='__main__':unittest.main()
