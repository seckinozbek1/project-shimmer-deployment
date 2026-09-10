# Unit context design (proposal, not built)

This document is a proposal. Nothing in it is built. It exists because a read-only trace,
run while a real local pipeline run was in flight, found that paired review judges a unit
in complete isolation from its neighbors, and the operator asked for a design before any
code, not a patch.

## The finding, restated precisely

`split_units()` (`scripts/pairing_map.py:101-145`) produces a four-key dict per unit:
`unit_id`, `title`, `kind`, `text`. Nothing else. No parent pointer, no prev/next pointer,
no stored offset. The only place order exists is the Python list order the function
returns units in, plus a numeric prefix baked into the opaque `unit_id` string (`u02-...`)
that a caller cannot query, only parse.

That list order survives as far as the pairing map's own entries (`pair_units`,
`pairing_map.py:218-278`, iterates `for unit in units` and preserves the sequence). It does
not survive to a single call. Every site that turns the unit list into something a call
site reads from does it by re-keying to a dict on `unit_id`:

```
scripts/paired_review.py:1644   {u["unit_id"]: u for u in pairing_map.split_units(...)}
scripts/pipeline.py:1258        unit_text = {u["unit_id"]: u for u in ...}
scripts/pipeline.py:1616        units_by_id = {u["unit_id"]: u for u in pairing.get("units", [])}
```

A dict lookup has no memory of what came before or after. `build_pair_payload`
(`scripts/paired_review.py:668-710`) sets `"document_text": unit.get("text", "")`: the
isolated unit's own text, nothing else, confirmed by reading the literal field. This is
not a bug in the sense of behaving other than intended. Paired mode was built narrow on
purpose, and the narrowness is why it works: `pairing_map.py`'s own header names the
reason: "the wide review handed a model eight declarations and twelve rules in one call
and got a summary of the rules back" (`pairing_map.py:3-4`). A unit judged alone cannot
summarize instead of checking, because there is nothing to summarize. That is the real
trade this document has to respect, not paper over: every option below that adds text
back is adding back some amount of the thing that made wide mode summarize.

Wide mode does not have this problem, but not by design either. `base_payload` at
`pipeline.py:1460-1463` sets `document_text` to `_truncate_doc(doc["text"], 6500)`, the
FULL document, clipped only by a character cap that removes the document's MIDDLE when it
exceeds the cap (`_truncate`, `pipeline.py:607-611`), not its edges. A wide-mode agent
sees a unit's real neighbors as ordinary prose as a side effect of seeing everything, which
is also why it summarizes rules instead of checking them. The two properties are the same
property, seen from two sides: send everything, and you get both adjacency and
summarization; send one unit, and you get neither.

## What the operator's four options would and would not catch, and what each costs

Every cost figure below is measured against real staged corpora (`benchmark/corpora/`),
not invented. Unit sizes: `catalogue_records` averages 303 chars/unit across 6 units
(range 269-329); the negotiation corpora average 85-156 chars/unit across 5-6 units
(range 33-474). These are small test corpora; the operator's own real documents run
larger. Costs here are given as "chars added to `document_text` per call" and as a
percentage of the current isolated-unit payload, using `catalogue_records`' 303-char
average unit as the worked example throughout, so the four options are comparable on the
same document.

Call volume is what a per-call context addition actually multiplies against, and it does
NOT collapse uniformly; this needs to be stated precisely rather than optimistically. H7's
fix (`plan_calls`, `paired_review.py`) collapses repeated calls ONLY where the underlying
check is arithmetic and rule-independent (a sum, a product, a band comparison, computed
once per unit regardless of how many rules pair with it): its own docstring cites a real
"operator's document" that went from 40 calls to "4 calls" this way. That collapse does
not fire on every document. Measured directly against `catalogue_records` by running
`plan_calls` on it (not read from a comment): the corpus states plainly it contains no
quantities at all ("No quantities appear anywhere in this document," `catalogue_records.md`'s
own header), confirmed by extraction (`extract_fields` finds zero scalars and zero columns
on every one of its 6 units); with nothing arithmetic to collapse, `plan_calls` planned one
call per pair, 23 calls for 23 pairs, no reduction. So the real cost model has two regimes,
not one: on an arithmetic-heavy document, a per-call context addition inherits H7's
existing collapse and multiplies against a small call count; on a document like
`catalogue_records`, dominated by presence and vocabulary checks rather than figures, it
multiplies against something closer to the raw pair count instead. A design that assumed
the collapse applies everywhere would understate the cost on exactly the kind of document
(no arithmetic, missing-field and vocabulary rules) this session's own real local and cloud
runs both used as the test case.

