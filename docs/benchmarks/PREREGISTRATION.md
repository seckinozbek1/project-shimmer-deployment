# Preregistration: external benchmarks

Draft, loop stage S4. Completed and frozen at the end of S5; its SHA-256 recorded in docs/loop/VERSIONS.md before S8.

The benchmarks, their sources and licences are in `docs/benchmarks/SELECTION.md`. Bundles follow `docs/INPUT_FORMAT.md` (version `input-format-v1-draft`); run output follows `docs/OUTPUT_FORMAT.md` (current draft). Where a field name below is marked PROVISIONAL, it comes from documentation only and is confirmed on development items before freeze (section 12).

## 0. Terms and references

- **Document**: what one Shimmer run reviews (a contract, a filing, a table with its caption, a ContraDoc text).
- **Item**: one scored decision, carrying one benchmark label.
- **Item rule**: the convention the adapter writes for an item, by one item-independent template (section 5.5). Each item has exactly one rule id.
- **Item table**: a file `items.json` written by the adapter beside the bundle, never inside it, with the fields `item_id`, `document_id`, `rule_id`, `benchmark`. It holds no gold label. The B1 tool reads it to know which items to ask; no arm reads gold.
- **Gold**: the benchmark label of an item. It lives in the bundle's `answer_key.json` (which `docs/INPUT_FORMAT.md` section 9 requires to exist and which only the scorer reads) and in role B's folder. Neither Shimmer nor the B1 tool reads it.
- **Opaque ids**: every arm sees only opaque ids. Item id = the first 12 hexadecimal characters of SHA-256 of the UTF-8 string `item:<benchmark>:<source item id>`; document id likewise from `document:<benchmark>:<source document id>`. Benchmark names in these strings are `contradoc`, `cuad`, `scitab`, `findver`. Source ids appear only in `items.json` and in B's folder. Bundle and file names use the opaque document id.
- **FLAG, CLEAR, UNDECIDED**: per benchmark, the label an irregular finding maps to, the label for no finding, and what a refusal maps to (section 5.2).
- **ABSTAIN**: no label. Never correct; its role in every metric is fixed in section 4. Coverage is answered items over all items.
- **Silent**: a completed B3 or B2 run with no record of any kind for the item's rule id.
- **Refusal**: a record for the item's rule that carries the UNCERTAIN marker (the UNCERTAIN channel, genesis Part XXV), whatever its `record_verdict`, or a refusal entry naming that rule in the run's `audit/pairing_map.json`. Nothing else is a refusal. Exact field names: PROVISIONAL, filled from `docs/OUTPUT_FORMAT.md` before freeze.
- **Run failure**: for a document and an arm, `review_data.json` is missing, or the run's final status (`FINAL_STATUS.json`) is not `completed`, including a refusal at start. Exact status values: PROVISIONAL, as above.
- **Reference material**: none, for all four benchmarks. The B1 prompt shows the single line `None.`
- **Role B**: the test preparer, a session separate from the builder, that draws and holds the holdout sample. **B-dev**: B's session that downloads each benchmark, applies the split and passes only development items to the lead. **C**: the scorer role; **C0** is its end-of-S5 run that implements the scorer and these output-to-label rules from this text alone and compares its labels with the adapters' on development outputs (section 12). **R**: the S8 runner.
- **Loop plan**: `prompts/SHIMMER_AUTONOMOUS_LOOP_2026-10-27.md`. S5 is its development runs, S8 its sealed evaluation (S8b preparation, S8c runs); S4d, S4e, S4f are its items on arms, this preregistration and the baseline tools; IV.3 is its budget part (S8 allocation, reserve, the 1.3 forecast margin); H3 is its hard spend stop.
- **LAW-III**: the constitution's "No self-audit" law (`config/constitution.json`): no model checks output of its own model family.
- **D-019**: the decision in `docs/loop/DECISIONS.md` that B-dev could not run in S4, adapters are built on synthetic items from documented schemas only, and SummEdits is rejected.
- **Deviation log**: `docs/benchmarks/DEVIATIONS.md` (section 7).

## 1. Benchmarks, splits, split rules and holdout sampling

| Benchmark | Development | Holdout pool | Document id | Split key |
|---|---|---|---|---|
| ContraDoc | hash rule | the rest | `unique id` | the near-duplicate group's key (below) |
| CUAD v1 | hash rule (no official development split) | the rest | not documented outside the data; the contract, identified by the SHA-256 of its text | the document id |
| SciTab | hash rule (no official split) | the rest | `table_id` | `paper_id` |
| FinDVer | official split `testmini` | `test`, minus any item whose `report` also appears in `testmini` | `report` | (official split) |

**Hash rule.** The key is the split key as a string: for an integer id, its decimal form with no sign and no leading zeros; for a string id, the string exactly as stored. Where the id is "identified by the SHA-256 of its text", the key is the lowercase hexadecimal SHA-256 of the UTF-8 bytes of that text exactly as distributed, with no normalisation. Compute SHA-256 of the UTF-8 bytes of the key and read the digest as an unsigned big-endian integer. If it is 0 modulo 5, every item of every document under that key is development; otherwise every item is in the holdout pool. The hash is never taken over the item, so all of one document's decisions, and all documents sharing a split key, fall on the same side.

