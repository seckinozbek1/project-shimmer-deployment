"""Local test boundary: no network, model weights, protected data or training."""
import os
from pathlib import Path
import sys

def install_local_guard(root, writable):
    root=Path(root).resolve();writable=Path(writable).resolve()
    def guard(event,args):
        if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo','os.system'):
            raise PermissionError('Local-only nullability validation')
        if event=='import' and args[0].split('.')[0] in ('torch','peft'):
            raise PermissionError('No Torch/PEFT model runtime import in local tests')
        if event=='exec' and Path(args[0].co_filename).name=='train.py':
            raise PermissionError('Training executor execution denied')
        if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
            p=Path(os.fsdecode(args[0])).resolve()
            if p.suffix in ('.safetensors','.bin','.pt','.pth','.onnx'):
                raise PermissionError('No model weight access')
            if p.name in ('seed.json','extension.json','protected_eval.py','PROTECTED_ACCESS_CONSUMED.json') or 'auditor' in {x.lower() for x in p.parts}:
                raise PermissionError('Protected/Auditor access denied')
            mode=args[1];flags=args[2] if len(args)>2 else 0
            writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            if writing and not p.is_relative_to(writable):
                raise PermissionError('Historical/unrelated write denied')
    sys.addaudithook(guard)
    return guard
