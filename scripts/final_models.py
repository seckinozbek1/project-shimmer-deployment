"""Frozen ordinary inference artifacts. Importing this module loads no model.

Explicit SHIMMER_MODEL_MODE=final selects the frozen pair; base preserves the
reference runtime. No training/evaluation datasets or cloud clients are imported.
"""
import contextlib
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
_RESIDENTS = {}
_LOAD_LOCK = threading.RLock()
PINS = {
    'producer': {'adapter': '8354d6545272399ea6771f1a6b560309e882fd7348f5c2be9cbd1bab01160703',
                 'adapter_config': 'cd672d24a74575fe9bec0e0589aa84a41f3078d5a23edaaee8ae1cafbc683507'},
    'auditor': {'adapter': '0ec8212f5288e5960f1e816d93c9c7e1206eed7c380b45cf355ae0825ecc1b5e',
                'adapter_config': 'af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6',
                'head': '6a2fcf89d3e843d5364443c20add30f0542e9dfbf00ff3b0e4d78ede397fdc3a',
                'mean': '370b185841099279202b09540b45231f70fc1b109795faf520369964831678f5',
                'std': '1221aff7ce64f090635267884183baabbd521e9a1738221555f074b4478f304a'}}

# D-058, D-060 and D-061 (docs/loop/DECISIONS.md): the producer's attention, fixed at load from
# a setting that travels in the sealed manifest's environment. Exactly two values: eager, the
# default (the kernel the producer was trained and evaluated with and ran from v5 to v12; L2's
# evidence kept it, D-060), and sdpa, under which every producer generate call runs pinned to
# the memory-efficient sdpa backend (pinned_attention), accepted only with the recorded
# decision (D-NNN) that asks for it, for a measurement pass. The Auditor896 classifier is never
# governed by this setting: it loads eager, as its runtime contract says. The models _load_qwen
# loads (VERIFIER, PRACTICE_AUDITOR, FACT_CHECKER, REDACTOR) run sdpa, pinned the same way.
PRODUCER_ATTENTION_ENV = 'SHIMMER_PRODUCER_ATTENTION'
PRODUCER_ATTENTION_DECISION_ENV = 'SHIMMER_PRODUCER_ATTENTION_DECISION'
EAGER = 'eager'
SDPA = 'sdpa'
PRODUCER_ATTENTION_DEFAULT = EAGER
PRODUCER_ATTENTIONS = (EAGER, SDPA)
SDPA_BACKEND = 'EFFICIENT_ATTENTION'
DECISION_ID = re.compile(r'D-\d{3}')
# D-060 and D-061: E, chunked prefill. Every producer generate call (B3) and every B1 call feeds
# its prompt through the KV cache in fixed chunks of PREFILL_CHUNK_DEFAULT tokens under the
# producer's attention (eager), leaving GENERATE_TAIL_TOKENS prompt tokens to generate() itself,
# so the first generated token is computed by the same kernel path as one-shot prefill. The
# chunk size is a sealed setting like the attention: 512 under D-061 unless a recorded decision
# names another size or one-shot prefill (`one_shot`, a measurement pass). A prompt of at most
# one chunk plus the tail is prefilled by generate() in one step: chunking it would change
# nothing about its memory.
PRODUCER_PREFILL_ENV = 'SHIMMER_PRODUCER_PREFILL_CHUNK'
PRODUCER_PREFILL_DECISION_ENV = 'SHIMMER_PRODUCER_PREFILL_DECISION'
PREFILL_CHUNK_DEFAULT = 512
PREFILL_DECISION_DEFAULT = 'D-061'
ONE_SHOT = 'one_shot'
CHUNKED = 'chunked'
GENERATE_TAIL_TOKENS = 2
# torch.backends.cuda's switch for each sdpa backend, by SDPBackend name.
SDPA_SWITCHES = {'FLASH_ATTENTION': 'flash_sdp_enabled', 'EFFICIENT_ATTENTION': 'mem_efficient_sdp_enabled',
                 'MATH': 'math_sdp_enabled', 'CUDNN_ATTENTION': 'cudnn_sdp_enabled'}


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def mode():
    value = os.environ.get('SHIMMER_MODEL_MODE', 'base')
    require(value in {'base', 'final'}, 'Unknown model mode; no fallback')
    return value


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def specification(role, root=ROOT):
    value = json.loads((Path(root) / 'config/final_models.json').read_text(encoding='utf8'))[role]
    require(value['checkpoint'] == {'producer': 168, 'auditor': 896}[role], 'Frozen checkpoint required')
    require({k: v['sha256'] for k, v in value['files'].items()} == PINS[role], 'Mixed or unapproved artifacts')
    return value