**Filters and groupings applied before the split.**

- SciTab: the 25 demonstration claims (5 tables) named by the paper are excluded from both sets. Their `table_id`s are listed here before freeze: pending B-dev. If they cannot be identified by freeze, no SciTab item is excluded.
- ContraDoc: before freeze, B-dev groups documents that share 80 percent or more of their sentences. A sentence is a run of text ended by `.`, `!` or `?` followed by whitespace, or by the end of the text, compared after collapsing whitespace. The share is shared sentences over the sentences of the shorter document. Groups are the connected components of that relation; the group's key is its smallest `unique id`. The number of groups and their sizes are reported.
- CUAD: contracts with identical text are merged before the split; the copy whose source id sorts first is kept, and the count is reported.
- FinDVer: before freeze, B-dev confirms that the pinned commit contains gold labels for `test`. If it does not, the commit is updated before freeze and recorded here and in `SELECTION.md`. If labels cannot be obtained before freeze, FinDVer is dropped from the holdout. The number of `test` items and filings removed for overlap with `testmini` is reported.
- Counts are taken from the pinned files and reported; published sizes are not used.

**Holdout sampling** (S8, role B). The unit sampled is the document; every item of a sampled document is scored. Sampling is done per benchmark separately, seeded and stratified by label:

- Length band, by whitespace-separated words of the document's source text before bundling and before the cut (for SciTab, the caption and the cell texts): A under 1,000; B 1,000 to 4,999; C 5,000 to 19,999; D 20,000 or more. S5 measures cost per document in these same bands.
- Label stratum: the share of the document's items whose gold label is FLAG: none; above none up to one half; above one half. For one-item documents this is the label itself. For CUAD, where nearly every contract lacks some category, the label stratum is the tertile of the share of absent categories: cut points from Python `statistics.quantiles(shares, n=3, method="inclusive")` over the pool, a share at or below the first cut point in the first stratum, at or below the second in the second, the rest in the third.
- Strata are length band crossed with label stratum.
- **Seed and generator.** The seed is chosen by role B at sampling time and recorded in B's folder, not here; B records it before drawing anything. The generator is Python's standard library `random.Random(seed)`. Each stratum's documents are sorted by source document id key (as in the hash rule) and shuffled in place by `Random.shuffle`, strata taken in order of band then label stratum, from one generator.
- **Order.** At position i (1-based), the deficit of stratum s is p_s * i - taken_s, where p_s is the stratum's share of the pool's documents and taken_s the number already taken from it. B takes the next document from the non-exhausted stratum with the largest deficit; ties go to the lower band, then the lower label stratum.
- B records this full seeded order, so that any prefix of it is itself a stratified random sample (S8c).

## 2. Sample sizes and the benchmark priority list

**Sample sizes: pending S5. Priority list: pending S5.**

Fit grades from `SELECTION.md`, the first key of the priority list: FinDVer Medium-high; CUAD, ContraDoc, SciTab Medium. (SummEdits is rejected as exposed, D-019.) The second key, measured cost per scored decision, is pending S5.

The rule, written now and applied at the end of S5:

> First set aside the forecast cost of B's synthetic tests, every arm. Then, in priority order, give each benchmark the smallest number of documents that yields at least 30 documents and at least 100 scored decisions, with B3 and B1 run on every item, at S5's measured cost per document by benchmark and document-length band, with the 1.3 forecast margin (IV.3). When the next benchmark's minimum would pass the S8 allocation, that benchmark gets what is left and is reported as a pilot, and the benchmarks below it get nothing. If allocation is left after every benchmark has its minimum, raise every benchmark by the same fraction until the allocation is used. A benchmark result is reported as a pilot unless it has at least 30 documents and at least 100 scored decisions. The priority list orders benchmarks by fit and then by measured cost per scored decision, cheapest first. It is fixed before B draws any sample.

How the rule is applied (clarifications beside the rule, not changes to it):

1. **Costs.** At the end of S5 the lead records cost per document by benchmark, length band and arm: B0 (no cost), B1, B2 (laptop, no rented cost) and B3; B4 separately. "Cost per scored decision" in the priority list is the cost of B1 plus B3 per decision; exact ties are broken alphabetically by benchmark name.
2. **Who and when.** The lead applies the rule at the end of S5, before freeze, from the pool's documents and decisions per band in `_handoff/B_SIZES.json` (written by B-dev). The number of documents n for a benchmark is the smallest n for which n documents with the pool's band shares and mean decisions per document reach both minimums; its forecast cost is n times the band-weighted cost per document, times 1.3. The n per benchmark is entered in this section before freeze.
3. **Prefix.** B's sample for a benchmark is the first n documents of B's seeded order. If those hold fewer than 100 scored decisions, B takes further documents in order until they do, before any run; the forecast is redone and the S8c cut rule applies to the result.
4. **Empty bands.** A length band with no development document takes the cost of the nearest measured band, scaled by the ratio of the two bands' median word counts in the pool (from `B_SIZES.json`; if absent there, by the ratio of the bands' lower bounds, band A counted as 500 words).
5. **The raise and B4.** The core forecast covers B0 to B3. The raise stops at twice each benchmark's minimum. B4 is forecast separately and runs only if the allocation left after that capped raise covers B4 on at least the minimum of the top-priority benchmark. Otherwise the raise continues past twice the minimum until the allocation is used, and B4 is not run.

