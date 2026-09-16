"""Targeted Producer-only additions; no DEV packet is an authoring input."""
from local_common import *
import itertools
import re
from copy import deepcopy
from structural import semantic_segments

DOMAINS = [('railway','switch cabin'),('theatre','stage crew'),('horticulture','seed nursery'),
           ('geology','core archive'),('manufacturing','lathe cell'),('navigation','beacon station'),
           ('textiles','weaving room'),('acoustics','echo chamber'),('ceramics','kiln workshop'),('cartography','map studio')]
STRUCTURES = ['sealed_capsules','signed_handoff','paired_abstracts','specimen_envelopes','correction_leaf']
# New clauses preserve the finite ontology; no historical packet is paraphrased.
# Plans are distinct combinations, not a domain/layout cross product.
GAPS = [
 'The event time was not supplied.', 'The observation time was not provided.',
 'The third entry was not recorded in the archive.', 'The recording time was not supplied.',
 'The submission was not submitted to the desk.', 'The event did not happen.',
 'Which entry came later in sequence?', 'What does the second entry contain?',
 'The authorization time was not provided.', 'The reporting time was not supplied.',
 'The amendment effective time was not provided.', 'The recorder was not named and remains unnamed.',
 'The first entry recording time was not supplied.', 'The second entry event time was not provided.',
 'No second entry exists in the collection.', 'The amendment ratification status was not supplied.',
 'What does the third entry state?', 'Which entry came previous in sequence?',
 'The submission time was not provided.', 'The date was not supplied.',
]
UNCERTAINTY = [
 'The first entry interpretation is undetermined.',
 'The second entry interpretation is uncertain.',
 'The third entry recording time is not known.',
 'The amendment ratification status is unresolved.',
 'The reporting time is uncertain.',
 'Whether the submission was submitted is undetermined.',
 'Whether the event happened is not known.',
 'The observation time is unknown.',
]

def label(packet, refuse=False):
    if refuse:return dict(status='refused',items=[],source_uncertainty_present=False,review_ambiguity=True)
    items=[]
    for span in packet['source_spans']:
        text=span['text'];refs=sorted(set(re.findall(r'REF-\d{4,}',text)));all_atoms=[]
        for clause in semantic_segments(text):all_atoms.extend(v2.sem.interpretations(clause,text,span['alias'],refs))
        unique={canonical(v2.sem.normalize(a)):a for a in all_atoms}
        items.append(dict(span=span['alias'],claims=sorted(set(re.findall(r'CLM-[A-Za-z0-9-]+',text))),refs=refs,
            gap_atoms=[a for a in unique.values() if a['kind']=='gap'],uncertainty_atoms=[a for a in unique.values() if a['kind']=='uncertainty']))
    return dict(status='examined',items=items,source_uncertainty_present=any(i['uncertainty_atoms'] for i in items),review_ambiguity=False)

def signature(lab):
    # Stronger than ID or layout checks: remove refs, owner aliases, names,
    # claims, quantities and support wording before checking semantic siblings.
    return sorted({canonical({k:a[k] for k in ('kind','category','subject','attribute','ordinal','relation','state','scope','unit')})
                   for i in lab['items'] for a in i['gap_atoms']+i['uncertainty_atoms']})

def wrap(structure,clauses,entity,number):
    if structure=='sealed_capsules':return f'{entity.title()} capsule {number}\nContents begin\n'+ '\n'.join(clauses)+'\nContents end'
    if structure=='signed_handoff':return f'{entity.title()} transfer {number}\nSender account\n'+'\n'.join(clauses)+'\nAccount sealed'
    if structure=='paired_abstracts':return f'{entity.title()} abstract {number}\nScope statement\n'+clauses[0]+'\nAssociated qualifications\n'+'\n'.join(clauses[1:])
    if structure=='specimen_envelopes':return f'{entity.title()} envelope {number}\n[outer]\n'+clauses[0]+'\n[inner]\n'+'\n'.join(clauses[1:])
    if structure=='correction_leaf':return f'{entity.title()} leaf {number}\nRetained statement\n'+clauses[0]+'\nAttached account\n'+'\n'.join(clauses[1:])
    raise ValueError(structure)

def packet(structure,clauses,entity,n,multi):
    chunks=[clauses[:1],clauses[1:]] if multi else [clauses]
    spans=[dict(alias=f's{k*4096:x}',text=wrap(structure,c,entity,n)) for k,c in enumerate(chunks)]
    refs=sorted(set(re.findall(r'REF-\d{4,}',' '.join(x['text'] for x in spans))))
    return dict(role='producer',production_contract='semantic-task-v1',source_spans=spans,
        context_only_spans=[dict(alias='sffff',text='CONTEXT ONLY: CLM-OUTSIDE identifies a separate collection (REF-990001).')],
        supplied_refs=refs+['REF-990001'],required_refs=refs,routed_rules=[])

