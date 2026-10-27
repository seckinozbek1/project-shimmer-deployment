# Preregistration: external benchmarks

Draft, loop stage S4. Completed and frozen at the end of S5; its SHA-256 recorded in docs/loop/VERSIONS.md before S8.

The benchmarks, their sources and licences are in `docs/benchmarks/SELECTION.md`. Bundles follow `docs/INPUT_FORMAT.md` (version `input-format-v1-draft`); run output follows `docs/OUTPUT_FORMAT.md` (current draft). Terms used below:

- **Document**: what one Shimmer run reviews (a contract, a filing, a table with its caption, a ContraDoc text).
- **Item**: one scored decision, carrying one benchmark label.
- **Item rule**: the convention the adapter writes for an item, by one item-independent template. Each item has exactly one rule id, recorded in the bundle's item table.
- **FLAG, CLEAR, UNDECIDED**: per benchmark, the label an irregular finding maps to, the label for no finding, and what a refusal maps to (item 5).
- **ABSTAIN**: no label. Never correct; counted as wrong in every accuracy-type metric and reported as coverage (answered items over all items).

## 1. Benchmarks, splits, split rules and holdout sampling

| Benchmark | Development | Holdout pool | Document id |
|---|---|---|---|
| ContraDoc | hash rule | the rest | `unique id` |
| CUAD v1 | hash rule (no official development split) | the rest | not documented outside the data; the unit is the contract, identified by the SHA-256 of its text |
| SciTab | hash rule (no official split) | the rest | `table_id` |
| FinDVer | official split `testmini` | `test`, minus any item whose `report` also appears in `testmini` | `report` |

**Hash rule.** The key is the document id as a string. Where the id is "identified by the SHA-256 of its text", the key is the lowercase hexadecimal SHA-256 of the UTF-8 bytes of that text exactly as distributed, with no normalisation. Compute SHA-256 of the UTF-8 bytes of the key and read the digest as an unsigned big-endian integer. If it is 0 modulo 5, every item of that document is development; otherwise every item is in the holdout pool. The hash is taken over the document, never the item, so all of one document's decisions fall on the same side.

**Filters applied before the split.** SciTab: the 25 demonstration claims (5 tables) named by the paper are excluded from both sets if B-dev's documented source identifies them; otherwise they fall under the hash rule like any table.

**Holdout sampling** (S8, role B). The unit sampled is the document; every item of a sampled document is scored. Sampling is seeded and stratified by label:

- Length band, by whitespace-separated words of the document under review: A under 1,000; B 1,000 to 4,999; C 5,000 to 19,999; D 20,000 or more. S5 measures cost per document in these same bands.
- Label stratum: the share of the document's items whose gold label is FLAG: none; above none up to one half; above one half. For one-item documents this is the label itself.
- Strata are length band crossed with label stratum.
- B shuffles each stratum with the seed (documents first sorted by document id), then builds one order of the whole pool: at each position it takes the next document from the stratum furthest below its proportional share of the positions filled so far, ties going to the earlier band, then the lower label stratum.
- B records this full seeded order, so that any prefix of it is itself a stratified random sample (S8c).
- The seed is chosen by role B at sampling time and recorded in B's folder, not here.

## 2. Sample sizes and the benchmark priority list

**Sample sizes: pending S5. Priority list: pending S5.**

Fit grades from `SELECTION.md`, the first key of the priority list: FinDVer Medium-high; CUAD, ContraDoc, SciTab Medium. (SummEdits is rejected as exposed, D-019.) The second key, measured cost per scored decision, is pending S5.

The rule, written now and applied at the end of S5:

> First set aside the forecast cost of B's synthetic tests, every arm. Then, in priority order, give each benchmark the smallest number of documents that yields at least 30 documents and at least 100 scored decisions, with B3 and B1 run on every item, at S5's measured cost per document by benchmark and document-length band, with the 1.3 forecast margin (IV.3). When the next benchmark's minimum would pass the S8 allocation, that benchmark gets what is left and is reported as a pilot, and the benchmarks below it get nothing. If allocation is left after every benchmark has its minimum, raise every benchmark by the same fraction until the allocation is used. A benchmark result is reported as a pilot unless it has at least 30 documents and at least 100 scored decisions. The priority list orders benchmarks by fit and then by measured cost per scored decision, cheapest first. It is fixed before B draws any sample.

