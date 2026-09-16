# Producer tuning V3 results

`PRODUCER_TUNING_V3_FAIL`

The single authorized fresh Producer V3 run completed all 168 updates and both fresh 84-row DEV evaluations validly. Neither checkpoint passes every frozen gate. No checkpoint is selected. Stop the Producer LoRA branch: no automatic V4, added data, hyperparameter sweep, or retraining. Any architecture/model-choice review requires a separate task.

## Cloud and cleanup

Tested cloud/executor commit: `668a9fa8e0bfe1a25736d241cd63c5ade290ba53`. V3 design commit: `eb958cd4d25a667ad2744cba01ac87c90270883f`. One Lambda Cloud A10 24 GB, x86-64, us-east-1, at **$1.29/hour**.

Launch-to-confirmed-termination upper bound: **4809.987 seconds (80 minutes 10 seconds)**. Estimated upper-bound compute cost: **$1.723579**, not a provider invoice. The $3 soft budget was never reached. Termination confirmed at `2026-09-16T16:52:06.872418+00:00`; independent subsequent inventory was empty. Temporary SSH registration and local key material were removed. Zero billable experiment resources remain.

Before launch the actual price allowed 139.535 minutes to $3 and 279.070 minutes to $6. The workload cutoff was 269.070 minutes, preserving ten minutes for evidence/teardown. A separate operator watchdog was armed to terminate before the hard ceiling. All durable progress projections remained within the cutoff.

## Identity and execution

Dataset `producer-targeted-v3.0` SHA-256: `b036707820a1851e94432319cc340cafec10a1b6093fab39b573cc4a47b9ecf0`. V3 freeze: `68afb77a9a5ff7c9360075c2699e6cb1d4cc57e1828728496a6648c49a3b7850`. Evaluation runtime `second-tuning-eval-runtime-v2_1` freeze: `8d1fd41d1ab059e47b1297c1c39cd29711acd8fa5446a60780f9a97faef1d1fa`.

Base: `unsloth/Qwen2.5-7B-Instruct-bnb-4bit`, revision `bdd404162d94997f390efbfa660eb3f21cbbc81d`, weight SHA-256 `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d`. Acquisition hashes, frozen configuration, and executed source hashes were verified. Base identity is bound by the acquisition/configuration receipts, rather than repeated in each low-level raw generation row.

Fresh seed-7 LoRA initialization was verified, including all-zero initial LoRA-B tensors and 20,185,088 trainable parameters. No V2 adapter was uploaded or loaded. The 420-row frozen corpus contains 336 TRAIN and 84 DEV rows, with no leakage-group overlap. The exact prospective four-example update order was verified: every TRAIN example appears twice, 672 exposures total, and no DEV example enters gradients. No update follows 168.

Optimization remained AdamW, LR 0.0001, betas 0.9/0.999, epsilon 1e-8, zero weight decay, linear schedule, one warmup update, clipping 1, microbatch 1 and accumulation 4. LoRA r8/alpha16/dropout0.05/bias-none and all seven frozen projection modules remained unchanged. Per-example mean target-only assistant-plus-native-termination loss retained equal example weights. Runtime remained BF16/eager, gradient checkpointing, deterministic algorithms, TF32 off, pinned NF4/double quantization; all 420 encodings fit 992 tokens, with observed maximum 988 and no truncation.

At each checkpoint, the real-object context preflight generated nothing; cache probes and both optimized six-ID control passes passed. All prompt/input IDs, output IDs, decoded strings, semantic/contract scores and stop reasons matched within each control pair. Each pass independently exceeded 4.438538339317307 output tokens/second. No historical traced-reference pass or observer-removal ratio was used. Exact parameter/gradient/optimizer/scheduler/adapter/training-counter and RNG restoration passed, including before update 85. Raw rows were fsynced before scoring; all 196 outputs were independently decoded and rescored locally after termination.

## Training telemetry

| Measure | Value |
| --- | --- |
| Optimizer updates | 168 |
| Training wall excluding DEV | 982.221 s / 16.370 min |
| First / final update loss | 1.587877840 / 0.015246504 |
| Update wall median / p95 | 5.851916 / 6.414139 s |
| Peak CUDA allocated / reserved | 11419709952 / 12459180032 bytes (10.635 / 11.604 GiB) |
| Training GPU utilization mean / median / p95 | 99.604% / 100% / 100% (957 samples) |
| Overall GPU utilization mean / median | 47.738% / 30% (3941 samples) |
| Training process CPU mean | 101.063% (100% corresponds to one logical CPU) |
| Peak sampled process RSS / host RAM used | 1682591744 / 3529121792 bytes |

Update losses use different scheduled examples and are descriptive training telemetry, not a held-out loss comparison. CUDA peaks are allocator counters; the separate telemetry process additionally records device memory and utilization.

## Checkpoint identity and runtime

Checkpoint 84 adapter SHA-256: `ddb2a0ba6e8687be573fafabb4f6d37a899142d5d9877c2c22ea06acc217816b`.

