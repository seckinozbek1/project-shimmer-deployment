"""Model-free forensic reproduction of the consumed run's cache-ref failure."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/fix/ordinary_final_cloud_run'


def probe():
    manifest = json.loads((BASE / 'execution_manifest.json').read_text())
    wheel = next((ROOT / 'output/cloud_wheels/ordinary_final_cp312').glob('huggingface_hub-*.whl'))
    sys.path.insert(0, str(wheel))
    import huggingface_hub
    assert huggingface_hub.__version__ == '0.30.2'
    from huggingface_hub import snapshot_download
    observations = []
    with tempfile.TemporaryDirectory(prefix='shimmer-ref-probe-') as temporary:
        cache = Path(temporary)
        with tarfile.open(ROOT / '.tmp/ordinary_final_assets.tar') as archive:
            for model in manifest['models']:
                prefix = 'hf_cache/hub/models--' + model['model_id'].replace('/', '--')
                directory = cache / prefix.split('/')[-1]
                refs = directory / 'refs/main'
                snapshot = directory / 'snapshots' / model['revision']
                refs.parent.mkdir(parents=True)
                snapshot.mkdir(parents=True)
                original = archive.extractfile(prefix + '/refs/main').read()
                refs.write_bytes(original)
                config = archive.extractfile(prefix + '/snapshots/' + model['revision'] + '/config.json').read()
                assert hashlib.sha256(config).hexdigest() == model['files']['config.json']['sha256']
                (snapshot / 'config.json').write_bytes(config)
                assert refs.read_text().strip() == model['revision']
                def resolve(revision=None):
                    return snapshot_download(model['model_id'], revision=revision,
                                             cache_dir=str(cache), local_files_only=True)
                try:
                    resolve()
                except OSError as error:
                    failed = type(error).__name__
                else:
                    raise AssertionError('Preserved newline ref unexpectedly resolved')
                assert Path(resolve(model['revision'])) == snapshot
                refs.write_bytes(model['revision'].encode('ascii'))
                assert Path(resolve()) == snapshot
                refs.write_bytes(original)
                try:
                    resolve()
                except OSError:
                    pass
                else:
                    raise AssertionError('Restored failure did not recur')
                observations.append(dict(model_id=model['model_id'],
                    ref_sha256=hashlib.sha256(original).hexdigest(),
                    ref_bytes=len(original),trailing_newline=original.endswith(b'\n'),
                    sealed_strip_check_passes=True,default_revision_error=failed,
                    explicit_revision_resolves=True,fixture_without_newline_resolves=True,
                    restored_original_fails=True,model_type=json.loads(config)['model_type']))
    with zipfile.ZipFile(wheel) as archive:
        library_source = archive.read('huggingface_hub/_snapshot_download.py')
    receipt = dict(passed=True,probe='Exact pinned offline snapshot resolver; config-only temporary fixtures',
        manifest_sha256=hashlib.sha256((BASE/'execution_manifest.json').read_bytes()).hexdigest(),
        library_version=huggingface_hub.__version__,
        library_source_sha256=hashlib.sha256(library_source).hexdigest(),observations=observations,
        network_used=False,model_loaded=False,production_files_modified=False,
        cloud_retried=False)
    (BASE/'cache_ref_failure_probe.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__ == '__main__':
    probe()
