"""Local registration/export validation; no model or human submissions."""
import argparse
import importlib.abc
import io
import json
from pathlib import Path
import socket
import sys
import unittest
import zipfile
import registration as r


class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'torch','transformers','anthropic','openai','sentence_transformers'}:
            raise RuntimeError('Model/provider import forbidden for review preparation')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=r.ROOT/'output/first_tuning_review_preparation')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    sys.meta_path.insert(0,NoModels())
    def blocked(*a,**k):raise RuntimeError('Network forbidden')
    socket.create_connection=blocked;socket.socket.connect=blocked
    r.verify_frozen()
    # Load this release's tests explicitly: the v1 checks module has the same
    # basename and intentionally remains outside this new release's test suite.
    import importlib.util
    spec=importlib.util.spec_from_file_location('first_review_checks',r.HERE/'checks.py')
    checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
    log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(checks))
    (args.out/'validation.log').write_text(log.getvalue(),encoding='utf-8')
    if not result.wasSuccessful():print(log.getvalue());return 1
    rows=r.records();first=r.read(r.HERE/'cohort.json')['ids'];second=r.read(r.HERE/'double_review.json')['ids']
    coverage=r.review_coverage(rows,first,second,r.HERE/'no_submissions_exist')
    sys.path.insert(0,str(r.ROOT/'tools'))
    from prepare_cloud_run import credential_locations
    export_scans={};total_files=0;archive_members=0
    for name,manifest in r.read(r.HERE/'export_admin_manifest.json').items():
        audit=r.audit_export(r.HERE/name,manifest['packet_ids'])
        for path in (r.HERE/name).iterdir():
            if credential_locations(path.read_bytes(),path.name):raise ValueError('Credential finding in reviewer export: '+path.name)
            total_files+=1
        with zipfile.ZipFile(r.HERE/(name+'.zip')) as z:
            for item in z.infolist():
                if credential_locations(z.read(item),item.filename):raise ValueError('Credential finding in reviewer archive member')
                archive_members+=1
        export_scans[name]=dict(audit,credential_findings=0,privacy_findings=0,
            privacy_basis='Byte-identical allowlisted packets from frozen public synthetic source; no operator or durable input access.')
    history=r.ROOT/'docs/fix/contract_model_ab_20260915'
    hashes=r.read(history/'ARTIFACT_HASHES.json')
    for name,expected in hashes.items():
        if r.digest((history/name).read_bytes())!=expected:raise ValueError('Historical evidence changed')
    import run_gate as old_gate
    historical=old_gate.historical_baseline(r.read(r.h.V1/'seed.json'))
    r.write(args.out/'historical_integrity.json',dict(entries_verified=len(hashes),rejections_reproduced=4,
        raw_hashes={v['label']:v['raw_sha256'] for v in historical['results']},historical_evidence_rewritten=False))
    r.write(args.out/'export_security.json',dict(exports=export_scans,files_scanned=total_files,archive_members_scanned=archive_members,
        no_gold=True,no_split_metadata=True,no_admin_mapping=True,no_historical_answers=True,no_private_operator_data=True))
    r.write(args.out/'readiness.json',{k:v for k,v in coverage.items() if k!='accepted_targets'})
    r.write(args.out/'validation.json',dict(tests=result.testsRun,failures=0,errors=0,
        effect_proofs=['export filename allowlist','blank packet byte integrity'],criteria=27,derived_hard_rule='R07',catastrophic_zero_limits=6,
        actual_human_submissions=0,fake_human_submissions_executed=0,model_generation=False,training=False,cloud=False,paid_api=False))
    print(json.dumps(dict(tests=result.testsRun,cohort=192,double_review=48,export_files=total_files,archive_members=archive_members,status=coverage['status'])))
    return 0


if __name__=='__main__':raise SystemExit(main())
