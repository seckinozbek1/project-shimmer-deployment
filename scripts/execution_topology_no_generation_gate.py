"""Topology fixtures plus the established safe gate. No full model gate."""
import builtins
import socket
import sys
import unittest


def main():
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "transformers", "sentence_transformers", "anthropic", "openai", "easyocr"}:
            raise AssertionError("Model/provider import prohibited")
        return original(name, *args, **kwargs)
    def denied(*args, **kwargs):
        raise AssertionError("Network prohibited")
    builtins.__import__ = guarded
    socket.create_connection = denied
    socket.socket.connect = denied
    import execution_topology_checks
    suite = unittest.defaultTestLoader.loadTestsFromModule(execution_topology_checks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.testsRun < 18:
        return 1
    import multi_round_no_generation_gate
    return multi_round_no_generation_gate.main()


if __name__ == "__main__":
    sys.exit(main())
