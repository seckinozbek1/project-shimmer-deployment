# Ordinary final run v5: the sealed workload ran end to end on the A10; execution integrity did not pass

Status: **ORDINARY_FINAL_CLOUD_RUN_V5_WORKLOAD_COMPLETED_INTEGRITY_NOT_PASSED**. The one authorized
instance ran for 54.5 minutes and was terminated; provider inventory is empty on the controller's
reading, on its independent client and on a fresh operator-side client; the temporary SSH
registration and the local key are removed; the watchdog exited. **The sealed workload was invoked
exactly once and the pipeline reached its end** (exit 0, one document, three amendments). The
sealed runner then assessed execution integrity and returned exit 2 for two reasons it names in
`evidence/result.json`: `pipeline_not_completed` (the run is recorded as `stopped`, not
`completed`, because its PROCESSOR extraction merged with two partitions missing) and
`required_contract_failure` (four non-PROCESSOR model outputs failed their contracts). No backend
failed, no call hit its cap, no network was attempted, and no model was replaced. No second
instance, no retry, nothing pushed. The authorization bound to bundle v5 is consumed.

## What the run establishes

1. **The decoding-policy correction holds on hardware.** All 18 generation calls ran under
   `torch.use_deterministic_algorithms(True)` with the greedy policy restored from the protocol
   files (`do_sample=false`, `num_beams=1`, protocol eos and pad ids). Every call ended at its
   EOS token (151645 for the producer, 32007 for the auditor base); none hit its cap; none was
   truncated. The failure that consumed run 88323b86 (float32 CUDA `cumsum` inside the top-p
   warper at the first sampling step) did not recur. The `qwen_local` (REDACTOR) policy, recorded
   as new, was not used: zero observations.
2. **The controller's phase sequence ran unchanged on the real instance.** The strings rehearsed
   on WSL are the strings that ran: 18 phases, every exit 0 except the workload's own 2, zero
   unreachable polls across 64 polls, `fresh_directory` exit 0 on the absent root, the detached
   workload phase polled 36 times over 424.6 s, evidence hashed remotely and verified locally.
3. **The A10 fits the report_optimized clinical_reference topology with headroom.** Peak VRAM in
   use 16.50 GB of 23.68 GB; peak CUDA allocation 11.83 GB; host RSS peak 3.51 GB; swap 0.
4. **The pipeline reaches its end on the frozen models.** Deliverables, bus, telemetry, cost
   ledger, run completion, ontology capture and GNN update were all written and collected.

What it does not establish: execution integrity (not passed), output quality (unmeasured; no key
in the bundle; `quality_claim: null`), the advisory Auditor896 path (never invoked, see below).

## What happened, in the controller's order

Instance `b11eb2ac4d234c0eab04341f1e0bc30f`, `gpu_1x_a10`, us-east-1, $1.29/h, image
`gpu-base-24-04` 24.4.4-2141. Launched 10:01:19 UTC; active after 249.9 s.

| Phase | Seconds | Exit | Polls (unreachable) |
|---|---|---|---|
| ssh_ready | 2.0 | 0 | |
| python_gate (asserts 3.12.3) | 8.0 | 0 | 1 (0) |
| fresh_directory (`test ! -e <remote>`) | 7.9 | 0 | 1 (0) |
| support_transfer | 33.5 | 0 | |
| assets_transfer (13,149,972,480 bytes) | 2251.6 | 0 | |
| archive_integrity | 19.8 | 0 | 2 (0) |
| extract_payload | 19.7 | 0 | 2 (0) |
| create_environment | 7.8 | 0 | 1 (0) |
| install_pinned_wheels (92 wheels, hash-checked, offline) | 79.3 | 0 | 7 (0) |
| dependency_closure (`pip check`) | 7.8 | 0 | 1 (0) |
| gpu_metadata | 7.9 | 0 | 1 (0) |
| watchdog_receipt_transfer | 3.0 | 0 | |
| ordinary_workload | 424.6 | 2 | 36 (0) |
| stop_workload, final_gpu_state, pack_evidence, evidence_hash | 7.8 each | 0 | 1 (0) each |
| evidence_download (1,267,502 bytes, 64 members, hash verified) | 7.1 | 0 | |

