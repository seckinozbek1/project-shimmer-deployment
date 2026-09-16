# Auditor relation-failure diagnosis and one next experiment design

Date: 2026-09-16. Local analysis only. Historical result: `AUDITOR_TUNING_FAIL` remains final and immutable. Results commit `7ab6ec62de9ad4ed0469d6cfa7453fbea3e76cbd`; tested execution commit `3dd892dcdb9c1be6d26cb1a4ba63d6acaaa81471`. Neither checkpoint is selected. Producer checkpoint168 remains preserved and unexecuted; protected receipt remains unconsumed.

**Readiness: `AUDITOR_NEXT_EXPERIMENT_READY` — design readiness, not execution authorization or a passing Auditor.** Select one frozen-representation, five-way classification-head experiment with a frozen refusal gate and class-conditioned explanation. A label-only patch to saved outputs is not sufficient.

## 1. Evidence, scope and method

Inputs are the canonical Auditor-only 300-row export, its 240 TRAIN / 60 DEV split, saved raw and scored checkpoint60/120 outputs, the executed training schedule/log, and local source/config/tokenizer files. All 143 text-file hashes in the historical evidence manifest were verified before analysis. Raw records match the corresponding scored records after removing the saved `metrics` field; predicted classes are independently parsed from saved JSON. Historical scoring is not replaced or reinterpreted. No historical file is modified.

Reproducible arithmetic and row-level records: [diagnosis.json](auditor_relation_diagnosis/diagnosis.json); local analysis tool: [diagnose_auditor_relations.py](../../tools/diagnose_auditor_relations.py). The tool loads the cached pinned tokenizer only, with model frameworks disabled and offline flags enabled. No model weights, protected targets, other folds, or Producer execution are needed. Analyst semantic annotations are explicitly separate from saved scorer fields; this is not an independent blinded or human review.

Important scorer limitation: `tuning/second_domain_agnostic_v2/runtime.py:145` marks a non-refusal reason correct only when it exactly equals the target reason; otherwise it stores **null**, not a semantic judgment of false. Acceptance at line 146 requires that field to be true. The manual comparisons below distinguish exact-match failure from an actually false or incomplete explanation. All 32 failed outputs have a substantive explanatory defect, not merely a harmless paraphrase mismatch. “Evidence correct” means the required reference-ID set is correct; it does not establish that the textual argument is supported by those references.

## 2. Current canonical result and reconstructed confusion

Class order throughout: MATCH, DIVERGENCE, OMISSION, ADDITION, INSUFFICIENT_EVIDENCE. Each expected class has 12 DEV rows. Appendix A lists all 25 expected/predicted cells per checkpoint with counts and exact row IDs, including zero cells.

| Measure | Step60 | Step120 |
|---|---:|---:|
| Prediction distribution in class order | 1, 8, 39, 0, 12 | 8, 3, 0, 37, 12 |
| Dominant class | OMISSION, 39/60 | ADDITION, 37/60 |
| Shannon prediction entropy, bits | 1.354387 | 1.498154 |
| Class diversity | 4/5 | 4/5 |
| Correct class decisions | 27/60 | 29/60 |
| Wrong substantive class decisions | 33/48 | 31/48 |
| Accepted outcomes | 19/60 | 28/60 |
| Macro relation F1 | 0.377043741 | 0.434965986 |
| Evidence F1 | 1.0 | 1.0 |
| Refusal precision / recall | 1.0 / 1.0 | 1.0 / 1.0 |
| Confident-wrong MATCH/DIVERGENCE | 5 | 4 |

Entropy uses all 60 class predictions, base-2 logarithms, and zero-count terms omitted; maximum five-way entropy is 2.321928 bits. Neither checkpoint exhibits refusal collapse: exactly 12/60 refusals, all correct. The class collapse moved between two substantive labels.

## 3. All step120 failures and relation/reason decomposition

There are **32 nonaccepted rows**, comprising **31 wrong relation decisions** and **one correct relation with an incorrect reason**. Appendix B contains every failed row, exact references, expected and generated reasons, source/extraction, and all requested diagnostic flags.

| Category | Definition | Count |
|---|---|---:|
| A | Complete semantically correct explanation, wrong relation label only | **0** |
| B | Wrong relation and a reason that rationalizes that wrong relation or misses the actual change | **31** |
| C | Correct relation but failed reason | **1** |
| D | Wrong evidence-reference selection | **0** |
| E | Other failure | **0** |

The A/B partition covers the 31 wrong substantive labels; C is the additional failed row 156. This avoids putting a correct-label example into the “wrong predictions” denominator. Evidence and refusal/status are correct on all 32 failures. Literal class-token mapping failures: **zero observed**. The reasons consistently use the language of their predicted class. That rhetorical consistency is not source-grounded support. Row156 does identify a DIVERGENCE at the relation-type level, but reverses its direction.

Examples of distinct mechanisms:

- False unsupported additions: row046 calls two qualifications additions although both occur in source and extraction; it ignores the pulses-to-boxes mutation.
- Direction reversal: row047 calls the missing source sentence an extraction addition.
- Semantic category confusion: row141 describes an unknown-to-known replacement as an addition and falsely says every original qualification remains.
- Structural text treated as a fact: row160 calls the extraction-only “End annex qualifications.” a substantive addition despite the explicit structural-heading clarification.
- False preservation: row142 says uncertainty was retained although it was omitted.
- False replacement: row138 turns two existing claims into an invented replacement and misses the newly asserted inspector verification.
- Correct class, reversed reason: row156 describes clear-to-unclear; source and extraction show unclear-to-clear.

This is a semantic comparison problem coupled to an unstable generative class decision. The saved outputs do **not** show a competent hidden explanation waiting for a label remap. A classifier is an experiment to isolate supervision and decision-making, not an already-proven repair.

## 4. Orientation audit

Frozen instruction in `scripts/compact_contracts.py` begins: “Compare ORIGINAL with EXTRACTION for fidelity, not one original figure against another.” It defines MATCH as preservation, DIVERGENCE as changed content, ADDITION as unsupported content, and OMISSION as missing content. The V2 addition in `runtime.py:55–58` explicitly says complete delivery with identifiable missing propositions is OMISSION and structural headings introduce no new facts. The prompt carries separate `source_spans` and `extraction` fields. Targets say “The extraction replaces [source] with [candidate]” or “The complete, delivered extraction omits the source content …”. There is no evidenced source/candidate-orientation ambiguity in these instructions or targets.

The definitions alone are short, but that does not imply ambiguity: field names, the initial comparison instruction, and directional target wording resolve the reference side. No labels or definitions are changed here.

Exact counts, distinguishing label coincidence from a full directional account:

- **10** OMISSION→ADDITION errors become class-correct under a label swap. Of 37 ADDITION predictions, these are the only 10 whose expected class is OMISSION. The other 27 comprise 10 correct ADDITIONs, seven MATCHs, and ten DIVERGENCEs.
- **5** wrong-label reasons fully match a reversed comparison: IDs **047, 137, 152, 157, 162**. They identify the exact omitted material but describe it as added. This is orientation-consistent evidence, not proof of the model's internal cause.
- **2** more wrong-label reasons contain a reversal-compatible fragment: **277, 282** identify one of two omitted qualifications. Even after reversal their accounts are incomplete.
- **3** remaining OMISSION→ADDITION errors, **052, 057, 272**, call retained material an addition. Reversal does not explain their reasons.
- **1** reason-only error, **156**, exactly reverses a replacement while retaining the correct DIVERGENCE label.

Thus there are **6 fully orientation-consistent failed outputs** (five B plus one C), **2 partial cases**, and **24 other failures**. For wrong-label rows alone: 5 full reversals + 2 partial reversals + 24 other semantic confusions = 31; label-mapping-only = 0. If “not fully explained by reversal” is used as the broader bucket, it contains 26 wrong-label rows, including the two partial cases. All 31 remain semantic failures under the actual orientation.

A global OMISSION/ADDITION label swap is not a fix: it would gain the 10 wrong OMISSION decisions and lose the 10 correct ADDITION decisions, leaving 29/60 class decisions correct. Reasons remain incompatible and historical acceptance is unchanged. This is arithmetic over saved labels, not a relabeled evaluation.

## 5. TRAIN / DEV shortcut audit

All 300 rows were audited. Every class has **48 TRAIN and 12 DEV** examples. Appendix C gives per-class lengths, token positions, evidence counts, structural/template distributions, transformations, lexical markers, status and order patterns; the JSON retains each individual row's features.

### Class leakage and easy cues

1. **Citation-number shortcut:** where a first required ref exists, its numeric value modulo 20 is exactly 0/4/8/12/16 for MATCH/DIVERGENCE/OMISSION/ADDITION/INSUFFICIENT_EVIDENCE. This holds for **288/288** such rows, including every DEV row; the other 12 TRAIN refusals have no required refs. These numbers are visible in the actual prompt. No claim is made that the model computed the modulus, but they carry non-semantic class information and must not be usable as features in the proposed classifier.
2. Example-ID suffix modulo 5 also perfectly encodes class on **300/300** rows. The ID is logging metadata, not part of `row['input']` or the model prompt. Dataset list order repeats the five classes. The executed optimizer schedule shuffles that order; each TRAIN ID occurs exactly twice. A future classifier must not ingest IDs, metadata, row position or filenames.
3. All 240 substantive targets require **exactly the input `required_refs` list**; 60 refusal targets have no evidence items. Ref counts match across all four substantive classes (TRAIN mean 2.0625; DEV mean 2.1667). Correct reference copying is much easier than validating an explanation and does not distinguish the four substantive classes. Each example has exactly one owned source span; source-span count cannot explain their class differences.
4. TRAIN ADDITION has a short, class-specific reason template (mean target 87.25 tokens versus OMISSION 102.23, DIVERGENCE 115.88, MATCH 97.54). Its extraction contains exclusive invention vocabulary: approved/supervisor 9/48; inspector/verified 6/48; external/rule 12/48; caused/equipment/vibration 12/48; overall/passed/review 9/48. DEV uses supervisor/approved 3/12, inspector/verified 6/12, overall/passed/review 3/12. These are legitimate content but narrow class-correlated surface cues. The presence of “end” is MATCH-exclusive in extraction (18/48 TRAIN, 6/12 DEV), reflecting structural footers. A word alone cannot establish semantic support or absence from the source.
5. Refusal is represented by the compact distinct target `{"items":[],"status":"refused"}` and fixed synthetic insufficient-input forms. TRAIN has five forms: interrupted claim 9, unresolved deictic 12, unbound quotation 6, missing owned original 12, ambiguous qualification 9. DEV has only interrupted claim 3, unbound quotation 6, ambiguous qualification 3. Thus perfect DEV refusal does not measure all TRAIN insufficiency forms or general real-world refusal competence.

### Layout and distribution shift

No OMISSION-only versus ADDITION-only layout exists in this release. Every class has the same TRAIN layout mix: discourse, enumerated, sectioned, tabular, 12 examples each; 16 named rendering templates, three each. Every DEV class is `anchored`, with timeline/register/machine_log/footnoted_record, three each. Numeric semantic-structure frequencies are identical across classes within each split. Layout is therefore a **split-level shift**, not a within-split class identifier. The observed failures on headings, annotation boundaries and changed qualifications make sensitivity to this shift plausible; its causal contribution is unmeasured.

OMISSION extraction is shorter than ADDITION on average (TRAIN extraction/source character ratios 0.674 vs 0.922; DEV 0.627 vs 0.843). That partly follows the task semantics, but aggregate length is not a sufficient semantic test, and source formatting contributes to the ratio. Prompt lengths overlap strongly. Domain frequencies are not identical by class (full counts in appendix), adding weaker surface correlations.

The substantive JSON prefix is identical through `finding`; relation content begins at target-token index **16** (zero-based), with MATCH 2, DIVERGENCE 4, OMISSION 3, ADDITION 2 relation-content tokens. Refusal has no `finding` field; its signal is in status/structure. Confidence is CONFIDENT throughout substantive targets; severity is low for MATCH and medium for the other three. These are output contract patterns, not independent input evidence. Teacher-forced reasoning is trained *after* the gold relation and can become a fluent class-conditioned template without proving correct pair comparison.

### Sample sufficiency

240 balanced labels are adequate for a **bounded linear-probe experiment**, not evidence that a robust semantic classifier can be learned. Effective variety is smaller than 240 independent natural examples because the data are machine-authored and templated; `human_reviewed` is false. DEV recall changes by 1/12 = 8.33 percentage points per row. Its anchored layout makes it a useful held-out structural challenge, but it is already inspected development data and cannot establish untouched generalization. No additional examples are necessary to answer the proposed narrow experiment; no data were authored or expanded. Canonical split and labels remain fixed.

