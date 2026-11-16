# DRAFT, APPROVED IN ADVANCE, NOT YET APPLIED: a DELTA letting JUDGE write one table tool request

Status: the text below is not yet in `config/constitution.json` and is not in
force until it is appended. The operator approved this amendment in advance
(D-694 item 2): the lead applies it, once, through `scripts/constitution_guard.py`
on the verified no-gap path (`constitution_guard.verify_amendment_append`), with
the next free id. No other agent and no lane applies it.

The operator's words (D-694), relayed to the lead through `SUPERVISOR_INBOX.md`
at 15:12 and 15:13 on 16 November 2026: Seckin, 15:10, "the model asking for a
tool was never the problem; the line he drew is that tools must not reach the
web".

The operator's decision behind this text is D-681 (16 November 2026, 01:54 and
01:58): v1.0 gets a table tool for the model, one batched round of fixed Python
tools per table, every call and result in the audit trail, the tools declared in
a registry that only the operator adds to. The design is
`docs/loop/stages/TABLE_TOOL_DESIGN.md` (D-689).

## What exists today

INFRA-049 (operator-approved 2026-11-08) made JUDGE the agent of the narrow
tasks. Its contract says JUDGE writes no text (one forward pass decides among the
declared answers) and does not choose its evidence or its tools: Python selects
the cells and runs the declared tools around the question.

The lane `lane/table-tool` built the request, switched off:

- `config/table_tools.json`, read by `scripts/tool_registry.py`: six tools in one
  standard form (`get_cells`, `difference`, `ratio`, `find_figure`, `compare`,
  `column_extreme`), each with its license, source, entry, structural
  `applies_when`, examples, `approved_by` and a `vetting` digest written by
  `tools/vet_table_tool.py`.
- `scripts/table_tools.py`: the tools, the request's text, the parser and the
  one batch that runs the calls.
- `scripts/contract_decoding.py` `RequestGrammar`: the per-request grammar the
  request decodes under.
- `scripts/cell_selection.py` `review(..., ask_request=...)` and
  `scripts/pipeline.py` `_cell_claim_review`: the request, made only when the
  judge's contract declares `request_tools` for `cell_claim`.

With nothing declared (the shipped state) no request is made, the registry is not
read, and the question and the run are byte for byte the measured ones (gate
check 394).

Declaring `request_tools` reverses two points of INFRA-049: JUDGE then writes
text (one grammar-bound request) and chooses among the tools shown to it. That
is a change to governed inter-agent structure, so the code honours the
declaration ONLY when `config/constitution.json` holds an amendment with
`operator_approved: true` whose `change` names both `cell_claim_request` and
`request_tools`. No amendment id is written in code. Without such an amendment,
boot refuses with one line beginning `[table-tool-request] STOP` and the run does
not start: the declaration is never ignored silently (gate check 388).

## The amendment the lead appends

One new amendment, appended at the end of `amendments[]`, with the next free id
when it is applied (INFRA-056 as of this lane's base; never reused, never
inserted, never renumbered). The `approval` block follows INFRA-055's shape.

