# First tuning review cohort v2 correction

Date: 15 September 2026. Implementation commit: `befb46816efd66c51a301e037304bc187b1e3b90`.
Base: `489e71d` and `4d7645d`. Cohort revision: `first-tuning-review-cohort-v2`.
Acceptance profile remains **first-tuning-experiment-v1**, byte-for-byte unchanged.

## Outcome and scope

**FIRST_TUNING_EXPERIMENT_REVIEW_PENDING**. The approved local selection correction is complete. No human review had started, no human work was discarded, and no actual or fake human submissions were executed here. Current eligible training labels remain zero.

Previous cohort: **39 TRAIN / 39 DEV / 114 evaluation-style rows**.
New cohort: **78 TRAIN / 40 DEV / 72 mandatory held-out / 2 additional evaluation = 192**.
Potential independently validated TRAIN+DEV material increases from **78 to 118**, a gain of 40 (51.28%), subject to actual independent review and adjudication. DEV remains for validation/tuning decisions, not automatic gradient-training input.

The initial requested 80/40/72 allocation could cover only 14 frozen templates. `attributed_dialogue` occurs only in TEST, and `scope_notice` only in public adversarial material. The operator explicitly approved reserving one evaluation example for each, reducing TRAIN by two. No criterion, example split or template identity was modified. The initial incompatibility proof and subsequent approval record are preserved separately in the evidence directory.

## Frozen boundaries

All 27 registered quantitative criteria, derived R07 and six catastrophic zero limits are unchanged. Acceptance SHA-256: `8b70b096b128183707b2cc77c7577efebc8a5232336316a498f133306e3495da`.

`semantic-benchmark-v2`, authored targets, `semantic-task-v1`, model pins, production validators, governance/evidence constraints and historical model evidence remain frozen. The old registration/export tree also verifies unchanged. This is a new selection/export release with its own hash freeze, not a new acceptance profile. Final model acceptance remains false and still requires genuine independently contributed sealed material under an external account/ACL, blind evaluation and the separate stricter final criteria.

## Deterministic selection

Seed: `shimmer-review-rebalance-20260915-v2`. Include all 72 mandatory astronomy/ecology examples first. Select 78 TRAIN and 40 DEV with hard role caps (32/46 and 16/24 producer/auditor). All selected TRAIN/DEV producers must be substantive EXTRACTED examples; no empty/refusal producers are added merely for balance. Select one auditor from each otherwise missing evaluation template. Overall balance is exactly 96/96.

Within these constraints, reserve auditor refusal coverage, then prefer new document families, templates, domains and relations; penalize repeated families; prioritize uncertainty, gaps, contradictory source statements, context-only evidence traps, multi-span input, evidence selection and hard semantic tags. SHA-256(seed + example ID) resolves remaining ties. Tests reproduce the exact selection from original and reversed input order. Selection metadata and difficulty proxies remain administrative, never reviewer-visible. Authored feature counts are not claims of measured human difficulty or label reliability.

The double subset reserves refusal cases per role plus at least twelve gap and twelve uncertainty cases, then maximizes family diversity and source difficulty. It reaches 48/48 distinct families, all ten domains and all 16 templates. The two additional template representatives also appear in double review. No negative candidate output was converted into gold.

## Access and role distribution

| Access category | Total | Producer | Auditor |
|---|---:|---:|---:|
| held_out | 72 | 48 | 24 |
| train | 78 | 32 | 46 |
| dev | 40 | 16 | 24 |
| additional_evaluation | 2 | 0 | 2 |

All 72 mandatory held-out examples remain evaluation-only: astronomy 36 and ecology 36. The two extra evaluation examples also remain excluded from training. The ordinary split labels are unchanged: TRAIN 78, DEV 40, TEST 37 and public adversarial 37. These categories are disjoint and contain 192 unique IDs. `sealed_adversarial` is the legacy name for public adversarial data, not a genuine sealed final set.

All 48 tuning-access producers are substantive extraction (32 TRAIN, 16 DEV). The mandatory held-out producer population contributes 24 substantive, 12 examined-empty and 12 refusal examples; it was not altered. Total substantive producers remain 72/96.

## Domain distribution

| Category | First review | Double review |
|---|---:|---:|
| astronomy | 36 | 5 |
| catalogue | 12 | 5 |
| clinical | 12 | 4 |
| contracts | 18 | 5 |
| device | 18 | 5 |
| ecology | 36 | 5 |
| negotiation | 17 | 5 |
| nonsense | 14 | 4 |
| procurement | 17 | 5 |
| regulation | 12 | 5 |

