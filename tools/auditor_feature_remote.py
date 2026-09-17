"""One offline A10 feature diagnostic. No training/evaluation action exists."""
import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import auditor_classifier_lora_core as c
import auditor_feature_diagnostics as d

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'diagnostic_payload'
OUT = ROOT / 'evidence'
VERDICTS = ('REMOTE_BLOCKER_REPRODUCED_AND_ISOLATED',
            'REMOTE_BLOCKER_REPRODUCED_BUT_NOT_FULLY_ISOLATED',
            'REMOTE_BLOCKER_NOT_REPRODUCED', 'REMOTE_DIAGNOSTIC_INCOMPLETE')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write(name, value):
    d.write_diagnostic(OUT / name, value)


def scope():
    manifest = c.read(ROOT / 'execution_manifest.json')
    for name, digest in manifest['files'].items():
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT) and c.sha(path) == digest, 'payload binding: ' + name)
    rows = c.read(DATA / 'rows.json')
    require(len(rows) == 33 and all(r['split'] == 'train' for r in rows), 'bounded TRAIN only')
    require(rows[31]['example_id'] == 'shimmer2-auditor-document-038', 'row32 binding')
    require(manifest['maximum_prefix_row'] == 32 and manifest['optimizer_updates'] == 0, 'diagnostic scope')
    return rows, c.read(DATA / 'runtime_contract.json'), manifest


def permit():
    p = c.read(ROOT / 'diagnostic_authorization.json')
    require(p['action'] == 'auditor-feature-diagnostic-only' and p['operator_authorized'] is True, 'diagnostic authorization')
    require(p['instances'] == 1 and p['region'] == 'us-east-1' and p['hourly_rate'] == 1.29, 'single A10 rate/region')
    require(p['soft_usd'] == 1 and p['hard_usd'] == 2 and p['optimizer_updates'] == 0, 'diagnostic budget/scope')
    require(p['execution_manifest_sha256'] == c.sha(ROOT / 'execution_manifest.json'), 'authorization identity')
    return p


def preflight():
    _, contract, manifest = scope(); p = permit()
    require(p['source_commit'] == manifest['source_commit'], 'source identity')
    require(sys.platform == 'linux' and platform.machine() == 'x86_64' and platform.python_version() == contract['python'], 'pinned platform')
    for name, version in contract['packages'].items():
        require(importlib.metadata.version(name) == version, 'package: ' + name)
    import torch
    require(torch.cuda.device_count() == 1 and torch.cuda.get_device_name() == 'NVIDIA A10', 'one A10')
    require(torch.cuda.get_device_properties(0).total_memory >= 22 * 2**30, '24GB class')
    require(torch.version.cuda == contract['cuda_runtime'] and torch.cuda.is_bf16_supported(), 'CUDA/BF16')
    write('preflight.json', dict(passed=True, packages=contract['packages'], python=platform.python_version(), gpu=torch.cuda.get_device_name()))


def acquire():
    preflight()
    from huggingface_hub import snapshot_download
    contract = c.read(DATA / 'runtime_contract.json')
    hashes = dict(contract['asset_hashes'], **{'model.safetensors': contract['base_weight_sha256']})
    path = Path(snapshot_download(contract['model_id'], revision=contract['revision'], allow_patterns=list(hashes), local_dir=ROOT / 'base_model'))
    for name, digest in hashes.items():
        require(c.sha(path / name) == digest, 'base asset: ' + name)
    write('acquisition.json', dict(model_id=contract['model_id'], revision=contract['revision'], files=hashes))


def stages(observe, reset, isolate):
    """All forward counts/order are bounded here; first failure prevents expansion."""
    for stage, indices in [('A', [31, 31]), ('B', [29, 30, 31, 32]), ('C', list(range(32)))]:
        if stage == 'C':
            # A clean initialization tests the original first32-forward ordering.
            reset()
        for sequence, index in enumerate(indices):
            if not observe(stage, sequence, index):
                return isolate(stage, index)
    return VERDICTS[2]


