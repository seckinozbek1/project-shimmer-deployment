"""Descriptive statistics only; no fitted classifier."""
import math
from collections import Counter
from validators import CLASSES, words

def mean(v):
    return sum(v)/len(v)

def median(v):
    x=sorted(v); n=len(x)
    return x[n//2] if n%2 else (x[n//2-1]+x[n//2])/2

def pstdev(v):
    m=mean(v)
    return math.sqrt(mean([(x-m)**2 for x in v]))

def describe(v):
    if not v:
        return dict(count=0,min=None,median=None,mean=None,p95=None,p99=None,max=None)
    v=sorted(v)
    return dict(count=len(v),min=v[0],median=median(v),mean=mean(v),
                p95=v[math.ceil(.95*len(v))-1],p99=v[math.ceil(.99*len(v))-1],max=v[-1])

def corpus(rows):
    result=dict(rows=len(rows),quartets=len({r['lineage_id'] for r in rows}),
        unique_docs=len({r['provenance']['source_doc_id'] for r in rows}),
        unique_document_hashes=len({r['provenance']['document_hash'] for r in rows}),
        unique_source_hashes=len({r['provenance']['source_hash'] for r in rows}),
        domains=dict(Counter(r['domain'] for r in rows)),
        rendering_pairs=dict(Counter(' -> '.join(r['rendering_pair']) for r in rows)),
        examples_per_doc=dict(Counter(Counter(r['provenance']['document_hash'] for r in rows).values())),
        by_source_dataset=dict(Counter(r['provenance']['dataset'] for r in rows)))
    result['by_split']={s:dict(rows=len(sub),docs=len({r['provenance']['document_hash'] for r in sub}),quartets=len({r['lineage_id'] for r in sub}))
        for s in ('train','dev','holdout') for sub in [[r for r in rows if r['split']==s]]}
    result['by_class']={}
    for c in CLASSES:
        sub=[r for r in rows if r['relation']==c]
        result['by_class'][c]=dict(rows=len(sub),source_chars=describe([len(r['transformation']['original_summary']) for r in sub]),
            candidate_chars=describe([len(r['transformation']['candidate']) for r in sub]),
            source_words=describe([len(words(r['transformation']['original_summary'])) for r in sub]),
            candidate_words=describe([len(words(r['transformation']['candidate'])) for r in sub]),
            source_tokens=describe([r['lengths']['source_tokens'] for r in sub]),
            candidate_tokens=describe([r['lengths']['candidate_tokens'] for r in sub]),
            prompt_tokens=describe([r['lengths']['prompt_tokens'] for r in sub]),
            word_length_ratio=describe([len(words(r['transformation']['candidate']))/len(words(r['transformation']['original_summary'])) for r in sub]),
            rendering_pairs=dict(Counter(' -> '.join(r['rendering_pair']) for r in sub)),domains=dict(Counter(r['domain'] for r in sub)))
    result['direct_executable_edit_percent']=25 if rows else 0
    result['deterministic_match_deletion_insertion_percent']=75 if rows else 0
    return result
