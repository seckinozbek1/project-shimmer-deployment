"""Run the mocked controller checks with network denied; neutralize, fail, restore, pass."""
import argparse
import io
import json
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
# Proofs that cannot bite on some platforms, DECLARED here, never inferred from a skip: each
# entry is (the test, the os.name where it does not apply, why). A neutralised test's skip is
# accepted only when the table names that test, that platform and the skip's exact reason; any
# other skip (a missing file, no git, no shell) fails the proof, as before this table.
EXPECTED_SKIPS = {
    'test_detached_controller_survives_its_parent_and_the_reaper_ends_an_orphan':
        ('posix', 'the detached start is proven on the Windows operator machine'),
}
# A neutralisation that runs but cannot bite off Windows: (the neutralised name, the os.name where
# it does not apply, why). Gate check 292 skips the same proof off Windows.
PLATFORM_ONLY = {
    ('test_every_child_process_on_the_controller_path_starts_without_a_window', 'cloud_run_common.windows'):
        ('posix', 'the no-window flag is added only on Windows; elsewhere the helper adds nothing, so '
                  'making it add nothing changes nothing'),
}


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

        def run(name):
            return unittest.TextTestRunner(stream=stream, verbosity=2).run(checks.ControllerChecks(name))

        def single(name):
            return run(name).wasSuccessful()
        proofs = []
        for name, owner, attribute, mutant in checks.NEUTRALIZATIONS:
            label = owner.__name__ + '.' + attribute
            first = run(name)
            skipped = [reason for _, reason in first.skipped]
            declared = EXPECTED_SKIPS.get(name)
            if skipped:
                if first.wasSuccessful() and declared and os.name == declared[0] and skipped == [declared[1]]:
                    proofs.append(dict(check=name, neutralized=label, not_applicable=declared[1], platform=os.name))
                else:   # an undeclared skip proves nothing, so the proof fails
                    proofs.append(dict(check=name, neutralized=label, baseline_pass=False, neutralized_fail=False,
                                       restored_pass=False, undeclared_skip=skipped))
                continue
            only = PLATFORM_ONLY.get((name, label))
            if only and os.name == only[0]:
                proofs.append(dict(check=name, neutralized=label, not_applicable=only[1], platform=os.name))
                continue
            invocations = []
            if callable(mutant):
                def replacement(*args, _mutant=mutant, **kwargs):
                    invocations.append(1)
                    return _mutant(*args, **kwargs)
            else:
                # A neutralised constant (a freshness bound, the gate tree's attributes) is read,
                # never called, so its reads cannot be counted: the proof is the test failing
                # with the value in place.
                replacement = mutant
            before = first.wasSuccessful()
            with patch.object(owner, attribute, replacement):
                failed = not single(name)
            after = single(name)
            proof = dict(check=name, neutralized=label, baseline_pass=before,
                         neutralized_fail=failed and (bool(invocations) or not callable(mutant)), restored_pass=after,
                         mutated_branch_invocations=len(invocations) if callable(mutant) else None)
            if not callable(mutant):
                proof['constant_counted_by_failing_test'] = name
            proofs.append(proof)
        applicable = [p for p in proofs if 'not_applicable' not in p]
        receipt = dict(passed=result.wasSuccessful() and bool(applicable) and all(p['baseline_pass'] and p['neutralized_fail'] and p['restored_pass'] for p in applicable),
                       tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), effect_proofs=proofs,
                       provider_mocked=True, ssh_mocked=True, clock_mocked=True, launches=0, network_allowed=False,
                       dead_connection_after_completion_recognised_as_completed=all(
                           p['baseline_pass'] for p in applicable if p['check'].startswith('test_dead_connection')))
        (out / 'controller_tests.log').write_text(stream.getvalue(), encoding='utf8')
        (out / 'controller_validation.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf8')
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    raise SystemExit(main(parser.parse_args().output_dir))
