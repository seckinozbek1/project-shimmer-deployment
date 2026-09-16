# Second tuning experiment: canonical fold-0 pilot

Date: 2026-09-16. Final verdict: **SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE**.

`FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=false`

The authorized budget stopped this pilot during Producer checkpoint-120 DEV generation. Producer completed all 120 optimizer updates and checkpoint 60's full evaluation, but only 42/60 final DEV outputs were saved. Auditor training did not start. This is an incomplete execution, not a completed two-role experiment. Checkpoint 60 independently **FAILS** its frozen selection gates. Neither role has a selected checkpoint; no fallback was created.

## Cloud, source, and budget

| Item | Recorded value |
|---|---|
| Tested source commit | `a818d43ec38bafffbf9e57e124efaddabd6fcf57` |
| Release | `SECOND_TUNING_EXPERIMENT_DESIGN_READY`, second-domain-agnostic-v2 |
| Frozen release SHA-256 | `bb27d49234fcc30cf02438ac0ce1c43dc690cf514aa9ebbe8d4ae4f6341aa78d` |
| Provider / region | Lambda / us-east-1 |
| Instance | One fresh A10 24 GB, x86-64, BF16; `9051149f738c4d678c9e51a41212f60c` |
| Rate | $1.29/hour |
| Billable wall upper bound | 5,819.009 seconds / 96.9835 minutes, from launch request to verified termination |
| Estimated cost upper bound | **$2.085145**; not an invoice |
| Verified termination | 2026-09-16 10:32:40 UTC; second inventory query empty |
| Remaining resources | **Zero instances**; temporary SSH registration and local key material removed |

Fresh inventory showed A10 at $1.29/hour, unavailable A6000 at $1.09/hour, available A100 at $1.99/hour and H100 at $3.29/hour. A10 was the cheapest available suitable option. The prelaunch estimate, including setup and ten-minute reserve, was 121.94 minutes / $2.62165. Soft point: 93.02 minutes; hard point: 139.53 minutes; workload cutoff: 129.53 minutes. A separate watchdog guarded termination.

At the soft-budget assessment, cost was $2.011829 and 41/60 final Producer outputs were saved. Extrapolating measured final-DEV generation time left 1,435.976 seconds for Producer, plus the prelaunch 2,292.063-second Auditor estimate. Their total was **62.134 minutes**, against **35.961 minutes** before the reserve cutoff. Projected total cost with reserve was **$3.562710**. Continuation therefore failed the user's explicit soft-budget rule. No workload or hyperparameter was shortened to fit.

Automatic approval review initially rejected the process stop as unauthorized service interruption. Rechecking and citing the user's explicit soft-budget and blocked-work teardown instructions resolved the rejection; the same stop action was approved. One further output completed before the stop, leaving 42 final-checkpoint outputs. GPU process inventory was empty before packaging. The controller's generic `Frozen runtime failed` exception records the externally requested budget stop, not an observed OOM, nonfinite loss, or spontaneous training crash.

The initial generation estimate was too optimistic for this observed runtime: Producer generated about **1.875 tokens/second** at checkpoint 60 and **1.880 tokens/second** over the saved checkpoint-120 outputs. Checkpoint 60 averaged 29.78 output tokens; checkpoint 120's saved prefix averaged 141.55. The latter averaged 75.29 seconds per output. The evidence does not isolate a causal performance bottleneck. Observer tracing was enabled; its overhead was not separately benchmarked. No post-result runtime or configuration adaptation was attempted.

## Integrity and scope

Local gates passed before provisioning: exact HEAD and release binding, deterministic no-model dry-run (600 encoded rows; 14 fault checks), canonical equality with fold 0, 240/60 TRAIN/DEV per role, all 120 planned updates, grouped isolation, absent protected receipts, exact model pins, and credential/private-state scan. Provider metadata checks passed 11 tests; runtime-contract checks passed 26 tests. Authorization rejected all alternate split arguments, including the duplicate `0` alias; only `canonical` was permitted.

The 52-file minimal bundle excluded protected labels/evaluator and local credential/private state. Its actual-byte hashes and Git blob hashes are recorded in `manifest.json`. Windows-backslash paths in the frozen verifier were supported on Linux by in-root symlink aliases; no frozen source or JSON bytes were changed. Four legacy CRLF checkout files were explicitly checked against their committed content and exact frozen byte hashes. Those portability details are recorded rather than presented as byte-identical Git checkouts.

Before acquisition, remote checks passed Python 3.12.3, pinned packages, source compilation/imports, CUDA 12.1, one BF16-capable GPU, RAM/disk, release hash and schedules. Only the two pinned snapshots were acquired and hashed:

