# Auditor external relation data V1

`AUDITOR_EXTERNAL_RELATION_DATA_V1_NOT_READY`

The acquisition, deterministic converter, grouped splits, tokenizer dry-run, merged view, and prospective classifier configuration are complete. The 208-row candidate is frozen as a **quarantine/analysis artifact**, not admitted training data. The specified quartet design exposes a 75% word-count-sign shortcut on both TRAIN and DEV, and only 52 independent documents survive the conservative rules. HOLDOUT remains unconsumed.

## Motivation and preserved evidence

The preceding frozen-representation linear probe fit TRAIN perfectly but obtained canonical DEV macro F1 0.679320 and accuracy 41/60. More diverse labeled data could test scarcity/coverage against a representation limitation. This task makes no model-quality claim and changes none of the canonical Auditor, linear-probe, or Producer results. All three prior evidence manifests were rechecked against their text files before and after preparation; model/feature binaries were not opened.

## Upstream acquisition

| Source | Rows | Normalized documents | Upstream doc IDs | License |
|---|---:|---:|---:|---|
| Salesforce/summexecedit | 4241 | 216 | 218 | CC-BY-4.0 |
| Salesforce/summedits | 6348 | 216 | not supplied | CC-BY-4.0 |

Both exact schemas and row counts match the request. SummExecEdit has 218 distinct raw doc_id values: 217 non-placeholder IDs plus `N/A`, which occurs on 2,120 rows. Placeholder IDs were excluded from identity unions. Exact normalized document content is authoritative for deduplicating ID aliases. Both datasets contain the same 216 normalized document texts; SummEdits is retained as a future pool, not counted as extra independent coverage.

Full revisions, download timestamps, sizes, raw/card SHA-256 identities and exact field/type schemas are in `source_manifest.json`. Only public dataset files, dataset documentation and license text were downloaded; no authentication was used. Raw JSON is ignored under `data/external/auditor_relations/raw/`.

Salesforce/summexecedit revision `d71ee27582afae29b1459b518229d9266ed4c8b2`; raw SHA-256 `f7ba6dece8322db94dbe86eb003a47a3e1fb90668e451be7414237e4d8313600`.

Salesforce/summedits revision `ce0c479aaf59259abb6b67e42248b2f49004b7d5`; raw SHA-256 `21e34593330020d02b7d92f4651fdcc550f7d79a2f899392f106fd816c215a89`.

See [attribution](AUDITOR_EXTERNAL_DATA_ATTRIBUTION.md) for source links, citations, licenses and modification notices.

## Mechanical conversion and rejection

Factual consistency against the original upstream document is not identity or a Shimmer relation between two summaries. No upstream label was mapped directly. A lineage must have a unique exact source span and a byte-exact executable replacement, with nonempty substantive text. Normalization-only changes and word-subsequence insertions/deletions disguised as replacements are rejected. Both spans must be complete sentence-like units with at least five lexical words; deleting the original span must leave a sentence-like remainder. Obvious leading dangling pronouns/connectives, unbalanced delimiters, reserved transport strings, and pre-existing replacement text are rejected.

Each quartet uses the same original summary. MATCH changes only a reversible wrapper; DIVERGENCE uses the exact verified edited summary; OMISSION removes exactly the designated span without global cleanup; ADDITION retains every source byte and inserts the exact replacement immediately after the original span, with a separating space. No sentence is paraphrased, reordered or summarized. Every emitted candidate is checked against its mechanically reconstructed expected value. Entire quartets are filtered together.

Mechanically eligible: 112 base edits from 52 documents. Selected: 52 quartets / 208 rows. Rejected or not selected: 4189 upstream rows. Reasons are exclusive first-failure categories:

| Reason | Rows |
|---|---:|
| missing_or_placeholder_span | 2120 |
| not_complete_sentence_replacement | 1667 |
| omission_dangling_referent_risk | 9 |
| omission_no_well_formed_remainder | 19 |
| one_lineage_per_document_cap | 60 |
| pure_insertion_deletion_or_nested_content | 307 |
| source_span_not_unique | 7 |

All 6,348 SummEdits rows are audited source-pool records, not rejected quartet attempts. No quotas are filled from its consistency labels. Of emitted rows, 25% are direct verified executable replacements and 75% are deterministic identity/deletion/insertion derivatives; all 100% retain the executable-edit lineage.

## Diversity and split

There are 52 distinct upstream documents, 52 normalized document hashes, 52 source-summary hashes and 9 domains. Each document contributes exactly four rows (one quartet). No document is counted as independent multiple times. There are six rendering pairs, each applied identically across sibling classes. These are conservative single-item plain/bullet/numbered wrappers, so structural coverage is modest.

