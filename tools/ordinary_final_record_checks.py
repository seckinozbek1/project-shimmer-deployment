"""Controller proofs of the seal request's launch record (order 85, D-675; the checker's items 1, 2, 5, 12 and 13): the real
controller driven on the controller checks' fakes, for a record launch and for an ordinary bundle launch. The tests
live in RecordChecks, mixed into ordinary_final_controller_checks.ControllerChecks; each rule is proven by
neutralise, fail, restore, pass through RECORD_NEUTRALIZATIONS.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / 'tools'), str(ROOT / 'scripts')):
    if _path not in sys.path:
        sys.path.insert(0, _path)
import ordinary_final_cloud as controller  # noqa: E402
import ordinary_final_run as runner  # noqa: E402
from ordinary_final_run import read, write, sha  # noqa: E402


def ledger_intents(ledger):
    return [json.loads(line) for line in Path(ledger).read_text(encoding='utf-8').splitlines()
            if line.strip() and json.loads(line).get('event') == 'launch_intent']


def support_transfer(transport):
    return next((argv for argv, _ in transport.calls if argv[0] == 'scp' and any('execution_manifest.json' in a for a in argv)), [])


def phases(transport, *labels):
    """The commands the named detached phases ran, decoded as the instance receives them."""
    from ordinary_final_aux_env_checks import phase_script
    return {label: phase_script(transport, label) or '' for label in labels}


class RecordChecks:
    def make_record(self, layers=None):
        """The fixture bundle turned into a seal request's launch record as seal_route.launch_record makes one: the
        job files as support files, the request file, no project archive, arm S, kind and request digest."""
        manifest = read(self.base / 'execution_manifest.json')
        (self.base / 'project.tar.gz').unlink()
        support = {}
        for name in runner.SEAL_SUPPORT + ('seal_request.json',):
            data = json.dumps({'commit': 'a' * 40, 'tree': 'b' * 40, 'requests': []}).encode() if name == 'seal_job.json' \
                else ('fixture ' + name).encode()
            (self.base / name).write_bytes(data)
            support[name] = sha(self.base / name)
        manifest.update(kind=controller.LAUNCH_RECORD_KIND, arm='S', argv=list(runner.SEAL_ARGV),
                        seal_job={'commit': 'a' * 40, 'tree': 'b' * 40, 'requests': []}, support_files=support,
                        source_archive_sha256=None, request_sha256=support['seal_request.json'])
        if layers:
            manifest['layers'] = layers
        write(self.base / 'execution_manifest.json', manifest)
        digest = json.loads((self.base / 'assets_transfer_archive.json').read_text())['sha256']
        write(self.base / 'seal.json', dict(execution_manifest_sha256=sha(self.base / 'execution_manifest.json'),
                                            kind=controller.LAUNCH_RECORD_KIND))
        write(self.base / 'AUTHORIZED_LOCAL_REVERIFICATION.json', dict(passed=True, manifest_sha256=sha(self.base / 'execution_manifest.json')))
        write(self.base / 'assets_transfer_archive.json', dict(path=None, sha256=digest, bytes=1,
                                                              manifest_sha256=sha(self.base / 'execution_manifest.json')))
        return digest

    def test_a_record_launch_takes_the_copy_uploads_no_project_and_names_the_instance_seal(self):
        """Items 1 and 2: a record's run uploads no project archive, uses the provider-side copy, hashes and extracts
        the asset archive alone, and its ledger lines carry seal_on instance."""
        digest = self.make_record()
        self.declare_copy(digest=digest)
        transport, console, failure = self.execute(require_copy=True, mount=dict(present=True, files={digest: digest}),
                                                   plan=self.plan(forecast_includes_upload=False))
        self.assertIsNone(failure, failure)
        self.assertTrue(self.copy_receipt()['used'])
        self.assertFalse(any(a.endswith('project.tar.gz') for a in support_transfer(transport)))
        ran = phases(transport, 'archive_integrity', 'extract_payload')
        self.assertTrue(all(ran.values()), ran)
        self.assertFalse([c for c in ran.values() if 'project.tar.gz' in c], ran)
        self.assertIn('assets.tar', ran['archive_integrity'])
        self.assertFalse(self.scp_assets_argv(transport))
        self.assertEqual({i.get('seal_on') for i in ledger_intents(self.ledger)}, {'instance'})

    def test_a_record_whose_copy_is_not_used_stops_and_uploads_nothing(self):
        """Item 1: a record with a declared copy that is MISSING on the filesystem stops (no laptop archive exists),
        never falling back to the upload."""
        digest = self.make_record()
        self.declare_copy(digest=digest)
        transport, console, failure = self.execute(require_copy=True, mount=dict(present=True, files={}),
                                                   plan=self.plan(forecast_includes_upload=False))
        self.assertIsNotNone(failure)
        self.assertIn(controller.RECORD_COPY_REFUSAL, failure['message'])
        self.assertFalse(self.scp_assets_argv(transport))

    def test_a_record_with_no_usable_copy_or_with_layers_is_refused_before_any_instance(self):
        """Items 2 and 13: a record with no declared copy, or carrying image layers, is refused before any instance."""
        import ordinary_final_controller_checks as checks
        self.make_record()
        with self.assertRaisesRegex(RuntimeError, 'needs the declared provider-side copy'):
            self.execute(plan=self.plan(forecast_includes_upload=False))
        self.assertEqual((checks.FakeProvider.state or {}).get('launches', 0), 0)
        self.setUp()
        digest = self.make_record(layers={'spec': 'image_spec.json', 'keys': []})
        self.declare_copy(digest=digest)
        with self.assertRaisesRegex(RuntimeError, 'carries no image layers'):
            self.execute(require_copy=True, mount=dict(present=True, files={digest: digest}),
                         plan=self.plan(forecast_includes_upload=False))
        self.assertEqual((checks.FakeProvider.state or {}).get('launches', 0), 0)

    def test_an_ordinary_bundle_keeps_its_project_and_its_upload_and_names_no_instance_seal(self):
        """Item 1 (the name clash): an ordinary bundle still uploads and hashes its project archive, falls back to the
        upload with no copy, and its ledger lines name no instance seal."""
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        self.assertTrue(any(a.endswith('project.tar.gz') for a in support_transfer(transport)))
        ran = phases(transport, 'archive_integrity', 'extract_payload')
        self.assertTrue(all('project.tar.gz' in c for c in ran.values()), ran)
        self.assertTrue(self.scp_assets_argv(transport))
        # Item 12: every launch names where its bundle was sealed; one no admission lists was sealed on the laptop.
        self.assertEqual({i.get('seal_on') for i in ledger_intents(self.ledger)}, {'laptop'})

    def test_a_bundle_its_admission_lists_names_the_instance_seal_and_a_changed_one_the_laptop(self):
        """Item 12: a bundle a seal job sealed on the instance, listed by the admission.json beside it under its own name
        and manifest digest, launches with seal_on instance; the same listing naming another digest reads laptop."""
        def admitted(digest):
            write(self.base.parent / 'admission.json', dict(rows=[dict(name=self.base.name, binding=digest, admitted=True)]))
        admitted(sha(self.base / 'execution_manifest.json'))
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        self.assertEqual({i.get('seal_on') for i in ledger_intents(self.ledger)}, {'instance'})
        self.setUp()
        admitted('0' * 64)
        transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        self.assertEqual({i.get('seal_on') for i in ledger_intents(self.ledger)}, {'laptop'})

    def test_a_batch_refuses_a_launch_record_entry_before_any_instance(self):
        """Item 5: batch_entries run on a batch whose entry is a launch record (its seal naming it) refuses it, before
        any provider call."""
        import ordinary_final_controller_checks as checks
        import seal_route
        bundles, entries = self.batch_bundles()
        folder = bundles[('i2', 'B1')]
        manifest = read(folder / 'execution_manifest.json')
        manifest['kind'] = seal_route.LAUNCH_RECORD_KIND
        write(folder / 'execution_manifest.json', manifest)
        write(folder / 'seal.json', dict(read(folder / 'seal.json'), execution_manifest_sha256=sha(folder / 'execution_manifest.json')))
        with self.assertRaisesRegex(RuntimeError, 'refused as a batch entry'):
            self.execute(plan=checks.fixture_plan(self.ledger, batch=entries))
        self.assertEqual((checks.FakeProvider.state or {}).get('launches', 0), 0)


def no_refusal(*args):
    return None


RECORD_NEUTRALIZATIONS = [
    ('test_a_record_launch_takes_the_copy_uploads_no_project_and_names_the_instance_seal', controller, 'seal_place',
     lambda launch_record: 'laptop'),
    ('test_a_record_whose_copy_is_not_used_stops_and_uploads_nothing', controller, 'record_upload_refusal', no_refusal),
    # Every bundle read as a record (the name clash the checker found): the ordinary launch breaks.
    ('test_an_ordinary_bundle_keeps_its_project_and_its_upload_and_names_no_instance_seal', controller,
     'LAUNCH_RECORD_KIND', None),
    ('test_a_record_with_no_usable_copy_or_with_layers_is_refused_before_any_instance', controller,
     'RECORD_NO_COPY_REFUSAL', 'another message'),
    ('test_a_bundle_its_admission_lists_names_the_instance_seal_and_a_changed_one_the_laptop', controller,
     'bundle_seal_place', lambda record, base: 'laptop'),
    # The batch rule reads the controller's own kind name: neutralised, a record entry is taken.
    ('test_a_batch_refuses_a_launch_record_entry_before_any_instance', controller, 'LAUNCH_RECORD_KIND', 'another kind'),
]
