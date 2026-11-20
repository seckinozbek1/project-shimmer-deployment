# Table tool switch on (D-681 item 6, D-811)

Lane `lane/table-tool-on`, from `lane/grouped-reseal` at 26d13e31. It picks up the switch that
`docs/loop/stages/GROUPED_RESEAL_GATE.md` left off because checks 326 and 544 failed with it on.

## The switch

`config/agent_contracts.json`: JUDGE's `cell_claim` task declares `request_tools` with the twelve tools in
`config/table_tools.json` (the six of D-681 and the six added by the D-694 tool audit), in the registry's order.
INFRA-056 (operator approved) ratifies it, so the constitution is not touched. Boot accepts it: check 388 passes,
`startup_refusals` comes back empty. This is the same declaration the grouped-reseal lane tried.

## The request path, traced

1. `pipeline._cell_claim_review` (scripts/pipeline.py:3446-3457) builds `ask_request` only when the judge's
   contract declares `request_tools`. That is one narrow call: task and plan `cell_claim_request`, sent through
   `table_tools.send`, then `wrapper.dispatch` under the request grammar.
2. `cell_selection.review` (scripts/cell_selection.py:621-629) makes one `table_tools.request_round` call before
   each question. That function (scripts/table_tools.py:327-354) has three outcomes:
   - No shown tool applies: the request is skipped and no prompt is sent.
   - The reply is None: `request_failed` is counted (line 348), and the rows stay `[]`.
   - Otherwise the reply is parsed and every line is run. A reply of `NONE` parses to `[]` (line 255).
3. `cited` is set only when a request reply was read, meaning the request was not skipped and did not fail
   (cell_selection.py:628-629): `cited_cells(request_rows)` collects the `rNcM` ids of the lines Python ran.
4. The question is then decided exactly as before (`call_choice`), with the RESULTS block placed in `{tools}`.
5. `_row` -> `leaning_of` (cell_selection.py:259-286), under TABLE-AUTHORITY-A: if `cited` is not None and
   cites no cell, `no_cell_cited` is added (lines 282-283). The verdict becomes a leaning, and a lowered "not met"
   writes no record (line 656). A decided verdict becomes its finding only when no leaning is set (lines 658-672).

## The mechanical cause of the two failures

- **326 and 544 at baseline.** Their fixture (`cell_selection_checks._phase`) never answered the request. The
  fixture backend's `dispatch` failed it (outcome `backend_failure`, request_failed 1), so `cited` stayed None
  and nothing was lowered. The decided "not met" at 0.9 **did** still become its finding: row (1, 1, 1),
  findings 1, `observe_record` equal. The checks failed only because the request's reply record added a second
  outcome (`backend_failure` beside `not_promoted`), and because `observe_masked` saw two masked calls instead of
  one. Nothing on the product path was lost.
