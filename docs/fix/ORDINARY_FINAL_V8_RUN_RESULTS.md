# Ordinary final run v8: recall 4 of 5 with reasons confirmed, no false positives, FACT_CHECKER ruled out

Status: **ORDINARY_FINAL_CLOUD_RUN_V8_WORKLOAD_COMPLETED_INTEGRITY_NOT_PASSED**. One authorized
instance ran for 54.0 minutes and was terminated; provider inventory is empty on three
independent readings; the temporary SSH registration and the local key are removed; the watchdog
exited. The sealed workload was invoked exactly once, every controller phase passed with zero
unreachable polls, and the pipeline reached its end in 446.7 s. This is the first run whose
QUALITY moved: recall 4 of 5 with every reason confirmed, zero false positives, zero distractor
hits, against a flat 3 of 5 with one false positive in v7 and 3 of 5 in v5 and v6. The runner
still returned exit 2, and both of its reasons trace to the single FACT_CHECKER call, whose
output is byte-identical to v7's. No second instance, no retry, nothing pushed. The
authorization bound to bundle v8 is consumed.

## Bound identity, reverified before launch

Source and preparation commit `a687b5637c7db7f7b7d841a57daab9037911b42a`, seal commit e0d5e0d,
manifest `8c5de3eaf7f1145d154c352f73ac9343716e63b5e697ae007cfab8f14c6af3d6`, seal
`5ba3c0b1cffebc581c9bd6a10581caf3613da5a693961402afa3e340790ee8c3`, project
`a6453ef8ebcf3519c5cc8ef018ebe93965fcb3faa53d9f772a659ec3ffeac4f8`, assets
`8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6` rebound from v7, not rebuilt
(122 members verified, three 40-byte refs), controller `7562dad3...`. The declared CONV-L02
heading was confirmed present inside the sealed project archive before launch. Local
reverification: 152 members compared to the sealed commit, `head_moved_by_evidence_only: []`,
`sealed_runtime_is_what_launches: true`, decoding policy admitted with the same digests the
instance admitted (`local_producer` restored `51da77c944`, `local_auditor` restored
`49199195d3`, `qwen_local` new `a51a93f054`). Live preflight: inventory empty, A10 in us-east-1
at $1.29, image `gpu-base-24-04` 24.4.4-2141. Rehearsed through the controller's own phases on
the local Ubuntu, both polarities, before launch. The launch receipt records exactly these
values.

## What happened, in the controller's order

Instance `6c6a17998fbd42ffa80449c0957c6048`, `gpu_1x_a10`, us-east-1, $1.29/h. Launched
17:09:31 UTC; active after about 4 minutes.

| Phase | Seconds | Exit | Polls (unreachable) |
|---|---|---|---|
| ssh_ready | 2.1 | 0 | |
| python_gate | 7.8 | 0 | 1 (0) |
| fresh_directory | 7.8 | 0 | 1 (0) |
| support_transfer | 42.4 | 0 | |
| assets_transfer (13.15 GB) | 2211.9 | 0 | |
| archive_integrity | 19.9 | 0 | 2 (0) |
| extract_payload | 19.8 | 0 | 2 (0) |
| create_environment | 7.8 | 0 | 1 (0) |
| install_pinned_wheels | 79.2 | 0 | 7 (0) |
| dependency_closure | 7.7 | 0 | 1 (0) |
| gpu_metadata | 7.8 | 0 | 1 (0) |
| watchdog_receipt_transfer | 3.0 | 0 | |
| ordinary_workload | 472.5 | 2 | 40 (0) |
| stop_workload, final_gpu_state, pack_evidence, evidence_hash | about 8 each | 0 | 1 (0) each |
| evidence_download (1,270,528 bytes, hash verified) | 7.1 | 0 | |

Pipeline run id `a66496726e454cfab8a6358ecfbce8be`, 17:53:33 to 18:01:00 UTC:

| Pipeline phase | Wall seconds | v7 |
|---|---|---|
| 3-4 content production | 232.4 | 236.8 |
| 5 verification and fact check (including 7 classifier calls) | 168.9 | 163.6 |
| 5.5 convention review, paired | 1.0 | 60.6 |
| 6 synthesis | 0.4 | 0.4 |
| 6.5 editorial board | 26.0 | 28.9 |

Phase 5.5 fell from 60.6 s to 1.0 s: with CONV-L02 scoped, the convention review is entirely
computed and makes no model call at all.

