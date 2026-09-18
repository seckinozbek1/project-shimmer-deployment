# The three items after ordinary final run v6

Status: **CORRECTIONS_PROVEN_LOCALLY**. Local only: no cloud, no model execution, no weight
loading. Run v6 (0cbc7f26, `ORDINARY_FINAL_V6_RUN_RESULTS.md`) left two integrity causes and
one advisory path never exercised. The three items were proposed by a session that could not
see the evidence; where the evidence contradicts a proposal, the proposal is named and the
evidence given. No weights, HPO settings, telemetry architecture, workload or routing changed;
the one phase-5 behaviour change is stated under A5.

## Order of work, and why

A6 first: whether partition 1's answer was right under the frozen policy decides whether a
partial delivery is the normal case or the exception, and A5's partial-pair marking had to be
designed knowing that. A5 second. A7 last, because it touches only the record section and is
independent of the other two.

## A6. PROCESSOR partition 1

**The proposal's premise, and what the evidence says.** The proposal read the three empty
answers as "content was there and the model returned nothing". Under the frozen policy the
model extracts claim ids and explicit absence statements, nothing else: of the 408
question-bearing training targets, 401 sit on an explicit cue in the span ("unavailable",
"missing", "not recorded") and the other 7 on statements such as "The recorder is unnamed" or
"No first entry exists"; the 20 empty targets carry no claim id and no refs, and so do the 4
all-empty DEV answers. The three partition-1 entries (RES-DAMSON, RES-ELDER, RES-FIRTH) carry no
claim id and no absence statement; RES-FIRTH omits its sample identifier silently, which is not
an explicit statement and not an attribute of the finite ontology. The correct extraction of
those spans under the validated policy is therefore three `empty` items with no refs, which is
what the model returned, and what partition 0 returned for its four spans. One behaviour, not
two: the document's figures are the paired review's business, not the extraction's.

**The missing key is the whole failure, and it is a layout question.** Every training input
and DEV row of checkpoint 168 carries ONE or TWO owned spans (292 and 128 in training, 57 and
27 in DEV; owned spans of 49 to 507 characters) and one context-only span. The pipeline sent up
to four owned spans per request. The one omission of the `uncertainty` key was on the
three-span request; the four-span request kept the shape, and every DEV request of the
validated layout kept it (102 of 102 items, the four all-empty answers included, all
single-span). What makes v6's case different from those four is the layout, not the
emptiness. The correction is therefore the layout, not a tolerance: `owned_spans_per_request`
is declared in `config/compact_extraction_prompt.json` (2, the validated maximum), read by
`compact_contracts.request_size` and used by the live partitioning. The contract stays exact.
If a validated-layout request ever drops the key, that is new evidence about the model and is
recorded as a contract violation, where a tolerance can be decided on it.

Residual risk, stated: the layout removes the one known out-of-distribution factor; it is not a
proof that the key is never dropped on a two-span request.

## A5. The pairing gate

**The proposal's diagnosis, corrected.** The delivery-level condition at
`auditor_pairs.build` never fired in any run. In v5 no partition was accepted, so there were no
items. In v6 four items were accepted and `merge` reported the delivery `ok: False` because a
partition was missing; phase 5 read `ok` as "no draft", VERIFIER was skipped (the v5
correction), and `build()` never ran. Auditor896 was never invoked for an upstream reason, not
because of line 99.

**Where the gate belongs.** The third consideration: the two questions have different scopes,
and the wrong one was being asked. Item fidelity is span-local by construction (a pair compares
one item with its own span; `stamp_ownership` binds the item to that span by hash and
revision). Document completeness is already enforced where it belongs: `semantic_incomplete`,
`run_completion` `stopped`, and the runner's `pipeline_not_completed`. A delivery-level refusal
in the pairing therefore duplicated a document-level refusal at the item level, bought nothing
for integrity, and cost the only hardware evidence of the classifier. Against moving it, "a pair
drawn from a partial view may mislead" does not hold for this classifier: its input is one
span and one item, never the rest of the document.

**What changed.**

- `auditor_pairs.delivery_scope` distinguishes a single call from a partition-merged delivery.
  The delivery-level `ok`, `truncated` and `complete` refusal stays exactly as it was for a
  single call. A merged delivery already carries only the items of accepted, untruncated
  partitions, so those items pair; in a partial delivery each requires an ownership receipt
  (`partial_delivery_without_receipt` otherwise), and the pair record carries `delivery:
  partial`. Every item-level disqualification is unchanged; `contract_self_check` passes.
