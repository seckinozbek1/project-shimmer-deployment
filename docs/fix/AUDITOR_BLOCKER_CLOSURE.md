# Auditor blocker closure — completed diagnostic and fail-closed admission

## 1. Executive verdict

**AUDITOR_BLOCKER_CLOSED_SAFE_ADMISSION**

Experiment: **BOTH_MATCH_THROUGH_32**. Root cause: **ROOT_CAUSE_UNRESOLVED**. Safeguard: **SAFE_ADMISSION_BOUNDARY_ESTABLISHED**. Technical retry assessment: **RETRY_REASONABLE**, subject to separate final-training authorization and a newly reviewed execution identity. **No training is authorized or was performed by this task.**

The single approved A10 ran Arm O and then Arm D in fresh sequential processes. Each produced 32 finite `(3072,)` FP32 vectors exactly equal to historical bytes. Total: **64 forwards, zero warmups, zero optimizer updates**. Neither arm diverged; no first-divergence capture was triggered. The original cause is not fixed or proven transient.

The justified local change rejects every newly extracted TRAIN vector unless its FP32 byte SHA-256 exactly matches its immutable historical receipt. This covers all **1,792** rows, not only a prefix. Input/order binding, failure latching, and a complete persisted-feature check stop execution before normalization, head fitting or optimizer creation. The reference contains receipts only, so it cannot supply a replacement vector. The original failed observations are rejected at their first finite drift, **row 11**.

All 33 relevant local CPU tests pass. Neutralizing the admission predicate fails the finite-drift regression; restoration passes. The experiment demonstrates reproducibility of the live prefix; deterministic tests establish the admission control. Neither establishes full-run device stability or successful future optimization.

The instance is terminated, independent provider inventory is empty, and temporary provider/local SSH credentials are removed. Conservative elapsed-time cost through independent confirmation is **$0.2232846483**, below both budgets. This is an estimate, not a provider invoice. Nothing was pushed and no other Shimmer work was started.

## 2. Authorization and exact execution identities

The operator explicitly approved the prepared diagnostic in `f5a6c00`. Approval, fresh preflight and source/bundle reverification were recorded in `1e230d9` before provisioning. The five prerequisite reports were read completely before preparation; the prior forensic finding remains ten exact rows, 21 finite divergent rows, and an unretained row-32 admission failure.

| Item | Executed identity |
|---|---|
| Prepared diagnostic commit | `f5a6c00` |
| Forensic baseline | `d0b218e` |
| Failed execution source copied into diagnostic | `b4f7e8247391e2278a7b7a1ba84f6b5915c56ced` |
| Execution-manifest SHA-256 | `8cb99d5aff7967ec2d951d941d6041c5aabd2a379a7d923d670c13d45fc4b2e5` |
| Runtime-bundle SHA-256 | `cab6408e2fc8e6424a00448fe032b860a9bb2c394d3deb01f23ef263e81751fe` |
| Provider instance | `80c398d739444f09b239ffa1cec0340b`; exactly one Lambda A10 24GB, `us-east-1` |
| Verified rate and caps | $1.29/hour; $1 soft / $2 hard |
| Image | `f9ba07bd-c60b-4e08-ab29-5d9be6bd62d0`, lambda-stack-24-04, 24.4.4-2141 |
| Working directory / Python | `/home/ubuntu/shimmer-auditor-final`; `.venv/bin/python`, Python 3.12.3 |
| Base state SHA-256, both arms | `d07dae6b59e73394974e2699a2f66dad8c7d57be1c800c6774eccd114f38db18` |
| Canonical adapter SHA-256, both arms | `733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6` |
| Historical full TRAIN array SHA-256 | `06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287` |
| Historical TRAIN receipts SHA-256 | `75cd0e49a85e0fd9637141b836baf1be1c627cc6a6479127f2dcd8875441a11c` |
| Collected archive SHA-256 | `358b115d3414167d06a1ec39347771ec705443d907f732f461ea5813040b4749` |

