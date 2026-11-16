# The negotiation bar (D-709, standing order 102)

Written 16 November 2026, before any new scoring. Set by the operator (Seckin 20:23, floor corrected to 0.60 at 20:25) on the lead's draft. The bar may be
raised over rounds, never lowered. No later stage (final test, v1.0 release, ablations) starts before it is met.

Measured on the VALIDATION set, with the power record simulated again for its item counts. All of these at once:

1. **M1** (conflict Macro-F1) at least **0.60**, and the lower end of its 95 percent item-cluster interval above chance (0.33 for three classes).
2. **M10** (open-point detection, AM-3) at least **0.60**.
3. **M4** (stance matches fate) at least **0.60**.
4. **M7** (approach) recall at least **0.80** and precision at least **0.70**.
5. **M8** (Python field checks) **1.0**, and at most **10 percent** of answers dropped (ANSWER-FORM-A drop counts).

Every other figure is reported beside these (M2, M3, M5, M6, G1 to G4, red lines, M9 labelled not validated).
Each change is made and judged on development items; the validation set is read only to test a round against this
bar; each pilot is opened once and then joins development; the final test set is never seen. Every look and every
change tried is logged in docs/loop/stages/NEG_ITERATION_LOG.md.

## How many sets each decision needs (D-710, Seckin 20:27)
- **Adopting a change:** judged on at least two development sets; adopted only when it does not lower the bar figures on any of them beyond its interval and raises them on at least one, and the change and every set it was looked at on are logged first.
- **Passing the bar:** read on the validation set only (one look per round, logged), after the change was adopted on the development sets.
- **Confirming:** at least one pilot, opened once, then joined to development; a second pilot confirms before the final test is opened.
- The final test set is never seen until all of the above hold.

## Both record kinds (16 November 2026, recording D-711 item 3, Seckin 20:40)
This section records the operator's decision D-711 item 3; it adds no rule of the lane's.
- Every set (development, validation, each pilot) holds complete-record items and missing-notes items. A
  masked-party item (one party's column or notes hidden, the hidden text the key) counts as missing notes.
  The set builder declares each item's `record_kind` (`complete` or `missing_notes`) and, for a masked-party
  item, the `masked_party`.
- Every line of the bar is read on each kind apart and must pass on both. `tools/score_neg_advisor.py` reports
  every bar figure per kind (`by_record_kind`) and refuses a bar reading for a set without both kinds, or
  with any item of undeclared kind (`neg_bar`). The pilot set of 24 items declares no kind, so no bar
  reading is possible on it.

## The class that matters (16 November 2026, recording D-712, Seckin 20:49)
This section records the operator's decision D-712; it adds no rule of the lane's. Round 1 showed M1 can pass
0.60 without one conflict found. Each figure below that averages over classes, or that a constant answer
could pass, gets a floor of at least 0.60 on its class that matters. The floor sits on the line of its
figure, and a line whose figures pass but whose floor is missed is not met. The scorer reports every floor
(`by_record_kind` floors, `neg_bar` floors_missed).

| Figure | In the bar | Its floor (at least 0.60) |
|---|---|---|
| M1 (conflict Macro-F1) | line 1 | F1 of the `conflict` class |
| M1m (M1 on proposals with a persona position) | line 1 | F1 of the `conflict` class |
| M1s (M1 on proposals with none) | no, diagnostic | none: its one class, `not_stated`, is decided by structure |
| M2 (alignment Macro-F1) | no, reported | not a bar figure; its per-class rows are in the report |
| M3 (article state Macro-F1) | no, reported | not a bar figure; its per-class rows are in the report |
| M4 (stance matches fate) | line 3 | the hit rate within each fate the key holds: `kept`, `changed`, `removed` (a constant stance cannot pass) |
| M5 (stance consistent with conflict) | no, reported | not a bar figure |
| M6 (counter wording closer to the next round) | no, reported | not a bar figure; one class |
| M7 (approach) | line 4 | recall at least 0.80 and precision at least 0.70 already floor both sides |
| M8 (Python field checks) | line 5 | none needed: 1.0 is required, with the drop share at most 10 percent |
| M9 (judge's wording grade) | no, not validated | not a bar figure |
| M10 (open-point detection) | line 2 | F1 of the `movable` class |

## Party structure (16 November 2026, recording the operator's instruction of 20:32)
This section records Seckin's instruction of 16 November 2026 20:32 (relayed through SUPERVISOR_INBOX); it adds
no rule of the lane's.
- Every negotiation item is tagged by its party structure: `two_singles` (two single parties), `teams` (two
  coalitions, teams of several), `one_vs_coalition` (one party against a coalition), `three_or_more` (three or
  more parties). The set builder declares the parties and their kinds; the tag is computed in Python from them
  (`structure_of` in tools/score_neg_advisor.py), never read from words. A declared tag that differs is refused.
- Every set (development, validation, each pilot) holds several structures.
- The scorer reports every bar figure and every class floor of D-712 per structure as well as overall
  (`by_structure`, and each line per structure in `neg_bar` `structures`), so a weakness in multi-party or
  coalition cases cannot hide, and it refuses a bar reading for a set whose headline items hold one structure
  only. The pass itself is read on both record kinds as above; whether every line must also pass on each
  structure is the operator's to decide and is not assumed here.
- The pilot set of 24 items declares no record kind, so no bar reading is possible on it either way; its
  structures are read from its items' parties when it is scored.

## The bar in each party structure (16 November 2026, recording D-715 item 1, Seckin 22:31)
This section records the operator's decision D-715 item 1; it adds no rule of the lane's. It settles the open
question of the section above: the bar must pass in each party structure separately as well as overall.
- The bar is met only when every line and every class floor holds on both record kinds (D-711), on every
  party structure the set holds, and overall (all headline items pooled). A structure, or overall, that
  misses one line or floor fails the bar; `tools/score_neg_advisor.py` names it (`neg_bar` `structures_failing`).
- Every set holds enough items of each structure: at least `MIN_ITEMS_PER_STRUCTURE` headline items of each
  structure it holds, declared once in tools/score_neg_advisor.py and equal to `MIN_CELL` (5). The reason: a
  reporting cell of fewer than five items gives its count alone, with no figure and no interval (plan section
  6), so a structure with fewer items could never meet a line and its pass could not be read. A set below it,
  or holding one structure only, gets no bar reading. Role N and role S are told (D-715 item 1).
