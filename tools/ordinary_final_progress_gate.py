"""Run the measured-progress proofs with network denied; neutralize, fail, restore, pass.

The readings are replayed from saved observations, so nothing here reaches an instance or
a provider. Each neutralization replaces one reader's honesty with a plausible shortcut (a
reading with its rate missing, an unanswered observation reported as zero) and the named
proof must FAIL while it is in force: a check that cannot fail proves nothing.

    py -3.12 tools/ordinary_final_progress_gate.py --output-dir docs/fix/ordinary_final_v13_gates
"""
import argparse
import io
import json
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    def denied(*args, **kwargs):
        raise AssertionError('Network prohibited')

    sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'scripts')]
    with patch.object(socket.socket, 'connect', denied), patch.object(socket, 'create_connection', denied):
        import ordinary_final_progress_checks as checks
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromModule(checks))

        def single(name):
            return unittest.TextTestRunner(stream=stream, verbosity=2).run(
                checks.ProgressReadings(name)).wasSuccessful()

        proofs = []
        for name, owner, attribute, mutant in checks.NEUTRALIZATIONS:
            before = single(name)
            with patch.object(owner, attribute, mutant):
                neutralized = single(name)
            after = single(name)
            proofs.append(dict(check=name, neutralized=attribute, passes_before=before,
                               neutralized_fail=not neutralized, passes_after_restore=after))

        receipt = dict(
            tests_run=result.testsRun,
            failures=[str(t) for t, _ in result.failures],
            errors=[str(t) for t, _ in result.errors],
            passed=result.wasSuccessful(),
            proofs=proofs,
            proofs_all_neutralized=all(p['neutralized_fail'] and p['passes_before'] and p['passes_after_restore']
                                       for p in proofs),
        )
        (out / 'progress_gate.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf8')
        (out / 'progress_gate.log').write_text(stream.getvalue(), encoding='utf8')
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if receipt['passed'] and receipt['proofs_all_neutralized'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output-dir', required=True)
    raise SystemExit(main(parser.parse_args().output_dir))
