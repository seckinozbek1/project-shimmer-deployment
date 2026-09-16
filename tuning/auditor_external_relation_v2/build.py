"""Offline V2 preparation; human labels/edits only, never model fitting."""
import sys,hashlib,json,zipfile
from collections import Counter,defaultdict
from local_utils import *
import filters
import leakage
import split as splitter
import shortcut_audit
from tokenizer_check import load,CEILING

def guard():
    def audit(event,args):
        if event in {'socket.connect','socket.getaddrinfo','subprocess.Popen','os.system'}:raise PermissionError('Offline build denies network/process execution')
        if event=='open' and isinstance(args[0],(str,bytes)):
            p=str(args[0]).replace('\\','/').lower();mode=args[1]
            if any(s in p for s in ['/benchmark/keys/','/api_keys/','protected_targets','protected_holdout']):raise PermissionError('Protected path denied')
            if p.endswith(('.safetensors','.bin','.pt','.pth','.npy','.npz')):raise PermissionError('Weight/feature files denied')
            if '/auditor_external_relation_v1/' in p and isinstance(mode,str) and any(c in mode for c in 'wax+'):raise PermissionError('V1 mutation denied')
    sys.addaudithook(audit)

def preserve():
    v1=ROOT/'tuning/auditor_external_relation_v1';f=read(v1/'freeze.json')
    assert f['verdict']=='AUDITOR_EXTERNAL_RELATION_DATA_V1_NOT_READY'
    for path,h in f['files'].items():assert sha(ROOT/path)==h,'V1 changed: '+path
    assert not read(v1/'experiment.json')['data_admitted'] and not read(v1/'holdout_receipt.json')['consumed']
    records={'v1_freeze_sha256':sha(v1/'freeze.json'),'v1_verified_files':len(f['files'])}
    for name in ['auditor_linear_probe_run','auditor_canonical_tuning_run','producer_tuning_v3_run']:
        m=read(ROOT/'docs/fix'/name/'EVIDENCE_MANIFEST.json')
        for path,entry in m['text_files'].items():assert sha(ROOT/path)==entry['sha256']
        records[name]=len(m['text_files'])
    return records

def acquire_local():
    import pyarrow.parquet as pq
    downloads=read(HERE/'download_manifest.json')
    for v in downloads.values():assert sha(ROOT/v['path'])==v['sha256']
    schemas={};counts={}
    for s,n in [('train',49401),('dev',8000),('test',8000)]:
        f=pq.ParquetFile(RAW/f'paws-{s}.parquet');assert f.metadata.num_rows==n
        assert f.schema.names==['id','sentence1','sentence2','label']
        schemas[s]=str(f.schema_arrow);counts[s]=f.metadata.num_rows
    paws=pq.read_table(RAW/'paws-train.parquet').to_pylist()
    archive=read(RAW/'peer-zenodo.json')
    assert archive['metadata']['version']=='v1.0' and archive['metadata']['license']['id']=='cc-by-4.0'
    assert hashlib.md5((RAW/'PEER.zip').read_bytes()).hexdigest()=='8bca47b0019ce1ec33d332a73d7b3b75'
    with zipfile.ZipFile(RAW/'PEER.zip') as z:
        raw=z.read('PEER/edits/insertions_deletions.jsonl')
        assert hashlib.sha256(raw).hexdigest()==sha(RAW/'wikiatomic-peer.jsonl')
        ids={int(x) for x in z.read('PEER/splits/insertions_deletions.train.txt').splitlines()}
    atomic=[json.loads(x) for x in raw.splitlines()];assert len(atomic)==104000 and len(ids)==83200
    assert len({r['id'] for r in atomic})==104000
    tags=Counter('insert' if 'insert' in r['src_tag'] else 'delete' for r in atomic)
    assert dict(tags)=={'insert':52000,'delete':52000}
    source=dict(paws=dict(repository='google-research-datasets/paws',revision='161ece9501cf0a11f3e48bd356eaa82de46d6a09',
        original_repository_revision='02b29f3af1143620d1b7f352247e65c0bdd2ec18',counts=counts,schemas=schemas,
        license='Google custom unrestricted-use dataset notice; retained verbatim in licenses/paws-LICENSE.txt',
        citation='Zhang, Yuan; Baldridge, Jason; He, Luheng. PAWS: Paraphrase Adversaries from Word Scrambling. NAACL 2019.',
        policy='Only official TRAIN rows are parsed for conversion. Official DEV/TEST downloaded and hashed; only Parquet footer counts/schema inspected, no label columns read. No QQP, swap-only or noisy data.'),
        wikiatomic=dict(original_repository='google-research-datasets/wiki-atomic-edits',original_revision='1f6769f2f9d93b6bf5acb091eb509b2be36e8e79',
            source_archive='https://zenodo.org/records/4478267',doi='10.5281/zenodo.4478267',version='v1.0',
            member='PEER/edits/insertions_deletions.jsonl',member_sha256=hashlib.sha256(raw).hexdigest(),rows=104000,
            operation_counts=dict(tags),eligible_source_split_rows=83200,schema={k:type(v).__name__ for k,v in atomic[0].items()},
            derivation='PEER authors sampled approximately 150K English WikiAtomicEdits edits; cleaning retained 104K. We use only published PEER TRAIN IDs. The archive MD5 matches Zenodo; no arbitrary mirror data used.',
            original_citation='Faruqui, Manaal; Pavlick, Ellie; Tenney, Ian; Das, Dipanjan. WikiAtomicEdits. EMNLP 2018. https://aclanthology.org/D18-1028/',
            sample_citation='Marrese-Taylor, Edison; Reid, Machel; Matsuo, Yutaka. Variational Inference for Learning Representations of Natural Language Edits. AAAI 2021. https://doi.org/10.1609/aaai.v35i15.17598',
            license_records=dict(upstream='CC-BY-SA-4.0 notice in official README (contains unrelated Query-wellformedness wording)',sample_archive='CC-BY-4.0 in Zenodo metadata',hf_card='unknown; used only for provenance documentation, not licensing authority'),
            license_handling='Retain both upstream ShareAlike and sample attribution notices; do not silently relicense under repository code terms or claim the notices are equivalent.'),
        original_download_failures=dict(paws='Official GCS object returned 403 AccessDenied',wikiatomic='Both official English GCS objects returned 403 AccessDenied'),
        archive_other_members='Other PEER datasets were neither extracted nor inspected; only the requested WikiAtomic component was read')
    source['download_manifest_sha256']=sha(HERE/'download_manifest.json')
    write('source_manifest.json',source)
    return paws,[r for r in atomic if r['id'] in ids],source

