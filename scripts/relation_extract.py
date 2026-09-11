"""Relations between provisions, the deterministic baseline (ontology chain, job 2).

WHAT THIS IS FOR. The graph records where a finding came from and never that one
provision relates to another. That missing relation is exactly what the long-range
case needs: a term defined at the start of a document and used at the end, which
the adjacent-neighbour mechanism explicitly does not reach (it carries one unit's
immediate neighbours and nothing further).

TWO MECHANISMS, BOTH DETERMINISTIC, BOTH IN THIS MODULE:

  1. CROSS-REFERENCE EXTRACTION. One unit's text names another unit. Every pattern
     is the OPERATOR'S, read from config/relation_patterns.json; this module holds
     no pattern of its own and cannot (S5: no domain-specific content in scripts/).
     A reference is written differently in every domain, language and house style,
     so a pattern written once in code against the domain of the day is the mistake
     the vocabulary probe exists to catch. With no patterns declared, nothing is
     extracted, which is an honest nothing.

  2. EMBEDDING SIMILARITY over units of the same document. No pattern, so no
     vocabulary at all. Only pairs at least `min_units_apart` apart are considered,
     because a unit is trivially similar to the one beside it and the neighbour
     mechanism already carries that case. The ranker is INJECTED, never imported, so
     this module never depends on an embedding store existing and never loads a
     model itself.

WHAT A RELATION IS AND IS NOT. It says one unit names, or reads like, another. It
does NOT say the two agree, conflict, or bear on each other's correctness, and it is
not evidence for any finding. It is a structural candidate, recorded so that
something downstream can later be scored on it.

NOT MEASURED. Neither mechanism has been scored on any corpus. They are proved on
fixtures in the verify gate and nothing more. The operator scores both on the
long-range corpus after the move to a GPU box and decides between them then. Nothing
here claims either works.

Deterministic, local, stdlib only, no model calls in this module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATTERNS_PATH = ROOT / "config" / "relation_patterns.json"

# The relation types this module can mint. Both are STRUCTURAL: neither asserts that
# the two units agree or conflict, only that one names the other or reads like it.
RELATION_CROSS_REFERENCE = "references"
RELATION_SIMILAR = "similar_to"

# How a relation records which mechanism found it, so a reader (and a later score)
# can tell the two apart rather than seeing one undifferentiated pile.
METHOD_PATTERN = "pattern"
METHOD_SIMILARITY = "embedding_similarity"


def load_patterns(path=None):
    """The operator's patterns and similarity settings. Returns
    (compiled_patterns, similarity_settings, warnings).

    A pattern whose regex does not compile is SKIPPED and named in `warnings`: a
    broken pattern and an absent pattern are different facts, and silently treating
    the first as the second would hide an operator's typo behind an empty result."""
    p = Path(path) if path else DEFAULT_PATTERNS_PATH
    warnings = []
    if not p.exists():
        return [], {}, ["no relation pattern file at %s; no cross-reference extracted" % p]
    try:
        spec = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [], {}, ["relation pattern file unreadable (%s): %s" % (p, type(e).__name__)]

    compiled = []
    for entry in spec.get("patterns") or []:
        if not isinstance(entry, dict):
            continue
        name, regex = entry.get("name"), entry.get("regex")
        if not name or not regex:
            warnings.append("a pattern entry without a name or a regex was skipped")
            continue
        flags = 0 if entry.get("case_sensitive") else re.IGNORECASE
        try:
            rx = re.compile(regex, flags | re.UNICODE)
        except re.error as e:
            warnings.append("pattern %r does not compile and was skipped: %s" % (name, e))
            continue
        compiled.append({"name": name, "regex": rx,
                         "target_group": int(entry.get("target_group") or 1)})
    sim = spec.get("similarity") if isinstance(spec.get("similarity"), dict) else {}
    return compiled, sim, warnings


def _norm(text):
    """Lowercase and collapse whitespace, for comparing a captured reference against a
    unit's own label. Unicode-aware by default in Python 3."""
    return " ".join((text or "").lower().split())


def _unit_labels(units):
    """{normalised label: unit_id} over every unit's title and its id's own slug, so a
    captured reference can be resolved to a real unit. Built from the document's own
    units: no list of section names exists here or can."""
    labels = {}
    for u in units:
        uid = u.get("unit_id")
        if not uid:
            continue
        title = _norm(u.get("title"))
        if title:
            labels.setdefault(title, uid)
        # the id's trailing slug (u05-entry-unit-damson -> "entry unit damson")
        if "-" in uid:
            slug = _norm(uid.split("-", 1)[1].replace("-", " "))
            if slug:
                labels.setdefault(slug, uid)
    return labels


def _resolve_target(captured, labels):
    """Resolve a captured reference to a unit id: exact normalised match first, then a
    unique containment match. AMBIGUITY IS REFUSED, never broken by picking one: two
    units whose labels both contain the captured text is a real ambiguity, and a wrong
    relation is worse than no relation."""
    key = _norm(captured)
    if not key:
        return None
    if key in labels:
        return labels[key]
    hits = [uid for label, uid in labels.items() if key in label or label in key]
    unique = set(hits)
    if len(unique) == 1:
        return hits[0]
    return None