def verify(role, root=ROOT):
    spec = specification(role, root)
    paths = {}
    for key, entry in spec['files'].items():
        path = Path(root) / entry['path']
        require(path.is_file(), 'Missing frozen ' + role + ' ' + key)
        require(sha(path) == entry['sha256'], 'Frozen hash mismatch: ' + role + ' ' + key)
        paths[key] = path
    require(paths['adapter'].parent == paths['adapter_config'].parent, 'Adapter/config directory mismatch')
    return spec, paths


def identity(role, spec=None):
    spec = spec or specification(role)
    return dict(model_mode='final', designation=role, model_id=spec['model_id'],
                model_revision=spec['revision'], adapter_checkpoint=spec['checkpoint'],
                adapter_sha256=spec['files']['adapter']['sha256'],
                head_sha256=spec['files'].get('head', {}).get('sha256'),
                normalization_sha256={k: spec['files'][k]['sha256'] for k in ('mean', 'std') if k in spec['files']},
                runtime_engine='transformers/peft/bitsandbytes', limitations=spec.get('limitations'))


def producer_attention(environ=None):
    """The producer's attention as the sealed environment sets it (D-058, D-060):
    {attention_implementation, sdpa_backend, attention_decision}. Unset is eager. sdpa is
    accepted only with SHIMMER_PRODUCER_ATTENTION_DECISION naming a recorded decision
    (D-NNN), for a measurement pass; a decision with eager, or any other value, is refused,
    never ignored."""
    environ = os.environ if environ is None else environ
    value = environ.get(PRODUCER_ATTENTION_ENV)
    value = PRODUCER_ATTENTION_DEFAULT if value is None else value
    decision = environ.get(PRODUCER_ATTENTION_DECISION_ENV)
    require(value in PRODUCER_ATTENTIONS, PRODUCER_ATTENTION_ENV + ' is eager or sdpa; no other attention is admitted')
    require((value == SDPA) == (decision is not None),
            PRODUCER_ATTENTION_ENV + '=sdpa needs ' + PRODUCER_ATTENTION_DECISION_ENV
            + ' (the recorded decision that asks for it), and a decision is accepted only with sdpa')
    require(decision is None or bool(DECISION_ID.fullmatch(decision)),
            PRODUCER_ATTENTION_DECISION_ENV + ' names a recorded decision (D-NNN)')
    return dict(attention_implementation=value, sdpa_backend=SDPA_BACKEND if value == SDPA else None,
                attention_decision=decision)


def prefill_setting(chunk=None, decision=None):
    """How a producer prompt is prefilled (D-060, D-061), one rule for B3 and B1:
    {prefill, prefill_chunk_tokens, prefill_decision}. With nothing named it is chunked at
    PREFILL_CHUNK_DEFAULT tokens under PREFILL_DECISION_DEFAULT. Another chunk size (a positive
    whole number) or `one_shot` (no chunking, a measurement pass) is accepted only with the
    recorded decision (D-NNN) that asks for it; a decision naming the default is accepted
    only when it is the default's own. Anything else is refused, never ignored."""
    if isinstance(chunk, str) and chunk != ONE_SHOT:
        require(chunk.isdigit(), 'The prefill chunk is a positive number of tokens or one_shot')
        chunk = int(chunk)
    require(chunk is None or chunk == ONE_SHOT or (type(chunk) is int and chunk > 0),
            'The prefill chunk is a positive number of tokens or one_shot')
    require(decision is None or bool(DECISION_ID.fullmatch(str(decision))),
            'The prefill decision names a recorded decision (D-NNN)')
    default = chunk is None or chunk == PREFILL_CHUNK_DEFAULT
    if default:
        require(decision in (None, PREFILL_DECISION_DEFAULT),
                'A prefill decision is named only with another chunk size or one_shot')
        return dict(prefill=CHUNKED, prefill_chunk_tokens=PREFILL_CHUNK_DEFAULT,
                    prefill_decision=PREFILL_DECISION_DEFAULT)
    require(decision is not None, 'A prefill chunk other than %d, or one_shot, needs the recorded decision '
            'that asks for it' % PREFILL_CHUNK_DEFAULT)
    if chunk == ONE_SHOT:
        return dict(prefill=ONE_SHOT, prefill_chunk_tokens=None, prefill_decision=decision)
    return dict(prefill=CHUNKED, prefill_chunk_tokens=chunk, prefill_decision=decision)