Documents for each benchmark are taken as a prefix of B's seeded order (section 1).

**The S8c cut rule** (applied before any holdout run, by rule only, if the forecast of the whole design from S5's measured cost per document, by benchmark and length band, with the 1.3 margin, passes the S8 allocation):

1. drop B4;
2. drop whole benchmarks from the bottom of this priority list (fixed before B draws any sample);
3. if the design still does not fit, shorten every remaining benchmark to the same fraction, by taking the first n documents of B's seeded order (section 1), so that the shortened set is itself a stratified random sample.

The resulting n per benchmark is written down before the runner starts, and every cut is reported. The number of benchmarks sealed is whatever these rules give, and it is reported.

## 3. Primary measures

For every benchmark and every arm:

1. **The official metric**, or the closest honest measure with the reason:
   - ContraDoc: judgement accuracy (headline), with precision, recall and F1 for "contradictory". Evidence Hit Rate needs BERTScore; it is replaced by exact containment of the marked evidence sentence (whitespace-normalised) and labelled as not the official measure.
   - CUAD: AUPR and precision at 80 and 90 percent recall need a ranked score, which Shimmer's findings do not carry, and span Jaccard needs extracted spans. They are not reported. Closest honest measure (headline): macro-F1 over the two classes present and absent, computed on all (contract, category) items pooled, with precision and recall for "present" at Shimmer's single operating point. Secondary, not tested: the mean over categories of per-category macro-F1, and per-category F1 in an appendix table.
   - SciTab: macro-F1 over supports, refutes, not enough info; the 3 by 3 confusion matrix per arm is reported.
   - FinDVer: accuracy over all items, ABSTAIN counted wrong (headline); coverage and accuracy on answered items beside it. Also per subset (FDV-IE, FDV-MATH, FDV-KNOW; subset field PROVISIONAL) as a prespecified secondary breakdown, without tests.
   - Never claim comparability with published numbers that use a different metric or split.
2. **Location recall**: the share of FLAG items for which the arm emits the FLAG label and locates the evidence.
   - B3 and B2 locate by citing a unit: a record for the item's rule whose `unit_id` is a unit containing the evidence.
   - B1 locates by its `evidence` field: the string, whitespace-normalised, is contained in a unit that contains the evidence.
   - ContraDoc: a unit counts if it contains the evidence sentence or any marked reference sentence. FinDVer: a unit counts if it holds any of the item's context indices (section 5.6).
   - Where the benchmark marks no evidence, where FLAG is an absence (CUAD), or where the bundle holds one unit only (SciTab), location is not measurable: the value reported is recall on FLAG, labelled so.
3. **Reason-confirmed recall**: location catches whose explanation a reviewer marks correct, for B1 and B3 alike. The reviewer sees each catch with the arm label removed, B1 and B3 catches interleaved in a seeded order, and applies one written criterion: "the explanation identifies the conflicting or deciding content and is consistent with the gold evidence". Every catch is reviewed; above 200 per arm and benchmark, a seeded random sample of 200 per arm, reported as an estimate with a document-cluster bootstrap interval. The reviewer is never the builder.
4. **False positives**:
   - Item level: gold CLEAR and predicted FLAG, per arm.
   - Unattached findings (B3 and B2): irregular records whose `source_rule_id` matches no item, counted once by record id in `review_data.json`. Per-deliverable counts show how many of those record ids appear in each file (`review_data.json`, `review_findings.md`, `tracked_changes.docx`, `document_summary.md`). They change no label.
5. **Refusals**: items mapped from a refusal, and documents with a run failure.
6. **Which layer produced each catch**: Python (computed, `model=python`, `absence_path: computed`) or a model (judged).

## 4. Arms, comparisons and statistics

**Arms** (S4d), applied to every benchmark and every synthetic test of B:

- **B0, trivial baseline**: "no finding" on every item, mapped by section 5.2 (every item gets CLEAR).
- **B1, bare model**: the main reading agent's model and decoding policy, as recorded in VERSIONS.md (below); the fixed prompt of section 5.4, one call per item; no pipeline.
- **B2, Python only**: Shimmer's computing layer with no model call, run by `benchmark/baselines/python_only.py` on the laptop.
- **B3, full Shimmer**: the default configuration at the commit recorded in VERSIONS.md. Same bundles, same cut text.
- **B4, optional**: B3 with one alternative open-weight model family, named in VERSIONS.md before B draws any sample, only if budget remains after the core (section 2); LAW-III cross-family checking must hold.

These arm names are not the role sessions B1 and B2, nor the commits C1 to C5.

**Frozen configuration.** Before B draws the sample, the lead records in `docs/loop/VERSIONS.md`: the Shimmer commit; the SHA-256 of `config/agent_registry.json`, of `config/decoding_policy.json` and of the pipeline configuration used (backend profile, topology and review mode as resolved at that commit); the digest of every model checkpoint the pipeline loads, as pinned by the repository; and the decoding parameters of the main reading agent (the agent whose model `config/agent_registry.json` names for reading the document under review; it is a local model run by the pipeline). B1 uses exactly that checkpoint and those parameters, and the same thinking setting if the main reading agent has one. If a loaded checkpoint digest, a hashed file or the commit differs from the record during S8, the run stops and this is logged as a deviation.

**Run order** (S8c). B3 and B1 run on the same items, in the same instance session, by the same runner process, document by document in B's order: for each document, B3 first, then B1 on each of its items in item-id order, so that any stop leaves paired data. B2 runs on the laptop. B4 runs after the core. B0 needs no run.

**Comparisons**, per benchmark, on the headline metric of section 3:

- **Primary hypothesis H1** (per benchmark): B3's headline metric differs from B1's. Two-sided, alpha 0.05. B3 is called better on a benchmark only if the 95 percent paired cluster-bootstrap interval of (B3 minus B1) lies wholly above 0, and worse only if it lies wholly below 0. Otherwise the result is "no detectable difference", reported with the smallest detectable difference.
- **Across benchmarks**: any statement about Shimmer across benchmarks uses Holm-adjusted primary p-values across all non-pilot benchmarks (family-wise 0.05). It reports how many benchmarks favour each arm, and no pooled metric.
- **Secondary**, Holm-adjusted within each benchmark at family-wise 0.05: the family is {B3 against B2, B3 against B0}, ordered by p-value.
- **B4**: descriptive only, B4 against B3 intervals, no test.
- **Pilots**: point estimates and intervals only. No p-values, no Holm, no wording of "better" or "worse".

**Statistics.**

- Decisions inside one document are not independent (a CUAD contract carries 41). Confidence intervals come from a paired cluster bootstrap that resamples clusters, not decisions. The cluster is the split key (section 1): the document for ContraDoc without a group, CUAD and FinDVer; the near-duplicate group for ContraDoc; the paper for SciTab. Draw as many clusters as were scored, with replacement; recompute both arms' metric on all items of the drawn clusters (a cluster drawn twice counts twice); take the difference. 95 percent percentile interval, 10,000 resamples.
- **Seeds are derived, not chosen** (except the sampling seed, section 1): seed = int(SHA-256 hex of the UTF-8 string `<frozen preregistration SHA-256 hex>:<purpose>:<benchmark>`, base 16) mod 2^63. Purposes: `bootstrap`, `reason-review`, `text-review`. The generator is Python `random.Random(seed)`. A bootstrap resample is n calls of `randrange(n)` over the clusters sorted by their key; the review samples are `Random.sample` over the texts sorted by record id. A result computed with any other seed is a deviation.
- **p-values**: for each of the shares of resampled differences at or below zero and at or above zero, the share is (k + 1) / (10,000 + 1), where k is the count; the p-value is twice the smaller share, capped at 1.
- **ABSTAIN in F1-type metrics**: in every F1, precision or recall, ABSTAIN is a prediction of a class that matches no gold label: a false negative for the item's gold class and a false positive for no class. Any precision, recall or F1 with a zero denominator is set to 0, in point estimates and in every resample alike (as scikit-learn's `zero_division=0`). The number of resamples with a zero denominator is reported.
- McNemar's exact test is reported for ContraDoc (one decision per document), on correct versus not correct, ABSTAIN counted not correct, as a check; it decides nothing.
- Every result states the number of documents and clusters beside the number of decisions.
- **Smallest detectable difference** (SDD): 2.80 times the bootstrap standard error of the paired difference (two-sided 5 percent, 80 percent power), reported per benchmark. Planned SDD = 2.80 x SE_dev x sqrt(n_dev_docs / n_holdout_docs), from S5's development variance: pending S5. The observed SDD describes precision; it is not a power claim.
- **Sensitivity**: S-1 and S-2 (section 5.1); FinDVer also with a cluster bootstrap by issuer (CIK or ticker, where it can be derived from `report`; PROVISIONAL), reported beside the primary result.

