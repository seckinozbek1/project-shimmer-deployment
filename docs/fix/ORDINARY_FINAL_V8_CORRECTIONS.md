# The pass after ordinary final run v8

Status: **CORRECTIONS_PROVEN_LOCALLY**. Local only: no cloud, no model execution, no weight
loading. Four Part 1 items were put on the table. ONE was a defect and is corrected; the other
three are not defects, and for the largest of them the proposal's premise is contradicted by the
run's own evidence. No weights, HPO settings, telemetry architecture, workload or routing
changed. The one behaviour change is in phase 5 and is stated under item 2.

## The rescope, and why

The pass was scoped around item 1: scoping CONV-L02 moved recall 3/5 to 4/5 and dropped phase
5.5 from 60.6 s to 1.0 s, so the proposal was to repeat that for the other four conventions.
**That saving cannot be repeated, because it has already been taken in full.** Measured on v8's
own artifacts:

- `logs/call_evidence.jsonl` contains NO phase-5.5 call. The remaining 1.0 s is Python.
- `audit/agent_activation.json` records every phase-5.5 plan as not-called:
  `exact_comparison_reason_rendered` six times and `declared_absence_computed` once.

So "the model call it should no longer need" is a call that does not exist. Item 1 reduces to
verifying the classification and declaring nothing, which is what was done. The item with real
value was item 2, FACT_CHECKER, the sole remaining integrity failure, and it was done first.

## 1. Every convention, classified by what the planner does with it

Measured through the real parser, splitter, pairing map and planner, no model:

| Rule | Its text names these document fields | Pairing | Plans | Classification |
|---|---|---|---|---|
| CONV-001 (conv-l01) | measured value, test | paired on all 6 | settled by the reference-table band path | **arithmetic, already handled**, with no scope declaration |
| CONV-002 (conv-l02) | all four | paired on all 6 | 1 `absence_computed` | **arithmetic, scoped last pass** |
| CONV-003 (conv-l03) | NONE | undecided on all 6 | none | sheet-level arithmetic whose subject is in no unit (item 5) |
| CONV-004 (conv-l04) | NONE | undecided on all 6 | none | a constraint on how a finding is WRITTEN, not on what a unit contains |
| CONV-005 (conv-l05) | NONE | undecided on all 6 | none | a prohibition on inference; no field decides it |

Three of the five name no field the document uses, so no scope declaration could pair them to a
unit: a scope pairs a rule to units carrying the scope field, and there is no such field to
name. An undecided rule is never dispatched, so none of the three costs a call today either.

CONV-001 deserves its own note. It IS arithmetic, and it is already fully computed, but by a
different mechanism: its band is read from the reference corpus's own table
(`reference_tables`), not from a scope declaration. In a harness without that binding its plans
appear as `uncomputable`; in the real run all six are `exact_comparison_reason_rendered`.
Declaring a scope on it would not improve that and would put a second mechanism in front of a
working one.

**Nothing further was declared.** Check 272 holds the classification and fails if a later pass
quietly scopes a rule that is not a unit-scoped question.

## 2. FACT_CHECKER, withheld for this corpus

**The evidence.** Three instrumented runs, no substantively correct item. v5 passed its contract
with five substantively wrong items; v7 and v8 failed it with five wrong items each, and v8's
output is BYTE-IDENTICAL to v7's (2,362 raw bytes) despite a complete PROCESSOR draft being
available and consumed successfully by VERIFIER in the same phase. Two prompt corrections have
been measured against it and the second changed nothing the model did.

**The mechanism.** The operator declares withheld auditors per review scope, in their own file:

```
config/review_scope.json  ->  "withheld_audit_agents": ["FACT_CHECKER"]
```

`pipeline._withheld_audit_agents` reads it from the run's own project root. A withheld agent is
recorded as `not_called` with reason `operator_withheld_for_corpus`, evidence naming the file and
field, and a `audit_agent_withheld` log line. It is NOT removed from `agent_registry.json` or
from `AUDIT_AGENTS_PER_DOC`, so LAW-III enforcement (check 148) sees exactly what it saw before,
and another corpus restores the agent by clearing one declaration with no code change. A name
that is not an audit agent is ignored rather than treated as a new agent.

