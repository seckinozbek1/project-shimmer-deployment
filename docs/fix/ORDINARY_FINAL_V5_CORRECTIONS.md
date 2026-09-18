# The four corrections after ordinary final run v5

Status: **CORRECTIONS_PROVEN_LOCALLY**. Local only: no cloud, no model execution, no weight
loading. Run v5 (110990c1, bundle `docs/fix/ordinary_final_cloud_run_v5`, results in
`ORDINARY_FINAL_V5_RUN_RESULTS.md`) reached the pipeline's end and failed execution integrity
on output shape. The diagnosis that followed (in the session record) found four causes, and
each is corrected here with an executed proof. No weights, HPO settings, pairing contract,
telemetry architecture, workload or routing changed beyond what the four require; the one
routing consequence is stated under A4.

## Order of work, and why

A1 and A2 were designed together: the grounding rule and the prompt shape are one decision,
because what Python tells the model about references decides what the model can cite, and the
validator has to check exactly that. A4 came next, independent of the PROCESSOR path. A3 came
last, because it acts on parsed output and has to hold whatever the prompts become: once
PROCESSOR items are accepted they enter the bus and change the dynamic content of every
envelope call, which is the dependency the instruction named.

## A1. Ungrounded extraction evidence

**The incompatibility.** `compact_contracts.producer` accepted a ref only when its id was
written inside the span's own text. Training and DEV spans carried inline markers such as
"(REF-20180)"; the v5 result sheet, like every real document, carried none (0 REF literals in
the document, 0 in all seven ledger spans), so every non-empty refs array was refused. The
model had cited, for each span, the reference index's own id for that span's paragraph, which
the prompt had rendered and the contract had told it to select.

**The correction, mechanism and rendering together.**

- `reference_builder.paragraph_ranges` is the one paragraph splitter, used by the index and
  by the grounding, so an indexed paragraph can be located again by its index.
