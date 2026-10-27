# Benchmark adapters

Adapters for the five external benchmarks of `docs/benchmarks/SELECTION.md`: ContraDoc, CUAD v1, SciTab, FinDVer and ContractNLI (added by the operator's decision D-S3). Each one turns benchmark items into test bundles in the input format `input-format-v1-draft` (`docs/INPUT_FORMAT.md`, on branch `loop/s03`), turns a run's output into labels, and scores labels against gold.

What they implement, from `docs/benchmarks/PREREGISTRATION.md`:

- section 0: opaque ids, the item table and the parts record;
- section 1: the hash split rule and the official splits, enforced at build;
- section 3: the official metric or the closest honest measure, location recall, false positives (item level and unattached), refusals, and the catch layer;
- section 4: ABSTAIN and zero division in every F1-type measure;
- section 5.1 and 5.2: the output-to-label mapping, with S-1 and S-2;
- section 5.3: the cut rule, with a per-document budget;
- sections 5.5 and 5.6: the rule templates and the document text and units.

What they do not implement is listed at the end.

## Developed on synthetic items only

No benchmark data was downloaded, opened or searched to write these adapters (hard limit H17, decision D-019). B-dev, the role that would pass on development items, could not run in loop stage S4. Each adapter was written from the schemas documented in `SELECTION.md` and the preregistration, and was checked only on synthetic items in those schemas (`<name>/fixtures/synthetic_items.json`).

- The items are hand-written.
- CUAD's 41 QA entries per contract are expanded by the tracked script `cuad/fixtures/make_synthetic_items.py` from hand-written contract texts and answer choices. The script reproduces the fixture byte for byte.

Where a field name or a stored value is not documented outside the data, the adapter takes it from a named constant marked PROVISIONAL, kept in one block at the top of the adapter. Nothing is inferred from data. Every PROVISIONAL constant must be confirmed on development items in S5 before freeze (preregistration section 12, item 5). Until then, results from these adapters on real items are not evidence.

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
  <name>/fixtures/synthetic_items.json   synthetic items in the documented schema
  <name>/fixtures/mapping_cases.json     synthetic run outputs with the expected labels
```

The checks are in `scripts/adapter_checks.py`. The verify gate runs them through `check()` once the lead registers it; `py -3.12 -X utf8 scripts/adapter_checks.py` runs them by hand. They read only these fixtures, work in temporary folders, and skip when `benchmark/adapters/` is absent.

## Portability

Standard library only. Nothing imports the repository's `scripts/`. Copy `benchmark/adapters/` anywhere, with `benchmark/baselines/b1_prompt.json` or a `--b1-prompt` path, and run, for example, `py -3.12 -I adapters/contradoc/adapter.py ...`.

## Commands

Every adapter has the same four commands:

```
py -3.12 benchmark/adapters/<name>/adapter.py build --input <benchmark file> --out <empty folder> --side development|holdout --max-context N --output-allowance N --token-counter <file.py> [--b1-prompt F] [--assignment F] [--testmini F]
py -3.12 benchmark/adapters/<name>/adapter.py build --input <file> --out <folder> --development     (synthetic or development work only)
py -3.12 benchmark/adapters/<name>/adapter.py split --input <benchmark file> [--out <file>]
py -3.12 benchmark/adapters/<name>/adapter.py label --items <items.json> --arm B0|B1|B2|B3|B4 [--runs <folder>] --out <labels.json>
py -3.12 benchmark/adapters/<name>/adapter.py score --labels <labels.json> --bundles <build folder> --out <metrics.json>
```

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
- **Sides.** Every build declares its side; a document on the other side makes the whole build refuse, writing nothing.
  - ContraDoc reads groups and sides from the frozen file that `split --out` wrote once on the whole input (`--assignment`).
  - A FinDVer holdout build needs `--testmini` and refuses an overlapping report.
  - ContractNLI and FinDVer take the declared official split as the side.
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
  - The output file holds the primary labels and the S-1 and S-2 analyses.
  - The command exits 3 when it records an adapter fault (a prior relation, a missing typed-record key, an unrecognised verdict).
- **score** scores each analysis. It reads gold from the bundles' `answer_key.json` and units from the bundle documents. It refuses when a labelled document has a gold item with no label. Every result carries the statement that it is not comparable with published numbers.

## PROVISIONAL, per adapter

**All adapters (run output, `common/mapping.py`).** These are PROVISIONAL until `docs/OUTPUT_FORMAT.md`, to be written in S3, settles them (section 12, items 1 and 9).

- The completion record `<run>/audit/run_completion.json` is the pipeline's own (`scripts/run_completion.py`), read with the validity rules of its `read()`; B2 writes the same record.
- The typed-record key `findings` is what B2 writes; the pipeline does not write it yet, so B3 and B4 are refused.
- The UNCERTAIN marker is tested as `scripts/verifiability_gate.py` tests it.
- Pairing-map refusals are the entries under `absence_refused`, naming their rule by `source_rule_id` or `rule_id`. The pipeline writes the registry id there, so they do not match item rules yet (section 12 item 11).
- The record id `item_id` and its `revision` (INFRA-037 supersession).
- The computed-layer markers.
- The deliverables path.

**ContraDoc.** `unique id` is documented; `text` is named by section 5.6. These are PROVISIONAL:

- `label`, with the stored values `contradictory` and `not contradictory`;
- `evidence` and `reference`;
- the file shape.

**CUAD.** PROVISIONAL as a whole: the SQuAD-style container, the `__<Category>` QA-id suffix, the data's category spellings, the category descriptions (empty until freeze), and `title` as the tie-break between duplicate copies.

**SciTab.** `id`, `table_id`, `paper_id` and `label` are documented. These are PROVISIONAL:

- the label spellings;
- `claim`, `table_caption`, `table_column_names` and `table_content_values`;
- the file shape;
- `DEMONSTRATION_TABLE_IDS`, which is empty, pending B-dev.

**FinDVer.** `example_id` and `report` are documented. These are PROVISIONAL:

- `claim` and `label` with its values;
- `context`, a list in index order;
- `CONTEXT_INDEX_BASE`;
- `relevant_context` and `subset`.

The issuer is not derived.

**ContractNLI.** PROVISIONAL as a whole: `documents`, `id`, `text`, `spans`, `annotation_sets` (the first set is used), `annotations`, `choice` with its values, `labels` and `hypothesis`. The hypothesis keys also feed the rule ids.

## Readings

Where the preregistration left a choice, the adapters made one. The list of readings is section 5.7 of the preregistration; this README does not repeat it.

## Not done here

- The paired cluster bootstrap, Holm adjustment, McNemar test and derived seeds. These are cross-arm statistics for the scorer, C.
- The FinDVer issuer bootstrap.
- Reason-confirmed recall. That needs a reviewer.
- The 5.3 report figures: the share of words removed across a benchmark, and the uncut-only comparison. `parts.json` holds the numbers they are computed from.
- The single-claim analysis of section 7. It is computed from `items.json` and the labels.
- The real budget inputs and tokenizer. These are pending VERSIONS.md.
- The SciTab demonstration tables and the CUAD descriptions. These are pending B-dev and freeze.