def producer_prefill(environ=None):
    """The producer's prefill as the sealed environment sets it (prefill_setting):
    SHIMMER_PRODUCER_PREFILL_CHUNK and SHIMMER_PRODUCER_PREFILL_DECISION, both unset by
    default (chunked at 512 under D-061)."""
    environ = os.environ if environ is None else environ
    return prefill_setting(environ.get(PRODUCER_PREFILL_ENV), environ.get(PRODUCER_PREFILL_DECISION_ENV))


# What a call not governed by the producer's prefill setting records (a _load_qwen model's
# call: VERIFIER, PRACTICE_AUDITOR, FACT_CHECKER, REDACTOR): one-shot, no decision.
NOT_GOVERNED_PREFILL = dict(prefill=ONE_SHOT, prefill_chunk_tokens=None, prefill_decision=None)


def _forward_owner(model):
    """The module whose forward() generate() calls once per step: the one holding lm_head
    directly (a PEFT wrapper reaches it through attribute forwarding, never as its own
    child), else the model itself. None for a stand-in model that is no torch module."""
    module_type = getattr(getattr(sys.modules.get('torch'), 'nn', None), 'Module', None)
    if not isinstance(module_type, type) or not isinstance(model, module_type):
        return None
    for module in model.modules():
        if 'lm_head' in module._modules:
            return module
    return model


def chunked_prefill(model, input_ids, chunk_tokens, *, cache=None):
    """E (D-060, D-061): every prompt token but the last GENERATE_TAIL_TOKENS fed through the
    model in chunks of `chunk_tokens`, filling a KV cache, under whatever attention the model
    carries (eager for the producer). Returns (cache, chunks)."""
    torch = importlib.import_module('torch')
    if cache is None:
        cache = importlib.import_module('transformers').DynamicCache()
    total = int(input_ids.shape[1]) - GENERATE_TAIL_TOKENS
    chunks = 0
    for start in range(0, max(total, 0), int(chunk_tokens)):
        end = min(start + int(chunk_tokens), total)
        model(input_ids=input_ids[:, start:end],
              attention_mask=torch.ones((input_ids.shape[0], end), dtype=torch.long, device=input_ids.device),
              past_key_values=cache, use_cache=True,
              cache_position=torch.arange(start, end, device=input_ids.device), logits_to_keep=1)
        chunks += 1
    return cache, chunks


