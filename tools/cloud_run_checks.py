"""Deterministic local tests. Network blocked; no model generation or GPU access."""
from __future__ import annotations

import argparse
import ast
import contextlib
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import socket
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from cloud_run_common import (InvalidPreparation, budget_deadlines, credential_locations, digest,
    extract_source, safe_metadata, safe_name, verify_bundle, verify_files, write_json)
from prepare_cloud_run import (ARGV, behavioral_proof, make_source, pins, safetensor_header, validate_wheels)
import prepare_cloud_run as preparation
from deploy_cloud_run import execute, host_value, plan, run_transport, transport_plan
from cloud_run_observer import Recorder, summarize
from cloud_run_watchdog import load_credential, operator_preflight, watch


class Checks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='shimmer-cloud-check-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def sealed(self):
        root = self.root / 'bundle'
        root.mkdir()
        write_json(root / 'experiment.json', {'max_runs': 1, 'source_commit': 'a'*40, 'experiment_id': 'fixture', 'hourly_rate_usd': 1.99})
        write_json(root / 'operator_readiness.json', {'ssh_public_key_sha256': 'fixture'})
        write_json(root / 'runtime.json', preparation.RUNTIME)
        (root / 'runtime_contract.py').write_bytes((ROOT / 'tools/runtime_contract.py').read_bytes())
        write_json(root / 'bundle_manifest.json', {name: digest(root / name) for name in ['experiment.json', 'operator_readiness.json', 'runtime.json', 'runtime_contract.py']})
        write_json(root / 'READY_TO_PROVISION.json', {'ready_to_provision': True, 'experiment_id': 'fixture',
            'source_commit': 'a'*40, 'bundle_manifest_sha256': digest(root / 'bundle_manifest.json'),
            'runtime_source_preflight_passed': True, 'runtime_contract_sha256': digest(root / 'runtime_contract.py')})
        return root

    def source_checkout(self):
        expected = 'b' * 40
        files = {'scripts/pipeline.py': b'# fixture runtime\n', 'README.md': b'# Guide\n'}
        for name, data in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as output:
            for name, data in files.items():
                member = tarfile.TarInfo(name)
                member.size = len(data)
                output.addfile(member, io.BytesIO(data))
        def fake_git(root, *args):
            if args == ('rev-parse', 'HEAD'):
                return expected.encode()
            if args == ('ls-files', '-z'):
                return ('\0'.join(files) + '\0').encode()
            if args[0] == 'archive':
                self.assertEqual(args[-1], expected)
                return archive.getvalue()
            if args[0] == 'ls-files':
                return b'private-note.md\0'
            if args[0] == 'branch':
                return b'main\n'
            if args == ('rev-parse', '@{u}'):
                return preparation.BASELINE.encode()
            if args[0] == 'log':
                return b'bbbbbbb fixture commit\n'
            raise AssertionError(args)
        return expected, fake_git

    def test_explicit_clean_source_commit_is_not_historical_baseline(self):
        expected, fake_git = self.source_checkout()
        with patch.object(preparation, 'git', fake_git):
            files, status = preparation.source_files(self.root, expected)
        self.assertEqual(set(files), {'scripts/pipeline.py'})
        self.assertEqual(status['head'], expected)
        self.assertFalse(status['remote_tip_live_verified'])
        self.assertEqual(status['untracked_files_untouched'], ['private-note.md'])

    def test_git_guard_scans_staged_contents_not_removed_fixture_text(self):
        responses = [SimpleNamespace(stdout=b'fixture.py\0'),
                     SimpleNamespace(stdout=b'api_key = "TEST_CREDENTIAL_PLACEHOLDER"\n'),
                     SimpleNamespace(stdout=b'operation completed')]
        with patch.object(preparation.subprocess, 'run', side_effect=responses) as run:
            self.assertEqual(preparation.git(self.root, 'status', '--short'), b'operation completed')
        self.assertEqual(run.call_args_list[1].args[0], ['git', 'show', ':fixture.py'])
        self.assertEqual(run.call_args_list[2].args[0], ['git', 'status', '--short'])

    def test_git_guard_rejects_staged_auth_literal_before_operation(self):
        value = b'sk-' + b'x' * 24
        responses = [SimpleNamespace(stdout=b'fixture.py\0'),
                     SimpleNamespace(stdout=b'api_key = "' + value + b'"\n')]
        with patch.object(preparation.subprocess, 'run', side_effect=responses) as run:
            with self.assertRaises(InvalidPreparation) as caught:
                preparation.git(self.root, 'status', '--short')
        self.assertEqual(run.call_count, 2)
        self.assertNotIn(value.decode(), str(caught.exception))
        self.assertIn('fixture.py:1', str(caught.exception))

    def test_source_commit_mismatch_is_rejected(self):
        expected, fake_git = self.source_checkout()
        with patch.object(preparation, 'git', fake_git), self.assertRaisesRegex(InvalidPreparation, 'HEAD mismatch'):
            preparation.source_files(self.root, 'c' * 40)

    def test_tracked_edits_are_rejected_including_documentation(self):
        expected, fake_git = self.source_checkout()
        (self.root / 'README.md').write_text('uncommitted edit', encoding='utf-8')
        with patch.object(preparation, 'git', fake_git), self.assertRaisesRegex(InvalidPreparation, 'tracked source changed'):
            preparation.source_files(self.root, expected)

    def test_old_remote_verification_cannot_certify_new_commit(self):
        expected, fake_git = self.source_checkout()
        audit = self.root / 'output/cloud_prep_audit/source_remote_verification.json'
        audit.parent.mkdir(parents=True)
        write_json(audit, {'source_commit': preparation.BASELINE})
        with patch.object(preparation, 'git', fake_git):
            _, status = preparation.source_files(self.root, expected)
        self.assertFalse(status['prior_live_remote_verification_matches_source'])
        self.assertNotIn('prior_live_remote_verification', status)

    def test_provider_metadata_drops_secret_fields(self):
        value = 'synthetic-' + 'x'*24
        raw = {'instance_id': 'a'*32, 'status': 'active', 'public_ip': '203.0.113.1', 'hourly_rate': 1.99,
               'jupyter_token': value, 'notebook_url': 'https://invalid.example/' + '?token=' + value,
               'api_key': value, 'ssh_private_key': value, 'signed_url': value, 'cookies': value,
               'session': {'credential': value}, 'raw_response': {'token': value}}
        kept = safe_metadata(raw)
        self.assertEqual(set(kept), {'instance_id', 'status', 'public_ip', 'hourly_rate'})
        self.assertNotIn(value, json.dumps(kept))

    def test_metadata_rejects_secret_under_allowlisted_name(self):
        for value in ['https://example.invalid/' + '?token=x', {'token': 'fixture'}, 'notebook_token', 'sk-' + 'proj-' + 'x'*24]:
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                safe_metadata({'name': value})

    def test_metadata_rejects_bad_numbers_and_ip(self):
        for value in [True, -1, float('nan'), float('inf'), '1.99']:
            with self.assertRaises(ValueError):
                safe_metadata({'hourly_rate': value})
        with self.assertRaises(ValueError):
            safe_metadata({'public_ip': 'example.invalid'})

    def test_metadata_idempotent(self):
        value = {'name': 'shimmer', 'gpu_count': 1, 'gpu_type': 'A100 SXM4 40GB', 'status': 'terminated'}
        self.assertEqual(safe_metadata(value), safe_metadata(safe_metadata(value)))

    def test_scanner_detects_credentials_without_values(self):
        values = ['sk-' + 'ant-' + 'x'*24, 'AK' + 'IA' + 'X'*16,
                  'https://example.invalid/' + '?token=' + 'x'*20,
                  'api_key = ' + repr('x'*24), '"jupyter_token": ' + repr('x'*24)]
        for value in values:
            found = credential_locations(value.encode(), 'fixture.py')
            self.assertEqual(found, [{'file': 'fixture.py', 'line': 1}])
            self.assertNotIn(value, json.dumps(found))

    def test_scanner_excludes_non_auth_hash_and_placeholder(self):
        data = 'commit = ' + repr('a'*40) + '\napi_key = "TEST_CREDENTIAL_PLACEHOLDER"'
        self.assertEqual(credential_locations(data.encode(), 'fixture'), [])

    def test_auth_hash_still_rejected(self):
        self.assertTrue(credential_locations(('secret = ' + repr('a'*40)).encode(), 'fixture'))

    def test_source_archive_reproducible(self):
        files = {'scripts/a.py': b'pass\n', 'config/b.json': b'{}\n'}
        a, b = self.root / 'a.tar.gz', self.root / 'b.tar.gz'
        make_source(files, a)
        make_source(dict(reversed(list(files.items()))), b)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        manifest = {n: hashlib.sha256(v).hexdigest() for n, v in files.items()}
        extract_source(a, self.root / 'extracted', manifest)
        verify_files(self.root / 'extracted', manifest)

    def test_source_hash_tamper_rejected(self):
        path = self.root / 'a.tar.gz'
        make_source({'a': b'wrong'}, path)
        with self.assertRaises(ValueError):
            extract_source(path, self.root / 'out', {'a': hashlib.sha256(b'correct').hexdigest()})
        self.assertFalse((self.root / 'out').exists())

    def test_source_traversal_rejected(self):
        for name in ['../a', '/a', 'C:/a', 'a\\b', 'a/../b']:
            self.assertFalse(safe_name(name))
            with self.assertRaises(ValueError):
                make_source({name: b'bad'}, self.root / 'bad.tar.gz')

    def test_source_symlink_rejected(self):
        archive = self.root / 'bad.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            info = tarfile.TarInfo('a'); info.type = tarfile.SYMTYPE; info.linkname = '/etc/passwd'
            tar.addfile(info)
        with self.assertRaises(ValueError):
            extract_source(archive, self.root / 'out', {'a': 'x'})

    def test_source_extra_file_rejected(self):
        archive = self.root / 'bad.tar.gz'
        make_source({'a': b'a', 'extra': b'b'}, archive)
        with self.assertRaises(ValueError):
            extract_source(archive, self.root / 'out', {'a': hashlib.sha256(b'a').hexdigest()})

    def test_source_duplicate_rejected(self):
        archive = self.root / 'bad.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            for _ in range(2):
                info = tarfile.TarInfo('a'); info.size = 1; tar.addfile(info, io.BytesIO(b'a'))
        with self.assertRaises(ValueError):
            extract_source(archive, self.root / 'out', {'a': hashlib.sha256(b'a').hexdigest()})

    def test_seal_verifies(self):
        self.assertTrue(verify_bundle(self.sealed())['ready_to_provision'])

    def test_seal_rejects_tampering(self):
        root = self.sealed()
        (root / 'experiment.json').write_text('{}')
        with self.assertRaises(ValueError):
            verify_bundle(root)

    def test_seal_rejects_extra_private_document(self):
        root = self.sealed()
        (root / 'operator.md').write_text('private fixture')
        with self.assertRaises(ValueError):
            verify_bundle(root)

    def test_missing_readiness_rejected(self):
        with self.assertRaises(FileNotFoundError):
            verify_bundle(self.root)

    def test_false_readiness_rejected(self):
        root = self.sealed()
        write_json(root / 'READY_TO_PROVISION.json', {'ready_to_provision': False})
        with self.assertRaises(ValueError):
            verify_bundle(root)

    def test_budget_from_billing_start(self):
        value = budget_deadlines(1.99, 1000)
        self.assertAlmostEqual(value['soft_epoch'] - 1000, 5 / 1.99 * 3600)
        self.assertAlmostEqual(value['ceiling_epoch'] - value['terminate_epoch'], 120)

    def test_invalid_budget_rejected(self):
        for rate in [0, -1, float('nan'), float('inf'), True]:
            with self.assertRaises(ValueError):
                budget_deadlines(rate, 1000)

    def test_watchdog_ceiling_and_verified_termination(self):
        provider = SimpleNamespace(terminated=False, calls=0)
        def instance(instance_id):
            return {'instance_id': instance_id, 'status': 'terminated' if provider.terminated else 'active'}
        def terminate(instance_id):
            provider.calls += 1; provider.terminated = True
        provider.instance, provider.terminate = instance, terminate
        watch(provider, 'a'*32, 1.99, 1000, self.root, sleep=lambda seconds: None, now=lambda: 100000)
        self.assertEqual(provider.calls, 1)
        self.assertTrue((self.root / 'TERMINATION_VERIFIED.json').is_file())

    def test_watchdog_retries_without_persisting_response(self):
        (self.root / 'TERMINATE_REQUEST').touch()
        class Provider:
            calls = 0
            def instance(self, instance_id):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError('synthetic confidential response')
                return {'instance_id': instance_id, 'status': 'terminated'}
        watch(Provider(), 'a'*32, 1.99, 1000, self.root, sleep=lambda seconds: None, now=lambda: 1001)
        self.assertNotIn('synthetic confidential response', (self.root / 'TERMINATION_RETRY.json').read_text())

    def test_transport_mock_ssh(self):
        commands = transport_plan('ubuntu@203.0.113.1', self.root / 'bundle', '/home/ubuntu/shimmer_experiments/test')
        called = []
        def runner(command, **kwargs):
            called.append(command)
            self.assertTrue(kwargs['check'])
            self.assertFalse(kwargs.get('shell', False))
        for key in ('connect', 'create', 'upload'):
            run_transport(commands[key], 20, runner)
        self.assertEqual(len(called), 3)
        self.assertIn('StrictHostKeyChecking=accept-new', called[0])

    def test_host_injection_rejected(self):
        for host in ['ubuntu@127.0.0.1;id', '-oProxyCommand=x', 'root@203.0.113.1', 'ubuntu@example.com']:
            with self.assertRaises(ValueError):
                host_value(host)

    def test_remote_path_injection_rejected(self):
        with self.assertRaises(ValueError):
            transport_plan('ubuntu@203.0.113.1', self.root, '/tmp/;id')

    def test_legacy_bundle_cannot_bypass_new_runtime_gate(self):
        root = self.sealed()
        ready = json.loads((root / 'READY_TO_PROVISION.json').read_text())
        del ready['runtime_source_preflight_passed']
        write_json(root / 'READY_TO_PROVISION.json', ready)
        with self.assertRaisesRegex(ValueError, 'reseal locally'):
            plan(root, 'ubuntu@203.0.113.1', 1000)

    def test_dry_run_performs_no_transport(self):
        args = SimpleNamespace(bundle=self.sealed(), host='ubuntu@203.0.113.1',
                               running_since='2026-09-14T00:00:00Z', execute=False)
        import cloud_run_watchdog
        with contextlib.redirect_stdout(io.StringIO()) as output, \
             patch.object(cloud_run_watchdog, 'operator_preflight', return_value={'ssh_public_key_sha256': 'fixture'}):
            self.assertEqual(execute(args, runner=lambda *a, **k: self.fail('transport in dry run')), 0)
        self.assertFalse(json.loads(output.getvalue())['network_contacted'])

    def test_unready_deploy_never_calls_ssh(self):
        args = SimpleNamespace(bundle=self.root, host='ubuntu@203.0.113.1',
                               running_since='2026-09-14T00:00:00Z', execute=True)
        with self.assertRaises(FileNotFoundError):
            execute(args, runner=lambda *a, **k: self.fail('transport for unready bundle'))

    def test_failed_transport_propagates(self):
        import subprocess
        def failure(*a, **k):
            raise subprocess.TimeoutExpired('ssh', 20)
        with self.assertRaises(subprocess.TimeoutExpired):
            run_transport(['ssh'], 20, failure)

    def mocked_deploy(self, fail_remote=False, fail_runtime=False):
        bundle = self.sealed()
        args = SimpleNamespace(bundle=bundle, host='ubuntu@203.0.113.1', execute=True,
            running_since=datetime.now(timezone.utc).isoformat(), hourly_rate=1.99,
            instance_id='a'*32, collection=self.root / 'collected')
        args.identity_file = self.root / 'fixture_identity'
        local = args.collection / 'fixture'
        calls = []
        def popen(command, **kwargs):
            write_json(local / 'WATCHDOG_ARMED.json', {'fixture': True})
            return SimpleNamespace(poll=lambda: None)
        def runner(command, **kwargs):
            calls.append(command)
            if 'for candidate in' in command[-1]:
                return SimpleNamespace(stdout=json.dumps({'executable': '/usr/bin/python3.12', 'version': [3, 10, 12] if fail_runtime else [3, 12, 3]}))
            if 'cloud_run_remote.py' in command[-1] and fail_remote:
                raise RuntimeError('authored SSH failure')
            if command[0] == 'scp' and command[-2].endswith('/evidence'):
                evidence = local / 'evidence'; evidence.mkdir()
                write_json(evidence / 'result.json', {'exit_code': 0, 'completed_runs': 1})
                write_json(evidence / 'collection_hashes.json', {'result.json': digest(evidence / 'result.json')})
        def sleep(seconds):
            if (local / 'TERMINATE_REQUEST').exists():
                write_json(local / 'TERMINATION_VERIFIED.json', {'status': 'terminated'})
        provider = SimpleNamespace(instance=lambda identity: {'instance_id': identity, 'public_ip': '203.0.113.1',
                                   'status': 'active', 'type': 'gpu_1x_a100_sxm4', 'gpu_count': 1, 'hourly_rate': 1.99})
        import deploy_cloud_run
        import cloud_run_watchdog
        with patch.object(deploy_cloud_run.subprocess, 'Popen', side_effect=popen), \
             patch.object(cloud_run_watchdog, 'operator_preflight', return_value={'ssh_public_key_sha256': 'fixture'}), \
             patch.object(deploy_cloud_run.time, 'sleep', side_effect=sleep), \
             patch.dict('os.environ', {'LAMBDA_API_KEY': 'synthetic-' + 'x'*24}), \
             contextlib.redirect_stdout(io.StringIO()):
            code = execute(args, runner=runner, provider=provider)
        return code, calls, json.loads((local / 'EXPERIMENT_STATUS.json').read_text())

    def test_complete_mock_deployment_collects_and_terminates(self):
        code, calls, status = self.mocked_deploy()
        self.assertEqual(code, 0)
        self.assertTrue(status['benchmark_valid'])
        self.assertEqual(sum('cloud_run_remote.py' in command[-1] for command in calls), 1)

    def test_incompatible_mock_remote_runtime_never_transfers_source(self):
        code, calls, status = self.mocked_deploy(fail_runtime=True)
        self.assertEqual(code, 2)
        self.assertTrue(status['termination_verified'])
        self.assertFalse(any(command[0] == 'scp' for command in calls))
        self.assertFalse(any('cloud_run_remote.py' in command[-1] for command in calls))

    def test_failed_mock_remote_run_terminates_as_non_benchmark(self):
        code, calls, status = self.mocked_deploy(fail_remote=True)
        self.assertEqual(code, 2)
        self.assertTrue(status['termination_verified'])
        self.assertFalse(status['benchmark_valid'])
        self.assertEqual(status['classification'], 'ABORTED / NON-BENCHMARK')

    def test_offline_pins_require_exact_versions(self):
        path = self.root / 'lock'
        path.write_text('fixture>=1.0\n')
        with self.assertRaises(ValueError):
            pins(path)

    def wheel(self, name='fixture', version='1.0', tag='py3-none-any', dependencies=()):
        path = self.root / (name + '-' + version + '-' + tag + '.whl')
        with zipfile.ZipFile(path, 'w') as archive:
            metadata = 'Metadata-Version: 2.1\nName: ' + name + '\nVersion: ' + version + '\nRequires-Python: >=3.9\n'
            metadata += ''.join('Requires-Dist: ' + d + '\n' for d in dependencies)
            archive.writestr(name + '-' + version + '.dist-info/METADATA', metadata)
        return path

    def test_offline_wheelhouse_missing_fails(self):
        with self.assertRaises(ValueError):
            validate_wheels(self.root / 'absent', {'fixture': '1.0'})

    def test_offline_wheel_closure_passes(self):
        self.wheel()
        self.assertEqual(set(validate_wheels(self.root, {'fixture': '1.0'})), {'fixture'})

    def test_windows_wheel_rejected(self):
        self.wheel(tag='cp312-cp312-win_amd64')
        with self.assertRaises(ValueError):
            validate_wheels(self.root, {'fixture': '1.0'})

    def test_missing_transitive_dependency_rejected(self):
        self.wheel(dependencies=['missing>=1'])
        with self.assertRaises(ValueError):
            validate_wheels(self.root, {'fixture': '1.0'})

    def test_linux_marker_dependencies_checked(self):
        self.wheel(dependencies=['missing>=1; sys_platform == "linux"'])
        with self.assertRaises(ValueError):
            validate_wheels(self.root, {'fixture': '1.0'})

    def test_windows_marker_dependencies_ignored(self):
        self.wheel(dependencies=['missing>=1; sys_platform == "win32"'])
        self.assertTrue(validate_wheels(self.root, {'fixture': '1.0'}))

    def test_wrong_wheel_pin_rejected(self):
        self.wheel(version='2.0')
        with self.assertRaises(ValueError):
            validate_wheels(self.root, {'fixture': '1.0'})

    def test_actual_parser_and_dag_isolation(self):
        files = {'scripts/' + n + '.py': (ROOT / 'scripts' / (n + '.py')).read_bytes()
                 for n in ('pipeline', 'agent_activation', 'execution_scheduler', 'execution_topology')}
        proof = behavioral_proof(files, self.root / 'proof')
        self.assertTrue(proof['multi_round_inactive'])
        self.assertTrue(proof['draft_rejected'])
        self.assertEqual(len(proof['guards']), 3)

    def test_observer_concurrency_finops(self):
        events = [{'event': 'span_start', 'seq': 1, 't': 1}, {'event': 'span_start', 'seq': 2, 't': 2},
                  {'event': 'span_end', 'span': 1, 'name': 'dispatch', 't': 4},
                  {'event': 'span_end', 'span': 2, 'name': 'dispatch', 't': 5},
                  {'event': 'span_end', 'name': 'generate', 'seconds': 3},
                  {'event': 'process_finish', 't': 10}]
        result = summarize(events, [], [{'event': 'instance_reported_running', 'epoch': 10},
                                       {'event': 'first_generation_start', 'epoch': 35}])
        self.assertEqual(result['actual_max_concurrent_calls'], 2)
        self.assertEqual(result['generation_seconds'], 3)
        self.assertEqual(result['provisioned_to_first_generation_seconds'], 25)

    def test_no_generation_is_not_zero_startup_time(self):
        self.assertIsNone(summarize([], [], [])['provisioned_to_first_generation_seconds'])

    def test_observer_finalization_after_recorder_closed(self):
        recorder = Recorder(self.root / 'events.jsonl')
        recorder.event('process_finish')
        recorder.close()
        # Instrumented Path/JSON calls during result writing must be inert now.
        with recorder.span('file.write_bytes'):
            write_json(self.root / 'result.json', {'exit_code': 0})
        self.assertEqual(json.loads((self.root / 'result.json').read_text())['exit_code'], 0)

    def test_four_credential_fixtures_are_explicit_placeholders(self):
        source = (ROOT / 'scripts/verify_session1.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        names = {'check_85_model_approval_shape', 'check_92_provider_timeout',
                 'check_95_provider_error_scrubbed', 'check_111_converted_log_site_emits_json_line'}
        for function in [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]:
            segment = ast.get_source_segment(source, function)
            self.assertIn('TEST_CREDENTIAL_PLACEHOLDER', segment)
            self.assertTrue('_FakeAnthropicClient' in segment or 'list_available_models = lambda' in segment)

    def test_aborted_evidence_never_has_valid_benchmark_flag(self):
        source = (ROOT / 'tools/deploy_cloud_run.py').read_text()
        self.assertIn("'benchmark_valid': success and terminated", source)
        self.assertIn('ABORTED / NON-BENCHMARK', source)

    def mocked_prepare(self, output, wheels_ok=True):
        """Only external inventory inputs are fixtures; run the real sealing algorithm."""
        locked = pins(preparation.ASSETS / 'runtime.lock')
        wh = self.root / 'wheelhouse'
        wh.mkdir(exist_ok=True)
        (wh / 'fixture.whl').write_bytes(b'authored wheel bytes')
        wheels = {n: {'filename': 'fixture.whl', 'sha256': digest(wh / 'fixture.whl')} for n in locked}
        files = {'scripts/pipeline.py': b'# inert sealing fixture\n',
                 'config/local_models.json': (ROOT / 'config/local_models.json').read_bytes(),
                 'benchmark/corpora/clinical_reference/context/result_sheet.md': b'synthetic\n'}
        args = SimpleNamespace(experiment_id='fixture', expected_commit=preparation.BASELINE,
                               hourly_rate=1.99, output=output, wheelhouse=wh, model_cache=self.root)
        mock_models = [{'model': n, 'revision': r, 'files': {}} for n, r in json.loads((preparation.ASSETS / 'models.json').read_text()).items()]
        test_result = SimpleNamespace(returncode=0, stdout=json.dumps({'passed': True, 'tests_run': 1}).encode())
        with patch.object(preparation, 'resolve', return_value={'executable': sys.executable, 'profile': 'experiment'}), \
             patch.object(preparation, 'subprocess_check', return_value={'source_preflight_passed': True}), \
             patch.object(preparation, 'source_files', return_value=(files, {'fixture': True})), \
             patch.object(preparation, 'operator_preflight', return_value={'credential_loaded': True}), \
             patch.object(preparation, 'behavioral_proof', return_value={'options': {}}), \
             patch.object(preparation, 'model_manifest', return_value=mock_models), \
             patch.object(preparation, 'validate_wheels', side_effect=None if wheels_ok else InvalidPreparation('fixture missing wheels'), return_value=wheels), \
             patch.object(preparation.subprocess, 'run', return_value=test_result):
            return preparation.prepare(args)

    def test_full_bundle_reproducible_and_readiness_last(self):
        a, ra = self.mocked_prepare(self.root / 'one')
        b, rb = self.mocked_prepare(self.root / 'two')
        self.assertTrue(ra['ready_to_provision'] and rb['ready_to_provision'])
        self.assertEqual(verify_bundle(a), verify_bundle(b))
        self.assertEqual((a / 'bundle_manifest.json').read_bytes(), (b / 'bundle_manifest.json').read_bytes())

    def test_preparation_missing_prerequisite_never_writes_ready(self):
        root, report = self.mocked_prepare(self.root / 'missing', wheels_ok=False)
        self.assertFalse(report['ready_to_provision'])
        self.assertFalse((root / 'READY_TO_PROVISION.json').exists())
        self.assertTrue((root / 'PREPARATION_REPORT.json').is_file())

    def test_preparation_refuses_existing_evidence(self):
        root, report = self.mocked_prepare(self.root / 'one')
        before = (root / 'READY_TO_PROVISION.json').read_bytes()
        with self.assertRaises(ValueError):
            self.mocked_prepare(self.root / 'one')
        self.assertEqual(before, (root / 'READY_TO_PROVISION.json').read_bytes())

    def test_credential_file_is_parsed_without_execution(self):
        path = self.root / 'private_config.py'
        value = 'synthetic-' + 'x'*24
        path.write_text('raise RuntimeError("must not execute")\nLAMBDA_API_KEY = ' + repr(value))
        self.assertTrue(load_credential(path))

    def test_credential_parse_failure_does_not_echo_source(self):
        path = self.root / 'bad_config.py'
        path.write_text('LAMBDA_API_KEY = "synthetic broken')
        with self.assertRaises(InvalidPreparation) as raised:
            load_credential(path)
        self.assertNotIn('synthetic', str(raised.exception))

    def test_missing_operator_credential_is_not_ready(self):
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(InvalidPreparation):
            load_credential()

    def test_protected_ssh_identity_needs_no_agent_or_private_read(self):
        private = self.root / 'existing_identity'
        private.write_text('private fixture: must not be read')
        Path(str(private) + '.pub').write_text('ssh-ed25519 Zml4dHVyZQ== fixture')
        original = Path.read_text
        def public_only(path, *a, **k):
            self.assertNotEqual(path, private)
            return original(path, *a, **k)
        def validate_public(command, **kwargs):
            self.assertEqual(command, ['ssh-keygen', '-l', '-f', str(private) + '.pub'])
            return SimpleNamespace(returncode=0)
        with patch('cloud_run_watchdog.load_credential', return_value='synthetic-' + 'x'*24), \
             patch.object(Path, 'read_text', public_only), \
             patch('subprocess.run', side_effect=validate_public):
            result = operator_preflight(identity_file=private)
        self.assertFalse(result['ssh_agent_required_for_local_preparation'])
        self.assertFalse(result['private_key_read_or_decrypted'])

    def test_explicit_identity_and_interactive_ssh_supported(self):
        key = self.root / 'existing_identity'
        commands = transport_plan('ubuntu@203.0.113.1', self.root, '/home/ubuntu/shimmer_experiments/test', key, interactive=True)
        self.assertIn(str(key.resolve()), commands['connect'])
        self.assertIn('IdentitiesOnly=yes', commands['connect'])
        self.assertIn('BatchMode=no', commands['connect'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    import execution_topology_checks
    suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Checks),
                               unittest.defaultTestLoader.loadTestsFromModule(execution_topology_checks)])
    stream = io.StringIO()
    def denied(*args, **kwargs):
        raise AssertionError('Local preparation tests prohibit network access')
    with patch.object(socket.socket, 'connect', denied), patch.object(socket.socket, 'connect_ex', denied), patch.object(socket, 'getaddrinfo', denied), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    value = {'passed': result.wasSuccessful(), 'tests_run': result.testsRun,
             'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
             'network_blocked': True, 'model_generation': False, 'gpu_workload': False,
             'failure_test_ids': [case.id() for case, _ in result.failures + result.errors]}
    if args.json:
        print(json.dumps(value, sort_keys=True))
    else:
        # Tracebacks can contain fixture values: report identifiers, never raw captures.
        print(json.dumps(value, indent=2))
        for case, details in result.failures + result.errors:
            print(case.id(), details.splitlines()[-1].split(':')[0])
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
