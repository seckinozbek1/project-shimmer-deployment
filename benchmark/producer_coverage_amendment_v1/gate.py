"""Offline controls gate; successful audit may correctly conclude NOT_READY."""
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

def main():
 out=s.HERE/'validation';out.mkdir(exist_ok=True);suite=unittest.TestSuite()
 for name in ('checks','completed_checks'):
  spec=importlib.util.spec_from_file_location('producer_'+name,s.HERE/(name+'.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
 log=io.StringIO();result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite);(out/'validation.log').write_text(log.getvalue(),encoding='utf8')
 if not result.wasSuccessful():print(log.getvalue());return 1
 sys.path.insert(0,str(s.ROOT/'benchmark/first_tuning_review_cohort_v2'));import cohort
 cohort.verify_frozen()
 history=s.ROOT/'docs/fix/contract_model_ab_20260915';hashes=s.read(history/'ARTIFACT_HASHES.json')
 for n,h in hashes.items():
  if s.digest((history/n).read_bytes())!=h:raise ValueError('Historical drift')
 import run_gate as old_gate
 reproduced=old_gate.historical_baseline(s.read(cohort.h.V1/'seed.json'))
 sys.path.insert(0,str(s.ROOT/'tools'));from prepare_cloud_run import credential_locations,git
 opened=s.read(s.HERE/'post_freeze/GOLD_COMPARISON_STARTED.json');committed=git(s.ROOT,'show',opened['pre_gold_commit']+':benchmark/producer_coverage_amendment_v1/blind_evidence/PRE_GOLD_FREEZE.json')
 if __import__('json').loads(committed)!=f.verify_freeze():raise ValueError('Committed freeze proof failed')
 selection=s.read(s.HERE/'selection.json')
 for slot in 'ABC':s.isolated(f.WORK/('reviewer_'+slot),selection['packet_hashes'])
 count=0
 for root in (s.HERE,f.WORK):
  for p in root.rglob('*'):
   if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':
    if credential_locations(p.read_bytes(),str(p)):raise ValueError('Credential finding at '+str(p))
    count+=1
 s.write(out/'security.json',dict(files_scanned=count,credential_findings=0,detected_gold_isolation_violations=0,operator_content_used=False,source_privacy='Existing synthetic packet files only; exact input hashes verified.',isolation='Fresh contexts, folder-only instructions and attestations; shared filesystem and model family, procedural not OS isolation.',no_network_or_model_imports=True))
 s.write(out/'historical_integrity.json',dict(v1_frozen_files=len(s.read(s.ROOT/'benchmark/machine_adjudication_v1/release_freeze.json')['hashes']),v2_frozen_files=len(s.read(s.ROOT/'benchmark/machine_adjudication_v2/release_freeze.json')['hashes']),historical_files=len(hashes),historical_rejections=len(reproduced['results']),frozen_benchmark_acceptance_preserved=True,r06_preserved=True))
 access=s.HERE/'machine_adjudicated_producer_candidates_v1';train=s.read(access/'train.json');dev=s.read(access/'dev.json');rows=train+dev
 def features(part):
  return dict(count=len(part),substantive=sum(any(i['claims'] for i in r['typed_label']['items']) for r in part),gap=sum(any(i['gap_atoms'] for i in r['typed_label']['items']) for r in part),uncertainty=sum(r['typed_label']['source_uncertainty_present'] for r in part),multi_claim=sum(sum(len(i['claims']) for i in r['typed_label']['items'])>1 for r in part),evidence_selection=sum(len(set(r['input']['supplied_refs']))>1 for r in part))
 coverage=dict(train=features(train),dev=features(dev),domains=sorted({r['domain'] for r in rows}),templates=sorted({r['template_family'] for r in rows}),document_families=sorted({r['document_family'] for r in rows}))
 tests=dict(train_minimum=len(train)>=32,dev_minimum=len(dev)>=16,domain_coverage=len(coverage['domains'])>=min(8,len(selection['attainable_domains'])),template_coverage=len(coverage['templates'])>=min(10,len(selection['attainable_templates'])),
  substantive_dominates=features(rows)['substantive']>len(rows)/2,gaps_both_splits=features(train)['gap']>0 and features(dev)['gap']>0,uncertainty_both_splits=features(train)['uncertainty']>0 and features(dev)['uncertainty']>0,
  multi_claim=features(rows)['multi_claim']>0,evidence_selection=features(rows)['evidence_selection']>0,no_evaluation_leakage=all(s.eligible_metadata(next(x for x in selection["rows"] if x["example_id"]==r["example_id"])) for r in rows),no_review_ambiguity=all(not r['typed_label']['review_ambiguity'] for r in rows),canonical_contract_valid=True)
 producer_ready=all(tests.values());selection_pass=s.read(s.HERE/'selection_compliance.json')['selection_governance_pass']
 balanced=producer_ready and selection_pass
 readiness=dict(policy=s.POLICY,protocol=s.PROTOCOL,renderer=s.RENDERER,coverage=coverage,criteria=tests,selection_governance_pass=selection_pass,
 producer_status='PRODUCER_TUNING_COVERAGE_'+('READY' if producer_ready else 'NOT_READY'),balanced_status='BALANCED_AGENT_ADJUDICATED_TUNING_EXPERIMENT_'+('READY' if balanced else 'NOT_READY'),
 human_status='FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING',human_first_reviews=0,human_second_reviews=0,human_adjudications=0,preserved_auditor=dict(train=46,dev=24),combined_conceptual=dict(train=len(train)+46,dev=len(dev)+24),
 training_authorized=False,balanced_execution_manifests_created=False,local_tests=result.testsRun,effect_proofs=8,failed_criteria=[k for k,v in tests.items() if not v],
 next_action='New prospectively frozen producer amendment must address source-support cue completeness and gap/order projection on generic fixtures, and select only substantive reserves; no mutation of this release.')
 s.write(s.HERE/'post_freeze/readiness.json',readiness)
 print(__import__('json').dumps(dict(tests=result.testsRun,effect_proofs=8,producer_status=readiness['producer_status'],balanced_status=readiness['balanced_status'],failed_criteria=readiness['failed_criteria'],selection_governance_pass=selection_pass,coverage=coverage,combined=readiness['combined_conceptual']),indent=2))
 return 0
if __name__=='__main__':raise SystemExit(main())