## 6. Training trajectory

Only step60 and step120 full-DEV class outputs were measured. Checkpoint0 records fresh initialization, not class predictions. There are **no early or intermediate training-time class outputs** establishing when dominance first emerged. It is valid to say OMISSION dominates at 60 and ADDITION at 120, not that OMISSION emerged at an invented early checkpoint or that a continuous transition was observed.

Mean saved training loss for updates 1–10 is 1.377635; 51–60 is 0.034652; 61–70 is 0.024402; 111–120 is 0.015510. First/final individual update losses are 2.625045/0.012164. Loss generally falls but is not monotonic and batches differ. DEV macro F1 improves from 0.3770 to 0.4350 and acceptance from 19 to 28; it does **not** degrade overall, but remains far below the gates while one class loses all predictions.

Final ten updates contain 40 exposures: MATCH 5, DIVERGENCE 8, OMISSION 9, ADDITION 6, refusal 12. The late ADDITION dominance is not explained by a simple majority of ADDITION examples in that final window. Logs provide no class-specific token loss, gradient contribution or causal ablation. Low aggregate training loss does not demonstrate relation generalization.

## 7. Loss and token-weight audit

The executed worker `tools/auditor_canonical_remote.py:227–230` calls `model(**batch).loss` with prompt labels masked to -100 by `runtime.py:41–49`, then divides each microbatch loss by four before accumulation. There is no relation-specific objective or weight. For the pinned causal LM this is ordinary next-token cross entropy over unmasked target positions, averaged within each single-example microbatch. The latter matters: pooled token proportions are not the exact example-averaged loss allocation.

The local cached tokenizer was used on the exact chat-rendered TRAIN and DEV targets, including termination. Tokens are assigned by character-offset overlap with the relation value (excluding quotes), reason string (excluding surrounding quotes), evidence array, remaining status/contract text, and native termination token. Boundary-merging makes this an approximate field attribution; totals reconcile exactly. Reference strings quoted *inside reasons* count as reason tokens. INSUFFICIENT_EVIDENCE has no literal relation token; its class signal is carried by the refusal structure, not omitted supervision.

| TRAIN target portion | Tokens, one visit to 240 rows | Pooled share | Mean per-example share, matching loss reduction |
|---|---:|---:|---:|
| Relation content | 528 | **2.6449%** | **2.1712%** |
| Reason | 8,539 | 42.7741% | 34.6501% |
| Evidence array | 3,360 | 16.8311% | 14.0276% |
| Status / contract / other structure | 7,296 | 36.5476% | 46.8028% |
| Native termination | 240 | 1.2022% | 2.3482% |
| Total | 19,963 | 100% | 100% |

Reason + evidence: **59.6053% pooled**, **48.6777% example-averaged**. Both visits double counts without changing these shares. DEV relation share is 132/4,919 = 2.6835%; reason + evidence is 2,903/4,919 = 59.0161%. Refusal training targets have 13 tokens including chat suffix; saved generated refusals have 12 because generation stops at EOS before the trailing template newline.

**`RELATION_SIGNAL_DILUTION_SUPPORTED`**, in the precise sense that explicit substantive class content receives a small fraction of the uniform token objective and the loss mostly supervises other fields. This does not establish insufficient gradient magnitude, prove causation, or show that weighting alone would repair the errors. Class-specific token losses were not saved, gradient norms by objective component are unavailable, and a few difficult class tokens could dominate loss despite low token share. The result supports a dedicated class objective as a clean next test; it does not justify another broad causal-LM tuning cycle.

## 8. Four confident-wrong catastrophes

The unchanged scorer at `runtime.py:142` flags a valid output when the predicted finding is MATCH or DIVERGENCE, differs from the expected class, and confidence is CONFIDENT. It does not flag every confidently wrong ADDITION. This explains why 31 wrong labels produce only four catastrophes. Other five catastrophic category counts remain zero. No confidence downgrade or category change is proposed to evade this gate.

| ID suffix | Expected → predicted | Source/evidence issue | Could a correct classifier prevent it? | Deterministic post-generation check |
|---|---|---|---|---|
| 058 | ADDITION → MATCH | Existing claims/gaps retained, but extraction adds “A supervisor approved all 3 entries.” | Yes, by selecting ADDITION; the saved reason must also change. Actual prevention is unmeasured. | A sound aligned fact inventory would detect unmatched candidate approval. Ref-ID checks alone cannot. |
| 138 | ADDITION → DIVERGENCE | Reason concatenates two source claims into an invented replacement and misses “An independent inspector verified every qualification.” | Yes, with correct ADDITION and explanation; no performance guarantee. | Verify quoted replacement against separately aligned source/candidate claims and inspect unmatched candidate facts. Literal substring absence across layout boundaries is insufficient. |
| 142 | OMISSION → MATCH | “The amendment ratification status remains unknown.” exists in source and is absent from extraction, despite claimed preservation. | Yes, correct OMISSION could avoid false MATCH. | A faithful aligned qualification inventory detects missing uncertainty. |
| 147 | OMISSION → MATCH | “The third entry recording date is uncertain.” is absent from extraction, despite claimed preservation. | Yes, correct OMISSION could avoid false MATCH. | Same missing-qualification check, preserving epistemic meaning. |

Exact generated reasons and refs for all four are in Appendix B. These deterministic checks are feasible for these explicit synthetic forms but require a sound parser/alignment for arbitrary text. They were inspected locally, not deployed. No existing universal semantic equivalence checker is established. Changing CONFIDENT to UNCERTAIN would not fix wrong relations and is not part of the design.

## 9. Counterfactual system value from saved outputs

The analysis computes counterfactual acceptance algebraically using the frozen predicate; it neither generates reasons nor writes corrected historical outputs.

| Saved-output counterfactual | Supportable accepted count |
|---|---:|
| Current | **28/60** |
| Perfect relation correction only, retaining existing reasons/evidence | **28/60**, gain 0 |
| Perfect reason correction only, retaining relation decisions | **29/60**, gain 1 (row156) |
| Perfect relation plus existing compatible reason/evidence | **28/60** |

No wrong-label output contains a complete reason compatible with the expected relation. Some contain a true fragment (retained claims, or the exact missing text with the wrong directional verb); retaining such fragments is not the same as retaining a valid complete explanation. Reversing verbs, adding omitted facts, or rewriting an explanation would be a reason correction, not label-only correction. The theoretical 60/60 with newly perfect reasons is not a bound supported by existing generations. The measured counterfactual therefore argues for **classification before explanation**, not merely overwriting a label after generation.

## 10. Architecture / objective review

| Design | Fit to measured failure and catastrophe implications | Training complexity | Inference latency / cloud cost | Traceability, deterministic testability, compatibility |
|---|---|---|---|---|
| A. Current single generative Auditor | Coupled wrong relation and rationalization; does not directly isolate the class decision. More of the same training is not the selected next intervention. No evidence of catastrophe control. | Existing causal-LM LoRA path is implemented; another full objective run still mixes class, copy and prose. | Historical full run about $1; autoregressive full JSON dominates latency. No improvement assumed. | Existing schema/runner fit; deterministic replay exists, but label objective and reason objective cannot be assessed separately. |
| B. Classifier first, then conditioned reason/evidence | Direct supervised five-way loss before prose; can distinguish decision failure from explanation failure. Correct labels could prevent the four catastrophes, but correctness is unproven and reasoning still needs evaluation. **Selected with the small frozen head specified below.** | Cache frozen features; fit one linear head; small routing/serialization adapter. No generator retraining. | One classifier prefill and short refusal probe, then reason generation only for substantive outputs. Expected similar or lower generation volume; extra prefill measured, not assumed free. One A10, projected $0.65–$1.08. | Log logits, class, refusal decision, generated reason and input-derived refs separately; unit-test routing and deterministic assembly; emit existing Auditor contract. New execution binding required before any authorized run. |
| C. Derive relation deterministically from structured Producer outputs where sound | Exact matching can prove preservation, missing aligned propositions, or unmatched additions only where representation and scope are complete. Divergence needs identity/alignment; set difference alone confuses replacement with addition+omission. No Producer output was executed or inspected as a model result here. | No learned head, but substantial soundness, normalization and alignment work for general coverage. | Very low per-call compute after valid structured inputs; engineering cost and unknown coverage dominate. | Best rule traceability/testability in its supported domain; preserve provenance and refuse unsupported cases. Current Auditor receives source spans and extraction text, so this is a larger integration change and cannot be assumed complete. |
| D. Separate classification model/head plus current model for explanation | Splits objectives, but independent explanations may still disagree unless conditioned on the class. A separate smaller encoder is untested; a larger LLM is unjustified. | New model adds representation/training/dependency choices and possibly a second serving artifact. A shared frozen head is the smaller special case selected in B. | Separate model adds load/residency and inference overhead; no measured price/latency estimate available. Could be cheap but is not required to answer this test. | Separate logits are auditable; end-to-end contract checks remain essential. More integration than reusing the pinned backbone. |

Retain the existing generator only as a **frozen refusal/explanation component**, not the authority for the substantive relation token. Step120 is reusable in that narrow experimental role despite being an ineligible final Auditor. It is not promoted, selected as a historical winner, or claimed to contain linearly separable semantic features. Whether those features suffice is the point of the experiment.

## 11. Exactly one selected experiment: frozen step120 representation + linear relation head

Working design name: **Auditor classification-first linear probe**. This document is a design, not executable launch/training authorization. No experiment implementation, new data release or new training has been performed.

### Architecture and weights

- Reuse pinned `unsloth/Phi-3.5-mini-instruct-bnb-4bit`, revision `5c20803aa197416f43fb455e55c85178775320cb`, actual `LlamaForCausalLM` with hidden size **3072**, and frozen step120 adapter SHA-256 `733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6`. Use the existing frozen quantization, tokenizer, BF16 and eager execution settings. All base, LM-head and LoRA weights remain frozen and in eval mode.
- Stage1 representation is the final normalized hidden state at the last non-padding token of the existing assistant-generation prompt, before generating any answer. Detach and store FP32 vectors. Do not append gold class, reason or target to the feature input. Disable gradients and KV caching for feature extraction. One cached vector per row, no repeated backbone training.
- Classifier is `logits = W h + b`, **5 × 3072 + 5 = 15,365 new trainable parameters**. No hidden layer, no dropout, no new backbone adapter. Fixed label order is the five classes used in this report. Argmax ties use that order. Log all five raw logits and raw predicted class before any refusal routing.
- Fit per-dimension mean and standard deviation using TRAIN vectors only; standardize TRAIN/DEV with those frozen values and clamp standard deviations below 1e-6 to 1e-6. No DEV feature normalization fit.

### Data and shortcut protection

Use **exactly the existing 240 TRAIN IDs and 60 DEV IDs** from `tuning/auditor_canonical_execution/split.json`; 48/12 per class. No new rows, labels, augmentation or folds. Labels come only from the existing relation field. Refusal is the fifth supervised class, not a dropped category.

For the classifier feature view only, replace citation identifiers consistently with local aliases `REF-0001`, `REF-0002`, etc., assigned in first-occurrence order scanning owned source spans, then extraction, then context-only spans, then required/supplied-ref arrays. Replace complete REF identifiers, including every repeated occurrence, without replacing quantities, dates, claim text, or structural markers. Retain the bijection for traceability. A consistent upstream renaming must yield an identical normalized prompt; verify that property before launch. The purpose is to eliminate numeric-ID class leakage. This is deterministic input preprocessing of the same examples, not new authored data. Original prompts and target refs remain intact for the frozen refusal/explanation component and scorer.

No example ID, list index, transformation metadata, template label, domain metadata, gold target, saved prediction or DEV failure annotation may enter the classifier input. Input domain words present in source text remain; do not introduce a corpus-specific lexical rule. Existing lexical/template correlations remain a limitation of what this run can establish.

### Objective and fixed training protocol

Train only W and b, initialized to zero with seed7, on cached standardized TRAIN vectors. Use full-batch 240-example softmax cross entropy plus `0.001 * mean(W**2)`; equal example weights, no class reweighting. Use FP32 Adam, learning rate 0.01, betas (0.9, 0.999), epsilon 1e-8, weight decay 0, **200 updates**, no scheduler, no hyperparameter search. Do not backpropagate through the frozen representation.

