# Tool audit (D-694 item 4)

16 November 2026, lane/tool-audit from lead tip 5ea8c651. Read only: the contracts and registry
(`config/agent_contracts.json`, `config/agent_registry.json`, `config/strategic_support_contracts.json`),
the question configs (`config/cell_selection.json`, `passage_pairs.json`, `auditor_questions.json`,
`case_questions.json`, `producer_questions.json`, `unit_conversions.json`), and the modules that build
each model step or consume its value (`agent_wrapper`, `compact_contracts`, `bounded_extraction`,
`strategic_support`, `paired_review`, `relation_checks`, `reference_tables`, `cell_selection`,
`judge_agent`, `passage_pairs`, `auditor_pairs`, `auditor_questions`, `case_questions`,
`multi_round_phase`, `position_gaps`, `producer_questions`, `document_dating`, `pipeline` phases 3 to 6,
`benchmark/baselines/doc_judge.py`). No model and no run was used.

The question for every place: does a model step today do something a fixed Python function could
do exactly (arithmetic, counting, a lookup, date math, a unit conversion, copying an id or a quote,
a field check)? The product rule holds for every tool named here (D-694 item 3 a, NO-WEB-LOCAL-A): pure
Python on what is already inside the run, no socket, no lookup, nothing sent anywhere.

