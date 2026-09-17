# Ordinary final retry results — stopped for operator handoff

Status: **ORDINARY_FINAL_CLOUD_RUN_FAILED**. The one authorized retry ended; **zero provider instances remain**, temporary SSH credentials are removed, and the local controller and watchdog have exited. No further diagnosis, patch, launch or roadmap work is being performed after the operator's stop instruction.

## Bound identity and scope

- Authorized fix/seal commit: `eb71e6b9e1e43ee03855f686a277a08f8c503689`.
- Manifest: `f06584d937b732fe65b5966081768ad922751c6e7cc0324d45b74c49ad3552b5`.
- Seal: `96f2f496d37b009423f231e660ab5ec7ef41b93a46b07aefd5c3030e95302701`.
- Project archive: `4867e1db33e656117844028d647744a6316f2a6b8154949cde9087a1f08c138a`.
- Assets archive: `8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6`.
- Ordinary source remains `2f0d0f706fd0b68f757f664cb19d1956e69c27a1`.
- One Lambda `gpu_1x_a10`, us-east-1, verified **$1.29/hour**, instance `9f3b02f51531434f8917e216a7efb73f`.
- One `report_optimized`, `clinical_reference`, final-mode invocation. Producer168 and advisory Auditor896 artifacts unchanged. No second instance, automatic full-run retry, tuning, HPO, protected data or multi-round.

The live empty inventory, capacity/rate and exact image were reverified. All source/test/validation/support hashes matched; the project archive passed exact-tree verification. Every one of the 122 assets members was independently hash-verified locally, and all three generated refs resolved to the pinned revisions as exact 40-byte values. Both archives passed remote hash verification; Python 3.12.3, offline wheel installation, dependency closure, installed library-byte admission and hardware admission passed.

Only operator-side execution/analysis support changed for this retry: the existing controller's preparation/name constants became configurable; `ordinary_final_retry_cloud.py` binds them to this exact authorization; the evidence analyzer accepts a bundle path. The sealed remote code, models, workload, routing, pairing and telemetry were not changed. Controller failure/cleanup behavior was validated with fully mocked provider/SSH operations.

## What happened

The cache-family startup refusal is resolved in this execution: the pipeline body started, loaded BGE-M3 on CPU, built the reference index and embedded the selected corpus. It entered the first Producer-backed wave in phase 3–4.

Run ID: `88323b86f25e4ddc9f12deaddc4ffffa`.

- Pipeline start: 2026-09-17 **22:37:27.626463 UTC**.
- Failed completion: **22:38:09.169603 UTC**; `reached_end=false`, `error_type=RuntimeError`.
- Measured pipeline elapsed: **41.543391 seconds**. This is a failed prefix, not successful full-run latency.
- Full remote entry command including admission: **61.898715 seconds**, exit code **2**.
- Three backend failures: **ARCHIVIST**, **INST_FINDER**, **CITATION_RESOLVER**, each categorized `RuntimeError`.
- Producer model lifecycle includes `model_load_end`, followed by resident reuse for the latter two calls. Thus Producer loading was reached and completed; this is later than the prior startup refusal.
- There are **19 model-call receipts**, comprising **16 embedding receipts and three failed Producer168 calls**. The analyzer's generic `semantic_call_receipts` field includes embeddings and must not be read as 19 successful generative calls.
- No Auditor896 classifier calls/forwards or Producer→Auditor handoff occurred. No completed ordinary report or quality result exists.

The preserved telemetry contains exception categories but does not establish the underlying RuntimeError message/stack or a causal mechanism. No new cause is asserted. In particular, sampled VRAM is not proof of OOM, and a backend failure is not evidence that the trained weights are defective. Deeper inspection of generation-observation/call evidence and the exact executed call path is left for the handoff.

## Preserved timing and resource measurements

| Metric | Observed value / interpretation |
|---|---|
| Assets upload | 2255.28 s (37.59 min) |
| Producer failed-call service total | 23.970192 s; first includes cold loading |
| ARCHIVIST / INST_FINDER / CITATION_RESOLVER | 15.956704 / 3.959348 / 4.054140 s |
| Embedding model-call service total | 13.776595 s |
| Model-call wall interval union | 37.746786 s |
| Completed scheduler prefix critical path | 23.980678 s, three serial lane tasks; not a completed full-pipeline critical path |
| Semantic waves / max measured call concurrency | 1 / 1 |
| Resource sample count | 20, approximately two-second cadence |
| Sampled GPU utilization peak | 100% |
| Sampled VRAM peak / median | 16,499,343,360 / 248,512,512 bytes |
| Sampled CUDA allocated / reserved peak | 12,336,043,008 / 16,169,041,920 bytes |
| Sampled process RSS peak | 3,261,800,448 bytes |
| Sampled process CPU / system CPU peak | 2985% / 99.5%; process CPU can exceed 100% across cores |
| Sampled swap used | 0 |

Input/output token totals, generation duration, emitted/retained findings and truncation outcomes are unavailable. Zero true-valued cap-hit/contract counters are not evidence of successful or complete output. The separate legacy memory sampler reports a different RSS peak; retain both measurement streams without conflating sampling times. Process CPU time includes embeddings, inference/runtime work and telemetry, not isolated deterministic CPU work.

## Cost and teardown

Launch request epoch `1789681941.3188002`; first independent empty-inventory confirmation epoch `1789684805.39506`. Conservative infrastructure estimate through that confirmation: **$1.026294**; model/API cost **$0**; combined **$1.026294**, not an invoice. Both the $5 soft and $7 hard limits were respected. The old generic Claude/GPT-4o pre-run estimates in stderr are not actual API spend; this was the sealed local/offline profile.

The controller collected evidence, terminated the instance regardless of failure and removed the temporary provider SSH registration plus local keypair. A fresh post-controller provider client independently reconfirmed empty inventory and removed credentials at epoch `1789685084.2155452`. No persistent storage was created. Watchdog PID 30776 was confirmed exited, and the controller returned normally after cleanup.

## Evidence and handoff boundary

Evidence directory: `docs/fix/ordinary_final_cloud_run_v2`.

Collection SHA-256: `045e4514901822bc2c166085976869acd76f41083f8ac0c640f40d4e3d689593`. **All 37 collected files verified** against the remote hash inventory; raw files were not modified. Original archives and the generated binary embedding cache remain locally preserved with hash receipts. Derived summaries are under `analysis/`, separate from downloaded evidence.

Read first:

- `FINAL_STATUS.json`, `verified_evidence.json`, `remote_collection_manifest.json`.
- `downloaded/workload.stderr.log` and `downloaded/evidence/result.json`.
- `downloaded/evidence/run/audit/run_completion.json` and `execution_topology.jsonl`.
- `downloaded/evidence/run/logs/model_telemetry.jsonl`, `call_evidence.jsonl`, `generation_observation.jsonl`, `prompt_structure.jsonl`, `agent_bus.jsonl`.
- `analysis/model_telemetry_summary.json`, `ordinary_final_summary.json`, `stages.json`.
- `cleanup.json`, `independent_inventory_confirmation.json`, `operator_post_cleanup_confirmation.json`.

Known Auditor limitations remain: external macro F1 approximately 0.8010; historical approximately 0.4576; historical OMISSION recall **1/12**. This attempt did not reach Auditor inference and adds no Auditor-quality evidence.

The authorization is **consumed**. No further cloud run is authorized. Any continuation should first examine preserved evidence locally and distinguish model-load, prompt/tokenization, generation and exception-wrapping boundaries. No runtime fix, model workload or further roadmap action is implied by this handoff. Nothing was pushed.
