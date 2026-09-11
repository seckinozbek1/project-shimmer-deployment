# STEP FNE REPORT: false-negative evidence, the recording and the classification

Ordered by the operator on 2026-09-11 after the second W6 stop: build the false-negative
evidence classification, recording first, classifier on top, so that rules the model was
never asked and rules the model failed to answer stop landing in one recall number. Built
under the standing rule: no pipeline run, every proof on fixtures, a stubbed backend and
the artifacts already on disk.

## 1. The recording (`scripts/call_evidence.py`, `AgentWrapper.run_task`)

What was traced on 10 September held: every model call funnels through
`AgentWrapper.run_task`, which assembles a context package, renders the prompt, hands the
two strings to `dispatch`, and keeps nothing of them; after the call only a `CallResult`
survives (backend, model, raw text, usage). The cost row carried agent, backend, model,
phase, a per-document position and tokens; the bus post carried the parsed envelope; neither
carried a per-call id, and the items' own ids collide across calls. Which reference passages
reached the prompt was decided by a character budget inside the renderer and discarded.

`run_task` now records, just before dispatch, one line to `<run>/logs/call_evidence.jsonl`
with these fields and no others (`call_evidence.RECORD_FIELDS`): `call_id` (minted per
call), `run_id`, `ts`, `phase`, `doc_id` (the value `run_task` was given, the per-document
position in the phases that pass one), `agent`, `backend`, `model`, `task`,
`payload_document_id`, `unit_id` (the reviewed unit), `neighbour_unit_ids` (the units
immediately before and after it in the document map, listed only when the payload carried
their text), `heading_unit_id` (the unit whose heading opens the reviewed passage),
`document_unit_ids` (the map supplied for orientation), `reference_ids` (supplied),
`reference_ids_in_prompt` (the subset actually present in the bytes sent, read off the
prompt, not assumed), `rule_ids`, `payload_keys` (field names only), `document_text_chars`,
`document_text_truncated` (whether the token-budget clip cut a whole-document payload; a
clipped payload cannot prove a unit was inside it), `prompt_chars`. Never text: no unit
text, rule text, reference text or heading title. The same `call_id` goes on the call's
cost row (`CostEvent.call_id`) and on the bus post it produces (`AGENT_OUTPUT`,
`CONTRACT_VIOLATION` and `BACKEND_ERROR` bodies), so the three saved artifacts join. A
wrapper with no run context (the harness outside a run) records nothing and says so in its
return value; a write failure is logged and never takes a call down.

**Proof that one already-executed call reconstructs from saved data alone** (check 204,
executed): the real paired path (`build_pairing_map`, `_paired_convention_review`,
`_run_one`, `run_task`, `build_prompt`) runs on a two-unit domain-free document with one
computable rule and one reference, the backend replaced by a stub that keeps the prompt it
was shown and records a cost row as every real backend does. The one record is then read
back from the file alone and compared with the bytes the stub received: reviewed unit
`u01-unit-7`, neighbour `u02-unit-8` (the following unit only, and the prompt carries the
`following_unit_text` field and no `preceding_unit_text` field), heading, document map,
`REF-0009` supplied and present in the prompt, `CONV-001`, PRACTICE_AUDITOR, phase 5.5, the
run id, backend, model, timestamp, and a prompt length equal to the bytes sent. No passage
of the document, the rule or the reference appears in the record (`leaked_text`). The call
id on the record equals the call id on the cost row and on the bus post.

Neutralised, with `call_evidence.record` replaced by a no-op:

```
('FAIL', "no call_evidence.jsonl was written under the run's logs/ for a real paired call")
```

Restored: `PASS`.

## 2. The classifier (`scripts/fn_evidence.py`, through `tools/score_corpus.py`)

Every expected defect the run did not produce is put into exactly one of four classes,
from the run's saved artifacts and nothing else, each classification carrying its basis:

- `EVIDENCE_PRESENT_IN_MODEL_PAYLOAD`: a recorded call carried the rule and showed the
  unit, as the reviewed unit, as a supplied neighbour, or inside an unclipped whole-document
  payload whose map lists it (`call_evidence.calls_exposing`).
- `EVIDENCE_PRESENT_UPSTREAM_BUT_NOT_IN_PAYLOAD`: the unit is in the parsed document
  (`audit/pairing_map.json`) and the rule was loaded (`audit/convention_assignment.json`),
  but no call carried both: the pairing map never paired them, or a plan exists and the
  run's evidence file records no call for it. A missed defect for a rule that was never
  paired is this class, never the first, as instructed.
- `EVIDENCE_ABSENT_FROM_CORPUS`: no unit of the parsed document contains the key's unit, or
  the rule was never loaded by the run.
- `UNKNOWN`: no pairing map; a rule id no saved artifact maps to a registry id; or a planned
  pair on a run that predates the recording (the call may have happened; nothing saved says
  what it saw).

