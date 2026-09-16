# Producer checkpoint-120 evaluation runtime V2 results

**PRODUCER_CHECKPOINT120_INDETERMINATE**

**CHECKPOINT120_EVALUATION_NO_GO**

The one authorized experiment stopped during evaluation-context entry for the first reference cache preflight, before any `generate()` call. This is an invalidating runtime interruption, not a failed Producer semantic gate. No control outputs or fresh DEV outputs exist. The historical pilot remains `SECOND_TUNING_CANONICAL_PILOT_INDETERMINATE`; `FULL_GROUPED_CV_CONTINUATION_RECOMMENDED=false`.

## Cloud and identity

| Item | Verified result |
|---|---|
| Tested integration commit | `bee77af53576249fc889020ac44e969777433de7` |
| Runtime freeze SHA-256 | `4f0005934ed09593c2ca1dcefe3c6295924d9cbcac6e0e180b3fb05abdd17d49` |
| Provider / region / GPU | Lambda Cloud / us-east-1 / one NVIDIA A10 24 GB, x86-64 |
| Queried hourly price | $1.29 |
| Billable-duration upper bound | 729.84 seconds / 12.16 minutes |
| Cost upper bound | **$0.261526**; not an invoice claim |
| Terminated, provider verified | 2026-09-16 12:59:25 UTC |
| Subsequent inventory checks | Empty; zero experiment instances |
| Temporary SSH registration / local keys | Removed and verified |
| Adapter SHA-256 | `3f1e12d107f1206641902565b28ea6217d70ff2768c321a216227dbc21b702a6` |
| Adapter config SHA-256 | `cd672d24a74575fe9bec0e0589aa84a41f3078d5a23edaaee8ae1cafbc683507` |
| Base-weight SHA-256 | `99b85155b7bb40344d8c3938c8ec1147b27028804bca5d2e5559cb8e6533747d` |

Budget was frozen before launch: soft $2.50 / 116.28 minutes; hard $3 / 139.53 minutes; workload cutoff 129.53 minutes with ten minutes reserved. The conditional 110.33-minute / $2.3721 projection was below the ceiling. Independent termination watchdog armed before workload setup. The soft threshold was never reached.

Initial automatic approval review blocked process creation over destination/payload egress specificity. The operator subsequently explicitly approved Lambda Cloud us-east-1 and SSH upload of the reviewed Producer-only code, 60 canonical DEV rows and saved adapter. The same command was retried after price/capacity revalidation. That approval event created no instance; the later accepted execution launched exactly one. `PRELAUNCH_STATUS.json` and `PRELAUNCH_BLOCKED_INVENTORY.json` preserve that resolved historical event, not the final experiment status.

## Local and remote gates

Before provisioning, the 50 frozen-runtime local tests passed, the guarded tokenizer-only check matched all 60 prompt strings/token-ID sequences, and all 125 historical artifacts plus the runtime freeze verified. The packaged module imports, source hashes and fresh authorization passed. Three executed read attempts were denied for protected targets, Auditor data and the training executor. No historical permit was reused.

The remote bundle contained the exact frozen evaluation core, required frozen metric code, only the authorized 60 Producer DEV rows, the saved adapter and the new integration. No Auditor data/config/model, protected labels/evaluator, training executor or private corpus was uploaded. Historical observer source was included solely for exact callback AST extraction, not execution of its training function.

Remote preflight passed Python 3.12.3; Torch 2.5.1+cu121; Transformers 4.51.3; PEFT 0.15.2; the remaining pinned dependency lock; CUDA 12.1; one BF16-capable A10; RAM/disk; source and authorization bindings. Only the pinned Producer base was acquired. Base, tokenizer/config and adapter hashes verified before model execution; loading was offline with `trust_remote_code=False`.

The loader reproduced historical BF16/eager 4-bit base loading, k-bit preparation and LoRA wrapping. The adapter key set, shapes, dtypes and every loaded tensor value matched the saved safetensors file. Active adapter was `default`; adapter parameters were FP32 on `cuda:0`, matching the saved artifact and historical preparation rather than recasting them. BF16 base-load/compute constraints remained unchanged. No optimizer was created; optimizer construction and backward calls were denied. Model weights received no training update.

