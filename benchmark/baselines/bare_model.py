"""B1, the bare-model arm: the main reading agent's model, one fixed prompt per item, no pipeline.

An evaluation tool, not a review. For one test bundle and the item table the adapter
wrote beside it (``items.json``: item_id, document_id, rule_id, benchmark; no gold;
the source ids it also holds are never put in a prompt), it sends the preregistered
prompt (``b1_prompt.json``, from docs/benchmarks/PREREGISTRATION.md section 5.4) once
per item. The prompt is rendered by benchmark/adapters/common/prompt.py, the same code
the adapters' cut rule counts with: the document as it stands in the bundle (already cut
by the adapter, section 5.3), every convention of the bundle as written in it, and the
bundle's reference material (its grounding files, the earlier version included), or the
line ``None.`` when it has none. It writes:

  <out>/audit/model_replies/   one record per call, through reply_records.write (the
                               S1 Part 4 write path every pipeline backend uses); the
                               run stops if a record cannot be written
  <out>/labels/<item_id>.json  one typed label per item; a reply that does not parse,
                               or whose label is not in the list, is ABSTAIN
  <out>/b1_summary.json        counts and the parse rate per benchmark for this document,
                               the number of replies whose length reached the output
                               allowance (possibly truncated), and whether this document's
                               rate is below 95 percent (information only), and the
                               attention every call ran under (D-056)
  <out>/b1_setup_failure.json  only when a call ran out of memory or its attention kernel
                               was refused: the run stops there (D-056 condition 3)

The development floor of 95 percent (section 5.4) is decided per benchmark on the rate
pooled over all its development items: ``bare_model.py pool --runs <folder>`` reads every
document's b1_summary.json and writes b1_parse_rates.json.

Before the first item the model is loaded and verified ONCE: its model id, checkpoint
digest and decoding are compared with the values passed in (from VERSIONS.md; section 4),
and every item's prompt plus the output allowance must fit the model's context. Any
failure there stops the run with a non-zero exit before anything is generated. Inside
the item loop only a generation error is caught (and recorded as a failed call), except
an out-of-memory error or a refused attention kernel, which stops the run (below).

The reading agent is passed in (``--agent``). PROCESSOR is a PLACEHOLDER default until
preregistration section 12 item 8 names the main reading agent. Its backend comes from
the pipeline's local profile table and config/local_models.json (read as data, the
pipeline is never imported), its checkpoint through final_models in final mode, its
decoding policy through scripts/decoding_policy.py, and its output allowance from the
pipeline's PROCESSOR budget (PRODUCTION_MAX_TOKENS) unless --max-new-tokens overrides it.

Two checkpoints (preregistration section 12 item 12; loop plan S5 revisions R3 and R20).
In final mode (SHIMMER_MODEL_MODE=final) ``--checkpoint`` selects which one is loaded:

  tuned   the tuned producer, through final_models.resident exactly as the pipeline loads
          it: the pinned 4-bit base at its revision with the checkpoint 168 adapter
  base    the SAME pinned 4-bit base at the same revision, read through
          final_models.base_path (which checks every base_hashes entry), prepared as the
          tuned producer's base is prepared, and WITHOUT the adapter: no adapter file is
          read and PeftModel is never called, so the comparison isolates the adapter

Each checkpoint is recorded in b1_summary.json under ``checkpoint`` (its name, model id,
revision, the model.safetensors SHA-256 from base_hashes, the adapter SHA-256 or null, and
whether an adapter was applied); its digest is ``<revision>:<model.safetensors sha256>``
for the base and that followed by ``+adapter:<adapter sha256>`` for the tuned producer.
In base mode only ``base`` exists (the reference loader, a PROVISIONAL snapshot digest).
Each checkpoint runs in its own process into its own output folder (one reply record per
item per checkpoint).

Attention (docs/loop/DECISIONS.md D-056, conditions 1 to 4). B1, both checkpoints, every
item, generates with the model's attention set to sdpa inside
``torch.nn.attention.sdpa_kernel([SDPBackend.EFFICIENT_ATTENTION])``: the memory-efficient
kernel only, so a refused kernel raises instead of falling back to the quadratic math
kernel. The model is loaded eager, as scripts/final_models.py loads it for B3; B1 switches
the resident model's attention setting around each call (b1_attention) and restores it in a
finally, so a B3 call in the same process still runs eager. The attention B1 declares
(attention_record) is compared with what the backend loaded (verify_identity) and with what
each call observed inside the switch; it is written into every reply record and into
b1_summary.json. An out-of-memory error, or a refused kernel, stops the run as a SETUP
FAILURE: the call's reply record is written, then ``b1_setup_failure.json`` (counts only),
and no label is written for that item, so it is never an abstention. The fallback, chunked
prefill (the prompt fed through the KV cache in fixed chunks under the same kernel,
chunked_prefill), is OFF unless ``--prefill-chunk`` is given with ``--prefill-decision``
naming the recorded decision that adopted it; both are sealed arguments.

In-process entry, for a runner that imports this file (benchmark/baselines on sys.path):
    run_b1(bundle, items, out, checkpoint, *, expected=None, development=False,
           agent=READING_AGENT, max_new_tokens=None, sensitive=False, run_id=None,
           prefill_chunk=None, prefill_decision=None) -> dict
It returns the b1_summary.json content and raises on any setup failure (nothing generated).

Usage (loads a local model; for the rented machine, never this laptop):
    py -3.12 benchmark/baselines/bare_model.py --bundle <bundle> --items <items.json> --out <dir>
        --checkpoint tuned|base --agent <AGENT> --expect-model-id <id> --expect-digest <digest>
        --expect-decoding '<json>'
    py -3.12 benchmark/baselines/bare_model.py pool --runs <folder> [--out <file>]   (no model)
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPTS = ROOT / "scripts"
ADAPTERS = HERE.parent / "adapters"
for _p in (str(SCRIPTS), str(HERE), str(ADAPTERS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import decoding_policy  # noqa: E402
import final_models  # noqa: E402
import python_only  # noqa: E402  the bundle loader shared with B2
import reply_records  # noqa: E402
from common import prompt as b1_prompt  # noqa: E402  the one renderer of the section 5.4 prompt

ARM = "B1"
AGENT_LABEL = "B1_BARE_MODEL"
BASELINE_TEXT = "BASELINE B1 (bare model): one fixed prompt per item, no pipeline. This is not a review."
PROMPT_PATH = HERE / "b1_prompt.json"
READING_AGENT = "PROCESSOR"   # PLACEHOLDER until preregistration section 12 item 8 is settled
PIPELINE_SOURCE = SCRIPTS / "pipeline.py"
_FENCE = re.compile(r"^\s*```[^`\s]*\s*$")
_ESCAPE = re.compile(r'\\(["\\/bfnrtu])|\\')
UNCERTAIN_LABEL = "uncertain"
# Section 5.4 (D-039 item 11): a benchmark whose development parse rate, pooled over all its
# development items (pool_parse_rates), is below this floor has its prompt and parser
# revised before the freeze, at most three times.
PARSE_RATE_FLOOR = 0.95
# The two checkpoints of section 12 item 12 (R20): the tuned producer, and the pinned base it
# is built on without its adapter. Final mode offers both; base mode only the base.
TUNED, BASE = "tuned", "base"
CHECKPOINTS = (TUNED, BASE)
FINAL_ROLE = "producer"
# D-056 condition 1: B1's attention, and the memory-efficient sdpa backend pinned for it.
B1_ATTENTION = "sdpa"
B1_SDPA_BACKEND = "EFFICIENT_ATTENTION"
# What scripts/final_models.py loads the model with, and what B3 keeps (condition 2). B1
# never changes it outside its own calls.
B3_ATTENTION = "eager"
# torch.backends.cuda's switch for each sdpa backend, by SDPBackend name.
SDPA_SWITCHES = {"FLASH_ATTENTION": "flash_sdp_enabled", "EFFICIENT_ATTENTION": "mem_efficient_sdp_enabled",
                 "MATH": "math_sdp_enabled", "CUDNN_ATTENTION": "cudnn_sdp_enabled"}
# The recorded decision that adopts chunked prefill (condition 4): a decision id.
DECISION_ID = re.compile(r"D-\d{3}")
SETUP_FAILURE_FILE = "b1_setup_failure.json"


class SetupError(Exception):
    """A failure before or outside generation: never caught per item."""


class SetupFailure(SetupError):
    """A call that stopped the run (D-056 condition 3): out of memory, or a refused
    attention kernel. Counted and reported apart, never an abstention."""

    def __init__(self, kind, item_id, error):
        super().__init__("B1 stopped at item %s: %s (%s), a setup failure, never an abstention"
                         % (item_id, kind, error))
        self.kind, self.item_id, self.error = kind, item_id, error


def _now():
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# the prompt


def load_prompt(path=PROMPT_PATH):
    spec = b1_prompt.load_prompt(path)
    for name, bench in spec["benchmarks"].items():
        names = label_names(bench)
        if _norm_label(bench["undecided"]) not in {_norm_label(n) for n in names}:
            raise ValueError("the undecided label of %s is not one of its labels" % name)
    return spec


def label_names(bench):
    """The label names: each label line's text before its first colon."""
    return [line.split(":", 1)[0].strip() for line in bench["labels"]]


