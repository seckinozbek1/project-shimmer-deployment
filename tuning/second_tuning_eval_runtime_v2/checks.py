"""Deterministic local effect proofs. No model loading or real generation."""
import ast
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import eval_runtime as runtime
import audit
import protocol_builder as prepare


class Parameter:
    dtype = 'float32'
    device = 'cpu'
    requires_grad = True
    _version = 0


class Model:
    """No neural network: a state/sequence stand-in returning fixed token IDs."""
    def __init__(self):
        self.training = True
        self.gradient_checkpointing = True
        self._gradient_checkpointing_func = object()
        self.config = SimpleNamespace(use_cache=False, other='unchanged')
        self.generation_config = SimpleNamespace(use_cache=False, do_sample=True)
        self.child = SimpleNamespace(training=False, gradient_checkpointing=True)
        self.active_adapters = ['default']
        self.parameter = Parameter()
        self.device = 'cpu'
        self.calls = []
        self.failure = None

    def modules(self):
        return [self, self.child]

    def parameters(self):
        return [self.parameter]

    def eval(self):
        for module in self.modules():
            module.training = False
        return self

    def generate(self, **kwargs):
        self.calls.append(dict(kwargs=deepcopy(kwargs), training=self.training,
                               grad=TorchFacade.grad_enabled, inference=TorchFacade.inference_enabled,
                               checkpointing=self.gradient_checkpointing,
                               cache=self.config.use_cache, traced=sys.gettrace() is not None))
        if self.failure:
            raise self.failure
        return TensorStandin([kwargs['input_ids'].values[0] + [11, 151645]])


class TensorStandin:
    def __init__(self, values):
        self.values = deepcopy(values)

    def to(self, device):
        return self

    def __getitem__(self, index):
        row, section = index
        return SimpleNamespace(tolist=lambda: self.values[row][section])


class TorchFacade:
    grad_enabled = True
    inference_enabled = False

    def __init__(self):
        self.tensor = lambda values, dtype: TensorStandin(values)
        self.long = 'int64'
        self.syncs = 0
        self.cuda = SimpleNamespace(synchronize=self.sync, memory_allocated=lambda: 100,
                                    memory_reserved=lambda: 200, max_memory_allocated=lambda: 150,
                                    max_memory_reserved=lambda: 250)

    def sync(self):
        self.syncs += 1

    @staticmethod
    def is_grad_enabled():
        return TorchFacade.grad_enabled

    @staticmethod
    @contextmanager
    def inference_mode():
        prior = TorchFacade.grad_enabled, TorchFacade.inference_enabled
        TorchFacade.grad_enabled, TorchFacade.inference_enabled = False, True
        try:
            yield
        finally:
            TorchFacade.grad_enabled, TorchFacade.inference_enabled = prior


class Sink:
    def __init__(self):
        self.rows = []

    def append(self, item):
        self.rows.append(deepcopy(item))


class RuntimeChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol = json.loads((HERE / 'protocol.json').read_text())
        cls.records = json.loads((HERE / 'prepared_dev.json').read_text())
        cls.results = json.loads((HERE / 'audit_results.json').read_text())

    def state(self, model):
        return ([(m.training, m.gradient_checkpointing) for m in model.modules()],
                deepcopy(vars(model.config)), deepcopy(vars(model.generation_config)),
                runtime.parameter_state(model), list(model.active_adapters))

    def invoke(self, model=None, sink=None, score=None, records=None):
        model = model or Model()
        torch = TorchFacade()
        sink = sink or Sink()
        score = score or (lambda *args: {'contract_valid': True})
        result = runtime.evaluate_records(model, SimpleNamespace(decode=lambda ids, **kw: '{"items":[]}'), torch,
                                          records or self.records[:1], self.protocol, sink, score)
        return model, torch, sink, result

    def test_01_historical_files_preserved(self):
        # Explicit byte verification outside weight-denying tokenizer dry-run.
        for name, expected in json.loads((HERE / 'historical_preservation.json').read_text()).items():
            self.assertEqual(prepare.filehash(ROOT / name), expected, name)

    def test_02_adapter_binding(self):
        p = audit.PILOT / 'downloaded/runs/second-domain-agnostic-v2/canonical/producer/checkpoint-120'
        for name, value in self.protocol['adapter']['files'].items():
            self.assertEqual(prepare.filehash(p / name), value)

    def test_03_dev_population_order(self):
        runtime.validate_records(self.records, self.protocol)
        for rows in (self.records[:-1], list(reversed(self.records)), self.records + self.records[:1]):
            with self.assertRaises(ValueError):
                runtime.validate_records(rows, self.protocol)

    def test_04_prompt_mutation_denied(self):
        rows = deepcopy(self.records)
        rows[0]['prompt'] += ' changed'
        with self.assertRaises(ValueError):
            runtime.validate_records(rows, self.protocol)

    def test_05_token_mutation_denied(self):
        rows = deepcopy(self.records)
        rows[0]['input_ids'][0] += 1
        with self.assertRaises(ValueError):
            runtime.validate_records(rows, self.protocol)

    def test_06_generation_identity(self):
        frozen = json.loads((audit.FROZEN / 'producer/experiment.json').read_text())
        self.assertEqual(self.protocol['generation_kwargs'], dict(frozen['generation'], eos_token_id=frozen['terminal_token_ids'], pad_token_id=151654))
        for name, value in [('use_cache', False), ('max_new_tokens', 200), ('do_sample', True), ('output_scores', True)]:
            changed = dict(self.protocol['generation_kwargs'], **{name: value})
            with self.assertRaises(ValueError):
                runtime.validate_generation(changed, self.protocol)

    def test_07_normal_restoration(self):
        model = Model(); before = self.state(model)
        self.invoke(model)
        self.assertEqual(self.state(model), before)

    def test_08_exception_restoration(self):
        model = Model(); before = self.state(model); model.failure = RuntimeError('injected')
        with self.assertRaises(RuntimeError):
            self.invoke(model)
        self.assertEqual(self.state(model), before)

    def test_09_early_termination_restoration(self):
        model = Model(); before = self.state(model)
        with self.assertRaises(KeyboardInterrupt):
            with runtime.evaluation_state(model, TorchFacade()):
                raise KeyboardInterrupt()
        self.assertEqual(self.state(model), before)

    def test_10_inference_effect(self):
        model, _, _, _ = self.invoke()
        observation = model.calls[0]
        self.assertFalse(observation['grad'])
        self.assertTrue(observation['inference'])
        self.assertFalse(observation['training'])
        self.assertTrue(TorchFacade.grad_enabled)

    def test_11_cache_lifecycle(self):
        model = Model()
        with runtime.evaluation_state(model, TorchFacade()):
            self.assertTrue(model.config.use_cache)
            self.assertTrue(model.generation_config.use_cache)
        self.assertFalse(model.config.use_cache)
        self.assertFalse(model.generation_config.use_cache)

    def test_12_checkpoint_flags_kept_inactive_then_restored(self):
        model = Model(); function = model._gradient_checkpointing_func
        with runtime.evaluation_state(model, TorchFacade()):
            self.assertTrue(model.gradient_checkpointing)
            self.assertFalse(model.gradient_checkpointing and model.training)
        self.assertTrue(model.gradient_checkpointing and model.training)
        self.assertIs(model._gradient_checkpointing_func, function)

    def test_13_shared_config_identity_restoration(self):
        model = Model(); original = model.generation_config
        model.child.generation_config = original
        with runtime.evaluation_state(model, TorchFacade()):
            model.child.generation_config = SimpleNamespace(use_cache=False)
        self.assertIs(model.generation_config, original)
        self.assertIs(model.child.generation_config, original)

    def test_14_raw_precedes_scoring(self):
        sink = Sink()
        def score(*args):
            self.assertEqual(len(sink.rows), 1)
            self.assertNotIn('metrics', sink.rows[0])
            return {'contract_valid': True}
        self.invoke(sink=sink, score=score)

    def test_15_raw_survives_scoring_error(self):
        sink = Sink()
        def score(*args):
            raise RuntimeError('score error')
        with self.assertRaises(RuntimeError):
            self.invoke(sink=sink, score=score)
        self.assertEqual(len(sink.rows), 1)

    def test_16_no_global_trace_in_optimized_path(self):
        model, _, _, _ = self.invoke()
        self.assertFalse(model.calls[0]['traced'])
        previous = sys.gettrace()
        try:
            sys.settrace(lambda *args: None)
            with self.assertRaises(ValueError):
                self.invoke()
        finally:
            sys.settrace(previous)

    def test_17_boundary_sync_count(self):
        _, torch, _, _ = self.invoke(records=self.records[:2])
        self.assertEqual(torch.syncs, 4)

    def test_18_durable_single_row(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            path = Path(folder) / 'rows.jsonl'
            sink = runtime.DurableRows(path)
            try:
                sink.append({'raw_output': 'unchanged', 'output_token_ids': [1, 2]})
                self.assertEqual(json.loads(path.read_text())['raw_output'], 'unchanged')
            finally:
                sink.close()
            with self.assertRaises(FileExistsError):
                runtime.DurableRows(path)

    def test_19_quantiles(self):
        x = audit.distribution([10, 20, 30, 40])
        self.assertEqual(x['median'], 25)
        self.assertAlmostEqual(x['p95'], 38.5)
        self.assertIsNone(audit.distribution([])['mean'])

    def test_20_efficiency_exact_counts(self):
        score = {key: dict(tp=n, fp=0, fn=1) for n, key in enumerate(audit.FIELDS.values(), 1)}
        score.update(contract_valid=True, accepted_outcome=False)
        value = audit.efficiency(score, 20)
        self.assertEqual(value['correct_atoms']['all'], 10)
        self.assertEqual(value['per_output_token']['all'], .5)
        self.assertFalse(value['accepted'])

    def test_21_refusal_not_rewarded_as_content_atom(self):
        score = {key: dict(tp=0, fp=0, fn=3) for key in audit.FIELDS.values()}
        score.update(contract_valid=True, accepted_outcome=False)
        self.assertEqual(audit.efficiency(score, 10)['per_output_token']['all'], 0)
        with self.assertRaises(ValueError):
            audit.efficiency(score, 0)

    def test_22_trailing_prose(self):
        value = audit.decorations('{"items":[]} finished')
        self.assertTrue(value['json_followed_by_prose'])
        self.assertTrue(value['commentary_after_json'])

    def test_23_second_json(self):
        value = audit.decorations('{"items":[]} {"items":[]}')
        self.assertTrue(value['json_followed_by_second_json'])
        self.assertFalse(value['json_followed_by_prose'])

    def test_24_fences_and_prefix(self):
        for text in ('```json\n{"items":[]}\n```', 'Result: {"items":[]}'):
            self.assertTrue(audit.decorations(text)['commentary_before_json'])
        self.assertTrue(audit.decorations('```json\n{}\n```')['code_fence'])
        self.assertFalse(any(audit.decorations('{"items":[]}').values()))

    def test_25_duplicate_exact_and_canonical(self):
        a = dict(category='missing_information', subject='entry', attribute='recorder', ordinal=None, relation=None, state='unspecified', scope='owned_record', unit=None)
        x = 'Gap: ' + json.dumps(a)
        y = 'Gap: ' + json.dumps(a, sort_keys=True, separators=(',', ':'))
        obj = {'items': [{'span': 's0', 'claims': ['CLM-1', 'CLM-1'], 'questions': [x, y], 'refs': ['REF-1', 'REF-1'], 'uncertainty': []}]}
        d = audit.duplicates(obj)
        self.assertEqual(d['claims']['exact'], 1)
        self.assertEqual(d['questions']['exact'], 0)
        self.assertEqual(d['questions']['canonical_additional'], 1)
        self.assertEqual(d['refs']['exact'], 1)

    def test_26_different_span_not_duplicate(self):
        self.assertEqual(audit.duplicates({'items': [{'span': 's0', 'claims': ['A']}, {'span': 's1', 'claims': ['A']}]})['claims']['exact'], 0)

    def test_27_paired_only_shared_prefix(self):
        pairs = self.results['paired_PARTIAL_PREFIX_ONLY']
        self.assertEqual(pairs['count'], 42)
        self.assertEqual([x['example_id'] for x in pairs['pairs']], self.protocol['dev_ids'][:42])
        self.assertTrue(all(x['scope'] == 'PARTIAL_PREFIX_ONLY' for x in pairs['pairs']))

    def test_28_saved_output_counts(self):
        self.assertEqual(self.results['checkpoint60']['output_tokens']['mean'], 1787 / 60)
        self.assertEqual(self.results['checkpoint120_PARTIAL_PREFIX_ONLY']['output_tokens']['mean'], 5945 / 42)
        self.assertEqual(self.results['checkpoint60']['accepted_output_token_cost']['n'], 12)

    def test_29_authorization_fail_closed(self):
        with self.assertRaises(ValueError):
            runtime.authorize({}, self.protocol, 'release')
        valid = dict(operator_authorized=True, experiment='second-tuning-eval-runtime-v2', action='producer-checkpoint120-evaluation-only', role='producer', split='canonical', checkpoint=120, runtime_release_sha256='release', protocol_sha256=runtime.digest(self.protocol), adapter_sha256=self.protocol['adapter']['files']['adapter_model.safetensors'])
        runtime.authorize(valid, self.protocol, 'release')
        for name, value in [('role', 'auditor'), ('split', '1'), ('training', True), ('protected_access', True), ('adapter_sha256', 'wrong')]:
            with self.assertRaises(ValueError):
                runtime.authorize(dict(valid, **{name: value}), self.protocol, 'release')

    def test_30_auditor_and_fold_effect_denial(self):
        for key, value in [('role', 'auditor'), ('split', '1')]:
            rows = deepcopy(self.records[:1]); rows[0][key] = value
            model = Model()
            with self.assertRaises(ValueError):
                self.invoke(model=model, records=rows)
            self.assertEqual(model.calls, [])

    def control_rows(self, seconds):
        return [dict(example_id=i, output_token_ids=[11, 151645], generation_seconds=seconds, metrics={'contract_valid': True}, prompt_sha256=self.protocol['prompt_bindings'][i]['prompt_sha256'], input_ids_sha256=self.protocol['prompt_bindings'][i]['input_ids_sha256'], adapter=self.protocol['adapter'], checkpoint=120) for i in self.protocol['control_ids']]

    def test_31_speed_gate_pass_and_failure(self):
        ref, fast = self.control_rows(1), self.control_rows(.2)
        self.assertTrue(runtime.control_gate(ref, fast, self.protocol)['pass_gate'])
        self.assertFalse(runtime.control_gate(ref, self.control_rows(.5), self.protocol)['pass_gate'])
        changed = deepcopy(fast); changed[0]['output_token_ids'][0] += 1
        self.assertFalse(runtime.control_gate(ref, changed, self.protocol)['pass_gate'])
        changed = deepcopy(fast); changed[0]['metrics']['contract_valid'] = False
        self.assertFalse(runtime.control_gate(ref, changed, self.protocol)['pass_gate'])

    def test_32_missing_control_denied(self):
        with self.assertRaises(ValueError):
            runtime.control_gate(self.control_rows(1)[:-1], self.control_rows(.2), self.protocol)
        session = self.session()
        session.admit_cache(self.cache_observations())
        with self.assertRaises(ValueError):
            session.admit_control(self.control_rows(1)[:-1], self.control_rows(.2))
        with self.assertRaisesRegex(ValueError, 'No repeated control'):
            session.admit_control(self.control_rows(1), self.control_rows(.2))

    def test_33_exact_historical_trace_reaches_foreign_calls(self):
        callback, _ = audit.historical_trace_callback(); hits = []
        def tracked(frame, event, arg):
            if frame.f_code.co_name == 'foreign_leaf':
                hits.append(event)
            return callback(frame, event, arg)
        def foreign_leaf():
            return 7
        try:
            sys.settrace(tracked)
            self.assertEqual(foreign_leaf(), 7)
        finally:
            sys.settrace(None)
        self.assertEqual(hits, ['call'])

    def test_34_pinned_qwen_cache_branches_effect(self):
        path = Path(importlib.metadata.distribution('transformers').locate_file('transformers/models/qwen2/modeling_qwen2.py'))
        spec = json.loads((audit.FROZEN / 'producer/experiment.json').read_text())
        self.assertEqual(prepare.filehash(path), spec['architecture']['source_sha256'])
        module = ast.parse(path.read_text())
        cls = next(x for x in module.body if isinstance(x, ast.ClassDef) and x.name == 'Qwen2Model')
        forward = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == 'forward')
        guards = [x for x in forward.body if isinstance(x, ast.If) and ast.unparse(x.test) in ('self.gradient_checkpointing and self.training and use_cache', 'use_cache and past_key_values is None')]
        self.assertEqual(len(guards), 2)
        fn = ast.parse('def effect(self, use_cache, past_key_values):\n pass').body[0]
        fn.body = guards + [ast.Return(ast.Tuple(elts=[ast.Name('use_cache', ast.Load()), ast.Name('past_key_values', ast.Load())], ctx=ast.Load()))]
        namespace = dict(DynamicCache=lambda: 'created_cache', logger=SimpleNamespace(warning_once=lambda *a: None))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), '<pinned-qwen-cache-guards>', 'exec'), namespace)
        self.assertEqual(namespace['effect'](SimpleNamespace(training=False, gradient_checkpointing=True), True, None), (True, 'created_cache'))
        self.assertEqual(namespace['effect'](SimpleNamespace(training=True, gradient_checkpointing=True), True, None), (False, None))

    def boundary_attempt(self, statement):
        code = f"import sys; from pathlib import Path; sys.path.insert(0,{str(HERE)!r}); from boundary import install; install({str(ROOT)!r});\ntry:\n {statement}\nexcept PermissionError:\n print('DENIED')\nelse:\n raise SystemExit('boundary failed')"
        value = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
        self.assertEqual(value.returncode, 0, value.stderr)
        self.assertEqual(value.stdout.strip(), 'DENIED')

    def test_35_protected_read_denial(self):
        self.boundary_attempt(f"Path({str(ROOT / 'benchmark/task_semantics/seed.json')!r}).read_bytes()")

    def test_36_auditor_read_denial(self):
        self.boundary_attempt(f"Path({str(audit.FROZEN / 'auditor/dev.json')!r}).read_bytes()")

    def test_37_weight_open_denial(self):
        self.boundary_attempt(f"Path({str(audit.PILOT / 'downloaded/runs/second-domain-agnostic-v2/canonical/producer/checkpoint-120/adapter_model.safetensors')!r}).read_bytes()")

    def test_38_network_denial(self):
        self.boundary_attempt("__import__('socket').getaddrinfo('localhost',80)")

    def test_39_historical_write_denial(self):
        self.boundary_attempt(f"Path({str(audit.PILOT / 'RECOMPUTED_RESULTS.json')!r}).open('w')")

    def test_40_telemetry_separate_process(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            path = Path(folder); output = path / 'telemetry.jsonl'; stop = path / 'stop'
            worker = subprocess.Popen([sys.executable, '-B', str(HERE / 'telemetry_worker.py'), '--pid', str(os.getpid()), '--output', str(output), '--stop-file', str(stop), '--cpu-only'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + 10
                while not output.exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertNotEqual(worker.pid, os.getpid())
                model, _, _, _ = self.invoke()
                self.assertEqual(len(model.calls), 1)
                stop.touch()
                _, error = worker.communicate(timeout=5)
                self.assertEqual(worker.returncode, 0, error)
                self.assertTrue(output.read_text().strip())
            finally:
                if worker.poll() is None:
                    stop.touch()
                    worker.communicate(timeout=5)

    def test_41_saved_historical_metric_equality(self):
        recorded = json.loads((audit.PILOT / 'downloaded/runs/second-domain-agnostic-v2/canonical/producer/validation-60.json').read_text())
        by_id = {x['example_id']: x for x in self.results['rows60']}
        for row in recorded:
            current = by_id[row['example_id']]
            self.assertEqual(current['contract_valid'], row['metrics']['contract_valid'])
            self.assertEqual(current['accepted'], row['metrics']['accepted_outcome'])
            for key in audit.FIELDS.values():
                self.assertEqual(current['efficiency']['correct_atoms'][key], row['metrics'][key]['tp'])

    def test_42_cache_kwarg_reaches_standin(self):
        model, _, _, _ = self.invoke()
        self.assertTrue(model.calls[0]['kwargs']['use_cache'])
        self.assertEqual(model.calls[0]['kwargs']['max_new_tokens'], 288)

    def cache_observations(self):
        rows = [dict(use_cache=True, training=False, grad_enabled=False, input_length=20, incoming_cache_length=0, returned_cache_length=20), dict(use_cache=True, training=False, grad_enabled=False, input_length=1, incoming_cache_length=20, returned_cache_length=21)]
        return dict(reference=deepcopy(rows), optimized=deepcopy(rows))

    def session(self):
        permit = dict(operator_authorized=True, experiment='second-tuning-eval-runtime-v2', action='producer-checkpoint120-evaluation-only', role='producer', split='canonical', checkpoint=120, runtime_release_sha256='test-only-release', protocol_sha256=runtime.digest(self.protocol), adapter_sha256=self.protocol['adapter']['files']['adapter_model.safetensors'])
        return runtime.EvaluationSession(permit, self.protocol, 'test-only-release')

    def test_43_cache_observation_failure_is_no_go(self):
        self.assertTrue(runtime.cache_effect_gate(self.cache_observations()))
        for field, value in [('use_cache', False), ('training', True), ('grad_enabled', True), ('returned_cache_length', 0)]:
            observations = self.cache_observations(); observations['optimized'][0][field] = value
            with self.assertRaises(ValueError):
                runtime.cache_effect_gate(observations)

    def test_44_session_cannot_generate_without_controls(self):
        session = self.session(); model = Model()
        with self.assertRaises(ValueError):
            session.complete_dev(model, None, TorchFacade(), self.records, Sink(), None)
        self.assertEqual(model.calls, [])

    def test_45_session_denies_stitching_and_resume(self):
        session = self.session(); session.admit_cache(self.cache_observations())
        session.admit_control(self.control_rows(1), self.control_rows(.2))
        model = Model()
        with self.assertRaises(ValueError):
            session.complete_dev(model, None, TorchFacade(), self.records[42:], Sink(), None)
        self.assertEqual(model.calls, [])
        session.full_used = True
        with self.assertRaises(ValueError):
            session.complete_dev(model, None, TorchFacade(), self.records, Sink(), None)

    def test_46_session_denies_protocol_drift(self):
        session = self.session(); session.admit_cache(self.cache_observations())
        session.admit_control(self.control_rows(1), self.control_rows(.2))
        session.protocol['generation_kwargs']['max_new_tokens'] = 100
        with self.assertRaises(ValueError):
            session.complete_dev(Model(), None, TorchFacade(), self.records, Sink(), None)

    def test_47_controls_require_actual_bound_identity(self):
        changed = self.control_rows(.2); changed[0]['checkpoint'] = 60
        with self.assertRaises(ValueError):
            runtime.control_gate(self.control_rows(1), changed, self.protocol)

    def test_48_cache_hooks_removed_on_exception(self):
        removed = []
        target = SimpleNamespace(register_forward_pre_hook=lambda *a, **k: SimpleNamespace(remove=lambda: removed.append('pre')), register_forward_hook=lambda *a, **k: SimpleNamespace(remove=lambda: removed.append('post')))
        model = SimpleNamespace(get_base_model=lambda: SimpleNamespace(model=target))
        with self.assertRaises(RuntimeError):
            with runtime.cache_probe(model, TorchFacade()):
                raise RuntimeError('injected')
        self.assertEqual(removed, ['post', 'pre'])

    def test_49_cache_probe_observes_real_hook_arguments(self):
        hooks = {}; removed = []
        def register(name, callback):
            hooks[name] = callback
            return SimpleNamespace(remove=lambda: removed.append(name))
        target = SimpleNamespace(training=False, register_forward_pre_hook=lambda callback, **k: register('pre', callback), register_forward_hook=lambda callback, **k: register('post', callback))
        model = SimpleNamespace(get_base_model=lambda: SimpleNamespace(model=target))
        with TorchFacade.inference_mode():
            with runtime.cache_probe(model, TorchFacade()) as observations:
                cache = SimpleNamespace(get_seq_length=lambda: 0)
                kwargs = dict(input_ids=SimpleNamespace(shape=(1, 20)), use_cache=True, past_key_values=cache)
                hooks['pre'](target, (), kwargs)
                cache.get_seq_length = lambda: 20
                hooks['post'](target, (), kwargs, SimpleNamespace(past_key_values=cache))
                kwargs['input_ids'] = SimpleNamespace(shape=(1, 1))
                hooks['pre'](target, (), kwargs)
                cache.get_seq_length = lambda: 21
                hooks['post'](target, (), kwargs, SimpleNamespace(past_key_values=cache))
        self.assertTrue(runtime.cache_effect_gate(dict(reference=observations, optimized=observations)))
        self.assertEqual(removed, ['post', 'pre'])

    def test_50_memory_counters_preserved_outside_timer(self):
        _, _, sink, _ = self.invoke()
        self.assertEqual(sink.rows[0]['cuda_memory_after']['max_memory_allocated'], 150)
        self.assertEqual(sink.rows[0]['cuda_memory_before']['memory_reserved'], 200)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeChecks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    summary = dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                   passed=result.wasSuccessful(), real_model_generations=0, training_updates=0,
                   effect_proofs='Executed mock training/cache/inference lifecycle, exact pinned Qwen cache-guard AST, actual historical callback on foreign frames, filesystem/network denial, separate telemetry process and raw-before-score persistence',
                   limitation='Local Torch import aborts with Anaconda duplicate OpenMP runtime; no unsafe override used. Inference lifecycle uses an explicit stand-in. No real model/GPU token-equivalence or throughput proof; future pinned-runtime preflight and control gate remain mandatory')
    (HERE / 'test_results.json').write_text(json.dumps(summary, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
