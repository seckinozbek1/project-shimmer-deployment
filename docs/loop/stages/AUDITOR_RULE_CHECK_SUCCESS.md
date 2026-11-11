# The auditor rule check: success rule and progress minimum (D-S72, D-324)

Written 8 November 2026, before the first training attempt and before any trained or untrained
decision on these questions has been read. A fresh checker attacks it with the other lanes' rules
before any launch (D-S72 item 2). Development, exposed: nothing here is the fresh set or sealed
material, and neither ever feeds this part.

## 1. The part and what is compared

- **The part.** The auditor backend's rule check (`config/auditor_questions.json` `rule_check`, frozen
  at 4714d4ed, question digest `4c8959d337a6a89d427cf9c67af58a6e9959e12e32e99cda5b66b650d516cd2a`):
  one narrow question on a rule's own words and one unit's text, answered Yes (met), No (not_met) or
  Unclear (cannot be settled) from the model's choice probabilities, no text written.
- **The untrained form.** `unsloth/Phi-3.5-mini-instruct-bnb-4bit` at revision `5c20803a`, the model every
  local_auditor role runs on, with no adapter: the `base` pass of the session.
- **The trained form.** The same base with one adapter of the session (`dev_mix` or `permissive_mix`,
  at `trained_half` or `trained_full`), chosen on half A alone (section 3). Publication follows the
  operator's rule (D-281): a `dev_mix` adapter is measured and never shipped; the shipped candidate is
  `permissive_mix`.
- **Both read the same way**, as the product would ask them: `bare_model.LocalBackend.choose`, the
  rendering and scoring of `agent_wrapper.call_choice`, on prompts each proved byte for byte the
  driver's own call on its unit and rule (check 333). L-3: training in the run-time form is the change
  this attempt makes; the rows and the questions carry one question digest.

## 2. The questions and the held-out part

- **File.** `external/train_auditor/questions/rule_check_dev.json`, sha256
  `9dbd82f2eba994f3e6ba122ceb4df45ca97346f4f25c3538e73200304c3ae97e`, built by
  `tools/build_auditor_questions.py` from ContractNLI's development split (read before in L4b, never its
  test split, never a training row; `auditor_train.check` refuses a question that is a row). 789
  questions: the evidence units of an entailed or contradicted hypothesis (met, not_met) and every unit
  of a not-mentioned one (cannot be settled).
- **Halves, by document** (the SHA-256 of `20261108:` and the document id):
  - **Half A, tuning:** 398 questions, 31 documents (158 cannot be settled, 146 met, 94 not met).
    Digest of its sorted (question_id, user_sha256, answer) list:
    `06154dae7b74ceda544f5a0d67b645dbe88387381f5ff11878666ff25b2cbff5`.
  - **Half B, held out:** 391 questions, 30 documents (142, 154, 95). Digest
    `b5a47e9625c8866cec1685ffa4dd445b13d43a7b837da1c9c2d2fba2b79b9d6e`.
- **What "no attempt is tuned on half B" means here.** The session computes decisions on both halves
  (one pass over the file). Every choice is made on half A only: the adapter and checkpoint, the
  decision threshold, and every later recipe. Half B is opened only by the success read below, once per
  attempt that has passed its half-A margin, and what it gives the next recipe is pass or fail only,
  never which items and never a reason to change a setting (L-4: an effect chosen on the data that
  measures it misleads; D-330).
