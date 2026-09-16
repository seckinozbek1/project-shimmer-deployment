# Producer checkpoint-120 evaluation runtime V2.1 results

**PRODUCER_CHECKPOINT120_FAIL**. Fresh 60/60 evaluation completed after every admission gate passed. Five frozen quality gates fail. Stop the Producer tuning branch; no automatic retraining.

Tested cloud integration commit: `539ca0c12cc734f7c35736baff1f6963008a5694`. Runtime freeze SHA-256: `8d1fd41d1ab059e47b1297c1c39cd29711acd8fa5446a60780f9a97faef1d1fa`. The frozen runtime was verified locally and remotely and remained unchanged. Local validation passed 92 tests / 11 effect proofs and three cloud-integration checks. Independent post-termination analysis verified all 74 raw rows (2 cache, 12 controls, 60 fresh DEV), decoded tokens, prompts, scores, and the verdict.

Cloud: one Lambda Cloud A10 24 GB, us-east-1, $1.29/hour. Launch-to-confirmed-termination upper bound 2400.059725 seconds (40.000995 minutes); estimated cost upper bound $0.860022, not an invoice. Hard ceiling $3, with 600 seconds reserved for teardown. Termination confirmed 2026-09-16T14:21:57.757621+00:00; subsequent inventory empty. Temporary SSH registration and local keys removed. Zero billable resources remain.

Real-runtime context preflight passed without generation: 61 owned fields, one nullable field, three identity groups. Shared Qwen2Config, GenerationConfig, and generation_config=None were inventoried. Exact configuration, training/checkpointing flags, adapter activation, parameter identity/dtype/device/requires_grad/version restoration passed.

Cache probes passed for both runtimes: prefill input 711, cache 0 -> 711; incremental input exactly one token, cache 711 -> 712. Both used eval mode, disabled gradients, and effective use_cache=True.

Six fixed controls ran reference then optimized on the same resident model. Prompt/token/decoded output/contract/semantic/stop identity: 6/6. Reference 1.931357131 output tok/s; optimized 8.941981839; ratio 4.629895578. Both frozen speed gates passed (>=4.438538339317307 tok/s and >=2x). `CHECKPOINT120_EVALUATION_ADMITTED`. Rates include prefill; no isolated decode or TTFT claim.

Full DEV: 8720 output tokens in 972.236440 generation seconds (16.203941 minutes), aggregate 8.969011698 output tok/s. All 60 were generated afresh in canonical order; no cache/control/historical outputs counted, no stitching or resume.

| Frozen quality metric | Actual | Required | Result |
|---|---:|---:|---|
| contract_validity | 1.000000000 | >= 1 | PASS |
| claims_f1 | 1.000000000 | >= 0.95 | PASS |
| evidence_f1 | 1.000000000 | >= 0.95 | PASS |
| typed_gaps_f1 | 0.760180995 | >= 0.8 | FAIL |
| typed_uncertainty_f1 | 0.909090909 | >= 0.8 | PASS |
| semantic_completeness | 0.583333333 | >= 0.75 | FAIL |
| accepted_semantic_outcomes | 0.583333333 | >= 0.75 | FAIL |
| refusal_precision | 0.571428571 | >= 0.9 | FAIL |
| refusal_recall | 1.000000000 | >= 0.8 | PASS |
| over_refusal_rate | 0.053571429 | <= 0.05 | FAIL |

All six catastrophic categories are zero: invented evidence, invented rule, confident wrong-match divergence, truncation, Producer source copy, governance violations. Accepted and semantically complete: 35/60. Refusals 7 (4 correct, 3 over-refusals); non-refusals 53, including four correct empty outputs and 49 substantive nonempty outputs.

| Output token distribution | Min | Median | Mean | p90 | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| All 60 | 10.000000 | 165.000000 | 145.333333 | 199.400000 | 209.150000 | 245.410000 | 246.000000 |
| Accepted (35) | 10.000000 | 162.000000 | 140.828571 | 204.200000 | 214.900000 | 240.240000 | 245.000000 |
| Accepted substantive (27) | 119.000000 | 176.000000 | 177.074074 | 206.200000 | 224.100000 | 241.360000 | 245.000000 |
| Refusal (7) | 10.000000 | 10.000000 | 10.000000 | 10.000000 | 10.000000 | 10.000000 | 10.000000 |
| Non-refusal (53) | 27.000000 | 176.000000 | 163.207547 | 202.200000 | 217.200000 | 245.480000 | 246.000000 |

EOS-before-cap: 60/60 (100%). Cap hits: 0/60. Trailing prose, second JSON, code fences, and outputs with exact/canonical duplicate atoms: each 0/60. Cap remains 288.

Accepted-output cost excludes failed outputs. The 35 successes comprise four correct refusals at 10 tokens each, four correct empty outputs at 27 each, and 27 substantive nonempty successes (mean 177.074074, median 176). Small-group tail quantiles should be treated cautiously. Short refusals do not establish substantive efficiency.

| Correct semantic atoms / generated output tokens (per-row distribution) | Mean | Median | p10 | p90 |
|---|---:|---:|---:|---:|
| all | 0.026342519 | 0.030288667 | 0.000000000 | 0.048377853 |
| claims | 0.007780193 | 0.008065041 | 0.000000000 | 0.016862192 |
| typed_gaps | 0.008078454 | 0.010101268 | 0.000000000 | 0.013698630 |
| typed_uncertainty | 0.002703680 | 0.002032520 | 0.000000000 | 0.006024096 |
| evidence | 0.007780193 | 0.008065041 | 0.000000000 | 0.016862192 |

