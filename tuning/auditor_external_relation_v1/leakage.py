"""Deterministic lexical grouping and metadata diagnostics; no fitting or embeddings."""
from collections import Counter, defaultdict
from conversion import digest
from validators import norm, words

THRESHOLD=.80

def shingles(text):
    w=words(text)
    return set(tuple(w[i:i+5]) for i in range(max(1,len(w)-4)))

def similarity(a,b):
    return len(a & b)/len(a | b) if a or b else 1.

class Groups:
    def __init__(self,keys): self.parent={k:k for k in keys}
    def root(self,k):
        while self.parent[k]!=k:
            self.parent[k]=self.parent[self.parent[k]];k=self.parent[k]
        return k
    def union(self,a,b):
        a,b=self.root(a),self.root(b)
        if a!=b:self.parent[max(a,b)]=min(a,b)

def cluster(documents,variants,doc_id_sets):
    g=Groups(documents); edges=[]
    for group in doc_id_sets:
        group=sorted(set(group))
        for k in group[1:]:g.union(group[0],k)
    # Underlying full documents and every prospective source/candidate participate.
    texts=[(k,'doc',v) for k,v in documents.items()]
    texts += [(k,'source_or_candidate',v) for k,vs in variants.items() for v in set(vs)]
    buckets=defaultdict(list)
    for k,kind,text in texts:buckets[norm(text)].append((k,kind))
    exact_edges=0
    for refs in buckets.values():
        for k,_ in refs[1:]:
            if g.root(refs[0][0])!=g.root(k):exact_edges+=1
            g.union(refs[0][0],k)
    # Sparse inverted index avoids comparing unrelated long documents.
    prepared=[(refs[0][0],refs[0][1],shingles(t)) for t,refs in sorted(buckets.items())]
    postings=defaultdict(list); pairs=Counter()
    for i,(_,_,ss) in enumerate(prepared):
        for sh in ss:
            for j in postings[sh]:pairs[(j,i)]+=1
            postings[sh].append(i)
    for (i,j),intersection in sorted(pairs.items()):
        a,ka,sa=prepared[i];b,kb,sb=prepared[j]
        sim=intersection/(len(sa)+len(sb)-intersection)
        if a!=b and sim>=THRESHOLD:
            g.union(a,b);edges.append(dict(a=a,b=b,similarity=sim,kind=[ka,kb]))
    return {k:g.root(k) for k in documents},dict(threshold=THRESHOLD,exact_document_merge_edges=exact_edges,near_duplicate_edges=edges,
        canonical_documents=len(documents),groups=len({g.root(k) for k in documents}))

def cross_split(rows,documents):
    entries={}
    for r in rows:
        for kind,text in [('source',r['transformation']['original_summary']),('candidate',r['transformation']['candidate']),('document',documents[r['provenance']['document_hash']])]:
            key=(r['split'],r['document_group'],kind,norm(text))
            entries[key]=shingles(text)
    items=list(entries.items()); maxsim=0.; pair=None; duplicate_pairs=0; suspicious=[]
    for i,(a,sa) in enumerate(items):
        for b,sb in items[i+1:]:
            if a[0]==b[0]:continue
            sim=similarity(sa,sb)
            duplicate_pairs+=a[3]==b[3]
            if sim>maxsim:
                maxsim=sim;pair=dict(left=list(a[:3]),right=list(b[:3]))
            if sim>=THRESHOLD:suspicious.append(dict(left=list(a[:3]),right=list(b[:3]),similarity=sim))
    return dict(exact_cross_split_duplicate_pairs=duplicate_pairs,max_cross_split_5gram_jaccard=maxsim,
                maximum_pair=pair,near_duplicate_pairs=suspicious,threshold=THRESHOLD,
                limitation='Lexical tests cannot prove semantic independence.')

def purity(rows,key):
    bins=defaultdict(Counter)
    for i,r in enumerate(rows):bins[str(key(i,r))][r['relation']]+=1
    return dict(oracle_bucket_accuracy=sum(max(v.values()) for v in bins.values())/len(rows) if rows else None,
                bins=len(bins),fully_deterministic=bool(rows) and all(len(v)==1 for v in bins.values()))

def shortcut_audit(rows):
    # Admission diagnostics only on TRAIN/DEV. HOLDOUT labels are never scored.
    result={'method':'Fixed rules and bucket purity only; no classifier fitted; HOLDOUT excluded.',
            'excluded_prompt_metadata':['example_id','lineage_id','document_key','document_group','domain','relation','provenance','transformation','lengths','split','rendering_pair','integrity'],
            'bucket_purity_interpretation':'Descriptive in-sample oracle upper bound, not held-out predictive accuracy. Sparse ID buckets can have high purity by chance; IDs are excluded from prompts. Only the predeclared length-sign rule reports predictive accuracy.'}
    for split in ('train','dev'):
        rs=[r for r in rows if r['split']==split]
        features={
          'id_last_hex':lambda i,r:int(r['example_id'][-1],16),
          'id_mod4':lambda i,r:int(r['example_id'],16)%4,
          'id_mod5':lambda i,r:int(r['example_id'],16)%5,
          'id_mod20':lambda i,r:int(r['example_id'],16)%20,
          'refs':lambda i,r:str(r['input']['required_refs']),
          'row_order_mod4':lambda i,r:i%4,
          'renderer':lambda i,r:r['rendering_pair'],
          'domain':lambda i,r:r['domain'],
          'source_length_20word_bin':lambda i,r:len(words(r['transformation']['original_summary']))//20,
          'candidate_length_20word_bin':lambda i,r:len(words(r['transformation']['candidate']))//20,
          'prompt_length_50token_bin':lambda i,r:r['lengths']['prompt_tokens']//50,
          'word_ratio_sign':lambda i,r:(len(words(r['transformation']['candidate']))>len(words(r['transformation']['original_summary'])))-(len(words(r['transformation']['candidate']))<len(words(r['transformation']['original_summary']))),
        }
        results={k:purity(rs,fn) for k,fn in features.items()}
        def predict(r):
            d=len(words(r['transformation']['candidate']))-len(words(r['transformation']['original_summary']))
            return 'MATCH' if d==0 else 'ADDITION' if d>0 else 'OMISSION'
        correct=sum(predict(r)==r['relation'] for r in rs)
        results['fixed_length_sign_rule']=dict(rows=len(rs),correct=correct,accuracy=correct/len(rs) if rs else None,
            rule='equal word count -> MATCH; positive delta -> ADDITION; negative delta -> OMISSION; never DIVERGENCE')
        result[split]=results
    result['id_assignment']='Four opaque slot hashes allocated without labels; independent per-lineage permutation assigns classes. No IDs enter prompts.'
    result['ref_assignment']='No external citations invented; empty lists for every class; existing canonicalizer reused.'
    result['order']='Global opaque-ID hash sort, independent of relation and upstream order.'
    result['known_blocker']='Whole-quartet content-preserving MATCH, deletion OMISSION, insertion ADDITION guarantee >=75% accuracy from word-count sign alone. Rebalancing complete quartets cannot remove this. Formatting padding would hide rather than eliminate the cue.'
    result['metadata_prompt_allowlist_pass']=True
    result['length_shortcut_pass']=False
    result['ready']=False
    return result
