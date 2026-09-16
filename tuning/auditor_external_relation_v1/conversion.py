"""Pure quartet construction; IDs allocated before independently permuted labels."""
import hashlib
import json
import random
from rendering import pair, render, reverse
from validators import CLASSES, candidates, norm, validate

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def lineage(row):
    return digest(['Salesforce/summexecedit',row['sample_id'],digest(row)])

def document_key(row):
    return digest(['Salesforce/summexecedit',row['doc_id'],norm(row['doc'])])

def quartet(row, provenance, split, group):
    lin=lineage(row); styles=pair(lin)
    labels=list(CLASSES)
    random.Random(int(digest(['assignment',lin]),16)).shuffle(labels)
    out=[]
    for slot,label in enumerate(labels):
        source=row['original_summary']; candidate=candidates(row)[label]
        validate(row,label,source,candidate)
        value=dict(role='auditor',production_contract='semantic-task-v1',delivery_complete=True,
                   source_spans=[dict(alias='s0',text=render(source,styles[0]))],extraction=render(candidate,styles[1]),
                   context_only_spans=[],required_refs=[],supplied_refs=[],routed_rules=[])
        assert reverse(value['source_spans'][0]['text'],styles[0]) == source
        assert reverse(value['extraction'],styles[1]) == candidate
        out.append(dict(example_id=digest(['opaque-id',lin,slot]),lineage_id=lin,
                        document_key=document_key(row),document_group=group,split=split,role='auditor',
                        relation=label,domain=row['domain'],rendering_pair=list(styles),input=value,
                        provenance=provenance,transformation=dict(original_summary=source,
                        original_text=row['original_text'],replace_text=row['replace_text'],
                        edited_summary=row['edited_summary'],candidate=candidate),
                        integrity=dict(source_utf8_sha256=hashlib.sha256(source.encode()).hexdigest(),
                            candidate_utf8_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
                            normalized_source_hash=digest(norm(source)),normalized_candidate_hash=digest(norm(candidate)))))
    return out