**What it does to the integrity verdict.** Both of v8's reasons trace to that one call. Replayed
through the v8 runner's own `assess()` over v8's own telemetry:

| Input | Reasons | Integrity |
|---|---|---|
| As shipped | `pipeline_not_completed`, `required_contract_failure` | failed |
| With FACT_CHECKER's rows removed | none | **passed** |

The mechanism is direct: the call is the only `contract_valid: false` model call in the run
(`required_contract_failure`), and as a failed optimized-semantics call it sets
`semantic_incomplete`, which turns `completed` into `stopped` and produces
`pipeline_not_completed`. A call that is never made can do neither.

**What it does to the phase-5 shape.** VERIFIER alone is dispatched, with the same draft, the
same payload and the same advisory pairing request; the classifier still receives its seven
pairs, since the pairing hangs off VERIFIER. Phase 5 loses one call of about 975 output tokens.
Nothing else in the phase changes.

Recorded in `docs/fix/TUNING_BACKLOG.md` with the evidence, including what the evidence does NOT
establish (capability versus prompt versus framing, and behaviour on other corpora).

## 3. STYLE_GUARDIAN is correct behaviour

In paired mode the judging agent is pinned to `CONVENTION_REVIEW_AGENTS[0]`, PRACTICE_AUDITOR, so
STYLE_GUARDIAN never judges a pair. This is the documented design in
`docs/api/CONVENTION_ASSIGNMENT_DESIGN.md`. In v8 it is recorded exactly 7 times, once per plan,
always with `selected_agent: PRACTICE_AUDITOR`. The count tracks the plan count rather than being
a fixed 11, which is what a correct per-plan record looks like. Not a defect; nothing corrected.

## 4. The absence forecast is not exercised, correctly

`absence_quote_prediction.json` forecasts 14 judged and 7 computed plans, and carries its own
limit clause: "Historical plan counts are a forecast, not a required cohort size or a claim
count." In v8 it records `status: not_exercised`, `judged_plans: 0` and `count_comparison:
differs` rather than claiming a match. Worth noting: `computed_plans` is now **1**, where it was
0 in v5, v6 and v7, which is the CONV-L02 declaration showing up in the forecast's own counters.
The judged path stays at 0 because no rule on this corpus is scoped without a declared
requirement, which is the condition for a judged absence plan. Behaving as designed. Not a
defect; nothing corrected.

## Proofs

Checks 271 and 272, with five executed proofs in `scripts/ordinary_final_correction_checks.py`
and one new neutralize/fail/restore/pass entry in the integration gate:

| Proof | What it executes |
|---|---|
| the declaration is read from the operator's file | the shipped scope, a stray name ignored, an empty scope, the registry and audit list untouched |
| a withheld agent is not dispatched and is recorded | the live `phase_5_audit` with the declaration staged in the run's own root, and the same path WITHOUT it dispatching both auditors |
| withholding removes both v8 integrity reasons | the v8 runner's own `assess()` over v8's own telemetry, shipped and with the rows removed |
| every rule is classified by the planner | the live pairing map and planner over the real corpus |
| the real run made no phase-5.5 model call | v8's activation ledger and call evidence |

Both pinned reference contracts carry a fourth amendment for the `phase_5_audit` change and the
new `_withheld_audit_agents`.

## Gates

| Gate | Result |
|---|---|
| Correction checks | 29 checks, no skips |
| Compact-contract gate with its safe-gate baseline | 85 passed, PASS |
| Report-recommendations mutations | 15 of 15 |
| Controller, startup, decoding | PASS |
| Integration gate | 143 tests, 29 neutralize/fail/restore/pass proofs, PASS |
| Main gate against the clean baseline | see `docs/fix/ordinary_final_v10_gates/main_gate_comparison.json` |
