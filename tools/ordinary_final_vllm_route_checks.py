"""Proofs of the vLLM route's sealed switch (D-630 part A, A3): the sealer's block and environment
(tools/prepare_ordinary_final_run.py), the auxiliary lock's admission, and the runner's admission and
the Python it hands the route (tools/ordinary_final_run.py). Each rule is proven by neutralise, fail,
restore, pass (NEUTRALIZATIONS). Fixtures only.

    py -3.12 -X utf8 tools/ordinary_final_vllm_route_checks.py
"""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / 'tools'), str(ROOT / 'scripts')):
    if _path not in sys.path:
        sys.path.insert(0, _path)
import ordinary_final_run as runner  # noqa: E402
import prepare_ordinary_final_run as sealer  # noqa: E402

REGISTRY = json.loads((ROOT / 'config' / 'agent_registry.json').read_text(encoding='utf-8'))
ROUTE = dict(agents=['VERIFIER'], memory_share=0.55, max_model_len=28672)


def manifest(arm_block=True, **environment):
    block, env = sealer.vllm_route_block(ROUTE, REGISTRY)
    found = {'environment': dict({'SHIMMER_MODEL_MODE': 'final'}, **env), 'aux_env': {'lock': 'aux_env.lock'}}
    if arm_block:
        found['vllm_route'] = block
    found['environment'].update(environment)
    return found


