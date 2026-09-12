# Checks that prove a reading rather than an effect

**Historical worked cases.** THIRTEEN is complete; see "THIRTEEN implemented,
2026-09-12" below and [RESUME.md](RESUME.md) for the current consumer-effect
protocol. The pending-work language in the original analysis is historical.

TWO-E. Carried here as the worked case for item THIRTEEN, which has to propose a
cheap structural check that catches this shape.

## The worked case: `unless` at f1f09cd

The parser read `[unless: ...]`, the registry entry carried it, the paired
payload carried it, and the ontology drew a `QUALIFIED_BY` edge for it. Check 236
proved every one of those. All of it passed, and the declaration **suspended
nothing**: no code evaluated it, so no rule was ever withheld from a unit because
of it. The feature was built, gated, documented and inert, and the gate was
green throughout.

The check proved the declaration was READ. It never proved it CHANGED AN
OUTCOME. Those are different claims, and only the second one is the feature.

## What the pattern is, stated so item THIRTEEN can act on it

A check of this shape:

1. exercises a PRODUCER (a parser, a builder, a payload assembler) and asserts
   on the structure it returns, and
2. never calls the CONSUMER that is supposed to act on that structure, so
3. removing the consumer entirely would leave the check green.

The last line is the operational test, and it is the one worth automating:
**if deleting the code that acts on X leaves the check that covers X passing,
the check covers the reading of X and not the effect of X.**

## What the scan found

Two passes over all 239 checks.

**First pass** looked for checks with "reading" assertions and no "effect"
words. It returned 9 candidates. The three strongest (18, 39, 152) were all
FALSE POSITIVES, and instructively so: they do test effects, by feeding
malformed input and requiring rejection. That evidence reads as ordinary
assertion syntax, so a word-based heuristic cannot see it. Recorded because item
THIRTEEN will be tempted by the same heuristic.

**Second pass** looked for checks that touch a producer and never a decider. It
returned 48, which is too coarse to be a finding: the decider list is
necessarily incomplete, so most are false positives too. A list of 48 suspects
is not a result.

Neither heuristic is good enough to ship as the check item THIRTEEN wants. What
does work is the deletion test above, and that is what THIRTEEN should cost out.

## The one confirmed second instance: a convention's declared severity

Found by following the pattern rather than the heuristic, in the sibling of the
check that missed `unless`.

**Check 197** proves that a convention heading's brackets are read: it asserts
CONV-D01 comes out `severity=required` with subjects `['conformance']`, CONV-D03
comes out `advisory` with none, and so on. Every assertion is about what the
PARSER PRODUCED.

**Nothing decides anything from it.** Every computed amendment hardcodes
`"severity": "required"` (`paired_review.py:2115`). The seven other places that
read a rule's severity are all DISPLAY: the bus viewer, the summary generator, a
graph node attribute, an API echo. Not one of them changes what the run does.

So an operator who writes `[advisory]` on a heading gets:
  - a correctly parsed `advisory` severity, proved by a green check
  - an amendment marked `required` anyway
  - and no error, anywhere

**Why it stayed invisible:** all 8 rules in the shipped corpus declare
`required`, so the hardcoded value is indistinguishable from the real one on
every rule that exists. The corpus cannot reveal this defect; only reading the
consumer can.

**Not fixed here, and deliberately.** Deciding what `advisory` should DO is an
operator's call, not a repair: it could lower the amendment's severity field,
suppress amendment generation entirely, or route the finding to a different
section. Recorded with a recommendation instead.

**Recommendation:** an `advisory` rule should still produce its finding (the
arithmetic is the same and the operator still wants to see it) but should not
produce an AMENDMENT, since an amendment is a proposed change to the document
and an advisory rule by its name is not asking for one. That is one branch at
the amendment-minting site, and it makes the declared severity mean something
for the first time.

---

# THIRTEEN-B: the neutralise that was never at risk

A second shape, distinct from reading-not-effect, and worse in one respect: it
defeats the discipline that is supposed to catch the first.

## What happened

TWO-F added a refusal for an unrecognised severity. To prove it, I neutralised
the branch that refuses:

```python
if _amends is None:     ->    if False:
```

The check stayed GREEN. Not because the check was weak, but because `None` is
falsy and the NEXT branch (`if not _amends:`) caught the same case and withheld
the amendment anyway. Two independent paths produced the same outcome, so
disabling one changed nothing.

I read the green as a gap in the check and started to strengthen the check. That
was the wrong diagnosis: the check was fine, the NEUTRALISE was a no-op.

## Why it is worse than reading-not-effect

Reading-not-effect produces a check that proves too little. This produces a
check that **reports a pass that was never at risk**. Neutralise, fail, restore,
pass is the discipline the whole gate rests on, and here it ran to completion
and certified nothing. A green from an ineffective neutralise is
indistinguishable, in the log, from a green that was genuinely earned.

