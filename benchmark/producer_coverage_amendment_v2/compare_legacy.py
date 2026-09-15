"""Post-commit legacy diagnostics; no frozen policy/label modifications."""
from collections import Counter
from datetime import datetime,timezone
import argparse
import semantics as s
s.sys.path.insert(0,str(s.HERE))
import review_flow as f
import legacy_projection as lp

def atoms_for(label,key):return [a for item in label['items'] for a in item[key]]
def fields(target,key):return sorted((i.get('span',''),v) for i in target['items'] for v in i.get(key,[]))
def source_settles_extra(a,packet):
 text=next(x['text'] for x in packet['source_spans'] if x['alias']==a['span'])
 try:
  s.ground(a,text,a['refs'])
  projected=lp.project(a['support'],a['kind'],a['span'],a['refs'],text)
  return s.normalize(projected)==s.normalize(a)
 except ValueError:return False

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--pre-gold-commit',required=True);args=parser.parse_args()
 freeze=f.verify_freeze();f.policy_intact()
 s.sys.path.insert(0,str(s.ROOT/'tools'));from prepare_cloud_run import git
 recorded=git(s.ROOT,'show',args.pre_gold_commit+':benchmark/producer_coverage_amendment_v2/blind_evidence/PRE_GOLD_FREEZE.json')
 if __import__('json').loads(recorded)!=freeze:raise ValueError('Pre-gold freeze not committed')
 out=s.HERE/'post_freeze'
 if out.exists():raise ValueError('Never overwrite post-freeze diagnostics')
 s.write(out/'GOLD_COMPARISON_STARTED.json',dict(evidence_kind='training_label_curation_evidence',use='curation_only',started_at=datetime.now(timezone.utc).isoformat(),pre_gold_commit=args.pre_gold_commit,freeze_sha256=s.digest((s.HERE/'blind_evidence/PRE_GOLD_FREEZE.json').read_bytes())))
 # Fresh-label comparison starts here; PRE_GOLD_ACCESS_AUDIT records the earlier historical regression access.
 authored=s.read(s.ROOT/'benchmark/task_semantics/seed.json')+s.read(s.ROOT/'benchmark/task_semantics_v2/extension.json');index={r['example_id']:r for r in authored}
 labels=s.read(s.HERE/'blind_evidence/labels.json');canonical=s.read(s.HERE/'blind_evidence/canonical_targets.json');cons=s.read(s.HERE/'blind_evidence/consensus.json');sel=s.read(s.HERE/'population.json');packets=f.packets()
 comparisons={};counters=Counter();train=[];dev=[];exclusions=[];qualified=[]
 governance=s.read(s.HERE/'PRE_GOLD_ACCESS_AUDIT.json')['governance_pass']
 for row in sel['rows']:
  pid=row['packet_id'];entry=labels[pid];label=entry['review']['label'];wire=canonical[pid];gold=index[row['example_id']]['gold_target'];packet=packets[pid]['input'];spans={x['alias']:x['text'] for x in packet['source_spans']}
  gaps=[];unc=[];errors=[]
  for item in gold['items']:
   for key,kind,values in [('questions','gap',gaps),('uncertainty','uncertainty',unc)]:
    for wording in item[key]:
     try:values.append(lp.project(wording,kind,item['span'],item['refs'],spans[item['span']]))
     except (ValueError,KeyError) as exc:errors.append(dict(field=key,span=item['span'],wording=wording,reason=str(exc)))
  machine_gaps=atoms_for(label,'gap_atoms');machine_unc=atoms_for(label,'uncertainty_atoms')
  result=dict(example_id=row['example_id'],packet_id=pid,claims=fields(wire,'claims')==fields(gold,'claims'),evidence=fields(wire,'refs')==fields(gold,'refs'),
   refusal=(wire.get('status')=='refused')==(gold.get('status')=='refused'),typed_gaps=not any(e['field']=='questions' for e in errors) and s.material_atoms(machine_gaps)==s.material_atoms(gaps),
   typed_uncertainty=not any(e['field']=='uncertainty' for e in errors) and s.material_atoms(machine_unc)==s.material_atoms(unc),canonical_output_difference=wire!=gold,
   legacy_projection_errors=errors,legacy_target=gold,machine_canonical_target=wire,projected_legacy_gaps=gaps,projected_legacy_uncertainty=unc)
  agrees=all(result[k] for k in ('claims','evidence','refusal','typed_gaps','typed_uncertainty'))
  if agrees:classification='semantic_agreement';resolved=True
  elif errors:classification='legacy_projection_limitation';resolved=False
  elif not result['claims'] or not result['evidence'] or not result['refusal']:classification='real_semantic_disagreement';resolved=False
  else:
   gm=set(s.material_atoms(gaps+unc));mm=set(s.material_atoms(machine_gaps+machine_unc));extras=[a for a in machine_gaps+machine_unc if __import__('json').dumps(s.normalize(a),sort_keys=True) not in gm]
   if gm<mm and extras and entry['valid'] and all(entry['primary_valid'].values()) and all(source_settles_extra(a,packet) for a in extras):classification='legacy_authored_target_under_specification';resolved=True
   elif not entry['valid']:classification='unresolved';resolved=False
   else:classification='real_semantic_disagreement';resolved=False
  result.update(classification=classification,material_dispute_resolved=resolved,eligible=False,evidence_kind='training_label_curation_evidence',use='curation_only',typed_machine_label=label,source_support_spans=[dict(span=a['span'],support=a['support'],refs=a['refs']) for a in machine_gaps+machine_unc],classification_basis='Exact claims/refs/refusal and finite typed source-context projection; source-grounded strict legacy subset only when three valid primaries and final label validate. Unsupported or different meanings stay unresolved.')
  reasons=[]
  if not all(entry['primary_valid'].values()):reasons.append('invalid_primary')
  if not entry['valid']:reasons.append('invalid_final_review')
  if label['review_ambiguity']:reasons.append('review_ambiguity')
  if not resolved:reasons.append('unresolved_legacy_diagnostic')
  if not s.eligible_metadata(row):reasons.append('evaluation_access')
  if not reasons and not governance:
   qualified.append(dict(example_id=row['example_id'],packet_id=pid,split=row['split'],role='producer',evidence_kind='training_label_curation_evidence',use='curation_only',provenance='quarantined_producer_label_v2',human_reviewed=False,training_authorized=False,typed_label=label,canonical_target=wire,reason='Strict pre-gold access governance failed; not eligible'))
  if not governance:reasons.append('pre_gold_access_governance_failure')
  if not reasons:
   target=s.validate_label(label,packet)
   item=dict(example_id=row['example_id'],packet_id=pid,split=row['split'],role='producer',domain=row['domain'],template_family=row['template_family'],document_family=row['document_family'],
    provenance='machine_adjudicated_producer_candidate_v2',evidence_kind='training_label_curation_evidence',use='curation_only',human_reviewed=False,policy=s.POLICY,renderer=s.RENDERER,input=packet,input_sha256=packets[pid]['input_sha256'],typed_label=label,canonical_target=target)
   (train if row['split']=='train' else dev).append(item);result['eligible']=True
  else:exclusions.append(dict(example_id=row['example_id'],packet_id=pid,split=row['split'],reasons=reasons))
  for k in ('claims','evidence','refusal','typed_gaps','typed_uncertainty','canonical_output_difference'):counters[k]+=result[k]
  counters[classification]+=1;counters['unresolved']+=not resolved and classification!='unresolved';comparisons[pid]=result
 s.write(out/'legacy_comparison.json',comparisons);s.write(out/'legacy_summary.json',dict(evidence_kind='training_label_curation_evidence',use='curation_only',total=len(comparisons),**counters));s.write(out/'excluded_candidates.json',exclusions)
 access=s.HERE/'machine_adjudicated_producer_candidates_v2'
 for split,rows in [('train',train),('dev',dev)]:s.write(access/(split+'.json'),rows)
 s.write(access/'manifest.json',dict(policy=s.POLICY,protocol=s.PROTOCOL,provenance='machine_adjudicated_producer_candidate_v2',evidence_kind='training_label_curation_evidence',use='curation_only',human_reviewed=False,training_authorized=False,
  train=len(train),dev=len(dev),allowed_ids=[r['example_id'] for r in train+dev],files={n:s.digest((access/n).read_bytes()) for n in ('train.json','dev.json')},evaluation_data_included=False))
 s.write(out/'quarantined_semantically_qualified_labels.json',qualified)
 agreement=Counter(c['state'] for c in cons.values());triple={key:0 for key in ('claims','gaps','uncertainty','evidence','refusal')}
 for pid in labels:
  vals=[s.read(s.HERE/'blind_evidence'/slot/'reviews'/(pid+'.json'))['label'] for slot in 'ABC']
  for key in triple:
   if key in ('gaps','uncertainty'):sig=[s.material_atoms(atoms_for(v,'gap_atoms' if key=='gaps' else 'uncertainty_atoms')) for v in vals]
   elif key=='refusal':sig=[v['status'] for v in vals]
   else:sig=[fields(s.render(v),'refs' if key=='evidence' else 'claims') for v in vals]
   triple[key]+=all(v==sig[0] for v in sig)
 summary=dict(protocol=s.PROTOCOL,evidence_kind='training_label_curation_evidence',use='curation_only',independent_generalization_evidence=False,blind_final_evaluation=False,packets=len(labels),splits=dict(Counter(r['split'] for r in sel['rows'])),primary_expected=3*len(labels),primary_completed=sum(len(list((s.HERE/'blind_evidence'/slot/'reviews').glob('*.json'))) for slot in 'ABC'),
  valid_primaries=sum(sum(e['primary_valid'].values()) for e in labels.values()),invalid_primaries=sum(sum(not v for v in e['primary_valid'].values()) for e in labels.values()),
  agreement=dict(agreement),agreement_rates={k:v/len(labels) for k,v in agreement.items()},semantic_unanimity=triple,evidence_valid_triples=sum(all(e['primary_valid'].values()) for e in labels.values()),
  adjudications=len(s.read(s.HERE/'blind_evidence/adjudication_validation.json')),unresolved_ambiguities=sum(e['review']['label']['review_ambiguity'] for e in labels.values()),
  candidates=dict(train=len(train),dev=len(dev)),quarantined_semantically_qualified=dict(Counter(r['split'] for r in qualified)),governance_pass=governance,legacy=dict(counters),human_reviewed=False,training_authorized=False)
 s.write(out/'summary.json',summary);print(__import__('json').dumps(summary,indent=2))
if __name__=='__main__':main()
