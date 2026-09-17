# Auditor blocker closure — prepared diagnostic, awaiting authorization

## 1. Executive verdict

**AUDITOR_BLOCKER_STILL_OPEN**

Root cause: **ROOT_CAUSE_UNRESOLVED**. Safe production admission boundary: **not established**. Final Auditor training retry: **RETRY_NOT_YET_JUSTIFIED**.

The exact two-process experiment is prepared and locally tested. **No cloud resource was launched, no provider API was called, and neither arm ran on an A10.** The prepared authorization explicitly has `operator_authorized: false`.

Experiment outcome: **REMOTE_DIAGNOSTIC_INCOMPLETE**, specifically **NOT_RUN_AWAITING_OPERATOR_AUTHORIZATION**. This describes execution status, not another unsuccessful numerical reproduction. No causal conclusion follows from the synthetic CPU tests.

The five requested reports were read completely. The latest evidence remains: ten exact historical vectors, finite divergence on rows 11–31, and a terminal combined shape/finite failure on row 32 whose offending tensor was lost. The subsequent instrumented A10 success did not reproduce the original process lifecycle. This preparation addresses that specific gap; it does not authorize training or another roadmap item.

## 2. Exact experiment identities

| Item | Prepared identity |
|---|---|
| Baseline forensic commit | `d0b218e` |
| Original execution source | `b4f7e8247391e2278a7b7a1ba84f6b5915c56ced` |
| Original source bytes | Manifest-verified members of `docs/fix/auditor_final_run/runtime_bundle.zip` |
| Execution-manifest SHA-256 | `8cb99d5aff7967ec2d951d941d6041c5aabd2a379a7d923d670c13d45fc4b2e5` |
| Runtime-bundle SHA-256 | `cab6408e2fc8e6424a00448fe032b860a9bb2c394d3deb01f23ef263e81751fe` |
| Instance, if authorized | Exactly one Lambda `gpu_1x_a10`, NVIDIA A10 24GB, `us-east-1` |
| Image | `f9ba07bd-c60b-4e08-ab29-5d9be6bd62d0`, lambda-stack-24-04, version 24.4.4-2141 |
| Rate | Historical cap $1.29/hour; fresh provider price/capacity verification required before launch; no acceptance of a higher rate |
| Budget | $1 soft / $2 hard ceiling; one launch, no automatic retry or second instance |
| Arm execution | One O process, wait for exit, then one D process; each at most rows 1–32; at most 64 forwards total |
| Working directory | `/home/ubuntu/shimmer-auditor-final`, matching the failed run on a new instance |
| Model/runtime | Original sealed runtime contract, canonical adapter, checkpoint revision, eager attention, NF4/BF16, package pins and seed settings |
| Historical comparison | First 32 vectors derived from immutable full TRAIN cache SHA-256 `06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287`; each vector and token binding checked against its original receipt |
| Data payload | Original sealed 1,792 TRAIN records retained for startup/allocation fidelity; only first 32 may be forwarded; 32 historical comparison vectors; no DEV/challenge contents |

The manifest identifies new diagnostic source by **file-content hashes**, not by falsely attributing it to the baseline commit. The generated arm/helper source is retained for direct review. The final local commit contains the reviewed new code and preparation evidence. The approximately 60MB runtime ZIP remains locally retained, with its hash, rather than duplicating the canonical adapter in Git.

Artifacts:

- [Execution manifest](auditor_blocker_closure_run/execution_manifest.json)
- [Launch/budget specification](auditor_blocker_closure_run/manifest.json)
- [Unapproved authorization](auditor_blocker_closure_run/diagnostic_authorization.json)
- [Generated shared arm source](auditor_blocker_closure_run/auditor_blocker_arm.py)
- [Generated helper with boundary callback](auditor_blocker_closure_run/auditor_blocker_helper.py)
- [Local test gates](auditor_blocker_closure_run/LOCAL_GATES.json)

This is preparation of the authorized diagnostic payload, not work on roadmap packaging or release readiness.

## 3. Arm O result and exact path

**NOT RUN.** No live parity or finite-shape result is claimed.

