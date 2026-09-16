# External Auditor relation data V1 — quarantined preparation

`AUDITOR_EXTERNAL_RELATION_DATA_V1_NOT_READY`

This frozen artifact documents public-data acquisition and a deterministic
four-way contrast experiment. It is **not admitted for training or evaluation**.
The specified quartet construction has an unavoidable word-count-sign shortcut:
equal -> MATCH, shorter -> OMISSION, longer -> ADDITION scores 75% without
understanding content. Rebalancing whole quartets cannot change that result.
The conservative conversion also yields far fewer than the preferred 800 rows.

`examples.jsonl` and `substantive_relation_view.jsonl` contain identical external
rows, including frozen HOLDOUT labels for structural integrity checks only.
`merged_auditor_view.jsonl` preserves all 240 original historical TRAIN objects
unchanged and appends only external TRAIN. Historical DEV is never merged.
These files are quarantine/analysis artifacts, not an authorization to fit a head.
The only supported execution-facing accessor, `access.load_split`, fails closed.
Do not bypass it by directly reading these JSONL files for future experiments.

All outer metadata, provenance, transformation traces and labels are excluded
from classifier prompts. `tokenizer_check.py` uses the exact existing canonicalizer,
Auditor system prompt, chat template and pinned local tokenizer. External refs are
empty; no evidence references are invented. The classifier input ceiling is 1056;
future explanation generation needs its own combined sequence-budget validation.

From the repository root, with the original pinned tokenizer locally cached:

```powershell
python -B tuning/auditor_external_relation_v1/build.py
python -B tuning/auditor_external_relation_v1/test_release.py
python -B tuning/auditor_external_relation_v1/report.py
python -B tuning/auditor_external_relation_v1/verify.py
```

The builder is offline and refuses socket connections, subprocess execution,
credential/protected paths and model/feature weight file opens. It hash-checks
the ignored raw sources against `download_manifest.json`; it never redownloads
or silently accepts schema/count changes. `tools/download_auditor_external.py`
is the separate, explicitly networked public-data acquisition script. Reacquisition
changes timestamps and requires a separately reviewed manifest/freeze update.
Never rerun acquisition over a frozen release merely to rebuild derived rows.

Document identity uses non-placeholder upstream document IDs plus normalized
document hashes, cross-dataset exact matches, and lexical similarity components.
The upstream `N/A` doc IDs are placeholders, not a common document identity.
At most one base edit per document is retained, with the complete quartet in one
split. SummEdits is recorded only as a future pool; its factuality labels are not
Shimmer labels. No new LLM labeling or paraphrasing was used; upstream data itself
contains model-generated edits, retained as provenance.

The rendering library deliberately uses reversible single-item plain/bullet/numbered
wrappers, not inferred clause boundaries. That limits structural diversity but
preserves the original bytes. The sentence eligibility filter is conservative
and mechanical; it cannot prove semantic non-equivalence or all grammatical and
coreference properties. Lexical leakage checks do not prove semantic independence.

See `../../docs/fix/AUDITOR_EXTERNAL_RELATION_DATA_V1.md` and
`../../docs/fix/AUDITOR_EXTERNAL_DATA_ATTRIBUTION.md` for measurements and attribution.
External text retains CC-BY-4.0 attribution and modification notices. Repository
code licensing does not replace the upstream data license. Raw public JSON stays
ignored under `data/external/auditor_relations/raw/`.