Accepted substantive-only atoms/token: mean 0.036174086, median 0.035175879. Per-row values and full distributions are preserved in RECOMPUTED_PER_ROW.json and RECOMPUTED_RESULTS.json.

Historical comparison is descriptive only, performed after fresh completion. The old checkpoint-120 evidence remains **42/60 PARTIAL_PREFIX_ONLY** and is not a complete checkpoint verdict. All 42 overlapping generated token sequences match this fresh run.

| Metric | Historical checkpoint 60 (60/60) | Historical checkpoint 120 (42/60 PARTIAL_PREFIX_ONLY) | Fresh checkpoint 120 V2.1 (60/60) |
|---|---:|---:|---:|
| Refusals | 49.000000 | 5.000000 | 7.000000 |
| Non-refusals | 11.000000 | 37.000000 | 53.000000 |
| Substantive nonempty outputs | 7.000000 | 35.000000 | 49.000000 |
| Accepted substantive outputs | 4.000000 | 22.000000 | 27.000000 |
| Output tok/s | 1.874250 | 1.880012 | 8.969012 |
| EOS-before-cap rate | 1.000000 | 1.000000 | 1.000000 |
| Output tokens min | 10.000000 | 10.000000 | 10.000000 |
| Output tokens median | 10.000000 | 161.500000 | 165.000000 |
| Output tokens mean | 29.783333 | 141.547619 | 145.333333 |
| Output tokens p90 | 143.200000 | 197.000000 | 199.400000 |
| Output tokens p95 | 183.100000 | 198.900000 | 209.150000 |
| Output tokens p99 | 192.510000 | 201.360000 | 245.410000 |
| Output tokens max | 199.000000 | 203.000000 | 246.000000 |
| contract_validity | 1.000000000 | 1.000000000 | 1.000000000 |
| claims_f1 | 0.400000000 | 1.000000000 | 1.000000000 |
| evidence_f1 | 0.400000000 | 1.000000000 | 1.000000000 |
| typed_gaps_f1 | 0.153846154 | 0.775510204 | 0.760180995 |
| typed_uncertainty_f1 | 0.263157895 | 0.913043478 | 0.909090909 |
| semantic_completeness | 0.200000000 | 0.619047619 | 0.583333333 |
| accepted_semantic_outcomes | 0.200000000 | 0.619047619 | 0.583333333 |
| refusal_precision | 0.081632653 | 0.400000000 | 0.571428571 |
| refusal_recall | 1.000000000 | 1.000000000 | 1.000000000 |
| over_refusal_rate | 0.803571429 | 0.075000000 | 0.053571429 |

Historical checkpoint 60 shows refusal collapse; short outputs do not demonstrate quality. Prefix composition prevents interpreting the historical checkpoint-120 partial rate as a full-DEV comparison. Full historical distributions, semantic metrics and accepted-cost breakdowns are in the machine-readable results.

Immutable identities: base `unsloth/Qwen2.5-7B-Instruct-bnb-4bit`, revision `bdd404162d94997f390efbfa660eb3f21cbbc81d`; base SHA-256 `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d`; adapter `3f1e12d107f1206641902565b28ea6217d70ff2768c321a216227dbc21b702a6`; adapter config `cd672d24a74575fe9bec0e0589aa84a41f3078d5a23edaaee8ae1cafbc683507`. Hashes and loaded adapter tensor equality passed. Generation stayed greedy, batch one, BF16 compute/eager attention, exact frozen prompts/tokenizer, EOS [151645], padding 151654, cache enabled. No adapter merge or output repair.

Runtime: Python 3.12.3; Torch 2.5.1+cu121; Transformers 4.51.3; PEFT 0.15.2; tokenizers 0.21.1; accelerate 1.10.1; bitsandbytes 0.48.2; safetensors 0.5.3; huggingface-hub 0.30.2; numpy 2.0.2; jinja2 3.1.4. Acquisition followed preflight; subsequent loading/execution used the local snapshot.

Evidence: [directory](producer_checkpoint120_eval_v2_1/), [recomputation](producer_checkpoint120_eval_v2_1/RECOMPUTED_RESULTS.json), [verification](producer_checkpoint120_eval_v2_1/POST_RUN_VERIFICATION.json), [termination](producer_checkpoint120_eval_v2_1/TERMINATION_VERIFIED.json). Archive SHA-256 `b9cc8c94a81029ea3a3c7a781d4a3fda6407e2ae659cb0c7774bd113f394093e` matched the remote archive before extraction. EVIDENCE_HASHES.json binds retained evidence. Raw prompts/token IDs/outputs, context nullable inventory, cache observations, controls, telemetry, versions, timing, cost timeline and cleanup receipts are preserved. Security scans found no credentials.

All 125 historical preservation entries passed fresh byte hashes. V2.1 release verification additionally checked 217 historical files and 10 metadata-only entries. Original statuses remain `SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE`, `FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=false`; historical failed runtime-V2 evaluation remains `PRODUCER_CHECKPOINT120_INDETERMINATE` / `CHECKPOINT120_EVALUATION_NO_GO`. This report records the separate completed V2.1 evaluation.

`AUDITOR_STATUS=UNTOUCHED`

`PROTECTED_RECEIPT_STATUS=UNCONSUMED`

No training, optimizer creation, weight update, Producer retraining, Auditor acquisition/execution, folds 1-4, protected access, paid inference API, second instance, full pipeline, multi-round execution, or push occurred. Stop the Producer tuning branch; no automatic retraining.