`prepare_auditor_blocker_closure.py` derives the arm from the failed run's exact preserved Python source. The original `scope`, `runtime`, and `load_base` function ASTs are unchanged; tests compare them directly. The original imports inside initialization, base loading, canonical adapter loading/verification, unused head construction, eval/freeze state, base hash, and `(1792,3072)` FP32 memmap allocation are copied from the failed path.

The common authorization function is replaced with diagnostic-only authorization; the remaining-work budget estimate is replaced because an estimate for 896 updates would refuse this bounded experiment. The original signal-handler/budget object remains. These changes affect both arms equally. No original training permit is supplied, and the generated executable has no normalization, fitting, optimizer, evaluation, or training entry point.

O creates IDs inside inference mode, uses the original all-ones mask construction in the original model call, performs BF16 autocast, selects `[0,-1]`, and makes the normal FP32 CPU NumPy copy. The CPU vector is compared byte-for-byte with historical **before memmap persistence**. Exact matches retain original memmap flush and feature-event behavior. Prior `hidden` remains alive into the next forward, preserving the original output-storage lifetime.

Two small, explicit accommodations are necessary to retain the requested failing evidence: the full raw result is named before selecting its last token, and the original `ones_like(ids)` mask is named using an assignment expression in the call. These references survive through the CPU comparison, then are dropped on success. They add no GPU reduction, scan, hook, or allocation probe. The mask therefore lives slightly longer after the forward than the original anonymous argument; the raw reference shares storage already retained by the last-token view. This is not claimed to be a zero-perturbation replay of an expired process. Both arms also necessarily incur the new CPU historical comparison and reference-array allocation.

Malformed raw output is captured at the boundary, including indexing failures; no subsequent forward occurs. Unexpected forward exceptions yield an incomplete arm rather than being mislabeled as historical numerical divergence.

## 4. Arm D result and intended contrast

**NOT RUN.** No live parity or finite-shape result is claimed.

D is the same executable in a second fresh Python process. It uses the same scope, authorization/environment ordering, runtime initialization, loader, adapter, unused-head lifetime, memmap size, data order, budget logic, CPU parity check, and persistence. Unlike the previous A/B/C diagnostic, there are no earlier warmup forwards or same-process model reloads.

Only the extraction branch changes: D uses the current diagnostic helper with `record_success=True`. A diagnostic-only generated copy adds a boundary callback after the normal CPU copy, before successful receipt creation/return. This permits immediate comparison and raw-tensor preservation without a second forward or layer hook. On exact match the helper follows its existing success-receipt path; its locals then expire before the next call. Its input tensors are created outside inference mode, while the model call remains inside inference mode/BF16 autocast.

The production helper is unchanged. The generated copy's only functional additions are the optional callback argument and callback invocation; they are visible in the retained source. The callback never substitutes, casts, repairs, skips, or returns a historical vector as an observation.

The supervisor invokes O with blocking `subprocess.run`, verifies its terminal result, then invokes D with another `subprocess.run`. Each arm records PID and Linux process-start ticks. A reused PID or an incomplete arm prevents a completed experiment classification. One-time supervisor and arm attempt markers prevent automatic resume/retry. Separate acquisition/preflight support processes execute zero model forwards; the two arm processes are the only inference processes.

## 5. First-divergence capture

**No new divergence boundary exists yet.** The historical observed boundary remains row 11, document-012, with the unexplained row-32 terminal failure.

The prepared comparator requires FP32 shape `(3072,)`, finiteness, and exact byte equality. No `allclose` tolerance is used; even a one-ULP finite change or a signed-zero byte change is refused. Raw shape is checked separately using metadata. On the first bad boundary:

1. A minimal strict-JSON boundary receipt is flushed and fsynced.
2. The produced CPU vector, if one exists, is saved and fsynced separately.
3. Raw hidden values are retained as a CPU tensor file with dtype preserved, if safely recoverable.
4. Only then are detailed post-boundary probes attempted. Each result/error is durably recorded, and no additional model forward is invoked.