def extract_cross_references(units, patterns):
    """Relations a pattern found: one unit's text names another unit's label.

    A unit never references itself (a heading naming its own title is not a relation),
    a reference that resolves to no unit is dropped rather than invented, and an
    ambiguous one is refused by _resolve_target. Every relation names the pattern that
    found it, so a reader can tell which of the operator's patterns is doing the work.
    """
    labels = _unit_labels(units)
    out = []
    seen = set()
    for unit in units:
        uid = unit.get("unit_id")
        text = unit.get("text") or ""
        if not uid or not text:
            continue
        for pat in patterns:
            for m in pat["regex"].finditer(text):
                try:
                    captured = m.group(pat["target_group"])
                except (IndexError, re.error):
                    # a target_group the operator's own regex does not have: skipped,
                    # never guessed at by falling back to group 0 (the whole match).
                    captured = None
                if not captured:
                    continue
                target = _resolve_target(captured, labels)
                if not target or target == uid:
                    continue
                key = (uid, target, pat["name"])
                if key in seen:
                    continue
                seen.add(key)
                out.append({
                    "type": RELATION_CROSS_REFERENCE,
                    "method": METHOD_PATTERN,
                    "source": uid,
                    "target": target,
                    "pattern": pat["name"],
                })
    return out


def extract_similarities(units, similarity_settings, *, rank=None):
    """Relations embedding similarity found, over units of the SAME document.

    `rank` is an injected callable (unit_text, [(unit_id, unit_text)]) -> [(unit_id,
    score)], the same injection shape pairing_map.pair_units already uses for its
    ranker, so this module never imports an embedding store and never loads a model.
    With no ranker, this returns nothing: the mechanism is simply unavailable, which
    is the honest answer rather than a fallback that pretends to be similarity.

    Only pairs at least `min_units_apart` apart by document index are considered, so
    this addresses the distance the adjacent-neighbour mechanism does not reach.
    """
    if rank is None or not units:
        return []
    min_score = float(similarity_settings.get("min_score", 0.75))
    max_per_unit = int(similarity_settings.get("max_per_unit", 3))
    min_apart = int(similarity_settings.get("min_units_apart", 2))

    index_of = {}
    for i, u in enumerate(units):
        uid = u.get("unit_id")
        if uid:
            index_of[uid] = u.get("index") if u.get("index") is not None else i

    out = []
    seen = set()
    for unit in units:
        uid = unit.get("unit_id")
        if not uid:
            continue
        here = index_of.get(uid)
        candidates = [(u.get("unit_id"), u.get("text") or "") for u in units
                      if u.get("unit_id") and u.get("unit_id") != uid
                      and here is not None and index_of.get(u.get("unit_id")) is not None
                      and abs(index_of[u.get("unit_id")] - here) >= min_apart]
        if not candidates:
            continue
        try:
            ranked = rank(unit.get("text") or "", candidates)
        except Exception:
            continue
        kept = 0
        for target, score in ranked or []:
            if kept >= max_per_unit:
                break
            try:
                score = float(score)
            except (TypeError, ValueError):
                continue
            if score < min_score or target == uid:
                continue
            # one relation per unordered pair: similarity is symmetric, and recording
            # it twice would double every count a later score reads.
            pair = tuple(sorted((uid, target)))
            if pair in seen:
                continue
            seen.add(pair)
            kept += 1
            out.append({
                "type": RELATION_SIMILAR,
                "method": METHOD_SIMILARITY,
                "source": uid,
                "target": target,
                "score": round(score, 6),
            })
    return out


def _canonical_pair(a, b):
    """The canonical form of an unordered pair: the two unit ids sorted.

    Direction is what splits the same relationship into two records today, because a
    pattern match is directional (this unit names that one) while similarity is
    symmetric and is emitted under whichever unit the ranker reached first. Sorting is
    the one canonicalisation that needs no judgement about which direction is "right",
    and the direction a mechanism actually reported is never discarded: it is recorded
    on the merged relation (see `found_by`).
    """
    return tuple(sorted((str(a), str(b))))


