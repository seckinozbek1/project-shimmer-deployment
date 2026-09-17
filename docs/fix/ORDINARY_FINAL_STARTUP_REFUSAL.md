# Ordinary final startup refusal: cache-ref root cause and correction

Status: **STARTUP_BLOCKER_FIXED_NEW_EXECUTION_SEALED**. Local deterministic validation only after teardown. **No new cloud execution is authorized or performed.** The consumed attempt and verified cleanup are recorded in [ORDINARY_FINAL_CLOUD_RUN_RESULTS.md](ORDINARY_FINAL_CLOUD_RUN_RESULTS.md), committed as `20d553a`.

## Finding

The refusal was caused by malformed generated Hugging Face cache refs, not by two non-independent models or an incompatible Producer168/Auditor896 layout. The assets archive generated for the authorized attempt contained a trailing LF after each revision. I introduced those newline-terminated refs during transfer preparation. The sealed admission code also failed to detect that mistake because it stripped whitespace before comparison.

`huggingface_hub==0.30.2` reads `refs/main` verbatim. A 41-byte revision-plus-LF value resolves to a nonexistent snapshot-directory name. Its `LocalEntryNotFoundError` is an `OSError`, caught by the topology entry guard and reported as the generic family error. This mechanism reproduces with the exact preserved bytes and pinned library. Removing only the LF in a temporary config-only fixture makes the actual startup guard pass; restoring it makes resolution fail again.

No model loading or inference was reached. Torch/CUDA runtime admission initialized the CUDA runtime, but that is not a model forward. This is **not a model failure**.

## Exact executed branch and expected identities

Executed ordinary source: `2f0d0f706fd0b68f757f664cb19d1956e69c27a1`, bound by the consumed manifest. Source below was compared against the actual project archive, not inferred from old design documentation.

1. `tools/ordinary_final_run.py:execute` configured `HF_HOME=/home/ubuntu/shimmer-ordinary-final/hf_cache` and `HF_HUB_CACHE=/home/ubuntu/shimmer-ordinary-final/hf_cache/hub`. It verified snapshot files and accepted refs via `.read_text().strip()`. It admitted final artifact hashes/runtime, recorded hardware, denied external network and called `pipeline.main(argv)` once.
2. `scripts/pipeline.py` defines base-profile fallback IDs, then **at import time** calls `_resolve_local_models(_LOCAL_PROFILE, ROOT)`. The archived `config/local_models.json` replaces those fallback IDs by backend with the active unsloth IDs below. The guard therefore did **not** inspect the stale Qwen/microsoft fallback cache IDs.
3. `scripts/execution_topology.py:entrypoint`, lines 254–261, takes the `report_optimized` branch and calls `semantic_waves.validate_model_families(target.__globals__["_LOCAL_PROFILE"], agent_wrapper._local_checkpoint_path)`. It catches `(OSError, ValueError, KeyError)` and calls `parser.error("Cannot establish independent cached local model families")`.
4. `scripts/semantic_waves.py:validate_model_families`, lines 35–47, iterates the unique `(backend, model)` pairs. It reads the resolved snapshot's `config.json`, gathers nonempty `model_type` strings for `local_producer` and `local_auditor`, and requires both sets to be nonempty and disjoint. It does not require brand-name strings `Qwen` or `Phi`, compare adapter IDs, or expect a distinct third family for VERIFIER.
5. `scripts/agent_wrapper.py:_local_checkpoint_path`, lines 132–148, calls `snapshot_download(model_id, local_files_only=True)` without an explicit revision for a repo ID. The pinned loader reads `refs/main` to select the revision. In this attempt the resulting snapshot path did not exist.

| Role inspected by the guard | Resolved active model ID | Pinned snapshot / expected config family |
|---|---|---|
| Producer roles, including PROCESSOR | `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` | `bdd404162d94997f390efbfa660eb3f21cbbc81d` / `qwen2` |
| Auditor roles, including generative VERIFIER | `unsloth/Phi-3.5-mini-instruct-bnb-4bit` | `5c20803aa197416f43fb455e55c85178775320cb` / `llama` |

The checked cache roots are respectively:

```text
/home/ubuntu/shimmer-ordinary-final/hf_cache/hub/models--unsloth--Qwen2.5-7B-Instruct-bnb-4bit
/home/ubuntu/shimmer-ordinary-final/hf_cache/hub/models--unsloth--Phi-3.5-mini-instruct-bnb-4bit
```

Each should resolve `snapshots/<40-character revision>/config.json`. Instead its `refs/main` produced a path ending in `<revision><LF>`. Both model roots have this defect. The guard iterates a set and the remote receipt did not preserve its underlying exception or iteration order, so **which model was attempted first is not recoverable**. The deterministic fixture proves either lookup fails. The guard did not reach a comparison and did not conclude that any two families were the same.

The advisory Auditor896 descriptor uses the same canonical base as the unadapted generative Auditor/VERIFIER, with separate final adapter/head/statistics and classifier behavior. That shared Auditor family is intentional; independence is between Producer and Auditor roles. The archived final descriptors and active-model config agree. The public Phi alias has `model_type=llama`; architecture detection correctly uses that config value, which is disjoint from `qwen2`. BGE's third malformed ref would also fail default resolution, but BGE is **not** part of this family check and was not reached.

## Evidence and alternatives tested

