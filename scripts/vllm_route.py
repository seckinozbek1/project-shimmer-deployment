"""One local generate call routed to the resident vLLM server (D-630 part A, A2; the link is
scripts/vllm_link.py). Called from AgentWrapper.call_local only when the sealed switch names the
agent (vllm_link.routed); with the switch off nothing here runs and call_local is as it was.

What stays exactly as on the transformers path: the rendered prompt (the same chat template and
the same tokenizer, so both engines read the same ids), the frozen decoding policy (greedy, one
beam, the policy's own stop ids, which are required here: a policy naming none is refused, since
vLLM's model stop ids are not the transformers model's), the checkpoint's own repetition_penalty
(transformers applies it under greedy decoding; the server applies the same figure), the context
refusal (D-058, read from the model's own config), the constraint (DECODING-B: the server builds
the very ContractProcessor from the same rendered prompt and agent, and its declaration and
contract digests must equal the ones the runner builds from the binding, or the call fails), the
decode of the reply (the runner's tokenizer, skip_special_tokens), the stop reason, the usage
fields and the one reply record per call. What differs: the record's `attention` names the engine
(vllm, the protocol, the server's versions and load record, its start seconds and the request
seconds) where a transformers call names its kernel, and the usage carries `engine: vllm`.

Part A routes local_auditor agents only (no adapter); the producer with its adapter is part B.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import threading
import time
from pathlib import Path

import vllm_link

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "benchmark" / "baselines"
BACKENDS = ("local_auditor",)
_TOKENIZERS = {}
_LOCK = threading.Lock()


class RouteRefused(RuntimeError):
    """The call cannot be routed as declared; it is a failed call, never sent to transformers."""


def _replay():
    if str(BASELINES) not in sys.path:
        sys.path.insert(0, str(BASELINES))
    return importlib.import_module("vllm_replay")


def tokenizer(model_id, checkpoint_path):
    """The runner's tokenizer of this model, loaded once from the local files (no model weights:
    the transformers model of a routed agent is never loaded)."""
    with _LOCK:
        found = _TOKENIZERS.get(model_id)
        if found is None:
            from transformers import AutoConfig, AutoTokenizer
            found = _TOKENIZERS[model_id] = (AutoTokenizer.from_pretrained(checkpoint_path, local_files_only=True),
                                             AutoConfig.from_pretrained(checkpoint_path, local_files_only=True))
        return found


def table_digest(tok):
    """The token table's digest, as benchmark/baselines/vllm_constraint.table_digest computes it."""
    import hashlib
    import contract_decoding
    table = contract_decoding.TokenTable.of(tok)
    return hashlib.sha256(json.dumps([table.size, table.strings], ensure_ascii=False).encode("utf-8")).hexdigest()


# The generate() kwargs a frozen policy may name for the route: greedy, one beam, its stop ids, and the
# two that change nothing under vLLM (the pad id, the KV cache). Any other kwarg is refused, never dropped.
POLICY_KWARGS = {"do_sample", "num_beams", "eos_token_id", "pad_token_id", "use_cache", "max_new_tokens"}
# Generation-config fields transformers applies under greedy decoding that the server does not carry:
# a checkpoint setting one of them (to anything but its neutral value) is refused. Its
# repetition_penalty is carried (vllm_replay.repetition_penalty).
UNCARRIED_GENERATION = {"no_repeat_ngram_size": (None, 0), "encoder_no_repeat_ngram_size": (None, 0),
                        "suppress_tokens": (None, []), "begin_suppress_tokens": (None, []),
                        "bad_words_ids": (None, []), "min_new_tokens": (None, 0), "min_length": (None, 0),
                        "forced_bos_token_id": (None,), "forced_eos_token_id": (None,),
                        "sequence_bias": (None, {}), "exponential_decay_length_penalty": (None,),
                        "length_penalty": (None, 1.0)}


