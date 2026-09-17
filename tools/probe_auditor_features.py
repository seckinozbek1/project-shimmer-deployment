"""Offline, bounded row32 reproduction. No optimizer or cloud entry point.

Use --neighbors only after the single-row probe. Local runtime differences are
recorded, never presented as equivalent to the pinned Linux/A10 execution.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--neighbors', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    from auditor_feature_diagnostics import write_diagnostic, path_identity
    receipt = dict(completed=False, model_loaded=False, forward_rows=[], optimizer_updates=0,
                   extraction_path=path_identity(), device=args.device,
                   python=platform.python_version(), platform=platform.platform())
    def save(): write_diagnostic(args.output / 'probe.json', receipt)
    save()
    # Deny network and forbidden datasets even if a dependency tries to open them.
    from auditor_final_core import Boundary
    boundary = Boundary(ROOT)
    def local_boundary(event, values):
        if event in ('socket.connect', 'socket.getaddrinfo'):
            raise PermissionError('offline feature probe')
        if event == 'open' and isinstance(values[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(values[0])).resolve()
            # The package integrity scan opens torch/utils/benchmark source.
            # Dataset restrictions apply to the project, not dependency names.
            if path.is_relative_to(ROOT):
                boundary.check(path)
    sys.addaudithook(local_boundary)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                      USE_TORCH='1', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    try:
        if sys.platform == 'win32':
            from local_inference_runtime import configure
            receipt['runtime_overlay'] = configure()
            sys.path.insert(0, str(ROOT / '.tmp/auditor_feature_deps'))
        import torch
        import numpy as np
        from transformers import AutoModelForCausalLM
        from peft import PeftModel, prepare_model_for_kbit_training
        import auditor_classifier_lora_core as c
        import auditor_classifier_lora_current_core as current
        import auditor_classifier_lora_fork as fork
        import auditor_classifier_lora_stable as stable
        from auditor_feature_diagnostics import extract_train_vector, model_state, tensor_summary
        contract = c.read(ROOT / 'tuning/auditor_final/runtime_contract.json')
        receipt['packages'] = {n: importlib.metadata.version(n) for n in contract['packages']}
        receipt['package_differences'] = {n: dict(expected=v, actual=receipt['packages'][n])
            for n, v in contract['packages'].items() if receipt['packages'][n] != v}
        receipt['cuda_runtime'] = torch.version.cuda
        receipt['gpu'] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        torch.set_num_threads(2)
        torch.use_deterministic_algorithms(True)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.manual_seed(7); torch.cuda.manual_seed_all(7); np.random.seed(7)
        path = Path.home() / '.cache/huggingface/hub' / ('models--' + contract['model_id'].replace('/', '--')) / 'snapshots' / contract['revision']
        expected = dict(contract['asset_hashes'], **{'model.safetensors': contract['base_weight_sha256']})
        receipt['base_assets'] = {name: c.sha(path / name) for name in expected}
        if receipt['base_assets'] != expected: raise RuntimeError('pinned base assets differ')
        adapter = ROOT / 'tuning/auditor_final/canonical_adapter'
        if c.sha(adapter / 'adapter_model.safetensors') != fork.SOURCE_SHA or c.sha(adapter / 'adapter_config.json') != fork.CONFIG_SHA:
            raise RuntimeError('canonical adapter identity')
        receipt['adapter_sha256'] = fork.SOURCE_SHA
        save()
        base = AutoModelForCausalLM.from_pretrained(str(path), local_files_only=True, trust_remote_code=False,
            device_map={'': 0 if args.device == 'cuda' else 'cpu'}, torch_dtype=torch.bfloat16, attn_implementation='eager')
        if base.config.architectures != ['LlamaForCausalLM'] or base.config.hidden_size != 3072 or not base.is_loaded_in_4bit:
            raise RuntimeError('base architecture/quantization')
        base.config.use_cache = False
        base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True,
                                               gradient_checkpointing_kwargs={'use_reentrant': True})
        model = PeftModel.from_pretrained(base, str(adapter), adapter_name=fork.REFERENCE, is_trainable=False)
        head = torch.nn.Linear(3072, 4, device=args.device, dtype=torch.float32)
        fork.freeze_slots(model, head)
        inventory = fork.inventory(adapter / 'adapter_model.safetensors')
        current.verify_adapter(torch, model, fork.REFERENCE, inventory)
        receipt['adapter_tensor_hashes_verified'] = len(inventory)
        audit = stable.FrozenAudit(torch, model)
        receipt['base_state_sha256'] = audit.initial_hash
        receipt['base_state_matches_cloud'] = audit.initial_hash == contract['base_state_sha256']
        receipt['model_state'] = model_state(torch, model)
        receipt['model_loaded'] = True
        save()
        rows = c.read(ROOT / 'tuning/auditor_final/records_train_only.json')
        if rows[31]['example_id'] != 'shimmer2-auditor-document-038': raise RuntimeError('row32 identity')
        prior_path = ROOT / 'docs/fix/auditor_classifier_lora_current_runtime_run/downloaded/evidence/current_train_features.npy'
        if c.sha(prior_path) != '06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287':
            raise RuntimeError('prior cache identity')
        prior = np.load(prior_path, mmap_mode='r', allow_pickle=False)
        prior_events = [json.loads(s) for s in prior_path.with_suffix('.jsonl').read_bytes().splitlines()]
        for index in ([29, 30, 31, 32] if args.neighbors else [31]):
            row = rows[index]
            if prior_events[index]['example_id'] != row['example_id'] or prior_events[index]['token_sha256'] != fork.token_hash(row['input_ids']):
                raise RuntimeError('prior token binding')
            value = extract_train_vector(torch, np, model, row, index, args.device, args.output / 'failure.json')
            repeated = extract_train_vector(torch, np, model, row, index, args.device, args.output / 'repeat_failure.json')
            item = dict(row_one_based=index + 1, example_id=row['example_id'], tokens=len(row['input_ids']),
                token_sha256=fork.token_hash(row['input_ids']), shape=list(value.shape), finite=bool(np.isfinite(value).all()),
                feature_sha256=hashlib.sha256(value.tobytes()).hexdigest(),
                repeat_bitwise_equal=bool(np.array_equal(value, repeated)),
                repeat_max_abs_difference=float(np.max(np.abs(value - repeated))),
                prior_bitwise_equal=bool(np.array_equal(value, prior[index])),
                prior_max_abs_difference=float(np.max(np.abs(value - prior[index]))))
            np.save(args.output / f'row-{index + 1}.npy', value, allow_pickle=False)
            receipt['forward_rows'].append(item); save()
        receipt['base_unchanged'] = audit.unchanged(full=True)
        receipt['completed'] = True
    except Exception as exc:
        # Type only: dependency errors can include paths or external config text.
        receipt['error_type'] = type(exc).__name__
        receipt['error_message'] = str(exc) if isinstance(exc, (RuntimeError, ImportError, ModuleNotFoundError)) else 'See local stderr'
        raise
    finally:
        receipt['data_access'] = boundary.receipt
        save()


if __name__ == '__main__':
    main()
