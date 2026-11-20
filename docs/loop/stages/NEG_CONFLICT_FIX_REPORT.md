# Negotiation conflict fix (D-806, after D-788 and D-796)

Written 2026-11-19 by lane/neg-conflict-fix (branch from lead/night-20261119 at c6b58904). Label-free: only the
system's own saved replies, the prompts files and the code were read. No answer key, no gold label, no role
folder, nothing under benchmark/keys. No model was run on the laptop, nothing was launched, nothing was tuned.

## 1. Why "oppose" is never chosen

### 1.1 Evidence read

The pilots' evidence archives, each extracted whole into a fresh scratch folder
(`<USER_HOME>\AppData\Local\Temp\claude\98615fb4d64ceccf\8fee59db-05ba-4f74-b566-421805410a26\scratchpad`,
folders `ev_mstep_run`, `ev_improved_run`; the counting scripts in a separate `tools` folder there, run with
`py -3.12 -I`):

- M-step: `external/s05/NIGHT_neg_mstep/run_mstep/NR1118_MSTEP_PILOT/collected_evidence.tar.gz`,
  `evidence/b1/mstep/stepwise_steps/audit/model_replies` (388 step records).
- improved: `external/s05/NIGHT_neg_improved/run_improved/NR1118_IMPROVED_PILOT/collected_evidence.tar.gz`,
  `evidence/b1/improved/stepwise_steps/audit/model_replies` (2,296 step records), the same tree S42b hands to
  role N (D-794).
- The prompts each run carried: the archive's own `replay_prompts.json`.

Counts by form (every choice record carries its decision: answers, renormalised probabilities, token ids,
`declared_mass`, `undeclared_top`):

| | M-step | improved (both arms) |
|---|---|---|
| stance decisions (answers support, oppose, accept) | 147 | 1,306 |
| top answer accept / support / oppose | 92 / 55 / 0 | 888 / 418 / 0 |
| largest renormalised p(oppose) | 0.034 | 0.022 |
| median p(oppose) | 1.5e-07 | 2.1e-07 |
| declared mass, min / median | 0.891 / 0.989 | 0.926 / 0.993 |
| undeclared top token | `Support` 137, `Accept` 10 | `Support` 1,156, `Accept` 150 |

Item structure of the improved prompts (24 items, 179 proposals): 85 persona positions and 269 other parties'
positions, every one of them article-level (proposal null); 20 articles hold several proposals; persona red
lines declared: 0. Of the 85 persona positions, 73 were put on record in an earlier round than the item's
(most in round 0) and 12 in the item's own round.

### 1.2 Each candidate cause, tested

| Candidate | Finding | Verdict |
|---|---|---|
| The answer set offered | `STEP_ANSWERS["stance"]` is `POSITION_STANCES` (support, oppose, accept), `benchmark/baselines/neg_advisor.py:1168`; every one of the 1,453 records offers oppose | not the cause |
| A parse step mapping oppose away | `_step_check` keeps any declared word as said (`neg_advisor.py:1240`); the decided label is the settled top answer (`neg_advisor.py:1715`); no mapping exists | not the cause |
| Threshold or decision rule | `choice_threshold` 0 (`neg_advisor_prompt.json:15`), the top answer read; oppose was never top and its margin never above -0.5 in improved (D788_JOINT_FIELDS_20261119.md) | not the cause |
| A decoding constraint | choice steps generate nothing: one forward pass, probabilities over the declared tokens (`scripts/choice_decision.py:100`); the declared mass is 0.89 to 0.999, so the model is not pushed off a wanted answer | not the cause |
| The answer's token form | oppose is scored on its first token `op` (453, a fragment; `oppose` is `op` + `pose`), support and accept on whole-word tokens (23362, 10330) (`scripts/choice_decision.py:85`). The asymmetry is real, but a first-token probability bounds the whole word's from above, so it can only favour oppose; it cannot make it 0 | real, removed by the fix, not the cause |
| Answer order | accept is named last and wins 980 of 1,453; order bias may shift accept against support, it cannot hold oppose at a median of 2e-07 | not the cause of 0 |
| **The step's input and question** | The stance question asks whether a position "supports, opposes or accepts the proposal" (`neg_advisor_prompt.json:18`, choice-first form `:25`). 73 of 85 persona positions predate the proposal's text: they state what the party wants and cannot hold an attitude toward a later text. Read literally, a statement in favour of something on the same topic "supports" or "accepts"; the question never asks whether the proposal fails what the position asks for, which is what a conflict is | **the cause** |
| **The red-line route** | The second route to a conflict is a crossed red line (`neg_advisor.py:1440`, `1454`); it is asked only of positions marked red lines (`neg_advisor.py:1319`), and 0 of 18 items declare one, so it is never asked | **second cause: conflict has a single route, the stance step** |

