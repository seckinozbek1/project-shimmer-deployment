"""Assemble readiness from frozen policy thresholds and completed post gates."""
import sys,json,shutil
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'benchmark/producer_coverage_amendment_v3'))
import access_guard as ag
G=ag.install('POST_GOLD')
import semantics as s
import review_flow as flow
from collections import Counter
OUT=s.HERE/'post_freeze'
WORK=ROOT/'output/producer_coverage_amendment_v3'

def main():
 binding=G.verify_post_phase();flow.verify_freeze();flow.policy_intact()
 history=s.read(OUT/'historical_integrity.json')
 cohort=s.read(WORK/'cohort_targeted_gate/validation.json')
 production=s.read(WORK/'production_gate_retry/validation.json')
 legacy=s.read(OUT/'legacy_summary.json')
 audit=s.read(s.HERE/'blind_evidence/PRE_GOLD_ACCESS_AUDIT.json')
 population=s.read(s.HERE/'population.json')
 metadata={r['example_id']:r for r in s.read(ROOT/'benchmark/task_semantics_v2/family_manifest.json')}
 assert cohort['tests']==24 and cohort['failures']==cohort['errors']==0
 assert production['status']=='PASS' and production['passed_checks']==85
 assert history['preserved_auditor']=={'train':46,'dev':24}
 assert history['r06_exact_non_train_population']==114 and history['r06_train_exclusion_effect']
 assert history['registered_criteria']==27 and history['catastrophic_zero_limits']==6
 assert legacy['governance_pass'] and audit['governance_pass'] and audit['successful_target_reads']==0
 producers={split:s.read(OUT/'machine_adjudicated_producer_candidates_v3'/(split+'.json')) for split in ('train','dev')}
 auditor_root=ROOT/'benchmark/machine_adjudication_v2/machine_adjudicated_training_access_v2'
 auditors={split:[r for r in s.read(auditor_root/(split+'.json')) if r['role']=='auditor'] for split in ('train','dev')}
 for role,pool in [('producer',producers),('auditor',auditors)]:
  for split,rows in pool.items():
   assert len({r['example_id'] for r in rows})==len(rows)
   for row in rows:
    m=metadata[row['example_id']]
    assert m['split']==split and m['domain'] not in ('astronomy','ecology') and row['role']==role
 for split,rows in producers.items():
  for row in rows:assert s.validate_label(row['typed_label'],row['input'])==row['canonical_target']
 all_producers=producers['train']+producers['dev']
 def coverage(rows):
  return dict(count=len(rows),domains=sorted({r['domain'] for r in rows}),templates=sorted({r['template_family'] for r in rows}),families=sorted({r['document_family'] for r in rows}),gap=sum(any(i['gap_atoms'] for i in r['typed_label']['items']) for r in rows),uncertainty=sum(r['typed_label']['source_uncertainty_present'] for r in rows),multi_claim=sum(sum(len(i['claims']) for i in r['typed_label']['items'])>1 for r in rows),evidence_selection=sum(len(r['input'].get('supplied_refs',[]))>1 for r in rows))
 cov={split:coverage(rows) for split,rows in producers.items()};overall=coverage(all_producers)
 criteria=dict(train_minimum=len(producers['train'])>=32,dev_minimum=len(producers['dev'])>=16,domains=len(overall['domains'])==8,templates=set(overall['templates'])==set(population['templates']),gaps_both=all(cov[x]['gap']>0 for x in cov),uncertainty_both=all(cov[x]['uncertainty']>0 for x in cov),multi_claim=overall['multi_claim']>0,evidence_selection=overall['evidence_selection']>0,canonical_valid=True,no_evaluation_leakage=True,governance=True)
 producer=all(criteria.values())
 balanced=producer and len(auditors['train'])==46 and len(auditors['dev'])==24
 manifest=dict(protocol=s.PROTOCOL,policy=s.POLICY,renderer=s.RENDERER,label_freeze_commit=binding['commit'],evidence_kind='training_label_curation_evidence',use='curation_only',training_authorized=False,human_reviewed=False,execution_manifest=False,roles={})
 for role,pool in [('producer',producers),('auditor',auditors)]:
  manifest['roles'][role]={}
  for split,rows in pool.items():
   source=(OUT/'machine_adjudicated_producer_candidates_v3'/(split+'.json')) if role=='producer' else auditor_root/(split+'.json')
   manifest['roles'][role][split]=dict(source=source.relative_to(ROOT).as_posix(),source_sha256=s.digest(source.read_bytes()),role_filter=role,count=len(rows),allowed_ids=[r['example_id'] for r in rows],selected_rows_sha256=s.digest(rows))
 if balanced:s.write(OUT/'balanced_role_separated_candidates_v3.json',manifest)
 readiness=dict(protocol=s.PROTOCOL,policy=s.POLICY,renderer=s.RENDERER,evidence_kind='training_label_curation_evidence',use='curation_only',strict_chronology_pass=True,pre_gold_target_reads=0,producer_status='PRODUCER_TUNING_COVERAGE_'+('READY' if producer else 'NOT_READY'),balanced_status='BALANCED_AGENT_ADJUDICATED_TUNING_EXPERIMENT_'+('READY' if balanced else 'NOT_READY'),human_status='FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING',human_first_reviews=0,human_second_reviews=0,human_adjudications=0,eligible_producer=cov,producer_overall=overall,preserved_auditor={k:len(v) for k,v in auditors.items()},combined={k:len(producers[k])+len(auditors[k]) for k in producers},criteria=criteria,PRE_GOLD_SAFE_tests=45,POST_GOLD_ONLY_checks=110,post_test_breakdown={'cohort':24,'production':85,'R06_effect':1,'existing_optional_production_skip':1},training_authorized=False,final_model_acceptance=False,independent_generalization_evidence=False,blind_final_evaluation=False,execution_manifests_issued=False)
 s.write(OUT/'readiness.json',readiness)
 # Capture the first successful protected open; synthetic guard fixture logs live elsewhere.
 reads=[]
 for path in (WORK/'access_logs').glob('*.json'):
  value=s.read(path)
  for r in value['successful_target_reads']:reads.append(dict(r,log=path.name))
 first=min(reads,key=lambda r:r['at']);assert G.verify_post_phase()['commit']==binding['commit']
 s.write(OUT/'FIRST_TARGET_ACCESS.json',dict(first_successful_target_open=first,commit=binding['commit'],manifest_sha256=binding['manifest_sha256'],pre_gold_target_reads=0,barrier='Actual commit object and exact manifest/current hashes verified before opening authored targets'))
 evidence=OUT/'validation_evidence';evidence.mkdir(exist_ok=False)
 for name in ('cohort_gate','cohort_targeted_gate','production_gate','production_gate_retry'):
  shutil.copytree(WORK/name,evidence/name)
 for name in ('post_broad_runner.py','post_integrity_adapter.py','integrity_worker.py','cohort_integrity_worker.py','cohort_targeted_runner.py','post_harness_corrections.json'):
  shutil.copyfile(WORK/name,evidence/name)
 shutil.copytree(WORK/'catalog_proofs',evidence/'catalog_proofs')
 shutil.copytree(WORK/'access_logs',evidence/'access_logs')
 shutil.copyfile(Path(__file__),evidence/'finalize_readiness.py')
 print(json.dumps({k:readiness[k] for k in ('producer_status','balanced_status','combined','preserved_auditor','PRE_GOLD_SAFE_tests','POST_GOLD_ONLY_checks')}))
if __name__=='__main__':main()
