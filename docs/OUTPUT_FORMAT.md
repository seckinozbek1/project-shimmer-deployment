# Shimmer output format

Version: `output-format-v1-draft`

This document tells you what a Shimmer run writes and what each file means. It is written for whoever writes a scorer, without reading Shimmer's code. Every rule here describes what the code does today (branch `loop/s03`, commit `990ed88`, and the typed refusal kind of section 7.1 added by the S3 fix lane). All examples are invented. A source note, hidden in each section and collected in the "Sources" list at the end, names the code each statement was taken from.

It is a draft. It is kept current until it is frozen as `output-format-v1`. From the final run of the scorer's own calibration until the freeze, it changes only by additions that a scorer does not read. A change to a file or field a scorer reads is recorded as a defect to fix after the freeze, not made here.

The input side (documents, rules, answer keys) is described in `docs/INPUT_FORMAT.md`. Words defined there (unit, unit id, label, normalised label, figure, measure, band, REF id, operator's own id, registry id, relation, verdict, amendment) keep the same meaning here.

## 1. Words used throughout

<!-- Sources: scripts/run_context.py (module docstring, RunContext); scripts/message_bus.py; scripts/agent_wrapper.py (make_envelope, post_to_bus, run_task); scripts/finding_record.py (written_by, is_model_written). -->

- **Run**: one execution of Shimmer. A run writes only into its own **run folder**.
- **Run id**: the run's own identity, 32 lowercase hexadecimal characters (`3f9c...`). Read it from `audit/run_identity.json` (section 3.1), never from the folder name.
- **JSON** and **JSON Lines**: a JSON file holds one JSON value. A JSON Lines file (`.jsonl`) holds one JSON object per line; blank lines can be skipped.
- **Machine-readable** files are JSON or JSON Lines with the fields given here. **Human-facing** files are Markdown or Word documents written for a person. Their wording changes between versions and they are not described field by field. A scorer should read machine-readable files only.
- **The bus**: the run's message log, `logs/agent_bus.jsonl`. Every agent's output, Python's included, is posted there as one line.
- **Envelope**: the standard container an agent output travels in on the bus: `{"agent": ..., "doc_id": ..., "items": [...]}`.
- **Item**: one flat record inside an envelope. Flat means every value is a number, a string, a boolean, `null`, or a list of those; never a nested object.
- **Finding record** (finding): an item that carries a `relation` from the list in section 6.2 and a `record_verdict` field.
- **Written by**: who wrote a finding, `python` or `model` (section 5.4). Python is Shimmer's fixed code; the model is a language model.
- **Promoted**: turned into an amendment. Only Python's irregular findings are ever promoted.
- **Judging call**: one model call in the paired review about one unit and one rule (section 5.6).
- **Session folder**: on a rented cloud machine run, the folder on this machine that the run controller works in. It holds the downloaded run folder and the controller's own records (section 11).

## 2. Where the run folder is and what it is called

<!-- Sources: scripts/run_context.py (create_run, run_dirname, date_run_dirname, rename_run, start_run_in, for_run_dir, RunContext.ensure); scripts/pipeline.py (main: --output-dir handling, rename at end only when --output-dir is absent, _review_slug, _slug_from_question); tools/ordinary_final_run.py (execute: --output-dir evidence/run); tools/score_corpus.py (main: --run). -->

- **A run started on this machine** without an output folder is created as `output/runs/<YYYYMMDD>T<HHMMSS>Z__<run id>` (time in UTC).
- When an ordinary review or draft run reaches its end, the folder is renamed to `output/runs/<YYYY-MM-DD>__<slug>`. The slug of a review is `<N>doc_review`, where N is the number of documents under review (`1doc_review`). The slug of a draft is made from the draft question. If that name is taken, `__<run id>` is added. If the move fails, the folder keeps its first name.
- So a folder that still has its first name is either still running, stopped early, a multi-round run (which is never renamed), or one whose rename failed. The name proves nothing by itself; read `audit/run_completion.json` (section 4).
- **A run given an output folder** (`--output-dir`) writes into that folder and is never renamed. The server and the cloud runner do this.
- **A cloud run** writes its run folder on the rented machine as `evidence/run`. After collection and analysis it is at `<session folder>/downloaded/evidence/run/` (section 11).
- Two runs never share a folder.
- **What a scorer is given** is a run folder: the folder that holds `logs/`, `audit/` and, for an ordinary review, `deliverables/`. The repository's own scorer takes it as `--run <run folder>`.

## 3. Map of the run folder

<!-- Sources: scripts/run_context.py (RunContext paths, DELIVERABLE_FILENAMES, RUN_SUMMARY_NAME, DRAFT_MEMO_NAME, IDENTITY_FILENAME); scripts/run_completion.py (COMPLETION_NAME); scripts/pipeline.py (_inst_finder_startup_guard, main: convention assignment written after the multi-round branch, phase_6_synthesis, write_deliverables_run_summary call); scripts/pairing_map.py (write_pairing_map); scripts/convention_assignment.py (write_assignment); scripts/reference_builder.py (ReferenceIndex.save); scripts/reply_records.py; scripts/call_evidence.py; scripts/agent_activation.py; scripts/run_options.py (configure); scripts/multi_round.py (write_record); scripts/multi_round_rounds.py (RECORD_NAME); scripts/server.py (_write_status, multi-round request); scripts/audit_synthesizer.py; scripts/agent_wrapper.py (_persist_contract_violation_raw_text). -->

`<doc>` is a document id: the file name of a document under review without its extension (`price_list_k7.md` gives `price_list_k7`). If two documents share a name and differ only in extension, each id is `<name>__<extension>`.

| Path inside the run folder | Format | For | Section |
|---|---|---|---|
| `audit/run_identity.json` | JSON | machine | 3.1 |
| `audit/run_completion.json` | JSON | machine | 4 |
| `logs/agent_bus.jsonl` | JSON Lines | machine | 5 |
| `deliverables/<doc>/review_data.json` | JSON | machine | 7 |
| `deliverables/<doc>/review_findings.md` | Markdown | human | 7.5 |
| `deliverables/<doc>/tracked_changes.docx` | Word | human | 7.5 |
| `deliverables/<doc>/document_summary.md` | Markdown | human | 7.5 |
| `deliverables/<doc>/grounding_summary.md` | Markdown | human | 7.5 |
| `deliverables/<doc>/reviewed_document.md` | Markdown | human | 7.5 |
| `deliverables/<doc>/memo.md` | Markdown | human, draft runs only | 7.5 |
| `deliverables/_run_summary.md` | Markdown | human | 7.5 |
| `audit/pairing_map.json` | JSON | machine, ordinary reviews | 8.1 |
| `audit/convention_assignment.json` | JSON | machine, not in multi-round runs | 8.2 |
| `audit/reference_index.json` | JSON | machine | 8.3 |
| `logs/call_evidence.jsonl` | JSON Lines | machine | 8.4 |
| `audit/agent_switches.json` | JSON | machine | 8.5 |
| `audit/agent_activation.json` | JSON | machine | 8.6 |
| `audit/run_options.json` | JSON | machine | 8.7 |
| `audit/model_replies/<NNNNNN>_<call id>.json` | JSON, one per model call | machine | 9 |
| `audit/model_replies/outcomes.jsonl` | JSON Lines | machine | 9 |
| `audit/multi_round.json` | JSON | machine, multi-round runs only | 10 |
| `audit/round_reuse.json` | JSON | machine, multi-round runs only | 10 |
| `audit/audit_synthesis.md` | Markdown | human | 12 |
| `status.json` | JSON | machine, server runs only | 4.3 |

Other files exist (cost and telemetry logs, the editorial board's records, scheduling records, raw text of replies that broke their contract, and more). This format does not describe them, and a scorer must not depend on them. Section 12 lists the ones that exist today.

### 3.1 `audit/run_identity.json`

Written when the folder is created. `{"schema_version": 1, "run_id": "<run id>"}`. The run id never changes, even when the folder is renamed.

## 4. Did the run finish?

<!-- Sources: scripts/run_completion.py (RunCompletion, finish, tracked, read); scripts/pipeline.py (main: @run_completion_mod.tracked, completion.begin, every early return, completion.reached_end at the end of the ordinary path and of the multi-round path, return 5 on a redaction block); scripts/generation_observation.py (mark_incomplete); scripts/semantic_waves.py (merged partitions); scripts/server.py (_STATUS_FIELDS, _write_status); tools/ordinary_final_run.py (ARGV, MULTI_ROUND_ARGV); tools/score_corpus.py (_completeness_note). -->

### 4.1 `audit/run_completion.json`

Written as soon as the run folder exists, rewritten when the run ends.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | `1`. |
| `run_id` | string | The run id. |
| `state` | string | One of `running`, `completed`, `stopped`, `interrupted`, `failed` (below). |
| `started_at` | string | ISO 8601 time in UTC. |
| `finished_at` | string or null | ISO 8601 time in UTC; `null` while running. |
| `reached_end` | boolean | `true` only when the run finished all of its required work. |
| `exit_code` | integer or null | The run's exit code (section 4.2); `null` while running or when none was returned. |
| `document_count` | integer or null | Documents reviewed; set only when `reached_end` is `true`. In a multi-round run: the case documents loaded. |
| `amendment_count` | integer or null | Amendments written, over all documents; set only when `reached_end` is `true`. `0` in a multi-round run. |
| `error_type` | string or null | The name of the error type when the run raised one, such as `RuntimeError`. Never the error's message. |
| `semantic_complete` | boolean, optional | Present, and `false`, when the run used the `report_optimized` schedule (an ordinary cloud run does; a multi-round cloud run does not) and a model answer it needed failed or came back incomplete. |

**The states.**

| `state` | Meaning |
|---|---|
| `running` | The run started and no end was recorded. Either it is still running, or it was killed (a hard kill, a power loss, or the cloud runner's budget stop) and never wrote an end. |
| `completed` | The run reached its end and returned exit code 0. The only state that means success. |
| `stopped` | The run returned without an error but is not `completed`: it refused at start, stopped on purpose, returned a nonzero exit code, or reached its end with `semantic_complete: false`. |
| `interrupted` | The run was stopped by an interrupt or by an exit request. |
| `failed` | The run raised an error. `error_type` names it. |

**A record is valid** only when `schema_version` is 1 and `state` is one of the five values; and, for `completed`, `reached_end` is `true`, `exit_code` is the integer 0, and `finished_at` is a non-empty string. Treat an invalid or missing record as "completion unknown".

**How to recognise a run that did not succeed.** Any one of these:

- `audit/run_completion.json` is missing, unreadable, invalid, or has a state other than `completed`.
- `semantic_complete` is `false`.
- No `deliverables/<doc>/review_data.json` exists for an ordinary review. Missing deliverables mean "no measurement", not "zero findings".
- In a cloud run, `evidence/result.json` says `execution_integrity_passed: false`, or `evidence/terminal_error.json` exists (section 11).

A run that refuses before its folder exists (an invalid command line, an invalid multi-round manifest) leaves no run folder at all.

### 4.2 Exit codes

| Code | Meaning |
|---|---|
| 0 | Normal end. Also returned when the operator answers "no" at an interactive prompt; then `reached_end` is `false` and `state` is `stopped`. |
| 2 | The command line was refused (no run folder is written). |
| 3 | A model in the registry is deprecated; the run stops for the operator. |
| 4 | The redaction gate refused to start. |
| 5 | A draft run had no question or produced no memo, or the privacy redaction blocked a deliverable. |
| 6 | The privacy layer is inactive and the run was not declared non-sensitive. |
| 7 | The operator declined to continue at a governance check. |
| 8 | A multi-round run was refused (section 10). |
| 9 | `SHIMMER_INST_FINDER=off` was set without the required approval (section 8.5). |
| 124 | Cloud runs only, and not a pipeline code: the cloud runner's budget stop ended the whole process. It appears as `exit_code` in the session folder's `workload_return.json` (section 11). The run folder then still says `running`. |

### 4.3 `status.json` (server runs only)

A run started through the server also has `status.json` at the top of the run folder, written on every job change. Fields: `run_id`, `status` (`queued`, `running`, `completed`, `failed` or `interrupted`), `task`, `submitted_at`, `started_at`, `completed_at`, `exit_code`, `error`, `progress`, `files`, `sensitive`, `review_mode`, `question`, `intake_mode`, `review_targets`, `prior_files`, `native_intake`, `input_language`, `output_language`, `agent_briefs`, and `multi_round: true` on a multi-round job. It records the server's process state only. `audit/run_completion.json` is the record of whether the run's work finished.

## 5. The bus: `logs/agent_bus.jsonl`

<!-- Sources: scripts/message_bus.py (MessageBus.post, _validate, VALID_TYPES, VALID_ROLES); scripts/agent_wrapper.py (post_to_bus, run_task: AGENT_OUTPUT, CONTRACT_VIOLATION, BACKEND_ERROR, items_are_advisory withholding, contract_normalized; make_envelope; current_items); scripts/pipeline.py (_paired_convention_review: consume_judgment, advisory only for plans other than absence_judged, computed post with backend paired and judging_calls, PAIRED_JUDGING_CALLS post, stamped judged post; _stamped_judged_items; _prior_comparison: backend computed; phase_6_synthesis: AMENDMENT_REFUSED); scripts/paired_review.py (judging_call_record, JUDGING_OUTCOMES, JUDGED_ABSENCE_PLAN, plan_calls plan kinds, stamp_note_writer, note_models); scripts/multi_round_rounds.py (post_findings, bus_envelopes); scripts/multi_round_phase.py (MULTI_ROUND_REVIEWED); scripts/finding_record.py (is_finding, written_by, COMPUTED_BACKENDS); tools/score_corpus.py (_load_bus_findings). -->

The bus is append-only: one JSON object per line, in the order posted.

### 5.1 One line

| Field | Type | Meaning |
|---|---|---|
| `timestamp` | string | ISO 8601 time in UTC. |
| `sender` | string | The agent name the post is made under, such as `PRACTICE_AUDITOR`. Python's own records are posted under an agent's name too (section 5.4). |
| `sender_role` | string | `agent`, `supervisor`, `orchestrator` or `operator`. |
| `recipient` | string | Usually `ORCHESTRATOR`. |
| `channel` | string | `main` for the ordinary review, `multi_round` for a multi-round run, `escalation` for operator escalations; other values exist. |
| `type` | string | The message type. Findings travel in `INFORM` messages. Other values: `PROPOSE`, `REQUEST`, `OFFER`, `CHALLENGE`, `YIELD`, `BLOCK`, `CONFIRM`, `ESCALATE`, `MEMORY_HIT`, `DEDUP_ALERT`, `CHARTER_PROPOSE`, `CHARTER_APPROVE`, `CHARTER_DENY`, `DISSOLVE`, `PRECEDENT_APPLIED`, `LAW_CREATED`, `API_DISCOVERED`. |
| `body` | object | The content (section 5.2). |
| `constitution_check` | object | A governance record; not needed for scoring. |
| `uncertain` | boolean | Usually `false`. |

### 5.2 The body of an agent output

A line whose `body.event` is `AGENT_OUTPUT` carries an agent's result:

| Field | Type | Meaning |
|---|---|---|
| `event` | string | `AGENT_OUTPUT`. |
| `backend` | string | Where the result came from. `paired` or `computed` for Python's own records; otherwise the model backend's name. |
| `model` | string | `python` (or a value starting `python`) for Python's own records; otherwise the model's id. |
| `item_count` | integer | How many items the result had. |
| `payload` | object | The envelope: `agent` (string), `doc_id` (string: the document id, or the case id in a multi-round run's reviewed records), `items` (list of items). |
| `call_id` | string, optional | The model call's id (32 hexadecimal characters). Joins the bus to section 9 and to `logs/call_evidence.jsonl`. Absent on posts Python makes itself, including the stamped copies of section 5.5. |
| `truncated` | boolean or null, optional | `true` when the model's reply was cut off. |
| `contract_normalized` | list, optional | On a model reply: the key spellings Python read as a declared field (for example `confident` read as `confidence`). Empty when none. |
| `note_models` | list of strings, optional | On Python's paired posts: the models whose sentences sit in these records as notes. |
| `judging_calls` | list of objects, optional | On Python's paired post (backend `paired`): every judging call this agent made on this document, kept note or not (section 5.6). This is the one body field that holds objects; it is not an item. |
| `stamped_by`, `absence_path` | strings, optional | On a judged-absence post (section 5.5): `python` and `judged`. |
| `items_withheld`, `items_withheld_reason` | optional | On an advisory model reply: the reply's items were withheld, `items` is empty, and `items_withheld` counts them. |

Other `body.event` values carry no findings:

- `CONTRACT_VIOLATION`: a model reply that broke its required shape. It carries the first 400 characters of the reply and `missing_fields`.
- `BACKEND_ERROR`: a model call that failed.
- `AMENDMENT_REFUSED`: Python could not build an amendment from a finding. Each item is `{"item": <the finding>, "reason": ..., "unit_id": ..., "rule_id": ..., "severity": ...}` and is not itself a finding.
- `PAIRED_JUDGING_CALLS`: `{"event", "backend": "paired", "model": "python", "doc_id", "judging_calls"}`, with no `payload`. Posted for an agent whose judging calls produced no finding Python computed, so its calls are still on the record (section 5.6).
- `MULTI_ROUND_REVIEWED` (section 10), and others.

### 5.3 Finding a run's findings

Read every line. For each line whose `body.payload.items` is a list, every item that has a `relation` from the list in section 6.2 and has a `record_verdict` field is a finding. Nothing else is. Whether a scorer counts a model's findings, and a judged absence's two copies, is the input format's rule (its section 9, "Which findings count").

- The envelope's `doc_id` says which document the finding is about. Findings themselves do not carry it.
- Every item also carries `item_id` (string), `revision` (integer, 1 unless superseded) and `ts` (time). An item supersedes an earlier one only within the same agent and document: the same envelope `agent`, the same envelope `doc_id` and the same `item_id`, with a higher `revision` (a later `ts` breaks a tie). Items with the same `item_id` under another agent or another document are different items. Python posts each of its own envelopes once per document per step.

### 5.4 Who wrote a finding

A finding carries no reliable field that says who wrote it. It is decided from the line it travelled in:

- **`python`** when `body.backend` is `paired` or `computed` **and** `body.model` starts with `python`.
- **`model`** in every other case, including a missing backend or model.

Never decide it from the agent name: Python's records are posted under agent names such as `PRACTICE_AUDITOR`. A finding's `provenance` field is not the test either: Python sets `provenance: "computed"` only on change records (section 6.5) and multi-round round findings, not on its other findings, and a model can write the field itself.

### 5.5 Repeats on the bus

The same claim can appear more than once.

**Judged absence.** A judged absence is a model's answer to the question whether one unit meets one scoped rule. Unlike every other judging call, its reply is posted with its items, because the model's answer is the record. It then appears twice:

1. The model's reply as it wrote it: an ordinary `AGENT_OUTPUT` line with the model's backend and model, a `call_id`, and the items exactly as the model wrote them (the `unit_id` may be wrong or missing). Written by `model`.
2. If Python kept the answer, a copy on a second line: same backend and model (so still written by `model`), no `call_id`, `stamped_by: "python"` and `absence_path: "judged"` on the body. In each copied item Python sets `unit_id` to the unit it asked about, `absence_path: "judged"`, `revision: 1` and an `item_id` of the form `<agent>:finding:<unit id>:<rule id>:<n>`. It fills `rule_id` and `source_rule_id` only when the model left them out; a value the model wrote stays.

Python refuses a `missing_field` answer that gives no quote, names no field, or names a field the unit carries, and any answer that quotes text the unit does not contain. A refused answer appears only in the first line. The refusals are listed in `audit/pairing_map.json` under `absence_refused` (section 8.1).

To tell the two lines apart: the second has `body.stamped_by`. To find the first: its `body.call_id` appears in the pairing map's `judging_calls` with `plan_kind` `absence_judged` (section 5.6).

**Multi-round runs.** Round findings reused from an earlier round appear once per round (section 10).

### 5.6 Judging calls

In the paired review, Python asks a model about one unit and one rule only where its own checks call for it. Every such call is recorded as one flat object, in two places: the `judging_calls` list of the agent's paired post on the bus (or of its `PAIRED_JUDGING_CALLS` post), and the document's `judging_calls` list in `audit/pairing_map.json`. The number of records equals the pairing map's `calls_made`.

| Field | Type | Meaning |
|---|---|---|
| `call_id` | string | The model call's id; `""` when none was recorded. |
| `agent` | string | The agent asked. |
| `unit_id`, `rule_id` | strings | The unit and the registry id of the rule asked about. |
| `plan_kind` | string | Why the call was made: `computed` (Python found a disagreement and asks for a note), `band` or `duration` (a band or date-window comparison), `uncomputable` (Python could compute nothing for the pair), `absence_judged` (a judged absence, section 5.5). |
| `backend`, `model` | strings | The model that answered; `""` when unknown. |
| `notes_kept` | integer | How many of Python's findings carry this call's sentence as a note. |
| `absence_listed`, `absence_refused` | integers | On a judged absence: the answers Python kept and the answers it refused. `0` otherwise. |
| `outcome` | string | What became of the reply (below). |

| `outcome` | Meaning |
|---|---|
| `note_kept` | The call's sentence is attached to at least one of Python's findings as a note. |
| `no_note_returned` | The reply carried no sentence. |
| `no_finding_to_attach` | Python found no disagreement on this unit and rule, so the sentence was not kept. |
| `advisory_not_kept` | Python could compute nothing for the pair; the reply was kept neither as a finding nor as a note. |
| `reply_failed` | The call failed. |
| `judged_absence` | A judged-absence call that returned. Its counts are in `absence_listed` and `absence_refused`. |

A judging call never changes a figure. Its reply's own items are withheld from the bus (`items_withheld`), except for a judged absence.

## 6. The Finding record

<!-- Sources: config/agent_contracts.json (finding_record: fields, required, relations, verdicts, says); scripts/finding_record.py (module docstring, is_finding, validate_finding, PRIOR_RELATIONS, ABSENCE_RELATIONS, resolved_rule_id, RULE_ID_FIELD_ALIASES, source_rule_id_for); scripts/paired_review.py (compute_checks, finding_from_check, RELATION_DETAIL_FIELDS, _close, ABS_TOLERANCE, REL_TOLERANCE, _unit_str, unit_exponents, prior_checks, absent_checks, prior_findings, plan_calls, disagreements, stamp_note_writer, computed_sentence, unit_ref_for, unit_passage_refs, opens_with); scripts/pairing_map.py (unmatched_findings); scripts/pipeline.py (_paired_convention_review, _stamp_source_rule_ids, _stamped_judged_items); scripts/multi_round_rounds.py (_findings_for_plans). -->

### 6.1 Fields

| Field | Type | Meaning |
|---|---|---|
| `rule_id` | string | The **registry id** of the rule, `CONV-` followed by digits (`CONV-001`). Required. A model-written item may name its rule under `procedure_id`, `conv_id` or `convention_ref` instead; read them in that order when `rule_id` is missing. |
| `source_rule_id` | string, optional | The **operator's own id** of the rule, in upper case (`CONV-P01`), as written on its heading. Use this one to compare with an answer key. Present on every Python finding of an ordinary review whose rule has an operator's own id. Left out (absent, never `""`) on multi-round round findings (section 10.2). |
| `unit_id` | string | The unit id (input format, section 2): `u00-...` for the preamble, `u01-...` and so on. Required. On a model-written item it is whatever the model wrote. |
| `relation` | string | The kind of finding (section 6.2). Required. |
| `record_verdict` | string | `irregular` (a problem) or `ok` (information only). Required. Python writes it in lower case; compare without case. A model may write another value. |
| `field_label` | string, optional | The field the finding is about, as its **normalised label**: the normalised words joined by single spaces (`line total`). A table cell adds ` row` and a number (`line total row2`). |
| `value_a`, `unit_a` | number, string, optional | The first figure and its measure (section 6.3). |
| `value_b`, `unit_b` | number, string, optional | The second figure and its measure. |
| `source_refs` | list of strings | The REF ids (`REF-0012`) or web REF ids (`WEB-REF-0003`) the finding cites. On Python's review findings: the passage of the finding's own unit when Python could place it, otherwise empty (the finding then sits at document level). Python places a unit when exactly one passage of the document has the unit's first line (its heading, or a preamble's first line) as its own first line, spaces folded. On change records: the earlier version's passage. On multi-round round findings: empty. |
| `compared_with_refs` | list of strings, optional | Where the figure it was compared with came from: a reference table, a bound sentence, or the earlier version's statement. |
| `conditional_on` | list of strings, optional | On a `below_band` finding whose low side the rule qualifies: the normalised labels of the condition. Such a finding is never promoted. |
| `explanation` | string | A sentence for a human reader. Do not parse it. |
| `explanation_by` | string, optional | `model` when the sentence in `explanation` was written by a model (then also `explanation_model`, `explanation_backend`, `explanation_call_id` when known). Absent when Python wrote the sentence. The figures are Python's either way. |
| `delta` | number, optional | `value_a` minus `value_b`, on change records. |
| `band_distance_change` | number, optional | On change records oriented by a band: the distance to the band now minus the distance then. Negative is toward the band. |
| `addend_field`, `addends` | string, list of numbers, optional | On `sum_mismatch`: the column summed and the values added. |
| `factor_fields`, `factors` | lists, optional | On `product_mismatch`: the two labels multiplied and their values. |
| `absence_path` | string, optional | On an absence: `computed` (Python decided a field declared in `[requires: ...]` is missing) or `judged` (a model answered, section 5.5). |
| `provenance` | string, optional | `computed` on change records and multi-round round findings. |
| `quote` | string, optional | On a model's absence claim: the words it relied on. |
| `round_id` | string, optional | On multi-round round findings on the bus: the round. |
| `ref`, `kind`, `confidence` | strings | Envelope bookkeeping. On Python's findings: the first cited REF id or `document-level`, `finding`, and `CONFIDENT`. |
| `item_id`, `revision`, `ts` | string, integer, string | Section 5.3. |

Python always writes figures as JSON numbers. A model-written item may hold a string in a figure field; treat a value that is not a number as not matching any number.

### 6.2 Relations and verdicts

The complete list of relations: `sum_mismatch`, `above_band`, `below_band`, `missing_field`, `product_mismatch`, `ratio_out_of_range`, `date_window`, `licence_missing`, `changed_from_prior`, `unchanged_from_prior`, `moved_toward`, `moved_away`, `absent_since_prior`.

- Python writes a finding only where its computation **disagrees**, with `record_verdict: "irregular"`, except for the five change-record relations (`changed_from_prior`, `unchanged_from_prior`, `moved_toward`, `moved_away`, `absent_since_prior`), which are always `ok`.
- `ratio_out_of_range` and `licence_missing` are model-only relations: Python never writes either. A ratio outside a band is written by Python as `above_band` or `below_band`. Any finding with one of these two relations is written by `model`.

### 6.3 Location, rule, figures, relation, verdict and provenance

- **Location** is `unit_id`, together with the envelope's `doc_id`. `source_refs` cites the unit's passage; it is not the location.
- **Rule** is `source_rule_id` (the operator's own id) and `rule_id` (the registry id). Section 8.2 maps one to the other for every rule of an ordinary review.
- **Figures** are `value_a` and `value_b` with their measures `unit_a` and `unit_b`. What each one holds depends on the relation:

| Relation | `value_a` / `unit_a` | `value_b` / `unit_b` | `field_label` |
|---|---|---|---|
| `sum_mismatch` | the computed sum / the column's measure | the stated total / its measure | the total's label |
| `product_mismatch` | the computed product / the product's measure | the stated figure / its measure | the stated figure's label |
| `above_band`, `below_band` | the figure or the ratio / the band's measure | the bound crossed (the high bound for `above_band`, the low bound for `below_band`) / the band's measure | the figure's label; absent for a ratio |
| `date_window` | the gap between the two dates / `hours` or `days` | the bound / the same | the first date's label |
| `missing_field`, declared field missing | `0` / `values` | `1` / `required` | the missing field's label |
| `missing_field`, blank cells | the number of cells holding a number / `values` | the number of body rows / `rows` | the column's label |
| `missing_field`, "no rule applies" | absent | absent | absent; `source_refs` is empty |
| `unchanged_from_prior`, `changed_from_prior`, `moved_toward`, `moved_away` | the figure now / its measure | the earlier figure / its measure | the field's label |
| `absent_since_prior` | absent | the earlier figure / its measure | the field's label |

- A computed sum, product or ratio is rounded to 6 decimal places. Two figures are the same when they differ by at most 0.000000001, or by at most one millionth of the larger in absolute value.
- **Measures are strings, and their spelling varies.** A measure copied from the document stays as written (`EUR/box`, `EUR / box`). A measure Python computed is written in a fixed form: parts sorted, joined by `*`, powers as `^2`, a divisor after `/` (`EUR/box`, `1/box`, `m^2`). A figure with no measure has the measure `1`. Both forms occur in the same run. Compare measures by their parts, as the input format (section 2) does, never as strings.
- **Relation** is `relation`.
- **Verdict** is `record_verdict`.
- **Provenance** is decided from the bus line (section 5.4). In `review_data.json` it is stamped as `written_by` (section 7).

### 6.4 Example

An invented bus line (shortened where it says `...`, and spread over several lines here; on disk it is one line). Python found that 4 `box` times 12 `EUR/box` is 48 `EUR` on a unit that states a line total of 52 `EUR`. One judging call was made about the pair and returned no sentence:

```json
{"timestamp": "2026-10-27T09:14:02.511204+00:00", "sender": "PRACTICE_AUDITOR",
 "sender_role": "agent", "recipient": "ORCHESTRATOR", "channel": "main", "type": "INFORM",
 "body": {"event": "AGENT_OUTPUT", "backend": "paired", "model": "python", "item_count": 1,
   "parse_trace": {}, "note_models": [],
   "payload": {"agent": "PRACTICE_AUDITOR", "doc_id": "price_list_k7", "items": [
     {"ref": "REF-0005", "kind": "finding", "confidence": "CONFIDENT",
      "rule_id": "CONV-001", "source_rule_id": "CONV-P01", "unit_id": "u02-item-p-101",
      "relation": "product_mismatch", "record_verdict": "irregular",
      "value_a": 48.0, "unit_a": "EUR", "value_b": 52.0, "unit_b": "EUR",
      "field_label": "line total", "factor_fields": ["quantity", "unit price"],
      "factors": [4.0, 12.0], "source_refs": ["REF-0005"], "explanation": "...",
      "ts": "2026-10-27T09:14:02.510977+00:00", "revision": 1,
      "item_id": "PRACTICE_AUDITOR:finding:REF-0005:0"}]},
   "judging_calls": [
     {"call_id": "5d0c...", "agent": "PRACTICE_AUDITOR", "unit_id": "u02-item-p-101",
      "rule_id": "CONV-001", "plan_kind": "computed", "backend": "...", "model": "...",
      "notes_kept": 0, "absence_listed": 0, "absence_refused": 0,
      "outcome": "no_note_returned"}]},
 "constitution_check": {"result": "RESOLVED", "...": "..."}, "uncertain": false}
```

`backend` is `paired` and `model` is `python`, so this finding is written by `python`. A number may be written with or without a decimal part (`48` or `48.0`); compare numbers, not text.

### 6.5 Change records

The five change-record relations compare the document with its declared earlier version. They are Python's, `ok`, never promoted, and carry `provenance: "computed"`, `field_label`, `delta` (except `absent_since_prior`), and `compared_with_refs` and `source_refs` naming the earlier version's passage. Their bus line has backend `computed` and model `python`. Comparisons Python refused are not findings; they are listed in `review_data.json` (section 7.1) and `audit/pairing_map.json`.

## 7. The deliverables folder

<!-- Sources: scripts/run_context.py (DELIVERABLE_FILENAMES, RUN_SUMMARY_NAME, DRAFT_MEMO_NAME, doc_deliverables_dir); scripts/pipeline.py (phase_6_synthesis: _process_doc, stamp_written_by before any copy, model_findings, computed_findings, _promotable, ensure_amendments_for_findings call, amendments_payload, _prior_records filtered by is_model_written, _prior_refusals_for, _prior_orphans_for, draft memo copy; _harvest_amendment_payloads_from_bus and its call before any per-document step); scripts/amendment_render.py (CANONICAL_CONTENT_KEYS, MODEL_FINDINGS_KEY, write_amendment_deliverables, render_model_findings); scripts/paired_review.py (computed_finding_items, ensure_amendments_for_findings, amendment_from_finding, _severity_makes_amendment, unit_passage_refs, COMPUTED_PROVENANCE_WITH_NOTE, ABSENCE_PROVENANCE_WITH_NOTE); scripts/finding_record.py (stamp_written_by, is_model_written, model_finding_for_reader, MODEL_FINDING_MARK, CHECKED_SOUNDING_FIELDS); scripts/docx_builder.py (comment_author, COMPUTED_AUTHOR, anchor_span); scripts/pairing_map.py (unmatched_findings); tools/score_corpus.py (_load_review_data, _load_amendments). -->

`deliverables/` holds one folder per document under review, named by its document id, and `_run_summary.md`. The file names inside are fixed:

| Key in the code | File name | For |
|---|---|---|
| `amendments_json` | `review_data.json` | machine: the **master** record (below) |
| `amendments_md` | `review_findings.md` | human: the master rendered |
| `amendments_docx` | `tracked_changes.docx` | human: the amendments as tracked changes |
| `operative_summary` | `document_summary.md` | human |
| `context_summary` | `grounding_summary.md` | human |
| `per_agent_deliverable` | `reviewed_document.md` | human |

A draft run also keeps the generated memo as `memo.md`. A multi-round run writes no deliverables.

### 7.1 `review_data.json`

One JSON object per document:

| Field | Type | Meaning |
|---|---|---|
| `document_id` | string | The document id. |
| `amendments` | list | The amendments (section 7.2). |
| `prior_comparisons` | list of findings | Python's change records for this document (section 6.5), each stamped `written_by: "python"`. Only records stamped as Python's enter; a record that carries `provenance: "computed"` but was not posted as Python's is left out. Empty when no earlier version was declared. |
| `prior_refusals` | list | Change records Python refused: `{"unit_id", "label", "reason", "reason_kind"}`. |
| `prior_orphans` | list | Earlier-version labels whose heading has no counterpart now: `{"label", "unit_slug", "reason", "reason_kind"}`, `reason_kind` always `orphan`. |
| `model_findings_not_promoted` | list | Every finding a model wrote for this document (section 7.4). |
| `_validator_errors` | list of strings | Problems the amendment check found. Normally empty. |

`label` in these lists is a normalised label (empty when a whole table of the earlier version was refused). `reason` is a sentence for a human: do not parse it. `reason_kind` is the typed kind of the refusal, one of:

| `reason_kind` | Why the comparison was refused (input format, section 6) |
|---|---|
| `possible_rename` | The label vanished and a label new in its section has a figure within 2% in the same non-empty measure. |
| `possible_successor` | The label vanished and a label new in its section, in the same measure, is not claimed by a rename. |
| `possible_successor_no_unit` | The same, where neither figure has a measure. |
| `tie` | The earlier version states the label with differing figures, even under the heading with the same slug; or two table rows match it. |
| `reverse_tie` | Several labels of the document match one row of an earlier table. |
| `no_citation` | The earlier statement has no REF id (past the indexed paragraphs). |
| `unit_mismatch` | The two figures' measures differ, or one is empty. |
| `disagreeing_bands` | Two or more distinct bands orient the change (the record is still written, as `changed_from_prior` or `unchanged_from_prior`). |
| `no_key_column` | An earlier table has no key column identifying its rows. |
| `value_column_count` | An earlier table does not have exactly one value column. |
| `no_rule` | No paired rule can be cited for the comparison. |
| `orphan` | In `prior_orphans` only: the earlier heading has no counterpart. |

An answer key's `expected_refusals` (input format, section 9) names the kind it expects. A run older than the S3 fix lane has no `reason_kind`.

### 7.2 Amendments

An amendment is built by Python from one of **its own** irregular findings. A model's finding never becomes one. Rules:

- One amendment per pair of (unit id, registry rule id). If Python has several irregular findings for the same pair, the amendment is built from the first one Python lists and carries that finding's figures only. The others make no amendment, and stay on the bus. So read the bus (section 5.3) for every finding Python made; an amendment shows one of them.
- No amendment comes from an `ok` finding, from a finding with `conditional_on`, or from a finding under an `[advisory]` rule or a rule whose severity is not recognised. Each irregular finding of these kinds is listed on the bus in an `AMENDMENT_REFUSED` post instead (section 5.2).
- A "no rule applies" `missing_field` finding does become an amendment.

| Field | Type | Meaning |
|---|---|---|
| `finding_unit_id` | string | The unit id of the finding: the amendment's **location** for scoring. |
| `finding_rule_id` | string | The registry id of the finding's rule. |
| `convention_ref` | string | The same registry id. |
| `source_convention_ref` | string, optional | The operator's own id, upper case. Use this for attribution. |
| `finding_relation` | string | The finding's relation. |
| `finding_field_label` | string or null | The finding's `field_label`. |
| `finding_value_a`, `finding_unit_a`, `finding_value_b`, `finding_unit_b` | number or null, string or null | The finding's figures and measures, copied unchanged. |
| `derived_from` | string | Always `computed_finding` in the current code. |
| `agent` | string or null | The agent name the finding was posted under. |
| `location` | string | The REF id of the unit's own passage, or `document-level` when Python could not place it (section 6.1, `source_refs`). |
| `ref_ids` | list of strings | The REF ids cited: the unit's passage first, or, at document level, only the compared passages. |
| `original_text` | string | The whole text of the unit, or `unit id <id> (text not available)`. |
| `proposed_text` | string or null | A corrected line, only when the optional wording pass supplied one. |
| `action` | string | Always `flag`. |
| `comment` | string | Sentences for a human: the figures first, then how they were checked, the citation, the rule's words, and any model note, marked as the model's. Do not parse it. |
| `severity` | string | Always the fixed value `required`, whatever the rule's severity (section 13, point 3). Do not read a rule's severity from it. |
| `finding_type` | string | Always `factual`. Not the relation. |
| `ref`, `kind`, `confidence` | strings | Bookkeeping: the location again, `amendment`, and normally `CONFIDENT`. |
| `unit_id_repaired_to` | string, optional | Present when the finding's unit id matched no unit and Python found it written inside exactly one unit. The amendment then sits on this unit (its `original_text` is this unit's text): read it as the location instead of `finding_unit_id`. The repository's scorer does not read it; it matches a key's unit against `finding_unit_id` and `original_text`. |

The amendment built from the finding in section 6.4 carries, among its other fields:

```json
{"finding_unit_id": "u02-item-p-101", "finding_rule_id": "CONV-001",
 "convention_ref": "CONV-001", "source_convention_ref": "CONV-P01",
 "finding_relation": "product_mismatch", "finding_field_label": "line total",
 "finding_value_a": 48.0, "finding_unit_a": "EUR", "finding_value_b": 52.0, "finding_unit_b": "EUR",
 "derived_from": "computed_finding", "location": "REF-0005", "action": "flag", "severity": "required"}
```

Amendments for a run are every `amendments` list over every `deliverables/<doc>/review_data.json`.

### 7.3 Python's findings that are not in `review_data.json`

`review_data.json` does not list Python's irregular findings. They are on the bus (section 5), and those that were promoted are visible through their amendments. Read the bus for every Python finding, including those that made no amendment.

### 7.4 Model findings: `model_findings_not_promoted`

Every finding a model wrote for the document, irregular or not, is kept here and marked. None became an amendment. "A model wrote it" means it was not posted as Python's (section 5.4); a finding no post can be shown to own counts as a model's. Each entry is the model's item with these changes:

- `written_by` is `model`, `promoted` is `false`, `checked_by_python` is `false`.
- `record_verdict`, `verdict`, `confidence` and `provenance` are removed. The verdict the model claimed is kept as `model_claimed_verdict`.
- `agent` names the agent it came from.
- `figures_in_unit` is `true` when every figure it states is a number written in the unit it names, `false` when one is not, and `null` when that cannot be checked.
- `reader_notes` is a list of sentences Python adds for a human (for example, that it cites another unit's passage).
- `source_rule_id` is added when the rule has an operator's own id.

In the Markdown files every such finding carries the sentence "Written by a model. Not promoted to an amendment. Not checked by Python."

### 7.5 The human-facing files

`review_findings.md` and `tracked_changes.docx` are renders of `review_data.json` and add nothing to it. `tracked_changes.docx` shows amendments only, and may be missing if the Word library is not installed. Each of its comments names its author by provenance (an amendment built from Python's finding is authored "Shimmer / computed by Python"), and an amendment whose passage spans several paragraphs is anchored across them. `document_summary.md`, `grounding_summary.md`, `reviewed_document.md`, `memo.md` and `_run_summary.md` are summaries for a person; `reviewed_document.md` also lists each agent's judging calls in words. Their wording depends on the run's output language (section 8.7). Do not score from them.

## 8. Other machine-readable files in `audit/` and `logs/`

<!-- Sources: scripts/pairing_map.py (pair_units, build_pairing_map, unmatched_findings, write_pairing_map); scripts/pipeline.py (_paired_convention_review: band_conditions, not_judged, reattributed, absence, absence_refused, calls_made, judging_calls, suspended; _prior_comparison: prior_comparisons, prior_orphans; main: convention assignment written with source_rule_id, after the multi-round branch; _inst_finder_switch, _inst_finder_startup_guard); scripts/paired_review.py (judging_call_record); scripts/convention_assignment.py (assign_conventions, write_assignment); scripts/reference_builder.py (ReferenceEntry, WebReferenceEntry, ReferenceIndex.save, index_document); scripts/call_evidence.py (RECORD_FIELDS, extract, record); scripts/agent_activation.py (ActivationAudit, STATE_WORDS); scripts/run_options.py (Options, configure). -->

### 8.1 `audit/pairing_map.json`

Written in every ordinary review, before any agent is asked. One object keyed by document id.

**Which review mode ran.** No field of the run folder names the review mode. A paired run's pairing map carries the paired-review fields below (`calls_made`, `judging_calls`); a wide run's does not. A server run also names it in `status.json` (`review_mode`). A cloud run is always paired: the cloud tool passes `--review-mode paired`.
 The document fields from `not_judged` to `judging_calls`, and each unit's `band_conditions`, are added by the paired review only. For each document:

| Field | Meaning |
|---|---|
| `document_id`, `unit_count`, `rule_count` | Counts. |
| `field_vocabulary` | Every normalised label of the document. |
| `units` | One entry per unit, in document order (below). |
| `unmatched_units` | Unit ids no rule paired with. |
| `missing_field_findings` | The "no rule applies" findings, as findings. |
| `pair_count`, `rejected_count`, `undecided_count`, `semantic_pairing` | Pairing counts; `semantic_pairing` is `null` unless some rule could not be placed. |
| `not_judged`, `not_judged_count` | Planned questions no agent could take: `{"unit_id", "rule_id", "kind", "reason", "consumer_agents", "status"}`, sometimes with `reattribution_blocked_by`. |
| `reattributed` | Findings moved to another rule: `{"unit_id", "from_rule_id", "to_rule_id", "kind"}`. |
| `suspended`, `suspended_count` | Present when an `[unless: ...]` switched a rule off on a unit: `{"unit_id", "rule_id", "source_rule_id", "detail"}`. |
| `absence` | Every absence decided: `{"unit_id", "rule_id", "field", "path"}` with `path` `computed` or `judged`; a judged entry also has `items` (answers kept) and `call_id`. |
| `absence_computed_count`, `absence_judged_count`, `absence_refused`, `absence_refused_count` | `absence_refused` lists judged answers Python refused: `{"unit_id", "rule_id", "relation", "reason"}`. |
| `calls_made` | Model calls made in this step. |
| `judging_calls` | One record per call made (section 5.6). Its length equals `calls_made`. |
| `prior_orphans` | As in section 7.1, when an earlier version was declared. |

A unit entry: `unit_id`, `title` (the heading), `kind` (`preamble` for the preamble unit), `index` (position), `fields_present` (normalised labels), `paired` and `rejected` (lists of `{"rule_id", "reason", ...}`), `undecided` (rule ids), `band_conditions` (what the band check could decide), and `prior_comparisons` (`hit_count`, `checks`, `refused`) when an earlier version was declared.

### 8.2 `audit/convention_assignment.json`

Which agent each rule was routed to. Written in every ordinary run; not written in a multi-round run. `by_rule` maps each registry id to `{"subjects", "agents", "consumer_agents", "status", "source_rule_id"}`. `source_rule_id` is the operator's own id in upper case, or `""` when the rule has none. **This is the map from registry ids to operator's own ids.** `status` is `untagged`, `assigned`, `assigned_no_consumer` or `unassigned`. `by_agent` maps each agent to its rule ids.

### 8.3 `audit/reference_index.json`

Every REF id of the run. `entries` is a list of `{"ref_id", "input_type", "document_id", "document_name", "location", "text_excerpt", "cited_by", "first_indexed"}`. `input_type` is `context` (the reference corpus and the earlier version), `operational` (a document under review, or a multi-round source span) or `convention`. `location` holds `paragraph` (from 1), `page` (an estimate), `sentence`, `char_start` and `char_end`, or, for a multi-round span, `char_start`, `char_end` and `unit_id`. `text_excerpt` is the stored passage (input format, section 7). `cited_by` names the agents and deliverables that cite it. `web_references` lists web REF ids the same way.

### 8.4 `logs/call_evidence.jsonl`

One line per model call, written just before the call. It records identifiers only, never text: `call_id`, `run_id`, `ts`, `phase`, `doc_id`, `agent`, `backend`, `model`, `task`, `payload_document_id`, `unit_id`, `neighbour_unit_ids`, `heading_unit_id`, `document_unit_ids`, `reference_ids`, `reference_ids_rendered`, `rule_ids`, `rule_ids_rendered`, `payload_rule_id`, `convention_text_truncated`, `reference_text_truncated`, `bus_messages_rendered`, `bus_messages_dropped`, `payload_keys`, `document_text_chars`, `document_text_truncated`, `prompt_chars`. It tells which unit and rules a model was shown. A model call made outside the usual path (the draft memo) is recorded with fewer fields filled.

### 8.5 `audit/agent_switches.json`

Written at the start of every run. `{"schema_version": 1, "variable": "SHIMMER_INST_FINDER", "value": <the environment value or null>, "agent": "INST_FINDER", "setting": "on" | "off", "switched_off": [...], "ratified_by": <amendment id or null>, "refusal": <sentence or null>}`. `switched_off` is `["INST_FINDER"]` only when `off` was set and approved. A non-null `refusal` means the run stopped with exit code 9.

### 8.6 `audit/agent_activation.json`

Whether each agent was called, and why not. `agent_states` has one entry per agent: `agent`, `state`, `eligible`, `activated`, `actual_calls`, `decision_ids`. `state` is one of `phase_not_reached`, `eligible_inactive`, `ineligible`, `activated_not_dispatched`, `dispatch_started`, `completed`, `execution_failure`, `pre_dispatch_failure`, `no_execution_path`, `switched_off`. `decisions` lists every recorded decision with its `reason`.

### 8.7 `audit/run_options.json`

`{"schema_version": 1, "input_language": ..., "output_language": "en" | "tr", "agent_briefs": "enabled" | "disabled"}`. The output language changes the human-facing files only; field names, relations, outcomes and ids are never translated.

## 9. Model replies: `audit/model_replies/`

<!-- Sources: scripts/reply_records.py (SCHEMA_VERSION, DIRNAME, OUTCOMES_NAME, OUTCOMES, write, write_outcome, mark_not_promoted, records, outcomes, outcome_of); scripts/agent_wrapper.py (_write_reply, call_claude, call_gpt, call_qwen, call_local payload forms, run_task outcomes); scripts/auditor_pairs.py (classifier record and outcome); scripts/pipeline.py (_draft_generate_with_evidence; _paired_convention_review advisory flag; phase_6_synthesis mark_not_promoted); scripts/final_models.py (mode). -->

Every model call writes exactly one record here, whatever path it took. A run with no model call has no such folder. Embedding calls are not recorded.

**One record per call**: `<NNNNNN>_<call id>.json`, where `NNNNNN` is the call's sequence number in the run, six digits from `000001`.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | integer | `1`. |
| `sequence` | integer | The call's order in the run. |
| `call_id` | string | The call's id (32 hexadecimal characters). |
| `run_id` | string | The run id. |
| `agent` | string | The agent, or `AUDITOR896` for the reply classifier. |
| `backend` | string | The backend that answered. |
| `model_id` | string | The model's id. |
| `model_mode` | string or null | `base` or `final`. |
| `timestamp` | string | ISO 8601 UTC. |
| `phase`, `doc_id` | strings | The pipeline step and the document, `""` when unknown. |
| `decoding` | object | The decoding settings used. |
| `backend_ok` | boolean | `false` when the call failed. |
| `error_category` | string or null | The start of the error, up to the first colon. |
| `error` | string, optional | The error text, in a non-sensitive run only. |
| `sensitive` | boolean | `true` in a run with redaction on: then `text` is left out below. |
| `payload` | object or null | What was sent: `sha256`, `length_bytes`, `form` (`anthropic_messages_json`, `openai_messages_json`, `rendered_prompt` or `classifier_messages_json`) and `text`. |
| `reply` | object or null | What came back: `sha256`, `length_bytes` and `text`. For the classifier, the label. |

**`outcomes.jsonl`**: what happened to each reply, one line per decision: `{"call_id", "outcome", "source", "timestamp", ...}`, sometimes with `item_count`, `findings_withheld` or `pair_id`. A later line for the same `call_id` replaces an earlier one. A call with no line has the outcome `not_decided`.

| `outcome` | Meaning |
|---|---|
| `accepted_to_bus` | A valid reply; its items were posted on the bus. A judged-absence call (section 5.5) ends here. |
| `advisory_not_record` | A valid reply whose items were withheld from the bus: Python made the record from its own arithmetic (every judging call except a judged absence), or the call was a multi-round call. |
| `not_promoted` | The reply carried a finding that was kept in `model_findings_not_promoted` and not promoted. |
| `contract_violation` | The reply broke its required shape. |
| `refused` | A valid reply that refused the task. |
| `backend_failure` | The call failed. |
| `classified` | The reply classifier returned a label. |
| `classifier_failed` | The reply classifier failed. |
| `free_text` | The draft memo. |
| `not_decided` | No outcome was recorded. |

`call_id` joins a record to its line in `logs/call_evidence.jsonl`, to the bus line whose `body.call_id` matches, and to a judging-call record (section 5.6).

## 10. Multi-round outputs

<!-- Sources: scripts/multi_round.py (begin, activation, write_record, validate_records, project, read_saved, STATES, KINDS, MOVEMENTS, CATEGORIES); scripts/multi_round_phase.py (execute, accept_review); scripts/multi_round_rounds.py (review_rounds, review_document, _findings_for_plans, _rebase, bus_envelopes, post_findings, PYTHON_PLAN_KINDS, SIGNATURE_INPUTS, FINDINGS_AGENT); scripts/paired_review.py (finding_from_check: source_rule_id defaults to empty); scripts/pipeline.py (main: multi-round branch returns before the convention assignment, exit 8, reached_end with amendment_count 0); tools/ordinary_final_run.py (assess, MULTI_ROUND_ARGV). -->

A multi-round run (input format, section 12) writes `audit/multi_round.json`, `audit/round_reuse.json`, its bus posts, its model replies, `audit/reference_index.json` (the source spans only), `audit/agent_switches.json`, `audit/run_options.json`, `audit/agent_activation.json` and `audit/run_completion.json`. It writes no deliverables, no amendments, no `audit/pairing_map.json` and no `audit/convention_assignment.json`, and its folder is never renamed.

### 10.1 `audit/multi_round.json`

| Field | Meaning |
|---|---|
| `schema_version`, `run_id` | `1` and the run id. |
| `baseline_commit` | A fixed code reference; not needed for scoring. |
| `activation` | `{"requested", "eligible", "activated", "state", "reason"}`. `state` is `not_requested`, `refused`, `activated` or `phase_not_reached`. `reason` names a refusal (such as `fixture_requires_offline_test_adapter`, `sensitive_multi_round_unavailable`, `explicit_non_sensitive_declaration_required` or `independent_review_unavailable`). |
| `manifest` | The case manifest, as given. |
| `fixture` | The manifest's `fixture` value. |
| `evidence` | The source spans, each as declared plus its `ref_id`. |
| `round_review` | The Python round review: `{"record": "audit/round_reuse.json", "availability": ..., "bus_envelopes": <count>}`, or `{"availability": "failed", "error_type": ...}`. `availability` is `recorded`, `no_conventions` or `unavailable`. |
| `records` | The models' position records after review (below). Empty when refused. |
| `strategic_layer` | The decision-support layer's record. Not needed for scoring. |
| `outcome` | `reviewed` when the whole case phase ran, `refused` when it stopped. Missing means the phase did not complete. |

A **record** is flat: `record_id`, `case_id`, `actor_id`, `issue_id`, `round_id`, `kind` (`position`, `movement`, `unresolved_issue`, `trajectory` or `decision_support`), `state` (`accepted`, `rejected`, `refused`, `unresolved`, `insufficient_evidence`, `not_comparable` or `unknown`), `category` (`observed_evidence`, `semantic_interpretation` or `recommendation`), `confidence` (`CONFIDENT` or `UNCERTAIN`), `text`, `source_ids`, `ref_ids`, and, by kind, `position`, `value` and `unit`, `previous_round_id`, `previous_position_id`, `current_position_id`, `movement` (`concession`, `hardening`, `reversal`, `stable`, `ambiguous` or `unknown`). It also carries `review_state` (the reviewer's decision, or `missing`), the producer's and the reviewer's `agent`, `backend`, `model` and `call_id` (as `producer_...` and `reviewer_...`), `item_id`, `revision` and `ref`. Every record is written by a model. The same records are posted on the bus with `body.event` `MULTI_ROUND_REVIEWED` (envelope `doc_id` is the case id); they are not findings.

A multi-round run is healthy when `outcome` is `reviewed`, `activation.activated` is `true`, `round_review.availability` is `recorded`, and `audit/run_completion.json` says `completed`. A case with no conventions gives `no_conventions`, which is not healthy.

### 10.2 `audit/round_reuse.json`

Python's round review.

| Field | Meaning |
|---|---|
| `schema_version`, `case_id` | `1` and the case id. |
| `rule` | A sentence stating the reuse rule. |
| `availability`, `reason` | As in `round_review` above; `reason` only when unavailable. |
| `rounds` | One entry per round, in `sequence` order: `round_id`, `sequence`, `documents`. |

A document entry is `{"document_id", "availability": "missing_document"}` for a missing document, or `{"document_id", "units", "pairs_computed", "units_reused", "units_computed", "findings"}`. `findings` lists the document's Python findings in this round, in the shape of section 6, with `provenance: "computed"`, and `absence_path: "computed"` on a declared absence. These findings cite no REF id and carry no `source_rule_id`: only the registry id. A multi-round run folder holds no map from registry ids to operator's own ids. Registry ids are numbered `CONV-001`, `CONV-002`, ... in reading order of the conventions (input format, section 3, where a dropped short rule still uses up a number), so the map can be rebuilt from the bundle's conventions. An answer key travels without them: a scorer that checks the rule of a multi-round finding must be given the case's sealed conventions files too.

What the round review computes: sums, products, blank cells, bands the rule states itself, and declared absences. It does not compute reference-table or labelled-sentence bands, date windows, change records or the "no rule applies" finding.

A unit entry: `unit_id`, `signature` (a hash of what the computation read), `status` (`computed` or `reused`), `reused_from` (`{"round_id", "document_id", "unit_id"}`, when reused), `pairs`, `pairs_computed`, `findings` (a count), and `needs_model` (`{"unit_id", "rule_id", "kind"}` for each question that needed a model and was not asked).

**On the bus**, each round document's findings are posted once, on channel `multi_round`, under `PRACTICE_AUDITOR`, with backend `paired` and model `python` (written by `python`), with `doc_id` the document id, each item carrying `round_id` and an `item_id` of the form `round:<round id>:<document id>:<unit id>:<rule id>:<n>`. A reused finding is therefore posted again in each later round, under its new unit id.

## 11. Cloud runs: the session folder

<!-- Sources: tools/ordinary_final_cloud.py (execute, run_entry, collect and its pack script, batch_schedule, batch_entries, BATCH_ARMS, park_command, consumed, save calls: run_record.json, launch.json, operator_authorization.json, workload_return.json, asset_copy_receipt.json, independent_inventory_confirmation.json, cleanup.json, controller_failure.json); tools/ordinary_final_bound_cloud.py (run_folder, refuse_sealed_bundle_in_repository); tools/ordinary_final_run.py (execute, assess, failure_identity, budget_stop); tools/analyze_ordinary_final_run.py (analyze, analyze_batch, report_fields, write_report). -->

A cloud run is controlled from this machine. The **session folder** is the prepared bundle's own folder, or, when the launch names an output folder, a fresh copy `<output folder>/<bundle name>` (then `<bundle name>.2`, `.3`, ... if earlier attempts left folders). A sealed run's bundle and session folder sit outside the repository.

The controller collects the run as one archive, `collected_evidence.tar.gz`. The analyser (`tools/analyze_ordinary_final_run.py`, run separately after the controller) checks it and unpacks it into `downloaded/`. Until the analyser has run, there is no `downloaded/` folder.

### 11.1 Layout after collection and analysis

| Path inside the session folder | For | Meaning |
|---|---|---|
| `downloaded/evidence/run/` | machine | The pipeline's run folder (sections 3 to 10). **This is the folder a scorer reads.** |
| `downloaded/evidence/result.json` | machine | The runner's health check (below). |
| `downloaded/evidence/terminal_error.json` | machine | Present when the pipeline raised an error: `error_type`, `error_module`, `error_frame`, `error_origin` (file, line and function names only). |
| `downloaded/evidence/network.jsonl` | machine | Network attempts, which are denied during the run. |
| `downloaded/BUDGET_WORKLOAD_STOP.json` | machine | Present when the budget stop ended the run: `{"epoch", "completed": false}`. |
| `downloaded/...` | | Every other collected file, with the same paths as on the instance. |
| `FINAL_STATUS.json` | machine | The analyser's summary (below). |
| `RUN_REPORT.md` | human | The same report rows as text. |
| `verified_evidence.json` | machine | `{"passed": true, "members", "archive_sha256", "originals_unmodified": true}`: the download matched its hashes. |
| `analysis/` | machine | Cost and telemetry summaries; not described here. |
| `run_record.json` | machine | The launch plan: `purpose`, `exposure` (`exposed` or `sealed`), `test_manifest_sha256`, `multi_round`, `protected_test`, `shimmer_inst_finder`, `frozen_tag`, `batch_entries`, `report`. |
| `launch.json` | machine | `instance_id`, `epoch`, `hourly_rate`, `instance_type`, `region`. |
| `workload_return.json` | machine | `exit_code` (section 4.2, code 124), `epoch`, `full_run_retried`. |
| `collected_evidence.tar.gz`, `remote_collection_manifest.json`, `collection_integrity.json` | machine | The collected archive and its hashes. |

**`evidence/result.json`**: `execution_integrity_passed` (boolean), `reasons` (list), `failed_backend_attempts` (integer), `collection_and_teardown_pending` (`true`), `quality_claim` (`null`), `pipeline_exit_code` (integer). `reasons` values: `pipeline_not_completed`, `required_telemetry_missing`, `auditor_pair_failure`, `required_contract_failure`, `backend_failure`, and for a multi-round run `multi_round_not_reviewed`, `multi_round_not_activated`, `multi_round_round_review_not_recorded`. The runner's own exit code is 0 only when the pipeline returned 0 and the check passed; otherwise 2.

**`FINAL_STATUS.json`** fields: `status` (`ORDINARY_FINAL_CLOUD_RUN_COMPLETED` when the run folder says `completed` and the health check passed, else `ORDINARY_FINAL_CLOUD_RUN_FAILED`), `pipeline_started`, `pipeline_completion` (the run's `run_completion.json` or `null`), `remote_result` (`result.json` or `null`), `terminal_error`, `semantic_call_receipts`, `producer168_receipts`, `auditor896_receipts`, `auditor896_pairs`, `auditor896_pairs_from_partial_delivery`, `cost_estimates` (an object; `combined_estimate` is the estimated dollars), `within_hard_ceiling`, `exactly_one_instance`, `maximum_one_workload_invocation`, `full_run_retried`, `protected_data_accessed`, `multi_round_declared`, `multi_round_executed`, `inventory_empty`, `temporary_ssh_removed`, `evidence_verified`, `quality_claim` (`null`), `subsequent_roadmap_work_started`, and `report`.

**`report`** maps each row title to a sentence. The titles, in order: `Purpose`, `Sealed or exposed`, `Date and time (UTC)`, `Code commit`, `Test version`, `Test manifest hash`, `Authors (test, key, scorer)`, `Scorer version`, `Models and checkpoints`, `Decoding settings`, `Backend and machine`, `Instance type and price`, `Cost`, `Location and reason-confirmed recall`, `Attribution`, `False positives in every deliverable`, `Clean-twin result`, `Layer that produced each catch`, `Catches that depended on a directive`, `Model-text review verdicts`, `Agents withheld or settings changed`, `SHIMMER_INST_FINDER`, `Multi-round`, `Asset copy`, `Role separation`, `What the result does not show`. The quality rows say they were not computed: scoring belongs to the scorer. The values are sentences for a human; do not parse them.

### 11.2 Batch sessions

One rented machine can run several bundles in turn. Each bundle's run has its own folder `batch/<NN>_<item>_<arm>/` inside the session folder:

- `NN` is the bundle's place in the schedule, two digits from `00`. `item` is the batch item's name (letters, digits, `_`, `.`, `-`). `arm` is `B3` or `B1`: the two arms the loop specification pairs; the code only names them. Items run in turn, each `B3` then `B1`.
- Each folder holds the files of section 11.1 for its own run: its `execution_manifest.json`, `seal.json`, `operator_authorization.json`, `workload_return.json`, its collected archive and, after analysis, `downloaded/`, `FINAL_STATUS.json` and `RUN_REPORT.md`. It also holds `seal_entry.json` (`index`, `item`, `arm`, `paired_with`, `bundle`, `execution_manifest_sha256`, `seal_sha256`, `exposure`, `test_manifest_sha256`) and copies of the session's `launch.json`, `run_record.json`, `asset_copy_receipt.json` and clean-up records.
- `paired_with` is the schedule index of the same item's other arm.
- **The batch folder is the one to score.** The analyser in batch mode reads only `batch/*` folders that hold `collection_integrity.json`, one run each. A folder without that file was not collected.
- After the last entry, or after a stop, the controller also collects the machine's state into the session folder itself. That copy repeats the last entry's evidence, or holds a partial run when the stop came mid-entry. The batch analyser does not read it; do not score it.
- The `Cost` row of a batch folder's report is the cost of the whole session, not of that bundle alone.

## 12. Files not described further

<!-- Sources: scripts/run_context.py; scripts/audit_synthesizer.py (summary fields, registered_agents); scripts/agent_wrapper.py (_persist_contract_violation_raw_text); scripts/cost_tracker.py; scripts/model_telemetry.py; scripts/generation_observation.py; scripts/run_options.py (record_prompt); scripts/execution_topology.py; scripts/auditor_pairs.py; scripts/absence_prediction.py; scripts/document_dating.py; scripts/orchestrator.py; scripts/pipeline.py (model_bindings, editorial, pending approval); scripts/sensitivity_layer/redaction_stage.py; scripts/server.py. -->

These exist in some or all runs. They are for operations, debugging or human reading, and a scorer must not depend on them: `audit/audit_synthesis.md` and `audit/delta_proposals.json` (patterns across the audit trail and proposed rule changes), `audit/contract_violations/` (raw text of replies that broke their shape), `audit/feature_admission/`, `audit/editorial/`, `audit/redaction/`, `audit/execution_topology.jsonl`, `audit/absence_quote_prediction.json`, `audit/undated_documents.json`, `audit/pending_approval.json`, `audit/approval_decision.json`, `audit/multi_round_request.json` (server multi-round requests), `logs/cost_tracker.jsonl`, `logs/cost_tracker.json`, `logs/model_telemetry.jsonl`, `logs/generation_observation.jsonl`, `logs/prompt_structure.jsonl`, `logs/model_bindings.json`, `logs/run_summary_<YYYYMMDD>_<HHMMSS>.md`.

## 13. Open points

The code does not decide these. Each names the code it concerns.

1. **How a sealed run's folder reaches the scorer.** A sealed cloud run keeps its session folder outside the repository and prints counts only (`tools/ordinary_final_bound_cloud.py`, `run_folder`; `tools/ordinary_final_cloud.py`, `execute`). Nothing in the code hands `downloaded/evidence/run/` to the scorer. The repository's own scorer also looks for a twin's run only under `output/runs/` (`tools/score_corpus.py`, `twin_findings`), where no cloud run folder lands.
2. **Counting a judged absence once.** The model's raw judged-absence reply stays on the bus beside Python's stamped copy, including answers Python refused (section 5.5; `scripts/pipeline.py`, `_paired_convention_review`, `advisory = plan.get("kind") != "absence_judged"`). The repository's scorer counts every bus finding (`tools/score_corpus.py`, `_load_bus_findings`), so a refused answer can locate a planted flaw. Whether a scorer should read only the stamped copy is not decided.
3. **`severity` on an amendment** is the fixed string `required` (`scripts/paired_review.py`, `amendment_from_finding`), even under a `[recommended]` rule. Whether that is intended, or a defect to record, is not decided.
4. **Multi-round scoring.** The input format's section 9 now defines a multi-round key (entries scoped by round and document, scored on the round findings), but no scorer reads it yet. Round findings cite no REF id and carry no operator's own id, and the run folder holds no registry map (section 10.2; `scripts/multi_round_rounds.py`, `_findings_for_plans`; `scripts/pipeline.py`, `main`). The round review's scope (section 10.2; `PYTHON_PLAN_KINDS`, `review_document`) is what the code does; whether it is the intended scope for the first multi-round test is not decided.

## Sources

All files at branch `loop/s03`, commit `990ed88`, unless noted.

- `scripts/run_context.py`: module docstring, `DELIVERABLE_FILENAMES`, `RUN_SUMMARY_NAME`, `DRAFT_MEMO_NAME`, `IDENTITY_FILENAME`, `RunContext` (all path methods, `ensure`), `create_run`, `run_dirname`, `date_run_dirname`, `rename_run`, `start_run_in`, `for_run_dir`, `_recorded_run_id`.
- `scripts/run_completion.py`: `RunCompletion`, `reached_end`, `finish`, `begin`, `tracked`, `read`.
- `scripts/pipeline.py`: `main` (decorators, `--output-dir`, final-mode block, multi-round branch and its return before the convention assignment, every early return and exit code, rename at end only without `--output-dir`, `completion.reached_end`), `_load_corpus`, `_review_slug`, `_slug_from_question`, `_inst_finder_switch`, `_inst_finder_startup_guard`, `_inst_finder_decision`, `_prior_comparison`, `_paired_convention_review` (`consume_judgment`, the advisory flag, `judging_calls_by_agent`, computed post with `judging_calls`, `PAIRED_JUDGING_CALLS` post, stamped judged post, `pairing` fields), `_stamped_judged_items`, `_stamp_source_rule_ids`, `phase_6_synthesis` (`_process_doc`), `_harvest_amendment_payloads_from_bus` (called once, before any per-document step), `_polish_findings`, `_prior_refusals_for`, `_prior_orphans_for`, `_draft_generate_with_evidence`, `_render_per_agent_md`.
- `scripts/finding_record.py`: module docstring, `_FALLBACK`, `schema`, `is_finding`, `validate_finding`, `COMPUTED_BACKENDS`, `written_by`, `stamp_written_by`, `is_model_written`, `MODEL_FINDING_MARK`, `CHECKED_SOUNDING_FIELDS`, `model_finding_for_reader`, `RULE_ID_FIELD_ALIASES`, `resolved_rule_id`, `source_rule_id_for`, `PRIOR_RELATIONS`, `ABSENCE_RELATIONS`, `render_prior_comparison`, `figure_text`.
- `config/agent_contracts.json`: `finding_record` (fields, required, relations, verdicts, says), `envelope`.
- `scripts/paired_review.py`: `REL_TOLERANCE`, `ABS_TOLERANCE`, `unit_exponents`, `_unit_str`, `compute_checks`, `_close`, `disagreements`, `RELATION_DETAIL_FIELDS`, `finding_from_check`, `_default_explanation`, `dedupe`, `_absence_check`, `absence_plans`, `plan_calls` (plan kinds), `_rule_for_check`, `prior_checks`, `absent_checks`, `PRIOR_REFUSAL_KINDS`, `prior_findings`, `computed_finding_items`, `amendment_from_finding`, `stamp_note_writer`, `JUDGING_OUTCOMES`, `JUDGED_ABSENCE_PLAN`, `judging_call_record`, `judging_call_counts`, `notes_on_python_findings`, `note_models`, `computed_sentence`, `COMPUTED_PROVENANCE_WITH_NOTE`, `ABSENCE_PROVENANCE_WITH_NOTE`, `model_item_notes`, `_severity_makes_amendment`, `ensure_amendments_for_findings`, `figures_in_unit`, `unit_passage_refs`, `opens_with`.
- `scripts/pairing_map.py`: `pair_units`, `unmatched_findings`, `build_pairing_map`, `write_pairing_map`.
- `scripts/reference_tables.py`: `prior_values_for_scalars` (its refusals and their `reason_kind`).
- `scripts/agent_wrapper.py`, `current_items`, and `scripts/pipeline.py`, `_items_for`: supersession by `item_id` within one agent's results for one document.
- `scripts/pipeline.py`, `resolve_review_mode`; `tools/ordinary_final_run.py`, `ARGV` and `MULTI_ROUND_ARGV` (`--review-mode paired`).
- `scripts/amendment_render.py`: `CANONICAL_CONTENT_KEYS`, `MODEL_FINDINGS_KEY`, `render_model_findings`, `write_amendment_deliverables`.
- `scripts/docx_builder.py`: `comment_author`, `COMPUTED_AUTHOR`, `anchor_span`, `AmendmentDocxBuilder`.
- `scripts/message_bus.py`: `VALID_TYPES`, `VALID_ROLES`, `MessageBus.post`, `_validate`.
- `scripts/agent_wrapper.py`: `make_envelope`, `current_items`, `post_to_bus`, `_write_reply`, `run_task` (bus posts, `items_are_advisory`, `contract_normalized`, reply outcomes), payload `form` values.
- `scripts/reply_records.py`: whole module.
- `scripts/auditor_pairs.py`: the classifier's reply record and outcome.
- `scripts/call_evidence.py`: `RECORD_FIELDS`, `extract`, `record`.
- `scripts/convention_assignment.py`: `assign_conventions`, `write_assignment`.
- `scripts/reference_builder.py`: `ReferenceEntry`, `WebReferenceEntry`, `ReferenceIndex.save`, `index_document`.
- `scripts/agent_activation.py`: `ActivationAudit`, `STATE_WORDS`.
- `scripts/run_options.py`: `Options`, `configure`, `saved`.
- `scripts/final_models.py`: `mode`.
- `scripts/generation_observation.py`: `mark_incomplete`; `scripts/semantic_waves.py` (its call).
- `scripts/multi_round.py`: whole module.
- `scripts/multi_round_phase.py`: `execute`, `accept_review`.
- `scripts/multi_round_rounds.py`: whole module.
- `scripts/server.py`: `_STATUS_FIELDS`, `_write_status`.
- `tools/ordinary_final_run.py`: `execute`, `assess`, `failure_identity`, `argv_for`, `ARGV`, `MULTI_ROUND_ARGV`.
- `tools/ordinary_final_cloud.py`: `execute`, `run_entry`, `collect` and its pack script, `batch_schedule`, `batch_entries`, `BATCH_ARMS`, `park_command`, `consumed`.
- `tools/ordinary_final_bound_cloud.py`: `run_folder`, `refuse_sealed_bundle_in_repository`, `consumed`.
- `tools/analyze_ordinary_final_run.py`: `analyze`, `analyze_batch`, `report_fields`, `write_report`.
- `tools/score_corpus.py`: `main`, `_load_bus_findings`, `_load_review_data`, `_completeness_note`, `twin_findings`, `score`, `score_rounds` (used only to confirm which files the repository's own scorer reads).