- **"No longer becomes its finding."** The earlier lane saw this with the judge's request answering `NONE`.
  The tool's result really does lower the verdict there: a `NONE` reply is a request reply that was read but
  cites no cell. Then `cited = {"cells": [], "missing": 0}`, so `no_cell_cited` applies (cell_selection.py:283),
  the verdict becomes a leaning, and no record is written (line 656). This is the rule as declared, not a bug:
  TABLE-AUTHORITY-A ("no cell cited lowers 'holds' or 'not met' alike, and a lowered 'not met' writes no
  `claim_not_met` record"), D-642 (d), and D-715 item 2, where Seckin wrote: "The rule that no cell shown means a
  weak leaning stays". Changing it would need his word, so it is unchanged.

## The fix (checks only, no product code changed)

- `scripts/cell_selection_checks.py`: `_phase` now answers the request explicitly whenever the shipped contract
  declares it. The answer is one reply record with outcome `free_text`, written the way a backend function
  writes one. The default answer is `compare(r1c2, r3c2)`. That is a tool shown on this table (`get_cells` is
  not shown, since every cell is already shown), applied to the two cells the claim turns on. Because the verdict
  cites cells, nothing is lowered, and the decided "not met" is its finding exactly as it is with the switch off.
  - `expected_product` adds `free_text` to the outcomes while the request is declared.
  - `observe_masked` also proves the request is masked against the whole document. With the request declared,
    there are two masked calls and the request is not sent raw.
  - A new proof, `a request citing no cell lowers the verdict`, runs only while the request is declared. It says
    explicitly that with a `NONE` reply, row (1, 0, 0) has leaning "not met" and `no_cell_cited`, the decision is
    unchanged ("not met", settled, 0.9), and there are no findings. It is neutralised by removing the
    `no_cell_cited` line.
- `scripts/table_tool_checks.py` (check 394, G): the proofs that the request is off now run on a fixture contract
  that declares nothing. A new observation, `observe_shipped_request`, holds the shipped declaration, on or off,
  to JUDGE's `cell_claim` and to a boot under the ratified amendment. Two new neutralisations cover it: a
  declaration on `passage_pair`, and a declaration with no ratified amendment.
- `scripts/tool_audit_checks.py` (check 424, E): "no shipped contract declares request_tools" becomes "none except
  JUDGE's cell_claim, ratified when declared", with two neutralisations and a local `both` helper.
- `docs/CLAUDE_REFERENCE.md`: TABLE-TOOL-A now records the D-811 switch and says what check 394 now holds. The
  "none declared" sentence about the audit tools is updated. TABLE-AUTHORITY-A now says that a `NONE` reply
  lowers the verdict, and that a column id is not a cited cell.

## Proofs (run alone, `--offline --checks`, never the whole gate)

The same 22 checks were run once with the switch on and once with it off (the declaration removed, then put back).
Every check passed both times (PASS=22 of 22):

- 326 cell selection: 43 proofs with the switch on (the NONE proof added), 42 with it off.
- 544 small table shown whole: 3 proofs.
- 388 to 394 table tool A to G: 8, 4, 3, 5, 3, 4 and 5 proofs. 394 has 3 off-path proofs and 2 for the shipped
  declaration.
- 420 to 424 tool audit A to E: 5, 5, 3, 4 and 5 proofs.
- Also run: 331 (judge agent, 12 proofs), 480 to 483 (TABLE-AUTHORITY-A, 5, 5, 6 and 5 proofs), 509 (D-715
  item 2, 5 proofs), 536 (N1), 545 (S3).

Before the fix, with the switch on, 326 and 544 failed at BASELINE_FAILED; the only differences were the
`outcomes` and `masked` observations. Check 325, the known red, was not run.

## Re-seal

No controller-bound file changed: none of the touched files are in `tools/prepare_ordinary_final_run.py`
CONTROL_FILES, so existing bundles need no re-seal for their binding. `config/agent_contracts.json` and the
check modules ship in every project archive, though. A bundle that is meant to measure the tool on the fresh
table set (D-811) must therefore be sealed from a commit with this switch on. Bundles sealed before it run with
the request off.

## For the measurement (open, not fixed here)

- With the switch on, every claim whose judge answers `NONE` is lowered to a leaning, and a "not met" then
  writes no record. Expect fewer `claim_not_met` records than with the switch off. The fresh-table measurement
  should report how many verdicts the `no_cell_cited` rule lowered (`leanings` and `leaning_why` on the row).
- `cited_cells` counts only `rNcM` ids. A verdict grounded on `column_extreme(c2)` alone, or on a figure id,
  cites no cell and is lowered. That follows the declared rule; whether a column or figure id should count as a
  citation is a question for Seckin after the measurement.
- The titles of checks 394 and 424 in `scripts/verify_session1.py` still say "no request_tools declared" and
  "off as shipped". What each check proves is now in its own summary line. The titles were left alone so this
  lane does not touch the gate file; the lead can rename them at merge.
- The cell threshold (0.6) was measured without tool results. With the request on, it is an indicator until it
  is measured again (TABLE-TOOL-A).
