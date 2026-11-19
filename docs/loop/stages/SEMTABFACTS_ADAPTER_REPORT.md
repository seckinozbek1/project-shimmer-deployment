# SEM-TAB-FACTS adapter: a separate auxiliary validation set (D-798 item 4)

Lane `lane/semtabfacts-adapter`, from `lead/night-20261119` (155e17bb), 19 November 2026. Built from the
format description only (role B's element and attribute count, the research note
docs/loop/private/SEMTABFACTS_RESEARCH_20261119.md); no benchmark data, no role folder and no SciTab data
were opened. No pipeline run.

## What was built

| Part | Where |
|---|---|
| Adapter, SciTab's place and style | `benchmark/adapters/semtabfacts/adapter.py` |
| Set declaration (read at call time) | `config/semtabfacts_aux_val.json` |
| Two hand-written XML fixtures (invented) | `benchmark/adapters/semtabfacts/fixtures/dev/90001.xml`, `fixtures/test/90002.xml` |
| Gate check 585, run alone: PASS, 9 proofs | `scripts/semtabfacts_checks.py`, registered in `scripts/verify_session1.py` |
| Two additive lines in common | `common/ids.py` (`semtabfacts` in BENCHMARKS), `common/bundle.py` (`semtabfacts` declares `compare: cells`, as SciTab) |
| README section, open item 162 | `benchmark/adapters/README.md`, `docs/fix/OPEN_ITEMS.md` |

- **Two steps.** `freeze` reads the dev and test XML files carrying the gold types into one frozen file
  (set name, digest, `looks: []`, counts, refusals by reason). The common `build`, `split`, `bands`,
  `label` and `score` commands then run over that frozen file only. `read_source` refuses a file whose
  digest, set name or type map does not match the declaration.
- **Bundle.** It is SciTab's bundle. There is one document per table, made of the caption line, a blank
  line, then the pipe table with row 0 as the header. Each statement gets one rule, with SciTab's rule
  text and `[compare: cells]`. FLAG = refutes, CLEAR = supports, UNDECIDED = not enough info.
- **Ids.** The source document id is `<file stem>/<table id>` and the source item id adds
  `/<statement id>`. The split key is the file stem. The document and table ids are kept in `parts.json`.
- **Mapping.** entailed to supports, refuted to refutes, unknown to not enough info. This is declared
  in config, not in code.
- **Spans.** A spanning cell is expanded over every row and column it covers. With `span_fill`
  `repeat` (as declared) its text goes into every covered position; with `first` it goes into the
  first position only. A position that no cell covers becomes an empty cell and is counted as a hole.
- **Evidence.** Every evidence element is removed from the parsed tree before any cell is read, and the
  number removed is recorded.
- **Refusals.** Each refusal is a row of ids only, counted by reason as files, tables and statements.
  The reasons are `span_outside_grid`, `missing_type`, `unknown_type`, `span_unreadable`,
  `overlapping_cells`, `no_cells`, `no_table_id`, `duplicate_table`, `duplicate_statement_id`,
  `empty_statement`, `no_statement_id`, `statement_outside_table`, `unreadable_xml` and
  `not_a_document`.
- **Apart from SciTab.** The set has its own benchmark name and ids. The SciTab adapter refuses its
  frozen file and its item table (check 585). Its side is declared `development` (validation material,
  never a gate set).

## Scoring note

- **Our figure.** It is our own 3-class macro-F1 over supports, refutes and not enough info, from
  `score --class-setting 3-class`. The measure is named `semtabfacts_aux_val 3-class macro-F1 ...` and
  the result carries `never_merged_with: ["scitab"]`.
- **How it is reported.** It goes on its own line, beside the SciTab figures. It is never pooled,
  averaged or summed with any SciTab set or score, and never sampled with one.
- **What it is not.** It is not the task's official metric, which is micro-F1 computed per table and
  then averaged over tables. The published SemEval figures (research note, 6b and 6c) are not
  comparable with ours, and we do not report the official figure as ours.

## Command the lead sends to role B

The role B session needs this commit as a verified git bundle in `_xfer\lead_to_B`. In it, `<dev>` is
the dev v1.1 output folder and `<test>` is the posted test ground-truth folder, both under role B's
`semtabfacts\` folder. Use the gold files: input files carry an empty type, and every statement in them
would be refused as `missing_type`.

```
py -3.12 -X utf8 benchmark/adapters/semtabfacts/adapter.py freeze ^
    --part dev=semtabfacts\<dev> --part test=semtabfacts\<test> ^
    --out semtabfacts\frozen\semtabfacts_aux_val.json
```

- **The set declaration.** Write it beside the frozen file with the printed `digest` and `file_sha256`,
  `looks: []` (look counter 0), and the overlap check against SciTab (by article and by table, research
  note) recorded before the set is first read.
- **Send back counts only:** `counts.by_class`, `counts.by_part`, the table and statement totals,
  `refused_by_reason`, `evidence_marks_stripped`, the digest and the look counter. Send no text and no
  ids beyond the counts.
- **Before any build.** D-798 item 4 builds the set only if it is clean. The data terms have to fit,
  unknown has to match not enough info, and the set must share no table with SciTab. Otherwise it goes
  to FOR_SECKIN with a wake (a SORU entry under D-801).

## Open (open item 162)

- **(a) The older converter.** `tools/scitab_nei_dev.py` (D-642 (c), check 484) still turns SEM-TAB-FACTS
  into SciTab records under the name `scitab`, which is the mixing this set forbids. The lead decides
  whether to retire it.
- **(b) No B1 prompt entry.** `benchmark/baselines/b1_prompt.json` has no `semtabfacts` entry, so B1 and
  cut-rule builds refuse until one is added. That is a re-seal question.
- **(c) Provisional nesting.** The XML nesting is provisional until role B's first freeze.
- **Check number.** I took 585 because it is free on every local branch.
- **Re-seal.** `common/ids.py` and `common/bundle.py` changed additively. If a sealed bundle carries
  benchmark/adapters, re-seal it before its next launch.
