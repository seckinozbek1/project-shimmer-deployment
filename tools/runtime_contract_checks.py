"""Local deterministic runtime gates. No providers, model imports or generation."""
import copy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import runtime_contract as runtime
import prepare_remote_experiment as preparation

ROOT = Path(__file__).resolve().parents[1]


class RuntimeChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.exe = str(self.root / 'compatible-python.exe')
        self.old = str(self.root / 'old-python.exe')
        self.calls, self.expensive = [], []
        self.source = self.root / 'scripts/fixture.py'
        self.source.parent.mkdir()
        self.source.write_text('value = 1\n')
        self.manifest = {'scripts/fixture.py': hashlib.sha256(self.source.read_bytes()).hexdigest()}

    def runner(self, args, **kwargs):
        self.calls.append(args)
        if '-c' in args:
            old = args[0] in ('python', self.old)
            result = {'version': [3, 10, 12] if old else [3, 12, 3],
                      'executable': self.old if old else self.exe}
        elif '--source' in args:
            result = {'source_preflight_passed': True, 'imports': ['agent_wrapper', 'finding_record']}
        else:
            result = {'missing': [], 'dependencies_ready': True}
        return SimpleNamespace(returncode=0, stdout=json.dumps(result))

    def prepare(self, **kwargs):
        def action(label):
            return lambda *args: self.expensive.append((label, args[0]['executable']))
        return preparation.prepare(self.root, self.manifest, self.root / 'result',
            candidate_commands=kwargs.pop('candidates', [self.exe]),
            runner=kwargs.pop('runner', self.runner),
            install=action('install'), acquire=action('download'),
            hydrate=action('hydrate'), infer=action('inference'), **kwargs)

    def test_checkpoint_exists_before_acquisition_and_contains_dependency_proof(self):
        def acquire(selected):
            value = json.loads((self.root / 'result/PRE_INFERENCE_CHECKPOINT.json').read_text())
            self.assertTrue(value['all_green'])
            self.assertTrue(value['source_integrity_passed'])
            self.assertTrue(value['source_preflight']['source_preflight_passed'])
            self.assertTrue(value['dependencies']['dependencies_ready'])
            self.assertEqual(value['interpreter']['executable'], selected['executable'])
        preparation.prepare(self.root, self.manifest, self.root / 'result',
            candidate_commands=[self.exe], runner=self.runner, acquire=acquire)

    def test_incompatible_interpreter_stops_every_expensive_stage(self):
        with self.assertRaisesRegex(runtime.RuntimeContractError, '3.10'):
            self.prepare(candidates=['python'])
        self.assertEqual(self.expensive, [])
        self.assertFalse((self.root / 'result/READY.json').exists())
        self.assertTrue(all('-c' in args for args in self.calls))

    def test_compatible_interpreter_proceeds_in_required_order(self):
        result = self.prepare()
        self.assertEqual(result['stages'], ['resolve_runtime', 'source_integrity', 'source_compile_import',
            'dependency_check', 'model_acquisition', 'model_hydration', 'bounded_inference'])
        self.assertTrue((self.root / 'result/READY.json').exists())

    def test_source_failure_stops_installer_models_and_readiness(self):
        def fail(args, **kwargs):
            if '--source' in args:
                return SimpleNamespace(returncode=2, stdout=json.dumps({'error': 'Source import failed: finding_record (SyntaxError)'}))
            return self.runner(args, **kwargs)
        with self.assertRaisesRegex(runtime.RuntimeContractError, 'finding_record'):
            self.prepare(runner=fail)
        self.assertEqual(self.expensive, [])
        self.assertFalse((self.root / 'result/READY.json').exists())

    def test_path_default_cannot_override_compatible_candidate(self):
        result = self.prepare(candidates=['python', self.exe])
        self.assertEqual(result['interpreter']['executable'], self.exe)
        self.assertTrue(all(path == self.exe for _, path in self.expensive))

    def test_selected_absolute_executable_used_for_every_post_selection_subprocess(self):
        self.prepare(candidates=['python', self.exe])
        work = [args for args in self.calls if '-c' not in args]
        self.assertTrue(work)
        self.assertTrue(all(args[0] == self.exe for args in work))
        self.assertTrue(all(path == self.exe for _, path in self.expensive))

    def test_patch_level_profiles_are_distinct(self):
        self.assertTrue(runtime.compatible([3, 12, 9]))
        self.assertFalse(runtime.compatible([3, 12, 9], profile='sealed_reference'))
        self.assertTrue(runtime.compatible([3, 12, 3], profile='sealed_reference'))
        self.assertFalse(runtime.compatible([3, 13, 0]))

    def test_identity_requery_prevents_alias_change(self):
        count = 0
        def drift(args, **kwargs):
            nonlocal count
            count += 1
            result = self.runner(args, **kwargs)
            if count == 2:
                result.stdout = json.dumps({'version': [3, 10, 12], 'executable': self.old})
            return result
        with self.assertRaises(runtime.RuntimeContractError):
            self.prepare(runner=drift)
        self.assertEqual(self.expensive, [])

    def test_source_hash_failure_is_before_import_and_install(self):
        self.source.write_text('value = 2\n')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.prepare()
        self.assertEqual(self.expensive, [])
        self.assertTrue(all('-c' in args for args in self.calls))

    def test_unhashed_source_cannot_reach_import(self):
        self.source.with_name('extra.py').write_text('value = 2\n')
        with self.assertRaisesRegex(runtime.RuntimeContractError, 'omits'):
            self.prepare()
        self.assertEqual(self.expensive, [])

    def test_dependency_mismatch_stops_before_install_and_models(self):
        def mismatch(args, **kwargs):
            if '--dependencies' in args:
                return SimpleNamespace(returncode=2, stdout=json.dumps({'error': 'Dependency version mismatch: torch'}))
            return self.runner(args, **kwargs)
        with self.assertRaisesRegex(runtime.RuntimeContractError, 'Dependency version mismatch'):
            self.prepare(runner=mismatch)
        self.assertEqual(self.expensive, [])

    def test_missing_dependencies_install_only_after_source_pass_then_recheck(self):
        count = 0
        def missing(args, **kwargs):
            nonlocal count
            if '--dependencies' in args:
                count += 1
                return SimpleNamespace(returncode=0, stdout=json.dumps(
                    {'missing': ['psutil'] if count == 1 else [], 'dependencies_ready': count > 1}))
            return self.runner(args, **kwargs)
        result = self.prepare(runner=missing)
        self.assertEqual(self.expensive[0], ('install', self.exe))
        self.assertLess(result['stages'].index('source_compile_import'), result['stages'].index('install_missing_dependencies'))
        self.assertLess(result['stages'].index('dependency_recheck'), result['stages'].index('model_acquisition'))

    def test_real_current_source_import_graph_without_model_stack(self):
        selected = runtime.resolve([sys.executable])
        result = runtime.subprocess_check(selected, ROOT)
        self.assertTrue(result['source_preflight_passed'])
        self.assertIn('agent_wrapper', result['imports'])
        self.assertIn('finding_record', result['imports'])

    def test_real_compatible_interpreter_rejects_syntax_before_import(self):
        self.source.write_text('def invalid(:\n')
        selected = runtime.resolve([sys.executable])
        with self.assertRaisesRegex(runtime.RuntimeContractError, 'fixture.py:1'):
            runtime.subprocess_check(selected, self.root)

    def test_real_compatible_interpreter_rejects_missing_import_graph(self):
        selected = runtime.resolve([sys.executable])
        with self.assertRaisesRegex(runtime.RuntimeContractError, 'agent_wrapper'):
            runtime.subprocess_check(selected, self.root)

    def test_remote_bootstrap_is_generated_from_contract(self):
        contract = copy.deepcopy(runtime.load_contract())
        contract['python_compatibility']['minor'] = 99
        contract['python'] = '3.99.4'
        contract['python_profiles']['sealed_reference'] = '==3.99.4'
        command = runtime.remote_resolver_command(contract=contract)
        self.assertIn('python3.99', command)
        self.assertIn('[3, 99, 4]', command)
        self.assertNotIn('3.12.3', command)

    def test_neutralise_version_guard_is_detected_and_restored(self):
        # Mutant must cause the incompatible-interpreter assertion to fail.
        with patch.object(runtime, 'compatible', return_value=True):
            with self.assertRaises(AssertionError):
                self.test_incompatible_interpreter_stops_every_expensive_stage()
        self.assertFalse(runtime.compatible([3, 10, 12]))

    def test_neutralise_source_guard_is_detected_and_restored(self):
        original = runtime.subprocess_check
        def bypass(selection, root, *, dependencies=False, **kwargs):
            if not dependencies:
                return {'source_preflight_passed': True}
            return original(selection, root, dependencies=True, **kwargs)
        with patch.object(runtime, 'subprocess_check', side_effect=bypass):
            with self.assertRaises(AssertionError):
                self.test_source_failure_stops_installer_models_and_readiness()
        self.assertIs(runtime.subprocess_check, original)

    def test_dependency_version_check_precedes_imports(self):
        folder = self.root / 'tools/cloud_run'
        folder.mkdir(parents=True)
        (folder / 'runtime.lock').write_text('fixture==1.0\n')
        contract = {'core_dependencies': {'fixture': 'fixture'}}
        with patch.object(runtime.importlib.metadata, 'version', return_value='2.0'), \
             patch.object(runtime.importlib, 'import_module') as imports:
            with self.assertRaisesRegex(runtime.RuntimeContractError, 'required.*1.0.*observed.*2.0'):
                runtime.dependency_check(self.root, contract)
            imports.assert_not_called()

    def test_dependency_import_failure_refuses_readiness(self):
        folder = self.root / 'tools/cloud_run'
        folder.mkdir(parents=True)
        (folder / 'runtime.lock').write_text('fixture==1.0\n')
        with patch.object(runtime.importlib.metadata, 'version', return_value='1.0'), \
             patch.object(runtime.importlib, 'import_module', side_effect=ImportError('fixture')):
            with self.assertRaisesRegex(runtime.RuntimeContractError, 'Dependency import failed: fixture'):
                runtime.dependency_check(self.root, {'core_dependencies': {'fixture': 'fixture'}})

    def test_sealed_remote_hydration_cannot_bypass_source_preflight(self):
        import cloud_run_remote
        contract = runtime.load_contract()
        (self.root / 'runtime.json').write_text(json.dumps(contract))
        with patch.object(cloud_run_remote, '__file__', str(self.root / 'cloud_run_remote.py')), \
             patch.object(cloud_run_remote.sys, 'platform', 'linux'), \
             patch.object(runtime, 'subprocess_check', side_effect=runtime.RuntimeContractError('Source import failed')), \
             patch.object(cloud_run_remote, 'hydrate') as hydrate:
            with self.assertRaisesRegex(runtime.RuntimeContractError, 'Source import'):
                cloud_run_remote.main(['--execute', '--hydrate-only'])
            hydrate.assert_not_called()

    def test_sealed_remote_version_failure_cannot_create_attempt_or_run_commands(self):
        import cloud_run_remote
        (self.root / 'runtime.json').write_text(json.dumps(runtime.load_contract()))
        with patch.object(cloud_run_remote, '__file__', str(self.root / 'cloud_run_remote.py')), \
             patch.object(cloud_run_remote.sys, 'platform', 'linux'), \
             patch.object(runtime.sys, 'version_info', (3, 10, 12)), \
             patch.object(cloud_run_remote.subprocess, 'run') as run:
            with self.assertRaisesRegex(runtime.RuntimeContractError, 'observed 3.10.12'):
                cloud_run_remote.main(['--execute'])
            run.assert_not_called()
            self.assertFalse((self.root / 'RUN_CLAIMED').exists())

    def test_source_layer_carries_authoritative_contract_and_lock(self):
        from prepare_source_layer import manifest
        value = manifest(ROOT)
        for name in ('tools/cloud_run/runtime.json', 'tools/cloud_run/runtime.lock'):
            self.assertEqual(value['source_files'][name]['sha256'], hashlib.sha256((ROOT / name).read_bytes()).hexdigest())

    def test_docker_source_gate_is_a_prerequisite_of_dependency_layer(self):
        source = (ROOT / 'Dockerfile').read_text()
        self.assertLess(source.index('--source /app'), source.index('COPY --from=source-preflight'))
        self.assertLess(source.index('COPY --from=source-preflight'), source.index('-m pip install'))
        self.assertIn('tools/cloud_run/runtime.json', source)
        self.assertNotIn('python3.9', source)

    def test_executed_cli_uses_selected_python_for_install_acquire_and_probe(self):
        folder = self.root / 'tools/cloud_run'
        folder.mkdir(parents=True)
        (folder / 'runtime.json').write_text(json.dumps(runtime.load_contract()))
        (folder / 'runtime.lock').write_text('psutil==1.0\n')
        manifest = dict(self.manifest)
        for name in ('tools/cloud_run/runtime.json', 'tools/cloud_run/runtime.lock'):
            manifest[name] = hashlib.sha256((self.root / name).read_bytes()).hexdigest()
        path = self.root / 'source.json'
        path.write_text(json.dumps({'source_files': {k: {'sha256': v} for k, v in manifest.items()}}))
        calls = []
        dependency_checks = 0
        def runner(args, **kwargs):
            nonlocal dependency_checks
            calls.append(args)
            if '--dependencies' in args:
                dependency_checks += 1
                return SimpleNamespace(returncode=0, stdout=json.dumps({
                    'missing': ['psutil'] if dependency_checks == 1 else [],
                    'dependencies_ready': dependency_checks > 1}))
            return self.runner(args, **kwargs)
        with contextlib.redirect_stdout(io.StringIO()):
            preparation.main(['--root', str(self.root), '--manifest', str(path),
                '--output', str(self.root / 'cli'), '--interpreter', 'python', '--interpreter', self.exe,
                '--execute', '--install-missing'], runner=runner)
        work = [args for args in calls if '-c' not in args]
        self.assertTrue(all(args[0] == self.exe for args in work))
        install = next(i for i, args in enumerate(calls) if 'pip' in args)
        acquire = next(i for i, args in enumerate(calls) if any(x.endswith('remote_experiment_models.py') for x in args))
        probe = next(i for i, args in enumerate(calls) if any(x.endswith('remote_short_burst_probe.py') for x in args))
        self.assertLess(install, acquire)
        self.assertLess(acquire, probe)
        self.assertTrue((self.root / 'cli/READY.json').exists())

    def test_inaccessible_path_alias_does_not_hide_other_candidates(self):
        original = Path.is_file
        def inaccessible(path):
            if 'inaccessible-alias' in str(path):
                raise OSError('fixture inaccessible alias')
            return original(path)
        with patch.object(runtime.os, 'get_exec_path', return_value=[str(self.root / 'inaccessible-alias')]), \
             patch.object(Path, 'is_file', inaccessible):
            values = runtime.candidates()
        self.assertIn((sys.executable,), values)


if __name__ == '__main__':
    unittest.main()
