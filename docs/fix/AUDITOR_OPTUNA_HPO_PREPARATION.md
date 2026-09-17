# Auditor Optuna HPO — local preparation

**AUDITOR_OPTUNA_HPO_READY**

Prepared after `00d5dcd`. This status means local preparation and deterministic contract tests passed. It is not a finding that a real optimizer configuration is stable, a final Auditor PASS, or permission to launch. No real HPO trial has run. Prior `AUDITOR_JOINT_TRAINING_STABILIZATION_UNISOLATED` and `AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY` verdicts remain unchanged.

## Frozen inner split

Only `tuning/auditor_external_relation_v2/merged_four_way_train.jsonl` supplies data. The combined TRAIN/DEV records were not opened. Assignment sorts SHA-256 of canonical `["inner-split",7,class,source_family,id]` within each class's historical/external stratum, with ID tie-break. The first 10 historical and 80 external rows per class become INNER_VAL. Assignment is independent of input order and never redrawn between trials.

| Split | Total | Per class | Historical | External | PAWS | WikiAtomic |
|---|---:|---:|---:|---:|---:|---:|
| INNER_TRAIN | 1,432 | 358 | 152 (38/class) | 1,280 (320/class) | 640 | 640 |
| INNER_VAL | 360 | 90 | 40 (10/class) | 320 (80/class) | 160 | 160 |

IDs, labels and source-family classes are persisted in `tuning/auditor_optuna_hpo/split.json`. Canonical list SHA-256:

- INNER_TRAIN: `e2bcfb2052913a6a3d110c4e4376b79b89c908d2fee70d37635c4d5fefc73ef0`
- INNER_VAL: `9a02b591da3e37ac48880c5fd84087cad9a96d63608eb918aed1f410078d90c2`
- Complete assignments: `b630fc2fbd451c1a0b1a0c7240778031f1432f3a3aa0ad50dd31c37f8d12ba2b`

Source-family metadata stays in split/accounting records. Runtime classifier records contain only IDs, four-way labels, split marker, prompt hash and token IDs. All 1,792 prompts were reconstructed locally with the pinned tokenizer from normalized input fields only; every prompt/token hash matches the successful current-runtime receipts. No model was loaded or invoked.

**Initialization exposure:** as explicitly requested, head-200 and normalization remain fitted on the original full 1,792 TRAIN rows. Thus the new INNER_VAL labels were previously used by head fitting, and its features by normalization. This is optimizer/stability selection on an internal TRAIN subset, not untouched validation. No claim of unbiased validation or final generalization may be made from it. Historical/source provenance confounding also remains unresolved.

## Search and selection

Pinned Optuna 4.5.0; `TPESampler(seed=7, n_startup_trials=10)`; maximize; one sequential study, `n_jobs=1`, maximum 15 trials. Each trial has at most 80 updates, microbatch1, accumulation4, effective batch4. A single frozen hash-based INNER_TRAIN order supplies the first 320 distinct rows for every trial; no INNER_VAL gradients. The study cannot resume, retry, create a second study in the same output directory, or trigger full training.

| Parameter | Frozen search |
|---|---|
| Classifier-LoRA peak LR | log-uniform [1e-6, 1e-4] |
| Head LR | log-uniform [1e-4, 1e-3] |
| LoRA warmup updates | categorical [0, 5, 10, 20, 40] |
| LoRA dropout | categorical [0.0, 0.05] |

Nothing else is searched. AdamW betas(.9,.999), epsilon1e-8, weight decay0, clipping1.0 and existing head regularization remain fixed. At optimizer update `u>=1`, LoRA LR is `peak*min(1,u/warmup)` for positive warmup; zero warmup uses peak immediately. Head LR is constant. There is no scheduler after warmup. Base pin, historical step120 initializer, rank8, alpha16, targets, classes, data, head-fit/normalization methods and final quality gates remain frozen.