Save head/normalization/label-map identities at initialization and update200. **Only update200 is evaluated as a candidate**; initialization is an identity snapshot, not a candidate checkpoint. Do not inspect DEV logits during fitting. Training loss is logged each update; no train-loss early-selection criterion. The two hundred tiny head updates are not comparable in compute to the historical 120 backbone updates.

### Refusal preservation and Stage2

The existing frozen model's original-prompt greedy **refusal branch** is a veto. On each DEV row, follow the original decoder only until it identifies the canonical nonempty-items branch or completes the exact refusal object followed by native EOS; cap this probe at 16 generated tokens. Save raw tokens. The two branches are distinguishable before a relation is generated in the measured canonical outputs. An unexpected branch, incomplete refusal, changed token identity versus deterministic controls, or cap exhaustion is a runtime failure, not an invented refusal. The saved step120 token streams were checked locally: all 48 nonempty branches are recognizable after five tokens, and all 12 refusals complete with native EOS after 12 tokens. This establishes cap feasibility, not parity of an unimplemented runtime. The implemented prefix decoder must be tested against all 60 saved branch prefixes before future launch; no saved refusal mask may be used as an inference lookup table.

If the frozen branch refuses, emit the same refusal object regardless of the head. Otherwise, if the head predicts INSUFFICIENT_EVIDENCE, emit refusal; this may create over-refusal, which must be scored and can reject the candidate. Otherwise, use the head's substantive relation. Report raw-head five-way metrics separately from routed final metrics. This veto preserves the historical refusal mechanism on identical inputs without claiming that it guarantees all new system metrics. Require final DEV refusal/evidence metrics to remain at their current 1.0 in this experiment as an additional non-regression check, without weakening any frozen gate.

For a substantive output, use the original prompt and frozen step120 generator with a forced canonical assistant prefix through the head-selected `finding` and opening `reasoning` string. Greedily generate **only the JSON-escaped reason string**, stopping at its first unescaped closing quote with an escape-aware JSON-string parser. No gold reason, target template, expected relation or dataset metadata is supplied. EOS before a complete reason or malformed escaping is a failure, not repaired text. Serialize the remainder deterministically: `ref_ids` from input `required_refs` after confirming these are unique supplied refs; confidence CONFIDENT; severity low for MATCH, medium otherwise; one item, no extra fields. A required-ref mismatch fails admission rather than inventing a ref. This reproduces the existing evidence obligation (all 240 substantive targets exactly use required_refs), not a claim of general semantic evidence selection.

Retain a **192-token ceiling on the full assembled answer including termination**. Account for the forced prefix and deterministic suffix before computing the reason-generation allowance; use exact tokenizer checks and reject overflow. Preserve the raw generated reason, token counts, assembled JSON, head logits, routing decisions and provenance separately. Do not count forced/assembled tokens as model-generated throughput. Contract, reason, evidence and catastrophic scoring remain the same frozen functions. Saving only final JSON would hide the intervention and is insufficient.

This is deliberately a conditional-generation test, not an assertion that the frozen explainer will improve. Wrong explanation after a correct class remains a failure. It cannot be rescued by editing reasons after DEV inspection.

### Evaluation, gates and selection

One full fresh DEV evaluation at head update200, after deterministic two-pass controls on the same five prospectively bound class-control IDs. Controls, token accounting and raw-before-scoring durability follow the existing Auditor-only execution conventions. There is one candidate; it is selected only if all frozen gates pass on all 60 outputs and non-regression checks pass. No ranking among alternative heads, pooling of runs, or best-example selection.

Frozen gates retained: contract validity = 1.0; macro relation F1 >= 0.75; each of five class recalls >= 0.60; accepted outcomes >= 0.70; evidence F1 >= 0.85; refusal precision >= 0.90; refusal recall >= 0.80; over-refusal <= 0.05; substantive non-refusal coverage >= 0.90; all six catastrophic categories = 0. At DEV size60, acceptance requires at least 42; recall requires at least 8/12 per class. This experiment additionally requires evidence F1=1.0, refusal precision=recall=1.0, over-refusal=0, and full non-refusal coverage of the 48 substantive rows to preserve the measured strengths. These are stricter admission checks, not replacements for historical gates.

Primary binary question: **Does a direct five-way head on the frozen Auditor representation, followed by class-conditioned explanation, produce a gate-passing canonical Auditor while preserving refusal and evidence behavior?** Also report raw-head class results to distinguish representation/classification failure from explanation failure. If the head succeeds but the assembled Auditor fails, the full answer is FAIL, with explanation identified as the remaining bottleneck. A head failure does not disprove classification-first architectures generally; it rejects this frozen-feature linear probe.

## 12. Projected runtime, GPU and cost

One A10 24 GB or an explicitly approved smaller compatible GPU; the concrete estimate uses **one A10**. Frozen NF4 backbone plus adapter previously used about 2.76 GiB allocated during generation; the head and cached vectors are small (300 × 3072 × 4 bytes = 3.52 MiB before metadata). Final-layer extraction should not retain all layer states; a hook or decoder final state avoids that overhead. Project a <8 GiB live-memory envelope but verify during preflight; no measured head-run memory or throughput exists yet.

At the **historical observed** $1.29/hour rate, an estimated **30–50 minutes** costs **$0.645–$1.075**. This is a local projection, not a current quote or reservation. Rough planning envelope: setup/acquisition 8–12 minutes, 300 frozen feature prefills 3–8 minutes, head fitting under 1 minute, original refusal probes 1–3 minutes, one DEV plus ten controls of reason generation 10–18 minutes, archive/cleanup 3–5 minutes. These overlapping ranges are planning assumptions; a conservative maximum-output bound is larger than typical-output estimates. No cloud/API lookup was made in this task.

For a separately authorized run, prospectively bind one-instance ceiling, soft $1.50 / hard $3.00, and a **55-minute launch-to-termination deadline** (about $1.1825 at the historical rate), reserving the final five minutes for archive and termination. Stop new work at minute50. Measure prefill/decode rates and remaining tokens early; if the entire remaining DEV/control work cannot finish by minute50, stop before further work, archive and terminate. Do not silently raise the bound. Fresh rate, destination/payload approval and a tested execution commit belong to that future task.

## 13. Stop rule, one fallback and readiness

No automatic retries, second head, hyperparameter search, extra adapter updates, new data, label revision or second GPU. Missing raw evidence, unsafe identifier normalization, invalid refusal routing, nonfinite head loss, contract/runtime failure, exceeded token/memory limit, or insufficient remaining time invalidate or stop the run; complete nonpassing quality results are FAIL. Keep the failed historical adapter unchanged and store the new head separately. Archive evidence and terminate even on failure. No subsequent governed Producer+Auditor test is admitted by this design.

**One fallback only, not selected or authorized:** if the frozen linear head fails the relation gates, a future separately reviewed experiment may train a small rank8 classifier-specific LoRA plus the same five-way head under class cross entropy, keeping the original step120 refusal/explanation adapter separately frozen. That would test whether representation adaptation is necessary. Do not execute it automatically, do not combine it with this probe, and do not create new examples. If only explanation fails, stop for local diagnosis rather than invoke this classifier fallback.

Readiness requirements are met: complete 32-row taxonomy, A/B/C/D/E decomposition, orientation and shortcut audits, quantitative token-objective audit, four catastrophe reviews, exactly one selected architecture, and unchanged quality gates. **`AUDITOR_NEXT_EXPERIMENT_READY`** means this bounded design is ready for a separate implementation/authorization task; it does not mean the unimplemented classifier/prefix-routing code has been tested. Prelaunch work must bind and test normalization invariance, feature position/no-target leakage, TRAIN-only statistics, refusal-prefix parity, escaped-string stopping, token caps, contract assembly, deterministic controls and termination. Those checks must pass before any future cloud execution.

No cloud, training, model generation, new Auditor data, Producer execution, protected access, folds1–4 execution, paid API, full pipeline, multi-round execution or push occurred in this task. `PRODUCER_STATUS=PRESERVED_UNEXECUTED`; `PROTECTED_RECEIPT_STATUS=UNCONSUMED`.

<!-- GENERATED DIAGNOSTIC APPENDICES -->

## Appendix A. Exact confusion cells and row IDs

IDs below are complete dataset IDs; an em dash denotes an empty cell. Counts are computed from saved scored evidence and checked against raw JSON findings.

### Step60

| Expected | Predicted | Count | Row IDs |
|---|---|---:|---|
| MATCH | MATCH | 1 | shimmer2-auditor-document-150 |
| MATCH | DIVERGENCE | 2 | shimmer2-auditor-document-045, shimmer2-auditor-document-050 |
| MATCH | OMISSION | 9 | shimmer2-auditor-document-055, shimmer2-auditor-document-135, shimmer2-auditor-document-140, shimmer2-auditor-document-145, shimmer2-auditor-document-155, shimmer2-auditor-document-160, shimmer2-auditor-document-270, shimmer2-auditor-document-275, shimmer2-auditor-document-280 |
| MATCH | ADDITION | 0 | — |
| MATCH | INSUFFICIENT_EVIDENCE | 0 | — |
| DIVERGENCE | MATCH | 0 | — |
| DIVERGENCE | DIVERGENCE | 3 | shimmer2-auditor-document-051, shimmer2-auditor-document-136, shimmer2-auditor-document-151 |
| DIVERGENCE | OMISSION | 9 | shimmer2-auditor-document-046, shimmer2-auditor-document-056, shimmer2-auditor-document-141, shimmer2-auditor-document-146, shimmer2-auditor-document-156, shimmer2-auditor-document-161, shimmer2-auditor-document-271, shimmer2-auditor-document-276, shimmer2-auditor-document-281 |
| DIVERGENCE | ADDITION | 0 | — |
| DIVERGENCE | INSUFFICIENT_EVIDENCE | 0 | — |
| OMISSION | MATCH | 0 | — |
| OMISSION | DIVERGENCE | 1 | shimmer2-auditor-document-142 |
| OMISSION | OMISSION | 11 | shimmer2-auditor-document-047, shimmer2-auditor-document-052, shimmer2-auditor-document-057, shimmer2-auditor-document-137, shimmer2-auditor-document-147, shimmer2-auditor-document-152, shimmer2-auditor-document-157, shimmer2-auditor-document-162, shimmer2-auditor-document-272, shimmer2-auditor-document-277, shimmer2-auditor-document-282 |
| OMISSION | ADDITION | 0 | — |
| OMISSION | INSUFFICIENT_EVIDENCE | 0 | — |
| ADDITION | MATCH | 0 | — |
| ADDITION | DIVERGENCE | 2 | shimmer2-auditor-document-048, shimmer2-auditor-document-148 |
| ADDITION | OMISSION | 10 | shimmer2-auditor-document-053, shimmer2-auditor-document-058, shimmer2-auditor-document-138, shimmer2-auditor-document-143, shimmer2-auditor-document-153, shimmer2-auditor-document-158, shimmer2-auditor-document-163, shimmer2-auditor-document-273, shimmer2-auditor-document-278, shimmer2-auditor-document-283 |
| ADDITION | ADDITION | 0 | — |
| ADDITION | INSUFFICIENT_EVIDENCE | 0 | — |
| INSUFFICIENT_EVIDENCE | MATCH | 0 | — |
| INSUFFICIENT_EVIDENCE | DIVERGENCE | 0 | — |
| INSUFFICIENT_EVIDENCE | OMISSION | 0 | — |
| INSUFFICIENT_EVIDENCE | ADDITION | 0 | — |
| INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | 12 | shimmer2-auditor-document-049, shimmer2-auditor-document-054, shimmer2-auditor-document-059, shimmer2-auditor-document-139, shimmer2-auditor-document-144, shimmer2-auditor-document-149, shimmer2-auditor-document-154, shimmer2-auditor-document-159, shimmer2-auditor-document-164, shimmer2-auditor-document-274, shimmer2-auditor-document-279, shimmer2-auditor-document-284 |

### Step120

