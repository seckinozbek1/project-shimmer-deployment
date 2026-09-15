"""Reproducibly author the public seed. Split plans precede all descendants.

This is data curation, not a model/optimizer job. Never reads existing private
corpora or answer keys. All vocabulary and labels below are public seed data.
"""
from copy import deepcopy
from collections import Counter
from pathlib import Path
import json
import re

from core import ROOT, VERSION, GROUPS, digest, write, ex, cc

HERE = Path(__file__).resolve().parent
DOMAINS = {
    'negotiation': ('offer memo', 'Orin', 'Vela', 'concessions', 'Council of Talks'),
    'contracts': ('service clause', 'Leto', 'Mira', 'delivery lots', 'Accord Office'),
    'regulation': ('filing excerpt', 'Nera', 'Sola', 'filed notices', 'Registry Board'),
    'clinical': ('fictional observation', 'Case Alder', 'Case Birch', 'recorded observations', 'Synthetic Clinic'),
    'device': ('diagnostic note', 'Module Cedar', 'Module Elm', 'signal cycles', 'Test Lab'),
    'procurement': ('bid worksheet', 'Bidder Flint', 'Bidder Gale', 'supply crates', 'Purchasing Desk'),
    'catalogue': ('metadata record', 'Collection Haze', 'Collection Iris', 'catalogue entries', 'Archive Office'),
    'nonsense': ('blenket folio', 'Zorvit', 'Plenko', 'quavels', 'Institute of Nimbular Blenkets'),
}
# These are structurally distinct source templates. Renamings within each
# template are confined to its preassigned split, including across domains.
PLANS = {
    'train': ('paired_register', 'register', 'CLM-A: {a} planned {n} {u} (REF-0001); CLM-B: {b} reported {m} {u} (REF-0002). {gap} {unc}'),
    'dev': ('revision_log', 'revision history', 'Revision history maintained by {org}: CLM-A registers {a} proposed {n} {u} under REF-0001. The retained amendment, CLM-B, registers {b} amended {m} {u} under REF-0002. Both versions remain in the archive. {unc} {gap}'),
    'test': ('attributed_dialogue', 'attributed dialogue', 'Interview transcript, {org}. First speaker: "CLM-A says {a} accepted {n} {u}; see REF-0001." Second speaker: "CLM-B says {b} declined {m} {u}; see REF-0002." Recorder asks: "{gap}" An unsigned marginal note reads: "{unc}"'),
    'sealed_adversarial': ('scope_notice', 'scope and exception note', 'Exception notice: the {org} inventory separates authorization from storage. CLM-A assigns {a} authorized {n} {u} [REF-0001]; CLM-B assigns {b} stored {m} {u} [REF-0002]. Neither classification implies the other. {gap} {unc}'),
}
NEGATIVES = (
    'number_change', 'label_swap', 'unit_change', 'entity_swap', 'claim_omission',
    'gap_omission', 'unsupported_addition', 'irrelevant_ref', 'missing_ref',
    'unrouted_rule', 'duplicate_ownership', 'context_ownership',
    'uncertainty_removed', 'unsupported_certainty', 'status_contradiction',
    'copied_prose', 'trailing_prose', 'code_fence',
)
SEMANTIC = ('number_change','label_swap','unit_change','entity_swap','claim_omission',
            'gap_omission','unsupported_addition','uncertainty_removed','unsupported_certainty')


