# Ordinary final run v6: the four corrections held on the A10; integrity did not pass on two residual causes

Status: **ORDINARY_FINAL_CLOUD_RUN_V6_WORKLOAD_COMPLETED_INTEGRITY_NOT_PASSED**. One authorized
instance ran for 52.8 billable minutes and was terminated; provider inventory is empty on the
controller's reading, on its independent client and on a fresh operator-side client; the
temporary SSH registration and the local key are removed; the watchdog exited. The sealed
workload was invoked exactly once, every controller phase passed with zero unreachable polls,
and the pipeline reached its end (exit 0, one document, three amendments) in 346 s. The sealed
runner returned exit 2 with the same two reason names as v5, `pipeline_not_completed` and
`required_contract_failure`, but behind them the four v5 causes are down to two: one PROCESSOR
partition whose all-empty answer omits the `uncertainty` key, and FACT_CHECKER on the untuned
auditor base replacing its `verdict` with `record_verdict`. No second instance, no retry,
nothing pushed. The authorization bound to bundle v6 is consumed.

## Bound identity, reverified before launch

Source and preparation commit `a387a83a2ccd3bfebbba29d05fcecddb69af5829` (the four corrections),
seal commit 92cf995, manifest `378db7e19fca2d1729140a5bf9fffe5a3e597cca73979dabbea158d8df77cec9`,
seal `f9b6a4309f309db6b8c37832fd8646666cc67abc148c0115f8a2dd4cc9b5d218`, project
`b823e404b2028921bf30e0777e4122e9f2156b458c225ec1b275c2262ab2c27f`, assets
`8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6` rebound from v5, not rebuilt
(122 members verified, three 40-byte refs), controller `7562dad3…`. Local reverification: 152
members compared to the sealed commit, `head_moved_by_evidence_only: []`,
`sealed_runtime_is_what_launches: true`, decoding policy admitted with the same digests the
instance admitted. Live preflight: inventory empty, A10 listed in us-east-1 at $1.29, image
`gpu-base-24-04` 24.4.4-2141 present. The v6 archive itself was rehearsed through the
controller's own phases on the local Ubuntu before launch (357 s, both polarities). The launch
receipt records exactly these values.

## What happened, in the controller's order

Instance `f82600af47c34e4982b1396ccdb31b51`, `gpu_1x_a10`, us-east-1, $1.29/h. Launched
12:42:07 UTC; active after 222.6 s.

| Phase | Seconds | Exit | Polls (unreachable) |
|---|---|---|---|
| ssh_ready | 2.0 | 0 | |
| python_gate | 8.1 | 0 | 1 (0) |
| fresh_directory | 7.8 | 0 | 1 (0) |
| support_transfer | 31.6 | 0 | |
| assets_transfer (13,149,972,480 bytes) | 2227.8 | 0 | |
| archive_integrity | 19.8 | 0 | 2 (0) |
| extract_payload | 19.6 | 0 | 2 (0) |
| create_environment | 7.8 | 0 | 1 (0) |
| install_pinned_wheels | 79.2 | 0 | 7 (0) |
| dependency_closure | 7.7 | 0 | 1 (0) |
| gpu_metadata | 7.7 | 0 | 1 (0) |
| watchdog_receipt_transfer | 3.0 | 0 | |
| ordinary_workload | 376.9 | 2 | 32 (0) |
| stop_workload, final_gpu_state, pack_evidence, evidence_hash | 7.8 each | 0 | 1 (0) each |
| evidence_download (1,263,873 bytes, hash verified) | 7.2 | 0 | |

The upload is 37.1 of the 52.8 billed minutes. Inside the workload the runner passed every
admission and ran the pipeline (run id `0cbc7f262a7448479517aba8a2c9ae1f`) from 13:26:31 to
13:32:17 UTC:

| Pipeline phase | Wall seconds |
|---|---|
| 3-4 content production | 227.9 |
| 5 verification and fact check (FACT_CHECKER only) | 16.6 |
| 5.5 convention review, paired | 59.8 |
| 6 synthesis | 0.3 |
| 6.5 editorial board | 26.2 |

## The corrections, as they behaved on hardware

| Correction | Evidence from the run |
|---|---|
| A3, the `confident` alias | fired on ARCHIVIST, LEGAL_ANALYST twice and EDITOR_CLERK; all four calls contract-valid; `contract_normalized` recorded on the result, the bus post, the observation row and the telemetry call record |
| A2, the validated prompt shape | every PROCESSOR call sent as the two validated turns; partition 0 (four spans) passed the compact contract and hydrated on the bus |
| A1, grounding by passage placement | in force; partition 0 cited no refs at all, so no citation exercised it on this run (the v5 raw outputs remain its executed proof) |
| A4, VERIFIER | not called: activation ledger `activated: false`, reason `processor_draft_unavailable`; pairing recorded `AUDITOR_PAIR_UNAVAILABLE` with the same reason; no VERIFIER violation |

## The integrity verdict, precisely

`evidence/result.json`: `execution_integrity_passed: false`, `pipeline_exit_code: 0`,
`failed_backend_attempts: 0`, reasons `pipeline_not_completed` and `required_contract_failure`.

**pipeline_not_completed.** PROCESSOR partition 1 (spans s2d3, s35d, s3e6: the three complete
result entries) answered, identically on both attempts under greedy decoding, with three items of
`status: "empty"` and no `uncertainty` key (221 bytes, 65 tokens), refused as `Exact compact
extraction fields required`. The merged extraction is therefore `complete: false`,
`missing_partitions: [1]`, the run is marked semantically incomplete and `run_completion`
records `stopped`. Partition 0's four items carried all six keys. The checkpoint's own DEV
evaluation had four all-empty answers and every one carried the key, so the omission is
content-dependent, not a fixed habit; two greedy attempts with the same prompt cannot differ.

