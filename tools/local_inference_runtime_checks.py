"""Small offline tests for the process-local environment selection boundary."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import local_inference_runtime as runtime


class RuntimeChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'conda-meta').mkdir()
        (self.root/'conda-meta/pytorch-fixture.json').write_text(json.dumps(dict(name='pytorch', version='fixture')))
        self.package = self.root/'pkgs/pytorch-fixture'
        self.relative = 'Lib/site-packages/torch/__init__.py'
        self.source = self.package/self.relative
        self.source.parent.mkdir(parents=True)
        self.source.write_bytes(b'fixture')
        (self.package/'info').mkdir()
        (self.package/'info/paths.json').write_text(json.dumps(dict(paths=[
            dict(_path=self.relative, sha256=hashlib.sha256(b'fixture').hexdigest())])))
        self.enterContext(patch.object(sys, 'prefix', str(self.root)))
        self.enterContext(patch.object(sys, 'path', list(sys.path)))
        self.enterContext(patch.dict(os.environ, {}, clear=True))

    def test_verified_cache_is_selected_without_global_mutation(self):
        result = runtime.configure()
        self.assertEqual(result['verified_files'], 1)
        self.assertEqual(sys.path[0], str(self.package/'Lib/site-packages'))
        self.assertFalse(result['global_environment_modified'])
        self.assertEqual(os.environ['HF_HUB_OFFLINE'], '1')
        self.assertNotIn('KMP_DUPLICATE_LIB_OK', os.environ)

    def test_tampered_package_is_refused(self):
        self.source.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'integrity mismatch'):
            runtime.configure()

    def test_suppression_is_refused(self):
        os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
        with self.assertRaisesRegex(RuntimeError, 'suppression'):
            runtime.configure()

    def test_already_imported_torch_is_refused(self):
        with patch.dict(sys.modules, {'torch': object()}):
            with self.assertRaisesRegex(RuntimeError, 'before importing'):
                runtime.configure()

    def test_ambiguous_package_is_refused(self):
        (self.root/'conda-meta/pytorch-other.json').write_text(json.dumps(dict(name='pytorch', version='other')))
        with self.assertRaisesRegex(RuntimeError, 'Exactly one'):
            runtime.configure()

    def test_probe_records_real_call_result_before_contract_parsing(self):
        from local_inference_probe import response_record
        with patch.object(sys, 'path', [str(Path(__file__).resolve().parents[1]/'scripts')] + sys.path):
            from agent_wrapper import CallResult
        result = CallResult('local_auditor', 'fixture', '{"items":[]}', usage={'output_tokens': 5})
        row = response_record(type('Wrapper', (), {'name': 'VERIFIER'})(), result, 1.25, 'fixture')
        self.assertEqual(row['raw_text'], result.raw_text)
        self.assertEqual(row['usage']['output_tokens'], 5)
        self.assertEqual(row['wall_seconds'], 1.25)

    def test_missing_latency_does_not_invent_a_critical_path(self):
        with patch.object(sys, 'path', [str(Path(__file__).resolve().parents[1]/'scripts')] + sys.path):
            from run_projection import project
        result = project({'nodes': [{'id': 'first', 'parents': [], 'seconds': None}]})
        self.assertIsNone(result['critical_path'])
        self.assertEqual(result['semantic_waves'], 1)

    def test_existing_probe_evidence_is_not_overwritten(self):
        from local_inference_probe import supervise
        with patch('subprocess.Popen') as spawn:
            with self.assertRaisesRegex(ValueError, 'must be fresh'):
                supervise(self.root)
            spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
