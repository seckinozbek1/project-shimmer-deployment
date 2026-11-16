"""Transformers on the auxiliary stack (#217, D-608, 217f option 4): run in venv_aux's own Python, the
environment vLLM's lock pins (its torch, bitsandbytes and transformers), never imported by the runner.

    <venv_aux>/bin/python hf_aux_child.py --job job.json --out results.json

It answers one question: does transformers itself agree with the runner's transformers when only the
library stack changes? It loads the group's pre-quantised snapshot as the current engine's auditor
path does (agent_wrapper._load_qwen: device_map on GPU 0, local files only, sdpa, no torch_dtype),
runs under the runner's determinism (torch.use_deterministic_algorithms, TF32 off), pins sdpa to the
memory-efficient kernel (final_models.pinned_attention), and generates each prompt alone with the frozen
policy's generate() kwargs, the prompt's own allowance and, for an envelope agent, the same
contract_decoding constraint as a logits processor. The runner's network denial is applied first.
Results: per prompt the reply text, its token count and whether it stopped on a stop token; the arm's
seconds and output tokens; the stack's versions. They stay on the instance: the runner writes hashes
and counts only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1] / "scripts"), str(HERE)]

ARM = "hf_aux"


def load(job):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    tok = AutoTokenizer.from_pretrained(job["model"], local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(job["model"], device_map={"": 0}, local_files_only=True,
                                                 attn_implementation="sdpa")
    model.eval()
    return tok, model


def generate(tok, model, prompt, decoding):
    import torch
    from torch.nn.attention import SDPBackend, sdpa_kernel
    ids = torch.tensor([prompt["token_ids"]], device=model.device)
    extra = {}
    constraint = None
    if prompt.get("constraint"):
        import contract_decoding
        constraint = contract_decoding.for_prompt(prompt["constraint"]["prompt"], tok, ids.shape[1], prompt["eos"],
                                                  agent=prompt["constraint"].get("agent"))
        extra = constraint.generate_kwargs()
    with torch.no_grad(), sdpa_kernel([SDPBackend.EFFICIENT_ATTENTION]):
        out = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids), max_new_tokens=int(prompt["max_new_tokens"]),
                             **decoding, **extra)
    generated = out[0][ids.shape[1]:].tolist()
    text = tok.decode(generated, skip_special_tokens=True)
    stopped = bool(generated) and generated[-1] in prompt["eos"]
    del out, ids
    torch.cuda.empty_cache()
    return {"text": text, "token_ids": generated, "output_tokens": len(generated),
            "finish_reason": "stop" if stopped else "length",
            "constraint": dict(constraint.summary()) if constraint is not None else None}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="hf_aux_child.py", allow_abbrev=False)
    parser.add_argument("--job", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    import vllm_child
    vllm_child.deny_network(job, Path(args.out).parent)
    result = {"arms": {}, "error": None}
    try:
        import torch
        import transformers
        import vllm_replay
        tok, model = load(job)
        result["spec"] = dict(vllm_replay.platform_spec(torch), engine="transformers (auxiliary stack)",
                              engine_version=transformers.__version__, bitsandbytes=vllm_replay._version("bitsandbytes"),
                              model=job["model"], dtype=str(getattr(model, "dtype", None)), attention="sdpa (efficient, pinned)",
                              decoding=job["decoding"], deterministic=bool(torch.are_deterministic_algorithms_enabled()),
                              seed=None, batch=1)
        started = time.perf_counter()
        rows = {}
        for prompt in job["prompts"]:
            rows[ARM + ":" + prompt["prompt_id"]] = generate(tok, model, prompt, job["decoding"])
        seconds = time.perf_counter() - started
        result["arms"][ARM] = {"seconds": round(seconds, 3), "rows": rows,
                               "output_tokens": sum(r["output_tokens"] for r in rows.values())}
    except Exception as exc:  # recorded for the runner, which decides what it means
        result["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:400])
        result["traceback"] = vllm_child.traceback_frames(exc)
    Path(args.out).write_text(json.dumps(result), encoding="utf-8")
    return 0 if result["error"] is None else 3


if __name__ == "__main__":
    sys.exit(main())
