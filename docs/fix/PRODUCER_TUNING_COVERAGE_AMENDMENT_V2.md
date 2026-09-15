# Producer semantic policy V2 and label-curation review

**PRODUCER_TUNING_COVERAGE_NOT_READY**

**BALANCED_AGENT_ADJUDICATED_TUNING_EXPERIMENT_NOT_READY**

**FIRST_TUNING_EXPERIMENT_HUMAN_REVIEW_STATUS=PENDING**

Evidence: **training_label_curation_evidence / curation_only**. This is not independent generalization evidence, blind final evaluation, model-quality measurement or training authorization.

## Outcome and controlling limitation

The full substantive producer population was reviewed:32 TRAIN/32 DEV. Sixty labels otherwise qualify semantically (32 TRAIN/28 DEV), covering eight domains and all eight attainable templates. However, **all60 are quarantined and the new eligible producer manifests contain0 TRAIN/0 DEV**, because the parent ran a target-reading historical regression before the label freeze. This is a recorded governance failure, not a relaxed chronology requirement. Four DEV packets additionally fail the frozen completeness validator.

The auditor pool remains46 TRAIN/24 DEV. From this new release, the eligible conceptual combined pool is46 TRAIN/24 DEV, with no eligible new producer labels. If the quarantined labels were counted, arithmetic would be78 TRAIN/52 DEV; that is explicitly hypothetical and not an approved or accessible experiment manifest. Prior amendment-V1's20 TRAIN/16 DEV candidates remain unchanged in their historical namespace; they were not silently substituted into this V2 release.

## Starting limitation and methodology

Base `0114f66ba879654b35f68f0a2a6e221c69641f4c`. V1 had six support-validation cases,24 legacy projection limitations and four order/content disputes, plus an improper easy-reserve fallback. All those records remain intact.

Versions:

- `producer-semantic-policy-v2`
- `producer-coverage-amendment-v2`
- `producer-target-renderer-v2`

Method and population freeze commit: **`1c50cff8a89e1fcbfb113277211815ae15cd93f0`**.
Label/canonical-target freeze commit: **`3f5d4f4520e85db40b42a5c075a7166cd349bd7a`**.

The method was informed by aggregate prior diagnostics on already inspected TRAIN/DEV material. Generic fixtures and a separate methodology audit preceded method freeze; no target answers were provided to the fresh reviewers. A later preservation-harness timing violation is described below. These curation agreements must never be used as independent test scores, final model acceptance or near-perfect quality claims.

## Frozen semantic policy

Python retains source text, offsets, ordering, identity and reconstruction. Every explicit CLM assertion remains a claim; conflicting assertions are not reconciled and do not themselves create uncertainty. Only explicit epistemic source language creates an uncertainty atom. Source uncertainty and review ambiguity remain separate.

Atoms bind category, subject, attribute, ordinal, state, owned alias, exact refs and source-explicit origin to an exact support substring. Material identity ignores support/rationale wording but preserves all semantic distinctions. The canonical rendered question need not occur in the source. The support itself must occur exactly, retain relevant negation/modality and ground under the finite interpreter. Context-only refs cannot become owned evidence. The validator also checks completeness of meanings recognized by its finite grammar; successful labels are therefore constrained by that grammar, another reason agreement is curation evidence rather than independent capability evidence.

Absence ontology distinguishes missing information, explicit nonoccurrence and unknown whether an occurrence happened. Not recorded does not mean the underlying event did not happen; not submitted is separate from recording absence. Explicit absent entries retain ordinal referents. All six former non-submission constructions now pass their individual source-support grounding; one packet still fails overall completeness for the separate heading issue.

Deictic references resolve only to a unique owned referent. Competing named/ordinal entries or explicit plurality reject resolution. Submission noun identity survives an ordinal. Bare this/it in a recording question refers to the owned record; unrelated context does not supply a date role.

Temporal attributes distinguish recording, underlying event, submission, authorization, observation, reporting and effective time. An unspecified date is not automatically recording time. A unique immediately following same-record temporal question may establish its role. Unknown WHEN and unknown WHETHER remain different.

