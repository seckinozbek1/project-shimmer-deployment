# Evaluation set inventory (operator request, 20 November 2026 14:36)

Written 20 November 2026 by a read-only helper for the lead, from tracked records only: docs/loop/DECISIONS.md,
docs/loop/HELDOUT_OPENINGS.md, docs/fix/OPEN_ITEMS.md, docs/loop/stages/*.md, config/neg_synth.json,
config/semtabfacts_aux_val.json, and the README.txt, plan.json and request draft in external/s05/QUICK_READ_ALPHA and
external/s05/TRIAL40_ALPHA (outside git, read as named in the request). No key, label, held key file, benchmark/keys
or role folder was opened; nothing was launched. docs/loop/private is untracked (gitignored, .gitignore:212) and was not
read, so figures that live only there (BCOUNT1 and BDRAW1 hand-backs, per-paper claim counts) are marked "not in
tracked records". Every number carries its source as file:line. "Looks" counts recorded reads that produced or could
produce a figure; a steering read of the quick subset is a look.

## 1. ContraDoc

| Set | Kind | Serves | Items | Looks | Labelled | Source |
|---|---|---|---|---|---|---|
| Development (D-S63 delivery) | development, all tuned | G1, judge calibration, fixes | 231 documents in 163 groups; 0 clean | many (G1 half A and B, B3 runs) | yes (role B keys) | GATE_SET.md:22-29 |
| G1 half A / half B | development | C_BAR thresholds, judge calibration / T read | 30 / 30 documents | many / spent (read once for T) | yes | GATE_SET.md:25-26; HELDOUT_OPENINGS.md:19 |
| Fresh set D-S56 | was the one fresh test; now pilot plus reserve | judge-alone fresh test (alpha .05 one-sided, power .80 at 100); since D-692 a pilot of about 50, then development | 100 documents, one a group (62 + 38) | 0 (unread at D-692) | yes, keys with role B | DECISIONS.md:2979, 2987, 7474 |
| Fresh set's other group members | excluded | never read, overlap filters only | 14 documents (114 minus 100); 9 siblings in build_moved | 0 | yes | GATE_SET.md:24; DECISIONS.md:2996 |
| TRIAL40_ALPHA (from the fresh set) | pilot (trial) | alpha 40-document trial; 50 cut to 40 | 40 documents planned (draw not yet made) | 0 (not built, not run) | yes, role B scores | TRIAL40_ALPHA/README.txt:1-2; REQUEST_ROLE_B_TRIAL40.draft.md:9-14; DECISIONS.md:8349 |
| Fresh set left after the trial | reserve ("unread and reserved for a later, larger test") | none yet | 60 documents (100 minus 40) | 0 | yes | DECISIONS.md:7474, 8349 (arithmetic) |
| Gate quick subset 0127b080 | quick subset, steering only | direction for the claim read; QUICK_READ_ALPHA | 40 documents in 40 groups | 5 steering rows (K0 15 Nov, K1, K0, B1 on 13 Nov, QUICKSCORE2 19 Nov); a sixth planned (QUICK_READ_ALPHA) | yes | GATE_SET.md:290; HELDOUT_OPENINGS.md:13-17; QUICK_READ_ALPHA/README.txt:8-12 |
| Gate claim set b0a942ad | final test (full release, the old v1.1) | bars (a) and (b), read once at alpha .025 | 230 documents in 230 groups | 0 (no gate-claim-set row) | yes | GATE_SET.md:289, 165-169; HELDOUT_OPENINGS.md:9-17 |
| of which the D-692 locked half | final test | opened once at the end | about 115 documents (draw by group rule; no record that role B has drawn it) | 0 | yes | DECISIONS.md:7474-7475 |
| of which the other half | held (reserved for a later, larger test) | none | about 115 documents | 0 | yes | DECISIONS.md:7474 |
| Sealed side, kept groups not drawn | held, later used by BDRAW1 | D-798 validation and per-fix sets | 136 groups (406 kept minus 270 drawn) | 0 | yes | GATE_SET.md:296, 289-290; DECISIONS.md:8135 |
| BDRAW1 contradoc_val | validation | D-798 general validation | 40 groups | 0 at freeze; no read in tracked records | yes | DECISIONS.md:8135 |
| BDRAW1 per-fix sets (3 fixes) | validation and pilot per fix (D-789) | three future fixes | 3 x (20 validation + 10 pilot) = 90 groups | 0 at freeze; no read in tracked records | yes | DECISIONS.md:8135 |
| Kept groups left after BDRAW1 | held | none | 6 groups (136 minus 130) | 0 | yes | DECISIONS.md:8135 |
| Sealed side, leakage-excluded groups | held, unusable (overlap) | none | 111 groups (144 candidates) | 0 | yes | GATE_SET.md:227 |

Note on the TRIAL40 open question (TRIAL40_ALPHA/README.txt:23-24): the 136 groups BDRAW1 drew from are the sealed side's
kept groups beyond the gate draw (406 minus 270, GATE_SET.md:289-290, 296), while the fresh set is on the development side
(GATE_SET.md:24, 40). On the records they are two different pools, so the trial does not compete with contradoc_val.

## 2. SciTab

| Set | Kind | Serves | Items | Looks | Labelled | Source |
|---|---|---|---|---|---|---|
| Development | development, all tuned | G1 | 95 claims in 29 tables from 15 papers | many | yes | GATE_SET.md:31-33 |
| Holdout pool (band A) | held, source of everything below | | 1,129 claims in 184 tables | | yes | GATE_SET.md:41 |
| Preregistration v3 sealed share | held (only Seckin may release) | v3 sealed evaluation | 30 tables (claims not in tracked records) | 0 | yes | GATE_SET.md:48-59; DECISIONS.md:7474 |
| Gate quick subset 0127b080 | quick subset, steering only | direction | 78 claims, 13 tables, 6 papers | 5 steering rows (one, K0 13 Nov, refused with no figure); a sixth planned | yes | GATE_SET.md:290; HELDOUT_OPENINGS.md:13-17 |
| Gate claim set b0a942ad | final test (full release) | macro-F1, 3-class | 363 claims, 61 tables, 24 papers (supports 122, refutes 110, not enough info 131) | 0 | yes | GATE_SET.md:289, 292-294 |
| of which the D-692 locked half | final test | opened once | about 182 claims (by tables) | 0 | yes | DECISIONS.md:7474-7475 |
| of which the other half | held (reserved) | none | about 181 claims | 0 | yes | DECISIONS.md:7474 (arithmetic) |
| scitab_val2c (BDRAW1) | validation, 2-class | D-798 SciTab validation | 8 whole papers (claims not in tracked records) | 0 at freeze; no read in tracked records | yes | DECISIONS.md:8134; TABLE_TOOL_MEASURE_PLAN.md:27-28 |
| Unused papers with no not-enough-info | held for later per-fix sets | none yet | 14 papers (claims not in tracked records) | 0 | yes | DECISIONS.md:8134 |
| D3 pool (D-778) | not drawn | was the cell_claim threshold | 83 claims, 0 not-enough-info; draw stopped | 0 | yes | DECISIONS.md:8057 |
| Sealed manifest after the gate draw | held | | 688 claims remain of 1,129 | | yes | GATE_SET.md:301-302 |

## 3. SEM-TAB-FACTS auxiliary (never a SciTab score)

| Set | Kind | Serves | Items | Looks | Labelled | Source |
|---|---|---|---|---|---|---|
| semtabfacts_aux_val (dev and test) | validation, development side | not-enough-info question; table tool | 104 tables, 57 articles, 1,209 statements (524 supports, 461 refutes, 224 not enough info) | 0 at freeze | yes (role B) | TABLE_TOOL_MEASURE_PLAN.md:19-23; config/semtabfacts_aux_val.json:24 |
| its table tool validation part | validation | table tool switch | 38 tables (18 articles) | runs partly done, stopped; no score read | yes | DECISIONS.md:8301-8303, 8383-8386 |
| its reserve | held for the not-enough-info fix and per-fix sets | none | 66 tables | 0 | yes | DECISIONS.md:8301; TABLE_TOOL_MEASURE_PLAN.md:62-65 |

## 4. Negotiation, real items

| Set | Kind | Serves | Items | Looks | Labelled | Source |
|---|---|---|---|---|---|---|
| Old pilot 6a8af3c7 | development since D-695 | advisor pilot | 24 items (18 INB headline, 6 LLM-Deliberation) | openings k=1, 2, 3; iteration-log looks 1 to 3 | yes | HELDOUT_OPENINGS.md:21-31; NEG_ITERATION_LOG.md:10-20; NEG_C4_MEASURE_PREP.md:11-12 |
| Final test, negotiation part | final test | full release | 32 items planned; 0 real items exist ("real items: none unused"); synthetic never in it | 0 | n/a | DECISIONS.md:7478, 7610; NEG_C4_MEASURE_PREP.md:11-15; NEG_FINAL_ITEMS_METHOD.md:26 |

## 5. Negotiation, synthetic items (config/neg_synth.json)

| Set | Kind | Items (target / drawn / built / kept after dedup) | Looks | Labelled | Source |
|---|---|---|---|---|---|
| dev_1 | development | 40 / 80 / 65 / 57 | R1 and R2 at least (counts not logged per look) | yes (relabelled, SYNLAB2) | neg_synth.json:114; NEG_C4_MEASURE_PREP.md:21; OPEN_ITEMS.md:1463 |
| pilot_1 | pilot, now development | 24 / 48 / 31 / 30 | R1 and R2 at least | yes | neg_synth.json:120; NEG_C4_MEASURE_PREP.md:22; OPEN_ITEMS.md:1463 |
| validation (D-798) | validation | 40 / 80 / 53 / 49; structures of the 53: three_or_more 51, two_singles 1, teams 1, one_vs_coalition 0 | 0 | no (not labelled or selected) | neg_synth.json:117; NEG_STRATIFIED_DRAW_REPORT.md:12-13; OPEN_ITEMS.md:1463 |
| validation_strata (top-up) | validation | 30 / 120 / 104 / not yet deduplicated; two_singles 37, teams 32, one_vs_coalition 35 | 0 | no | neg_synth.json:118-119; DECISIONS.md:8453-8454 |
| c4pilot_1 | C4 pilot, now development | 24 / 64 / 43 / 40 (label check kept 39 of 43) | 1 (NR_C4_PILOT) | yes | neg_synth.json:125-126; DECISIONS.md:8266, 8270, 8277; NEG_ITERATION_LOG.md:22, 24 |
| c4val_1 | C4 validation, now development | 40 / 120 / 95 / 73 (label check kept 92 of 95) | 1 (NR_C4_VAL_A and B) | yes | neg_synth.json:122-124; DECISIONS.md:8266, 8270, 8277; NEG_ITERATION_LOG.md:23-24 |
| r2val_1, r2pilot_1 | round 2 fix sets | 40 / 120 and 24 / 64; never drawn | 0 | n/a | neg_synth.json:127-131, 137 |
| dev_2, dev_3, pilot_2 | development, pilot | 40, 40, 24 targets; never drawn | 0 | n/a | neg_synth.json:115-116, 121; NEG_C4_MEASURE_PREP.md:25 |

## 6. Answers

### Q1. Test pools holding items never used or looked at

| Pool | Unused, unlooked items | Source |
|---|---|---|
| ContraDoc gate claim set (final test, both halves) | 230 documents (about 115 locked, about 115 reserved) | GATE_SET.md:289; DECISIONS.md:7474 |
| SciTab gate claim set (final test, both halves) | 363 claims, 61 tables (about 182 locked, about 181 reserved) | GATE_SET.md:289; DECISIONS.md:7474 |
| SciTab v3 sealed share | 30 tables | GATE_SET.md:50-59 |
| ContraDoc fresh set, after the 40-document trial | 60 documents (the trial's 40 are also unread until it runs) | DECISIONS.md:7474, 8349 |
| ContraDoc sealed kept groups left after BDRAW1 | 6 groups | DECISIONS.md:8135 |
| SciTab unused papers (no not-enough-info) | 14 papers | DECISIONS.md:8134 |
| SEM-TAB-FACTS reserve | 66 tables | DECISIONS.md:8301 |
| Negotiation final test (32) | 0 items exist | NEG_C4_MEASURE_PREP.md:11-15 |
| Not unused: the quick subset (5 steering looks), the old negotiation pilot (3 openings), every development set | | HELDOUT_OPENINGS.md:13-31 |

### Q2. Possible moves to validation (moved items never used for testing again)

Power figures are the records' own; no new power was computed. "Test shrink" is against the set the item leaves.

| Move | Gain | Test shrink | Power on record, now / after | Source |
|---|---|---|---|---|
| SEM-TAB-FACTS reserve to validation | 66 tables | none (already validation material, never a test) | none recorded | DECISIONS.md:8301; TABLE_TOOL_MEASURE_PLAN.md:35-37 |
| SciTab 14 unused papers to validation | 14 papers (2-class only) | none (not a test pool) | none recorded | DECISIONS.md:8134 |
| ContraDoc 6 leftover kept groups | 6 groups | none (held, not a test) | none recorded | DECISIONS.md:8135 |
| ContraDoc fresh set's 60 leftover documents | 60 documents, 60 groups (independent) | the "later, larger test" reserve 60 to 0 (100 percent of the reserve; the fresh set 100 to 40, 60 percent) | fresh test at 100: .80 at half A's effect, .40 to .47 at half B's; pilot of 50: about .27 | DECISIONS.md:2997, 7474, 7476 |
| ContraDoc claim set's reserved half | about 115 documents | 230 to about 115 (50 percent); the full-release test is locked at half | 230: .77 / .72 (interval, d .27 / .30, 10 points, 97.5 percent), 0.83 (alpha .05 two-sided); 115: about .54, smallest detectable at .8 about 13.6 points | GATE_SET.md:116-119; DECISIONS.md:7476 |
| SciTab claim set's reserved half | about 181 claims (the only large 3-class source with not-enough-info: 131 in the whole set) | 363 to about 182 (50 percent) | 352 drawn: .81 (3-class), .80 (2-class); 182: about .52, detectable at .8 about 13.9 points | GATE_SET.md:137-140, 292-294; DECISIONS.md:7476 |
| SciTab v3 share | 30 tables | v3 sealed evaluation 30 to 0 tables (100 percent) | none recorded; only Seckin may release | GATE_SET.md:57-59 |

### Q3. Negotiation items unused besides validation_strata

| Set | Unused items | By party structure | Source |
|---|---|---|---|
| validation (D-798) | 49 kept of 53 built (0 looks, not labelled) | of the 53: three_or_more 51, two_singles 1, teams 1, one_vs_coalition 0; per structure after dedup not recorded | NEG_STRATIFIED_DRAW_REPORT.md:12-13; OPEN_ITEMS.md:1463 |
| validation_strata (for reference) | 104 built | two_singles 37, teams 32, one_vs_coalition 35 | DECISIONS.md:8454 |
| dev_2, dev_3, pilot_2, r2val_1, r2pilot_1 | 0 built (declared, never drawn; 168 target items, 0 exist) | r2val_1 would be 10 per structure | neg_synth.json:115-131 |
| Real items | 0 unused | | NEG_C4_MEASURE_PREP.md:11-15 |
| Final test (32) | 0 built | | DECISIONS.md:7478 |

So D-843's "other unused items at hand" are the 49 kept items of the plain validation set, almost all three_or_more:
validation plus validation_strata give about 153 items before validation_strata's deduplication and the labelling
(DECISIONS.md:8457, 8463).

## 7. Recommendation

The free moves come first, because no test set gets smaller: the SEM-TAB-FACTS reserve (66 tables, the best source of
not-enough-info material), the 14 unused SciTab papers, the 6 leftover ContraDoc groups and, for negotiation, the 49
kept validation items beside validation_strata. One move with a real cost is worth asking Seckin about: the fresh set's
60 documents left after the 40-document trial. They gain 60 independent ContraDoc documents. They cost only D-692's
"reserved for a later, larger test", and that reserve was already too small to carry a test (D-316 gives .40 to .47 at
100 on the out-of-sample effect). This changes D-692 item 1, so it needs his word. Do not move anything from either
gate claim set. ContraDoc's power is about .54 at the locked half and .77 to .83 only at the full 230, and SciTab's
about .52 at about 182 and .81 at 363. Taking the reserved halves would lock the full release's final test at the
half size, where neither benchmark has the planned power. If anything, the full-release test should go back to the
whole claim sets. The SciTab v3 share stays sealed (Seckin's alone). The negotiation final test has no items, so
nothing can move from it.

## Moves to validation (D-848, Seckin 20 November 2026 14:46, option (a))

Recorded 14:50 +0300 by the lead. A moved item is never used for testing again. No final test set is touched.

| Moved | Items | From | Now |
|---|---|---|---|
| SEM-TAB-FACTS reserve | 66 tables | unread reserve | validation |
| SciTab unused papers (no not-enough-info claim) | 14 papers | held | validation |
| ContraDoc leftover kept groups | 6 groups | held | validation |
| Negotiation `validation` set | 49 items | unused synthetic validation | validation (joins validation_strata for D-843's parts) |
| ContraDoc fresh set left after the 40-document trial | 60 documents | D-692 reserve for a later, larger test | validation; the reserve is let go |