| Expected | Predicted | Count | Row IDs |
|---|---|---:|---|
| MATCH | MATCH | 5 | shimmer2-auditor-document-045, shimmer2-auditor-document-055, shimmer2-auditor-document-135, shimmer2-auditor-document-150, shimmer2-auditor-document-155 |
| MATCH | DIVERGENCE | 0 | — |
| MATCH | OMISSION | 0 | — |
| MATCH | ADDITION | 7 | shimmer2-auditor-document-050, shimmer2-auditor-document-140, shimmer2-auditor-document-145, shimmer2-auditor-document-160, shimmer2-auditor-document-270, shimmer2-auditor-document-275, shimmer2-auditor-document-280 |
| MATCH | INSUFFICIENT_EVIDENCE | 0 | — |
| DIVERGENCE | MATCH | 0 | — |
| DIVERGENCE | DIVERGENCE | 2 | shimmer2-auditor-document-136, shimmer2-auditor-document-156 |
| DIVERGENCE | OMISSION | 0 | — |
| DIVERGENCE | ADDITION | 10 | shimmer2-auditor-document-046, shimmer2-auditor-document-051, shimmer2-auditor-document-056, shimmer2-auditor-document-141, shimmer2-auditor-document-146, shimmer2-auditor-document-151, shimmer2-auditor-document-161, shimmer2-auditor-document-271, shimmer2-auditor-document-276, shimmer2-auditor-document-281 |
| DIVERGENCE | INSUFFICIENT_EVIDENCE | 0 | — |
| OMISSION | MATCH | 2 | shimmer2-auditor-document-142, shimmer2-auditor-document-147 |
| OMISSION | DIVERGENCE | 0 | — |
| OMISSION | OMISSION | 0 | — |
| OMISSION | ADDITION | 10 | shimmer2-auditor-document-047, shimmer2-auditor-document-052, shimmer2-auditor-document-057, shimmer2-auditor-document-137, shimmer2-auditor-document-152, shimmer2-auditor-document-157, shimmer2-auditor-document-162, shimmer2-auditor-document-272, shimmer2-auditor-document-277, shimmer2-auditor-document-282 |
| OMISSION | INSUFFICIENT_EVIDENCE | 0 | — |
| ADDITION | MATCH | 1 | shimmer2-auditor-document-058 |
| ADDITION | DIVERGENCE | 1 | shimmer2-auditor-document-138 |
| ADDITION | OMISSION | 0 | — |
| ADDITION | ADDITION | 10 | shimmer2-auditor-document-048, shimmer2-auditor-document-053, shimmer2-auditor-document-143, shimmer2-auditor-document-148, shimmer2-auditor-document-153, shimmer2-auditor-document-158, shimmer2-auditor-document-163, shimmer2-auditor-document-273, shimmer2-auditor-document-278, shimmer2-auditor-document-283 |
| ADDITION | INSUFFICIENT_EVIDENCE | 0 | — |
| INSUFFICIENT_EVIDENCE | MATCH | 0 | — |
| INSUFFICIENT_EVIDENCE | DIVERGENCE | 0 | — |
| INSUFFICIENT_EVIDENCE | OMISSION | 0 | — |
| INSUFFICIENT_EVIDENCE | ADDITION | 0 | — |
| INSUFFICIENT_EVIDENCE | INSUFFICIENT_EVIDENCE | 12 | shimmer2-auditor-document-049, shimmer2-auditor-document-054, shimmer2-auditor-document-059, shimmer2-auditor-document-139, shimmer2-auditor-document-144, shimmer2-auditor-document-149, shimmer2-auditor-document-154, shimmer2-auditor-document-159, shimmer2-auditor-document-164, shimmer2-auditor-document-274, shimmer2-auditor-document-279, shimmer2-auditor-document-284 |

## Appendix B. All 32 failed step120 rows

“Supports predicted” below distinguishes the relation type asserted by the prose from support in the actual source/extraction. A true fragment is not a complete correct reason. Evidence flags evaluate ID selection, not entailment of the reason. Exact saved scorer reason_correct is null for every row below; semantic annotations do not change it.

### shimmer2-auditor-document-046

Expected **DIVERGENCE**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40184, REF-40185`.

**Expected reason:** The extraction replaces "CLM-A: The count is 11 pulses. (REF-40184)" with "CLM-A: The count is 11 boxes. (REF-40184)". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction adds "The event date is missing." and "The first entry recording date is missing." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Device comparison dossier
Phase 01 | CLM-A: The count is 11 pulses. (REF-40184)
Phase 02 | CLM-B: The transport container count is 11 boxes. (REF-40185)
Phase 03 | The following qualifications concern a separate annex, not the numbered claim events.
Phase 04 | The event date is missing.
Phase 05 | The first entry recording date is missing.
Phase 06 | The amendment ratification status remains unknown.
```

**Extraction, exact:**

```text
CLM-A: The count is 11 boxes. (REF-40184) CLM-B: The transport container count is 11 boxes. (REF-40185) The following qualifications concern a separate annex, not the numbered claim events. The event date is missing. The first entry recording date is missing. The amendment ratification status remains unknown.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The event date is missing. | True | True |
| The first entry recording date is missing. | True | True |

### shimmer2-auditor-document-047

Expected **OMISSION**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40188, REF-40189`.

**Expected reason:** The complete, delivered extraction omits the source content "The event date is missing." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction adds "The event date is missing." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Identifies exactly the missing source content, but calls it an unsupported extraction addition. Both label and directional reason reverse the comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | complete_reversed_comparison |

**Owned source, exact:**

```text
Procurement comparison dossier
Phase 01 | CLM-A: The count is 11 crates. (REF-40188)
Phase 02 | CLM-B: The transport container count is 11 boxes. (REF-40189)
Phase 03 | The following qualifications concern a separate annex, not the numbered claim events.
Phase 04 | The event date is missing.
Phase 05 | The second entry event date is missing.
Phase 06 | The amendment ratification status remains unknown.
```

**Extraction, exact:**

```text
CLM-A: The count is 11 crates. (REF-40188) CLM-B: The transport container count is 11 boxes. (REF-40189) The following qualifications concern a separate annex, not the numbered claim events. The second entry event date is missing. The amendment ratification status remains unknown.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The event date is missing. | True | False |

### shimmer2-auditor-document-050

Expected **MATCH**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40200, REF-40201, REF-40202`.

**Expected reason:** The extraction preserves all 3 explicit claims, including their scope and evidence, and retains both gaps (The event date is missing. Which entry came later?) and the stated uncertainty.

**Generated reason, exact:** The extraction adds "The event date is missing." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Astronomy comparison dossier
Phase 01 | CLM-A: The authorization date is 2041-02-01. (REF-40200)
Phase 02 | CLM-B: The submission date is 2041-02-02. (REF-40201)
Phase 03 | CLM-C: The event date is 2041-02-03. (REF-40202)
Phase 04 | The following qualifications concern a separate annex, not the numbered claim events.
Phase 05 | The event date is missing.
Phase 06 | Which entry came later?
Phase 07 | The third entry recording date is uncertain.
```

**Extraction, exact:**

```text
CLM-A: The authorization date is 2041-02-01. (REF-40200) CLM-B: The submission date is 2041-02-02. (REF-40201) CLM-C: The event date is 2041-02-03. (REF-40202) The following qualifications concern a separate annex, not the numbered claim events. The event date is missing. Which entry came later? The third entry recording date is uncertain.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The event date is missing. | True | True |

### shimmer2-auditor-document-051

Expected **DIVERGENCE**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40204, REF-40205, REF-40206`.

**Expected reason:** The extraction replaces "CLM-A: The authorization date is 2041-02-01. (REF-40204)" with "CLM-A: The submission date is 2041-02-01. (REF-40204)". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction adds "The third entry recording date is uncertain." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Ecology comparison dossier
Phase 01 | CLM-A: The authorization date is 2041-02-01. (REF-40204)
Phase 02 | CLM-B: The submission date is 2041-02-02. (REF-40205)
Phase 03 | CLM-C: The event date is 2041-02-03. (REF-40206)
Phase 04 | The following qualifications concern a separate annex, not the numbered claim events.
Phase 05 | The event date is missing.
Phase 06 | The submission was not submitted.
Phase 07 | The third entry recording date is uncertain.
```

**Extraction, exact:**

```text
CLM-A: The submission date is 2041-02-01. (REF-40204) CLM-B: The submission date is 2041-02-02. (REF-40205) CLM-C: The event date is 2041-02-03. (REF-40206) The following qualifications concern a separate annex, not the numbered claim events. The event date is missing. The submission was not submitted. The third entry recording date is uncertain.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The third entry recording date is uncertain. | True | True |

### shimmer2-auditor-document-052

Expected **OMISSION**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40208, REF-40209, REF-40210`.

**Expected reason:** The complete, delivered extraction omits the source content "The event date is missing." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction adds "The third entry recording date is uncertain." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Negotiation comparison dossier
Phase 01 | CLM-A: The authorization date is 2041-02-01. (REF-40208)
Phase 02 | CLM-B: The submission date is 2041-02-02. (REF-40209)
Phase 03 | CLM-C: The event date is 2041-02-03. (REF-40210)
Phase 04 | The following qualifications concern a separate annex, not the numbered claim events.
Phase 05 | The event date is missing.
Phase 06 | The date is unavailable.
Phase 07 | The third entry recording date is uncertain.
```

**Extraction, exact:**

```text
CLM-A: The authorization date is 2041-02-01. (REF-40208) CLM-B: The submission date is 2041-02-02. (REF-40209) CLM-C: The event date is 2041-02-03. (REF-40210) The following qualifications concern a separate annex, not the numbered claim events. The date is unavailable. The third entry recording date is uncertain.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The third entry recording date is uncertain. | True | True |

### shimmer2-auditor-document-056

Expected **DIVERGENCE**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40224, REF-40225, REF-40226`.

**Expected reason:** The extraction replaces "CLM-A: The first entry concerns the sensor rack. (REF-40224)" with "CLM-A: The second entry concerns the sensor rack. (REF-40224)". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction adds "The submission date is unspecified." and "The reporting date is unspecified." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Device comparison dossier
Phase 01 | CLM-A: The first entry concerns the sensor rack. (REF-40224)
Phase 02 | CLM-B: The second entry concerns a separate record. (REF-40225)
Phase 03 | CLM-C: The third entry repeats the first entry. (REF-40226)
Phase 04 | The following qualifications concern a separate annex, not the numbered claim events.
Phase 05 | The submission date is unspecified.
Phase 06 | The reporting date is unspecified.
Phase 07 | Whether the submission was submitted is unknown.
```

**Extraction, exact:**

```text
CLM-A: The second entry concerns the sensor rack. (REF-40224) CLM-B: The second entry concerns a separate record. (REF-40225) CLM-C: The third entry repeats the first entry. (REF-40226) The following qualifications concern a separate annex, not the numbered claim events. The submission date is unspecified. The reporting date is unspecified. Whether the submission was submitted is unknown.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The submission date is unspecified. | True | True |
| The reporting date is unspecified. | True | True |

### shimmer2-auditor-document-057

Expected **OMISSION**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40228, REF-40229, REF-40230`.

**Expected reason:** The complete, delivered extraction omits the source content "The submission date is unspecified." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction adds "The amendment effective date is unavailable." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Procurement comparison dossier
Phase 01 | CLM-A: The first entry concerns the purchase lot. (REF-40228)
Phase 02 | CLM-B: The second entry concerns a separate record. (REF-40229)
Phase 03 | CLM-C: The third entry repeats the first entry. (REF-40230)
Phase 04 | The following qualifications concern a separate annex, not the numbered claim events.
Phase 05 | The submission date is unspecified.
Phase 06 | The amendment effective date is unavailable.
Phase 07 | Whether the submission was submitted is unknown.
```

**Extraction, exact:**

```text
CLM-A: The first entry concerns the purchase lot. (REF-40228) CLM-B: The second entry concerns a separate record. (REF-40229) CLM-C: The third entry repeats the first entry. (REF-40230) The following qualifications concern a separate annex, not the numbered claim events. The amendment effective date is unavailable. Whether the submission was submitted is unknown.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The amendment effective date is unavailable. | True | True |

### shimmer2-auditor-document-058

Expected **ADDITION**; predicted **MATCH**. Category **B**. Catastrophe: **True**.

Evidence refs (generated and expected, identical): `REF-40232, REF-40233, REF-40234`.

**Expected reason:** The extraction adds "A supervisor approved all 3 entries." without support in any owned source span. All original claims and qualifications remain.

**Generated reason, exact:** The extraction preserves all 3 explicit claims, including their scope and evidence, and retains both gaps (The submission date is unspecified. The recorder is unnamed.) and the stated uncertainty.

