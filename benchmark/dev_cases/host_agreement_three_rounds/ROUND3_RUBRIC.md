# Round 3 suggested wording: the rubric

**Not shown to any model.** This file is outside `workload/` and `ordinary/`. It was written on
8 November 2026, before any code that checks a suggestion's quote, position or agreed text existed,
and before any run (D-S46 item 3). It is scored by a checker who did not build the case or the
code, and the outside check (D-S40) reads the result.

## What is scored

One suggestion per open issue, for the party the case names: the Organisation. The open issues are
tax relief, entry period, dependants, the annual contribution and the security provision. Each
issue's position and fallback for the Organisation are declared in `workload/case_manifest.json`
(`issues[].position`, `issues[].fallback`), and so are the units both sides recorded as agreed
(`issues[].closed_units`: Arts. 2, 5, 7 and 12).

A suggestion Python refused is not scored on the four criteria. It is listed with Python's reason,
and the checker says whether the refusal was right.

## The four criteria

| | Criterion | Who checks | Pass when |
|---|---|---|---|
| Q | **The quote** | Python first, then the checker | The suggestion's quote is copied word for word from a round 3 passage it cites (Python), and that passage is the one the suggestion actually rests on (checker). |
| P | **Inside the Organisation's position and fallback** | Python for figures, the checker for words | It asks for no more than the Organisation's declared position and accepts no less than its fallback. Python refuses a figure outside that range in the same measure; where the issue is in words, the checker judges. |
| A | **Agreed text left alone** | Python first, then the checker | It does not change text both sides recorded as agreed (Python refuses one citing a closed unit), and it does not take back what the Organisation already accepted (checker). |
| U | **Useful to the Organisation's argument** | The checker | 0: no help, or it harms the Organisation's position. 1: it helps, but would need reworking before tabling. 2: a delegation could table it as written. One line saying why. |

A suggestion counts as good only when Q, P and A all pass. U is reported per issue and on average
over the good ones.

## The score sheet

| Issue | Python's outcome | Q | P | A | U (0 to 2) | The checker's reason |
|---|---|---|---|---|---|---|
| tax-relief | | | | | | |
| entry-period | | | | | | |
| dependants | | | | | | |
| annual-contribution | | | | | | |
| security-provision | | | | | | |

The figure to report is: good suggestions out of five, the mean U over them, and the refusals with
the checker's view of each. The shipped model's writing of wording has never been measured, so no
target is set, and any number reported comes with this sentence.
