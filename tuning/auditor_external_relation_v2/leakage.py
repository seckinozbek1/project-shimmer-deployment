"""Exact lexical connected components using a deterministic Jaccard prefix index."""
import math
from collections import Counter,defaultdict
from local_utils import norm,words,digest
THRESHOLD=.5
def shingles(t):
    w=words(t);return frozenset(tuple(w[i:i+5]) for i in range(max(1,len(w)-4)))
def similarity(a,b):return len(a&b)/len(a|b) if a or b else 1.
class Union:
    def __init__(self,n):self.p=list(range(n))
    def root(self,i):
        while self.p[i]!=i:self.p[i]=self.p[self.p[i]];i=self.p[i]
        return i
    def join(self,a,b):
        a,b=self.root(a),self.root(b)
        if a!=b:self.p[max(a,b)]=min(a,b)
def group(rows,historical):
    by_dataset=defaultdict(set)
    for r in rows:
        if 'dataset' in r:by_dataset[r['dataset']].update([norm(r['source']),norm(r['candidate'])])
    dataset_sets=list(by_dataset.values())
    cross_dataset_exact=len(set.intersection(*dataset_sets)) if len(dataset_sets)>1 else 0
    texts=sorted({norm(t) for r in rows for t in (r['source'],r['candidate'])}|{norm(t) for t in historical})
    ids={t:i for i,t in enumerate(texts)};u=Union(len(texts));ss=[shingles(t) for t in texts]
    for r in rows:u.join(ids[norm(r['source'])],ids[norm(r['candidate'])])
    frequency=Counter(sh for s in ss for sh in s);index=defaultdict(list);edges=0;comparisons=0
    for i,s in enumerate(ss):
        prefix=sorted(s,key=lambda x:(frequency[x],x))[:len(s)-math.ceil(THRESHOLD*len(s))+1]
        possible=set(j for sh in prefix for j in index[sh])
        for j in possible:
            if min(len(s),len(ss[j])) < THRESHOLD*max(len(s),len(ss[j])):continue
            comparisons+=1
            if similarity(s,ss[j])>=THRESHOLD:u.join(i,j);edges+=1
        for sh in prefix:index[sh].append(i)
    blocked={u.root(ids[norm(t)]) for t in historical}
    roots={u.root(i):digest(['lexical-group',texts[u.root(i)]]) for i in range(len(texts))}
    keep=[]
    for r in rows:
        k=u.root(ids[norm(r['source'])])
        if k not in blocked:r['group_id']=roots[k];keep.append(r)
    component_sources=defaultdict(set)
    for r in keep:
        if 'dataset' in r:component_sources[r['group_id']].add(r['dataset'])
    return keep,dict(threshold=THRESHOLD,unique_sentence_sides=len(texts),near_edges=edges,exact_similarity_comparisons=comparisons,
        paws_to_wikiatomic_exact_sentence_overlaps=cross_dataset_exact,paws_to_wikiatomic_shared_components=sum(len(v)>1 for v in component_sources.values()),
        historical_overlap_rows_excluded=len(rows)-len(keep),groups=len({r['group_id'] for r in keep}),
        algorithm='Global-frequency ordered prefix-filter candidates followed by exact 5-gram Jaccard; union sentence pairs, exact sides and >=0.50 near sides before split assignment. Tightened once after an initial 0.80 audit found cross-split similarity 0.555556.')
def audit(rows):
    sides={}
    for r in rows:
        for t in (r['source'],r['candidate']):sides[(r['split'],norm(t))]=shingles(t)
    items=list(sides.items());maximum=0.;exact=0;near=0
    for i,(a,sa) in enumerate(items):
        for b,sb in items[i+1:]:
            if a[0]==b[0]:continue
            exact+=a[1]==b[1];v=similarity(sa,sb);maximum=max(maximum,v);near+=v>=THRESHOLD
    return dict(cross_split_exact_sentence_pairs=exact,cross_split_near_pairs=near,max_cross_split_5gram_jaccard=maximum,
        unique_pairs=len({r['pair_id'] for r in rows}),unique_groups=len({r['group_id'] for r in rows}),
        limitation='Sentence lineage independence only; no Wikipedia article IDs supplied; lexical checks do not prove semantic independence.')