The composition then cascades (`neg_advisor.py:1454`): no oppose and no red line gives `no_conflict`, so the
stance is never reject (`neg_advisor.py:1495`, `1511`). In the plain method one constrained reply writes every
field; its near-constant accept / no_conflict is the same model on the same literal reading, and is not changed
here (see section 5).

## 2. The fix: C4, the compare conflict question

`advice.methods.stepwise.conflict_question: compare` (declared config, off as shipped: `stance`).

- In place of the stance question, each touched position is asked one CHOICE-A question
  (`neg_advisor_prompt.json:54`, `compare`): the proposal with the item's round, the position with the round it
  was put on record in, and "Set what this position asks for against what the proposal would do if it were
  adopted as written. Would the proposal go against what the position asks for, fit it, or leave it aside?
  Answer with exactly one of: against, fits, aside."
- `compare_answers` declares each answer and the stance it counts as, written before any read, never from labels:
  against counts as oppose, fits as support, aside as accept. Each label's first token on the producer's
  tokenizer is a whole word (against 68749, fits 29222, aside 28512), so the token-form asymmetry is gone too.
- `neg_advisor.compare_answers` (`neg_advisor.py:1056`) checks the declaration: the template fills
  `{proposal} {quote} {party} {position_round} {round}` and names every label; labels distinct, lower case, none a
  stance label; each counts as a declared stance, exactly one as oppose. Refused with `conditional_accept` and in
  the trimmed arm.
- The chain (`neg_advisor.py:1360`) keeps `answered` (the label) beside `stance` (what it counts as) on each
  position, and the oppose margin toward the label counting as oppose, so the P3 threshold and the N1 figures of
  `tools/score_neg_advisor.py` read it unchanged.
- `neg_advisor.py build --config <copy>` builds a run's prompts from a declared copy of the config, so the shipped
  file stays as it is.
