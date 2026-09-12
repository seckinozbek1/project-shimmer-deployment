# Knowledge categories: what counts, where the boundary is enforced, and what it does to the arithmetic

Written 2026-09-12, in answer to the operator's three questions, BEFORE building.
Proposals are marked as proposals. Where an existing mechanism already does the
work it is named rather than replaced, because the cheapest boundary is one that
already exists and is already tested.

---

## Question 1: what counts as domain knowledge

**Proposed, not assumed.** The test is not where a fact is stored or what it is
about. It is **what authority it carries and what happens if it is wrong**.

Three categories, by that test:

### CONSTITUTION-derived
The seed laws and the ratified amendments. `config/constitution.json`: 7 seed
laws, 28 amendments. Authority: absolute and operator-ratified. Wrong means the
system is misgoverned.

Already carries precedence in its own vocabulary: every seed law has a
`priority` integer, an `immutable` flag, and an `outranked_by` list. `LAW-0` is
`outranked_by: ["LAW-IV"]`. **Precedence between laws is already expressible and
already expressed.** No new vocabulary is needed at this layer.

### RULE-derived
The operator's conventions, compiled into `config/convention_registry.json` from
`input/conventions/`. Authority: the operator's own instruction for this review.
Wrong means the review applies the wrong standard.

### USAGE-derived (this is what "domain knowledge" means here)
Everything the system concluded by looking at documents, as opposed to being
told. The proposed membership test, in one sentence:

> A fact is usage-derived when no operator wrote it and no law ratified it, and
> it exists only because this installation processed some documents.

By that test, and confirmed against what is on disk:

| store | `source` field | usage-derived? |
|---|---|---|
| `durable/learnings/citation_convention.json` | `adaptive_spawn` | **yes** |
| `durable/learnings/institution_registry.json` | `adaptive_spawn` | **yes** |
| `durable/learnings/speech_acts_taxonomy.json` | `adaptive_spawn` | **yes** |
| `durable/learnings/search_strategy_learnings.json` | (none) | **yes** |
| `durable/learnings/document_dates.json` | (none) | **yes**, and see the caveat |
| `durable/learnings/spawn_log.jsonl` | (none) | **yes** (bookkeeping) |
| `durable/cache/embedding_store.pkl` | n/a | **yes** (derived index) |
| `ontology/stores/provisions.jsonl` | n/a | **yes**: passages observed in documents |
| `ontology/stores/graph.json`, `gnn_state.json` | n/a | **yes**: derived from the above |
| `durable/governance/*` | n/a | **no**: operator verdicts and law-adjacent audit |
| `config/convention_registry.json` | compiled | **no**: rule-derived |
| `config/constitution.json` | ratified | **no**: constitution-derived |

**The caveat worth stating rather than hiding.** `document_dates.json` is a
borderline case and I place it in usage-derived deliberately. It is a conclusion
about documents, not an instruction, so by the test it is usage-derived; but a
*specific operator's* documents are named in it, which is why it must ship empty
rather than merely being ignorable. That is the stronger reason for the shipping
rule, not a weaker one.

**A fourth thing that is none of the three.** A run's own `output/runs/<id>/`
artifacts are evidence of one run, not knowledge. They are already gitignored and
already excluded from the image. They need no category.

---

## Question 2: where the boundary is enforced

**A boundary a caller can forget is not a boundary.** So the enforcement must be
structural, and the proposal is to use the one that already exists rather than
invent a second.

**It already exists: `durable_paths.RESETTABLE_SUBDIRS = (cache, learnings,
reference)`**, at `scripts/durable_paths.py:31`, consumed by
`snapshot_manager.py:250` which deletes exactly those subtrees on
`--reset-snapshot`. Governance and global are excluded from it by construction.
The category boundary and the resettable boundary are, on inspection, the same
line drawn for a different reason.

That gets the boundary most of the way but **not all of it**, and the gap is
worth naming precisely:

1. `ontology/stores/` is **not** under `durable/`, so it is not in
   `RESETTABLE_SUBDIRS` and a reset does not clear it. The provisions, the graph
   and the GNN state are usage-derived and survive a reset today. **That is a real
   hole in the shipping rule** and is the one thing here that needs fixing rather
   than documenting.
2. Nothing *asserts* the boundary. A future store added under `durable/global/`
   or a new top-level directory would be outside it silently, which is the
   "silently swallowed" failure shape this project keeps finding.

**Proposed enforcement, two parts, both structural:**

- **A declared manifest** naming every usage-derived location, with
  `ontology/stores/` included, so the reset and the ship path read one list
  instead of each knowing its own.
- **A gate check that fails when a store exists outside the manifest**, so
  adding a store without categorising it breaks the build rather than shipping
  someone's usage data. This is the part a caller cannot forget, because it is
  not the caller who is asked to remember.

---

## Question 3: does this change the volume arithmetic

**Yes, and it changes the conclusion, which is why the operator was right to ask.**

