"""Mechanical filters only; PAWS human labels and atomic tags determine relation."""
import re
from local_utils import norm,words,pair_key,digest,features

def text_reason(a,b):
    for t in (a,b):
        if not isinstance(t,str) or not t.strip():return 'empty_text'
        if not 8<=len(words(t))<=60:return 'lexical_length_outside_8_60'
        if re.search(r'<[^>]*>|__\w+__|\[\[|\]\]|\{\{|\}\}|https?://|REF-\d+|\ufffd',t):return 'placeholder_markup_or_reserved_text'
        if not re.match(r'[A-Z0-9"\u201c]',t.strip()) or not re.search(r'[.!?]["\u201d\u2019\s]*$',t):return 'sentence_boundary_shape'
        if any(t.count(x)!=t.count(y) for x,y in [('(',')'),('[',']'),('{','}')]):return 'unbalanced_delimiters'
    if norm(a)==norm(b):return 'identical_pair'
    return None

def paws(raw):
    assert set(raw)=={'id','sentence1','sentence2','label'} and raw['label'] in (0,1)
    a,b=raw['sentence1'],raw['sentence2'];reason=text_reason(a,b)
    if reason:return None,reason
    if len(words(a))==len(words(b)):return None,'equal_lexical_length'
    key=pair_key(a,b);want='shorter' if int(digest(['orientation',key]),16)%2 else 'longer'
    reversed_pair=features(a,b)['sign']!=want
    if reversed_pair:a,b=b,a
    return dict(pair_id=key,source=a,candidate=b,relation='MATCH' if raw['label']==1 else 'DIVERGENCE',
                dataset='PAWS-Wiki Labeled Final',features=features(a,b),
                provenance=dict(upstream_row_id=raw['id'],upstream_split='train',raw_row_hash=digest(raw),
                human_label=raw['label'],orientation_reversed=reversed_pair,operation=None)),None

def atomic(raw):
    assert set(raw)=={'id','src','tgt','changed','src_tag','yin_before','yin_after'}
    tags=raw['src_tag'];before=raw['yin_before'];after=raw['yin_after']
    if len(tags)!=len(before) or len(tags)!=len(after):return None,'alignment_length_mismatch'
    ops=set(tags)-{'equal'}
    if ops not in ({'insert'},{'delete'}):return None,'not_single_operation'
    op=next(iter(ops));positions=[i for i,t in enumerate(tags) if t==op]
    if positions!=list(range(min(positions),max(positions)+1)):return None,'noncontiguous_edit'
    changed=[]
    for tag,a,b in zip(tags,before,after):
        if tag=='equal' and (a!=b or a=='__EMPTY__'):return None,'hidden_equal_edit'
        if tag=='insert':
            if a!='__EMPTY__' or b=='__EMPTY__':return None,'invalid_insertion_alignment'
            changed.append(b)
        if tag=='delete':
            if b!='__EMPTY__' or a=='__EMPTY__':return None,'invalid_deletion_alignment'
            changed.append(a)
    if [t for t in before if t!='__EMPTY__']!=raw['src'] or [t for t in after if t!='__EMPTY__']!=raw['tgt'] or changed!=raw['changed']:
        return None,'exact_reconstruction_failed'
    span=' '.join(changed);sw=words(span)
    function_words=set('a an the of to in on at by for and or but as is was were be been being it its this that these those he she they their with from than'.split())
    if not sw or all(w in function_words for w in sw):return None,'non_substantive_edit_span'
    a,b=' '.join(raw['src']),' '.join(raw['tgt']);reason=text_reason(a,b)
    if reason:return None,reason
    f=features(a,b)
    if f['sign']!=('longer' if op=='insert' else 'shorter'):return None,'nonlexical_or_wrong_sign'
    return dict(pair_id=pair_key(a,b),source=a,candidate=b,relation='ADDITION' if op=='insert' else 'OMISSION',
        dataset='WikiAtomicEdits / PEER published sample',features=f,
        provenance=dict(upstream_row_id=raw['id'],upstream_split='train',raw_row_hash=digest(raw),operation=op,
            orientation_reversed=False,changed_tokens=changed,alignment_start=min(positions),
            rendering='Single-space join of published token arrays; no token alteration')),None
