# The learning signal: what Tier 2 is, and whether an operator decision can be it

Written 2026-09-12, before building anything, because the operator asked for the
mismatch to be settled rather than quietly resolved by substitution.

## The mismatch, stated

The GNN's own docstring (`scripts/ontology_gnn.py:6`) names four Tier-2 signals:

> DeltaProposal recurrence, Finding recurrence, VerificationVerdict,
> Precedent-Principle

**None of the four is an operator decision.** All four are properties of the
system's own output observed across runs. The decisions the system records
(approvals, conflict answers, waivers, overrides) are a different set.

## Are they two different things wearing one name?

**Yes. They are two distinct signals and should not be substituted for each
other.** The difference is what each one can teach.

**Tier 2 as the docstring means it is a SELF-CONSISTENCY signal.** DeltaProposal
recurrence means "this proposal arose again on another run". Finding recurrence
means "this finding keeps appearing". Neither says the thing is *right*. A
mechanism that reliably produces the same wrong answer scores high on recurrence.
Trained on recurrence alone, a model learns what the pipeline does often, which
is exactly the failure this project spent two days finding: the model emitted a
near-identical wrong sentence about UNIT-VETCH on both twins, and recurrence
would have rewarded it.

**An operator decision is a CORRECTNESS signal.** A conflict answer says which of
two competing claims the operator accepted. An approval says a specific escalation
was allowed. These carry ground truth that nothing in the system can derive for
itself.

They answer different questions. Recurrence answers "what does this system do
repeatedly". An operator decision answers "what is right". A learner given the
first and told it is the second will confidently learn to repeat itself.

## Which to build toward

**The operator decision, and not because recurrence is worthless.** Three reasons,
in order of weight.

1. **Recurrence is already partly present and already misleading.** The one
   DeltaProposal on disk carries `occurrence_count: 2`, `first_run_id: 2f174664`,
   `last_run_id: 479f3219` (`ontology/stores/delta_proposals.jsonl`). Those are the
   two runs of 2026-09-11, one flawed twin and one clean. A proposal recurring
   across a twin pair is the same signal the twin detector now reports as evidence
   that a claim did NOT come from the document. Recurrence across twins is a
   warning sign here, not a reward.

2. **The correctness signal has no other source.** Nothing in the system can
   derive whether a finding was right. The scorer needs an answer key, which
   exists only for benchmark corpora. On a real operator document there is no key,
   and the operator's own verdict is the only ground truth that will ever exist.

3. **The shape already exists and is one field from working.**
   `ontology_capture.py:197` sets `"status": "proposed"` with the comment
   **"operator-decision default (C1)"**, and `:206` says status is preserved
   because "the operator may have moved it past 'proposed'". The design already
   anticipated an operator verdict on a DeltaProposal. No route provides one.

So the honest reading is that **DeltaProposal status is where the two signals
meet**: the proposal is machine-generated (recurrence), and its status is the
operator's verdict on it (correctness). That is one record with a target and a
human verdict, of the same shape as a conflict Resolution.

## What the GNN would learn from once this is closed

Nothing, yet, and this needs saying plainly rather than being buried.

The GNN today is a **graph autoencoder** reconstructing its own input
(`ontology_gnn.py:22`). It has no label input at all. Giving it operator decisions
is not a matter of populating a file: it needs a second objective, because a
reconstruction loss cannot consume a label. That is a model change, not a data
change, and it is not in scope here.

What closing the data gap achieves is narrower and worth stating exactly: **the
rows would exist**, so the question "is there enough signal to learn from" becomes
answerable instead of unanswerable.

## How many rows a real run produces, and whether that is enough

This is the question that decides whether the whole direction is worth taking, so
it is answered with counts rather than optimism.

| source | rows per run, measured or derived |
|---|---|
| Conflict resolutions | **0.** No run has ever produced a conflict; the module says so itself (`ontology_conflicts.py:36`). Needs item THREE to produce any. |
| DeltaProposals | **1 across two runs** (the single row on disk, occurrence_count 2). |
| Approvals | **0.** No approval file exists anywhere. The escalation path exists but nothing on the review path escalates. |
| Redaction waivers | 18 rows, but run-level boilerplate with no target. Not a signal. |

**So the honest answer is: not enough, and it will stay not enough.** If a real
run yields on the order of one DeltaProposal and zero conflicts, then at one run a
day this produces a few hundred labelled rows a year, against a 28-feature model.
That is not a training set. It is an audit trail.

**What that means for what to build.** The rows are worth creating for their own
sake, because an operator verdict tied to a target is the only correctness record
this system will ever have, and because a conflict that is raised and answered
stops being raised again, which is a real operational gain independent of any
learning. They are NOT worth creating on the argument that the GNN will learn from
them, and this note exists so nobody makes that argument later.

**Do not touch the `tier2_signal` literal.** It says "empty" and it will still be
empty after this work: a handful of operator verdicts is not a Tier-2 signal, and
a flag claiming otherwise is the failure mode this project keeps catching. It
changes when there is a real corpus of decisions behind it and a model that can
read them, not before.

## What this note commits to building

- A conflict can be **raised by a run**, so a Resolution row can exist (item ONE,
  wired to item THREE which produces the conflicts).
- An approval record **carries its subject**, so a verdict is attached to
  something rather than floating.
- The graph builder **reads what governance holds**, so a decision reaches the
  graph at all.

And what it commits to NOT doing: no change to the GNN objective, no change to
the tier2 literal, no claim that any of this constitutes learning.
