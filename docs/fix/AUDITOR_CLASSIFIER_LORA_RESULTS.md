# Auditor classifier-specific LoRA results

**AUDITOR_CLASSIFIER_LORA_INDETERMINATE**

**RELATION_ADAPTATION_INDETERMINATE**

One predeclared classification-only experiment. Historical verdicts and adapters are immutable; V2 remains quarantined and NOT_READY. This is not integrated Auditor acceptance or deployment.

## Cloud

Tested commit: `550b9144ab53cb540a7ced460f0be77429caab81`. Lambda Cloud, us-east-1, one A10 24GB, x86-64, one GPU. Live rate $1.29/hour; $2 soft budget and $3 hard ceiling.

Launch-to-confirmed-termination upper bound: 561.063s (9.35 minutes). Estimated compute cost $0.201048; not a provider invoice or tax calculation. Terminated 2026-09-17T09:06:26.656986+00:00. Independent final inventory is empty, temporary SSH registration/key material removed. Zero billable resources.

The initial approval-review rejection was resolved by direct operator confirmation before the one launch. No prior diagnostic authorization was reused.

## Bound architecture and data

Pinned base `unsloth/Phi-3.5-mini-instruct-bnb-4bit` at `5c20803aa197416f43fb455e55c85178775320cb` → fresh rank-8 classifier LoRA → final normalized hidden state at the last prompt token → four-way FP32 linear head. The historical step120 adapter was excluded from the payload and never loaded, stacked or modified. No old feature cache and no population feature standardization. Head zero-initialized; fresh PEFT LoRA B matrices zero; seed 7.

LoRA alpha 16, dropout .05, no bias; q/k/v/o/gate/up/down targets. Frozen base; classification CE + .001*mean(W**2). AdamW: LoRA LR 1e-4, head LR .01, betas .9/.999, epsilon 1e-8, weight decay 0, combined clip norm 1. Constant LR; no scheduler, class weights or calibration.

Exact TRAIN 1,792 (192 historical + 1,600 external), 448/class; external DEV 200, historical substantive DEV 48; SHORTER and LONGER each 75. Only preflight-bound token IDs enter the model. No provenance, gold-label, split or ID metadata in prompts. The mixed external file and HOLDOUT data were not opened.

## Incomplete execution

**Numerical runtime failure during attempted update 4.** The finite-loss assertion rejected non-finite CE plus regularization before that microbatch's backward pass. Saved evidence does not isolate whether the originating problem was activations, logits, loss or parameter state. No root cause is asserted.

Only **3/896 optimizer updates** completed, covering **12 TRAIN presentations** in completed updates. Zero complete passes. The number of microbatches attempted within update 4 was not recorded. Neither checkpoint 448 nor 896 exists; no DEV/challenge inference or scoring occurred. No passing result or selected checkpoint is asserted. No retry or fallback was run.

Verified initial trainable inventory: base 0; classifier LoRA 14,942,208; head 12,292; total 14,954,500. Historical adapter loaded: NO. Optimizer groups exclude every base parameter.

First/last completed-update CE: 1.38629436/53.68067718; the second-update CE was 58.26807022. These are partial four-example losses, not a final training result. Completed-update wall 9.2022s; median/p95 3.1632/3.2789s. Peak allocated/reserved VRAM in completed updates: 3.559/3.902 GiB.

Telemetry: 20 samples; mean/max GPU utilization 51.25%/100%; peak process RSS 2.564 GiB.

Initialization LoRA/head artifacts and their hashes were verified locally, including zero LoRA B matrices and zero head. Only checkpoint 0 was saved. **Post-update adapter/head weights and the final base-state comparison are unavailable** because the run aborted before a planned checkpoint. The initial inventory proves the base was frozen and excluded from the optimizer; a final bytewise state equality check cannot be claimed. Historical on-disk adapter/evidence preservation checks passed.

## Checkpoints 448 and 896

| Checkpoint | External F1/recalls | SHORTER | LONGER | Historical F1/recalls | LoRA/head hashes | Gate |
|---|---|---|---|---|---|---|
| 448 | Not evaluated | Not evaluated | Not evaluated | Not evaluated | Not produced | Not assessable |
| 896 | Not evaluated | Not evaluated | Not evaluated | Not evaluated | Not produced | Not assessable |

## Selection and interpretation

Passing checkpoints: []. Selected checkpoint: none.

Required gates remain external macro F1 ≥ .75 and each recall ≥ .60, SHORTER/LONGER macro F1 ≥ .70, historical macro F1 ≥ .70 and each recall ≥ .60. Both DEV sets are co-primary. Checkpoint ranking uses historical F1, external F1, minimum recall across both DEV sets, earlier step, then hashes. A passing partial run cannot yield PASS. No statistical-significance claim is made.

The PAWS/WikiAtomic source-family confound remains unresolved; this experiment does not certify V2 as a clean benchmark or generally admitted corpus.

`V2_CORPUS_STATUS=AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`  
`HOLDOUT_STATUS=UNCONSUMED`  
`PRODUCER_STATUS=PRESERVED_UNEXECUTED`

Exactly one instance/GPU; no base update or historical adapter modification. Only the fresh classifier LoRA and head were eligible for training. No explanation/refusal generation, new data, HOLDOUT, Producer, protected data, paid inference API, full pipeline, governance run, folds 1–4, multi-round, second candidate, retry, fallback or push. Zero billable resources remain.

## Evidence

The archive SHA-256 was verified locally before termination. After cleanup, the available evidence was checked locally. For this interrupted run that comprises initial trainable inventory, optimizer groups, checkpoint-0 hashes/zero initialization, the three completed updates and their TRAIN identities, partial telemetry and budget timeline, historical preservation and cleanup. There are no checkpoint DEV logits or metrics to recompute and no valid adaptation conclusion. No local model training or inference was performed.

Run directory: `docs/fix/auditor_classifier_lora_run/`. Key files: `RECOMPUTED_RESULTS.json`, `execution_manifest.json`, `training_authorization.json`, `DIRECT_OPERATOR_CONFIRMATION.json`, `collection_integrity.json`, `TERMINATION_VERIFIED.json`, `final_inventory_confirmation.json`, `cleanup.json`, `preservation_after.json`, `EVIDENCE_MANIFEST.json`. Binary adapters, heads and arrays remain local; text evidence is committed after secret scanning.