The mapping from the operator's own rule id (the key's `rule`) to the registry id the
pairing map and the evidence speak in is now saved per run: pipeline BOOT writes
`source_rule_id` beside every registry id in `audit/convention_assignment.json`. A second,
weaker source is any typed Finding's own (`source_rule_id`, `rule_id`) pair on the bus.
Nothing else is consulted; in particular not `config/convention_registry.json`, which is
regenerated at every BOOT and is not a record of the run being scored. The classifier never
opens an answer key (check 205 asserts its source names none): the scorer, the only reader
of a key, hands it each missed planted entry as a dict and prints, per entry, the class and
every artifact fact it rests on, plus the four counts.

**Proof** (check 205, executed on tempdir fixtures with a synthetic key built in memory):
seven cases across two fixture runs, one with an evidence file recording a paired call for
(u01, CONV-001) and one without: exposed to a recorded call; planned in the map but no
call recorded (the evidence file present); never paired; a unit the parsed document does
not contain; an unmappable rule id; a planned pair on a run with no recording; a
never-paired pair on that same run (provable from the map alone). The summary counts, and
that with no pairing map at all every miss is UNKNOWN. The scorer's wiring and BOOT's
mapping column are asserted in source.

Neutralised, with the pairing map hidden from the classifier:

```
('FAIL', "{'unit': 'u01', 'rule': 'CONV-A01'} on with_evidence: got UNKNOWN, expected
EVIDENCE_PRESENT_IN_MODEL_PAYLOAD (exposed to a recorded call carrying the rule);
basis=['no audit/pairing_map.json: the parsed document's units are not on record']")
```

Restored: `PASS`.

## 3. What the classifier says about the stopped run, honestly

Scored against the device key, run `20260911T123328Z__d5728e4b` (stopped in the paired
phase, no deliverable, findings on the bus only) has nine missed planted entries and the
classifier puts all nine in `UNKNOWN`, each with the same basis: the key's rule id (CONV-D01
to CONV-D08) maps to no registry id in that run's saved assignment, which predates the
`source_rule_id` column, and no typed Finding on its bus carries one of those rules. That
is the correct answer under "never infer": the second-stop section of the W6 report
establishes by hand, from the map's own rejection lines, that D02 to D05 were never paired,
but the map speaks in registry ids and the run saved no mapping. From the next run on, the
mapping is saved and the same misses would classify as
`EVIDENCE_PRESENT_UPSTREAM_BUT_NOT_IN_PAYLOAD` with the rejection reason as basis.

## 4. What changed

- `scripts/call_evidence.py` (new): the record, `extract`, `record`, `load`,
  `reconstruct`, `calls_exposing`, `leaked_text`.
- `scripts/fn_evidence.py` (new): the four classes, `load_run_artifacts`, `resolve_units`,
  `resolve_rule`, `classify`, `classify_missed`, `summary`.
- `scripts/agent_wrapper.py`: `run_task` mints the call id, records the evidence before
  dispatch, joins the id to the cost row (`_cost_call_id`) and the three bus bodies, and
  returns `call_id` and `call_evidence_path`.
- `scripts/cost_tracker.py`: `CostEvent.call_id`, `record(call_id=)`.
- `scripts/pipeline.py`: BOOT writes `source_rule_id` beside every registry id in the saved
  assignment.
- `tools/score_corpus.py`: classifies every missed planted entry and prints class, counts
  and basis.
- `scripts/verify_session1.py`: checks 204 and 205.
- `README.md` (the run folder's `logs/`, the corpora section, the check total 206),
  `CLAUDE.md` (key paths).

Every existing check that reads the wrapper, the cost rows or the bus bodies (9, 12, 26,
68, 83, 92, 95, 97, 98, 99, 100, 111, 123, 131, 134, 135, 136, 137, 140, 146, 147, 148,
149, 151, 160, 166, 175, 177, 180, 181, 195, 199, 203) still passes; nothing was weakened.
The em dashes in `scripts/agent_wrapper.py` (11) and `scripts/cost_tracker.py` (3) predate
this work and none was added.

## 5. Gate result

```
PASS=204  WARN=0  SKIP=0  FAIL/ERROR=2  TOTAL=206
```

`output/fne_gate1.log`, run once at this HEAD. Two checks added over W8's 204, two more
passes, WARN 0, the same two source-only failures (checks 01 and 145). The suite was not
run again at this HEAD.

## 6. Left open, recorded

- The two calls that do not go through `run_task` record nothing: draft phase 0 calls the
  drafter's `call_claude` directly, and the harness's arithmetic probe calls `dispatch` with
  its own prompt. Both are outside the review's finding path.
- `doc_id` on the record is the per-document position `run_task` is given in phases 3, 5
  and 5.5 (the cost row's own convention), not the document id; `payload_document_id`
  carries the payload's own identifier. Classification does not need the document id.
- Which bus messages reached a prompt is still decided by budget inside the renderer and
  not recorded; the record covers units, headings, references and rules, which is what a
  false negative is classified on.
- The board-only gap (D06 to D08 still paired and judged by PRACTICE_AUDITOR) is the next
  piece of work, as the operator ordered, and is unchanged here.

---

STEP FNE COMPLETE (recording proved on an executed call reconstructed from disk; the four
classes proved on fixtures; the scorer prints them per missed entry)