def merge_relations(relations):
    """One relation per unordered pair, carrying which mechanisms found it.

    THE DEFECT THIS CLOSES. Before this, a pair both mechanisms found produced TWO
    records that both persisted, because the store id encodes direction and type and
    the two mechanisms disagree on both: a cross-reference from u09 to u01 and a
    similarity between u01 and u09 are the same relationship written twice. Neither
    superseded the other, so every count over the store double-counted exactly the
    pair a reader would most want to trust, the one two independent mechanisms agree
    on. Agreement was invisible as agreement and visible only as duplication.

    WHAT IS COLLAPSED AND WHAT IS KEPT. The merged relation is keyed on the canonical
    (sorted) pair. Nothing a mechanism reported is thrown away:

      found_by       the methods that found this pair, sorted, so agreement is a fact
                     the store holds rather than something a reader has to notice by
                     seeing two rows.
      agreed         True when more than one mechanism found it. Derived, not asserted:
                     it is len(found_by) > 1 and nothing else.
      observations   one entry per mechanism, each keeping the direction THAT mechanism
                     reported (its own source and target), its type, and its pattern or
                     score. A reader can see that the cross-reference said one direction
                     and similarity said the other.
      relation_type  the type of the first observation in method order, and NOT a
                     judgement that one type outranks the other. The types are kept per
                     observation; this field exists only because a record needs one id.

    ORDERING, the one rule the operator has declared and the only one: a pair found by
    both mechanisms ranks above a pair found by one. Nothing else is ordered, because
    ordering the rest would need a weight, and a weight between a boolean (a pattern
    matched) and a similarity score that occupies a narrow band would let the boolean
    decide every ordering while the weight only appeared to work. That decision waits
    on the long-range corpus being scored.
    """
    merged = {}
    for r in relations or []:
        key = _canonical_pair(r["source"], r["target"])
        entry = merged.get(key)
        if entry is None:
            entry = {
                "source": key[0],
                "target": key[1],
                "found_by": [],
                "observations": [],
            }
            merged[key] = entry
        if r["method"] not in entry["found_by"]:
            entry["found_by"].append(r["method"])
        observation = {
            "method": r["method"],
            "type": r["type"],
            # the direction THIS mechanism reported, kept rather than normalised away
            "reported_source": r["source"],
            "reported_target": r["target"],
        }
        if r.get("pattern") is not None:
            observation["pattern"] = r["pattern"]
        if r.get("score") is not None:
            observation["score"] = r["score"]
        entry["observations"].append(observation)

    out = []
    for entry in merged.values():
        entry["found_by"] = sorted(entry["found_by"])
        entry["agreed"] = len(entry["found_by"]) > 1
        entry["observations"].sort(key=lambda o: (o["method"], o["reported_source"]))
        entry["relation_type"] = entry["observations"][0]["type"]
        # The best similarity score any mechanism reported for this pair, kept so a
        # later weighting has the number available. It orders nothing today.
        scores = [o["score"] for o in entry["observations"] if o.get("score") is not None]
        entry["score"] = max(scores) if scores else None
        out.append(entry)

    # The declared ordering, and only it: agreed pairs first. Within each group the
    # order is the pair's own ids, which is stable and carries no claim about rank.
    out.sort(key=lambda e: (not e["agreed"], e["source"], e["target"]))
    return out


def extract_relations(units, *, patterns_path=None, rank=None):
    """Both deterministic mechanisms over one document's units, MERGED.

    Returns {relations, counts, warnings}. `relations` holds one entry per unordered
    pair (see merge_relations); the counts still separate the two methods, because they
    are different mechanisms with different failure modes and the operator scores them
    against each other later, and one undifferentiated total would make that comparison
    impossible.

    `agreed` counts the pairs BOTH mechanisms found, which the concatenated form could
    not report at all: agreement showed up there only as duplication. Note that
    `pattern` + `embedding_similarity` no longer sums to `total` once any pair is
    agreed, and that is the point rather than an inconsistency: the method counts count
    observations, `total` counts pairs.
    """
    patterns, sim, warnings = load_patterns(patterns_path)
    refs = extract_cross_references(units, patterns)
    sims = extract_similarities(units, sim, rank=rank)
    relations = merge_relations(refs + sims)
    return {
        "relations": relations,
        "counts": {
            "total": len(relations),
            METHOD_PATTERN: len(refs),
            METHOD_SIMILARITY: len(sims),
            "agreed": sum(1 for r in relations if r["agreed"]),
            "patterns_loaded": len(patterns),
            "similarity_available": rank is not None,
        },
        "warnings": warnings,
    }


def relation_records(relations, *, document_id, run_id, provenance):
    """Shape MERGED relations as ontology store records, so they are written and read
    back through the SAME scoped storage layer provisions use.

    The id is the canonical pair (`<document>::<a>::relates::<b>`, the ids sorted) and
    carries NEITHER direction NOR mechanism, which is what makes the duplicate
    impossible rather than merely unlikely: the two records a pair used to produce now
    collide on one id by construction. Re-extracting the same pair in a later run
    supersedes its earlier revision, the storage layer's existing behaviour.

    `found_by`, `agreed` and `observations` travel with the record, so agreement is a
    fact the store holds and the direction each mechanism reported survives the merge.
    """
    out = []
    for r in relations:
        pair = _canonical_pair(r["source"], r["target"])
        out.append({
            "node": "Relation",
            "id": "%s::%s::relates::%s" % (document_id, pair[0], pair[1]),
            "document_id": document_id,
            "source_unit": pair[0],
            "target_unit": pair[1],
            "relation_type": r.get("relation_type"),
            "found_by": list(r.get("found_by") or []),
            "agreed": bool(r.get("agreed")),
            "observations": list(r.get("observations") or []),
            "score": r.get("score"),
            "run_id": run_id,
            "provenance": provenance,
        })
    return out
