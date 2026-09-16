# V2 one-off diagnostic preflight

Status: **PREPARED ONLY — no cloud launch or experiment execution authorized.**

The frozen release remains `AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`. Source-family confounding remains unresolved. This package records a one-off diagnostic exception, not corpus admission or a benchmark release.

## Exact bindings

New package: `tuning/auditor_v2_diagnostic/`. `bindings.json` records SHA-256 identities for the frozen V2 configuration, safe merged TRAIN view, split/challenge definitions, canonical historical dataset/split, prior saved predictions and selected external DEV content. `records.json` contains only the authorized 2,040 prompt-token records, with explicit ID/label/split bindings outside model inputs.

| Purpose | Historical | External V2 | Total |
|---|---:|---:|---:|
| TRAIN | 192 | 1,600 | 1,792 |
| Co-primary DEV | 48 | 200 | 248 |

Each TRAIN class has 448 rows; external DEV has 50/class; historical DEV has 12/class. SHORTER and LONGER each contain 75 external DEV rows, 25 per declared class. Historical TRAIN rows are checked for exact equality with the canonical source.

Frozen backbone: `unsloth/Phi-3.5-mini-instruct-bnb-4bit`, revision `5c20803aa197416f43fb455e55c85178775320cb`; preserved Auditor checkpoint-120 adapter. Asset/adapter/base hashes are in the new experiment file. Final prompt-token representation is 3,072 dimensions. TRAIN-only mean/std uses ddof=0 and clamp=1e-6. Head: 4 outputs, 12,292 parameters, zero initialization, Adam lr=.01, regularization=.001, seed=7, exactly 200 updates. Existing V2 settings are unchanged. No candidate selection or repeats.

## Co-primary success rule

External DEV: four-way macro F1 >= .75 and every recall >= .60. Both SHORTER and LONGER: macro F1 >= .70 over their three supported classes. Historical canonical substantive DEV: four-way macro F1 >= .70 and every recall >= .60. All gates are required.

- All pass: `EXTERNAL_DATA_GENERALIZATION_SUPPORTED`.
- External including challenges passes; historical fails: `SOURCE_FAMILY_OR_DISTRIBUTION_OVERFIT`.
- Both primary relation gates fail: `RELATION_REPRESENTATION_STILL_INSUFFICIENT`, with exact scores/margins and no unsupported statistical-materiality claim.
- Other combinations: `INCONCLUSIVE_MIXED_GATES`; no success claim.

The previous frozen-representation head, recomputed from saved predictions on exactly 48 historical substantive rows, has four-way macro F1 **0.5991505914**, accuracy **0.6041666667**, and recalls MATCH **0.4167**, DIVERGENCE **0.5833**, OMISSION **0.4167**, ADDITION **1.0000**. The previous five-way macro is not the comparison. Full recomputation is in `baseline.json`.

## Cost and boundaries

[Lambda public pricing](https://lambda.ai/instances), checked September 17, 2026: one A10 24GB is **$1.29/GPU-hour**, before applicable taxes. Region capacity is not verified. Existing A10 throughput projects 431.2 seconds of feature extraction plus 2.8 seconds of head training; total planning allowance **15–30 minutes, $0.3225–$0.645** for compute. These are estimates, not a quote or an authorized spending ceiling. Setup/transfer time may vary. Launch-time capacity, spending ceiling, watchdog and termination checks remain required after separate execution approval.

Only prompt token IDs feed the classifier; source-family/provenance metadata is excluded. Textual source inferability remains possible. No explanation generation, refusal retraining, LoRA update, Producer, protected data, full pipeline or HOLDOUT evaluation is included.

The frozen JSONL interleaves all splits. Its opaque byte envelopes are scanned for ID routing, but only allowlisted DEV records are deserialized. HOLDOUT labels/text are not decoded, retained or exported; no HOLDOUT predictions/logits/metrics are accessed. `consumed=false` remains unchanged. This report deliberately distinguishes transport routing from evaluation access.

Local preparation performs no model inference or training and imports no Torch. Contract tests cover the co-primary decision rule, excluded-record decoding guard, duplicate/missing IDs, four-way baseline semantics, TRAIN-only normalization and artifact bindings. The future training primitive has not been GPU-tested or executed. The package has no cloud launcher; execution hardening is deferred until a separately authorized launch.
