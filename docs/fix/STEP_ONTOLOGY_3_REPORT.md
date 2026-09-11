# ONTOLOGY JOB 3: remember the operator's decisions

**Built, not measured.** No run has ever produced a conflict, because the ontology store is
empty: `provisions.jsonl` is zero bytes, the only writer is run-end capture, and no run has
been made since the store was scoped. Every path here is proved on fixtures in the verify
gate. Nothing in this job is known to be useful on real content; it is known to be correct on
fixtures. No pipeline run was started and no model was loaded at any point.

## The decision this implements

The operator's words: when the ontology conflicts with a rule, the conflicted pair is refused
in that run, never guessed; the refusals are listed and put to the operator together at the
end; the next run applies their answers; the answer is written to the ontology so the same
conflict is never put to them twice; and the override rate is tracked, with the caveat
recorded that at single-operator volume it is not statistically meaningful.

Every clause of that is a rule about what **not** to do, which is why the module is mostly
refusals.

## What a conflict is, narrowly

The store remembers which rule governed a provision when a past run captured it. The current
run has a rule it would apply to the same provision. A conflict is the case where those two
identifiers disagree about the same provision id.

Nothing semantic is inferred. The module compares identifiers, never meanings, and it never
asks whether a rule is right. Two things that look like conflicts are deliberately not:

- a provision the store has never seen, because an absent memory is not a disagreement;
- a provision whose stored rule matches, obviously.

A stored record carrying no rule at all is also not a conflict, for the same reason as the
first case.

## What refusal means

The conflicted pair produces no finding in that run. Not a guess, not the store's answer, not
the rule's answer: nothing, recorded as refused with both sides named and the reason stating
both rule ids. This is why the module cannot resolve a conflict on its own even when one side
looks obviously better: resolving it would be the guess the decision forbids.

## Never asked twice

An answered conflict is written into the ontology as a `Resolution` record, through the same
scoped storage layer provisions and relations use, keyed by a stable conflict id derived from
the provision and both rule ids. A later run that meets the same conflict finds the
resolution and applies it without asking.

A conflict whose **sides have changed** hashes to a different id and is therefore asked
again. That is correct, not a bug: if the current run would now apply a third rule, the
operator has not answered that question.

**Three answers are recognised, not two.** The rule wins, the store wins, or keep refusing.
"Keep refusing" is a real decision (the operator may want the pair to keep producing nothing)
and is deliberately distinguishable from never having answered. An answer the module does not
recognise is **refused rather than stored**, because storing it would make every later run
either re-ask or, worse, act on an instruction nobody wrote.

Because the storage layer supersedes by id, an operator who changes their mind writes a new
answer and the latest one is what a later run reads. That behaviour is inherited, not
reinvented here.

## The override rate, and its caveat

Answers where the current rule won over the store's memory, over answers total. It is served
by `GET /ontology/conflicts` and it **carries its own caveat inside the return value**, not
only in documentation, so no caller can report the number without it: at single-operator
volume it is not statistically meaningful and must never be read as a quality measure.

It is `null`, never `0.0`, when nothing has been answered, because "no answers yet" and
"never overrode" are different facts and a rate that conflated them would be actively
misleading on exactly the store every installation has today.

## The reading path is real, and exercised

The brief asked for this specifically: the reader must not be a function nobody calls.

- Detection reads the scoped store through the storage layer.
- Resolutions are written through it and read back by a later run, which is the mechanism,
  not a description of one.
- `GET /ontology/conflicts` serves the answered conflicts and the rate.
- Check 212 drives all of it end to end on a fixture store.

## A defect this job found, in job 1's code

Writing `Resolution` records into the same store made `provenance_summary` count them as
provisions, the same way job 2's relations had. The read path now tests an **allowlist**
(`node == "Provision"`, with a record carrying no node treated as a provision, which is every
record written before job 2) rather than a list of node types to exclude, so a fourth node
type added later cannot leak in by being forgotten. Provisions, relations and resolutions now
coexist in one scope, each read by its own reader, with no count contaminating another.

## The check, and its neutralise-and-restore proof

Check 212, `ontology conflicts and the operator's answers`. It asserts the whole cycle on a
fixture store: one disagreement among three candidate pairs is detected and the other two are
correctly not conflicts; with nothing answered the pair is refused and listed, with both
sides named in the reason; the operator's answer is written once; the next run applies it and
asks nothing; `refuse` is applied and produces nothing; a conflict whose sides changed is
asked as the different question it is; an unrecognised answer is refused rather than written;
the override rate counts correctly and is `None` on an empty store; and resolutions
contaminate neither the provision nor the relation counts.

**Neutralise:** `resolutions_in` is replaced by one that always reports no memory, which is
the defect the never-ask-twice requirement exists to prevent.

```
neutralised -> FAIL: an answered conflict must never be put to the operator twice
restored    -> PASS
```

Run alone, before the full gate:

```
PASS  ontology-versus-rule conflicts: a disagreement about the same provision is detected and
      REFUSED in that run with both sides named and neither guessed, an agreeing pair and an
      unseen provision are not conflicts, the operator's answer is written into the ontology
      and applied by the next run so the same conflict is never asked twice, 'refuse' is a
      real answer that produces nothing, a conflict whose sides changed is re-asked as the
      different question it is, an unrecognised answer is refused rather than stored, and the
      override rate carries its own not-meaningful-at-this-volume caveat (None, never 0.0,
      when nothing is answered); neutralise (no memory of an answer) FAILS, restore PASSES
```

## README, checked start to finish against the tree

- The new route added to the table (check 167 fails in both directions; it now agrees at 22
  routes).
- The check count corrected from 212 to 213 in both places that state it.
- Check 212 named in section L's coverage list.
- The `scripts/` tree line naming the conflict memory.
- A section G paragraph stating the decision, the three answers, the never-twice rule and the
  override rate's caveat.

## Not built, recorded

- **The pipeline does not call this yet.** Detection, refusal, the operator's answers and the
  memory are complete and exercised, but no phase invokes them, because there is nothing in
  the store to conflict with and the wiring point belongs with the first run that has content.
  The call site is one place in phase 8 beside the existing capture, and it is named here
  rather than left implicit.
- **No console section.** The conflicts surface would render nothing on every installation
  today. The route exists and is the read path; a console section follows when a run has
  produced a conflict to show.
- The override rate has never been computed on real answers, only on fixtures.

---

ONTOLOGY JOB 3 COMPLETE (conflicts detected structurally and refused in-run with both sides
named, refusals listed for the operator, answers written into the ontology and applied by the
next run so the same conflict is never asked twice, three answers recognised including
"keep refusing", unrecognised answers refused, the override rate served with its
not-meaningful caveat inside the response; check 212 with neutralise and restore; a node-type
allowlist defect found and closed in job 1's reader; built without measurement because the
store is empty and the first conflict arrives on the first run after the move)
