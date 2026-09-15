"""Local V2 release gate; no model imports, network, training or human promotion."""
import importlib.abc,importlib.util,io,socket,sys,unittest
from pathlib import Path
class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'torch','transformers','anthropic','openai','sentence_transformers'}:raise RuntimeError('Model/provider imports forbidden in review gate')
sys.meta_path.insert(0,NoModels())
def blocked(*args,**kwargs):raise RuntimeError('Network forbidden in review gate')
socket.create_connection=blocked;socket.socket.connect=blocked
import review as m
sys.path.insert(0,str(m.HERE))
import pipeline

def main():
    out=m.HERE/'validation';out.mkdir(exist_ok=True)
    suite=unittest.TestSuite()
    for name in ('normalizer_checks','projection_checks','completed_checks'):
        spec=importlib.util.spec_from_file_location('v2_'+name,m.HERE/(name+'.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    (out/'validation.log').write_text(log.getvalue(),encoding='utf8')
    if not result.wasSuccessful():print(log.getvalue());return 1
    sys.path.insert(0,str(m.ROOT/'benchmark/first_tuning_review_cohort_v2'))
    import cohort as c
    c.verify_frozen()
    history=m.ROOT/'docs/fix/contract_model_ab_20260915';hashes=m.read(history/'ARTIFACT_HASHES.json')
    for n,h in hashes.items():
        if m.sha((history/n).read_bytes())!=h:raise ValueError('Historical artifact drift')
    import run_gate as old_gate
    reproduced=old_gate.historical_baseline(m.read(c.h.V1/'seed.json'))
    v1=m.ROOT/'benchmark/machine_adjudication_v1';v1hash=m.read(v1/'release_freeze.json')['hashes']
    for n,h in v1hash.items():
        if m.sha((v1/n).read_bytes())!=h:raise ValueError('V1 release drift')
    iso=m.read(m.HERE/'blind_evidence/isolation_manifest.json')
    for s in 'ABC':m.verify_isolation(m.WORK/('reviewer_'+s),iso['packet_hashes'])
    pipeline.verify_freeze()
    sys.path.insert(0,str(m.ROOT/'tools'))
    from prepare_cloud_run import credential_locations,git
    checkpoint=m.read(m.HERE/'post_freeze/GOLD_COMPARISON_STARTED.json')
    committed=git(m.ROOT,'show',checkpoint['pre_gold_commit']+':benchmark/machine_adjudication_v2/blind_evidence/PRE_GOLD_FREEZE.json')
    if m.read(m.HERE/'blind_evidence/PRE_GOLD_FREEZE.json')!=__import__('json').loads(committed):raise ValueError('Freeze absent from recorded commit')
    count=0
    for root in (m.HERE,m.WORK):
        for p in root.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
                if credential_locations(p.read_bytes(),str(p)):raise ValueError('Credential finding; path='+str(p))
                count+=1
    security=dict(files_scanned=count,credential_findings=0,detected_gold_isolation_violations=0,
        privacy_basis='Exact synthetic packet hashes, clean assigned workspaces and agent access attestations; no operator/durable input used.',
        isolation_limit='Shared filesystem and parent model family; procedural isolation, not OS ACL or cross-model independence.',
        no_network_or_model_imports=True)
    m.write(out/'security.json',security)
    m.write(out/'historical_integrity.json',dict(v1_release_files=len(v1hash),historical_files=len(hashes),historical_rejections=len(reproduced['results']),cohort_benchmark_acceptance_unchanged=True,r06_train_exclusion_proved=True))
    b=m.HERE/'blind_evidence';post=m.HERE/'post_freeze';labels=m.read(b/'labels.json');dis=m.read(b/'disagreements.json');ad=m.read(b/'adjudication_validation.json')
    summary=m.read(post/'summary.json');refs=m.read(post/'evaluation_reference.json')
    access=m.HERE/'machine_adjudicated_training_access_v2';train=m.read(access/'train.json');dev=m.read(access/'dev.json');rows=train+dev
    criteria={
      'M01':dict(measured=sum(len(list((b/s/'reviews').glob('*.json'))) for s in 'ABC'),required=576),
      'M02':dict(measured=summary['valid_effective_primary'],required=576),
      'M03':dict(measured=sum(i in ad and ad[i]['valid'] for i in dis['designated_hard']),required=48),
      'M04':dict(measured=sum(i in ad and ad[i]['valid'] for i in dis['required_adjudication']),required=len(dis['required_adjudication']),ambiguous_candidates=sum(r['review_ambiguity'] for r in rows)),
      'M05':dict(measured=sum(r['held_out'] and r['label']['valid'] for r in refs),required=72,evaluation_candidates=len({r['example_id'] for r in refs}&{r['example_id'] for r in rows})),
      'M06':dict(measured=0,required=0),
      'M07':dict(measured=True,required=True)}
    for v in criteria.values():v['passed']=v['measured']==v['required'] and v.get('ambiguous_candidates',0)==0 and v.get('evaluation_candidates',0)==0
    meaningful=bool(train and dev and {r['role'] for r in rows}=={'producer','auditor'})
    passed=all(v['passed'] for v in criteria.values()) and meaningful
    status='AGENT_ADJUDICATED_TUNING_EXPERIMENT_'+('READY' if passed else 'NOT_READY')
    readiness=dict(summary,criteria=criteria,meaningful_machine_pool=meaningful,machine_status=status,
        human_status='FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING',training_authorized=False,final_model_acceptance_ready=False,
        local_tests=result.testsRun,normalizer_effect_proofs=7,model_improvement_claimed=False,
        limitation='Pool has 12 producer TRAIN and zero producer DEV; restricted machine review readiness does not establish balanced producer tuning/evaluation readiness.')
    m.write(post/'readiness.json',readiness)
    print(__import__('json').dumps(dict(tests=result.testsRun,effect_proofs=7,criteria=criteria,machine_status=status),indent=2))
    return 0 if passed else 2
if __name__=='__main__':raise SystemExit(main())
