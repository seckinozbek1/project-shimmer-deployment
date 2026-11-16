"""The resident vLLM server of the vLLM route (D-630 part A, #217), protocol `vllm-link-v1`
(scripts/vllm_link.py is the contract). Run in the auxiliary environment's own Python on the
instance, one process per local model, spoken to over standard input and output:

    <venv_aux>/bin/python -u scripts/vllm_server.py

It decides nothing: it generates the token ids a request asks for, under the frozen decoding
(vllm_child.params, the one builder of the sampling parameters) and the request's own
constraint, and returns them. The protocol channel is a private duplicate of the original
standard output; fd 1 and sys.stdout then point at standard error, so a library's print
(vLLM logs to stdout) never lands on the channel. The runner's network denial is applied
before vLLM is imported. A start failure is a hello with an error and exit 3; one failing
request is a reply with an error and the server keeps serving.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "benchmark" / "baselines")]

import vllm_link  # noqa: E402


def private_channel():
    """The protocol channel: the original standard output, duplicated; fd 1 goes to standard error."""
    proto = os.fdopen(os.dup(1), "w", encoding="utf-8", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return proto


def say(proto, message):
    proto.write(vllm_link.server_line(message))
    proto.flush()


def start(job):
    """Import, build the engine, check the token table. Returns (llm, hello)."""
    os.environ["SHIMMER_CONSTRAINT_TOKENIZER"] = job["tokenizer"]
    imported = time.perf_counter()
    import torch
    import vllm
    import_seconds = round(time.perf_counter() - imported, 3)
    import vllm_child
    import vllm_constraint
    started = time.perf_counter()
    with vllm_child.StartLog() as log:
        llm = vllm_child.engine(job)
    engine_seconds = round(time.perf_counter() - started, 3)
    digest = vllm_constraint.table_digest(vllm_constraint.tokenizer(job["tokenizer"]))
    if digest != job["token_table_sha256"]:
        raise RuntimeError("the token table differs from the runner's; the constraint would read replies differently")
    return llm, {"op": "hello", "protocol": vllm_link.PROTOCOL,
                 "versions": {"vllm": vllm.__version__, "torch": torch.__version__,
                              "batch_invariant": os.environ.get("VLLM_BATCH_INVARIANT")},
                 "loaded": vllm_child.loaded(llm), "token_table_sha256": digest,
                 "import_seconds": import_seconds, "engine_seconds": engine_seconds,
                 "engine_phases": log.record(),
                 "aux_env": vllm_child.aux_env_size()}


def generate(llm, job, req):
    """One request, one vLLM request, built as vllm_child builds it. Returns the reply."""
    import vllm_child
    import vllm_constraint
    from vllm.inputs import TokensPrompt
    key = "link:" + str(req["id"])
    try:
        constraint = req["constraint"]
        p = {"max_new_tokens": req["max_new_tokens"], "eos": req["eos"], "constraint": constraint,
             "key": key, "token_ids": req["token_ids"]}
        started = time.perf_counter()
        out = llm.generate([TokensPrompt(prompt_token_ids=req["token_ids"])], [vllm_child.params(job, p)],
                           lora_request=None, use_tqdm=False)[0]
        seconds = round(time.perf_counter() - started, 3)
        first = out.outputs[0]
        counts = vllm_constraint.COUNTS.get(key)
        return {"op": "reply", "id": req["id"], "token_ids": list(first.token_ids),
                "finish_reason": first.finish_reason, "seconds": seconds,
                "constraint": dict(counts) if constraint is not None and counts is not None else None}
    finally:
        vllm_constraint.COUNTS.pop(key, None)


def serve(proto, llm, job, stdin):
    for line in stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except ValueError:
            say(proto, {"op": "reply", "id": None, "error": "the request is not JSON"})
            continue
        if isinstance(req, dict) and req.get("op") == "shutdown":
            return 0
        rid = req.get("id") if isinstance(req, dict) else None
        problem = vllm_link.request_error(req) if isinstance(req, dict) else "the request is not an object"
        if problem:
            say(proto, {"op": "reply", "id": rid, "error": problem})
            continue
        try:
            reply = generate(llm, job, req)
        except Exception as exc:  # one request failing never stops the server
            reply = {"op": "reply", "id": rid, "error": ("%s: %s" % (type(exc).__name__, exc))[:400]}
        say(proto, reply)
    return 0


def main(argv=None, stdin=None):
    proto = private_channel()
    stdin = stdin if stdin is not None else sys.stdin
    llm = job = None
    try:
        job = json.loads(stdin.readline())
        problem = vllm_link.job_error(job) if isinstance(job, dict) else "the job is not an object"
        if problem:
            say(proto, {"op": "hello", "error": problem[:400]})
            return 3
        import vllm_child
        vllm_child.deny_network(job, os.environ.get("SHIMMER_VLLM_LOG_DIR") or os.getcwd())
        llm, hello = start(job)
    except Exception as exc:
        import vllm_child
        say(proto, {"op": "hello", "error": ("%s: %s" % (type(exc).__name__, exc))[:400],
                    "traceback": vllm_child.traceback_frames(exc)})
        return 3
    say(proto, hello)
    return serve(proto, llm, job, stdin)


if __name__ == "__main__":
    sys.exit(main())
