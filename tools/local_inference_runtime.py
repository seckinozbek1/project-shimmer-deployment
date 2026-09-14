"""Use the existing Conda PyTorch package cache without mixed pip leftovers.

Explicit, process-local Windows repair. No package mutation, download, DLL
suppression, or change to normal Shimmer startup. Call before importing torch.
"""
import hashlib
import json
import os
from pathlib import Path
import sys


def configure():
    if 'torch' in sys.modules:
        raise RuntimeError('Select the runtime before importing torch')
    if os.environ.get('KMP_DUPLICATE_LIB_OK', '').lower() in ('true', '1', 'yes'):
        raise RuntimeError('Duplicate OpenMP suppression is forbidden')
    prefix = Path(sys.prefix)
    records = list((prefix / 'conda-meta').glob('pytorch-*.json'))
    records = [p for p in records if json.loads(p.read_text()).get('name') == 'pytorch']
    if len(records) != 1:
        raise RuntimeError('Exactly one installed Conda PyTorch record required')
    record = json.loads(records[0].read_text())
    package = prefix / 'pkgs' / records[0].stem
    manifest = package / 'info/paths.json'
    paths = json.loads(manifest.read_text())['paths']
    verified = 0
    # Verify source and native binaries against the cached package manifest.
    # Streaming avoids materializing large DLLs in the laptop's limited RAM.
    for entry in paths:
        relative = entry['_path']
        if not relative.startswith('Lib/site-packages/torch/'):
            continue
        expected = entry.get('sha256')
        if not expected:
            raise RuntimeError('Package manifest lacks a content hash')
        digest = hashlib.sha256()
        with (package / relative).open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise RuntimeError('Cached PyTorch package integrity mismatch: ' + relative)
        verified += 1
    if not verified:
        raise RuntimeError('Empty PyTorch package manifest')
    site = package / 'Lib/site-packages'
    sys.path.insert(0, str(site))
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        os.environ[name] = '2'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    return dict(interpreter=sys.executable, python=sys.version,
                torch_package=str(package), torch_version=record['version'],
                verified_files=verified, repair='verified_cached_package_process_overlay',
                global_environment_modified=False, unsafe_suppression=False)


def runtime_evidence():
    import psutil
    import torch
    paths = sorted({m.path for m in psutil.Process().memory_maps()
                    if 'libiomp5md.dll' in m.path.lower()})
    if len(paths) != 1:
        raise RuntimeError('Expected exactly one loaded Intel OpenMP runtime')
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    cpu = torch.tensor([[1., 2.], [3., 4.]])
    if not torch.equal(cpu @ cpu, torch.tensor([[7., 10.], [15., 22.]])):
        raise RuntimeError('CPU arithmetic check failed')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required: refuse CPU model fallback')
    if not torch.equal((cpu.cuda() @ cpu.cuda()).cpu(), cpu @ cpu):
        raise RuntimeError('GPU arithmetic check failed')
    return dict(torch_path=torch.__file__, torch_version=torch.__version__,
                cuda=torch.version.cuda, openmp_dlls=paths, arithmetic_pass=True)
