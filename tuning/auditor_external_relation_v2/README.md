# Auditor external relation data V2

`AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`

This is a frozen local preparation/analysis release. Execution remains disabled.
It replaces synthetic quartets with PAWS-Wiki human paraphrase labels and the
published PEER sample of human WikiAtomicEdits. V1 remains byte-for-byte unchanged,
quarantined and unused in either V2 data view.

The word-sign baseline passes the requested <=0.55 DEV gate. However, the required
source-to-class mapping still couples PAWS to MATCH/DIVERGENCE and WikiAtomic to
OMISSION/ADDITION. Dataset identity plus sign reaches 75% in a provenance oracle.
Provenance is excluded from prompts, so this is **not evidence that a classifier
can infer dataset identity from text**. It is a remaining source-family confound;
this release conservatively does not claim the requested no-known-source-shortcut
condition is satisfied. No stricter word-sign gate has been substituted.

Raw official Google Storage links returned anonymous AccessDenied. PAWS files
come from the pinned Google Research Datasets HF repository. WikiAtomic rows come
from the authors' published PEER Zenodo v1.0 archive, verified against its published
MD5 and bound locally by SHA-256. The HF sample card supplies provenance only;
its `unknown` license is not used as permission. See `attribution.md` for the
distinct upstream and archive license notices and their limitations.

Only PAWS official TRAIN and PEER published TRAIN are source pools. PAWS official
DEV/TEST files are downloaded/hash-bound; only their Parquet footer counts/schema
are inspected. Their label columns are not read. PEER valid/test rows are excluded
from conversion. No QQP, noisy/swap-only PAWS, generated paraphrase, reversed
WikiAtomic operation, padding, or LLM row labeling is used.

`external_four_way_view.jsonl` contains frozen TRAIN/DEV/HOLDOUT examples.
`merged_four_way_train.jsonl` preserves the 192 historical substantive TRAIN
objects and appends external TRAIN. It contains no refusal rows and no V1 rows.
`access.load_split` rejects training/evaluation without separate authorization;
HOLDOUT always requires separate admission. Direct JSONL access is for preparation
and integrity verification only, not a supported execution bypass.

Group-first splits use exact/unordered pairs, sentence-side identity and >=0.50
token 5-gram Jaccard connected components across both source pools and historical
Auditor text. The threshold was tightened once after an initial >=0.80 audit
found cross-split similarity 0.555556. At most one row is selected per final group.
Groups are sentence lineages, not independently verified Wikipedia articles.

PAWS orientation is hash-determined and symmetric. Each split/sign is sampled in
common bins of abs(log(word ratio)) / 0.025 and shorter-side word length / 10.
One sampling unit has MATCH, DIVERGENCE and two atomic examples from distinct
groups in the same bin. This balances four classes while matching magnitude
distributions. Units are bookkeeping only: rows are unrelated human examples,
not synthetic quartet siblings. No source or class controls the opaque IDs.

From repository root, with the pinned tokenizer already cached:

```powershell
python -B tuning/auditor_external_relation_v2/build.py
python -B tuning/auditor_external_relation_v2/test_release.py
python -B tuning/auditor_external_relation_v2/report.py
python -B tuning/auditor_external_relation_v2/verify.py
```

The builder is offline and denies model/feature weights, networking, subprocesses,
credential/protected paths and V1 writes. All provenance/operation/source metadata
stays outside the exact future classifier input. The original Auditor reference
canonicalizer and pinned tokenizer are reused; external reference lists are empty.
No model is loaded and no training or evaluation is run.

`experiment.json` prepares `AUDITOR_EXTERNAL_RELATION_CLASSIFIER_V2`: frozen
step120 representation plus four-way linear head, classification only initially.
The historical refusal mechanism remains frozen and separate. Explanation and
classifier-specific LoRA execution are not authorized.