def render_user(spec, bench_key, *, document, conventions, item, reference=""):
    return b1_prompt.render_user(spec, bench_key, document=document, conventions=conventions,
                                 item=item, reference=reference)


def render_system(spec, bench_key):
    return b1_prompt.render_system(spec, bench_key)


# ---------------------------------------------------------------------------
# the parser (section 5.4)


def _norm_label(value):
    text = str(value).lower().strip()
    if text.endswith("(undecided)"):
        text = text[: -len("(undecided)")]
    text = text.split(":", 1)[0].strip()
    return text.replace("_", " ")


def _last_balanced_object(text):
    """The last balanced {...}: from each closing brace, last first, scan back for the
    brace that balances it; the first closing brace that has one wins."""
    for end in range(len(text) - 1, -1, -1):
        if text[end] != "}":
            continue
        depth = 0
        for start in range(end, -1, -1):
            if text[start] == "}":
                depth += 1
            elif text[start] == "{":
                depth -= 1
                if depth == 0:
                    return text[start:end + 1]
    return None


def _loads(candidate):
    """(object, repaired): the JSON object, or, when it does not parse, the same text with
    every backslash that starts no valid JSON escape doubled (a copied `\\|`, `\\#` or
    LaTeX command in `evidence` or `reason` must not cost the label)."""
    try:
        return json.loads(candidate), False
    except ValueError:
        fixed = _ESCAPE.sub(lambda m: m.group(0) if m.group(1) else "\\\\", candidate)
        return json.loads(fixed), True


