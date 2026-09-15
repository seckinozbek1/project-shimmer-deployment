"""Build a payload-free source-layer manifest, without cloud or model artifacts.

Compare --previous to enumerate changed files for a future source-only image
layer. Dependency and model layers have separate fingerprints and lifetimes.
No upload, image build, credential read, or operator-data packaging occurs here.
"""
import argparse
import hashlib
import json
from pathlib import Path


def manifest(root):
    root=Path(root).resolve()
    files={}
    for folder in ["scripts","tools","corpus_ingest"]:
        for p in sorted((root/folder).rglob("*")):
            if not p.is_file() or "__pycache__" in p.parts or p.suffix not in {".py",".js",".css",".html",".sh",".ps1"}:
                continue
            if not p.resolve().is_relative_to(root):raise ValueError("Source symlink escapes repository")
            data=p.read_bytes();files[p.relative_to(root).as_posix()]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
    # Immutable runtime requirements travel with the executable source layer.
    for name in ("tools/cloud_run/runtime.json", "tools/cloud_run/runtime.lock", "tools/cloud_run/models.json"):
        path=root/name
        if path.is_file():
            data=path.read_bytes();files[name]=dict(sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
    dependency=root/"requirements.txt"
    return dict(schema_version=1,source_files=files,source_bytes=sum(v["bytes"] for v in files.values()),
                source_layer_sha256=hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),
                dependency_sha256=hashlib.sha256(dependency.read_bytes()).hexdigest(),
                excluded=["weights","wheels","credentials","input","output","durable","mutable runtime config"],
                complete_deployment_bundle=False,
                model_cache_policy="preposition pinned checkpoints; verify separately; never include per-run source layer")


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,default=Path(__file__).resolve().parent.parent)
    p.add_argument("--previous",type=Path);p.add_argument("--output",type=Path,required=True);a=p.parse_args()
    from runtime_contract import resolve, subprocess_check, remote_resolver_command
    selection=resolve(root=a.root)
    preflight=subprocess_check(selection,a.root)
    current=manifest(a.root)
    current["runtime_preflight"]=preflight
    current["remote_interpreter_bootstrap"]=remote_resolver_command(profile="experiment")
    current["remote_entrypoint"]="tools/prepare_remote_experiment.py"
    if a.previous:
        previous=json.loads(a.previous.read_text())["source_files"]
        current["changed_files"]=[k for k,v in current["source_files"].items() if previous.get(k)!=v]
        current["removed_files"]=[k for k in previous if k not in current["source_files"]]
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(current,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:current[k] for k in ["source_bytes","source_layer_sha256"]}))


if __name__=="__main__":main()
