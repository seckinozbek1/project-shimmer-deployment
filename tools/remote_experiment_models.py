"""Pinned two-model cache acquisition, only after independent runtime gates."""
import argparse
import json
from pathlib import Path
import sys
import runtime_contract as runtime


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--root', type=Path, required=True)
    args = p.parse_args()
    if not args.execute:
        p.error('Explicit experiment execution required')
    selected = runtime.resolve([sys.executable])
    runtime.subprocess_check(selected, args.root)
    dependencies = runtime.subprocess_check(selected, args.root, dependencies=True)
    if not dependencies['dependencies_ready']:
        raise runtime.RuntimeContractError('Dependencies are not ready; model acquisition refused')
    from huggingface_hub import snapshot_download
    models = json.loads((args.root / 'config/local_models.json').read_text())
    revisions = json.loads((args.root / 'tools/cloud_run/models.json').read_text())
    for role in ('active_producer', 'active_auditor'):
        name = models[role]
        snapshot = Path(snapshot_download(name, revision=revisions[name], token=False,
            allow_patterns=['*.json', '*.safetensors', 'tokenizer*', '*.model', '*.txt']))
        ref = snapshot.parents[1] / 'refs/main'
        ref.parent.mkdir(exist_ok=True)
        ref.write_text(revisions[name])


if __name__ == '__main__':
    main()