Checkpoint 168 adapter SHA-256: `8354d6545272399ea6771f1a6b560309e882fd7348f5c2be9cbd1bab01160703`.

Shared adapter-config SHA-256: `cd672d24a74575fe9bec0e0589aa84a41f3078d5a23edaaee8ae1cafbc683507`. Initialization adapter SHA-256: `61e13e0871378a204aa94d2ba4873e9e53cf37a5244aaa5c01c452aefc95e0e9`.

| Measure | Checkpoint 84 | Checkpoint 168 |
| --- | --- | --- |
| Deterministic controls | 6/6 | 6/6 |
| Control pass 1 / pass 2 tok/s | 8.506577 / 8.692683 | 8.859714 / 8.855092 |
| Fresh complete DEV | 84/84 | 84/84 |
| DEV generation wall (s) | 1253.262539 | 1407.980090 |
| DEV aggregate output tok/s | 8.820977 | 8.958223 |
| Generated DEV output tokens | 11055 | 12613 |
| Every frozen quality gate passed | FAIL | FAIL |

Generation timing includes prefill; decode-only latency and TTFT were not measured. CUDA synchronization bounded each generation. Full DEV throughput excludes cache/control probes.

## Frozen quality gates

| Metric | Required | Checkpoint 84 | Checkpoint 168 |
| --- | --- | --- | --- |
| contract_validity | >=1.0 | 0.988095238 | 1.000000000 |
| typed_gaps_f1 | >=0.8 | 0.763888889 | 0.861635220 |
| semantic_completeness | >=0.75 | 0.571428571 | 0.702380952 |
| claims_f1 | >=0.95 | 0.985365854 | 1.000000000 |
| evidence_f1 | >=0.95 | 0.985365854 | 1.000000000 |
| typed_uncertainty_f1 | >=0.8 | 0.787878788 | 0.920000000 |
| refusal_precision | >=0.9 | 0.380952381 | 0.555555556 |
| refusal_recall | >=0.8 | 1.000000000 | 0.625000000 |
| accepted_semantic_outcomes | >=0.75 | 0.571428571 | 0.702380952 |
| over_refusal_rate | <=0.05 | 0.171052632 | 0.052631579 |

Checkpoint 84 has 83/84 valid contracts and 48/84 accepted/complete outcomes. Checkpoint 168 has 84/84 valid contracts and 59/84 accepted/complete outcomes; at least 63/84 are required. Refusals: checkpoint 84 correctly refuses 8/8 required refusals, but also refuses 13/76 non-refusal rows; checkpoint 168 correctly refuses 5/8 and incorrectly refuses 4/76 non-refusal rows.

| Semantic atoms | 84 precision / recall / F1 | 168 precision / recall / F1 |
| --- | --- | --- |
| claims | 1.000000000 / 0.971153846 / 0.985365854 | 1.000000000 / 1.000000000 / 1.000000000 |
| evidence | 1.000000000 / 0.971153846 / 0.985365854 | 1.000000000 / 1.000000000 / 1.000000000 |
| typed_gaps | 0.880000000 / 0.674846626 / 0.763888889 | 0.883870968 / 0.840490798 / 0.861635220 |
| typed_uncertainty | 0.780000000 / 0.795918367 / 0.787878788 | 0.901960784 / 0.938775510 / 0.920000000 |

| Catastrophic category | Checkpoint 84 | Checkpoint 168 |
| --- | --- | --- |
| invented_evidence | 0 | 0 |
| invented_rule | 0 | 0 |
| confident_wrong_match_divergence | 0 | 0 |
| truncation | 0 | 0 |
| producer_source_copy | 0 | 0 |
| governance_violations | 0 | 0 |

These are the unchanged frozen scorer categories; zero counts are scoped to this canonical DEV evaluation, not a broader safety claim. DEV was used for selection and is not an independent final benchmark.

## Output efficiency

| Output tokens | Checkpoint 84 | Checkpoint 168 |
| --- | --- | --- |
| min | 10.000000 | 10.000000 |
| median | 168.000000 | 163.000000 |
| mean | 131.607143 | 150.154762 |
| p90 | 202.700000 | 205.000000 |
| p95 | 226.000000 | 221.350000 |
| p99 | 247.040000 | 245.340000 |
| max | 257.000000 | 247.000000 |

Both checkpoints: EOS before cap 84/84 (100%); cap hits 0/84 (0%); trailing prose 0; second JSON 0; code fences 0; exact/canonical duplicate atoms 0 in every atom category. Quantiles use linear interpolation at (n-1)q.

| Correct semantic atoms / all generated DEV tokens | Checkpoint 84 | Checkpoint 168 |
| --- | --- | --- |
| claims | 0.009136137 | 0.008245461 |
| typed_gaps | 0.009950249 | 0.010861809 |
| typed_uncertainty | 0.003527815 | 0.003647031 |
| evidence | 0.009136137 | 0.008245461 |