## 5. Mapping text and the B1 prompt

### 5.1 Output to label, all benchmarks

Records are read from `review_data.json` only. A record belongs to an item when its `source_rule_id` equals the item's rule id, compared without regard to case. For each item apply the first matching line:

1. **Run failure**: every item of the document is ABSTAIN.
2. At least one record with `record_verdict` irregular that is not a refusal (any relation: `sum_mismatch`, `product_mismatch`, `above_band`, `below_band`, `missing_field`, `date_window`, or a judged finding): FLAG, except as stated for CUAD.
3. Otherwise, at least one refusal: UNDECIDED.
4. Otherwise:
   - 4a. at least one `ok` record: CLEAR;
   - 4b. no record of any kind for the item's rule (silent): CLEAR in the primary analysis. This is Shimmer's real answer: nothing found. For B2, a plan a model would have answered is listed as not asked (`ablation_not_asked`); that is silence, never a refusal.

Irregular wins over refusal; refusal wins over ok. Prior-comparison relations (`changed_from_prior` and the others) cannot occur, since no bundle declares a prior; if one appears it is ignored and reported as an adapter fault. Irregular records tied to no item count as unattached findings (section 3.4) and change no label.

**B1.** B1 returns the benchmark label directly (section 5.4). Its undecided label maps to UNDECIDED as below. A reply that cannot be parsed, or whose label matches no label name, is ABSTAIN (S4f: one typed JSON label per item, an unparseable reply counted as an abstention). A B1 call that fails or returns nothing is an unparseable reply. **B2** output is mapped exactly as B3's.

