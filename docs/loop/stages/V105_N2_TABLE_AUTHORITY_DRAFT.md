# N2 draft: a Python comparison layer for table claims (TABLE-AUTHORITY change)

Status: DRAFT ONLY (D-764 item 3, Seckin 19 November 2026 08:17). Written at 0 USD: no Lambda, no
model call, no runtime file changed. It rides v1.05's grouped re-seal only if money is left after
the planned v1.05 steps; otherwise it moves to v1.1. Nothing here is applied: the hard-rule text and
the amendment in section 4 are for the operator to ratify, and the lead appends an amendment only
through `scripts/constitution_guard.py` after that.

## 1. What TABLE-AUTHORITY-A says today, and why

On a rule declaring `[compare: cells]` (CELLS-A) the verdict on a table claim is the model's,
decided as CHOICE-A decides it: Python selects the cells (`cell_selection.select`), the JUDGE agent
(JUDGE-AGENT-A, INFRA-049) is asked one narrow question on the claim and those cells, and the answer
is read from its next-token probabilities over three fixed answers ("holds", "not met", "cannot be
settled"). Python checks only what it can compute and only LOWERS: a lowered verdict is a leaning on
the pairing map's `cell_claims` row (`cell_selection.leaning_of`, `cell_selection._row`), never a
settled decision, never a record, never turned around and never raised. The closed set of reasons
is `below_threshold`, `figure_unverified` (`cell_selection.figure_check`: a claim figure found in no
shown cell and in no single difference or ratio of two figures of one row or column), and
`cited_cell_missing` / `no_cell_cited` (when the table tool request of TABLE-TOOL-A ran).

Why it was written this way:

- WORDS-A. Python never reads the meaning of the claim's words. Which arithmetic a claim asks for
  ("higher", "the best", "by 2 points", "lower error") is a reading of words, so Python cannot pick
  the operation, and a verdict Python made by itself would rest on a word reading it may not do.
- The model writes no free text (INFRA-049): no verdict text to parse, no format to break.
- Python's sub-steps are partial. `figure_check` can say "this figure is nowhere in the cells", which
  is evidence against "holds", but it never knows which cells the claim compares, so it cannot say
  "holds". Lowering is the only safe use of a partial check.
- The `claim_not_met` record (INFRA-048) is defined as a model's settled answer and is never
  promoted (HONEST-OUTPUT-A).

The cost of that design: many table claims are plain arithmetic over two or three cells (a look-up,
a comparison, a difference against a stated number, the highest in a column, a count), and a small
model gets such arithmetic wrong far more often than Python would, while today Python may only
lower a "holds" and never correct a wrong "holds" into "not met" or the reverse.

## 2. The proposed change

The model no longer has to do the arithmetic. It fills a small fixed form that says WHAT the claim
compares; Python reads the cells and computes WHETHER it holds. The meaning stays the model's (it
chooses the operation, the cells, the direction), so WORDS-A holds; the arithmetic becomes Python's.

### 2.1 The form

One narrow call per claim and table (task `cell_claim_form`), grammar-bound exactly as the table
tool request is (`contract_decoding.RequestGrammar` style, frozen decoding policy, DECODING-A): the
reply is ONE line or `NONE`, and the grammar admits nothing else. Every argument is an id from the
index Python shows (the same index `table_tools.render_request` builds), never a typed label or a
typed number:

    operation(argument ids ..., direction)      or      NONE

| Field | What it is | Allowed values |
|---|---|---|
| operation | the kind of comparison | a name from the declared operation list (below) |
| cells, rows, columns | what is compared | cell ids `r3c2`, row ids `r3`, column ids `c2` of the WHOLE table |
| stated number | the figure the claim writes | a claim figure id `f1` (Python numbers the claim's figures, as `table_tools.claim_figures` does) |
| direction | which way the claim points | `greater`, `less`, `equal`; for an extreme, `highest` or `lowest` |
| absent | the claim names something the table does not hold | the token `not_in_table` in place of an id |

The direction is the model's reading, which is where "lower is better" (error rates, perplexity,
loss) is decided: Python never decides which way is better.

### 2.2 The declared operation list

