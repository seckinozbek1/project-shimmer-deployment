# Held-out openings (D-330)

Every opening of an optimised part's held-out development material is one line here. The lead writes it before the result is read and commits it. A lane's code refuses to score its held-out part unless the line for that attempt exists in a commit, and a committed record shows the candidate passed its tuning part.

The k-th opening of a part is tested at alpha 0.05 / 2^k, one-sided. However many attempts a part takes (D-S72), the chance of any false success for that part stays at most 0.05.

A held-out part tells the next recipe pass or fail only, never which items (LESSONS L-4). The fresh set is not a held-out part; it is read once, by the whole system (D-322).

| Part | k | Alpha | Attempt | Held-out material (file, digest) | Tuning pass record (commit) | Written | Result |
|---|---|---|---|---|---|---|---|
| ontology-pairs | 1 | 0.025 | 2 | generator block 930001-930040 (listing digest when generated) | lane/ontology 84307a38 (attempt 1 is outside the rule and passed nothing; the recipe and the margin are in code there) | 2026-11-08 21:25 | PASS (rule at 84307a38): beats the shipped ranker and the structural control by the 5-point margin at K 10 and 40, sign test at alpha .025; not real progress over attempt 1's model (-1.5 points at K 10); synthetic generator tests only |
| auditor_rule_check | 1 | 0.025 | 2 permissive_mix@trained_full | rule_check_dev.json b5a47e9625c8866cec1685ffa4dd445b13d43a7b837da1c9c2d2fba2b79b9d6e | 62ec720a | 2026-11-09 13:52 | fail (read-b 2026-11-09, attempt 2, permissive_mix@trained_full; pass or fail only) |

The first opening above. The judge's half B was read once for T (D-294) before this ledger existed; under D-330 it is spent and is no held-out part.