**Prespecified sensitivity analyses**, reported beside the primary result:

- **S-1**: B1 parse failures map to CLEAR, as B3's silence does.
- **S-2**: on ContraDoc, CUAD and FinDVer, UNDECIDED from every arm maps to CLEAR.

Per arm and benchmark the report gives the counts of silent items, UNDECIDED items and B1 parse failures.

### 5.2 Per benchmark

- **ContraDoc.** One item per document; one rule for all documents (section 5.5). FLAG = contradictory, from any irregular record under that rule, whatever its relation. CLEAR = not contradictory. UNDECIDED = ABSTAIN.
- **CUAD.** One item per contract and category (41 per contract); one rule per category (section 5.5). FLAG = absent: absent if any irregular record for the rule has relation `missing_field`, whatever its `absence_path` (computed or judged), even if other irregular records exist. Present otherwise: an irregular record with any other relation, an `ok` record, or silence. UNDECIDED = ABSTAIN. Prespecified counts per arm: items with both `missing_field` and another irregular relation, and judged irregular findings with no relation. Gold (PROVISIONAL): the CUAD text is the `context` string of the contract in `CUAD_v1.json`, UTF-8; present when the QA entry whose id ends in `__<Category>` has a non-empty `answers` list, else absent. `master_clauses.csv` is not used.
- **SciTab.** One item per claim; the document is the table with its caption. FLAG = refutes. UNDECIDED = not enough info. CLEAR = supports. A run failure is ABSTAIN, never not enough info.
- **FinDVer.** One item per claim; the document is the filing. FLAG = refuted. CLEAR = entailed. UNDECIDED = ABSTAIN: the benchmark has no refusal class, so a refusal is reported as coverage and never counted as correct.

### 5.3 Cut rule for long documents (all arms)

Stated once, applied by the adapter before bundling, so B0, B1, B2, B3 and B4 receive the same text. The budget is the main reading agent's maximum context length (from its own configuration, as recorded in VERSIONS.md), minus the token count of the B1 prompt below with an empty document (the largest over the document's items), minus the main reading agent's output allowance from the pipeline configuration, minus 32. Tokens are counted with that model's own tokenizer, loaded from the pinned local checkpoint. If the document under review fits, it is not cut. Otherwise the adapter keeps whole source parts (the parts of section 5.6, before they are written as units, so whole units) from the start, in order, while they fit, and appends to the last kept part the line `[Document cut: the remaining N of M words are not shown.]`. If the first part alone does not fit, it is cut at the last whitespace that fits. Reference material is never cut: no benchmark has any. B3 receives the same cut text; how the pipeline divides it across its own calls is part of B3. B4 receives the B3 text; if that does not fit B4's context, B4 is not run on that benchmark. Items whose evidence falls beyond the cut are kept and scored, since removing them would use the labels. Every report gives, per benchmark, the number of documents cut and the share of words removed, and repeats the primary comparison on the uncut documents alone.

### 5.4 The B1 prompt, word for word

Sent through the model's own chat template, decoded under the main reading agent's decoding policy, with that agent's output allowance. Text in braces is filled by `benchmark/baselines/bare_model.py`; everything else is fixed.

System turn:

```
You are reviewing a document against written rules. You will receive the document, the rules (conventions) that apply to it, any reference material, one item to decide, and the labels you may use. Use the material given; you may use general knowledge to interpret it.

Work through the item first: quote the passages of the document that bear on it, and do any calculation step by step. Then decide which label applies.

End your reply with one line holding one JSON object, and write nothing after it:
{"item_id": "<the item id>", "evidence": "<the exact sentence or sentences of the document your decision rests on, copied from it>", "reason": "<one or two sentences naming the part of the material your decision rests on>", "label": "<one label name from the list>"}

Copy the label name exactly as it is written before the colon in its line. If the material does not let you decide, use the undecided label named below the list.
```

