# STEP D2 REPORT: declared scope and Python-first absence (D, option 2)

**This fix is built without measurement. The gap is real, because it was traced in code
and in the stopped run's saved map. The fix is not known to be correct until a run scores
it. Nothing here is described as working; the worst-case reading was taken in each design.**

## The decision, as built

Scope is declared by the operator, never derived. Absence is Python first, the model only
where Python cannot settle it, and the path that decided each one is recorded.

## The declarations

Two bracket forms on a rule's heading, beside the severity and subject tags, read by their
leading word and by nothing else (`convention_parser._heading_bracket_declarations`;
neither is ever a subject):

- `[scope: class=A, device]`: the field labels, each optionally pinned to a value, that
  identify the units the rule governs. Carried on the registry entry as `scope`
  (`[{"label": "class", "value": "a"}, {"label": "device", "value": null}]`).
- `[requires: calibration authority signature]`: the field labels whose absence from a
  unit in scope is a finding. Carried as `requires`.

The labels and values are the operator's own words, lowercased, and normalised by the map
exactly as it normalises the document's own labels. The parser knows the two prefixes and
no label at all. A JSON conventions file may carry `scope` and `requires` directly.

## Pairing on a declared scope (`pairing_map.pair_units`)

A rule with a declared scope pairs with a unit when the unit carries every scope field and,
for a pinned entry, the field's value (read from the unit's own `label: value` line,
`unit_field_values`; a table cell is a row's value, not the unit's, and is not read). The
reason line names the declared scope (`unit carries every scope field the rule declares:
class=a, device`; `unit lacks the declared scope field ...`; `unit's class does not carry
the value the rule's scope declares`), never a document value. The fields the rule's text
happens to name are no longer requirements: D04's mention of the glossary's "fault window"
no longer rejects every entry. A scoped rule never goes to the similarity ranker.

## Absence, Python first (`paired_review.absence_plans`)

For every scoped rule paired on a unit:

- a declared required field the unit does not carry yields a plan of kind
  `absence_computed`: a `missing_field` check (0 of 1 required) that
  `finding_from_check` mints exactly as it mints any computed check; the pipeline makes NO
  call, posts the finding under the judging agent with backend `paired` and model `python`,
  stamps `absence_path: computed`, and logs `paired_review_absence ... path=computed`;
- a scoped rule with no declared requirement yields a plan of kind `absence_judged` on
  EVERY unit in scope, regardless of whatever else was computed on that unit: the
  requirement's condition has to be read from the rule's text, so the model is asked one
  narrow question on this unit alone (`build_pair_payload` plus an `absence_question`
  field). The model's typed Finding items in the reply are stamped by the pipeline with the
  unit and rule it asked about (known by construction), the operator's rule id,
  `absence_path: judged`, and an item id naming the unit and rule so two judged plans can
  never collide on the wrapper's derived id; they are posted under the judging agent with
  the MODEL's own backend and model (never `python`) and `stamped_by: python` on the body,
  and returned to phase 6 like any other item. A malformed or empty reply yields no items,
  never a dead run.

A scoped rule contributes nothing to the text-derived needed set of the shared checks and
is excluded from the old "uncomputable" branch (its question is planned above). Rules
without a declared scope pair and plan exactly as before.

## The record

`audit/pairing_map.json` per document gains `absence` (unit, rule, field for a computed
one, path, item count and the call id for a judged one), `absence_computed_count` and
`absence_judged_count`; the `paired_review_not_judged` log line carries both counts. Every
posted finding carries `absence_path`. A later reader can tell a computed absence from a
judged one on the map, on the bus and on the finding itself.

## The two consequences the operator asked to be reported, not smoothed over

- **Plan count.** With `[scope: ...]` and no `[requires: ...]` on a rule, one judged plan is
  made per unit in scope: on the device corpus, 18 entries per such rule. With three rules
  declared that way, about 54 more plans, most of them model calls on this corpus (its
  bands are prose, so little is computable). With `[requires: ...]` declared, the same
  rules cost no call at all: Python decides. The count rises exactly as much as the
  operator's declarations make conditional. On the VM that is cheap; correctness was not
  traded for it.
- **The clean twin.** Every judged question on a clean entry is a chance for a wrong "not
  required" or a wrong "missing". If the clean twin produces a wall of false positives,
  that is a real result about scope declaration and the model's reading of a condition, not
  a failure of the run, and the report of that run must say so plainly.

## Proof, on fixtures (check 209)

Executed, no model: the parser on a three-rule file (declarations read, subjects and
severity untouched, an undeclared rule unchanged); the real map on a glossary and three
entries (class a, class a without the signature, class b: the value match rejects class b,
the glossary unit pairs with nothing, the text-named glossary label is no requirement, no
reason line carries a document value); the real `plan_calls` (a computed absence for the
entry lacking the declared field, none for the entry carrying it, one judged question per
unit in scope for the conditional rule); the real `_paired_convention_review` with
`_run_one` stubbed (no call for the computed absence; three judged questions each carrying
`absence_question`; the computed finding posted once under paired/python on the right unit;
the judged answers stamped with unit, rule and `absence_path=judged` under the stub's own
provenance with unique item ids; the map's `absence` record with both counts and the call
ids; phase 6 receiving every item).

Neutralised, with `absence_plans` replaced by one that plans nothing:

```
('FAIL', "beta lacks the declared signature and must get a computed absence plan:
[('u02-entry-alpha', 'CONV-002', 'computed'), ('u03-entry-beta', 'CONV-001', 'computed'),
('u03-entry-beta', 'CONV-002', 'computed'), ('u04-entry-gamma', 'CONV-002', 'computed')]")
```

(With the absence plans gone, the scoped rules fall back into the old text-derived path
and the map's glossary label becomes a requirement of every entry again: the neutralised
plans above are exactly the old behaviour, and the check refuses them.)

Restored: `PASS`. Every check that touches the parser, the pairing map or the paired path
passes unchanged.

## What the operator still declares

Nothing in `benchmark/corpora/device_log_review/conventions/device_conventions.md` was
tagged with a scope or a requirement: that knowledge is the operator's. The mechanism is
ready for `[scope: ...]` and `[requires: ...]` on D02 to D05 (and any other rule) in both
the flawed corpus and the clean twin, and the measurement then runs on whatever was
declared.

## Gate result

```
PASS=208  WARN=0  SKIP=0  FAIL/ERROR=2  TOTAL=210
```

`output/d2_gate1.log`, run once at this HEAD. One check added (209), one more pass, WARN 0,
the same two source-only failures (checks 01 and 145).

---

STEP D2 COMPLETE (built without measurement; proved on fixtures by check 209)
