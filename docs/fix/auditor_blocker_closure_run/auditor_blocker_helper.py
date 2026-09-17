"""Fail-closed TRAIN extraction shared by the live final pass and bounded probe.

No cache substitution, tensor repair, training, tokenizer, or network operations.
"""
import hashlib
import importlib.metadata
import json
import os
import platform
from collections import Counter
from pathlib import Path

VERSION = 'auditor-train-hidden-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write_diagnostic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def path_identity():
    root = Path(__file__).resolve().parent
    names = ['auditor_feature_diagnostics.py', 'auditor_final_remote.py',
             'auditor_classifier_lora_fork.py', 'auditor_classifier_lora_current_core.py']
    files = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}
    return dict(version=VERSION, files=files, sha256=digest(files))


def tensor_summary(torch, value, limit=16):
    if value is None:
        return None
    flat = value.detach().reshape(-1).to(device='cpu', dtype=torch.float64)
    finite = torch.isfinite(flat)
    result = dict(shape=list(value.shape), dtype=str(value.dtype), device=str(value.device),
                  total_count=flat.numel(), finite_count=int(finite.sum()), index_format='flat_row_major')
    for name, mask in [('nan', torch.isnan(flat)), ('positive_inf', torch.isposinf(flat)),
                       ('negative_inf', torch.isneginf(flat))]:
        indices = mask.nonzero().flatten()
        result[name] = dict(count=indices.numel(), indices=indices[:limit].tolist(),
                            sample_limit=limit, truncated=indices.numel() > limit)
    values = flat[finite]
    result['finite_statistics'] = (dict(min=float(values.min()), max=float(values.max()),
        mean=float(values.mean()), std=float(values.std(unbiased=False)),
        norm=float(torch.linalg.vector_norm(values))) if values.numel() else None)
    return result


def autocast_state(torch, device):
    return dict(device_type=device, enabled=torch.is_autocast_enabled(device),
                dtype=str(torch.get_autocast_dtype(device)), grad_enabled=torch.is_grad_enabled(),
                inference_mode=torch.is_inference_mode_enabled())


def runtime_state(torch):
    packages = {}
    for name in ['torch', 'numpy', 'transformers', 'peft', 'bitsandbytes', 'accelerate',
                 'safetensors', 'tokenizers', 'huggingface-hub']:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return dict(python=platform.python_version(), platform=platform.platform(), packages=packages,
        torch_version=torch.__version__, cuda_runtime=torch.version.cuda,
        cudnn_version=torch.backends.cudnn.version(),
        devices=[dict(index=i, name=torch.cuda.get_device_name(i), capability=list(torch.cuda.get_device_capability(i)))
                 for i in range(torch.cuda.device_count())] if torch.cuda.is_initialized() else [])


def model_state(torch, model):
    groups = Counter((str(p.dtype), str(p.device), bool(p.requires_grad))
                     for p in model.parameters())
    dropout = [dict(name=name, p=float(module.p), training=bool(module.training))
               for name, module in model.named_modules() if isinstance(module, torch.nn.Dropout)]
    adapters = [dict(name=name, active_adapters=list(module.active_adapters),
                     disabled=bool(module.disable_adapters), merged=bool(module.merged))
                for name, module in model.named_modules() if hasattr(module, 'lora_A')]
    return dict(training=bool(model.training), training_module_count=sum(m.training for m in model.modules()),
        active_adapters=list(model.active_adapters), adapter_layers=adapters,
        dropout=dropout, dropout_sha256=digest(dropout),
        adapter_config={name: dict(r=config.r, lora_alpha=config.lora_alpha,
            lora_dropout=config.lora_dropout, inference_mode=config.inference_mode)
            for name, config in model.peft_config.items()},
        quantized_compute=[dict(name=name, compute_dtype=str(module.compute_dtype),
                                compute_type_is_set=getattr(module, 'compute_type_is_set', None))
                           for name, module in model.named_modules() if hasattr(module, 'compute_dtype')],
        parameter_groups=[dict(dtype=k[0], device=k[1], requires_grad=k[2], tensors=v)
                          for k, v in sorted(groups.items())],
        attention_implementation=getattr(model.config, '_attn_implementation', None),
        deterministic_algorithms=torch.are_deterministic_algorithms_enabled(),
        initial_seed=torch.initial_seed(), cpu_rng_sha256=hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest(),
        cuda_rng_sha256=[hashlib.sha256(s.cpu().numpy().tobytes()).hexdigest()
                        for s in torch.cuda.get_rng_state_all()] if torch.cuda.is_initialized() else [],
        cublas_workspace_config=os.environ.get('CUBLAS_WORKSPACE_CONFIG'),
        matmul_allow_tf32=torch.backends.cuda.matmul.allow_tf32,
        cudnn_allow_tf32=torch.backends.cudnn.allow_tf32)


def extract_train_vector(torch, np, model, row, index, device, diagnostic_path, record_success=False, boundary_callback=None):
    """Execute the original forward and pooling, persisting evidence before refusal.

    Index is zero based. A malformed raw shape is refused before indexing. No
    successful row is logged here or admitted until the live shape/finite guard.
    """
    if row['split'] != 'train':
        raise RuntimeError('TRAIN-only feature diagnostic')
    raw = hidden = vector = None
    context = None
    ids = torch.tensor([row['input_ids']], device=device, dtype=torch.long)
    mask = torch.ones_like(ids)
    before = model_state(torch, model) if record_success else None
    failure = None
    try:
        with torch.inference_mode():
            with torch.autocast(ids.device.type, dtype=torch.bfloat16):
                context = autocast_state(torch, ids.device.type)
                raw = model.get_base_model().model(input_ids=ids, attention_mask=mask,
                    use_cache=False, return_dict=True).last_hidden_state
            if tuple(raw.shape) != (1, ids.shape[1], 3072):
                failure = 'raw_hidden_shape'
            else:
                hidden = raw[0, -1]
                vector = hidden.float().cpu().numpy().copy()
                if vector.shape != (3072,) or not np.isfinite(vector).all():
                    failure = 'finite TRAIN hidden'
    except Exception as exc:
        failure = 'forward_or_extraction_exception:' + type(exc).__name__
        original = exc
    if boundary_callback is not None:
        boundary_callback(raw, hidden, vector, ids, mask, failure)
    if failure or record_success:
        receipt = dict(event='train_feature_failure' if failure else 'train_feature_valid', reason=failure,
            index=index, row_one_based=index + 1, example_id=row['example_id'],
            prompt_sha256=row.get('prompt_sha256'), token_sha256=digest(row['input_ids']),
            input_ids_sha256=digest(ids.cpu().tolist()), attention_mask_sha256=digest(mask.cpu().tolist()),
            input_shape=list(ids.shape), attention_mask_shape=list(mask.shape),
            raw_hidden=tensor_summary(torch, raw), extracted_hidden=tensor_summary(torch, hidden),
            vector=tensor_summary(torch, torch.from_numpy(vector)) if vector is not None else None,
            pooling='last_hidden_state[0,-1]; float32 CPU numpy copy',
            model=model_state(torch, model), model_before=before, runtime=runtime_state(torch), forward_autocast=context,
            outside_autocast=autocast_state(torch, ids.device.type), extraction_path=path_identity())
        write_diagnostic(diagnostic_path, receipt)
    if failure:
        if failure.startswith('forward_or_extraction_exception:'):
            raise RuntimeError(failure) from original
        raise RuntimeError('finite TRAIN hidden: ' + failure)
    return vector
