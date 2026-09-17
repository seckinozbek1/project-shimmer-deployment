# Clean HPO initialization correction

**AUDITOR_OPTUNA_HPO_CLEAN_READY**

This local-only correction supersedes the initialization exposure in preparation commit `d00a136`. The split and four-parameter HPO search are unchanged. No cloud, backbone/model loading, backbone inference/training, forbidden evaluation-data access, Producer or push occurred. Only the explicitly authorized numerical linear-head fitting and affine scoring of cached vectors were performed.

## Frozen inputs and isolation

Input feature SHA-256: `06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287`.

Split SHA-256 remains `b630fc2fbd451c1a0b1a0c7240778031f1432f3a3aa0ad50dd31c37f8d12ba2b`: INNER_TRAIN1432 (358/class), INNER_VAL360 (90/class). Original feature order is retained within each selected population.

The fitting function receives only a copied1432x3072 FP32 INNER_TRAIN matrix and1432 INNER_TRAIN labels. Population mean/std use that matrix exclusively, ddof0, with1e-6 minimum std. No INNER_VAL vector is selected or scored until the initialization freeze has been flushed to disk. Split metadata necessarily contains validation IDs/labels, but these are never supplied to fitting. Tests poison validation features with NaN and validation labels with an invalid class while proving selected fitting inputs remain identical.

Head recipe is unchanged mathematically: zero W4x3072/bias4, seed7, FP32, full-population softmax CE plus .001*mean(W²), Adam LR.01, betas(.9,.999), epsilon1e-8, weight decay0, exactly200 updates, no early stopping. The local implementation uses NumPy2.0.2 FP32 analytic gradients and bias-corrected Adam, with one BLAS thread; it does not load a model or Torch. CPU/GPU bitwise arithmetic equivalence is not asserted. Two independent fits of this same fixed recipe produce bitwise-equal arrays, identical200-step traces and identical serialized hashes; there is no candidate selection between them.

`clean_initialization/FROZEN.json` binds the fitting IDs, feature and label bytes, recipe, implementation, repeatability and three artifacts. Its freeze precedes `starting_metrics.json`. Artifact hashes and freeze hash are rechecked after validation. Recorded INNER_VAL feature contributions, label contributions and gradient rows during initialization are all **zero**. No setting or artifact was changed using the resulting validation metrics.

This zero-exposure claim concerns the new HPO normalization/head fit. The explicitly required historical-step120 adapter remains unchanged; this correction does not erase its earlier training history or resolve source-family confounding.

## Artifact SHA-256

| HPO-only artifact | SHA-256 |
|---|---|
| INNER_TRAIN mean | `f812e63fec063220b9eaf27c3e9782005abad3cb66293491b55f93b38ad8aecf` |
| INNER_TRAIN std | `be4270e87f7df6ae7f9312bbeabc894c2f794ec897d4e9c5deeb52d84cdd2b68` |
| INNER_TRAIN head-200 | `8a9f94c6a78c01c15ddb4ac07e7e80586a7d1515aefcfc6f68040fc9181aa6e3` |

Artifacts and repeat-verification copies are under `tuning/auditor_optuna_hpo/clean_initialization/`. The historical full1792 head/mean/std and prior model/run evidence are unchanged and no longer appear in the active HPO initializer allowlist. Failed post-update1 state remains denied.

## Starting metrics, information only

| Population | Accuracy | Macro F1 | Minimum recall | Mean CE |
|---|---:|---:|---:|---:|
| INNER_TRAIN1432 | 1.000000 | 1.000000 | 1.000000 | .0651812495 |
| INNER_VAL360 | .763888889 | .764495785 | .655555556 | .7857790373 |

INNER_VAL recalls in MATCH/DIVERGENCE/OMISSION/ADDITION order: **.655555556 / .800000000 / .788888889 / .811111111**. Its confusion matrix is `[[59,9,10,12],[16,72,1,1],[8,3,71,8],[9,1,7,73]]`. These starting measurements neither select hyperparameters nor establish final Auditor quality. They were computed only after initialization was frozen.

## HPO and runtime compatibility

Every trial now restores the clean step120 classifier fork and the HPO-specific head, mean and std above. Fresh optimizer state, gradients and RNG reset remain required. Optuna4.5.0 TPE seed7; successive halving20/40;15 sequential trials;80 updates; the four LR/warmup/dropout ranges, objective, admission criteria and final gates are unchanged. `unchanged_search.json` compares the previous committed configuration: only the two initialization-exposure flags differ.

The future exact-runtime/package/base checks,16 paired reference/fork controls and one full1792-row raw-hidden compatibility pass remain mandatory. Live raw features are compared to the preserved current-runtime cache. Derived standardized vectors/logits are checked using the **new HPO-specific** normalization/head, never against the old full-TRAIN head. Compatibility observation does not read labels or compute loss. The single full feature pass additionally computes the HPO baseline on the1432 INNER_TRAIN IDs only. INNER_VAL labels are excluded from that baseline, with a poison-label fixture proving the boundary.

The prospective explosion formula remains `max(10*ln(4),20*baseline_CE)` and four times that for microbatches. Its baseline is now the clean INNER_TRAIN CE .0651812495; the floor still gives13.86294361/55.45177444. No thresholds were changed based on validation performance. Compatibility failure is NO_GO, with no cloud feature/head refit or cache fallback.

## Separate final-training semantics

HPO-only initializers are not automatically final production initializers. After a future HPO selects its four hyperparameters, a separately authorized final experiment must restore all1792 TRAIN rows, calculate/freeze full-TRAIN normalization, fit a fresh full-TRAIN head using the same deterministic200-update procedure, initialize the clean classifier fork, and run896 updates with checkpoints448/896. Only that final experiment may use the existing frozen DEV/challenge sets at their authorized evaluation points. No final-training execution is triggered by HPO selection or this correction.

## Validation and cost

**59/59 local deterministic tests pass**, including the original46 HPO tests and13 clean-initialization tests. Scope/secret scans and the updated seal pass. All prior current-runtime evidence and historical artifact hashes remain unchanged. External DEV, historical DEV, SHORTER, LONGER, HOLDOUT and protected successful access counts are **zero each** in the fitting audit. No existing evaluation set was opened.

The two deterministic fits and artifact writes took about **2.40 seconds locally**. No billable work was done. Cloud HPO estimates remain about74.75/96.73/319.70 minutes for low/typical/conservative-worst scenarios ($1.61/$2.08/$6.87 at the historical $1.29/hour). Recommended prospective budgets remain$7 soft/$9 hard; no cloud price was queried and no execution authorization was created. The one full compatibility pass remains; there is no cloud normalization/head refit. The changed initialization may change actual pruning outcomes, so the scenario mixes remain projections rather than predictions.

The active status and seal are in `tuning/auditor_optuna_hpo/LOCAL_VALIDATION.json`. Implementation: `tools/clean_auditor_hpo_initialization.py`; runtime admission and initializer bindings are updated in the HPO modules. No push.
