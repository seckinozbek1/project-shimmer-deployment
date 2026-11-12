# The D-S92 gate: which configurations go to the quick subset

Written 11 November 2026, 11:51 +03:00 (system clock), on lane/gate-attempts from loop/2026-10-27 at
af1a3e85, before the gate set is drawn and before any quick-subset figure exists. Plan only: nothing
here was launched, sealed, built or read. No key, label, fresh-set, role or held-out file was opened;
every result below is copied from a decision on the loop branch. Every figure is marked
**(measured: source)** or **(estimate: basis)**. Prices: A10, us-east-1, 1.29 USD an hour
(measured: D-398), times the guard's 1.3 factor, so 0.028 USD a forecast minute.

Read for this: PLAN_TO_14_NOVEMBER.md, GATE_SCOREBOARD.md, GATE_SET.md, DECISIONS.md D-248 to D-297 and
D-320 to D-470, ABLATION_PLAN.md (lane/ablation), SAVINGS_PLAN.md (lane/savings), TRAIN_JUDGE_DATA.md
(lane/train, attempt 2f), IMAGE_PLAN.md (lane/image), OPEN_ITEMS.md, and the code named in section 4.

## 1. Where the system stands against both bars

No gate figure exists: the scoreboard has no row, and the system as it ships today (the ContraDoc
rule declaring `[compare: passages]` since D-331, the pair question in the reply form, answered by
PRACTICE_AUDITOR on Phi-3.5) has never run on any item (measured: ABLATION_PLAN finding 6). All the
evidence below is development evidence on items now counted as tuned (GATE_SET section 1), most of it
from replays, not from the pipeline. B1 is the bare Phi-4 in J1's two forms.

How the system's label is made matters for every figure: the scorer labels B3 under `v2_primary`
(`tools/score_corpus.py`, `mapping.label_pipeline_arm`), where an item with no record is CLEAR. A
silent system therefore answers "no contradiction" on every ContraDoc document and "supports" on every
SciTab claim (read from code: `benchmark/adapters/common/mapping.py` lines 1 to 20).

### ContraDoc (binary judgment accuracy, ABSTAIN wrong)

| Arm | Figure | Mark |
|---|---|---|
| B1, Phi-4 with reasoning, 60 documents | .567 | measured: D-277 |
| B1, the better group, half A / half B (30 each) | .600 / .567 | measured: D-291, D-294 |
| Cloud reference (claude-opus-4-8), half A, direct / reasoning | .900 / .867 | measured: D-365 |
| The judge by probabilities, Phi-4 base, replay, half A (in sample) / half B | .700 / .600 | measured: D-291, D-294 |
| The same, trained mix (permissive), half A / half B | .733 / .600 | measured: D-293, D-294 |
| "Either" (base judge or B1 with reasoning flags), half A, in sample | .733 | measured: D-297 |
| The pipeline's own unit judging before INFRA-046 (C1, 15 documents) | 0 right flags, all silent | measured: D-257 |

- Bar (a) needs about .67 to .70 (estimate: B1 .567 to .600 plus .10). The best figure out of sample
  is .600, three points above B1 (measured: D-294). Gap to (a): about 7 to 10 points (estimate).