| Class | Rows | Mean source words | Mean candidate words | Mean word ratio | Mean prompt tokens |
|---|---:|---:|---:|---:|---:|
| ADDITION | 52 | 44.90 | 61.69 | 1.390 | 626.27 |
| DIVERGENCE | 52 | 44.90 | 45.08 | 1.007 | 602.19 |
| MATCH | 52 | 44.90 | 44.90 | 1.000 | 601.87 |
| OMISSION | 52 | 44.90 | 28.29 | 0.617 | 578.02 |

Domain row counts: {"billsum": 12, "ectsum": 28, "news": 36, "podcast": 20, "qmsumm": 16, "sales_call": 20, "sales_email": 32, "samsum": 28, "shakespeare": 16}.

Rendering pair row counts: {"bullet -> numbered": 48, "bullet -> plain": 32, "numbered -> bullet": 52, "numbered -> plain": 24, "plain -> bullet": 16, "plain -> numbered": 36}.

Every class has exactly the same source, domain and renderer distribution. Detailed source/candidate character and tokenizer distributions, prompt distributions and ratios are in `statistics.json`.

| Split | Rows | Docs | Quartets |
|---|---:|---:|---:|
| TRAIN | 168 | 42 | 42 |
| DEV | 20 | 5 | 5 |
| HOLDOUT | 20 | 5 | 5 |

Document groups are formed before final example emission using non-placeholder upstream ID links, normalized full-document identity across datasets, exact source/candidate duplicates and token 5-gram Jaccard >=0.80 connected components. Hash-ordered group assignment gives approximately 80/10/10. All upstream rows have a frozen registry entry, including reserved split membership for corresponding SummEdits documents. Every selected sibling and document stays in one split. Selection is at most one base edit per document.

Cross-split exact normalized duplicates: 0. Maximum cross-split token 5-gram Jaccard: 0.016216216. Pairs at or above 0.80: 0. Sources, candidates and underlying documents are included. Maximum overlap against historical TRAIN/DEV source/candidate text: 0.000000000. No high-overlap pair required exclusion. These lexical checks do not establish semantic independence.

## Shortcut audit and readiness blocker

Opaque IDs are allocated as four independent slot hashes before a separately seeded per-lineage permutation assigns classes. Rows are globally sorted by a separate opaque hash. No label is encoded in an ID suffix or REF number. External reference lists are empty; the exact historical reference canonicalizer is reused. All outer metadata—including provenance, transformation trace, hashes, domain, IDs and relation—is excluded from prompts.

| Descriptive bucket purity (oracle, not fitted model) | TRAIN | DEV |
|---|---:|---:|
| id_mod4 | 0.315 | 0.500 |
| id_mod5 | 0.327 | 0.500 |
| id_mod20 | 0.417 | 0.650 |
| row_order_mod4 | 0.321 | 0.400 |
| refs | 0.250 | 0.250 |
| renderer | 0.250 | 0.250 |
| domain | 0.250 | 0.250 |
| source_length_20word_bin | 0.250 | 0.250 |
| candidate_length_20word_bin | 0.488 | 0.450 |
| prompt_length_50token_bin | 0.381 | 0.400 |
| word_ratio_sign | 0.750 | 0.750 |

Sparse ID bins have high in-sample purity by chance, particularly with only 20 DEV rows. This is not held-out accuracy and no classifier was fitted. No tested ID/modulo/order feature deterministically recovers all labels. Domain, renderer, refs and source-length buckets are exactly balanced. The raw merged historical records deliberately retain their original fields; those known historical ID/REF shortcuts must remain excluded/canonicalized at prompt construction.

The predeclared fixed length rule (equal -> MATCH; shorter -> OMISSION; longer -> ADDITION; never DIVERGENCE) scores 75.00% on TRAIN and 75.00% on DEV. HOLDOUT was excluded from baseline scoring. This is an analytical construction-level defect: in every complete quartet the rule gets MATCH, OMISSION and ADDITION correct, regardless of DIVERGENCE. Reweighting/reselecting complete quartets or changing harmless wrappers cannot reduce that 3/4 floor after wrapper removal. Artificial whitespace or token padding would merely conceal it. No such padding, extra same-document lineages, label remapping, or looser span rules were used to force readiness.

Reconstruction within the mandated quartet constraints therefore cannot eliminate the observed shortcut. This freeze records the failed admission candidate; it is not a ready corpus freeze. A future task needs a changed deterministic construction or an explicitly narrower contrast-task objective before the dataset can test the semantic-diversity hypothesis. Even apart from the shortcut, 208 rows and five DEV documents are useful for converter diagnostics but inadequate evidence for the requested substantial diversity expansion.

## Tokenizer dry-run

Pinned local tokenizer: `unsloth/Phi-3.5-mini-instruct-bnb-4bit` revision `5c20803aa197416f43fb455e55c85178775320cb`. Tokenizer/config assets were hash-checked; no weights were opened. Prompts use the frozen Auditor instruction, V2 clarification, canonical input normalization and native chat template. No truncation.

