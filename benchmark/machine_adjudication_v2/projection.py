"""Strict legacy wording adapter, registered before V2 gold is opened.

Reviewer atoms use atoms.normalize directly. This adapter only bridges legacy
authored free-form fields to that same typed ontology after the label freeze.
Unknown qualifiers are not silently discarded by keyword matching.
"""
import re
import atoms

GAP_WORDS=set('the a is was are missing unknown unavailable not provided supplied specified absent unspecified what when does it this take effect of date recording reporting report observation effective time period recorded recorder who unnamed by author amendment its question gap needed'.split())
UNCERTAINTY_WORDS=set('the a is was remains unclear whether were uncertain uncertainty unresolved unknown interpretation second entry ratification ratified amendment conflict conflicting contradictions contradictory statements assertions assignments source preserved'.split())


def project(wording,text,span,refs,kind):
    value=atoms.norm(wording)
    words=re.findall(r'[a-z]+',value)
    allowed=GAP_WORDS if kind=='gap' else UNCERTAINTY_WORDS
    if not words or set(words)-allowed or re.search(r'\d',value):
        raise ValueError('Unsupported legacy wording or qualifier; no automatic equivalence')
    if kind=='gap' and any(x in value for x in ('recorder','who recorded','recorded by','author')):
        candidates=[a for a in atoms.source_atoms(text,span,refs)[0] if a['target']=='recorder']
        if len(candidates)!=1:raise ValueError('Unsupported recorder referent')
        return dict(candidates[0],wording=wording)
    return atoms.wording_to_atoms(wording,text,span,refs,kind)