- Bar (b) needs about .82 to .85 (estimate: the cloud's .867 to .900 less .05). The best figure in
  sample is .733. Gap to (b): about 9 to 12 points in sample, about 22 to 25 out of sample (estimate).
- Loss causes. (1) Reach: of 30 gold documents, 4 name no partner, 1 matches no passage, 7 hold both
  marks in one passage, and of the 18 with two passages the top 40 pairs hold both on 14 (measured:
  D-274); a proposed pair reached 9 of 17 gold on half A and 5 of 13 on half B (measured: D-285). So a
  perfect judge on these pairs ends near .73 (estimate: clear documents right plus reached gold, 22 of
  30 on each half). The ranker does not separate gold from clear (AUC .491, measured: D-276), so more
  pairs buy reach and false flags together. (2) Out of sample the judge's flags fail the chance test
  (tail .29 to .40, measured: D-294). (3) The shipped form asks Phi-3.5, which flagged all 50 items in
  the agent prompt (measured: D-263); it has never been asked the narrow pair question.
- Read plainly: no configuration in hand has development evidence of meeting bar (b) on ContraDoc.

### SciTab (macro-F1; every figure so far is 2-class, D-379)

| Arm | Figure | Mark |
|---|---|---|
| B1, Phi-4 with reasoning, 93 claims | .838 | measured: D-277, D-380 |
| B1, half A / half B | .918 / .761 | measured: D-291, D-294 |
| Cloud reference, half A, direct / reasoning | .891 / .888 | measured: D-379 |
| The cell question by probabilities, Phi-4 base, half A (in sample) / half B | .738 / .716 | measured: D-291, D-294 |
| The same, trained mix (permissive), half A / half B | .837 / .756 | measured: D-293, D-294 |
| Judge 2e trained_full, half A, in sample | .797 | measured: D-370 |
| Judge with B1 combined, half A, in sample | .941 to .943 | measured: D-297 |
| The pipeline's unit judging (C1, 37 claims), `detection_dev` | .035, 34 silent | measured: D-257 |

- The system as it ships asks no cell question (`[compare: cells]` is off and no build takes it), so
  it is silent and every claim reads "supports": about .33 to .35 in 2-class (estimate: one class at
  F1 near .67, the other at 0, on a near-balanced set).
- Bar (a) in 2-class needs about .86 to 1.0 (estimate: B1 .761 to .918 plus .10), which is above the
  cloud reference's own .89. Bar (b) needs about .84. The best figure out of sample is .756.
- The gate set is likely 3-class (GATE_SET section 7: at least 30 not-enough-info claims and 15
  percent). No arm has a 3-class figure: not B1, not the cloud, not the system (measured: D-379).
  This is the one place the standing could differ from the table above, in either direction.
- Loss causes. (1) Nothing is asked (above). (2) In the 5,800-token agent prompt the same Phi-4 goes
  from 13 right, 2 false to 13 right, 10 false (measured: D-277): the narrow question exists for
  that. (3) By probabilities the judge has no reasoning step, and B1 with reasoning leads it on both
  halves. (4) The answer order moved the top answer on 10 of 45 claims (measured: D-291). (5) In
  3-class, a cell decision of "cannot be settled" writes no record (CELLS-A), and no adapter labeller
  reads the pairing map's `cell_claims` row (read from code: no match in `benchmark/adapters/` or
  `tools/score_corpus.py`), so it is labelled "supports" and the system can never answer
  not-enough-info through the cell step. That caps 3-class macro-F1 near two thirds of its 2-class
  value (estimate: one class of three at F1 0).

## 2. The configurations, ranked

Ranked by the chance of clearing bar (a) on both benchmarks, then by what is already built. K0 runs
whatever the ranking says: it is the plan's rows 6a and 6b, the scoreboard's first row and the "off"
arm of every part.

| # | Name | The one change against the shipped system |
|---|---|---|
| 1 | K1, the judge decides | Both narrow questions go to JUDGE (Phi-4 base) in the decision form: pairs on ContraDoc, cells on SciTab |
| 2 | K3, either | K1, and a document is also flagged when a whole-document reading with reasoning flags it; on SciTab the reading answers where the judge cannot settle |
| 3 | K2, the trained judge | K1 with judge 2e's adapter (trained_full) and 2f's calibration |
| 4 | K0, as shipped | none |
| 5 | K4, a stronger reader | the judging model replaced by the strongest open model the licence rule and a larger card allow |

### K1, the judge decides (top choice)

- **Change.** `config/passage_pairs.json` `form: decision`; a `passage_pair` and a `cell_claim`
  threshold in `config/semantic_thresholds.json`; `[compare: cells]` on the SciTab gate build.
- **Evidence.** ContraDoc: the base judge was above B1 on both halves (.700 against .600 in sample,
  .600 against .567 out of sample; measured: D-291, D-294), never by 10 out of sample. SciTab: it
  replaces silence (about .34, estimate) with a judge measured at .716 to .738 2-class (measured), so
  it is the only built step that moves SciTab at all, and it stays below B1 in 2-class.
- **Where the code is.** Merged on loop/2026-10-27: CHOICE-A, PAIRS-A, CELLS-A, JUDGE-AGENT-A (checks
  324, 325, 326, 331). Not merged: `"compare: cells"` is not in `bundle.RULE_DECLARATIONS` and the
  SciTab adapter has no `--rule-declaration` option.
- **Needs before it may run or ship.** (1) `[compare: cells]` on the SciTab gate build: ruled by the
  lead as D-471 (a configuration of the system under test; Seckin is informed) and built on this lane
  (section 5).
  (2) Thresholds: none is measured in the product file, so nothing would be asked (CHOICE-A). For the
  quick subset a measurement decision in D-404's form on a measurement branch; the values come from a
  written calibration record on G1's half A rows only (the base by C_BAR's rule at temperature 1:
  .9 for pairs and .6 for cells, measured in sample: D-291), never from the quick subset. D-371's
  gap applies: the read must refuse a threshold with no calibration record. (3) To ship: a decision
  adopting the form (CHOICE-A), written with the quick-subset evidence. (4) The peak VRAM of a run
  that loads Phi-4 beside Phi-3.5 and the producer is not measured (JUDGE-AGENT-A); the savings proof
  (i) run measures it (D-404, proof iii).
- **Cost.** ContraDoc 40 documents: about 243 minutes, 6.79 USD (estimate: K0's 223 minutes plus 80
  decisions a document at 0.36 s). SciTab 8 tables: at most 64 minutes, 1.79 USD (estimate: FULL-ST's
  upper end; the cell decisions add seconds). Two instances.