### A. The unit alone (today)

**Catches:** anything the unit's own text and the rule's own text can decide together.
This is everything paired mode currently catches: missing fields, vocabulary membership,
sums, products, ratios against a rule-stated band. All of it is real and none of it needs
a neighbor.

**Does not catch:** a provision that is only wrong or only sound in light of an adjacent
provision. The operator's own example: a general rule that a specific, adjacent exception
overrides. A model shown only the general rule's unit has no way to know the exception
exists, however well the rule text is written, because the exception is not in the rule
text, it is in the neighboring unit's text.

**Cost:** the baseline. 303 chars of `document_text` per call (the worked-example unit).

### B. The unit with the text immediately before and after it

**Catches:** exactly the operator's stated concern, directly. An exception in the
preceding unit, a contradiction in the following one, are now in the same call as the
provision being judged. This is the narrowest addition that can catch adjacency-dependent
error at all: it adds only what "immediately before/after" means, nothing further out.

**Does not catch:** a provision that depends on something several units away, or on a
document-wide pattern (the same term defined differently in two places that are not
neighbors). It also does not tell the model WHY the neighbor matters, only THAT it exists;
the model still has to notice the relationship unprompted, same as it has to notice
anything else in a payload.

**Cost:** two more `text` fields, sized like the unit itself. On `catalogue_records`
(average 303 chars/unit, adjacent units similarly sized), a call carrying a unit plus its
two neighbors is roughly 909 chars of unit text, a 3x increase over option A on this
corpus. On a real document with more varied unit sizes this ratio moves with whatever the
neighbors happen to be, not with the corpus average; a unit next to a long table row costs
more than a unit next to a short one. This is proportional, not open-ended: it is bounded
by two unit-sized additions, however large those two units happen to be, and it does not
grow with document length or rule count, only with the two units nearest to whichever unit
is being judged.

### C. The unit with its parent heading and the sibling units under it

**Does not apply as stated, and this needs to be said plainly rather than answered as if
it did.** `split_units()` has no parent/child structure to draw from. Every heading below
the top level starts a NEW, SIBLING-SHAPED unit (`pairing_map.py:113`,
`body_headings = [m for m in headings if len(m.group(1)) >= 2]`); a subsection is not
nested inside its section's unit, it is a separate unit at the same structural level with
no back-reference to what it was nested under in the source document. Building option C as
described would require changing what a unit IS, not just what accompanies it to a call,
because "parent heading" and "sibling units" are not concepts the current split produces.
That is a materially different, larger change than B or D, and this document does not
recommend making it to solve the adjacency problem, because B and D solve the same problem
without it. If the operator wants true section/subsection nesting for a different reason
(a reason beyond adjacency at review time), that is a separate design question from this
one and should be scoped separately rather than folded into this cost comparison.

### D. The unit with a short structural map of the whole document, headings only

**Catches:** something different from B, not a superset or subset of it. A structural map
(the ordered list of every unit's `title`, nothing else) tells a model where the unit it is
judging sits in the document's overall shape: is this the last exception clause after a
general rule, is this one of six parallel entries, is there a section further away whose
existence alone (not its content) is relevant. It does not tell the model what any other
unit SAYS, only that it EXISTS and where. It would not, by itself, let a model catch the
operator's exact example (an adjacent unit's specific wording creating an exception),
because the map carries no wording, only titles. It is a different, complementary kind of
context: awareness of shape, not access to neighboring content.