def mutate_extraction(text, kind, facts):
    replacements = {
        'number_change': (str(facts['n']), str(facts['n']+3), 'DIVERGENCE', 'The first labeled quantity changed.'),
        'unit_change': (facts['u'], 'unrelated units', 'DIVERGENCE', 'The unit changed without source support.'),
        'gap_omission': (facts['gap'], '', 'OMISSION', 'The explicitly unavailable information and its question were omitted.'),
        'uncertainty_removed': (facts['unc'], '', 'OMISSION', 'The stated uncertainty was omitted.'),
        'unsupported_certainty': (facts['unc'], 'The matter is certain.', 'DIVERGENCE', 'An explicitly uncertain matter was presented as certain.'),
    }
    if kind in replacements:
        old,new,relation,reason = replacements[kind]
        changed = text.replace(old,new,1)
    elif kind in ('label_swap','entity_swap'):
        a,b = (facts['label_a'],facts['label_b']) if kind == 'label_swap' else (facts['a'],facts['b'])
        changed = text.replace(a, '\x01').replace(b,a).replace('\x01',b)
        relation,reason = 'DIVERGENCE', 'The labels or entities attached to the two statements were exchanged.'
    elif kind == 'claim_omission':
        changed = re.sub(r'CLM-B[^.!?;]*(?:[.;])?', '', text, count=1)
        relation,reason = 'OMISSION', 'The second explicit claim was omitted.'
    elif kind == 'unsupported_addition':
        changed = text + ' A supervisor approved both entries.'
        relation,reason = 'ADDITION', 'Supervisor approval was added without support.'
    else:
        raise ValueError('Unknown semantic transformation')
    if changed == text: raise ValueError('Transformation had no effect')
    return changed,relation,reason


def candidate(parent, kind):
    """Corrupt a target, retaining ancestry/split; never overwrite its gold."""
    obj = deepcopy(parent['gold_target'])
    item = obj['items'][0]
    role = parent['role']
    refkey = 'refs' if role == 'producer' else 'ref_ids'
    if kind == 'irrelevant_ref': item[refkey].append('REF-9999')
    elif kind == 'missing_ref': item[refkey].pop()
    elif kind == 'unrouted_rule':
        if role == 'auditor': item['reasoning'] += ' CONV-DISTRACTOR applies.'
        else: item['rule_id'] = 'CONV-DISTRACTOR'
    elif kind == 'duplicate_ownership': obj['items'].append(deepcopy(item))
    elif kind == 'context_ownership': item['span'] = parent['context_only_aliases'][0]
    elif kind == 'status_contradiction': item['status'] = 'empty'
    elif kind == 'copied_prose': item['draft_text'] = parent['source_text']
    elif kind == 'claim_omission': item['claims'].pop()
    elif kind == 'gap_omission': item['questions'] = []
    elif kind == 'uncertainty_removed': item['uncertainty'] = []
    elif kind == 'unsupported_certainty': item['uncertainty'] = ['Interpretation is certain.']
    elif kind == 'unsupported_addition': item['claims'].append('CLM-INVENTED')
    elif kind not in ('trailing_prose','code_fence'): raise ValueError('Unsupported candidate mutation')
    raw = json.dumps(obj, ensure_ascii=False)
    if kind == 'trailing_prose': raw += '\nThis is the correct answer.'
    if kind == 'code_fence': raw = '```json\n' + raw + '\n```'
    return dict(candidate_id=parent['example_id']+'-negative-'+kind, parent_id=parent['example_id'],
                split=parent['split'], derivation_group=parent['derivation_group'],
                transformation=kind, raw=raw, expected_accepted=False,
                provenance='authored_deterministic_corruption')


def adjudication(gold):
    return dict(state='authored_single', first_id='seed-author-assistant', first_judgment=deepcopy(gold),
                second_id=None, second_judgment=None, agreement='not_reviewed',
                final_target=deepcopy(gold), rationale='Authored against the explicit fixture facts; independent review pending.', ambiguity=False)