Declared in config (a `form` block in `config/cell_selection.json`), written and committed before
any development read, and taken from the published reasoning types of the public table-claim
benchmark's own paper, not from errors seen on any run. Proposed first list:

| Operation | Arguments | Python computes |
|---|---|---|
| `lookup` | cell, figure | the cell's number equals the stated figure within the cell's own rounding |
| `compare` | cell, cell, direction | the first cell is greater, less or equal to the second |
| `extreme` | cell, column or row, direction | the cell holds the highest (or lowest) number of that column or row |
| `difference` | cell, cell, figure | the first minus the second equals the stated figure within rounding |
| `ratio` | cell, cell, figure | the first divided by the second equals the stated figure within rounding |
| `count` | cell list, cell, direction, figure | how many of the listed cells are greater (less, equal) than the reference cell equals the stated count |
| `all` | cell list, cell, direction | every listed cell is greater (less, equal) than the reference cell |

Not in the list, on purpose: "most", "significant", "consistent", "comparable" and every other
word whose threshold is a meaning; those claims stay with the model.

### 2.3 Who decides, per claim

1. Python selects the cells exactly as today (CELLS-A unchanged).
2. The form call is made (only when switched on, section 5).
3. The unchanged choice question is asked exactly as today, byte for byte, so the model's own
   verdict is always there beside Python's.
4. Python parses the form and resolves it on the table:
   - complete and resolved (a declared operation, the right number and types of ids, every id in
     the table, every cell holding exactly one number, comparable units, no percent against plain
     number): Python computes `holds` or `not met`. This is the verdict, `decided_by: python_form`.
   - anything else: the model's verdict stands, `decided_by: model_choice`, with today's leanings
     applied to it unchanged. The form's state is recorded with a reason from a closed set:
     `form_none`, `form_not_parsed`, `operation_not_declared`, `wrong_arguments`, `id_not_valid`,
     `not_one_number`, `percent_against_plain`, `zero_divisor`, `label_not_in_table`,
     `form_call_failed`.
