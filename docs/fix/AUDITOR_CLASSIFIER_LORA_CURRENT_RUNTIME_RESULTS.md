# Current-runtime rebase and final relation-training attempt

**AUDITOR_CLASSIFIER_LORA_INDETERMINATE**

The current-runtime rebase, live reference/fork parity and full-TRAIN consistency checks all passed. Joint training completed one optimizer update, then stopped at **attempted update 2, microbatch 1**, where finite CE **134.57772827148438** exceeded the frozen microbatch ceiling **55.451774444795625**. The gate stopped before that microbatch's backward call. No second joint optimizer update occurred.

The 20-update numerical admission **FAILED**. Neither quality checkpoint was reached, so this is not a valid quality PASS or FAIL. Per the operator's final stop rule, **this training path is stopped**. No retry, optimization change, cache investigation or further experiment was performed.

## Cloud and tested source

Implementation: `ceabb0afda9c87812e2461fd70c505fb6f9e4b9a`. Authorization attachment: `dcfd3146-30c0-488e-bfaa-43bf99428397`. Exactly one Lambda A10 24GB, one GPU, x86-64, us-east-1; instance `f4b7c342275a490a9c34ce45c4455f13`. Live rate **$1.29/hour** and empty initial inventory were verified before provisioning.

Soft budget $2.50; hard ceiling $3.50. Conservative full-work projection was 9,232 seconds / $3.308133, including a 600-second termination reserve. Hard runtime9767.442 seconds; workload cutoff9167.442 seconds; independent termination-watchdog cutoff9647.442 seconds. Runtime estimates included measured feature/update timing and all remaining mandatory work. The stop was numerical, not budget-related.

Launch epoch1789641450.9217272; termination verified **2026-09-17T11:00:21.570243Z**. Conservative launch-to-termination wall: **1,370.6485 seconds =22m50.65s**. Estimated upper-bound cost: **$0.49114905**, not an invoice. Evidence was collected and hash-verified before termination. Provider state was polled until absent, two subsequent inventories were empty, temporary SSH registration and local key files were removed. **Zero billable resources remain.**

Runtime bundle SHA-256: `7161d167bec8ea7ce3f39042a89e73cd4bf7c44ba252d55ecfe74d49fe1241d9`.

Evidence archive SHA-256: `57c20dfaf7d2ca6f87296f01ed3deb0135c99e8cd86ca0a64fcc764230d3dde4` (188,476,352 bytes).

## Fresh TRAIN features, normalization and head

All **1,792 TRAIN features** were extracted under the same pinned runtime and frozen historical reference adapter, in eval/inference mode, from the final normalized last prompt-token hidden representation. Shape1792x3072, FP32; extraction wall **386.5925 seconds**. Every row's ID, prompt/token hash, feature hash, finite flag and norm were persisted. No DEV features entered normalization or head fitting.

New TRAIN-only mean/std use FP32 population statistics, ddof0, std clamp1e-6. They remained fixed throughout the attempted joint phase. Old cached features, mean/std, head weights and expected logits were excluded from the upload and all admission anchors.

| Current artifact | SHA-256 |
| --- | --- |
| TRAIN features | `06e47fd6a0244cbff94f75e66eff81b4cad417843e34d62c3b370a3468cf8287` |
| Mean | `370b185841099279202b09540b45231f70fc1b109795faf520369964831678f5` |
| Std | `1221aff7ce64f090635267884183baabbd521e9a1738221555f074b4478f304a` |
| Fresh head after200 head-fit updates | `027c880e6c10a13f3e7354d12665ffacca5f7d68836291feaf195c167c13f915` |

One head, 12,292 parameters, zero W/b, seed7, full-population FP32 CE plus .001*mean(WÂ²), Adam LR.01, betas .9/.999, epsilon1e-8, weight decay0, no scheduler, exactly **200 updates** in **1.586669 seconds**. Head0/head200, all200 losses, TRAIN predictions and metrics were saved. Each update repeated its forward and gradient calculation from the same parameter state and required bitwise equality before the one optimizer step. Deterministic algorithms were enabled. This was arithmetic repeatability verification, not a second candidate or a repeated head-fit trajectory.

Head-fit TRAIN accuracy **0.9927455357142857** (1779/1792), macro F1 **0.9927336256393637**, CE **0.08585196733474731**. The predeclared TRAIN-only sanity gates passed. No optional update0 DEV metrics were computed.

## Live parity and real update0 baseline

The classifier fork was created after head fitting as an isolated exact copy of the immutable historical adapter. All448 tensor names, shapes, FP32 dtypes and values matched. Actual loaded tensors were checked against the source inventory. Source/fork initial adapter hash:

`733eb0005f898d1ff61aa72a92d84c1b35f11d52a9a09f3b0aafa73dfb35ade6`

Source/fork initial config hash:

`af6a53d6c24938eeaa74b5aaf753ebe7b67cf2b5be76d9fd5454fa6fdaa4d8b6`

All **16/16 current reference-versus-fork controls passed**. Maximum hidden error0; normalized-feature error0; logit error0; CE error0; argmax16/16 identical. The same bound token sequences and new normalization/head were used. Tolerances remained rtol1e-4/atol2e-4. No historical cached output was consulted.