**Cost:** proportional to unit COUNT, not unit size, and the cheapest of the three real
options. On `catalogue_records` (6 units, titles averaging roughly 16 chars,
`"Record CAT-ALDER"` through `"Record CAT-FIRTH"`), a full map costs roughly 100-150 chars
total, once per document, reused across every call for that document rather than rebuilt
per unit. This is already partly built: `pipeline.py:1478-1482` adds `document_units`
(`unit_id`+`title` pairs) to the WIDE-mode payload today, for a different reason (so
PRACTICE_AUDITOR can copy a real `unit_id` rather than inventing one, the fix committed
earlier today). The same list, unchanged, is the structural map option D describes; wiring
it into the PAIRED-mode payload as well is not new construction, it is reusing a payload
field pipeline.py already builds once per document for wide mode.

### E. Anything else

Two variants worth naming because they are cheaper than B for a narrower slice of the same
problem, not because they are better in general:

**E1, neighbor TITLES only, not neighbor TEXT.** A cut-down version of B: add the
preceding and following unit's `title` field (already present in every unit dict,
`pairing_map.py:122`) without their `text`. This tells a model "the unit before this one is
called X, the unit after is called Y" at near-zero cost (titles average well under 30
chars on the measured corpora), which can prompt a model to ask for more via a second call
only where a title suggests it matters, but cannot itself catch a content-dependent
exception, only suggest that one might exist. This is a real option, cheaper than B, that
catches less than B; it belongs in the comparison honestly rather than omitted because it
sounds like a compromise.

**E2, a rule-stated cross-reference, read from the rule's own text rather than added
unconditionally.** Some rules already name which OTHER rule or field they interact with
in their own prose (the codebase's existing discipline of reading bounds and fields "from
the rule's own text," never inferred, already applies this same idea to numeric bands,
`reference_tables.py`). If a rule's text names a specific other field or unit
relationship, the pairing step could resolve that reference structurally (no model call,
no vocabulary, matching the existing containment-based mechanisms this codebase already
trusts) and attach only the named neighbor, not every neighbor. This is narrower than B
(it only fires when a rule says it needs to), and it would require the rule text to
actually state the cross-reference, which not every real rule will. Worth naming as a
future refinement once real data shows how often rules do state this, not worth building
speculatively now.

## Recommendation

**B (immediate neighbors), reached through D's existing scaffold, not built as a separate
mechanism.** Reasoning, in the operator's own terms:

D alone answers "where does this unit sit," not "what does the unit beside it say," and
the operator's own concern is explicitly the second question, not the first: "a provision
read alone can look wrong when the previous provision creates an exception... it cannot
judge either case" without seeing what the neighbor SAYS, not just that it exists. D is
real and cheap and should still be built, because it is nearly free (a per-document list
already computed for a different reason) and answers a genuinely different question B
does not (document shape awareness), but D on its own does not close the finding.

B directly closes the finding at the smallest correct PER-CALL cost: two more unit-sized
text fields, bounded by the two neighboring units' own size, not by document length or
rule count. That per-call bound is unconditional, but the earlier cost-model finding
still applies to B's TOTAL cost across a run: on an arithmetic-heavy document, B's added
text is multiplied by H7's already-collapsed, small call count; on a document like
`catalogue_records`, with no arithmetic to collapse, it is multiplied by something closer
to the raw pair count instead, same as every other option here, since none of them change
how many calls `plan_calls` decides to make, only what each call carries. This is not a
reason to prefer a cheaper option over B; every option in this comparison is subject to
the same two-regime total-cost multiplier, since it is a property of call count, not of
what a call carries. C is not comparable, it requires restructuring what a unit is, for a
benefit B already delivers without that restructuring. E1 is cheaper than B per call but
catches less (a hint, not the actual neighboring text); E2 is a real future refinement but
depends on rule text stating cross-references explicitly, which cannot be assumed today.