User turn:

```
DOCUMENT
{document, after the cut rule, as it stands in the bundle}

CONVENTIONS
{every convention in the bundle, as written in it, one per line with its rule id}

REFERENCE MATERIAL
None.

ITEM
Item id: {opaque item id}
Rule id: {the item's rule id}
{the item's question line, below}

LABELS
{the benchmark's label lines, below}
The undecided label is: {the benchmark's undecided label name}
```

Question lines and label lines:

- ContraDoc. Question: `Decide whether the document contradicts itself: whether two statements in it cannot both be true.` Labels: `contradictory: two statements in the document cannot both be true.` / `not_contradictory: no two statements in the document conflict.` / `undecided: the material does not let you decide.` Undecided label: `undecided`.
- CUAD. Question: `Decide whether the document contains a clause of the category this rule describes.` Labels: `present: the document contains such a clause.` / `absent: the document contains no such clause.` / `undecided: the material does not let you decide.` Undecided label: `undecided`.
- SciTab. Question: `Decide whether the table and its caption support the claim in this rule.` Labels: `supports: the table and caption show the claim is true.` / `refutes: the table and caption show the claim is false.` / `not enough info: the table and caption do not settle the claim.` Undecided label: `not enough info`.
- FinDVer. Question: `Decide whether the filing supports the claim in this rule.` Labels: `entailed: the filing shows the claim is true.` / `refuted: the filing shows the claim is false.` / `undecided: the material does not let you decide.` Undecided label: `undecided`.

Each label line is one line of the LABELS block. The bare model gets the same document, conventions and reference material as Shimmer, every label with its meaning, room to work, and Shimmer's abstention option.

**The parser.** Remove every line that is only a code fence (three backticks, with or without a language name). Take the last balanced `{...}` in the reply and parse it as JSON; if that fails, the reply is unparseable. Read `label`; lowercase it, trim it, remove a trailing `(undecided)` and anything from the first `:` on, trim again, and replace `_` with a space. Compare it with the label names treated the same way; a match gives that label, no match makes the reply unparseable. An `item_id` that differs from the item's id is ignored. `evidence` and `reason` are kept for sections 3.2 and 3.3 and never change the label. The parse rate per benchmark is reported.

**Development check.** In S5, B1 is run on the development items. The B1 prompt and parser may be revised before freeze under the same rules as B3: development items only, every revision logged with its development numbers. The frozen prompt is the last revision.

### 5.5 Rule templates, word for word

Each bundle has one conventions file, `conventions/rules.md`. Its first line is `# Review rules`, then one blank line, then for each rule, in rule-id order: the rule heading, a blank line, the rule text as one paragraph, a blank line. The heading is `## <rule id> <name> [required] [conformance]`. The operator's own id on the heading must start with `CONV-` (`docs/INPUT_FORMAT.md` section 3), so the short rule ids below are written on the heading in that form. In every template, `{claim}` is the claim text with each run of whitespace replaced by one space and nothing else changed; it is the only slot except CUAD's `{name}` and `{description}`. No rule carries a `[scope: ...]`, `[requires: ...]` or `[unless: ...]` directive; each rule pairs with every unit through the label `Passage` (section 5.6).

- **ContraDoc.** Rule id `CONV-CDOC-01`, name `Consistency`. Text: `No passage of the document may contain a statement that cannot be true together with another statement in the same passage or in another passage of the document.`
- **CUAD.** One rule per row of the table below; rule id `CONV-CUAD-NN` for row `cuad-NN`, name `Category`. Text: `The document must contain, in at least one passage, a clause of this category: {name}. {description}`
- **SciTab.** One rule per claim; rule id `CONV-` followed by the opaque item id, name `Claim`. Text: `Claim about the table in this passage: {claim} The claim must agree with the table and its caption. If the table and caption do not settle the claim, emit UNCERTAIN.`
- **FinDVer.** One rule per claim; rule id `CONV-` followed by the opaque item id, name `Claim`. Text: `Claim about the filing: {claim} The claim must agree with the passages of the filing.`

CUAD categories. Names are copied from the CUAD paper's category list (arXiv 2103.06268, Tables 4 and 5), in its order. For every row the description is: as in the category list distributed with CUAD v1, copied verbatim by the adapter at freeze. In the template, `{description}` is that text with each run of whitespace replaced by one space; if a row has none, `{description}` is empty and the template uses the name alone. Where the spelling of a category in the data's QA ids differs from the name here, the adapter matches by the data's own spelling, records both here at freeze, and the name here stays in the rule text (PROVISIONAL).

