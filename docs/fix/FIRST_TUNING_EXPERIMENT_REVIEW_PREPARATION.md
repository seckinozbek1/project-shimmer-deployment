# First tuning experiment review preparation

Date: 15 September 2026. Implementation commit: `4d7645da2d4d896b6657f09ce5ba2b84d209e6d8`.
Base: `c03c9fe65ce8c78569978f22d658d7c9696a4038` (v2 implementation `fee042a`).

## 1. Purpose

Prepare a frozen, independently reviewable basis for one future bounded tuning feasibility experiment. No tuning or model execution is authorized or performed here. Profile: `first-tuning-experiment-v1`; benchmark `semantic-benchmark-v2`; production contract `semantic-task-v1` remains frozen.

## 2. First experiment versus final acceptance

`FIRST_TUNING_EXPERIMENT_REVIEW_READY` requires all 192 valid independent first reviews, all 48 designated second reviews, resolved material disagreements, 72 reviewed held-out examples, all 16 templates, at least 64 unseen-template examples, frozen registration and passing leakage/access/governance/evidence gates. It is not checkpoint performance or training authorization. Final acceptance retains genuine independently contributed sealed material, external account/ACL, blind evaluation, stronger independent adjudication, family/domain generalization and future final thresholds. `FINAL_MODEL_ACCEPTANCE_READY` remains false.

## 3. Frozen criteria

These are **prospectively registered first-experiment decision thresholds**, not universal constants or near-perfect production claims. The request names 27 criteria but lists 28 IDs: P01-P11, A01-A10 and R01-R07. The registration preserves all rules as 27 independent numeric criteria plus R07, a derived conjunction of the six catastrophic limits. Final-model numeric thresholds remain unregistered and unchanged.

| ID | Metric | Rule |
|---|---|---|
| P01 | claim_precision | >= 0.95 |
| P02 | claim_recall | >= 0.95 |
| P03 | information_gap_precision | >= 0.95 |
| P04 | information_gap_recall | >= 0.95 |
| P05 | evidence_reference_precision | == 1.0 |
| P06 | evidence_reference_recall | >= 0.98 |
| P07 | refusal_precision | >= 0.95 |
| P08 | refusal_recall | >= 0.95 |
| P09 | semantic_completeness | >= 0.95 |
| P10 | contract_validity | >= 0.99 |
| P11 | uncertainty_preservation | >= 0.95 |
| A01 | overall_relation_accuracy | >= 0.95 |
| A02 | macro_relation_f1 | >= 0.93 |
| A03 | minimum_supported_relation_recall | >= 0.9 |
| A04 | refusal_precision | >= 0.95 |
| A05 | refusal_recall | >= 0.95 |
| A06 | reason_correctness | >= 0.9 |
| A07 | evidence_reference_precision | == 1.0 |
| A08 | evidence_reference_recall | >= 0.98 |
| A09 | contract_validity | >= 0.99 |
| A10 | uncertainty_preservation | >= 0.95 |
| R01 | independently_reviewed_fraction_of_selected_experimental_cohort | == 1.0 |
| R02 | double_independent_review_fraction | >= 0.25 |
| R03 | reviewed_structural_template_coverage | == 1.0 |
| R04 | reviewed_held_out_domain_examples | == 1.0 |
| R05 | reviewed_unseen_template_examples | >= 64 |
| R06 | worst_sufficiently_sampled_family_accepted_outcome_rate | >= 0.8 |

R01 denominator is the selected 192, R02 is the designated 48/192, R03 is 16/16 and R04 is 72/72. R06 requires at least four independently reviewed examples per document family; smaller samples are explicitly `insufficient_sample_for_family_gate`. Undefined metrics cannot pass. The frozen profile specifies metric populations and aggregation. Future saved-output evaluation requires complete unique coverage of all 153 selected non-TRAIN examples (39 DEV, 57 TEST, 57 public adversarial); missing outputs cannot disappear from the denominator. No checkpoint has been evaluated here.

## 4. Six unchanged catastrophic limits

Invented evidence references, unrouted/invented rule attribution, confident semantic reversal, truncation, producer source copying and governance violations each remain exactly zero. R07 requires all six limits to pass. The registration and every new implementation/export artifact are hash-bound by `benchmark/first_tuning_experiment_v1/freeze.json`.

