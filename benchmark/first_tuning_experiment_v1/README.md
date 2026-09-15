# First tuning experiment: registered review preparation

Profile **first-tuning-experiment-v1** references unchanged **semantic-benchmark-v2**
and **semantic-task-v1**. There is no training, inference, provider client or new model.

The operator enumerated 11 producer, 10 auditor and seven review/generalization rules
while requesting 27 criteria. This profile freezes **27 independent thresholds**
(P01-P11, A01-A10, R01-R06) and preserves **R07 separately as the derived conjunction
of six unchanged zero-catastrophic limits**. No enumerated rule is dropped or relaxed.

The first-experiment thresholds are prospective decision thresholds, not universal
constants or production/near-perfect acceptance standards. Final model acceptance
retains its independent sealed material, external account/ACL, blind evaluation,
stronger adjudication and future final numeric criteria. Its existing frozen profile
is unchanged. A final sealed set is not required just to satisfy this review gate.

## Prepared material

- Cohort: 192 unique examples, 96 producer/96 auditor, all 72 astronomy/ecology
  examples, all ten domains, all 16 templates and all 80 available document families.
- Unseen-template review: 114; substantive producer cases: 72 of 96.
- Double review: 48 examples, 24/24 roles, 48 distinct families, ten domains,
  16 templates, ten held-out-domain and 24 unseen-template examples.
- 544 other packets remain untouched and available for later review.
- 78 selected tuning-access examples (39 TRAIN/39 DEV) could become eligible after
  valid independent review. **Currently eligible: zero.**
- Saved-output evaluation is prospectively restricted to the 153 selected non-TRAIN
  examples, with complete unique coverage. This is not a blind final test.

Give Reviewer 1 only `reviewer_1_first_tuning_v1.zip` and Reviewer 2 only
`reviewer_2_first_tuning_v1.zip`. Both contain original blank packet JSON/Markdown
plus identical instructions. Do not send this README or any admin files with them.
There is no selection rationale, cohort mapping, split, gold, prior response or
acceptance answer inside either export. Filenames and bytes are strictly allowlisted.

## Administrator workflow

See [ADMIN_SUBMISSION.md](ADMIN_SUBMISSION.md). Use the existing v2 journal to import
actual human responses and resolve disagreements. No fake human submissions were
executed in this task. Operator-verified independent-human registry entries must
be supplied separately; the template has no approved people.

`review_status.py` reads real journal submissions to rebuild coverage. All 192 need
valid human review; each designated 48 needs two distinct people and any material
disagreement must be resolved. Resolvers also require operator-verified independence.
The journal's chronological submission hashes are compared without relying on
filename sort order. Author agreement is not a substitute for independent review.

Only accepted independent TRAIN/DEV labels are exported to a separate
`training_access/` directory. Held-out domains, test/public-adversarial labels and
the administrator's reviewed target map are excluded. Give future jobs that limited
directory only, with appropriate filesystem permissions. This is not authorization
to start training.

## Metrics and family rule

The profile records denominators and undefined-metric behavior. Refusal performance
is separate from substantive completeness/reason/confidence metrics. Supported
relations have at least one gold example; class support remains visible. Unassessed
reasons count against truth coverage. Reason truth/paraphrases still require the
existing independent rubric process; no fluency similarity is introduced.

R06 requires at least four independently reviewed examples per document family.
Smaller families are explicitly `insufficient_sample_for_family_gate`. With this
maximally diverse cohort, 12 families would qualify after review; 68 have only one
or two selected examples. Poor measured families cannot be excluded, and missing
outputs for an adequately reviewed family prevent a pass. No row-level precision
claim is inferred from this sparse family coverage.

## Validate locally

```powershell
& 'C:\Users\secki\anaconda3\python.exe' benchmark/first_tuning_experiment_v1/preparation_gate.py
```

The gate blocks network/model imports, verifies the frozen registration and source
benchmarks, checks deterministic cohorts/exports/archives, runs metric/access tests,
scans export bytes and verifies historical rejections. No review submissions are
created. `build.py` reproduces the initial release only when its freeze is unchanged.

Current status: **FIRST_TUNING_EXPERIMENT_REVIEW_PENDING**. Real human reviews are
the next action. REVIEW_READY will not mean FINAL_MODEL_ACCEPTANCE_READY or authorize
a training run. No cloud, paid API, models, training, LoRA/SFT, model changes, pipeline,
multi-round or push are performed.
