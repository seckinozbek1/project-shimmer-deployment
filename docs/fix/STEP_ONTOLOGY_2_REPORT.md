# ONTOLOGY JOB 2: relations between provisions

**Built, not measured.** The deterministic baseline is built and wired to the store. Neither
mechanism has been scored on any corpus, and neither is claimed to work. The store is empty,
so there is nothing to extract relations from in this repository today; every assertion here
is proved on fixtures. No pipeline run was started and no model was loaded at any point in
this job.

**The second half stops for an operator decision.** The brief's premise about the GNN does
not match the code. What is actually true, and the options, are in the last section. Nothing
was half-built while that is open.

## The gap

The graph records where a finding came from (`HAS_PROVISION`, `GOVERNED_BY`, `CITES`,
`EXHIBITS`) and one provision-to-provision edge, `CROSS_REFERENCES`, which is derived from a
finding's own `context_refs` and so records which REFERENCES an amendment cited, never that
two provisions of a document relate to each other. The long-range case the adjacent-neighbour
work explicitly does not reach (a term defined at the start of a document and used at the
end) needs the second kind of relation, and nothing produced it.

## What was built: the deterministic baseline, first, as the brief orders

`scripts/relation_extract.py`, two mechanisms, both deterministic, no model call in the
module at all.

**1. Cross-reference extraction.** One unit's text names another unit's label. Every pattern
is the operator's, read from `config/relation_patterns.json`; the module holds no pattern of
its own and cannot (S5). The config ships two patterns as a starting point, both replaceable
outright: a numbered-unit reference ("see section 1", the referring phrases and unit kinds
both listed in config, not in code) and a defined-term reference ("as defined in the
glossary"), which is the long-range shape this job exists for. With no patterns declared,
nothing is extracted, which is an honest nothing. A pattern that does not compile is skipped
and named in `warnings`, because a broken pattern and an absent pattern are different facts.

Resolution of a captured reference to a real unit is exact-match first, then unique
containment, and **an ambiguity is refused rather than broken**: a captured phrase contained
in two units' labels yields no relation. Proved on a fixture where two units are "Alpha thing
one" and "Alpha thing two" and the reference says "alpha thing": no relation is minted. A
wrong relation is worse than no relation.

**2. Embedding similarity** over units of the same document. No pattern, so no vocabulary at
all. The ranker is **injected**, never imported, the same shape `pairing_map.pair_units`
already uses, so this module never depends on an embedding store existing and never loads a
model. With no ranker the mechanism is simply unavailable and returns nothing rather than
falling back to something that pretends to be similarity. Only pairs at least
`min_units_apart` apart are considered (default 2), because a unit is trivially similar to
the one beside it and the neighbour mechanism already carries that case; this mechanism is
for the distance that one does not reach. Similarity is symmetric, so one relation is
recorded per unordered pair, not two, which would have doubled every count a later score
reads.

**Recorded into the store and read back.** `relation_records` shapes relations as records for
the same scoped storage layer provisions use, rather than a second store with its own rules.
The id is composite and stable (`<document>::<source>::<type>::<target>`), so re-extracting
the same relation in a later run supersedes its earlier revision instead of duplicating it,
which is the storage layer's existing behaviour and not a new one. `ontology_reader.relation_summary`
reads them back, counting by type, by method and by pattern, keeping the two mechanisms
distinguishable because the operator scores them against each other later and one
undifferentiated total would make that impossible.

**A defect this found and closed.** Writing relations into the same store made
`provenance_summary` count them as provisions, silently inflating every figure job 1 reports.
Provisions and relations are now separated by node type on the read path, with a record
carrying no node treated as a provision, which is what every record written before job 2 is.

## What a relation is, and is not

It says one unit names, or reads like, another. It does **not** say the two agree, conflict,
or bear on each other's correctness, and it is **not** evidence for any finding. It is a
structural candidate, recorded so that something downstream can later be scored on it.
Nothing in the review reads relations today.

## The GNN half: what the brief assumed, what the code does, and the decision

The brief says: "The GNN today resets its weights every run and learns nothing; if making it
accumulate is more than a contained change, say what it costs and stop rather than
half-building it."

**The premise does not hold, and this is worth stating precisely before any option is
chosen.** `ontology_gnn.gnn_update` already accumulates:

- It loads any prior state from `gnn_state.json` and **restores the persisted encoder and
  decoder weights** when the feature dimensions match, reinitialising only when there is no
  prior state or the dimensions changed.
- It keeps a **high-water mark** of trained node ids and backpropagates only over nodes new
  since that mark, then persists the updated mark.
- The feature width is constant across runs by construction (deterministic feature hashing
  into fixed buckets), which is precisely what makes a persisted weight matrix stay valid.

So weights do not reset each run, and the accumulation mechanism the brief asks for exists.
What is true, and what the module's own header says in its first paragraph, is that it
**demonstrates machinery, not learning**: the loss is a self-supervised reconstruction of the
input with no labels, because the learning signal (Tier 2: proposal recurrence, finding
recurrence, verification verdicts, precedent) is empty and stays empty until runs populate
it. It learns nothing because there is nothing yet to learn from, not because it forgets.

That difference changes what the second half of job 2 should be, so I have not picked one.
**The decision is yours.**

| option | what it is | cost | what it would be worth |
|---|---|---|---|
| **A. Nothing further now** | Keep the deterministic baseline as the only relation producer. Revisit the candidate finder after the baseline has been scored on the long-range corpus. | None. | The baseline may be enough; scoring it first is the cheapest way to find out, and it is the order the brief itself sets ("build the deterministic baseline first"). |
| **B. The candidate finder on the graph as it stands** | The GNN narrows to candidate pairs by embedding proximity in its learned space, the model decides and writes the reasoning, the score is shown beside the decision. | Contained: a scoring function over the persisted state plus a wiring point. It would run on a graph whose weights are fit to a self-supervised reconstruction with no Tier-2 signal, so its ranking today is a function of graph structure and node features, not of anything learned about relevance. | Little until Tier 2 has content. It would produce numbers that look like evidence and are not, which is the failure the project has already decided against once (the no-confidence-field decision in the store). |
| **C. Give the GNN a real signal first** | Populate Tier 2 (recurrence of proposals and findings across runs) so the loss has something other than reconstruction to fit. | Substantial, and it needs runs to exist before it can be built: the signal is cross-run recurrence, which needs several scored runs first. | This is what would make a candidate finder mean anything. It is gated on measurement, not on code. |

My reading, offered as a recommendation and not acted on: **A**, because the brief's own
ordering says score the baseline before deciding, and because B produces a number that looks
like evidence while Tier 2 is empty. But the choice is yours, and if you want B I will build
it as a contained change with the score shown rather than hidden, exactly as the brief
describes.

**No code for the GNN half was written.** The deterministic baseline stands alone and is
complete in itself.

## The check, and its neutralise-and-restore proof

See `STEP_ONTOLOGY_2_CHECK.md` section below, folded into this report at commit time.

## Not built, recorded

- Nothing in the review reads relations. They are written and read back; no phase, agent or
  deliverable consumes them. That is deliberate at this stage: the operator scores them
  before anything relies on them.
- The extractor is not wired into the pipeline's phase 8 in this commit, because the wiring
  point depends on the GNN decision above (whether relations feed a candidate finder or stand
  alone). The mechanism is complete and exercised; its call site is one line and is named in
  the decision.
- No corpus has been scored. The long-range corpus exists (`device_log_review`, three
  long-range flaws) and is the instrument, on the GPU box, after the move.

---

ONTOLOGY JOB 2: the deterministic baseline is BUILT (cross-reference extraction with every
pattern in operator config, embedding similarity with an injected ranker, ambiguity refused,
relations written to the scoped store and read back, provisions and relations separated on
the read path). The candidate-finder half STOPS for an operator decision, because the
premise it rests on does not match the code: the GNN already accumulates weights and a
high-water mark; what it lacks is a Tier-2 signal, not persistence. Nothing measured.