Order and content are explicit: ?What came next?? concerns entry order; a question about what a second entry contains concerns content plus ordinal2; ?What was entered first?? concerns content plus ordinal1. First/next and previous/later remain distinct. No packet-specific synonym table or embedding similarity was used.

Renderer V2 emits only existing compact span/claims/questions/uncertainty/status/refs fields. Stable semantic strings and sorted arrays make equivalent atoms byte-stable and distinct semantics different. Production schema, validators, model pins and source reconstruction were not modified.

## Pre-review tests and exact population

Before review: **26 generic tests and nine required effect proofs passed**. The audit caught and corrected, before freezing, negated absence, event versus recording nonoccurrence, temporal uncertainty versus occurrence uncertainty, ambiguous named deictics, ordinal submission identity, support cropping, numeric ordinal typing and missing semantic atoms. No policy change was made after review or comparison.

Population is exactly the entire source-only substantive producer inventory: **32 TRAIN/32 DEV,64 total,zero reserve**. Administrative family/split maps and existing gold-free packets were used. No empty/refusal fallback, TEST, adversarial, held-out astronomy/ecology, additional evaluation, final/sealed or regression example was included. Attainable coverage was frozen at **eight domains/eight templates**. Sixteen mandatory audits were selected prospectively (eight per split) across source features and diversity, using seed `producer-coverage-amendment-v2-20260915`.

## Fresh review and adjudication

Fresh A/B/C contexts independently read all64 packet-only inputs and emitted one review each. Fresh D saw only original packets and neutral A/B/C candidates. All agents attest assigned-workspace-only access, no prior answers, gold, network or model tools. They share a parent model family and filesystem: isolation is procedural, not OS-enforced or cross-model independence.

| Measure | Result |
|---|---:|
| Packets / TRAIN / DEV | 64 /32 /32 |
| Primaries expected/completed | 192/192 |
| Valid / invalid primaries | 180 /12 |
| Unanimous material agreement | 64/64 (100%, curation-only) |
| 2/3 majority-only / no majority | 0 /0 |
| Valid triple coverage | 60/64 (93.75%) |
| Claim/gap/uncertainty/ref/refusal unanimity | 64/64 each |
| Repairs / semantic retries | 0 /0 |
| Adjudications completed | 19/19 |
| Adjudications valid | 15/19 |
| Mandatory audit completed / valid | 16/16 /15/16 |
| Final unresolved annotation ambiguity | 0 |

The12 invalid judgments concern four DEV memo packets. Their individual submitted atoms have exact, valid source support; the completeness parser additionally interprets the heading ?Unresolved matters? as epistemic content. All three reviewers and D preserved the substantive source semantics but did not add that spurious heading-derived assertion. Frozen validation failures remain failures; they were not reclassified as passes or repaired with a new semantic retry. All four packets are excluded from the otherwise-qualified subset.

## Strict target-access timing failure

The parent executed `benchmark/first_tuning_review_cohort_v2/gate.py` after method commit but before label commit. That harness reads authored dataset records internally, including its historical-baseline checks. Its console output was aggregate test results, and no authored target contents were supplied to fresh reviewers. Nevertheless, the operator required target reads to wait until the label commit, so **strict_target_access_order_pass=false and governance_pass=false**.

`PRE_GOLD_ACCESS_AUDIT.json` records the action and was included in the label-freeze commit. The freeze still preceded the new-label legacy comparison; that narrower ordering is verified, without pretending the broader boundary was clean. All otherwise-qualified labels are quarantined outside eligible access.

A new `regression_phase_guard.py` requires a label-freeze manifest and verifies its exact contents in an actual40-character commit before starting target-reading regressions. The post-label audit uses this guard; a negative test verifies that missing freeze evidence blocks access first. This prevents recurrence in that maintained entry point but cannot undo the early historical read. No prior evidence was rewritten.

## Post-freeze legacy diagnostics

The new-label comparison started after commit `3f5d4f4`; its timestamp and freeze hash are in `GOLD_COMPARISON_STARTED.json`.

