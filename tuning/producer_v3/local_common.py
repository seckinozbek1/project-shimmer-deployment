"""Producer V3 local design primitives. Install the guard before dependencies."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
os.environ.update(USE_TORCH='0', USE_TF='0', USE_FLAX='0', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')

def guard(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'):
        raise PermissionError('V3 local-only: network/subprocess forbidden')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        p = Path(os.fsdecode(args[0])).resolve()
        if p.suffix.lower() in ('.safetensors', '.bin', '.pt', '.pth', '.gguf'):
            raise PermissionError('V3 local-only: model weight access forbidden')
        if p.is_relative_to(ROOT/'benchmark') and p.suffix not in ('.py', '.pyc'):
            raise PermissionError('V3 local-only: benchmark data forbidden')
        if 'protected' in p.name.lower():
            raise PermissionError('Protected artifact reads forbidden; metadata checks only')

sys.addaudithook(guard)
sys.path.insert(0, str(ROOT/'tuning/second_domain_agnostic_v2'))
import runtime as v2
# Legacy imports prepend their own directories; restore this release's priority
# so similarly named dry_run/release modules cannot dispatch a historical flow.
sys.path.insert(0,str(HERE))
import json
import hashlib
from collections import Counter

def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def write(p, value): v2.write(p, value)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(value): return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
