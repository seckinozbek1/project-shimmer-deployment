# Final Auditor retry results

**AUDITOR_FINAL_COMPLETE — checkpoint 896 selected.**

All 1,792 fresh TRAIN vectors passed exact historical admission and the persisted-feature recheck. Fresh TRAIN-only normalization and deterministic head-200 completed, followed by exactly 896 joint optimizer updates. Both planned checkpoints were preserved and evaluated only after durable 896 completion. Source, artifacts, schedules, normalization, saved-logit metrics and selection were independently verified locally.

Checkpoint896 is the best usable artifact under the established selection rule, **not a claim that every former quality target passed**. Historical DEV macro F1 is 0.4576 and OMISSION recall is1/12. No further tuning, integration, protected evaluation or roadmap work was started.

## Execution identity and scope

| Item | Verified value |
|---|---|
| Baseline with admission safeguard | `04cdb026484b38c4319b9d58a94e3fc20198c61c` |
| Execution source | `c9c2380ad11abe8e8795ce13ed5d84a8b97f42df` |
| Direct approval/preflight commit | `6485e6e` |
| Manifest SHA-256 | `474d5354fe4bc6beee227e1586bb5da92647080984fe55f0f8adb003acc577d4` |
| New seal SHA-256 | `00b1b47b1534f17b8aae8d293977c94deae3ebaf2d2fded4c62c8cb0f03a0198` |
| Bundle SHA-256 | `f2d38f0989af23a4b9497d7b63ce6f057a7d56a6dcf57f3f3961477c1550fc82` |
| Instance | Lambda `6434d0658b184b6e9eb8b7406c9ff88d`, one `gpu_1x_a10`, NVIDIA A10 24GB, `us-east-1` |
| Image | `f9ba07bd-c60b-4e08-ab29-5d9be6bd62d0`, lambda-stack-24-04,24.4.4-2141 |
| Runtime | Python 3.12.3; Torch 2.5.1+cu121; CUDA 12.1; cuDNN 90100; NumPy 2.0.2; Transformers 4.51.3; PEFT 0.15.2; bitsandbytes 0.48.2; Accelerate 1.10.1 |
| Rate / budget | $1.29/hour; $5 soft / $7 hard |
| Cost through independent cleanup | **$1.6791548249 estimated**,4,686.013465seconds (78.10minutes); not a provider invoice |

The operator directly approved paid compute and model/adapter/TRAIN transfer after the earlier automatic approval block. That block launched nothing and consumed no paid attempt. Exactly one launch occurred after direct approval; no retry or second instance followed. The old consumed seal and historical run evidence were preserved. Every executed workload/data/reference file was byte-verified against 04cdb02 (canonical adapter weights against their pinned hash); only isolated retry orchestration and a fresh seal/permit were added.

Frozen HPO values remained LoRA peak LR `1.2943234833221302e-6`, head LR `0.0009721418411547451`, warmup 10 updates, dropout 0.05. The starting adapter was the canonical clean Auditor step 120, not HPO Trial 11 weights. Architecture, rank, target modules and optimizer design were unchanged.

References: [manifest](auditor_final_retry_run/execution_manifest.json), [new seal](auditor_final_retry_run/retry_seal.json), [direct approval/hash reverification](auditor_final_retry_run/DIRECT_APPROVAL_REVERIFICATION.json), [runtime receipt](auditor_final_retry_run/downloaded/evidence/feature_runtime.json).

## TRAIN admission, fitting and numerical stability