def record(family, split, domain, source, role, gold, relation, *, parent=None, extraction='', tags=(), refuse=False):
    span_size = source.index('CONTEXT ONLY:') if 'CONTEXT ONLY:' in source else 1200
    spans = ex.ledger(source, family, span_size)
    # Last span is visibly labeled context and cannot be claimed as owned.
    owned_spans = [s for s in spans if not s.text.startswith('CONTEXT ONLY:')]
    row = dict(example_id=family+'-'+role+'-'+(tags[0] if tags else relation.lower()),
        role=role, task_type='bounded_extraction' if role=='producer' else 'fidelity',
        abstract_relation=relation, domain=domain, document_type=DOMAINS[domain][0],
        language='en', style=PLANS[split][1], document_family=family,
        template_family=PLANS[split][0], derivation_group=family,
        paraphrase_family=family, renamed_family=PLANS[split][0], near_duplicate_family=PLANS[split][0],
        parent_id=parent, split=split, split_plan_id='split-plan-v1-before-variants',
        provenance=dict(source='newly authored synthetic fixture', rights='project_authored',
                        privacy='authored_public_synthetic', public_regression=False),
        source_text=source, extraction_text=extraction, ledger_max_chars=span_size,
        owned_aliases=[ex.wire_id(s) for s in owned_spans],
        context_only_aliases=[ex.wire_id(s) for s in spans if s not in owned_spans],
        supplied_refs=sorted(set(re.findall(r'\bREF-\d{4,}\b',source))),
        required_refs=[] if refuse or relation=='EMPTY' else ['REF-0001','REF-0002'],
        routed_rules=[], distractor_rules=['CONV-DISTRACTOR'],
        gold_target=gold, expected_refusal=refuse, expected_uncertainty=role=='producer' and relation not in ('EMPTY','INSUFFICIENT_EVIDENCE'),
        hard_negative_tags=list(tags), versions={k:VERSION for k in ('schema','task','adapter','validator')},
        adjudication=adjudication(gold), notes='Semantic fixture only; no clinical/legal advice. Public seed, not blind evidence.')
    return row


def auditor_gold(relation, reason, uncertain=False):
    return {'items':[dict(finding=relation,ref_ids=['REF-0001','REF-0002'],reasoning=reason,
                         severity='low' if relation=='MATCH' else 'medium',confidence='UNCERTAIN' if uncertain else 'CONFIDENT')]}