Documents for each benchmark are taken as a prefix of B's seeded order (item 1).

**The S8c cut rule** (applied before any holdout run, by rule only, if the forecast of the whole design from S5's measured cost per document, by benchmark and length band, with the 1.3 margin, passes the S8 allocation):

1. drop B4;
2. drop whole benchmarks from the bottom of this priority list (fixed before B draws any sample);
3. if the design still does not fit, shorten every remaining benchmark to the same fraction, by taking the first n documents of B's seeded order (item 1), so that the shortened set is itself a stratified random sample.

The resulting n per benchmark is written down before the runner starts, and every cut is reported.

## 3. Primary measures

For every benchmark and every arm:

1. **The official metric**, or the closest honest measure with the reason:
   - ContraDoc: judgement accuracy (headline), with precision, recall and F1 for "contradictory". Evidence Hit Rate needs BERTScore; it is replaced by exact containment of the marked evidence sentence (whitespace-normalised) and labelled as not the official measure.
   - CUAD: AUPR and precision at 80 and 90 percent recall need a ranked score, which Shimmer's findings do not carry, and span Jaccard needs extracted spans. They are not reported. Closest honest measure: macro-F1 over present and absent (headline), with precision and recall for "present" at Shimmer's single operating point.
   - SciTab: macro-F1 over supports, refutes, not enough info.
   - FinDVer: accuracy over all items, ABSTAIN counted wrong (headline); coverage and accuracy on answered items beside it.
   - Never claim comparability with published numbers that use a different metric or split.
2. **Location recall**: the share of FLAG items for which the arm emits the FLAG label and, where the benchmark marks evidence, cites a unit that contains it (ContraDoc evidence sentence; FinDVer context indices, through the adapter's record of which unit holds each source paragraph). Where the benchmark marks no evidence, where FLAG is an absence (CUAD), or where the bundle holds one unit only, location is not measurable: the value reported is recall on FLAG, labelled so.
3. **Reason-confirmed recall**: location catches whose explanation a reviewer marks correct. Every B3 location catch is reviewed; above 200 per benchmark, a seeded random sample of 200, reported as an estimate with its interval.
4. **False positives in every deliverable**: irregular findings on CLEAR items, plus irregular findings tied to no item, counted in each deliverable file (`review_data.json`, `review_findings.md`, `tracked_changes.docx`, `document_summary.md`) and in total.
5. **Refusals**: items mapped from a refusal, and documents with a run failure.
6. **Which layer produced each catch**: Python (computed, `model=python`, `absence_path: computed`) or a model (judged).

## 4. Arms, comparisons and statistics

**Arms** (S4d), applied to every benchmark and every synthetic test of B:

- **B0, trivial baseline**: "no finding" on every item, mapped by item 5 (every item gets CLEAR).
- **B1, bare model**: the main reading agent's model and decoding policy, read at run time from the configuration the pipeline uses; the fixed prompt of item 5, one call per item; no pipeline.
- **B2, Python only**: Shimmer's computing layer with no model call, run by `benchmark/baselines/python_only.py` on the laptop.
- **B3, full Shimmer**: the current default configuration. Same bundles, same cut text.
- **B4, optional**: B3 with one alternative open-weight model family, only if budget remains after the core; LAW-III cross-family checking must hold.

These arm names are not the role sessions B1 and B2, nor the commits C1 to C5.

**Comparisons**, per benchmark, on the headline metric of item 3:

- Primary: B3 against B1.
- Secondary, Holm-adjusted within each benchmark at family-wise 0.05: B3 against B2, then B3 against B0.
- Primary comparisons are not adjusted across benchmarks; each answers its own question, and the number of benchmarks is stated beside them.

**Statistics.**

- Decisions inside one document are not independent (a CUAD contract carries 41). Confidence intervals come from a paired cluster bootstrap that resamples documents, not decisions: draw as many documents as were scored, with replacement; recompute both arms' metric on all items of the drawn documents (a document drawn twice counts twice); take the difference. 95 percent percentile interval, 10,000 resamples. The seed is drawn at scoring time and recorded with the results.
- p-values for Holm: twice the smaller of the shares of resampled differences at or below zero and at or above zero, capped at 1.
- McNemar's exact test is used only where each document gives one decision (ContraDoc), on correct versus not correct, ABSTAIN counted not correct.
- Every result states the number of documents beside the number of decisions.
- Smallest detectable difference: 2.80 times the bootstrap standard error of the paired difference (two-sided 5 percent, 80 percent power), reported per benchmark. A planned value from S5's development variance: pending S5.

## 5. Mapping text and the B1 prompt

### 5.1 Output to label, all benchmarks

A record belongs to an item when its `source_rule_id` equals the item's rule id. A refusal for an item is an UNCERTAIN record, or a refusal entry in the pairing map or run output, naming that rule. For each item apply the first matching line:

1. **Run failure** (no deliverable for the document, the run stopped, or it refused at start): every item of the document is ABSTAIN.
2. At least one record with `record_verdict` irregular (any relation: `sum_mismatch`, `product_mismatch`, `above_band`, `below_band`, `missing_field`, `date_window`, or a judged finding): FLAG, except as stated for CUAD.
3. Otherwise, at least one refusal: UNDECIDED.
4. Otherwise (only `ok` records, or nothing): CLEAR.

Irregular wins over refusal; refusal wins over ok. Prior-comparison relations (`changed_from_prior` and the others) cannot occur, since no bundle declares a prior; if one appears it is ignored and reported as an adapter fault. Irregular records tied to no item count as false positives (item 3.4) and change no label.

### 5.2 Per benchmark

- **ContraDoc.** One item per document; one rule for all documents ("the document does not contradict itself"). FLAG = contradictory, from any irregular record under that rule, whatever its relation. CLEAR = not contradictory. UNDECIDED = ABSTAIN.
- **CUAD.** One item per contract and category (41 per contract); one rule per category from its name and published description. FLAG = absent, only from an irregular record with relation `missing_field`. An irregular record with any other relation means present, because it implies the clause was found. CLEAR (no record, or ok only) = present. UNDECIDED = ABSTAIN. Gold: present when the category has at least one answer span, else absent.
- **SciTab.** One item per claim; the document is the table with its caption. FLAG = refutes. UNDECIDED = not enough info. CLEAR = supports. A run failure is ABSTAIN, never not enough info.
- **FinDVer.** One item per claim; the document is the filing. FLAG = refuted. CLEAR = entailed. UNDECIDED = ABSTAIN: the benchmark has no refusal class, so a refusal is reported as coverage and never counted as correct.

**B1** returns the benchmark label directly. Its "undecided" label maps to UNDECIDED as above (for SciTab, "not enough info" is the undecided label). An unparseable reply, or a label outside the list, is ABSTAIN. **B2** output is mapped exactly as B3's.

### 5.3 Cut rule for long documents (all arms)

Stated once, applied by the adapter before bundling, so B0, B1, B2, B3 and B4 receive the same text. The budget is the main reading agent's maximum context length (from its own configuration, read at run time), minus the token count of the B1 prompt below with an empty document (the largest over the document's items), minus the main reading agent's output allowance from the pipeline configuration, minus 32. Tokens are counted with that model's tokenizer. If the document under review fits, it is not cut. Otherwise the adapter keeps whole paragraphs (split at blank lines) from the start, in order, while they fit, and appends the line `[Document cut: the remaining N of M words are not shown.]`. If the first paragraph alone does not fit, it is cut at the last whitespace that fits. If the material still does not fit, the reference material is cut by the same rule. Items whose evidence falls beyond the cut are kept and scored, since removing them would use the labels. Every report gives, per benchmark, the number of documents cut and the share of words removed, and repeats the primary comparison on the uncut documents alone.

### 5.4 The B1 prompt, word for word

Sent through the model's own chat template, decoded under the main reading agent's decoding policy, with that agent's output allowance. Text in braces is filled by `benchmark/baselines/bare_model.py`; everything else is fixed.

System turn:

```
You are reviewing a document against written rules. You will receive the document, the rules (conventions) that apply to it, any reference material, one item to decide, and the labels you may use. Use only the material given.

Read the item. Find the parts of the document, and of the reference material, that bear on it. Then decide which label applies.

Answer with one JSON object and nothing else, in exactly this form:
{"item_id": "<the item id>", "reason": "<one or two sentences naming the part of the material your decision rests on>", "label": "<one label from the list>"}

Copy the label exactly as written in the list. If the material does not let you decide, use the label the list marks as undecided.
```

User turn:

```
DOCUMENT
{document, after the cut rule}

CONVENTIONS
{every convention in the bundle, as written in it, one per line with its rule id}

REFERENCE MATERIAL
{the bundle's reference material, or the single line: None.}

ITEM
Item id: {item id}
Rule id: {the item's rule id}
{the item's question line, below}

LABELS
{the benchmark's label lines, below}
```

Question lines and label lines:

- ContraDoc. Question: `Decide whether the document contradicts itself: whether two statements in it cannot both be true.` Labels: `contradictory: two statements in the document cannot both be true.` / `not_contradictory: no two statements in the document conflict.` / `undecided: the material does not let you decide. (undecided)`
- CUAD. Question: `Decide whether the document contains a clause of the category this rule describes.` Labels: `present: the document contains such a clause.` / `absent: the document contains no such clause.` / `undecided: the material does not let you decide. (undecided)`
- SciTab. Question: `Decide whether the table and its caption support the claim in this rule.` Labels: `supports: the table and caption show the claim is true.` / `refutes: the table and caption show the claim is false.` / `not enough info: the table and caption do not settle the claim. (undecided)`
- FinDVer. Question: `Decide whether the filing supports the claim in this rule.` Labels: `entailed: the filing shows the claim is true.` / `refuted: the filing shows the claim is false.` / `undecided: the material does not let you decide. (undecided)`

Each label line is one line of the LABELS block. The prompt gives the bare model the same document, conventions and reference material as Shimmer, the full label set with its meaning, room for a short reason before the label, and the same abstention option Shimmer has. A checker attacks it as a possible straw man (item 11).

## 6. The model-text review sample

For each external benchmark: a seeded random sample of at least 50 model-written texts from the B3 holdout runs (saved model reply records, and the `explanation` and `proposed_text` of model-written findings), or all of them if there are fewer. For B's synthetic tests: every text. The seed is chosen and recorded before any text is read. Each text gets one verdict, read against the source document: correct, partly correct, wrong, empty, unverifiable. The reviewer is never the builder. Verdict counts are reported per benchmark and change no label.

## 7. Reported whatever the result

- Every benchmark that received a sample, with every arm, on every measure of item 3, including null results and results where B3 is worse than B1, B2 or B0.
- Documents and decisions per benchmark; pilots marked as pilots.
- Coverage, abstentions, refusals and run failures per arm.
- Documents cut, the share of words removed, and the uncut-only comparison.
- The smallest detectable difference per benchmark.
- C0's mapping agreement counts and any benchmark dropped after three C0 runs.
- The model-text review verdicts.
- Every deviation from this preregistration, with its reason.
- Cost and time per document and per scored decision.

## 8. Contamination note

The models may have seen these public datasets, or their source documents, during training. Every report says so. Specifically: FinDVer's test labels have been public since 2026-07-14, so its contamination guard is gone; ContraDoc is built on public web text (CNN/DailyMail, NarrativeQA, WikiText); CUAD's contracts and annotations are public and widely circulated.

## 9. Limitations, stated in advance

- B's synthetic tests and the builder come from the same model family, so they may share blind spots.
- The order of preregistration, freeze, sampling and run is attested only by local records.
- Adapters were written and gate-checked on hand-written synthetic items built from documented schemas, without development items (D-019); the CUAD adapter is PROVISIONAL until their schemas are confirmed.
- CUAD's official ranked metrics cannot be produced; its headline measure is not comparable with published numbers.
- The cut rule removes text equally for every arm, which understates any arm built to read long documents; FinDVer filings are the most affected.
- B1 decides one item per call and sees each item alone; B3 reviews the whole document in one run. This difference is part of what the primary comparison measures.
- Mapping "no finding" to the CLEAR label credits silence; B0 shows how much that alone earns.
- FinDVer has no refusal class, so a correct refusal scores as wrong.
- FinDVer's size is reported differently by its own sources.

## 10. Hash records by B and C

When B and C start (B-dev, C0 and the S8b sessions), each copies this preregistration's current SHA-256 into a dated file in its own folder. That record sits outside the builder's write access.

## 11. Checker attacks

A `loop-checker` attacks this draft, including the B1 prompt as a possible straw man, before S4 closes. A fresh `loop-checker` attacks the completed version at the end of S5, before it is frozen.
