"""Frozen model/telemetry checks. No model weights loaded and no network."""
import contextlib
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import final_models as frozen
import model_telemetry as telemetry


def arm_g_gate_tree(root=frozen.ROOT):
    """True only in arm G's gate tree on a rented machine: a git checkout the runner made itself
    (tools/ordinary_final_run.git_checkout), its own `.git` folder on branch `gate`, holding the
    runner's attributes file byte for byte (GATE_GIT_ATTRIBUTES, read from the runner's source,
    never retyped here). The laptop's main checkout and its worktrees are never this tree."""
    import ast
    git = Path(root) / '.git'
    runner = Path(root) / 'tools/ordinary_final_run.py'
    if not (git.is_dir() and runner.is_file()):
        return False
    try:
        head = (git / 'HEAD').read_text(encoding='utf8').strip()
        written = (git / 'info' / 'attributes').read_text(encoding='utf8')
    except OSError:
        return False
    declared = next((ast.literal_eval(node.value) for node in ast.parse(runner.read_text(encoding='utf8')).body
                     if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'GATE_GIT_ATTRIBUTES'
                                                             for t in node.targets)), None)
    return head == 'ref: refs/heads/gate' and declared is not None and written == declared


def frozen_weights_withheld():
    """True only in arm G's gate tree with NONE of the frozen weight files present. The weights
    (adapters, head, normalisation arrays) are gitignored evidence under docs/fix/, so a tree made
    from git's blobs holds none of them; only their JSON configs are tracked. Anywhere else, or
    with any weight present, every check runs on the real files and refuses as the runtime would."""
    weights = [frozen.ROOT / entry['path'] for role in ('producer', 'auditor')
               for entry in frozen.specification(role)['files'].values() if not entry['path'].endswith('.json')]
    return arm_g_gate_tree() and bool(weights) and not any(path.is_file() for path in weights)


def verify_tracked(role, root=frozen.ROOT):
    """final_models.verify on what a git-blob tree holds: the pins read from config/final_models.json
    (specification), each tracked JSON file present and at its pinned hash, and the adapter and its
    config in one folder (verify's own rule). Only the weight files' presence and hashes are not read."""
    spec = frozen.specification(role, root)
    paths = {}
    for key, entry in spec['files'].items():
        path = Path(root) / entry['path']
        if entry['path'].endswith('.json'):
            frozen.require(path.is_file(), 'Missing frozen ' + role + ' ' + key)
            frozen.require(frozen.sha(path) == entry['sha256'], 'Frozen hash mismatch: ' + role + ' ' + key)
        paths[key] = path
    frozen.require(paths['adapter'].parent == paths['adapter_config'].parent, 'Adapter/config directory mismatch')
    return spec, paths


def without_frozen_files():
    """In arm G's gate tree with the weights withheld, admission runs with verify_tracked in place
    of verify; everywhere else the real verify reads the real files."""
    if not frozen_weights_withheld():
        return contextlib.nullcontext()
    return patch.object(frozen, 'verify', verify_tracked)


def call(identifier, start, end, role='producer', parents=(), **kwargs):
    value = dict(event='model_call', call_id=identifier, agent=identifier, designation=role,
        wave_id='wave-'+identifier, task_id=identifier, start_monotonic_s=start, end_monotonic_s=end,
        total_service_seconds=end-start, parent_call_ids=list(parents), input_tokens=10,
        output_tokens=5, emitted_count=2, retained_count=None, contract_valid=True,
        backend_success=True, truncated=False, cap_hit=False)
    value.update(kwargs)
    return value


