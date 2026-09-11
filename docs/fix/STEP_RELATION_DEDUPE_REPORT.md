# RELATION DEDUPE: one relation per pair, agreement as a stored fact

**Built, not measured.** Nothing here has been scored on any corpus. The ontology store is at
zero bytes, no phase of the pipeline calls the extractor, and nothing in a review reads a
relation. The merge is proved on fixtures in the verify gate and nowhere else. No pipeline run
was started and no model was loaded.

## The defect

Before this, the two deterministic mechanisms were combined by one line, `refs + sims`, a list
concatenation: no weighting, no normalisation, no cross-method dedupe, and an implicit
ordering that was an accident of concatenation rather than a decision.

The consequence was worse than a missing weight. A pair **both** mechanisms found produced
**two records that both persisted**, because the store id encoded direction and type and the
two mechanisms disagree on both:

```
d::u09-qux::references::u01-glossary        (the pattern, directional)
d::u01-glossary::similar_to::u09-qux        (similarity, symmetric)
```

Neither superseded the other. So every count over the store double-counted exactly the pair a
reader would most want to trust, the one two independent mechanisms agree on, and agreement
was visible only as duplication. On the fixture, the glossary case job 2 exists to find
produced two rows for one relationship.

## What was built

**The canonical form is the sorted pair.** Direction is what split the relationship in two.
Sorting is the one canonicalisation that needs no judgement about which direction is right,
and the direction a mechanism actually reported is never discarded.

`merge_relations` produces one entry per unordered pair carrying:

| field | what it holds |
|---|---|
| `found_by` | the mechanisms that found this pair, sorted |
| `agreed` | derived, `len(found_by) > 1`, never asserted |
| `observations` | one per mechanism, each keeping the direction THAT mechanism reported, its type, and its pattern or score |
| `relation_type` | the first observation's type, and explicitly not a judgement that one type outranks the other |
| `score` | the best similarity score reported, kept so a later weighting has the number; it orders nothing today |

The store id is now `<document>::<a>::relates::<b>` with the ids sorted, carrying **neither
direction nor mechanism**, which is what makes the duplicate impossible by construction rather
than merely unlikely: the two records a pair used to produce now collide on one id.

`relation_summary` was updated to match: `by_method` counts **observations** while
`relation_count` counts **pairs**, so the two no longer sum to the same number once any pair is
agreed, and `agreed_count` reports the figure the concatenated form could not report at all.

## The one declared ordering rule

A pair found by both mechanisms ranks above a pair found by one. Applied in
`merge_relations` and again on the read path.

That is the only ordering declared, and it is declared because it needs no number. **No
weighting between the two mechanisms exists and none will be declared until the long-range
corpus is scored.** The reason is recorded in `config/relation_patterns.json` so nobody adds
one casually: a cross-reference is a boolean (a pattern matched and resolved unambiguously)
while a similarity is a score that on the fixtures occupied a band about 0.07 wide, so any
weight mixing them would let the boolean decide every ordering while the weight only appeared
to be doing work. That is the failure mode this project has caught itself in before, and it is
the operator's own reason for deferring.

## The three similarity settings, and what is under them

Recorded beside each value in the config and in the README, so a reader cannot mistake any of
them for a measured value:

| setting | value | what is under it |
|---|---|---|
| `min_score` | 0.75 | a conventional default, no evidence |
| `max_per_unit` | 3 | a conventional default, no evidence |
| `min_units_apart` | 2 | not measured either, but it has a structural reason: a unit is trivially similar to its neighbour and the adjacent-neighbour mechanism already covers that case |

## The check, and its two neutralise-and-restore proofs

Check 211, extended. It now asserts, beyond what it did: a pair both mechanisms find is ONE
relation; `found_by` names both; `agreed` is True on the record; the counts report it; both
observations survive; **both reported directions are kept**, so a reader can see that the
cross-reference said one and similarity the other; one store id results; and the agreed pair
ranks above the two single-mechanism pairs.

Two neutralise cycles, because there are now two defects to hold closed:

```
neutralise 1 (ambiguity broken by picking the first candidate)          -> FAIL, restore PASSES
neutralise 2 (merge replaced by the concatenation it replaced)          -> FAIL, restore PASSES
```

The second is the one that matters here: with `merge_relations` swapped for the old
concatenation, an agreed pair becomes two records again and the body fails.

## README, checked start to finish against the tree

- The merge, what it keeps and why the store id carries neither direction nor mechanism.
- The absent weighting, with the compression reason stated rather than implied.
- The one declared ordering rule.
- The three settings and what is under each.
- The `by_method` phrasing corrected: it counts observations, not pairs.
- The tracked file count, 190 to 191.
- Check counts (214), route table and env table re-verified by checks 167, 116 and 174.

## Not changed, recorded

- No weighting, by the operator's decision, until the long-range corpus is scored.
- Nothing in a review reads a relation, and no phase writes one. The merge changes the shape
  of a record that nothing yet produces in a run.
- The GNN candidate finder is untouched: it proposes pairs and has never written a relation,
  so the duplicate never reached it.

---

RELATION DEDUPE COMPLETE (one relation per unordered pair keyed on sorted ids, agreement
stored as `found_by` and `agreed` rather than left for a reader to notice, both reported
directions kept in observations, the store id carrying neither direction nor mechanism so the
duplicate is impossible by construction, the one declared ordering rule applied in both the
merge and the reader, the three similarity settings marked as unmeasured in config and README;
check 211 with two neutralise cycles; built without measurement)
