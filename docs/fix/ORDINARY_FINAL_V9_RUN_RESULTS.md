# Ordinary final run v9: execution integrity PASSED, recall 4 of 5 with reasons confirmed

Status: **ORDINARY_FINAL_CLOUD_RUN_V9_INTEGRITY_PASSED**. One authorized instance ran for 53.7
minutes and was terminated; provider inventory is empty on three independent readings; the
temporary SSH registration and the local key are removed; the watchdog exited. The sealed
workload was invoked exactly once, every controller phase passed with zero unreachable polls,
and the workload returned **exit code 0**, the first clean return in this project's history.
`execution_integrity_passed: true` with an EMPTY reasons list, `run_completion.state: completed`,
and NO contract violations at all. Quality held: recall 4 of 5 with every reason confirmed, zero
false positives, zero distractor hits, attribution 4 of 4. No second instance, no retry, nothing
pushed. The authorization bound to bundle v9 is consumed.

## What this run was launched to measure

The withholding correction was proven locally by replaying v8's telemetry through the v8
runner's own `assess()`: removing FACT_CHECKER's rows left no reasons. That replay could not
establish the live outcome, because `semantic_incomplete` is set during execution by the
generation observer and `state: completed` is written by `RunCompletion.finish` at the end of a
real run. Whether this pipeline can produce a clean integrity verdict end to end had never been
observed in v5, v6, v7 or v8, all of which ended exit 2. It can, and now has.

## Bound identity, reverified before launch

Source and preparation commit `bd1fc2efafed2d76df60dfd9e6cc1424fc1f0081`, seal commit fa0234f,
manifest `dbdfe93993dc84da86633257f3cc0f746f59e734ac74a56aa487148dac67bbe6`, seal
`7b4ffda7a7a73a07cc1c0ebf33852dc2f9a7ae5d2b169621a61bb95779b5b953`, project
`fe8bbd391863e25873241a5d531d500b4e3410760f331c055415375829b34b13`, assets
`8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6` rebound from v8, not rebuilt
(122 members verified, three 40-byte refs), controller `7562dad3...`. The withheld-auditor
declaration was confirmed present inside the sealed project archive before launch. Local
reverification: 152 members compared to the sealed commit, `head_moved_by_evidence_only: []`,
`sealed_runtime_is_what_launches: true`, decoding policy admitted with unchanged digests
(`local_producer` restored `51da77c944`, `local_auditor` restored `49199195d3`, `qwen_local` new
`a51a93f054`). Live preflight: inventory empty, A10 in us-east-1 at $1.29, image
`gpu-base-24-04` 24.4.4-2141. Rehearsed through the controller's own phases on the local Ubuntu,
both polarities, before launch.

## What happened, in the controller's order

Instance `e40eb9499fe14cdca028d08f981b38eb`, `gpu_1x_a10`, us-east-1, $1.29/h. Launched
19:08:36 UTC; active after about 4 minutes.

| Phase | Seconds | Exit | Polls (unreachable) |
|---|---|---|---|
| ssh_ready | 2.0 | 0 | |
| python_gate | 7.9 | 0 | 1 (0) |
| fresh_directory | 7.9 | 0 | 1 (0) |
| support_transfer | 31.7 | 0 | |
| assets_transfer (13.15 GB) | 2269.3 | 0 | |
| archive_integrity | 20.4 | 0 | 2 (0) |
| extract_payload | 20.2 | 0 | 2 (0) |
| create_environment | 8.2 | 0 | 1 (0) |
| install_pinned_wheels | 81.0 | 0 | 7 (0) |
| dependency_closure | 8.5 | 0 | 1 (0) |
| gpu_metadata | 8.2 | 0 | 1 (0) |
| watchdog_receipt_transfer | 3.3 | 0 | |
| **ordinary_workload** | **408.3** | **0** | 34 (0) |
| stop_workload, final_gpu_state, pack_evidence, evidence_hash | about 8.5 each | 0 | 1 (0) each |
| evidence_download (1,266,142 bytes, hash verified) | 7.8 | 0 | |

Pipeline run id `1543757447c24ebeb65a31a517950065`, 19:53:37 to 19:59:57 UTC, wall 379.8 s:

| Pipeline phase | v9 | v8 |
|---|---|---|
| 3-4 content production | 230.8 | 232.4 |
| 5 verification and fact check | **105.5** | 168.9 |
| 5.5 convention review, paired | 1.0 | 1.0 |
| 6 synthesis | 0.3 | 0.4 |
| 6.5 editorial board | 26.8 | 26.0 |

Phase 5 fell by 63.4 s, which is the withheld FACT_CHECKER call.

## The integrity verdict

```
execution_integrity_passed : true
reasons                    : []
pipeline_exit_code         : 0
failed_backend_attempts    : 0
run_completion.state       : completed
run_completion.reached_end : true
contract_violations/       : (empty)
```

For contrast, v8 recorded `pipeline_not_completed` and `required_contract_failure`, and its
`run_completion.state` was `stopped` with `semantic_complete: false`. The mechanism is exactly as
the local proof predicted: the withheld call was the only `contract_valid: false` model call in
v8, and as a failed optimized-semantics call it set `semantic_incomplete`, which turned
`completed` into `stopped`. A call that is never made can do neither.

The withholding is recorded in the run's own activation ledger:

```
FACT_CHECKER | operator_withheld_for_corpus | phase 5
evidence: {"declared_in": "config/review_scope.json", "field": "withheld_audit_agents"}
```

## The scored result, against the enriched answer key

| Measure | v5 | v6 | v7 | v8 | **v9** |
|---|---|---|---|---|---|
| Run completeness | stopped | stopped | stopped | stopped | **COMPLETED** |
| Amendments | 3 | 3 | 5 | 4 | **4** |
| Recall, location only | 3/5 | 3/5 | 3/5 | 4/5 | **4/5** |
| Recall, reason confirmed | 3/5 | 3/5 | 3/5 | 4/5 | **4/5** |
| Right place, wrong reason | 0 | 0 | 0 | 0 | **0** |
| False positives | 0 | 0 | 1 | 0 | **0** |
| Distractor hits | 0 | 0 | 1 | 0 | **0** |
| Attribution | 3 of 3 | 3 of 3 | 3 of 3 | 4 of 4 | **4 of 4** |

All four amendments are `derived_from: computed_finding`: three CONV-L01 band findings on ALDER,
BIRCH and ELDER, and the CONV-L02 missing sample identifier on FIRTH. The one miss is the
sheet-level count defect, whose header block is in no unit
(`EVIDENCE_ABSENT_FROM_CORPUS`), deliberately out of scope for this pass.

## Every generation call

12 generation calls (13 in v8, 18 in v7), all EOS, no cap hit, no truncation, zero backend
failures, **12 of 12 contract-valid**. 49 semantic call receipts, 11 Producer168, 7 Auditor896.
Input tokens 58,339 (68,498 in v8); output 3,022.

| Task | Agent | Contract | Normalised | Output / requested |
|---|---|---|---|---|
| 000000 | ARCHIVIST | valid | confident to confidence | 110 / 4096 |
| 000001 | INST_FINDER | valid (empty output) | | 23 / 2048 |
| 000002 | CITATION_RESOLVER | valid | | 130 / 2048 |
| 000003 to 000006 | PROCESSOR (4 partitions) | valid | | 52, 53, 54, 29 / 1536 |
| 000007 | SPEECH_ACT_TAGGER | valid | | 969 / 2048 |
| 000008 | LEGAL_ANALYST | valid | confident to confidence | 117 / 2048 |
| 000009 | LEGAL_ANALYST | valid | confident to confidence | 109 / 2048 |
| 000010 | VERIFIER | valid | | 1267 / 2048 |
| 000011 | EDITOR_CLERK | valid | confident to confidence | 109 / 8192 |
| 7 classifier calls | AUDITOR896 | classified | | non-generative |

`extraction_merge complete: true`, 7 items, no missing partitions, for the third run running.

## The classifier

Seven pairs, all `classified`, all `delivery: complete`, zero failures,
`pairs_from_partial_delivery: 0`, label distribution `OMISSION: 7`. Unchanged from v7 and v8,
and for the same reason: every PROCESSOR item is correctly `extraction_status: empty` under the
frozen policy, so the classifier's input is an empty extraction against a content-bearing span.
Withholding FACT_CHECKER did not affect the pairing, which hangs off VERIFIER. MATCH, DIVERGENCE
and ADDITION remain unmeasured and are not answerable on this corpus.

## Resources and cost

Peak CUDA allocation 13.45 GB, VRAM in use 15.37 GB of 23.68 GB, host RSS 6.25 GB, GPU
utilisation median 51 % and peak 100 % over 187 samples. `network.jsonl` is empty: no network
access from the workload.

53.7 minutes at $1.29/h: $1.155 infrastructure, $0 model API, estimate not invoice; within the
$5.00 soft budget and the $7.00 hard ceiling. The asset upload is 37.8 of those minutes, about
70 % of billed time. Termination confirmed at 20:02:20 UTC; `instances_after: []`; the
controller's independent client confirmed an empty inventory, the temporary registration absent,
local key material absent and no persistent storage; `cleanup.json` all true; the watchdog
exited. A fresh operator-side client confirmed an empty inventory and no key with the temporary
registration's id `13e4e1fc...` or name `shimmer-ordinary-final-bd1fc2e`; the account's standing
key `shimmer-lambda` remains.

## What remains

1. **The sheet-level CONV-L03 defect**, the only remaining miss and the only path to 5 of 5. A
   contained fix was scoped this pass: a preamble unit whose id is not a heading ordinal
   renumbers nothing on any of the twelve corpus documents, and the clinical header carries the
   fields the rule needs. Recommended as the next pass.
2. **The classifier's discrimination**, needing a corpus whose spans carry explicit claim ids.
3. **FACT_CHECKER**, in `docs/fix/TUNING_BACKLOG.md`, withheld for this corpus and reversible in
   one line of the operator's own file.
4. **The provider-side asset copy**, worth about 70 % of billed time, to be proposed separately.

## Evidence

`docs/fix/ordinary_final_cloud_run_v9/`: launch and phase receipts, `workload_return.json`,
`workload_progress.log`, `cost.json`, `TERMINATION_VERIFIED.json`, `instances_after.json`,
`cleanup.json`, `independent_inventory_confirmation.json`,
`operator_post_cleanup_confirmation.json`, `collected_evidence.tar.gz`, `verified_evidence.json`,
`FINAL_STATUS.json`, `downloaded/` and `analysis/`.