## Template distribution and unseen coverage

| Category | First review | Double review |
|---|---:|---:|
| attributed_dialogue | 1 | 1 |
| paired_register | 32 | 8 |
| revision_log | 16 | 8 |
| scope_notice | 1 | 1 |
| v2-bullet_list | 15 | 4 |
| v2-chronological_events | 8 | 2 |
| v2-compact_table | 12 | 2 |
| v2-form_fields | 16 | 4 |
| v2-machine_records | 12 | 1 |
| v2-memo_sections | 8 | 3 |
| v2-mixed_prose_table | 12 | 2 |
| v2-multirow_table | 12 | 2 |
| v2-nested_provisions | 12 | 2 |
| v2-paragraph | 15 | 4 |
| v2-question_answer | 8 | 3 |
| v2-transaction_register | 12 | 1 |

All **16/16** templates are represented. **74** selected examples legitimately use the frozen unseen-template splits (72 held-out + two additional evaluation), exceeding the unchanged minimum of 64. No human-reviewed unseen examples exist yet. The second subset contains 12 unseen-template examples, including ten mandatory held-out examples.

## Document-family coverage and maximum proof

The old cohort represented 80 document families. The new allocation can access at most **54**: 20 TRAIN families + 20 DEV families + 12 mandatory held-out families + at most one new family per extra evaluation row. All 54 are selected. Thus retaining 80 is mathematically impossible under the approved allocation; the reduction does not arise from greedy selection failure.

Examples per family: 12 families have six, 18 have four, two have three, 20 have two, and two have one. The double subset uses 48 distinct families, the maximum for 48 examples.

| Category | First review | Double review |
|---|---:|---:|
| dev-catalogue | 2 | 1 |
| dev-clinical | 2 | 1 |
| dev-contracts | 2 | 1 |
| dev-device | 2 | 1 |
| dev-negotiation | 2 | 1 |
| dev-nonsense | 2 | 1 |
| dev-procurement | 2 | 1 |
| dev-regulation | 2 | 1 |
| sealed_adversarial-nonsense | 1 | 1 |
| test-nonsense | 1 | 1 |
| train-catalogue | 4 | 1 |
| train-clinical | 4 | 1 |
| train-contracts | 4 | 1 |
| train-device | 4 | 1 |
| train-negotiation | 4 | 1 |
| train-nonsense | 4 | 1 |
| train-procurement | 4 | 1 |
| train-regulation | 4 | 1 |
| v2-bullet_list-contracts | 4 | 1 |
| v2-bullet_list-device | 4 | 1 |
| v2-bullet_list-negotiation | 4 | 1 |
| v2-bullet_list-procurement | 3 | 1 |
| v2-chronological_events-catalogue | 2 | 1 |
| v2-chronological_events-clinical | 2 | 0 |
| v2-chronological_events-nonsense | 2 | 0 |
| v2-chronological_events-regulation | 2 | 1 |
| v2-compact_table-astronomy | 6 | 1 |
| v2-compact_table-ecology | 6 | 1 |
| v2-form_fields-contracts | 4 | 1 |
| v2-form_fields-device | 4 | 1 |
| v2-form_fields-negotiation | 4 | 1 |
| v2-form_fields-procurement | 4 | 1 |
| v2-machine_records-astronomy | 6 | 1 |
| v2-machine_records-ecology | 6 | 0 |
| v2-memo_sections-catalogue | 2 | 1 |
| v2-memo_sections-clinical | 2 | 1 |
| v2-memo_sections-nonsense | 2 | 0 |
| v2-memo_sections-regulation | 2 | 1 |
| v2-mixed_prose_table-astronomy | 6 | 1 |
| v2-mixed_prose_table-ecology | 6 | 1 |
| v2-multirow_table-astronomy | 6 | 1 |
| v2-multirow_table-ecology | 6 | 1 |
| v2-nested_provisions-astronomy | 6 | 1 |
| v2-nested_provisions-ecology | 6 | 1 |
| v2-paragraph-contracts | 4 | 1 |
| v2-paragraph-device | 4 | 1 |
| v2-paragraph-negotiation | 3 | 1 |
| v2-paragraph-procurement | 4 | 1 |
| v2-question_answer-catalogue | 2 | 1 |
| v2-question_answer-clinical | 2 | 1 |
| v2-question_answer-nonsense | 2 | 0 |
| v2-question_answer-regulation | 2 | 1 |
| v2-transaction_register-astronomy | 6 | 0 |
| v2-transaction_register-ecology | 6 | 1 |