class VllmRouteChecks(unittest.TestCase):
    def test_the_sealer_writes_one_block_and_its_two_switch_values(self):
        block, env = sealer.vllm_route_block(ROUTE, REGISTRY)
        self.assertEqual(block['agents'], ['VERIFIER'])
        self.assertEqual(block['job'], dict(dtype='float16', max_model_len=28672, gpu_memory_utilization=0.55,
                                            batch=1, batch_invariant=True, request_seconds=600))
        self.assertEqual(env['SHIMMER_VLLM_AGENTS'], 'VERIFIER')
        self.assertEqual(json.loads(env['SHIMMER_VLLM_JOB']), block['job'])

    def test_the_sealer_refuses_an_agent_the_route_does_not_serve(self):
        for agents, words in ((['PROCESSOR'], 'not one'), (['NO_SUCH_AGENT'], 'not one'),
                              (['JUDGE'], 'declared envelope agents only'),
                              (['VERIFIER', 'VERIFIER'], 'each agent once'), ([], 'each agent once')):
            with self.subTest(agents=agents):
                with self.assertRaises(Exception) as caught:
                    sealer.vllm_route_block(dict(ROUTE, agents=agents), REGISTRY)
                self.assertIn(words, str(caught.exception))
        for share in (0.05, 0.95, 1):
            with self.subTest(share=share), self.assertRaises(Exception):
                sealer.vllm_route_block(dict(ROUTE, memory_share=share), REGISTRY)

    def test_the_route_needs_a_lock_that_pins_vllm_and_its_flags_need_the_route(self):
        self.assertTrue(sealer.aux_lock_pins_vllm((ROOT / 'benchmark/baselines/vllm_aux.lock').read_bytes()))
        self.assertFalse(sealer.aux_lock_pins_vllm(b'torch==2.14.0 --hash=sha256:' + b'a' * 64 + bytes([10])))
        from types import SimpleNamespace as NS
        self.assertIsNone(sealer.vllm_route_args(NS(vllm_agents=None, vllm_memory_share=None, vllm_max_model_len=None)))
        for share, length in ((0.6, None), (None, 4096)):
            with self.subTest(share=share, length=length), self.assertRaises(Exception) as caught:
                sealer.vllm_route_args(NS(vllm_agents=None, vllm_memory_share=share, vllm_max_model_len=length))
            self.assertIn('only with --vllm-agents', str(caught.exception))
        self.assertEqual(sealer.vllm_route_args(NS(vllm_agents='VERIFIER', vllm_memory_share=None, vllm_max_model_len=None)),
                         dict(agents=['VERIFIER'], memory_share=0.7, max_model_len=28672))

    def test_an_aux_lock_goes_with_a_route_in_an_exposed_b3_bundle_only(self):
        lock = Path('aux.lock')
        self.assertTrue(sealer.aux_lock_admitted(lock, 'B3', False, None, ROUTE))
        self.assertFalse(sealer.aux_lock_admitted(None, 'B3', False, None, ROUTE))     # a route needs its lock
        self.assertFalse(sealer.aux_lock_admitted(lock, 'B3', True, None, ROUTE))      # never sealed
        self.assertFalse(sealer.aux_lock_admitted(lock, 'B1', False, None, ROUTE))     # never B1
        self.assertFalse(sealer.aux_lock_admitted(lock, 'B3', False, None, None))      # a lock alone, as before
        self.assertTrue(sealer.aux_lock_admitted(None, 'B3', False, None, None))       # neither, as before

    def test_the_runner_admits_the_route_only_as_sealed(self):
        self.assertIsNone(runner.vllm_route_error(manifest(), 'B3', 'exposed'))
        self.assertIsNone(runner.vllm_route_error({'environment': {}}, 'B3', 'exposed'))
        cases = (
            (manifest(arm_block=False), 'B3', 'exposed', 'no vLLM route sealed'),
            (manifest(SHIMMER_VLLM_AGENTS='VERIFIER,PRACTICE_AUDITOR'), 'B3', 'exposed', "not the route's"),
            (manifest(SHIMMER_VLLM_JOB='{}'), 'B3', 'exposed', "not the route's"),
            (manifest(), 'B1', 'exposed', 'exposed B3 bundle only'),
            (manifest(), 'B3', 'sealed', 'exposed B3 bundle only'),
            (dict(manifest(), aux_env=None), 'B3', 'exposed', 'auxiliary environment'),
        )
        for found, arm, exposure, words in cases:
            with self.subTest(words=words, arm=arm, exposure=exposure):
                self.assertIn(words, runner.vllm_route_error(found, arm, exposure) or '')

    def test_the_runner_hands_the_route_venv_auxs_python_or_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(runner.vllm_python({'environment': {}}, d))
            with self.assertRaises(Exception):
                runner.vllm_python(manifest(), d)
            python = Path(d) / 'venv_aux' / 'bin' / 'python'
            python.parent.mkdir(parents=True)
            python.write_text('')
            self.assertEqual(runner.vllm_python(manifest(), d), str(python))

    def test_the_runner_sets_the_routes_python_only_for_a_sealed_route(self):
        with tempfile.TemporaryDirectory() as d:
            python = Path(d) / 'venv_aux' / 'bin' / 'python'
            python.parent.mkdir(parents=True)
            python.write_text('')
            environ = {runner.VLLM_PYTHON_ENV: '/somewhere/else/python'}
            runner.route_environment({'environment': {}}, d, environ)
            self.assertNotIn(runner.VLLM_PYTHON_ENV, environ)          # never inherited
            runner.route_environment(manifest(), d, environ)
            self.assertEqual(environ[runner.VLLM_PYTHON_ENV], str(python))

    def test_admit_workload_refuses_through_its_route_check(self):
        found = dict(manifest(), multi_round=False, protected_test=False, argv=['x'], support_files={})
        with patch.object(runner, 'argv_for', lambda m: ['x']), patch.object(runner, 'arm_declaration', lambda m: 'B3'):
            self.assertEqual(runner.admit_workload(found, {})['arm'], 'B3')
            bad = dict(found, environment=dict(found['environment'], SHIMMER_VLLM_AGENTS='VERIFIER,JUDGE'))
            with self.assertRaises(Exception) as caught:
                runner.admit_workload(bad, {})
        self.assertIn("not the route's", str(caught.exception))

    def test_prepare_refuses_a_route_without_its_lock_before_any_work(self):
        """Run only to its first refusal: whatever comes after the auxiliary-lock check (the output folder,
        the decoding policy read, any copy or git call) is replaced by a stop, so a neutralised check can
        never start a real seal; and the sealer's module-level output folder is restored."""
        class PastTheGate(Exception):
            pass

        def stop(*args, **kwargs):
            raise PastTheGate('prepare() went past the auxiliary-lock check')
        saved = sealer.OUT
        try:
            with tempfile.TemporaryDirectory() as d, patch.object(__import__('decoding_policy'), 'summary', stop), \
                    patch.object(Path, 'mkdir', stop):
                with self.assertRaises(Exception) as caught:
                    sealer.prepare(Path(d) / 'out', arm='B3', exposure='exposed', aux_lock=None, vllm_route=ROUTE)
                self.assertNotIsInstance(caught.exception, PastTheGate)
                self.assertIn('vLLM route', str(caught.exception))
        finally:
            sealer.OUT = saved

    def test_the_call_sites_the_helpers_are_proven_through_are_in_place(self):
        """prepare()'s block and lock checks and execute()'s environment step sit deep in a whole seal and a
        whole run; that each is called where it must be is read from the code (the helpers themselves are
        proven above, and admit_workload's and prepare()'s first refusals by running them)."""
        import ast
        def calls(module, function):
            tree = ast.parse(Path(module.__file__).read_text(encoding='utf-8'))
            node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function)
            return {c.func.id if isinstance(c.func, ast.Name) else getattr(c.func, 'attr', None)
                    for c in ast.walk(node) if isinstance(c, ast.Call)}
        self.assertTrue({'vllm_route_block', 'aux_lock_pins_vllm', 'aux_lock_admitted'} <= calls(sealer, 'prepare'))
        self.assertIn('route_environment', calls(runner, 'execute'))
        self.assertIn('vllm_route_error', calls(runner, 'admit_workload'))

    def test_the_sealers_and_the_runners_switch_names_are_the_routes(self):
        import vllm_link
        self.assertEqual((sealer.VLLM_AGENTS_ENV, sealer.VLLM_JOB_ENV), (vllm_link.AGENTS_ENV, vllm_link.JOB_ENV))
        self.assertEqual((runner.VLLM_AGENTS_ENV, runner.VLLM_JOB_ENV, runner.VLLM_PYTHON_ENV),
                         (vllm_link.AGENTS_ENV, vllm_link.JOB_ENV, vllm_link.PYTHON_ENV))


