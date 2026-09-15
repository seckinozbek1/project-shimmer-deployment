"""Finite, source-bound semantic atom normalizer; no fuzzy matching or gold."""
import re

FIELDS={'type','subject','target','scope','span','refs','origin','unit'}
TARGET_ALIASES={'date of report':'reporting_date','report date':'reporting_date','reporting date':'reporting_date',
 'recording date':'recording_date','observation date':'observation_date','effective time':'effective_time',
 'effective period':'effective_time','recorded by':'recorder','recorder':'recorder','interpretation':'interpretation',
 'ratification':'ratification','assertions':'assertions'}


def norm(s):return ' '.join(s.lower().replace('_',' ').split())


def normalize(atom):
    if set(atom)-FIELDS-{'wording','source_quote'} or not FIELDS<=set(atom):raise ValueError('Exact typed atom fields required')
    if atom['type'] not in ('missing_information','unknown','conflicting'):raise ValueError('Unsupported atom type')
    if atom['origin']!='source_explicit':raise ValueError('Inferred atoms are not source labels')
    if not all(isinstance(atom[k],str) and atom[k] for k in FIELDS-{'refs','unit'}):raise ValueError('Atom strings required')
    if not isinstance(atom['refs'],list) or not all(isinstance(x,str) for x in atom['refs']):raise ValueError('Atom refs required')
    if atom['unit'] is not None and not isinstance(atom['unit'],str):raise ValueError('Unit must be explicit string or null')
    target=TARGET_ALIASES.get(norm(atom['target']),atom['target'])
    return dict(type=atom['type'],subject=atom['subject'],target=target,scope=atom['scope'],span=atom['span'],
                refs=sorted(set(atom['refs'])),origin=atom['origin'],unit=atom['unit'])


def make(kind,target,span,subject='owned_record',refs=(),wording=''):
    return dict(type=kind,subject=subject,target=target,scope='owned_record',span=span,refs=list(refs),origin='source_explicit',unit=None,wording=wording)


def source_atoms(text,span,refs):
    """Recognize only explicit constructions in the finite supported source vocabulary.

    Output is used for grounding/diagnostic mapping, not to fill agent responses.
    Unknown constructions do not acquire an invented default semantic label.
    """
    t=norm(text);g=[];u=[]
    if 'observation date' in t and any(x in t for x in ('unavailable','what is')):g.append(make('missing_information','observation_date',span,refs=refs))
    elif any(x in t for x in ('date is absent','when was this recorded','recording date is unavailable')):g.append(make('missing_information','recording_date',span,refs=refs))
    elif any(x in t for x in ('reporting date is unavailable','date of report is not provided')):g.append(make('missing_information','reporting_date',span,refs=refs))
    if any(x in t for x in ('effective time is missing','no effective period is specified','when does the amendment take effect','when does it take effect')):
        g.append(make('missing_information','effective_time',span,subject='amendment' if 'amendment' in t else 'owned_record',refs=refs))
    if any(x in t for x in ('recorder is unnamed','who recorded it')):g.append(make('missing_information','recorder',span,refs=refs))
    if 'interpretation' in t and any(x in t for x in ('uncertain','unresolved')):
        u.append(make('unknown','interpretation',span,subject='second_entry' if 'second entry' in t else 'owned_record',refs=refs))
    if 'unclear whether' in t and 'ratified' in t:u.append(make('unknown','ratification',span,subject='amendment',refs=refs))
    if 'statements conflict' in t:u.append(make('conflicting','assertions',span,refs=refs))
    return g,u


def material(atoms):
    import json
    return sorted({json.dumps(normalize(a),sort_keys=True,separators=(',',':')) for a in atoms})


def ground(atom,text,span,refs):
    value=normalize(atom)
    if value['span']!=span or value['refs']!=sorted(set(refs)):raise ValueError('Atom ownership/evidence mismatch')
    g,u=source_atoms(text,span,refs)
    if material([atom])[0] not in material(g+u):raise ValueError('Atom is not licensed by explicit supported source semantics')
    return True


def wording_to_atoms(wording,text,span,refs,kind):
    """Finite post-freeze authored wording projection; ambiguous/unknown forms fail.

    Unqualified date may bind only to one source-supported date/time concept.
    Explicit referents must agree. No similarity threshold, stemming model or
    post-hoc corpus-specific answer map is used.
    """
    t=norm(wording);g,u=source_atoms(text,span,refs);available=g if kind=='gap' else u
    if kind=='gap':
        if any(x in t for x in ('recorder','who recorded','recorded by','author')):targets={'recorder'}
        elif any(x in t for x in ('effect','time','date','period','when')):targets={'effective_time','recording_date','observation_date','reporting_date'}
        else:raise ValueError('Unsupported gap wording')
        if 'observation' in t:targets={'observation_date'}
        elif 'report' in t:targets={'reporting_date'}
        elif 'recording' in t or 'recorded' in t:targets={'recording_date'}
        elif 'effect' in t:targets={'effective_time'}
    else:
        if any(x in t for x in ('conflict','contradict')):targets={'assertions'}
        elif any(x in t for x in ('ratif','amendment')):targets={'ratification'}
        elif any(x in t for x in ('interpret','uncertain','unresolved')):targets={'interpretation'}
        else:raise ValueError('Unsupported uncertainty wording')
    candidates=[a for a in available if a['target'] in targets]
    if 'second entry' in t:candidates=[a for a in candidates if a['subject']=='second_entry']
    if len(candidates)!=1:raise ValueError('Ambiguous or unsupported semantic projection')
    return dict(candidates[0],wording=wording)