The reason this does not reopen wide mode's failure: wide mode's problem was sending
EVERYTHING (every unit, every rule, in one call), which gave a model room to answer a
different, easier question ("summarize the rules") instead of the one asked. B sends
exactly three units' worth of text (bounded, small, the same order of magnitude as the
unit itself) alongside one rule's text and Python's own computed comparison, which is
still a narrow question about one unit's own figures against one rule, now with two more
units of read-only surrounding text the model is not asked to reason about on their own
terms, only to notice if they bear on the unit actually being judged. The `arithmetic_note`
field already tells the model not to recompute the figures; the same instruction pattern
extends naturally to "the surrounding text is for context, the question is still about
THIS unit."

## The two things to settle

### Order is thrown away at the point a call is built

The smallest change that keeps it: add one field, `"index": i`, to each unit dict at the
point `split_units()` already has `i` as a loop variable (`pairing_map.py:116`,
`for i, m in enumerate(body_headings)`, and the equivalent loops for table rows and table
blocks). This is genuinely the smallest possible fix, not merely the first one considered,
because of how the rest of the codebase already handles a unit dict: every re-keying site
(`paired_review.py:1644`, `pipeline.py:1258`, `pipeline.py:1616`) builds
`{u["unit_id"]: u for u in ...}`, copying the WHOLE dict by reference. An `index` field
added at the source survives every one of those re-keyings automatically, with no change
needed at any of the three sites, because none of them projects the dict down to a named
subset of fields, they all keep the dict whole. This is also the field option B needs
regardless: finding "the unit immediately before/after" a given unit by id requires
knowing the unit's position, which `index` is exactly for. One field, one write site, three
free downstream consumers.

### The reference index currently ingests the document under review

`_populate_operational` copies the operational document's source file into
`input/operational/` with `shutil.copy2` (`pipeline.py`, the `_populate_operational`
loop), never removing it from `input/context/`. `embedding_store.build_store`
(`embedding_store.py:400-401`) globs every file still present in `input/context/`,
including that one, and registers its chunks with `input_type="context"`
(`embedding_store.py:440-449`), indistinguishable by that field from genuine grounding
material. `_doc_refs_excerpt` (`pipeline.py`, `return [e.as_dict() for e in
reference_index.find_by_document(document_id)[:30]]`) filters by document id ALONE, no
`input_type` check, so for an operational document it returns that SAME document's own
paragraph-level excerpts, reachable through `reference_index_excerpt` on every paired call
(`pipeline.py:1686`) with no label distinguishing them from real reference-corpus text.

This should be excluded, not labelled, and not turned into the deliberate neighbor
mechanism. Reasoning: labelling it would mean building a signal for the model to
distinguish "this excerpt is from the document you are reviewing" from "this excerpt is
from the reference corpus," which is real design work to fix a mechanism that was never
meant to do this job in the first place, retrieval by embedding similarity against a
4000-char document head or a rule's own text (`pipeline.py:210`, `head = doc_text[:4000]`)
has no relationship to unit adjacency; a similarity hit near the TOP of a document has no
reason to be the unit's actual neighbor. Turning it into the deliberate mechanism would
mean relying on semantic similarity to approximate physical adjacency, when physical
adjacency is already known exactly, structurally, for free, once `index` (above) exists.
There is no reason to approximate a fact the pipeline already has. The correct fix is
narrow and structural, matching every other fix this codebase already trusts: exclude the
document under review from what `_doc_refs_excerpt` and the embedding-store ingestion both
draw from, by document id, the same shape of exclusion `reference_tables_mod.tables_from_entries`
already applies in a narrower scope (`exclude_document_id=doc["id"]`, `pipeline.py:1296`
and `pipeline.py:1636`) for a different but structurally identical reason: the document
under review is the thing being checked, not the material it is checked against, and that
distinction should hold everywhere a document reaches the reference index, not only in the
one place it currently does.