My earlier finding stands unchanged for what it measured: **operator decisions
accrue at roughly one per run and zero conflicts, so they are an audit trail and
not a training set.** That was about a signal that waits for a human answer.

Usage-derived knowledge is a different quantity and accrues differently:

| | per run | waits for a human? |
|---|---|---|
| Operator decisions | ~1 (and 0 conflicts) | **yes** |
| Provisions captured | 22 on disk from a handful of runs | no |
| Graph nodes | 20 nodes, 10 edges today | no |
| DeltaProposals | 1 across two runs | no |

So the arithmetic is genuinely different: **usage-derived knowledge accumulates
every run and blocks on nothing.** On volume alone it is the only one of the two
that could ever reach a training set.

**But volume is not the constraint, and this is the part that must not be lost.**
The reason operator decisions are the correctness signal is that usage-derived
knowledge is **self-generated**: a model trained on what the pipeline concluded
learns what the pipeline does, not what is true. That is exactly the UNIT-VETCH
failure, where the same wrong sentence appeared on both twins and recurrence
would have rewarded it.

So the honest statement, which supersedes neither answer:

> Usage-derived knowledge has the volume and lacks the ground truth. Operator
> decisions have the ground truth and lack the volume. Neither alone is a
> training signal, and the category separation is what makes it possible to say
> that precisely instead of mixing them and claiming a signal exists.

That is an argument **for** the category scheme independent of learning: keeping
them apart is what stops a high-volume self-generated store being mistaken for
evidence.

---

## How item TWO sits inside this

The operator's framing is right and it simplifies the work. A rule qualifying
another rule and a rule outranking a usage-derived fact are the same question at
two scales, and the answer is the same shape at both: **an ordering between
categories, and an ordering within a category.**

**Between categories (new, and the decision settles it):**

    constitution  >  rule  >  usage

Read as: where they conflict, the higher category governs. This needs no new
vocabulary, because it is a property of the category, not of any individual item.

**Within a category (item TWO's actual question):** the constitution already has
`priority` and `outranked_by`. The convention registry has nothing. So what item
TWO must add is the *within-rules* ordering, and the smallest set that expresses
what CONV-D01 actually says.

### The smallest set, proposed

CONV-D01 says, in the operator's own words:

> a reading "must fall inside its class's standard tolerance band, 20 to 60
> units, UNLESS a locally adjusted range for that device's batch or rack has been
> stated in the entry immediately before it or in the same entry."

Stripped to its structure, that is **one relation and no more**:

    [unless: <condition stated in the document>]

Not a taxonomy. Not parent/child, not overrides, not precedence, not priority.
D01 does not qualify another *rule*; it qualifies **itself**, conditionally, on
something the document states. The smallest honest reading is a **conditional
suspension of a rule, triggered by the document**.

**Proposed declaration, in the existing bracket syntax:**

    [unless: locally adjusted range]

reading as: when the unit in scope, or the entry beside it, states this field,
this rule does not fire. It reuses the field-label vocabulary `scope` and
`requires` already use, so the parser gains a third declaration and no new
concept.

**What I would have asked, and the reading I took.** I would have asked whether
`unless` should point at a *rule* (making it rule-to-rule) or at a *field* (making
it rule-to-document). I took the field reading, because it is what D01's text
actually says and it changes least: it needs no cross-rule payload assembly, no
ontology edge, and no change to the pairing map's independence assumption. The
rule-to-rule reading would need all three. If the intent was rule-to-rule, this is
the correction to make, and it costs one declaration type rather than a rebuild.

### What hierarchy does to `_reattribute_computed_plan`

The operator flagged this and it is the sharpest consequence. That function's
docstring says the comparison "is the same whichever rule prompted it", and swaps
in an interchangeable rule so a finding is not lost to a bookkeeping choice.

**Under the field reading, nothing breaks**, and that is a further argument for
it. An `unless` condition is evaluated against the *unit*, so a plan reattributed
from rule A to rule B is still evaluated against B's own conditions. The two rules
remain interchangeable *for the arithmetic*, which is all that function claims.

**Under a rule-to-rule reading it would break**, exactly as the operator says: an
exception and its parent are not swappable, and reattributing a computed plan from
a parent to its exception would silently change which rule's conditions applied.
If the rule-to-rule reading is ever taken, `_reattribute_computed_plan` must
refuse to swap across a qualifying relation. Recorded here so it is not
rediscovered later.

### The ontology edge, fourth layer

**Not needed for this case, and here is why.** The `unless` condition is
rule-to-document, not rule-to-rule, so there is no Convention-to-Convention edge
to draw. The relation is already expressible where it matters: in the registry
entry and in the agent payload. Adding a graph edge would create a node relation
the reasoning never reads, which is scaffolding.

It becomes needed if and when a rule genuinely qualifies another rule. Recorded
as deliberately skipped, with the trigger for revisiting it.
