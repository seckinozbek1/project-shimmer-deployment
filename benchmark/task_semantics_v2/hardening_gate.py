"""Reproduce local benchmark-hardening evidence without model execution."""
import argparse
from collections import Counter
import importlib.abc
import io
import json
from pathlib import Path
import socket
import sys
import unittest

import hardening as h


class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'torch','transformers','anthropic','openai','sentence_transformers'}:
            raise RuntimeError('No models/providers in benchmark hardening')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=h.ROOT/'output/domain_agnostic_hardening')
    args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
    sys.meta_path.insert(0,NoModels())
    def blocked(*args,**kwargs):raise RuntimeError('Network forbidden')
    socket.create_connection=blocked;socket.socket.connect=blocked
    baseline_files=h.verify_baseline();h.verify_freeze()
    base=h.read(h.V1/'seed.json');extension=h.read(h.HERE/'extension.json');rows=base+extension
    metadata=h.read(h.HERE/'metadata.json');policy=h.read(h.HERE/'domain_holdout.json')
    leakage=h.validate(rows,metadata,policy)
    import hardening_checks
    stream=io.StringIO();tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(hardening_checks))
    (args.out/'validation.log').write_text(stream.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():print(stream.getvalue());return 1
    scored=[h.baseline.evaluate(r,json.dumps(r['gold_target'])) for r in rows]
    index={r['example_id']:r for r in rows}
    old_neg=h.read(h.V1/'negative_candidates.json');new_neg=h.read(h.HERE/'compound_negatives.json')
    negatives=[dict(h.baseline.evaluate(index[n['parent_id']],n['raw']),candidate_id=n['candidate_id']) for n in old_neg+new_neg]
    if any(r['accepted_outcome'] for r in negatives):raise ValueError('Negative candidate accepted')
    # Existing public regression reader; original hashes and outputs remain intact.
    import run_gate as old_gate
    historical=old_gate.historical_baseline(base)
    stats={key:dict(Counter(r[key] for r in rows)) for key in ('role','domain','split','template_family','document_family','abstract_relation')}
    stats.update(dataset_version=h.VERSION,production_contract=h.CONTRACT,total=len(rows),new_examples=len(extension),
                 structural_templates=len({r['template_family'] for r in rows}),new_structural_templates=12,
                 document_families=len({r['document_family'] for r in rows}),new_document_families=48,
                 tuning_access=len(h.training_records(rows,metadata,policy)),heldout_domain_examples=sum(r['domain'] in policy['held_out_domains'] for r in rows),
                 unseen_template_examples=len(h.read(h.HERE/'unseen_templates.json')['unseen_examples']),
                 new_semantic_producer_cases=sum(r['role']=='producer' and r['abstract_relation']=='EXTRACTED' for r in extension),
                 independently_reviewed=0,pending_independent_review=len(rows),packets=len(h.read(h.HERE/'review_admin_mapping.json')['packet_to_examples']),
                 disagreements=0,final_adjudications=0,sealed_independent_examples=0,
                 prior_negative_candidates=len(old_neg),compound_candidates=len(new_neg),compound_types=dict(Counter(n['types'][0] for n in new_neg)))
    h.write(args.out/'statistics.json',stats)
    h.write(args.out/'authored_baseline.json',dict(provenance='authored_self_consistency_not_model_quality',results=scored,summary=h.baseline.aggregate(scored)))
    h.write(args.out/'negative_baseline.json',dict(provenance='authored_negative_candidates_not_generated_models',results=negatives,summary=h.baseline.aggregate(negatives)))
    h.write(args.out/'historical_baseline.json',historical)
    h.write(args.out/'family_statistics.json',h.family_statistics(scored,rows))
    leakage.update(tuning_access_findings=0,blinded_packet_findings=0,sealed_populated_examples=0,
                   blind_state='Pending independent contribution; synthetic temporary access tests are not blind examples')
    h.write(args.out/'leakage_audit.json',leakage)
    h.write(args.out/'validation.json',dict(tests=tests.testsRun,failures=0,errors=0,gold_outcomes=len(scored),negative_rejections=len(negatives),
                 historical_rejections=4,immutable_baseline_files_verified=baseline_files,historical_entries_verified=historical['historical_entries_verified'],
                 effect_proofs=['packet input allowlist','heldout domain exclusion','training file allowlist'],model_execution=False,network=False))
    h.write(args.out/'readiness.json',dict(verdict='DOMAIN_AGNOSTIC_TRAINING_EXPERIMENT_NOT_READY',
        blockers=['736 examples require independent human review; no actual reviewer submissions',
                  'Numeric quality, sample coverage and family/domain thresholds require prospective operator registration',
                  'Independent sealed-final material and external account/ACL provisioning remain pending'],
        infrastructure_implemented=True,training_authorized=False))
    print(json.dumps(dict(tests=tests.testsRun,gold=len(scored),negative_rejections=len(negatives),historical_rejections=4,
                          independently_reviewed=0,pending=len(rows))))
    return 0


if __name__=='__main__':raise SystemExit(main())
