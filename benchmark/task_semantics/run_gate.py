"""Offline entry point. Outputs are separate from immutable historical evidence."""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import difflib
import importlib.abc
import io
import json
from pathlib import Path
import socket
import sys
import unittest

import core as c

HERE=Path(__file__).resolve().parent


class NoModels(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split('.')[0] in {'torch','transformers','anthropic','openai','sentence_transformers'}:
            raise RuntimeError('Model/provider import forbidden in dataset gate')


def historical_baseline(seed):
    evidence=c.ROOT/'docs/fix/contract_model_ab_20260915'
    public=c.read(c.ROOT/'docs/fix/compact_contract_ab/fixture.json')
    probe=c.read(evidence/'evidence/probe/probe.json')
    adjudication=c.read(evidence/'semantic_adjudication.json')
    manifest=c.read(evidence/'ARTIFACT_HASHES.json')
    for name,expected in manifest.items():
        if c.digest((evidence/name).read_bytes())!=expected:
            raise ValueError('Historical evidence integrity failed: '+name)
    # Hash-bound raw observations remain diagnostics, not repaired acceptance.
    results=[]
    for call in probe['calls']:
        role='producer' if call['label'].startswith('producer') else 'auditor'
        row=deepcopy(next(r for r in seed if r['role']==role and r['abstract_relation'] in ('EXTRACTED','MATCH')))
        row.update(example_id='public-ab-'+role,split='regression',source_text=public['source'],
                   extraction_text=public['source'],owned_aliases=['s0'],context_only_aliases=[],ledger_max_chars=1200,
                   supplied_refs=['REF-0001','REF-0002'],required_refs=['REF-0001','REF-0002'],expected_uncertainty=False)
        row['provenance']['public_regression']=True
        row['gold_target']=({'items':[dict(span='s0',claims=['CLM-001','CLM-002'],questions=['What is the reporting date?'],uncertainty=[],status='extracted',refs=['REF-0001','REF-0002'])]}
            if role=='producer' else {'items':[dict(finding='MATCH',ref_ids=['REF-0001','REF-0002'],reasoning='Both labeled capacities and the missing reporting date are preserved without additions or omissions.',severity='low',confidence='CONFIDENT')]})
        raw=call['raw_text']
        result=c.evaluate(row,raw,truncated=call['usage']['truncated'])
        preserved=adjudication[call['label']]
        if c.digest(raw.encode('utf-8'))!=preserved['raw_sha256']:
            raise ValueError('Historical raw adjudication hash mismatch')
        if result['contract_valid'] or result['semantic_accepted']:
            raise ValueError('Historical rejected response promoted')
        result.update(label=call['label'],provenance='historical_generated_model_output',
            original_source_commit=probe['source_commit'],original_usage=call['usage'],
            evaluated_contract='semantic-task-v1 (OLD controls also rejected by their original adapter)',
            preserved_original_contract_valid=preserved['contract_valid'],
            preserved_raw_diagnostics=preserved,
            diagnostic_notice='Original hash-bound single-review observations only; no prefix parsing, repair, or acceptance.')
        results.append(result)
    if len(results)!=4:raise ValueError('Unexpected historical call set')
    return dict(results=results,summary=c.aggregate(results),all_four_rejections_reproduced=True,
                historical_entries_verified=len(manifest),
                historical_manifest_sha256=c.digest((evidence/'ARTIFACT_HASHES.json').read_bytes()))


def validate_artifacts(rows):
    index={r['example_id']:r for r in rows}
    plan=c.read(HERE/'split_plan.json')
    allocation={r['family']:r['split'] for r in plan['allocation']}
    for row in rows:
        if allocation.get(row['document_family'])!=row['split'] or row['split_plan_id']!=plan['id']:
            raise ValueError('Split changed after allocation')
    expected={s:[r['example_id'] for r in rows if r['split']==s] for s in ('train','dev','test','sealed_adversarial')}
    if c.read(HERE/'split_manifest.json')!=expected:raise ValueError('Split manifest drift')
    expected=[{k:r[k] for k in ('example_id','parent_id','split',*c.GROUPS)} for r in rows]
    if c.read(HERE/'family_ancestry.json')!=expected:raise ValueError('Ancestry manifest drift')
    seen=set()
    for candidate in c.read(HERE/'negative_candidates.json'):
        if candidate['candidate_id'] in seen:raise ValueError('Duplicate negative ID')
        seen.add(candidate['candidate_id'])
        parent=index[candidate['parent_id']]
        if candidate['split']!=parent['split'] or candidate['derivation_group']!=parent['derivation_group']:
            raise ValueError('Negative sibling leakage')
    freeze=c.read(HERE/'frozen_dataset.json')
    if c.digest((c.ROOT/'config/semantic_task_contract_v1.json').read_bytes())!=freeze['contract_manifest_sha256']:
        raise ValueError('Frozen contract manifest drift')
    for file,expected in freeze['hashes'].items():
        if c.digest((HERE/file).read_bytes())!=expected:raise ValueError('Frozen benchmark drift: '+file)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=c.ROOT/'output/domain_agnostic_tuning')
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    sys.meta_path.insert(0,NoModels())
    def blocked(*a,**kw):raise RuntimeError('Network forbidden in dataset gate')
    socket.create_connection=blocked
    socket.socket.connect=blocked
    rows=c.read(HERE/'seed.json')
    c.verify_freeze();validate_artifacts(rows)
    leak=c.leakage(rows)
    import checks
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(checks))
    (args.out/'validation.log').write_text(stream.getvalue(),encoding='utf-8')
    if not result.wasSuccessful():
        print(stream.getvalue());return 1
    authored=[c.evaluate(r,json.dumps(r['gold_target'],ensure_ascii=False)) for r in rows]
    index={r['example_id']:r for r in rows}
    negatives=[dict(c.evaluate(index[x['parent_id']],x['raw']),candidate_id=x['candidate_id'],transformation=x['transformation'])
               for x in c.read(HERE/'negative_candidates.json')]
    baseline=historical_baseline(rows)
    stats={field:dict(Counter(r[field] for r in rows)) for field in ('role','domain','abstract_relation','split','document_family','template_family','language','style')}
    stats.update(examples=len(rows),refusals=sum(r['expected_refusal'] for r in rows),
        uncertainty=sum(r['expected_uncertainty'] for r in rows),adjudication=dict(Counter(r['adjudication']['state'] for r in rows)),
        hard_negative_gold=dict(Counter(tag for r in rows for tag in r['hard_negative_tags'])),
        negative_candidates=dict(Counter(r['transformation'] for r in negatives)))
    # Lightweight warnings only. Explicit family/ancestry remains authoritative.
    representatives={r['document_family']:r for r in rows if r['role']=='producer' and r['abstract_relation']=='EXTRACTED'}
    pairs=[];families=list(representatives)
    for i,a in enumerate(families):
        for b in families[i+1:]:
            x,y=representatives[a],representatives[b]
            if x['split']==y['split']:continue
            similarity=difflib.SequenceMatcher(None,x['source_text'],y['source_text'],autojunk=False).ratio()
            if similarity>=.70:pairs.append(dict(a=a,b=b,ratio=similarity))
    leak['near_duplicate_warnings']=pairs
    leak['warning_interpretation']='Shared abstract facts and gap language produce similarity warnings; four public template families only. Manual independent review required before final held-out claims.'
    c.write(args.out/'statistics.json',stats)
    c.write(args.out/'leakage_audit.json',leak)
    c.write(args.out/'authored_baseline.json',dict(provenance='authored_gold_self_consistency_not_model_quality',results=authored,summary=c.aggregate(authored)))
    c.write(args.out/'negative_baseline.json',dict(provenance='authored_deterministic_corruptions_not_model_outputs',results=negatives,summary=c.aggregate(negatives)))
    c.write(args.out/'historical_baseline.json',baseline)
    c.write(args.out/'validation.json',dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
            authored_outcomes=len(authored),negative_rejections=sum(not r['accepted_outcome'] for r in negatives),
            effect_proofs=['whole-response parsing','exact evidence scoring','cross-split leakage'],
            model_imports_blocked=True,network_blocked=True,no_training=True))
    print(json.dumps(dict(tests=result.testsRun,authored=len(authored),negative_rejected=len(negatives),
                         historical_rejections=4,near_duplicate_warnings=len(pairs))))
    return 0


if __name__=='__main__':raise SystemExit(main())