## 5. Selection algorithm

Seed: `shimmer-first-review-20260915-v1`. Include all mandatory held-out rows first, apply exact role caps, then greedily maximize new document family, new template, new domain, least represented family, new semantic features and substantive producer coverage, with representation tie-breaks and SHA-256(seed + ID). Selection is deterministic even when input order is reversed. The same stratified mechanism selects the second-review subset. Administrative selection details stay outside exports.

## 6. Exact cohort composition

192 unique examples from 736 existing packets; the other 544 remain preserved and available. TRAIN 39, DEV 39, TEST 57, public adversarial 57. There are 72 substantive producer extractions, 72 information-gap cases, 59 uncertainty cases and 15 refusals. Both selections cover context ownership, contradictory sources, evidence selection, multi-span reasoning, all relations and both roles' refusal. No negative candidate output is promoted into gold. Authored family diversity does not establish human independence.

## 7. Role distribution

| Category | Cohort | Double review |
|---|---:|---:|
| auditor | 96 | 24 |
| producer | 96 | 24 |

Producer balance includes 72 substantive, 12 examined-empty and 12 refusal cases. The second subset includes 22 substantive, one examined-empty and one producer refusal.

## 8. Domain distribution

| Category | Cohort | Double review |
|---|---:|---:|
| astronomy | 36 | 5 |
| catalogue | 14 | 4 |
| clinical | 14 | 4 |
| contracts | 16 | 5 |
| device | 16 | 5 |
| ecology | 36 | 5 |
| negotiation | 16 | 5 |
| nonsense | 16 | 5 |
| procurement | 14 | 5 |
| regulation | 14 | 5 |

## 9. Template distribution

| Category | Cohort | Double review |
|---|---:|---:|
| attributed_dialogue | 15 | 3 |
| paired_register | 15 | 4 |
| revision_log | 15 | 4 |
| scope_notice | 15 | 3 |
| v2-bullet_list | 8 | 2 |
| v2-chronological_events | 8 | 3 |
| v2-compact_table | 14 | 3 |
| v2-form_fields | 8 | 3 |
| v2-machine_records | 14 | 3 |
| v2-memo_sections | 8 | 3 |
| v2-mixed_prose_table | 14 | 3 |
| v2-multirow_table | 14 | 3 |
| v2-nested_provisions | 14 | 3 |
| v2-paragraph | 8 | 2 |
| v2-question_answer | 8 | 3 |
| v2-transaction_register | 14 | 3 |

## 10. Document-family coverage

80/80 available document families, the maximum. Twelve families have six examples, 52 have two, and 16 have one. After successful review, only the twelve six-example families satisfy R06's minimum; 68 remain explicitly insufficient. No family is independently reviewed yet. The full per-family counts follow; a zero in the last column means absent from the second subset.

