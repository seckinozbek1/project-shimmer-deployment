# Two reasoning methods on ContraDoc and SciTab: the development measurement (D-713, document review half)

Written 16 November 2026 by lane/reason-docreview. A plan for the lead to approve and launch. Nothing here has run;
the lane launched nothing, built no prompts file from real workloads and opened no key.

## What it measures

Whether either of D-713's two methods, built in `benchmark/baselines/reasoning_methods.py` (REASON-METHODS-A), moves
the judging path's figures toward the bar without raising the dropped-answer rate, on the two choice questions:

- **ContraDoc, `pair`**: do two passages of one document contradict each other (Yes, No, Unclear);
- **SciTab, `claim`**: do the table cells Python selected show that a claim holds (Yes, No, Unclear).

Three groups on one model, Phi-4 4-bit base (`unsloth/phi-4-bnb-4bit`, C's candidate), each asked the same questions:

| Group | Calls a prompt | What it is |
|---|---|---|
| `choice_direct` | 1 choose | the form itself, byte for byte (C base's question) |
| `choice_reason_first` | 1 generate (at most 96 tokens), 1 choose | rationale in a fixed field, then the label from probabilities |
| `choice_stepwise` | 1 generate (at most 96 tokens), 2 choose | evidence (cell ids or two quotes, checked), comparison, label |

The direct group rides every launch as that launch's own control, so each method is compared with direct on the
same machine, session and documents (FACTORS-A: no cross-machine-type comparison).

## Items: development only

Half A of C_BAR's split, as `external/s05/P2A/choice_prompts_r1.json` holds it (D-280; counts from DECISIONS.md, to
be confirmed from the file at build time and written beside the prompts' digests):

- ContraDoc: 30 documents, their top-40 pairs in both orders, **2,400 pair prompts** (80 a document);
- SciTab: 15 documents, **47 claims**.

Half B is never built, launched or read here. No `order_control` prompt is built (a method group refuses one). Two
development sets, as D-710 item 2 asks for any adopted change: ContraDoc half A and SciTab half A.

## Building the prompts (laptop, no model, no key)

`choice_judge.py build --pairs-from external/s05/P2A/choice_prompts_r1.json` (the very pairs, nothing encoded again)
plus `--claim-workload`/`--claim-items` for half A's SciTab workloads, with `--config` a copy of
`benchmark/baselines/choice_methods_prompt.json` keeping ONE group per prompts file (three files per part), since
`choice_read.load` reads one candidate per pass (open item 143 (b)). Each file's digest and its config digest are
written into the request before sealing. Parts are cut by whole documents.

## Time and money (forecasts; the A10, `gpu_1x_a10`, 1.29 USD an hour)

Per prompt, from saved evidence: a choose call is **0.36 s** (C base, 7,340 choice prompts on the A10). A generated
step is forecast at its cap: 96 tokens at an assumed 10 tokens a second for Phi-4 4-bit, about 9.6 s, plus the
prompt's prefill, so **10.4 s** for reason_first and **10.8 s** for stepwise. Measured replies stop on the model's own
stop token and are usually shorter, so these are upper figures; the pilot measures them. Launch to ready with the
filesystem copy: about 15 minutes (L12, C1); with the model load, collection and teardown, **20 minutes** of overhead a
launch. All three groups a prompt: 0.36 + 10.4 + 10.8 = **21.56 s**.

| Step | What | Prompts a group | Model time | Billed | Forecast USD | Cap (1.5 times) |
|---|---|---|---|---|---|---|
| 1 (pilot) | SciTab half A (47 claims) + ContraDoc half A, 4 documents | 47 + 320 | 132 min | 152 min | 3.27 | 4.90 |
| 2 to 7 | ContraDoc half A, 4 documents each (24 documents) | 320 | 115 min | 135 min | 2.90 each | 4.35 each |
| 8 | ContraDoc half A, the last 2 documents | 160 | 57.5 min | 77.5 min | 1.67 | 2.50 |
| **All** | 47 claims and 2,400 pair prompts, three groups | | | | **22.34** | |

Every step is within the 5 USD per-step pre-approval (D-708; each forecast is also within PARALLEL-LAMBDA-A's 3 USD
move but step 1, 3.27 USD, which is within D-708's 5 USD). Steps 2 to 8 are independent and run at the same time on
seven machines (PARALLEL-LAMBDA-A); the spend is then about 22 USD of the remaining limit (config/loop_spend_limits.json,
read at call time by the guard).

**Expected finish times, back to back (BACK-TO-BACK-A):** build and seal about 40 minutes after approval; step 1 about
2.5 hours after its launch; the pilot read 15 minutes; steps 2 to 8 in parallel about 2.3 hours; the read and the
adoption verdict 30 minutes. About 6.2 hours from approval to the verdict.

## The pilot gate (after step 1, before steps 2 to 8)

Read from step 1 alone, a stop rule only, never the adoption: a method's steps 2 to 8 are not launched (and its
share of the spend saved) when (a) its dropped-answer rate on step 1 exceeds direct's by more than 10 percentage
points, or (b) more than half its generated steps reached the allowance (the model is not stopping; the fixed field
is then not one line). Either is reported with its counts. A forecast that the pilot's measured seconds raise above 5
USD for a part is re-cut into smaller parts before launch, never run over.

## What is read

- **Figures.** Per benchmark on half A, what `choice_read.py` reads for a candidate (C_BAR.md): ContraDoc at the
  document (a pair flagged when both orders put contradicts on top at or above the threshold; FLAG when any pair is
  flagged), SciTab at the claim; FLAG precision, recall and F1 and accuracy, ABSTAIN counted wrong. The threshold is
  set on half A by C_BAR's own rule, for each group the same way.
- **Dropped-answer rate.** `reasoning_methods.dropped` over the measurement rows: the prompts with no decision (a
  failed call by its kind, a refused step by `<step>:<reason>`) over the prompts asked, per group and benchmark. A tie
  at the label is a decision (unsettled), as on the direct form.
- **Beside them.** Seconds and output tokens per step, USD per launch, the share of generated steps at the allowance,
  for stepwise the refusals by reason (`no_cell_named`, `cell_not_shown`, `too_many_cells`, `quote_missing`,
  `quote_not_found`, `quote_not_content`, `comparison_tie`, `prompt_over_context`), and the declared mass of the label
  step against direct's.

## The adoption rule (D-713)

A method is adopted only if, on **both** development sets, it moves the figures toward the bar and does not raise the
dropped-answer rate. In code, `reasoning_methods.adopt(direct, method, bar)` with `bar` the per-figure floors taken
from C_BAR.md's bar file and written into the read before any figure is read: on each set no figure moves away from
its floor, at least one moves toward it (for a figure direct already holds at or above its floor, one that rises), and
the method's dropped-answer rate is not above direct's. Time and USD are reported beside the verdict, never a
condition. A method adopted is then a decision for the lead: it applies to the next seal only, and is wired into the
pipeline's own route with its own check (open item 143 (a)). Repeated sampling with a majority vote is not tested
(D-713, not now).

## Bound files: change only as part of a planned re-seal

The method code rides the replay pass, so it reaches an instance only in a bundle sealed at a commit holding it.
No sealed or running measurement changes; the measurement's bundles are new seals. Files this lane changed that
travel in every sealed bundle:

- `benchmark/baselines/doc_judge.py` (`check_config` reads the methods block; `load_prompts` refuses an order control in
  a method group; `run` runs a method group's chain and writes its step records);
- `benchmark/baselines/reasoning_methods.py` (new);
- `benchmark/baselines/choice_methods_prompt.json` (new, the measurement config);
- `scripts/verify_session1.py` (checks 475 and 476).

Not bound: `tools/reasoning_methods_checks.py`. Unchanged: the controller, the bound wrapper, the guard, the sealer,
the runner (`tools/ordinary_final_run.py`'s one record per prompt holds), `choice_judge_prompt.json`, `choice_read.py`
and `bare_model.py`. No CONTROLLER-BINDING file changed.
