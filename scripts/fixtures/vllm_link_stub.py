"""A stand-in vLLM server for the link's proofs (no vLLM, no model): it speaks vllm-link-v1 exactly as
scripts/vllm_server.py must, and misbehaves on demand.

    VLLM_STUB_REPLY   JSON list of token ids every request answers with (the request's first stop id is
                      appended unless VLLM_STUB_MODE is "cap")
    VLLM_STUB_MODE    "" | "noise" (a line outside the protocol) | "die" (exit on the first request) |
                      "badhello" (an error at start) | "otherid" (answer another id) | "cap"
                      (no stop id: the allowance runs out) | "table" (another token table) |
                      "hang" (never answers a request) | "hanghello" (never says hello)
    VLLM_STUB_LOG     a file each received request is appended to (JSON line)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import vllm_link  # noqa: E402

out = sys.stdout
mode = os.environ.get("VLLM_STUB_MODE", "")
reply = json.loads(os.environ.get("VLLM_STUB_REPLY", "[11, 12]"))
log = os.environ.get("VLLM_STUB_LOG")


def say(message):
    out.write(vllm_link.server_line(message))
    out.flush()


job = json.loads(sys.stdin.readline())
sys.stderr.write("stub server log line\n")
sys.stderr.flush()
if mode == "hanghello":
    import time
    time.sleep(120)
if mode == "badhello":
    say({"op": "hello", "error": "engine failed: stub"})
    sys.exit(3)
table = "0" * 64 if mode == "table" else job["token_table_sha256"]
say({"op": "hello", "protocol": vllm_link.PROTOCOL, "versions": {"vllm": "stub"}, "loaded": {"dtype": job["dtype"]},
     "token_table_sha256": table, "import_seconds": 0.0, "engine_seconds": 0.0,
     "aux_env": {"bytes": 1, "files": 1}})
for line in sys.stdin:
    request = json.loads(line)
    if request["op"] == "shutdown":
        sys.exit(0)
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(request) + "\n")
    if mode == "die":
        sys.exit(4)
    if mode == "hang":
        import time
        time.sleep(120)
    if mode == "noise":
        out.write("INFO a library line\n")
        out.flush()
        continue
    ids = list(reply)[: request["max_new_tokens"]]
    finish = "length"
    if mode != "cap" and len(ids) < request["max_new_tokens"]:
        ids.append(request["eos"][0])
        finish = "stop"
    say({"op": "reply", "id": "other" if mode == "otherid" else request["id"], "token_ids": ids,
         "finish_reason": finish, "seconds": 0.0,
         "constraint": None if request["constraint"] is None else {"stub": True, "agent": request["constraint"]["agent"]}})
