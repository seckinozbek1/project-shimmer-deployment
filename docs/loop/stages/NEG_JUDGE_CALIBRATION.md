# The negotiation advisor judge: calibration, or a replacement, until kappa reaches the floor (D-656 item 1; lane contradoc-d652, 16 November 2026)

Plan and tooling only; nothing here has run on a model. 0 USD spent.

## 1. The floor and where the judge stands

- **The floor.** Cohen's kappa 0.60 between the checker's grades and the judge's, on the checker's sample:
  NEG_ADVISOR_PLAN section 6.3 (below 0.60, M9 is reported "not validated") and the bar's line 4; in code
  `tools/score_neg_advisor.KAPPA_FLOOR`, read with AM-1's single-class rule (`agreement`, `at_bar`).
- **Now.** kappa 0.0 on 10 entries (D-653, unchanged at the k=2 re-score, D-695): the judge (Phi-4) graded every
  counter 2; the checker gave 0 seven times and 1 three times, never 2. Raw agreement 0 of 10. With the judge's
  column constant this is a measured disagreement, not a parse fault. M9 is not validated.

## 2. Why calibration can work now, and why a temperature cannot

Since 4e33a1d2 (D-672) the judge decides by fixed choices: one forward pass, the probability of each grade
(CHOICE-A), saved on the reply record. The pilot's grades were free generations; the new decisions carry the
probabilities a calibration needs. A temperature (the trained ContraDoc judge's calibration,
`benchmark/baselines/judge_calibration.py`) never changes which grade is on top, so it cannot move a judge
that always says 2. The smallest change that can is a per-grade offset on the log probabilities (a prior shift):
grade g wins when log p_g + b_g is highest, b_2 fixed at 0.

## 3. The calibration step (built: `tools/neg_judge_calibration.py`, check 486)

1. `rows`: the judge's decisions of a pass folder (entry, item and the three probabilities; no text).
2. `fit`: offsets b_0 and b_1 on a grid from -8 to 8 in steps of 0.25, chosen to maximise the scorer's own kappa,
   a tie going to the smaller total offset. Judged **leaving one item out**: each item's entries are graded by
   offsets fitted on the other items only; the out-of-fold kappa is the figure, with a 95 percent percentile
   interval from 2,000 seeded resamples of items. In-sample kappa is written beside it and never decides.
3. **At the floor** only when the out-of-fold kappa is at or above 0.60 (AM-1 rule) on at least 30 entries from at
   least 6 items; fewer reads `too_few_entries`. The offsets fitted on all entries are then applied at score time.
4. **Refusals.** `--exclude-items` is required: any decision or checker entry of a listed item stops the fit
   (D-656: "neither the pilot's 24 items nor their replies are used to calibrate it"). A checker entry graded
   twice, or a decision without the three grades, stops it too.
5. `compare`: several judges' decisions on the same entries, each read the same way, for the replacement route.

## 4. A conflict to rule on

D-656 forbids calibrating the judge on the pilot's items or replies. D-671 and D-695 later moved the pilot's items
into development, and D-710 opened them a third time for M10. The lane keeps D-656's narrower rule: the pilot's
24 item ids go into `--exclude-items`. The lead or Seckin may lift it by a decision; the tool then takes an empty
list. Recommendation: keep the exclusion, since the pilot's 10 graded entries are the only judge record M9's
"not validated" rests on, and calibrating on them would grade the judge on its own fitting data.

## 5. The measurement (development entries only)

- **Entries.** The judge grades the system's counters. At least 30 counters from at least 6 development items
  that are not the pilot's: role N's development sets (the 6-item list, track A's development part, the
  synthetic development set of D-707, each marked synthetic and reported apart). About 2.5 counters an item on
  the pilot (12 graded counters on 18 items for the cloud, fewer for the system) means 12 or more items.
- **The checker.** A fresh Claude agent of role N grades every one of those counters by the plan's rubric, blind
  (as session 19 did): Claude usage only, 0 USD on Lambda.
- **The judge's pass.** The judge group as choice decisions under the re-sealed configuration (4e33a1d2), on the
  counters the system's after pass writes.
- **Round 1:** `fit` with offsets. **If below the floor, round 2: a replacement**, read by `compare` on the same
  entries. Candidates, local only (D-671: no cloud model until after v1.1) and never of the graded arms' families
  (plan 6.3's family limit: Qwen writes the advice, Phi-3.5 audits it): a local model of a third family whose
  licence allows it, as a new checkpoint archive. Plan 6.3 allows a non-Phi judge "for a later opening only":
  the replacement applies to development and later sets, never inside an opened score.
- **If neither reaches 0.60,** M9 stays "not validated" and is reported so; no figure rests on the judge.

## 6. Cost, two ways

| Step | Without the saving measures | With them |
|---|---|---|
| Round 1 judge pass (counters of 12 items) | own instance: setup 15 min, the system's advice for 12 items to make counters (16 min free, 33 under the constraint), the judge load and 30 single-pass decisions (4 min): about 52 min, **1.46 USD** at 1.68 USD an hour (A10 1.29 times 1.3), **3.25 USD** if the asset copy reads MISSING | rides on the output side's after pass (PARSE_SWEEP_DEV_MEASUREMENT.md), which already writes those counters and loads the judge: the 30 decisions add about 1 minute, **about 0.03 USD** |
| Round 2, one replacement candidate | own instance: setup, the new checkpoint's transfer (about 10 min for an 8 GB archive) and load, 30 decisions: about 30 min, **0.84 USD**, plus building and verifying the archive once | in the same session as round 1 when the candidate is chosen before it: load and 30 decisions, about 4 min, **0.11 USD**, plus the archive |
| The checker | Claude usage only | Claude usage only |

The saving measures: the judge decisions ride on a pass that runs anyway; the replacement is chosen before the
session so it shares the setup; the asset copy is reused (MATCH). Every figure is under the 5 USD per-step
pre-approval (D-708).

## 7. Before it can run

The re-seal on Lambda carrying 4e33a1d2 (the output side's precondition, D-674 item 4); role N's development
items and the checker's sheet over all their counters; the pilot's 24 item ids as the exclusion file.
