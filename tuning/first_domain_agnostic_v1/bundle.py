"""Deterministic allowlisted TRAIN/DEV-only source bundle. No directory crawling."""
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

SOURCE = [
    'scripts/compact_contracts.py','scripts/bounded_extraction.py','scripts/pairing_map.py','scripts/finding_record.py',
    'scripts/localization.py',
    'benchmark/producer_coverage_amendment_v3/semantics.py',
    'benchmark/producer_coverage_amendment_v3/structural.py',
    'benchmark/task_semantics/core.py',
]

def allowed():
    prefix=HERE.relative_to(ROOT).as_posix()+'/'
    names=SOURCE+[prefix+n for n in ('common.py','evaluation.py','train.py','experiment.json','dependency_lock.json')]
    for role in PINS:
        names.extend(prefix+role+'/'+n for n in ('experiment.json','dataset.json','train.json','dev.json'))
    return sorted(names)

def seal():
    names=allowed()
    manifest=dict(experiment=EXPERIMENT,files={n:digest((ROOT/n).read_bytes()) for n in names},
        data_scope='Only exact approved role TRAIN/DEV; no protected labels or admin maps')
    write(HERE/'freeze.json',manifest)
    return manifest

def build(destination, extra=()):
    require(not extra,'Additional bundle inputs forbidden')
    manifest=frozen();require(sorted(manifest['files'])==allowed(),'Bundle allowlist changed')
    for role in PINS:
        load_rows(role,'train',gradient=True);load_rows(role,'dev')
    sys.path.insert(0,str(ROOT/'tools'))
    from cloud_run_common import credential_locations
    names=allowed()+[(HERE/'freeze.json').relative_to(ROOT).as_posix()]
    for n in names:
        require(not credential_locations((ROOT/n).read_bytes(),n),'Possible credential; stop: '+n)
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for n in sorted(names):
            info=zipfile.ZipInfo(n,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,(ROOT/n).read_bytes())
    with zipfile.ZipFile(destination) as archive:
        require(archive.namelist()==sorted(names),'Archive membership mismatch')
        for n in names:
            require(digest(archive.read(n))==digest((ROOT/n).read_bytes()),'Archive integrity failure')
    return dict(file_count=len(names),bytes=Path(destination).stat().st_size,sha256=digest(Path(destination).read_bytes()),
        files=names,protected_labels=0,credential_hits=0,model_weights=0,uploaded=False)

if __name__=='__main__':
    seal()
    write(HERE/'bundle_manifest.json',build(HERE/'training_bundle.zip'))
