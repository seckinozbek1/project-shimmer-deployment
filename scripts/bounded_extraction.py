"""Lossless source ledger and compact PROCESSOR wire format.

Source offsets cover the entire input, including table surrounds not represented by
pairing_map units and a preamble the splitter makes no unit of. Unit identity is
reused, never renumbered: a document's preamble unit (u00, added 2026-09-19) owns the
same span it always occupied, with the same identity and offsets, measured on every
corpus document.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json

from pairing_map import split_units


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Span:
    id: str
    start: int
    end: int
    unit_id: str
    unit_index: int | None
    text: str


def wire_id(span):
    """A short offset alias within one document; full hashes stay in the ledger."""
    return "s%x" % span.start


@lru_cache(maxsize=4)
def ledger(text, document_id, max_chars=1200):
    if max_chars < 1:
        raise ValueError("Positive span size required")
    units = split_units(text, document_id=document_id)
    anchors = []
    cursor = 0
    for unit in units:
        needle = unit["text"] if unit["kind"] != "row" else unit["text"].splitlines()[-1]
        start = text.find(needle, cursor)
        if start < 0:
            raise ValueError("Cannot map source unit without guessing")
        anchors.append((start, start+len(needle), unit))
        cursor = start + len(needle)
    boundaries = sorted({0, len(text)} | {x for a,b,u in anchors for x in (a,b)})
    intervals = []
    for left, right in zip(boundaries, boundaries[1:]):
        owner = next((u for a,b,u in anchors if a <= left and right <= b), None)
        # Separators belong to the preceding source span, without another
        # semantic question about blank lines or a second unit numbering scheme.
        if owner is None and not text[left:right].strip() and intervals:
            previous_left,_,previous_owner=intervals[-1]
            intervals[-1]=(previous_left,right,previous_owner)
        else:
            intervals.append((left,right,owner))
    spans = []
    for left,right,owner in intervals:
        for start in range(left, right, max_chars):
            end = min(start+max_chars, right)
            identity = digest([document_id, text[start:end], start, end])
            spans.append(Span(identity, start, end, owner["unit_id"] if owner else "",
                              owner["index"] if owner else None, text[start:end]))
    assert "".join(s.text for s in spans) == text
    return tuple(spans)


def partitions(spans, size=4):
    if size < 1:
        raise ValueError("Positive partition size required")
    return [tuple(spans[i:i+size]) for i in range(0, len(spans), size)]


def payload(base, owned, all_spans):
    indices = {s.id: i for i,s in enumerate(all_spans)}
    first, last = indices[owned[0].id], indices[owned[-1].id]
    context = [s for i,s in enumerate(all_spans) if i in {first-1,last+1}]
    return dict(task="bounded_source_extraction", document_id=base.get("document_id", ""),
                document_name=base.get("document_name", ""),
                structural_inventory=base.get("structural_inventory", []),
                source_spans=[dict(span_id=wire_id(s), text=s.text) for s in owned],
                boundary_context=[dict(span_id=wire_id(s), text=s.text[-400:] if indices[s.id]<first else s.text[:400],
                                       context_only=True) for s in context],
                instructions="Use the compact extraction contract. Every owned alias needs one item; "
                "boundary_context is not owned. Python reconstructs source text.")


def hydrate(obj, owned, document_id):
    if not isinstance(obj, dict) or obj.get("agent") != "PROCESSOR" or obj.get("doc_id") != document_id:
        raise ValueError("Partition envelope identity mismatch")
    items = obj.get("items")
    if not isinstance(items, list):
        raise ValueError("Partition items missing")
    by_id = {wire_id(s): s for s in owned}
    seen = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Partition item is not an object")
        key = item.get("section_id")
        if key not in by_id or item.get("draft_text") != key:
            raise ValueError("Source span missing or context-only span claimed")
        if key in seen and seen[key] != item:
            raise ValueError("Conflicting duplicate source span")
        for field in ("open_questions", "claims_referenced"):
            if not isinstance(item.get(field), list) or any(not isinstance(x,str) for x in item[field]):
                raise ValueError("Semantic extraction fields must be explicit arrays")
        seen[key] = item
    if set(seen) != set(by_id):
        raise ValueError("Incomplete partition coverage")
    restored = []
    for span in owned:
        item = dict(seen[wire_id(span)], section_id=span.id, draft_text=span.text, source_span_id=span.id,
                    source_start=span.start, source_end=span.end, unit_id=span.unit_id,
                    source_hash=digest(span.text), provenance="source_span_reconstruction",
                    item_id="PROCESSOR:" + document_id + ":" + span.id, revision=1)
        if span.unit_index is not None:
            item["unit_index"] = span.unit_index
        restored.append(item)
    return dict(obj, items=restored)


def merge(results, document_id):
    """Incomplete partitions never become an accepted whole-document extraction."""
    good = [r for r in results if r.get("ok") and r.get("truncated") is False]
    complete = len(good) == len(results)
    items = [item for r in good for item in r["parsed"]["items"]]
    items.sort(key=lambda x: (x["source_start"], x["source_end"], x["source_span_id"]))
    if len({x["source_span_id"] for x in items}) != len(items):
        raise ValueError("Duplicate partition output")
    return dict(ok=complete, agent="PROCESSOR", parsed=dict(agent="PROCESSOR", doc_id=document_id, items=items),
                truncated=any(r.get("truncated") is True for r in results),
                complete=complete, item_count=len(items), error=None if complete else "incomplete_extraction",
                partition_calls=[r.get("call_id") for r in results],
                source_ownership=[entry for r in good for entry in r.get('source_ownership', [])],
                missing_partitions=[i for i,r in enumerate(results) if r not in good])


def _entry_field(entry, name, default=None):
    if isinstance(entry, dict):
        return entry.get(name, default)
    return getattr(entry, name, default)


def grounding(text, spans, entries):
    """Which indexed passages lie inside which source span, decided by Python from
    the reference index, never from the model or from prose.

    Returns (citable, markers, supplied):
      citable:  {alias: [ref ids of every indexed passage located inside that span,
                 every copy of the document included]}
      markers:  {alias: [(offset_in_span, ref_id), ...]} one marker per passage, the
                operational copy's id preferred, at the passage's end
      supplied: sorted ref ids that appear in a marker

    The compact validator's grounding rule used to accept a ref only when its id was
    written inside the span's own text, which the training spans carried inline and
    no real document does (v5: 0 REF literals in the document, so every non-empty
    refs array was refused). An entry is placed by its paragraph index in the same
    paragraph split the index used (reference_builder.paragraph_ranges) and must
    match that paragraph's first line; anything that does not fit is skipped, never
    guessed.
    """
    from reference_builder import paragraph_ranges
    ranges = paragraph_ranges(text)
    citable = {wire_id(s): [] for s in spans}
    passages = {}
    for entry in entries or ():
        location = _entry_field(entry, "location") or {}
        index = location.get("paragraph") if isinstance(location, dict) else None
        ref_id = _entry_field(entry, "ref_id")
        if not isinstance(index, int) or isinstance(index, bool) or not (1 <= index <= len(ranges)):
            continue
        if not isinstance(ref_id, str) or not ref_id:
            continue
        start, end, paragraph = ranges[index - 1]
        excerpt = str(_entry_field(entry, "text_excerpt") or "")
        anchor = excerpt.splitlines()[0].strip() if excerpt.strip() else ""
        if not anchor or not paragraph.startswith(anchor):
            continue
        span = next((s for s in spans if s.start <= start < s.end), None)
        if span is None:
            continue
        alias = wire_id(span)
        if ref_id not in citable[alias]:
            citable[alias].append(ref_id)
        offset = min(end, span.end) - span.start
        passages.setdefault((alias, offset), []).append(entry)
    markers = {alias: [] for alias in citable}
    for (alias, offset), group in sorted(passages.items()):
        preferred = sorted(group, key=lambda e: (_entry_field(e, "input_type") != "operational",
                                                 str(_entry_field(e, "ref_id"))))[0]
        markers[alias].append((offset, _entry_field(preferred, "ref_id")))
    supplied = sorted({ref for group in markers.values() for _, ref in group})
    return citable, markers, supplied


def annotate(text, markers):
    """`text` with ' (REF-NNNN)' at the end of each indexed passage, the way the
    checkpoint's training spans carried their references. Prompt text only: the
    source the pipeline reconstructs is the ledger's, never this."""
    out = text
    for offset, ref_id in sorted(markers, reverse=True):
        at = min(max(int(offset), 0), len(out))
        # The marker sits inside the sentence's final full stop, as in training.
        if at > 0 and out[at - 1] == ".":
            at -= 1
        out = out[:at] + " (" + ref_id + ")" + out[at:]
    return out


def clip_markers(text, markers, *, tail, limit=400):
    """The boundary-context clip the wide payload used (the previous span's last
    `limit` characters, the next span's first `limit`), with the markers that fall
    inside the window re-based to it; a marker outside the window is dropped."""
    if tail:
        window = text[-limit:]
        shift = len(text) - len(window)
        kept = [(offset - shift, ref) for offset, ref in markers if offset - shift >= 0]
    else:
        window = text[:limit]
        kept = [(offset, ref) for offset, ref in markers if offset <= len(window)]
    return window, kept