- Attempted/admitted: **1,792/1,792**; first failure: **none**. Exact FP32 byte SHA-256 admission, all row/input bindings and the final persisted-feature recheck passed. No tolerance, substitution, repair or skipped row. The remote reference contained comparison receipts only, not historical vectors. The independently verified fresh array hash equals the historical array hash because all live outputs matched exactly.
- Admission reference: `75cd0e49a85e0fd9637141b836baf1be1c627cc6a6479127f2dcd8875441a11c`. Fresh feature array: `06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287`.
- Normalization: fresh full TRAIN only, zero DEV fit rows; mean/std independently recomputed exactly with NumPy 2.0.2. Population standard deviation, clamp1e-6, zero clamped dimensions. Fresh feature/normalization stage:416.03seconds.
- Head fit: fresh deterministic 200 updates on 1,792 TRAIN rows; CE 0.0858519673. Clean classifier fork and empty fresh optimizer/gradients verified.
- Joint training: **896 updates /3,584 microbatches**, exactly two complete TRAIN passes. Training-update time3,425.49seconds; median3.7338seconds/update; peak allocated memory3.5587GiB.
- All completed update telemetry and retained parameters were finite. Maximum mean update CE5.90891734 versus configured ceiling13.86294361; maximum microbatch CE20.32736778 versus55.45177444. No CE-explosion/nonfinite stop.
- Head gradient norm range 0.00004365–60.6712; LoRA 0.00095699–810.3379; combined pre-clip maximum 811.2720, post-clip maximum 1.0000001065 (floating-point rounding around 1).
- Head and LoRA parameter deltas were nonzero on every update: head 0.0139857–0.1077612, LoRA 0.00049865–0.00198292. Actual head LR stayed fixed; LoRA followed the frozen 10-update warmup then fixed peak.
- Checkpoints448 and 896 each report 450 populated optimizer parameter states, the correct exact step and finite moments. Full frozen-base/source audits passed.

Prelaunch validation: **41 passing local tests** (28 feature/admission/probe,10 final-contract,3 retry gates), plus packaged scope/identity verification. The post-run analyzer verified 896 schedules,3,584 microbatch bindings, all admission hashes, fresh normalization, finite checkpoint arrays, checkpoint identities, evaluation chronology, every saved prediction/CE, exact metrics and checkpoint selection. The first local Python 3.10 metric comparison differed only at roughly 1e-16; rerunning with matching Python 3.12.3/NumPy 2.0.2 reproduced every metric exactly. No comparison tolerance was weakened and no new model forward ran locally.

Evidence: [admission](auditor_final_retry_run/downloaded/evidence/feature_admission.json), [head fit](auditor_final_retry_run/downloaded/evidence/head_fit.json), [numerical summary](auditor_final_retry_run/NUMERICAL_SUMMARY.json), [independent recomputation](auditor_final_retry_run/RECOMPUTED_RESULTS.json).

## Checkpoint evaluation and selection

Each checkpoint evaluated 200 external DEV plus 48 historical DEV rows. SHORTER 75 and LONGER 75 are the existing disjoint three-class subsets of external DEV, scored from those predictions. Total evaluation forwards:496.

| Checkpoint | Population | Accuracy | Macro F1 | Minimum recall | Mean CE |
|---|---|---:|---:|---:|---:|
| 448 | external | 0.8000 | 0.7865 | 0.4600 | 1.6484 |
| 448 | historical | 0.5000 | 0.4541 | 0.1667 | 4.7253 |
| 448 | shorter | 0.7600 | 0.7350 | 0.4000 | 1.8863 |
| 448 | longer | 0.7067 | 0.7152 | 0.5200 | 2.4987 |
| 896 | external | 0.7950 | 0.8010 | 0.6600 | 1.3739 |
| 896 | historical | 0.4792 | 0.4576 | 0.0833 | 3.4274 |
| 896 | shorter | 0.8000 | 0.8036 | 0.7200 | 1.3911 |
| 896 | longer | 0.6933 | 0.7081 | 0.6000 | 2.0386 |

**Why896:** neither checkpoint passes all former gates. The next established criterion is historical macro F1:896 scores 0.4576474342 versus 448 at 0.4540964480, so 896 wins at that criterion. External macro F1 also improves, but was not needed as a tie-breaker. This rule does not maximize accuracy: external accuracy is79.5% versus80.0%, and historical accuracy47.92% versus50.0%.

