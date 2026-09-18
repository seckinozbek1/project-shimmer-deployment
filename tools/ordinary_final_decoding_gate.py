"""Run the decoding gate: torch/transformers imported, weight loading and network denied."""
import argparse
import contextlib
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

    def no_load(*args, **kwargs):
        raise AssertionError('Model weight loading prohibited')
    sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'scripts')]
    import transformers
    with patch.object(socket.socket, 'connect', denied), patch.object(socket, 'create_connection', denied), \
            patch.object(transformers.AutoModelForCausalLM, 'from_pretrained', no_load), \
            patch.object(transformers.AutoModel, 'from_pretrained', no_load), \
            patch.object(transformers.PreTrainedModel, 'from_pretrained', no_load):
        import ordinary_final_decoding_checks as checks
        import decoding_policy
        import torch
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromModule(checks))

        def single(name):
            return unittest.TextTestRunner(stream=stream, verbosity=2).run(checks.DecodingFamilyChecks(name)).wasSuccessful()

        @contextlib.contextmanager
        def blind_recorder():
            yield []

        def no_policy(backend, root=None):
            return dict(backend=backend, status='neutralized', source='', sha256='', kwargs={})
        proofs = []
        for name, owner, attribute, mutant in [
                ('test_producer_family', decoding_policy, 'policy', no_policy),
                ('test_auditor_family', decoding_policy, 'policy', no_policy),
                ('test_redactor_family', decoding_policy, 'policy', no_policy),
                ('test_producer_family', checks, 'cumsum_recorder', blind_recorder),
                ('test_redactor_family', checks, 'cumsum_recorder', blind_recorder)]:
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
        receipt = dict(passed=result.wasSuccessful() and all(p['baseline_pass'] and p['neutralized_fail'] and p['restored_pass']
                                                             for p in proofs),
                       tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                       families=checks.REPORT, effect_proofs=proofs, torch=torch.__version__,
                       transformers=transformers.__version__, cuda_available=torch.cuda.is_available(),
                       device=torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                       deterministic_mode_restored=not torch.are_deterministic_algorithms_enabled(),
                       model_loads=0, network_allowed=False, generation_calls=0)
        (out / 'decoding_tests.log').write_text(stream.getvalue(), encoding='utf8')
        (out / 'decoding_validation.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf8')
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    raise SystemExit(main(parser.parse_args().output_dir))
