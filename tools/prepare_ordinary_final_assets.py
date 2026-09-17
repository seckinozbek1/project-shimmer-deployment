"""Build only sealed snapshot/wheel members and exact, non-newline Hub refs."""
import io
from pathlib import Path
import tarfile

from ordinary_final_run import cache_ref_bytes, require, sha


def build_assets(path, models, wheels, cache, wheelhouse):
    path, cache, wheelhouse = map(Path, (path, cache, wheelhouse))
    require(not path.exists(), 'Refuse to replace an existing asset archive')
    inventory = {}
    with tarfile.open(path, 'w', format=tarfile.PAX_FORMAT) as archive:
        def add(name, source=None, content=None, expected=None):
            if source is not None:
                require(sha(source) == expected['sha256'] and source.stat().st_size == expected['bytes'],
                        'Asset source hash/size mismatch: '+name)
                info = tarfile.TarInfo(name); info.size = source.stat().st_size
                with source.open('rb') as stream:
                    archive.addfile(info, stream)
            else:
                import hashlib
                require(dict(bytes=len(content),sha256=hashlib.sha256(content).hexdigest()) == expected,
                        'Generated ref differs from manifest')
                info = tarfile.TarInfo(name); info.size = len(content)
                archive.addfile(info, io.BytesIO(content))
            inventory[name] = expected
        for model in models:
            directory = 'models--'+model['model_id'].replace('/','--')
            prefix = 'hf_cache/hub/'+directory
            add(prefix+'/refs/main', content=cache_ref_bytes(model), expected=model['cache_ref'])
            for name, entry in sorted(model['files'].items()):
                add(prefix+'/snapshots/'+model['revision']+'/'+name,
                    source=cache/directory/'snapshots'/model['revision']/name, expected=entry)
        for entry in wheels.values():
            source = wheelhouse/entry['filename']
            add('wheels/'+entry['filename'], source=source,
                expected=dict(sha256=entry['sha256'],bytes=source.stat().st_size))
    return dict(filename=path.name,bytes=path.stat().st_size,sha256=sha(path),members=inventory)
