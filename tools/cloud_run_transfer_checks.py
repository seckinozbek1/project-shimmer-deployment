"""Local transfer-budget regression tests; no SSH, cloud calls, or model work."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from deploy_cloud_run import execute, run_transport, transport_plan, upload_timeout


class TransferChecks(unittest.TestCase):
    def test_ssh_upload_and_collection_share_connection_liveness_limits(self):
        for interactive in (False, True):
            plan = transport_plan('ubuntu@203.0.113.1', Path('fixture'),
                                  '/home/ubuntu/shimmer_experiments/fixture',
                                  identity_file=Path('existing_identity'), interactive=interactive)
            # Collection constructs its scp command from the same returned options.
            for name in ('connect', 'gpu_before_transfer', 'create', 'upload', 'ssh', 'options'):
                with self.subTest(interactive=interactive, command=name):
                    command = plan[name]
                    for setting in ('ConnectTimeout=10', 'ServerAliveInterval=15', 'ServerAliveCountMax=3'):
                        self.assertEqual(command.count(setting), 1)
                        self.assertEqual(command[command.index(setting) - 1], '-o')
                    self.assertIn('IdentitiesOnly=yes', command)
                    self.assertIn('BatchMode=no' if interactive else 'BatchMode=yes', command)

    def test_transport_timeout_propagates_without_retrying_model_command(self):
        plan = transport_plan('ubuntu@203.0.113.1', Path('fixture'),
                              '/home/ubuntu/shimmer_experiments/fixture')
        command = plan['ssh'] + ['python3.12 cloud_run_remote.py --execute']
        with patch('deploy_cloud_run.subprocess.run',
                   side_effect=subprocess.TimeoutExpired(command, 120)) as runner:
            with self.assertRaises(subprocess.TimeoutExpired):
                run_transport(command, 120, runner=runner)
        runner.assert_called_once()
        self.assertEqual(runner.call_args.kwargs['timeout'], 120)

    def test_upload_can_exceed_previous_five_minute_limit(self):
        self.assertEqual(upload_timeout(1200, terminate_epoch=5000, now=1000), 1200)

    def test_upload_leaves_cleanup_time_before_termination(self):
        self.assertEqual(upload_timeout(1200, terminate_epoch=1700, now=1000), 580)

    def test_upload_refuses_exhausted_transfer_budget(self):
        for deadline in (1120, 1100):
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                upload_timeout(1200, terminate_epoch=deadline, now=1000)

    def test_invalid_upload_limits_are_rejected(self):
        for requested in (0, -1, float('nan'), float('inf'), True, '1200'):
            with self.subTest(requested=str(requested)), self.assertRaises(ValueError):
                upload_timeout(requested, terminate_epoch=5000, now=1000)

    def test_dry_run_exposes_default_and_explicit_timeout(self):
        for requested in (None, 900):
            args = SimpleNamespace(bundle=Path('fixture'), host='ubuntu@203.0.113.1',
                                   running_since='2026-09-14T00:00:00Z', execute=False)
            if requested is not None:
                args.upload_timeout_seconds = requested
            with patch('deploy_cloud_run.plan', return_value={}), \
                 patch('cloud_run_watchdog.operator_preflight',
                       return_value={'ssh_public_key_sha256': 'fixture'}), \
                 patch.object(Path, 'read_text', return_value='{"ssh_public_key_sha256":"fixture"}'), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                result = execute(args, runner=lambda *a, **k: self.fail('transport called during dry run'))
            self.assertEqual(result, 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report['upload_timeout_seconds'], 1200 if requested is None else requested)
            self.assertEqual(report['upload_cleanup_reserve_seconds'], 120)
            self.assertFalse(report['network_contacted'])


if __name__ == '__main__':
    unittest.main()