The asset upload is 37.5 of the 54.5 billed minutes. Inside the workload, the sealed runner
passed every admission (manifest, exact tree, permit, watchdog receipt, single claim, Hub cache
refs, installed runtime, frozen adapters, pairing contract, decoding policy, `verify_runtime`,
hardware) and started the pipeline at 10:46:36 UTC:

| Pipeline phase | Wall seconds |
|---|---|
| 3-4 content production (10 producer calls) | 180.3 |
| 5 verification and fact check (2 auditor-base calls) | 91.9 |
| 5.5 convention review, paired (5 auditor-base calls) | 77.8 |
| 6 synthesis and deliverables | 0.3 |
| 6.5 editorial board (1 producer call) | 26.2 |
| 7, 8, 9 (9 skipped: non-sensitive mode) | under 0.1 |

Pipeline wall 392.2 s; process CPU 823.3 s; cold load of the producer 11.2 s; the producer was
evicted for the auditor base in phase 5 and reloaded for the editorial board.

## The integrity verdict, precisely

`evidence/result.json`: `execution_integrity_passed: false`, `pipeline_exit_code: 0`,
`failed_backend_attempts: 0`, reasons `pipeline_not_completed` and `required_contract_failure`.

**pipeline_not_completed.** `run_completion.json` records `reached_end: true`, `exit_code: 0`,
`state: stopped`, `semantic_complete: false`. The four PROCESSOR calls all failed the compact
extraction contract; the merged extraction reports `missing_partitions: [0, 1]`,
`complete: false`, and `semantic_waves.py` marks the run semantically incomplete, which
`run_completion.finish` turns from `completed` into `stopped`. The runner's `assess` requires
`completed`.

**required_contract_failure.** Four non-PROCESSOR calls have `contract_valid: false`
(ARCHIVIST, LEGAL_ANALYST task 9, VERIFIER, EDITOR_CLERK). PROCESSOR failures are excluded from
this reason by design (its partition-recovery contract) but drive the first reason.

## The eight contract violations

Raw outputs are under `downloaded/evidence/run/audit/contract_violations/`. None was truncated;
every one ended at EOS.