Checkpoint896 passes the former external, SHORTER and LONGER gates; historical DEV fails. Checkpoint448 fails external minimum recall and historical DEV. No new optimization loop was opened.

Per-class recall (M=MATCH, D=DIVERGENCE, O=OMISSION, A=ADDITION; dash means not a target class in that subset):

| Checkpoint / population | M | D | O | A |
|---|---:|---:|---:|---:|
| 448 / external | 0.4600 | 0.8200 | 1.0000 | 0.9200 |
| 448 / historical | 0.1667 | 0.2500 | 0.6667 | 0.9167 |
| 448 / shorter | 0.4000 | 0.8800 | 1.0000 | — |
| 448 / longer | 0.5200 | 0.7600 | — | 0.8400 |
| 896 / external | 0.8200 | 0.6600 | 0.8400 | 0.8600 |
| 896 / historical | 0.5833 | 0.5833 | 0.0833 | 0.6667 |
| 896 / shorter | 0.8800 | 0.7200 | 0.8000 | — |
| 896 / longer | 0.7600 | 0.6000 | — | 0.7200 |

Confusion matrices: columns always `[M,D,O,A]`; rows are `[M,D,O,A]` for DEV, `[M,D,O]` for SHORTER and `[M,D,A]` for LONGER.

```text
448 external: [[23, 13, 8, 6], [8, 41, 0, 1], [0, 0, 50, 0], [2, 1, 1, 46]]
448 historical: [[2, 0, 5, 5], [0, 3, 3, 6], [0, 0, 8, 4], [0, 0, 1, 11]]
448 shorter: [[10, 9, 6, 0], [3, 22, 0, 0], [0, 0, 25, 0]]
448 longer: [[13, 4, 2, 6], [5, 19, 0, 1], [2, 1, 1, 21]]
896 external: [[41, 4, 2, 3], [16, 33, 0, 1], [7, 1, 42, 0], [6, 0, 1, 43]]
896 historical: [[7, 0, 0, 5], [1, 7, 0, 4], [5, 0, 1, 6], [4, 0, 0, 8]]
896 shorter: [[22, 2, 1, 0], [7, 18, 0, 0], [4, 1, 20, 0]]
896 longer: [[19, 2, 1, 3], [9, 15, 0, 1], [6, 0, 1, 18]]
```

Classifier contract validity and substantive non-refusal coverage are 1.0 for every population/checkpoint. Refusal precision/recall and explanation/evidence precision, recall and F1 are **not applicable**, because this is the fixed four-way classifier without refusal/explanation/evidence generation. Confidence-specific wrong-decision, invented-evidence, truncation, Producer-copy and governance metrics are likewise unmeasured/not applicable; they are not reported as zero.

Measured catastrophic/numerical counters: **zero nonfinite logits and zero invalid classes** in every population/checkpoint. Ordinary classification error counts remain material:

| Checkpoint / population | Total errors | False MATCH | Wrong MATCH or DIVERGENCE |
|---|---:|---:|---:|
| 448 / external | 40 | 10 | 24 |
| 448 / historical | 24 | 0 | 0 |
| 448 / shorter | 18 | 3 | 12 |
| 448 / longer | 22 | 7 | 12 |
| 896 / external | 41 | 29 | 34 |
| 896 / historical | 25 | 10 | 10 |
| 896 / shorter | 15 | 11 | 14 |
| 896 / longer | 23 | 15 | 17 |

Full metrics/predictions: [checkpoint 448](auditor_final_retry_run/downloaded/evidence/checkpoint-448/results.json), [checkpoint 896](auditor_final_retry_run/downloaded/evidence/checkpoint-896/results.json).

## Selected artifact and evidence identity

[Selected final Auditor descriptor](auditor_final_retry_run/SELECTED_FINAL_AUDITOR.json) records checkpoint 896, the base/runtime contract, frozen hyperparameters and normalization paths. Both 448 and 896 remain locally retained.

