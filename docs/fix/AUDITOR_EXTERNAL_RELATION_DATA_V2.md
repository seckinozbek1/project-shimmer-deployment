# Auditor external relation data V2

`AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`

V2 preparation is complete. The word-sign hard gate passes and the requested balanced data views, challenge subsets, grouping, tokenizer evidence and classification-only experiment are prepared. Admission remains disabled under a conservative reading of the requested no-known-source-shortcut condition: source identity still separates the two class families, and source identity plus sign reaches 75% in a provenance oracle. This is not a demonstrated prompt-level exploit: dataset identity is excluded from prompts, and its inferability from text was not established. No stronger word-sign threshold is substituted and no model performance is claimed.

## Source acquisition and policy

Original Google Storage URLs returned 403 AccessDenied for PAWS and both WikiAtomic English files. PAWS Labeled Final was obtained from the pinned Google Research Datasets HF repository. WikiAtomic uses the authors’ published PEER Zenodo sample, verified against its published archive checksum and hash-bound locally. No arbitrary scraped mirror, PAWS-QQP, noisy PAWS or swap-only data was used.

| Source | Downloaded rows | Conversion pool | Retained |
|---|---:|---:|---:|
| PAWS-Wiki Labeled Final | 49,401 TRAIN + 8,000 DEV + 8,000 TEST | 49,401 official TRAIN | 1000 |
| WikiAtomicEdits, published PEER sample | 104,000 (52,000 per operation) | 83,200 published TRAIN | 1000 |

PAWS DEV/TEST were only hashed and inspected through Parquet footer row counts/schema; their label columns were not read. They do not source any V2 split. PEER valid/test IDs were excluded from conversion. New TRAIN/DEV/HOLDOUT are created from grouped upstream TRAIN pools. Thus neither original test set is turned into new training data.

PAWS fields are id:int32, sentence1:string, sentence2:string, label:int64 (human 0/1 judgment). The published WikiAtomic sample has id plus src, tgt, changed, src_tag, yin_before and yin_after arrays. Alignment tags provide the operation; full exact reconstruction is required. The source manifest records actual schemas, counts, revisions, raw hashes and licenses. See [attribution](../../tuning/auditor_external_relation_v2/attribution.md) for citations and the distinct Google/CC-BY/CC-BY-SA notices. Raw downloads remain ignored.

paws-train.parquet: `8dc9ad3e5f30ad9a86b290fe236d528ef23a5751fec9a35d99cbacf68ba277cf`.

paws-dev.parquet: `7760d829453764ba342a6f562809a8ed21c2c3eec3fd9ffa544089f145d42f6d`.

paws-test.parquet: `ae342ff12bb84b84b95f468abf5db6cb7c7bd578271299fe9c99be75b8132f4d`.

PEER.zip: `2b628bee49ee2dfd7eb0e7103219799528060a79b6c641d09b0c11ebf25eb536`.

## Conversion and length controls

PAWS label 1 maps only to MATCH and label 0 only to DIVERGENCE. Orientation can be reversed because both upstream relations are symmetric; reversal is recorded. Equal-word-count PAWS pairs are excluded. Both sources require nonempty, sentence-like text of 8-60 lexical words, plausible sentence boundaries, balanced delimiters and no malformed markup/placeholders. This mechanical screening supplements PAWS Labeled Final human fluency judgments; it is not an LLM grammaticality review.

WikiAtomic requires exactly one contiguous insertion or deletion run, equal tokens unchanged, EMPTY markers only on the appropriate aligned side, and exact reconstruction of src/tgt and changed tokens. Pure punctuation/function-word-only edits are excluded. No atomic sentence is padded or relabeled, and no extra synthetic examples are created.

Groups are assigned before final sampling. Within each split and sign, common bins match abs(log(candidate/source word ratio)) in 0.025 steps and shorter-side word count in 10-word steps. Each selection unit draws one MATCH, one DIVERGENCE and two atomic examples from four distinct groups in the same bin. This yields equal overall class counts and matched magnitude-bin distributions. Units do not share semantic content or synthetic lineage.

| Pool | Eligible before duplicate grouping | Rejection reasons |
|---|---:|---|
| paws | 25544 | {"equal_lexical_length": 20567, "identical_pair": 52, "lexical_length_outside_8_60": 370, "sentence_boundary_shape": 2776, "unbalanced_delimiters": 92} |
| wikiatomic | 40074 | {"lexical_length_outside_8_60": 2191, "non_substantive_edit_span": 4846, "noncontiguous_edit": 61, "placeholder_markup_or_reserved_text": 35654, "sentence_boundary_shape": 374} |