- **Slot.** Fits beside rows 6a to 6c at 14:30 and ends about 18:35, before step 8, only if it is
  sealed with them at 14:00 to 14:30. It needs role B's SciTab bundles built with the declaration in
  the same pull, so the request must change before role B builds.

### K3, either (a what-if first, a build only if it leads)

- **Change.** Beside K1's steps, one whole-document question with reasoning to the same Phi-4; the
  document is flagged when either flags.
- **Evidence.** The only combination with a development figure 10 points above B1 on ContraDoc: .733
  against .600, in sample, 9 discordant documents (measured: D-297). On SciTab .941 to .943 against
  .918 in sample, on 2 to 8 discordant claims (measured: D-297). It was chosen as D-S45's attempt 1
  and never read out of sample (D-322). It reaches contradictions inside one passage, which no pair
  can (7 of 30 gold, measured: D-274). It still sits about 13 to 17 points under the cloud (estimate).
- **Where the code is.** As a measurement only: `benchmark/baselines/either_test.py`, bound to the
  D-S45 set. No pipeline step asks a whole-document question (G1's document form is replay only and
  was not usable, D-248).
- **Needs.** For the quick subset nothing rented: its rows are computed on the laptop from K1's saved
  decisions and the B1 arm's saved replies (row 6c), labelled "what-if, not a system run, steering
  only". To ship: a pipeline step, its checks, and a decision; a flag from a whole-document reading
  has no two quotes, so it cannot be a `contradiction` record as INFRA-046 defines one. Whether it may
  decide an item with no record is a governed question for Seckin. It then needs its own real
  quick-subset run before any claim read.
- **Cost.** 0 USD for the what-if. As a real run: K1 plus about 55 seconds a document with reasoning
  (measured rate on long prompts: D-278), about 37 minutes more on 40 documents, 1.03 USD (estimate).
- **Slot.** The what-if fits step 7 (18:15 to 19:30). The build does not fit 11 November.

### K2, the trained judge

- **Change.** JUDGE answers with judge 2e's adapter and 2f's temperature and thresholds.
- **Evidence.** In sample on half A, SciTab .703 to .797 and ContraDoc net held (measured: D-370);
  still below B1's .838. The earlier trained mix did not beat its base out of sample (no "training
  helped" at .0125; measured: D-294).
- **Where the code is.** 2f's procedure and code on lane/train a2bfdda0 (not merged); the replay and
  derived-run tools on lane/savings (`reuse_read.py`, check 346, not merged). The registry's JUDGE is
  the base model: no product route loads the adapter or applies a temperature (read from code:
  `config/agent_registry.json`, no adapter reference under `scripts/`).
- **Needs.** The gate set pinned (2f refuses without it), 2f's calibration record per family (a
  laptop fit from saved passes, no model), proof (ii) riding the replay, and, if chosen, the product
  route for the adapter before the claim set is sealed.
- **Cost.** One replay of K1's saved questions: 35 minutes, 0.98 USD (estimate: SAVINGS_PLAN R2).
- **Slot.** After K1 ends: about 18:45 to 19:20, inside step 8's window. This is the plan's own
  ablation rows 1 and 3.

### K0, as shipped

- **Change.** None. ContraDoc with `[compare: passages]` in the reply form; SciTab unit by unit.
- **Evidence.** None on ContraDoc (never run). SciTab: silence (measured: D-257).
- **Needs.** Nothing. **Cost.** 6.23 USD and 1.26 to 1.79 USD (estimate: plan rows 6a, 6b). It is
  also the first timing of the pair step in the reply form (plan section "Kısa cevap").

### K4, a stronger reader (the only route in sight to bar (b) on ContraDoc; not for 11 November)

- **Change.** A larger open model as JUDGE and as B1's model (B1 is the same model bare, D-S33 item
  2a), on a larger card (D-S95).
- **Evidence.** None measured. It can close the gap to the cloud; it raises B1 with it, so it does
  not by itself help bar (a).
- **Needs.** A candidate read live from the provider, licence checked (D-281), its weights in a new
  asset archive, a decoding policy entry, one reference run on its machine type (D-389), a decision.
- **Cost and slot.** Not forecast: no rate is measured. A plan today, a quick-subset run on 12
  November at the earliest.

Not listed, with the reason: more than 40 pairs (reach rises at most from 14 to 18 of 30 gold, and
the false flags rise with every pair; measured: D-274, D-280); the reply form on Phi-4 (withdrawn by
D-279: about 8 hours for a form the path is leaving); the document-level judge G1 and the prompt
without its example C1 (not usable, dropped; D-248, D-257).

## 3. The selection rule, written before any quick-subset figure is read

