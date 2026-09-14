"""Capabilities + topology + prior safe gates, with credentials and models blocked."""
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
    import agent_wrapper
    agent_wrapper.load_api_keys = lambda: {}
    import brief_language_strategy_checks
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(brief_language_strategy_checks))
    if not result.wasSuccessful() or result.testsRun < 19:
        return 1
    import execution_topology_no_generation_gate
    return execution_topology_no_generation_gate.main()


if __name__ == "__main__":
    sys.exit(main())