def generate_with_prefill(model, inputs, *, max_new_tokens, decoding_kwargs, prefill, **extra):
    """The ONE generate helper of every producer call (agent_wrapper) and every B1 call
    (bare_model), D-061 item 6. `prefill` is a prefill_setting record. One-shot, or a prompt of
    at most one chunk plus the tail, is plain generate(); otherwise chunked_prefill fills the
    cache first and generate() prefills the last GENERATE_TAIL_TOKENS tokens itself. Returns
    (output, measured): measured = {prompt_tokens, chunks, chunked_tokens, tail_tokens,
    prefill_seconds}, prefill_seconds being the time from the call's start to the end of the
    forward step that produced the first generated token's scores (CUDA synchronized there),
    None for a stand-in model without forward hooks. `extra` is for the checks (scores)."""
    import time
    prompt_tokens = int(inputs['input_ids'].shape[1])
    chunk = prefill.get('prefill_chunk_tokens') if prefill.get('prefill') == CHUNKED else None
    chunked = bool(chunk) and prompt_tokens > int(chunk) + GENERATE_TAIL_TOKENS
    owner = _forward_owner(model)
    seen = dict(forwards=0, at=None, target=None)
    started = time.perf_counter()

    def timer(module, args, output):
        seen['forwards'] += 1
        if seen['at'] is None and seen['forwards'] == seen['target']:
            torch = sys.modules.get('torch')
            cuda = getattr(torch, 'cuda', None)
            try:
                if cuda is not None and cuda.is_available() and cuda.is_initialized():
                    cuda.synchronize()
            except Exception:
                pass
            seen['at'] = time.perf_counter()
    handle = owner.register_forward_hook(timer) if owner is not None else None
    try:
        if not chunked:
            seen['target'] = 1
            out = model.generate(**inputs, max_new_tokens=max_new_tokens, **decoding_kwargs, **extra)
            chunks = 0
        else:
            cache, chunks = chunked_prefill(model, inputs['input_ids'], chunk)
            seen['target'] = chunks + 1
            out = model.generate(**inputs, past_key_values=cache, max_new_tokens=max_new_tokens,
                                 **decoding_kwargs, **extra)
            del cache
    finally:
        if handle is not None:
            handle.remove()
    # The tokens generate() prefilled itself: the tail after chunking, else the whole prompt.
    tail = GENERATE_TAIL_TOKENS if chunked else prompt_tokens
    return out, dict(prompt_tokens=prompt_tokens, chunks=chunks,
                     chunked_tokens=prompt_tokens - tail, tail_tokens=tail,
                     prefill_seconds=None if seen['at'] is None else round(seen['at'] - started, 6))


def load_attention(role, spec=None):
    """The attn_implementation a frozen role is loaded with: the producer's sealed setting
    (producer_attention); the Auditor896 classifier eager, read from its runtime contract,
    which must say eager (D-058 condition iii)."""
    if role == 'auditor':
        spec = spec or specification('auditor')
        value = spec['runtime']['attn_implementation']
        require(value == EAGER, 'The Auditor896 classifier runs eager, as its runtime contract says')
        return value
    require(role == 'producer', 'Unknown frozen role')
    return producer_attention()['attention_implementation']


def attention_of(model):
    """The attention setting a loaded model carries (its config's _attn_implementation), or
    None when it carries none (a stand-in model)."""
    value = getattr(getattr(model, 'config', None), '_attn_implementation', None)
    return value if isinstance(value, str) else None


def enabled_sdpa_backends(torch):
    """The sdpa backends torch currently allows, by SDPBackend name, joined with `+`."""
    switches = torch.backends.cuda
    return '+'.join(name for name, switch in sorted(SDPA_SWITCHES.items()) if getattr(switches, switch)())


@contextlib.contextmanager
def pinned_attention(model, decision=None):
    """One local generate call's attention (D-058 conditions ii and iii). A model whose
    attention is sdpa on a CUDA device runs inside
    torch.nn.attention.sdpa_kernel([SDPBackend.EFFICIENT_ATTENTION]): only the memory-efficient
    kernel, so a refused kernel raises (AttentionKernelRefused below) instead of falling back
    to the quadratic math kernel. An eager model, or one on the CPU (which has no
    memory-efficient kernel), runs unpinned and says so. Yields the record written into the
    call's reply record: the attention, the sdpa backends enabled inside the block, the
    decision that set it and whether the backend was pinned. torch is imported only to pin."""
    implementation = attention_of(model)
    device = str(getattr(model, 'device', '') or '')
    pinned = implementation == SDPA and device.startswith('cuda')
    record = dict(attention_implementation=implementation, sdpa_backend=None,
                  attention_decision=decision, pinned=pinned)
    if not pinned:
        yield record
        return
    torch = importlib.import_module('torch')
    attention = importlib.import_module('torch.nn.attention')
    with attention.sdpa_kernel([getattr(attention.SDPBackend, SDPA_BACKEND)]):
        record['sdpa_backend'] = enabled_sdpa_backends(torch)
        yield record


