# Threshold measurement for the five-voter ensemble

WORDS-A constraint 3: each voter's threshold is justified by measurement and by
the margin between the closest true case and the closest false one, never by a
round number. This file is that measurement, and it reports a result I did not
expect and cannot round away.

## Method

Leave-one-out over the operator's reference set in
`config/semantic_references.json`, so a reference never matches itself, plus
every one of the 44 shipped convention rules as an additional TRUE NEGATIVE
(none of them is a redaction rule).

- 15 positive references, 12 negative references
- 44 shipped rules, all negative
- each voter scores `best_positive - best_negative`, so a candidate merely IN
  THE DOMAIN does not score as a match

The threshold, where one exists, is the midpoint of the measured gap.

## Result: one voter of five separates the classes

| voter | closest true | closest false | margin | threshold | separates |
|---|---|---|---|---|---|
| sbert | +0.0787 | +0.0330 | **+0.0457** | **0.0559** | **yes** |
| keybert | -0.0563 | +0.0552 | -0.1115 | - | no, overlaps |
| tfidf | -0.0596 | +0.1190 | -0.1786 | - | no, overlaps |
| bow | -0.1389 | +0.1500 | -0.2889 | - | no, overlaps |
| word_overlap | -0.3333 | +0.0000 | -0.3333 | - | no, overlaps |

A negative margin means the closest true case scores BELOW the closest false
case. No threshold separates them. There is no honest number to put in the
config for four of the five voters.

## Why the four overlap, which is diagnostic rather than incidental

Every failure is the same failure, and it is the known weakness of lexical
methods on a small reference set.

**The weakest true cases are the lexically isolated ones.** Under leave-one-out,
"Conceal the date of birth in every deliverable" loses the only other reference
sharing its vocabulary, and scores -0.14 on bag of words and -0.33 on word
overlap. It is a perfectly good redaction rule; it just has no lexical twin.

**The strongest false cases share a common word with no shared meaning.**

- bow ranks "Every entry must state a calibration date" at +0.15, above every
  true case, because it shares `date` and `state`.
- tfidf ranks "Diagnosis is the fleet engineer's task, not the reviewer's" at
  +0.12, because `reviewer` is distinctive in the reference set.
- keybert ranks "The GPP minimum annual payout must sit inside 4% to 6%" at
  +0.055, above four true cases.

These are precisely the sentences a keyword table gets wrong, scoring highly for
sharing a word while meaning something unrelated. **The lexical voters reproduce
the defect the ensemble exists to fix**, which is worth knowing and is the
opposite of a reason to keep them at a fitted threshold.

## What this does to WORDS-A, stated rather than worked around

WORDS-A requires five voters and three of five, and constraint 4 says no voter
is dropped silently. Constraint 3 says a threshold is justified by measurement.
**On this decision those two constraints are in conflict**: four voters have no
measurable threshold, so either they run on an unjustified number or the
ensemble cannot reach five.

I will not invent four thresholds. A number chosen so a voter can participate is
the round number constraint 3 forbids, dressed as a measurement, and it would
give three lexical votes that are demonstrably wrong on this decision the power
to outvote the one method that works.

**So the ensemble REFUSES on this decision, by its own constraint 4**, and the
refusal names the four voters that have no measured threshold. That is the
designed behaviour of a rule that cannot be satisfied, and it is reported to the
operator rather than resolved by me.

## What would make five voters possible

Not guesses, and not mine to choose:

1. **A larger reference set.** The lexical voters fail on isolation: 15
   positives is too few for a bag of words to have seen the vocabulary. Perhaps
   40 to 60 positives, with lexical variety deliberately included. This is
   operator-written text and is the operator's job, the same way the severity
   corpus is (WORDS-C).
2. **Per-voter reference sets.** The dense voters want few, clean examples; the
   lexical ones want many, varied ones. One set serving both is a compromise
   that suits neither.
3. **Dropping to a dense-only ensemble of different models** (bge-m3 plus a
   second embedding model, with different pooling), which meets "never one
   method alone" but not "these five".
4. **Accepting three of five where the three are measured**, changing the rule
   rather than faking the inputs.

My recommendation is (1), then re-measure. It is the only option that keeps
WORDS-A as written.

## What is NOT blocked by this

The measurement itself is the useful artifact, and it already answers TWO-K's
question. SBERT, the one voter that separates, scores the case that motivated
the whole item:

```
"The reviewer must not publish the client's address."   (active prohibition)
  cosine against "Redact the client name..."     = 0.597
  cosine against "Findings must withhold judgement..." = 0.340
```

The active-voice prohibition that the regex silently failed to compile is
clearly separated by the dense voter. The capability is demonstrated; what is
missing is four voters' worth of calibration data, which is reference text an
operator writes.