The denominator includes all 84 outputs, including failures and refusals; the numerator is exact micro-counted true-positive atoms. Per-row efficiency distributions are also preserved in RECOMPUTED_RESULTS.json. Efficiency never overrides a quality gate.

| Accepted category | Checkpoint | Count | Total tokens | Mean | Median | Min / p90 / p95 / p99 / max |
| --- | --- | --- | --- | --- | --- | --- |
| correct_refusals | 84 | 8 | 80 | 10.000000 | 10.000000 | 10.00 / 10.00 / 10.00 / 10.00 / 10.00 |
| correct_refusals | 168 | 5 | 50 | 10.000000 | 10.000000 | 10.00 / 10.00 / 10.00 / 10.00 / 10.00 |
| correct_empty | 84 | 4 | 108 | 27.000000 | 27.000000 | 27.00 / 27.00 / 27.00 / 27.00 / 27.00 |
| correct_empty | 168 | 4 | 108 | 27.000000 | 27.000000 | 27.00 / 27.00 / 27.00 / 27.00 / 27.00 |
| substantive_successes | 84 | 36 | 6335 | 175.972222 | 176.500000 | 119.00 / 203.50 / 214.50 / 240.10 / 245.00 |
| substantive_successes | 168 | 50 | 8848 | 176.960000 | 176.000000 | 119.00 / 208.10 / 228.50 / 246.02 / 247.00 |

Small refusal/empty groups have descriptive tail quantiles only; they are not stable population-tail estimates. Accepted-output cost conditions on correctness and is not a cost-per-attempt measure.

## Selection and stop rule

Passing checkpoints: none. Selected checkpoint: none. Selected adapter SHA-256: not applicable. Both complete checkpoints fail at least one gate, so the quality-first eligibility filter yields no candidates; completeness/gap/earlier-step/hash tie-breaks do not apply. The better-scoring checkpoint 168 is retained as evidence, not selected for deployment.

`PRODUCER_TUNING_V3_FAIL` — stop Producer LoRA. No V4, automatic data expansion, rank/LR changes, sweeps, or retraining. Recommend only a separately scoped architecture/model-choice review. Auditor is not the next automatically authorized action.

## Preservation, durability, and verification

The post-run frozen release verifier passed all 36 V3 bound files and dependencies, 436 historical byte hashes, three protected-artifact metadata checks, and two historical adapter metadata checks. Protected target labels were not opened; historical adapter tensors were not loaded. Historical `PRODUCER_CHECKPOINT120_FAIL`, `SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE`, runtime-V2 NO_GO and runtime-V2.1 evidence remain unchanged. Historical protected-wrapper inventory details remain documented in the pre-existing preservation receipt; this run used metadata-only protected checks.

`AUDITOR_STATUS=UNTOUCHED`  
`PROTECTED_RECEIPT_STATUS=UNCONSUMED`

Exactly one instance and one GPU were used. No second GPU, protected evaluation/access, Auditor acquisition/execution, folds 1-4, paid inference API, full Shimmer pipeline, multi-round run, or push occurred. Zero billable resources remain.

Downloaded archive: `producer_tuning_v3_run/evidence.tar.gz`, 182,859,528 bytes, SHA-256 `2c60cf6fbeffccee33f3d70ef927934c6f9490ceea1f9a8f4ddfb3978fca314d`. Archive hash matched before termination. Path-safe extraction and all checkpoint/config hashes passed afterward. Bulk archive and three adapter-weight files remain local and ignored; their hashes and all reviewable text evidence are committed. Copy those local binaries separately if moving to another machine.

Primary evidence under `producer_tuning_v3_run/`: `RECOMPUTED_RESULTS.json`, `RECOMPUTED_PER_ROW.json`, `POST_RUN_VERIFICATION.json`, `EVIDENCE_MANIFEST.json`, `final_inventory_confirmation.json`, `TERMINATION_VERIFIED.json`, and `downloaded/evidence/`. The latter contains exact training order/loss/LR records, adapter/config identities, state/RNG receipts, cache/control/raw DEV/scoring records, telemetry, and budget timeline. The execution bundle is hash-bound and contains only reviewed Producer scope. No old authorization was reused.

Local verification commands: `python -B tools/analyze_producer_v3.py`; `python -B tools/producer_v3_checks.py`; `python -B tuning/producer_v3/release.py`. The independent verifier requires the preserved local archive and adapters. It recomputed 196 raw outputs (168 full DEV + 24 control + 4 cache), all gates and selection, exact schedule, learning rates, fresh initialization tensors, checkpoint hashes, state restoration, and cleanup. Text evidence was scanned without printing credential values; zero findings.

Reproduction limitation: a checked-out repository contains the text evidence and identities; rerunning the full local verifier additionally needs the preserved local binary archive/adapters and existing pinned tokenizer assets. No new model generation is performed by the verifier.