| Role | Model / revision | Actual architecture | Base weight SHA-256 |
|---|---|---|---|
| Producer | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` / `bdd404162d94997f390efbfa660eb3f21cbbc81d` | Qwen2ForCausalLM | `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d` |
| Auditor | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` / `5c20803aa197416f43fb455e55c85178775320cb` | LlamaForCausalLM (frozen configuration; not loaded for training) | `e6c61d932846517fc3d5bf09abb69b8c6f657b673ff8380999b15fb20cfcb64a` |

Producer executed the unchanged frozen trainer with local files only, remote code disabled and socket access blocked. Rank 8, alpha 16, dropout .05, seven projection families, AdamW 1e-4, microbatch 1 / accumulation 4, seed 7, BF16, checkpointing, eager attention, one warmup, linear decay, target-only per-example mean loss with native termination, two passes, sequence ceiling 992 and generation cap 288 were unchanged. Parameter proof records **20,185,088 trainable parameters, all LoRA**. Exact TRAIN IDs, DEV IDs and optimizer schedule are in `RUN_BINDING.json` and match the frozen canonical plan.

Post-termination checks verified the archive hash, remote freeze and observer bytes, all completed raw-output metrics against frozen scoring, checkpoint-60 adapter identity, all 120 step/loss observations, authorized DEV order/prefixes, both adapter hashes, cleanup and unconsumed protected receipts. There were 19 collected files; artifact security scan found zero credential findings (adapter headers scanned; binary payloads hashed). Partial checkpoint 120 was not aggregated or rescued into selection.

## Producer measurements

| Measurement | Value |
|---|---|
| Training updates / examples | 120/120; 240 distinct TRAIN examples, exactly two passes |
| Training wall | **973.189 seconds / 16.220 minutes** across two observed training windows |
| Timing definition | Parameter-proof event to update 60, plus last DEV-60 generation to update 120; minor setup/aggregation overhead included, model loading and generation excluded |
| Controller role wall through stop | 5,232.487 seconds / 87.208 minutes; includes initialization, training, DEV and interrupted work |
| Median ordinary update wall | 7.877 seconds (steps 1 and 61 excluded because they include initialization/DEV) |
| Model load | 33.595 seconds |
| Sampled peak allocated / reserved VRAM | **9.424 / 11.605 GiB** |
| Peak caveat | Sampled lower bounds, not CUDA final high-water marks: SIGTERM prevented the final status writer |
| Sampled peak process RSS | 5,646,000,128 bytes / 5.258 GiB |
| Telemetry | 5,067 samples, approximately one-second cadence |
| Loss first / last update | **0.818865 / 0.023798**; all 120 losses retained in observer events |
| Checkpoint 60 DEV | 60/60 outputs, 1,787 tokens, 953.448 seconds; all EOS |
| Checkpoint 120 DEV | **42/60 outputs**, 5,945 tokens, 3,162.214 seconds; saved outputs all EOS; in-flight output not counted |

The frozen `loss_diagnostics.json` was last written after checkpoint 60 and has 60 losses. The independent observer saved all 120 updates and losses; the final loss above comes from that trace. Reduced training loss does not establish generalization or a valid selected checkpoint.

### Checkpoint gates

| Frozen metric | Required | Step 60 | Step 120 |
|---|---:|---:|---|
| Contract validity | 1.00 | **1.0000 (60/60)** | Unavailable: incomplete |
| Six catastrophic categories | Each 0 | **All 0** | Unavailable |
| Typed-gap F1 | >= .80 | **.153846 FAIL** | Unavailable |
| Semantic completeness | >= .75 | **.200000 FAIL** | Unavailable |
| Accepted outcomes | >= .75 | **.200000 (12/60) FAIL** | Unavailable |
| Claim F1 | >= .95 | **.400000 FAIL** | Unavailable |
| Evidence F1 | >= .95 | **.400000 FAIL** | Unavailable |
| Typed-uncertainty F1 | >= .80 | **.263158 FAIL** | Unavailable |
| Refusal precision | >= .90 | **.081633 (4/49) FAIL** | Unavailable |
| Refusal recall | >= .80 | **1.000000 (4/4)** | Unavailable |
| Over-refusal | <= .05 | **.803571 (45/56) FAIL** | Unavailable |
| Substantive non-refusal coverage (diagnostic) | — | .196429 (11/56) | Unavailable |
| Eligibility | All frozen gates | **FAIL, measured** | **FAIL CLOSED, incomplete evaluation** |

Step 60 predicted refusal on **49/60** rows; four were expected refusals and 45 were over-refusals. The saved step-120 prefix contains five explicit refusals and 37 other parsed objects. That is a partial-output description only, not a full-population metric or evidence of passing the gates. No checkpoint-120 metrics file or selection decision exists. Producer selection status is **NOT_EVALUABLE_INCOMPLETE**, not a completed `ROLE_SELECTION_FAILED` decision.

