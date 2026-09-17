# Ordinary final cloud run: startup refusal

Status: **ORDINARY_FINAL_CLOUD_RUN_FAILED**. The authorized invocation stopped before model loading/inference or pipeline execution. This is a cache-resolution startup failure, not a Producer/Auditor model failure. No retry or second instance was launched.

## Execution and outcome

- Preparation commit: `776d8c131279c88798e4a27d6099c98e8d5d7643`.
- Ordinary source: `2f0d0f706fd0b68f757f664cb19d1956e69c27a1`.
- Manifest SHA-256: `dcc3aa913b2e59ca2831bc92009b9f888ca0a23e617f4a8d02acb0761876f223`.
- Seal SHA-256: `93d2c5b2fe371f19143abe536569fe7bf15bcf9307b3136826b6440e028a4916`.
- One Lambda `gpu_1x_a10`, us-east-1, reverified $1.29/hour. Instance `a2ee83366fef4ed8b30e6d1970edf302`.
- Exact approved `clinical_reference`, ordinary `report_optimized`, final mode; no workload/model/routing substitution.
- Launch requested 2026-09-17 20:45:18 UTC; independent empty-inventory confirmation 21:31:31 UTC. A second independent post-controller read at 21:31:48 UTC also confirmed empty inventory.
- Conservative infrastructure estimate through the first independent confirmation: **$0.993761**, 2773.29 seconds. Model/API cost $0. This is an estimate, not an invoice; both budget limits were respected.

Local source/artifact/wheel reverification and 14 preparation tests passed. Both transferred archives passed remote SHA-256 verification. Offline installation and `pip check` passed. Installed library-byte admission, final artifact hashes, Python/CUDA/BF16 and hardware admission were reached successfully before the startup refusal. Observed hardware: NVIDIA A10, driver 580.126.20, 23,684,841,472 GPU bytes, 30 logical CPUs, 238,546,341,888 RAM bytes.

| Measured controller phase | Seconds |
|---|---:|
| Activation | approximately 212 |
| Support upload | 32.46 |
| Model/wheel assets upload | 2299.18 |
| Remote archive hash verification | 13.47 |
| Extraction | 9.87 |
| Offline wheel installation | 71.49 |
| Single entry-point invocation, including admission | 19.41 |
| Evidence download | 7.04 |

The entry point returned 2. The original terminal receipt records `SystemExit`; stderr says `Cannot establish independent cached local model families.` The assessor correctly refused completion with `pipeline_not_completed` and `required_telemetry_missing`. Its fallback `pipeline_exit_code=1` is an initialized sentinel after the caught exception, not the argparse exit status. No RunCompletion, model-call receipt, semantic wave, generated finding, classifier forward or performance/quality measurement exists. The 19.41 seconds is startup/admission elapsed time, **not pipeline latency**. Critical path, tokens, throughput, model service, pairing coverage and inference resource peaks are unavailable.

## Proven startup defect

The generated transfer archive contains 41-byte `refs/main` files: the correct 40-character revisions followed by LF. `ordinary_final_run.py` accepted them using `.read_text().strip()`. The pinned `huggingface_hub==0.30.2` offline resolver reads refs verbatim (`commit_hash = f.read()`), then looks for a snapshot directory whose final component includes that LF. The actual directories have the 40-character names. Resolution therefore raises `LocalEntryNotFoundError`, which the topology entry guard catches as `OSError` and turns into the generic family error.

The model-free probe `tools/probe_ordinary_final_cache_refs.py` uses the exact pinned wheel and original archive ref/config bytes. All three models fail default-revision resolution with the original refs, resolve by explicit revision, resolve with a 40-byte ref in a temporary fixture, and fail again when original bytes are restored. Production/archive bytes were not modified. Evidence: `ordinary_final_cloud_run/cache_ref_failure_probe.json`.

The model configs are distinct: Producer `qwen2`, shared Auditor/VERIFIER base `llama` (despite the public Phi model ID), and BGE `xlm-roberta`. The failure occurs before a family comparison. No evidence supports a numerical/model failure or a change to pairing semantics. Follow-up startup correction and resealing are separately documented; this run and its consumed authorization remain immutable.

## Evidence and cleanup

Remote collection archive SHA-256: `5f8dd70de87eb9bbbf0ae9c3c05aec26b40bd6c7641fd907e8d7de64e9b51272`. All **12** collected files matched their remote per-file hashes. Original archive and raw evidence are preserved locally; derived analysis lives separately under `ordinary_final_cloud_run/analysis`. Large payload/archive files remain uncommitted, with committed inventories/hashes.

The controller terminated regardless of failure. Provider inventory is empty; the temporary provider SSH registration and local private/public files are removed. No persistent storage was created. See `cleanup.json`, `independent_inventory_confirmation.json`, and `operator_post_cleanup_confirmation.json`. The independent watchdog also verified termination. No protected data, multi-round, Producer/Auditor training, HPO, model replacement or subsequent full workload occurred. Nothing was pushed.

Known Auditor limitation remains unchanged: external macro F1 approximately 0.8010; historical macro F1 approximately 0.4576; historical OMISSION recall **1/12**. This attempt supplies no new classifier-quality evidence.
