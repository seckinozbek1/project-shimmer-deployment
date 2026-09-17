"""Verify the sealed asset archive and resolve its config-only offline cache."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from unittest.mock import patch

from ordinary_final_run import admit_cache_ref, read, require, sha, write


def verify(bundle, wheelhouse):
    bundle=Path(bundle);manifest=read(bundle/'execution_manifest.json')
    expected=manifest['assets_archive'];archive_path=bundle/expected['filename']
    require(sha(archive_path)==expected['sha256'],'Asset archive hash mismatch')
    require(archive_path.stat().st_size==expected['bytes'],'Asset archive size mismatch')
    with tempfile.TemporaryDirectory(prefix='shimmer-sealed-cache-') as folder:
        cache=Path(folder)/'hf_cache/hub'
        with tarfile.open(archive_path) as archive:
            names=[]
            for member in archive:
                require(member.isfile() and member.name in expected['members'],'Unexpected archive entry')
                names.append(member.name);entry=expected['members'][member.name]
                require(member.size==entry['bytes'],'Member size mismatch')
                h=hashlib.sha256();small=bytearray()
                selected=member.name.endswith(('/refs/main','/config.json'))
                stream=archive.extractfile(member)
                for block in iter(lambda:stream.read(8*1024*1024),b''):
                    h.update(block)
                    if selected:small.extend(block)
                require(h.hexdigest()==entry['sha256'],'Member hash mismatch: '+member.name)
                if selected:
                    target=(Path(folder)/member.name).resolve()
                    require(target.is_relative_to(Path(folder).resolve()),'Unsafe member')
                    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(small)
            require(len(names)==len(set(names)) and set(names)==set(expected['members']),'Archive inventory mismatch')
        sys.path.insert(0,str(next(Path(wheelhouse).glob('huggingface_hub-*.whl'))))
        import huggingface_hub
        require(huggingface_hub.__version__=='0.30.2','Pinned resolver required')
        resolutions=[]
        with patch.object(huggingface_hub.HfApi,'repo_info',side_effect=AssertionError('Network forbidden')):
            for model in manifest['models']:
                directory=cache/('models--'+model['model_id'].replace('/','--'))
                admit_cache_ref(directory,model)
                snapshot=Path(huggingface_hub.snapshot_download(model['model_id'],cache_dir=cache,local_files_only=True))
                require(snapshot==directory/'snapshots'/model['revision'],'Default revision resolved incorrectly')
                resolutions.append(dict(model_id=model['model_id'],revision=snapshot.name,
                    model_type=read(snapshot/'config.json')['model_type'],ref_bytes=(directory/'refs/main').stat().st_size))
    receipt=dict(passed=True,manifest_sha256=sha(bundle/'execution_manifest.json'),
        archive_sha256=expected['sha256'],verified_members=len(names),default_revision_resolutions=resolutions,
        model_loads=0,network_used=False)
    write(bundle/'asset_verification.json',receipt);print(json.dumps(receipt,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--wheelhouse',type=Path,required=True)
    args=p.parse_args();verify(args.bundle,args.wheelhouse)
