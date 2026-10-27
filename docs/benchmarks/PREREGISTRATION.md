# Preregistration: external benchmarks

Draft, loop stage S4. Completed and frozen at the end of S5; its SHA-256 recorded in docs/loop/VERSIONS.md before S8.

The benchmarks, their sources and licences are in `docs/benchmarks/SELECTION.md`. Bundles follow `docs/INPUT_FORMAT.md` (version `input-format-v1-draft`, on branch `loop/s03`); run output will follow `docs/OUTPUT_FORMAT.md`, to be written in S3 (no draft exists yet on any branch). The field names and stored values of the five releases were confirmed on the development items B-dev passed on (D-032; the adapters were then fixed from them, D-038). Two kinds of name are still PROVISIONAL: those of a run's output, until `docs/OUTPUT_FORMAT.md` settles them (section 12 items 1 and 9), and the few release facts no development item could show (section 12 item 5). Everything else still open is listed in section 12.

## 0. Terms and references

- **Document**: what one Shimmer run reviews (a contract, a filing, a table with its caption, a ContraDoc text).
- **Item**: one scored decision, carrying one benchmark label.
- **Item rule**: the convention the adapter writes for an item, by one item-independent template (section 5.5). Each item has exactly one rule id.
- **Item table**: a file `items.json` written by the adapter beside the bundle, never inside it, with the fields `item_id`, `document_id`, `rule_id`, `benchmark`, and the source ids `source_item_id` and `source_document_id`. It holds no gold label. The B1 tool reads it to know which items to ask; no arm's model sees it, and no arm reads gold.
- **Parts record**: a file `parts.json` written by the adapter beside the bundles: per document the unit id of each part with its source span or index, the split key, side and cluster, the word count and length band, the cut record (budget, prompt overhead, words removed, parts kept whole), and the ids of the items whose marked evidence lies beyond the cut (section 5.3); the build's declared side, the SHA-256 of any split, testmini or exclusion file it read, the frozen-file check of its input where the benchmark has one (section 1), and the documents skipped or excluded. It holds source ids and no gold label (the evidence-beyond-cut list is read from the evidence marks, not from the labels). The adapters, B, C and the scorer read it; no arm's model sees it.
- **Gold**: the benchmark label of an item. It lives in the bundle's `answer_key.json` (which `docs/INPUT_FORMAT.md` section 9 requires to exist and which only the scorer reads) and in role B's folder. Neither Shimmer nor the B1 tool reads it.
- **Opaque ids**: every arm sees only opaque ids. Item id = the first 12 hexadecimal characters of SHA-256 of the UTF-8 string `item:<benchmark>:<source item id>`; document id likewise from `document:<benchmark>:<source document id>`. Benchmark names in these strings are `contradoc`, `cuad`, `scitab`, `findver`, `contractnli`. Source ids appear only in `items.json`, `parts.json` and B's folder, never inside a bundle. Bundle and file names use the opaque document id.
- **Key order**: wherever ids or keys are sorted, they are sorted as key strings (section 1) in code-point order.
- **FLAG, CLEAR, UNDECIDED**: per benchmark, the label an irregular finding maps to, the label for a settled answer or no finding, and what a refusal maps to (section 5.2).
- **ABSTAIN**: no label. Never correct; its role in every metric is fixed in section 4. Coverage is answered items over all items.
- **Silent**: a completed B3 or B2 run with no record of any kind for the item's rule id.
- **Refusal**: a record for the item's rule that carries the UNCERTAIN marker (the UNCERTAIN channel, genesis Part XXV), whatever its `record_verdict`, or a refusal entry naming that rule in the run's `audit/pairing_map.json`. Nothing else is a refusal. The marker is tested as the verifiability gate tests it (`scripts/verifiability_gate.py`): a truthy `uncertain` field, or a `confidence` field equal to `UNCERTAIN` once uppercased. Exact field names: PROVISIONAL, filled from `docs/OUTPUT_FORMAT.md` before freeze.
- **Figure-audit record**: a record whose `relation` is `missing_field`, `below_band`, `above_band`, `sum_mismatch` or `product_mismatch`. Python computes these on any figure, label or table in a part, whatever the rules say (`docs/INPUT_FORMAT.md` section 7), and attributes each to a paired rule (section 5.1 says when it decides an item).
- **Run failure**: for a document and an arm, `review_data.json` is missing or unreadable, or the run's completion record is absent, invalid or not `completed`. The completion record is `<run>/audit/run_completion.json`, written by the pipeline (`scripts/run_completion.py`); B2 writes the same record. It is valid only as `run_completion.read()` accepts it: `schema_version` 1, a known `state`, and for `completed` also `reached_end` true, an integer `exit_code` of 0 and a `finished_at` timestamp. A refusal at start leaves no `completed` record. Exact names: PROVISIONAL, as above.
- **Reference material**: none, for all five benchmarks. The B1 prompt shows the single line `None.` B's synthetic tests may carry reference material (grounding files); B1 then shows it (section 5.4).
- **Role B**: the test preparer, a session separate from the builder, that draws and holds the holdout sample. **B-dev**: B's session that downloaded each benchmark, applied the split and passed only development items to the lead (D-032). **C**: the scorer role; **C0** is its end-of-S5 run that implements the scorer and these output-to-label rules from this text alone and compares its labels with the adapters' on development outputs (section 12). **R**: the S8 runner.
- **Loop plan**: `prompts/SHIMMER_AUTONOMOUS_LOOP_2026-10-27.md`. S5 is its development runs, S8 its sealed evaluation (S8b preparation, S8c runs, S8d results); S4d, S4e, S4f are its items on arms, this preregistration and the baseline tools; IV.3 is its budget part (S8 allocation, reserve, the 1.3 forecast margin); H3 is its hard spend stop.
- **S8 allocation**: 36 USD (the operator's decision D-S9, amending IV.3), plus any roll-forward recorded in `docs/loop/BUDGET.md` at the end of S5; the reserve is excluded.
- **LAW-III**: the constitution's "No self-audit" law (`config/constitution.json`): no model checks output of its own model family.
- **Decisions** in `docs/loop/DECISIONS.md`: **D-019** rejects SummEdits as exposed; its other parts (B-dev could not run in S4, adapters on synthetic items only) were superseded when B-dev ran. **D-032**: the B-dev session, which ran on 27 October 2026 and passed development items for all five benchmarks with a manifest each. **D-038**: the adapters fixed on those development items. **D-039**: the lead's twenty decisions of S4 checker round 2, made before any B1 or B3 development output existed, carried into this text. **D-S3**: the operator's decision of 27 October 2026 accepting ContractNLI's terms of use; only role B downloads it, under that acceptance. **D-S9**: the operator's decision raising the budget (the S8 allocation above).
- **Deviation log**: `docs/benchmarks/DEVIATIONS.md` (section 7).

## 1. Benchmarks, splits, split rules and holdout sampling

| Benchmark | Development | Holdout pool | Document id | Split key |
|---|---|---|---|---|
| ContraDoc | hash rule | the rest | `unique id` (a string) | the near-duplicate group's key (below) |
| CUAD v1 | hash rule (no official development split) | the rest | the contract, identified by the SHA-256 of its `context` text | the document id |
| SciTab | hash rule (no official split) | the rest, minus the demonstration tables (below) | `table_id` | `paper_id` |
| FinDVer | official split `testmini` | `test`, minus any item whose `report` also appears in `testmini` | `report` (the filing's file name) | (official split) |
| ContractNLI | official split `dev` | official split `test` (`train` is not used) | `id` (an integer) | (official split) |

**Hash rule.** The key is the split key as a string: for an integer id, its decimal form with no sign and no leading zeros; for a string id, the string exactly as stored. Where the id is "identified by the SHA-256 of its text", the key is the lowercase hexadecimal SHA-256 of the UTF-8 bytes of that text exactly as distributed, with no normalisation. Compute SHA-256 of the UTF-8 bytes of the key and read the digest as an unsigned big-endian integer. If it is 0 modulo 5, every item of every document under that key is development; otherwise every item is in the holdout pool. The hash is never taken over the item, so all of one document's decisions, and all documents sharing a split key, fall on the same side. This document-level rule replaces, for B-dev, the item-id rule of the loop plan's S4c item 0 ("SHA-256 of the item id, modulo 5"), which B-dev's role file repeats; where the two differ, this section governs (B-dev followed this section: `external/_bdev/BDEV_REPORT.json`, notes).

**Sides are enforced at build.** Every build declares its side (`--side development|holdout`). A document whose recorded side differs from the declared side makes the whole build refuse, writing nothing. Only a build flagged `--development` (development work) may skip the declaration, and `parts.json` records that it did; such a build refuses a document on the holdout side unless `--side holdout` is also given (D-039 item 14). A document's side is the hash rule's for ContraDoc, CUAD and SciTab; for FinDVer, the official split of its items (`split`); for ContractNLI, the side of the frozen file it is read from:

- ContractNLI: an input is accepted only when its SHA-256 is that of the frozen file of the declared side. The development side is the release's `dev.json`, whose SHA-256 the B-dev manifest records (`external/contractnli/MANIFEST.json`, `files_passed_on_sha256`), held by the adapter; the holdout side is `test.json`, whose SHA-256 role B records and passes with `--frozen-sha256`. `train.json`, or any other file, is refused for either side, and so is a development build of anything but `dev.json`. `split` applies the same check.

**Demonstration documents.** A document that a benchmark's own paper prints as an in-context (demonstration) example is excluded from the holdout pool, because it is the most likely to have been seen (D-039 item 15). Role B identifies such documents before sampling and passes their source document ids in a file to every build, `split` and `bands` of that benchmark (`--exclude`); `parts.json` records the file's SHA-256 and every document removed, with its item count, and `split` marks them `excluded_demonstration`.

**Filters and groupings applied before the split.**

- SciTab: the paper says 5 tables (25 claims) were held out as in-context examples, but prints only four of them and names no fifth table and no list of the claims (`external/scitab/MANIFEST.json`, `demonstration_tables`). The tables B identifies by caption are excluded from the holdout pool as above. B-dev matched the four printed tables by caption; all four are on the holdout side, so no development item is affected. A table B cannot identify stays in the pool, and the number excluded is reported.
- ContraDoc: documents that share 80 percent or more of their sentences are grouped. A sentence is a run of text ended by `.`, `!` or `?` followed by whitespace, or by the end of the text, compared after collapsing whitespace. The share is shared distinct sentences over the distinct sentences of the document that has fewer. Groups are the connected components of that relation; the group's key is its smallest `unique id` (numeric order when every id is an integer, else string order; the stored ids are strings, not all integers, so string order applies). B-dev computed the groups once, on the whole input (891 documents: 494 near-duplicate links, 642 groups, the largest of 7 documents), with its own implementation of this rule, because the adapter's `split` command was not available to it; that frozen file (`assignments`: group key and side per `unique id`) is held by B with its SHA-256, and its development entries reached the lead (`external/contradoc/MANIFEST.json`). Every build reads groups and sides from the frozen file (`build --assignment <file>`) and refuses a document the file does not list, so a build from a sample never regroups. On the 184 development documents the adapter's own grouping equals B-dev's (125 groups). Before sampling, B runs the frozen adapter's `split` on the whole input and reports the number of documents whose group key differs from the frozen file (expected 0); any difference is entered in the deviation log and settled before B draws. The number of groups and their sizes are reported.
- CUAD: contracts with identical text are merged before the split; the copy whose `title` sorts first is kept, because the source id, the SHA-256 of the text, is the same for every copy. In the release, 1 of 510 entries is such a copy (509 contracts; `external/cuad/MANIFEST.json`). The count is reported.
- FinDVer: a holdout build is given the `testmini` file and refuses any report that also appears in it, and an item whose own `split` names the other official split is refused. The pinned commit holds gold labels for `test` (`external/findver/MANIFEST.json`, `test_gold_labels_present_at_pinned_commit`). At that commit `testmini` holds 700 items over 255 filings and `test` 1,700 items over 439 filings; 155 filings appear in both, so 470 `test` items are removed, leaving a holdout pool of 1,230 items over 284 filings. No filing is on both sides.
- ContractNLI: the `dev` split (61 agreements, 1,037 items) is development and the `test` split (123 agreements, 2,091 items) the holdout pool; `train` (423 agreements) is not used. No agreement id or identical text is shared between the splits (`external/contractnli/MANIFEST.json`). An agreement is identified by the release's integer `id`, which is also its cluster. Every item is one (agreement, hypothesis) pair; its source item id is `<document id>:<hypothesis key>`.
- Counts are taken from the pinned files and reported; published sizes are not used.

**Holdout sampling** (S8, role B). The unit sampled is the document; every item of a sampled document is scored. Sampling is done per benchmark separately, seeded and stratified by label:

- Length band, by the document's words as section 5.6 (Words) counts them, before bundling and before the cut: A under 1,000; B 1,000 to 4,999; C 5,000 to 19,999; D 20,000 or more. S5 measures cost per document in these same bands. B reads every pool document's words and band with the frozen adapter's `bands` command, which writes them over a whole input with no build, and stratifies by it; B writes S8's `_handoff/B_SIZES.json` (documents, decisions and median words per band) from the same output (D-039 item 7).
- Label stratum: the share of the document's items whose gold label is FLAG: none; above none up to one half; above one half. For one-item documents this is the label itself. For CUAD, where nearly every contract lacks some category, the label stratum is the tertile of the share of absent categories: cut points from Python `statistics.quantiles(shares, n=3, method="inclusive")` over the pool, a share at or below the first cut point in the first stratum, at or below the second in the second, the rest in the third.
- Strata are length band crossed with label stratum.
- **Seed and generator.** The seed is chosen by role B at sampling time and recorded in B's folder, not here; B records it before drawing anything. The generator is Python's standard library `random.Random(seed)`. Each stratum's documents are sorted by source document id key (key order, section 0) and shuffled in place by `Random.shuffle`, strata taken in order of band then label stratum, from one generator.
- **Order.** At position i (1-based), the deficit of stratum s is p_s * i - taken_s, where p_s is the stratum's share of the pool's documents and taken_s the number already taken from it. B takes the next document from the non-exhausted stratum with the largest deficit; ties go to the lower band, then the lower label stratum.
- B records this full seeded order, so that any prefix of it is itself a stratified random sample (S8c).

## 2. Sample sizes and the benchmark priority list

**Sample sizes: pending S5. Priority list: pending S5.**

Fit grades from `SELECTION.md`, the first key of the priority list: ContractNLI High; FinDVer Medium-high; CUAD, ContraDoc, SciTab Medium. (SummEdits is rejected as exposed, D-019.) The second key, measured cost per scored decision, is pending S5. Fit is the first key, so ContractNLI is first and cannot move down the list by cost; D-038's remark that its cost "may move ContractNLI down the cost-ordered priority list" is corrected here (D-039 item 2). Its cost is met instead by the fallback below.

The rule, written now and applied at the end of S5:

> First set aside the forecast cost of B's synthetic tests, every arm. Then, in priority order, give each benchmark the smallest number of documents that yields at least 30 documents and at least 100 scored decisions, with B3 and B1 run on every item, at S5's measured cost per document by benchmark and document-length band, with the 1.3 forecast margin (IV.3). When the next benchmark's minimum would pass the S8 allocation, that benchmark gets what is left and is reported as a pilot, and the benchmarks below it get nothing. If allocation is left after every benchmark has its minimum, raise every benchmark by the same fraction until the allocation is used. A benchmark result is reported as a pilot unless it has at least 30 documents and at least 100 scored decisions. The priority list orders benchmarks by fit and then by measured cost per scored decision, cheapest first. It is fixed before B draws any sample.

The S8 allocation is 36 USD (D-S9, amending IV.3), plus any roll-forward recorded in `docs/loop/BUDGET.md` at the end of S5; the reserve is excluded.

**ContractNLI's cost fallback, written now** (D-039 item 2). ContractNLI keeps one part per span (section 5.6), so that location stays measurable. If S5's measured B3 cost per ContractNLI agreement, times the 30-agreement minimum, times 1.3, exceeds half of the S8 allocation (half of 36 USD, so 18 USD), its parts become merged spans (section 5.6, the fallback rule) for every arm and for the rest of the design. The trigger is decided by cost alone, from S5's measured cost; S5 records the measured cost, the product and which rule applied, and the cost per agreement under the applied rule is the one used for sizing.

How the rule is applied (clarifications beside the rule, not changes to it):

1. **Costs.** At the end of S5 the lead records cost per document by benchmark, length band and arm: B0 (no cost), B1, B2 (laptop, no rented cost) and B3; B4 separately. "Cost per scored decision" in the priority list is the cost of B1 plus B3 per decision; exact ties are broken alphabetically by benchmark name.
2. **Who and when.** The lead applies the rule at the end of S5, before freeze, from the pool's documents and decisions per band in `_handoff/B_SIZES.json`. B-dev wrote that file with, per benchmark and length band, the pool's documents, its decisions (items) and its median word count, by its own reading: the whitespace-separated tokens of each document's raw source strings, a FinDVer table's pipes and separator tokens included, not the word rule of section 5.6. On the development items the two readings place 11 of the 255 FinDVer filings in different bands (D by B-dev's reading, C by the rule) and every development document of the other four benchmarks in the same band (private run summary `bands_development.json`). The S5 sizing therefore uses `B_SIZES.json` only as counts per band (documents, decisions, and the median words of item 4), never to place a document in a band. Its bias has a known direction: for FinDVer it overweights band D, the most expensive band, so the FinDVer forecast errs high (it overstates the cost, which spends less, never more). Every document that is built, sampled, costed or reported is placed by the section 5.6 rule, as the adapters' `bands` command and `parts.json` record it, and S8's `B_SIZES.json` is written by B from the `bands` command (section 1). The number of documents n for a benchmark is the smallest n for which n documents with the pool's band shares and mean decisions per document reach both minimums; its forecast cost is n times the band-weighted cost per document, times 1.3. The n per benchmark is entered in this section before freeze.
3. **Prefix.** B's sample for a benchmark is the first n documents of B's seeded order. If those hold fewer than 100 scored decisions, B takes further documents in order until they do, before any run; the forecast is redone and the S8c cut rule applies to the result.
4. **Empty bands.** A length band with no development document takes the cost of the nearest measured band, scaled by the ratio of the two bands' median word counts in the pool (from `B_SIZES.json`; if absent there, by the ratio of the bands' lower bounds, band A counted as 500 words).
5. **The raise and B4.** The core forecast covers B0 to B3. The raise stops at twice each benchmark's minimum. B4 is forecast separately and runs only if the allocation left after that capped raise covers B4 on at least the minimum of the top-priority benchmark. Otherwise the raise continues past twice the minimum until the allocation is used, and B4 is not run.

Documents for each benchmark are taken as a prefix of B's seeded order (section 1).

**The S8c cut rule** (applied before any holdout run, by rule only, if the forecast of the whole design from S5's measured cost per document, by benchmark and length band, with the 1.3 margin, passes the S8 allocation):

1. drop B4;
2. drop whole benchmarks from the bottom of this priority list (fixed before B draws any sample);
3. if the design still does not fit, shorten every remaining benchmark to the same fraction, by taking the first n documents of B's seeded order (section 1), so that the shortened set is itself a stratified random sample.

The resulting n per benchmark is written down before the runner starts, and every cut is reported. S8 aims to seal at least three benchmarks, in priority order. If these rules leave fewer than three that qualify (at least 30 documents and 100 scored decisions), the number sealed is what they give, the reason is recorded, and the shortfall is met together with B's synthetic tests.

## 3. Primary measures

For every benchmark and every arm:

1. **The official metric**, or the closest honest measure with the reason. Each benchmark has one headline metric, the one H1 tests (section 4); every other measure is reported with its interval and not tested:
   - ContraDoc: judgement accuracy (headline), with precision, recall and F1 for "contradictory". Evidence Hit Rate needs BERTScore; it is replaced by exact containment of the marked evidence sentence (whitespace-normalised) and labelled as not the official measure. It is reported on all documents and on the documents of more than one unit alone, since on a one-unit document any unit a B3 finding cites holds the evidence.
   - CUAD: AUPR and precision at 80 and 90 percent recall need a ranked score, which Shimmer's findings do not carry, and span Jaccard needs extracted spans. They are not reported. Closest honest measure (headline): macro-F1 over the two classes present and absent, computed on all (contract, category) items pooled, with precision and recall for "present" at Shimmer's single operating point. Secondary, not tested: the mean over categories of per-category macro-F1, and per-category F1 in an appendix table.
   - SciTab: macro-F1 over supports, refutes, not enough info (headline); the 3 by 3 confusion matrix per arm is reported.
   - FinDVer: accuracy over all items, ABSTAIN counted wrong (headline); coverage and accuracy on answered items beside it. Also per subset as a prespecified secondary breakdown, without tests: the stored `subset` values `ie`, `numeric` and `knowledge` are the paper's FDV-IE, FDV-MATH and FDV-KNOW (development: 250, 250 and 200 items).
   - ContractNLI: accuracy over all items, ABSTAIN counted wrong (headline; H1 tests it). F1 for Contradiction and F1 for Entailment (the paper's other measures) are reported with their intervals, without a test, and the 3 by 3 confusion matrix beside them. The official evidence measures (mean average precision and precision at 80 percent recall over spans) need ranked spans, which Shimmer's findings do not carry; they are not reported. Location recall (3.2) over Contradiction items with marked evidence spans is the closest honest measure, labelled as not official.
   - Never claim comparability with published numbers that use a different metric or split.
2. **Location recall**: over the FLAG items whose evidence is marked (location measurable), the share for which the arm emits the FLAG label and locates the evidence. Unmeasurable FLAG items are not in the denominator; their count is reported.
   - B3 and B2 locate by citing a unit: an irregular record deciding the FLAG whose `unit_id` is a unit containing the evidence, unit ids compared without regard to case.
   - B1 locates by its `evidence` field, split into sentences by the section 1 sentence rule, each whitespace-normalised. On ContraDoc (evidence marked as sentences) B1 is located if any one quoted sentence is contained in a unit that contains the evidence. On FinDVer and ContractNLI (evidence marked as parts, by index) B1 is located if any one quoted sentence is contained in the text of an evidence unit, or contains the text of an evidence unit, or is contained in the texts of the evidence units joined in document order by single spaces (D-039 item 10); a ContractNLI span is often shorter than the sentence it ends, so containment one way alone would hold B1 to a stricter test than B3. A contradiction's two sentences usually sit in different units, so the joined string is never required to fit one unit.
   - Evidence units are read on the text as kept after the cut (section 5.3): a unit cut mid-text holds only the evidence that survived, and evidence marked by index on a part cut mid-text is not evidence at all (the item counts as having its evidence beyond the cut).
   - ContraDoc: a unit counts if it contains the evidence sentence or any marked reference sentence. FinDVer: a unit counts if it holds any of the item's context indices (section 5.6). ContractNLI: a unit counts if it is made from one of the spans the item's evidence names (section 5.6).
   - A document of one unit makes every B3 FLAG on it located; the number of measurable items in one-unit documents is reported per benchmark.
   - Where the benchmark marks no evidence, where FLAG is an absence (CUAD), or where the bundle holds one unit only (SciTab), location is not measurable: the value reported is recall on FLAG, labelled so.
3. **Reason-confirmed recall**: location catches whose explanation a reviewer marks correct, for B1 and B3 alike. The reviewer sees each catch with the arm label removed, B1 and B3 catches interleaved in a seeded order, and applies one written criterion: "the explanation identifies the conflicting or deciding content and is consistent with the gold evidence". Every catch is reviewed; above 200 per arm and benchmark, a seeded random sample of 200 per arm, reported as an estimate with a document-cluster bootstrap interval. The reviewer is never the builder.
4. **False positives**:
   - Item level: gold CLEAR and predicted FLAG, per arm.
   - Unattached findings (B3 and B2): irregular records whose `source_rule_id` matches no item, and, in a bundle of more than one rule, the irregular figure-audit records tied to an item (section 5.1), counted once by record id in `review_data.json`; the figure-audit share is reported apart. Per-deliverable counts show how many of those record ids appear in each file (`review_data.json`, `review_findings.md`, `tracked_changes.docx`, `document_summary.md`). They change no label.
5. **Refusals**: items mapped from a refusal, and documents with a run failure.
6. **Which layer produced each catch**: Python (computed) or a model (judged), read from the records that decide the FLAG. A record is Python's exactly when its `written_by` field equals the string `python`, compared exactly; any other value, and a record with no `written_by` field at all, is a model's, whatever else the record carries (D-039 item 16). The stamp is the pipeline's WRITTEN-BY-A stamp, on branch `loop/s02`: the pipeline stamps a record `python` only when the post that carried it has backend `paired` or `computed` and a model id starting `python`, and `model` for everything else, including an item no envelope claims. B2 writes the same stamp on every record.

## 4. Arms, comparisons and statistics

**Arms** (S4d), applied to every benchmark and every synthetic test of B:

- **B0, trivial baseline**: "no finding" on every item, mapped by section 5.2 (every item gets CLEAR).
- **B1, bare model**: the main reading agent's model and decoding policy, with the checkpoint chosen under section 12 item 12, as recorded in VERSIONS.md (below); the fixed prompt of section 5.4, one call per item; no pipeline.
- **B2, Python only**: Shimmer's computing layer with no model call, run by `benchmark/baselines/python_only.py` on the laptop.
- **B3, full Shimmer**: the default configuration at the commit recorded in VERSIONS.md. Same bundles, same cut text.
- **B4, optional**: B3 with one alternative open-weight model family, named in VERSIONS.md before B draws any sample, only if budget remains after the core (section 2); LAW-III cross-family checking must hold.

These arm names are not the role sessions B1 and B2, nor the commits C1 to C5.

**Frozen configuration.** Before B draws the sample, the lead records in `docs/loop/VERSIONS.md`: the Shimmer commit; the SHA-256 of `config/agent_registry.json`, of `config/decoding_policy.json` and of the pipeline configuration used (backend profile, topology and review mode as resolved at that commit); B3's review mode and its paired-mode pair cap (`--pairs-per-unit`, or that none is set), each stated explicitly; the digest of every model checkpoint the pipeline loads, as pinned by the repository; and the decoding parameters of the main reading agent (the agent whose model `config/agent_registry.json` names for reading the document under review; which agent and checkpoint that is, is open item 8 of section 12). B1 uses exactly that agent's model and decoding parameters, the checkpoint chosen under section 12 item 12, and the same thinking setting if the main reading agent has one. If a loaded checkpoint digest, a hashed file or the commit differs from the record during S8, the run stops and this is logged as a deviation.

**Run order** (S8c). B3 and B1 run on the same items, in the same instance session, by the same runner process, document by document in B's order: for each document, B3 first, then B1 on each of its items in item-id order, so that any stop leaves paired data. B2 runs on the laptop. B4 runs after the core. B0 needs no run.

**Comparisons**, per benchmark, on the headline metric of section 3:

- **Primary hypothesis H1** (per benchmark): B3's headline metric differs from B1's. Two-sided, alpha 0.05. B3 is called better on a benchmark only if the 95 percent paired cluster-bootstrap interval of (B3 minus B1) lies wholly above 0, and worse only if it lies wholly below 0. Otherwise the result is "no detectable difference", reported with the observed smallest detectable difference. Every per-benchmark call is reported with its Holm-adjusted p-value beside it (the across-benchmarks family below).
- **Across benchmarks**: any statement about Shimmer across benchmarks uses Holm-adjusted primary p-values across all non-pilot benchmarks (family-wise 0.05). It reports how many benchmarks favour each arm, and no pooled metric.
- **Secondary**, Holm-adjusted within each benchmark at family-wise 0.05: the family is {B3 against B2, B3 against B0}, ordered by p-value.
- **B4**: descriptive only, B4 against B3 intervals, no test.
- **Pilots**: point estimates and intervals only. No p-values, no Holm, no wording of "better" or "worse".

**Statistics.**

- Decisions inside one document are not independent (a CUAD contract carries 41). Confidence intervals come from a paired cluster bootstrap that resamples clusters, not decisions. The cluster is the split key (section 1): the document for ContraDoc without a group, CUAD, FinDVer and ContractNLI; the near-duplicate group for ContraDoc; the paper for SciTab. Draw as many clusters as were scored, with replacement; recompute both arms' metric on all items of the drawn clusters (a cluster drawn twice counts twice); take the difference. 10,000 resamples; the 95 percent percentile interval is the 250th and the 9,751st of the 10,000 differences sorted in ascending order (1-based order statistics).
- **Seeds are derived, not chosen** (except the sampling seed, section 1): seed = int(SHA-256 hex of the UTF-8 string `<frozen preregistration SHA-256 hex>:<purpose>:<benchmark>`, base 16) mod 2^63. Purposes: `bootstrap`, `reason-review`, `text-review`. The generator is Python `random.Random(seed)`. A bootstrap resample is n calls of `randrange(n)` over the clusters sorted by their key string in code-point order; the review samples are `Random.sample` over the texts sorted by record id in code-point order. A result computed with any other seed is a deviation.
- **p-values**: for each of the shares of resampled differences at or below zero and at or above zero, the share is (k + 1) / (10,000 + 1), where k is the count; the p-value is twice the smaller share, capped at 1.
- **ABSTAIN in F1-type metrics**: in every F1, precision or recall, ABSTAIN is a prediction of a class that matches no gold label: a false negative for the item's gold class and a false positive for no class. Any precision, recall or F1 with a zero denominator is set to 0, in point estimates and in every resample alike (as scikit-learn's `zero_division=0`). F1 is computed as 2tp / (2tp + fp + fn), as scikit-learn computes it, so its denominator is zero only when tp, fp and fn are all zero. The number of zero denominators and of resamples with one is reported.
- McNemar's exact test is reported for ContraDoc (one decision per document), on correct versus not correct, ABSTAIN counted not correct, as a check; it treats documents as independent and so ignores ContraDoc's near-duplicate groups, which the bootstrap respects; it decides nothing.
- Every result states the number of documents and clusters beside the number of decisions.
- **Smallest detectable difference** (SDD): 2.80 times the bootstrap standard error of the paired difference (two-sided 5 percent, 80 percent power), reported per benchmark. Planned SDD = 2.80 x SE_dev x sqrt(n_dev_clusters / n_holdout_clusters), scaled by clusters, not documents, from S5's development variance: pending S5. The planned SDD decides nothing: it is reported beside the result, and it neither sizes the sample (section 2 does) nor changes any call. The observed SDD describes precision; it is not a power claim.
- **Sensitivity**: S-1, S-2 and S-3 (section 5.1) and S-4 (section 5.3), reported beside the primary result; FinDVer also with a cluster bootstrap by issuer, the issuer being the SEC CIK read from the filing's `url` (the number after `/edgar/data/`), recorded per filing in `parts.json` as `issuer_cik`. The ticker in `report` is not used, because one issuer can file under more than one ticker. Every development filing carries a CIK.

## 5. Mapping text and the B1 prompt

### 5.1 Output to label, all benchmarks

Records are read from `review_data.json`, under its typed-record key (PROVISIONAL, section 12 item 9), and refusal entries from `audit/pairing_map.json`; nothing else is read. Until item 9 is settled and the pipeline writes that key, the adapters refuse to label B3 and B4 (B2 writes it). Before any line is applied, of the records sharing an `item_id` only the one with the highest `revision` is kept (INFRA-037 supersession; the later one in the file on a tie; a record with no `item_id` is kept as it is). A record belongs to an item when its `source_rule_id` equals the item's rule id, compared without regard to case.

**Figure-audit records** (section 0; D-039 item 3). In a bundle with exactly one rule a figure-audit record belongs to that rule's item like any other record, because its attribution is not a choice. In a bundle with more than one rule, a figure-audit record decides no item in the primary analysis: before the lines below are applied it is set aside, and an irregular one is counted as an unattached finding (section 3.4). The reason (P1): Python computes these records on any figure, label or table of a part, whatever the rules say, and attributes a blank-cell, sum or product record among the rules paired with the unit by the words those rules' texts share with the record's labels, a tie or no shared word going to the first rule in reading order, which follows the opaque ids' hash order; a band record goes to the rule that produced it (`docs/INPUT_FORMAT.md` section 9). In a bundle of several claims that choice is not a check of the item's claim. On the development items all 3 SciTab blank-cell records and 386 of the 779 FinDVer ones (cut bundles; 197 of 1,200 uncut) went to the bundle's first rule and the rest by shared words, and SciTab's 12 band records went to the rules that produced them (private run summary `attribution_development.json`). A band record may therefore read the claim's own figures (section 12 item 3); D-039 item 3 sets it aside in a several-rule bundle all the same, and S-3 shows the other reading. The prespecified sensitivity S-3 attributes them as the record says. CUAD is not covered by this rule: see section 12 item 7, which records why and that the lead decides it; until then a CUAD item is labelled as if every bundle had one rule, and its S-3 equals its primary analysis.

An item is a claim about the whole document, judged unit by unit, so a settled answer on any unit beats a refusal on another (D-039 item 1). For each item apply the first matching line:

1. **Run failure**: every item of the document is ABSTAIN.
2. At least one record with `record_verdict` irregular that is not a refusal, on any unit (any relation: `sum_mismatch`, `product_mismatch`, `above_band`, `below_band`, `missing_field`, `date_window`, or a judged finding): the "violated" label, FLAG, except as stated for CUAD.
3. Otherwise, at least one record with `record_verdict` ok that is not a refusal, on any unit (the rule settled and satisfied there): the "holds" label, CLEAR.
4. Otherwise, at least one refusal: the "not settled" label, UNDECIDED.
5. Otherwise (silent, no record of any kind for the item's rule): the benchmark's silence label, CLEAR in the primary analysis. This is Shimmer's real answer: nothing found. For B2, a plan a model would have answered is listed as not asked (`ablation_not_asked`); that is silence, never a refusal.

Per benchmark, lines 2 to 5 give:

| Benchmark | 2 irregular | 3 ok | 4 refusal | 5 silent |
|---|---|---|---|---|
| ContraDoc | contradictory | not contradictory | ABSTAIN | not contradictory |
| CUAD | absent if any such record has relation `missing_field`, else present | present | ABSTAIN | present |
| SciTab | refutes | supports | not enough info | supports |
| FinDVer | refuted | entailed | ABSTAIN | entailed |
| ContractNLI | Contradiction | Entailment | NotMentioned | Entailment |

This order replaces the earlier "refusal wins over ok": under per-unit judging a refusal on one unit that does not settle the rule would otherwise outweigh a settled answer on the unit that does. Irregular still wins over ok and over refusal. A record whose verdict is neither ok nor irregular, and is not a refusal, is an adapter fault and matches no line (section 5.7 item 10). Prior-comparison relations (`changed_from_prior` and the others) cannot occur, since no bundle declares a prior; if one appears it is ignored and reported as an adapter fault. Irregular records tied to no item count as unattached findings (section 3.4) and change no label.

**B1.** B1 returns the benchmark label directly (section 5.4). Its undecided label maps to UNDECIDED as above. A reply that cannot be parsed, or whose label matches no label name, is ABSTAIN (S4f: one typed JSON label per item, an unparseable reply counted as an abstention). A B1 call that fails or returns nothing is an unparseable reply. **B2** output is mapped exactly as B3's.

**Prespecified sensitivity analyses**, reported beside the primary result:

- **S-1**: B1 parse failures map to CLEAR, as B3's silence does.
- **S-2**: on ContraDoc, CUAD and FinDVer, UNDECIDED from every arm maps to CLEAR.
- **S-3**: figure-audit records in a bundle of more than one rule are attributed to the rule they name, as in a one-rule bundle; every other line is unchanged. B0 and B1 are unchanged by it.
- **S-4**: section 5.3 (items whose marked evidence lies wholly in the kept text).

Per arm and benchmark the report gives the counts of silent items, UNDECIDED items, B1 parse failures, items with a figure-audit record set aside, and unattached figure-audit records.

### 5.2 Per benchmark

- **ContraDoc.** One item per document; one rule for all documents (section 5.5), so every ContraDoc bundle has one rule. FLAG = contradictory, from any irregular record under that rule, whatever its relation. CLEAR = not contradictory, from an ok record or silence. UNDECIDED = ABSTAIN.
- **CUAD.** One item per contract and category (41 per contract); one rule per category (section 5.5). FLAG = absent: absent if any irregular record for the rule has relation `missing_field`, whatever its `absence_path` (computed or judged), even if other irregular records exist. Present otherwise: an irregular record with any other relation, an `ok` record, or silence. UNDECIDED = ABSTAIN. Prespecified counts per arm: items with both `missing_field` and another irregular relation, and judged irregular findings with no relation. Gold: the CUAD text is the `context` string of the contract's one paragraph in `CUAD_v1.json`, UTF-8; present when the QA entry whose id ends in `__<category spelling>` has a non-empty `answers` list, else absent (`answers` is empty exactly when `is_impossible` is true, on every development contract). `master_clauses.csv` is not used.
- **SciTab.** One item per claim; the document is the table with its caption. FLAG = refutes. UNDECIDED = not enough info. CLEAR = supports. A run failure is ABSTAIN, never not enough info.
- **FinDVer.** One item per claim; the document is the filing. FLAG = refuted. CLEAR = entailed. UNDECIDED = ABSTAIN: the benchmark has no refusal class, so a refusal is reported as coverage and never counted as correct. Gold: `entailment_label`, a boolean, true is entailed.
- **ContractNLI.** One item per agreement and hypothesis (17 per agreement); one rule per hypothesis (section 5.5). FLAG = Contradiction: an irregular record says the agreement conflicts with the hypothesis. CLEAR = Entailment, from an ok record on any unit, or from silence, as SciTab's silence is supports. UNDECIDED = NotMentioned: no unit settled the hypothesis (no irregular and no ok record) and some unit refused (the template's UNCERTAIN), which is what NotMentioned means. A run failure is ABSTAIN, never NotMentioned. S-2 does not apply: UNDECIDED is a class of this benchmark.

### 5.3 Cut rule for long documents (all arms)

Stated once, applied by the adapter before bundling, so B0, B1, B2, B3 and B4 receive the same text. The budget is computed per document: the main reading agent's maximum context length (from its own configuration, as recorded in VERSIONS.md), minus the token count of the B1 prompt below with an empty document (the largest over the document's items, rendered from that bundle's own conventions, each item's system turn included, by `benchmark/adapters/common/prompt.py`, the renderer B1 uses), minus the main reading agent's output allowance from the pipeline configuration, minus 32. Tokens are counted with that model's own tokenizer and chat template, loaded from the pinned local checkpoint and passed to the adapter as a counter. The adapter refuses to build without these inputs unless the build is flagged as development, which `parts.json` records. B1 checks every prompt before generating: if a prompt plus the output allowance exceeds the model's context, B1 stops with a non-zero exit and generates nothing. If the document under review fits, it is not cut. Otherwise the adapter keeps whole source parts (the parts of section 5.6, before they are written as units, so whole units) from the start, in order, while they fit, and appends to the last kept part the line `[Document cut. The remaining N of M words are not shown.]` (no colon, so the line is never read as a field). N and M are words of the source parts, counted by the one word rule of section 5.6 (Words), so M equals the document's word count, the count its length band is read from. If the first part alone does not fit, it is cut at the last whitespace that fits. Reference material is never cut: no benchmark has any. B3 receives the same cut text; how the pipeline divides it across its own calls is part of B3. B4 receives the B3 text; if that does not fit B4's context, B4 is not run on that benchmark.

Items whose evidence falls beyond the cut are kept and scored in the primary analysis, since removing them would use the labels. An item's evidence lies beyond the cut when a unit that holds it in the uncut text no longer holds it in the kept text; evidence marked by index (FinDVer, ContractNLI) on a part that was cut mid-text is not evidence (D-039 item 8). `parts.json` lists those items per document before any run. Every report gives, per benchmark, the number of documents cut and the share of words removed (of all the benchmark's words, and of the words of the cut documents), and, per arm, the number of items whose evidence lies beyond the cut; it repeats the primary comparison on the uncut documents alone, and, as the prespecified sensitivity **S-4**, on the items whose marked evidence lies wholly in the kept text (an item with no marked evidence included), every arm on the same items, read from `parts.json`. The magnitude measured on the development items is in section 9.

### 5.4 The B1 prompt, word for word

Sent through the model's own chat template, decoded under the main reading agent's decoding policy, with that agent's output allowance. Text in braces is filled by `benchmark/adapters/common/prompt.py`, which `benchmark/baselines/bare_model.py` and the adapters' cut rule both use; everything else is fixed.

Revision 2 (S4 checker round 1, before any development item): the system turn's last sentence on UNCERTAIN, the reference-material slot, the conventions slot as written in the bundle, the parser's escape repair and UNCERTAIN reading, and the ContractNLI lines. Revision 3 (S4 checker round 2, D-039 item 5, before any B1 development output): the system turn invites the undecided label only on the benchmarks whose rule template asks for UNCERTAIN (SciTab, ContractNLI), so that B1 is not invited to an answer scored as wrong where B3's silence earns CLEAR; on ContraDoc, CUAD and FinDVer the undecided label stays listed and parsed but is not invited. The system turn also says, in one added sentence, that the headings and label lines of the document are markup, not content.

System turn:

```
You are reviewing a document against written rules. You will receive the document, the rules (conventions) that apply to it, any reference material, one item to decide, and the labels you may use. Use the material given; you may use general knowledge to interpret it. In the document, the heading lines (starting with #) and the lines reading Passage: part are markup that divides it into passages, not content; a backslash before a # only keeps a line from being read as a heading, and the bracketed tags after a rule's id only label the rule.

Work through the item first: quote the passages of the document that bear on it, and do any calculation step by step. Then decide which label applies.

End your reply with one line holding one JSON object, and write nothing after it:
{"item_id": "<the item id>", "evidence": "<the exact sentence or sentences of the document your decision rests on, copied from it>", "reason": "<one or two sentences naming the part of the material your decision rests on>", "label": "<one label name from the list>"}

Copy the label name exactly as it is written before the colon in its line.{undecided invitation} A rule that says to emit UNCERTAIN means: use the undecided label.
```

`{undecided invitation}` is a space followed by the sentence below on a benchmark marked "Invited: yes", and nothing on the others. Undecided invitation: `If the material does not let you decide, use the undecided label named below the list.`

User turn:

```
DOCUMENT
{document, after the cut rule, as it stands in the bundle}

CONVENTIONS
{every convention in the bundle as written in it, one per line: its heading without the leading # characters, a colon, a space, then its text}

REFERENCE MATERIAL
{the bundle's reference material: for each grounding file, the earlier version included, in file-name order, its file name on one line and its text below, the files separated by a blank line; the single line None. when there is none}

ITEM
Item id: {opaque item id}
Rule id: {the item's rule id}
{the item's question line, below}

LABELS
{the benchmark's label lines, below}
The undecided label is: {the benchmark's undecided label name}
```

Question lines and label lines:

- ContraDoc. Question: `Decide whether the document contradicts itself: whether two statements in it cannot both be true.` Labels: `contradictory: two statements in the document cannot both be true.` / `not_contradictory: no two statements in the document conflict.` / `undecided: the material does not let you decide.` Undecided label: `undecided`. Invited: no.
- CUAD. Question: `Decide whether the document contains a clause of the category this rule describes.` Labels: `present: the document contains such a clause.` / `absent: the document contains no such clause.` / `undecided: the material does not let you decide.` Undecided label: `undecided`. Invited: no.
- SciTab. Question: `Decide whether the table and its caption support the claim in this rule.` Labels: `supports: the table and caption show the claim is true.` / `refutes: the table and caption show the claim is false.` / `not enough info: the table and caption do not settle the claim.` Undecided label: `not enough info`. Invited: yes.
- FinDVer. Question: `Decide whether the filing supports the claim in this rule.` Labels: `entailed: the filing shows the claim is true.` / `refuted: the filing shows the claim is false.` / `undecided: the material does not let you decide.` Undecided label: `undecided`. Invited: no.
- ContractNLI. Question: `Decide whether the agreement supports, contradicts or does not settle the hypothesis in this rule.` Labels: `entailment: the agreement shows the hypothesis is true.` / `contradiction: the agreement shows the hypothesis is false.` / `not mentioned: the agreement does not settle the hypothesis.` Undecided label: `not mentioned`. Invited: yes.

Each label line is one line of the LABELS block. The bare model gets the same document, conventions and reference material as Shimmer, every label with its meaning, room to work, and, where the rules ask for it, Shimmer's abstention option.

**The parser.** Remove every line that is only a code fence (three backticks, with or without a language name). Take the last balanced `{...}` in the reply and parse it as JSON. If that fails, double every backslash that does not begin a valid JSON escape (a valid pair such as `\\` or `\"` is left as it is) and parse once more; a copied `\|`, `\#` or LaTeX command in `evidence` or `reason` must not cost the label. If that fails too, the reply is unparseable. Read `label`; lowercase it, trim it, remove a trailing `(undecided)` and anything from the first `:` on, trim again, and replace `_` with a space. A label that then reads `uncertain` is the undecided label. Compare it with the label names treated the same way; a match gives that label, no match makes the reply unparseable. Each label file records whether the repair was used, and the count is reported. An `item_id` that differs from the item's id is ignored. `evidence` and `reason` are kept for sections 3.2 and 3.3 and never change the label. The parse rate per benchmark is reported.

**Length.** Each label file records the number of tokens the reply used and whether it reached the output allowance (a reply that reaches it may be cut short); the count of such replies is reported per benchmark (D-039 item 11).

**Development check.** In S5, B1 is run on the development items. The B1 prompt and parser may be revised before freeze under the same rules as B3: development items only, every revision logged with its development numbers. A benchmark whose development parse rate is below 95 percent has its prompt or parser revised before the freeze (`b1_summary.json` flags it). The frozen prompt is the last revision.

### 5.5 Rule templates, word for word

Each bundle has one conventions file, `conventions/rules.md`. Its first line is `# Review rules`, then one blank line, then for each rule, in rule-id order: the rule heading, a blank line, the rule text as one paragraph, a blank line. The heading is `## <rule id> <name> [required] [conformance]`. The operator's own id on the heading must start with `CONV-` (`docs/INPUT_FORMAT.md` section 3), so the short rule ids below are written on the heading in that form. In every template, `{claim}` is the claim text with each run of whitespace replaced by one space and nothing else changed; it is the only slot except CUAD's `{name}` and `{description}`. No rule carries a `[scope: ...]`, `[requires: ...]` or `[unless: ...]` directive; each rule pairs with every unit through the label `Passage` (section 5.6).

- **ContraDoc.** Rule id `CONV-CDOC-01`, name `Consistency`. Text: `No passage of the document may contain a statement that cannot be true together with another statement in the same passage or in another passage of the document.`
- **CUAD.** One rule per row of the table below; rule id `CONV-CUAD-NN` for row `cuad-NN`, name `Category`. Text: `The document must contain, in at least one passage, a clause of this category: {name}. {description}`
- **SciTab.** One rule per claim; rule id `CONV-` followed by the opaque item id, name `Claim`. Text: `Claim about the table in this passage: {claim} The claim must agree with the table and its caption. If the table and caption do not settle the claim, emit UNCERTAIN.`
- **FinDVer.** One rule per claim; rule id `CONV-` followed by the opaque item id, name `Claim`. Text: `Claim about the filing: {claim} The claim must agree with the passages of the filing.`
- **ContractNLI.** One rule per hypothesis; rule id `CONV-CNLI-` followed by the hypothesis key, upper-cased, every run of characters other than letters and digits written as one `-` (the release's keys are `nda-1` to `nda-20`, 17 of them, so the ids read `CONV-CNLI-NDA-1`), name `Hypothesis`. Text: `Hypothesis about the agreement: {hypothesis} The hypothesis must agree with the passages of the agreement. If the agreement does not settle the hypothesis, emit UNCERTAIN.` `{hypothesis}` is the hypothesis text with each run of whitespace replaced by one space, the only slot.

The SciTab and ContractNLI templates ask for UNCERTAIN, Shimmer's refusal channel, which maps to their undecided class. B1 reads the same rule text; its system turn says that a rule asking for UNCERTAIN means the undecided label, invites the undecided label on these two benchmarks only, and its parser reads `uncertain` as that label (section 5.4, revisions 2 and 3).

CUAD categories. Names are copied from the CUAD paper's category list (arXiv 2103.06268, Tables 4 and 5), in its order. For every row the description is: as in the category list distributed with CUAD v1 (its `CUAD_v1_README.txt`), copied verbatim by the adapter at freeze (PROVISIONAL until then). In the template, `{description}` is that text with each run of whitespace replaced by one space; if a row has none, `{description}` is empty and the template uses the name alone. The data's QA ids spell 15 categories differently from the names here (confirmed on every development contract, and the same 41 spellings over the whole file, `external/cuad/MANIFEST.json`); the adapter matches a QA entry by the data's own spelling, and the name here stays in the rule text: cuad-07 `Notice Period To Terminate Renewal`, cuad-12 `No-Solicit Of Customers`, cuad-14 `No-Solicit Of Employees`, cuad-16 `Termination For Convenience`, cuad-17 `Rofr/Rofo/Rofn`, cuad-18 `Change Of Control`, cuad-21 `Price Restrictions`, cuad-24 `Ip Ownership Assignment`, cuad-25 `Joint Ip Ownership`, cuad-28 `Affiliate License-Licensor`, cuad-29 `Affiliate License-Licensee`, cuad-30 `Unlimited/All-You-Can-Eat-License`, cuad-31 `Irrevocable Or Perpetual License`, cuad-36 `Cap On Liability`, cuad-40 `Covenant Not To Sue`.

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

`k` counts the parts from 00001 in order (the heading may carry digits; headings are not values). The label line `Passage: part` holds letters only, because every digit in a value is read as a figure (`docs/INPUT_FORMAT.md` section 2; `P-00001` would be the figure -1, which enters products and ratios). It gives every unit the field the rule templates name, so every unit pairs with every rule and no unit is left with no rule (`docs/INPUT_FORMAT.md` sections 4 and 5). A source line that begins with `#` is written with a backslash before the `#`, so it never starts a unit. The adapter records, per document, the unit id of each part and the source span or index it came from. Offsets (character spans) are code-point indices into the decoded text. The parts:

- **ContraDoc**: the `text` field verbatim, one part per blank-line paragraph. No sentence splitter is used.
- **CUAD**: the contract's `context` string, one part per blank-line paragraph.
- **SciTab**: one part only: the caption line (`table_caption`), a blank line, then the table as a pipe-delimited Markdown table, header row first (`table_column_names`), then the separator row, then body rows (`table_content_values`), each cell's text as given with `|` written as `\|`.
- **FinDVer**: the filing `financial_reports/<report>` is an object whose `context` lists its entries `{id, context, type}` in id order from 0; each entry is one part, in index order, so the part at context index k is part k + 1. An entry of `type` `table` keeps its string as given (pipe rows between lines of text), and in each run of pipe rows a separator row as wide as the first row is written after it, unless one is already there (Shimmer reads a table's header only when a separator row follows it); the release almost never has one (3 of the 10,991 development table entries).
- **ContractNLI**: the agreement's `text`, one part per span of the agreement's own `spans` list (the release's segmentation of every agreement into character ranges), in text order. Text the spans leave out, before, between or after them, is not dropped: each such stretch is a part of its own. A span or stretch of whitespace only makes no part. Spans out of order, overlapping or outside the text, or a missing span list, make the build refuse. An item's evidence (indices into that `spans` list) marks the part made from each span it names; an index naming a whitespace-only span marks none, and an index naming no span makes the build refuse. **Fallback, applied only if section 2's cost trigger fires**: the same pieces (spans and the stretches between them, whitespace-only ones dropped) are joined in order into parts, each closed as soon as the text from its first piece's start to its last piece's end holds at least 100 words; the last part may be shorter. A merged part counts as evidence if it holds any span the item names (an index naming a whitespace-only span still marks none). `parts.json` records which rule built the document (`part_rule`) and the spans each merged part holds.

**Words.** One rule counts words everywhere: the length band (section 1), N and M in the cut line (section 5.3) and every count in `parts.json`. A document's words are the sum of the words of its source parts above, each counted on the part's source text as the release stores it, before bundling and before the cut. A text's words are the tokens Python's `str.split()` with no argument gives, line by line, except that inside table text a token made only of the characters `-`, `:` and `|` is not a word. Table text is SciTab's column names and cell values (each cell counted on its own) and every pipe row (a line whose first non-blank character is `|`) of a part's source text; a caption and the lines of text around a FinDVer table are not table text, so every token there is a word. So a table's words are its cell words, and the separator row the adapter writes is never counted. A token that a part boundary splits counts once in each part.

### 5.7 Readings fixed while writing the adapters (on synthetic items, then confirmed on the development items)

The adapters under `benchmark/adapters/` were first written and checked by `scripts/adapter_checks.py` on hand-written synthetic items in each benchmark's documented schema; in S4c item 4 they were run on the development items B-dev passed on, every named constant was checked against them, and the faults found were fixed (D-038; S4 checker round 2, D-039). The fixtures stay hand-written synthetic items in the release's own schema (CUAD's 41 QA entries per contract expanded by a tracked script), and the counts these readings rest on are held by the checks' development group, which reads the development items where they are present and is skipped where they are not. Where this text left a choice, the adapters made the one below; C implements the same from this text.

1. A source line whose first non-blank character is `#` is written with a backslash before that `#`.
2. Part text: a carriage return before a line feed is dropped; lines are split at line feeds only; leading and trailing blank lines of a part are dropped.
3. A document with no text is skipped when bundles are built: it is listed in the build summary and under `skipped` in `parts.json`, and the other documents are built.
4. `{claim}`: each run of whitespace becomes one space; nothing is trimmed.
5. CUAD with an empty description: the rule text ends `... a clause of this category: <name>.`, the name followed by the template's full stop, with no trailing space.
6. SciTab: a line break inside a caption or a cell is written as a space. Where the claims of one table store different cells (one development table, two of its eight claims; three tables over the whole file), the document is the table as its first claim in file order stores it, and `parts.json` lists the other claims under `table_variants`; claims of one table naming different papers are refused.
7. The cut rule counts tokens over the written document file, headings, label lines and the cut line included; N and M in the cut line, like the length band, are words by the one rule of section 5.6 (Words), so M equals the word count the band is read from.
8. ContraDoc grouping (section 1): the share is the distinct shared sentences over the distinct sentences of the document that has fewer; the smallest unique id is numeric order when every id is an integer, else string order; groups are computed once over the whole input and read from the frozen split file by every build. The adapter reads both its own `split --out` file (`documents`) and B-dev's (`assignments`), and refuses a side that is not the hash rule on its group key. The gold is the container (`pos` contradictory, `neg` not contradictory); no record has a label field. `evidence` is one string; `ref sentences` is a string, a list of strings, or absent.
9. CUAD: an irregular record with another relation together with a refusal gives present (line 2 of section 5.1 matches first); a `missing_field` record carrying the UNCERTAIN marker is a refusal, not an absence.
10. A record whose verdict is neither `ok` nor `irregular`, and is not a refusal, matches no line of section 5.1. An adapter fault is recorded whenever such a record exists; the item's label comes from its other records by section 5.1, and is CLEAR when it has none.
11. A run output with no typed-record key, or whose typed-record value is not a list of objects, is not a run failure: its items are silent, an adapter fault is recorded, and the labelling step exits non-zero so the fault cannot pass unnoticed. An unreadable `review_data.json` is a run failure (section 0).
12. Location: see section 3.2 (unit ids compared without regard to case; only the irregular records that decide the FLAG count; B1 by any one quoted sentence, by containment either way or in the joined evidence units on FinDVer and ContractNLI). For ContraDoc the evidence measure reads B1's `evidence` string or the text of a unit B3 cites.
13. `items.json` carries the source ids beside the opaque ones, and `parts.json` holds them too (section 0); no arm's model sees either file.
14. The catch layer is reported as computed, judged, or both, read as section 3.6 says (`written_by` equal to `python`, exactly; anything else a model's).
15. Each bundle's `answer_key.json` (required by the input format) holds empty `planted`, `clean` and `twin_of`, and the gold labels under `items`, with each item's evidence units, whether its evidence lies beyond the cut, and the number of units of its document.
16. Supersession (section 5.1): of the typed records sharing an `item_id`, only the highest `revision` is kept before any line applies.
17. A gold item of a labelled document that has no label is an error at scoring, never skipped; a document with no label at all is outside the scored prefix (section 7). S-4 leaves out only the items `parts.json` lists.
18. ContractNLI: irregular is Contradiction, then ok is Entailment, then refusal is NotMentioned, and silence is Entailment (sections 5.1, 5.2), so B0 labels every item Entailment.
19. ContractNLI parts (section 5.6): `parts.json` records per part the span index it was made from (none for a stretch the spans leave out) with its character range, and per agreement the number of spans and the indices of the whitespace-only spans; under the fallback, the spans each part holds.
20. A bundle's rule count, for section 5.1's figure-audit rule, is the number of distinct rule ids among its items (one rule per item, section 5.5).
21. FinDVer, a development build that declares no side: a filing's side is the official split its items name when they all name one; ContractNLI's is the side of the frozen file the input matches. The adapter holds `dev.json`'s SHA-256 from the B-dev manifest; it holds no holdout file's hash.
22. A FinDVer table entry's separator row is recognised as a pipe row whose cells are each made of `-` with an optional `:` at either end.
23. The `bands` command reads a whole input with no side check and no build, and gives per document the opaque and source ids, words, band and items, and per band the documents, items and median words; it leaves out excluded documents and documents with no text.
24. The checks build their synthetic fixtures, which mix sides on purpose, through a keyword of the build function that is not an option of the command line; such a build is recorded in `parts.json` (`synthetic_fixture_build`). Every other build follows section 1 exactly.

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
- Coverage, abstentions, refusals, silent items, B1 parse failures (and B1 replies that reached the output allowance) and run failures per arm, with S-1, S-2 and S-3.
- Figure-audit records set aside and counted as unattached per arm (section 5.1), and the demonstration documents excluded (section 1).
- Documents cut, the share of words removed, the items whose evidence lies beyond the cut per arm, the uncut-only comparison and S-4.
- For SciTab and FinDVer, the share of documents carrying more than one claim, and the primary comparison repeated on single-claim documents only. Every claim of a table or filing is a rule in the same bundle, and B1's prompt shows them all, so a refuted claim built by editing a supported sibling may be told apart by the pair; the single-claim analysis shows how much that is worth.
- The smallest detectable difference per benchmark, planned and observed.
- C0's mapping agreement counts, the number of C0 runs, and any benchmark dropped under the C0 rule (section 12).
- The model-text review verdicts.
- Every deviation from this preregistration, from the deviation log.
- Cost and time per document and per scored decision, per arm, with the number of model calls and tokens.
- S8d's lines on every result: the role-separation statement "Role separation: separate sessions and folders on one Windows account; not enforced by the operating system (Annex A, 11.2 options not in place; Annex B.11)", and the label "role separation not enforced by the operating system"; the contamination note of section 8; the limitation line (B's synthetic tests and the builder are the same model family and may share blind spots); the ordering line (the order of preregistration, freeze and sampling is attested only by local records); the label "pilot" where it applies; and the number of documents beside the number of decisions.

## 8. Contamination note

The models may have seen these public datasets, or their source documents, during training. Every report says so. Specifically: FinDVer's test labels have been public since 2026-07-14, so its contamination guard is gone; ContraDoc is built on public web text (CNN/DailyMail, NarrativeQA, WikiText); CUAD's contracts and annotations are public and widely circulated; SciTab's tables come from public arXiv papers and its claims are public, and the tables its paper prints as in-context examples are excluded from the holdout pool (section 1); ContractNLI's agreements come from EDGAR and public PDFs, and LegalBench's ContractNLI tasks are drawn from ContractNLI's test set, so a model that has seen LegalBench has seen ContractNLI test items, and the two are not independent.

The tuned adapters this repository trains (under `tuning/`) were not trained on any of these five sources: a search of every file under `tuning/` for the five benchmarks' names and file names finds none. The base models can still have seen them. The pinned local models (`config/local_models.json`, `config/final_models.json`) are from the Qwen2.5-7B-Instruct release (September 2024) and the Phi-3.5-mini-instruct release (August 2024). ContractNLI (2021), CUAD v1 (2021), ContraDoc (2023) and SciTab (2023) were public before both, so the base models may have seen them. FinDVer's paper appeared in late 2024, after both model releases, and its test labels in 2026; whether its repository or development split was public before the models' training cut-off is not known here, so no claim is made that FinDVer is unseen. The model ids and their release dates are recorded in VERSIONS.md at the freeze beside these dataset dates.

## 9. Limitations, stated in advance

- B's synthetic tests and the builder come from the same model family, so they may share blind spots.
- The order of preregistration, freeze, sampling and run is attested only by local records.
- The adapters were written on synthetic items and then corrected on the development items; a release fact no development item shows (SciTab's `not enough info` spelling: no development claim carries that class) is unconfirmed, and the UNDECIDED path cannot be checked on SciTab development items.
- Location recall is coarse for B3 on one-unit documents (any FLAG there is located): 123 of the 184 ContraDoc development documents are one part (64 of the 103 contradictory ones), and every contradictory development document has its evidence sentence in a single part, so ContraDoc's evidence containment is also reported on documents of more than one unit (section 3.1). Section 3.2 reports the one-unit count. B1 is held to quoting a sentence that meets an evidence unit; on FinDVer and ContractNLI containment either way is enough (section 3.2).
- Per-unit judging (D-039 item 1): a document judged unit by unit gives many records per item. A settled answer on any unit decides, so a single wrong ok on one of many units can turn a NotMentioned (or a refusal) into Entailment; ContractNLI agreements have about 83 units each on the development items. The share of items with both a refusal and an ok record is reported per arm.
- Figure-audit records (D-039 item 3): in a bundle of more than one rule they are set aside in the primary analysis. On the development items every B2 FLAG on SciTab and FinDVer came from such a record (`SELECTION.md`, Dry-run results), so B2's primary analysis there is close to B0's; S-3 shows the other reading. CUAD is not covered by that rule until the lead decides it (section 12 item 7).
- ContractNLI's NotMentioned class is reached only when no unit settles the hypothesis and some unit refuses; silence counts as Entailment, so a run that says little about a hypothesis scores as Entailment.
- CUAD's official ranked metrics cannot be produced; its headline measure is not comparable with published numbers.
- The cut rule removes text equally for every arm, which understates any arm built to read long documents; FinDVer filings are the most affected. Measured on the development items with a stand-in counter (one token per word, a 32,768-token context and a 2,048-token output allowance; the real tokenizer is pinned in S5): FinDVer, 158 of the 255 filings cut, 28.6 percent of all their words removed (35.1 percent of the words of the cut filings), and 159 of the 700 items (23 percent) with their evidence beyond the cut; CUAD, 3 of 96 contracts cut (6.3 percent of all words, 34.8 percent of the cut contracts' words; CUAD marks no evidence); ContraDoc, SciTab and ContractNLI, nothing cut (private run summaries `findver_summary.json`, `cuad_summary.json`, `contradoc_summary.json`, `scitab_summary.json`, `contractnli_summary.json`). Silence earns B3 CLEAR on such items, so S-4 is reported beside the primary result (section 5.3).
- B1 decides one item per call and sees each item alone; B3 reviews the whole document in one run. This difference is part of what the primary comparison measures.
- Mapping "no finding" to the CLEAR label credits silence; B0 shows how much that alone earns, and S-1 shows how much it changes the B1 comparison.
- FinDVer has no refusal class, so a correct refusal scores as wrong.
- FinDVer's size is reported differently by its own sources; the counts used are those of the pinned files.
- The rule templates are fixed text; a different wording could change every arm's result.
- B1's checkpoint (section 12 item 12) is chosen on development items by the stronger of two baselines, never by B3's result.
- B-dev's report (`external/_bdev/BDEV_REPORT.json`, on the lead's disk, never committed) names the four holdout SciTab tables its paper prints, with their ids and claim counts but no content; that holdout metadata reached the lead (incident INC-010). Those tables are excluded from the holdout pool (section 1), so the exposure has no effect on any sealed result.

## 10. Hash records by B and C

When B and C start (B-dev, C0 and the S8b sessions), each copies this preregistration's current SHA-256 into a dated file in its own folder. That record sits outside the builder's write access.

## 11. Checker attacks

A `loop-checker` attacks this draft, including the B1 prompt as a possible straw man, before S4 closes. A fresh `loop-checker` attacks the completed version at the end of S5, before it is frozen.

## 12. The C0 rule and items open before freeze

**C0.** C0 uses development items only; no holdout item enters it. The preregistration is frozen only after a C0 run reports full agreement, on every benchmark that stays in the design, between C's labels (from this text) and the adapters' labels. If any item differs, the lead settles it in this text or in the adapter, and C0 runs again. At most three C0 runs. If items still differ after the third, the benchmarks they belong to are dropped from the S8 priority list and the sample sizes are refilled by section 2, before B draws any sample.

**Open before freeze**, each settled on development items in S5 and written here, or the benchmark it concerns is dropped before B draws any sample:

1. The exact field names of a refusal and of a run's final status, from `docs/OUTPUT_FORMAT.md`.
2. Per-unit records, on all five benchmarks (D-039 item 1). Section 5.1 now combines one item's per-unit records by a fixed order (irregular, then ok, then refusal, then silence). Settle under the frozen review mode: whether B3 returns one document-level judgement or one record per unit for each benchmark's rules (ContraDoc's one rule, a CUAD category, a SciTab or FinDVer claim, a ContractNLI hypothesis), and count, per benchmark and arm, the items with both a refusal and an ok or silent unit, the items with both an irregular and an ok record, and the items decided by an ok record on one unit against refusals on others; report them, and change the order only by a deviation entered before C0.
3. Whether claim figures in a SciTab or FinDVer rule are read as a band (`docs/INPUT_FORMAT.md` section 7). If they are, the count of items whose FLAG came from a band relation is reported per arm.
4. Settled on synthetic bundles and confirmed on the development items: Shimmer's own unit splitter (`pairing_map.split_units`) gives the adapters' unit ids (on every synthetic bundle and on all 61 ContractNLI development agreements, 16 of them above 99 parts), keeps an escaped `\#` line inside its unit, and gives `u100-p-00100` above 99. Held by `scripts/adapter_checks.py` (structure group).
5. The release facts no development item could show, each kept in a marked constant at the top of its adapter: SciTab's spelling of `not enough info` (no development claim carries that class) and CUAD's category descriptions (empty until copied from `CUAD_v1_README.txt` at freeze, section 5.5). Everything else named in sections 1, 5.2, 5.5 and 5.6 was confirmed on the development items (`benchmark/adapters/README.md` lists what was confirmed per adapter).
6. The SciTab demonstration tables: role B identifies by caption the tables the paper prints and passes their ids before sampling (section 1); the fifth table and the 25 claims cannot be identified from the paper. The FinDVer test labels are present at the pinned commit (settled).
7. Computed findings on source text (the figure audit). Settled for four benchmarks by D-039 item 3 (section 5.1): figure-audit records decide an item only in a one-rule bundle, and in a several-rule bundle count as unattached, with S-3 attributing them. **Not applied to CUAD, pending the lead**: every CUAD bundle has 41 rules, and CUAD's FLAG (absent) is read from relation `missing_field` alone (section 5.2), so applying the rule to CUAD would make absent unreachable in CUAD's primary analysis, for a judged absence a model returns for the rule it was asked about as much as for a blank-cell record the figure audit attributes by shared words or to the first rule. Until the lead decides, CUAD labels every record as in a one-rule bundle (its S-3 equals its primary analysis), and the count of CUAD `missing_field` records by layer (computed, judged) is reported per arm. Dates and identifiers with digits read as figures with no measure (open item 16 of `docs/fix/OPEN_ITEMS.md` on branch `loop/s03`, defect 2) are part of the figure audit. Measured on the development items (illustrative; `SELECTION.md`, Dry-run results): every B2 flag on SciTab and FinDVer came from the figure audit, and every such record sat in a bundle of more than one rule (attributed as section 5.1 describes). Under the rule above B2 now flags no SciTab or FinDVer development item in the primary analysis, and under S-3 the 3 SciTab claims and the 9 FinDVer claims (8 filings, cut bundles; 11 uncut) it flagged before; the records behind them, 12 `below_band` and 3 `missing_field` on SciTab and 779 `missing_field` records from blank table cells on the 8 cut FinDVer filings (1,200 uncut), are counted as unattached instead (private run summaries `scitab_summary.json`, `findver_summary.json`).
8. The main reading agent: which agent, model and output allowance B1 uses and the cut rule counts with. `bare_model.py` takes the agent as an argument; PROCESSOR is its placeholder default until this item is settled, and each B1 summary records whether the placeholder was used. The agent registry names a cloud model for the reading agent while the local profile and the final-model configuration name local checkpoints, and the output allowance differs by path (2048 by default, other bounds on the optimized path). One model id, checkpoint digest and output allowance are pinned in VERSIONS.md before sampling (section 4), and B1 is passed that allowance explicitly.
9. Where the typed records live in a run's output. `review_data.json` holds amendments without each finding's `source_rule_id` and `record_verdict`; section 5.1 needs them. `docs/OUTPUT_FORMAT.md` names the key that carries the typed records (B2 writes them under `findings`), and the pipeline and B2 agree on it, before C0.
10. Claim rules may not pair through `Passage` alone, on any of the five benchmarks: Shimmer reads table headers, caption lines (such as `Table 1: ...`) and any `Label: value` line of a part as field labels, so a rule using those words names them and pairs only with the units carrying them (section 5.5 says every rule pairs with every unit). Settle on development items, per benchmark: count the items whose rule pairs with fewer units than the document has, and either keep the behaviour (it is Shimmer's) or change the template.
11. Refusals in the pairing map name the registry id (`CONV-001`), not the operator's own id, so a pairing-map refusal never matches an item's rule today. Settle before C0: map the registry id to the operator's id from the run's own convention registry, or rely only on UNCERTAIN markers on records.
12. B1 with the base or the tuned checkpoint. In final mode the main reading agent runs the Producer adapter (checkpoint 168), evaluated only on the validated two-turn extraction shape (CLAUDE.md, EXTRACTION-A); B1's free-form prompt is outside that shape, which could make B1 a straw man (section 11). Settled in S5 on development items by a rule written now (D-039 item 4): B1 uses whichever checkpoint, base or tuned, has the higher development parse rate pooled over the benchmarks in the design; on a tie, the one with the higher pooled headline metric on the development items (the mean over benchmarks of each benchmark's headline); that is, the stronger baseline. B3's development results play no part. Both checkpoints' parse rates and headline metrics, and the choice, are recorded in VERSIONS.md before freeze.