def execute():
    preflight(); rows, contract, manifest = scope(); p = permit()
    OUT.mkdir(exist_ok=True)
    with (OUT / 'DIAGNOSTIC_ATTEMPTED').open('x') as stream:
        stream.write('One diagnostic process; no resume or training.\n')
    result = dict(verdict=VERDICTS[3], source_commit=manifest['source_commit'], forwards=[], optimizer_updates=0,
                  dev_rows=0, challenge_rows=0, protected_rows=0, producer_rows=0, stage_c_reason='Original failure followed31 forwards; order dependence remains unresolved.')
    def budget():
        remaining = p['workload_deadline_epoch'] - time.time()
        write('progress.json', dict(epoch=time.time(), forwards=len(result['forwards']), remaining_seconds=remaining,
             estimated_cost=(time.time() - p['launch_epoch']) * 1.29 / 3600))
        require(remaining > 60, 'diagnostic workload cutoff; preserve partial evidence')
    os.environ.update(USE_TORCH='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', CUBLAS_WORKSPACE_CONFIG=':4096:8')
    import torch
    import numpy as np
    from transformers import AutoModelForCausalLM
    from peft import PeftModel, prepare_model_for_kbit_training
    import auditor_classifier_lora_fork as fork
    import auditor_classifier_lora_current_core as current
    import auditor_classifier_lora_stable as stable
    from auditor_final_core import Boundary
    boundary = Boundary(ROOT); boundary.install()
    torch.use_deterministic_algorithms(True)
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    def no_training(*args, **kwargs):
        raise RuntimeError('diagnostic forbids backward/optimizer')
    torch.Tensor.backward = no_training
    torch.autograd.backward = no_training
    for name in ['Adam', 'AdamW', 'SGD']:
        setattr(torch.optim, name, no_training)
    hardware = dict(runtime=d.runtime_state(torch),
        nvidia_smi=subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version,uuid,pci.bus_id,memory.total', '--format=csv,noheader'],capture_output=True,text=True,check=True).stdout.strip(),
        driver=Path('/proc/driver/nvidia/version').read_text(), torch_build=torch.__config__.show(),
        environment={name:os.environ.get(name) for name in ['PYTHONHASHSEED','CUBLAS_WORKSPACE_CONFIG','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','TOKENIZERS_PARALLELISM']})
    write('hardware.json', hardware)
    library_cache = {}
    def libraries():
        paths = {line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if '/' in line}
        selected = sorted(path for path in paths if any(x in path.lower() for x in ['libcuda','libcublas','libcudnn','libcusparse','libnv','libtorch','libbitsandbytes']) and Path(path).is_file())
        for name in selected:
            if name not in library_cache:
                library_cache[name] = c.sha(Path(name))
        identity = dict(files={name:library_cache[name] for name in selected}, hardware_sha256=c.sha(OUT / 'hardware.json'))
        digest = d.digest(identity); write('libraries-' + digest + '.json', identity)
        return digest
    holder = {}
    def reset():
        budget()
        holder.clear(); gc.collect(); torch.cuda.empty_cache()
        torch.manual_seed(7); torch.cuda.manual_seed_all(7); np.random.seed(7)
        path = ROOT / 'base_model'
        for name, digest in dict(contract['asset_hashes'], **{'model.safetensors':contract['base_weight_sha256']}).items():
            require(c.sha(path / name) == digest, 'base hash before inference')
        reference = DATA / 'canonical_adapter'
        require(c.sha(reference / 'adapter_model.safetensors') == fork.SOURCE_SHA and c.sha(reference / 'adapter_config.json') == fork.CONFIG_SHA, 'canonical adapter')
        base = AutoModelForCausalLM.from_pretrained(str(path), local_files_only=True, trust_remote_code=False,
            device_map={'':0}, torch_dtype=torch.bfloat16, attn_implementation='eager')
        require(base.config.architectures == ['LlamaForCausalLM'] and base.config.hidden_size == 3072 and base.is_loaded_in_4bit, 'base architecture')
        quant = base.config.quantization_config
        if hasattr(quant, 'to_dict'): quant = quant.to_dict()
        require(quant['bnb_4bit_quant_type'] == 'nf4', 'NF4')
        base.config.use_cache = False
        base = prepare_model_for_kbit_training(base, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={'use_reentrant':True})
        model = PeftModel.from_pretrained(base, str(reference), adapter_name=fork.REFERENCE, is_trainable=False)
        # Reproduce the failed loader's RNG consumption; this unused head is never fitted or forwarded.
        head = torch.nn.Linear(3072, 4, device='cuda', dtype=torch.float32); fork.freeze_slots(model, head)
        inventory = fork.inventory(reference / 'adapter_model.safetensors')
        current.verify_adapter(torch, model, fork.REFERENCE, inventory)
        audit = stable.FrozenAudit(torch, model)
        require(audit.initial_hash == contract['base_state_sha256'], 'prepared base state')
        holder.update(model=model, audit=audit)
        write('initialization-' + str(len(result['forwards'])) + '.json', dict(base_state_sha256=audit.initial_hash,
              adapter_sha256=fork.SOURCE_SHA, adapter_tensor_hashes=inventory, state=d.model_state(torch, model)))
    prior = np.load(DATA / 'historical33.npy', allow_pickle=False)
    local = np.load(DATA / 'local30_33.npy', allow_pickle=False)
    require(prior.shape == (33,3072) and local.shape == (4,3072) and np.isfinite(prior).all() and np.isfinite(local).all(), 'comparison arrays')
    observed = {}
    def observe(stage, sequence, index):
        budget(); name=f'{stage}-{sequence:02d}-row{index+1}'
        record=dict(stage=stage, sequence=sequence, index=index, row_one_based=index+1, example_id=rows[index]['example_id'])
        path = OUT / (name + '.json')
        try:
            value = d.extract_train_vector(torch, np, holder['model'], rows[index], index, 'cuda', path, record_success=True)
            record.update(valid=True, feature_sha256=hashlib.sha256(value.tobytes()).hexdigest(), shape=list(value.shape),
                          historical_max_abs=float(np.max(np.abs(value-prior[index]))), historical_bitwise=bool(np.array_equal(value,prior[index])))
            if 29 <= index <= 32:
                record.update(local_max_abs=float(np.max(np.abs(value-local[index-29]))), local_bitwise=bool(np.array_equal(value,local[index-29])))
            if index in observed:
                record.update(previous_cloud_max_abs=float(np.max(np.abs(value-observed[index]))), previous_cloud_bitwise=bool(np.array_equal(value,observed[index])))
            observed[index] = value.copy(); np.save(OUT / (name+'.npy'), value, allow_pickle=False)
        except RuntimeError:
            if not path.exists(): raise
            receipt=c.read(path)
            require(receipt['event']=='train_feature_failure', 'unexpected diagnostic exception')
            record.update(valid=False, reason=receipt['reason'])
        receipt=c.read(path); receipt.update(stage=stage, sequence=sequence, library_identity=libraries(),
              numpy_rng_sha256=hashlib.sha256(np.random.get_state()[1].tobytes()).hexdigest(), source_commit=manifest['source_commit'])
        d.write_diagnostic(path,receipt)
        record['receipt_sha256']=c.sha(path); result['forwards'].append(record); write('result.json',result)
        return record['valid']
    def isolate(stage,index):
        # One replay with module entry/exit summaries, stopping at first nonfinite output.
        # A clean input plus invalid output narrows to that module, not necessarily a causal mechanism.
        budget(); events=[]; handles=[]
        class FirstInvalid(RuntimeError): pass
        def tensors(value):
            if torch.is_tensor(value): return [value]
            if isinstance(value, (list,tuple)): return [t for v in value for t in tensors(v)]
            if isinstance(value,dict): return [t for v in value.values() for t in tensors(v)]
            return []
        def record(name, edge, values):
            budget()
            floating=[t for t in tensors(values) if t.is_floating_point()]
            summaries=[d.tensor_summary(torch,t) for t in floating]
            event=dict(name=name,edge=edge,tensors=summaries)
            events.append(event)
            with (OUT/'layer_boundaries.jsonl').open('a') as stream:
                stream.write(json.dumps(event,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
            if any(x['finite_count']!=x['total_count'] for x in summaries):
                result['first_invalid_boundary']=event
                raise FirstInvalid(name)
        for name,module in holder['model'].get_base_model().model.named_modules():
            # Covers decoder blocks, attention/MLP, norms, projections, embeddings and LoRA components.
            if name:
                # Attention masks legitimately contain -Inf; inspect only the representation input.
                handles.append(module.register_forward_pre_hook(lambda m,a,k,n=name:record(n,'input',a[:1] if a else k.get('hidden_states',())),with_kwargs=True))
                handles.append(module.register_forward_hook(lambda m,a,o,n=name:record(n,'output',o)))
        try:
            ids=torch.tensor([rows[index]['input_ids']],device='cuda',dtype=torch.long)
            with torch.inference_mode(),torch.autocast('cuda',dtype=torch.bfloat16):
                raw=holder['model'].get_base_model().model(input_ids=ids,attention_mask=torch.ones_like(ids),use_cache=False,return_dict=True).last_hidden_state
            write('layer_replay_final.json',dict(raw_hidden=d.tensor_summary(torch,raw),pooled=d.tensor_summary(torch,raw[0,-1])))
            result['isolation_replay']='passed_or_shape_only; original failing receipt retained'
        except FirstInvalid:
            result['isolation_replay']='stopped_at_first_invalid_module_boundary'
        finally:
            for handle in handles:handle.remove()
        result['isolation_row']=index+1
        # Module boundary is evidence, not proof of which internal operator caused the original failure.
        return VERDICTS[1]
    try:
        reset(); result['verdict']=stages(observe,reset,isolate)
        result['base_unchanged']=holder['audit'].unchanged(full=True)
        require(result['base_unchanged'], 'frozen base changed')
        result['complete']=True
    except Exception as exc:
        result.update(verdict=VERDICTS[3],complete=False,error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        result['data_access']=boundary.receipt;result['finished_epoch']=time.time();write('result.json',result)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['scope','preflight','acquire','execute'])
    globals()[parser.parse_args().action]()
