# The stratified synthetic draw by party structure (lane neg-stratified-draw)

19 November 2026, 18:46 +0300 onward, branch `lane/neg-stratified-draw` from `lead/night-20261119` (c6b58904).
Code and fixtures only: no item generated, no model called, nothing spent, no role session started.
Rules: D-711 items 2 and 3, D-715 item 1, the party-structure instruction of 16 November 20:32, D-732,
NEG-SYNTH-A, NEG-STRUCTURE-A.

## 1. Why

D-715 item 1 reads the negotiation bar per party structure, and the scorer refuses a structure with fewer than
`MIN_ITEMS_PER_STRUCTURE` (5) items. Role S session 3 drew the validation set from the plain distributions
(parties {2: 0.20, 3: 0.35, 4: 0.30, 5: 0.15}, coalition_share 0.30): 53 accepted, 51 three_or_more,
1 two_singles, 1 teams, 0 one_vs_coalition. The stratified-draw lane D-732 approved had not started.

The sampler alone, on 1,500 fixture seeds, gives three_or_more 79 percent, two_singles 10, one_vs_coalition 8,
teams 2.5, no seed refused, and fixture replies pass the validator in every structure (400 seeds, 0 rejected).
Session 3's 2 two-party items of 53 is far below the roughly 11 the sampler gives, so something on role S's side
(generation, regeneration or the order the briefs were worked in) drops two-party items. Not visible from the
lead's side; the S4 request asks for accepted and rejected counts per structure to find it.

## 2. What was built

- `config/neg_synth.json`: a set may declare `strata` {structure: count}; `split.strata_rule` states the rule.
  The new set `validation_strata`: purpose validation, `tops_up: validation`, offset 11000, 120 seeds drawn,
  10 kept each of two_singles, teams and one_vs_coalition (target 30). Its range overlaps no other set.
- `tools/neg_synth.py`:
  - `check_strata` (called by `check_split`): structures only from `score_neg_advisor.STRUCTURES`, each count at
    least 1, target equal to their sum, at least two seeds drawn per kept item in each stratum. A top-up names a
    declared plain set of the same purpose and always declares strata. A top-up is not counted as a set of its
    own, so there is still exactly one validation set.
  - `stratum_of`: (seed // 2) modulo the number of strata, in the scorer's order. The record kind stays
    seed modulo 2 (D-711), so the two are crossed: every stratum holds about half of each kind.
  - `party_kinds` / `draw_structure(seed, cfg, structure)`: two_singles, teams and one_vs_coalition fix the two
    parties' kinds (one_vs_coalition in a drawn order). three_or_more draws the number from `parties`
    restricted to 3 or more, and each kind from `coalition_share`. With no stratum the draw is byte for byte
    the former one.
  - `sample_card(..., stratum=)` records `stratum` and refuses parties of another structure. `draw` reads the
    stratum from the set name.
  - `select_strata`: per structure, the first `count` built items in seed order that no screen dropped. A
    structure never borrows from another, and `short_by_structure` names each shortfall. `select` uses it for a
    stratified set.
  - `coverage` counts `structure`, and with `--set` refuses a stratum below its count. `set-check` prints the
    built items by structure and record kind (counts only), so role S reports per structure without opening a
    card.
- The seed scheme is unchanged: base + offset + i over the set's own range, from the same seed base.

## 3. Proof

Check 644 (`tools/neg_stratified_draw_checks.py`) has five proofs, each one neutralised, failed, restored and
passed:
- each stratified card is of its seed's stratum, the strata are drawn equally, and both kinds are in each;
- a plain set follows the former party rule and records no stratum;
- `select_strata` keeps each structure's count in seed order, honours drops and names the shortfall;
- the split refuses eight malformed declarations and keeps exactly one plain validation set;
- the CLI: `draw` and `coverage --set validation_strata`, then `set-check` on fixture builds, prints counts only.

Run alone, with no whole gate: 644 together with 455 to 459, 472 to 474, 504, 510, 520, 522 to 524, 22 and 174,
all PASS. A fixture draw of all 120 `validation_strata` seeds gave 40 cards of each structure, 60 of each kind,
no seed refused and no fixture-reply rejection.

## 4. Role S handoff (not started)

- Commits 7303ad85 (the draw) and 34d7bfea (the per-structure set-check line).
- Bundle `_xfer\lead_to_S\S4_code.bundle`, prerequisite 0e822027, head 34d7bfea283975aae3d64831b5ce17b112da6dc0,
  2,899,527 bytes, SHA-256 11fe07d3c6187e8c905a7e60118e2a9ca75f2d8414b90470fdb2c544ad4476af,
  `git bundle verify` ok.
- `_xfer\lead_to_S\REQUEST_ROLE_S_S4.md`: role S fetches the bundle into its checkout, checks out 34d7bfea, and
  runs draw, coverage, generate and assemble, set-check and the hand-on to B and V. It reports per-structure
  counts in `S4_DONE.json` and stops before `select`. CODE_COMMIT.txt is not changed; the request states the
  fetch, and the lead updates the file.
- `docs/loop/private/role_starts/start_s4.cmd`: copied from start_s3.cmd by exact replacements (S3 to S4 names,
  the comment line, plus one guard that the bundle exists), LF kept. `role_start_check`: PASS, 10 commands, all
  ALLOWED.
- The lead's part: add start_s4 to role_starter's allow-list (D-793), and merge the lane.

## 5. Open

- Check number 644 was the next free number on this branch. A parallel lane taking 644 needs a renumber at merge.
- The S3 request could not be read (the command guard allows writes only in `_xfer\lead_to_S`). S4 was written
  from the pipeline doc, and it names folders as "the ones session 3 used for validation".
- When the bar is read, role N joins `validation_strata` with `validation` as one validation set, per its
  `tops_up`. The scorer's freeze reads set folders; joining the two at the freeze is role N's step and is not
  built here.
- After the top-up, the validation set holds 11, 11 and 10 two-party items before the screens. That is enough
  for 5 per structure unless the screens drop more than half.