def policy_stops(decoding):
    """The frozen policy's greedy kwargs and its stop ids, or RouteRefused."""
    kwargs = decoding["kwargs"]
    unknown = sorted(set(kwargs) - POLICY_KWARGS)
    if unknown:
        raise RouteRefused("the vLLM route does not carry the policy's %s" % ", ".join(unknown))
    if kwargs.get("do_sample") is not False or kwargs.get("num_beams", 1) != 1:
        raise RouteRefused("the vLLM route decodes greedily with one beam; this policy does not")
    eos = kwargs.get("eos_token_id")
    eos = [eos] if type(eos) is int else eos
    if not (isinstance(eos, list) and eos and all(type(e) is int for e in eos)):
        raise RouteRefused("the vLLM route needs the frozen policy's own stop ids; this policy names none")
    return eos


def generation_refusal(checkpoint_path):
    """None, or why the checkpoint's own generation config sets something the server does not carry."""
    try:
        config = json.loads((Path(checkpoint_path) / "generation_config.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return "the checkpoint's generation config cannot be read"
    set_fields = sorted(k for k, neutral in UNCARRIED_GENERATION.items() if k in config and config[k] not in neutral)
    return None if not set_fields else "the checkpoint's generation config sets %s, which the vLLM route does not carry" \
        % ", ".join(set_fields)


OVERHEAD_BYTES = int(1.5 * 2 ** 30)   # activations, CUDA graphs and the sampler beside weights and cache
# What the card keeps beside the server for the transformers models a run loads again after free_gpu: the
# tuned producer (Qwen2.5-7B NF4, about 4.5 GB resident by _load_qwen's own record) and its working memory.
# A larger model beside the server (JUDGE's Phi-4, reached only by a declared judge task, which no shipped rule
# declares) is a stated limit, measured in A5 before any such run.
REMAINDER_FLOOR_BYTES = 6 * 2 ** 30
# transformers' 4-bit quantizer gives a pre-quantised load with no torch_dtype float16 for its other layers
# (_load_qwen passes none; vllm-test-217f recorded current dtype float16 for VERIFIER).
TRANSFORMERS_PREQUANTISED_DTYPE = "float16"


def memory_plan(config, checkpoint_path, max_model_len, share, total_bytes):
    """Whether the sealed card share holds the weights, one full-length sequence's KV cache and the
    overhead, from the model's own config (layers, KV heads, head size, at 2 bytes a value) and the
    checkpoint's weight files: (plan, None) or (plan, why not)."""
    layers = int(config.num_hidden_layers)
    heads = int(config.num_attention_heads)
    kv_heads = int(getattr(config, "num_key_value_heads", None) or heads)
    head_dim = int(getattr(config, "head_dim", None) or config.hidden_size // heads)
    kv_bytes = 2 * layers * kv_heads * head_dim * 2 * int(max_model_len)
    weights = weight_bytes(checkpoint_path)
    need = weights + kv_bytes + OVERHEAD_BYTES
    plan = dict(kv_bytes_per_token=2 * layers * kv_heads * head_dim * 2, kv_bytes=kv_bytes, weight_bytes=weights,
                overhead_bytes=OVERHEAD_BYTES, need_bytes=need, share_bytes=int(share * total_bytes),
                card_bytes=int(total_bytes), max_model_len=int(max_model_len), share=share)
    plan["remainder_bytes"] = int(total_bytes - share * total_bytes)
    plan["remainder_floor_bytes"] = REMAINDER_FLOOR_BYTES
    if need > share * total_bytes:
        return plan, ("the vLLM share (%.2f of %.1f GiB) cannot hold the weights, one %d-token KV cache and the "
                      "overhead (%.1f GiB)" % (share, total_bytes / 2 ** 30, max_model_len, need / 2 ** 30))
    if plan["remainder_bytes"] < REMAINDER_FLOOR_BYTES:
        return plan, ("the vLLM share (%.2f) leaves %.1f GiB of the card, under the %.1f GiB the transformers models "
                      "loaded beside it need" % (share, plan["remainder_bytes"] / 2 ** 30, REMAINDER_FLOOR_BYTES / 2 ** 30))
    return plan, None


# The transformers versions whose 4-bit quantizer gives float16 to a pre-quantised load with no torch_dtype
# (the runner's pins; vllm-test-217f recorded float16 on 4.51.3). Another version is refused, not assumed.
TRANSFORMERS_FLOAT16_VERSIONS = ("4.51.", "4.52.")


def transformers_version():
    import transformers
    return transformers.__version__


def dtype_plan(sealed_dtype, quant):
    """The two engines' dtypes: transformers' load (TRANSFORMERS_PREQUANTISED_DTYPE, the checkpoint's 4-bit
    compute dtype) and vLLM's (vllm_replay.vllm_dtypes); refused unless vLLM can run transformers' own
    dtypes (vllm_replay.dtype_refusal) and the sealed dtype is the one it would run."""
    replay = _replay()
    version = transformers_version()
    if not version.startswith(TRANSFORMERS_FLOAT16_VERSIONS):
        raise RouteRefused("the transformers load dtype is known for %s only; this runner has %s"
                           % (", ".join(v + "x" for v in TRANSFORMERS_FLOAT16_VERSIONS), version))
    current = {"dtype": TRANSFORMERS_PREQUANTISED_DTYPE, "compute_dtype": quant.get("compute_dtype")}
    why = replay.dtype_refusal(current, quant)
    if why:
        raise RouteRefused(why)
    expected = replay.vllm_dtypes(current)["dtype"]
    if sealed_dtype != expected:
        raise RouteRefused("the sealed vLLM dtype %s is not the %s the transformers load runs" % (sealed_dtype, expected))
    return {"transformers_dtype": current["dtype"], "checkpoint_compute_dtype": current["compute_dtype"],
            "vllm_dtype": sealed_dtype, "transformers_version": version}


def server_request(local, prompt, wrapper):
    """The constraint the server builds: the same prompt, the agent and, for an envelope agent, the
    wrapper's own contract (the one the runner's constraint was built from)."""
    if local is None:
        return None
    request = {"prompt": prompt, "agent": local.get("agent")}
    contract = getattr(wrapper, "contract", None)
    if request["agent"] is not None and isinstance(contract, dict) and contract:
        request["contract"] = contract
    return request


def weight_bytes(checkpoint_path):
    return sum(f.stat().st_size for f in Path(checkpoint_path).glob("*.safetensors"))


def quant_of(checkpoint_path):
    """The checkpoint's NF4 quantisation (both engines load the same weights), or RouteRefused."""
    quant, why = _replay().quantisation(checkpoint_path)
    if quant is None:
        raise RouteRefused(why)
    return quant


def card_bytes():
    import torch
    return torch.cuda.mem_get_info()[1]


def checkpoint_penalty(checkpoint_path):
    """The repetition_penalty the checkpoint's own generation config sets (transformers applies it under
    greedy decoding), carried to the server."""
    return _replay().repetition_penalty(checkpoint_path)


def loaded_refusal(hello, sealed):
    """None when the server loaded what the route sealed, read from the engine itself (vllm_child.loaded):
    bitsandbytes 4-bit weights, the sealed dtype and the sealed batch-invariant mode; else why not."""
    loaded = hello.get("loaded") or {}
    if loaded.get("quantization") != "bitsandbytes":
        return "the server loaded %r weights, not bitsandbytes 4-bit" % loaded.get("quantization")
    if loaded.get("dtype") != "torch." + sealed["dtype"]:
        return "the server runs %s, not the sealed %s" % (loaded.get("dtype"), sealed["dtype"])
    if bool(loaded.get("batch_invariant_mode")) != bool(sealed.get("batch_invariant", True)):
        return "the server's batch-invariant mode is not the sealed one"
    return None


def job_for(model_id, checkpoint_path, tok):
    """The server's job: the sealed fields (vllm_link.sealed_job) and what the runner reads itself."""
    sealed = vllm_link.sealed_job()
    replay = _replay()
    return {"protocol": vllm_link.PROTOCOL, "model": str(checkpoint_path), "tokenizer": str(checkpoint_path),
            "adapter": None, "lora_rank": None, "dtype": sealed["dtype"],
            "max_model_len": int(sealed["max_model_len"]), "batch": int(sealed.get("batch", 1)),
            "gpu_memory_utilization": float(sealed["gpu_memory_utilization"]),
            "repetition_penalty": checkpoint_penalty(checkpoint_path),
            "observer": replay._observer(), "token_table_sha256": table_digest(tok)}


def start(model_id, checkpoint_path, tok, log_dir=None, popen=None):
    """The server of this model, started on first use and again after it gave the card back
    (vllm_link.yield_card); the server of any other model is shut down first, so the card holds one."""
    key = (model_id, str(checkpoint_path))

    def make():
        job = job_for(model_id, checkpoint_path, tok)
        free_gpu()
        python = os.environ[vllm_link.PYTHON_ENV]
        env = _replay().child_env(python, bool(vllm_link.sealed_job().get("batch_invariant", True)))
        if log_dir is not None:      # the server's network log (child_network.jsonl), in the run's logs
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            env["SHIMMER_VLLM_LOG_DIR"] = str(log_dir)
        extra = {} if popen is None else {"popen": popen}
        stderr_path = None if log_dir is None else Path(log_dir) / "server.stderr.log"
        return vllm_link.Link(python, job, env=env, stderr_path=stderr_path, **extra)
    with vllm_link.CARD_LOCK:      # the hand-back and the start, with no load between them
        vllm_link.yield_card("server_start", model_id, keep=key)
        return vllm_link.link_for(key, make)


def free_gpu():
    """Before the server takes its share of the card: every resident transformers model is released
    (the run's own eviction, the reference residency and this worker's residents), so vLLM's memory
    check sees the card as the run leaves it between models. A model released here is loaded again on
    its next call. A stated limit: a model another thread is generating with stays in memory until that
    call returns (its references are held), and another lane's residents are that lane's; a start that
    then finds too little memory fails as a start failure, recorded, and the route stays off for the run."""
    import gc
    import agent_wrapper as aw
    import execution_topology
    import final_models
    with aw._QWEN_LOAD_LOCK:
        aw._evict_generation_models(keep_model_id=None)
    final_models.release_reference_residency()
    context = getattr(execution_topology.WORK, "context", None)
    if context is not None and getattr(context, "worker", None) is not None and context.worker.residents:
        context.worker.residents.clear()
        gc.collect()
        torch = sys.modules.get("torch")
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()


def held_context(context, server_length):
    """The context record held to the server's sealed length too: a call that fits the model's
    positions but not the server's length is the same declared exclusion (D-058)."""
    if context["over_context"] or context["prompt_tokens"] + context["max_new_tokens"] <= server_length:
        return context
    return dict(context, model_context=server_length, over_context=True,
                model_positions=context["model_context"], held_to="vllm_max_model_len")


def stop_of(last, eos, count, requested, finish_reason):
    """The stop reason as call_local reads it (its stop ids, then the allowance), and a reply vLLM cut
    for its own length bound is a truncation, never read as complete."""
    import generation_observation
    stop_reason, truncated = generation_observation.local_stop(last, eos, count, requested)
    if stop_reason == "unknown" and finish_reason == "length":
        return "length", True
    return stop_reason, truncated


def same_constraint(runner, server):
    """The server's constraint is the runner's: the same declaration and the same contract."""
    if runner is None or server is None:
        return runner is None and server is None
    keys = ("name", "version", "declaration_sha256", "contract_sha256")
    return all(runner.get(k) == server.get(k) for k in keys)


# How many times a request refused because its server was shut down after its start (vllm_link.Yielded,
# nothing sent) starts the server again before the call fails.
YIELD_RESTARTS = 1


def live_link(model_id, checkpoint_path, tok, log_dir, sealed, server_length, plan, dtypes, config, sent,
              run_context=None):
    """The started server of this model, refused unless it loaded the sealed engine; the reply record's
    attention field names it (the field names the kernel and backend a call ran under; here the engine)."""
    link = start(model_id, checkpoint_path, tok, log_dir)
    if getattr(link, "run_context", None) is None:      # where its hand-back events are written
        link.run_context = run_context
    why = loaded_refusal(link.hello, sealed)
    if why:
        vllm_link.retire((model_id, str(checkpoint_path)), why)
        raise RouteRefused(why)
    sent["attention"] = {"engine": "vllm", "protocol": vllm_link.PROTOCOL, "versions": link.hello.get("versions"),
                         "loaded": link.hello.get("loaded"), "start_seconds": link.hello.get("start_seconds"),
                         "server_start": getattr(link, "start_number", None),
                         "dtype": sealed["dtype"], "dtypes": dtypes, "bnb_compute_dtype": "bfloat16",
                         "max_model_len": server_length,
                         "gpu_memory_utilization": sealed["gpu_memory_utilization"], "memory_plan": plan,
                         # Phi-3.5's LongRoPE switches factors at its original positions; the two engines'
                         # switch rules may differ (measured in A5, never assumed equal).
                         "rope_scaling": (getattr(config, "rope_scaling", None) or {}).get("type")
                         if isinstance(getattr(config, "rope_scaling", None), dict) else None,
                         "original_max_position_embeddings": getattr(config, "original_max_position_embeddings", None)}
    return link


def call(wrapper, prompt, system, max_new_tokens, decoding, template_applied, sent):
    """One routed call. Returns a CallResult; `sent` is filled for the reply record as call_local
    fills it. Raises nothing the caller would treat differently from a failed call."""
    import agent_wrapper as aw
    import contract_decoding
    import decoding_policy
    import final_models
    import generation_observation
    import model_telemetry
    model_id = wrapper.model
    if wrapper.backend not in BACKENDS:
        raise RouteRefused("part A routes %s only; %s is on %s" % (", ".join(BACKENDS), wrapper.name, wrapper.backend))
    eos = policy_stops(decoding)
    checkpoint_path = aw._local_checkpoint_path(model_id)
    quant = quant_of(checkpoint_path)
    why = generation_refusal(checkpoint_path)
    if why:
        raise RouteRefused(why)
    sealed = vllm_link.sealed_job()
    dtypes = dtype_plan(sealed["dtype"], quant)
    tok, config = tokenizer(model_id, checkpoint_path)
    plan, why = memory_plan(config, checkpoint_path, sealed["max_model_len"], float(sealed["gpu_memory_utilization"]),
                            card_bytes())
    sent["memory_plan"] = plan
    if why:
        raise RouteRefused(why)
    wrapper._model_identity = dict(model_mode="base", adapter_checkpoint=None, adapter_sha256=None,
                                   runtime_engine="vllm", model_revision=None,
                                   base_reason="explicit base mode" if final_models.mode() == "base"
                                   else "generative Auditor evidence/other task; not final classifier")
    if template_applied:
        if not getattr(tok, "chat_template", None):
            raise ValueError("Configured local tokenizer has no chat template")
        messages = ([{"role": "system", "content": system}] if system is not None else []) + \
                   [{"role": "user", "content": prompt}]
        prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    sent.update(payload=prompt, form="rendered_prompt", model_mode="base",
                decoding=dict(decoding_policy.usage_fields(decoding), max_new_tokens=max_new_tokens))
    # The same tokenizer call as call_local's, so both engines read the same ids.
    ids = [int(i) for i in tok(prompt, return_tensors="pt",
                               **({"add_special_tokens": False} if template_applied else {}))["input_ids"][0].tolist()]
    in_tokens = len(ids)

    class _Config:   # context_record reads model.config.max_position_embeddings
        pass
    holder = _Config()
    holder.config = config
    sent["context"] = final_models.context_record(holder, in_tokens, max_new_tokens)
    # The server's sealed length is a second, tighter bound: a call past it is the same declared
    # exclusion (D-058), with the server's length recorded as the context it was held to.
    server_length = int(sealed["max_model_len"])
    sent["context"] = held_context(sent["context"], server_length)
    if sent["context"]["over_context"]:
        fit = sent["context"]
        model_telemetry.emit(wrapper.run_context, "prompt_over_context",
            call_id=getattr(wrapper, "_cost_call_id", None), agent=wrapper.name, backend=wrapper.backend,
            doc_id=getattr(wrapper, "_cost_doc_id", "") or "", phase=getattr(wrapper, "_cost_phase", "") or "",
            prompt_tokens=fit["prompt_tokens"], max_new_tokens=fit["max_new_tokens"], model_context=fit["model_context"])
        return aw.CallResult(wrapper.backend, model_id, "", ok=False, error=(
            "prompt_over_context: %d prompt tokens and an output allowance of %d exceed the "
            "model's %d positions; not truncated, not generated (D-058, a declared exclusion)"
            % (fit["prompt_tokens"], fit["max_new_tokens"], fit["model_context"])))
    constraint = contract_decoding.for_call(wrapper, tok, in_tokens, eos)
    local = constraint.summary() if constraint is not None else None
    request = server_request(local, prompt, wrapper)
    run_context = getattr(wrapper, "run_context", None)
    run_dir = getattr(run_context, "run_dir", None)
    log_dir = None if run_dir is None else Path(run_dir) / "logs" / "vllm_server"
    link = live_link(model_id, checkpoint_path, tok, log_dir, sealed, server_length, plan, dtypes, config, sent,
                     run_context)
    try:
        for restart in range(YIELD_RESTARTS + 1):
            if restart:
                link = live_link(model_id, checkpoint_path, tok, log_dir, sealed, server_length, plan, dtypes, config,
                                 sent, run_context)
            started = time.perf_counter()
            try:
                reply = link.generate(ids, int(max_new_tokens), eos, request, seconds=int(sealed["request_seconds"]))
                break
            except vllm_link.Yielded:
                # A load on another lane shut the server down between its start and this request (nothing
                # was sent): started again up to YIELD_RESTARTS times; past that it is a failed call.
                if restart == YIELD_RESTARTS:
                    raise
    except vllm_link.RequestFailed as exc:
        # An out-of-memory or a refused kernel in the server is the named failure the transformers
        # path raises (one record, one generation_failure event, raised on); any other server error
        # is a failed call.
        named = final_models.named_generation_failure(RuntimeError(exc.server_error))
        if named is None:
            raise
        wrapper._write_reply(aw.CallResult(wrapper.backend, model_id, "", ok=False, error=named.kind), sent)
        model_telemetry.emit(wrapper.run_context, "generation_failure",
            call_id=getattr(wrapper, "_cost_call_id", None), agent=wrapper.name, backend=wrapper.backend,
            kind=named.kind, attention=sent.get("attention"), prompt_tokens=in_tokens)
        raise named from exc
    ended = time.perf_counter()
    if not same_constraint(local, reply["constraint"]):
        sent["decoding_constraint"] = {"runner": local, "server": reply["constraint"]}
        raise RouteRefused("the server's constraint is not the runner's (declaration or contract digest)")
    if local is not None:
        sent["decoding_constraint"] = dict(reply["constraint"], runner_source=local.get("source"))
    sent["attention"]["request_seconds"] = reply["seconds"]
    model_telemetry.emit(wrapper.run_context, "generation_interval", call_id=getattr(wrapper, "_cost_call_id", None),
                         start_monotonic_s=started, end_monotonic_s=ended)
    out = list(reply["token_ids"])
    last = out[-1] if out else None
    stop_reason, truncated = stop_of(last, eos, len(out), max_new_tokens, reply["finish_reason"])
    sent["attention"]["finish_reason"] = reply["finish_reason"]
    text = tok.decode(out, skip_special_tokens=True)
    return aw.CallResult(wrapper.backend, model_id, text, usage={
        "input_tokens": in_tokens, "output_tokens": len(out),
        "truncated": truncated, "finish_reason": stop_reason,
        "requested_max_output_tokens": max_new_tokens,
        "generation_seconds": ended - started, "generation_finished_at": model_telemetry.now(),
        "time_to_first_token_seconds": None, "chat_template_applied": template_applied,
        "rendered_prompt_sha256": generation_observation.prompt_identity(prompt),
        "cap_hit": len(out) >= max_new_tokens, "terminal_token_id": last, "configured_eos_token_ids": eos,
        **decoding_policy.usage_fields(decoding),
        **({"decoding_constraint": sent["decoding_constraint"]} if local is not None else {}),
        "engine": "vllm"})