5. A computed verdict is never lowered by `figure_unverified` (Python computed it) and never by the
   citation reasons (the form's ids are its citation). `label_not_in_table` gives NO verdict: it is
   recorded and counted as a possible "cannot be settled" signal for later study, and turning it
   into a verdict would need its own operator decision.
6. Python never repairs a form and never guesses a missing field.

### 2.4 Records and marks (HONEST-OUTPUT-A)

- The pairing map's `cell_claims` decision row keeps every field it has today, unchanged, and adds:
  `form` (operation name and argument ids only, no text, no value), `form_state` (`resolved` or the
  reason), `computed` (`holds`, `not met` or null), `verdict` (the one used) and `decided_by`
  (`python_form` or `model_choice`). A row with no `form` field reads exactly as before.
- A computed "not met" writes a record of a NEW relation, `claim_not_met_computed`, appended to the
  relation list (never a change to `claim_not_met`): `quote` holds the cells the form named, as
  Python renders them, `quote_b` the claim. It is still a model-assisted record, because the model
  chose the operation and the cells: written_by model (the form is the model's), carrying the model
  finding mark and the extra mark "computed by Python from the model's form", screened, NEVER
  promoted to an amendment.
- A model "not met" keeps writing `claim_not_met` as today, so a reader can always tell who decided.
- The form call writes its one reply record (REPLIES-A), outcome `free_text`, never promoted; the
  audit row in `audit/judge_tools.jsonl` holds the operation, the argument ids, the state and the
  result's digest, never a value.

### 2.5 Threshold

A computed verdict does not depend on the choice threshold: it is a computation, not a probability.
This is the one point where the change touches CHOICE-A's settling rule, so it is listed for the
operator in section 4 as a choice: (A) a resolved form settles with or without a measured
`cell_claim` threshold; (B) it settles only when the threshold is measured. The draft recommends (A),
because the form's completeness is its own gate, and the without-form figure is always reported
beside it.

## 3. Files and functions that would change

Bound means: the file travels in the source archive and is hashed into the bundle's runtime hashes
(`RUNTIME_PREFIXES` `scripts/`, `config/`, `corpus_ingest/`; `RUNTIME_FILES`, which include
`tools/score_corpus.py` and `genesis.md`; `ARCHIVE_EXTRAS` `benchmark/adapters/` and
`benchmark/baselines/`, in `tools/prepare_ordinary_final_run.py`), or it is a function pinned by AST
hash in `benchmark/fixtures/topology_reference_contract.json` and
`benchmark/fixtures/multi_round_baseline_contract.json`. Any of them changing means every bundle
that will run it is re-sealed (the grouped re-seal).

### 3.1 Bound runtime files (re-seal)

| File | Function or block | Change |
|---|---|---|
| `scripts/table_form.py` (new) | `parse_form`, `resolve`, `compute`, `FORM_REASONS` | the form's parse and Python's computation; pure functions of the table context and the ids; reuses `table_tools.context_of`, `number`, `value_of` and `cell_selection.figure_value` and its rounding rule (`_overlaps`) |
| `scripts/cell_selection.py` | `review` | a new `ask_form` callable, used only when the contract declares the form; the form call before the unchanged question |
| `scripts/cell_selection.py` | `_row`, `leaning_of`, `finding`, module docstring | the new row fields; no leaning on a computed verdict; the computed record of the new relation |
| `scripts/table_tools.py` | `number`, `value_of`, `context_of` | read only by the new module; changed only if a helper must be shared (prefer no change) |
| `scripts/contract_decoding.py` | `RequestGrammar`, `for_call` | a grammar for the one form line (adds a `direction` slot type and the `not_in_table` token), read from a `_table_form` spec on the wrapper |
| `scripts/judge_agent.py` | `KNOWN_TOOLS`, `declared_tools`, a new `form_operations(task, contracts)`, `refusals` | the `compute_form` tool; boot refuses a declared form without a ratified amendment |
| `scripts/tool_registry.py` | a `form_ratified(root)` beside `request_ratified` | the amendment check, self-contained, no amendment id in code |
| `scripts/finding_record.py` | `TEXT_RELATIONS`, `CELL_RELATIONS`, fallback relation list | the appended relation |
| `scripts/paired_review.py` | `_cell_claim_refusal` | refuses the new relation unless Python resolved the form on the unit's own table |
| `scripts/pipeline.py` | `_cell_claim_review` (PINNED) | builds `ask_form` through `_narrow_ask` with task `cell_claim_form` when the judge contract declares it |
| `config/agent_contracts.json` | JUDGE `cell_claim` task; `finding_record.relations` | an optional `form` declaration (empty as shipped); the relation appended at the end |
| `config/cell_selection.json` | new `form` block | template, operation list with argument types, `max_new_tokens` |
| `config/constitution.json` | `amendments[]` | the new amendment, appended by the lead after ratification only |
| `benchmark/adapters/common/detection.py` | `cell_state`, `cell_claims`, `_classify`, counts | scores the `verdict` field when present; carries `class_without_form` and `label_without_form` beside, as leanings are carried; adds `decided_by_form_rows` and `moved_by_form` counts |
| `tools/score_corpus.py` | `benchmark_items` | carries `b3_class_without_form` |
| `benchmark/baselines/doc_judge.py`, `benchmark/baselines/choice_judge_prompt.json` | `render_choice`, `select_cells`, the claim form config | only if the measurement uses the replay pass: the replay renders the same form with the same function, so the two paths stay held equal (check 326's rule) |
| `genesis.md` | Part VII JUDGE paragraph, if it states that Python only lowers | hygiene, after ratification |

### 3.2 Pinned functions (reference amendments)

`_cell_claim_review` is pinned in both contract fixtures. Its change is recorded as one
`reference_amendments` entry in each (`from` the current hash, `to` the new one, the reason and the
decision id), the way every earlier pinned change was. `_narrow_ask`, `_judging_role`,
`_write_tool_rows` and `record_cell_threshold_missing` stay unchanged.

### 3.3 Controller files

No file of `CONTROL_FILES` in `tools/prepare_ordinary_final_run.py` changes (the watchdogs, the
runner, the bound wrapper, the budget guard, the reaper, `seal_route.py`, `asset_build.py`). The
controller binding is untouched; the re-seal is needed because the runtime hashes change.

### 3.4 Gate side (not bound, never in a source archive)

`scripts/table_form_checks.py` (new, a `*_checks.py` file), new check entries in
`scripts/verify_session1.py`, and the two fixture contracts above.

### 3.5 Documents (hygiene)

`CLAUDE.md` (the TABLE-AUTHORITY-A bullet, section 4), `docs/CLAUDE_REFERENCE.md#table-authority-a`
and `#cells-a`, `README.md` if it describes table claims, `docs/fix/OPEN_ITEMS.md`.

## 4. Constitution amendment and hard-rule change (for the operator to ratify)

Both are needed. The change reverses TABLE-AUTHORITY-A's core sentence ("Python checks only what it
can compute and only lowers"), and it changes INFRA-049 (the judge writes no text and its answer is
read from probabilities), INFRA-048 (a cell record is a model's settled answer) and INFRA-056's
"unchanged" clause (the decision rules). Agents never self-apply; nothing below is in
`config/constitution.json`.

### 4.1 Draft amendment (append-only, the next free INFRA id)

- kind: `judge_agent_form`
- title: JUDGE may fill one grammar-bound comparison form per cell claim and table; where the form
  is complete and the cells resolve, Python computes the verdict.
- change:
  - task: `cell_claim_form`; setting: a `form` declaration on JUDGE's `cell_claim` task in
    `config/agent_contracts.json` naming operations from the declared list in
    `config/cell_selection.json`. With none declared nothing changes.
  - effect: before the cell claim's unchanged question, JUDGE writes ONCE one line, a declared
    operation with ids of the shown index as arguments and a direction, or NONE, under a grammar
    that admits nothing else. Python parses it and, when it is complete and every id resolves to a
    one-number cell, computes "holds" or "not met"; that is the verdict, marked decided by Python
    from the model's form. Otherwise the model's own decision stands, as before.
  - relation appended: `claim_not_met_computed`, a claim the cells the model's form named do not
    meet by Python's computation; quote the named cells as Python renders them, quote_b the claim;
    written_by model, marked, screened, never promoted. `claim_not_met` keeps its meaning.
  - threshold: option (A) or (B) of section 2.5, as the operator chooses.
  - reverses: INFRA-049 on two points (JUDGE writes one form line; Python computes a verdict where
    the form resolves) and TABLE-AUTHORITY-A's "only lowers" for resolved forms. Unchanged: the cell
    selection, the choice question byte for byte, the threshold family, the leanings on model
    verdicts, `claim_not_met` and its refusal, the table tool request, the internet rule of
    INFRA-056 (the form reaches nothing outside the run).
  - scope: append only; no seed law, existing amendment, agent, relation or field is modified.

### 4.2 Draft hard-rule text for CLAUDE.md (replacing the TABLE-AUTHORITY-A bullet)

    TABLE-AUTHORITY-A: a table verdict is the model's, except where its declared comparison form
    resolves: then Python computes it from the cells the form names, marked decided by Python from
    the model's form, never promoted; on a model verdict Python's computable sub-steps (figures,
    cited cells) and the threshold only lower it to a leaning; the form is off unless declared under
    a ratified amendment (full text: docs/CLAUDE_REFERENCE.md#table-authority-a)

### 4.3 Points the operator decides

1. Whether to ratify the amendment at all, and when (v1.05 only if money is left, else v1.1).
2. The threshold option (A) or (B).
3. Whether `label_not_in_table` may ever become a "cannot be settled" verdict (the draft says no,
   recorded only).
4. The operation list's source (the draft proposes the benchmark paper's published reasoning
   types, frozen before any read).

## 5. The switch, and the gate checks that would prove it

The switch: the `form` declaration on JUDGE's `cell_claim` task in `config/agent_contracts.json`.
As shipped it is absent, so no form call is made, no row field is added and the question is the
measured one byte for byte. Declared without a ratified amendment, boot refuses with one line
(`[table-form] STOP`, through `judge_agent.refusals`) and the run does not start; it is never
ignored silently, as INST-SWITCH-A and TABLE-TOOL-A do it. The check numbers are the next free ones
when the change is built (the lead assigns them; several numbers above 546 are already taken).

Each proof is neutralise, fail, restore, pass (`scripts/effect_proof.py`), on invented tables and a
scripted model only; no provider, no key, nothing written to real `durable/`, `ontology/` or
`config/`:

1. Off as shipped: with nothing declared the phase makes no form call, the question and the rows
   are byte for byte those of today (the D-715 style comparison). Neutralised: the form asked when
   undeclared; the check fails.
2. Boot refusal: a declared form with no ratified amendment stops boot with the one line.
   Neutralised: the refusal skipped; fails.
3. Computation per operation: on an invented table, each declared operation with a complete form
   gives the expected computed verdict, including a difference within the cells' rounding, a
   comparison where the form says lower is better, an extreme over a column, a count and an "all".
   Neutralised: `compute` returns nothing, so the model's verdict appears; fails.
4. Fallback: every reason of the closed set leaves the model's verdict in place with
   `decided_by: model_choice` and the reason recorded; today's leanings still apply to it.
   Neutralised: an unresolved form read as "not met"; fails.
5. Marks and records: a computed "not met" writes `claim_not_met_computed` with Python's rendering
   of the named cells, marked and never promoted; a model "not met" still writes `claim_not_met`;
   a computed verdict is never lowered by `figure_unverified`. Neutralised: the mark dropped; fails.
6. WORDS-A: the same form on two claims with different words gives the same computed verdict, and
   Python reads no word of the claim to choose an operation or a direction (check 174's vocabulary
   probe stays green). Neutralised: an operation picked from the claim's text; fails.
7. Scoring: under `detection_dev` the adapter's labeller scores the `verdict` field, carries
   `class_without_form` beside it and counts the rows the form decided or moved; a row with no
   `form` field scores exactly as before; `tools/score_corpus.benchmark_items` carries both.
   Neutralised: the without-form class taken from the computed verdict; fails.
8. Replay held equal (only if the replay pass is used): the replay renders the same form string as
   the pipeline for the same table and claim, as check 326 holds the question equal.

## 6. How it is measured

- Development material only: the SciTab development parts the loop already uses for the cell step,
  read under their existing rules (G1 half A only, D-296; half B never). Never the quick subset as a
  test, never a gate set, never the fresh sets, never a sealed or held-out set, never any item the
  leakage check removed.
- The bar is written and committed BEFORE any development read, in a stage file of its own, with
  the operation list frozen in config at the same commit. Proposed bar:
  - primary: the development figure the cell step is reported by today (macro-F1 as the
    development report computes it) with the form, against the same run's figure without the form
    (`class_without_form`), so both come from one run on the same items and the same checkpoint
    (FACTORS-A: the form is the only recorded factor that differs);
  - paired cluster bootstrap by table, the improvement's lower bound above zero;
  - a coverage figure (how many claims resolved), counted with no key;
  - a safety floor: among claims the form decided, the share whose computed verdict disagrees with
    the key is reported, and the change is not adopted if it is higher than the model's own
    disagreement on the same claims.
- One round on the development set. If it fails the bar it is reported as failed and not tuned on
  the same items; a second attempt needs a fresh development part and a new bar.
- Every figure is reported with and without the form, item counts and intervals beside it; no item
  id, gold label or claim text leaves the scorer.

## 7. Cost

- Now: 0 USD. This draft is a document; nothing ran.
- Building it later: 0 USD (fixtures and a scripted model on the laptop gate path only).
- Measuring it, if it rides v1.05's grouped re-seal: one development launch with the form switched
  on; the without-form figure comes from the same run's rows, so no second arm is launched. The
  seal itself rides the grouped re-seal and adds no seal launch of its own. Per claim the run adds
  one short grammar-bound generated call (one line, a few dozen tokens) beside the unchanged
  one-pass choice question.
- Forecast: about 3 to 7 USD for that launch. This is an ESTIMATE, not a priced figure: it is scaled
  from the size of one cell-step development rerun on one GPU instance, with the form calls adding
  roughly a third to a half to the model time. Before any launch the lead prices it with
  `tools/loop/step_cost.py` from the provider inventory and the storage record (STEP-COST-A); a
  figure up to 5 USD is pre-approved (D-708), above it goes to Seckin, and the remaining spend limit
  in `config/loop_spend_limits.json` applies.