"Fits the mechanism" means the merged tool request (TABLE-TOOL-A): a judge asks, once per claim and
table, for tools declared in `config/table_tools.json`, each taking ids only over a table context,
vetted by `tools/vet_table_tool.py`, approved by a decision on `approving_decisions`. Today that
mechanism serves one task (`cell_claim`) and one context kind (a table and a claim). A place that
needs another context (a unit's text, a corpus, two passages, a case record) does not fit it as it
stands; it needs either a new context kind for the registry or a plain Python step, and in several
cases an operator declaration or a DELTA.

## 1. What Python already does (not gaps)

So that nothing below is counted twice:

- **Paired review arithmetic** (`paired_review.compute_checks`): column holes, missing named fields,
  `sum_mismatch`, `product_mismatch`, two-sided bands the rule states (`bounds_from_rule`),
  reference-table bands, `date_window` on ISO dates in hours or days.
- **Relations** (`relation_checks`, RELATIONS-A): rate (part, whole, percent, at the written
  precision), copy, carry, and unit conversion by a declared decimal prefix.
- **Prior-version comparisons and version changes**: all Python (`paired_review` prior relations,
  `version_changes`).
- **Quote checks**: `quote_not_in_unit`, `_cells_stand_in`, `_rule_check_refusal`,
  `judge_agent.check_quote`, `absence_prediction._valid_quote`, the case suggestion's quote check.
- **Dates and chronology**: `document_dating.resolve_dates` does the whole cascade. ARCHIVIST's own
  `date` and `chronology_position` go to the bus and are read by nobody (`pipeline` reads only
  `kind=inventory` items).
- **Counts and summaries**: `summary_generators`, `audit_synthesizer`, `amendment_render`,
  `multi_round_phase.computed_records` (positions, movements, ids), `position_gaps` (gap arithmetic
  and its relation).
- **Cell claims**: Python selects the cells (CELLS-A) and `locate_figures` shows where each figure the
  claim writes stands. The six registry tools (`get_cells`, `difference`, `ratio`, `find_figure`,
  `compare`, `column_extreme`) are off as shipped.
- **Amendments**: rendered by Python from typed findings. AMENDMENT_DRAFTER's model call is off by
  default (`agent_registry.json`).

## 2. The places, ranked

The rank weighs three things: the expected effect on scored quality or on dropped answers, how often
the place is reached, and the risk of the change. Each entry gives where it is, what the model does,
the tool that would do it exactly, whether it fits the mechanism, the expected effect and the risk.

### 1. The cell claim's arithmetic (SciTab and every `[compare: cells]` rule). BUILT (section 3)

- **Where.** `cell_selection.review`, question `config/cell_selection.json` `decision`
  ("Do the cells show that the claim holds?"). `doc_judge` reuses the same selection, so the
  development judge has the same gap.
- **What the model does.** Every operation the claim names, in its head, on the cells shown:
  differences, ratios, percent changes, points between two percents, sums, means, rank ("second
  best"), and whether a figure matches a cell at the claim's own rounding ("71.2" against "71.24").
- **The tools.**
  - The six shipped tools cover a difference, a ratio, a comparison and a column's extremes.
  - Still missing: a percent change, a sum, a mean, a rank, and equality at the written rounding.
  - Also missing: TABLE-AUTHORITY-A rule 3 (ii), "a claim figure in no cell equals one arithmetic
    step of two located figures, within the cells' own rounding". It is written in
    `docs/loop/stages/SCITAB_INSIDE.md` and was never built.
  - GATE_ATTEMPTS row 2a ("SciTab arithmetic in Python") names the same gap.
- **Fits.** Yes, exactly: a table context, ids only, task `cell_claim`.
- **Expected effect.**
  - The SciTabAlign figures in SCITAB_INSIDE section (d) show small models gaining 3.5 to 9.8
    points when given the right cells.
  - The arithmetic step is the other half of the same failure.
  - No Shimmer figure exists yet. With the request on, the cell threshold (0.6) is an indicator
    until it is measured again on development items (TABLE-TOOL-A).
- **Risk.** Low for correctness, since each tool is exact and refuses rather than guesses. A longer
  tool list costs a small model attention: `max_shown` (6) caps it, and `applies_when` shows a tool
  only on structure.

### 2. ARCHIVIST's corpus inventory counts

- **Where.** `config/agent_contracts.json` ARCHIVIST fields `document_count` and
  `document_names`, and its directive.
- **What the model does.** It counts how many corpus documents hold each structural element and
  lists them.
- **Consumers.** The value is passed raw to LEGAL_ANALYST and PRACTICE_AUDITOR as
  `work_payload.structural_inventory` (`pipeline` phase 3 to 4 and phase 5).
- **The tool.** A verbatim containment count over the corpus.
  `producer_questions.corpus_count` already exists, but only its checks call it.
- **Fits.** No: the context is a corpus, not a table. It needs a Python overwrite of the two fields
  after ARCHIVIST answers (the element name stays the model's) or a corpus context kind.
- **Expected effect.** Every absence finding of both auditors rests on this count, so a wrong count
  is a false absence or a missed one.
- **Risk.** Medium. Verbatim containment undercounts an element the documents name in other words.
  The honest form is to record the Python count beside the model's, then use the Python count once a
  development replay shows it does not lose true absences.

### 3. The absence majority directive (PRACTICE_AUDITOR, LEGAL_ANALYST)

- **Where.** The two contracts' `directives`: "present in more than half the corpus documents but
  absent from this operational document", citing the corpus documents in `ref_ids`.
- **What the model does.** Three exact things:
  - a threshold over item 2's count;
  - an absence test on the document;
  - a lookup from documents to REF ids.
- **The tool.** `count * 2 > n_docs`, a verbatim absence check, and a REF lookup per document
  (`reference_index.find_by_document`).
- **Fits.** No (corpus and document context). This is a Python pre-step that gives each auditor the
  list of elements that pass the threshold and are absent.
- **Expected effect.** Fewer invented absences; better `ref_ids` (the comment's REF citation is a
  hard rule).
- **Risk.** It depends on item 2. Changing what the auditors are given changes governed inter-agent
  structure, so it needs a DELTA.

### 4. Single-sided bounds on uncomputable plans

- **Where.**
  - `paired_review` plans `uncomputable` when `compute_checks` returns nothing.
  - The model is asked "Does the part meet the rule?" (`auditor_questions.json` `rule_check`) or a
    reply under "Do not perform arithmetic".
  - `config/auditor_questions.json` records 3,818 uncomputable calls over 253 saved pairing maps.
- **What the model does.**
  - "Must not exceed X" and "at least N": `bounds_from_rule` needs two figures in the same unit, so
    a one-sided bound falls through.
  - Counts of rows, list items or entries.
  - Comparisons of two scalars with no unit relation.
- **The tool.** A single-bound comparator on a named figure, and a row or item counter.
- **Fits.** Not the registry as it stands (a unit's text, not a table claim). The natural home is a
  new `compute_checks` family.
- **Expected effect.** This is the most frequent model step in the review. Each rule it settles
  takes one model call out and makes a Python record.
- **Risk.** High if done wrong. Which side a bound is on is what the rule's words mean, and code may
  not read that (WORDS-A, D-198). So it needs an operator declaration in the heading's brackets (for
  example `[bound: at most]`, declared like `[scope:]`). A new relation is a Finding record change
  under an amendment, as RELATIONS-A was.

### 5. Ids the model must copy (negotiation and strategic records, finding records)

- **Where.**
  - `strategic_support_contracts.json` PROCESSOR `actor_ids`, `issue_ids`, `round_ids` and
    `source_ids`: each must equal the union over the cited sources, and `strategic_support` enforces
    this as equalities.
  - The strategic VERIFIER's "copy all source_ids".
  - The finding record's `unit_id` ("copy EXACTLY ... matched by its title"; `_repair_unit_id`
    repairs it after the fact).
  - PRACTICE_AUDITOR `procedure_id` and STYLE_GUARDIAN `conv_id`, which the paired plan already
    knows.
  - The compact VERIFIER's `required_refs` copy.
- **What the model does.** It copies sets Python holds, and Python then refuses the answer when the
  copy is wrong.
- **The tool.** Set unions over the evidence graph and a title-to-id lookup. Python fills the field
  and the model is not asked.
- **Fits.** No (not a table). These are plain Python fills.
- **Expected effect.**
  - Fewer dropped answers.
  - D-695 counts 20 of the negotiation system's 25 drops as "proposal ids not declared". Those are
    the same family: an id the model wrote that Python could have given or constrained.
  - ANSWER-FORM-A counts these drops, so the effect is measurable from saved replies at 0 USD.
- **Risk.** Low for unions Python already enforces. Bound runtime parsers change only with a re-seal
  (ANSWER-FORM-A). The contract change is governed.

### 6. Date math: OUTDATED, deadlines, sequence

- **Where.**
  - FACT_CHECKER and PRACTICE_AUDITOR `OUTDATED` verdicts.
  - `date_pair_for_rule` reads ISO dates only and refuses on two shapes or on three or more one-date
    lines.
  - `date_window` takes the gap as an absolute value, so it never checks order (acknowledged before
    logged, expiry before issue), and it reads its bound from reference prose only.
- **What the model does.** It orders dates, takes deltas and adds days to get a deadline.
- **The tool.** A broader date parser (`document_dating` already reads more forms), a signed delta,
  order checks, and date plus N.
- **Fits.** No (unit text). It would extend `compute_checks` and `document_dating`.
- **Expected effect.** Medium: dates are common in operational documents. On the current development
  corpora the count is not recorded.
- **Risk.**
  - Medium. Order is what the words mean ("before"), so an order rule needs a declaration, as item 4
    does.
  - The signed delta itself is exact.
  - OUTDATED against "today" needs the run's own date, never a lookup.

### 7. Rate refusals handed on (`rate_reading_ambiguous` and its family)

- **Where.**
  - `relation_checks` refuses when the figures fit both a share and a plus-or-minus percent change
    (`other_reading_fits`).
  - The same happens on `rate_part_whole_undecided`, `rate_third_figure_tied`,
    `rate_third_figure_unnamed` and `rate_too_many_figures`.
  - The rule then falls to item 4's uncomputable plan.
- **What the model does.** It works out both readings and picks one.
- **The tool.** Compute both readings exactly, and show the model only the choice of reading. Or
  settle it with no model when only one reading agrees.
- **Fits.** Partly. This is the same request idea on a unit context, but not the table registry.
- **Expected effect.**
  - Small to medium. The 27 L12 development entries lost 8 to rate and ratio (RELATIONS-A).
  - Some of those 8 are now refusals, and this tool would recover those.
- **Risk.** Low for the computation. Which reading is meant stays a model's or a declaration's,
  never code's.

### 8. PRACTICE_AUDITOR `record_verdict`

- **Where.** The contract says `irregular` exactly when the verdict is VIOLATION, ANTI_PATTERN or
  OUTDATED, and `ok` when it is COMPLIANT or ALIGNED. The model still writes the field.
- **The tool.** An enum table.
- **Fits.** No (a field derivation). It is a Python fill at intake, like the core field aliases.
- **Expected effect.** It removes one way an answer is inconsistent or dropped. It is small but
  reached on every PRACTICE_AUDITOR item.
- **Risk.**
  - Very low.
  - The mapping is already the contract's text.
  - The contract change is governed. NO_REFERENCE_AVAILABLE and AMBIGUOUS keep the model's field.

### 9. The case movement question beside Python's own trajectory

- **Where.** `case_questions.ask_movements` asks toward, away or neither for every accepted movement.
- **What Python already has.** `position_gaps` computes `moved_toward`, `moved_away` or
  `unchanged_from_prior` for figure-bearing quotes. These are stored as trajectory records.
- **The gap.** The ask does not check those records first, and nothing compares the two answers.
- **The tool.** Reuse the trajectory relation wherever one exists, and ask the model only where none
  does.
- **Fits.** No (a case record). This is a Python pre-step.
- **Expected effect.** Fewer model calls, and agreement by construction on figure movements.
  NEGOTIATION-MEASURE-A measures it on held-out cases.
- **Risk.** Low. CASE-QUESTIONS-A keeps the two narrow model steps, and this narrows only the first.

### 10. Passage pairs: figures and dates of the two passages

- **Where.** `passage_pairs` marks only whether both passages hold a figure, then asks "contradict?"
  (`config/passage_pairs.json`).
- **What the model does.** It decides whether the two passages give different figures or dates for
  the same label.
- **The tool.** A FIGURES block for the pair, by analogy with `locate_figures`:
  - each figure and date of passage A;
  - whether passage B writes the same value;
  - the labels they share.
  It is shown, never decided.
- **Fits.** Partly. It is a judge tool for `passage_pair` (JUDGE-AGENT-A declares tools per task), not
  a request tool.
- **Expected effect.** Unknown. ContraDoc contradictions are mostly not numeric.
- **Risk.** Low. It changes the measured question, so the threshold must be measured again.

### Also found, lower rank

- 11. Computed plans that still call a model for a note (`missing_field`, `date_window`,
  `ratio_out_of_range`, any plan without a ref id): render the note from the check's own fields as
  exact plans already do (`semantic_waves.exact_comparison_plan`). The effect is waste only.
- 12. The fidelity pair (VERIFIER, Auditor896) answers Same, Changed, Missing or Added, while
  `auditor_pairs.claim_coverage` computes the claim-id sets exactly but only records them. Figure
  equality between the extraction and the passage could be shown.
- 13. Model-written figure relations on judged paths (`value_a`, `value_b`, `delta`,
  `band_distance_change`): never recomputed. `judged_item_refusal` checks only that a figure is
  present. A recompute would mark a wrong delta. These records are never promoted, so this is
  honesty, not correctness of amendments.
- 14. The judged absence's trigger condition ("if a figure is over X, field Y is required") and band
  low sides that need a condition field (`low_side_condition` returns "model"): a figure, date or
  yes or no field check. Each needs a declaration, as item 4 does.
- 15. Unit conversions outside decimal prefixes (minutes, hours, days; area exponents): declared
  refusals today (RELATIONS-A names `min` against `d` as never converting). Extending
  `config/unit_conversions.json` is the operator's call.
- 16. The compact PROCESSOR's `claims` (every CLM id in the span, which Python already validates by
  the same regex) and `status` (derived from the arrays).
- 17. Audit-only agents with no consumer: CITATION_RESOLVER (exact name matching,
  `producer_questions.citation_plan`), INST_FINDER, SPEECH_ACT_TAGGER (`lines_of`), and
  `claim_classifier` (no live caller). There is no effect until a consumer exists.

## 3. Built in this lane: the cell claim's missing arithmetic (item 1)

`scripts/table_tools_extra.py`. Six tools, declared in `config/table_tools.json` in the standard form,
`approved_by` D-694 (now on `approving_decisions`), vetted by `tools/vet_table_tool.py` (two fresh
processes, no socket, no write, the same output under two hash seeds, every example passing):

| tool | inputs | does |
|---|---|---|
| `figure_step` | a claim figure | the cells that write it, or every single step (difference, ratio, percent of, percent change) of two one-number cells of one row or one column that gives it at the figure's own rounding, at most 4 listed; it never says which step the claim means (WORDS-A) |
| `rounds_to` | two cells or figures | whether the first, rounded half up to the decimals the second writes (the review's one comma rule), is the second |
| `percent_change` | two cells or figures | (a - b) / b * 100 |
| `sum_cells` | 2 to 6 cells | the sum |
| `mean_cells` | 2 to 6 cells | the mean |
| `rank_in_column` | a cell | its place from the highest and the lowest among its column's one-number cells, with ties |

Every tool takes ids only (a typed number is refused by the parser and the grammar). A percent against
a plain number, a zero divisor, a cell with no single number and an unknown id are refused with the
closed set of reasons. A difference of two percents is listed for a plain figure too (points), so the
tool reports facts and the model reads the claim.

Proofs: gate checks 420 to 424 (`scripts/tool_audit_checks.py`), 21 proofs, each neutralise, fail,
restore, pass. Check 389's list of shipped entries now names the six additions as well.

**Not switched on.** No contract declares `request_tools` (check 424 pins it). The lead switches the
request on after the Lambda gate. When it does, the contract's `request_tools` list orders the tools
and `max_shown` (6) caps what one question sees; which of the twelve to list first is a measurement
for development items, not settled here.

## 4. Left, and why

- Items 2 to 10 do not fit the table registry: their context is a corpus, a unit's text, a case
  record or two passages. Each is either a plain Python step (items 2, 3, 5, 8, 9) or a new
  `compute_checks` family (items 4, 6, 7).
- Items 3, 5 and 8 change what an agent is given or asked, which is governed structure and needs a
  DELTA.
- Items 4, 6, 7 and 14 need an operator declaration of what the words mean (WORDS-A, D-198) before
  any code may act on them.
- Recommended next, in order:
  1. Item 5: a 0 USD replay of saved replies first, under ANSWER-FORM-A, counts the drops a Python
     fill removes.
  2. Item 2 with item 3: record the Python count beside the model's on development runs.
  3. Item 8.
  4. Item 4 once the operator chooses the bound declaration's syntax.