The historical reference was reverified and removed before the full-TRAIN baseline and joint optimizer creation. There was no dual-adapter active or gradient path. The fork then evaluated all **1,792 TRAIN rows** without gradients. Phase8 predictions and all metrics matched Phase4 exactly:

- Accuracy: **0.9927455357142857**.
- Macro F1: **0.9927336256393637**.
- CE: **0.08585197478532791**, differing from Phase4 by ~7.45e-9.
- Recalls in MATCH/DIVERGENCE/OMISSION/ADDITION order: **0.9821428571 /0.9888392857 /1.0 /1.0**.

The runtime-local ceilings were persisted before joint optimizer update1 using the predetermined formula:

`max(10*ln(4),20*0.08585197478532791) =13.862943611198906` mean-update CE; microbatch CE ceiling **55.451774444795625**. Their equality to earlier numeric ceilings is due to the formula's uniform-CE floor, not reuse of old cached CE.

## Joint training and stop evidence

Authoritative remote inventory: frozen base0 trainable; removed historical reference0; classifier fork14,942,208; head12,292; total **14,954,500**. AdamW groups were verified at fork LR1e-4 and head LR1e-3, betas .9/.999, epsilon1e-8, weight decay0; combined clip1; no scheduler; microbatch1/accumulation4/effective4. Fixed FP32 normalization, head, logits, CE and regularization were retained with all numerical telemetry.

Completed **1/896 joint updates** on the exact scheduled first four TRAIN IDs. First and last completed-update mean CE: **0.006041544547770172**. Update wall **3.470272066 seconds**; median and p95 are both that value because there is only one sample, not a robust throughput estimate. Post-step fork/head parameters were finite and the frozen-parameter mutation check passed.

At update2/microbatch1, hidden, standardized hidden, logits, CE, regularization and total loss were all finite FP32. Logits ranged **-40.21820068 to94.35951996**; CE **134.57772827** triggered `microbatch_ce_explosion` before backward. No NaN/Inf or bad-gradient event is claimed. This is observed finite-loss explosion; its underlying cause was not investigated in this task.

Training CUDA allocation peak: **3.558658GiB**. Across795 whole-workload samples (including extraction, head fit and preflight), mean GPU utilization **92.7761%**, peak device memory **4,345MiB (~4.243GiB)**. These whole-workload utilization figures are not sustained joint-training statistics.

The initial joint checkpoint0 was preserved and verified against the source fork/current head/current normalization identities. A finite partial-state artifact preserves the fork/head after the one completed update:450 tensors,14,954,500 FP32 values, SHA-256 `01ca6da63b0dcde5fe89513a75fc83a60a65208988fd780b96ca20b5f198b05a`. It is not a selected or quality-qualified checkpoint.

Checkpoint448: **NOT REACHED**. External/SHORTER/LONGER/historical metrics and checkpoint fork/head hashes unavailable.

Checkpoint896: **NOT REACHED**. All corresponding metrics and hashes unavailable. No DEV logits were produced, reused or fabricated. Passing checkpoints: none evaluated. Selected checkpoint/fork/head/normalization: **none**.

## Preservation and local verification

63 deterministic local tests and packaged scope validation passed before launch. After teardown, the analyzer verified archive/source/preservation hashes; reconstructed TRAIN mean/std exactly; recomputed head-fit metrics and logits from saved fresh features; verified live control and Phase4/Phase8 consistency; checked runtime-local ceilings, optimizer groups, inventory, initial checkpoint hashes, partial-state inventory and exact completed schedule prefix. No local base/LoRA execution or additional training was used.

Historical source adapter/config and prior evidence seals remain unchanged. Base parameters were frozen in the authoritative inventory. Full base-state checks passed during preflight, and the completed step's frozen-parameter version check passed; **a final full base-state hash comparison was not reached**. This limitation is retained rather than claiming a missing final check.

Machine-readable results: `auditor_classifier_lora_current_runtime_run/RECOMPUTED_RESULTS.json`. Retained text evidence and local-only binaries are indexed in `EVIDENCE_MANIFEST.json`. Old cached representation provenance was not investigated or reconciled.

`V2_CORPUS_STATUS=AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`

`HOLDOUT_STATUS=UNCONSUMED`

`PRODUCER_STATUS=PRESERVED_UNEXECUTED`

Exactly one instance/GPU was used for this authorization. Only the fresh head was fitted, then only classifier fork + head received the one joint update. No generation, explanation/refusal training, new data, HOLDOUT, Producer, protected evaluation, full pipeline, governance, multi-round, paid inference API, retry or push occurred. Zero billable resources remain. This final attempt's authorization is consumed; the numerical-stop rule ends this training path.

## Subsequently authorized local analysis

One saved-state numerical analysis is complete: **AUDITOR_JOINT_TRAINING_STABILIZATION_UNISOLATED**. See [the analysis](AUDITOR_JOINT_TRAINING_STABILIZATION_ANALYSIS.md). The head-only explanation and tiny-std clamp pathology are excluded; the first LoRA AdamW step is the leading hypothesis, unresolved against dropout/mode effects. Exactly one design is proposed: LoRA LR 1e-4 to 1e-5. It is not implemented or authorized for execution. Current head/mean/std reuse is conditional on exact-runtime and full TRAIN consistency checks. No cloud or training occurred during this analysis.
