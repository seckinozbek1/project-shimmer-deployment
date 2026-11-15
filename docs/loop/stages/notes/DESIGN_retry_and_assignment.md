# Design note: step 1 (retry with changed input) and the per-unit agent-assignment layer (D-567, D-571 to D-573)

Written before any code. Development material only; failure TYPES from GATE_ATTEMPTS section 10 only.

## 1. Retry of an incomplete or refused step

**What exists.**
- PROCESSOR already has a bounded partition-recovery contract.
- Under deterministic decoding, no partition retry is made (`retry_skipped_deterministic`, D-061), because a same-input re-ask repeats byte for byte.
- Requests are cut at `owned_spans_per_request` 2 (`compact_contracts.request_size`, EXTRACTION-C). Checkpoint 168's DEV rows carry 1 or 2 spans.

**Design.** Retry once, with changed input, never the same bytes.

| Failure type | Smaller input on retry | Notes |
|---|---|---|
| (a) PROCESSOR refusal or cap hit on a 2-span request | Each owned span asked alone | 1 span per request is inside the DEV shape, so no prompt shape is new. |
| (b) PROCESSOR refusal on a 1-span request | None exists | Recorded `retry_not_possible: single_span`. This is 6 of the 7 refusals of section 10, so (a) does not reach them. |
| (c) A cap hit on a corpus-level or per-document wide call (INST_FINDER at 2,048, VERIFIER at 4,096) | The same agent on halves of its own payload | INST_FINDER: the document digest split by document. VERIFIER: its pair list split in two, through `auditor_pairs.pair_view`. Each half is a new request, recorded as `retry_of` the call it replaces. |

For (b), the only input-changing retry is to merge the remainder span into the previous request. That makes 2 spans, also inside the DEV shape. It changes how requests are cut, so it needs a decision.

**Length check before every call.**
- The prompt's tokens are already checked against the model's context (PREFILL-E).
- The step adds a check of prompt tokens plus allowance against the context. A request over it is split before the call, as in (a) or (c), never sent.
- The output cap cannot be known before generating. A cap hit is handled as in (c).

**Record.** On the original call's reply record and in `audit/retries.jsonl`: call ids, the reason, the piece sizes in tokens, and the outcome. The merge keeps every partition's ownership receipt, so PAIRING-A still binds items to spans.

**Where.**
- `scripts/compact_contracts.py`: the request cutter.
- The pipeline's PROCESSOR partition loop.
- The INST_FINDER and VERIFIER call sites.
- No bound controller file changes. The runtime files travel in the sealed archive; they are not in the binding.

**Tests (fixtures, gate check).**
- A 2-span refusal is re-asked as two 1-span requests, and the bytes differ from the first ask.
- A 1-span refusal is recorded `retry_not_possible`.
- An over-context request is split and never sent.
- The receipts still bind.
- Each test is neutralised once: the retry removed, which must fail.

**Development measurement.** Replay the saved dev prompts of the same failure types on the A10. The bar is written first:
- refusals and cap hits fall;
- no valid reply changes;
- DEV 102 of 102 items and 75 of 84 valid stay.

**Time.** About 3 h of code and tests, plus about 1.5 h of Lambda replay.

## 2. Per-unit agent-assignment layer

**Where selection lives today.**
- The dispatch is fixed lists in the pipeline: `PRODUCTION_AGENTS_PER_DOC` = PROCESSOR, SPEECH_ACT_TAGGER and LEGAL_ANALYST; `PRODUCTION_AGENTS_CORPUS_LEVEL` = ARCHIVIST, INST_FINDER and CITATION_RESOLVER; `AUDIT_AGENTS_PER_DOC` = VERIFIER and FACT_CHECKER.
- Skips are recorded by `agent_activation.not_called(reason, evidence, state)`, written to `audit/agent_activation.json`. There are about 25 such sites, all for structural reasons: no conventions, no findings in pass one, a draft unavailable, and so on.
- INFRA-050's per-unit selection ("a unit Python selects nothing in makes no call") is built in `scripts/producer_questions.py`. It is NOT live: every form in `config/producer_questions.json` is `reply`, so the five roles still run wide, on the whole document.
- JUDGE-AGENT-A (INFRA-049) routes `[compare: cells]` and `[compare: passages]` to JUDGE only in the decision form.

**Design.** A new module, `scripts/agent_assignment.py`, called once per document before `_process_doc` builds wrappers, and per unit where an agent is per-unit. Output: `assign(doc, units) -> {agent: {assigned: bool, reason, conditions}}`. It feeds the existing dispatch, which skips through `agent_activation.not_called(..., state="unassigned", trigger_source="assignment", evidence=conditions)`, plus one record per document in `audit/agent_assignment.json`.

**Conditions Python can read structurally (WORDS-A: no meaning, no keyword table).**

| Condition | Read by |
|---|---|
| Pipe table present; numeric cell count | the existing table reader in `cell_selection.py` and `pairing_map.split_units` |
| Prose outside tables | lines that are not table rows or headings, by structure |
| Citation markers in declared syntax | `numbered_references` and REF ids in `config/relation_patterns.json` |
| Declared rule brackets (`[scope:]`, `[requires:]`, `[compare:]`) | already parsed |
| A declared act set present for SPEECH_ACT_TAGGER | config |
| Field labels and figures with a unit | `_QUANTITY` |
| Number of units and their sizes in tokens | the unit split |