| Selected artifact | SHA-256 |
|---|---|
| LoRA adapter | `0ec8212f5288e5960f1e816d93c9c7e1206eed7c380b45cf355ae0825ecc1b5e` |
| Adapter config | `af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6` |
| Head | `6a2fcf89d3e843d5364443c20add30f0542e9dfbf00ff3b0e4d78ede397fdc3a` |
| Mean | `370b185841099279202b09540b45231f70fc1b109795faf520369964831678f5` |
| Std | `1221aff7ce64f090635267884183baabbd521e9a1738221555f074b4478f304a` |
| Frozen base state | `d07dae6b59e73394974e2699a2f66dad8c7d57be1c800c6774eccd114f38db18` |

The collected archive is 246,041,293bytes, SHA-256 `6a6b8d9e43e9eda31dbeb31fa0ff9d849dbcb63aa3d31c38c7f9a52cfe0e3207`. All manifest-bound executed files and checkpoint hashes were verified against the collected archive. Text evidence is committed; arrays, weights and archive remain local with hashes in the [evidence inventory](auditor_final_retry_run/EVIDENCE_MANIFEST.json).

## Data boundary, cost and teardown

All times below are UTC on 2026-09-17.

| Event | Time |
|---|---|
| Single launch | 17:25:11.231 |
| Durable TRAINING_COMPLETE896, evaluation rows opened0 | 18:38:14.519 |
| Controller verified completion and released evaluation | 18:38:20.181 |
| Evaluation process first opened authorized populations | 18:38:39.383 |
| Training/evaluation finished | 18:41:04.926 |
| Archive collected and hash-verified | 18:41:49.220 |
| Termination requested | 18:41:54.660 |
| Provider termination verified | 18:43:12.411 |
| Independent empty inventory/credential cleanup | 18:43:17.244 |

Training access counters: external DEV0, historical DEV0, SHORTER0, LONGER0. Evaluation counters after 896:200/48/75/75. Both training and evaluation report successful forbidden access counters of 0 for HOLDOUT, protected final test, Producer and full Shimmer; denied-before-open counters are also0. Protected final test remains **unconsumed**. No governance or multi-round execution occurred.

At the verified $1.29/hour rate, elapsed time through independent cleanup gives **$1.6791548249**, below both $5 soft and $7 hard. The soft threshold was never reached. Runtime remaining-work projections and watchdog/reserves were active. Actual billed cost awaits the provider invoice.

The instance is terminated; independent provider inventory is empty; zero billable instances remain. Temporary provider SSH registration and local private/public SSH keys are absent. Evidence collection preceded termination. See [termination](auditor_final_retry_run/TERMINATION_VERIFIED.json), [independent cleanup](auditor_final_retry_run/independent_inventory_confirmation.json), [collection integrity](auditor_final_retry_run/collection_integrity.json), [training access](auditor_final_retry_run/downloaded/evidence/training_data_access.json), [evaluation access](auditor_final_retry_run/downloaded/evidence/evaluation_data_access.json).

## Remaining limitations and stop point

Historical generalization remains weak: checkpoint 896 historical macro F1 is 0.4576, and OMISSION recall is 0.0833 (1/12). External false-MATCH errors are 29/200, up from 10/200 at448; historical false-MATCH errors are 10/48. These limitations remain visible despite the rule selecting 896. Protected-test quality, integrated Shimmer behavior, generative refusal/explanations and governance behavior are not established by this classifier evaluation.

The original extraction failure mechanism remains unresolved; this successful full exact-admission run does not prove a causal fix. The safeguard remained load-bearing and was not relaxed. The selected artifact is usable under the requested completion-first workflow, without claiming all quality targets or deployment readiness.

**Stop after the local results commit.** No push, integration, Producer, full Shimmer, protected evaluation, multi-round execution, additional training attempt or further optimization was performed or scheduled.
