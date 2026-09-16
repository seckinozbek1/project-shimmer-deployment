"""Effect-testable local dry-run boundary; no network, weights or protected reads."""
import os
from pathlib import Path
import sys


def install(root, allowed_writes=()):
    root = Path(root).resolve()
    writes = [Path(x).resolve() for x in allowed_writes]
    forbidden = [root / 'benchmark/task_semantics/seed.json',
                 root / 'benchmark/task_semantics_v2/extension.json',
                 root / 'tuning/first_domain_agnostic_v1/protected_eval.py']
    def guard(event, args):
        if event in ('socket.connect', 'socket.connect_ex', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'):
            raise PermissionError('Offline dry-run forbids network/process execution')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            p = Path(os.fsdecode(args[0])).resolve()
            low = str(p).lower()
            if p in forbidden or p.name == 'PROTECTED_ACCESS_CONSUMED.json' or 'protected_eval' in p.name:
                raise PermissionError('Protected access denied')
            if p.suffix in ('.safetensors', '.bin', '.pt', '.pth', '.onnx') or 'pytorch_model' in p.name:
                raise PermissionError('Model-weight access denied in dry-run')
            if 'auditor' in (x.lower() for x in p.parts) and p.suffix not in ('.py',):
                raise PermissionError('Auditor artifacts denied in Producer dry-run')
            mode = args[1]
            flags = args[2] if len(args) > 2 else 0
            writing = (isinstance(mode, str) and any(x in mode for x in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            if writing and not any(p == q or p.is_relative_to(q) for q in writes):
                raise PermissionError('Historical and unrelated writes denied')
    sys.addaudithook(guard)
    return guard