### Exact excluded families

All 26 omitted families are non-held-out TEST/public-adversarial families outside the two approved additional evaluation slots. The frozen benchmark and their packets remain preserved:

- `sealed_adversarial-catalogue`
- `sealed_adversarial-clinical`
- `sealed_adversarial-contracts`
- `sealed_adversarial-device`
- `sealed_adversarial-negotiation`
- `sealed_adversarial-procurement`
- `sealed_adversarial-regulation`
- `test-catalogue`
- `test-clinical`
- `test-contracts`
- `test-device`
- `test-negotiation`
- `test-procurement`
- `test-regulation`
- `v2-compact_table-device`
- `v2-compact_table-negotiation`
- `v2-machine_records-contracts`
- `v2-machine_records-nonsense`
- `v2-mixed_prose_table-device`
- `v2-mixed_prose_table-negotiation`
- `v2-multirow_table-device`
- `v2-multirow_table-negotiation`
- `v2-nested_provisions-contracts`
- `v2-nested_provisions-nonsense`
- `v2-transaction_register-contracts`
- `v2-transaction_register-nonsense`

The remaining 544 benchmark packets are not deprecated and are available for later review. No representative was fabricated to inflate family coverage.

## Relations and difficult semantic cases

| Category | First review | Double review |
|---|---:|---:|
| ADDITION | 18 | 3 |
| DIVERGENCE | 18 | 3 |
| EMPTY | 12 | 1 |
| EXTRACTED | 72 | 19 |
| INSUFFICIENT_EVIDENCE | 30 | 18 |
| MATCH | 24 | 1 |
| OMISSION | 18 | 3 |

First review: **30 refusal/insufficiency, 72 information-gap, 60 uncertainty** cases. Double review: **18 refusal/insufficiency, 19 information-gap, 19 uncertainty** cases. The second subset contains 19 substantive producer extractions, one examined-empty producer and four producer refusals; its other 14 refusals are auditors. All required MATCH, DIVERGENCE, OMISSION, ADDITION, EXTRACTED and refusal classes are covered.

Both selections contain evidence-selection, context ownership, contradictory sources and multi-span cases, plus hard semantic transformations such as number, unit, entity/label changes, omission and unsupported certainty. The double selection deliberately does not maximize easy MATCH counts. Counts describe authored source strata; independent humans still determine actual labels and disagreement.

## Revised blinded exports

Only distribute the new ZIPs:

- [Reviewer 1 ZIP](../../benchmark/first_tuning_review_cohort_v2/reviewer_1_first_tuning_v1_cohort_v2.zip): 192 packets, 385 files, 458,778 bytes; SHA-256 `f67bcfccc88bf69179319780a60c2969d78ab72a18bbdf7d9a67838f55096206`.
- [Reviewer 2 ZIP](../../benchmark/first_tuning_review_cohort_v2/reviewer_2_first_tuning_v1_cohort_v2.zip): 48 packets, 97 files, 119,676 bytes; SHA-256 `c74b69fed194cf30944896b9aab299edefcdb2d13897a311a1d07cc93768db19`.

Each export contains JSON/Markdown packet pairs and one instruction file. Legitimate input and the nested blank semantic response are identical to the frozen v2 packet; only an opaque binding envelope is added. The instructions explain preserving that envelope and otherwise retain the existing semantic guidance. No gold, expected answers, transformations, splits, family identity, selection rationale, admin mappings, historical outputs, other reviewer answers or operator-private material is included.

## Supersession and submission safety

Old exports are explicitly **SUPERSEDED_BEFORE_HUMAN_REVIEW** in `supersession.json`, which records old ZIP hashes, old cohort hash and the replacement hash/revision. Their original bytes remain intact. `benchmark/first_tuning_review_active.json` identifies the active directory and freeze hash. Legacy entry points remain historical and must not be used for current coverage.

Every new return must preserve the complete `binding` + `review` envelope. Binding includes the revision, cohort-file SHA-256 and export-payload SHA-256. The payload digest covers all frozen base packets plus instructions before adding the binding, avoiding a circular self-hash. The admin manifest separately binds each final export file and actual ZIP bytes, checked by the active freeze before submission/status. Only the hashes are reviewer-visible, not membership lists or mappings.