| Row | Category | Row | Category |
|---|---|---|---|
| cuad-01 | Document Name | cuad-22 | Minimum Commitment |
| cuad-02 | Parties | cuad-23 | Volume Restriction |
| cuad-03 | Agreement Date | cuad-24 | IP Ownership Assignment |
| cuad-04 | Effective Date | cuad-25 | Joint IP Ownership |
| cuad-05 | Expiration Date | cuad-26 | License Grant |
| cuad-06 | Renewal Term | cuad-27 | Non-Transferable License |
| cuad-07 | Notice to Terminate Renewal | cuad-28 | Affiliate IP License-Licensor |
| cuad-08 | Governing Law | cuad-29 | Affiliate IP License-Licensee |
| cuad-09 | Most Favored Nation | cuad-30 | Unlimited/All-You-Can-Eat License |
| cuad-10 | Non-Compete | cuad-31 | Irrevocable or Perpetual License |
| cuad-11 | Exclusivity | cuad-32 | Source Code Escrow |
| cuad-12 | No-Solicit of Customers | cuad-33 | Post-Termination Services |
| cuad-13 | Competitive Restriction Exception | cuad-34 | Audit Rights |
| cuad-14 | No-Solicit of Employees | cuad-35 | Uncapped Liability |
| cuad-15 | Non-Disparagement | cuad-36 | Cap on Liability |
| cuad-16 | Termination for Convenience | cuad-37 | Liquidated Damages |
| cuad-17 | ROFR/ROFO/ROFN | cuad-38 | Warranty Duration |
| cuad-18 | Change of Control | cuad-39 | Insurance |
| cuad-19 | Anti-Assignment | cuad-40 | Covenant Not to Sue |
| cuad-20 | Revenue/Profit Sharing | cuad-41 | Third Party Beneficiary |
| cuad-21 | Price Restriction | | |

No template, category name or description may change after freeze. A change is a deviation and is reported, with results under both versions where both were run.

### 5.6 Document text and units

Every document file is `context/<opaque document id>.md`, named alone in `targets` of `context/_review_targets.json`, with empty `grounding` and `prior`. Its first line is `# D-<opaque document id>`. Then the document's parts follow in order, each as one unit made by a heading (`docs/INPUT_FORMAT.md` section 2):

```
## P-<k, five digits>

Passage: part

<the part's text>
```

`k` counts the parts from 00001 in order (the heading may carry digits; headings are not values). The label line `Passage: part` holds letters only, because every digit in a value is read as a figure (`docs/INPUT_FORMAT.md` section 2; `P-00001` would be the figure -1, which enters products and ratios). It gives every unit the field the rule templates name, so every unit pairs with every rule and no unit is left with no rule (`docs/INPUT_FORMAT.md` sections 4 and 5). A source line that begins with `#` is written with a backslash before the `#`, so it never starts a unit. The adapter records, per document, the unit id of each part and the source span or index it came from. The parts:

- **ContraDoc**: the `text` field verbatim, one part per blank-line paragraph. No sentence splitter is used.
- **CUAD**: the contract's `context` string (PROVISIONAL), one part per blank-line paragraph.
- **SciTab**: one part only: the caption line, a blank line, then the table as a pipe-delimited Markdown table, header row first, then the separator row, then body rows, each cell's text as given with `|` written as `\|`. Field names for caption and table: PROVISIONAL.
- **FinDVer**: the filing's paragraphs and tables in index order, one part each, a table written as SciTab's is. The part at context index k is part k when indices start at 1, and part k + 1 when they start at 0; the adapter records which, so that context index k maps to exactly one unit. Field names: PROVISIONAL.

## 6. The model-text review sample

For each external benchmark: a seeded random sample of at least 50 model-written texts from the B3 holdout runs (saved model reply records, and the `explanation` and `proposed_text` of model-written findings), or all of them if there are fewer. For B's synthetic tests: every text. The seed is derived (section 4, purpose `text-review`) and so fixed before any text is read. Each text gets one verdict, read against the source document: correct, partly correct, wrong, empty, unverifiable. The reviewer is never the builder. Verdict counts are reported per benchmark and change no label.

## 7. Reported whatever the result, and the stopping rule

**Stopping and changes.**

- No holdout metric is computed until every arm has finished the sized sample, or the hard stop (H3) has ended the runs. The sample is never extended after any holdout result is seen.
- Never drop, skip or reorder items after any result is seen. If the hard stop interrupts a run, the scored set is the completed prefix in B's order (documents on which both B3 and B1 finished), and it is reported as such; a document begun but not finished is listed.
- An item whose pipeline run fails is scored as a failure: never dropped, never re-run. Only an infrastructure failure before the item started (instance lost, attach failed) may be re-run, once, paid from the reserve, and the re-run is reported.
- A defect in an adapter, the mapping or the scorer found after unblinding is fixed for every arm. Results are reported under both the frozen and the fixed code; the frozen code's numbers are primary.
- Every deviation is entered in `docs/benchmarks/DEVIATIONS.md` before the change is applied, with a timestamp, its reason, and whether any holdout result had been seen.

**Reported:**

