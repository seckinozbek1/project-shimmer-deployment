"""Generic structural segmentation; never infer a proposition from a title."""
import re

# Finite verbs/copulas, explicit questions and assertion identifiers are content.
# Participles alone (e.g. a label ending in 'recorded') are not finite verbs.
FINITE = re.compile(r'\b(?:is|are|was|were|remains?|did|does|do|has|have|had|can|could|may|might|must|shall|should|will|would|appears?|occurred|happened|exists?|came|comes|followed|follows)\b', re.I)

def proposition(text):
    value=text.strip().strip('#| ')
    return bool(re.search(r'\bCLM-[A-Za-z0-9-]+',value) or FINITE.search(value) or
                re.match(r'(?:who|what|when|where|which|whether|how)\b.*\?',value,re.I))

def segments(text):
    """Return source-exact pieces with structural classification, without context."""
    result=[]
    for match in re.finditer(r'[^\n]+',text):
        line=match.group()
        # Colon prefixes and table cells are structural positions. A finite
        # proposition is retained even in those positions.
        for cell in re.finditer(r'[^|]+',line):
            piece=cell.group();offset=match.start()+cell.start()
            colon=piece.find(':')
            parts=[(piece,offset)]
            if colon>=0 and not proposition(piece[:colon]):
                parts=[(piece[:colon],offset),(piece[colon+1:],offset+colon+1)]
            for part,start in parts:
                for clause in re.finditer(r'.+?(?:[.!?;](?=\s|$)|$)',part):
                    raw=clause.group();clean=raw.strip()
                    if not clean:continue
                    pos=start+clause.start()+len(raw)-len(raw.lstrip())
                    content=proposition(clean)
                    result.append(dict(text=clean,start=pos,end=pos+len(clean),
                                       role='proposition' if content else 'structural_only'))
    return result

def semantic_segments(text):
    return [x['text'] for x in segments(text) if x['role']=='proposition']
