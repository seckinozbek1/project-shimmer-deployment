"""Conservative mechanical acceptance, never a semantic model or upstream-label map."""
import re
import unicodedata

CLASSES = ('MATCH', 'DIVERGENCE', 'OMISSION', 'ADDITION')

def norm(text):
    return ' '.join(unicodedata.normalize('NFKC', text).casefold().split())

def words(text):
    return re.findall(r"\w+(?:['’-]\w+)*", norm(text))

def subsequence(a, b):
    it = iter(b)
    return all(any(x == y for y in it) for x in a)

def sentence(text):
    t = text.strip()
    return (len(words(t)) >= 5 and bool(re.match(r'[A-Z0-9]', t))
            and t[-1:] in '.!?' and '\n' not in t
            and all(t.count(a) == t.count(b) for a,b in [('(',')'),('[',']'),('{','}')]))

def check_base(row):
    s,a,b,t = (row[k] for k in ('original_summary','original_text','replace_text','edited_summary'))
    if any(not x.strip() or norm(x) in {'n/a','none','null'} for x in (s,a,b,t)):
        return 'missing_or_placeholder_span'
    if s.count(a) != 1:
        return 'source_span_not_unique'
    if s.replace(a,b,1) != t:
        return 'edit_not_exactly_reproduced'
    if norm(a) == norm(b) or words(a) == words(b):
        return 'normalization_identical_or_noncontent_edit'
    if subsequence(words(a),words(b)) or subsequence(words(b),words(a)):
        return 'pure_insertion_deletion_or_nested_content'
    i = s.index(a); end = i+len(a)
    if (not sentence(a) or not sentence(b) or a != a.strip() or b != b.strip()
        or (s[:i].strip() and not re.search(r'[.!?]\s+$',s[:i]))
        or (s[end:] and not s[end].isspace())):
        return 'not_complete_sentence_replacement'
    omitted = (s[:i]+s[end:]).strip()
    if not sentence(omitted):
        return 'omission_no_well_formed_remainder'
    # Reject obvious dangling anaphora after deleting a complete sentence.
    if re.match(r'(?i)^(it|its|this|that|these|those|he|she|they|their|his|her|however|therefore|also|furthermore)\b',omitted):
        return 'omission_dangling_referent_risk'
    if norm(b) in norm(s):
        return 'replacement_already_present'
    if re.search(r'REF-\d+|<\|[^>]+\|>',s+b):
        return 'reserved_transport_text'
    return None

def candidates(row):
    s,a,b,t = (row[k] for k in ('original_summary','original_text','replace_text','edited_summary'))
    i=s.index(a); end=i+len(a)
    return {'MATCH':s, 'DIVERGENCE':t, 'OMISSION':s[:i]+s[end:],
            'ADDITION':s[:end]+' '+b+s[end:]}

def validate(row, relation, source, candidate):
    reason=check_base(row)
    if reason:
        raise ValueError(reason)
    if relation not in CLASSES or source != row['original_summary']:
        raise ValueError('source_or_class_changed')
    expected=candidates(row)[relation]
    if candidate != expected:
        raise ValueError('unexpected_content_edit')
    a,b=row['original_text'],row['replace_text']
    if relation == 'MATCH' and words(source) != words(candidate):
        raise ValueError('match_changed')
    if relation == 'OMISSION' and a in candidate:
        raise ValueError('omission_span_remains')
    if relation == 'ADDITION' and (candidate.count(b) != 1 or not subsequence(words(source),words(candidate))):
        raise ValueError('addition_not_unique_or_source_removed')
    return True