Post-boundary capture covers input/token/mask hashes; raw/pooled/vector shapes, dtypes/devices and finite/NaN/+Inf/-Inf summaries; model train state; adapter active/disabled/merged state; dropout and quantized compute flags; every named parameter hash; persistent and nonpersistent named buffers (values and hashes); Python/NumPy/Torch/CUDA RNG hashes; relevant module file/origin metadata; mapped native-library paths/maps/hashes; Torch build and CUDA/cuDNN/bitsandbytes identities; driver; allocator summary; and whitelisted deterministic/native environment settings. NVIDIA ECC/retirement/row-remap information and filtered Xid/NVRM messages are collected if available. Unavailable commands and failed captures are reported, not interpreted as a clean device.

A wrong raw shape can prevent pooling, especially in D. In that case no CPU vector is invented: the raw tensor and receipt are retained and the absence of a vector is explicit. I/O failure also stops execution. The post-run analyzer refuses a fully classified completed experiment when required capture is incomplete. It never deserializes the saved `.pt` files to run code or loads a model.

Successful O forwards contain no new GPU reductions, full-tensor scans, layer hooks, allocator sampling, or runtime-state snapshots. Successful D instrumentation is the intended experimental contrast.

## 6. Causal interpretation and root-cause status

There is no new A10 evidence yet, so **ROOT_CAUSE_UNRESOLVED** remains mandatory. Local tests demonstrate diagnostic mechanics, not the cause of the original row-11 transition or row-32 failure.

After authorization and execution, report exactly one of:

| Outcome | Required interpretation |
|---|---|
| `O_DIVERGES_D_MATCHES` | Strong evidence of extraction lifecycle/instrumentation sensitivity under common startup; inspect the preserved boundary and smallest source/state differences before considering a causal fix |
| `BOTH_DIVERGE` | Helper is not a sufficient distinction; inspect preserved first-divergence runtime/model state; no training retry |
| `O_MATCHES_D_DIVERGES` | Helper path is suspect; no promotion of that helper as a remedy |
| `BOTH_MATCH_THROUGH_32` | Nonreproduction; evaluate a fail-closed production admission mechanism without claiming the original cause was fixed |
| `REMOTE_DIAGNOSTIC_INCOMPLETE` | Missing arm, resource/runtime failure, invalid process/order evidence, or inadequate required capture; no closure claim |

There is no automatic second experiment, layer replay, parameter sweep, or training continuation in the code. The analyzer verifies receipts and produces an outcome; it does not automatically declare a causal fix, safe admission, or training authorization.

## 7. Safe admission boundary and retry readiness

**SAFE_ADMISSION_BOUNDARY_ESTABLISHED is not claimed. RETRY_NOT_YET_JUSTIFIED.** Production behavior was not changed because the required discriminating experiment has not run.

A future bounded-prefix gate can prove that the prefix matched and can prevent fitting after an observed prefix mismatch. It cannot, by itself, prove that finite divergence never occurs on rows 33–1792. Shape/finiteness checks on those later rows would still admit finite drift there. Therefore the broad statement “prevents divergent finite features from ever entering training” is stronger than a 32-row-only guarantee.

If both arms match, the next causal/safety analysis must address this explicitly. One possible stronger boundary is CPU historical parity on every newly extracted TRAIN row, with no historical substitution and no extra model forwards, plus a final complete-admission check before normalization. That is a proposal, not an implemented or authorized production change here. Alternatively, any bounded-prefix-only safeguard must state its restricted guarantee and justify its operational sufficiency. Neither broad safety nor closure is inferred merely from `BOTH_MATCH_THROUGH_32`.

The frozen HPO parameters, datasets, architecture, original successful cache, historical evidence, current final source and existing consumed training authorization remain unchanged. No final training can start through the prepared arm executable regardless of its outcome.

## 8. Code changes and neutralize/fail/restore/pass evidence

New diagnostic-only source:

- `tools/prepare_auditor_blocker_closure.py`: deterministic payload creation, historical/input/source bindings, generated shared arm/helper, false authorization.
- `tools/auditor_blocker_support.py`: immediate CPU parity, post-boundary capture, bounded supervisor, diagnostic authorization and acquisition support.
- `tools/auditor_blocker_closure_cloud.py`: isolated one-instance controller derived from the earlier diagnostic controller, with an explicit pre-provider authorization gate, sealed-source/test binding, budget/watchdog, collection and teardown.
- `tools/analyze_auditor_blocker_closure.py`: post-teardown artifact verification and outcome classification; no model execution.
- `tools/test_auditor_blocker_closure.py`: local deterministic tests.