The sealed runtime, base revision, quantization and adapter construction were the prepared design. All 33 manifest-bound remote files were verified after collection. New generated source is identified by content hashes in the manifest, not falsely attributed to the old baseline commit. Post-run admission and analyzer edits described below were **not** in the paid execution; its original source remains in the approved bundle and downloaded archive.

References: [execution manifest](auditor_blocker_closure_run/execution_manifest.json), [operator authorization](auditor_blocker_closure_run/OPERATOR_AUTHORIZATION.json), [pre-launch reverification](auditor_blocker_closure_run/PRE_LAUNCH_REVERIFICATION.json), [fresh inventory/capacity/price preflight](auditor_blocker_closure_run/live_preflight.json), [post-run verification](auditor_blocker_closure_run/POST_RUN_VERIFICATION.json).

## 3. Arm O — original lifecycle

**32/32 exact matches, finite `(3072,)`, zero updates.** PID `3636`, parent `3635`, Linux start ticks `34100`. Observed process start epoch `1789662981.8056514`; completion `1789663004.9838216`.

The generated source preserves the original failed source's `scope`, `runtime` and `load_base` ASTs, import/environment ordering, base preparation, adapter load/verification, unused head creation/lifetime, eval/freeze state and `(1792,3072)` memmap allocation. Only rows 1–32 are forwarded. Original training authorization is replaced with diagnostic authorization, and the remaining-work estimate is bounded to this experiment. The executable has no downstream normalization, fitting, optimizer or evaluation entry point.

The inline branch creates IDs inside inference mode, creates an all-ones mask in the model call, runs BF16 autocast, selects `[0,-1]`, and makes the normal FP32 CPU copy. CPU parity precedes memmap persistence. The prior pooled view remains alive into the next forward, preserving the original output-storage lifetime. Successful forwards add no GPU reductions, tensor scans, layer hooks, allocator probes or model-state snapshots.

Explicit replay limitations: the raw output is named for failure capture; the mask is named by an assignment expression and survives until comparison, then is released. Naming raw shares storage already retained by the pooled view, but the mask has a slightly longer lifetime. Both arms add CPU reference allocation/comparison. This is a faithful bounded replay, not a claim of zero perturbation or recreation of the original expired device/process state.

Evidence: [O result](auditor_blocker_closure_run/downloaded/evidence/O/result.json), [O feature receipts](auditor_blocker_closure_run/downloaded/evidence/O/events.jsonl), [generated arm](auditor_blocker_closure_run/auditor_blocker_arm.py).

## 4. Arm D — helper lifecycle

**32/32 exact matches, finite `(3072,)`, zero updates.** PID `3809`, parent `3635`, Linux start ticks `36486`. Observed process start epoch `1789663005.668844`; completion `1789663030.8538258`. O completed before D started; executable and working directory matched. The supervisor used two blocking, sequential child invocations, not same-process reloads.

Common cold startup, loader, adapter, head lifetime, memmap, rows and budgets match O. D uses the then-current diagnostic helper with success receipts, through a generated callback after CPU copy and before successful logging. Inputs are created outside inference mode; forward remains inside inference/BF16 autocast. Helper locals expire before the next call. No earlier warmups or other real-model forwards occurred.

All 32 success receipts independently verify token/IDs/mask bindings, raw/pooled/vector finiteness, zero training modules, active enabled/unmerged historical adapter, eval dropout, BF16 quantized compute, eager attention, deterministic algorithms and disabled TF32. No state discrepancy was found. Detailed native/buffer capture was deliberately reserved for divergence and was not invoked.

Evidence: [D result](auditor_blocker_closure_run/downloaded/evidence/D/result.json), [D feature receipts](auditor_blocker_closure_run/downloaded/evidence/D/events.jsonl), [first success receipt](auditor_blocker_closure_run/downloaded/evidence/D/row-01.json), [last success receipt](auditor_blocker_closure_run/downloaded/evidence/D/row-32.json), [executed generated helper](auditor_blocker_closure_run/auditor_blocker_helper.py).

Both memmaps allocate 1,792 rows for lifecycle fidelity. **Only their first 32 rows are observations.** Unwritten rows are not evidence of model output.