| Prompt set | Count | Min | Median | Mean | p95 | p99 | Max |
|---|---:|---:|---:|---:|---:|---:|---:|
| All prospective eligible quartet members | 448 | 513 | 584.0 | 591.34 | 672 | 705 | 759 |
| Frozen external candidate | 208 | 514 | 598.5 | 602.09 | 681 | 709 | 759 |
| Historical substantive TRAIN + DEV | 240 | 671 | 768.0 | 774.72 | 866 | 889 | 896 |

Supported classifier input ceiling: 1056. Prospective overflows: 0; released-candidate overflows: 0. No quartet was dropped for length. Combined explanation-output budgeting remains a separate future integration check.

## Views and next experiment

The merged view contains 240 unchanged historical TRAIN objects plus 168 external TRAIN rows, for 408 rows. Substantive TRAIN is 192 historical + 168 external = 360; all 48 historical INSUFFICIENT_EVIDENCE rows are preserved unchanged. No historical DEV row is merged.

`AUDITOR_EXTERNAL_RELATION_CLASSIFIER_V1` is prepared but disabled: frozen refusal veto -> four-way substantive linear classifier -> conditioned explanation. The prospective head uses the same frozen Auditor/checkpoint-120 representation, final prompt-token vector of dimension 3072, TRAIN-only standardization, four outputs, 12,292 trainable head parameters, seed 7, 200 Adam updates at 0.01 with the prior 0.001 weight regularization. This configuration is a proposal, not execution tooling or authorization.

Primary DEV would contain 20 external rows; historical 48-row substantive canonical DEV remains a secondary distribution-shift diagnostic. HOLDOUT is excluded. Classifier gates remain macro substantive F1 >=0.75 and every class recall >=0.60; aspirational targets are 0.80/0.70. All frozen integrated Auditor gates and zero catastrophic errors are retained verbatim in `experiment.json`; no integrated evaluation was run. No classifier LoRA fallback is implemented, and success of a larger-data linear head is not assumed.

## Runtime and cost projection only

For this rejected candidate, feature extraction projects to 113.20 seconds: TRAIN 93.92s, external DEV 4.67s, historical DEV 14.61s. This scales the measured 227,276 prompt tokens / 86.1036 seconds by the actual planned prompt-token total, not row count alone. After feature caching, head inference is budgeted at 0.01-1 second for each DEV set (unmeasured).

The 200-update head calculation projects 0.55s from the historical 0.462s, scaled by TRAIN rows and four rather than five outputs; reserve 1-5s because tiny GPU operations have fixed overhead. Expected peak allocation is roughly 3.56-4.5 GiB; reserve 6 GiB. Warm classification-only compute is about 1.93 minutes. With provisioning, environment preparation and transfers, plan 10-20 A10 minutes / $0.215-$0.43 using the prior $1.29/hour rate. These are projections, not current price verification, a hard bound, or cloud authorization. Veto/explanation generation is excluded; the prior 48 explanations alone took 279.56s and would dominate integrated evaluation.

## Validation and boundaries

Validation covers source hashes/counts/exact schemas/license cards, executable edit reproduction, complete balanced quartets, reverse rendering, provenance round-trip, document cap, sibling containment, cross-dataset identity, lexical duplicates, token ceiling, unchanged historical rows, and separate HOLDOUT denial. Invalid fixtures cover empty/repeated spans, hidden edits, normalization-only changes, disguised insertion, partial clauses, empty deletion, dangling pronouns, and tampered candidates. Additional tests cover lexical grouping, renderer reversibility, prompt metadata exclusion, REF renaming, overflow detection, and runtime denial hooks. Both original-order and reversed-order reconstruction produce identical row/rejection identities; whole-artifact rebuild hashes are recorded separately.

The strict sentence-like filter is a mechanical approximation: it cannot prove every grammatical/coreference condition or detect every semantically equivalent replacement. Single-item wrappers offer limited structural variety; scitldr supplies no admitted quartet. These limitations further prevent treating this small diagnostic corpus as a successful test of the data-scarcity hypothesis.

HOLDOUT has frozen labels and structural/token/lexical integrity checks only. No prediction, classifier baseline, model inference, or evaluation was performed on it. The receipt remains `consumed=false`; the accessor denies all execution while data admission is false. All existing historical text evidence passed preservation checks.

Confirmed: public dataset/documentation/license downloads only; no new LLM labeling, per-row agent generation, cloud compute, model generation/inference, model weights, training, Producer execution, protected access, folds1-4 execution, paid API, full pipeline, multi-round run, or push.

`AUDITOR_EXTERNAL_RELATION_DATA_V1_NOT_READY`