class IntegrationChecks(unittest.TestCase):
    def test_preserved_artifacts_match(self):
        # In arm G's gate tree the weights are withheld (gitignored); there the tracked configs,
        # the pins and the folder rule are still checked, and the weights' hashes are proven on
        # the laptop's main checkout, which holds them.
        check = verify_tracked if frozen_weights_withheld() else frozen.verify
        for role in ('producer','auditor'):
            spec, paths = check(role)
            self.assertEqual(set(paths), set(frozen.PINS[role]))
            self.assertEqual(spec['checkpoint'], 168 if role == 'producer' else 896)

    def test_modes_are_explicit(self):
        for mode in ('final','base'):
            with patch.dict(os.environ, SHIMMER_MODEL_MODE=mode):
                self.assertEqual(frozen.mode(), mode)
        with patch.dict(os.environ, SHIMMER_MODEL_MODE='trial11'):
            with self.assertRaises(RuntimeError): frozen.mode()

    def test_tuned_producer_uses_frozen_loader_without_base_fallback(self):
        import agent_wrapper
        w=object.__new__(agent_wrapper.AgentWrapper)
        w.backend='local_producer';w.name='PROCESSOR';w.run_context=None
        w.model=frozen.specification('producer')['model_id'];w.cost_tracker=None
        with patch.dict(os.environ,SHIMMER_MODEL_MODE='final'), \
             patch.object(agent_wrapper.importlib,'import_module',return_value=SimpleNamespace()), \
             patch.object(frozen,'resident',side_effect=RuntimeError('fixture admission refusal')) as selected, \
             patch.object(agent_wrapper,'_load_qwen',side_effect=AssertionError('Base fallback forbidden')):
            result=w.call_local('fixture')
        selected.assert_called_once_with('producer',None)
        self.assertFalse(result.ok)

    def test_missing_and_wrong_files_refuse_without_loading(self):
        for role in ('producer','auditor'):
            spec = frozen.specification(role)
            with tempfile.TemporaryDirectory() as folder:
                with patch.object(frozen, 'specification', return_value=spec):
                    with self.assertRaisesRegex(RuntimeError, 'Missing'): frozen.verify(role, folder)
                for item in spec['files'].values():
                    p=Path(folder)/item['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'wrong')
                with patch.object(frozen, 'specification', return_value=spec):
                    with self.assertRaisesRegex(RuntimeError, 'hash mismatch'): frozen.verify(role, folder)

    def test_mixed_checkpoint_hpo_and_448_refuse(self):
        original = json.loads((frozen.ROOT/'config/final_models.json').read_text(encoding='utf8'))
        changes = [('checkpoint',448),('checkpoint',120),('head','0'*64),('adapter','1'*64),('mean','2'*64),('std','3'*64)]
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'config/final_models.json';p.parent.mkdir()
            for key,value in changes:
                obj=copy.deepcopy(original)
                if key == 'checkpoint': obj['auditor'][key]=value
                else: obj['auditor']['files'][key]['sha256']=value
                p.write_text(json.dumps(obj),encoding='utf8')
                with self.assertRaises(RuntimeError): frozen.specification('auditor',folder)

    def test_wrong_producer_checkpoint_refuses(self):
        original = json.loads((frozen.ROOT/'config/final_models.json').read_text(encoding='utf8'))
        original['producer']['checkpoint']=84
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'config/final_models.json';p.parent.mkdir();p.write_text(json.dumps(original),encoding='utf8')
            with self.assertRaises(RuntimeError): frozen.specification('producer',folder)

    def test_parallel_serial_and_missing_dag(self):
        nodes=[dict(id='p',start=0,end=4,parents=[]),dict(id='other',start=0,end=2,parents=[]),
               dict(id='a',start=5,end=8,parents=['p','other'])]
        p=telemetry.critical_path(nodes)
        self.assertEqual(p['members'],['p','a']);self.assertEqual(p['service_seconds'],7)
        self.assertEqual(p['gap_seconds'],1);self.assertEqual(p['elapsed_seconds'],8)
        nodes[1].update(start=4,end=6,parents=['p']);nodes[2].update(start=7,end=10)
        p=telemetry.critical_path(nodes)
        self.assertEqual(p['members'],['p','other','a']);self.assertEqual(p['elapsed_seconds'],10)
        with self.assertRaises(ValueError): telemetry.critical_path([dict(id='a',start=0,end=1,parents=['missing'])])

    def test_overlap_and_handoff(self):
        summary=telemetry.summarize([call('p',0,4),call('q',0,3),call('a',5,8,'auditor',['p'])])
        self.assertEqual(summary['call_wall_union_seconds'],7)
        self.assertEqual(summary['service_totals'],dict(producer=7,auditor=3))
        self.assertEqual(summary['maximum_concurrency'],2)
        self.assertEqual(summary['handoffs'][0]['seconds'],1)

    def test_cost_seconds_to_hours_unknown_not_zero(self):
        row=dict(event='infrastructure_cost',provider='fixture',instance_type='fixture',hourly_rate=2,
                 active_start_epoch=0,active_end_epoch=900)
        result=telemetry.cost([row,dict(event='api_cost',estimated_cost=.1)])
        self.assertEqual(result['infrastructure_estimate'],.5)
        self.assertEqual(result['combined_estimate'],.6)
        self.assertIsNone(telemetry.cost([])['combined_estimate'])
        with self.assertRaises(ValueError): telemetry.cost([dict(row,active_end_epoch=-1)])

    def test_integrity_and_retention_are_distinct(self):
        raw=[call('a',0,1,truncated=True,cap_hit=True),
             call('b',1,2,contract_valid=False,failure_category='contract_invalid'),
             call('c',2,3,backend_success=False,contract_valid=None,failure_category='backend_failure'),
             dict(event='retention_snapshot',call_counts={'a':0,'b':0}),
             dict(event='retention_snapshot',call_counts={'a':1})]
        result=telemetry.summarize(raw)
        self.assertEqual(result['counts']['truncated'],1)
        self.assertEqual(result['counts']['contract_valid'],1)
        self.assertEqual(result['failed_calls'],2)
        self.assertEqual(result['retained']['value'],1)
        self.assertEqual(result['retained']['measured_calls'],2)
        self.assertEqual(result['emitted']['value'],6)

    def test_summary_is_recomputable(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'logs/model_telemetry.jsonl';p.parent.mkdir()
            p.write_text(json.dumps(call('a',0,1))+'\n',encoding='utf8')
            first=telemetry.recompute(folder)
            self.assertEqual(first,telemetry.recompute(folder))
            self.assertIsNone(first['pipeline_wall_seconds'])
            self.assertIsNone(first['semantic_critical_path'])

    def test_ordinary_final_admission_requires_valid_pair_contract(self):
        import auditor_pairs
        with patch.dict(os.environ,SHIMMER_MODEL_MODE='final'),patch.object(frozen,'verify_runtime'),without_frozen_files():
            frozen.admit_ordinary()
            with patch.object(auditor_pairs,'contract_self_check',return_value=False):
                with self.assertRaisesRegex(RuntimeError,'pairing contract'):
                    frozen.admit_ordinary()
        with patch.dict(os.environ,SHIMMER_MODEL_MODE='base'):
            frozen.admit_ordinary()

    def test_current_contract_does_not_establish_classifier_pairs(self):
        from compact_contract_checks import wrapper
        w=wrapper('VERIFIER')
        items=[dict(paragraph=i+1, finding=label, severity='low', reasoning='fixture reasoning',
                    ref='document-level',kind='finding',confidence='UNCERTAIN')
               for i,label in enumerate(['MATCH','OMISSION'])]
        parsed,missing=w.parse_contract_output(json.dumps(dict(agent='VERIFIER',doc_id='fixture',items=items)))
        self.assertEqual(missing,[])
        self.assertEqual([i['finding'] for i in parsed['items']],['MATCH','OMISSION'])
        self.assertTrue(all('original' not in i and 'output' not in i and 'ref_ids' not in i for i in parsed['items']))
        # One document-level relation cannot represent this accepted contract.
        self.assertEqual(len({i['finding'] for i in parsed['items']}),2)

    def test_unknown_metrics_stay_null(self):
        wrapper=SimpleNamespace(name='VERIFIER',backend='local_auditor',model='fixture',run_context=None,
                                _generation_usage={'backend_success':True},_observed_contract_valid=True)
        rows=[]
        with patch.object(telemetry,'emit',side_effect=lambda context,event,**fields:rows.append(fields)):
            telemetry.call_record(wrapper,dict(ok=True,parsed=dict(items=[])),0,'fixture')
        row=rows[0]
        self.assertIsNone(row['semantically_complete']);self.assertIsNone(row['retained_count'])
        self.assertIsNone(row['time_to_first_token_seconds']);self.assertIn('time_to_first_token_seconds',row['unavailable'])


if __name__ == '__main__':
    unittest.main()
