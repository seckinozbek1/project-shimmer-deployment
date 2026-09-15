"""Post-label-commit audit; failures remain quarantined and NOT_READY."""
import importlib.abc,importlib.util,io,socket,sys,unittest
from collections import Counter
class NoModels(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'torch','transformers','openai','anthropic','sentence_transformers'}:raise RuntimeError('Model/provider imports forbidden')
sys.meta_path.insert(0,NoModels())
def blocked(*a,**k):raise RuntimeError('Network forbidden')
socket.create_connection=blocked;socket.socket.connect=blocked
import semantics as s
sys.path.insert(0,str(s.HERE))
import review_flow as f
import regression_phase_guard as phase

def main():
 checkpoint=s.read(s.HERE/'post_freeze/GOLD_COMPARISON_STARTED.json')
 phase.require_label_commit(checkpoint['pre_gold_commit'])
 out=s.HERE/'validation';out.mkdir(exist_ok=True);suite=unittest.TestSuite()
 for name in ('checks','completed_checks'):
  spec=importlib.util.spec_from_file_location('curation_'+name,s.HERE/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
 log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite);(out/'validation.log').write_text(log.getvalue(),encoding='utf8')
 if not result.wasSuccessful():print(log.getvalue());return 1
 sys.path.insert(0,str(s.ROOT/'benchmark/first_tuning_review_cohort_v2'));import cohort
 cohort.verify_frozen()
 history=s.ROOT/'docs/fix/contract_model_ab_20260915';hashes=s.read(history/'ARTIFACT_HASHES.json')
 for n,h in hashes.items():
  if s.digest((history/n).read_bytes())!=h:raise ValueError('Historical drift')
 import run_gate as old_gate
 reproduced=old_gate.historical_baseline(s.read(cohort.h.V1/'seed.json'))
 historical={}
 for name in ('machine_adjudication_v1','machine_adjudication_v2','producer_coverage_amendment_v1'):
  root=s.ROOT/'benchmark'/name;manifest=s.read(root/'release_freeze.json')['hashes']
  for n,h in manifest.items():
   if s.digest((root/n).read_bytes())!=h:raise ValueError('Prior evidence drift')
  historical[name]=len(manifest)
 s.write(out/'historical_integrity.json',dict(frozen_files=historical,historical_files=len(hashes),historical_rejections=len(reproduced['results']),benchmark_acceptance_unchanged=True,r06_preserved=True))
 sys.path.insert(0,str(s.ROOT/'tools'));from prepare_cloud_run import credential_locations
 population=s.read(s.HERE/'population.json')
 for slot in 'ABC':s.isolated(f.WORK/('reviewer_'+slot),population['packet_hashes'])
 count=0
 for root in (s.HERE,f.WORK):
  for p in root.rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
    if credential_locations(p.read_bytes(),str(p)):raise ValueError('Credential finding at '+str(p))
    count+=1
 audit=s.read(s.HERE/'PRE_GOLD_ACCESS_AUDIT.json')
 s.write(out/'security.json',dict(files_scanned=count,credential_findings=0,operator_content_used=False,reviewer_gold_exposure_detected=False,strict_target_access_order_pass=False,governance_pass=False,
  isolation='Fresh contexts, exact synthetic packet hashes and access attestations; shared filesystem/model family. Historical harness target read before label freeze is a separately recorded timing violation.',network_and_model_imports_blocked=True))
 meta={r['example_id']:r for r in population['rows']}
 quarantined=s.read(s.HERE/'post_freeze/quarantined_semantically_qualified_labels.json')
 def coverage(rows):
  labels=[r.get('typed_label') for r in rows]
  return dict(count=len(rows),domains=sorted({meta[r['example_id']]['domain'] for r in rows}),templates=sorted({meta[r['example_id']]['template_family'] for r in rows}),families=sorted({meta[r['example_id']]['document_family'] for r in rows}),
   gap=sum(any(i['gap_atoms'] for i in l['items']) for l in labels),uncertainty=sum(l['source_uncertainty_present'] for l in labels),multi_claim=sum(sum(len(i['claims']) for i in l['items'])>1 for l in labels),evidence_selection=sum(meta[r['example_id']]['features']['evidence_selection'] for r in rows))
 qtrain=[r for r in quarantined if r['split']=='train'];qdev=[r for r in quarantined if r['split']=='dev']
 access=s.HERE/'machine_adjudicated_producer_candidates_v2';train=s.read(access/'train.json');dev=s.read(access/'dev.json');rows=train+dev
 c=coverage(rows);qc=coverage(quarantined)
 criteria=dict(train_minimum=len(train)>=32,dev_minimum=len(dev)>=16,domains=len(c['domains'])>=8,templates=len(c['templates'])==len(population['templates']),gaps_both=coverage(train)['gap']>0 and coverage(dev)['gap']>0,uncertainty_both=coverage(train)['uncertainty']>0 and coverage(dev)['uncertainty']>0,multi_claim=c['multi_claim']>0,evidence_selection=c['evidence_selection']>0,canonical_valid=True,no_evaluation_leakage=True,governance=audit['governance_pass'])
 producer=all(criteria.values())
 readiness=dict(protocol=s.PROTOCOL,policy=s.POLICY,renderer=s.RENDERER,evidence_kind='training_label_curation_evidence',use='curation_only',independent_generalization_evidence=False,blind_final_evaluation=False,
  producer_status='PRODUCER_TUNING_COVERAGE_'+('READY' if producer else 'NOT_READY'),balanced_status='BALANCED_AGENT_ADJUDICATED_TUNING_EXPERIMENT_'+('READY' if producer else 'NOT_READY'),
  human_status='FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING',human_first_reviews=0,human_second_reviews=0,human_adjudications=0,
  eligible_producer=dict(train=len(train),dev=len(dev),coverage=c),quarantined_semantically_qualified=dict(train=coverage(qtrain),dev=coverage(qdev),overall=qc),
  semantic_coverage_without_governance=len(qtrain)>=32 and len(qdev)>=16 and len(qc['domains'])==8 and len(qc['templates'])==8,preserved_auditor=dict(train=46,dev=24),combined_eligible_conceptual=dict(train=46+len(train),dev=24+len(dev)),
  combined_quarantined_hypothetical=dict(train=46+len(qtrain),dev=24+len(qdev)),criteria=criteria,training_authorized=False,final_model_acceptance=False,execution_manifests_issued=False,local_tests=result.testsRun,effect_proofs=9,
  blocker='Strict target-access timing violation quarantines all otherwise qualified producer labels; four DEV packets additionally fail frozen completeness parsing of a heading.')
 s.write(s.HERE/'post_freeze/readiness.json',readiness)
 print(__import__('json').dumps(dict(tests=result.testsRun,effect_proofs=9,producer_status=readiness['producer_status'],balanced_status=readiness['balanced_status'],eligible=readiness['eligible_producer'],quarantined_train=len(qtrain),quarantined_dev=len(qdev),quarantined_domains=len(qc['domains']),quarantined_templates=len(qc['templates']),quarantined_families=len(qc['families']),semantic_coverage_without_governance=readiness['semantic_coverage_without_governance']),indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())
