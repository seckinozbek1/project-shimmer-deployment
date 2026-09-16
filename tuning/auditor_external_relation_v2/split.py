"""Group-first split and common length-stratum matching, with no text fabrication."""
from collections import defaultdict,Counter
from local_utils import digest,stratum

def assign(group):
    n=int(digest(['split-v2',group]),16)%100
    return 'train' if n<80 else 'dev' if n<90 else 'holdout'

def select(rows):
    pools=defaultdict(lambda:defaultdict(list))
    for r in sorted(rows,key=lambda r:digest(['selection',r['pair_id']])):
        r['split']=assign(r['group_id'])
        pools[(r['split'],r['features']['sign'])][(stratum(r),r['relation'])].append(r)
    selected=[];used=set();evidence={}
    for split,wanted in [('train',200),('dev',25),('holdout',25)]:
        for sign,atomic in [('shorter','OMISSION'),('longer','ADDITION')]:
            pool=pools[(split,sign)];bins=sorted({b for b,c in pool},key=lambda b:digest(['bin-order',b]));units=0;bin_counts=Counter()
            # Round-robin over common ratio/shorter-side-length strata avoids a single easy bin.
            while units<wanted:
                changed=False
                for b in bins:
                    chosen=[];local=set()
                    for cls in ['MATCH','DIVERGENCE',atomic,atomic]:
                        options=pool[(b,cls)]
                        while options and (options[-1]['group_id'] in used or options[-1]['group_id'] in local):options.pop()
                        if not options:break
                        r=options.pop();chosen.append(r);local.add(r['group_id'])
                    if len(chosen)!=4:
                        for r in chosen:pool[(b,r['relation'])].append(r)
                        continue
                    selected.extend(chosen);used.update(local);units+=1;bin_counts[str(b)]+=1;changed=True
                    if units==wanted:break
                if not changed:break
            evidence[split+'_'+sign]=dict(target_units=wanted,units=units,strata=dict(bin_counts))
    selected.sort(key=lambda r:digest(['opaque-row-order',r['pair_id']]))
    return selected,evidence