- `bounded_extraction.grounding(text, spans, entries)` places every reference entry of the
  document (both copies, context and operational) in the span that contains its paragraph,
  by paragraph index, and requires the entry's excerpt to match that paragraph's first line;
  anything that does not fit is skipped, never guessed. It returns the citable ids per span,
  one marker per passage (the operational copy's id preferred) and the ids shown.
- `bounded_extraction.annotate` shows each passage as " (REF-NNNN)" at its end, inside the
  final full stop where there is one, the way the training spans carried their references.
  Prompt text only: the source the pipeline reconstructs stays the ledger's.
- `compact_contracts.producer(obj, owned, doc, citable)` grounds a ref when it is in the
  span's citable set or written inside the span's text. The validator's citable set is the
  same placement that rendered the markers: one decision, made by Python.

**What the corrected rule still refuses.** An id the index does not hold (invented); an id
whose passage lies in another span (mismatched); a duplicate; a context-only span's id cited
for an owned span; and, with no placement and no inline id, everything, exactly as before.

**Proof against the v5 evidence** (`test_grounding_v5_raw_outputs_correct_citation_passes_mismatched_refused`,
on the tracked result sheet, sha256 `d0f332c8…`, and the run's own reference index and raw
outputs):

| v5 raw output | Under the corrected rule |
|---|---|
| task-000003 (refs REF-0039, REF-0041, REF-0045, REF-0027: each span's own paragraph) | passes the whole contract; items hydrate |
| task-000008 (refs REF-0032, REF-0035, REF-0037: each one paragraph off) | refused, `Ungrounded extraction evidence` |
| task-000003 with REF-9999 forged in | refused, `Ungrounded extraction evidence` |
| task-000004 and task-000007 (no `uncertainty` key) | still refused, `Exact compact extraction fields required` |

The ledger aliases reproduce the run's (s0, s14c, s1cd, s251, s2d3, s35d, s3e6) and 21 ids are
shown, one per indexed paragraph of the operational copy. The fixture
`docs/fix/compact_contract_ab/fixture.json` now carries `real_document`, a multi-paragraph
document with headings and separators and no inline id, indexed twice by the real
`ReferenceIndex`, on which the same three outcomes are proven and the old inline-id fixture
still passes. Neutralising `grounding` (empty placement) makes the correct citation fail;
restoring it passes.

## A2. Prompt format shift

**What moved.** Under `report_optimized` the PROCESSOR call now sends exactly the two turns
checkpoint 168 was evaluated on:

- the SYSTEM turn is the compact contract followed by the frozen semantic policy, read from
  `config/compact_extraction_prompt.json` (`system_suffix`, the frozen renderer's text, never
  typed into a script) and pinned by `system_sha256`;
- the USER turn is one canonical JSON object with the keys every DEV prompt carried
  (`context_only_spans`, `production_contract`, `required_refs`, `role`, `routed_rules`,
  `source_spans`, `supplied_refs`), sorted keys, compact separators, the owned spans marked as
  in A1, the boundary context clipped to 400 characters as the wide payload clipped it;
- both go through the model's own chat template as system and user messages
  (`agent_wrapper.call_local(prompt, system=…)`, `dispatch` under `_compact_messages`), never
  concatenated into one user turn; no context package, reference passages, rules, bus, briefs,
  constitution or role anchor reach the model on that path.

`compact_contracts.validated_messages` builds it; `semantic_waves` binds it per partition; the
work payload recorded for the call is that user object, so the call evidence names exactly the
keys sent; `_compact_rendered` records the shown ids as what was rendered; the PROCESSOR call
receives the document's whole reference index (`_doc_refs_all`) because nothing of it is
rendered any more (v5's 30-entry excerpt stopped at REF-0045).

**Proof.** `test_prompt_dev_row_reproduces_the_protocol_hash`: twelve DEV rows rendered through
the runtime builder equal the frozen prepared prompts byte for byte and reproduce the
protocol's recorded `prompt_sha256`; through the cached Qwen tokenizer's own template as well.
`test_prompt_validated_messages_shape`: on the fixture document the two turns carry the
validated key set, marked spans, no wide-prompt section, under 8,000 characters.
`test_prompt_dispatch_sends_system_and_user_turns`: the recording tokenizer receives
`[system, user]`, and the prompt hash recorded on the call is the hash of that rendering; a
system turn without the native template is refused. Neutralisations: `validated_system`
without the policy, the pre-correction `build_prompt`, the pre-correction concatenating
`dispatch`; each makes its test fail and restoring passes.

**What had to stay.** The per-partition output budget (1,536 tokens) and the evaluation's
`max_new_tokens` withholding (DECODING-A). The 400-character boundary clip. The document text
is the full text under `report_optimized` (`_truncate_doc` returns it whole), so nothing was
cut. The user turn of a real document is longer than a DEV row's (a partition of up to four
1,200-character spans against DEV sources of a few hundred characters); the shape is the
validated one, the length is the document's. The semantic policy binds `questions` and
`uncertainty` to the canonical Gap/Uncertainty strings the checkpoint was trained to write;
downstream consumers read those fields as strings, which they remain.

## A3. The `confident` key

**The correction the ranking supports.** The diagnosis ranked an adapter-induced flip at one
token position first, value priming second, and could not separate them without a forward
pass; it found no defect in the prompt, which names `confidence` four or five times. The
adapter cannot be retrained (that branch is closed) and the policy is frozen, so the
correction that holds under either origin acts on the output: `config/agent_contracts.json`
declares `core_field_aliases: {"confident": "confidence"}`, and `agent_wrapper` reads the
alias as the canonical key only when the canonical key is absent and the value maps without
interpretation (`CONFIDENT`/`UNCERTAIN` as written in any case, `true` to CONFIDENT, `false` to
UNCERTAIN). Anything else (`"maybe"`, a number, a different misspelling) stays where the model
put it and fails as missing, exactly as before. Every application is recorded as
`contract_normalized` on the result, the bus post, the observation row and the telemetry call
record, so a run's "contract validity per call" says what was read as what.

It holds under either origin because it does not depend on why the first token flipped: the
adapter's preference and the prompt's CONFIDENT tokens produce the same output, and the parser
reads that output. It does not loosen the contract: the value is still validated, the key is
still required, and the alias list is a declaration in config, not a guess in code.

**Proof.** The three v5 raw outputs (ARCHIVIST, LEGAL_ANALYST task 9, EDITOR_CLERK) parse
valid with `items[0].confident->confidence` recorded; eight value cases behave as declared;
a live `run_task` with a stubbed backend carries the record on the result, the bus and the
observation row. Neutralising the alias declaration makes the v5 outputs fail on
`items[0].confidence` again; restoring it passes.

## A4. VERIFIER

**The example.** `_finding_record_text` rendered a worked example with none of the agent's
required fields, and the local base copied it. The example is now built from the agent's own
`required` list (`_record_example_required`), and the section says the record adds fields and
never replaces them. Proven for VERIFIER and LEGAL_ANALYST; ARCHIVIST still gets no record
section. The v5 VERIFIER raw output still fails its contract, which is the point: the change
is to what the model is shown. Neutralising the required-field insertion makes the test fail.

**The case the run exposed.** VERIFIER was sent `verify_draft_against_source` with
`processor_draft_available: false`. Now `phase_5_audit` does not make that call: the
activation ledger records VERIFIER as not called with reason `processor_draft_unavailable`
and the PROCESSOR call id and error as evidence, and `auditor_pairs.record_unavailable`
writes the same two coverage events `prepare_context` would have written, so the analyzer's
pairing figures say unavailable with the reason. FACT_CHECKER keeps its call. With an
accepted draft both calls run as before. This is the one change to phase-5 behaviour, on that
one condition; the pair record contract itself is untouched.

Two pinned contracts refuse silent changes to the reference path: the topology reference
contract (`benchmark/fixtures/topology_reference_contract.json`, baseline 804afa5) and the
pre-multi-round pipeline contract (`benchmark/fixtures/multi_round_baseline_contract.json`,
baseline 47c63ac). This change is recorded in both as an explicit amendment (old and new hash,
reason, this document), and each test now requires its pin to agree with its record. Check 245,
which asserted both auditors in every draft state, now asserts FACT_CHECKER alone in the
no-draft state. The A2 change to phase 3-4 is an optimized-only adapter and is inverted by the
reference tree like the other `semantic_waves` adapters, so that pin is unchanged.

## Sealing and rehearsal

The sealer (`tools/prepare_ordinary_final_run.py`) now requires
`config/compact_extraction_prompt.json` in the bound commit by name, as it requires the decoding
policy files: the declaration is first read at the first bounded partition, long after
admission, and an archive without it would fail a run forty minutes in. The rehearsal harness
takes `--source-bundle`, so the new sealed archive itself is rehearsed on the local Ubuntu
through the controller's own phases before the authorization is spent.

## Gates

| Gate | Result |
|---|---|
| Correction checks (`scripts/ordinary_final_correction_checks.py`) | 14 checks, all executed against fixtures and the v5 evidence |
| Compact-contract gate with its safe-gate baseline | 85 passed, PASS |
| Report-recommendations mutations | 15 of 15 |
| Controller gate | 11 tests, 3 effect proofs, PASS |
| Startup gate | 18 tests, PASS |
| Decoding gate (CUDA, strict determinism) | 3 tests, 5 effect proofs, PASS |
| Integration gate | 128 tests, 21 neutralize/fail/restore/pass proofs (10 new), PASS |
| Main gate, current tree | 248 checks: 234 PASS, 11 FAIL, 3 SKIP; 262 to 265 PASS |
| Main gate, clean baseline worktree at e50a1cc | 245 checks: 229 PASS, 13 FAIL, 3 SKIP |
| Comparison | 0 new failures; the 11 failures are identical pre-existing ones (fastapi and pypdf absent from this interpreter, known fixture states); 28 and 31 fail only at baseline (gitignored input tree in a fresh worktree) |

Evidence under `docs/fix/ordinary_final_v6_gates/`.

## Files

`config/compact_extraction_prompt.json` (new), `config/agent_contracts.json`,
`scripts/bounded_extraction.py`, `scripts/compact_contracts.py`, `scripts/reference_builder.py`,
`scripts/semantic_waves.py`, `scripts/agent_wrapper.py`, `scripts/pipeline.py`,
`scripts/auditor_pairs.py`, `scripts/generation_observation.py`, `scripts/model_telemetry.py`,
`scripts/ordinary_final_correction_checks.py` (new), `scripts/verify_session1.py` (checks 263
to 265), `scripts/final_integration_no_generation_gate.py`, `scripts/execution_topology_checks.py`,
`scripts/report_recommendations_checks.py`, `benchmark/fixtures/topology_reference_contract.json`,
`docs/fix/compact_contract_ab/fixture.json`, `Dockerfile` (the DEV rows check 263 reads),
`CLAUDE.md` (EXTRACTION-A, EXTRACTION-B, ENVELOPE-A, VERIFIER-A), `README.md`.