**Assessment:** False preservation: the added supervisor approval is not addressed; the reason describes only retained material.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Catalogue comparison dossier
Phase 01 | CLM-A: The first entry concerns the index collection. (REF-40232)
Phase 02 | CLM-B: The second entry concerns a separate record. (REF-40233)
Phase 03 | CLM-C: The third entry repeats the first entry. (REF-40234)
Phase 04 | The following qualifications concern a separate annex, not the numbered claim events.
Phase 05 | The submission date is unspecified.
Phase 06 | The recorder is unnamed.
Phase 07 | Whether the submission was submitted is unknown.
```

**Extraction, exact:**

```text
CLM-A: The first entry concerns the index collection. (REF-40232) CLM-B: The second entry concerns a separate record. (REF-40233) CLM-C: The third entry repeats the first entry. (REF-40234) The following qualifications concern a separate annex, not the numbered claim events. The submission date is unspecified. The recorder is unnamed. Whether the submission was submitted is unknown. A supervisor approved all 3 entries.
```

### shimmer2-auditor-document-137

Expected **OMISSION**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40548, REF-40549`.

**Expected reason:** The complete, delivered extraction omits the source content "Whether the event occurred is unknown." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction adds "Whether the event occurred is unknown." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Identifies exactly the missing source content, but calls it an unsupported extraction addition. Both label and directional reason reverse the comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | complete_reversed_comparison |

**Owned source, exact:**

```text
Contracts comparison dossier
Entry slot 1
CLM-A: Account A says the count is 11 clauses. (REF-40548)
End slot
Entry slot 2
CLM-B: Account B says the same count is 17 clauses. (REF-40549)
End slot
Entry slot 3
The following qualifications concern a separate annex, not the numbered claim events.
End slot
Entry slot 4
The reporting date is unspecified.
End slot
Entry slot 5
The amendment ratification status is missing.
End slot
Entry slot 6
Whether the event occurred is unknown.
End slot
```

**Extraction, exact:**

```text
CLM-A: Account A says the count is 11 clauses. (REF-40548) CLM-B: Account B says the same count is 17 clauses. (REF-40549) The following qualifications concern a separate annex, not the numbered claim events. The reporting date is unspecified. The amendment ratification status is missing.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| Whether the event occurred is unknown. | True | False |

### shimmer2-auditor-document-138

Expected **ADDITION**; predicted **DIVERGENCE**. Category **B**. Catastrophe: **True**.

Evidence refs (generated and expected, identical): `REF-40552, REF-40553`.

**Expected reason:** The extraction adds "An independent inspector verified every qualification." without support in any owned source span. All original claims and qualifications remain.

**Generated reason, exact:** The extraction replaces "CLM-A: Account A says the count is 11 permits. (REF-40552)" with "CLM-A: Account A says the count is 11 permits. (REF-40552) CLM-B: Account B says the same count is 17 permits. (REF-40553)". This changes the same proposition, referent, or evidence association rather than preserving it.

**Assessment:** False replacement: two existing source claims are concatenated as a replacement for one; added inspector verification is ignored.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Regulation comparison dossier
Entry slot 1
CLM-A: Account A says the count is 11 permits. (REF-40552)
End slot
Entry slot 2
CLM-B: Account B says the same count is 17 permits. (REF-40553)
End slot
Entry slot 3
The following qualifications concern a separate annex, not the numbered claim events.
End slot
Entry slot 4
The reporting date is unspecified.
End slot
Entry slot 5
The first entry recording date is missing.
End slot
Entry slot 6
Whether the event occurred is unknown.
End slot
```

**Extraction, exact:**

```text
CLM-A: Account A says the count is 11 permits. (REF-40552) CLM-B: Account B says the same count is 17 permits. (REF-40553) The following qualifications concern a separate annex, not the numbered claim events. The reporting date is unspecified. The first entry recording date is missing. Whether the event occurred is unknown. An independent inspector verified every qualification.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| CLM-A: Account A says the count is 11 permits. (REF-40552) | True | True |
| CLM-A: Account A says the count is 11 permits. (REF-40552) CLM-B: Account B says the same count is 17 permits. (REF-40553) | False | True |

### shimmer2-auditor-document-140

Expected **MATCH**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40560, REF-40561`.

**Expected reason:** The extraction preserves all 2 explicit claims, including their scope and evidence, and retains both gaps (The reporting date is unspecified. The second entry event date is missing.) and the stated uncertainty.

**Generated reason, exact:** The extraction adds "Device comparison dossier" as the source content, which is not present in any owned source span. All original claims and qualifications remain.

**Assessment:** Source heading is called an unsupported addition although it occurs in the source and is absent from extraction; headings are explicitly non-propositional.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Device comparison dossier
Entry slot 1
CLM-A: The event occurred on 2041-02-03. (REF-40560)
End slot
Entry slot 2
CLM-B: The event was recorded on 2041-02-09. (REF-40561)
End slot
Entry slot 3
The following qualifications concern a separate annex, not the numbered claim events.
End slot
Entry slot 4
The reporting date is unspecified.
End slot
Entry slot 5
The second entry event date is missing.
End slot
Entry slot 6
The amendment ratification status remains unknown.
End slot
```

**Extraction, exact:**

```text
The following qualifications concern a separate annex, not the numbered claim events. The reporting date is unspecified. The second entry event date is missing. The amendment ratification status remains unknown. End annex qualifications. CLM-A: The event occurred on 2041-02-03. (REF-40560) CLM-B: The event was recorded on 2041-02-09. (REF-40561)
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| Device comparison dossier | True | False |

### shimmer2-auditor-document-141

Expected **DIVERGENCE**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40564, REF-40565`.

**Expected reason:** The extraction replaces "The amendment ratification status remains unknown." with "The amendment ratification status remains known.". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction adds "The amendment ratification status remains known." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Changed uncertainty is treated as an addition; the claim that all original qualifications remain is false.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Procurement comparison dossier
Entry slot 1
CLM-A: The event occurred on 2041-02-03. (REF-40564)
End slot
Entry slot 2
CLM-B: The event was recorded on 2041-02-09. (REF-40565)
End slot
Entry slot 3
The following qualifications concern a separate annex, not the numbered claim events.
End slot
Entry slot 4
The reporting date is unspecified.
End slot
Entry slot 5
What was entered third?
End slot
Entry slot 6
The amendment ratification status remains unknown.
End slot
```

**Extraction, exact:**

```text
CLM-A: The event occurred on 2041-02-03. (REF-40564) CLM-B: The event was recorded on 2041-02-09. (REF-40565) The following qualifications concern a separate annex, not the numbered claim events. The reporting date is unspecified. What was entered third? The amendment ratification status remains known.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The amendment ratification status remains known. | False | True |

### shimmer2-auditor-document-142

Expected **OMISSION**; predicted **MATCH**. Category **B**. Catastrophe: **True**.

Evidence refs (generated and expected, identical): `REF-40568, REF-40569`.

**Expected reason:** The complete, delivered extraction omits the source content "The amendment ratification status remains unknown." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction preserves all 2 explicit claims, including their scope and evidence, and retains both gaps (The reporting date is unspecified. Which entry came later?) and the stated uncertainty.

**Assessment:** False preservation: the stated uncertainty was omitted, contradicting the reason.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Catalogue comparison dossier
Entry slot 1
CLM-A: The event occurred on 2041-02-03. (REF-40568)
End slot
Entry slot 2
CLM-B: The event was recorded on 2041-02-09. (REF-40569)
End slot
Entry slot 3
The following qualifications concern a separate annex, not the numbered claim events.
End slot
Entry slot 4
The reporting date is unspecified.
End slot
Entry slot 5
Which entry came later?
End slot
Entry slot 6
The amendment ratification status remains unknown.
End slot
```

**Extraction, exact:**

```text
CLM-A: The event occurred on 2041-02-03. (REF-40568) CLM-B: The event was recorded on 2041-02-09. (REF-40569) The following qualifications concern a separate annex, not the numbered claim events. The reporting date is unspecified. Which entry came later?
```

### shimmer2-auditor-document-145

Expected **MATCH**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40580, REF-40581`.

**Expected reason:** The extraction preserves all 2 explicit claims, including their scope and evidence, and retains both gaps (The reporting date is unspecified. The date is unavailable.) and the stated uncertainty.

**Generated reason, exact:** The extraction adds "The reporting date is unspecified." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Ecology comparison dossier
Entry slot 1
CLM-A: The first entry was submitted. (REF-40580)
End slot
Entry slot 2
CLM-B: The first entry was not recorded. (REF-40581)
End slot
Entry slot 3
The following qualifications concern a separate annex, not the numbered claim events.
End slot
Entry slot 4
The reporting date is unspecified.
End slot
Entry slot 5
The date is unavailable.
End slot
Entry slot 6
The third entry recording date is uncertain.
End slot
```

**Extraction, exact:**

```text
The following qualifications concern a separate annex, not the numbered claim events. The reporting date is unspecified. The date is unavailable. The third entry recording date is uncertain. End annex qualifications. CLM-A: The first entry was submitted. (REF-40580) CLM-B: The first entry was not recorded. (REF-40581)
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The reporting date is unspecified. | True | True |

### shimmer2-auditor-document-146

Expected **DIVERGENCE**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40584, REF-40585`.

**Expected reason:** The extraction replaces "The third entry recording date is uncertain." with "The third entry recording date is certain.". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction adds "The amendment effective date is unavailable." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Negotiation comparison dossier
Entry slot 1
CLM-A: The first entry was submitted. (REF-40584)
End slot
Entry slot 2
CLM-B: The first entry was not recorded. (REF-40585)
End slot
Entry slot 3
The following qualifications concern a separate annex, not the numbered claim events.
End slot
Entry slot 4
The amendment effective date is unavailable.
End slot
Entry slot 5
The recorder is unnamed.
End slot
Entry slot 6
The third entry recording date is uncertain.
End slot
```

**Extraction, exact:**

```text
CLM-A: The first entry was submitted. (REF-40584) CLM-B: The first entry was not recorded. (REF-40585) The following qualifications concern a separate annex, not the numbered claim events. The amendment effective date is unavailable. The recorder is unnamed. The third entry recording date is certain.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The amendment effective date is unavailable. | True | True |

### shimmer2-auditor-document-147

Expected **OMISSION**; predicted **MATCH**. Category **B**. Catastrophe: **True**.

Evidence refs (generated and expected, identical): `REF-40588, REF-40589`.

**Expected reason:** The complete, delivered extraction omits the source content "The third entry recording date is uncertain." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction preserves all 2 explicit claims, including their scope and evidence, and retains both gaps (The amendment effective date is unavailable. What was entered first?) and the stated uncertainty.

**Assessment:** False preservation: the stated uncertainty was omitted, contradicting the reason.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Contracts comparison dossier
Entry slot 1
CLM-A: The first entry was submitted. (REF-40588)
End slot
Entry slot 2
CLM-B: The first entry was not recorded. (REF-40589)
End slot
Entry slot 3
The following qualifications concern a separate annex, not the numbered claim events.
End slot
Entry slot 4
The amendment effective date is unavailable.
End slot
Entry slot 5
What was entered first?
End slot
Entry slot 6
The third entry recording date is uncertain.
End slot
```

**Extraction, exact:**

```text
CLM-A: The first entry was submitted. (REF-40588) CLM-B: The first entry was not recorded. (REF-40589) The following qualifications concern a separate annex, not the numbered claim events. The amendment effective date is unavailable. What was entered first?
```

### shimmer2-auditor-document-151

Expected **DIVERGENCE**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40604, REF-40605`.

**Expected reason:** The extraction replaces "Whether the submission was submitted is unknown." with "Whether the submission was submitted is known.". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction adds "Which entry came previous?" and "Whether the submission was submitted is known." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Changed uncertainty is treated as addition alongside an unchanged gap; original uncertainty no longer remains.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Contracts comparison dossier
[segment=1]
CLM-A: The event did not occur. (REF-40604)
[/segment]
[segment=2]
CLM-B: The report of the event was recorded. (REF-40605)
[/segment]
[segment=3]
The following qualifications concern a separate annex, not the numbered claim events.
[/segment]
[segment=4]
The amendment effective date is unavailable.
[/segment]
[segment=5]
Which entry came previous?
[/segment]
[segment=6]
Whether the submission was submitted is unknown.
[/segment]
```

**Extraction, exact:**

```text
CLM-A: The event did not occur. (REF-40604) CLM-B: The report of the event was recorded. (REF-40605) The following qualifications concern a separate annex, not the numbered claim events. The amendment effective date is unavailable. Which entry came previous? Whether the submission was submitted is known.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| Which entry came previous? | True | True |
| Whether the submission was submitted is known. | False | True |

### shimmer2-auditor-document-152

