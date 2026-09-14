"""Mocked Lambda transport checks: no credentials, network, or provider actions."""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cloud_run_common import InvalidPreparation
from cloud_run_watchdog import LambdaTermination


class TransportChecks(unittest.TestCase):
    def setUp(self):
        self.fixture = 'TEST_CREDENTIAL_PLACEHOLDER'
        self.client = LambdaTermination()
        self.loader = self.enterContext(patch('cloud_run_watchdog.load_credential', return_value=self.fixture))
        self.find = self.enterContext(patch('cloud_run_watchdog.shutil.which', return_value='curl'))
        self.run = self.enterContext(patch('cloud_run_watchdog.subprocess.run'))
        self.run.return_value = SimpleNamespace(returncode=0, stdout='{"data": []}\n200', stderr='')

    def test_list_uses_bearer_stdin_and_bounded_https(self):
        self.assertEqual(self.client.request('instances'), {'data': []})
        args = self.run.call_args.args[0]
        kwargs = self.run.call_args.kwargs
        self.assertNotIn(self.fixture, repr(args))
        self.assertEqual(args[1], '--disable')
        self.assertEqual(args[-1], 'https://cloud.lambda.ai/api/v1/instances')
        self.assertIn('=https', args)
        self.assertNotIn('--location', args)
        self.assertEqual(args[args.index('--config') + 1], '-')
        self.assertEqual(kwargs['input'], 'header = "Authorization: Bearer ' + self.fixture + '"\n')
        self.assertEqual(kwargs['timeout'], 25)
        self.assertTrue(kwargs['capture_output'])
        self.assertFalse(kwargs.get('shell', False))
        self.assertNotIn('env', kwargs)

    def test_termination_posts_exactly_one_instance_without_credentials_in_argv(self):
        self.run.return_value.stdout = '{"data": {"terminated_instances": []}}\n200'
        self.assertIsNone(self.client.terminate('a' * 32))
        args = self.run.call_args.args[0]
        self.assertEqual(args[-1], 'https://cloud.lambda.ai/api/v1/instance-operations/terminate')
        self.assertEqual(json.loads(args[args.index('--data-binary') + 1]), {'instance_ids': ['a' * 32]})
        self.assertNotIn(self.fixture, repr(args))

    def test_config_quotes_and_backslashes_are_escaped(self):
        self.loader.return_value = self.fixture + '\\"'
        self.client.request('instances')
        config = self.run.call_args.kwargs['input']
        self.assertEqual(config, 'header = "Authorization: Bearer ' + self.fixture + '\\\\\\""\n')

    def test_no_other_host_endpoint_or_operation_allowed(self):
        invalid = [('https://example.invalid/instances', None), ('../instances', None),
                   ('instance-operations/launch', {'instance_ids': ['a' * 32]}),
                   ('instances', {}), ('instance-operations/terminate', None),
                   ('instance-operations/terminate', {'instance_ids': ['a' * 32, 'b' * 32]}),
                   ('instance-operations/terminate', {'instance_ids': ['invalid']}),
                   ('instance-operations/terminate', {'instance_ids': ['a' * 32], 'extra': True})]
        for path, body in invalid:
            with self.subTest(path=path), self.assertRaises(InvalidPreparation):
                self.client.request(path, body)
        self.loader.assert_not_called()
        self.run.assert_not_called()

    def test_missing_curl_fails_before_reading_credential(self):
        self.find.return_value = None
        with self.assertRaises(InvalidPreparation):
            self.client.request('instances')
        self.loader.assert_not_called()
        self.run.assert_not_called()

    def test_header_control_characters_rejected(self):
        for suffix in ['\n', '\r', '\0']:
            self.loader.return_value = self.fixture + suffix
            with self.assertRaises(InvalidPreparation):
                self.client.request('instances')
        self.run.assert_not_called()

    def test_http_failures_and_malformed_responses_never_expose_body(self):
        outputs = [self.fixture + '\n403', self.fixture + '\n301', self.fixture + '\n000',
                   self.fixture, self.fixture + '\n200', '[]\n200',
                   json.dumps({'error': self.fixture}) + '\n200',
                   json.dumps({'data': [], 'error': self.fixture}) + '\n200']
        for output in outputs:
            self.run.return_value = SimpleNamespace(returncode=0, stdout=output, stderr=self.fixture)
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                with self.assertRaises(InvalidPreparation) as raised:
                    self.client.request('instances')
            self.assertNotIn(self.fixture, str(raised.exception))
            self.assertEqual(stream.getvalue(), '')

    def test_subprocess_failures_do_not_expose_captured_output_or_command(self):
        for failure in [OSError(self.fixture), subprocess.TimeoutExpired(self.fixture, 25, output=self.fixture)]:
            self.run.side_effect = failure
            with self.assertRaises(InvalidPreparation) as raised:
                self.client.request('instances')
            self.assertEqual(str(raised.exception), 'provider transport failed')
            self.assertTrue(raised.exception.__suppress_context__)
        self.run.side_effect = None
        self.run.return_value = SimpleNamespace(returncode=7, stdout=self.fixture, stderr=self.fixture)
        with self.assertRaisesRegex(InvalidPreparation, '^provider transport failed$'):
            self.client.request('instances')


if __name__ == '__main__':
    unittest.main()
