"""The vLLM side of a vllm-replay-v1 pass (#217): run in the auxiliary environment's own Python,
never imported by the runner. Reads one job file, writes one results file, and exits.

    <venv_aux>/bin/python vllm_child.py --job job.json --out results.json

The job names one model group: the base model's local folder, the adapter folder or none, the
tokenizer folder, the context length, the batch bound, the repetition penalty the checkpoint's
own generation config sets (transformers applies it under greedy decoding, so it is applied
here too), and the prompts, each with its token ids (tokenised by the runner's own tokenizer,
so both engines read the same ids), its output allowance, its stop ids and its constraint (or
none). Every prompt runs twice on one engine: first alone (one request at a time, a batch of
one), then all together (the engine batching up to the bound). Greedy, VLLM_BATCH_INVARIANT=1.
Before vLLM or torch is imported, the runner's own network denial (cloud_run_observer.deny_network,
the file the job names) is applied in this process, its log beside the results: the engine runs
in this process (VLLM_ENABLE_V1_MULTIPROCESSING=0), so every Python-level connection it tries is
refused and counted.
The results carry per prompt and arm the reply text, its token ids, the stop reason and the
constraint's counts, and per arm the wall seconds and output tokens. They stay on the instance:
the runner writes hashes and counts only.
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

ARMS = ("vllm_b1", "vllm_batch")


def engine(job):
    from vllm import LLM
    options = dict(model=job["model"], tokenizer=job["tokenizer"], dtype=job["dtype"], seed=0,
                   max_model_len=int(job["max_model_len"]), max_num_seqs=int(job["batch"]),
                   gpu_memory_utilization=float(job.get("gpu_memory_utilization", 0.85)),
                   logits_processors=["vllm_constraint:ShimmerConstraint"], trust_remote_code=False)
    if job.get("adapter"):
        options.update(enable_lora=True, max_lora_rank=int(job["lora_rank"]), max_loras=1)
    return LLM(**options)


def params(job, prompt):
    from vllm import SamplingParams
    extra = None
    if prompt.get("constraint"):
        extra = {"shimmer_constraint": dict(prompt["constraint"], key=prompt["key"],
                                            prompt_tokens=len(prompt["token_ids"]), eos=prompt["eos"])}
    # ignore_eos: the model's own end token and its generation config's are not stop tokens; only the
    # frozen policy's ids are, as for transformers (vllm 0.33 sampling_params.py:781-803, check_stop in
    # v1/core/sched/utils.py:104-112).
    return SamplingParams(temperature=0.0, max_tokens=int(prompt["max_new_tokens"]), stop_token_ids=prompt["eos"],
                          ignore_eos=True,
                          repetition_penalty=float(job.get("repetition_penalty") or 1.0),
                          skip_special_tokens=True, extra_args=extra)


def loaded(llm):
    """What vLLM loaded and under which mode, read from the engine itself."""
    from vllm.model_executor.determinism import batch_invariant
    config = llm.llm_engine.model_config
    return {"quantization": getattr(config, "quantization", None), "dtype": str(getattr(config, "dtype", None)),
            "batch_invariant_mode": bool(getattr(batch_invariant, "_batch_invariant_MODE", False)),
            "batch_invariant_env": os.environ.get("VLLM_BATCH_INVARIANT")}


def run_arm(llm, job, prompts, together, lora):
    from vllm.inputs import TokensPrompt
    import vllm_constraint
    started = time.perf_counter()
    outputs = []
    if together:
        outputs = llm.generate([TokensPrompt(prompt_token_ids=p["token_ids"]) for p in prompts],
                               [params(job, p) for p in prompts], lora_request=lora, use_tqdm=False)
    else:
        for p in prompts:
            outputs += llm.generate([TokensPrompt(prompt_token_ids=p["token_ids"])], [params(job, p)],
                                    lora_request=lora, use_tqdm=False)
    seconds = time.perf_counter() - started
    rows = {}
    for p, out in zip(prompts, outputs):
        first = out.outputs[0]
        ids = list(first.token_ids)
        rows[p["key"]] = {"text": first.text, "token_ids": ids, "output_tokens": len(ids),
                          "finish_reason": first.finish_reason,
                          "stopped": bool(ids) and ids[-1] in p["eos"] or first.finish_reason == "stop",
                          "constraint": dict(vllm_constraint.COUNTS.get(p["key"]) or {}) or None}
        vllm_constraint.COUNTS.pop(p["key"], None)
    return {"seconds": round(seconds, 3), "output_tokens": sum(r["output_tokens"] for r in rows.values()), "rows": rows}


def traceback_frames(exc):
    """The failure's last frames for the evidence: the exception type, each frame's file, line and
    function, and the failing source line of code (never a prompt's or a reply's text, which no
    frame of vLLM or this tool holds as source)."""
    import traceback
    frames = traceback.extract_tb(exc.__traceback__)[-8:]
    return {"type": type(exc).__name__,
            "frames": [{"file": f.filename, "line": f.lineno, "function": f.name, "source": (f.line or "")[:200]}
                       for f in frames]}


def aux_env_size():
    """For part C (an env layer on the filesystem): the auxiliary venv's size on disk, read from this
    process's own prefix (bytes and file count, symlinks not followed)."""
    total = files = 0
    for root, _, names in os.walk(sys.prefix, followlinks=False):
        for name in names:
            path = os.path.join(root, name)
            try:
                if not os.path.islink(path):
                    total += os.path.getsize(path)
                    files += 1
            except OSError:
                continue
    return {"prefix": sys.prefix, "bytes": total, "files": files}


