"""Recheck local artifacts and emit the implementation-only readiness decision."""
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from bundle import allowed

def main():
    frozen()
    evidence=read(HERE/'dry_run_evidence.json')
    require(evidence['status']=='PASS' and evidence['real_optimizer_updates']==0 and evidence['real_generation_calls']==0,'Dry-run failure')
    require(not any(evidence['access'].values()),'Forbidden data/model/network access')
    for role in PINS:
        for split in ('train','dev'):load_rows(role,split,gradient=split=='train')
    manifest=read(HERE/'bundle_manifest.json');archive=HERE/'training_bundle.zip'
    require(digest(archive.read_bytes())==manifest['sha256'],'Bundle bytes changed')
    with zipfile.ZipFile(archive) as z:
        require(set(z.namelist())==set(allowed()+[(HERE/'freeze.json').relative_to(ROOT).as_posix()]),'Bundle membership changed')
    sys.path.insert(0,str(ROOT/'tools'))
    from cloud_run_common import credential_locations
    from prepare_cloud_run import git
    paths=sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ('security_scan.json','release_freeze.json'))
    for name in ('FIRST_DOMAIN_AGNOSTIC_TUNING_EXPERIMENT_IMPLEMENTATION.md','RESUME.md'):
        p=ROOT/'docs/fix'/name
        if p.exists():paths.append(p)
    scanned=[]
    for p in paths:
        if p.suffix=='.zip':
            with zipfile.ZipFile(p) as z:
                for name in z.namelist():
                    hits=credential_locations(z.read(name),name)
                    require(not hits,'WARNING: Possible API key detected in '+name+'. Do not push. Rotate the key immediately.')
        else:
            hits=credential_locations(p.read_bytes(),p.name)
            require(not hits,'WARNING: Possible API key detected in '+str(p)+'. Do not push. Rotate the key immediately.')
        scanned.append(p.relative_to(ROOT).as_posix())
    changed=git(ROOT,'diff','--name-only','a4e369fbfb18f1f547ab207334fe3698627b9d7b').decode().splitlines()
    require(all(n.startswith('tuning/first_domain_agnostic_v1/') or n in ('docs/fix/FIRST_DOMAIN_AGNOSTIC_TUNING_EXPERIMENT_IMPLEMENTATION.md','docs/fix/RESUME.md') for n in changed),'Historical tracked artifact changed')
    write(HERE/'security_scan.json',dict(files=scanned,file_count=len(scanned),credential_findings=0,
        protected_label_findings=0,archive_entries=len(manifest['files']),historical_tracked_changes=0,
        sensitive_values_printed=False,operator_files_touched=False))
    write(HERE/'readiness.json',dict(status='FIRST_TUNING_EXPERIMENT_IMPLEMENTATION_READY',
        experiment=EXPERIMENT,training_authorized=False,counts=read(HERE/'experiment.json')['counts'],
        checks_passed=evidence['check_count'],effect_proofs=evidence['effect_count'],
        real_model_training=False,real_optimizer_updates=0,model_generation_calls=0,cloud_calls=0,paid_api_calls=0,
        protected_reads=0,credential_findings=0,historical_evidence_modified=False,
        human_review_status='FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING',
        scope='Implementation readiness only. No model-quality, independent-test, human-validation or training-authorization claim.',
        runtime_limit='Exact remote CUDA/PEFT imports and kernel behavior must pass future runtime preflight; no full model loaded locally.'))
    print('FIRST_TUNING_EXPERIMENT_IMPLEMENTATION_READY')
    print('Security scan files:',len(scanned),'findings: 0; protected labels in bundle: 0')

if __name__=='__main__':main()