Pair duplicate/conflict audit: {"conflicting_pairs_excluded": 14, "conflicting_rows_excluded": 28, "duplicate_or_reversed_extra_rows": 62, "remaining_pairs": 65542}.

## Final candidate corpus

| Class | Rows | Shorter / equal / longer | Mean source words | Mean candidate words | Ratio min / median / p95 / max |
|---|---:|---|---:|---:|---|
| MATCH | 500 | 250 / 0 / 250 | 18.50 | 18.43 | 0.769 / 1.002 / 1.200 / 1.333 |
| DIVERGENCE | 500 | 250 / 0 / 250 | 18.26 | 18.18 | 0.765 / 1.003 / 1.200 / 1.333 |
| OMISSION | 500 | 500 / 0 / 0 | 19.85 | 17.57 | 0.760 / 0.887 / 0.958 / 0.973 |
| ADDITION | 500 | 0 / 0 / 500 | 18.16 | 20.35 | 1.034 / 1.118 / 1.222 / 1.333 |

Total: 2000; unique normalized pair/lineage groups: 2000. Both sources are Wikipedia-derived. Identical plain transport rendering is used for all classes. Detailed source/candidate words, word/character ratios and token statistics are in `statistics.json`. These are sentence lineages; unavailable article IDs prevent a claim of article-level independence.

| Split | Rows | Per class | Unique lineages |
|---|---:|---|---:|
| TRAIN | 1600 | {"ADDITION": 400, "DIVERGENCE": 400, "MATCH": 400, "OMISSION": 400} | 1600 |
| DEV | 200 | {"ADDITION": 50, "DIVERGENCE": 50, "MATCH": 50, "OMISSION": 50} | 200 |
| HOLDOUT | 200 | {"ADDITION": 50, "DIVERGENCE": 50, "MATCH": 50, "OMISSION": 50} | 200 |

## Leakage

Unordered normalized pairs bind reversed duplicates. Exact sentence-side matches and exact 5-gram Jaccard connections are unioned across both eligible source pools and historical Auditor TRAIN/DEV text before splitting. Any group touching historical text is excluded; at most one example per remaining group is selected. The original 0.80 threshold was tightened once to 0.50 after the first integrity audit found a cross-split similarity of 0.555556. This adjustment used lexical integrity, not model predictions or HOLDOUT performance.

Pool grouping: {"algorithm": "Global-frequency ordered prefix-filter candidates followed by exact 5-gram Jaccard; union sentence pairs, exact sides and >=0.50 near sides before split assignment. Tightened once after an initial 0.80 audit found cross-split similarity 0.555556.", "exact_similarity_comparisons": 58230, "groups": 46471, "historical_overlap_rows_excluded": 0, "near_edges": 34979, "paws_to_wikiatomic_exact_sentence_overlaps": 1, "paws_to_wikiatomic_shared_components": 1, "threshold": 0.5, "unique_sentence_sides": 106594}.

Final cross-split audit: {"cross_split_exact_sentence_pairs": 0, "cross_split_near_pairs": 0, "limitation": "Sentence lineage independence only; no Wikipedia article IDs supplied; lexical checks do not prove semantic independence.", "max_cross_split_5gram_jaccard": 0.15384615384615385, "unique_groups": 2000, "unique_pairs": 2000}.

No exact, reversed-pair or near-sentence lineage crosses the final splits. Lexical checks do not prove semantic independence. The complete eligible pool group registry is frozen so unselected siblings cannot later be silently assigned across splits.

## Shortcut baselines

| Fixed rule | TRAIN accuracy | DEV accuracy |
|---|---:|---:|
| fixed_word_sign | 0.5000 | 0.5000 |
| fixed_ratio_threshold | 0.4813 | 0.4800 |
| fixed_source_dataset | 0.5000 | 0.5000 |
| fixed_source_and_sign_oracle | 0.7500 | 0.7500 |
| fixed_id_mod4 | 0.2575 | 0.2800 |
| fixed_row_mod4 | 0.2419 | 0.2850 |

The fixed sign rule predicts OMISSION for shorter, ADDITION for longer, MATCH for equal. It passes the <=0.55 DEV requirement; no sign rebalancing retry was needed. The fixed ratio rule uses <0.95 -> OMISSION, >1.05 -> ADDITION, otherwise MATCH. ID/order rules use four-way modulo with a predeclared class order. No classifier or embedding model was trained.

| Descriptive oracle bucket purity | TRAIN | DEV |
|---|---:|---:|
| source_words_10bin | 0.2881 | 0.2850 |
| candidate_words_10bin | 0.2900 | 0.3050 |
| word_ratio_005bin | 0.5000 | 0.5050 |
| character_ratio_005bin | 0.5450 | 0.5500 |
| punctuation_counts | 0.3231 | 0.3250 |
| source_dataset | 0.5000 | 0.5000 |
| id_mod4 | 0.2781 | 0.3100 |
| id_mod5 | 0.2644 | 0.3550 |
| id_mod20 | 0.3088 | 0.4350 |
| row_mod4 | 0.2719 | 0.3050 |
| row_mod5 | 0.2719 | 0.3100 |

