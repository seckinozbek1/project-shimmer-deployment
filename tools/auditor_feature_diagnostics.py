"""Fail-closed TRAIN extraction shared by the live final pass and bounded probe.

No cache substitution, tensor repair, training, tokenizer, or network operations.
"""
import hashlib
import importlib.metadata
import json
import os
import platform
import tempfile
from collections import Counter
from pathlib import Path

VERSION = 'auditor-train-hidden-v2'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def write_diagnostic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf8') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


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


def extract_train_vector(torch, np, model, row, index, device, diagnostic_path, record_success=False, admission=None):
    """Execute the original forward and pooling, persisting evidence before refusal.

    Index is zero based. A malformed raw shape is refused before indexing. No
    successful row is logged here or admitted until the live shape/finite guard.
    """
    if admission is not None:
        admission.check_input(index, row)
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
    if admission is not None:
        if failure is None:
            failure = admission.vector_reason(vector, index)
        if failure:
            admission.failed = True
            # Preserve the boundary before expensive summaries or device transfers.
            minimal = dict(event='train_feature_failure', reason=failure, index=index,
                example_id=row['example_id'], token_sha256=digest(row['input_ids']),
                input_ids_sha256=digest([row['input_ids']]),
                attention_mask_sha256=digest([[1]*len(row['input_ids'])]),
                expected_feature_sha256=admission.receipts[index]['feature_sha256'],
                actual_feature_sha256=hashlib.sha256(vector.tobytes()).hexdigest() if vector is not None else None,
                capture_complete=False)
            write_diagnostic(diagnostic_path, minimal)
            if vector is not None:
                with Path(diagnostic_path).with_suffix('.npy').open('wb') as stream:
                    np.save(stream, vector, allow_pickle=False)
                    stream.flush(); os.fsync(stream.fileno())
                minimal['vector_file_sha256'] = hashlib.sha256(Path(diagnostic_path).with_suffix('.npy').read_bytes()).hexdigest()
                write_diagnostic(diagnostic_path, minimal)
            if raw is not None:
                try:
                    with Path(diagnostic_path).with_suffix('.pt').open('wb') as stream:
                        torch.save(raw.detach().cpu(), stream)
                        stream.flush(); os.fsync(stream.fileno())
                    minimal['raw_file_sha256'] = hashlib.sha256(Path(diagnostic_path).with_suffix('.pt').read_bytes()).hexdigest()
                    write_diagnostic(diagnostic_path, minimal)
                except Exception as exc:
                    minimal['raw_capture_error'] = type(exc).__name__
                    write_diagnostic(diagnostic_path, minimal)
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
        if admission is not None and failure:
            receipt.update(admission=minimal, capture_complete='raw_capture_error' not in minimal)
        write_diagnostic(diagnostic_path, receipt)
    if failure:
        if failure.startswith('forward_or_extraction_exception:'):
            raise RuntimeError(failure) from original
        raise RuntimeError('finite TRAIN hidden: ' + failure)
    if admission is not None:
        admission.accepted += 1
    return vector


HISTORICAL_RECEIPTS_SHA256 = '75cd0e49a85e0fd9637141b836baf1be1c627cc6a6479127f2dcd8875441a11c'


class HistoricalAdmission:
    """Exact FP32 byte-hash admission for every fresh TRAIN observation.

    The reference contains only immutable comparison receipts, never features to
    return to the caller. No tolerance, substitution, resume or partial pass.
    """
    def __init__(self, np, rows, reference_path):
        self.np = np
        self.accepted = 0
        self.failed = False
        raw = Path(reference_path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != HISTORICAL_RECEIPTS_SHA256:
            raise RuntimeError('historical TRAIN receipt identity')
        self.receipts = [json.loads(line) for line in raw.splitlines()]
        if len(rows) != 1792 or len(self.receipts) != 1792:
            raise RuntimeError('complete 1792 TRAIN reference required')
        for index, (row, receipt) in enumerate(zip(rows, self.receipts)):
            if (receipt['index'] != index or not receipt['finite'] or
                    not self.same_input(row, receipt)):
                raise RuntimeError('historical TRAIN input binding')

    @staticmethod
    def same_input(row, receipt):
        return (row['split'] == 'train' and row['example_id'] == receipt['example_id'] and
                row['prompt_sha256'] == receipt['prompt_sha256'] and
                digest(row['input_ids']) == receipt['token_sha256'])

    def check_input(self, index, row):
        if (self.failed or index != self.accepted or not 0 <= index < 1792 or
                not self.same_input(row, self.receipts[index])):
            self.failed = True
            raise RuntimeError('TRAIN admission latched/order/input failure')

    def vector_reason(self, vector, index):
        if vector is None or vector.shape != (3072,):
            return 'historical_vector_shape'
        if vector.dtype != self.np.dtype('<f4'):
            return 'historical_vector_dtype'
        if not self.np.isfinite(vector).all():
            return 'historical_vector_nonfinite'
        if hashlib.sha256(vector.tobytes()).hexdigest() != self.receipts[index]['feature_sha256']:
            return 'historical_finite_drift'
        return None

    def require_complete(self, features):
        good = not self.failed and self.accepted == 1792 and features.shape == (1792, 3072)
        if good:
            good = all(self.vector_reason(features[i], i) is None for i in range(1792))
        if not good:
            self.failed = True
            raise RuntimeError('TRAIN admission incomplete/failed/persistence mismatch')
        return dict(rows=1792, comparison='exact FP32 byte SHA-256; no tolerance',
                    historical_receipts_sha256=HISTORICAL_RECEIPTS_SHA256,
                    fresh_live_vectors=True, reference_substitution=False)