Expected **OMISSION**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40608, REF-40609`.

**Expected reason:** The complete, delivered extraction omits the source content "The interpretation of the second entry remains unresolved." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction adds "The interpretation of the second entry remains unresolved." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Identifies exactly the missing source content, but calls it an unsupported extraction addition. Both label and directional reason reverse the comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | complete_reversed_comparison |

**Owned source, exact:**

```text
Regulation comparison dossier
[segment=1]
CLM-A: The event did not occur. (REF-40608)
[/segment]
[segment=2]
CLM-B: The report of the event was recorded. (REF-40609)
[/segment]
[segment=3]
The following qualifications concern a separate annex, not the numbered claim events.
[/segment]
[segment=4]
The amendment effective date is unavailable.
[/segment]
[segment=5]
The second entry was not submitted.
[/segment]
[segment=6]
The interpretation of the second entry remains unresolved.
[/segment]
```

**Extraction, exact:**

```text
CLM-A: The event did not occur. (REF-40608) CLM-B: The report of the event was recorded. (REF-40609) The following qualifications concern a separate annex, not the numbered claim events. The amendment effective date is unavailable. The second entry was not submitted.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The interpretation of the second entry remains unresolved. | True | False |

### shimmer2-auditor-document-156

Expected **DIVERGENCE**; predicted **DIVERGENCE**. Category **C**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40624, REF-40625`.

**Expected reason:** The extraction replaces "The first entry interpretation is unclear." with "The first entry interpretation is clear.". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction replaces "The first entry interpretation is clear." with "The first entry interpretation is unclear.". This changes the same proposition, referent, or evidence association rather than preserving it.

**Assessment:** Exact source-to-extraction replacement is reversed: unclear -> clear is described as clear -> unclear.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | No; correct relation, reversed reason |
| Reason supports expected class | Yes at relation-type level only; direction is wrong |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | reversed_replacement_reason |

**Owned source, exact:**

```text
Catalogue comparison dossier
[segment=1]
CLM-A: Approval applies only if the count exceeds 10 cards. (REF-40624)
[/segment]
[segment=2]
CLM-B: The measured count is 11 cards. (REF-40625)
[/segment]
[segment=3]
The following qualifications concern a separate annex, not the numbered claim events.
[/segment]
[segment=4]
The amendment effective date is unavailable.
[/segment]
[segment=5]
No first entry exists.
[/segment]
[segment=6]
The first entry interpretation is unclear.
[/segment]
```

**Extraction, exact:**

```text
CLM-A: Approval applies only if the count exceeds 10 cards. (REF-40624) CLM-B: The measured count is 11 cards. (REF-40625) The following qualifications concern a separate annex, not the numbered claim events. The amendment effective date is unavailable. No first entry exists. The first entry interpretation is clear.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The first entry interpretation is clear. | False | True |
| The first entry interpretation is unclear. | True | False |

### shimmer2-auditor-document-157

Expected **OMISSION**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40628, REF-40629`.

**Expected reason:** The complete, delivered extraction omits the source content "The first entry interpretation is unclear." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction adds "The first entry interpretation is unclear." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Identifies exactly the missing source content, but calls it an unsupported extraction addition. Both label and directional reason reverse the comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | complete_reversed_comparison |

**Owned source, exact:**

```text
Nonsense comparison dossier
[segment=1]
CLM-A: Approval applies only if the count exceeds 10 flims. (REF-40628)
[/segment]
[segment=2]
CLM-B: The measured count is 11 flims. (REF-40629)
[/segment]
[segment=3]
The following qualifications concern a separate annex, not the numbered claim events.
[/segment]
[segment=4]
The amendment effective date is unavailable.
[/segment]
[segment=5]
The amendment ratification status is missing.
[/segment]
[segment=6]
The first entry interpretation is unclear.
[/segment]
```

**Extraction, exact:**

```text
CLM-A: Approval applies only if the count exceeds 10 flims. (REF-40628) CLM-B: The measured count is 11 flims. (REF-40629) The following qualifications concern a separate annex, not the numbered claim events. The amendment effective date is unavailable. The amendment ratification status is missing.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The first entry interpretation is unclear. | True | False |

### shimmer2-auditor-document-160

Expected **MATCH**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40640, REF-40641`.

**Expected reason:** The extraction preserves all 2 explicit claims, including their scope and evidence, and retains both gaps (The amendment effective date is unavailable. The second entry event date is missing.) and the stated uncertainty.

**Generated reason, exact:** The extraction adds "End annex qualifications." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Extraction-only structural footer is treated as a substantive addition; the prompt explicitly excludes structural headings as new facts.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Negotiation comparison dossier
[segment=1]
CLM-A: The count is 11 offers in the northern section. (REF-40640)
[/segment]
[segment=2]
CLM-B: The southern section reports 17 offers. (REF-40641)
[/segment]
[segment=3]
The following qualifications concern a separate annex, not the numbered claim events.
[/segment]
[segment=4]
The amendment effective date is unavailable.
[/segment]
[segment=5]
The second entry event date is missing.
[/segment]
[segment=6]
The reporting date is unknown.
[/segment]
```

**Extraction, exact:**

```text
The following qualifications concern a separate annex, not the numbered claim events. The amendment effective date is unavailable. The second entry event date is missing. The reporting date is unknown. End annex qualifications. CLM-A: The count is 11 offers in the northern section. (REF-40640) CLM-B: The southern section reports 17 offers. (REF-40641)
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| End annex qualifications. | False | True |

### shimmer2-auditor-document-161

Expected **DIVERGENCE**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40644, REF-40645`.

**Expected reason:** The extraction replaces "The reporting date is unknown." with "The reporting date is known.". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction adds "The reporting date is known." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Changed uncertainty is treated as addition; original unknown status was replaced, not retained.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Contracts comparison dossier
[segment=1]
CLM-A: The count is 11 clauses in the northern section. (REF-40644)
[/segment]
[segment=2]
CLM-B: The southern section reports 17 clauses. (REF-40645)
[/segment]
[segment=3]
The following qualifications concern a separate annex, not the numbered claim events.
[/segment]
[segment=4]
The amendment effective date is unavailable.
[/segment]
[segment=5]
What was entered third?
[/segment]
[segment=6]
The reporting date is unknown.
[/segment]
```

**Extraction, exact:**

```text
CLM-A: The count is 11 clauses in the northern section. (REF-40644) CLM-B: The southern section reports 17 clauses. (REF-40645) The following qualifications concern a separate annex, not the numbered claim events. The amendment effective date is unavailable. What was entered third? The reporting date is known.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The reporting date is known. | False | True |

### shimmer2-auditor-document-162

Expected **OMISSION**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-40648, REF-40649`.

**Expected reason:** The complete, delivered extraction omits the source content "The reporting date is unknown." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction adds "The reporting date is unknown." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Identifies exactly the missing source content, but calls it an unsupported extraction addition. Both label and directional reason reverse the comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | complete_reversed_comparison |

**Owned source, exact:**

```text
Regulation comparison dossier
[segment=1]
CLM-A: The count is 11 permits in the northern section. (REF-40648)
[/segment]
[segment=2]
CLM-B: The southern section reports 17 permits. (REF-40649)
[/segment]
[segment=3]
The following qualifications concern a separate annex, not the numbered claim events.
[/segment]
[segment=4]
The amendment effective date is unavailable.
[/segment]
[segment=5]
Which entry came later?
[/segment]
[segment=6]
The reporting date is unknown.
[/segment]
```

**Extraction, exact:**

```text
CLM-A: The count is 11 permits in the northern section. (REF-40648) CLM-B: The southern section reports 17 permits. (REF-40649) The following qualifications concern a separate annex, not the numbered claim events. The amendment effective date is unavailable. Which entry came later?
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The reporting date is unknown. | True | False |

### shimmer2-auditor-document-270

Expected **MATCH**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-41080, REF-41081`.

**Expected reason:** The extraction preserves all 2 explicit claims, including their scope and evidence, and retains both gaps (The third entry was not recorded. The date is unavailable.) and the stated uncertainty.

**Generated reason, exact:** The extraction adds "The amendment ratification status remains unknown." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Astronomy comparison dossier
CLM-A: The event did not occur. (REF-41080)
Annotations
[1] CLM-B: The report of the event was recorded. (REF-41081)
[2] The following qualifications concern a separate annex, not the numbered claim events.
[3] The third entry was not recorded.
[4] The date is unavailable.
[5] The amendment ratification status remains unknown.
```

**Extraction, exact:**

```text
CLM-A: The event did not occur. (REF-41080) CLM-B: The report of the event was recorded. (REF-41081) The following qualifications concern a separate annex, not the numbered claim events. The third entry was not recorded. The date is unavailable. The amendment ratification status remains unknown.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The amendment ratification status remains unknown. | True | True |

### shimmer2-auditor-document-271

Expected **DIVERGENCE**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-41084, REF-41085`.

**Expected reason:** The extraction replaces "No first entry exists." with "No third entry exists.". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction adds "CLM-A: The event did not occur. (REF-41084)" without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Ecology comparison dossier
CLM-A: The event did not occur. (REF-41084)
Annotations
[1] CLM-B: The report of the event was recorded. (REF-41085)
[2] The following qualifications concern a separate annex, not the numbered claim events.
[3] The event did not occur.
[4] No first entry exists.
[5] The amendment ratification status remains unknown.
```

**Extraction, exact:**

```text
CLM-A: The event did not occur. (REF-41084) CLM-B: The report of the event was recorded. (REF-41085) The following qualifications concern a separate annex, not the numbered claim events. The event did not occur. No third entry exists. The amendment ratification status remains unknown.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| CLM-A: The event did not occur. (REF-41084) | True | True |

### shimmer2-auditor-document-272

Expected **OMISSION**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-41088, REF-41089`.

**Expected reason:** The complete, delivered extraction omits the source content "The event did not occur. The amendment ratification status is missing." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction adds "The amendment ratification status remains unknown." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Negotiation comparison dossier
CLM-A: The event did not occur. (REF-41088)
Annotations
[1] CLM-B: The report of the event was recorded. (REF-41089)
[2] The following qualifications concern a separate annex, not the numbered claim events.
[3] The event did not occur.
[4] The amendment ratification status is missing.
[5] The amendment ratification status remains unknown.
```

**Extraction, exact:**

```text
CLM-A: The event did not occur. (REF-41088) CLM-B: The report of the event was recorded. (REF-41089) The following qualifications concern a separate annex, not the numbered claim events. The amendment ratification status remains unknown.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The amendment ratification status remains unknown. | True | True |

### shimmer2-auditor-document-275

Expected **MATCH**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-41100, REF-41101`.

**Expected reason:** The extraction preserves all 2 explicit claims, including their scope and evidence, and retains both gaps (The event did not occur. The second entry event date is missing.) and the stated uncertainty.

**Generated reason, exact:** The extraction adds "The second entry event date is missing." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Claims unsupported addition of content present in the owned source; does not correctly explain the actual comparison.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Clinical comparison dossier
CLM-A: Approval applies only if the count exceeds 10 specimens. (REF-41100)
Annotations
[1] CLM-B: The measured count is 11 specimens. (REF-41101)
[2] The following qualifications concern a separate annex, not the numbered claim events.
[3] The event did not occur.
[4] The second entry event date is missing.
[5] The third entry recording date is uncertain.
```

**Extraction, exact:**

```text
CLM-A: Approval applies only if the count exceeds 10 specimens. (REF-41100) CLM-B: The measured count is 11 specimens. (REF-41101) The following qualifications concern a separate annex, not the numbered claim events. The event did not occur. The second entry event date is missing. The third entry recording date is uncertain.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The second entry event date is missing. | True | True |

### shimmer2-auditor-document-276

Expected **DIVERGENCE**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-41104, REF-41105`.

**Expected reason:** The extraction replaces "What was entered third?" with "What was entered second?". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction adds "What was entered third?" without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Old wording of a changed question is falsely called an addition; reversing orientation still yields DIVERGENCE.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Device comparison dossier
CLM-A: Approval applies only if the count exceeds 10 pulses. (REF-41104)
Annotations
[1] CLM-B: The measured count is 11 pulses. (REF-41105)
[2] The following qualifications concern a separate annex, not the numbered claim events.
[3] The event did not occur.
[4] What was entered third?
[5] The third entry recording date is uncertain.
```

**Extraction, exact:**