```json
{
  "id": "<next free INFRA id>",
  "created": "<date applied>",
  "kind": "agent_contract",
  "title": "JUDGE may write one grammar-bound table tool request per cell claim and table, when its contract declares request_tools; no tool reaches the internet",
  "genesis_part": "II",
  "operator_approved": true,
  "approval": {
    "date": "2026-11-16",
    "by": "operator",
    "words": "Seckin, 16 November 2026 15:10: the model asking for a tool was never the problem; the line he drew is that tools must not reach the web (D-694)",
    "asked": "the lead's question of 16 November 2026 (D-681, D-689): the table tool design reverses two points of INFRA-049, so the request needs an amendment before it may be switched on",
    "channel": "relayed to the lead session through docs/loop/private/SUPERVISOR_INBOX.md, 16 November 2026 15:12 and 15:13 +0300",
    "authorization": {
      "date": "2026-11-16",
      "by": "operator",
      "words": "approved in advance (D-694 item 2); tools must not reach the web (15:10)",
      "recorded_in": "docs/loop/DECISIONS.md D-681, D-689, D-694; draft docs/TABLE_TOOL_REQUEST_DELTA_DRAFT.md; design docs/loop/stages/TABLE_TOOL_DESIGN.md",
      "what": "the operator's answer, which is also the instruction: the lead appends this one amendment through scripts/constitution_guard.py on the verified no-gap path, as built on lane/table-tool"
    }
  },
  "change": {
    "product_rule": "When Shimmer runs as a product, neither the model nor any tool sends anything to the internet: no web search, no lookup, not even a masked or anonymised query. Tools compute only on what is already inside Shimmer's own run (D-694 item 3 a).",
    "where_work_runs": "Running Shimmer, its tools, sealing or tests on rented machines stays allowed under the spending and data rules. 'Local' means inside Shimmer's own run with no internet access, never laptop only (D-694 item 3 b).",
    "task": "cell_claim_request",
    "setting": "request_tools on JUDGE's cell_claim task in config/agent_contracts.json: the names of registry tools (config/table_tools.json) JUDGE may ask for. With none declared nothing changes.",
    "effect": "Before each cell claim's question, JUDGE is shown the cells, the claim, the table's index by id and the tools that apply (structural facts only, at most max_shown), and writes ONCE at most max_calls lines, each a shown tool with ids as arguments, or NONE, under a grammar that admits nothing else. Python parses every line, runs every call in one batch and adds a RESULTS block to the question's {tools} slot; the question is then decided from JUDGE's probabilities as before. There is never a second round.",
    "audit": "The request is one narrow call with one reply record (task cell_claim_request, outcome free_text, never promoted). Each line is one row of audit/judge_tools.jsonl: tool, argument ids, ok or the refusal's reason, the result's SHA-256 and the call id; no value is kept.",
    "reverses": "INFRA-049 on two points: JUDGE writes one request, and it chooses among the shown tools. Python still selects the cells, and the decision is still read from probabilities over the declared answers.",
    "registry": "Only the operator adds a tool. Each is vetted by tools/vet_table_tool.py (license on the allowlist, no socket, no file written, deterministic across hash seeds, examples passing) and names its approving decision; boot refuses an entry whose vetting digest does not match its declaration and module source.",
    "unchanged": "The cell selection, the decision rules, the threshold family, the settled and leaning records, the claim_not_met relation (INFRA-048) and its refusal. No other agent, phase, contract or LAW changes."
  }
}
```

Once the amendment is appended, the request is switched on by adding, to JUDGE's
`cell_claim` task in `config/agent_contracts.json`:

```json
"request_tools": ["get_cells", "difference", "ratio", "find_figure", "compare", "column_extreme"]
```

Any subset may be declared; only declared tools can be shown.

## What the operator is also asked (not covered by the advance approval)

1. **The threshold.** The cell threshold (0.6) was measured without tool results.
   With the request on, it is re-measured on development items, or the decision
   is reported as an indicator only until it is.
2. **Digests or values.** `judge_tools.jsonl` keeps digests only (the built
   default). Keeping values in exposed runs would need its own decision.
3. **A guard on the registry.** `config/table_tools.json` is protected by its
   vetting digests at boot, but an agent with config write access could change an
   entry and re-run the vetting tool. An INFRA-029-style guard on the file is
   proposed, not built.
4. **Third-party tools.** A package tool is vetted at registration with its wheel
   pinned by SHA-256 and read before it is added; blocking sockets in the vetting
   process is not a sandbox.

## What applying it does not do

It runs nothing. A re-seal is needed before any sealed run (the change touches
`scripts/` and `config/`), and the measurement (a replay of the cell step only,
both arms on one instance, within the 3 USD pre-approval) is the lead's next
stage.