class GenerationFailure(RuntimeError):
    """A local generate call that failed for want of memory or of its pinned kernel (D-058
    condition ii): one recorded failure, named by `kind`, never retried (P13)."""
    kind = 'generation_failure'

    def __init__(self, cause):
        super().__init__('%s: %s' % (self.kind, cause))


class GenerationOutOfMemory(GenerationFailure):
    kind = 'out_of_memory'


class AttentionKernelRefused(GenerationFailure):
    kind = 'attention_kernel_refused'


def generation_failure_kind(exc):
    """'out_of_memory', 'attention_kernel_refused', or None for any other failure.
    torch.cuda.OutOfMemoryError is read by its class name, so no model library is imported."""
    if isinstance(exc, GenerationFailure):
        return exc.kind
    if any(cls.__name__ == 'OutOfMemoryError' for cls in type(exc).__mro__):
        return GenerationOutOfMemory.kind
    if isinstance(exc, RuntimeError):
        text = str(exc)
        if 'out of memory' in text.lower():
            return GenerationOutOfMemory.kind
        if 'No available kernel' in text or 'No viable backend for scaled_dot_product_attention' in text:
            return AttentionKernelRefused.kind
    return None


def named_generation_failure(exc):
    """The named failure to raise for `exc`, or None when it is an ordinary failure."""
    kind = generation_failure_kind(exc)
    if kind is None:
        return None
    if isinstance(exc, GenerationFailure):
        return exc
    return (GenerationOutOfMemory if kind == GenerationOutOfMemory.kind else AttentionKernelRefused)(
        type(exc).__name__)


def context_record(model, prompt_tokens, max_new_tokens):
    """Whether one local call fits its model's context (D-058 condition v): the prompt's
    tokens plus the call's output allowance against max_position_embeddings, the test B1
    applies to every item (section 5.3). Counts only. `over_context` is None when the model
    states no context (a stand-in model)."""
    limit = getattr(getattr(model, 'config', None), 'max_position_embeddings', None)
    limit = limit if type(limit) is int else None
    return dict(prompt_tokens=int(prompt_tokens), max_new_tokens=int(max_new_tokens), model_context=limit,
                over_context=None if limit is None else int(prompt_tokens) + int(max_new_tokens) > limit)


def verify_runtime():
    contract = specification('auditor')['runtime']
    require(sys.platform == 'linux' and platform.machine() == 'x86_64' and
            platform.python_version() == contract['python'], 'Pinned Linux/Python runtime required')
    for package, version in contract['packages'].items():
        require(importlib.metadata.version(package) == version, 'Runtime package mismatch: ' + package)
    require(os.environ.get('CUBLAS_WORKSPACE_CONFIG') == ':4096:8', 'Set CUBLAS_WORKSPACE_CONFIG before process startup')
    import torch
    require(torch.cuda.is_available() and torch.cuda.is_bf16_supported() and
            torch.version.cuda == contract['cuda_runtime'], 'Pinned CUDA/BF16 required')
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    return torch


def base_path(role, spec):
    override = os.environ.get('SHIMMER_' + role.upper() + '_BASE_PATH')
    if override:
        path = Path(override)
    else:
        from huggingface_hub import snapshot_download
        path = Path(snapshot_download(spec['model_id'], revision=spec['revision'], local_files_only=True))
    for name, digest in spec['base_hashes'].items():
        require(sha(path / name) == digest, 'Base asset mismatch: ' + role + ' ' + name)
    require(not (path / 'custom_generate/generate.py').exists(), 'Custom generation not admitted')
    return path