def run():
    old=[x for x in read(ROOT/'tuning/second_domain_agnostic_v2/dataset.json') if x['role']=='producer']
    seen={canonical(signature(x['typed_label'])) for x in old if x['substantive']}
    additions=[];plans=[]
    # Retain every base row byte-equivalently at the JSON-object level.
    # Candidate plans depend only on abstract ontology atoms, not failed DEV packets.
    for group,structure in enumerate(STRUCTURES):
        for j in range(20):
            n=group*20+j;domain,entity=DOMAINS[(3*group+j)%len(DOMAINS)]
            candidates=((n%8,8+(n+s)%12,(n+u)%8) for s in range(12) for u in range(8))
            for primary,secondary,u in candidates:
                clauses=[GAPS[primary],GAPS[secondary]]+([] if j%5==0 else [UNCERTAINTY[u]])
                # Include 25 triple-gap examples, while staying below the unchanged cap.
                if j%4==3 or j%5==0:clauses.insert(2,GAPS[(secondary+3+u)%20])
                # One anchored antecedent supports the hard contrast for j=2/3.
                if j in (2,3):clauses=[f'The first entry concerns the {entity}.','This entry recording time was not supplied.',GAPS[secondary],UNCERTAINTY[u]]
                claims=j%4
                if j<4:claims=0
                prefix=[f'CLM-K{chr(65+k)}: The {entity} logged {31+n+5*k} units (REF-{70000+n*4+k}).' for k in range(claims)]
                if claims==3 and n%2:
                    prefix[2]=f'CLM-KC: The {entity} logged {56+n} units for the same batch as CLM-KB (REF-{70000+n*4+2}).'
                p=packet(structure,prefix+clauses,entity,n,multi=(j%5==4))
                try:lab=label(p)
                except ValueError:continue  # Do not retain ambiguous positive candidates.
                sig=signature(lab)
                # Exclude source epistemic/known-state tensions for identical referents.
                aa=[a for i in lab['items'] for a in i['gap_atoms']+i['uncertainty_atoms']]
                if any(a['kind']!=b['kind'] and (a['subject'],a['ordinal'],a['attribute'])==(b['subject'],b['ordinal'],b['attribute']) for a in aa for b in aa):continue
                if canonical(sig) in seen:continue
                v2.sem.validate_label(lab,p);seen.add(canonical(sig));break
            else:raise AssertionError('Insufficient distinct targeted plans')
            family=f'producer-v3-document-{n:03d}';eid=family+'-extract'
            conservative='anchored' if structure=='specimen_envelopes' else 'sectioned'
            meta=dict(example_id=eid,role='producer',domain=domain,domain_family=domain,document_family=family,
                template_family=conservative,rendering_template=structure,source_structure=structure,derivation_group=family,paraphrase_family=family,renamed_family=family,
                parent_ids=[],leakage_group='v2-structure-'+conservative,provenance='targeted_machine_authored_abstract_error_class',
                human_reviewed=False,training_authorized=False,source_policy=v2.sem.POLICY,hard_negative=True)
            additions.append(dict(meta,input=p,typed_label=lab,canonical_target=v2.sem.render(lab),semantic_signature=sig,substantive=True,refusal_basis=None))
            plans.append(dict(example_id=eid,primary_gap=primary,secondary_gap=secondary,uncertainty=u,
                target_classes=['gap_completeness','refusal_boundary' if j<4 else 'referent_attribute_type'],
                canonical_semantic_signature=sig))
            if j<4:
                # Matched surface cues, changed semantic sufficiency. Whole-packet
                # refusal is the unchanged finite-policy behavior, never a missing-info shortcut.
                neg=deepcopy(p)
                if j==0:extra=f'The {entity} quantitative magnitude was not supplied.';basis='Unsupported quantitative magnitude; do not invent a temporal or presence surrogate.'
                elif j==1:extra=f'The {entity} temperature is unknown.';basis='Unknown temperature outside the finite ontology, not representable uncertainty.'
                else:
                    # The positive has exactly one antecedent; the negative adds a second.
                    extra=f'The second entry concerns a separate {entity}.';basis='Two ordinal antecedents make this entry ambiguous; the requested recording relation cannot be assigned.'
                neg['source_spans'][0]['text']=extra+'\n'+neg['source_spans'][0]['text']
                nl=label(neg,True)
                additions.append(dict(meta,example_id=family+'-refuse',parent_ids=[eid],input=neg,typed_label=nl,
                    canonical_target=v2.sem.render(nl),semantic_signature=dict(refused=True,boundary=j,pair=eid),substantive=False,refusal_basis=basis))
    assert len(additions)==120 and sum(x['substantive'] for x in additions)==100
    rows=old+additions
    oldsplit=read(ROOT/'tuning/second_domain_agnostic_v2/splits.json')['canonical']
    split={k:[i for i in oldsplit[k] if i in {x['example_id'] for x in old}] for k in ('train','validation')}
    # Do not rename familiar layouts into supposedly independent new groups:
    # the four sectioned organizations inherit TRAIN; anchored envelopes inherit
    # the complete V2 anchored DEV superfamily, including every new sibling.
    dev_structure='specimen_envelopes'
    for x in additions:split['validation' if x['source_structure']==dev_structure else 'train'].append(x['example_id'])
    split.update(seed=43,allocation='Preserve V2 canonical memberships and conservative superfamilies: new sectioned documents TRAIN, new anchored envelope documents DEV. No new holdout-independence claim from renamed layouts.',held_out_new_structure=dev_structure)
    v2.check_split(rows,split)
    write(HERE/'augmentation.json',additions);write(HERE/'dataset.json',rows);write(HERE/'authoring_plans.json',plans);write(HERE/'split.json',split)
    # Input-only review payload. Authored labels/plans are absent.
    ordered=sorted(additions,key=lambda x:hashlib.sha256(('blind43:'+x['example_id']).encode()).hexdigest())
    mapping={f'v3-review-{i:03d}':x['example_id'] for i,x in enumerate(ordered)}
    write(HERE/'review_mapping.json',mapping)
    write(HERE/'blind_review/packets.json',[dict(example_id=f'v3-review-{i:03d}',input=x['input']) for i,x in enumerate(ordered)])
    print(json.dumps(dict(base_rows=len(old),base_substantive=sum(x['substantive'] for x in old),new_rows=len(additions),new_substantive=100,train=len(split['train']),dev=len(split['validation']),held_out=dev_structure)))

if __name__=='__main__':run()