```text
CLM-A: Approval applies only if the count exceeds 10 pulses. (REF-41104) CLM-B: The measured count is 11 pulses. (REF-41105) The following qualifications concern a separate annex, not the numbered claim events. The event did not occur. What was entered second? The third entry recording date is uncertain.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| What was entered third? | True | False |

### shimmer2-auditor-document-277

Expected **OMISSION**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-41108, REF-41109`.

**Expected reason:** The complete, delivered extraction omits the source content "The event did not occur. Which entry came later?" while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction adds "Which entry came later?" without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Calls one omitted qualification an addition; two qualifications were omitted. Reversal-compatible fragment, but not a complete account even after reversal.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | partial_reversed_omission |

**Owned source, exact:**

```text
Procurement comparison dossier
CLM-A: Approval applies only if the count exceeds 10 crates. (REF-41108)
Annotations
[1] CLM-B: The measured count is 11 crates. (REF-41109)
[2] The following qualifications concern a separate annex, not the numbered claim events.
[3] The event did not occur.
[4] Which entry came later?
[5] The third entry recording date is uncertain.
```

**Extraction, exact:**

```text
CLM-A: Approval applies only if the count exceeds 10 crates. (REF-41108) CLM-B: The measured count is 11 crates. (REF-41109) The following qualifications concern a separate annex, not the numbered claim events. The third entry recording date is uncertain.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| Which entry came later? | True | False |

### shimmer2-auditor-document-280

Expected **MATCH**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-41120, REF-41121`.

**Expected reason:** The extraction preserves all 2 explicit claims, including their scope and evidence, and retains both gaps (The event did not occur. The date is unavailable.) and the stated uncertainty.

**Generated reason, exact:** The extraction adds "The date is unavailable. Whether the submission was submitted is unknown." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Two qualifications present in both sides are concatenated and called an unsupported addition; source annotation markers interrupt the literal substring but not its meaning.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Astronomy comparison dossier
CLM-A: The count is 11 exposures in the northern section. (REF-41120)
Annotations
[1] CLM-B: The southern section reports 17 exposures. (REF-41121)
[2] The following qualifications concern a separate annex, not the numbered claim events.
[3] The event did not occur.
[4] The date is unavailable.
[5] Whether the submission was submitted is unknown.
```

**Extraction, exact:**

```text
CLM-A: The count is 11 exposures in the northern section. (REF-41120) CLM-B: The southern section reports 17 exposures. (REF-41121) The following qualifications concern a separate annex, not the numbered claim events. The event did not occur. The date is unavailable. Whether the submission was submitted is unknown.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The date is unavailable. Whether the submission was submitted is unknown. | False | True |

### shimmer2-auditor-document-281

Expected **DIVERGENCE**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-41124, REF-41125`.

**Expected reason:** The extraction replaces "The amendment ratification status is missing." with "The amendment ratification status is known.". This changes the same proposition, referent, or evidence association rather than preserving it.

**Generated reason, exact:** The extraction adds "The amendment ratification status is missing." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Old wording of a changed status is falsely called an addition; reversing orientation still yields DIVERGENCE.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | not_explained_by_orientation |

**Owned source, exact:**

```text
Ecology comparison dossier
CLM-A: The count is 11 quadrats in the northern section. (REF-41124)
Annotations
[1] CLM-B: The southern section reports 17 quadrats. (REF-41125)
[2] The following qualifications concern a separate annex, not the numbered claim events.
[3] No first entry exists.
[4] The amendment ratification status is missing.
[5] Whether the submission was submitted is unknown.
```

**Extraction, exact:**

```text
CLM-A: The count is 11 quadrats in the northern section. (REF-41124) CLM-B: The southern section reports 17 quadrats. (REF-41125) The following qualifications concern a separate annex, not the numbered claim events. No first entry exists. The amendment ratification status is known. Whether the submission was submitted is unknown.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The amendment ratification status is missing. | True | False |

### shimmer2-auditor-document-282

Expected **OMISSION**; predicted **ADDITION**. Category **B**. Catastrophe: **False**.

Evidence refs (generated and expected, identical): `REF-41128, REF-41129`.

**Expected reason:** The complete, delivered extraction omits the source content "No first entry exists. The first entry recording date is missing." while retaining the remaining material. This is a substantive omission, not a transport failure.

**Generated reason, exact:** The extraction adds "The first entry recording date is missing." without support in any owned source span. All original claims and qualifications remain.

**Assessment:** Calls one omitted qualification an addition; two qualifications were omitted. Reversal-compatible fragment, but not a complete account even after reversal.

| Requested diagnostic | Finding |
|---|---|
| Evidence selection correct | Yes |
| Refusal/status correct | Yes |
| Only relation label wrong | No |
| Relation and reason both wrong | Yes |
| Reason supports expected class | No complete source-grounded account of the expected relation |
| Reason supports predicted class | Rhetorically yes; no complete source-grounded justification |
| Merely label-token mapping | No |
| Directionality | partial_reversed_omission |

**Owned source, exact:**

```text
Negotiation comparison dossier
CLM-A: The count is 11 offers in the northern section. (REF-41128)
Annotations
[1] CLM-B: The southern section reports 17 offers. (REF-41129)
[2] The following qualifications concern a separate annex, not the numbered claim events.
[3] No first entry exists.
[4] The first entry recording date is missing.
[5] Whether the submission was submitted is unknown.
```

**Extraction, exact:**

```text
CLM-A: The count is 11 offers in the northern section. (REF-41128) CLM-B: The southern section reports 17 offers. (REF-41129) The following qualifications concern a separate annex, not the numbered claim events. Whether the submission was submitted is unknown.
```

Quoted-content substring check (diagnostic only; formatting can interrupt a true semantic match):

| Quoted text | Literally in source | Literally in extraction |
|---|---|---|
| The first entry recording date is missing. | True | False |

## Appendix C. Complete dataset feature summaries

Each numeric cell is mean [minimum, maximum]. All 300 individual feature records, exact categorical counts and source hashes are in diagnosis.json. Token-field attribution is approximate at subword boundaries; total token counts are exact.

### TRAIN

| Class | n | Target tokens | Prompt tokens | Reason words | Reason chars | Refs | Source spans |
|---|---:|---|---|---|---|---|---|
| MATCH | 48 | 97.542 [87, 110] | 778.333 [680, 900] | 29.792 [27, 33] | 198.125 [175, 224] | 2.062 [1, 3] | 1.000 [1, 1] |
| DIVERGENCE | 48 | 115.875 [90, 153] | 776.021 [684, 899] | 29.979 [23, 40] | 213.708 [165, 295] | 2.062 [1, 3] | 1.000 [1, 1] |
| OMISSION | 48 | 102.229 [85, 127] | 763.167 [674, 890] | 29.062 [25, 36] | 203.375 [174, 241] | 2.062 [1, 3] | 1.000 [1, 1] |
| ADDITION | 48 | 87.250 [78, 96] | 785.333 [692, 908] | 23.500 [22, 26] | 161.062 [147, 168] | 2.062 [1, 3] | 1.000 [1, 1] |
| INSUFFICIENT_EVIDENCE | 48 | 13.000 [13, 13] | 687.521 [624, 777] | 0.000 [0, 0] | 0.000 [0, 0] | 0.000 [0, 0] | 1.000 [1, 1] |

#### TRAIN: MATCH

- template_family: {"discourse": 12, "enumerated": 12, "sectioned": 12, "tabular": 12}
- rendering_template: {"prose": 3, "bullet_list": 3, "form_fields": 3, "question_answer": 3, "memo": 3, "compact_table": 3, "multi_row_table": 3, "nested_clauses": 3, "mixed_prose_table": 3, "correspondence": 3, "meeting_minutes": 3, "incident_report": 3, "structured_notice": 3, "checklist": 3, "dialogue": 3, "comparison_matrix": 3}
- structure: {"0": 5, "1": 5, "2": 5, "3": 4, "4": 4, "5": 4, "6": 3, "7": 3, "8": 3, "9": 4, "10": 4, "11": 4}
- transformation: {"complete_ordered": 9, "reordered_preserving_scope": 12, "claims_after_qualifiers": 6, "multi_clause_faithful": 12, "explicit_refusal_rejected": 9}
- domain: {"negotiation": 4, "procurement": 5, "contracts": 6, "catalogue": 6, "regulation": 6, "nonsense": 6, "device": 5, "ecology": 4, "astronomy": 3, "clinical": 3}
- id_mod5: {"0": 48}
- first_ref_mod20: {"0": 48}
- delivery_complete: {"True": 48}
- status: {"absent": 48}
- target_prefix: {"{\"items\":[{\"confidence\":\"CONFIDENT\",\"finding\":\"MATCH\",\"": 48}
- Relation-content target-token positions, zero-based: [[16, 17]]
- Token-field counts: {"relation": 96, "reason": 2018, "evidence": 840, "structure": 1680, "termination": 48}
- Class-exclusive extraction words with document frequency >=3: {"end": 18}

#### TRAIN: DIVERGENCE

- template_family: {"discourse": 12, "enumerated": 12, "sectioned": 12, "tabular": 12}
- rendering_template: {"prose": 3, "bullet_list": 3, "form_fields": 3, "question_answer": 3, "memo": 3, "compact_table": 3, "multi_row_table": 3, "nested_clauses": 3, "mixed_prose_table": 3, "correspondence": 3, "meeting_minutes": 3, "incident_report": 3, "structured_notice": 3, "checklist": 3, "dialogue": 3, "comparison_matrix": 3}
- structure: {"0": 5, "1": 5, "2": 5, "3": 4, "4": 4, "5": 4, "6": 3, "7": 3, "8": 3, "9": 4, "10": 4, "11": 4}
- transformation: {"core_claim_mutation": 9, "correct_words_wrong_evidence": 14, "uncertainty_replaced_by_certainty": 6, "gap_referent_or_temporal_role_changed": 19}
- domain: {"contracts": 4, "catalogue": 5, "regulation": 6, "nonsense": 6, "clinical": 6, "astronomy": 6, "procurement": 5, "negotiation": 4, "ecology": 3, "device": 3}
- id_mod5: {"1": 48}
- first_ref_mod20: {"4": 48}
- delivery_complete: {"True": 48}
- status: {"absent": 48}
- target_prefix: {"{\"items\":[{\"confidence\":\"CONFIDENT\",\"finding\":\"DIVERGEN": 48}
- Relation-content target-token positions, zero-based: [[16, 17, 18, 19]]
- Token-field counts: {"relation": 192, "reason": 2802, "evidence": 840, "structure": 1680, "termination": 48}
- Class-exclusive extraction words with document frequency >=3: {"known": 6}

#### TRAIN: OMISSION

- template_family: {"discourse": 12, "enumerated": 12, "sectioned": 12, "tabular": 12}
- rendering_template: {"prose": 3, "bullet_list": 3, "form_fields": 3, "question_answer": 3, "memo": 3, "compact_table": 3, "multi_row_table": 3, "nested_clauses": 3, "mixed_prose_table": 3, "correspondence": 3, "meeting_minutes": 3, "incident_report": 3, "structured_notice": 3, "checklist": 3, "dialogue": 3, "comparison_matrix": 3}
- structure: {"0": 5, "1": 5, "2": 5, "3": 4, "4": 4, "5": 4, "6": 3, "7": 3, "8": 3, "9": 4, "10": 4, "11": 4}
- transformation: {"first_gap_omission": 9, "second_gap_omission": 12, "uncertainty_omission": 6, "scoped_claim_omission": 12, "simultaneous_gap_omission": 9}
- domain: {"regulation": 4, "nonsense": 5, "clinical": 6, "astronomy": 6, "device": 6, "ecology": 6, "catalogue": 5, "contracts": 4, "negotiation": 3, "procurement": 3}
- id_mod5: {"2": 48}
- first_ref_mod20: {"8": 48}
- delivery_complete: {"True": 48}
- status: {"absent": 48}
- target_prefix: {"{\"items\":[{\"confidence\":\"CONFIDENT\",\"finding\":\"OMISSION": 48}
- Relation-content target-token positions, zero-based: [[16, 17, 18]]
- Token-field counts: {"relation": 144, "reason": 2195, "evidence": 840, "structure": 1680, "termination": 48}
- Class-exclusive extraction words with document frequency >=3: {}

#### TRAIN: ADDITION