- Coverage carries the mark everywhere it is reported: the `auditor_pair` event (record field),
  the `auditor_pair_coverage` event (`delivery`, `pairs_from_partial_delivery`), the run summary
  (`auditor_pairing.pairs_from_partial_delivery`, `partial_deliveries`) and the analyzer's
  `FINAL_STATUS.json` (`auditor896_pairs`, `auditor896_pairs_from_partial_delivery`).
- Phase 5 hands a partition-merged delivery with partitions missing to both auditors as a
  PARTIAL draft (`_accepted_draft`; `processor_draft_partial`, `processor_missing_partitions`
  and the note), so VERIFIER is called and the pairing runs; a delivery with no accepted items
  is still recorded as VERIFIER not called. This is the one change to phase-5 behaviour, on
  that one condition, recorded as a second amendment in both pinned reference contracts.

## A7. FACT_CHECKER

**The validator-mapping option.** Agreed, and removed: the v6 item compared a sodium reading of
148 mmol/L with the declared result count of 6; mapping its shape would have admitted a
meaningless comparison as valid. The v6 raw output is still refused, and the proof asserts it.

**Base property or prompt effect.** Prompt effect. The same base held the contract in v5 (5
valid items) and in every earlier run on disk (16 of 16 FACT_CHECKER items carry `verdict`). Between
v5 and v6 the FACT_CHECKER prompt's dynamic part had the same size (8,832 characters, 5 bus
messages rendered, the same payload keys and the same draft state) and the static prefix
differed by 288 characters: the v5 record-section change. Under greedy decoding that change
flipped the answer from five valid items to one typed-record item without `verdict`. Which
element flipped it cannot be isolated from preserved evidence; what the evidence does show is a
defect in the example itself: the model filled the two named placeholders it was shown
(`claim_id`, `search_method`) and dropped the one field shown as a sentence about a value
("<your own contract's verdict value, unchanged>"), and the section told VERIFIER to keep a
`verdict` field its contract does not have.

**The correction, lane unchanged.** The typed-record example now carries the agent's own
declared values (`_declared_values`: FACT_CHECKER `verdict: CONFIRMED`, LEGAL_ANALYST
`GROUNDED`, VERIFIER `finding: MATCH`, `paragraph: 1`, `severity: low`), and the section names
the agent's own verdict-bearing field (`_own_verdict_field`). A type description such as
"string | null" is not read as an enumeration. This repairs a demonstrable defect; it is not a
claim that the v6 output is now impossible, and the record says so.

## Proofs

Twenty-one checks in `scripts/ordinary_final_correction_checks.py`, all executed; six new
neutralize/fail/restore/pass entries run in the integration gate:

| Item | Proof | Neutralised mechanism |
|---|---|---|
| A5 | a partial merged delivery pairs its receipt-bound item, marked; a merged delivery with a truncated sibling still pairs; without a receipt it is refused; a failed single delivery is refused as before; coverage and the pair event carry the mark; the run summary carries the figure over the v6 telemetry | `delivery_scope` reporting every delivery single |
| A5 | phase 5 calls VERIFIER with a partial draft, flagged and noted | `_accepted_draft` reverting to the ok-only rule |
| A6 | the declared size is within the validated layout and the live partitioning over a long source groups spans by it | `request_size` returning four |
| A7 | the example carries declared values and names the agent's own field; the v6 FACT_CHECKER output is still refused | `_declared_values` returning nothing |

Main-gate checks 266, 267 and 268; check 265 grows by the partial-draft proof.

## Gates

| Gate | Result |
|---|---|
| Correction checks (`scripts/ordinary_final_correction_checks.py`) | 19 checks, all executed against fixtures and the v5 and v6 evidence |
| Compact-contract gate with its safe-gate baseline | 85 passed, PASS |
| Report-recommendations mutations | 15 of 15 |
| Controller gate | 11 tests, PASS |
| Startup gate | 18 tests, PASS |
| Decoding gate (CUDA, strict determinism) | 3 tests, PASS |
| Integration gate | 133 tests, 26 neutralize/fail/restore/pass proofs (6 new), PASS |
| Main gate, current tree | 251 checks: 237 PASS, 11 FAIL, 3 SKIP; 245 and 262 to 268 PASS |
| Main gate, clean baseline worktree at a8f752e | 248 checks: 232 PASS, 13 FAIL, 3 SKIP |
| Comparison | 0 new failures; the 11 failures are the identical pre-existing ones (fastapi and pypdf absent from this interpreter, known fixture states); 28 and 31 fail only at baseline (gitignored input tree in a fresh worktree) |

Evidence under `docs/fix/ordinary_final_v7_gates/`.