def _block_without_checks(vllm_route, registry, envelope=None):
    job = dict(dtype='float16', max_model_len=vllm_route['max_model_len'], gpu_memory_utilization=vllm_route['memory_share'],
               batch=1, batch_invariant=True, request_seconds=600)
    return (dict(protocol='vllm-link-v1', agents=list(vllm_route['agents']), job=job),
            {sealer.VLLM_AGENTS_ENV: ','.join(vllm_route['agents']),
             sealer.VLLM_JOB_ENV: json.dumps(job, sort_keys=True, separators=(',', ':'))})


def _keeps_inherited(manifest, base, environ):
    found = runner.vllm_python(manifest, base)
    if found is not None:
        environ[runner.VLLM_PYTHON_ENV] = found


NEUTRALIZATIONS = [
    # The call sites, neutralised by a helper that admits everything.
    ('test_admit_workload_refuses_through_its_route_check', runner, 'vllm_route_error', lambda m, a, e: None),
    ('test_prepare_refuses_a_route_without_its_lock_before_any_work', sealer, 'aux_lock_admitted',
     lambda lock, arm, sealed, prompts, route=None: True),
    # A block whose job is not the route's figures.
    ('test_the_sealer_writes_one_block_and_its_two_switch_values', sealer, 'vllm_route_block',
     lambda route, registry, envelope=None: (dict(_block_without_checks(route, registry)[0],
                                                  job=dict(_block_without_checks(route, registry)[0]['job'],
                                                           gpu_memory_utilization=0.9)),
                                             _block_without_checks(route, registry)[1])),
    # An inherited route Python kept for a run that sealed no route.
    ('test_the_runner_sets_the_routes_python_only_for_a_sealed_route', runner, 'route_environment', _keeps_inherited),
    # A block written for any agent lets PROCESSOR, an unregistered name or JUDGE be routed.
    ('test_the_sealer_refuses_an_agent_the_route_does_not_serve', sealer, 'vllm_route_block', _block_without_checks),
    # A lock check that admits any lock, and flags read without the route.
    ('test_the_route_needs_a_lock_that_pins_vllm_and_its_flags_need_the_route', sealer, 'aux_lock_pins_vllm',
     lambda data: True),
    # The runner reading any route as admitted lets an unsealed switch through.
    ('test_the_runner_admits_the_route_only_as_sealed', runner, 'vllm_route_error', lambda m, a, e: None),
    # A lock admitted whatever the arm lets the route into a B1 or sealed bundle.
    ('test_an_aux_lock_goes_with_a_route_in_an_exposed_b3_bundle_only', sealer, 'aux_lock_admitted',
     lambda lock, arm, sealed, prompts, route=None: lock is not None),
    # A route Python handed without its file.
    ('test_the_runner_hands_the_route_venv_auxs_python_or_refuses', runner, 'vllm_python',
     lambda m, base: None if m.get('vllm_route') is None else str(Path(base) / runner.VLLM_PYTHON)),
]


class Neutralizations(unittest.TestCase):
    def test_each_proof_fails_when_its_rule_is_neutralised_and_passes_restored(self):
        for name, module, attribute, broken in NEUTRALIZATIONS:
            with self.subTest(name=name, attribute=attribute):
                with patch.object(module, attribute, broken):
                    result = unittest.TextTestRunner(stream=io.StringIO(),
                                                     verbosity=0).run(VllmRouteChecks(name))
                self.assertFalse(result.wasSuccessful(), '%s still passes with %s neutralised' % (name, attribute))
                restored = unittest.TextTestRunner(stream=io.StringIO(),
                                                   verbosity=0).run(VllmRouteChecks(name))
                self.assertTrue(restored.wasSuccessful(), name)


if __name__ == '__main__':
    unittest.main(verbosity=1)
