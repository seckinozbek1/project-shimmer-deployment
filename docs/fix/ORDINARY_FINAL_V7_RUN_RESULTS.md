# Ordinary final run v7: extraction complete, Auditor896 executed, one contract failure left

Status: **ORDINARY_FINAL_CLOUD_RUN_V7_WORKLOAD_COMPLETED_INTEGRITY_NOT_PASSED**. One authorized
instance ran for 55.4 minutes and was terminated; provider inventory is empty on three
independent readings; the temporary SSH registration and the local key are removed; the watchdog
exited. The sealed workload was invoked exactly once, every controller phase passed with zero
unreachable polls, and the pipeline reached its end (exit 0, one document, five amendments) in
508 s. Two of the three items proved out on hardware: the PROCESSOR extraction merged COMPLETE
for the first time (7 of 7 spans, no missing partitions) and Auditor896 EXECUTED for the first
time, on 7 of 7 pairs, all classified. The sealed runner still returned exit 2, and both of its
reasons now trace to a single call: FACT_CHECKER emitted five items carrying `record_verdict`
and no `verdict`. No second instance, no retry, nothing pushed. The authorization bound to
bundle v7 is consumed.

## Bound identity, reverified before launch

Source and preparation commit `205bbb3c3976f621b2f1dba33346dc5fce9cbe59`, seal commit 4291ccf,
manifest `93a645acad549518f20eaca3330c06ac0e3da9b9aa594c0a8b3975bbc06def70`, seal
`a3965cdb219545069f2a9c128cf4523187d2f217457a537e6732cdbe5978d298`, project
`72d10f7bb881cc3fddda85f1d43b44edf187495da947c737d3b77076210fc60f`, assets
`8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6` rebound from v6, not rebuilt
(122 members verified, three 40-byte refs), controller `7562dad3…`. Local reverification: 152
members compared to the sealed commit, `head_moved_by_evidence_only: []`,
`sealed_runtime_is_what_launches: true`, decoding policy admitted with the same digests the
instance admitted. Live preflight: inventory empty, A10 in us-east-1 at $1.29, image
`gpu-base-24-04` 24.4.4-2141. The v7 archive was rehearsed through the controller's own phases
on the local Ubuntu before launch (324.7 s, both polarities). The launch receipt records exactly
these values.

## What happened, in the controller's order

Instance `6da925f74435496a8a97f59831bb0d76`, `gpu_1x_a10`, us-east-1, $1.29/h. Launched
14:39:49 UTC; active after about 3 minutes.

| Phase | Seconds | Exit | Polls (unreachable) |
|---|---|---|---|
| ssh_ready | 1.9 | 0 | |
| python_gate | 7.8 | 0 | 1 (0) |
| fresh_directory | 7.9 | 0 | 1 (0) |
| support_transfer | 33.4 | 0 | |
| assets_transfer (13,149,972,480 bytes) | 2261.2 | 0 | |
| archive_integrity | 19.8 | 0 | 2 (0) |
| extract_payload | 19.7 | 0 | 2 (0) |
| create_environment | 7.9 | 0 | 1 (0) |
| install_pinned_wheels | 79.3 | 0 | 7 (0) |
| dependency_closure | 7.8 | 0 | 1 (0) |
| gpu_metadata | 7.8 | 0 | 1 (0) |
| watchdog_receipt_transfer | 3.0 | 0 | |
| ordinary_workload | 531.9 | 2 | 45 (0) |
| stop_workload, final_gpu_state, pack_evidence, evidence_hash | about 8 each | 0 | 1 (0) each |
| evidence_download (1,281,434 bytes, hash verified) | 7.2 | 0 | |

Pipeline run id `6f89626310b843798e46ece6d758f358`, 15:24:21 to 15:32:49 UTC:

| Pipeline phase | Wall seconds |
|---|---|
| 3-4 content production | 236.8 |
| 5 verification and fact check (including 7 classifier calls) | 163.6 |
| 5.5 convention review, paired | 60.6 |
| 6 synthesis | 0.4 |
| 6.5 editorial board | 28.9 |

## The three items, as they behaved on hardware

| Item | Evidence from the run |
|---|---|
| A6, the validated two-span layout | all four PROCESSOR requests contract-valid (52, 53, 54 and 29 output tokens); `extraction_merge complete: true`, 7 items, `missing_partitions: []`. In v6 the one three-span request failed twice and the merge was incomplete. |
| A5, the item-scoped pairing gate | Auditor896 ran on 7 of 7 pairs, all `classified`, all `ownership: compact_partition`, all `delivery: complete`, zero failures, 10.9 s of classifier service; `pairs_from_partial_delivery: 0`. First execution of the advisory classifier on hardware. |
| A7, the record example from declared values | did not hold: FACT_CHECKER emitted five items, each with `record_verdict` and no `verdict`. |
| A3 (v5), the `confident` alias | fired on ARCHIVIST, both LEGAL_ANALYST calls and EDITOR_CLERK; all four contract-valid and recorded. |
| A4 (v5), VERIFIER with a draft | called, contract-valid, five findings (1,253 output tokens), joined to the run. |

The partial-delivery path was therefore never exercised: the delivery was complete, so the
marking is proven only by the executed local checks, not by this run.

## The integrity verdict, precisely

