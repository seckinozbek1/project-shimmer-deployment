"""Input-only machine-agent curation. No target, reviewer, or policy oracle imports."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Each observed semantic clause was read and assigned a typed interpretation.
# Tuple: kind, attribute, subject, ordinal, category, state.
MAPPING = {
    'The event time was not supplied.': ('gap','event_time','owned_record',None,'missing_information','unspecified'),
    'The observation time was not provided.': ('gap','observation_time','owned_record',None,'missing_information','unspecified'),
    'The recording time was not supplied.': ('gap','recording_time','owned_record',None,'missing_information','unspecified'),
    'The authorization time was not provided.': ('gap','authorization_time','owned_record',None,'missing_information','unspecified'),
    'The reporting time was not supplied.': ('gap','reporting_time','owned_record',None,'missing_information','unspecified'),
    'The submission time was not provided.': ('gap','submission_time','submission',None,'missing_information','unspecified'),
    'The date was not supplied.': ('gap','date_unspecified','owned_record',None,'missing_information','unspecified'),
    'The first entry recording time was not supplied.': ('gap','recording_time','entry',1,'missing_information','unspecified'),
    'This entry recording time was not supplied.': ('gap','recording_time','entry',1,'missing_information','unspecified'),
    'The second entry event time was not provided.': ('gap','event_time','entry',2,'missing_information','unspecified'),
    'The amendment effective time was not provided.': ('gap','effective_time','amendment',None,'missing_information','unspecified'),
    'The amendment ratification status was not supplied.': ('gap','ratification_status','amendment',None,'missing_information','unspecified'),
    'The recorder was not named and remains unnamed.': ('gap','recorder','owned_record',None,'missing_information','unspecified'),
    'The third entry was not recorded in the archive.': ('gap','recording_occurrence','entry',3,'explicit_nonoccurrence','not_recorded'),
    'The submission was not submitted to the desk.': ('gap','submission_occurrence','submission',None,'explicit_nonoccurrence','not_submitted'),
    'The event did not happen.': ('gap','event_occurrence','event',None,'explicit_nonoccurrence','did_not_occur'),
    'No second entry exists in the collection.': ('gap','entry_presence','entry',2,'explicit_nonoccurrence','absent'),
    'What does the second entry contain?': ('gap','entry_content','entry',2,'explicit_question','requested'),
    'What does the third entry state?': ('gap','entry_content','entry',3,'explicit_question','requested'),
    'Which entry came previous in sequence?': ('gap','entry_order','entry','previous','explicit_question','requested'),
    'Which entry came later in sequence?': ('gap','entry_order','entry','later','explicit_question','requested'),
    'The amendment ratification status is unresolved.': ('uncertainty','ratification_status','amendment',None,'unknown','unknown'),
    'The reporting time is uncertain.': ('uncertainty','reporting_time','owned_record',None,'unknown','unknown'),
    'The observation time is unknown.': ('uncertainty','observation_time','owned_record',None,'unknown','unknown'),
    'The third entry recording time is not known.': ('uncertainty','recording_time','entry',3,'unknown','unknown'),
    'The first entry interpretation is undetermined.': ('uncertainty','interpretation','entry',1,'unknown','unknown'),
    'The second entry interpretation is uncertain.': ('uncertainty','interpretation','entry',2,'unknown','unknown'),
    'Whether the submission was submitted is undetermined.': ('uncertainty','submission_occurrence','submission',None,'unknown','unknown'),
    'Whether the event happened is not known.': ('uncertainty','event_occurrence','event',None,'unknown','unknown'),
}
STRUCTURAL = {'Account sealed','Associated qualifications','Attached account','Contents begin','Contents end','Inner note','Outer inscription','Retained statement','Scope statement','Sender account',''}
STRUCTURAL.update({'[outer]', '[inner]'})

def review(row):
    items, reasons, tensions = [], [], []
    for span in row['input']['source_spans']:
        source = span['text']
        refs = sorted(set(re.findall(r'\bREF-\d{4,}\b',source)))
        claims = sorted(set(re.findall(r'\bCLM-[A-Za-z0-9-]+',source)))
        atoms = []
        for line in source.splitlines():
            if re.fullmatch(r'The .+ temperature is unknown\.',line):
                reasons.append('Unsupported meaningful uncertainty about temperature: '+line)
                continue
            if re.fullmatch(r'The .+ quantitative magnitude was not supplied\.',line):
                reasons.append('Unsupported meaningful missing quantitative magnitude: '+line)
                continue
            if line in MAPPING:
                if line.startswith('This entry'):
                    antecedents = set(re.findall(r'\b(first|second|third) entry\b',source))
                    if antecedents != {'first'}:
                        reasons.append('Ambiguous deictic entry: multiple ordinal entry referents in the owned source.')
                        continue
                    tensions.append('Resolved This entry to the sole explicit first entry within its owned span.')
                kind,attribute,subject,ordinal,category,state = MAPPING[line]
                atoms.append(dict(kind=kind,category=category,subject=subject,attribute=attribute,ordinal=ordinal,relation=None,state=state,scope='owned_record',unit=None,span=span['alias'],refs=refs,support=line,origin='source_explicit'))
            elif (line in STRUCTURAL or re.fullmatch(r'.+ (?:leaf|capsule|abstract|transfer|envelope) \d+',line)
                  or re.fullmatch(r'The (?:first|second) entry concerns .+\.',line)
                  or re.fullmatch(r'CLM-[A-Za-z0-9-]+: .+ logged .+\.',line)):
                pass
            else:
                raise ValueError('Unreviewed source clause: '+line)
        if 'for the same batch as' in source:
            tensions.append('Preserved all claim IDs and references despite differing quantities for the same batch; no reconciliation inferred.')
        if 'The date was not supplied.' in source:
            tensions.append('Unqualified date remains date_unspecified; nearby specific temporal roles do not establish its role.')
        if 'No second entry exists' in source and ('second entry contain' in source or 'second entry interpretation' in source):
            tensions.append('Preserved explicit second-entry absence alongside content question or interpretation uncertainty; no source contradiction repaired.')
        unique_atoms = {json.dumps(a,sort_keys=True): a for a in atoms}
        if len(unique_atoms) != len(atoms):
            tensions.append('Identical repeated source clause expresses one distinct semantic observation; retained once to satisfy no-duplicate atom contract.')
        items.append(dict(span=span['alias'],claims=claims,refs=refs,atoms=list(unique_atoms.values())))
    if reasons:
        return dict(example_id=row['example_id'],predicted_status='refused',reason=' '.join(dict.fromkeys(reasons)),items=[],interpretation_tensions=tensions)
    status = 'extracted' if any(i['claims'] or i['atoms'] for i in items) else 'empty'
    return dict(example_id=row['example_id'],predicted_status=status,reason='Every owned source span examined; all explicit claim IDs, evidence refs, supported gaps and uncertainties retained. Structural labels add no atoms.',items=items,interpretation_tensions=tensions)

def main():
    raw = (HERE/'packets.json').read_bytes()
    packets = json.loads(raw)
    reviews = [review(row) for row in packets]
    assert len(reviews) == 120 and len({r['example_id'] for r in reviews}) == 120
    counts = Counter(r['predicted_status'] for r in reviews)
    atoms = [a for r in reviews for i in r['items'] for a in i['atoms']]
    result = dict(
        input_sha256=hashlib.sha256(raw).hexdigest(),
        method='Input-only machine-agent curation using an explicit manually specified mapping of 29 distinct observed semantic clauses to typed atoms, source-only unsupported-attribute refusal, and within-owner deictic resolution. No calls to semantics.interpretations, target comparison, or model execution.',
        read_scope=['tuning/producer_v3/blind_review/packets.json','benchmark/producer_coverage_amendment_v3/semantics.py','benchmark/producer_coverage_amendment_v3/structural.py','scripts/compact_contracts.py'],
        limits=['Machine-agent curation, not human review or independent benchmark validation.','Frozen policy code was read to understand the schema and bounded ontology; predictions were manually mapped rather than generated by its interpretation function.','Only owned source_spans contribute labels; context-only spans provide no claims, evidence, or atoms.','No author data, targets, historical reviews, protected evaluation, Auditor data, model weights, network, training, or generation were accessed.','Repeated clause templates and surface substitutions limit linguistic diversity and do not establish broad generalization.'],
        diversity_review=dict(semantic_clause_templates=len(MAPPING),status_counts=dict(counts),accepted_atom_count=len(atoms),attributes=sorted({a['attribute'] for a in atoms}),assessment='Meaningful coverage across temporal roles, ordinal entries, content/order questions, explicit nonoccurrence, missingness, and uncertainty. Surface form variation is narrow: repeated short English clauses inside five document framing patterns, venue/name and numeric substitutions, and one/two-owner packaging. Refusals cover unsupported temperature/magnitude and deictic ambiguity. No empty-only packets in the observed population; negated epistemic cues, extensive paraphrases, and broad syntactic variation are not demonstrated.'),
        interpretation_review=['Whole-packet refusal preserves the completion contract when even one owned proposition cannot be represented.','Missing supplied time/status is a supported gap, not inability to extract. Unknown occurrence is uncertainty, distinct from explicit nonoccurrence.','Temporal event attributes default to owned_record under the frozen representation; explicit event nonoccurrence uses event.','With first and second entries present, This entry may appear pragmatically local but remains ambiguous under the frozen bounded referent policy.','All owned refs accompany each atom as required by the frozen representation; this does not independently establish real-world evidentiary relevance.'],
        revision_review='Re-examined final source inventory after packet revision: same 29 mapped clause forms; shortened claim IDs retained source-exactly. Added missingness-only combinations remain extractable. Duplicate event nonoccurrence in v3-review-015 and duplicate recording-time missingness in v3-review-069 are each retained as one distinct atom, with tension noted. No new unsupported clause forms or additional ambiguous referents identified.',
        final_header_review='Final packet inventory contains [outer] and [inner] as structural headers. Neither states a proposition, question, missingness, uncertainty, claim, or evidence reference; neither adds atoms. Source semantic clause mapping remains unchanged.',
        reviews=reviews)
    (HERE/'fresh_review.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps(dict(packet_count=len(reviews),status_counts=dict(counts),atom_count=len(atoms),input_sha256=result['input_sha256'])))

if __name__ == '__main__':
    main()
