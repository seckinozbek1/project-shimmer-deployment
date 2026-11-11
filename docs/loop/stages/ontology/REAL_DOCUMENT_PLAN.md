# The ontology proposer on documents people wrote, and the system comparison (D-S102 item 7)

Written 9 November 2026, before any of it runs. Nothing below is measured. Its record is
`docs/loop/stages/ontology/attempt2_measurement.json`, which states what attempt 2 showed and what it
did not show.

## Where it stands

**What attempt 2 showed.** The unit-pair GNN proposer passed its one opening on held-out generator
block 930 (40 documents, 313 gold pairs; D-330, D-359, L-9). Gold pairs reached:

| Proposer | In the first 10 | In the first 40 |
|---|---|---|
| Shipped embedding ranker | 3 | 17 |
| Structural control (no training) | 13 | 89 |
| The GNN proposer, attempt 2 | 171 | 302 |
| Attempt 1's model | 187 | 305 |

It won 39 documents and lost 0 against the ranker at K 10.

**What that does not show.** Every figure comes from this repository's own generator tests: the same
four families on both sides, and documents nobody wrote. It shows nothing about reach on real
documents, and nothing about whether the system works better with the ontology routed in. The page
labels it "synthetic generator tests only".

**Why it cannot be used yet.** The routing that would let a review use the proposer is a governed
change. It is drafted, not ratified: `docs/ONTOLOGY_ROUTING_DELTA_DRAFT.md`, on lane/ontology. Agents
never apply it.

## Part 1: the proposer on real documents, held out

**Question.** On documents people wrote, does the GNN proposer reach more gold pairs in its first K
proposals than the shipped embedding ranker and the structural control?

**Items.** ContraDoc documents, whose keys mark contradicting passage pairs.
- They come from the development pool only.
- Never the fresh set or its groups, never the gate set (D-S100), never a group either was drawn from.
- The documents are chosen by a seeded hash before anything is read, and their list and digest are
  committed first.
- A document whose marks the proposer cannot express as a unit pair is counted apart, never dropped.
- The keys are read only by `tools/score_corpus.py`.

**Size.** Set by the same power line as attempt 2: the sign test over documents at the opening's
alpha. Forty untied documents give power about .90 if a document is a win with probability .75. The
document count is committed with the list.

**Bar.** The rule of `tools/ontology_pairs_measure.py` at 84307a38, unchanged:
- the margin of 5 points over the ranker and over the control, at K 10 and K 40;
- the sign test at alpha `0.05 / 2^k`, with one opening written in `docs/loop/HELDOUT_OPENINGS.md`
  before the read;
- the earlier best measured on the same documents.

**Not in the generator test.** ContraDoc's gold is a contradiction, not the generator's link
families. So this tests whether the proposer reaches a kind of pair it was never trained on, and a
loss there is a finding, not a defect of the test. It is a measurement only: nothing is trained or
tuned on these documents (D-S61 item 1: every run locked).

**Record.** A tracked file beside this one: the reach per arm with each document's counts, its 95
percent bootstrap interval over documents (D-S99), the opening, and the label "development, exposed;
real documents".

## Part 2: the system with and without the ontology (D-S61 item 4(b), item 6)

**Order.** This comes only after the routing DELTA is ratified by Seckin. An update counts only when
it is made from allowed material (D-S60 item 2), with the lock opened by the operator for that
purpose (D-S61 item 2), as a new named version beside the frozen one.

**Arms, on the same items, all locked:**
1. The full system at its best measured state with the frozen ontology version, which is "the system
   without it" (D-S61 item 6).
2. The same system with the updated version.
3. B1.

**Items.** Development items not used to make the update: ContraDoc from Part 1's pool less Part 1's
own documents, plus the multi-round development cases where the routing proposes position pairs.
Fixed by seeded hash and digest before any read. Never the gate set or the fresh set.

**Metric.** Each benchmark's own (D-S99): ContraDoc binary judgment accuracy, with the contradictory
class's precision, recall and F1 beside it. Each figure gets its item count and a 95 percent
interval.

**Adopted only if all three hold:**
- arm 2 is above arm 1 by the paired difference's interval;
- arm 2 is above arm 3 by the same test;
- a checker who did not build it spot-checks the update's new relations and proposals, and each one
  traces to its source passage.

Otherwise the frozen version stays, and the result is recorded with its figures.

**Cost.**
- Arms 1 and 2 are B3 runs on a rented machine, one per arm on the same type (D-S82). The forecast
  per arm is taken from the measured C1 batch (25 ContraDoc and SciTab entries in 178 minutes, 3.83
  USD, D-257), scaled to the item count, and stated before the launch.
- Arm 3 is a B1 replay.
- The total budget is the only limit (D-S95 item 4).

## Before any claim

No statement that the ontology or the GNN helps the system is made until Part 2 has passed. Until
then:
- every candidate set keeps `learned_relevance: false` (check 213);
- the page shows attempt 2 under its synthetic label;
- Part 1, when measured, is shown as "real documents, proposer only, not the system".
