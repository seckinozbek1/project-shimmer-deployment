"""Frozen ordinary inference artifacts. Importing this module loads no model.

Explicit SHIMMER_MODEL_MODE=final selects the frozen pair; base preserves the
reference runtime. No training/evaluation datasets or cloud clients are imported.
"""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
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
    torch = verify_runtime()
    require(device.startswith('cuda:'), 'Frozen inference requires CUDA')
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel, prepare_model_for_kbit_training
    path = base_path(role, spec)
    tokenizer = AutoTokenizer.from_pretrained(str(path), local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(str(path), local_files_only=True,
        trust_remote_code=False, device_map={'': int(device.split(':')[1])},
        torch_dtype=torch.bfloat16, attn_implementation='eager')
    expected = 'qwen2' if role == 'producer' else 'llama'
    require(model.config.model_type == expected and model.is_loaded_in_4bit, 'Frozen architecture mismatch')
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
        # Every local generate site decodes under the frozen evaluation policy;
        # a drifted protocol or an unsound declaration refuses the run here,
        # before verify_runtime turns strict determinism on and before any load.
        decoding_policy.summary()
        verify_runtime()
