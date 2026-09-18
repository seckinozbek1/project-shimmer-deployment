"""Task-scoped wire contracts; strict adaptation precedes canonical validation.

Identity and source reconstruction are routing facts. Claims, gaps, uncertainty,
judgments and selected evidence always come from the response, never from routing.
"""
from functools import lru_cache
import json
from pathlib import Path
import re

import bounded_extraction as extraction

ROOT = Path(__file__).resolve().parents[1]
PROMPT_DECLARATION = ROOT / 'config/compact_extraction_prompt.json'

PRODUCER = '''Return only one JSON object: {"items":[{"span":"s0","claims":[],"questions":[],"uncertainty":[],"status":"empty","refs":[]}]}.
Exactly one item per owned source_spans alias; multiple observations belong in its arrays.
claims: every explicit CLM-* id. questions: explicit questions and missing information as questions. uncertainty: unresolved interpretation, if any.
status: extracted if any claims/questions/uncertainty, otherwise empty. Empty means examined, not omitted. If unable to complete use {"items":[],"status":"refused"}.
refs: select supplied REF-* evidence for this span. Do not invent ids. Do not judge context-only spans.
Python owns source, offsets, identity and order: return the alias once in span; never copy prose or emit draft_text/section_id. No other fields.'''

AUDITOR = '''Compare ORIGINAL with EXTRACTION for fidelity, not one original figure against another. Preserve each figure's label and any missing-information statement. Different quantities in the original are not themselves extraction errors.
MATCH means extraction preserves the original; DIVERGENCE means changed content; ADDITION means unsupported content; OMISSION means missing content. No policy rule or numeric threshold is supplied: do not attribute a rule or judge compliance.
Return only {"items":[{"finding":"MATCH","ref_ids":["REF-0001","REF-0002"],"reasoning":"Concise evidence-based comparison","severity":"low","confidence":"CONFIDENT"}]}.
Select evidence refs supporting the comparison, including every required ref. Explain what was preserved or changed, including information gaps. Do not copy the source. MATCH requires low severity. Use UNCERTAIN for uncertain interpretation; insufficient evidence or incomplete extraction requires {"items":[],"status":"refused"}. Empty items without refusal is allowed only when both inputs are empty.
One routed comparison item; no extra fields. Python supplies agent/doc/paragraph identity. No finding_record, rule_id or invented citation. Complete the JSON before stopping.'''


def arrays(item, fields):
    for field in fields:
        value = item.get(field)
        if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
            raise ValueError('Explicit string arrays required')
        if len(set(value)) != len(value):
            raise ValueError('Duplicate semantic observation')


def envelope(obj):
    if not isinstance(obj, dict) or set(obj) != {'items'} or not isinstance(obj['items'], list):
        raise ValueError('Complete compact items envelope required; refusal is not acceptance')
    return obj['items']


def producer(obj, owned, doc, citable=None):
    """`citable` is Python's own decision of which indexed passages lie inside which
    owned span (bounded_extraction.grounding): a ref is grounded when it is one of
    those, or when its id is written inside the span's text as the training spans
    wrote theirs. A ref that is neither (an id the index does not hold, or one that
    names a passage of another span) is refused as before."""
    items = envelope(obj)
    by_alias = {extraction.wire_id(s): s for s in owned}
    seen = set()
    canonical = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {'span','claims','questions','uncertainty','status','refs'}:
            raise ValueError('Exact compact extraction fields required')
        alias = item['span']
        if not isinstance(alias, str) or alias not in by_alias or alias in seen:
            raise ValueError('Invalid or duplicate owned alias')
        seen.add(alias)
        arrays(item, ('claims','questions','uncertainty','refs'))
        span = by_alias[alias]
        if not set(item['claims']) <= set(re.findall(r'\bCLM-[A-Za-z0-9-]+', span.text)):
            raise ValueError('Ungrounded claim id')
        grounded = set(re.findall(r'\bREF-\d{4,}\b', span.text)) | set((citable or {}).get(alias, ()))
        if not set(item['refs']) <= grounded:
            raise ValueError('Ungrounded extraction evidence')
        semantic = any(item[k] for k in ('claims','questions','uncertainty'))
        if item['status'] != ('extracted' if semantic else 'empty'):
            raise ValueError('Explicit empty/extracted status mismatch')
        canonical.append(dict(section_id=alias, draft_text=alias, extraction_method='source_span',
                              claims_referenced=item['claims'], open_questions=item['questions'],
                              uncertainty=item['uncertainty'], extraction_status=item['status'],
                              ref_ids=item['refs'], ref=item['refs'][0] if item['refs'] else 'document-level',
                              kind='extraction', confidence='UNCERTAIN'))
    # The original hydration validator still enforces full coverage and order.
    return extraction.hydrate(dict(agent='PROCESSOR', doc_id=doc, items=canonical), owned, doc)


def auditor(obj, doc, required_refs, available_refs, *, paragraph=1, empty_input=False):
    items = envelope(obj)
    if len(items) != (0 if empty_input else 1):
        raise ValueError('Incomplete routed comparison')
    result = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {'finding','ref_ids','reasoning','severity','confidence'}:
            raise ValueError('Exact fidelity fields required; rule attribution is not routed')
        arrays(item, ('ref_ids',))
        if not set(required_refs) <= set(item['ref_ids']) <= set(available_refs):
            raise ValueError('Missing or ungrounded fidelity evidence')
        if item['finding'] not in {'MATCH','DIVERGENCE','ADDITION','OMISSION'}:
            raise ValueError('Invalid fidelity judgment')
        if item['confidence'] not in {'CONFIDENT','UNCERTAIN'} or item['severity'] not in {'low','medium','high'}:
            raise ValueError('Invalid confidence or severity')
        if item['finding'] == 'MATCH' and item['severity'] != 'low':
            raise ValueError('MATCH severity mismatch')
        if not isinstance(item['reasoning'], str) or not item['reasoning'].strip():
            raise ValueError('Evidence comparison reason required')
        if re.search(r'\bCONV-[A-Za-z0-9-]+', item['reasoning']):
            raise ValueError('Ungrounded rule in fidelity reason')
        if not set(re.findall(r'\bREF-\d{4,}\b', item['reasoning'])) <= set(item['ref_ids']):
            raise ValueError('Unselected citation in fidelity reason')
        result.append(dict(item, paragraph=paragraph, kind='finding',
                           ref=item['ref_ids'][0] if item['ref_ids'] else 'document-level'))
    return dict(agent='VERIFIER', doc_id=doc, items=result)