**20/20 tests passed** under local Torch 2.5.1+cpu. See [full test log](auditor_blocker_closure_run/local_tests.log). Tests cover exact passes; one-ULP finite drift; shape and NaN/+Inf/-Inf failures; dtype/signed-zero distinctions; durable refusal and I/O failure; both generated arms through 32 synthetic rows; first finite drift stopping at row 11; invalid vectors excluded from memmap persistence; original-versus-helper input inference context; unchanged loader/runtime/scope ASTs; absence of downstream fitting/training calls; sequential child dispatch; incomplete-O stopping; consumed-attempt refusal; authorization refusal before provider construction; and analyzer refusal before teardown.

The cloud-refusal test mocks provider construction and verifies it was never called. Generated-arm tests use a synthetic CPU model and mocked acquisition/runtime/adapter gates; they are not Linux/A10 model validation and do not claim full real-device capture succeeded.

[Neutralize/restore receipt](auditor_blocker_closure_run/neutralize_restore.json): replacing the diagnostic comparator's decision function with unconditional success makes the finite-drift regression fail; restoring the function makes it pass. The mutation is temporary in memory and was restored. This proves the diagnostic admission check is load-bearing for that test. It is **not** a production-fix regression or a demonstrated repair of the unknown native failure.

## 9. Cloud budget and teardown status

No new launch, instance, SSH registration, paid workload, collection archive, or teardown event exists. New cloud cost is **$0**. A fresh live inventory was not requested during preparation; old empty-inventory receipts are not represented as a new provider check.

If separately authorized, the controller must verify empty inventory, exact A10 capacity/price, and the pinned image before provisioning. At the $1.29/hour cap the $2 elapsed-time budget is 5,581.395 seconds; workload cutoff is 4,681.395 seconds, leaving a 900-second collection/teardown reserve. The watchdog requests termination by 5,401.395 seconds, before the hard deadline. The $1 soft checkpoint requires the remaining work and reserve to fit. Provider teardown delay remains an operational risk; the ceiling is enforced by cutoffs/watchdog requests, not a guarantee of provider billing latency.

The controller collects and hashes evidence before teardown when possible, then terminates regardless of workload success. Independent empty inventory and temporary SSH/local-key cleanup are required. A collection failure must not postpone termination. No second instance or launch retry is permitted.

## 10. Exact next action

**Stop here for separate operator authorization.** This boundary comes directly from the request attachment: “Do not launch cloud compute unless separately authorized by the operator” and “Prepare the exact experiment and stop for authorization before provisioning.”

The requested approval is only for the manifest and bundle hashes above: **one Lambda A10 24GB in us-east-1, O then D in two fresh sequential processes, at most 32 TRAIN forwards per arm, $1 soft/$2 hard, no warmup or training, no second instance/retry**. It does not authorize a final Auditor training retry.

After explicit authorization, bind that approval to the existing manifest, reverify the prepared source/test/bundle hashes and provider prerequisites, then use `tools/auditor_blocker_closure_cloud.py execute`. The remote workload command is `.venv/bin/python -B -u tools/auditor_blocker_support.py run`; the supervisor alone dispatches the two arms. After verified teardown, run `tools/analyze_auditor_blocker_closure.py`, update this report with the actual outcome/capture evidence, and perform the requested causal or safe-admission analysis. No approval was written during preparation.

Remaining unknowns are the original internal row-11 transition, original offending row-32 shape/values, relevant old device/native state, whether the two observed failures share one cause, and whether either cold path will reproduce them. The prepared diagnostic is designed to preserve the first new divergence if it occurs. Until its results justify closure, **AUDITOR_BLOCKER_STILL_OPEN** remains the final status and all other Project Shimmer roadmap work remains stopped. Producer Optuna HPO remains post-roadmap, after packaging.
