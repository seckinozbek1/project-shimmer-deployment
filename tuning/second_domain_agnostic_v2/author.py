"""V2 compositional authoring: unique semantic plans, never a surface cross product.

Each retained substantive plan has a unique normalized semantic signature.
Surfaces and reference numbers are explicitly excluded from expansion credit.
"""
import itertools
import json
import re
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'benchmark/producer_coverage_amendment_v3'))
import semantics as sem
from structural import semantic_segments

DOMAINS = {
    'negotiation': ('delegation', 'offers'), 'contracts': ('licence', 'clauses'),
    'regulation': ('circular', 'permits'), 'clinical': ('synthetic ward', 'specimens'),
    'device': ('sensor rack', 'pulses'), 'procurement': ('purchase lot', 'crates'),
    'catalogue': ('index collection', 'cards'), 'nonsense': ('zorb council', 'flims'),
    'astronomy': ('observatory', 'exposures'), 'ecology': ('transect', 'quadrats'),
}
TEMPLATES = ['prose', 'bullet_list', 'form_fields', 'timeline', 'question_answer',
             'memo', 'compact_table', 'multi_row_table', 'nested_clauses', 'register',
             'machine_log', 'mixed_prose_table', 'correspondence', 'meeting_minutes',
             'incident_report', 'structured_notice', 'checklist', 'dialogue',
             'footnoted_record', 'comparison_matrix']
# These clauses are finite-ontology propositions, not inferred domain facts.
GAPS = [
    'The recording date is unavailable.', 'The event date is missing.',
    'The submission date is unspecified.', 'The authorization date is unavailable.',
    'The observation date is missing.', 'The reporting date is unspecified.',
    'The amendment effective date is unavailable.', 'The recorder is unnamed.',
    'What was entered first?', 'What was entered second?', 'What came next?',
    'Which entry came previous?', 'The second entry was not submitted.',
    'The third entry was not recorded.', 'The event did not occur.',
    'No first entry exists.', 'The amendment ratification status is missing.',
    'The first entry recording date is missing.', 'The second entry event date is missing.',
    'What was entered third?', 'Which entry came later?',
    'The submission was not submitted.', 'The date is unavailable.',
]
UNCERTAINTIES = [
    'The interpretation of the second entry remains unresolved.',
    'Whether the event occurred is unknown.',
    'The amendment ratification status remains unknown.',
    'The third entry recording date is uncertain.',
    'Whether the submission was submitted is unknown.',
    'The first entry interpretation is unclear.',
    'The reporting date is unknown.',
]


