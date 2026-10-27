# Benchmark adapters

Adapters for the five external benchmarks of `docs/benchmarks/SELECTION.md`: ContraDoc, CUAD v1, SciTab, FinDVer and ContractNLI (added by the operator's decision D-S3). Each one turns benchmark items into test bundles in the input format `input-format-v1-draft` (`docs/INPUT_FORMAT.md`, on branch `loop/s03`), turns a run's output into labels, and scores labels against gold.

What they implement, from `docs/benchmarks/PREREGISTRATION.md`:

- section 0: opaque ids, the item table and the parts record;
- section 1: the hash split rule and the official splits, enforced at build (ContractNLI by its frozen files); the exclusion of demonstration documents; the length band of every document (`bands`);
- section 3: the official metric or the closest honest measure (each benchmark's headline named in its score), location recall, false positives (item level and unattached), refusals, and the catch layer;
- section 4: ABSTAIN and zero division in every F1-type measure;
- section 5.1 and 5.2: the output-to-label mapping (a settled answer on any unit beats a refusal; a figure-audit record is a figure-audit relation stamped `written_by: python`, one definition for all five benchmarks: a band record decides its own rule's item, Python's `missing_field`, `sum_mismatch` and `product_mismatch` records decide only in a one-rule bundle, and a model-written record always decides its rule's item), with S-1, S-2, S-3 and S-5 (the earlier order, a refusal before an ok record);
- section 5.3: the cut rule, with a per-document budget, and S-4;
- sections 5.5 and 5.6: the rule templates and the document text and units, with ContractNLI's merged-span fallback.

What they do not implement is listed at the end.

## Written on synthetic items, confirmed on development items

The adapters were first written from the schemas documented in `SELECTION.md` and the preregistration, with no benchmark data opened (hard limit H17), and checked on synthetic items in those schemas.

In loop stage S4c item 4 they were run on the development items role B's B-dev session passed on (development side only, opened under H17's exception for development items, decision D-032); nothing else of any release was opened. Each named constant was checked against them, every one the data confirmed is marked so in a comment (no document text is quoted), and the faults the data showed were fixed (D-038; per adapter below). The fixtures were rewritten in the release's own schema and stay hand-written synthetic items: no real item is copied into them, and no real party name or listed ticker appears in them. The checks' `development` group, reading the development items where they are present (`external/`, gitignored) and skipped where they are not, holds the counts listed in section 5.7 of the preregistration (documents and items per adapter, ContractNLI's parts and spans, ContraDoc's grouping, one-part documents and evidence sentences, Shimmer's splitter and the short evidence parts on the 61 ContractNLI agreements, FinDVer's table entries with a separator row, its CIKs and its development bands); the other development figures are read from the private run summaries the preregistration names, not held by a check.

- The items are hand-written.
- CUAD's 41 QA entries per contract are expanded by the tracked script `cuad/fixtures/make_synthetic_items.py` from hand-written contract texts and answer choices. The script reproduces the fixture byte for byte.
- FinDVer's fixture is laid out as the release is: `findver/fixtures/data/testmini.json` and the filings under `findver/fixtures/financial_reports/`.

Where a field name or a stored value could not be confirmed on development items, it stays a named constant marked PROVISIONAL, kept in one block at the top of the adapter (section 12 of the preregistration, item 5). Nothing is inferred from data at run time.

## Layout

```
benchmark/adapters/
  common/            shared code, standard library only
    ids.py           opaque ids (section 0), the hash split rule (section 1), length bands
    bundle.py        the one bundle writer: everything the input format decides lives here
    prompt.py        the one renderer of the B1 prompt (section 5.4), used by bare_model.py
                     and by the cut budget
    cut.py           the one implementation of the cut rule (section 5.3)
    mapping.py       run output to label (5.1, 5.2), B0, B1, S-1, S-2; run-output names
    metrics.py       section 3 measures, with ABSTAIN and zero division as section 4 says
    cli.py           the commands below
  contradoc/  cuad/  scitab/  findver/  contractnli/      adapter.py and fixtures/
  <name>/fixtures/synthetic_items.json   synthetic items in the release's schema (FinDVer:
                                         fixtures/data/testmini.json and fixtures/financial_reports/)
  <name>/fixtures/mapping_cases.json     synthetic run outputs with the expected labels
```

The checks are in `scripts/adapter_checks.py`; the verify gate runs them through `check()` (gate check 283 for the adapters; 282 runs `scripts/baseline_checks.py` for the baseline arms). `py -3.12 -X utf8 scripts/adapter_checks.py [group ...] [--external <folder>]` runs them by hand. They read only these fixtures (and, in the `development` group, the development items), work in temporary folders, and skip when `benchmark/adapters/` is absent.

## Portability

Standard library only. Nothing imports the repository's `scripts/`. Copy `benchmark/adapters/` anywhere, with `benchmark/baselines/b1_prompt.json` beside it (as `<copy>/baselines/b1_prompt.json`) or a `--b1-prompt` path, and run, for example, `py -3.12 -I <copy>/adapters/contradoc/adapter.py ...`. The `cli` check group does exactly that: it copies the tree to a temporary folder and runs, in a fresh `-I` interpreter, FinDVer, SciTab (with `--exclude`), CUAD and ContractNLI (holdout, with `--frozen-sha256` and `--parts merged`) builds, and `bands` and `split`.

## Commands

Every adapter has the same five commands:

```
py -3.12 benchmark/adapters/<name>/adapter.py build --input <benchmark file> --out <empty folder> --side development|holdout --max-context N --output-allowance N --token-counter <file.py> [--b1-prompt F] [--assignment F] [--testmini F] [--exclude F] [--reports D] [--frozen-sha256 H] [--parts span|merged]
py -3.12 benchmark/adapters/<name>/adapter.py build --input <file> --out <folder> --development [--side holdout]     (development work only)
py -3.12 benchmark/adapters/<name>/adapter.py split --input <benchmark file> [--out <file>] [--exclude F]
py -3.12 benchmark/adapters/<name>/adapter.py bands --input <benchmark file> [--out <file>] [--exclude F] [--testmini F] [--assignment F] [--reports D] [--frozen-sha256 H]
py -3.12 benchmark/adapters/<name>/adapter.py label --items <items.json> --arm B0|B1|B2|B3|B4 [--runs <folder>] --out <labels.json>
py -3.12 benchmark/adapters/<name>/adapter.py score --labels <labels.json> --bundles <build folder> --out <metrics.json>
```

`--reports` is FinDVer's own option; `--frozen-sha256` and `--parts` are ContractNLI's. An option an adapter does not take is refused.

- **build** writes one bundle per document, named by its opaque document id, plus `items.json` and `parts.json` beside the bundles. The output is byte-identical for the same input.
  - Inside each bundle: `context/<id>.md`, `context/_review_targets.json`, `conventions/rules.md` and `answer_key.json`.
  - `items.json` is the item table: `item_id`, `document_id`, `rule_id`, `benchmark`, and the source item and document ids. It holds no gold.
  - `parts.json` gives, per document:
    - the unit id and source words of every part, with its source span or context index;
    - the split key, side and cluster;
    - the word count and length band;
    - the cut record: budget, prompt overhead, words removed.
    It also gives the build's declared side, the SHA-256 of the split and testmini files it read, and the documents skipped (no text). It holds source ids and no gold; no arm's model sees it.
  - `answer_key.json` holds the input format's required fields, with empty `planted`, `clean` and `twin_of`, and the gold of every item: label, evidence units, and whether location is measurable. The repository's `.gitignore` ignores every file named `*key*`, so built bundles are never committed by accident. They are build output.
- **Sides.** Every build declares its side; a document on the other side makes the whole build refuse, writing nothing. A `--development` build that declares no side refuses a holdout document unless `--side holdout` is also given.
  - ContraDoc reads groups and sides from the frozen file written once on the whole input (`--assignment`: the adapter's own `split --out`, or the file B-dev wrote with its own implementation).
  - A FinDVer holdout build needs `--testmini` and refuses an overlapping report; with no side declared, a filing's side is its items' official split.
  - ContractNLI reads only the frozen file of its side: `dev.json` by the SHA-256 the B-dev manifest records (held in the adapter); a holdout input only under the SHA-256 role B records for `test.json` and passes with `--frozen-sha256` (the manifest records none for `test.json`, so the adapter holds none and cannot check B's value; it refuses `dev.json`'s). `split` and `bands` check the same.
- **Exclusions.** `--exclude <file>` (a JSON list of source document ids, or `{"source_document_ids": [...]}`) removes the documents a benchmark's own paper prints as in-context examples, as role B identified them, with all their items; `parts.json` records the file's SHA-256 and what was removed, and `split` marks them `excluded_demonstration`.
- **bands** gives every document's words, length band and side (as a build records it) by the one word rule over a whole input, with no build, and per band the documents, items and median words for the holdout pool alone (`holdout_pool_bands`, what role B writes S8's `B_SIZES.json` from) and for the development side apart (`development_bands`). FinDVer's `--testmini` marks a holdout filing it also holds `removed_overlap` (in no total), and a FinDVer holdout input without it is refused; ContraDoc's sides come from the frozen `--assignment` alone, and a ContraDoc input without it is refused, as a holdout build refuses it; ContractNLI's input is checked as a build checks it.
- **The cut budget** is computed per document: the context length, minus the B1 prompt rendered with an empty document from that bundle's own conventions (the largest over its items), minus the output allowance, minus 32.
  - The token counter file defines `count(text) -> int` and `count_prompt(system, user) -> int` with the main reading agent's own tokenizer and chat template.
  - A build without these inputs is refused unless it is flagged `--development`, which `parts.json` records.
- **split** gives the side of every document.
  - ContraDoc, CUAD and SciTab use the hash rule.
  - FinDVer and ContractNLI use their official splits with `--official development|holdout`. FinDVer's `--testmini <file>` marks overlapping reports.
  - `--out` writes the frozen file, with the input's SHA-256.
- **label** reads run output.
  - For B2, B3 and B4, `--runs` holds one run folder per document, named by its opaque document id.
  - For B1, `--runs` holds one `bare_model.py` output folder per document, named the same way, with `labels/<item id>.json` inside.
  - B0 needs no run.
  - B3 and B4 are refused (exit 4) while the typed-record key of the pipeline's output is not settled (section 12 item 9). B2 writes that key.
  - The output file holds the primary labels and the S-1, S-2, S-3 and S-5 analyses.
  - The command exits 3 when it records an adapter fault (a prior relation, a missing typed-record key, an unrecognised verdict).
- **score** scores each analysis, and S-4 (the primary labels without the items `parts.json` lists as having their evidence beyond the cut). It reads gold from the bundles' `answer_key.json` and units from the bundle documents. It refuses when a labelled document has a gold item with no label. Every result carries the statement that it is not comparable with published numbers, and names its headline measure.

## PROVISIONAL, per adapter

**All adapters (run output, `common/mapping.py`).** These are PROVISIONAL until `docs/OUTPUT_FORMAT.md` settles them (section 12, items 1 and 9). Its draft, `output-format-v1-draft`, is on branch `loop/s03` since 5fca716; its section 7.3 (Python's irregular findings are on the bus, not in `review_data.json`) conflicts with section 5.1's reading of `review_data.json` alone, recorded in section 12 item 9.

- The completion record `<run>/audit/run_completion.json` is the pipeline's own (`scripts/run_completion.py`), read with the validity rules of its `read()`; B2 writes the same record.
- The typed-record key `findings` is what B2 writes; the pipeline does not write it yet, so B3 and B4 are refused.
- The UNCERTAIN marker is tested as `scripts/verifiability_gate.py` tests it.
- Pairing-map refusals are the entries under `absence_refused`, naming their rule by `source_rule_id` or `rule_id`. The pipeline writes the registry id there, so they do not match item rules yet (section 12 item 11).
- The record id `item_id` and its `revision` (INFRA-037 supersession).
- The deliverables path.

The computed layer is not PROVISIONAL: a record is Python's exactly when its `written_by` equals `python` (the pipeline's WRITTEN-BY-A stamp on branch `loop/s02`; B2 stamps every record so); any other stamp, and no stamp, is a model's (section 3.6). The same stamp decides whether a record is a figure-audit record (section 0).

**ContraDoc.** Confirmed on the B-dev development items (S4c item 4), none PROVISIONAL now:

- the file is an object of two containers, `pos` and `neg`, each `{unique id: record}`; the container is the gold (`pos` contradictory, `neg` not contradictory) and no record has a label field;
- `unique id` is a string; `text` a string;
- `evidence` is one string in every `pos` record; `ref sentences` is a string, a list of strings, or absent.

`--assignment` reads the adapter's own `split --out` file and the frozen file B-dev wrote with its own implementation of section 1 (`assignments`: `{unique id: {group, side}}`), and refuses a side that is not the hash rule on its group key. On the 184 development documents the adapter's own grouping equals B-dev's (125 groups).

**CUAD.** Confirmed on the B-dev development items (S4c item 4): the SQuAD-style container (`{version, data}`, one paragraph per contract, 41 QA entries), the `<title>__<category>` QA id, `answers` empty exactly when `is_impossible` is true, `title` as the tie-break between duplicate copies, and the data's own category spellings (`DATA_SPELLING`: 15 of the 41 differ from the paper's names, which stay in the rule text). Still PROVISIONAL: the category descriptions, empty until they are copied at freeze from the release's `CUAD_v1_README.txt` category list. Section 5.1's figure-audit rule applies to CUAD as to every benchmark (the CUAD exception of D-043 is withdrawn; preregistration section 12 item 7): on its 41-rule bundles Python's blank-cell `missing_field` records decide no item, and a model-written `missing_field` decides its rule's item.

**SciTab.** Confirmed on the B-dev development items (S4c item 4): the file is a list of claim records; `id`, `table_id`, `paper_id`, `claim` and `table_caption` are strings; `table_column_names` is a list of strings and `table_content_values` a list of rows as wide as it; the labels are spelled `supports` and `refutes`. Where the claims of one table store different cells (one development table, two of its eight claims), the document is the table as its first claim in file order stores it and `parts.json` lists the other claims under `table_variants`; claims of one table naming different papers are refused. Still PROVISIONAL:

- the spelling `not enough info`: no development claim carries that class.

The tables the paper prints as in-context examples are not held in the adapter: role B identifies them by caption and passes their `table_id`s with `--exclude` (section 1; B-dev matched four, all on the holdout side).

**FinDVer.** Confirmed on the B-dev development items (S4c item 4), none PROVISIONAL now. The release keeps claims and filings apart:

- the items file (`data/testmini.json`, `data/test.json`) is a list of claims: `example_id`, `statement` (the claim), `entailment_label` (a boolean, true is entailed), `relevant_context` (integer entry ids), `subset` (`ie`, `numeric`, `knowledge`), `split` (`testmini` or `test`) and `report`, the filing's file name;
- the filing is `financial_reports/<report>`, an object whose `context` lists the entries `{id, context, type}` in id order from 0 (`CONTEXT_INDEX_BASE` 0); `type` is `paragraph` or `table`, and a table's text is pipe rows between lines of text, almost never with a separator row (3 of the 10,991 development table entries have one; held by the `development` check group).

`build --reports <folder>` names the filings' folder; by default it is `financial_reports` beside the items file's folder, as the release lays it out. A table entry is written with a separator row after the first row of each run of pipe rows, unless one is already there (section 5.6, as SciTab's table is; Shimmer reads a table's header only when a separator row follows it), and its words are its cell words and the lines of text around them. An item whose `split` names the other official split is refused. `parts.json` records per filing its SHA-256 and `issuer_cik`, the number after `/edgar/data/` in the filing's `url`, for the issuer bootstrap.

**ContractNLI.** Confirmed on the B-dev development items (S4c item 4), none PROVISIONAL now: `documents`, `id` (an integer), `text`, `spans` (character spans that segment the text, none crossing a line break), `annotation_sets` (one per agreement; the first is used), `annotations`, `choice` with the values `Entailment`, `Contradiction`, `NotMentioned`, `labels` and `hypothesis`; the hypothesis keys are `nda-1` to `nda-20` (17 keys). No development agreement's text holds a blank line, so the earlier rule (one part per blank-line paragraph) made every agreement one part. Section 5.6 now makes one part per span of the agreement's own `spans` list: on the 61 development agreements the spans are in order, never overlap and leave only whitespace between them; 63 of the 5,102 spans hold a single space and make no part, so there are 5,039 parts, 20 to 255 per agreement (median 72), 16 agreements above 99. Every evidence index names a span; one names a single-space span (on an Entailment item with five other spans). `parts.json` records the span index of every part and, per agreement, `spans` and `spans_without_text`. `--parts merged` is section 5.6's cost fallback (consecutive pieces joined into parts of at least 100 words, the last possibly shorter), used only if S5's measured cost triggers it (section 2); `parts.json` records `part_rule` and the spans each merged part holds.

## Words

One rule counts words for the length band, the cut line and `parts.json` (section 5.6, Words): `common/ids.py` `word_count`, Python's `str.split()` with no argument, line by line, where on a pipe row (table text) a token made only of `-`, `:` and `|` is not a word; a SciTab cell is counted on its own as table text (`cell_word_count`). `common/cut.py` `words` is the same function, and every adapter counts its parts with it, so a table's words are its cell words wherever they are counted.

## Readings

Where the preregistration left a choice, the adapters made one. The list of readings is section 5.7 of the preregistration; this README does not repeat it.

## Not done here

- The paired cluster bootstrap, Holm adjustment, McNemar test and derived seeds. These are cross-arm statistics for the scorer, C.
- The FinDVer issuer bootstrap.
- Reason-confirmed recall. That needs a reviewer.
- The 5.3 report figures: the share of words removed across a benchmark, and the uncut-only comparison. `parts.json` holds the numbers they are computed from.
- The single-claim analysis of section 7. It is computed from `items.json` and the labels.
- The real budget inputs and tokenizer. These are pending VERSIONS.md.
- The CUAD descriptions. These are pending freeze. The SciTab demonstration tables are role B's to identify (`--exclude`).
