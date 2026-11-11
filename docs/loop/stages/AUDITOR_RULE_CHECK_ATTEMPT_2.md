# Auditor rule check, attempt 2: the lesson of attempt 1 and the recipe (D-S71, D-S72)

Part `auditor_rule_check`, under docs/loop/stages/AUDITOR_RULE_CHECK_SUCCESS.md, which is unchanged:
the same questions file (9dbd82f2), halves, margin .05 on A and B, the half-B lower bound above 0 at
0.05 / 2^k, and the not_met precision floor. Written on lane/auditor, 2026-11-09, after attempt 1's
half-A read (fdc0eb0c) and before attempt 2's. Half B is unopened.

## The lesson of attempt 1 (for docs/loop/LESSONS.md)

- **Tried.** LoRA on Phi (local_auditor), the rule-check choice form, `dev_mix` and
  `permissive_mix` (12,000 balanced NLI rows each: MultiNLI, WANLI, TabFact), checkpoints at .5 and
  1 (AUD_TRAIN5, 750 and 737 updates). Decisions were the argmax of the three answer probabilities.
- **Result.** On half A (398 questions, 31 documents), the untrained form scored .541 and the best
  arm, `permissive_mix@trained_half`, scored .588. The margin was .047 against .05: a fail, with the
  progress minimum met.
- **Why, from the saved records.**
  - Per class on half A, training doubled the No class: not_met F1 went from .42 to .62 and .65,
    and its precision from .41 to .70 and .76.
  - It lost the Yes class into Unclear. met recall went from .37 to .26 and .32. The trained arms
    answer Unclear on 273 to 285 of 398 questions, where the gold has 158 Unclear. Between 89 and
    100 met questions went to Unclear, against 56 for the untrained form.
  - The half/full curve is flat on half A (.558 against .572, and .588 against .579). The
    in-distribution held-out accuracy also rose only 1.5 points after the midpoint (.744 to .760,
    .762 to .776). Size is not the lever.
  - The data mix is not the lever either: the two mixes differ by .02 or less on every figure.
  - The training rows are balanced by answer and short (215 tokens on average). A ContractNLI part is
    a long contract section with a different answer prior. The trained model's probabilities rank
    the answers better, but its argmax carries the training prior.
  - Exploratory on half A only: with a per-label offset on log probability, fitted by document
    2-fold cross-validation within A (20 repetitions), the untrained form scores .573 and the trained
    arms .655 to .688. The best arm's margin over the untrained form is .115, at or above .05 in 95
    percent of splits.
  - So the loss is calibration of the decision. It is not the base's ceiling, the size or the mix.
- **Next changed (attempt 2).** The decision rule only. No new training, and no new run on a model.

## Attempt 2's recipe (fixed here, before its read)

1. The decisions are attempt 1's own, unchanged: AUD_TRAIN5's six decisions.jsonl files, with
   digests as in docs/loop/stages/AUDITOR_RULE_CHECK_HALF_A_1.json.
2. Each arm, the untrained form included, decides by the argmax of log probability plus a per-label
   offset (met 0; not_met and cannot be settled on the grid -3 to 3 in steps of .25).
3. The offset pair for an arm is the one with the highest macro-F1 on that arm's own half-A rows. A
   tie goes to the smallest total offset, then the lower not_met offset, then the lower cannot
   offset (`auditor_read.fit_offsets`).
4. Selection, the margin and the not_met thresholds are as in the success rule, on the calibrated
   half-A decisions.
5. The offsets are frozen in the half-A record. read-b applies them to half B unrefitted, the
   untrained form's to the untrained form (`auditor_read.read_b`).
6. The read: `auditor_read.py read-a --session-out <AUD_TRAIN5 evidence/b1/auditor_train>
   --questions external/train_auditor/questions/rule_check_dev.json --attempt 2 --calibration
   prior_offset --out docs/loop/stages/AUDITOR_RULE_CHECK_HALF_A_2.json`.

Proofs are in check 333: the offsets are fitted on half A, frozen and applied to half B. Two
neutralisations: the offsets never applied, and half B refitted.

Stated limit: the offsets were explored on half A before this recipe was written. Attempt 2's own
half-A margin is therefore an in-sample figure, with .115 the cross-validated estimate. The test that
carries the claim is half B: gain at least .05, and the bootstrap lower bound above 0 at 0.025 for k 1.

## Cost and time

No instance, no seal and no launch. The read takes seconds on this laptop, so it ends well before the
configuration freezes on the morning of 10 November. If it passes, half B is read after the committed
opening row, in seconds too.
