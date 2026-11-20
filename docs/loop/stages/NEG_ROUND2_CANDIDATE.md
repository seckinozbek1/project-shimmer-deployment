# Negotiation round 2 candidate: R2, the limit read (D-814 round 2)

Written 2026-11-19 by lane/neg-round2-candidate (branch from lead/night-20261119 at 33dacb02). Label-free: only
the system's own saved step records and prompts, the code and the stage reports were read. No answer key, no gold
label, no role folder, nothing under benchmark/keys. No model was run on the laptop, nothing was launched, sealed
or spent, nothing was tuned on any set.

## 1. Cause addressed

D-814 allows three measurement rounds toward the conflict-class F1 floor of 0.60 (D-712). Round 1 is C4
(`conflict_question: compare`, check 651), which changes the question of the stance step. The C4 report names two
causes for "no conflict ever composed" (NEG_CONFLICT_FIX_REPORT.md section 1.2):

1. the stance question itself (fixed by C4);
2. conflict has one route only. The second route, a crossed red line (`neg_advisor.py` red_line step), is asked only
   of persona positions the build marks red lines, and no item marks one. Open item 163 (a) left this to the item
   build.

R2 addresses cause 2 from the model side, without waiting for the build. Counts by form from the saved system-side
records (scratch copies of the two pilots' evidence archives, scripts run with `py -3.12 -I`, no text printed):

| | improved (NR1118_IMPROVED_PILOT) | M-step (NR1118_MSTEP_PILOT) |
|---|---|---|
| step records | 2,696 | 456 |
| stance choice decisions | 1,306 | 147 |
| yes/no decisions | 358 (= one open point per proposal per arm, 2 x 179) | 44 |
| red-line steps asked | 0 | 0 |
| persona positions / marked red lines | 85 / 0 | 85 / 0 |
| proposals with a persona position on them | 73 of 179 | 73 of 179 |

So on every proposal where a conflict is possible (73 of 179), the stance step alone decided it, and it never said
oppose. C4 may fix that step; it cannot add a route. If C4's against answer is rare or misplaced, the conflict
class still rests on one question. R2 is independent of C4: it reads the persona's position alone, never the
proposal's text, so a misreading of the proposal-against-position comparison does not carry into it.

Other candidates considered and not chosen for round 2: a P3 threshold on the compare margin (already built, check
532; a threshold, not a route, and it needs a development split of the round-1 data, so it fits round 3); P5's
second-family auditor (built, check 542, but it flips only inside a margin band of the same stance step, so it is
not independent of it); a fate forecast (P2, check 539; it never writes the conflict field).

## 2. Design

Switch `advice.methods.stepwise.limit_read` in `benchmark/baselines/neg_advisor_prompt.json`, false as shipped,
read by `neg_advisor.optional_switches` when the chain runs.

- Read (step `limit_read`, CHOICE-A): once per item, before any proposal, each persona position not marked a red
  line is asked the `limit` template: the party, the round the position was put on record in and its quote, and
  "Does this position state a firm line, something the party says it must have or will not accept whatever is
  proposed, or a wish it could trade or give up in the negotiation? Answer with exactly one of: firm, wish." The
  template may not show `{proposal}`, `{proposal_id}`, `{article}`, `{title}` or `{changes}`.
- Answers: `limit_answers`, each a label named in the template and `limit` true or false, exactly one true,
  declared before any read, never from labels (firm true, wish false). Both labels' first tokens on the producer's
  tokenizer are whole words (firm 8802, wish 81099).
- Crossing (step `limit_cross`, yes or no): each proposal a position read as a limit applies to (by the mapping's
  own `_applicable`) is asked the `limit_cross` template: the proposal with its round, the line with its round, "If
  the proposal were adopted as written, would it go past this line?". No `{changes}`, so it works under both orders.
- Composition (Python): conflict when any persona stance is oppose, a marked red line is crossed, or a read limit
  is crossed. The piece keeps `limit_hit` and `limit_lines` marked `limit_basis: inferred` (D-711: a model reading,
  never on record), apart from the declared `red_line_hit`; the reply keeps every read in `limit_reads` with its
  probabilities. Stance follows as before (reject on conflict unless the open point is yes).
- Precedence: a marked red line from the build is the first source; it is asked by the declared red_line step as
  before and never read again.
- Refusals: a refused read is no limit, a refused crossing no crossing; each counted with its reason, neither
  ending a chain. Malformed config is refused at load: a non-boolean switch, fewer than two answers, two or no
  answers counting as a limit, a non-boolean `limit`, a label that is yes, no, a declared stance or not lower case,
  a read template showing a proposal, missing a slot or not naming a label, a crossing template missing the quote
  or showing `{changes}`.
- Composes with `conflict_question` stance, two_checks or compare (C4), both orders and both stance contexts.
- P3 (`tools/score_neg_advisor.margin_conflict_reply`) now holds a crossed limit's conflict whatever the margin,
  as it does for a marked red line.
- Replay: the reads and crossings are ordinary step records, so `recompose_stepwise` rebuilds the reply from saved
  records with no model.
- WORDS-A: no keyword table, no cue word; the meaning decision is the model's, Python only checks the label and
  composes.

Touched: `benchmark/baselines/neg_advisor.py`, `benchmark/baselines/neg_advisor_prompt.json`,
`tools/score_neg_advisor.py` (P3 line), `tools/neg_round2_checks.py` (new), `scripts/verify_session1.py` (check
652), `docs/CLAUDE_REFERENCE.md`, `docs/fix/OPEN_ITEMS.md` (item 163 update), `NEG_ITERATION_LOG.md`. No
controller-bound file is touched. The workload code travels in each bundle's source tree: a run under R2 needs its
own prompts build (`neg_advisor.py build --config <copy with limit_read true>`) and its own seal; old prompts files
(the key absent or false) replay byte for byte as before.

## 3. Proof results

```
py -3.12 -X utf8 tools/neg_round2_checks.py
652 PASS 8 proofs, 2 neutralisations, fail, restore, pass, no model: ...
py -3.12 -X utf8 scripts/verify_session1.py --checks 356,450,466,467,468,490,491,492,493,494,515,516,518,531,532,533,535,539,540,541,542,543,651,652
PASS=24  WARN=0  SKIP=0  FAIL/ERROR=0  TOTAL=24
```

Check 652 (`tools/neg_round2_checks.py`, fixture item of `tools/neg_advisor_checks.py`, scripted model):

1. cascade_closed: the runs' shape (stance never oppose, no red line marked) with limit_read on: the two persona
   positions are read first, once each, the read showing no proposal text; the one read firm is asked
   limit_cross on P-A2-1 only; yes makes P-A2-1 conflict / reject with `limit_hit` true, `limit_lines` [POS-2],
   `limit_basis` inferred and no `red_line_hit`.
2. no_crossing: firm reads crossed no, and all reads wish, give no conflict; a wish is never asked limit_cross.
3. declared_kept: with POS-2 marked a red line, it is asked by the red_line step and not read; only POS-1 is read.
4. with_c4: under compare, in generated_first and choice_first: a conflict through the limit route with every
   compare answer aside, and through the compare route with every read wish; compare asked of all 6 positions.
5. refused_read: an undeclared read answer is refused (not_declared), the position is no limit, the chain goes on
   (3 open points asked).
6. replay: R2 and C4 together composed again from saved records by `recompose_stepwise`, the same reply.
7. p3_holds: at a 0.5 threshold with all margins negative, P3 keeps P-A2-1 a conflict.
8. refusals: 13 malformed configs (each form listed in section 2) refused; shipped off; off and not declared ask and compose exactly as
   before.

Neutralised (the crossing not counted in the chain's composition): proofs 1, 4 and 6 fail. Neutralised (P3 not
reading `limit_hit`): proof 7 fails. Restored: all pass. The whole gate was not run (lane rule).

## 4. Cost forecast for its measurement

`tools/loop/step_cost.py` on step files in the C4 form, A10 at 1.29 USD an hour from the provider inventory of
NIGHT_neg_improved (observed 2026-11-18), boot 6, install 6, return 3, upload 64 minutes, asset copy MATCH. The
workload is C4's (98, 163, 82 minutes for 24, 40, 20 items) plus R2's extra choice steps: from the improved run's
measured rows a choice step takes 0.28 to 0.32 s (a generated step 7.9 to 17.2 s); per item at most 3.5 reads and
6.6 crossings (85 persona positions and 158 position-proposal pairs over 24 items, every position read as a
limit), so at most 3.2 s an item, rounded up to 2, 3 and 2 minutes.

| Step | Workload | Without measures | With measures |
|---|---|---|---|
| neg.r2_pilot (24 items) | 100 min | 5.00 USD (above the line by rounding) | 3.21 USD |
| neg.r2_validation (40 items, one launch) | 166 min | 6.85 USD | 5.06 USD (above 5 USD) |
| neg.r2_validation as two launches of 20 | 84 min each | 4.56 USD each | 2.77 USD each |

Use the asset copy and the two-launch split: 3.21 + 2 x 2.77 = 8.75 USD with measures, each step within the 5 USD
pre-approval (D-708), against C4's 8.58 USD. Seals and role V labelling are separate steps with their own
forecasts, as for C4.

## 5. How it combines with C4's outcome

Sets: R2 is measured on its own fresh sets (D-789), built and frozen before any R2 run, sizes as C4's (24 pilot,
40 validation), not overlapping C4's sets or any earlier set. Before any read the look is logged in
NEG_ITERATION_LOG.md with the figures named: M1, M1m, conflict-class F1 (floor 0.60), N1, M5, M4 and M10 beside
them, and, system-side, the count of conflicts by route (stance or compare only, limit only, both), from the
pieces' `limit_hit` and `position_stances`, so a gain is attributed to a route without a second arm (FACTORS-A).
A pilot stop rule declared now: if the read gives one answer to every position (all firm or all wish), or the
crossing answers yes on every pair, the validation launches are not made (a constant read is no route).
Role N can also report, key side, the read's agreement with role V's per-position `red_line` field where a set
carries it, as a development figure beside the bar, never inside it.

- C4 meets the floor on both record kinds: no round 2 is needed for the bar; R2 stays off and goes to the v1.1
  ablations as a measured-later switch.
- C4 holds partly (against occurs and conflict F1 rises, but stays under 0.60):
  - recall short (conflicts missed, few false ones): round 2 is C4 plus R2 (`conflict_question: compare`,
    `limit_read: true`). R2 adds conflicts, never removes one, so it is aimed at recall.
  - precision short (many false conflicts): R2 would make precision worse. Round 2 is then the P3 threshold on the
    compare margin (built, check 532), tuned on a development split of C4's data only, and R2 moves to round 3 on
    top of whatever round 2 keeps.
- C4 does nothing (against never top, or the conflict class unchanged): round 2 is R2 alone with the shipped
  stance question (`conflict_question: stance`, `limit_read: true`), so the round tests the second route on its
  own and its figure is not mixed with a question that did not move.

After three rounds without the floor, D-814's SORU follows; R2's figures go into it whichever way they fall.