def layout(template, clauses, title):
    """Distinct information organizations; never count layouts as semantic novelty."""
    c = list(clauses)
    if not c: c=['Identifier','Attachment','Section']
    if template == 'prose': return title + '\n' + ' '.join(c)
    if template == 'bullet_list': return title + '\n' + '\n'.join('- ' + x for x in c)
    if template == 'form_fields': return title + '\n' + '\n'.join(f'Field {i+1}: {x}' for i,x in enumerate(c))
    if template == 'timeline': return title + '\n' + '\n'.join(f'Phase {i+1:02d} | {x}' for i,x in enumerate(c))
    if template == 'question_answer': return title + '\n' + '\n'.join('Q: Record segment?\nA: ' + x for x in c)
    if template == 'memo': return 'To: Desk\nSubject: ' + title + '\nSummary\n' + c[0] + '\nDetails\n' + '\n'.join(c[1:])
    if template == 'compact_table': return title + '\n| Key | Statement |\n|---|---|\n' + '| Record | ' + ' '.join(c) + ' |'
    if template == 'multi_row_table': return title + '\n| Row | Statement |\n|---|---|\n' + '\n'.join(f'| {i+1} | {x} |' for i,x in enumerate(c))
    if template == 'nested_clauses': return title + '\n' + '\n'.join(('  ' * (i%3)) + f'Clause {i+1}: {x}' for i,x in enumerate(c))
    if template == 'register': return title + '\n' + '\n'.join(f'Entry slot {i+1}\n{x}\nEnd slot' for i,x in enumerate(c))
    if template == 'machine_log': return title + '\n' + '\n'.join(f'[segment={i+1}]\n{x}\n[/segment]' for i,x in enumerate(c))
    if template == 'mixed_prose_table': return title + '\n' + c[0] + '\n| Detail |\n|---|\n' + '\n'.join('| '+x+' |' for x in c[1:])
    if template == 'correspondence': return title + '\nMessage body\n' + c[0] + '\nContinuation of the same record\n' + '\n'.join(c[1:])
    if template == 'meeting_minutes': return title + '\nAgenda\n' + c[0] + '\nDiscussion\n' + '\n'.join(c[1:]) + '\nEnd minutes'
    if template == 'incident_report': return title + '\nInitial account\n' + c[0] + '\nFollow-up observations\n' + '\n'.join(c[1:])
    if template == 'structured_notice': return title + '\nPart I\n' + c[0] + '\nPart II\n' + '\n'.join(c[1:]) + '\nEnd notice'
    if template == 'checklist': return title + '\n' + '\n'.join('[x] ' + x for x in c)
    if template == 'dialogue': return title + '\nRecord readback\n' + '\n'.join(('Readback segment: ' if i%2==0 else 'Readback continuation: ') + x for i,x in enumerate(c))
    if template == 'footnoted_record': return title + '\n' + c[0] + '\nAnnotations\n' + '\n'.join(f'[{i+1}] {x}' for i,x in enumerate(c[1:]))
    if template == 'comparison_matrix': return title + '\n| Position | Account |\n|---|---|\n' + '\n'.join(f'| {"Initial" if i==0 else "Supplement"} | {x} |' for i,x in enumerate(c))
    raise ValueError(template)


def packet(role, spans, extraction=None):
    refs = sorted(set(re.findall(r'REF-\d{4,}', ' '.join(s['text'] for s in spans))))
    p = dict(role=role, production_contract='semantic-task-v1', source_spans=spans,
             context_only_spans=[dict(alias='sffff', text='CONTEXT ONLY: CLM-NEIGHBOR reports 900 units (REF-9999). The recording date is 2040-01-01.')],
             supplied_refs=refs + ['REF-9999'], required_refs=refs, routed_rules=[])
    if extraction is not None: p['extraction'] = extraction
    return p


def typed_label(p, refused=False):
    if refused: return dict(status='refused', items=[], source_uncertainty_present=False, review_ambiguity=True)
    items = []
    for s in p['source_spans']:
        refs = sorted(set(re.findall(r'REF-\d{4,}', s['text'])))
        atoms = []
        for clause in semantic_segments(s['text']):
            atoms.extend(sem.interpretations(clause, s['text'], s['alias'], refs))
        atoms = list({json.dumps(sem.normalize(a), sort_keys=True):a for a in atoms}.values())
        items.append(dict(span=s['alias'], claims=sorted(set(re.findall(r'CLM-[A-Za-z0-9-]+', s['text']))), refs=refs,
                          gap_atoms=[a for a in atoms if a['kind']=='gap'], uncertainty_atoms=[a for a in atoms if a['kind']=='uncertainty']))
    return dict(status='examined', items=items, source_uncertainty_present=any(i['uncertainty_atoms'] for i in items), review_ambiguity=False)


def base_metadata(role, number, template, domain):
    family = f'shimmer2-{role}-document-{number:03d}'
    return dict(example_id=family, role=role, domain=domain, domain_family=domain,
                document_family=family, template_family=template, derivation_group=family,
                paraphrase_family=family, renamed_family=family, parent_ids=[],
                leakage_group='layout-' + template, provenance='new_machine_authored_compositional_plan',
                human_reviewed=False, training_authorized=False, source_policy=sem.POLICY)