PEFT preparation source and source hashes were preserved remotely. Its inspected helper contains no `use_cache` mutation. This does not establish live cache behavior, which the failed preflight never reached.

## Invalidating runtime defect

Remote traceback:

```text
eval_runtime.py:89
saved = {identity: deepcopy(vars(obj)) for identity, obj in unique.items()}
TypeError: vars() argument must have __dict__ attribute
```

The frozen context iterates all modules and records owned `config` and `generation_config` attributes. It assumes each value supports `vars()`. Pinned Transformers `modeling_utils.py:1884` explicitly sets `generation_config=None` for modules that cannot generate. A local no-model reproduction adding that state to the existing module stand-in raises the identical TypeError, before entering eval/inference or calling generation. The exact offending remote object was not separately instrumented, so identifying a particular module instance is a source-supported inference; the failing line and exception are directly recorded.

The original 50 tests missed the nullable-generation-config state. Their success did not prove integration with the actual pinned model hierarchy. This run therefore invalidates readiness to execute this frozen runtime without a separately reviewed correction; the original frozen bytes and historical READY record remain unchanged as evidence.

No repair or redesign was attempted while billing. The controller immediately preserved the exception, empty raw cache file, PEFT state, telemetry, acquisition/preflight and source bindings, downloaded and hashed the archive, and terminated. Local diagnosis happened only after termination.

## Cache, controls and complete DEV

| Measurement | Result |
|---|---|
| Cache preflight | Interrupted before generation; no PASS |
| Prefill-cache creation | Not observed |
| Incremental one-token input/cache growth | Not observed |
| Reference / optimized speed controls | 0/6 / 0/6 |
| Reference / optimized aggregate tok/s | N/A / N/A |
| Speed ratio | N/A |
| Exact token identity 6/6 | Not measured |
| Exact semantic/stop identity 6/6 | Not measured |
| Admission | NO_GO due runtime interruption |
| Fresh full DEV | 0/60 |

No full-run generation wall, throughput, token distribution, EOS rate, prose/duplicate rate, contract validity, claim/gap/uncertainty/evidence F1, semantic completeness, accepted outcomes, refusal precision/recall, over-refusal, correct atoms/token or accepted-output token cost can be calculated. They are unavailable, not zero. No historical comparison was performed because complete new evidence does not exist. No checkpoint is selected and no historical rows are stitched into a new result.

## Evidence and independent local verification

Archive SHA-256: `66c33828ac1923c12d696c0ca8e16a5344afab430cd9ddfe39fee67de39a6073` (12,883 bytes). Download hash matched remote hash. All 13 archive files were scanned without credential findings before safe extraction. Subsequent local scans cover source/log/JSON evidence without publishing credentials.

The local analyzer independently verifies termination, empty inventories, SSH cleanup, archive/source/runtime/authorization bindings, base and adapter identities, zero raw generated rows, missing cache/control admission receipts and the exact local failure reproduction. Metric recomputation and control-equivalence verification are inapplicable because there are no generated outputs. It does not reinterpret absence as a gate score.

`AUDITOR_STATUS=UNTOUCHED`

`PROTECTED_RECEIPT_STATUS=UNCONSUMED`

All 125 historical artifact hashes and the runtime freeze remain unchanged. No protected targets were opened, no receipt consumed, and no Auditor acquired, loaded, trained, evaluated or redesigned.

## Next action

Diagnose/correct only the nullable configuration snapshot handling locally, with a test using the actual pinned non-generating model configuration structure plus normal/exception restoration coverage. Any corrected runtime needs a new prospective freeze and separate cloud authorization. Do not silently edit or retry this consumed release/one-instance authorization. No Producer retraining is justified by this infrastructure failure.

No training, optimizer, weight updates, Auditor execution, folds 1-4, protected access, paid inference API, second instance, full pipeline, multi-round or push occurred. Zero experiment billable resources remain.
