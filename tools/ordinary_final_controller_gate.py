"""Run the mocked controller checks with network denied; neutralize, fail, restore, pass."""
import argparse
import io
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    def denied(*args, **kwargs):
        raise AssertionError('Network prohibited')
    sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'scripts')]
    with patch.object(socket.socket, 'connect', denied), patch.object(socket, 'create_connection', denied):
        import ordinary_final_controller_checks as checks
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(checks))

        def single(name):
            return unittest.TextTestRunner(stream=stream, verbosity=2).run(checks.ControllerChecks(name)).wasSuccessful()
        proofs = []
        for name, owner, attribute, mutant in checks.NEUTRALIZATIONS:
            invocations = []

            def replacement(*args, _mutant=mutant, **kwargs):
                invocations.append(1)
                return _mutant(*args, **kwargs)
            before = single(name)
            with patch.object(owner, attribute, replacement):
                failed = not single(name)
            after = single(name)
            proofs.append(dict(check=name, neutralized=owner.__name__ + '.' + attribute, baseline_pass=before,
                               neutralized_fail=failed and bool(invocations), restored_pass=after,
                               mutated_branch_invocations=len(invocations)))
        receipt = dict(passed=result.wasSuccessful() and all(p['baseline_pass'] and p['neutralized_fail'] and p['restored_pass'] for p in proofs),
                       tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), effect_proofs=proofs,
                       provider_mocked=True, ssh_mocked=True, clock_mocked=True, launches=0, network_allowed=False,
                       dead_connection_after_completion_recognised_as_completed=all(
                           p['baseline_pass'] for p in proofs if p['check'].startswith('test_dead_connection')))
        (out / 'controller_tests.log').write_text(stream.getvalue(), encoding='utf8')
        (out / 'controller_validation.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf8')
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    raise SystemExit(main(parser.parse_args().output_dir))
