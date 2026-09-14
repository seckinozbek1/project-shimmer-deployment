"""Explicit safe subset. Never invoke the full model-loading verification gate."""
import builtins
import socket
import sys
import unittest


def main():
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "transformers", "sentence_transformers", "anthropic", "openai", "easyocr"}:
            raise AssertionError("Prohibited model/provider import")
        return original(name, *args, **kwargs)

    def denied(*args, **kwargs):
        raise AssertionError("Network prohibited in no-generation validation")

    builtins.__import__ = guarded
    socket.create_connection = denied
    socket.socket.connect = denied
    import multi_round_checks
    suite = unittest.defaultTestLoader.loadTestsFromModule(multi_round_checks)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    import verify_session1 as legacy
    allowed = {"00", "01", "02", "03", "04", "07", "21", "22", "29", "260"}
    failed = False
    for title, check in legacy.CHECKS:
        if title.split()[0] not in allowed:
            continue
        status, detail = check()
        print(title.split()[0], status, detail)
        failed = failed or status not in {"PASS", "SKIP", "WARN"}
    print("Full gate: NOT RUN (contains prohibited model/GPU checks).")
    return 0 if result.wasSuccessful() and result.testsRun > 0 and not failed else 1


if __name__ == "__main__":
    sys.exit(main())