Bucket purity is an in-sample oracle description, not fitted or held-out predictive accuracy. Dataset alone gives 50%; dataset plus sign gives 75% because the atomic classes become identifiable while PAWS remains two-way. Dataset name, operation, source file, upstream IDs, provenance and class labels never enter classifier prompts. The oracle is therefore a source-family confounding diagnostic, not proof of input leakage. We leave admission false rather than certify the no-known-source-shortcut requirement. Changing the mandated class/source mapping or explicitly accepting this controlled confound would require a subsequent scoped decision; no extra labels were invented here.

Opaque IDs hash normalized unoriented content identity with a fixed salt; they do not use class, source dataset, operation or row index. Row order uses a separate content hash. No tested ID/order bucket deterministically identifies all classes. References are empty, and the exact historical canonicalizer is reused.

## DEV challenges

- LONGER: 75 rows, 25 per class across MATCH, DIVERGENCE, ADDITION; required macro F1 >=0.70.
- SHORTER: 75 rows, 25 per class across MATCH, DIVERGENCE, OMISSION; required macro F1 >=0.70.

Sign is constant within each challenge. This removes sign as a within-subset predictor, but does not eliminate all possible source/style confounds. HOLDOUT was excluded from baseline scoring and challenge construction.

## Tokenizer and views

Pinned Auditor tokenizer only: `unsloth/Phi-3.5-mini-instruct-bnb-4bit`, revision `5c20803aa197416f43fb455e55c85178775320cb`. The exact frozen prompt, V2 clarification, chat template and reference canonicalizer were used. Asset hashes are verified without weight access.

Prompt tokens: {"ceiling": 1056, "overflow": 0, "statistics": {"count": 2000, "max": 631, "mean": 529.015, "median": 528.0, "min": 489, "p95": 564, "p99": 581}, "truncation": false}.

Merged four-way TRAIN: 192 unchanged historical substantive rows + 1600 external TRAIN = 1792. No historical refusal, DEV or V1 row is included. The original historical refusal mechanism remains separate. All V1 release bytes and historical evidence remain unchanged; V1 admission stays false.

## Next experiment and projection

`AUDITOR_EXTERNAL_RELATION_CLASSIFIER_V2` is prepared but not executed or admitted: frozen historical refusal veto -> same frozen checkpoint-120 representation and four-way linear classifier -> conditioned explanation. The first measurement is classification only; no explanation or veto generation is included. Use final prompt-token hidden states (3072 dimensions), TRAIN-only standardization, 12,292 head parameters, 200 Adam updates, seed 7, lr 0.01 and prior 0.001 weight regularization. No classifier-specific LoRA is authorized.

Primary external DEV: 200 rows. Historical substantive canonical DEV: 48 rows, secondary distribution-shift diagnostic. External gates remain macro F1 >=0.75, every class recall >=0.60; each challenge requires macro F1 >=0.70. Aspirational overall gates are 0.80/0.70. HOLDOUT is excluded and requires separate authorization. Historical integrated gates remain recorded.

Projection only: feature extraction 431.22s total (TRAIN 376.65s; external DEV 39.96s; historical DEV 14.61s). Head training approximately 2.76s, scaling historical measurements. Expected peak GPU allocation 3.56-4.5 GiB. Setup-inclusive planning range: 15-30 A10 minutes / $0.3225-$0.645 using the historical $1.29/hour rate. This is not a current price quote, a hard bound, or cloud authorization. Explanation generation is excluded.

## Validation and verdict

Checks cover source/archive hashes, official split footer counts/schema, atomic reconstruction, label/orientation preservation, provenance round-trip, symmetric duplicates, exact/near lineage containment, common ratio bins, four-class/sign balance, challenge construction, tokenizer ceiling, metadata exclusion, unchanged historical rows and V1 quarantine. Unit tests compare the prefix index against exhaustive lexical similarity and prove rejection of invalid alignment, placeholders, identity pairs, tampering, unauthorized data access and prohibited runtime operations. Reversed input ordering and independent-process artifact rebuild evidence are retained.

HOLDOUT receipt remains consumed=false. No HOLDOUT prediction/evaluation was run. Public data/documentation/license downloads only; no new LLM labels, model inference/generation, model weights, training, cloud compute, paid API, Producer execution, protected access, or push.

`AUDITOR_EXTERNAL_RELATION_DATA_V2_NOT_READY`
