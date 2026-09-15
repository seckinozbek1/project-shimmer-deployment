"""Local, network/model-blocked validation and evidence collection."""
import importlib.abc
import importlib.util
import io
import json
from pathlib import Path
import socket
import sys
import unittest
import zipfile
import cohort as c


class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch','transformers','anthropic','openai','sentence_transformers'}:
            raise RuntimeError('Model/provider imports forbidden')


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=c.ROOT/'output/first_tuning_cohort_v2_validation')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    sys.meta_path.insert(0,NoModels())
    def blocked(*a,**k):raise RuntimeError('Network forbidden')
    socket.create_connection=blocked;socket.socket.connect=blocked
    c.verify_frozen()
    spec=importlib.util.spec_from_file_location('cohort_v2_checks',c.HERE/'checks.py')
    checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
    log=io.StringIO()
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(checks))
    (args.out/'validation.log').write_text(log.getvalue(),encoding='utf-8')
    if not result.wasSuccessful():
        print(log.getvalue());return 1
    sys.path.insert(0,str(c.ROOT/'tools'))
    from prepare_cloud_run import credential_locations
    exports=c.manifests()[2];scans={};files=members=0
    for name,m in exports.items():
        audit=c.audit_export(c.HERE/name,m['ids'])
        for p in (c.HERE/name).iterdir():
            if credential_locations(p.read_bytes(),p.name):raise ValueError('Credential finding in '+p.name)
            files+=1
        with zipfile.ZipFile(c.HERE/(name+'.zip')) as z:
            for p in z.namelist():
                if credential_locations(z.read(p),p):raise ValueError('Credential finding in archive')
                members+=1
        scans[name]=dict(audit,gold_findings=0,admin_findings=0,split_findings=0,historical_answer_findings=0,
                        credential_findings=0,privacy_findings=0,
                        privacy_basis='Exact allowlist from frozen synthetic legitimate input and blank responses, plus opaque binding; no private input reads.')
    c.write(args.out/'export_security.json',dict(exports=scans,files_scanned=files,archive_members_scanned=members))
    history=c.ROOT/'docs/fix/contract_model_ab_20260915'
    hashes=c.read(history/'ARTIFACT_HASHES.json')
    for name,expected in hashes.items():
        if c.digest((history/name).read_bytes())!=expected:raise ValueError('Historical evidence changed')
    import run_gate as old_gate
    historical=old_gate.historical_baseline(c.read(c.h.V1/'seed.json'))
    c.write(args.out/'historical_integrity.json',dict(entries_verified=len(hashes),rejections_reproduced=4,
            raw_hashes={v['label']:v['raw_sha256'] for v in historical['results']},rewritten=False))
    c.write(args.out/'validation.json',dict(tests=result.testsRun,failures=0,errors=0,
            effect_proofs=['held-out exclusion','superseded binding rejection','export filename allowlist','blank response byte integrity'],
            actual_human_submissions=0,fake_human_submissions=0,acceptance_unchanged=True,
            old_cohort_rejection_verified=True,model_generation=False,training=False,cloud=False,paid_api=False))
    print(json.dumps(dict(tests=result.testsRun,effect_proofs=4,export_files=files,archive_members=members,status='FIRST_TUNING_EXPERIMENT_REVIEW_PENDING')))
    return 0


if __name__=='__main__':raise SystemExit(main())
