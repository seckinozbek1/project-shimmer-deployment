# Benchmark adapters

Adapters for the four external benchmarks of `docs/benchmarks/SELECTION.md`: ContraDoc, CUAD v1, SciTab and FinDVer. Each one turns benchmark items into test bundles in the input format `input-format-v1-draft` (`docs/INPUT_FORMAT.md`), turns a run's output into labels, and scores labels against gold. The rules they implement are `docs/benchmarks/PREREGISTRATION.md` sections 0, 1, 3, 4 and 5.1 to 5.6.

## Developed on synthetic items only

No benchmark data was downloaded, opened or searched to write these adapters (hard limit H17, decision D-019). B-dev, the role that would pass on development items, could not run in loop stage S4. Each adapter was written from the schemas documented in `SELECTION.md` and the preregistration, and was checked only on synthetic items written by hand in those schemas (`<name>/fixtures/synthetic_items.json`). The CUAD fixture's 41 QA entries per contract were expanded by a short script from hand-written contract texts and answer choices.

Where a field name or a stored value is not documented outside the data, the adapter takes it from a named constant marked PROVISIONAL, kept in one block at the top of the adapter. Nothing is inferred from data. Every PROVISIONAL constant must be confirmed on development items in S5 before freeze (preregistration section 12). Until then, results from these adapters on real items are not evidence.

## Layout

```
benchmark/adapters/
  common/            shared code, standard library only
    ids.py           opaque ids (section 0), the hash split rule (section 1), length bands
    bundle.py        the one bundle writer: everything the input format decides lives here
    cut.py           the cut rule for long documents (section 5.3), with an injected counter
    mapping.py       run output to label (5.1, 5.2), B0, B1, S-1, S-2; run-output names
    metrics.py       section 3 measures, with ABSTAIN and zero division as section 4 says
    cli.py           the commands below
  contradoc/adapter.py   cuad/adapter.py   scitab/adapter.py   findver/adapter.py
  <name>/fixtures/synthetic_items.json   hand-written items in the documented schema
  <name>/fixtures/mapping_cases.json     hand-written run outputs with the expected labels
```

The gate check module is `scripts/adapter_checks.py`. It reads only these fixtures, works in temporary folders, and skips when `benchmark/adapters/` is absent.

## Portability

Standard library only. Nothing imports the repository's `scripts/`. Copy `benchmark/adapters/` anywhere and run, for example, `py -3.12 -I adapters/contradoc/adapter.py ...`.

## Commands

Every adapter has the same four commands:

```
py -3.12 benchmark/adapters/<name>/adapter.py build --input <benchmark file> --out <empty folder> [--cut-budget N --token-counter <file.py>]
py -3.12 benchmark/adapters/<name>/adapter.py split --input <benchmark file> [--out <file>]
py -3.12 benchmark/adapters/<name>/adapter.py label --items <items.json> --arm B0|B1|B2|B3|B4 [--runs <folder>] --out <labels.json>
py -3.12 benchmark/adapters/<name>/adapter.py score --labels <labels.json> --bundles <build folder> --out <metrics.json>
```

- **build** writes one bundle per document, named by its opaque document id, plus `items.json` and `parts.json` beside the bundles. The output is byte-identical for the same input.
  - Inside each bundle: `context/<id>.md`, `context/_review_targets.json`, `conventions/rules.md` and `answer_key.json`.
  - `items.json` is the item table: `item_id`, `document_id`, `rule_id`, `benchmark`, plus the source item and document ids. It holds no gold.
  - `parts.json` gives, per document, the unit id of every part with its source span or context index, the split key and side, the cluster, the word count and length band, and the cut record.
  - `answer_key.json` holds the input format's required fields, with empty `planted`, `clean` and `twin_of`, and the gold label of every item. The repository's `.gitignore` ignores every file named `*key*`, so built bundles are never committed by accident. They are build output, not source.
- **The cut rule** needs the main reading agent's own tokenizer, which the standard library cannot load. `--token-counter` names a Python file that defines `count(text) -> int`. `--cut-budget` is the budget of section 5.3: `cut.budget(max_context, prompt_tokens_empty_document, output_allowance)` computes it from the values VERSIONS.md pins. Without `--cut-budget` nothing is cut, and `parts.json` records `"applied": false`.
- **split** gives the side of every document. ContraDoc, CUAD and SciTab use the hash rule. FinDVer uses its official split: `--official development|holdout`, and `--testmini <file>` removes from a holdout file every report that also appears in testmini.
- **label** reads run output.
  - For B2, B3 and B4, `--runs` holds one run folder per document, named by its opaque document id.
  - For B1, `--runs` holds one `bare_model.py` output folder per document, named the same way, with `labels/<item id>.json` inside.
  - B0 needs no run.
  - The output file holds the primary labels and the S-1 and S-2 analyses. The command exits with code 3 when it records an adapter fault, such as a prior relation or a missing typed-record key.
- **score** scores each analysis. It reads gold from the bundles' `answer_key.json` and units from the bundle documents. Every result carries the statement that it is not comparable with published numbers.

## PROVISIONAL, per adapter

**All adapters (run output, `common/mapping.py`).** These names come from the code as it stands and from `benchmark/baselines/python_only.py`, not from a published output format. They are settled under preregistration section 12, items 1 and 9.