`SuccessiveHalvingPruner(min_resource=20, reduction_factor=2, min_early_stopping_rate=0, bootstrap_count=0)` receives the objective at20/40. Only its deterministic decision or prospective numerical failure prunes a trial. Update80 is evaluated and reported but not performance-pruned. The objective code enforces the resource cap because the pruner itself does not impose a maximum resource. See the [official Optuna 4.5.0 pruner documentation](https://optuna.readthedocs.io/en/v4.5.0/reference/generated/optuna.pruners.SuccessiveHalvingPruner.html).

At20/40/80, eval/no-grad on all360 frozen INNER_VAL rows records accuracy, macroF1, per-class recall, minimum recall, mean CE and confusion matrix. Score = `0.75*macroF1 + 0.25*minimum_recall`. Completed trials use update80. Tie-break: descending score, descending macroF1, descending minimum recall, ascending CE, ascending maximum observed eval-mode standardized control drift from update0, ascending LoRA peak LR, ascending trial number.

Only stable80-update trials with macroF1>=.60 and every recall>=.45 are eligible. If none qualify: `AUDITOR_OPTUNA_HPO_NO_CANDIDATE`. Otherwise only the four winning hyperparameters are frozen, with a separate future design restoring all1792 TRAIN rows, clean checkpoint0,896 updates and448/896 evaluations. No final training executes automatically. Existing frozen validation sets become available only to that separately authorized final experiment.

## Numerical stability and matched controls

Every microbatch checks hidden, standardized hidden, logits, CE/loss, gradients and trainable parameters for finite values. Every update checks gradients before/after clipping and parameters after step. NaN/Inf causes immediate Optuna numerical pruning, not a fallback. Scope violations, failed cache admission, base mutation, corrupted reset or unexpected runtime errors abort the study rather than silently continuing.

The prospective finite-explosion formula is unchanged: `mean_ceiling=max(10*ln(4),20*current_compatibility_TRAIN_CE)`; microbatch ceiling is four times that. The bound compatibility CE is .0858519748, yielding mean13.86294361 and micro55.45177444. The observed prior134.577728 failure would prune before backward. Thresholds are fixed before trials; no threshold is learned from outcomes. Evaluation forwards also reject nonfinite/catastrophic CE. Matched diagnostics record finite CE without making finite-CE pruning decisions; nonfinite tensors still invoke the mandatory numerical gate.

Telemetry records hidden/standardized L2, standardized max-absolute, logits min/max/max-absolute, CE, head/LoRA accumulated gradients, combined pre/post-clip norm, head/LoRA parameter norms and actual delta-vector norms, optimizer-group LRs, train/eval flags, dropout and dtype/autocast settings. Forward summaries are emitted before finite-CE pruning so the failing boundary is retained.

Fixed INNER_TRAIN control: `2e450e57adbff186b7762db2d022be6bc2587f65b5b4f1e3ba0995dd93d798b3`. At0/1/2/5/10/20/40/80, no-gradient eval and train forwards retain complete hidden/standardized/logit vectors and differences. Probe RNG seed7007 is fixed; Python/NumPy/Torch CPU/CUDA RNG state and all module mode flags are restored afterward. Parameter hashes and empty gradients are checked. These forwards do not consume training RNG or change the objective; their eval-mode drift is the specified late tie-break. They measure a reproducible mask contrast, not the whole distribution of dropout outcomes.

## Current-runtime reuse and trial reset

Artifacts remain local and hash-bound; no model tensors were deserialized in preparation:

| Artifact | SHA-256 |
|---|---|
| head-200 | `027c880e6c10a13f3e7354d12665ffacca5f7d68836291feaf195c167c13f915` |
| mean | `370b185841099279202b09540b45231f70fc1b109795faf520369964831678f5` |
| std | `1221aff7ce64f090635267884183baabbd521e9a1738221555f074b4478f304a` |
| TRAIN features | `06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287` |

Initial adapter SHA `733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6`, config SHA `af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6`. Failed post-update1 state is explicitly denied.

Future reuse admission checks exact Python/package/CUDA versions, base/tokenizer pins, NF4/BF16/FP32 preparation, architecture, prepared base-state hash, and initial adapter/head/normalization hashes. Sixteen reference/fork controls must agree with each other and the current cache. After reference removal, **one full1792-row pass** checks every hidden/standardized/logit vector against the saved current cache, exact predictions, aggregate F1 and bounded CE. Tolerances are rtol1e-4/atol2e-4. Failure is NO_GO; no extraction/refit fallback. This single pass also supplies the baseline; there is no repeated1792-row extraction or head fitting.

The loaded frozen base may be reused. Before every trial, restore immutable CPU snapshots of the clean classifier adapter/head; verify exact state hash; remove all gradients; set sampled dropout; reset training RNG to7; create a new AdamW with empty state. No moments, step counters, gradients, parameters or RNG progression leak from prior trials. Frozen-base checks run between trials and at checkpoints. Actual GPU admission/reset behavior remains a mandatory future check; local tests use synthetic state.

## Data boundaries and authorization

Successful access counts in local preparation: external DEV0, historical DEV0, SHORTER0, LONGER0, HOLDOUT0, protected0. A process audit rejects forbidden dataset opens before they occur; explicit data loaders also require exact allowed paths and hashes. Denial tests use invented paths, not real forbidden datasets. Only TRAIN rows exist in the new records file. No challenge definitions or protected payloads are included. Metadata naming historical gates is not evaluation-data access.

`preparation_receipt.json` records process-level and loader receipts. The future workload installs the same process audit, denies network, seals data reads and writes `data_access.json`. A separate future launch needs a newly reviewed permit bound to the seal, one A10/us-east-1, one GPU, one study, explicit budgets and a deadline leaving600 seconds for teardown. No permit, cloud query, archive upload, provisioner action or billable resource was created here. A future cloud controller must enforce termination independently of the workload and verify zero resources; no previous run authorization is reusable.

## Cost envelope — historical rate only

No cloud price/capacity query was made. At recorded $1.29/hour, calibration is3.470272 seconds/update (only one completed joint-update sample), .215732 seconds/inference row and approximately432.219 seconds setup through base load. Current feature extraction time calibrates a single compatibility pass:386.592 seconds. This is a projection, not measured HPO throughput.

| Per-trial stopping point | Measured-rate estimate | Estimated cost | Conservative estimate |
|---|---:|---:|---:|
| update20 | 2.99 min | $0.0644 | 6.60 min |
| update40 | 5.45 min | $0.1172 | 11.62 min |
| update80 | 9.07 min | $0.1950 | 18.63 min |

Per-trial estimates include360/720/1080 validation forwards,12/14/16 diagnostic forwards, and30 seconds reset/hash/logging overhead (90 seconds conservative). Conservative rates are6 seconds/update and.5 seconds/forward. Setup allowance900 seconds, one TRAIN pass896 seconds and32 control forwards16 seconds are used for the conservative envelope.

| Whole study, including setup/compatibility/controls/600-second teardown | Runtime | Cost |
|---|---:|---:|
| Low:14 trials stop20,1 completes80 | 74.75 min | $1.61 |
| Typical scenario:8 stop20,4 stop40,3 complete80 | 96.73 min | $2.08 |
| Conservative worst allocation:15 complete80 | 319.70 min | $6.87 |

Recommended future **soft budget $7.00 / hard ceiling $9.00**. These are recommendations only, not authorization. The pruned mix is illustrative; first-trial/rung behavior and actual results determine pruning. Hardware/setup delays can exceed this modeled envelope. Stop before the authorized deadline even if some trials are unfinished; never add an instance or retry to finish. A soft-budget review must use remaining work and reserve, not approve expansion automatically.

## Local validation and handoff

46 deterministic tests pass, including real Optuna4.5.0 TPE repeatability and successive-halving decisions, split/source balance, pre-open DEV/HOLDOUT/protected denial, reset/moment isolation, four-parameter search,15/80 caps, warmup/dropout, finite/CE pruning, objective/ties, candidate freeze/no candidate, no automatic full run, matched diagnostic RNG/mode restoration, and reuse success/mismatch cases. AST/scope/secret scans pass. Local dependencies live in an isolated ignored directory; no real model weights were loaded.

Reviewable code: `tools/auditor_optuna_hpo.py`, `tools/auditor_optuna_hpo_backend.py`, `tools/auditor_optuna_hpo_remote.py`, preparation/seal tools and tests. Frozen inputs, costs, logs, dependency pins, access receipts and code/data SHA bindings are under `tuning/auditor_optuna_hpo/`. `LOCAL_VALIDATION.json` binds the final seal. There is no runnable launch controller or issued execution permit.

No cloud, real-model inference/training, existing DEV/challenge/HOLDOUT/protected access, Producer, multi-round execution or push. Historical evidence and verdicts remain unchanged. The next action is review of this preparation; any paid HPO launch needs separate authorization.
