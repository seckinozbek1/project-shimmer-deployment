"""Prove, inside the container with the network blocked, that a WORD DECISION
can be made at all.

Item ZERO-C / item SIXTEEN. The five-voter ensemble decides redaction intent and
shape authorisation from what words MEAN, against operator-visible references,
using the embedding model this project ships. That makes the weights
load-bearing for a parse-time decision: without them the ensemble refuses and
the product cannot do the thing the WORDS chain built.

This probe answers the question by doing it, not by asserting it. Run with
`--network none` and nothing mounted:

    docker run --rm --network none --gpus all --entrypoint python shimmer:zero-c \
        tools/container_offline_probe.py

Exit 0 means the container made every decision offline. Non-zero names what it
could not do and why, which is the honest answer to SIXTEEN rather than a note.
"""

from __future__ import annotations

import os
import math
import socket
import sys
import traceback
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

FAILURES = []
NETWORK_ATTEMPTS = []


def _blocked_network(*args, **kwargs):
    NETWORK_ATTEMPTS.append(True)
    raise OSError("offline probe: network attempt refused")


def _validate_votes(record):
    import semantic_ensemble as se
    votes = record.get("votes", [])
    if (len(votes) != 5 or {v.get("voter") for v in votes} != set(se.VOTER_NAMES)
            or any(not v.get("available") or not isinstance(v.get("vote"), bool)
                   or not isinstance(v.get("score"), (int, float))
                   or not math.isfinite(v["score"]) or not v.get("matched")
                   for v in votes)):
        raise RuntimeError("decision lacks five available votes, scores and references")


def step(label, fn):
    try:
        detail = fn()
        print("  PASS  %-46s %s" % (label, detail or ""))
    except Exception as exc:
        FAILURES.append((label, "%s: %s" % (type(exc).__name__, exc)))
        print("  FAIL  %-46s %s: %s" % (label, type(exc).__name__, exc))
        if os.environ.get("PROBE_TRACE"):
            traceback.print_exc()


def _weights_present():
    hub = Path(os.environ.get("HF_HOME", "/root/.cache/huggingface")) / "hub"
    names = sorted(p.name for p in hub.iterdir()
                   if p.is_dir() and p.name.startswith("models--")) if hub.is_dir() else []
    if not any("bge-m3" in n for n in names):
        raise RuntimeError("bge-m3 is not in %s (found %r)" % (hub, names))
    return "%d model(s) cached" % len(names)


def _references_present():
    import semantic_ensemble as se
    refs = se.load_references()
    thr = se.load_thresholds()
    missing = [d for d in ("redaction_intent", "shape_identifier", "shape_figure",
                           "shape_name") if d not in refs or d not in thr]
    if missing:
        raise RuntimeError("no references or thresholds for %r" % missing)
    decisions = [name for name, value in refs.items()
                 if isinstance(value, dict) and "positive" in value and "negative" in value]
    return "%d decisions declared" % len(decisions)


def _model_loads_offline():
    # No network is available at all; if this reaches out it fails here, which
    # is the point. HF_HUB_OFFLINE is NOT set on purpose: the claim is that the
    # code does not need it, not that a flag hides the attempt.
    import embedding_store as es
    st = es._try_import_st()
    if st is None:
        raise RuntimeError("sentence-transformers is not importable in the image")
    name, model = es._resolve_model(st, es.DEFAULT_MODEL_NAME)
    if model is None:
        raise RuntimeError("the embedding model did not load from the image cache")
    if name != es.DEFAULT_MODEL_NAME:
        raise RuntimeError("the loader substituted a different embedding model")
    if NETWORK_ATTEMPTS:
        raise RuntimeError("the cached load attempted network access")
    return "loaded %s" % name


def _decision_redaction_intent():
    import semantic_ensemble as se
    active = "The reviewer must not publish the client address."
    r = se.decide(active, "redaction_intent")
    _validate_votes(r)
    if not r["result"]:
        raise RuntimeError("the active prohibition was not read as redaction "
                           "intent (%d of %d)" % (r["yes"], r["of"]))
    return "%d of %d voters, all five reported" % (r["yes"], r["of"])


def _decision_shape_authorisation():
    import semantic_ensemble as se
    from sensitivity_layer import redaction_detect as rd
    from sensitivity_layer.redaction_detect import load_cues, authorized_shapes
    cues = load_cues(str(ROOT))
    if not cues:
        raise RuntimeError("the language cue resource did not load")
    fixture = [{"id": "C", "rule": "Mask the account number.",
                "category": "confidentiality"}]
    with patch.object(rd, "_ensemble_authorises", return_value=False):
        if authorized_shapes(fixture, cues):
            raise RuntimeError("BADFIXTURE: cue words already authorise this fixture")
    decision = se.decide(fixture[0]["rule"], "shape_identifier")
    _validate_votes(decision)
    auth = authorized_shapes(fixture, cues)
    if "identifier" not in auth:
        raise RuntimeError("'Mask the account number' authorised no detector, so "
                           "the ensemble half of the union is not working offline")
    return "authorised %s" % ",".join(sorted(auth))


def _full_redaction_compile():
    from sensitivity_layer.rules import redaction_rules
    out = redaction_rules({"conventions": [
        {"id": "CONV-X", "category": "conformance", "action": "flag",
         "action_declared": False, "severity": "required",
         "rule": "Salary bands are confidential and are removed before delivery."}]})
    if not out["operator_in_force"]:
        raise RuntimeError("a rule only the ensemble can reach did not compile")
    votes = out.get("semantic_votes") or []
    if not votes or not votes[0].get("available"):
        raise RuntimeError("the ensemble did not run inside redaction_rules")
    for record in votes:
        _validate_votes(record)
    return "compiled, %d vote record(s) carried" % len(votes)


def main():
    import requests
    FAILURES.clear()
    NETWORK_ATTEMPTS.clear()
    print("container offline probe: network blocked, nothing mounted")
    print("  HF_HOME=%s" % os.environ.get("HF_HOME", "(unset)"))
    # Docker's --network none provides isolation. These guards additionally
    # detect attempted access, so retries cannot hide behind a later fallback.
    with patch.object(requests.Session, "send", _blocked_network), \
            patch.object(socket.socket, "connect", _blocked_network), \
            patch.object(socket.socket, "connect_ex", _blocked_network), \
            patch.object(socket, "getaddrinfo", _blocked_network):
        step("weights present in the image", _weights_present)
        step("references and thresholds present", _references_present)
        step("embedding model loads with no network", _model_loads_offline)
        step("word decision: redaction intent", _decision_redaction_intent)
        step("word decision: shape authorisation", _decision_shape_authorisation)
        step("redaction rule compiles through the ensemble", _full_redaction_compile)
    if NETWORK_ATTEMPTS:
        FAILURES.append(("network access", "%d attempts" % len(NETWORK_ATTEMPTS)))
    print()
    if FAILURES:
        print("OFFLINE PROBE FAILED: %d failures" % len(FAILURES))
        for label, why in FAILURES:
            print("  %s -> %s" % (label, why))
        return 1
    print("OFFLINE PROBE PASSED: the container makes every word decision with no "
          "network and nothing mounted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