def bind_producer(wrapper, owned, doc, *, citable=None, messages=None):
    """`messages` = (system, user, supplied) from validated_messages: the wrapper then
    sends exactly those two messages through the model's chat template (the shape
    checkpoint 168 was evaluated on) instead of the wide agent prompt, and records
    the supplied ref ids as what was rendered."""
    if wrapper.name != 'PROCESSOR':
        raise ValueError('Extraction routing mismatch')
    wrapper._compact_role = '- Extract semantic fields from owned source spans; Python reconstructs source.'
    wrapper._compact_contract = PRODUCER
    wrapper._compact_grounding = dict(citable or {})
    wrapper._source_adapter = lambda obj: producer(obj, owned, doc, wrapper._compact_grounding)
    wrapper._owned_source_spans = tuple(owned)
    if messages is not None:
        system, user, supplied = messages
        wrapper._compact_messages = (system, user)
        wrapper._compact_rendered = dict(reference_ids=list(supplied), convention_ids=[],
                                         bus_messages_rendered=0, bus_messages_dropped=0,
                                         convention_text_truncated=False, reference_text_truncated=False)


@lru_cache(maxsize=1)
def prompt_declaration():
    """config/compact_extraction_prompt.json: the validated prompt shape, read once."""
    return json.loads(PROMPT_DECLARATION.read_text(encoding='utf-8'))


def validated_system():
    """The system message checkpoint 168 was evaluated under: the compact contract
    followed by the frozen semantic policy, read from the declaration, never typed here."""
    return PRODUCER + prompt_declaration()['system_suffix']


def canonical(value):
    """The evaluation runtime's serialisation of a user payload: sorted keys, compact separators."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def validated_payload(source_spans, context_spans, supplied_refs, *, required_refs=(), routed_rules=()):
    """The user object of the validated shape. `source_spans` and `context_spans` are
    [(alias, text)]; the key set is exactly the one every DEV prompt carried."""
    declaration = prompt_declaration()
    return dict(context_only_spans=[dict(alias=alias, text=text) for alias, text in context_spans],
                production_contract=declaration['production_contract'],
                required_refs=list(required_refs), role=declaration['role'],
                routed_rules=list(routed_rules),
                source_spans=[dict(alias=alias, text=text) for alias, text in source_spans],
                supplied_refs=list(supplied_refs))


def validated_messages(text, owned, all_spans, entries):
    """(system, user, citable, supplied) for one bounded partition, in the validated
    shape: every indexed passage inside a span is marked with its own id at its end,
    the boundary context keeps the 400-character clip the wide payload used, and the
    refs the model may cite for an owned span are exactly the passages Python located
    inside it. Nothing else (no reference passages, rules, bus, constitution, briefs,
    anchor) reaches the model on this path."""
    citable, markers, _ = extraction.grounding(text, all_spans, entries)
    indices = {s.id: i for i, s in enumerate(all_spans)}
    first, last = indices[owned[0].id], indices[owned[-1].id]
    shown, source, context = [], [], []
    for span in owned:
        alias = extraction.wire_id(span)
        source.append((alias, extraction.annotate(span.text, markers.get(alias, []))))
        shown.extend(ref for _, ref in markers.get(alias, []))
    for i, span in enumerate(all_spans):
        if i not in {first - 1, last + 1}:
            continue
        alias = extraction.wire_id(span)
        window, kept = extraction.clip_markers(span.text, markers.get(alias, []), tail=i < first)
        context.append((alias, extraction.annotate(window, kept)))
        shown.extend(ref for _, ref in kept)
    supplied = sorted(set(shown))
    payload = validated_payload(source, context, supplied)
    owned_citable = {extraction.wire_id(s): list(citable.get(extraction.wire_id(s), [])) for s in owned}
    return validated_system(), canonical(payload), owned_citable, supplied


def bind_auditor(wrapper, doc, refs, *, paragraph=1, empty_input=False):
    if wrapper.name != 'VERIFIER':
        raise ValueError('Fidelity routing mismatch')
    wrapper._compact_role = '- Compare original content with extraction for fidelity only.'
    wrapper._compact_contract = AUDITOR
    wrapper._source_adapter = lambda obj: auditor(obj, doc, refs, refs, paragraph=paragraph, empty_input=empty_input)


def producer_prompt(owned, all_spans, doc):
    return PRODUCER + '\n' + json.dumps(extraction.payload(dict(document_id=doc), owned, all_spans))


def auditor_prompt(source, parsed, refs):
    # Retain semantic extraction fields and exact reconstructed source; omit only
    # runtime identity/provenance already supplied by the routed comparison.
    relevant = [{k: i[k] for k in ('draft_text','claims_referenced','open_questions','uncertainty') if k in i}
                for i in parsed['items']]
    return AUDITOR + '\n' + json.dumps(dict(required_refs=refs, ORIGINAL=source, EXTRACTION=relevant))