- `TYPED_RECORDS_KEY = "findings"`: the key of the typed records in `review_data.json`.
- `FINAL_STATUS_FILE`, `FINAL_STATUS_FIELD = "state"`, `FINAL_STATUS_COMPLETED = "completed"`.
- The UNCERTAIN marker: `confidence == "UNCERTAIN"`, case-folded, or `uncertain: true`. This is the test the verifiability gate uses.
- Pairing-map refusals: the entries under `absence_refused`, naming their rule by `source_rule_id` or `rule_id`.
  - The pipeline today writes the registry id (`CONV-001`) there, not the operator's id.
  - So a pairing-map refusal will not match an item rule until the output format carries the operator's id.
- `RECORD_ID_FIELD = "item_id"`: the record id counted once for unattached findings.
- The computed-layer markers: `model == "python"`, `absence_path == "computed"` or `provenance == "computed"`.
- The deliverables path, `<run>/deliverables/<document id>/`.

**ContraDoc.** `unique id` and `text` are documented. These are PROVISIONAL:

- `label`, with the stored values `contradictory` and `not contradictory`;
- `evidence`, the marked evidence sentence;
- `reference`, the marked reference sentence or sentences;
- the file shape: a list of records, or an object whose values are records.

**CUAD.** PROVISIONAL as a whole (preregistration section 9).

- The SQuAD-style container `data` / `title` / `paragraphs` (exactly one per contract) / `context` / `qas` / `id` / `answers`.
- The QA id suffix `__<Category>`.
- `DATA_SPELLING`: the data's own category spellings. Empty, so the paper's names are used.
- `DESCRIPTIONS`: the category descriptions, copied at freeze. Empty, so the template uses the name alone.
- The title is the source id used to choose which copy of a duplicate contract to keep.

**SciTab.** `id`, `table_id`, `paper_id` and `label` are documented. These are PROVISIONAL:

- the label spellings `supports`, `refutes` and `not enough info`;
- `claim`, `table_caption`, `table_column_names` (the header row) and `table_content_values` (the body rows);
- the file shape: a list;
- `DEMONSTRATION_TABLE_IDS`. It is empty, pending B-dev, so no item is excluded.

**FinDVer.** `example_id` and `report` are documented. These are PROVISIONAL:

- `claim`, and `label` with the values `entailed` and `refuted`;
- `context`: the filing's entries in index order, where a string is a paragraph and a list of rows is a table;
- `CONTEXT_INDEX_BASE = 0`;
- `relevant_context`: the item's context indices;
- `subset`.

The issuer for the sensitivity bootstrap is not derived, because how to read it from `report` is not documented.

## Readings chosen where the preregistration leaves room

These are listed for the preregistration. Each one is a reading the code implements; the lead settles them in the text.

1. **Escaping.** A source line whose first non-blank character is `#` is escaped, not only a line whose first character is `#`. An indented heading would also start a unit.
2. **Part text.** CR before LF is dropped. Leading and trailing blank lines of a part are dropped. Lines are split at LF only.
3. **Empty documents.** A document with no part is refused at build. It is never bundled.
4. **`{claim}`.** Runs of whitespace become one space, and nothing is trimmed: the literal reading of "nothing else changed".
5. **Empty CUAD description.** With no description, the trailing space after the name is removed.
6. **SciTab captions and cells.** Line breaks in a caption or in a cell are written as spaces, so the caption stays one line and a row stays one row.
7. **What the cut rule counts.** The token count is taken over the document file exactly as written into the bundle: title, headings, label lines and the cut line. The word counts N and M are taken over the parts' source text.
8. **ContraDoc near-duplicate share.** Shared distinct sentences, over the distinct sentences of the document with fewer distinct sentences.
   - "Smallest unique id" is numeric when all ids in the group are integers, and string order otherwise.
   - Groups are computed over the records given to the command.
9. **Items within CUAD's first matching line.** An irregular record with another relation plus a refusal is `present`, because line 2 matches before line 3.
   - A `missing_field` record that carries the UNCERTAIN marker is a refusal, not an absence.
10. **Records outside lines 2 to 4.** A record whose `record_verdict` is neither `ok` nor `irregular`, and is not a refusal, matches no line of 5.1. It is labelled CLEAR and recorded as an adapter fault.
11. **Missing typed-record key.** A `review_data.json` without the typed-record key is not a run failure under section 0. Its items come out silent, and an adapter fault is recorded.
12. **Location.** A record cites a unit when its `unit_id` equals the unit id, ignoring case. Only the irregular records that decide the FLAG count.
    - ContraDoc's replacement for the Evidence Hit Rate counts a hit when the B1 `evidence` string, or the text of a unit B3 cites, contains the marked evidence sentence.
13. **The item table.** `items.json` carries the four fields of section 0 plus `source_item_id` and `source_document_id`. Section 0 says source ids appear only in `items.json` and in B's folder.
14. **The deciding layer.** "Which layer produced each catch" is `computed`, `judged` or `both`, over the irregular records that decide the FLAG.

## Not done here

- The paired cluster bootstrap, the Holm adjustment, McNemar and the derived seeds. These are cross-arm statistics for the scorer, C.
- The issuer bootstrap for FinDVer.
- Reason-confirmed recall. That needs a reviewer.
- The cut rule's real budget and tokenizer. These are pending VERSIONS.md.
- The SciTab demonstration tables and the CUAD descriptions. These are pending B-dev and freeze.