| Candidate | Evidence / falsification | Verdict |
|---|---|---|
| Newline cache refs | Original 41-byte refs fail pinned offline lookup; exact revisions resolve; 40-byte refs pass actual guard; restoring LF fails | Established immediate cause |
| Same Producer/Auditor architecture | Hash-verified configs are `qwen2` and `llama`; corrected cache passes; synthetic same-family config still refuses | Ruled out for preserved artifacts |
| Stale base-profile aliases | Actual import-time resolver maps every applicable role to the two transferred unsloth IDs | Ruled out |
| Final classifier versus generative VERIFIER confusion | Exact final configuration passes unchanged once refs are corrected | Ruled out as this refusal's cause |
| Model inference/numerical failure | Guard fails before pipeline body, model loading or forwards; no model-call receipts | Not reached |
| Missing/corrupt model weights or changed runtime pins | Remote archive, snapshot, installed library-byte and final artifact admissions passed | No supporting evidence; not needed to explain refusal |

The remote top-level `SystemExit` receipt is coarse. The preserved archive hashes, source branch and exact local resolver/guard reproduction supply the specific causal evidence; no claim is made about the lost first-error stack or set iteration order.

## Minimal correction

- `tools/ordinary_final_run.py`: `cache_ref_bytes` requires a 40-character lowercase hexadecimal revision and returns exactly its ASCII bytes. `admit_cache_ref` requires the manifest's ref length/hash and exact file bytes. No whitespace stripping or automatic repair occurs.
- `tools/prepare_ordinary_final_assets.py`: replaces the ad hoc transfer-archive construction with a deterministic regular-file archive builder. It verifies every input hash/length and creates exact 40-byte refs using the shared encoder.
- `tools/prepare_ordinary_final_run.py`: hashes generated refs explicitly in each model descriptor, binds the complete 122-member assets archive and its inventory, records generator source hashes, and requires a separate output directory. An existing manifest cannot be overwritten.
- The family guard, ordinary runtime, final model descriptors, weights, HPO provenance, pairing contracts, telemetry, workload and routing are unchanged. The fix belongs to the **cache preparation/admission boundary**, rather than weakening the family safeguard or adding aliases.

## Deterministic validation

`tools/ordinary_final_startup_checks.py` builds config-only fixtures from the original transfer archive and uses the exact pinned Hub wheel. It executes the actual parser/profile resolver, topology entry guard, family detector and local checkpoint resolver. Only scheduler construction and the pipeline body are replaced with sentinels: the failure must occur before the body, and corrected refs must reach the body without inference.

- **18 startup/preparation checks PASS**: four exact-cache/startup regressions plus all 14 prior preparation checks.
- **104 existing integration checks PASS**, ordinary activation gate PASS, **seven existing neutralize/fail/restore/pass proofs PASS**. No multi-round gate was chained.
- **Three new neutralize/fail/restore/pass proofs PASS**: restoring the old whitespace-stripping admission breaks the whitespace test; restoring newline ref generation breaks the archive/resolver test; bypassing family independence breaks the same-family refusal test.
- All **122 real new archive members** independently hash/length verified. All three real generated refs resolved offline to their exact pinned snapshots with the pinned library. No model weights were loaded.
- The real project archive extracted and passed exact tree/hash/seal verification. Old/new comparisons prove identical ordinary source/project archive, workload, config/artifacts, snapshot files, package/wheel pins, environment, argv and topology.
- The startup gate explicitly blocks model/provider imports and network. Its first harness run mistakenly blocked an internal relative Hub module called `openai`; the guard was corrected to distinguish relative imports, then the entire gate passed. This was a test-harness issue, not a runtime patch or cloud attempt.

Evidence: `ordinary_final_startup_fix/startup_validation.json`, `startup_tests.log`, `integration_validation.json`, `integration_no_generation_tests.log`; new bundle `asset_verification.json` and `source_validation.json`. The expected failures inside mutation-proof logs are deliberate; the final receipt requires restored tests to pass.

## New sealed identity — not authorized

Directory: `docs/fix/ordinary_final_cloud_run_v2`.

| Item | SHA-256 |
|---|---|
| Execution manifest | `f06584d937b732fe65b5966081768ad922751c6e7cc0324d45b74c49ad3552b5` |
| Seal | `96f2f496d37b009423f231e660ab5ec7ef41b93a46b07aefd5c3030e95302701` |
| Project archive (unchanged) | `4867e1db33e656117844028d647744a6316f2a6b8154949cde9087a1f08c138a` |
| Assets archive | `8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6` |
| New admission source | `d0ad366f363e2a6da87a433a08c6fe8927a731f92db95fb8593e6860d5c5d201` |

The ordinary source commit remains `2f0d0f706fd0b68f757f664cb19d1956e69c27a1`; support/preparation changes are separately hash-bound and committed with this report. Local ignored archives are retained; small manifests, source, tests and receipts are committed. The new directory contains **no operator authorization, launch intent or execution claim**. The old controller remains bound to the consumed old identity and cannot be used for this new bundle. Any future launch must explicitly bind the new manifest/seal, reverify live empty inventory/capacity/rate and obtain separate operator authorization; this work does not launch or authorize it.

The new bundle's provider-capacity snapshot is historical preparation evidence, **not a current availability claim**. The independently confirmed post-run inventory was empty. No persistent resources remain and temporary SSH credentials were removed. The failed attempt cost approximately **$0.994**, not an invoice.

Known Auditor weakness remains: external macro F1 approximately 0.8010; historical approximately 0.4576; historical OMISSION recall **1/12**. No inference quality/performance was measured here. Full Linux/model execution beyond this startup guard remains untested by this correction. Stop for operator review; no tuning or further roadmap work is started.