## 5. First divergence and evidence integrity

There was **no new first divergence**. The original row-11 transition and missing row-32 tensor remain the unresolved historical boundary. The prepared capture mechanism was exercised synthetically, not by an actual cloud fault in this experiment.

The remote archive was hash-verified before termination. Its prepared tar command omitted the manifest-bound launch-environment file `tuning/first_domain_agnostic_v1/experiment.json` because it included only `tuning/auditor_final`. That single file was collected separately, read-only, with remote and local hash verification before workload completion. No payload or forward logic was changed. The supplemental file and archive together satisfy all 33 manifest hashes. See [supplemental collection receipt](auditor_blocker_closure_run/supplemental_collection.json).

`verify_auditor_blocker_closure_results.py` additionally binds all 1,792 historical receipts to the existing full TRAIN array and serialized inputs, checks all 64 event hashes/bytes against historical, verifies the 32 D model/input receipts and process order, and confirms collection/cleanup receipts. It uses no model and opens no DEV/challenge/protected payload.

Remaining verification limits: no new failure means no fault-time native-library/buffer/device evidence; source and parameter hashes cannot reconstruct old transient native state; O retains the necessary minor capture accommodations; final hardware billing is not independently invoiced here. Neither version pins nor successful recurrence prove the original process had identical nonpersistent state.

## 6. Ranked causal assessment

Ranking is investigative priority, not a probability estimate. No candidate explains all original observations strongly enough to claim causality. See the earlier [full root-cause analysis](AUDITOR_FAILURE_ROOT_CAUSE_ANALYSIS.md) for the four-run semantic comparison and saved-evidence falsification.

| Rank / candidate | Supporting evidence | Falsification / expected observation | Verdict after O/D |
|---|---|---|---|
| 1. Original execution-specific model/native/device state changed around row 11 | Ten initial exact rows followed by all-coordinate finite drift, then terminal refusal; cold cloud runs match | A persistent deterministic input/source fault should recur at the same boundary. Neither O nor D does. Original fault-time state/tensor is absent, so native buffer, device and other state mechanisms cannot be separated | Plausible boundary; exact mechanism untestable from preserved evidence |
| 2. Inline output lifetime/input inference context alone causes the failure | Original and helper differ in lifetime and ID context; prior CPU probe confirms these differences | Under common startup, a sufficient deterministic inline defect predicts O divergence and D match. Both match. Rare allocation sensitivity is not eliminated by one replay | Unlikely as a sufficient deterministic cause; conditional sensitivity remains unproved |
| 3. Success instrumentation repairs or masks a deterministic defect | Earlier successful A10 diagnostic was instrumented | New O has no success-time GPU scans/state snapshots yet matches. If such instrumentation were necessary, O should fail | Unlikely; not a demonstrated fix |
| 4. Wrong persistent base/adapter/source/token identity | Such differences can alter all coordinates | Verified source/assets and token bindings, ten exact original rows, and new complete-prefix parity contradict a static identity mismatch. A static mismatch would usually affect row 1 as well | Unlikely for verified identities; hashes do not certify all runtime state |
| 5. Row-32 content or deterministic sequence-length failure | Original guard failed on that row | Historical row32 and repeated later A10 row32 are finite, including this sequential O and D; earlier forensic length comparison did not show a new maximum at row11 | Ruled out as an unconditional input-only failure in the pinned path |
| 6. Local-vs-cloud runtime difference explains the original cloud transition | Local execution is deterministic but differs numerically from cloud | This explains local mismatch, not ten exact then 21 drifting original cloud rows; both new pinned A10 processes reproduce historical | Not an explanation of the original failure |

A transient GPU fault is one possible member of the first boundary, not an established explanation. No recovered Xid/ECC report or offending tensor proves it. The two original symptoms could share a mechanism, but that is also unproven.

**ROOT_CAUSE_UNRESOLVED.** No causal numerical or lifecycle fix was implemented.

## 7. Safe admission boundary