# For part C (a persistent compile cache): the engine start split as vLLM's own startup log states it.
# Each pattern is the format of one vLLM 0.33 startup message (structural: its own wording and number).
import re  # noqa: E402

START_PHASES = (
    ("model_load_seconds", re.compile(r"Model loading took .*?([0-9]+(?:\.[0-9]+)?) s(?:ec(?:ond)?s?)?")),
    ("dynamo_transform_seconds", re.compile(r"Dynamo bytecode transform time: ([0-9]+(?:\.[0-9]+)?) s")),
    ("compile_seconds", re.compile(r"torch\.compile takes ([0-9]+(?:\.[0-9]+)?) s in total")),
    ("graph_capture_seconds", re.compile(r"Graph capturing finished in ([0-9]+(?:\.[0-9]+)?) secs?")),
)


class StartLog:
    """Reads vLLM's own startup messages (logger `vllm` and its children) while the engine starts and
    keeps, per phase, the seconds the message states and the message itself (startup lines only; no
    prompt is in flight then). A phase whose message never came stays None: not measured."""

    def __init__(self):
        import logging
        self.phases = {name: None for name, _ in START_PHASES}
        self.lines = []
        outer = self

        class Handler(logging.Handler):
            def emit(self, record):
                try:
                    text = record.getMessage()
                except Exception:
                    return
                for name, pattern in START_PHASES:
                    found = pattern.search(text)
                    if found:
                        outer.phases[name] = round((outer.phases[name] or 0.0) + float(found.group(1)), 3)
                        outer.lines.append(text[:200])
        self.handler = Handler(level=logging.INFO)
        self.logger = logging.getLogger("vllm")

    def __enter__(self):
        self.logger.addHandler(self.handler)
        return self

    def __exit__(self, *exc):
        self.logger.removeHandler(self.handler)
        return False

    def record(self):
        return dict(self.phases, messages=self.lines)


def deny_network(job, folder):
    """The runner's network denial, from the file the job names, applied in this process."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("cloud_run_observer", job["observer"])
    observer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observer)
    recorder = observer.Recorder(Path(folder) / "child_network.jsonl")
    observer.deny_network(recorder)
    return recorder


def main(argv=None):
    parser = argparse.ArgumentParser(prog="vllm_child.py", allow_abbrev=False)
    parser.add_argument("--job", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    deny_network(job, Path(args.out).parent)
    os.environ["SHIMMER_CONSTRAINT_TOKENIZER"] = job["tokenizer"]
    result = {"versions": {}, "arms": {}, "error": None, "aux_env": aux_env_size()}
    try:
        imported = time.perf_counter()
        import torch
        import vllm
        result["import_seconds"] = round(time.perf_counter() - imported, 3)
        result["versions"] = {"vllm": vllm.__version__, "torch": torch.__version__,
                              "batch_invariant": os.environ.get("VLLM_BATCH_INVARIANT")}
        started = time.perf_counter()
        with StartLog() as log:
            llm = engine(job)
        result["engine_seconds"] = round(time.perf_counter() - started, 3)
        result["engine_phases"] = log.record()
        result["loaded"] = loaded(llm)
        import vllm_replay
        result["spec"] = dict(vllm_replay.platform_spec(torch), engine="vllm", engine_version=vllm.__version__,
                              bnb_plugin=vllm_replay._version("vllm-bnb-plugin"),
                              bitsandbytes=vllm_replay._version("bitsandbytes"),
                              triton=vllm_replay._version("triton"), accelerate=vllm_replay._version("accelerate"),
                              model=job["model"], quantisation=result["loaded"], dtype=job["dtype"],
                              compute_dtype=vllm_replay.VLLM_BNB_COMPUTE,
                              lora=None if not job.get("adapter") else {"adapter": job["adapter"], "max_lora_rank": job["lora_rank"]},
                              sampling={"temperature": 0.0, "ignore_eos": True, "repetition_penalty": job.get("repetition_penalty"),
                                        "skip_special_tokens": True, "max_num_seqs": int(job["batch"])},
                              batch_invariant=os.environ.get("VLLM_BATCH_INVARIANT"),
                              v2_model_runner=os.environ.get("VLLM_USE_V2_MODEL_RUNNER"), seed=0,
                              max_model_len=int(job["max_model_len"]))
        import vllm_constraint
        digest = vllm_constraint.table_digest(vllm_constraint.tokenizer(job["tokenizer"]))
        result["token_table_sha256"] = digest
        if digest != job["token_table_sha256"]:
            raise RuntimeError("the token table differs from the runner's; the constraint would read replies differently")
        lora = None
        if job.get("adapter"):
            from vllm.lora.request import LoRARequest
            lora = LoRARequest("adapter", 1, job["adapter"])
        prompts = job["prompts"]
        for arm in ARMS:
            for p in prompts:
                p["key"] = arm + ":" + p["prompt_id"]
            result["arms"][arm] = run_arm(llm, job, prompts, arm == "vllm_batch", lora)
        result["peak_gpu_bytes"] = int(torch.cuda.max_memory_allocated()) if torch.cuda.is_available() else None
    except Exception as exc:  # recorded for the runner, which decides what it means
        result["error"] = "%s: %s" % (type(exc).__name__, str(exc)[:400])
        result["traceback"] = traceback_frames(exc)
    Path(args.out).write_text(json.dumps(result), encoding="utf-8")
    return 0 if result["error"] is None else 3


if __name__ == "__main__":
    sys.exit(main())