- Every benchmark that received a sample, with every arm, on every measure of section 3, including null results and results where B3 is worse than B1, B2 or B0.
- Documents, clusters and decisions per benchmark; pilots marked as pilots.
- Coverage, abstentions, refusals, silent items, B1 parse failures and run failures per arm, with S-1 and S-2.
- Documents cut, the share of words removed, and the uncut-only comparison.
- The smallest detectable difference per benchmark, planned and observed.
- C0's mapping agreement counts, the number of C0 runs, and any benchmark dropped under the C0 rule (section 12).
- The model-text review verdicts.
- Every deviation from this preregistration, from the deviation log.
- Cost and time per document and per scored decision, per arm, with the number of model calls and tokens.

## 8. Contamination note

The models may have seen these public datasets, or their source documents, during training. Every report says so. Specifically: FinDVer's test labels have been public since 2026-07-14, so its contamination guard is gone; ContraDoc is built on public web text (CNN/DailyMail, NarrativeQA, WikiText); CUAD's contracts and annotations are public and widely circulated.

## 9. Limitations, stated in advance

- B's synthetic tests and the builder come from the same model family, so they may share blind spots.
- The order of preregistration, freeze, sampling and run is attested only by local records.
- Adapters were written and gate-checked on hand-written synthetic items built from documented schemas, without development items (D-019); the CUAD adapter is PROVISIONAL until their schemas are confirmed.
- CUAD's official ranked metrics cannot be produced; its headline measure is not comparable with published numbers.
- The cut rule removes text equally for every arm, which understates any arm built to read long documents; FinDVer filings are the most affected.
- B1 decides one item per call and sees each item alone; B3 reviews the whole document in one run. This difference is part of what the primary comparison measures.
- Mapping "no finding" to the CLEAR label credits silence; B0 shows how much that alone earns, and S-1 shows how much it changes the B1 comparison.
- FinDVer has no refusal class, so a correct refusal scores as wrong.
- FinDVer's size is reported differently by its own sources; the counts used are those of the pinned files.
- The rule templates are fixed text; a different wording could change every arm's result.

## 10. Hash records by B and C

When B and C start (B-dev, C0 and the S8b sessions), each copies this preregistration's current SHA-256 into a dated file in its own folder. That record sits outside the builder's write access.

## 11. Checker attacks

A `loop-checker` attacks this draft, including the B1 prompt as a possible straw man, before S4 closes. A fresh `loop-checker` attacks the completed version at the end of S5, before it is frozen.

## 12. The C0 rule and items open before freeze

**C0.** C0 uses development items only; no holdout item enters it. The preregistration is frozen only after a C0 run reports full agreement, on every benchmark that stays in the design, between C's labels (from this text) and the adapters' labels. If any item differs, the lead settles it in this text or in the adapter, and C0 runs again. At most three C0 runs. If items still differ after the third, the benchmarks they belong to are dropped from the S8 priority list and the sample sizes are refilled by section 2, before B draws any sample.

**Open before freeze**, each settled on development items in S5 and written here, or the benchmark it concerns is dropped before B draws any sample:

1. The exact field names of a refusal and of a run's final status, from `docs/OUTPUT_FORMAT.md`.
2. Whether B3, under the frozen review mode, can return one document-level judgement for the ContraDoc rule and a document-level absence for a CUAD category when each rule pairs with every unit, rather than one record per unit.
3. Whether claim figures in a SciTab or FinDVer rule are read as a band (`docs/INPUT_FORMAT.md` section 7). If they are, the count of items whose FLAG came from a band relation is reported per arm.
4. Whether the backslash before a source `#` keeps the line from starting a unit, and whether unit positions above 99 keep their ids.
5. The PROVISIONAL field names for CUAD, SciTab and FinDVer, and the FinDVer subset and issuer fields.
6. The SciTab demonstration tables (section 1) and the FinDVer test labels at the pinned commit.
7. Computed findings on source text. Python reads every `Label: value` line, number and pipe table inside a part as fields and figures, and computes sums, products, bands and blank cells on them, whatever the rules say (`docs/INPUT_FORMAT.md` section 7, "Figure audit"). Such a finding is attributed to the paired rule sharing the most words with its labels, ties to the first in reading order (section 9 of the input format); with every rule naming only `passage`, that is the first rule of the bundle. Settle on development items: the count per benchmark and arm of irregular records whose relation is `sum_mismatch`, `product_mismatch` or `missing_field` from blank cells, and whether they are excluded from the item mapping (they are not a check of the item's claim) or kept. Dates and identifiers with digits read as figures with no measure (open item 16, defect 2) are part of this count.
8. The main reading agent: which model and output allowance B1 uses and the cut rule counts with. The agent registry names a cloud model for the reading agent while the local profile and the final-model configuration name local checkpoints, and the output allowance differs by path (2048 by default, other bounds on the optimized path). One model id, checkpoint digest and output allowance are pinned in VERSIONS.md before sampling (section 4), and B1 is passed that allowance explicitly.
9. Where the typed records live in a run's output. `review_data.json` holds amendments without each finding's `source_rule_id` and `record_verdict`; section 5.1 needs them. `docs/OUTPUT_FORMAT.md` names the key that carries the typed records (B2 writes them under `findings`), and the pipeline and B2 agree on it, before C0.