Conditions that rest on what words mean are NOT read before 14 November: a normative or deontic sentence, an addressed institution, a possible clash between units. Under WORDS-A they go through `semantic_ensemble`, with references and measured thresholds that do not exist yet. Until then an agent that needs one of them stays assigned, and the record says `condition not read: needs the ensemble`.

**Floor.** The layer refuses any assignment below the floor (section 3). The refusal is proved by a gate check with a neutralisation: the floor check removed, an unassigned VERIFIER must then pass, so the neutralised check fails.

**Tests (fixtures).**
- Each condition, read on a synthetic table document and a synthetic prose document.
- A skip carries its reason and conditions.
- The floor refusal, with its neutralisation.
- "Every agent on" equals today's dispatch, byte for byte in the calls made: the layer with all conditions true changes nothing.

**Report on the development set.** Per agent: ran, skipped and why. Then the layer against all agents on: accuracy, integrity and time, per benchmark, on the dev builds only, on Lambda.

**Time.** About 5 h of code and tests for the Python-condition version, plus about 2 h on Lambda for the dev comparison.

**Bound controller files.** None change.

## 3. The binding floor: what the rules make mandatory

Each item is listed with the rule behind it and where code enforces it.

| # | Floor item | Rule | Enforced in code by |
|---|---|---|---|
| F1 | Every produced output is audited by the other model family: VERIFIER (local_auditor) on PROCESSOR's (local_producer) draft whenever a draft exists | LAW-III: "No model may verify, fact-check, or audit output that was generated by the same model family ... The audit trail must show which model produced and which model verified every output segment." | the backend column fixed in code, never from config (pipeline lines 453 to 481), and checks 87 and 127 (corrected 13 November from "check 148", the tolerant-recovery check; F1 is rewritten to INFRA-053 by #250) |
| F2 | PROCESSOR with checkpoint 168 runs | Runner integrity: `required_telemetry_missing` unless a model_call with adapter_checkpoint 168 | `tools/ordinary_final_run.assess` |
| F3 | INST_FINDER runs unless an operator-ratified amendment switches it off; otherwise the run refuses (exit 9) | INST-SWITCH-A | the pipeline's `_inst_finder_decision` |
| F4 | The redaction phase always runs, with its hard stop when no rule compiles | INFRA-034; LAW-IV | the redaction gate |
| F5 | The verifiability gate always runs | pipeline behaviour, CLAUDE.md: "Do not remove or weaken it" | `scripts/verifiability_gate.py` |
| F6 | An editorial observation is reviewed by the other family, or recorded as not reviewed | INFRA-050 editorial_routing | the editorial board |
| F7 | An agent's function is never done by another | LAW-II: an agent "may not perform another agent's function" | the registry |

F7 bounds substitution, not skipping. FACT_CHECKER is already withheld under the local profile, with the Annex B.4 reasons.

**Rules that disagree (reported, not settled).**
- **D1 (LAW-III against the local profile).** LAW-III's text says "Local model output is audited by cloud models". The local profile audits local output by the other LOCAL family (Qwen against Phi). The layer cannot say which reading the floor follows.
- **D2 (INST_FINDER).** INST-SWITCH-A makes switching INST_FINDER off governed. INFRA-050 says a unit Python selects nothing in makes no call, which would let a selection skip INST_FINDER per unit once its narrowed form is adopted. Whether a layer's "unassigned" is a switch-off (governed) or a selection (INFRA-050) is not decided by the rules. This needs the lead's ruling, or Seckin's.

**Do the rules force every agent every time (D-573)?** Not as written. No rule quoted above requires SPEECH_ACT_TAGGER, LEGAL_ANALYST, ARCHIVIST or CITATION_RESOLVER to run on every document. Their constant presence comes from code lists (`PRODUCTION_AGENTS_PER_DOC`, `PRODUCTION_AGENTS_CORPUS_LEVEL`), not from a law or an amendment. The one rule that comes close is INST-SWITCH-A, for INST_FINDER alone (D2). So no rule-change section is needed beyond D1 and D2.

## 4. The chain for tables, from built rules (D-569, for the record)

1. **SPEECH_ACT_TAGGER.** INFRA-050 python_decides_first: "a run with no declared set makes no call". It reaches tables only once speech_act's form is adopted as decision, a recorded decision after measurement and not a DELTA. Until then, no built rule skips it.
2. **LEGAL_ANALYST.** INFRA-050 roles: one question per Python-selected (claim, passage). Same adoption condition. No built rule skips the wide form.
3. **Claims on cells.** JUDGE through JUDGE-AGENT-A and INFRA-049, already live under the cells declaration in the decision form (K1).
4. **PROCESSOR and VERIFIER.** These stay: F1 and F2.

Plainly: while the narrowed forms are `reply`, no built rule skips the wide roles on tables. The layer's structural skip (section 2) is the new rule. It touches governed structure only through D2.

## 5. 2c, for later (noted only)

NOT ENOUGH INFO first from evidence: a deterministic Python check that the cells or entities a claim names are absent from the table's labels, using `cell_selection`'s word matching, which is structural. Only what that check cannot settle is tuned, on a split of the dev set, with its error rate recorded (CHOICE-A).
