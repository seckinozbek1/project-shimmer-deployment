"""Controller proofs of item 16 (the 16 November b1 activation): an instance still booting with no public IP yet is not
ready, never a refusal; a metadata refusal keeps its message in controller_failure.json, and every such message names
a declared field only, never a value. The tests live in ActivationChecks, mixed into
ordinary_final_controller_checks.ControllerChecks; each rule is proven by neutralise, fail, restore, pass through
ACTIVATION_NEUTRALIZATIONS.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / 'tools'), str(ROOT / 'scripts')):
    if _path not in sys.path:
        sys.path.insert(0, _path)
import cloud_run_common as common  # noqa: E402
import ordinary_final_cloud as controller  # noqa: E402

SENTINEL = 'SYNTHETIC-sentinel-value'


def booting_then(provider_class, states):
    """The fake provider's instance() answering `states` (each merged over its own answer) first, then as itself."""
    real = provider_class.instance
    queue = list(states)

    def instance(self, instance_id):
        value = real(self, instance_id)
        return dict(value, **queue.pop(0)) if queue else value
    return patch.object(provider_class, 'instance', instance)


class ActivationChecks:
    def test_an_instance_booting_with_no_public_ip_yet_is_not_ready_and_then_launches(self):
        """Item 16 (b): while the instance is not yet active, a public IP that is missing, null or empty is read as not
        ready; activation goes on polling and the run launches once it is active with its address."""
        import ordinary_final_controller_checks as checks
        states = [dict(status='booting', public_ip=None), dict(status='booting', public_ip=''),
                  dict(status='unhealthy', public_ip=None)]
        with booting_then(checks.FakeProvider, states):
            transport, console, failure = self.execute()
        self.assertIsNone(failure, failure)
        self.assertIn('ordinary_workload', transport.started)

    def test_an_active_instance_with_a_bad_address_keeps_the_field_only_message(self):
        """Item 16 (a): an active instance whose public IP is not an address stops the run, and controller_failure.json
        keeps the InvalidPreparation message, which names the field and never the value."""
        import ordinary_final_controller_checks as checks
        with booting_then(checks.FakeProvider, [dict(status='active', public_ip=SENTINEL)]):
            transport, console, failure = self.execute()
        self.assertIsNotNone(failure)
        self.assertEqual(failure['error_type'], 'InvalidPreparation')
        self.assertEqual(failure['message'], 'invalid metadata: public_ip')
        self.assertNotIn(SENTINEL, json.dumps(failure))
        self.assert_torn_down()

    def test_every_metadata_refusal_names_a_declared_field_and_no_value(self):
        """Item 16 (a): every refusal safe_metadata and the provider projection can give, for every declared field fed
        a bad value carrying a sentinel, is an InvalidPreparation whose message is a fixed prefix and the field name."""
        prefixes = ('invalid numeric metadata: ', 'invalid metadata: ', 'credential in metadata: ',
                    'credential marker in metadata: ')
        bad = {key: (-1 if key in common.NUMBER_FIELDS else SENTINEL + ' token' if key in common.TEXT_FIELDS
                     else SENTINEL) for key in common.METADATA_FIELDS}
        for key, value in bad.items():
            with self.subTest(field=key):
                with self.assertRaises(common.InvalidPreparation) as caught:
                    common.safe_metadata({'status': 'active', key: value})
                message = str(caught.exception)
                self.assertNotIn(SENTINEL, message)
                self.assertIn(message, [p + key for p in prefixes])
        raw = dict(id='a' * 32, status='active', ip=SENTINEL, instance_type=dict(name='gpu_1x_a10', specs={}))
        with self.assertRaises(common.InvalidPreparation) as caught:
            common.provider_instance(raw)
        self.assertEqual(str(caught.exception), 'invalid provider instance metadata: invalid metadata: public_ip')


def leaking_message(prefix, key):
    return prefix + key + ' ' + SENTINEL


ACTIVATION_NEUTRALIZATIONS = [
    ('test_an_instance_booting_with_no_public_ip_yet_is_not_ready_and_then_launches', common, 'ip_not_ready',
     lambda raw: False),
    ('test_an_active_instance_with_a_bad_address_keeps_the_field_only_message', controller, 'KEPT_MESSAGES',
     (RuntimeError,)),
    ('test_every_metadata_refusal_names_a_declared_field_and_no_value', common, 'field_message', leaking_message),
]