| Category | Cohort | Double review |
|---|---:|---:|
| dev-catalogue | 2 | 1 |
| dev-clinical | 2 | 0 |
| dev-contracts | 2 | 1 |
| dev-device | 2 | 0 |
| dev-negotiation | 1 | 0 |
| dev-nonsense | 2 | 1 |
| dev-procurement | 2 | 0 |
| dev-regulation | 2 | 1 |
| sealed_adversarial-catalogue | 2 | 0 |
| sealed_adversarial-clinical | 2 | 1 |
| sealed_adversarial-contracts | 2 | 1 |
| sealed_adversarial-device | 1 | 0 |
| sealed_adversarial-negotiation | 2 | 0 |
| sealed_adversarial-nonsense | 2 | 0 |
| sealed_adversarial-procurement | 2 | 1 |
| sealed_adversarial-regulation | 2 | 0 |
| test-catalogue | 2 | 0 |
| test-clinical | 2 | 0 |
| test-contracts | 1 | 0 |
| test-device | 2 | 1 |
| test-negotiation | 2 | 0 |
| test-nonsense | 2 | 1 |
| test-procurement | 2 | 1 |
| test-regulation | 2 | 0 |
| train-catalogue | 2 | 1 |
| train-clinical | 2 | 0 |
| train-contracts | 2 | 0 |
| train-device | 2 | 1 |
| train-negotiation | 2 | 1 |
| train-nonsense | 1 | 0 |
| train-procurement | 2 | 0 |
| train-regulation | 2 | 1 |
| v2-bullet_list-contracts | 2 | 0 |
| v2-bullet_list-device | 2 | 1 |
| v2-bullet_list-negotiation | 2 | 0 |
| v2-bullet_list-procurement | 2 | 1 |
| v2-chronological_events-catalogue | 2 | 1 |
| v2-chronological_events-clinical | 2 | 1 |
| v2-chronological_events-nonsense | 2 | 0 |
| v2-chronological_events-regulation | 2 | 1 |
| v2-compact_table-astronomy | 6 | 1 |
| v2-compact_table-device | 1 | 0 |
| v2-compact_table-ecology | 6 | 1 |
| v2-compact_table-negotiation | 1 | 1 |
| v2-form_fields-contracts | 2 | 1 |
| v2-form_fields-device | 2 | 0 |
| v2-form_fields-negotiation | 2 | 1 |
| v2-form_fields-procurement | 2 | 1 |
| v2-machine_records-astronomy | 6 | 0 |
| v2-machine_records-contracts | 1 | 1 |
| v2-machine_records-ecology | 6 | 1 |
| v2-machine_records-nonsense | 1 | 1 |
| v2-memo_sections-catalogue | 2 | 0 |
| v2-memo_sections-clinical | 2 | 1 |
| v2-memo_sections-nonsense | 2 | 1 |
| v2-memo_sections-regulation | 2 | 1 |
| v2-mixed_prose_table-astronomy | 6 | 1 |
| v2-mixed_prose_table-device | 1 | 1 |
| v2-mixed_prose_table-ecology | 6 | 1 |
| v2-mixed_prose_table-negotiation | 1 | 0 |
| v2-multirow_table-astronomy | 6 | 1 |
| v2-multirow_table-device | 1 | 1 |
| v2-multirow_table-ecology | 6 | 0 |
| v2-multirow_table-negotiation | 1 | 1 |
| v2-nested_provisions-astronomy | 6 | 1 |
| v2-nested_provisions-contracts | 1 | 0 |
| v2-nested_provisions-ecology | 6 | 1 |
| v2-nested_provisions-nonsense | 1 | 1 |
| v2-paragraph-contracts | 2 | 0 |
| v2-paragraph-device | 2 | 0 |
| v2-paragraph-negotiation | 2 | 1 |
| v2-paragraph-procurement | 2 | 1 |
| v2-question_answer-catalogue | 2 | 1 |
| v2-question_answer-clinical | 2 | 1 |
| v2-question_answer-nonsense | 2 | 0 |
| v2-question_answer-regulation | 2 | 1 |
| v2-transaction_register-astronomy | 6 | 1 |
| v2-transaction_register-contracts | 1 | 1 |
| v2-transaction_register-ecology | 6 | 1 |
| v2-transaction_register-nonsense | 1 | 0 |

## 11. Relation distribution

| Category | Cohort | Double review |
|---|---:|---:|
| ADDITION | 17 | 4 |
| DIVERGENCE | 21 | 5 |
| EMPTY | 12 | 1 |
| EXTRACTED | 72 | 22 |
| INSUFFICIENT_EVIDENCE | 15 | 2 |
| MATCH | 34 | 8 |
| OMISSION | 21 | 6 |

## 12. Held-out domains

All 72 required cases are selected: astronomy 36 and ecology 36. None become training-access labels, even after independent review. The second subset includes ten: five from each domain.

## 13. Unseen templates

114 selected unseen-template examples (57 TEST and 57 public adversarial), exceeding the registered minimum of 64. The second subset includes 24. These counts describe selection; independently reviewed counts are currently zero. Legacy `sealed_adversarial` IDs denote public adversarial material, never a genuinely blind final set.

## 14. Double review

Exactly 48 unique examples, a 25% subset: 24 producer/24 auditor, all ten domains, all 16 templates and 48 distinct document families. Includes two refusals, 22 information-gap cases and 18 uncertainty cases. All material disagreements require explicit independent-human adjudication; incompatible labels are never averaged.

## 15. Reviewer exports