def load(role, device):
    spec, paths = verify(role)
    # D-058, D-060: the producer's attention is its sealed setting (eager unless a recorded
    # decision asks for sdpa); the classifier stays eager, as its runtime contract says. The
    # producer's prefill setting (D-061) is read here too, so an unadmitted one refuses before
    # any weight is read.
    attention = load_attention(role, spec)
    prefill = producer_prefill() if role == 'producer' else None
    torch = verify_runtime()
    require(device.startswith('cuda:'), 'Frozen inference requires CUDA')
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel, prepare_model_for_kbit_training
    path = base_path(role, spec)
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(str(path), local_files_only=True,
        trust_remote_code=False, device_map={'': int(device.split(':')[1])},
        torch_dtype=torch.bfloat16, attn_implementation=attention)
    expected = 'qwen2' if role == 'producer' else 'llama'
    require(model.config.model_type == expected and model.is_loaded_in_4bit, 'Frozen architecture mismatch')
    require(attention_of(model) == attention, 'Frozen attention mismatch: ' + role)
    quant = model.config.quantization_config
    quant = quant.to_dict() if hasattr(quant, 'to_dict') else quant
    require(quant['bnb_4bit_quant_type'] == 'nf4' and quant['bnb_4bit_compute_dtype'] == 'bfloat16', 'Frozen quantization mismatch')
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True,
                                          gradient_checkpointing_kwargs={'use_reentrant': True})
    model = PeftModel.from_pretrained(model, str(paths['adapter'].parent),
        adapter_name='classifier_fork' if role == 'auditor' else 'default', is_trainable=False)
    model.requires_grad_(False)
    model.eval()
    model.gradient_checkpointing_disable()
    model.config.use_cache = role == 'producer'
    model._shimmer_identity = identity(role, spec)
    if role == 'producer':
        model._shimmer_attention = producer_attention()
        model._shimmer_prefill = prefill
    if role == 'auditor':
        return tokenizer, Classifier(torch, model, paths, spec)
    return tokenizer, model


class Classifier:
    """Final prompt token, immutable saved FP32 statistics/head; sticky admission."""
    def __init__(self, torch, model, paths, spec):
        import numpy as np
        from safetensors.torch import load_file
        self.torch, self.model, self.failed = torch, model, False
        self._shimmer_identity = identity('auditor', spec)
        self.device = model.device
        self.head = torch.nn.Linear(3072, 4, device=self.device, dtype=torch.float32)
        self.head.load_state_dict(load_file(str(paths['head']), device=str(self.device)), strict=True)
        self.head.requires_grad_(False).eval()
        values = [np.load(paths[key], allow_pickle=False) for key in ('mean', 'std')]
        require(all(v.shape == (3072,) and v.dtype == np.float32 and np.isfinite(v).all() for v in values), 'Normalization admission')
        require(bool((values[1] >= np.float32(1e-6)).all()), 'Normalization std admission')
        self.mean, self.std = [torch.tensor(v, device=self.device) for v in values]
        # The frozen state audit is shared with the final evaluation implementation.
        self.audit = tools_module('auditor_classifier_lora_stable').FrozenAudit(torch, model)
        require(self.audit.initial_hash == spec['runtime']['base_state_sha256'], 'Frozen base state mismatch')

    def predict(self, ids, failure_dir=None):
        torch = self.torch
        require(not self.failed, 'No inference retry after numerical failure')
        require(isinstance(ids, list) and ids and all(type(x) is int and x >= 0 for x in ids), 'Token admission')
        hidden = None
        try:
            require(self.audit.unchanged(), 'Frozen state mutated')
            inputs = torch.tensor([ids], device=self.device, dtype=torch.long)
            with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
                raw = self.model.get_base_model().model(input_ids=inputs, attention_mask=torch.ones_like(inputs),
                        use_cache=False, return_dict=True).last_hidden_state
                require(tuple(raw.shape) == (1, len(ids), 3072), 'Hidden shape admission')
                hidden = raw[:, -1, :].float()
            with torch.inference_mode(), torch.autocast('cuda', enabled=False):
                require(tuple(hidden.shape) == (1, 3072) and bool(torch.isfinite(hidden).all()), 'Hidden finite admission')
                z = (hidden - self.mean) / self.std
                require(bool(torch.isfinite(z).all()), 'Normalized hidden admission')
                logits = self.head(z)
                require(tuple(logits.shape) == (1, 4) and bool(torch.isfinite(logits).all()), 'Logit admission')
            require(self.audit.unchanged(), 'Frozen state mutated')
            return ('MATCH', 'DIVERGENCE', 'OMISSION', 'ADDITION')[int(logits.argmax())]
        except BaseException:
            self.failed = True
            if failure_dir is not None:
                directory = Path(failure_dir)
                directory.mkdir(parents=True, exist_ok=True)
                if hidden is not None:
                    import numpy as np
                    with (directory / 'first_invalid_hidden.npy').open('xb') as stream:
                        np.save(stream, hidden.detach().cpu().numpy(), allow_pickle=False)
                (directory / 'admission_failure.json').write_text(json.dumps(dict(
                    failed=True, input_length=len(ids), hidden_available=hidden is not None,
                    identity=self._shimmer_identity)), encoding='utf8')
            raise