## The scored result, against the enriched answer key

| Measure | v5 | v6 | v7 | **v8** |
|---|---|---|---|---|
| Amendments | 3 | 3 | 5 | **4** |
| Recall, location only | 3/5 | 3/5 | 3/5 | **4/5** |
| Recall, reason confirmed | 3/5 | 3/5 | 3/5 | **4/5** |
| Right place, wrong reason | 0 | 0 | 0 | **0** |
| False positives | 0 | 0 | 1 | **0** |
| Distractor hits | 0 | 0 | 1 | **0** |
| Attribution | 3 of 3 | 3 of 3 | 3 of 3 | **4 of 4** |

| Planted | Rule | Found | Reason | Attributed | Matched via |
|---|---|---|---|---|---|
| RES-ALDER | CONV-L01 | yes | yes | yes | bus:above_band |
| RES-BIRCH | CONV-L01 | yes | yes | yes | bus:below_band |
| RES-ELDER | CONV-L01 | yes | yes | yes | bus:above_band |
| RES-FIRTH | CONV-L02 | **yes** | **yes** | **yes** | **bus:missing_field** |
| sheet | CONV-L03 | no | - | no | EVIDENCE_ABSENT_FROM_CORPUS |

The one remaining miss is the sheet-level count defect, deliberately out of scope for this pass:
the header block sits above the first heading and is in no unit, which the scorer reports
independently as `no unit of the parsed document contains 'sheet'`. Correcting it means changing
`split_units`, which changes every unit id in every corpus.

## The two corrections, as they behaved on hardware

**The CONV-L02 declaration (decision 1).** The pairing map now records one absence record:
`{unit_id: u06-result-res-firth, rule_id: CONV-002, field: sample identifier, path: computed}`.
The fourth amendment reads "The computed value is 0 values against a stated 1 required. the rule
declares sample identifier required and this unit does not carry it", attributed to CONV-002 and
the operator's own CONV-L02, `derived_from: computed_finding`, with no model call anywhere on
that rule. In v7 the same rule was rejected on that unit and five PRACTICE_AUDITOR calls were
spent on it for nothing. Both convention-review agents are now recorded as not called, 7 times
each, which is correct rather than a failure: a scoped rule is settled by Python.

**The promotion narrowing (item 2 of the prior pass).** Four amendments, all
`derived_from: computed_finding`, all from PRACTICE_AUDITOR's computed records. VERIFIER again
produced five typed records with `record_verdict: irregular`, and none became an amendment. In
v7 two of them did, one on a clean distractor. The deliverable's provenance is now honest and
the false positive is gone, which is exactly what the local proofs predicted.

## Every generation call

13 generation calls (18 in v7), all EOS, no cap hit, no truncation, zero backend failures,
12 of 13 contract-valid. 50 semantic call receipts, 11 Producer168, 7 Auditor896.
Input tokens 68,498 (103,935 in v7); output 4,059.

| Task | Agent | Contract | Normalised | Output / requested |
|---|---|---|---|---|
| 000000 | ARCHIVIST | valid | confident to confidence | 110 / 4096 |
| 000001 | INST_FINDER | valid (empty output) | | 23 / 2048 |
| 000002 | CITATION_RESOLVER | valid | | 130 / 2048 |
| 000003 to 000006 | PROCESSOR (4 partitions) | valid | | 52, 53, 54, 29 / 1536 |
| 000007 | SPEECH_ACT_TAGGER | valid | | 924 / 2048 |
| 000008 | LEGAL_ANALYST | valid | confident to confidence | 117 / 2048 |
| 000009 | LEGAL_ANALYST | valid | confident to confidence | 109 / 2048 |
| 000010 | VERIFIER | valid | | 1385 / 2048 |
| 000011 | FACT_CHECKER | **refused, `verdict` absent on 5 items** | | 975 / 2048 |
| 000012 | EDITOR_CLERK | valid | confident to confidence | 98 / 8192 |
| 7 classifier calls | AUDITOR896 | classified | | non-generative |

`extraction_merge complete: true`, 7 items, no missing partitions, for the second run running.

## FACT_CHECKER: the condition is met, the base is ruled out

The operator's condition was that if its items are again substantively wrong with a real draft,
the base is ruled out for this task on evidence. A real draft existed: the extraction merged
complete and VERIFIER consumed it successfully in the same phase.