**SAFE_ADMISSION_BOUNDARY_ESTABLISHED** for admission of fresh TRAIN features to normalization/fitting. The narrow CPU boundary is observable and enforceable even though its upstream failure mechanism is unknown.

A prefix-only check cannot prevent later finite drift. The implementation therefore covers every one of the 1,792 rows:

1. `HistoricalAdmission` validates the immutable historical receipt-file SHA-256 and binds every row index, example ID, prompt hash and serialized token hash to TRAIN-only inputs before model loading.
2. Before each forward, it enforces order and a nonfailed state. The ordinary live forward/pooling/CPU copy still runs; no historical feature values are loaded by this gate.
3. Raw shape and vector shape/finiteness remain mandatory. Each FP32 vector's byte SHA-256 must equal its historical receipt exactly. This is cryptographic exact-byte admission, with no numeric tolerance or `allclose`; the normal SHA-256 collision assumption applies.
4. On first finite drift or raw/vector failure, the gate latches failure, durably records a minimal receipt, saves the observed CPU vector and raw tensor when recoverable, then records detailed model/runtime/tensor summaries. Further forwards are refused. Atomic JSON replacement preserves the minimal receipt if a later detail write fails. I/O/capture failures do not permit progress.
5. Before normalization, the gate requires all 1,792 successful admissions and rechecks every persisted vector against its receipt. Partial extraction, ignored failure, or changed persisted features cannot unlock fitting. An admission receipt is written only after this check.

Only comparison receipts were copied to `tuning/auditor_final/historical_train_features.jsonl`, byte-identical to historical. There is no historical-vector substitution, sanitization, row skipping, cache-as-observation reuse or automatic resume. The helper's default behavior remains available for bounded diagnostics; the production extraction call explicitly requires the admission object.

Production changes are confined to `auditor_feature_diagnostics.py`, the live final extraction call/completion boundary in `auditor_final_remote.py`, and the immutable TRAIN comparison receipts. Existing frozen HPO values, datasets, architecture, runtime contract, schedule and consumed seal remain unchanged. No final payload was resealed, bundled or launched; the old source seal intentionally cannot admit the changed code. Future execution needs a separately reviewed identity and authorization, not reuse of this diagnostic permit.

The guarantee is limited to extracted-feature admission. It does not prove future optimization stability, general hardware correctness, or completion of the full extraction. A benign but nonidentical future runtime will be refused rather than tolerated. Diagnostic persistence cannot be guaranteed if storage/device access itself is unavailable; such errors still stop the process.

## 8. Deterministic validation and minimal analysis correction

Before launch, the prepared diagnostic passed **20/20 CPU tests**, with a diagnostic-comparator neutralize/fail/restore/pass check: [original gates](auditor_blocker_closure_run/LOCAL_GATES.json), [log](auditor_blocker_closure_run/local_tests.log), [mutation receipt](auditor_blocker_closure_run/neutralize_restore.json). Those are preserved prelaunch results for the approved source, not claimed as tests of the later admission change.

After teardown, **33/33 tests passed**: 16 admission/cost regressions, seven existing extraction regressions and ten existing final-contract tests. Coverage includes:

- exact live CPU-copy acceptance; all 1,792 saved historical vectors passing complete admission;
- one-ULP finite drift refusal and persistent failure latch; later row101 drift refusal;
- saved failed-run rows1–10 passing and row11 failing before any later row;
- malformed shape, wrong dtype, NaN/+Inf/-Inf, changed/missing reference and input/order refusal;
- incomplete admission and post-persistence corruption blocking completion;
- actual production-loop AST executed with synthetic extraction, proving failed admission prevents memmap writes/normalization; downstream fitting and optimizer calls structurally follow completion;
- durable minimal/vector/raw evidence, raw/detail-capture failure and atomic receipt-upgrade failure;
- unchanged final contracts and the corrected cost units.

