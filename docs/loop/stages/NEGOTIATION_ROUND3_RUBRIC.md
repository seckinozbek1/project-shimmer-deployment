# Round 3 suggested wording: the rubric for any case (D-S102 item 8)

**Not shown to any model.** This is the rubric the graders apply to every held-out case
(`NEGOTIATION_MEASUREMENT_PLAN.md` section 4). It is the rubric of 8 November 2026
(`benchmark/dev_cases/host_agreement_three_rounds/ROUND3_RUBRIC.md`), with the worked case's names
replaced by each case's own declarations. The criteria and their pass rules are unchanged. It was
committed before any grading, and the differences from the original are listed at the end.

## What is scored

One suggestion per open issue of a case, for the party the case declares `supported`. The case's
`case_manifest.json` declares, for each open issue:

- the party's position (`issues[].position`) and fallback (`issues[].fallback`);
- the units both sides recorded as agreed (`issues[].closed_units`).

The case's `KEY_ROUND3.json` gives, for each open issue, the round-3 passages a good suggestion may
rest on and the agreed text it must leave alone.

The graders see each suggestion in one common form: its wording and the passage it quotes, as plain
text, with no arm, no citation ids, no model mark and no refusal reason. A suggestion that Python's
checks refused is not shown in the first pass. It is scored not good, and in a second pass the
graders say whether the refusal was right.

## The four criteria

| | Criterion | Who checks | Pass when |
|---|---|---|---|
| Q | **The quote** | Python first, then the grader | The suggestion's quote is copied word for word from a last-round passage it cites (Python), and that passage is the one the suggestion actually rests on (grader, against `KEY_ROUND3.json`). |
| P | **Inside the party's position and fallback** | Python for figures, the grader for words | It asks for no more than the party's declared position and accepts no less than its fallback. Python refuses a figure outside that range in the same measure; where the issue is in words, the grader judges. |
| A | **Agreed text left alone** | Python first, then the grader | It does not change text both sides recorded as agreed (Python refuses one citing a closed unit), and it does not take back what the party already accepted (grader). |
| U | **Useful to the party's argument** | The grader | 0: no help, or it harms the party's position. 1: it helps, but would need reworking before tabling. 2: a delegation could table it as written. One line saying why. |

A suggestion counts as good only when Q, P and A all pass, by Python and by the grader.

## The score sheet, per case

| Case | Issue | Q | P | A | U (0 to 2) | Guessed arm | The grader's reason |
|---|---|---|---|---|---|---|---|

Each grader also guesses which arm wrote each item (system, B1 or cloud reference). The rate is
reported against chance (plan section 4.4).

## The figures reported

The plan's section 4.5:

- the good-suggestion rate over open issues;
- mean U over all open issues, a suggestion that is not good scoring 0;
- mean U over the good ones;
- each arm's refusal rate;
- the share of Python's refusals the graders judge right.

The shipped model's writing of wording has never been measured on held-out cases, so no target is
set, and any number reported comes with this sentence.

## Differences from the original (8 November)

1. "One suggestion per open issue, for the party the case names: the Organisation. The open issues
   are tax relief, entry period, dependants, the annual contribution and the security provision."
   becomes "one suggestion per open issue of a case, for the party the case declares `supported`".
   The issues are each case's own.
2. "for the Organisation are declared in `workload/case_manifest.json` ... (Arts. 2, 5, 7 and 12)"
   becomes the case's own `case_manifest.json` declarations, with no article named.
3. "a round 3 passage" becomes "a last-round passage", and the grader's judgement of Q is made
   against `KEY_ROUND3.json`. The original grader judged without a written sheet.
4. "the Organisation's" becomes "the party's" in P, A and U.
5. Added: the common display, the refusals' second pass, the guessed-arm column (plan section 4.4).
6. Added: mean U over all open issues and each arm's refusal rate, beside the original's figures
   (plan section 4.5).
7. The original's sheet listed five fixed issues and reported "good suggestions out of five"; the
   sheet is now per case, and the rate is over all open issues.

Nothing in Q, P, A or U, or in "good only when Q, P and A all pass", is changed.
