# SciTab inside the current configuration (D-642 item 4): routing, decision authority, cell-grounded reasoning

Written 15 November 2026, 15:33 +0300 (from date), on lane/scitab-route from b0ab0d83. This is a design, nothing built.
It loads no model, and its figures were read from code, from decisions and from the paper at source.
It never reads an item of the quick subset (GATE_ATTEMPTS section 3 line 6). Every measurement proposed here runs on G1's SciTab development rows only: 93 scored claims in 29 tables, 2-class, no NOT ENOUGH INFO gold (D-239, `benchmark/baselines/g1_bar_items.json`, `judge_read.G1_SETTINGS`). Item (c), NOT ENOUGH INFO, is left to its own lane, as D-642 says.

## (a) Routing: where table answers meet the legal-text checks

**The trace, at b0ab0d83.**
1. `paired_review.plan_calls` (scripts/paired_review.py:1541) makes one plan per unit and rule. The one exception is a rule whose heading declares a comparison (`rules_by_id[rule_id].get("compare")`, :1575): it is skipped there and asked elsewhere. `[compare: passages]` goes to `passage_pairs`, and `[compare: cells]` goes to `cell_selection` (CELLS-A).
2. A SciTab claim built as shipped (K0, no `--rule-declaration`) declares nothing. Its unit holds a pipe table and the claim's figures are not a sum, band, rate, copy or carry Python computes, so its plan is `uncomputable` (UNCOMPUTABLE_PLAN, :2780).
3. The uncomputable plan's reply is read in the pipeline driver's phase 5.5 (the `plan.get("kind") == UNCOMPUTABLE_PLAN` branch). Each item is stamped from the plan and held to `paired_review.judged_item_refusal` (:2943). That is one test, written for findings about text fields.
4. A table answer fails it in one of two ways:
   - a figure relation (`finding_record.figure_relations()`) whose `value_a` and `value_b` are no number or date (`_is_figure`, :2874) is refused as `NO_FIGURES_FIGURE_RELATION`, "figure relation supplies no figures" (:2839). The model writes the claim's words or a cell's label into the figure fields.
   - an absence relation with no quote is refused through `refuses_judged_absence` (:1382, rule 0) as "absence claim supplies no quote" (:2992). The model answers "the table does not show it" as `missing_field`.
5. The refusals go to the pairing map's `uncomputable_refused`, and `tools/miss_diagnosis.py` names them `exposed_uncomputable_refused`. The figures are D-577 item 4 (K0 SciTab: 27 of 28 missed, 16 and 11 by the two reasons) and D-634 item 5 (30 of 30 lost, all this sub-cause). Since no kept record and no cell decision remains, `detection.classify` makes every item silence: ABSTAIN, K0's 0.0.

**What the trace says.** Neither refusal is wrong for what it was built for: a figure relation with no figures, and an absence with no quote, are exactly the unverifiable claims R1 (D-S22 item 1 (d)) refuses on legal text. The fault is the route. A claim over a table has no Finding-record shape on that path, because `claim_not_met` (the relation for it, INFRA-048) is refused there by design (`CLAIM_NOT_FROM_CELLS`: only the cell step may write it). K1 is not refused because its build declares `[compare: cells]` (D-471, `bundle.BENCHMARK_DECLARATIONS["scitab"]`), so its claims never reach an uncomputable plan.