**required_contract_failure.** FACT_CHECKER (Phi-3.5 base, 237 tokens) emitted one typed-record
item carrying `record_verdict` and no `verdict`, although its rendered record example now shows
`claim_id`, `verdict` and `search_method` and the section says the record never replaces them.
The item is also wrong on its face (it compares a sodium reading of 148 mmol/L with the declared
result count of 6). In v5 FACT_CHECKER was valid; under the same greedy policy a different prompt
(no draft, the corrected record section) gave a different answer.

Auditor896 was admitted and invoked on 0 pairs: with partition 1 refused, no producer item was
accepted, so the advisory path remains unexercised on hardware.

## Every generation call

16 generation calls (10 on `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` at revision `bdd40416…` with
adapter checkpoint 168, 6 on `unsloth/Phi-3.5-mini-instruct-bnb-4bit` at revision `5c20803a…`
with no adapter), plus 30 embedding calls. Input tokens 77,144; output tokens 2,974. Every call
ended at EOS; cap hit 0; truncated 0; backend failures 0; contract valid 13 of 16.

| Task | Agent | Model | Contract | Normalised | Output / requested |
|---|---|---|---|---|---|
| 000000 | ARCHIVIST | 168 | valid | confident to confidence | 110 / 4096 |
| 000001 | INST_FINDER | 168 | valid (empty output) | | 23 / 2048 |
| 000002 | CITATION_RESOLVER | 168 | valid | | 130 / 2048 |
| 000003 | PROCESSOR partition 0 | 168 | valid | | 101 / 1536 |
| 000004 | PROCESSOR partition 1 | 168 | refused, `uncertainty` absent | | 65 / 1536 |
| 000005 | SPEECH_ACT_TAGGER | 168 | valid | | 924 / 2048 |
| 000006 | LEGAL_ANALYST | 168 | valid | confident to confidence | 117 / 2048 |
| 000007 | PROCESSOR partition 1, retry | 168 | refused, identical answer | | 65 / 1536 |
| 000008 | LEGAL_ANALYST | 168 | valid | confident to confidence | 109 / 2048 |
| 000009 | FACT_CHECKER | base | refused, `verdict` absent | | 237 / 2048 |
| 000010 to 000014 | PRACTICE_AUDITOR (5) | base | valid | | 169 to 217 / 768 |
| 000015 | EDITOR_CLERK | 168 | valid | confident to confidence | 109 / 8192 |

## Deliverables and resources

Three amendments, all `CONV-001`, computed in Python from the pairing map, the same three figures
as v5 (sodium, potassium, total bilirubin outside their reference ranges). Peak CUDA allocation
14.23 GB, reserved 15.06 GB, VRAM in use 15.37 GB of 23.68 GB, host RSS 3.82 GB, GPU utilisation
median 52 % and peak 100 %, power peak 155.9 W over 170 samples; no network attempt under
`deny_network`.

## Cost and teardown

52.8 billable minutes at $1.29/h: $1.135 infrastructure (the controller's upper bound at
termination; the analyzer reads $1.137), $0 model API, estimate not invoice; within the $5.00
soft budget and the $7.00 hard ceiling. Terminate requested 13:33:11 UTC; provider status
`terminated` 13:34:55; `instances_after: []`; the controller's independent client confirmed an
empty inventory, the temporary registration absent, local key material absent and no persistent
storage; `cleanup.json` all true; the watchdog exited. A fresh operator-side client
(`operator_post_cleanup_confirmation.json`) read an empty inventory and no key with the temporary
registration's id `53968bc9…` or name `shimmer-ordinary-final-a387a83`; the account's standing
key `shimmer-lambda` remains, as before.

## What remains, none implemented

The authorization excluded roadmap work; nothing in the runtime, prompts, validators, weights or
topology changed after launch. For a decision:

1. PROCESSOR's all-empty answer for a partition of complete entries omits `uncertainty`. The
   narrowest candidate is a declared tolerance in the compact validator, reading an absent
   `uncertainty` as `[]` only when `status` is `empty` and the other five keys are exact, recorded
   like the alias; the alternative is to leave the contract exact and accept that such partitions
   refuse. Two greedy attempts of one prompt cannot differ, so a retry never helps here.
2. FACT_CHECKER on the untuned Phi base displaces its contract's `verdict` with the record's
   `record_verdict`. The options are the ones already listed for VERIFIER: route the call to the
   producer lane, omit the record section for the untuned base, or map the record shape in the
   validator. Its answer was also wrong in substance, which none of those change.
3. The upload is 70 percent of billed time; a provider-side copy of the asset archive is the cost
   lever, to be proposed separately as instructed.

## Evidence

`docs/fix/ordinary_final_cloud_run_v6/`: launch and phase receipts, `workload_return.json`,
`workload_progress.log`, `cost.json`, `TERMINATION_VERIFIED.json`, `instances_after.json`,
`cleanup.json`, `independent_inventory_confirmation.json`,
`operator_post_cleanup_confirmation.json`, `collected_evidence.tar.gz` (sha256 `cf77656a…`),
`verified_evidence.json`, `FINAL_STATUS.json`, `downloaded/` (the evidence extracted:
`evidence/result.json`, `run_completion.json`, `contract_violations/`, the logs and
deliverables), `analysis/`. The 13.15 GB `assets.tar` and the 131 MB `project.tar.gz` stay on
disk, hashed in the tracked manifest, not committed.