def parse_reply(reply, bench, item_id=None):
    """{parsed, label, evidence, reason, reply_item_id, item_id_matches, failure, repaired}."""
    out = {"parsed": False, "label": None, "evidence": None, "reason": None,
           "reply_item_id": None, "item_id_matches": None, "failure": None, "repaired": False}
    if not isinstance(reply, str) or not reply.strip():
        out["failure"] = "empty_reply"
        return out
    kept = "\n".join(line for line in reply.splitlines() if not _FENCE.match(line))
    candidate = _last_balanced_object(kept)
    if candidate is None:
        out["failure"] = "no_json_object"
        return out
    try:
        obj, out["repaired"] = _loads(candidate)
    except ValueError:
        out["failure"] = "json_invalid"
        return out
    if not isinstance(obj, dict) or not isinstance(obj.get("label"), str):
        out["failure"] = "no_label"
        return out
    wanted = _norm_label(obj["label"])
    if wanted == UNCERTAIN_LABEL:  # a rule's "emit UNCERTAIN" means the undecided label
        wanted = _norm_label(bench["undecided"])
    match = next((name for name in label_names(bench) if _norm_label(name) == wanted), None)
    out["reply_item_id"] = obj.get("item_id")
    out["item_id_matches"] = (str(obj.get("item_id")) == str(item_id)) if item_id else None
    out["evidence"] = obj.get("evidence") if isinstance(obj.get("evidence"), str) else None
    out["reason"] = obj.get("reason") if isinstance(obj.get("reason"), str) else None
    if match is None:
        out["failure"] = "label_not_in_list"
        return out
    out["parsed"] = True
    out["label"] = match
    return out


# ---------------------------------------------------------------------------
# the model, read from the pipeline's own configuration


pipeline_literal = python_only.pipeline_literal  # one ast reader of the pipeline source


def resolve_checkpoint(mode, checkpoint=None):
    """The checkpoint to load: `tuned` by default in final mode, `base` in base mode. A tuned
    checkpoint outside final mode, or a name not in CHECKPOINTS, is refused."""
    chosen = checkpoint or (TUNED if mode == "final" else BASE)
    if chosen not in CHECKPOINTS:
        raise ValueError("unknown checkpoint %r (one of %s)" % (chosen, ", ".join(CHECKPOINTS)))
    if chosen == TUNED and mode != "final":
        raise ValueError("the tuned checkpoint exists only in final mode (SHIMMER_MODEL_MODE=final)")
    return chosen


def checkpoint_record(checkpoint, spec):
    """(record, digest) of a final-mode checkpoint, from the pinned specification: the
    revision and model.safetensors SHA-256 base_path checks at load, and for the tuned
    producer the adapter SHA-256 final_models.verify checks (R20)."""
    weights = spec["base_hashes"]["model.safetensors"]
    adapter = spec["files"]["adapter"]["sha256"] if checkpoint == TUNED else None
    record = {"checkpoint": checkpoint, "model_id": spec["model_id"], "revision": spec["revision"],
              "model_safetensors_sha256": weights, "adapter_sha256": adapter,
              "adapter_applied": checkpoint == TUNED,
              "adapter_checkpoint": spec.get("checkpoint") if checkpoint == TUNED else None}
    digest = "%s:%s" % (spec["revision"], weights)
    if adapter:
        digest += "+adapter:" + adapter
    return record, digest


def load_base_checkpoint(device="cuda:0", *, spec=None, libs=None):
    """The pinned 4-bit base of the tuned producer WITHOUT its adapter (R20). The same
    path, checks and preparation as final_models.load gives the producer's base, up to the
    adapter: final_models.verify_runtime, final_models.base_path (every base_hashes entry
    checked; a mismatch refuses), the same from_pretrained arguments, architecture and
    quantization checks, prepare_model_for_kbit_training, eval and the cache on. No adapter
    file is read and PeftModel is never called. `libs` (AutoTokenizer, AutoModelForCausalLM,
    prepare_model_for_kbit_training) is for the checks' mocked model; None imports the
    real libraries."""
    spec = spec or final_models.specification(FINAL_ROLE)
    torch = final_models.verify_runtime()
    final_models.require(device.startswith("cuda:"), "Frozen inference requires CUDA")
    path = final_models.base_path(FINAL_ROLE, spec)
    if libs is None:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import prepare_model_for_kbit_training
        libs = SimpleNamespace(AutoTokenizer=AutoTokenizer, AutoModelForCausalLM=AutoModelForCausalLM,
                               prepare_model_for_kbit_training=prepare_model_for_kbit_training)
    tokenizer = libs.AutoTokenizer.from_pretrained(str(path), local_files_only=True,
                                                   trust_remote_code=False)
    model = libs.AutoModelForCausalLM.from_pretrained(
        str(path), local_files_only=True, trust_remote_code=False,
        device_map={"": int(device.split(":")[1])}, torch_dtype=torch.bfloat16,
        attn_implementation="eager")
    final_models.require(model.config.model_type == "qwen2" and model.is_loaded_in_4bit,
                         "Frozen architecture mismatch")
    quant = model.config.quantization_config
    quant = quant.to_dict() if hasattr(quant, "to_dict") else quant
    final_models.require(quant["bnb_4bit_quant_type"] == "nf4"
                         and quant["bnb_4bit_compute_dtype"] == "bfloat16",
                         "Frozen quantization mismatch")
    model = libs.prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": True})
    model.requires_grad_(False)
    model.eval()
    model.gradient_checkpointing_disable()
    model.config.use_cache = True
    return tokenizer, model


