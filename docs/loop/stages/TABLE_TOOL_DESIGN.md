# Table tool for the model: design (issue #299, D-681)

Written 16 November 2026 by a read-only design agent for the lead (D-689). Design only: nothing here is built yet.
The tool is switched off by default and is used only after the operator ratifies its DELTA (section 4).

## Where the table path lives today
- `scripts/pipeline.py::_cell_claim_review` calls `cell_selection.review`, which runs `_selections`, then `question`
  (with its `{tools}` slot), then `ask`. `ask` is `narrow_call.narrow_ask`: one forward pass decided from the
  model's probabilities over fixed answers (CHOICE-A).
- `scripts/judge_agent.py` holds a fixed `KNOWN_TOOLS` list (`find_cells`, `locate_figures`, `check_quote`). It fills
  the `{tools}` slot through `claim_tools` and writes `<run>/audit/judge_tools.jsonl`.
- The JUDGE contract (INFRA-049) says JUDGE writes no text and does not choose its evidence or its tools. D-681
  reverses both points, so this is a change to governed structure and needs a DELTA.
- `_cell_claim_review`, `_narrow_ask`, `_judging_role` and `_write_tool_rows` are pinned in
  `benchmark/fixtures/topology_reference_contract.json` and `multi_round_baseline_contract.json`; a change takes
  `reference_amendments` entries. No bound controller file changes. `scripts/` and `config/` are sealed runtime
  folders, so bundles are re-sealed.

## 1. Design
- **Registry:** `config/table_tools.json`. Each entry gives `name`; `does` (one sentence); `inputs` (typed slots: a
  cell id or a claim-figure id); `outputs` (a number, a cell value or a refusal reason); `licence`; `source`
  (`shimmer`, or a package with its pinned wheel hash); `entry` (module:function); `tasks`; `applies_when`
  (structural conditions only); `examples` (input and expected output); `approved_by` (a decision id); and `vetting`
  (the declaration's SHA-256 with its result).
- **Tools:** D-681 fixes `get_cells`, `difference` and `ratio`. Proposed additions: `find_figure`, `compare` and
  `column_extreme`. Arguments are always cell ids (`r3c2`) or claim-figure ids (`f1`), never a typed number, so the
  model cannot invent a figure.
- **One request, never a loop:** the prompt shows a short TOOLS block with only the relevant tools, and asks for
  "CALLS (at most N, one per line, or NONE)". The model generates once, under the frozen decoding policy and a
  per-request grammar (`scripts/contract_decoding.py`) that allows only the shown names, valid ids and at most N
  lines. Python parses every line, runs them all in one batch, and puts a RESULTS block into the existing `{tools}`
  slot. The unchanged `call_choice` then decides, so the settled and leaning records stay as they are.
- **Unit:** one request per (claim, table) question; the shared table prefix benefits from prefix caching.
- **Relevance:** Python reads `applies_when` against the selection, by structure only (WORDS-A): a table is present,
  the shown cells hold at least two numbers, the claim writes at least one figure. A `max_shown` cap is in config.
- **Audit:** the request is one reply record (task `cell_claim_request`, outcome `free_text`, never promoted:
  REPLIES-A, HONEST-OUTPUT-A); each executed call is one row in `judge_tools.jsonl` (tool, argument ids, ok or
  refused with its reason, result digest, call id). Sealed runs print counts only.
- **Vetting as code:** `tools/vet_table_tool.py` checks that the licence is on an operator-declared allowlist, that
  the tool runs with sockets blocked, that two fresh subprocesses with different hash seeds give the same output,
  that it writes no file, and that its examples pass. It writes the `vetting` hash. At start-up, `judge_agent.refusals`
  refuses an entry whose hash does not match or that has no `approved_by`.

## 2. Files and gate checks
- New: `scripts/tool_registry.py`, `scripts/table_tools.py`, `config/table_tools.json`, `tools/vet_table_tool.py`.
- Changed: `judge_agent.py`, `cell_selection.py` (an optional `ask_request`; a `request` block in
  `config/cell_selection.json`), `contract_decoding.py`, `pipeline._cell_claim_review` (pinned),
  `benchmark/baselines/doc_judge.render_choice` and its replay (check 326 still holds), the JUDGE contract and
  registry entry, and the docs (CLAUDE_REFERENCE, CLAUDE.md, genesis.md, README, OPEN_ITEMS).
- Gate checks, each proven by neutralise, fail, restore, pass: (A) start-up refuses a bad licence, a socket-opening
  tool, a non-deterministic tool and an unapproved entry; (B) each tool is correct on a fixture and refuses a zero
  divisor and a percent against a plain number; (C) one round only, and lines above N are refused; (D) an unshown
  tool, an invalid id or a literal number is refused and recorded; (E) a table with no numbers is shown no arithmetic
  tool; (F) one reply record per request, with tool rows equal to the executed calls; (G) with no `request_tools`
  declared, the question and the run are byte for byte the measured ones.

## 3. Cost
- Hands-on build about 16 to 20 hours. Waiting: a re-seal (about 1 hour, 0.5 to 0.7 USD) and the gate on Lambda
  (two parts, about 40 minutes and 0.8 USD each).
- Measurement on the SciTab quick subset already read (13 tables, 78 claims): a replay of the cell step only, both
  arms on one instance, about 2 to 2.6 USD with the seal (inside the 3 USD pre-approval). A full pipeline per arm
  would be about 5.5 USD and needs the operator's word. No bare-model or cloud runs (order 87).

## 4. What needs the operator's word
- A DELTA (a new INFRA amendment) that lets JUDGE write one grammar-bound tool request and choose among the shown
  tools; it reverses two points of INFRA-049. Until it is ratified, the tool stays off and check G holds.
- The cell threshold (0.6) was measured without tool results; it is re-measured on development items, or kept as an
  indicator only.
- Whether `judge_tools.jsonl` keeps digests only (recommended) or values in exposed runs.
- An INFRA-029-style guard on the registry file, since an agent with config write access could edit it.
- Third-party tools are vetted at registration with pinned wheel hashes; blocking sockets is not a sandbox.
- Recommended defaults the lane builds with unless the operator says otherwise: one request per question, the three
  extra tools included, the replay measurement.