- [Reviewer 1 ZIP](../../benchmark/first_tuning_experiment_v1/reviewer_1_first_tuning_v1.zip): 192 packets, 385 files, 405,960 bytes.
- [Reviewer 2 ZIP](../../benchmark/first_tuning_experiment_v1/reviewer_2_first_tuning_v1.zip): 48 packets, 97 files, 103,737 bytes.

Each packet has JSON and Markdown, plus one identical generic instruction file per export. Both contain original blank responses only. Instructions cover claims/gaps/uncertainty, evidence, semantic relations, numeric context, unsupported rule IDs, refusal and ambiguity without specific benchmark answers. No gold, split, family assignment, admin mapping, historic answer, selection rationale or first review is included. Packet/hash/admin manifests remain outside exports. Only distribute the applicable ZIP to each verified reviewer.

## 16. Validation, leakage and security

30 new deterministic tests plus 85 production checks pass: 115 total, with one pre-existing optional fixture skip. Six neutralise/fail/restore/pass effect proofs: two new export controls and four existing production controls. Exact filename and byte allowlists reject unknown files or altered packets. All 482 export files and 482 ZIP members pass gold, split, admin, historical answer, credential and privacy checks with zero findings. Privacy is established through byte-identical frozen synthetic packet provenance and no operator/durable inputs. No actual or fake human submissions were executed.

All 30 v1 baseline references, the frozen v2 tree and 106 historical A/B evidence entries verify unchanged. Four historical invalid outputs remain rejected. Production validators and model pins were not changed. Evidence is retained in [first_tuning_review_preparation_20260915](first_tuning_review_preparation_20260915/), with a separate artifact hash manifest and safe artifact scan.

## 17. Submission workflow

Follow [ADMIN_SUBMISSION.md](../../benchmark/first_tuning_experiment_v1/ADMIN_SUBMISSION.md). Verify human identity and independence in a separate administrative reviewer registry. Operator/self-review, LLMs, automated judges and authored-gold comparisons never count. Import either reviewer's returned files with the existing v2 `submit_review.py RESPONSE.json --journal ADMIN_DIRECTORY`; resolve material disagreement with `--resolve-packet PACKET_ID --resolution RESOLUTION.json --journal ADMIN_DIRECTORY`. Rebuild coverage using the new `review_status.py --journal ADMIN_DIRECTORY --reviewers REVIEWER_REGISTRY.json --out ADMIN_STATUS_DIRECTORY`. The documented commands use the resolved local Python executable. This layer reads the existing hash-bound journal without redesigning or fabricating submissions.

## 18. Training-label eligibility

Only independently reviewed, accepted TRAIN and DEV labels may enter the generated `training_access/` directory. Authored-only, held-out domains, TEST, public adversarial, regression and sealed/final labels stay excluded. Current eligible count is zero, with empty TRAIN/DEV outputs. If all selected reviews are accepted, at most 78 selected examples (39 TRAIN + 39 DEV) become automatically eligible. A future job receives only that directory, never surrounding admin target maps. Application filtering is not an external OS access boundary. No training is authorized by this preparation.

## 19. Sealed final policy

No sealed examples were fabricated or relabeled. A genuine sealed set is not required for first-experiment review readiness. Independently contributed sealed material under an external account/ACL remains mandatory for final acceptance, alongside blind evaluation and stricter future registered criteria.

## 20. Current readiness

**FIRST_TUNING_EXPERIMENT_REVIEW_PENDING**.

Registration and exports are frozen and validated. Actual independent first reviews: 0/192; designated second reviews: 0/48; independently reviewed held-out examples: 0/72. No actual disagreements or final adjudications exist. Training-eligible labels: zero. Final model acceptance remains false. No cloud, paid API, model generation, training, LoRA/SFT, model/revision/quantization change, full pipeline, multi-round or push occurred. User-owned `SHIMMER_HANDOFF.md` and `durable/` were untouched.

## 21. Next human action

Provide each packet-only ZIP to an operator-verified independent human. Collect 192 first reviews and 48 separate second reviews, adjudicate material disagreements, then rebuild coverage and eligible labels. The remaining 544 reviews are not a prerequisite for this first experiment. A later tuning run still requires explicit authorization; preparation is not permission to start it.