Neutralizing `HistoricalAdmission.vector_reason` to unconditional success makes the finite-drift test fail because the exception no longer occurs. Restoring it passes. No source neutralization remains. [Validation and source hashes](auditor_blocker_closure_run/ADMISSION_VALIDATION.json), [33-test log](auditor_blocker_closure_run/admission_tests.log), [neutralized failure](auditor_blocker_closure_run/admission_neutralized.log), [restored pass](auditor_blocker_closure_run/admission_restored.log).

Reproduce locally with `.venv/Scripts/python.exe tools/validate_auditor_feature_admission.py`; it uses synthetic tensors and saved TRAIN evidence, not real-model inference. `python tools/verify_auditor_blocker_closure_results.py` verifies retained receipts. Neither launches resources or trains.

A post-run analyzer bug multiplied elapsed seconds by the hourly rate without dividing by 3,600. Only that derived estimate was wrong; controller/watchdog cost logic and timing receipts already used correct units. `cost_usd` now performs the conversion and has a one-hour regression. The corrected [recomputed results](auditor_blocker_closure_run/RECOMPUTED_RESULTS.json) reports $0.2232846483. The executed analyzer source is retained unchanged in the archive. Its `safe_admission_boundary_established: false` field is deliberately the experiment-only classification; the subsequent reviewed production-safeguard verdict is in this report and `FINAL_STATUS.json`.

## 9. Budget, collection and teardown

| Event (UTC, 2026-09-17) | Evidence |
|---|---|
| 16:28:47.299 — one launch | Empty inventory, A10 us-east-1 availability and $1.29 rate verified before launch |
| 16:36:44.984 — O complete | 32 exact matches |
| 16:36:45.669 — D observed start | Distinct PID/start ticks, after O exit |
| 16:37:10.854 — D complete | 32 exact matches |
| 16:37:14.474 — supervisor completion recorded | Exit code 0; no automatic continuation |
| 16:37:33.880 — archive verified locally | 57,464,126 bytes; archive hash above |
| 16:37:40.130 — termination requested | After verified collection |
| 16:39:05.986 — termination verified | Provider status terminated |
| 16:39:10.419 — independent cleanup confirmation | Inventory empty; temporary SSH registration absent; local key material absent |

Elapsed time through independent confirmation: **623.119949 seconds**. At $1.29/hour: **$0.2232846483**. The workload stayed below the $1 soft budget and $2 hard ceiling; no additional instance, launch retry or multi-round execution occurred. Watchdog and reserve protection were armed; normal completion/teardown occurred long before their cutoffs.

Both arms report zero forbidden accesses and zero DEV/historical-DEV/challenge rows. No normalization, head fitting, optimizer/backward/training, HPO, protected test, Producer or full Shimmer was executed. Dependency acquisition and provider-support processes performed no model forwards.

Receipts: [collection integrity](auditor_blocker_closure_run/collection_integrity.json), [termination confirmation](auditor_blocker_closure_run/TERMINATION_VERIFIED.json), [independent empty inventory and credentials](auditor_blocker_closure_run/independent_inventory_confirmation.json), [cleanup](auditor_blocker_closure_run/cleanup.json), [evidence inventory](auditor_blocker_closure_run/EVIDENCE_MANIFEST.json).

## 10. Retry assessment, unknowns and exact next action

**RETRY_REASONABLE** technically: two distinct cold extraction lifecycles reproduce the historical prefix; the live extraction boundary now refuses finite drift anywhere in the full TRAIN pass; complete fresh-feature admission is mandatory before any fitting; regression tests reject the actually preserved original failure at row11. This is an operational containment decision, not causal repair or an assurance that the retry will complete.

Unknown: the original row11 internal transition, row32 offending shape/values, original native/device state, whether both symptoms shared a mechanism, whether unobserved rows33–1792 will match on a future cold extraction, and whether subsequent optimization will remain stable. The new gate may stop a future run on those later rows; that is its intended behavior.

No further remote diagnostic is required to establish this admission boundary, and none is authorized. No automatic final retry follows. **Stop after this local results/safeguard commit.** A final Auditor training attempt requires separate operator authorization and review of the changed source/admission reference and execution identity. The consumed diagnostic/final authorizations are not reset. No packaging, release, Producer or other roadmap work is part of this closure.
