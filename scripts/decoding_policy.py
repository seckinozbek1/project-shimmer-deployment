"""Frozen decoding policy for every local generate site, read from the evaluation protocols.

The two generative roles were validated under explicit decoding kwargs that their
frozen evaluation protocols record: greedy, single beam, cached, with the stop set
and pad id of each family. The ordinary pipeline passed none of them, so each
checkpoint's own generation config governed generate(), and the Producer's
sampling config met strict deterministic mode at the first sampling step: the
top-p warper's floating-point CUDA cumsum has no deterministic implementation in
the pinned torch, and every local call raised RuntimeError there before its first
token (run 88323b86, 2026-09-17).

This module carries the protocol values to generate(). No decoding value is typed
here or in the wrapper: a restored backend reads its kwargs from the protocol file
named in config/decoding_policy.json, whose digest is pinned so an edit to the
protocol refuses the call instead of drifting silently. Only the evaluation-only
keys are withheld (max_new_tokens is an evaluation cap; the pipeline's per-agent
budget stays in force), and everything a protocol does not name
(repetition_penalty, temperature, top_k, top_p) stays with the checkpoint's own
generation config, exactly as during evaluation. A backend with no frozen
protocol declares a new policy in the same file and is reported as such.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECLARATION = "config/decoding_policy.json"
LOCAL_BACKENDS = ("local_producer", "local_auditor", "qwen_local")
STATUSES = ("restored", "new")


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def normalized(data):
    """Line endings are a checkout property; the pinned digest ignores them."""
    return data.replace(b"\r\n", b"\n")


def digest(data):
    return hashlib.sha256(normalized(data)).hexdigest()


def declaration(root=None):
    """The operator-visible declaration and its own digest."""
    data = (Path(root or ROOT) / DECLARATION).read_bytes()
    value = json.loads(normalized(data).decode("utf-8"))
    require(value.get("schema_version") == 1 and isinstance(value.get("backends"), dict),
            "Invalid decoding policy declaration")
    return value, digest(data)


def policy(backend, root=None):
    """The generate() kwargs for one local backend, with their provenance.

    Returns {backend, status, source, sha256, kwargs}. `kwargs` is a fresh dict on
    every call and is passed to generate() verbatim beside the call's own
    max_new_tokens budget. A restored backend's kwargs are the protocol's
    generation_kwargs minus the evaluation-only keys; the declaration's key list
    only says which keys the protocol is expected to carry, never their values.
    """
    root = Path(root or ROOT)
    value, declared = declaration(root)
    entry = value["backends"].get(backend)
    require(isinstance(entry, dict), "No decoding policy declared for backend " + repr(backend))
    require(entry.get("status") in STATUSES, "Unknown decoding policy status for backend " + repr(backend))
    withheld = tuple(value.get("evaluation_only_keys", ()))
    if entry["status"] == "restored":
        protocol = str(entry["protocol"])
        data = (Path(root) / protocol).read_bytes()
        require(digest(data) == entry["protocol_sha256"], "Decoding protocol drift: " + protocol)
        recorded = json.loads(normalized(data).decode("utf-8"))[entry["field"]]
        require(isinstance(recorded, dict), "Protocol field is not a kwargs object: " + protocol)
        kwargs = {k: v for k, v in recorded.items() if k not in withheld}
        require(sorted(kwargs) == sorted(entry["keys"]),
                "Protocol decoding keys differ from the declaration: " + protocol)
        source, sha = protocol, entry["protocol_sha256"]
    else:
        kwargs = dict(entry["policy"])
        source, sha = DECLARATION, declared
    require(not any(k in withheld for k in kwargs), "Evaluation-only key carried into the decoding policy")
    require(kwargs.get("do_sample") is False and kwargs.get("num_beams") == 1,
            "Decoding policy must be greedy and single-beam for backend " + repr(backend))
    return dict(backend=backend, status=entry["status"], source=source, sha256=sha, kwargs=kwargs)


def effective_eos(decoding, model):
    """The stop set generate() actually used: the policy's when it names one, else the model's own."""
    kwargs = decoding["kwargs"]
    if "eos_token_id" in kwargs:
        return kwargs["eos_token_id"]
    return getattr(getattr(model, "generation_config", None), "eos_token_id", None)


def usage_fields(decoding):
    """Payload-free provenance of the decoding in force, carried on the call's usage record."""
    return dict(decoding_policy_status=decoding["status"], decoding_policy_source=decoding["source"],
                decoding_policy_sha256=decoding["sha256"], decoding_kwargs=dict(decoding["kwargs"]))


def summary(root=None):
    """Every declared backend resolved; raises on the first drift or unsound policy."""
    value, _ = declaration(root)
    return {backend: policy(backend, root) for backend in sorted(value["backends"])}