The adapter validates current binding, export membership and verified human identity before invoking the unchanged v2 semantic submission journal. Native entries have exact-content envelope receipts. Coverage rejects legacy layouts, unreceipted entries, altered receipts, obsolete revision/hash values, wrong assignment membership, repeated export slots and inconsistent final-submission hashes. Two returns need distinct verified humans. A second-export response cannot substitute for the first slot. Adjudications require the current cohort/export-manifest binding and a verified independent resolver. Packet ID coincidence alone cannot bypass these checks.

The adapter is fail-closed on partial journal writes: no receipt means no accepted coverage. Status output must be a fresh empty directory separate from the journal and benchmark exports, preventing stale labels from being reused after a failed rebuild. Opaque public hashes establish version/content binding, not human identity or OS isolation; those remain operator-verified responsibilities.

## Human submission and training-access workflow

Use [ADMIN_SUBMISSION.md](../../benchmark/first_tuning_review_cohort_v2/ADMIN_SUBMISSION.md), including the new submit, resolve and status commands. Do not retrofit an old return with current hashes. Verify each person's independence; operator/self-review, LLMs, automated judges and authored-gold comparisons never count.

All 192 require valid first reviews. All designated 48 require second reviews by a different independent human. Material disagreement in semantic atoms, relation, refs, refusal/ambiguity or typed reason requires explicit adjudication; incompatible labels are not averaged. Only accepted selected TRAIN/DEV appear in the generated training-access directory. Held-out exclusion takes precedence even if an erroneous TRAIN split were supplied, as demonstrated by an effect proof. Current TRAIN and DEV files are empty.

Review readiness still does not authorize training or indicate checkpoint quality. Sealed final material is not required for first-experiment review readiness; it remains mandatory for final acceptance.

### Future performance evaluation boundary

No checkpoint metrics or performance acceptance were evaluated in this selection-only task. The frozen non-TRAIN evaluation population now contains 114 selected rows: 40 DEV, 72 held-out and two extras. The inherited R06 minimum remains four independently reviewed examples per family. After successful review, 30 selected families would meet that sample minimum and 24 would remain insufficient.

A downstream integration issue must be handled before future checkpoint scoring: the frozen legacy evaluator counts accepted TRAIN families for R06 while excluding TRAIN from its saved-output population. This rebalance creates 18 TRAIN families with four selected examples, exposing that inconsistency. The evaluator was not changed in this narrow selection/export correction, and no R06 pass is claimed. Future scoring must reconcile population handling without relaxing the frozen criterion or treating TRAIN predictions as generalization evidence. This does not prevent independent packet review or promote model readiness.

## Validation and retained evidence

- New cohort-v2 gate: **30 tests**, zero failures/errors, **four effect proofs** (held-out exclusion, obsolete binding rejection, unknown admin filename rejection, blank response/gold byte integrity).
- Preserved first-experiment gate: **30 tests**, two effect proofs, pass.
- Production governance/evidence gate: **85 checks**, four effect proofs, pass; one pre-existing optional fixture skip.
- Total: **145 passing checks**, **ten effect proofs**; no actual or fake human submissions, no models or network operations.
- New exports: **482 files and 482 ZIP members** scanned. **Zero** gold, admin, split, historical-answer, credential or privacy findings. Privacy basis is an exact allowlist of frozen synthetic legitimate input and blank responses plus opaque binding; no operator/durable input reads.
- All frozen v1/v2/first-registration hashes verify unchanged. **106 historical A/B evidence entries** verify, and **four historical invalid outputs** remain rejected.
- Maintained status command against an absent real-review journal reports reviewed=0, eligible_training=0, pending. It does not create submissions.

Evidence: [first_tuning_cohort_v2_20260915](first_tuning_cohort_v2_20260915/), including safe scan results and artifact hashes. The initial allocation proof is historical context, not the final status.

## Current status and next action

**FIRST_TUNING_EXPERIMENT_REVIEW_PENDING**.

Prepared: 192 first-review packets and 48 double-review packets. Actual independent reviews: **0/192 and 0/48**. Maximum future accepted TRAIN+DEV pool: **118**; actual eligible labels: **0**. Final model acceptance remains false.

Next human action: distribute only the cohort-v2 packet ZIPs to verified independent humans, collect complete bound envelopes, adjudicate material disagreements, and rebuild coverage using the new active workflow. Do not train or run a model from preparation readiness.

No cloud, paid API, model execution/generation, training, LoRA/SFT, model/revision/quantization change, full pipeline, multi-round or push occurred. Root `SHIMMER_HANDOFF.md` and `durable/` remain user-owned and untouched. Historical artifacts were not rewritten.