def producer():
    rows=[]; pairs=list(itertools.combinations(range(len(GAPS)), 2)); substantive_index=0
    for t, template in enumerate(TEMPLATES):
        for j in range(15):
            n=t*15+j; domain=list(DOMAINS)[(t+j)%10]; entity,unit=DOMAINS[domain]
            meta=base_metadata('producer', n, template, domain)
            refused=j==14; empty=j==13
            count=(substantive_index%4) if not (refused or empty) else 0
            claims=[f'CLM-{chr(65+k)}: The {entity} {"planned" if k==0 else "reported"} {11+3*k} {unit} (REF-{20000+n*4+k}).' for k in range(count)]
            if count==3 and substantive_index%3==0:
                claims[2]=f'CLM-C: The {entity} reported 29 {unit} for the same entry as CLM-B (REF-{20000+n*4+2}).'
            if empty: clauses=[]; gap_indices=[]
            elif refused:
                clauses=[f'The {entity} quantitative value is missing.', GAPS[t%len(GAPS)]]; gap_indices=[]
            else:
                # 23 single-atom tasks, then 237 different paired/triple semantic tasks.
                gap_indices=[substantive_index] if substantive_index<len(GAPS) else list(pairs[substantive_index-len(GAPS)])
                if substantive_index>=210:
                    third=next(x for x in range(len(GAPS)) if x not in gap_indices)
                    gap_indices.append(third)
                clauses=claims+[GAPS[x] for x in gap_indices]
                if substantive_index%3 != 0: clauses.append(UNCERTAINTIES[substantive_index%len(UNCERTAINTIES)])
                substantive_index+=1
            # Actual ownership separation, not an artificial renamed sibling.
            chunks=[clauses]
            if not (refused or empty) and len(clauses)>2 and n%2==0:
                chunks=[clauses[:1], clauses[1:]]
            spans=[dict(alias=f's{k*4096:x}', text=layout(template, chunk, f'{domain.title()} dossier / segment {k+1}')) for k,chunk in enumerate(chunks)]
            p=packet('producer', spans); label=typed_label(p, refused)
            target=sem.validate_label(label,p)
            signature=dict(gaps=sorted(gap_indices), claims=count, uncertainty=[] if refused or empty else [a['attribute'] for i in label['items'] for a in i['uncertainty_atoms']],
                           ownership=[len(i['gap_atoms']) for i in label['items']], refused=refused, empty=empty)
            rows.append(dict(meta, input=p, typed_label=label, canonical_target=target, semantic_signature=signature,
                substantive=not(refused or empty), hard_negative=True,
                refusal_basis='Unspecified quantitative value lies outside the frozen finite attribute ontology; no surrogate date/presence atom is licensed.' if refused else None))
    return rows