- **The guard is in the scoring, not in the run (D-330 item 2).** The session computes decisions on both
  halves, so nothing in the run can keep half B unread. `benchmark/baselines/auditor_read.py` is the one
  reader: `read-a` drops half B's rows where the decision files are read, before any figure is formed,
  and writes the half-A record; `read-b` refuses before reading any half-B row unless the COMMITTED
  `docs/loop/HELDOUT_OPENINGS.md` at the repository's HEAD holds the opening's row (this part, the
  attempt and the candidate, half B's digest, the commit of the half-A record) and that record, as
  committed there, shows half A passed for the same attempt, the same decision files and the same
  candidate. Proved in check 333 with five neutralisations (no committed row, an uncommitted register, a
  failed half A read as passed, a fixed test level, half A mixing in half B's rows).
- **Held out by document, not by rule: the limit, stated (D-330 item 3).** Half B shares ContractNLI's 17
  hypotheses (the rules) and the agreements' near-duplicate boilerplate with half A. Splitting by rule as
  well was weighed and not chosen: crossing the document split with a rule split leaves about half of
  each half usable (a quarter of the whole), about 47 not_met questions in half B, below what criterion 3
  and the bootstrap need at the halved test level. It is also less needed here than for the judge: no training row comes from
  ContractNLI (the mix is MultiNLI, WANLI and TabFact), so training cannot have learnt these 17 rules;
  only the choice of adapter and threshold reads half A. So every success of this part is stated with
  this sentence beside it: "held out by document; half A and half B share ContractNLI's 17 rules and its
  boilerplate, so the gain is not shown to hold on rules unseen at selection".

## 3. Measures, written before any read

- **Primary: macro-F1** over the three answers, on each question's top answer (no threshold), the
  same for both forms.
- **The product's measure beside it: not_met precision at the threshold.** A record is written only on
  a settled No, so the record's own error is a wrong No. The threshold is the lowest value of
  `{.50, .55, ..., .95}` at which half A's not_met precision is at least .80 with at least 10 settled
  No answers; none such means "no usable threshold" for that candidate.
- **Selection on half A:** the candidate with the highest half-A macro-F1; a tie goes to
  `permissive_mix`, then to the earlier checkpoint.

## 4. The success rule (the one stopping rule, D-S72 item 2)

The part succeeds, and its attempts stop, only when all of these hold:

1. **Margin on half A.** The selected candidate's macro-F1 is at least **.05** above the untrained
   form's on half A.
2. **The gain holds on half B.** On half B the same candidate's macro-F1 is at least **.05** above the
   untrained form's, and the gain is above 0 at the opening's level: the k-th opening of this part's
   half B (counted in `docs/loop/HELDOUT_OPENINGS.md`) is tested one-sided at alpha **0.05 / 2^k**, so
   however many attempts the part takes the chance of any false success stays at most 0.05 (D-330 item
   1). The test is a document-cluster bootstrap of the gain (2,000 resamples of half B's 30 documents,
   seed 20261108): its alpha-quantile must be above 0. Questions of one document are not independent, so
   documents are resampled, not questions.
3. **No worse record.** At the threshold fixed on half A, half B's not_met precision is at least .80 on
   at least 10 settled No answers, and not below the untrained form's precision at the untrained form's
   own half-A threshold. When the untrained form has no usable half-A threshold, or settles no No on half
   B at it, there is nothing to be below: the floor alone decides, and the result says
   "untrained threshold not usable" beside it (D-330 item 4).
4. **The publishable candidate.** If the selected candidate is `dev_mix`, `permissive_mix` must meet 1 to
   3 as well before anything ships; otherwise the operator is told (D-281). Its half-B read is an opening
   of its own, a row of its own in `HELDOUT_OPENINGS.md` with the next k, and tested at that level.

A pass is reported with the attempt number beside it (D-S45 item 7). Meeting it changes nothing in the
product by itself: adopting `form: decision`, with the threshold written to
`config/semantic_thresholds.json` (`auditor_rule_check`), is a recorded decision afterwards.

**Power, stated plainly (L-4).** No out-of-sample effect exists yet, so no power figure is claimed. With
30 held-out documents a real gain of about .05 may fail criterion 2; such a result is reported as "not
shown at this size", never as no gain.

## 5. Per-attempt real-progress minimum (D-S72 item 3)

An attempt is real progress only if its selected candidate's **half-A macro-F1 is at least .02 above
the best earlier attempt's** (the first attempt is measured against the untrained form). Half A, because
half B is read only for success and must not steer the series. An attempt below that is reported in
FOR_SECKIN with a push (what was tried, why it did not work, from the records, and what the next attempt
changes), and the loop goes on by itself.

## 6. The published level (D-S73) and the search behind it

D-S73's target table is built for SciTab and ContraDoc (the judge). The search record for this part
(8 November 2026, one web search, "LegalBench contract_nli tasks excerpt hypothesis entailment results
open models"):

| Nearest task | Source | Date | How it differs from this question |
|---|---|---|---|
| ContractNLI | Koreeda and Manning, Findings of EMNLP 2021 (the arXiv id was not checked in this search) | 2021 | Document-level: the whole agreement is the premise, three labels per hypothesis, evidence as spans; no question is asked of one part alone. |
| LegalBench `contract_nli_*` tasks | Guha et al., LegalBench, NeurIPS 2023 Datasets and Benchmarks (arxiv.org/pdf/2308.11462v1); data at huggingface.co/datasets/nguha/legalbench | 2023 | The closest: one excerpt of an agreement and one hypothesis, answered per excerpt, which is near this part's unit and rule. But two answers (Yes, No), no Unclear, excerpts chosen to hold the evidence, no part that leaves the hypothesis unsettled, and few-shot prompts with generated answers. |
| Small open models on LegalBench | arXiv 2603.25944 (2026), nine 3B to 9B models, seven open-weight | 2026 | Same tasks as LegalBench; its contract-entailment scores were not retrieved in this search, so no figure is quoted here. |

So "no published counterpart" is corrected: LegalBench's `contract_nli_*` tasks are a near counterpart
at the excerpt level, in a different setting (binary, evidence excerpts only, generated answers). This
part's success is judged against its untrained form, as above; a LegalBench figure may be printed beside
it only labelled "different setting: two answers, evidence excerpts only", never as a like-for-like
claim. If the lead holds that D-S73 binds this part, the LegalBench scores of comparable open models
have to be read from the papers above and attacked before the first attempt.

## 7. What is fixed before the first attempt

The question digest, the questions file and both half digests above, the margins (.05, .02), the
precision floor (.80 on at least 10), the threshold grid, the bootstrap (2,000, seed 20261108, by
document), the test level 0.05 / 2^k with k from `HELDOUT_OPENINGS.md`, the selection rule and the tie
order, and the reader `benchmark/baselines/auditor_read.py` with these constants in it. A change to any
of them is a new rule, written and attacked again before the attempt it governs.