def statistics(rows):
    out={}
    for c in CLASSES:
        rs=[r for r in rows if r['relation']==c]
        out[c]=dict(rows=len(rs),source_datasets=dict(Counter(r['dataset'] for r in rs)),signs=dict(Counter(r['features']['sign'] for r in rs)),
            source_words=describe([r['features']['source_words'] for r in rs]),candidate_words=describe([r['features']['candidate_words'] for r in rs]),
            word_ratio=describe([r['features']['word_ratio'] for r in rs]),character_ratio=describe([r['features']['character_ratio'] for r in rs]),
            prompt_tokens=describe([r['lengths']['prompt_tokens'] for r in rs]))
    return dict(total=len(rows),by_class=out,by_split={s:dict(rows=len(rs),classes=dict(Counter(r['relation'] for r in rs)),
        lineages=len({r['group_id'] for r in rs})) for s in ['train','dev','holdout'] for rs in [[r for r in rows if r['split']==s]]},
        unique_lineages=len({r['group_id'] for r in rows}),style='Wikipedia-derived tokenized sentences, identical plain transport wrapper; article/domain metadata unavailable')

def main():
    guard();preserved=preserve();print('Preservation verified',flush=True)
    paws,atomic,source=acquire_local();print('Source identities verified',flush=True)
    rows=[];rejected={}
    for name,pool,convert in [('paws',paws,filters.paws),('wikiatomic',atomic,filters.atomic)]:
        counter=Counter()
        for raw in pool:
            row,reason=convert(raw)
            if reason:counter[reason]+=1
            else:rows.append(row)
        rejected[name]=dict(input_rows=len(pool),reasons=dict(counter),eligible=len(pool)-sum(counter.values()))
    bypair=defaultdict(list)
    for r in rows:bypair[r['pair_id']].append(r)
    conflict={k for k,rs in bypair.items() if len({r['relation'] for r in rs})>1}
    rows=[sorted(rs,key=lambda r:digest(r['provenance']))[0] for k,rs in sorted(bypair.items()) if k not in conflict]
    rejected['pair_dedup']=dict(conflicting_pairs_excluded=len(conflict),conflicting_rows_excluded=sum(len(bypair[k]) for k in conflict),
        duplicate_or_reversed_extra_rows=sum(len(rs)-1 for rs in bypair.values()),remaining_pairs=len(rows))
    historical=read(ROOT/'tuning/auditor_canonical_execution/dataset.json');hs=read(ROOT/'tuning/auditor_canonical_execution/split.json')
    htexts=[t for r in historical for t in [r['input']['extraction']]+[s['text'] for s in r['input']['source_spans']]]
    print('Grouping '+str(len(rows))+' eligible pairs',flush=True)
    rows,grouping=leakage.group(rows,htexts)
    write('pool_group_registry.json',{r['pair_id']:dict(group=r['group_id'],split=splitter.assign(r['group_id'])) for r in rows})
    selected,selection=splitter.select(rows)
    again,selection_again=splitter.select(list(reversed(rows)))
    assert digest(selected)==digest(again) and selection==selection_again
    print('Selected '+str(len(selected))+' rows; tokenizer dry-run',flush=True)
    lengths=load();overflow=[]
    raw_indices={'paws':{r['id']:r for r in paws},'wikiatomic':{r['id']:r for r in atomic}}
    for r in selected:
        r['example_id']=digest(['opaque-content-identity-v2',r['pair_id']])
        r['lineage_id']=r['group_id'];r['role']='auditor';r['input']=model_input(r['source'],r['candidate'])
        r['lengths']=lengths(r)
        r['provenance']['source_record']='paws' if r['dataset'].startswith('PAWS') else 'wikiatomic'
        raw=raw_indices[r['provenance']['source_record']][r['provenance']['upstream_row_id']]
        converted,reason=(filters.paws if r['provenance']['source_record']=='paws' else filters.atomic)(raw)
        assert not reason and digest(raw)==r['provenance']['raw_row_hash']
        assert all(converted[k]==r[k] for k in ['source','candidate','relation','pair_id','features'])
        r['provenance']['source_file']='paws-train.parquet' if r['provenance']['source_record']=='paws' else 'PEER.zip:PEER/edits/insertions_deletions.jsonl'
        r['provenance']['source_manifest_sha256']=sha(HERE/'source_manifest.json')
        r['provenance']['license_record']=source[r['provenance']['source_record']].get('license',source['wikiatomic']['license_records'])
        if r['lengths']['prompt_tokens']>CEILING:overflow.append(r['example_id'])
    assert not overflow,'Token overflow: no truncation or partial release allowed'
    assert len(selected)<=3000 and len({r['group_id'] for r in selected})==len(selected)
    print('Auditing cross-split lexical overlap',flush=True)
    lex=leakage.audit(selected);assert lex['cross_split_exact_sentence_pairs']==lex['cross_split_near_pairs']==0
    audits=shortcut_audit.run(selected)
    assert audits['word_sign_gate_pass'],'Deterministic balancing failed; NOT_READY, no further tuning'
    stats=statistics(selected);write('statistics.json',stats)
    write('rejection_stats.json',rejected);write('selection_evidence.json',selection)
    write('leakage_audit.json',dict(pool_grouping=grouping,final_cross_split=lex));write('shortcut_audit.json',audits)
    jsonl('external_four_way_view.jsonl',selected)
    htrain=[r for r in historical if r['example_id'] in hs['train'] and r['relation']!='INSUFFICIENT_EVIDENCE']
    hdev=[r for r in historical if r['example_id'] in hs['validation'] and r['relation']!='INSUFFICIENT_EVIDENCE']
    exttrain=[r for r in selected if r['split']=='train'];extdev=[r for r in selected if r['split']=='dev']
    assert len(htrain)==192 and len(hdev)==48
    jsonl('merged_four_way_train.jsonl',htrain+exttrain)
    write('split.json',{s:[r['example_id'] for r in selected if r['split']==s] for s in ['train','dev','holdout']})
    challenges={}
    for sign,classes in [('shorter',['MATCH','DIVERGENCE','OMISSION']),('longer',['MATCH','DIVERGENCE','ADDITION'])]:
        pools={c:sorted([r for r in extdev if r['relation']==c and r['features']['sign']==sign],key=lambda r:digest(['challenge',r['example_id']])) for c in classes}
        n=min(len(v) for v in pools.values());challenges[sign]=dict(classes=classes,rows=3*n,per_class=n,
            example_ids=[r['example_id'] for c in classes for r in pools[c][:n]],macro_f1_gate=.70,
            note='Sign constant; provenance/style confounds may remain, so success is not alone proof of semantic reasoning.')
    write('dev_challenges.json',challenges)
    write('holdout_receipt.json',dict(consumed=False,evaluations=0,admitted=False,separate_authorization_required=True))
    token=describe([r['lengths']['prompt_tokens'] for r in selected]);write('tokenizer_evidence.json',dict(statistics=token,overflow=0,ceiling=CEILING,truncation=False))
    old=read(ROOT/'tuning/auditor_linear_probe/experiment.json')
    train_tokens=sum(lengths(r)['prompt_tokens'] for r in htrain)+sum(r['lengths']['prompt_tokens'] for r in exttrain)
    dev_tokens=sum(r['lengths']['prompt_tokens'] for r in extdev);hist_tokens=sum(lengths(r)['prompt_tokens'] for r in hdev)
    seconds=(train_tokens+dev_tokens+hist_tokens)/2639.563832
    projection=dict(label='Projection only; no compute authorized',feature_seconds=seconds,train_feature_seconds=train_tokens/2639.563832,
        external_dev_feature_seconds=dev_tokens/2639.563832,historical_dev_feature_seconds=hist_tokens/2639.563832,
        head_seconds=.462147746*(192+len(exttrain))/240*.8,planning_A10_minutes=[15,30],historical_hourly_usd=1.29,
        planning_A10_usd=[.3225,.645],expected_peak_GPU_GiB=[3.56,4.5],
        assumptions='Historical feature throughput 227276 tokens / 86.103619569s. Head scaling from .462147746s / 240 rows / 200 updates. No explanation or refusal generation. Setup and transfers uncertain; historical price is not a current quote.')
    write('runtime_projection.json',projection)
    experiment=dict(name='AUDITOR_EXTERNAL_RELATION_CLASSIFIER_V2',execution_authorized=False,training_authorized=False,cloud_authorized=False,
        data_admitted=False,status='PREPARED_NOT_ADMITTED',architecture=['frozen historical refusal veto','four-way substantive linear head','conditioned explanation'],
        first_test='CLASSIFICATION_ONLY; no explanation or veto generation in this first measurement; refusal mechanism remains separate and frozen',
        model_id=old['model']['model_id'],revision=old['model']['revision'],adapter_hashes=old['adapter_hashes'],asset_hashes=old['model']['asset_hashes'],
        representation='Same frozen checkpoint-120 Auditor final prompt-token hidden state, 3072 float32 features',
        head=dict(outputs=4,parameters=12292,seed=7,updates=200,optimizer='Adam',learning_rate=.01,regularization=.001,initialization='zero'),
        standardization=dict(train_only=True,ddof=0,clamp=1e-6),classes=list(CLASSES),
        train=dict(historical=192,external=len(exttrain),total=192+len(exttrain)),dev=dict(external=len(extdev),historical_secondary=48),
        gates=dict(external_macro_f1=.75,every_class_recall=.60,shorter_challenge_macro_f1=.70,longer_challenge_macro_f1=.70),
        aspirational=dict(macro_f1=.80,every_class_recall=.70),historical_integrated_gates=old['model']['selection_gates'],
        holdout_excluded=True,lora_fallback_authorized=False,explanation_generation_authorized=False,
        limitation='V2 passes the word-sign gate but source-family confounding remains; not admitted under the no-known-source-shortcut readiness condition.')
    write('experiment.json',experiment)
    assert preserve()==preserved and 'torch' not in sys.modules
    write('dry_run_evidence.json',dict(verdict='AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY',mechanical_checks_passed=True,
        source_shortcut_gate_pass=False,word_sign_gate_pass=audits['word_sign_gate_pass'],deterministic_reversed_pool_rebuild=True,
        preservation=preserved,v1_rows_used=0,training=False,model_inference=False,weights_opened=False,cloud=False,protected_access=False,
        human_labels_only=True,holdout_consumed=False,upstream_paws_test_labels_read=False,upstream_paws_dev_labels_read=False,
        historical_train_rows_unchanged=True,provenance_roundtrip_rows=len(selected),prohibited_runtime_paths_guarded=True))
    print(json.dumps(dict(rows=len(selected),split=stats['by_split'],tokens=token,word_sign_dev=audits['dev']['fixed_word_sign'],projection=projection),indent=2))

if __name__=='__main__':main()
