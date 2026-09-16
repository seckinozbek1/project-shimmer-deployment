"""Input-only machine curation. Explicit clause map independently transcribed by reviewer.
No import or execution of author, semantics, labels, training, or model code.
"""
import collections, hashlib, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'packets.json'
def digest(x):
    return hashlib.sha256(x if isinstance(x, bytes) else json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

# Each tuple: kind, attribute, subject, ordinal, category, state.
M = {}
def gap(clause, attribute, subject='owned_record', ordinal=None, category='missing_information', state='unspecified'):
    M[clause] = ('gap', attribute, subject, ordinal, category, state)
def unknown(clause, attribute, subject='owned_record', ordinal=None):
    M[clause] = ('uncertainty', attribute, subject, ordinal, 'unknown', 'unknown')

gap('The event time was not supplied.', 'event_time')
gap('The authorization time was not provided.', 'authorization_time')
gap('The observation time was not provided.', 'observation_time')
gap('The reporting time was not supplied.', 'reporting_time')
gap('The amendment effective time was not provided.', 'effective_time', 'amendment')
gap('The recorder was not named and remains unnamed.', 'recorder')
gap('The submission time was not provided.', 'submission_time', 'submission')
gap('The recording time was not supplied.', 'recording_time')
gap('The date was not supplied.', 'date_unspecified')
gap('The amendment ratification status was not supplied.', 'ratification_status', 'amendment')
gap('The first entry recording time was not supplied.', 'recording_time', 'entry', 1)
gap('The second entry event time was not provided.', 'event_time', 'entry', 2)
gap('This entry recording time was not supplied.', 'recording_time', 'entry', 1)
gap('The submission was not submitted to the desk.', 'submission_occurrence', 'submission', category='explicit_nonoccurrence', state='not_submitted')
gap('The event did not happen.', 'event_occurrence', 'event', category='explicit_nonoccurrence', state='did_not_occur')
gap('No second entry exists in the collection.', 'entry_presence', 'entry', 2, 'explicit_nonoccurrence', 'absent')
gap('The third entry was not recorded in the archive.', 'recording_occurrence', 'entry', 3, 'explicit_nonoccurrence', 'not_recorded')
gap('Which entry came later in sequence?', 'entry_order', 'entry', 'later', 'explicit_question', 'requested')
gap('Which entry came previous in sequence?', 'entry_order', 'entry', 'previous', 'explicit_question', 'requested')
gap('What does the second entry contain?', 'entry_content', 'entry', 2, 'explicit_question', 'requested')
gap('What does the third entry state?', 'entry_content', 'entry', 3, 'explicit_question', 'requested')
unknown('The first entry interpretation is undetermined.', 'interpretation', 'entry', 1)
unknown('The second entry interpretation is uncertain.', 'interpretation', 'entry', 2)
unknown('The amendment ratification status is unresolved.', 'ratification_status', 'amendment')
unknown('The reporting time is uncertain.', 'reporting_time')
unknown('The observation time is unknown.', 'observation_time')
unknown('The third entry recording time is not known.', 'recording_time', 'entry', 3)
unknown('Whether the submission was submitted is undetermined.', 'submission_occurrence', 'submission')
unknown('Whether the event happened is not known.', 'event_occurrence', 'event')

HEADINGS = {'Contents begin','Contents end','Sender account','Associated qualifications','Scope statement','Inner note','Outer inscription','[face=outer]','[face=inner]','[outer]','[inner]','Account sealed','Retained statement','Attached account'}
def structural(line):
    return not line or line in HEADINGS or bool(re.fullmatch(r'[A-Za-z ]+ (?:capsule|transfer|abstract|envelope|leaf) \d+',line))

def review(packet):
    p=packet['input']; reasons=[]; ambiguities=[]; contradictions=[]; items=[]; owned=set()
    aliases=[s['alias'] for s in p['source_spans']]
    if len(set(aliases)) != len(aliases): reasons.append('Duplicate owned aliases')
    for s in p['source_spans']:
        text=s['text']; refs=sorted(set(re.findall(r'\bREF-\d{4,}\b',text)));owned.update(refs)
        claims=sorted(set(re.findall(r'\bCLM-[A-Za-z0-9-]+',text)))
        atoms=[]; claim_values={}
        for clause in text.splitlines():
            if structural(clause):continue
            match=re.fullmatch(r'(CLM-[A-Za-z0-9-]+): The ([a-z ]+) logged (\d+) units(?: for the same batch as (CLM-[A-Za-z0-9-]+))? \((REF-\d+)\)\.',clause)
            if match:
                claim_values[match[1]]=(match[2],int(match[3]))
                if match[4]:
                    previous=claim_values.get(match[4])
                    if previous and previous[0]==match[2] and previous[1]!=int(match[3]):
                        contradictions.append({'span':s['alias'],'type':'same_batch_conflicting_quantity','claims':[match[4],match[1]],'note':'Explicit same-batch quantities disagree; preserve both source claim IDs without adjudicating.'})
                continue
            if re.fullmatch(r'The (?:first|second) entry concerns (?:the|a separate) [a-z ]+\.',clause):continue
            if clause not in M:
                reasons.append('Unsupported meaningful source proposition: '+clause);continue
            if clause.startswith('This entry'):
                antecedents=set(re.findall(r'The (first|second|third) entry concerns ',text))
                if antecedents != {'first'}:
                    reasons.append('Deictic entry has multiple or nonunique antecedents in its owned source span')
                    ambiguities.append({'span':s['alias'],'support':clause,'antecedents':sorted(antecedents)})
                    continue
            kind,attribute,subject,ordinal,category,state=M[clause]
            atoms.append(dict(kind=kind,category=category,subject=subject,attribute=attribute,ordinal=ordinal,relation=None,state=state,scope='owned_record',unit=None,span=s['alias'],refs=refs,support=clause,origin='source_explicit'))
        items.append(dict(span=s['alias'],claims=claims,refs=refs,atoms=atoms))
    if not owned <= set(p.get('supplied_refs',[])):reasons.append('Owned evidence missing from supplied refs')
    if not set(p.get('required_refs',[])) <= owned:reasons.append('Required refs outside owned evidence')
    status='refused' if reasons else 'extracted' if any(i['claims'] or i['atoms'] for i in items) else 'empty'
    return dict(example_id=packet['example_id'],input_sha256=digest(p),source_sha256=digest(p['source_spans']),predicted_status=status,refusal_reason='; '.join(dict.fromkeys(reasons)) or None,items=[] if reasons else items,review_ambiguity=bool(ambiguities),ambiguity_flags=ambiguities,source_contradictions=contradictions,source_uncertainty_present=False if reasons else any(a['kind']=='uncertainty' for i in items for a in i['atoms']))

def main():
    raw=SOURCE.read_bytes();packets=json.loads(raw);rows=[review(p) for p in packets]
    inventory=collections.Counter(a['attribute'] for r in rows for i in r['items'] for a in i['atoms'])
    report=dict(review_kind='input-only machine-agent curation with prior identifier exposure',policy='producer-semantic-policy-v3',source_file='tuning/producer_v3/blind_review/packets.json',source_file_sha256=digest(raw),reviewer_sha256=digest(Path(__file__).read_bytes()),rows=rows,
        method='Independently transcribed 29-clause semantic table after reading source clause inventory and frozen ontology. Applied to every packet with independent ownership, refs, claims, unsupported-clause, deictic and same-batch contradiction checks. No semantic interpreter calls or imports; full source clauses preserved as support.',
        shared_policy_dependence=['Read semantics.py ontology and resolution rules, structural.py, and compact_contracts.py. Shared specification means this is not fully independent validation of the specification itself.'],
        limitations=['Machine-agent curation, not human review or an independent benchmark.','Reviewer initially saw example IDs containing extract/refuse suffixes. Final packets use opaque IDs and were reloaded, but initial exposure prevents a fully blind claim. Predictions use only packet input content.','Synthetic repeated 29-clause mapping with superficial domain and wrapper variation; limited natural-language diversity.','No unsupported novel wording is silently treated as structural; unrecognized meaningful lines refuse.','Contradictory source claims are flagged and both IDs preserved; no real-world truth adjudication.','Claim numbering does not itself establish first/second/third entry identity, so no inferred contradiction from ID ordinal and missing entry.'],
        summary=dict(packet_count=len(rows),status_counts=dict(collections.Counter(r['predicted_status'] for r in rows)),ambiguity_count=sum(r['review_ambiguity'] for r in rows),source_contradiction_packet_count=sum(bool(r['source_contradictions']) for r in rows),manually_mapped_distinct_clauses=len(M),attribute_counts=dict(inventory),ownership_span_counts=dict(collections.Counter(len(p['input']['source_spans']) for p in packets)),context_only_ignored=True))
    assert len(rows)==120 and len({r['example_id'] for r in rows})==120
    (HERE/'review.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps(report['summary'],indent=2))
if __name__=='__main__':main()
