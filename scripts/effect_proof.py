"""Small, explicit mutation proofs for declared consumer outcomes.

This cannot discover the right consumer or observation. Each caller names both.
No observed effect means an inconclusive mutation, not evidence of a weak check.
"""
from __future__ import annotations

import json


class ProofFailure(AssertionError):
    def __init__(self, category):
        self.category = category
        super().__init__(category)


def _invoke(function, category):
    try:
        return function()
    except ProofFailure:
        raise
    except Exception:
        # Exception messages can contain input data. A broken probe is not a
        # successful mutation proof, even if an ordinary assertion went red.
        raise ProofFailure(category) from None


def _observation(observe):
    value = _invoke(observe, "OBSERVATION_ERROR")
    try:
        # Snapshot mutable values, reject non-JSON objects and non-finite floats.
        return json.dumps(value, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError):
        raise ProofFailure("INVALID_OBSERVATION") from None


def _verdict(check):
    result = _invoke(check, "CHECK_ERROR")
    if not isinstance(result, tuple) or len(result) != 2 or result[0] not in ("PASS", "FAIL"):
        raise ProofFailure("INVALID_CHECK_RESULT")
    return result[0]


def prove_effect(*, name, validate, observe, check, neutralise):
    """Validate inputs, observe, mutate, re-observe, consult, restore and verify.

    validate must return True for the declared INPUTS, never generated outputs.
    observe independently executes the consumer and returns its stable JSON-safe
    outcome. It must not call check or return a test verdict. neutralise returns
    a context manager that restores the mutation even when a probe raises.

    NO_OBSERVED_EFFECT refuses to consult the mutated check. Investigate safe
    fallthrough AND incomplete observations before diagnosing the check. SURVIVED
    means the outcome changed but the check stayed green. Neither is a PASS.
    Restoration compares outcomes as well as requiring the check to pass again.
    """
    if _invoke(validate, "FIXTURE_ERROR") is not True:
        raise ProofFailure("BAD_FIXTURE")
    before = _observation(observe)
    if _verdict(check) != "PASS":
        raise ProofFailure("BASELINE_FAILED")
    failure = None
    changed = None
    try:
        with neutralise():
            changed = _observation(observe)
            if changed == before:
                raise ProofFailure("NO_OBSERVED_EFFECT")
            if _verdict(check) != "FAIL":
                raise ProofFailure("SURVIVED")
    except ProofFailure as exc:
        failure = exc
    except Exception:
        failure = ProofFailure("MUTATION_ERROR")
    finally:
        restored = _observation(observe)
        restored_verdict = _verdict(check)
        if restored != before or restored_verdict != "PASS":
            raise ProofFailure("RESTORATION_FAILED")
    if failure is not None:
        raise failure
    return {"name": name, "status": "PASS", "before": json.loads(before),
            "mutated": json.loads(changed), "restored": json.loads(restored)}
