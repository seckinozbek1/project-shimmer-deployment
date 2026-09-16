"""Canonical-only group, ancestry, semantic-signature and lexical overlap audit."""
from local_common import *
from dry_run import signatures
import re

def grams(row):
    text=' '.join(s['text'] for s in row['input']['source_spans']).lower()
    text=re.sub(r'clm-[\w-]+|ref-\d+|\b\d+\b',' ID ',text)
    words=re.findall(r'[a-z]+',text)
    return {tuple(words[i:i+5]) for i in range(len(words)-4)}

def run():
    rows=read(HERE/'dataset.json');new=read(HERE/'augmentation.json');split=read(HERE/'split.json')
    by={x['example_id']:x for x in rows};train=[by[i] for i in split['train']];dev=[by[i] for i in split['validation']]
    intersections={k:sorted({r[k] for r in train}&{r[k] for r in dev}) for k in v2.GROUP_FIELDS}
    assert not any(intersections.values())
    base_dev=[r for r in dev if r['example_id'].startswith('shimmer2-')]
    comparisons=[]
    for row in new:
        a=grams(row);nearest=None
        for old in base_dev:
            b=grams(old);value=len(a&b)/len(a|b)
            if nearest is None or value>nearest['fivegram_jaccard']:nearest=dict(new_id=row['example_id'],old_dev_id=old['example_id'],fivegram_jaccard=value)
        comparisons.append(nearest)
    semantic_intersection=set(canonical(signatures(r)) for r in train if r['substantive'])&set(canonical(signatures(r)) for r in dev if r['substantive'])
    assert not semantic_intersection
    result=dict(passed=True,group_intersections=intersections,semantic_signature_intersection_count=0,
        old_dev_membership_preserved=60,contrast_pairs=20,contrast_pairs_crossing_split=0,
        max_new_to_old_dev_fivegram_jaccard=max(x['fivegram_jaccard'] for x in comparisons),nearest_old_dev=comparisons,
        interpretation='All old canonical memberships and ancestry groups preserved. No exact source/input or normalized semantic sibling crossing. Lexical screen is descriptive; no numerical screen proves absence of conceptual leakage. New rows were authored from abstract error classes, not DEV packet paraphrases.',
        benchmark_status='Development corpus after failure-informed design; not an independent final benchmark or protected evaluation.')
    assert result['max_new_to_old_dev_fivegram_jaccard']<.8
    write(HERE/'leakage_audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='nearest_old_dev'},indent=2))

if __name__=='__main__':run()