| Task | Agent (model) | Validator's missing fields | What the output did |
|---|---|---|---|
| 000000 | ARCHIVIST (Producer168) | `items[0].confidence` | wrote the key as `confident` |
| 000003 | PROCESSOR (Producer168) | Ungrounded extraction evidence | compact extraction items without grounding |
| 000004 | PROCESSOR (Producer168) | Exact compact extraction fields required | item shape short of the compact contract |
| 000007 | PROCESSOR, retry 1 (`malformed_contract`) | Exact compact extraction fields required | same |
| 000008 | PROCESSOR, retry 1 (`malformed_contract`) | Ungrounded extraction evidence | same |
| 000009 | LEGAL_ANALYST (Producer168) | `items[0].confidence` | wrote the key as `confident` |
| 000010 | VERIFIER (Phi-3.5 base) | `paragraph`, `finding`, `severity`, `reasoning` | a fenced ```json block holding a Finding-record-shaped item, followed by prose |
| 000017 | EDITOR_CLERK (Producer168) | `items[0].confidence` | wrote the key as `confident: true` |

The prompt names the field `confidence` and gives it in every example (`agent_wrapper.py`
instruction and examples); no prompt, contract or check in the repository uses `confident`. The
key came from the model. Three of the four producer calls that emit confidence-bearing items
wrote it; INST_FINDER, CITATION_RESOLVER, SPEECH_ACT_TAGGER and LEGAL_ANALYST task 6 were valid.
The producer and auditor protocol files record no contract-validity baseline, so this evidence
does not decide whether the key is a property of checkpoint 168 under greedy decoding, of the
prompt wording or of the 4-bit base.

The editorial board stopped at its first rank (EDITOR_CLERK, `contract_violation`, 0 rounds),
advisory; the deliverable shipped.

## Auditor pairing and the advisory Auditor896

`auditor_pair_unavailable`, reason `no_producer_items`: eligible producer items 0, pairs
constructed 0, classifier calls 0. The Auditor896 adapter passed the frozen-adapter admission
but was never invoked (`auditor896_receipts: 0`). The VERIFIER join carries one finding
(`VERIFIER:finding:REF-0022:0`), `not_comparable`, `verifier_ok: false`. The advisory path
therefore remains unexercised on hardware; this run says nothing about it.

## Every generation call

18 generation calls (11 on `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` at revision
`bdd404162d94997f390efbfa660eb3f21cbbc81d` with adapter checkpoint 168; 7 on
`unsloth/Phi-3.5-mini-instruct-bnb-4bit` at revision `5c20803aa197416f43fb455e55c85178775320cb`
with no adapter), plus 30 embedding calls. Input tokens 95,063; output tokens 4,142.

| Task | Agent | Checkpoint | Finish | Cap hit | Contract | Output / requested | Decode tok/s |
|---|---|---|---|---|---|---|---|
| 000000 | ARCHIVIST | 168 | eos | no | invalid | 110 / 4096 | 6.3 |
| 000001 | INST_FINDER | 168 | eos | no | valid (empty output) | 23 / 2048 | 3.5 |
| 000002 | CITATION_RESOLVER | 168 | eos | no | valid | 130 / 2048 | 6.8 |
| 000003 | PROCESSOR | 168 | eos | no | invalid | 251 / 1536 | 7.7 |
| 000004 | PROCESSOR | 168 | eos | no | invalid | 104 / 1536 | 7.0 |
| 000005 | SPEECH_ACT_TAGGER | 168 | eos | no | valid | 68 / 2048 | 6.2 |
| 000006 | LEGAL_ANALYST | 168 | eos | no | valid | 108 / 2048 | 6.4 |
| 000007 | PROCESSOR | 168 | eos | no | invalid | 102 / 1536 | 6.9 |
| 000008 | PROCESSOR | 168 | eos | no | invalid | 123 / 1536 | 7.1 |
| 000009 | LEGAL_ANALYST | 168 | eos | no | invalid | 109 / 2048 | 6.8 |
| 000010 | VERIFIER | base | eos | no | invalid | 389 / 2048 | 17.6 |
| 000011 | FACT_CHECKER | base | eos | no | valid | 1222 / 2048 | 18.3 |
| 000012 to 000016 | PRACTICE_AUDITOR (5) | base | eos | no | valid | 198 to 344 / 768 | 16.5 to 17.4 |
| 000017 | EDITOR_CLERK | 168 | eos | no | invalid | 107 / 8192 | 6.7 |

Every call's `decoding_kwargs` are exactly the admitted ones: producer
`{do_sample: false, num_beams: 1, eos_token_id: [151645], pad_token_id: 151654, use_cache: true}`
from `tuning/producer_v3/evaluation_protocol.json` (policy sha256 `51da77c9…`, status
`restored`); auditor base `{do_sample: false, num_beams: 1, eos_token_id: [32000, 32007],
pad_token_id: 32009, use_cache: true}` from
`tuning/auditor_canonical_execution/evaluation_protocol.json` (sha256 `49199195…`, `restored`).
transformers warned once per family that the checkpoint's `top_p` and `top_k` are ignored under
`do_sample=false`, which is the intended state.

## Deliverables produced

`deliverables/result_sheet/`: three amendments, all `CONV-001`, factual, action `flag`, located
at `REF-0007`, computed in Python from the pairing map (6 units, 5 rules, 11 pairs, 1 rejected,
18 undecided): sodium 148 against 135 to 145 mmol/L, potassium 3.1 against 3.5 to 5.0 mmol/L,
total bilirubin 24 against 1.7 to 17 umol/L. Paired review: 11 calls planned, 5 made
(PRACTICE_AUDITOR), 3 findings. Audit synthesis 0 findings, 0 deltas. Absence quote prediction
not exercised. Ontology capture: 3 provisions appended, graph 12 nodes and 2 edges, GNN update
loss 0.1177 (self-supervised reconstruction; not learned relevance). Quality against a key was not
measured.

## Resources

193 resource samples. CUDA allocated median 5.14 GB, peak 11.83 GB; CUDA reserved peak
16.17 GB; VRAM in use peak 16.50 GB of 23.68 GB (the wrapper's own progress sampler reported a
10,699 MB peak on its cadence); process RSS peak 3.51 GB; system RAM used peak 3.68 GB of
238.5 GB; swap 0; GPU utilisation median 61 %, peak 100 %; GPU power peak 158 W.
`evidence/network.jsonl` is empty: zero network attempts under `deny_network`.

## Bound identity, reverified before launch

Source commit `fbfc6f83df7a77a7f8ef458e455c07a25a441e6e`, bundle commit `a8583ef`, manifest
`06c78beb7831bc0075686205dde68c771cc1593fa4e509c43a148ea209b977b6`, seal
`fa867ee889e30a2db1777783b8e4999f941395de15448b318752c4ac1a26013b`, project
`b70cbded794a9ad97dbc50f84db996fec4f50706df43ae69c7d5389f2b28879d`, assets
`8f0cbd8155874fab9f2183c590b0d942973a4267b7dba35c04f01fce05a91df6` (rebound from v4, not
rebuilt, 122 members verified, three 40-byte refs), controller `7562dad3…`, wrapper
`e3da53b9…`. `AUTHORIZED_LOCAL_REVERIFICATION.json`: 151 members compared to the sealed commit,
`head_moved_by_evidence_only: []`, `sealed_runtime_is_what_launches: true`, decoding policy
admitted locally with the same digests the instance admitted. `authorized_live_preflight.json`:
inventory empty, A10 listed in us-east-1 at $1.29, image present, `launched: false`.

## Cost and teardown

54.5 minutes at $1.29/h: $1.172 infrastructure, $0 model API, estimate not invoice; within the
$5.00 soft budget and the $7.00 hard ceiling. Terminate requested 10:54:05 UTC; provider status
`terminated` 10:55:47; `TERMINATION_VERIFIED` 10:55:51; `instances_after: []`; the controller's
independent client confirmed an empty inventory, the temporary registration absent, local key
material absent and no persistent storage; `cleanup.json` all true; watchdog pid 8832 exited. A
fresh operator-side client at 11:00:33 UTC (`operator_post_cleanup_confirmation.json`) read an
empty inventory and no key with the temporary registration's id `8ed881f7…` or name
`shimmer-ordinary-final-fbfc6f8`; the account's one remaining key, `shimmer-lambda`, was not
created by this controller, which registers under the instance name and deletes that id.

## What was not measured or retained

- Output quality: no scorer, no key, `semantic_quality: unmeasured` on every call.
- The advisory Auditor896 classifier: never invoked (no eligible producer items).
- The REDACTOR (`qwen_local`) decoding policy: unused.
- A contract-validity baseline from the tuning protocols: none exists to compare against.

## Observations for the operator, none implemented

The authorization excluded roadmap work; nothing in the runtime, prompts, validators, weights or
topology changed. For a decision:

1. The `confident` key accounts for three of the four non-PROCESSOR contract failures and stops
   the editorial board at rank 1. Where that key comes from (checkpoint 168 under greedy decoding,
   the prompt wording, the 4-bit base) is not decided by this evidence.
2. The PROCESSOR compact-extraction contract rejected all four calls, two after one retry each,
   and that alone converts a reached-end exit-0 run into `stopped`.
3. VERIFIER on the untuned Phi-3.5 base fenced its JSON and used the Finding-record shape rather
   than the fields its validator asks for.
4. The upload of the 13.15 GB asset archive is 69 % of billed time; a run that reused a
   provider-side copy would spend under 20 minutes.

## Evidence

- `docs/fix/ordinary_final_cloud_run_v5/`: launch and phase receipts (`*_timing.json`,
  `*_status.json`, `*.log`), `workload_return.json`, `workload_progress.log`, `cost.json`,
  `TERMINATION_VERIFIED.json`, `instances_after.json`, `cleanup.json`,
  `independent_inventory_confirmation.json`, `operator_post_cleanup_confirmation.json`,
  `collected_evidence.tar.gz` (sha256 `7f2c756d…`), `verified_evidence.json`, `FINAL_STATUS.json`.
- `downloaded/`: the collected evidence extracted, including `evidence/result.json`,
  `evidence/run/audit/run_completion.json`, `model_telemetry_summary.json`,
  `contract_violations/`, `logs/model_telemetry.jsonl`, `logs/generation_observation.jsonl`,
  `logs/call_evidence.jsonl`, the deliverables, `hardware_admission.json`,
  `workload.stderr.log`.
- `analysis/`: the analyzer's `ordinary_final_summary.json`, `model_telemetry_summary.json`,
  `stages.json`, `cost_records.jsonl`.
- The 13.15 GB `assets.tar` and the 131 MB `project.tar.gz` stay on disk, hashed in the tracked
  manifest, not committed.