def resolve_reader(root=ROOT, *, agent=READING_AGENT, profile="local", max_new_tokens=None,
                   checkpoint=None, prefill_chunk=None, prefill_decision=None):
    """The reading agent's backend, model, decoding policy, output allowance, checkpoint and
    B1's attention (D-056; chunked prefill only with its recorded decision)."""
    root = Path(root)
    attention = attention_record(prefill_chunk, prefill_decision)
    registry = json.loads((root / "config" / "agent_registry.json").read_text(encoding="utf-8"))
    entry = registry["agents"][agent]
    backend, model_id = entry["backend"], entry["model"]
    sources = {"registry": "config/agent_registry.json"}
    if profile == "local":
        backend, model_id = pipeline_literal("_LOCAL_PROFILE", root / "scripts" / "pipeline.py")[agent]
        try:
            chosen = json.loads((root / "config" / "local_models.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            chosen = {}
        key = {"local_producer": "active_producer", "local_auditor": "active_auditor"}.get(backend)
        if key and str(chosen.get(key) or "").strip():
            model_id = chosen[key].strip()
            sources["model"] = "config/local_models.json " + key
    if backend not in decoding_policy.LOCAL_BACKENDS:
        raise ValueError("the reading agent's backend %r is not a local backend" % backend)
    decoding = decoding_policy.policy(backend, root)
    declared, _ = decoding_policy.declaration(root)
    role = declared["backends"][backend].get("role")
    mode = final_models.mode()
    frozen = mode == "final" and backend == "local_producer"
    # The two checkpoints exist for the frozen producer only; anywhere else the reference
    # loader runs and only `base` is accepted.
    chosen = resolve_checkpoint("final" if frozen else "base", checkpoint)
    if frozen:
        model_id = final_models.specification(FINAL_ROLE, root)["model_id"]
        sources["model"] = "config/final_models.json producer"
    allowance = (int(max_new_tokens) if max_new_tokens is not None
                 else int(pipeline_literal("PRODUCTION_MAX_TOKENS", root / "scripts" / "pipeline.py")))
    return {"agent": agent, "agent_source": "placeholder" if agent == READING_AGENT else "argument",
            "backend": backend, "model_id": model_id, "model_mode": mode, "checkpoint": chosen,
            "role": role, "decoding": decoding, "max_new_tokens": allowance,
            "max_new_tokens_source": "argument" if max_new_tokens is not None
            else "pipeline PRODUCTION_MAX_TOKENS", "sources": sources, "attention": attention}


# ---------------------------------------------------------------------------
# attention (D-056 conditions 1 to 4)


def attention_record(prefill_chunk=None, prefill_decision=None):
    """B1's declared attention: sdpa, the memory-efficient backend pinned, and how the prompt
    is prefilled (one shot, or in chunks of `prefill_chunk` tokens adopted by the decision
    `prefill_decision`). Chunked prefill is off unless both are given."""
    if (prefill_chunk is None) != (prefill_decision is None):
        raise ValueError("chunked prefill needs both --prefill-chunk and --prefill-decision "
                         "(the recorded decision that adopted it)")
    if prefill_chunk is not None:
        if type(prefill_chunk) is not int or prefill_chunk < 1:
            raise ValueError("--prefill-chunk is a positive number of tokens")
        if not DECISION_ID.fullmatch(str(prefill_decision)):
            raise ValueError("--prefill-decision names a recorded decision (D-NNN)")
    return {"attention_implementation": B1_ATTENTION, "sdpa_backend": B1_SDPA_BACKEND,
            "prefill": "chunked" if prefill_chunk else "one_shot",
            "prefill_chunk_tokens": prefill_chunk, "prefill_decision": prefill_decision}


def declared_attention(reader):
    """The attention a run declares: the reader's, or the default (one-shot prefill)."""
    return dict((reader or {}).get("attention") or attention_record())


def _attention_configs(model):
    """Every distinct config object of the model that carries an attention setting: the
    model's own and its modules' (one object in transformers, shared by every layer)."""
    found = {}
    candidates = [getattr(model, "config", None)]
    modules = getattr(model, "modules", None)
    if callable(modules):
        candidates += [getattr(m, "config", None) for m in modules()]
    for config in candidates:
        if config is not None and hasattr(config, "_attn_implementation"):
            found[id(config)] = config
    return list(found.values())


def enabled_sdpa_backends(torch):
    """The sdpa backends torch currently allows, by SDPBackend name, joined with `+`."""
    switches = torch.backends.cuda
    return "+".join(name for name, switch in sorted(SDPA_SWITCHES.items())
                    if getattr(switches, switch)())


@contextlib.contextmanager
def b1_attention(model, backends=None):
    """B1's attention for the calls inside the block (D-056 conditions 1 and 2): the model's
    attention setting switched to sdpa and the memory-efficient sdpa backend pinned, so a
    refused kernel raises rather than falling back; the setting is restored in a finally to
    what it was (eager, as scripts/final_models.py loads it), whatever the block raised.
    Yields observe(), which reads the setting and the enabled backends as they stand inside.
    `backends` (SDPBackend names) is for the checks' CPU model only."""
    import torch
    from torch.nn.attention import SDPBackend, sdpa_kernel
    configs = _attention_configs(model)
    if not configs:
        raise SetupError("the model carries no attention setting to switch")
    before = [c._attn_implementation for c in configs]
    chosen = [getattr(SDPBackend, name) for name in (backends or (B1_SDPA_BACKEND,))]

    def observe():
        values = sorted({str(c._attn_implementation) for c in configs})
        return {"attention_implementation": "+".join(values),
                "sdpa_backend": enabled_sdpa_backends(torch)}

    try:
        for config in configs:
            config._attn_implementation = B1_ATTENTION
        with sdpa_kernel(chosen):
            yield observe
    finally:
        for config, value in zip(configs, before):
            config._attn_implementation = value


def chunked_prefill(model, input_ids, chunk_tokens, *, cache=None):
    """The fallback of D-056 condition 4: every prompt token but the last fed through the
    model in chunks of `chunk_tokens`, filling a KV cache, under whatever attention the
    caller set (b1_attention). generate() then reads only the last token from the prompt,
    so its next-token scores equal one-shot prefill's (checked on a tiny CPU model)."""
    import torch
    if cache is None:
        from transformers import DynamicCache
        cache = DynamicCache()
    total = int(input_ids.shape[1]) - 1
    for start in range(0, total, int(chunk_tokens)):
        end = min(start + int(chunk_tokens), total)
        model(input_ids=input_ids[:, start:end],
              attention_mask=torch.ones((input_ids.shape[0], end), dtype=torch.long, device=input_ids.device),
              past_key_values=cache, use_cache=True,
              cache_position=torch.arange(start, end, device=input_ids.device), logits_to_keep=1)
    return cache


def generate_ids(model, inputs, *, max_new_tokens, decoding_kwargs, prefill_chunk=None, **extra):
    """model.generate on the rendered prompt: one-shot prefill, or chunked prefill first
    when `prefill_chunk` is set. `extra` is for the checks (scores)."""
    if not prefill_chunk:
        return model.generate(**inputs, max_new_tokens=max_new_tokens, **decoding_kwargs, **extra)
    cache = chunked_prefill(model, inputs["input_ids"], prefill_chunk)
    return model.generate(**inputs, past_key_values=cache, max_new_tokens=max_new_tokens,
                          **decoding_kwargs, **extra)


def setup_failure_kind(exc):
    """The kind of a call failure that stops the run (D-056 condition 3), or None for an
    ordinary generation failure (a failed call, ABSTAIN). torch.cuda.OutOfMemoryError is
    read by its class name, so this module imports no model library."""
    if any(cls.__name__ == "OutOfMemoryError" for cls in type(exc).__mro__):
        return "out_of_memory"
    text = str(exc)
    if isinstance(exc, RuntimeError):
        if "out of memory" in text.lower():
            return "out_of_memory"
        if "No available kernel" in text or "No viable backend for scaled_dot_product_attention" in text:
            return "attention_kernel_refused"
    return None


class LocalBackend:
    """The model, loaded and called the way agent_wrapper.call_local loads and calls it:
    final mode through final_models.resident, base mode through the shared loader, the
    model's own chat template with a system and a user turn, the frozen decoding kwargs.
    prepare() loads it once; nothing generates before that."""

    def __init__(self, reader, run_context, *, libs=None):
        self.reader, self.run_context, self.libs = reader, run_context, libs
        self._tok = self._mdl = None

    def prepare(self):
        """Load and verify; returns {model_id, digest, decoding, checkpoint} of what was
        loaded. In final mode the reader's checkpoint decides: `tuned` through
        final_models.resident (base plus adapter), `base` through load_base_checkpoint (the
        same base, no adapter)."""
        checkpoint = self.reader.get("checkpoint") or TUNED
        if self.reader["model_mode"] == "final" and self.reader["backend"] == "local_producer":
            spec = final_models.specification(FINAL_ROLE)
            record, digest = checkpoint_record(checkpoint, spec)
            if checkpoint == TUNED:
                final_models.verify_runtime()
                self._tok, self._mdl = final_models.resident(FINAL_ROLE, self.run_context)
            else:
                self._tok, self._mdl = load_base_checkpoint(spec=spec, libs=self.libs)
        else:
            import agent_wrapper
            from huggingface_hub import snapshot_download
            self._tok, self._mdl = agent_wrapper._load_qwen(self.reader["model_id"])
            # PROVISIONAL: a base-mode checkpoint is identified by its local snapshot revision
            snapshot = Path(snapshot_download(self.reader["model_id"], local_files_only=True))
            digest = "snapshot:" + snapshot.name
            record = {"checkpoint": BASE, "model_id": self.reader["model_id"],
                      "revision": snapshot.name, "model_safetensors_sha256": None,
                      "adapter_sha256": None, "adapter_applied": False, "adapter_checkpoint": None}
        return {"model_id": self.reader["model_id"], "digest": digest,
                "decoding": dict(self.reader["decoding"]["kwargs"]), "checkpoint": record,
                "attention": declared_attention(self.reader)}

    def _loaded(self):
        if self._tok is None:
            raise SetupError("the model was not prepared before the first call")
        return self._tok, self._mdl

    def _render(self, system, user):
        tok, _ = self._loaded()
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    def count_prompt(self, system, user):
        tok, _ = self._loaded()
        return len(tok(self._render(system, user), add_special_tokens=False)["input_ids"])

    def count(self, text):
        tok, _ = self._loaded()
        return len(tok(text, add_special_tokens=False)["input_ids"])

    def max_context(self):
        _, mdl = self._loaded()
        return int(mdl.config.max_position_embeddings)

    def generate(self, system, user, max_new_tokens):
        import torch
        tok, mdl = self._loaded()
        prompt = self._render(system, user)
        inputs = tok(prompt, return_tensors="pt", add_special_tokens=False).to(mdl.device)
        attention = declared_attention(self.reader)
        # D-056: sdpa with the memory-efficient backend pinned for this call only; the
        # resident model is eager again when the block ends, whatever it raised.
        with torch.no_grad(), b1_attention(mdl) as observe:
            observed = observe()
            out = generate_ids(mdl, inputs, max_new_tokens=max_new_tokens,
                               decoding_kwargs=self.reader["decoding"]["kwargs"],
                               prefill_chunk=attention["prefill_chunk_tokens"])
        start = int(inputs["input_ids"].shape[1])
        generated = int(out[0].shape[0]) - start
        text = tok.decode(out[0][start:], skip_special_tokens=True)
        del inputs, out
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return {"text": text, "payload": prompt, "form": "rendered_prompt",
                "output_tokens": generated, "attention": dict(attention, **observed)}


# ---------------------------------------------------------------------------
# the run


class RunContext:
    """The run context B1 hands to the write paths it shares with the pipeline:
    reply_records.write reads `run_dir` and `run_id`, and final_models.resident's load
    telemetry (model_telemetry.emit) writes under `logs_dir()`, as on the pipeline's own
    RunContext. A bare namespace without logs_dir() made the tuned load raise."""

    def __init__(self, run_dir, run_id):
        self.run_dir, self.run_id = str(run_dir), run_id

    def logs_dir(self):
        return Path(self.run_dir) / "logs"


def load_items(path, document_id):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("items") if isinstance(data, dict) else data
    items = [r for r in rows or [] if str(r.get("document_id")) == str(document_id)]
    for r in items:
        for key in ("item_id", "rule_id", "benchmark"):
            if not r.get(key):
                raise ValueError("an item lacks " + key)
    return sorted(items, key=lambda r: str(r["item_id"]))


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _hashed(text):
    if text is None:
        return None
    data = text.encode("utf-8")
    return {"sha256": hashlib.sha256(data).hexdigest(), "length_bytes": len(data)}


def verify_identity(loaded, expected, attention=None):
    """Compare what was loaded with the values passed in (VERSIONS.md): a mismatch stops
    the run (section 4). `attention`, the run's declared attention (D-056 condition 1), is
    always compared when given: a backend that reports none, or another, stops the run."""
    wrong = [key for key in ("model_id", "digest", "decoding", "attention")
             if key in expected and expected[key] != loaded.get(key)]
    if attention is not None and loaded.get("attention") != attention and "attention" not in wrong:
        wrong.append("attention")
    if wrong:
        raise SetupError("loaded model differs from the recorded values on: " + ", ".join(wrong))


def length_reached(result, allowance):
    """True when the reply's length reached the output allowance (it may be cut short),
    False when it did not, None when the backend does not report its output length."""
    tokens = result.get("output_tokens") if isinstance(result, dict) else None
    if type(tokens) is not int:
        return None
    return tokens >= int(allowance)


def run(bundle, items_path, out, *, backend=None, reader=None, prompt_path=PROMPT_PATH,
        run_id=None, expected=None, development=False, sensitive=False):
    """Run B1 on one bundle. `backend` needs prepare() -> {model_id, digest, decoding},
    count_prompt(system, user), max_context() and generate(system, user, max_new_tokens)
    -> {text, payload, form, output_tokens}; None builds the LocalBackend (a real model load).
    `expected` holds the recorded model_id, digest and decoding; it may be omitted only
    with development=True, which is recorded."""
    out = Path(out)
    if not expected and not development:
        raise SetupError("the recorded model id, checkpoint digest and decoding are required "
                         "(section 4); only a development run may omit them")
    spec = load_prompt(prompt_path)
    data = python_only.load_bundle(bundle)
    if len(data["targets"]) != 1:
        raise ValueError("a benchmark bundle names exactly one document under review")
    doc = data["targets"][0]
    items = load_items(items_path, doc["id"])
    if not items:
        raise ValueError("items.json holds no item for document " + doc["id"])
    unknown = sorted({str(i["benchmark"]).lower() for i in items} - set(spec["benchmarks"]))
    if unknown:
        raise ValueError("no prompt for benchmark " + ", ".join(unknown))
    reader = reader or resolve_reader()
    context = RunContext(out, run_id or ("b1-" + uuid.uuid4().hex[:12]))
    backend = backend or LocalBackend(reader, context)
    conventions = b1_prompt.conventions_from_bundle(bundle)
    reference = b1_prompt.reference_from_bundle(bundle)
    # Load and verify once, before the first item; nothing below is caught.
    loaded = backend.prepare()
    attention = declared_attention(reader)
    verify_identity(loaded, expected or {}, attention)
    users = {i["item_id"]: render_user(spec, str(i["benchmark"]).lower(), document=doc["text"],
                                       conventions=conventions, item=i, reference=reference)
             for i in items}
    systems = {i["item_id"]: render_system(spec, str(i["benchmark"]).lower()) for i in items}
    limit = backend.max_context()
    over = [i for i, user in users.items()
            if backend.count_prompt(systems[i], user) + reader["max_new_tokens"] > limit]
    if over:
        raise SetupError("prompt plus output allowance exceeds the model's context for %d item(s): %s"
                         % (len(over), ", ".join(over[:5])))
    decoding = dict(decoding_policy.usage_fields(reader["decoding"]),
                    max_new_tokens=reader["max_new_tokens"])
    summary, written = {}, []
    for item in items:
        bench_key = str(item["benchmark"]).lower()
        bench = spec["benchmarks"][bench_key]
        error, result, stop = "", {}, None
        try:
            result = backend.generate(systems[item["item_id"]], users[item["item_id"]],
                                      reader["max_new_tokens"]) or {}
        except SetupError:
            raise
        except Exception as exc:  # a generation error is a failed call, and still a record
            error = type(exc).__name__
            # D-056 condition 3: out of memory, or a refused kernel, stops the run.
            stop = setup_failure_kind(exc)
        reply = result.get("text") if isinstance(result.get("text"), str) else None
        # The attention the call ran under, as the backend observed it inside the switch;
        # a backend that observes nothing (a failed call) is recorded under the declared one.
        observed = result.get("attention") if isinstance(result.get("attention"), dict) else None
        call_attention = observed or attention
        call_id = reply_records.write(
            context, agent=AGENT_LABEL, backend=reader["backend"], model_id=reader["model_id"],
            model_mode=reader["model_mode"], payload=result.get("payload"),
            payload_form=result.get("form"), reply=reply, ok=not error, error=error,
            decoding=decoding, sensitive=sensitive, phase=ARM, doc_id=doc["id"],
            attention=call_attention)
        if not call_id:
            raise SetupError("the reply record for item %s could not be written" % item["item_id"])
        written.append(call_id)
        if stop:
            _write_json(out / SETUP_FAILURE_FILE, {
                "baseline": BASELINE_TEXT, "arm": ARM, "schema": "b1-setup-failure-v1",
                "kind": stop, "error": error, "item_id": item["item_id"], "document_id": doc["id"],
                "items_total": len(items), "items_before_stop": len(written) - 1,
                "reply_records_written": len(written), "call_id": call_id,
                "checkpoint": reader.get("checkpoint"), "attention": attention,
                "counted_as": "a setup failure of the B1 run, never an abstention (D-056 condition 3)",
                "finished_at": _now()})
            raise SetupFailure(stop, item["item_id"], error)
        if observed is not None and observed != attention:
            raise SetupError("item %s ran under attention %s, not the declared %s"
                             % (item["item_id"], json.dumps(observed, sort_keys=True),
                                json.dumps(attention, sort_keys=True)))
        parsed = parse_reply(reply, bench, item["item_id"]) if not error else dict(
            parse_reply(None, bench), failure="backend_failure")
        undecided = bool(parsed["parsed"]) and _norm_label(parsed["label"]) == _norm_label(bench["undecided"])
        reached = None if error else length_reached(result, reader["max_new_tokens"])
        texts = ({"evidence": parsed["evidence"], "reason": parsed["reason"]} if not sensitive else
                 {"evidence": None, "reason": None, "evidence_hashed": _hashed(parsed["evidence"]),
                  "reason_hashed": _hashed(parsed["reason"])})
        _write_json(out / "labels" / (str(item["item_id"]) + ".json"), dict({
            "baseline": BASELINE_TEXT, "arm": ARM, "schema": "b1-label-v2",
            "item_id": item["item_id"], "document_id": doc["id"], "rule_id": item["rule_id"],
            "benchmark": bench_key, "label": parsed["label"], "abstain": not parsed["parsed"],
            "undecided": undecided, "parse_failure": parsed["failure"],
            "parse_repaired": parsed["repaired"], "output_tokens": result.get("output_tokens")
            if type(result.get("output_tokens")) is int else None,
            "length_reached_allowance": reached}, **texts, **{
            "reply_item_id": parsed["reply_item_id"], "item_id_matches": parsed["item_id_matches"],
            "call_id": call_id, "backend_ok": not error, "reading_agent": reader["agent"],
            "model_id": reader["model_id"], "model_mode": reader["model_mode"],
            "checkpoint": reader.get("checkpoint"), "attention": call_attention}))
        row = summary.setdefault(bench_key, {"items": 0, "parsed": 0, "undecided": 0,
                                             "abstain": 0, "backend_failures": 0, "repaired": 0,
                                             "length_reached_allowance": 0,
                                             "length_not_reported": 0})
        row["items"] += 1
        row["length_reached_allowance"] += int(reached is True)
        row["length_not_reported"] += int(reached is None)
        row["parsed"] += int(parsed["parsed"])
        row["undecided"] += int(undecided)
        row["abstain"] += int(not parsed["parsed"])
        row["backend_failures"] += int(bool(error))
        row["repaired"] += int(parsed["repaired"])
    if len(written) != len(items) or len(set(written)) != len(items):
        raise SetupError("reply records (%d) do not match items (%d)" % (len(set(written)), len(items)))
    for row in summary.values():
        row["parse_rate"] = row["parsed"] / row["items"]
        row["parse_rate_floor"] = PARSE_RATE_FLOOR
        row["below_parse_rate_floor"] = row["parse_rate"] < PARSE_RATE_FLOOR
    result = {"baseline": BASELINE_TEXT, "arm": ARM, "finished_at": _now(), "run_id": context.run_id,
              "bundle": Path(bundle).name, "document_id": doc["id"],
              "prompt": {"source": spec.get("source"), "status": spec.get("status")},
              "reader": {k: reader.get(k) for k in ("agent", "agent_source", "backend", "model_id",
                                                    "model_mode", "checkpoint", "max_new_tokens",
                                                    "max_new_tokens_source")},
              "checkpoint": loaded.get("checkpoint") or {"checkpoint": reader.get("checkpoint")},
              "attention": attention,
              "loaded": loaded, "verified_against": sorted(set(expected or {}) | {"attention"}),
              "development": bool(development), "sensitive": bool(sensitive),
              "reference_material": bool(reference), "decoding": decoding, "benchmarks": summary}
    _write_json(out / "b1_summary.json", result)
    return result


def run_b1(bundle, items, out, checkpoint, *, expected=None, development=False,
           agent=READING_AGENT, max_new_tokens=None, sensitive=False, run_id=None,
           backend=None, profile="local", prefill_chunk=None, prefill_decision=None):
    """The one public entry for a runner that imports this file: B1 on one bundle with one
    checkpoint (`tuned` or `base`), into `out` (a folder of its own per checkpoint). The
    reader is resolved from the tracked configuration as the command line resolves it; a
    real model is loaded unless `backend` is given (the checks' mocked model). Returns the
    b1_summary.json content; raises on any setup failure, before anything is generated."""
    reader = resolve_reader(agent=agent, profile=profile, max_new_tokens=max_new_tokens,
                            checkpoint=checkpoint, prefill_chunk=prefill_chunk,
                            prefill_decision=prefill_decision)
    return run(bundle, items, out, backend=backend, reader=reader, expected=expected,
               development=development, sensitive=sensitive, run_id=run_id)


def pool_parse_rates(runs_root, out=None) -> dict:
    """Section 5.4: the development parse rate per benchmark, pooled over every document's
    b1_summary.json under `runs_root` (one bare_model.py output folder per document, as the
    adapters' label command reads them). The 95 percent floor is decided on this pooled rate,
    never on one document's; a document's own `below_parse_rate_floor` is information only.
    Writes `out` (default `<runs_root>/b1_parse_rates.json`)."""
    root = Path(runs_root)
    pooled, documents = {}, 0
    for path in sorted(root.glob("*/b1_summary.json")):
        summary = json.loads(path.read_text(encoding="utf-8"))
        documents += 1
        for bench, row in (summary.get("benchmarks") or {}).items():
            total = pooled.setdefault(bench, {"documents": 0, "items": 0, "parsed": 0})
            total["documents"] += 1
            total["items"] += int(row["items"])
            total["parsed"] += int(row["parsed"])
    if not documents:
        raise ValueError("no b1_summary.json under " + str(root))
    for row in pooled.values():
        row["parse_rate"] = row["parsed"] / row["items"] if row["items"] else 0.0
        row["parse_rate_floor"] = PARSE_RATE_FLOOR
        row["below_parse_rate_floor"] = row["parse_rate"] < PARSE_RATE_FLOOR
    result = {"baseline": BASELINE_TEXT, "arm": ARM, "documents": documents,
              "floor_decided_on": "the pooled rate per benchmark (section 5.4)",
              "benchmarks": dict(sorted(pooled.items()))}
    _write_json(Path(out) if out else root / "b1_parse_rates.json", result)
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["pool"]:
        pool = argparse.ArgumentParser(prog="bare_model.py pool",
                                       description="pool the development parse rate per benchmark")
        pool.add_argument("--runs", required=True, help="one bare_model.py output folder per document")
        pool.add_argument("--out")
        args = pool.parse_args(argv[1:])
        try:
            result = pool_parse_rates(args.runs, args.out)
        except (OSError, ValueError, KeyError) as exc:
            print("pooling stopped: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
            return 4
        print(json.dumps(result["benchmarks"], indent=2))
        return 0
    args = build_parser().parse_args(argv)
    expected = {}
    if args.expect_model_id:
        expected["model_id"] = args.expect_model_id
    if args.expect_digest:
        expected["digest"] = args.expect_digest
    if args.expect_decoding:
        expected["decoding"] = json.loads(args.expect_decoding)
    try:
        result = run_b1(args.bundle, args.items, args.out, args.checkpoint, expected=expected,
                        development=args.development, agent=args.agent,
                        max_new_tokens=args.max_new_tokens, sensitive=args.sensitive,
                        profile=args.profile, prefill_chunk=args.prefill_chunk,
                        prefill_decision=args.prefill_decision)
    except SetupFailure as exc:  # D-056 condition 3: reported apart, in b1_setup_failure.json
        print("B1 stopped by a setup failure (%s), recorded in %s: %s"
              % (exc.kind, SETUP_FAILURE_FILE, exc), file=sys.stderr)
        return 4
    except Exception as exc:  # setup, load, verification or record failure: stop, non-zero
        print("B1 stopped before or during the run: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 4
    print(json.dumps(result["benchmarks"], indent=2))
    return 0


def build_parser():
    """The run's argument parser, the one main() parses with. The ordinary final runner seals
    a checkpoint's arguments against exactly these options (tools/ordinary_final_run.py
    B1_RUNNER_ARGS and B1_SEALED_ARGS; a controller check holds the two equal). No option is
    taken by an abbreviation, so a sealed argument means here exactly what the seal admitted."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0], allow_abbrev=False)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--items", required=True, help="items.json written beside the bundle")
    parser.add_argument("--out", required=True)
    parser.add_argument("--agent", default=READING_AGENT,
                        help="the main reading agent (PROCESSOR is a placeholder pending section 12 item 8)")
    parser.add_argument("--profile", choices=["local", "registry"], default="local")
    parser.add_argument("--checkpoint", choices=list(CHECKPOINTS), default=None,
                        help="final mode: the tuned producer (default) or its pinned base without "
                             "the adapter; base mode: base only")
    parser.add_argument("--max-new-tokens", type=int, default=None)
    parser.add_argument("--expect-model-id")
    parser.add_argument("--expect-digest")
    parser.add_argument("--expect-decoding", help="the decoding kwargs as a JSON object")
    parser.add_argument("--development", action="store_true",
                        help="development run: the recorded values may be omitted (recorded)")
    parser.add_argument("--sensitive", action="store_true",
                        help="keep only hashes of prompts, replies, evidence and reason")
    parser.add_argument("--prefill-chunk", type=int, default=None,
                        help="D-056 fallback, off by default: prefill the prompt in chunks of this "
                             "many tokens; only with --prefill-decision")
    parser.add_argument("--prefill-decision", default=None,
                        help="the recorded decision (D-NNN) that adopted chunked prefill")
    return parser


if __name__ == "__main__":
    sys.exit(main())
