# One-off V2 classification diagnostic preparation

This separate package records the operator's one-off exception for quarantined TRAIN data. It does not admit V2, change its frozen release, or authorize cloud launch. The historical verdict remains `AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`.

Run local preparation with `python tools/auditor_v2_diagnostic.py`; run contract tests with `python -m unittest discover -s tools -p test_auditor_v2_diagnostic.py`. Preparation loads only the pinned tokenizer, never model weights. There is no cloud launcher or model execution command in this package. The future head-training primitive is uninvoked.

`records.json` is the minimal authorized representation input: 1,792 TRAIN, 200 external DEV, 48 historical substantive DEV, in that order. Only `input_ids` are model input. IDs, labels and evaluation split stay outside prompts. The original normalized Auditor prompt template and token ceiling are retained. The TRAIN rows are unchanged before prompt canonicalization.

The mixed frozen external JSONL has no separate DEV file. Preparation scans opaque byte envelopes for example IDs, decodes only the DEV allowlist, and never deserializes excluded records. This is transport-level access to a mixed file, not HOLDOUT label, prediction, logit or metric inspection. No HOLDOUT record is exported; the receipt stays unconsumed. The separate split file is used only for ID exclusion.

Both DEV sets are co-primary. External four-way macro F1 >= .75 and each recall >= .60; historical four-way macro F1 >= .70 and each recall >= .60. SHORTER and LONGER additionally require macro F1 >= .70, averaged over each challenge's three declared classes. Predicting the fourth class counts as an error. Both co-primary gates and both challenges must pass for success.

The prior probe baseline uses saved `raw_head_class` predictions on exactly the historical 48 IDs and the same four-way metric function. A refusal prediction would count as an error, not be dropped. No prior explanation or refusal-generation result is used as relation evidence.

`evaluate` accepts only the exact two DEV prediction sets. It reports the three requested diagnostic conclusions when the corresponding predicates apply. Other gate combinations return `INCONCLUSIVE_MIXED_GATES`, never success. For both-primary failure, exact scores must accompany the insufficiency label; threshold failure alone is not statistical evidence of materiality. No conclusion has been measured for this experiment.

Before future execution, obtain separate cloud approval bound to the reviewed payload and price/budget; verify region capacity and model/adapter hashes; enforce one exclusive run, 200 updates, frozen backbone/LoRA identity before and after, TRAIN-only normalization, runtime deadline and provider termination. This preparation is not a launch-ready cloud orchestrator. No existing historical launch permission is reused.