def tools_module(name):
    import importlib.util
    module_name = '_shimmer_frozen_' + name
    if module_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(module_name, ROOT/'tools'/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[module_name] = module
    return sys.modules[module_name]


def resident(role, run_context=None):
    """Use the lane's existing residency budget; no additional model replica."""
    import execution_topology
    import model_telemetry
    import gc
    context = getattr(execution_topology.WORK, 'context', None)
    worker = context.worker if context is not None else None
    key = 'final-' + role
    cache = worker.residents if worker else _RESIDENTS
    device = worker.lane.device if worker else 'cuda:0'
    def event(name, **fields):
        model_telemetry.emit(run_context, name, model=key, **fields)
        if context:
            context.event(name, model=key, **fields)
    with _LOAD_LOCK:
        if key in cache:
            event('model_resident', cold=False)
            return cache[key]
        event('model_load_start', cold=True)
        if worker:
            if len(cache) >= worker.lane.resident_limit:
                evicted = next(iter(cache))
                del cache[evicted]
                event('model_evicted', evicted_model=evicted)
        else:
            import agent_wrapper
            with agent_wrapper._QWEN_LOAD_LOCK:
                agent_wrapper._evict_generation_models()
            cache.clear()
        gc.collect()
        torch = sys.modules.get('torch')
        if torch is not None and torch.cuda.is_initialized():
            torch.cuda.empty_cache()
        value = load(role, device)
        cache[key] = value
        event('model_load_end', cold=True)
        return value


def release_reference_residency():
    """Called before the reference loader to avoid co-resident hidden replicas."""
    with _LOAD_LOCK:
        if _RESIDENTS:
            _RESIDENTS.clear()
            import gc
            gc.collect()
            torch = sys.modules.get('torch')
            if torch is not None and torch.cuda.is_initialized():
                torch.cuda.empty_cache()


def classifier_messages(value):
    # The exact training serialization; no training module (with environment
    # mutations or dataset imports) is imported into the ordinary runtime.
    import compact_contracts
    normalized, mapping = tools_module('auditor_linear_core').normalized_input(value)
    instruction = compact_contracts.AUDITOR + (
        '\nV2 transport clarification: delivery_complete=false means an interrupted extraction, requiring refusal. '
        'For a complete delivery, identifiable missing propositions are OMISSION, not transport incompleteness. '
        'Refuse when the owned original, referent, or comparison mapping is insufficient to determine a relation. '
        'A short extraction alone does not justify refusal. Structural readback/section headings do not introduce new speakers or facts.')
    return [dict(role='system', content=instruction), dict(role='user', content=json.dumps(
        normalized, sort_keys=True, separators=(',', ':'), ensure_ascii=False))], mapping



def admit_ordinary():
    if mode() == 'final':
        import auditor_pairs
        import decoding_policy
        if not auditor_pairs.contract_self_check():
            raise RuntimeError('Auditor pairing contract not admitted')
        verify('producer')
        verify('auditor')
        # D-058, D-061: an unadmitted attention or prefill setting refuses the run here,
        # before any load.
        producer_attention()
        producer_prefill()
        load_attention('auditor')
        # Every local generate site decodes under the frozen evaluation policy;
        # a drifted protocol or an unsound declaration refuses the run here,
        # before verify_runtime turns strict determinism on and before any load.
        decoding_policy.summary()
        verify_runtime()