1. **Figures.** Only `gate_score.figures` on the pinned quick-set digest, in each paper's metric, in
   the class setting the freeze declared, with the 95 percent paired interval. A replayed, derived or
   what-if arm is labelled so and is "steering only" until its proof has passed (SAVINGS_PLAN).
2. **A valid arm.** At least 95 percent of its entries passed execution integrity and its B1 group is
   at least 95 percent readable (system_test's void rule). An arm that is not valid is not compared.
3. **A part goes in only when shown (D-422).** Starting from K0, a part (the decision form on pairs,
   the cell step, the adapter, the either reading) enters the configuration only if, on the benchmark
   it acts on, the paired 95 percent interval of with minus without lies above zero, and on the other
   benchmark its point difference is not below zero. "Not shown" keeps the part off.
4. **The choice.** Among configurations whose every part passed line 3, the one with the largest
   point difference from B1 on its weaker benchmark. A tie goes to the configuration with fewer
   model-backed parts, then to the cheaper per item. K3 as a what-if can be chosen only as "build it
   and run it on the quick subset"; it is never sealed for the claim set from a what-if.
5. **Whether the claim set is read at all.** The claim set is sealed and launched only if the chosen
   configuration's point figures on the quick subset meet both bars as coded on both benchmarks: at
   least 10 points above B1 and at most 5 below the cloud reference. The intervals are reported beside
   them and do not gate this step, since 40 documents cannot show a 10-point gain (standard error near
   .08, GATE_SET section 5). Reason: the claim read is one opening at the 97.5 percent level, a second
   one is at 98.75 and costs about 43 to 69 USD of Lambda (estimate: plan rows 10a, 10b) from the
   144.86 left under 299 (measured: plan section 1).
6. **Nothing is tuned on the quick subset tonight.** Thresholds and temperatures come only from
   calibration records on G1's rows. A change made after seeing a quick-subset figure is a new
   attempt: written first, then run.
7. **The record.** One decision on the loop branch naming the configuration's digest, each part's
   interval, the three figures side by side for each benchmark, and this rule; one steering row per
   arm in HELDOUT_OPENINGS.md and on the scoreboard.

**If no configuration clears line 5.** No claim read and no fresh read (D-S70 item 3: no forced
read). The same hour: the scoreboard rows, FOR_SECKIN and a push with the system's, B1's and the
cloud's figures side by side (D-S92 item 4), opening with the "Hedefe uzaklık" line (D-S94). The lesson
is written (D-S71) and `tools/miss_diagnosis.py` is run over the quick-subset runs for the loss table.
The next attempt is chosen from that table and written before its read, in this order unless the table
says otherwise: K3 built as a real step, K4, then a reasoning step on the cells the judge cannot
settle. Work does not stop (D-S92 item 2). Two flat measurements or 12 hours without a rise go to
Seckin as an alarm with the change of course (D-S94 item 5). The latest claim-set launch that still
leaves the fresh read before 14 November 14:30 (D-492; was 11:00) is about 13 November 15:00 at the slow end (estimate:
plan rows 10 to 14, 19.5 hours). Past that, the 14 November package states the standing against both
bars on the quick subset, and the work goes on (D-S92 item 3).

**One thing only Seckin can settle.** In 2-class, B1's .838 plus 10 points is above the cloud's own
.89 (measured figures, tuned items). If the gate set comes out 2-class, or B1 stays near the cloud in
3-class, bar (a) on SciTab asks the system to beat the cloud reference. The numbers 10 and 5 are his.

**Settled (D-550, Seckin 21:29, 12 November).** The bars stay as they are, in each paper's metric and the
class setting the freeze declared (3-class, D-543), and are not changed before or after any read. If B1
sits near the cloud on SciTab, so that bar (a) asks the system to beat the cloud, that is reported plainly
as it falls.

## 4. What must be built or sealed today, and by whom

Times are the plan's; the clock read 11:51 when this was written.

| # | What | For | Who | By |
|---|---|---|---|---|
| 1 | `[compare: cells]` on the SciTab gate build: ruled, D-471. Done | K1, K2, K3 | lead | done |
| 2 | The SciTab adapter's `--rule-declaration "compare: cells"`, its proofs, and the role B request's step 5 (each set built as shipped for B1 and declared for B3). Done on this lane, 783650ff; role B must build from a tree that holds it | K1 | this lane, then role B | before role B builds (step 4, ends 14:00) |
| 3 | Launch the savings proof (i) (measure/savings-proof-i, 16 entries on C1 documents, 89 minutes, 2.49 USD, estimate: D-404). It needs no gate set and it measures the judge's peak VRAM beside the auditor before K1 is sealed | K1 | lead, `savings` | now, not 14:30 |
| 4 | Merge lane/train (2f) and lane/savings (reuse, check 346) after their gates | K1, K2 | lead | 14:00 |
| 5 | After the freeze: pin the gate set in 2f; fit the calibration records (trained_full by 2f; the base by C_BAR's rule) for `passage_pair` and `cell_claim`, laptop, no model | K1, K2 | `train-judge` | 14:15 |
| 6 | A measurement branch from the loop tip: the decision form and the base thresholds of item 5; the refusal of a threshold with no calibration record (D-371's gap); the lead's measurement decision in D-404's form before the seal | K1 | `choice-build`, lead | 14:15 |
| 7 | Seal order at 14:00: K0 ContraDoc, B1, K1 ContraDoc, K1 SciTab, K0 SciTab, then the ablation rows. K1 goes before ablation row 5 (both checkpoints against base), which serves the report more than the gate (D-S94 item 4) | all | lead | 14:30 |
| 8 | The labeller reads the cell step's decisions: ruled, D-472, built on this lane, 4fe6a492 (section 5). Still open: the gate's read must ask for it (`benchmark_labels(..., arm="B3", scoring="detection_dev")`), and under that mode a silent ContraDoc document is ABSTAIN, not CLEAR; which mode the ContraDoc arm is read in is the lead's ruling before any read | K1, K2 | lead rules, `choice-build` wires the read | before step 7 |
| 9 | The what-if rows for K3 from K1's decisions and row 6c's replies, through `gate_score.compute`, labelled "not a gate read" | K3 | `choice-build` | 19:30 |
| 10 | K2's replay bundle: K1's saved questions (`reuse_read.py judge-prompts`), the 2e adapter as a support file, proof (ii) riding | K2 | `savings`, `train-judge` | 18:45 |
| 11 | Only if K2 is chosen: a product route that loads JUDGE's adapter and applies the temperature, with its check, before the claim set is sealed at 21:00. If it is not ready, K2 is not sealed and K1 stands | K2 | `judge-product` | 21:00 |
| 12 | K4's plan: candidate, licence, archive size, machine type, forecast | K4 | a new lane | 12 November |

Not known, stated: the pair step's time in the reply form; K1's peak VRAM; every 3-class figure; the
cloud reference on any gate item; whether Phi-3.5 answers the narrow pair question at all. The quick
subset measures the first, second and last this afternoon.

## 5. Built on this lane after the lead's rulings (D-471, D-472)

- **783650ff, D-471.** `bundle.RULE_DECLARATIONS` admits `compare: cells`; `bundle.BENCHMARK_DECLARATIONS`
  lets a SciTab build add only that and a ContraDoc build only `compare: passages`. Under the
  declaration the SciTab rule's text is the claim alone: the cell step takes the rule's whole text as
  the claim (`cell_selection.review`), and the measured question asked the claim without the
  template's other sentences (`choice_judge.claim_of`). The lead accepted the claim-alone text because it
  is the measured question, and confirmed `compare: passages` on ContraDoc's B3 build. B1's prompt is built from the bundle's rules,
  so role B builds each set twice, as shipped for B1 and declared for B3 (GATE_SET_ROLE_B_REQUEST.md
  step 5); on the synthetic fixture `items.json`, `parts.json` and every key are byte for byte the
  same in both builds. Proofs in `scripts/system_test_checks.py` (gate check 325), four through
  `prove_effect` with their neutralisations.
- **4fe6a492, D-472.** `detection.cell_decisions` reads the pairing map's `cell_claims` row. Settled
  as holding: the unit holds (supports). Not settled: the unit is uncertain, never CLEAR; with every
  unit unsettled the three-way reading gives not enough info, otherwise ABSTAIN. A settled "not met"
  speaks through its kept `claim_not_met` record alone. No decision and no record: silence, ABSTAIN,
  counted apart. Python's-records-alone (S-8) reads no decision. `tools/score_corpus.py`
  `benchmark_items(..., scoring="detection_dev")` is the route; `v2_primary` stays the default and is
  unchanged. Proof in the adapter checks' detection group (gate check 317), two neutralisations.
- **Run in the foreground:** the adapter checks (87 cases, PASS), the detection group (11 cases,
  PASS), the build group (20 cases, PASS), `scorer_path_checks` and `scorer_section9_checks` (PASS).
  `system_test_checks.run_checks` stops at "counted before any fresh key" (BASELINE_FAILED) in a lane
  worktree, the same on the unchanged loop-lead worktree, so not from this change; the declaration
  proofs were run through `prove_effect` one by one.

## 6. K1's thresholds under CHOICE-A: the calibration plan

Both thresholds are the untrained Phi-4's at temperature 1, chosen by C_BAR's own rule
(`choice_read.choose_threshold`: its grid .5 to .999 and its gates) on G1's half A, development items
the gate set excludes by group and paper (GATE_SET section 6). Never the gate set, never half B,
never the fresh set. The product reads one number per family
(`choice_decision.threshold`) and applies no temperature, so K1 needs none.

| Family | Rows | The pass to read | Value and the errors it produces | Lambda |
|---|---|---|---|---|
| `passage_pair` | ContraDoc half A: 30 documents, 2,400 pair prompts of `external/s05/P2A/choice_prompts_r1.json` (`9d5b3e1f...`), order controls apart | C base's saved pass (`external/s05/C`, D-291). The pair task declares no shown tool, so the product's question is the measured one byte for byte | .9 (measured: D-291, `choice_read_a.json` `20a6f39b...`). At .9 on half A: 10 documents flagged, 9 right, 1 false (precision .90); 9 of 17 gold found; accuracy .70. Out of sample, half B at the same value: 3 flagged, 2 right, accuracy .60 (measured: D-294) | 0 minutes, 0 USD: a laptop read of a saved pass |
| `cell_claim` | SciTab half A: 15 tables, 45 claims | The untrained group's pass of judge 2e's session (`external/s05/T2E/ev_F/evidence/b1/train/passes/base`: `unsloth/phi-4-bnb-4bit`, snapshot `098ea917...`, no adapter), in the shipped claim form with the FIGURES block | **.6** (measured: the record below). At .6 on half A: 10 claims flagged, 10 right, 0 false (precision 1.0); 26 of 45 claims right (accuracy .578); 2-class macro-F1 .703; 0 abstained | 0 minutes, 0 USD: read from a saved record |

**Read on 11 November for D-476 (item 2), nothing run on a model and no pass read again.** Both values
stand in one saved record, `external/s05/T2E/read_a_2e2/judge_success_read_a.json` (sha256
`db4f20fb16a19bc04791d9e8f4d33bb25a6de8e8542a9b879352e021f6f3b29b`), under `read.base`: each
`threshold_by: choose_threshold`, C_BAR's rule at temperature 1, on half A alone. It is judge 2e's
success read (`judge_success.tuning_thresholds`, lane/train), not a new `choice_read.py read-a`: the
rule and the rows are the same, so I did not read the pass a second time, and half B was not read.
The same record gives the pair value again on the same session: .9, 10 documents flagged, 9 right,
1 false, accuracy .70, 2,400 pair prompts. What ties the record to the product's questions:
- the base pass asked `trained_questions.json` (`d65b849c...`), 4,894 prompts, each equal by
  `user_sha256` to the prompt of the same id in `choice_prompts_r1_shipped.json` (`12479763...`,
  7,340 prompts with the order controls);
- every prompt of that file that is not an order control opens and closes with the product's own
  template: 93 of 93 claims against `config/cell_selection.json` `decision.template`, 4,800 of 4,800
  pairs against `config/passage_pairs.json` `decision.template`; 68 of the 140 claim prompts carry a
  FIGURES block. Not checked: that the cells shown equal what the product selects today (limit (b)
  below).
The fallback replay is not needed.

Commands as first planned (kept for the record; steps 1 to 3 are answered by the saved record
above, step 4 is done as branch measure/gate-k1, commit 64b99284 on loop tip ea851ecc, not sealed):

1. `py -3.12 benchmark/baselines/choice_read.py read-a` on each pass with the bar's inputs, as D-291
   and D-293 ran it (bar `60ceda17`), into a new folder; its output names the threshold per benchmark
   and the counts above. A pass whose prompts are not the file's is refused by the tool.
2. Confirm the question is the product's: render one half A pair and one half A claim through
   `passage_pairs` and `cell_selection.question` with JUDGE's shipped contracts and compare the
   SHA-256 with the saved prompt's `user_sha256`. A difference means the pass is not this question's.
3. Only if step 2 fails for a family, the replay: `py -3.12 benchmark/baselines/choice_judge.py build
   --pairs-from external/s05/P2A/p2a_prompts.json --claim-workload <G1 SciTab bundle> --claim-items
   <its items.json> ... --permuted-half-a --out <prompts.json>`, sealed as a B1 replay bundle
   (`--arm B1 --replay-prompts <prompts.json> --b1-checkpoints <one pass, "replay": true>`), on the
   A10: 7,340 prompts took 47 minutes (measured: D-291) plus 15.4 of setup, about 62 minutes, 1.74 USD
   with the factor (estimate). Then step 1 on it.
4. The two values go into `config/semantic_thresholds.json` `choice_decision` as plain numbers, with
   `config/passage_pairs.json` `form: decision`, on a measurement branch from the loop tip with this
   lane merged (`measure/gate-k1`), in the shape of measure/savings-proof-i's commit 0f4f6624, each
   with a note naming its read record's SHA-256.

Stated limits. (a) Half A holds no not-enough-info claim (23 supported, 22 refuted; measured: D-380),
so how often the cell threshold leaves a true not-enough-info claim unsettled is not measured on any
development item. (b) The measured selection has no embedding tie-break and the product's has
(CELLS-A), so the cells shown can differ on ties. (c) Both values were chosen on 30 documents and 45
claims; half B did not confirm the pair value. (d) Peak VRAM with the judge loaded beside the
auditor is unmeasured until proof (i) below.

**The measurement decision the lead records (D-404's form), before the seal:**

> **What:** K1 on the gate's quick subset, on branch measure/gate-k1, never merged into the product by
> this decision. One commit on the loop tip: `passage_pairs` form `decision`; `choice_decision`
> thresholds `passage_pair` .9 and `cell_claim` .6, each the untrained Phi-4's at
> temperature 1 by C_BAR's rule on G1's half A, record `judge_success_read_a.json` `db4f20fb...`
> (pairs also `choice_read_a.json` `20a6f39b...`), error rates as GATE_ATTEMPTS section 6 states
> them. The commit is measure/gate-k1 64b99284. **Items:** the quick subset alone (40 ContraDoc documents, the SciTab quick
> tables), B3 bundles from role B's declared builds (D-331, D-471). **Run:** two `b3_only` batches on
> the A10 beside rows 6a to 6c, forecast 243 and 64 minutes. **Read:** steering only, by GATE_ATTEMPTS
> section 3, SciTab B3 labelled under D-472. **Not a claim, not an opening of the claim set; nothing
> is tuned on the result.** Adoption for shipping is a later decision under CHOICE-A, with the
> quick-subset evidence.

## 7. Savings proof (i): the seal and launch recipe (D-404)

State found: `external/s05/SAVINGS_PROOF/workload` holds the 8 staged documents and `STAGED.json`;
nothing is sealed. Branch measure/savings-proof-i holds commit A (0f4f6624, thresholds .5) and B
(14166f73, .7) on d89984d4, which is behind the loop tip: D-404 seals them rebased. Bundles sealed
before lane/tiers' merge refuse, so both commits must sit on the current tip. The helper scripts are
in the earlier lead session's scratchpad, `...\98615fb4d64ceccf\ac63cd67-443d-4def-839e-58be2eeb42e3\scratchpad`
(`seal_launch.py`, `make_binding.py`) and `...\20264aae-f72b-4867-8e32-3806ef167bb1\scratchpad`
(`dedup_archives.py`); written `<S>` below. I did not run any of this; flags not seen in a log are
marked "confirm".

1. **Rebase.** In `.claude/worktrees/savings-proof`: `git rebase --onto loop/2026-10-27 d89984d4
   measure/savings-proof-i`. Check that A and B differ only in `config/semantic_thresholds.json` (two
   lines) and that A differs from the tip only in that file and `config/passage_pairs.json`:
   `git diff --stat loop/2026-10-27 HEAD~1` and `git diff --stat HEAD~1 HEAD`. Note the two new ids.
2. **One ledger.** The worktree's `docs/loop/private` must be a junction to the main checkout's
   (D-364), and `external` reachable there the same way, since the sealer and the guard read paths
   under the running checkout.
3. **Two batch files** in `external/s05/SAVINGS_PROOF/`: `BATCH_A.json` and `BATCH_B.json`, each
   `{"form": "b3_only", "entries": [{"item": "contradoc_<id>", "arm": "B3", "bundle":
   "external/s05/SAVINGS_PROOF/bundles/contradoc_<id>_A"}, ...]}` (`_B` in the second), 8 entries
   each, for sealing (`seal_launch.py` finds a workload folder by the item's name). For the launch,
   `BATCH.json` with all 16 entries and the same bundle paths, the items named `contradoc_<id>_a` and
   `contradoc_<id>_b`: a `b3_only` batch refuses an item named twice (`batch_schedule`, "Every B3-only
   batch item runs once"). Settled by reading `tools/ordinary_final_cloud.py`: an item's name is held
   to `[A-Za-z0-9_.-]{1,64}` and used for the once-only rule, the entry's folder
   (`batch/<index>_<item>_<arm>`), `seal_entry.json` and the analyser's grouping; `batch_entries`
   compares nothing inside a bundle with it.
4. **Seal A, then B, in the foreground** (a background seal dies under the idle reaper): with the
   worktree at A, `py -3.12 <S>/seal_launch.py SAVINGS_PROOF BATCH_A.json 89
   external/s05/SAVINGS_PROOF/inputs`; then `git checkout` B and the same with `BATCH_B.json`. Two
   changes to `seal_launch.py` first: `--reuse-assets` must name a bundle whose archive holds Phi-4
   (`750cf50d...`, for example `external/s05/C/C_BASE`; v12's archive does not), and add
   `--comparison savings-proof-i` so all 16 run on one machine type (D-389). `inputs` needs
   `runtime.candidate.lock` and a fresh `provider_inventory.json` (C1's folder shows the two files).
   The script pauses cleanly after 420 s; rerun it until it prints `failures 0`.
5. `py -3.12 <S>/dedup_archives.py` over the 16 bundles (hard links for the shared archive), then
   `py -3.12 <S>/make_binding.py <each bundle>`.
6. Per bundle: `py -3.12 tools/ordinary_final_bound_reverify.py --bundle <b>`; from `tools/`:
   `py -3.12 verify_ordinary_final_assets.py --bundle <b> --wheelhouse
   ../output/cloud_wheels/ordinary_final_cp312`; `MSYS_NO_PATHCONV=1 py -3.12
   tools/declare_asset_copy.py --bundle <b> --filesystem-name shimmer-filesystem --mount
   /home/ubuntu/shimmer-filesystem`; `py -3.12 tools/ordinary_final_bound_preflight.py --bundle <b>`.
7. Consistency: all 16 share assets, image, lock and control hashes; 8 name commit A and 8 commit B.
   Then usage, the reaper's last run and the ledger's spend (154.14 measured, 299 the stop).
8. **Launch,** one launch for all 16, from the worktree (at B). Settled by reading the code:
   `batch_entries` requires every entry to share the asset archive, image, `install.lock`, the
   control hashes and the sealed budget, and compares no source commit or source archive, so entries
   of A and B may share a session. The launch itself compares the running checkout only with the
   control hashes (the tools, equal in A and B) and requires each bundle's
   `AUTHORIZED_LOCAL_REVERIFICATION.json`. The one place HEAD matters is step 6's reverify
   (`ordinary_final_bound_reverify.py`: "HEAD changed runtime files after the sealed commit" when a
   pinned file differs between the bundle's commit and HEAD), so **reverify A's 8 bundles with the
   worktree at A and B's 8 at B**, in step 4's order, before moving on:
   `py -3.12 tools/ordinary_final_bound_cloud.py --bundle <the session bundle> --batch
   external/s05/SAVINGS_PROOF/BATCH.json --ledger docs/loop/private/budget_ledger.jsonl --purpose
   dev-savings-proof-i --forecast-minutes 89 --storage-forecast-usd 1.0 --detach`. Forecast 89
   minutes, 2.49 USD with the factor (estimate: D-404; the pair step's time in a full run is
   unmeasured, so the cap of 1.5 times is the real bound).
9. **Read,** after collection, with lane/savings merged: per document `reuse_read.py threshold
   --bundle <A bundle> --entry <its entry> --commit <B> --out <dir>` then `reuse_read.py compare
   --derived <dir> --full-bundle <B bundle> --full-entry <its entry> --out <file>`; the proof holds
   when every compare is equal and every label is the same. Proof (iii): the peak GPU memory in each
   entry's records, read before K1 is sealed.

## 8. Done for D-476 on this lane (11 November)

- **The mode per benchmark** (91405abd): `system_test.SCORING` (ContraDoc `v2_primary`, SciTab
  `detection_dev`), `system_rows(runs, by_key, benchmark)`; a benchmark with no declared mode is
  refused. Three proofs in `scripts/system_test_checks.py`, each neutralised, run through
  `prove_effect` on synthetic run folders.
- **The cell threshold:** .6, section 6.
- **The recipe's two open points:** settled by reading, section 7 steps 3 and 8.
- **measure/gate-k1:** 64b99284, one commit on ea851ecc (`passage_pairs` form `decision`;
  `choice_decision` `passage_pair` .9 and `cell_claim` .6 with their record). Not sealed. Not built:
  D-371's refusal of a threshold with no calibration record; the branch's values are named in the
  file by their record instead. It is cut from the loop tip, which does not hold this lane; the
  bundles' runtime needs nothing from the lane (the lane changes the adapters' build, the labeller and
  the read).

## 9. After the vekil check (D-478)

- **The cut (CRITICAL).** Under a token counter each document's budget and prompt overhead came from
  B1's prompt over the bundle's own rules, so a declared build wrote another `parts.json` and role
  B's SHA-256 check would have stopped every B3 set; my first proof used the fixture with no cut and
  could not see it. Now `bundle.shipped_rules` gives the cut the as-shipped rules in every build.
  Proved with a token counter whose prompt count depends on the prompt's words and limits that
  really cut documents, on both benchmarks: only `conventions/rules.md` differs between the builds.
  Step 5 of the role B request says so.
- **The gate's SciTab arm.** `gate_score.system_arm` builds the system's rows for `figures` through
  `system_test.system_rows(runs, by_key, benchmark)`; the proof fails when that call drops the
  benchmark. `system_test.read` stays the fresh ContraDoc read and calls with its own default.
- **Never CLEAR beside a settled "not met".** `detection.cell_not_met`; two-unit proof.
- **Proof output:** `docs/loop/stages/gate_attempts_proofs.txt`, each stage of each entry.
- **measure/gate-k1:** a second commit corrects the `choice_decision` note; see the branch's tip.
  Section 8's commit id is the first of its two.