| Measure | Direct agreement |
|---|---:|
| Claims | 64/64 |
| Typed gaps | 58/64 |
| Typed uncertainty | 64/64 |
| Evidence refs | 64/64 |
| Refusal | 64/64 |
| Canonical wire differs from legacy free wording | 64/64 |

| Classification | Packets |
|---|---:|
| Semantic agreement | 58 |
| Real semantic disputes | 0 |
| Legacy projection limitations | 0 |
| Source-supported legacy under-specification | 5 |
| Source-proven machine semantic errors | 0 |
| Unresolved diagnostic cases | 1 |

The six typed-gap differences are explicit non-submission semantics missing from legacy gap targets. Five meet the pre-frozen source-grounding, triple-validity and final-validity rule for legacy under-specification. The sixth remains unresolved because the whole packet fails the memo-heading completeness check. Zero source-proven machine semantic errors does not erase the12 validation failures. Source supports, refs, machine typed labels, legacy projections and classification bases are preserved per discrepancy.

No policy, ontology, grounding rule or synonym was changed after target comparison. A summary counter initially counted the sole unresolved case twice; its nonsemantic accounting was corrected to1, with prior hashes and correction recorded in `metric_correction.json`. Labels, classifications and candidate decisions were unchanged.

## Candidate and coverage disposition

New **eligible** producer counts are0 TRAIN/0 DEV because governance is required for every candidate. The eligible directory contains empty TRAIN/DEV files and an explicit training_authorized=false manifest.

The following is **quarantined, not eligible**:

| Measure | TRAIN | DEV | Overall |
|---|---:|---:|---:|
| Otherwise-qualified labels | 32 | 28 | 60 |
| Gap cases | 32 | 28 | 60 |
| Explicit uncertainty | 26 | 24 | 50 |
| Multiple claims | 29 | 26 | 55 |
| Evidence-selection cases | 29 | 26 | 55 |

This quarantined subset spans **eight domains, eight templates and40 document families**. It meets numerical producer coverage before governance is applied. It is stored as `quarantined_producer_label_v2` in post-freeze evidence, not the eligible training-access namespace. No balanced execution manifest was issued.

Auditor candidates remain **46 TRAIN/24 DEV**, with prior96/96 relation/evidence/refusal agreement unchanged. New-release eligible conceptual totals are46 TRAIN/24 DEV; the quarantined hypothetical totals78 TRAIN/52 DEV cannot be used for training. Human first/second/adjudication counts remain0/0/0, PENDING.

## Validation and integrity

- Completed amendment audit: **41 tests, nine effect proofs**. Test success validates the recorded failures/quarantine; it does not imply readiness.
- Preserved cohort harness: **30 tests/four effect proofs**, with its early invocation explicitly retained as the timing failure.
- Production contracts: **85 passed checks/four effect proofs**, one existing optional skip, no generation.
- Frozen history: **961 machine-review-V1 files,692 machine-review-V2 files,406 amendment-V1 files** verified unchanged. All106 historical A/B hashes remain intact; all four historical rejections reproduced.
- Frozen semantic-benchmark-v2, semantic-task-v1,27 acceptance criteria, derived R07 and all six catastrophic zero limits remain unchanged.
- R06 retains >=0.80 and its non-TRAIN population. The114-row registered evaluation population is unchanged. A generic effect proof and real-population TRAIN-injection regression confirm TRAIN rows cannot alter R06 accounting/results. No model predictions were generated.
- Credential scan findings: zero. Exact synthetic packet hashes and agent attestations support reviewer privacy/isolation. The historical harness timing violation is reported separately, not hidden behind a clean credential scan.

## Exact next action

Do not train from the quarantined labels. Any subsequent prospectively authorized curation run must route target-reading regressions through the post-label-commit guard. Before freezing any revised parser, add generic structural-heading versus epistemic-assertion fixtures and resolve that distinction without changing this frozen release. The numerical label-curation result is promising only for label construction; protected non-TRAIN evaluation is still required for future model-quality claims.

No human review falsely claimed. No cloud, paid API, Shimmer model execution, training, LoRA/SFT, model/revision/quantization change, full pipeline, multi-round or push. All changes and commits are local.