**Proposed rule, keyed on declared structure only (for the lead's ruling).**
- **R-a1.** A rule whose heading declares `[compare: cells]` is answered by the cell step alone. Unit plans, judged absences and uncomputable plans never ask it (as today, :1575). This is kept and pinned by a check that a declared rule produces no `uncomputable_refused` row.
- **R-a2.** A SciTab build always carries the declaration. `BENCHMARK_DECLARATIONS` already names it, and K0 is "as shipped" only in its agents, not in its rule headings. So K0 and K1 differ in their agents and steps, never in whether a table claim reaches the legal-text checks. The declaration is written by the operator or the adapter, in the heading's brackets. No code ever infers it from a word, a caption or the presence of a table (the bracket rule; WORDS-A).
- **R-a3.** An undeclared rule keeps today's path and refusals unchanged. If its unit is a table, the refusals stay. In addition, the pairing map counts per document `uncomputable_on_table`: plans whose unit carries a pipe table (`pairing_map._TABLE_ROW`, a structural test) and whose rule declares no comparison. It is a count for the reader, never a re-route. It shows an operator where a declaration is missing and decides nothing.
- **Not proposed:** loosening `_is_figure` or rule 0 for tables. Both would let unverifiable claims through on legal text too, which R1 forbids.

**Development measurement.** G1 SciTab, half A for building and half B only for the read. Two B3 arms on the same 93 claims at the same commit, differing only in the declaration (K0 headings with and without `compare: cells`), scored through `tools/score_corpus.py` `benchmark_items(..., scoring="detection_dev")`. Readouts:
- macro-F1, 2-class;
- the count of `exposed_uncomputable_refused` items, which must go to 0 with the declaration;
- the silence count.

**Expected effect:** from about 0 (K0's undeclared figure) to K1's level on development, a range of 40 to 55 macro-F1. K1 reached 49.3 on the quick subset, and B1 judge_direct 55.8 there; the quick figures are bounds, not targets. Routing creates no new decision power; it only stops discarding answers. **Cost:** the declared arm is K1's build. For the undeclared arm, the development SciTab sessions run about 2.15 USD for 13 tables over 100 minutes (D-634), so 29 tables are about 4.8 USD and 220 minutes per arm on gpu_1x_a10. Half A alone (about 15 tables) is about 2.5 USD. That is above 3 USD in total, so it goes to Seckin with this figure first. The code change for R-a3 is about 1 hour with a check; R-a1 and R-a2 need no code, only one check.

## (b) Decision authority on tables (decision text for the lead's ruling)

**Today.** The cell step asks one narrow question per unit (CELLS-A, CHOICE-A). It shows Python's selected cells and the claim, and decides from the model's next-token probabilities over the answers "holds", "not met" and "cannot be settled" (config/cell_selection.json). Below the measured threshold, on a tie, or with no threshold, the decision is UNSETTLED. That gives the unit the state `uncertain` (`detection.cell_state`), and with no other state the claim is ABSTAIN in 2-class scoring. Only a settled "not met" is a record (`claim_not_met`, INFRA-048), marked as a model's and never an amendment. The record, the decision and its probabilities (`answers[].probability`, `top`, `confidence`, `declared_mass`) stand in the pairing map's `cell_claims` row (`choice_decision.settle`, :126).

**Proposed rule, D-642 (b).** Its wording comes first, then why each standing rule stays intact.

> **TABLE-AUTHORITY-A.** On a rule declaring `[compare: cells]`:
> 1. **The verdict is the model's.** The question shows the cells Python selected (CELLS-A unchanged), and the model's answer is its verdict: "holds" or "not met". It is decided from its probabilities as today (CHOICE-A unchanged: settled above the measured threshold, else unsettled).
> 2. **An unsettled verdict is kept as a leaning, at lowered confidence, never forced to abstain.** When a decision is unsettled because its top answer is below the threshold (`why` = below threshold, never a tie and never "no threshold") and that top answer is "holds" or "not met", the pairing map row records `leaning` = that answer and `leaning_confidence` = its probability. The development scoring reads a leaning as its unit's state, `holds` or `violates`, marked `low_confidence`. A top answer of "cannot be settled", a tie, or a family with no threshold stays `uncertain` exactly as today.
> 3. **Python checks only what it can compute, and only lowers confidence.** Before a verdict or a leaning is read, Python runs two structural sub-steps on the claim and the cells it selected, with no word read for meaning:
>    - (i) **figures found:** every number the claim writes stands in a selected cell, read by the readers the review already uses (`norm_number`; JUDGE-AGENT-A's `locate_figures`);
>    - (ii) **one arithmetic step:** a claim figure that stands in no cell equals the difference or the ratio of two located figures of one row or one column, within the cells' own rounding.
>    
>    A figure that fails both is recorded `figure_unverified`. A settled "holds" with any `figure_unverified` is read as a leaning, which lowers its confidence (rule 2), and the row says why. A sub-step never raises a confidence, never settles an unsettled decision, never turns a verdict around and never writes a record. Python does not decide what the claim's words mean (WORDS-A), so a figure it confirms is no verdict.
> 4. **Records stay as they are.** A record is written only for a settled "not met" (INFRA-048 unchanged), with its cells held to the unit (`CLAIM_CELLS_NOT_IN_UNIT`) and its claim held to the rule (`CLAIM_NOT_THE_RULE`). A leaning and a lowered "holds" write no record, so no finding exists that cites nothing.
> 5. **Scoring.** Under `detection_dev` the class of a claim resting on a leaning is counted beside the settled classes and reported apart (`decided_by: leaning`, its count and its accuracy in their own row). v2_primary and the preregistration's modes are untouched. This is a change to the rule of DETECTION-DEV-A, so it is its own decision, written before any score it changes is read (DETECTION-DEV-A's own clause).

**Why each standing rule stays intact.**
- **UNCOMPUTABLE-A:** not touched. Declared table rules never reach an uncomputable plan (R-a1), and the refusals of `judged_item_refusal` stay word for word for every other rule.
- **CELLS-A:** the selection, its caps, its refusals and the `claim_not_met` record are unchanged. Two additions: the `leaning` fields on an unsettled decision, and the sub-step's `figure_unverified` list. Both are identifiers and numbers only in the pairing map row, as every cell decision is today.
- **CHOICE-A:** "below the threshold the decision is cannot be settled" stays true of the decision. The leaning is a reading beside it, its probability the same number `settle` already records. No threshold is lowered, and a family with no measured threshold still decides nothing and leans nothing.
- **HONEST-OUTPUT-A:** a leaning is a model's, never Python's. It is shown in the deliverables, if anywhere, only under MODEL_FINDING_MARK with its confidence, and it is never promoted. The producer sentence counts leanings apart from settled decisions.
- **The verifiability gate** (`scripts/verifiability_gate.py`, check 75): never weakened. Its fire-set and code are not touched. It downgrades an affirmative finding that cites nothing to UNCERTAIN. This rule makes no new finding: a leaning is no record, and every record it could bear on (`claim_not_met`) still cites its cells and is refused if they do not stand in the unit. Lowering a confidence is the same UNCERTAIN channel the gate uses (genesis Part XXV), and nothing here ever raises one. The build would add one check that check 75 passes unchanged and that a leaning never appears among the gate's inputs.

**Development measurement.** First, at 0 USD from records: the K1-style development runs' cell decisions already carry every answer's probability, so rule 2's leaning can be read off them without a run, labelled what-if. Then a real run of the built rule on G1 SciTab half B. Readouts: macro-F1 2-class, the leaning count, the leaning accuracy and settled accuracy apart, and the ABSTAIN count.

**Expected effect:** +0 to +8 macro-F1 over the same arm without leanings. The ceiling is the share of claims now ABSTAIN with a "holds" or "not met" top answer; D-641's 27 abstentions are on the quick subset and not counted here. The K3 what-if's +10.5 came from a reasoning reply, a different mechanism, so it is no basis for this figure. **Cost:** the what-if is 0 USD and laptop records only (no model). The build is about 4 to 6 hours with proofs and a checker. One G1 SciTab half-B session is about 2.5 USD.

## (d) Cell-grounded reasoning: what SciTabAlign measured, read at source

**Source.** Ho, Kumar, Wu, Boudin, Takasu, Aizawa, "Table-Text Alignment: Explaining Claim Verification Against Tables in Scientific Papers", arXiv 2506.10486 (v1 12 June 2025, v2 17 September 2025, EMNLP 2025 Findings). Read from the arXiv abstract page and the HTML of v2.

**What it measured.**
- **Data:** SciTab's 1,224 claims (457 supported, 411 refuted, 356 NOT ENOUGH INFO). NOT ENOUGH INFO is excluded. After the authors' annotation and filtering, 372 claims remain (195 supported, 177 refuted), each with human-marked minimal cell rationales. Agreement on 50 tables (137 claims): cell precision 75.2, recall 89.1, macro-F1 78.0. A five-way taxonomy of ambiguous cases: conversion errors, extra context needed, unexpected claim types, subjective adjectives, unclear claims.
- **Models:** TAPAS base and large; Qwen 2.5 7B and 72B; Llama 3.1 8B and 70B (instruction-tuned); GPT-4o on 100 samples. Zero-shot, few-shot (four demonstrations) and chain-of-thought, with pipe-encoded tables. Claim labels scored by 2-class macro-F1, cells by macro-F1 over (row, column).
- **Claim labels without cells as input (zero / few / CoT):** Qwen 2.5 7B 66.3 / 68.1 / 67.9; Llama 3.1 8B 53.2 / 59.5 / 62.4; Qwen 72B 83.5 / 84.7 / 81.5; GPT-4o 88.4 / 87.0 / 88.0.
- **The models' own cell selection** (macro-F1, zero / few / CoT): Qwen 7B 20.7 / 16.6 / 17.0; Llama 8B 23.6 / 22.3 / 22.6; Qwen 72B up to 50.8; GPT-4o 32 to 35. Few-shot and CoT help the small models' labels but hurt their cell selection.
- **Gold cells as input (zero-shot only; table / cells only / table plus cells):** Qwen 7B 66.3 / 67.5 / 69.8 (+3.5); Llama 8B 53.2 / 56.9 / 63.0 (+9.8); Llama 70B 75.2 / 80.1 / 80.9 (+5.7); Qwen 72B 83.5 / 80.6 / 81.9 (-1.6). Only gold cells were fed in; no setting fed a model its own predicted cells back. With exact-match cells, the CoT runs of the 7B and 8B models had 0.0 percent of claims both right in label and right in cells.

**How it maps to the cell step.**
- The gain the paper reports for 7B to 8B models comes from **correct cells given as input**, not from asking the model to name cells first. Its own measurement says the small models name the wrong cells (17 to 24 macro-F1) and are right on the label without being right on the cells.
- So "the model reasons from cells it names" (D-642 (b)) is not supported by this paper at our size. What it supports is our existing order: **Python selects the cells, then the model gives the verdict on them**. That is CELLS-A's step, the paper's "table plus explanation" condition, with Python's selection in place of the gold cells.
- Our selection is shown the claim's own figures and words, so its recall against human rationales is the number that decides whether the paper's +3.5 to +9.8 can transfer. That recall has never been measured: SciTab's key states no cells (CELLS-A). SciTabAlign's rationales are the first key that does.
- Two cautions:
  - The paper's models are Qwen and Llama; our judge on a narrow task is Phi-4 (JUDGE-AGENT-A) when declared, else the rule's agent, and the paper says nothing of Phi.
  - Its data are SciTab claims, the same source as our gate and G1 sets, so any use needs LEAKAGE_PROTOCOL first. Its claims may sit in our gate set. Its rationales may be used only to score our selection on items the leakage check keeps out of every gate set, never for tuning.
- **Proposed form (for (b)'s build):** keep "Python's cells, then the verdict". Add the whole table beside the selected cells only if the measurement below shows it helps, since the paper's best small-model condition is table plus cells.

**Development measurement.**
1. **Selection recall, 0 USD, laptop, no model:** run `cell_selection` (no embedding, as `doc_judge.select_cells`) on the SciTabAlign claims the leakage check admits, and score cell recall, precision and F1 against their rationales. This needs the licence read and LEAKAGE_PROTOCOL's split (role B's side) first.
2. **Form, on G1 SciTab rows:** one replay pass with the cell question in two forms, selected cells alone (today) and the table plus the selected cells, judged by the same model. Read 2-class macro-F1 for each and the paired difference.

**Expected effect:** +0 to +4 macro-F1 from the table-plus-cells form if our selection's recall is near the paper's agreement level, and none or negative if recall is low. The paper's +3.5 is for Qwen 7B with gold cells, an upper bound for us. **Cost:** step 1 is 0 USD and about 2 hours after the licence and leakage checks; step 2 is one replay launch of about 1 to 1.5 USD on gpu_1x_a10 (93 claims, two forms) and about 2 hours of work.

## Order and totals

1. (a) R-a1 and R-a2's check, plus R-a3's count: about 1 hour, 0 USD. The declared-against-undeclared measurement is about 4.8 USD a full arm, so it goes to Seckin before spend (D-642: spends above 3 USD reported first).
2. (b) the leaning what-if from records: 0 USD. If it shows a gain, the TABLE-AUTHORITY-A build (4 to 6 hours) and one half-B session (about 2.5 USD).
3. (d) selection recall after the licence and leakage checks: 0 USD. Then the form replay: about 1 to 1.5 USD.

Nothing here touches a bound controller file. Every change is runtime source, so any bundle sealed before it lacks it and is re-sealed for the next read.

## Addendum, 15 November 2026 (lead's 15:40 instruction): scripts prepared, licence and leakage read (text only)

**Scripts, prepared and not run** (each has a `--self-test` on invented records, which passes; no measurement was made):
- `tools/scitab_leaning_whatif.py` (b). Given `[{key, run}]` pairs of G1 SciTab development runs, it copies each run folder to a temporary folder and rewrites the copy's pairing-map cell decisions by one rule, `leaned`. An unsettled decision becomes a leaning only when its reason is `choice_decision.BELOW_THRESHOLD`, and its top recorded probability (no tie) is "holds" or "not met". Both the original and the copy are labelled by the scorer's own route (`score_corpus.benchmark_items`, detection_dev). It prints 2-class macro-F1 as read and with leanings (`judge_read.macro_f1`), the ABSTAIN counts, the items moved and the moved-and-right count. It prints no id and no gold. It is labelled "what-if from records, not a system run".
- `tools/scitab_selection_recall.py` (d). It runs Python's selection with no embedding on each SciTab-shaped record's text, as the adapter builds it (`part_text`), and scores the selected rows by columns against `rationale_cells`: mean precision, recall and F1, and how many claims show every rationale cell. It refuses without role B's exclusion file and prints counts only. The mapping from SciTabAlign's data.zip to those records (field names, index base) is written only when role B opens the archive. A rationale index outside its table refuses the run rather than being guessed.

**Licence (read at source, text only; no data downloaded).**
- SciTabAlign: MIT, "Copyright (c) 2025 Alab-NII" (LICENSE in github.com/Alab-NII/SciTabAlign). The data are not in the repository: the README points to two Dropbox archives (`data.zip`, `outputs.zip`) and states no separate data licence. Read as covered by the repository's MIT licence, with that gap stated.
- SciTab: the repository github.com/XinyuanLu00/SciTab is MIT, with no separate data terms.
- Use here: an internal development measurement with attribution kept, nothing redistributed or published. Before any publication, the data's own terms are asked of the authors.

**LEAKAGE_PROTOCOL, applied by its text.**
- SciTabAlign's 372 claims are SciTab claims: the same source, papers and tables as our G1 rows and the gate set. The rationales would be read only to score Python's selection, never to tune it and never as a judge's input.
- Even so, no lead-side session may learn which SciTabAlign items fall in the gate or quick sets, since a kept or excluded list would reveal gate membership. So the measurement runs wholly on role B's side, as the protocol's step 4 runs every check:
  - role B opens the archive in its own folder;
  - it drops every claim whose paper or table is in its exclusion file (the gate set, the quick subset and their papers: rule 4, a group going whole);
  - it runs `scitab_selection_recall.py` and returns the counts and averages alone.
- Rules 1 to 3 (exact, 8-word runs, cosine) need no fingerprint here: a SciTabAlign claim is the same SciTab item by id and paper, so rule 4 alone decides its side.
- What is not caught: a SciTabAlign claim the authors revised wording of ("Revised", 81) still carries its SciTab ids and is excluded by them. That is stated, not a gap.
- **Needed before go:** a role B request (as GATE_SET_ROLE_B_REQUEST.md) naming the archive's URL, this tool's commit and the output's fields.

## Addendum, 16 November 2026: TABLE-AUTHORITY-A built (lane/tables-d642); the D-646 what-if; the half A run's plan

**Built (checks 480 to 484, docs/CLAUDE_REFERENCE.md#table-authority-a).** Rules 1 to 5 of (b) above, as written, with two clarifications:
- Rule 3's "two located figures" is read as any two figures of one shown row or one shown column, since a claim's computed figure is usually not itself in a cell.
- "The cells' own rounding" is read as interval overlap: each figure stands for its last written place, plus or minus half a unit.

D-642 (d), cell-grounded verdicts, is built inside the same rule:
- When the table tool request runs (TABLE-TOOL-A, still off), the judge's cited cells are the cell ids in its request.
- A cited cell the table does not hold lowers the verdict, and so does a verdict that cites no cell.
- With no request, as shipped, the verdict rests on Python's selected cells. That is the paper's best small-model condition, read at source ((d) above).

**Task wording against the design.** The lane's task said "where Python can decide a cell claim by arithmetic, Python's decision outranks the model's".
- Python never decides the claim. It decides only the sub-step it can compute: whether each written figure is in a shown cell, or one step away.
- Where that sub-step fails, its result outranks a model's "holds" by lowering it.
- This follows D-642 (b) ("Python verifies only the sub-steps it can compute; where it cannot decide, it lowers the confidence") and WORDS-A.
- D-593's two arithmetic designs, which let Python choose the computation, failed their bar and stay off.

**As shipped nothing moves.** `config/semantic_thresholds.json` holds no `cell_claim` threshold, so the cell step asks nothing and no leaning can exist (rule 2 never leans on "no threshold"). The rule acts only in a development bundle that declares K1's .6 (D-477), or after a threshold is adopted under CHOICE-A.

**The D-646 what-if, from saved replies, 0 USD.**
- Inputs:
  - the cell question's own decisions in judge 2e's base pass (`external/s05/T2E/ev_F/evidence/b1/train/passes/base`, 4,894 replies, half A only);
  - the shipped prompts file (`external/s05/T2E/choice_prompts_r1_shipped.json`), read for ids, benchmark and order-control flags only;
  - K1's threshold of .6.
- Tool: `tools/scitab_leaning_whatif.py --replies PROMPTS RUN`. It refuses any half B row (D-296, D-649) and prints counts only, with no gold.
- What is left: the two macro-F1 figures, side by side, need G1's keys, which were lost on 16 November (D-704, D-705).
  - The keys must be rebuilt (adapter build over `external/scitab/dev` and `external/contradoc/dev`).
  - They must be proven equal by `g1_bar_items.json` `keys_sha256` before `--key` is given. The tool refuses any other key set.
- Recorded figure without leanings (D-477, the same pass and threshold): 45 claims, macro-F1 .703, accuracy .578.
- **Counts read on 16 November** (no gold; 15 half A tables, 45 claims, the 47 order controls set aside):

  | Reading | supports (CLEAR) | refutes (FLAG) | not settled (UNDECIDED) |
  |---|---|---|---|
  | as read | 18 | 10 | 17 (10 below the threshold, 7 settled as "cannot be settled") |
  | with leanings | 20 | 16 | 9 |

  - 8 claims move: 2 to supports and 6 to refutes. Every leaning's probability lies between .4 and .6.
  - The counts as read match D-477's record (10 flagged). Under 2-class an UNDECIDED claim is a miss, so the 8 moved claims bound the effect. Accuracy can only move between .578 (all 8 wrong) and .756 (all 8 right).
  - Which one it is needs the gold, through the scorer.

**The paid run on half A (D-646; approved at 2.5 USD on half A by D-649). Plan written, not launched.**
- **Arm:** B3 at this lane's commit, plus a development bundle that declares:
  - `cell_claim` .6 (K1, D-477), never merged into the product;
  - `[compare: cells]` (R-a2).
- **Items:** G1 SciTab half A, 15 tables and 45 scored claims, rebuilt and proven by digest first.
- **Readouts:**
  - macro-F1 2-class with leanings and without, side by side;
  - the leaning count, and the leanings' accuracy apart;
  - the ABSTAIN and UNDECIDED counts;
  - the `figure_unverified` count.
- **Cost without saving measures** (old path; D-634's 7.7 instance minutes a table at 0.0215 USD a minute on gpu_1x_a10):
  - workload 15 x 7.7 = 116 minutes, plus the launch's fixed 18 minutes: about 134 minutes, about 2.9 USD;
  - the route S seal: about 0.46 USD (half of A5's 0.92 for two seal jobs);
  - **total about 3.3 USD.** This is above the 2.5 USD approval and the 3 USD line, so it is not launched in this form without Seckin's word.
- **Cost with saving measures** (SPEED_PLAN_V1 rank 1, vLLM routing for the local generations if A5 passes; rank 4, image layers instead of the asset copy):
  - workload about 116 x 0.6 = 70 minutes, plus a fixed part of about 14 minutes: about 84 minutes, about 1.8 USD;
  - plus the seal: **total about 2.3 USD**, inside the approval.
  - If A5's vLLM result is void, only the image layers apply: about 3.2 USD, again above the approval, so it goes to Seckin first.
- **Order:**
  1. G1 rebuilt and proven.
  2. The what-if's two figures read.
  3. This run, by the lead, after the full gate on Lambda passes at this commit. Runtime source changed, so the bundle is re-sealed.