def auditor():
    """Sixty comparison configurations per class, with decision-bearing contrasts.

    Qualifiers are compared, removed, contradicted, or left unresolved. Twelve
    proposition structures avoid teaching a single two-quantity extraction.
    """
    rows=[]; relations=['MATCH','DIVERGENCE','OMISSION','ADDITION','INSUFFICIENT_EVIDENCE']
    pairs=list(itertools.combinations(range(len(GAPS)),2))
    structures=[
        ['The count is 11 {unit}.'],
        ['The planned count is 11 {unit}.','The reported count is 17 {unit}.'],
        ['The planned count is 11 {unit}.','The reported count is 11 {unit}.'],
        ['Account A says the count is 11 {unit}.','Account B says the same count is 17 {unit}.'],
        ['The event occurred on 2041-02-03.','The event was recorded on 2041-02-09.'],
        ['The first entry was submitted.','The first entry was not recorded.'],
        ['The event did not occur.','The report of the event was recorded.'],
        ['Approval applies only if the count exceeds 10 {unit}.','The measured count is 11 {unit}.'],
        ['The count is 11 {unit} in the northern section.','The southern section reports 17 {unit}.'],
        ['The count is 11 {unit}.','The transport container count is 11 boxes.'],
        ['The authorization date is 2041-02-01.','The submission date is 2041-02-02.','The event date is 2041-02-03.'],
        ['The first entry concerns the {entity}.','The second entry concerns a separate record.','The third entry repeats the first entry.'],
    ]
    for n in range(300):
        t,j=divmod(n,15); template=TEMPLATES[t];relation=relations[j%5];v=n//5
        domain=list(DOMAINS)[(t+j)%10];entity,unit=DOMAINS[domain]
        structure=v%12;layer=v//12
        refs=[f'REF-{40000+n*4+k}' for k in range(4)]
        claims=[f'CLM-{chr(65+k)}: '+text.format(entity=entity,unit=unit)+f' ({refs[k]})' for k,text in enumerate(structures[structure])]
        # Retained qualifier pair is a source-level semantic combination, not a name substitution.
        g1,g2=pairs[(v*4+j%5)%len(pairs)]
        uncertainty=UNCERTAINTIES[(v+layer)%len(UNCERTAINTIES)]
        # Avoid an unscoped known nonoccurrence plus unknown occurrence in the
        # same annex; explicit conflicting accounts remain in structure 3.
        pair_text=GAPS[g1]+' '+GAPS[g2]
        if ('did not occur' in pair_text and 'Whether the event occurred' in uncertainty) or ('not submitted' in pair_text and 'Whether the submission was submitted' in uncertainty):
            uncertainty='The interpretation of the second entry remains unresolved.'
        qualifiers=[GAPS[g1],GAPS[g2],uncertainty]
        scope='The following qualifications concern a separate annex, not the numbered claim events.'
        clauses=claims+[scope]+qualifiers;extract=list(clauses);subtype='';reason=''
        if relation=='MATCH':
            subtype=['complete_ordered','reordered_preserving_scope','claims_after_qualifiers','multi_clause_faithful','explicit_refusal_rejected'][layer]
            if layer in (1,2):extract=[scope]+qualifiers+['End annex qualifications.']+claims
            # This is a comparison of an extraction, never a request to abstain.
            reason=f'The extraction preserves all {len(claims)} explicit claims, including their scope and evidence, and retains both gaps ({GAPS[g1]} {GAPS[g2]}) and the stated uncertainty.'
        elif relation=='DIVERGENCE':
            original=qualifiers[0]
            if layer==0:
                original=claims[0]
                substitutions=[('11','12'),('planned','reported'),('planned','reported'),('11','17'),
                    ('2041-02-03','2041-02-09'),('submitted','recorded'),('did not occur','occurred'),
                    ('only if','regardless of whether'),('northern','southern'),(unit,'boxes'),
                    ('authorization','submission'),('first','second')]
                before,after=substitutions[structure];replacement=original.replace(before,after,1);subtype='core_claim_mutation'
            elif layer==1:
                original=claims[0];replacement=original.replace(refs[0],refs[1] if len(claims)>1 else 'REF-9999');subtype='correct_words_wrong_evidence'
            elif layer==2:
                original=uncertainty;replacement=original
                for before,after in [('unresolved','resolved'),('unknown','known'),('uncertain','certain'),('unclear','clear')]:replacement=replacement.replace(before,after)
                subtype='uncertainty_replaced_by_certainty'
            else:
                original=qualifiers[layer-3];replacement=original
                mutations=[('first','third'),('second','first'),('third','second'),('next','previous'),('previous','later'),('later','next'),
                    ('recording','event'),('event','recording'),('submission','authorization'),('authorization','submission'),
                    ('observation','reporting'),('reporting','observation'),('effective','recording'),('unnamed','named'),
                    ('missing','known'),('unavailable','known'),('unspecified','known')]
                for before,after in mutations:
                    if before in original:replacement=original.replace(before,after,1);break
                if replacement==original:replacement=original.replace('did not occur','occurred').replace('not submitted','submitted')
                subtype='gap_referent_or_temporal_role_changed'
                if 'came later' in original:
                    original=claims[0]
                    replacement=original.replace(refs[0],refs[1] if len(claims)>1 else 'REF-9999')
                    subtype='correct_words_wrong_evidence'
            assert original!=replacement
            extract[extract.index(original)]=replacement
            reason=f'The extraction replaces "{original}" with "{replacement}". This changes the same proposition, referent, or evidence association rather than preserving it.'
            reason=reason.replace('REF-9999','the context-only reference')
        elif relation=='OMISSION':
            if layer<3:
                removed=extract.pop(len(claims)+1+layer);subtype=['first_gap_omission','second_gap_omission','uncertainty_omission'][layer]
            elif layer==3:
                removed=extract.pop(0);subtype='scoped_claim_omission'
            else:
                removed=' '.join(extract[len(claims)+1:len(claims)+3]);del extract[len(claims)+1:len(claims)+3];subtype='simultaneous_gap_omission'
            reason=f'The complete, delivered extraction omits the source content "{removed}" while retaining the remaining material. This is a substantive omission, not a transport failure.'
        elif relation=='ADDITION':
            extra=[f'A supervisor approved all {len(claims)} entries.',
                'An external rule requires every entry to be signed twice.',
                'An independent inspector verified every qualification.',
                'The reported result was caused by equipment vibration.',
                'The overall review passed without reservations.'][layer]
            extract.append(extra);subtype=['approval_invention','rule_invention','verification_invention','cause_invention','outcome_invention'][layer]
            reason=f'The extraction adds "{extra}" without support in any owned source span. All original claims and qualifications remain.'
        else:
            # Different missing-information structures; no one common refusal token.
            subtype=['interrupted_claim','unresolved_deictic','unbound_quotation','missing_owned_original','ambiguous_qualification'][layer]
            if layer==0:extract=[claims[0].split(': ',1)[0]+': The'];
            elif layer==1:extract=['That is the entry referred to by this statement.']
            elif layer==2:extract=['"'+qualifiers[0].split(' ')[-2]+'"']
            elif layer==3:
                extract=clauses;clauses=['[Owned original was not supplied; the neighboring record is context only.]']
            else:extract=['The date or entry mentioned there remains as stated.']
        text=layout(template,clauses,domain.title()+' comparison dossier')
        source=[dict(alias='s0',text=text)]
        # Comparisons use an explicit completed-delivery flag to distinguish a
        # semantic omission from interrupted/missing transport. It is visible
        # for all classes and not sufficient by itself to decide the relation.
        p=packet('auditor',source,' '.join(extract))
        p['delivery_complete']=not (relation=='INSUFFICIENT_EVIDENCE' and layer==0)
        if relation=='INSUFFICIENT_EVIDENCE':target=dict(items=[],status='refused')
        else:target=dict(items=[dict(finding=relation,ref_ids=refs[:len(claims)],reasoning=reason,severity='low' if relation=='MATCH' else 'medium',confidence='CONFIDENT')])
        rows.append(dict(base_metadata('auditor',n,template,domain),input=p,semantic_target=target,
            relation=relation,substantive=True,hard_negative=True,reason_difficulty=subtype,
            semantic_signature=dict(structure=structure,gaps=[g1,g2],uncertainty=uncertainty,relation=relation,transformation=subtype),
            source_claims=claims,source_qualifications=qualifiers))
    return rows


def build():
    result=producer()+auditor()
    for role in ('producer','auditor'):
        signatures=[json.dumps(r['semantic_signature'],sort_keys=True) for r in result if r['role']==role and r['substantive']]
        assert len(signatures)==len(set(signatures)), 'Duplicate semantic plans cannot count as expansion'
    return result


if __name__=='__main__':
    rows=build()
    (HERE/'dataset.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8')
    print({role:sum(r['role']==role for r in rows) for role in ('producer','auditor')})