def schema():
    string = {'type':'string','minLength':1}
    strings = {'type':'array','items':string,'uniqueItems':True}
    fields = {k:string for k in ('example_id','task_type','domain','document_type','language','style',*GROUPS,'split_plan_id','notes')}
    fields.update(role={'enum':['producer','auditor']}, abstract_relation={'enum':['EXTRACTED','EMPTY','MATCH','DIVERGENCE','OMISSION','ADDITION','INSUFFICIENT_EVIDENCE']},
                  split={'enum':['train','dev','test','sealed_adversarial','regression']}, parent_id={'type':['string','null']},
                  ledger_max_chars={'type':'integer','minimum':1},source_text={'type':'string'},extraction_text={'type':'string'},gold_target={'type':'object'},
                  expected_refusal={'type':'boolean'},expected_uncertainty={'type':'boolean'})
    fields.update({k:strings for k in ('owned_aliases','context_only_aliases','supplied_refs','required_refs','routed_rules','distractor_rules','hard_negative_tags')})
    def obj(props): return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
    fields['versions'] = obj({k:{'const':VERSION} for k in ('schema','task','adapter','validator')})
    fields['provenance'] = obj(dict(source=string,rights=string,privacy=string,public_regression={'type':'boolean'}))
    fields['adjudication'] = obj(dict(state={'enum':['authored_single','independently_reviewed','adjudicated']},
        first_id=string,first_judgment={'type':'object'},second_id={'type':['string','null']},
        second_judgment={'type':['object','null']},agreement={'enum':['not_reviewed','agree','disagree']},
        final_target={'type':'object'},rationale=string,ambiguity={'type':'boolean'}))
    return dict(obj(fields), **{'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'shimmer:semantic-task-v1:record'})


def build():
    freeze_path=HERE/'frozen_dataset.json'
    if freeze_path.exists():
        previous=json.loads(freeze_path.read_text(encoding='utf-8'))
        if previous['version']==VERSION:
            __import__('core').verify_freeze()
            if digest((ROOT/'config/semantic_task_contract_v1.json').read_bytes())!=previous['contract_manifest_sha256']:
                raise ValueError('Frozen contract manifest changed; review and bump VERSION')
            for name,expected in previous['hashes'].items():
                if digest((HERE/name).read_bytes())!=expected:
                    raise ValueError('Frozen version changed; review and bump VERSION before rebuilding: '+name)
    # Persist allocation before constructing a single target or variant.
    allocation = [{'family':split+'-'+domain,'split':split,'template':spec[0]} for split,spec in PLANS.items() for domain in DOMAINS]
    write(HERE/'split_plan.json',dict(id='split-plan-v1-before-variants',allocation=allocation,
          seed_adversarial_is_public=True, final_blind_replacement_required=True))
    write(HERE/'record.schema.json',schema())
    rows,candidates = [],[]
    for plan in allocation:
        split,domain,family = plan['split'],plan['family'].split('-',1)[1],plan['family']
        _,a,b,u,org = DOMAINS[domain]
        # Equal values in half the families deliberately do not neutralize label/entity changes.
        n = 12 + list(DOMAINS).index(domain)*2
        m = n if list(DOMAINS).index(domain)%2 else n+7
        label_a,label_b,question,gap,unc = {
            'train':('planned','reported','What is the observation date?','The observation date is unavailable.', 'The interpretation of the second entry remains unresolved.'),
            'dev':('proposed','amended','When does the amendment take effect?','No effective period is specified.', 'It is unclear whether the amendment was ratified.'),
            'test':('accepted','declined','Who recorded this interview?','The recorder is not identified.', 'The attribution of the marginal note is uncertain.'),
            'sealed_adversarial':('authorized','stored','Where are these objects located?','The storage location has not been supplied.', 'The scope of the authorization is ambiguous.'),
        }[split]
        facts = dict(a=a,b=b,u=u,org=org,n=n,m=m,label_a=label_a,label_b=label_b,gap=gap+' '+question,unc=unc)
        main = PLANS[split][2].format(**facts)
        source = main+'\n\nCONTEXT ONLY: neighboring record has REF-9999 and CONV-DISTRACTOR; neither is routed evidence or a policy for this task.'
        spans = ex.ledger(source,family,len(main)+2)
        target = {'items':[dict(span=ex.wire_id(s),claims=re.findall(r'\bCLM-[A-Za-z0-9-]+',s.text),
                   questions=[question],uncertainty=[facts['unc']],status='extracted',refs=['REF-0001','REF-0002'])
                   for s in spans if not s.text.startswith('CONTEXT ONLY:')]}
        producer = record(family,split,domain,source,'producer',target,'EXTRACTED')
        rows.append(producer)
        match = record(family,split,domain,source,'auditor',auditor_gold('MATCH',
            'Both labeled statements, the explicitly unavailable information and its question, and the stated uncertainty are preserved.'),
            'MATCH',parent=producer['example_id'],extraction=main)
        rows.append(match)
        for kind in SEMANTIC:
            changed,relation,reason = mutate_extraction(main,kind,facts)
            rows.append(record(family,split,domain,source,'auditor',auditor_gold(relation,reason),relation,
                               parent=match['example_id'],extraction=changed,tags=[kind]))
        for role in ('producer','auditor'):
            incomplete = source if role=='auditor' else (
                PLANS[split][0]+' / '+org+': the owned text is an unreadable fragment; semantic content cannot be determined.')
            row = record(family,split,domain,incomplete,role,{'items':[],'status':'refused'},
                         'INSUFFICIENT_EVIDENCE',parent=producer['example_id'],extraction=PLANS[split][0]+' / '+org+': [extraction incomplete]' if role=='auditor' else '',refuse=True)
            rows.append(row)
        empty_source = PLANS[split][0]+' / '+org+': divider only.'
        empty_target = {'items':[dict(span=ex.wire_id(s),claims=[],questions=[],uncertainty=[],status='empty',refs=[])
                                  for s in ex.ledger(empty_source,family)]}
        rows.append(record(family,split,domain,empty_source,'producer',empty_target,'EMPTY',parent=producer['example_id']))
        for kind in NEGATIVES:
            if kind in ('number_change','label_swap','unit_change','entity_swap'):
                # The semantic mutated input is labeled above; this wrong MATCH
                # candidate tests whether the evaluator detects the lost relation.
                derived = next(r for r in rows if r['document_family']==family and r['hard_negative_tags']==[kind])
                obj = deepcopy(derived['gold_target']);obj['items'][0]['finding']='MATCH';obj['items'][0]['severity']='low'
                candidates.append(dict(candidate_id=derived['example_id']+'-wrong-match',parent_id=derived['example_id'],
                    split=split,derivation_group=family,transformation=kind,raw=json.dumps(obj),expected_accepted=False,
                    provenance='authored_deterministic_corruption'))
            else:
                candidates.append(candidate(match if kind=='unrouted_rule' else producer,kind))
    write(HERE/'seed.json',rows)
    write(HERE/'negative_candidates.json',candidates)
    write(HERE/'transformations.json',dict(version=VERSION,types=list(NEGATIVES),
          semantic_input_variants=list(SEMANTIC),counts=dict(Counter(c['transformation'] for c in candidates)),
          construction='Split allocation written before any variant. Gold inputs transformed separately from negative outputs.'))
    write(HERE/'split_manifest.json',{s:[r['example_id'] for r in rows if r['split']==s] for s in PLANS})
    write(HERE/'family_ancestry.json',[{k:r[k] for k in ('example_id','parent_id','split',*GROUPS)} for r in rows])
    manifest = dict(version=VERSION, schema_version=VERSION,prompt_task_version=VERSION,adapter_version=VERSION,validator_version=VERSION,
        authority='scripts/compact_contracts.py; scripts/bounded_extraction.py; config/agent_contracts.json',
        hashes={p:digest((ROOT/p).read_bytes()) for p in ('scripts/compact_contracts.py','scripts/bounded_extraction.py','scripts/agent_wrapper.py','config/agent_contracts.json')},
        prompt_hashes={role:digest(prompt.encode('utf-8')) for role,prompt in [('producer',cc.PRODUCER),('auditor',cc.AUDITOR)]},
        model_owned=dict(producer=['span selection','claims','questions','uncertainty','status','refs'],auditor=['finding','ref_ids','reasoning','severity','confidence']),
        python_owned=['source text','source offsets','source order','document identity','provenance','agent identity','paragraph routing'],
        producer_semantics={'claims':'All explicit CLM identifiers, multiple per owned alias. No prose reconstruction.',
            'questions':'Explicit questions and unavailable information as questions.', 'uncertainty':'Unresolved interpretation, never invented certainty.',
            'status':'extracted iff semantic arrays populated, otherwise examined empty.', 'refs':'Exact supplied applicable evidence IDs only.'},
        auditor_semantics={'finding':'Fidelity MATCH/DIVERGENCE/OMISSION/ADDITION; unequal original values do not imply divergence.',
            'reasoning':'Concise source/extraction comparison; no unsupported policy attribution.',
            'ref_ids':'Every required reference selected from supplied set.', 'confidence':'CONFIDENT or UNCERTAIN',
            'severity':'low/medium/high; MATCH requires low'},
        refusal={'wire':{'items':[],'status':'refused'},'evaluation_state':'semantic_refusal','production_accepted':False},
        completeness='Every owned alias exactly once. Context excluded. Partial coverage and truncated output not accepted.',
        reconstruction='Use existing bounded_extraction ledger/hydrate; exact original text and order.',
        routing='Python stamps identity. Fidelity tasks route no policy rules.',
        statuses=__import__('core').STATES, error_classes=__import__('core').ERRORS)
    write(ROOT/'config/semantic_task_contract_v1.json',manifest)
    write(HERE/'acceptance_registration.template.json',dict(state='unregistered', registered_before_run=False,
          rationale=None,dataset_sha256=None,minimum_families=None,minimum_contract_rate=None,
          goals=['near-perfect task semantics','zero truncation','evidence/governance integrity'],
          note='Independent adjudication, final blind dataset, uncertainty bounds and prospective criteria required; seed scores cannot accept a model.'))
    files = [p for p in HERE.iterdir() if p.suffix in ('.json','.py') and p.name != 'frozen_dataset.json']
    write(HERE/'frozen_dataset.json',dict(version=VERSION,hashes={p.name:digest(p.read_bytes()) for p in sorted(files)},
          contract_manifest_sha256=digest((ROOT/'config/semantic_task_contract_v1.json').read_bytes()),
          notice='Public seed freeze. A target, evaluator or split change requires explicit review and a new version before training.'))
    print(json.dumps(dict(examples=len(rows),negative_candidates=len(candidates))))


if __name__ == '__main__':
    build()