`evidence/result.json`: `execution_integrity_passed: false`, `pipeline_exit_code: 0`,
`failed_backend_attempts: 0`, reasons `pipeline_not_completed` and `required_contract_failure`.
Both trace to task-000011, the FACT_CHECKER call: its five items are missing `verdict`
(`missing_fields: items[0..4].verdict`), which makes it the required contract failure and, as a
failed optimized-semantics call, marks the run semantically incomplete, so `run_completion`
records `stopped` despite `reached_end: true` and exit 0.

The items themselves are better formed than v6's: they carry `claim_id`, `search_method`,
`relation`, `value_a`/`unit_a`, `source_refs`, quotes from the source and, in one case, a
`sum_mismatch` on the declared total. What they omit is the one enumerated field the contract
requires. In v6 the same base dropped the same field from a single item; here it dropped it from
five, so the correction to the example did not change the behaviour. The model is filling the
typed record's fields and treating `record_verdict` as the verdict slot, which is precisely what
the record section tells it not to do.

## Every generation call

25 model calls: 11 on `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` with adapter checkpoint 168, 7 on
`unsloth/Phi-3.5-mini-instruct-bnb-4bit` with no adapter, 7 on the same base with the Auditor896
classifier fork. Input tokens 103,935; output 4,873. Every generation call ended at EOS; cap hit
0; truncated 0; backend failures 0; 24 of 25 contract-valid.

| Task | Agent | Model | Contract | Normalised | Output / requested |
|---|---|---|---|---|---|
| 000000 | ARCHIVIST | 168 | valid | confident to confidence | 110 / 4096 |
| 000001 | INST_FINDER | 168 | valid (empty output) | | 23 / 2048 |
| 000002 | CITATION_RESOLVER | 168 | valid | | 130 / 2048 |
| 000003 to 000006 | PROCESSOR (4 partitions) | 168 | valid | | 52, 53, 54, 29 / 1536 |
| 000007 | SPEECH_ACT_TAGGER | 168 | valid | | 924 / 2048 |
| 000008 | LEGAL_ANALYST | 168 | valid | confident to confidence | 117 / 2048 |
| 000009 | LEGAL_ANALYST | 168 | valid | confident to confidence | 109 / 2048 |
| 000010 | VERIFIER | base | valid | | 1253 / 2048 |
| 000011 | FACT_CHECKER | base | refused, `verdict` absent on 5 items | | 975 / 2048 |
| 000012 to 000016 | PRACTICE_AUDITOR (5) | base | valid | | 147 to 215 / 768 |
| 000017 | EDITOR_CLERK | 168 | valid | confident to confidence | 115 / 8192 |
| 7 classifier calls | AUDITOR896 | 896 fork | classified | | non-generative |

## Deliverables and resources

Five amendments (three in v5 and v6), all rendered from the pairing map. VERIFIER contributed
five findings, all `MATCH`, none joined to a pair (`unjoined_findings: 5`, `agreements: 0`,
`disagreements: 0`): the classifier returned `OMISSION` on all seven pairs while VERIFIER
reported `MATCH`, and the join is `not_comparable` because the findings carry no pair id. That
asymmetry is the first real signal from the advisory layer and is for the operator to read, not
for me to act on. Peak CUDA allocation 13.49 GB, VRAM in use 15.37 GB of 23.68 GB, host RSS
6.80 GB, GPU utilisation median 52 % and peak 100 % over 250 samples; `network.jsonl` empty.

## Cost and teardown

55.4 minutes at $1.29/h: $1.191 infrastructure, $0 model API, estimate not invoice; within the
$5.00 soft budget and the $7.00 hard ceiling. The asset upload is 37.7 of those minutes.
Termination confirmed at 15:35:12 UTC; `instances_after: []`; the controller's independent
client confirmed an empty inventory, the temporary registration absent, local key material
absent and no persistent storage; `cleanup.json` all true; the watchdog exited. A fresh
operator-side client (`operator_post_cleanup_confirmation.json`) read an empty inventory and no
key with the temporary registration's id `d2827f35…` or name `shimmer-ordinary-final-205bbb3`;
the account's standing key `shimmer-lambda` remains.

## What remains, none implemented

1. **FACT_CHECKER's `verdict`.** Two prompt corrections have now failed to move it, and the v7
   evidence is stronger than v6's: five items, all well formed, all missing the one enumerated
   field. The remaining options are the ones already on the table, and the evidence now argues
   that the prompt is not where this is fixed: withhold the record section from the untuned
   auditor base for this agent, or route the call to the producer lane, or accept the failure
   and stop counting it as a required contract failure. Each changes routing or contract scope,
   so each is yours to decide.
2. **The advisory disagreement.** Seven `OMISSION` classifications against five `MATCH`
   findings, with no join between them. Worth reading before any further tuning of either side.
3. **The provider-side asset copy**, which would cut about 68 % of billed time. I will propose
   it separately as instructed.

## Evidence

`docs/fix/ordinary_final_cloud_run_v7/`: launch and phase receipts, `workload_return.json`,
`workload_progress.log`, `cost.json`, `TERMINATION_VERIFIED.json`, `instances_after.json`,
`cleanup.json`, `independent_inventory_confirmation.json`,
`operator_post_cleanup_confirmation.json`, `collected_evidence.tar.gz`, `verified_evidence.json`,
`FINAL_STATUS.json` (with `auditor896_pairs: 7`, `auditor896_pairs_from_partial_delivery: 0`),
`downloaded/` and `analysis/`. The asset and project archives stay on disk, hashed in the tracked
manifest.
