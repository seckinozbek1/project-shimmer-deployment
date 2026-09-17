"""Pinned runtime preflight and public base acquisition for one final Auditor workflow."""
import argparse
import importlib.metadata
import json
import platform
import sys
import time
from pathlib import Path
import auditor_final_core as h
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'tuning/auditor_final'
OUT=ROOT/'evidence'


def read(p):return json.loads(p.read_bytes())
def write(name,value):
    OUT.mkdir(exist_ok=True);(OUT/name).write_text(json.dumps(value,indent=2)+'\n')


def preflight():
    from auditor_final_remote import scope,authorize
    authorize()
    scope();contract=read(D/'runtime_contract.json')
    h.require(platform.python_version()==contract['python'] and sys.platform=='linux' and platform.machine()=='x86_64','runtime platform')
    pins=contract['packages']
    for name,version in pins.items():h.require(importlib.metadata.version(name)==version,'pinned package '+name)
    import torch
    h.require(torch.cuda.device_count()==1 and 'A10' in torch.cuda.get_device_name() and 'A100' not in torch.cuda.get_device_name(),'one A10')
    h.require(torch.version.cuda==contract['cuda_runtime'] and torch.cuda.is_bf16_supported(),'CUDA/BF16')
    write('operational_preflight.json',dict(passed=True,python=platform.python_version(),packages=pins,gpu=torch.cuda.get_device_name(),gpu_count=1,model_loaded=False))


def acquire():
    preflight();contract=read(D/'runtime_contract.json')
    from huggingface_hub import snapshot_download
    expected=dict(contract['asset_hashes'],**{'model.safetensors':contract['base_weight_sha256']})
    begin=time.time();path=Path(snapshot_download(contract['model_id'],revision=contract['revision'],allow_patterns=list(expected),local_dir=ROOT/'base_model'))
    for name,digest in expected.items():h.require(h.c.sha(path/name)==digest,'pinned acquisition')
    write('acquisition.json',dict(model_id=contract['model_id'],revision=contract['revision'],files=expected,seconds=time.time()-begin))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','acquire']);globals()[p.parse_args().action]()