## The operational test

**A neutralise proves nothing unless the neutralised code is the ONLY thing
producing the behaviour under test.**

Stated as a procedure, since that is what THIRTEEN has to automate:

1. neutralise the code
2. the check must go RED
3. **if it stays green, do not conclude the check is weak.** First establish
   whether a second path produces the same behaviour. Until that question is
   answered, neither the check nor the code has been shown to be wrong.
4. a neutralise that leaves the behaviour intact is not evidence of anything and
   must not be recorded as a proof

The trap in step 3 is the expensive part. The natural reading of an unexpected
green is "my check is too weak", and acting on that reading means editing a
check that was already correct, to catch a defect that was never there.

## What a safe fallthrough is, and why it is not a bug

The two-path structure above is DESIRABLE: an unknown severity is withheld by
two independent branches, so removing either one leaves the safe behaviour
standing. Defence in depth is not a defect. What it is, is **unprovable by
single-point neutralisation**, and a check over such code has to neutralise the
thing that genuinely changes the outcome. Here that was the predicate's return
value:

```python
return None, (...)    ->    return True, (...)
```

which does turn check 239 red, and was used instead.

## What THIRTEEN has to catch

Both shapes, and they need different tests:

| shape | symptom | test |
|---|---|---|
| reading-not-effect | check passes with the consumer deleted | delete the consumer; check must go red |
| neutralise-not-at-risk | check passes with the neutralise applied | neutralise must change observable behaviour BEFORE the check is consulted |

The second is the cheaper of the two to automate: a neutralise step can assert
that the neutralised build actually behaves differently, independently of what
any check says about it.

---

## Other places worth the same question, not yet checked

Named so the next reader has somewhere to start, not asserted as defects:

- **`action` on a convention: checked, and it is the same defect.** All 8 rules
  declare `flag`, it is hardcoded `"flag"` at the same amendment site, and every
  reader of it is display (bus viewer, summary, graph attribute, API echo) with
  ONE real exception: `sensitivity_layer/rules.py:112` does decide from it, but
  only for redaction rules, never for a review convention. The `chat.py` hits
  are a different `action` entirely (a parsed chat command) and are not related.
  So `severity` and `action` are one finding, not two.
- the subject tags from check 197: they reach the convention assignment, which
  does act on them, so this one is probably sound. Not verified.


## THIRTEEN implemented, 2026-09-12

The historical severity/action and unless findings above were subsequently fixed
by the ratified TWO work; they remain evidence here, not newly reopened decisions.
The cheap structural answer is scripts/effect_proof.py, replayed by gate check 248.
It takes four explicit boundaries plus a name: input validation, an independent
consumer observation, the check, and a reversible mutation context. Execution order
is fixed: valid inputs, clean observation/check, mutation, independent observation,
mutated check, restoration, clean observation/check. A mutation with no observed
effect never reaches the mutated check. Mutable observations are snapshotted as
JSON; non-finite and non-JSON values refuse. A probe exception is not a killed test.
Restoration is verified even after a refused proof.

This separates NO_OBSERVED_EFFECT from SURVIVED. The former is inconclusive: a safe
fallthrough may preserve behavior, or the observation may omit the changed outcome.
It must not automatically accuse either the check or the mutation of being wrong.
The latter establishes a changed declared outcome with a green check, which is the
reading-not-effect failure when that check claims to cover this consumer.

The pilot is a real consumer: remove RunCompletion.reached_end. A separate disk
observer sees completed become stopped and final counts disappear. Existing check
246 fails, then passes after restoration. A deliberately reading-only check over
the same declared input survives and is refused. Synthetic protocol cases establish
ordering, invalid-input rejection, no-effect refusal, surviving-check rejection,
probe-error rejection and restoration. Five guard mutations first change the
protocol's independent classification/order, then fail check 248, then restore PASS.
They never edit real source files or start a pipeline.

Scope is explicit: this does not certify all prior checks, infer the right consumer,
or decide whether an observer is complete. It prevents accepting these proof shapes
for callers using the helper and replays the completion pilot on every gate. Adopt it for
new effect claims when a cheap deterministic consumer fixture is available. Each
claim still needs a reviewed outcome projection: dates and random paths cannot be
used as evidence that work completion changed. Revisit the projection when behavior
moves to another branch; check 197's fallback and the narrow fingerprint incident
are precisely why an unchanged projection is not a finding by itself.

The expensive general version needs a maintained claim-to-consumer mutation map,
independent artifact observations, isolated mutations of every relevant branch,
and a baseline/mutated/restored suite run per mutation. It must also resolve
surviving mutants and distinguish equivalence from missing coverage. There is no
cheap syntax scan that supplies those semantic decisions. The two failed scans
above are retained; neither was repeated or shipped.
