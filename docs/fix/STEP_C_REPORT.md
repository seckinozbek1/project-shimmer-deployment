# STEP C REPORT: the three recording gaps in the false-negative classifier

**These fixes are built without measurement. Each gap is real, because each was traced in
code. No fix is known to be correct until a run scores it. Nothing here is described as
working; the worst-case reading was taken in each design.**

## The three gaps, what each costs, whether it closes without a run

| gap | traced where | cost to close | closed? |
|---|---|---|---|
| 1. The draft memo call bypasses `run_task` and recorded nothing | `pipeline.py`, the draft block of `main()`: `_draft_generate` called `drafter.call_claude` directly | small: one module-level function that records the evidence, stamps the call id onto the cost row and makes the call; the draft block calls it; the passages retrieved are kept for their REF-* ids | yes, on fixtures |
| 2. The arithmetic probe bypasses `run_task` and recorded nothing | `scripts/harness/probe_arithmetic.py`, `probe()`: builds its own prompt and calls `wrapper.dispatch` | small: a call id and the prompt length per case in the probe's own records (its `--out` file), the id stamped onto the cost row when a tracker is passed | yes, on fixtures |
| 3. Which bus messages, reference passages and rule lines reach a prompt is decided by budget inside the renderer and was not recorded, so the first class could be asserted when a truncation had dropped what was needed | `bus_reader.py`: `_render_conventions` keeps `convs[:40]` then clips the section to a token budget; `_render_reference_index` leaves out passages that do not fit and clips; `_render_bus` drops the oldest messages | moderate: the package reports what each budgeted section actually kept, read off the finished text; the record carries requested and rendered ids apart; the classifier counts a rule only when its text reached the call | yes, on fixtures |

Gap 3 was the serious one. The registry section for a wide call with more than a handful
of rules is clipped (60 short rules against the 6000-character budget render a prefix and a
clip marker), so `rule_ids` on the record, which lists what was REQUESTED, was not the same
thing as what the model was shown. A miss for a rule beyond the clip would have classified
as "evidence present in the payload": confidently wrong in exactly the case the classifier
exists for.

## What was built

- `bus_reader.rendered_line_ids(section_text)`: the ids of the entries a budgeted section
  carries WHOLE, every `- <id> [` line of the finished text, minus the last such line when
  the section ends in the truncation marker (the clip falls mid-line, so that entry may be a
  fragment). Read off the text the model receives; nothing is assumed from the input list.
- `assemble_context` attaches `rendered` to the `ContextPackage`: `convention_ids`,
  `convention_text_truncated`, `reference_ids`, `reference_text_truncated`,
  `bus_messages_rendered`, `bus_messages_dropped` (`_render_bus` now returns the counts).
- The evidence record gains `rule_ids_rendered`, `reference_ids_rendered` (replacing the
  earlier substring search of the prompt for reference ids), `payload_rule_id`,
  `convention_text_truncated`, `reference_text_truncated`, `bus_messages_rendered`,
  `bus_messages_dropped`.
- `call_evidence.rule_reached(record, rule_id)`: true only when the rule's text reached the
  call, in the payload itself (a paired or polish call carries `rule_id` and `rule_text`,
  never clipped) or rendered whole in the registry section. `calls_exposing` uses it, so the
  classifier's first class requires the rule's text to have been shown, not merely asked
  for. Worst-case reading: a requested-but-clipped rule classifies as present upstream but
  not in the payload.
- `pipeline._draft_generate_with_evidence(drafter, stable, dynamic, passages, run_ctx)`:
  records `task=draft_memo`, the drafter's agent, backend and model, the run, the REF-* ids
  of the passages the prompt carried, the prompt length, a fresh call id also stamped on
  the cost row; then makes the call as before. The draft block of `main()` calls it and
  keeps the retrieved passages for the record.
- `probe_arithmetic.probe`: every case record carries `call_id`, `task=arithmetic_probe`
  and `prompt_chars`; the wrapper's cost row carries the same id.

## Proof, on fixtures only (check 207)

Executed, no model: `rendered_line_ids` on an unclipped and a clipped section; a real
`assemble_context` with 60 long rules (a proper prefix rendered, the clip flagged, every
reported id present as a whole line in the section text), 40 long passages (a strict
subset rendered, each present), and 40 bus messages against the bus budget (rendered plus
dropped equal to the offer, with a drop); a real `run_task` (dispatch stubbed) on a
wide-shaped payload requesting the 60 rules, whose record keeps 60 requested apart from the
rendered prefix; `rule_reached` false for a requested-but-clipped rule, true for a rendered
one, false for one nobody requested; the classifier, on a fixture run built from that
record, puts a miss for a rendered rule in the first class and a miss for a clipped rule
upstream, never in the payload; the draft memo call through
`_draft_generate_with_evidence` (call_claude stubbed) writes one record that agrees with the
call and clears the cost id afterwards; the probe's records carry unique call ids.

Neutralised, with `rendered_line_ids` replaced by a credulous reader that counts the
clipped last line:

```
('FAIL', 'a clipped section must not count its last, possibly partial, line')
```

Restored: `PASS`. Check 204's expected record was extended to the new fields; it passes.

## Known blind spots left, recorded, not assumed away

- The model's own context window. Nothing in this code drops tokens past a window: the
  local backends tokenise the whole prompt without a length cap, and the API backends
  reject an over-limit prompt with an error rather than clipping it. What a model attends
  to inside its window is not a recording question. `prompt_chars` is on the record so a
  reader can see how long each call was.
- Which OLDER bus messages were summarised rather than rendered is recorded as counts only.
  The classifier never uses bus context as evidence, so this cannot make the first class
  wrong; it is on the record so the count is visible.
- The `RUN_OBJECTIVES` and `PRECEDENTS` sections are clipped by token budgets and not
  itemised; neither carries a unit, a rule or a reference.
- The draft memo call's record has no unit, rule or document map, because the memo has
  none; it is outside the review's finding path.
- The probe runs outside a run folder; its evidence lives in its own `--out` records, not
  under `output/runs/`.

## Gate result

```
PASS=206  WARN=0  SKIP=0  FAIL/ERROR=2  TOTAL=208
```

`output/step_c_gate1.log`, run once at this HEAD. One check added (207), one more pass,
WARN 0, the same two source-only failures (checks 01 and 145). The em dashes in
`scripts/bus_reader.py` (4, inside the constitution and precedent renderers) predate this
work; none was added.

---

STEP C COMPLETE (all three gaps closed on fixtures; built without measurement; blind spots
recorded)