- template_family: {"discourse": 12, "enumerated": 12, "sectioned": 12, "tabular": 12}
- rendering_template: {"prose": 3, "bullet_list": 3, "form_fields": 3, "question_answer": 3, "memo": 3, "compact_table": 3, "multi_row_table": 3, "nested_clauses": 3, "mixed_prose_table": 3, "correspondence": 3, "meeting_minutes": 3, "incident_report": 3, "structured_notice": 3, "checklist": 3, "dialogue": 3, "comparison_matrix": 3}
- structure: {"0": 5, "1": 5, "2": 5, "3": 4, "4": 4, "5": 4, "6": 3, "7": 3, "8": 3, "9": 4, "10": 4, "11": 4}
- transformation: {"approval_invention": 9, "rule_invention": 12, "verification_invention": 6, "cause_invention": 12, "outcome_invention": 9}
- domain: {"clinical": 4, "astronomy": 5, "device": 6, "ecology": 6, "procurement": 6, "negotiation": 6, "nonsense": 5, "regulation": 4, "contracts": 3, "catalogue": 3}
- id_mod5: {"3": 48}
- first_ref_mod20: {"12": 48}
- delivery_complete: {"True": 48}
- status: {"absent": 48}
- target_prefix: {"{\"items\":[{\"confidence\":\"CONFIDENT\",\"finding\":\"ADDITION": 48}
- Relation-content target-token positions, zero-based: [[16, 17]]
- Token-field counts: {"relation": 96, "reason": 1524, "evidence": 840, "structure": 1680, "termination": 48}
- Class-exclusive extraction words with document frequency >=3: {"all": 9, "an": 18, "approved": 9, "be": 12, "caused": 12, "entries": 9, "equipment": 12, "every": 18, "external": 12, "independent": 6, "inspector": 6, "overall": 9, "passed": 9, "qualification": 6, "requires": 12, "reservations": 9, "result": 12, "review": 9, "rule": 12, "signed": 12, "supervisor": 9, "twice": 12, "verified": 6, "vibration": 12, "without": 9}

#### TRAIN: INSUFFICIENT_EVIDENCE

- template_family: {"discourse": 12, "enumerated": 12, "sectioned": 12, "tabular": 12}
- rendering_template: {"prose": 3, "bullet_list": 3, "form_fields": 3, "question_answer": 3, "memo": 3, "compact_table": 3, "multi_row_table": 3, "nested_clauses": 3, "mixed_prose_table": 3, "correspondence": 3, "meeting_minutes": 3, "incident_report": 3, "structured_notice": 3, "checklist": 3, "dialogue": 3, "comparison_matrix": 3}
- structure: {"0": 5, "1": 5, "2": 5, "3": 4, "4": 4, "5": 4, "6": 3, "7": 3, "8": 3, "9": 4, "10": 4, "11": 4}
- transformation: {"interrupted_claim": 9, "unresolved_deictic": 12, "unbound_quotation": 6, "missing_owned_original": 12, "ambiguous_qualification": 9}
- domain: {"device": 4, "ecology": 5, "procurement": 6, "negotiation": 6, "catalogue": 6, "contracts": 6, "astronomy": 5, "clinical": 4, "regulation": 3, "nonsense": 3}
- id_mod5: {"4": 48}
- first_ref_mod20: {"16": 36, "None": 12}
- delivery_complete: {"False": 9, "True": 39}
- status: {"refused": 48}
- target_prefix: {"{\"items\":[],\"status\":\"refused\"}": 48}
- Relation-content target-token positions, zero-based: [[]]
- Token-field counts: {"relation": 0, "reason": 0, "evidence": 0, "structure": 576, "termination": 48}
- Class-exclusive extraction words with document frequency >=3: {"as": 9, "mentioned": 9, "or": 9, "referred": 12, "stated": 9, "statement": 12, "that": 12, "there": 9, "this": 12}

### DEV

| Class | n | Target tokens | Prompt tokens | Reason words | Reason chars | Refs | Source spans |
|---|---:|---|---|---|---|---|---|
| MATCH | 12 | 99.667 [96, 106] | 815.000 [758, 886] | 30.417 [29, 33] | 199.833 [185, 220] | 2.167 [2, 3] | 1.000 [1, 1] |
| DIVERGENCE | 12 | 110.417 [95, 153] | 809.667 [754, 887] | 29.333 [25, 35] | 213.000 [175, 252] | 2.167 [2, 3] | 1.000 [1, 1] |
| OMISSION | 12 | 99.500 [95, 105] | 803.833 [749, 882] | 29.000 [27, 33] | 203.333 [185, 229] | 2.167 [2, 3] | 1.000 [1, 1] |
| ADDITION | 12 | 87.333 [86, 94] | 820.000 [768, 901] | 22.000 [22, 22] | 158.750 [147, 165] | 2.167 [2, 3] | 1.000 [1, 1] |
| INSUFFICIENT_EVIDENCE | 12 | 13.000 [13, 13] | 722.333 [686, 767] | 0.000 [0, 0] | 0.000 [0, 0] | 0.000 [0, 0] | 1.000 [1, 1] |

#### DEV: MATCH

- template_family: {"anchored": 12}
- rendering_template: {"timeline": 3, "register": 3, "machine_log": 3, "footnoted_record": 3}
- structure: {"9": 1, "10": 1, "11": 1, "3": 1, "4": 1, "5": 1, "6": 2, "7": 2, "8": 2}
- transformation: {"complete_ordered": 3, "claims_after_qualifiers": 6, "explicit_refusal_rejected": 3}
- domain: {"clinical": 3, "astronomy": 3, "ecology": 2, "device": 1, "negotiation": 2, "procurement": 1}
- id_mod5: {"0": 12}
- first_ref_mod20: {"0": 12}
- delivery_complete: {"True": 12}
- status: {"absent": 12}
- target_prefix: {"{\"items\":[{\"confidence\":\"CONFIDENT\",\"finding\":\"MATCH\",\"": 12}
- Relation-content target-token positions, zero-based: [[16, 17]]
- Token-field counts: {"relation": 24, "reason": 520, "evidence": 220, "structure": 420, "termination": 12}
- Class-exclusive extraction words with document frequency >=3: {"end": 6}

#### DEV: DIVERGENCE

- template_family: {"anchored": 12}
- rendering_template: {"timeline": 3, "register": 3, "machine_log": 3, "footnoted_record": 3}
- structure: {"9": 1, "10": 1, "11": 1, "3": 1, "4": 1, "5": 1, "6": 2, "7": 2, "8": 2}
- transformation: {"core_claim_mutation": 3, "uncertainty_replaced_by_certainty": 6, "gap_referent_or_temporal_role_changed": 3}
- domain: {"device": 3, "ecology": 3, "negotiation": 2, "procurement": 1, "contracts": 2, "catalogue": 1}
- id_mod5: {"1": 12}
- first_ref_mod20: {"4": 12}
- delivery_complete: {"True": 12}
- status: {"absent": 12}
- target_prefix: {"{\"items\":[{\"confidence\":\"CONFIDENT\",\"finding\":\"DIVERGEN": 12}
- Relation-content target-token positions, zero-based: [[16, 17, 18, 19]]
- Token-field counts: {"relation": 48, "reason": 625, "evidence": 220, "structure": 420, "termination": 12}
- Class-exclusive extraction words with document frequency >=3: {"known": 5}

#### DEV: OMISSION

- template_family: {"anchored": 12}
- rendering_template: {"timeline": 3, "register": 3, "machine_log": 3, "footnoted_record": 3}
- structure: {"9": 1, "10": 1, "11": 1, "3": 1, "4": 1, "5": 1, "6": 2, "7": 2, "8": 2}
- transformation: {"first_gap_omission": 3, "uncertainty_omission": 6, "simultaneous_gap_omission": 3}
- domain: {"procurement": 3, "negotiation": 3, "contracts": 2, "catalogue": 1, "regulation": 2, "nonsense": 1}
- id_mod5: {"2": 12}
- first_ref_mod20: {"8": 12}
- delivery_complete: {"True": 12}
- status: {"absent": 12}
- target_prefix: {"{\"items\":[{\"confidence\":\"CONFIDENT\",\"finding\":\"OMISSION": 12}
- Relation-content target-token positions, zero-based: [[16, 17, 18]]
- Token-field counts: {"relation": 36, "reason": 506, "evidence": 220, "structure": 420, "termination": 12}
- Class-exclusive extraction words with document frequency >=3: {}

#### DEV: ADDITION

- template_family: {"anchored": 12}
- rendering_template: {"timeline": 3, "register": 3, "machine_log": 3, "footnoted_record": 3}
- structure: {"9": 1, "10": 1, "11": 1, "3": 1, "4": 1, "5": 1, "6": 2, "7": 2, "8": 2}
- transformation: {"approval_invention": 3, "verification_invention": 6, "outcome_invention": 3}
- domain: {"catalogue": 3, "contracts": 3, "regulation": 2, "nonsense": 1, "clinical": 2, "astronomy": 1}
- id_mod5: {"3": 12}
- first_ref_mod20: {"12": 12}
- delivery_complete: {"True": 12}
- status: {"absent": 12}
- target_prefix: {"{\"items\":[{\"confidence\":\"CONFIDENT\",\"finding\":\"ADDITION": 12}
- Relation-content target-token positions, zero-based: [[16, 17]]
- Token-field counts: {"relation": 24, "reason": 372, "evidence": 220, "structure": 420, "termination": 12}
- Class-exclusive extraction words with document frequency >=3: {"all": 3, "an": 6, "approved": 3, "entries": 3, "every": 6, "independent": 6, "inspector": 6, "overall": 3, "passed": 3, "qualification": 6, "reservations": 3, "review": 3, "supervisor": 3, "verified": 6, "without": 3}

#### DEV: INSUFFICIENT_EVIDENCE

- template_family: {"anchored": 12}
- rendering_template: {"timeline": 3, "register": 3, "machine_log": 3, "footnoted_record": 3}
- structure: {"9": 1, "10": 1, "11": 1, "3": 1, "4": 1, "5": 1, "6": 2, "7": 2, "8": 2}
- transformation: {"interrupted_claim": 3, "unbound_quotation": 6, "ambiguous_qualification": 3}
- domain: {"nonsense": 3, "regulation": 3, "clinical": 2, "astronomy": 1, "device": 2, "ecology": 1}
- id_mod5: {"4": 12}
- first_ref_mod20: {"16": 12}
- delivery_complete: {"False": 3, "True": 9}
- status: {"refused": 12}
- target_prefix: {"{\"items\":[],\"status\":\"refused\"}": 12}
- Relation-content target-token positions, zero-based: [[]]
- Token-field counts: {"relation": 0, "reason": 0, "evidence": 0, "structure": 144, "termination": 12}
- Class-exclusive extraction words with document frequency >=3: {"as": 3, "mentioned": 3, "or": 3, "stated": 3, "there": 3}

## Appendix D. Training class windows and preservation

Class counts in four ten-update windows (40 exposures per window):

```json
{
  "10": {
    "INSUFFICIENT_EVIDENCE": 8,
    "MATCH": 4,
    "OMISSION": 11,
    "ADDITION": 9,
    "DIVERGENCE": 8
  },
  "60": {
    "INSUFFICIENT_EVIDENCE": 10,
    "OMISSION": 10,
    "DIVERGENCE": 11,
    "MATCH": 4,
    "ADDITION": 5
  },
  "70": {
    "OMISSION": 7,
    "DIVERGENCE": 8,
    "ADDITION": 5,
    "MATCH": 11,
    "INSUFFICIENT_EVIDENCE": 9
  },
  "120": {
    "DIVERGENCE": 8,
    "INSUFFICIENT_EVIDENCE": 12,
    "MATCH": 5,
    "OMISSION": 9,
    "ADDITION": 6
  }
}
```

Historical manifest: 143 text files hash-verified. Canonical labels/split and all historical artifacts remain unchanged.

```json
{
  "tuning\\auditor_canonical_execution\\dataset.json": "ba5289a1273eb51692a22bcd3b2d5f325643ea15e0d70b7e65f4c6147f7f3ec9",
  "tuning\\auditor_canonical_execution\\split.json": "befcd49cf5cf555708cc98f38f0f2a0168db18ae5ee71e5faf0910c573e1e0f8",
  "tuning\\auditor_canonical_execution\\execution_plan.json": "5d435a48e44fca157590f7c7f1696f160a55bc38c3632e96f9f4cdac62643680",
  "tuning\\second_domain_agnostic_v2\\runtime.py": "84110e53bc53a2e5fe134f81871dab8ad207034ebb3ff8bc6e832e5de2864cf3",
  "tools\\auditor_canonical_remote.py": "a11901d9fe85bcca55b4ff3c23eb26780333904c75c6d8b371fca00444a05616"
}
```
