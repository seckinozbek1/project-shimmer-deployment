# D-792: the four set jobs, planned (19 November 2026, lead 8fee59db)

Seckin's decision D-792 (14:29): fix every set gap at once, as parallel jobs. Same rules for every job: no
tuning on labels; a leakage check in every set's declaration; every set carries a look counter (standing
order 88: how many times it was looked at and which changes were tried on it); before any set is built, the
real items are counted and the split and its cost go to Seckin, who gives the word (standing order 90); a
forecast and his yes before any money. Real benchmark items are reached only through role B (the builder never
reads benchmark data, H17); synthetic negotiation items through the seeded generator and role V's blind
labelling (NEG-SYNTH-A). The v1.1 claim sets and the preregistration v3 SciTab share are never touched,
sampled from or looked at for selection.

| Job | What | Owner | First step (0 USD) | Then, after Seckin's word | Expected cost | Expected finish |
|---|---|---|---|---|---|---|
| 1 | Validation sets: negotiation, ContraDoc, SciTab | role B (ContraDoc, SciTab); generator and role V (negotiation) | role B session BCOUNT1 counts what is left unused in both pools, by group, paper and gold class (counts only) | role B draws each validation set by a seeded, written rule from the unused part; negotiation validation from new seeded cards, labelled blind | draws 0 USD; negotiation labelling about one role V Lambda pass (the last one cost 2.46 USD) | counts within an hour of BCOUNT1's start; draws the same day after his word |
| 2 | A SciTab development and validation set that holds not-enough-info | role B | BCOUNT1 reports the unused claims by class and the unused papers holding not-enough-info | role B draws whole papers (the split is by paper) until both sets reach the size Seckin chooses | 0 USD to build | same as job 1 |
| 3 | A fresh validation and pilot set per fix (D-789), built and frozen before the fix is tried | role B; generator and role V | the size per fix is proposed with BCOUNT1's counts: each fix uses up unused material, so the number of fixes the pools can serve is stated beside it | one draw per fix, frozen with its digest and a look counter at 0, before the fix's first run | 0 USD to build; each fix's runs are priced with the fix | per fix, before its first run |
| 4 | Negotiation development (65) and pilot (31) labels through role V's merge | lane/label-wording-reader, then role V | found: the labeller read only 81 of 1201 positions (1120 dropped for the wording's form; the model quoted the bracketed text) | the reader fix re-reads the saved replies (no new paid labelling run), then the review merge runs again | 0 USD (re-read of saved replies) | the same afternoon, after the lane and one role V session |

Leakage check in each declaration: exact text, normalised text and group or paper identity against every
development, tuned, fresh, claim, quick and v3 set, with the counts recorded before the set is first read.
Look counter: a `looks` list in each set's declaration (time, purpose, change tried), started at zero.