FACT_CHECKER's output is **byte-identical to v7's** (2,362 raw bytes, the same five items, the
same five missing `verdict` fields). Scored for substance the same way v5 and v7 were:

| Item | Claim | Verdict |
|---|---|---|
| 1 | `sum_mismatch`, 6 against 6, on the sheet total | wrong: identical values with an irregular verdict; the real defect is 4 plus 3 equals 7, and the item names none of those figures |
| 2 | `missing_field` on sodium 148, a complete entry | wrong: the entry carries every field; sodium's real defect is out-of-range |
| 3 | `missing_field` on chloride 99, a clean distractor | wrong: no defect exists on RES-CEDAR |
| 4 | `product_mismatch` on total calcium 2.3, in range | wrong: a relation with no meaning here, on a clean distractor |
| 5 | `product_mismatch` on albumin 42, in range | wrong: RES-FIRTH's real defect is the missing identifier, which the item does not mention |

Five of five substantively wrong, in two independent runs, with and without a real draft. The
base has now never produced a substantively correct item on this corpus in three runs. **The
condition is satisfied: the base is ruled out for this task on evidence.** Per the operator's
instruction the next pass removes the agent from this corpus and records it in the tuning
backlog. Nothing was implemented in this run.

## The classifier's label distribution

Seven pairs, all `classified`, all `delivery: complete`, zero failures,
`pairs_from_partial_delivery: 0`. The distribution is again `OMISSION: 7`, with MATCH,
DIVERGENCE and ADDITION at zero.

The operator asked whether a complete non-empty extraction would now produce MATCH candidates.
It did not, and the evidence says why: the extraction is complete in the sense that all seven
partitions merged, but every one of the seven PROCESSOR items is `extraction_status: empty` with
no claims, no questions and no refs, which is the CORRECT extraction under the frozen policy for
entries carrying no claim ids and no explicit absence statements. So the classifier's input is
the same as v7's, an empty extraction against a content-bearing span, and OMISSION is the
correct label for all seven. This run therefore still provides no signal about the other three
classes. Producing that signal needs a corpus whose spans carry explicit claim ids, which is a
corpus question, not a classifier question.

VERIFIER's five findings are again unjoined (`unjoined_findings: 5`, `agreements: 0`,
`disagreements: 0`): the two layers answer different questions, so this is not a disagreement.

## Resources and cost

Peak CUDA allocation 11.37 GB, VRAM in use 15.37 GB of 23.68 GB, host RSS 7.03 GB, GPU
utilisation median 52 % and peak 100 % over 220 samples. `network.jsonl` is empty: no network
access from the workload.

54.0 minutes at $1.29/h: $1.158 infrastructure, $0 model API, estimate not invoice; within the
$5.00 soft budget and the $7.00 hard ceiling. The asset upload is 36.9 of those minutes, 68 % of
billed time. Termination confirmed at 18:03:23 UTC; `instances_after: []`; the controller's
independent client confirmed an empty inventory, the temporary registration absent, local key
material absent and no persistent storage; `cleanup.json` all true; the watchdog exited. A fresh
operator-side client confirmed an empty inventory and no key with the temporary registration's
id `ee728659...` or name `shimmer-ordinary-final-a687b56`; the account's standing key
`shimmer-lambda` remains.

## What remains

1. **FACT_CHECKER**, ruled out on this corpus by the operator's own condition. The next pass
   removes it from this corpus and records it in the tuning backlog.
2. **The sheet-level CONV-L03 defect**, requiring a `split_units` change that touches every unit
   id in every corpus. Its own piece of work.
3. **The classifier's discrimination**, still unmeasured for MATCH, DIVERGENCE and ADDITION, and
   not answerable on a corpus whose correct extraction is empty everywhere.
4. **The provider-side asset copy**, worth about 68 % of billed time, to be proposed separately.

## Evidence

`docs/fix/ordinary_final_cloud_run_v8/`: launch and phase receipts, `workload_return.json`,
`workload_progress.log`, `cost.json`, `TERMINATION_VERIFIED.json`, `instances_after.json`,
`cleanup.json`, `independent_inventory_confirmation.json`,
`operator_post_cleanup_confirmation.json`, `collected_evidence.tar.gz`, `verified_evidence.json`,
`FINAL_STATUS.json`, `downloaded/` and `analysis/`.
