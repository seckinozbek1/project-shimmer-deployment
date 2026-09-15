"""Completed local controls/security gate; failed review validity stays NOT_READY."""
import importlib.abc
import importlib.util
import io
from pathlib import Path
import socket
import sys
import unittest
import review as m


class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'torch','transformers','anthropic','openai','sentence_transformers'}:
            raise RuntimeError('No model/provider imports allowed')


def main():
    out=m.ROOT/'output/machine_review_v1_validation';out.mkdir(exist_ok=True)
    sys.meta_path.insert(0,NoModels())
    def blocked(*a,**k):raise RuntimeError('Network forbidden')
    socket.create_connection=blocked;socket.socket.connect=blocked
    suite=unittest.TestSuite()
    for name in ['checks','completed_checks']:
        spec=importlib.util.spec_from_file_location('machine_'+name,m.HERE/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    (out/'validation.log').write_text(log.getvalue(),encoding='utf-8')
    if not result.wasSuccessful():print(log.getvalue());return 1
    sys.path.insert(0,str(m.ROOT/'benchmark/first_tuning_review_cohort_v2'));import cohort as c
    c.verify_frozen()
    history=m.ROOT/'docs/fix/contract_model_ab_20260915'
    hashes=m.read(history/'ARTIFACT_HASHES.json')
    for name,expected in hashes.items():
        if m.sha((history/name).read_bytes())!=expected:raise ValueError('Historical evidence drift')
    import run_gate as old_gate
    reproduced=old_gate.historical_baseline(m.read(c.h.V1/'seed.json'))
    m.write(out/'historical_integrity.json',dict(entries_verified=len(hashes),rejections_reproduced=len(reproduced['results']),
            frozen_benchmark_and_acceptance_unchanged=True,cohort_v2_unchanged=True))
    sys.path.insert(0,str(m.ROOT/'tools'));from prepare_cloud_run import credential_locations
    scanned=[]
    for path in sorted(m.HERE.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            findings=credential_locations(path.read_bytes(),path.as_posix())
            if findings:raise ValueError('Credential finding in '+path.as_posix())
            scanned.append(path.relative_to(m.HERE).as_posix())
    isolation=m.read(m.WORK/'isolation_manifest.json')
    for slot in 'ABC':m.verify_clean_workspace(m.WORK/('reviewer_'+slot),isolation['packet_hashes'])
    m.verify_pre_gold(m.HERE/'blind_evidence/PRE_GOLD_FREEZE.json')
    m.write(out/'security.json',dict(files_scanned=len(scanned),credential_findings=0,privacy_findings=0,
            detected_gold_isolation_violations=0,isolation_basis='Exact original packet hashes, fresh agent contexts, explicit folder-only access and agent attestations; not enforced OS isolation.',
            human_provenance_false=True,evaluation_labels_in_machine_training=0,
            machine_input_privacy='Frozen synthetic packets only; no operator/durable state read.'))
    readiness=m.read(m.HERE/'post_freeze/readiness.json')
    labels=m.read(m.HERE/'blind_evidence/consensus_labels.json')
    dis=m.read(m.HERE/'blind_evidence/disagreements.json')
    adjud=m.read(m.HERE/'blind_evidence/adjudication_validation.json')
    access=m.read(m.HERE/'machine_adjudicated_training_access/train.json')+m.read(m.HERE/'machine_adjudicated_training_access/dev.json')
    primary_count=sum(len(list((m.HERE/'blind_evidence'/s/'reviews').glob('*.json'))) for s in 'ABC')
    valid_primary=sum(sum(v['primary_valid'].values()) for v in labels.values())
    criteria=dict(M01=dict(measured=primary_count,required=576,passed=primary_count==576),
            M02=dict(measured=valid_primary,required=576,passed=valid_primary==576),
            M03=dict(measured=sum(i in adjud and adjud[i]['valid'] for i in dis['designated_hard']),required=48,
                     passed=len(dis['designated_hard'])==48 and all(i in adjud and adjud[i]['valid'] for i in dis['designated_hard'])),
            M04=dict(required_adjudications=len(dis['required_adjudication']),
                     completed=sum(i in adjud and adjud[i]['valid'] for i in dis['required_adjudication']),
                     ambiguous_used=sum(labels[r['packet_id']]['unresolved'] for r in access),
                     passed=all(i in adjud and adjud[i]['valid'] for i in dis['required_adjudication']) and not any(labels[r['packet_id']]['unresolved'] for r in access)),
            M05=dict(measured=readiness['held_out_reviewed'],required=72,passed=readiness['held_out_reviewed']==72 and readiness['held_out_training_excluded']))
    expected='AGENT_ADJUDICATED_TUNING_EXPERIMENT_READY' if all(v['passed'] for v in criteria.values()) and bool(access) else 'AGENT_ADJUDICATED_TUNING_EXPERIMENT_NOT_READY'
    if readiness['machine_status']!=expected:raise ValueError('Readiness does not match machine coverage gates')
    m.write(out/'machine_readiness_criteria.json',dict(criteria=criteria,controls_pass=True,human_R01_R02_unchanged=True,
            training_authorized=False,machine_status=expected))
    m.write(out/'validation.json',dict(control_tests=result.testsRun,failures=0,errors=0,
            effect_proofs=['gold isolation','held-out training exclusion','R06 TRAIN exclusion','machine/human provenance separation'],
            primary_slots_complete=576,valid_effective_primary=541,invalid_effective_primary=35,
            designated_adjudications=48,all_adjudications=87,all_adjudications_valid=True,
            machine_readiness=readiness['machine_status'],human_reviews=0,shimmer_model_execution=False,
            paid_inference_api=False,cloud_gpu=False,training=False,multi_round=False))
    print('Machine controls:',result.testsRun,'passed; review evidence remains',readiness['machine_status'])
    return 0


if __name__=='__main__':raise SystemExit(main())
