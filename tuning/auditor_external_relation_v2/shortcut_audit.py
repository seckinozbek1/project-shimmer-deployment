"""Fixed metadata diagnostics only. Never fit a model or score HOLDOUT."""
from collections import defaultdict,Counter
from local_utils import CLASSES

def purity(rows,key):
    bins=defaultdict(Counter)
    for i,r in enumerate(rows):bins[str(key(i,r))][r['relation']]+=1
    return dict(oracle_bucket_purity=sum(max(c.values()) for c in bins.values())/len(rows),
        bins=len(bins),deterministically_identifies_all_classes=all(len(c)==1 for c in bins.values()))
def run(rows):
    out={}
    for split in ['train','dev']:
        rs=[r for r in rows if r['split']==split]
        keys={
            'word_sign':lambda i,r:r['features']['sign'],
            'source_words_10bin':lambda i,r:r['features']['source_words']//10,
            'candidate_words_10bin':lambda i,r:r['features']['candidate_words']//10,
            'word_ratio_005bin':lambda i,r:int(r['features']['word_ratio']/.05),
            'character_ratio_005bin':lambda i,r:int(r['features']['character_ratio']/.05),
            'source_dataset':lambda i,r:r['dataset'],
            'source_dataset_and_sign':lambda i,r:(r['dataset'],r['features']['sign']),
            'row_mod4':lambda i,r:i%4,'row_mod5':lambda i,r:i%5,
            'id_mod4':lambda i,r:int(r['example_id'],16)%4,'id_mod5':lambda i,r:int(r['example_id'],16)%5,
            'id_mod20':lambda i,r:int(r['example_id'],16)%20,
            'punctuation_counts':lambda i,r:(r['features']['source_punctuation']//3,r['features']['candidate_punctuation']//3),
        }
        out[split]={name:purity(rs,key) for name,key in keys.items()}
        rules={
            'fixed_word_sign':lambda i,r:'OMISSION' if r['features']['sign']=='shorter' else 'ADDITION' if r['features']['sign']=='longer' else 'MATCH',
            'fixed_ratio_threshold':lambda i,r:'OMISSION' if r['features']['word_ratio']<.95 else 'ADDITION' if r['features']['word_ratio']>1.05 else 'MATCH',
            'fixed_source_dataset':lambda i,r:'MATCH' if r['dataset'].startswith('PAWS') else 'OMISSION',
            'fixed_source_and_sign_oracle':lambda i,r:'MATCH' if r['dataset'].startswith('PAWS') else 'OMISSION' if r['features']['sign']=='shorter' else 'ADDITION',
            'fixed_id_mod4':lambda i,r:CLASSES[int(r['example_id'],16)%4],
            'fixed_row_mod4':lambda i,r:CLASSES[i%4],
        }
        for name,rule in rules.items():out[split][name]=dict(accuracy=sum(rule(i,r)==r['relation'] for i,r in enumerate(rs))/len(rs),rows=len(rs))
    out['word_sign_gate_pass']=out['dev']['fixed_word_sign']['accuracy']<=.55
    out['rebalance_retries']=0
    out['method']='Predeclared rules plus descriptive oracle bin purity; no classifier fitted. HOLDOUT excluded. Bin purity is not held-out accuracy.'
    out['source_confounding']='Dataset alone identifies the two-class source family; dataset plus sign identifies atomic classes and reaches 75% with arbitrary PAWS tie-breaking. Dataset metadata is not present in prompts, but this remains a known provenance/source-family confound. No claim of source independence.'
    out['prompt_metadata_excluded']=True
    out['source_shortcut_gate_pass']=False
    return out
