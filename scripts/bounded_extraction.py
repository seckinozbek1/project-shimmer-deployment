"""Lossless source ledger and compact PROCESSOR wire format.

Source offsets cover the entire input, including preambles and table surrounds
not represented by pairing_map units. Unit identity is reused, never renumbered.
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
