"""Offline deterministic corpus preparation. No training or execution path."""
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
# Do not shadow the standard-library statistics module in tokenizer dependencies.
sys.path=[p for p in sys.path if Path(p or '.').resolve()!=HERE]
import statistics as std_statistics
sys.path.insert(0,str(HERE))
import copy
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from conversion import digest, lineage, quartet
from validators import CLASSES, check_base, candidates, norm, validate
from leakage import cluster, cross_split, shortcut_audit, shingles, similarity, THRESHOLD
from tokenizer_check import load, CEILING

spec=importlib.util.spec_from_file_location('external_statistics',HERE/'statistics.py')
stats=importlib.util.module_from_spec(spec);spec.loader.exec_module(stats)

def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,value):
    (HERE/name).write_bytes((json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n').encode())
def jsonl(name,rows):
    (HERE/name).write_bytes((''.join(json.dumps(r,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows)).encode())

def guard():
    def hook(event,args):
        if event in {'socket.connect','socket.getaddrinfo','subprocess.Popen','os.system'}:
            raise PermissionError('Offline preparation denies networking/process execution')
        if event=='open' and isinstance(args[0],(str,bytes)):
            p=str(args[0]).replace('\\','/').lower()
            if any(x in p for x in ['/benchmark/keys/','/api_keys/','protected_holdout','protected_targets']):
                raise PermissionError('Protected/credential path denied')
            if p.endswith(('.safetensors','.bin','.pt','.pth','.npy','.npz')):
                raise PermissionError('Model/feature weight access denied')
    sys.addaudithook(hook)

def preserve():
    results={}
    for name in ['auditor_linear_probe_run','auditor_canonical_tuning_run','producer_tuning_v3_run']:
        path=ROOT/'docs/fix'/name/'EVIDENCE_MANIFEST.json'
        m=read(path)
        for p,v in m['text_files'].items():
            assert sha(ROOT/p)==v['sha256'], 'Historical text changed: '+p
        results[name]=dict(manifest_sha256=sha(path),text_files_checked=len(m['text_files']),all_match=True,
                          binary_files_opened=0)
    return results

def sources():
    manifests=read(HERE/'download_manifest.json'); rows=[]; records=[]
    expected=[set('sample_id doc_id doc original_summary original_text replace_text edited_summary explanation domain model edit_type'.split()),
              set('id doc seed_summary summary domain label edit_types'.split())]
    citations=[dict(title='SummExecEdit: A Factual Consistency Benchmark in Summarization with Executable Edits',
                    authors=['Onkar Thorat','Philippe Laban','Chien-Sheng Wu'],year=2024,url='https://arxiv.org/abs/2412.13378'),
               dict(title='LLMs as Factual Reasoners: Insights from Existing Benchmarks and Beyond',url='https://arxiv.org/abs/2305.14540',
                    documentation='https://github.com/salesforce/factualNLG')]
    for i,m in enumerate(manifests):
        for f in m['files']:
            assert sha(ROOT/f['path'])==f['sha256']
        d=read(ROOT/m['files'][0]['path'])
        assert len(d)==[4241,6348][i], 'Material upstream count change: stop'
        assert all(set(r)==expected[i] for r in d), 'Material upstream schema change: stop'
        for r in d:
            assert all(isinstance(v,list if k=='edit_types' else int if k=='label' else str) for k,v in r.items())
        card=(ROOT/m['files'][1]['path']).read_text(encoding='utf8')
        assert 'license: cc-by-4.0' in card
        if i==1:assert {r['label'] for r in d}=={0,1} and '1 if the summary is factually consistent' in card
        identifier='sample_id' if i==0 else 'id'
        assert len({r[identifier] for r in d})==len(d)
        record=dict(m,rows=len(d),schema={k:type(d[0][k]).__name__ for k in sorted(expected[i])},
            license='CC-BY-4.0',license_url='https://creativecommons.org/licenses/by/4.0/',citation=citations[i],
            unique_upstream_doc_ids=len({r['doc_id'] for r in d}) if i==0 else None,
            valid_nonplaceholder_doc_ids=len({r['doc_id'] for r in d if norm(r['doc_id']) not in {'n/a','none','null',''}}) if i==0 else None,
            unique_normalized_documents=len({norm(r['doc']) for r in d}),domains=dict(Counter(r['domain'] for r in d)),
            upstream_label_policy='Never mapped to Shimmer relations',
            conversion_use='Executable spans only' if i==0 else 'Future source pool only; no relation rows emitted')
        records.append(record);rows.append(d)
        (HERE/'licenses'/(m['dataset'].split('/')[1]+'-dataset-card.md')).write_bytes((ROOT/m['files'][1]['path']).read_bytes())
    write('source_manifest.json',records)
    return rows,records

def provenance(row,source):
    return dict(dataset=source['dataset'],publisher=source['publisher'],revision=source['revision'],license=source['license'],
        license_url=source['license_url'],citation=source['citation'],source_row_id=row['sample_id'],source_doc_id=row['doc_id'],
        original_row_hash=digest(row),document_hash=digest(norm(row['doc'])),source_hash=digest(norm(row['original_summary'])),
        upstream_edit_type=row['edit_type'],upstream_model=row['model'],
        changes='Deterministic formatting / verified replacement / designated deletion / adjacent insertion; relation assigned mechanically')

def fixtures():
    s='The vessel arrived at the northern port. Workers unloaded the cargo before sunset.'
    a='The vessel arrived at the northern port.';b='The vessel arrived at the southern port.'
    valid=dict(original_summary=s,original_text=a,replace_text=b,edited_summary=s.replace(a,b))
    assert check_base(valid) is None
    invalid={
        'empty':dict(valid,replace_text=''),
        'repeated_span':dict(valid,original_summary=s+' '+a),
        'hidden_edit':dict(valid,edited_summary=s.replace(a,b)+' Extra.'),
        'normalization_only':dict(valid,replace_text=a.lower(),edited_summary=s.replace(a,a.lower())),
        'insertion_disguised':dict(valid,replace_text=a[:-1]+' today.',edited_summary=s.replace(a,a[:-1]+' today.')),
        'partial_clause':dict(valid,original_text='northern',replace_text='southern'),
        'empty_omission':dict(valid,original_summary=a,edited_summary=b),
        'dangling_pronoun':dict(valid,original_summary=a+' It arrived before sunset.',edited_summary=b+' It arrived before sunset.'),
    }
    out={k:check_base(r) for k,r in invalid.items()};assert all(out.values())
    for c,candidate in candidates(valid).items():
        assert validate(valid,c,s,candidate)
        try:validate(valid,c,s,candidate+' Unrelated added text.')
        except ValueError:out['tamper_'+c]='rejected'
        else:raise AssertionError('tampered candidate admitted')
    return out

def construct(execs,summedits,source,lengths):
    rejected=[];eligible=[]
    for r in execs:
        reason=check_base(r)
        if reason:rejected.append(dict(source_row_id=r['sample_id'],original_row_hash=digest(r),reason=reason))
        else:eligible.append(r)
    documents={digest(norm(r['doc'])):r['doc'] for r in execs+summedits}
    idgroups=defaultdict(list)
    for r in execs:
        if norm(r['doc_id']) not in {'n/a','none','null',''}:
            idgroups[r['doc_id']].append(digest(norm(r['doc'])))
    variants=defaultdict(list)
    for r in eligible:variants[digest(norm(r['doc']))].extend(candidates(r).values())
    groups,group_audit=cluster(documents,variants,idgroups.values())
    historical=read(ROOT/'tuning/auditor_canonical_execution/dataset.json')
    hs=read(ROOT/'tuning/auditor_canonical_execution/split.json')
    htexts=[shingles(t) for r in historical for t in [r['input']['extraction']]+[s['text'] for s in r['input']['source_spans']]]
    badgroups=set();histmax=0.
    for doc,vs in variants.items():
        for text in vs:
            ss=shingles(text)
            for ht in htexts:
                sim=similarity(ss,ht);histmax=max(histmax,sim)
                if sim>=THRESHOLD:badgroups.add(groups[doc])
    bydoc=defaultdict(list);token_rejections=0;prospective=[];overflow_rows=0
    for r in sorted(eligible,key=lambda r:digest(['selection',lineage(r)])):
        dh=digest(norm(r['doc']));reason=None
        if groups[dh] in badgroups:reason='historical_train_or_dev_lexical_overlap'
        else:
            temp=quartet(r,provenance(r,source),'prospective',groups[dh])
            ls=[lengths(x) for x in temp];prospective.extend(x['prompt_tokens'] for x in ls)
            over=sum(x['prompt_tokens']>CEILING for x in ls);overflow_rows+=over
            if over:reason='token_ceiling_whole_quartet';token_rejections+=1
        if reason:rejected.append(dict(source_row_id=r['sample_id'],original_row_hash=digest(r),reason=reason))
        else:bydoc[dh].append(r)
    chosen=[]
    for dh,rs in sorted(bydoc.items()):
        chosen.append(rs[0])
        for r in rs[1:]:rejected.append(dict(source_row_id=r['sample_id'],original_row_hash=digest(r),reason='one_lineage_per_document_cap'))
    chosen=sorted(chosen,key=lambda r:digest(['limit',lineage(r)]))
    for r in chosen[300:]:rejected.append(dict(source_row_id=r['sample_id'],original_row_hash=digest(r),reason='preferred_1200_row_cap'))
    chosen=chosen[:300]
    assert len({r['doc_id'] for r in chosen})==len(chosen), 'Upstream document ID cap exceeded'
    selected_groups=sorted({groups[digest(norm(r['doc']))] for r in chosen},key=lambda k:digest(['split',k]))
    n=len(selected_groups);nd=max(1,round(n*.1)) if n>=3 else 0
    assignments={g:('dev' if i<nd else 'holdout' if i<2*nd else 'train') for i,g in enumerate(selected_groups)}
    rows=[]
    for r in chosen:
        group=groups[digest(norm(r['doc']))]
        rows.extend(quartet(r,provenance(r,source),assignments[group],group))
    rows.sort(key=lambda r:digest(['row-order',r['example_id']]))
    for r in rows:r['lengths']=lengths(r)
    index={r['sample_id']:r for r in execs}
    for r in rows:
        raw=index[r['provenance']['source_row_id']]
        assert r['provenance']==provenance(raw,source)
        assert validate(raw,r['relation'],r['transformation']['original_summary'],r['transformation']['candidate'])
        assert r['lengths']['prompt_tokens']<=CEILING
    for key in ['lineage_id','document_group','document_key']:
        d=defaultdict(set)
        for r in rows:d[r[key]].add(r['split'])
        assert all(len(v)==1 for v in d.values())
    doc_split={r['provenance']['document_hash']:r['split'] for r in rows}
    registry=[]
    for dataset,pool in [('Salesforce/summexecedit',execs),('Salesforce/summedits',summedits)]:
        for r in pool:
            dh=digest(norm(r['doc']))
            registry.append(dict(dataset=dataset,row_id=r.get('sample_id',r.get('id')),upstream_doc_id=r.get('doc_id'),
                document_hash=dh,canonical_group=groups[dh],reserved_split=assignments.get(groups[dh]),original_row_hash=digest(r)))
    overlap=set(digest(norm(r['doc'])) for r in execs)&set(digest(norm(r['doc'])) for r in summedits)
    group_audit.update(cross_dataset_exact_document_overlap=len(overlap),cross_dataset_document_registry_rows=len(registry),
        placeholder_doc_id_rows_not_used_for_identity=sum(norm(r['doc_id']) in {'n/a','none','null',''} for r in execs),
        historical_train_dev_max_5gram_jaccard=histmax,historical_train_dev_excluded_groups=len(badgroups),
        split_assignment_order='Document clustering and assignment precede final example emission; only prospective token sizing occurs earlier.')
    return (rows,dict(upstream_rows=len(execs),mechanically_eligible_base_lineages=len(eligible),
        eligible_unique_docs=len({digest(norm(r['doc'])) for r in eligible}),selected_quartets=len(chosen),
        rejected_rows=len(rejected),reasons=dict(Counter(r['reason'] for r in rejected)),
        token_overflow_quartets=token_rejections,prospective_overflow_rows=overflow_rows,
        prospective_prompt_statistics=stats.describe(prospective),records=sorted(rejected,key=lambda r:r['source_row_id'])),
        group_audit,registry,documents,historical,hs)

def main():
    guard();before=preserve();fixture_results=fixtures()
    (execs,summedits),source=sources()
    lengths=load()
    # Cache pure tokenizer results across deterministic reconstruction.
    cache={}
    def cached_lengths(row):
        k=digest(row['input'])
        if k not in cache:cache[k]=lengths(row)
        return cache[k]
    built=construct(execs,summedits,source[0],cached_lengths)
    rows,rejections,group_audit,registry,documents,historical,hs=built
    again=construct(list(reversed(execs)),list(reversed(summedits)),source[0],cached_lengths)
    assert digest(rows)==digest(again[0]) and digest(rejections)==digest(again[1]), 'Non-deterministic rebuild'
    lexical=cross_split(rows,documents)
    assert lexical['exact_cross_split_duplicate_pairs']==0 and not lexical['near_duplicate_pairs']
    historical_train=[r for r in historical if r['example_id'] in hs['train']]
    historical_sub=[r for r in historical_train if r['relation']!='INSUFFICIENT_EVIDENCE']
    historical_dev=[r for r in historical if r['example_id'] in hs['validation'] and r['relation']!='INSUFFICIENT_EVIDENCE']
    external_train=[r for r in rows if r['split']=='train'];external_dev=[r for r in rows if r['split']=='dev']
    merged=historical_train+external_train
    assert len(historical_train)==240 and len(historical_sub)==192 and len(historical_dev)==48
    assert [r for r in merged if r['example_id'] in hs['train']]==historical_train
    assert len([r for r in merged if r['relation']=='INSUFFICIENT_EVIDENCE'])==48
    jsonl('examples.jsonl',rows);jsonl('substantive_relation_view.jsonl',rows);jsonl('merged_auditor_view.jsonl',merged)
    jsonl('document_registry.jsonl',sorted(registry,key=lambda r:(r['dataset'],r['row_id'])))
    write('rejection_stats.json',rejections);write('leakage_audit.json',dict(grouping=group_audit,cross_split=lexical))
    write('split.json',{s:[r['example_id'] for r in rows if r['split']==s] for s in ('train','dev','holdout')})
    write('holdout_receipt.json',dict(consumed=False,admitted=False,evaluated=False,evaluation_count=0,
        labels_frozen_for_integrity_only=True,required='Separate admission and receipt before any evaluation; this release is NOT_READY'))
    shortcut=shortcut_audit(rows);write('shortcut_audit.json',shortcut)
    statistics=stats.corpus(rows);write('statistics.json',statistics)
    historical_lengths={r['example_id']:cached_lengths(r) for r in historical_sub+historical_dev}
    tokenstats=dict(ceiling=CEILING,ceiling_scope='Classifier input only; explanation output budget must be revalidated before future integrated execution',
        no_truncation=True,release_prompt_statistics=stats.describe([r['lengths']['prompt_tokens'] for r in rows]),
        release_overflow_count=sum(r['lengths']['prompt_tokens']>CEILING for r in rows),
        prospective_prompt_statistics=rejections['prospective_prompt_statistics'],prospective_overflow_rows=rejections['prospective_overflow_rows'],
        historical_substantive_prompt_statistics=stats.describe([v['prompt_tokens'] for v in historical_lengths.values()]))
    write('tokenizer_evidence.json',tokenstats)
    old=read(ROOT/'tuning/auditor_linear_probe/experiment.json')
    feature_sets={'train':historical_sub+external_train,'external_dev':external_dev,'historical_dev':historical_dev}
    projection={}
    for name,sub in feature_sets.items():
        tokens=sum(cached_lengths(r)['prompt_tokens'] for r in sub)
        projection[name]=dict(rows=len(sub),prompt_tokens=tokens,feature_seconds=tokens/2639.563832)
    total=sum(v['feature_seconds'] for v in projection.values());head=.462147746*(len(historical_sub)+len(external_train))/240*4/5
    projection.update(label='Projection only, no execution authorized',total_feature_seconds=total,
        head_200_update_seconds_linear_scaling=head,head_budget_seconds=[1,5],
        classification_after_cached_features_seconds_per_dev=[.01,1],
        gpu_peak_GiB_expected=[3.56,4.5],gpu_reservation_GiB=6,
        warm_gpu_compute_minutes=(total+head+2)/60,
        provisioned_A10_minutes_with_setup=[10,20],historical_A10_hourly_usd=1.29,projected_A10_usd=[.215,.43],
        assumptions='Historical 227276 tokens / 86.103619569 seconds; head 200 updates / .462147746 seconds. Setup-inclusive 10-20 minutes is a planning range, not a bound. Historical price only, not current quote. No explanation generation or refusal-veto generation included.',
        reason_generation_note='Prior 48 reasons took 279.56 seconds; integrated evaluation requires a separate larger estimate.')
    write('runtime_projection.json',projection)
    experiment=dict(name='AUDITOR_EXTERNAL_RELATION_CLASSIFIER_V1',status='PREPARED_NOT_ADMITTED',execution_authorized=False,
        training_authorized=False,cloud_authorized=False,data_admitted=False,
        architecture=['existing frozen refusal veto','four-way substantive linear classifier','conditioned explanation'],
        classes=list(CLASSES),model_id=old['model']['model_id'],revision=old['model']['revision'],
        adapter_hashes=old['adapter_hashes'],asset_hashes=old['model']['asset_hashes'],
        representation='Same frozen base plus checkpoint-120 Auditor adapter; final prompt-token hidden state, dimension 3072, float32; no generation for feature extraction',
        input_policy='Only normalized input, original frozen prompt and chat template; no outer metadata or transformation fields',
        canonicalizer=dict(path='tools/auditor_linear_core.py',sha256=sha(ROOT/'tools/auditor_linear_core.py'),function='normalized_input'),
        standardization=dict(train_only=True,ddof=0,clamp=1e-6),
        proposed_head=dict(input_dim=3072,outputs=4,parameters=12292,updates=200,seed=7,optimizer='Adam',learning_rate=.01,weight_regularization=.001,initialization='zero'),
        train=dict(historical_substantive=192,external_substantive=len(external_train),combined_substantive=192+len(external_train)),
        dev=dict(primary_external=len(external_dev),secondary_historical_substantive=48,secondary_role='Distribution-shift diagnostic, not relabeled or merged into TRAIN'),
        holdout=dict(excluded=True,requires_separate_admission=True),
        classifier_gates=dict(macro_substantive_f1=.75,every_class_recall=.60),aspirational=dict(macro_substantive_f1=.80,every_class_recall=.70),
        integrated_gates=old['model']['selection_gates'],catastrophic_errors_allowed=0,
        fallback='Do not implement classifier LoRA here. Only reconsider after a separately admitted expanded-data frozen-head experiment fails.',
        hypothesis='Test labeled-data scarcity/structural coverage against frozen-representation limits; no precommitment to success.',
        admission_blockers=['length-sign shortcut inherent in specified quartet construction','below preferred 800 rows; limited independent document coverage'],
        required_next='Redesign or explicitly scope the deterministic contrast task before experiment admission; no execution with this quarantine release')
    write('experiment.json',experiment)
    from access import load_split
    denial={}
    for s in ('train','dev','holdout'):
        try:load_split(s,admission={'approved':True})
        except PermissionError:denial[s]=True
        else:raise AssertionError('Unadmitted data allowed')
    assert 'torch' not in sys.modules
    assert before==preserve()
    write('dry_run_evidence.json',dict(verdict='AUDITOR_EXTERNAL_RELATION_DATA_V1_NOT_READY',
        mechanical_integrity_checks_passed=True,readiness_passed=False,invalid_fixtures=fixture_results,
        deterministic_rebuild=True,reversed_input_rebuild=True,provenance_roundtrip_rows=len(rows),
        quartet_balance=all(v['rows']==len(rows)//4 for v in statistics['by_class'].values()),
        rendering_and_domain_balance=all(v['domains']==statistics['by_class']['MATCH']['domains'] and v['rendering_pairs']==statistics['by_class']['MATCH']['rendering_pairs'] for v in statistics['by_class'].values()),
        holdout_denial=denial,historical_preservation=before,
        merged_historical_train_unchanged=True,existing_insufficient_preserved=48,
        runtime_guards=dict(network_denied=True,subprocess_denied=True,weight_file_open_denied=True,protected_and_credential_paths_denied=True),
        torch_imported=False,model_inference=False,training=False,producer_execution=False,protected_access=False,cloud=False,paid_api=False,
        llm_labeling=False,per_row_agent_generation=False,folds1_to_4=False,full_pipeline=False,multi_round=False,
        limitation='Runtime guards cover this Python builder. They are not OS-wide attestation. HOLDOUT only had structural integrity/token/lexical checks, not predictions or baseline scoring.'))
    print(json.dumps(dict(rows=len(rows),quartets=len(rows)//4,split=statistics['by_split'],
        prompt=tokenstats['release_prompt_statistics'],verdict='AUDITOR_EXTERNAL_RELATION_DATA_V1_NOT_READY'),indent=2))

if __name__=='__main__':main()