- No keyword table, no cue word, no figure chosen on labels (WORDS-A, Seckin's 15 November rule). The threshold
  stays 0 (top answer); a P3 threshold, if used, is tuned on a development split only (D-756 item 3, check 532).

Not fixed here, recorded: no item declares a persona red line (0 of 18). Red lines come from the item build
(`red_lines` in the build files, D-664); filling them is a build and labelling question for role S and role V,
not a code change in the chain.

## 3. Proof commands and results

```
py -3.12 -X utf8 tools/neg_conflict_fix_checks.py
651 PASS 5 proofs, neutralise, fail, restore, pass, no model: ...
py -3.12 -X utf8 scripts/verify_session1.py --checks 356,450,466,467,468,490,491,492,493,494,515,516,518,531,532,533,535,539,540,541,542,543,651
PASS=23  WARN=0  SKIP=0  FAIL/ERROR=0  TOTAL=23
```

Check 651 (`tools/neg_conflict_fix_checks.py`, fixture item of `tools/neg_advisor_checks.py`, scripted model):

1. cascade: the shipped stance question, a model that never answers oppose and no red line (the runs' shape):
   0 conflicts, the persona's opposing position on P-A2-1 reads `no_conflict` / accept, red line asked 0 times.
2. oppose-shaped: under compare, `against` on the persona's position makes P-A2-1 `conflict` / reject; compare
   asked of all 6 positions, stance asked 0 times; both rounds and the quote shown; margin toward against 0.85.
3. neutral: every answer `aside`: no conflict on any proposal.
4. replay: the same reply composed again from saved step records by `recompose_stepwise`, no model.
5. refusals: trimmed arm, conditional_accept, two answers counting as oppose, a stance label, a template not
   naming a label, each refused; off (or not declared) asks and composes exactly as before.

Neutralised (the compare answer read as accept whatever was said): proofs 2 and 4 fail; restored: all pass.
The whole gate was not run (lane rule); the 23 checks above are the ones that exercise the negotiation advisor's
chain, its prompts config and its readers.

## 4. Bound files and re-seal

Touched: `benchmark/baselines/neg_advisor.py`, `benchmark/baselines/neg_advisor_prompt.json`,
`tools/neg_conflict_fix_checks.py` (new), `scripts/verify_session1.py` (check 651), `docs/CLAUDE_REFERENCE.md`.

- No controller-bound file is touched (CONTROLLER-BINDING: `tools/ordinary_final_cloud.py`, the bound wrapper,
  runner, watchdog, guard and sealer are unchanged), so no existing bundle is invalidated.
- The workload code is carried in each bundle's source tree, and the switch is read from the prompts file's own
  config: a measurement under compare needs its own prompts build and its own seal from a commit holding this
  change. Old prompts files (conflict_question absent or stance) replay byte for byte as before.

## 5. Measurement plan (D-789: the fix's own fresh sets, built and frozen before it is tried)

Sets, built before any compare run and opened only for this check, each frozen with its digest and a look counter
at 0 (`tools/freeze_negotiation_set.py`), sizes from stages/NEG_SYNTH_PIPELINE.md:

- C4 validation: 40 items, C4 pilot: 24 items, drawn whole by a seeded, written rule; real items first, synthetic
  items from new seeded cards under NEG-SYNTH-A (never the final test, reported apart). Neither set overlaps the
  old pilot, dev_1 (65), pilot_1 (31) or the D-798 validation set. Labels by role V (blind), keys held by role N.
- Before reading: the look logged in stages/NEG_ITERATION_LOG.md, with the figures to be read named: M1, M1m,
  conflict-class F1 (floor 0.60, D-712), N1 position-level oppose recall and precision against the build's
  stances (check 533), M5, and, beside them, M4 and M10 (no conflict rule alone reaches 0.60 on them,
  stages/NEG_ROUND1.md:92-97).

Runs (one prompts file per set, `neg_advisor.py build --set <set> --form advice --groups system_advice
--config <copy with conflict_question compare> --out <outside the repository>`; the stepwise method with the
choice_first order, full context; one seal per set):

1. The pilot set first (24 items): a check that the compare question is answered by form (no refusal rate above
   the stance step's), that `against` occurs at all, and the declared mass of the new answers; counts only.
2. Then the validation set (40 items), split into two launches of 20 items so each step stays inside the 5 USD
   pre-approval with margin.
3. Role N scores each with `tools/score_neg_advisor.py score` (key side) and `dev-figures` (N1, P3 with and
   without, D-758 link reported on and off), counts and figures only back to the lead. The plain method and the
   shipped stance question are not run again (D-752); the comparison is to the bar and to the recorded
   pilot figures, with the set difference named (FACTORS-A).

Cost forecast (`tools/loop/step_cost.py`, A10 at 1.29 USD an hour from the provider inventory of
NIGHT_neg_improved, observed 2026-11-18; workload from the improved run's measured 8,779 s for 36 stepwise
prompts, about 244 s an item; boot 6, install 6, return 3 minutes; asset copy MATCH):

| Step | Workload | Without measures | With measures |
|---|---|---|---|
| neg.c4_pilot (24 items) | 98 min | 4.95 USD | 3.16 USD |
| neg.c4_validation (40 items, one launch) | 163 min | 6.76 USD | 4.98 USD |
| neg.c4_validation as two launches of 20 | 82 min each | 4.50 USD each | 2.71 USD each |

The improved run's workload took 146 minutes against a forecast of 90, so the single 40-item launch (4.98 USD)
is too close to the 5 USD pre-approval: use the two-launch split. Seals and role V labelling are separate steps
with their own forecasts. Total for the three launches with measures: 8.58 USD (3.16 + 2 x 2.71), within the
D-749 cap; the split figures are the same formula (minutes / 60 x 1.29 x 1.3), to be printed by step_cost.py from
their own step files at launch.