### Gap failure taxonomy and run-1 comparison

The historical column is copied from the frozen `run1_audit.json`; run 1 was not rescored. Counts are atom-level error counts, not mutually exclusive counts of examples. The DEV populations differ (32 versus 60), so raw counts are descriptive, not a controlled improvement estimate.

| Failure class | Run 1 Producer step 16 (32 DEV) | V2 Producer step 60 (60 DEV) |
|---|---:|---:|
| Exact gap omission | 12 | **104** |
| Wrong referent | 8 | **1** |
| Wrong attribute | 4 | **0** |
| Wrong type/state | 1 | **2** |
| Other wrong type/field | 3 | **0** |
| Rendering failure | 6 | **0** |
| Extra gaps | 0 | **0** |
| Unparsed contract error | 1 | **0** |
| Invalid JSON | Not separately reported | **0** |

Run 1 accepted 10/32 Producer outputs; this complete V2 checkpoint accepts 12/60. Step 60's dominant failure is broad refusal and resulting omitted gaps, despite valid JSON. This does not demonstrate credible gap improvement. Step 120 remains unevaluable as a complete checkpoint; its partial outputs do not repair this evidence gap.

## Auditor: not run

The exact pinned snapshot was acquired and hash-verified, but the model was never loaded for training. Updates: **0/120**; DEV outputs: **0/120**. Training wall, VRAM, losses, macro relation F1, every-class recall, refusal precision/recall, over-refusal, substantive coverage, evidence F1 and accepted outcomes are **unavailable**, not zero-valued measurements.

| Output category | Step 60 | Step 120 |
|---|---|---|
| MATCH | Not evaluated | Not evaluated |
| DIVERGENCE | Not evaluated | Not evaluated |
| OMISSION | Not evaluated | Not evaluated |
| ADDITION | Not evaluated | Not evaluated |
| INSUFFICIENT_EVIDENCE / refusal | Not evaluated | Not evaluated |
| Malformed / other | Not evaluated | Not evaluated |

Both Auditor checkpoints **FAIL CLOSED for eligibility because they were not produced/evaluated**; neither has a measured semantic gate result. No Auditor checkpoint was selected. Historical run 1 step 24 remains 24/24 refusal, precision 8/24 = .333333, and 0% non-refusal coverage. This pilot provides no evidence that V2 Auditor avoids that collapse. No structurally valid all-refusal checkpoint is treated as success.

## Evidence, verdict and handoff

Archive: `second_tuning_canonical_pilot/evidence.tar.gz`, 149,117,060 bytes.

SHA-256: `647a437cc6c326ad1dc307e1a345d84d27f2be2d8189fcc9369c395ec2126469`.

Both saved Producer adapter payloads are retained locally:

- Step 60: `664e72eedc8bfc63b1dabfdb08bf7dcc93d8d0bcf17fcec4758d91dc6dcdcff8`.
- Step 120: `3f1e12d107f1206641902565b28ea6217d70ff2768c321a216227dbc21b702a6`.

Small evidence files, raw/parsed outputs, exact ID/schedule bindings, timings, telemetry, gates and hashes are committed locally. The archive and adapter binaries remain local, excluded from Git. `tools/analyze_second_tuning_pilot.py` verifies termination first, rechecks archive integrity, recomputes the complete checkpoint from raw outputs using unchanged frozen scoring, and refuses to select from partial evidence. Re-run locally with `python -B tools/analyze_second_tuning_pilot.py` while the retained archive is present.

`LOCAL_VERIFICATION.json` also confirms all 120 observed learning rates match the frozen schedule and every loss is finite. `COST_TIMELINE.json` reconstructs cost from saved event timestamps and the fixed rate, starting at the launch request; these are upper-bound estimates, not an invoice or a retained sequence of watchdog samples.

**SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE** is due to genuine bounded-runtime interruption, not a way to conceal the measured step-60 failure. A complete two-role verdict is unavailable. **FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=false**. The authorization is consumed; no retry, resume, extra fold, second instance or configuration change is implied. Any further cloud work requires a new explicit authorization, with the observed runtime considered before provisioning. The frozen V2 release remains unchanged.

Confirmed: canonical/fold 0 only; folds 1–4 not run; protected 114-example labels/evaluator never uploaded or opened; protected receipt **UNCONSUMED**; no BASE/protected comparison; no paid inference API; no hyperparameter/data/prompt/gate changes; no second instance; no full pipeline; no multi-round; no push; **zero billable instances remain**.
